import asyncio
from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.network.local_player import LocalPlayer
from src.hooks.useEnsureActiveDevice import useEnsureActiveDevice

async def useDaemonService(app):
    """
    Background service that monitors the local playback daemon and 
    Spotify connectivity.
    """
    player = Container.resolve(LocalPlayer)
    network = Container.resolve(SpotifyNetwork)
    
    while True:
        try:
            # 1. Ensure daemon process is still alive and only ONE instance exists
            if player and not player.is_running():
                # Clean up any zombies before restart
                player.stop_existing()
                player.restart()
                await asyncio.sleep(3)
                
            # 2. Check Spotify connectivity
            playback = network.get_current_playback()
            # If no device is active, try to force-activate the local player
            is_device_lost = not playback or not playback.get('device') or not playback['device'].get('is_active')
            
            if is_device_lost:
                # Silently wake up the device
                # This ensures the daemon registers as 'Active' even if paused
                await useEnsureActiveDevice(app, silent=True)
                # Check again soon
                await asyncio.sleep(10)
                continue
                
        except Exception:
            # Prevent background service from crashing the whole app
            pass
            
        # Standard polling interval
        await asyncio.sleep(20)
