import os
from collections import defaultdict
import logging
from logging.handlers import RotatingFileHandler
import time
import sys
from helpers.msg_utils import MakeButtons
# --- MODIFIED START ---
import aiohttp
# --- MODIFIED END ---

"""Some Constants"""
MERGE_MODE = {}  # Maintain each user merge_mode
UPLOAD_AS_DOC = {}  # Maintain each user ul_type
UPLOAD_TO_DRIVE = {}  # Maintain each user drive_choice

FINISHED_PROGRESS_STR = os.environ.get("FINISHED_PROGRESS_STR", "█")
UN_FINISHED_PROGRESS_STR = os.environ.get("UN_FINISHED_PROGRESS_STR", "░")
EDIT_SLEEP_TIME_OUT = 10
gDict = defaultdict(lambda: [])
queueDB = {}
formatDB = {}
replyDB = {}
# --- MODIFIED START ---
# For metadata editing
METADATA_TITLE = "title"
METADATA_DESCRIPTION = "description"
METADATA_TAGS = "tags"
# --- MODIFIED END ---

VIDEO_EXTENSIONS = ["mkv", "mp4", "webm", "ts", "wav", "mov"]
AUDIO_EXTENSIONS = ["aac", "ac3", "eac3", "m4a", "mka", "thd", "dts", "mp3"]
SUBTITLE_EXTENSIONS = ["srt", "ass", "mka", "mks"]

w = open("mergebotlog.txt", "w")
w.truncate(0)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler("mergebotlog.txt", maxBytes=50000000, backupCount=10),
        logging.StreamHandler(sys.stdout),  # to get sys messages
    ],
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)
# --- MODIFIED START ---
# Add logging for new libs if needed
logging.getLogger("yt_dlp").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

# Global aiohttp session
AIO_SESSION = None

async def get_aio_session():
    global AIO_SESSION
    if AIO_SESSION is None or AIO_SESSION.closed: # Check if closed
        AIO_SESSION = aiohttp.ClientSession()
        logging.info("Created new aiohttp ClientSession.")
    return AIO_SESSION

async def close_aio_session():
    global AIO_SESSION
    if AIO_SESSION and not AIO_SESSION.closed: # Check if exists and not closed
        await AIO_SESSION.close()
        logging.info("Closed aiohttp ClientSession.")
        AIO_SESSION = None
# --- MODIFIED END ---

LOGGER = logging.getLogger(__name__)
BROADCAST_MSG = """
**Total: {}
Done: {}**
"""
bMaker = MakeButtons()
