import asyncio

async def useDaemonService(app):
    """
    Background service temporarily disabled.
    The previous logic was repeatedly killing and restarting the daemon
    because process.poll() was returning a false negative, which caused
    the music to stop continuously while the TUI was running.
    """
    while True:
        await asyncio.sleep(60)
