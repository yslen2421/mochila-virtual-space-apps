"""Estadísticas básicas para el Superadmin."""
from __future__ import annotations

from ..domain.entidades import Rol
from ..domain.puertos import RegistroActividad, RepositorioUsuarios


class ServicioEstadisticas:
    def __init__(self, usuarios: RepositorioUsuarios, actividad: RegistroActividad):
        self._usuarios = usuarios
        self._actividad = actividad

    def resumen(self) -> dict:
        participantes = [u for u in self._usuarios.listar() if u.rol == Rol.PARTICIPANTE]
        por_modalidad: dict[str, int] = {}
        for u in participantes:
            por_modalidad[u.modalidad.value] = por_modalidad.get(u.modalidad.value, 0) + 1
        return {
            "participantes": {
                "total": len(participantes),
                "activos": sum(u.activo for u in participantes),
                "han_ingresado": sum(u.ultimo_login is not None for u in participantes),
                "por_modalidad": por_modalidad,
            },
            **self._actividad.resumen(),
        }
