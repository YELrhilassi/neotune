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
from src.ui.screens.login import LoginScreen
from src.ui.screens.player_auth import PlayerAuthScreen
from textual.app import App

def setup_config():
    """Register essential services that don't depend on Spotify Auth."""
    Container.register(ClientConfiguration, ClientConfiguration, singleton=True)
    Container.register(UserPreferences, UserPreferences, singleton=True)
    Container.register(Store, Store, singleton=True)
    Container.register(CommandService, CommandService, singleton=True)

def setup_spotify():
    """Register Spotify-dependent services once config is valid."""
    client_config = Container.resolve(ClientConfiguration)
    if not client_config.is_valid():
        return False
        
    network = SpotifyNetwork(client_config)
    Container.register(SpotifyNetwork, lambda: network, singleton=True)
    
    if network.is_authenticated():
        # Register Local Player but don't start yet, check auth first
        player = LocalPlayer()
        Container.register(LocalPlayer, lambda: player, singleton=True)
        return True
    return False

class WizardApp(App):
    """Temporary app for setup and login flows."""
    CSS_PATH = [
        "styles/_variables.tcss",
        "styles/_base.tcss",
        "styles/_status_bar.tcss",
        "styles/_now_playing.tcss",
        "styles/_main_view.tcss",
        "styles/_modals.tcss",
        "styles/_telescope.tcss",
        "styles/_onboarding.tcss",
    ]
    def __init__(self, start_screen):
        super().__init__()
        self.start_screen = start_screen
        
    def on_mount(self):
        self.push_screen(self.start_screen)

if __name__ == "__main__":
    setup_config()
    client_config = Container.resolve(ClientConfiguration)
    
    # 1. Check if Client ID/Secret are configured
    if not client_config.is_valid():
        wizard = WizardApp(SetupScreen())
        result = wizard.run()
        if result == "setup_complete":
            client_config.load()
        else:
            sys.exit(0)
            
    # 2. Check if Web API Authenticated
    if not setup_spotify():
        wizard = WizardApp(LoginScreen())
        result = wizard.run()
        if result == "login_complete":
            setup_spotify()
        else:
            sys.exit(0)
            
    # 3. Check if Local Player (spotifyd) Authenticated
    player = Container.resolve(LocalPlayer)
    if player and not player.is_authenticated():
        wizard = WizardApp(PlayerAuthScreen())
        result = wizard.run()
        if result != "player_auth_complete":
            # Optional: Allow continuing without local player if user cancels?
            # For now, we enforce it for high-quality playback.
            pass

    # 4. Start Local Player if authenticated
    if player and player.is_authenticated():
        prefs = Container.resolve(UserPreferences)
        player.start(audio_config=prefs.audio_config)

    # 5. Launch main TUI
    app = TerminalRenderer()
    app.run()
