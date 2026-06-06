## 2024-05-18 - Inline Cancel Button UX
**Learning:** Forcing users to type commands like `/cancel` during active conversational flows (FSMs) creates high friction, especially on mobile. Inline buttons are vastly superior for flow control in chat interfaces.
**Action:** Always provide inline keyboard alternatives for critical escape routes (like cancelling) rather than relying solely on slash commands.
## 2024-05-19 - Helpful Empty States\n**Learning:** Users can feel lost when arriving at an empty state (e.g. empty folders or empty user lists) without clear instructions on what they can do next.\n**Action:** Always provide actionable guidance and calls-to-action in empty states (e.g., 'Tap ➕ New Folder or 📤 Upload below to add content.') tailored to the user's permissions.
## 2024-05-20 - Pagination Layout Shifts in Inline Keyboards
**Learning:** Telegram inline keyboards automatically center their rows based on the number of buttons. Omitting 'Prev' or 'Next' buttons on the first or last pages of a paginated list causes the row to jump from 3 buttons to 2, causing a jarring layout shift that displaces the page indicator and causes misclicks.
**Action:** Always maintain a consistent button count per row in paginated keyboards by replacing inactive 'Prev'/'Next' buttons with disabled-like placeholders (e.g. `·` with a `noop` callback).
## 2024-05-21 - Maintain Navigation Context on Cancel/Delete
**Learning:** Users experience a "jarring layout shift" and lose context when they are teleported to the root directory after cancelling an action deep within a nested folder structure. Context-aware return navigation is essential for a smooth file manager UX.
**Action:** Always maintain the user's navigational state during FSM actions or destructive confirmations. When an action is completed or cancelled, read the contextual data (such as `parent_id` or `folder_id`) and return the user exactly where they were instead of a generic main menu.
## 2024-05-22 - Personalized Empty States
**Learning:** Generic empty states can feel impersonal. Addressing the user by their display name when they reach an empty state adds a touch of personalization and makes the interface feel more engaging.
**Action:** Personalize empty state messages using the user's name where appropriate.
## 2026-06-03 - Interactive Toast Labels for Informational Buttons
**Learning:** Users can misclick on 'dead' informational buttons (like disabled arrows or page indicators) which fails silently, causing confusion.
**Action:** Use the `query.answer()` toast capability to provide helpful, temporary feedback (e.g., '🚫 No more pages' or '📄 Page X of Y') on informational buttons, turning dead elements into interactive micro-interactions.
