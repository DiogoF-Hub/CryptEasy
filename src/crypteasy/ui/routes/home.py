"""Accueil, page Info et choix de la langue."""

from flask import Blueprint, current_app, render_template, request

from ..i18n import catalogs
from ..security_levels import ICONS, ORDER, PRESETS
from . import back_to, backend

bp = Blueprint("home", __name__)


@bp.get("/")
def index():
    b = backend()
    return render_template("home.html", identities=b.list_identities(), contacts=b.list_contacts())


@bp.get("/info")
def info():
    return render_template("info.html", levels=ORDER, icons=ICONS, presets=PRESETS)


@bp.post("/langue")
def language():
    """Change la langue et l'enregistre dans settings.json (§ 7.1)."""
    lang = request.form.get("lang", "")
    if lang in catalogs():
        current_app.config["LANGUAGE"] = lang
        b = backend()
        b.save_settings({**b.load_settings(), "language": lang})
    return back_to("home.index")
