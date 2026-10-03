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
        por_categoria: dict[str, int] = {}
        for u in participantes:
            por_modalidad[u.modalidad.value] = por_modalidad.get(u.modalidad.value, 0) + 1
            if u.categoria:
                por_categoria[u.categoria.value] = por_categoria.get(u.categoria.value, 0) + 1
        equipos = {u.equipo.casefold() for u in participantes if u.equipo}
        return {
            "participantes": {
                "total": len(participantes),
                "activos": sum(u.activo for u in participantes),
                "han_ingresado": sum(u.ultimo_login is not None for u in participantes),
                "por_modalidad": por_modalidad,
                "por_categoria": por_categoria,
                "equipos": len(equipos),
                "sin_equipo": sum(not u.equipo for u in participantes),
            },
            **self._actividad.resumen(),
        }
