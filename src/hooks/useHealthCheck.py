import os
import psutil
from src.core.di import Container
from src.config.client_config import ClientConfiguration
from src.network.spotify_network import SpotifyNetwork
from src.network.local_player import LocalPlayer


def useHealthCheck(app):
    """
    Performs a full diagnostic check of the application state.
    """
    report = []
    report.append("[bold #cba6f7]=== Spotify TUI Health Report ===[/]\n")

    # 1. Config Check
    config = Container.resolve(ClientConfiguration)
    report.append("[bold #89b4fa][Config][/]")
    report.append(
        f"  Valid: {'[#a6e3a1]Yes[/]' if config.is_valid() else '[#f38ba8]No[/]'}"
    )
    report.append(f"  Path: {config.config_path}")
    report.append(f"  Redirect URI: {config.redirect_uri}")

    # 2. Network/Auth Check
    network = Container.resolve(SpotifyNetwork)
    report.append("\n[bold #89b4fa][Spotify API][/]")
    device_list = []
    try:
        devices = network.get_devices()
        auth_status = (
            "[#a6e3a1]Authenticated[/]"
            if network.is_authenticated()
            else "[#f38ba8]Not Authenticated[/]"
        )
        report.append(f"  Status: {auth_status}")

        device_list = devices.get("devices", []) if devices else []
        report.append(f"  Visible Devices: {len(device_list)}")
        for d in device_list:
            status = "(Active)" if d["is_active"] else ""
            report.append(f"    - {d['name']} {status} [#6c7086][{d['id'][:8]}...][/]")
    except Exception as e:
        report.append(f"  [#f38ba8]Error:[/] {e}")

    # 3. Local Player Check
    player = Container.resolve(LocalPlayer)
    report.append("\n[bold #89b4fa][Local Player (librespot)][/]")

    # Check if librespot exists in path or local
    binary_exists = False
    if os.path.exists(player.binary_path):
        binary_exists = True
    else:
        try:
            import subprocess

            subprocess.check_output(["which", "librespot"])
            binary_exists = True
        except:
            binary_exists = False

    report.append(
        f"  Binary Found: {'[#a6e3a1]Yes[/]' if binary_exists else '[#f38ba8]No[/]'}"
    )
    report.append(
        f"  Process Running: {'[#a6e3a1]Yes[/]' if player.is_running() else '[#f38ba8]No[/]'}"
    )

    # Check for external librespot processes
    external_daemons = []
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            if "librespot" in (proc.info["name"] or "") or any(
                "librespot" in arg for arg in (proc.info["cmdline"] or [])
            ):
                external_daemons.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if external_daemons:
        report.append(f"  System Processes: {len(external_daemons)}")
    else:
        report.append("  System Processes: None found")

    # 4. Logs
    log_path = os.path.join(player.cache_dir, "librespot.log")
    if os.path.exists(log_path):
        report.append("\n[bold #89b4fa][Player Logs][/]")
        try:
            with open(log_path, "r") as f:
                lines = f.readlines()
                for line in lines[-5:]:
                    report.append(f"  {line.strip()}")
        except Exception:
            report.append("  Failed to read logs.")

    full_report = "\n".join(report)
    app.app_log(full_report)

    if not player.is_running() or not device_list:
        app.notify(
            "Health check complete: [bold #f38ba8]Issues Found[/]. Check logs (ctrl+L).",
            severity="warning",
        )
    else:
        app.notify(
            "Health check complete: [bold #a6e3a1]System OK[/]. Check logs (ctrl+L).",
            severity="information",
        )

    return full_report
