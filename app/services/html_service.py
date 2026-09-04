import re

import bleach


ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "ol",
    "ul",
    "li",
    "span",
]

ALLOWED_ATTRIBUTES = {
    "span": ["class"],
}


def sanitize_html(value: str) -> str:
    if not value:
        return ""
    value = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", value, flags=re.IGNORECASE | re.DOTALL)
    return bleach.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )
