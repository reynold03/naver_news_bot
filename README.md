# naver-news-api

Simple Naver News Search API client.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# edit .env and put your keys
python naver_news_bot.py
```

## Usage

- Edit `naver_news_bot.py` to set `query` and `days`.
- If no new items are found, it prints `새로운 뉴스 없음`.

## .env

- Keep your API keys in `.env` at the project root.
- `.env` is ignored by git so it will not be committed.

## News cache

- `.news_seen.json` stores recently seen news to avoid duplicates across runs.
- The cache keeps the last 7 days and is ignored by git.

## Telegram

- Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env` to enable auto-send.
- If they are missing, the script prints only to the terminal.
