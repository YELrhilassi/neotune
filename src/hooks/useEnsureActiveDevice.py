from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.hooks.useSwitchToLocalPlayer import useSwitchToLocalPlayer
from src.config.user_prefs import UserPreferences


def useEnsureActiveDevice(app, silent=True):
    """
    Checks if a device is currently active. If not, it attempts to set the preferred device
    but avoids violently transferring playback if there is no active session.
    """
    prefs = Container.resolve(UserPreferences)
    if not prefs.auto_select_device:
        return

    try:
        network = Container.resolve(SpotifyNetwork)
        playback = network.get_current_playback()

        # If there is no active device at all, we don't want to force a transfer_playback
        # because transferring an empty session causes the local player to crash into an Invalid State.
        # We only force=True if there IS an active session on a DIFFERENT device.
        is_playing = bool(playback and playback.get("is_playing"))

        if (
            not playback
            or not playback.get("device")
            or not playback["device"].get("is_active")
        ):
            if not silent:
                app.notify("Connecting to local player...", severity="information")
            useSwitchToLocalPlayer(app, force=is_playing)
    except Exception:
        pass
