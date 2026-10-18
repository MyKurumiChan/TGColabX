# TGColabX - Based on WZML-X & XronTrix10
# Copyright (c) 2024-2026 TGColabX

import os
import re
import json
import math
import psutil
import logging
import subprocess
import urllib.request
from time import time
from PIL import Image
from os import path as ospath
from datetime import datetime
from urllib.parse import urlparse
from asyncio import get_event_loop
from colab_leecher import colab_bot
from pyrogram.errors import BadRequest, FloodWait

try:
    from pyrogram.types import LinkPreviewOptions
    link_preview = LinkPreviewOptions(is_disabled=True)
except ImportError:
    link_preview = None

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from colab_leecher.utility.variables import (
    BOT,
    MSG,
    BotTimes,
    Messages,
    Paths,
)


def isLink(_, __, update):
    """
    Robust link capture: catches any message containing http/https, tg://,
    magnet links, or local Colab file paths anywhere in the text.
    """
    if update.text:
        text = update.text.strip()
        if "/content/" in text or "/home" in text:
            return True
        elif "magnet:?xt=" in text.lower() or text.lower().endswith(".torrent"):
            return True

        # Check for any valid URL anywhere in the message
        url_match = re.search(r"https?://[^\s]+", text)
        if url_match:
            return True

    return False


def is_google_drive(link):
    return "drive.google.com" in str(link)


def is_mega(link):
    return "mega.nz" in str(link)


def is_terabox(link):
    return "terabox" in str(link) or "1024tera" in str(link) or "teraboxapp" in str(link) or "4funbox" in str(link)


def is_ytdl_link(link):
    """
    Enhanced streaming link detector for yt-dlp:
    Covers YouTube, Vimeo, Dailymotion, Twitch, Facebook, Instagram, Twitter/X,
    TikTok, Reddit, SoundCloud, Bilibili, Pinterest, streamtape, ok.ru, VK, etc.
    """
    ytdl_hosts = [
        "youtube.com", "youtu.be", "facebook.com", "fb.watch", "fb.com",
        "instagram.com", "twitter.com", "x.com", "tiktok.com", "reddit.com",
        "vimeo.com", "dailymotion.com", "twitch.tv", "soundcloud.com",
        "bilibili.com", "pinterest.com", "ok.ru", "vk.com", "loom.com",
        "rumble.com", "streamable.com", "bitchute.com", "odysee.com",
    ]
    low_link = str(link).lower()
    return any(host in low_link for host in ytdl_hosts)


def is_telegram(link):
    return "t.me" in link or "telegram.me" in link


def is_gofile(link):
    return "gofile.io" in str(link)


def is_pixeldrain(link):
    return "pixeldrain.com" in str(link) or "pixeldra.in" in str(link)


def is_torrent_or_magnet(link):
    low = str(link).lower().strip()
    return "magnet:?xt=" in low or low.endswith(".torrent") or "torrent" in low


is_torrent = is_torrent_or_magnet


def getTime(seconds):
    seconds = int(seconds)
    days = seconds // (24 * 3600)
    seconds = seconds % (24 * 3600)
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60

    if days > 0:
        return f"{days}d {hours}h {minutes}m {seconds}s"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


def sizeUnit(size):
    try:
        size = float(size)
    except Exception:
        return "0 B"
    if size > 1024 * 1024 * 1024 * 1024 * 1024:
        siz = f"{size/(1024**5):.2f} PiB"
    elif size > 1024 * 1024 * 1024 * 1024:
        siz = f"{size/(1024**4):.2f} TiB"
    elif size > 1024 * 1024 * 1024:
        siz = f"{size/(1024**3):.2f} GiB"
    elif size > 1024 * 1024:
        siz = f"{size/(1024**2):.2f} MiB"
    elif size > 1024:
        siz = f"{size/1024:.2f} KiB"
    else:
        siz = f"{size:.2f} B"
    return siz


def fileType(file_path: str):
    extensions_dict = {
        ".mp4": "video",
        ".avi": "video",
        ".mkv": "video",
        ".m2ts": "video",
        ".mov": "video",
        ".ts": "video",
        ".m3u8": "video",
        ".webm": "video",
        ".mpg": "video",
        ".mpeg": "video",
        ".mpeg4": "video",
        ".vob": "video",
        ".m4v": "video",
        ".flv": "video",
        ".3gp": "video",
        ".mp3": "audio",
        ".wav": "audio",
        ".flac": "audio",
        ".aac": "audio",
        ".ogg": "audio",
        ".m4a": "audio",
        ".opus": "audio",
        ".jpg": "photo",
        ".jpeg": "photo",
        ".png": "photo",
        ".bmp": "photo",
        ".gif": "photo",
        ".webp": "photo",
    }
    _, extension = ospath.splitext(file_path)
    return extensions_dict.get(extension.lower(), "document")


def shortFileName(path):
    if ospath.isfile(path):
        dir_path, filename = ospath.split(path)
        if len(filename) > 60:
            basename, ext = ospath.splitext(filename)
            basename = basename[: 60 - len(ext)]
            filename = basename + ext
            path = ospath.join(dir_path, filename)
        return path
    elif ospath.isdir(path):
        dir_path, dirname = ospath.split(path)
        if len(dirname) > 60:
            dirname = dirname[:60]
            path = ospath.join(dir_path, dirname)
        return path
    else:
        return path[:60] if len(path) > 60 else path


def getSize(path):
    if not ospath.exists(path):
        return 0
    if ospath.isfile(path):
        return ospath.getsize(path)
    total_size = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = ospath.join(dirpath, f)
            if ospath.exists(fp):
                total_size += ospath.getsize(fp)
    return total_size


def videoExtFix(file_path: str):
    _, ext = ospath.splitext(file_path)
    if ext.lower() in [".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".ts", ".m4v", ".3gp"]:
        return file_path
    new_path = file_path + ".mp4"
    try:
        os.rename(file_path, new_path)
        return new_path
    except Exception:
        return file_path


def getVideoDuration(file_path):
    """Get video duration in seconds using ffprobe."""
    try:
        cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{file_path}"'
        res = subprocess.check_output(cmd, shell=True).decode().strip()
        return round(float(res))
    except Exception:
        return 0


def extractVideoFrame(file_path, output_path, timestamp=1):
    """Extract a single frame from video at given timestamp using ffmpeg."""
    try:
        cmd = f'ffmpeg -y -ss {timestamp} -i "{file_path}" -vframes 1 -q:v 2 "{output_path}"'
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return ospath.exists(output_path) and ospath.getsize(output_path) > 0
    except Exception:
        return False


def thumbMaintainer(file_path, task_ctx=None, user_id=None):
    from colab_leecher.utility.settings_manager import SettingsManager

    duration = getVideoDuration(file_path)
    work_dir = task_ctx.work_path if task_ctx else Paths.WORK_PATH
    frame_path = ospath.join(work_dir, "video_frame.jpg")

    try:
        if ospath.exists(frame_path):
            try:
                os.remove(frame_path)
            except Exception:
                pass

        # 1. Check user custom thumbnail
        if user_id:
            u_thumb = SettingsManager.get_user_thumb_path(user_id)
            if ospath.exists(u_thumb):
                return u_thumb, duration

        # 2. Check global custom thumbnail
        if ospath.exists(Paths.THMB_PATH):
            return Paths.THMB_PATH, duration

        # 3. Check YTDL downloaded thumbnail
        thumb_dirs = []
        if task_ctx and ospath.exists(task_ctx.thumbnail_ytdl):
            thumb_dirs.append(task_ctx.thumbnail_ytdl)
        if ospath.exists(Paths.thumbnail_ytdl):
            thumb_dirs.append(Paths.thumbnail_ytdl)

        fname, _ = ospath.splitext(ospath.basename(file_path))
        for tdir in thumb_dirs:
            # Check direct name matches
            for ext in [".jpg", ".jpeg", ".webp", ".png"]:
                candidate = ospath.join(tdir, f"{fname}{ext}")
                if ospath.exists(candidate):
                    if ext.lower() in [".webp", ".png"]:
                        return convertIMG(candidate), duration
                    return candidate, duration

            # Check any image in thumb folder
            for img_file in os.listdir(tdir):
                if img_file.lower().endswith((".jpg", ".jpeg")):
                    return ospath.join(tdir, img_file), duration
                elif img_file.lower().endswith((".webp", ".png")):
                    return convertIMG(ospath.join(tdir, img_file)), duration

        # 4. Fallback: Extract video frame
        capture_time = max(1, math.floor(duration / 2)) if duration > 0 else 1
        if extractVideoFrame(file_path, frame_path, capture_time):
            return frame_path, duration

        # 5. Default Hero image
        if ospath.exists(Paths.DEFAULT_HERO):
            return Paths.DEFAULT_HERO, duration
        return Paths.HERO_IMAGE, duration

    except Exception as e:
        logging.error(f"Thumbnail maintainer error: {e}")
        if ospath.exists(Paths.THMB_PATH):
            return Paths.THMB_PATH, 0
        return Paths.HERO_IMAGE, 0


async def setThumbnail(message, user_id=None):
    from colab_leecher.utility.settings_manager import SettingsManager
    try:
        target_path = SettingsManager.get_user_thumb_path(user_id) if user_id else Paths.THMB_PATH
        if ospath.exists(target_path):
            try:
                os.remove(target_path)
            except Exception:
                pass
        await message.download(file_name=target_path)
        if user_id:
            SettingsManager.set_user_setting(user_id, "has_thumb", True)
        BOT.Setting.thumbnail = True
        return True
    except Exception as e:
        logging.error(f"Error Downloading Thumbnail: {e}")
        return False


def download_thumbnail_from_url(url: str, user_id=None):
    """Downloads an image from URL and sets as custom thumbnail."""
    from colab_leecher.utility.settings_manager import SettingsManager
    try:
        target_path = SettingsManager.get_user_thumb_path(user_id) if user_id else Paths.THMB_PATH
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response, open(target_path, "wb") as out_file:
            out_file.write(response.read())
        if user_id:
            SettingsManager.set_user_setting(user_id, "has_thumb", True)
        BOT.Setting.thumbnail = True
        return True
    except Exception as e:
        logging.error(f"Failed to download thumbnail from URL: {e}")
        return False


def isYtdlComplete(check_path=None):
    target = check_path or Paths.down_path
    if not ospath.exists(target):
        return False
    found_files = False
    for _d, _, filenames in os.walk(target):
        for f in filenames:
            __, ext = ospath.splitext(f)
            if ext in [".part", ".ytdl"]:
                return False
            found_files = True
    return found_files


def convertIMG(image_path):
    image = Image.open(image_path)
    if image.mode != "RGB":
        image = image.convert("RGB")
    output_path = ospath.splitext(image_path)[0] + ".jpg"
    image.save(output_path, "JPEG")
    try:
        os.remove(image_path)
    except Exception:
        pass
    return output_path


def get_progress_bar_string(pct):
    """WZML-X circular progress bar style."""
    try:
        p = float(str(pct).strip("%"))
    except Exception:
        p = 0.0
    p = min(max(p, 0.0), 100.0)

    total_blocks = 12
    filled_blocks = int(p / (100 / total_blocks))

    p_str = "⬤" * filled_blocks
    remaining_pct = p % (100 / total_blocks)
    if remaining_pct > 0 and filled_blocks < total_blocks:
        if remaining_pct < (25 / total_blocks * 100):
            p_str += "◔"
            filled_blocks += 1
        elif remaining_pct < (50 / total_blocks * 100):
            p_str += "◑"
            filled_blocks += 1
        elif remaining_pct < (75 / total_blocks * 100):
            p_str += "◕"
            filled_blocks += 1

    p_str += "○" * (total_blocks - filled_blocks)
    return f"[{p_str}]"


def sysINFO():
    """WZML-X formatted Bot Stats card."""
    cpu_usage_percent = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    disk_usage = psutil.disk_usage("/")
    uptime = getTime((datetime.now() - BotTimes.start_time).seconds)

    string = "\n\n❂ <b><i>𝗕𝗢𝗧 𝗦𝗧𝗔𝗧𝗦</i></b>\n"
    string += f"<blockquote>╭ <code>CPU  :</code> {cpu_usage_percent}%\n"
    string += f"┊ <code>RAM  :</code> {ram.percent}%\n"
    string += f"┊ <code>FREE :</code> {sizeUnit(disk_usage.free)}\n"
    string += f"╰ <code>UP   :</code> {uptime}</blockquote>"
    return string


def multipartArchive(path: str, type: str, remove: bool):
    dirname, filename = ospath.split(path)
    name, _ = ospath.splitext(filename)

    c, size, rname = 1, 0, name
    if type == "rar":
        name_, _ = ospath.splitext(name)
        rname = name_
        na_p = name_ + ".part" + str(c) + ".rar"
        p_ap = ospath.join(dirname, na_p)
        while ospath.exists(p_ap):
            if remove:
                os.remove(p_ap)
            size += getSize(p_ap)
            c += 1
            na_p = name_ + ".part" + str(c) + ".rar"
            p_ap = ospath.join(dirname, na_p)

    elif type == "7z":
        na_p = name + "." + str(c).zfill(3)
        p_ap = ospath.join(dirname, na_p)
        while ospath.exists(p_ap):
            if remove:
                os.remove(p_ap)
            size += getSize(p_ap)
            c += 1
            na_p = name + "." + str(c).zfill(3)
            p_ap = ospath.join(dirname, na_p)

    elif type == "zip":
        na_p = name + ".zip"
        p_ap = ospath.join(dirname, na_p)
        if ospath.exists(p_ap):
            if remove:
                os.remove(p_ap)
            size += getSize(p_ap)
        na_p = name + ".z" + str(c).zfill(2)
        p_ap = ospath.join(dirname, na_p)
        while ospath.exists(p_ap):
            if remove:
                os.remove(p_ap)
            size += getSize(p_ap)
            c += 1
            na_p = name + ".z" + str(c).zfill(2)
            p_ap = ospath.join(dirname, na_p)

        if rname.endswith(".zip"):
            rname, _ = ospath.splitext(rname)

    return rname, size


def isTimeOver(force: bool = False):
    global BotTimes
    passed = force or (time() - BotTimes.current_time >= 3)
    if passed:
        BotTimes.current_time = time()
    return passed


def applyCustomName():
    if len(BOT.Options.custom_name) != 0 and BOT.Mode.type not in ["zip", "undzip"]:
        if ospath.exists(Paths.down_path):
            files = os.listdir(Paths.down_path)
            for file_ in files:
                current_name = ospath.join(Paths.down_path, file_)
                new_name = ospath.join(Paths.down_path, BOT.Options.custom_name)
                try:
                    os.rename(current_name, new_name)
                except Exception:
                    pass


def speedETA(start, done, total):
    percentage = (done / total) * 100 if total > 0 else 0
    percentage = min(100.0, max(0.0, percentage))
    elapsed_time = (datetime.now() - start).seconds
    if done > 0 and elapsed_time != 0:
        raw_speed = done / elapsed_time
        speed = f"{sizeUnit(raw_speed)}/s"
        eta = (total - done) / raw_speed
    else:
        speed, eta = "N/A", 0
    return speed, eta, percentage


async def message_deleter(message1, message2):
    try:
        await message1.delete()
    except Exception:
        pass
    try:
        await message2.delete()
    except Exception:
        pass


async def send_settings(client, message, msg_id, command: bool):
    up_mode = "document" if BOT.Options.stream_upload else "media"
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"Set {up_mode.capitalize()}", callback_data=up_mode
                ),
                InlineKeyboardButton("Video Settings", callback_data="video"),
            ],
            [
                InlineKeyboardButton("Caption Font", callback_data="caption"),
                InlineKeyboardButton("Thumbnail", callback_data="thumb"),
            ],
            [
                InlineKeyboardButton("Set Suffix", callback_data="set-suffix"),
                InlineKeyboardButton("Set Prefix", callback_data="set-prefix"),
            ],
            [InlineKeyboardButton("Close ✘", callback_data="close")],
        ]
    )
    text = "<b>⚙️ TGColabX Settings Menu »</b>\n"
    text += f"\n╭⌬ <b>Upload :</b> <i>{BOT.Setting.stream_upload}</i>"
    text += f"\n├⌬ <b>Split  :</b> <i>{BOT.Setting.split_video}</i>"
    text += f"\n├⌬ <b>Convert:</b> <i>{BOT.Setting.convert_video}</i>"
    text += f"\n├⌬ <b>Caption:</b> <i>{BOT.Setting.caption}</i>"
    pr = "None" if BOT.Setting.prefix == "" else "Exists"
    su = "None" if BOT.Setting.suffix == "" else "Exists"
    thmb = "None" if not BOT.Setting.thumbnail else "Exists"
    text += f"\n├⌬ <b>Prefix :</b> <i>{pr}</i>\n├⌬ <b>Suffix :</b> <i>{su}</i>"
    text += f"\n╰⌬ <b>Thumb  :</b> <i>{thmb}</i>"
    try:
        if command:
            await message.reply_text(text=text, reply_markup=keyboard)
        else:
            await colab_bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg_id,
                text=text,
                reply_markup=keyboard,
            )
    except BadRequest:
        pass
    except Exception as error:
        logging.error(f"Error Modifying settings message: {error}")


def automated_video_merge(work_dir: str):
    """
    Automated video/audio merge using FFmpeg (WZML-X feature).
    Merges multiple video parts into a single video file,
    or muxes separate video and audio files into a single video.
    """
    from natsort import natsorted

    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".ts"}
    audio_exts = {".mp3", ".m4a", ".aac", ".wav", ".opus", ".flac"}

    if not ospath.exists(work_dir):
        return None

    video_files = []
    audio_files = []
    for f in os.listdir(work_dir):
        fp = ospath.join(work_dir, f)
        if ospath.isfile(fp):
            ext = ospath.splitext(f)[1].lower()
            if ext in video_exts:
                video_files.append(fp)
            elif ext in audio_exts:
                audio_files.append(fp)

    video_files = natsorted(video_files)
    audio_files = natsorted(audio_files)

    if len(video_files) > 1:
        logging.info(f"Merging {len(video_files)} video parts...")
        concat_txt = ospath.join(work_dir, "concat_list.txt")
        with open(concat_txt, "w", encoding="utf-8") as f:
            for vf in video_files:
                f.write(f"file '{vf}'\n")

        base_name = ospath.splitext(ospath.basename(video_files[0]))[0]
        merged_name = re.sub(r'[\s._-]*(?:part|pt)[\s._-]*\d+', '', base_name, flags=re.I).strip()
        if not merged_name:
            merged_name = "Merged_Video"
        merged_output = ospath.join(work_dir, f"{merged_name}.mp4")

        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_txt, "-c", "copy", merged_output]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0 or not ospath.exists(merged_output) or ospath.getsize(merged_output) == 0:
            logging.info("Fast concat copy failed, merging with re-encode fallback...")
            cmd_reencode = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_txt, "-c:v", "libx264", "-crf", "22", "-preset", "fast", "-c:a", "aac", merged_output]
            subprocess.run(cmd_reencode, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if ospath.exists(concat_txt):
            try:
                os.remove(concat_txt)
            except Exception:
                pass

        if ospath.exists(merged_output) and ospath.getsize(merged_output) > 0:
            for vf in video_files:
                try:
                    os.remove(vf)
                except Exception:
                    pass
            logging.info(f"Automated merge complete: {merged_output}")
            return merged_output

    elif len(video_files) == 1 and len(audio_files) == 1:
        vf = video_files[0]
        af = audio_files[0]
        logging.info(f"Muxing video {vf} with audio {af}...")
        merged_output = ospath.join(work_dir, f"Muxed_{ospath.basename(vf)}")
        cmd = ["ffmpeg", "-y", "-i", vf, "-i", af, "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", merged_output]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if ospath.exists(merged_output) and ospath.getsize(merged_output) > 0:
            try:
                os.remove(vf)
                os.remove(af)
            except Exception:
                pass
            logging.info(f"Muxing complete: {merged_output}")
            return merged_output

    return None


def generate_sample_video(video_path: str, sample_duration: int = 30) -> str:
    """
    WZML-X Feature: Generates a high-quality sample video of specified duration.
    """
    if not ospath.exists(video_path):
        return None

    duration = getVideoDuration(video_path)
    if duration <= sample_duration:
        return None

    os.makedirs(Paths.samples_dir, exist_ok=True)
    base_name = ospath.splitext(ospath.basename(video_path))[0]
    sample_file = ospath.join(Paths.samples_dir, f"SAMPLE_{base_name}.mp4")

    start_pos = max(10, (duration // 2) - (sample_duration // 2))

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(start_pos),
        "-i", video_path,
        "-t", str(sample_duration),
        "-c:v", "libx264",
        "-crf", "22",
        "-preset", "fast",
        "-c:a", "aac",
        sample_file,
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        if proc.returncode == 0 and ospath.exists(sample_file) and ospath.getsize(sample_file) > 0:
            return sample_file
    except Exception as e:
        logging.error(f"Sample video creation failed: {e}")

    return None


def generate_screenshots(video_path: str, count: int = 5) -> list:
    """
    WZML-X Feature: Generates evenly spaced screenshots from a video.
    """
    if not ospath.exists(video_path) or count <= 0:
        return []

    duration = getVideoDuration(video_path)
    if duration <= 2:
        return []

    count = min(count, 10)
    os.makedirs(Paths.screenshots_dir, exist_ok=True)
    base_name = ospath.splitext(ospath.basename(video_path))[0]

    interval = duration / (count + 1)
    shots = []
    for i in range(1, count + 1):
        ts = int(i * interval)
        out_shot = ospath.join(Paths.screenshots_dir, f"SS_{base_name}_{i:02d}.jpg")
        if extractVideoFrame(video_path, out_shot, ts):
            shots.append(out_shot)

    return shots


def get_media_info_text(file_path: str) -> str:
    """
    WZML-X Feature: Extracts detailed MediaInfo / FFprobe specifications.
    """
    if not ospath.exists(file_path):
        return "<i>File not found.</i>"

    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_format",
            "-show_streams",
            "-print_format", "json",
            file_path,
        ]
        out = subprocess.check_output(cmd).decode("utf-8", errors="ignore")
        data = json.loads(out)
    except Exception as e:
        return f"⚠️ <b>MediaInfo extraction error:</b> <code>{e}</code>"

    fmt = data.get("format", {})
    duration_sec = round(float(fmt.get("duration", 0)))
    duration_str = getTime(duration_sec)
    size_str = sizeUnit(int(fmt.get("size", ospath.getsize(file_path))))
    bitrate = int(fmt.get("bit_rate", 0))
    bitrate_str = f"{bitrate // 1000} kb/s" if bitrate else "N/A"

    streams = data.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    sub_streams = [s for s in streams if s.get("codec_type") == "subtitle"]

    lines = [
        f"🎬 <b><i>Media Information</i></b>\n",
        f"<b>Filename :</b> <code>{ospath.basename(file_path)}</code>",
        f"<b>Format   :</b> <code>{fmt.get('format_long_name', 'Unknown')}</code>",
        f"<b>Size     :</b> <code>{size_str}</code>",
        f"<b>Duration :</b> <code>{duration_str}</code>",
        f"<b>Bitrate  :</b> <code>{bitrate_str}</code>\n",
    ]

    if video_streams:
        v = video_streams[0]
        w = v.get("width", 0)
        h = v.get("height", 0)
        codec = v.get("codec_name", "unknown")
        fps = v.get("avg_frame_rate", "N/A")
        lines.append(f"📹 <b><u>Video Stream</u></b>")
        lines.append(f"• <b>Codec      :</b> <code>{codec}</code>")
        lines.append(f"• <b>Resolution :</b> <code>{w}x{h}</code>")
        lines.append(f"• <b>Framerate  :</b> <code>{fps}</code>\n")

    if audio_streams:
        lines.append(f"🔊 <b><u>Audio Streams ({len(audio_streams)})</u></b>")
        for idx, a in enumerate(audio_streams, 1):
            acodec = a.get("codec_name", "unknown")
            channels = a.get("channels", 2)
            lang = a.get("tags", {}).get("language", "und")
            lines.append(f"• <b>Track {idx} :</b> <code>{acodec}</code> ({channels} ch) [{lang}]")
        lines.append("")

    if sub_streams:
        lines.append(f"💬 <b><u>Subtitles ({len(sub_streams)})</u></b>")
        for idx, s in enumerate(sub_streams, 1):
            slang = s.get("tags", {}).get("language", "und")
            stitle = s.get("tags", {}).get("title", "")
            disp = f"[{slang}] {stitle}".strip()
            lines.append(f"• <b>Sub {idx}   :</b> <code>{disp}</code>")

async def status_bar(down_msg, speed, percentage, eta, done, left, engine, status_type=None, task_title=None, task_ctx=None):
    """WZML-X styled status card with live Group Link, metrics, and multi-task support."""
    import html
    from colab_leecher.utility.task_manager import ACTIVE_TASKS
    cur_time = time()

    if task_ctx:
        # Update metrics on the task context
        task_ctx.speed = speed
        task_ctx.percentage = percentage
        task_ctx.eta = eta
        task_ctx.done = done
        task_ctx.left = left
        if engine:
            task_ctx.engine = engine
        if status_type:
            task_ctx.status_state = status_type
        if task_title:
            task_ctx.task_title = task_title

        # Check task-level throttle (at least 3.5s between message edits to avoid floodwait)
        if cur_time - getattr(task_ctx, "last_update", 0) < 3.5:
            return
        task_ctx.last_update = cur_time

        from colab_leecher.utility.task_manager import CHAT_STATUS_MSGS
        if task_ctx.chat_id in CHAT_STATUS_MSGS:
            target_msg = CHAT_STATUS_MSGS[task_ctx.chat_id]
            task_ctx.status_msg = target_msg
        else:
            target_msg = task_ctx.status_msg

        user_name = task_ctx.user_name or "Owner"
        mode_name = task_ctx.mode.capitalize()
        task_id_str = f" #{task_ctx.task_id}"
        stop_cmd = f"/cancel_{task_ctx.task_id}"
    else:
        if not isTimeOver():
            return
        target_msg = MSG.status_msg
        user_name = BOT.TaskUser or "Owner"
        mode_name = "Leech" if BOT.Mode.mode != "mirror" else "Mirror"
        task_id_str = ""
        stop_cmd = "/cancel"

    if target_msg is None:
        return

    # If multiple tasks are active, automatically render the combined multi-task dashboard!
    if len(ACTIVE_TASKS) > 1:
        full_text = render_multi_status(ACTIVE_TASKS)
        markup = keyboard_for_multi(ACTIVE_TASKS)
    else:
        bar = get_progress_bar_string(percentage)
        status_label = status_type or (task_ctx.status_state if task_ctx else BOT.StatusState) or ("Upload" if ("Pyrofork" in engine or "DzGram" in engine or "UPLOAD" in str(down_msg)) else "Download")
        engine_name = engine or (task_ctx.engine if task_ctx else BOT.CurrentEngine) or "Aria2c"

        start_t = task_ctx.start_time if task_ctx else BotTimes.task_start
        elapsed_time = getTime(max(1, (datetime.now() - start_t).seconds))
        name = task_title or (task_ctx.task_title if task_ctx else Messages.download_name) or "Task Processing..."

        src_link = Messages.src_link if (Messages.src_link and Messages.src_link != "https://t.me") else ""
        src_link_header = f" | <a href='{src_link}'>Channel 🔗</a>" if src_link else ""
        src_status_link = f"<a href='{src_link}'>{status_label}</a>" if src_link else status_label
        src_stop_link = f" | <a href='{src_link}'>Task 📌</a>" if src_link else ""

        header = "<blockquote><b><i>TGColabX 🚀 Live Status</i></b></blockquote>\n\n"

        task_card = f"<b>1.</b> <b><code>{html.escape(name)}</code></b>{task_id_str}\n"
        task_card += f"<blockquote>╭ <b>Task By {html.escape(user_name)}</b>{src_link_header}\n"
        task_card += f"┊ <code>{bar}</code> <i>{percentage:.2f}%</i>\n"
        task_card += f"┊ <code>Status   :</code> <b>{src_status_link}</b>\n"
        task_card += f"┊ <code>Done     :</code> <i>{done}</i>\n"
        task_card += f"┊ <code>Total    :</code> <i>{left}</i>\n"
        task_card += f"┊ <code>Speed    :</code> <i>{speed}</i>\n"
        task_card += f"┊ <code>ETA      :</code> <i>{eta}</i>\n"
        task_card += f"┊ <code>Past     :</code> <i>{elapsed_time}</i>\n"
        task_card += f"┊ <code>Engine   :</code> <i>{engine_name}</i>\n"
        task_card += f"╰ <code>Mode     :</code> <i>#{mode_name}</i></blockquote>\n"
        task_card += f"<blockquote>» <code>Stop :</code> <i>{stop_cmd}</i>{src_stop_link}</blockquote>"

        if BOT.Queue:
            task_card += f"\n\n⏳ <b><u>Queued Tasks ({len(BOT.Queue)})</u></b>\n"
            for q_idx, q_item in enumerate(BOT.Queue, start=1):
                q_mode = getattr(q_item, "mode", "leech").capitalize()
                q_user = getattr(q_item, "user_name", "User")
                q_name = getattr(q_item, "task_title", "Task")
                task_card += f"• <code>#{q_idx}</code> <b>{html.escape(q_name)}</b> <i>({q_mode} by {html.escape(q_user)})</i>\n"

        full_text = header + task_card + sysINFO()
        markup = keyboard(task_ctx)

    try:
        try:
            await target_msg.edit_text(
                text=full_text,
                reply_markup=markup,
                disable_web_page_preview=True,
            )
        except Exception:
            await target_msg.edit_text(
                text=full_text,
                reply_markup=markup,
            )
    except FloodWait as f:
        logging.warning(f"FloodWait in status_bar: {f.value}s")
        if task_ctx:
            task_ctx.last_update = cur_time + f.value
        else:
            BotTimes.current_time = time() + f.value
    except BadRequest as e:
        err_str = str(e)
        if "MESSAGE_NOT_MODIFIED" in err_str:
            pass
        elif "MESSAGE_ID_INVALID" in err_str or "MESSAGE_EMPTY" in err_str:
            if task_ctx:
                try:
                    new_msg = await colab_bot.send_message(
                        chat_id=task_ctx.chat_id,
                        text=full_text,
                        reply_markup=markup,
                        disable_web_page_preview=True
                    )
                    from colab_leecher.utility.task_manager import CHAT_STATUS_MSGS
                    CHAT_STATUS_MSGS[task_ctx.chat_id] = new_msg
                    task_ctx.status_msg = new_msg
                except Exception:
                    pass
        else:
            logging.error(f"Status update error: {err_str}")
    except Exception as e:
        err_str = str(e)
        if "MESSAGE_NOT_MODIFIED" not in err_str:
            logging.error(f"Error Updating Status bar: {err_str}")


def keyboard(task_ctx=None):
    """Clean interactive action buttons supporting concurrent task cancellation."""
    from colab_leecher.utility.task_manager import ACTIVE_TASKS
    if len(ACTIVE_TASKS) > 1:
        return keyboard_for_multi(ACTIVE_TASKS)

    # Automatically bind to active task if single task is running
    if not task_ctx and ACTIVE_TASKS:
        task_ctx = next(iter(ACTIVE_TASKS.values()))

    buttons = [
        [
            InlineKeyboardButton("≡ Settings", callback_data="settings"),
            InlineKeyboardButton("♻️ Refresh", callback_data="ref"),
        ],
    ]
    if task_ctx:
        buttons.append([
            InlineKeyboardButton("❌ Stop Task", callback_data=f"cancel_{task_ctx.task_id}"),
            InlineKeyboardButton("🛑 Stop All", callback_data="cancel_all"),
        ])
    elif BOT.Queue:
        buttons.append([
            InlineKeyboardButton("❌ Stop Active", callback_data="cancel"),
            InlineKeyboardButton("🚫 Clear Queue", callback_data="clear_queue"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton("❌ Stop / Cancel", callback_data="cancel"),
        ])
    return InlineKeyboardMarkup(buttons)


def keyboard_for_multi(active_tasks_dict: dict):
    """Action buttons when multiple concurrent downloads are active."""
    buttons = [
        [
            InlineKeyboardButton("≡ Settings", callback_data="settings"),
            InlineKeyboardButton("♻️ Refresh", callback_data="ref"),
        ],
    ]
    row = []
    for t_id in list(active_tasks_dict.keys())[:4]:
        row.append(InlineKeyboardButton(f"❌ Stop #{t_id}", callback_data=f"cancel_{t_id}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton("🛑 Stop All Tasks", callback_data="cancel_all"),
    ])
    return InlineKeyboardMarkup(buttons)


def quality_buttons(request_id: str = ""):
    """WZML-X interactive quality selector buttons tied to unique task request."""
    suffix = f" {request_id}" if request_id else ""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎬 1080p", callback_data=f"qual 1080{suffix}"),
                InlineKeyboardButton("🎬 720p", callback_data=f"qual 720{suffix}"),
                InlineKeyboardButton("🎬 480p", callback_data=f"qual 480{suffix}"),
            ],
            [
                InlineKeyboardButton("🎬 360p", callback_data=f"qual 360{suffix}"),
                InlineKeyboardButton("⭐ Best", callback_data=f"qual best{suffix}"),
                InlineKeyboardButton("🎵 MP3", callback_data=f"qual mp3{suffix}"),
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data=f"cancel{suffix}"),
            ],
        ]
    )


def render_multi_status(active_tasks_dict: dict) -> str:
    """Renders a unified status dashboard for ALL currently running concurrent tasks."""
    import html
    if not active_tasks_dict:
        return ""

    if len(active_tasks_dict) > 1:
        header = f"<blockquote><b><i>TGColabX 🚀 Live Status ({len(active_tasks_dict)} Active Tasks)</i></b></blockquote>\n\n"
    else:
        header = "<blockquote><b><i>TGColabX 🚀 Live Status</i></b></blockquote>\n\n"
    cards = []

    for idx, (t_id, ctx) in enumerate(active_tasks_dict.items(), start=1):
        bar = get_progress_bar_string(ctx.percentage)
        elapsed = getTime(max(1, (datetime.now() - ctx.start_time).seconds))
        c_name = ctx.task_title or "Task Processing..."
        u_name = ctx.user_name or "User"
        mode_name = ctx.mode.capitalize()
        engine = ctx.engine or "Aria2c"
        state = ctx.status_state or "Download"

        card = f"<b>{idx}.</b> <b><code>{html.escape(c_name)}</code></b> <i>(#{t_id})</i>\n"
        card += f"<blockquote>╭ <b>By {html.escape(u_name)}</b> | <i>{engine}</i>\n"
        card += f"┊ <code>{bar}</code> <i>{ctx.percentage:.2f}%</i>\n"
        card += f"┊ <code>Status:</code> <b>{state}</b> | <code>Speed:</code> <i>{ctx.speed}</i>\n"
        card += f"┊ <code>Done  :</code> <i>{ctx.done}</i> / <i>{ctx.left}</i> | <code>ETA:</code> <i>{ctx.eta}</i>\n"
        card += f"╰ <code>Stop  :</code> <i>/cancel_{t_id}</i> | <code>Past:</code> <i>{elapsed}</i></blockquote>\n"
        cards.append(card)

    return header + "\n".join(cards) + sysINFO()
