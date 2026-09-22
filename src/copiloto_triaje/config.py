"""Configuracion unica del pipeline. Toda aleatoriedad pasa por `semilla`.

Los valores por defecto son los de la SEGUNDA corrida, revisados el
21-sep-2026 con la evidencia de la primera. La primera corrida (224 px,
MobileNetV3, 7 epocas) dio AUC 0,845 y recall 76,6%, por debajo del minimo
de 0,85 y 80% que el propio spec exige, asi que las elecciones que llevaban
ahi se cambiaron. La justificacion de cada cambio esta en
`docs/mejoras-2026-09-21.md`.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ARQUITECTURAS = ("densenet121", "mobilenet_v3_large", "efficientnet_b0")


@dataclass(frozen=True)
class Config:
    """Parametros del pipeline."""

    raiz_datos: Path
    zip_rsna: Path
    semilla: int = 42

    # --- datos y modelo -------------------------------------------------
    # 320 en vez de 224: las opacidades son sutiles y difusas, y reducir una
    # placa de 1024 a 224 tira la mayor parte de esa senal. Es la palanca de
    # mas efecto conocido en radiografia de torax.
    tam_imagen: int = 320
    # DenseNet121 es la arquitectura de CheXNet, el referente del area. Se
    # eligio MobileNetV3 por el limite de 4 s en CPU que impone SP2, pero la
    # medicion real dio 0,023 s: quedaba el 99,4% del presupuesto sin usar.
    arquitectura: str = "densenet121"
    proporciones: tuple[float, float, float] = (0.70, 0.15, 0.15)
    lote: int = 24
    # El alcance entregado declara ADULTOS. El analisis exploratorio encontro
    # que el 4,78% del padron son menores de 18 anios (desde 1 ano) y cinco
    # pacientes tienen edades imposibles de 148 a 155. Se filtran: entrenar
    # con ellos contradiria lo entregado, y la neumonia pediatrica se ve
    # distinta en la placa. Quedan 25 403 pacientes (95,2%), con la tasa de
    # positivos practicamente igual: 22,15% frente a 22,53%.
    edad_minima: int = 18
    edad_maxima: int = 100

    # --- entrenamiento --------------------------------------------------
    # La primera corrida paro a las 7 epocas con el AUC todavia subiendo.
    epocas_cabeza: int = 4
    epocas_ajuste: int = 20
    lr_cabeza: float = 1e-3
    lr_ajuste: float = 2e-4
    paciencia: int = 5
    # Ajuste fino completo: descongelar solo los 3 ultimos bloques deja fija
    # casi toda la representacion de ImageNet, que no transfiere del todo a
    # rayos X (un solo canal, estadistica distinta).
    descongelar_todo: bool = True
    bloques_ajuste: int = 3  # solo se usa si descongelar_todo es False
    usar_scheduler: bool = True

    # --- criterios de aceptacion (spec §2) -------------------------------
    especificidad_objetivo: float = 0.75
    especificidad_minima: float = 0.70
    recall_objetivo: float = 0.85
    recall_minimo: float = 0.80

    def __post_init__(self) -> None:
        total = sum(self.proporciones)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Las proporciones deben sumar 1, suman {total}")
        if self.semilla is None:
            raise ValueError("La semilla es obligatoria para poder reproducir")
        if self.arquitectura not in ARQUITECTURAS:
            raise ValueError(
                f"Arquitectura '{self.arquitectura}' no soportada; "
                f"opciones: {', '.join(ARQUITECTURAS)}"
            )
        if self.recall_minimo > self.recall_objetivo:
            raise ValueError("El recall minimo no puede superar al objetivo")
        if self.especificidad_minima > self.especificidad_objetivo:
            raise ValueError("La especificidad minima no puede superar a la objetivo")
        if self.edad_minima > self.edad_maxima:
            raise ValueError("La edad minima no puede superar a la maxima")

    @property
    def dir_png(self) -> Path:
        return self.raiz_datos / "png"

    @property
    def dir_manifiestos(self) -> Path:
        return self.raiz_datos / "manifiestos"

    @property
    def dir_checkpoints(self) -> Path:
        return self.raiz_datos / "checkpoints"
