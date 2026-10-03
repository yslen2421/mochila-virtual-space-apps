"""Almacenamiento de archivos en disco local.

Los archivos se guardan con un nombre aleatorio (nunca el nombre que manda el usuario),
así no hay colisiones ni rutas maliciosas. Para pasar a S3 u otro servicio basta con
otra clase que cumpla el puerto AlmacenArchivos.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import BinaryIO

TAMANO_BLOQUE = 1024 * 1024


class AlmacenLocal:
    def __init__(self, carpeta: str):
        self._carpeta = Path(carpeta).resolve()
        self._carpeta.mkdir(parents=True, exist_ok=True)

    def guardar(self, flujo: BinaryIO, extension: str) -> tuple[str, int]:
        nombre = f"{secrets.token_hex(16)}.{extension}"
        destino = self._carpeta / nombre
        tamano = 0
        with open(destino, "wb") as salida:
            while bloque := flujo.read(TAMANO_BLOQUE):
                salida.write(bloque)
                tamano += len(bloque)
        return nombre, tamano

    def ruta(self, nombre_guardado: str) -> str:
        ruta = (self._carpeta / nombre_guardado).resolve()
        if ruta.parent != self._carpeta:
            raise ValueError("Ruta de archivo no válida")
        return str(ruta)

    def miniatura(self, nombre_guardado: str, lado: int = 720) -> str | None:
        """Versión liviana (WebP) de una imagen para las vistas previas.

        Se genera la primera vez que alguien la pide y queda guardada. Ahorra mucho
        ancho de banda en el wifi de la sede: un wallpaper 4K pesa ~5 MB, su miniatura ~60 KB.
        """
        extension = nombre_guardado.rsplit(".", 1)[-1].lower()
        if extension not in {"png", "jpg", "jpeg", "webp", "gif"}:
            return None
        destino = self._carpeta / "miniaturas" / f"{nombre_guardado}.{lado}.webp"
        if destino.exists():
            return str(destino)
        try:
            from PIL import Image
        except ImportError:
            return None
        destino.parent.mkdir(exist_ok=True)
        temporal = destino.with_suffix(f".{secrets.token_hex(4)}.tmp")
        try:
            with Image.open(self.ruta(nombre_guardado)) as imagen:
                imagen.seek(0)
                imagen = imagen.convert("RGBA" if imagen.mode in ("RGBA", "LA", "P") else "RGB")
                imagen.thumbnail((lado, lado))
                imagen.save(temporal, "WEBP", quality=80)
            os.replace(temporal, destino)  # atómico: dos hilos a la vez no se pisan
        except Exception:
            temporal.unlink(missing_ok=True)
            return None
        return str(destino)

    def eliminar(self, nombre_guardado: str) -> None:
        try:
            os.remove(self.ruta(nombre_guardado))
        except FileNotFoundError:
            pass
        for miniatura in (self._carpeta / "miniaturas").glob(f"{nombre_guardado}.*"):
            miniatura.unlink(missing_ok=True)
