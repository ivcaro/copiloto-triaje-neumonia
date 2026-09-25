# -*- coding: utf-8 -*-
"""Conduce el SQL REAL del flujo del profesional contra una PostgreSQL desechable.

El hermano de `verificar_sql_paciente.py`, y por la misma razon: no sustituye a
las pruebas conducidas de `tests/test_flujo_profesional.py` -no prueba el grafo
de n8n-, sino que prueba lo que no se puede afirmar sin ejecutarlo. Aqui hay dos
cosas que solo se ven corriendo el SQL:

1. **Los tipos dentro del `jsonb`.** Los signos viajan a la consulta como
   literal JSON en base64 y la consulta los pasa por `::jsonb`. Si eso estuviera
   mal, `temperatura_c` entraria como la CADENA "38.2" en vez del numero 38,2, y
   H6 recibiria un jsonb sintacticamente valido con el tipo equivocado. Nadie se
   enteraria hasta calcular la probabilidad previa.

2. **`Registrar` escribe UNA fila y borra la sesion solo cuando toca.** El §9
   tiene once ramas y cada una dice si la conversacion termina; esa columna vive
   en el parametro $5 de una sola consulta, y las CTE que modifican datos no se
   comportan como uno cree hasta que se ejecutan.

**Imita al nodo Postgres de n8n donde importa.** `options.queryReplacement` es
UNA cadena con expresiones; n8n la resuelve y la pasa por `stringToArray`, que
parte por comas, recorta cada trozo **y descarta los vacios**. Un arnes que no
imita esa regla no ve el fallo que en la T5 dejo al paciente sin su codigo.

Uso (hace falta Docker):

    docker run -d --name sp3-verifica-sql-prof -e POSTGRES_PASSWORD=verifica \\
        -e POSTGRES_DB=copiloto -p 15498:5432 postgres:16-alpine
    docker exec -i sp3-verifica-sql-prof psql -U postgres -d copiloto < bd/esquema.sql
    C:/venv-copiloto/Scripts/python.exe pruebas/verificar_sql_profesional.py
    docker rm -f sp3-verifica-sql-prof
"""
import base64
import json
import pathlib
import re
import sys

import psycopg

DSN = "host=127.0.0.1 port=15498 dbname=copiloto user=postgres password=verifica"
DR = 999000010          # el profesional autorizado
DRA = 999000011         # otra profesional, para la prueba de concurrencia
INTRUSO = 999000099
REPO = pathlib.Path(__file__).resolve().parents[1]
FLUJO = json.loads((REPO / "n8n" / "copiloto-profesional.json")
                   .read_text(encoding="utf-8"))
NODOS = {n["name"]: n for n in FLUJO["nodes"]}

fallos = []


def comprobar(etiqueta, ok, detalle=""):
    print(("  OK   " if ok else "  FALLO") + f" {etiqueta}" +
          (f"  {detalle}" if detalle else ""))
    if not ok:
        fallos.append(etiqueta)


def string_to_array(resuelto):
    """`stringToArray` de n8n: parte por comas, recorta, DESCARTA LOS VACIOS."""
    return [t for t in (x.strip() for x in resuelto.split(",")) if t != ""]


def parametros(nombre, ctx):
    """Los parametros que el nodo Postgres pasaria de verdad.

    Si una expresion del nodo no esta en `ctx`, esto revienta: es deliberado,
    para que renombrar un campo en `Decidir` sin actualizar el nodo no pase
    inadvertido.
    """
    crudo = NODOS[nombre]["parameters"].get("options", {}).get("queryReplacement")
    if not crudo:
        return []
    assert crudo.startswith("="), crudo
    resuelto = re.sub(r"\{\{(.*?)\}\}",
                      lambda m: str(ctx[m.group(1).strip()]), crudo[1:])
    return string_to_array(resuelto)


def ejecutar(cur, nombre, ctx):
    consulta = NODOS[nombre]["parameters"]["query"]
    vals = parametros(nombre, ctx)
    referenciados = max((int(m) for m in re.findall(r"\$(\d+)", consulta)),
                        default=0)
    if referenciados != len(vals):
        raise AssertionError(
            f"{nombre}: la consulta referencia ${referenciados} pero n8n pasaria "
            f"{len(vals)} parametros ({vals!r}). Postgres diria "
            f"'there is no parameter ${referenciados}'.")
    sql = re.sub(r"\$(\d+)", r"%(p\1)s", consulta)
    cur.execute(sql, {f"p{i + 1}": v for i, v in enumerate(vals)})
    if cur.description is None:
        return None
    r = cur.fetchone()
    return dict(zip([d.name for d in cur.description], r)) if r else None


CHAT_EXPR = "$('Normalizar update').first().json.chat_id"
NULO = "N"


def cod(texto):
    """La codificacion de `Decidir`: 'T' + base64. Nunca vacia, nunca con comas."""
    return "T" + base64.b64encode(str(texto).encode("utf-8")).decode("ascii")


def ctx_leer(chat):
    return {CHAT_EXPR: chat}


def ctx_abrir(chat, reinicio):
    return {CHAT_EXPR: chat, "$json.reinicio": reinicio}


def ctx_buscar(chat, codigo):
    return {CHAT_EXPR: chat, "$json.codigo_cod": cod(codigo)}


def ctx_signo(chat, clave, literal_json, paso, paso_actual):
    return {CHAT_EXPR: chat, "$json.clave": clave,
            "$json.valor_cod": cod(literal_json), "$json.paso": paso,
            "$json.paso_actual": paso_actual}


def ctx_registrar(chat, resultado, error, ms, termina, registrar):
    return {CHAT_EXPR: chat,
            "$json.resultado_cod": NULO if resultado is None else cod(json.dumps(resultado)),
            "$json.error_cod": NULO if error is None else cod(error),
            "$json.ms": ms, "$json.termina": termina,
            "$json.registrar": registrar}


SINTOMAS = {"fiebre": "si", "tos": "con_flema", "dias_evolucion": "3_a_7",
            "disnea": "no", "dolor_toracico": "si", "asma": "no_se",
            "texto_libre": "me duele, mucho; ' OR 1=1 --"}
# El structuredContent REAL de la placa de la banda contradictoria, medido
# contra el contenedor el 25-sep-2026.
RESULTADO = {"probabilidad_cruda": 0.5649,
             "probabilidad_calibrada": 0.1984732824427481,
             "razon_de_verosimilitud": 0.8702999032570139, "umbral": 0.4258,
             "clasificacion": "opacidad_probable", "edad_paciente": 58,
             "modelo": "efficientnet_b0_320px", "auc_validacion": 0.8827,
             "milisegundos": 42.7}


with psycopg.connect(DSN, autocommit=True) as cx:
    cur = cx.cursor()
    cur.execute("TRUNCATE sesiones_profesional, cuestionarios, consultas,"
                " profesionales")
    cur.execute("INSERT INTO profesionales (chat_id, nombre) VALUES"
                " (%s,'Dr Prueba'), (%s,'Dra Dos')", (DR, DRA))

    print("\n0. el fallo bloqueante de la T5 no puede volver")
    # Asi se mandaria un valor SIN el prefijo: la cadena vacia. `stringToArray`
    # la descarta, la consulta sale con cuatro parametros y Postgres responde
    # `there is no parameter $5`. El arnes lo detecta antes de tocar Postgres.
    crudo = {CHAT_EXPR: DR, "$json.clave": "temperatura_c",
             "$json.valor_cod": "", "$json.paso": 3, "$json.paso_actual": 2}
    try:
        ejecutar(cur, "Guardar signo", crudo)
        comprobar("un parametro vacio se detecta", False, "paso sin protestar")
    except AssertionError as e:
        comprobar("un parametro vacio se detecta antes de tocar Postgres",
                  "there is no parameter $5" in str(e), str(e)[:110])
    # Y con la codificacion de `Decidir` un valor vacio es IMPOSIBLE: 'T' +
    # base64 de la cadena vacia sigue siendo 'T', que no es vacio.
    comprobar("'T' + base64('') no es una cadena vacia", cod("") == "T")
    comprobar("y el base64 nunca lleva comas, que es lo que parte los parametros",
              "," not in cod("38.2") and "," not in cod("true"))

    print("\n1. Leer sesion y permiso: SIEMPRE una fila")
    r = ejecutar(cur, "Leer sesion y permiso", ctx_leer(INTRUSO))
    comprobar("un chat desconocido da fila, con autorizado=False",
              r is not None and r["autorizado"] is False, str(r))
    comprobar("y sin sesion: existe=False, paso=0",
              r["existe"] is False and r["paso"] == 0)
    comprobar("paso vuelve como numero, no cadena", isinstance(r["paso"], int))
    r = ejecutar(cur, "Leer sesion y permiso", ctx_leer(DR))
    comprobar("el profesional de la lista blanca pasa", r["autorizado"] is True)
    cur.execute("UPDATE profesionales SET activo=false WHERE chat_id=%s", (DR,))
    r = ejecutar(cur, "Leer sesion y permiso", ctx_leer(DR))
    comprobar("dado de baja deja de pasar EN EL MENSAJE SIGUIENTE (§7)",
              r["autorizado"] is False, str(r["autorizado"]))
    cur.execute("UPDATE profesionales SET activo=true WHERE chat_id=%s", (DR,))

    print("\n2. Abrir sesion")
    r = ejecutar(cur, "Abrir sesion", ctx_abrir(DR, "N"))
    comprobar("la primera vez nace en el paso 1", r["paso"] == 1, str(r))
    cur.execute("UPDATE sesiones_profesional SET paso=2, codigo='AAAAAA'"
                " WHERE chat_id=%s", (DR,))
    ejecutar(cur, "Guardar signo", ctx_signo(DR, "temperatura_c", "38.2", 3, 2))
    r = ejecutar(cur, "Abrir sesion", ctx_abrir(DR, "N"))
    comprobar("/start a medias NO reinicia (el destructivo es /reiniciar)",
              r["paso"] == 3, str(r))
    fila = cur.execute("SELECT codigo, signos FROM sesiones_profesional"
                       " WHERE chat_id=%s", (DR,)).fetchone()
    comprobar("y no borra el codigo ni los signos ya recogidos",
              fila[0] == "AAAAAA" and fila[1] != {}, str(fila))
    r = ejecutar(cur, "Abrir sesion", ctx_abrir(DR, "S"))
    fila = cur.execute("SELECT paso, codigo, signos FROM sesiones_profesional"
                       " WHERE chat_id=%s", (DR,)).fetchone()
    comprobar("/reiniciar SI borra codigo y signos, y vuelve al paso 1",
              fila == (1, None, {}), str(fila))

    print("\n3. Buscar cuestionario (§7.2: comprobando expira_en)")
    cur.execute("INSERT INTO cuestionarios (codigo, respuestas, consentido_en,"
                " expira_en) VALUES ('K7FM2P', %s, now(), now() + interval"
                " '7 days')", (json.dumps(SINTOMAS),))
    cur.execute("INSERT INTO cuestionarios (codigo, respuestas, consentido_en,"
                " expira_en) VALUES ('CADUC2', %s, now() - interval '9 days',"
                " now() - interval '2 days')", (json.dumps(SINTOMAS),))
    r = ejecutar(cur, "Buscar cuestionario", ctx_buscar(DR, "K7FM2P"))
    comprobar("un codigo vivo se encuentra y no da error",
              r["error_cod"] == "N" and r["codigo"] == "K7FM2P", str(r))
    comprobar("devuelve los sintomas del paciente", r["sintomas"] == SINTOMAS,
              json.dumps(r["sintomas"], ensure_ascii=False))
    comprobar("el texto libre con comas y SQL llega INTACTO",
              r["sintomas"]["texto_libre"] == SINTOMAS["texto_libre"],
              repr(r["sintomas"]["texto_libre"]))
    fila = cur.execute("SELECT paso, codigo FROM sesiones_profesional"
                       " WHERE chat_id=%s", (DR,)).fetchone()
    comprobar("el codigo queda atado a la sesion y el paso avanza al 2",
              fila == (2, "K7FM2P"), str(fila))
    r = ejecutar(cur, "Buscar cuestionario", ctx_buscar(DR, "K7FM2P"))
    comprobar("repetir el codigo cuando ya no se esta en el paso 1 no hace nada",
              r["error_cod"] == "codigo_invalido", str(r))
    ejecutar(cur, "Abrir sesion", ctx_abrir(DR, "S"))
    r = ejecutar(cur, "Buscar cuestionario", ctx_buscar(DR, "CADUC2"))
    comprobar("un codigo CADUCADO da codigo_invalido (§9)",
              r["error_cod"] == "codigo_invalido" and r["codigo"] is None, str(r))
    comprobar("y la sesion se queda en el paso 1, esperando otro codigo",
              cur.execute("SELECT paso FROM sesiones_profesional WHERE"
                          " chat_id=%s", (DR,)).fetchone()[0] == 1)
    r = ejecutar(cur, "Buscar cuestionario", ctx_buscar(DR, "ZZZZZZ"))
    comprobar("un codigo inexistente, igual", r["error_cod"] == "codigo_invalido")
    comprobar("el mismo codigo se puede usar DOS veces (§5.2: no es de un solo"
              " uso)", (ejecutar(cur, "Buscar cuestionario",
                                 ctx_buscar(DR, "K7FM2P"))["error_cod"] == "N"))

    print("\n4. Guardar signo: cada uno en SU clave y CON SU TIPO")
    ejecutar(cur, "Abrir sesion", ctx_abrir(DR, "S"))
    ejecutar(cur, "Buscar cuestionario", ctx_buscar(DR, "K7FM2P"))
    ESPERADO = {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
                "crepitantes": True, "murmullo_disminuido": False}
    for paso, clave, literal in ((2, "temperatura_c", "38.2"),
                                 (3, "frecuencia_cardiaca", "104"),
                                 (4, "crepitantes", "true"),
                                 (5, "murmullo_disminuido", "false")):
        r = ejecutar(cur, "Guardar signo",
                     ctx_signo(DR, clave, literal, paso + 1, paso))
        comprobar(f"paso {paso}: {clave} guardado, paso -> {paso + 1}",
                  r is not None and r["paso"] == paso + 1, str(r))
    signos = cur.execute("SELECT signos FROM sesiones_profesional WHERE"
                         " chat_id=%s", (DR,)).fetchone()[0]
    comprobar("los cuatro signos, exactamente las claves del §4.4",
              signos == ESPERADO, json.dumps(signos))
    tipos = cur.execute(
        "SELECT jsonb_typeof(signos->'temperatura_c'),"
        "       jsonb_typeof(signos->'frecuencia_cardiaca'),"
        "       jsonb_typeof(signos->'crepitantes'),"
        "       jsonb_typeof(signos->'murmullo_disminuido')"
        "  FROM sesiones_profesional WHERE chat_id=%s", (DR,)).fetchone()
    comprobar("y con SUS TIPOS: numero, numero, booleano, booleano",
              list(tipos) == ["number", "number", "boolean", "boolean"],
              str(tipos))
    r = ejecutar(cur, "Guardar signo",
                 ctx_signo(DR, "murmullo_disminuido", "true", 6, 5))
    comprobar("un doble toque en el mismo boton no encuentra fila (idempotente)",
              r is None, str(r))
    comprobar("y no ha cambiado el valor ya guardado",
              cur.execute("SELECT signos->'murmullo_disminuido' = 'false'::jsonb"
                          " FROM sesiones_profesional WHERE chat_id=%s",
                          (DR,)).fetchone()[0])

    print("\n5. Leer sesion y permiso trae los sintomas SOLO en el paso 6")
    r = ejecutar(cur, "Leer sesion y permiso", ctx_leer(DR))
    comprobar("en el paso 6 si, para poder redactar el §8",
              r["paso"] == 6 and r["sintomas"] == SINTOMAS,
              str(r["paso"]))
    comprobar("y trae los signos completos", r["signos"] == ESPERADO)
    cur.execute("UPDATE sesiones_profesional SET paso=3 WHERE chat_id=%s", (DR,))
    r = ejecutar(cur, "Leer sesion y permiso", ctx_leer(DR))
    comprobar("en el paso 3 NO (§5.4: menos dato del paciente por n8n)",
              r["sintomas"] is None, str(r["sintomas"]))
    cur.execute("UPDATE sesiones_profesional SET paso=6 WHERE chat_id=%s", (DR,))

    print("\n6. Registrar: una sola fila, con la COPIA de los sintomas (D12)")
    r = ejecutar(cur, "Registrar",
                 ctx_registrar(DR, RESULTADO, None, 812, "S", "S"))
    comprobar("escribio una fila y borro la sesion", r == {"filas": 1, "borradas": 1},
              str(r))
    fila = cur.execute("SELECT codigo, chat_id, sintomas, signos, resultado,"
                       " error, ms_extremo FROM consultas ORDER BY id DESC"
                       " LIMIT 1").fetchone()
    comprobar("codigo y chat_id", fila[0] == "K7FM2P" and fila[1] == DR, str(fila[:2]))
    comprobar("los sintomas se COPIARON (D12)", fila[2] == SINTOMAS,
              json.dumps(fila[2], ensure_ascii=False))
    comprobar("los signos, con sus tipos", fila[3] == ESPERADO, json.dumps(fila[3]))
    comprobar("el structuredContent entero y tal cual (§5.3)", fila[4] == RESULTADO,
              json.dumps(fila[4]))
    comprobar("sin error", fila[5] is None)
    comprobar("la latencia del §16 quedo guardada", fila[6] == 812, str(fila[6]))
    comprobar("la sesion murio", cur.execute(
        "SELECT count(*) FROM sesiones_profesional WHERE chat_id=%s",
        (DR,)).fetchone()[0] == 0)

    print("\n7. Registrar: las ramas de error del §9")
    # Un rechazo que TERMINA: fuera_de_alcance.
    ejecutar(cur, "Abrir sesion", ctx_abrir(DR, "S"))
    ejecutar(cur, "Buscar cuestionario", ctx_buscar(DR, "K7FM2P"))
    cur.execute("UPDATE sesiones_profesional SET paso=6 WHERE chat_id=%s", (DR,))
    r = ejecutar(cur, "Registrar",
                 ctx_registrar(DR, None, "fuera_de_alcance", 700, "S", "S"))
    fila = cur.execute("SELECT error, resultado FROM consultas ORDER BY id DESC"
                       " LIMIT 1").fetchone()
    comprobar("fuera_de_alcance: fila con su codigo",
              fila[0] == "fuera_de_alcance", str(fila))
    comprobar("y SIN resultado: un rechazo no puede traer cifras (§9)",
              fila[1] is None)
    comprobar("y la conversacion termina: la sesion se borro", r["borradas"] == 1)
    # Un error que NO termina: se queda esperando el archivo.
    ejecutar(cur, "Abrir sesion", ctx_abrir(DR, "S"))
    ejecutar(cur, "Buscar cuestionario", ctx_buscar(DR, "K7FM2P"))
    cur.execute("UPDATE sesiones_profesional SET paso=6 WHERE chat_id=%s", (DR,))
    antes = cur.execute("SELECT paso FROM sesiones_profesional WHERE chat_id=%s",
                        (DR,)).fetchone()[0]
    r = ejecutar(cur, "Registrar",
                 ctx_registrar(DR, None, "envio_como_foto", 90, "N", "S"))
    comprobar("envio_como_foto: registra pero NO borra la sesion",
              r == {"filas": 1, "borradas": 0}, str(r))
    comprobar("y el paso no se movio (§9: se queda esperando el archivo)",
              cur.execute("SELECT paso FROM sesiones_profesional WHERE"
                          " chat_id=%s", (DR,)).fetchone()[0] == antes)
    # El mensaje que solo ensena el caso: no es un desenlace clinico.
    n_antes = cur.execute("SELECT count(*) FROM consultas").fetchone()[0]
    r = ejecutar(cur, "Registrar", ctx_registrar(DR, None, None, 120, "N", "N"))
    comprobar("registrar='N' no escribe fila", r["filas"] == 0 and cur.execute(
        "SELECT count(*) FROM consultas").fetchone()[0] == n_antes, str(r))
    comprobar("ni borra la sesion", cur.execute(
        "SELECT count(*) FROM sesiones_profesional WHERE chat_id=%s",
        (DR,)).fetchone()[0] == 1)
    # El rechazo de un chat SIN sesion: es el no_autorizado, y tiene que quedar
    # registrado igual (§5.1).
    r = ejecutar(cur, "Registrar",
                 ctx_registrar(INTRUSO, None, "no_autorizado", 40, "N", "S"))
    fila = cur.execute("SELECT chat_id, codigo, error, resultado FROM consultas"
                       " ORDER BY id DESC LIMIT 1").fetchone()
    comprobar("un chat sin sesion tambien deja su fila de rechazo",
              r["filas"] == 1 and fila[0] == INTRUSO and
              fila[1] is None and fila[2] == "no_autorizado" and fila[3] is None,
              str(fila))
    # El texto integro de lo que no se sabe interpretar (§9).
    ejecutar(cur, "Registrar", ctx_registrar(
        DR, None, "error_no_reconocido: gremlins_en_el_gpu: se fue la luz",
        55, "S", "S"))
    comprobar("error_no_reconocido guarda el texto integro en consultas.error",
              cur.execute("SELECT error FROM consultas ORDER BY id DESC LIMIT 1")
              .fetchone()[0].endswith("se fue la luz"))

    print("\n8. dos profesionales a la vez NO cruzan sus signos")
    cur.execute("TRUNCATE sesiones_profesional, consultas")
    cur.execute("INSERT INTO cuestionarios (codigo, respuestas, consentido_en,"
                " expira_en) VALUES ('QQ2222', %s, now(), now() + interval"
                " '7 days')", (json.dumps({"fiebre": "no", "tos": "no",
                                           "dias_evolucion": "menos_3",
                                           "disnea": "no",
                                           "dolor_toracico": "no",
                                           "asma": "no", "texto_libre": None}),))
    for chat, codigo in ((DR, "K7FM2P"), (DRA, "QQ2222")):
        ejecutar(cur, "Abrir sesion", ctx_abrir(chat, "N"))
        ejecutar(cur, "Buscar cuestionario", ctx_buscar(chat, codigo))
    # Intercalados, como llegarian dos conversaciones simultaneas.
    for chat, temp in ((DR, "38.2"), (DRA, "36.4")):
        ejecutar(cur, "Guardar signo", ctx_signo(chat, "temperatura_c", temp, 3, 2))
    for chat, fc in ((DRA, "72"), (DR, "104")):
        ejecutar(cur, "Guardar signo", ctx_signo(chat, "frecuencia_cardiaca", fc, 4, 3))
    a = cur.execute("SELECT signos, codigo FROM sesiones_profesional WHERE"
                    " chat_id=%s", (DR,)).fetchone()
    b = cur.execute("SELECT signos, codigo FROM sesiones_profesional WHERE"
                    " chat_id=%s", (DRA,)).fetchone()
    comprobar("cada uno con SUS signos",
              a[0] == {"temperatura_c": 38.2, "frecuencia_cardiaca": 104} and
              b[0] == {"temperatura_c": 36.4, "frecuencia_cardiaca": 72},
              json.dumps([a[0], b[0]]))
    comprobar("y con SU codigo de paciente",
              a[1] == "K7FM2P" and b[1] == "QQ2222", str([a[1], b[1]]))
    for chat in (DR, DRA):
        cur.execute("UPDATE sesiones_profesional SET paso=6 WHERE chat_id=%s",
                    (chat,))
        ejecutar(cur, "Registrar", ctx_registrar(chat, RESULTADO, None, 500, "S", "S"))
    filas = cur.execute("SELECT chat_id, codigo, signos->'temperatura_c'"
                        " FROM consultas ORDER BY chat_id").fetchall()
    comprobar("las dos consultas se registran sin mezclarse",
              filas == [(DR, "K7FM2P", 38.2), (DRA, "QQ2222", 36.4)], str(filas))

    print("\n9. el flujo del profesional NO toca las tablas del paciente")
    for tabla in ("sesiones_paciente", "limite_paciente",
                  "cuestionarios_iniciados"):
        comprobar(f"{tabla} sigue vacia", cur.execute(
            f"SELECT count(*) FROM {tabla}").fetchone()[0] == 0)

print(f"\n{'TODO VERDE' if not fallos else 'FALLOS: ' + ', '.join(fallos)}")
sys.exit(1 if fallos else 0)
