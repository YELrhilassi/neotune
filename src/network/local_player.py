import os
import subprocess
import atexit
import psutil
import time
import signal


class LocalPlayer:
    def __init__(self, device_name="Spotify TUI Player"):
        # Strictly use librespot compiled from source
        self.binary_path = self._find_binary()
        self.device_name = device_name
        self.cache_dir = os.path.expanduser("~/.cache/spotify_tui_librespot")
        self.binary_type = "librespot"

        self.process = None
        self._last_audio_config = None
        os.makedirs(self.cache_dir, exist_ok=True)

    def _find_binary(self):
        # 1. Check local librespot (compiled and placed here)
        local_librespot = os.path.join(os.path.dirname(__file__), "librespot")
        if os.path.exists(local_librespot):
            return local_librespot

        # 2. Check system PATH for librespot as fallback
        try:
            return subprocess.check_output(["which", "librespot"]).decode().strip()
        except Exception:
            pass

        return "librespot"

    def is_authenticated(self):
        # librespot usually saves credentials in the cache dir if it has them
        creds_file = os.path.join(self.cache_dir, "credentials.json")
        return os.path.exists(creds_file)

    def is_running(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    def stop_existing(self):
        try:
            # Forcefully kill any existing librespot processes to ensure we start fresh
            # and no ghost processes are left behind from previous crashes.
            import psutil

            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    # Check if 'librespot' is in name or any of the cmdline arguments
                    is_librespot = "librespot" in (proc.info["name"] or "").lower()
                    if not is_librespot and proc.info["cmdline"]:
                        is_librespot = any(
                            "librespot" in arg.lower() for arg in proc.info["cmdline"]
                        )

                    if is_librespot and proc.pid != os.getpid():
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass

    def start(self, audio_config=None, access_token=None):
        if self.is_running():
            return

        self._last_audio_config = audio_config
        self.stop_existing()

        bitrate = "320"
        if audio_config:
            bitrate = audio_config.get("bitrate", bitrate)

        cmd = [
            self.binary_path,
            "--name",
            self.device_name,
            "--bitrate",
            bitrate,
            "--cache",
            self.cache_dir,
            "--initial-volume",
            "100",
            "--device-type",
            "computer",
            "--disable-discovery",  # Ensure it doesn't stay alive as a discovery daemon
        ]

        if access_token:
            cmd.extend(["--access-token", access_token])

        if audio_config and audio_config.get("backend"):
            cmd.extend(["--backend", audio_config.get("backend")])

        try:
            log_path = os.path.join(self.cache_dir, "librespot.log")
            self._log_file = open(log_path, "w")

            def preexec_fn():
                # On Linux, ensure the child dies when the parent dies
                try:
                    import ctypes

                    libc = ctypes.CDLL("libc.so.6")
                    # PR_SET_PDEATHSIG = 1, SIGKILL = 9
                    libc.prctl(1, 9, 0, 0, 0)
                except Exception:
                    pass

            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=self._log_file,
                stderr=self._log_file,
                preexec_fn=preexec_fn if os.name == "posix" else None,
            )
            atexit.register(self.stop)
        except Exception as e:
            print(f"Failed to start librespot: {e}")

    def restart(self, access_token=None):
        self.stop()
        # Wait a moment for port to release
        time.sleep(0.5)
        self.start(self._last_audio_config, access_token=access_token)

    def stop(self):

        if self.process:
            try:
                self.process.kill()
                self.process.wait(timeout=1)
            except Exception:
                pass
            self.process = None

        if hasattr(self, "_log_file") and self._log_file and not self._log_file.closed:
            try:
                self._log_file.close()
            except Exception:
                pass
        self.stop_existing()

    def __del__(self):
        self.stop()
