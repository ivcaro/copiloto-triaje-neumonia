"""scripts/validar_combinacion.py: la rejilla, el JSON y sus huellas."""
import copy
import json
import re

import pytest

from copiloto_triaje.servicio.heckerling import PREVALENCIA_COHORTE
from copiloto_triaje.validacion import datos, oraculo, simulacion


@pytest.fixture(autouse=True)
def analisis_fuera_del_repo(validar, tmp_path_factory, monkeypatch):
    """Ninguna prueba escribe el analisis del repo: `main()` sin `--analisis`
    lo deja en una carpeta temporal."""
    ruta = tmp_path_factory.mktemp("analisis") / "validacion-semisintetica-sp5.md"
    monkeypatch.setattr(validar, "ANALISIS", ruta)
    return ruta


def test_las_tareas_de_la_rejilla(validar):
    tareas = validar.tareas_de_la_rejilla(1000)
    assert len(tareas) == 25
    assert tareas[0] == (0.0, 0.0, 1000, True)            # 0A
    completas = [(a, b) for a, b, replicas, todo in tareas if todo]
    assert set(completas) == {(0.0, 0.0)} | set(oraculo.CELDAS_DESTACADAS)
    assert all(replicas == (1000 if todo else 0) for _, _, replicas, todo in tareas)
    assert [(a, b) for a, b, _, _ in tareas[:6]] == [
        (0.0, 0.0), (0.0, 0.15), (0.0, 0.3), (0.0, 0.45), (0.0, 0.6), (0.15, 0.0)]


def test_los_resultados_llevan_rotulo_insumos_y_parametros(resultados_minimos):
    r = resultados_minimos
    assert r["rotulo"] == "simulación semisintética"
    assert "simulación semisintética" in r["titulo"]
    assert "exactitud clínica" in r["advertencia"]
    i = r["insumos"]
    assert (i["placas"], i["positivas"], i["prevalencia"]) == (3811, 844, 0.2215)
    # rutas relativas a la raiz del repo: ni la carpeta ni el usuario de nadie
    assert i["crudas"] == "docs/validacion-semisintetica/crudas_prueba.csv"
    assert i["calibrador"] == "servidor/calibrador.json"
    assert i["crudas_sha256"] == datos.huella_de_texto(datos.CRUDAS_CONGELADAS)
    assert i["calibrador_sha256"] == datos.huella_de_texto(datos.CALIBRADOR)
    assert i["pesos_sha256"] == datos.HASH_CONGELADO.read_text(encoding="utf-8").split()[0]
    assert len(i["pesos_sha256"]) == 64
    p = r["parametros"]
    assert p["replicas"] == 2 and p["epsilon"] == 0.015 and p["bins"] == 10
    assert p["previo_desplegado"] == pytest.approx(PREVALENCIA_COHORTE)
    assert p["semilla_puntual"] == simulacion.SEMILLA_PUNTUAL
    assert p["rejilla"] == [0.0, 0.3] and p["destacadas"] == [[0.3, 0.3]]
    assert list(r) == ["rotulo", "titulo", "advertencia", "insumos", "parametros",
                       "entorno", "imagen_sola", "celdas"]


def test_los_resultados_dicen_con_que_versiones_se_calcularon(validar, resultados_minimos):
    import platform

    import numpy
    import pandas
    import scipy
    import sklearn
    assert resultados_minimos["entorno"] == validar.entorno() == {
        "python": platform.python_version(), "numpy": numpy.__version__,
        "scipy": scipy.__version__, "pandas": pandas.__version__,
        "scikit-learn": sklearn.__version__}
    assert list(validar.entorno()) == ["python", "numpy", "scipy", "pandas", "scikit-learn"]
    # versiones y nada mas: ni la maquina, ni el usuario, ni la ruta del interprete
    for version in validar.entorno().values():
        assert re.fullmatch(r"\d+(\.\w+)+", version), version


def test_las_destacadas_repetidas_salen_una_vez(validar, monkeypatch):
    monkeypatch.setattr(simulacion, "evaluar_tarea", lambda tarea: {})
    r = validar.calcular(replicas=2, procesos=1, rejilla=(0.0, 0.3, 0.6),
                         destacadas=[[0.6, 0.3], (0.3, 0.3), (0.6, 0.3), [0.3, 0.3]])
    assert r["parametros"]["destacadas"] == [[0.6, 0.3], [0.3, 0.3]]
    assert [c["destacada"] for c in r["celdas"]].count(True) == 2
    assert len(r["celdas"]) == 9


def test_las_celdas_van_en_el_orden_de_la_rejilla(resultados_minimos):
    celdas = resultados_minimos["celdas"]
    assert [c["nombre"] for c in celdas] == ["0A", "(0; 0,3)", "(0,3; 0)", "(0,3; 0,3)"]
    assert [c["destacada"] for c in celdas] == [False, False, False, True]
    con_intervalos = [c["nombre"] for c in celdas if "intervalos" in c]
    assert con_intervalos == ["0A", "(0,3; 0,3)"]
    assert [c["nombre"] for c in celdas if "sensibilidad_al_previo" in c] == con_intervalos
    assert [c["nombre"] for c in celdas if "optimismo_de_la_derivacion" in c] == ["0A"]
    cero = celdas[0]
    assert cero["horquilla"]["todos"]["contencion"] == 1.0
    assert cero["intervalos"]["horquilla.todos.contencion"] == [1.0, 1.0]
    assert resultados_minimos["imagen_sola"]["casos"] == 3811


def test_el_json_se_escribe_en_utf8_con_lf_y_se_lee_igual(validar, resultados_minimos, tmp_path):
    ruta = validar.escribir_resultados(resultados_minimos, tmp_path / "sub" / "r.json")
    crudo = ruta.read_bytes()
    assert b"\r\n" not in crudo and crudo.endswith(b"\n")
    assert "simulación semisintética".encode("utf-8") in crudo
    assert "intermedia→baja".encode("utf-8") in crudo
    assert validar.leer_resultados(ruta) == resultados_minimos
    assert json.loads(crudo.decode("utf-8")) == resultados_minimos


def test_la_huella_de_texto_no_depende_del_fin_de_linea(tmp_path):
    lf, crlf = tmp_path / "lf.csv", tmp_path / "crlf.csv"
    lf.write_bytes(b"a,b\n1,2\n")
    crlf.write_bytes(b"a,b\r\n1,2\r\n")
    assert datos.huella_de_texto(lf) == datos.huella_de_texto(crlf) == datos.sha256_de(lf)
    assert datos.sha256_de(crlf) != datos.sha256_de(lf)


def test_en_paralelo_sale_lo_mismo_que_en_serie(validar, resultados_minimos):
    r = validar.calcular(replicas=2, procesos=2, rejilla=(0.0, 0.3),
                         destacadas=((0.3, 0.3),))
    assert json.loads(json.dumps(r, ensure_ascii=False)) == resultados_minimos

    # y no solo los mismos datos: el mismo FICHERO, con las claves en su orden
    def como_fichero(d):
        return json.dumps(d, ensure_ascii=False, indent=1, allow_nan=False)
    assert como_fichero(r) == como_fichero(resultados_minimos)


def test_una_destacada_que_no_esta_en_la_rejilla_se_rechaza(validar):
    # como listas, que es como las guarda el propio JSON, valen
    tareas = validar.tareas_de_la_rejilla(5, rejilla=[0, 0.3], destacadas=[[0.3, 0.3]])
    assert tareas == [(0.0, 0.0, 5, True), (0.0, 0.3, 0, False),
                      (0.3, 0.0, 0, False), (0.3, 0.3, 5, True)]
    with pytest.raises(ValueError, match="rejilla"):
        validar.tareas_de_la_rejilla(5, rejilla=(0.0, 0.3), destacadas=((0.3, 0.45),))
    with pytest.raises(ValueError, match="0A"):
        validar.tareas_de_la_rejilla(5, rejilla=(0.0, 0.3), destacadas=((0.0, 0.0),))


def test_la_huella_de_los_pesos_tiene_que_ser_un_sha256(validar, tmp_path, monkeypatch):
    assert validar.huella_de_los_pesos() == datos.HASH_CONGELADO.read_text(
        encoding="utf-8").strip()
    for contenido in ("", "no-es-una-huella", "ab" * 32 + " " + "cd" * 32, "AB" * 32):
        malo = tmp_path / "pesos.sha256"
        malo.write_text(contenido, encoding="utf-8")
        monkeypatch.setattr(datos, "HASH_CONGELADO", malo)
        with pytest.raises(SystemExit, match="no lleva un sha256"):
            validar.huella_de_los_pesos()


def test_un_nan_no_llega_al_json(validar, tmp_path):
    with pytest.raises(ValueError):
        validar.escribir_resultados({"cifra": float("nan")}, tmp_path / "r.json")
    assert not (tmp_path / "r.json").exists()


def test_si_no_se_puede_escribir_lo_anterior_sigue_entero(
        validar, resultados_minimos, tmp_path, monkeypatch):
    ruta = validar.escribir_resultados({"cifra": 1.5}, tmp_path / "r.json")
    antes = ruta.read_bytes()
    with pytest.raises(ValueError):
        validar.escribir_resultados({"cifra": float("nan")}, ruta)
    assert ruta.read_bytes() == antes
    # y el documento, lo mismo: se redacta antes de abrir
    analisis = validar.escribir_analisis(resultados_minimos, [], tmp_path / "a.md")
    antes = analisis.read_bytes()
    sin_entorno = {k: v for k, v in resultados_minimos.items() if k != "entorno"}
    with pytest.raises(KeyError):
        validar.escribir_analisis(sin_entorno, [], analisis)
    assert analisis.read_bytes() == antes and len(antes) > 1000
    with pytest.raises(KeyError):
        validar.escribir_analisis(sin_entorno, [], tmp_path / "sub" / "no.md")
    assert not (tmp_path / "sub").exists()


def test_main_escribe_los_resultados_donde_se_le_dice(
        validar, resultados_minimos, tmp_path, monkeypatch, capsys):
    llamadas = []

    def calcular_falso(replicas, procesos):
        llamadas.append((replicas, procesos))
        return resultados_minimos

    monkeypatch.setattr(validar, "calcular", calcular_falso)
    assert validar.main(["--replicas", "3", "--procesos", "1", "--salida", str(tmp_path),
                         "--sin-figuras"]) == 0
    assert llamadas == [(3, 1)]
    assert validar.leer_resultados(tmp_path / "resultados_simulacion.json") == resultados_minimos
    assert "resultados_simulacion.json" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        validar.main(["--procesos", "0", "--salida", str(tmp_path)])


# --------------------------------------------------------------------------
# Las figuras (tarea 5). Cada prueba que dibuja pide matplotlib: sin el extra
# `figuras` instalado se saltan, y las del calculo siguen corriendo.
# --------------------------------------------------------------------------
NOMBRES_MINIMOS = ["fiabilidad_0a.png", "fiabilidad_r1-030_r0-030.png",
                   "horquilla_por_celda.png", "contencion_rejilla.png",
                   "pendiente_rejilla.png"]


def test_el_slug_de_celda(validar, resultados_minimos):
    assert [validar.slug_de_celda(c) for c in resultados_minimos["celdas"]] == [
        "0a", "r1-000_r0-030", "r1-030_r0-000", "r1-030_r0-030"]
    assert validar.slug_de_celda(
        {"nombre": "(0,15; 0,6)", "rho1": 0.15, "rho0": 0.6}) == "r1-015_r0-060"
    assert validar.FIGURAS_GLOBALES == (
        "horquilla_por_celda", "contencion_rejilla", "pendiente_rejilla")
    assert validar.PREFIJO_FIABILIDAD == "fiabilidad_"
    assert validar.DPI == 300


def test_las_figuras_salen_con_su_nombre_a_300_dpi_y_con_el_rotulo(
        validar, resultados_minimos, tmp_path):
    pytest.importorskip("matplotlib")
    from PIL import Image
    rutas = validar.figuras(resultados_minimos, tmp_path / "figuras")
    assert [r.name for r in rutas] == NOMBRES_MINIMOS
    assert all(r.parent == tmp_path / "figuras" for r in rutas)
    for ruta in rutas:
        assert ruta.stat().st_size > 10_000
        with Image.open(ruta) as imagen:
            assert imagen.format == "PNG"
            assert imagen.size == (2700, 1650)            # 9 x 5,5 pulgadas a 300 DPI
            assert imagen.info["dpi"] == pytest.approx((300, 300), abs=1)
            assert "simulación semisintética" in imagen.info["Title"]
            # la version con que se dibujo, sin direccion web
            import matplotlib
            assert imagen.info["Software"] == f"matplotlib {matplotlib.__version__}"
            assert "http" not in " ".join(str(v) for v in imagen.info.values())
            assert sorted(k for k in imagen.info if k != "dpi") == [
                "Description", "Software", "Title"]
    # cada una dice de que resultados sale
    huella = validar.huella_de_resultados(resultados_minimos)
    assert re.fullmatch(r"[0-9a-f]{64}", huella)
    for ruta in rutas:
        with Image.open(ruta) as imagen:
            assert imagen.info["Description"] == (
                "dibujada de resultados_simulacion.json; sha256 de su contenido: " + huella)
        assert validar.huella_de_figura(ruta) == huella
    assert validar.figuras_ajenas(resultados_minimos, rutas) == []
    otro = copy.deepcopy(resultados_minimos)
    otro["imagen_sola"]["auc"] += 1e-9
    assert validar.figuras_ajenas(otro, rutas) == sorted(r.stem for r in rutas)
    titulos = {}
    for ruta in rutas:
        with Image.open(ruta) as imagen:
            titulos[ruta.name] = imagen.info["Title"]
    assert titulos == {
        "fiabilidad_0a.png": "Fiabilidad por deciles — celda 0A — simulación semisintética",
        "fiabilidad_r1-030_r0-030.png":
            "Fiabilidad por deciles — celda (0,3; 0,3) — simulación semisintética",
        "horquilla_por_celda.png":
            "El oráculo frente a la horquilla, por celda y lado — simulación semisintética",
        "contencion_rejilla.png":
            "Contención del oráculo en la horquilla, por celda — simulación semisintética",
        "pendiente_rejilla.png":
            "Pendiente de la independencia, por celda — simulación semisintética"}
    assert validar.figuras_presentes(tmp_path / "figuras") == sorted(rutas)


def test_cada_figura_se_puede_dibujar_por_separado(validar, resultados_minimos, tmp_path):
    pytest.importorskip("matplotlib")
    celda = resultados_minimos["celdas"][3]
    destino = tmp_path / "una.png"
    assert validar.figura_fiabilidad(celda, destino) == destino
    assert validar.figura_horquilla(resultados_minimos, tmp_path / "dos.png").is_file()
    assert validar.figura_rejilla(resultados_minimos, tmp_path / "tres.png",
                                  "contencion").is_file()
    assert validar.figura_rejilla(resultados_minimos, tmp_path / "cuatro.png",
                                  "pendiente").is_file()
    assert destino.stat().st_size > 10_000
    # dibujada suelta no lleva huella, salvo que se le de
    assert validar.huella_de_figura(destino) is None
    assert validar.figuras_ajenas(resultados_minimos, [destino]) == ["una"]
    for n, dibujar in enumerate((
            lambda d: validar.figura_fiabilidad(celda, d, "ab" * 32),
            lambda d: validar.figura_horquilla(resultados_minimos, d, "ab" * 32),
            lambda d: validar.figura_rejilla(resultados_minimos, d, "pendiente", "ab" * 32))):
        assert validar.huella_de_figura(dibujar(tmp_path / f"con_huella_{n}.png")) == "ab" * 32
    with pytest.raises(ValueError, match="contencion"):
        validar.figura_rejilla(resultados_minimos, tmp_path / "cinco.png", "auc")
    assert not (tmp_path / "cinco.png").exists()


def test_la_huella_es_del_contenido_y_no_del_fichero(validar, resultados_minimos, tmp_path):
    huella = validar.huella_de_resultados(resultados_minimos)
    al_reves = dict(reversed(list(resultados_minimos.items())))
    assert list(al_reves) != list(resultados_minimos)
    assert validar.huella_de_resultados(al_reves) == huella
    ruta = validar.escribir_resultados(resultados_minimos, tmp_path / "r.json")
    assert validar.huella_de_resultados(validar.leer_resultados(ruta)) == huella
    con_crlf = tmp_path / "crlf.json"
    con_crlf.write_bytes(ruta.read_bytes().replace(b"\n", b"\r\n"))
    assert validar.huella_de_resultados(validar.leer_resultados(con_crlf)) == huella
    otro = copy.deepcopy(resultados_minimos)
    otro["celdas"][3]["horquilla"]["todos"]["contencion"] += 1e-12
    assert validar.huella_de_resultados(otro) != huella
    # lo que no es un PNG con huella, no la tiene
    (tmp_path / "no_es.png").write_bytes(b"de una corrida anterior")
    assert validar.huella_de_figura(tmp_path / "no_es.png") is None
    assert validar.huella_de_figura(tmp_path / "no_existe.png") is None
    from PIL import Image
    Image.new("RGB", (4, 4)).save(tmp_path / "sin_metadatos.png")
    assert validar.huella_de_figura(tmp_path / "sin_metadatos.png") is None


def test_un_lado_sin_casos_se_rotula_en_la_figura_de_la_horquilla(
        validar, resultados_minimos, tmp_path, monkeypatch):
    pytest.importorskip("matplotlib")
    from matplotlib.axes import Axes
    escritos = []
    escribir = Axes.text

    def escribir_espia(self, x, y, texto, **kwargs):
        escritos.append((x, y, texto, kwargs.get("color")))
        return escribir(self, x, y, texto, **kwargs)

    monkeypatch.setattr(Axes, "text", escribir_espia)
    validar.figura_horquilla(resultados_minimos, tmp_path / "con_casos.png")
    assert escritos and not [e for e in escritos if "n/d" in e[2]]
    escritos.clear()
    vacio = copy.deepcopy(resultados_minimos)
    vacio["celdas"][3]["horquilla"]["en_contra"].update(
        n=0, bajo=None, contencion=None, sobre=None)
    validar.figura_horquilla(vacio, tmp_path / "sin_casos.png")
    # la celda (0,3; 0,3) es la segunda barra (la primera es 0A)
    assert [e for e in escritos if "n/d" in e[2]] == [
        (50.0, 1, "n/d (sin casos)", validar.TINTA)]


def _contraste(una: float, otra: float) -> float:
    """La razon de contraste de WCAG 2 entre dos luminancias."""
    clara, oscura = max(una, otra), min(una, otra)
    return (clara + 0.05) / (oscura + 0.05)


def test_la_tinta_es_la_que_mas_contrasta_con_el_color_pintado(validar):
    pytest.importorskip("matplotlib")
    # la luminancia relativa de WCAG 2: sus tres coeficientes y su gamma
    assert validar._luminancia("#ff0000") == pytest.approx(0.2126)
    assert validar._luminancia("#00ff00") == pytest.approx(0.7152)
    assert validar._luminancia("#0000ff") == pytest.approx(0.0722)
    assert validar._luminancia("white") == pytest.approx(1.0)
    assert validar._luminancia("black") == 0.0
    assert validar._luminancia("#808080") == pytest.approx(0.2159, abs=1e-4)
    for claro in ("#e34948", "#f0a09f", "#c9c8c3", "#f0efec", "#cde2fb", "white"):
        assert validar._tinta_sobre(claro) == validar.TINTA, claro
    for oscuro in ("#1c5cab", "#0d366b", validar.TINTA, "black"):
        assert validar._tinta_sobre(oscuro) == "white", oscuro
    # tal como lo da un mapa de color: una tupla RGBA
    assert validar._tinta_sobre((0.05, 0.21, 0.42, 1.0)) == "white"
    assert validar._tinta_sobre((0.91, 0.55, 0.54, 1.0)) == validar.TINTA
    # y en cualquier color, tambien donde las dos casi empatan, la elegida
    # contrasta al menos tanto como la otra
    tinta = validar._luminancia(validar.TINTA)
    for color in validar.RAMPA_AZUL + validar.RAMPA_DIVERGENTE + tuple(
            c for _, _, c in validar.TRAMOS):
        fondo = validar._luminancia(color)
        elegida, otra = ((1.0, tinta) if validar._tinta_sobre(color) == "white"
                         else (tinta, 1.0))
        assert _contraste(fondo, elegida) >= _contraste(fondo, otra), color


def test_las_casillas_y_las_barras_se_escriben_con_la_tinta_que_contrasta(
        validar, resultados_minimos, tmp_path, monkeypatch):
    pytest.importorskip("matplotlib")
    from matplotlib.axes import Axes
    escritos = []
    escribir = Axes.text

    def escribir_espia(self, x, y, texto, **kwargs):
        escritos.append((texto, kwargs.get("color")))
        return escribir(self, x, y, texto, **kwargs)

    monkeypatch.setattr(Axes, "text", escribir_espia)
    # cifras puestas a mano, lejos del punto en que la tinta cambia (la
    # contencion cambia hacia el 59 %): la prueba es del dibujo, no de la
    # simulacion. Con la regla vieja (por posicion en la escala) el 55 % y las
    # pendientes 0,65 y 1,30 irian en blanco.
    trucados = copy.deepcopy(resultados_minimos)
    for celda, contencion, pendiente in zip(
            trucados["celdas"], (1.0, 0.20, 0.55, 0.70), (1.0, 0.65, 0.79, 1.30)):
        celda["horquilla"]["todos"]["contencion"] = contencion
        celda["modelos"]["independencia"]["pendiente"] = pendiente
    validar.figura_rejilla(trucados, tmp_path / "pendiente.png", "pendiente")
    assert escritos == [("1,00", validar.TINTA), ("0,65", validar.TINTA),
                        ("0,79", validar.TINTA), ("1,30", validar.TINTA)]

    escritos.clear()
    validar.figura_rejilla(trucados, tmp_path / "contencion.png", "contencion")
    assert escritos == [("100,0 %", "white"), ("20,0 %", validar.TINTA),
                        ("55,0 %", validar.TINTA), ("70,0 %", "white")]

    escritos.clear()
    for lado in ("a_favor", "en_contra"):
        trucados["celdas"][3]["horquilla"][lado].update(bajo=0.25, contencion=0.5, sobre=0.25)
    validar.figura_horquilla(trucados, tmp_path / "horquilla.png")
    assert ("25,0 %", validar.TINTA) in escritos and ("50,0 %", validar.TINTA) in escritos
    assert not [texto for texto, _ in escritos if "," not in texto]
    assert all(color == validar.TINTA for _, color in escritos)


def test_la_leyenda_de_fiabilidad_da_la_ece_con_la_media_y_el_p95_de_su_suelo(
        validar, resultados_minimos, tmp_path, monkeypatch):
    pytest.importorskip("matplotlib")
    from matplotlib.axes import Axes
    rotulos = []
    trazar = Axes.plot

    def trazar_espia(self, *args, **kwargs):
        rotulos.append(kwargs.get("label", ""))
        return trazar(self, *args, **kwargs)

    monkeypatch.setattr(Axes, "plot", trazar_espia)
    celda = resultados_minimos["celdas"][3]
    validar.figura_fiabilidad(celda, tmp_path / "fiabilidad.png")

    def coma(x):
        return f"{x:.3f}".replace(".", ",")

    assert rotulos[0] == "calibración perfecta"
    assert rotulos[1:] == [
        f"{validar.NOMBRE_MODELO[m]} — ECE {coma(celda['modelos'][m]['ece'])} (suelo "
        f"{coma(celda['modelos'][m]['suelo']['media'])}; "
        f"p95 {coma(celda['modelos'][m]['suelo']['p95'])})"
        for m in simulacion.MODELOS]


def test_el_rojo_es_exagerar_en_la_horquilla_y_en_la_pendiente(validar):
    colores = {clave: color for clave, _, color in validar.TRAMOS}
    # λ < 0: el oraculo queda mas cerca del previo que las dos combinaciones
    assert colores["bajo"] == validar.RAMPA_DIVERGENTE[0]          # pendiente < 1
    assert colores["sobre"] == validar.RAMPA_DIVERGENTE[-1]        # pendiente > 1
    assert [clave for clave, _, _ in validar.TRAMOS] == ["bajo", "contencion", "sobre"]
    # las colas llevan la tolerancia: no son «λ < 0» y «λ > 1» a secas
    assert [rotulo for _, rotulo, _ in validar.TRAMOS] == [
        "más allá del extremo conservador, en más de ε", "dentro de la horquilla",
        "más allá de la independencia, en más de ε"]


def test_las_figuras_nombran_los_modelos_y_las_clases_como_el_documento(
        validar, resultados_minimos, tmp_path, monkeypatch):
    from copiloto_triaje.validacion import informe
    assert validar.NOMBRE_MODELO == dict(informe.MODELOS)
    assert list(validar.NOMBRE_MODELO) == list(simulacion.MODELOS)
    pytest.importorskip("matplotlib")
    from matplotlib.axes import Axes
    ejes = []
    for cual in ("set_xlabel", "set_ylabel"):
        poner = getattr(Axes, cual)

        def espia(self, texto, *a, _poner=poner, **k):
            ejes.append(texto)
            return _poner(self, texto, *a, **k)

        monkeypatch.setattr(Axes, cual, espia)
    for que in validar.REJILLAS:
        validar.figura_rejilla(resultados_minimos, tmp_path / f"{que}.png", que)
    assert "ρ0 (dependencia entre los casos sin opacidad)" in ejes
    assert "ρ1 (dependencia entre los casos con opacidad)" in ejes
    assert not [e for e in ejes if "neumon" in e]


def test_sin_matplotlib_se_calcula_y_dibujar_lo_dice(
        validar, resultados_minimos, tmp_path, monkeypatch):
    import sys
    calculos = []

    def calcular_falso(replicas, procesos):
        calculos.append(replicas)
        return resultados_minimos

    monkeypatch.setitem(sys.modules, "matplotlib", None)      # como si no estuviera instalado
    monkeypatch.setattr(validar, "calcular", calcular_falso)
    orden = ["--replicas", "2", "--procesos", "1", "--salida", str(tmp_path)]
    assert validar.main(orden + ["--sin-figuras"]) == 0
    assert [p.name for p in tmp_path.iterdir()] == ["resultados_simulacion.json"]
    assert calculos == [2]
    # con figuras de una corrida anterior: pedir dibujar sale ANTES de calcular
    # y ANTES de borrarlas
    previa = tmp_path / "fiabilidad_0a.png"
    previa.write_bytes(b"de la corrida anterior")
    with pytest.raises(SystemExit, match="--sin-figuras"):
        validar.main(orden)
    assert calculos == [2]
    assert previa.read_bytes() == b"de la corrida anterior"
    with pytest.raises(SystemExit, match="extra `figuras`"):
        validar.figuras(resultados_minimos, tmp_path)
    assert previa.read_bytes() == b"de la corrida anterior"
    with pytest.raises(SystemExit, match="--sin-figuras"):
        validar.main(orden + ["--solo-documento"])
    assert [p.name for p in tmp_path.glob("*.png")] == ["fiabilidad_0a.png"]
    # y si lo que falta es el JSON, se dice eso: es lo primero que hay que arreglar
    with pytest.raises(SystemExit, match="no existe .*corre primero sin --solo-documento"):
        validar.main(["--salida", str(tmp_path / "vacia"), "--solo-documento"])
    with pytest.raises(ValueError, match="contencion"):      # se rechaza antes de importar nada
        validar.figura_rejilla(resultados_minimos, tmp_path / "x.png", "auc")


def test_si_falta_otra_cosa_no_se_dice_que_falta_matplotlib(validar, monkeypatch):
    import builtins
    importar = builtins.__import__

    def sin_numpy(nombre, *args, **kwargs):
        if nombre == "matplotlib":
            raise ModuleNotFoundError("No module named 'numpy'", name="numpy")
        return importar(nombre, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", sin_numpy)
    with pytest.raises(ModuleNotFoundError, match="numpy"):
        validar._pyplot()


def test_las_figuras_borran_las_propias_rancias_y_respetan_las_ajenas(
        validar, resultados_minimos, tmp_path):
    pytest.importorskip("matplotlib")
    rancia = tmp_path / "fiabilidad_viejo.png"
    rancia.write_bytes(b"rancio")
    ajena = tmp_path / "latencia.png"
    ajena.write_bytes(b"ajeno")
    otra = tmp_path / "resultados_simulacion.json"
    otra.write_text("{}", encoding="utf-8")
    assert validar.figuras_presentes(tmp_path) == [rancia]
    rutas = validar.figuras(resultados_minimos, tmp_path)
    assert not rancia.exists()
    assert ajena.read_bytes() == b"ajeno"
    assert otra.read_text(encoding="utf-8") == "{}"
    assert sorted(p.name for p in tmp_path.glob("*.png")) == sorted(
        NOMBRES_MINIMOS + ["latencia.png"])
    assert validar.figuras_presentes(tmp_path) == sorted(rutas)
    assert validar.figuras_presentes(tmp_path / "no_existe") == []


def test_main_dibuja_las_figuras_leyendo_el_json(
        validar, resultados_minimos, tmp_path, monkeypatch, capsys):
    pytest.importorskip("matplotlib")
    leidos = []
    leer = validar.leer_resultados

    def leer_espia(ruta):
        leidos.append(ruta)
        leido = leer(ruta)
        # lo leido NO es lo calculado: si main dibujara con lo que tiene en
        # memoria, la figura de (0,3; 0,3) seguiria saliendo
        leido["celdas"][3]["destacada"] = False
        return leido

    monkeypatch.setattr(validar, "calcular", lambda replicas, procesos: resultados_minimos)
    monkeypatch.setattr(validar, "leer_resultados", leer_espia)
    assert resultados_minimos["celdas"][3]["destacada"] is True
    assert validar.main(["--replicas", "2", "--procesos", "1", "--salida", str(tmp_path)]) == 0
    assert leidos == [tmp_path / "resultados_simulacion.json"]
    dibujadas = [n for n in NOMBRES_MINIMOS if n != "fiabilidad_r1-030_r0-030.png"]
    assert sorted(p.name for p in tmp_path.glob("*.png")) == sorted(dibujadas)
    salida = capsys.readouterr().out
    assert [linea[len("figura: "):] for linea in salida.splitlines()
            if linea.startswith("figura: ")] == [str(tmp_path / n) for n in dibujadas]


def test_main_sin_figuras_no_dibuja_nada(validar, tmp_path, capsys):
    """Corre la rejilla entera (25 celdas, sin bootstrap) por la línea de
    órdenes; `tests/test_resultados_publicados.py` la corre también, por
    `calcular`."""
    assert validar.main(["--replicas", "0", "--procesos", "1", "--salida", str(tmp_path),
                         "--sin-figuras"]) == 0
    assert [p.name for p in tmp_path.iterdir()] == ["resultados_simulacion.json"]
    assert len(validar.leer_resultados(tmp_path / "resultados_simulacion.json")["celdas"]) == 25
    assert "figura:" not in capsys.readouterr().out


# --------------------------------------------------------------------------
# El documento de analisis (tarea 6)
# --------------------------------------------------------------------------
def test_escribir_analisis_enlaza_las_figuras_con_rutas_relativas(
        validar, resultados_minimos, tmp_path):
    carpeta = tmp_path / "docs" / "validacion-semisintetica"
    figuras = [carpeta / "fiabilidad_0a.png", carpeta / "contencion_rejilla.png"]
    destino = tmp_path / "docs" / "sub" / "analisis.md"
    assert validar.escribir_analisis(resultados_minimos, figuras, destino) == destino
    crudo = destino.read_bytes()
    assert b"\r" not in crudo and crudo.endswith(b"\n")
    texto = crudo.decode("utf-8")
    assert texto.startswith("# Validación de la combinación de clínica e imagen: "
                            "simulación semisintética (SP5)\n")
    assert "](../validacion-semisintetica/fiabilidad_0a.png)" in texto
    assert "](../validacion-semisintetica/contencion_rejilla.png)" in texto
    assert texto.count(".png") == 2
    assert "\\" not in texto and str(tmp_path) not in texto
    # esas dos figuras no existen: no llevan la huella, y el documento lo avisa
    assert ("**Aviso: ninguna de las 2 figuras enlazadas lleva la huella de los "
            "resultados de este documento** (`fiabilidad_0a` y `contencion_rejilla`)"
            ) in texto
    sin = validar.escribir_analisis(resultados_minimos, [], tmp_path / "sin.md")
    assert ".png" not in sin.read_text(encoding="utf-8")


def test_main_escribe_el_analisis_leyendo_el_json(
        validar, resultados_minimos, tmp_path, monkeypatch, capsys, analisis_fuera_del_repo):
    pytest.importorskip("matplotlib")
    monkeypatch.setattr(validar, "calcular", lambda replicas, procesos: resultados_minimos)
    salida = tmp_path / "docs" / "validacion-semisintetica"
    analisis = tmp_path / "docs" / "analisis.md"
    assert validar.main(["--replicas", "2", "--procesos", "1", "--salida", str(salida),
                         "--analisis", str(analisis)]) == 0
    texto = analisis.read_text(encoding="utf-8")
    assert [linea for linea in texto.splitlines() if linea.startswith("![")] == [
        f"![{titulo} (simulación semisintética)](validacion-semisintetica/{nombre})"
        for titulo, nombre in (
            ("Fiabilidad por deciles, celda 0A", "fiabilidad_0a.png"),
            ("Fiabilidad por deciles, celda (0,3; 0,3)", "fiabilidad_r1-030_r0-030.png"),
            ("El oráculo frente a la horquilla, por celda y lado", "horquilla_por_celda.png"),
            ("Contención del oráculo en la horquilla, por celda", "contencion_rejilla.png"),
            ("Pendiente de la independencia, por celda", "pendiente_rejilla.png"))]
    assert capsys.readouterr().out.splitlines()[-1] == f"análisis: {analisis}"
    assert not analisis_fuera_del_repo.exists()
    # recien dibujadas de estos resultados: todas llevan su huella
    assert ("Las 5 figuras enlazadas llevan la huella de los resultados de este "
            "documento.") in texto
    assert "Aviso" not in texto
    # sin --analisis va al de por defecto (aqui, desviado a una carpeta temporal)
    assert validar.main(["--replicas", "2", "--procesos", "1", "--salida", str(salida),
                         "--sin-figuras"]) == 0
    assert analisis_fuera_del_repo.is_file()


def test_solo_documento_sin_json_sale_con_un_mensaje(validar, tmp_path, monkeypatch):
    monkeypatch.setattr(validar, "calcular", lambda *a, **k: pytest.fail("ha recalculado"))
    analisis = tmp_path / "analisis.md"
    with pytest.raises(SystemExit) as salida:
        validar.main(["--solo-documento", "--salida", str(tmp_path),
                      "--analisis", str(analisis)])
    assert "resultados_simulacion.json" in str(salida.value)
    assert "sin --solo-documento" in str(salida.value)
    assert not analisis.exists()
    assert list(tmp_path.iterdir()) == []


def test_solo_documento_escribe_el_documento_sin_recalcular(
        validar, resultados_minimos, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(validar, "calcular", lambda *a, **k: pytest.fail("ha recalculado"))
    otro = json.loads(json.dumps(resultados_minimos))
    otro["insumos"]["placas"] = 9876
    ruta = validar.escribir_resultados(otro, tmp_path / "resultados_simulacion.json")
    antes = ruta.read_bytes()
    ajena = tmp_path / "fiabilidad_0a.png"
    ajena.write_bytes(b"de una corrida anterior")
    analisis = tmp_path / "analisis.md"
    assert validar.main(["--solo-documento", "--sin-figuras", "--salida", str(tmp_path),
                         "--analisis", str(analisis)]) == 0
    assert ruta.read_bytes() == antes
    texto = analisis.read_text(encoding="utf-8")
    assert "9 876" in texto                                   # leido del JSON
    assert "](fiabilidad_0a.png)" in texto                    # las figuras que hubiera
    assert ("**Aviso: la única figura enlazada no lleva la huella de los resultados de "
            "este documento** (`fiabilidad_0a`)") in texto
    assert ajena.read_bytes() == b"de una corrida anterior"
    salida = capsys.readouterr().out
    assert "resultados:" not in salida and "figura:" not in salida
    assert salida.splitlines() == [f"análisis: {analisis}"]
