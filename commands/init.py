"""InitCommand — init / bootstrap / SSE-stream command."""

from __future__ import annotations

import json

import requests
from requests.exceptions import RequestException
from tqdm import tqdm

from smartloop.constants import SLP_PRIMARY

from commands.base import Command
from commands.console import console


class InitCommand(Command):
    """Handles ``init`` and ``_bootstrap`` CLI commands."""

    args: object
    developer_token: str

    def execute(self) -> None:
        """CLI entry-point for the ``init`` command."""
        if not self._require_server():
            return

        explicit_model = getattr(self.args, "model", None)
        if explicit_model:
            self._init()
            return

        if self._is_ready():
            try:
                health = requests.get(f"{self._base_url()}/health", timeout=5).json()
                model_name = health.get("model_name", "unknown")
            except RequestException:
                model_name = "unknown"
            console.print(f"[{SLP_PRIMARY}][:white_check_mark:] Already set up with base model: {model_name}[/{SLP_PRIMARY}]")
            console.print(
                "[dim]To install additional models use your developer token:[/dim]\n"
                "[dim]  slp init --model=gemma3-4b --developer-token=<your-token>[/dim]"
            )
            return

        if self.developer_token:
            self._init()
            return

        console.print("[cyan]No developer token found. Setting up with the default base model...[/cyan]")
        self._bootstrap()

    def _init(self) -> None:
        """Authenticated init — download a specific model via /init."""
        payload = {}
        if m := getattr(self.args, "model", None):
            payload["model_name"] = m
        if self.developer_token:
            payload["developer_token"] = self.developer_token
        try:
            with requests.post(
                f"{self._base_url()}/v1/init",
                json=payload,
                stream=True,
                timeout=600,
            ) as resp:
                self._consume_sse_stream(resp)
        except RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")

    def _bootstrap(self) -> None:
        """Unauthenticated bootstrap — download model + create default project."""
        try:
            with requests.post(
                f"{self._base_url()}/v1/bootstrap",
                stream=True,
                timeout=1800,
            ) as resp:
                self._consume_sse_stream(resp)
        except RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")

    def _consume_sse_stream(self, resp: requests.Response) -> None:
        """Read an SSE response and render download progress / status messages."""
        if not resp.ok:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            console.print(f"[red]{detail}[/red]")
            return

        progress_bar = None
        for raw in resp.iter_lines():
            if not raw:
                continue
            line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            if not line.startswith("data:"):
                continue
            try:
                data = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue

            status = data.get("status", "")
            total = data.get("total", 0)
            downloaded = data.get("downloaded", 0)
            filename = data.get("filename", "")
            msg = data.get("message", "")

            if total and downloaded is not None:
                if progress_bar is None:
                    progress_bar = tqdm(
                        total=total, unit="B", unit_scale=True,
                        unit_divisor=1024, desc=filename or "Downloading",
                        dynamic_ncols=True,
                    )
                elif filename and progress_bar.desc != filename:
                    progress_bar.set_description(filename)
                progress_bar.n = downloaded
                progress_bar.refresh()
            elif status == "completed":
                if progress_bar is not None:
                    progress_bar.n = progress_bar.total
                    progress_bar.refresh()
                    progress_bar.close()
                    progress_bar = None
                console.print(f"[cyan][:rocket:] {msg}[/cyan]")
            elif status == "project_created":
                project = data.get("project", {})
                console.print(
                    f"[green][:white_check_mark:] Project created: "
                    f"{project.get('name', '')} (id={project.get('id', '')})[/green]"
                )
            elif status == "error":
                if progress_bar is not None:
                    progress_bar.close()
                    progress_bar = None
                console.print(f"[red]{msg}[/red]")
            else:
                if msg:
                    console.print(f"[dim]{msg}[/dim]")

        if progress_bar is not None:
            progress_bar.close()
