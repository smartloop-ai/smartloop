"""RuleCommandsMixin — /rule add|show|clear commands."""

from __future__ import annotations
from hashlib import md5

import httpx
from textual import work

from rich.table import Table
from textual.containers import VerticalScroll
from textual.widgets import Static

class Rule:
    """Command handler for _handle_rule_command and all _rule_* helpers."""

    server_url: str

    def _handle_rule_command(self, args: str) -> None:
        """Dispatch /rule sub-commands."""
        if args.startswith("add "):
            rule_text = args[4:].strip()
            if rule_text:
                self._rule_add(rule_text)
            else:
                self._append_system("Usage: /rule add <text>")
        elif args == "list":
            self._rule_list()
        elif args.startswith("remove "):
            rule_id = args[7:].strip()
            if rule_id:
                self._rule_remove(rule_id)
            else:
                self._append_system("Usage: /rule remove <id>")
        else:
            self._append_system("Usage: /rule <add|list|remove>")

    @work(exclusive=True)
    async def _rule_add(self, rule_text: str) -> None:
        """Add a rule to the project."""
        if not self.project_id:
            self._append_system("No project selected. Use /project add or /project list to switch to one.")
            return
        self._set_loading("Updating rules...")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                rules = await self._get_rules(client)

                if any(r.get("content") == rule_text for r in rules):
                    self._append_system("This rule already exists.")
                    return 

                rules.append({"content": rule_text})
        
                resp = await client.patch(
                    f"{self.server_url}/v1/projects/{self.project_id}",
                    json={"rules": rules},
                )
                resp.raise_for_status()
                self._append_system("New rule added")
        except (httpx.RequestError, httpx.HTTPStatusError):
            self._append_system("Request failed")
        finally:
            self._clear_loading()


    async def _get_rules(self, client: httpx.AsyncClient) -> list[dict]:
        """Helper to fetch current rules for the project."""
        resp = await client.get(f"{self.server_url}/v1/projects")
        resp.raise_for_status()
        for p in resp.json().get("projects", []):
            if p.get("id") == self.project_id:
                return p.get("rules", [])
        return []

    @work(exclusive=True)
    async def _rule_list(self) -> None:
        """Show current project rules."""
        if not self.project_id:
            self._append_system("No project selected.")
            return
        self._set_loading("Fetching rules...")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                rules = await self._get_rules(client)

            if not rules:
                self._append_system("No rules are set")
                return

            table = Table(style="#6b5b7b")
            table.add_column("#", style="dim", width=3)
            table.add_column("Description")
            for i, r in enumerate(rules, 1):
                table.add_row(str(i), r.get("content", ""))
            log = self.query_one("#chat-log", VerticalScroll)
            log.mount(Static(table, classes="system-msg"))
            log.scroll_end(animate=False)
        except (httpx.RequestError, httpx.HTTPStatusError):
            self._append_system("Request failed")
        finally:
            self._clear_loading()

    @work(exclusive=True)
    async def _rule_remove(self, idx: str) -> None:
        """Remove a rule from the project by 1-based index."""
        if not self.project_id:
            self._append_system("No project selected.")
            return
        try:
            index = int(idx)
        except ValueError:
            self._append_system("Usage: /rule remove <number>  (use /rule list to see indices)")
            return
        self._set_loading("Updating rules...")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                rules = await self._get_rules(client)
                if index < 1 or index > len(rules):
                    self._append_system(f"Invalid index {index}. Use /rule list to see available rules.")
                    return
                rules.pop(index - 1)
                resp = await client.patch(
                    f"{self.server_url}/v1/projects/{self.project_id}",
                    json={"rules": rules},
                )
                resp.raise_for_status()
                self._append_system(f"Rule {index} removed")
        except (httpx.RequestError, httpx.HTTPStatusError):
            self._append_system("Request failed")
        finally:
            self._clear_loading()


