from src.core.di import Container
from src.state.store import Store
from src.network.spotify_network import SpotifyNetwork


def useGetActiveDevice():
    """
    Returns the ID of the currently active or preferred device.
    """
    store = Container.resolve(Store)
    network = Container.resolve(SpotifyNetwork)

    try:
        devices_data = network.get_devices()
    except Exception:
        return None

    if not devices_data or not devices_data.get("devices"):
        return None

    devices = devices_data["devices"]
    target_device_id = store.get("preferred_device_id")

    # Validate the preferred device is still online
    if target_device_id:
        if not any(d.get("id") == target_device_id for d in devices):
            target_device_id = None

    # If no preferred ID, look for the TUI Player
    if not target_device_id:
        for device in devices:
            if device["name"] == "NeoTune Player":
                target_device_id = device["id"]
                store.set("preferred_device_id", target_device_id)
                break

    # If still none, find any active device
    if not target_device_id:
        for device in devices:
            if device["is_active"]:
                target_device_id = device["id"]
                break

    # Fallback to the first available device
    if not target_device_id and devices:
        target_device_id = devices[0]["id"]

    return target_device_id
