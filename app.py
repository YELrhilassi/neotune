import sys
from src.core.di import Container
from src.state.store import Store
from src.config.client_config import ClientConfiguration
from src.config.user_prefs import UserPreferences
from src.network.spotify_network import SpotifyNetwork
from src.network.local_player import LocalPlayer
from src.core.command_service import CommandService
from src.ui.terminal_renderer import TerminalRenderer
from src.ui.screens.setup import SetupScreen
from textual.app import App

def setup_di():
    # Register core configurations
    Container.register(ClientConfiguration, ClientConfiguration, singleton=True)
    Container.register(UserPreferences, UserPreferences, singleton=True)
    
    # Register state store
    Container.register(Store, Store, singleton=True)
    
    client_config = Container.resolve(ClientConfiguration)
    
    if client_config.is_valid():
        # Create network instance
        try:
            network = SpotifyNetwork(client_config)
            store = Container.resolve(Store)
            store.set("is_authenticated", True)
        except Exception as e:
            network = None
            store = Container.resolve(Store)
            store.set("is_authenticated", False)
            store.set("auth_error", str(e))
            
        Container.register(SpotifyNetwork, lambda: network, singleton=True)
        
        # Local Player
        player = LocalPlayer()
        prefs = Container.resolve(UserPreferences)
        player.start(
            audio_config=prefs.audio_config, 
            credentials={"username": client_config.username, "password": client_config.password}
        )
        Container.register(LocalPlayer, lambda: player, singleton=True)
    else:
        # Placeholder for DI if not valid yet
        Container.register(SpotifyNetwork, lambda: None, singleton=True)
        Container.register(LocalPlayer, lambda: None, singleton=True)
    
    Container.register(CommandService, CommandService, singleton=True)

class SetupApp(App):
    CSS_PATH = "styles/main.tcss"
    def on_mount(self):
        self.push_screen(SetupScreen())

if __name__ == "__main__":
    setup_di()
    
    client_config = Container.resolve(ClientConfiguration)
    if not client_config.is_valid():
        setup_app = SetupApp()
        result = setup_app.run()
        if result == "setup_complete":
            # Re-setup DI with new config
            setup_di()
            app = TerminalRenderer()
            app.run()
    else:
        app = TerminalRenderer()
        app.run()
