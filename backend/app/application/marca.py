"""Casos de uso de la identidad del evento: logo y aliados.

El logo y los logos de aliados son públicos (se ven incluso en la pantalla de
ingreso, antes de iniciar sesión). Solo el Superadmin puede cambiarlos.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.entidades import Aliado, Archivo, GrupoAliados
from ..domain.errores import ErrorValidacion, NoEncontrado
from ..domain.puertos import RepositorioAjustes, RepositorioAliados, RepositorioArchivos
from ..domain.reglas import validar_aliado, validar_grupo_aliados, validar_reorden
from .archivos import ServicioArchivos

CLAVE_LOGO = "logo_archivo_id"
CLAVE_GRUPOS_BASE = "grupos_base_creados"
GRUPOS_BASE = ("Organizadores", "Patrocinadores", "Divulgadores")


@dataclass
class Marca:
    logo: Archivo | None
    grupos: list[GrupoAliados] = field(default_factory=list)


@dataclass(frozen=True)
class DatosAliado:
    nombre: str | None = None
    url: str | None = None
    archivo_id: int | None = None
    quitar_logo: bool = False


class ServicioMarca:
    def __init__(
        self,
        ajustes: RepositorioAjustes,
        aliados: RepositorioAliados,
        repo_archivos: RepositorioArchivos,
        archivos: ServicioArchivos,
    ):
        self._ajustes = ajustes
        self._aliados = aliados
        self._repo_archivos = repo_archivos
        self._archivos = archivos

    # ------------------------------------------------------------ lectura

    def marca(self, incluir_grupos_vacios: bool) -> Marca:
        grupos = self._aliados.grupos()
        todos = self._aliados.aliados()
        logo_id = self._logo_id()
        ids = {a.archivo_id for a in todos if a.archivo_id} | ({logo_id} if logo_id else set())
        por_id = self._repo_archivos.por_ids(list(ids))
        por_grupo: dict[int, list[Aliado]] = {}
        for aliado in todos:
            aliado.archivo = por_id.get(aliado.archivo_id) if aliado.archivo_id else None
            por_grupo.setdefault(aliado.grupo_id, []).append(aliado)
        for grupo in grupos:
            grupo.aliados = por_grupo.get(grupo.id, [])
        if not incluir_grupos_vacios:
            grupos = [g for g in grupos if g.aliados]
        return Marca(logo=por_id.get(logo_id) if logo_id else None, grupos=grupos)

    def archivo_publico(self, archivo_id: int, miniatura: bool) -> tuple[Archivo, str, bool]:
        """Archivos que cualquiera puede ver: el logo del evento y los logos de aliados."""
        es_publico = archivo_id == self._logo_id() or any(a.archivo_id == archivo_id for a in self._aliados.aliados())
        if not es_publico:
            raise NoEncontrado("El archivo no existe o no es público.")
        return self._archivos.ruta_publica(archivo_id, miniatura)

    # ------------------------------------------------------------ logo del evento

    def _logo_id(self) -> int | None:
        valor = self._ajustes.obtener(CLAVE_LOGO)
        return int(valor) if valor else None

    def _exigir_imagen(self, archivo_id: int) -> Archivo:
        archivo = self._repo_archivos.por_id(archivo_id)
        if not archivo:
            raise ErrorValidacion("El archivo no existe. Vuelve a subirlo.", {"campo": "archivo_id"})
        if not archivo.tipo_mime.startswith("image/"):
            raise ErrorValidacion("El logo debe ser una imagen (PNG, JPG, SVG o WebP).", {"campo": "archivo_id"})
        return archivo

    def fijar_logo(self, archivo_id: int | None) -> Archivo | None:
        archivo = self._exigir_imagen(archivo_id) if archivo_id else None
        self._ajustes.fijar(CLAVE_LOGO, str(archivo_id) if archivo_id else None)
        self._archivos.limpiar_huerfanos()
        return archivo

    # ------------------------------------------------------------ grupos

    def asegurar_grupos_base(self) -> None:
        """Crea Organizadores, Patrocinadores y Divulgadores la primera vez (y nunca más,
        para respetar lo que el Superadmin borre o renombre)."""
        if self._ajustes.obtener(CLAVE_GRUPOS_BASE):
            return
        if not self._aliados.grupos():
            for orden, titulo in enumerate(GRUPOS_BASE):
                self._aliados.guardar_grupo(GrupoAliados(id=None, titulo=titulo, orden=orden))
        self._ajustes.fijar(CLAVE_GRUPOS_BASE, "1")

    def _grupo(self, grupo_id: int) -> GrupoAliados:
        grupo = self._aliados.grupo_por_id(grupo_id)
        if not grupo:
            raise NoEncontrado("El grupo no existe.")
        return grupo

    def crear_grupo(self, titulo: str) -> GrupoAliados:
        grupo = GrupoAliados(id=None, titulo=titulo, orden=self._aliados.siguiente_orden_grupo())
        validar_grupo_aliados(grupo)
        return self._aliados.guardar_grupo(grupo)

    def renombrar_grupo(self, grupo_id: int, titulo: str) -> GrupoAliados:
        grupo = self._grupo(grupo_id)
        grupo.titulo = titulo
        validar_grupo_aliados(grupo)
        return self._aliados.guardar_grupo(grupo)

    def eliminar_grupo(self, grupo_id: int) -> None:
        self._grupo(grupo_id)
        self._aliados.eliminar_grupo(grupo_id)  # sus aliados caen en cascada
        self._archivos.limpiar_huerfanos()

    def reordenar_grupos(self, ids_en_orden: list[int]) -> None:
        validar_reorden([g.id for g in self._aliados.grupos()], ids_en_orden)
        self._aliados.reordenar_grupos(ids_en_orden)

    # ------------------------------------------------------------ aliados

    def _aliado(self, aliado_id: int) -> Aliado:
        aliado = self._aliados.aliado_por_id(aliado_id)
        if not aliado:
            raise NoEncontrado("El aliado no existe.")
        return aliado

    def crear_aliado(self, grupo_id: int, datos: DatosAliado) -> Aliado:
        self._grupo(grupo_id)
        aliado = Aliado(id=None, grupo_id=grupo_id, nombre=datos.nombre or "", url=datos.url or "",
                        archivo_id=datos.archivo_id, orden=self._aliados.siguiente_orden_aliado(grupo_id))
        validar_aliado(aliado)
        if aliado.archivo_id:
            self._exigir_imagen(aliado.archivo_id)
        return self._aliados.guardar_aliado(aliado)

    def actualizar_aliado(self, aliado_id: int, datos: DatosAliado) -> Aliado:
        aliado = self._aliado(aliado_id)
        if datos.nombre is not None:
            aliado.nombre = datos.nombre
        if datos.url is not None:
            aliado.url = datos.url
        if datos.quitar_logo:
            aliado.archivo_id = None
        elif datos.archivo_id:
            self._exigir_imagen(datos.archivo_id)
            aliado.archivo_id = datos.archivo_id
        validar_aliado(aliado)
        guardado = self._aliados.guardar_aliado(aliado)
        self._archivos.limpiar_huerfanos()
        return guardado

    def eliminar_aliado(self, aliado_id: int) -> None:
        self._aliado(aliado_id)
        self._aliados.eliminar_aliado(aliado_id)
        self._archivos.limpiar_huerfanos()

    def reordenar_aliados(self, grupo_id: int, ids_en_orden: list[int]) -> None:
        self._grupo(grupo_id)
        actuales = [a.id for a in self._aliados.aliados() if a.grupo_id == grupo_id]
        validar_reorden(actuales, ids_en_orden)
        self._aliados.reordenar_aliados(grupo_id, ids_en_orden)
