import re

with open("src/hooks/useUpdateNowPlaying.py", "r") as f:
    code = f.read()

# We want to check virtual queue inside useUpdateNowPlaying
injection = """
        # --- VIRTUAL QUEUE AUTO-SKIP CHECK ---
        if playback and playback.get("is_playing"):
            item = playback.get("item")
            if item:
                uri = item.get("uri")
                from src.state.virtual_queue import VirtualQueueManager
                vq = VirtualQueueManager()
                if uri and vq.is_skipped(uri):
                    # We are currently playing a track marked as skipped!
                    network.next_track()
                    # We unmark it so it doesn't get skipped if we try to play it manually again later?
                    # No, user wants it out of the queue. If it plays again later, it will be skipped again unless removed from skipped list.
                    # Wait, if we keep it in skipped list FOREVER, we can never play the track again.
                    # The skipped_uris is essentially a "Do Not Play" list.
                    # That is a bit aggressive. Maybe we should remove it from skipped list after we skip it?
                    # "skip when reached" -> usually means we discard it. Let's unmark it so they can play it later.
                    vq.unmark_skipped(uri)
                    return # Stop here, we will update on next poll
        # -------------------------------------
"""

code = code.replace('store.set("current_playback", playback)', 'store.set("current_playback", playback)\n' + injection)

with open("src/hooks/useUpdateNowPlaying.py", "w") as f:
    f.write(code)
