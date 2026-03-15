"""RuleCommand — ``rules`` CLI command."""

from __future__ import annotations

import requests
from requests.exceptions import RequestException

from smartloop.constants import SLP_PRIMARY

from commands.base import Command
from commands.console import console
from commands.helpers import load_file_content, get_rule_input


class RuleCommand(Command):
    """Handles the ``rules`` CLI command."""

    args: object

    def execute(self) -> None:
        """Add or update project rules."""
        if not self._require_server():
            return
        existing_rules = ""
        try:
            resp = requests.get(f"{self._base_url()}/v1/rules", timeout=5)
            if resp.ok:
                existing_rules = resp.json().get("rules", "")
        except RequestException:
            pass

        if self.args.file:
            rule_text = load_file_content(self.args.file)
        else:
            try:
                rule_text = get_rule_input(existing_rules)
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Rule input cancelled[/yellow]")
                return

        if rule_text and rule_text.strip():
            try:
                resp = requests.put(
                    f"{self._base_url()}/v1/rules",
                    json={"rule": rule_text},
                    timeout=30,
                )
                resp.raise_for_status()
                console.print(f"[{SLP_PRIMARY}]Rules updated[/{SLP_PRIMARY}]")
            except RequestException as e:
                console.print(f"[red]API Error: {e}[/red]")
        else:
            console.print("[red]No rule text provided[/red]")
