from asyncio import gather, create_task, sleep as asleep, Event
from asyncio.subprocess import PIPE
from os import path as ospath
from aiofiles import open as aiopen
from aiofiles.os import remove as aioremove
from traceback import format_exc
from base64 import urlsafe_b64encode
from time import time
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import bot, bot_loop, Var, ani_cache, ffQueue, ffLock, ff_queued
from .filehandler import FileHandler
from .database import db
from .func_utils import encode, editMessage, sendMessage, convertBytes
from .text_utils import TextEditor
from .ffencoder import FFEncoder
from .tguploader import TgUploader
from .reporter import rep

btn_formatter = {
    '1080':'𝟭𝟬𝟴𝟬𝗽', 
    '720':'𝟳𝟮𝟬𝗽',
    '480':'𝟰𝟴𝟬𝗽',
    '360':'𝟯𝟲𝟬𝗽'
}

async def fetch_animes():
    """
    This function is kept as a placeholder to maintain compatibility with the scheduler.
    Since we're moving to direct file uploads, this won't actively fetch anime anymore.
    """
    await rep.report("Bot is ready to process direct file uploads!", "info")
    while True:
        await asleep(60)  # Sleep to prevent high CPU usage

async def get_animes(name, force=False):
    """
    Legacy function maintained for compatibility.
    Now redirects to process_file for direct file handling.
    """
    await rep.report("Using direct file processing instead of anime fetching", "info")
    return None

async def process_file(message, name=None):
    try:
        if not name and message.document:
            name = message.document.file_name
            
        aniInfo = TextEditor(name)
        await aniInfo.load_anilist()
        
        post_msg = await bot.send_photo(
            Var.MAIN_CHANNEL,
            photo=await aniInfo.get_poster(),
            caption=await aniInfo.get_caption()
        )
        
        await asleep(1.5)
        stat_msg = await sendMessage(Var.MAIN_CHANNEL, f"‣ <b>File Name :</b> <b><i>{name}</i></b>\n\n<i>Downloading...</i>")
        
        file_handler = FileHandler("./downloads")
        dl = await file_handler.save_file(message, name)
        
        if not dl or not ospath.exists(dl):
            await rep.report(f"File Download Failed", "error")
            await stat_msg.delete()
            return

        post_id = post_msg.id
        ffEvent = Event()
        ff_queued[post_id] = ffEvent
        
        if ffLock.locked():
            await editMessage(stat_msg, f"‣ <b>File Name :</b> <b><i>{name}</i></b>\n\n<i>Queued to Encode...</i>")
            await rep.report("Added Task to Queue...", "info")
            
        await ffQueue.put(post_id)
        await ffEvent.wait()
        
        await ffLock.acquire()
        btns = []
        
        for qual in Var.QUALS:
            filename = await aniInfo.get_upname(qual)
            await editMessage(stat_msg, f"‣ <b>File Name :</b> <b><i>{name}</i></b>\n\n<i>Ready to Encode...</i>")
            
            await asleep(1.5)
            await rep.report("Starting Encode...", "info")
            
            try:
                out_path = await FFEncoder(stat_msg, dl, filename, qual).start_encode()
            except Exception as e:
                await rep.report(f"Error: {e}, Cancelled, Retry Again!", "error")
                await stat_msg.delete()
                ffLock.release()
                return
                
            await rep.report("Successfully Compressed Now Going To Upload...", "info")
            
            await editMessage(stat_msg, f"‣ <b>File Name :</b> <b><i>{filename}</i></b>\n\n<i>Ready to Upload...</i>")
            await asleep(1.5)
            
            try:
                msg = await TgUploader(stat_msg).upload(out_path, qual)
            except Exception as e:
                await rep.report(f"Error: {e}, Cancelled, Retry Again!", "error")
                await stat_msg.delete()
                ffLock.release()
                return
                
            await rep.report("Successfully Uploaded File to Telegram...", "info")
            
            msg_id = msg.id
            link = f"https://telegram.me/{(await bot.get_me()).username}?start={await encode('get-'+str(msg_id * abs(Var.FILE_STORE)))}"
            
            if post_msg:
                if len(btns) != 0 and len(btns[-1]) == 1:
                    btns[-1].insert(1, InlineKeyboardButton(f"{btn_formatter[qual]} - {convertBytes(msg.document.file_size)}", url=link))
                else:
                    btns.append([InlineKeyboardButton(f"{btn_formatter[qual]} - {convertBytes(msg.document.file_size)}", url=link)])
                await editMessage(post_msg, post_msg.caption.html if post_msg.caption else "", InlineKeyboardMarkup(btns))
                
            bot_loop.create_task(extra_utils(msg_id, out_path))
            
        ffLock.release()
        await stat_msg.delete()
        await aioremove(dl)
        
    except Exception as error:
        await rep.report(format_exc(), "error")

async def extra_utils(msg_id, out_path):
    msg = await bot.get_messages(Var.FILE_STORE, message_ids=msg_id)
    
    if Var.BACKUP_CHANNEL != 0:
        for chat_id in Var.BACKUP_CHANNEL.split():
            await msg.copy(int(chat_id))
