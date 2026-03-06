import os
import yaml
from pathlib import Path

class ClientConfiguration:
    def __init__(self, config_dir=None):
        if config_dir is None:
            self.config_dir = Path.home() / ".config" / "spotify-tui"
        else:
            self.config_dir = Path(config_dir)
            
        self.config_path = self.config_dir / "client.yml"
        
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = "http://127.0.0.1:8080"
        
        # spotifyd credentials
        self.username = None
        self.password = None
        
        self.load()

    def load(self):
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                data = yaml.safe_load(f)
                if data:
                    self.client_id = data.get("client_id")
                    self.client_secret = data.get("client_secret")
                    self.redirect_uri = data.get("redirect_uri", self.redirect_uri)
                    self.username = data.get("username")
                    self.password = data.get("password")
                    
    def save(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "username": self.username,
            "password": self.password
        }
        with open(self.config_path, "w") as f:
            yaml.dump(data, f)
        # Set permissions to 600
        self.config_path.chmod(0o600)

    def is_valid(self):
        return bool(self.client_id and self.client_secret)

    def has_spotifyd_creds(self):
        return bool(self.username and self.password)
