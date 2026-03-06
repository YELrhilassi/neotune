import spotipy
from spotipy.oauth2 import SpotifyOAuth
from src.config.client_config import ClientConfiguration

class SpotifyNetwork:
    def __init__(self, config: ClientConfiguration):
        self.config = config
        self.sp = None
        self.authenticate()

    def authenticate(self):
        if not self.config.is_valid():
            raise Exception("Invalid client configuration. Check .env or client.yml")
            
        try:
            scope = "user-read-playback-state,user-modify-playback-state,playlist-read-private,user-read-currently-playing,user-library-read,user-read-recently-played"
            auth_manager = SpotifyOAuth(
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                redirect_uri=self.config.redirect_uri,
                scope=scope,
                open_browser=False
            )
            self.sp = spotipy.Spotify(auth_manager=auth_manager)
            self.sp.current_user() # Validate
        except Exception as e:
            self.sp = None
            raise Exception(f"Authentication failed: {e}")

    def get_playlists(self, limit=50):
        if not self.sp: return []
        results = self.sp.current_user_playlists(limit=limit)
        return results.get('items', [])

    def get_playlist_tracks(self, playlist_id, limit=50):
        if not self.sp: return []
        results = self.sp.playlist_items(playlist_id, limit=limit)
        return results.get('items', [])

    def get_featured_playlists(self, limit=20):
        if not self.sp: return []
        try:
            results = self.sp.featured_playlists(limit=limit)
            return results.get('playlists', {}).get('items', [])
        except Exception:
            return []

    def get_recently_played(self, limit=50):
        if not self.sp: return []
        try:
            results = self.sp.current_user_recently_played(limit=limit)
            return results.get('items', [])
        except Exception:
            return []

    def search(self, query, qtype="track", limit=50):
        if not self.sp: return []
        try:
            results = self.sp.search(q=query, type=qtype, limit=limit)
            if qtype == "track":
                return results.get('tracks', {}).get('items', [])
            elif qtype == "playlist":
                return results.get('playlists', {}).get('items', [])
            return []
        except Exception:
            return []

    def get_current_playback(self):
        if not self.sp: return None
        try:
            return self.sp.current_playback()
        except Exception:
            return None

    def get_devices(self):
        if not self.sp: return None
        return self.sp.devices()

    def play_track(self, track_uri, device_id=None):
        if not self.sp: return
        self.sp.start_playback(device_id=device_id, uris=[track_uri])

    def transfer_playback(self, device_id, force_play=True):
        if not self.sp: return
        self.sp.transfer_playback(device_id=device_id, force_play=force_play)

    def toggle_play_pause(self):
        if not self.sp: return
        playback = self.get_current_playback()
        if playback and playback.get('is_playing'):
            self.sp.pause_playback()
            return False
        else:
            self.sp.start_playback()
            return True

    def toggle_shuffle(self):
        if not self.sp: return
        playback = self.get_current_playback()
        if playback:
            current_shuffle = playback.get('shuffle_state', False)
            self.sp.shuffle(state=not current_shuffle)
            return not current_shuffle

    def cycle_repeat(self):
        if not self.sp: return
        playback = self.get_current_playback()
        if playback:
            states = ['off', 'context', 'track']
            current = playback.get('repeat_state', 'off')
            try:
                next_idx = (states.index(current) + 1) % len(states)
            except ValueError:
                next_idx = 0
            self.sp.repeat(state=states[next_idx])
            return states[next_idx]

    def next_track(self):
        if not self.sp: return
        self.sp.next_track()

    def prev_track(self):
        if not self.sp: return
        self.sp.previous_track()
