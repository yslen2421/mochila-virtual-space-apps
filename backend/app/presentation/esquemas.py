"""Validación en el borde: JSON crudo → comandos tipados.

Nada de lo que llega del navegador pasa al dominio sin pasar por aquí.
"""
from __future__ import annotations

from typing import Any

from ..application.comandos import (
    ActualizarItem,
    ActualizarSeccion,
    ActualizarUsuario,
    CrearItem,
    CrearSeccion,
    CrearUsuario,
)
from ..domain.entidades import Modalidad, Rol, TipoItem
from ..domain.errores import ErrorValidacion


def _cuerpo(datos: Any) -> dict:
    if not isinstance(datos, dict):
        raise ErrorValidacion("El cuerpo de la petición debe ser un objeto JSON.")
    return datos


def _texto(d: dict, campo: str, requerido: bool = False, maximo: int = 20000) -> str | None:
    valor = d.get(campo)
    if valor is None:
        if requerido:
            raise ErrorValidacion(f"Falta el campo '{campo}'.", {"campo": campo})
        return None
    if not isinstance(valor, str):
        raise ErrorValidacion(f"El campo '{campo}' debe ser texto.", {"campo": campo})
    if len(valor) > maximo:
        raise ErrorValidacion(f"El campo '{campo}' es demasiado largo.", {"campo": campo})
    return valor


def _booleano(d: dict, campo: str) -> bool | None:
    valor = d.get(campo)
    if valor is None:
        return None
    if not isinstance(valor, bool):
        raise ErrorValidacion(f"El campo '{campo}' debe ser verdadero o falso.", {"campo": campo})
    return valor


def _entero(d: dict, campo: str) -> int | None:
    valor = d.get(campo)
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErrorValidacion(f"El campo '{campo}' debe ser un número entero.", {"campo": campo})
    return valor


def _enum(d: dict, campo: str, tipo, requerido: bool = False):
    valor = _texto(d, campo, requerido)
    if valor is None:
        return None
    try:
        return tipo(valor.strip().lower())
    except ValueError:
        raise ErrorValidacion(
            f"Valor no válido para '{campo}'.", {"campo": campo, "permitidos": [e.value for e in tipo]})


def _sin_nulos(**kwargs) -> dict:
    return {k: v for k, v in kwargs.items() if v is not None}


# ---------------------------------------------------------------- auth

def credenciales(datos: Any) -> tuple[str, str]:
    d = _cuerpo(datos)
    return _texto(d, "usuario", True, 100), _texto(d, "contrasena", True, 200)


def cambio_contrasena(datos: Any) -> tuple[str, str]:
    d = _cuerpo(datos)
    return _texto(d, "actual", True, 200), _texto(d, "nueva", True, 200)


def lista_ids(datos: Any) -> list[int]:
    d = _cuerpo(datos)
    ids = d.get("ids")
    if not isinstance(ids, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
        raise ErrorValidacion("Envía 'ids' como una lista de números.", {"campo": "ids"})
    return ids


# ---------------------------------------------------------------- secciones

def crear_seccion(datos: Any) -> CrearSeccion:
    d = _cuerpo(datos)
    return CrearSeccion(**_sin_nulos(
        titulo=_texto(d, "titulo", True, 120), descripcion=_texto(d, "descripcion", maximo=2000),
        icono=_texto(d, "icono", maximo=16), activa=_booleano(d, "activa")))


def actualizar_seccion(datos: Any) -> ActualizarSeccion:
    d = _cuerpo(datos)
    return ActualizarSeccion(
        titulo=_texto(d, "titulo", maximo=120), descripcion=_texto(d, "descripcion", maximo=2000),
        icono=_texto(d, "icono", maximo=16), activa=_booleano(d, "activa"))


# ---------------------------------------------------------------- ítems

def _campos_item(d: dict) -> dict:
    return dict(
        titulo=_texto(d, "titulo", maximo=200), descripcion=_texto(d, "descripcion"),
        url=_texto(d, "url", maximo=2000), archivo_id=_entero(d, "archivo_id"),
        fecha=_texto(d, "fecha", maximo=10), hora_inicio=_texto(d, "hora_inicio", maximo=5),
        hora_fin=_texto(d, "hora_fin", maximo=5), lugar=_texto(d, "lugar", maximo=200),
        activo=_booleano(d, "activo"))


def crear_item(datos: Any) -> CrearItem:
    d = _cuerpo(datos)
    campos = _campos_item(d)
    if campos["titulo"] is None:
        raise ErrorValidacion("Falta el campo 'titulo'.", {"campo": "titulo"})
    return CrearItem(tipo=_enum(d, "tipo", TipoItem, True), **_sin_nulos(**campos))


def actualizar_item(datos: Any) -> ActualizarItem:
    d = _cuerpo(datos)
    return ActualizarItem(tipo=_enum(d, "tipo", TipoItem), **_campos_item(d))


# ---------------------------------------------------------------- usuarios

def crear_usuario(datos: Any) -> CrearUsuario:
    d = _cuerpo(datos)
    return CrearUsuario(**_sin_nulos(
        usuario=_texto(d, "usuario", True, 100), nombre=_texto(d, "nombre", True, 120),
        email=_texto(d, "email", maximo=200), modalidad=_enum(d, "modalidad", Modalidad),
        rol=_enum(d, "rol", Rol), contrasena=_texto(d, "contrasena", maximo=200) or None))


def importar_usuarios(datos: Any) -> list[CrearUsuario]:
    d = _cuerpo(datos)
    filas = d.get("usuarios")
    if not isinstance(filas, list):
        raise ErrorValidacion("Envía 'usuarios' como una lista.", {"campo": "usuarios"})
    comandos, errores = [], []
    for n, fila in enumerate(filas, start=1):
        try:
            if isinstance(fila, dict):
                fila = {**fila, "rol": "participante"}  # la importación masiva solo crea participantes
            comandos.append(crear_usuario(fila))
        except ErrorValidacion as e:
            usuario = fila.get("usuario") if isinstance(fila, dict) else None
            errores.append({"fila": n, "usuario": usuario, "error": e.mensaje})
    if errores:
        raise ErrorValidacion("Hay filas con errores; no se importó nada.", errores)
    return comandos


def actualizar_usuario(datos: Any) -> ActualizarUsuario:
    d = _cuerpo(datos)
    return ActualizarUsuario(
        nombre=_texto(d, "nombre", maximo=120), email=_texto(d, "email", maximo=200),
        modalidad=_enum(d, "modalidad", Modalidad), activo=_booleano(d, "activo"))
