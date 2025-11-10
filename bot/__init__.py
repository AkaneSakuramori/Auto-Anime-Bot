from os import path as ospath, mkdir, system, getenv
from logging import INFO, ERROR, FileHandler, StreamHandler, basicConfig, getLogger
from traceback import format_exc
from asyncio import Queue, Lock
import asyncio

from pyrogram import filters, Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from uvloop import install

# Enable uvloop for better async performance
install()

# Logging configuration
basicConfig(
    format="[%(asctime)s] [%(name)s | %(levelname)s] - %(message)s [%(filename)s:%(lineno)d]",
    datefmt="%m/%d/%Y, %H:%M:%S %p",
    handlers=[FileHandler('log.txt'), StreamHandler()],
    level=INFO
)

getLogger("pyrogram").setLevel(ERROR)
LOGS = getLogger(__name__)

# Load environment variables
load_dotenv('config.env')

# Global caches and locks
ani_cache = {
    'fetch_animes': True,
    'ongoing': set(),
    'completed': set()
}
ffpids_cache = list()
ffLock = Lock()
ffQueue = Queue()
ff_queued = dict()


class Var:
    API_ID = getenv("API_ID")
    API_HASH = getenv("API_HASH")
    BOT_TOKEN = getenv("BOT_TOKEN")
    MONGO_URI = getenv("MONGO_URI")

    if not BOT_TOKEN or not API_HASH or not API_ID or not MONGO_URI:
        LOGS.critical("❌ Important Variables Missing. Fill Up and Retry..!! Exiting Now...")
        exit(1)

    RSS_ITEMS = getenv("RSS_ITEMS", "https://subsplease.org/rss/?r=1080").split()
    FSUB_CHATS = list(map(int, getenv("FSUB_CHATS", "0").split()))
    BACKUP_CHANNEL = getenv("BACKUP_CHANNEL") or ""
    MAIN_CHANNEL = int(getenv("MAIN_CHANNEL", "0"))
    LOG_CHANNEL = int(getenv("LOG_CHANNEL", "0"))
    FILE_STORE = int(getenv("FILE_STORE", "0"))
    ADMINS = list(map(int, getenv("ADMINS", "1242011540").split()))

    SEND_SCHEDULE = getenv("SEND_SCHEDULE", "False").lower() == "true"
    BRAND_UNAME = getenv("BRAND_UNAME", "@username")

    FFCODE_1080 = getenv("FFCODE_1080") or """ffmpeg -i '{}' -progress '{}' -preset veryfast -c:v libx264 -s 1920x1080 -pix_fmt yuv420p -crf 30 -c:a libopus -b:a 32k -c:s copy -map 0 -ac 2 -ab 32k -vbr 2 -level 3.1 '{}' -y"""
    FFCODE_720 = getenv("FFCODE_720") or """ffmpeg -i '{}' -progress '{}' -preset superfast -c:v libx264 -s 1280x720 -pix_fmt yuv420p -crf 30 -c:a libopus -b:a 32k -c:s copy -map 0 -ac 2 -ab 32k -vbr 2 -level 3.1 '{}' -y"""
    FFCODE_480 = getenv("FFCODE_480") or """ffmpeg -i '{}' -progress '{}' -preset superfast -c:v libx264 -s 854x480 -pix_fmt yuv420p -crf 30 -c:a libopus -b:a 32k -c:s copy -map 0 -ac 2 -ab 32k -vbr 2 -level 3.1 '{}' -y"""
    FFCODE_360 = getenv("FFCODE_360") or """ffmpeg -i '{}' -progress '{}' -preset superfast -c:v libx264 -s 640x360 -pix_fmt yuv420p -crf 30 -c:a libopus -b:a 32k -c:s copy -map 0 -ac 2 -ab 32k -vbr 2 -level 3.1 '{}' -y"""
    QUALS = getenv("QUALS", "360 480 720 1080").split()

    AS_DOC = getenv("AS_DOC", "True").lower() == "true"
    THUMB = getenv("THUMB", "https://te.legra.ph/file/621c8d40f9788a1db7753.jpg")
    AUTO_DEL = getenv("AUTO_DEL", "True").lower() == "true"
    DEL_TIMER = int(getenv("DEL_TIMER", "600"))
    START_PHOTO = getenv("START_PHOTO", "https://te.legra.ph/file/120de4dbad87fb20ab862.jpg")
    START_MSG = getenv("START_MSG", "<b>Hey {first_name}</b>,\n\n<i>I am Auto Animes Store & Automater Encoder Build with ❤️ !!</i>")
    START_BUTTONS = getenv("START_BUTTONS", "UPDATES|https://telegram.me/Matiz_Tech SUPPORT|https://t.me/+p78fp4UzfNwzYzQ5")


# Ensure required folders and thumbnail exist
try:
    if Var.THUMB and not ospath.exists("thumb.jpg"):
        system(f"wget -q {Var.THUMB} -O thumb.jpg")
        LOGS.info("✅ Thumbnail has been Saved!!")

    for folder in ["encode", "thumbs", "downloads"]:
        if not ospath.isdir(folder):
            mkdir(folder)
            LOGS.info(f"📁 Created missing folder: {folder}")

except Exception as e:
    LOGS.error(f"❌ Folder/Thumbnail setup failed: {e}")
    exit(1)


# Initialize Bot and Scheduler safely
try:
    # Create and set explicit event loop
    bot_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(bot_loop)

    bot = Client(
        name="AutoAniAdvance",
        api_id=Var.API_ID,
        api_hash=Var.API_HASH,
        bot_token=Var.BOT_TOKEN,
        plugins=dict(root="bot/modules"),
        parse_mode=ParseMode.HTML
    )

    sch = AsyncIOScheduler(timezone="Asia/Kolkata", event_loop=bot_loop)
    LOGS.info("🚀 Bot and Scheduler Initialized Successfully!")

except Exception as ee:
    LOGS.error(f"❌ Initialization Failed: {ee}\n{format_exc()}")
    exit(1)


# =========================
# Bot Startup Entry Point
# =========================
async def main():
    try:
        await bot.start()
        LOGS.info("✅ Bot Started Successfully!")
        sch.start()
        LOGS.info("🕒 Scheduler Started Successfully!")

        LOGS.info("🤖 Auto-Anime-Bot is Now Running...")
        await asyncio.Event().wait()  # Keeps the bot alive

    except Exception as e:
        LOGS.error(f"💥 Runtime Error: {e}\n{format_exc()}")
    finally:
        await bot.stop()
        LOGS.info("🛑 Bot Stopped Gracefully.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        LOGS.info("🧹 Exiting Auto-Anime-Bot... Goodbye!")
