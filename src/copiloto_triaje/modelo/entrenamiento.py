"""Bucle de entrenamiento en dos fases con early stopping por RECALL.

El criterio de parada observa el Recall en validacion, no la exactitud ni
la perdida: con 22,5% de positivos, la exactitud premia al modelo que
nunca detecta a nadie.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from copiloto_triaje.modelo.arquitectura import descongelar_para_ajuste
from copiloto_triaje.modelo.evaluacion import metricas_binarias


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


def entrenar(modelo, cargador_train, cargador_val, cfg, dispositivo,
             dir_checkpoints) -> dict:
    """Entrena en dos fases y devuelve el historial y el mejor checkpoint.

    Fase 1: solo la cabeza (backbone congelado), `cfg.epocas_cabeza` epocas.
    Fase 2: ajuste fino de los ultimos bloques, `cfg.epocas_ajuste` epocas.
    En ambas, early stopping por Recall en validacion con `cfg.paciencia`.

    Al retornar, `modelo` queda restaurado a los pesos de la MEJOR epoca por
    Recall en validacion (los de `ruta_mejor_checkpoint`), no a los de la
    ultima epoca ejecutada: el early stopping corta precisamente cuando el
    recall dejo de mejorar, asi que sin esta restauracion el modelo en
    memoria quedaria casi siempre peor que el guardado como "mejor".
    """
    # Se siembra el generador GLOBAL de torch aqui, antes de cualquier otra
    # operacion aleatoria (incluida la de `_etiquetas_de` mas abajo, que ya
    # puede iterar un cargador barajado). RandomAffine y ColorJitter -el
    # aumento de datos de `datos/dataset.py`- consumen ese generador global
    # porque la API de torchvision no admite pasarles uno propio; lo mismo
    # hace el barajado (shuffle) del DataLoader cuando no se le da un
    # `generator` explicito. Sin esta siembra, dos corridas con la misma
    # `cfg.semilla` no serian reproducibles.
    torch.manual_seed(cfg.semilla)

    dir_checkpoints = Path(dir_checkpoints)
    dir_checkpoints.mkdir(parents=True, exist_ok=True)
    modelo = modelo.to(dispositivo)

    # peso de la clase positiva: compensa el desbalance 22,5 / 77,5.
    # Se leen las etiquetas del manifiesto cuando existe: iterar el cargador
    # cargaria y transformaria las 18 000 imagenes solo para contar etiquetas.
    etiquetas_train = _etiquetas_de(cargador_train)
    positivos = max(float(etiquetas_train.sum()), 1.0)
    negativos = max(float(len(etiquetas_train) - positivos), 1.0)
    peso_positivo = torch.tensor([negativos / positivos], device=dispositivo)
    criterio = nn.BCEWithLogitsLoss(pos_weight=peso_positivo)

    historial: list[dict] = []
    # mejor_recall/mejor_epoca son el registro GLOBAL del entrenamiento: se
    # conservan entre fases (el mejor de todo el entrenamiento, cabeza o
    # ajuste). sin_mejora, en cambio, se reinicia al entrar a cada fase (ver
    # mas abajo): es un contador de paciencia POR FASE.
    mejor_recall, mejor_epoca = -1.0, -1
    ruta_mejor = dir_checkpoints / "mejor.pt"

    fases = [("cabeza", cfg.epocas_cabeza, cfg.lr_cabeza),
             ("ajuste", cfg.epocas_ajuste, cfg.lr_ajuste)]

    for nombre_fase, n_epocas, lr in fases:
        if n_epocas <= 0:
            continue
        if nombre_fase == "ajuste":
            descongelar_para_ajuste(modelo)
        parametros = [p for p in modelo.parameters() if p.requires_grad]
        optimizador = torch.optim.Adam(parametros, lr=lr)
        # Paciencia propia de esta fase: agotarla en "cabeza" significa que
        # la cabeza convergio, que es la señal para pasar al ajuste fino, no
        # para abandonar el entrenamiento completo.
        sin_mejora = 0

        for epoca in range(n_epocas):
            perdida = _pasada_de_entrenamiento(
                modelo, cargador_train, criterio, optimizador, dispositivo)
            y_true, y_score = evaluar_epoca(modelo, cargador_val, dispositivo)
            m = metricas_binarias(y_true, (y_score >= 0.5).astype(int))
            registro = {"fase": nombre_fase, "epoca": len(historial),
                        "perdida": perdida, "recall": m["recall"],
                        "especificidad": m["especificidad"]}
            historial.append(registro)

            # Checkpoint fiel para reanudar tras una caida de sesion: el
            # estado del optimizador (si no, Adam reanuda con el momento en
            # blanco, que no es reanudar sino reiniciar con pesos calientes),
            # la fase y el historial acumulado hasta esta epoca.
            estado = {"modelo": modelo.state_dict(), "optimizador": optimizador.state_dict(),
                      "epoca": registro["epoca"], "fase": nombre_fase,
                      "metricas": m, "historial": historial}
            torch.save(estado, dir_checkpoints / "ultimo.pt")

            if m["recall"] > mejor_recall:
                mejor_recall, mejor_epoca, sin_mejora = m["recall"], registro["epoca"], 0
                torch.save(estado, ruta_mejor)
            else:
                sin_mejora += 1
                if sin_mejora >= cfg.paciencia:
                    # Corta SOLO esta fase (break), nunca toda la funcion
                    # (return): el bucle exterior debe poder continuar con la
                    # fase siguiente.
                    break

    # Restaura el modelo a los pesos de la mejor epoca antes de devolverlo:
    # sin esto, `modelo` queda en el estado de la ULTIMA epoca ejecutada, y el
    # early stopping corta justo cuando el recall dejo de mejorar, asi que ese
    # estado es casi siempre peor que el mejor guardado. `ruta_mejor` solo
    # puede faltar si ninguna fase llego a correr una sola epoca (epocas_
    # cabeza y epocas_ajuste ambas <= 0); en ese caso no hay nada que
    # restaurar.
    if ruta_mejor.exists():
        estado_mejor = torch.load(ruta_mejor, weights_only=False)
        modelo.load_state_dict(estado_mejor["modelo"])

    return {"mejor_recall": mejor_recall, "mejor_epoca": mejor_epoca,
            "historial": historial, "ruta_mejor_checkpoint": ruta_mejor}
