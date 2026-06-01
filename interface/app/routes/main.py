from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.db import (
    fetch_items, fetch_item, fetch_recent_logs,
    fetch_price_history, fetch_listings,
    push_scrape_task, get_queue_length, get_mongo,
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
        logs=fetch_recent_logs(10),
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

    return render_template(
        "item_detail.html",
        item=item,
        latest_price=fetch_price_history(name, source, 1)[0] if fetch_price_history(name, source, 1) else None,
        listings=fetch_listings(name, source),
    )


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
            flash("Podaj nazwę przedmiotu", "error")

        return redirect(url_for("main.scraper"))

    return render_template("scraper.html", queue_length=get_queue_length())


@main_bp.route("/logs")
def logs():
    return render_template("logs.html", logs=fetch_recent_logs(50))