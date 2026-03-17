import re

with open("src/ui/components/queue_panel.py", "r") as f:
    code = f.read()

new_code = """
                elif idx > 0:
                    # Skip to the track
                    import time
                    app_ref = self.app
                    if hasattr(app_ref, "notify"):
                        app_ref.call_from_thread(app_ref.notify, f"Skipping {idx} tracks...")
                    
                    for i in range(idx):
                        try:
                            self.network.next_track()
                            if i < idx - 1:
                                time.sleep(0.3)
                        except:
                            pass
                    
                    if hasattr(app_ref, "update_now_playing"):
                        time.sleep(0.5)
                        app_ref.call_from_thread(app_ref.update_now_playing, force=True)
"""

code = code.replace("""
                elif idx > 0:
                    # Skip to the track
                    import time
                    for _ in range(idx):
                        self.network.next_track()
                        time.sleep(0.3)  # Small delay to let API catch up
                    
                    app_ref = self.app
                    if hasattr(app_ref, "update_now_playing"):
                        app_ref.call_from_thread(app_ref.update_now_playing, force=True)
""", new_code)

with open("src/ui/components/queue_panel.py", "w") as f:
    f.write(code)
