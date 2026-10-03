"""Casos de uso del participante: ver su mochila virtual."""
from __future__ import annotations

from ..domain.entidades import Item, Seccion, TipoItem, Usuario
from ..domain.errores import NoEncontrado
from ..domain.puertos import (
    RegistroActividad,
    RepositorioArchivos,
    RepositorioItems,
    RepositorioSecciones,
)


def adjuntar_archivos(items: list[Item], archivos: RepositorioArchivos) -> list[Item]:
    ids = [i.archivo_id for i in items if i.archivo_id]
    if ids:
        por_id = archivos.por_ids(ids)
        for item in items:
            if item.archivo_id:
                item.archivo = por_id.get(item.archivo_id)
    return items


class ServicioMochila:
    def __init__(
        self,
        secciones: RepositorioSecciones,
        items: RepositorioItems,
        archivos: RepositorioArchivos,
        actividad: RegistroActividad,
    ):
        self._secciones = secciones
        self._items = items
        self._archivos = archivos
        self._actividad = actividad

    def indice(self) -> list[tuple[Seccion, int]]:
        """Secciones activas con cuántos ítems visibles tiene cada una (sin el contenido)."""
        secciones = self._secciones.listar(solo_activas=True)
        items = self._items.de_secciones([s.id for s in secciones], solo_activos=True)
        conteo: dict[int, int] = {}
        for item in items:
            conteo[item.seccion_id] = conteo.get(item.seccion_id, 0) + 1
        return [(s, conteo.get(s.id, 0)) for s in secciones]

    def proximos_eventos(self, ahora: str, limite: int = 3) -> list[Item]:
        """Eventos del cronograma que están en curso o vienen después de `ahora` ("AAAA-MM-DD HH:MM", hora local)."""
        secciones = self._secciones.listar(solo_activas=True)
        eventos = [
            i for i in self._items.de_secciones([s.id for s in secciones], solo_activos=True)
            if i.tipo == TipoItem.EVENTO
        ]

        def fin(e: Item) -> str:
            # Sin hora de fin se asume una hora de duración; sin horas, todo el día.
            if e.hora_fin:
                return f"{e.fecha} {e.hora_fin}"
            if e.hora_inicio:
                h, m = map(int, e.hora_inicio.split(":"))
                return f"{e.fecha} {min(h + 1, 23):02d}:{m:02d}"
            return f"{e.fecha} 23:59"

        pendientes = sorted((e for e in eventos if fin(e) >= ahora), key=lambda e: (e.fecha, e.hora_inicio))
        return pendientes[:limite]

    def seccion(self, usuario: Usuario, seccion_id: int) -> Seccion:
        seccion = self._secciones.por_id(seccion_id)
        if not seccion or not seccion.activa:
            raise NoEncontrado("Esa sección no existe o ya no está disponible.")
        seccion.items = adjuntar_archivos(
            self._items.de_seccion(seccion_id, solo_activos=True), self._archivos
        )
        self._actividad.registrar("vista_seccion", usuario.id, seccion_id)
        return seccion
