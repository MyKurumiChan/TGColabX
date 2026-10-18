# TGColabX - Based on WZML-X & XronTrix10
# Copyright (c) 2024-2026 TGColabX

import os
import json
import shutil
import logging
import subprocess
from asyncio import sleep
from datetime import datetime
from os import makedirs, path as ospath

try:
    import GPUtil
except ImportError:
    GPUtil = None

from colab_leecher import colab_bot
from colab_leecher.utility.settings_manager import SettingsManager
from colab_leecher.utility.variables import BOT, MSG, BotTimes, Paths, Messages
from colab_leecher.utility.helper import (
    getSize,
    fileType,
    keyboard,
    multipartArchive,
    sizeUnit,
    speedETA,
    status_bar,
    sysINFO,
    getTime,
)


async def videoConverter(file: str):
    global BOT, MSG, BotTimes

    async def msg_updater(c: int, tr, engine: str):
        messg = f"╭「" + "░" * c + "█" + "░" * (11 - c) + "」"
        messg += f"\n├⏳ **Status »** __Running 🏃🏼‍♂️__\n├🕹 **Attempt »** __{tr}__"
        messg += f"\n├⚙️ **Engine »** __{engine}__\n├💪🏼 **Handler »** __{core}__"
        messg += f"\n╰🍃 **Time Spent »** __{getTime((datetime.now() - BotTimes.start_time).seconds)}__"
        try:
            if MSG.status_msg:
                await MSG.status_msg.edit_text(
                    text=Messages.task_msg + mtext + messg + sysINFO(),
                    reply_markup=keyboard(),
                )
        except Exception:
            pass

    name, ext = ospath.splitext(file)

    if ext.lower() in [".mkv", ".mp4"]:
        return file

    c, out_file, Err = 0, f"{name}.{BOT.Options.video_out}", False
    gpu = 0
    if GPUtil:
        try:
            gpu = len(GPUtil.getAvailable())
        except Exception:
            gpu = 0

    quality = "-preset slow -qp 0" if BOT.Options.convert_quality else ""

    if gpu >= 1:
        cmd = f"ffmpeg -y -i '{file}' {quality} -c:v h264_nvenc -c:a copy '{out_file}'"
        core = "GPU"
    else:
        cmd = f"ffmpeg -y -i '{file}' {quality} -c:v libx264 -c:a copy '{out_file}'"
        core = "CPU"

    mtext = f"<b>🎥 Converting Video »</b>\n\n<code>{ospath.basename(file)}</code>\n\n"

    proc = subprocess.Popen(cmd, shell=True)

    while proc.poll() is None:
        await msg_updater(c, "1st", "FFmpeg 🏍")
        c = (c + 1) % 12
        await sleep(3)

    if ospath.exists(out_file) and getSize(out_file) == 0:
        os.remove(out_file)
        Err = True
    elif not ospath.exists(out_file):
        Err = True

    # 2nd attempt: If audio copy failed, transcode audio to aac
    if Err:
        cmd2 = f"ffmpeg -y -i '{file}' {quality} -c:v libx264 -c:a aac -strict -2 '{out_file}'"
        core = "CPU"
        proc = subprocess.Popen(cmd2, shell=True)
        while proc.poll() is None:
            await msg_updater(c, "2nd", "FFmpeg-AAC 🏍")
            c = (c + 1) % 12
            await sleep(3)

    if ospath.exists(out_file) and getSize(out_file) == 0:
        try:
            os.remove(out_file)
        except Exception:
            pass
        Err = True
    elif not ospath.exists(out_file):
        Err = True
    else:
        Err = False

    if Err:
        logging.error("This Video Can't Be Converted !")
        return file
    else:
        try:
            os.remove(file)
        except Exception:
            pass
        return out_file


async def sizeChecker(file_path: str, remove: bool = False, task_ctx=None) -> bool:
    if not ospath.exists(file_path):
        return False
    file_size = os.stat(file_path).st_size

    # Check user custom split size or bot settings
    user_id = getattr(task_ctx, "user_id", None) or (task_ctx.chat_id if task_ctx else 0)
    u_conf = SettingsManager.get_user_settings(user_id) if user_id else {}
    b_conf = SettingsManager.get_bot_settings()

    is_prem = hasattr(colab_bot, "me") and getattr(colab_bot.me, "is_premium", False)
    max_allowed_mb = 3900 if is_prem else 1950

    custom_mb = u_conf.get("split_size_mb", 0)
    if custom_mb and int(custom_mb) > 50:
        max_size_mb = min(int(custom_mb), max_allowed_mb)
    else:
        user_split = str(u_conf.get("split_video", "2.0GB")).upper().strip()
        if "500" in user_split:
            max_size_mb = 500
        elif "1.5" in user_split or "1500" in user_split:
            max_size_mb = 1500
        elif "1" in user_split or "1000" in user_split:
            max_size_mb = 1000
        elif "4" in user_split and is_prem:
            max_size_mb = 3900
        else:
            max_size_mb = 1950

    max_size_bytes = max_size_mb * 1024 * 1024
    if file_size <= max_size_bytes:
        return False

    temp_zpath = task_ctx.temp_zpath if task_ctx else Paths.temp_zpath
    makedirs(temp_zpath, exist_ok=True)
    _, filename = ospath.split(file_path)
    filename_lower = filename.lower()

    logging.info(f"File {filename} ({sizeUnit(file_size)}) exceeds split target ({max_size_mb} MB). Splitting...")

    f_type = fileType(file_path)
    if f_type == "video":
        success = await splitVideo(file_path, max_size_mb, remove, target_dir=temp_zpath, task_ctx=task_ctx)
        if not success or not os.listdir(temp_zpath):
            logging.warning("Video splitting produced no parts or failed, falling back to 7z split archive...")
            await archive(file_path, is_split=True, remove=remove, split_size_mb=max_size_mb, target_dir=temp_zpath, task_ctx=task_ctx)
    elif any(filename_lower.endswith(ext) for ext in [".zip", ".rar", ".7z", ".tar", ".gz"]):
        await splitArchive(file_path, max_size_bytes, target_dir=temp_zpath, task_ctx=task_ctx)
    else:
        await archive(file_path, is_split=True, remove=remove, split_size_mb=max_size_mb, target_dir=temp_zpath, task_ctx=task_ctx)

    await sleep(1)
    return True


async def archive(path: str, is_split: bool = False, remove: bool = False, split_size_mb: int = 1950, target_dir: str = None, task_ctx=None):
    global BOT, Messages
    target_dir = target_dir or (task_ctx.temp_zpath if task_ctx else Paths.temp_zpath)
    makedirs(target_dir, exist_ok=True)

    dir_p, p_name = ospath.split(path)
    custom_name = (task_ctx.options.get("custom_name") if task_ctx else None) or BOT.Options.custom_name
    if custom_name:
        name = custom_name
    elif ospath.isfile(path):
        name = ospath.basename(path)
    else:
        name = (task_ctx.task_title if task_ctx else Messages.download_name) or "Archive"

    zip_pswd = (task_ctx.options.get("zip_pswd") if task_ctx else None) or BOT.Options.zip_pswd
    split_flag = f"-v{split_size_mb}m" if is_split else ""
    pswd_flag = f"-p{zip_pswd}" if zip_pswd else ""

    out_file = ospath.join(target_dir, f"{name}.7z")
    cmd = f'7z a -mx=0 {split_flag} {pswd_flag} "{out_file}" "{path}"'

    status_head = f"<b>🔐 COMPRESSING » </b>\n\n<code>{name}</code>\n"
    start_t = datetime.now()
    total_size = getSize(path)
    total_in_unit = sizeUnit(total_size)

    proc = subprocess.Popen(cmd, shell=True)
    while proc.poll() is None:
        written = getSize(target_dir)
        speed_string, eta, percentage = speedETA(start_t, written, total_size)
        await status_bar(
            down_msg=status_head,
            speed=speed_string,
            percentage=percentage,
            eta=getTime(eta),
            done=sizeUnit(written),
            left=total_in_unit,
            engine="TGColabX-7z 🔒",
            status_type="Compressing",
            task_title=name,
            task_ctx=task_ctx,
        )
        await sleep(1)

    if remove:
        if ospath.isfile(path):
            try:
                os.remove(path)
            except Exception:
                pass
        else:
            try:
                shutil.rmtree(path)
            except Exception:
                pass


async def extract(zip_filepath: str, remove: bool = False, temp_unzip_path: str = None, task_ctx=None):
    global BOT, Paths, Messages
    temp_unzip_path = temp_unzip_path or (task_ctx.temp_unzip_path if task_ctx else Paths.temp_unzip_path)
    makedirs(temp_unzip_path, exist_ok=True)

    _, filename = ospath.split(zip_filepath)
    status_head = f"<b>📂 EXTRACTING »</b>\n\n<code>{filename}</code>\n"
    pwd = (task_ctx.options.get("unzip_pswd") if task_ctx else None) or BOT.Options.unzip_pswd
    p = f"-p{pwd}" if pwd else ""
    name, ext = ospath.splitext(filename)
    file_pattern, real_name, total_ = "", name, 0

    if ext == ".rar":
        if "part" in name:
            cmd = f"unrar x -kb -idq {p} '{zip_filepath}' '{temp_unzip_path}'"
            file_pattern = "rar"
        else:
            cmd = f"unrar x {p} '{zip_filepath}' '{temp_unzip_path}'"
    elif ext == ".tar":
        cmd = f"tar -xvf '{zip_filepath}' -C '{temp_unzip_path}'"
    elif ext == ".gz":
        cmd = f"tar -zxvf '{zip_filepath}' -C '{temp_unzip_path}'"
    else:
        cmd = f"7z x {p} '{zip_filepath}' -o'{temp_unzip_path}'"
        if ext == ".001":
            file_pattern = "7z"
        elif ext == ".z01":
            file_pattern = "zip"

    if file_pattern == "":
        total_ = getSize(zip_filepath)
        total = sizeUnit(total_)
    else:
        real_name, total_ = multipartArchive(zip_filepath, file_pattern, False)
        total = sizeUnit(total_)

    start_t = datetime.now()
    proc = subprocess.Popen(cmd, shell=True)

    while proc.poll() is None:
        written = getSize(temp_unzip_path)
        speed_string, eta, percentage = speedETA(start_t, written, total_)
        await status_bar(
            down_msg=status_head,
            speed=speed_string,
            percentage=percentage,
            eta=getTime(eta),
            done=sizeUnit(written),
            left=total,
            engine="TGColabX-Unzip 🔓",
            status_type="Extracting",
            task_title=filename,
            task_ctx=task_ctx,
        )
        await sleep(1)

    if remove:
        multipartArchive(zip_filepath, file_pattern, True)
        if ospath.exists(zip_filepath):
            try:
                os.remove(zip_filepath)
            except Exception:
                pass

    if task_ctx:
        task_ctx.task_title = real_name
    else:
        Messages.download_name = real_name


async def splitArchive(file_path: str, max_size_bytes: int, target_dir: str = None, task_ctx=None):
    target_dir = target_dir or (task_ctx.temp_zpath if task_ctx else Paths.temp_zpath)
    makedirs(target_dir, exist_ok=True)

    _, filename = ospath.split(file_path)
    new_path = ospath.join(target_dir, filename)
    status_head = f"<b>✂️ SPLITTING ARCHIVE » </b>\n\n<code>{filename}</code>\n"
    total_size = ospath.getsize(file_path)
    start_t = datetime.now()

    with open(file_path, "rb") as f:
        chunk = f.read(max_size_bytes)
        i = 1
        bytes_written = 0
        while chunk:
            ext = str(i).zfill(3)
            output_filename = f"{new_path}.{ext}"

            with open(output_filename, "wb") as out:
                out.write(chunk)

            bytes_written += len(chunk)
            speed_string, eta, percentage = speedETA(start_t, bytes_written, total_size)
            await status_bar(
                down_msg=status_head,
                speed=speed_string,
                percentage=percentage,
                eta=getTime(eta),
                done=sizeUnit(bytes_written),
                left=sizeUnit(total_size),
                engine="Archive Split ✂️",
                status_type="Splitting",
                task_title=filename,
                task_ctx=task_ctx,
            )
            chunk = f.read(max_size_bytes)
            i += 1


async def splitVideo(file_path: str, max_size_mb: int, remove: bool = False, target_dir: str = None, task_ctx=None) -> bool:
    target_dir = target_dir or (task_ctx.temp_zpath if task_ctx else Paths.temp_zpath)
    makedirs(target_dir, exist_ok=True)

    _, filename = ospath.split(file_path)
    just_name, extension = ospath.splitext(filename)

    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", file_path]
    bitrate = None
    try:
        output = subprocess.check_output(cmd)
        video_info = json.loads(output)
        bitrate = float(video_info["format"]["bit_rate"])
    except Exception:
        logging.warning("Could not get video bitrate, estimating default 1500k")
        bitrate = 1500 * 1024

    target_size_bits = max_size_mb * 8 * 1024 * 1024
    duration = max(30, int(target_size_bits / max(bitrate, 500000)))

    out_pattern = ospath.join(target_dir, f"{just_name}.part%03d{extension}")
    cmd_split = f'ffmpeg -y -i "{file_path}" -c copy -f segment -segment_time {duration} -reset_timestamps 1 "{out_pattern}"'

    status_head = f"<b>✂️ SPLITTING VIDEO » </b>\n\n<code>{filename}</code>\n"
    start_t = datetime.now()
    total_size = getSize(file_path)
    total_in_unit = sizeUnit(total_size)

    proc = subprocess.Popen(cmd_split, shell=True)
    while proc.poll() is None:
        written = getSize(target_dir)
        speed_string, eta, percentage = speedETA(start_t, written, total_size)
        await status_bar(
            down_msg=status_head,
            speed=speed_string,
            percentage=percentage,
            eta=getTime(eta),
            done=sizeUnit(written),
            left=total_in_unit,
            engine="FFmpeg Split ✂️",
            status_type="Splitting",
            task_title=filename,
            task_ctx=task_ctx,
        )
        await sleep(1)

    generated = [f for f in os.listdir(target_dir) if ospath.isfile(ospath.join(target_dir, f))]
    if generated:
        logging.info(f"Video successfully split into {len(generated)} parts in {target_dir}.")
        if remove and ospath.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        return True
    return False
