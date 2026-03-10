import time
from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.state.store import Store


def useSwitchToLocalPlayer(app, force=False):
    """
    Switches playback to the local "Spotify TUI Player".
    Includes a retry loop to wait for the daemon to register with Spotify.
    """
    network = Container.resolve(SpotifyNetwork)
    store = Container.resolve(Store)

    # Try up to 10 times with a small delay to quickly find and switch to the device
    for attempt in range(10):
        try:
            devices_data = network.get_devices()
            if not devices_data or not devices_data.get("devices"):
                time.sleep(0.5)  # Fast polling for daemon registration
                continue

            devices = devices_data["devices"]

            # If not forcing, only switch if there is NO active device at all
            is_any_active = any(d.get("is_active") for d in devices)
            if not force and is_any_active:
                return True

            target_device = None
            # Look for our specific TUI player
            for device in devices:
                if device["name"] == "Spotify TUI Player":
                    target_device = device
                    break

            # Fallback to first available if forced
            if not target_device and force and devices:
                target_device = devices[0]

            if target_device:
                store.set("preferred_device_id", target_device["id"])
                store.set("preferred_device_name", target_device["name"])

                # Only transfer playback if there is an actively playing session globally,
                # or if we are explicitly forced to. Transferring a "None" or dead session
                # causes librespot to enter an Invalid State and refuse subsequent play commands.
                playback = network.get_current_playback()
                is_playing = playback and playback.get("is_playing")

                if is_playing or force:
                    network.transfer_playback(target_device["id"], force_play=force)

                return True

        except Exception:
            pass

        time.sleep(0.5)  # Fast polling before next attempt

    return False
