"""ModelCommand — ``status`` CLI command."""

from __future__ import annotations

import requests
from prettytable import PrettyTable
from requests.exceptions import RequestException

from smartloop.server import is_server_running, read_pid_file

from commands.base import Command
from commands.console import console


class ModelCommand(Command):
    """Handles the ``status`` CLI command."""

    args: object
    host: str
    port: int

    def execute(self) -> None:
        """Route to status, build, or train based on the active command."""
        handler = getattr(self, self.args.command, None)
        if handler:
            handler()

    def status(self) -> None:
        """Show server, model, and GPU status."""
        if not is_server_running(self.host, self.port):
            console.print("[dim]Server not running[/dim]")
            return

        table = PrettyTable()
        table.field_names = ["Property", "Value"]
        table.align["Property"] = "l"
        table.align["Value"] = "l"

        try:
            health = requests.get(f"{self._base_url()}/health", timeout=5).json()
            table.add_row(["Server", f"http://{self.host}:{self.port}"])
            pid = read_pid_file()
            if pid:
                table.add_row(["PID", pid])
            table.add_row(["Model loaded", health.get("model_loaded", False)])
            if health.get("model_name"):
                table.add_row(["Model", health["model_name"]])
            if health.get("quantization"):
                table.add_row(["Quantization", health["quantization"]])
            if health.get("n_ctx"):
                table.add_row(["Context window", health["n_ctx"]])
            if health.get("n_gpu_layers") is not None:
                table.add_row(["GPU layers", health["n_gpu_layers"]])
            if health.get("flash_attn") is not None:
                table.add_row(["Flash attention", health["flash_attn"]])
            model_bytes = health.get("model_size_bytes", 0)
            if model_bytes:
                size_gb = model_bytes / (1024 ** 3)
                table.add_row(["Model size", f"{size_gb:.1f} GB" if size_gb >= 1 else f"{model_bytes / (1024 ** 2):.0f} MB"])
            if health.get("memory_percent") is not None:
                table.add_row(["Memory usage", f"{health['memory_percent']}%"])
            try:
                import torch
                if torch.cuda.is_available():
                    table.add_row(["GPU", torch.cuda.get_device_name(0)])
                    table.add_row(["GPU memory", f"{torch.cuda.get_device_properties(0).total_memory / (1024 ** 3):.1f} GB"])
                elif torch.backends.mps.is_available():
                    table.add_row(["GPU", "Apple Silicon (MPS)"])
                else:
                    table.add_row(["GPU", "None (CPU only)"])
            except Exception:
                pass
        except RequestException:
            pass

        try:
            data = requests.get(f"{self._base_url()}/v1/projects", timeout=10).json()
            current = next((p for p in data.get("projects", []) if p.get("current")), None)
            if current:
                table.add_row(["Active project", f"{current.get('name')} (id={current.get('id')})"])
                table.add_row(["Project model", current.get("model_name") or "default"])
        except RequestException:
            pass

        console.print(table)
