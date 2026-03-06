import os
import yaml
from dotenv import load_dotenv

load_dotenv()

class ClientConfiguration:
    def __init__(self, config_path="client.yml"):
        self.config_path = config_path
        self.client_id = os.getenv("SPOTIPY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
        self.redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8080")
        self.load_from_yaml()

    def load_from_yaml(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                data = yaml.safe_load(f)
                if data:
                    self.client_id = data.get("client_id", self.client_id)
                    self.client_secret = data.get("client_secret", self.client_secret)
                    self.redirect_uri = data.get("redirect_uri", self.redirect_uri)
                    
    def is_valid(self):
        return bool(self.client_id and self.client_secret)
