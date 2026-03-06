from textual.app import ComposeResult
from textual.widgets import Label, OptionList
from textual.containers import Middle
from src.ui.modals.base import BaseModal

class ThemeSelector(BaseModal[str]):
    def __init__(self, current_theme):
        super().__init__()
        self.current_theme = current_theme
        self.themes = [
            "catppuccin",
            "nord",
            "dracula",
            "tokyo-night"
        ]

    def compose(self) -> ComposeResult:
        with Middle(id="theme-dialog"):
            yield Label("Select Theme", id="theme-title")
            options = []
            for t in self.themes:
                name = t
                if t == self.current_theme:
                    name = f"[*] {name}"
                else:
                    name = f"[ ] {name}"
                options.append(name)
            yield OptionList(*options, id="theme-list")

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted):
        # Live preview logic could go here by modifying app CSS variables or classes
        preview_theme = self.themes[event.option_index]
        # self.app.apply_theme(preview_theme)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        selected_theme = self.themes[event.option_index]
        self.dismiss(selected_theme)
