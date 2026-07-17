import os
import logging
import re
import requests
import html
import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
PORT = int(os.getenv("PORT", "8000"))
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

def clean_and_parse_query(text: str):
    match = re.search(r'\b(19\d\d|20\d\d)\b', text)
    year = None
    
    if match:
        year = match.group(1)
        cleaned = re.sub(r'[\(\[\{\-\s]*' + year + r'[\)\]\}\-\s]*', ' ', text)
    else:
        cleaned = text
        
    cleaned = cleaned.replace('.', ' ').replace('_', ' ')
    cleaned = re.sub(r'[\(\)\[\]\{\}]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned, year

def get_english_backdrop(media_type: str, media_id: int, api_key: str):
    url = f"https://api.themoviedb.org/3/{media_type}/{media_id}/images"
    params = {
        "api_key": api_key,
        "include_image_language": "en,null"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        backdrops = data.get("backdrops", [])
        
        if not backdrops:
            return None
            
        english_backdrops = [b for b in backdrops if b.get("iso_639_1") == "en"]
        if english_backdrops:
            english_backdrops.sort(key=lambda x: x.get("vote_average", 0), reverse=True)
            return english_backdrops[0].get("file_path")
            
        textless_backdrops = [b for b in backdrops if b.get("iso_639_1") in [None, "null", ""]]
        if textless_backdrops:
            textless_backdrops.sort(key=lambda x: x.get("vote_average", 0), reverse=True)
            return textless_backdrops[0].get("file_path")
            
        return backdrops[0].get("file_path")
    except Exception as e:
        logger.error(f"Error fetching English backdrop for {media_type} {media_id}: {e}")
        return None

def get_season_details(tv_id: int, season_num: int, api_key: str):
    url = f"https://api.themoviedb.org/3/tv/{tv_id}/season/{season_num}"
    params = {
        "api_key": api_key,
        "language": "en-US"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching details for TV ID {tv_id} Season {season_num}: {e}")
        return None

def get_tv_seasons_details(tv_id: int, api_key: str):
    url = f"https://api.themoviedb.org/3/tv/{tv_id}"
    params = {
        "api_key": api_key,
        "language": "en-US"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        name = data.get("name")
        escaped_name = html.escape(name) if name else ""
        
        seasons = data.get("seasons", [])
        valid_seasons = [s for s in seasons if s.get("season_number", 0) > 0]
        valid_seasons.sort(key=lambda x: x.get("season_number", 0))
        
        today = datetime.date.today()
        season_lines = []
        
        for idx, s in enumerate(valid_seasons):
            s_num = s.get("season_number")
            ep_count = s.get("episode_count", 0)
            
            is_latest = (idx == len(valid_seasons) - 1)
            expanded = False
            episodes = []
            
            if is_latest:
                season_details = get_season_details(tv_id, s_num, api_key)
                if season_details:
                    episodes = season_details.get("episodes", [])
                    has_future = False
                    for ep in episodes:
                        air_date_str = ep.get("air_date")
                        if not air_date_str:
                            has_future = True
                            break
                        try:
                            air_date = datetime.datetime.strptime(air_date_str, "%Y-%m-%d").date()
                            if air_date >= today:
                                has_future = True
                                break
                        except ValueError:
                            pass
                    if has_future:
                        expanded = True
            
            if expanded:
                for ep in episodes:
                    ep_num = ep.get("episode_number")
                    air_date_str = ep.get("air_date")
                    formatted_date = "TBA"
                    if air_date_str:
                        try:
                            dt = datetime.datetime.strptime(air_date_str, "%Y-%m-%d")
                            formatted_date = dt.strftime("%d %B, %Y")
                        except ValueError:
                            pass
                    season_lines.append(f"Season {s_num}: Episode {ep_num:02d}: <code>{formatted_date}</code>")
            else:
                ep_word = "Episode" if ep_count == 1 else "Episodes"
                padded_count = f"{ep_count:02d}"
                season_lines.append(f"Season {s_num}: {padded_count} {ep_word}")
                
        seasons_text = "\n".join(season_lines)
        return escaped_name, seasons_text
    except Exception as e:
        logger.error(f"Error fetching TV details for TV ID {tv_id}: {e}")
        return None, None

def get_tmdb_media(query: str, api_key: str):
    clean_query, target_year = clean_and_parse_query(query)
    
    if not clean_query:
        clean_query = query
        target_year = None
        
    url = "https://api.themoviedb.org/3/search/multi"
    params = {
        "api_key": api_key,
        "query": clean_query,
        "language": "en-US"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        if not results:
            return None
            
        filtered = [r for r in results if r.get("media_type") in ["movie", "tv"]]
        if not filtered:
            return None
            
        best_match = None
        if target_year:
            for item in filtered:
                media_type = item.get("media_type")
                date_key = "release_date" if media_type == "movie" else "first_air_date"
                date_str = item.get(date_key, "")
                item_year = date_str.split("-")[0] if date_str else ""
                if item_year == target_year:
                    best_match = item
                    break
                    
        if not best_match:
            best_match = filtered[0]
            
        media_type = best_match.get("media_type")
        media_id = best_match.get("id")
        
        english_backdrop_path = get_english_backdrop(media_type, media_id, api_key)
        
        image_path = english_backdrop_path or best_match.get("backdrop_path") or best_match.get("poster_path")
        image_url = f"https://image.tmdb.org/t/p/original{image_path}" if image_path else None
        
        if media_type == "movie":
            title = best_match.get("title")
            escaped_title = html.escape(title) if title else ""
            release_date = best_match.get("release_date", "")
            year = release_date.split("-")[0] if release_date else ""
            display_title = f"{escaped_title} ({year})" if year else escaped_title
            
            if release_date:
                try:
                    dt = datetime.datetime.strptime(release_date, "%Y-%m-%d")
                    formatted_date = dt.strftime("%d %B, %Y")
                    display_title += f"\n\n<code>{formatted_date}</code>"
                except ValueError:
                    pass
        else:
            tv_name, seasons_text = get_tv_seasons_details(media_id, api_key)
            if tv_name and seasons_text:
                display_title = f"{tv_name}\n\n{seasons_text}"
            else:
                title = best_match.get("name")
                escaped_title = html.escape(title) if title else ""
                first_air_date = best_match.get("first_air_date", "")
                year = first_air_date.split("-")[0] if first_air_date else ""
                display_title = f"{escaped_title} ({year})" if year else escaped_title
            
        return {
            "title": display_title,
            "image_url": image_url
        }
    except Exception as e:
        logger.error(f"Error querying TMDB API: {e}")
        return None

async def channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post
    if not message or not message.text:
        return

    query = message.text.strip()
    logger.info(f"Processing query: {query}")

    media_info = get_tmdb_media(query, TMDB_API_KEY)
    
    if not media_info or not media_info.get("image_url"):
        logger.warning(f"No results or images found for: {query}")
        return

    try:
        await context.bot.send_photo(
            chat_id=message.chat_id,
            photo=media_info["image_url"],
            caption=media_info["title"],
            parse_mode="HTML"
        )
        
        await message.delete()
        logger.info(f"Successfully processed: {media_info['title']}")
    except Exception as e:
        logger.error(f"Failed to process channel post: {e}")

def main():
    if not BOT_TOKEN or not TMDB_API_KEY:
        logger.error("Missing configuration. Please check your BOT_TOKEN and TMDB_API_KEY.")
        return

    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        logger.info("No active event loop found. Creating a new one...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(
        MessageHandler(
            filters.ChatType.CHANNEL & filters.TEXT,
            channel_post,
        )
    )

    if RENDER_EXTERNAL_HOSTNAME:
        logger.info("Starting webhook...")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"https://{RENDER_EXTERNAL_HOSTNAME}/{BOT_TOKEN}",
            allowed_updates=Update.ALL_TYPES
        )
    else:
        logger.info("Starting local polling...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()