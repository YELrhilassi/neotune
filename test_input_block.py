import os, sys
sys.path.insert(0, os.getcwd())
import asyncio
from textual.app import App, ComposeResult
from src.ui.modals.telescope.header import TelescopeInput

class TestApp(App):
    def compose(self) -> ComposeResult:
        yield TelescopeInput(id="test-input")

    def on_mount(self):
        self.query_one("#test-input").focus()

async def run_test():
    app = TestApp()
    async with app.run_test() as pilot:
        await pilot.press("x")
        await pilot.pause(0.1)
        val = app.query_one("#test-input").value
        print(f"Value after pressing 'x' in NORMAL: '{val}'")
        
        await pilot.press("i")
        await pilot.press("y")
        await pilot.pause(0.1)
        val = app.query_one("#test-input").value
        print(f"Value after 'i' then 'y': '{val}'")

asyncio.run(run_test())
