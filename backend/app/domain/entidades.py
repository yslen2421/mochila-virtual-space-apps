"""Entidades del dominio: Usuario, Sección, Ítem y Archivo.

Son clases Python puras: no importan Flask, SQLite ni nada de infraestructura.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Rol(str, Enum):
    PARTICIPANTE = "participante"
    SUPERADMIN = "superadmin"


class Modalidad(str, Enum):
    PRESENCIAL = "presencial"
    VIRTUAL = "virtual"


class TipoItem(str, Enum):
    TEXTO = "texto"          # Párrafos de texto (guías, anuncios, FAQ…)
    ENLACE = "enlace"        # Un link externo (Zoom, Meet, datos NASA, AWS…)
    ARCHIVO = "archivo"      # Descargable (PDF, ZIP, certificado…)
    IMAGEN = "imagen"        # Imagen con vista previa y descarga (wallpapers, stickers)
    EVENTO = "evento"        # Entrada de cronograma (fecha, horas, lugar, link)


@dataclass
class Usuario:
    id: int | None
    usuario: str
    nombre: str
    rol: Rol
    password_hash: str
    email: str = ""
    modalidad: Modalidad = Modalidad.PRESENCIAL
    activo: bool = True
    version_token: int = 1          # sube al resetear contraseña o desactivar → invalida sesiones
    creado_en: datetime | None = None
    ultimo_login: datetime | None = None

    @property
    def es_superadmin(self) -> bool:
        return self.rol == Rol.SUPERADMIN

    def invalidar_sesiones(self) -> None:
        self.version_token += 1


@dataclass
class Seccion:
    id: int | None
    titulo: str
    descripcion: str = ""
    icono: str = "📦"
    orden: int = 0
    activa: bool = True
    items: list["Item"] = field(default_factory=list)


@dataclass
class Item:
    id: int | None
    seccion_id: int
    tipo: TipoItem
    titulo: str
    descripcion: str = ""
    url: str = ""
    archivo_id: int | None = None
    # Datos propios de un evento de cronograma
    fecha: str = ""          # AAAA-MM-DD
    hora_inicio: str = ""    # HH:MM
    hora_fin: str = ""       # HH:MM
    lugar: str = ""
    orden: int = 0
    activo: bool = True
    archivo: "Archivo | None" = None   # se completa al leer, para mostrar nombre/tamaño


@dataclass
class Archivo:
    id: int | None
    nombre_original: str
    nombre_guardado: str
    tipo_mime: str
    tamano_bytes: int
    creado_en: datetime | None = None
