import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.application.comandos import CrearUsuario  # noqa: E402
from app.configuracion import Configuracion  # noqa: E402
from app.domain.entidades import Rol  # noqa: E402


@pytest.fixture
def app(tmp_path):
    config = Configuracion(
        carpeta_datos=tmp_path, ruta_bd=str(tmp_path / "test.db"),
        carpeta_archivos=str(tmp_path / "archivos"), secret_key="x" * 40,
        servir_frontend=False, metodo_hash="pbkdf2:sha256:1000",  # hash rápido en pruebas
    )
    app = create_app(config)
    c = app.extensions["contenedor"]
    c.usuarios.crear(CrearUsuario(usuario="admin", nombre="Admin", rol=Rol.SUPERADMIN, contrasena="admin-secreta"))
    c.usuarios.crear(CrearUsuario(usuario="ana", nombre="Ana", contrasena="ana-secreta"))
    return app


@pytest.fixture
def cliente(app):
    return app.test_client()


def _token(cliente, usuario, contrasena):
    r = cliente.post("/api/v1/auth/login", json={"usuario": usuario, "contrasena": contrasena})
    assert r.status_code == 200, r.json
    return {"Authorization": f"Bearer {r.json['token']}"}


@pytest.fixture
def admin(cliente):
    return _token(cliente, "admin", "admin-secreta")


@pytest.fixture
def ana(cliente):
    return _token(cliente, "ana", "ana-secreta")
