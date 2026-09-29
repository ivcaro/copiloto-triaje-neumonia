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


# La palabra entera, tambien pegada a un parentesis o a una comilla; `--rm`,
# `rmi` o `ON_ERROR_STOP` no son ninguna de ellas.
PARAN_O_BORRAN = re.compile(
    r"(?<![\w-])(down|stop|kill|rm|restart|pause|prune|disconnect)(?![\w-])")


def _ordenes(bloque):
    """Los trozos de un bloque de shell: se parte por `&&`, `||`, `;`, `|` y
    saltos de linea, despues de unir las lineas que siguen con `\\`."""
    return re.split(r"&&|\|\||;|\||\n", bloque.replace("\\\n", " "))


def _las_que_paran(bloque):
    """Los trozos de un bloque de shell que llevan `docker` y paran o borran
    algo, con los blancos normalizados. Se mira el trozo ENTERO, no solo lo
    que va detras de `docker`: `systemctl restart docker` para todos los
    contenedores de la maquina."""
    return [" ".join(orden.split()) for orden in _ordenes(bloque)
            if "docker" in orden and PARAN_O_BORRAN.search(orden)]


def _bloques(texto):
    """[(apartado, bloque)]: el contenido de cada bloque con valla, con
    lenguaje o sin el (```bash, ```sh, ```), y el titulo del apartado en el
    que esta. Las vallas pueden ir sangradas, dentro de una lista; y las
    lineas de un bloque que empiezan por `#` son comentarios, no titulos."""
    bloques, apartado, dentro = [], "", None
    for linea in texto.splitlines():
        if linea.lstrip().startswith("```"):
            if dentro is None:
                dentro = []
            else:
                bloques.append((apartado, "\n".join(dentro) + "\n"))
                dentro = None
        elif dentro is not None:
            dentro.append(linea)
        elif re.match(r"#{1,6} ", linea):
            apartado = linea.lstrip("#").strip()
    return bloques


@pytest.mark.parametrize("bloque, paran", [
    ("sudo systemctl restart docker\n", ["sudo systemctl restart docker"]),
    ("kill $(docker inspect -f '{{.State.Pid}}' x)\n",
     ["kill $(docker inspect -f '{{.State.Pid}}' x)"]),
    ("docker network disconnect red x\n", ["docker network disconnect red x"]),
    ("x=$(docker compose -p otro down)\n", ["x=$(docker compose -p otro down)"]),
    ("docker compose \\\n  -p otro \\\n  stop\n", ["docker compose -p otro stop"]),
    ("cd /opt && docker compose up -d --build && docker logs --tail 50 copiloto-mcp\n", []),
    ("rm -f ~/copia\n", []),
    ("docker run --rm x && docker rmi y\n", []),
])
def test_las_que_paran_mira_el_trozo_entero(bloque, paran):
    assert _las_que_paran(bloque) == paran


# Las ordenes de la guia que paran o borran algo y NO van por nombre de
# proyecto, una a una, con el apartado donde estan y su motivo. Fuera de ese
# apartado, la misma orden no vale.
EXCEPCIONES = {
    ("Caso B: en local, para probar el despliegue desde cero",
     "docker compose down"):
        "en la maquina de quien prueba, desde `servidor/`: baja el proyecto de "
        "ese compose, con la red de tirar, y alli no hay ningun stack ajeno",
    ("Caso B: en local, para probar el despliegue desde cero",
     "docker network rm copiloto-local"):
        "borra la red de tirar que el mismo caso crea dos ordenes antes; el "
        "nombre de la red de n8n no aparece nunca junto a un `network rm`",
}

_COMPOSE = re.compile(r"docker(-|\s+)compose(?![\w-])")
_POR_PROYECTO = re.compile(r"(?<![\w-])(-p\s+|--project-name[\s=]+)copiloto-mcp(?![\w-])")
_CON_VOLUMENES = re.compile(r"(?<![\w-])(-[A-Za-z]*v[A-Za-z]*|--volumes)(?![\w-])")
_BORRA_VOLUMEN = re.compile(r"docker\s+volume\s+rm(?![\w-])")


def _ordenes_que_no_valen(guia):
    """Las ordenes de los bloques de la guia (con cualquier valla) que borran
    datos o pueden parar lo ajeno: un `down` con `-v` o `--volumes` en
    cualquier posicion, un `docker volume rm` o un `prune`, y cualquier orden
    que pare, arranque o borre algo sin ser de Compose por nombre de proyecto
    (`-p copiloto-mcp`), salvo las `EXCEPCIONES`. Devuelve [(apartado,
    orden, por que)]; tambien, las excepciones que ya no estan en la guia."""
    malas, usadas = [], set()
    for apartado, bloque in _bloques(guia):
        for orden in _ordenes(bloque):
            orden = " ".join(orden.split())
            if "docker" not in orden:
                continue
            if (re.search(r"(?<![\w-])down(?![\w-])", orden)
                    and _CON_VOLUMENES.search(orden)):
                malas.append((apartado, orden, "down con volumenes: borra la base"))
            elif _BORRA_VOLUMEN.search(orden) or re.search(r"(?<![\w-])prune(?![\w-])", orden):
                malas.append((apartado, orden, "borra volumenes o imagenes"))
            elif (PARAN_O_BORRAN.search(orden)
                  or re.search(r"(?<![\w-])start(?![\w-])", orden)):
                if (apartado, orden) in EXCEPCIONES:
                    usadas.add((apartado, orden))
                elif not (_COMPOSE.search(orden) and _POR_PROYECTO.search(orden)):
                    malas.append((apartado, orden,
                                  "para, arranca o borra sin ir por -p copiloto-mcp"))
    malas += [(apartado, orden, "excepcion que la guia ya no lleva")
              for apartado, orden in set(EXCEPCIONES) - usadas]
    return malas


def _guia():
    return (RAIZ / "docs" / "sp2-despliegue.md").read_text(encoding="utf-8")


def test_la_guia_entera_no_lleva_ordenes_que_borren_datos_o_paren_lo_ajeno():
    """El servidor es COMPARTIDO con los servicios de un cliente y la guia la
    sigue una persona copiando y pegando: en ningun bloque de ordenes, del
    tipo que sea, hay un `down` con volumenes, un `docker volume rm` ni un
    `prune`, y todo lo que para, arranca o borra va por nombre de proyecto,
    salvo las excepciones de arriba."""
    assert _ordenes_que_no_valen(_guia()) == []
    # y la comprobacion ha visto las que van por proyecto: la bajada de
    # reserva del primer redespliegue, y el `down`, el `stop` y el `start`
    # del paso 12
    ordenes = [" ".join(o.split()) for _, b in _bloques(_guia()) for o in _ordenes(b)]
    assert ordenes.count("docker compose -p copiloto-mcp down") == 2
    for verbo in ("stop", "start"):
        assert any(o.startswith(f"docker compose -p copiloto-mcp {verbo} ")
                   for o in ordenes), verbo


# La orden de una linea del redespliegue de siempre, la que mas se pega.
ORDEN_DE_SIEMPRE = ("docker compose -f servidor/docker-compose.yml up -d --build "
                    "copiloto-mcp")


@pytest.mark.parametrize("mutar", [
    lambda g: g + "\n```sh\ndocker volume rm copiloto-mcp_copiloto_bd_datos\n```\n",
    lambda g: g + ("\n```\ncd servidor\ndocker compose -p copiloto-mcp down "
                   "--remove-orphans --volumes\n```\n"),
    lambda g: g + "\n```\ndocker stop n8n\n```\n",
    lambda g: g.replace(ORDEN_DE_SIEMPRE, "docker compose -f servidor/docker-compose.yml"
                        " down -v && " + ORDEN_DE_SIEMPRE, 1),
    # la excepcion del caso local no vale fuera de el
    lambda g: g + "\n## 13. Otra cosa\n\n```bash\ndocker compose down\n```\n",
    lambda g: g + "\n```bash\ndocker system prune -a\n```\n",
    lambda g: g + "\n```bash\nsystemctl restart docker\n```\n",
], ids=["volume-rm-en-sh", "volumes-detras-sin-lenguaje", "stop-de-otro-contenedor",
        "down-v-en-la-orden-de-siempre", "excepcion-fuera-de-su-apartado",
        "prune", "reiniciar-docker"])
def test_la_comprobacion_de_la_guia_caza_las_ordenes_peligrosas(mutar):
    guia = _guia()
    assert ORDEN_DE_SIEMPRE in guia
    mutada = mutar(guia)
    assert mutada != guia
    assert _ordenes_que_no_valen(mutada) != []


def test_una_excepcion_que_la_guia_ya_no_lleva_se_dice():
    guia = _guia().replace("docker network rm copiloto-local", "docker network ls")
    assert _ordenes_que_no_valen(guia) == [
        ("Caso B: en local, para probar el despliegue desde cero",
         "docker network rm copiloto-local", "excepcion que la guia ya no lleva")]


def test_el_primer_redespliegue_no_baja_el_servicio_antes_de_construir():
    """El apartado lo sigue una persona en un servidor que comparte con otros
    servicios. Las ordenes que redespliegan construyen y recrean sin parar
    nada antes, y esperan a los dos contenedores; la unica orden que para algo
    es la bajada de reserva, que va por nombre de proyecto, sin volumenes y
    DESPUES de construir; la base y los contenedores se apuntan antes y se
    comparan despues; hay copia de la base; y la vuelta atras restaura el
    `.env` antes de levantar."""
    guia = _guia()
    inicio = guia.index("### El primer redespliegue con `RED_N8N` obligatoria")
    apartado = guia[inicio:guia.index("\n## 7. ", inicio)]
    bloques = [b for _, b in _bloques(apartado)]
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

    # el commit de vuelta: antes de apuntarlo, la guarda de que el codigo
    # nuevo no esta ya traido; y al reintentar, el de vuelta sigue siendo el
    # de la primera vez, no el de ahora
    guarda = "grep -c 'RED_N8N:?' /opt/copiloto/servidor/docker-compose.yml"
    assert any(guarda in b for b in bloques)
    assert apartado.index(guarda) < apartado.index("git rev-parse HEAD")
    seguido = " ".join(apartado.split())
    assert ("`git switch main`, y otra vez desde el punto 1. El commit de vuelta "
            "sigue siendo el que apuntaste la primera vez") in seguido

    # la copia de la base se restaura en una sola transaccion: si se
    # interrumpe, la base se queda como estaba
    (restaura,) = [b for b in bloques if "gunzip -c ~/copiloto-bd.antes-de-red_n8n.sql.gz" in b]
    assert re.search(r"docker exec -i copiloto-bd psql .*(?<![\w-])-1(?![\w-])", restaura)
    assert "-v ON_ERROR_STOP=1" in restaura

    # las copias se borran con `rm -f`: tambien si una de las dos no llego a hacerse
    borrar = [b for b in bloques if "antes-de-red_n8n" in b and re.search(r"(?<![\w-])rm ", b)]
    assert [b.strip() for b in borrar] == [
        "rm -f ~/copiloto.env.antes-de-red_n8n ~/copiloto-bd.antes-de-red_n8n.sql.gz"]


# --- Lo que sostiene la seguridad de la guia --------------------------------
#
# La guia apoya el `down` por proyecto en el `name:` del compose, la
# conservacion de la base en la clave de su volumen, y cita el compose por
# numero de linea. Si un cambio del compose toca cualquiera de esas cosas, la
# guia se queda mintiendo: el siguiente redespliegue crea un volumen nuevo y
# vacio, o `down -p copiloto-mcp` deja de identificar nada.

def _compose():
    return (RAIZ / "servidor" / "docker-compose.yml").read_text(encoding="utf-8")


def test_el_compose_es_el_que_la_guia_dice():
    compose = _compose()
    assert re.findall(r"^name:\s*(\S+)\s*$", compose, flags=re.M) == ["copiloto-mcp"]
    assert re.findall(r"^\s+container_name:\s*(\S+)\s*$", compose, flags=re.M) == [
        "copiloto-mcp", "copiloto-bd"]
    assert not re.search(r"^\s*ports\s*:", compose, flags=re.M), "no publica puertos"
    # la clave del volumen, declarada y montada; el volumen se llama
    # <proyecto>_<clave>: cambiar cualquiera de los dos es otra base
    assert re.search(r"^volumes:\s*\n\s+copiloto_bd_datos:\s*$", compose, flags=re.M)
    assert "- copiloto_bd_datos:/var/lib/postgresql/data" in compose


# Lo que la guia dice que dice cada linea del compose que cita por numero.
LINEAS_CITADAS = {5: "name: copiloto-mcp", 12: "image: copiloto-mcp:0.1.0"}


def test_las_lineas_del_compose_que_cita_la_guia_dicen_lo_que_la_guia_dice():
    guia = " ".join(_guia().split())
    citadas = {int(n) for n in re.findall(r"l[ií]nea (\d+) del compose", guia)}
    assert citadas == set(LINEAS_CITADAS), "una cita nueva necesita su fila aqui"
    assert "`copiloto-mcp:0.1.0` (línea 12 del compose)" in guia
    assert "la línea 5 del compose (`name: copiloto-mcp`)" in guia
    lineas = _compose().splitlines()
    for numero, dice in LINEAS_CITADAS.items():
        assert lineas[numero - 1].strip() == dice, numero


def test_la_salida_literal_del_paso_2_1_es_la_que_da_hoy_la_orden():
    """El paso 2.1 enseña la salida de un `grep` sobre el compose como
    «Salida literal». Aqui se aplica al compose la MISMA expresion que lleva
    la orden de la guia, y se compara linea a linea."""
    bloques = [b for apartado, b in _bloques(_guia()) if apartado.startswith("2.1.")]
    (i,) = [n for n, b in enumerate(bloques) if "grep -nE" in b and "docker-compose.yml" in b]
    expresion = re.search(r"grep -nE '([^']+)' docker-compose\.yml", bloques[i]).group(1)
    salida = [f"{n}:{linea}" for n, linea in enumerate(_compose().splitlines(), 1)
              if re.search(expresion, linea)]
    assert bloques[i + 1].splitlines() == salida
    assert len(salida) == 7, "la guia dice «Siete lineas»"