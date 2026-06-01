from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.db import get_steam_auth_status, save_steam_auth
from app.services.steam_auth import steam_login

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/auth/steam", methods=["GET", "POST"])
def steam():
    if request.method == "POST":
        username   = request.form.get("username", "").strip()
        password   = request.form.get("password", "")
        guard_code = request.form.get("guard_code", "").strip()

        if not username or not password or not guard_code:
            flash("Wypełnij wszystkie pola.", "error")
            return render_template("auth_steam.html", current_auth=get_steam_auth_status())

        try:
            cookies = steam_login(username, password, guard_code)
            save_steam_auth(
                username=username,
                sessionid=cookies["sessionid"],
                login_secure=cookies["steamLoginSecure"],
            )
            flash(f"Zalogowano jako {username}. Sesja Steam aktywna.", "success")
            return redirect(url_for("main.index"))
        except Exception as exc:
            flash(f"Błąd logowania: {exc}", "error")

    return render_template("auth_steam.html", current_auth=get_steam_auth_status())
