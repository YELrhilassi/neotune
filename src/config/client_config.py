import os
from pathlib import Path
import keyring

class ClientConfiguration:
    def __init__(self, config_dir=None):
        if config_dir is None:
            self.config_dir = Path.home() / ".config" / "spotify-tui"
        else:
            self.config_dir = Path(config_dir)
            
        self.config_path = self.config_dir / "client.yml" # Keeping for backwards compatibility if needed, but not used for secrets anymore
        
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = "http://127.0.0.1:8080"
        
        self.load()

    def load(self):
        try:
            self.client_id = keyring.get_password("spotify_tui", "client_id")
            self.client_secret = keyring.get_password("spotify_tui", "client_secret")
        except Exception as e:
            print(f"Failed to access keyring: {e}")

    def save(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        try:
            if self.client_id:
                keyring.set_password("spotify_tui", "client_id", self.client_id)
            if self.client_secret:
                keyring.set_password("spotify_tui", "client_secret", self.client_secret)
        except Exception as e:
            print(f"Failed to save to keyring: {e}")

    def is_valid(self):
        return bool(self.client_id and self.client_secret)
