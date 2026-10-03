"""Raíz de composición: el único lugar que conoce las clases concretas.

Aquí se decide "SQLite + disco local + JWT". Para cambiar de base de datos o de
almacenamiento, se cambia una línea aquí; dominio y casos de uso no se tocan.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from .application.archivos import ServicioArchivos
from .application.autenticacion import ServicioAutenticacion
from .application.contenido import ServicioItems, ServicioSecciones
from .application.estadisticas import ServicioEstadisticas
from .application.mochila import ServicioMochila
from .application.usuarios import ServicioUsuarios
from .configuracion import Configuracion
from .infrastructure.almacen import AlmacenLocal
from .infrastructure.seguridad import EmisorJwt, HasherWerkzeug, RelojSistema
from .infrastructure.sqlite import (
    BaseDatos,
    ControlIntentosSqlite,
    RegistroActividadSqlite,
    RepositorioArchivosSqlite,
    RepositorioItemsSqlite,
    RepositorioSeccionesSqlite,
    RepositorioUsuariosSqlite,
)


@dataclass
class Contenedor:
    config: Configuracion
    db: BaseDatos
    auth: ServicioAutenticacion
    mochila: ServicioMochila
    secciones: ServicioSecciones
    items: ServicioItems
    archivos: ServicioArchivos
    usuarios: ServicioUsuarios
    estadisticas: ServicioEstadisticas


def construir(config: Configuracion) -> Contenedor:
    db = BaseDatos(config.ruta_bd)
    repo_usuarios = RepositorioUsuariosSqlite(db)
    repo_secciones = RepositorioSeccionesSqlite(db)
    repo_items = RepositorioItemsSqlite(db)
    repo_archivos = RepositorioArchivosSqlite(db)
    actividad = RegistroActividadSqlite(db, config.zona_horaria)
    hasher = HasherWerkzeug(config.metodo_hash)
    tokens = EmisorJwt(config.secret_key, timedelta(hours=config.horas_token))

    archivos = ServicioArchivos(repo_archivos, AlmacenLocal(config.carpeta_archivos), repo_items, actividad)
    return Contenedor(
        config=config,
        db=db,
        auth=ServicioAutenticacion(repo_usuarios, hasher, tokens, ControlIntentosSqlite(db), actividad, RelojSistema()),
        mochila=ServicioMochila(repo_secciones, repo_items, repo_archivos, actividad),
        secciones=ServicioSecciones(repo_secciones, repo_items, archivos),
        items=ServicioItems(repo_secciones, repo_items, repo_archivos, archivos),
        archivos=archivos,
        usuarios=ServicioUsuarios(repo_usuarios, hasher),
        estadisticas=ServicioEstadisticas(repo_usuarios, actividad),
    )
