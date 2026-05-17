import logging
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from bot.config import settings

logging.basicConfig(level=logging.DEBUG)

app = Client("cfm_bot", api_id=settings.api_id, api_hash=settings.api_hash, bot_token=settings.bot_token)

@app.on_message(filters.private)
async def on_msg(client, message):
    print("=== MESSAGE RECEIVED ===", flush=True)
    print("FROM:", message.from_user.id, flush=True)
    print("TEXT:", message.text, flush=True)
    await message.reply("**Hello!** Bot works.", parse_mode=ParseMode.MARKDOWN)
    print("=== REPLY SENT ===", flush=True)

print("STARTING...", flush=True)
app.run()
print("STOPPED.", flush=True)
