"""Name-key v1 conformance shared with Java query normalization."""

import re
import unicodedata


def name_key(value: str) -> str:
    """NFKC, ASCII lowercase, trim/collapse ASCII whitespace; preserve accents."""
    value = unicodedata.normalize("NFKC", value)
    value = value.translate(
        str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
    )
    return re.sub(r"[ \t\r\n\f\v]+", " ", value).strip(" \t\r\n\f\v")
