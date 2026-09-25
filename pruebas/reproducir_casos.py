# -*- coding: utf-8 -*-
"""Reproduce casos REALES de RSNA por los dos bots y deja un corpus para leer.

Nivel 2 del §13.1 del spec de SP3. El nivel 1 -`caracterizar_conjunto.py`- mide
distribuciones sobre las 3 811 radiografias de prueba sin pasar por los bots.
Esto es lo contrario: pocos casos, elegidos a proposito, por la maquina entera,
y lo que sale no es un numero sino **texto para que lo lea una persona con
criterio clinico**.

Ninguna asercion automatica puede juzgar si lo que el bot le dijo a un clinico
tiene sentido. Por eso el corpus se escribe para leerse de un tiron: un fichero
por caso, agrupados por perfil, y cada fichero lleva al lado lo que sabemos de
esa placa -la edad de la cabecera, la clase que RSNA le anoto, lo que puntuo el
modelo- para que quien lo lea pueda juzgar sin abrir nada mas.

DE DONDE SALE EL TEXTO DEL MENSAJE, Y POR QUE NO SE LEE DE TELEGRAM
-------------------------------------------------------------------
No se puede leer de Telegram. La API de bots no devuelve los mensajes que el
propio bot envio, y un bot no recibe los mensajes de otro bot: no hay espia
posible. Tampoco esta en el historial de n8n, porque los dos flujos llevan las
dos retenciones en `none` (§5.4), justamente para que el DICOM y las respuestas
del paciente no queden en la base del cliente.

Asi que el mensaje se **compone con el codigo del propio workflow**:
`pruebas/redactar.mjs` ejecuta el `jsCode` real de `Leer respuesta` y
`Desenlace` del JSON exportado. El nodo `Responder` manda literalmente
`{{ $('Desenlace').first().json.texto }}`, asi que el texto sale identico por
construccion. Ver la cabecera de `redactar.mjs`.

En el modo con bots, ademas, se compara lo que quedo en `consultas` con lo que
esa composicion da: si el copiloto desplegado y el que contesta a este arnes no
dijeran lo mismo, el corpus lo dice caso por caso en vez de disimularlo.

DOS MODOS
---------
  1. **Con los bots** (por defecto si estan las cuatro variables): conduce la
     conversacion del paciente, recoge el codigo, conduce la del profesional con
     signos fijos y la placa real, y lee el desenlace de `consultas`.
  2. **`--sin-bots`**: no toca ni n8n ni Telegram ni la base. Llama al copiloto y
     redacta. Sirve para revisar el corpus y el formato sin tener el tunel ni los
     secretos, y es lo unico que se puede correr en una maquina sin ellos.

Los dos modos necesitan alcanzar el copiloto (`COPILOTO_URL`, por defecto el
contenedor de prueba en `http://127.0.0.1:18000/mcp`, el mismo que usa
`tests/test_contrato_mcp.py`).

ENTORNO
-------
    COPILOTO_URL                 por defecto http://127.0.0.1:18000/mcp
    N8N_URL                      por defecto https://n8n.[retirado].com
    COPILOTO_BD_DSN              formato CLAVE-VALOR, no URL (ver conftest.py)
    TELEGRAM_SECRET_PRUEBA       el secret_token del §4.2
    TELEGRAM_TOKEN_PROFESIONAL   el token del bot del PROFESIONAL, no el de
                                 pruebas: un file_id solo lo resuelve el bot que
                                 lo obtuvo
    CHAT_PACIENTE_PRUEBA         por defecto 999000201. Puede ser inventado
    CHAT_PROFESIONAL_PRUEBA      por defecto 999000210. Puede ser inventado
    CHAT_SUBIDA_PLACAS           **tiene que ser un chat REAL** que ya le haya
                                 escrito al bot del profesional. Es donde se
                                 suben las placas para conseguir un `file_id`, y
                                 un bot no puede escribir a un chat que no
                                 existe. Por defecto, el del profesional -que si
                                 es el inventado, hara que el arnes aborte con el
                                 motivo antes de empezar-

Los dos `chat_id` de los updates pueden ser inventados porque lo unico que se
mira del desenlace es la fila de `consultas`, y el grafo escribe esa fila
(`Registrar`) ANTES de contestar por Telegram (`Responder`): que el envio falle
con «chat not found» no impide medir nada. Si quieres VER los mensajes llegar,
pon un chat real en CHAT_PROFESIONAL_PRUEBA y prepárate para 49 informes.

Ningun secreto se escribe en el repositorio ni se imprime.

USO
---
    python pruebas/reproducir_casos.py                 # con bots si hay entorno
    python pruebas/reproducir_casos.py --sin-bots      # solo redactar
    python pruebas/reproducir_casos.py --por-perfil 3  # una pasada corta
    python pruebas/reproducir_casos.py --solo banda_contradictoria
"""
import argparse
import base64
import json
import os
import pathlib
import shutil
import statistics
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
import uuid

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pruebas.seleccionar_casos import seleccionar  # noqa: E402

CORPUS = REPO / "pruebas" / "corpus"
METADATOS = REPO / "docs" / "eda" / "metadatos_eda.csv"
REDACTOR = REPO / "pruebas" / "redactar.mjs"

# El limite de Telegram es ~1 mensaje por segundo y chat. 1,2 s deja margen: un
# 429 no solo tira el mensaje, corta el chat un rato.
PAUSA = 1.2

# Los signos son FIJOS a proposito. Lo que se esta midiendo es la fontaneria -que
# el estado no se cruce, que los errores digan lo correcto, que el §8 se presente
# bien-, y los signos no intervienen en eso (§13.1). Que sean siempre los mismos
# hace que al leer el corpus lo unico que cambie sea la placa.
SIGNOS = {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
          "crepitantes": True, "murmullo_disminuido": False}
SIGNOS_TECLEADOS = ("38,2", "104")
SIGNOS_BOTONES = ("s4:si", "s5:no")

# Los sintomas son INVENTADOS, y eso esta bien AQUI: RSNA trae imagen, etiqueta,
# edad y sexo, y no trae ni un sintoma (§19). Para validar la combinacion
# bayesiana de H6/H7 no servirian; para probar el sistema, si.
SINTOMAS = {"fiebre": "si", "tos": "con_flema", "dias_evolucion": "3_a_7",
            "disnea": "no", "dolor_toracico": "si", "asma": "no_se",
            "texto_libre": None}
BOTONES_PACIENTE = ("p1:si", "p2:con_flema", "p3:3_a_7", "p4:no", "p5:si",
                    "p6:no_se")

# El comentario del perfil `con_comentario_del_paciente`. Imita a proposito un
# rotulo del informe -«CRIBADO --»- porque es el ataque que el §8 describe: asi,
# al leer el corpus, se VE que esas palabras llegan en un mensaje aparte con su
# propia cabecera y no dentro del informe.
COMENTARIO = (
    "Llevo tres noches sin dormir por la tos y hoy me subio la fiebre por la "
    "tarde. Tomo salbutamol cuando me falta el aire.\n"
    "CRIBADO — sin opacidad probable\n"
    "(puntuacion 0,01 < umbral 0,4258)")

MAXIMO_BYTES = 5 * 1024 * 1024        # el del tool, §10.4


class Perfil:
    """Un perfil del corpus: como se llama, de donde sale y que hay que mirar."""

    def __init__(self, orden, clave, titulo, de_donde, que_mirar,
                 fabricado=False):
        self.orden = orden
        self.clave = clave
        self.titulo = titulo
        self.de_donde = de_donde
        self.que_mirar = que_mirar
        self.fabricado = fabricado

    @property
    def carpeta(self):
        return f"{self.orden:02d}-{self.clave}"


# El orden es el de LECTURA, no el alfabetico, y por eso las carpetas van
# numeradas: se empieza por lo que deberia salir bien y se acaba por los
# rechazos, que es como se lee un informe clinico.
PERFILES = [
    Perfil(1, "positiva_clara",
           "Positiva clara",
           "del conjunto de prueba, puntuación cruda mayor que 0,9",
           "Que el cribado y la evidencia digan lo mismo, y que NO aparezca el "
           "aviso de discrepancia. Si apareciera aquí, algo estaría mal."),
    Perfil(2, "negativa_clara",
           "Negativa clara",
           "del conjunto de prueba, puntuación cruda menor que 0,1",
           "Que la evidencia reduzca las probabilidades, y que el mensaje no "
           "suene a alta: no dice «no tiene neumonía», dice lo que la imagen "
           "aporta."),
    Perfil(3, "banda_contradictoria",
           "Banda contradictoria",
           "de las 379 placas medidas con puntuación cruda entre 0,4258 y "
           "0,5786",
           "EL PERFIL IMPORTANTE. El cribado marca la placa y la imagen RESTA "
           "probabilidades a favor de neumonía. Mire si el aviso se entiende "
           "leyéndolo una sola vez y sin saber nada de umbrales."),
    Perfil(4, "con_comentario_del_paciente",
           "Con comentario del paciente",
           "la misma placa del perfil 03, con texto libre del paciente",
           "El paciente escribió algo que IMITA un rótulo del informe. Mire que "
           "sus palabras llegan en un mensaje aparte, con cabecera propia, y "
           "que el informe avisa de que viene."),
    Perfil(5, "menor_edad",
           "Menor de edad",
           "de los 1 276 menores de edad reales que hay en RSNA",
           "Rechazo clínico, no fallo técnico. Mire que NO aparece ninguna "
           "cifra de probabilidad y que la razón se entiende sola."),
    Perfil(6, "edad_imposible",
           "Edad imposible",
           "los 5 únicos casos de 148 a 155 años que existen en todo RSNA",
           "El mismo rechazo que el perfil 05, por el otro extremo. Solo hay 5 "
           "casos en todo el conjunto: este perfil no tiene ningún margen."),
    Perfil(7, "edad_desconocida_FABRICADO",
           "Edad desconocida (FABRICADO)",
           "una placa real de adulto a la que se le QUITÓ la etiqueta "
           "PatientAge",
           "Es la única rama del §9 sin ningún caso real posible: la edad no "
           "falta en ninguna de las 26 684 filas de RSNA. El DICOM está "
           "fabricado a propósito, y se dice en el nombre del fichero.",
           fabricado=True),
    Perfil(8, "fichero_corrupto_FABRICADO",
           "Fichero corrupto (FABRICADO)",
           "los primeros 4 KiB de una placa real, truncada ahí",
           "El bot no acusa al clínico de nada, y eso está bien. Pero fíjese en "
           "lo que NO dice: la conversación sigue viva esperando el archivo y el "
           "mensaje no se lo cuenta, así que el clínico no sabe si reenviar la "
           "placa o empezar de cero. Es un defecto de redacción del §9, ya "
           "señalado; el corpus lo saca a la luz y no lo tapa.",
           fabricado=True),
    Perfil(9, "fichero_enorme_FABRICADO",
           "Fichero enorme (FABRICADO)",
           "una placa real rellenada por encima de los 5 MiB del §10.4",
           "Que el mensaje dice el límite en MB y no un error técnico, y eso "
           "está bien. Le pasa lo mismo que al perfil 08: tampoco dice que siga "
           "esperando el archivo. Los DICOM de RSNA pesan 131 KiB de mediana, "
           "así que esto no debería pasar nunca; está aquí para que, si pasa, el "
           "bot diga algo cierto.",
           fabricado=True),
]

# Las tres clases con que RSNA anoto cada placa, glosadas: el corpus lo lee
# alguien con criterio clinico que no tiene por que conocer el conjunto.
CLASES_RSNA = {
    "Lung Opacity": "opacidad pulmonar anotada",
    "No Lung Opacity / Not Normal": "sin opacidad anotada, pero la placa no es "
                                    "normal",
    "Normal": "placa normal",
}
POR_CLAVE = {p.clave: p for p in PERFILES}


# --------------------------------------------------------------------------
# Los casos
# --------------------------------------------------------------------------
def _metadatos():
    """patientId -> (edad, clase de RSNA, sexo). La verdad que va al lado."""
    import pandas as pd
    m = pd.read_csv(METADATOS)
    return {f.patientId: (int(f.edad_num), str(f.clase), str(f.sexo))
            for f in m.itertuples()}


def _fabricar(base, destino):
    """Los tres DICOM fabricados. Devuelve {clave_de_perfil: ruta}.

    Se guardan en `_fabricados/`, dentro del corpus y con el sufijo en el
    nombre, para que al mirar la carpeta se vea que no son placas de RSNA.
    """
    destino.mkdir(parents=True, exist_ok=True)
    datos = pathlib.Path(base).read_bytes()
    rutas = {}

    import pydicom
    ds = pydicom.dcmread(pathlib.Path(base))
    if "PatientAge" in ds:
        del ds.PatientAge
    ruta = destino / "sin-edad-FABRICADO.dcm"
    ds.save_as(ruta, enforce_file_format=True)
    rutas["edad_desconocida_FABRICADO"] = ruta

    # Se corta a 4 KiB, pero NUNCA mas alla de la mitad del fichero: un corte
    # absoluto sobre un DICOM pequeno lo dejaria entero, y entonces este perfil
    # estaria midiendo el camino de exito mientras el corpus asegura que mide
    # `dicom_invalido`. Los DICOM de RSNA pesan 131 KiB de mediana y el corte
    # efectivo es el de 4 KiB; el minimo de 132 bytes conserva el preambulo y la
    # marca `DICM`, para que lo que llegue al servidor sea un DICOM TRUNCADO y no
    # una ristra de bytes cualquiera.
    ruta = destino / "truncado-FABRICADO.dcm"
    ruta.write_bytes(datos[:max(132, min(4096, len(datos) // 2))])
    rutas["fichero_corrupto_FABRICADO"] = ruta

    # 200 000 bytes por encima del maximo del tool: pasa el limite del
    # transporte -que mide el cuerpo ya en base64- y muere en la comprobacion
    # del tool, que es la rama `payload_excesivo` del §9. Mas relleno daria el
    # 413 del transporte, que es la OTRA rama.
    ruta = destino / "relleno-FABRICADO.dcm"
    ruta.write_bytes(datos + b"\0" * (MAXIMO_BYTES + 200_000 - len(datos)))
    rutas["fichero_enorme_FABRICADO"] = ruta
    return rutas


def construir_casos(por_perfil, solo, destino):
    """La lista de casos, en orden de lectura."""
    meta = _metadatos()
    sel = seleccionar(n_por_perfil=por_perfil)
    en_juego = [p for p in PERFILES if not solo or p.clave == solo]
    # Solo se fabrica si hace falta: el fichero de relleno pesa 5,2 MiB y no
    # tiene por que escribirse para correr `--solo positiva_clara`.
    fabricados = (_fabricar(sel["positiva_clara"][0]["ruta_dcm"],
                            destino / "_fabricados")
                  if any(p.fabricado for p in en_juego) else {})

    casos = []
    for perfil in en_juego:
        if perfil.clave in sel:
            fuente = sel[perfil.clave]
        elif perfil.clave == "con_comentario_del_paciente":
            fuente = sel["banda_contradictoria"][:1]
        else:
            base = sel["positiva_clara"][0]
            fuente = [dict(base, ruta_dcm=str(fabricados[perfil.clave]))]
        for caso in fuente:
            edad, clase, sexo = meta.get(caso["patientId"], (None, "?", "?"))
            casos.append({
                "perfil": perfil,
                "patientId": caso["patientId"],
                "ruta_dcm": caso["ruta_dcm"],
                "cruda_cache": caso["cruda"],
                "edad_rsna": edad,
                "clase_rsna": clase,
                "sexo_rsna": sexo,
                "sintomas": (dict(SINTOMAS, texto_libre=COMENTARIO)
                             if perfil.clave == "con_comentario_del_paciente"
                             else dict(SINTOMAS)),
            })
    return casos


def nombre_fichero(caso):
    sufijo = "-FABRICADO" if caso["perfil"].fabricado else ""
    return f"{caso['patientId']}{sufijo}.txt"


# --------------------------------------------------------------------------
# El copiloto, y la redaccion con el codigo del workflow
# --------------------------------------------------------------------------
def llamar_al_copiloto(url, ruta_dcm, tiempo_limite=120):
    """Un `tools/call` suelto, como el del nodo `Llamar al copiloto`.

    Devuelve (statusCode, cuerpo). `neverError: true` en el nodo significa que
    un 413 o un 500 llegan al codigo como respuesta, no como excepcion: aqui se
    hace lo mismo para que `Leer respuesta` vea lo que veria en n8n.
    """
    b64 = base64.b64encode(pathlib.Path(ruta_dcm).read_bytes()).decode()
    cuerpo = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "clasificar_radiografia",
                   "arguments": {"dicom_base64": b64}}}).encode()
    pet = urllib.request.Request(
        url, data=cuerpo,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    try:
        with urllib.request.urlopen(pet, timeout=tiempo_limite) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as exc:                      # red, DNS, timeout
        return None, f"{type(exc).__name__}: {exc}"


def comprobar_el_copiloto(url):
    """Un `tools/list` antes de empezar. Si el copiloto no esta, se dice YA.

    Existe por un fallo real: con el contenedor recien arrancado y todavia
    cargando el modelo, los 19 casos de una pasada volvieron
    `copiloto_no_responde`, el arnes escribio los 19 ficheros sin inmutarse y el
    corpus parecia un corpus. Veinte minutos de conversaciones por Telegram para
    eso son un mal negocio, y un corpus que parece bueno y no lo es es peor.
    """
    pet = urllib.request.Request(
        url, data=json.dumps({"jsonrpc": "2.0", "id": 1,
                              "method": "tools/list"}).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    try:
        with urllib.request.urlopen(pet, timeout=30) as r:
            cuerpo = r.read().decode("utf-8", "replace")
        if "clasificar_radiografia" not in cuerpo:
            raise SystemExit(
                f"el copiloto contesta en {url} pero no ofrece "
                f"`clasificar_radiografia`. No es el servidor que se espera.")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"el copiloto contesto HTTP {e.code} a un tools/list "
                         f"en {url}: no se puede reproducir nada.")
    except Exception as exc:
        raise SystemExit(
            f"no se alcanza el copiloto en {url} ({type(exc).__name__}: "
            f"{exc}).\nLevanta el contenedor de prueba o apunta COPILOTO_URL a "
            f"donde este. Si acabas de arrancarlo, dale unos segundos: tarda en "
            f"cargar el modelo.")


def redactar(lote):
    """Ejecuta `Leer respuesta` y `Desenlace` del workflow con `node`.

    Un solo proceso para todos los casos: arrancar node 49 veces es medio minuto
    tirado.
    """
    if not lote:
        return []
    salida = subprocess.run(
        ["node", str(REDACTOR)], input=json.dumps(lote), capture_output=True,
        text=True, encoding="utf-8")
    if salida.returncode != 0:
        raise SystemExit("`node pruebas/redactar.mjs` fallo:\n"
                         + (salida.stderr or "")[:3000])
    return json.loads(salida.stdout)


# --------------------------------------------------------------------------
# Los bots
# --------------------------------------------------------------------------
class Bots:
    """Conduce las dos conversaciones contra un n8n vivo."""

    def __init__(self, base, secreto, token, bd, chat_paciente,
                 chat_profesional, chat_subida, ruta_paciente,
                 ruta_profesional):
        self.base = base.rstrip("/")
        self.secreto = secreto
        self.token = token
        self.bd = bd
        self.paciente = chat_paciente
        self.profesional = chat_profesional
        # El chat donde se SUBEN las placas para conseguir un `file_id`, que no
        # tiene por que ser el de los updates fabricados. Ver `subir_placa`.
        self.subida = chat_subida
        self.ruta_paciente = ruta_paciente
        self.ruta_profesional = ruta_profesional
        self.contador = 0
        # Hasta que `comprobar_si_el_bot_puede_contestar` diga lo contrario, no se
        # afirma que el bot pueda entregar nada.
        self.entrega = "rechazada"
        self.motivo_entrega = "no se comprobo"

    def _alcanza_el_chat(self, chat):
        """Si el bot del profesional puede escribirle a `chat`. (ok, detalle)."""
        pet = urllib.request.Request(
            f"https://api.telegram.org/bot{self.token}/getChat?chat_id={chat}")
        try:
            with urllib.request.urlopen(pet, timeout=30) as r:
                if json.loads(r.read().decode()).get("ok"):
                    return True, ""
                return False, "Telegram contesto sin `ok`"
        except urllib.error.HTTPError as e:
            return False, (f"HTTP {e.code}: "
                           + e.read().decode("utf-8", "replace")[:160])
        except Exception as exc:
            raise SystemExit(f"no se alcanza la API de Telegram: "
                             f"{type(exc).__name__}: {exc}")

    def comprobar_el_chat_de_subida(self):
        """Que el bot del profesional pueda escribir en el chat de subida.

        Un bot de Telegram NO puede escribir a un `chat_id` que no exista o que
        no haya empezado una conversacion con el: `sendDocument` contesta 400
        `chat not found`. Sin esta comprobacion, eso se descubre a los veinte
        segundos del primer caso y en forma de traza.
        """
        ok, detalle = self._alcanza_el_chat(self.subida)
        if not ok:
            raise SystemExit(
                f"el bot del profesional no puede usar el chat {self.subida} "
                f"para subir las placas ({detalle}).\n"
                f"Tiene que ser un chat REAL que ya le haya escrito al bot: un "
                f"`file_id` solo existe si alguien subio el fichero, y un bot no "
                f"puede escribir primero. Pon uno en CHAT_SUBIDA_PLACAS.")

    def comprobar_si_el_bot_puede_contestar(self):
        """Si el bot podra ENTREGAR sus mensajes al chat de los updates.

        No es una comodidad, es la honestidad del corpus. Con un `chat_id`
        inventado -que es el valor por defecto, y a proposito- el nodo `Responder`
        se lleva un 400 `chat not found`: la fila de `consultas` se escribe igual
        porque `Registrar` va antes, pero **nadie lee el mensaje**. Un corpus que
        titulara «el mensaje que recibio el profesional» estaria afirmando algo
        falso de las 49 veces.

        Peor con el segundo mensaje: `Enviar texto del paciente` cuelga DETRAS de
        `Responder`, que no tiene `onError`, asi que cuando `Responder` falla ese
        nodo **no se intenta siquiera**. Verificado en las conexiones del JSON
        exportado.
        """
        ok, detalle = self._alcanza_el_chat(self.profesional)
        self.entrega = "intentada" if ok else "rechazada"
        self.motivo_entrega = detalle
        return self.entrega

    # -- transporte ------------------------------------------------------
    def _post(self, ruta, cuerpo):
        self.contador += 1
        cuerpo = dict(cuerpo, update_id=self.contador)
        pet = urllib.request.Request(
            f"{self.base}/webhook/{ruta}", data=json.dumps(cuerpo).encode(),
            headers={"Content-Type": "application/json",
                     "X-Telegram-Bot-Api-Secret-Token": self.secreto})
        try:
            with urllib.request.urlopen(pet, timeout=60) as r:
                r.read()
                return r.status
        except urllib.error.HTTPError as e:
            e.read()
            return e.code
        finally:
            # La pausa va SIEMPRE, tambien si el POST fallo: el limite es del
            # chat, no del exito.
            time.sleep(PAUSA)

    def _mensaje(self, chat, texto):
        return {"message": {"message_id": self.contador + 1, "date": 0,
                            "chat": {"id": chat, "type": "private"},
                            "from": {"id": chat, "is_bot": False,
                                     "first_name": "Arnes"},
                            "text": texto}}

    def _boton(self, chat, dato):
        return {"callback_query": {
            "id": str(uuid.uuid4()), "data": dato,
            "from": {"id": chat, "is_bot": False, "first_name": "Arnes"},
            "message": {"message_id": self.contador + 1, "date": 0,
                        "chat": {"id": chat, "type": "private"}}}}

    def _documento(self, chat, file_id, tamano):
        return {"message": {"message_id": self.contador + 1, "date": 0,
                            "chat": {"id": chat, "type": "private"},
                            "from": {"id": chat, "is_bot": False,
                                     "first_name": "Arnes"},
                            "document": {"file_id": file_id,
                                         "file_name": "placa.dcm",
                                         "file_size": tamano,
                                         "mime_type": "application/octet-stream"}}}

    def _esperar(self, sql, parametros, esperado, intentos=60):
        visto = None
        for _ in range(intentos):
            fila = self.bd.execute(sql, parametros).fetchone()
            visto = fila[0] if fila else None
            if visto == esperado:
                return visto
            time.sleep(0.5)
        return visto

    # -- el paciente -----------------------------------------------------
    def conversacion_del_paciente(self, sintomas):
        """Devuelve el codigo seudonimo, o None con el motivo del fallo."""
        chat = self.paciente
        # §4.2 limita a 5 cuestionarios completados por chat_id y dia. Un corpus
        # de 49 casos desde un solo chat choca con eso al sexto, asi que el
        # contador del chat DE PRUEBA se borra antes de cada caso. Es la misma
        # licencia que se toma `tests/test_flujo_paciente.py` y por la misma
        # razon; la contrapartida es que este arnes NO ejercita ese limite, y
        # ninguna otra prueba lo hace tampoco.
        self.bd.execute("DELETE FROM limite_paciente WHERE chat_id = %s", (chat,))
        self.bd.execute("DELETE FROM sesiones_paciente WHERE chat_id = %s", (chat,))
        marca = self.bd.execute("SELECT now()").fetchone()[0]

        self._post(self.ruta_paciente, self._mensaje(chat, "/start"))
        self._post(self.ruta_paciente, self._boton(chat, "consent:si"))
        if self._esperar("SELECT count(*) FROM sesiones_paciente WHERE"
                         " chat_id = %s", (chat,), 1, intentos=20) != 1:
            return None, "el bot del paciente no abrio la sesion tras aceptar"
        for dato in BOTONES_PACIENTE:
            self._post(self.ruta_paciente, self._boton(chat, dato))
        if sintomas.get("texto_libre"):
            self._post(self.ruta_paciente,
                       self._mensaje(chat, sintomas["texto_libre"]))
        else:
            self._post(self.ruta_paciente, self._boton(chat, "p7:omitir"))

        # `cuestionarios` esta identificada por el codigo seudonimo y NO lleva el
        # chat_id -eso es justamente lo que el seudonimo existe para impedir
        # (§4.2)-, asi que no se puede preguntar "el cuestionario de MI chat".
        # Coger el mas reciente sin mas seria un error grave: si un paciente REAL
        # completara el cuestionario durante los veinte minutos de la corrida, el
        # arnes se llevaria SU codigo, el bot del profesional leeria SUS sintomas
        # y acabarian escritos en el corpus. Se exige que las respuestas sean
        # exactamente las que este arnes acaba de enviar.
        esperadas = json.dumps(sintomas)
        for _ in range(40):
            fila = self.bd.execute(
                "SELECT codigo FROM cuestionarios WHERE creado_en > %s"
                # ASCENDENTE, y no es un detalle. Con `DESC` la consulta PREFERIA
                # al intruso: entre dos filas que empaten en respuestas, la del
                # arnes es la que se creo PRIMERO -es la que desbloquea esta
                # espera- y la de un paciente real que colisionara llegaria
                # despues, o sea primera con `DESC`. Con `ASC` sale la nuestra.
                " AND respuestas = %s::jsonb ORDER BY creado_en ASC LIMIT 1",
                (marca, esperadas)).fetchone()
            if fila:
                return fila[0], ""
            time.sleep(0.5)
        return None, "el cuestionario no llego a nacer: no hay codigo"

    # -- el profesional --------------------------------------------------
    def subir_placa(self, ruta):
        """Sube el DICOM con el bot del PROFESIONAL y devuelve su `file_id`.

        Con ese bot y no con el de pruebas: en Telegram un `file_id` solo lo
        resuelve el bot que lo obtuvo, asi que uno conseguido con otro token
        haria que el `getFile` del flujo contestara `wrong file identifier` y el
        arnes estaria midiendo eso.

        Y a `self.subida`, que NO tiene por que ser el chat de los updates
        fabricados: un `file_id` no esta atado a ningun chat -es del bot-,
        mientras que subir un fichero SI exige un chat real. Asi el chat_id que
        viaja en los updates puede seguir siendo uno inventado, que es lo
        correcto para no meter trafico de pruebas en la conversacion de un
        clinico de verdad.
        """
        limite = "----" + uuid.uuid4().hex
        datos = pathlib.Path(ruta).read_bytes()
        cuerpo = (f"--{limite}\r\nContent-Disposition: form-data; "
                  f'name="chat_id"\r\n\r\n{self.subida}\r\n').encode()
        cuerpo += (f"--{limite}\r\nContent-Disposition: form-data; "
                   f'name="document"; filename="{pathlib.Path(ruta).name}"\r\n'
                   "Content-Type: application/octet-stream\r\n\r\n").encode()
        cuerpo += datos + f"\r\n--{limite}--\r\n".encode()
        pet = urllib.request.Request(
            f"https://api.telegram.org/bot{self.token}/sendDocument",
            data=cuerpo,
            headers={"Content-Type":
                     f"multipart/form-data; boundary={limite}"})
        with urllib.request.urlopen(pet, timeout=300) as r:
            respuesta = json.loads(r.read().decode())
        if not respuesta.get("ok"):
            raise RuntimeError(f"sendDocument no dijo ok: {respuesta}")
        time.sleep(PAUSA)
        return respuesta["result"]["document"]["file_id"], len(datos)

    def conversacion_del_profesional(self, codigo, ruta_dcm):
        """Devuelve la fila de `consultas` que nacio, o None con el motivo."""
        chat = self.profesional
        ruta = self.ruta_profesional
        # Acotado a NUESTRO chat_id, no al maximo global: por la misma razon que
        # arriba, una consulta de un profesional de verdad hecha a la vez no debe
        # acabar leida como si fuera de este arnes.
        antes = self.bd.execute(
            "SELECT COALESCE(max(id), 0) FROM consultas WHERE chat_id = %s",
            (chat,)).fetchone()[0]

        self._post(ruta, self._mensaje(chat, "/reiniciar"))
        if self._esperar("SELECT paso FROM sesiones_profesional WHERE"
                         " chat_id = %s", (chat,), 1, intentos=20) != 1:
            return None, "el bot del profesional no pidio el codigo"
        self._post(ruta, self._mensaje(chat, codigo))
        if self._esperar("SELECT paso FROM sesiones_profesional WHERE"
                         " chat_id = %s", (chat,), 2, intentos=20) != 2:
            return None, f"el codigo {codigo} no se acepto"
        for texto, siguiente in zip(SIGNOS_TECLEADOS, (3, 4)):
            self._post(ruta, self._mensaje(chat, texto))
            if self._esperar("SELECT paso FROM sesiones_profesional WHERE"
                             " chat_id = %s", (chat,), siguiente,
                             intentos=20) != siguiente:
                return None, f"el signo {texto} no avanzo al paso {siguiente}"
        for dato, siguiente in zip(SIGNOS_BOTONES, (5, 6)):
            self._post(ruta, self._boton(chat, dato))
            if self._esperar("SELECT paso FROM sesiones_profesional WHERE"
                             " chat_id = %s", (chat,), siguiente,
                             intentos=20) != siguiente:
                return None, f"el boton {dato} no avanzo al paso {siguiente}"

        try:
            file_id, tamano = self.subir_placa(ruta_dcm)
        except Exception as exc:
            # Una subida fallida no puede tirar la corrida entera: son veinte
            # minutos y 49 casos, y el resto sigue siendo util.
            return None, f"no se pudo subir la placa: {type(exc).__name__}: {exc}"
        self._post(ruta, self._documento(chat, file_id, tamano))
        if self._esperar("SELECT count(*) FROM consultas WHERE id > %s"
                         " AND chat_id = %s", (antes, chat), 1,
                         intentos=120) != 1:
            return None, "el flujo no escribio la fila de `consultas`"
        # Se leen tambien `sintomas` y `signos`: son los dos bloques clinicos del
        # mensaje, y si el arnes redactara con SUS literales en vez de con lo que
        # el flujo guardo, el corpus estaria AFIRMANDO esos dos bloques en vez de
        # observarlos. Es el fallo que el §4.4 declara temer -una respuesta en la
        # clave equivocada no da error, da un mensaje clinico distinto-.
        fila = self.bd.execute(
            "SELECT error, resultado, ms_extremo, codigo, sintomas, signos"
            " FROM consultas WHERE id > %s AND chat_id = %s"
            " ORDER BY id DESC LIMIT 1", (antes, chat)).fetchone()
        return {"error": fila[0], "resultado": fila[1], "ms_extremo": fila[2],
                "codigo": fila[3], "sintomas": fila[4], "signos": fila[5]}, ""


# --------------------------------------------------------------------------
# El corpus
# --------------------------------------------------------------------------
RAYA = "=" * 78
LINEA = "-" * 78

# Tres estados de entrega, y cada uno con su rotulo. El corpus NO puede titular
# «el mensaje que recibio el profesional» cuando nadie lo recibio: un corpus solo
# vale lo que vale su honestidad, y un rotulo es una afirmacion como cualquier
# otra.
ENTREGA = {
    "no_intentada": {
        "titulo": "EL MENSAJE QUE EL BOT HABRÍA ENVIADO, LITERAL",
        "titulo_paciente": "Y EL SEGUNDO MENSAJE, EL DE LAS PALABRAS DEL "
                           "PACIENTE",
        "se_obtuvo": "NO. No hubo envío: nadie condujo la conversación, así que "
                     "no había a quién enviárselo",
        "resumen": "no hubo envío, porque no se condujo ninguna conversación",
    },
    "rechazada": {
        "titulo": "EL MENSAJE QUE EL BOT COMPUSO — PERO NADIE LO RECIBIÓ",
        "titulo_paciente": "Y EL SEGUNDO MENSAJE, QUE NI SE INTENTÓ ENVIAR",
        "se_obtuvo": "NO. El bot lo compuso y lo intentó, y Telegram lo rechazó: "
                     "el chat de los updates es inventado. La fila de `consultas` "
                     "se escribió igual porque `Registrar` va antes de `Responder`",
        "resumen": "Telegram los rechazó: el chat de los updates es inventado",
    },
    "intentada": {
        "titulo": "EL MENSAJE QUE EL BOT ENVIÓ AL PROFESIONAL, LITERAL",
        "titulo_paciente": "Y A CONTINUACIÓN, EN UN MENSAJE APARTE, LO QUE "
                           "ESCRIBIÓ EL PACIENTE",
        "se_obtuvo": "el bot lo envió a un chat real. La entrega en sí no se ha "
                     "comprobado: el arnés no ve la respuesta de Telegram",
        "resumen": "el bot los envió a un chat real; la entrega no se comprobó",
    },
}

# De donde salen los dos bloques clinicos del mensaje.
OBSERVADO = {
    "observados": "INVENTADOS, pero LEÍDOS de `consultas`: son los que el flujo "
                  "guardó de verdad, no los que este arnés quiso mandar (§19 del "
                  "spec: RSNA no trae ni un síntoma)",
    "afirmados": "INVENTADOS, y AFIRMADOS por este arnés: sin conducir la "
                 "conversación no hay nada que leer de la base, así que estos "
                 "dos bloques NO están verificados (§19 del spec)",
}


def _num(valor, decimales):
    if valor is None:
        return "(no se calculo)"
    return f"{valor:.{decimales}f}".replace(".", ",")


def _punto(rotulo, valor, ancho=34):
    """`rotulo ..... valor`, con el valor colgando alineado si no cabe."""
    izquierda = "  " + (rotulo + " ").ljust(ancho, ".") + " "
    # `break_long_words=False`: una ruta de Windows o un patientId partidos por
    # la mitad dejan de poder copiarse, y eso es peor que pasarse de 78 columnas.
    trozos = textwrap.wrap(str(valor), width=78 - len(izquierda),
                           break_long_words=False,
                           break_on_hyphens=False) or [""]
    sangria = " " * len(izquierda)
    return "\n".join([izquierda + trozos[0]]
                     + [sangria + t for t in trozos[1:]])


def _parrafo(texto, sangria="   "):
    return "\n".join(textwrap.wrap(texto, width=78,
                                   initial_indent=sangria,
                                   subsequent_indent=sangria,
                                   break_long_words=False,
                                   break_on_hyphens=False))


def texto_del_caso(caso, obs, redaccion):
    """El fichero que alguien va a leer. Sin JSON, sin claves, sin siglas."""
    perfil = caso["perfil"]
    r = redaccion.get("resultado")
    clase = caso["clase_rsna"]
    glosa = CLASES_RSNA.get(clase)
    lineas = [
        RAYA,
        f" PERFIL   {perfil.orden:02d} — {perfil.titulo}",
        f" PLACA    {caso['patientId']}",
        RAYA,
        "",
        " QUÉ MIRAR EN ESTE PERFIL",
        _parrafo(perfil.que_mirar),
        "",
        " LO QUE SABEMOS DE ESTA PLACA ANTES DE PREGUNTARLE AL BOT",
        _punto("de dónde sale", perfil.de_donde),
        _punto("edad en la cabecera DICOM",
               "se le quitó la etiqueta" if perfil.clave.startswith("edad_desc")
               else f"{caso['edad_rsna']} años"),
        _punto("sexo", caso["sexo_rsna"]),
        _punto("lo que RSNA anotó",
               f"{clase} ({glosa})" if glosa else clase),
        _punto("puntuación del modelo (caché)",
               _num(caso["cruda_cache"], 4) if caso["cruda_cache"] is not None
               else "no está en el conjunto de prueba: esta placa se filtró "
                    "antes de partir el conjunto, y su puntuación no se ha "
                    "calculado"),
    ]
    if perfil.fabricado:
        lineas += ["", " ESTE DICOM ESTÁ FABRICADO",
                   _parrafo("No es una placa de RSNA tal como viene: es " +
                            perfil.de_donde + ". Se modificó a propósito para "
                            "llegar a una rama del §9 del spec que ningún caso "
                            "real puede alcanzar.")]

    lineas += ["", " LO QUE EL COPILOTO DIJO DE ELLA"]
    if r:
        lineas += [
            _punto("clasificación", r["clasificacion"].replace("_", " ")),
            _punto("probabilidad cruda",
                   f"{_num(r['probabilidad_cruda'], 4)}   "
                   f"(umbral {_num(r['umbral'], 4)})"),
            _punto("probabilidad calibrada",
                   _num(r["probabilidad_calibrada"], 4)),
            _punto("razón de verosimilitud",
                   f"{_num(r['razon_de_verosimilitud'], 3)}   "
                   + ("MULTIPLICA las probabilidades a favor de neumonía"
                      if r["razon_de_verosimilitud"] >= 1
                      else "RESTA probabilidades a favor de neumonía")),
            _punto("edad que leyó el servidor", f"{r['edad_paciente']} años"),
            _punto("tardó el modelo", f"{_num(r['milisegundos'], 1)} ms"),
        ]
    else:
        lineas += [_punto("no dio ningún resultado", "la rechazó"),
                   _punto("lo que quedó registrado",
                          redaccion.get("error") or "(nada)")]

    entrega = obs.get("entrega", "no_intentada")
    lineas += ["", " CÓMO SE OBTUVO"]
    if obs.get("con_bots"):
        lineas += [
            _punto("por los dos bots de Telegram", "sí"),
            _punto("código del cuestionario", obs.get("codigo") or "(ninguno)"),
            _punto("de extremo a extremo",
                   f"{obs['ms_extremo']} ms" if obs.get("ms_extremo") is not None
                   else "(no se registró)"),
            _punto("el bot y esta lectura coinciden",
                   obs.get("coincide", "(no se comprobó)")),
        ]
    else:
        lineas += [
            _punto("por los dos bots de Telegram",
                   "NO. Solo se llamó al copiloto y se redactó el mensaje con "
                   "el código del propio workflow: el texto es el que el bot "
                   "habría enviado, pero nadie condujo la conversación"),
            _punto("por qué", obs.get("motivo_sin_bots", "")),
        ]
    lineas.append(_punto("¿lo leyó alguien?", ENTREGA[entrega]["se_obtuvo"]))
    lineas += [
        _punto("síntomas", OBSERVADO[obs.get("bloques", "afirmados")]),
        _punto("signos", "fijos en todos los casos: 38,2 °C, 104 lpm, "
                         "crepitantes sí, murmullo normal"),
        "",
        LINEA,
        " " + ENTREGA[entrega]["titulo"],
        LINEA,
        "",
        redaccion["texto"],
        "",
    ]
    if redaccion.get("texto_paciente"):
        lineas += [LINEA, " " + ENTREGA[entrega]["titulo_paciente"], LINEA]
        if entrega == "rechazada":
            lineas.append(_parrafo(
                "Este segundo mensaje NO se intentó enviar, ni siquiera sin "
                "éxito: en el grafo, `Enviar texto del paciente` cuelga detrás "
                "de `Responder`, que no tiene manejo de error. Al fallar el "
                "primer envío, el nodo del segundo no llegó a ejecutarse. El "
                "texto es el que el bot habría mandado.", " "))
        lineas += ["", redaccion["texto_paciente"], ""]
    lineas += [
        LINEA,
        " ¿TIENE SENTIDO CLÍNICO LO QUE ACABA DE LEER?",
        " Eso es lo único que ninguna aserción automática puede juzgar, y es",
        " para lo que existe este fichero. Si algo suena raro, apúntelo aquí",
        " debajo y dígalo: el corpus se vuelve a generar cuando haga falta.",
        LINEA,
        "",
    ]
    return "\n".join(lineas) + "\n"


def escribir_corpus(destino, filas):
    """Escribe el corpus, BORRANDO primero el de la corrida anterior.

    Sin ese borrado, una corrida con `--por-perfil 3` sobre el corpus de una de
    10 dejaria siete ficheros viejos por perfil, indistinguibles de los nuevos y
    con los numeros de otro dia. Un corpus es para leerlo: un fichero rancio ahi
    dentro es peor que no tenerlo.

    Se borran SOLO las carpetas de los perfiles que esta corrida va a escribir:
    con `--solo`, arrasar las otras ocho seria una sorpresa desagradable. Y nunca
    `_fabricados/`, que se escribio antes que esto.
    """
    destino.mkdir(parents=True, exist_ok=True)
    for perfil in {caso["perfil"] for caso, _, _ in filas}:
        vieja = destino / perfil.carpeta
        if vieja.is_dir():
            shutil.rmtree(vieja)
    for caso, obs, redaccion in filas:
        carpeta = destino / caso["perfil"].carpeta
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / nombre_fichero(caso)).write_text(
            texto_del_caso(caso, obs, redaccion), encoding="utf-8")


# --------------------------------------------------------------------------
# El resumen: tiene que decir algo que no supieramos
# --------------------------------------------------------------------------
def _mediana(valores):
    valores = [v for v in valores if v is not None]
    return statistics.median(valores) if valores else None


def procedencia(filas, url):
    """De que copiloto salio este corpus.

    Hace falta porque el corpus no describe «el sistema», describe el sistema QUE
    CONTESTO. Dos ejemplos reales, los dos del mismo dia:

      - si se reentrena el modelo, cambian las puntuaciones, las razones de
        verosimilitud y hasta que placas caen en la banda del §8;
      - y el texto de los rechazos por edad llega LITERAL del servidor (§9,
        `relata: true`), asi que si la imagen desplegada es mas vieja que el
        repositorio, el corpus ensena la redaccion vieja y parece la de hoy.

    Sin esta seccion, eso no se ve en ningun sitio y el corpus se lee como si
    hablara del presente.
    """
    lineas = ["", " DE QUÉ COPILOTO SALE ESTO", _punto("  copiloto", url)]
    primero = next((red["resultado"] for _, _, red in filas
                    if red.get("resultado")), None)
    if primero:
        lineas += [
            _punto("  modelo", primero.get("modelo", "?")),
            _punto("  AUC de validación", _num(primero.get("auc_validacion"), 4)),
            _punto("  umbral", _num(primero.get("umbral"), 4)),
        ]
    lineas.append(_parrafo(
        "El texto de los rechazos lo escribe ESE servidor y el bot lo relata "
        "literal (§9). Si su imagen es más vieja que el repositorio, aquí se lee "
        "la redacción vieja: compárela con `inferencia.py` antes de dar por "
        "bueno un mensaje de rechazo."))
    return lineas


def resumen(filas, con_bots, destino, url_copiloto=None):
    lineas = [RAYA,
              f" CORPUS DE REPRODUCCIÓN — {len(filas)} casos reales de RSNA",
              RAYA]
    modo = ("los dos bots de Telegram, copiloto-bd y el copiloto"
            if con_bots else "solo el copiloto (--sin-bots): sin Telegram, sin "
                             "n8n y sin base de datos")
    lineas += [_punto("pasó por", modo),
               _punto("corpus en", str(destino))]
    # Que alguien lea el mensaje es otra cosa que que el bot lo componga, y el
    # resumen lo dice antes que nada: si nadie lo recibio, el corpus es igual de
    # util pero no es una prueba de entrega.
    entregas = {}
    for _, obs, _ in filas:
        e = obs.get("entrega", "no_intentada")
        entregas[e] = entregas.get(e, 0) + 1
    for estado, n in sorted(entregas.items(), key=lambda x: -x[1]):
        lineas.append(_punto("  mensajes enviados de verdad"
                             if estado == "intentada"
                             else "  mensajes que no leyó nadie",
                             f"{n}, y {ENTREGA[estado]['resumen']}"))
    lineas.append("")

    lineas.append(" CASOS POR PERFIL")
    presentes = 0
    for perfil in PERFILES:
        n = sum(1 for c, _, _ in filas if c["perfil"] is perfil)
        if n:
            presentes += 1
            lineas.append(_punto("  " + perfil.carpeta, n))
    if presentes < len(PERFILES):
        lineas.append(_parrafo(
            f"Esta corrida cubrio {presentes} de los {len(PERFILES)} perfiles. "
            f"Si en `{destino.name}/` hay carpetas de las que no aparecen aqui, "
            f"son de otra corrida y este resumen NO las describe."))

    lineas += ["", " LOS CASOS, UNO POR LÍNEA Y EN ORDEN DE LECTURA",
               "   OPA = RSNA anotó opacidad · NO-OPA = sin opacidad pero no "
               "normal · NORM = normal",
               "   RV = razón de verosimilitud · AVISO = llevó el aviso de "
               "discrepancia del §8", ""]
    ABREVIA = {"Lung Opacity": "OPA", "No Lung Opacity / Not Normal": "NO-OPA",
               "Normal": "NORM"}
    for perfil in PERFILES:
        propias = [(c, red) for c, _, red in filas if c["perfil"] is perfil]
        if not propias:
            continue
        lineas.append(f"   {perfil.carpeta}")
        for caso, red in propias:
            r = red.get("resultado")
            cruda = (_num(caso["cruda_cache"], 4)
                     if caso["cruda_cache"] is not None else "—")
            if r:
                cola = ("opacidad probable"
                        if r["clasificacion"] == "opacidad_probable"
                        else "sin opacidad").ljust(17)
                cola += f"  RV {_num(r['razon_de_verosimilitud'], 2):>6}"
                if (r["clasificacion"] == "opacidad_probable"
                        and r["razon_de_verosimilitud"] < 1.0):
                    cola += "  AVISO"
            else:
                cod = (red.get("error") or "").split(":", 1)[0].strip()
                cola = f"RECHAZADA: {cod}"
            lineas.append(
                f"     {caso['patientId'][:8]}… "
                f"{str(caso['edad_rsna']) + 'a':>5} {caso['sexo_rsna']:<2} "
                f"{ABREVIA.get(caso['clase_rsna'], '?'):<6} {cruda:>7}  {cola}")

    # Rechazos, por codigo. La columna del §5.1 guarda `codigo: texto`.
    rechazos = {}
    for _, _, red in filas:
        if red.get("error"):
            cod = red["error"].split(":", 1)[0].strip()
            rechazos[cod] = rechazos.get(cod, 0) + 1
    total_rechazos = sum(rechazos.values())
    lineas += ["", f" RECHAZOS — {total_rechazos} de los {len(filas)} casos no "
                   f"llegaron a dar un resultado"]
    for cod, n in sorted(rechazos.items(), key=lambda x: -x[1]):
        lineas.append(_punto("  " + cod, n))
    if not rechazos:
        lineas.append("   ninguno")
    # `copiloto_no_responde` no es un desenlace clinico: es el copiloto caido a
    # mitad de corrida, y entonces esos ficheros del corpus no valen nada.
    caidos = rechazos.get("copiloto_no_responde", 0)
    if caidos:
        lineas.append(_parrafo(
            f"!! {caidos} de esos rechazos son «copiloto_no_responde». Eso no es "
            f"un desenlace clínico: es el servicio de imagen sin contestar. Esos "
            f"casos hay que volver a correrlos, y sus ficheros del corpus no "
            f"dicen nada de cómo se comporta el bot."))

    # El aviso del §8. El subconjunto esta estratificado A PROPOSITO, asi que
    # este porcentaje NO estima el de la poblacion: para eso esta el nivel 1.
    con_resultado = [(c, red) for c, _, red in filas if red.get("resultado")]
    positivos = [(c, red) for c, red in con_resultado
                 if red["resultado"]["clasificacion"] == "opacidad_probable"]
    avisados = [(c, red) for c, red in positivos
                if red["resultado"]["razon_de_verosimilitud"] < 1.0]
    AVISO = "El cribado marca esta placa"
    en_texto = sum(1 for _, red in con_resultado if AVISO in red["texto"])
    # POR PLACA y no por caso. El perfil 04 reusa a proposito la primera placa de
    # la banda, asi que contar casos contaba esa placa dos veces: el «8 de 11» de
    # la primera version era «7 de 10» mal sumado.
    placas_avisadas = {c["patientId"] for c, _ in avisados}
    lineas += ["", " EL AVISO DE DISCREPANCIA DEL §8",
               _punto("  casos que dieron resultado", len(con_resultado)),
               _punto("  etiquetados «opacidad probable»", len(positivos)),
               _punto("  mensajes con el aviso (positivo y RV < 1)",
                      len(avisados))]
    if len(placas_avisadas) != len(avisados):
        lineas.append(_punto("  ...sobre placas DISTINTAS",
                             f"{len(placas_avisadas)}: el perfil 04 reusa una "
                             f"placa de la banda, y las cuentas de abajo van por "
                             f"placa para no contarla dos veces"))
    if en_texto != len(avisados):
        lineas.append(_parrafo(
            f"!! El aviso aparece en {en_texto} mensajes pero los números dicen "
            f"que debería aparecer en {len(avisados)}. ALGO NO CUADRA: o el "
            f"texto del aviso cambió, o la condición que lo dispara no es la "
            f"del §8."))
    else:
        lineas.append(_parrafo("Y el aviso aparece en esos mensajes y solo en "
                               "esos: se comprobó buscándolo en el texto, no "
                               "dándolo por hecho."))
    if placas_avisadas:
        clases = {c["patientId"]: c["clase_rsna"] for c, _ in avisados}
        acierta = sum(1 for pid in placas_avisadas
                      if clases[pid] != "Lung Opacity")
        lineas.append(_punto("  y RSNA NO anotó opacidad en",
                             f"{acierta} de esas {len(placas_avisadas)} placas "
                             f"({acierta / len(placas_avisadas) * 100:.0f} %): "
                             f"cuando el aviso salta, suele tener razón"))
    lineas.append(_parrafo(
        "OJO con los porcentajes de aquí arriba: el subconjunto está "
        "estratificado a propósito y sobrerrepresenta la banda, así que NO "
        "estiman los de la población. Eso lo mide el nivel 1 "
        "(`pruebas/caracterizar_conjunto.py`) sobre las 3 811 placas: el aviso "
        "salta en el 23,3 % de los positivos, y en el 80,5 % de esos casos no "
        "había opacidad de verdad."))

    # Latencia. La cifra interesante no es la mediana: es cuanto de ella NO es
    # el modelo.
    modelo = _mediana([red["resultado"]["milisegundos"]
                       for _, red in con_resultado])
    lineas += ["", " LATENCIA"]
    if con_bots:
        extremo = _mediana([obs.get("ms_extremo") for _, obs, _ in filas])
        lineas.append(_punto("  de extremo a extremo (mediana)",
                             f"{extremo:.0f} ms" if extremo is not None
                             else "(no se registró)"))
        lineas.append(_punto("  solo el modelo (mediana)",
                             f"{_num(modelo, 1)} ms" if modelo is not None
                             else "—"))
        if extremo is not None and modelo is not None:
            resto = extremo - modelo
            lineas.append(_punto(
                "  todo lo demás",
                f"{resto:.0f} ms, el {resto / extremo * 100:.0f} % del total. "
                f"El modelo no es el cuello de botella: lo son Telegram, n8n y "
                f"la base"))
    else:
        # Medido en Python alrededor de la llamada, NO con el `ms` que devuelve
        # `Desenlace`. Ese `ms` es `Date.now() - t0`, y `redactar()` corre UNA vez
        # al final de la corrida: el `t0` de cada caso es de cuando se llamo al
        # copiloto, asi que el `ms` de todos abarcaba hasta el final de todo. La
        # primera version imprimia 1 445 ms para una ida y vuelta de unos 60.
        local = _mediana([obs.get("ms_arnes") for _, obs, _ in filas])
        lineas.append(_punto("  solo el modelo (mediana)",
                             f"{_num(modelo, 1)} ms" if modelo is not None
                             else "—"))
        lineas.append(_punto("  ida y vuelta de este arnés",
                             f"{_num(local, 1)} ms (mediana)"
                             if local is not None else "—"))
        lineas.append(_parrafo(
            "Sin los bots no hay latencia de extremo a extremo que medir: lo "
            "de arriba es esta máquina hablando con el contenedor, no un "
            "clínico esperando en Telegram."))

    # Desacuerdos entre lo que quedo en `consultas` y lo que esta lectura da.
    if con_bots:
        malos = [c["patientId"] for c, obs, _ in filas
                 if obs.get("coincide") not in (None, "sí")]
        fallos = [(c["patientId"], obs.get("fallo")) for c, obs, _ in filas
                  if obs.get("fallo")]
        lineas += ["", " COHERENCIA"]
        lineas.append(_punto("  casos donde el bot y esta lectura difieren",
                             len(malos) if malos else "ninguno"))
        for pid in malos[:10]:
            lineas.append(f"     {pid}")
        lineas.append(_punto("  conversaciones que no llegaron al final",
                             len(fallos) if fallos else "ninguna"))
        for pid, motivo in fallos[:10]:
            lineas.append(f"     {pid}  {motivo}")

    if url_copiloto:
        lineas += procedencia(filas, url_copiloto)

    lineas += ["", RAYA,
               _parrafo("El corpus es para LEERLO, y no hay atajo. Empiece por "
                        "el perfil 03: ahí el cribado y la evidencia se "
                        "contradicen, y si el aviso está bien dicho o no es "
                        "algo que solo puede decir un clínico.", " "),
               RAYA]
    return "\n".join(lineas)


# --------------------------------------------------------------------------
def _conectar(dsn):
    try:
        import psycopg
    except ImportError:
        raise SystemExit("falta psycopg: pip install 'psycopg[binary]'")
    return psycopg.connect(dsn, autocommit=True, connect_timeout=10)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        # El resumen lleva «§» y acentos; una consola en cp1252 los rechazaria y
        # el arnes moriria por el print, despues de 20 minutos de trabajo.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--por-perfil", type=int, default=10,
                   help="cuantos casos por perfil (por defecto 10)")
    p.add_argument("--solo", metavar="PERFIL",
                   choices=sorted(POR_CLAVE), help="un solo perfil")
    p.add_argument("--sin-bots", action="store_true",
                   help="no tocar n8n, Telegram ni la base: solo redactar")
    p.add_argument("--salida", default=str(CORPUS),
                   help=f"donde escribir el corpus (por defecto {CORPUS})")
    args = p.parse_args()

    url_copiloto = os.environ.get("COPILOTO_URL",
                                  "http://127.0.0.1:18000/mcp")
    falta = [v for v in ("COPILOTO_BD_DSN", "TELEGRAM_SECRET_PRUEBA",
                         "TELEGRAM_TOKEN_PROFESIONAL")
             if not os.environ.get(v)]
    con_bots = not args.sin_bots and not falta
    motivo_sin_bots = ("--sin-bots" if args.sin_bots
                       else "falta " + ", ".join(falta))
    if not con_bots:
        print(f"MODO SIN BOTS ({motivo_sin_bots}).")
        print("Se llamara al copiloto y se redactara con el codigo del "
              "workflow, pero")
        print("NO se conducira ninguna conversacion: el corpus lo dira caso "
              "por caso.\n")

    destino = pathlib.Path(args.salida)
    comprobar_el_copiloto(url_copiloto)
    casos = construir_casos(args.por_perfil, args.solo, destino)
    print(f"{len(casos)} casos, copiloto en {url_copiloto}")
    if con_bots:
        # 16 updates por caso mas la subida de la placa, cada uno con su pausa.
        estimado = len(casos) * 17 * PAUSA / 60
        print(f"con los bots: al menos {estimado:.0f} minutos "
              f"(17 mensajes por caso, {PAUSA} s entre mensajes)\n")

    bots = bd = None
    profesional_existia = None
    chat_profesional = int(os.environ.get("CHAT_PROFESIONAL_PRUEBA", 999000210))
    if con_bots:
        bd = _conectar(os.environ["COPILOTO_BD_DSN"])
        bots = Bots(
            base=os.environ.get("N8N_URL", "https://n8n.[retirado].com"),
            secreto=os.environ["TELEGRAM_SECRET_PRUEBA"],
            token=os.environ["TELEGRAM_TOKEN_PROFESIONAL"],
            bd=bd,
            chat_paciente=int(os.environ.get("CHAT_PACIENTE_PRUEBA", 999000201)),
            chat_profesional=chat_profesional,
            chat_subida=int(os.environ.get("CHAT_SUBIDA_PLACAS",
                                           chat_profesional)),
            ruta_paciente=os.environ.get("WEBHOOK_PACIENTE",
                                         "copiloto-paciente"),
            ruta_profesional=os.environ.get("WEBHOOK_PROFESIONAL",
                                            "copiloto-profesional"))
        # ANTES de tocar la lista blanca: si esto aborta, no se ha dado de alta a
        # nadie y no hay nada que limpiar. Al reves quedaria un chat_id de pruebas
        # autorizado en la unica puerta del bot del profesional (D6).
        bots.comprobar_el_chat_de_subida()
        if bots.comprobar_si_el_bot_puede_contestar() == "rechazada":
            print(f"AVISO: el bot no puede entregar sus mensajes al chat "
                  f"{chat_profesional} ({bots.motivo_entrega}).")
            print("La corrida sirve igual -la fila de `consultas` se escribe "
                  "antes del envio- y el")
            print("corpus lo dira caso por caso: NO titulara «el mensaje que "
                  "recibio el profesional».\n")
        profesional_existia = bd.execute(
            "SELECT count(*) FROM profesionales WHERE chat_id = %s",
            (chat_profesional,)).fetchone()[0] > 0
        bd.execute(
            "INSERT INTO profesionales (chat_id, nombre) VALUES (%s, %s)"
            " ON CONFLICT (chat_id) DO UPDATE SET activo = true, baja_en = NULL",
            (chat_profesional, "(arnes de reproduccion)"))

    try:
        filas = []
        lote = []
        for i, caso in enumerate(casos, 1):
            print(f"[{i:>3}/{len(casos)}] {caso['perfil'].carpeta}  "
                  f"{caso['patientId']}", flush=True)
            obs = {"con_bots": False, "motivo_sin_bots": motivo_sin_bots,
                   "entrega": "no_intentada", "bloques": "afirmados"}
            if con_bots:
                obs["con_bots"] = True
                obs["entrega"] = bots.entrega
                codigo, fallo = bots.conversacion_del_paciente(caso["sintomas"])
                if codigo is None:
                    obs["fallo"] = fallo
                    print(f"        no hubo codigo: {fallo}")
                else:
                    obs["codigo"] = codigo
                    consulta, fallo = bots.conversacion_del_profesional(
                        codigo, caso["ruta_dcm"])
                    if consulta is None:
                        obs["fallo"] = fallo
                        print(f"        {fallo}")
                    else:
                        obs.update(consulta)
            # Los dos bloques clinicos se redactan con lo que el flujo GUARDO
            # cuando eso existe, y no con los literales de este arnes: si no, el
            # corpus los afirmaria en vez de observarlos.
            if obs.get("sintomas") is not None:
                obs["bloques"] = "observados"
            sintomas = (obs["sintomas"] if obs.get("sintomas") is not None
                        else caso["sintomas"])
            signos = obs["signos"] if obs.get("signos") else SIGNOS
            t0 = int(time.time() * 1000)
            reloj = time.perf_counter()
            estado, cuerpo = llamar_al_copiloto(url_copiloto, caso["ruta_dcm"])
            # Medido AQUI, no con el `ms` de `Desenlace`: `redactar()` corre una
            # sola vez al final, asi que aquel `ms` llegaba hasta el final de la
            # corrida entera y no hasta el final de esta llamada.
            obs["ms_arnes"] = (time.perf_counter() - reloj) * 1000
            lote.append({
                "http": {"statusCode": estado, "cuerpo": cuerpo},
                "decidir": {"chat_id": chat_profesional, "t0": t0,
                            "codigo": obs.get("codigo") or "",
                            "sintomas": sintomas, "signos": signos},
                "normalizar": {"chat_id": chat_profesional, "t0": t0}})
            filas.append([caso, obs, None])

        print("\nredactando con el `jsCode` del workflow...")
        redacciones = redactar(lote)
        if len(redacciones) != len(filas):
            # Un `zip` mas corto dejaria filas sin redaccion, se filtrarian mas
            # abajo, y el corpus saldria incompleto sin decirlo.
            raise SystemExit(f"el redactor devolvio {len(redacciones)} mensajes "
                             f"para {len(filas)} casos: el corpus saldria "
                             f"incompleto y no se escribe nada.")
        for fila, redaccion in zip(filas, redacciones):
            fila[2] = redaccion
            caso, obs = fila[0], fila[1]
            if obs.get("con_bots") and not obs.get("fallo"):
                obs["coincide"] = _coincide(obs, caso, redaccion)
    finally:
        if bd is not None:
            bd.execute("DELETE FROM sesiones_profesional WHERE chat_id = %s",
                       (chat_profesional,))
            if profesional_existia is False:
                # No se deja un chat_id de pruebas en la lista blanca: es la
                # unica puerta del bot del profesional (D6).
                bd.execute("DELETE FROM profesionales WHERE chat_id = %s",
                           (chat_profesional,))
            bd.close()

    filas = [(c, o, r) for c, o, r in filas if r is not None]
    escribir_corpus(destino, filas)
    texto = resumen(filas, con_bots, destino, url_copiloto)
    (destino / "RESUMEN.txt").write_text(texto + "\n", encoding="utf-8")
    print()
    print(texto)
    if con_bots:
        print(f"\nLas {len(filas)} filas que este arnes dejo en `consultas` "
              f"llevan chat_id {chat_profesional}.")
        print("Para quitarlas:  DELETE FROM consultas WHERE chat_id = "
              f"{chat_profesional};")
    return 0


def _coincide(obs, caso, redaccion):
    """Dice si lo que quedo en `consultas` y esta lectura cuentan lo mismo.

    Compara CUATRO cosas y no dos. Antes comparaba la puntuacion, la
    clasificacion y el codigo de error, y con eso un mensaje podia decir
    «tos: (valor no reconocido)» y «EXPLORADO — (sin datos completos)» y el corpus
    seguia poniendo «coinciden: si»: los dos bloques clinicos no entraban en la
    comparacion. Son justo los que un clinico lee primero.
    """
    enviados = (caso["sintomas"], SIGNOS)
    guardados = (obs.get("sintomas"), obs.get("signos"))
    if obs.get("sintomas") is not None and guardados[0] != enviados[0]:
        faltan = [k for k in enviados[0]
                  if guardados[0].get(k) != enviados[0][k]]
        return (f"NO: `consultas.sintomas` no es lo que se envio; difieren "
                f"{', '.join(faltan) or 'las claves'}")
    if obs.get("signos") is not None and guardados[1] != enviados[1]:
        faltan = [k for k in enviados[1]
                  if guardados[1].get(k) != enviados[1][k]]
        return (f"NO: `consultas.signos` no es lo que se envio; difieren "
                f"{', '.join(faltan) or 'las claves'}")
    del_bot = obs.get("resultado")
    aqui = redaccion.get("resultado")
    if (del_bot is None) != (aqui is None):
        return "NO: uno dio resultado y el otro no"
    if del_bot and aqui:
        if abs(del_bot["probabilidad_cruda"] - aqui["probabilidad_cruda"]) > 1e-9:
            return (f"NO: el bot vio {del_bot['probabilidad_cruda']} y aquí "
                    f"{aqui['probabilidad_cruda']}")
        if del_bot["clasificacion"] != aqui["clasificacion"]:
            return "NO: clasificaciones distintas"
        return "sí"
    cod_bot = (obs.get("error") or "").split(":", 1)[0].strip()
    cod_aqui = (redaccion.get("error") or "").split(":", 1)[0].strip()
    if cod_bot != cod_aqui:
        return f"NO: el bot registró «{cod_bot}» y aquí sale «{cod_aqui}»"
    return "sí"


if __name__ == "__main__":
    raise SystemExit(main())
