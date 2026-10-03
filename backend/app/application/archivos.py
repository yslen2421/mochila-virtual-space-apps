"""Casos de uso de archivos: subir (Superadmin) y descargar (cualquier usuario autenticado)."""
from __future__ import annotations

import mimetypes
from typing import BinaryIO

from ..domain.entidades import Archivo, Usuario
from ..domain.errores import ErrorValidacion, NoEncontrado
from ..domain.puertos import AlmacenArchivos, RegistroActividad, RepositorioArchivos, RepositorioItems

EXTENSIONES_PERMITIDAS = {
    # documentos
    "pdf", "txt", "md", "csv", "docx", "pptx", "xlsx", "ics",
    # imágenes
    "png", "jpg", "jpeg", "webp", "gif", "svg",
    # paquetes y multimedia
    "zip", "mp4", "mp3",
    # tipografías (branding)
    "ttf", "otf", "woff", "woff2",
}

mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("text/markdown", ".md")
mimetypes.add_type("text/calendar", ".ics")
mimetypes.add_type("font/woff2", ".woff2")


class ServicioArchivos:
    def __init__(
        self,
        repo: RepositorioArchivos,
        almacen: AlmacenArchivos,
        items: RepositorioItems,
        actividad: RegistroActividad,
    ):
        self._repo = repo
        self._almacen = almacen
        self._items = items
        self._actividad = actividad

    def subir(self, nombre_original: str, flujo: BinaryIO) -> Archivo:
        nombre_original = (nombre_original or "").strip().replace("\\", "/").split("/")[-1][:200]
        extension = nombre_original.rsplit(".", 1)[-1].lower() if "." in nombre_original else ""
        if extension not in EXTENSIONES_PERMITIDAS:
            raise ErrorValidacion(
                "Tipo de archivo no permitido.",
                {"permitidos": sorted(EXTENSIONES_PERMITIDAS)},
            )
        nombre_guardado, tamano = self._almacen.guardar(flujo, extension)
        if tamano == 0:
            self._almacen.eliminar(nombre_guardado)
            raise ErrorValidacion("El archivo está vacío.")
        # El tipo MIME se decide por la extensión, nunca por lo que diga el navegador.
        tipo_mime = mimetypes.guess_type(f"x.{extension}")[0] or "application/octet-stream"
        return self._repo.guardar(
            Archivo(id=None, nombre_original=nombre_original, nombre_guardado=nombre_guardado,
                    tipo_mime=tipo_mime, tamano_bytes=tamano)
        )

    def para_descarga(
        self, usuario: Usuario, archivo_id: int, registrar: bool = True, miniatura: bool = False
    ) -> tuple[Archivo, str, bool]:
        """Devuelve (archivo, ruta en disco, es_miniatura)."""
        archivo = self._repo.por_id(archivo_id)
        visible = archivo and (usuario.es_superadmin or self._items.archivo_visible_para_participantes(archivo_id))
        if not visible:
            raise NoEncontrado("El archivo no existe o no está disponible.")
        if miniatura:
            ruta = self._almacen.miniatura(archivo.nombre_guardado)
            if ruta:
                return archivo, ruta, True
        if registrar and not usuario.es_superadmin:
            self._actividad.registrar("descarga", usuario.id, archivo_id)
        return archivo, self._almacen.ruta(archivo.nombre_guardado), False

    def ruta_publica(self, archivo_id: int, miniatura: bool) -> tuple[Archivo, str, bool]:
        """Ruta de un archivo ya autorizado como público (logos). Devuelve (archivo, ruta, es_miniatura)."""
        archivo = self._repo.por_id(archivo_id)
        if not archivo:
            raise NoEncontrado("El archivo no existe.")
        if miniatura:
            ruta = self._almacen.miniatura(archivo.nombre_guardado)
            if ruta:
                return archivo, ruta, True
        return archivo, self._almacen.ruta(archivo.nombre_guardado), False

    def limpiar_huerfanos(self) -> int:
        """Borra archivos que ya no usa ningún ítem, aliado ni el logo (y con más de un día subidos)."""
        huerfanos = self._repo.huerfanos()
        for archivo in huerfanos:
            self._almacen.eliminar(archivo.nombre_guardado)
            self._repo.eliminar(archivo.id)
        return len(huerfanos)
