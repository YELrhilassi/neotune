import re

with open("src/ui/components/queue_panel.py", "r") as f:
    code = f.read()

mount_replacement = """
    def on_mount(self):
        self.add_columns(f"{Icons.TRACK} Track", f"{Icons.ARTIST} Artist", f"{Icons.DURATION} Duration")
        self.cursor_type = "row"
        self.show_header = True

        self.store.subscribe("queue", lambda val, **kw: self.safe_load_queue(val))

    def _update_dynamic_column_widths(self):
        if not self.columns:
            return
        cols = list(self.columns.values())
        if len(cols) == 3:
            total_w = max(10, self.size.width - 2)
            cols[2].auto_width = False
            cols[2].width = max(8, cols[2].content_width)
            
            remaining = max(5, total_w - cols[2].width - 4)
            c0_w = max(len("Track") + 2, cols[0].content_width)
            c1_w = max(len("Artist") + 2, cols[1].content_width)
            sum_c = c0_w + c1_w
            
            if sum_c > 0:
                cols[0].width = max(len("Track") + 2, int(remaining * (c0_w / sum_c)))
                cols[1].width = remaining - cols[0].width
                
            for c in cols[:2]:
                c.auto_width = False
                
            self.refresh()
"""

code = re.sub(r'    def on_mount\(self\):.*?    def on_resize\(self, event: events\.Resize\):', mount_replacement + '\n    def on_resize(self, event: events.Resize):', code, flags=re.DOTALL)

with open("src/ui/components/queue_panel.py", "w") as f:
    f.write(code)
