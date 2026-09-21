"""Bucle de entrenamiento en dos fases con early stopping por RECALL.

El criterio de parada observa el Recall en validacion, no la exactitud ni
la perdida: con 22,5% de positivos, la exactitud premia al modelo que
nunca detecta a nadie.

Ese Recall se mide SIEMPRE en el umbral que `elegir_umbral` selecciona para
esa epoca, nunca en un 0,5 fijo. Ver `_puntuar_epoca`: es la diferencia
entre elegir la mejor epoca y elegir la primera.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from copiloto_triaje.modelo.arquitectura import (
    descongelar_para_ajuste,
    descongelar_todo,
)
from copiloto_triaje.modelo.evaluacion import elegir_umbral, metricas_binarias

NOMBRE_ULTIMO = "ultimo.pt"
NOMBRE_MEJOR = "mejor.pt"
NOMBRE_PESOS_CPU = "pesos_modelo_cpu.pt"

# Umbral ingenuo. NO se usa para decidir nada: solo se registra en el
# historial como diagnostico, para dejar por escrito la distancia entre lo
# que mide un 0,5 fijo y lo que mide el punto de operacion real.
UMBRAL_DIAGNOSTICO = 0.5


def fijar_semillas(semilla: int) -> None:
    """Siembra los generadores y fija el modo determinista de cuDNN.

    Se siembra el generador GLOBAL de torch antes de cualquier otra operacion
    aleatoria (incluida la de `_etiquetas_de`, que ya puede iterar un cargador
    barajado). RandomAffine y ColorJitter -el aumento de datos de
    `datos/dataset.py`- consumen ese generador global porque la API de
    torchvision no admite pasarles uno propio; lo mismo hace el barajado
    (shuffle) del DataLoader cuando no se le da un `generator` explicito.

    `torch.manual_seed` basta en CPU pero NO en GPU, que es donde corre el
    entrenamiento real: cuDNN elige por benchmark el algoritmo de convolucion
    para cada forma de entrada y algunos de sus kernels son no deterministas,
    de modo que dos corridas con la misma semilla pueden diferir en CUDA. Las
    dos banderas de abajo lo impiden.

    COSTE EN VELOCIDAD: `benchmark = False` renuncia a la busqueda del
    algoritmo de convolucion mas rapido para cada forma de entrada, y
    `deterministic = True` descarta los kernels no deterministas cuando los
    hay. En una MobileNetV3 con entradas de tamano fijo (224x224, el caso de
    este proyecto) el sobrecoste tipico esta entre el 5% y el 20% por epoca.
    Se paga a proposito: "misma semilla, mismos resultados" es un criterio de
    aceptacion del spec (§2), y sin estas banderas no se cumple en Colab.
    """
    torch.manual_seed(semilla)
    torch.cuda.manual_seed_all(semilla)  # no hace nada si no hay CUDA
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def evaluar_epoca(modelo, cargador, dispositivo) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (y_true, y_score) con y_score = probabilidad de la clase positiva."""
    modelo.eval()
    etiquetas, puntajes = [], []
    with torch.no_grad():
        for x, y in cargador:
            logits = modelo(x.to(dispositivo)).squeeze(1)
            puntajes.append(torch.sigmoid(logits).cpu().numpy())
            etiquetas.append(y.numpy())
    return np.concatenate(etiquetas), np.concatenate(puntajes)


def _etiquetas_de(cargador) -> np.ndarray:
    """Etiquetas del conjunto sin cargar las imagenes, si el dataset expone su
    manifiesto. Solo itera el cargador como ultimo recurso.

    Los dos caminos solo coinciden en conteo si el cargador tiene
    `drop_last=False` (el valor por defecto de DataLoader): con
    `drop_last=True` la iteracion omite las muestras del ultimo lote
    incompleto y devolveria menos etiquetas que las del manifiesto.
    """
    dataset = cargador.dataset
    manifiesto = getattr(dataset, "manifiesto", None)
    if manifiesto is not None and "etiqueta" in manifiesto:
        return manifiesto["etiqueta"].to_numpy(dtype=float)
    return np.concatenate([y.numpy() for _, y in cargador])


def _pasada_de_entrenamiento(modelo, cargador, criterio, optimizador, dispositivo) -> float:
    modelo.train()
    perdida_total = 0.0
    for x, y in cargador:
        x, y = x.to(dispositivo), y.to(dispositivo)
        optimizador.zero_grad()
        perdida = criterio(modelo(x).squeeze(1), y)
        perdida.backward()
        optimizador.step()
        # .item() en vez de float(): extrae el escalar ya desprendido del
        # grafo de autograd, sin el UserWarning de convertir un tensor con
        # requires_grad=True directamente a float.
        perdida_total += perdida.item() * x.size(0)
    return perdida_total / len(cargador.dataset)


def _puntuar_epoca(y_true, y_score, cfg) -> dict:
    """Puntua una epoca con el MISMO criterio con el que se elegira el umbral
    final, no con un umbral fijo.

    Por que no vale medir el recall en 0,5: el entrenamiento usa
    `pos_weight = negativos / positivos` (~3,44 con el 22,5% de positivos
    del dataset). Ese peso hace que la salida constante optima de la perdida
    sea exactamente un logit 0, es decir una probabilidad de 0,5: el modelo
    queda sentado justo encima del umbral ingenuo y basta un sesgo minimo
    para que caiga entero a un lado. En la practica, en la epoca 0 predice
    casi todo positivo, el recall en 0,5 satura en 1,0 con especificidad 0,0
    y, como la comparacion de "mejor epoca" es estricta, NINGUNA epoca
    posterior puede superarlo jamas. El triple dano ya reproducido: se
    restaura la epoca menos entrenada, la fase de ajuste muere por paciencia
    falsa y las metricas del informe salen de ese modelo.

    El arreglo es hacer coherente el criterio de epoca con el criterio final
    de seleccion de umbral: se aplica `elegir_umbral` sobre los puntajes de
    validacion y se usa el recall resultante, que ya respeta el piso de
    especificidad del spec. El coste es una curva ROC por epoca: despreciable
    frente a la pasada de entrenamiento.
    """
    umbral, metricas, paso = elegir_umbral(
        y_true, y_score,
        cfg.especificidad_objetivo, cfg.especificidad_minima, cfg.recall_objetivo,
        getattr(cfg, "recall_minimo", 0.80))
    diagnostico = metricas_binarias(
        y_true, (np.asarray(y_score) >= UMBRAL_DIAGNOSTICO).astype(int))
    return {
        "recall": metricas["recall"],
        "especificidad": metricas["especificidad"],
        "precision": metricas["precision"],
        "f1": metricas["f1"],
        "auc": metricas["auc"],
        "umbral": umbral,
        "paso_umbral": paso,
        # Diagnostico, no criterio: el par que antes gobernaba el early
        # stopping. Verlo junto al de arriba en el reporte es la prueba
        # visible de por que un umbral fijo no puede puntuar epocas.
        "recall_umbral_fijo": diagnostico["recall"],
        "especificidad_umbral_fijo": diagnostico["especificidad"],
    }


def _es_mejor(puntajes: dict, mejor_recall: float, mejor_auc: float) -> bool:
    """Recall primero, AUC como desempate.

    El desempate no es cosmetico. En la fase de ajuste fino el recall en el
    umbral elegido se queda clavado en el mismo valor varias epocas seguidas
    (la curva ROC se mueve poco de una epoca a la siguiente) mientras el AUC
    sigue subiendo. Con una comparacion estricta solo por recall, esas epocas
    cuentan como "sin mejora" y la paciencia corta el ajuste fino antes de
    tiempo aunque el modelo siga mejorando.
    """
    if puntajes["recall"] > mejor_recall:
        return True
    return puntajes["recall"] == mejor_recall and puntajes["auc"] > mejor_auc


def exportar_pesos_cpu(modelo, ruta) -> Path:
    """Guarda SOLO los pesos del modelo, en CPU: el entregable para SP2.

    `mejor.pt` y `ultimo.pt` son checkpoints de entrenamiento: mezclan los
    pesos con el estado del optimizador, el historial y los contadores de
    paciencia, y sus tensores viven en el dispositivo donde se entreno (CUDA,
    en Colab). SP2 tiene que servir el modelo en la CPU de un VPS sin CUDA, y
    alli ese .pt fallaria con `RuntimeError` al deserializar tensores CUDA.

    Este archivo se carga sin sorpresas con
    `torch.load(ruta, map_location="cpu", weights_only=True)` y se pasa
    directo a `load_state_dict`.
    """
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    estado_cpu = {
        clave: (valor.detach().cpu().clone() if torch.is_tensor(valor) else valor)
        for clave, valor in modelo.state_dict().items()
    }
    torch.save(estado_cpu, ruta)
    return ruta


def entrenar(modelo, cargador_train, cargador_val, cfg, dispositivo,
             dir_checkpoints, reanudar: bool = False) -> dict:
    """Entrena en dos fases y devuelve el historial y el mejor checkpoint.

    Fase 1: solo la cabeza (backbone congelado), `cfg.epocas_cabeza` epocas.
    Fase 2: ajuste fino de los ultimos bloques, `cfg.epocas_ajuste` epocas.
    En ambas, early stopping por Recall en validacion con `cfg.paciencia`.
    El Recall es el del umbral elegido por `elegir_umbral` para esa epoca
    (ver `_puntuar_epoca`), con el AUC como desempate (ver `_es_mejor`).

    Con `reanudar=True`, si existe `ultimo.pt` en `dir_checkpoints` se retoma
    el entrenamiento desde alli -pesos, estado del optimizador, epoca, fase,
    historial y contador de paciencia- en vez de empezar de cero. Es lo que
    el spec §8 promete para una caida de sesion en Colab; sin esto, el
    checkpoint por epoca se escribia y no lo leia nadie. Si no hay checkpoint,
    `reanudar=True` arranca de cero sin quejarse.

    Al retornar, `modelo` queda restaurado a los pesos de la MEJOR epoca (los
    de `ruta_mejor_checkpoint`), no a los de la ultima ejecutada: el early
    stopping corta precisamente cuando el recall dejo de mejorar, asi que sin
    esta restauracion el modelo en memoria quedaria casi siempre peor que el
    guardado como "mejor".
    """
    # Al reanudar se vuelve a sembrar con la misma semilla: la secuencia de
    # aumento de datos arranca de nuevo desde el principio en vez de continuar
    # donde estaba. Es una divergencia conocida y aceptada respecto de una
    # corrida sin caida; reproducirla exigiria serializar el estado del
    # generador global en cada checkpoint, y el valor no lo justifica.
    fijar_semillas(cfg.semilla)

    dir_checkpoints = Path(dir_checkpoints)
    dir_checkpoints.mkdir(parents=True, exist_ok=True)
    modelo = modelo.to(dispositivo)
    ruta_ultimo = dir_checkpoints / NOMBRE_ULTIMO
    ruta_mejor = dir_checkpoints / NOMBRE_MEJOR

    # peso de la clase positiva: compensa el desbalance 22,5 / 77,5.
    # Se leen las etiquetas del manifiesto cuando existe: iterar el cargador
    # cargaria y transformaria las 18 000 imagenes solo para contar etiquetas.
    etiquetas_train = _etiquetas_de(cargador_train)
    positivos = max(float(etiquetas_train.sum()), 1.0)
    negativos = max(float(len(etiquetas_train) - positivos), 1.0)
    peso_positivo = torch.tensor([negativos / positivos], device=dispositivo)
    criterio = nn.BCEWithLogitsLoss(pos_weight=peso_positivo)

    fases = [("cabeza", cfg.epocas_cabeza, cfg.lr_cabeza),
             ("ajuste", cfg.epocas_ajuste, cfg.lr_ajuste)]
    nombres_fase = [nombre for nombre, _, _ in fases]

    historial: list[dict] = []
    # mejor_recall/mejor_auc/mejor_epoca son el registro GLOBAL del
    # entrenamiento: se conservan entre fases (el mejor de todo el
    # entrenamiento, cabeza o ajuste). sin_mejora, en cambio, se reinicia al
    # entrar a cada fase: es un contador de paciencia POR FASE.
    mejor_recall, mejor_auc, mejor_epoca = -1.0, -1.0, -1
    estado_previo = None
    fase_inicial = 0

    if reanudar and ruta_ultimo.exists():
        # map_location: un checkpoint escrito en Colab lleva tensores CUDA y
        # tiene que poder releerse tambien en una maquina sin GPU.
        estado_previo = torch.load(ruta_ultimo, map_location=dispositivo,
                                   weights_only=False)
        modelo.load_state_dict(estado_previo["modelo"])
        historial = list(estado_previo["historial"])
        mejor_recall = float(estado_previo.get("mejor_recall", -1.0))
        mejor_auc = float(estado_previo.get("mejor_auc", -1.0))
        mejor_epoca = int(estado_previo.get("mejor_epoca", -1))
        fase_inicial = nombres_fase.index(estado_previo["fase"])
        if int(estado_previo.get("sin_mejora", 0)) >= cfg.paciencia:
            # Esa fase ya habia terminado por paciencia agotada cuando cayo la
            # sesion: reanudar debe empezar en la SIGUIENTE, no repetirla, y
            # el estado de su optimizador ya no sirve para nada.
            fase_inicial += 1
            estado_previo = None

    # Cuantas epocas lleva hecha cada fase, para retomar la que quedo a medias.
    epocas_hechas = Counter(registro["fase"] for registro in historial)

    for indice_fase, (nombre_fase, n_epocas, lr) in enumerate(fases):
        if n_epocas <= 0 or indice_fase < fase_inicial:
            continue
        hechas = epocas_hechas.get(nombre_fase, 0)
        if hechas >= n_epocas:
            continue  # fase completada en la corrida anterior
        if nombre_fase == "ajuste":
            # Ajuste fino completo por defecto: dejar fijos casi todos los
            # bloques limita cuanto puede adaptarse la red a una imagen de
            # un solo canal y estadistica muy distinta a ImageNet.
            if getattr(cfg, "descongelar_todo", False):
                descongelar_todo(modelo)
            else:
                descongelar_para_ajuste(modelo, getattr(cfg, "bloques_ajuste", 3))
        parametros = [p for p in modelo.parameters() if p.requires_grad]
        optimizador = torch.optim.Adam(parametros, lr=lr)
        # Coseno sobre las epocas de la fase: baja la tasa de forma suave
        # para afinar al final en vez de rebotar alrededor del minimo.
        planificador = (
            torch.optim.lr_scheduler.CosineAnnealingLR(optimizador, T_max=max(n_epocas, 1))
            if getattr(cfg, "usar_scheduler", False) else None
        )
        # Paciencia propia de esta fase: agotarla en "cabeza" significa que
        # la cabeza convergio, que es la señal para pasar al ajuste fino, no
        # para abandonar el entrenamiento completo.
        sin_mejora = 0
        if estado_previo is not None and estado_previo["fase"] == nombre_fase:
            # Reanudar de verdad: sin el estado de Adam el momento arranca en
            # blanco, que es reiniciar con pesos calientes, no reanudar.
            optimizador.load_state_dict(estado_previo["optimizador"])
            sin_mejora = int(estado_previo.get("sin_mejora", 0))
            if planificador is not None and estado_previo.get("planificador"):
                planificador.load_state_dict(estado_previo["planificador"])

        for _ in range(hechas, n_epocas):
            perdida = _pasada_de_entrenamiento(
                modelo, cargador_train, criterio, optimizador, dispositivo)
            y_true, y_score = evaluar_epoca(modelo, cargador_val, dispositivo)
            puntajes = _puntuar_epoca(y_true, y_score, cfg)
            registro = {"fase": nombre_fase, "epoca": len(historial),
                        "perdida": perdida, **puntajes}
            historial.append(registro)

            mejora = _es_mejor(puntajes, mejor_recall, mejor_auc)
            if mejora:
                mejor_recall = puntajes["recall"]
                mejor_auc = puntajes["auc"]
                mejor_epoca = registro["epoca"]
                sin_mejora = 0
            else:
                sin_mejora += 1

            # El planificador avanza al cerrar la epoca y ANTES de guardar:
            # si se guardara antes de avanzar, el checkpoint registraria la
            # tasa de la epoca anterior y al reanudar se repetiria un paso.
            if planificador is not None:
                planificador.step()

            # Checkpoint fiel para reanudar tras una caida de sesion: el
            # estado del optimizador (si no, Adam reanuda con el momento en
            # blanco, que no es reanudar sino reiniciar con pesos calientes),
            # la fase, el historial acumulado y los contadores de mejor y de
            # paciencia, que son lo que decide donde retomar.
            estado = {"modelo": modelo.state_dict(),
                      "optimizador": optimizador.state_dict(),
                      "epoca": registro["epoca"], "fase": nombre_fase,
                      "metricas": dict(registro), "historial": historial,
                      "mejor_recall": mejor_recall, "mejor_auc": mejor_auc,
                      "mejor_epoca": mejor_epoca, "sin_mejora": sin_mejora,
                      "planificador": (planificador.state_dict()
                                       if planificador is not None else None)}
            torch.save(estado, ruta_ultimo)
            if mejora:
                torch.save(estado, ruta_mejor)
            if sin_mejora >= cfg.paciencia:
                # Corta SOLO esta fase (break), nunca toda la funcion
                # (return): el bucle exterior debe poder continuar con la
                # fase siguiente.
                break

        # La reanudacion solo alimenta a la primera fase que llega a correr.
        estado_previo = None

    # Restaura el modelo a los pesos de la mejor epoca antes de devolverlo:
    # sin esto, `modelo` queda en el estado de la ULTIMA epoca ejecutada, y el
    # early stopping corta justo cuando el recall dejo de mejorar, asi que ese
    # estado es casi siempre peor que el mejor guardado. `ruta_mejor` solo
    # puede faltar si ninguna fase llego a correr una sola epoca (epocas_
    # cabeza y epocas_ajuste ambas <= 0); en ese caso no hay nada que
    # restaurar.
    if ruta_mejor.exists():
        estado_mejor = torch.load(ruta_mejor, map_location=dispositivo,
                                  weights_only=False)
        modelo.load_state_dict(estado_mejor["modelo"])

    ruta_pesos_cpu = exportar_pesos_cpu(modelo, dir_checkpoints / NOMBRE_PESOS_CPU)

    return {"mejor_recall": mejor_recall, "mejor_auc": mejor_auc,
            "mejor_epoca": mejor_epoca, "historial": historial,
            "ruta_mejor_checkpoint": ruta_mejor,
            "ruta_ultimo_checkpoint": ruta_ultimo,
            "ruta_pesos_cpu": ruta_pesos_cpu}
