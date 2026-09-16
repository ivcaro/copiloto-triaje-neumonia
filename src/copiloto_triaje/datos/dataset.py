"""Dataset de PyTorch que lee SIEMPRE desde un manifiesto, nunca del
directorio: asi la particion es un artefacto explicito y auditable."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

MEDIA_IMAGENET = [0.485, 0.456, 0.406]
DESV_IMAGENET = [0.229, 0.224, 0.225]


def construir_transformaciones(tam_imagen: int, entrenamiento: bool):
    """Transformaciones de imagen. El aumento solo se aplica en entrenamiento.

    No se usa volteo horizontal: la lateralidad cardiaca es informacion
    clinica real y voltearla produciria anatomia imposible.

    NOTA: RandomAffine y ColorJitter usan el generador global de torch porque
    la API v1 de torchvision no acepta generadores propios. La reproducibilidad
    depende de sembrar torch.manual_seed con la semilla de configuracion.
    """
    pasos = [transforms.Resize((tam_imagen, tam_imagen))]
    if entrenamiento:
        pasos.append(transforms.RandomAffine(degrees=7, translate=(0.05, 0.05)))
        pasos.append(transforms.ColorJitter(brightness=0.15, contrast=0.15))
    pasos.append(transforms.ToTensor())
    pasos.append(transforms.Normalize(MEDIA_IMAGENET, DESV_IMAGENET))
    return transforms.Compose(pasos)


class DatasetRadiografias(Dataset):
    """Lee las imagenes listadas en un manifiesto y devuelve (tensor, etiqueta)."""

    def __init__(self, manifiesto: pd.DataFrame, dir_png, tam_imagen: int = 224,
                 entrenamiento: bool = False):
        self.manifiesto = manifiesto.reset_index(drop=True)
        self.dir_png = Path(dir_png)
        self.transformaciones = construir_transformaciones(tam_imagen, entrenamiento)

    def __len__(self) -> int:
        return len(self.manifiesto)

    def __getitem__(self, indice: int):
        fila = self.manifiesto.iloc[indice]
        ruta = self.dir_png / fila["archivo_png"]
        imagen = Image.open(ruta).convert("RGB")  # 3 canales: la red es de ImageNet
        x = self.transformaciones(imagen)
        y = torch.tensor(float(fila["etiqueta"]), dtype=torch.float32)
        return x, y
