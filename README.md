# ☁️ Telegram Cloud File Manager

![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)
![Pyrogram](https://img.shields.io/badge/Pyrogram-2.3-blue?style=for-the-badge&logo=telegram)
![MongoDB](https://img.shields.io/badge/MongoDB_Atlas-Green?style=for-the-badge&logo=mongodb)

An ultra-robust, industrial-grade virtual file system and cloud storage manager operating entirely through a Telegram bot. 

Instead of paying for AWS S3 or Google Cloud Storage, this bot utilizes **Telegram's native CDN** as a limitless backend to store files. It provides a beautiful, folder-based navigation UI inside Telegram to manage, organize, and securely share your files with authorized users.

---

## ✨ Enterprise-Grade Features

* **♾️ Zero-Storage Footprint:** The server running this bot requires 0 bytes of disk space for your files. Media is uploaded to a private Telegram "Dump Group", and the bot only saves the resulting `file_id` references to MongoDB.
* **🔐 Role-Based Access Control (RBAC):** Built-in whitelist system. 
  * **Owner:** Full access to create folders, upload files, delete content, and approve/revoke users.
  * **Approved Users:** Can browse the library and request files.
  * **Guests:** Denied access automatically until manually approved by the Owner.
* **📂 Infinite Virtual Hierarchy:** Create folders inside folders, rename them, and organize your files just like a real operating system.
* **🛡️ Secure File Delivery (DRM):** 
  * Media sent to users is **Forward-Protected** (`protect_content=True`) so it cannot be saved to their gallery or forwarded to other chats.
  * **Auto-Deleting Media:** Files automatically vanish from the user's chat after 1 hour (configurable) to maintain strict access control and keep the chat clean.
* **⚡ Highly Performant:** Fully asynchronous event loop powered by `asyncio`, Pyrogram, and Beanie ODM (Motor) for blazing fast MongoDB interactions.
* **🌐 Cloud Deployment Ready:** Includes an integrated Uvicorn health-check server, making it 100% compatible with free cloud hosting platforms like Render or Railway.

---

## 🚀 Beginner-Friendly Setup Guide

Follow these steps exactly to get your Cloud File Manager running from scratch.

### Step 1: Get Telegram API Credentials
1. Go to [my.telegram.org](https://my.telegram.org/auth) and log in with your phone number.
2. Click on **"API development tools"**.
3. Create a new application (you can enter anything for the app name and short name).
4. Note down your **`API_ID`** (a number) and **`API_HASH`** (a long string). You will need these later.

### Step 2: Create Your Bot
1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts to give your bot a name and a username (must end in `_bot`).
3. BotFather will give you an HTTP API Token (e.g., `1234567890:ABCdefGhIJKlmNoPQRstuVWXyz`). This is your **`BOT_TOKEN`**.

### Step 3: Setup MongoDB Database (Free)
This bot needs a database to remember your folder structure and approved users.
1. Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas/register) and create a free account.
2. Build a **Free Cluster** (M0 sandbox).
3. Under **Database Access**, create a new database user with a username and password.
4. Under **Network Access**, click "Add IP Address" and select **"Allow Access from Anywhere"** (`0.0.0.0/0`).
5. Go back to your Cluster, click **Connect**, choose **Drivers**, select Python, and copy the connection string.
6. Replace `<password>` in the string with the password you created in step 3. This is your **`MONGO_URI`**.

### Step 4: Get Your Telegram ID
1. Go to Telegram and search for [@userinfobot](https://t.me/userinfobot) or [@RawDataBot](https://t.me/RawDataBot).
2. Send `/start` to it.
3. It will reply with your `Id` (a number like `123456789`). This is your **`OWNER_ID`**.

---

## 💻 Local Installation

If you want to run the bot on your own computer:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/telegram-cloud-file-manager.git
   cd telegram-cloud-file-manager
   ```

2. **Create a Virtual Environment:**
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Mac/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables:**
   Rename the `.env.example` file to `.env` and fill in the values you gathered above:
   ```env
   API_ID=your_api_id
   API_HASH=your_api_hash
   BOT_TOKEN=your_bot_token
   MONGO_URI=mongodb+srv://user:password@cluster.mongodb.net/
   OWNER_ID=your_telegram_id
   DUMP_CHAT_ID= 
   HEALTH_PORT=10000
   ITEMS_PER_PAGE=15
   ```
   *(Leave `DUMP_CHAT_ID` blank for now).*

5. **Start the Bot:**
   ```bash
   python -m bot
   ```

---

## 🛠️ The "Dump Group" Initialization

The bot needs a private Telegram group to act as the "hidden storage drive" where files are actually uploaded before being registered in the database.

1. Create a **New Private Group** in Telegram.
2. Add your newly created bot to this group.
3. Inside the group, send the command: `/setup`
4. The bot will automatically detect the group ID, save it to the database, and link itself to this group. **Your bot is now fully operational!**
5. Go to the bot's private chat and send `/start` to open the File Manager UI.

---

## ☁️ Free Hosting Deployment (Render)

You can host this bot 24/7 for **free** using [Render.com](https://render.com).

1. Upload your code to a private GitHub repository.
2. Create an account on Render and click **New+** -> **Web Service**.
3. Connect your GitHub account and select your bot repository.
4. Fill in the settings:
   * **Environment:** `Python 3`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `python -m bot`
5. Scroll down to **Environment Variables** and add all the variables from your `.env` file (`API_ID`, `API_HASH`, `BOT_TOKEN`, `MONGO_URI`, `OWNER_ID`, `HEALTH_PORT=10000`).
6. Click **Create Web Service**. 

> **💡 Why a Web Service?** 
> Render's free tier spins down background workers. By using a Web Service, the built-in `HEALTH_PORT` (Uvicorn server) binds to a port. You can then use a free pinging service like [Cron-job.org](https://cron-job.org) to ping your Render URL every 14 minutes, keeping your bot awake 24/7 forever!

---

## 📱 Using the Bot

* **`/start`** - Opens the main dashboard (always cleans up old menus so your chat stays neat).
* **Manage Folders** - Click "New Folder" to create infinite nested hierarchies.
* **Upload Files** - Click "Upload", select the folder destination, and forward/send any files, photos, or videos to the bot. Click "✅ Done" when finished.
* **Manage Users** - Only the Owner sees the "Manage Users" button. You can approve pending users by entering their Telegram ID, or revoke them at any time.
* **Playback** - When an approved user clicks a file, it is delivered securely with rich metadata (Duration, Size, Resolution) and is automatically deleted after 1 hour.

---
*Built with ❤️ for robust, scalable Telegram architecture.*
