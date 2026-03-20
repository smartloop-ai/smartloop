"""PromptTextArea — Enter-to-submit TextArea with command menu routing."""

from __future__ import annotations

from textual import events
from textual.widgets import TextArea

from tui.constants import SLASH_COMMANDS
from tui.widgets.command_menu import CommandMenu


class PromptTextArea(TextArea):
    """TextArea subclass: Enter submits, Ctrl+A selects all."""

    def _on_paste(self, event: events.Paste) -> None:
        """Strip backslash-escaped spaces (e.g. foo\\ bar.txt) on paste."""
        cleaned = event.text
        # Strip file:// prefix from drag-and-drop paths
        if cleaned.lower().startswith("file://"):
            cleaned = cleaned[7:]
        cleaned = cleaned.replace("\\ ", " ")
        if cleaned != event.text:
            event.prevent_default()
            self.insert(cleaned)

    async def _on_key(self, event: events.Key) -> None:
        # Route keys to command menu when visible
        try:
            menu = self.app.query_one("#command-menu", CommandMenu)
            menu_visible = menu.display
        except Exception:
            menu_visible = False

        if menu_visible:
            if event.key == "up":
                event.stop()
                event.prevent_default()
                menu.action_cursor_up()
                return
            if event.key == "down":
                event.stop()
                event.prevent_default()
                menu.action_cursor_down()
                return
            if event.key in ("tab", "enter"):
                event.stop()
                event.prevent_default()
                if menu.highlighted is not None:
                    option = menu.get_option_at_index(menu.highlighted)
                    cmd = option.id
                    menu.display = False
                    self.app._suppress_menu = True
                    needs_input = any(
                        c == cmd and "<" in c
                        for c, _ in SLASH_COMMANDS
                    )
                    if needs_input:
                        base = cmd.split("<")[0].rstrip() + " "
                        self.load_text(base)
                        self.action_cursor_line_end()
                    else:
                        self.load_text(cmd)
                        self.post_message(self.Submitted(self))
                return
            if event.key == "escape":
                event.stop()
                event.prevent_default()
                menu.display = False
                return

        if event.key == "shift+enter":
            event.stop()
            event.prevent_default()
            self.insert("\n")
            return
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self.post_message(self.Submitted(self))
            return
        if event.key == "ctrl+a":
            event.stop()
            event.prevent_default()
            self.action_select_all()
            return
        await super()._on_key(event)

    class Submitted(TextArea.Changed):
        """Posted when the user presses Enter to submit."""
        pass
