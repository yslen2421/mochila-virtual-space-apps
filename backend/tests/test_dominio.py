"""El dominio se prueba sin servidor, sin base de datos y sin archivos."""
import pytest

from app.domain.entidades import Item, TipoItem
from app.domain.errores import ErrorValidacion
from app.domain.reglas import validar_item, validar_reorden, validar_usuario


def test_usuario_se_normaliza():
    assert validar_usuario("  Ana.Perez ") == "ana.perez"
    with pytest.raises(ErrorValidacion):
        validar_usuario("a b")


def test_enlace_exige_url():
    with pytest.raises(ErrorValidacion):
        validar_item(Item(None, 1, TipoItem.ENLACE, "AWS", url="javascript:alert(1)"))
    validar_item(Item(None, 1, TipoItem.ENLACE, "AWS", url="https://aws.amazon.com"))


def test_evento_valida_horas():
    with pytest.raises(ErrorValidacion):
        validar_item(Item(None, 1, TipoItem.EVENTO, "Cierre", fecha="2026-11-15", hora_inicio="18:00", hora_fin="17:00"))


def test_tipo_sin_archivo_descarta_archivo_id():
    item = Item(None, 1, TipoItem.TEXTO, "Hola", descripcion="texto", archivo_id=9, fecha="2026-01-01")
    validar_item(item)
    assert item.archivo_id is None and item.fecha == ""


def test_reorden_debe_ser_permutacion():
    validar_reorden([1, 2, 3], [3, 1, 2])
    with pytest.raises(ErrorValidacion):
        validar_reorden([1, 2, 3], [1, 1, 2])
