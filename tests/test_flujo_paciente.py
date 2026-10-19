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
import shutil
import subprocess
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
                        "SELECT codigo, expira_en, respuestas FROM cuestionarios"
                        " WHERE creado_en > now() - interval '2 minutes'"
                        " ORDER BY creado_en DESC LIMIT 1")
        assert fila is not None, (
            "no nacio el codigo tras pulsar Omitir. Es el camino normal de "
            "salida de la pregunta 7, y es por donde se rompio en la ronda 1: "
            "el valor vacio desaparecia de los parametros del nodo Postgres")
        codigo, expira, respuestas = fila
        assert len(codigo) == 6
        assert set(codigo) <= set("ABCDEFGHJKMNPQRSTUVWXYZ23456789")
        # «Omitir» es ausencia de texto, no el texto "omitir". Si se guardara la
        # cadena, el profesional leeria "omitir" como si el paciente lo hubiera
        # escrito.
        assert "texto_libre" in respuestas, respuestas
        assert respuestas["texto_libre"] is None, respuestas["texto_libre"]
        assert bd_sp3.execute(
            "SELECT count(*) FROM sesiones_paciente WHERE chat_id = %s",
            (CHAT,)).fetchone()[0] == 0, "la sesion debia borrarse al completar"

    def test_el_texto_libre_de_la_7_llega_entero_y_no_inyecta_nada(
            self, webhook_n8n, bd_sp3):
        """La otra salida de la pregunta 7. Con comas, porque el parametro del
        nodo Postgres es una lista separada por comas."""
        webhook_n8n(RUTA, _mensaje("/start"), SECRETO); time.sleep(2)
        webhook_n8n(RUTA, _boton("consent:si"), SECRETO); time.sleep(2)
        for dato in ("p1:no", "p2:seca", "p3:mas_7", "p4:si", "p5:no", "p6:si"):
            webhook_n8n(RUTA, _boton(dato), SECRETO); time.sleep(1.5)
        veneno = "me duele, mucho; ' OR 1=1 --  y tambien la espalda"
        webhook_n8n(RUTA, _mensaje(veneno), SECRETO)

        fila = _esperar(bd_sp3,
                        "SELECT respuestas FROM cuestionarios"
                        " WHERE creado_en > now() - interval '2 minutes'"
                        " ORDER BY creado_en DESC LIMIT 1")
        assert fila is not None
        assert fila[0]["texto_libre"] == veneno, fila[0]["texto_libre"]
        assert fila[0]["asma"] == "si", fila[0]


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


def test_el_flujo_del_paciente_no_tiene_como_salir_a_la_red():
    """El complemento del anterior, y hay que ser exacto sobre su alcance.

    QUE GARANTIZA: que nadie *arrastre un nodo sin pensar*. Prohibe los tipos
    de nodo que hablan con el exterior -HTTP Request, cualquier nodo MCP- y
    busca primitivas de red en el `jsCode` de los nodos Code. Esa es la
    regresion realista: dentro de tres meses alguien amplia el flujo y mete un
    HTTP Request, o un `$helpers.httpRequest` en un Code.

    QUE **NO** GARANTIZA: no detiene a quien quiera evadirla a proposito. Un
    nodo Code de n8n SI puede salir a la red, y este flujo tiene dos. Con el
    nombre de la funcion construido en tiempo de ejecucion, o la URL troceada,
    esta prueba pasa y la llamada ocurre. No es una frontera de seguridad y no
    se debe presentar como tal: contra un cambio malicioso lo que hay es la
    revision del codigo, no esta prueba.

    Se escribe con todas las letras porque una prueba que promete mas de lo que
    cumple es peor que no tenerla: da por comprobada la garantia clinica de D1
    y nadie vuelve a mirarla.
    """
    flujo = _flujo()
    tipos = {n["type"] for n in flujo["nodes"]}
    permitidos = {
        "n8n-nodes-base.webhook", "n8n-nodes-base.code",
        "n8n-nodes-base.postgres", "n8n-nodes-base.switch",
        "n8n-nodes-base.telegram", "n8n-nodes-base.if",
        "n8n-nodes-base.noOp", "n8n-nodes-base.stickyNote",
    }
    assert tipos <= permitidos, tipos - permitidos

    # Los nodos Code estan permitidos -el flujo los necesita- pero un Code
    # alcanza la red. Se le mira el codigo.
    primitivas = ("httpRequest", "fetch(", "require('http", 'require("http',
                  "axios", "XMLHttpRequest", "$helpers", "net.", "dns.")
    for nodo in flujo["nodes"]:
        if nodo["type"] != "n8n-nodes-base.code":
            continue
        codigo = nodo["parameters"].get("jsCode", "")
        for p in primitivas:
            assert p not in codigo, (nodo["name"], p)


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


def test_el_consentimiento_dice_lo_que_pasa_con_los_datos():
    """D11, y la mitigación M2 del análisis ético (5-oct-2026): el
    consentimiento nombra al tercero por el que pasan los datos, dice que el
    resultado lo calcula una IA y da los plazos reales, también el de la copia
    que queda en `consultas`. Y ya no promete lo que no era verdad: que el
    identificador de Telegram nunca va unido a las respuestas (mientras se
    contesta, sí) ni que solo las ve el médico (las ve también el equipo)."""
    texto = _nodo(_flujo(), "Pedir consentimiento")["parameters"]["text"]
    for debe in ("Telegram", "inteligencia artificial", "NO un diagnóstico",
                 "7 días", "2 días", "31 de diciembre de 2026",
                 "equipo del proyecto", "urgencias AHORA"):
        assert debe in texto, debe
    for falso in ("NO va unido a sus respuestas", "Solo las verá el médico"):
        assert falso not in texto, falso
    assert len(texto) <= 4096      # el límite de un mensaje de Telegram
    assert "{{" not in texto       # un literal, no una expresión de n8n


def test_el_consentimiento_nombra_a_openai():
    """SP5-D, D7: el bot del profesional manda el informe a OpenAI para que lo
    resuma, y el paciente tiene que saberlo antes de aceptar. La viñeta va justo
    detrás de la de la inteligencia artificial que lee la radiografía, nombra a
    la empresa y dice qué NO lleva el resumen. El mensaje sigue cabiendo en uno
    de Telegram."""
    texto = _nodo(_flujo(), "Pedir consentimiento")["parameters"]["text"]
    lineas = texto.split("\n")
    (i,) = [i for i, l in enumerate(lineas) if l.startswith(
        "• Un programa de inteligencia artificial analiza la radiografía")]
    assert lineas[i + 1] == (
        "• Para su médico, otro programa de inteligencia artificial de OpenAI, una "
        "empresa extranjera, resume el informe del sistema. Ese resumen no lleva su "
        "nombre, su cuenta ni lo que usted escriba."), lineas[i + 1]
    assert texto.count("OpenAI") == 1
    assert len(texto) <= 4096


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


def test_las_reglas_del_reparto_encaminan_el_paso_a_su_propia_salida():
    """La otra mitad del reparto, y la que faltaba.

    La prueba de arriba solo mira las CONEXIONES: que la salida 3 vaya al nodo
    de la pregunta 3. Pero que el paso 3 llegue a la SALIDA 3 lo deciden las
    reglas del Switch, y esas no las miraba nadie. Cruzar dos `rightValue` deja
    al paciente del paso 3 viendo la pregunta 4 para siempre: contesta, el
    UPDATE no encuentra fila porque `paso` no coincide, y vuelve a ver la
    misma. Un bucle, sin un solo error en ningun log.
    """
    reglas = _nodo(_flujo(), "Repartir pregunta")["parameters"]["rules"]["values"]
    assert len(reglas) == 8, f"se esperaban 8 reglas, hay {len(reglas)}"
    for i, regla in enumerate(reglas):
        condiciones = regla["conditions"]["conditions"]
        assert len(condiciones) == 1, (i, condiciones)
        c = condiciones[0]
        assert c["leftValue"] == "={{ $json.paso }}", (i, c["leftValue"])
        assert c["operator"] == {"type": "number", "operation": "equals"}, (i, c["operator"])
        assert c["rightValue"] == i + 1, (f"salida {i}", c["rightValue"])


def test_guardar_respuesta_consume_la_clave_que_produce_decidir():
    """La tabla del §4.4 vive en `Decidir`, pero si el nodo que ESCRIBE no la
    usa, la tabla es decorativa. Fijar la clave a `disnea`, o deducirla del
    prefijo del callback_data, dejaba la suite verde.

    Se comprueba que los cinco parametros del UPDATE salen de donde deben: el
    chat del update normalizado, y la clave, el valor y los dos pasos del nodo
    `Decidir`. Nada literal.
    """
    nodo = _nodo(_flujo(), "Guardar respuesta")
    crudo = nodo["parameters"]["options"]["queryReplacement"]
    assert crudo.startswith("="), crudo
    exprs = [e.strip() for e in re.findall(r"\{\{(.*?)\}\}", crudo)]
    assert exprs == [
        "$('Normalizar update').first().json.chat_id",
        "$json.clave",
        "$json.valor_cod",
        "$json.paso",
        "$json.paso_actual",
    ], exprs
    # Y que la consulta use cada uno de los cinco, sin literales colados.
    consulta = nodo["parameters"]["query"]
    assert set(re.findall(r"\$(\d)", consulta)) == {"1", "2", "3", "4", "5"}


def test_ninguna_consulta_pide_mas_parametros_de_los_que_n8n_le_pasaria():
    """El fallo bloqueante de la ronda 1, convertido en prueba estatica.

    El nodo Postgres arma sus parametros con `stringToArray`, que parte la
    cadena por comas, recorta cada trozo **y descarta los vacios**. Si una
    consulta referencia `$5` y uno de los cinco valores sale vacio, n8n pasa
    cuatro y Postgres responde `there is no parameter $5`. Paso de verdad: el
    «Omitir» de la pregunta 7 mandaba cadena vacia para decir NULL, y el
    paciente que pulsaba Omitir -la salida normal de la ultima pregunta- no
    recibia su codigo ni ningun aviso.

    Esto comprueba el recuento; que ningun valor pueda salir vacio lo comprueba
    `tests/decidir.mjs`, que es donde se decide.
    """
    for nodo in _flujo()["nodes"]:
        if nodo["type"] != "n8n-nodes-base.postgres":
            continue
        consulta = nodo["parameters"]["query"]
        crudo = nodo["parameters"].get("options", {}).get("queryReplacement", "")
        referenciados = max((int(m) for m in re.findall(r"\$(\d+)", consulta)), default=0)
        pasados = len(re.findall(r"\{\{.*?\}\}", crudo))
        assert referenciados == pasados, (nodo["name"], referenciados, pasados)


def test_la_tabla_de_decision_se_comporta_como_dice_el_spec():
    """Ejecuta el jsCode REAL de `Normalizar update` y `Decidir` con node.

    Las pruebas estaticas comparan la TABLA de `Decidir` contra el §4.4, pero
    no pueden decir nada de sus RAMAS. Y las ramas son donde estaban los
    fallos: que /start a medias no borre las respuestas, que «Omitir» signifique
    null y no la cadena 'omitir', que ningun parametro salga vacio, que el paso
    8 se pueda reintentar. Todo eso hay que ejecutarlo, y el codigo es
    JavaScript.

    **Falla, no se salta, si no hay node.** Un skip se ve verde, y esta prueba
    afirma la propiedad clinica de la tarea: cada respuesta en SU clave. Quien
    toque este workflow tiene node, porque n8n corre sobre node.
    """
    node = shutil.which("node")
    assert node, ("hace falta node para ejecutar el jsCode del workflow: "
                  "instala Node.js, o corre `node tests/decidir.mjs` a mano")
    arnes = pathlib.Path(__file__).resolve().parent / "decidir.mjs"
    assert arnes.exists(), arnes
    r = subprocess.run([node, str(arnes)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-2000:]
    assert "TODO VERDE" in r.stdout, r.stdout[-2000:]


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
    # Si algo falla se dice el nodo o lo que se busco, nunca lo que se
    # encontro: cada comprobacion se reduce ANTES a un booleano, porque pytest
    # enseña lo que compara, y lo que imprime una prueba tambien se puede
    # publicar.
    # Las credenciales se referencian por id y nombre y nada mas: sus valores
    # viven en n8n.
    con_de_mas = [f"{nodo['name']} ({tipo})"
                  for nodo in flujo["nodes"]
                  for tipo, cred in (nodo.get("credentials") or {}).items()
                  if not set(cred) <= {"id", "name"}]
    solo_id_y_nombre = not con_de_mas
    assert solo_id_y_nombre, f"credenciales con algo mas que id y nombre: {con_de_mas}"
    texto = json.dumps(flujo)
    # Un token de bot de Telegram tiene forma reconocible: <id>:<35 chars>. Se
    # busca la FORMA y no la palabra «token», que aparece legitimamente en los
    # comentarios del flujo al explicar el secret_token del §4.2.
    parece_un_token = re.search(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b", texto) is not None
    assert not parece_un_token, "algo con la forma de un token de bot de Telegram"
    presentes = [s for s in ("accessToken", "\"password\"") if s in texto]
    ninguno = not presentes
    assert ninguno, f"el JSON lleva {presentes}"


def test_solo_se_usa_la_credencial_del_bot_del_paciente():
    """D9 y la regla dura 2: reutilizar una credencial de Telegram del cliente
    le robaria el webhook a un bot suyo y lo dejaria mudo sin error visible."""
    con_telegram = [(n["name"], c["id"])
                    for n in _flujo()["nodes"]
                    for t, c in (n.get("credentials") or {}).items()
                    if t == "telegramApi"]
    # El marcador (SP5 §6.1). Si falla se dicen los nodos y no la credencial
    # que llevan: lo que imprime una prueba tambien se puede publicar.
    con_otra = [nodo for nodo, c in con_telegram if c != "CRED_TELEGRAM_PACIENTE"]
    solo_la_suya = bool(con_telegram) and not con_otra
    assert solo_la_suya, con_otra


def test_el_workflow_no_guarda_los_datos_de_ejecucion():
    """§5.4: n8n guarda las entradas y salidas de cada nodo en la base de
    n8n, que es DEL CLIENTE. Ahi irian las respuestas del cuestionario."""
    ajustes = _flujo().get("settings", {})
    assert ajustes.get("saveDataSuccessExecution") == "none"
    assert ajustes.get("saveDataErrorExecution") == "none"
    assert ajustes.get("saveManualExecutions") is False
