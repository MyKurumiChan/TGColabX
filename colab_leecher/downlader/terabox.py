# TGColabX - Based on WZML-X & XronTrix10
# Copyright (c) 2024-2026 TGColabX

import aiohttp
import logging
from colab_leecher.utility.variables import Aria2c
from colab_leecher.utility.handler import cancelTask
from colab_leecher.downlader.aria2 import aria2_Download


async def terabox_download(link: str, index: int):
    global Aria2c
    payload = {"url": f"{link}"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    fast_download_url = ""
    slow_download_url = ""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://ytshorts.savetube.me/api/v1/terabox-downloader",
                data=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                response.raise_for_status()
                json_response = await response.json()
                resolutions = json_response.get("response", [{}])[0].get("resolutions", {})
                fast_download_url = resolutions.get("Fast Download", "")
                slow_download_url = resolutions.get("HD Video", "") or resolutions.get("Fast Download", "")

        target_url = fast_download_url or slow_download_url
        if not target_url:
            await cancelTask("Terabox: Could not extract download stream URL.")
            return

        Aria2c.link_info = False
        await aria2_Download(target_url, index)

    except Exception as e:
        logging.error(f"Terabox download exception: {e}")
        await cancelTask(f"Terabox extraction error: {e}")
