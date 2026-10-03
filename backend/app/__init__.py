"""Fábrica de la aplicación Flask."""
from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, send_from_directory
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from .configuracion import RAIZ_BACKEND, Configuracion
from .contenedor import construir
from .presentation.api import api
from .presentation.errores import registrar_manejadores

CARPETA_FRONTEND = (RAIZ_BACKEND.parent / "frontend").resolve()

CSP_FRONTEND = (
    "default-src 'self'; img-src 'self' blob: data:; style-src 'self'; font-src 'self'; "
    "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)


def create_app(config: Configuracion | None = None) -> Flask:
    config = config or Configuracion.desde_entorno()
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = config.max_subida_mb * 1024 * 1024
    app.config["JSON_AS_ASCII"] = False
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if config.detras_de_proxy:
        # Nginx pone la IP real del visitante en X-Forwarded-For (necesaria para el límite de intentos).
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    if config.origenes_cors:
        CORS(app, resources={r"/api/*": {"origins": config.origenes_cors}},
             allow_headers=["Authorization", "Content-Type"], max_age=600)

    app.extensions["contenedor"] = construir(config)
    app.register_blueprint(api)
    registrar_manejadores(app)

    from .cli import registrar_comandos
    registrar_comandos(app)

    if config.servir_frontend and CARPETA_FRONTEND.exists():
        _servir_frontend(app)

    @app.after_request
    def cabeceras_seguridad(respuesta):
        respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
        respuesta.headers.setdefault("Referrer-Policy", "no-referrer")
        respuesta.headers.setdefault("X-Frame-Options", "DENY")
        if respuesta.mimetype == "application/json":
            respuesta.headers["Cache-Control"] = "no-store"
        elif respuesta.mimetype == "text/html":
            respuesta.headers.setdefault("Content-Security-Policy", CSP_FRONTEND)
        return respuesta

    return app


def _servir_frontend(app: Flask) -> None:
    """Modo desarrollo / instalación sencilla: Flask sirve también los archivos estáticos.

    En producción con Nginx esto se desactiva (SERVIR_FRONTEND=0) y Nginx los sirve.
    """

    @app.get("/")
    def portal_participante():
        return send_from_directory(CARPETA_FRONTEND, "index.html")

    @app.get("/admin")
    @app.get("/admin/")
    def panel_admin():
        return send_from_directory(CARPETA_FRONTEND / "admin", "index.html")

    @app.get("/<path:ruta>")
    def estaticos(ruta: str):
        return send_from_directory(CARPETA_FRONTEND, ruta, max_age=300)
