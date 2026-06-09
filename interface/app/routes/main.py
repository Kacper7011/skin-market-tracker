from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.db import (
    fetch_items, fetch_item, fetch_recent_logs,
    fetch_price_history,
    push_scrape_task, get_queue_length, get_mongo,
    get_catalog_count, clear_all_items,
)

main_bp = Blueprint("main", __name__)


def get_stats() -> dict:
    db = get_mongo()
    return {
        "items_count": db.items.count_documents({}),
        "prices":      db.prices.count_documents({}),
        "queue":       get_queue_length(),
    }


@main_bp.route("/")
def index():
    from datetime import datetime, timedelta, timezone
    db     = get_mongo()
    stats  = get_stats()
    month_ago = datetime.now(timezone.utc) - timedelta(days=30)

    raw_items = list(db.items.find({}, {"_id": 0}).sort("updated_at", -1).limit(18))
    market_items = []
    for item in raw_items:
        name   = item["name"]
        source = item.get("source", "steam")

        latest = db.prices.find_one(
            {"item_name": name, "source": source},
            sort=[("timestamp", -1)],
        )
        old = db.prices.find_one(
            {"item_name": name, "source": source, "timestamp": {"$lte": month_ago}},
            sort=[("timestamp", -1)],
        )

        latest_price = latest["price"] if latest else None
        old_price    = old["price"]    if old    else None
        change_pct   = None
        if latest_price and old_price and old_price > 0:
            change_pct = round(((latest_price - old_price) / old_price) * 100, 1)

        market_items.append({**item, "latest_price": latest_price, "change_pct": change_pct})

    return render_template(
        "index.html",
        stats=stats,
        logs=fetch_recent_logs(6),
        catalog_count=get_catalog_count(),
        market_items=market_items,
    )


@main_bp.route("/items")
def items():
    query  = request.args.get("q", "")
    source = request.args.get("source", "")
    db     = get_mongo()

    filters = {}
    if query:
        filters["name"] = {"$regex": query, "$options": "i"}
    if source:
        filters["source"] = source

    items_list = list(db.items.find(filters, {"_id": 0}).limit(100))
    return render_template("items.html", items=items_list, query=query, source=source)


@main_bp.route("/items/<path:name>")
def item_detail(name: str):
    source = request.args.get("source", "steam")
    item   = fetch_item(name, source)
    if not item:
        flash("Przedmiot nie znaleziony", "error")
        return redirect(url_for("main.items"))

    price_history = fetch_price_history(name, source, 200)
    latest_price  = price_history[-1] if price_history else None

    return render_template(
        "item_detail.html",
        item=item,
        latest_price=latest_price,
        price_history=price_history,
    )


@main_bp.route("/scraper", methods=["GET", "POST"])
def scraper():
    if request.method == "POST":
        item_name = request.form.get("item_name", "").strip()
        action    = request.form.get("action", "search")
        source    = request.form.get("source", "steam")

        if item_name:
            push_scrape_task(source, action, item_name)
            # After search, also fetch price history immediately
            if action == "search":
                push_scrape_task(source, "history", item_name)
            # Fetch Skinport price history alongside any Steam task
            if source == "steam":
                push_scrape_task("skinport", "history", item_name)
            flash(f"Dodano do kolejki: {item_name}", "success")
        else:
            flash("Wybierz skin z listy", "error")

        return redirect(url_for("main.scraper"))

    db = get_mongo()
    items_count = db.items.count_documents({})
    return render_template(
        "scraper.html",
        queue_length=get_queue_length(),
        items_count=items_count,
        catalog_count=get_catalog_count(),
    )


@main_bp.route("/scraper/refresh-all", methods=["POST"])
def scraper_refresh_all():
    db    = get_mongo()
    items = list(db.items.find({}, {"_id": 0, "name": 1, "source": 1}))
    count = 0
    seen  = set()
    for item in items:
        push_scrape_task(item["source"], "history", item["name"])
        count += 1
        # Also refresh Skinport for each Steam item (avoid duplicates)
        if item["source"] == "steam" and item["name"] not in seen:
            push_scrape_task("skinport", "history", item["name"])
            seen.add(item["name"])
            count += 1
    flash(f"Dodano {count} zadań historii cen do kolejki.", "success")
    return redirect(url_for("main.scraper"))


@main_bp.route("/logs")
def logs():
    return render_template("logs.html", logs=fetch_recent_logs(50))


@main_bp.route("/scraper/clear-all", methods=["POST"])
def scraper_clear_all():
    result = clear_all_items()
    flash(
        f"Baza wyczyszczona: usunięto {result['items']} skinów i {result['prices']} rekordów cen.",
        "success",
    )
    return redirect(url_for("main.scraper"))


@main_bp.route("/browse")
def browse():
    return redirect(url_for("main.scraper"))
