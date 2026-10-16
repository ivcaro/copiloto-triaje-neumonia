# -*- coding: utf-8 -*-
"""La interfaz de demostración del copiloto (SP5-C1, spec §3).

Es la puerta de evaluación del MISMO sistema que usa el bot del profesional: el
mismo `Motor` (`servicio/inferencia.py`), con los mismos pesos, la misma calibración
y la misma combinación con la regla de Heckerling. Calcula en su propio proceso: no
llama al servidor, a n8n ni a Telegram, y la placa no sale de aquí (D2).

USO, con el paquete instalado, DESDE LA CARPETA `app/`:

    cd app
    streamlit run app.py

Desde `app/` y no desde la raíz del repositorio: Streamlit lee `.streamlit/config.toml` del
directorio desde el que se LANZA, y desde la raíz no hay ninguno. Se pierden, en silencio,
la telemetría apagada, el límite de subida del servidor (de 5 MB pasa a 200; la app
comprueba además los 5 MB ella misma), las trazas ocultas en el navegador y la barra de
herramientas reducida. La imagen Docker (`app/Dockerfile`) ya la lanza desde `app/`.

EL ENTORNO, con la misma disciplina que `servidor/arrancar.py`:

    AUC_VALIDACION     obligatoria y sin valor por defecto: el AUC en validación de
                       los pesos que se cargan, y la app lo enseña.
    PREVALENCIA_LOCAL  obligatoria y sin valor por defecto: la probabilidad de
                       partida de la combinación con la regla clínica.
    UMBRAL             el umbral global del cribado. Por defecto, el de
                       app/assets/metricas.json, que es el mismo 0,4258 del servidor:
                       así las métricas de «Acerca de» son las de ese umbral.
    RUTA_PESOS         los pesos; por defecto, servidor/pesos_modelo_cpu.pt (no se
                       versionan). Es también la variable de PRUEBA: tests/test_app.py
                       la apunta a una red con pesos aleatorios, y la app la carga por
                       `Motor.cargar` igual que los de verdad. No hay otro camino.
    RUTA_CALIBRADOR    por defecto, servidor/calibrador.json.

Los valores del despliegue son los de servidor/docker-compose.yml. Sin una variable
obligatoria, o con un valor imposible, la app no calcula y dice qué declarar.

El umbral por vista (experimental) usa los de app/assets/metricas.json, su fuente
única, en un segundo `Motor` construido sobre el MISMO modelo y el MISMO calibrador:
nunca se reasigna el atributo de un `Motor`, que se saltaría su validación (R9).
Encendido, se llama a los dos, para decir si la etiqueta cambia (R17).

Los textos que el bot ya tiene -los avisos y los rechazos- se copian de él, y
están en `DEL_BOT`: tests/test_app.py comprueba que siguen siendo los suyos.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import math
import os
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import NamedTuple

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from matplotlib import colormaps
from PIL import Image

from copiloto_triaje.datos.dicom import (
    LADO_MAXIMO_DE_LA_PLACA, PlacaNoEvaluable, leer_dicom_desde_bytes,
)
from copiloto_triaje.servicio.heckerling import (
    PREVALENCIA_COHORTE, PULSO_CORTE_LPM, RV_POR_PUNTUACION, TEMPERATURA_CORTE_C,
)
from copiloto_triaje.servicio.inferencia import (
    EDAD_MAXIMA, EDAD_MINIMA, ErrorDeInferencia, Motor,
)

REGISTRO = logging.getLogger("copiloto_triaje.app")

CARPETA_APP = Path(__file__).resolve().parent
REPO = CARPETA_APP.parent
METRICAS = CARPETA_APP / "assets" / "metricas.json"
CARPETA_EJEMPLOS = CARPETA_APP / "assets" / "ejemplos"
LICENCIAS = CARPETA_APP / "assets" / "LICENCIAS.md"
PESOS_POR_DEFECTO = REPO / "servidor" / "pesos_modelo_cpu.pt"
CALIBRADOR_POR_DEFECTO = REPO / "servidor" / "calibrador.json"

# 5 MB: el MISMO límite que el servidor (`MAXIMO_BYTES` de servicio/aplicacion.py,
# 5 * 1024 * 1024), escrito aquí y no importado porque aplicacion.py arrastra FastAPI
# y MCP. La app lo comprueba ella misma (R14): `app/.streamlit/config.toml` dice lo
# mismo, pero Streamlit lo lee del directorio desde el que se LANZA, así que con
# `streamlit run app/app.py` desde la raíz no se aplica.
TAMANO_MAXIMO_MB = 5
TAMANO_MAXIMO_BYTES = TAMANO_MAXIMO_MB * 1024 * 1024

# Lo que la placa tiene que ser para que se calcule (R24, R27 y R28) ya no se decide aquí:
# es la regla del motor, `comprobar_que_se_puede_evaluar` en datos/dicom.py (SP5-B4), que
# `leer_dicom_desde_bytes` aplica antes de descodificar un solo píxel, con sus límites
# (`LADO_MAXIMO_DE_LA_PLACA`). La app traduce cada motivo a sus mensajes:
# `mensaje_de_la_placa`.

# Límites de INTERFAZ de los hallazgos (spec §3): lo que se puede teclear. No son
# rangos clínicos de nada; solo impiden un 380 °C. Streamlit no deja enviar un valor
# fuera de ellos.
TEMPERATURA_MIN, TEMPERATURA_MAX = 30.0, 45.0
FRECUENCIA_MIN, FRECUENCIA_MAX = 20, 250

# La opción del control no se llama «Prueba con ejemplo»: ese es el BOTÓN que calcula
# el ejemplo elegido (el mínimo del curso lo pide), y dos rótulos iguales en la misma
# columna confundirían.
FUENTE_EJEMPLO = "Usar un ejemplo"
FUENTE_FICHERO = "Subir un DICOM"
BOTON_EJEMPLO = "Prueba con ejemplo"

# Los ejemplos (spec §6), por lo que dice su FUENTE y no por lo que diga el modelo
# (R15): el modelo no se ha medido con ellos y puede discrepar.
EJEMPLOS = {
    "normal_pa": "Normal, PA — según su fuente",
    "neumonia_pa": "Neumonía, PA — según su fuente",
    "neumonia_ap": "Neumonía, AP — según su fuente",
    "rechazado_menor": "Rechazado: menor de edad (edad inventada)",
}
AVISO_EJEMPLOS = (
    "Los ejemplos son radiografías de Wikimedia Commons (CC0), de fuera de RSNA: el "
    "modelo no se ha medido con ellos, y su resultado puede discrepar de lo que dice "
    "su fuente. Sirven para ver cómo funciona la app, no para evaluarla.")

# La placa se enseña con su lado mayor como mucho a esto: basta para la pantalla, y
# colorear una placa de 3 000 px en cada recarga no aporta nada.
LADO_MAXIMO_EN_PANTALLA = 1024
MAPA_DE_COLOR = "turbo"
OPACIDAD_DEL_MAPA = 50          # %, al abrir el resultado

# Una RV entre 0,5 y 2 cambia la probabilidad poco, y rara vez de forma importante
# (Jaeschke R, Guyatt GH, Sackett DL. JAMA 1994;271:703-7). Es lo que la app dice
# cuando la imagen «apenas mueve la probabilidad» (R15).
RV_POCO_INFORMATIVA = (0.5, 2.0)

# --------------------------------------------------------------------------
# Los textos del bot del profesional (n8n/copiloto-profesional.json), COPIADOS (R12):
# los de su nodo «Desenlace» aquí, y el de «Leer respuesta» debajo. Las frases que el
# bot arma por trozos están por trozos, y la app las arma igual. La prueba de los
# textos busca cada uno en el bot: si el bot cambia una frase, se entera.
# --------------------------------------------------------------------------
DEL_BOT = {
    # §8 de SP3: el informe.
    "cribado": "CRIBADO — ",
    "opacidad_probable": "opacidad probable",
    "sin_opacidad_probable": "sin opacidad probable",
    "puntuacion": "puntuación ",
    "umbral": " umbral ",
    "punto_medido": "; punto orientado a detectar, sens. ",
    "esp": " / esp. ",
    "evidencia": "EVIDENCIA DE LA IMAGEN — ",
    "multiplica": "multiplica por ",
    "a_favor": " las probabilidades a favor de una opacidad compatible",
    "reduce": "reduce a ",
    "reduce_a_favor": "× las probabilidades a favor de una opacidad compatible",
    "calibrada": " (probabilidad calibrada ",
    "positivo_sin_apoyo": (
        "⚠️ El cribado marca esta placa por estar orientado a detectar, pero la "
        "imagen en sí no apoya el diagnóstico. Decide la clínica."),
    "negativo": (
        "⚠️ El modelo mide opacidad en la placa, no neumonía. Un resultado negativo "
        "no la descarta. Decide usted."),
    "descargo": "Esto no es un diagnóstico.",
    # §8 de SP4: el bloque combinado y su aviso de dependencia.
    "sin_combinar": ("SIN COMBINAR — faltan signos de la exploración, así que no hay "
                     "puntuación de Heckerling."),
    "combinado": "COMBINADO — ",
    "de_probabilidad": " de probabilidad de opacidad compatible",
    "prevalencia": "(prevalencia ",
    "por_clinica": " % × clínica ",
    "por_imagen": " × imagen ",
    "heckerling": "Heckerling ",
    "dos_puntuaciones": " de 5, según tenga asma o no",
    "de_5": " de 5",
    "menos_de_1": "menos de 1 %",
    "mas_de_99": "más de 99 %",
    "lados_distintos": (
        "⚠️ Que la clínica apunte en el mismo sentido que la imagen o en el contrario "
        "depende de si tiene asma, y además no son pruebas independientes: "),
    "opuestos": ("⚠️ La clínica y la imagen apuntan en sentidos opuestos, y además no "
                 "son pruebas independientes: "),
    "la_cifra": "la cifra",
    "la_horquilla": "la horquilla",
    "orientativa": " es orientativa. Decide usted.",
    "misma_consolidacion": (
        "⚠️ La auscultación y la imagen miran la misma consolidación, así que no son "
        "pruebas independientes: "),
    "puede_exagerar": "la cifra puede exagerar. Decide usted.",
    "supone": " supone que cada una aporta información nueva, y el ",
    "decide": ". Decide usted.",
    "absorbe_imagen": "que la auscultación no añade nada sobre la imagen",
    "absorbe_clinica": "que la imagen no añade nada sobre la auscultación",
    "absorbe_mixta": "que solo cuenta la más informativa de las dos",
    # §4.4: los hallazgos, con las palabras del informe.
    "grados": " °C",
    "lpm": " lpm",
    "crepitantes": "crepitantes ",
    "murmullo_disminuido": "murmullo disminuido",
    "murmullo_normal": "murmullo normal",
    "asma_si": "asma sí",
    "asma_no": "sin asma",
    "asma_no_se": "asma: no sabe",
    # §9: los rechazos, en lenguaje llano.
    "no_pude_leer": "No pude leer esa radiografía.",
    "fuera_de_alcance": "NO PROCEDE — fuera del alcance del modelo.",
    "edad_desconocida": "NO PROCEDE — no se puede saber la edad.",
    "coletilla_edad": (
        f"No hay resultado que dar: el modelo se validó entre {EDAD_MINIMA} y "
        f"{EDAD_MAXIMA} años, y aplicarlo fuera de ahí no significaría nada. Decida "
        "clínicamente."),
    "tamano": f"El archivo supera los {TAMANO_MAXIMO_MB} MB.",
}
# La frase del bot para lo que el servidor no supo leer y no trajo código (un DICOM
# truncado): la que la app da ante cualquier fallo inesperado del cálculo (R18). Sin
# su punto final, porque la app le añade «, o pruebe con un ejemplo.»: el fallo puede
# no ser un recorte, y probar un ejemplo siempre se puede.
DEL_BOT_LECTURA = {
    "sin_codigo": ("No pude interpretar el contenido del fichero. Si lo recortó al "
                   "enviarlo, vuelva a exportarlo completo"),
}

ETIQUETAS = {"opacidad_probable": DEL_BOT["opacidad_probable"],
             "sin_opacidad_probable": DEL_BOT["sin_opacidad_probable"]}
POSITIVA = "opacidad_probable"
ABSORBE = {"imagen": DEL_BOT["absorbe_imagen"], "clinica": DEL_BOT["absorbe_clinica"],
           "mixta": DEL_BOT["absorbe_mixta"]}
ASMA_EN_EL_INFORME = {"si": DEL_BOT["asma_si"], "no": DEL_BOT["asma_no"],
                      "no_se": DEL_BOT["asma_no_se"]}
# Lo que se lee en los campos y en la tabla del historial; el CSV guarda las claves.
SI_NO = {"si": "sí", "no": "no"}
ASMA = {"si": "sí", "no": "no", "no_se": "no sé"}

# Los textos propios de la app: lo que el bot no tiene. Cortos y en su registro.
AYUDA_DICOM = ("Compruebe que es el DICOM de la placa y que está completo (una foto o "
               "un JPEG no sirven), o pruebe con un ejemplo.")
AYUDA_TAMANO = "Pruebe con un DICOM más pequeño o con un ejemplo."
HALLAZGOS_INVALIDOS = ("Los hallazgos de la exploración no son válidos. Revíselos, o "
                       "quite los hallazgos para calcular solo con la imagen.")
SIN_FICHERO = f"Suba un fichero DICOM, o elija «{FUENTE_EJEMPLO}»."
# Lo que se dice de un fichero que no es un DICOM: lo del motor para `dicom_invalido`,
# y lo de la app cuando no hay metainformación que leer (R28, motivo
# `sin_metainformacion`), con las mismas palabras.
NO_ES_UN_DICOM = "\n\n".join([DEL_BOT["no_pude_leer"], AYUDA_DICOM])
# R28 (motivo `deflated`): con la sintaxis Deflated, TODO el conjunto de datos tras el
# grupo 0002 va comprimido con zlib, y pydicom lo infla entero en cuanto se le pide la
# cabecera (`dcmread(..., stop_before_pixels=True)`): un fichero de 398 KiB con 400 MiB
# de ceros dentro llevó el pico de memoria de 54 a 854 MiB. La regla del motor mira la
# sintaxis antes, en el grupo 0002, que nunca va comprimido, y no lo abre.
RECHAZO_DEFLATED = (
    "Este fichero viene comprimido entero (en DICOM, «Deflated Explicit VR Little "
    "Endian»), y la app no lo descomprime: podría ocupar cientos de veces lo que pesa. "
    "Así que no se calcula nada.\n\n"
    "Expórtelo sin comprimir, o pruebe con un ejemplo.")
INESPERADO = "\n\n".join([DEL_BOT["no_pude_leer"],
                          f"{DEL_BOT_LECTURA['sin_codigo']}, o pruebe con un ejemplo."])
# R24 y R27: una placa que el modelo vería mal NO se calcula, ni con aviso: una cifra
# que se sabe que no vale no se enseña («ninguna rama de error emite una
# probabilidad»). El motor la convierte con `Image.fromarray(arreglo).convert("RGB")`,
# que con más de 8 bits SATURA todo lo que pasa de 255 (medido en la revisión: una
# neumonía en 16 bits baja de 0,91 a 0,48, y el mapa cae fuera del pulmón), no invierte
# una MONOCHROME1 y no lleva tope de memoria (unos 600 bytes en RLE que declaran 60 000
# × 60 000 hacen que `pixel_array` intente reservar 3,35 GiB). Por eso se decide con la
# CABECERA, antes de descodificar un solo píxel: desde SP5-B4 lo decide la regla del
# motor (datos/dicom.py), que es también la del bot, y estos son sus motivos dichos con
# las palabras de la app (`mensaje_de_la_placa`).
RECHAZO_BITS = (
    "Esta placa es de {bits}: los visores la enseñan bien, pero el modelo se entrenó con "
    "placas de 8 bits, como las de RSNA, y hoy no convierte las demás: {como}. Así que "
    "no se calcula nada.\n\n"
    "Expórtela en 8 bits, o pruebe con un ejemplo.")
RECHAZO_INVERTIDA = (
    "Esta placa guarda la escala de grises invertida: los visores la enseñan bien, pero "
    "el modelo se entrenó con placas como las de RSNA, con el hueso claro, y hoy no las "
    "invierte: la vería al revés, con el hueso oscuro. Así que no se calcula nada.\n\n"
    "Expórtela con la escala de grises normal (en DICOM, MONOCHROME2), o pruebe con un "
    "ejemplo.")
RECHAZO_COLOR = (
    "Esta placa no está en escala de grises: los visores la enseñan bien, pero el modelo "
    "se entrenó con placas en grises, como las de RSNA, y hoy no convierte las demás. Así "
    "que no se calcula nada.\n\n"
    "Expórtela en escala de grises (en DICOM, MONOCHROME2), o pruebe con un ejemplo.")
RECHAZO_LADO = (
    "Esta placa declara {filas} × {columnas} píxeles, y la app no lee placas de más de "
    "{lado} de lado (una placa de tórax digital no llega a tanto). Así que no se calcula "
    "nada.\n\n"
    "Expórtela más pequeña, o pruebe con un ejemplo.")
RECHAZO_CUADROS = (
    "Este fichero trae {cuadros} imágenes, y la app evalúa una placa sola. Así que no se "
    "calcula nada.\n\n"
    "Exporte solo la placa de tórax, o pruebe con un ejemplo.")
AVISO_DEL_MAPA = ("⚠️ El mapa señala dónde mira el modelo, no por qué acierta: no es "
                  "una explicación de la puntuación ni marca lesiones.")
MAPA_DE_CEROS = "El mapa vale cero en toda la placa: no hay ninguna zona que señalar."
MAPA_FALLIDO = ("No se pudo calcular el mapa de calor de esta placa (se ha registrado). "
                "El resultado no depende de él.")
PLACA_ILEGIBLE = "No se puede enseñar esta placa."

# Las columnas del historial y de su CSV (R10). Ni la imagen, ni el nombre del fichero
# subido, ni nada de su cabecera (un DICOM real puede traer nombre, identificador o
# fechas): el origen es «ejemplo: <nombre>» o «fichero subido», y lo demás sale de la
# respuesta del motor y de los hallazgos que se teclearon. Tampoco la edad, que es
# de la cabecera.
COLUMNAS_HISTORIAL = (
    "n", "origen", "umbral_por_vista", "vista_del_umbral", "clasificacion",
    "probabilidad_cruda", "umbral", "probabilidad_calibrada", "razon_de_verosimilitud",
    "temperatura_c", "frecuencia_cardiaca", "crepitantes", "murmullo_disminuido",
    "asma", "puntuacion_heckerling", "rv_clinica", "prevalencia", "combinado_minima",
    "combinado_maxima",
)


# --------------------------------------------------------------------------
# Números, como los escribe el bot
# --------------------------------------------------------------------------
def _dec(x, n: int) -> str:
    """`x` con `n` decimales y coma decimal: el `dec` del bot. Redondea la mitad hacia
    arriba sobre el valor exacto, como `toFixed`, y no al par como `format`."""
    cuantizado = Decimal(float(x)).quantize(Decimal(1).scaleb(-n),
                                            rounding=ROUND_HALF_UP)
    return f"{cuantizado:.{n}f}".replace(".", ",")


def _como_el_campo(x) -> float:
    """La temperatura con un decimal, como la enseña su campo (M1): Streamlit la formatea
    con «%.1f», que en el navegador redondea como `toFixed` -la mitad hacia arriba sobre
    el valor exacto: 38,25 es exacto en binario y el campo enseña 38.3- y como `_dec`
    la escribe en el informe. Es lo que se manda al motor: con 37,84 el campo dice 37,8,
    que no pasa del corte, y puntuar con 37,84 sería puntuar un número que no se ve. El
    `round` de Python iría al par (38,2)."""
    return float(Decimal(float(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _prob(x) -> str:
    """Una probabilidad con dos decimales, sin llegar nunca a 0,00 ni a 1,00 (el
    `prob` del bot): la calibración ya acota, y un 0,00 sería certeza fabricada."""
    v = float(x)
    if 0 < v < 0.005:
        return "< 0,01"
    if 0.995 < v < 1:
        return "> 0,99"
    return _dec(v, 2)


def _rv(v) -> str:
    """Una razón de verosimilitud: dos decimales por debajo de 10, uno por encima."""
    return _dec(v, 2 if v < 10 else 1)


def _pct(x) -> str:
    """Un porcentaje entero, nunca 0 % ni 100 % (el `pct` del bot). `floor(+0,5)` es
    el `Math.round` de JavaScript; el `round` de Python redondea al par."""
    v = float(x)
    if v < 0.01:
        return "< 1 %"
    if v > 0.99:
        return "> 99 %"
    return f"{math.floor(v * 100 + 0.5)} %"


def _cifra(x) -> str:
    """Un límite de interfaz o de regla: entero si lo es (30, no 30,0)."""
    return str(int(x)) if float(x).is_integer() else _dec(x, 1)


def _con_ic(valor, ic, decimales=2) -> str:
    """`0,88 (0,86–0,90)`, o una raya si no se pudo medir (el JSON lleva `null`)."""
    if valor is None:
        return "—"
    texto = _dec(valor, decimales)
    if ic:
        texto += f" ({_dec(ic[0], decimales)}–{_dec(ic[1], decimales)})"
    return texto


def _entero(n) -> str:
    return f"{int(n):,}".replace(",", " ")


def _cambio(medida: str, antes, despues) -> str:
    """`la especificidad baja de 0,88 a 0,65`: el verbo sale de las dos cifras, no se
    escribe a mano, así que la frase es cierta con cualquier JSON."""
    a, d = _dec(antes, 2), _dec(despues, 2)
    if a == d:
        return f"la {medida} se queda en {a}"
    return f"la {medida} {'sube' if despues > antes else 'baja'} de {a} a {d}"


# --------------------------------------------------------------------------
# La configuración, los motores y las métricas
# --------------------------------------------------------------------------
class ConfiguracionInvalida(Exception):
    """El entorno no deja arrancar. El mensaje lo lee quien despliega."""


class Configuracion(NamedTuple):
    ruta_pesos: str
    ruta_calibrador: str
    umbral: float
    auc_validacion: float
    prevalencia_local: float


FALTA = {
    "AUC_VALIDACION": (
        "Falta la variable de entorno AUC_VALIDACION. Es el AUC en validación de los "
        "pesos que se cargan y la app lo enseña, así que no tiene valor por defecto "
        "(como en el servidor): uno silencioso sobreviviría a un reentrenamiento y "
        "seguiría citando la cifra vieja. Declárala al arrancar, con el valor de "
        "servidor/docker-compose.yml."),
    "PREVALENCIA_LOCAL": (
        "Falta la variable de entorno PREVALENCIA_LOCAL. Es la probabilidad de partida "
        "con la que se combina la regla clínica con la imagen, y la app la enseña, así "
        "que no tiene valor por defecto (como en el servidor). Declárala al arrancar, "
        "con el valor de servidor/docker-compose.yml."),
}


def _probabilidad_del_entorno(entorno, nombre, por_defecto=None, admite_uno=False):
    """El valor de la variable como número en (0, 1) -o (0, 1] si `admite_uno`-, o
    `ConfiguracionInvalida` diciendo qué pasa. Vacía cuenta como no declarada, como
    en el servidor. `nan` no cumple ninguna comparación y cae con un 1,5; un texto,
    también, con su mensaje y no con la traza de `float()`."""
    crudo = entorno.get(nombre, "")
    if not crudo.strip():
        if por_defecto is None:
            raise ConfiguracionInvalida(FALTA[nombre])
        return float(por_defecto)
    try:
        valor = float(crudo)
    except ValueError:
        valor = math.nan
    if not (0.0 < valor < 1.0 or (admite_uno and valor == 1.0)):
        raise ConfiguracionInvalida(
            f"{nombre} vale {crudo!r} y tiene que ser un número "
            + ("mayor que 0 y como mucho 1." if admite_uno
               else "estrictamente entre 0 y 1."))
    return valor


def leer_configuracion(entorno, umbral_por_defecto) -> Configuracion:
    return Configuracion(
        ruta_pesos=entorno.get("RUTA_PESOS", "").strip() or str(PESOS_POR_DEFECTO),
        ruta_calibrador=(entorno.get("RUTA_CALIBRADOR", "").strip()
                         or str(CALIBRADOR_POR_DEFECTO)),
        umbral=_probabilidad_del_entorno(entorno, "UMBRAL", umbral_por_defecto),
        auc_validacion=_probabilidad_del_entorno(entorno, "AUC_VALIDACION",
                                                 admite_uno=True),
        prevalencia_local=_probabilidad_del_entorno(entorno, "PREVALENCIA_LOCAL"),
    )


class Motores(NamedTuple):
    """Los dos `Motor` de la app, sobre el MISMO modelo y el MISMO calibrador: el del
    umbral global y el del umbral por vista (R9). Y la huella de los pesos, para
    comprobar que las métricas de «Acerca de» son las suyas."""
    un_umbral: Motor
    por_vista: Motor
    huella_de_los_pesos: str


@st.cache_resource(show_spinner="Cargando el modelo…", max_entries=1)
def cargar_motores(ruta_pesos: str, ruta_calibrador: str, umbral: float,
                   auc_validacion: float, prevalencia_local: float,
                   umbrales_por_vista: tuple, clase_del_motor: int) -> Motores:
    """Una sola vez por proceso: el modelo pesa 16 MB y se comparte entre sesiones,
    que es lo que `mapa_de_calor` permite (no registra ganchos).

    `clase_del_motor` es `id(Motor)`, y está en la clave a propósito. Cuando cambia un
    fichero vigilado, Streamlit saca de `sys.modules` TODOS los módulos que vigila
    -los de la carpeta de la app y los de PYTHONPATH- y los vuelve a importar. Sin
    esto la caché seguiría dando el `Motor` del código viejo, que lanza el
    `ErrorDeInferencia` viejo: el `except` de la clase nueva no lo atraparía y un
    rechazo saldría como un fallo inesperado. Con ella, código nuevo, motor nuevo; y
    con `max_entries=1`, el viejo no se queda en memoria."""
    un_umbral = Motor.cargar(ruta_pesos, ruta_calibrador, umbral, auc_validacion,
                             prevalencia_local)
    # El constructor, y no reasignar `umbrales_por_vista` en el de arriba: así pasa
    # por la validación (exactamente PA y AP, en (0, 1)).
    por_vista = Motor(un_umbral.modelo, un_umbral.calibrador, un_umbral.umbral,
                      un_umbral.tam_imagen, un_umbral.nombre_modelo,
                      un_umbral.auc_validacion, un_umbral.prevalencia_local,
                      umbrales_por_vista=dict(umbrales_por_vista))
    huella = hashlib.sha256(Path(ruta_pesos).read_bytes()).hexdigest()
    return Motores(un_umbral, por_vista, huella)


def leer_metricas() -> dict:
    return json.loads(METRICAS.read_text(encoding="utf-8"))


def _subgrupo(metricas, nombre):
    return next((s for s in metricas["subgrupos"] if s["nombre"] == nombre), None)


# --------------------------------------------------------------------------
# La placa y el mapa de calor
# --------------------------------------------------------------------------
def placa_para_ver(arreglo: np.ndarray) -> np.ndarray:
    """La placa EXACTAMENTE como la recibe el modelo: `Image.fromarray(arreglo)` y a
    grises, que es cada canal del `convert("RGB")` del motor. Sin estirar nada: lo que
    se enseña nunca puede ser una placa más legible que la que se puntuó. (Las que
    llegan aquí son de 8 bits, en grises y no invertidas: R24 y R27; con más bits esto
    sería la placa saturada, que es justo lo que el modelo vería.) Con su lado mayor
    como mucho `LADO_MAXIMO_EN_PANTALLA`."""
    imagen = Image.fromarray(np.asarray(arreglo)).convert("L")
    imagen.thumbnail((LADO_MAXIMO_EN_PANTALLA, LADO_MAXIMO_EN_PANTALLA),
                     Image.Resampling.LANCZOS)
    return np.asarray(imagen)


def _rechazo_por_los_bits(bits: int, con_signo: bool = False) -> str:
    """`Esta placa es de 16 bits…`. Con más de 8 se satura todo lo que pasa de 255; con
    menos, o con signo, lo que vería el modelo no es la placa, sin más."""
    texto = f"{bits} bit{'' if bits == 1 else 's'}" + (" con signo" if con_signo else "")
    como = ("la vería saturada, casi blanca" if bits > 8 and not con_signo
            else "la vería mal")
    return RECHAZO_BITS.format(bits=texto, como=como)


def mensaje_de_la_placa(exc: PlacaNoEvaluable) -> str:
    """Una placa que el motor no puede evaluar (su regla, en datos/dicom.py), dicha con
    las palabras de la app: un mensaje por motivo, los de siempre (R24, R27 y R28). El
    texto del motor no se enseña: es para el servidor y sus registros.

    El signo solo se nombra con 8 bits: con más, la app habla de los bits, como cuando
    la cabecera ni lo miraba. Lo que no se puede leer -una cabecera a la que le falta un
    campo, un fichero sin la imagen, una compresión sin descodificador (`compresion`, que
    antes llegaba aquí como un RuntimeError)- y cualquier motivo que la app no conozca
    llevan el mensaje de R18, como hasta ahora."""
    if exc.motivo == "sin_metainformacion":
        return NO_ES_UN_DICOM
    if exc.motivo == "deflated":
        return RECHAZO_DEFLATED
    if exc.motivo == "tamano":
        return RECHAZO_LADO.format(filas=_entero(exc.filas),
                                   columnas=_entero(exc.columnas),
                                   lado=_entero(LADO_MAXIMO_DE_LA_PLACA))
    if exc.motivo == "cuadros":
        return RECHAZO_CUADROS.format(cuadros=_entero(exc.cuadros))
    if exc.motivo == "bits":
        return _rechazo_por_los_bits(exc.bits, exc.con_signo and exc.bits == 8)
    if exc.motivo == "fotometria":
        return RECHAZO_INVERTIDA
    if exc.motivo == "color":
        return RECHAZO_COLOR
    return INESPERADO


def superponer(placa: np.ndarray, mapa: np.ndarray, opacidad: float) -> np.ndarray:
    """La placa (grises, alto x ancho) en color con el mapa de calor encima.

    El mapa es el de la imagen que vio el modelo: la placa aplastada a tam x tam por
    `Resize((tam, tam))`, sin recorte. Por eso vuelve a la placa con un `resize`
    simple (R12). Cada píxel se tiñe en proporción a su valor en el mapa, hasta
    `opacidad` (de 0 a 1): donde el mapa vale 0 se ve la placa tal cual."""
    alto, ancho = placa.shape
    reescalado = np.asarray(
        Image.fromarray(np.asarray(mapa, dtype=np.float32))
        .resize((ancho, alto), Image.Resampling.BILINEAR), dtype=np.float32)
    reescalado = np.clip(reescalado, 0.0, 1.0)
    color = colormaps[MAPA_DE_COLOR](reescalado)[..., :3]
    gris = np.repeat(placa.astype(np.float32)[..., None] / 255.0, 3, axis=2)
    alfa = float(opacidad) * reescalado[..., None]
    mezcla = gris * (1.0 - alfa) + color * alfa
    return np.clip(np.rint(mezcla * 255.0), 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------
# El cálculo
# --------------------------------------------------------------------------
def _rechazo(exc: ErrorDeInferencia) -> str:
    """Un rechazo del motor en lenguaje llano, como lo dice el bot (§9 de SP3). El
    detalle del motor se relata SOLO en los dos rechazos por edad, cuyo texto compone
    nuestro código (un literal y un entero). El de `dicom_invalido` puede llevar el texto
    de pydicom sobre bytes ajenos (la cláusula genérica del motor), y el de
    `hallazgos_invalidos`, nombres de campo."""
    if exc.codigo == "fuera_de_alcance":
        return "\n\n".join([DEL_BOT["fuera_de_alcance"], str(exc),
                            DEL_BOT["coletilla_edad"]])
    if exc.codigo == "edad_desconocida":
        return "\n\n".join([DEL_BOT["edad_desconocida"], str(exc),
                            DEL_BOT["coletilla_edad"]])
    if exc.codigo == "hallazgos_invalidos":
        return HALLAZGOS_INVALIDOS
    # `dicom_invalido`, y cualquier código que esta app no conozca.
    return NO_ES_UN_DICOM


def calcular(motores: Motores, datos: bytes, hallazgos, por_vista: bool) -> dict:
    """Lo que la pantalla enseña de un cálculo: un rechazo (`{"rechazo": texto}`) o el
    resultado, con el del umbral global al lado si el interruptor está encendido, la
    placa y el mapa. Nunca deja escapar una excepción: lo inesperado se registra y
    se dice en llano (R18)."""
    if len(datos) > TAMANO_MAXIMO_BYTES:
        return {"rechazo": "\n\n".join([DEL_BOT["tamano"], AYUDA_TAMANO])}
    # R24, R27 y R28, ANTES del motor: el mismo lector que él, que aplica la regla del
    # motor (datos/dicom.py) antes de nada -la metainformación sin abrir el conjunto de
    # datos y la cabecera sin descodificar un solo píxel; después, la placa entera y la
    # segunda red- y da la placa que se enseña. Lo que la regla rechaza se dice con las
    # palabras de la app; lo que pydicom no sabe leer lo dice el motor, con su código
    # (`dicom_invalido`), o la red de R18.
    try:
        arreglo, _ = leer_dicom_desde_bytes(datos)
    except PlacaNoEvaluable as exc:
        return {"rechazo": mensaje_de_la_placa(exc)}
    except Exception:
        arreglo = None
    motor = motores.por_vista if por_vista else motores.un_umbral
    try:
        resultado = motor.clasificar(datos, hallazgos)
        # R17: encendido, también el del umbral global, para decir si la etiqueta
        # cambia. Se compara SU etiqueta, no la cruda redondeada de la respuesta.
        resultado_global = (motores.un_umbral.clasificar(datos, hallazgos)
                            if por_vista else None)
    except ErrorDeInferencia as exc:
        return {"rechazo": _rechazo(exc)}
    except Exception:
        # Lo que el motor no traduce (R18): un DICOM sin píxeles o con `Rows` vacío ya no
        # llega aquí (lo para la regla, arriba), pero sí cualquier otro fallo. Lo mismo
        # que hace el bot cuando el servidor cae sin código: se dice que no se pudo leer.
        REGISTRO.exception("el cálculo falló con una excepción que el motor no traduce")
        return {"rechazo": INESPERADO}
    salida = {"resultado": resultado, "resultado_global": resultado_global,
              "placa": None, "mapa": None, "aviso_mapa": None}
    try:
        salida["placa"] = placa_para_ver(arreglo)
    except Exception:
        REGISTRO.exception("no se pudo preparar la placa para enseñarla")
    try:
        # Sin `torch.inference_mode()` alrededor: el mapa necesita el gradiente.
        salida["mapa"] = motores.un_umbral.mapa_de_calor(datos)
    except Exception:
        REGISTRO.exception("el mapa de calor falló")
        salida["aviso_mapa"] = MAPA_FALLIDO
    return salida


def _si_no(valor):
    return None if valor is None else ("si" if valor else "no")


def fila_del_historial(n: int, origen: str, resultado: dict, hallazgos,
                       por_vista: bool) -> dict:
    """Una fila del historial: lo que dijo el motor y lo que se tecleó, nada más."""
    c = resultado.get("combinacion")
    h = hallazgos or {}
    return {
        "n": n,
        "origen": origen,
        "umbral_por_vista": "encendido" if por_vista else "apagado",
        "vista_del_umbral": (resultado.get("umbral_por_vista") or {}).get("vista"),
        "clasificacion": resultado["clasificacion"],
        "probabilidad_cruda": resultado["probabilidad_cruda"],
        "umbral": resultado["umbral"],
        "probabilidad_calibrada": resultado["probabilidad_calibrada"],
        "razon_de_verosimilitud": resultado["razon_de_verosimilitud"],
        "temperatura_c": h.get("temperatura_c"),
        "frecuencia_cardiaca": h.get("frecuencia_cardiaca"),
        "crepitantes": _si_no(h.get("crepitantes")),
        "murmullo_disminuido": _si_no(h.get("murmullo_disminuido")),
        "asma": h.get("asma"),
        "puntuacion_heckerling": "/".join(map(str, c["puntuacion"])) if c else None,
        "rv_clinica": "/".join(map(str, c["rv_clinica"])) if c else None,
        "prevalencia": c["prevalencia"] if c else None,
        "combinado_minima": c["minima"] if c else None,
        "combinado_maxima": c["maxima"] if c else None,
    }


def historial_en_csv(historial) -> bytes:
    salida = io.StringIO()
    escritor = csv.DictWriter(salida, fieldnames=COLUMNAS_HISTORIAL,
                              lineterminator="\n")
    escritor.writeheader()
    escritor.writerows(historial)
    return salida.getvalue().encode("utf-8")


def _origen_para_ver(origen: str) -> str:
    """`ejemplo: normal_pa` -> el nombre del ejemplo; «fichero subido», tal cual."""
    prefijo = "ejemplo: "
    if origen.startswith(prefijo):
        return EJEMPLOS.get(origen[len(prefijo):], origen)
    return origen


def _lista_para_ver(texto: str, formato, union: str) -> str:
    """`3/4` -> `3 o 4`; `1.64/7.18` -> `1,64–7,18`: las dos puntuaciones o las dos RV
    que el CSV guarda separadas por «/», escritas como en el informe."""
    return union.join(formato(float(v)) for v in texto.split("/"))


# Cómo se escribe cada columna en la tabla de la pantalla (M4): como en el informe. El
# CSV guarda los valores tal cual, para otro programa; esto es para una persona.
FORMATOS_DE_LA_TABLA = {
    "n": str,
    "origen": _origen_para_ver,
    "umbral_por_vista": str,
    "vista_del_umbral": str,
    "clasificacion": ETIQUETAS.get,
    "probabilidad_cruda": lambda v: _dec(v, 4),
    "umbral": lambda v: _dec(v, 4),
    "probabilidad_calibrada": _prob,
    "razon_de_verosimilitud": _rv,
    "temperatura_c": lambda v: _dec(v, 1),
    "frecuencia_cardiaca": lambda v: _dec(v, 0),
    "crepitantes": SI_NO.get,
    "murmullo_disminuido": SI_NO.get,
    "asma": ASMA.get,
    "puntuacion_heckerling": lambda v: _lista_para_ver(v, lambda p: str(int(p)), " o "),
    "rv_clinica": lambda v: _lista_para_ver(v, _rv, "–"),
    "prevalencia": lambda v: f"{_dec(v * 100, 1)} %",
    "combinado_minima": _pct,
    "combinado_maxima": _pct,
}


def historial_para_ver(historial) -> pd.DataFrame:
    """La tabla del historial en la pantalla: las mismas filas y columnas que el CSV,
    escritas para leerlas, con «—» donde no hay nada."""
    return pd.DataFrame(
        [{columna: ("—" if fila[columna] is None
                    else FORMATOS_DE_LA_TABLA[columna](fila[columna]))
          for columna in COLUMNAS_HISTORIAL} for fila in historial],
        columns=COLUMNAS_HISTORIAL)


# --------------------------------------------------------------------------
# Los textos del resultado, como el informe del bot
# --------------------------------------------------------------------------
def _medida_del_umbral(r: dict, metricas: dict) -> str:
    """La sensibilidad y la especificidad del punto de operación, SOLO si el umbral
    aplicado es uno de los medidos (como el bot: con otro umbral serían de otro punto
    de la curva). De metricas.json, no escritas aquí."""
    vista = r.get("umbral_por_vista") or {}
    if vista.get("aplicado"):
        nombre = vista["vista"]
        medido = metricas["umbrales_por_vista"].get(nombre)
        fila = metricas["umbral_por_vista_en_prueba"]["dos_umbrales"].get(nombre)
        if medido is not None and fila and abs(r["umbral"] - medido) < 1e-9:
            return (f"; en las placas {nombre} de prueba, sens. "
                    f"{_dec(fila['recall'], 2)}{DEL_BOT['esp']}"
                    f"{_dec(fila['especificidad'], 2)}")
        return ""
    if abs(r["umbral"] - metricas["umbral"]) < 1e-9:
        g = metricas["global"]
        return (f"{DEL_BOT['punto_medido']}{_dec(g['recall'], 2)}{DEL_BOT['esp']}"
                f"{_dec(g['especificidad'], 2)}")
    return ""


def texto_del_punto(r: dict, metricas: dict) -> str:
    """`puntuación 0,5509 ≥ umbral 0,4258; …`. El comparador sale de la ETIQUETA del
    motor, la verdad de la respuesta: la decidió con la puntuación sin redondear, y la
    respuesta lleva puntuación y umbral a 4 decimales, así que comparar los dos números
    que se enseñan podría decir «0,4258 ≥ 0,4258» junto a «sin opacidad probable»."""
    comparador = "≥" if r["clasificacion"] == POSITIVA else "<"
    return (f"{DEL_BOT['puntuacion']}{_dec(r['probabilidad_cruda'], 4)} {comparador}"
            f"{DEL_BOT['umbral']}{_dec(r['umbral'], 4)}{_medida_del_umbral(r, metricas)}")


def texto_de_la_vista(r: dict) -> str:
    vista = r.get("umbral_por_vista") or {}
    if vista.get("aplicado"):
        return (f"Umbral por vista (experimental): la cabecera dice {vista['vista']}, y "
                f"se aplicó el umbral de {vista['vista']}.")
    return ("Umbral por vista (experimental): la cabecera no declara PA ni AP, y se "
            "aplicó el umbral global.")


def texto_de_la_evidencia(r: dict) -> str:
    rv = r["razon_de_verosimilitud"]
    if rv >= 1:
        cuerpo = f"{DEL_BOT['multiplica']}{_rv(rv)}{DEL_BOT['a_favor']}"
    else:
        cuerpo = f"{DEL_BOT['reduce']}{_rv(rv)}{DEL_BOT['reduce_a_favor']}"
    return f"{cuerpo}{DEL_BOT['calibrada']}{_prob(r['probabilidad_calibrada'])})"


def texto_de_heckerling(c: dict) -> str:
    p = c["puntuacion"]
    if len(p) == 2:
        return f"{DEL_BOT['heckerling']}{p[0]} o {p[1]}{DEL_BOT['dos_puntuaciones']}"
    return f"{DEL_BOT['heckerling']}{p[0]}{DEL_BOT['de_5']}"


def texto_de_los_hallazgos(h: dict) -> str:
    return ", ".join([
        f"{_dec(h['temperatura_c'], 1)}{DEL_BOT['grados']}",
        f"{_dec(h['frecuencia_cardiaca'], 0)}{DEL_BOT['lpm']}",
        f"{DEL_BOT['crepitantes']}{'sí' if h['crepitantes'] else 'no'}",
        DEL_BOT["murmullo_disminuido" if h["murmullo_disminuido"] else "murmullo_normal"],
        ASMA_EN_EL_INFORME[h["asma"]],
    ])


def texto_de_la_horquilla(c: dict) -> str:
    """`entre 20 % y 52 %`, o un solo número si la horquilla se cierra. Una cota dentro
    de una horquilla se dice con palabras: no se anida un signo en un rango."""
    lo, hi = _pct(c["minima"]), _pct(c["maxima"])
    if lo == hi:
        return lo
    palabras = {"< 1 %": DEL_BOT["menos_de_1"], "> 99 %": DEL_BOT["mas_de_99"]}
    return f"entre {palabras.get(lo, lo)} y {palabras.get(hi, hi)}"


def texto_del_combinado(c: dict) -> tuple[str, str]:
    cabecera = (f"{DEL_BOT['combinado']}{texto_de_la_horquilla(c)}"
                f"{DEL_BOT['de_probabilidad']}")
    detalle = (f"{DEL_BOT['prevalencia']}{_dec(c['prevalencia'] * 100, 1)}"
               f"{DEL_BOT['por_clinica']}{'–'.join(_rv(v) for v in c['rv_clinica'])}"
               f"{DEL_BOT['por_imagen']}{_rv(c['rv_imagen'])}; "
               f"{texto_de_heckerling(c)})")
    return cabecera, detalle


def aviso_de_dependencia(c: dict) -> str:
    """El ⚠️ del bloque combinado, como el bot (§7.3 de SP4): siempre, y distinto en
    cada caso, porque tiene que ser verdad en cada uno."""
    lo, hi = _pct(c["minima"]), _pct(c["maxima"])
    if not c["concordantes"]:
        lados_distintos = (len(c["puntuacion"]) == 2
                           and (c["rv_clinica"][0] >= 1) != (c["rv_clinica"][1] >= 1))
        sustantivo = DEL_BOT["la_cifra"] if lo == hi else DEL_BOT["la_horquilla"]
        inicio = DEL_BOT["lados_distintos"] if lados_distintos else DEL_BOT["opuestos"]
        return f"{inicio}{sustantivo}{DEL_BOT['orientativa']}"
    a_favor = c["rv_imagen"] >= 1
    ind = _pct(max(c["independencia"]) if a_favor else min(c["independencia"]))
    dep = _pct(min(c["dependencia"]) if a_favor else max(c["dependencia"]))
    es_cota = lambda p: p in ("< 1 %", "> 99 %")
    if ind == dep or es_cota(ind) or es_cota(dep):
        return f"{DEL_BOT['misma_consolidacion']}{DEL_BOT['puede_exagerar']}"
    quien = ABSORBE.get(c["absorbe"], ABSORBE["mixta"])
    return (f"{DEL_BOT['misma_consolidacion']}el {ind}{DEL_BOT['supone']}{dep}, "
            f"{quien}{DEL_BOT['decide']}")


# --------------------------------------------------------------------------
# Los gráficos
# --------------------------------------------------------------------------
# Los dos gráficos, sin títulos de eje ni cifras con punto decimal: las cifras, con
# coma, están en el texto del bloque, y en un gráfico bajo Streamlit corta lo que se
# sale del área de dibujo. Lo que cada uno enseña lo dice el pie.
AZUL, ROJO = "#4c78a8", "#d62728"


def grafico_del_cribado(r: dict) -> alt.LayerChart:
    """La puntuación (una barra desde 0) frente al umbral aplicado (una línea roja
    discontinua), de 0 a 1. El valor del umbral va en el pie: un rótulo dentro del
    gráfico pisaría la barra cuando la puntuación lo pasa."""
    puntuacion = pd.DataFrame({"x": [r["probabilidad_cruda"]], "fila": ["puntuación"]})
    umbral = pd.DataFrame({"x": [r["umbral"]]})
    eje = alt.X("x:Q", scale=alt.Scale(domain=[0, 1]), title=None,
                axis=alt.Axis(values=[0, 0.25, 0.5, 0.75, 1],
                              labelExpr="replace(format(datum.value, '.2f'), '.', ',')"))
    barra = alt.Chart(puntuacion).mark_bar(size=16, color=AZUL).encode(
        x=eje, y=alt.Y("fila:N", axis=None))
    regla = alt.Chart(umbral).mark_rule(color=ROJO, strokeWidth=2,
                                        strokeDash=[5, 3]).encode(x="x:Q")
    return (barra + regla).properties(height=alt.Step(34))


def grafico_del_combinado(c: dict) -> alt.LayerChart:
    """La probabilidad de partida (un punto) y, debajo, la horquilla combinada (una
    barra entre sus extremos, o un punto si se cierra), de 0 a 100 %."""
    partida = c["prevalencia"] * 100
    filas = pd.DataFrame([
        {"fila": "De partida", "desde": partida, "hasta": partida},
        {"fila": "Clínica e imagen", "desde": c["minima"] * 100,
         "hasta": c["maxima"] * 100},
    ])
    y = alt.Y("fila:N", sort=None, title=None)
    escala = alt.Scale(domain=[0, 100])
    eje = alt.Axis(values=[0, 20, 40, 60, 80, 100], labelExpr="datum.value + ' %'")
    barras = alt.Chart(filas).mark_bar(size=10, cornerRadius=3, color=AZUL,
                                       opacity=0.5).encode(
        x=alt.X("desde:Q", scale=escala, title=None, axis=eje), x2="hasta:Q", y=y)
    extremos = alt.Chart(filas).transform_fold(["desde", "hasta"]).mark_point(
        filled=True, size=60, color=AZUL, opacity=1).encode(
        x=alt.X("value:Q", scale=escala), y=y)
    return (barras + extremos).properties(height=alt.Step(30))


# --------------------------------------------------------------------------
# La pantalla
# --------------------------------------------------------------------------
def _entrada():
    """Los controles: la radiografía, los hallazgos y el interruptor. Devuelve lo
    elegido, sin leer todavía ningún fichero."""
    col_placa, col_clinica = st.columns(2, gap="large")
    entrada = {"datos": None, "clave": None, "origen": None, "legible": None}
    probar = False
    with col_placa:
        st.markdown("##### 1 · La radiografía")
        fuente = st.segmented_control(
            "De dónde sale la radiografía", (FUENTE_EJEMPLO, FUENTE_FICHERO),
            default=FUENTE_EJEMPLO, required=True, key="fuente",
            label_visibility="collapsed")
        if fuente == FUENTE_FICHERO:
            subido = st.file_uploader(
                "Un DICOM de radiografía de tórax de un adulto, de hasta "
                f"{TAMANO_MAXIMO_MB} MB", key="dicom", max_upload_size=TAMANO_MAXIMO_MB)
            st.caption("Se lee aquí mismo y no se envía a ningún otro sitio; la app no "
                       "la guarda en disco.")
            if subido is not None:
                entrada.update(datos=subido.getvalue, clave=subido.file_id,
                               origen="fichero subido", legible="fichero subido")
        else:
            col_selector, col_boton = st.columns([3, 2], vertical_alignment="bottom")
            ejemplo = col_selector.selectbox("Ejemplo", list(EJEMPLOS),
                                             format_func=EJEMPLOS.get, key="ejemplo")
            # El botón que pide el mínimo del curso: calcula el ejemplo elegido, con
            # los hallazgos y el interruptor que haya. Lo mismo que «Calcular».
            probar = col_boton.button(BOTON_EJEMPLO, key="probar_ejemplo",
                                      width="stretch")
            st.caption(AVISO_EJEMPLOS)
            entrada.update(datos=(CARPETA_EJEMPLOS / f"{ejemplo}.dcm").read_bytes,
                           clave=ejemplo, origen=f"ejemplo: {ejemplo}",
                           legible=f"ejemplo «{EJEMPLOS[ejemplo]}»")
    with col_clinica:
        st.markdown("##### 2 · La exploración (opcional)")
        con_hallazgos = st.toggle("Añadir los cinco hallazgos de Heckerling",
                                  key="con_hallazgos")
        crudos = None
        if con_hallazgos:
            a, b = st.columns(2)
            temperatura = a.number_input(
                "Temperatura (°C)", min_value=TEMPERATURA_MIN, max_value=TEMPERATURA_MAX,
                value=None, step=0.1, format="%.1f", key="temperatura",
                placeholder=f"de {_cifra(TEMPERATURA_MIN)} a {_cifra(TEMPERATURA_MAX)}")
            frecuencia = b.number_input(
                "Frecuencia cardíaca (lpm)", min_value=FRECUENCIA_MIN,
                max_value=FRECUENCIA_MAX, value=None, step=1, key="frecuencia",
                placeholder=f"de {FRECUENCIA_MIN} a {FRECUENCIA_MAX}")
            crepitantes = st.radio("Crepitantes", tuple(SI_NO), index=None,
                                   format_func=SI_NO.get, horizontal=True,
                                   key="crepitantes")
            murmullo = st.radio("Murmullo disminuido", tuple(SI_NO), index=None,
                                format_func=SI_NO.get, horizontal=True, key="murmullo")
            asma = st.radio("Asma", tuple(ASMA), index=None, format_func=ASMA.get,
                            horizontal=True, key="asma")
            crudos = (temperatura, frecuencia, crepitantes, murmullo, asma)
        else:
            st.caption("Sin hallazgos, el resultado es solo la evidencia de la imagen.")
    st.markdown("##### 3 · El cálculo")
    col_vista, col_boton = st.columns([3, 2], gap="large", vertical_alignment="center")
    with col_vista:
        por_vista = st.toggle(
            "Umbral por vista (experimental)", key="por_vista",
            help="Clasifica una placa PA y una AP cada una con su umbral, elegidos en "
                 "validación. Solo cambia la etiqueta del cribado. Su precio, en «Acerca "
                 "de».")
    with col_boton:
        calcular_ahora = st.button("Calcular", type="primary", key="calcular",
                                   width="stretch")
    entrada.update(fuente=fuente, crudos=crudos, por_vista=por_vista,
                   calcular=calcular_ahora or probar,
                   firma=(fuente, entrada["clave"], crudos, por_vista))
    return entrada


def _hallazgos_o_que_falta(crudos):
    """Los hallazgos para el motor, o lo que falta, dicho para una persona."""
    temperatura, frecuencia, crepitantes, murmullo, asma = crudos
    faltan = [texto for valor, texto in (
        (temperatura, f"la temperatura (de {_cifra(TEMPERATURA_MIN)} a "
                      f"{_cifra(TEMPERATURA_MAX)} °C)"),
        (frecuencia, f"la frecuencia cardíaca (de {FRECUENCIA_MIN} a "
                     f"{FRECUENCIA_MAX} lpm)"),
        (crepitantes, "los crepitantes"),
        (murmullo, "el murmullo"),
        (asma, "el asma")) if valor is None]
    if faltan:
        lista = (faltan[0] if len(faltan) == 1
                 else ", ".join(faltan[:-1]) + " y " + faltan[-1])
        return None, (f"Faltan hallazgos: {lista}. Complete los cinco, o quite los "
                      "hallazgos para calcular solo con la imagen.")
    return {"temperatura_c": _como_el_campo(temperatura),
            "frecuencia_cardiaca": int(frecuencia),
            "crepitantes": crepitantes == "si",
            "murmullo_disminuido": murmullo == "si",
            "asma": asma}, None


def _bloque_cribado(r, r_global, por_vista, metricas):
    with st.container(border=True):
        st.markdown(f"**{DEL_BOT['cribado']}{ETIQUETAS[r['clasificacion']]}**")
        st.markdown(f"({texto_del_punto(r, metricas)})")
        if por_vista:
            st.markdown(texto_de_la_vista(r))
        if r_global is not None and r_global["clasificacion"] != r["clasificacion"]:
            st.markdown(f"Con el umbral global ({_dec(r_global['umbral'], 4)}) sería "
                        f"«{ETIQUETAS[r_global['clasificacion']]}».")
        st.altair_chart(grafico_del_cribado(r), width="stretch")
        st.caption("La barra es la puntuación del modelo, de 0 a 1 (no es una "
                   "probabilidad); la línea roja discontinua, el umbral aplicado "
                   f"({_dec(r['umbral'], 4)}).")


def _bloque_evidencia(r):
    rv = r["razon_de_verosimilitud"]
    with st.container(border=True):
        # El espacio, fuera de los asteriscos: `**… — **` no cierra la negrita.
        st.markdown(f"**{DEL_BOT['evidencia'].rstrip()}** {texto_de_la_evidencia(r)}")
        if RV_POCO_INFORMATIVA[0] <= rv <= RV_POCO_INFORMATIVA[1]:
            st.markdown(
                "La imagen apenas mueve la probabilidad: una razón de verosimilitud "
                f"entre {_cifra(RV_POCO_INFORMATIVA[0])} y "
                f"{_cifra(RV_POCO_INFORMATIVA[1])} la cambia poco.")
        # `icon=""`: sin él, Streamlit saca el ⚠️ del texto para hacerlo icono, y el
        # aviso ya no sería, letra a letra, el del bot.
        if r["clasificacion"] == POSITIVA and rv < 1:
            st.warning(DEL_BOT["positivo_sin_apoyo"], icon="")
        if r["clasificacion"] != POSITIVA:
            st.warning(DEL_BOT["negativo"], icon="")


def _bloques_clinicos(c, hallazgos):
    with st.container(border=True):
        st.markdown(f"**CLÍNICA — {texto_de_heckerling(c)}**")
        st.markdown("razón de verosimilitud "
                    + "–".join(_rv(v) for v in c["rv_clinica"]))
        st.caption(f"({texto_de_los_hallazgos(hallazgos)})")
    cabecera, detalle = texto_del_combinado(c)
    with st.container(border=True):
        st.markdown(f"**{cabecera}**")
        st.markdown(detalle)
        st.altair_chart(grafico_del_combinado(c), width="stretch")
        st.caption("Probabilidad de opacidad compatible, de 0 a 100 %: la de partida y, "
                   "debajo, la horquilla con la clínica y la imagen.")
        st.warning(aviso_de_dependencia(c), icon="")


def _bloque_mapa(ultimo):
    with st.container(border=True):
        st.markdown("**MAPA DE CALOR**")
        placa, mapa = ultimo["placa"], ultimo["mapa"]
        if placa is None:
            st.caption(PLACA_ILEGIBLE)
            return
        if mapa is None:
            st.image(placa, width="stretch")
            st.caption(ultimo["aviso_mapa"] or MAPA_FALLIDO)
            return
        opacidad = st.slider("Intensidad del mapa", 0, 100, OPACIDAD_DEL_MAPA, step=5,
                             format="%d %%", key="opacidad")
        st.image(superponer(placa, mapa, opacidad / 100), width="stretch")
        if not np.any(mapa > 0):
            st.caption(MAPA_DE_CEROS)
        st.caption(AVISO_DEL_MAPA + " Rojo: donde más mira; sin color: donde no mira.")


def _resultado(ultimo, metricas):
    r = ultimo["resultado"]
    st.markdown(f"#### Resultado: {ultimo['legible']}")
    st.caption(f"Edad en la cabecera: {r['edad_paciente']} años · modelo "
               f"{r['modelo']} · {_dec(r['milisegundos'], 0)} ms")
    col_bloques, col_mapa = st.columns([3, 2], gap="large")
    with col_bloques:
        _bloque_cribado(r, ultimo["resultado_global"], ultimo["por_vista"], metricas)
        _bloque_evidencia(r)
        if "combinacion" in r:
            _bloques_clinicos(r["combinacion"], ultimo["hallazgos"])
        else:
            with st.container(border=True):
                st.markdown(DEL_BOT["sin_combinar"])
                st.caption("Añada los cinco hallazgos para combinar la imagen con la "
                           "regla de Heckerling.")
    with col_mapa:
        _bloque_mapa(ultimo)
    st.markdown(f"**{DEL_BOT['descargo']}**")


def pantalla_probar(motores: Motores, metricas: dict):
    entrada = _entrada()
    st.divider()
    problema = None
    if entrada["calcular"]:
        hallazgos = None
        if entrada["datos"] is None:
            problema = SIN_FICHERO
        elif entrada["crudos"] is not None:
            hallazgos, problema = _hallazgos_o_que_falta(entrada["crudos"])
        if problema:
            st.warning(problema)
        else:
            with st.spinner("Calculando…"):
                ultimo = calcular(motores, entrada["datos"](), hallazgos,
                                  entrada["por_vista"])
            ultimo.update(firma=entrada["firma"], legible=entrada["legible"],
                          hallazgos=hallazgos, por_vista=entrada["por_vista"])
            st.session_state["ultimo"] = ultimo
            if "resultado" in ultimo:
                historial = st.session_state["historial"]
                historial.append(fila_del_historial(
                    len(historial) + 1, entrada["origen"], ultimo["resultado"],
                    hallazgos, entrada["por_vista"]))
    ultimo = st.session_state.get("ultimo")
    if ultimo and ultimo["firma"] == entrada["firma"]:
        if "rechazo" in ultimo:
            st.error(ultimo["rechazo"])
        else:
            _resultado(ultimo, metricas)
    elif not problema:
        # Un resultado solo se enseña junto a la entrada que lo dio.
        st.info("La entrada ha cambiado: pulse «Calcular» para ver su resultado."
                if ultimo else "Elija un ejemplo o suba un DICOM, y pulse «Calcular».")


def pantalla_historial():
    historial = st.session_state["historial"]
    if not historial:
        st.info("Aún no hay cálculos en esta sesión.")
        return
    st.dataframe(
        historial_para_ver(historial), hide_index=True,
        column_config={
            "n": "N.º", "origen": "Origen", "umbral_por_vista": "Umbral por vista",
            "vista_del_umbral": "Vista", "clasificacion": "Cribado",
            "probabilidad_cruda": "Puntuación", "umbral": "Umbral",
            "probabilidad_calibrada": "Prob. calibrada",
            "razon_de_verosimilitud": "RV de la imagen", "temperatura_c": "Temp. (°C)",
            "frecuencia_cardiaca": "FC (lpm)", "crepitantes": "Crepitantes",
            "murmullo_disminuido": "Murmullo dism.", "asma": "Asma",
            "puntuacion_heckerling": "Heckerling", "rv_clinica": "RV clínica",
            "prevalencia": "Prevalencia", "combinado_minima": "Combinado, mín.",
            "combinado_maxima": "Combinado, máx.",
        })
    st.download_button("Descargar el historial (CSV)", data=historial_en_csv(historial),
                       file_name="historial_de_la_sesion.csv", mime="text/csv",
                       on_click="ignore", key="descargar")
    st.caption("Solo lo de esta sesión del navegador, y sin la imagen: ni el nombre del "
               "fichero subido ni nada de su cabecera. El origen es el ejemplo o "
               "«fichero subido».")


def _tabla_de_subgrupos(metricas) -> pd.DataFrame:
    return pd.DataFrame([{
        "Subgrupo": s["nombre"],
        "n": _entero(s["n"]),
        "Con opacidad": _entero(s["positivos"]),
        "AUC": _con_ic(s["auc"], None, 3),
        "Sensibilidad (IC 95 %)": _con_ic(s["recall"], s["recall_ic"]),
        "Especificidad (IC 95 %)": _con_ic(s["especificidad"], s["especificidad_ic"]),
    } for s in metricas["subgrupos"]])


def _tabla_del_precio(metricas) -> pd.DataFrame:
    precio = metricas["umbral_por_vista_en_prueba"]
    uno, dos = precio["un_umbral"], precio["dos_umbrales"]
    return pd.DataFrame([{
        "Placas": rotulo,
        "Sensibilidad, un umbral": _con_ic(uno[clave]["recall"], uno[clave]["recall_ic"]),
        "Sensibilidad, dos umbrales": _con_ic(dos[clave]["recall"],
                                              dos[clave]["recall_ic"]),
        "Especificidad, un umbral": _con_ic(uno[clave]["especificidad"],
                                            uno[clave]["especificidad_ic"]),
        "Especificidad, dos umbrales": _con_ic(dos[clave]["especificidad"],
                                               dos[clave]["especificidad_ic"]),
    } for rotulo, clave in (("PA", "PA"), ("AP", "AP"), ("Todas", "global"))])


def _licencias_para_la_pantalla() -> str:
    """LICENCIAS.md tal cual, con los títulos dos niveles más abajo: dentro de un
    desplegable, un título de primer nivel se come la pantalla."""
    texto = LICENCIAS.read_text(encoding="utf-8")
    return re.sub(r"^(#+)", lambda m: "#" * min(len(m.group(1)) + 2, 6), texto,
                  flags=re.MULTILINE)


def pantalla_acerca_de(motores: Motores, metricas: dict, config: Configuracion):
    motor = motores.un_umbral
    calibrador = motor.calibrador
    g = metricas["global"]

    st.markdown("### Qué hace y qué no")
    st.markdown(
        f"Lee la radiografía de tórax de un adulto (de {EDAD_MINIMA} a {EDAD_MAXIMA} "
        "años, en DICOM) y da tres cosas: una etiqueta de cribado —opacidad probable o "
        "no—, la evidencia de la imagen como razón de verosimilitud y, si se le dan "
        "los cinco hallazgos de la exploración, una probabilidad combinada con la "
        "regla clínica de Heckerling.\n\n"
        "No diagnostica neumonía, no localiza lesiones y no sustituye el juicio "
        "clínico. El producto es un bot de Telegram para profesionales; esta app es la "
        "puerta para evaluarlo, con el mismo motor: los mismos pesos, la misma "
        "calibración y la misma combinación.")

    st.markdown("### El modelo")
    rv_min = calibrador.razon_de_verosimilitud(0.0)
    rv_max = calibrador.razon_de_verosimilitud(1.0)
    st.markdown(
        f"- **Red:** EfficientNet-B0 (Tan y Le, 2019), ajustada a {motor.tam_imagen} × "
        f"{motor.tam_imagen} px (`{motor.nombre_modelo}`). Puntúa de 0 a 1 la "
        "opacidad pulmonar de la placa.\n"
        f"- **Cribado:** la etiqueta compara esa puntuación con el umbral "
        f"{_dec(motor.umbral, 4)}, elegido para detectar: prioriza la sensibilidad. La "
        "puntuación no es una probabilidad.\n"
        "- **Calibración:** una regresión isotónica ajustada en validación "
        f"(`{calibrador.procedencia}`) convierte la puntuación en una probabilidad "
        f"—con la prevalencia de ese conjunto, {_dec(calibrador.prevalencia * 100, 2)} "
        "%— y en una razón de verosimilitud (RV), que es lo que se combina. La RV se "
        "acota a lo que sostienen los datos de validación: entre "
        f"{_rv(rv_min)} y {_rv(rv_max)}.\n"
        f"- **AUC en validación:** {_dec(motor.auc_validacion, 4)}, el que declara el "
        "despliegue (`AUC_VALIDACION`).\n"
        "- **Regla de Heckerling** (Heckerling et al., 1990): un punto por cada "
        f"hallazgo —temperatura por encima de {_cifra(TEMPERATURA_CORTE_C)} °C, "
        f"frecuencia cardíaca por encima de {PULSO_CORTE_LPM} lpm, crepitantes, "
        "murmullo disminuido y no tener asma—. Cada puntuación tiene su RV, la de la "
        "cohorte de derivación según la tabla 2 de la revisión "
        "[PMC7422644](https://pmc.ncbi.nlm.nih.gov/articles/PMC7422644/); si el asma "
        "no se sabe, se dan las dos puntuaciones posibles.")
    st.table(pd.DataFrame({"Puntuación de Heckerling": list(RV_POR_PUNTUACION),
                           "RV": [_rv(v) for v in RV_POR_PUNTUACION.values()]}),
             hide_index=True, width="content")
    de_la_cohorte = abs(motor.prevalencia_local - round(PREVALENCIA_COHORTE, 4)) < 1e-9
    st.markdown(
        "- **Combinación:** odds de partida × RV clínica × RV de la imagen, con una "
        f"prevalencia de partida de {_dec(motor.prevalencia_local * 100, 2)} % "
        "(`PREVALENCIA_LOCAL`"
        + (", la de la cohorte de derivación de la regla" if de_la_cohorte else "")
        + "). La auscultación y la placa miran la misma consolidación, así que no son "
        "pruebas independientes: cuando apuntan al mismo lado, el resultado es la "
        "horquilla entre la probabilidad bajo independencia y la que da la evidencia más "
        "informativa sola; cuando se oponen, esa segunda no se calcula, y el resultado "
        "es la probabilidad bajo independencia —una, o dos si el asma no se sabe—, que "
        "el informe da por orientativa.\n"
        "- **Mapa de calor:** Grad-CAM (Selvaraju et al., 2017) sobre el último bloque "
        "convolucional, respecto de la puntuación de opacidad. Señala dónde mira el "
        "modelo, no por qué acierta.")
    st.caption(
        f"Valores de este despliegue: UMBRAL = {_dec(config.umbral, 4)} · "
        f"AUC_VALIDACION = {_dec(config.auc_validacion, 4)} · PREVALENCIA_LOCAL = "
        f"{_dec(config.prevalencia_local, 4)} ({_dec(config.prevalencia_local * 100, 2)} "
        "%).")

    st.markdown("### Los datos")
    st.markdown(
        "El modelo se entrenó, se calibró y se evaluó con el conjunto público RSNA "
        "Pneumonia Detection Challenge (2018): radiografías de tórax del NIH (Estados "
        "Unidos) anotadas por radiólogos, con la partición hecha por paciente. El "
        "repositorio no lleva ninguna de esas imágenes; solo estas referencias:\n\n"
        "- [RSNA Pneumonia Detection Challenge]"
        "(https://www.kaggle.com/competitions/rsna-pneumonia-detection-challenge), en "
        "Kaggle.\n"
        "- G. Shih *et al.*, «Augmenting the National Institutes of Health chest "
        "radiograph dataset with expert annotations of possible pneumonia», "
        "*Radiol. Artif. Intell.*, vol. 1, n.º 1, art. e180041, ene. 2019, doi: "
        "[10.1148/ryai.2019180041](https://doi.org/10.1148/ryai.2019180041).")

    st.markdown("### Las métricas")
    st.markdown(
        f"En el conjunto de prueba de RSNA —{_entero(g['n'])} placas, una por paciente, "
        f"{_entero(g['positivos'])} con opacidad; nunca usado para entrenar ni para "
        f"calibrar—, con el umbral {_dec(metricas['umbral'], 4)}: AUC "
        f"{_dec(g['auc'], 3)}, sensibilidad {_con_ic(g['recall'], g['recall_ic'])} y "
        f"especificidad {_con_ic(g['especificidad'], g['especificidad_ic'])}. "
        "Intervalos de Wilson al 95 %.")
    if motores.huella_de_los_pesos == metricas["pesos_sha256"]:
        st.success("Las métricas son de estos mismos pesos: su huella (sha256) coincide "
                   "con la de los cargados.")
    else:
        st.warning("Las métricas de esta sección se calcularon con otros pesos: la "
                   "huella (sha256) de los cargados no coincide, así que no describen "
                   "este modelo.")
    if abs(motor.umbral - metricas["umbral"]) >= 1e-9:
        st.warning(f"El umbral de este despliegue ({_dec(motor.umbral, 4)}) no es aquel "
                   f"con el que se midieron estas métricas ({_dec(metricas['umbral'], 4)})"
                   ": la sensibilidad y la especificidad son de otro punto de la curva.")
    st.table(_tabla_de_subgrupos(metricas), hide_index=True)
    st.caption(f"De app/assets/metricas.json, generado el {metricas['generado']} con "
               f"los pesos de huella {metricas['pesos_sha256'][:12]}…: solo agregados, "
               "ninguna fila por paciente.")

    st.markdown("### Las limitaciones")
    pa, ap = _subgrupo(metricas, "Placa PA (de pie)"), _subgrupo(metricas,
                                                                 "Placa AP (portátil)")
    mayores, jovenes = (_subgrupo(metricas, "60 años o más"),
                        _subgrupo(metricas, "18 a 39 años"))
    if all((pa, ap, mayores, jovenes)):
        sesgo = (f"Con el umbral único, en prueba, las placas PA tienen una sensibilidad "
                 f"de {_dec(pa['recall'], 2)} y las AP una especificidad de "
                 f"{_dec(ap['especificidad'], 2)}; con 60 años o más, el AUC es "
                 f"{_dec(mayores['auc'], 3)}, frente a {_dec(jovenes['auc'], 3)} de 18 a "
                 "39 años.")
    else:
        sesgo = "El rendimiento cambia con la vista y con la edad: véase la tabla."
    st.markdown(
        "- **Opacidad no es neumonía.** El modelo aprendió la etiqueta de opacidad "
        "pulmonar de RSNA: hay opacidades que no son neumonía (atelectasia, derrame, "
        "tumor) y neumonías sin opacidad visible.\n"
        "- **Datos de Estados Unidos.** Las placas son del NIH; con otra población, "
        "otros equipos u otros protocolos, el rendimiento no está medido.\n"
        f"- **Sesgo por vista y por edad.** {sesgo}\n"
        "- **Validación semisintética.** La combinación con la clínica se validó con las "
        "placas reales de prueba y una clínica sorteada con la distribución publicada "
        "de la regla de Heckerling; la dependencia entre clínica e imagen es un "
        "supuesto. No mide exactitud clínica en pacientes.\n"
        "- **Los ejemplos** no son de RSNA: el modelo no se ha medido con ellos.")

    st.markdown("### El umbral por vista y su precio")
    umbrales = metricas["umbrales_por_vista"]
    precio = metricas["umbral_por_vista_en_prueba"]
    uno, dos = precio["un_umbral"], precio["dos_umbrales"]
    # Lo que gana Y lo que pierde cada vista, con las cifras del JSON (M5).
    cambia = lambda clave, medida: " y ".join(
        _cambio(m, uno[clave][c], dos[clave][c]) for m, c in medida)
    sens, esp = ("sensibilidad", "recall"), ("especificidad", "especificidad")
    st.markdown(
        "Experimental y apagado por defecto, también en el servidor. Encendido, una "
        f"placa PA se clasifica con el umbral {_dec(umbrales['PA'], 4)} y una AP con "
        f"{_dec(umbrales['AP'], 4)}, elegidos en validación; cualquier otra vista, con "
        f"el global ({_dec(motor.umbral, 4)}). Solo cambia la etiqueta del cribado: la "
        "RV y la combinación no dependen de la vista.\n\n"
        f"En prueba, con dos umbrales: en las placas PA, {cambia('PA', (sens, esp))}; en "
        f"las AP, {cambia('AP', (esp, sens))}; y en todas, "
        f"{cambia('global', (sens, esp))}. Encenderlo en producción lo decide la "
        "institución.")
    st.table(_tabla_del_precio(metricas), hide_index=True)

    st.markdown("### Los ejemplos")
    st.markdown(AVISO_EJEMPLOS)
    with st.expander("Licencias y atribución de los ejemplos"):
        st.markdown(_licencias_para_la_pantalla())

    st.markdown("### Aviso")
    st.warning("**No es un producto sanitario.** Es una demostración académica, sin "
               "autorización de ninguna autoridad sanitaria: no la use para decidir "
               "sobre un paciente.")


def main():
    st.set_page_config(page_title="Copiloto de triaje — demostración", page_icon="🫁",
                       layout="wide")
    st.title("Copiloto de triaje para neumonía en adultos")
    st.markdown("Pruebe el mismo motor que usa el bot del profesional: la red que lee "
                "la placa, su calibración y la combinación con la regla clínica de "
                "Heckerling. Calcula aquí mismo; la placa no se envía a ningún otro "
                "sitio.")
    st.warning("**Demostración académica.** No es un producto sanitario: no la use "
               "para decidir sobre un paciente.")
    st.session_state.setdefault("historial", [])

    try:
        metricas = leer_metricas()
    except (OSError, ValueError) as exc:
        REGISTRO.exception("no se pudo leer metricas.json")
        st.error(f"No se pudo leer app/assets/metricas.json ({type(exc).__name__}). "
                 "Sin él no hay umbrales ni métricas que enseñar.")
        st.stop()
    try:
        config = leer_configuracion(os.environ, metricas["umbral"])
    except ConfiguracionInvalida as exc:
        st.error(str(exc))
        st.stop()
    try:
        motores = cargar_motores(config.ruta_pesos, config.ruta_calibrador,
                                 config.umbral, config.auc_validacion,
                                 config.prevalencia_local,
                                 tuple(sorted(metricas["umbrales_por_vista"].items())),
                                 id(Motor))
    except FileNotFoundError as exc:
        st.error(f"No se pudo cargar el modelo: {exc}. Revise RUTA_PESOS y "
                 "RUTA_CALIBRADOR; los pesos no se versionan.")
        st.stop()
    except Exception:
        REGISTRO.exception("no se pudo cargar el modelo")
        st.error("No se pudo cargar el modelo (se ha registrado). Revise RUTA_PESOS y "
                 "RUTA_CALIBRADOR.")
        st.stop()

    probar, historial, acerca = st.tabs(["Probar el modelo", "Historial de la sesión",
                                         "Acerca de"])
    with probar:
        pantalla_probar(motores, metricas)
    with historial:
        pantalla_historial()
    with acerca:
        pantalla_acerca_de(motores, metricas, config)


if __name__ == "__main__":
    # La última red: nada de lo que falle aquí llega a la pantalla como traza. Las
    # excepciones de control de Streamlit (`st.stop`, una nueva ejecución) no son
    # `Exception` y pasan.
    try:
        main()
    except Exception:
        REGISTRO.exception("la app falló")
        st.error("La app falló por un error que no sé interpretar. Se ha registrado: "
                 "recargue la página.")
