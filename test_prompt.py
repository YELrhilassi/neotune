import os, sys
sys.path.insert(0, os.getcwd())
import asyncio
from textual.app import App
from src.ui.modals.telescope import TelescopePrompt
from src.core.di import Container
from src.config.user_prefs import UserPreferences

class TestApp(App):
    CSS_PATH = "styles/main.tcss"
    def on_mount(self):
        Container.register(UserPreferences, UserPreferences, singleton=True)
        from src.network.spotify_network import SpotifyNetwork
        from src.core.command_service import CommandService
        from src.state.store import Store
        Container.register(Store, Store, singleton=True)
        
        class MockNetwork:
            def search(self, query, type_str):
                return [{"_qtype": "track", "data": {"name": "Test Track", "artists": [{"name": "Test Artist"}], "album": {"name": "Test Album"}, "duration_ms": 120000}}]
        
        Container.register(SpotifyNetwork, MockNetwork, singleton=True)
        Container.register(CommandService, CommandService, singleton=True)
        self.push_screen(TelescopePrompt(initial_query=":"))

async def run_test():
    app = TestApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.5)
        
        # Verify initial query is set
        input_w = pilot.app.screen.query_one("#telescope-input")
        print(f"Input value: '{input_w.value}'")
        
        # Let's hit backspace and type "test" to see search working
        await pilot.press("backspace", "t", "e", "s", "t")
        await pilot.pause(1.0)
        
        opt_list = pilot.app.screen.query_one("#telescope-results")
        print(f"Options after search: {opt_list.option_count}")

asyncio.run(run_test())
