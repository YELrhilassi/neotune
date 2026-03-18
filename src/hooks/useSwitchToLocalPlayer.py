"""Hook for switching playback to the local player."""

import time
from src.core.di import Container
from src.network.playback_service import PlaybackService
from src.state.store import Store


def useSwitchToLocalPlayer(app, force=False):
    """
    Switches playback to the local "NeoTune Player".
    Uses optimized service calls to prevent network spam.
    """
    try:
        playback_svc = Container.resolve(PlaybackService)
        store = Container.resolve(Store)

        # Try multiple times to find the local player (daemons take time to register)
        # First few attempts: quick checks
        for attempt in range(3):
            devices = playback_svc.get_devices(force=True)  # Force refresh
            if not devices:
                if attempt < 2:
                    time.sleep(0.5)
                continue

            # Check if anything is already active
            is_any_active = any(d.get("is_active") for d in devices)
            if not force and is_any_active:
                return True

            target_device = next((d for d in devices if d["name"] == "NeoTune Player"), None)

            if target_device:
                dev_id = target_device["id"]
                store.set("preferred_device_id", dev_id)
                store.set("preferred_device_name", target_device["name"])

                # Check current state (internally cached)
                playback = playback_svc.get_current_playback()
                is_playing = bool(playback and playback.get("is_playing"))

                if is_playing or force:
                    playback_svc.transfer(dev_id, force_play=force)

                return True

        # Extended wait for slow device registration
        for attempt in range(10):
            time.sleep(1.0)
            devices = playback_svc.get_devices(force=True)

            if not devices:
                continue

            target_device = next((d for d in devices if d["name"] == "NeoTune Player"), None)

            if target_device:
                dev_id = target_device["id"]
                store.set("preferred_device_id", dev_id)
                store.set("preferred_device_name", target_device["name"])

                if force:
                    playback_svc.transfer(dev_id, force_play=True)

                return True

    except Exception as e:
        import logging

        logging.getLogger("neotune").error(f"Error switching to local player: {e}")

    return False
