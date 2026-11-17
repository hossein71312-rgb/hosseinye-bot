import os
import tempfile

from bot.places import PLACES, STYLE
from bot.rubika import send_text, send_image
from bot.sources import get_news, commons_image, norm
from bot.state import already_published, mark_published

CHAT_ID = os.environ["RUBIKA_CHANNEL_ID"]

FILTERS = {
    "economy": ["اقتصاد", "ارز", "دلار", "طلا", "سکه", "تورم", "بورس", "بانک", "بازار", "نفت", "بودجه", "قیمت", "صادرات"],
    "livelihood": ["معیشت", "حقوق", "دستمزد", "یارانه", "بازنشست", "کارگر", "نان", "اجاره", "مسکن", "کالا", "گرانی", "سبد"],
    "war": ["جنگ", "حمله", "حملات", "موشک", "پهپاد", "اسرائیل", "آتش بس", "سپاه", "نظامی", "تحریم", "دفاع", "غزه", "لبنان"],
    "top": [],
    "roundup": [],
}
LABELS = {
    "economy": "📊 اقتصاد",
    "livelihood": "🧺 معیشت مردم",
    "war": "📰 تحولات جنگ و منطقه",
    "top": "📌 خبر",
    "roundup": "🌙 مرور خبرها",
}

def choose_news(category, state):
    keywords = [norm(k) for k in FILTERS.get(category, [])]
    for item in get_news():
        if already_published(state, item["key"]):
            continue
        text = norm(f'{item["title"]} {item["summary"]}')
        if not keywords or any(k in text for k in keywords):
            return item
    return None

def format_news(item, category):
    summary = item["summary"].strip()
    if len(summary) > 430:
        summary = summary[:427].rsplit(" ", 1)[0] + "…"
    lines = [LABELS.get(category, "📌 خبر"), "", item["title"]]
    if summary:
        lines += ["", summary]
    lines += ["", f'منبع: {item["source"]}', item["link"], "", "#نبض_ایران"]
    return "\n".join(lines)

def publish_news(category, state):
    item = choose_news(category, state)
    if not item:
        return False
    send_text(CHAT_ID, format_news(item, category))
    mark_published(state, item["key"])
    return True

def publish_scenic(category, state):
    places = [p for p in PLACES if p["cat"] == category]
    if not places:
        return False
    start = state["idx"].get(category, 0)
    emoji, tag = STYLE[category]
    for step in range(min(len(places), 6)):
        i = (start + step) % len(places)
        place = places[i]
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp:
            path = temp.name
        try:
            try:
                credit = commons_image(place["query"], path,
                                       skip=lambda k: already_published(state, k))
            except RuntimeError as exc:
                print(f'{place["title"]}: {exc}')
                continue
            who = f'{credit["artist"]} | ' if credit["artist"] else ""
            caption = (
                f'{emoji} {place["title"]}\n\n{place["desc"]}\n\n'
                f'📷 {who}{credit["license"]} | Wikimedia Commons\n'
                f'#نبض_ایران {tag}'
            )
            send_image(CHAT_ID, path, caption)
            mark_published(state, credit["key"])
            state["idx"][category] = i + 1
            return True
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
    state["idx"][category] = start + 6
    return False
