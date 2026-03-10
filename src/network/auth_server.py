from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn
import threading
import queue
import logging
from jinja2 import Template

# Disable uvicorn/fastapi spam
logging.getLogger("uvicorn.access").setLevel(logging.ERROR)
logging.getLogger("uvicorn.error").setLevel(logging.ERROR)

app = FastAPI()
auth_queue = queue.Queue()
# Use a shared dict for state that the server can access
server_state = {"auth_url": None}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Spotify TUI Setup</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #121212; color: #fff; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .card { background: #181818; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); width: 400px; text-align: center; }
        .spotify-green { color: #1DB956; }
        h1 { margin-top: 0; }
        input { width: 100%; padding: 10px; margin: 10px 0; border-radius: 4px; border: 1px solid #333; background: #282828; color: white; box-sizing: border-box; }
        button { background: #1DB956; color: white; border: none; padding: 12px 24px; border-radius: 50px; font-weight: bold; cursor: pointer; margin-top: 10px; width: 100%; }
        button:hover { background: #1ed760; transform: scale(1.02); }
        .help { font-size: 0.8rem; color: #b3b3b3; margin-top: 20px; }
        a { color: #1DB956; text-decoration: none; }
        .btn-secondary { background: #333; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="card">
        <h1 class="spotify-green">Spotify TUI</h1>
        
        {% if step == 'config' %}
        <p>Enter your Spotify Application credentials.</p>
        <form method="POST" action="/setup">
            <input type="text" name="client_id" placeholder="Spotify Client ID" required>
            <input type="password" name="client_secret" placeholder="Spotify Client Secret" required>
            <input type="text" name="redirect_uri" value="http://127.0.0.1:8080" required>
            <button type="submit">Save and Continue</button>
        </form>
        <div class="help">
            Find your credentials at <a href="https://developer.spotify.com/dashboard" target="_blank">Spotify Developer Dashboard</a>
        </div>
        {% elif step == 'authorize' %}
        <p>Credentials saved!</p>
        <h2 class="spotify-green">Step 2: Spotify Login</h2>
        <p>Click the button below to authorize this app with your Spotify account.</p>
        <button onclick="window.location.href='/authorize-link'">Authorize with Spotify</button>
        <button class="btn-secondary" onclick="window.location.href='/'">Edit Credentials</button>
        {% elif step == 'success' %}
        <h2 class="spotify-green">All Done!</h2>
        <p>Authentication successful. You can now close this tab and return to your terminal.</p>
        {% elif step == 'waiting' %}
        <h2 class="spotify-green">Waiting...</h2>
        <p>Please complete the authorization in the popup or check your terminal.</p>
        {% endif %}
    </div>
</body>
</html>
"""


def render_html(step):
    template = Template(HTML_TEMPLATE)
    return template.render(step=step)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if "code" in request.query_params or "error" in request.query_params:
        full_url = str(request.url)
        auth_queue.put({"type": "callback", "url": full_url})
        return HTMLResponse(render_html("success"))
    return render_html("config")


@app.post("/setup", response_class=HTMLResponse)
async def setup(
    client_id: str = Form(...),
    client_secret: str = Form(...),
    redirect_uri: str = Form(...),
):
    auth_queue.put(
        {
            "type": "config",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }
    )
    # Give the app a moment to generate the URL
    return render_html("authorize")


@app.get("/authorize-link")
async def authorize_link():
    if server_state["auth_url"]:
        return RedirectResponse(server_state["auth_url"])
    return HTMLResponse(
        "Authorization link not ready yet. Please wait a second and refresh."
    )


@app.get("/callback", response_class=HTMLResponse)
async def callback(request: Request):
    full_url = str(request.url)
    auth_queue.put({"type": "callback", "url": full_url})
    return HTMLResponse(render_html("success"))


class AuthServer:
    def __init__(self, port=8080):
        self.port = port
        self.thread = None

    def start(self):
        config = uvicorn.Config(
            app, host="127.0.0.1", port=self.port, log_level="error"
        )
        server = uvicorn.Server(config)
        self.thread = threading.Thread(target=server.run, daemon=True)
        self.thread.start()

    def set_auth_url(self, url):
        server_state["auth_url"] = url

    def get_event(self, timeout=None):
        try:
            return auth_queue.get(timeout=timeout)
        except queue.Empty:
            return None
