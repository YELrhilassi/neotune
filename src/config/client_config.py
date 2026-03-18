"""Client configuration management with secure credential storage."""

import os
import sys
from pathlib import Path
from typing import Optional

import yaml

from src.core.constants import Paths, KeyringKeys, ServerSettings
from src.core.logging_config import get_logger

logger = get_logger("client_config")


# Check if running from PyInstaller bundle
def is_bundled():
    """Check if running from PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


class ClientConfiguration:
    """Manages client credentials using system keyring or file-based storage."""

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        """Initialize client configuration.

        Args:
            config_dir: Optional custom configuration directory path.
            Defaults to ~/.config/neotune
        """
        if config_dir is None:
            self.config_dir = Paths.CONFIG_DIR
        else:
            self.config_dir = Path(config_dir)

        self.config_path = self.config_dir / "client.yml"
        self.credentials_path = self.config_dir / ".credentials.yml"

        self.client_id: Optional[str] = None
        self.client_secret: Optional[str] = None
        self.redirect_uri: str = ServerSettings.DEFAULT_REDIRECT_URI

        # Use file-based storage for bundled apps
        self.use_file_storage = is_bundled()

        self.load()

    def load(self) -> None:
        """Load credentials from keyring or file."""
        if self.use_file_storage:
            self._load_from_file()
        else:
            self._load_from_keyring()

    def _load_from_file(self) -> None:
        """Load credentials from file (for bundled apps)."""
        try:
            if self.credentials_path.exists():
                with open(self.credentials_path, "r") as f:
                    data = yaml.safe_load(f) or {}
                    self.client_id = data.get("client_id")
                    self.client_secret = data.get("client_secret")
                    self.redirect_uri = data.get(
                        "redirect_uri", ServerSettings.DEFAULT_REDIRECT_URI
                    )
                logger.debug("Loaded credentials from file")
        except Exception as e:
            logger.error(f"Failed to load credentials from file: {e}")

    def _load_from_keyring(self) -> None:
        """Load credentials from system keyring."""
        try:
            import keyring

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
        """Save credentials to keyring or file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if self.use_file_storage:
            self._save_to_file()
        else:
            self._save_to_keyring()

    def _save_to_file(self) -> None:
        """Save credentials to file (for bundled apps)."""
        try:
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
            }
            with open(self.credentials_path, "w") as f:
                yaml.dump(data, f)
            # Make file readable only by owner
            os.chmod(self.credentials_path, 0o600)
            logger.info("Saved credentials to file")
        except Exception as e:
            logger.error(f"Failed to save credentials to file: {e}")

    def _save_to_keyring(self) -> None:
        """Save credentials to system keyring."""
        try:
            import keyring

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
        """Clear all stored credentials."""
        if self.use_file_storage:
            self._clear_file()
        else:
            self._clear_keyring()

    def _clear_file(self) -> None:
        """Clear credentials from file."""
        try:
            if self.credentials_path.exists():
                self.credentials_path.unlink()
            self.client_id = None
            self.client_secret = None
            logger.info("Cleared credentials from file")
        except Exception as e:
            logger.error(f"Failed to clear credentials file: {e}")

    def _clear_keyring(self) -> None:
        """Clear credentials from keyring."""
        try:
            import keyring

            keyring.delete_password(KeyringKeys.SERVICE_NAME, KeyringKeys.CLIENT_ID_KEY)
            keyring.delete_password(KeyringKeys.SERVICE_NAME, KeyringKeys.CLIENT_SECRET_KEY)
            self.client_id = None
            self.client_secret = None
            logger.info("Cleared credentials from keyring")
        except Exception as e:
            logger.error(f"Failed to clear keyring: {e}")
