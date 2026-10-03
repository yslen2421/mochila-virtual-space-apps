"""Errores del dominio.

Cada error lleva un `codigo` estable (para el front) y un mensaje legible.
La capa de presentación los traduce a HTTP; el dominio no sabe nada de HTTP.
"""


class ErrorDominio(Exception):
    codigo = "ERROR_DOMINIO"

    def __init__(self, mensaje: str, detalle: dict | list | str | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalle = detalle


class ErrorValidacion(ErrorDominio):
    codigo = "VALIDACION"


class NoEncontrado(ErrorDominio):
    codigo = "NO_ENCONTRADO"


class Conflicto(ErrorDominio):
    codigo = "CONFLICTO"


class NoAutenticado(ErrorDominio):
    codigo = "NO_AUTENTICADO"


class SinPermiso(ErrorDominio):
    codigo = "SIN_PERMISO"


class DemasiadosIntentos(ErrorDominio):
    codigo = "DEMASIADOS_INTENTOS"
