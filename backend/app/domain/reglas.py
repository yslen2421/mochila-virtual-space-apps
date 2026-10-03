"""Reglas de negocio puras (sin framework, sin persistencia)."""
from __future__ import annotations

import re
from typing import Callable

from .entidades import Aliado, GrupoAliados, Item, Rol, Seccion, TipoItem, Usuario
from .errores import ErrorValidacion

PATRON_USUARIO = re.compile(r"^[a-z0-9._-]{3,40}$")
PATRON_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PATRON_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
LARGO_MINIMO_CONTRASENA = 8


def normalizar_usuario(usuario: str) -> str:
    return (usuario or "").strip().lower()


def validar_usuario(usuario: str) -> str:
    usuario = normalizar_usuario(usuario)
    if not PATRON_USUARIO.match(usuario):
        raise ErrorValidacion(
            "El usuario debe tener de 3 a 40 caracteres: letras minúsculas, números, punto, guion o guion bajo.",
            {"campo": "usuario"},
        )
    return usuario


def validar_contrasena(contrasena: str) -> None:
    if not contrasena or len(contrasena) < LARGO_MINIMO_CONTRASENA:
        raise ErrorValidacion(
            f"La contraseña debe tener al menos {LARGO_MINIMO_CONTRASENA} caracteres.",
            {"campo": "contrasena"},
        )
    if len(contrasena) > 128:
        raise ErrorValidacion("La contraseña es demasiado larga.", {"campo": "contrasena"})


def validar_seccion(seccion: Seccion) -> None:
    if not seccion.titulo.strip():
        raise ErrorValidacion("La sección necesita un título.", {"campo": "titulo"})
    if len(seccion.titulo) > 120:
        raise ErrorValidacion("El título no puede superar 120 caracteres.", {"campo": "titulo"})


def _url_valida(url: str) -> bool:
    return url.startswith("https://") or url.startswith("http://")


# --- Validación de ítems: una regla por tipo (agregar un tipo = agregar una regla) ---

def _regla_texto(item: Item) -> None:
    if not item.descripcion.strip():
        raise ErrorValidacion("Un ítem de texto necesita contenido.", {"campo": "descripcion"})


def _regla_enlace(item: Item) -> None:
    if not _url_valida(item.url):
        raise ErrorValidacion("El enlace debe empezar por https:// o http://", {"campo": "url"})


def _regla_archivo(item: Item) -> None:
    if not item.archivo_id:
        raise ErrorValidacion("Sube un archivo para este ítem.", {"campo": "archivo_id"})


def _regla_evento(item: Item) -> None:
    if not PATRON_FECHA.match(item.fecha):
        raise ErrorValidacion("La fecha del evento debe tener formato AAAA-MM-DD.", {"campo": "fecha"})
    if item.hora_inicio and not PATRON_HORA.match(item.hora_inicio):
        raise ErrorValidacion("La hora de inicio debe tener formato HH:MM.", {"campo": "hora_inicio"})
    if item.hora_fin and not PATRON_HORA.match(item.hora_fin):
        raise ErrorValidacion("La hora de fin debe tener formato HH:MM.", {"campo": "hora_fin"})
    if item.hora_inicio and item.hora_fin and item.hora_fin < item.hora_inicio:
        raise ErrorValidacion("La hora de fin no puede ser anterior a la de inicio.", {"campo": "hora_fin"})
    if item.url and not _url_valida(item.url):
        raise ErrorValidacion("El enlace del evento debe empezar por https:// o http://", {"campo": "url"})


REGLAS_POR_TIPO: dict[TipoItem, Callable[[Item], None]] = {
    TipoItem.TEXTO: _regla_texto,
    TipoItem.ENLACE: _regla_enlace,
    TipoItem.ARCHIVO: _regla_archivo,
    TipoItem.IMAGEN: _regla_archivo,
    TipoItem.EVENTO: _regla_evento,
}


TIPOS_CON_ARCHIVO = {TipoItem.ARCHIVO, TipoItem.IMAGEN}


def normalizar_item(item: Item) -> Item:
    """Limpia espacios y descarta campos que no aplican al tipo del ítem."""
    item.titulo = item.titulo.strip()
    item.url = item.url.strip()
    if item.tipo not in TIPOS_CON_ARCHIVO:
        item.archivo_id = None
    if item.tipo != TipoItem.EVENTO:
        item.fecha = item.hora_inicio = item.hora_fin = item.lugar = ""
    return item


def validar_item(item: Item) -> None:
    normalizar_item(item)
    if not item.titulo:
        raise ErrorValidacion("El ítem necesita un título.", {"campo": "titulo"})
    if len(item.titulo) > 200:
        raise ErrorValidacion("El título no puede superar 200 caracteres.", {"campo": "titulo"})
    if len(item.descripcion) > 20000:
        raise ErrorValidacion("El contenido es demasiado largo.", {"campo": "descripcion"})
    REGLAS_POR_TIPO[item.tipo](item)


def validar_reorden(ids_actuales: list[int], ids_nuevos: list[int]) -> None:
    if sorted(ids_actuales) != sorted(ids_nuevos):
        raise ErrorValidacion(
            "El nuevo orden debe incluir exactamente los mismos elementos, sin repetir.",
            {"esperados": sorted(ids_actuales)},
        )


def validar_grupo_aliados(grupo: GrupoAliados) -> None:
    grupo.titulo = grupo.titulo.strip()
    if not grupo.titulo:
        raise ErrorValidacion("El grupo necesita un nombre.", {"campo": "titulo"})
    if len(grupo.titulo) > 80:
        raise ErrorValidacion("El nombre del grupo no puede superar 80 caracteres.", {"campo": "titulo"})


def validar_aliado(aliado: Aliado) -> None:
    aliado.nombre = aliado.nombre.strip()
    aliado.url = aliado.url.strip()
    if not aliado.nombre:
        raise ErrorValidacion("Escribe el nombre de la organización.", {"campo": "nombre"})
    if len(aliado.nombre) > 120:
        raise ErrorValidacion("El nombre no puede superar 120 caracteres.", {"campo": "nombre"})
    if aliado.url and not _url_valida(aliado.url):
        raise ErrorValidacion("El enlace debe empezar por https:// o http://", {"campo": "url"})


def normalizar_equipo(equipo: str) -> str:
    """Quita espacios repetidos para que "Los  Cometas " y "Los Cometas" sean el mismo equipo."""
    return " ".join((equipo or "").split())[:120]


def validar_datos_participante(usuario: Usuario) -> None:
    if usuario.rol == Rol.PARTICIPANTE and usuario.categoria is None:
        raise ErrorValidacion("Elige la categoría: universidad o bachillerato.", {"campo": "categoria"})


PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validar_email(email: str) -> str:
    """Correo opcional de contacto; si viene, debe tener forma de correo."""
    email = (email or "").strip()
    if email and (len(email) > 200 or not PATRON_EMAIL.match(email)):
        raise ErrorValidacion(f"El correo «{email}» no parece válido.", {"campo": "email"})
    return email
