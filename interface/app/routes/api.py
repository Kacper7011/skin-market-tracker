from flask import Blueprint, jsonify, request
from app.db import (
    fetch_items,
    fetch_item,
    fetch_price_history,
    fetch_recent_logs,
    push_scrape_task,
    get_queue_length,
    steam_search_proxy,
    search_skin_catalog,
    get_catalog_count,
    browse_skin_catalog,
    get_exchange_rates,
    get_inspect_float,
    steam_browse_search,
    get_steam_live_listings,
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


# ---------- Search (Steam first, catalog fallback) ----------

@api_bp.route("/search/steam")
def search_steam():
    q     = request.args.get("q", "").strip()
    count = min(int(request.args.get("count", 30)), 50)

    if not q or len(q) < 2:
        return jsonify([])

    # Always try live Steam search first (returns all wear variants)
    results = steam_search_proxy(q, count)
    if results:
        return jsonify(results)

    # Fallback: local catalog if Steam is unavailable
    local = search_skin_catalog(q, limit=count)
    return jsonify(local)


@api_bp.route("/catalog/count")
def catalog_count():
    return jsonify({"count": get_catalog_count()})


@api_bp.route("/catalog/browse")
def catalog_browse():
    item_type = request.args.get("type", "")
    weapon    = request.args.get("weapon", "")
    wear      = request.args.get("wear", "")
    stattrak  = request.args.get("stattrak", "")
    page      = max(1, int(request.args.get("page", 1)))
    result = browse_skin_catalog(item_type, weapon, wear, stattrak, page)
    return jsonify(result)


@api_bp.route("/browse")
def browse_api():
    # Map frontend category key → Steam type tags
    TYPE_TAG_MAP = {
        "Rifle":              ["tag_CSGO_Type_Rifle"],
        "Pistol":             ["tag_CSGO_Type_Pistol"],
        "SMG":                ["tag_CSGO_Type_SMGun"],
        "Shotgun,Machine Gun":["tag_CSGO_Type_Shotgun", "tag_CSGO_Type_Machinegun"],
        "Knife":              ["tag_CSGO_Type_Knife"],
        "Gloves":             ["tag_CSGO_Type_Hands"],
        "Agent":              ["tag_CSGO_Type_Agent"],
        "Sticker":            ["tag_CSGO_Type_Sticker"],
        "Container":          ["tag_CSGO_Type_WeaponCase"],
        "Key":                ["tag_CSGO_Type_WeaponCase_KeyTag"],
        "Graffiti":           ["tag_CSGO_Type_Spray"],
        "Patch":              ["tag_CSGO_Type_Patch"],
    }

    # Map wear display names → Steam exterior tags
    WEAR_TAG_MAP = {
        "Factory New":    "tag_WearCategory0",
        "Minimal Wear":   "tag_WearCategory1",
        "Field-Tested":   "tag_WearCategory2",
        "Well-Worn":      "tag_WearCategory3",
        "Battle-Scarred": "tag_WearCategory4",
    }

    cat      = request.args.get("type", "")
    weapon   = request.args.get("weapon", "")   # Steam weapon tag, e.g. "tag_weapon_ak47"
    wears    = request.args.getlist("wear")      # display wear names
    quality  = request.args.get("quality", "")  # "" | "tag_strange" | "tag_tournament"
    start    = max(0, int(request.args.get("start", 0)))
    count    = min(48, max(1, int(request.args.get("count", 48))))

    type_tags   = TYPE_TAG_MAP.get(cat, [])
    weapon_tags = [weapon] if weapon else []
    wear_tags   = [WEAR_TAG_MAP[w] for w in wears if w in WEAR_TAG_MAP]

    result = steam_browse_search(type_tags, weapon_tags, wear_tags, quality, start, count)
    return jsonify(result)


# ---------- Live listings ----------

@api_bp.route("/live-listings/<path:name>")
def live_listings(name: str):
    return jsonify(get_steam_live_listings(name))


# ---------- Exchange rates ----------

@api_bp.route("/exchange-rates")
def exchange_rates():
    return jsonify(get_exchange_rates())


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
