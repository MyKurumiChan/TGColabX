# TGColabX - Based on WZML-X & XronTrix10
# Copyright (c) 2024-2026 TGColabX

import os
import re
import json
import base64
import random
import logging
import aiohttp
from datetime import datetime
from colab_leecher.utility.helper import sizeUnit, getTime, status_bar, getSize
from colab_leecher.utility.settings_manager import SettingsManager

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


class AsyncProgressFileReader:
    """Async file reader with live progress tracking for aiohttp streaming uploads."""
    def __init__(self, filepath, callback=None):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.total_size = os.path.getsize(filepath)
        self.callback = callback
        self.uploaded = 0
        self.file_obj = None

    async def __aenter__(self):
        self.file_obj = open(self.filepath, "rb")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.file_obj:
            self.file_obj.close()

    def read(self, chunk_size=1024 * 512):
        chunk = self.file_obj.read(chunk_size)
        if chunk:
            self.uploaded += len(chunk)
            if self.callback:
                self.callback(self.uploaded, self.total_size)
        return chunk


# ==================== GOFILE UPLOADER ====================

async def get_gofile_server() -> str:
    """Fetches an active best Gofile upload server."""
    url = "https://api.gofile.io/servers"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={"User-Agent": BROWSER_UA}, timeout=15) as resp:
                data = await resp.json()
                if data.get("status") == "ok" and data.get("data", {}).get("servers"):
                    servers = data["data"]["servers"]
                    return random.choice(servers)["name"]
    except Exception as e:
        logging.warning(f"Error fetching Gofile server: {e}")
    return "store1"


async def upload_file_to_gofile(file_path: str, token: str = "", folder_id: str = "", task_ctx=None) -> dict:
    """
    Uploads a single file to Gofile using official API.
    Supports user/bot API token and custom folder ID.
    Returns: {"url": download_link, "name": filename, "size": filesize}
    """
    user_id = task_ctx.chat_id if task_ctx else None
    if not token and user_id:
        u_conf = SettingsManager.get_user_settings(user_id)
        token = u_conf.get("gofile_token", "")
    if not token:
        b_conf = SettingsManager.get_bot_settings()
        token = b_conf.get("gofile_token", "")

    server = await get_gofile_server()
    upload_url = f"https://{server}.gofile.io/uploadfile"
    file_name = os.path.basename(file_path)
    total_size = os.path.getsize(file_path)
    start_t = datetime.now()

    def progress(uploaded, total):
        elapsed = max(1, (datetime.now() - start_t).seconds)
        speed = uploaded / elapsed
        pct = round((uploaded / total) * 100, 2) if total > 0 else 0
        if task_ctx:
            task_ctx.done = sizeUnit(uploaded)
            task_ctx.left = sizeUnit(total)
            task_ctx.speed = f"{sizeUnit(speed)}/s"
            task_ctx.percentage = pct
            task_ctx.status_state = "Gofile Upload"
            task_ctx.engine = "Gofile 📁"

    logging.info(f"Uploading {file_name} ({sizeUnit(total_size)}) to Gofile server {server}...")

    # Upload using streaming multipart
    data = aiohttp.FormData()
    if token:
        data.add_field("token", token)
    if folder_id:
        data.add_field("folderId", folder_id)

    async with AsyncProgressFileReader(file_path, progress) as pfile:
        data.add_field("file", pfile.file_obj, filename=file_name)
        async with aiohttp.ClientSession() as session:
            async with session.post(upload_url, data=data, timeout=aiohttp.ClientTimeout(total=3600)) as resp:
                res = await resp.json(content_type=None)

    if res.get("status") == "ok":
        d_page = res["data"]["downloadPage"]
        logging.info(f"Gofile upload complete! Link: {d_page}")
        return {
            "url": d_page,
            "name": file_name,
            "size": total_size,
            "code": res["data"].get("code"),
            "file_id": res["data"].get("fileId"),
        }
    else:
        raise RuntimeError(f"Gofile upload error: {res.get('status')}")


async def upload_path_to_gofile(path: str, user_id: int = None, task_ctx=None) -> list:
    """Uploads a file or directory of files to Gofile. Returns list of uploaded items."""
    results = []
    if os.path.isfile(path):
        res = await upload_file_to_gofile(path, task_ctx=task_ctx)
        results.append(res)
    elif os.path.isdir(path):
        for root, _, files in os.walk(path):
            for f in sorted(files):
                if task_ctx and task_ctx.is_cancelled:
                    break
                fp = os.path.join(root, f)
                res = await upload_file_to_gofile(fp, task_ctx=task_ctx)
                results.append(res)
    return results


# ==================== PIXELDRAIN UPLOADER ====================

async def upload_file_to_pixeldrain(file_path: str, api_key: str = "", task_ctx=None) -> dict:
    """
    Uploads a single file to Pixeldrain using PUT /api/file/{filename}.
    Supports user personal API key or global bot setting.
    Returns: {"url": download_link, "name": filename, "size": filesize, "id": file_id}
    """
    user_id = task_ctx.chat_id if task_ctx else None
    if not api_key and user_id:
        u_conf = SettingsManager.get_user_settings(user_id)
        api_key = u_conf.get("pixeldrain_token", "")
    if not api_key:
        b_conf = SettingsManager.get_bot_settings()
        api_key = b_conf.get("pixeldrain_token", "")

    file_name = os.path.basename(file_path).replace(" ", ".")
    total_size = os.path.getsize(file_path)
    start_t = datetime.now()
    upload_url = f"https://pixeldrain.com/api/file/{file_name}"

    headers = {"User-Agent": BROWSER_UA}
    if api_key:
        auth_str = base64.b64encode(f":{api_key}".encode()).decode()
        headers["Authorization"] = f"Basic {auth_str}"

    def progress(uploaded, total):
        elapsed = max(1, (datetime.now() - start_t).seconds)
        speed = uploaded / elapsed
        pct = round((uploaded / total) * 100, 2) if total > 0 else 0
        if task_ctx:
            task_ctx.done = sizeUnit(uploaded)
            task_ctx.left = sizeUnit(total)
            task_ctx.speed = f"{sizeUnit(speed)}/s"
            task_ctx.percentage = pct
            task_ctx.status_state = "Pixeldrain Upload"
            task_ctx.engine = "Pixeldrain ⚡"

    logging.info(f"Uploading {file_name} ({sizeUnit(total_size)}) to Pixeldrain...")

    async with AsyncProgressFileReader(file_path, progress) as pfile:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.put(upload_url, data=pfile.file_obj, timeout=aiohttp.ClientTimeout(total=3600)) as resp:
                res = await resp.json(content_type=None)

    if res.get("success") or "id" in res:
        file_id = res.get("id")
        dl_link = f"https://pixeldrain.com/u/{file_id}"
        logging.info(f"Pixeldrain upload complete! Link: {dl_link}")
        return {
            "url": dl_link,
            "id": file_id,
            "name": file_name,
            "size": total_size,
        }
    else:
        raise RuntimeError(f"Pixeldrain upload error: {res.get('message', 'Upload rejected')}")


async def create_pixeldrain_list(title: str, file_ids: list, api_key: str = "") -> str:
    """Creates a Pixeldrain List containing multiple uploaded files."""
    if not api_key:
        return ""
    headers = {
        "User-Agent": BROWSER_UA,
        "Authorization": f"Basic {base64.b64encode(f':{api_key}'.encode()).decode()}",
    }
    payload = {
        "title": title,
        "anonymous": False,
        "files": [{"id": fid} for fid in file_ids],
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post("https://pixeldrain.com/api/list", json=payload, timeout=20) as resp:
            data = await resp.json(content_type=None)
            if data.get("success") and "id" in data:
                return f"https://pixeldrain.com/l/{data['id']}"
    return ""


async def upload_path_to_pixeldrain(path: str, user_id: int = None, task_ctx=None) -> list:
    """Uploads file or directory to Pixeldrain, packaging directories into a list if possible."""
    results = []
    if os.path.isfile(path):
        res = await upload_file_to_pixeldrain(path, task_ctx=task_ctx)
        results.append(res)
    elif os.path.isdir(path):
        file_ids = []
        for root, _, files in os.walk(path):
            for f in sorted(files):
                if task_ctx and task_ctx.is_cancelled:
                    break
                fp = os.path.join(root, f)
                res = await upload_file_to_pixeldrain(fp, task_ctx=task_ctx)
                results.append(res)
                if res.get("id"):
                    file_ids.append(res["id"])

        # Try list creation for multiple files
        if len(file_ids) > 1:
            try:
                list_url = await create_pixeldrain_list(os.path.basename(path), file_ids)
                if list_url:
                    results.append({"url": list_url, "name": f"List: {os.path.basename(path)}", "size": getSize(path)})
            except Exception as le:
                logging.warning(f"Pixeldrain list creation note: {le}")
    return results

