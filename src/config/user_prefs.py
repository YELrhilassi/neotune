from pathlib import Path
import os
import lupa
from lupa import LuaRuntime


class UserPreferences:
    def __init__(self, config_dir=None):
        if config_dir is None:
            config_dir = os.path.join(Path.home(), ".config", "neotune")
        self.config_dir = os.path.abspath(config_dir)
        self.lua = LuaRuntime(unpack_returned_tuples=True)

        # Configure Lua package.path so require() works for our config dir
        path_setup = f"package.path = package.path .. ';{self.config_dir}/?.lua;{self.config_dir}/?/init.lua'"
        self.lua.execute(path_setup)

        self.theme = "default"
        self.theme_vars = None
        self.leader = "space"
        self.show_which_key = True
        self.auto_play = False
        self.auto_select_device = True

        # We will store dynamic mappings like: {"p": {"action": "play_pause", "desc": "Play/Pause"}}
        self.keybindings = {
            "p": {"action": "play_pause", "desc": "Play/Pause"},
            "n": {"action": "next_track", "desc": "Next Track"},
            "b": {"action": "prev_track", "desc": "Previous Track"},
            "o": {"action": "show_device", "desc": "Output Device"},
            "a": {"action": "show_audio", "desc": "Audio Backend"},
            "r": {"action": "refresh", "desc": "Refresh Data"},
            ":": {"action": "command_prompt", "desc": "Command Mode"},
            "/": {"action": "search_prompt", "desc": "Search Tracks/Playlists"},
            "s": {"action": "fuzzy_search", "desc": "Fuzzy Search App Content"},
        }

        self.commands = {}

        self.nav_bindings = {
            "up": "k",
            "down": "j",
            "left": "h",
            "right": "l",
            "page_up": "U",
            "page_down": "D",
        }

        self.audio_config = {"backend": "pulseaudio", "device": "default", "bitrate": "320"}
        self.special_playlists = []

        self._expose_api()
        self.load()

    def _expose_api(self):
        # Expose a global api to lua to register configurations
        setup_lua = """
        neotune = {}
        neotune.keymaps = {}
        neotune.commands = {}
        neotune.audio = {}
        neotune.special_playlists = {}
        
        function neotune.set_leader(key)
            neotune.leader = key
        end
        
        function neotune.set_which_key(show)
            neotune.show_which_key = show
        end
        
        function neotune.set_auto_play(enabled)
            neotune.auto_play = enabled
        end
        
        function neotune.set_auto_select_device(enabled)
            neotune.auto_select_device = enabled
        end
        
        function neotune.map(key, action, desc)
            neotune.keymaps[key] = { action = action, desc = desc }
        end
        
        function neotune.command(alias, action, desc)
            neotune.commands[alias] = { action = action, desc = desc }
        end
        
        function neotune.set_nav(up, down, left, right, page_up, page_down)
            neotune.nav = { up = up, down = down, left = left, right = right, page_up = page_up, page_down = page_down }
        end
        
        function neotune.set_audio(backend, device, bitrate)
            neotune.audio.backend = backend
            neotune.audio.device = device
            neotune.audio.bitrate = tostring(bitrate)
        end
        
        function neotune.set_theme(theme, vars)
            neotune.theme = theme
            if vars then
                neotune.theme_vars = vars
            end
        end
        
        function neotune.set_debug(config)
            neotune.debug = config
        end
        """
        self.lua.execute(setup_lua)

    def load(self):
        # Ensure config dir exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Internal lua files path
        internal_lua_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lua")
        
        # Always run the internal init first as base
        internal_init = os.path.join(internal_lua_dir, "init.lua")
        
        # We need to tell lupa where to find the require files. 
        # By default lupa uses package.path
        setup_paths_lua = f"""
        package.path = "{internal_lua_dir}/?.lua;" .. package.path
        """
        self.lua.execute(setup_paths_lua)
        
        if os.path.exists(internal_init):
            try:
                self.lua.require("init")
            except Exception as e:
                import logging
                logging.getLogger("neotune").error(f"Failed to load internal config: {e}")

        # Then let user override with their own init.lua if it exists
        user_init = os.path.join(self.config_dir, "init.lua")
        
        if os.path.exists(user_init):
            setup_user_paths = f"""
            package.path = "{self.config_dir}/?.lua;" .. package.path
            """
            self.lua.execute(setup_user_paths)
            
            try:
                # Use dofile to execute the exact user init.lua without caching conflicts
                self.lua.execute(f'dofile("{user_init}")')
            except Exception as e:
                import logging
                logging.getLogger("neotune").error(f"Failed to load user config: {e}")
        else:
            # If the user doesn't have an init.lua, let's create a stub for them so they know where to configure it
            try:
                with open(user_init, "w") as f:
                    f.write("""-- NeoTune User Configuration
-- This file overrides the default internal configuration
-- You can set your own keybindings, theme, and audio settings here.
-- Example:
-- neotune.set_leader("space")
-- neotune.map("p", "play_pause", "Play/Pause")
-- neotune.set_theme("catppuccin")
""")
            except Exception as e:
                import logging
                logging.getLogger("neotune").error(f"Failed to create stub: {e}")

        try:
            # Extract config from Lua global
            tui_api = self.lua.eval("neotune")

            if tui_api:
                if getattr(tui_api, "theme", None):
                    self.theme = tui_api.theme

                if getattr(tui_api, "theme_vars", None):
                    self.theme_vars = {
                        "primary": getattr(tui_api.theme_vars, "primary", None),
                        "accent": getattr(tui_api.theme_vars, "accent", None),
                        "background": getattr(tui_api.theme_vars, "background", None),
                        "surface": getattr(tui_api.theme_vars, "surface", None),
                        "panel": getattr(tui_api.theme_vars, "panel", None),
                        "success": getattr(tui_api.theme_vars, "success", None),
                        "warning": getattr(tui_api.theme_vars, "warning", None),
                        "error": getattr(tui_api.theme_vars, "error", None),
                    }

                if getattr(tui_api, "leader", None):
                    self.leader = tui_api.leader

                if getattr(tui_api, "show_which_key", None) is not None:
                    self.show_which_key = bool(tui_api.show_which_key)

                if getattr(tui_api, "auto_play", None) is not None:
                    self.auto_play = bool(tui_api.auto_play)

                if getattr(tui_api, "auto_select_device", None) is not None:
                    self.auto_select_device = bool(tui_api.auto_select_device)

                # Extract keybindings
                lua_kb = getattr(tui_api, "keymaps", None)
                if lua_kb:
                    for k, v in lua_kb.items():
                        self.keybindings[k] = {"action": v.action, "desc": v.desc}

                lua_cmds = tui_api.commands
                if lua_cmds:
                    self.commands.clear()
                    for k, v in lua_cmds.items():
                        self.commands[k] = {"action": v.action, "desc": v.desc}

                lua_nav = getattr(tui_api, "nav", None)
                if lua_nav:
                    self.nav_bindings["up"] = getattr(lua_nav, "up", self.nav_bindings["up"])
                    self.nav_bindings["down"] = getattr(lua_nav, "down", self.nav_bindings["down"])
                    self.nav_bindings["left"] = getattr(lua_nav, "left", self.nav_bindings["left"])
                    self.nav_bindings["right"] = getattr(
                        lua_nav, "right", self.nav_bindings["right"]
                    )
                    self.nav_bindings["page_up"] = getattr(
                        lua_nav, "page_up", self.nav_bindings["page_up"]
                    )
                    self.nav_bindings["page_down"] = getattr(
                        lua_nav, "page_down", self.nav_bindings["page_down"]
                    )

                # Extract audio
                lua_audio = getattr(tui_api, "audio", None)
                if lua_audio:
                    self.audio_config["backend"] = getattr(
                        lua_audio, "backend", self.audio_config["backend"]
                    )
                    self.audio_config["device"] = getattr(
                        lua_audio, "device", self.audio_config["device"]
                    )
                    self.audio_config["bitrate"] = getattr(
                        lua_audio, "bitrate", self.audio_config["bitrate"]
                    )

                # Extract special playlists
                lua_sp = getattr(tui_api, "special_playlists", None)
                if lua_sp:
                    self.special_playlists = []

                    def _parse_item(p):
                        if not p:
                            return
                        try:
                            # Try attribute access then dict access
                            name = getattr(p, "name", None)
                            if name is None:
                                try:
                                    name = p["name"]
                                except:
                                    pass

                            uri = getattr(p, "uri", None)
                            if uri is None:
                                try:
                                    uri = p["uri"]
                                except:
                                    pass

                            desc = getattr(p, "description", None)
                            if desc is None:
                                try:
                                    desc = p["description"]
                                except:
                                    desc = ""

                            if name and uri:
                                self.special_playlists.append(
                                    {"name": str(name), "uri": str(uri), "description": str(desc)}
                                )
                        except:
                            pass

                    # Try multiple iteration strategies for lupa
                    try:
                        # Case 1: Array-like table
                        if hasattr(lua_sp, "items"):
                            # This handles dict-like or lupa objects with .items()
                            for _, p in lua_sp.items():
                                _parse_item(p)
                        else:
                            # Case 2: Standard 1-based indexing
                            for i in range(1, 1000):
                                item = lua_sp[i]
                                if item:
                                    _parse_item(item)
                                else:
                                    break
                    except:
                        try:
                            # Case 3: Direct iteration
                            for p in lua_sp:
                                if p:
                                    _parse_item(p)
                        except:
                            pass

                    from src.core.debug_logger import DebugLogger

                    DebugLogger().info(
                        "UserPrefs",
                        f"Loaded {len(self.special_playlists)} special playlists from Lua",
                    )

                # Extract debug config
                lua_debug = getattr(tui_api, "debug", None)
                if lua_debug:
                    from src.core.debug_logger import DebugLogger, DebugConfig

                    debug_config = DebugConfig()
                    debug_config.from_lua(dict(lua_debug))
                    DebugLogger().configure(debug_config)

        except Exception as e:
            print(f"Error loading Lua config: {e}")

    def save_theme(self, theme_name: str):
        self.theme = theme_name
        theme_file = os.path.join(self.config_dir, "theme.lua")
        with open(theme_file, "w") as f:
            f.write(f'neotune.set_theme("{theme_name}")\n')
