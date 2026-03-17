import re

with open("src/hooks/track_actions.py", "r") as f:
    code = f.read()

injection = """
        if app and hasattr(app, "notify"):
            app.call_from_thread(app.notify, "Added to queue")
            
        # Refresh queue if visible
        store = Store()
        if store.get("queue_visible"):
            def _refresh_q():
                q = network.get_queue()
                store.set("queue", q)
            import threading
            threading.Thread(target=_refresh_q, daemon=True).start()
"""

code = code.replace("""
        if app and hasattr(app, "notify"):
            app.call_from_thread(app.notify, "Added to queue")
""", injection)

with open("src/hooks/track_actions.py", "w") as f:
    f.write(code)
