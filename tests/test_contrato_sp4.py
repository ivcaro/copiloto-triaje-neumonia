# tests/test_contrato_sp4.py
"""Lo que el bot de SP4 espera del copiloto DESPLEGADO: el bloque `combinacion`.

Aparte de `test_contrato_mcp.py` a proposito: las diez comprobaciones de aquel
fichero son el criterio 2 del spec de SP4 -pasan sin modificarse- y su unico
cambio es la constante del `docker run`, que ahora necesita PREVALENCIA_LOCAL.

NECESITA EL SERVIDOR VIVO, y con SP4. Sin servidor se salta, como aquel. Con
un servidor ANTERIOR a SP4 -su /salud no publica `prevalencia_local`- tambien
se salta, diciendo que la imagen que responde es vieja: eso no es un fallo del
contrato, es que todavia no se ha redesplegado. Se lee con `pytest -rs`.
"""
import base64
import json
import urllib.request

import pytest

from test_contrato_mcp import ARRANCAR, BASE, dicom_adulto  # noqa: F401

CONTRATO_SP3 = {"probabilidad_cruda", "probabilidad_calibrada",
                "razon_de_verosimilitud", "umbral", "clasificacion",
                "edad_paciente", "modelo", "auc_validacion", "milisegundos"}
HALLAZGOS = {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
             "crepitantes": True, "murmullo_disminuido": False,
             "asma": "no_se"}


@pytest.fixture(scope="module", autouse=True)
def copiloto_con_sp4() -> dict:
    try:
        with urllib.request.urlopen(f"{BASE}/salud", timeout=3) as r:
            salud = json.load(r)
    except (OSError, ValueError) as e:
        pytest.skip(
            f"CONTRATO SP4 SIN VERIFICAR: {BASE}/salud no responde "
            f"({type(e).__name__}). Se queda sin comprobar el bloque "
            f"`combinacion` (§9.2 de SP4). Levanta el contenedor y repite:  "
            f"{ARRANCAR}  -- o apunta COPILOTO_URL a uno que ya este vivo.")
    if salud.get("estado") != "listo":
        pytest.skip(f"CONTRATO SP4 SIN VERIFICAR: estado={salud.get('estado')!r}")
    if "prevalencia_local" not in salud:
        pytest.skip(
            "CONTRATO SP4 SIN VERIFICAR: el copiloto que responde es ANTERIOR "
            "a SP4 (su /salud no publica `prevalencia_local`). Reconstruye la "
            "imagen con el compose actual y repite.")
    return salud


def _llamar_con(b64: str, hallazgos) -> dict:
    """Como `_llamar` de test_contrato_mcp.py, con el segundo argumento. No se
    importa aquel para no tocarle ni la firma."""
    argumentos = {"dicom_base64": b64}
    if hallazgos is not None:
        argumentos["hallazgos"] = hallazgos
    cuerpo = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "clasificar_radiografia",
                   "arguments": argumentos}}).encode()
    pet = urllib.request.Request(
        f"{BASE}/mcp", data=cuerpo,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    texto = urllib.request.urlopen(pet, timeout=30).read().decode()
    for linea in texto.splitlines():
        if linea.startswith("data: "):
            return json.loads(linea[6:])
    pytest.fail(f"la respuesta no traia ninguna linea 'data: ': {texto[:200]}")


def test_con_hallazgos_llega_el_bloque_combinacion(dicom_adulto, copiloto_con_sp4):
    sc = _llamar_con(base64.b64encode(dicom_adulto).decode(),
                     HALLAZGOS)["result"]["structuredContent"]
    assert set(sc) == CONTRATO_SP3 | {"combinacion"}
    c = sc["combinacion"]
    assert c["rv_imagen"] == sc["razon_de_verosimilitud"]
    assert c["prevalencia"] == copiloto_con_sp4["prevalencia_local"]
    assert c["puntuacion"] == [3, 4]
    assert 0.0 < c["minima"] <= c["maxima"] < 1.0


def test_sin_hallazgos_la_respuesta_desplegada_sigue_siendo_la_de_sp3(dicom_adulto):
    """Criterio 2, contra el contenedor: ni una clave mas."""
    sc = _llamar_con(base64.b64encode(dicom_adulto).decode(),
                     None)["result"]["structuredContent"]
    assert set(sc) == CONTRATO_SP3


def test_unos_hallazgos_invalidos_se_rechazan_con_su_codigo_en_segundo_campo(dicom_adulto):
    """El codigo va en la posicion que `Leer respuesta` sabe leer (§10.3 de
    SP3), aunque el bot no conozca este codigo y lo trate como
    error_no_reconocido (D4)."""
    r = _llamar_con(base64.b64encode(dicom_adulto).decode(),
                    {**HALLAZGOS, "asma": "quizas"})["result"]
    assert r["isError"] is True
    partes = r["content"][0]["text"].split(":")
    assert partes[1].strip() == "hallazgos_invalidos", r["content"][0]["text"]
    assert r.get("structuredContent") in (None, {})
