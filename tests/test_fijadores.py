# -*- coding: utf-8 -*-
"""Los fijadores de `tests/conftest.py`, probados sin red.

`webhook_n8n` habla con un n8n de verdad, y el repositorio no lleva la URL de
ninguno: la pone quien corre la suite, en `N8N_URL`. Lo que se comprueba aqui es
la puerta, que es lo unico que se puede comprobar sin ese n8n: sin la variable
la prueba que pida el fijador se SALTA -no falla, y sobre todo no manda nada a
ningun sitio-, y con ella se habla a esa URL y a ninguna otra.

La funcion del fijador se llama a traves de `__wrapped__`: pytest no deja llamar
a un fijador directamente, pero guarda ahi la funcion que decoro.
"""
import json

import pytest

import conftest

fijador = conftest.webhook_n8n.__wrapped__


def _sin_red(monkeypatch):
    """Cualquier intento de salir a la red hace fallar la prueba."""
    monkeypatch.setattr(
        conftest.urllib.request, "urlopen",
        lambda *a, **k: pytest.fail("el fijador salió a la red"))


@pytest.mark.parametrize("valor", [None, "", "   "],
                         ids=["ausente", "vacia", "en-blanco"])
def test_sin_N8N_URL_el_fijador_salta_y_dice_que_se_queda_sin_correr(
        monkeypatch, valor):
    if valor is None:
        monkeypatch.delenv("N8N_URL", raising=False)
    else:
        monkeypatch.setenv("N8N_URL", valor)
    _sin_red(monkeypatch)

    with pytest.raises(pytest.skip.Exception) as salto:
        fijador()

    motivo = str(salto.value)
    assert "N8N_URL" in motivo
    assert "pruebas conducidas" in motivo


@pytest.mark.parametrize("valor", [
    "n8n.inventado.test", "https://n8n.inventado.test/webhook/copiloto-paciente",
    '"https://n8n.inventado.test"', "https://n8n. inventado.test", "/"])
def test_con_N8N_URL_mal_puesta_el_fijador_falla_diciendo_por_que(monkeypatch, valor):
    """Mal puesta no se SALTA: un salto se ve verde, y quien la puso quiere
    correr las pruebas conducidas. Falla, diciendo por que, sin repetir el
    valor y sin salir a la red."""
    monkeypatch.setenv("N8N_URL", valor)
    _sin_red(monkeypatch)

    with pytest.raises(pytest.fail.Exception) as fallo:
        fijador()

    motivo = str(fallo.value)
    assert "N8N_URL" in motivo and "mal puesta" in motivo
    assert "inventado" not in motivo


def test_con_N8N_URL_el_fijador_habla_con_esa_url_y_con_ninguna_otra(monkeypatch):
    monkeypatch.setenv("N8N_URL", "https://otro.ejemplo.test/")
    pedidas = []

    def falso(pet, timeout=0):
        pedidas.append(pet)

        class R:
            status = 200

            def read(self_inner):
                return b"hecho"
        return R()

    monkeypatch.setattr(conftest.urllib.request, "urlopen", falso)

    enviar = fijador()
    assert enviar("copiloto-paciente", {"a": 1}, "S3CR3T0") == (200, "hecho")

    (pet,) = pedidas
    assert pet.full_url == "https://otro.ejemplo.test/webhook/copiloto-paciente"
    assert json.loads(pet.data) == {"a": 1}
    assert pet.get_header("X-telegram-bot-api-secret-token") == "S3CR3T0"
