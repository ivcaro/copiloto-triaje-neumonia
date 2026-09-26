# -*- coding: utf-8 -*-
"""El flujo del profesional: la presentacion del §8, las once ramas del §9 y la
concurrencia.

El fichero tiene DOS mitades, y por la misma razon que `test_flujo_paciente.py`:

- `TestConducido` habla con un n8n vivo, con `copiloto-bd`, con Telegram y con el
  copiloto. Se salta si falta el entorno (`N8N_URL`, `COPILOTO_BD_DSN`,
  `TELEGRAM_SECRET_PRUEBA`, `TELEGRAM_TOKEN_PROFESIONAL`).
- Las pruebas de MODULO leen el JSON exportado y no necesitan NADA: ni red, ni
  base, ni secretos. Ahi viven las garantias que no pueden depender de que
  alguien tenga el tunel montado -un skip se ve verde-: los tres bloques del §8,
  el aviso de la banda contradictoria, y que ninguna rama de error emita una
  cifra de probabilidad. Estan FUERA de la clase a proposito.

La prueba de dos conversaciones solapadas es la mas importante de la mitad
conducida: sin `sesiones_profesional`, los signos de un paciente acabarian junto
a la placa de otro, y el mensaje saldria sintacticamente perfecto.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

SECRETO = os.environ.get("TELEGRAM_SECRET_PRUEBA")
RUTA = os.environ.get("WEBHOOK_PROFESIONAL", "copiloto-profesional")
# El token del bot del PROFESIONAL, no el del bot de pruebas. Ver
# `_subir_dicom`: un `file_id` de Telegram solo vale para el bot que lo obtuvo.
TOKEN = os.environ.get("TELEGRAM_TOKEN_PROFESIONAL")
AUTORIZADO = 999000010
OTRO = 999000011
INTRUSO = 999000099

# El chat REAL donde se SUBEN las placas, que no es el mismo que viaja en los
# updates fabricados. La distincion no es un detalle de estilo, y estas tres
# pruebas no podian pasar sin ella:
#
#   - `AUTORIZADO` es un chat_id inventado, y eso es correcto: un chat de verdad
#     en los updates llenaria la conversacion de alguien con informes de prueba.
#   - Pero para que el flujo pueda BAJAR una placa hace falta un `file_id`, y un
#     `file_id` solo existe si alguien SUBIO el fichero. Y un bot de Telegram no
#     puede escribir a un chat que no existe ni a uno que no le haya escrito
#     antes: `sendDocument` contesta `400 chat not found`, y `urlopen` lanza
#     HTTPError ANTES del `assert respuesta.get("ok")`, asi que las tres pruebas
#     que suben una placa daban ERROR, no fallo de asercion.
#   - Lo que lo arregla es que un `file_id` es del BOT y no de un chat: se puede
#     subir a un chat real y luego afirmar en el update que viene de otro.
#
# Sin la variable, esas tres se SALTAN con este motivo escrito, que es mas honesto
# que verlas reventar por algo que no es lo que prueban.
SUBIDA = os.environ.get("CHAT_SUBIDA_PLACAS")

FLUJO = (pathlib.Path(__file__).resolve().parents[1] / "n8n"
         / "copiloto-profesional.json")
FLUJO_PACIENTE = (pathlib.Path(__file__).resolve().parents[1] / "n8n"
                  / "copiloto-paciente.json")

# El §4.4 del spec, copiado AQUI a mano. Testigo independiente del workflow: si
# el workflow cambia una clave o un rango, las pruebas de modulo lo ven. Por eso
# no se importa de ningun sitio.
SPEC_4_4 = {
    2: ("temperatura_c", 30.0, 45.0),
    3: ("frecuencia_cardiaca", 20, 250),
    4: ("crepitantes", None, None),
    5: ("murmullo_disminuido", None, None),
}

# La tabla del §9: situacion -> codigo, y si la conversacion TERMINA despues.
SPEC_9 = {
    "envio_como_foto": False,
    "dicom_invalido": False,
    "fuera_de_alcance": True,
    "edad_desconocida": True,
    "base64_invalido": False,
    "payload_excesivo": False,
    "payload_excesivo_transporte": False,
    "codigo_invalido": False,
    "fichero_no_descargable": False,
    "copiloto_no_responde": False,
    "error_no_reconocido": True,
}

# Codigos que NO estan en el §9 y que el flujo necesita. Se listan aparte para que
# se vea que son un anadido, no un descuido de lectura del spec:
#
#   no_autorizado    el rechazo de D6. El §5.1 guarda tambien los rechazos y la
#                    tasa es la senal del §16, asi que necesita codigo.
#   descarga_fallida Telegram acepta el update y luego falla al entregar el
#                    fichero. Antes reusaba `fichero_no_descargable`, cuyo mensaje
#                    acusa de haber mandado mas de 20 MB: para un DICOM de 131 KB
#                    es una frase falsa, y una frase falsa manda al clinico a
#                    buscar por donde no es.
#
# `no_autorizado` lleva termina=False aunque la tabla del §9 diga «termina»: en
# esta columna `termina` significa BORRAR LA SESION, y a un profesional al que dan
# de baja a mitad de conversacion se le perderian los signos ya recogidos. El §7
# dice que deja de pasar en el mensaje siguiente, no que se le tire el estado.
ANADIDOS_AL_9 = {"no_autorizado": False, "descarga_fallida": False}

SINTOMAS_PRUEBA = {"fiebre": "si", "tos": "con_flema", "dias_evolucion": "3_a_7",
                   "disnea": "no", "dolor_toracico": "si", "asma": "no_se",
                   "texto_libre": None}

# Las TRES pruebas que suben una placa. Las otras cinco de la clase no suben nada
# y no dependen de esto.
necesita_subida = pytest.mark.skipif(
    not SUBIDA,
    reason="sin CHAT_SUBIDA_PLACAS no hay chat real donde subir la placa, y sin "
           "subirla no hay `file_id` que el flujo pueda bajar. Ponla al chat que "
           "le escribio /start al bot del profesional")


def _mensaje(texto, chat):
    return {"update_id": 1, "message": {
        "message_id": 1, "date": 0, "chat": {"id": chat, "type": "private"},
        "from": {"id": chat, "is_bot": False, "first_name": "Dr"},
        "text": texto}}


def _boton(dato, chat):
    return {"update_id": 2, "callback_query": {
        "id": "1", "from": {"id": chat, "is_bot": False, "first_name": "Dr"},
        "message": {"message_id": 1, "date": 0,
                    "chat": {"id": chat, "type": "private"}},
        "data": dato}}


def _documento(file_id, chat, file_size=131072):
    return {"update_id": 3, "message": {
        "message_id": 1, "date": 0, "chat": {"id": chat, "type": "private"},
        "from": {"id": chat, "is_bot": False, "first_name": "Dr"},
        "document": {"file_id": file_id, "file_name": "a.dcm",
                     "file_size": file_size,
                     "mime_type": "application/octet-stream"}}}


def _foto(chat):
    return {"update_id": 4, "message": {
        "message_id": 1, "date": 0, "chat": {"id": chat, "type": "private"},
        "from": {"id": chat, "is_bot": False, "first_name": "Dr"},
        "photo": [{"file_id": "fake", "width": 100, "height": 100,
                   "file_size": 1000}]}}


# --------------------------------------------------------------------------
# Ayudantes de la mitad conducida
# --------------------------------------------------------------------------
def _subir_dicom(ruta, chat=None):
    """Sube el DICOM con el bot del PROFESIONAL y devuelve su `file_id`.

    Con el bot del profesional y no con `[retirado]`, aunque el brief diga
    otra cosa: en Telegram un `file_id` solo lo puede resolver **el bot que lo
    obtuvo**. Un `file_id` conseguido subiendo el fichero al bot de pruebas haria
    que el `getFile` del flujo -que usa la credencial de `[retirado]`-
    respondiera `wrong file identifier`, y la prueba estaria midiendo eso y no el
    flujo.

    Y a `CHAT_SUBIDA_PLACAS`, que tiene que ser un chat REAL y no el `AUTORIZADO`
    inventado de los updates. El motivo entero esta donde se define `SUBIDA`.
    """
    chat = chat or SUBIDA
    limite = "----" + uuid.uuid4().hex
    datos = pathlib.Path(ruta).read_bytes()
    cuerpo = b""
    for nombre, valor in (("chat_id", str(chat)),):
        cuerpo += (f"--{limite}\r\nContent-Disposition: form-data; "
                   f'name="{nombre}"\r\n\r\n{valor}\r\n').encode()
    cuerpo += (f"--{limite}\r\nContent-Disposition: form-data; "
               f'name="document"; filename="{pathlib.Path(ruta).name}"\r\n'
               "Content-Type: application/octet-stream\r\n\r\n").encode()
    cuerpo += datos + f"\r\n--{limite}--\r\n".encode()
    pet = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendDocument", data=cuerpo,
        headers={"Content-Type": f"multipart/form-data; boundary={limite}"})
    with urllib.request.urlopen(pet, timeout=120) as r:
        respuesta = json.loads(r.read().decode())
    assert respuesta.get("ok"), respuesta
    return respuesta["result"]["document"]["file_id"]


def _esperar(bd, consulta, parametros, esperado, intentos=24):
    """Espera a que la base diga lo que se espera. Devuelve el ultimo valor."""
    visto = None
    for _ in range(intentos):
        fila = bd.execute(consulta, parametros).fetchone()
        visto = fila[0] if fila else None
        if visto == esperado:
            return visto
        time.sleep(0.5)
    return visto


def _esperar_paso(bd, chat, paso):
    return _esperar(bd, "SELECT paso FROM sesiones_profesional WHERE chat_id = %s",
                    (chat,), paso)


def _crear_cuestionario(bd, sintomas=None):
    """Nace un cuestionario vivo y se devuelve su codigo."""
    return bd.execute(
        "INSERT INTO cuestionarios (codigo, respuestas, consentido_en, expira_en)"
        " VALUES (generar_codigo(), %s, now(), now() + interval '7 days')"
        " RETURNING codigo",
        (json.dumps(sintomas or SINTOMAS_PRUEBA),)).fetchone()[0]


def _llevar_hasta_la_placa(webhook_n8n, bd, chat=AUTORIZADO, sintomas=None):
    """Conduce la conversacion hasta el paso que espera la radiografia."""
    codigo = _crear_cuestionario(bd, sintomas)
    webhook_n8n(RUTA, _mensaje("/reiniciar", chat), SECRETO)
    assert _esperar_paso(bd, chat, 1) == 1, "el bot no pidio el codigo"
    webhook_n8n(RUTA, _mensaje(codigo, chat), SECRETO)
    assert _esperar_paso(bd, chat, 2) == 2, "el codigo no se acepto"
    for texto, siguiente in (("38,2", 3), ("104", 4)):
        webhook_n8n(RUTA, _mensaje(texto, chat), SECRETO)
        assert _esperar_paso(bd, chat, siguiente) == siguiente, texto
    for dato, siguiente in (("s4:si", 5), ("s5:no", 6)):
        webhook_n8n(RUTA, _boton(dato, chat), SECRETO)
        assert _esperar_paso(bd, chat, siguiente) == siguiente, dato
    return codigo


def _consulta_completa(webhook_n8n, bd, caso, chat=AUTORIZADO, sintomas=None):
    """La conversacion entera, con una radiografia REAL de RSNA."""
    antes = bd.execute("SELECT COALESCE(max(id), 0) FROM consultas").fetchone()[0]
    codigo = _llevar_hasta_la_placa(webhook_n8n, bd, chat, sintomas)
    # La placa se sube al chat REAL de `SUBIDA`; el update dice que viene de
    # `chat`, que es inventado. Se puede porque un `file_id` es del bot.
    file_id = _subir_dicom(caso["ruta_dcm"])
    webhook_n8n(RUTA, _documento(file_id, chat), SECRETO)
    nueva = _esperar(bd, "SELECT count(*) FROM consultas WHERE id > %s",
                     (antes,), 1, intentos=60)
    assert nueva == 1, "el flujo no escribio la fila de `consultas`"
    return codigo


# --------------------------------------------------------------------------
# Conducidas: n8n vivo + copiloto-bd + Telegram + copiloto. Se saltan sin entorno.
# --------------------------------------------------------------------------
@pytest.mark.skipif(
    not (SECRETO and TOKEN),
    reason="sin TELEGRAM_SECRET_PRUEBA no se pasa la puerta del §4.2, y sin "
           "TELEGRAM_TOKEN_PROFESIONAL no hay file_id que el flujo pueda bajar")
class TestConducido:

    @pytest.fixture(autouse=True)
    def entorno(self, bd_sp3):
        bd_sp3.execute(
            "INSERT INTO profesionales (chat_id, nombre) VALUES (%s, 'Dr Prueba')"
            " ON CONFLICT (chat_id) DO UPDATE SET activo = true", (AUTORIZADO,))
        bd_sp3.execute("DELETE FROM profesionales WHERE chat_id = %s", (INTRUSO,))
        bd_sp3.execute("DELETE FROM sesiones_profesional WHERE chat_id IN %s",
                       ((AUTORIZADO, OTRO, INTRUSO),))
        yield
        bd_sp3.execute("DELETE FROM sesiones_profesional WHERE chat_id IN %s",
                       ((AUTORIZADO, OTRO, INTRUSO),))
        bd_sp3.execute(
            "UPDATE profesionales SET activo = true WHERE chat_id = %s",
            (AUTORIZADO,))

    def test_un_chat_no_autorizado_no_llega_al_copiloto(self, webhook_n8n, bd_sp3):
        antes = bd_sp3.execute("SELECT count(*) FROM consultas WHERE resultado"
                               " IS NOT NULL").fetchone()[0]
        webhook_n8n(RUTA, _mensaje("/start", INTRUSO), SECRETO)
        assert _esperar(
            bd_sp3, "SELECT count(*) FROM consultas WHERE chat_id = %s AND error"
                    " = 'no_autorizado'", (INTRUSO,), 1) >= 1
        assert bd_sp3.execute("SELECT count(*) FROM consultas WHERE resultado"
                              " IS NOT NULL").fetchone()[0] == antes
        assert bd_sp3.execute(
            "SELECT count(*) FROM sesiones_profesional WHERE chat_id = %s",
            (INTRUSO,)).fetchone()[0] == 0, "a un intruso no se le abre sesion"

    def test_dar_de_baja_corta_en_el_mensaje_siguiente(self, webhook_n8n, bd_sp3):
        """La comprobacion es por MENSAJE, no un paso del flujo.

        El brief mandaba un codigo inventado (`ABC234`). Eso NO mide la baja: un
        codigo inexistente deja `sesiones_profesional.codigo` en NULL tambien
        para un profesional perfectamente activo, asi que la prueba pasaria
        aunque la puerta del §7 no existiera. Aqui se manda un codigo que SI
        existe, de modo que la unica razon por la que no queda atado a la sesion
        es la baja.
        """
        codigo = _crear_cuestionario(bd_sp3)
        webhook_n8n(RUTA, _mensaje("/start", AUTORIZADO), SECRETO)
        assert _esperar_paso(bd_sp3, AUTORIZADO, 1) == 1
        bd_sp3.execute("UPDATE profesionales SET activo = false WHERE chat_id = %s",
                       (AUTORIZADO,))
        webhook_n8n(RUTA, _mensaje(codigo, AUTORIZADO), SECRETO)
        assert _esperar(
            bd_sp3, "SELECT count(*) FROM consultas WHERE chat_id = %s AND error"
                    " = 'no_autorizado'", (AUTORIZADO,), 1) >= 1
        assert bd_sp3.execute(
            "SELECT codigo FROM sesiones_profesional WHERE chat_id = %s",
            (AUTORIZADO,)).fetchone()[0] is None
        assert bd_sp3.execute(
            "SELECT paso FROM sesiones_profesional WHERE chat_id = %s",
            (AUTORIZADO,)).fetchone()[0] == 1, "la sesion tampoco avanza"

    def test_una_foto_no_avanza_de_paso_y_lo_explica(self, webhook_n8n, bd_sp3):
        """Telegram recomprime las fotos y destruye el DICOM. La conversacion se
        queda esperando el archivo (§9)."""
        _llevar_hasta_la_placa(webhook_n8n, bd_sp3)
        paso = bd_sp3.execute(
            "SELECT paso FROM sesiones_profesional WHERE chat_id = %s",
            (AUTORIZADO,)).fetchone()[0]
        webhook_n8n(RUTA, _foto(AUTORIZADO), SECRETO)
        assert _esperar(
            bd_sp3, "SELECT error FROM consultas WHERE chat_id = %s ORDER BY id"
                    " DESC LIMIT 1", (AUTORIZADO,), "envio_como_foto"
        ) == "envio_como_foto"
        assert bd_sp3.execute(
            "SELECT paso FROM sesiones_profesional WHERE chat_id = %s",
            (AUTORIZADO,)).fetchone()[0] == paso
        assert bd_sp3.execute(
            "SELECT resultado FROM consultas WHERE chat_id = %s ORDER BY id DESC"
            " LIMIT 1", (AUTORIZADO,)).fetchone()[0] is None

    @necesita_subida
    def test_un_menor_de_edad_se_rechaza_sin_ninguna_cifra(self, webhook_n8n,
                                                           bd_sp3):
        """Criterio 7. Se usa una placa de un nino REAL, de los 1 276 de RSNA."""
        from pruebas.seleccionar_casos import seleccionar
        caso = seleccionar(n_por_perfil=1)["menor_edad"][0]
        assert caso["edad"] < 18, caso
        _consulta_completa(webhook_n8n, bd_sp3, caso)
        fila = bd_sp3.execute(
            "SELECT error, resultado FROM consultas WHERE chat_id = %s ORDER BY"
            " id DESC LIMIT 1", (AUTORIZADO,)).fetchone()
        assert fila[0] == "fuera_de_alcance"
        assert fila[1] is None, "un rechazo no puede traer resultado"
        assert bd_sp3.execute(
            "SELECT count(*) FROM sesiones_profesional WHERE chat_id = %s",
            (AUTORIZADO,)).fetchone()[0] == 0, "§9: el rechazo por edad TERMINA"

    @necesita_subida
    def test_la_banda_contradictoria_lleva_su_aviso(self, webhook_n8n, bd_sp3):
        """Criterio 6. Pasa una de cada cuatro veces que hay un positivo (§3)."""
        from pruebas.seleccionar_casos import seleccionar
        caso = seleccionar(n_por_perfil=1)["banda_contradictoria"][0]
        _consulta_completa(webhook_n8n, bd_sp3, caso)
        res = bd_sp3.execute(
            "SELECT resultado FROM consultas WHERE chat_id = %s ORDER BY id DESC"
            " LIMIT 1", (AUTORIZADO,)).fetchone()[0]
        assert res["clasificacion"] == "opacidad_probable"
        assert res["razon_de_verosimilitud"] < 1.0
        # El aviso vive en el nodo `Desenlace`, y que se dispare con ESTOS
        # numeros lo comprueba `tests/profesional.mjs` ejecutando su codigo. Aqui
        # se confirma que la placa real cae de verdad en la banda.
        assert res["probabilidad_cruda"] >= res["umbral"]

    def test_dos_profesionales_a_la_vez_no_cruzan_sus_signos(self, webhook_n8n,
                                                            bd_sp3):
        """LA prueba de esta tarea. Sin sesiones_profesional, los signos de un
        paciente acaban junto a la placa de otro y el mensaje sale perfecto.

        El brief mandaba las dos temperaturas justo despues de sendos `/start`.
        Eso no puede pasar: tras `/start` la conversacion esta pidiendo el CODIGO
        del paciente, asi que un «38.2» se interpreta como un codigo mal formado,
        los dos `signos` se quedan en `{}` y `a != b` falla por vacios, no por
        cruce. Aqui se lleva a los dos hasta el paso de la temperatura -cada uno
        con SU codigo de paciente- y se intercalan los mensajes de verdad.
        """
        bd_sp3.execute(
            "INSERT INTO profesionales (chat_id, nombre) VALUES (%s, 'Dra Dos')"
            " ON CONFLICT (chat_id) DO UPDATE SET activo = true", (OTRO,))
        try:
            codigos = {}
            for chat in (AUTORIZADO, OTRO):
                codigos[chat] = _crear_cuestionario(bd_sp3)
                webhook_n8n(RUTA, _mensaje("/reiniciar", chat), SECRETO)
            for chat in (AUTORIZADO, OTRO):
                assert _esperar_paso(bd_sp3, chat, 1) == 1
                webhook_n8n(RUTA, _mensaje(codigos[chat], chat), SECRETO)
            for chat in (AUTORIZADO, OTRO):
                assert _esperar_paso(bd_sp3, chat, 2) == 2
            # Intercalados, que es como llegarian dos conversaciones a la vez.
            for chat, temp in ((AUTORIZADO, "38,2"), (OTRO, "36,4")):
                webhook_n8n(RUTA, _mensaje(temp, chat), SECRETO)
            for chat in (AUTORIZADO, OTRO):
                assert _esperar_paso(bd_sp3, chat, 3) == 3
            for chat, fc in ((OTRO, "72"), (AUTORIZADO, "104")):
                webhook_n8n(RUTA, _mensaje(fc, chat), SECRETO)
            for chat in (AUTORIZADO, OTRO):
                assert _esperar_paso(bd_sp3, chat, 4) == 4

            def estado(chat):
                return bd_sp3.execute(
                    "SELECT signos, codigo FROM sesiones_profesional WHERE"
                    " chat_id = %s", (chat,)).fetchone()

            a, b = estado(AUTORIZADO), estado(OTRO)
            assert a[0] != b[0], "los dos profesionales comparten estado"
            assert a[0] == {"temperatura_c": 38.2, "frecuencia_cardiaca": 104}, a
            assert b[0] == {"temperatura_c": 36.4, "frecuencia_cardiaca": 72}, b
            assert a[1] == codigos[AUTORIZADO] and b[1] == codigos[OTRO], \
                "cada conversacion con SU codigo de paciente"
        finally:
            bd_sp3.execute("DELETE FROM sesiones_profesional WHERE chat_id = %s",
                           (OTRO,))
            bd_sp3.execute("DELETE FROM profesionales WHERE chat_id = %s", (OTRO,))

    @necesita_subida
    def test_los_sintomas_se_copian_a_consultas(self, webhook_n8n, bd_sp3):
        """D12: sin la copia, H7 se queda sin nada que validar porque
        `cuestionarios` se borra a los 7 dias."""
        from pruebas.seleccionar_casos import seleccionar
        caso = seleccionar(n_por_perfil=1)["positiva_clara"][0]
        codigo = _consulta_completa(webhook_n8n, bd_sp3, caso)
        fila = bd_sp3.execute(
            "SELECT codigo, sintomas, signos FROM consultas WHERE chat_id = %s"
            " ORDER BY id DESC LIMIT 1", (AUTORIZADO,)).fetchone()
        assert fila[0] == codigo
        assert fila[1] and "fiebre" in fila[1]
        assert fila[1] == SINTOMAS_PRUEBA, fila[1]
        assert fila[2] == {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
                           "crepitantes": True, "murmullo_disminuido": False}, \
            fila[2]

    def test_fuera_de_rango_no_avanza_de_paso(self, webhook_n8n, bd_sp3):
        """§4.4: fuera de rango el bot lo dice, NO avanza y vuelve a preguntar.
        Y no deja fila en `consultas`: una errata no es un rechazo clinico."""
        _crear_cuestionario(bd_sp3)
        codigo = _crear_cuestionario(bd_sp3)
        webhook_n8n(RUTA, _mensaje("/reiniciar", AUTORIZADO), SECRETO)
        assert _esperar_paso(bd_sp3, AUTORIZADO, 1) == 1
        webhook_n8n(RUTA, _mensaje(codigo, AUTORIZADO), SECRETO)
        assert _esperar_paso(bd_sp3, AUTORIZADO, 2) == 2
        antes = bd_sp3.execute("SELECT count(*) FROM consultas").fetchone()[0]
        for malo in ("51", "12,5", "manzana"):
            webhook_n8n(RUTA, _mensaje(malo, AUTORIZADO), SECRETO)
            time.sleep(2)
            assert bd_sp3.execute(
                "SELECT paso, signos FROM sesiones_profesional WHERE chat_id = %s",
                (AUTORIZADO,)).fetchone() == (2, {}), malo
        assert bd_sp3.execute("SELECT count(*) FROM consultas").fetchone()[0] \
            == antes, "una errata no escribe en consultas"


# --------------------------------------------------------------------------
# De modulo: solo leen el JSON exportado. No se saltan nunca.
# --------------------------------------------------------------------------
def _flujo(ruta=None):
    """El JSON exportado. Si no existe, la prueba FALLA -no se salta-: su
    ausencia es exactamente lo que estas pruebas existen para detectar."""
    ruta = ruta or FLUJO
    assert ruta.exists(), f"falta el workflow exportado: {ruta}"
    return json.loads(ruta.read_text(encoding="utf-8"))


def _nodo(flujo, nombre):
    for n in flujo["nodes"]:
        if n["name"] == nombre:
            return n
    raise AssertionError(f"el workflow no tiene un nodo '{nombre}'")


def test_el_webhook_rechaza_por_cabecera_antes_de_ejecutar_nada():
    """§4.2, y aqui importa mas que en el flujo del paciente: el `chat_id` ES la
    lista blanca (D6), y lo aporta quien llama. Sin esta puerta, forjar un update
    con un chat_id autorizado basta para usar el modelo."""
    p = _nodo(_flujo(), "Webhook Telegram (profesional)")["parameters"]
    assert p["authentication"] == "headerAuth"
    assert p["httpMethod"] == "POST"
    assert p["path"] == "copiloto-profesional"


def test_solo_se_usa_la_credencial_del_bot_del_profesional():
    """D9 y la regla dura 2: reutilizar una credencial de Telegram del cliente le
    robaria el webhook a un bot suyo y lo dejaria mudo sin error visible.
    `[retirado]` la usan cinco workflows del cliente."""
    usadas = {c["id"]
              for n in _flujo()["nodes"]
              for t, c in (n.get("credentials") or {}).items()
              if t == "telegramApi"}
    assert usadas == {"[retirado]"}, usadas            # [retirado]
    paciente = {c["id"]
                for n in _flujo(FLUJO_PACIENTE)["nodes"]
                for t, c in (n.get("credentials") or {}).items()
                if t == "telegramApi"}
    assert not (usadas & paciente), \
        "los dos bots no pueden compartir credencial: un token, un webhook"


def test_ningun_secreto_viaja_en_el_JSON_exportado():
    """§12: ninguno va al repositorio. Las credenciales se referencian por id y
    nombre; sus valores se quedan en n8n."""
    flujo = _flujo()
    for nodo in flujo["nodes"]:
        for tipo, cred in (nodo.get("credentials") or {}).items():
            assert set(cred) <= {"id", "name"}, (nodo["name"], tipo, cred)
    texto = json.dumps(flujo)
    assert not re.search(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b", texto), \
        "algo con la forma de un token de bot de Telegram"
    for sospechoso in ("accessToken", "\"password\"", "api.telegram.org/bot1",
                       "Bearer "):
        assert sospechoso not in texto, sospechoso


def test_el_workflow_no_guarda_los_datos_de_ejecucion():
    """§5.4: n8n guarda las entradas y salidas de cada nodo en la base de n8n,
    que es DEL CLIENTE. Ahi iria el DICOM, su base64 y el cuestionario."""
    ajustes = _flujo().get("settings", {})
    assert ajustes.get("saveDataSuccessExecution") == "none"
    assert ajustes.get("saveDataErrorExecution") == "none"
    assert ajustes.get("saveManualExecutions") is False
    assert ajustes.get("saveExecutionProgress") is False


def test_el_tiempo_de_ejecucion_cabe_la_llamada_al_copiloto_con_su_reintento():
    """30 s de timeout y un reintento (§10.1), mas la descarga del DICOM. Con los
    60 s del flujo del paciente, un copiloto lento mataria el workflow por
    timeout en vez de contestar `copiloto_no_responde`."""
    flujo = _flujo()
    http = _nodo(flujo, "Llamar al copiloto")
    espera = http["parameters"]["options"]["timeout"] * http["maxTries"]
    assert flujo["settings"]["executionTimeout"] * 1000 > espera, \
        (flujo["settings"]["executionTimeout"], espera)


def test_la_llamada_al_copiloto_es_la_del_spec():
    """§10.1, verificado contra el contenedor: Response Format Text (la respuesta
    es SSE), timeout 30 000 ms, y UN solo reintento."""
    n = _nodo(_flujo(), "Llamar al copiloto")
    p = n["parameters"]
    assert p["method"] == "POST"
    assert p["url"] == "http://copiloto-mcp:8000/mcp"
    respuesta = p["options"]["response"]["response"]
    assert respuesta["responseFormat"] == "text", "un parseo a JSON fallaria: es SSE"
    assert p["options"]["timeout"] == 30000
    assert n["retryOnFail"] is True and n["maxTries"] == 2, "UN reintento"
    # Sin estos dos, un HTTP 413 -el limite del TRANSPORTE del §10.4- seria un
    # fallo de nodo en vez de una rama del §9.
    assert respuesta["neverError"] is True
    assert respuesta["fullResponse"] is True
    # Y la salida de error del nodo tiene que ir a algun sitio, o un timeout
    # dejaria al profesional sin respuesta.
    assert n["onError"] == "continueErrorOutput"
    salidas = _flujo()["connections"]["Llamar al copiloto"]["main"]
    assert len(salidas) == 2, salidas
    assert [c["node"] for c in salidas[1]] == ["Leer respuesta"], salidas[1]
    cabeceras = {c["name"]: c["value"]
                 for c in p["headerParameters"]["parameters"]}
    assert "text/event-stream" in cabeceras["Accept"], cabeceras
    # El cuerpo JSON-RPC se serializa en `A base64`, no en esta expresion.
    # Medido contra el n8n real: una expresion con un objeto literal dentro falla
    # con «invalid syntax» -las llaves anidadas dejan `}}}` y el separador de
    # expresiones corta donde no debe-, la peticion no sale, y TODAS las
    # radiografias habrian contestado `copiloto_no_responde`.
    assert p["jsonBody"] == "={{ $json.cuerpo_jsonrpc }}", p["jsonBody"]
    assert "cuerpo_jsonrpc" in _nodo(_flujo(), "A base64")["parameters"]["jsCode"]
    # Y el campo del que `Leer respuesta` saca el texto es el que el nodo escribe.
    assert respuesta["outputPropertyName"] == "cuerpo", respuesta
    assert "e.cuerpo" in _nodo(_flujo(), "Leer respuesta")["parameters"]["jsCode"]


def test_ningun_fallo_deja_al_profesional_sin_respuesta():
    """Los dos nodos que pueden reventar en la rama de la radiografia tienen una
    salida de error que acaba en un mensaje.

    Sin esto, un 5xx de Telegram al bajar el fichero mataba el workflow en ese
    nodo, el profesional no recibia NADA, y como el §5.4 obliga a
    `saveDataErrorExecution: none` tampoco quedaba rastro de la ejecucion. En una
    herramienta clinica el silencio es el peor desenlace: el §9 existe para que
    toda situacion acabe en un mensaje y en un estado conocido.
    """
    flujo = _flujo()
    for nombre, destino in (("Descargar fichero", "Descarga fallida"),
                            ("Llamar al copiloto", "Leer respuesta")):
        nodo = _nodo(flujo, nombre)
        assert nodo.get("onError") == "continueErrorOutput", nombre
        salidas = flujo["connections"][nombre]["main"]
        assert len(salidas) == 2, (nombre, salidas)
        assert [c["node"] for c in salidas[1]] == [destino], (nombre, salidas[1])
    # Y las dos ramas de error llegan al mismo redactor, que es quien sabe el §9.
    for origen in ("Descarga fallida", "Leer respuesta", "Buscar cuestionario"):
        assert [c["node"] for c in flujo["connections"][origen]["main"][0]] \
            == ["Desenlace"], origen


def test_el_codigo_del_error_se_busca_dentro_del_texto():
    """§10.3: el SDK antepone su propio prefijo, asi que el codigo queda de
    SEGUNDO. Partir por el primer ':' devuelve
    'Error executing tool clasificar_radiografia' para todos por igual."""
    fuente = _nodo(_flujo(), "Leer respuesta")["parameters"]["jsCode"]
    assert "indexOf" in fuente, "el codigo se BUSCA dentro del texto"
    assert ".split(':')" not in fuente.replace(" ", "")
    for codigo in ("base64_invalido", "dicom_invalido", "edad_desconocida",
                   "fuera_de_alcance", "payload_excesivo"):
        assert codigo in fuente, codigo


def test_las_once_ramas_del_error_estan_y_dicen_si_la_conversacion_termina():
    """§9. La tabla vive en un solo nodo; si faltara una rama, ese codigo
    llegaria al profesional como 'no se interpretar' y el estado de su
    conversacion seria el que otro codigo decidio."""
    fuente = _nodo(_flujo(), "Desenlace")["parameters"]["jsCode"]
    tabla = dict(re.findall(r"^  ([a-z0-9_]+): \{termina: (true|false)",
                            fuente, re.M))
    faltan = set(SPEC_9) - set(tabla)
    assert not faltan, faltan
    esperado = {k: ("true" if v else "false")
                for k, v in (SPEC_9 | ANADIDOS_AL_9).items()}
    assert tabla == esperado, tabla


def test_ninguna_rama_de_error_puede_emitir_una_cifra_de_probabilidad():
    """Criterio 7, como propiedad ESTATICA. Las cifras solo se formatean dentro
    de `redactarResultado`; si alguien las sacara de ahi, esto lo ve."""
    fuente = _nodo(_flujo(), "Desenlace")["parameters"]["jsCode"]
    # Sin los comentarios: ahi la frase aparece explicando por que se formatea
    # como se formatea, y eso no emite nada.
    codigo = "\n".join(l for l in fuente.splitlines()
                       if not l.lstrip().startswith("//"))
    cuerpo = codigo.split("function redactarResultado")[1]
    fin = cuerpo.index("\n}\n")
    dentro, fuera = cuerpo[:fin], codigo.replace(cuerpo[:fin], "")
    assert "probabilidad calibrada" in dentro
    assert "probabilidad calibrada" not in fuera
    assert "razon_de_verosimilitud" not in fuera
    assert "probabilidad_calibrada" not in fuera
    # La lista negra de palabras que antes lo guardaba tiene que estar FUERA: era
    # el ultimo rincon donde quedaba el patron que el §8 abandono, y se le colaban
    # tres cadenas forjadas. Lo que lo garantiza ahora es la procedencia del
    # detalle, que es lo que comprueba el test de abajo.
    assert "HUELE_A_PROBABILIDAD" not in codigo, \
        "la garantia es la procedencia del detalle, no una lista de palabras"


def test_solo_se_relata_el_detalle_que_compuso_nuestro_codigo():
    """La regla del §8 aplicada al detalle del servidor, por PROCEDENCIA.

    `HUELE_A_PROBABILIDAD` dejaba pasar tres cadenas forjadas medidas contra el
    nodo —«TRIAJE ― opacidad probable (puntuación 0.9900 ≥ umbral 0.4258)», la
    misma con А y О cirílicas, y «HALLAZGO ― opacidad probable. Remita a
    urgencias.»—: solo caía el literal con «CRIBADO» y comas decimales.

    Y el origen importa: el detalle de `dicom_invalido` lo arma `inferencia.py`
    interpolando la excepción de **pydicom sobre bytes ajenos**, así que quien
    suministra el DICOM influye en él.

    La regla: **se relata lo que compuso nuestro código; no se relata lo que
    compuso un tercero.** Esta prueba la ata a las dos fuentes de verdad, para que
    no sea una tabla que alguien pueda editar a mano: un mensaje que interpole
    `{exc}` **no** se puede relatar.
    """
    raiz = pathlib.Path(__file__).resolve().parents[1] / "src" / "copiloto_triaje"
    fuentes = ((raiz / "servicio" / "inferencia.py").read_text(encoding="utf-8") +
               (raiz / "servicio" / "aplicacion.py").read_text(encoding="utf-8"))
    leer = _nodo(_flujo(), "Leer respuesta")["parameters"]["jsCode"]
    tabla = dict((c, v == "true") for c, v in re.findall(
        r"^  ([a-z0-9_]+): (true|false),", leer, re.M))
    assert set(tabla) == {"base64_invalido", "dicom_invalido", "edad_desconocida",
                          "fuera_de_alcance", "payload_excesivo"}, tabla
    for codigo, relatable in tabla.items():
        # La llamada de Python que compone el mensaje de ese codigo, delimitada por
        # sus propios parentesis: un trozo de N caracteres arrastraria el `{exc}`
        # de la llamada de al lado y daria un falso positivo. Paso.
        i = fuentes.index('"%s' % codigo)
        abre = fuentes.rindex("(", 0, i)
        profundidad, j = 0, abre
        while j < len(fuentes):
            if fuentes[j] == "(":
                profundidad += 1
            elif fuentes[j] == ")":
                profundidad -= 1
                if profundidad == 0:
                    break
            j += 1
        llamada = fuentes[abre:j + 1]
        assert codigo in llamada, (codigo, llamada[:120])
        interpola_terceros = "{exc}" in llamada
        assert relatable != interpola_terceros, (
            codigo, "relatable=%s pero el mensaje %s interpola {exc}"
            % (relatable, "si" if interpola_terceros else "no"))
    # Y el nodo tiene que usar la tabla para decidir, no relatarlo todo.
    assert "CODIGOS_DEL_SERVIDOR[codigo] ? dice : ''" in leer, leer


def test_ningun_mensaje_lleva_parse_mode():
    """Tras el agujero de los rotulos, la ausencia de `parse_mode` es parte de la
    defensa y no solo una preferencia, asi que se ata.

    Estos mensajes llevan texto que escribio el paciente (§4.4) y numeros del
    modelo. Con `MarkdownV2` un `*` o un `_` suelto rompe el envio o permite
    inyectar formato; y con formato disponible, los rotulos en mayusculas dejarian
    de ser la unica forma de rotular.
    """
    for nodo in _flujo()["nodes"]:
        if nodo["type"] != "n8n-nodes-base.telegram":
            continue
        p = nodo["parameters"]
        assert "parse_mode" not in json.dumps(p), nodo["name"]
        if p.get("operation") != "sendMessage":
            continue      # `Descargar fichero` no manda nada
        extras = p.get("additionalFields", {})
        assert "parse_mode" not in extras, (nodo["name"], extras)
        assert extras.get("appendAttribution") is False, nodo["name"]


def test_el_informe_no_lleva_ni_un_caracter_que_haya_escrito_el_paciente():
    """LA REGLA DEL INFORME, escrita al revés que en la ronda anterior.

    Antes el texto del paciente entraba en el informe y se le quitaban los
    caracteres peligrosos. Esa defensa se rodeó por tres vías, y la tercera no la
    arregla ningún filtro: con 447 caracteres y **ningún** carácter de control, el
    cliente de Telegram envuelve la burbuja y una fila renderizada empieza por el
    rótulo. «Cabe en una línea» es cierto en la cadena y falso en la pantalla,
    porque el salto lo mete el cliente y no el dato.

    Ahora: el informe se genera solo a partir de números validados, de valores de
    una enumeración cerrada y de literales del nodo. `tests/profesional.mjs`
    comprueba el comportamiento -que el informe no cambie ni un byte con 69
    caracteres distintos con forma de raya o de espacio-; esto ata la estructura,
    que es lo que una prueba de comportamiento no garantiza para el futuro.
    """
    fuente = _nodo(_flujo(), "Desenlace")["parameters"]["jsCode"]
    # 1. La lista negra tiene que estar FUERA. Si alguien la reinstala, la regla
    #    vuelve a ser «quitar caracteres» y el agujero vuelve con ella.
    assert "function neutralizar" not in fuente, \
        "la defensa es la regla invertida, no una lista de caracteres"
    # 2. El texto libre no se usa en el informe: solo en el mensaje aparte.
    cuerpo = fuente.split("function redactarResultado")[1]
    informe = cuerpo[:cuerpo.index("\n}\n")]
    assert "texto_libre" not in informe, informe
    assert "texto_libre" in fuente.split("function textoDelPaciente")[1], \
        "el texto libre tiene que ir al segundo mensaje"
    # 3. El bloque de los sintomas sale de la enumeracion cerrada, y un valor que
    #    no este en ella se declara sin imprimirse.
    assert "(valor no reconocido)" in fuente
    # 4. Y la busqueda va por propiedad PROPIA: con `tabla[v]` a secas, un valor
    #    como `constructor` alcanza Object.prototype y el informe imprimia
    #    «function Object() { [native code] }» en vez del dato.
    assert "hasOwnProperty" in fuente
    paleta = fuente.split("function dePaleta")[1]
    paleta = paleta[:paleta.index("\n}\n")]
    assert paleta.index("propio.call(tabla, v)") < paleta.index("tabla[v]"), \
        "la comprobacion de propiedad propia tiene que ir ANTES del acceso"
    # Y no queda ningun acceso a la enumeracion fuera de ese ayudante (sin contar
    # el comentario que explica por que no puede haberlo).
    codigo = "\n".join(l for l in fuente.splitlines()
                       if not l.lstrip().startswith("//"))
    assert codigo.count("tabla[") == 1, \
        "la enumeracion se consulta solo por `dePaleta`"


def test_el_segundo_mensaje_no_lleva_ni_un_caracter_del_sistema():
    """La otra mitad de la regla invertida, y el arreglo de la ronda 3.

    La versión anterior le ponía cabecera y cierre para atribuirlo, y se rodeó: con
    498 de sus 500 caracteres el paciente escribe el cierre —«Fin de lo que escribió
    el paciente.»— y detrás un informe positivo completo; el cierre de verdad queda
    debajo y vuelven a haber dos `CRIBADO`. La forma aguda es peor: en el paso 1→2,
    con 361 caracteres, el único bloque con forma de cribado de toda la conversación
    es el suyo, **antes de que se haya mandado ninguna placa**.

    El fondo: **cualquier delimitador que escriba el sistema, el paciente también
    puede escribirlo.** Lo único que no puede fabricar es el límite del mensaje: no
    puede crear una burbuja.

    Pero de ahí se sacó una conclusión de más: lo que se rodeó fue el **cierre**, y
    se tiraron los dos cuando solo uno había fallado. Si el paciente no puede
    fabricar el límite del mensaje, **tampoco puede ponerse delante del primer
    byte**: la posición 0 es tan del sistema como el límite. Y sin cabecera, en las
    superficies donde la burbuja se ve sola —notificación push, lista de chats,
    reenvío, cita, fijado, búsqueda— la atribución era **cero** y la interfaz la
    rotulaba «[retirado]»; el camino realista al daño es que el clínico reenvíe
    esa burbuja a un colega.

    Estructura final: **una línea literal en la posición 0, y nada más. Sin
    cierre.** `tests/profesional.mjs` comprueba el comportamiento con la igualdad
    `mensaje === cabecera + texto_recortado` y exigiendo la posición 0, no la mera
    presencia. Esto ata la estructura.
    """
    flujo = _flujo()
    assert [c["node"] for c in flujo["connections"]["Responder"]["main"][0]] \
        == ["Hay texto del paciente?"]
    salidas = flujo["connections"]["Hay texto del paciente?"]["main"]
    assert [c["node"] for c in salidas[0]] == ["Enviar texto del paciente"]
    assert len(salidas) == 1, "la rama falsa no manda nada"
    cond = _nodo(flujo, "Hay texto del paciente?")["parameters"]["conditions"]
    c = cond["conditions"][0]
    assert c["leftValue"] == "={{ $('Desenlace').first().json.texto_paciente }}", c
    assert c["operator"]["operation"] == "notEmpty", c
    envio = _nodo(flujo, "Enviar texto del paciente")["parameters"]
    # El texto del mensaje es SOLO la expresión. Cualquier literal en el nodo de
    # Telegram quedaría fuera del alcance de la igualdad que prueba el arnés.
    assert envio["text"] == "={{ $('Desenlace').first().json.texto_paciente }}"
    assert "inlineKeyboard" not in envio, "un teclado tambien seria mio"
    # Y el nodo que lo produce devuelve la cabecera y el recorte, y nada más.
    fuente = _nodo(flujo, "Desenlace")["parameters"]["jsCode"]
    cuerpo = fuente.split("function textoDelPaciente")[1]
    cuerpo = cuerpo[:cuerpo.index("\n}\n")]
    assert "recortar(libre, LIMITE_TEXTO_LIBRE)" in cuerpo, cuerpo
    assert cuerpo.rstrip().endswith("return CABECERA_PACIENTE + recortado;"), cuerpo
    # La decisión se toma con lo que se manda, no con el original: la guarda mira
    # `recortado` y no `libre`. Con 600 espacios y una `x` detrás, mirar `libre`
    # prometía un comentario y mandaba una burbuja de 500 espacios.
    assert "(recortado)" in cuerpo and "(libre)" not in cuerpo, cuerpo
    # Y la guarda se define por lo que SI cuenta, no por una lista de
    # caracteres invisibles: `trim()` dejaba pasar U+200B, U+0085, U+2060,
    # U+180E y U+3164, y con 500 copias el informe prometia un comentario
    # que la burbuja no ensenaba. Se afirma la FORMA de la regla -una clase
    # de caracteres permitidos- y no su texto exacto, para que anadir una
    # categoria no rompa esta prueba sin motivo.
    assert "TIENE_CONTENIDO" in cuerpo, cuerpo
    clase = fuente.split("const TIENE_CONTENIDO = ")[1].split("\n")[0]
    for categoria in (r"\p{L}", r"\p{N}", r"\p{P}", r"\p{S}"):
        assert categoria in clase, (categoria, clase)
    assert r"\p{C}" not in clase, (
        "los caracteres de control NO cuentan como contenido: son justo los "
        "que se ven vacios", clase)
    # La cabecera es UNA línea y acaba en salto: lo que venga detrás empieza en la
    # línea 2, y no hay cierre que el paciente pueda fabricar.
    m = re.search(r"const CABECERA_PACIENTE = '([^']+)';", fuente)
    assert m, fuente
    assert m.group(1).endswith(r"\n") and m.group(1).count(r"\n") == 1, m.group(1)
    # No hay cierre: es lo que se demostró falsificable. Se mira el código, no los
    # comentarios, que sí lo mencionan para explicar por qué no está.
    codigo_js = "\n".join(l for l in fuente.splitlines()
                          if not l.lstrip().startswith("//"))
    assert "CIERRE" not in codigo_js, "el cierre es lo que se demostro falsificable"
    # El aviso vive en el PRIMER mensaje, que es el canal que el paciente no toca.
    assert "bloques.push(AVISA_DEL_SEGUNDO)" in fuente
    # Y este mensaje tampoco lleva parse_mode: lo cubre
    # `test_ningun_mensaje_lleva_parse_mode`, que recorre los nueve nodos.


def test_ningun_mensaje_puede_pasarse_del_limite_de_telegram():
    """Un mensaje de más de 4 096 caracteres lo rechaza Telegram, y un mensaje
    rechazado es **un profesional que no recibe nada**: el mismo desenlace que el
    agujero de `ERRORES[codigo]`, por otra puerta.

    `e.detalle` era el único cabo suelto —todo lo demás está acotado por
    construcción: literales, números y valores de la enumeración—, y el camino para
    llegar a él es justo el que el §9 más teme, una caída del servidor con un
    volcado de 20 000 caracteres. Con él iba sin recortar, el primer mensaje salía
    de 20 031.

    El comportamiento y la mutación los cubre `tests/profesional.mjs`; esto ata que
    el tope siga existiendo en los dos sitios que lo aplican.
    """
    leer = _nodo(_flujo(), "Leer respuesta")["parameters"]["jsCode"]
    desen = _nodo(_flujo(), "Desenlace")["parameters"]["jsCode"]
    # En el origen, donde nace el detalle del servidor.
    assert re.search(r"const TOPE_DETALLE = (\d+);", leer), leer
    assert "slice(0, TOPE_DETALLE)" in leer, leer
    # Y otra vez donde se usa, porque a `Desenlace` lo alimentan cuatro nodos y
    # basta con que uno no lo acote.
    m = re.search(r"const TOPE_DETALLE = (\d+);", desen)
    assert m, desen
    assert int(m.group(1)) <= 1000, m.group(1)
    assert "recortar(e.detalle, TOPE_DETALLE)" in desen, desen
    # Y el texto libre, que es el otro dato de longitud ajena.
    assert re.search(r"const LIMITE_TEXTO_LIBRE = (\d+);", desen), desen


def test_el_codigo_del_caso_se_valida_donde_se_imprime():
    """N1: `'Caso ' + String(e.codigo)` era seguro **solo** porque hoy lo genera
    `generar_codigo()`. Eso es una propiedad de otro sitio: la columna no tiene
    CHECK, y el día que alguien inserte un cuestionario a mano o lo importe, esto
    imprimiría lo que le dieran. Un identificador que se imprime sin validar es el
    mismo patrón que ya falló dos veces en este nodo.
    """
    fuente = _nodo(_flujo(), "Desenlace")["parameters"]["jsCode"]
    assert "codigoODesconocido(e.codigo)" in fuente
    assert "'Caso ' + String(e.codigo" not in fuente
    # El alfabeto es el del §5.2, copiado aquí a mano como testigo independiente.
    assert "const ALFABETO_CODIGO = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';" in fuente
    assert "(código no reconocido)" in fuente


def test_la_tabla_de_errores_se_consulta_por_propiedad_propia():
    """El SEGUNDO agujero de `Object.prototype`, que hay que nombrar.

    `ERRORES[codigo]` con `error_cod = "constructor"` devolvía la función `Object`,
    `fila.texto` era `undefined`, y **el profesional no recibía nada** — con la
    suite entera en verde. Es el mismo fallo que el de la enumeración de síntomas,
    en otro sitio, y no lo mencioné al arreglarlo.

    `tests/profesional.mjs` lo comprueba con las siete claves heredadas **y con una
    prueba de mutación**: quitándole la guarda al nodo real, el mensaje se rompe.
    """
    fuente = _nodo(_flujo(), "Desenlace")["parameters"]["jsCode"]
    assert "propio.call(ERRORES, codigo) ? ERRORES[codigo] : null" in fuente
    codigo = "\n".join(l for l in fuente.splitlines()
                       if not l.lstrip().startswith("//"))
    assert codigo.count("ERRORES[codigo]") == 1, codigo.count("ERRORES[codigo]")


def test_las_dos_etiquetas_son_las_que_emite_el_servidor():
    """Si SP2 renombrara la etiqueta negativa, `Leer respuesta` la rechazaría y
    **toda** radiografía negativa terminaría la conversación con
    `error_no_reconocido`. Esto lo ata a la fuente en vez de dejarlo a la suerte.

    Se lee `inferencia.py`, que es quien las emite (§10.2).
    """
    fuente_py = (pathlib.Path(__file__).resolve().parents[1] / "src"
                 / "copiloto_triaje" / "servicio" / "inferencia.py"
                 ).read_text(encoding="utf-8")
    m = re.search(r'"clasificacion":\s*\(\s*"([a-z_]+)"\s+if\s+.*?else\s+"([a-z_]+)"',
                  fuente_py, re.S)
    assert m, "no encuentro la expresion que decide `clasificacion` en inferencia.py"
    positiva, negativa = m.group(1), m.group(2)
    leer = _nodo(_flujo(), "Leer respuesta")["parameters"]["jsCode"]
    declaradas = re.search(r"const ETIQUETAS = \[([^\]]+)\]", leer)
    assert declaradas, leer
    assert [x.strip().strip("'\"") for x in declaradas.group(1).split(",")] == \
        [positiva, negativa], (declaradas.group(1), positiva, negativa)
    # Y la que `Desenlace` considera positiva es la misma.
    desen = _nodo(_flujo(), "Desenlace")["parameters"]["jsCode"]
    assert re.search(r"const POSITIVA = '%s'" % re.escape(positiva), desen), positiva


def test_el_texto_crudo_del_servidor_siempre_queda_registrado():
    """Lo que mi informe anterior decía y era falso.

    En la rama sin código, `consultas.error` recibía solo `"dicom_invalido"`:
    `Desenlace` concatenaba el detalle únicamente si el código era
    `error_no_reconocido`, y `Leer respuesta` ya había sustituido el texto del
    servidor por uno fabricado. Para un DICOM truncado la pérdida es nula; para
    cualquier otra caída sin código se perdía lo único diagnosticable.

    Ahora `Leer respuesta` lleva `crudo` aparte de `detalle` -uno es lo que se
    registra, el otro lo que se puede enseñar- y `Desenlace` lo concatena para
    **todos** los códigos. El comportamiento lo comprueba el arnés; esto ata que
    los dos campos sigan existiendo y que el código siga siendo lo primero, que es
    de lo que depende el `GROUP BY` del §16.
    """
    leer = _nodo(_flujo(), "Leer respuesta")["parameters"]["jsCode"]
    assert "crudo" in leer and "detalle" in leer
    assert re.search(r"const salir = \(codigo, detalle, crudo\)", leer), leer
    desen = _nodo(_flujo(), "Desenlace")["parameters"]["jsCode"]
    assert "codificar(codigo + (crudo ? ': ' + crudo : ''))" in desen, \
        "el codigo tiene que ir PRIMERO: el §16 agrupa por el"


def test_los_tres_bloques_del_spec_estan_rotulados_y_separados():
    """§8, criterio 6. Los rotulos son lo que impide que el clinico reciba dos
    afirmaciones contradictorias sin pista de cual manda."""
    fuente = _nodo(_flujo(), "Desenlace")["parameters"]["jsCode"]
    for rotulo in ("CRIBADO — ", "EVIDENCIA DE LA IMAGEN — ",
                   "REFERIDO POR EL PACIENTE — ", "EXPLORADO — "):  # y nada mas
        assert rotulo in fuente, rotulo
    assert "bloques.join('\\n\\n')" in fuente, "los bloques van separados"
    assert "⚠️" in fuente, "el aviso de la banda contradictoria"


def test_el_flujo_solo_habla_con_el_copiloto_en_la_rama_de_la_radiografia():
    """Nada de llamadas de red fuera de la rama que clasifica: ni telemetria, ni
    un LLM (§4.5: ningun dato de paciente sale hacia un tercero)."""
    flujo = _flujo()
    externos = [n for n in flujo["nodes"]
                if n["type"] in ("n8n-nodes-base.httpRequest",
                                 "n8n-nodes-base.webhook")
                or "langchain" in n["type"]]
    assert [n["name"] for n in externos] == ["Webhook Telegram (profesional)",
                                             "Llamar al copiloto"], externos
    for nodo in flujo["nodes"]:
        if nodo["type"] != "n8n-nodes-base.code":
            continue
        for primitiva in ("fetch(", "require(", "http.request", "axios",
                          "child_process"):
            assert primitiva not in nodo["parameters"]["jsCode"], \
                (nodo["name"], primitiva)


def test_un_solo_nodo_escribe_en_consultas():
    """§10.1: la fila se escribe UNA sola vez, con el desenlace final, para que
    el dashboard no cuente dos veces la misma consulta. Con un solo escritor eso
    es una propiedad del grafo, no una intencion."""
    escritores = [n["name"] for n in _flujo()["nodes"]
                  if n["type"] == "n8n-nodes-base.postgres"
                  and "INSERT INTO consultas" in n["parameters"]["query"]]
    assert escritores == ["Registrar"], escritores
    borradores = [n["name"] for n in _flujo()["nodes"]
                  if n["type"] == "n8n-nodes-base.postgres"
                  and "DELETE FROM sesiones_profesional" in n["parameters"]["query"]]
    assert borradores == ["Registrar"], borradores


def test_ninguna_consulta_pide_mas_parametros_de_los_que_n8n_le_pasaria():
    """El fallo bloqueante de la T5, convertido en prueba estatica: el nodo
    Postgres arma sus parametros con `stringToArray`, que parte por comas y
    DESCARTA LOS VACIOS. Si una consulta referencia `$5` y un valor sale vacio,
    n8n pasa cuatro y Postgres responde `there is no parameter $5`."""
    for nodo in _flujo()["nodes"]:
        if nodo["type"] != "n8n-nodes-base.postgres":
            continue
        consulta = nodo["parameters"]["query"]
        crudo = nodo["parameters"].get("options", {}).get("queryReplacement", "")
        referenciados = max((int(m) for m in re.findall(r"\$(\d+)", consulta)),
                            default=0)
        pasados = len(re.findall(r"\{\{.*?\}\}", crudo))
        assert referenciados == pasados, (nodo["name"], referenciados, pasados)


def test_cada_signo_declara_la_clave_y_el_rango_del_spec():
    """La tabla de `Decidir` es la UNICA fuente de la clave con la que se guarda
    cada signo y del rango que se acepta. Se compara literal contra el §4.4."""
    fuente = _nodo(_flujo(), "Decidir")["parameters"]["jsCode"]
    pares = re.findall(r"\{paso:\s*(\d+),\s*clave:\s*'([a-z_]+)'", fuente)
    assert {int(n): c for n, c in pares if int(n) in SPEC_4_4} == \
        {n: clave for n, (clave, _a, _b) in SPEC_4_4.items()}
    for paso, (clave, minimo, maximo) in SPEC_4_4.items():
        if minimo is None:
            continue
        patron = (r"min:\s*%s(\.0)?\s*,\s*max:\s*%s(\.0)?\b"
                  % (re.escape(str(minimo)), re.escape(str(maximo))))
        assert re.search(patron, fuente), (clave, minimo, maximo)


def test_guardar_signo_consume_la_clave_que_produce_decidir():
    """La tabla del §4.4 vive en `Decidir`, pero si el nodo que ESCRIBE no la
    usa, la tabla es decorativa. Fijar la clave, o deducirla del prefijo del
    callback_data, dejaria la suite verde."""
    nodo = _nodo(_flujo(), "Guardar signo")
    crudo = nodo["parameters"]["options"]["queryReplacement"]
    exprs = [e.strip() for e in re.findall(r"\{\{(.*?)\}\}", crudo)]
    assert exprs == [
        "$('Normalizar update').first().json.chat_id",
        "$json.clave",
        "$json.valor_cod",
        "$json.paso",
        "$json.paso_actual",
    ], exprs
    assert set(re.findall(r"\$(\d)", nodo["parameters"]["query"])) == \
        {"1", "2", "3", "4", "5"}


def test_el_reparto_manda_cada_paso_a_la_pregunta_que_le_toca():
    """El fallo silencioso que esto cierra: que la salida del paso 4 llegue al
    nodo del paso 5. El profesional veria una pregunta y su respuesta se
    guardaria en la clave de la otra."""
    flujo = _flujo()
    salidas = flujo["connections"]["Repartir pregunta"]["main"]
    esperado = ["Pedir codigo", "Pedir temperatura", "Pedir frecuencia",
                "Pedir crepitantes", "Pedir murmullo", "Pedir placa"]
    assert [[c["node"] for c in s] for s in salidas] == [[x] for x in esperado]
    reglas = _nodo(flujo, "Repartir pregunta")["parameters"]["rules"]["values"]
    assert len(reglas) == 6, len(reglas)
    for i, regla in enumerate(reglas):
        condiciones = regla["conditions"]["conditions"]
        assert len(condiciones) == 1, (i, condiciones)
        c = condiciones[0]
        assert c["leftValue"] == "={{ $('Decidir').first().json.paso }}", c
        assert c["operator"] == {"type": "number", "operation": "equals"}, c
        assert c["rightValue"] == i + 1, (f"salida {i}", c["rightValue"])


def test_los_botones_llevan_el_prefijo_de_su_propia_pregunta():
    """Sin prefijo por pregunta, un teclado viejo que siga en la pantalla
    guardaria el «Si» de crepitantes dentro de `murmullo_disminuido`."""
    flujo = _flujo()

    def botones(nombre):
        salida = []
        for fila in (_nodo(flujo, nombre)["parameters"]
                     .get("inlineKeyboard", {}).get("rows", [])):
            for b in fila.get("row", {}).get("buttons", []):
                salida.append(b["additionalFields"]["callback_data"])
        return salida

    assert botones("Pedir crepitantes") == ["s4:si", "s4:no"]
    assert botones("Pedir murmullo") == ["s5:si", "s5:no"]
    fuente = _nodo(flujo, "Decidir")["parameters"]["jsCode"]
    assert re.findall(r"prefijo:\s*'(s\d+)'", fuente) == ["s4", "s5"]


def test_el_nombre_lleva_el_prefijo_acordado_y_no_pisa_nada_del_cliente():
    """Regla dura: el workflow es NUEVO y se distingue de los del cliente."""
    assert _flujo()["name"] == "\U0001fa7a Copiloto Triaje: Profesional (Telegram)"


def test_el_flujo_del_profesional_se_comporta_como_dice_el_spec():
    """Ejecuta el jsCode REAL de los cuatro nodos de codigo con node.

    Las pruebas estaticas de arriba comparan TABLAS; no pueden decir nada de las
    RAMAS, y las ramas son donde estan las dos propiedades medidas de esta tarea:
    que los tres bloques del §8 salgan separados con su aviso, y que ninguna de
    las once ramas del §9 emita una cifra. `tests/profesional.mjs` lo ejecuta
    contra los valores REALES medidos del contenedor, incluida la placa de la
    banda contradictoria.

    **Falla, no se salta, si no hay node.** Un skip se ve verde. Quien toque este
    workflow tiene node, porque n8n corre sobre node.
    """
    node = shutil.which("node")
    assert node, ("hace falta node para ejecutar el jsCode del workflow: "
                  "instala Node.js, o corre `node tests/profesional.mjs` a mano")
    arnes = pathlib.Path(__file__).resolve().parent / "profesional.mjs"
    assert arnes.exists(), arnes
    r = subprocess.run([node, str(arnes)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    assert r.returncode == 0, r.stdout[-6000:] + r.stderr[-2000:]
    assert "TODO VERDE" in r.stdout, r.stdout[-2000:]


def test_el_workflow_del_paciente_no_se_ha_tocado():
    """Regla dura: ningun workflow existente se modifica, ni el del paciente. Su
    export sigue siendo el de la tarea 5, nodo por nodo."""
    paciente = _flujo(FLUJO_PACIENTE)
    assert paciente["name"] == "\U0001fa7a Copiloto Triaje: Paciente (Telegram)"
    assert len(paciente["nodes"]) == 24, len(paciente["nodes"])
    # Y sigue sin hablar con el copiloto (D1).
    assert not any("copiloto-mcp" in json.dumps(n) for n in paciente["nodes"])
