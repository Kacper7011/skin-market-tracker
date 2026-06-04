from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.db import (
    fetch_items, fetch_item, fetch_recent_logs,
    fetch_price_history, fetch_listings,
    push_scrape_task, get_queue_length, get_mongo,
    get_catalog_count,
)

main_bp = Blueprint("main", __name__)


def get_stats() -> dict:
    db = get_mongo()
    return {
        "items_count": db.items.count_documents({}),
        "prices":      db.prices.count_documents({}),
        "listings":    db.listings.count_documents({}),
        "queue":       get_queue_length(),
    }


@main_bp.route("/")
def index():
    return render_template(
        "index.html",
        stats=get_stats(),
        logs=fetch_recent_logs(8),
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
        listings=fetch_listings(name, source),
    )


@main_bp.route("/items/<path:name>/live")
def live_listings(name: str):
    source = request.args.get("source", "steam")
    item   = fetch_item(name, source)
    return render_template("live_listings.html", item=item, item_name=name)


@main_bp.route("/scraper", methods=["GET", "POST"])
def scraper():
    if request.method == "POST":
        item_name = request.form.get("item_name", "").strip()
        action    = request.form.get("action", "search")
        source    = request.form.get("source", "steam")

        if item_name:
            push_scrape_task(source, action, item_name)
            flash(f"Dodano do kolejki: {item_name}", "success")
        else:
            flash("Wybierz lub wpisz nazwę skina", "error")

        return redirect(url_for("main.scraper"))

    db    = get_mongo()
    items = list(db.items.find({}, {"_id": 0, "name": 1, "source": 1, "icon_url": 1, "wear": 1}).limit(200))
    return render_template(
        "scraper.html",
        queue_length=get_queue_length(),
        items=items,
        catalog_count=get_catalog_count(),
    )


@main_bp.route("/scraper/refresh-all", methods=["POST"])
def scraper_refresh_all():
    db    = get_mongo()
    items = list(db.items.find({}, {"_id": 0, "name": 1, "source": 1}))
    count = 0
    for item in items:
        push_scrape_task(item["source"], "history", item["name"])
        count += 1
    flash(f"Dodano {count} zadań historii cen do kolejki.", "success")
    return redirect(url_for("main.scraper"))


@main_bp.route("/logs")
def logs():
    return render_template("logs.html", logs=fetch_recent_logs(50))
