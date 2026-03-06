import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, os.getcwd())

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    from src.config.client_config import ClientConfiguration
except ImportError as e:
    print(f"Error: Missing dependencies. {e}")
    sys.exit(1)

def run_auth_test():
    print("=== Standalone Spotify Auth Test ===\n")
    
    # 1. Load Configuration
    config = ClientConfiguration()
    if not config.is_valid():
        print("Error: Client configuration is invalid or missing.")
        print(f"Checked path: {config.config_path}")
        return

    print(f"Config loaded from: {config.config_path}")
    print(f"Client ID: {config.client_id[:5]}...")
    print(f"Redirect URI: {config.redirect_uri}")

    # 2. Initialize OAuth
    scope = "user-read-playback-state,user-modify-playback-state,playlist-read-private,user-read-currently-playing,user-library-read,user-read-recently-played"
    auth_manager = SpotifyOAuth(
        client_id=config.client_id,
        client_secret=config.client_secret,
        redirect_uri=config.redirect_uri,
        scope=scope,
        open_browser=False
    )

    # 3. Check for cached token
    token_info = auth_manager.get_cached_token()
    if token_info:
        print("\n[✓] Found cached token.")
        if auth_manager.is_token_expired(token_info):
            print("Token is expired. Attempting refresh...")
            try:
                token_info = auth_manager.refresh_access_token(token_info['refresh_token'])
                print("[✓] Token refreshed successfully.")
            except Exception as e:
                print(f"[X] Token refresh failed: {e}")
                token_info = None
        else:
            print("Token is still valid.")

    # 4. Interactive login if no valid token
    if not token_info:
        print("\n[!] No valid token found. Starting interactive login...")
        auth_url = auth_manager.get_authorize_url()
        print(f"\n1. Open this URL in your browser:\n{auth_url}")
        
        print("\n2. Log in and authorize.")
        response_url = input("\n3. Paste the FULL redirect URL here: ").strip()
        
        try:
            code = auth_manager.parse_response_code(response_url)
            token = auth_manager.get_access_token(code, as_dict=False)
            if token:
                print("\n[✓] Authentication successful! Token acquired.")
                token_info = {"access_token": token}
            else:
                print("\n[X] Failed to acquire token.")
        except Exception as e:
            print(f"\n[X] Error during code exchange: {e}")

    # 5. Verify with API call
    if token_info:
        print("\nVerifying with Spotify API...")
        try:
            sp = spotipy.Spotify(auth=token_info['access_token'])
            user = sp.current_user()
            print(f"[✓] Connected as: {user['display_name']} ({user['id']})")
            
            devices = sp.devices()
            print(f"[✓] Visible devices: {len(devices['devices'])}")
            for d in devices['devices']:
                active = "[ACTIVE]" if d['is_active'] else ""
                print(f"    - {d['name']} {active}")
                
        except Exception as e:
            print(f"[X] API Verification failed: {e}")

if __name__ == "__main__":
    run_auth_test()
