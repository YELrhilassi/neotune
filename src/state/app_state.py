from src.network.spotify_network import SpotifyNetwork
from src.network.local_player import LocalPlayer
from src.config.client_config import ClientConfiguration
from src.config.user_prefs import UserPreferences

class ApplicationState:
    def __init__(self):
        self.local_player = LocalPlayer()
        self.client_config = ClientConfiguration()
        self.user_prefs = UserPreferences()
        
        # Start local player after loading preferences
        self.local_player.start(self.user_prefs.audio_config)
        
        try:
            self.network = SpotifyNetwork(self.client_config)
            self.is_authenticated = True
        except Exception as e:
            self.network = None
            self.is_authenticated = False
            self.auth_error = str(e)

        self.playlists = []
        self.featured_playlists = []
        self.recently_played = []
        
        self.current_tracks = []
        self.current_playback = None
        
        # Navigation History (rudimentary stack of views)
        self.navigation_history = ["library"]

    def refresh_playlists(self):
        if self.network:
            self.playlists = self.network.get_playlists()
            self.featured_playlists = self.network.get_featured_playlists()
            self.recently_played = self.network.get_recently_played()

    def refresh_playback(self):
        if self.network:
            self.current_playback = self.network.get_current_playback()

    def load_tracks(self, playlist_id):
        if self.network:
            self.current_tracks = self.network.get_playlist_tracks(playlist_id)
            self.navigation_history.append(f"playlist_{playlist_id}")

    def load_recent_tracks(self):
        self.current_tracks = self.recently_played
        self.navigation_history.append("recently_played")

    def search(self, query, qtype="track"):
        if self.network:
            return self.network.search(query, qtype)
        return []

    def go_back(self):
        if len(self.navigation_history) > 1:
            self.navigation_history.pop()
