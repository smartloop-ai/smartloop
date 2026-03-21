"""DocumentCommandsMixin — /document add|list|remove commands."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
from rich.table import Table
from textual import work
from textual.containers import VerticalScroll
from textual.widgets import Static


class Document:
    """Command handler for _handle_document_command and all _document_* helpers."""

    server_url: str
    project_id: str | None

    def _handle_document_command(self, args: str) -> None:
        """Dispatch /document sub-commands."""
        if not self.project_id:
            self._append_system("No current project. Create or switch to a project first.")
            return
        if args.startswith("add "):
            path = args[4:].strip()
            if path:
                self._document_add(path)
            else:
                self._append_system("Usage: /document add <path>")
        elif args == "list":
            self._document_list()
        elif args.startswith("remove "):
            doc_id = args[7:].strip()
            if doc_id:
                self._document_remove(doc_id)
            else:
                self._append_system("Usage: /document remove <id>")
        else:
            self._append_system("Usage: /document <add|list|remove>")

    @work(exclusive=True)
    async def _document_add(self, source: str) -> None:
        """Add a document to the project."""
        self._set_loading("Processing document...")
        try:
            documents: list[dict] = []
            event_type: str | None = None
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream(
                    "POST",
                    f"{self.server_url}/v1/projects/{self.project_id}/documents",
                    json={"source": source},
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            event_type = None
                            continue
                        if line.startswith("event:"):
                            event_type = line[len("event:"):].strip()
                        elif line.startswith("data:"):
                            payload = json.loads(line[len("data:"):].strip())
                            if event_type == "progress":
                                stage = payload.get("stage", "processing")
                                filename = payload.get("filename", "")
                                label = stage.capitalize()
                                if filename:
                                    label += f": {filename}"
                                self._set_loading(label)
                            elif event_type == "complete":
                                documents = payload.get("documents", [])
            if documents:
                for doc in documents:
                    name = Path(doc["path"]).name
                    self._append_system(f"Added: {name} (id={doc['id']})")
            else:
                self._append_system("No new documents added (may already exist)")
        except httpx.HTTPStatusError as e:
            detail = e.response.json().get("detail", "Unknown error") if e.response else "Unknown error"
            self._append_system(f"Failed to add document: {detail}")
        except httpx.RequestError:
            self._append_system("Request failed")
        finally:
            self._clear_loading()

    @work(exclusive=True)
    async def _document_list(self) -> None:
        """List project documents."""
        self._set_loading("Fetching documents...")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.server_url}/v1/projects/{self.project_id}/documents"
                )
                resp.raise_for_status()
                docs = resp.json().get("documents", [])
            if not docs:
                self._append_system("No documents in project")
                return
            table = Table(style="#6b5b7b")
            table.add_column("#", style="dim", width=3)
            table.add_column("Name")
            for i, doc in enumerate(docs, 1):
                table.add_row(str(i), Path(doc["path"]).name)
            log = self.query_one("#chat-log", VerticalScroll)
            log.mount(Static(table, classes="system-msg"))
            log.scroll_end(animate=False)
        except (httpx.RequestError, httpx.HTTPStatusError):
            self._append_system("Request failed")
        finally:
            self._clear_loading()

    @work(exclusive=True)
    async def _document_remove(self, index_str: str) -> None:
        """Remove a document by its index number."""
        try:
            index = int(index_str)
        except ValueError:
            self._append_system("Invalid index. Use /document list to see numbered documents.")
            return

        self._set_loading("Removing document...")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.server_url}/v1/projects/{self.project_id}/documents"
                )
                resp.raise_for_status()
                docs = resp.json().get("documents", [])

                if index < 1 or index > len(docs):
                    self._append_system(f"Invalid index {index}. Documents have {len(docs)} entries.")
                    return

                doc = docs[index - 1]
                del_resp = await client.delete(
                    f"{self.server_url}/v1/projects/{self.project_id}/documents/{doc['id']}"
                )
                del_resp.raise_for_status()
                name = Path(doc["path"]).name
                self._append_system(f"Removed: {name}")
        except (httpx.RequestError, httpx.HTTPStatusError):
            self._append_system("Request failed")
        finally:
            self._clear_loading()


