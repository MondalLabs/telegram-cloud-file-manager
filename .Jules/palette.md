## 2024-05-18 - Inline Cancel Button UX
**Learning:** Forcing users to type commands like `/cancel` during active conversational flows (FSMs) creates high friction, especially on mobile. Inline buttons are vastly superior for flow control in chat interfaces.
**Action:** Always provide inline keyboard alternatives for critical escape routes (like cancelling) rather than relying solely on slash commands.
## 2024-05-19 - Helpful Empty States\n**Learning:** Users can feel lost when arriving at an empty state (e.g. empty folders or empty user lists) without clear instructions on what they can do next.\n**Action:** Always provide actionable guidance and calls-to-action in empty states (e.g., 'Tap ➕ New Folder or 📤 Upload below to add content.') tailored to the user's permissions.
## 2024-05-20 - Pagination Layout Shifts in Inline Keyboards
**Learning:** Telegram inline keyboards automatically center their rows based on the number of buttons. Omitting 'Prev' or 'Next' buttons on the first or last pages of a paginated list causes the row to jump from 3 buttons to 2, causing a jarring layout shift that displaces the page indicator and causes misclicks.
**Action:** Always maintain a consistent button count per row in paginated keyboards by replacing inactive 'Prev'/'Next' buttons with disabled-like placeholders (e.g. `·` with a `noop` callback).
