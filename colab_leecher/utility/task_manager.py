# TGColabX - Based on WZML-X & XronTrix10
# Copyright (c) 2024-2026 TGColabX

import shutil
import logging
from time import time
from datetime import datetime
from asyncio import sleep, get_event_loop
from os import makedirs, path as ospath
from colab_leecher import OWNER, colab_bot, DUMP_ID
from colab_leecher.downlader.manager import calDownSize, get_d_name, downloadManager
from colab_leecher.utility.settings_manager import SettingsManager
from colab_leecher.utility.helper import (
    getSize,
    keyboard,
    sysINFO,
    is_google_drive,
    is_telegram,
    is_ytdl_link,
    is_mega,
    is_terabox,
    is_torrent_or_magnet,
    is_gofile,
    is_pixeldrain,
    automated_video_merge,
    render_multi_status,
)
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from colab_leecher.uploader.cloud_uploader import (
    upload_path_to_gofile,
    upload_path_to_pixeldrain,
)
from colab_leecher.utility.handler import (
    Leech,
    Unzip_Handler,
    Zip_Handler,
    SendLogs,
    cancelTask,
)
from colab_leecher.utility.variables import (
    BOT,
    MSG,
    BotTimes,
    Messages,
    Paths,
    Transfer,
)

ACTIVE_TASKS = {}       # task_id -> TaskContext
CHAT_STATUS_MSGS = {}   # chat_id -> Message (Live unified status message per chat)


class TaskContext:
    def __init__(self, task_id: str, chat_id: int, user_name: str, mode: str, mode_type: str, is_ytdl: bool, links: list, options: dict, user_id: int = 0):
        self.task_id = task_id
        self.chat_id = chat_id
        self.user_id = user_id or (chat_id if chat_id > 0 else 0)
        self.user_name = user_name
        self.mode = mode               # "leech" or "mirror"
        self.mode_type = mode_type     # "normal", "zip", "unzip", "undzip"
        self.is_ytdl = is_ytdl
        self.links = list(links)
        self.options = dict(options)
        self.delivered_to = "chat"

        # Isolated directory tree for this task
        self.work_path = ospath.join(Paths.WORK_PATH, f"task_{task_id}")
        self.down_path = ospath.join(self.work_path, "Downloads")
        self.temp_zpath = ospath.join(self.work_path, "Leeched_Files")
        self.temp_unzip_path = ospath.join(self.work_path, "Unzipped_Files")
        self.temp_dirleech_path = ospath.join(self.work_path, "dir_leech_temp")
        self.temp_files_dir = ospath.join(self.work_path, "leech_temp")
        self.thumbnail_ytdl = ospath.join(self.work_path, "ytdl_thumbnails")
        self.samples_dir = ospath.join(self.work_path, "samples")
        self.screenshots_dir = ospath.join(self.work_path, "screenshots")

        # Live status tracking
        clean_name = ospath.basename(str(links[0]).split("?")[0].rstrip("/")) if links else "Task Processing..."
        self.task_title = options.get("custom_name") or clean_name
        self.status_state = "Download"

        has_cookies = SettingsManager.has_cookies(chat_id)
        if is_ytdl:
            self.engine = "yt-dlp 🏮 (🍪 Cookies)" if has_cookies else "yt-dlp 🏮"
        elif is_pixeldrain(links[0] if links else ""):
            self.engine = "Pixeldrain ⚡"
        elif is_gofile(links[0] if links else ""):
            self.engine = "Gofile 📁"
        else:
            self.engine = "Aria2c 🧨"

        self.speed = "0 B/s"
        self.percentage = 0.0
        self.eta = "N/A"
        self.done = "0 B"
        self.left = "N/A"
        self.total_size = 0
        self.up_bytes = []
        self.start_time = datetime.now()
        self.last_update = 0
        self.is_cancelled = False
        self.status_msg = None
        self.sent_msg = None
        self.asyncio_task = None


async def task_starter(message, text):
    try:
        await message.delete()
    except Exception:
        pass
    try:
        src_request_msg = await message.reply_text(text)
    except Exception:
        src_request_msg = await colab_bot.send_message(chat_id=message.chat.id, text=text)
    return src_request_msg


async def dispatch_task(mode_type: str, mode: str, is_ytdl: bool, links: list, user_name: str, chat_id: int, options: dict, message=None, user_id: int = 0):
    """
    WZML-X True Concurrent Multi-Download Engine:
    - Multiple links start immediately in parallel!
    - Single window status updates in-place without cluttering chat history.
    """
    bot_conf = SettingsManager.get_bot_settings()
    max_parallel = bot_conf.get("max_parallel_tasks", 5)

    if not links:
        return

    if not user_id and message and message.from_user:
        user_id = message.from_user.id
    if not user_id:
        user_id = chat_id if chat_id > 0 else 0

    tasks_to_start = []
    for link in links:
        # Duplicate detection: prevent re-downloading active or queued links
        duplicate_ctx = None
        for active_tid, active_ctx in list(ACTIVE_TASKS.items()):
            if link in active_ctx.links:
                duplicate_ctx = active_ctx
                break
        if not duplicate_ctx:
            for q_ctx in list(BOT.Queue):
                if link in q_ctx.links:
                    duplicate_ctx = q_ctx
                    break

        if duplicate_ctx:
            logging.info(f"Duplicate task detected for link {link} (matching Task #{duplicate_ctx.task_id})")
            if message:
                try:
                    await message.reply_text(
                        f"⚠️ <b>Duplicate Task Detected!</b>\n"
                        f"This link is already running in Task <code>#{duplicate_ctx.task_id}</code> by <b>{duplicate_ctx.user_name}</b>.\n"
                        f"<i>Skipping duplicate to save bandwidth.</i>"
                    )
                except Exception:
                    pass
            continue

        t_id = f"{int(time() * 1000) % 1000000:06d}"
        ctx = TaskContext(
            task_id=t_id,
            chat_id=chat_id,
            user_name=user_name,
            mode=mode,
            mode_type=mode_type,
            is_ytdl=is_ytdl,
            links=[link],
            options=options,
            user_id=user_id,
        )

        can_start = (max_parallel == 0) or (len(ACTIVE_TASKS) < max_parallel)
        if can_start:
            ACTIVE_TASKS[t_id] = ctx
            tasks_to_start.append(ctx)
            BOT.State.task_going = True
            logging.info(f"[Parallel Engine] Task #{t_id} queued for start! Total active tasks: {len(ACTIVE_TASKS)}")
        else:
            BOT.Queue.append(ctx)
            pos = len(BOT.Queue)
            if message:
                try:
                    await message.reply_text(
                        f"⏳ <b>Task Queued!</b> <code>#{t_id}</code> (Position: #{pos})\n"
                        f"<i>Max parallel downloads ({max_parallel}) active. Starts automatically once a slot frees up!</i>"
                    )
                except Exception:
                    pass

    # Auto-delete trigger command message to maintain a clean single-window chat
    if message:
        try:
            await message.delete()
        except Exception:
            pass

    # Single-Window Live Dashboard: Deploy or edit existing status card BEFORE running tasks
    old_stat = CHAT_STATUS_MSGS.get(chat_id)
    multi_txt = render_multi_status(ACTIVE_TASKS)
    new_stat_msg = None

    if old_stat:
        try:
            await old_stat.edit_text(
                multi_txt,
                reply_markup=keyboard(),
                disable_web_page_preview=True
            )
            new_stat_msg = old_stat
        except Exception:
            try:
                await old_stat.delete()
            except Exception:
                pass
            new_stat_msg = None

    if not new_stat_msg and ACTIVE_TASKS:
        try:
            new_stat_msg = await colab_bot.send_message(
                chat_id=chat_id,
                text=multi_txt,
                reply_markup=keyboard(),
                disable_web_page_preview=True
            )
        except Exception as e:
            logging.warning(f"Error posting single-window status card: {e}")

    if new_stat_msg:
        CHAT_STATUS_MSGS[chat_id] = new_stat_msg
        for t_c in ACTIVE_TASKS.values():
            if t_c.chat_id == chat_id:
                t_c.status_msg = new_stat_msg

    # Now launch task pipelines concurrently with bound status cards
    loop = get_event_loop()
    for ctx in tasks_to_start:
        if new_stat_msg:
            ctx.status_msg = new_stat_msg
        ctx.asyncio_task = loop.create_task(run_task_pipeline(ctx))


async def run_task_pipeline(task_ctx: TaskContext):
    """Executes the full download -> process -> upload pipeline for an isolated task."""
    try:
        makedirs(task_ctx.work_path, exist_ok=True)
        makedirs(task_ctx.down_path, exist_ok=True)
        makedirs(task_ctx.thumbnail_ytdl, exist_ok=True)

        target_chat = task_ctx.chat_id or OWNER

        # Bind to existing chat live status message or create if missing
        if target_chat in CHAT_STATUS_MSGS:
            task_ctx.status_msg = CHAT_STATUS_MSGS[target_chat]
        elif not task_ctx.status_msg:
            multi_txt = render_multi_status(ACTIVE_TASKS)
            try:
                task_ctx.status_msg = await colab_bot.send_message(
                    chat_id=target_chat,
                    text=multi_txt,
                    reply_markup=keyboard(task_ctx),
                    disable_web_page_preview=True,
                )
                CHAT_STATUS_MSGS[target_chat] = task_ctx.status_msg
            except Exception as e:
                logging.error(f"Failed to send task init message: {e}")

        # Dump channel tracking
        if DUMP_ID and str(DUMP_ID).strip() not in ["0", ""]:
            try:
                task_ctx.sent_msg = await colab_bot.send_message(
                    chat_id=DUMP_ID,
                    text=f"📥 <b>Task #{task_ctx.task_id} Initiated</b>\nLink: {task_ctx.links[0]}\nBy: {task_ctx.user_name}",
                )
            except Exception as de:
                logging.warning(f"Dump message error: {de}")

        if not task_ctx.sent_msg:
            task_ctx.sent_msg = task_ctx.status_msg

        # Initial name setup (instant, non-blocking)
        if not task_ctx.task_title or task_ctx.task_title == "Task Processing...":
            custom_n = task_ctx.options.get("custom_name")
            if custom_n:
                task_ctx.task_title = custom_n
            elif task_ctx.links:
                first_lk = task_ctx.links[0]
                clean_n = ospath.basename(str(first_lk).split("?")[0].rstrip("/"))
                task_ctx.task_title = clean_n if clean_n else "Download_Task"

        is_zip = task_ctx.mode_type == "zip"
        is_unzip = task_ctx.mode_type == "unzip"
        is_dualzip = task_ctx.mode_type == "undzip"

        if task_ctx.mode == "leech":
            await Do_Leech_Task(task_ctx, is_zip, is_unzip, is_dualzip)
        else:
            await Do_Mirror_Task(task_ctx, is_zip, is_unzip, is_dualzip)

    except Exception as e:
        logging.error(f"Unhandled exception in Task #{task_ctx.task_id}: {e}")
        try:
            if task_ctx.status_msg:
                await task_ctx.status_msg.edit_text(f"⚠️ <b>Task #{task_ctx.task_id} Error:</b> <code>{e}</code>")
        except Exception:
            pass

    finally:
        # Cleanup task workspace
        if task_ctx.task_id in ACTIVE_TASKS:
            del ACTIVE_TASKS[task_ctx.task_id]

        bot_conf = SettingsManager.get_bot_settings()
        if bot_conf.get("auto_clean_temp", True):
            if ospath.exists(task_ctx.work_path):
                try:
                    shutil.rmtree(task_ctx.work_path)
                except Exception:
                    pass

        # Send group completion notification if files were delivered to Bot DM or Dump Channel
        if task_ctx.chat_id < 0 and getattr(task_ctx, "delivered_to", None) in ["dm", "dump"]:
            try:
                bot_un = getattr(getattr(colab_bot, "me", None), "username", "")
                if task_ctx.delivered_to == "dm":
                    notif = (
                        f"✅ <b>Leech Completed for {task_ctx.user_name}!</b>\n"
                        f"📦 <code>{task_ctx.task_title}</code>\n\n"
                        f"<i>Files have been delivered directly to your Bot DM!</i>"
                    )
                    dm_markup = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📥 Open Bot DM", url=f"https://t.me/{bot_un}")]
                    ]) if bot_un else None
                else:
                    notif = (
                        f"✅ <b>Leech Completed for {task_ctx.user_name}!</b>\n"
                        f"📦 <code>{task_ctx.task_title}</code>\n\n"
                        f"<i>Files have been uploaded to your custom Dump Channel!</i>"
                    )
                    dm_markup = None

                await colab_bot.send_message(
                    chat_id=task_ctx.chat_id,
                    text=notif,
                    reply_markup=dm_markup,
                    disable_web_page_preview=True
                )
            except Exception as ne:
                logging.warning(f"Failed to send group leech completion note: {ne}")

        # Update live status card for remaining tasks if any
        if task_ctx.chat_id in CHAT_STATUS_MSGS:
            try:
                if ACTIVE_TASKS:
                    multi_txt = render_multi_status(ACTIVE_TASKS)
                    await CHAT_STATUS_MSGS[task_ctx.chat_id].edit_text(multi_txt, reply_markup=keyboard(), disable_web_page_preview=True)
                else:
                    try:
                        await CHAT_STATUS_MSGS[task_ctx.chat_id].delete()
                    except Exception:
                        pass
                    del CHAT_STATUS_MSGS[task_ctx.chat_id]
            except Exception:
                pass

        # Check queue and auto-start next pending task
        if BOT.Queue:
            next_ctx = BOT.Queue.pop(0)
            t_id = next_ctx.task_id
            ACTIVE_TASKS[t_id] = next_ctx
            loop = get_event_loop()
            next_ctx.asyncio_task = loop.create_task(run_task_pipeline(next_ctx))
            logging.info(f"[Queue Dispatch] Auto-starting task #{t_id} from queue.")

        BOT.State.task_going = len(ACTIVE_TASKS) > 0


async def Do_Leech_Task(task_ctx: TaskContext, is_zip: bool, is_unzip: bool, is_dualzip: bool):
    """Handles download, optional merge, archive, and Telegram upload for a task."""
    logging.info(f"Starting download for Task #{task_ctx.task_id}...")
    await downloadManager(task_ctx.links, task_ctx.is_ytdl, task_ctx)

    if task_ctx.is_cancelled:
        return

    task_ctx.total_size = getSize(task_ctx.down_path)
    if task_ctx.total_size == 0:
        err_msg = task_ctx.error or "Download failed: 0 bytes received from source. Check link or cookies."
        logging.error(f"Task #{task_ctx.task_id} produced 0 bytes in {task_ctx.down_path}: {err_msg}")
        await cancelTask(err_msg, task_id=task_ctx.task_id)
        return

    # Automated merge if requested
    if task_ctx.options.get("is_merge"):
        try:
            task_ctx.status_state = "Merging"
            task_ctx.engine = "FFmpeg 🎬"
            merged = automated_video_merge(task_ctx.down_path)
            if merged:
                task_ctx.task_title = ospath.basename(merged)
                task_ctx.total_size = getSize(task_ctx.down_path)
        except Exception as me:
            logging.error(f"Merge error in Task #{task_ctx.task_id}: {me}")

    # Upload stage: default is ALWAYS normal Telegram leech unless explicitly requested via flag
    upload_target = (task_ctx.options.get("upload_target") if task_ctx else None) or "telegram"
    upload_target = str(upload_target).lower()

    # Determine processed source directory
    if is_zip:
        await Zip_Handler(task_ctx.down_path, True, True, task_ctx)
        upload_source = task_ctx.temp_zpath
    elif is_unzip:
        await Unzip_Handler(task_ctx.down_path, True, task_ctx)
        upload_source = task_ctx.temp_unzip_path
    elif is_dualzip:
        await Unzip_Handler(task_ctx.down_path, True, task_ctx)
        await Zip_Handler(task_ctx.temp_unzip_path, True, True, task_ctx)
        upload_source = task_ctx.temp_zpath
    else:
        upload_source = task_ctx.down_path

    cloud_links = []

    # Gofile Upload
    if upload_target in ["gofile", "all"] and not task_ctx.is_cancelled:
        try:
            task_ctx.status_state = "Uploading (Gofile)"
            task_ctx.engine = "Gofile 📁"
            g_res = await upload_path_to_gofile(upload_source, user_id=task_ctx.chat_id, task_ctx=task_ctx)
            cloud_links.extend(g_res)
        except Exception as ge:
            logging.error(f"Gofile upload failed in Task #{task_ctx.task_id}: {ge}")

    # Pixeldrain Upload
    if upload_target in ["pixeldrain", "all"] and not task_ctx.is_cancelled:
        try:
            task_ctx.status_state = "Uploading (Pixeldrain)"
            task_ctx.engine = "Pixeldrain ⚡"
            p_res = await upload_path_to_pixeldrain(upload_source, user_id=task_ctx.chat_id, task_ctx=task_ctx)
            cloud_links.extend(p_res)
        except Exception as pe:
            logging.error(f"Pixeldrain upload failed in Task #{task_ctx.task_id}: {pe}")

    # Telegram MTProto Upload (DzGram / Pyrofork)
    if upload_target in ["telegram", "all"] and not task_ctx.is_cancelled:
        task_ctx.status_state = "Upload"
        task_ctx.engine = "DzGram ⚡"
        await Leech(upload_source, True, task_ctx)

    # Deliver cloud links if generated
    if cloud_links and not task_ctx.is_cancelled:
        btn_rows = []
        msg_text = "<b>☁️ Cloud Upload Completed!</b>\n\n"
        for item in cloud_links:
            u_name = item.get("name", "Download")
            u_url = item.get("url")
            u_size = sizeUnit(item.get("size", 0))
            msg_text += f"• <b>{u_name}</b> ({u_size})\n🔗 <code>{u_url}</code>\n\n"
            btn_rows.append([InlineKeyboardButton(f"📥 Open {u_name[:25]}", url=u_url)])
        markup = InlineKeyboardMarkup(btn_rows) if btn_rows else None
        target_chat = task_ctx.chat_id or OWNER
        try:
            await colab_bot.send_message(chat_id=target_chat, text=msg_text, reply_markup=markup, disable_web_page_preview=True)
        except Exception as ce:
            logging.error(f"Failed to send cloud links: {ce}")

    if not task_ctx.is_cancelled and upload_target in ["telegram", "all"]:
        await SendLogs(True, task_ctx)


async def Do_Mirror_Task(task_ctx: TaskContext, is_zip: bool, is_unzip: bool, is_dualzip: bool):
    """Handles download and cloud / Google Drive upload for a mirror task."""
    upload_target = (task_ctx.options.get("upload_target") if task_ctx else None) or "googledrive"
    upload_target = str(upload_target).lower()

    # If mirroring to Google Drive, check mount
    if upload_target in ["googledrive", "drive", "gdrive"] and not ospath.exists(Paths.MOUNTED_DRIVE):
        await cancelTask("Google Drive is NOT mounted in Colab! Use -up gofile or -up pixeldrain to mirror to cloud hosts.", task_id=task_ctx.task_id)
        return

    makedirs(Paths.mirror_dir, exist_ok=True)
    await downloadManager(task_ctx.links, task_ctx.is_ytdl, task_ctx)

    if task_ctx.is_cancelled:
        return

    task_ctx.total_size = getSize(task_ctx.down_path)
    if task_ctx.total_size == 0:
        err_msg = task_ctx.error or "Download failed: 0 bytes received from source. Check link or cookies."
        logging.error(f"Task #{task_ctx.task_id} produced 0 bytes in {task_ctx.down_path}: {err_msg}")
        await cancelTask(err_msg, task_id=task_ctx.task_id)
        return

    cdt_ = datetime.now().strftime("Uploaded » %Y-%m-%d %H:%M:%S")
    mirror_dir_ = ospath.join(Paths.mirror_dir, cdt_)

    if is_zip:
        await Zip_Handler(task_ctx.down_path, True, True, task_ctx)
        upload_source = task_ctx.temp_zpath
    elif is_unzip:
        await Unzip_Handler(task_ctx.down_path, True, task_ctx)
        upload_source = task_ctx.temp_unzip_path
    elif is_dualzip:
        await Unzip_Handler(task_ctx.down_path, True, task_ctx)
        await Zip_Handler(task_ctx.temp_unzip_path, True, True, task_ctx)
        upload_source = task_ctx.temp_zpath
    else:
        upload_source = task_ctx.down_path

    # Mirror to Gofile
    if upload_target == "gofile":
        task_ctx.status_state = "Mirroring (Gofile)"
        task_ctx.engine = "Gofile 📁"
        g_res = await upload_path_to_gofile(upload_source, user_id=task_ctx.chat_id, task_ctx=task_ctx)
        if g_res:
            links_txt = "\n".join([f"• <b>{r['name']}</b>: <code>{r['url']}</code>" for r in g_res])
            await colab_bot.send_message(chat_id=(task_ctx.chat_id or OWNER), text=f"📁 <b>Mirrored to Gofile!</b>\n\n{links_txt}")

    # Mirror to Pixeldrain
    elif upload_target == "pixeldrain":
        task_ctx.status_state = "Mirroring (Pixeldrain)"
        task_ctx.engine = "Pixeldrain ⚡"
        p_res = await upload_path_to_pixeldrain(upload_source, user_id=task_ctx.chat_id, task_ctx=task_ctx)
        if p_res:
            links_txt = "\n".join([f"• <b>{r['name']}</b>: <code>{r['url']}</code>" for r in p_res])
            await colab_bot.send_message(chat_id=(task_ctx.chat_id or OWNER), text=f"⚡ <b>Mirrored to Pixeldrain!</b>\n\n{links_txt}")

    # Mirror to Google Drive
    else:
        if ospath.exists(upload_source):
            shutil.copytree(upload_source, mirror_dir_)

    if not task_ctx.is_cancelled:
        await SendLogs(False, task_ctx)


async def add_to_queue_or_start(mode_type: str, mode: str, is_ytdl: bool, links: list, user_name: str, chat_id: int, options: dict):
    """Backward compatibility wrapper for dispatching tasks."""
    await dispatch_task(mode_type, mode, is_ytdl, links, user_name, chat_id, options)
    return True, 0
