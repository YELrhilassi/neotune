from textual.app import ComposeResult
from textual.widgets import Input, OptionList
from textual.containers import Vertical
from src.ui.modals.base import BaseModal
from src.core.di import Container
from src.config.user_prefs import UserPreferences
from src.core.command_service import CommandService
from textual import events

class CommandPrompt(BaseModal[str]):
    def on_mount(self):
        self.user_prefs = Container.resolve(UserPreferences)
        self.command_service = Container.resolve(CommandService)
        self.input = self.query_one("#command-input", Input)
        self.results = self.query_one("#command-results", OptionList)
        self.input.focus()
        self.matched_commands = []
        self.update_matches("")

    def compose(self) -> ComposeResult:
        with Vertical(id="command-prompt-container"):
            yield Input(placeholder=":", id="command-input")
            yield OptionList(id="command-results")

    def on_input_changed(self, event: Input.Changed):
        self.update_matches(event.value)

    def update_matches(self, query: str):
        commands = self.user_prefs.commands
        self.results.clear_options()
        self.matched_commands = []
        
        if query:
            matched = [k for k in commands if k.startswith(query)]
        else:
            matched = list(commands.keys())
            
        for m in matched:
            cmd = commands[m]
            self.matched_commands.append({"action": cmd["action"], "alias": m, "desc": cmd["desc"]})
            self.results.add_option(f"{m} - [dim]{cmd['desc']}[/dim]")

    def on_key(self, event: events.Key):
        if event.key == "escape":
            self.dismiss()
            return

        if event.key in ["down", "tab"]:
            self.results.action_cursor_down()
            event.prevent_default()
        elif event.key in ["up", "shift+tab"]:
            self.results.action_cursor_up()
            event.prevent_default()
        elif event.key == "enter":
            if self.matched_commands and self.results.highlighted is not None:
                item = self.matched_commands[self.results.highlighted]
                self.dismiss()
                self.command_service.execute(item["action"], self.app)
            event.prevent_default()
        else:
            super().on_key(event)
