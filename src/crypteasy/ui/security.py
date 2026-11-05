"""Protections du serveur local (SPEC_TECHNIQUE § 8).

pywebview affiche nos pages via un petit serveur sur 127.0.0.1. Tant que l'appli est
ouverte, d'autres programmes du PC, ou un site ouvert dans le navigateur habituel,
pourraient essayer de l'appeler : d'où les contrôles ci-dessous.

Ordre des contrôles à chaque requête :
  1. en-tête Host  → 400 si ce n'est pas 127.0.0.1:<port> ou localhost:<port> (DNS rebinding)
  2. jeton de lancement → 403 si la session n'est pas authentifiée
  3. jeton CSRF (Flask-WTF) sur chaque POST → 400
Puis, sur chaque réponse : en-têtes de sécurité.
"""

from __future__ import annotations

import hmac
import secrets
from urllib.parse import urlencode

from flask import Flask, abort, redirect, request, session
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()


def init_security(app: Flask, *, port: int | None, launch_token: str) -> None:
    app.config.update(
        SECRET_KEY=secrets.token_bytes(32),  # nouvelle clé à chaque lancement
        # Les cookies ne tiennent pas compte du port : un nom par port évite qu'une
        # autre appli locale (ou une 2e instance) écrase notre session.
        SESSION_COOKIE_NAME=f"crypteasy_{port or 'test'}",
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_HTTPONLY=True,
        WTF_CSRF_TIME_LIMIT=None,  # le jeton vit autant que la session (= le lancement)
        LAUNCH_TOKEN=launch_token,
    )
    # port=None : uniquement pour le client de test Flask, qui envoie « localhost » sans port
    allowed_hosts = (
        {f"127.0.0.1:{port}", f"localhost:{port}"} if port else {"127.0.0.1", "localhost"}
    )

    # Enregistrés AVANT CSRFProtect : Flask exécute les before_request dans l'ordre.
    @app.before_request
    def check_host():
        if request.host not in allowed_hosts:
            abort(400, "bad-host")

    @app.before_request
    def check_launch_token():
        # CSS, JS et logo sont publics : la page « Accès refusé » doit pouvoir s'afficher
        if session.get("auth") or request.endpoint == "static":
            return None
        token = request.args.get("token", "")
        if token and hmac.compare_digest(token.encode(), launch_token.encode()):
            session.clear()
            session["auth"] = True
            # On retire le jeton de l'URL (historique, barre d'adresse)
            rest = {k: v for k, v in request.args.items() if k != "token"}
            return redirect(request.path + ("?" + urlencode(rest) if rest else ""))
        abort(403)

    csrf.init_app(app)

    @app.after_request
    def security_headers(resp):
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; "
            "form-action 'self'; base-uri 'none'"
        )
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        return resp
