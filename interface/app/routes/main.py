from flask import Blueprint, render_template
from app.db import fetch_recent_logs, get_queue_length, get_mongo

main_bp = Blueprint("main", __name__)


def get_stats() -> dict:
    db = get_mongo()
    return {
        "items_count": db.items.count_documents({}),
        "prices":   db.prices.count_documents({}),
        "listings": db.listings.count_documents({}),
        "queue":    get_queue_length(),
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
    return render_template("index.html", stats=get_stats(), logs=[])


@main_bp.route("/scraper")
def scraper():
    return render_template("index.html", stats=get_stats(), logs=[])


@main_bp.route("/logs")
def logs():
    return render_template("index.html", stats=get_stats(), logs=[])