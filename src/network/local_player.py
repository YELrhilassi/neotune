import os
import subprocess
import atexit
import psutil
import webbrowser
import time

class LocalPlayer:
    def __init__(self, device_name="Spotify TUI Player"):
        # The binary should be in the same folder as this script
        self.binary_path = os.path.join(os.path.dirname(__file__), "spotifyd")
        self.device_name = device_name
        self.cache_dir = os.path.expanduser("~/.cache/spotify_tui_daemon")
        self.process = None
        os.makedirs(self.cache_dir, exist_ok=True)

    def is_authenticated(self):
        creds_file = os.path.join(self.cache_dir, "oauth", "credentials.json")
        return os.path.exists(creds_file)

    def authenticate(self):
        # We don't print to terminal anymore. 
        # For spotifyd, it will use the web auth token if we configure it correctly,
        # but spotifyd often requires its own auth.
        # We will let it fail silently or use browser auth if it supports it.
        pass

    def stop_existing(self):
        """Kills any existing spotifyd processes to avoid duplicates or orphans."""
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] == 'spotifyd':
                    proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def start(self, audio_config=None):
        if not os.path.exists(self.binary_path):
            return

        # Kill any orphaned processes first
        self.stop_existing()

        # Build command from user prefs or defaults
        backend = "pulseaudio"
        bitrate = "320"
        device = "default"
        
        if audio_config:
            backend = audio_config.get("backend", backend)
            bitrate = audio_config.get("bitrate", bitrate)
            device = audio_config.get("device", device)

        cmd = [
            self.binary_path,
            "--no-daemon",
            "--device-name", self.device_name,
            "--bitrate", bitrate,
            "--backend", backend,
            "-c", self.cache_dir
        ]
        
        # Only add device if it's not 'default' or if backend is not pulseaudio
        if device != "default":
            cmd.extend(["--device", device])
        
        try:
            # We open it in the background
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            # Register both normal exit and crash/termination exit
            atexit.register(self.stop)
        except Exception:
            pass

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None
        # Double check to kill any orphans in the same group
        self.stop_existing()
