"""Datos de cada persona: nombre, categoría, usuario, rol y equipo."""
import sqlite3

from app import create_app
from app.configuracion import Configuracion


def _usuarios(cliente, admin):
    return {u["usuario"]: u for u in cliente.get("/api/v1/admin/usuarios", headers=admin).json["usuarios"]}


def test_crear_participante_con_todos_los_datos(cliente, admin):
    r = cliente.post("/api/v1/admin/usuarios", headers=admin, json={
        "nombre": "Mateo Álvarez", "usuario": "mateo.alvarez", "categoria": "bachillerato",
        "rol": "participante", "equipo": "  Los   Cometas "})
    assert r.status_code == 201, r.json
    u = r.json["usuario"]
    assert (u["categoria"], u["equipo"], u["rol"]) == ("bachillerato", "Los Cometas", "participante")


def test_participante_sin_categoria_no_se_crea(cliente, admin):
    r = cliente.post("/api/v1/admin/usuarios", headers=admin, json={"nombre": "Sin Cat", "usuario": "sin.cat"})
    assert r.status_code == 400 and r.json["error"]["detalle"] == {"campo": "categoria"}
    r = cliente.post("/api/v1/admin/usuarios", headers=admin, json={
        "nombre": "X", "usuario": "x.y", "categoria": "primaria"})
    assert r.status_code == 400


def test_superadmin_no_necesita_categoria(cliente, admin):
    r = cliente.post("/api/v1/admin/usuarios", headers=admin, json={
        "nombre": "Coordinadora", "usuario": "coord", "rol": "superadmin"})
    assert r.status_code == 201 and r.json["usuario"]["categoria"] is None


def test_importar_con_categoria_rol_y_equipo(cliente, admin):
    r = cliente.post("/api/v1/admin/usuarios/importar", headers=admin, json={"usuarios": [
        {"nombre": "Ana Ríos", "usuario": "ana.rios", "categoria": "universidad", "equipo": "Órbita"},
        {"nombre": "Juan Gil", "usuario": "juan.gil", "categoria": "bachillerato", "equipo": "Órbita"},
        {"nombre": "Mentora", "usuario": "mentora", "rol": "superadmin"},
    ]})
    assert r.status_code == 201, r.json
    u = _usuarios(cliente, admin)
    assert u["ana.rios"]["equipo"] == "Órbita" and u["juan.gil"]["categoria"] == "bachillerato"
    assert u["mentora"]["rol"] == "superadmin"


def test_importar_sin_categoria_no_crea_a_nadie(cliente, admin):
    r = cliente.post("/api/v1/admin/usuarios/importar", headers=admin, json={"usuarios": [
        {"nombre": "Bien", "usuario": "bien", "categoria": "universidad"},
        {"nombre": "Mal", "usuario": "mal"}]})
    assert r.status_code == 400
    assert r.json["error"]["detalle"][0]["fila"] == 2
    assert "bien" not in _usuarios(cliente, admin)


def test_editar_categoria_equipo_y_rol(cliente, admin, ana):
    ana_id = _usuarios(cliente, admin)["ana"]["id"]
    r = cliente.put(f"/api/v1/admin/usuarios/{ana_id}", headers=admin,
                    json={"categoria": "bachillerato", "equipo": "Nebulosa"})
    assert (r.json["usuario"]["categoria"], r.json["usuario"]["equipo"]) == ("bachillerato", "Nebulosa")
    # Darle permisos de Superadmin cierra su sesión de participante
    r = cliente.put(f"/api/v1/admin/usuarios/{ana_id}", headers=admin, json={"rol": "superadmin"})
    assert r.json["usuario"]["rol"] == "superadmin"
    assert cliente.get("/api/v1/mochila", headers=ana).status_code == 401


def test_no_se_puede_quitar_el_ultimo_superadmin(cliente, admin):
    admin_id = _usuarios(cliente, admin)["admin"]["id"]
    r = cliente.put(f"/api/v1/admin/usuarios/{admin_id}", headers=admin, json={"rol": "participante"})
    assert r.status_code == 400  # ni a sí mismo ni al último


def test_estadisticas_por_categoria_y_equipos(cliente, admin):
    cliente.post("/api/v1/admin/usuarios/importar", headers=admin, json={"usuarios": [
        {"nombre": "A", "usuario": "aaa", "categoria": "bachillerato", "equipo": "los cometas"},
        {"nombre": "B", "usuario": "bbb", "categoria": "bachillerato"}]})
    p = cliente.get("/api/v1/admin/estadisticas", headers=admin).json["participantes"]
    assert p["por_categoria"] == {"universidad": 1, "bachillerato": 2}
    assert p["equipos"] == 1      # "Los Cometas" y "los cometas" son el mismo equipo
    assert p["sin_equipo"] == 1


def test_base_de_datos_vieja_recibe_las_columnas_nuevas(tmp_path):
    """Una base creada antes de este cambio (como la de un computador ya en uso) se actualiza sola."""
    ruta = tmp_path / "vieja.db"
    with sqlite3.connect(ruta) as c:
        c.executescript("""
            CREATE TABLE usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL UNIQUE,
              nombre TEXT NOT NULL, email TEXT NOT NULL DEFAULT '', rol TEXT NOT NULL,
              modalidad TEXT NOT NULL DEFAULT 'presencial', password_hash TEXT NOT NULL,
              activo INTEGER NOT NULL DEFAULT 1, version_token INTEGER NOT NULL DEFAULT 1,
              creado_en TEXT NOT NULL, ultimo_login TEXT);
            INSERT INTO usuarios (usuario, nombre, rol, password_hash, creado_en)
              VALUES ('vieja', 'Cuenta vieja', 'participante', 'x', '2026-10-01T00:00:00+00:00');""")
    app = create_app(Configuracion(carpeta_datos=tmp_path, ruta_bd=str(ruta), carpeta_archivos=str(tmp_path / "a"),
                                   secret_key="x" * 40, servir_frontend=False))
    u = app.extensions["contenedor"].usuarios.listar()[0]
    assert (u.usuario, u.categoria, u.equipo) == ("vieja", None, "")
