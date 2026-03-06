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
        # Sort navigation keys logically
        nav_order = ["up", "down", "left", "right", "page_up", "page_down"]
        for name in nav_order:
            if name in nav:
                key = nav[name]
                all_keys.append(("Navigation", key, f"Nav {name.replace('_', ' ').title()}"))
            
        # 3. Leader Actions
        kb = self.prefs.keybindings or {}
        # Sort leader actions by description for better organization
        sorted_kb = sorted(kb.items(), key=lambda x: x[1]['desc'])
        for key, val in sorted_kb:
            all_keys.append(("Leader Actions", key, val['desc']))

        # 4. Telescope (if active)
        if any(type(s).__name__ == "TelescopePrompt" for s in self.app.screen_stack):
            all_keys.append(("Telescope", "H/L", "Tabs Switch"))
            all_keys.append(("Telescope", "i/a", "Insert Mode"))
            all_keys.append(("Telescope", "h/l", "Switch Panels"))
            all_keys.append(("Telescope", "j/k", "Navigate List"))
            all_keys.append(("Telescope", "esc", "Normal Mode"))
            
        # Group by category in a specific order
        category_order = ["Global", "Navigation", "Leader Actions", "Telescope"]
        
        categories = {cat: [] for cat in category_order}
        for cat, key, desc in all_keys:
            if cat in categories:
                categories[cat].append((key, desc))
            
        # Let's chunk categories or items into pages.
        ITEMS_PER_PAGE = 30
        pages = []
        current_page_items = []
        
        for cat in category_order:
            items = categories[cat]
            if not items: continue
            
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
            with Vertical(id="which-key-content"):
                yield Label("Loading...", id="which-key-page-content")

    def _get_page_indicator(self) -> str:
        total = len(self.pages)
        if total <= 1:
            return "esc to close"
        return f"Page {self.current_page + 1}/{total} • ◀/▶ to paginate • esc to close"

    def watch_current_page(self, new_page: int):
        self.update_content()

    def update_content(self):
        try:
            content_label = self.query_one("#which-key-page-content", Label)
            dialog = self.query_one("#which-key-dialog")
        except Exception:
            return
            
        items = self.pages[self.current_page]
        
        import math
        
        num_cols = 2
        num_rows = math.ceil(len(items) / num_cols)
        
        lines = []
        for r in range(num_rows):
            col1_idx = r
            col2_idx = r + num_rows
            
            # Format column 1
            cat1, k1, d1 = items[col1_idx]
            c1_str = f"[bold #a6e3a1]{str(k1):<6}[/] [dim]→[/] [#cdd6f4]{str(d1):<24}[/]"
            
            # Format column 2 if it exists
            if col2_idx < len(items):
                cat2, k2, d2 = items[col2_idx]
                c2_str = f"[bold #a6e3a1]{str(k2):<6}[/] [dim]→[/] [#cdd6f4]{str(d2)}[/]"
                lines.append(c1_str + c2_str)
            else:
                lines.append(c1_str)
            
        content_label.update("\n".join(lines))
        dialog.border_subtitle = self._get_page_indicator()

    def on_mount(self):
        try:
            dialog = self.query_one("#which-key-dialog")
            dialog.border_title = "Which Key?"
        except Exception:
            pass
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
