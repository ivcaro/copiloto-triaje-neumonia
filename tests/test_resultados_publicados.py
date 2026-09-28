"""Lo publicado de la simulación semisintética (spec de SP5 §4.8, §11.2-§11.3):
el JSON versionado corresponde a los insumos y al código de hoy, y el
documento y las figuras salen de él.

QUÉ VIGILA. Todo lo que no es bootstrap se vuelve a calcular con el propio
guion (`calcular` con 0 réplicas: las 25 celdas, la imagen sola, los insumos y
los parámetros) y se compara con lo publicado, cifra a cifra. El documento se
regenera desde el JSON y tiene que ser el versionado. Las figuras tienen que
ser las de las celdas del JSON, con su resolución y su rótulo. Si alguien
cambia las crudas, el calibrador, el generador, el oráculo, las métricas, una
semilla, un umbral o el documento sin volver a correr
`scripts/validar_combinacion.py`, esto falla.

QUÉ NO VIGILA. Los intervalos del bootstrap no se vuelven a calcular (son
minutos): solo se comprueba que están donde tienen que estar y bien formados.
Tampoco se compara el contenido de las figuras: solo sus nombres, su
resolución y su título. Si se toca algo que cambie el bootstrap o el dibujo,
hay que volver a correr el guion: ninguna prueba lo va a pedir.
"""
import json
import os

import pytest

from copiloto_triaje.servicio.heckerling import PREVALENCIA_COHORTE
from copiloto_triaje.validacion import datos, informe, metricas, oraculo, simulacion

RESULTADOS = datos.CARPETA / "resultados_simulacion.json"
ANALISIS = datos.REPO / "docs" / "validacion-semisintetica-sp5.md"
ROTULO = "simulación semisintética"
DEL_BOOTSTRAP = ("intervalos", "replicas")     # lo unico de una celda que no se recalcula


@pytest.fixture(scope="module")
def publicados():
    return json.loads(RESULTADOS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def hoy(validar):
    """Lo que el guion calcula HOY, sin bootstrap, tal como lo escribiria."""
    return json.loads(json.dumps(validar.calcular(replicas=0, procesos=1),
                                 ensure_ascii=False, allow_nan=False))


def _celda(publicados, nombre):
    return next(c for c in publicados["celdas"] if c["nombre"] == nombre)


def _sin_bootstrap(celda):
    return {k: v for k, v in celda.items() if k not in DEL_BOOTSTRAP}


def _comparar(publicado, recalculado, ruta):
    """Las mismas claves, las mismas listas y las mismas cifras (a 1e-9)."""
    if isinstance(publicado, dict):
        assert isinstance(recalculado, dict) and set(publicado) == set(recalculado), ruta
        for clave in publicado:
            _comparar(publicado[clave], recalculado[clave], f"{ruta}.{clave}")
    elif isinstance(publicado, list):
        assert isinstance(recalculado, list) and len(publicado) == len(recalculado), ruta
        for i, (a, b) in enumerate(zip(publicado, recalculado)):
            _comparar(a, b, f"{ruta}[{i}]")
    elif isinstance(publicado, float) and isinstance(recalculado, (int, float)) \
            and not isinstance(recalculado, bool):
        assert recalculado == pytest.approx(publicado, abs=1e-9), ruta
    else:
        assert recalculado == publicado, ruta


def test_llevan_el_rotulo_y_las_huellas_de_los_insumos_de_hoy(publicados):
    assert publicados["rotulo"] == ROTULO and ROTULO in publicados["titulo"]
    i = publicados["insumos"]
    assert i["crudas"] == "docs/validacion-semisintetica/crudas_prueba.csv"
    assert i["calibrador"] == "servidor/calibrador.json"
    assert i["crudas_sha256"] == datos.huella_de_texto(datos.CRUDAS_CONGELADAS)
    assert i["calibrador_sha256"] == datos.huella_de_texto(datos.CALIBRADOR)
    assert i["pesos_sha256"] == datos.HASH_CONGELADO.read_text(encoding="utf-8").split()[0]
    assert (i["placas"], i["positivas"], i["prevalencia"]) == (3811, 844, 0.2215)


def test_los_parametros_publicados_son_las_constantes_del_codigo(publicados):
    """Una semilla o un umbral cambiados en el codigo dejan viejo lo publicado."""
    assert publicados["parametros"] == {
        "replicas": simulacion.B_REPLICAS,
        "semilla_puntual": simulacion.SEMILLA_PUNTUAL,
        "semilla_clinica": simulacion.SEMILLA_CLINICA,
        "semilla_indices": simulacion.SEMILLA_INDICES,
        "epsilon": metricas.EPSILON,
        "bins": metricas.BINS,
        "repeticiones_suelo": metricas.REPETICIONES_SUELO,
        "semilla_suelo": metricas.SEMILLA_SUELO,
        "hipotesis_contencion": simulacion.HIPOTESIS_CONTENCION,
        "previo_desplegado": PREVALENCIA_COHORTE,
        "rejilla": [float(r) for r in oraculo.RHO_REJILLA],
        "destacadas": [[float(a), float(b)] for a, b in oraculo.CELDAS_DESTACADAS],
    }
    assert publicados["parametros"]["replicas"] == 1000


def test_son_la_rejilla_entera_con_mil_replicas_en_0a_y_las_destacadas(publicados):
    p = publicados["parametros"]
    celdas = publicados["celdas"]
    assert len(celdas) == 25
    assert [(c["rho1"], c["rho0"]) for c in celdas] == [
        (a, b) for a in oraculo.RHO_REJILLA for b in oraculo.RHO_REJILLA]
    destacadas = {(c["rho1"], c["rho0"]) for c in celdas if c["destacada"]}
    assert destacadas == set(oraculo.CELDAS_DESTACADAS)
    con_intervalos = {(c["rho1"], c["rho0"]) for c in celdas if "intervalos" in c}
    assert con_intervalos == destacadas | {(0.0, 0.0)}
    assert all(c["replicas"] == p["replicas"] for c in celdas if "intervalos" in c)
    assert all("replicas" not in c for c in celdas if "intervalos" not in c)
    assert {(c["rho1"], c["rho0"]) for c in celdas
            if "sensibilidad_al_previo" in c} == con_intervalos


def test_la_fila_0a_publicada_es_la_comprobacion_de_la_metrica(publicados):
    cero = _celda(publicados, "0A")
    for lado in ("todos", "a_favor", "en_contra"):
        h = cero["horquilla"][lado]
        assert (h["bajo"], h["sobre"], h["contencion"]) == (0.0, 0.0, 1.0)
        assert cero["intervalos"][f"horquilla.{lado}.contencion"] == [1.0, 1.0]
        assert cero["intervalos"][f"horquilla.{lado}.bajo"] == [0.0, 0.0]
        assert cero["intervalos"][f"horquilla.{lado}.sobre"] == [0.0, 0.0]
    assert cero["hipotesis"]["se_sostiene"] is True
    assert "optimismo_de_la_derivacion" in cero


def test_el_codigo_de_hoy_reproduce_todo_lo_publicado_salvo_el_bootstrap(publicados, hoy):
    """Las 25 celdas, enteras: tambien las asimetricas (intercambiar ρ1 y ρ0
    no cambia las simetricas), 0C, la correlacion teorica y la hipotesis."""
    assert set(publicados) == set(hoy)
    for clave in ("rotulo", "titulo", "advertencia", "insumos", "imagen_sola"):
        _comparar(publicados[clave], hoy[clave], clave)
    _comparar({k: v for k, v in publicados["parametros"].items() if k != "replicas"},
              {k: v for k, v in hoy["parametros"].items() if k != "replicas"}, "parametros")
    assert [c["nombre"] for c in hoy["celdas"]] == [c["nombre"] for c in publicados["celdas"]]
    for publicada, recalculada in zip(publicados["celdas"], hoy["celdas"]):
        assert not set(recalculada) & set(DEL_BOOTSTRAP), publicada["nombre"]
        _comparar(_sin_bootstrap(publicada), recalculada, publicada["nombre"])
    # y lo que se compara no es poca cosa: cada celda lleva todo lo medido
    for celda in publicados["celdas"]:
        assert {"recuentos", "modelos", "pareadas", "horquilla", "discordantes", "no_se",
                "hipotesis", "escala_legible", "correlacion_teorica"} <= set(celda)


def test_cada_intervalo_publicado_esta_bien_formado(publicados):
    """El bootstrap no se repite aqui: se comprueba su forma, no sus cifras."""
    total = 0
    for celda in publicados["celdas"]:
        for ruta, (li, ls) in celda.get("intervalos", {}).items():
            assert li is not None and ls is not None and li <= ls, (celda["nombre"], ruta)
            valor = celda
            for clave in ruta.split("."):
                valor = valor[clave]               # el intervalo es de una cifra que existe
            assert isinstance(valor, (int, float)), (celda["nombre"], ruta)
            total += 1
    assert total > 300


def test_las_figuras_publicadas_son_las_de_las_celdas_del_json(publicados, validar):
    esperadas = sorted(
        [f"fiabilidad_{validar.slug_de_celda(c)}.png" for c in publicados["celdas"]
         if c["nombre"] == "0A" or c["destacada"]]
        + [f"{nombre}.png" for nombre in validar.FIGURAS_GLOBALES])
    presentes = validar.figuras_presentes(datos.CARPETA)
    assert [p.name for p in presentes] == esperadas
    assert len(esperadas) == 10
    from PIL import Image
    for ruta in presentes:
        with Image.open(ruta) as imagen:
            assert imagen.info["dpi"] == pytest.approx((300, 300), abs=1), ruta.name
            assert ROTULO in imagen.info["Title"], ruta.name


def test_el_documento_versionado_es_el_que_sale_del_json(publicados, validar):
    figuras = validar.figuras_presentes(datos.CARPETA)
    enlaces = {f.stem: os.path.relpath(f, ANALISIS.parent).replace(os.sep, "/")
               for f in figuras}
    esperado = informe.redactar(publicados, enlaces)
    versionado = ANALISIS.read_text(encoding="utf-8")       # newline=None: CRLF y LF valen igual
    assert versionado == esperado
    assert versionado.startswith("# ") and ROTULO in versionado.splitlines()[0]
    assert "validacion-semisintetica/fiabilidad_0a.png" in versionado
