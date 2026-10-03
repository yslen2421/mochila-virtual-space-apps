"""Comandos: datos ya validados en el borde que entran a los casos de uso.

`None` en un campo de un comando de actualización significa "no cambiar".
"""
from __future__ import annotations

from dataclasses import dataclass

from ..domain.entidades import Modalidad, Rol, TipoItem


@dataclass(frozen=True)
class CrearSeccion:
    titulo: str
    descripcion: str = ""
    icono: str = "📦"
    activa: bool = True


@dataclass(frozen=True)
class ActualizarSeccion:
    titulo: str | None = None
    descripcion: str | None = None
    icono: str | None = None
    activa: bool | None = None


@dataclass(frozen=True)
class CrearItem:
    tipo: TipoItem
    titulo: str
    descripcion: str = ""
    url: str = ""
    archivo_id: int | None = None
    fecha: str = ""
    hora_inicio: str = ""
    hora_fin: str = ""
    lugar: str = ""
    activo: bool = True


@dataclass(frozen=True)
class ActualizarItem:
    tipo: TipoItem | None = None
    titulo: str | None = None
    descripcion: str | None = None
    url: str | None = None
    archivo_id: int | None = None
    fecha: str | None = None
    hora_inicio: str | None = None
    hora_fin: str | None = None
    lugar: str | None = None
    activo: bool | None = None


@dataclass(frozen=True)
class CrearUsuario:
    usuario: str
    nombre: str
    email: str = ""
    modalidad: Modalidad = Modalidad.PRESENCIAL
    rol: Rol = Rol.PARTICIPANTE
    contrasena: str | None = None   # None → se genera una


@dataclass(frozen=True)
class ActualizarUsuario:
    nombre: str | None = None
    email: str | None = None
    modalidad: Modalidad | None = None
    activo: bool | None = None
