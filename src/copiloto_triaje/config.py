"""Configuracion unica del pipeline. Toda aleatoriedad pasa por `semilla`."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Parametros del pipeline. Los valores por defecto son los del spec."""

    raiz_datos: Path
    zip_rsna: Path
    semilla: int = 42
    tam_imagen: int = 224
    proporciones: tuple[float, float, float] = (0.70, 0.15, 0.15)
    lote: int = 32
    epocas_cabeza: int = 3
    epocas_ajuste: int = 7
    lr_cabeza: float = 1e-3
    lr_ajuste: float = 1e-4
    paciencia: int = 3
    especificidad_objetivo: float = 0.75
    especificidad_minima: float = 0.70
    recall_objetivo: float = 0.85

    def __post_init__(self) -> None:
        total = sum(self.proporciones)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Las proporciones deben sumar 1, suman {total}")
        if self.semilla is None:
            raise ValueError("La semilla es obligatoria para poder reproducir")

    @property
    def dir_png(self) -> Path:
        return self.raiz_datos / "png"

    @property
    def dir_manifiestos(self) -> Path:
        return self.raiz_datos / "manifiestos"

    @property
    def dir_checkpoints(self) -> Path:
        return self.raiz_datos / "checkpoints"
