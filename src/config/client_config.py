"""Client configuration management with secure credential storage."""

from pathlib import Path
from typing import Optional

import keyring

from src.core.constants import Paths, KeyringKeys, ServerSettings
from src.core.logging_config import get_logger

logger = get_logger("client_config")


class ClientConfiguration:
    """Manages client credentials using system keyring for security."""

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        """Initialize client configuration.

        Args:
            config_dir: Optional custom configuration directory path.
                       Defaults to ~/.config/spotify-tui
        """
        if config_dir is None:
            self.config_dir = Paths.CONFIG_DIR
        else:
            self.config_dir = Path(config_dir)

        self.config_path = self.config_dir / "client.yml"

        self.client_id: Optional[str] = None
        self.client_secret: Optional[str] = None
        self.redirect_uri: str = ServerSettings.DEFAULT_REDIRECT_URI

        self.load()

    def load(self) -> None:
        """Load credentials from system keyring."""
        try:
            self.client_id = keyring.get_password(
                KeyringKeys.SERVICE_NAME, KeyringKeys.CLIENT_ID_KEY
            )
            self.client_secret = keyring.get_password(
                KeyringKeys.SERVICE_NAME, KeyringKeys.CLIENT_SECRET_KEY
            )
            logger.debug("Loaded credentials from keyring")
        except Exception as e:
            logger.error(f"Failed to access keyring: {e}")

    def save(self) -> None:
        """Save credentials to system keyring."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        try:
            if self.client_id:
                keyring.set_password(
                    KeyringKeys.SERVICE_NAME,
                    KeyringKeys.CLIENT_ID_KEY,
                    self.client_id,
                )
            if self.client_secret:
                keyring.set_password(
                    KeyringKeys.SERVICE_NAME,
                    KeyringKeys.CLIENT_SECRET_KEY,
                    self.client_secret,
                )
            logger.info("Saved credentials to keyring")
        except Exception as e:
            logger.error(f"Failed to save to keyring: {e}")

    def is_valid(self) -> bool:
        """Check if configuration has valid credentials.

        Returns:
            True if both client_id and client_secret are set
        """
        return bool(self.client_id and self.client_secret)

    def clear(self) -> None:
        """Clear all stored credentials from keyring."""
        try:
            keyring.delete_password(KeyringKeys.SERVICE_NAME, KeyringKeys.CLIENT_ID_KEY)
            keyring.delete_password(KeyringKeys.SERVICE_NAME, KeyringKeys.CLIENT_SECRET_KEY)
            self.client_id = None
            self.client_secret = None
            logger.info("Cleared credentials from keyring")
        except Exception as e:
            logger.error(f"Failed to clear keyring: {e}")
