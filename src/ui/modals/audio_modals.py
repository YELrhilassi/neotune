from textual.app import ComposeResult
from textual.widgets import Label, OptionList
from textual.containers import Middle
from src.ui.modals.base import BaseModal

class DeviceSelector(BaseModal[str]):
    def __init__(self, devices, active_device_id):
        super().__init__()
        self.devices = devices
        self.active_device_id = active_device_id

    def compose(self) -> ComposeResult:
        with Middle(id="device-dialog"):
            yield Label("Select Audio Output", id="device-title")
            options = []
            for d in self.devices:
                name = d['name']
                if d['id'] == self.active_device_id or d.get('is_active'):
                    name = f"[*] {name}"
                else:
                    name = f"[ ] {name}"
                options.append(name)
            yield OptionList(*options, id="device-list")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        selected_device = self.devices[event.option_index]
        self.dismiss(selected_device['id'])

class AudioConfigSelector(BaseModal[dict]):
    def __init__(self, current_config):
        super().__init__()
        self.current_config = current_config
        self.backends = ["pulseaudio", "alsa", "rodio", "pipe"]

    def compose(self) -> ComposeResult:
        with Middle(id="audio-config-dialog"):
            yield Label("Select Audio Backend", id="audio-config-title")
            options = []
            for b in self.backends:
                name = b
                if b == self.current_config.get("backend"):
                    name = f"[*] {name}"
                else:
                    name = f"[ ] {name}"
                options.append(name)
            yield OptionList(*options, id="backend-list")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        new_backend = self.backends[event.option_index]
        self.dismiss({"backend": new_backend})
