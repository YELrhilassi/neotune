import re

with open("src/ui/components/queue_panel.py", "r") as f:
    code = f.read()

def repl(match):
    return """        # 1. Currently Playing
        currently_playing = filtered_queue.get("currently_playing")
        if currently_playing and currently_playing.get("name"):
            uri = currently_playing.get("uri", "")
            unique_key = f"{uri}_{uuid.uuid4().hex[:8]}"
            self.track_data_map[unique_key] = currently_playing

            track_name = strip_icons(currently_playing.get("name", ""))
            artists_list = currently_playing.get("artists", [])
            artists = ", ".join([strip_icons(a.get("name", "")) for a in artists_list])
            duration_ms = currently_playing.get("duration_ms", 0)
            duration_str = f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}"

            col1 = f"[bold #a6e3a1]{Icons.PLAY} {track_name}[/]"
            col2 = f"[bold #a6e3a1]{artists}[/]"
            col3 = f"[bold #a6e3a1]{duration_str}[/]"
            self.add_row(col1, col2, col3, key=unique_key)

        # 2. Up Next
        for track in filtered_queue.get("queue", []):
            if not track or not track.get("name"):
                continue

            uri = track.get("uri", "")
            unique_key = f"{uri}_{uuid.uuid4().hex[:8]}"
            self.track_data_map[unique_key] = track

            track_name = strip_icons(track.get("name", ""))
            artists_list = track.get("artists", [])
            artists = ", ".join([strip_icons(a.get("name", "")) for a in artists_list])
            duration_ms = track.get("duration_ms", 0)
            duration_str = f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}"

            self.add_row(track_name, f"[dim]{artists}[/]", duration_str, key=unique_key)

        if saved_row is not None and len(self.track_data_map) > 0:"""

code = re.sub(r'        # 1\. Currently Playing.*?        if saved_row is not None and len\(self\.track_data_map\) > 0:', repl, code, flags=re.DOTALL)

with open("src/ui/components/queue_panel.py", "w") as f:
    f.write(code)
