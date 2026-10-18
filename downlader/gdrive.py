# TGColabX - Based on WZML-X & XronTrix10
# Copyright (c) 2024-2026 TGColabX

import io
import logging
import pickle
from natsort import natsorted
from re import search as re_search
from os import makedirs, path as ospath
from urllib.parse import parse_qs, urlparse
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from colab_leecher.utility.handler import cancelTask
from colab_leecher.utility.helper import sizeUnit, getTime, speedETA, status_bar
from colab_leecher.utility.variables import Gdrive, Messages, Paths, BotTimes, Transfer


async def build_service():
    global Gdrive
    if ospath.exists(Paths.access_token):
        with open(Paths.access_token, "rb") as token:
            creds = pickle.load(token)
            Gdrive.service = build("drive", "v3", credentials=creds)
    else:
        await cancelTask(
            "token.pickle NOT FOUND! Stop the bot and generate token.pickle, then try again."
        )


async def g_DownLoad(link, num):
    global down_msg
    down_msg = f"<b>📥 DOWNLOADING FROM » </b><i>🔗Link {str(num).zfill(2)}</i>\n\n<b>🏷️ Name » </b><code>{Messages.download_name}</code>\n"
    file_id = await getIDFromURL(link)
    if not file_id:
        return
    meta = getFileMetadata(file_id)

    if meta.get("mimeType") == "application/vnd.google-apps.folder":
        await gDownloadFolder(file_id, Paths.down_path)
    else:
        await gDownloadFile(file_id, Paths.down_path)


async def getIDFromURL(link: str):
    if "folders" in link or "file" in link:
        regex = r"https:\/\/drive\.google\.com\/(?:drive(.*?)\/folders\/|file(.*?)?\/d\/)([-\w]+)"
        res = re_search(regex, link)
        if res is None:
            await cancelTask("G-Drive ID not found in Link.")
            logging.error("G-Drive ID not found.")
            return None
        else:
            return res.group(3)
    parsed = urlparse(link)
    q = parse_qs(parsed.query)
    if "id" in q and q["id"]:
        return q["id"][0]
    return None


def getFilesByFolderID(folder_id):
    page_token = None
    files = []
    while True:
        response = (
            Gdrive.service.files()
            .list(
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                q=f"'{folder_id}' in parents and trashed = false",
                spaces="drive",
                pageSize=200,
                fields="nextPageToken, files(id, name, mimeType, size, shortcutDetails)",
                orderBy="folder, name",
                pageToken=page_token,
            )
            .execute()
        )
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if page_token is None:
            break
    return files


def getFileMetadata(file_id):
    return (
        Gdrive.service.files()
        .get(fileId=file_id, supportsAllDrives=True, fields="name, id, mimeType, size")
        .execute()
    )


def get_Gfolder_size(folder_id):
    try:
        query = f"trashed = false and '{folder_id}' in parents"
        results = (
            Gdrive.service.files()
            .list(
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                q=query,
                fields="files(id, mimeType, size)",
            )
            .execute()
        )

        total_size = 0
        items = results.get("files", [])

        folders_without_size = [
            item["id"]
            for item in items
            if item.get("size") is None and item.get("mimeType") == "application/vnd.google-apps.folder"
        ]

        for item in items:
            if "size" in item:
                total_size += int(item["size"])

        for fid in folders_without_size:
            total_size += get_Gfolder_size(fid)

        return total_size

    except HttpError as error:
        logging.error(f"Error while checking size: {error}")
        return 0


async def gDownloadFile(file_id, path):
    try:
        file = getFileMetadata(file_id)
    except HttpError as error:
        err = "Sorry, the specified Google Drive file does not exist or is not accessible."
        logging.info(err)
        await cancelTask(err)
        return
    else:
        if file.get("mimeType", "").startswith("application/vnd.google-apps"):
            err = "The specified ID is a Google Docs/Sheets/Slides file. Direct download is unsupported."
            logging.info(err)
            await cancelTask(err)
            return
        else:
            try:
                makedirs(path, exist_ok=True)
                file_name = file.get("name", f"drivefile_{file_id}")
                file_dest = ospath.join(path, file_name)
                file_contents = io.BytesIO()

                request = Gdrive.service.files().get_media(
                    fileId=file_id, supportsAllDrives=True
                )

                file_downloader = MediaIoBaseDownload(
                    file_contents, request, chunksize=70 * 1024 * 1024
                )

                f_size = int(file.get("size", 0))
                total_target = Transfer.total_down_size if Transfer.total_down_size > 0 else f_size

                done = False
                while done is False:
                    status, done = file_downloader.next_chunk()
                    file_contents.seek(0)
                    with open(file_dest, "ab") as f:
                        f.write(file_contents.getvalue())
                    file_contents.seek(0)
                    file_contents.truncate()

                    file_d_size = int(status.progress() * f_size)
                    down_done = sum(Transfer.down_bytes) + file_d_size
                    speed_string, eta, percentage = speedETA(
                        BotTimes.task_start, down_done, total_target
                    )
                    await status_bar(
                        down_msg=down_msg,
                        speed=speed_string,
                        percentage=percentage,
                        eta=getTime(eta),
                        done=sizeUnit(down_done),
                        left=sizeUnit(total_target),
                        engine="G-Api ♻️",
                    )
                Transfer.down_bytes.append(f_size)

            except HttpError as error:
                if error.resp.status == 403 and "User Rate Limit Exceeded" in str(error):
                    logging.error("Download quota for the file has been exceeded.")
                    await cancelTask("Download quota for the file has been exceeded.")
                    return
                else:
                    logging.error(f"HttpError While Downloading: {error}")
                    await cancelTask(f"HttpError While Downloading: {error}")
                    return

            except Exception as e:
                logging.error(f"Error downloading: {e}")
                await cancelTask(f"Error downloading: {e}")
                return


async def gDownloadFolder(folder_id, path):
    folder_meta = getFileMetadata(folder_id)
    folder_name = folder_meta.get("name", f"folder_{folder_id}")
    folder_path = ospath.join(path, folder_name)
    makedirs(folder_path, exist_ok=True)
    result = getFilesByFolderID(folder_id)
    if not result:
        return
    result = natsorted(result, key=lambda k: k.get("name", ""))
    for item in result:
        file_id = item["id"]
        shortcut_details = item.get("shortcutDetails")
        if shortcut_details is not None:
            file_id = shortcut_details["targetId"]
            mime_type = shortcut_details["targetMimeType"]
        else:
            mime_type = item.get("mimeType")
        if mime_type == "application/vnd.google-apps.folder":
            await gDownloadFolder(file_id, folder_path)
        else:
            await gDownloadFile(file_id, folder_path)
