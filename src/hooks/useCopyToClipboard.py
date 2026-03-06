import subprocess
import platform

def useCopyToClipboard(text: str) -> bool:
    """
    Attempts to copy text to the system clipboard using available system tools.
    Supports Linux (xclip, wl-copy), macOS (pbcopy), and Windows (clip).
    """
    try:
        os_type = platform.system()
        
        if os_type == "Linux":
            # Try wl-copy (Wayland)
            try:
                subprocess.run(['wl-copy'], input=text.encode('utf-8'), check=True)
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
                
            # Try xclip (X11)
            try:
                subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode('utf-8'), check=True)
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
                
        elif os_type == "Darwin": # macOS
            subprocess.run(['pbcopy'], input=text.encode('utf-8'), check=True)
            return True
            
        elif os_type == "Windows":
            subprocess.run(['clip'], input=text.encode('utf-16'), check=True)
            return True
            
        return False
    except Exception:
        return False
