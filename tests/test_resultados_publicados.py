"""Lo publicado de la simulación semisintética (spec de SP5 §4.8, §11.2-§11.3):
el JSON versionado corresponde a los insumos y al código de hoy, y el
documento y las figuras salen de él.

QUÉ VIGILA. Todo lo que no es bootstrap se vuelve a calcular con el propio
guion (`calcular` con 0 réplicas: las 25 celdas, la imagen sola, los insumos y
los parámetros) y se compara con lo publicado, cifra a cifra. El documento se
regenera desde el JSON y tiene que ser el versionado. Las figuras tienen que
ser las de las celdas del JSON, con su resolución, su rótulo y la huella de
ESE JSON en sus metadatos: una figura de otra corrida no pasa. Si alguien
cambia las crudas, el calibrador, el generador, el oráculo, las métricas, una
semilla, un umbral o el documento sin volver a correr
`scripts/validar_combinacion.py`, esto falla.

Del bootstrap se vuelven a calcular, con sus 1 000 réplicas, los intervalos
de UNA celda, (0,6; 0), que es asimétrica: si cambia el método del bootstrap,
una semilla o una métrica, esto falla.

QUÉ NO VIGILA. Los intervalos de las otras seis celdas no se vuelven a
calcular: se comprueba que cada cifra medida lleva el suyo y que están bien
formados. Sus cifras solo quedan vigiladas de rebote: las que el documento
imprime, y con los decimales con que las imprime, porque el documento se
regenera y se compara. Tampoco se comparan los píxeles de las figuras: solo
sus nombres, su resolución, su huella y su título (que lleve el rótulo y, en
las de fiabilidad, el nombre de su celda). Si se toca el dibujo, o algo del
bootstrap que no mueva los intervalos de (0,6; 0), hay que volver a correr el
guion: ninguna prueba lo va a pedir.

Las versiones de las librerías (`entorno`) no se comparan con las de esta
máquina: lo publicado salió con las suyas. Pero si el recálculo no coincide y
las versiones son otras, el fallo lo dice.
"""
import json
import os
import re

import pytest

from copiloto_triaje.servicio.heckerling import PREVALENCIA_COHORTE
from copiloto_triaje.validacion import datos, informe, metricas, oraculo, simulacion

RESULTADOS = datos.CARPETA / "resultados_simulacion.json"
ANALISIS = datos.REPO / "docs" / "validacion-semisintetica-sp5.md"
ROTULO = "simulación semisintética"
DEL_BOOTSTRAP = ("intervalos", "replicas")     # lo unico de una celda que no se recalcula
RECALCULADA = (0.6, 0.0)                       # la celda cuyo bootstrap si se repite
# Lo que mide `simulacion.medir`, que es lo que lleva intervalo.
MEDIDO = ("modelos", "pareadas", "horquilla", "discordantes", "no_se")
SIN_INTERVALO = ("suelo", "fiabilidad")        # de cada modelo: solo en la estimacion
# Las claves de primer nivel que NO se comparan con `_comparar`, y por que:
# `parametros` lleva las replicas, que son del bootstrap (se compara sin ellas);
# `celdas` se compara celda a celda, sin lo del bootstrap; `entorno` es de la
# maquina que publico. Cualquier otra clave, tambien una nueva, se compara.
APARTE = ("parametros", "celdas", "entorno")
LIBRERIAS = ["python", "numpy", "scipy", "pandas", "scikit-learn"]


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
    """Las mismas claves, las mismas listas, los mismos tipos y las mismas
    cifras (a 1e-9). Un 3 no es un 3.0 ni un 1 es un True: los dos salen de
    `json.loads`, y una diferencia de tipo es una diferencia."""
    assert type(recalculado) is type(publicado), ruta
    if isinstance(publicado, dict):
        assert set(publicado) == set(recalculado), ruta
        for clave in publicado:
            _comparar(publicado[clave], recalculado[clave], f"{ruta}.{clave}")
    elif isinstance(publicado, list):
        assert len(publicado) == len(recalculado), ruta
        for i, (a, b) in enumerate(zip(publicado, recalculado)):
            _comparar(a, b, f"{ruta}[{i}]")
    elif isinstance(publicado, float):
        assert recalculado == pytest.approx(publicado, abs=1e-9), ruta
    else:
        assert recalculado == publicado, ruta


def _otra_pila(publicados, hoy) -> str:
    """Si lo publicado se calculo con otras versiones, la frase que lo dice."""
    antes, ahora = publicados["entorno"], hoy["entorno"]
    distintas = [f"{clave} {antes[clave]} → {ahora.get(clave, 'no está')}"
                 for clave in antes if antes[clave] != ahora.get(clave)]
    if not distintas:
        return ""
    return ("\nOJO: lo publicado se calculó con otras versiones (" + "; ".join(distintas)
            + "): la diferencia puede venir de la librería y no del código.")


def test_comparar_distingue_tipos_claves_y_cifras():
    _comparar({"a": [1, 2.0, "x", None, True]}, {"a": [1, 2.0 + 5e-10, "x", None, True]}, "r")
    for publicado, recalculado in (
            (3, 3.0), (3.0, 3), (1, True), (True, 1), (0.0, False), (None, 0), ("1", 1),
            (2.0, 2.0 + 2e-9), (1e6, 1e6 + 1e-6), ([1, 2], [1, 2, 3]), ([1, 2], [2, 1]),
            ({"a": 1}, {"a": 1, "b": 2}), ({"a": 1, "b": 2}, {"a": 1}), ({"a": 1}, [1]),
            ([1.0], (1.0,))):
        with pytest.raises(AssertionError):
            _comparar(publicado, recalculado, "r")
    assert _otra_pila({"entorno": {"numpy": "2.5.2"}}, {"entorno": {"numpy": "2.5.2"}}) == ""
    assert _otra_pila({"entorno": {"numpy": "2.5.2", "scipy": "1.18.1"}},
                      {"entorno": {"numpy": "2.6.0"}}) == (
        "\nOJO: lo publicado se calculó con otras versiones (numpy 2.5.2 → 2.6.0; scipy "
        "1.18.1 → no está): la diferencia puede venir de la librería y no del código.")


def test_llevan_el_rotulo_y_las_huellas_de_los_insumos_de_hoy(publicados):
    assert publicados["rotulo"] == ROTULO and ROTULO in publicados["titulo"]
    i = publicados["insumos"]
    assert i["crudas"] == "docs/validacion-semisintetica/crudas_prueba.csv"
    assert i["calibrador"] == "servidor/calibrador.json"
    assert i["crudas_sha256"] == datos.huella_de_texto(datos.CRUDAS_CONGELADAS)
    assert i["calibrador_sha256"] == datos.huella_de_texto(datos.CALIBRADOR)
    assert i["pesos_sha256"] == datos.HASH_CONGELADO.read_text(encoding="utf-8").split()[0]
    assert (i["placas"], i["positivas"], i["prevalencia"]) == (3811, 844, 0.2215)


def test_dicen_con_que_versiones_se_calcularon(publicados):
    """Las de la maquina que publico, que no tienen por que ser las de esta."""
    assert list(publicados["entorno"]) == LIBRERIAS
    for version in publicados["entorno"].values():
        assert re.fullmatch(r"\d+(\.\w+)+", version), version


def test_los_parametros_publicados_son_las_constantes_del_codigo(publicados):
    """Una semilla o un umbral cambiados en el codigo dejan viejo lo publicado."""
    assert publicados["parametros"] == {
        "replicas": simulacion.B_REPLICAS,
        "semilla_puntual": simulacion.SEMILLA_PUNTUAL,
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
    assert p["replicas"] == simulacion.B_REPLICAS == 1000
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
    assert {"rotulo", "titulo", "advertencia", "insumos", "imagen_sola"} <= (
        set(publicados) - set(APARTE))
    try:
        for clave in sorted(set(publicados) - set(APARTE)):
            _comparar(publicados[clave], hoy[clave], clave)
        _comparar({k: v for k, v in publicados["parametros"].items() if k != "replicas"},
                  {k: v for k, v in hoy["parametros"].items() if k != "replicas"},
                  "parametros")
        assert [c["nombre"] for c in hoy["celdas"]] == [
            c["nombre"] for c in publicados["celdas"]]
        for publicada, recalculada in zip(publicados["celdas"], hoy["celdas"]):
            assert not set(recalculada) & set(DEL_BOOTSTRAP), publicada["nombre"]
            _comparar(_sin_bootstrap(publicada), recalculada, publicada["nombre"])
    except AssertionError as error:
        nota = _otra_pila(publicados, hoy)
        if not nota:
            raise
        raise AssertionError(f"{error}{nota}") from error
    # y lo que se compara no es poca cosa: cada celda lleva todo lo medido
    for celda in publicados["celdas"]:
        assert {"recuentos", "modelos", "pareadas", "horquilla", "discordantes", "no_se",
                "hipotesis", "escala_legible", "correlacion_teorica"} <= set(celda)


def _rutas_medidas(celda) -> list:
    """Las rutas de las cifras `float` que mide `medir` en una celda: las que
    tienen que llevar intervalo."""
    medido = {clave: celda[clave] for clave in MEDIDO}
    medido["modelos"] = {
        modelo: {k: v for k, v in cifras.items() if k not in SIN_INTERVALO}
        for modelo, cifras in celda["modelos"].items()}
    return sorted(simulacion.aplanar(medido))


def test_el_bootstrap_de_una_celda_se_repite_y_da_lo_publicado(publicados):
    """Una celda asimétrica, entera: las 1 000 réplicas y los 51 intervalos."""
    rho1, rho0 = RECALCULADA
    publicada = next(c for c in publicados["celdas"]
                     if (c["rho1"], c["rho0"]) == RECALCULADA)
    assert publicada["destacada"] and publicada["replicas"] == simulacion.B_REPLICAS
    hoy = simulacion.evaluar_celda(simulacion.cargar_conjunto(), rho1, rho0,
                                   replicas=simulacion.B_REPLICAS)
    assert sorted(hoy["intervalos"]) == sorted(publicada["intervalos"])
    assert len(hoy["intervalos"]) == 51
    for ruta, (li, ls) in publicada["intervalos"].items():
        assert hoy["intervalos"][ruta] == pytest.approx([li, ls], abs=1e-9), ruta


def test_cada_intervalo_publicado_esta_bien_formado(publicados):
    """El bootstrap de las demás celdas no se repite aquí: se comprueba su
    forma, y que cada cifra medida lleva su intervalo."""
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
    # y estan todos: cada cifra que se mide en la celda lleva el suyo
    con_bootstrap = [c for c in publicados["celdas"] if "intervalos" in c]
    assert len(con_bootstrap) == 7
    for celda in con_bootstrap:
        assert sorted(celda["intervalos"]) == _rutas_medidas(celda), celda["nombre"]
        assert len(celda["intervalos"]) == 51, celda["nombre"]


def test_las_figuras_publicadas_son_las_de_las_celdas_del_json(publicados, validar):
    con_figura = [c for c in publicados["celdas"] if c["nombre"] == "0A" or c["destacada"]]
    esperadas = sorted(
        [f"fiabilidad_{validar.slug_de_celda(c)}.png" for c in con_figura]
        + [f"{nombre}.png" for nombre in validar.FIGURAS_GLOBALES])
    presentes = validar.figuras_presentes(datos.CARPETA)
    assert [p.name for p in presentes] == esperadas
    assert len(esperadas) == 10
    from PIL import Image
    titulos = {}
    for ruta in presentes:
        with Image.open(ruta) as imagen:
            assert imagen.info["dpi"] == pytest.approx((300, 300), abs=1), ruta.name
            assert ROTULO in imagen.info["Title"], ruta.name
            assert re.fullmatch(r"matplotlib \d+(\.\w+)+", imagen.info["Software"]), ruta.name
            assert "http" not in " ".join(str(v) for v in imagen.info.values()), ruta.name
            titulos[ruta.name] = imagen.info["Title"]
    # cada figura de fiabilidad es la de SU celda
    for celda in con_figura:
        titulo = titulos[f"fiabilidad_{validar.slug_de_celda(celda)}.png"]
        assert f"celda {celda['nombre']} —" in titulo, titulo
    assert len(set(titulos.values())) == 10
    # y todas salen de ESTE JSON: llevan su huella
    assert validar.figuras_ajenas(publicados, presentes) == []


def test_el_documento_versionado_es_el_que_sale_del_json(publicados, validar):
    figuras = validar.figuras_presentes(datos.CARPETA)
    enlaces = {f.stem: os.path.relpath(f, ANALISIS.parent).replace(os.sep, "/")
               for f in figuras}
    esperado = informe.redactar(publicados, enlaces,
                                validar.figuras_ajenas(publicados, figuras))
    versionado = ANALISIS.read_text(encoding="utf-8")       # newline=None: CRLF y LF valen igual
    assert versionado == esperado
    assert versionado.startswith("# ") and ROTULO in versionado.splitlines()[0]
    assert "validacion-semisintetica/fiabilidad_0a.png" in versionado
    assert ("Las 10 figuras enlazadas llevan la huella de los resultados de este documento."
            ) in versionado
    assert "**Aviso:" not in versionado
