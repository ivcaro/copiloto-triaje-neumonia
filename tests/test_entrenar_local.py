"""Pruebas del guion de entrenamiento local (scripts/entrenar_local.py).

No comprueban que el modelo aprenda -eso no lo decide el script- sino lo que
el script promete: fallar al inicio cuando la configuracion o los datos no
sirven, avisar de cada epoca con una estimacion de lo que falta, y dejar un
reporte con el bloque "corrida" completo, que es lo unico que hace comparables
dos corridas de arquitecturas distintas.

Todo corre sobre un conjunto sintetico diminuto y una sola epoca: la pieza que
se vigila es el guion, no el entrenamiento, que ya tiene sus propias pruebas.
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch
from PIL import Image

from copiloto_triaje.config import ARQUITECTURAS

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "entrenar_local.py"

LADO = 32  # las imagenes sinteticas y el --tam-imagen de las pruebas
# Tamanos DISTINTOS a proposito, y mas abajo tambien contenidos distintos.
# Con val y test del mismo tamano y la misma pinta, la clase de error mas cara
# que este script puede cometer -confundir validacion con prueba, o peor,
# elegir el umbral sobre el conjunto de prueba- no la ve ninguna prueba: la
# suite aprueba igual el codigo correcto y el que filtra datos.
TAMANOS = {"train": 12, "val": 8, "test": 10}

# El contrato del bloque que hace comparables dos reportes. Si una clave
# desaparece, el reporte sigue siendo valido por si solo pero deja de servir
# para lo que se escribio: contrastarlo con el de otra arquitectura.
CLAVES_CORRIDA = {
    "nombre", "arquitectura", "tam_imagen", "lote", "epocas",
    "ajuste_fino_completo", "scheduler_coseno", "paciencia", "edad",
    "n_val", "n_test", "dispositivo", "segundos_entrenamiento",
}


def _cargar_script():
    """Importa scripts/entrenar_local.py como modulo.

    Los scripts no viven bajo src/, asi que no hay un import normal que los
    alcance. Se carga por ruta para poder llamar a `main()` en este mismo
    proceso: por subprocess, cada prueba pagaria el arranque de torch y no
    habria forma de sustituir la construccion del modelo.
    """
    especificacion = importlib.util.spec_from_file_location("entrenar_local", SCRIPT)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


entrenar_local = _cargar_script()


class ModeloMinimo(torch.nn.Module):
    """Un lineal sobre la media de la imagen: entrena en milisegundos en CPU.

    Mismo recurso que `ModeloTrivial` en test_entrenamiento.py. `features`
    existe porque `descongelar_todo` y `descongelar_para_ajuste` lo buscan si
    la corrida llega a la fase de ajuste fino.
    """

    def __init__(self):
        super().__init__()
        self.capa = torch.nn.Linear(1, 1)
        self.features = torch.nn.ModuleList([torch.nn.Identity()])

    def forward(self, x):
        return self.capa(x.mean(dim=(1, 2, 3), keepdim=False).unsqueeze(1))


@pytest.fixture
def sin_descarga_de_pesos(monkeypatch):
    """Sustituye la red real por `ModeloMinimo`.

    `construir_modelo` descarga decenas de MB de pesos de ImageNet y entrena
    una red entera. Ninguna de las dos cosas dice nada sobre lo que estas
    pruebas vigilan, y las dos las harian lentas y dependientes de la red.
    """
    monkeypatch.setattr(entrenar_local, "construir_modelo",
                        lambda *args, **kwargs: ModeloMinimo())


@pytest.fixture
def raiz_preparada(tmp_path):
    """Una raiz con la misma forma que deja preparar_datos.py: png/ y
    manifiestos/ con train.csv, val.csv y test.csv.

    Las tres particiones llevan mitad de positivos: `elegir_umbral` y el AUC
    necesitan las dos clases presentes, y con una sola clase el script fallaria
    por el conjunto de datos y no por lo que se esta probando.
    """
    generador = np.random.default_rng(0)
    dir_png = tmp_path / "png"
    dir_png.mkdir()
    dir_manifiestos = tmp_path / "manifiestos"
    dir_manifiestos.mkdir()

    for particion, cuantas in TAMANOS.items():
        filas = []
        for i in range(cuantas):
            etiqueta = i % 2
            imagen = generador.integers(0, 120, (LADO, LADO), dtype=np.uint8)
            if etiqueta:
                imagen[8:24, 8:24] = 240  # los positivos llevan una mancha clara
            nombre = f"{particion}_{i:02d}.png"
            Image.fromarray(imagen).save(dir_png / nombre)
            filas.append({"patientId": f"{particion}{i:02d}",
                          "archivo_png": nombre, "etiqueta": etiqueta,
                          "semilla": 42})
        pd.DataFrame(filas).to_csv(dir_manifiestos / f"{particion}.csv", index=False)
    return tmp_path


def _argumentos(raiz: Path, salida: Path, *extra: str) -> list[str]:
    """Una corrida minima: una epoca de cabeza, ninguna de ajuste y sin
    procesos de carga (num_workers=0 evita levantar procesos en Windows)."""
    return ["--raiz", str(raiz), "--salida", str(salida),
            "--tam-imagen", str(LADO), "--lote", "4",
            "--epocas-cabeza", "1", "--epocas-ajuste", "0",
            "--trabajadores", "0", *extra]


def test_arquitectura_invalida_falla_al_inicio_y_lista_las_validas(tmp_path, capsys):
    """La raiz que se pasa no tiene ni png/ ni manifiestos/: si la validacion
    de la arquitectura ocurriera despues de mirar el disco, este caso fallaria
    con FileNotFoundError y no con el mensaje que nombra las opciones."""
    with pytest.raises(SystemExit) as salida_del_proceso:
        entrenar_local.main(["--raiz", str(tmp_path), "--arquitectura", "resnet50"])

    assert salida_del_proceso.value.code == 2
    mensaje = capsys.readouterr().err
    assert "resnet50" in mensaje
    for arquitectura in ARQUITECTURAS:
        assert arquitectura in mensaje, f"el mensaje no nombra {arquitectura}"


def test_sin_manifiestos_falla_antes_de_entrenar(tmp_path):
    """Fallar al inicio, no a las tres horas. El mensaje tiene que citar la
    ruta buscada y el script que la produce, porque la causa real casi siempre
    es que --raiz apunta a otra carpeta."""
    (tmp_path / "png").mkdir()
    (tmp_path / "manifiestos").mkdir()

    with pytest.raises(FileNotFoundError) as error:
        entrenar_local.main(_argumentos(tmp_path, tmp_path / "corrida"))

    mensaje = str(error.value)
    assert str(tmp_path / "manifiestos") in mensaje
    assert "train.csv" in mensaje
    assert "preparar_datos.py" in mensaje


def test_sin_directorio_de_png_falla_antes_de_entrenar(tmp_path):
    with pytest.raises(FileNotFoundError) as error:
        entrenar_local.main(_argumentos(tmp_path, tmp_path / "corrida"))

    mensaje = str(error.value)
    assert str(tmp_path / "png") in mensaje
    assert "preparar_datos.py" in mensaje


def test_la_corrida_escribe_los_entregables_con_el_bloque_corrida_completo(
        raiz_preparada, tmp_path, sin_descarga_de_pesos):
    salida = tmp_path / "corrida_de_prueba"
    codigo = entrenar_local.main(
        _argumentos(raiz_preparada, salida,
                    "--arquitectura", "mobilenet_v3_large"))
    assert codigo == 0

    for nombre in ("reporte_metricas.json", "reporte_metricas.md", "curva_roc.svg"):
        assert (salida / nombre).is_file(), f"no se escribio {nombre}"

    reporte = json.loads((salida / "reporte_metricas.json").read_text(encoding="utf-8"))
    corrida = reporte["corrida"]
    faltantes = CLAVES_CORRIDA - set(corrida)
    assert not faltantes, f"al bloque 'corrida' le faltan claves: {sorted(faltantes)}"

    # Lo que se pidio por linea de comandos tiene que ser lo que quede escrito:
    # un bloque que describa otra configuracion es peor que no tenerlo.
    assert corrida["nombre"] == salida.name
    assert corrida["arquitectura"] == "mobilenet_v3_large"
    assert corrida["tam_imagen"] == LADO
    assert corrida["lote"] == 4
    assert corrida["epocas"] == [1, 0]
    assert corrida["n_val"] == TAMANOS["val"]
    assert corrida["n_test"] == TAMANOS["test"]
    assert corrida["dispositivo"] in ("cpu", "cuda")
    assert corrida["segundos_entrenamiento"] >= 0

    # Y el resto del reporte, que es lo que se compara junto al bloque.
    # El umbral que se congelo en validacion es el mismo con el que se
    # midio la prueba: si no coincidieran, el reporte estaria describiendo
    # un punto de operacion que nunca se evaluo.
    assert reporte["umbral"] == reporte["prueba"]["umbral"]
    assert reporte["regla"].startswith(("paso_", "sin_umbral"))
    assert len(reporte["historial"]) == 1
    assert {"recall", "especificidad", "auc"} <= set(reporte["prueba"])


def test_el_veredicto_se_imprime_para_los_tres_criterios(
        raiz_preparada, tmp_path, sin_descarga_de_pesos, capsys):
    """Despues de horas de espera, lo primero que se quiere saber es si la
    corrida cumple; que este en el JSON no basta si hay que ir a buscarlo."""
    entrenar_local.main(_argumentos(raiz_preparada, tmp_path / "corrida"))

    lineas = [linea for linea in capsys.readouterr().out.splitlines()
              if linea.startswith(("OK ", "NO "))]
    assert len(lineas) == 3

    # No basta con que haya tres lineas: hay que exigir que el OK/NO
    # corresponda a la comparacion con el minimo. Sin esto, invertir el
    # operador -anunciar OK a una corrida con recall 0,40- pasa la prueba.
    reporte = json.loads((tmp_path / "corrida" / "reporte_metricas.json")
                         .read_text(encoding="utf-8"))
    prueba = reporte["prueba"]
    esperado = {
        "recall": prueba["recall"] >= entrenar_local.Config.recall_minimo,
        "especificidad": (prueba["especificidad"]
                          >= entrenar_local.Config.especificidad_minima),
        "AUC": prueba["auc"] >= entrenar_local.AUC_MINIMO,
    }
    for etiqueta, cumple in esperado.items():
        linea = next(x for x in lineas if etiqueta in x)
        assert linea.startswith("OK " if cumple else "NO "), linea

    # Y que el minimo impreso sea el del baremo, no cualquier numero: con
    # AUC_MINIMO = 0.0 el script anunciaria OK mientras el Markdown dice que
    # no cumple.
    linea_auc = next(x for x in lineas if "AUC" in x)
    assert f"{entrenar_local.AUC_MINIMO}" in linea_auc
    assert entrenar_local.AUC_MINIMO == 0.85


def test_reanudar_no_repite_las_epocas_ya_hechas(
        raiz_preparada, tmp_path, sin_descarga_de_pesos, capsys):
    """Relanzar una corrida ya terminada no la vuelve a entrenar: es la mitad
    util de --reanudar, porque el caso real es un proceso que murio a media
    tarde y hay que retomar sin perder lo hecho."""
    salida = tmp_path / "corrida"
    entrenar_local.main(_argumentos(raiz_preparada, salida))
    primero = json.loads((salida / "reporte_metricas.json").read_text(encoding="utf-8"))
    capsys.readouterr()

    entrenar_local.main(_argumentos(raiz_preparada, salida, "--reanudar"))
    segundo = json.loads((salida / "reporte_metricas.json").read_text(encoding="utf-8"))
    segunda_salida = capsys.readouterr().out

    assert len(segundo["historial"]) == len(primero["historial"]) == 1
    # El aviso por epoca es lo unico que empieza por "[fase]": si no aparece
    # ninguno, no se entreno ninguna epoca en la segunda invocacion.
    assert "[cabeza]" not in segunda_salida and "[ajuste]" not in segunda_salida, \
        f"se volvio a entrenar una epoca ya hecha:\n{segunda_salida}"
    assert str(salida / "checkpoints" / "ultimo.pt") in segunda_salida


def test_al_reanudar_el_tiempo_de_entrenamiento_se_acumula(
        raiz_preparada, tmp_path, sin_descarga_de_pesos):
    """`segundos_entrenamiento` existe para comparar el coste de dos
    arquitecturas. Si solo contara la ultima invocacion, una corrida larga
    -que es justo la que se reanuda varias veces- mentiria a la baja.

    El contador se lee del fichero que vive JUNTO AL CHECKPOINT, no del
    reporte final. La revision demostro por que: el reporte solo se escribe
    cuando el entrenamiento termina, asi que una corrida que murio a mitad
    -el unico caso para el que existe --reanudar- no dejaba nada que
    acumular. Por eso aqui se siembra el contador donde de verdad sobrevive.
    """
    salida = tmp_path / "corrida"
    (salida / "checkpoints").mkdir(parents=True)
    previos = 10_000.0
    (salida / "checkpoints" / entrenar_local.NOMBRE_SEGUNDOS).write_text(
        str(previos), encoding="utf-8")

    entrenar_local.main(_argumentos(raiz_preparada, salida, "--reanudar"))
    reporte = json.loads((salida / "reporte_metricas.json").read_text(encoding="utf-8"))
    # >= y no >: el redondeo a una decima se come la epoca sintetica, que
    # dura milesimas. Sin acumular, el valor seria esas milesimas.
    assert reporte["corrida"]["segundos_entrenamiento"] >= previos

    # Sin --reanudar la corrida empieza de cero, y el contador tambien: sumarle
    # el tiempo de otra corrida distinta seria inventarse el dato.
    entrenar_local.main(_argumentos(raiz_preparada, salida, "--no-reanudar"))
    reporte = json.loads((salida / "reporte_metricas.json").read_text(encoding="utf-8"))
    assert reporte["corrida"]["segundos_entrenamiento"] < previos


def test_el_aviso_por_epoca_estima_lo_que_falta(capsys):
    """Sin la estimacion, el usuario mira horas de silencio sin saber si
    faltan dos o veinte. El reloj se inyecta para no esperar nada."""
    tiempos = iter([0.0, 600.0])  # creacion del avisador y cierre de la epoca 0
    avisar = entrenar_local.crear_avisador(4, reloj=lambda: next(tiempos))

    avisar({"fase": "cabeza", "epoca": 0, "perdida": 0.5, "recall": 0.8,
            "especificidad": 0.7, "auc": 0.85, "umbral": 0.4,
            "mejora": True, "sin_mejora": 0, "paciencia": 5})

    linea = capsys.readouterr().out
    assert "[cabeza] época  0/4" in linea
    assert "10 min/época" in linea
    assert "faltan ~30 min" in linea, f"estimacion ausente o erronea: {linea}"
    assert "<- mejor" in linea


def test_al_reanudar_no_cuenta_como_pendientes_las_epocas_ya_hechas(capsys):
    """Las epocas restantes salen del indice GLOBAL de la epoca, no del numero
    de avisos de este proceso: al reanudar en la epoca 20 de 24 quedan 3, no
    23, aunque este proceso solo haya cronometrado una."""
    tiempos = iter([0.0, 300.0])
    avisar = entrenar_local.crear_avisador(24, reloj=lambda: next(tiempos))

    avisar({"fase": "ajuste", "epoca": 20, "perdida": 0.5, "recall": 0.8,
            "especificidad": 0.7, "auc": 0.85, "umbral": 0.4,
            "mejora": False, "sin_mejora": 1, "paciencia": 5})

    linea = capsys.readouterr().out
    assert "5 min/época" in linea
    assert "faltan ~15 min" in linea, f"estimacion ausente o erronea: {linea}"
    assert "(sin mejorar 1/5)" in linea


def test_el_umbral_sale_de_validacion_y_las_metricas_de_prueba(
        raiz_preparada, tmp_path, sin_descarga_de_pesos, monkeypatch):
    """La clase de error mas cara del script, y la que la suite no veia.

    La revision comprobo que cuatro mutaciones graves pasaban sin que fallara
    ninguna prueba: reportar las metricas de validacion bajo la etiqueta de
    prueba, ELEGIR EL UMBRAL SOBRE EL CONJUNTO DE PRUEBA (fuga que invalida
    todo el reporte), intercambiar n_val y n_test, y evaluar con aumento de
    datos activado. Las cuatro son invisibles si val y test tienen el mismo
    tamano y la misma pinta.

    Aqui se observa que particion recibe cada llamada, en vez de confiar en
    que los numeros salgan distintos.
    """
    salida = tmp_path / "corrida"
    vistos = []
    original = entrenar_local.construir_cargador

    def espiar(cfg, particion, entrenamiento, *resto):
        vistos.append((particion, entrenamiento))
        return original(cfg, particion, entrenamiento, *resto)

    monkeypatch.setattr(entrenar_local, "construir_cargador", espiar)

    umbrales = []
    original_umbral = entrenar_local.elegir_umbral

    def espiar_umbral(y, s, *resto):
        umbrales.append(len(y))
        return original_umbral(y, s, *resto)

    monkeypatch.setattr(entrenar_local, "elegir_umbral", espiar_umbral)
    entrenar_local.main(_argumentos(raiz_preparada, salida))

    particiones = [p for p, _ in vistos]
    assert particiones.count("test") == 1, "la prueba se toca una sola vez"
    assert particiones.index("test") > particiones.index("val"), \
        "el conjunto de prueba se evalua DESPUES de fijar el umbral"

    # Solo el cargador de entrenamiento lleva aumento de datos: evaluar con
    # RandomAffine y ColorJitter activos daria metricas que no corresponden a
    # lo que el modelo vera en produccion.
    assert [e for p, e in vistos if p in ("val", "test")] == [False, False]

    # El umbral se elige SOBRE VALIDACION. Los tamanos distintos de la fixture
    # son lo que hace observable la diferencia.
    assert umbrales == [TAMANOS["val"]], \
        f"elegir_umbral recibio {umbrales}, se esperaba {[TAMANOS['val']]}"

    reporte = json.loads((salida / "reporte_metricas.json").read_text(encoding="utf-8"))
    assert reporte["corrida"]["n_val"] == TAMANOS["val"]
    assert reporte["corrida"]["n_test"] == TAMANOS["test"]
    assert reporte["corrida"]["n_val"] != reporte["corrida"]["n_test"]


def test_el_tiempo_sobrevive_a_una_corrida_que_muere_a_mitad(
        raiz_preparada, tmp_path, sin_descarga_de_pesos, monkeypatch):
    """El caso que el contador anterior NO cubria, y el unico para el que
    existe --reanudar.

    Antes el tiempo se recuperaba del reporte final, pero ese fichero solo se
    escribe cuando el entrenamiento termina: un proceso que muere a las 20 h
    de 24,9 h dejaba checkpoint pero ningun reporte, asi que el contador
    volvia a cero y `segundos_entrenamiento` -el campo con el que se compara
    el coste entre arquitecturas- declaraba solo el ultimo tramo.

    Aqui se simula la caida haciendo estallar `entrenar` despues de que el
    avisador haya cerrado una epoca, que es cuando el contador se persiste.
    """
    salida = tmp_path / "corrida"
    ruta_contador = salida / "checkpoints" / entrenar_local.NOMBRE_SEGUNDOS

    original = entrenar_local.entrenar

    def morir_a_mitad(*args, **kwargs):
        # Cerrar una epoca -que es lo que persiste el contador- y caerse.
        kwargs["al_terminar_epoca"]({"fase": "cabeza", "epoca": 0, "perdida": 0.5,
                                     "recall": 0.5, "especificidad": 0.5,
                                     "auc": 0.5, "umbral": 0.5, "mejora": True,
                                     "sin_mejora": 0, "paciencia": 5})
        raise RuntimeError("la sesion se cayo")

    monkeypatch.setattr(entrenar_local, "entrenar", morir_a_mitad)
    with pytest.raises(RuntimeError):
        entrenar_local.main(_argumentos(raiz_preparada, salida))

    assert not (salida / "reporte_metricas.json").exists(), \
        "una corrida que murio no deja reporte: de ahi el problema"
    assert ruta_contador.is_file(), \
        "el contador tiene que sobrevivir a la caida, es su unica razon de ser"
    perdido = float(ruta_contador.read_text(encoding="utf-8"))

    # Al relanzar, el tiempo del tramo perdido se suma en vez de perderse.
    monkeypatch.setattr(entrenar_local, "entrenar", original)
    entrenar_local.main(_argumentos(raiz_preparada, salida, "--reanudar"))
    reporte = json.loads((salida / "reporte_metricas.json").read_text(encoding="utf-8"))
    assert reporte["corrida"]["segundos_entrenamiento"] >= perdido
