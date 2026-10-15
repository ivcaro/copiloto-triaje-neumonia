# -*- coding: utf-8 -*-
"""La capa del curso para el modelo (SP5-C2): `src/model.py`, `src/train.py` y `src/evaluate.py`.

QUÉ VIGILA
- `model.py` y `train.py`: que reexportan, objeto por objeto, lo de `copiloto_triaje` y no
  definen más que un `main` (el de `train.py` llama a `scripts/entrenar_local.py`); que las
  cifras del despliegue que `model.py` lleva son las de `servidor/docker-compose.yml` y
  `app/generar_metricas.py` (una sola fuente de verdad, vigilada); y, con los pesos, que son
  los de la huella de `app/assets/metricas.json` y que cargan.
- `evaluate.py`: que sus números son los de `app/assets/metricas.json` (global, 13 subgrupos y
  el efecto del umbral por vista: igualdad exacta), que el JSON que versiona `results/` es lo
  que sale de las puntuaciones congeladas, que no lleva ni una fila por paciente, que sus tres
  figuras existen y están bien hechas, y qué pasa cuando falta algo.

Las pruebas que recalculan desde `crudas_prueba.csv` se SALTAN, diciéndolo, donde las
puntuaciones no están (el repositorio público lleva el JSON y las figuras, no las puntuaciones por
placa); las que comparan los JSON versionados corren siempre. Las que cargan los pesos se saltan
sin ellos. Importa torch y scikit-learn: corre en la imagen Linux de pruebas (README, «Pruebas»).
"""
import inspect
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:      # `src` es un paquete de la raíz, no de `pythonpath`
    sys.path.insert(0, str(REPO))

import torch  # noqa: E402
from copiloto_triaje.modelo import arquitectura, entrenamiento, evaluacion  # noqa: E402
from copiloto_triaje.servicio import calibracion, inferencia  # noqa: E402

from src import evaluate, model, train, utils  # noqa: E402

PUBLICADAS = REPO / "app" / "assets" / "metricas.json"
RESULTADOS = REPO / "results"
JSON_DE_PRUEBA = RESULTADOS / "metrics" / "metricas_prueba.json"
FIGURAS = ("roc_prueba.png", "calibracion.png", "subgrupos.png")
CRUDAS = utils.PUNTUACIONES_DE_PRUEBA
COMPOSE = REPO / "servidor" / "docker-compose.yml"

sin_puntuaciones = pytest.mark.skipif(
    not CRUDAS.is_file(),
    reason="no están las puntuaciones congeladas de prueba (docs/validacion-semisintetica/"
           "crudas_prueba.csv): sin ellas no se puede recalcular, y se queda sin comprobar "
           "que results/ sale de ellas")
sin_pesos = pytest.mark.skipif(
    not utils.PESOS_DESPLEGADOS.is_file(),
    reason="no están los pesos (models/pesos_modelo_cpu.pt o servidor/pesos_modelo_cpu.pt; "
           "ver models/README.md): se queda sin comprobar que cargan y que son los medidos")

# Las claves de `metricas.json` que `metricas_prueba.json` repite tal cual (la fecha cambia).
CLAVES_IGUALES = ("pesos_sha256", "puntuaciones_sha256", "umbral", "umbrales_por_vista",
                  "global", "subgrupos", "umbral_por_vista_en_prueba")


def _json(ruta):
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# model.py y train.py: sin lógica propia
# --------------------------------------------------------------------------
@pytest.mark.parametrize("nombre,origen", [
    ("construir_modelo", arquitectura), ("descongelar_para_ajuste", arquitectura),
    ("descongelar_todo", arquitectura), ("contar_parametros_entrenables", arquitectura),
    ("Calibrador", calibracion), ("ajustar_calibrador", calibracion),
    ("Motor", inferencia), ("ErrorDeInferencia", inferencia)])
def test_model_reexporta_el_objeto_del_paquete(nombre, origen):
    assert getattr(model, nombre) is getattr(origen, nombre)
    assert nombre in model.__all__


@pytest.mark.parametrize("nombre,origen", [
    ("entrenar", entrenamiento), ("evaluar_epoca", entrenamiento),
    ("exportar_pesos_cpu", entrenamiento), ("fijar_semillas", entrenamiento),
    ("NOMBRE_PESOS_CPU", entrenamiento), ("elegir_umbral", evaluacion),
    ("metricas_en_umbral", evaluacion)])
def test_train_reexporta_el_objeto_del_paquete(nombre, origen):
    assert getattr(train, nombre) is getattr(origen, nombre)
    assert nombre in train.__all__


def test_las_funciones_que_definen_model_y_train_son_pocas_y_finas():
    """Lo único propio de `train.py` es `main`; lo de `model.py`, atajos de una línea o dos
    (cargar el motor, comprobar la huella) y las constantes del despliegue."""
    propias_train = [n for n in train.__all__
                     if inspect.isfunction(getattr(train, n))
                     and getattr(train, n).__module__ == "src.train"]
    assert propias_train == ["main"]
    for nombre in ("comprobar_pesos", "cargar_motor", "cargar_modelo", "resumen"):
        lineas = [x for x in inspect.getsource(getattr(model, nombre)).splitlines()
                  if x.strip() and not x.strip().startswith(('"""', '#'))]
        assert len(lineas) < 40, nombre
    assert "copiloto_triaje" in model.__doc__ and "copiloto_triaje" in train.__doc__
    assert "scripts/entrenar_local.py" in train.__doc__


def test_el_main_de_train_llama_al_guion_de_entrenamiento(capsys):
    with pytest.raises(SystemExit) as salida:
        train.main(["--help"])
    assert salida.value.code == 0
    texto = capsys.readouterr().out
    assert "python -m src.train" in texto
    for opcion in ("--raiz", "--arquitectura", "--tam-imagen", "--lote", "--epocas-cabeza",
                   "--epocas-ajuste", "--salida", "--reanudar", "--trabajadores"):
        assert opcion in texto


def test_el_main_de_train_rechaza_una_arquitectura_que_no_existe(capsys, tmp_path):
    with pytest.raises(SystemExit) as salida:
        train.main(["--raiz", str(tmp_path), "--arquitectura", "resnet_inventada"])
    assert salida.value.code == 2
    assert "no soportada" in capsys.readouterr().err


# --------------------------------------------------------------------------
# model.py: el modelo desplegado
# --------------------------------------------------------------------------
def _de_compose(clave: str) -> float:
    coincidencias = re.findall(rf'^\s+{clave}:\s*"([0-9.]+)"', COMPOSE.read_text(encoding="utf-8"),
                               re.M)
    assert len(coincidencias) == 1, (clave, coincidencias)
    return float(coincidencias[0])


def test_las_cifras_del_despliegue_son_las_del_compose_y_las_de_las_metricas():
    assert model.UMBRAL == _de_compose("UMBRAL")
    assert model.AUC_VALIDACION == _de_compose("AUC_VALIDACION")
    assert model.PREVALENCIA_LOCAL == _de_compose("PREVALENCIA_LOCAL")
    publicadas = _json(PUBLICADAS)
    assert model.UMBRAL == publicadas["umbral"]
    por_defecto = {n: p.default for n, p in inspect.signature(inferencia.Motor.cargar).parameters.items()}
    assert model.ARQUITECTURA_DESPLEGADA == por_defecto["arquitectura"]
    assert model.TAM_IMAGEN_DESPLEGADO == por_defecto["tam_imagen"]


def test_la_corrida_desplegada_es_de_la_que_sale_el_calibrador():
    calibrador = _json(utils.CALIBRADOR_DESPLEGADO)
    assert calibrador["procedencia"] == model.CORRIDA_DESPLEGADA
    assert model.CORRIDA_DESPLEGADA.startswith(f"{model.ARQUITECTURA_DESPLEGADA}_"
                                               f"{model.TAM_IMAGEN_DESPLEGADO}px")


def test_el_readme_de_models_lleva_la_huella_y_las_cifras_de_las_metricas():
    texto = (REPO / "models" / "README.md").read_text(encoding="utf-8")
    publicadas = _json(PUBLICADAS)
    assert publicadas["pesos_sha256"] in texto
    assert model.CORRIDA_DESPLEGADA in texto
    assert "servidor/calibrador.json" in texto
    assert "v1.0" in texto and "se publican como descarga del release" in texto
    for cifra in (f"{model.UMBRAL}".replace(".", ","), f"{model.AUC_VALIDACION}".replace(".", ","),
                  f"{model.PREVALENCIA_LOCAL}".replace(".", ",")):
        assert cifra in texto, cifra


def test_la_red_desplegada_tiene_una_salida_a_320_px():
    red = model.construir_modelo(model.ARQUITECTURA_DESPLEGADA, congelar_backbone=False,
                                 preentrenado=False).eval()
    with torch.no_grad():
        salida = red(torch.randn(1, 3, model.TAM_IMAGEN_DESPLEGADO, model.TAM_IMAGEN_DESPLEGADO))
    assert salida.shape == (1, 1)


def test_el_resumen_del_modelo_tiene_lo_que_dice_el_readme(tmp_path):
    resumen = model.resumen(tmp_path / "no_estan.pt")
    assert resumen["corrida"] == model.CORRIDA_DESPLEGADA
    assert resumen["umbral"] == 0.4258 and resumen["auc_validacion"] == 0.8827
    assert 3_500_000 < resumen["parametros"] < 4_500_000
    assert resumen["pesos"]["sha256"] is None and "models/README.md" in resumen["pesos"]["nota"]


def test_unos_pesos_que_no_estan_se_dicen_con_el_camino_para_conseguirlos(tmp_path):
    with pytest.raises(FileNotFoundError, match=r"models/README\.md"):
        model.comprobar_pesos(tmp_path / "no_estan.pt")
    with pytest.raises(FileNotFoundError, match=r"models/README\.md"):
        model.cargar_motor(tmp_path / "no_estan.pt")


def test_unos_pesos_que_no_son_los_medidos_se_rechazan(tmp_path):
    otros = tmp_path / "otros.pt"
    otros.write_bytes(b"no son los pesos")
    with pytest.raises(ValueError, match="no son los del modelo desplegado"):
        model.comprobar_pesos(otros)
    with pytest.raises(ValueError):
        model.resumen(otros)          # un ValueError no se disfraza de «no están»


@sin_pesos
def test_los_pesos_son_los_medidos_y_cargan_en_el_motor_desplegado():
    assert model.comprobar_pesos() == _json(PUBLICADAS)["pesos_sha256"]
    motor = model.cargar_motor()
    assert isinstance(motor, model.Motor)
    assert (motor.umbral, motor.auc_validacion, motor.prevalencia_local) == (
        model.UMBRAL, model.AUC_VALIDACION, model.PREVALENCIA_LOCAL)
    assert motor.tam_imagen == model.TAM_IMAGEN_DESPLEGADO
    red = model.cargar_modelo()
    assert not red.training
    with torch.no_grad():
        assert red(torch.zeros(1, 3, 320, 320)).shape == (1, 1)


@sin_pesos
def test_el_main_de_model_imprime_el_resumen_en_json(capsys):
    assert model.main([]) == 0
    resumen = json.loads(capsys.readouterr().out)
    assert resumen["pesos"]["coincide_con_metricas_json"] is True
    assert resumen["pesos"]["sha256"] == _json(PUBLICADAS)["pesos_sha256"]


def test_el_main_de_model_no_acepta_argumentos(capsys):
    assert model.main(["--algo"]) == 2
    assert "uso:" in capsys.readouterr().err


# --------------------------------------------------------------------------
# evaluate.py: sus números son los de la app
# --------------------------------------------------------------------------
def test_el_json_versionado_repite_las_cifras_de_la_app_sin_cambiar_una():
    """LA prueba de `evaluate.py`: global, 13 subgrupos y el efecto del umbral por vista de
    `results/metrics/metricas_prueba.json` son, valor por valor, los de `app/assets/metricas.json`."""
    de_prueba, de_la_app = _json(JSON_DE_PRUEBA), _json(PUBLICADAS)
    for clave in CLAVES_IGUALES:
        assert de_prueba[clave] == de_la_app[clave], clave
    assert de_prueba["global"]["n"] == 3811 and de_prueba["global"]["positivos"] == 844
    assert len(de_prueba["subgrupos"]) == 13
    assert set(de_prueba) - set(de_la_app) == {"calibracion"}
    assert set(de_la_app) - set(de_prueba) == set()


def test_el_json_versionado_no_lleva_ninguna_fila_por_paciente():
    texto = JSON_DE_PRUEBA.read_text(encoding="utf-8")
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", texto)
    assert "patientId" not in texto and "archivo" not in texto
    assert "NaN" not in texto and "Infinity" not in texto
    for ruta in ("C:\\", "C:/", "/home/", "/Users/", "\\\\"):
        assert ruta not in texto, ruta

    def listas(valor):
        if isinstance(valor, list):
            yield valor
            for v in valor:
                yield from listas(v)
        elif isinstance(valor, dict):
            for v in valor.values():
                yield from listas(v)

    assert max(len(lista) for lista in listas(_json(JSON_DE_PRUEBA))) <= 20


def test_la_calibracion_del_json_dice_lo_que_el_calibrador_corrige():
    cal = _json(JSON_DE_PRUEBA)["calibracion"]
    n = _json(JSON_DE_PRUEBA)["global"]["n"]
    assert cal["grupos"] == 10
    assert cal["prevalencia_observada"] == pytest.approx(844 / n, abs=1e-6)
    for clave in ("cruda", "calibrada"):
        assert sum(g["n"] for g in cal[clave]["fiabilidad"]) == n
        assert len(cal[clave]["fiabilidad"]) == 10
    # la puntuación cruda no es una probabilidad: el calibrador la acerca a la diagonal
    assert cal["calibrada"]["ece"] < cal["cruda"]["ece"] / 3
    assert cal["calibrada"]["brier"] < cal["cruda"]["brier"]
    assert abs(cal["calibrada"]["pendiente"] - 1) < 0.1
    assert abs(cal["calibrada"]["intercepto"]) < abs(cal["cruda"]["intercepto"])


def test_las_figuras_versionadas_son_tres_png_bien_hechos():
    from PIL import Image
    for nombre in FIGURAS:
        ruta = RESULTADOS / "figures" / nombre
        assert ruta.is_file(), nombre
        with Image.open(ruta) as imagen:
            assert imagen.format == "PNG"
            assert imagen.width >= 1000 and imagen.height >= 1000, nombre
            assert imagen.info["dpi"][0] == pytest.approx(evaluate.DPI, abs=1), nombre
            assert re.fullmatch(r"matplotlib \d+(\.\w+)+", imagen.info["Software"]), nombre
            assert "http" not in " ".join(str(v) for v in imagen.info.values()), nombre
            assert imagen.info["Title"], nombre
    assert sorted(p.name for p in (RESULTADOS / "figures").glob("*.png")) == sorted(FIGURAS)


def test_el_json_publicado_y_la_pagina_de_los_resultados_se_corresponden():
    texto = (RESULTADOS / "README.md").read_text(encoding="utf-8")
    for nombre in ("metricas_prueba.json",) + FIGURAS:
        assert nombre in texto, nombre
    assert "python -m src.evaluate" in texto
    informes = (RESULTADOS / "reports" / "README.md").read_text(encoding="utf-8")
    for enlace in ("docs/validacion-semisintetica/acta-h7.md", "docs/validacion-semisintetica-sp5.md"):
        assert enlace in informes
        assert (REPO / enlace).is_file(), enlace


# --------------------------------------------------------------------------
# evaluate.py: lo que sale de las puntuaciones congeladas
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def evaluado():
    return evaluate.evaluar(generado="2000-01-01")


@sin_puntuaciones
def test_recalcular_da_las_cifras_de_la_app_y_las_del_json_versionado(evaluado):
    de_la_app, versionado = _json(PUBLICADAS), _json(JSON_DE_PRUEBA)
    for clave in CLAVES_IGUALES:
        assert evaluado[clave] == de_la_app[clave] == versionado[clave], clave
    assert evaluado["generado"] == "2000-01-01"
    # la calibración se compara con holgura de 1e-5: las iteraciones de Newton y el redondeo
    # a 6 decimales pueden bailar una cifra entre versiones de BLAS
    esperado, obtenido = versionado["calibracion"], evaluado["calibracion"]
    for clave in ("cruda", "calibrada"):
        for medida in ("brier", "ece", "pendiente", "intercepto"):
            assert obtenido[clave][medida] == pytest.approx(esperado[clave][medida], abs=1e-5)
        for a, b in zip(obtenido[clave]["fiabilidad"], esperado[clave]["fiabilidad"]):
            assert a["n"] == b["n"]
            assert a["p_media"] == pytest.approx(b["p_media"], abs=1e-5)
            assert a["observada"] == pytest.approx(b["observada"], abs=1e-5)


@sin_puntuaciones
def test_el_umbral_llega_al_guion_de_las_metricas(evaluado):
    con_otro = evaluate.evaluar(umbral=0.7, generado="2000-01-01")
    assert con_otro["umbral"] == 0.7
    assert con_otro["global"]["recall"] < evaluado["global"]["recall"]
    assert con_otro["global"]["especificidad"] > evaluado["global"]["especificidad"]
    assert con_otro["global"]["auc"] == evaluado["global"]["auc"]     # no depende del umbral


@sin_puntuaciones
def test_unos_pesos_distintos_de_los_de_las_puntuaciones_se_rechazan(tmp_path):
    otros = tmp_path / "otros.pt"
    otros.write_bytes(b"otros pesos")
    with pytest.raises(evaluate.ErrorDeEvaluacion, match="no son con los que se generaron"):
        evaluate.evaluar(ruta_pesos=otros)


@sin_puntuaciones
def test_el_main_sin_figuras_escribe_solo_el_json_y_es_el_versionado(tmp_path):
    assert evaluate.main(["--salida", str(tmp_path), "--sin-figuras"]) == 0
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()
                  ) == ["metrics/metricas_prueba.json"]
    escrito = _json(tmp_path / "metrics" / "metricas_prueba.json")
    versionado = _json(JSON_DE_PRUEBA)
    for clave in CLAVES_IGUALES:
        assert escrito[clave] == versionado[clave], clave
    texto = (tmp_path / "metrics" / "metricas_prueba.json").read_text(encoding="utf-8")
    assert texto.endswith("}\n") and "\r" not in texto


@sin_puntuaciones
def test_el_main_con_figuras_dibuja_las_tres(tmp_path):
    pytest.importorskip("matplotlib")
    from PIL import Image
    assert evaluate.main(["--salida", str(tmp_path)]) == 0
    for nombre in FIGURAS:
        with Image.open(tmp_path / "figures" / nombre) as imagen:
            assert imagen.width >= 1000 and imagen.height >= 1000
            assert imagen.info["Title"]
    assert sorted(p.name for p in (tmp_path / "figures").iterdir()) == sorted(FIGURAS)


def test_sin_las_puntuaciones_el_main_lo_dice_y_no_escribe_nada(tmp_path, capsys):
    salida = tmp_path / "resultados"
    assert evaluate.main(["--crudas", str(tmp_path / "no_estan.csv"), "--salida", str(salida),
                          "--sin-figuras"]) == 1
    error = capsys.readouterr().err
    assert "faltan las puntuaciones congeladas de prueba" in error
    assert str(tmp_path) not in error                  # la ruta sale relativa o solo el nombre
    assert not salida.exists()


def test_el_main_lista_sus_opciones_con_help(capsys):
    with pytest.raises(SystemExit) as salida:
        evaluate.main(["--help"])
    assert salida.value.code == 0
    texto = capsys.readouterr().out
    assert "python -m src.evaluate" in texto
    for opcion in ("--crudas", "--calibrador", "--pesos", "--salida", "--umbral",
                   "--umbral-pa", "--umbral-ap", "--sin-figuras"):
        assert opcion in texto


def test_evaluate_no_reescribe_las_cuentas_que_ya_hace_el_guion_de_la_app():
    """`evaluate.py` llama a `app/generar_metricas.py` y a `copiloto_triaje.validacion`: ni el
    AUC, ni Wilson, ni los subgrupos, ni la ECE se vuelven a escribir aquí."""
    funciones = {nombre for nombre, objeto in vars(evaluate).items()
                 if inspect.isfunction(objeto) and objeto.__module__ == "src.evaluate"}
    prohibidas = {"auc", "wilson", "marcadas", "calcular", "generar", "ece", "brier", "fiabilidad"}
    assert funciones.isdisjoint(prohibidas), funciones & prohibidas
    guion = utils.cargar_guion("app/generar_metricas.py")
    assert evaluate._guion_de_metricas() is guion
    assert [s.nombre for s in guion.SUBGRUPOS] == [f["nombre"] for f in _json(JSON_DE_PRUEBA)["subgrupos"]]
    # y el barrido de `test_informe.py` (ningún `import matplotlib` en `src/`) tampoco lo ve
    fuente = Path(evaluate.__file__).read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|from)\s+matplotlib\b", fuente, re.M)
