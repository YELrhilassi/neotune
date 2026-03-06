from src.core.di import Container
from src.state.store import Store
from src.config.client_config import ClientConfiguration
from src.config.user_prefs import UserPreferences
from src.network.spotify_network import SpotifyNetwork
from src.network.local_player import LocalPlayer
from src.core.command_service import CommandService
from src.ui.terminal_renderer import TerminalRenderer

def setup_di():
    # Register core configurations
    Container.register(ClientConfiguration, ClientConfiguration, singleton=True)
    Container.register(UserPreferences, UserPreferences, singleton=True)
    
    # Register state store
    Container.register(Store, Store, singleton=True)
    
    # Resolve configs to inject into services if necessary, or let them resolve themselves
    client_config = Container.resolve(ClientConfiguration)
    
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
    player.start(prefs.audio_config)
    Container.register(LocalPlayer, lambda: player, singleton=True)
    
    Container.register(CommandService, CommandService, singleton=True)

if __name__ == "__main__":
    setup_di()
    app = TerminalRenderer()
    app.run()
