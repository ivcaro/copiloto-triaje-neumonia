# -*- coding: utf-8 -*-
"""Que Telegram siga entregando donde debe: la mitad del §16 que no cabe dentro
de n8n.

POR QUE ESTO ES UN SCRIPT Y NO UN NODO DEL WORKFLOW. La comprobacion es
`GET https://api.telegram.org/bot<TOKEN>/getWebhookInfo`, y el token de Telegram
va **en la ruta de la URL**. En n8n un token vive en una credencial, y una
credencial solo sabe poner cabeceras, parametros de consulta o autenticacion
basica: no puede escribir en la URL. Tampoco hay operacion de webhook en el nodo
Telegram (v1.2: chat, callback, file, message; ninguna llama a `getWebhookInfo`).
Asi que dentro del workflow solo caben dos opciones, y las dos son peores que
esta: escribir el token en un parametro del nodo -donde se exporta al
repositorio y lo ve cualquiera con acceso al n8n del cliente, que es justo lo que
el §16 evita al no usar el Telegram Trigger-, o no comprobarlo.

Lo que SI hace el workflow, cada dia y sin ningun secreto, es sondear los dos
webhooks desde fuera: un POST sin `secret_token` a un webhook registrado y activo
devuelve 403, y a una ruta que no existe, 404. Eso cubre el lado de n8n -flujo
desactivado, ruta cambiada, proxy roto-. Lo que NO cubre, y cubre esto, es el
lado de Telegram:

  - que Telegram siga apuntando a nuestra URL y no a la del otro bot;
  - que no haya un `last_error_message` (un 403 ahi = el `secret_token` de n8n y
    el del `setWebhook` no coinciden, y el bot esta mudo sin que nada mas lo
    note);
  - que `pending_update_count` no este creciendo entre dos lecturas.

Los tokens NO se escriben en ningun sitio: se leen del entorno si ya estan
(`TELEGRAM_TOKEN_PACIENTE`, `TELEGRAM_TOKEN_PROFESIONAL`) o se piden por
teclado. Salen siempre de BotFather (`/token`); el que esta en una credencial de
n8n no se puede volver a leer desde la interfaz.

Uso:
    C:\\venv-copiloto\\Scripts\\python.exe pruebas/verificar_webhooks.py
    C:\\venv-copiloto\\Scripts\\python.exe pruebas/verificar_webhooks.py --sin-teclado

A mano, en una consola, el token que no este en el entorno se pide por
teclado; sin consola, no. Con `--sin-teclado` no se pide NUNCA: el bot sin
token en el entorno no se comprueba y se cuenta como problema.

LA TAREA PROGRAMADA LO LANZA CON `--sin-teclado` (§5 del manual de operacion).
Mirar si hay consola no basta: el Programador de tareas le da a python.exe una
consola aunque nadie la vea, y sin la opcion `getpass` se quedaria esperando en
ella un token que nadie va a escribir -sin avisar de nada, y sin dejar que la
tarea vuelva a correr los dias siguientes, porque sigue en marcha-.

Devuelve 0 si los dos webhooks estan como deben, y 1 si hay algo que arreglar.

`N8N_URL` ES OBLIGATORIA y no tiene valor por defecto: es la URL base del n8n
que sirve a los dos bots (por ejemplo `https://n8n.ejemplo.test`), y con ella se
calcula donde tendria que estar entregando Telegram. El repositorio no lleva la
de ningun despliegue. Sin ella, o mal puesta (sin esquema, con una ruta detras,
entre comillas...), el script no pide ningun token ni comprueba nada: dice que
falta o que esta mal, lo manda por Telegram si el canal de avisos esta puesto,
y devuelve 1. Mal puesta, compararla con lo que devuelve Telegram daria por mal
apuntado un webhook que esta bien.

PARA LA TAREA PROGRAMADA DIARIA (§5 del manual de operacion) hacen falta dos
variables mas: `COPILOTO_CHAT_EQUIPO` y `TELEGRAM_TOKEN_AVISOS` -el token del bot
que ya usa el workflow de mantenimiento, para que el aviso caiga en el MISMO hilo
de Telegram-. Con las dos puestas, lo que encuentre se manda por Telegram; sin
ellas solo se imprime. Una tarea programada que escribe en un log que nadie lee
es el silencio que esto existe para romper.
"""
import argparse
import getpass
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from copiloto_triaje.config import url_base_n8n  # noqa: E402


def _base_de_n8n():
    """(base, motivo): la URL base de `N8N_URL`, o "" y por que no vale. Sin
    la variable el motivo va vacio: ausente y mal puesta se dicen distinto."""
    valor = os.environ.get("N8N_URL", "").strip()
    if not valor:
        return "", ""
    try:
        return url_base_n8n(valor), ""
    except ValueError as e:
        return "", str(e)


# Sin valor por defecto, y sin fallar al importar: `tests/test_mantenimiento.py`
# importa este modulo para probar el diagnostico, y tiene que poder hacerlo en
# una maquina que no sabe de ningun n8n, o que la tiene mal puesta. Quien se
# niega a seguir es `main()`.
BASE_N8N, N8N_URL_MAL_PUESTA = _base_de_n8n()

# Donde se pone, dicho para la tarea programada: una tarea de Windows no tiene
# variables propias, lee las del perfil del usuario que la corre.
DONDE_SE_PONE = (
    "en el entorno de quien corre el script; si lo corre la tarea programada, "
    "con `setx N8N_URL` en el perfil del usuario que la corre (manual de "
    "operación, §5, paso 2).")

SIN_N8N_URL = (
    "Falta N8N_URL: sin ella no se sabe en qué URL tendría que estar "
    "entregando Telegram, y no se ha comprobado ningún webhook.\n"
    "   Qué hacer: pon en N8N_URL la URL base del n8n que sirve a los dos bots "
    "(por ejemplo https://n8n.ejemplo.test), " + DONDE_SE_PONE)

# El motivo, y nunca el valor: el mensaje viaja por Telegram.
N8N_URL_MAL = (
    "N8N_URL está mal puesta ({motivo}): con ella no se sabe en qué URL "
    "tendría que estar entregando Telegram, y no se ha comprobado ningún "
    "webhook.\n"
    "   Qué hacer: pon en N8N_URL solo la URL base del n8n que sirve a los dos "
    "bots, con su esquema y sin nada detrás del host (por ejemplo "
    "https://n8n.ejemplo.test), " + DONDE_SE_PONE)

BOTS = [
    ("paciente", "TELEGRAM_TOKEN_PACIENTE", "copiloto-paciente",
     "\U0001fa7a Copiloto Triaje: Paciente (Telegram)"),
    ("profesional", "TELEGRAM_TOKEN_PROFESIONAL", "copiloto-profesional",
     "\U0001fa7a Copiloto Triaje: Profesional (Telegram)"),
]

# El `pending_update_count` de la lectura anterior, para poder ver si CRECE. Va
# fuera del repositorio: es estado de una maquina, no del proyecto.
MEMORIA = (pathlib.Path(os.environ.get("LOCALAPPDATA", pathlib.Path.home()))
           / "copiloto-triaje" / "webhooks.json")


def pedir_api(token: str, metodo: str):
    """Devuelve (ok, dato_o_descripcion). Un 404 aqui casi nunca es la URL: es
    que el token no existe (revocado o mal copiado)."""
    url = f"https://api.telegram.org/bot{token}/{metodo}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            cuerpo = json.load(r)
    except urllib.error.HTTPError as e:
        try:
            cuerpo = json.load(e)
        except Exception:
            return False, f"HTTP {e.code} sin cuerpo JSON"
        descripcion = cuerpo.get("description", f"HTTP {e.code}")
        if e.code == 401:
            return False, ("token no válido (401 Unauthorized): el token está "
                           "revocado o mal copiado. Saca uno nuevo de BotFather "
                           "con /token y actualiza la credencial de n8n")
        if e.code == 404:
            return False, ("token inexistente (404): no es la URL, es el token. "
                           "Compruébalo con getMe")
        return False, descripcion
    except OSError as e:
        return False, f"no se pudo hablar con api.telegram.org: {e}"
    if not cuerpo.get("ok"):
        return False, cuerpo.get("description", "respuesta sin ok")
    return True, cuerpo["result"]


def diagnosticar(quien, ruta, flujo, info, anterior=None):
    """La parte que se puede probar sin red: de un `getWebhookInfo` a una lista de
    problemas, cada uno con lo que hay que hacer.

    `info` es el `result` de getWebhookInfo; `anterior` el
    `pending_update_count` de la lectura previa, o None si no hay."""
    esperada = f"{BASE_N8N}/webhook/{ruta}"
    problemas = []
    url = (info or {}).get("url") or ""
    if url != esperada:
        if not url:
            problemas.append(
                f"Telegram no tiene ningún webhook para el bot del {quien}: "
                f"nadie le entrega los mensajes y el bot está mudo.\n"
                f"   Qué hacer: registrarlo otra vez (§4 del manual de "
                f"operación), con la ruta {ruta} y el mismo secret_token que "
                f"tiene la credencial de n8n.")
        else:
            problemas.append(
                f"Telegram entrega el bot del {quien} en {url}, y tendría que "
                f"ser {esperada}.\n"
                f"   Qué hacer: si esa URL es la del OTRO bot, se pegó la ruta "
                f"equivocada en el setWebhook: Telegram contesta «Webhook was "
                f"set» igualmente y el bot se queda mudo sin decir por qué. "
                f"Vuelve a registrarlo con {esperada}.")
    ultimo = (info or {}).get("last_error_message")
    if ultimo:
        fecha = (info or {}).get("last_error_date")
        pista = ""
        if "403" in str(ultimo):
            pista = (" Un 403 aquí es el caso claro: el secret_token de la "
                     "credencial de n8n y el del setWebhook no coinciden. "
                     "Regenera el secreto, ponlo en la credencial y vuelve a "
                     "llamar a setWebhook con el mismo.")
        elif "404" in str(ultimo):
            pista = (f" Un 404 aquí significa que n8n rechaza la entrega: el "
                     f"workflow «{flujo}» está desactivado, o le cambiaron la "
                     f"ruta.")
        if not pista:
            pista = (" mira el log del proxy del cliente y comprueba que el "
                     "workflow está activo.")
        problemas.append(
            f"Telegram dice que su último intento de entrega al bot del "
            f"{quien} falló: «{ultimo}» (last_error_date={fecha}).\n"
            f"   Qué hacer:{pista}")
    pendientes = (info or {}).get("pending_update_count")
    if isinstance(pendientes, int) and pendientes > 0:
        if anterior is not None and pendientes > anterior:
            problemas.append(
                f"El bot del {quien} acumula {pendientes} mensajes sin entregar "
                f"y ayer eran {anterior}: Telegram está guardando lo que no "
                f"consigue entregar.\n"
                f"   Qué hacer: es el mismo problema que las dos líneas de "
                f"arriba, pero visto desde la cola. Arregla la entrega y la "
                f"cola se vacía sola.")
        else:
            print(f"   nota: {pendientes} mensajes pendientes ahora mismo. "
                  f"Uno o dos son normales; si en la siguiente lectura son "
                  f"más, Telegram no está entregando.")
    return problemas


def _memoria_leer():
    try:
        return json.loads(MEMORIA.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _memoria_escribir(datos):
    try:
        MEMORIA.parent.mkdir(parents=True, exist_ok=True)
        MEMORIA.write_text(json.dumps(datos), encoding="utf-8")
    except OSError:
        pass


def mensaje_para_telegram(problemas, comprobado=True):
    """El mismo formato que el aviso del workflow: encabezado, y cada problema
    con su «Que hacer». Recortado al limite de Telegram, que son 4096.

    Con `comprobado` en False el encabezado dice que NO se comprobo nada: si
    no se llego a mirar ningun webhook, el aviso no puede decir que uno no
    esta como debe, o quien lea solo la notificacion ira a registrar otra
    vez un webhook que estaba bien."""
    titulo = ("el webhook de Telegram no está como debe" if comprobado
              else "los webhooks de Telegram NO se han comprobado")
    cabeza = (f"\U0001fa7a Copiloto Triaje — {titulo}\n\n(lo dice "
              "pruebas/verificar_webhooks.py, que es la mitad de la sexta "
              "comprobación del §16 que no cabe dentro de n8n)\n")
    cuerpo = "\n\n".join(f"{i}. {p}" for i, p in enumerate(problemas, 1))
    texto = f"{cabeza}\n{cuerpo}"
    if len(texto) > 3900:
        texto = (f"{texto[:3900]}\n\n[…] recortado: corre el script a mano para "
                 "verlo entero.")
    return texto


def avisar_por_telegram(token, chat_id, texto):
    """Manda el texto por Telegram. Devuelve (ok, detalle).

    Sin dependencias: la API acepta el cuerpo como formulario, y asi el texto no
    viaja en la URL -donde acabaria en cualquier log de por medio-.
    """
    datos = urllib.parse.urlencode({"chat_id": chat_id, "text": texto}).encode()
    pet = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=datos)
    try:
        with urllib.request.urlopen(pet, timeout=20) as r:
            cuerpo = json.load(r)
        return bool(cuerpo.get("ok")), ""
    except urllib.error.HTTPError as e:
        try:
            detalle = json.load(e).get("description", f"HTTP {e.code}")
        except Exception:
            detalle = f"HTTP {e.code}"
        if "chat not found" in str(detalle):
            detalle += (" — el chat_id es de otra cuenta, o nadie le ha escrito "
                        "nunca a ese bot: un bot no puede iniciar la "
                        "conversacion")
        return False, detalle
    except OSError as e:
        return False, str(e)


def avisar_al_equipo(problemas, comprobado=True):
    """El canal de la tarea programada: sin esto, lo que se imprime acaba en un
    log que nadie abre. Hacen falta las dos variables; con una sola se dice.
    `comprobado` es el de `mensaje_para_telegram`."""
    chat = os.environ.get("COPILOTO_CHAT_EQUIPO", "").strip()
    token_avisos = os.environ.get("TELEGRAM_TOKEN_AVISOS", "").strip()
    if problemas and chat and token_avisos:
        enviado, detalle = avisar_por_telegram(
            token_avisos, chat, mensaje_para_telegram(problemas, comprobado))
        print("\naviso por Telegram: "
              + ("enviado." if enviado else f"NO se pudo enviar ({detalle})."))
    elif problemas and (chat or token_avisos):
        print("\naviso por Telegram: no se manda, faltan COPILOTO_CHAT_EQUIPO o "
              "TELEGRAM_TOKEN_AVISOS (hacen falta las dos).")


def _hay_consola() -> bool:
    """Si hay una consola a la que pedirle el token. Sin ella (una entrada
    redirigida, un proceso sin consola) `getpass` se quedaria esperando un
    token que nadie va a teclear. Que la haya no quiere decir que haya alguien
    delante: la tarea programada tiene una que nadie ve, y por eso va con
    `--sin-teclado`.

    En Windows `isatty()` no basta: una entrada redirigida desde `NUL` es un
    dispositivo de caracteres y dice que si. Alli se pregunta ademas a la
    consola por su modo, que solo lo tiene una consola de verdad."""
    try:
        if sys.stdin is None or not sys.stdin.isatty():
            return False
    except (AttributeError, ValueError, OSError):
        return False
    if os.name != "nt":
        return True
    try:
        import msvcrt
        manejador = msvcrt.get_osfhandle(sys.stdin.fileno())
    except (AttributeError, ValueError, OSError):
        # una entrada sin descriptor que dice ser una consola: se le cree
        return True
    import ctypes
    modo = ctypes.c_ulong()
    return bool(ctypes.windll.kernel32.GetConsoleMode(
        ctypes.c_void_p(manejador), ctypes.byref(modo)))


def leer_opciones(argv=None):
    """Las opciones de la linea de ordenes (con `argv` None, las de
    `sys.argv`). Se leen en `main()` y nunca al importar: este modulo lo
    importan las pruebas, con las opciones de pytest en `sys.argv`. Sin
    abreviaturas: la orden de la tarea tiene que llevar la opcion entera."""
    p = argparse.ArgumentParser(
        allow_abbrev=False,
        description="Mira que Telegram siga entregando los dos bots donde debe: "
                    "la mitad del §16 que no cabe dentro de n8n.")
    p.add_argument(
        "--sin-teclado", action="store_true",
        help="no pedir nunca un token por teclado: el bot sin token en el "
             "entorno se cuenta como problema. Es como lo lanza la tarea "
             "programada (§5 del manual de operacion), que tiene una consola "
             "que nadie ve")
    return p.parse_args(argv)


def main(argv=None) -> int:
    opciones = leer_opciones(argv)
    if not BASE_N8N:
        # Antes de pedir ningun token y de tocar la memoria: sin la base no hay
        # con que comparar, y una lectura a medias borraria la de ayer. Mal
        # puesta es lo mismo: compararla daria por mal apuntados los dos
        # webhooks y mandaria registrarlos en una direccion equivocada.
        mensaje = (N8N_URL_MAL.format(motivo=N8N_URL_MAL_PUESTA)
                   if N8N_URL_MAL_PUESTA else SIN_N8N_URL)
        print(mensaje)
        avisar_al_equipo([mensaje], comprobado=False)
        return 1
    memoria = _memoria_leer()
    nueva = {}
    problemas_todos = []
    problemas_totales = 0
    for quien, variable, ruta, flujo in BOTS:
        token = os.environ.get(variable)
        if not token and not opciones.sin_teclado and _hay_consola():
            token = getpass.getpass(
                f"token del bot del {quien} (de BotFather, no se muestra): ").strip()
        if not token:
            print(f"{quien}: sin token, no se puede comprobar. SALTADO")
            problemas_todos.append(
                f"El bot del {quien} no se pudo comprobar: falta su token en "
                f"{variable}.")
            problemas_totales += 1
            continue
        print(f"\n== bot del {quien} ==")
        ok, info = pedir_api(token, "getWebhookInfo")
        if not ok:
            print(f"   PROBLEMA: {info}")
            problemas_todos.append(f"Bot del {quien}: {info}")
            problemas_totales += 1
            continue
        problemas = diagnosticar(quien, ruta, flujo, info,
                                 memoria.get(quien))
        nueva[quien] = info.get("pending_update_count", 0)
        if problemas:
            for i, p in enumerate(problemas, 1):
                print(f"   PROBLEMA {i}: {p}")
            problemas_todos.extend(problemas)
            problemas_totales += len(problemas)
        else:
            print(f"   bien: Telegram entrega en {info['url']}, sin errores.")
    _memoria_escribir(nueva)
    avisar_al_equipo(problemas_todos)

    if problemas_totales:
        print(f"\n{problemas_totales} cosas que arreglar.")
        return 1
    print("\nLos dos webhooks están como deben.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
