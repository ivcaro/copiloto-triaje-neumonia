"""Entrena UNA configuracion en la maquina local y deja su reporte comparable.

Uso:
    C:\\venv-copiloto\\Scripts\\python.exe scripts/entrenar_local.py ^
        --raiz "C:\\Users\\[retirado]\\datasets\\rsna-pneumonia\\trabajo" ^
        --arquitectura mobilenet_v3_large --tam-imagen 224 --lote 32 ^
        --salida "C:\\...\\corridas\\corrida3_mobilenet_224px"

Por que existe: esta maquina no tiene GPU y la cuota de Colab se agoto, asi
que el entrenamiento real hay que dejarlo corriendo horas sobre los 20 nucleos
de esta CPU. Medido aqui, 4+20 epocas cuestan entre 3,1 h (MobileNetV3 a
224 px, lote 32) y 24,9 h (DenseNet121 a 320 px, lote 24). De ahi las tres
cosas que este script anade a lo que hacia el notebook: un aviso por epoca con
la estimacion de lo que falta, reanudacion tras una caida y una carpeta de
salida propia por corrida.

Entrena UNA sola configuracion a proposito. Comparar arquitecturas es lanzarlo
varias veces cambiando --arquitectura y contrastar despues el bloque "corrida"
de cada reporte_metricas.json: es lo unico que dice con que se entreno cada
reporte, y sin el dos reportes del mismo formato no son comparables.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import fields
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copiloto_triaje.config import ARQUITECTURAS, Config  # noqa: E402
from copiloto_triaje.datos.dataset import DatasetRadiografias  # noqa: E402
from copiloto_triaje.modelo.arquitectura import construir_modelo  # noqa: E402
from copiloto_triaje.modelo.entrenamiento import (  # noqa: E402
    entrenar, evaluar_epoca, fijar_semillas,
)
from copiloto_triaje.modelo.evaluacion import (  # noqa: E402
    elegir_umbral, metricas_en_umbral,
)
from copiloto_triaje.modelo.reporte import (  # noqa: E402
    CRITERIOS_ACEPTACION, escribir_reporte_markdown, guardar_curva_roc,
)

PARTICIONES = ("train", "val", "test")
NOMBRE_JSON = "reporte_metricas.json"
NOMBRE_MD = "reporte_metricas.md"
NOMBRE_ROC = "curva_roc.svg"

# Valores por defecto leidos del propio dataclass: argparse no debe repetir
# numeros que ya estan decididos -y justificados- en config.py, porque una
# copia se desincroniza en silencio en cuanto uno de los dos cambie.
_DEFECTOS = {campo.name: campo.default for campo in fields(Config)}

# El AUC minimo no sale de Config: Config parametriza el pipeline y esto es el
# baremo con el que se juzga su resultado, que vive junto a los otros criterios
# en modelo/reporte.py. Se lee de alli para no dejar un 0,85 suelto que luego
# se desincronice del reporte que el propio script escribe.
AUC_MINIMO = next(minimo for _, clave, minimo, _ in CRITERIOS_ACEPTACION
                  if clave == "auc")

# Medido en esta maquina: 268 img/s con 8 procesos de carga, es decir 1,1 min
# por epoca de puro leer imagenes, contra decenas de minutos de computo. La
# carga NO es el cuello de botella en CPU, asi que 4 basta y sobra.
#
# Lo que NO se puede afirmar es que subirlo perjudique: torch usa aqui 10
# hilos (los nucleos fisicos), no los 20 logicos que reporta el sistema, asi
# que 4 procesos de carga no le quitan nucleos al computo. El script imprime
# ese numero al arrancar; si en una corrida real el tiempo por epoca parece
# dominado por la carga, subir esta bandera es barato de probar.
TRABAJADORES_POR_DEFECTO = 4


def verificar_datos_listos(cfg: Config) -> None:
    """Falla antes de empezar si los datos no estan preparados.

    Un entrenamiento local son horas: descubrir a la tercera que falta un
    manifiesto es perder la tarde entera. El mensaje cita siempre la ruta
    buscada y el comando que la produce, porque el error real casi nunca es
    "faltan datos" sino "--raiz apunta a otra carpeta".
    """
    if not cfg.dir_png.is_dir():
        raise FileNotFoundError(
            f"No existe el directorio de imágenes: {cfg.dir_png}\n"
            f"Ejecuta primero scripts/preparar_datos.py con "
            f"--raiz {cfg.raiz_datos}")
    faltantes = [nombre for nombre in PARTICIONES
                 if not (cfg.dir_manifiestos / f"{nombre}.csv").is_file()]
    if faltantes:
        esperados = ", ".join(f"{nombre}.csv" for nombre in faltantes)
        raise FileNotFoundError(
            f"Faltan manifiestos en {cfg.dir_manifiestos}: {esperados}\n"
            f"Ejecuta primero scripts/preparar_datos.py con "
            f"--raiz {cfg.raiz_datos}")


def formatear_duracion(segundos: float) -> str:
    """Duracion legible de un vistazo: '4 h 36 min', '38 min', '45 s'.

    Una estimacion en segundos ('16 380 s') obliga a dividir mentalmente, y
    esta cifra existe justo para decidir en un segundo si la tarde se espera o
    se dedica a otra cosa.
    """
    segundos = max(float(segundos), 0.0)
    if segundos < 90:
        return f"{segundos:.0f} s"
    minutos = segundos / 60.0
    if minutos < 90:
        return f"{minutos:.0f} min"
    horas, resto = divmod(int(round(minutos)), 60)
    return f"{horas} h {resto:02d} min"


def crear_avisador(total_epocas: int, reloj=time.monotonic,
                   ruta_segundos=None, segundos_base: float = 0.0):
    """Devuelve la funcion que `entrenar` llama al cerrar cada epoca.

    `entrenar` no imprime nada a proposito (es libreria y tiene pruebas), asi
    que sin esto una corrida de 24 epocas son horas de silencio en las que no
    se distingue "avanzando" de "colgado". El aviso llega DESPUES de escribir
    el checkpoint: si la linea salio, esa epoca ya sobrevive a una caida.

    La estimacion de lo que falta se calcula solo con las epocas cronometradas
    en ESTA invocacion, pero el numero de epocas restantes sale de
    `registro["epoca"]`, que es el indice global dentro del entrenamiento; asi
    una corrida reanudada no vuelve a contar como pendientes las epocas que ya
    hizo el proceso anterior. Es una cota superior: si el early stopping corta
    una fase, termina antes.

    `reloj` es inyectable para poder probar la estimacion sin esperar horas.
    `ruta_segundos` y `segundos_base` sirven para que el coste acumulado
    sobreviva a una caida: ver el comentario dentro de `avisar`.
    """
    estado = {"inicio": reloj(), "hechas": 0}

    def avisar(registro: dict) -> None:
        estado["hechas"] += 1
        transcurrido = reloj() - estado["inicio"]
        if ruta_segundos is not None:
            # El contador se persiste EN CADA EPOCA, no al final.
            # `segundos_entrenamiento` existe para comparar el coste de dos
            # arquitecturas, y antes se recuperaba del reporte final; pero el
            # reporte solo se escribe cuando el entrenamiento TERMINA, asi que
            # una corrida que murio a las 20 horas -el unico caso para el que
            # existe --reanudar- no dejaba ningun tiempo que acumular y el
            # campo declaraba solo el ultimo tramo. Escribirlo aqui, al lado
            # del checkpoint que si sobrevive, es lo que hace que el numero
            # corresponda al coste real.
            escribir_segundos(ruta_segundos, segundos_base + transcurrido)
        por_epoca = transcurrido / estado["hechas"]
        restantes = max(total_epocas - (registro["epoca"] + 1), 0)
        marca = ("  <- mejor" if registro["mejora"]
                 else f"  (sin mejorar {registro['sin_mejora']}/"
                      f"{registro['paciencia']})")
        # flush=True: la salida de un proceso de horas se mira con la consola
        # abierta o con `tail` sobre un log redirigido, y sin flush el buffer
        # de bloque la retiene hasta que se llena.
        print(f"[{registro['fase']}] época {registro['epoca']:>2}/{total_epocas} "
              f"| pérdida {registro['perdida']:.4f} "
              f"| recall {registro['recall']:.3f} "
              f"| espec. {registro['especificidad']:.3f} "
              f"| AUC {registro['auc']:.3f} "
              f"| umbral {registro['umbral']:.3f} "
              f"| {formatear_duracion(por_epoca)}/época "
              f"| faltan ~{formatear_duracion(por_epoca * restantes)}"
              f"{marca}", flush=True)

    return avisar


def construir_cargador(cfg: Config, nombre: str, entrenamiento: bool,
                       trabajadores: int, anclar_memoria: bool = False) -> DataLoader:
    """DataLoader de una particion, leida SIEMPRE desde su manifiesto.

    `persistent_workers` evita volver a levantar los procesos de carga en cada
    epoca: en Windows cada arranque es un proceso nuevo que reimporta torch, y
    eso se paga tantas veces como epocas haya.
    """
    manifiesto = pd.read_csv(cfg.dir_manifiestos / f"{nombre}.csv")
    conjunto = DatasetRadiografias(manifiesto, cfg.dir_png, cfg.tam_imagen,
                                   entrenamiento)
    return DataLoader(conjunto, batch_size=cfg.lote, shuffle=entrenamiento,
                      num_workers=trabajadores,
                      persistent_workers=trabajadores > 0,
                      pin_memory=anclar_memoria)


NOMBRE_SEGUNDOS = "segundos_entrenamiento.txt"


def segundos_previos(ruta_segundos: Path) -> float:
    """Segundos de entrenamiento que ya acumulaba esta corrida.

    Vive junto al checkpoint y NO dentro del reporte final, que es donde se
    leia antes. El reporte solo se escribe cuando el entrenamiento termina, de
    modo que una corrida que murio a mitad -el unico caso para el que existe
    --reanudar- no dejaba nada que acumular: el contador se reiniciaba y
    `segundos_entrenamiento` declaraba solo el ultimo tramo. En una corrida de
    24,9 h que cae a las 20 h, el campo que existe para comparar el coste
    entre arquitecturas habria declarado 4,9 h.
    """
    ruta_segundos = Path(ruta_segundos)
    if not ruta_segundos.is_file():
        return 0.0
    try:
        return max(float(ruta_segundos.read_text(encoding="utf-8").strip()), 0.0)
    except (ValueError, OSError):
        # Un contador ilegible no justifica abortar horas de entrenamiento.
        return 0.0


def escribir_segundos(ruta_segundos: Path, segundos: float) -> None:
    """Deja el contador en disco. Los fallos se ignoran a proposito: perder el
    dato de coste es molesto, tirar una corrida de horas por no poder escribir
    un numero seria mucho peor."""
    try:
        ruta_segundos.parent.mkdir(parents=True, exist_ok=True)
        ruta_segundos.write_text(f"{segundos:.3f}", encoding="utf-8")
    except OSError:
        pass


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Entrena una configuracion en la CPU local y escribe su reporte")
    parser.add_argument("--raiz", required=True, type=Path,
                        help="carpeta con png/ y manifiestos/ (la --raiz que "
                             "se le pasó a preparar_datos.py)")
    parser.add_argument("--arquitectura", default=_DEFECTOS["arquitectura"],
                        help=f"una de: {', '.join(ARQUITECTURAS)}")
    parser.add_argument("--tam-imagen", type=int, default=_DEFECTOS["tam_imagen"])
    parser.add_argument("--lote", type=int, default=_DEFECTOS["lote"])
    parser.add_argument("--epocas-cabeza", type=int,
                        default=_DEFECTOS["epocas_cabeza"])
    parser.add_argument("--epocas-ajuste", type=int,
                        default=_DEFECTOS["epocas_ajuste"])
    parser.add_argument("--salida", type=Path, default=None,
                        help="carpeta de la corrida; por defecto "
                             "<raiz>/corridas/<arquitectura>_<tam>px_lote<lote>")
    # Por defecto se reanuda: si no hay checkpoint, `entrenar` arranca de cero
    # sin quejarse, de modo que el valor solo cambia algo en el unico caso en
    # que importa, que es relanzar una corrida que murio a media tarde.
    parser.add_argument("--reanudar", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="continuar desde el último checkpoint de la corrida")
    parser.add_argument("--trabajadores", type=int,
                        default=TRABAJADORES_POR_DEFECTO,
                        help="procesos de carga de imágenes (num_workers)")
    return parser


def main(argv=None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argv)

    # Se valida ANTES de construir Config y antes de mirar el disco: un nombre
    # mal escrito tiene que costar un segundo, no el tiempo de cargar torch y
    # los manifiestos. `parser.error` ya imprime el uso y sale con codigo 2.
    if args.arquitectura not in ARQUITECTURAS:
        parser.error(
            f"arquitectura '{args.arquitectura}' no soportada; "
            f"las válidas son: {', '.join(ARQUITECTURAS)}")

    # `zip_rsna` apunta a la raiz y no a un zip porque aqui los datos ya estan
    # preparados: este script no descomprime nada y no tiene forma de saber de
    # que zip salieron. Config exige el campo como procedencia; inventarle una
    # ruta inexistente seria peor que citar la carpeta que si existe.
    cfg = Config(raiz_datos=args.raiz, zip_rsna=args.raiz,
                 arquitectura=args.arquitectura, tam_imagen=args.tam_imagen,
                 lote=args.lote, epocas_cabeza=args.epocas_cabeza,
                 epocas_ajuste=args.epocas_ajuste)
    verificar_datos_listos(cfg)

    # Una carpeta por corrida, nunca una compartida: los checkpoints viven
    # dentro, y en Colab ya paso que un 'ultimo.pt' de otra arquitectura
    # quedara en la carpeta comun y reventara la reanudacion de la siguiente
    # corrida. El nombre por defecto lleva la configuracion para que dos
    # corridas distintas no puedan caer en la misma carpeta por descuido.
    # Las epocas van en el nombre porque son parte de la configuracion y
    # viajan al bloque 'corrida'. Sin ellas, dos corridas iguales salvo en
    # epocas comparten carpeta y checkpoints; y como --reanudar es el valor
    # por defecto, la segunda no reentrena nada y escribe un bloque que
    # describe una configuracion que nunca se ejecuto.
    salida = args.salida or (
        args.raiz / "corridas"
        / f"{cfg.arquitectura}_{cfg.tam_imagen}px_lote{cfg.lote}"
          f"_{cfg.epocas_cabeza}+{cfg.epocas_ajuste}ep")
    salida.mkdir(parents=True, exist_ok=True)
    dir_checkpoints = salida / "checkpoints"

    dispositivo = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"dispositivo: {dispositivo} | hilos de torch: {torch.get_num_threads()}",
          flush=True)
    print(f"corrida: {salida.name} | {cfg.arquitectura} | {cfg.tam_imagen} px "
          f"| lote {cfg.lote} | {cfg.epocas_cabeza}+{cfg.epocas_ajuste} épocas "
          f"| {args.trabajadores} proceso(s) de carga", flush=True)
    print(f"salida: {salida}", flush=True)

    anclar = dispositivo.type == "cuda"  # pin_memory solo sirve para copiar a GPU
    cargador_train = construir_cargador(cfg, "train", True, args.trabajadores, anclar)
    cargador_val = construir_cargador(cfg, "val", False, args.trabajadores, anclar)

    # Sembrar AQUI, no dentro de entrenar(). _reemplazar_cabeza crea la capa
    # final con el generador global de torch, y esa cabeza es lo unico que se
    # entrena durante toda la fase 1. Si se siembra despues de construirla,
    # cada invocacion arranca de una cabeza distinta: dos corridas del mismo
    # comando con la misma semilla dan reportes distintos. Aqui duele el
    # doble, porque este script existe para comparar arquitecturas entre si y
    # el margen entre ellas puede ser del tamano de ese ruido.
    fijar_semillas(cfg.semilla)
    modelo = construir_modelo(cfg.arquitectura, congelar_backbone=True,
                              preentrenado=True)

    previo = dir_checkpoints / "ultimo.pt"
    print("reanudando desde " + (str(previo) if args.reanudar and previo.exists()
                                 else "cero (no hay checkpoint previo de esta corrida)"),
          flush=True)

    # El contador vive junto al checkpoint porque es lo unico que sobrevive a
    # una caida. Con --no-reanudar se parte de cero: es una corrida nueva.
    ruta_segundos = dir_checkpoints / NOMBRE_SEGUNDOS
    segundos_base = segundos_previos(ruta_segundos) if args.reanudar else 0.0

    comienzo = time.monotonic()
    resultado = entrenar(
        modelo, cargador_train, cargador_val, cfg, dispositivo, dir_checkpoints,
        reanudar=args.reanudar,
        al_terminar_epoca=crear_avisador(
            cfg.epocas_cabeza + cfg.epocas_ajuste,
            ruta_segundos=ruta_segundos, segundos_base=segundos_base))
    ruta_json = salida / NOMBRE_JSON
    segundos = segundos_base + (time.monotonic() - comienzo)
    escribir_segundos(ruta_segundos, segundos)

    print(f"mejor época: {resultado['mejor_epoca']} "
          f"| recall en validación: {resultado['mejor_recall']:.3f} "
          f"| AUC: {resultado['mejor_auc']:.3f}", flush=True)

    # `modelo` ya vuelve de entrenar() con los pesos de su MEJOR epoca, no con
    # los de la ultima: no hay que recargar nada a mano aqui.
    y_val, s_val, _ = evaluar_epoca(modelo, cargador_val, dispositivo)
    umbral, metricas_val, paso = elegir_umbral(
        y_val, s_val, cfg.especificidad_objetivo, cfg.especificidad_minima,
        cfg.recall_objetivo, cfg.recall_minimo,
        cfg.margen_especificidad)
    print(f"umbral elegido en validación: {umbral:.4f} | regla: {paso}", flush=True)

    # El cargador de prueba se construye aqui, y no junto a los otros dos, para
    # que quede a la vista que el conjunto de prueba no se toca hasta que el
    # umbral esta congelado. Se evalua UNA sola vez: reevaluarlo despues
    # invalidaria estas metricas.
    cargador_test = construir_cargador(cfg, "test", False, args.trabajadores, anclar)
    y_test, s_test, _ = evaluar_epoca(modelo, cargador_test, dispositivo)
    metricas_test = metricas_en_umbral(y_test, s_test, umbral)

    reporte = {
        # El bloque que hace comparables dos reportes: dice con que se entreno
        # este. Sin el, dos reporte_metricas.json con el mismo formato no se
        # pueden contrastar, que es justo lo que hay que hacer con varias
        # arquitecturas.
        "corrida": {
            "nombre": salida.name,
            "arquitectura": cfg.arquitectura,
            "tam_imagen": cfg.tam_imagen,
            "lote": cfg.lote,
            "epocas": [cfg.epocas_cabeza, cfg.epocas_ajuste],
            "ajuste_fino_completo": cfg.descongelar_todo,
            "scheduler_coseno": cfg.usar_scheduler,
            "paciencia": cfg.paciencia,
            "edad": [cfg.edad_minima, cfg.edad_maxima],
            "n_val": int(len(y_val)),
            "n_test": int(len(y_test)),
            "dispositivo": str(dispositivo),
            "segundos_entrenamiento": round(segundos, 1),
        },
        "umbral": umbral,
        "regla": paso,
        "validacion": metricas_val,
        "prueba": metricas_test,
        "mejor_epoca": resultado["mejor_epoca"],
        "historial": resultado["historial"],
    }
    ruta_json.write_text(json.dumps(reporte, indent=2, ensure_ascii=False),
                         encoding="utf-8")

    ruta_roc = guardar_curva_roc(y_test, s_test, salida / NOMBRE_ROC, umbral=umbral)
    ruta_md = escribir_reporte_markdown(
        salida / NOMBRE_MD, umbral=umbral, paso=paso,
        metricas_validacion=metricas_val, metricas_prueba=metricas_test,
        historial=resultado["historial"], mejor_epoca=resultado["mejor_epoca"],
        ruta_roc=ruta_roc)

    print(f"tiempo de entrenamiento: {formatear_duracion(segundos)}", flush=True)
    print(f"entregables en {salida}", flush=True)
    for ruta in (ruta_json, ruta_md, ruta_roc):
        print(f" - {ruta.name}", flush=True)
    # Los pesos NO estan en <salida> sino en <salida>/checkpoints, porque los
    # escribe entrenar(). Listarlos junto a los otros tres mandaba a buscar en
    # la carpeta equivocada justo el unico fichero que SP2 necesita.
    print(f" - {Path(resultado['ruta_pesos_cpu'])}  (pesos para SP2)", flush=True)

    # El veredicto, dicho sin rodeos: el JSON lo tiene, pero hay que buscarlo,
    # y despues de horas de espera lo primero que se quiere saber es si esta
    # corrida cumple. No se devuelve codigo de error si no cumple: la corrida
    # se ejecuto bien y su reporte sigue siendo valido para comparar.
    for etiqueta, valor, minimo in (
            ("recall", metricas_test["recall"], cfg.recall_minimo),
            ("especificidad", metricas_test["especificidad"], cfg.especificidad_minima),
            ("AUC", metricas_test["auc"], AUC_MINIMO)):
        print(f"{'OK ' if valor >= minimo else 'NO '} {etiqueta}: {valor:.3f} "
              f"(mínimo {minimo})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
