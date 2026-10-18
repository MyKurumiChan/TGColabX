# TGColabX - Based on WZML-X & XronTrix10
# Copyright (c) 2024-2026 TGColabX

import os
import logging
import yt_dlp
from asyncio import sleep, get_event_loop
from threading import Thread
from os import makedirs, path as ospath
from colab_leecher.utility.variables import BOT, YTDL, MSG, Messages, Paths
from colab_leecher.utility.settings_manager import SettingsManager
from colab_leecher.utility.helper import getTime, sizeUnit, status_bar


class MyLogger:
    def __init__(self):
        pass

    def debug(self, msg):
        pass

    @staticmethod
    def warning(msg):
        logging.warning(f"[yt-dlp warning] {msg}")

    @staticmethod
    def error(msg):
        if "ERROR: Cancelling..." not in str(msg):
            logging.error(f"[yt-dlp error] {msg}")


async def YTDL_Status(link, num, task_ctx=None):
    global Messages, YTDL

    user_id = task_ctx.chat_id if task_ctx else None
    cookie_path = SettingsManager.get_cookie_path(user_id)
    has_cookies = bool(cookie_path)
    engine_name = "yt-dlp 🏮 (🍪 Cookies)" if has_cookies else "yt-dlp 🏮"

    name = await get_YT_Name(link, cookie_path=cookie_path)
    custom_name = (task_ctx.options.get("custom_name") if task_ctx else None) or BOT.Options.custom_name
    if custom_name:
        name = custom_name

    if task_ctx:
        task_ctx.task_title = name
        task_ctx.engine = engine_name
        task_ctx.status_state = "Download"
    else:
        Messages.download_name = name
        Messages.status_head = f"<b>📥 DOWNLOADING FROM » </b><i>🔗Link {str(num).zfill(2)}</i>\n\n<code>{name}</code>\n"

    # Reset metrics
    if task_ctx:
        task_ctx.speed = "0 B/s"
        task_ctx.percentage = 0.0
        task_ctx.eta = "N/A"
        task_ctx.done = "0 B"
        task_ctx.left = "N/A"
        task_ctx.error = None
    else:
        YTDL.speed = "0 B/s"
        YTDL.percentage = 0.0
        YTDL.eta = "N/A"
        YTDL.done = "0 B"
        YTDL.left = "N/A"

    ytdl_thread = Thread(target=YouTubeDL, name="YouTubeDL", args=(link, task_ctx, cookie_path), daemon=True)
    ytdl_thread.start()

    while ytdl_thread.is_alive():
        try:
            if task_ctx and task_ctx.is_cancelled:
                logging.info(f"Task {task_ctx.task_id} was cancelled, breaking YTDL status monitor.")
                break

            speed = task_ctx.speed if task_ctx else (YTDL.speed or "0 B/s")
            pct = task_ctx.percentage if task_ctx else float(YTDL.percentage or 0.0)
            eta = task_ctx.eta if task_ctx else (YTDL.eta or "N/A")
            done = task_ctx.done if task_ctx else (YTDL.done or "0 B")
            left = task_ctx.left if task_ctx else (YTDL.left or "N/A")

            await status_bar(
                down_msg=f"<b>📥 DOWNLOADING » </b><code>{name}</code>\n",
                speed=speed,
                percentage=pct,
                eta=eta,
                done=done,
                left=left,
                engine=engine_name,
                task_title=name,
                task_ctx=task_ctx,
            )
        except Exception as e:
            logging.error(f"Error in YTDL status update: {e}")

        await sleep(2.0)

    # Thread finished, ensure join
    ytdl_thread.join(timeout=2.0)

    # Check for cancellation
    if task_ctx and task_ctx.is_cancelled:
        return

    # Check for thread-level error
    if task_ctx and task_ctx.error:
        raise RuntimeError(f"yt-dlp failed: {task_ctx.error}")

    # Verify that a media file actually exists in down_dir
    down_dir = task_ctx.down_path if task_ctx else Paths.down_path
    if ospath.exists(down_dir):
        # Media files excluding auxiliary metadata and part files
        valid_files = []
        for root, _, files in os.walk(down_dir):
            for f in files:
                f_low = f.lower()
                if not f_low.endswith((".part", ".ytdl", ".info.json", ".description", ".annotations.xml")):
                    valid_files.append(ospath.join(root, f))

        if not valid_files:
            err_msg = task_ctx.error if (task_ctx and task_ctx.error) else "yt-dlp completed but no media file was downloaded. (Check cookies or video restriction)"
            if task_ctx:
                task_ctx.error = err_msg
            raise RuntimeError(err_msg)
    else:
        raise RuntimeError("yt-dlp download directory not found!")


def YouTubeDL(url, task_ctx=None, cookie_path: str = ""):
    global YTDL

    user_id = task_ctx.chat_id if task_ctx else None
    if not cookie_path:
        cookie_path = SettingsManager.get_cookie_path(user_id)

    def my_hook(d):
        nonlocal task_ctx
        global YTDL

        if d.get("status") == "downloading":
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            dl_bytes = d.get("downloaded_bytes") or 0
            percent = 0.0
            if total_bytes > 0:
                percent = round((float(dl_bytes) * 100 / float(total_bytes)), 2)

            speed = d.get("speed")
            eta = d.get("eta")

            speed_str = f"{sizeUnit(speed)}/s" if (isinstance(speed, (int, float)) and speed > 0) else "0 B/s"
            eta_str = getTime(eta) if (isinstance(eta, (int, float)) and eta > 0) else "N/A"
            done_str = sizeUnit(dl_bytes)
            left_str = sizeUnit(total_bytes) if total_bytes > 0 else "N/A"

            if task_ctx:
                task_ctx.speed = speed_str
                task_ctx.percentage = percent
                task_ctx.eta = eta_str
                task_ctx.done = done_str
                task_ctx.left = left_str
                if total_bytes > 0:
                    task_ctx.total_size = total_bytes
            else:
                YTDL.header = ""
                YTDL.speed = speed_str
                YTDL.percentage = percent
                YTDL.eta = eta_str
                YTDL.done = done_str
                YTDL.left = left_str

    down_dir = task_ctx.down_path if task_ctx else Paths.down_path
    thumb_dir = task_ctx.thumbnail_ytdl if task_ctx else Paths.thumbnail_ytdl
    makedirs(down_dir, exist_ok=True)
    makedirs(thumb_dir, exist_ok=True)

    # Format handling
    format_choice = "bv*+ba/b"
    if task_ctx and task_ctx.options.get("ytdl_format"):
        format_choice = task_ctx.options["ytdl_format"]
    elif BOT.Options.ytdl_format:
        format_choice = BOT.Options.ytdl_format

    custom_name = (task_ctx.options.get("custom_name") if task_ctx else None) or BOT.Options.custom_name

    # Safe templates
    if custom_name:
        base_name = ospath.splitext(custom_name)[0]
        default_tmpl = f"{down_dir}/{base_name}.%(ext)s"
    else:
        default_tmpl = f"{down_dir}/%(title).180s.%(ext)s"

    thumb_tmpl = f"{thumb_dir}/%(title).180s.%(ext)s"

    outtmpl_dict = {
        "default": default_tmpl,
        "thumbnail": thumb_tmpl,
    }

    # WZML-X production-grade yt-dlp configurations
    base_ydl_opts = {
        "outtmpl": outtmpl_dict,
        "writethumbnail": True,
        "overwrites": True,
        "ignoreerrors": False,
        "allow_multiple_video_streams": True,
        "allow_multiple_audio_streams": True,
        "allow_playlist_files": True,
        "trim_file_name": 180,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "merge_output_format": "mp4",
        "retries": 10,
        "fragment_retries": 10,
        "extractor_retries": 5,
        "progress_hooks": [my_hook],
        "logger": MyLogger(),
        "quiet": False,
        "no_warnings": False,
        # Configure YouTube extractor args adaptively
        # Never skip hls or dash (which removes all video/audio streams on YouTube!)
        "extractor_args": {
            "youtube": {
                "player_client": ["tv", "web_creator", "mweb", "web"] if (cookie_path and ospath.exists(cookie_path)) else ["tv", "web_creator", "mweb", "web", "android", "ios"],
            }
        },
    }

    if cookie_path and ospath.exists(cookie_path):
        base_ydl_opts["cookiefile"] = cookie_path
        logging.info(f"Attached cookies to yt-dlp: {cookie_path}")

    # Build format string with resilient fallbacks
    if format_choice == "mp3":
        ydl_opts = dict(base_ydl_opts)
        ydl_opts.update({
            "format": "ba/b/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                },
                {
                    "key": "FFmpegMetadata",
                    "add_metadata": True,
                },
            ],
        })
    else:
        if "height<=" in format_choice:
            format_str = f"{format_choice}/bv*+ba/b/best"
        elif format_choice in ["bv*+ba/b", "best"]:
            format_str = "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b[ext=mp4]/b/best"
        else:
            format_str = f"{format_choice}/bv*+ba/b/best"

        ydl_opts = dict(base_ydl_opts)
        ydl_opts.update({
            "format": format_str,
            "postprocessors": [
                {
                    "key": "FFmpegMetadata",
                    "add_metadata": True,
                },
            ],
        })

    try:
        logging.info(f"Invoking yt-dlp.YoutubeDL with format: {ydl_opts.get('format')} for {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Verify output
        has_file = False
        if ospath.exists(down_dir):
            for _, _, files in os.walk(down_dir):
                if any(not f.endswith((".part", ".ytdl")) for f in files):
                    has_file = True
                    break

        if not has_file:
            logging.warning("No complete file found after initial attempt. Retrying with format 'best'...")
            fallback_opts = dict(base_ydl_opts)
            fallback_opts["format"] = "b/best"
            fallback_opts.pop("postprocessors", None)
            with yt_dlp.YoutubeDL(fallback_opts) as ydl_fb:
                ydl_fb.download([url])

    except Exception as e:
        logging.warning(f"Initial yt-dlp attempt failed: {e}. Retrying with generic fallback 'b/best'...")
        try:
            fallback_opts = dict(base_ydl_opts)
            fallback_opts["format"] = "b/best"
            fallback_opts.pop("postprocessors", None)
            with yt_dlp.YoutubeDL(fallback_opts) as ydl_fallback:
                ydl_fallback.download([url])
            logging.info("yt-dlp fallback download succeeded!")
        except Exception as e2:
            logging.error(f"YTDL ERROR completely failed: {e2}")
            if task_ctx:
                task_ctx.error = str(e2)


async def get_YT_Name(link, cookie_path: str = ""):
    loop = get_event_loop()

    if not cookie_path:
        cookie_path = SettingsManager.get_cookie_path()

    def _extract():
        opts = {
            "logger": MyLogger(),
            "quiet": True,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["tv", "web_creator", "mweb", "web"] if (cookie_path and ospath.exists(cookie_path)) else ["tv", "web_creator", "mweb", "web", "android", "ios"],
                }
            },
        }
        if cookie_path and ospath.exists(cookie_path):
            opts["cookiefile"] = cookie_path
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(link, download=False)

    try:
        info = await loop.run_in_executor(None, _extract)
        if info:
            if "title" in info and info["title"]:
                return info["title"]
            elif "entries" in info and info["entries"]:
                first = info["entries"][0]
                if first and "title" in first:
                    return first["title"]
        return "YTDL_Download"
    except Exception as e:
        logging.warning(f"Error fetching YT title: {e}")
        return "YTDL_Download"
