# TGColabX - Based on WZML-X & XronTrix10
# Copyright (c) 2024-2026 TGColabX

# @title 🚀 TGColabX - Main Colab Leecher Code

API_ID = 0  # @param {type: "integer"}
API_HASH = ""  # @param {type: "string"}
BOT_TOKEN = ""  # @param {type: "string"}
USER_ID = 0  # @param {type: "integer"}
DUMP_ID = 0  # @param {type: "integer"}
REPO_URL = "https://github.com/MyKurumiChan/TGColabX"  # @param {type: "string"}

import os
import sys
import json
import time
import shutil
import subprocess
from threading import Thread

banner = r"""

  ______ _____ _____      _       _     __  __
 |__   _/ ____/ ____|    | |     | |   \ \ / /
    | || |  __ | |     ___ | | __ _| |__  \ V / 
    | || | |_ || |    / _ \| |/ _` | '_ \  > <  
    | || |__| || |___| (_) | | (_| | |_) |/ . \ 
    |_| \_____|\_____\___/|_|\__,_|_.__//_/ \_\
                                               
 ⚡ TGColabX — Next-Gen Colab Telegram Leecher
 💖 Developed by: MyKurumiChan
 🌟 Enhanced with WZML-X Features & Architecture
 💖 Credits: WZML-X, XronTrix10 & DownloaderZone (DzGram)

"""

print(banner)

# Validate credentials early
missing_creds = []
if not API_ID or str(API_ID).strip() == "0":
    missing_creds.append("API_ID")
if not API_HASH or not str(API_HASH).strip():
    missing_creds.append("API_HASH")
if not BOT_TOKEN or not str(BOT_TOKEN).strip():
    missing_creds.append("BOT_TOKEN")

if missing_creds:
    print("=" * 80)
    print("❌ CONFIGURATION ERROR: Missing Telegram API credentials!")
    print(f"👉 Missing fields: {', '.join(missing_creds)}")
    print("👉 Please fill in API_ID, API_HASH, and BOT_TOKEN in the parameters above!")
    print("   Get API_ID & API_HASH from: https://my.telegram.org")
    print("   Get BOT_TOKEN from: https://t.me/BotFather")
    print("=" * 80)
    sys.exit(1)

Working = True

def Loading():
    white = 37
    black = 0
    while Working:
        print("\r" + "░" * white + "▒▒" + "▓" * black + "▒▒" + "░" * white, end="", flush=True)
        black = (black + 2) % 75
        white = (white - 1) if white != 0 else 37
        time.sleep(1)

_Thread = Thread(target=Loading, name="Prepare", args=())
_Thread.start()

dump_str = str(DUMP_ID).strip()
if dump_str and dump_str != "0":
    if not dump_str.startswith("-100"):
        if dump_str.startswith("-"):
            dump_str = dump_str[1:]
        if dump_str.startswith("100"):
            dump_str = "-" + dump_str
        else:
            dump_str = "-100" + dump_str
    try:
        DUMP_ID = int(dump_str)
    except ValueError:
        pass

if os.path.exists("/content/sample_data"):
    try:
        shutil.rmtree("/content/sample_data")
    except Exception:
        pass

repo_name = REPO_URL.rstrip("/").split("/")[-1].replace(".git", "")
repo_dir = f"/content/{repo_name}"

# Always ensure fresh repository clone on Colab to apply latest updates
if os.path.exists(repo_dir):
    try:
        shutil.rmtree(repo_dir, ignore_errors=True)
    except Exception:
        pass

clone_res = subprocess.run(f"git clone --depth=1 {REPO_URL} {repo_dir}", shell=True, capture_output=True, text=True)
if clone_res.returncode != 0 or not os.path.exists(repo_dir):
    Working = False
    try:
        _Thread.join(timeout=2)
    except Exception:
        pass
    print("\n" + "=" * 80)
    print(f"❌ REPOSITORY CLONE FAILED for: {REPO_URL}")
    print(f"Error output:\n{clone_res.stderr.strip() or clone_res.stdout.strip()}")
    print("👉 Please verify REPO_URL is correct and the repository exists and is public.")
    print("=" * 80)
    sys.exit(1)

# Remove any stale __pycache__ compiled files
subprocess.run(f"find {repo_dir} -type d -name '__pycache__' -exec rm -rf {{}} +", shell=True)

subprocess.run("apt update -y && apt install -y ffmpeg aria2 mediainfo p7zip-full unrar nodejs", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
pip_res = subprocess.run(f"pip3 install --upgrade -r {repo_dir}/requirements.txt", shell=True, capture_output=True, text=True)
if pip_res.returncode != 0:
    Working = False
    print(f"\n⚠️ Requirements installation encountered issues:\n{pip_res.stderr.strip() or pip_res.stdout.strip()}")

credentials = {
    "API_ID": API_ID,
    "API_HASH": API_HASH,
    "BOT_TOKEN": BOT_TOKEN,
    "USER_ID": USER_ID,
    "DUMP_ID": DUMP_ID,
}

with open(f"{repo_dir}/credentials.json", "w", encoding="utf-8") as file:
    file.write(json.dumps(credentials, indent=2))

Working = False
try:
    _Thread.join(timeout=3)
except Exception:
    pass

# Pre-flight check: verify module can be imported without errors
preflight = subprocess.run(
    [sys.executable, "-c", "import colab_leecher; print('✅ TGColabX modules loaded successfully.')"],
    cwd=repo_dir,
    capture_output=True,
    text=True,
)
if preflight.returncode != 0:
    print("\n" + "=" * 80)
    print("❌ PRE-FLIGHT VERIFICATION FAILED:")
    print(preflight.stderr.strip() or preflight.stdout.strip())
    print("=" * 80)
    sys.exit(1)

try:
    from IPython.display import clear_output
    clear_output(wait=True)
except Exception:
    pass

print(banner)

# Remove any previous session files to ensure clean start
for s in ["tgcolabx_bot.session", "my_bot.session"]:
    if os.path.exists(f"{repo_dir}/{s}"):
        try:
            os.remove(f"{repo_dir}/{s}")
        except Exception:
            pass

print("\n🚀 Starting TGColabX.... Live logs active below:\n" + "-" * 80)

# Run colab_leecher with merged real-time stdout & stderr streaming
proc = subprocess.Popen(
    [sys.executable, "-u", "-m", "colab_leecher"],
    cwd=repo_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
)

for line in iter(proc.stdout.readline, ""):
    print(line, end="", flush=True)

proc.stdout.close()
return_code = proc.wait()
if return_code != 0:
    print(f"\n⚠️ Bot process terminated with exit code: {return_code}")
