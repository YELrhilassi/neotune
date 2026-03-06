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
        self._last_audio_config = None
        os.makedirs(self.cache_dir, exist_ok=True)

    def is_authenticated(self):
        creds_file = os.path.join(self.cache_dir, "oauth", "credentials.json")
        return os.path.exists(creds_file)

    def is_running(self) -> bool:
        """Checks if the spotifyd process is alive."""
        if self.process is None:
            return False
        return self.process.poll() is None

    def get_auth_process(self):
        """Starts the spotifyd authentication process and returns the popen object."""
        cmd = [
            self.binary_path, 
            "authenticate", 
            "-c", self.cache_dir, 
            "--oauth-port", "8082"
        ]
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def stop_existing(self):
        """Kills any existing spotifyd processes to avoid duplicates or orphans."""
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                if proc.info['name'] == 'spotifyd' and proc.info['pid'] != os.getpid():
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def start(self, audio_config=None):
        if not os.path.exists(self.binary_path):
            return

        self._last_audio_config = audio_config

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
            # We open it in the background but capture errors to a log file
            log_path = os.path.join(self.cache_dir, "daemon.log")
            with open(log_path, "w") as log_file:
                self.process = subprocess.Popen(
                    cmd, 
                    stdout=log_file, 
                    stderr=log_file
                )
            # Register both normal exit and crash/termination exit
            atexit.register(self.stop)
            # Give the daemon 2 seconds to authenticate and appear in the device list
            time.sleep(2)
        except Exception:
            pass

    def restart(self):
        """Silently restarts the daemon using previous config."""
        self.stop()
        self.start(audio_config=self._last_audio_config)

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
