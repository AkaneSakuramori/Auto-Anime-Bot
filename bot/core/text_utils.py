from calendar import month_name
from datetime import datetime
from random import choice
from asyncio import sleep as asleep
from aiohttp import ClientSession
from anitopy import parse
from re import sub as re_sub
from re import search as re_search

from bot import Var, bot
from .ffencoder import ffargs
from .func_utils import handle_logs
from .reporter import rep

CAPTION_FORMAT = """
<b>㊂ <i>{title}</i></b>
<b>╭┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</b>
<b>⊙</b> <i>Genres:</i> <i>{genres}</i>
<b>⊙</b> <i>Status:</i> <i>{status}</i> 
<b>⊙</b> <i>Source:</i> <i>{source}</i>
<b>⊙</b> <i>Episode:</i> <i>{ep_no}</i>
<b>⊙</b> <i>Audio: Japanese</i>
<b>⊙</b> <i>Subtitle: English</i>
<b>╰┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</b>
╭┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅
⌬  <b><i>Powered By</i></b> ~ </i></b><b><i>{cred}</i></b>
╰┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅
"""

GENRES_EMOJI = {
    "Action": "👊",
    "Adventure": choice(['🪂', '🧗‍♀']),
    "Comedy": "🤣",
    "Drama": "🎭",
    "Ecchi": choice(['💋', '🥵']),
    "Fantasy": choice(['🧞', '🧞‍♂', '🧞‍♀']),
    "Romance": "💕",
    "Sci-Fi": "🛰️",
    "Slice of Life": "☕",
    "Mystery": "🕵️",
    "Supernatural": "👻",
    "Thriller": "🔪"
}

ANIME_GRAPHQL_QUERY = """
query ($id: Int, $search: String, $seasonYear: Int) {
  Media(id: $id, type: ANIME, format_not_in: [MOVIE, MUSIC, MANGA, NOVEL, ONE_SHOT], search: $search, seasonYear: $seasonYear) {
    id
    idMal
    title {
      romaji
      english
      native
    }
    type
    format
    status(version: 2)
    description(asHtml: false)
    startDate { year month day }
    endDate { year month day }
    season
    seasonYear
    episodes
    duration
    coverImage { large }
    genres
    synonyms
    averageScore
    siteUrl
  }
}
"""

class AniLister:
    def __init__(self, anime_name: str, year: int) -> None:
        self.__api = "https://graphql.anilist.co"
        self.__ani_name = anime_name
        self.__ani_year = year
        self.__vars = {'search': self.__ani_name, 'seasonYear': self.__ani_year}

    async def __post(self):
        async with ClientSession() as sess:
            async with sess.post(self.__api, json={'query': ANIME_GRAPHQL_QUERY, 'variables': self.__vars}) as resp:
                return resp.status, await resp.json(), resp.headers

    async def get_anidata(self):
        res_code, resp_json, res_heads = await self.__post()
        while res_code == 404 and self.__ani_year > 2000:
            self.__ani_year -= 1
            self.__vars['seasonYear'] = self.__ani_year
            await rep.report(f"AniList Query Name: {self.__ani_name}, Retrying with {self.__ani_year}", "warning", log=False)
            res_code, resp_json, res_heads = await self.__post()
        if res_code == 404:
            self.__vars = {'search': self.__ani_name}
            res_code, resp_json, res_heads = await self.__post()
        if res_code == 200:
            return resp_json.get('data', {}).get('Media', {}) or {}
        if res_code == 429:
            f_timer = int(res_heads.get('Retry-After', 5))
            await rep.report(f"AniList API FloodWait: {res_code}, Sleeping for {f_timer}", "warning")
            await asleep(f_timer)
            return await self.get_anidata()
        if res_code in (500, 501, 502):
            await rep.report(f"AniList Server Error: {res_code}, retrying", "warning")
            await asleep(5)
            return await self.get_anidata()
        await rep.report(f"AniList API Error: {res_code}", "error", log=False)
        return {}

class TextEditor:
    def __init__(self, name):
        self.__name = name or ""
        self.adata = {}
        self.pdata = parse(self.__name or "")

    @handle_logs
    async def load_anilist(self):
        cache_names = []
        for option in ((False, False), (False, True), (True, False), (True, True)):
            ani_name = await self.parse_name(*option)
            if not ani_name:
                continue
            if ani_name in cache_names:
                continue
            cache_names.append(ani_name)
            self.adata = await AniLister(ani_name, datetime.now().year).get_anidata()
            if self.adata:
                break

    @handle_logs
    async def get_id(self):
        ani_id = self.adata.get('id')
        if ani_id and str(ani_id).isdigit():
            return ani_id
        return None

    @handle_logs
    async def parse_name(self, no_s=False, no_y=False):
        anime_name = self.pdata.get("anime_title") or ""
        anime_season = self.pdata.get("anime_season")
        anime_year = self.pdata.get("anime_year")
        if not anime_name:
            anime_name = self.__name
        anime_name = re_sub(r"\[.*?\]", " ", anime_name)
        anime_name = re_sub(r"\(.*?\)", " ", anime_name)
        anime_name = anime_name.replace("_", " ").replace(".", " ").strip()
        anime_name = re_sub(r"@[\w-]+", "", anime_name).strip()
        anime_name = re_sub(r"\s{2,}", " ", anime_name).strip()
        pname = anime_name
        if not no_s and self.pdata.get("episode_number") and anime_season:
            pname = f"{pname} {anime_season}"
        if not no_y and anime_year:
            pname = f"{pname} {anime_year}"
        return pname

    @handle_logs
    async def get_poster(self):
        anime_id = await self.get_id()
        if anime_id:
            return f"https://img.anili.st/media/{anime_id}"
        return Var.THUMB or "https://telegra.ph/file/112ec08e59e73b6189a20.jpg"

    @handle_logs
    async def get_upname(self, qual=""):
        anime_name = self.pdata.get("anime_title") or ""
        codec = "HEVC" if "libx265" in ffargs.get(qual, "") else "AV1" if "libaom-av1" in ffargs.get(qual, "") else ""
        lang = "Multi-Audio" if "multi-audio" in self.__name.lower() else "Sub"
        ani_s = self.pdata.get('anime_season', '01')
        if isinstance(ani_s, list):
            anime_season = str(ani_s[-1])
        else:
            anime_season = str(ani_s)
        ep_no = self.pdata.get("episode_number")
        titles = self.adata.get('title', {}) or {}
        title_main = titles.get('english') or titles.get('romaji') or titles.get('native') or anime_name
        if anime_name and ep_no:
            return f"[S{anime_season}-E{ep_no}] {title_main} [{codec}] [{lang}]"
        return f"{title_main} [{codec}] [{lang}]"

    @handle_logs
    async def get_caption(self):
        sd = self.adata.get('startDate', {}) or {}
        startdate = f"{month_name[sd['month']]} {sd['day']}, {sd['year']}" if sd.get('day') and sd.get('year') else ""
        ed = self.adata.get('endDate', {}) or {}
        enddate = f"{month_name[ed['month']]} {ed['day']}, {ed['year']}" if ed.get('day') and ed.get('year') else ""
        titles = self.adata.get("title", {}) or {}
        title_text = titles.get('english') or titles.get('romaji') or titles.get('native') or (self.pdata.get("anime_title") or self.__name)
        genres = self.adata.get("genres") or []
        genres_list = ", ".join((GENRES_EMOJI.get(g, "") + " " + g).strip() for g in genres) or "N/A"
        avg_score = f"{self.adata.get('averageScore')}%" if self.adata.get('averageScore') else "N/A"
        status = self.adata.get("status") or "N/A"
        plot = self.adata.get("description") or ""
        if plot and len(plot) > 200:
            plot = plot[:200] + "..."
        ep_no = self.pdata.get("episode_number") or "N/A"
        return CAPTION_FORMAT.format(
            title=title_text,
            genres=genres_list,
            status=status,
            source=self.adata.get("source") or "Subsplease",
            ep_no=ep_no,
            cred=Var.BRAND_UNAME
      )
