"""Pruebas del punto de entrada del contenedor.

Se comprueba que dos variables sean de verdad obligatorias: `AUC_VALIDACION` y
`PREVALENCIA_LOCAL`. Son afirmaciones de calidad y de contexto clinico que se
le muestran al profesional -`AUC_VALIDACION` en cada respuesta y
`PREVALENCIA_LOCAL` en cada informe con combinacion-, y un default silencioso
sobreviviria a un reentrenamiento o a un despliegue en otra sede citando la
cifra vieja. El comentario del fichero siempre dijo eso; la linea de debajo le
ponia un valor por defecto y lo desmentia -es la garantia que esta rama ya
perdio una vez con `AUC_VALIDACION`-.

Se ejecuta en un subproceso porque el fichero carga el modelo al importarse.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
ARRANCAR = RAIZ / "servidor" / "arrancar.py"

# El comienzo de cada negativa. Se busca esta frase y no solo el nombre de la
# variable: el nombre tambien aparece en el traceback de cualquier OTRO fallo
# posterior -sale en la linea de codigo que lo provoco-, y una prueba que solo
# lo buscara pasaria tambien cuando el arranque murio de otra cosa.
NEGATIVA = "Falta la variable de entorno AUC_VALIDACION"
NEGATIVA_PREVALENCIA = "Falta la variable de entorno PREVALENCIA_LOCAL"
OBLIGATORIAS = ("AUC_VALIDACION", "PREVALENCIA_LOCAL")


def _arrancar(**entorno):
    """Lanza `arrancar.py` con rutas de pesos inexistentes a proposito.

    Asi el arranque muere siempre, y lo que la prueba mira es DE QUE muere: si
    de una variable que falta o de los pesos que no estan. Nunca llega a
    `uvicorn.run`. Se quitan del entorno LAS DOS obligatorias, para que una
    puesta en la maquina de quien corre las pruebas no las deje pasar.
    """
    env = {k: v for k, v in os.environ.items() if k not in OBLIGATORIAS}
    env["PYTHONPATH"] = str(RAIZ / "src")
    env["RUTA_PESOS"] = str(RAIZ / "no_existen_estos_pesos.pt")
    env["RUTA_CALIBRADOR"] = str(RAIZ / "no_existe_este_calibrador.json")
    env.update(entorno)
    return subprocess.run([sys.executable, str(ARRANCAR)], env=env,
                          capture_output=True, text=True, timeout=300)


def test_sin_auc_de_validacion_el_arranque_falla_diciendo_cual_falta():
    """Sin la variable, el arranque se niega y el mensaje dice que hay que
    declararla. No arranca sirviendo una cifra de calidad inventada."""
    resultado = _arrancar()

    assert resultado.returncode != 0
    salida = resultado.stdout + resultado.stderr
    assert NEGATIVA in salida, salida
    # Y no muere de los pesos: se niega ANTES de intentar cargar nada.
    assert "no_existen_estos_pesos.pt" not in salida, salida


def test_con_auc_de_validacion_el_arranque_pasa_de_esa_comprobacion():
    """La hermana de la anterior, y la que impide que la comprobacion se
    convierta en un "siempre falla" que nadie distinguiria de un acierto: con
    las dos variables puestas, el arranque ya no se queja de ninguna y llega a
    lo siguiente, que aqui son los pesos inexistentes."""
    resultado = _arrancar(AUC_VALIDACION="0.8827", PREVALENCIA_LOCAL="0.1466")

    salida = resultado.stdout + resultado.stderr
    assert NEGATIVA not in salida, salida
    assert "no_existen_estos_pesos.pt" in salida, salida


def test_sin_prevalencia_local_el_arranque_falla_diciendo_cual_falta():
    """SP4 §5 y criterio 8: la misma disciplina que AUC_VALIDACION, por la
    misma razon. Es una cifra que acaba delante de un clinico."""
    resultado = _arrancar(AUC_VALIDACION="0.8827")

    assert resultado.returncode != 0
    salida = resultado.stdout + resultado.stderr
    assert NEGATIVA_PREVALENCIA in salida, salida
    assert NEGATIVA not in salida, salida
    assert "no_existen_estos_pesos.pt" not in salida, salida


def test_una_prevalencia_que_no_es_probabilidad_se_rechaza_al_arrancar():
    resultado = _arrancar(AUC_VALIDACION="0.8827", PREVALENCIA_LOCAL="1.5")

    assert resultado.returncode != 0
    salida = resultado.stdout + resultado.stderr
    assert "entre 0 y 1" in salida, salida
    assert "no_existen_estos_pesos.pt" not in salida, salida


def test_el_compose_declara_la_prevalencia_con_su_fuente():
    """Restriccion 3: sin default en el codigo, con valor y fuente en el
    compose. Que la fuente este escrita al lado es parte del diseno (§5)."""
    compose = (RAIZ / "servidor" / "docker-compose.yml").read_text(encoding="utf-8")
    assert 'PREVALENCIA_LOCAL: "0.1466"' in compose
    assert "134/914" in compose and "Heckerling" in compose
    # Y en el servicio que la lee: el texto crudo tambien pasaria con la
    # linea en otro servicio. (PyYAML esta en el venv pero no en las
    # dependencias del proyecto: sin el, esta mitad se salta y lo dice.)
    yaml = pytest.importorskip("yaml")
    servicios = yaml.safe_load(compose)["services"]
    assert servicios["copiloto-mcp"]["environment"]["PREVALENCIA_LOCAL"] == "0.1466"


# --- La red externa de n8n (spec de SP5 §6.1) -------------------------------
#
# La clave de la red es neutra y su nombre real NO vive en el repositorio: lo
# pone quien despliega, en `RED_N8N`. Sin valor por defecto a proposito: un
# nombre por defecto es el nombre de la red de alguien, y ademas un compose
# que arranca «con lo que haya» puede unirse a la red equivocada sin avisar.

NOMBRE_DE_LA_RED = "${RED_N8N:?define RED_N8N con el nombre de la red externa de n8n}"


def test_el_compose_exige_RED_N8N_y_no_le_pone_valor_por_defecto():
    """Sobre el texto crudo, para que corra aunque no haya PyYAML."""
    compose = (RAIZ / "servidor" / "docker-compose.yml").read_text(encoding="utf-8")
    usos = re.findall(r"\$\{?RED_N8N[^}\s]*", compose)
    assert usos, "el compose ya no lee RED_N8N"
    # `:?` aborta si la variable falta O esta vacia. `:-` y `-` serian un valor
    # por defecto; `?` a secas dejaria pasar la variable vacia.
    assert all(uso.startswith("${RED_N8N:?") for uso in usos), usos
    assert f"    name: {NOMBRE_DE_LA_RED}\n" in compose


def test_los_dos_servicios_van_a_la_red_externa_red_n8n():
    yaml = pytest.importorskip(
        "yaml", reason="sin PyYAML no se lee el compose: se queda sin verificar que "
                       "los dos servicios van a la red externa `red_n8n`")
    compose = yaml.safe_load(
        (RAIZ / "servidor" / "docker-compose.yml").read_text(encoding="utf-8"))
    # Una sola red, con clave neutra, externa, y con el nombre por entorno.
    assert compose["networks"] == {
        "red_n8n": {"external": True, "name": NOMBRE_DE_LA_RED}}
    for servicio in ("copiloto-mcp", "copiloto-bd"):
        assert compose["services"][servicio]["networks"] == ["red_n8n"], servicio


def test_el_env_de_ejemplo_declara_RED_N8N_con_un_valor_de_ejemplo():
    lineas = (RAIZ / "servidor" / ".env.ejemplo").read_text(
        encoding="utf-8").splitlines()
    assert "RED_N8N=cambiar-esto" in lineas


def test_la_guia_de_despliegue_no_promete_un_valor_por_defecto_para_la_red():
    guia = (RAIZ / "docs" / "sp2-despliegue.md").read_text(encoding="utf-8")
    assert "${RED_N8N:-" not in guia and "${RED_N8N-" not in guia
    assert "${RED_N8N:?" in guia
    # La fila de la tabla de variables (paso 10) lo dice con todas las letras.
    assert "| `RED_N8N` | **ninguno: es obligatoria** |" in guia


PARAN_O_BORRAN = {"down", "stop", "kill", "rm", "restart", "pause", "prune"}


def _las_que_paran(bloque):
    """Las ordenes de docker de un bloque de shell que paran o borran algo.
    El bloque se parte por `&&`, `||`, `;`, `|` y saltos de linea."""
    paran = []
    for orden in re.split(r"&&|\|\||;|\||\n", bloque):
        if "docker" not in orden:
            continue
        palabras = orden[orden.index("docker"):].split()
        if PARAN_O_BORRAN & set(palabras):
            paran.append(" ".join(palabras))
    return paran


def test_el_primer_redespliegue_no_baja_el_servicio_antes_de_construir():
    """El apartado lo sigue una persona en un servidor que comparte con otros
    servicios. Las ordenes que redespliegan construyen y recrean sin parar
    nada antes, y esperan a los dos contenedores; la unica orden que para algo
    es la bajada de reserva, que va por nombre de proyecto, sin volumenes y
    DESPUES de construir; la base y los contenedores se apuntan antes y se
    comparan despues; hay copia de la base; y la vuelta atras restaura el
    `.env` antes de levantar."""
    guia = (RAIZ / "docs" / "sp2-despliegue.md").read_text(encoding="utf-8")
    inicio = guia.index("### El primer redespliegue con `RED_N8N` obligatoria")
    apartado = guia[inicio:guia.index("\n## 7. ", inicio)]
    bloques = re.findall(r"```bash\n(.*?)```", apartado, flags=re.S)
    # en todo el apartado, dentro o fuera de un bloque, nadie baja con los volumenes
    assert not re.search(r"down\s+(-v\b|--volumes)", apartado)

    # las dos ordenes que redespliegan: la del punto 5 y la de la vuelta atras
    redespliegues = [b for b in bloques if "up -d --build" in b]
    assert len(redespliegues) == 2
    for orden in redespliegues:
        assert _las_que_paran(orden) == [], "no para ni borra nada antes de construir"
        assert ("docker compose -f servidor/docker-compose.yml up -d --build && "
                "for c in copiloto-bd copiloto-mcp") in orden, (
            "no nombra un servicio, y espera a los dos contenedores")

    # la unica orden del apartado que para algo es la bajada de reserva
    con_parada = [b for b in bloques if _las_que_paran(b)]
    assert len(con_parada) == 1
    reserva = con_parada[0]
    assert _las_que_paran(reserva) == ["docker compose -p copiloto-mcp down"]
    construir = "docker compose -f servidor/docker-compose.yml build"
    levantar = "docker compose -f servidor/docker-compose.yml up -d"
    assert reserva.index(construir) < reserva.index(" down") < reserva.index(levantar)
    assert "for c in copiloto-bd copiloto-mcp" in reserva

    # como estan la base y los contenedores, antes (punto 3) y despues (punto 6)
    assert apartado.count("'volumen creado: {{.CreatedAt}}'") == 2
    assert apartado.count("'{{.Name}} creado: {{.Created}}'") == 2
    assert apartado.count("-tAc 'select count(*) from consultas'") == 3, (
        "antes, despues y tras restaurar la copia")

    # la copia de la base: antes de redesplegar, y un fallo no pasa por bueno
    copias = [b for b in bloques if "pg_dump" in b]
    assert len(copias) == 1
    assert "set -o pipefail" in copias[0] and "umask 077" in copias[0]
    assert apartado.index("pg_dump") < apartado.index("up -d --build")

    # el .env se guarda antes de tocarlo, la linea se ANADE, y la vuelta
    # atras lo restaura antes de levantar el commit anterior
    guardar = "cp -p servidor/.env ~/copiloto.env.antes-de-red_n8n"
    restaurar = "cp -p ~/copiloto.env.antes-de-red_n8n servidor/.env"
    assert apartado.index(guardar) < apartado.index(">> /opt/copiloto/servidor/.env")
    assert not re.search(r"[^>]> /opt/copiloto/servidor/\.env", apartado)
    vuelta = [b for b in redespliegues if "git checkout --detach <commit del punto 1>" in b]
    assert len(vuelta) == 1
    assert (vuelta[0].index(restaurar) < vuelta[0].index("git checkout --detach")
            < vuelta[0].index("up -d --build"))
