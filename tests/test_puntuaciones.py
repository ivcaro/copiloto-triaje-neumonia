# -*- coding: utf-8 -*-
"""La cache de pruebas/puntuaciones.py se invalida cuando el modelo cambia.

Punto 5 del informe de arreglos finales de sp3-bot-n8n: antes,
`puntuaciones_de_prueba()` cacheaba en `crudas_prueba.csv` sin mirar los
pesos del modelo, asi que un reentrenamiento la dejaba sirviendo, en
silencio, las puntuaciones del modelo viejo -- y `caracterizar_conjunto.py`
(los numeros del §3 del spec) habria seguido reportando el modelo anterior
sin que nada lo avisara.

Estas pruebas NO vuelven a inferir sobre las 3 811 imagenes de prueba (eso
tarda minutos y ya lo ejercitan `test_seleccion_casos.py` y
`test_contrato_mcp.py` contra el modelo real): aislan la logica de
invalidacion con ficheros pequenos de mentira, monkeypencheando las rutas
del modulo, y verifican tanto el helper `_sha256` como el camino rapido de
`puntuaciones_de_prueba()` cuando la cache SI es valida.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from pruebas import puntuaciones  # noqa: E402


@pytest.fixture
def entorno_aislado(tmp_path, monkeypatch):
    """Pesos, cache y hash de prueba, sin tocar los ficheros reales del repo."""
    pesos = tmp_path / "pesos_modelo_cpu.pt"
    pesos.write_bytes(b"pesos de mentira, version 1")
    cache = tmp_path / "crudas_prueba.csv"
    cache_hash = tmp_path / "crudas_prueba.sha256"
    monkeypatch.setattr(puntuaciones, "PESOS", pesos)
    monkeypatch.setattr(puntuaciones, "CACHE", cache)
    monkeypatch.setattr(puntuaciones, "CACHE_HASH", cache_hash)
    return pesos, cache, cache_hash


def test_sha256_es_determinista_y_depende_del_contenido(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"igual")
    b.write_bytes(b"igual")
    assert puntuaciones._sha256(a) == puntuaciones._sha256(b)
    b.write_bytes(b"distinto")
    assert puntuaciones._sha256(a) != puntuaciones._sha256(b)


def test_cache_invalida_sin_fichero_hash(entorno_aislado):
    """Cache presente pero sin su .sha256: no hay forma de saber contra que
    modelo se genero, asi que no es de fiar."""
    _, cache, cache_hash = entorno_aislado
    cache.write_text("patientId,cruda\n1,0.5\n", encoding="utf-8")
    assert not cache_hash.exists()
    assert puntuaciones._cache_valida() is False


def test_cache_invalida_si_el_hash_no_coincide(entorno_aislado):
    _, cache, cache_hash = entorno_aislado
    cache.write_text("patientId,cruda\n1,0.5\n", encoding="utf-8")
    cache_hash.write_text("0" * 64, encoding="utf-8")
    assert puntuaciones._cache_valida() is False


def test_cache_valida_si_el_hash_coincide(entorno_aislado):
    pesos, cache, cache_hash = entorno_aislado
    cache.write_text("patientId,cruda\n1,0.5\n", encoding="utf-8")
    cache_hash.write_text(puntuaciones._sha256(pesos), encoding="utf-8")
    assert puntuaciones._cache_valida() is True


def test_puntuaciones_de_prueba_no_reinfiere_si_la_cache_es_valida(entorno_aislado):
    """El camino rapido: si la cache y el hash coinciden, se lee el CSV tal
    cual -- si esto intentara reinferir, fallaria (no hay modelo real, dataset
    ni pesos de verdad en `entorno_aislado`)."""
    pesos, cache, cache_hash = entorno_aislado
    cache.write_text("patientId,cruda\nabc,0.42\n", encoding="utf-8")
    cache_hash.write_text(puntuaciones._sha256(pesos), encoding="utf-8")
    df = puntuaciones.puntuaciones_de_prueba()
    assert df.to_dict("records") == [{"patientId": "abc", "cruda": 0.42}]


def test_pesos_cambiados_invalida_la_cache_existente(entorno_aislado):
    """Si el modelo se reentrena (los pesos cambian de contenido), la cache
    vieja deja de ser valida aunque el fichero siga estando ahi -- este es
    exactamente el bug del punto 5: antes, nada comprobaba esto."""
    pesos, cache, cache_hash = entorno_aislado
    cache.write_text("patientId,cruda\nabc,0.42\n", encoding="utf-8")
    cache_hash.write_text(puntuaciones._sha256(pesos), encoding="utf-8")
    assert puntuaciones._cache_valida() is True

    pesos.write_bytes(b"pesos de mentira, version 2 (reentrenado)")
    assert puntuaciones._cache_valida() is False


def test_con_la_cache_valida_no_se_pide_rsna_raiz(entorno_aislado, monkeypatch):
    """Con la cache al dia no se toca el dataset, asi que tampoco se pide
    donde esta: quien solo quiere las puntuaciones no necesita RSNA."""
    pesos, cache, cache_hash = entorno_aislado
    cache.write_text("patientId,cruda\nabc,0.42\n", encoding="utf-8")
    cache_hash.write_text(puntuaciones._sha256(pesos), encoding="utf-8")
    monkeypatch.delenv("RSNA_RAIZ", raising=False)
    df = puntuaciones.puntuaciones_de_prueba()
    assert df.to_dict("records") == [{"patientId": "abc", "cruda": 0.42}]


def test_con_la_cache_fria_y_sin_rsna_raiz_se_detiene_nombrandola(
        entorno_aislado, monkeypatch):
    """Sin cache hay que inferir, y para inferir hace falta el dataset. Sin
    la variable se dice cual falta, antes de leer nada."""
    _, cache, cache_hash = entorno_aislado
    monkeypatch.delenv("RSNA_RAIZ", raising=False)
    with pytest.raises(SystemExit, match="RSNA_RAIZ"):
        puntuaciones.puntuaciones_de_prueba()
    assert not cache.exists() and not cache_hash.exists()


def test_con_la_cache_fria_el_manifiesto_se_busca_bajo_rsna_raiz(
        entorno_aislado, tmp_path, monkeypatch):
    """La raiz es la de la variable y ninguna otra: con una carpeta vacia, lo
    que falta es SU manifiesto."""
    raiz = tmp_path / "rsna"
    raiz.mkdir()
    monkeypatch.setenv("RSNA_RAIZ", str(raiz))
    with pytest.raises(FileNotFoundError) as error:
        puntuaciones.puntuaciones_de_prueba()
    assert error.value.filename == str(raiz / "manifiestos" / "test.csv")


def test_el_modulo_no_guarda_ninguna_ruta_del_dataset():
    assert not hasattr(puntuaciones, "RAIZ")
