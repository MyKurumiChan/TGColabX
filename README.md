# 🚀 TGColabX — Next-Gen Colab Telegram Leecher & Cloud Mirror

<p align="center">
  <b>A lightweight, ultra-fast, and feature-packed Telegram Leecher & Cloud Mirror bot designed specifically for Google Colab.</b><br>
  <i>Powered by DzGram MTProto Engine, Rust WarpCrypto, Aria2c, FFmpeg, and yt-dlp.</i>
</p>

---

## 👨‍💻 Developer & Acknowledgements

### 💖 Author & Lead Developer
* **[MyKurumiChan](https://github.com/MyKurumiChan)** — Project Developer & Maintainer of **TGColabX**.

### 🌟 Core Technologies & Upstream Inspirations
* **[WZML-X](https://github.com/WZML-X)** — For the revolutionary features, flags architecture, circular progress dashboard, automated video merge, sample generation, and status aesthetics.
* **[XronTrix10](https://github.com/XronTrix10)** — For the pioneering Telegram-Leecher Colab architecture.
* **[DownloaderZone (DzGram)](https://github.com/DownloaderZone/DzGram)** — For the high-performance MTProto transfer engine with connection pooling and Rust `WarpCrypto` acceleration.
* **[yt-dlp Team](https://github.com/yt-dlp/yt-dlp)** — For the ultimate media extraction engine and YouTube client stream resolution.
* **[Aria2 Team](https://github.com/aria2/aria2)** — For the high-speed multi-connection split-download engine.
* **[Gofile.io & Pixeldrain](https://gofile.io)** — For direct cloud storage API endpoints.

---

## ✨ Features & Architecture

### ⚡ MTProto High-Throughput Engine (DzGram + Rust WarpCrypto)
* **High-Speed Transfers**: Tuned connection pooling with Rust `WarpCrypto` for multi-megabyte burst uploads without CPU bottlenecks.
* **Auto-Reaping Media Sessions**: Idle media upload sessions are cleanly closed after transfer completion, preventing connection drops and server timeouts.
* **Unbuffered Streaming**: Real-time progress updates directly in Google Colab cells without output buffering.

### 🪟 Single-Window Dashboard & Clutter-Free Chats
* **Unified Status Card**: All active parallel downloads stream inside a single live dashboard card per chat.
* **No Dialogues Flashing**: Intermediate messages (`Getting Download Info`, `Starting upload...`) are eliminated from chat history and integrated smoothly into the live status card.
* **Auto-Delete Commands**: User trigger commands (`/leech`, `/mirror`, `/status`) are auto-deleted to keep group chats clean.

### 🛡️ Duplicate Task & Link Detection
* **Bandwidth Protection**: Detects if a submitted link is already downloading in an active or queued task and alerts the user immediately, preventing duplicate bandwidth usage.

### 📥 Direct Message (DM) & Custom Dump Channel Delivery
* **Keep Groups Clean**: When tasks are triggered inside group chats, completed files are automatically delivered privately to the user's **Bot DM**!
* **Personal Dump Channels**: Users can set their own private Telegram channel ID (`-100...`) in `/usersettings` to store all their personal leeched files automatically.

### ✂️ Freedom to Customize Split Sizes
* **Presets & Custom MB**: Choose between `500 MB`, `1.0 GB`, `1.5 GB`, `2.0 GB` (Free default), `4.0 GB` (Premium), or type your own custom split size in MB (e.g. `800`, `1200`, `3500`).
* **Clean Video Splitting**: Videos are cleanly split into playable segments using FFmpeg stream copy (`-c copy`).
* **Archive Splitting**: Documents and zip archives are cleanly split into numbered 7z parts (`.7z.001`, `.7z.002`).

### 🔒 Access Control (Personal PM vs. Groups)
* **Private Chat (PM) Access**: Only the owner and authorized VIP users can interact with the bot in private messages.
* **Free Users**: Can run commands in authorized groups, and their completed files are delivered to their private Bot DM.
* **Admin Commands**:
  * `/auth <user_id>` — Permit a user to use the bot in private chat.
  * `/unauth <user_id>` — Revoke private chat permission.
  * `/authusers` — List all permitted users.
  * `/authgroup <chat_id>` & `/unauthgroup <chat_id>` — Manage authorized groups.

### 🍪 Personal YouTube Cookies & Custom Cloud APIs
* **yt-dlp Cookies (`cookies.txt`)**: Send your `cookies.txt` file directly to the bot in PM to unlock premium, age-restricted, or member-only YouTube streams.
* **Cloud Storage Uploads**: Upload to **Gofile.io** (`-gofile`) or **Pixeldrain** (`-pixeldrain`) with optional custom API tokens configured in `/usersettings`.

---

## 📋 Commands Reference

| Command | Aliases | Description |
| :--- | :--- | :--- |
| `/leech` | `/l`, `/tupload` | Download and leech file(s) to Telegram (Parallel multi-download) |
| `/mirror` | `/m`, `/gdupload` | Download and mirror file(s) to Google Drive / Cloud hosts |
| `/ytdl` | `/y`, `/ytupload` | Download streaming media via yt-dlp with resolution selector |
| `/merge` | `/mrg` | Merge multiple video or audio parts into a single video |
| `/sample` | `/smp` | Generate video preview clip (e.g. `/sample 30`) |
| `/sshot` | `/ss` | Generate video screenshots (e.g. `/sshot 5`) |
| `/mediainfo` | `/mi` | Inspect technical media info of file |
| `/drupload` | — | Upload a local folder from Colab filesystem |
| `/status` | `/s` | View unified live dashboard of all active downloads |
| `/usetting` | `/usersettings` | Interactive User Settings menu (Prefix, Suffix, Caption, Thumb, Split, Dump, APIs) |
| `/cookies` | `/cookie` | Upload or view personal `cookies.txt` for yt-dlp |
| `/delcookies` | `/delcookie` | Delete personal saved cookies |
| `/bsetting` | `/botsettings` | Bot settings panel (Owner only) |
| `/auth` | — | Authorize user for private PM bot usage (`/auth <user_id>`) |
| `/unauth` | — | Revoke private PM authorization (`/unauth <user_id>`) |
| `/authusers` | — | View list of all authorized users |
| `/authgroup` | — | Authorize group chat (`/authgroup <chat_id>`) |
| `/unauthgroup` | — | Remove authorized group (`/unauthgroup <chat_id>`) |
| `/stats` | `/st` | View Colab server hardware metrics (CPU, RAM, Disk) |
| `/speedtest` | `/stest` | Run internet speedtest on Colab |
| `/ping` | — | Test bot response latency |
| `/cancel <id>` | `/cancel_<id>` | Cancel a specific running task |
| `/cancelall` | `/call` | Cancel all active and queued tasks |
| `/restart` | `/r` | Reset bot state, purge temp cache, and restart |

---

## 🚩 WZML-X Style Flags

Append flags directly to your command or URL:

```bash
# Normal Telegram Leech:
/leech https://example.com/video.mp4 -n MyMovie.mp4 -med

# Leech & Upload to Gofile.io:
/leech https://example.com/video.mp4 -gofile

# Leech & Upload to Pixeldrain:
/leech https://example.com/file.zip -pixeldrain

# Upload to Telegram + Gofile + Pixeldrain:
/leech https://example.com/video.mp4 -all

# Video Sample & Screenshots:
/leech https://example.com/movie.mkv -ss 30 -shots 5

# YouTube Download with 1080p Quality:
/ytdl https://youtube.com/watch?v=... -s 1080

# Archive & Password Protection:
/leech https://example.com/archive.zip -e -p MySecretPassword
```

| Flag | Argument | Description |
| :--- | :--- | :--- |
| `-n` | `<name>` | Set custom output filename |
| `-gofile` / `-gf` | — | Upload directly to Gofile.io |
| `-pixeldrain` / `-pd` | — | Upload directly to Pixeldrain API |
| `-all` | — | Upload to Telegram + Gofile + Pixeldrain |
| `-up` | `<target>` | Destination target (`tg`, `gofile`, `pixeldrain`, `all`) |
| `-doc` | — | Upload as Document (uncompressed file) |
| `-med` | — | Upload as Media (streamable video/audio) |
| `-z` | — | Compress files into a 7z/ZIP archive |
| `-e` | — | Extract archives before uploading |
| `-p` | `<password>` | Password for zip archiving or archive extraction |
| `-m` | — | Automated video/audio merge |
| `-s` / `-q` | `[res]` | Resolution selection (1080, 720, 480, 360, best, mp3) |
| `-ss` | `<seconds>` | Generate sample video clip (e.g. `-ss 30`) |
| `-shots` | `<count>` | Generate screenshot album (e.g. `-shots 5`) |
| `-c` | `<caption>` | Set custom caption for task |
| `-thumb` | `<url>` | Download and set custom thumbnail from URL |

---

## 🚀 How to Run on Google Colab

1. Open **[Google Colab](https://colab.research.google.com/)** and create a new notebook.
2. Paste the contents of [`main.py`](main.py) into a cell.
3. Fill in your credentials in the form parameters:
   - `API_ID`: Get from [my.telegram.org](https://my.telegram.org)
   - `API_HASH`: Get from [my.telegram.org](https://my.telegram.org)
   - `BOT_TOKEN`: Get from [@BotFather](https://t.me/BotFather)
   - `USER_ID`: Your Telegram user ID
   - `DUMP_ID`: Optional channel/group ID for backup logging (e.g. `-100...`)
   - `REPO_URL`: `https://github.com/MyKurumiChan/TGColabX`
4. Run the cell and enjoy high-speed, parallel leeching!

---

## 📜 License & Disclaimer

* Distributed under the terms of the GNU General Public License v3.0.
* Respect Google Colab's Terms of Service: Torrenting/magnet links are restricted to safeguard your Colab runtime.
