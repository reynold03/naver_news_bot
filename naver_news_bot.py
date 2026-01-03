import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

import requests

from naver_news_api import NaverNewsClient

TAG_RE = re.compile(r"<[^>]+>")
SEEN_FILE = Path(".news_seen.json")
SEEN_KEEP_DAYS = 7
USE_NEWS_CACHE = True
TELEGRAM_API_TIMEOUT = 10
TELEGRAM_MAX_MESSAGE_LENGTH = 3500
ANALYSIS_RULES = [
    (("fomc", "fed", "금리", "cpi", "pce", "고용"), "거시/금리 변수 영향"),
    (("실적", "어닝", "earnings", "guidance", "가이던스"), "실적/가이던스 이벤트"),
    (("출하", "delivery", "deliveries", "생산", "production"), "수요/공급 지표"),
    (("가격인하", "price cut"), "가격 정책 변화"),
    (("리콜", "recall", "안전"), "품질/규제 리스크"),
    (("fsd", "자율주행", "로보택시"), "자율주행 모멘텀"),
    (("수출규제", "export", "규제", "ban", "제재"), "규제/정책 리스크"),
    (("ai", "gpu", "hbm", "데이터센터", "datacenter"), "AI/데이터센터 수요"),
    (("양자", "quantum", "ionq", "rigetti"), "양자컴퓨팅 모멘텀"),
    (("전기차", "ev", "배터리", "충전", "battery"), "EV/배터리 수요"),
]


def clean_text(value: str) -> str:
    return html.unescape(TAG_RE.sub("", value))


def parse_pub_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def analyze_title(title: str) -> str:
    lowered = title.lower()
    tags = []
    for keywords, label in ANALYSIS_RULES:
        if any(keyword in lowered for keyword in keywords):
            tags.append(label)
    return ", ".join(tags) if tags else "일반 뉴스"


def build_summary(description: str, analysis: str) -> str:
    if description:
        return f"{description}\n분석: {analysis}"
    return f"분석: {analysis}"


def make_item_key(title: str, link: str, pub_date: Optional[datetime]) -> str:
    if link:
        return link
    if pub_date:
        return f"{title}|{pub_date.isoformat()}"
    return title


def load_seen() -> dict[str, str]:
    if not SEEN_FILE.is_file():
        return {}
    try:
        data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def prune_seen(seen: dict[str, str], keep_days: int) -> dict[str, str]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    pruned: dict[str, str] = {}
    for key, value in seen.items():
        try:
            ts = datetime.fromisoformat(value)
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts >= cutoff:
            pruned[key] = ts.isoformat()
    return pruned


def save_seen(seen: dict[str, str]) -> None:
    SEEN_FILE.write_text(
        json.dumps(seen, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


def load_dotenv() -> None:
    env_path = Path.cwd() / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_telegram_config() -> tuple[Optional[str], Optional[str]]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return None, None
    return token, chat_id


def truncate_message(message: str, limit: int) -> str:
    if len(message) <= limit:
        return message
    return message[: max(0, limit - 1)] + "…"


def build_telegram_message(
    title: str,
    description: str,
    link: str,
    pub_date: Optional[datetime],
    analysis: str,
) -> str:
    lines = []
    if pub_date:
        lines.append(f"[{pub_date:%Y-%m-%d %H:%M}]")
    lines.append(title)
    lines.append(f"분석: {analysis}")
    if description:
        lines.append(description)
    if link:
        lines.append(link)
    message = "\n".join(lines)
    return truncate_message(message, TELEGRAM_MAX_MESSAGE_LENGTH)


def send_telegram_message(token: str, chat_id: str, message: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }
    response = requests.post(url, data=payload, timeout=TELEGRAM_API_TIMEOUT)
    if response.ok:
        return
    try:
        error = response.json().get("description", response.text)
    except (ValueError, AttributeError):
        error = response.text
    raise RuntimeError(f"Telegram error {response.status_code}: {error}")


def main() -> None:
    load_dotenv()
    client = NaverNewsClient()
    query = "테슬라"
    days = 2
    data = client.search(query, display=20, sort="date")
    items = data.get("items", [])
    if not items:
        print("No results.")
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    seen = prune_seen(load_seen(), SEEN_KEEP_DAYS) if USE_NEWS_CACHE else {}
    now = datetime.now(timezone.utc)
    telegram_token, telegram_chat_id = load_telegram_config()
    telegram_enabled = bool(telegram_token and telegram_chat_id)
    if not telegram_enabled:
        print("Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")

    printed = 0
    for item in items:
        pub_date = parse_pub_date(item.get("pubDate", ""))
        if pub_date and pub_date.astimezone(timezone.utc) < cutoff:
            continue
        title = clean_text(item.get("title", ""))
        description = clean_text(item.get("description", ""))
        link = item.get("link", "")
        key = make_item_key(title, link, pub_date)
        if USE_NEWS_CACHE and key in seen:
            continue
        analysis = analyze_title(title)
        summary = build_summary(description, analysis)

        if USE_NEWS_CACHE:
            seen[key] = now.isoformat()
        if pub_date:
            print(f"[{pub_date:%Y-%m-%d %H:%M}] {title}")
        else:
            print(title)
        print(summary)
        if link:
            print(link)
        print("-" * 60)
        if telegram_enabled:
            message = build_telegram_message(title, description, link, pub_date, analysis)
            try:
                send_telegram_message(telegram_token, telegram_chat_id, message)
            except (requests.RequestException, RuntimeError) as exc:
                print(f"Telegram send failed: {exc}")
                telegram_enabled = False
        printed += 1

    if printed == 0:
        print("새로운 뉴스 없음")

    if USE_NEWS_CACHE:
        save_seen(seen)


if __name__ == "__main__":
    main()
