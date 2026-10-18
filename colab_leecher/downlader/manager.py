# TGColabX - Based on WZML-X & XronTrix10
# Copyright (c) 2024-2026 TGColabX

import logging
from natsort import natsorted
from datetime import datetime
from asyncio import sleep
from colab_leecher.downlader.mega import megadl
from colab_leecher.utility.handler import cancelTask
from colab_leecher.downlader.terabox import terabox_download
from colab_leecher.downlader.ytdl import YTDL_Status, get_YT_Name
from colab_leecher.downlader.aria2 import aria2_Download, get_Aria2c_Name
from colab_leecher.downlader.telegram import TelegramDownload, media_Identifier, get_media_info
from colab_leecher.downlader.direct_resolver import (
    is_gofile,
    is_pixeldrain,
    resolve_any_link,
)
from colab_leecher.utility.variables import (
    BOT,
    Transfer,
    MSG,
    Messages,
    Aria2c,
    BotTimes,
)
from colab_leecher.utility.helper import (
    keyboard,
    sysINFO,
    is_google_drive,
    is_mega,
    is_terabox,
    is_ytdl_link,
    is_telegram,
    is_torrent_or_magnet,
)
from colab_leecher.downlader.gdrive import (
    build_service,
    g_DownLoad,
    get_Gfolder_size,
    getFileMetadata,
    getIDFromURL,
)


async def downloadManager(source, is_ytdl: bool, task_ctx=None):
    message = "\n<b>Please Wait...</b> ⏳\n<i>Processing Media...</i> 🐬"
    BotTimes.task_start = datetime.now()
    logging.info(f"downloadManager starting with {len(source)} items. is_ytdl={is_ytdl}")

    target_stat_msg = task_ctx.status_msg if (task_ctx and task_ctx.status_msg) else MSG.status_msg

    if is_ytdl:
        try:
            for i, link in enumerate(source):
                if task_ctx and task_ctx.is_cancelled:
                    logging.info(f"Task {task_ctx.task_id} cancelled during downloadManager.")
                    return
                BOT.CurrentTaskIndex = i + 1
                BOT.ActiveTasks = source[i:]
                logging.info(f"[Download {i+1}/{len(source)}] Starting yt-dlp download: {link}")
                await YTDL_Status(link, i + 1, task_ctx)
                logging.info(f"[Download {i+1}/{len(source)}] yt-dlp download completed.")

            if target_stat_msg:
                try:
                    await target_stat_msg.edit_text(
                        text=Messages.task_msg + Messages.status_head + message + sysINFO(),
                        reply_markup=keyboard(task_ctx),
                        disable_web_page_preview=True,
                    )
                except Exception:
                    pass
        except Exception as Error:
            logging.error(f"Error While Downloading via yt-dlp: {Error}")
            await cancelTask(f"Download Error: {str(Error)}", task_id=(task_ctx.task_id if task_ctx else None))
            return
    else:
        for i, link in enumerate(source):
            if task_ctx and task_ctx.is_cancelled:
                logging.info(f"Task {task_ctx.task_id} cancelled during downloadManager.")
                return
            BOT.CurrentTaskIndex = i + 1
            BOT.ActiveTasks = source[i:]
            logging.info(f"[Download {i+1}/{len(source)}] Starting download: {link}")
            try:
                user_id = task_ctx.chat_id if task_ctx else None
                pwd = task_ctx.options.get("zip_pswd", "") if task_ctx else ""

                if is_google_drive(link):
                    await g_DownLoad(link, i + 1)

                elif is_telegram(link):
                    await TelegramDownload(link, i + 1, task_ctx)

                elif is_ytdl_link(link):
                    await YTDL_Status(link, i + 1, task_ctx)
                    if target_stat_msg:
                        try:
                            await target_stat_msg.edit_text(
                                text=Messages.task_msg + Messages.status_head + message + sysINFO(),
                                reply_markup=keyboard(task_ctx),
                            )
                        except Exception:
                            pass

                elif is_mega(link):
                    await megadl(link, i + 1)

                elif is_terabox(link):
                    tera_dn = f"<b>PLEASE WAIT ⌛</b>\n\n__Generating Download Link For__\n\n<code>{link}</code>"
                    try:
                        if target_stat_msg:
                            await target_stat_msg.edit_text(
                                text=tera_dn + sysINFO(), reply_markup=keyboard(task_ctx)
                            )
                    except Exception as e1:
                        logging.warning(f"Couldn't Update text: {e1}")
                    await terabox_download(link, i + 1)

                elif is_torrent_or_magnet(link):
                    err = "Torrent / Magnet links are strictly prohibited by Google Colab policies."
                    logging.error(err)
                    await cancelTask(err, task_id=(task_ctx.task_id if task_ctx else None))
                    return

                else:
                    # Master Link Resolver: handles Pixeldrain, Gofile, Mediafire, Buzzheavier, Solidfiles, redirect links, or generic direct URLs
                    resolved_items = resolve_any_link(link, user_id=user_id, password=pwd)
                    for r_item in resolved_items:
                        direct_link = r_item["url"]
                        if r_item.get("name") and task_ctx and not task_ctx.options.get("custom_name"):
                            task_ctx.options["custom_name"] = r_item["name"]
                            task_ctx.task_title = r_item["name"]

                        if task_ctx:
                            task_ctx.status_text = "Fetching info..."
                        else:
                            aria2_dn = f"<b>PLEASE WAIT ⌛</b>\n\n__Getting Download Info For__\n\n<code>{direct_link}</code>"
                            try:
                                if target_stat_msg:
                                    await target_stat_msg.edit_text(
                                        text=aria2_dn + sysINFO(), reply_markup=keyboard(task_ctx)
                                    )
                            except Exception as e1:
                                logging.warning(f"Couldn't Update text: {e1}")

                        Aria2c.link_info = False
                        await aria2_Download(direct_link, i + 1, task_ctx)

            except Exception as Error:
                logging.error(f"Error While Downloading: {Error}")
                await cancelTask(f"Download Error: {str(Error)}", task_id=(task_ctx.task_id if task_ctx else None))
                return


async def calDownSize(sources, task_ctx=None):
    total = 0
    user_id = task_ctx.chat_id if task_ctx else None
    pwd = task_ctx.options.get("zip_pswd", "") if task_ctx else ""

    for link in natsorted(sources):
        try:
            if is_google_drive(link):
                await build_service()
                id = await getIDFromURL(link)
                meta = getFileMetadata(id)
                if meta.get("mimeType") == "application/vnd.google-apps.folder":
                    total += get_Gfolder_size(id)
                else:
                    total += int(meta.get("size", 0))
            elif is_telegram(link):
                media, message = await media_Identifier(link)
                if media is not None and message is not None:
                    _, size = get_media_info(media, message)
                    total += size
            else:
                items = resolve_any_link(link, user_id=user_id, password=pwd)
                for it in items:
                    total += it.get("size", 0) or 0
        except Exception:
            pass

    Transfer.total_down_size += total
    if task_ctx:
        task_ctx.total_size = total


async def get_d_name(link, task_ctx=None):
    user_id = task_ctx.chat_id if task_ctx else None
    pwd = task_ctx.options.get("zip_pswd", "") if task_ctx else ""

    try:
        if is_google_drive(link):
            await build_service()
            id = await getIDFromURL(link)
            meta = getFileMetadata(id)
            name = meta.get("name", "Unknown_Gdrive_File")
        elif is_telegram(link):
            media, message = await media_Identifier(link)
            if media and message:
                name, _ = get_media_info(media, message)
            else:
                name = "Telegram_File"
        elif is_ytdl_link(link):
            name = await get_YT_Name(link)
        else:
            items = resolve_any_link(link, user_id=user_id, password=pwd)
            if items and items[0].get("name"):
                name = items[0]["name"]
            else:
                name = get_Aria2c_Name(items[0]["url"] if items else link, task_ctx)
    except Exception:
        name = get_Aria2c_Name(link, task_ctx)

    Messages.download_name = name
    if task_ctx:
        task_ctx.task_title = name
    return name
