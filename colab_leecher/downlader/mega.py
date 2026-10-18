# TGColabX - Based on WZML-X & XronTrix10
# Copyright (c) 2024-2026 TGColabX

import logging
from os import makedirs
from datetime import datetime
from colab_leecher.utility.helper import status_bar, getTime
from colab_leecher.utility.variables import BotTimes, Messages, Paths
from pymegatools import Megatools, MegaError


async def megadl(link: str, num: int):
    global BotTimes, Messages
    BotTimes.task_start = datetime.now()
    makedirs(Paths.down_path, exist_ok=True)
    mega = Megatools()
    try:
        await mega.async_download(link, progress=pro_for_mega, path=Paths.down_path)
    except MegaError as e:
        logging.error(f"Mega download error: {e}")
    except Exception as e:
        logging.error(f"Mega unexpected error: {e}")


async def pro_for_mega(stream, process):
    line = stream[-1]
    file_name = "N/A"
    percentage = 0
    downloaded_size = "N/A"
    total_size = "N/A"
    speed = "N/A"
    eta = "Unknown"
    try:
        ok = line.split(":")
        file_name = ok[0].strip()
        ok = ok[1].split()
        percentage = float(ok[0][:-1])
        downloaded_size = ok[2] + " " + ok[3]
        total_size = ok[7] + " " + ok[8]
        speed = ok[9][1:] + " " + ok[10][:-1]

        remaining_bytes = float(ok[7]) - float(ok[2])
        bytes_per_second = float(ok[9][1:]) * (1024 if ok[10][-1] == 'K' else 1)
        if bytes_per_second != 0:
            remaining_seconds = remaining_bytes / bytes_per_second
            eta = getTime(remaining_seconds)
    except Exception:
        pass

    Messages.download_name = file_name
    Messages.status_head = f"<b>📥 DOWNLOADING FROM MEGA » </b>\n\n<b>🏷️ Name » </b><code>{file_name}</code>\n"

    await status_bar(
        down_msg=Messages.status_head,
        speed=speed,
        percentage=percentage,
        eta=eta,
        done=downloaded_size,
        left=total_size,
        engine="Mega 💾",
    )
