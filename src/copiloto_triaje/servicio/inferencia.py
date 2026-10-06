"""El nucleo: bytes de un DICOM a evidencia de imagen.

No sabe de HTTP, de MCP ni de Docker. Las dos puertas del servidor son
envoltorios sobre `Motor.clasificar`, y esa simetria es lo unico que impide
que el respaldo REST y el camino MCP digan cosas distintas sobre la misma
radiografia.
"""
from __future__ import annotations

import time
from collections.abc import Mapping
from numbers import Real
from pathlib import Path

import numpy as np
import pydicom.errors
import torch
import torch.nn.functional as F
from PIL import Image

from copiloto_triaje.datos.dataset import construir_transformaciones
from copiloto_triaje.datos.dicom import leer_dicom_desde_bytes
from copiloto_triaje.datos.preparacion import edad_en_anios
from copiloto_triaje.modelo.arquitectura import construir_modelo
from copiloto_triaje.servicio.calibracion import Calibrador
from copiloto_triaje.servicio.heckerling import (
    HallazgosInvalidos, combinacion, validar_hallazgos,
)

EDAD_MINIMA = 18
EDAD_MAXIMA = 100

# Las unicas vistas con umbral propio (SP5-C1 §4): la `ViewPosition` de la
# cabecera. Cualquier otra -una lateral, una etiqueta vacia o ausente- usa el
# umbral global.
VISTAS_CON_UMBRAL = ("PA", "AP")


def _validar_umbrales_por_vista(umbrales) -> dict:
    """Los umbrales por vista, comprobados y COPIADOS a un `dict` propio.

    Exactamente `PA` y `AP`, cada una un numero estrictamente entre 0 y 1: la
    misma guarda que `prevalencia_local`, y por la misma razon. `nan` no cumple
    ninguna comparacion e `inf` no esta por debajo de 1, asi que caen en la
    misma que un 1,5; un texto no es un umbral aunque `float()` se lo coma, y
    `True` y `False` valen 1 y 0. Todo es `ValueError` y dice QUE esta mal: lo
    lee quien despliega, al arrancar, no un profesional con una placa delante.

    Se guarda una copia porque guardar el mapa de quien llama dejaria que
    cambiarlo despues se saltara esta validacion.
    """
    if not isinstance(umbrales, Mapping):
        raise ValueError("umbrales_por_vista tiene que ser un mapa con las "
                         f"claves 'PA' y 'AP', y es {umbrales!r}")
    detalle = []
    faltan = [repr(v) for v in VISTAS_CON_UMBRAL if v not in umbrales]
    sobran = [repr(k) for k in umbrales if k not in VISTAS_CON_UMBRAL]
    if faltan:
        detalle.append("falta " + ", ".join(faltan))
    if sobran:
        detalle.append("sobra " + ", ".join(sobran))
    if detalle:
        raise ValueError("umbrales_por_vista tiene que llevar exactamente las "
                         "claves 'PA' y 'AP': " + "; ".join(detalle))
    validos = {}
    for vista in VISTAS_CON_UMBRAL:
        valor = umbrales[vista]
        # La comparacion va sobre el valor tal cual y la conversion a `float`,
        # despues: un entero enorme se rechaza aqui, no revienta en `float()`.
        if not isinstance(valor, Real) or not 0.0 < valor < 1.0:
            raise ValueError(
                f"umbrales_por_vista[{vista!r}] vale {valor!r} y tiene que ser "
                "un numero estrictamente entre 0 y 1")
        validos[vista] = float(valor)
    return validos


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
                 tam_imagen: int, nombre_modelo: str, auc_validacion: float,
                 prevalencia_local: float,
                 umbrales_por_vista: Mapping[str, float] | None = None):
        self.modelo = modelo
        self.modelo.eval()
        self.calibrador = calibrador
        self.umbral = float(umbral)
        self.tam_imagen = int(tam_imagen)
        self.nombre_modelo = nombre_modelo
        self.auc_validacion = float(auc_validacion)
        # La probabilidad previa de la combinacion bayesiana (SP4 §5). Es un
        # parametro de despliegue con la misma disciplina que `auc_validacion`:
        # obligatorio, sin default, y se le muestra al profesional en cada
        # informe con combinacion.
        self.prevalencia_local = float(prevalencia_local)
        if not 0.0 < self.prevalencia_local < 1.0:
            raise ValueError("prevalencia_local tiene que ser una probabilidad "
                             f"estrictamente entre 0 y 1, y es {prevalencia_local!r}")
        # El umbral por vista (SP5-C1 §4): una mitigacion de equidad, y un
        # parametro de despliegue OPCIONAL y APAGADO por defecto. Con `None`,
        # la respuesta es la de SP3 y SP4 clave por clave. Encenderlo lo decide
        # la institucion, no el codigo: por eso no hay valores por defecto.
        self.umbrales_por_vista = (
            None if umbrales_por_vista is None
            else _validar_umbrales_por_vista(umbrales_por_vista))
        # Una sola instancia: construir_transformaciones en cada peticion
        # recrearia los mismos objetos por nada.
        self._transformar = construir_transformaciones(tam_imagen,
                                                       entrenamiento=False)

    @classmethod
    def cargar(cls, ruta_pesos, ruta_calibrador, umbral: float,
               auc_validacion: float, prevalencia_local: float,
               arquitectura: str = "efficientnet_b0",
               tam_imagen: int = 320,
               umbrales_por_vista: Mapping[str, float] | None = None) -> "Motor":
        """Carga como lo hara el contenedor: en CPU y con weights_only.

        `auc_validacion` es obligatorio y sin default: es una cifra que se
        muestra al profesional como afirmacion de calidad del modelo
        cargado, no un dato ligado al codigo sino a LOS PESOS. Un default
        silencioso (0,883 o cualquier otro) sobreviviria a un reentrenamiento
        sin que nadie lo actualizara, y cada respuesta seguiria citando la
        cifra vieja como si fuera la del modelo nuevo.
        `prevalencia_local` es obligatoria por la misma razon.

        `umbrales_por_vista` es lo contrario: opcional, y apagado si no se da.
        Se pasa al constructor tal cual, que lo valida.
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
                   tam_imagen, f"{arquitectura}_{tam_imagen}px", auc_validacion,
                   prevalencia_local, umbrales_por_vista=umbrales_por_vista)

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

    @staticmethod
    def _leer_placa_de_adulto(datos_dicom: bytes) -> tuple[np.ndarray, dict, int]:
        """Lo que `clasificar` y `mapa_de_calor` hacen IGUAL antes de tocar el
        modelo: leer el DICOM y comprobar que el paciente es un adulto. Devuelve
        `(pixeles, metadatos, edad)` o levanta el `ErrorDeInferencia` que toque.

        Esta en UN solo sitio para que las dos rechacen lo mismo, con el mismo
        codigo y las mismas palabras: copiarlo dejaria que divergieran, y un
        mapa de calor de un paciente que el modelo no admite seria dar por
        valido lo que no lo es.
        """
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
                "asume que el paciente sea adulto: compruebe la edad en la "
                "cabecera del estudio.")
        if not EDAD_MINIMA <= edad <= EDAD_MAXIMA:
            raise ErrorDeInferencia(
                "fuera_de_alcance",
                f"El paciente tiene {edad} años y el modelo solo es válido "
                f"entre {EDAD_MINIMA} y {EDAD_MAXIMA}.")
        return arreglo, meta, edad

    def clasificar(self, datos_dicom: bytes, hallazgos: Mapping | None = None) -> dict:
        comienzo = time.perf_counter()
        # Los hallazgos se validan ANTES de tocar el DICOM: es barato, y si
        # vienen mal el error es de quien llama -nuestro bot-, no de la placa.
        validados = None
        if hallazgos is not None:
            try:
                validados = validar_hallazgos(hallazgos)
            except HallazgosInvalidos as exc:
                raise ErrorDeInferencia("hallazgos_invalidos", str(exc)) from exc
        arreglo, meta, edad = self._leer_placa_de_adulto(datos_dicom)

        # El umbral que decide la etiqueta del cribado (SP5-C1 §4). Sin
        # `umbrales_por_vista` es SIEMPRE el global y no se mira la vista: la
        # respuesta es la de hoy. Con el, la `ViewPosition` de la cabecera
        # -sin espacios ni minusculas- elige el de PA o el de AP, y cualquier
        # otra cosa deja el global. Solo la etiqueta cambia: la evidencia de
        # abajo y la combinacion no dependen de la vista.
        umbral = self.umbral
        por_vista = None
        if self.umbrales_por_vista is not None:
            vista = (meta.get("vista") or "").strip().upper()
            if vista in self.umbrales_por_vista:
                umbral = self.umbrales_por_vista[vista]
                por_vista = {"vista": vista, "aplicado": True}
            else:
                por_vista = {"vista": None, "aplicado": False}

        # El arreglo ya esta leido: se reusa en vez de volver a decodificar el
        # DICOM. _tensor_desde_arreglo es el UNICO lugar que hace esta
        # conversion; no hay una segunda copia que pueda desincronizarse.
        tensor = self._tensor_desde_arreglo(arreglo)
        with torch.no_grad():
            cruda = float(torch.sigmoid(self.modelo(tensor).view(-1))[0])

        rv = self.calibrador.razon_de_verosimilitud(cruda)
        salida = {
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
            "razon_de_verosimilitud": rv,
            # `umbral` es el APLICADO. Con el parametro, `umbral_por_vista` va
            # justo detras; sin el, no hay tal clave.
            "umbral": round(umbral, 4),
            **({} if por_vista is None else {"umbral_por_vista": por_vista}),
            "clasificacion": ("opacidad_probable" if cruda >= umbral
                              else "sin_opacidad_probable"),
            "edad_paciente": edad,
            "modelo": self.nombre_modelo,
            "auc_validacion": self.auc_validacion,
        }
        if validados is not None:
            # SP4 (§9.2): el bloque va DENTRO de la misma respuesta y solo si
            # se pidio. Sin `hallazgos` la respuesta es la de SP3, clave por
            # clave, y eso es un criterio de aceptacion.
            salida["combinacion"] = combinacion(self.prevalencia_local,
                                                validados, rv)
        salida["milisegundos"] = round((time.perf_counter() - comienzo) * 1000, 1)
        return salida

    def mapa_de_calor(self, datos_dicom: bytes) -> np.ndarray:
        """El mapa de calor de la placa: Grad-CAM sobre el ultimo bloque
        convolucional, respecto del logit de opacidad (SP5-C1 §5).

        Las activaciones de ese bloque, ponderadas por el gradiente del logit
        respecto de ellas (su media en el espacio, por canal), con ReLU,
        interpoladas a `tam_imagen` x `tam_imagen` y divididas por su maximo.
        Devuelve un `numpy.ndarray` float32 de esa forma con valores en [0, 1];
        la app lo reescala a la imagen original para superponerlo. Si no hay
        nada que atribuir -gradiente nulo, o un mapa que queda por debajo de 0 en
        todas partes- es una matriz de ceros, no `nan`.

        Rechaza lo mismo que `clasificar`, con los mismos codigos, porque
        comparte con ella la lectura y las comprobaciones de edad.

        Solo vale para EfficientNet-B0, la unica red que se despliega: compone su
        forward a mano -`features`, `avgpool`, `classifier`- y una prueba vigila
        que esa composicion sea la del modelo.
        """
        arreglo, _, _ = self._leer_placa_de_adulto(datos_dicom)
        # Por el mismo camino que `clasificar`: el mapa es el de la imagen que
        # el modelo ve, no el de otra.
        x = self._tensor_desde_arreglo(arreglo)

        # SIN ganchos (`register_forward_hook`) a proposito: el `Motor` es uno
        # solo y la app lo comparte entre sesiones, que corren en hilos. Un
        # gancho registrado aqui estaria vivo mientras OTRA sesion llama a
        # `clasificar` y se dispararia dentro de ella, mezclando sus activaciones
        # con las de este mapa; quitarlo en un `finally` no cierra esa ventana.
        # Por eso el forward se compone a mano -las activaciones del ultimo
        # bloque quedan en una variable local- y el gradiente se pide con
        # `autograd.grad`, que ademas no deja `.grad` en ningun parametro. Nada
        # del modelo se toca: ni el modo, ni los pesos, ni sus `requires_grad`.
        #
        # La imagen se marca con `requires_grad` para que haya grafo hasta las
        # activaciones: con el backbone congelado (las pruebas) ningun parametro
        # de `features` lo exige, y sin esto no habria por donde derivar. Con el
        # desplegado (`cargar`, sin congelar) da igual. `enable_grad` porque quien
        # llama puede estar bajo `torch.no_grad()`, como `clasificar`.
        x.requires_grad_(True)
        with torch.enable_grad():
            activaciones = self.modelo.features(x)
            logit = self.modelo.classifier(
                torch.flatten(self.modelo.avgpool(activaciones), 1)).view(-1)[0]
            (gradientes,) = torch.autograd.grad(logit, activaciones)

        with torch.no_grad():
            pesos = gradientes.mean(dim=(2, 3), keepdim=True)
            mapa = torch.relu((pesos * activaciones).sum(dim=1, keepdim=True))
            mapa = F.interpolate(mapa, size=(self.tam_imagen, self.tam_imagen),
                                 mode="bilinear", align_corners=False)[0, 0]
            # Se normaliza DESPUES de interpolar: la interpolacion baja el
            # maximo, y asi el punto mas caliente del mapa que sale vale 1. Con
            # maximo 0 el mapa ya es de ceros y se queda como esta; dividir daria
            # 0/0 en todos los puntos.
            maximo = mapa.max()
            if maximo > 0:
                mapa = mapa / maximo
        return np.asarray(mapa.numpy(), dtype=np.float32)
