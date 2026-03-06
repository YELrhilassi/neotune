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
                
            # We removed the aggressive active device polling (is_device_lost check)
            # because transferring playback in the background randomly interrupts
            # continuous playback and causes the player to restart songs.
            
        except Exception:
            # Prevent background service from crashing the whole app
            pass
            
        # Standard polling interval
        await asyncio.sleep(20)
