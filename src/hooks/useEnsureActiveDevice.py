from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.hooks.useSwitchToLocalPlayer import useSwitchToLocalPlayer

async def useEnsureActiveDevice(app, silent=True):
    """
    Checks if a device is currently active. If not, it attempts to activate the TUI player.
    """
    try:
        network = Container.resolve(SpotifyNetwork)
        playback = network.get_current_playback()
        if not playback or not playback.get('device') or not playback['device'].get('is_active'):
            if not silent:
                app.notify("Activating playback device...", severity="information")
            await useSwitchToLocalPlayer(app, force=True)
    except Exception:
        pass
