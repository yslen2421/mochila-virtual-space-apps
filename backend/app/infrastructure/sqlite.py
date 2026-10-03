"""Persistencia en SQLite: implementación de los puertos del dominio.

Notas para soportar 150+ usuarios concurrentes:
- Modo WAL: las lecturas (la inmensa mayoría del tráfico) nunca bloquean a la escritura.
- Una conexión por hilo (thread-local), reutilizada entre peticiones.
- busy_timeout: si dos escrituras coinciden, la segunda espera en vez de fallar.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..domain.entidades import Aliado, Archivo, Categoria, GrupoAliados, Item, Modalidad, Rol, Seccion, TipoItem, Usuario

ESQUEMA = Path(__file__).with_name("esquema.sql")


def _ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _a_fecha(valor: str | None) -> datetime | None:
    return datetime.fromisoformat(valor) if valor else None


class BaseDatos:
    def __init__(self, ruta: str):
        self.ruta = ruta
        self._local = threading.local()
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        # executescript maneja su propia transacción
        self.conexion().executescript(ESQUEMA.read_text(encoding="utf-8"))
        self._migrar()

    # Columnas agregadas después de la primera versión. Las bases que ya existen
    # (con participantes y contenido cargados) las reciben al arrancar, sin perder nada.
    MIGRACIONES = {
        "usuarios": {
            "categoria": "TEXT CHECK (categoria IN ('universidad', 'bachillerato'))",
            "equipo": "TEXT NOT NULL DEFAULT ''",
        },
    }

    def _migrar(self) -> None:
        conn = self.conexion()
        for tabla, columnas in self.MIGRACIONES.items():
            existentes = {f["name"] for f in conn.execute(f"PRAGMA table_info({tabla})")}
            for columna, definicion in columnas.items():
                if columna not in existentes:
                    conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")

    def conexion(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.ruta, timeout=10, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=10000")
            self._local.conn = conn
        return conn

    @contextmanager
    def transaccion(self):
        conn = self.conexion()
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise

    def consultar(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        return self.conexion().execute(sql, params).fetchall()

    def uno(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        return self.conexion().execute(sql, params).fetchone()


def _marcadores(n: int) -> str:
    return ",".join("?" * n)


# ---------------------------------------------------------------- usuarios

class RepositorioUsuariosSqlite:
    def __init__(self, db: BaseDatos):
        self._db = db

    @staticmethod
    def _a_entidad(f: sqlite3.Row) -> Usuario:
        return Usuario(
            id=f["id"], usuario=f["usuario"], nombre=f["nombre"], email=f["email"],
            rol=Rol(f["rol"]), modalidad=Modalidad(f["modalidad"]),
            categoria=Categoria(f["categoria"]) if f["categoria"] else None, equipo=f["equipo"] or "",
            password_hash=f["password_hash"], activo=bool(f["activo"]),
            version_token=f["version_token"], creado_en=_a_fecha(f["creado_en"]),
            ultimo_login=_a_fecha(f["ultimo_login"]),
        )

    def por_id(self, usuario_id: int) -> Usuario | None:
        f = self._db.uno("SELECT * FROM usuarios WHERE id = ?", (usuario_id,))
        return self._a_entidad(f) if f else None

    def por_usuario(self, usuario: str) -> Usuario | None:
        f = self._db.uno("SELECT * FROM usuarios WHERE usuario = ?", (usuario,))
        return self._a_entidad(f) if f else None

    def listar(self) -> list[Usuario]:
        return [self._a_entidad(f) for f in self._db.consultar(
            "SELECT * FROM usuarios ORDER BY rol DESC, nombre COLLATE NOCASE")]

    def _guardar_en(self, c: sqlite3.Connection, u: Usuario) -> Usuario:
        valores = (u.usuario, u.nombre, u.email, u.rol.value, u.modalidad.value,
                   u.categoria.value if u.categoria else None, u.equipo,
                   u.password_hash, int(u.activo), u.version_token)
        if u.id is None:
            cur = c.execute(
                """INSERT INTO usuarios (usuario, nombre, email, rol, modalidad, categoria, equipo,
                   password_hash, activo, version_token, creado_en) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (*valores, _ahora_iso()),
            )
            u.id = cur.lastrowid
        else:
            c.execute(
                """UPDATE usuarios SET usuario=?, nombre=?, email=?, rol=?, modalidad=?, categoria=?,
                   equipo=?, password_hash=?, activo=?, version_token=? WHERE id=?""",
                (*valores, u.id),
            )
        return u

    def guardar(self, usuario: Usuario) -> Usuario:
        with self._db.transaccion() as c:
            self._guardar_en(c, usuario)
        return self.por_id(usuario.id)

    def guardar_varios(self, usuarios: list[Usuario]) -> list[Usuario]:
        with self._db.transaccion() as c:
            for u in usuarios:
                self._guardar_en(c, u)
        return [self.por_id(u.id) for u in usuarios]

    def eliminar(self, usuario_id: int) -> None:
        with self._db.transaccion() as c:
            c.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))

    def registrar_login(self, usuario_id: int, momento: datetime) -> None:
        with self._db.transaccion() as c:
            c.execute("UPDATE usuarios SET ultimo_login = ? WHERE id = ?",
                      (momento.isoformat(timespec="seconds"), usuario_id))


# ---------------------------------------------------------------- secciones

class RepositorioSeccionesSqlite:
    def __init__(self, db: BaseDatos):
        self._db = db

    @staticmethod
    def _a_entidad(f: sqlite3.Row) -> Seccion:
        return Seccion(id=f["id"], titulo=f["titulo"], descripcion=f["descripcion"],
                       icono=f["icono"], orden=f["orden"], activa=bool(f["activa"]))

    def por_id(self, seccion_id: int) -> Seccion | None:
        f = self._db.uno("SELECT * FROM secciones WHERE id = ?", (seccion_id,))
        return self._a_entidad(f) if f else None

    def listar(self, solo_activas: bool = False) -> list[Seccion]:
        filtro = "WHERE activa = 1" if solo_activas else ""
        return [self._a_entidad(f) for f in self._db.consultar(
            f"SELECT * FROM secciones {filtro} ORDER BY orden, id")]

    def guardar(self, s: Seccion) -> Seccion:
        with self._db.transaccion() as c:
            if s.id is None:
                cur = c.execute(
                    "INSERT INTO secciones (titulo, descripcion, icono, orden, activa) VALUES (?,?,?,?,?)",
                    (s.titulo, s.descripcion, s.icono, s.orden, int(s.activa)))
                s.id = cur.lastrowid
            else:
                c.execute(
                    "UPDATE secciones SET titulo=?, descripcion=?, icono=?, orden=?, activa=? WHERE id=?",
                    (s.titulo, s.descripcion, s.icono, s.orden, int(s.activa), s.id))
        return self.por_id(s.id)

    def eliminar(self, seccion_id: int) -> None:
        with self._db.transaccion() as c:
            c.execute("DELETE FROM secciones WHERE id = ?", (seccion_id,))

    def reordenar(self, ids_en_orden: list[int]) -> None:
        with self._db.transaccion() as c:
            c.executemany("UPDATE secciones SET orden = ? WHERE id = ?",
                          [(pos, sid) for pos, sid in enumerate(ids_en_orden)])

    def siguiente_orden(self) -> int:
        return self._db.uno("SELECT COALESCE(MAX(orden), -1) + 1 AS n FROM secciones")["n"]


# ---------------------------------------------------------------- ítems

class RepositorioItemsSqlite:
    def __init__(self, db: BaseDatos):
        self._db = db

    @staticmethod
    def _a_entidad(f: sqlite3.Row) -> Item:
        return Item(
            id=f["id"], seccion_id=f["seccion_id"], tipo=TipoItem(f["tipo"]), titulo=f["titulo"],
            descripcion=f["descripcion"], url=f["url"], archivo_id=f["archivo_id"],
            fecha=f["fecha"], hora_inicio=f["hora_inicio"], hora_fin=f["hora_fin"],
            lugar=f["lugar"], orden=f["orden"], activo=bool(f["activo"]),
        )

    # Los eventos del cronograma se ordenan por fecha y hora; el resto, por el orden manual.
    _ORDEN = "ORDER BY CASE WHEN tipo='evento' THEN fecha || ' ' || hora_inicio ELSE '' END, orden, id"

    def por_id(self, item_id: int) -> Item | None:
        f = self._db.uno("SELECT * FROM items WHERE id = ?", (item_id,))
        return self._a_entidad(f) if f else None

    def de_seccion(self, seccion_id: int, solo_activos: bool = False) -> list[Item]:
        return self.de_secciones([seccion_id], solo_activos)

    def de_secciones(self, seccion_ids: list[int], solo_activos: bool = False) -> list[Item]:
        if not seccion_ids:
            return []
        filtro = "AND activo = 1" if solo_activos else ""
        return [self._a_entidad(f) for f in self._db.consultar(
            f"SELECT * FROM items WHERE seccion_id IN ({_marcadores(len(seccion_ids))}) {filtro} {self._ORDEN}",
            seccion_ids)]

    def guardar(self, i: Item) -> Item:
        valores = (i.seccion_id, i.tipo.value, i.titulo, i.descripcion, i.url, i.archivo_id,
                   i.fecha, i.hora_inicio, i.hora_fin, i.lugar, i.orden, int(i.activo))
        with self._db.transaccion() as c:
            if i.id is None:
                cur = c.execute(
                    """INSERT INTO items (seccion_id, tipo, titulo, descripcion, url, archivo_id,
                       fecha, hora_inicio, hora_fin, lugar, orden, activo)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", valores)
                i.id = cur.lastrowid
            else:
                c.execute(
                    """UPDATE items SET seccion_id=?, tipo=?, titulo=?, descripcion=?, url=?, archivo_id=?,
                       fecha=?, hora_inicio=?, hora_fin=?, lugar=?, orden=?, activo=? WHERE id=?""",
                    (*valores, i.id))
        return self.por_id(i.id)

    def eliminar(self, item_id: int) -> None:
        with self._db.transaccion() as c:
            c.execute("DELETE FROM items WHERE id = ?", (item_id,))

    def reordenar(self, seccion_id: int, ids_en_orden: list[int]) -> None:
        with self._db.transaccion() as c:
            c.executemany("UPDATE items SET orden = ? WHERE id = ? AND seccion_id = ?",
                          [(pos, iid, seccion_id) for pos, iid in enumerate(ids_en_orden)])

    def siguiente_orden(self, seccion_id: int) -> int:
        return self._db.uno("SELECT COALESCE(MAX(orden), -1) + 1 AS n FROM items WHERE seccion_id = ?",
                            (seccion_id,))["n"]

    def archivo_visible_para_participantes(self, archivo_id: int) -> bool:
        return self._db.uno(
            """SELECT 1 FROM items i JOIN secciones s ON s.id = i.seccion_id
               WHERE i.archivo_id = ? AND i.activo = 1 AND s.activa = 1 LIMIT 1""",
            (archivo_id,)) is not None


# ---------------------------------------------------------------- archivos

class RepositorioArchivosSqlite:
    def __init__(self, db: BaseDatos, gracia_huerfanos: timedelta = timedelta(hours=24)):
        self._db = db
        self._gracia = gracia_huerfanos

    @staticmethod
    def _a_entidad(f: sqlite3.Row) -> Archivo:
        return Archivo(id=f["id"], nombre_original=f["nombre_original"], nombre_guardado=f["nombre_guardado"],
                       tipo_mime=f["tipo_mime"], tamano_bytes=f["tamano_bytes"], creado_en=_a_fecha(f["creado_en"]))

    def por_id(self, archivo_id: int) -> Archivo | None:
        f = self._db.uno("SELECT * FROM archivos WHERE id = ?", (archivo_id,))
        return self._a_entidad(f) if f else None

    def por_ids(self, ids: list[int]) -> dict[int, Archivo]:
        if not ids:
            return {}
        filas = self._db.consultar(f"SELECT * FROM archivos WHERE id IN ({_marcadores(len(ids))})", ids)
        return {f["id"]: self._a_entidad(f) for f in filas}

    def guardar(self, a: Archivo) -> Archivo:
        with self._db.transaccion() as c:
            cur = c.execute(
                """INSERT INTO archivos (nombre_original, nombre_guardado, tipo_mime, tamano_bytes, creado_en)
                   VALUES (?,?,?,?,?)""",
                (a.nombre_original, a.nombre_guardado, a.tipo_mime, a.tamano_bytes, _ahora_iso()))
            a.id = cur.lastrowid
        return self.por_id(a.id)

    def eliminar(self, archivo_id: int) -> None:
        with self._db.transaccion() as c:
            c.execute("DELETE FROM archivos WHERE id = ?", (archivo_id,))

    def huerfanos(self) -> list[Archivo]:
        limite = (datetime.now(timezone.utc) - self._gracia).isoformat(timespec="seconds")
        # Un archivo está en uso si lo usa un ítem, un aliado o es el logo del evento.
        return [self._a_entidad(f) for f in self._db.consultar(
            """SELECT a.* FROM archivos a
               WHERE a.creado_en < ?
                 AND NOT EXISTS (SELECT 1 FROM items i WHERE i.archivo_id = a.id)
                 AND NOT EXISTS (SELECT 1 FROM aliados al WHERE al.archivo_id = a.id)
                 AND NOT EXISTS (SELECT 1 FROM ajustes aj
                                 WHERE aj.clave = 'logo_archivo_id' AND aj.valor = CAST(a.id AS TEXT))""",
            (limite,))]


# ---------------------------------------------------------------- identidad del evento

class RepositorioAjustesSqlite:
    def __init__(self, db: BaseDatos):
        self._db = db

    def obtener(self, clave: str) -> str | None:
        f = self._db.uno("SELECT valor FROM ajustes WHERE clave = ?", (clave,))
        return f["valor"] if f else None

    def fijar(self, clave: str, valor: str | None) -> None:
        with self._db.transaccion() as c:
            if valor is None:
                c.execute("DELETE FROM ajustes WHERE clave = ?", (clave,))
            else:
                c.execute("INSERT INTO ajustes (clave, valor) VALUES (?, ?) "
                          "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor", (clave, valor))


class RepositorioAliadosSqlite:
    def __init__(self, db: BaseDatos):
        self._db = db

    @staticmethod
    def _grupo(f: sqlite3.Row) -> GrupoAliados:
        return GrupoAliados(id=f["id"], titulo=f["titulo"], orden=f["orden"])

    @staticmethod
    def _aliado(f: sqlite3.Row) -> Aliado:
        return Aliado(id=f["id"], grupo_id=f["grupo_id"], nombre=f["nombre"], url=f["url"],
                      archivo_id=f["archivo_id"], orden=f["orden"])

    def grupos(self) -> list[GrupoAliados]:
        return [self._grupo(f) for f in self._db.consultar("SELECT * FROM grupos_aliados ORDER BY orden, id")]

    def grupo_por_id(self, grupo_id: int) -> GrupoAliados | None:
        f = self._db.uno("SELECT * FROM grupos_aliados WHERE id = ?", (grupo_id,))
        return self._grupo(f) if f else None

    def guardar_grupo(self, g: GrupoAliados) -> GrupoAliados:
        with self._db.transaccion() as c:
            if g.id is None:
                g.id = c.execute("INSERT INTO grupos_aliados (titulo, orden) VALUES (?, ?)",
                                 (g.titulo, g.orden)).lastrowid
            else:
                c.execute("UPDATE grupos_aliados SET titulo = ?, orden = ? WHERE id = ?", (g.titulo, g.orden, g.id))
        return self.grupo_por_id(g.id)

    def eliminar_grupo(self, grupo_id: int) -> None:
        with self._db.transaccion() as c:
            c.execute("DELETE FROM grupos_aliados WHERE id = ?", (grupo_id,))

    def reordenar_grupos(self, ids_en_orden: list[int]) -> None:
        with self._db.transaccion() as c:
            c.executemany("UPDATE grupos_aliados SET orden = ? WHERE id = ?",
                          [(pos, gid) for pos, gid in enumerate(ids_en_orden)])

    def siguiente_orden_grupo(self) -> int:
        return self._db.uno("SELECT COALESCE(MAX(orden), -1) + 1 AS n FROM grupos_aliados")["n"]

    def aliados(self) -> list[Aliado]:
        return [self._aliado(f) for f in self._db.consultar("SELECT * FROM aliados ORDER BY grupo_id, orden, id")]

    def aliado_por_id(self, aliado_id: int) -> Aliado | None:
        f = self._db.uno("SELECT * FROM aliados WHERE id = ?", (aliado_id,))
        return self._aliado(f) if f else None

    def guardar_aliado(self, a: Aliado) -> Aliado:
        valores = (a.grupo_id, a.nombre, a.url, a.archivo_id, a.orden)
        with self._db.transaccion() as c:
            if a.id is None:
                a.id = c.execute("INSERT INTO aliados (grupo_id, nombre, url, archivo_id, orden) VALUES (?,?,?,?,?)",
                                 valores).lastrowid
            else:
                c.execute("UPDATE aliados SET grupo_id=?, nombre=?, url=?, archivo_id=?, orden=? WHERE id=?",
                          (*valores, a.id))
        return self.aliado_por_id(a.id)

    def eliminar_aliado(self, aliado_id: int) -> None:
        with self._db.transaccion() as c:
            c.execute("DELETE FROM aliados WHERE id = ?", (aliado_id,))

    def reordenar_aliados(self, grupo_id: int, ids_en_orden: list[int]) -> None:
        with self._db.transaccion() as c:
            c.executemany("UPDATE aliados SET orden = ? WHERE id = ? AND grupo_id = ?",
                          [(pos, aid, grupo_id) for pos, aid in enumerate(ids_en_orden)])

    def siguiente_orden_aliado(self, grupo_id: int) -> int:
        return self._db.uno("SELECT COALESCE(MAX(orden), -1) + 1 AS n FROM aliados WHERE grupo_id = ?",
                            (grupo_id,))["n"]


# ---------------------------------------------------------------- actividad e intentos

class RegistroActividadSqlite:
    def __init__(self, db: BaseDatos, zona_horaria: str = "America/Bogota"):
        self._db = db
        self._zona = zona_horaria

    def _desfase(self) -> str:
        """Desfase de la zona local en minutos, para agrupar por día local y no por día UTC."""
        from zoneinfo import ZoneInfo
        minutos = int(datetime.now(ZoneInfo(self._zona)).utcoffset().total_seconds() // 60)
        return f"{minutos:+d} minutes"

    def registrar(self, tipo: str, usuario_id: int, referencia_id: int | None = None) -> None:
        with self._db.transaccion() as c:
            c.execute("INSERT INTO actividad (tipo, usuario_id, referencia_id, creado_en) VALUES (?,?,?,?)",
                      (tipo, usuario_id, referencia_id, _ahora_iso()))

    def resumen(self) -> dict:
        logins = self._db.uno(
            "SELECT COUNT(*) AS total, COUNT(DISTINCT usuario_id) AS unicos FROM actividad WHERE tipo='login'")
        por_dia = self._db.consultar(
            """SELECT date(creado_en, ?) AS dia, COUNT(*) AS n FROM actividad
               WHERE tipo='login' GROUP BY dia ORDER BY dia DESC LIMIT 14""", (self._desfase(),))
        secciones = self._db.consultar(
            """SELECT s.id, s.icono, s.titulo, COUNT(a.id) AS vistas, COUNT(DISTINCT a.usuario_id) AS personas
               FROM secciones s LEFT JOIN actividad a ON a.tipo='vista_seccion' AND a.referencia_id = s.id
               GROUP BY s.id ORDER BY vistas DESC, s.orden""")
        descargas = self._db.consultar(
            """SELECT ar.id, ar.nombre_original AS nombre, COUNT(a.id) AS descargas,
                      COUNT(DISTINCT a.usuario_id) AS personas
               FROM actividad a JOIN archivos ar ON ar.id = a.referencia_id
               WHERE a.tipo='descarga' GROUP BY ar.id ORDER BY descargas DESC LIMIT 15""")
        return {
            "logins": {"total": logins["total"], "usuarios_unicos": logins["unicos"],
                       "por_dia": [dict(f) for f in reversed(por_dia)]},
            "secciones": [dict(f) for f in secciones],
            "descargas": [dict(f) for f in descargas],
        }


class ControlIntentosSqlite:
    def __init__(self, db: BaseDatos):
        self._db = db

    def fallos_recientes(self, clave: str, ventana_segundos: int) -> int:
        return self._db.uno("SELECT COUNT(*) AS n FROM intentos_login WHERE clave = ? AND creado_en > ?",
                            (clave, time.time() - ventana_segundos))["n"]

    def registrar_fallo(self, clave: str) -> None:
        with self._db.transaccion() as c:
            c.execute("INSERT INTO intentos_login (clave, creado_en) VALUES (?, ?)", (clave, time.time()))
            # Mantenimiento: borrar intentos de hace más de un día.
            c.execute("DELETE FROM intentos_login WHERE creado_en < ?", (time.time() - 86400,))

    def limpiar(self, clave: str) -> None:
        with self._db.transaccion() as c:
            c.execute("DELETE FROM intentos_login WHERE clave = ?", (clave,))
