"""El nucleo: bytes de un DICOM a evidencia de imagen.

No sabe de HTTP, de MCP ni de Docker. Las dos puertas del servidor son
envoltorios sobre `Motor.clasificar`, y esa simetria es lo unico que impide
que el respaldo REST y el camino MCP digan cosas distintas sobre la misma
radiografia.
"""
from __future__ import annotations

import time
from pathlib import Path

import pydicom.errors
import torch
from PIL import Image

from copiloto_triaje.datos.dataset import construir_transformaciones
from copiloto_triaje.datos.dicom import leer_dicom_desde_bytes
from copiloto_triaje.datos.preparacion import edad_en_anios
from copiloto_triaje.modelo.arquitectura import construir_modelo
from copiloto_triaje.servicio.calibracion import Calibrador

EDAD_MINIMA = 18
EDAD_MAXIMA = 100


class ErrorDeInferencia(Exception):
    """Un fallo que el profesional puede entender y accionar.

    Lleva `codigo` para que las dos puertas lo traduzcan al formato que
    corresponda sin tener que interpretar el texto del mensaje.
    """

    def __init__(self, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.codigo = codigo


class Motor:
    """Modelo cargado y listo para clasificar. Se construye una vez al arrancar."""

    def __init__(self, modelo, calibrador: Calibrador, umbral: float,
                 tam_imagen: int, nombre_modelo: str, auc_validacion: float):
        self.modelo = modelo
        self.modelo.eval()
        self.calibrador = calibrador
        self.umbral = float(umbral)
        self.tam_imagen = int(tam_imagen)
        self.nombre_modelo = nombre_modelo
        self.auc_validacion = float(auc_validacion)
        # Una sola instancia: construir_transformaciones en cada peticion
        # recrearia los mismos objetos por nada.
        self._transformar = construir_transformaciones(tam_imagen,
                                                       entrenamiento=False)

    @classmethod
    def cargar(cls, ruta_pesos, ruta_calibrador, umbral: float,
               auc_validacion: float, arquitectura: str = "efficientnet_b0",
               tam_imagen: int = 320) -> "Motor":
        """Carga como lo hara el contenedor: en CPU y con weights_only.

        `auc_validacion` es obligatorio y sin default: es una cifra que se
        muestra al profesional como afirmacion de calidad del modelo
        cargado, no un dato ligado al codigo sino a LOS PESOS. Un default
        silencioso (0,883 o cualquier otro) sobreviviria a un reentrenamiento
        sin que nadie lo actualizara, y cada respuesta seguiria citando la
        cifra vieja como si fuera la del modelo nuevo.
        """
        ruta_pesos, ruta_calibrador = Path(ruta_pesos), Path(ruta_calibrador)
        if not ruta_pesos.is_file():
            raise FileNotFoundError(f"No estan los pesos en {ruta_pesos}")
        if not ruta_calibrador.is_file():
            raise FileNotFoundError(f"No esta el calibrador en {ruta_calibrador}")
        modelo = construir_modelo(arquitectura, congelar_backbone=False,
                                  preentrenado=False)
        modelo.load_state_dict(torch.load(ruta_pesos, map_location="cpu",
                                          weights_only=True))
        return cls(modelo, Calibrador.desde_json(ruta_calibrador), umbral,
                   tam_imagen, f"{arquitectura}_{tam_imagen}px", auc_validacion)

    def _tensor_desde_arreglo(self, arreglo) -> torch.Tensor:
        """La conversion, en UN solo sitio: aqui y solo aqui se decide como
        un arreglo de pixeles se convierte en el tensor que ve el modelo.

        No existe una segunda copia (ni siquiera para pruebas): un metodo
        auxiliar aparte que solo llamaran las pruebas invitaria a que esa
        prueba verificara un camino distinto del que usa `clasificar`, que es
        justo el fallo que la prueba de preprocesamiento existe para impedir.
        Por eso esa prueba captura el tensor que `clasificar` le pasa
        REALMENTE al modelo (espiando `modelo.forward`), no el resultado de
        llamar a este metodo por separado.
        """
        return self._transformar(
            Image.fromarray(arreglo).convert("RGB")).unsqueeze(0)

    def clasificar(self, datos_dicom: bytes) -> dict:
        comienzo = time.perf_counter()
        try:
            arreglo, meta = leer_dicom_desde_bytes(datos_dicom)
        # AttributeError NO esta en esta tupla a proposito: `datos/dicom.py`
        # documenta que los errores de PROGRAMACION deben propagarse
        # ruidosamente, no camuflarse como "DICOM invalido". Si estuviera,
        # un typo dentro de `leer_dicom_desde_bytes` haria que TODA peticion
        # dijera al profesional que su radiografia esta corrupta.
        except (pydicom.errors.InvalidDicomError, ValueError,
                TypeError) as exc:
            raise ErrorDeInferencia(
                "dicom_invalido",
                f"El fichero no es un DICOM legible: {exc}") from exc

        edad = edad_en_anios(meta.get("edad"))
        if edad is None:
            raise ErrorDeInferencia(
                "edad_desconocida",
                "La cabecera DICOM no declara una edad interpretable. No se "
                "asume que el paciente sea adulto: pide la edad al profesional.")
        if not EDAD_MINIMA <= edad <= EDAD_MAXIMA:
            raise ErrorDeInferencia(
                "fuera_de_alcance",
                f"El paciente tiene {edad} anios y el modelo solo es valido "
                f"entre {EDAD_MINIMA} y {EDAD_MAXIMA}.")

        # El arreglo ya esta leido: se reusa en vez de volver a decodificar el
        # DICOM. _tensor_desde_arreglo es el UNICO lugar que hace esta
        # conversion; no hay una segunda copia que pueda desincronizarse.
        tensor = self._tensor_desde_arreglo(arreglo)
        with torch.no_grad():
            cruda = float(torch.sigmoid(self.modelo(tensor).view(-1))[0])

        return {
            "probabilidad_cruda": round(cruda, 4),
            # SIN redondear estas dos. `Calibrador.calibrar` las acota a los
            # extremos SOSTENIDOS de la curva de calibracion -con el
            # calibrador desplegado, 0,004608 y 0,956522- para que nadie
            # reciba mas certeza que la que los datos de validacion
            # respaldan. Redondear aqui deshace esa cota igual que antes
            # deshacia la vieja (round(1e-6, 4) == 0.0), solo que ahora el
            # valor que se perderia es una probabilidad de verdad y no un
            # epsilon. SP4 calcula odds = p/(1-p) sobre
            # `probabilidad_calibrada` y multiplica las odds previas por
            # `razon_de_verosimilitud`: cualquier numero que este redondeo
            # fabricara seria certeza -de ausencia o de presencia de
            # neumonia- que la radiografia no respalda.
            "probabilidad_calibrada": self.calibrador.calibrar(cruda),
            "razon_de_verosimilitud": self.calibrador.razon_de_verosimilitud(cruda),
            "umbral": round(self.umbral, 4),
            "clasificacion": ("opacidad_probable" if cruda >= self.umbral
                              else "sin_opacidad_probable"),
            "edad_paciente": edad,
            "modelo": self.nombre_modelo,
            "auc_validacion": self.auc_validacion,
            "milisegundos": round((time.perf_counter() - comienzo) * 1000, 1),
        }
