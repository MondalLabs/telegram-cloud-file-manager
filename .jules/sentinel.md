## 2023-10-27 - Telegram Markdown Injection DoS
**Vulnerability:** User-controlled inputs (file/folder names, usernames) containing unclosed Markdown formatting characters (like `*`, `_`, `~`, `|`, `[`, `]`, `` ` ``) are directly injected into strings formatted with `ParseMode.MARKDOWN`.
**Learning:** Pyrogram's `ParseMode.MARKDOWN` does not automatically escape user inputs. If an unmatched markdown character is present, it throws an exception (HTTP 400 Bad Request), causing the bot's UI or specific workflows (like listing users or browsing folders) to crash permanently for that entry, leading to a persistent Denial of Service (DoS).
**Prevention:** Always escape user inputs at the presentation layer (in handlers/keyboards) right before rendering them in Markdown-formatted strings. Use a utility that explicitly escapes backslashes first to prevent bypass payloads, and then escapes all markdown characters (`text.replace(char, f"\\{char}")`). Do not mutate the underlying data in the database.

## 2024-05-19 - Markdown Injection in Config Variables and Chat Titles
**Vulnerability:** Config variables (like `cfg.display_name`) and chat attributes (like `chat_title` from a group) were interpolated directly into Markdown-formatted strings without escaping.
**Learning:** Even data that seems internal (like config variables or group titles) can contain unbalanced Markdown characters (e.g. `*`, `_`, `[`), causing Pyrogram to throw `Bad Request: can't parse entities` and crash the handler (DoS).
**Prevention:** Extend the practice of escaping Markdown to ALL dynamic text interpolation when `ParseMode.MARKDOWN` is used, including config values and chat titles, not just user names and file names. Use `utils.sanitize.escape_markdown` consistently.
