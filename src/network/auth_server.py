"""Web-based authentication server for initial setup."""

import queue
import threading
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Template

from src.core.constants import ServerSettings
from src.core.logging_config import get_logger
from src.core.debug_logger import DebugLogger

logger = get_logger("auth_server")
debug = DebugLogger()

app = FastAPI()
auth_queue = queue.Queue()
server_state: dict[str, Optional[str]] = {"auth_url": None}

# Disable uvicorn/fastapi spam
import logging

logging.getLogger("uvicorn.access").setLevel(logging.ERROR)
logging.getLogger("uvicorn.error").setLevel(logging.ERROR)

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
<input type="text" name="redirect_uri" value="{{ redirect_uri }}" required>
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


def render_html(step: str) -> str:
    """Render HTML template with given step.

    Args:
        step: Current setup step

    Returns:
        Rendered HTML string
    """
    template = Template(HTML_TEMPLATE)
    return template.render(step=step, redirect_uri=ServerSettings.DEFAULT_REDIRECT_URI)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Handle index route."""
    if "code" in request.query_params or "error" in request.query_params:
        full_url = str(request.url)
        auth_queue.put({"type": "callback", "url": full_url})
        debug.info("AuthServer", "Received OAuth callback", {"url": full_url})
        logger.info("Received OAuth callback")
        return HTMLResponse(render_html("success"))
    return HTMLResponse(render_html("config"))


@app.post("/setup", response_class=HTMLResponse)
async def setup(
    client_id: str = Form(...),
    client_secret: str = Form(...),
    redirect_uri: str = Form(...),
) -> HTMLResponse:
    """Handle setup form submission."""
    auth_queue.put(
        {
            "type": "config",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }
    )
    debug.info("AuthServer", "Received client configuration", {"client_id": client_id})
    logger.info("Received client configuration")
    return HTMLResponse(render_html("authorize"))


@app.get("/authorize-link", response_model=None)
async def authorize_link() -> RedirectResponse | HTMLResponse:
    """Redirect to Spotify authorization URL."""
    if server_state["auth_url"]:
        return RedirectResponse(server_state["auth_url"])
    return HTMLResponse("Authorization link not ready yet. Please wait a second and refresh.")


@app.get("/callback", response_class=HTMLResponse)
async def callback(request: Request) -> HTMLResponse:
    """Handle OAuth callback."""
    full_url = str(request.url)
    auth_queue.put({"type": "callback", "url": full_url})
    logger.info("Received OAuth callback via /callback endpoint")
    return HTMLResponse(render_html("success"))


class AuthServer:
    """Web server for handling Spotify OAuth flow."""

    def __init__(self, port: int = ServerSettings.DEFAULT_PORT) -> None:
        """Initialize auth server.

        Args:
            port: Port to listen on
        """
        self.port = port
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the authentication server in background thread."""
        config = uvicorn.Config(
            app, host=ServerSettings.DEFAULT_HOST, port=self.port, log_level="error"
        )
        server = uvicorn.Server(config)
        self.thread = threading.Thread(target=server.run, daemon=True)
        self.thread.start()
        logger.info(f"Auth server started on {ServerSettings.DEFAULT_HOST}:{self.port}")

    def set_auth_url(self, url: str) -> None:
        """Set the Spotify authorization URL.

        Args:
            url: Authorization URL from SpotifyOAuth
        """
        server_state["auth_url"] = url
        logger.debug("Auth URL set")

    def get_event(self, timeout: Optional[float] = None) -> Optional[dict]:
        """Get event from queue.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Event dictionary or None if timeout
        """
        try:
            return auth_queue.get(timeout=timeout)
        except queue.Empty:
            return None
