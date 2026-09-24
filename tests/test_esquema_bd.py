"""El SQL de SP3, contra una PostgreSQL de verdad.

Un `WHERE` mal puesto en la limpieza borra datos vivos o no borra nada y la
tabla crece para siempre con datos de pacientes en el disco del cliente. Eso
no se revisa leyendo: se prueba.
"""
import pathlib
import subprocess
import time
import uuid

import psycopg
import pytest

BD = pathlib.Path(__file__).resolve().parents[1] / "bd"


@pytest.fixture(scope="module")
def conexion():
    nombre = f"copiloto-bd-prueba-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", nombre,
         "-e", "POSTGRES_PASSWORD=prueba", "-p", "15432:5432",
         "postgres:16-alpine"], check=True, capture_output=True)
    try:
        dsn = "postgresql://postgres:prueba@127.0.0.1:15432/postgres"
        for _ in range(60):
            try:
                with psycopg.connect(dsn, connect_timeout=2) as c:
                    break
            except psycopg.OperationalError:
                time.sleep(1)
        else:
            pytest.fail("la PostgreSQL de prueba no arranco")
        with psycopg.connect(dsn, autocommit=True) as c:
            c.execute((BD / "esquema.sql").read_text(encoding="utf-8"))
            yield c
    finally:
        subprocess.run(["docker", "rm", "-f", nombre], capture_output=True)


def test_el_codigo_tiene_seis_caracteres_del_alfabeto_sin_ambiguos(conexion):
    """Se dicta en voz alta en una consulta: ni 0/O ni 1/I/L."""
    permitidos = set("ABCDEFGHJKMNPQRSTUVWXYZ23456789")
    for _ in range(200):
        codigo = conexion.execute("SELECT generar_codigo()").fetchone()[0]
        assert len(codigo) == 6
        assert set(codigo) <= permitidos, codigo


def test_el_codigo_no_usa_un_alfabeto_sesgado(conexion):
    """256 no es multiplo de 31: un `% 31` a secas hace que los primeros 8
    caracteres del alfabeto salgan con probabilidad 9/256 cada uno y el resto
    con 8/256 -- un 12.5% mas, no al azar sino de forma determinista. La
    prueba compara el conteo MEDIO del grupo de 8 contra el del grupo de 23:
    esa media tiene mucha menos varianza que un caracter suelto, así que el
    sesgo se separa limpiamente del ruido con una muestra manejable.

    Lo que había antes de esta correccion (`frecuencias[-1] / frecuencias[0]
    < 1.5`, comparando el caracter MAS frecuente contra el MENOS frecuente de
    los 31) no funciona a ningun umbral razonable: esa es una estadistica de
    extremos con demasiada varianza propia -- con muestreo uniforme de verdad
    ya sale ~1.33 de puro ruido con 1000 codigos, y ~1.16 incluso con 4000.
    El "Ruling 3" del controlador pedia subir a 4000 codigos y bajar el
    umbral a 1.4, pero un `% 31` sesgado con 4000 codigos da ~1.27 de media
    (max ~1.30 en 50000 simulaciones) -- por debajo de 1.4. Verificado en
    vivo: con el `% 31` a secas sustituyendo el rechazo, esta prueba SEGUIA
    EN VERDE. Con el estadistico de grupo de abajo, en 50 000 simulaciones
    Monte Carlo el alfabeto uniforme nunca supera ~1.066 y el sesgado nunca
    baja de ~1.062; el umbral 1.06 separa ambos con margen y una tasa de
    falso-fallo de ~1 en 25 000."""
    from collections import Counter
    ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    cuenta = Counter()
    for _ in range(4000):
        cuenta.update(conexion.execute("SELECT generar_codigo()").fetchone()[0])
    primeros8 = sum(cuenta[c] for c in ALFABETO[:8]) / 8
    resto23 = sum(cuenta[c] for c in ALFABETO[8:]) / 23
    assert primeros8 / resto23 < 1.06, dict(cuenta)


def test_la_limpieza_borra_los_cuestionarios_caducados_y_solo_esos(conexion):
    conexion.execute("TRUNCATE cuestionarios")
    conexion.execute(
        "INSERT INTO cuestionarios (codigo, respuestas, consentido_en, expira_en)"
        " VALUES ('VIEJO1', '{}', now(), now() - interval '1 hour'),"
        "        ('NUEVO1', '{}', now(), now() + interval '6 days')")
    conexion.execute((BD / "limpieza.sql").read_text(encoding="utf-8"))
    quedan = [f[0] for f in conexion.execute(
        "SELECT codigo FROM cuestionarios ORDER BY codigo").fetchall()]
    assert quedan == ["NUEVO1"]


def test_la_limpieza_borra_las_sesiones_abandonadas_de_mas_de_24h(conexion):
    conexion.execute("TRUNCATE sesiones_paciente, sesiones_profesional")
    conexion.execute(
        "INSERT INTO sesiones_paciente (chat_id, actualizado_en) VALUES"
        " (1, now() - interval '25 hours'), (2, now() - interval '1 hour')")
    conexion.execute(
        "INSERT INTO sesiones_profesional (chat_id, actualizado_en) VALUES"
        " (3, now() - interval '25 hours'), (4, now() - interval '1 hour')")
    conexion.execute((BD / "limpieza.sql").read_text(encoding="utf-8"))
    assert [f[0] for f in conexion.execute(
        "SELECT chat_id FROM sesiones_paciente").fetchall()] == [2]
    assert [f[0] for f in conexion.execute(
        "SELECT chat_id FROM sesiones_profesional").fetchall()] == [4]


def test_la_limpieza_NO_toca_consultas(conexion):
    """`consultas` es el registro permanente: sin el no hay validacion en H7."""
    conexion.execute("TRUNCATE consultas")
    conexion.execute(
        "INSERT INTO consultas (codigo, chat_id, creado_en)"
        " VALUES ('ANTIGU', 1, now() - interval '400 days')")
    conexion.execute((BD / "limpieza.sql").read_text(encoding="utf-8"))
    assert conexion.execute("SELECT count(*) FROM consultas").fetchone()[0] == 1


def test_consultas_no_referencia_a_cuestionarios(conexion):
    """Si hubiera clave foranea, borrar un cuestionario caducado arrastraria o
    bloquearia el registro permanente."""
    conexion.execute("TRUNCATE consultas")
    conexion.execute(
        "INSERT INTO consultas (codigo, chat_id) VALUES ('NOEXIS', 1)")
    assert conexion.execute("SELECT count(*) FROM consultas").fetchone()[0] == 1


def test_el_contador_de_iniciados_acumula_por_dia(conexion):
    """El dashboard mide abandono, y las sesiones se borran: sin este contador
    'iniciados vs completados' es incalculable."""
    conexion.execute("TRUNCATE cuestionarios_iniciados")
    for _ in range(3):
        conexion.execute(
            "INSERT INTO cuestionarios_iniciados (dia, cuantos)"
            " VALUES ((now() AT TIME ZONE 'America/Guayaquil')::date, 1)"
            " ON CONFLICT (dia) DO UPDATE SET cuantos ="
            " cuestionarios_iniciados.cuantos + 1")
    assert conexion.execute(
        "SELECT cuantos FROM cuestionarios_iniciados").fetchone()[0] == 3


def test_el_limite_cuenta_por_chat_id_y_dia(conexion):
    """El limite de 5/dia del §4.2, que el esquema anterior no podia sostener:
    `cuestionarios` no tiene `chat_id`."""
    conexion.execute("TRUNCATE limite_paciente")
    for _ in range(3):
        conexion.execute(
            "INSERT INTO limite_paciente (chat_id, dia, cuantos)"
            " VALUES (777, (now() AT TIME ZONE 'America/Guayaquil')::date, 1)"
            " ON CONFLICT (chat_id, dia) DO UPDATE SET cuantos ="
            " limite_paciente.cuantos + 1")
    conexion.execute(
        "INSERT INTO limite_paciente (chat_id, dia, cuantos)"
        " VALUES (888, (now() AT TIME ZONE 'America/Guayaquil')::date, 1)")
    filas = dict(conexion.execute(
        "SELECT chat_id, cuantos FROM limite_paciente ORDER BY chat_id").fetchall())
    assert filas == {777: 3, 888: 1}, "los contadores de dos chats se mezclaron"


def test_el_limite_no_puede_ligar_un_chat_id_a_un_codigo(conexion):
    """LA prueba de esta tabla, y la razon de que sea una tabla aparte.

    El contador necesita saber CUANTOS cuestionarios hizo un chat_id hoy, no
    CUALES. Si alguien anadiera aqui una columna con el codigo seudonimo -o
    metiera el chat_id en `cuestionarios`- el seudonimo dejaria de serlo: se
    podria reconstruir que cuenta de Telegram respondio que cuestionario.

    Esta prueba existe para que ese cambio no pase desapercibido en una
    revision.
    """
    columnas = {f[0] for f in conexion.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_name = 'limite_paciente'").fetchall()}
    assert columnas == {"chat_id", "dia", "cuantos"}, columnas

    de_cuestionarios = {f[0] for f in conexion.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_name = 'cuestionarios'").fetchall()}
    assert "chat_id" not in de_cuestionarios, (
        "cuestionarios no puede llevar chat_id: ataria el codigo seudonimo a "
        "una cuenta de Telegram")


def test_la_limpieza_borra_el_contador_a_los_dos_dias(conexion):
    conexion.execute("TRUNCATE limite_paciente")
    conexion.execute(
        "INSERT INTO limite_paciente (chat_id, dia, cuantos) VALUES"
        " (1, (now() AT TIME ZONE 'America/Guayaquil')::date, 1),"
        " (2, (now() AT TIME ZONE 'America/Guayaquil')::date - 1, 1),"
        " (3, (now() AT TIME ZONE 'America/Guayaquil')::date - 5, 1)")
    conexion.execute((BD / "limpieza.sql").read_text(encoding="utf-8"))
    quedan = sorted(f[0] for f in conexion.execute(
        "SELECT chat_id FROM limite_paciente").fetchall())
    assert quedan == [1, 2], "se borro el contador de hoy o sobrevivio el viejo"
