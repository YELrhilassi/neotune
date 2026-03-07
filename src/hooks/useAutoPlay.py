from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.config.user_prefs import UserPreferences
from src.hooks.useGetActiveDevice import useGetActiveDevice
from src.state.store import Store

def useAutoPlay(app):
    """
    Triggers playback if auto_play is enabled in user preferences.
    """
    prefs = Container.resolve(UserPreferences)
    if not prefs.auto_play:
        return
        
    network = Container.resolve(SpotifyNetwork)
    store = Container.resolve(Store)
    try:
        playback = network.get_current_playback()
        # Only start if not already playing
        if not playback or not playback.get('is_playing'):
            # If we don't have an active context (Spotify returns empty session)
            # just toggling play won't work on a fresh daemon. We should auto-play
            # from their recently played or a saved playlist.
            
            target_device_id = useGetActiveDevice()
            
            try:
                network.toggle_play_pause()
                app.call_from_thread(app.notify, "Auto-playing...")
            except Exception as e:
                # If it failed due to no active device or no context, try playing recent context
                if "No active device" in str(e) or "404" in str(e) or "403" in str(e):
                    recent = store.get("recently_played")
                    if recent and len(recent) > 0:
                        first_track = recent[0]
                        track_uri = first_track.get('track', {}).get('uri')
                        context_uri = first_track.get('context', {}).get('uri') if first_track.get('context') else None
                        
                        if track_uri:
                            if context_uri:
                                network.play_track(track_uri, device_id=target_device_id, context_uri=context_uri)
                            else:
                                network.play_track([track_uri], device_id=target_device_id)
                            app.call_from_thread(app.notify, "Auto-playing recent track...")
    except Exception as e:
        pass
