"""McpCommand — ``mcp`` CLI command (synchronous)."""

from __future__ import annotations

import time as _time
import webbrowser
from urllib.parse import urlparse, parse_qs

import requests
from prettytable import PrettyTable
from requests.exceptions import RequestException

from smartloop.constants import SLP_PRIMARY
from smartloop.mcp import MCPClient, MCPOAuthService
from smartloop.mcp.oauth import MCPOAuthError

from commands.base import Command
from commands.console import console
from commands.helpers import _find_free_port, _run_oauth_callback_server


class McpCommand(Command):
    """Handles ``mcp`` CLI sub-commands (add / list / remove)."""

    args: object

    def execute(self) -> None:
        """Dispatch mcp sub-commands."""
        sub = getattr(self, f"mcp_{self.args.mcp_command}", None)
        if sub:
            sub()
        else:
            console.print("[dim]Usage: slp mcp <add|list|remove>[/dim]")

    def mcp_add(self) -> None:
        """Register a remote MCP server (handles OAuth flow locally)."""
        if not self._require_server():
            return
        server_url = self.args.url
        parsed = urlparse(server_url)
        if not parsed.scheme or not parsed.netloc:
            console.print("[red]Invalid URL. Please provide a full URL (e.g. https://example.com/mcp)[/red]")
            return
        query_params = parse_qs(parsed.query)
        token_from_url = query_params.get("token", [None])[0]
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}" if token_from_url else server_url

        with console.status("[bold cyan]Connecting to MCP server...[/bold cyan]", spinner="dots"):
            with MCPClient() as client:
                result = client.connect_and_discover_tools(
                    clean_url, access_token=token_from_url, token_type="Bearer"
                )
        if result.success:
            self._save_remote_mcp_server(
                name=result.server_info.name if result.server_info else parsed.netloc,
                server_url=clean_url,
                auth_type="token_url" if token_from_url else "none",
                token=token_from_url,
                tools=result.tools,
            )
            return
        if token_from_url:
            console.print(f"[red]Failed to connect: {result.error}[/red]")
            return

        # OAuth flow
        console.print("[dim]No-auth connection failed, attempting OAuth...[/dim]")
        try:
            with MCPOAuthService() as oauth:
                with console.status("[bold cyan]Discovering OAuth metadata...[/bold cyan]", spinner="dots"):
                    oauth_metadata = None
                    prm = None
                    try:
                        prm = oauth.discover_protected_resource_metadata(clean_url)
                        if prm.authorization_servers:
                            oauth_metadata = oauth.discover_oauth_metadata(prm.authorization_servers[0])
                    except MCPOAuthError:
                        pass
                    if not oauth_metadata:
                        oauth_metadata = oauth.discover_oauth_metadata(clean_url)
                if not oauth_metadata.registration_endpoint:
                    console.print("[red]OAuth server does not support dynamic client registration[/red]")
                    return
                callback_port = _find_free_port()
                redirect_uri = f"http://localhost:{callback_port}/callback"
                with console.status("[bold cyan]Registering OAuth client...[/bold cyan]", spinner="dots"):
                    registration = oauth.register_client(oauth_metadata.registration_endpoint, redirect_uri)
                code_verifier, code_challenge = MCPOAuthService.generate_pkce()
                state = MCPOAuthService.generate_state()
                scopes = oauth_metadata.scopes_supported or (prm.scopes_supported if prm else None)
                scope = " ".join(scopes) if scopes else None
                auth_url = oauth.build_authorization_url(
                    authorization_endpoint=oauth_metadata.authorization_endpoint,
                    client_id=registration.client_id,
                    redirect_uri=redirect_uri,
                    state=state,
                    code_challenge=code_challenge,
                    scope=scope,
                )
                console.print("\n[bold]Opening browser for authorization...[/bold]")
                console.print("[dim]If the browser doesn't open, visit:[/dim]")
                console.print(f"[link]{auth_url}[/link]\n")
                webbrowser.open(auth_url)
                console.print("[bold cyan]Waiting for authorization (timeout: 2 min)...[/bold cyan]")
                auth_code = _run_oauth_callback_server(callback_port, state)
                if not auth_code:
                    console.print("[red]Authorization timed out or failed[/red]")
                    return
                console.print(f"[{SLP_PRIMARY}]Authorization received![/{SLP_PRIMARY}]")
                with console.status("[bold cyan]Exchanging code for tokens...[/bold cyan]", spinner="dots"):
                    token_response = oauth.exchange_code_for_tokens(
                        token_endpoint=oauth_metadata.token_endpoint,
                        code=auth_code,
                        redirect_uri=redirect_uri,
                        client_id=registration.client_id,
                        code_verifier=code_verifier,
                        client_secret=registration.client_secret,
                    )
                expires_at = _time.time() + token_response.expires_in if token_response.expires_in else None
                with console.status("[bold cyan]Discovering tools...[/bold cyan]", spinner="dots"):
                    with MCPClient() as client:
                        result = client.connect_and_discover_tools(
                            clean_url,
                            access_token=token_response.access_token,
                            token_type=token_response.token_type,
                        )
                if not result.success:
                    console.print(f"[red]Failed to connect after OAuth: {result.error}[/red]")
                    return
                self._save_remote_mcp_server(
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
        except MCPOAuthError as e:
            console.print(f"[red]OAuth error: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def _save_remote_mcp_server(self, name: str, server_url: str, auth_type: str, tools, **kwargs) -> None:
        """POST the remote MCP server data to the API for persistence."""
        payload = {
            "name": name,
            "server_url": server_url,
            "auth_type": auth_type,
            "tools": [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ],
            **kwargs,
        }
        try:
            resp = requests.post(f"{self._base_url()}/v1/mcp/remote", json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            console.print(f"\n[{SLP_PRIMARY}]MCP server registered: {data.get('name')}[/{SLP_PRIMARY}]")
        except RequestException as e:
            console.print(f"[red]Failed to save MCP server: {e}[/red]")

    def mcp_list(self) -> None:
        """List registered MCP servers."""
        if not self._require_server():
            return
        try:
            resp = requests.get(f"{self._base_url()}/v1/mcp", timeout=10)
            resp.raise_for_status()
            servers = resp.json().get("servers", [])
            if not servers:
                console.print("[dim]No MCP servers registered[/dim]")
                return
            table = PrettyTable()
            table.align = "l"
            table.title = "MCP Servers"
            table.field_names = ["ID", "Name", "Type", "Tools", "Enabled"]
            table.align["Tools"] = "r"
            for s in servers:
                table.add_row([
                    s["id"][:8],
                    s["name"],
                    s.get("server_type", "local"),
                    len(s.get("tools", [])),
                    "yes" if s.get("enabled") else "no",
                ])
            print(table)
        except RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")

    def mcp_remove(self) -> None:
        """Remove a registered MCP server."""
        if not self._require_server():
            return
        target_id = self.args.id
        try:
            resp = requests.get(f"{self._base_url()}/v1/mcp", timeout=10)
            resp.raise_for_status()
            servers = resp.json().get("servers", [])
            found = next(
                (s for s in servers if s["id"] == target_id or s["id"].startswith(target_id)), None
            )
            if not found:
                console.print(f"[red]MCP server not found: {target_id}[/red]")
                return
            del_resp = requests.delete(f"{self._base_url()}/v1/mcp/{found['id']}", timeout=10)
            del_resp.raise_for_status()
            console.print(f"[{SLP_PRIMARY}]Removed MCP server: {found['name']} ({found['id'][:8]})[/{SLP_PRIMARY}]")
        except RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")
