from os import path as ospath
from aiofiles import open as aiopen
from aiofiles.os import path as aiopath, mkdir

from bot import LOGS
from bot.core.func_utils import handle_logs

class FileHandler:
    def __init__(self, path="."):
        self.__downdir = path
        
    @handle_logs
    async def save_file(self, message, filename=None):
        try:
            if not filename:
                filename = message.document.file_name or "video_file"
            file_path = ospath.join(self.__downdir, filename)
            await message.download(file_path)
            return file_path
        except Exception as e:
            LOGS.error(str(e))
            return None
