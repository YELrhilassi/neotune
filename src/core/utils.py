import re

def strip_icons(text: str) -> str:
    if not text:
        return ""
    # Strip typical emoji ranges and symbols that mess up terminal rendering
    clean = re.sub(r'[\U00010000-\U0010ffff\u2600-\u27BF\u2300-\u23FF]', '', text)
    return clean.strip()
