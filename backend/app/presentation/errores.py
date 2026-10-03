"""Traducción uniforme de errores a JSON: {"error": {"codigo", "mensaje", "detalle"}}."""
from __future__ import annotations

import logging

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from ..domain.errores import (
    Conflicto,
    DemasiadosIntentos,
    ErrorDominio,
    ErrorValidacion,
    NoAutenticado,
    NoEncontrado,
    SinPermiso,
)

ESTADO_HTTP = {
    ErrorValidacion: 400,
    NoAutenticado: 401,
    SinPermiso: 403,
    NoEncontrado: 404,
    Conflicto: 409,
    DemasiadosIntentos: 429,
}

MENSAJES_HTTP = {
    400: ("PETICION_INVALIDA", "La petición no es válida."),
    401: ("NO_AUTENTICADO", "Inicia sesión para continuar."),
    403: ("SIN_PERMISO", "No tienes permiso para esta acción."),
    404: ("NO_ENCONTRADO", "Recurso no encontrado."),
    405: ("METODO_NO_PERMITIDO", "Método no permitido."),
    413: ("ARCHIVO_DEMASIADO_GRANDE", "El archivo supera el tamaño máximo permitido."),
    415: ("TIPO_NO_SOPORTADO", "Envía los datos como JSON."),
    429: ("DEMASIADOS_INTENTOS", "Demasiadas peticiones, espera un momento."),
}

log = logging.getLogger("portal")


def cuerpo_error(codigo: str, mensaje: str, detalle=None):
    return jsonify(error={"codigo": codigo, "mensaje": mensaje, "detalle": detalle})


def registrar_manejadores(app: Flask) -> None:
    @app.errorhandler(ErrorDominio)
    def _dominio(e: ErrorDominio):
        estado = next((s for t, s in ESTADO_HTTP.items() if isinstance(e, t)), 400)
        return cuerpo_error(e.codigo, e.mensaje, e.detalle), estado

    @app.errorhandler(HTTPException)
    def _http(e: HTTPException):
        codigo, mensaje = MENSAJES_HTTP.get(e.code, ("ERROR_HTTP", e.description or "Error"))
        if e.code == 413:
            mensaje += f" (máximo {app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)} MB)"
        return cuerpo_error(codigo, mensaje), e.code

    @app.errorhandler(Exception)
    def _inesperado(e: Exception):
        log.exception("Error no controlado")
        return cuerpo_error("ERROR_INTERNO", "Algo salió mal en el servidor. Intenta de nuevo."), 500
