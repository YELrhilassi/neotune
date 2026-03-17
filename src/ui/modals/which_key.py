from textual.app import ComposeResult
from textual.widgets import Label, Static
from textual.containers import Vertical, Horizontal, Grid
from textual import events
from textual.reactive import reactive
from textual.binding import Binding

from src.ui.modals.base import BaseModal
from src.core.di import Container
from src.config.user_prefs import UserPreferences


class WhichKeyPopup(BaseModal):
    current_page = reactive(0)

    BINDINGS = [
        Binding("left", "previous_page", "Previous Page", show=False),
        Binding("right", "next_page", "Next Page", show=False),
        Binding("escape", "close", "Close", show=False),
        Binding("q", "close", "Close", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.prefs = Container.resolve(UserPreferences)
        self.pages = self._build_pages()

    def _build_pages(self):
        """Build categorized keybinding pages."""
        pages = []

        # Page 1: Global & Navigation
        page1 = {
            "Global": [
                (self.prefs.leader or "space", "Leader Key"),
                ("tab", "Focus Next"),
                ("shift+tab", "Focus Previous"),
                ("enter", "Select/Play"),
                ("esc", "Cancel/Close"),
                ("ctrl+c", "Quit App"),
            ],
            "Navigation": [
                ("h / ←", "Move Left"),
                ("j / ↓", "Move Down"),
                ("k / ↑", "Move Up"),
                ("l / →", "Move Right"),
                ("g+g", "Go to Top"),
                ("G", "Go to Bottom"),
                ("page_up", "Page Up"),
                ("page_down", "Page Down"),
            ],
        }
        pages.append(page1)

        # Page 2: Playback Controls
        page2 = {
            "Playback": [
                ("p", "Play/Pause"),
                ("n", "Next Track"),
                ("b", "Previous Track"),
                ("s", "Toggle Shuffle"),
                ("r", "Cycle Repeat"),
                ("l", "Like/Unlike Track"),
                ("a", "Add to Queue"),
                ("x / del", "Remove from Queue (in Up Next)"),
            ],
            "Volume": [
                ("+", "Volume Up"),
                ("-", "Volume Down"),
                ("m", "Mute/Unmute"),
            ],
            "Now Playing (when focused)": [
                ("space", "Play/Pause"),
                ("n", "Next Track"),
                ("p", "Previous Track"),
                ("s", "Toggle Shuffle"),
                ("r", "Cycle Repeat"),
                ("l", "Like Track"),
            ],
        }
        pages.append(page2)

        # Page 3: Search & Discovery
        page3 = {
            "Search": [
                ("/", "Search Tracks/Playlists"),
                ("s", "Fuzzy Search"),
                (":", "Command Prompt"),
            ],
            "Discovery": [
                ("R", "Start Track Radio"),
                ("o", "Select Output Device"),
                ("a", "Select Audio Backend"),
            ],
            "System": [
                ("ctrl+l", "Show Debug Logs"),
                ("?", "Show Which Key"),
            ],
        }
        pages.append(page3)

        return pages

    def compose(self) -> ComposeResult:
        with Vertical(id="which-key-dialog"):
            yield Static("Loading...", id="which-key-page-content")

    def _get_page_indicator(self) -> str:
        total = len(self.pages)
        if total <= 1:
            return "Which Key?"
        return f"Page {self.current_page + 1}/{total} • ◀/▶ to paginate • esc/q to close"

    def watch_current_page(self, new_page: int):
        self.update_content()

    def _render_category(self, category: str, items: list, color: str) -> str:
        """Render a category section with colored header."""
        lines = [f"[{color} bold]{category}[/]"]
        lines.append(f"[{color}]─" + "─" * len(category) + "─[/]")

        for key, desc in items:
            key_display = str(key).upper()
            lines.append(f" [bold]{key_display:<12}[/] {desc}")

        return "\n".join(lines)

    def update_content(self):
        try:
            content_label = self.query_one("#which-key-page-content", Static)
            dialog = self.query_one("#which-key-dialog", Vertical)
        except Exception:
            return

        page_data = self.pages[self.current_page]

        # Collect all category renderings
        sections = []
        for category, items in page_data.items():
            color_map = {
                "Global": "#f38ba8",
                "Navigation": "#89b4fa",
                "Playback": "#a6e3a1",
                "Volume": "#fab387",
                "Now Playing (when focused)": "#cba6f7",
                "Search": "#94e2d5",
                "Discovery": "#b4befe",
                "System": "#cdd6f4",
            }
            color = color_map.get(category, "#cdd6f4")
            sections.append(self._render_category(category, items, color))

        content = "\n\n".join(sections)
        content_label.update(content)

    def on_mount(self):
        dialog = self.query_one("#which-key-dialog", Vertical)
        dialog.border_title = "Which Key?"
        dialog.border_subtitle = self._get_page_indicator()
        self.update_content()

    def action_previous_page(self):
        if self.current_page > 0:
            self.current_page -= 1
        else:
            self.current_page = len(self.pages) - 1

    def action_next_page(self):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
        else:
            self.current_page = 0

    def action_close(self):
        """Close the modal without error if already dismissed."""
        try:
            if self.app and self in self.app._screen_stack:
                self.dismiss()
        except:
            pass

    def on_key(self, event) -> None:
        """Handle key events for pagination."""
        key = event.key
        char = event.character or ""

        if key == "left":
            self.action_previous_page()
            event.stop()
        elif key == "right":
            self.action_next_page()
            event.stop()
        elif char.lower() == "q":
            self.action_close()
            event.stop()
        elif key == "escape":
            self.action_close()
            event.stop()
