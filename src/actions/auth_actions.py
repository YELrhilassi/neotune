"""Authentication-related actions."""

import shutil
from pathlib import Path
from typing import Any

from src.core.di import Container
from src.core.constants import Paths
from src.core.logging_config import get_logger
from src.core.debug_logger import DebugLogger
from src.network.local_player import LocalPlayer

logger = get_logger("auth_actions")


def logout(app: Any) -> None:
    """Perform full logout: stop player, clear caches, remove credentials.

    Args:
        app: Application instance with notify and exit methods
    """
    debug = DebugLogger()
    try:
        # Stop and cleanup local player
        player = Container.resolve(LocalPlayer)
        if player:
            player.stop()
            debug.info("AuthActions", "Stopped local player")
            logger.info("Stopped local player")

        # Clear librespot cache directory
        if Paths.CACHE_DIR.exists():
            shutil.rmtree(Paths.CACHE_DIR)
            debug.info("AuthActions", "Cleared librespot cache")
            logger.info("Cleared librespot cache")

        # Clear spotipy token cache
        token_cache = Path(".cache")
        if token_cache.exists():
            token_cache.unlink()
            debug.info("AuthActions", "Cleared token cache")
            logger.info("Cleared token cache")

        # Remove stored client credentials
        if Paths.CLIENT_CONFIG_FILE.exists():
            Paths.CLIENT_CONFIG_FILE.unlink()
            debug.info("AuthActions", "Cleared client config")
            logger.info("Cleared client config")

        app.notify(
            "Logged out successfully. Restart the app to re-configure.",
            severity="information",
        )

        # Exit the application
        app.exit()

    except Exception as e:
        logger.error(f"Logout failed: {e}")
        app.notify(f"Logout failed: {e}", severity="error")
