"""Entidades → diccionarios JSON. Nunca se expone el hash de la contraseña."""
from __future__ import annotations

from ..domain.entidades import Archivo, Item, Seccion, Usuario


def _fecha(valor):
    return valor.isoformat() if valor else None


def usuario(u: Usuario) -> dict:
    return {
        "id": u.id, "usuario": u.usuario, "nombre": u.nombre, "email": u.email,
        "rol": u.rol.value, "modalidad": u.modalidad.value, "activo": u.activo,
        "creado_en": _fecha(u.creado_en), "ultimo_login": _fecha(u.ultimo_login),
    }


def archivo(a: Archivo | None) -> dict | None:
    if not a:
        return None
    return {"id": a.id, "nombre": a.nombre_original, "tipo_mime": a.tipo_mime,
            "tamano_bytes": a.tamano_bytes, "url": f"/api/v1/archivos/{a.id}"}


def item(i: Item) -> dict:
    return {
        "id": i.id, "seccion_id": i.seccion_id, "tipo": i.tipo.value, "titulo": i.titulo,
        "descripcion": i.descripcion, "url": i.url, "archivo_id": i.archivo_id,
        "archivo": archivo(i.archivo), "fecha": i.fecha, "hora_inicio": i.hora_inicio,
        "hora_fin": i.hora_fin, "lugar": i.lugar, "orden": i.orden, "activo": i.activo,
    }


def seccion(s: Seccion, cantidad_items: int | None = None, con_items: bool = False) -> dict:
    datos = {"id": s.id, "titulo": s.titulo, "descripcion": s.descripcion, "icono": s.icono,
             "orden": s.orden, "activa": s.activa}
    if cantidad_items is not None:
        datos["cantidad_items"] = cantidad_items
    if con_items:
        datos["items"] = [item(i) for i in s.items]
    return datos
