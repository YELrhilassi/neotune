import re


def strip_icons(text: str) -> str:
    if not text:
        return ""

    # 1. Target non-BMP characters and specific symbol blocks (emojis, misc symbols, etc)
    # This regex is optimized for terminal-disrupting characters
    clean = re.sub(
        r"[\U00010000-\U0010ffff\u2600-\u27BF\u2300-\u23FF\u2b50\u2b55\u203c\u2049\u2122\u2139\u2194-\u2199\u21a9-\u21aa\u231a-\u231b\u2328\u23cf\u23e9-\u23f3\u23f8-\u23fa\u24c2\u25aa-\u25ab\u25b6\u25c0\u25fb-\u25fe\u2b05-\u2b07\u2b1b-\u2b1c\u2b50\u2b55\u3030\u303d\u3297\u3299]",
        "",
        text,
    )

    # 2. Clean up whitespace
    clean = re.sub(r"\s+", " ", clean).strip()

    return clean
