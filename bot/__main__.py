from os import path as ospath, execl, kill
from sys import executable
from signal import SIGKILL
from aiohttp import web
from asyncio import create_task, create_subprocess_exec, create_subprocess_shell, run as asyrun, all_tasks, gather, sleep as asleep
from aiofiles import open as aiopen
from pyrogram import idle
from pyrogram.filters import command, user
from pyrogram.errors import ChatIdInvalid, ChannelInvalid

from bot import bot, Var, bot_loop, sch, LOGS, ffQueue, ffLock, ffpids_cache, ff_queued
from bot.core.auto_animes import fetch_animes
from bot.core.func_utils import clean_up, new_task, editMessage
from bot.modules.up_posts import upcoming_animes

# Health check endpoint for Render
async def health_check(request):
    return web.Response(text="Bot is running!")

async def start_health_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(Var.PORT) if hasattr(Var, 'PORT') and Var.PORT else 8080
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    LOGS.info(f"🌐 Health check server started on port {port}")

async def preload_chats():
    chat_ids = []
    if Var.MAIN_CHANNEL:
        chat_ids.append(Var.MAIN_CHANNEL)
    if Var.FILE_STORE:
        chat_ids.append(Var.FILE_STORE)
    if Var.LOG_CHANNEL:
        chat_ids.append(Var.LOG_CHANNEL)
    if Var.BACKUP_CHANNEL:
        for cid in str(Var.BACKUP_CHANNEL).split():
            try:
                if cid.strip():
                    chat_ids.append(int(cid))
            except:
                continue
    if Var.FSUB_CHATS:
        chat_ids.extend(Var.FSUB_CHATS)
    LOGS.info(f"🔄 Preloading {len(chat_ids)} chat(s) for peer cache...")
    for cid in chat_ids:
        try:
            await bot.get_chat(int(cid))
            LOGS.info(f"✅ Cached chat: {cid}")
        except (ChatIdInvalid, ChannelInvalid):
            LOGS.error(f"❌ Invalid or inaccessible chat: {cid}")
        except Exception as e:
            LOGS.error(f"⚠️ Failed to preload {cid}: {e}")
        await asleep(1)

@bot.on_message(command('restart') & user(Var.ADMINS))
@new_task
async def restart_bot(client, message):
    rmessage = await message.reply('<i>Restarting...</i>')
    if sch.running:
        sch.shutdown(wait=False)
    await clean_up()
    if len(ffpids_cache) != 0:
        for pid in ffpids_cache:
            try:
                LOGS.info(f"Process ID : {pid}")
                kill(pid, SIGKILL)
            except (OSError, ProcessLookupError):
                LOGS.error("Killing Process Failed !!")
                continue
    await (await create_subprocess_exec('python3', 'update.py')).wait()
    async with aiopen(".restartmsg", "w") as f:
        await f.write(f"{rmessage.chat.id}\n{rmessage.id}\n")
    execl(executable, executable, "-m", "bot")

async def restart():
    if ospath.isfile(".restartmsg"):
        with open(".restartmsg") as f:
            chat_id, msg_id = map(int, f)
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="<i>Restarted !</i>")
        except Exception as e:
            LOGS.error(e)

async def queue_loop():
    LOGS.info("Queue Loop Started !!")
    while True:
        if not ffQueue.empty():
            post_id = await ffQueue.get()
            await asleep(1.5)
            ff_queued[post_id].set()
            await asleep(1.5)
            async with ffLock:
                ffQueue.task_done()
        await asleep(10)

async def main():
    sch.add_job(upcoming_animes, "cron", hour=0, minute=30)
    await bot.start()
    await preload_chats()
    await restart()
    LOGS.info('Auto Anime Bot Started!')
    sch.start()
    
    # Start health check server
    bot_loop.create_task(start_health_server())
    bot_loop.create_task(queue_loop())
    
    await fetch_animes()
    await idle()
    LOGS.info('Auto Anime Bot Stopped!')
    await bot.stop()
    for task in all_tasks():
        task.cancel()
    await clean_up()
    LOGS.info('Finished AutoCleanUp !!')

if __name__ == '__main__':
    bot_loop.run_until_complete(main())
