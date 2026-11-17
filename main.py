import os

from bot.publisher import publish_news, publish_scenic, FILTERS
from bot.state import load_state, save_state

SCENIC = {"nature", "village", "history"}
# ترتیب چرخشی؛ هر اجرا یک نوبت جلو می‌رود (مستقل از ساعت cron-job)
CYCLE = ["economy", "nature", "livelihood", "war", "history", "top", "village", "war"]

def publish(category, state):
    if category in SCENIC:
        return publish_scenic(category, state)
    return publish_news(category, state)

def main():
    category = os.getenv("POST_CATEGORY", "").strip().lower()
    state = load_state()
    if category not in SCENIC and category not in FILTERS:
        category = CYCLE[state["n"] % len(CYCLE)]
        state["n"] += 1

    ok = publish(category, state)
    if not ok and category in FILTERS and category != "top":
        print(f"No new news for {category}; trying top.")
        ok = publish_news("top", state)
    print(f"Published category={category}" if ok else f"Nothing posted for {category}.")
    save_state(state)

if __name__ == "__main__":
    main()
