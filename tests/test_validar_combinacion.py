"""scripts/validar_combinacion.py: la rejilla, el JSON y sus huellas."""
import json

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
    titulos = {}
    for ruta in rutas:
        with Image.open(ruta) as imagen:
            titulos[ruta.name] = imagen.info["Title"]
    assert "0A" in titulos["fiabilidad_0a.png"]
    assert "(0,3; 0,3)" in titulos["fiabilidad_r1-030_r0-030.png"]
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
    with pytest.raises(ValueError, match="contencion"):
        validar.figura_rejilla(resultados_minimos, tmp_path / "cinco.png", "auc")
    assert not (tmp_path / "cinco.png").exists()


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
        return leer(ruta)

    monkeypatch.setattr(validar, "calcular", lambda replicas, procesos: resultados_minimos)
    monkeypatch.setattr(validar, "leer_resultados", leer_espia)
    assert validar.main(["--replicas", "2", "--procesos", "1", "--salida", str(tmp_path)]) == 0
    assert leidos == [tmp_path / "resultados_simulacion.json"]
    assert sorted(p.name for p in tmp_path.glob("*.png")) == sorted(NOMBRES_MINIMOS)
    salida = capsys.readouterr().out
    assert [linea[len("figura: "):] for linea in salida.splitlines()
            if linea.startswith("figura: ")] == [str(tmp_path / n) for n in NOMBRES_MINIMOS]


def test_main_sin_figuras_no_dibuja_nada(validar, tmp_path, capsys):
    """La unica prueba que corre la rejilla entera (25 celdas, sin bootstrap)."""
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
    assert ajena.read_bytes() == b"de una corrida anterior"
    salida = capsys.readouterr().out
    assert "resultados:" not in salida and "figura:" not in salida
    assert salida.splitlines() == [f"análisis: {analisis}"]
