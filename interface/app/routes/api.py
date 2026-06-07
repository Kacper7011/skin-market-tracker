from flask import Blueprint, jsonify, request
from app.db import (
    fetch_items,
    fetch_item,
    fetch_price_history,
    fetch_listings,
    fetch_recent_logs,
    push_scrape_task,
    get_queue_length,
    steam_search_proxy,
    get_live_listings,
    get_live_listings_ttl,
    search_skin_catalog,
    get_catalog_count,
    get_exchange_rates,
    get_inspect_float,
)

api_bp = Blueprint("api", __name__)


@api_bp.route("/health")
def health():
    return jsonify({"status": "ok", "service": "interface"})


@api_bp.route("/items")
def items():
    limit = int(request.args.get("limit", 50))
    return jsonify(fetch_items(limit))


@api_bp.route("/items/<path:name>")
def item_detail(name: str):
    source = request.args.get("source", "steam")
    item = fetch_item(name, source)
    if not item:
        return jsonify({"error": "nie znaleziono"}), 404
    return jsonify(item)


@api_bp.route("/prices/<path:name>")
def price_history(name: str):
    source = request.args.get("source", "steam")
    limit  = int(request.args.get("limit", 200))
    return jsonify(fetch_price_history(name, source, limit))


@api_bp.route("/listings/<path:name>")
def listings(name: str):
    source = request.args.get("source", "steam")
    return jsonify(fetch_listings(name, source))


@api_bp.route("/logs")
def logs():
    limit = int(request.args.get("limit", 20))
    return jsonify(fetch_recent_logs(limit))


@api_bp.route("/queue/push", methods=["POST"])
def queue_push():
    data      = request.get_json()
    source    = data.get("source", "steam")
    action    = data.get("action", "search")
    item_name = data.get("item_name")

    if not item_name:
        return jsonify({"error": "brak item_name"}), 400

    push_scrape_task(source, action, item_name)
    return jsonify({"status": "ok", "queued": item_name})


@api_bp.route("/queue/length")
def queue_length():
    return jsonify({"length": get_queue_length()})


# ---------- Search (catalog first, Steam fallback) ----------

@api_bp.route("/search/steam")
def search_steam():
    q     = request.args.get("q", "").strip()
    count = min(int(request.args.get("count", 30)), 50)

    # prefer local catalog
    if q and len(q) >= 2:
        local = search_skin_catalog(q, limit=count)
        if local:
            return jsonify(local)

    # fallback: live Steam search
    results = steam_search_proxy(q, count)
    return jsonify(results)


@api_bp.route("/catalog/count")
def catalog_count():
    return jsonify({"count": get_catalog_count()})


# ---------- Exchange rates ----------

@api_bp.route("/exchange-rates")
def exchange_rates():
    return jsonify(get_exchange_rates())


# ---------- Live listings (Redis-cached) ----------

@api_bp.route("/live-listings/<path:name>")
def live_listings(name: str):
    listings, from_cache = get_live_listings(name)
    ttl = get_live_listings_ttl(name)
    return jsonify({
        "listings": listings,
        "from_cache": from_cache,
        "ttl": ttl,
        "count": len(listings),
    })


# ---------- Inspect float (CSFloat proxy) ----------

@api_bp.route("/inspect-float")
def inspect_float_api():
    url = request.args.get("url", "").strip()
    if not url or not url.startswith("steam://"):
        return jsonify({"error": "invalid inspect url"}), 400
    result = get_inspect_float(url)
    if result:
        return jsonify(result)
    return jsonify({"error": "could not fetch"}), 503
