from src.core.di import Container
from src.state.store import Store
from src.network.spotify_network import SpotifyNetwork
from src.config.user_prefs import UserPreferences

class CommandService:
    def execute(self, action: str, app_instance):
        from src.ui.modals.theme_selector import ThemeSelector
        from src.ui.modals.telescope import TelescopePrompt
        from src.ui.modals.command_prompt import CommandPrompt
        from src.ui.modals.audio_modals import DeviceSelector, AudioConfigSelector
        
        network = Container.resolve(SpotifyNetwork)
        store = Container.resolve(Store)
        prefs = Container.resolve(UserPreferences)

        if action == "play_pause":
            playing = app_instance.safe_network_call(network.toggle_play_pause)
            if playing is not None:
                app_instance.notify("Playing" if playing else "Paused")
                app_instance.update_now_playing()
        elif action == "next_track":
            if app_instance.safe_network_call(network.next_track) is not None:
                app_instance.notify("Next track")
                app_instance.update_now_playing()
        elif action == "prev_track":
            if app_instance.safe_network_call(network.prev_track) is not None:
                app_instance.notify("Previous track")
                app_instance.update_now_playing()
        elif action == "toggle_shuffle":
            state = app_instance.safe_network_call(network.toggle_shuffle)
            if state is not None:
                app_instance.notify(f"Shuffle {'On' if state else 'Off'}")
                app_instance.update_now_playing()
        elif action == "cycle_repeat":
            state = app_instance.safe_network_call(network.cycle_repeat)
            if state is not None:
                app_instance.notify(f"Repeat: {state.capitalize()}")
                app_instance.update_now_playing()
        elif action == "show_device":
            devices_data = app_instance.safe_network_call(network.get_devices)
            if not devices_data or not devices_data.get('devices'):
                app_instance.notify("No available devices found", severity="warning")
                return
            devices = devices_data['devices']
            active_id = next((d['id'] for d in devices if d['is_active']), None)
            def on_device_selected(device_id: str):
                if device_id:
                    selected_device = next((d for d in devices if d['id'] == device_id), None)
                    if selected_device:
                        store.set("preferred_device_id", device_id)
                        store.set("preferred_device_name", selected_device['name'])
                    app_instance.safe_network_call(network.transfer_playback, device_id, force_play=True)
                    app_instance.notify(f"Switched output.")
                    app_instance.update_now_playing()
            app_instance.push_screen(DeviceSelector(devices, active_id), on_device_selected)
        elif action == "show_audio":
            def on_config_selected(new_config: dict):
                if new_config:
                    prefs.audio_config.update(new_config)
                    app_instance.local_player.stop()
                    app_instance.local_player.start(prefs.audio_config)
                    app_instance.notify(f"Backend switched to {new_config['backend']}. Restarting player...")
            app_instance.push_screen(AudioConfigSelector(prefs.audio_config), on_config_selected)
        elif action == "theme_selector":
            def on_theme_selected(theme_name: str):
                if theme_name:
                    prefs.save_theme(theme_name)
                    app_instance.notify(f"Theme '{theme_name}' saved. Restart to apply.", severity="information")
            app_instance.push_screen(ThemeSelector(prefs.theme), on_theme_selected)
        elif action == "command_prompt":
            app_instance.push_screen(CommandPrompt())
        elif action == "search_prompt":
            app_instance.push_screen(TelescopePrompt())
        elif action == "toggle_sidebar":
            sidebar = app_instance.query_one("#sidebar")
            sidebar.display = not sidebar.display
            if not sidebar.display:
                app_instance.query_one("#track-list").focus()
        elif action == "refresh":
            app_instance.refresh_data()
            app_instance.update_now_playing()
            app_instance.notify("Refreshed")
        elif action == "logout":
            from src.ui.modals.confirmation import ConfirmationModal
            def on_confirm(confirmed: bool):
                if confirmed:
                    from src.hooks.useLogout import useLogout
                    useLogout(app_instance)
            app_instance.push_screen(ConfirmationModal("Are you sure you want to logout and clear all sessions?"), on_confirm)
        elif action == "quit":
            app_instance.exit()
        else:
            app_instance.notify(f"Unknown action: {action}", severity="warning")
