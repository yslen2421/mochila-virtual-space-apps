-- Esquema SQLite del portal. Se aplica al arrancar (idempotente).

CREATE TABLE IF NOT EXISTS usuarios (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario        TEXT    NOT NULL UNIQUE,
    nombre         TEXT    NOT NULL,
    email          TEXT    NOT NULL DEFAULT '',
    rol            TEXT    NOT NULL CHECK (rol IN ('participante', 'superadmin')),
    modalidad      TEXT    NOT NULL DEFAULT 'presencial' CHECK (modalidad IN ('presencial', 'virtual')),
    password_hash  TEXT    NOT NULL,
    activo         INTEGER NOT NULL DEFAULT 1,
    version_token  INTEGER NOT NULL DEFAULT 1,
    creado_en      TEXT    NOT NULL,
    ultimo_login   TEXT
);

CREATE TABLE IF NOT EXISTS secciones (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo       TEXT    NOT NULL,
    descripcion  TEXT    NOT NULL DEFAULT '',
    icono        TEXT    NOT NULL DEFAULT '📦',
    orden        INTEGER NOT NULL DEFAULT 0,
    activa       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS archivos (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_original  TEXT    NOT NULL,
    nombre_guardado  TEXT    NOT NULL UNIQUE,
    tipo_mime        TEXT    NOT NULL,
    tamano_bytes     INTEGER NOT NULL,
    creado_en        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    seccion_id   INTEGER NOT NULL REFERENCES secciones(id) ON DELETE CASCADE,
    tipo         TEXT    NOT NULL CHECK (tipo IN ('texto', 'enlace', 'archivo', 'imagen', 'evento')),
    titulo       TEXT    NOT NULL,
    descripcion  TEXT    NOT NULL DEFAULT '',
    url          TEXT    NOT NULL DEFAULT '',
    archivo_id   INTEGER REFERENCES archivos(id) ON DELETE SET NULL,
    fecha        TEXT    NOT NULL DEFAULT '',
    hora_inicio  TEXT    NOT NULL DEFAULT '',
    hora_fin     TEXT    NOT NULL DEFAULT '',
    lugar        TEXT    NOT NULL DEFAULT '',
    orden        INTEGER NOT NULL DEFAULT 0,
    activo       INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_items_seccion ON items (seccion_id, orden);
CREATE INDEX IF NOT EXISTS ix_items_archivo ON items (archivo_id);

CREATE TABLE IF NOT EXISTS actividad (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo           TEXT    NOT NULL,
    usuario_id     INTEGER NOT NULL,
    referencia_id  INTEGER,
    creado_en      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_actividad_tipo ON actividad (tipo, referencia_id);

CREATE TABLE IF NOT EXISTS intentos_login (
    clave      TEXT NOT NULL,
    creado_en  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_intentos_clave ON intentos_login (clave, creado_en);
