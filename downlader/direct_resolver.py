# TGColabX - Based on WZML-X & XronTrix10
# Copyright (c) 2024-2026 TGColabX

import re
import json
import logging
import urllib.request
import urllib.parse
from hashlib import sha256
from time import time
from colab_leecher.utility.settings_manager import SettingsManager

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def is_gofile(url: str) -> bool:
    return bool(re.search(r"https?://(?:www\.)?gofile\.io/(?:d/|contents/)?([a-zA-Z0-9_-]+)", str(url)))


def is_pixeldrain(url: str) -> bool:
    return bool(re.search(r"https?://(?:www\.)?(?:pixeldrain\.com|pixeldra\.in)/(?:u|api/file|l)/([a-zA-Z0-9_-]+)", str(url)))


def is_mediafire(url: str) -> bool:
    return "mediafire.com" in str(url).lower()


def is_buzzheavier(url: str) -> bool:
    return any(x in str(url).lower() for x in ["buzzheavier.com", "bzzhr.co", "bzzhr.to"])


def is_solidfiles(url: str) -> bool:
    return "solidfiles.com" in str(url).lower()


def is_krakenfiles(url: str) -> bool:
    return "krakenfiles.com" in str(url).lower()


def is_uploadee(url: str) -> bool:
    return "upload.ee" in str(url).lower()


def get_gofile_id(url: str) -> str:
    match = re.search(r"gofile\.io/(?:d/|contents/)?([a-zA-Z0-9_-]+)", str(url))
    return match.group(1) if match else ""


def get_pixeldrain_id(url: str) -> str:
    match = re.search(r"(?:pixeldrain\.com|pixeldra\.in)/(?:u|api/file|l)/([a-zA-Z0-9_-]+)", str(url))
    return match.group(1) if match else ""


def resolve_pixeldrain(url: str, api_key: str = "", user_id: int = None) -> dict:
    """
    Resolves Pixeldrain file link to direct download link using Pixeldrain API.
    Supports user personal API key or global bot setting.
    Returns: {"url": direct_download_url, "name": filename, "size": filesize}
    """
    file_id = get_pixeldrain_id(url)
    if not file_id:
        raise ValueError("Invalid Pixeldrain URL")

    # Resolve token priority: passed api_key -> user setting -> bot setting
    token = api_key
    if not token and user_id:
        u_conf = SettingsManager.get_user_settings(user_id)
        token = u_conf.get("pixeldrain_token", "")
    if not token:
        b_conf = SettingsManager.get_bot_settings()
        token = b_conf.get("pixeldrain_token", "")

    api_url = f"https://pixeldrain.com/api/file/{file_id}/info"
    req = urllib.request.Request(api_url, headers={"User-Agent": BROWSER_UA})
    if token:
        import base64
        auth = base64.b64encode(f":{token}".encode()).decode()
        req.add_header("Authorization", f"Basic {auth}")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if not data.get("success", False):
                raise ValueError(data.get("message", "Pixeldrain file not found or inaccessible"))

            filename = data.get("name") or f"pixeldrain_{file_id}"
            filesize = data.get("size", 0)
            direct_url = f"https://pixeldrain.com/api/file/{file_id}?download"

            return {
                "url": direct_url,
                "name": filename,
                "size": filesize,
            }
    except Exception as e:
        logging.warning(f"Pixeldrain API info lookup failed: {e}. Using direct API endpoint.")
        return {
            "url": f"https://pixeldrain.com/api/file/{file_id}?download",
            "name": f"pixeldrain_{file_id}",
            "size": 0,
        }


def _get_gofile_token() -> str:
    """Creates a temporary guest account on Gofile to obtain an access token."""
    url = "https://api.gofile.io/accounts"
    headers = {
        "User-Agent": BROWSER_UA,
        "Accept": "*/*",
    }
    req = urllib.request.Request(url, headers=headers, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode())
            if res.get("status") == "ok":
                return res["data"]["token"]
    except Exception as e:
        logging.error(f"Gofile token creation failed: {e}")
    return ""


def resolve_gofile(url: str, password: str = "", custom_token: str = "", user_id: int = None) -> list:
    """
    Resolves Gofile link via official API v2.
    Supports user personal Gofile account token or global bot setting.
    Returns a list of dicts: [{"url": direct_download_url, "name": filename, "size": filesize}, ...]
    """
    content_id = get_gofile_id(url)
    if not content_id:
        raise ValueError("Invalid Gofile URL")

    # If password embedded with ::
    if "::" in url:
        password = url.split("::")[-1]

    # Resolve token priority: passed custom_token -> user setting -> bot setting -> guest token
    token = custom_token
    if not token and user_id:
        u_conf = SettingsManager.get_user_settings(user_id)
        token = u_conf.get("gofile_token", "")
    if not token:
        b_conf = SettingsManager.get_bot_settings()
        token = b_conf.get("gofile_token", "")
    if not token:
        token = _get_gofile_token()

    if not token:
        raise ValueError("Failed to obtain Gofile API token.")

    api_url = f"https://api.gofile.io/contents/{content_id}?cache=true"
    headers = {
        "User-Agent": BROWSER_UA,
        "Authorization": f"Bearer {token}",
        "Accept": "*/*",
    }

    if password:
        hashed_pw = sha256(password.encode()).hexdigest()
        api_url += f"&password={hashed_pw}"

    req = urllib.request.Request(api_url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        res = json.loads(resp.read().decode())

    status = res.get("status")
    if status != "ok":
        if "error-passwordWrong" in status:
            raise ValueError("Gofile link password is incorrect! Provide with -p <password> or link::password")
        elif "error-notFound" in status:
            raise ValueError("Gofile file/folder not found or has been deleted.")
        elif "error-notPublic" in status:
            raise ValueError("Gofile folder is not public.")
        else:
            raise ValueError(f"Gofile API Error: {status}")

    data = res.get("data", {})
    files = []

    # If it is a single file
    if data.get("type") == "file":
        files.append({
            "url": data.get("link"),
            "name": data.get("name"),
            "size": data.get("size", 0),
        })
    else:
        # It is a folder with children
        children = data.get("children", {})
        for child_id, child in children.items():
            if child.get("type") == "file":
                files.append({
                    "url": child.get("link"),
                    "name": child.get("name"),
                    "size": child.get("size", 0),
                })

    if not files:
        raise ValueError("No downloadable files found in this Gofile link.")

    return files


def resolve_mediafire(url: str) -> dict:
    """Extracts direct download link from Mediafire HTML page."""
    # If already a direct download link
    if re.search(r"https?://download\d+\.mediafire\.com/", url):
        return {"url": url, "name": None, "size": 0}

    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    # Look for download button
    match = re.search(r'href\s*=\s*["\'](https?://download\d+\.mediafire\.com/[^"\']+)["\']', html)
    if not match:
        match = re.search(r'id=["\']downloadButton["\'][^>]*href=["\']([^"\']+)["\']', html)
    if not match:
        match = re.search(r'aria-label=["\']Download file["\'][^>]*href=["\']([^"\']+)["\']', html)

    if match:
        direct_url = match.group(1)
        # Extract filename if available
        fn_match = re.search(r'<div class=["\']filename["\']>([^<]+)</div>', html)
        name = fn_match.group(1).strip() if fn_match else None
        return {"url": direct_url, "name": name, "size": 0}

    raise ValueError("Could not extract direct download link from Mediafire page.")


def resolve_buzzheavier(url: str) -> dict:
    """Resolves Buzzheavier / Bzzhr links to direct download link."""
    clean_url = url.split("?")[0].rstrip("/")
    if not clean_url.endswith("/download"):
        clean_url = f"{clean_url}/download"
    return {"url": clean_url, "name": None, "size": 0}


def resolve_solidfiles(url: str) -> dict:
    """Extracts direct stream/download URL from Solidfiles page."""
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    match = re.search(r'"downloadUrl":\s*"([^"]+)"', html)
    if match:
        direct_url = match.group(1)
        name_match = re.search(r'"name":\s*"([^"]+)"', html)
        name = name_match.group(1) if name_match else None
        return {"url": direct_url, "name": name, "size": 0}

    raise ValueError("Could not extract download URL from Solidfiles.")


RESOLVED_CACHE = {}

COMMON_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".ts", ".m4v",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso",
    ".mp3", ".flac", ".wav", ".m4a", ".aac", ".opus", ".ogg",
    ".pdf", ".epub", ".apk", ".exe", ".bin", ".dmg", ".pkg"
}


def resolve_generic_web(url: str) -> dict:
    """
    Follows HTTP redirects and extracts direct downloadable file URL,
    Content-Disposition filename, and Content-Length.
    Fast path: If URL path already contains a known file extension, returns immediately without network lag.
    """
    parsed = urllib.parse.urlparse(url)
    path_clean = parsed.path.rstrip("/")
    if path_clean:
        base = os.path.basename(path_clean)
        ext = os.path.splitext(base)[1].lower()
        if ext in COMMON_EXTENSIONS:
            clean_name = urllib.parse.unquote(base)
            return {"url": url, "name": clean_name, "size": 0}

    headers = {
        "User-Agent": BROWSER_UA,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }

    try:
        req = urllib.request.Request(url, headers=headers, method="HEAD")
        with urllib.request.urlopen(req, timeout=3) as resp:
            final_url = resp.geturl() or url
            resp_headers = resp.headers
            size = int(resp_headers.get("Content-Length", 0) or 0)
            disposition = resp_headers.get("Content-Disposition", "")
            name = None
            if disposition and "filename=" in disposition:
                fn_match = re.search(r'filename\*?=["\']?(?:UTF-8\'\')?([^"\';]+)', disposition)
                if fn_match:
                    name = urllib.parse.unquote(fn_match.group(1).strip())
            return {"url": final_url, "name": name, "size": size}
    except Exception as e:
        logging.debug(f"HEAD request redirect resolution note: {e}")

    # Fallback from URL basename
    clean_name = os.path.basename(parsed.path.rstrip("/")) if parsed.path else None
    return {"url": url, "name": clean_name or None, "size": 0}


def resolve_any_link(url: str, user_id: int = None, password: str = "") -> list:
    """
    Master Link Resolver:
    Detects link type and resolves to a list of dicts:
    [{"url": direct_url, "name": filename or None, "size": size}, ...]
    Uses memory cache to avoid redundant lookups.
    """
    url_str = str(url).strip()
    cache_key = f"{url_str}:{user_id}:{password}"
    if cache_key in RESOLVED_CACHE:
        return RESOLVED_CACHE[cache_key]

    res = None
    if is_pixeldrain(url_str):
        logging.info(f"Resolving Pixeldrain link: {url_str}")
        res = [resolve_pixeldrain(url_str, user_id=user_id)]

    elif is_gofile(url_str):
        logging.info(f"Resolving Gofile link: {url_str}")
        res = resolve_gofile(url_str, password=password, user_id=user_id)

    elif is_mediafire(url_str):
        logging.info(f"Resolving Mediafire link: {url_str}")
        try:
            res = [resolve_mediafire(url_str)]
        except Exception as me:
            logging.warning(f"Mediafire direct resolver error: {me}")

    elif is_buzzheavier(url_str):
        logging.info(f"Resolving Buzzheavier link: {url_str}")
        res = [resolve_buzzheavier(url_str)]

    elif is_solidfiles(url_str):
        logging.info(f"Resolving Solidfiles link: {url_str}")
        try:
            res = [resolve_solidfiles(url_str)]
        except Exception as se:
            logging.warning(f"Solidfiles direct resolver error: {se}")

    if not res:
        try:
            res = [resolve_generic_web(url_str)]
        except Exception:
            res = [{"url": url_str, "name": None, "size": 0}]

    RESOLVED_CACHE[cache_key] = res
    return res
