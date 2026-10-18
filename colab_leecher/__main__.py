# TGColabX - Based on WZML-X & XronTrix10
# Copyright (c) 2024-2026 TGColabX

import os
import re
import sys
import json
import random
import logging
import platform
import subprocess
import shutil
import psutil
from time import time
from datetime import datetime
from io import BytesIO
from asyncio import sleep, get_event_loop
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from colab_leecher import colab_bot, OWNER, bot_start_time
from colab_leecher.utility.handler import cancelTask
from colab_leecher.utility.variables import BOT, MSG, BotTimes, Paths, Messages
from colab_leecher.utility.task_manager import (
    task_starter,
    dispatch_task,
    ACTIVE_TASKS,
    CHAT_STATUS_MSGS,
    TaskContext,
)
from colab_leecher.utility.settings_manager import (
    SettingsManager,
    get_user_settings_text,
    get_user_settings_markup,
    get_cookie_menu_markup,
    get_api_menu_markup,
    get_ytdl_quality_markup,
    get_font_style_markup,
    get_sample_markup,
    get_shots_markup,
    get_thumb_menu_markup,
    get_split_menu_markup,
    get_dump_menu_markup,
    get_bot_settings_text,
    get_bot_settings_markup,
    get_bot_tasks_markup,
)
from colab_leecher.utility.helper import (
    isLink,
    setThumbnail,
    download_thumbnail_from_url,
    message_deleter,
    send_settings,
    sizeUnit,
    getTime,
    is_torrent_or_magnet,
    sysINFO,
    keyboard,
    quality_buttons,
    get_media_info_text,
    render_multi_status,
)

src_request_msg = None
PENDING_QUALITY_REQUESTS = {}  # req_id -> {links, user_name, chat_id, options, mode_type}
USER_INPUT_STATES = {}         # user_id -> "set_prefix" | "set_suffix" | "set_caption"

EASTER_EGGS = [
    "💀 <b><i>Stop it, Get Some Help!</i></b>",
    "☠️ <b><i>Bro… there's nothing here.</i></b>",
    "🧠 <b><i>Empty. Just like your head.</i></b>",
    "👻 <b><i>Ghost town, pal. No tasks here.</i></b>",
    "📭 <b><i>The taskbox is emptier than your DMs.</i></b>",
    "🥶 <b><i>Cold, dead silence. No action here.</i></b>",
    "🕳️ <b><i>A black hole of nothingness.</i></b>",
    "😴 <b><i>Asleep on the job? Nope — nothing started.</i></b>",
    "🔍 <b><i>Searched everywhere — found nothing.</i></b>",
    "🖥️ <b><i>System idle. Awaiting your orders.</i></b>",
    "🚫 <b><i>No active tasks right now!</i></b>",
]


def parse_flags_and_links(input_text: str, reply_message=None):
    """
    Parses links and WZML-X style flags from text or replied message.
    Supported Flags:
      -n <name>          : Custom file name
      -doc               : Stream upload = False (Document)
      -med               : Stream upload = True (Media)
      -z                 : Compress / zip mode
      -e                 : Extract / unzip mode
      -p <pswd>          : Archive password
      -m / -merge        : Automated video/audio merge
      -s / -q [res]      : Resolution selection (1080, 720, 480, 360, best, mp3)
      -ss <seconds>      : Video sample generation duration
      -shots <num>       : Screenshots count to generate
      -c <caption>       : Custom caption
      -thumb <url>       : Custom thumbnail URL
    """
    lines = (input_text or "").strip().splitlines()
    first_line_parts = lines[0].split() if lines else []

    if first_line_parts and first_line_parts[0].startswith("/"):
        tokens = first_line_parts[1:]
    else:
        tokens = first_line_parts

    links = []
    custom_name = ""
    stream_upload = None
    mode_type = "normal"
    password = ""
    is_split = None
    is_merge = False
    ytdl_format = None
    ask_quality = False
    sample_video = 0
    screenshots = 0
    custom_caption = ""
    thumb_url = ""
    upload_target = None

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "-n" and i + 1 < len(tokens):
            custom_name = tokens[i + 1]
            i += 2
        elif tok in ["-up", "-target"] and i + 1 < len(tokens):
            upload_target = tokens[i + 1].lower()
            i += 2
        elif tok in ["-gofile", "-gf"]:
            upload_target = "gofile"
            i += 1
        elif tok in ["-pixeldrain", "-pd"]:
            upload_target = "pixeldrain"
            i += 1
        elif tok in ["-tg", "-telegram"]:
            upload_target = "telegram"
            i += 1
        elif tok == "-all":
            upload_target = "all"
            i += 1
        elif tok == "-doc":
            stream_upload = False
            i += 1
        elif tok == "-med":
            stream_upload = True
            i += 1
        elif tok == "-z":
            mode_type = "zip"
            i += 1
        elif tok == "-e":
            mode_type = "unzip"
            i += 1
        elif tok == "-p" and i + 1 < len(tokens):
            password = tokens[i + 1]
            i += 2
        elif tok in ["-m", "-merge"]:
            is_merge = True
            i += 1
        elif tok in ["-ss", "-sample"] and i + 1 < len(tokens) and tokens[i + 1].isdigit():
            sample_video = int(tokens[i + 1])
            i += 2
        elif tok in ["-shots", "-sshot"] and i + 1 < len(tokens) and tokens[i + 1].isdigit():
            screenshots = int(tokens[i + 1])
            i += 2
        elif tok == "-c" and i + 1 < len(tokens):
            cap_parts = []
            i += 1
            while i < len(tokens) and not tokens[i].startswith("-"):
                cap_parts.append(tokens[i])
                i += 1
            custom_caption = " ".join(cap_parts)
        elif tok == "-thumb" and i + 1 < len(tokens) and tokens[i + 1].startswith(("http://", "https://")):
            thumb_url = tokens[i + 1]
            i += 2
        elif tok in ["-s", "-q"]:
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("-") and not tokens[i + 1].startswith(("http://", "https://", "/")):
                val = tokens[i + 1].lower().rstrip("p")
                if val in ["1080", "720", "480", "360"]:
                    ytdl_format = f"bv*[height<={val}]+ba/b[height<={val}]"
                elif val in ["audio", "mp3"]:
                    ytdl_format = "mp3"
                elif val == "best":
                    ytdl_format = "bv*+ba/b"
                else:
                    ytdl_format = tokens[i + 1]
                i += 2
            else:
                ask_quality = True
                i += 1
        elif tok.startswith(("http://", "https://", "tg://", "/content/", "/home/", "magnet:")):
            links.append(tok)
            i += 1
        else:
            # Check if token contains one or multiple embedded URLs
            embedded = re.findall(r"https?://[^\s<>'\"]+|magnet:\?[^\s]+|/content/[^\s]+|/home/[^\s]+", tok)
            if embedded:
                links.extend(embedded)
            i += 1

    if len(lines) > 1:
        for line in lines[1:]:
            line_str = line.strip()
            if line_str.startswith("[") and line_str.endswith("]"):
                custom_name = line_str[1:-1]
            elif line_str.startswith("{") and line_str.endswith("}"):
                password = line_str[1:-1]
                mode_type = "zip"
            elif line_str.startswith("(") and line_str.endswith(")"):
                password = line_str[1:-1]
                mode_type = "unzip"
            else:
                embedded = re.findall(r"https?://[^\s<>'\"]+|magnet:\?[^\s]+|/content/[^\s]+|/home/[^\s]+", line_str)
                if embedded:
                    links.extend(embedded)

    if reply_message:
        source_text = (reply_message.text or "") + " " + (reply_message.caption or "")
        if source_text.strip():
            found_urls = re.findall(r"https?://[^\s<>'\"]+|magnet:\?[^\s]+|/content/[^\s]+|/home/[^\s]+", source_text)
            if found_urls:
                links.extend(found_urls)

        media = (
            reply_message.document
            or reply_message.video
            or reply_message.audio
            or reply_message.photo
        )
        if media and not links:
            chat_id = reply_message.chat.id
            msg_id = reply_message.id
            if str(chat_id).startswith("-100"):
                tg_link = f"https://t.me/c/{str(chat_id)[4:]}/{msg_id}"
            elif getattr(reply_message.chat, "username", None):
                tg_link = f"https://t.me/{reply_message.chat.username}/{msg_id}"
            else:
                tg_link = f"https://t.me/c/{abs(chat_id)}/{msg_id}"
            links.append(tg_link)

    # Deduplicate links preserving order
    clean_links = []
    seen = set()
    for lk in links:
        if lk not in seen:
            seen.add(lk)
            clean_links.append(lk)

    return (
        clean_links,
        custom_name,
        stream_upload,
        mode_type,
        password,
        is_split,
        is_merge,
        ytdl_format,
        ask_quality,
        sample_video,
        screenshots,
        custom_caption,
        thumb_url,
        upload_target,
    )


@colab_bot.on_message(filters.command(["start", "help", "h"]))
async def start_and_help(client, message):
    try:
        await message.delete()
    except Exception:
        pass

    u_id = message.from_user.id if message.from_user else message.chat.id
    u_name = message.from_user.first_name if message.from_user else "User"
    is_owner = (OWNER == 0) or (u_id == OWNER)
    is_perm = is_owner or SettingsManager.is_user_permitted(u_id, OWNER)
    user_tier = "👑 Owner / Admin" if is_owner else ("🌟 Permitted (VIP Personal Access)" if is_perm else "👤 Free User (Group Access Only)")

    u_conf = SettingsManager.get_user_settings(u_id)
    split_size = f"{u_conf.get('split_size_mb', 1950)} MB"
    dump_target = u_conf.get("dump_channel") or ("Bot DM (Private)" if u_conf.get("send_to_dm", True) else "Group Chat")

    text = (
        f"<b>⚡ Welcome to TGColabX 🚀</b>\n"
        f"<i>High-Performance Multi-Task Telegram Leecher & Cloud Mirror</i>\n\n"
        f"╭⌬ <b>User       :</b> <b>{u_name}</b> (<code>{u_id}</code>)\n"
        f"├⌬ <b>Tier       :</b> <i>{user_tier}</i>\n"
        f"├⌬ <b>Split Limit:</b> <code>{split_size}</code>\n"
        f"├⌬ <b>Delivery   :</b> <code>{dump_target}</code>\n"
        f"├⌬ <b>Engine     :</b> <i>DzGram + Aria2c + yt-dlp</i>\n"
        f"╰⌬ <b>Multi-DL   :</b> <i>True Parallel Multi-Download Active</i>\n\n"
        f"<blockquote><b>🌟 Based on: WZML-X, XronTrix10 & DZGram | Developed by: MyKurumiChan</b></blockquote>\n\n"
        f"⌬ <b><u>Task Commands</u></b>\n"
        f"├ <code>/leech</code> [links] [flags] : Concurrent Leech to Telegram\n"
        f"├ <code>/mirror</code> [links] [flags] : Mirror to Google Drive / Cloud\n"
        f"├ <code>/ytdl</code> [links] [flags] : Download video or audio via yt-dlp\n"
        f"├ <code>/merge</code> [links] : Automated video & audio merge\n"
        f"├ <code>/sample</code> [duration_s] : Generate sample preview video\n"
        f"├ <code>/sshot</code> [count] : Generate video screenshots\n"
        f"├ <code>/mediainfo</code> : Inspect video/audio file specs\n"
        f"├ <code>/status</code> : Live single-window download dashboard\n"
        f"├ <code>/usetting</code> : Open personal User Settings menu\n"
        f"├ <code>/cookies</code> : Upload your yt-dlp cookies.txt\n"
        f"├ <code>/cancel &lt;id&gt;</code> : Stop a specific task\n"
        f"├ <code>/cancelall</code> : Cancel all active tasks\n"
        f"╰ <code>/restart</code> : Clean cache and restart bot engine\n\n"
        f"⌬ <b><u>Supported Flags</u></b>\n"
        f"├ <code>-n &lt;name&gt;</code> : Custom output filename\n"
        f"├ <code>-gofile</code> / <code>-gf</code> : Upload to Gofile.io (Fast Cloud)\n"
        f"├ <code>-pixeldrain</code> / <code>-pd</code> : Upload to Pixeldrain API\n"
        f"├ <code>-all</code> : Upload to Telegram + Gofile + Pixeldrain\n"
        f"├ <code>-med</code> / <code>-doc</code> : Video stream mode or Document file\n"
        f"├ <code>-z</code> / <code>-e</code> : Zip or Unzip mode\n"
        f"├ <code>-p &lt;pass&gt;</code> : Password for archive extraction\n"
        f"├ <code>-s [res]</code> : yt-dlp quality (1080, 720, 480, 360, best, mp3)\n"
        f"├ <code>-ss &lt;sec&gt;</code> : Sample video duration\n"
        f"├ <code>-shots &lt;n&gt;</code> : Number of screenshots\n"
        f"├ <code>-c &lt;text&gt;</code> : Custom Telegram message caption\n"
        f"╰ <code>-thumb &lt;url&gt;</code> : Custom video thumbnail from URL\n\n"
        f"<i>Tip: In groups, completed files are automatically delivered to your private Bot DM to prevent flooding!</i>"
    )
    keyboard_menu = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👤 User Settings", callback_data=f"open_uset_{u_id}"),
                InlineKeyboardButton("🤖 Bot Settings", callback_data="open_bset"),
            ],
            [
                InlineKeyboardButton("♻️ Live Dashboard", callback_data="ref"),
                InlineKeyboardButton("⚡ Speedtest", callback_data="bset_speedtest"),
            ],
            [
                InlineKeyboardButton("❌ Close", callback_data="uset_close"),
            ],
        ]
    )
    try:
        await message.reply_text(text, reply_markup=keyboard_menu)
    except Exception:
        await colab_bot.send_message(chat_id=message.chat.id, text=text, reply_markup=keyboard_menu)


def check_access(message) -> tuple:
    u_id = message.from_user.id if message.from_user else message.chat.id
    chat_type = str(message.chat.type).lower()
    is_pm = ("private" in chat_type) or (message.chat.id > 0)
    is_owner = (OWNER == 0) or (u_id == OWNER)
    is_permitted = is_owner or SettingsManager.is_user_permitted(u_id, OWNER)

    # 1. PM Restriction: Free users can only use bot in groups, permitted users can use in PM
    if is_pm and not is_permitted:
        return False, (
            "⚠️ <b>Access Restricted: Personal Chat (PM)</b>\n\n"
            "<i>Free users can only use TGColabX inside authorized groups!</i>\n"
            "<blockquote>Please send your download links in our group. Permitted users can use bot in personal chat.</blockquote>"
        )

    # 2. Group restriction (if authorized_chats is configured)
    if not is_pm:
        if not is_owner and not SettingsManager.is_chat_authorized(message.chat.id):
            return False, (
                "⚠️ <b>This group is not authorized to use TGColabX!</b>\n"
                "<i>Please ask the bot owner to authorize this group.</i>"
            )

    return True, ""


@colab_bot.on_message(filters.command(["leech", "l", "tupload"]))
async def telegram_upload(client, message):
    global src_request_msg

    allowed, reason = check_access(message)
    if not allowed:
        await message.reply_text(reason)
        return

    (
        links,
        custom_name,
        stream_upload,
        mode_type,
        password,
        is_split,
        is_merge,
        _,
        _,
        sample_video,
        screenshots,
        custom_caption,
        thumb_url,
        upload_target,
    ) = parse_flags_and_links(message.text, message.reply_to_message)
    user_name = message.from_user.first_name if message.from_user else "Owner"

    for lk in links:
        if is_torrent_or_magnet(lk):
            await message.reply_text(
                "⚠️ <b>Torrent / Magnet links are strictly prohibited</b> by Google Colab policies. Task aborted."
            )
            return

    if links:
        if thumb_url:
            download_thumbnail_from_url(thumb_url, user_id=message.chat.id)

        options = {
            "custom_name": custom_name,
            "stream_upload": stream_upload,
            "is_split": is_split,
            "is_merge": is_merge,
            "sample_video": sample_video,
            "screenshots": screenshots,
            "custom_caption": custom_caption,
            "zip_pswd": password,
            "unzip_pswd": password,
            "upload_target": upload_target,
        }

        await dispatch_task(
            mode_type=mode_type,
            mode="leech",
            is_ytdl=False,
            links=links,
            user_name=user_name,
            chat_id=message.chat.id,
            options=options,
            message=message,
        )
    else:
        text = (
            "<b>⚡ Send DOWNLOAD LINK(s) to Leech 🔗»</b>\n\n"
            "🦀 Examples with flags:\n"
            "<code>/leech https://link1.mp4 https://link2.mp4</code>\n"
            "<code>/leech https://file.zip -e -n MyFolder</code>\n\n"
            "Or reply to any file/link with <code>/leech</code>!\n"
            "<i>(Multiple links will be downloaded simultaneously in parallel!)</i>"
        )
        src_request_msg = await task_starter(message, text)


@colab_bot.on_message(filters.command(["mirror", "m", "gdupload"]))
async def drive_upload(client, message):
    global src_request_msg

    allowed, reason = check_access(message)
    if not allowed:
        await message.reply_text(reason)
        return

    (
        links,
        custom_name,
        _,
        mode_type,
        password,
        _,
        is_merge,
        _,
        _,
        _,
        _,
        _,
        _,
        upload_target,
    ) = parse_flags_and_links(message.text, message.reply_to_message)
    user_name = message.from_user.first_name if message.from_user else "Owner"

    for lk in links:
        if is_torrent_or_magnet(lk):
            await message.reply_text(
                "⚠️ <b>Torrent / Magnet links are strictly prohibited</b> by Google Colab policies. Task aborted."
            )
            return

    if links:
        options = {
            "custom_name": custom_name,
            "is_merge": is_merge,
            "zip_pswd": password,
            "unzip_pswd": password,
            "upload_target": upload_target,
        }

        await dispatch_task(
            mode_type=mode_type,
            mode="mirror",
            is_ytdl=False,
            links=links,
            user_name=user_name,
            chat_id=message.chat.id,
            options=options,
            message=message,
        )
    else:
        text = (
            "<b>⚡ Send DOWNLOAD LINK(s) to Mirror to Drive 🔗»</b>\n\n"
            "🦀 Example:\n"
            "<code>/mirror https://linktofile.zip -e</code>\n\n"
            "Or reply directly to any link/file with <code>/mirror</code>!"
        )
        src_request_msg = await task_starter(message, text)


@colab_bot.on_message(filters.command(["ytdl", "y", "ytupload"]))
async def yt_upload(client, message):
    global src_request_msg

    allowed, reason = check_access(message)
    if not allowed:
        await message.reply_text(reason)
        return

    (
        links,
        custom_name,
        stream_upload,
        mode_type,
        password,
        is_split,
        is_merge,
        ytdl_format,
        ask_quality,
        sample_video,
        screenshots,
        custom_caption,
        thumb_url,
        upload_target,
    ) = parse_flags_and_links(message.text, message.reply_to_message)
    user_name = message.from_user.first_name if message.from_user else "Owner"

    if links:
        if thumb_url:
            download_thumbnail_from_url(thumb_url, user_id=message.chat.id)

        options = {
            "custom_name": custom_name,
            "stream_upload": stream_upload,
            "is_split": is_split,
            "is_merge": is_merge,
            "ytdl_format": ytdl_format,
            "sample_video": sample_video,
            "screenshots": screenshots,
            "custom_caption": custom_caption,
            "zip_pswd": password,
            "upload_target": upload_target,
        }

        if ask_quality:
            req_id = f"{int(time() * 1000) % 1000000:06d}"
            PENDING_QUALITY_REQUESTS[req_id] = {
                "links": links,
                "user_name": user_name,
                "chat_id": message.chat.id,
                "options": options,
                "mode_type": mode_type,
            }
            await message.reply_text(
                "🎬 <b>Select yt-dlp Video Quality / Format:</b>",
                reply_markup=quality_buttons(req_id),
            )
        else:
            # Check user default preference if not specified
            if not ytdl_format:
                u_conf = SettingsManager.get_user_settings(message.chat.id)
                preferred = u_conf.get("ytdl_quality", "Best")
                if preferred == "1080p":
                    options["ytdl_format"] = "bv*[height<=1080]+ba/b[height<=1080]"
                elif preferred == "720p":
                    options["ytdl_format"] = "bv*[height<=720]+ba/b[height<=720]"
                elif preferred == "480p":
                    options["ytdl_format"] = "bv*[height<=480]+ba/b[height<=480]"
                elif preferred == "360p":
                    options["ytdl_format"] = "bv*[height<=360]+ba/b[height<=360]"
                elif preferred == "Audio MP3":
                    options["ytdl_format"] = "mp3"
                else:
                    options["ytdl_format"] = "bv*+ba/b"

            await dispatch_task(
                mode_type=mode_type,
                mode="leech",
                is_ytdl=True,
                links=links,
                user_name=user_name,
                chat_id=message.chat.id,
                options=options,
                message=message,
            )
    else:
        text = (
            "<b>⚡ Send YTDL DOWNLOAD LINK(s) 🔗»</b>\n\n"
            "🦀 Examples:\n"
            "<code>/ytdl https://youtube.com/watch?v=... -s 1080</code>\n"
            "<code>/ytdl https://youtube.com/watch?v=... -s mp3</code>\n"
            "<code>/ytdl https://youtube.com/watch?v=... -s</code> (Quality Menu)"
        )
        src_request_msg = await task_starter(message, text)


@colab_bot.on_message(filters.command(["merge", "mrg"]))
async def merge_upload(client, message):
    global src_request_msg

    allowed, reason = check_access(message)
    if not allowed:
        await message.reply_text(reason)
        return

    (
        links,
        custom_name,
        stream_upload,
        mode_type,
        password,
        is_split,
        _,
        _,
        _,
        sample_video,
        screenshots,
        custom_caption,
        _,
        upload_target,
    ) = parse_flags_and_links(message.text, message.reply_to_message)
    user_name = message.from_user.first_name if message.from_user else "Owner"

    if links:
        options = {
            "custom_name": custom_name,
            "stream_upload": stream_upload,
            "is_split": is_split,
            "is_merge": True,
            "sample_video": sample_video,
            "screenshots": screenshots,
            "custom_caption": custom_caption,
            "zip_pswd": password,
            "upload_target": upload_target,
        }

        await dispatch_task(
            mode_type=mode_type,
            mode="leech",
            is_ytdl=False,
            links=links,
            user_name=user_name,
            chat_id=message.chat.id,
            options=options,
            message=message,
        )
    else:
        text = (
            "<b>🎬 Automated Merge Mode:</b>\n\n"
            "Send multiple video links or parts to download and merge into a single video!\n"
            "Example:\n<code>/merge https://link1.mp4 https://link2.mp4 -n FullMovie.mp4</code>"
        )
        src_request_msg = await task_starter(message, text)


@colab_bot.on_message(filters.command(["sample", "smp"]))
async def sample_command(client, message):
    allowed, reason = check_access(message)
    if not allowed:
        await message.reply_text(reason)
        return

    duration = 30
    args = message.text.split()
    for a in args[1:]:
        if a.isdigit():
            duration = int(a)

    links, _, _, mode_type, *rest = parse_flags_and_links(message.text, message.reply_to_message)
    if not links:
        await message.reply_text("<i>Send a video link or reply to a video message with <code>/sample [seconds]</code>!</i>")
        return

    user_name = message.from_user.first_name if message.from_user else "Owner"
    options = {"sample_video": duration}
    await dispatch_task(mode_type, "leech", False, links, user_name, message.chat.id, options, message)


@colab_bot.on_message(filters.command(["screenshot", "sshot", "ss"]))
async def screenshot_command(client, message):
    allowed, reason = check_access(message)
    if not allowed:
        await message.reply_text(reason)
        return

    shots_count = 5
    args = message.text.split()
    for a in args[1:]:
        if a.isdigit():
            shots_count = min(10, int(a))

    links, _, _, mode_type, *rest = parse_flags_and_links(message.text, message.reply_to_message)
    if not links:
        await message.reply_text("<i>Send a video link or reply to a video message with <code>/sshot [count]</code>!</i>")
        return

    user_name = message.from_user.first_name if message.from_user else "Owner"
    options = {"screenshots": shots_count}
    await dispatch_task(mode_type, "leech", False, links, user_name, message.chat.id, options, message)


@colab_bot.on_message(filters.command(["mediainfo", "mi"]))
async def mediainfo_command(client, message):
    reply = message.reply_to_message
    if reply and (reply.video or reply.document or reply.audio):
        stat_msg = await message.reply_text("<i>Downloading sample to inspect MediaInfo...</i>")
        try:
            os.makedirs(Paths.WORK_PATH, exist_ok=True)
            dl_path = os.path.join(Paths.WORK_PATH, "mi_temp_file")
            if os.path.exists(dl_path):
                os.remove(dl_path)
            await reply.download(file_name=dl_path)
            info_text = get_media_info_text(dl_path)
            if os.path.exists(dl_path):
                os.remove(dl_path)
            await stat_msg.edit_text(info_text, disable_web_page_preview=True)
        except Exception as e:
            await stat_msg.edit_text(f"⚠️ <b>MediaInfo error:</b> <code>{e}</code>")
    else:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1 and os.path.exists(parts[1].strip()):
            info_text = get_media_info_text(parts[1].strip())
            await message.reply_text(info_text, disable_web_page_preview=True)
        else:
            await message.reply_text(
                "<i>Reply to a video, audio, or document file with <code>/mediainfo</code> to view its full technical specs!</i>"
            )


@colab_bot.on_message(filters.command(["status", "s"]))
async def status_command(client, message):
    try:
        await message.delete()
    except Exception:
        pass

    if ACTIVE_TASKS:
        multi_text = render_multi_status(ACTIVE_TASKS)
        old_stat = CHAT_STATUS_MSGS.get(message.chat.id)
        if old_stat:
            try:
                await old_stat.delete()
            except Exception:
                pass
        stat_msg = await colab_bot.send_message(
            chat_id=message.chat.id,
            text=multi_text,
            reply_markup=keyboard(),
            disable_web_page_preview=True,
        )
        CHAT_STATUS_MSGS[message.chat.id] = stat_msg
        for t_ctx in ACTIVE_TASKS.values():
            if t_ctx.chat_id == message.chat.id:
                t_ctx.status_msg = stat_msg
    elif BOT.State.task_going and MSG.status_msg:
        try:
            await colab_bot.send_message(chat_id=message.chat.id, text="<i>Task is currently running! Check status card above.</i>")
        except Exception:
            pass
    else:
        egg = random.choice(EASTER_EGGS)
        free_space = sizeUnit(psutil.disk_usage("/").free)
        uptime_str = getTime(int(time() - bot_start_time))
        ram = psutil.virtual_memory()

        msg_text = f"""{egg}

⌬ <b><u>Bot Stats</u></b>
<blockquote>╭ <b>CPU</b>  → {psutil.cpu_percent()}%
┊ <b>RAM</b>  → {ram.percent}% ({sizeUnit(ram.used)})
┊ <b>Free</b> → {free_space}
╰ <b>UP</b>   → {uptime_str}</blockquote>"""
        await colab_bot.send_message(chat_id=message.chat.id, text=msg_text)


# ==================== User & Group Authorization (Owner Commands) ====================

@colab_bot.on_message(filters.command(["authorize", "auth"]))
async def authorize_user_command(client, message):
    try:
        await message.delete()
    except Exception:
        pass
    u_id = message.from_user.id if message.from_user else message.chat.id
    if OWNER and u_id != OWNER:
        await message.reply_text("⚠️ Only the bot owner can authorize users!")
        return
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) > 1 and parts[1].strip().isdigit():
        target_uid = int(parts[1].strip())
        SettingsManager.add_permitted_user(target_uid)
        await colab_bot.send_message(
            chat_id=message.chat.id,
            text=f"✅ User <code>{target_uid}</code> is now a <b>Permitted User</b> (Authorized for PM access)!"
        )
    elif message.reply_to_message and message.reply_to_message.from_user:
        target_uid = message.reply_to_message.from_user.id
        SettingsManager.add_permitted_user(target_uid)
        await colab_bot.send_message(
            chat_id=message.chat.id,
            text=f"✅ User <code>{target_uid}</code> ({message.reply_to_message.from_user.first_name}) is now a <b>Permitted User</b>!"
        )
    else:
        await colab_bot.send_message(
            chat_id=message.chat.id,
            text="<i>Usage: <code>/auth <user_id></code> or reply to user message with <code>/auth</code></i>"
        )


@colab_bot.on_message(filters.command(["unauthorize", "unauth"]))
async def unauthorize_user_command(client, message):
    try:
        await message.delete()
    except Exception:
        pass
    u_id = message.from_user.id if message.from_user else message.chat.id
    if OWNER and u_id != OWNER:
        await message.reply_text("⚠️ Only the bot owner can unauthorize users!")
        return
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) > 1 and parts[1].strip().isdigit():
        target_uid = int(parts[1].strip())
        SettingsManager.remove_permitted_user(target_uid)
        await colab_bot.send_message(
            chat_id=message.chat.id,
            text=f"🚫 User <code>{target_uid}</code> removed from Permitted Users."
        )
    elif message.reply_to_message and message.reply_to_message.from_user:
        target_uid = message.reply_to_message.from_user.id
        SettingsManager.remove_permitted_user(target_uid)
        await colab_bot.send_message(
            chat_id=message.chat.id,
            text=f"🚫 User <code>{target_uid}</code> removed from Permitted Users."
        )
    else:
        await colab_bot.send_message(
            chat_id=message.chat.id,
            text="<i>Usage: <code>/unauth <user_id></code></i>"
        )


@colab_bot.on_message(filters.command(["authusers", "permitted"]))
async def list_permitted_users(client, message):
    users = SettingsManager.get_permitted_users()
    u_list = "\n".join([f"• <code>{u}</code>" for u in users]) if users else "<i>No extra permitted users (Only Owner).</i>"
    await message.reply_text(f"👑 <b><u>Permitted Users (Personal Chat PM Access)</u></b>\n\n{u_list}")


@colab_bot.on_message(filters.command(["authgroup"]))
async def authorize_group_command(client, message):
    try:
        await message.delete()
    except Exception:
        pass
    u_id = message.from_user.id if message.from_user else message.chat.id
    if OWNER and u_id != OWNER:
        await message.reply_text("⚠️ Only the bot owner can authorize groups!")
        return
    if message.chat.id > 0:
        await message.reply_text("⚠️ Run this command inside the group you wish to authorize!")
        return
    SettingsManager.add_authorized_chat(message.chat.id)
    await colab_bot.send_message(
        chat_id=message.chat.id,
        text=f"✅ Group <b>{message.chat.title}</b> (<code>{message.chat.id}</code>) is now authorized to use TGColabX!"
    )


@colab_bot.on_message(filters.command(["unauthgroup"]))
async def unauthorize_group_command(client, message):
    try:
        await message.delete()
    except Exception:
        pass
    u_id = message.from_user.id if message.from_user else message.chat.id
    if OWNER and u_id != OWNER:
        await message.reply_text("⚠️ Only the bot owner can unauthorize groups!")
        return
    if message.chat.id > 0:
        await message.reply_text("⚠️ Run this command inside the group you wish to unauthorize!")
        return
    SettingsManager.remove_authorized_chat(message.chat.id)
    await colab_bot.send_message(
        chat_id=message.chat.id,
        text=f"🚫 Group <b>{message.chat.title}</b> removed from authorized groups."
    )


@colab_bot.on_message(filters.command(["usersettings", "usetting", "usettings", "uset"]))
async def user_settings_command(client, message):
    u_id = message.from_user.id if message.from_user else message.chat.id
    u_name = message.from_user.first_name if message.from_user else "User"
    text = get_user_settings_text(u_id, u_name)
    markup = get_user_settings_markup(u_id)
    await message.reply_text(text, reply_markup=markup, disable_web_page_preview=True)


@colab_bot.on_message(filters.command(["botsettings", "bsetting", "bsettings", "bset"]))
async def bot_settings_command(client, message):
    is_owner = (OWNER == 0) or (message.chat.id == OWNER) or (message.from_user and message.from_user.id == OWNER)
    if not is_owner:
        await message.reply_text("⚠️ <i>Only the bot owner can access Bot Settings. Use <code>/usersettings</code> for your preferences!</i>")
        return
    text = get_bot_settings_text(active_count=len(ACTIVE_TASKS))
    markup = get_bot_settings_markup()
    await message.reply_text(text, reply_markup=markup, disable_web_page_preview=True)


@colab_bot.on_message(filters.command("settings"))
async def combined_settings_command(client, message):
    is_owner = (OWNER == 0) or (message.chat.id == OWNER) or (message.from_user and message.from_user.id == OWNER)
    u_id = message.from_user.id if message.from_user else message.chat.id
    buttons = [
        [InlineKeyboardButton("👤 User Settings", callback_data=f"open_uset_{u_id}")],
    ]
    if is_owner:
        buttons.append([InlineKeyboardButton("🤖 Bot Settings (Admin)", callback_data="open_bset")])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="uset_close")])

    text = "⚙️ <b><i>TGColabX Settings Panel</i></b>\nSelect which settings menu you would like to open:"
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


@colab_bot.on_message(filters.command(["stats", "st"]))
async def stats_command(client, message):
    cpu = psutil.cpu_percent()
    cpu_cores = psutil.cpu_count(logical=True)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    uptime_str = getTime(int(time() - bot_start_time))

    text = f"""⌬ <b><i>𝗦𝗬𝗦𝗧𝗘𝗠 𝗦𝗧𝗔𝗧𝗜𝗦𝗧𝗜𝗖𝗦</i></b>
<blockquote>╭ <code>OS       :</code> {platform.system()} {platform.release()}
┊ <code>Python   :</code> {sys.version.split()[0]}
┊ <code>CPU      :</code> {cpu}% ({cpu_cores} Cores)
┊ <code>RAM      :</code> {ram.percent}% ({sizeUnit(ram.used)} / {sizeUnit(ram.total)})
┊ <code>Disk     :</code> {disk.percent}% ({sizeUnit(disk.used)} / {sizeUnit(disk.total)})
┊ <code>DiskFree :</code> {sizeUnit(disk.free)}
╰ <code>Uptime   :</code> {uptime_str}</blockquote>"""
    await message.reply_text(text)


@colab_bot.on_message(filters.command("ping"))
async def ping_command(client, message):
    start = time()
    reply = await message.reply_text("<i>Pinging...</i>")
    delta = (time() - start) * 1000
    await reply.edit_text(f"🏓 <b>Pong!</b> <code>{delta:.2f} ms</code>")


@colab_bot.on_message(filters.command(["speedtest", "stest"]))
async def speedtest_command(client, message):
    reply = await message.reply_text("<i>⚡ Running Speedtest on Colab... Please wait!</i>")
    try:
        cmd = "speedtest-cli --json"
        out = subprocess.check_output(cmd, shell=True).decode()
        data = json.loads(out)
        up = sizeUnit(data.get("upload", 0) / 8) + "/s"
        dl = sizeUnit(data.get("download", 0) / 8) + "/s"
        ping_val = data.get("ping", "N/A")
        server_info = data.get("server", {})
        s_name = server_info.get("name", "N/A")
        s_country = server_info.get("country", "N/A")

        text = f"""➲ <b><i>SPEEDTEST INFO</i></b>
<blockquote>╭ <b>Upload   :</b> <code>{up}</code>
┊ <b>Download :</b> <code>{dl}</code>
┊ <b>Ping     :</b> <code>{ping_val} ms</code>
╰ <b>Server   :</b> <code>{s_name}, {s_country}</code></blockquote>"""
        await reply.edit_text(text)
    except Exception as e:
        await reply.edit_text(f"⚠️ <b>Speedtest error:</b> <code>{e}</code>")


@colab_bot.on_message(filters.command(["shell", "sh"]))
async def shell_command(client, message):
    is_owner = (OWNER == 0) or (message.chat.id == OWNER) or (message.from_user and message.from_user.id == OWNER)
    if not is_owner:
        await message.reply_text("⚠️ <i>Only bot owner can run shell commands.</i>")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) == 1:
        await message.reply_text("<i>Send command to execute: <code>/shell &lt;cmd&gt;</code></i>")
        return

    cmd = parts[1]
    wait_msg = await message.reply_text("<i>Executing shell command...</i>")
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        output = ""
        if stdout:
            output += f"<b>Stdout:</b>\n<code>{stdout}</code>\n"
        if stderr:
            output += f"<b>Stderr:</b>\n<code>{stderr}</code>\n"
        if not output:
            output = "<i>Command executed with no output.</i>"

        if len(output) > 4000:
            with BytesIO(output.encode("utf-8")) as out_f:
                out_f.name = "shell_output.txt"
                await message.reply_document(out_f, caption=f"<code>{cmd}</code>")
            await wait_msg.delete()
        else:
            await wait_msg.edit_text(output)
    except Exception as e:
        await wait_msg.edit_text(f"⚠️ <b>Execution error:</b> <code>{e}</code>")


@colab_bot.on_message(filters.command(["restart", "r"]))
async def restart_command(client, message):
    is_owner = (OWNER == 0) or (message.chat.id == OWNER) or (message.from_user and message.from_user.id == OWNER)
    if is_owner:
        msg = await message.reply_text("<i>Cleaning temporary data and resetting bot...</i>")
        try:
            if os.path.exists(Paths.WORK_PATH):
                shutil.rmtree(Paths.WORK_PATH)
        except Exception:
            pass
        try:
            subprocess.run("pkill -9 -f 'aria2c|ffmpeg|ffprobe'", shell=True)
        except Exception:
            pass
        ACTIVE_TASKS.clear()
        BOT.Queue.clear()
        BOT.State.task_going = False
        await msg.edit_text("✅ <b>TGColabX reset complete and ready for new tasks!</b>")
    else:
        await message.reply_text("⚠️ <i>Only bot owner can restart the bot.</i>")


@colab_bot.on_message(filters.command(["cancel", "c"]))
async def cancel_command(client, message):
    parts = message.text.split(maxsplit=1)
    target_id = parts[1].strip().lstrip("_") if len(parts) > 1 else None

    if target_id and target_id in ACTIVE_TASKS:
        await cancelTask("Task Cancelled by User Command!", task_id=target_id)
        await message.reply_text(f"🛑 <b>Task #{target_id} cancelled!</b>")
    elif ACTIVE_TASKS:
        t_id, _ = next(iter(ACTIVE_TASKS.items()))
        await cancelTask("Task Cancelled by User Command!", task_id=t_id)
        rem = len(ACTIVE_TASKS)
        await message.reply_text(f"🛑 <b>Task #{t_id} cancelled!</b> ({rem} tasks still running)")
    elif BOT.State.task_going:
        await cancelTask("Task Cancelled by User Command!")
        await message.reply_text("🛑 <b>Active task cancelled!</b>")
    else:
        await message.reply_text("<i>No active task to cancel.</i>")


@colab_bot.on_message(filters.regex(r"^/cancel_(\w+)"))
async def cancel_by_regex(client, message):
    match = re.search(r"^/cancel_(\w+)", message.text)
    if match:
        t_id = match.group(1)
        if t_id in ACTIVE_TASKS:
            await cancelTask("Task Cancelled by User Command!", task_id=t_id)
            await message.reply_text(f"🛑 <b>Task #{t_id} cancelled!</b>")
        else:
            await message.reply_text(f"<i>Task #{t_id} is not currently running.</i>")


@colab_bot.on_message(filters.command(["cancelall", "call"]))
async def cancel_all_command(client, message):
    BOT.Queue.clear()
    await cancelTask("All Tasks Cancelled by User Command!", cancel_all=True)
    await message.reply_text("🛑 <b>All active and queued tasks have been cancelled!</b>")


@colab_bot.on_message(filters.photo & filters.private)
async def handle_image(client, message):
    u_id = message.from_user.id if message.from_user else message.chat.id
    msg = await message.reply_text("<i>Saving custom thumbnail...</i>")
    success = await setThumbnail(message, user_id=u_id)
    if success:
        await msg.edit_text("<b>Thumbnail Successfully Changed ✅</b>\n<i>Saved for your personal uploads!</i>")
    else:
        await msg.edit_text("🥲 <b>Couldn't Set Thumbnail, Please Try Again!</b>", quote=True)


@colab_bot.on_message(filters.document & filters.private)
async def handle_document_upload(client, message):
    """Handles cookies.txt documents sent directly by user."""
    doc = message.document
    if not doc:
        return
    u_id = message.from_user.id if message.from_user else message.chat.id
    fname = (doc.file_name or "").lower()

    if fname.endswith(".txt") or "cookie" in fname:
        status_msg = await message.reply_text("<i>Processing cookies file...</i>")
        temp_dir = os.path.join(Paths.WORK_PATH, "temp_cookies")
        os.makedirs(temp_dir, exist_ok=True)
        temp_file = os.path.join(temp_dir, f"temp_{u_id}_{doc.file_name}")
        try:
            await message.download(file_name=temp_file)
            saved = SettingsManager.save_cookies(u_id, temp_file)
            if os.path.exists(temp_file):
                os.remove(temp_file)
            if saved:
                await status_msg.edit_text(
                    "🍪 <b>Cookies Successfully Saved!</b> ✅\n"
                    "<i>Your personal cookies.txt is now active for all yt-dlp downloads!</i>\n"
                    "<blockquote>To remove your cookies anytime, use <code>/delcookies</code> or User Settings.</blockquote>"
                )
            else:
                await status_msg.edit_text("⚠️ <b>Invalid cookies format!</b>\n<i>Please ensure it is a valid Netscape cookies.txt file.</i>")
        except Exception as e:
            await status_msg.edit_text(f"⚠️ <b>Error saving cookies:</b> <code>{e}</code>")


@colab_bot.on_message(filters.command(["cookies", "cookie"]))
async def cookies_command(client, message):
    u_id = message.from_user.id if message.from_user else message.chat.id
    reply = message.reply_to_message
    if reply and reply.document:
        doc = reply.document
        fname = (doc.file_name or "").lower()
        if fname.endswith(".txt") or "cookie" in fname:
            status_msg = await message.reply_text("<i>Saving cookies from replied document...</i>")
            temp_dir = os.path.join(Paths.WORK_PATH, "temp_cookies")
            os.makedirs(temp_dir, exist_ok=True)
            temp_file = os.path.join(temp_dir, f"temp_{u_id}_{doc.file_name}")
            try:
                await reply.download(file_name=temp_file)
                saved = SettingsManager.save_cookies(u_id, temp_file)
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                if saved:
                    await status_msg.edit_text("🍪 <b>Cookies Successfully Saved!</b> ✅")
                else:
                    await status_msg.edit_text("⚠️ <b>Invalid cookies format!</b>")
            except Exception as e:
                await status_msg.edit_text(f"⚠️ <b>Error saving cookies:</b> <code>{e}</code>")
            return

    has_cookie = SettingsManager.has_cookies(u_id)
    c_status = "Active ✅" if has_cookie else "None ❌"
    text = (
        f"🍪 <b><u>yt-dlp Cookies Management</u></b>\n\n"
        f"╭⌬ <b>Status:</b> <i>{c_status}</i>\n"
        f"╰⌬ <b>Scope :</b> <i>Personal User Account</i>\n\n"
        f"<b>How to add/update your cookies:</b>\n"
        f"1. Export your cookies in Netscape format using any browser extension (e.g. <i>Get cookies.txt LOCALLY</i>).\n"
        f"2. Send or reply to the <code>cookies.txt</code> file here.\n"
        f"3. All your yt-dlp tasks will automatically use your authenticated cookies!\n\n"
        f"<i>To delete your cookies:</i> <code>/delcookies</code>"
    )
    await message.reply_text(text, reply_markup=get_cookie_menu_markup(u_id))


@colab_bot.on_message(filters.command(["delcookies", "delcookie"]))
async def del_cookies_command(client, message):
    u_id = message.from_user.id if message.from_user else message.chat.id
    deleted = SettingsManager.delete_cookies(u_id)
    if deleted:
        await message.reply_text("🍪 <b>Your cookies have been deleted!</b> 🗑️")
    else:
        await message.reply_text("<i>No saved cookies found to delete.</i>")



@colab_bot.on_message(filters.text & filters.private & ~filters.regex(r"^/"))
async def handle_user_text_replies(client, message):
    if not message.text or message.text.startswith("/"):
        return
    u_id = message.from_user.id if message.from_user else message.chat.id
    if u_id not in USER_INPUT_STATES:
        return
    u_name = message.from_user.first_name if message.from_user else "User"
    state = USER_INPUT_STATES.pop(u_id)
    text_val = message.text.strip()

    if state == "set_prefix":
        SettingsManager.set_user_setting(u_id, "prefix", text_val)
        await message.reply_text(f"✅ <b>Prefix updated:</b> <code>{text_val}</code>")
    elif state == "set_suffix":
        SettingsManager.set_user_setting(u_id, "suffix", text_val)
        await message.reply_text(f"✅ <b>Suffix updated:</b> <code>{text_val}</code>")
    elif state == "set_caption":
        SettingsManager.set_user_setting(u_id, "custom_caption", text_val)
        await message.reply_text(f"✅ <b>Custom caption updated:</b>\n<code>{text_val}</code>")
    elif state == "set_gofile":
        SettingsManager.set_user_setting(u_id, "gofile_token", text_val)
        await message.reply_text("✅ <b>Gofile API Token saved successfully!</b>")
    elif state == "set_pixeldrain":
        SettingsManager.set_user_setting(u_id, "pixeldrain_token", text_val)
        await message.reply_text("✅ <b>Pixeldrain API Key saved successfully!</b>")
    elif state == "set_dump_channel":
        SettingsManager.set_user_setting(u_id, "dump_channel", text_val)
        await message.reply_text(f"✅ <b>Custom Dump Channel saved:</b> <code>{text_val}</code>")
    elif state == "set_custom_split":
        try:
            cleaned = text_val.lower().replace("mb", "").replace("m", "").strip()
            if "gb" in cleaned or "g" in cleaned:
                mb_val = int(float(cleaned.replace("gb", "").replace("g", "").strip()) * 1024)
            else:
                mb_val = int(cleaned)
            is_prem = hasattr(colab_bot, "me") and getattr(colab_bot.me, "is_premium", False)
            max_mb = 3900 if is_prem else 1950
            mb_val = max(50, min(mb_val, max_mb))
            SettingsManager.set_user_setting(u_id, "split_size_mb", mb_val)
            disp = f"{mb_val/1024:.1f}GB" if mb_val >= 1024 else f"{mb_val}MB"
            SettingsManager.set_user_setting(u_id, "split_video", disp)
            await message.reply_text(f"✅ <b>Custom Split Size saved:</b> <code>{mb_val} MB</code> (<code>{disp}</code>)")
        except Exception as se:
            await message.reply_text(f"⚠️ Invalid format: <code>{se}</code>. Send a number like <code>1200</code> (in MB).")

    # Re-send updated settings
    s_text = get_user_settings_text(u_id, u_name)
    markup = get_user_settings_markup(u_id)
    await message.reply_text(s_text, reply_markup=markup, disable_web_page_preview=True)


@colab_bot.on_callback_query()
async def handle_all_callbacks(client, callback_query):
    global BOT, MSG, PENDING_QUALITY_REQUESTS, USER_INPUT_STATES
    data = callback_query.data
    u_id = callback_query.from_user.id if callback_query.from_user else callback_query.message.chat.id
    u_name = callback_query.from_user.first_name if callback_query.from_user else "User"

    # Refresh
    if data == "ref":
        if ACTIVE_TASKS:
            multi_text = render_multi_status(ACTIVE_TASKS)
            try:
                await callback_query.message.edit_text(multi_text, reply_markup=keyboard(), disable_web_page_preview=True)
                await callback_query.answer("♻️ Refreshed!", show_alert=False)
            except Exception:
                await callback_query.answer("Already up to date!", show_alert=False)
        else:
            await callback_query.answer("No active downloads running!", show_alert=True)

    # Cancel buttons
    elif data.startswith("cancel_"):
        target_id = data.replace("cancel_", "")
        if target_id == "all":
            await cancelTask("All Tasks Cancelled via button!", cancel_all=True)
            await callback_query.answer("🛑 All tasks stopped!", show_alert=True)
        else:
            await cancelTask(f"Task #{target_id} Cancelled via button!", task_id=target_id)
            await callback_query.answer(f"🛑 Task #{target_id} stopped!", show_alert=True)

    elif data == "cancel":
        await cancelTask("Task Cancelled via button!", cancel_all=False)
        await callback_query.answer("🛑 Task cancelled!", show_alert=False)

    elif data == "clear_queue":
        BOT.Queue.clear()
        await callback_query.answer("🚫 All queued tasks cleared!", show_alert=True)

    # Quality resolution callbacks
    elif data.startswith("qual "):
        parts = data.split()
        val = parts[1]
        req_id = parts[2] if len(parts) > 2 else ""

        if req_id and req_id in PENDING_QUALITY_REQUESTS:
            req = PENDING_QUALITY_REQUESTS.pop(req_id)
            links = req["links"]
            user_name = req["user_name"]
            chat_id = req["chat_id"]
            options = req["options"]
            mode_type = req["mode_type"]
        else:
            links = list(BOT.SOURCE)
            user_name = u_name
            chat_id = callback_query.message.chat.id
            options = {}
            mode_type = "normal"

        if val == "1080":
            options["ytdl_format"] = "bv*[height<=1080]+ba/b[height<=1080]"
            label = "1080p"
        elif val == "720":
            options["ytdl_format"] = "bv*[height<=720]+ba/b[height<=720]"
            label = "720p"
        elif val == "480":
            options["ytdl_format"] = "bv*[height<=480]+ba/b[height<=480]"
            label = "480p"
        elif val == "360":
            options["ytdl_format"] = "bv*[height<=360]+ba/b[height<=360]"
            label = "360p"
        elif val == "mp3":
            options["ytdl_format"] = "mp3"
            label = "Audio MP3"
        else:
            options["ytdl_format"] = "bv*+ba/b"
            label = "Best"

        await callback_query.answer(f"Selected: {label}")
        try:
            await callback_query.message.edit_text(f"🎬 <b>Selected Quality:</b> <code>{label}</code>\n<i>Starting download...</i>")
        except Exception:
            pass

        await dispatch_task(mode_type, "leech", True, links, user_name, chat_id, options, callback_query.message)

    # Settings Navigation
    elif data.startswith("open_uset_"):
        target_uid = int(data.split("_")[-1])
        text = get_user_settings_text(target_uid, u_name)
        markup = get_user_settings_markup(target_uid)
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data == "open_bset":
        is_owner = (OWNER == 0) or (callback_query.message.chat.id == OWNER) or (callback_query.from_user and callback_query.from_user.id == OWNER)
        if not is_owner:
            await callback_query.answer("⚠️ Only the bot owner can access Bot Settings!", show_alert=True)
            return
        text = get_bot_settings_text(active_count=len(ACTIVE_TASKS))
        markup = get_bot_settings_markup()
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data == "settings":
        text = get_user_settings_text(u_id, u_name)
        markup = get_user_settings_markup(u_id)
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    # User Settings Actions
    elif data.startswith("uset_mode_"):
        target_uid = int(data.split("_")[-1])
        curr = SettingsManager.get_user_settings(target_uid)["stream_upload"]
        new_val = "Document" if curr == "Media" else "Media"
        SettingsManager.set_user_setting(target_uid, "stream_upload", new_val)
        text = get_user_settings_text(target_uid, u_name)
        markup = get_user_settings_markup(target_uid)
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data.startswith("uset_ytmenu_"):
        target_uid = int(data.split("_")[-1])
        await callback_query.message.edit_text(
            "🎬 <b>Choose your default yt-dlp download quality:</b>\n<i>(This resolution will be used automatically unless -s flag is provided)</i>",
            reply_markup=get_ytdl_quality_markup(target_uid),
        )

    elif data.startswith("uset_setyt_"):
        parts = data.split("_")
        val = parts[2]
        target_uid = int(parts[3])
        SettingsManager.set_user_setting(target_uid, "ytdl_quality", val)
        await callback_query.answer(f"Default YT-DLP set to {val}!")
        text = get_user_settings_text(target_uid, u_name)
        markup = get_user_settings_markup(target_uid)
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data.startswith("uset_fontmenu_"):
        target_uid = int(data.split("_")[-1])
        await callback_query.message.edit_text(
            "🔤 <b>Select caption font style:</b>",
            reply_markup=get_font_style_markup(target_uid),
        )

    elif data.startswith("uset_setfont_"):
        parts = data.split("_")
        val = parts[2]
        target_uid = int(parts[3])
        SettingsManager.set_user_setting(target_uid, "caption_style", val)
        await callback_query.answer(f"Font set to {val}!")
        text = get_user_settings_text(target_uid, u_name)
        markup = get_user_settings_markup(target_uid)
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data.startswith("uset_thumbmenu_"):
        target_uid = int(data.split("_")[-1])
        s = SettingsManager.get_user_settings(target_uid)
        thmb_status = "Custom thumbnail is active ✅" if s["has_thumb"] else "No custom thumbnail set (using default) 🖼"
        await callback_query.message.edit_text(
            f"🖼 <b>Thumbnail Settings:</b>\n{thmb_status}\n\n<i>To set a new thumbnail, simply send any photo in this chat!</i>",
            reply_markup=get_thumb_menu_markup(target_uid),
        )

    elif data.startswith("uset_delthumb_"):
        target_uid = int(data.split("_")[-1])
        SettingsManager.delete_user_thumb(target_uid)
        await callback_query.answer("Custom thumbnail deleted!", show_alert=True)
        text = get_user_settings_text(target_uid, u_name)
        markup = get_user_settings_markup(target_uid)
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data.startswith("uset_cookiemenu_"):
        target_uid = int(data.split("_")[-1])
        has_c = SettingsManager.has_cookies(target_uid)
        c_status = "Active ✅" if has_c else "None ❌"
        cookie_text = (
            f"🍪 <b><u>yt-dlp Cookies Settings</u></b>\n\n"
            f"╭⌬ <b>Status:</b> <i>{c_status}</i>\n"
            f"╰⌬ <b>Scope :</b> <i>Personal User Account</i>\n\n"
            f"<b>How to add your cookies:</b>\n"
            f"Send your <code>cookies.txt</code> document directly to the bot in private chat.\n\n"
            f"<i>All yt-dlp tasks will automatically use your cookies!</i>"
        )
        await callback_query.message.edit_text(
            cookie_text,
            reply_markup=get_cookie_menu_markup(target_uid),
            disable_web_page_preview=True,
        )

    elif data.startswith("uset_delcookies_"):
        target_uid = int(data.split("_")[-1])
        SettingsManager.delete_cookies(target_uid)
        await callback_query.answer("🍪 Cookies deleted!", show_alert=True)
        text = get_user_settings_text(target_uid, u_name)
        markup = get_user_settings_markup(target_uid)
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data.startswith("uset_samplemenu_"):
        target_uid = int(data.split("_")[-1])
        await callback_query.message.edit_text(
            "🎞 <b>Configure automated sample video clip:</b>",
            reply_markup=get_sample_markup(target_uid),
        )

    elif data.startswith("uset_setsample_"):
        parts = data.split("_")
        val = int(parts[2])
        target_uid = int(parts[3])
        SettingsManager.set_user_setting(target_uid, "sample_duration", val)
        await callback_query.answer(f"Sample duration set to {val}s!")
        text = get_user_settings_text(target_uid, u_name)
        markup = get_user_settings_markup(target_uid)
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data.startswith("uset_shotsmenu_"):
        target_uid = int(data.split("_")[-1])
        await callback_query.message.edit_text(
            "📸 <b>Configure automated video screenshots count:</b>",
            reply_markup=get_shots_markup(target_uid),
        )

    elif data.startswith("uset_setshots_"):
        parts = data.split("_")
        val = int(parts[2])
        target_uid = int(parts[3])
        SettingsManager.set_user_setting(target_uid, "screenshot_count", val)
        await callback_query.answer(f"Screenshots count set to {val}!")
        text = get_user_settings_text(target_uid, u_name)
        markup = get_user_settings_markup(target_uid)
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data.startswith("uset_splitmenu_"):
        target_uid = int(data.split("_")[-1])
        text = (
            "✂️ <b><u>File Split Size Configuration</u></b>\n\n"
            "Choose a predefined file split size limit or type your own custom MB size.\n"
            "• Free users default: <b>2.0 GB (1950 MB)</b>\n"
            "• Telegram Premium default: <b>4.0 GB (3900 MB)</b>\n\n"
            "<i>Files exceeding this size will automatically be split cleanly into numbered parts.</i>"
        )
        await callback_query.message.edit_text(text, reply_markup=get_split_menu_markup(target_uid))

    elif data.startswith("uset_setsplit_"):
        parts = data.split("_")
        mb_val = int(parts[2])
        target_uid = int(parts[3])
        split_video_label = "4GB" if mb_val > 2000 else "2GB"
        SettingsManager.set_user_setting(target_uid, "split_size_mb", mb_val)
        SettingsManager.set_user_setting(target_uid, "split_video", split_video_label)
        await callback_query.answer(f"Split limit set to {mb_val} MB!")
        text = get_user_settings_text(target_uid, u_name)
        markup = get_user_settings_markup(target_uid)
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data.startswith("uset_customsplit_"):
        target_uid = int(data.split("_")[-1])
        USER_INPUT_STATES[target_uid] = "set_custom_split"
        await callback_query.message.reply_text(
            "✂️ <b>Send custom split size in Megabytes (MB):</b>\n"
            "<i>Examples: <code>500</code> for 500MB, <code>1500</code> for 1.5GB, <code>3900</code> for 3.9GB (Max 3900 MB)</i>"
        )
        await callback_query.answer("Awaiting custom split size in MB...")

    elif data.startswith("uset_dumpmenu_"):
        target_uid = int(data.split("_")[-1])
        s = SettingsManager.get_user_settings(target_uid)
        d_chan = s.get("dump_channel") or "None"
        dm_state = "Enabled (Tasks triggered in groups deliver files to your PM)" if s.get("send_to_dm", True) else "Disabled (Files sent to the group)"
        text = (
            "📢 <b><u>Dump Channel & Direct Message Delivery</u></b>\n\n"
            f"╭⌬ <b>Custom Dump Channel :</b> <code>{d_chan}</code>\n"
            f"╰⌬ <b>Delivery Mode        :</b> <i>{dm_state}</i>\n\n"
            "<blockquote>Configure your own private storage channel or choose whether files are sent privately to your Bot DM to keep groups clean!</blockquote>"
        )
        await callback_query.message.edit_text(text, reply_markup=get_dump_menu_markup(target_uid))

    elif data.startswith("uset_setdump_"):
        target_uid = int(data.split("_")[-1])
        USER_INPUT_STATES[target_uid] = "set_dump_channel"
        await callback_query.message.reply_text(
            "📢 <b>Send your Dump Channel ID or Username:</b>\n"
            "<i>Example: <code>-1001234567890</code> or <code>@MyChannel</code></i>\n\n"
            "<b>Note:</b> Make sure you have added the bot as an Administrator in that channel with post permissions!"
        )
        await callback_query.answer("Awaiting dump channel ID...")

    elif data.startswith("uset_toggledm_"):
        target_uid = int(data.split("_")[-1])
        curr_dm = SettingsManager.get_user_settings(target_uid).get("send_to_dm", True)
        SettingsManager.set_user_setting(target_uid, "send_to_dm", not curr_dm)
        await callback_query.answer(f"Deliver to DM: {'Disabled' if curr_dm else 'Enabled'}")
        await callback_query.message.edit_reply_markup(reply_markup=get_dump_menu_markup(target_uid))

    elif data.startswith("uset_cleardump_"):
        target_uid = int(data.split("_")[-1])
        SettingsManager.set_user_setting(target_uid, "dump_channel", "")
        await callback_query.answer("Custom dump channel cleared!", show_alert=True)
        await callback_query.message.edit_reply_markup(reply_markup=get_dump_menu_markup(target_uid))

    elif data.startswith("uset_split_"):
        target_uid = int(data.split("_")[-1])
        curr = SettingsManager.get_user_settings(target_uid)["split_video"]
        new_val = "4GB" if curr == "2GB" else "2GB"
        SettingsManager.set_user_setting(target_uid, "split_video", new_val)
        SettingsManager.set_user_setting(target_uid, "split_size_mb", 3900 if new_val == "4GB" else 1950)
        text = get_user_settings_text(target_uid, u_name)
        markup = get_user_settings_markup(target_uid)
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data.startswith("uset_convert_"):
        target_uid = int(data.split("_")[-1])
        curr = SettingsManager.get_user_settings(target_uid)["convert_video"]
        new_val = "Yes" if curr == "No" else "No"
        SettingsManager.set_user_setting(target_uid, "convert_video", new_val)
        text = get_user_settings_text(target_uid, u_name)
        markup = get_user_settings_markup(target_uid)
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data.startswith("uset_apimenu_"):
        target_uid = int(data.split("_")[-1])
        s = SettingsManager.get_user_settings(target_uid)
        gf_status = "Custom Token Set ✅" if s.get("gofile_token") else "Default (Guest Account) 👤"
        pd_status = "Custom Key Set ✅" if s.get("pixeldrain_token") else "Default (Free Tier) 👤"
        text = (
            f"🔑 <b><i>Direct API Engines Settings</i></b>\n\n"
            f"╭⌬ <b>Gofile API Token    :</b> <i>{gf_status}</i>\n"
            f"╰⌬ <b>Pixeldrain API Key  :</b> <i>{pd_status}</i>\n\n"
            f"<blockquote>Adding your own API token removes guest bandwidth throttles and unlocks full premium download speeds!</blockquote>"
        )
        await callback_query.message.edit_text(text, reply_markup=get_api_menu_markup(target_uid), disable_web_page_preview=True)

    elif data.startswith("uset_setgofile_"):
        target_uid = int(data.split("_")[-1])
        USER_INPUT_STATES[target_uid] = "set_gofile"
        await callback_query.message.reply_text(
            "📁 <b>Send your Gofile API account token</b> in your next message (or send empty space to clear):\n"
            "<i>(Get your token from your Gofile account page: gofile.io)</i>"
        )
        await callback_query.answer("Awaiting Gofile token input...")

    elif data.startswith("uset_setpixeldrain_"):
        target_uid = int(data.split("_")[-1])
        USER_INPUT_STATES[target_uid] = "set_pixeldrain"
        await callback_query.message.reply_text(
            "⚡ <b>Send your Pixeldrain API Key</b> in your next message (or send empty space to clear):\n"
            "<i>(Get your API key from pixeldrain.com/user/api_keys)</i>"
        )
        await callback_query.answer("Awaiting Pixeldrain key input...")

    elif data.startswith("uset_clearapis_"):
        target_uid = int(data.split("_")[-1])
        SettingsManager.set_user_setting(target_uid, "gofile_token", "")
        SettingsManager.set_user_setting(target_uid, "pixeldrain_token", "")
        await callback_query.answer("Custom API tokens cleared!", show_alert=True)
        text = get_user_settings_text(target_uid, u_name)
        markup = get_user_settings_markup(target_uid)
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data.startswith("uset_affixmenu_"):
        target_uid = int(data.split("_")[-1])
        buttons = [
            [
                InlineKeyboardButton("🏷 Set Prefix", callback_data=f"uset_setprefix_{target_uid}"),
                InlineKeyboardButton("🏷 Set Suffix", callback_data=f"uset_setsuffix_{target_uid}"),
            ],
            [
                InlineKeyboardButton("« Back to Settings", callback_data=f"uset_back_{target_uid}"),
            ],
        ]
        await callback_query.message.edit_text("🏷 <b>Configure Prefix and Suffix for filenames:</b>", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("uset_setprefix_"):
        target_uid = int(data.split("_")[-1])
        USER_INPUT_STATES[target_uid] = "set_prefix"
        await callback_query.message.reply_text(
            "🏷 <b>Send filename prefix in your next message</b> (or send empty space to clear):\n<i>Example: [MyChannel]</i>"
        )
        await callback_query.answer("Awaiting prefix input...")

    elif data.startswith("uset_setsuffix_"):
        target_uid = int(data.split("_")[-1])
        USER_INPUT_STATES[target_uid] = "set_suffix"
        await callback_query.message.reply_text(
            "🏷 <b>Send filename suffix in your next message</b> (or send empty space to clear):\n<i>Example: @MyChannel</i>"
        )
        await callback_query.answer("Awaiting suffix input...")

    elif data.startswith("uset_setcap_"):
        target_uid = int(data.split("_")[-1])
        USER_INPUT_STATES[target_uid] = "set_caption"
        await callback_query.message.reply_text(
            "📝 <b>Send custom caption in your next message</b> (or send /clear to reset to default):"
        )
        await callback_query.answer("Awaiting caption input...")

    elif data.startswith("uset_reset_"):
        target_uid = int(data.split("_")[-1])
        SettingsManager.reset_user_settings(target_uid)
        await callback_query.answer("Settings reset to defaults!", show_alert=True)
        text = get_user_settings_text(target_uid, u_name)
        markup = get_user_settings_markup(target_uid)
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data.startswith("uset_back_"):
        target_uid = int(data.split("_")[-1])
        text = get_user_settings_text(target_uid, u_name)
        markup = get_user_settings_markup(target_uid)
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data == "uset_close":
        try:
            await callback_query.message.delete()
        except Exception:
            pass

    # Bot Settings Actions (Owner)
    elif data == "bset_tasks_menu":
        await callback_query.message.edit_text(
            "⚡ <b>Select Max Concurrent Downloads:</b>\n<i>Choose how many parallel downloads can run simultaneously</i>",
            reply_markup=get_bot_tasks_markup(),
        )

    elif data.startswith("bset_settasks_"):
        val = int(data.replace("bset_settasks_", ""))
        SettingsManager.set_bot_setting("max_parallel_tasks", val)
        await callback_query.answer(f"Max parallel tasks set to {val}!")
        text = get_bot_settings_text(active_count=len(ACTIVE_TASKS))
        markup = get_bot_settings_markup()
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data == "bset_toggle_split":
        b = SettingsManager.get_bot_settings()
        new_size = 4194304000 if b["leech_split_size"] <= 2500000000 else 2097152000
        SettingsManager.set_bot_setting("leech_split_size", new_size)
        await callback_query.answer(f"Split limit set to {'4GB' if new_size > 2500000000 else '2GB'}!")
        text = get_bot_settings_text(active_count=len(ACTIVE_TASKS))
        markup = get_bot_settings_markup()
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data == "bset_toggle_engine":
        b = SettingsManager.get_bot_settings()
        new_eng = "yt-dlp" if b["default_engine"] == "aria2c" else "aria2c"
        SettingsManager.set_bot_setting("default_engine", new_eng)
        await callback_query.answer(f"Default engine set to {new_eng}!")
        text = get_bot_settings_text(active_count=len(ACTIVE_TASKS))
        markup = get_bot_settings_markup()
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data == "bset_toggle_mode":
        b = SettingsManager.get_bot_settings()
        new_mode = "mirror" if b["default_mode"] == "leech" else "leech"
        SettingsManager.set_bot_setting("default_mode", new_mode)
        await callback_query.answer(f"Default mode set to {new_mode.capitalize()}!")
        text = get_bot_settings_text(active_count=len(ACTIVE_TASKS))
        markup = get_bot_settings_markup()
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data == "bset_purge_temp":
        try:
            if os.path.exists(Paths.WORK_PATH):
                for item in os.listdir(Paths.WORK_PATH):
                    ip = os.path.join(Paths.WORK_PATH, item)
                    if item.startswith("task_"):
                        try:
                            shutil.rmtree(ip)
                        except Exception:
                            pass
            await callback_query.answer("🧹 Work cache and temp files purged!", show_alert=True)
        except Exception as pe:
            await callback_query.answer(f"Purge error: {pe}", show_alert=True)
        text = get_bot_settings_text(active_count=len(ACTIVE_TASKS))
        markup = get_bot_settings_markup()
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data == "bset_reset_bot":
        ACTIVE_TASKS.clear()
        BOT.Queue.clear()
        BOT.State.task_going = False
        try:
            subprocess.run("pkill -9 -f 'aria2c|ffmpeg|ffprobe'", shell=True)
        except Exception:
            pass
        await callback_query.answer("🔄 Bot engine and active states reset!", show_alert=True)
        text = get_bot_settings_text(active_count=0)
        markup = get_bot_settings_markup()
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data == "bset_back":
        text = get_bot_settings_text(active_count=len(ACTIVE_TASKS))
        markup = get_bot_settings_markup()
        await callback_query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    elif data == "bset_close":
        try:
            await callback_query.message.delete()
        except Exception:
            pass


async def start_bot():
    await colab_bot.start()
    bot_me = colab_bot.me
    b_conf = SettingsManager.get_bot_settings()
    is_prem = getattr(bot_me, "is_premium", False)
    split_disp = "4GB (Premium)" if is_prem or b_conf.get("leech_split_size", 2097152000) > 2500000000 else "2GB (Free User)"

    banner_log = f"""
================================================================================
🚀 TGColabX is ONLINE & RUNNING in Google Colab!
================================================================================
🤖 Bot Username    : @{bot_me.username} ({bot_me.first_name})
👑 Owner ID        : {OWNER}
📦 Leech Limit     : {split_disp} (Auto-Split Enabled)
⚡ MTProto Engine  : DzGram (Rust WarpCrypto & Connection Pooling)
🏮 yt-dlp & Aria2  : Active & Ready (Parallel Multi-Download Enabled)
📁 Cloud Engines   : Gofile.io & Pixeldrain API Ready
💖 Developed by    : MyKurumiChan
🌟 Based on        : WZML-X & XronTrix10
================================================================================
Live task logs and download progress will stream below:
"""
    print(banner_log, flush=True)
    logging.info(f"Bot @{bot_me.username} started successfully with {split_disp} limit.")

    # Notify owner that bot is running
    if OWNER and str(OWNER) not in ["0", ""]:
        try:
            start_txt = (
                f"🚀 <b>TGColabX is now ONLINE & RUNNING!</b>\n\n"
                f"╭⌬ <b>Bot Name   :</b> <code>{bot_me.first_name}</code>\n"
                f"├⌬ <b>Username   :</b> @{bot_me.username}\n"
                f"├⌬ <b>Split Limit:</b> <code>{split_disp}</code>\n"
                f"├⌬ <b>Engine     :</b> <i>DzGram + Aria2c + yt-dlp</i>\n"
                f"╰⌬ <b>Multi-DL   :</b> <i>True Parallel Active</i>\n\n"
                f"<blockquote>Send <code>/help</code> or <code>/leech</code> to start!</blockquote>"
            )
            await colab_bot.send_message(chat_id=OWNER, text=start_txt)
        except Exception as e:
            logging.warning(f"Could not send startup message to owner: {e}")

    from pyrogram import idle
    await idle()
    await colab_bot.stop()


if __name__ == "__main__":
    try:
        colab_bot.run(start_bot())
    except KeyboardInterrupt:
        print("\n🛑 TGColabX stopped by user.")
    except Exception as e:
        logging.critical(f"❌ Fatal error during TGColabX execution: {e}", exc_info=True)
        sys.exit(1)
