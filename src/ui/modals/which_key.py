from textual.app import ComposeResult
from textual.widgets import Label
from textual.containers import Vertical, Horizontal, Grid
from textual import events
from textual.reactive import reactive

from src.ui.modals.base import BaseModal
from src.core.di import Container
from src.config.user_prefs import UserPreferences

class WhichKeyPopup(BaseModal):
    current_page = reactive(0)

    def __init__(self):
        super().__init__()
        self.prefs = Container.resolve(UserPreferences)
        
        # Gather all keys and build pages
        self.pages = self._build_pages()

    def _build_pages(self):
        all_keys = []
        
        # 1. Global
        all_keys.append(("Global", self.prefs.leader, "Leader Key"))
        all_keys.append(("Global", "tab", "Focus Next"))
        all_keys.append(("Global", "enter", "Select"))
        all_keys.append(("Global", "esc", "Cancel/Close"))
        
        # 2. Navigation
        nav = self.prefs.nav_bindings
        for name, key in nav.items():
            all_keys.append(("Navigation", key, f"Nav {name.replace('_', ' ').title()}"))
            
        # 3. Leader Actions
        kb = self.prefs.keybindings or {}
        for key, val in kb.items():
            all_keys.append(("Leader Actions", key, val['desc']))

        # 4. Telescope (if active)
        if any(type(s).__name__ == "TelescopePrompt" for s in self.app.screen_stack):
            all_keys.append(("Telescope", "H", "Prev Category"))
            all_keys.append(("Telescope", "L", "Next Category"))
            all_keys.append(("Telescope", "h", "Panel Left / Search"))
            all_keys.append(("Telescope", "l", "Panel Right / Preview"))
            all_keys.append(("Telescope", "j/k", "Navigate List"))
            all_keys.append(("Telescope", "U/D", "Page Up/Down"))
            
        # Group by category
        categories = {}
        for cat, key, desc in all_keys:
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((key, desc))
            
        # We can just put 12 items max per page, arranged nicely.
        ITEMS_PER_PAGE = 12
        pages = []
        current_page_items = []
        
        # Flatten by category
        for cat, items in categories.items():
            for key, desc in items:
                current_page_items.append((cat, key, desc))
                if len(current_page_items) >= ITEMS_PER_PAGE:
                    pages.append(current_page_items)
                    current_page_items = []
                    
        if current_page_items:
            pages.append(current_page_items)
            
        return pages if pages else [[]]

    def compose(self) -> ComposeResult:
        with Vertical(id="which-key-dialog"):
            yield Label("[bold #89b4fa]Which Key?[/]", id="which-key-title")
            with Vertical(id="which-key-content"):
                yield Label("Loading...", id="which-key-page-content")
            yield Label(self._get_page_indicator(), id="which-key-footer")

    def _get_page_indicator(self) -> str:
        total = len(self.pages)
        if total <= 1:
            return "[dim]esc to close[/dim]"
        return f"[dim]Page {self.current_page + 1}/{total} • ◀/▶ to paginate • esc to close[/dim]"

    def watch_current_page(self, new_page: int):
        self.update_content()

    def update_content(self):
        try:
            content_label = self.query_one("#which-key-page-content", Label)
            footer_label = self.query_one("#which-key-footer", Label)
        except Exception:
            return
            
        items = self.pages[self.current_page]
        
        # Group current page items by category for display
        display_cats = {}
        for cat, k, d in items:
            if cat not in display_cats:
                display_cats[cat] = []
            display_cats[cat].append((k, d))
            
        text = ""
        for cat, cat_items in display_cats.items():
            text += f"[bold #f38ba8]{cat}[/]\n"
            for k, d in cat_items:
                # Format key and description
                text += f"  [bold #a6e3a1]{str(k):<8}[/] [dim]→[/] [#cdd6f4]{d}[/]\n"
            text += "\n"
            
        content_label.update(text.strip())
        footer_label.update(self._get_page_indicator())

    def on_mount(self):
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
