# TGColabX - Based on WZML-X & XronTrix10
# Copyright (c) 2024-2026 TGColabX

import os
import json
import logging
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from colab_leecher.utility.variables import Paths

USERS_SETTINGS_FILE = os.path.join(Paths.BASE_DIR, "users_settings.json")
BOT_SETTINGS_FILE = os.path.join(Paths.BASE_DIR, "bot_settings.json")

DEFAULT_USER_SETTINGS = {
    "stream_upload": "Media",          # "Media" or "Document"
    "prefix": "",                      # Filename prefix
    "suffix": "",                      # Filename suffix
    "caption_style": "Monospace",      # "Monospace", "Bold", "Italic", "Underlined", "Default"
    "custom_caption": "",              # Custom caption template
    "ytdl_quality": "Best",            # "Best", "1080p", "720p", "480p", "360p", "Audio MP3"
    "sample_duration": 0,              # 0 (off), 15, 30, 60
    "screenshot_count": 0,             # 0 (off), 3, 5, 10
    "split_video": "2.0GB",            # Preset display: 500MB, 1.0GB, 1.5GB, 2.0GB, 4.0GB, Custom
    "split_size_mb": 1950,             # Actual split size limit in MB
    "convert_video": "No",             # "Yes" or "No"
    "video_out": "mp4",                # "mp4" or "mkv"
    "has_thumb": False,                # Per-user custom thumbnail flag
    "gofile_token": "",                # Custom personal Gofile API account token
    "pixeldrain_token": "",            # Custom personal Pixeldrain API key
    "upload_target": "Telegram",        # "Telegram", "Gofile", "Pixeldrain", "All"
    "dump_channel": "",                # Personal custom dump channel ID or username
    "send_to_dm": True,                # When in group without custom dump channel, send files directly to Bot DM
}

DEFAULT_BOT_SETTINGS = {
    "max_parallel_tasks": 5,           # Max concurrent downloads (1, 2, 3, 5, 10, 0=unlimited)
    "leech_split_size": 2097152000,    # 2GB in bytes (Standard TG limit)
    "default_engine": "aria2c",        # "aria2c" or "yt-dlp"
    "default_mode": "leech",           # "leech" or "mirror"
    "auto_clean_temp": True,           # Auto-clean task folders upon completion
    "auto_delete_commands": True,      # Auto-delete user trigger commands to keep chat clean
    "permitted_users": [],             # User IDs permitted to use bot in private chat (PM)
    "authorized_chats": [],            # Group chat IDs permitted (empty list = all groups)
    "gofile_token": "",                # Global bot Gofile API account token
    "pixeldrain_token": "",            # Global bot Pixeldrain API key
    "default_upload_target": "Telegram", # Default upload destination
}


class SettingsManager:
    _users_data = None
    _bot_data = None

    @classmethod
    def _load_users(cls):
        if cls._users_data is None:
            if os.path.exists(USERS_SETTINGS_FILE):
                try:
                    with open(USERS_SETTINGS_FILE, "r", encoding="utf-8") as f:
                        cls._users_data = json.load(f)
                except Exception as e:
                    logging.error(f"Error loading users_settings.json: {e}")
                    cls._users_data = {}
            else:
                cls._users_data = {}
        return cls._users_data

    @classmethod
    def _save_users(cls):
        try:
            with open(USERS_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(cls._users_data, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving users_settings.json: {e}")

    @classmethod
    def _load_bot(cls):
        if cls._bot_data is None:
            if os.path.exists(BOT_SETTINGS_FILE):
                try:
                    with open(BOT_SETTINGS_FILE, "r", encoding="utf-8") as f:
                        cls._bot_data = json.load(f)
                except Exception as e:
                    logging.error(f"Error loading bot_settings.json: {e}")
                    cls._bot_data = dict(DEFAULT_BOT_SETTINGS)
            else:
                cls._bot_data = dict(DEFAULT_BOT_SETTINGS)
        return cls._bot_data

    @classmethod
    def _save_bot(cls):
        try:
            with open(BOT_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(cls._bot_data, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving bot_settings.json: {e}")

    # ==================== User Settings API ====================

    @classmethod
    def get_user_settings(cls, user_id: int) -> dict:
        data = cls._load_users()
        uid = str(user_id)
        user_conf = dict(DEFAULT_USER_SETTINGS)
        if uid in data:
            user_conf.update(data[uid])

        # Check if user custom thumb exists on disk
        thumb_path = cls.get_user_thumb_path(user_id)
        user_conf["has_thumb"] = os.path.exists(thumb_path)
        return user_conf

    @classmethod
    def set_user_setting(cls, user_id: int, key: str, value):
        data = cls._load_users()
        uid = str(user_id)
        if uid not in data:
            data[uid] = dict(DEFAULT_USER_SETTINGS)
        data[uid][key] = value
        cls._save_users()

    @classmethod
    def reset_user_settings(cls, user_id: int):
        data = cls._load_users()
        uid = str(user_id)
        if uid in data:
            del data[uid]
            cls._save_users()
        cls.delete_user_thumb(user_id)

    @classmethod
    def get_user_thumb_path(cls, user_id: int) -> str:
        thumbs_dir = os.path.join(Paths.WORK_PATH, "user_thumbs")
        os.makedirs(thumbs_dir, exist_ok=True)
        return os.path.join(thumbs_dir, f"thumb_{user_id}.jpg")

    @classmethod
    def save_user_thumb(cls, user_id: int, src_file: str) -> bool:
        try:
            from PIL import Image
            dst_path = cls.get_user_thumb_path(user_id)
            img = Image.open(src_file)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(dst_path, "JPEG", quality=90)
            cls.set_user_setting(user_id, "has_thumb", True)
            return True
        except Exception as e:
            logging.error(f"Error saving user thumbnail: {e}")
            return False

    @classmethod
    def delete_user_thumb(cls, user_id: int) -> bool:
        dst_path = cls.get_user_thumb_path(user_id)
        if os.path.exists(dst_path):
            try:
                os.remove(dst_path)
            except Exception:
                pass
        cls.set_user_setting(user_id, "has_thumb", False)
        return True

    # ==================== Cookie Management API ====================

    @classmethod
    def get_cookie_path(cls, user_id: int = None) -> str:
        """Returns the best matching cookies.txt path for this user or global bot."""
        if user_id:
            u_cookie = os.path.join(Paths.WORK_PATH, "user_cookies", f"cookies_{user_id}.txt")
            if os.path.exists(u_cookie) and os.path.getsize(u_cookie) > 0:
                return u_cookie

        # Global fallbacks
        candidates = [
            os.path.join(os.getcwd(), "cookies.txt"),
            os.path.join(Paths.BASE_DIR, "cookies.txt"),
            os.path.join(Paths.WORK_PATH, "cookies.txt"),
            "/content/cookies.txt",
        ]
        for c in candidates:
            if os.path.exists(c) and os.path.getsize(c) > 0:
                return c
        return ""

    @classmethod
    def has_cookies(cls, user_id: int = None) -> bool:
        return bool(cls.get_cookie_path(user_id))

    @classmethod
    def save_cookies(cls, user_id: int, file_path_or_content: str, is_file: bool = True) -> bool:
        try:
            cookies_dir = os.path.join(Paths.WORK_PATH, "user_cookies")
            os.makedirs(cookies_dir, exist_ok=True)
            target = os.path.join(cookies_dir, f"cookies_{user_id}.txt") if user_id else os.path.join(Paths.BASE_DIR, "cookies.txt")

            if is_file:
                import shutil
                shutil.copy(file_path_or_content, target)
            else:
                content = str(file_path_or_content).strip()
                if not content.startswith("# Netscape HTTP Cookie File"):
                    content = "# Netscape HTTP Cookie File\n# This file was generated by TGColabX\n\n" + content
                with open(target, "w", encoding="utf-8") as f:
                    f.write(content)
            return True
        except Exception as e:
            logging.error(f"Error saving cookies: {e}")
            return False

    @classmethod
    def delete_cookies(cls, user_id: int = None) -> bool:
        deleted = False
        if user_id:
            u_cookie = os.path.join(Paths.WORK_PATH, "user_cookies", f"cookies_{user_id}.txt")
            if os.path.exists(u_cookie):
                try:
                    os.remove(u_cookie)
                    deleted = True
                except Exception:
                    pass
        candidates = [
            os.path.join(Paths.BASE_DIR, "cookies.txt"),
            os.path.join(Paths.WORK_PATH, "cookies.txt"),
        ]
        for c in candidates:
            if os.path.exists(c):
                try:
                    os.remove(c)
                    deleted = True
                except Exception:
                    pass
        return deleted

    # ==================== Bot Settings API ====================

    @classmethod
    def get_bot_settings(cls) -> dict:
        data = cls._load_bot()
        bot_conf = dict(DEFAULT_BOT_SETTINGS)
        bot_conf.update(data)
        return bot_conf

    # ==================== Permissions & Access Control API ====================

    @classmethod
    def get_permitted_users(cls) -> list:
        b = cls.get_bot_settings()
        return [int(u) for u in b.get("permitted_users", []) if str(u).isdigit() or isinstance(u, int)]

    @classmethod
    def add_permitted_user(cls, user_id: int):
        users = set(cls.get_permitted_users())
        users.add(int(user_id))
        cls.set_bot_setting("permitted_users", list(users))

    @classmethod
    def remove_permitted_user(cls, user_id: int):
        users = set(cls.get_permitted_users())
        users.discard(int(user_id))
        cls.set_bot_setting("permitted_users", list(users))

    @classmethod
    def is_user_permitted(cls, user_id: int, owner_id: int = 0) -> bool:
        if owner_id and int(user_id) == int(owner_id):
            return True
        return int(user_id) in cls.get_permitted_users()

    @classmethod
    def get_authorized_chats(cls) -> list:
        b = cls.get_bot_settings()
        return [int(c) for c in b.get("authorized_chats", []) if str(c).lstrip("-").isdigit() or isinstance(c, int)]

    @classmethod
    def add_authorized_chat(cls, chat_id: int):
        chats = set(cls.get_authorized_chats())
        chats.add(int(chat_id))
        cls.set_bot_setting("authorized_chats", list(chats))

    @classmethod
    def remove_authorized_chat(cls, chat_id: int):
        chats = set(cls.get_authorized_chats())
        chats.discard(int(chat_id))
        cls.set_bot_setting("authorized_chats", list(chats))

    @classmethod
    def is_chat_authorized(cls, chat_id: int) -> bool:
        chats = cls.get_authorized_chats()
        if not chats:
            return True  # If empty, all groups are allowed
        return int(chat_id) in chats


# ==================== User Settings Menus ====================

def get_user_settings_text(user_id: int, user_name: str) -> str:
    s = SettingsManager.get_user_settings(user_id)
    thumb_status = "Custom ✅" if s["has_thumb"] else "Default 🖼"
    has_cookie = SettingsManager.has_cookies(user_id)
    cookie_status = "Active ✅" if has_cookie else "None ❌"
    pr = f"<code>{s['prefix']}</code>" if s["prefix"] else "<i>None</i>"
    su = f"<code>{s['suffix']}</code>" if s["suffix"] else "<i>None</i>"
    smp = f"{s['sample_duration']}s" if s['sample_duration'] > 0 else "Off"
    shots = f"{s['screenshot_count']} shots" if s['screenshot_count'] > 0 else "Off"
    cap = f"<code>{s['custom_caption'][:25]}...</code>" if len(s["custom_caption"]) > 25 else (f"<code>{s['custom_caption']}</code>" if s["custom_caption"] else "<i>Standard</i>")

    gf_token = "Custom Key 🔑" if s.get("gofile_token") else "Default Guest 👤"
    pd_token = "Custom Key 🔑" if s.get("pixeldrain_token") else "Default Free 👤"

    dump_val = s.get("dump_channel")
    if dump_val:
        dump_str = f"<code>{dump_val}</code>"
    else:
        dm_flag = s.get("send_to_dm", True)
        dump_str = "<i>Bot DM 📥 (in Groups)</i>" if dm_flag else "<i>Current Chat 💬</i>"

    split_str = f"{s.get('split_size_mb', 1950)} MB" if s.get("split_size_mb") else s.get("split_video", "2.0GB")

    text = (
        f"👤 <b><i>TGColabX User Settings</i></b>\n"
        f"User: <b>{user_name}</b> (ID: <code>{user_id}</code>)\n"
        f"<blockquote>Customize your leeching preferences below!</blockquote>\n\n"
        f"╭⌬ <b>Upload Mode   :</b> <i>{s['stream_upload']}</i>\n"
        f"├⌬ <b>Caption Font  :</b> <i>{s['caption_style']}</i>\n"
        f"├⌬ <b>YT-DLP Quality:</b> <i>{s['ytdl_quality']}</i>\n"
        f"├⌬ <b>YT-DLP Cookies:</b> <i>{cookie_status}</i>\n"
        f"├⌬ <b>Gofile API    :</b> <i>{gf_token}</i>\n"
        f"├⌬ <b>Pixeldrain API:</b> <i>{pd_token}</i>\n"
        f"├⌬ <b>Split Limit   :</b> <i>{split_str}</i>\n"
        f"├⌬ <b>File Delivery :</b> {dump_str}\n"
        f"├⌬ <b>Sample Clip   :</b> <i>{smp}</i>\n"
        f"├⌬ <b>Screenshots   :</b> <i>{shots}</i>\n"
        f"├⌬ <b>Convert Video :</b> <i>{s['convert_video']} ({s['video_out'].upper()})</i>\n"
        f"├⌬ <b>Prefix        :</b> {pr}\n"
        f"├⌬ <b>Suffix        :</b> {su}\n"
        f"├⌬ <b>Custom Caption:</b> {cap}\n"
        f"╰⌬ <b>Thumbnail     :</b> <i>{thumb_status}</i>"
    )
    return text


def get_user_settings_markup(user_id: int) -> InlineKeyboardMarkup:
    s = SettingsManager.get_user_settings(user_id)
    next_mode = "Document" if s["stream_upload"] == "Media" else "Media"
    has_cookie = SettingsManager.has_cookies(user_id)
    cookie_icon = "🍪 Cookies (✅)" if has_cookie else "🍪 Cookies (❌)"
    split_str = f"{s.get('split_size_mb', 1950)}MB" if s.get("split_size_mb") else s.get("split_video", "2.0GB")

    buttons = [
        [
            InlineKeyboardButton(f"📦 Upload Mode: {s['stream_upload']}", callback_data=f"uset_mode_{user_id}"),
        ],
        [
            InlineKeyboardButton(f"🎬 YT: {s['ytdl_quality']}", callback_data=f"uset_ytmenu_{user_id}"),
            InlineKeyboardButton(f"🔤 Font: {s['caption_style']}", callback_data=f"uset_fontmenu_{user_id}"),
        ],
        [
            InlineKeyboardButton("🖼 Thumbnail", callback_data=f"uset_thumbmenu_{user_id}"),
            InlineKeyboardButton(cookie_icon, callback_data=f"uset_cookiemenu_{user_id}"),
        ],
        [
            InlineKeyboardButton("🔑 Custom APIs", callback_data=f"uset_apimenu_{user_id}"),
            InlineKeyboardButton("📝 Custom Caption", callback_data=f"uset_setcap_{user_id}"),
        ],
        [
            InlineKeyboardButton("🏷 Prefix / Suffix", callback_data=f"uset_affixmenu_{user_id}"),
        ],
        [
            InlineKeyboardButton(f"🎞 Sample ({s['sample_duration']}s)", callback_data=f"uset_samplemenu_{user_id}"),
            InlineKeyboardButton(f"📸 Shots ({s['screenshot_count']})", callback_data=f"uset_shotsmenu_{user_id}"),
        ],
        [
            InlineKeyboardButton(f"✂️ Split Limit: {split_str}", callback_data=f"uset_splitmenu_{user_id}"),
            InlineKeyboardButton(f"🔄 Convert: {s['convert_video']}", callback_data=f"uset_convert_{user_id}"),
        ],
        [
            InlineKeyboardButton("📢 Dump Channel & DM", callback_data=f"uset_dumpmenu_{user_id}"),
        ],
        [
            InlineKeyboardButton("♻️ Reset Defaults", callback_data=f"uset_reset_{user_id}"),
            InlineKeyboardButton("❌ Close", callback_data="uset_close"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def get_split_menu_markup(user_id: int) -> InlineKeyboardMarkup:
    s = SettingsManager.get_user_settings(user_id)
    curr_mb = s.get("split_size_mb", 1950)
    buttons = [
        [
            InlineKeyboardButton(f"{'✅ ' if curr_mb == 500 else ''}500 MB", callback_data=f"uset_setsplit_500_{user_id}"),
            InlineKeyboardButton(f"{'✅ ' if curr_mb == 1000 else ''}1.0 GB", callback_data=f"uset_setsplit_1000_{user_id}"),
        ],
        [
            InlineKeyboardButton(f"{'✅ ' if curr_mb == 1500 else ''}1.5 GB", callback_data=f"uset_setsplit_1500_{user_id}"),
            InlineKeyboardButton(f"{'✅ ' if curr_mb == 1950 else ''}2.0 GB (Default)", callback_data=f"uset_setsplit_1950_{user_id}"),
        ],
        [
            InlineKeyboardButton(f"{'✅ ' if curr_mb == 3900 else ''}4.0 GB (Premium)", callback_data=f"uset_setsplit_3900_{user_id}"),
            InlineKeyboardButton("✏️ Custom Size (MB)", callback_data=f"uset_customsplit_{user_id}"),
        ],
        [
            InlineKeyboardButton("« Back to Settings", callback_data=f"uset_back_{user_id}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def get_dump_menu_markup(user_id: int) -> InlineKeyboardMarkup:
    s = SettingsManager.get_user_settings(user_id)
    d_chan = s.get("dump_channel", "")
    d_label = f"📢 Dump: {d_chan}" if d_chan else "📢 Set Custom Dump Channel"
    dm_status = "Deliver to DM: Enabled ✅" if s.get("send_to_dm", True) else "Deliver to DM: Disabled ❌"

    buttons = [
        [
            InlineKeyboardButton(d_label, callback_data=f"uset_setdump_{user_id}"),
        ],
        [
            InlineKeyboardButton(dm_status, callback_data=f"uset_toggledm_{user_id}"),
        ],
    ]
    if d_chan:
        buttons.append([
            InlineKeyboardButton("🗑 Clear Custom Dump Channel", callback_data=f"uset_cleardump_{user_id}")
        ])
    buttons.append([
        InlineKeyboardButton("« Back to Settings", callback_data=f"uset_back_{user_id}")
    ])
    return InlineKeyboardMarkup(buttons)


def get_api_menu_markup(user_id: int) -> InlineKeyboardMarkup:
    s = SettingsManager.get_user_settings(user_id)
    gf_lbl = "📁 Gofile Token (Set ✅)" if s.get("gofile_token") else "📁 Set Gofile Token"
    pd_lbl = "⚡ Pixeldrain Key (Set ✅)" if s.get("pixeldrain_token") else "⚡ Set Pixeldrain Key"

    buttons = [
        [
            InlineKeyboardButton(gf_lbl, callback_data=f"uset_setgofile_{user_id}"),
            InlineKeyboardButton(pd_lbl, callback_data=f"uset_setpixeldrain_{user_id}"),
        ],
        [
            InlineKeyboardButton("🗑 Clear Custom APIs", callback_data=f"uset_clearapis_{user_id}"),
        ],
        [
            InlineKeyboardButton("« Back to Settings", callback_data=f"uset_back_{user_id}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def get_cookie_menu_markup(user_id: int) -> InlineKeyboardMarkup:
    has_cookie = SettingsManager.has_cookies(user_id)
    buttons = []
    if has_cookie:
        buttons.append([
            InlineKeyboardButton("🗑 Delete My cookies.txt", callback_data=f"uset_delcookies_{user_id}")
        ])
    buttons.append([
        InlineKeyboardButton("« Back to Settings", callback_data=f"uset_back_{user_id}")
    ])
    return InlineKeyboardMarkup(buttons)


def get_ytdl_quality_markup(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("⭐ Best Available", callback_data=f"uset_setyt_Best_{user_id}"),
            InlineKeyboardButton("🎬 1080p (FHD)", callback_data=f"uset_setyt_1080p_{user_id}"),
        ],
        [
            InlineKeyboardButton("🎬 720p (HD)", callback_data=f"uset_setyt_720p_{user_id}"),
            InlineKeyboardButton("🎬 480p (SD)", callback_data=f"uset_setyt_480p_{user_id}"),
        ],
        [
            InlineKeyboardButton("🎬 360p", callback_data=f"uset_setyt_360p_{user_id}"),
            InlineKeyboardButton("🎵 Audio MP3", callback_data=f"uset_setyt_Audio MP3_{user_id}"),
        ],
        [
            InlineKeyboardButton("« Back to Settings", callback_data=f"uset_back_{user_id}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def get_font_style_markup(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("Monospace (code)", callback_data=f"uset_setfont_Monospace_{user_id}"),
            InlineKeyboardButton("Bold (b)", callback_data=f"uset_setfont_Bold_{user_id}"),
        ],
        [
            InlineKeyboardButton("Italic (i)", callback_data=f"uset_setfont_Italic_{user_id}"),
            InlineKeyboardButton("Underlined (u)", callback_data=f"uset_setfont_Underlined_{user_id}"),
        ],
        [
            InlineKeyboardButton("Default Regular", callback_data=f"uset_setfont_Default_{user_id}"),
        ],
        [
            InlineKeyboardButton("« Back to Settings", callback_data=f"uset_back_{user_id}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def get_sample_markup(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("❌ Disabled (0s)", callback_data=f"uset_setsample_0_{user_id}"),
            InlineKeyboardButton("15 Seconds", callback_data=f"uset_setsample_15_{user_id}"),
        ],
        [
            InlineKeyboardButton("30 Seconds", callback_data=f"uset_setsample_30_{user_id}"),
            InlineKeyboardButton("60 Seconds", callback_data=f"uset_setsample_60_{user_id}"),
        ],
        [
            InlineKeyboardButton("« Back to Settings", callback_data=f"uset_back_{user_id}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def get_shots_markup(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("❌ Disabled (0)", callback_data=f"uset_setshots_0_{user_id}"),
            InlineKeyboardButton("3 Screenshots", callback_data=f"uset_setshots_3_{user_id}"),
        ],
        [
            InlineKeyboardButton("5 Screenshots", callback_data=f"uset_setshots_5_{user_id}"),
            InlineKeyboardButton("10 Screenshots", callback_data=f"uset_setshots_10_{user_id}"),
        ],
        [
            InlineKeyboardButton("« Back to Settings", callback_data=f"uset_back_{user_id}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def get_thumb_menu_markup(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("🗑 Delete Custom Thumb", callback_data=f"uset_delthumb_{user_id}"),
        ],
        [
            InlineKeyboardButton("« Back to Settings", callback_data=f"uset_back_{user_id}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


# ==================== Bot Settings Menus (Admin / Owner) ====================

def get_bot_settings_text(active_count: int = 0) -> str:
    b = SettingsManager.get_bot_settings()
    split_gb = "4.0 GB (Premium)" if b["leech_split_size"] > 2500000000 else "2.0 GB (Standard TG)"
    max_p = f"{b['max_parallel_tasks']} Tasks" if b['max_parallel_tasks'] > 0 else "Unlimited ⚡"

    text = (
        f"🤖 <b><i>TGColabX Bot & System Settings</i></b>\n"
        f"<blockquote>Control global bot execution and limits (Owner Panel)</blockquote>\n\n"
        f"╭⌬ <b>Max Concurrent Tasks:</b> <i>{max_p}</i>\n"
        f"├⌬ <b>Telegram Split Limit :</b> <i>{split_gb}</i>\n"
        f"├⌬ <b>Default Leech Engine :</b> <i>{b['default_engine'].upper()}</i>\n"
        f"├⌬ <b>Default Mode         :</b> <i>{b['default_mode'].capitalize()}</i>\n"
        f"├⌬ <b>Auto-Clean Workspace :</b> <i>{'Enabled ✅' if b['auto_clean_temp'] else 'Disabled ❌'}</i>\n"
        f"╰⌬ <b>Active Tasks Running :</b> <code>{active_count}</code>"
    )
    return text


def get_bot_settings_markup() -> InlineKeyboardMarkup:
    b = SettingsManager.get_bot_settings()
    split_btn = "📏 Split: 4GB" if b["leech_split_size"] <= 2500000000 else "📏 Split: 2GB"
    engine_btn = "🌐 Engine: yt-dlp" if b["default_engine"] == "aria2c" else "🌐 Engine: Aria2c"
    mode_btn = "🎯 Mode: Mirror" if b["default_mode"] == "leech" else "🎯 Mode: Leech"

    buttons = [
        [
            InlineKeyboardButton(f"⚡ Max Tasks: {b['max_parallel_tasks']}", callback_data="bset_tasks_menu"),
            InlineKeyboardButton(split_btn, callback_data="bset_toggle_split"),
        ],
        [
            InlineKeyboardButton(engine_btn, callback_data="bset_toggle_engine"),
            InlineKeyboardButton(mode_btn, callback_data="bset_toggle_mode"),
        ],
        [
            InlineKeyboardButton("🧹 Purge Cache & Temp", callback_data="bset_purge_temp"),
            InlineKeyboardButton("🔄 Reset Bot Engine", callback_data="bset_reset_bot"),
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="bset_close"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def get_bot_tasks_markup() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("1 (Sequential)", callback_data="bset_settasks_1"),
            InlineKeyboardButton("2 Concurrent", callback_data="bset_settasks_2"),
            InlineKeyboardButton("3 Concurrent", callback_data="bset_settasks_3"),
        ],
        [
            InlineKeyboardButton("5 Concurrent (Rec)", callback_data="bset_settasks_5"),
            InlineKeyboardButton("10 Concurrent", callback_data="bset_settasks_10"),
            InlineKeyboardButton("Unlimited ⚡", callback_data="bset_settasks_0"),
        ],
        [
            InlineKeyboardButton("« Back to Bot Settings", callback_data="bset_back"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)
