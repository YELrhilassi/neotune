import re

with open("src/ui/components/queue_panel.py", "r") as f:
    code = f.read()

new_action = """
    def action_play_track(self):
        track = self.get_highlighted_track()
        if not track or not track.get("uri"):
            return

        def _worker():
            # If it's the currently playing track, just seek to 0
            if track.get("name") and getattr(self, "track_data_map", None):
                # Find index of selected track
                try:
                    keys = list(self.track_data_map.keys())
                    selected_key = next(k for k, v in self.track_data_map.items() if v == track)
                    idx = keys.index(selected_key)
                except:
                    idx = -1
                
                if idx == 0:
                    # Seek to 0
                    try:
                        self.network.playback.sp.seek_track(0)
                        app_ref = self.app
                        if hasattr(app_ref, "update_now_playing"):
                            app_ref.call_from_thread(app_ref.update_now_playing, force=True)
                    except:
                        pass
                elif idx > 0:
                    # Skip to the track
                    import time
                    for _ in range(idx):
                        self.network.next_track()
                        time.sleep(0.3)  # Small delay to let API catch up
                    
                    app_ref = self.app
                    if hasattr(app_ref, "update_now_playing"):
                        app_ref.call_from_thread(app_ref.update_now_playing, force=True)
                else:
                    # Fallback
                    if play_track(track["uri"], self.app):
                        app_ref = self.app
                        if hasattr(app_ref, "update_now_playing"):
                            app_ref.call_from_thread(app_ref.update_now_playing, force=True)

        threading.Thread(target=_worker, daemon=True).start()
"""

code = re.sub(r'    def action_play_track\(self\):.*?        threading\.Thread\(target=_worker, daemon=True\)\.start\(\)', new_action, code, flags=re.DOTALL)

with open("src/ui/components/queue_panel.py", "w") as f:
    f.write(code)
