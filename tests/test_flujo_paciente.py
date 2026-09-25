# -*- coding: utf-8 -*-
"""El flujo del paciente, conducido por updates de Telegram fabricados.

Las aserciones de las pruebas conducidas son sobre la BASE DE DATOS, no sobre
lo que el bot conteste: lo que importa es que la respuesta quede en la clave
correcta, porque de ahi sale la probabilidad previa de H6.

El fichero tiene DOS mitades y no es casual:

- `TestConducido` habla con un n8n vivo y con `copiloto-bd`. Se salta si falta
  el entorno (`N8N_URL`, `COPILOTO_BD_DSN`, `TELEGRAM_SECRET_PRUEBA`).
- Las pruebas de MODULO leen el JSON exportado del workflow y no necesitan
  NADA: ni red, ni base, ni secretos. Ahi viven las dos garantias que no pueden
  depender de que alguien tenga el tunel montado: que el flujo del paciente no
  habla con el copiloto (D1) y que cada pregunta guarda en SU clave (§4.4).
  Estan FUERA de la clase a proposito -ver el comentario de `limpio`-.
"""
import json
import os
import pathlib
import re
import time

import pytest

SECRETO = os.environ.get("TELEGRAM_SECRET_PRUEBA")
RUTA = os.environ.get("WEBHOOK_PACIENTE", "copiloto-paciente")
CHAT = 999000001          # chat de prueba, nunca uno real

FLUJO = pathlib.Path(__file__).resolve().parents[1] / "n8n" / "copiloto-paciente.json"

# Las 7 preguntas del §4.4 del spec, copiadas AQUI a mano. Esta tabla es el
# testigo independiente: si el workflow cambia una clave o un valor, las
# pruebas de modulo lo ven. Por eso no se importa de ningun sitio.
SPEC_4_4 = {
    1: ("fiebre",         {"si", "no", "no_se"}),
    2: ("tos",            {"con_flema", "seca", "no"}),
    3: ("dias_evolucion", {"menos_3", "3_a_7", "mas_7"}),
    4: ("disnea",         {"si", "no"}),
    5: ("dolor_toracico", {"si", "no"}),
    6: ("asma",           {"si", "no", "no_se"}),
    7: ("texto_libre",    {"omitir"}),
}


def _mensaje(texto, chat=CHAT):
    return {"update_id": 1, "message": {
        "message_id": 1, "date": 0, "chat": {"id": chat, "type": "private"},
        "from": {"id": chat, "is_bot": False, "first_name": "Prueba"},
        "text": texto}}


def _boton(dato, chat=CHAT):
    return {"update_id": 2, "callback_query": {
        "id": "1", "from": {"id": chat, "is_bot": False, "first_name": "Prueba"},
        "message": {"message_id": 1, "date": 0,
                    "chat": {"id": chat, "type": "private"}},
        "data": dato}}


def _esperar(bd, consulta, intentos=20):
    for _ in range(intentos):
        fila = bd.execute(consulta).fetchone()
        if fila and fila[0]:
            return fila
        time.sleep(0.5)
    return None


def _flujo():
    """El JSON exportado. Si no existe, la prueba FALLA -no se salta-: su
    ausencia es exactamente lo que estas pruebas existen para detectar."""
    assert FLUJO.exists(), f"falta el workflow exportado: {FLUJO}"
    return json.loads(FLUJO.read_text(encoding="utf-8"))


def _nodo(flujo, nombre):
    for n in flujo["nodes"]:
        if n["name"] == nombre:
            return n
    raise AssertionError(f"el workflow no tiene un nodo '{nombre}'")


def _botones(nodo):
    """Los (texto, callback_data) del teclado en linea de un nodo Telegram."""
    salida = []
    for fila in nodo["parameters"].get("inlineKeyboard", {}).get("rows", []):
        for b in fila.get("row", {}).get("buttons", []):
            salida.append((b.get("text"),
                           b.get("additionalFields", {}).get("callback_data")))
    return salida


# --------------------------------------------------------------------------
# Conducidas: n8n vivo + copiloto-bd. Se saltan sin entorno.
# --------------------------------------------------------------------------
@pytest.mark.skipif(not SECRETO,
                    reason="sin TELEGRAM_SECRET_PRUEBA: no se puede pasar la "
                           "puerta del secret_token del §4.2")
class TestConducido:
    """El `limpio` de aqui es autouse pero SOLO dentro de la clase.

    Si estuviera a nivel de modulo -como en el brief- arrastraria a `bd_sp3` a
    TODAS las pruebas del fichero, y las dos que comprueban el JSON exportado
    -las que sostienen D1 y §4.4- se saltarian en cualquier maquina sin tunel
    SSH. Un skip se ve verde: la garantia mas importante del flujo no se
    comprobaria nunca y nadie lo notaria.
    """

    @pytest.fixture(autouse=True)
    def limpio(self, bd_sp3):
        # `limite_paciente` tambien: el flujo se niega a empezar el sexto
        # cuestionario del dia (§4.2), asi que sin borrar el contador la suite
        # se pondria roja a la sexta ejecucion del mismo dia. El contador es
        # del chat de prueba, no de nadie real.
        for tabla in ("sesiones_paciente", "limite_paciente"):
            bd_sp3.execute(f"DELETE FROM {tabla} WHERE chat_id = %s", (CHAT,))
        yield
        for tabla in ("sesiones_paciente", "limite_paciente"):
            bd_sp3.execute(f"DELETE FROM {tabla} WHERE chat_id = %s", (CHAT,))

    def test_sin_secret_token_no_pasa_nada(self, webhook_n8n, bd_sp3):
        """El webhook es publico. Sin esta comprobacion, la lista blanca del bot
        del profesional tampoco protege de nada."""
        webhook_n8n(RUTA, _mensaje("/start"))          # sin secreto
        time.sleep(3)
        assert bd_sp3.execute(
            "SELECT count(*) FROM sesiones_paciente WHERE chat_id = %s",
            (CHAT,)).fetchone()[0] == 0

    def test_con_un_secreto_equivocado_tampoco(self, webhook_n8n, bd_sp3):
        """La otra mitad de la puerta: no basta con rechazar al que no manda
        cabecera; hay que rechazar al que manda una que no vale."""
        webhook_n8n(RUTA, _mensaje("/start"), SECRETO + "-no")
        time.sleep(3)
        assert bd_sp3.execute(
            "SELECT count(*) FROM sesiones_paciente WHERE chat_id = %s",
            (CHAT,)).fetchone()[0] == 0

    def test_no_aceptar_el_consentimiento_no_guarda_NADA(self, webhook_n8n, bd_sp3):
        """Criterio de aceptacion 1 del spec."""
        webhook_n8n(RUTA, _mensaje("/start"), SECRETO)
        time.sleep(2)
        webhook_n8n(RUTA, _boton("consent:no"), SECRETO)
        time.sleep(3)
        assert bd_sp3.execute(
            "SELECT count(*) FROM sesiones_paciente WHERE chat_id = %s",
            (CHAT,)).fetchone()[0] == 0
        assert bd_sp3.execute(
            "SELECT count(*) FROM cuestionarios WHERE consentido_en > now()"
            " - interval '1 minute'").fetchone()[0] == 0

    def test_aceptar_crea_la_sesion_con_su_marca_de_consentimiento(
            self, webhook_n8n, bd_sp3):
        webhook_n8n(RUTA, _mensaje("/start"), SECRETO)
        time.sleep(2)
        webhook_n8n(RUTA, _boton("consent:si"), SECRETO)
        fila = _esperar(bd_sp3,
                        f"SELECT consentido_en FROM sesiones_paciente"
                        f" WHERE chat_id = {CHAT}")
        assert fila is not None, "no se creo la sesion tras aceptar"

    def test_cada_respuesta_queda_en_SU_clave(self, webhook_n8n, bd_sp3):
        """El fallo que esto impide no da error: da una probabilidad previa
        equivocada en H6 y nadie la ve."""
        webhook_n8n(RUTA, _mensaje("/start"), SECRETO); time.sleep(2)
        webhook_n8n(RUTA, _boton("consent:si"), SECRETO); time.sleep(2)
        for dato in ("p1:si", "p2:con_flema", "p3:3_a_7", "p4:no",
                     "p5:si", "p6:no"):
            webhook_n8n(RUTA, _boton(dato), SECRETO)
            time.sleep(1.5)
        fila = _esperar(bd_sp3,
                        f"SELECT respuestas FROM sesiones_paciente"
                        f" WHERE chat_id = {CHAT}")
        assert fila[0] == {"fiebre": "si", "tos": "con_flema",
                           "dias_evolucion": "3_a_7", "disnea": "no",
                           "dolor_toracico": "si", "asma": "no"}

    def test_al_completar_nace_el_codigo_y_muere_la_sesion(
            self, webhook_n8n, bd_sp3):
        webhook_n8n(RUTA, _mensaje("/start"), SECRETO); time.sleep(2)
        webhook_n8n(RUTA, _boton("consent:si"), SECRETO); time.sleep(2)
        for dato in ("p1:si", "p2:seca", "p3:menos_3", "p4:no", "p5:no",
                     "p6:no_se"):
            webhook_n8n(RUTA, _boton(dato), SECRETO); time.sleep(1.5)
        webhook_n8n(RUTA, _boton("p7:omitir"), SECRETO)

        # Acotado a los ultimos 2 minutos: sin eso, una fila de una corrida
        # anterior satisface la asercion y la prueba se vuelve verde sin que
        # el flujo haya hecho nada.
        fila = _esperar(bd_sp3,
                        "SELECT codigo, expira_en FROM cuestionarios"
                        " WHERE creado_en > now() - interval '2 minutes'"
                        " ORDER BY creado_en DESC LIMIT 1")
        assert fila is not None
        codigo, expira = fila
        assert len(codigo) == 6
        assert set(codigo) <= set("ABCDEFGHJKMNPQRSTUVWXYZ23456789")
        assert bd_sp3.execute(
            "SELECT count(*) FROM sesiones_paciente WHERE chat_id = %s",
            (CHAT,)).fetchone()[0] == 0, "la sesion debia borrarse al completar"


# --------------------------------------------------------------------------
# Sobre el JSON exportado. Sin entorno, sin red, sin base.
# --------------------------------------------------------------------------
def test_el_flujo_del_paciente_no_habla_con_el_copiloto():
    """La garantia de D1, comprobada sobre el JSON exportado y no sobre la
    intencion: si algun nodo apuntara al copiloto, existiria un camino por el
    que un paciente recibe un resultado clinico."""
    texto = json.dumps(_flujo())
    for prohibido in ("copiloto-mcp", ":8000", "clasificar_radiografia",
                      "razon_de_verosimilitud"):
        assert prohibido not in texto, prohibido


def test_el_flujo_del_paciente_no_tiene_ningun_nodo_que_salga_a_la_red():
    """El complemento del anterior. Aquel prohibe unos literales; este prohibe
    la CAPACIDAD: un flujo sin nodos HTTP ni MCP no puede consultar el modelo
    ni aunque alguien escriba la URL de otra forma -por IP, o troceada-."""
    tipos = {n["type"] for n in _flujo()["nodes"]}
    permitidos = {
        "n8n-nodes-base.webhook", "n8n-nodes-base.code",
        "n8n-nodes-base.postgres", "n8n-nodes-base.switch",
        "n8n-nodes-base.telegram", "n8n-nodes-base.if",
        "n8n-nodes-base.noOp", "n8n-nodes-base.stickyNote",
    }
    assert tipos <= permitidos, tipos - permitidos


def test_los_botones_de_cada_pregunta_son_los_del_spec():
    """§4.4 fija los valores permitidos. Un `callback_data` con un valor que
    H6 no espera no da error: entra en el jsonb y falsea el calculo."""
    flujo = _flujo()
    vistos = {}
    for nodo in flujo["nodes"]:
        for _texto, dato in _botones(nodo):
            m = re.fullmatch(r"p([1-7]):(.+)", dato or "")
            if m:
                vistos.setdefault(int(m.group(1)), set()).add(m.group(2))
    esperado = {n: valores for n, (_clave, valores) in SPEC_4_4.items()}
    assert vistos == esperado


def test_cada_pregunta_declara_la_clave_del_spec():
    """La tabla del nodo `Decidir` es la UNICA fuente de la que sale la clave
    con la que se guarda cada respuesta. Se compara literal contra el §4.4."""
    codigo = _nodo(_flujo(), "Decidir")["parameters"]["jsCode"]
    pares = re.findall(r"\{n:\s*(\d+),\s*clave:\s*'([a-z_]+)'", codigo)
    assert len(pares) == 7, f"se esperaban 7 preguntas, hay {len(pares)}"
    assert {int(n): c for n, c in pares} == {
        n: clave for n, (clave, _v) in SPEC_4_4.items()}


def test_el_reparto_manda_cada_paso_a_la_pregunta_que_le_toca():
    """El fallo silencioso que esto cierra: que la salida del paso 3 llegue al
    nodo de la pregunta 4. El paciente veria una pregunta, y su respuesta se
    guardaria en la clave de la otra."""
    flujo = _flujo()
    salidas = flujo["connections"]["Repartir pregunta"]["main"]
    assert len(salidas) == 8, f"se esperaban 8 salidas, hay {len(salidas)}"
    for i in range(7):
        destinos = [c["node"] for c in salidas[i]]
        assert len(destinos) == 1, (i, destinos)
        prefijos = {d.split(":")[0] for _t, d in _botones(_nodo(flujo, destinos[0]))}
        assert prefijos == {f"p{i + 1}"}, (i + 1, destinos[0], prefijos)
    assert [c["node"] for c in salidas[7]] == ["Completar"]


def test_el_webhook_rechaza_por_cabecera_antes_de_ejecutar_nada():
    """§4.2: la comprobacion del `secret_token` va ANTES de mirar nada mas.
    Con `headerAuth` la hace n8n en la capa del webhook, asi que ningun nodo
    llega a correr, y el secreto vive en una credencial y no en este JSON."""
    p = _nodo(_flujo(), "Webhook Telegram (paciente)")["parameters"]
    assert p["authentication"] == "headerAuth"
    assert p["httpMethod"] == "POST"


def test_ningun_secreto_viaja_en_el_JSON_exportado():
    """El §12 del spec: ninguno va al repositorio. Las credenciales se
    referencian por id y nombre; sus valores se quedan en n8n."""
    flujo = _flujo()
    # Las credenciales se referencian por id y nombre y nada mas: sus valores
    # viven en n8n.
    for nodo in flujo["nodes"]:
        for tipo, cred in (nodo.get("credentials") or {}).items():
            assert set(cred) <= {"id", "name"}, (nodo["name"], tipo, cred)
    texto = json.dumps(flujo)
    # Un token de bot de Telegram tiene forma reconocible: <id>:<35 chars>. Se
    # busca la FORMA y no la palabra «token», que aparece legitimamente en los
    # comentarios del flujo al explicar el secret_token del §4.2.
    assert not re.search(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b", texto), \
        "algo con la forma de un token de bot de Telegram"
    for sospechoso in ("accessToken", "\"password\""):
        assert sospechoso not in texto, sospechoso


def test_solo_se_usa_la_credencial_del_bot_del_paciente():
    """D9 y la regla dura 2: reutilizar una credencial de Telegram del cliente
    le robaria el webhook a un bot suyo y lo dejaria mudo sin error visible."""
    usadas = {c["id"]
              for n in _flujo()["nodes"]
              for t, c in (n.get("credentials") or {}).items()
              if t == "telegramApi"}
    assert usadas == {"[retirado]"}, usadas    # [retirado]


def test_el_workflow_no_guarda_los_datos_de_ejecucion():
    """§5.4: n8n guarda las entradas y salidas de cada nodo en la base de
    n8n, que es DEL CLIENTE. Ahi irian las respuestas del cuestionario."""
    ajustes = _flujo().get("settings", {})
    assert ajustes.get("saveDataSuccessExecution") == "none"
    assert ajustes.get("saveDataErrorExecution") == "none"
    assert ajustes.get("saveManualExecutions") is False
