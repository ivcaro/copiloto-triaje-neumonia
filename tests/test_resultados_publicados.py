"""Lo publicado de la simulación semisintética (spec de SP5 §4.8, §11.2-§11.3):
el JSON versionado corresponde a los insumos y al código de hoy, y el
documento y las figuras salen de él.

No vuelve a correr el bootstrap (son minutos): recalcula la estimación
puntual de dos celdas y la compara con la publicada, y regenera el documento
desde el JSON para comprobar que el versionado es ese. Si alguien cambia las
crudas, el calibrador, el generador, el oráculo, las métricas o el documento
sin volver a correr `scripts/validar_combinacion.py`, esto falla.
"""
import json
import os

import pytest

from copiloto_triaje.validacion import datos, informe, metricas, oraculo, simulacion

RESULTADOS = datos.CARPETA / "resultados_simulacion.json"
ANALISIS = datos.REPO / "docs" / "validacion-semisintetica-sp5.md"
ROTULO = "simulación semisintética"
MEDIDO = ("modelos", "pareadas", "horquilla", "discordantes", "no_se")


@pytest.fixture(scope="module")
def publicados():
    return json.loads(RESULTADOS.read_text(encoding="utf-8"))


def _celda(publicados, nombre):
    return next(c for c in publicados["celdas"] if c["nombre"] == nombre)


def test_llevan_el_rotulo_y_las_huellas_de_los_insumos_de_hoy(publicados):
    assert publicados["rotulo"] == ROTULO and ROTULO in publicados["titulo"]
    i = publicados["insumos"]
    assert i["crudas"] == "docs/validacion-semisintetica/crudas_prueba.csv"
    assert i["calibrador"] == "servidor/calibrador.json"
    assert i["crudas_sha256"] == datos.huella_de_texto(datos.CRUDAS_CONGELADAS)
    assert i["calibrador_sha256"] == datos.huella_de_texto(datos.CALIBRADOR)
    assert i["pesos_sha256"] == datos.HASH_CONGELADO.read_text(encoding="utf-8").split()[0]
    assert (i["placas"], i["positivas"], i["prevalencia"]) == (3811, 844, 0.2215)


def test_son_la_rejilla_entera_con_mil_replicas_en_0a_y_las_destacadas(publicados):
    p = publicados["parametros"]
    assert p["replicas"] == simulacion.B_REPLICAS == 1000
    assert p["epsilon"] == metricas.EPSILON
    assert p["rejilla"] == list(oraculo.RHO_REJILLA)
    assert [tuple(d) for d in p["destacadas"]] == list(oraculo.CELDAS_DESTACADAS)
    celdas = publicados["celdas"]
    assert len(celdas) == 25
    assert [(c["rho1"], c["rho0"]) for c in celdas] == [
        (a, b) for a in oraculo.RHO_REJILLA for b in oraculo.RHO_REJILLA]
    destacadas = {(c["rho1"], c["rho0"]) for c in celdas if c["destacada"]}
    assert destacadas == set(oraculo.CELDAS_DESTACADAS)
    con_intervalos = {(c["rho1"], c["rho0"]) for c in celdas if "intervalos" in c}
    assert con_intervalos == destacadas | {(0.0, 0.0)}
    assert all(c["replicas"] == 1000 for c in celdas if "intervalos" in c)
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


@pytest.mark.parametrize("nombre, rho1, rho0", [("0A", 0.0, 0.0), ("(0,3; 0,3)", 0.3, 0.3)])
def test_el_codigo_de_hoy_reproduce_las_cifras_publicadas(publicados, nombre, rho1, rho0):
    publicada = _celda(publicados, nombre)
    hoy = simulacion.evaluar_celda(simulacion.cargar_conjunto(), rho1, rho0,
                                   con_sensibilidad=True)
    assert hoy["recuentos"] == publicada["recuentos"]
    a = simulacion.aplanar({k: hoy[k] for k in MEDIDO})
    b = simulacion.aplanar({k: publicada[k] for k in MEDIDO})
    assert set(a) == set(b)
    for ruta in a:
        assert a[ruta] == pytest.approx(b[ruta], abs=1e-9), ruta
    assert simulacion.aplanar(hoy["escala_legible"]) == pytest.approx(
        simulacion.aplanar(publicada["escala_legible"]), abs=1e-9)
    assert simulacion.aplanar(hoy["sensibilidad_al_previo"]) == pytest.approx(
        simulacion.aplanar(publicada["sensibilidad_al_previo"]), abs=1e-9)


def test_cada_intervalo_publicado_esta_bien_formado(publicados):
    for celda in publicados["celdas"]:
        for ruta, (li, ls) in celda.get("intervalos", {}).items():
            assert li is not None and ls is not None and li <= ls, (celda["nombre"], ruta)


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
