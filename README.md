# TMDB Telegram Channel Bot

A Python-based Telegram bot designed to run on a private Telegram channel. When you post a movie or TV show title, the bot automatically fetches the highest-quality English backdrop image from TMDB, formats the caption, posts the media, and deletes your original text message to keep the channel clean.

---

## Features

- **Automated Text Replacement**: Replaces plain-text movie/series search queries with rich media.
- **Smart Query Parsing**: Handles queries with or without years, such as `Avatar`, `Avatar 2009`, `Avatar (2009)`, or `Avatar.2009`.
- **English Backdrop Prioritization**: Searches TMDB and prioritizes English-localized backdrops. Falls back to textless or default images if an English logo version is unavailable.
- **Custom Post Formatting**:
  - **Movies**: Displays `Title (Year)`.
  - **TV Series**: Fetches and lists all active seasons with their respective episode counts (e.g., `Season 1: 8 Episodes`).
- **Production-Ready Deployment**: Includes dual compatibility for Webhooks (for production on Render) and long-polling (for local testing).

---

## File Structure

```text
├── bot.py             # Main bot application
├── requirements.txt   # Python dependencies
└── .gitattributes     # Line ending configurations
```

---

## Requirements

- Python 3.11.9
- A Telegram Bot Token (obtained from [@BotFather](https://t.me/BotFather))
- A TMDB API Key (v3 API key from [TheMovieDB](https://www.themoviedb.org/))

---

## Production Deployment on Render

You can host this bot on Render using a **Web Service**. Because of the built-in webhook logic, the bot will automatically sleep when idle and wake up instantly when you post to your channel.

### Step-by-Step Deployment:

1. Push your repository to GitHub or GitLab.
2. Log in to the [Render Dashboard](https://dashboard.render.com/).
3. Click **New +** and select **Web Service**.
4. Connect your repository.
5. Set the following configurations:
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
   - **Instance Type**: `Free`
6. Click **Advanced** and add the following **Environment Variables**:
   - `BOT_TOKEN`: Your Telegram Bot Token.
   - `TMDB_API_KEY`: Your TMDB API Key.
   - `PYTHON_VERSION`: `3.11.9`.
7. Click **Deploy Web Service**.

---

## Telegram Channel Configuration

For the bot to function in your channel, please complete the following:

1. Add your bot to your private Telegram channel as an **Administrator**.
2. Grant the bot the following administrative permissions:
   - **Post Messages** (required to post the image and formatted caption)
   - **Delete Messages** (required to clean up your initial text query)