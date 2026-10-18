# TGColabX - Based on WZML-X & XronTrix10
# Copyright (c) 2024-2026 TGColabX

import os
import re
import asyncio
import logging
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime
from colab_leecher.utility.helper import sizeUnit, status_bar, getSize
from colab_leecher.utility.variables import BOT, Aria2c, Paths, Messages, BotTimes

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


async def aria2_Download(link: str, num: int, task_ctx=None):
    global BotTimes, Messages

    down_dir = task_ctx.down_path if task_ctx else Paths.down_path
    os.makedirs(down_dir, exist_ok=True)
    name_d = (task_ctx.options.get("custom_name") if task_ctx else None) or Messages.download_name or get_Aria2c_Name(link, task_ctx)

    if task_ctx:
        task_ctx.task_title = name_d
        task_ctx.engine = "Aria2c 🧨"
        task_ctx.status_state = "Download"
    else:
        Messages.download_name = name_d
        BotTimes.task_start = datetime.now()
        Messages.status_head = f"<b>📥 DOWNLOADING FROM » </b><i>🔗Link {str(num).zfill(2)}</i>\n\n<b>🏷️ Name » </b><code>{name_d}</code>\n"

    success = await _run_aria2_process(link, down_dir, name_d, task_ctx, split_connections=True)

    # Fallback 1: Single connection retry if multi-connection was blocked by server/CDN
    if not success and not (task_ctx and task_ctx.is_cancelled):
        logging.warning(f"Aria2c multi-connection failed for {link}. Retrying with single connection mode...")
        success = await _run_aria2_process(link, down_dir, name_d, task_ctx, split_connections=False)

    # Fallback 2: Streamed direct Python download if aria2c executable fails on specific TLS or CDN handshakes
    if not success and not (task_ctx and task_ctx.is_cancelled):
        logging.warning(f"Aria2c failed completely for {link}. Attempting resilient Python direct stream download...")
        success = await _streamed_python_download(link, down_dir, name_d, task_ctx)

    if task_ctx and task_ctx.is_cancelled:
        return

    # Post-download verification
    dl_size = getSize(down_dir)
    if dl_size == 0 or not success:
        err_msg = task_ctx.error if (task_ctx and task_ctx.error) else f"Download failed: Server returned 0 bytes for {link}"
        if task_ctx:
            task_ctx.error = err_msg
        raise RuntimeError(err_msg)


async def _run_aria2_process(link: str, down_dir: str, name_d: str, task_ctx, split_connections: bool = True) -> bool:
    splits = "16" if split_connections else "1"
    command = [
        "aria2c",
        f"-x{splits}",
        f"-s{splits}",
        f"-j{splits}",
        "--min-split-size=1M",
        "--seed-time=0",
        "--summary-interval=1",
        "--max-tries=5",
        "--retry-wait=3",
        "--check-certificate=false",
        f"--user-agent={BROWSER_UA}",
        "--header=Accept: */*",
        "--header=Accept-Language: en-US,en;q=0.9",
        "--console-log-level=notice",
        "--allow-overwrite=true",
        "-d",
        down_dir,
    ]

    custom_name = (task_ctx.options.get("custom_name") if task_ctx else None) or BOT.Options.custom_name
    if custom_name:
        command.extend(["-o", custom_name])

    command.append(link)

    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:
        logging.error(f"Failed to start aria2c process: {e}")
        return False

    buffer = ""
    while True:
        if task_ctx and task_ctx.is_cancelled:
            logging.info(f"Task {task_ctx.task_id} was cancelled, terminating aria2c process.")
            try:
                proc.terminate()
            except Exception:
                pass
            break

        try:
            chunk = await proc.stdout.read(1024)
        except Exception:
            break
        if not chunk:
            if proc.returncode is not None or proc.stdout.at_eof():
                break
            await asyncio.sleep(0.1)
            continue

        buffer += chunk.decode("utf-8", errors="ignore")
        while "\r" in buffer or "\n" in buffer:
            pos_r = buffer.find("\r")
            pos_n = buffer.find("\n")
            if pos_r != -1 and (pos_n == -1 or pos_r < pos_n):
                line = buffer[:pos_r]
                buffer = buffer[pos_r + 1 :]
            else:
                line = buffer[:pos_n]
                buffer = buffer[pos_n + 1 :]
            line = line.strip()
            if line:
                await on_output(line, name_d, task_ctx)

    exit_code = await proc.wait()
    if exit_code != 0 and not (task_ctx and task_ctx.is_cancelled):
        error_output = (await proc.stderr.read()).decode("utf-8", errors="ignore")
        logging.error(f"aria2c exited with code {exit_code}: {error_output.strip()}")
        if task_ctx:
            task_ctx.error = f"Aria2 error code {exit_code}: {error_output.strip()}"
        return False

    return True


async def _streamed_python_download(link: str, down_dir: str, default_name: str, task_ctx) -> bool:
    """Fallback streaming downloader using standard urllib with progress reporting."""
    loop = asyncio.get_event_loop()

    def _sync_download():
        target_name = (task_ctx.options.get("custom_name") if task_ctx else None) or default_name or "downloaded_file"
        headers = {
            "User-Agent": BROWSER_UA,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        req = urllib.request.Request(link, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            # Parse Content-Disposition if available
            disp = resp.headers.get("Content-Disposition", "")
            if disp and "filename=" in disp and not (task_ctx and task_ctx.options.get("custom_name")):
                match = re.search(r'filename\*?=["\']?(?:UTF-8\'\')?([^"\';]+)', disp)
                if match:
                    target_name = urllib.parse.unquote(match.group(1).strip())

            out_file = os.path.join(down_dir, target_name)
            total_size = int(resp.headers.get("Content-Length", 0) or 0)
            if task_ctx and total_size > 0:
                task_ctx.total_size = total_size

            dl_bytes = 0
            block_size = 1024 * 1024  # 1MB
            with open(out_file, "wb") as f:
                while True:
                    if task_ctx and task_ctx.is_cancelled:
                        break
                    chunk = resp.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    dl_bytes += len(chunk)
                    if task_ctx and total_size > 0:
                        task_ctx.done = sizeUnit(dl_bytes)
                        task_ctx.percentage = round((dl_bytes / total_size) * 100, 2)

            return os.path.exists(out_file) and os.path.getsize(out_file) > 0

    try:
        return await loop.run_in_executor(None, _sync_download)
    except Exception as e:
        logging.error(f"Streamed Python download error: {e}")
        if task_ctx:
            task_ctx.error = str(e)
        return False


def get_Aria2c_Name(link: str, task_ctx=None) -> str:
    custom_name = (task_ctx.options.get("custom_name") if task_ctx else None) or BOT.Options.custom_name
    if custom_name:
        return custom_name

    # Instant URL basename extraction without blocking the asyncio loop
    clean_url = str(link).split("?")[0].rstrip("/")
    fallback_name = clean_url.split("/")[-1]
    if fallback_name and not fallback_name.lower().startswith(("index.htm", "download")):
        return urllib.parse.unquote(fallback_name)
    return "download_file"


async def on_output(output: str, task_name: str = "", task_ctx=None):
    match_prog = re.search(r"([\d\.]+[A-Za-z]+)/([\d\.]+[A-Za-z]+)\(([\d\.]+)%\)", output)
    match_dl = re.search(r"DL:([\d\.]+[A-Za-z]+)", output)
    match_eta = re.search(r"ETA:([\w\d]+)", output)

    if match_prog:
        Aria2c.link_info = True
        downloaded = match_prog.group(1)
        total = match_prog.group(2)
        try:
            pct = float(match_prog.group(3))
        except ValueError:
            pct = 0.0

        speed = f"{match_dl.group(1)}/s" if match_dl else "0 B/s"
        eta = match_eta.group(1) if match_eta else "N/A"

        if task_ctx:
            task_ctx.speed = speed
            task_ctx.percentage = pct
            task_ctx.eta = eta
            task_ctx.done = downloaded
            task_ctx.left = total

        await status_bar(
            down_msg=f"<b>📥 DOWNLOADING » </b><code>{task_name}</code>\n",
            speed=speed,
            percentage=pct,
            eta=eta,
            done=downloaded,
            left=total,
            engine="Aria2c 🧨",
            task_title=task_name,
            task_ctx=task_ctx,
        )
