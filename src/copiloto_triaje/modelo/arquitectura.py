"""Construccion del modelo de clasificacion.

Se elige MobileNetV3-Large sobre ResNet50 por una razon de sistema, no de
exactitud: SP2 exige servir la inferencia en la CPU del VPS en menos de 4
segundos. Entrenar primero el modelo que se va a poder servir evita
rehacer el trabajo.
"""
from __future__ import annotations

import torch.nn as nn
from torchvision.models import MobileNet_V3_Large_Weights, mobilenet_v3_large


def construir_modelo(congelar_backbone: bool = True, preentrenado: bool = True) -> nn.Module:
    """MobileNetV3-Large con una unica salida (logit) para clasificacion binaria."""
    pesos = MobileNet_V3_Large_Weights.IMAGENET1K_V1 if preentrenado else None
    modelo = mobilenet_v3_large(weights=pesos)
    entradas = modelo.classifier[-1].in_features
    modelo.classifier[-1] = nn.Linear(entradas, 1)
    if congelar_backbone:
        for parametro in modelo.features.parameters():
            parametro.requires_grad = False
    return modelo


def descongelar_para_ajuste(modelo: nn.Module, n_bloques: int = 3) -> None:
    """Descongela los ultimos n bloques del extractor para el ajuste fino."""
    bloques = list(modelo.features)
    for bloque in bloques[-n_bloques:]:
        for parametro in bloque.parameters():
            parametro.requires_grad = True


def contar_parametros_entrenables(modelo: nn.Module) -> int:
    return sum(p.numel() for p in modelo.parameters() if p.requires_grad)
