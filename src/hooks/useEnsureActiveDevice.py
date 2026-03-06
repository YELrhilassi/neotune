from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.hooks.useSwitchToLocalPlayer import useSwitchToLocalPlayer

def useEnsureActiveDevice(app):
    """
    Checks if a device is currently active. If not, it activates the first available device.
    """
    try:
        network = Container.resolve(SpotifyNetwork)
        playback = network.get_current_playback()
        if not playback or not playback.get('device'):
            app.notify("No active device found. Activating TUI player...", severity="information")
            useSwitchToLocalPlayer(app, force=True)
    except Exception:
        # This can fail if auth is expired, which is handled elsewhere.
        pass
