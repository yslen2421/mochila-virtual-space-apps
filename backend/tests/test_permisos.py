"""Un participante no tiene acceso al panel de organización por ningún camino."""
import re


def _rutas_admin(app):
    """Todas las rutas /api/v1/admin/... con cada método, rellenando los {id} con 1."""
    for regla in app.url_map.iter_rules():
        if not regla.rule.startswith("/api/v1/admin"):
            continue
        ruta = re.sub(r"<[^>]+>", "1", regla.rule)
        for metodo in sorted(regla.methods - {"HEAD", "OPTIONS"}):
            yield metodo, ruta


def test_participante_recibe_403_en_todas_las_rutas_del_panel(app, cliente, ana):
    rutas = list(_rutas_admin(app))
    assert len(rutas) > 25  # que de verdad estemos recorriendo todo el panel
    for metodo, ruta in rutas:
        r = cliente.open(ruta, method=metodo, headers=ana, json={})
        assert r.status_code == 403, f"{metodo} {ruta} respondió {r.status_code} a un participante"


def test_sin_sesion_recibe_401_en_todas_las_rutas_del_panel(app, cliente):
    for metodo, ruta in _rutas_admin(app):
        r = cliente.open(ruta, method=metodo, json={})
        assert r.status_code == 401, f"{metodo} {ruta} respondió {r.status_code} sin sesión"


def test_ingreso_del_panel_rechaza_participantes(cliente):
    r = cliente.post("/api/v1/auth/login-panel", json={"usuario": "ana", "contrasena": "ana-secreta"})
    assert r.status_code == 403
    assert "token" not in r.json
    assert r.json["error"]["mensaje"] == "Esta cuenta no tiene acceso al panel de organización."


def test_ingreso_del_panel_acepta_superadmin(cliente):
    r = cliente.post("/api/v1/auth/login-panel", json={"usuario": "admin", "contrasena": "admin-secreta"})
    assert r.status_code == 200 and r.json["usuario"]["rol"] == "superadmin"


def test_ingreso_del_panel_con_clave_mala_no_revela_el_rol(cliente):
    r = cliente.post("/api/v1/auth/login-panel", json={"usuario": "ana", "contrasena": "mala"})
    assert r.status_code == 401 and r.json["error"]["mensaje"] == "Usuario o contraseña incorrectos."


def test_superadmin_si_puede_ver_el_portal_de_participantes(cliente, admin):
    assert cliente.get("/api/v1/mochila", headers=admin).status_code == 200
