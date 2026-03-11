"""Local Spotify player using librespot binary."""

import os
import subprocess
import atexit
import psutil
import time
import signal
from pathlib import Path
from typing import Optional, Any

from src.core.logging_config import get_logger
from src.core.debug_logger import DebugLogger
from src.core.constants import PlayerSettings, Paths

logger = get_logger("local_player")


class LocalPlayer:
    """Manages local librespot player process."""

    def __init__(self, device_name: str = PlayerSettings.DEVICE_NAME):
        """Initialize LocalPlayer.

        Args:
            device_name: Name to display for this device on Spotify
        """
        self.debug_logger = DebugLogger()
        self.binary_path = self._find_binary()
        self.device_name = device_name
        self.cache_dir = str(Paths.CACHE_DIR)
        self.binary_type = "librespot"

        self.process: Optional[subprocess.Popen] = None
        self._last_audio_config: Optional[dict] = None
        self._log_file: Optional[Any] = None

        Paths.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _find_binary(self) -> str:
        """Locate librespot binary.

        Returns:
            Path to librespot binary or "librespot" as fallback
        """
        # Check local librespot first
        local_librespot = Path(__file__).parent / "librespot"
        if local_librespot.exists():
            return str(local_librespot)

        # Fallback to system PATH
        try:
            result = subprocess.check_output(["which", "librespot"]).decode().strip()
            return result
        except Exception:
            self.debug_logger.warning("LocalPlayer", "Could not find librespot in PATH")
            logger.warning("Could not find librespot in PATH, using default")

        return "librespot"

    def is_authenticated(self) -> bool:
        """Check if librespot has cached credentials.

        Returns:
            True if credentials file exists
        """
        creds_file = Path(self.cache_dir) / "credentials.json"
        return creds_file.exists()

    def is_running(self) -> bool:
        """Check if player process is running.

        Returns:
            True if process is active
        """
        if self.process is None:
            return False
        return self.process.poll() is None

    def stop_existing(self, wait: bool = True) -> None:
        """Kill any existing librespot processes with multiple passes."""
        my_pid = os.getpid()

        def is_librespot_proc(proc):
            try:
                # Check process name
                name = (proc.info.get("name") or "").lower()
                if "librespot" in name:
                    return True

                # Check command line
                cmdline = proc.info.get("cmdline") or []
                for arg in cmdline:
                    if "librespot" in arg.lower():
                        # Make sure it's not a python script or this process
                        if not arg.endswith(".py") and "python" not in arg.lower():
                            return True
                return False
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return False

        try:
            # Pass 1: SIGTERM
            found = False
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                if proc.pid == my_pid:
                    continue

                if is_librespot_proc(proc):
                    try:
                        proc.terminate()
                        found = True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

            if not found:
                return

            if wait:
                # Brief wait
                try:
                    time.sleep(0.5)
                except KeyboardInterrupt:
                    pass

            # Pass 2: SIGKILL
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                if proc.pid == my_pid:
                    continue

                if is_librespot_proc(proc):
                    try:
                        proc.kill()
                        self.debug_logger.debug(
                            "LocalPlayer", f"Killed librespot process {proc.pid}"
                        )
                        logger.debug(f"Killed librespot process {proc.pid}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        except Exception as e:
            logger.debug(f"Error in stop_existing: {e}")

    def start(
        self, audio_config: Optional[dict] = None, access_token: Optional[str] = None
    ) -> None:
        """Start the librespot process.

        Args:
            audio_config: Dictionary with 'backend' and 'bitrate' keys
            access_token: Spotify access token for authentication
        """
        if self.is_running():
            self.debug_logger.debug("LocalPlayer", "Process already running")
            logger.debug("LocalPlayer already running")
            return

        self._last_audio_config = audio_config
        self.stop_existing()

        bitrate = (
            audio_config.get("bitrate", PlayerSettings.DEFAULT_BITRATE)
            if audio_config
            else PlayerSettings.DEFAULT_BITRATE
        )

        cmd = [
            self.binary_path,
            "--name",
            self.device_name,
            "--bitrate",
            str(bitrate),
            "--cache",
            self.cache_dir,
            "--initial-volume",
            PlayerSettings.INITIAL_VOLUME,
            "--device-type",
            PlayerSettings.DEVICE_TYPE,
            "--disable-discovery",
        ]

        if access_token:
            cmd.extend(["--access-token", access_token])

        if audio_config:
            backend = audio_config.get("backend")
            if backend:
                cmd.extend(["--backend", str(backend)])

        try:
            log_path = Paths.LIBRESPOT_LOG_FILE
            self._log_file = open(log_path, "w")

            def preexec_fn():
                """Ensure child process dies when parent dies (Linux only)."""
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

            # Use a flag to ensure we only register once
            if not hasattr(self, "_atexit_registered"):
                atexit.register(self.stop)
                self._atexit_registered = True

            self.debug_logger.info(
                "LocalPlayer", f"Started librespot with PID {self.process.pid}", {"cmd": cmd}
            )
            logger.info(f"Started librespot with PID {self.process.pid}")
        except Exception as e:
            self.debug_logger.error("LocalPlayer", f"Failed to start librespot: {e}")
            logger.error(f"Failed to start librespot: {e}")

    def restart(self, access_token: Optional[str] = None) -> None:
        """Restart the player process.

        Args:
            access_token: Spotify access token
        """
        self.stop()
        time.sleep(0.5)  # Wait for port to release
        self.start(self._last_audio_config, access_token=access_token)

    def stop(self, wait: bool = True) -> None:
        """Stop the player process and cleanup."""
        if hasattr(self, "_is_stopping") and self._is_stopping:
            return
        self._is_stopping = True
        try:
            if self.process:
                try:
                    self.debug_logger.debug(
                        "LocalPlayer", f"Stopping librespot process {self.process.pid}"
                    )
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=1 if wait else 0.1)
                    except (subprocess.TimeoutExpired, KeyboardInterrupt):
                        self.process.kill()
                        try:
                            self.process.wait(timeout=0.5 if wait else 0.1)
                        except:
                            pass
                    self.debug_logger.debug("LocalPlayer", "Stopped librespot process")
                    logger.debug(f"Stopped librespot process")
                except Exception as e:
                    self.debug_logger.debug("LocalPlayer", f"Error stopping process: {e}")
                    logger.debug(f"Error stopping process: {e}")
                self.process = None

            if self._log_file and not self._log_file.closed:
                try:
                    self._log_file.close()
                except Exception as e:
                    logger.debug(f"Error closing log file: {e}")

            self.stop_existing(wait=wait)
        finally:
            self._is_stopping = False

    def __del__(self):
        """Cleanup on object destruction."""
        self.stop()
