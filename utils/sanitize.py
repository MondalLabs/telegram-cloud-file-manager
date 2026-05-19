"""
utils/sanitize.py
─────────────────────────────────────────────────────────────────────────────
Utilities to sanitize user-provided text that will be rendered by Pyrogram.

Pyrogram will throw an exception if strings with unclosed Markdown tags are
passed to a handler with ParseMode.MARKDOWN enabled, resulting in a persistent DoS.
"""

def escape_markdown(text: str) -> str:
    """
    Escapes Markdown formatting characters to prevent Markdown Injection / DoS.
    """
    if not text:
        return text

    # Escape backslashes first to prevent bypass payloads
    text = text.replace("\\", "\\\\")

    # Escape markdown specifiers to avoid rendering issues.
    for char in ("*", "_", "`", "[", "]", "~", "|"):
        text = text.replace(char, f"\\{char}")

    return text
