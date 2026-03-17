import re

with open("src/actions/auth_actions.py", "r") as f:
    code = f.read()

# We want to replace the body of logout
new_logout = """
def logout(app: Any) -> None:
    \"\"\"Perform full logout: stop player, clear caches, remove credentials.

    Args:
        app: Application instance with notify and exit methods
    \"\"\"
    from src.ui.modals.confirmation import ConfirmationModal

    def _on_confirm(confirmed: bool):
        if not confirmed:
            return
            
        debug = DebugLogger()
        try:
            # Stop and cleanup local player
            player = Container.resolve(LocalPlayer)
            if player:
                player.stop()
                debug.info("AuthActions", "Stopped local player")
                logger.info("Stopped local player")

            # Clear librespot cache directory
            if Paths.CACHE_DIR.exists():
                shutil.rmtree(Paths.CACHE_DIR)
                debug.info("AuthActions", "Cleared librespot cache")
                logger.info("Cleared librespot cache")

            # Clear spotipy token cache
            token_cache = Path(".cache")
            if token_cache.exists():
                token_cache.unlink()
                debug.info("AuthActions", "Cleared token cache")
                logger.info("Cleared token cache")

            # Remove stored client credentials
            if Paths.CLIENT_CONFIG_FILE.exists():
                Paths.CLIENT_CONFIG_FILE.unlink()
                debug.info("AuthActions", "Cleared client config")
                logger.info("Cleared client config")

            app.notify(
                "Logged out successfully. Restart the app to re-configure.",
                severity="information",
            )

            # Exit the application
            app.exit()

        except Exception as e:
            logger.error(f"Logout failed: {e}")
            app.notify(f"Logout failed: {e}", severity="error")

    app.push_screen(ConfirmationModal("Are you sure you want to logout and clear session?"), _on_confirm)
"""

code = re.sub(r'def logout\(app: Any\) -> None:.*', new_logout, code, flags=re.DOTALL)

with open("src/actions/auth_actions.py", "w") as f:
    f.write(code)
