"""Construccion del modelo de clasificacion.

La eleccion de arquitectura se revisó el 21-sep-2026 con datos medidos. La
primera corrida uso MobileNetV3-Large porque SP2 exige servir la inferencia
en la CPU del VPS en menos de 4 segundos; la medicion real dio 0,023 s por
imagen, es decir el 0,6% del presupuesto. Con 175x de margen, el limite de
sistema deja de ser vinculante y se puede usar una red mas capaz.

Por defecto se usa DenseNet121, la arquitectura de CheXNet -el trabajo de
referencia en deteccion de neumonia sobre radiografia de torax-. Las tres
arquitecturas soportadas comparten la misma forma (un `features` secuencial
mas un clasificador), que es lo que permite congelar y descongelar por
bloques con un solo codigo.
"""
from __future__ import annotations

import torch.nn as nn
from torchvision.models import (
    DenseNet121_Weights,
    EfficientNet_B0_Weights,
    MobileNet_V3_Large_Weights,
    densenet121,
    efficientnet_b0,
    mobilenet_v3_large,
)

# nombre -> (constructor, pesos de ImageNet)
_CATALOGO = {
    "densenet121": (densenet121, DenseNet121_Weights.IMAGENET1K_V1),
    "mobilenet_v3_large": (mobilenet_v3_large, MobileNet_V3_Large_Weights.IMAGENET1K_V1),
    "efficientnet_b0": (efficientnet_b0, EfficientNet_B0_Weights.IMAGENET1K_V1),
}


def _reemplazar_cabeza(modelo: nn.Module) -> None:
    """Deja el clasificador con UNA sola salida (logit), para BCEWithLogitsLoss.

    DenseNet expone `classifier` como una capa lineal suelta; MobileNet y
    EfficientNet lo exponen como un Sequential cuya ultima capa es la lineal.
    """
    cabeza = modelo.classifier
    if isinstance(cabeza, nn.Linear):
        modelo.classifier = nn.Linear(cabeza.in_features, 1)
    else:
        cabeza[-1] = nn.Linear(cabeza[-1].in_features, 1)


def construir_modelo(
    arquitectura: str = "densenet121",
    congelar_backbone: bool = True,
    preentrenado: bool = True,
) -> nn.Module:
    """Red preentrenada en ImageNet con una unica salida binaria."""
    if arquitectura not in _CATALOGO:
        raise ValueError(
            f"Arquitectura '{arquitectura}' no soportada; "
            f"opciones: {', '.join(_CATALOGO)}"
        )
    constructor, pesos_imagenet = _CATALOGO[arquitectura]
    modelo = constructor(weights=pesos_imagenet if preentrenado else None)
    _reemplazar_cabeza(modelo)
    if congelar_backbone:
        for parametro in modelo.features.parameters():
            parametro.requires_grad = False
    return modelo


def descongelar_para_ajuste(modelo: nn.Module, n_bloques: int = 3) -> None:
    """Descongela los ultimos n bloques del extractor para el ajuste fino.

    Con n_bloques <= 0 no descongela nada: `bloques[-0:]` seria la lista
    entera, que es lo contrario de lo que el nombre promete.
    """
    if n_bloques <= 0:
        return
    bloques = list(modelo.features)
    for bloque in bloques[-n_bloques:]:
        for parametro in bloque.parameters():
            parametro.requires_grad = True


def descongelar_todo(modelo: nn.Module) -> None:
    """Hace entrenable el modelo entero: ajuste fino completo.

    Las caracteristicas de ImageNet transfieren a rayos X, pero no del todo:
    son imagenes de un solo canal, con una estadistica muy distinta. Dejar
    fija casi toda la representacion limita cuanto puede aprender la red.
    """
    for parametro in modelo.parameters():
        parametro.requires_grad = True


def contar_parametros_entrenables(modelo: nn.Module) -> int:
    return sum(p.numel() for p in modelo.parameters() if p.requires_grad)
