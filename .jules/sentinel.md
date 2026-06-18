## 2023-10-27 - Telegram Markdown Injection DoS
**Vulnerability:** User-controlled inputs (file/folder names, usernames) containing unclosed Markdown formatting characters (like `*`, `_`, `~`, `|`, `[`, `]`, `` ` ``) are directly injected into strings formatted with `ParseMode.MARKDOWN`.
**Learning:** Pyrogram's `ParseMode.MARKDOWN` does not automatically escape user inputs. If an unmatched markdown character is present, it throws an exception (HTTP 400 Bad Request), causing the bot's UI or specific workflows (like listing users or browsing folders) to crash permanently for that entry, leading to a persistent Denial of Service (DoS).
**Prevention:** Always escape user inputs at the presentation layer (in handlers/keyboards) right before rendering them in Markdown-formatted strings. Use a utility that explicitly escapes backslashes first to prevent bypass payloads, and then escapes all markdown characters (`text.replace(char, f"\\{char}")`). Do not mutate the underlying data in the database.

## 2024-05-19 - Markdown Injection in Config Variables and Chat Titles
**Vulnerability:** Config variables (like `cfg.display_name`) and chat attributes (like `chat_title` from a group) were interpolated directly into Markdown-formatted strings without escaping.
**Learning:** Even data that seems internal (like config variables or group titles) can contain unbalanced Markdown characters (e.g. `*`, `_`, `[`), causing Pyrogram to throw `Bad Request: can't parse entities` and crash the handler (DoS).
**Prevention:** Extend the practice of escaping Markdown to ALL dynamic text interpolation when `ParseMode.MARKDOWN` is used, including config values and chat titles, not just user names and file names. Use `utils.sanitize.escape_markdown` consistently.

## 2025-02-28 - Information Disclosure via Exception Handling
**Vulnerability:** Broad exception handlers (`except Exception as e:`) directly presented the raw exception string `str(e)` to end-users via Telegram messages.
**Learning:** Displaying raw exceptions can expose sensitive backend configuration, MongoDB connection strings with credentials (like `ServerSelectionTimeoutError('mongodb+srv://user:pass@...')`), or internal stack traces to the user. Even though the user might be an admin/owner, it's unsafe to leak backend state.
**Prevention:** Catch specific expected exceptions (like `ValueError` or `RuntimeError`) when safe, and provide a generic user-friendly error message for unexpected internal errors, logging the actual stack trace via `log.error` server-side instead.

## 2025-06-03 - DoS via Missing Input Length Limits
**Vulnerability:** File and folder creation/renaming handlers did not enforce a length limit on user input for `name`.
**Learning:** Pyrogram API has internal message length limits. If a user provides an excessively long file or folder name, it could cause `MessageTooLong` exceptions or database bloat, resulting in a persistent Denial of Service (DoS) when attempting to render those entities in UI elements.
**Prevention:** Always enforce strict string length validations (e.g., max 64 characters) on user-controlled names before writing to the database or passing to the Pyrogram client.
## 2025-06-03 - DoS via Missing Input Length Limits
**Vulnerability:** File names extracted from uploaded Telegram media (e.g., via `getattr(media, "file_name", None)`) could be arbitrarily long. When rendered in Markdown messages, they exceeded Pyrogram API limits (`MessageTooLong` error), causing a persistent Denial of Service (DoS) for handlers processing those files.
**Learning:** External inputs, even seemingly benign ones like file names from Telegram media, must be treated as untrusted and can cause application crashes if their length is not constrained before storage and rendering.
**Prevention:** Always truncate or limit the length of file names (e.g., to 128 characters) immediately after extraction and before writing to the database or passing to the Pyrogram client, while taking care to preserve the file extension if applicable.
## 2024-05-24 - Unhandled PydanticObjectId Validation
**Vulnerability:** Instantiating `PydanticObjectId` from untrusted user input without validation in Pyrogram callback endpoints.
**Learning:** `PydanticObjectId` will raise `bson.errors.InvalidId` exceptions if given invalid hex strings. Untrusted callback query payloads lacking `is_valid` checks could crash the application or cause DoS conditions.
**Prevention:** Always validate `folder_id_str` or other IDs from user input with `PydanticObjectId.is_valid()` before instantiation in `handlers/*.py` and other untrusted inputs.
