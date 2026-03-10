"""Hook for ensuring an active playback device is selected."""

from src.core.di import Container
from src.network.playback_service import PlaybackService
from src.hooks.useSwitchToLocalPlayer import useSwitchToLocalPlayer
from src.config.user_prefs import UserPreferences


def useEnsureActiveDevice(app, silent=True):
    """
    Checks if a device is currently active.
    Uses the optimized PlaybackService to avoid request spam.
    """
    prefs = Container.resolve(UserPreferences)
    if not prefs.auto_select_device:
        return

    try:
        playback_svc = Container.resolve(PlaybackService)
        playback = playback_svc.get_current_playback()

        # Check if we have an active session on any device
        is_playing = bool(playback and playback.get("is_playing"))
        is_active = bool(playback and playback.get("device", {}).get("is_active"))

        if not is_active:
            if not silent:
                app.notify("Activating local player...", severity="information")
            useSwitchToLocalPlayer(app, force=is_playing)
    except Exception:
        pass
