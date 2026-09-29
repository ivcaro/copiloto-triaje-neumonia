# -*- coding: utf-8 -*-
"""El workflow de mantenimiento: la limpieza diaria y los avisos del §16.

Tres mitades, y ninguna necesita el VPS:

- Pruebas de MODULO sobre el JSON exportado: lo que tiene que seguir siendo
  verdad aunque alguien edite el workflow en n8n y lo vuelva a exportar. La mas
  importante es que el nodo de limpieza contenga `bd/limpieza.sql` **sin una
  linea de mas**: el fichero esta probado contra una PostgreSQL real en
  `test_esquema_bd.py`, y una copia divergente dentro del workflow dejaria esa
  prueba vigilando un texto que ya no es el que corre.

- Las CONSULTAS del workflow contra una PostgreSQL de verdad, desechable, como
  en `test_esquema_bd.py`. Aqui vive la comprobacion que pide el brief -meter un
  cuestionario caducado y ver que desaparece- y la decision de diseno del
  denominador de la tasa de placas, que se mide en vez de razonarse.

- El `jsCode` de `Evaluar` ejecutado de verdad, en `tests/mantenimiento.mjs`:
  ahi se comprueba el TEXTO del aviso y la regla de cuando se calla, que es lo
  que de verdad se entrega.

El export versionado lleva MARCADORES en vez de los valores de la instancia
-la URL de n8n y los ids y nombres de las credenciales (spec de SP5 §6.1)-,
asi que ya no es identico byte a byte al desplegado: entre uno y otro media
`scripts/marcadores_n8n.py`, que se prueba en `test_marcadores_n8n.py`.
"""
import json
import pathlib
import shutil
import subprocess
import time
import uuid

import psycopg
import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
FLUJO = RAIZ / "n8n" / "copiloto-mantenimiento.json"
LIMPIEZA = RAIZ / "bd" / "limpieza.sql"

# Los marcadores de las credenciales (spec de SP5 §6.1), y no sus ids en la
# instancia. Escritos a mano aqui para que sean un testigo independiente: si
# alguien versiona un export con los ids reales o con otra credencial, se ve.
CRED_BD = "CRED_POSTGRES_COPILOTO"
CRED_AVISOS = "CRED_TELEGRAM_AVISOS"

# Las comprobaciones del §16, por el nodo que las mide. La lista esta aqui y no
# se deduce del JSON: si alguien borra un nodo, la prueba falla en vez de
# adaptarse.
NODOS_DE_COMPROBACION = [
    "Limpieza",
    "Base de datos viva",
    "Salud del copiloto",
    "Placas rechazadas 7 dias",
    "Caducados sin borrar",
    "Webhook del paciente",
    "Webhook del profesional",
]

CADENA = [
    "Cada dia a las 06:45", "Configuracion", "Limpieza", "Base de datos viva",
    "Salud del copiloto", "Placas rechazadas 7 dias", "Caducados sin borrar",
    "Webhook del paciente", "Webhook del profesional", "Evaluar",
    "Hay algo que avisar?", "Avisar al equipo",
]


@pytest.fixture(scope="module")
def flujo():
    return json.loads(FLUJO.read_text(encoding="utf-8"))


def nodo(flujo, nombre):
    for n in flujo["nodes"]:
        if n["name"] == nombre:
            return n
    raise AssertionError(f"el workflow no tiene un nodo «{nombre}»")


def consultas_sql(flujo):
    return {n["name"]: n["parameters"]["query"] for n in flujo["nodes"]
            if n["type"] == "n8n-nodes-base.postgres"}


# --------------------------------------------------------------------------
# Modulo: el JSON
# --------------------------------------------------------------------------
def test_es_un_workflow_nuevo_con_el_prefijo_y_sin_superficie_publica(flujo):
    """Restriccion global: el workflow es NUEVO y lleva el prefijo. Y una que no
    esta escrita pero se deduce del §4.2: el mantenimiento no necesita una URL
    publica, asi que no tiene ninguna. Cada webhook mas es una puerta mas en el
    nginx del cliente."""
    assert flujo["name"] == "\U0001fa7a Copiloto Triaje: Mantenimiento"
    tipos = [n["type"] for n in flujo["nodes"]]
    assert "n8n-nodes-base.webhook" not in tipos, tipos
    assert "n8n-nodes-base.telegramTrigger" not in tipos, tipos
    assert tipos.count("n8n-nodes-base.scheduleTrigger") == 1, tipos
    assert [n["name"] for n in flujo["nodes"]] == CADENA


def test_la_limpieza_es_el_fichero_del_repositorio_sin_una_linea_de_mas(flujo):
    """El brief lo dice: el workflow EJECUTA bd/limpieza.sql, no lo reescribe. Un
    nodo de n8n no puede leer un fichero, asi que el SQL vive copiado dentro del
    JSON, y una copia sin vigilar es una copia que se queda atras: `limpieza.sql`
    esta probado contra una PostgreSQL real, y si el workflow ejecutara otra cosa
    esas pruebas estarian mirando a otro lado.

    Solo se normalizan los saltos de linea: el fichero del repositorio es CRLF y
    las cadenas del JSON exportado usan \\n, como los otros dos workflows."""
    del_fichero = LIMPIEZA.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert nodo(flujo, "Limpieza")["parameters"]["query"] == del_fichero


def test_ningun_sql_del_mantenimiento_toca_consultas(flujo):
    """`consultas` es el registro permanente del §5.1: sin el no hay validacion
    clinica en H7 ni dashboard. El mantenimiento lo LEE para medir la tasa de
    rechazos y no lo escribe ni lo borra jamas."""
    for nombre, sql in consultas_sql(flujo).items():
        sin_comentarios = "\n".join(
            l for l in sql.splitlines() if not l.strip().startswith("--"))
        minus = sin_comentarios.lower()
        for verbo in ("delete from consultas", "update consultas",
                      "insert into consultas", "truncate", "drop ", "alter "):
            assert verbo not in minus, (nombre, verbo)


def test_el_mantenimiento_no_lee_ni_un_dato_de_paciente(flujo):
    """§5.4: cuanto menos dato de paciente pase por un nodo de n8n, menos hay que
    confiar en la retencion de la base del cliente. El mantenimiento vive de
    recuentos: ninguna consulta trae respuestas, signos, sintomas, un codigo
    seudonimo ni un chat_id."""
    prohibidas = ("respuestas", "sintomas", "signos", "chat_id",
                  "profesionales", "generar_codigo")
    for nombre, sql in consultas_sql(flujo).items():
        if nombre == "Limpieza":       # los DELETE nombran columnas por fuerza
            continue
        minus = sql.lower()
        for columna in prohibidas:
            assert columna not in minus, (nombre, columna)
    # El `codigo` que si aparece es el CODIGO DE ERROR del §9 sacado con
    # split_part, no el codigo seudonimo del paciente: lo que sale de la base son
    # los nombres de columna que ata
    # `test_las_consultas_del_mantenimiento_dan_UNA_fila_y_numeros`.
    assert "split_part(error, ':', 1)" in nodo(
        flujo, "Placas rechazadas 7 dias")["parameters"]["query"]


def test_cada_comprobacion_sobrevive_a_su_propio_fallo(flujo):
    """La trampa de todo workflow de vigilancia: si el nodo que comprueba la base
    de datos ABORTA cuando la base no esta, la ejecucion muere ahi y no hay
    aviso. Justo el dia que hacia falta.

    Tres ajustes, y los tres hacen falta:
      - `onError: continueRegularOutput`, para que el fallo viaje como dato.
      - `alwaysOutputData`, para que un nodo sin filas -los DELETE de la
        limpieza no devuelven ninguna- no corte la cadena.
      - `executeOnce`, para que si un nodo devuelve mas de un elemento no se
        multipliquen las comprobaciones de aguas abajo, ni los avisos."""
    for nombre in NODOS_DE_COMPROBACION:
        n = nodo(flujo, nombre)
        assert n.get("onError") == "continueRegularOutput", nombre
        assert n.get("alwaysOutputData") is True, nombre
        assert n.get("executeOnce") is True, nombre
    assert nodo(flujo, "Evaluar").get("executeOnce") is True
    assert nodo(flujo, "Avisar al equipo").get("executeOnce") is True


def test_la_cadena_es_lineal_y_los_caducados_se_cuentan_DESPUES_de_limpiar(flujo):
    """El orden no es estetico: contar cuestionarios caducados antes de la
    limpieza mediria que hay datos por borrar; contarlos despues mide que la
    limpieza FALLO, que es la comprobacion del §16."""
    for origen, destino in zip(CADENA, CADENA[1:]):
        salidas = flujo["connections"][origen]["main"][0]
        assert [c["node"] for c in salidas] == [destino], origen
    # Y la rama falsa del IF no lleva a ningun sitio: el dia normal, silencio.
    assert len(flujo["connections"]["Hay algo que avisar?"]["main"]) == 1


def test_las_sondas_de_webhook_no_llevan_el_secreto_ni_disparan_los_bots(flujo):
    """Las dos sondas comprueban que el webhook de cada bot sigue registrado, y lo
    hacen SIN el `secret_token`: lo que se espera es justamente el 403. Si
    llevaran el secreto, cada dia meterian un update falso en el flujo del bot y
    ensuciarian `cuestionarios_iniciados`, que es una metrica del dashboard."""
    for nombre, ruta in (("Webhook del paciente", "copiloto-paciente"),
                         ("Webhook del profesional", "copiloto-profesional")):
        p = nodo(flujo, nombre)["parameters"]
        # si falla se dice la sonda y no la URL que lleva
        al_marcador = p["url"] == f"https://n8n.ejemplo.test/webhook/{ruta}"
        assert al_marcador, nombre
        assert p["method"] == "POST"
        assert not p.get("sendHeaders"), nombre
        assert "authentication" not in p, nombre
        # `neverError` para que un 403 o un 404 lleguen como dato y no como
        # fallo de nodo, que es lo que permite distinguirlos.
        assert p["options"]["response"]["response"]["neverError"] is True
        assert p["options"]["response"]["response"]["fullResponse"] is True
        assert p["options"]["timeout"] == 10000


def test_el_copiloto_se_comprueba_donde_lo_llama_el_bot(flujo):
    """Mismo destino que usa el flujo del profesional: si el nombre del servicio
    cambiara, esta comprobacion tiene que romperse igual que el bot."""
    p = nodo(flujo, "Salud del copiloto")["parameters"]
    assert p["url"] == "http://copiloto-mcp:8000/salud"
    assert p["method"] == "GET"
    assert p["options"]["timeout"] == 10000
    profesional = json.loads(
        (RAIZ / "n8n" / "copiloto-profesional.json").read_text(encoding="utf-8"))
    llamada = nodo(profesional, "Llamar al copiloto")["parameters"]["url"]
    assert llamada.startswith("http://copiloto-mcp:8000/")


def test_no_hay_ningun_secreto_ni_ningun_chat_id_en_el_repositorio(flujo):
    """Restriccion global: ningun secreto va al repositorio. El token sale de la
    credencial, y el chat del equipo se rellena en n8n -un chat_id es el
    identificador de una persona real-."""
    crudo = FLUJO.read_text(encoding="utf-8")
    import re
    # Las tres, sobre un booleano: si fallan, pytest no enseña lo que caso
    # (el token), el chat_id que lleve la configuracion ni un `chatId` escrito
    # a mano en el nodo que avisa.
    parece_un_token = re.search(r"\d{8,12}:[A-Za-z0-9_-]{30,}", crudo) is not None
    assert not parece_un_token, "parece un token"
    config = nodo(flujo, "Configuracion")["parameters"]["assignments"]["assignments"]
    assert [a["name"] for a in config] == ["chat_equipo"]
    vacio = config[0]["value"] == ""
    assert vacio, "el chat del equipo no se versiona"
    lee_la_configuracion = (nodo(flujo, "Avisar al equipo")["parameters"]["chatId"]
                            == "={{ $('Configuracion').first().json.chat_equipo }}")
    assert lee_la_configuracion, ("el chatId de «Avisar al equipo» no es la "
                                  "expresion que lee `chat_equipo` de Configuracion")


def test_las_credenciales_son_las_de_sp3(flujo):
    """§12 y la regla dura: no se toca ninguna credencial del cliente. Y los
    avisos NO salen por uno de los dos bots de produccion: van por el bot de
    pruebas, para que el canal del aviso no dependa del token que a veces hay que
    revocar, y para que no se intercalen en la conversacion clinica."""
    usadas = {}
    for n in flujo["nodes"]:
        for tipo, c in (n.get("credentials") or {}).items():
            usadas.setdefault(tipo, set()).add(c["id"])
    # si falla se dicen los tipos de credencial y cuantas hay de cada uno, no cuales
    las_de_sp3 = usadas == {"postgres": {CRED_BD}, "telegramApi": {CRED_AVISOS}}
    assert las_de_sp3, {tipo: len(ids) for tipo, ids in usadas.items()}


def test_el_aviso_va_en_texto_plano(flujo):
    """Sin parse_mode, como el resto del sistema. El texto del aviso lleva
    comandos con acentos graves, guiones bajos y porcentajes: con MarkdownV2
    cualquiera de ellos deja el mensaje sin enviar, y un aviso que no llega es
    peor que uno sin negritas."""
    p = nodo(flujo, "Avisar al equipo")["parameters"]
    assert "parse_mode" not in json.dumps(p)
    assert p["additionalFields"] == {"appendAttribution": False}


def test_el_disparador_es_diario_y_recupera_la_corrida_perdida(flujo):
    """Diario, como pide el brief. Y `coalesce`: si n8n estuvo caido a las 06:45,
    la corrida se recupera al volver en vez de saltarse la limpieza del dia."""
    p = nodo(flujo, "Cada dia a las 06:45")["parameters"]
    assert p["rule"]["interval"] == [{"field": "days", "triggerAtHour": 6,
                                     "triggerAtMinute": 45}]
    assert p["misfirePolicy"] == "coalesce"


def test_las_ejecuciones_guardan_el_error_pero_no_los_exitos(flujo):
    """Los dos bots llevan las dos en `none` porque sus ejecuciones arrastran el
    DICOM y las respuestas del paciente a la base de n8n del cliente (§5.4). Por
    el mantenimiento no pasa ni un dato de paciente -lo ata
    `test_el_mantenimiento_no_lee_ni_un_dato_de_paciente`-, y cuando una corrida
    falla su ejecucion es el UNICO rastro que queda, porque el aviso es
    justamente lo que no pudo salir.

    Es una EXCEPCION DECLARADA y no un descuido: esta escrita, con este mismo
    porque, en el §16 del spec y en el §5 del manual de operacion."""
    s = flujo["settings"]
    assert s["saveDataErrorExecution"] == "all"
    assert s["saveDataSuccessExecution"] == "none"
    assert s["timezone"] == "America/Guayaquil"
    assert s["executionOrder"] == "v1"


def test_los_dos_bots_siguen_sin_tocarse():
    """Restriccion global 1. Sus exports siguen siendo los de las tareas 5 y 6."""
    for fichero, nombre, cuantos in (
            ("copiloto-paciente.json",
             "\U0001fa7a Copiloto Triaje: Paciente (Telegram)", 24),
            ("copiloto-profesional.json",
             "\U0001fa7a Copiloto Triaje: Profesional (Telegram)", 25)):
        f = json.loads((RAIZ / "n8n" / fichero).read_text(encoding="utf-8"))
        assert f["name"] == nombre
        assert len(f["nodes"]) == cuantos, (fichero, len(f["nodes"]))


def test_el_texto_del_aviso_y_la_regla_de_silencio_hacen_lo_que_dicen():
    """Ejecuta el jsCode REAL de `Evaluar` con node.

    Lo que se entrega en esta tarea no es «un workflow que comprueba ocho cosas»:
    es el texto que alguien lee cuando algo se rompe y la regla de cuando se
    calla. Ninguna de las dos se puede afirmar leyendo el JSON, y la mitad de los
    estados -base caida, webhook desregistrado, copiloto mudo- no se pueden
    provocar contra el VPS sin romper el sistema de verdad.

    **Falla, no se salta, si no hay node.** Un skip se ve verde, y quien toque
    este workflow tiene node: n8n corre sobre node.
    """
    node = shutil.which("node")
    assert node, ("hace falta node para ejecutar el jsCode del workflow: "
                  "instala Node.js, o corre `node tests/mantenimiento.mjs`")
    arnes = pathlib.Path(__file__).resolve().parent / "mantenimiento.mjs"
    assert arnes.exists(), arnes
    r = subprocess.run([node, str(arnes)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    assert r.returncode == 0, r.stdout[-6000:] + r.stderr[-2000:]
    assert "TODO VERDE" in r.stdout, r.stdout[-2000:]


# --------------------------------------------------------------------------
# Las consultas, contra una PostgreSQL de verdad
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def conexion():
    """Una PostgreSQL desechable con el esquema de SP3, como en
    `test_esquema_bd.py`. Puerto distinto para no chocar con el de ese modulo."""
    if not shutil.which("docker"):
        pytest.skip("sin docker no hay PostgreSQL desechable")
    nombre = f"copiloto-bd-mantenimiento-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", nombre,
         "-e", "POSTGRES_PASSWORD=prueba", "-p", "15434:5432",
         "postgres:16-alpine"], check=True, capture_output=True)
    try:
        dsn = "postgresql://postgres:prueba@127.0.0.1:15434/postgres"
        for _ in range(60):
            try:
                with psycopg.connect(dsn, connect_timeout=2):
                    break
            except psycopg.OperationalError:
                time.sleep(1)
        else:
            pytest.fail("la PostgreSQL de prueba no arranco")
        with psycopg.connect(dsn, autocommit=True) as c:
            c.execute((RAIZ / "bd" / "esquema.sql").read_text(encoding="utf-8"))
            yield c
    finally:
        subprocess.run(["docker", "rm", "-f", nombre], capture_output=True)


@pytest.fixture
def limpio(conexion):
    conexion.execute("TRUNCATE cuestionarios, consultas, sesiones_paciente, "
                     "sesiones_profesional, limite_paciente, "
                     "cuestionarios_iniciados")
    return conexion


def sql(nombre):
    f = json.loads(FLUJO.read_text(encoding="utf-8"))
    return nodo(f, nombre)["parameters"]["query"]


def meter_consulta(c, codigo_error=None, dias=0, con_resultado=False):
    """Una fila de `consultas` como las que escribe el bot del profesional: el
    error guarda «codigo: texto crudo del servidor», no el codigo a secas."""
    error = f"{codigo_error}: texto crudo del servidor" if codigo_error else None
    c.execute(
        "INSERT INTO consultas (codigo, chat_id, resultado, error, creado_en) "
        "VALUES ('ABC123', 7, %s, %s, now() - make_interval(days => %s))",
        ('{"clasificacion": "opacidad_probable"}' if con_resultado else None,
         error, dias))


def test_las_consultas_del_mantenimiento_dan_UNA_fila_y_numeros(limpio):
    """Dos propiedades de las que depende todo lo de arriba:

    - UNA sola fila. Si una consulta devolviera varias, cada nodo de aguas abajo
      correria una vez por fila y el aviso saldria repetido tantas veces.
    - NUMEROS, no cadenas. `count(*)` es bigint y el nodo de n8n lo entrega como
      texto; sin los `::int`, la tasa se calcularia dividiendo cadenas.
    """
    columnas = {}
    for nombre in ("Base de datos viva", "Placas rechazadas 7 dias",
                   "Caducados sin borrar"):
        cur = limpio.execute(sql(nombre))
        columnas[nombre] = [c.name for c in cur.description]
        filas = cur.fetchall()
        assert len(filas) == 1, nombre
        for valor in filas[0]:
            assert isinstance(valor, (int, dict)), (nombre, type(valor))
    # Y lo que SALE de la base son estas columnas y nada mas: recuentos y codigos
    # de error. Ni un dato de paciente, ni un codigo seudonimo, ni un chat_id.
    assert columnas == {
        "Base de datos viva": ["uno"],
        "Placas rechazadas 7 dias": ["consultas", "intentos_placa",
                                     "dicom_invalido", "envio_como_foto",
                                     "por_codigo"],
        "Caducados sin borrar": ["caducados"],
    }, columnas


def test_la_tasa_de_placas_agrupa_por_codigo_con_split_part(limpio):
    """El §15 y el §16: la columna guarda «codigo: texto», asi que comparar la
    columna entera con 'dicom_invalido' daria 0 siempre y la comprobacion seria
    decorativa."""
    for _ in range(4):
        meter_consulta(limpio, "dicom_invalido")
    for _ in range(3):
        meter_consulta(limpio, "envio_como_foto")
    for _ in range(5):
        meter_consulta(limpio, con_resultado=True)
    meter_consulta(limpio, "dicom_invalido", dias=8)   # fuera de la ventana
    fila = limpio.execute(sql("Placas rechazadas 7 dias")).fetchone()
    consultas, intentos, dicom, fotos, por_codigo = fila
    assert consultas == 12, fila
    assert intentos == 12, fila
    assert dicom == 4, fila
    assert fotos == 3, fila
    assert por_codigo == {"dicom_invalido": 4, "envio_como_foto": 3}, por_codigo


def test_la_tasa_no_se_diluye_con_los_rechazos_de_antes_de_la_placa(limpio):
    """DECISION MEDIDA, y una desviacion deliberada de la letra del §16, que dice
    «la tasa de dicom_invalido de los ultimos 7 dias» sin decir de que.

    `consultas` guarda tambien los rechazos que ocurren ANTES de que haya placa
    -`no_autorizado` de la puerta de D6, `codigo_invalido`-. Si entran en el
    denominador, una racha de intentos no autorizados hunde el porcentaje sin
    que ninguna placa haya mejorado: aqui, de 33,3 % a 6,7 %, por debajo del
    umbral del 20 %. El aviso se apagaria justo cuando mas hace falta."""
    for _ in range(4):
        meter_consulta(limpio, "dicom_invalido")
    for _ in range(8):
        meter_consulta(limpio, con_resultado=True)
    antes = limpio.execute(sql("Placas rechazadas 7 dias")).fetchone()
    assert (antes[2], antes[1]) == (4, 12)

    for _ in range(50):
        meter_consulta(limpio, "no_autorizado")
    for _ in range(10):
        meter_consulta(limpio, "codigo_invalido")
    despues = limpio.execute(sql("Placas rechazadas 7 dias")).fetchone()
    assert (despues[2], despues[1]) == (4, 12), despues
    assert despues[0] == 72, despues          # y el total sigue contandose
    # Con el denominador ingenuo la tasa se habria caido asi:
    assert round(4 / 72, 3) == 0.056
    assert round(4 / 12, 3) == 0.333


def test_los_caducados_se_cuentan_con_una_hora_de_margen(limpio):
    """El margen no es pereza: entre el DELETE de la limpieza y esta consulta
    pasan milisegundos, y un cuestionario puede caducar justo en ese hueco. Con
    `< now()` eso seria un aviso falso, y un aviso falso al dia es como se deja
    de leer un aviso."""
    limpio.execute("INSERT INTO cuestionarios (codigo, respuestas, "
                   "consentido_en, expira_en) VALUES ('RECIEN', '{}', now(), "
                   "now() - interval '30 minutes')")
    assert limpio.execute(sql("Caducados sin borrar")).fetchone()[0] == 0
    limpio.execute("INSERT INTO cuestionarios (codigo, respuestas, "
                   "consentido_en, expira_en) VALUES ('VIEJO', '{}', now(), "
                   "now() - interval '2 hours')")
    assert limpio.execute(sql("Caducados sin borrar")).fetchone()[0] == 1


def test_el_paso_2_del_brief_un_cuestionario_caducado_desaparece(limpio):
    """El paso 2 del brief, con el SQL QUE LLEVA EL NODO y contra una PostgreSQL
    real: se mete un cuestionario caducado, se ejecuta la limpieza del workflow,
    y tiene que desaparecer. Y detras, la comprobacion del §16 tiene que dar 0:
    las dos consultas en el orden en el que las ejecuta el workflow.

    De paso queda probado que la cadena de sentencias con BEGIN/COMMIT se ejecuta
    entera tal como esta en el nodo."""
    limpio.execute("INSERT INTO cuestionarios (codigo, respuestas, "
                   "consentido_en, creado_en, expira_en) VALUES "
                   "('CADUCA', '{\"t1\": \"si\"}', now() - interval '8 days', "
                   "now() - interval '8 days', now() - interval '1 day')")
    limpio.execute("INSERT INTO cuestionarios (codigo, respuestas, "
                   "consentido_en, expira_en) VALUES ('VIVO', '{}', now(), "
                   "now() + interval '6 days')")
    limpio.execute("INSERT INTO sesiones_paciente (chat_id, paso, "
                   "actualizado_en) VALUES (11, 3, now() - interval '30 hours')")
    limpio.execute("INSERT INTO sesiones_profesional (chat_id, paso, "
                   "actualizado_en) VALUES (12, 2, now() - interval '30 hours')")
    limpio.execute("INSERT INTO sesiones_paciente (chat_id, paso) "
                   "VALUES (13, 1)")
    limpio.execute("INSERT INTO limite_paciente (chat_id, dia, cuantos) VALUES "
                   "(14, (now() AT TIME ZONE 'America/Guayaquil')::date - 5, 5)")
    meter_consulta(limpio, "dicom_invalido", dias=30)

    limpio.execute(sql("Limpieza"))

    vivos = [f[0] for f in limpio.execute(
        "SELECT codigo FROM cuestionarios ORDER BY codigo").fetchall()]
    assert vivos == ["VIVO"], vivos
    assert limpio.execute("SELECT count(*) FROM sesiones_paciente").fetchone()[0] == 1
    assert limpio.execute("SELECT count(*) FROM sesiones_profesional").fetchone()[0] == 0
    assert limpio.execute("SELECT count(*) FROM limite_paciente").fetchone()[0] == 0
    # `consultas` es el registro permanente: la limpieza no lo toca ni cuando la
    # fila tiene 30 dias.
    assert limpio.execute("SELECT count(*) FROM consultas").fetchone()[0] == 1
    assert limpio.execute(sql("Caducados sin borrar")).fetchone()[0] == 0


# --------------------------------------------------------------------------
# La mitad de la sexta comprobacion que no cabe en n8n
# --------------------------------------------------------------------------
# `pruebas/verificar_webhooks.py` mira el lado de TELEGRAM: si Telegram dejo de
# apuntar a nuestra URL, o si el `secret_token` de los dos lados dejo de
# coincidir, desde fuera todo se ve igual y el bot esta mudo. No cabe en el
# workflow porque el token va en la RUTA de la URL de la API de Telegram y una
# credencial de n8n no puede escribir en la ruta (ver la cabecera del script).
# Lo que se prueba aqui es el diagnostico, que es la parte que no necesita red.
import sys  # noqa: E402

sys.path.insert(0, str(RAIZ / "pruebas"))
import verificar_webhooks as vw  # noqa: E402

# La base de n8n de estas pruebas es un marcador, y la fija la prueba: el script
# ya no trae ninguna por defecto (`N8N_URL` es obligatoria para correrlo), y el
# diagnostico no puede depender de lo que haya en el entorno de quien corre la
# suite.
BASE = "https://n8n.ejemplo.test"
BIEN = {"url": f"{BASE}/webhook/copiloto-paciente",
        "pending_update_count": 0}


@pytest.fixture(autouse=True)
def _base_de_n8n_fija(monkeypatch):
    """`BASE_N8N` se calcula al importar el script, con el `N8N_URL` de ese
    momento. Aqui se pisa en cada prueba del fichero, y al acabar vuelve a ser
    la que era."""
    monkeypatch.setattr(vw, "BASE_N8N", BASE)


def diagnosticar(info, anterior=None):
    return vw.diagnosticar("paciente", "copiloto-paciente", "FLUJO", info,
                           anterior)


def test_un_webhook_correcto_no_da_ningun_problema():
    assert diagnosticar(BIEN) == []


def test_sin_webhook_registrado_lo_dice_y_manda_al_manual():
    p = diagnosticar({"url": "", "pending_update_count": 0})
    assert len(p) == 1
    assert "mudo" in p[0] and "§4 del manual" in p[0]


def test_el_webhook_del_otro_bot_es_el_error_silencioso_del_manual():
    """Pegar la ruta del otro bot: Telegram contesta «Webhook was set» igual y el
    bot queda mudo. Es el fallo que ya paso una vez."""
    p = diagnosticar({"url": f"{BASE}/webhook/copiloto-profesional",
                      "pending_update_count": 0})
    assert len(p) == 1
    assert "copiloto-paciente" in p[0] and "el OTRO bot" in p[0]


def test_un_403_en_last_error_apunta_al_secret_token():
    p = diagnosticar(dict(BIEN, last_error_message="Wrong response from the "
                          "webhook: 403 Forbidden", last_error_date=1758800000))
    assert len(p) == 1
    assert "secret_token" in p[0] and "setWebhook" in p[0]


def test_un_404_en_last_error_apunta_al_workflow_desactivado():
    p = diagnosticar(dict(BIEN, last_error_message="Wrong response from the "
                          "webhook: 404 Not Found", last_error_date=1758800000))
    assert len(p) == 1
    assert "desactivado" in p[0] and "FLUJO" in p[0]


def test_la_cola_pendiente_solo_avisa_cuando_CRECE():
    """Uno o dos mensajes en vuelo son normales; lo que significa algo es que
    crezcan entre dos lecturas, que es lo que pide el añadido del brief."""
    assert diagnosticar(dict(BIEN, pending_update_count=3), anterior=3) == []
    assert diagnosticar(dict(BIEN, pending_update_count=3), anterior=None) == []
    p = diagnosticar(dict(BIEN, pending_update_count=9), anterior=3)
    assert len(p) == 1 and "9" in p[0] and "3" in p[0]


def test_el_aviso_de_la_tarea_programada_lleva_los_problemas_y_no_el_token(monkeypatch):
    """La tarea programada del §5 del manual solo sirve si el resultado LLEGA a
    alguien: un script diario que escribe en un log es el mismo silencio que el
    workflow existe para romper. Se comprueba que el mensaje lleva los problemas
    con su «Qué hacer», y que el token viaja en la URL de la API pero NUNCA en el
    cuerpo del mensaje que se manda."""
    import urllib.parse

    enviados = {}

    def falso(pet, timeout=0):
        enviados["url"] = pet.full_url
        enviados["cuerpo"] = dict(urllib.parse.parse_qsl(pet.data.decode()))

        class R:
            def read(self_inner):
                return b'{"ok":true,"result":{}}'

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False
        return R()

    monkeypatch.setattr(vw.urllib.request, "urlopen", falso)
    problemas = diagnosticar({"url": "", "pending_update_count": 0})
    texto = vw.mensaje_para_telegram(problemas)
    ok, detalle = vw.avisar_por_telegram("T0K3N", "987", texto)
    assert ok is True, detalle
    assert enviados["url"] == "https://api.telegram.org/botT0K3N/sendMessage"
    assert enviados["cuerpo"]["chat_id"] == "987"
    assert "el webhook de Telegram no está como debe" in enviados["cuerpo"]["text"]
    assert "mudo" in enviados["cuerpo"]["text"]
    assert "Qué hacer" in enviados["cuerpo"]["text"]
    assert "T0K3N" not in enviados["cuerpo"]["text"]
    assert len(enviados["cuerpo"]["text"]) <= 4096


def test_un_token_revocado_se_distingue_de_un_problema_de_url(monkeypatch):
    """§4 del manual: un 404 de la API de Telegram no es la URL, es el token. Y un
    401 es un token revocado. Si el mensaje confunde las dos cosas, manda a
    mirar donde no es."""
    import io
    import urllib.error

    def falso(url, timeout=0):
        codigo = 401 if "bot401" in url else 404
        cuerpo = json.dumps({"ok": False, "error_code": codigo,
                             "description": "Unauthorized"}).encode()
        raise urllib.error.HTTPError(url, codigo, "no", {}, io.BytesIO(cuerpo))

    monkeypatch.setattr(vw.urllib.request, "urlopen", falso)
    ok, mensaje = vw.pedir_api("401fake", "getWebhookInfo")
    assert ok is False and "revocado" in mensaje and "BotFather" in mensaje
    ok, mensaje = vw.pedir_api("otro", "getWebhookInfo")
    assert ok is False and "no es la URL, es el token" in mensaje


# --------------------------------------------------------------------------
# `N8N_URL` no tiene valor por defecto
# --------------------------------------------------------------------------
# El script no trae la URL de ningun n8n: la pone quien lo corre. Pero este
# fichero lo importa entero, asi que sin la variable tiene que seguir
# importandose; el que se niega a trabajar sin ella es `main()`.
def _script_recien_importado():
    """El script cargado otra vez, con el entorno de AHORA. `vw` se importo al
    coleccionar, con el entorno de entonces."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "verificar_webhooks_recien_importado",
        RAIZ / "pruebas" / "verificar_webhooks.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _main_que_no_toca_nada(monkeypatch):
    """Deja `main()` sin teclado, sin red y sin memoria: si los busca antes de
    mirar `N8N_URL`, la prueba falla en vez de quedarse esperando un token."""
    def no_se_llama(*a, **k):
        raise AssertionError("main() siguió adelante sin N8N_URL")

    monkeypatch.setattr(vw.getpass, "getpass", no_se_llama)
    monkeypatch.setattr(vw, "pedir_api", no_se_llama)
    monkeypatch.setattr(vw, "_memoria_escribir", no_se_llama)
    for variable in ("TELEGRAM_TOKEN_PACIENTE", "TELEGRAM_TOKEN_PROFESIONAL",
                     "COPILOTO_CHAT_EQUIPO", "TELEGRAM_TOKEN_AVISOS"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(vw, "BASE_N8N", "")
    # y sin el motivo de una `N8N_URL` mal puesta que hubiera al coleccionar
    monkeypatch.setattr(vw, "N8N_URL_MAL_PUESTA", "")


def _canal_de_avisos_falso(monkeypatch):
    """El canal de avisos puesto, y un Telegram que contesta que si. Devuelve
    donde queda lo que `main()` le mande: la URL a la que llamo y el cuerpo."""
    import urllib.parse

    monkeypatch.setenv("COPILOTO_CHAT_EQUIPO", "987")
    monkeypatch.setenv("TELEGRAM_TOKEN_AVISOS", "T0K3N")
    enviados = {}

    def falso(pet, timeout=0):
        enviados["url"] = pet.full_url
        enviados["cuerpo"] = dict(urllib.parse.parse_qsl(pet.data.decode()))

        class R:
            def read(self_inner):
                return b'{"ok":true,"result":{}}'

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False
        return R()

    monkeypatch.setattr(vw.urllib.request, "urlopen", falso)
    return enviados


@pytest.mark.parametrize("valor", [None, "", "   "],
                         ids=["ausente", "vacia", "en-blanco"])
def test_el_script_se_importa_sin_N8N_URL_y_no_trae_ninguna_por_defecto(
        valor, monkeypatch):
    """Vacia o con solo espacios es lo mismo que ausente: si pasara por una
    base, `main()` pediria los tokens y daria los dos webhooks por mal
    apuntados."""
    if valor is None:
        monkeypatch.delenv("N8N_URL", raising=False)
    else:
        monkeypatch.setenv("N8N_URL", valor)
    assert _script_recien_importado().BASE_N8N == ""


def test_el_script_toma_la_base_de_N8N_URL_sin_la_barra_final(monkeypatch):
    monkeypatch.setenv("N8N_URL", "https://otro.ejemplo.test/")
    assert _script_recien_importado().BASE_N8N == "https://otro.ejemplo.test"


def test_el_diagnostico_no_vuelve_a_mirar_el_entorno(monkeypatch):
    """Con `N8N_URL` apuntando a otro sitio, el diagnostico sigue comparando con
    la base del modulo. Es lo que deja correr este fichero en la maquina que
    tiene la variable puesta para las pruebas conducidas."""
    monkeypatch.setenv("N8N_URL", "https://otro.ejemplo.test")
    assert diagnosticar(BIEN) == []
    p = diagnosticar({"url": "https://otro.ejemplo.test/webhook/copiloto-paciente",
                      "pending_update_count": 0})
    assert len(p) == 1 and f"{BASE}/webhook/copiloto-paciente" in p[0]


def test_sin_N8N_URL_main_sale_con_un_mensaje_y_no_pide_ningun_token(
        monkeypatch, capsys):
    _main_que_no_toca_nada(monkeypatch)
    monkeypatch.setattr(vw.urllib.request, "urlopen",
                        lambda *a, **k: pytest.fail("no había a quién avisar"))

    assert vw.main() == 1

    salida = capsys.readouterr().out
    assert "N8N_URL" in salida and "Qué hacer" in salida
    assert "están como deben" not in salida


def test_sin_N8N_URL_la_tarea_programada_avisa_por_telegram(monkeypatch, capsys):
    """La tarea programada que se quede sin la variable no puede callar: es el
    silencio que el script existe para romper. Con el canal de avisos puesto, el
    motivo llega al mismo hilo que los demas, y dice que NO se comprobo nada:
    con el encabezado de siempre, quien lea solo la notificacion iria a
    registrar otra vez un webhook que estaba bien."""
    _main_que_no_toca_nada(monkeypatch)
    enviados = _canal_de_avisos_falso(monkeypatch)

    assert vw.main() == 1

    assert enviados["url"] == "https://api.telegram.org/botT0K3N/sendMessage"
    assert enviados["cuerpo"]["chat_id"] == "987"
    texto = enviados["cuerpo"]["text"]
    assert "N8N_URL" in texto and "T0K3N" not in texto
    assert "los webhooks de Telegram NO se han comprobado" in texto
    assert "no está como debe" not in texto
    assert "aviso por Telegram: enviado." in capsys.readouterr().out


def test_sin_N8N_URL_el_mensaje_dice_donde_se_pone_para_la_tarea_programada():
    """Una tarea programada de Windows no tiene variables propias: la variable
    va en el perfil del usuario que la corre, con `setx`, como dice el paso 2
    del §5 del manual. «En la tarea» mandaba a buscar donde no hay."""
    assert "setx N8N_URL" in vw.SIN_N8N_URL
    assert "§5" in vw.SIN_N8N_URL and "paso 2" in vw.SIN_N8N_URL
    assert "en la tarea." not in vw.SIN_N8N_URL


# Mal puestas, con un host inventado que no sale en ningun mensaje: el mensaje
# no repite el valor (va por Telegram).
N8N_URL_MAL_PUESTAS = [
    "n8n.inventado.test",                                   # sin esquema
    "https://n8n.inventado.test/webhook/copiloto-paciente",  # con una ruta
    '"https://n8n.inventado.test"',                          # entre comillas
    "https://n8n. inventado.test",                           # con un blanco
    "https://alguien@n8n.inventado.test",                    # con usuario
    "/",
]


@pytest.mark.parametrize("valor", N8N_URL_MAL_PUESTAS)
def test_con_N8N_URL_mal_puesta_el_script_se_importa_y_no_la_da_por_buena(
        valor, monkeypatch):
    monkeypatch.setenv("N8N_URL", valor)
    modulo = _script_recien_importado()
    assert modulo.BASE_N8N == ""
    assert modulo.N8N_URL_MAL_PUESTA, "el motivo"
    assert "inventado" not in modulo.N8N_URL_MAL_PUESTA


@pytest.mark.parametrize("valor", N8N_URL_MAL_PUESTAS)
def test_con_N8N_URL_mal_puesta_main_avisa_sin_comprobar_nada(valor, monkeypatch, capsys):
    """Antes daba por mal apuntados los dos webhooks, que estaban bien, y
    mandaba registrarlos en la direccion mal escrita. Ahora sigue el camino de
    la variable ausente, con su propio mensaje: no pide tokens, no toca la
    memoria, avisa diciendo que NO se comprobo nada y devuelve 1."""
    _main_que_no_toca_nada(monkeypatch)
    enviados = _canal_de_avisos_falso(monkeypatch)
    monkeypatch.setenv("N8N_URL", valor)
    modulo = _script_recien_importado()

    def no_se_llama(*a, **k):
        raise AssertionError("main() siguió adelante con N8N_URL mal puesta")

    monkeypatch.setattr(modulo, "pedir_api", no_se_llama)
    monkeypatch.setattr(modulo, "_memoria_escribir", no_se_llama)

    assert modulo.main() == 1

    texto = enviados["cuerpo"]["text"]
    assert "los webhooks de Telegram NO se han comprobado" in texto
    assert "N8N_URL" in texto and "mal puesta" in texto and "Qué hacer" in texto
    assert "Vuelve a registrarlo" not in texto
    salida = capsys.readouterr().out
    assert "mal puesta" in salida and "aviso por Telegram: enviado." in salida
    assert "inventado" not in texto + salida


def test_los_problemas_de_una_lectura_de_verdad_llegan_al_canal_de_avisos(
        monkeypatch, capsys):
    """El final de `main()`: con la base puesta y un webhook mal apuntado, el
    aviso sale. Si esa llamada se perdiera, la tarea programada seguiria
    devolviendo 1 a un log que nadie abre."""
    monkeypatch.setenv("TELEGRAM_TOKEN_PACIENTE", "tok-paciente")
    monkeypatch.setenv("TELEGRAM_TOKEN_PROFESIONAL", "tok-profesional")
    monkeypatch.setattr(
        vw.getpass, "getpass",
        lambda *a, **k: pytest.fail("los tokens estaban en el entorno"))
    # los dos bots entregan en la ruta del profesional: el del paciente esta mal
    lecturas = {"tok-paciente": {"url": f"{BASE}/webhook/copiloto-profesional",
                                 "pending_update_count": 0},
                "tok-profesional": {"url": f"{BASE}/webhook/copiloto-profesional",
                                    "pending_update_count": 2}}
    monkeypatch.setattr(vw, "pedir_api", lambda token, metodo: (True, lecturas[token]))
    monkeypatch.setattr(vw, "_memoria_leer", lambda: {})
    escrita = {}
    monkeypatch.setattr(vw, "_memoria_escribir", escrita.update)
    enviados = _canal_de_avisos_falso(monkeypatch)

    assert vw.main() == 1

    assert escrita == {"paciente": 0, "profesional": 2}
    assert enviados["url"] == "https://api.telegram.org/botT0K3N/sendMessage"
    texto = enviados["cuerpo"]["text"]
    assert "el webhook de Telegram no está como debe" in texto
    assert "el OTRO bot" in texto and "bot del paciente" in texto
    assert "bot del profesional" not in texto
    for secreto in ("tok-paciente", "tok-profesional", "T0K3N"):
        assert secreto not in texto
    salida = capsys.readouterr().out
    assert "1 cosas que arreglar." in salida
    assert "aviso por Telegram: enviado." in salida
