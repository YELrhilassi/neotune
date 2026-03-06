import spotipy
from spotipy.oauth2 import SpotifyOAuth
from src.config.client_config import ClientConfiguration

class SpotifyNetwork:
    _auth_manager = None # Keep auth_manager as a class-level variable to maintain token state

    def __init__(self, config: ClientConfiguration):
        self.config = config
        self.sp = None
        self.setup_auth()

    def setup_auth(self):
        if not self.config.is_valid():
            return
            
        scope = "user-read-playback-state,user-modify-playback-state,playlist-read-private,user-read-currently-playing,user-library-read,user-read-recently-played"
        if not SpotifyNetwork._auth_manager:
            SpotifyNetwork._auth_manager = SpotifyOAuth(
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                redirect_uri=self.config.redirect_uri,
                scope=scope,
                open_browser=False
            )
        # Don't initialize self.sp here with auth_manager yet
        # We will initialize it lazily in is_authenticated or complete_login
        if self.sp is None:
            token_info = SpotifyNetwork._auth_manager.get_cached_token()
            if token_info:
                self.sp = spotipy.Spotify(auth_manager=SpotifyNetwork._auth_manager)
            else:
                self.sp = spotipy.Spotify() # Unauthenticated instance

    def get_auth_url(self):
        if not SpotifyNetwork._auth_manager:
            self.setup_auth()
        return SpotifyNetwork._auth_manager.get_authorize_url()

    def complete_login(self, response_url: str):
        if not SpotifyNetwork._auth_manager:
            self.setup_auth()
        
        # Extract code from URL and get token
        code = SpotifyNetwork._auth_manager.parse_response_code(response_url)
        token = SpotifyNetwork._auth_manager.get_access_token(code, as_dict=False)
        if token:
            self.sp = spotipy.Spotify(auth_manager=SpotifyNetwork._auth_manager)
            return True
        return False

    def is_authenticated(self) -> bool:
        if not SpotifyNetwork._auth_manager:
            return False
        
        token_info = SpotifyNetwork._auth_manager.get_cached_token()
        if not token_info:
            return False
            
        # If token is expired, SpotifyOAuth usually refreshes it automatically if possible.
        # But we want to avoid any method that might trigger an interactive prompt.
        if SpotifyNetwork._auth_manager.is_token_expired(token_info):
            try:
                # Attempt silent refresh
                token_info = SpotifyNetwork._auth_manager.refresh_access_token(token_info['refresh_token'])
            except Exception:
                return False
                
        if not token_info:
            return False
            
        if not self.sp or not getattr(self.sp, 'auth_manager', None):
            self.sp = spotipy.Spotify(auth_manager=SpotifyNetwork._auth_manager)
            
        return True

    def reauthenticate(self):
        # Force a re-authentication by clearing the cached token
        SpotifyNetwork._auth_manager = None
        self.setup_auth()

    def get_playlists(self, limit=50):
        if not self.sp: return []
        results = self.sp.current_user_playlists(limit=limit)
        return results.get('items', [])

    def get_playlist_tracks(self, playlist_id, limit=50):
        if not self.sp: return []
        results = self.sp.playlist_items(playlist_id, limit=limit)
        return results.get('items', [])

    def get_album_tracks(self, album_id, limit=50):
        if not self.sp: return []
        try:
            results = self.sp.album_tracks(album_id, limit=limit)
            return results.get('items', [])
        except Exception:
            return []

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

    def search(self, query, qtype="track,playlist,album", limit=50):
        if not self.sp: return []
        try:
            results = self.sp.search(q=query, type=qtype, limit=limit)
            if not results:
                return []
                
            items = []
            if "track" in qtype and results.get('tracks'):
                for t in results.get('tracks', {}).get('items', []):
                    items.append({"_qtype": "track", "data": t})
            if "album" in qtype and results.get('albums'):
                for a in results.get('albums', {}).get('items', []):
                    items.append({"_qtype": "album", "data": a})
            if "playlist" in qtype and results.get('playlists'):
                for p in results.get('playlists', {}).get('items', []):
                    items.append({"_qtype": "playlist", "data": p})
            return items
        except Exception as e:
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

    def _get_fallback_device_id(self):
        devices = self.get_devices()
        if not devices or not devices.get('devices'):
            return None
        for d in devices['devices']:
            if d.get('name') == "Spotify TUI Player":
                return d.get('id')
        return devices['devices'][0].get('id')

    def play_track(self, track_uri, device_id=None):
        if not self.sp: return
        
        # Decide if we use 'uris' (for tracks) or 'context_uri' (for albums/playlists)
        params = {"device_id": device_id}
        if ":track:" in track_uri:
            params["uris"] = [track_uri]
        else:
            params["context_uri"] = track_uri

        try:
            self.sp.start_playback(**params)
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 404 and 'No active device' in str(e):
                dev_id = self._get_fallback_device_id()
                if dev_id:
                    params["device_id"] = dev_id
                    self.sp.start_playback(**params)
                    return
            raise e

    def transfer_playback(self, device_id, force_play=True):
        if not self.sp: return
        self.sp.transfer_playback(device_id=device_id, force_play=force_play)

    def toggle_play_pause(self):
        if not self.sp: return
        playback = self.get_current_playback()
        try:
            if playback and playback.get('is_playing'):
                self.sp.pause_playback()
                return False
            else:
                self.sp.start_playback()
                return True
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 404 and 'No active device' in str(e):
                dev_id = self._get_fallback_device_id()
                if dev_id:
                    self.sp.transfer_playback(device_id=dev_id, force_play=True)
                    return True
            raise e

    def toggle_shuffle(self):
        if not self.sp: return
        playback = self.get_current_playback()
        if playback:
            current_shuffle = playback.get('shuffle_state', False)
            try:
                self.sp.shuffle(state=not current_shuffle)
                return not current_shuffle
            except spotipy.exceptions.SpotifyException as e:
                if e.http_status == 404 and 'No active device' in str(e):
                    dev_id = self._get_fallback_device_id()
                    if dev_id:
                        self.sp.transfer_playback(device_id=dev_id, force_play=False)
                        self.sp.shuffle(state=not current_shuffle, device_id=dev_id)
                        return not current_shuffle
                raise e

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
            
            try:
                self.sp.repeat(state=states[next_idx])
                return states[next_idx]
            except spotipy.exceptions.SpotifyException as e:
                if e.http_status == 404 and 'No active device' in str(e):
                    dev_id = self._get_fallback_device_id()
                    if dev_id:
                        self.sp.transfer_playback(device_id=dev_id, force_play=False)
                        self.sp.repeat(state=states[next_idx], device_id=dev_id)
                        return states[next_idx]
                raise e

    def next_track(self):
        if not self.sp: return
        try:
            self.sp.next_track()
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 404 and 'No active device' in str(e):
                dev_id = self._get_fallback_device_id()
                if dev_id:
                    self.sp.transfer_playback(device_id=dev_id, force_play=True)
                    self.sp.next_track(device_id=dev_id)
                    return
            raise e

    def prev_track(self):
        if not self.sp: return
        try:
            self.sp.previous_track()
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 404 and 'No active device' in str(e):
                dev_id = self._get_fallback_device_id()
                if dev_id:
                    self.sp.transfer_playback(device_id=dev_id, force_play=True)
                    self.sp.previous_track(device_id=dev_id)
                    return
            raise e
