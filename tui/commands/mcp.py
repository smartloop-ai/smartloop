"""MCPCommandsMixin — /mcp add|list|remove commands."""

from __future__ import annotations

import asyncio
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import httpx
from rich.table import Table
from textual import work
from textual.containers import VerticalScroll
from textual.widgets import Static

from smartloop.mcp import MCPClient, MCPOAuthService
from smartloop.mcp.oauth import MCPOAuthError

from tui.oauth import _find_free_port, _run_oauth_callback_server


class MCP:
    """Command handler for _handle_mcp_command and all _mcp_* helpers."""

    server_url: str
    model_name: str
    _current_worker: object

    # ------------------------------------------------------------------

    def _handle_mcp_command(self, args: str) -> None:
        """Dispatch /mcp sub-commands."""
        if args.startswith("add local "):
            rest = args[10:].strip()
            parts = rest.split()
            if len(parts) >= 3:
                name, raw_cwd, command, *cmd_args = parts
                cwd = Path(raw_cwd).expanduser()
                if not cwd.is_dir():
                    self._append_system(f"Directory not found: {cwd}")
                    return
                self._current_worker = self._mcp_add_local(name, command, cmd_args, str(cwd))
            else:
                self._append_system("Usage: /mcp add local <name> <cwd> <command> [args...]")
        elif args.startswith("add "):
            url = args[4:].strip()
            if url:
                self._current_worker = self._mcp_add(url)
            else:
                self._append_system("Usage: /mcp add <url>")
        elif args == "list":
            self._mcp_list()
        elif args.startswith("remove "):
            server_id = args[7:].strip()
            if server_id:
                self._mcp_remove(server_id)
            else:
                self._append_system("Usage: /mcp remove <id>")
        else:
            self._append_system("Usage: /mcp <add|list|remove>")

    @work(exclusive=True)
    async def _mcp_add(self, server_url: str) -> None:
        """Register a remote MCP server, handling OAuth if needed."""
        parsed = urlparse(server_url)
        if not parsed.scheme or not parsed.netloc:
            self._append_system("Invalid URL. Provide a full URL (e.g. https://example.com/mcp)")
            return

        # Warn early if the model is too small for tool use
        if self.model_name and "1b" in self.model_name.lower():
            self._append_system(
                f"[#f5d78e]Warning: The current model ({self.model_name}) may be too small for "
                f"reliable tool use. Consider switching to a model with 4B parameters for a "
                f"better experience.[/#f5d78e]"
            )

        query_params = parse_qs(parsed.query)
        token_from_url = query_params.get("token", [None])[0]
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}" if token_from_url else server_url

        self._set_loading("Connecting to MCP server...")

        try:
            result = await asyncio.to_thread(
                self._mcp_connect_sync, clean_url, token_from_url, "Bearer"
            )

            if result.success:
                await self._save_remote_mcp_server(
                    name=result.server_info.name if result.server_info else parsed.netloc,
                    server_url=clean_url,
                    auth_type="token_url" if token_from_url else "none",
                    token=token_from_url,
                    tools=result.tools,
                )
                return

            if token_from_url:
                self._append_system(f"Failed to connect: {result.error}")
                return

            # OAuth flow
            self._update_loading("Discovering OAuth metadata...")
            try:
                oauth_metadata, prm = await asyncio.to_thread(
                    self._mcp_discover_oauth_sync, clean_url
                )
            except MCPOAuthError as e:
                self._append_system(f"OAuth discovery failed: {e}")
                return

            if not oauth_metadata.registration_endpoint:
                self._append_system("OAuth server does not support dynamic client registration")
                return

            callback_port = _find_free_port()
            redirect_uri = f"http://localhost:{callback_port}/callback"

            self._update_loading("Registering OAuth client...")
            with MCPOAuthService() as oauth:
                registration = oauth.register_client(oauth_metadata.registration_endpoint, redirect_uri)

            code_verifier, code_challenge = MCPOAuthService.generate_pkce()
            state = MCPOAuthService.generate_state()

            scope = None
            scopes = oauth_metadata.scopes_supported or (prm.scopes_supported if prm else None)
            if scopes:
                scope = " ".join(scopes)

            with MCPOAuthService() as oauth:
                auth_url = oauth.build_authorization_url(
                    authorization_endpoint=oauth_metadata.authorization_endpoint,
                    client_id=registration.client_id,
                    redirect_uri=redirect_uri,
                    state=state,
                    code_challenge=code_challenge,
                    scope=scope,
                )

            self._update_loading("Waiting for browser authorization (2 min timeout)...")
            webbrowser.open(auth_url)

            auth_code = await asyncio.to_thread(
                _run_oauth_callback_server, callback_port, state
            )
            if not auth_code:
                self._append_system("Authorization timed out or failed")
                return

            self._update_loading("Exchanging code for tokens...")
            with MCPOAuthService() as oauth:
                token_response = oauth.exchange_code_for_tokens(
                    token_endpoint=oauth_metadata.token_endpoint,
                    code=auth_code,
                    redirect_uri=redirect_uri,
                    client_id=registration.client_id,
                    code_verifier=code_verifier,
                    client_secret=registration.client_secret,
                )

            expires_at = time.time() + token_response.expires_in if token_response.expires_in else None

            self._update_loading("Discovering tools...")
            result = await asyncio.to_thread(
                self._mcp_connect_sync, clean_url, token_response.access_token, token_response.token_type
            )

            if not result.success:
                self._append_system(f"Failed to connect after OAuth: {result.error}")
                return

            await self._save_remote_mcp_server(
                name=result.server_info.name if result.server_info else parsed.netloc,
                server_url=clean_url,
                auth_type="oauth",
                token_endpoint=oauth_metadata.token_endpoint,
                authorization_endpoint=oauth_metadata.authorization_endpoint,
                client_id=registration.client_id,
                client_secret=registration.client_secret,
                access_token=token_response.access_token,
                refresh_token=token_response.refresh_token,
                expires_at=expires_at,
                token_type=token_response.token_type,
                tools=result.tools,
            )

        except asyncio.CancelledError:
            self._append_system("[dim][interrupted][/dim]")
        except MCPOAuthError as e:
            self._append_system(f"OAuth error: {e}")
        except Exception as e:
            self._append_system(f"Error: {e}")
        finally:
            self._current_worker = None
            self._clear_loading()

    @work(exclusive=True)
    async def _mcp_add_local(self, name: str, command: str, args: list[str], cwd: str | None = None) -> None:
        """Register a local MCP server by command + args, with optional working directory."""
        self._set_loading(f"Registering local MCP server '{name}'...")
        try:
            payload: dict = {"name": name, "command": command, "args": args, "server_type": "local"}
            if cwd:
                payload["cwd"] = str(Path(cwd).expanduser())
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{self.server_url}/v1/mcp", json=payload)
                resp.raise_for_status()
                data = resp.json()
                tool_count = len(data.get("tools", []))
                self._append_system(
                    f"MCP server registered: {data.get('name')} ({tool_count} tools)"
                )
                if data.get("warning"):
                    self._append_system(f"[#f5d78e]{data['warning']}[/#f5d78e]")
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("detail", "")
            except Exception:
                pass
            self._append_system(f"Failed to register MCP server{': ' + detail if detail else ''}")
        except httpx.RequestError:
            self._append_system("Request failed")
        finally:
            self._current_worker = None
            self._clear_loading()

    @staticmethod
    def _mcp_connect_sync(server_url: str, access_token: str | None, token_type: str):
        """Run MCPClient.connect_and_discover_tools() synchronously (for use in a thread)."""
        with MCPClient() as client:
            return client.connect_and_discover_tools(
                server_url, access_token=access_token, token_type=token_type
            )

    @staticmethod
    def _mcp_discover_oauth_sync(server_url: str):
        """Discover OAuth metadata synchronously (for use in a thread)."""
        with MCPOAuthService() as oauth:
            oauth_metadata = None
            prm = None
            try:
                prm = oauth.discover_protected_resource_metadata(server_url)
                if prm.authorization_servers:
                    oauth_metadata = oauth.discover_oauth_metadata(prm.authorization_servers[0])
            except MCPOAuthError:
                pass
            if not oauth_metadata:
                oauth_metadata = oauth.discover_oauth_metadata(server_url)
            return oauth_metadata, prm

    async def _save_remote_mcp_server(self, name: str, server_url: str, auth_type: str,
                                      tools, **kwargs) -> None:
        """POST the remote MCP server data to the API."""
        payload = {
            "name": name,
            "server_url": server_url,
            "auth_type": auth_type,
            "tools": [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ],
            **{k: v for k, v in kwargs.items() if v is not None},
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{self.server_url}/v1/mcp/remote", json=payload)
                resp.raise_for_status()
                data = resp.json()
                tool_count = len(data.get("tools", []))
                self._append_system(f"MCP server registered: {data.get('name')} ({tool_count} tools)")
        except httpx.RequestError:
            self._append_system("Failed to save MCP server")
        except httpx.HTTPStatusError:
            self._append_system("Failed to save MCP server")

    @work(exclusive=True)
    async def _mcp_list(self) -> None:
        """List registered MCP servers."""
        self._set_loading("Fetching MCP servers...")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.server_url}/v1/mcp")
                resp.raise_for_status()
                servers = resp.json().get("servers", [])
            if not servers:
                self._append_system("No MCP servers registered")
                return
            table = Table(style="#6b5b7b")
            table.add_column("#", style="dim", width=3)
            table.add_column("Name")
            table.add_column("Type")
            table.add_column("Tools", justify="right", width=5)
            table.add_column("Tool Names", style="dim")
            table.add_column("Enabled")
            for i, s in enumerate(servers, 1):
                tools = s.get("tools", [])
                tool_names = ", ".join(t["name"] for t in tools) if tools else "—"
                table.add_row(
                    str(i),
                    s["name"],
                    s.get("server_type", "local"),
                    str(len(tools)),
                    tool_names,
                    "yes" if s.get("enabled") else "no",
                )
            log = self.query_one("#chat-log", VerticalScroll)
            log.mount(Static(table, classes="system-msg"))
            log.scroll_end(animate=False)
        except (httpx.RequestError, httpx.HTTPStatusError):
            self._append_system("Request failed")
        finally:
            self._clear_loading()

    @work(exclusive=True)
    async def _mcp_remove(self, index_str: str) -> None:
        """Remove a registered MCP server by its index number."""
        try:
            index = int(index_str)
        except ValueError:
            self._append_system("Invalid index. Use /mcp list to see numbered servers.")
            return

        self._set_loading("Removing MCP server...")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.server_url}/v1/mcp")
                resp.raise_for_status()
                servers = resp.json().get("servers", [])

                if index < 1 or index > len(servers):
                    self._append_system(f"Invalid index {index}. Servers have {len(servers)} entries.")
                    return

                server = servers[index - 1]
                del_resp = await client.delete(f"{self.server_url}/v1/mcp/{server['id']}")
                del_resp.raise_for_status()
                self._append_system(f"Removed MCP server: {server['name']}")
        except (httpx.RequestError, httpx.HTTPStatusError):
            self._append_system("Request failed")
        finally:
            self._clear_loading()


