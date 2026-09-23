"""Pruebas de la comparativa de corridas.

Lo que se protege aqui es la REGLA DE SELECCION, escalon por escalon. Elegir
que modelo queda es la decision que este sub-proyecto tiene que defender ante
el tribunal, y una regla que no esta fijada por pruebas es una regla que puede
cambiar sin que nadie se entere y dejar el informe diciendo otra cosa.
"""
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "comparar_corridas.py"


def _cargar_script():
    """Importa el script por ruta.

    No es un modulo del paquete -comparar corridas es trabajo de laboratorio,
    no algo que SP2 instale-, asi que no hay `import` normal que lo alcance.
    """
    especificacion = importlib.util.spec_from_file_location(
        "comparar_corridas", SCRIPT)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


comparar = _cargar_script()


def _escribir_reporte(tmp_path, nombre, *, recall, especificidad, auc=0.90,
                      f1=0.62, arquitectura="densenet121", tam_imagen=320,
                      epocas=(4, 20), n_test=3811, mejor_epoca=11,
                      umbral=0.4231, con_bloque_corrida=True):
    """Deja en disco un reporte_metricas.json con la misma forma que el real.

    La forma la fija la celda 7 de `notebooks/entrenar_gpu.ipynb`: si esa celda
    cambia, estas pruebas dejan de representar lo que se compara de verdad.
    """
    prueba = {"recall": recall, "especificidad": especificidad, "f1": f1,
              "precision": 0.5, "tp": 700, "tn": 2300, "fp": 600, "fn": 211,
              "umbral": umbral}
    if auc is not None:  # los reportes hechos con `metricas_binarias` no traen AUC
        prueba["auc"] = auc
    cuerpo = {"umbral": umbral, "regla": "paso_4_recall_minimo_con_especificidad_minima",
              "validacion": dict(prueba), "prueba": prueba,
              "mejor_epoca": mejor_epoca, "historial": []}
    if con_bloque_corrida:
        cuerpo["corrida"] = {"nombre": nombre, "arquitectura": arquitectura,
                             "tam_imagen": tam_imagen, "lote": 24,
                             "epocas": list(epocas), "ajuste_fino_completo": True,
                             "scheduler_coseno": True, "paciencia": 5,
                             "edad": [18, 100], "n_val": 3811, "n_test": n_test}
    carpeta = tmp_path / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / "reporte_metricas.json"
    ruta.write_text(json.dumps(cuerpo, ensure_ascii=False), encoding="utf-8")
    return ruta


def _resumen(ruta):
    return comparar.resumir(*comparar.cargar_reporte(ruta))


# --- regla de seleccion, escalon por escalon ----------------------------

def test_gana_la_que_satisface_mas_criterios_aunque_tenga_peor_recall(tmp_path):
    """Escalon 1. Es el caso que mas facil seria equivocar: la perdedora tiene
    mejor recall Y mejor AUC, pero se queda sin especificidad."""
    cumple = _resumen(_escribir_reporte(
        tmp_path, "cumple_los_tres", recall=0.82, especificidad=0.72, auc=0.86))
    incumple = _resumen(_escribir_reporte(
        tmp_path, "recall_alto_sin_especificidad",
        recall=0.95, especificidad=0.55, auc=0.93))

    ganadora, paso = comparar.elegir_ganadora([incumple, cumple])

    assert ganadora["nombre"] == "cumple_los_tres"
    assert paso == comparar.PASO_CRITERIOS


def test_a_igualdad_de_criterios_desempata_el_recall(tmp_path):
    """Escalon 2. La de mayor recall gana aunque tenga PEOR AUC: el falso
    negativo es el error caro y por eso el recall desempata antes."""
    auc_alto = _resumen(_escribir_reporte(
        tmp_path, "auc_alto", recall=0.82, especificidad=0.74, auc=0.92))
    recall_alto = _resumen(_escribir_reporte(
        tmp_path, "recall_alto", recall=0.88, especificidad=0.71, auc=0.86))

    ganadora, paso = comparar.elegir_ganadora([auc_alto, recall_alto])

    assert ganadora["nombre"] == "recall_alto"
    assert paso == comparar.PASO_RECALL


def test_si_empatan_en_recall_desempata_el_auc(tmp_path):
    """Escalon 3."""
    menos_auc = _resumen(_escribir_reporte(
        tmp_path, "auc_86", recall=0.84, especificidad=0.74, auc=0.86))
    mas_auc = _resumen(_escribir_reporte(
        tmp_path, "auc_91", recall=0.84, especificidad=0.71, auc=0.91))

    ganadora, paso = comparar.elegir_ganadora([menos_auc, mas_auc])

    assert ganadora["nombre"] == "auc_91"
    assert paso == comparar.PASO_AUC


def test_si_ninguna_cumple_no_se_corona_ninguna(tmp_path):
    """Escalon 4, el que evita el error de presentacion mas caro: coronar como
    ganadora a la mejor de un lote que el proyecto no puede aceptar."""
    # La corrida 1 de verdad, medida en Colab el 19-sep-2026.
    corrida1 = _resumen(_escribir_reporte(
        tmp_path, "corrida1_mobilenet_224px",
        recall=0.766, especificidad=0.764, auc=0.845,
        arquitectura="mobilenet_v3_large", tam_imagen=224))
    sin_especificidad = _resumen(_escribir_reporte(
        tmp_path, "sin_especificidad", recall=0.81, especificidad=0.62, auc=0.87))

    ganadora, paso = comparar.elegir_ganadora([corrida1, sin_especificidad])

    assert ganadora is None
    assert paso == comparar.NINGUNA

    ruta = comparar.escribir_comparativa([corrida1, sin_especificidad],
                                         tmp_path / "comparativa.md")
    texto = ruta.read_text(encoding="utf-8")
    assert "Ninguna corrida cumple" in texto
    # Y dice cuanto falta, no solo que falta: 0,800 - 0,766.
    assert "0.034" in texto
    assert "**NO CUMPLE**" in texto


def test_el_empate_total_se_declara_en_vez_de_disimularse(tmp_path):
    """Dos corridas identicas en los tres escalones: la regla no decide, y el
    informe tiene que decirlo en vez de fingir que si."""
    una = _resumen(_escribir_reporte(tmp_path, "una", recall=0.84,
                                     especificidad=0.74, auc=0.90))
    otra = _resumen(_escribir_reporte(tmp_path, "otra", recall=0.84,
                                      especificidad=0.71, auc=0.90))

    ganadora, paso = comparar.elegir_ganadora([una, otra])

    assert ganadora["nombre"] == "una"  # el orden de entrada, y se dice cual es
    assert paso == comparar.PASO_EMPATE


# --- casos degenerados --------------------------------------------------

def test_un_reporte_antiguo_sin_bloque_corrida_se_compara_igual(tmp_path):
    """Los reportes anteriores al 21-sep-2026 no traen el bloque `corrida`:
    tienen metricas pero no dicen con que configuracion se obtuvieron."""
    antiguo = _resumen(_escribir_reporte(
        tmp_path, "corrida1_mobilenet_224px", recall=0.86, especificidad=0.72,
        auc=0.89, con_bloque_corrida=False))
    nuevo = _resumen(_escribir_reporte(
        tmp_path, "corrida2_densenet121_320px", recall=0.84,
        especificidad=0.74, auc=0.90))

    # Sigue siendo comparable -las metricas estan- y se identifica por la
    # carpeta, que en este proyecto es el nombre de la corrida.
    assert antiguo["sin_bloque_corrida"] is True
    assert antiguo["nombre"] == "corrida1_mobilenet_224px"
    assert antiguo["criterios_cumplidos"] == 3

    texto = comparar.escribir_comparativa(
        [antiguo, nuevo], tmp_path / "c.md").read_text(encoding="utf-8")
    assert "n/d" in texto  # arquitectura y resolucion desconocidas
    assert "bloque `corrida`" in texto
    # Y no se inventa una atribucion que no puede sostener.
    assert "no se puede atribuir" not in texto


def test_un_criterio_no_reportado_no_cuenta_como_cumplido(tmp_path):
    """Sin AUC (reportes hechos con `metricas_binarias`) el criterio no se da
    por bueno, pero tampoco se declara incumplido: nadie lo midio."""
    resumen = _resumen(_escribir_reporte(
        tmp_path, "sin_auc", recall=0.84, especificidad=0.74, auc=None))

    assert resumen["criterios"]["auc"] is None
    assert resumen["criterios_cumplidos"] == 2
    assert resumen["cumple_todo"] is False

    ganadora, paso = comparar.elegir_ganadora([resumen])
    assert ganadora is None and paso == comparar.NINGUNA

    texto = comparar.escribir_comparativa(
        [resumen], tmp_path / "c.md").read_text(encoding="utf-8")
    assert "NO REPORTADO" in texto


def test_una_sola_corrida_no_finge_una_comparacion(tmp_path):
    sola = _resumen(_escribir_reporte(tmp_path, "sola", recall=0.86,
                                      especificidad=0.76, auc=0.89))

    ganadora, paso = comparar.elegir_ganadora([sola])
    assert ganadora["nombre"] == "sola"
    assert paso == comparar.PASO_UNICA

    texto = comparar.escribir_comparativa(
        [sola], tmp_path / "c.md").read_text(encoding="utf-8")
    assert "Solo hay una corrida" in texto


def test_una_ruta_inexistente_falla_antes_de_escribir_nada(tmp_path, capsys):
    bueno = _escribir_reporte(tmp_path, "bueno", recall=0.86,
                              especificidad=0.76, auc=0.89)
    salida = tmp_path / "docs" / "comparativa.md"

    codigo = comparar.main([str(bueno.parent), str(tmp_path / "no_existe"),
                            "--salida", str(salida)])

    assert codigo == 2
    assert "no_existe" in capsys.readouterr().err
    assert not salida.exists()  # nada a medias en disco


def test_un_json_que_no_es_un_reporte_lo_dice(tmp_path):
    ruta = tmp_path / "otra_cosa.json"
    ruta.write_text(json.dumps({"hola": "mundo"}), encoding="utf-8")

    with pytest.raises(ValueError, match="prueba"):
        comparar.cargar_reporte(ruta)


# --- el informe ---------------------------------------------------------

def test_el_markdown_lleva_escrita_la_regla_de_seleccion(tmp_path):
    """Requisito central: quien lea el informe tiene que poder auditar por que
    gano la que gano, sin abrir el codigo."""
    primera = _resumen(_escribir_reporte(tmp_path, "primera", recall=0.86,
                                         especificidad=0.74, auc=0.90))
    segunda = _resumen(_escribir_reporte(tmp_path, "segunda", recall=0.83,
                                         especificidad=0.72, auc=0.88))

    texto = comparar.escribir_comparativa(
        [primera, segunda], tmp_path / "c.md").read_text(encoding="utf-8")

    for escalon in comparar.REGLA_DE_SELECCION:
        assert escalon in texto
    # La regla no se limita a enunciarse: dice por que el recall desempata.
    assert "falso negativo" in texto
    assert comparar.PASO_RECALL in texto
    assert comparar.EXPLICACION_PASO[comparar.PASO_RECALL] in texto


def test_la_prosa_no_atribuye_la_mejora_si_cambian_dos_cosas_a_la_vez(tmp_path):
    vieja = _resumen(_escribir_reporte(
        tmp_path, "mobilenet_224", recall=0.82, especificidad=0.71, auc=0.86,
        arquitectura="mobilenet_v3_large", tam_imagen=224))
    nueva = _resumen(_escribir_reporte(
        tmp_path, "densenet_320", recall=0.86, especificidad=0.74, auc=0.90,
        arquitectura="densenet121", tam_imagen=320))

    texto = comparar.escribir_comparativa(
        [vieja, nueva], tmp_path / "c.md").read_text(encoding="utf-8")

    assert "no se puede atribuir" in texto
    assert "mobilenet_v3_large -> densenet121" in texto
    assert "224 -> 320" in texto
    assert "+0.040" in texto  # el delta de recall, dicho con su signo


def test_la_prosa_si_atribuye_la_mejora_si_cambia_una_sola_cosa(tmp_path):
    baja = _resumen(_escribir_reporte(tmp_path, "densenet_224", recall=0.82,
                                      especificidad=0.71, auc=0.86,
                                      tam_imagen=224))
    alta = _resumen(_escribir_reporte(tmp_path, "densenet_320", recall=0.86,
                                      especificidad=0.74, auc=0.90,
                                      tam_imagen=320))

    texto = comparar.escribir_comparativa(
        [baja, alta], tmp_path / "c.md").read_text(encoding="utf-8")

    assert "atribuible a ese cambio" in texto
    assert "no se puede atribuir" not in texto
    # Con una sola corrida por configuracion, la reserva se dice igual.
    assert "una sola semilla" in texto


def test_avisa_si_los_conjuntos_de_prueba_no_son_del_mismo_tamanio(tmp_path):
    """Comparar metricas medidas sobre conjuntos distintos no es comparar."""
    completa = _resumen(_escribir_reporte(tmp_path, "completa", recall=0.86,
                                          especificidad=0.74, auc=0.90,
                                          n_test=3811))
    recortada = _resumen(_escribir_reporte(tmp_path, "recortada", recall=0.83,
                                           especificidad=0.72, auc=0.88,
                                           n_test=400))

    texto = comparar.escribir_comparativa(
        [completa, recortada], tmp_path / "c.md").read_text(encoding="utf-8")

    assert "3811 frente a 400" in texto


def test_la_cli_acepta_carpetas_y_json_y_deja_el_informe(tmp_path, capsys):
    carpeta = _escribir_reporte(tmp_path, "ganadora", recall=0.88,
                                especificidad=0.74, auc=0.91).parent
    json_directo = _escribir_reporte(tmp_path, "perdedora", recall=0.81,
                                     especificidad=0.71, auc=0.86)
    salida = tmp_path / "docs" / "comparativa-corridas.md"

    codigo = comparar.main([str(carpeta), str(json_directo),
                            "--salida", str(salida)])

    assert codigo == 0
    assert salida.exists()
    # El veredicto tambien se dice por consola: despues de horas de
    # entrenamiento, lo primero que se quiere saber es cual queda.
    assert "gana ganadora" in capsys.readouterr().out
    texto = salida.read_text(encoding="utf-8")
    assert "Gana `ganadora`" in texto
    assert "| 1 | `ganadora` |" in texto
    assert "| 2 | `perdedora` |" in texto


def test_lo_ausente_pierde_todos_los_desempates(tmp_path):
    """El unico escalon de la regla que no tenia prueba propia.

    La revision lo demostro mutando `_numero_o` para que una metrica NO medida
    ganara cualquier desempate: las 15 pruebas seguian pasando. Un valor
    ausente y un 0,0 son cosas distintas -0,0 es un recall legitimo- y
    confundirlos corona como ganadora a la corrida de la que menos se sabe.
    """
    assert comparar._numero_o(None) == -1.0
    assert comparar._numero_o(0.0) == 0.0
    assert comparar._numero_o(None) < comparar._numero_o(0.0)

    # Y el efecto en la ordenacion, que es lo que de verdad decide.
    medida = _resumen(_escribir_reporte(tmp_path, "medida", recall=0.0,
                                        especificidad=0.0, auc=0.0))
    sin_medir = _resumen(_escribir_reporte(tmp_path, "sin_medir", recall=None,
                                           especificidad=None, auc=None))
    ordenadas = comparar.ordenar_corridas([sin_medir, medida])
    assert ordenadas[0]["nombre"] == "medida",         "una corrida sin metricas no puede ganarle a una medida"


def test_la_nota_de_procedencia_aparece_con_un_reporte_antiguo(tmp_path):
    """Prueba de la NOTA, no de cualquier aparicion de la cadena.

    La version anterior afirmaba cubrir esto buscando 'bloque `corrida`' en el
    Markdown, pero esa cadena la emite tambien el parrafo de prosa: la revision
    borro la nota entera y la prueba siguio pasando. Con UNA sola corrida -el
    caso real de la corrida 1- la prosa toma otra rama y no la menciona, asi
    que la nota es la unica explicacion de los n/d de la tabla.
    """
    ruta = _escribir_reporte(tmp_path, "vieja", recall=0.766,
                             especificidad=0.764, auc=0.845,
                             con_bloque_corrida=False)
    salida = tmp_path / "comparativa.md"
    assert comparar.main([str(ruta), "--salida", str(salida)]) == 0

    seccion = salida.read_text(encoding="utf-8").split("## Procedencia", 1)[1]
    assert "no trae el bloque `corrida`" in seccion,         "sin la nota, los n/d de la tabla quedan sin explicar"
    assert "2aa33c5" in seccion, "la nota debe citar de donde sale el bloque"


def test_una_corrida_pasada_dos_veces_no_se_compara_consigo_misma(tmp_path):
    """Pasar la carpeta y su JSON es un descuido facil, y antes producia dos
    filas identicas y un parrafo que atribuia a la semilla la diferencia entre
    un archivo y el mismo archivo."""
    ruta = _escribir_reporte(tmp_path, "dup", recall=0.86, especificidad=0.76)
    salida = tmp_path / "comparativa.md"
    assert comparar.main([str(ruta.parent), str(ruta),
                          "--salida", str(salida)]) == 0

    texto = salida.read_text(encoding="utf-8")
    assert "a partir de 1 reporte(s)" in texto
    # Una fila en Procedencia, no dos: es la tabla que lista los reportes
    # leidos. El nombre aparece tambien en la tabla comparativa y en el
    # veredicto, asi que contarlo en todo el documento no distingue nada.
    procedencia = texto.split("## Procedencia", 1)[1]
    assert procedencia.count("| `dup`") == 1
    # Y ningun parrafo que compare la corrida consigo misma.
    assert "**`dup`** frente a **`dup`**" not in texto


def test_un_json_con_prueba_inutilizable_dice_de_cual_se_trata(tmp_path):
    """Pasa la comprobacion de cargar_reporte (tiene la clave 'prueba') pero
    su contenido no sirve. Antes soltaba una traza cruda sin nombrar el
    archivo, que es justo lo que el contrato promete."""
    ruta = tmp_path / "rota.json"
    ruta.write_text(json.dumps({"prueba": [1, 2]}), encoding="utf-8")
    assert comparar.main([str(ruta), "--salida", str(tmp_path / "c.md")]) == 2
