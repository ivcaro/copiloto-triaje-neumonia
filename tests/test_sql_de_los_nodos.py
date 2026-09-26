# -*- coding: utf-8 -*-
"""Mete los dos arneses de SQL DENTRO de la puerta de `pytest`.

POR QUE EXISTE ESTE FICHERO
---------------------------
La semantica SQL de los dos bots -quien puede pasar la lista blanca, que sesion
se borra, que se copia a `consultas`, si un doble toque guarda dos signos- vive
en las consultas de los nodos de n8n, y `pytest` no la tocaba. Medido por una
revision: **9 de 9 mutaciones a esas consultas dejaban `pytest -q` en
300 passed y exit 0**, y los tres arneses de node tambien en verde. Las unicas
que las cazan son `pruebas/verificar_sql_paciente.py` y
`pruebas/verificar_sql_profesional.py`, que `testpaths = ["tests"]` deja fuera y
que el README no nombraba.

El problema no es que los arneses no existan: es que «303 passed» se lee como
«esta todo cubierto», y de SQL no habia nada. Un numero que dice de mas es peor
que un numero pequeno.

Aqui no se reescribe nada de los arneses. Se les llama, y **si no hay
contenedor, se SALTA diciendo exactamente que se queda sin verificar** -no se
falla, porque un `ConnectionRefusedError` repetido entrena a no mirar los
fallos, que es el ruling 18 de esta rama-.

UN SKIP AQUI SE VE VERDE. Para saber si de verdad corrieron:  `pytest -rs`.

NO SON SEGUROS EN PARALELO: cada arnes hace `TRUNCATE` de su base entera, asi
que dos sesiones apuntando al mismo contenedor se pisan y dan fallos falsos.
`pytest` los corre en serie, y por eso cada uno tiene su propio puerto.
"""
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

# (fichero, puerto, nombre del contenedor, que se queda sin verificar)
ARNESES = [
    ("verificar_sql_paciente.py", 15499, "sp3-verifica-sql",
     "el consentimiento, el limite diario por paciente, el alta de sesion, "
     "que se guarda cada respuesta y la generacion del codigo"),
    ("verificar_sql_profesional.py", 15498, "sp3-verifica-sql-prof",
     "la lista blanca de D6, el borrado de la sesion, los signos que se "
     "fusionan en el jsonb con su tipo, la copia de sintomas a `consultas` y "
     "que dos profesionales a la vez no se mezclan"),
]


def _arranca_el_contenedor(puerto: int) -> bool:
    """¿Hay una Postgres escuchando en ese puerto?"""
    try:
        import psycopg
    except ImportError:
        return False
    dsn = (f"host=127.0.0.1 port={puerto} dbname=copiloto "
           "user=postgres password=verifica")
    try:
        with psycopg.connect(dsn, connect_timeout=3):
            return True
    except Exception:
        return False


@pytest.mark.parametrize("fichero,puerto,contenedor,sin_verificar", ARNESES)
def test_la_semantica_sql_de_los_nodos(fichero, puerto, contenedor,
                                       sin_verificar):
    if not _arranca_el_contenedor(puerto):
        pytest.skip(
            f"sin la Postgres de prueba en el {puerto}, asi que NO se verifica: "
            f"{sin_verificar}.\n"
            f"Para verificarlo:\n"
            f"  docker run -d --rm --name {contenedor} "
            f"-e POSTGRES_PASSWORD=verifica -e POSTGRES_DB=copiloto "
            f"-p 127.0.0.1:{puerto}:5432 postgres:16-alpine\n"
            f"  docker exec -i {contenedor} psql -U postgres -d copiloto "
            f"< bd/esquema.sql\n"
            f"  (y al terminar: docker rm -f {contenedor})")

    p = subprocess.run([sys.executable, str(RAIZ / "pruebas" / fichero)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(RAIZ))
    # El arnes imprime su propio informe y sale 1 si algo fallo. Se ensena
    # entero: es donde dice QUE consulta se rompio y con que valores.
    assert p.returncode == 0, (
        f"{fichero} fallo (exit {p.returncode}):\n{p.stdout}\n{p.stderr}")
    assert "TODO VERDE" in p.stdout, p.stdout[-2000:]
