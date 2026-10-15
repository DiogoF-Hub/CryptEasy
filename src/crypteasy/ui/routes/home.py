from flask import Blueprint, render_template

from . import backend

bp = Blueprint("home", __name__)


@bp.get("/")
def index():
    b = backend()
    return render_template("home.html", identities=b.list_identities(),
                           contacts=b.list_contacts())


@bp.get("/info")
def info():
    return render_template("info.html")
