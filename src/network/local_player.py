import os
import subprocess
import atexit
import psutil
import webbrowser
import time
import signal

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
        """
        Kills any existing spotifyd processes safely across platforms.
        Handles normal and zombie (<defunct>) processes.
        """
        for proc in psutil.process_iter(['name', 'pid', 'cmdline', 'status']):
            try:
                name = proc.info['name']
                cmdline = proc.info.get('cmdline') or []

                if name == 'spotifyd' or any('spotifyd' in arg for arg in cmdline):
                    if proc.info['status'] == psutil.STATUS_ZOMBIE:
                        continue # Ignore zombies, they will be reaped by the OS init system
                    proc.kill()  # Brutal force kill immediately to prevent UI freezes
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                pass
                
        # Clean up any potential lock files or stale sockets in the cache dir
        try:
            for item in os.listdir(self.cache_dir):
                if item.endswith(".sock") or item.endswith(".lock"):
                    os.remove(os.path.join(self.cache_dir, item))
        except Exception:
            pass

    def start(self, audio_config=None):
        if not os.path.exists(self.binary_path):
            return
            
        if self.is_running():
            return

        self._last_audio_config = audio_config

        # Kill any orphaned processes first
        self.stop_existing()

        # Build command from user prefs or defaults
        bitrate = "320"
        
        if audio_config:
            bitrate = audio_config.get("bitrate", bitrate)

        cmd = [
            self.binary_path,
            "--no-daemon",
            "--device-name", self.device_name,
            "--bitrate", bitrate,
            "-c", self.cache_dir,
            "--initial-volume", "100"
        ]
        
        if audio_config and audio_config.get("backend"):
            cmd.extend(["--backend", audio_config.get("backend")])
        if audio_config and audio_config.get("device") and audio_config.get("device") != "default":
            cmd.extend(["--device", audio_config.get("device")])
        
        try:
            log_path = os.path.join(self.cache_dir, "daemon.log")
            self._log_file = open(log_path, "w")
            self.process = subprocess.Popen(
                cmd, 
                stdin=subprocess.DEVNULL,
                stdout=self._log_file, 
                stderr=self._log_file
            )
            
            atexit.register(self.stop)
        except Exception:
            pass

    def restart(self):
        """Silently restarts the daemon using previous config."""
        self.stop()
        self.start(audio_config=self._last_audio_config)

    def stop(self):
        # We explicitly kill it instantly to prevent TUI shutdown hangs
        if self.process:
            try:
                self.process.kill()
                # Do NOT wait() here! Calling wait() on the main thread causes the TUI to freeze.
                # Since the Python app is exiting anyway, the OS init system will reap the zombie.
            except Exception:
                pass
            self.process = None
            
        if hasattr(self, '_log_file') and self._log_file and not self._log_file.closed:
            try:
                self._log_file.close()
            except Exception:
                pass
                
        # Run a final system-wide sweep without blocking
        try:
            import threading
            threading.Thread(target=self.stop_existing, daemon=True).start()
        except Exception:
            pass
