"""Casos de uso del Superadmin sobre el contenido: secciones e ítems."""
from __future__ import annotations

from dataclasses import fields, replace

from ..domain.entidades import Item, Seccion
from ..domain.errores import ErrorValidacion, NoEncontrado
from ..domain.puertos import RepositorioArchivos, RepositorioItems, RepositorioSecciones
from ..domain.reglas import validar_item, validar_reorden, validar_seccion
from .archivos import ServicioArchivos
from .comandos import ActualizarItem, ActualizarSeccion, CrearItem, CrearSeccion
from .mochila import adjuntar_archivos


def _cambios(comando) -> dict:
    """Solo los campos que el comando trae (None = no cambiar)."""
    return {f.name: getattr(comando, f.name) for f in fields(comando) if getattr(comando, f.name) is not None}


class ServicioSecciones:
    def __init__(self, secciones: RepositorioSecciones, items: RepositorioItems, archivos: ServicioArchivos):
        self._secciones = secciones
        self._items = items
        self._archivos = archivos

    def listar(self) -> list[tuple[Seccion, int]]:
        secciones = self._secciones.listar()
        items = self._items.de_secciones([s.id for s in secciones])
        conteo: dict[int, int] = {}
        for item in items:
            conteo[item.seccion_id] = conteo.get(item.seccion_id, 0) + 1
        return [(s, conteo.get(s.id, 0)) for s in secciones]

    def obtener(self, seccion_id: int) -> Seccion:
        seccion = self._secciones.por_id(seccion_id)
        if not seccion:
            raise NoEncontrado("La sección no existe.")
        return seccion

    def crear(self, cmd: CrearSeccion) -> Seccion:
        seccion = Seccion(
            id=None,
            titulo=cmd.titulo.strip(),
            descripcion=cmd.descripcion.strip(),
            icono=cmd.icono or "📦",
            activa=cmd.activa,
            orden=self._secciones.siguiente_orden(),
        )
        validar_seccion(seccion)
        return self._secciones.guardar(seccion)

    def actualizar(self, seccion_id: int, cmd: ActualizarSeccion) -> Seccion:
        seccion = replace(self.obtener(seccion_id), **_cambios(cmd))
        seccion.titulo = seccion.titulo.strip()
        validar_seccion(seccion)
        return self._secciones.guardar(seccion)

    def eliminar(self, seccion_id: int) -> None:
        self.obtener(seccion_id)
        self._secciones.eliminar(seccion_id)  # los ítems caen en cascada
        self._archivos.limpiar_huerfanos()

    def reordenar(self, ids_en_orden: list[int]) -> None:
        validar_reorden([s.id for s in self._secciones.listar()], ids_en_orden)
        self._secciones.reordenar(ids_en_orden)


class ServicioItems:
    def __init__(
        self,
        secciones: RepositorioSecciones,
        items: RepositorioItems,
        repo_archivos: RepositorioArchivos,
        archivos: ServicioArchivos,
    ):
        self._secciones = secciones
        self._items = items
        self._repo_archivos = repo_archivos
        self._archivos = archivos

    def _seccion_existe(self, seccion_id: int) -> None:
        if not self._secciones.por_id(seccion_id):
            raise NoEncontrado("La sección no existe.")

    def _obtener(self, item_id: int) -> Item:
        item = self._items.por_id(item_id)
        if not item:
            raise NoEncontrado("El ítem no existe.")
        return item

    def _validar_archivo(self, item: Item) -> None:
        if item.archivo_id and not self._repo_archivos.por_id(item.archivo_id):
            raise ErrorValidacion("El archivo indicado no existe. Vuelve a subirlo.", {"campo": "archivo_id"})

    def listar(self, seccion_id: int) -> list[Item]:
        self._seccion_existe(seccion_id)
        return adjuntar_archivos(self._items.de_seccion(seccion_id), self._repo_archivos)

    def crear(self, seccion_id: int, cmd: CrearItem) -> Item:
        self._seccion_existe(seccion_id)
        item = Item(id=None, seccion_id=seccion_id, orden=self._items.siguiente_orden(seccion_id), **_cambios(cmd))
        validar_item(item)
        self._validar_archivo(item)
        guardado = self._items.guardar(item)
        return adjuntar_archivos([guardado], self._repo_archivos)[0]

    def actualizar(self, item_id: int, cmd: ActualizarItem) -> Item:
        item = replace(self._obtener(item_id), **_cambios(cmd))
        item.archivo = None
        validar_item(item)
        self._validar_archivo(item)
        guardado = self._items.guardar(item)
        self._archivos.limpiar_huerfanos()
        return adjuntar_archivos([guardado], self._repo_archivos)[0]

    def eliminar(self, item_id: int) -> None:
        self._obtener(item_id)
        self._items.eliminar(item_id)
        self._archivos.limpiar_huerfanos()

    def reordenar(self, seccion_id: int, ids_en_orden: list[int]) -> None:
        self._seccion_existe(seccion_id)
        validar_reorden([i.id for i in self._items.de_seccion(seccion_id)], ids_en_orden)
        self._items.reordenar(seccion_id, ids_en_orden)
