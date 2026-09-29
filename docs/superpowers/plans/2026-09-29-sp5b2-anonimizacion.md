# SP5-B2 — Anonimización de lo funcional y pruebas de anonimato: plan de implementación

> **Para trabajadores agénticos:** SUB-SKILL REQUERIDA: usa
> superpowers:subagent-driven-development (recomendado) o
> superpowers:executing-plans para ejecutar este plan tarea a tarea. Los pasos
> usan casillas (`- [ ]`) para el seguimiento.

**Objetivo:** dejar el árbol del repositorio sin ninguna cadena que
identifique al cliente, a la empresa, a la máquina ni a los integrantes, y sin
ningún secreto, de modo que el repositorio que se publique —nuevo, público y
de un solo commit (spec de SP5 §6.1)— se pueda construir desde
`git ls-files`; y dejar en la suite la prueba que lo vigila.

**Arquitectura:** los valores que identifican dejan de estar escritos y pasan
a venir de fuera: `N8N_URL` y `RSNA_RAIZ` sin valor por defecto, la red del
compose por `RED_N8N` obligatoria, y los workflows de n8n con **marcadores**
que una herramienta pone y quita (`scripts/marcadores_n8n.py`, con los valores
reales en un fichero ignorado). El resto es sustitución mecánica en la
documentación. La vigilancia no guarda la lista de lo prohibido: guarda una
**huella SHA-256 por token**, y la prueba tokeniza cada fichero de texto
versionado y falla si alguna huella aparece. Antes de publicar,
`scripts/verificar_anonimato.py` repite esa comprobación sobre el árbol del
repositorio nuevo y sobre los metadatos de su único commit, y busca además
patrones de secretos.

**Pila:** Python ≥ 3.11 (intérprete de la máquina de desarrollo:
`C:/venv-copiloto/Scripts/python.exe`), pytest, `node` para las pruebas
`.mjs`, `git`. Ninguna dependencia nueva.

**Spec:** `docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md`
— §6.1 (el repositorio que se publica, el inventario y las dos pruebas), §8
(«Anonimato»), §10 (riesgos: redesplegar el compose) y §11.5. Este plan
**prepara** el árbol y las pruebas; **no crea ni publica** el repositorio
nuevo: eso es del plan SP5-C, en la semana 6.

**Parte de:** `main` con SP5-B1 fusionado. Rama de trabajo:
`sp5b2-anonimizacion`.

## La regla que manda sobre este plan: no puede llevar lo que quita

Este documento se versiona y se publicará. **No contiene ninguna cadena de la
lista negra**, y quien lo ejecute tampoco las escribe en mensajes de commit,
en comentarios ni en nombres de fichero. Por eso:

- Lo que hay que **quitar** se identifica por fichero, número de línea (los
  del commit `1f328da`; si el fichero cambió, se localiza por la descripción)
  y descripción, o por un patrón que no contiene la cadena. Lo que hay que
  **poner** se cita entero.
- La **lista en claro** vive **fuera del repositorio**, en un fichero que el
  equipo guarda aparte; quien ejecuta el plan recibe su ruta en la variable
  de entorno `ANONIMATO_LISTA`. Tiene dos secciones: `[huellas]` (un token por
  línea, ya tokenizado) y `[sustituciones]` (`cadena => marcador`, de la más
  larga a la más corta: es la guía de la sustitución mecánica).
- Los scripts desechables que hagan sustituciones se crean en una carpeta
  temporal **fuera del repositorio**, leen las cadenas de `ANONIMATO_LISTA` y
  se borran al terminar. No se versionan.

## Restricciones globales

1. **Ninguna cadena que identifique** al cliente (dominio, red, contenedores,
   pila de mensajería, bots, ids de credenciales), a la empresa (correo,
   dominio), a la máquina (usuario, rutas absolutas) ni a los integrantes
   (nombres, filiación personal) en ningún fichero versionado. La universidad
   se conserva **solo** en el `README.md`, como institución del curso.
2. **Ningún secreto**: ni tokens, ni claves, ni contraseñas reales, ni `.env`,
   ni ficheros de claves. Los ficheros de configuración versionados llevan
   solo valores de ejemplo (`ejemplo.test`, `cambiar-esto`).
3. **No hay lista blanca.** Lo que se conserva —el huso `America/Guayaquil`,
   los `webhookId` de los workflows, los `chat_id` de prueba inventados, la
   IP de documentación `203.0.113.10`, el correo `noreply` de los pies de
   commit citados en los planes— se conserva porque no entra en la lista
   negra, no porque alguien lo exceptúe.
4. **Marcadores**, siempre los mismos: `https://n8n.ejemplo.test`; red
   `red_n8n` y variable `RED_N8N`; `<RSNA_RAIZ>`, `<carpeta-de-descarga>` y
   `<raiz-del-repositorio>` en la documentación; las credenciales de n8n, las
   de la tabla de la tarea 4.
5. **La suite queda verde en cada commit.** Lo que tiene que cambiar junto va
   en el mismo commit. `tests/test_anonimato.py` entra el último: antes
   nacería en rojo. **Las cuentas de pruebas de cada tarea** («N passed») son
   las de `main` con SP5-B1 fusionado y las tareas anteriores de este plan
   aplicadas, en una máquina sin Docker en marcha, sin secretos y sin
   base de datos. Antes de tocar nada, cada tarea corre su orden de partida
   y apunta la cifra: si no es la del plan, lo que tiene que cumplirse es la
   **diferencia**, y se dice en el informe.
6. **Las pruebas que dejan de poder correr se SALTAN con un mensaje que dice
   qué se queda sin verificar**; ninguna pasa a fallar ni desaparece. Tras
   este plan, en la máquina de desarrollo hay que tener puestas `RSNA_RAIZ` y,
   para las pruebas conducidas, `N8N_URL`: el plan dice dónde.
7. **Los exports de n8n se editan sin reformatear**: sustitución de texto
   exacta, exigiendo el número de apariciones esperado, y comprobando después
   que el JSON sigue siendo válido y que el `diff` enseña solo lo previsto.
   Desde este plan **los exports versionados ya no son idénticos byte a byte
   a lo desplegado**, y se dice donde se afirmaba lo contrario.
8. **Nada de este plan toca lo desplegado.** Ni el n8n del cliente, ni el VPS,
   ni los bots. Los cambios que exigen una acción en el servidor (volver a
   crear los contenedores con `RED_N8N`, poner `N8N_URL` en la tarea
   programada) se dejan escritos como órdenes para el equipo, que las ejecuta
   cuando le convenga y fuera de las fechas de la sesión con el médico.
9. **En `docs/superpowers/**` la sustitución es mecánica**: se cambian los
   identificadores, no se reescribe la prosa.
10. Mensajes de commit al estilo del repo, sin ninguna cadena de la lista, con
    la línea final `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Decisiones del plan

- **D1. Un solo mecanismo para los workflows.** Las URL de las sondas, los
  `id` de las seis credenciales y los nombres de las tres de Telegram pasan a
  marcadores; `scripts/marcadores_n8n.py` los pone (`aplicar`) antes de
  importar o desplegar desde el repo y los quita (`retirar`) antes de
  versionar un export. Los valores reales viven en `n8n/valores.local.json`,
  ignorado por git; `n8n/valores.ejemplo.json`, versionado, dice qué claves
  hacen falta.
- **D2. Los ids de las credenciales también.** El inventario del spec no los
  nombra, pero son identificadores de la instancia del cliente. Se tratan
  como el dominio.
- **D3. Los nombres de los bots del proyecto también.** Son cuentas reales de
  Telegram. En las pruebas `.mjs`, cualquier `/start@X` vale: pasa a
  `/start@BotDeEjemplo`.
- **D4. `raiz_rsna()` en `config.py`**, y no en un módulo nuevo: es el único
  módulo de configuración del paquete. La lectura es perezosa para que
  importar `pruebas/` no exija el dataset.
- **D5. `BASE_N8N` vacía, y el error en `main()`.** `tests/test_mantenimiento.py`
  importa `pruebas/verificar_webhooks.py` al cargarse: un error al importar
  rompería la colección de todo el fichero.
- **D6. Tokenización** (spec §6.1): minúsculas, sin tildes, partición por
  cualquier carácter que no sea `[a-z0-9]`. **Antes se quitan las tiradas de
  120 o más caracteres de `[A-Za-z0-9+/=]`**: las imágenes en base64 de los
  notebooks producen tokens al azar, y un token corto de la lista puede salir
  por casualidad. Esas imágenes se revisan a mano una vez y se declara
  (tarea 7).
- **D7. Los hallazgos nunca imprimen el token ni el secreto**: fichero, línea
  y huella o clase. La salida de la prueba también puede acabar publicada.
- **D9. Una huella no es un secreto, y eso cambia qué se publica.** El spec
  §6.1 pone `tests/anonimato/huellas.txt` en el repositorio. El SHA-256 de un
  token corto —un nombre, una palabra, un dominio de pocas letras— se adivina
  probando candidatos, así que publicar las huellas es publicar, para quien
  se tome la molestia, buena parte de la lista. **En el repositorio de
  desarrollo, que es privado, `huellas.txt` lleva la lista entera** (este
  plan). **En el repositorio que se publique llevará solo la huella del
  centinela**, y la comprobación de verdad se hace antes de publicar, con las
  huellas del repositorio de desarrollo: lo ejecuta el plan SP5-C al construir
  el árbol público, y lo decide el equipo. Este plan lo deja escrito en
  `tests/anonimato/README.md` (tarea 7).
- **D10. `RED_N8N` se declara una vez, en `servidor/.env`**, y no delante de
  cada orden de la guía (tarea 3): con la variable obligatoria, cualquier
  `docker compose` que lea el fichero la necesita, y la guía tiene más de
  veinte.
- **D8. Lo que no entra en la lista negra y por qué**: `C:\venv-copiloto` y
  `D:\corridas` (no llevan usuario), el código de la asignatura, `OneDrive`
  como palabra (las rutas que la contienen sí se sustituyen, porque llevan el
  usuario), y los nombres de productos genéricos de la pila de despliegue
  (`nginx`, `postgres`, `n8n`, `docker`).

## Estructura de ficheros

| Fichero | Tarea | Qué cambia |
| :--- | :--- | :--- |
| `pruebas/verificar_webhooks.py`, `pruebas/reproducir_casos.py`, `tests/conftest.py`, `tests/test_mantenimiento.py` | 1 | `N8N_URL` sin valor por defecto |
| `src/copiloto_triaje/config.py`, `scripts/preparar_sesion.py`, `pruebas/puntuaciones.py`, `pruebas/seleccionar_casos.py`, `tests/conftest.py`, `tests/test_contrato_mcp.py`, `tests/test_seleccion_casos.py`, `tests/test_flujo_profesional.py`, `tests/test_config.py` | 2 | `RSNA_RAIZ` |
| `scripts/comparar_corridas.py`, `docs/comparativa-corridas.md`, `scripts/entrenar_local.py`, `scripts/preparar_datos.py` | 2 | ninguna ruta de la máquina |
| `servidor/docker-compose.yml`, `servidor/.env.ejemplo`, `docs/sp2-despliegue.md`, `docs/sp3-operacion.md`, `tests/test_arrancar.py` | 3 | la red y su guía |
| `n8n/*.json`, `n8n/valores.ejemplo.json`, `scripts/marcadores_n8n.py`, `tests/test_marcadores_n8n.py`, `tests/test_mantenimiento.py`, `tests/test_flujo_paciente.py`, `tests/test_flujo_profesional.py`, `tests/*.mjs`, `docs/sp3-operacion.md`, `.gitignore` | 4 | marcadores en los workflows |
| `scripts/verificar_anonimato.py`, `tests/test_anonimato.py`, `tests/anonimato/huellas.txt`, `.gitignore` | 5 | la vigilancia: el mecanismo y sus pruebas |
| `docs/**`, `notebooks/eda_rsna.ipynb`, lo que quede; `tests/test_anonimato.py` | 6 | sustitución mecánica, y la prueba del árbol limpio |
| `tests/anonimato/README.md`, `tests/test_anonimato.py` | 7 | declaración de la revisión manual de los binarios |
| `README.md`, `docs/sp3-operacion.md` | 8 | lo que el equipo tiene que hacer en el servidor |
---

### Tarea 1: `N8N_URL` sin valor por defecto

**Ficheros:**
- Modificar: `pruebas/verificar_webhooks.py` (el docstring, la línea 54, el encabezado de `mensaje_para_telegram`, una función nueva `avisar_al_equipo` y `main()`)
- Modificar: `tests/test_mantenimiento.py` (el bloque de las pruebas de `diagnosticar`, líneas 496-550, dos aserciones en la prueba del aviso y seis pruebas nuevas al final)
- Modificar: `tests/conftest.py` (el docstring del módulo, líneas 8-19, y la fixture `webhook_n8n`, líneas 37-38)
- Crear: `tests/test_fijadores.py`
- Modificar: `pruebas/reproducir_casos.py` (la línea 61 del docstring, una función nueva `base_de_n8n` y dos puntos de `main()`)
- Modificar: `tests/test_reproducir_casos.py` (tres pruebas nuevas al final)

Los números de línea son los del commit `1f328da`, salvo los de
`pruebas/reproducir_casos.py`, que son los de `main` con SP5-B1 fusionado
(SP5-B1 le añadió 71 líneas por encima de `main()`; la 61 no se movió).

**Interfaces:**
- Consume: la variable de entorno `N8N_URL` (la URL base del n8n que sirve a los dos bots); las que ya
  leía cada script (`COPILOTO_CHAT_EQUIPO`, `TELEGRAM_TOKEN_AVISOS`, `TELEGRAM_TOKEN_PACIENTE`,
  `TELEGRAM_TOKEN_PROFESIONAL`, `COPILOTO_BD_DSN`, `TELEGRAM_SECRET_PRUEBA`).
- Produce, en `pruebas/verificar_webhooks.py`:
  - `BASE_N8N: str` — `N8N_URL` sin espacios ni barra final; **cadena vacía** si la variable falta.
    El módulo se importa sin la variable.
  - `SIN_N8N_URL: str` — el mensaje, con su «Qué hacer», que nombra `N8N_URL`.
  - `avisar_al_equipo(problemas: list, comprobado: bool = True) -> None` — el bloque que antes
    vivía al final de `main()`: manda `problemas` por Telegram si están `COPILOTO_CHAT_EQUIPO` y
    `TELEGRAM_TOKEN_AVISOS`, e imprime qué hizo.
  - `mensaje_para_telegram(problemas, comprobado=True) -> str` — con `comprobado` en `False` el
    encabezado dice que los webhooks NO se han comprobado; el de siempre no cambia.
  - `main() -> int` — con `BASE_N8N` vacía imprime `SIN_N8N_URL`, llama a
    `avisar_al_equipo([SIN_N8N_URL], comprobado=False)` y
    devuelve 1 **sin pedir ningún token, sin hablar con Telegram para leer nada y sin tocar la
    memoria** de la lectura anterior.
- Produce, en `tests/conftest.py`: la fixture `webhook_n8n` hace `pytest.skip` si `N8N_URL` falta,
  está vacía o solo tiene espacios; el motivo nombra `N8N_URL` y dice «pruebas conducidas».
- Produce, en `pruebas/reproducir_casos.py`: `base_de_n8n() -> str` (`N8N_URL` sin espacios a los
  lados; `SystemExit` con un mensaje que nombra `N8N_URL` y `--sin-bots` si falta o está vacía);
  `main()` la llama solo en el modo con bots, antes de comprobar el copiloto.
- Produce, en `tests/test_mantenimiento.py`: la constante `BASE = "https://n8n.ejemplo.test"` y la
  fixture `autouse` `_base_de_n8n_fija`, que fija `vw.BASE_N8N` a `BASE` en cada prueba del fichero.

**Notas para quien ejecuta:**
- Las órdenes se corren desde la raíz del repo. Los ficheros tienen fines de línea CRLF en el árbol
  de trabajo: edítalos con la herramienta de edición, no los reescribas enteros.
- Los textos que esta tarea QUITA llevan la URL de un despliegue real, y este plan no puede
  escribirla: se identifican por número de línea y por un patrón con `…` en su lugar. Los textos
  que PONE van enteros.
- Esta tarea **no toca** la línea 181 de `tests/test_mantenimiento.py`, ni sus líneas 38-39, ni los
  workflows de `n8n/`: son de la tarea 4. Hasta que la tarea 4 se aplique, `tests/test_mantenimiento.py`
  sigue llevando esas tres líneas con identificadores; es lo esperado.
- Las pruebas conducidas (las clases `TestConducido` de `tests/test_flujo_paciente.py` y
  `tests/test_flujo_profesional.py`) necesitan un n8n vivo, la base y los secretos. En una máquina
  sin ellos **se saltan antes y después** de esta tarea, y con el mismo motivo (el `skipif` de su
  clase, que mira los secretos y se evalúa antes que la fixture): 7 y 8 saltadas. Su verde solo se
  puede ver en la máquina que tiene el entorno, y desde esta tarea esa máquina tiene que tener
  además `N8N_URL` puesta.
- Antes de empezar, el punto de partida (sin `N8N_URL` en el entorno):

  Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_mantenimiento.py tests/test_reproducir_casos.py tests/test_flujo_paciente.py tests/test_flujo_profesional.py`
  Esperado: `101 passed, 15 skipped` (28 de mantenimiento; 30 del arnés; 13 y 7 saltadas del
  paciente; 30 y 8 saltadas del profesional).

#### Commit (a): `verificar_webhooks.py` y sus pruebas

- [ ] **Paso 1: Ver que las pruebas del diagnóstico dependen hoy del entorno**

Run (bash): `N8N_URL=https://otro.ejemplo.test C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_mantenimiento.py`
Esperado: `4 failed, 24 passed`. Fallan `test_un_webhook_correcto_no_da_ningun_problema`,
`test_un_403_en_last_error_apunta_al_secret_token`,
`test_un_404_en_last_error_apunta_al_workflow_desactivado` y
`test_la_cola_pendiente_solo_avisa_cuando_CRECE`: las cuatro usan `BIEN`, que lleva escrita la URL
por defecto, y `diagnosticar` compara con la base que el módulo leyó del entorno al importarse.

- [ ] **Paso 2: Desacoplar del entorno el bloque del diagnóstico**

En `tests/test_mantenimiento.py`, las líneas 501-502 asignan `BIEN`: un diccionario cuya `url` es
una cadena literal con la URL por defecto (patrón `BIEN = {"url": "https://…/webhook/copiloto-paciente",`
y, en la línea siguiente, `"pending_update_count": 0}`). Sustituye esas dos líneas por:

```python
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
```

En el mismo fichero, la línea 523 (dentro de
`test_el_webhook_del_otro_bot_es_el_error_silencioso_del_manual`) pasa a `diagnosticar` una `url`
literal con la misma URL y la ruta `copiloto-profesional` (patrón
`p = diagnosticar({"url": "https://…/webhook/copiloto-profesional",`). Sustituye esa línea por:

```python
    p = diagnosticar({"url": f"{BASE}/webhook/copiloto-profesional",
```

La fixture es `autouse` a nivel de módulo: se aplica a todas las pruebas del fichero, también a las
que no miran `BASE_N8N`, y no les cambia nada.

- [ ] **Paso 3: Añadir las pruebas nuevas**

En la prueba que ya estaba,
`test_el_aviso_de_la_tarea_programada_lleva_los_problemas_y_no_el_token`, las pruebas guardaban
la URL a la que se llamó y no la miraban. Busca:

```python
    assert ok is True, detalle
    assert enviados["cuerpo"]["chat_id"] == "987"
```

y sustitúyelo por (el token es inventado):

```python
    assert ok is True, detalle
    assert enviados["url"] == "https://api.telegram.org/botT0K3N/sendMessage"
    assert enviados["cuerpo"]["chat_id"] == "987"
    assert "el webhook de Telegram no está como debe" in enviados["cuerpo"]["text"]
```

Al final de `tests/test_mantenimiento.py`, después de
`test_un_token_revocado_se_distingue_de_un_problema_de_url`, añade (con dos líneas en blanco de
separación):

```python
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
```

- [ ] **Paso 4: Correr las pruebas y ver que fallan**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_mantenimiento.py`
Esperado: `4 failed, 32 passed`. Fallan:
- `test_el_script_se_importa_sin_N8N_URL_y_no_trae_ninguna_por_defecto`, en dos de sus tres
  casos: con la variable ausente `BASE_N8N` trae la URL por defecto en vez de `""`, y con la
  variable en blanco se queda con los espacios (el caso de la variable vacía ya pasa);
- `test_sin_N8N_URL_main_sale_con_un_mensaje_y_no_pide_ningun_token` y
  `test_sin_N8N_URL_la_tarea_programada_avisa_por_telegram`: las dos con
  `AssertionError: main() siguió adelante sin N8N_URL`, lanzado desde el `getpass` falso.

Las del diagnóstico ya pasan: la fixture las ha desacoplado. Y
`test_los_problemas_de_una_lectura_de_verdad_llegan_al_canal_de_avisos` también pasa: fija lo
que el final de `main()` ya hacía y ninguna prueba vigilaba.

- [ ] **Paso 5: Quitar el valor por defecto de `pruebas/verificar_webhooks.py`**

Cinco ediciones.

(1) En el docstring del módulo, después de la línea 36
(`Devuelve 0 si los dos webhooks estan como deben, y 1 si hay algo que arreglar.`) y de la línea en
blanco que la sigue, inserta este párrafo y una línea en blanco detrás, de modo que quede antes de
`PARA LA TAREA PROGRAMADA DIARIA`:

```text
`N8N_URL` ES OBLIGATORIA y no tiene valor por defecto: es la URL base del n8n
que sirve a los dos bots (por ejemplo `https://n8n.ejemplo.test`), y con ella se
calcula donde tendria que estar entregando Telegram. El repositorio no lleva la
de ningun despliegue. Sin ella el script no pide ningun token ni comprueba nada:
dice que falta, lo manda por Telegram si el canal de avisos esta puesto, y
devuelve 1.
```

(2) La línea 54 asigna `BASE_N8N` con un valor por defecto (patrón
`BASE_N8N = os.environ.get("N8N_URL", "https://…").rstrip("/")`). Sustitúyela por:

```python
# Sin valor por defecto, y sin fallar al importar: `tests/test_mantenimiento.py`
# importa este modulo para probar el diagnostico, y tiene que poder hacerlo en
# una maquina que no sabe de ningun n8n. Quien se niega a seguir es `main()`.
BASE_N8N = os.environ.get("N8N_URL", "").strip().rstrip("/")

SIN_N8N_URL = (
    "Falta N8N_URL: sin ella no se sabe en qué URL tendría que estar "
    "entregando Telegram, y no se ha comprobado ningún webhook.\n"
    "   Qué hacer: pon en N8N_URL la URL base del n8n que sirve a los dos bots "
    "(por ejemplo https://n8n.ejemplo.test), en el entorno de quien corre el "
    "script; si lo corre la tarea programada, en la tarea.")
```

(3) Justo antes de `def main() -> int:` (línea 215), añade la función `avisar_al_equipo`, y dentro
de `main()`, antes de su primera línea (`memoria = _memoria_leer()`), la guarda. El principio de
`main()` queda así:

```python
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


def main() -> int:
    if not BASE_N8N:
        # Antes de pedir ningun token y de tocar la memoria: sin la base no hay
        # con que comparar, y una lectura a medias borraria la de ayer.
        print(SIN_N8N_URL)
        avisar_al_equipo([SIN_N8N_URL], comprobado=False)
        return 1
    memoria = _memoria_leer()
```

(4) Al final de `main()`, las líneas 249-260 (el comentario «El canal de la tarea programada», las
dos lecturas de `COPILOTO_CHAT_EQUIPO` y `TELEGRAM_TOKEN_AVISOS`, y el `if`/`elif` que avisa) se
sustituyen por una llamada. Busca exactamente:

```python
    _memoria_escribir(nueva)

    # El canal de la tarea programada: sin esto, lo de arriba acaba en un log
    # que nadie abre.
    chat = os.environ.get("COPILOTO_CHAT_EQUIPO", "").strip()
    token_avisos = os.environ.get("TELEGRAM_TOKEN_AVISOS", "").strip()
    if problemas_todos and chat and token_avisos:
        enviado, detalle = avisar_por_telegram(
            token_avisos, chat, mensaje_para_telegram(problemas_todos))
        print("\naviso por Telegram: "
              + ("enviado." if enviado else f"NO se pudo enviar ({detalle})."))
    elif problemas_todos and (chat or token_avisos):
        print("\naviso por Telegram: no se manda, faltan COPILOTO_CHAT_EQUIPO o "
              "TELEGRAM_TOKEN_AVISOS (hacen falta las dos).")
```

y sustitúyelo por:

```python
    _memoria_escribir(nueva)
    avisar_al_equipo(problemas_todos)
```

(5) El encabezado del aviso. Sin `N8N_URL` no se ha comprobado ningún webhook, y el aviso no
puede decir que uno «no está como debe»: quien lea solo la notificación iría a registrar otra
vez un webhook que estaba bien. En `mensaje_para_telegram`, busca:

```python
def mensaje_para_telegram(problemas):
    """El mismo formato que el aviso del workflow: encabezado, y cada problema
    con su «Que hacer». Recortado al limite de Telegram, que son 4096."""
    cabeza = ("\U0001fa7a Copiloto Triaje — el webhook de Telegram no está como "
              "debe\n\n(lo dice pruebas/verificar_webhooks.py, que es la mitad "
              "de la sexta comprobación del §16 que no cabe dentro de n8n)\n")
```

y sustitúyelo por:

```python
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
```

El encabezado de siempre no cambia ni una letra.

- [ ] **Paso 6: Correr las pruebas y ver que pasan, con la variable y sin ella**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_mantenimiento.py`
Esperado: `36 passed`.

Run (bash): `N8N_URL=https://otro.ejemplo.test C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_mantenimiento.py`
Esperado: `36 passed` (en el paso 1 eran 4 fallos).

Run (bash): `env -u N8N_URL C:/venv-copiloto/Scripts/python.exe -B pruebas/verificar_webhooks.py; echo "codigo=$?"`
Esperado: el script no pide ningún token; imprime las dos líneas de `SIN_N8N_URL` («Falta N8N_URL:
…» y «Qué hacer: …») y después `codigo=1`. Si en ese entorno están `COPILOTO_CHAT_EQUIPO` y
`TELEGRAM_TOKEN_AVISOS`, además manda el aviso: córrelo en una consola que no las tenga.

- [ ] **Paso 7: Commit**

```bash
git add pruebas/verificar_webhooks.py tests/test_mantenimiento.py
git commit -m "fix(anonimato): verificar_webhooks sin N8N_URL por defecto (SP5-B2 T1)" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

#### Commit (b): la fixture `webhook_n8n`

- [ ] **Paso 8: Escribir la prueba que falla**

`tests/test_fijadores.py` (fichero nuevo):

```python
# -*- coding: utf-8 -*-
"""Los fijadores de `tests/conftest.py`, probados sin red.

`webhook_n8n` habla con un n8n de verdad, y el repositorio no lleva la URL de
ninguno: la pone quien corre la suite, en `N8N_URL`. Lo que se comprueba aqui es
la puerta, que es lo unico que se puede comprobar sin ese n8n: sin la variable
la prueba que pida el fijador se SALTA -no falla, y sobre todo no manda nada a
ningun sitio-, y con ella se habla a esa URL y a ninguna otra.

La funcion del fijador se llama a traves de `__wrapped__`: pytest no deja llamar
a un fijador directamente, pero guarda ahi la funcion que decoro.
"""
import json

import pytest

import conftest

fijador = conftest.webhook_n8n.__wrapped__


def _sin_red(monkeypatch):
    """Cualquier intento de salir a la red hace fallar la prueba."""
    monkeypatch.setattr(
        conftest.urllib.request, "urlopen",
        lambda *a, **k: pytest.fail("el fijador salió a la red"))


@pytest.mark.parametrize("valor", [None, "", "   "],
                         ids=["ausente", "vacia", "en-blanco"])
def test_sin_N8N_URL_el_fijador_salta_y_dice_que_se_queda_sin_correr(
        monkeypatch, valor):
    if valor is None:
        monkeypatch.delenv("N8N_URL", raising=False)
    else:
        monkeypatch.setenv("N8N_URL", valor)
    _sin_red(monkeypatch)

    with pytest.raises(pytest.skip.Exception) as salto:
        fijador()

    motivo = str(salto.value)
    assert "N8N_URL" in motivo
    assert "pruebas conducidas" in motivo


def test_con_N8N_URL_el_fijador_habla_con_esa_url_y_con_ninguna_otra(monkeypatch):
    monkeypatch.setenv("N8N_URL", "https://otro.ejemplo.test/")
    pedidas = []

    def falso(pet, timeout=0):
        pedidas.append(pet)

        class R:
            status = 200

            def read(self_inner):
                return b"hecho"
        return R()

    monkeypatch.setattr(conftest.urllib.request, "urlopen", falso)

    enviar = fijador()
    assert enviar("copiloto-paciente", {"a": 1}, "S3CR3T0") == (200, "hecho")

    (pet,) = pedidas
    assert pet.full_url == "https://otro.ejemplo.test/webhook/copiloto-paciente"
    assert json.loads(pet.data) == {"a": 1}
    assert pet.get_header("X-telegram-bot-api-secret-token") == "S3CR3T0"
```

- [ ] **Paso 9: Correr la prueba y ver que falla**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_fijadores.py`
Esperado: `3 failed, 1 passed`. Fallan los tres casos de
`test_sin_N8N_URL_el_fijador_salta_y_dice_que_se_queda_sin_correr` (`ausente`, `vacia`,
`en-blanco`) con `Failed: DID NOT RAISE`: la fixture no salta, toma la URL por defecto. La prueba
no sale a la red: la fixture solo construye la función.

- [ ] **Paso 10: Hacer que la fixture salte, y corregir el docstring del módulo**

En `tests/conftest.py`, dos ediciones.

(1) El docstring del módulo, líneas 8-19: son los dos párrafos que van desde la línea que empieza
por `OJO, QUE ESTE DOCSTRING DECIA LO CONTRARIO` hasta la que empieza por
`del cliente desde cualquier maquina`, ambas incluidas (con una línea en blanco entre los dos
párrafos). Dicen lo contrario de lo que pasa a ser cierto y nombran la URL por defecto. Sustituye
esas doce líneas por:

```text
`webhook_n8n` SALTA SIN `N8N_URL`. La variable dice a que n8n se habla y no
tiene valor por defecto: el repositorio no lleva la URL de ningun despliegue,
asi que sin ella las pruebas conducidas se saltan, y lo dicen. Es la primera
guarda. La segunda son los `skipif` de cada clase de pruebas por sus SECRETOS
-`TELEGRAM_SECRET_PRUEBA`, `TELEGRAM_TOKEN_PROFESIONAL`,
`CHAT_SUBIDA_PLACAS`-: sin el secreto no se pasa la puerta del secret_token del
§4.2, asi que la peticion no llega a ningun sitio. El fijador `bd_sp3` de abajo
salta por `COPILOTO_BD_DSN`.

Las dos guardas hacen falta. En la maquina que SI tiene `N8N_URL` el fijador no
salta, y una prueba nueva que use `webhook_n8n` sin guardar su secreto mandaria
trafico a ese n8n cada vez que alguien corra la suite alli.
```

(2) En la fixture `webhook_n8n`, la línea 37 cierra el docstring (`    """`) y la 38 asigna `base`
con un valor por defecto (patrón `base = os.environ.get("N8N_URL", "https://…").rstrip("/")`).
Sustituye esas dos líneas por:

```python

    Sin `N8N_URL` la prueba que lo pide se salta: no hay n8n por defecto.
    """
    base = os.environ.get("N8N_URL", "").strip().rstrip("/")
    if not base:
        pytest.skip(
            "sin N8N_URL no se sabe a qué n8n hablar: las pruebas conducidas "
            "de los dos bots se quedan sin correr. Para correrlas, pon en "
            "N8N_URL la URL base del n8n que los sirve, además de los secretos "
            "de cada prueba")
```

Lo que sigue (`def enviar(...)` y `return enviar`) no cambia.

- [ ] **Paso 11: Correr las pruebas y ver que pasan**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_fijadores.py`
Esperado: `4 passed`.

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q -rs tests/test_flujo_paciente.py tests/test_flujo_profesional.py`
Esperado, en una máquina sin los secretos: `43 passed, 15 skipped`, y los quince motivos son los de
antes (los de `TELEGRAM_SECRET_PRUEBA`, `TELEGRAM_TOKEN_PROFESIONAL` y `CHAT_SUBIDA_PLACAS`).
Ninguno nombra `N8N_URL` porque el `skipif` de la clase se evalúa antes que la fixture.

- [ ] **Paso 12: Commit**

```bash
git add tests/conftest.py tests/test_fijadores.py
git commit -m "fix(anonimato): webhook_n8n salta sin N8N_URL (SP5-B2 T1)" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

#### Commit (c): `reproducir_casos.py`

- [ ] **Paso 13: Escribir las pruebas que fallan**

Al final de `tests/test_reproducir_casos.py`, añade (con dos líneas en blanco de separación):

```python
# --------------------------------------------------------------------------
# `N8N_URL` no tiene valor por defecto: con los bots es obligatoria.
# --------------------------------------------------------------------------
def _entorno_con_bots(monkeypatch, tmp_path, *argumentos):
    """Los tres secretos que eligen el modo con bots, inventados, y `main()`
    sin copiloto ni base: si llega a buscarlos, la prueba falla en vez de salir
    a la red."""
    from pruebas import reproducir_casos as rc

    for variable in ("COPILOTO_BD_DSN", "TELEGRAM_SECRET_PRUEBA",
                     "TELEGRAM_TOKEN_PROFESIONAL"):
        monkeypatch.setenv(variable, "inventado")
    monkeypatch.delenv("N8N_URL", raising=False)
    monkeypatch.setattr(sys, "argv", ["reproducir_casos.py", "--salida",
                                      str(tmp_path), *argumentos])

    class Llego(Exception):
        pass

    def llego(*a, **k):
        raise Llego()

    monkeypatch.setattr(rc, "comprobar_el_copiloto", llego)
    monkeypatch.setattr(rc, "_conectar", llego)
    return rc, Llego


def test_la_base_de_n8n_sale_de_N8N_URL_y_de_ningun_otro_sitio(monkeypatch):
    from pruebas.reproducir_casos import base_de_n8n

    monkeypatch.setenv("N8N_URL", " https://otro.ejemplo.test/ ")
    assert base_de_n8n() == "https://otro.ejemplo.test/"
    for vacia in ("", "   "):
        monkeypatch.setenv("N8N_URL", vacia)
        with pytest.raises(SystemExit) as salida:
            base_de_n8n()
        assert "N8N_URL" in str(salida.value)
    monkeypatch.delenv("N8N_URL")
    with pytest.raises(SystemExit) as salida:
        base_de_n8n()
    assert "N8N_URL" in str(salida.value) and "--sin-bots" in str(salida.value)


def test_con_los_bots_y_sin_N8N_URL_el_arnes_sale_antes_de_empezar(
        monkeypatch, tmp_path, capsys):
    """Antes el arnes hablaba con un n8n por defecto. Ahora, con los secretos
    puestos y sin la URL, sale diciendo que variable falta, y lo hace antes de
    comprobar el copiloto, de elegir los casos y de abrir la base."""
    rc, _ = _entorno_con_bots(monkeypatch, tmp_path)

    with pytest.raises(SystemExit) as salida:
        rc.main()

    assert "N8N_URL" in str(salida.value)
    assert salida.value.code != 0
    assert list(tmp_path.iterdir()) == []


def test_sin_bots_el_arnes_no_pide_N8N_URL(monkeypatch, tmp_path, capsys):
    rc, Llego = _entorno_con_bots(monkeypatch, tmp_path, "--sin-bots")

    with pytest.raises(Llego):
        rc.main()

    assert "MODO SIN BOTS (--sin-bots)" in capsys.readouterr().out
```

- [ ] **Paso 14: Correr las pruebas y ver que fallan**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_reproducir_casos.py`
Esperado: `2 failed, 31 passed`. Fallan:
- `test_la_base_de_n8n_sale_de_N8N_URL_y_de_ningun_otro_sitio`, con
  `ImportError: cannot import name 'base_de_n8n'`;
- `test_con_los_bots_y_sin_N8N_URL_el_arnes_sale_antes_de_empezar`, con la excepción `Llego`
  lanzada desde `comprobar_el_copiloto`: `main()` no sale, sigue adelante.

`test_sin_bots_el_arnes_no_pide_N8N_URL` ya pasa: fija lo que no tiene que cambiar.

- [ ] **Paso 15: Hacer `N8N_URL` obligatoria con los bots**

En `pruebas/reproducir_casos.py`, cuatro ediciones.

(1) En el docstring, bloque `ENTORNO`, la línea 61 documenta el valor por defecto (patrón
`    N8N_URL                      por defecto https://…`). Sustitúyela por:

```text
    N8N_URL                      OBLIGATORIA con los bots, y sin valor por
                                 defecto: la URL base del n8n que los sirve
                                 (por ejemplo https://n8n.ejemplo.test). Si
                                 falta, el arnes sale diciendolo antes de
                                 empezar. Con --sin-bots no hace falta
```

(2) Justo antes de `def main() -> int:` (línea 1334), añade:

```python
def base_de_n8n() -> str:
    """La URL base del n8n de los bots. Sale de `N8N_URL` y de ningun otro
    sitio: el repositorio no lleva la de ningun despliegue, y un valor por
    defecto mandaria las conversaciones de prueba a un n8n que nadie eligio."""
    base = os.environ.get("N8N_URL", "").strip()
    if not base:
        raise SystemExit(
            "falta N8N_URL: con los bots el arnés conduce las conversaciones "
            "contra un n8n, y no hay ninguno por defecto.\n"
            "Pon en N8N_URL la URL base del n8n que sirve a los dos bots (por "
            "ejemplo https://n8n.ejemplo.test), o corre con --sin-bots.")
    return base
```

(3) En `main()`, después de la línea 1360 (`    con_bots = not args.sin_bots and not falta`),
añade:

```python
    # Aqui, y no al construir `Bots`: antes de comprobar el copiloto, de elegir
    # los casos y de abrir la base. Si falta, no se ha tocado nada.
    base_n8n = base_de_n8n() if con_bots else None
```

(4) La línea 1387, dentro de `bots = Bots(`, pasa `base` con un valor por defecto (patrón
`            base=os.environ.get("N8N_URL", "https://…"),`). Sustitúyela por:

```python
            base=base_n8n,
```

- [ ] **Paso 16: Correr las pruebas y ver que pasan**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_reproducir_casos.py`
Esperado: `33 passed`.

Run (bash): `env -u N8N_URL COPILOTO_BD_DSN=x TELEGRAM_SECRET_PRUEBA=x TELEGRAM_TOKEN_PROFESIONAL=x C:/venv-copiloto/Scripts/python.exe -B pruebas/reproducir_casos.py; echo "codigo=$?"`
Esperado: dos líneas («falta N8N_URL: con los bots el arnés conduce las conversaciones contra un
n8n, y no hay ninguno por defecto.» y «Pon en N8N_URL la URL base … o corre con --sin-bots.») y
`codigo=1`, de inmediato: no llega a comprobar el copiloto ni a abrir la base.

- [ ] **Paso 17: Comprobar que no queda ningún valor por defecto, y la suite de los ficheros tocados**

Run: `git grep -n -E "environ\.get\(.N8N_URL., *.http" -- pruebas tests scripts src`
Esperado: ninguna línea (el `grep` sale con 1).

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_mantenimiento.py tests/test_fijadores.py tests/test_reproducir_casos.py tests/test_flujo_paciente.py tests/test_flujo_profesional.py`
Esperado: `116 passed, 15 skipped` (eran `101 passed, 15 skipped`: las 15 de más son las 8 nuevas de
mantenimiento, las 4 de los fijadores y las 3 del arnés). El mismo resultado con
`N8N_URL=https://otro.ejemplo.test` delante de la orden.

- [ ] **Paso 18: Commit**

```bash
git add pruebas/reproducir_casos.py tests/test_reproducir_casos.py
git commit -m "fix(anonimato): reproducir_casos exige N8N_URL con los bots (SP5-B2 T1)" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

- [ ] **Paso 19: Verificación en la máquina que tiene el entorno (la hace una persona)**

Esta tarea cambia lo que hace falta para correr tres cosas que hablan con el n8n desplegado. No se
puede comprobar sin él; queda para quien lo tiene:

1. **La tarea programada diaria** que corre `pruebas/verificar_webhooks.py` (§5 del manual de
   operación) necesita `N8N_URL` en su entorno **antes** de recibir este cambio. Si no la tiene,
   desde el primer día devuelve 1 y avisa por Telegram con el texto de `SIN_N8N_URL` (si tiene el
   canal de avisos puesto), en vez de comprobar los webhooks.
2. **Las pruebas conducidas**: con `N8N_URL`, los secretos y el túnel,
   `C:/venv-copiloto/Scripts/python.exe -m pytest -q -rs tests/test_flujo_paciente.py tests/test_flujo_profesional.py`
   tiene que dar 0 saltadas por `N8N_URL` y el mismo verde que antes del cambio.
3. **El arnés con bots**: `pruebas/reproducir_casos.py --por-perfil 1` con `N8N_URL` puesta arranca
   como antes.
---

### Tarea 2: `RSNA_RAIZ`, y ninguna ruta de la máquina en el código

**Ficheros:**
- Modificar: `src/copiloto_triaje/config.py` (gana `raiz_rsna()`)
- Modificar: `scripts/preparar_sesion.py` (importa la de `config` y borra la suya)
- Modificar: `pruebas/puntuaciones.py`, `pruebas/seleccionar_casos.py` (fuera las constantes de módulo; lectura perezosa)
- Modificar: `tests/conftest.py` (fixtures `rsna_raiz` y `pesos_desplegados`, al final)
- Modificar: `tests/test_contrato_mcp.py`, `tests/test_seleccion_casos.py`, `tests/test_flujo_profesional.py`
- Modificar: `scripts/entrenar_local.py`, `scripts/preparar_datos.py` (solo el docstring de uso)
- Modificar: `scripts/comparar_corridas.py` y `docs/comparativa-corridas.md` (tabla «Procedencia»)
- Crear: `tests/test_entorno_de_datos.py`
- Prueba: `tests/test_config.py`, `tests/test_sesion.py`, `tests/test_puntuaciones.py`, `tests/test_seleccion_casos.py`, `tests/test_entorno_de_datos.py`, `tests/test_comparar_corridas.py`

**Interfaces:**
- Produce: `copiloto_triaje.config.raiz_rsna() -> pathlib.Path`. Lee `RSNA_RAIZ`
  en cada llamada; si falta, está vacía o son solo espacios, `SystemExit` con
  `RSNA_RAIZ` en el mensaje. No comprueba que la carpeta exista.
- Produce, en `tests/conftest.py`: las funciones `raiz_rsna_o_salta()` y
  `pesos_desplegados_o_salta()` y las fixtures de módulo `rsna_raiz` y
  `pesos_desplegados`, que las llaman.
- Produce: `comparar_corridas.reporte_sin_ruta(ruta_json) -> str`
  (`<carpeta de la corrida>/<fichero>`, siempre con `/`).
- Consume: nada de otras tareas de este plan. `tests/test_contrato_sp4.py`
  importa la fixture `dicom_adulto` de `tests/test_contrato_mcp.py` y NO se
  toca: la fixture pide `rsna_raiz`, que pytest encuentra en `conftest.py`.
- Desaparecen: `pruebas.puntuaciones.RAIZ`, `pruebas.seleccionar_casos.RAIZ`,
  `pruebas.seleccionar_casos.CRUDO`, `tests/test_contrato_mcp.CRUDO` y
  `preparar_sesion.raiz_rsna` como función propia (queda el nombre, importado).
  Nadie los usaba desde fuera.

**Qué pasa en cada máquina (decidido y probado).** `RSNA_RAIZ` es la carpeta
que tiene dentro `manifiestos/`, `png/` y `crudo/stage_2_train_images/`. Los
pesos (`servidor/pesos_modelo_cpu.pt`) y la caché de puntuaciones
(`pruebas/crudas_prueba.csv` y su `.sha256`) no se versionan.

| Escenario | `tests/test_seleccion_casos.py` | `tests/test_contrato_mcp.py` (con el servidor vivo) |
| :--- | :--- | :--- |
| Máquina de desarrollo: `RSNA_RAIZ`, pesos y caché | 9 pasan | 10 pasan |
| Clon limpio: sin variable, sin pesos, sin caché | 4 pasan, 5 se saltan («falta RSNA_RAIZ») | 2 pasan, 8 se saltan («falta RSNA_RAIZ») |
| Máquina de desarrollo SIN la variable (pesos y caché sí) | 4 pasan, 5 se saltan («falta RSNA_RAIZ») | 2 pasan, 8 se saltan |
| `RSNA_RAIZ` puesta con el dataset, sin pesos (con o sin caché) | 4 pasan, 5 se saltan («faltan los pesos desplegados») | 8 pasan, 2 se saltan (las del recorte) |
| `RSNA_RAIZ` puesta con el dataset y pesos, sin caché | 9 pasan; la primera vez infiere sobre las 3 811 imágenes (minutos) | 10 pasan, igual |
| `RSNA_RAIZ` apunta a una carpeta que no tiene el dataset | con pesos y caché, falla `test_todos_los_ficheros_existen` | 6 ERROR con `FileNotFoundError` y la ruta que falta |

La última fila es a propósito: una variable mal escrita tiene que verse, no
saltarse. Sin servidor, `tests/test_contrato_mcp.py` sigue saltándose entero
con el mensaje de `copiloto_vivo`, que va primero (por eso las fixtures nuevas
son de módulo y no de sesión: pytest prepara antes lo de alcance mayor).

Fuera de las pruebas: `pruebas/seleccionar_casos.py`,
`pruebas/reproducir_casos.py` (salvo con `--casos`, que no selecciona) y, con
la caché fría, `pruebas/caracterizar_conjunto.py`, se detienen sin la variable
con `falta RSNA_RAIZ: la raíz del dataset preparado, sin valor por defecto
(spec de SP5 §6.1)`. `pruebas/caracterizar_conjunto.py` con la caché al día no
la pide.

**Avisos para quien ejecuta.**
- Los números de línea son los del commit `1f328da`, ANTES de cualquier
  edición de esta tarea; los de `scripts/preparar_sesion.py`, los de `main`
  con SP5-B1 fusionado, que le añadió dos líneas al docstring. Dentro de un
  fichero, edita de abajo arriba o guíate por el texto del ancla.
- Casi todos estos ficheros tienen finales de línea CRLF en el árbol de
  trabajo (`tests/conftest.py`, LF). Edita con una herramienta que los
  conserve; `sed -i` de Git Bash los cambia a LF.
- Las líneas que se QUITAN llevan el usuario de la máquina y por eso aquí no
  se citan: se identifican por número y descripción.
- No corras la suite entera para comprobar esta tarea:
  `tests/test_mantenimiento.py` arranca un contenedor de Docker si lo
  encuentra. Todas las órdenes de abajo nombran ficheros o lo excluyen con
  `--ignore`.
- Las órdenes llevan `env -u RSNA_RAIZ` (Git Bash) para que la salida sea la
  misma en cualquier máquina. La comprobación con la variable puesta es el
  último paso.
- Esta tarea mueve líneas en `tests/test_flujo_profesional.py`, que la tarea 4
  también edita por número: lo que estaba por debajo de la línea 115 baja 2;
  por debajo de la 347, baja 3; por debajo de la 414, baja 4 (las líneas 161 y
  164 pasan a 163 y 166; 481 y 486, a 485 y 490; 790, a 794).

---

#### Commit A — `raiz_rsna()` en `config.py`, y el script de la sesión la importa

- [ ] **Paso 1: Las pruebas de `raiz_rsna()`**

En `tests/test_config.py`, la línea 3 (`from copiloto_triaje.config import Config`)
pasa a:

```python
from copiloto_triaje.config import Config, raiz_rsna
```

Y al final del fichero, después de `test_un_margen_negativo_se_rechaza`, añade:

```python


def test_raiz_rsna_devuelve_la_carpeta_de_la_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("RSNA_RAIZ", str(tmp_path))
    assert raiz_rsna() == tmp_path
    assert isinstance(raiz_rsna(), Path)


def test_raiz_rsna_se_lee_en_cada_llamada_y_no_al_importar(tmp_path, monkeypatch):
    """Perezosa: quien cambia la variable despues de importar el modulo ve el
    valor nuevo. Si se leyera al importar, los modulos que la usan no se
    podrian ni importar en una maquina sin dataset."""
    monkeypatch.setenv("RSNA_RAIZ", str(tmp_path / "una"))
    assert raiz_rsna() == tmp_path / "una"
    monkeypatch.setenv("RSNA_RAIZ", str(tmp_path / "otra"))
    assert raiz_rsna() == tmp_path / "otra"


@pytest.mark.parametrize("valor", [None, "", "   "])
def test_sin_rsna_raiz_se_detiene_y_nombra_la_variable(valor, monkeypatch):
    """No hay valor por defecto (spec de SP5 §6.1): una ruta por defecto seria
    la de una maquina concreta."""
    if valor is None:
        monkeypatch.delenv("RSNA_RAIZ", raising=False)
    else:
        monkeypatch.setenv("RSNA_RAIZ", valor)
    with pytest.raises(SystemExit, match="RSNA_RAIZ"):
        raiz_rsna()
```

En `tests/test_sesion.py`, al final del fichero, después de
`test_sin_rsna_raiz_el_script_lo_dice`, añade:

```python


def test_el_script_no_tiene_un_lector_propio_de_rsna_raiz():
    """Un solo lector de la variable, el de `copiloto_triaje.config`: con dos
    copias, una acaba ganando un valor por defecto y la otra no."""
    from copiloto_triaje import config
    assert _preparar().raiz_rsna is config.raiz_rsna
```

- [ ] **Paso 2: Verlas fallar**

```bash
env -u RSNA_RAIZ C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_config.py
```

Esperado: error de colección,
`ImportError: cannot import name 'raiz_rsna' from 'copiloto_triaje.config'`,
y `1 error` en la última línea.

- [ ] **Paso 3: `raiz_rsna()` en `src/copiloto_triaje/config.py`**

El bloque de las líneas 10-15 (de `from __future__ import annotations` a la
constante `ARQUITECTURAS`) pasa a ser:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ARQUITECTURAS = ("densenet121", "mobilenet_v3_large", "efficientnet_b0")


def raiz_rsna() -> Path:
    """La raiz del dataset preparado, leida de la variable `RSNA_RAIZ`.

    Es la carpeta que tiene dentro `manifiestos/`, `png/` y
    `crudo/stage_2_train_images/`. No hay valor por defecto: una ruta por
    defecto seria la de una maquina concreta (spec de SP5 §6.1). Se lee en
    cada llamada y nunca al importar, para que los modulos que la usan se
    puedan importar en una maquina sin dataset; quien la necesita la llama
    dentro de la funcion que de verdad va a leer el disco. No comprueba que la
    carpeta exista: eso lo dice, con la ruta, quien intente abrir el fichero.
    """
    raiz = os.environ.get("RSNA_RAIZ", "").strip()
    if not raiz:
        raise SystemExit("falta RSNA_RAIZ: la raíz del dataset preparado, sin valor "
                         "por defecto (spec de SP5 §6.1)")
    return Path(raiz)
```

(Siguen dos líneas en blanco y el `@dataclass(frozen=True)` de `Config`, sin
cambios.)

- [ ] **Paso 4: `scripts/preparar_sesion.py` importa esa y borra la suya**

Tres ediciones:

1. Borra la línea 44, `import os` (nadie más lo usa en el fichero).
2. Antes de la línea 54
   (`from copiloto_triaje.servicio.heckerling import PREVALENCIA_COHORTE  # noqa: E402`)
   añade:

   ```python
   from copiloto_triaje.config import raiz_rsna  # noqa: E402
   ```
3. Borra las líneas 62-69: la función `raiz_rsna()` entera y las dos líneas en
   blanco que la siguen. Entre `ROTULO = …` y `def entrada_formulario` quedan
   dos líneas en blanco.

El docstring del script (líneas 30-33, sección ENTORNO) ya dice lo correcto y
no cambia.

- [ ] **Paso 5: Verde, y commit**

```bash
env -u RSNA_RAIZ C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_config.py tests/test_sesion.py
```

Esperado: `42 passed` (13 de `test_config.py`, 29 de `test_sesion.py`). Entre
ellas sigue verde `test_sin_rsna_raiz_el_script_lo_dice`, que exige
`SystemExit` con `RSNA_RAIZ` en el mensaje.

```bash
git add src/copiloto_triaje/config.py scripts/preparar_sesion.py tests/test_config.py tests/test_sesion.py
git commit -m "$(cat <<'EOF'
fix(anonimato): raiz_rsna() vive en config.py y es el único lector de RSNA_RAIZ

El script de la sesión tenía su propia copia. Pasa a importar la de
copiloto_triaje.config, que es la que van a usar también pruebas/ y tests/.
Sin valor por defecto y leída en cada llamada, nunca al importar.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

#### Commit B — `pruebas/` y `tests/` sin rutas de la máquina

Todo lo de este commit va junto: en cuanto `seleccionar()` lee la variable,
las pruebas que la llaman necesitan la fixture que las salta.

- [ ] **Paso 6: Las pruebas de las dos funciones de `conftest.py`**

Crea `tests/test_entorno_de_datos.py`:

```python
# -*- coding: utf-8 -*-
"""Lo que vive fuera del repositorio y algunas pruebas necesitan: el dataset
de RSNA (`RSNA_RAIZ`) y los pesos desplegados.

Ninguno de los dos se versiona, asi que en un clon limpio no estan. Las pruebas
que los usan tienen que SALTARSE diciendo que se queda sin verificar, y no
fallar con un `FileNotFoundError` que no informa de nada. Aqui se prueban las
dos funciones de `conftest.py` que lo deciden; los fijadores `rsna_raiz` y
`pesos_desplegados` solo las llaman.
"""
import pytest

import conftest


def test_sin_rsna_raiz_se_salta_diciendo_que_falta_y_como_verificarlo(monkeypatch):
    monkeypatch.delenv("RSNA_RAIZ", raising=False)
    with pytest.raises(pytest.skip.Exception) as salto:
        conftest.raiz_rsna_o_salta()
    mensaje = str(salto.value)
    assert "SIN VERIFICAR" in mensaje
    assert "RSNA_RAIZ" in mensaje
    assert "crudo/stage_2_train_images" in mensaje, "debe decir que carpeta es"


def test_con_rsna_raiz_vacia_tambien_se_salta(monkeypatch):
    monkeypatch.setenv("RSNA_RAIZ", "")
    with pytest.raises(pytest.skip.Exception, match="RSNA_RAIZ"):
        conftest.raiz_rsna_o_salta()


def test_con_rsna_raiz_se_devuelve_la_carpeta(tmp_path, monkeypatch):
    monkeypatch.setenv("RSNA_RAIZ", str(tmp_path))
    assert conftest.raiz_rsna_o_salta() == tmp_path


def test_sin_los_pesos_se_salta_diciendo_cuales_faltan(tmp_path, monkeypatch):
    from pruebas import puntuaciones
    monkeypatch.setattr(puntuaciones, "PESOS", tmp_path / "pesos_modelo_cpu.pt")
    with pytest.raises(pytest.skip.Exception) as salto:
        conftest.pesos_desplegados_o_salta()
    mensaje = str(salto.value)
    assert "SIN VERIFICAR" in mensaje
    assert "pesos_modelo_cpu.pt" in mensaje


def test_con_los_pesos_se_devuelve_su_ruta(tmp_path, monkeypatch):
    from pruebas import puntuaciones
    pesos = tmp_path / "pesos_modelo_cpu.pt"
    pesos.write_bytes(b"pesos de mentira")
    monkeypatch.setattr(puntuaciones, "PESOS", pesos)
    assert conftest.pesos_desplegados_o_salta() == pesos


@pytest.mark.parametrize("nombre", ["rsna_raiz", "pesos_desplegados"])
def test_los_fijadores_sirven_a_fijadores_de_modulo(nombre, request):
    """De modulo, por dos razones. `casos` y los `dicom_*` son de modulo, y
    un fijador de modulo no puede pedir uno de funcion (ScopeMismatch). Y no
    de sesion, porque pytest prepara antes lo de alcance mayor: el skip del
    dataset le quitaria el sitio al de `copiloto_vivo`, que es `autouse` y de
    modulo y tiene que ir primero (sin servidor no hace falta mirar nada mas)."""
    definiciones = request.session._fixturemanager.getfixturedefs(
        nombre, request.node)
    assert definiciones, f"no existe el fijador {nombre}"
    assert definiciones[-1].scope == "module"
```

- [ ] **Paso 7: Las pruebas de `pruebas/puntuaciones.py`**

Al final de `tests/test_puntuaciones.py`, después de
`test_pesos_cambiados_invalida_la_cache_existente`, añade:

```python


def test_con_la_cache_valida_no_se_pide_rsna_raiz(entorno_aislado, monkeypatch):
    """Con la cache al dia no se toca el dataset, asi que tampoco se pide
    donde esta: quien solo quiere las puntuaciones no necesita RSNA."""
    pesos, cache, cache_hash = entorno_aislado
    cache.write_text("patientId,cruda\nabc,0.42\n", encoding="utf-8")
    cache_hash.write_text(puntuaciones._sha256(pesos), encoding="utf-8")
    monkeypatch.delenv("RSNA_RAIZ", raising=False)
    df = puntuaciones.puntuaciones_de_prueba()
    assert df.to_dict("records") == [{"patientId": "abc", "cruda": 0.42}]


def test_con_la_cache_fria_y_sin_rsna_raiz_se_detiene_nombrandola(
        entorno_aislado, monkeypatch):
    """Sin cache hay que inferir, y para inferir hace falta el dataset. Sin
    la variable se dice cual falta, antes de leer nada."""
    _, cache, cache_hash = entorno_aislado
    monkeypatch.delenv("RSNA_RAIZ", raising=False)
    with pytest.raises(SystemExit, match="RSNA_RAIZ"):
        puntuaciones.puntuaciones_de_prueba()
    assert not cache.exists() and not cache_hash.exists()


def test_con_la_cache_fria_el_manifiesto_se_busca_bajo_rsna_raiz(
        entorno_aislado, tmp_path, monkeypatch):
    """La raiz es la de la variable y ninguna otra: con una carpeta vacia, lo
    que falta es SU manifiesto."""
    raiz = tmp_path / "rsna"
    raiz.mkdir()
    monkeypatch.setenv("RSNA_RAIZ", str(raiz))
    with pytest.raises(FileNotFoundError) as error:
        puntuaciones.puntuaciones_de_prueba()
    assert error.value.filename == str(raiz / "manifiestos" / "test.csv")


def test_el_modulo_no_guarda_ninguna_ruta_del_dataset():
    assert not hasattr(puntuaciones, "RAIZ")
```

La primera es una guarda: pasa ya hoy (con la caché válida nunca se llegó a
la raíz) y tiene que seguir pasando.

- [ ] **Paso 8: Las pruebas de `pruebas/seleccionar_casos.py` que no necesitan dataset**

Al final de `tests/test_seleccion_casos.py`, después de
`test_la_seleccion_es_determinista`, añade:

```python


# --------------------------------------------------------------------------
# Lo que se prueba sin dataset: de donde sale la ruta de cada placa
# --------------------------------------------------------------------------
REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def con_puntuaciones_de_mentira(monkeypatch):
    """Tres filas en lugar de la cache: asi `seleccionar` no infiere ni lee
    los pesos. Los metadatos (`docs/eda/metadatos_eda.csv`) si son los reales,
    que estan versionados: de ahi salen los tres adultos de las filas, y los
    menores y las edades imposibles que `seleccionar` busca por su cuenta."""
    import pandas as pd
    from pruebas import seleccionar_casos
    meta = pd.read_csv(REPO / "docs" / "eda" / "metadatos_eda.csv")
    adultos = sorted(meta[(meta.edad_num >= 18) & (meta.edad_num <= 100)]
                     .patientId)[:3]
    df = pd.DataFrame({"patientId": adultos, "etiqueta": [1, 0, 1],
                       "cruda": [0.95, 0.05, 0.50]})
    monkeypatch.setattr(seleccionar_casos, "puntuaciones_de_prueba",
                        lambda: df.copy())
    return seleccionar_casos


def test_las_rutas_cuelgan_de_rsna_raiz(con_puntuaciones_de_mentira, tmp_path,
                                        monkeypatch):
    monkeypatch.setenv("RSNA_RAIZ", str(tmp_path))
    casos = con_puntuaciones_de_mentira.seleccionar(n_por_perfil=2)
    crudo = tmp_path / "crudo" / "stage_2_train_images"
    alta = casos["positiva_clara"][0]
    assert alta["ruta_dcm"] == str(crudo / f"{alta['patientId']}.dcm")
    for nombre, perfil in casos.items():
        assert perfil, f"el perfil {nombre} salio vacio"
        for c in perfil:
            assert pathlib.Path(c["ruta_dcm"]).parent == crudo, c


def test_sin_rsna_raiz_seleccionar_se_detiene_nombrandola(
        con_puntuaciones_de_mentira, monkeypatch):
    monkeypatch.delenv("RSNA_RAIZ", raising=False)
    with pytest.raises(SystemExit, match="RSNA_RAIZ"):
        con_puntuaciones_de_mentira.seleccionar(n_por_perfil=2)


def test_el_modulo_no_guarda_ninguna_ruta_del_dataset():
    from pruebas import seleccionar_casos
    assert not hasattr(seleccionar_casos, "RAIZ")
    assert not hasattr(seleccionar_casos, "CRUDO")


def test_los_dos_modulos_se_importan_sin_rsna_raiz():
    """En un proceso aparte, porque en este ya estan importados. Los importan
    sin dataset `tests/test_sesion.py` (por `UMBRAL`), `tests/test_puntuaciones.py`
    y `pruebas/reproducir_casos.py`: si la variable se leyera al importar, esos
    ficheros darian error de coleccion en un clon limpio."""
    import os
    import subprocess
    entorno = {k: v for k, v in os.environ.items() if k != "RSNA_RAIZ"}
    r = subprocess.run(
        [sys.executable, "-B", "-c",
         "import pruebas.puntuaciones, pruebas.seleccionar_casos; print('importados')"],
        cwd=REPO, env=entorno, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "importados"
```

La última también es una guarda: hoy pasa, porque las constantes no leen el
entorno. Protege de que alguien, al quitar las rutas, lea la variable al
importar.

- [ ] **Paso 9: Verlas fallar**

```bash
env -u RSNA_RAIZ C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_entorno_de_datos.py tests/test_puntuaciones.py tests/test_seleccion_casos.py
```

Esperado: `13 failed`, y son estas:

```
FAILED tests/test_entorno_de_datos.py::test_sin_rsna_raiz_se_salta_diciendo_que_falta_y_como_verificarlo
FAILED tests/test_entorno_de_datos.py::test_con_rsna_raiz_vacia_tambien_se_salta
FAILED tests/test_entorno_de_datos.py::test_con_rsna_raiz_se_devuelve_la_carpeta
FAILED tests/test_entorno_de_datos.py::test_sin_los_pesos_se_salta_diciendo_cuales_faltan
FAILED tests/test_entorno_de_datos.py::test_con_los_pesos_se_devuelve_su_ruta
FAILED tests/test_entorno_de_datos.py::test_los_fijadores_sirven_a_fijadores_de_modulo[rsna_raiz]
FAILED tests/test_entorno_de_datos.py::test_los_fijadores_sirven_a_fijadores_de_modulo[pesos_desplegados]
FAILED tests/test_puntuaciones.py::test_con_la_cache_fria_y_sin_rsna_raiz_se_detiene_nombrandola
FAILED tests/test_puntuaciones.py::test_con_la_cache_fria_el_manifiesto_se_busca_bajo_rsna_raiz
FAILED tests/test_puntuaciones.py::test_el_modulo_no_guarda_ninguna_ruta_del_dataset
FAILED tests/test_seleccion_casos.py::test_las_rutas_cuelgan_de_rsna_raiz
FAILED tests/test_seleccion_casos.py::test_sin_rsna_raiz_seleccionar_se_detiene_nombrandola
FAILED tests/test_seleccion_casos.py::test_el_modulo_no_guarda_ninguna_ruta_del_dataset
```

Los motivos: `AttributeError: module 'conftest' has no attribute
'raiz_rsna_o_salta'` (y `'pesos_desplegados_o_salta'`); `no existe el fijador
…`; `hasattr(…, 'RAIZ')` cierto; `DID NOT RAISE SystemExit`; y una `ruta_dcm`
que cuelga de la ruta fija y no de la carpeta temporal. Las dos de la caché
fría fallan, donde la ruta fija existe, con un `UnpicklingError` al cargar
los pesos de mentira; donde no existe, con un `FileNotFoundError` de la ruta
fija.

El resto de la última línea depende de la máquina: con pesos y caché,
`13 failed, 13 passed`; en un clon sin pesos, `13 failed, 8 passed, 5 errors`
(las cinco pruebas de `casos` dan `FileNotFoundError` en los pesos: es el
estado de hoy, y el paso 12 lo convierte en un skip).

- [ ] **Paso 10: `pruebas/puntuaciones.py`, lectura perezosa**

Tres ediciones:

1. Antes de la línea 34
   (`from copiloto_triaje.datos.dataset import DatasetRadiografias  # noqa: E402`)
   añade:

   ```python
   from copiloto_triaje.config import raiz_rsna  # noqa: E402
   ```
2. Borra la línea 37: la constante de módulo `RAIZ`, que asigna una ruta
   absoluta de la máquina. La línea en blanco de la 36 se queda; la siguiente
   línea es `PESOS = REPO / "servidor" / "pesos_modelo_cpu.pt"`.
3. En `puntuaciones_de_prueba()`, desde el final del docstring (línea 68,
   `    nada distinto.`) hasta la línea 76 (`batch_size=32, num_workers=4)`),
   el texto pasa a ser:

   ```python
       nada distinto.

       El dataset solo hace falta para inferir: con la cache al dia no se pide
       `RSNA_RAIZ`. Sin cache y sin la variable, se detiene nombrandola.
       """
       if _cache_valida():
           return pd.read_csv(CACHE)
       raiz = raiz_rsna()
       hash_actual = _sha256(PESOS)
       df = pd.read_csv(raiz / "manifiestos" / "test.csv")
       cargador = DataLoader(
           DatasetRadiografias(df, raiz / "png", 320, entrenamiento=False),
           batch_size=32, num_workers=4)
   ```

- [ ] **Paso 11: `pruebas/seleccionar_casos.py`, lectura perezosa**

Las líneas 16-28 (de `REPO = …` a la primera línea del cuerpo de
`seleccionar`, `    df = puntuaciones_de_prueba()`) pasan a ser:

```python
REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from copiloto_triaje.config import raiz_rsna  # noqa: E402
from pruebas.puntuaciones import puntuaciones_de_prueba  # noqa: E402

UMBRAL = 0.4258
CRUCE_RV = 0.5786          # donde la RV cruza 1,0; ver §3 del spec


def seleccionar(n_por_perfil: int = 10) -> dict:
    """Los casos de cada perfil, con la ruta de su DICOM bajo `RSNA_RAIZ`.

    La variable se lee aqui y no al importar: este modulo lo importan, solo
    por `UMBRAL` o de paso, ficheros que corren sin dataset.
    """
    crudo = raiz_rsna() / "crudo" / "stage_2_train_images"
    df = puntuaciones_de_prueba()
```

(Desaparecen las líneas 21-22, las constantes de módulo `RAIZ` y `CRUDO`.)

Y la línea 58 pasa a ser:

```python
             "ruta_dcm": str(crudo / f"{f.patientId}.dcm"),
```

- [ ] **Paso 12: Las fixtures de `tests/conftest.py` y la fixture `casos`**

Al FINAL de `tests/conftest.py` (después de la última fixture que haya; la
tarea 1 de este plan edita el principio del fichero y no estorba) añade:

```python


# --------------------------------------------------------------------------
# Lo que vive fuera del repositorio: el dataset de RSNA y los pesos desplegados
# --------------------------------------------------------------------------
def raiz_rsna_o_salta():
    """La raiz del dataset preparado (`RSNA_RAIZ`), o un skip que dice que se
    queda sin verificar y como verificarlo.

    No hay valor por defecto (spec de SP5 §6.1): una ruta por defecto seria la
    de una maquina concreta. La variable la lee `copiloto_triaje.config`, el
    unico lector que hay; aqui solo se convierte su `SystemExit` en un skip.
    Si la variable esta puesta pero la carpeta no tiene el dataset, NO se
    salta: las pruebas fallan con la ruta que no encuentran, que es lo que
    hace falta ver cuando la variable esta mal escrita.
    """
    from copiloto_triaje.config import raiz_rsna
    try:
        return raiz_rsna()
    except SystemExit:
        pytest.skip(
            "PRUEBAS CON RADIOGRAFÍAS REALES SIN VERIFICAR: falta RSNA_RAIZ, la"
            " raíz del dataset de RSNA preparado, que no tiene valor por"
            " defecto. Se quedan sin comprobar la selección de casos sobre los"
            " ficheros reales, el contrato con copiloto-mcp cuando recibe un"
            " DICOM y las consultas conducidas del bot del profesional que"
            " suben una placa. Para verificarlo, define RSNA_RAIZ con la"
            " carpeta que tiene dentro manifiestos/, png/ y"
            " crudo/stage_2_train_images/, y repite.")


def pesos_desplegados_o_salta():
    """La ruta de los pesos desplegados, o un skip si el fichero no esta.

    Los pesos no se versionan (16 MB binarios; `.gitignore`), y sin ellos no
    se puede ni inferir ni saber si la cache de puntuaciones es la del modelo
    desplegado: `pruebas/puntuaciones.py` compara su sha256 con el guardado.
    """
    import pathlib
    import sys
    repo = str(pathlib.Path(__file__).resolve().parents[1])
    if repo not in sys.path:
        sys.path.insert(0, repo)
    from pruebas import puntuaciones
    if not puntuaciones.PESOS.is_file():
        pytest.skip(
            "PRUEBAS CON LAS PUNTUACIONES DEL MODELO SIN VERIFICAR: faltan los"
            " pesos desplegados, servidor/pesos_modelo_cpu.pt, que no se"
            " versionan. Sin ellos no se puede inferir ni validar la caché de"
            " puntuaciones del conjunto de prueba, así que se quedan sin"
            " comprobar la selección de casos y las dos pruebas del recorte de"
            " la razón de verosimilitud. Para verificarlo, copia los pesos a"
            " esa ruta y repite; la primera vez, sin caché, infiere sobre las"
            " 3 811 imágenes de prueba y tarda minutos.")
    return puntuaciones.PESOS


@pytest.fixture(scope="module")
def rsna_raiz():
    """La raiz del dataset de RSNA. Sin `RSNA_RAIZ`, la prueba se salta."""
    return raiz_rsna_o_salta()


@pytest.fixture(scope="module")
def pesos_desplegados():
    """Los pesos desplegados. Sin el fichero, la prueba se salta."""
    return pesos_desplegados_o_salta()
```

En `tests/test_seleccion_casos.py`, la fixture `casos` (líneas 19-21) pasa a
ser:

```python
@pytest.fixture(scope="module")
def casos(rsna_raiz, pesos_desplegados):
    """La seleccion de verdad: necesita el dataset (`rsna_raiz`) y los pesos
    desplegados (`pesos_desplegados`), y sin cualquiera de los dos las cinco
    pruebas que la usan se saltan diciendo cual falta. Con los dos y sin la
    cache de puntuaciones, esta llamada la genera (infiere sobre las 3 811
    imagenes de prueba: minutos)."""
    return seleccionar(n_por_perfil=5)
```

- [ ] **Paso 13: Verde**

```bash
env -u RSNA_RAIZ C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q -rs tests/test_entorno_de_datos.py tests/test_puntuaciones.py tests/test_seleccion_casos.py
```

Esperado: `21 passed, 5 skipped`. Los cinco skips son las pruebas de `casos`
y su motivo empieza por `PRUEBAS CON RADIOGRAFÍAS REALES SIN VERIFICAR: falta
RSNA_RAIZ` (en una consola de Windows con otra codificación las tildes pueden
salir cambiadas; el fichero está en UTF-8).

- [ ] **Paso 14: `tests/test_contrato_mcp.py` sin rutas**

Seis ediciones, por orden de abajo arriba:

1. Línea 336, el `return` de `dicom_recortada_por_arriba`, y línea 319, el de
   `dicom_recortada_por_abajo` (son iguales):

   ```python
       return (_crudo(rsna_raiz) / f"{patient_id}.dcm").read_bytes()
   ```
2. Línea 323 y línea 296, las dos firmas:

   ```python
   def dicom_recortada_por_arriba(rsna_raiz, pesos_desplegados) -> bytes:
   ```
   ```python
   def dicom_recortada_por_abajo(rsna_raiz, pesos_desplegados) -> bytes:
   ```
3. `dicom_menor`: la línea 127 (la firma) y la 132 (el `return`):

   ```python
   def dicom_menor(rsna_raiz) -> bytes:
   ```
   ```python
       return (_crudo(rsna_raiz) / f"{menor.patientId}.dcm").read_bytes()
   ```
4. `dicom_adulto` entera (líneas 118-123, del decorador al `return`; la línea
   121 es la que asigna a `raiz` una ruta absoluta de la máquina) pasa a ser,
   con una función de ayuda delante:

   ```python
   def _crudo(rsna_raiz: pathlib.Path) -> pathlib.Path:
       """La carpeta de los DICOM originales, bajo la raiz del dataset."""
       return rsna_raiz / "crudo" / "stage_2_train_images"


   @pytest.fixture(scope="module")
   def dicom_adulto(rsna_raiz) -> bytes:
       import pandas as pd
       df = pd.read_csv(rsna_raiz / "manifiestos" / "test.csv")
       return (_crudo(rsna_raiz)
               / f"{df[df.etiqueta == 1].iloc[0].patientId}.dcm").read_bytes()
   ```
5. Borra las líneas 27-28: la constante de módulo `CRUDO` (dos líneas, un
   `pathlib.Path(` con una ruta absoluta de la máquina). Después de
   `BASE = os.environ.get("COPILOTO_URL", "http://127.0.0.1:18000")` queda una
   línea en blanco y el comentario del rango ajustado.
6. En el docstring del módulo, después de la línea 13
   (`ha quedado sin verificar y COMO verificarlo. Se leen con `pytest -rs`.`)
   y antes de las comillas que lo cierran, añade:

   ```

   OCHO DE LAS DIEZ NECESITAN ADEMAS EL DATASET, porque mandan una radiografia
   real: sin `RSNA_RAIZ` se saltan (fijador `rsna_raiz` de `conftest.py`), y las
   dos del recorte tambien sin los pesos desplegados (`pesos_desplegados`). Las
   dos que no mandan ningun DICOM -el base64 invalido y el 413- corren con el
   servidor solo.
   ```

No hace falta una fixture intermedia para la carpeta de los DICOM: sería una
fixture más que `tests/test_contrato_sp4.py` tendría que importar. `_crudo` es
una función.

Comprueba que no queda ninguna mención: `grep -n "CRUDO" tests/test_contrato_mcp.py`
no imprime nada.

- [ ] **Paso 15: `tests/test_flujo_profesional.py`: las tres pruebas que suben una placa**

Las tres llaman a `seleccionar()`, que lee la caché (pesos) y construye la
ruta (dataset), también para el perfil de menores. De abajo arriba:

1. Línea 414:

   ```python
       def test_los_sintomas_se_copian_a_consultas(self, webhook_n8n, bd_sp3,
                                                   rsna_raiz, pesos_desplegados):
   ```
2. Línea 347:

   ```python
       def test_la_banda_contradictoria_lleva_su_aviso(self, webhook_n8n, bd_sp3,
                                                       rsna_raiz, pesos_desplegados):
   ```
3. Líneas 330-331 (la firma, en dos líneas):

   ```python
       def test_un_menor_de_edad_se_rechaza_sin_ninguna_cifra(
               self, webhook_n8n, bd_sp3, rsna_raiz, pesos_desplegados):
   ```
4. El comentario de las líneas 114-115, encima de `necesita_subida`, pasa a
   ser:

   ```python
   # Las TRES pruebas que suben una placa. Las otras cinco de la clase no suben nada
   # y no dependen de esto. La placa es una radiografia real de RSNA, elegida con
   # `seleccionar`: las tres piden ademas `rsna_raiz` y `pesos_desplegados`, y sin
   # `RSNA_RAIZ` o sin los pesos se saltan diciendo cual falta.
   ```

No toques ninguna otra línea de este fichero: las que llevan identificadores
son de la tarea 4.

- [ ] **Paso 16: Verde en todo lo que toca el commit, y commit**

```bash
env -u RSNA_RAIZ -u N8N_URL C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_flujo_profesional.py tests/test_reproducir_casos.py tests/test_sesion.py
```

Esperado: `92 passed, 8 skipped` (30 + 33 + 29 pasan; las 8 que se saltan son
las conducidas de `test_flujo_profesional.py`, por sus secretos, como antes).
Si en el entorno están los secretos de Telegram y el túnel a la base, las
conducidas dejan de saltarse por eso y las tres que suben una placa se saltan
por `RSNA_RAIZ`.

```bash
env -u RSNA_RAIZ C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q -rs tests/test_contrato_mcp.py tests/test_contrato_sp4.py
```

Esperado, según haya servidor en `COPILOTO_URL` (por defecto
`http://127.0.0.1:18000`):

- sin servidor: `13 skipped`, las trece con el mensaje `CONTRATO … SIN
  VERIFICAR: …/salud no responde`;
- con un servidor anterior a SP4: `2 passed, 11 skipped` (pasan el base64
  inválido y el 413; ocho se saltan por `falta RSNA_RAIZ`; las tres de SP4,
  por su propio motivo);
- con el servidor de SP4: `2 passed, 11 skipped` también, y las once por
  `falta RSNA_RAIZ`.

Ninguna puede dar ERROR ni FAILED.

```bash
grep -nE 'C:[/\\]+Users' pruebas/puntuaciones.py pruebas/seleccionar_casos.py tests/test_contrato_mcp.py tests/test_seleccion_casos.py tests/conftest.py tests/test_entorno_de_datos.py
```

Esperado: ninguna línea (el `grep` sale con 1).

```bash
git add pruebas/puntuaciones.py pruebas/seleccionar_casos.py tests/conftest.py tests/test_entorno_de_datos.py tests/test_puntuaciones.py tests/test_seleccion_casos.py tests/test_contrato_mcp.py tests/test_flujo_profesional.py
git commit -m "$(cat <<'EOF'
fix(anonimato): el dataset se busca en RSNA_RAIZ; ninguna ruta de la máquina en pruebas/ ni en tests/

pruebas/puntuaciones.py y pruebas/seleccionar_casos.py pierden las
constantes con la ruta absoluta y leen la variable dentro de la función que
va a tocar el disco: importarlos sigue sin pedir nada, y con la caché al día
puntuaciones_de_prueba() tampoco la pide.

En tests/, las fixtures rsna_raiz y pesos_desplegados saltan, diciendo qué
se queda sin verificar, las pruebas que necesitan el dataset o los pesos. En
un clon limpio test_seleccion_casos.py daba cinco errores; ahora son cinco
skips con su motivo.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

#### Commit C — Los docstrings de uso de dos scripts

- [ ] **Paso 17: `scripts/entrenar_local.py` y `scripts/preparar_datos.py`**

Son texto de ejemplo dentro del docstring (las barras van dobles porque el
docstring no es crudo). Los argumentos de `argparse` no cambian: `--raiz`
sigue siendo obligatorio y sin valor por defecto.

En `scripts/entrenar_local.py`, la línea 5 (el `--raiz` del ejemplo) y la
línea 7 (el `--salida`) pasan a ser:

```
        --raiz "<RSNA_RAIZ>" ^
```
```
        --salida "<RSNA_RAIZ>\\corridas\\corrida3_mobilenet_224px"
```

En `scripts/preparar_datos.py`, las líneas 5 (el `--zip` del ejemplo) y 6 (el
`--raiz`) pasan a ser:

```
        --zip "<carpeta-de-descarga>\\rsna-pneumonia-detection-challenge.zip" ^
        --raiz "<RSNA_RAIZ>" ^
```

- [ ] **Paso 18: Comprobar, y commit**

```bash
grep -nE 'C:[/\\]+Users' scripts/entrenar_local.py scripts/preparar_datos.py
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_entrenar_local.py
```

Esperado: el `grep` no imprime nada; las pruebas del script, todas verdes
(ninguna lee el docstring).

```bash
git add scripts/entrenar_local.py scripts/preparar_datos.py
git commit -m "$(cat <<'EOF'
docs(anonimato): los ejemplos de uso de los scripts dicen <RSNA_RAIZ>, no una ruta de la máquina

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

#### Commit D — La tabla «Procedencia» de la comparativa de corridas

- [ ] **Paso 19: La prueba**

Al final de `tests/test_comparar_corridas.py`, después de
`test_un_json_con_prueba_inutilizable_dice_de_cual_se_trata`, añade:

```python


def test_la_procedencia_no_escribe_la_ruta_de_la_maquina(tmp_path):
    """El informe se versiona y se publica: la ruta tal como se paso lleva
    dentro el usuario y las carpetas de quien lo genero. De cada reporte se
    escribe la carpeta de la corrida y el nombre del fichero, que es lo que
    lo identifica, y nada de lo que hay por encima."""
    carpeta = _escribir_reporte(tmp_path, "corrida_a", recall=0.88,
                                especificidad=0.74, auc=0.91).parent
    json_directo = _escribir_reporte(tmp_path, "corrida_b", recall=0.81,
                                     especificidad=0.71, auc=0.86)
    salida = tmp_path / "comparativa.md"
    assert comparar.main([str(carpeta), str(json_directo),
                          "--salida", str(salida)]) == 0

    texto = salida.read_text(encoding="utf-8")
    procedencia = texto.split("## Procedencia", 1)[1]
    assert "| `corrida_a` | `corrida_a/reporte_metricas.json` |" in procedencia
    assert "| `corrida_b` | `corrida_b/reporte_metricas.json` |" in procedencia
    assert str(tmp_path) not in texto
    assert tmp_path.as_posix() not in texto
    assert tmp_path.name not in texto


def test_la_procedencia_nombra_la_carpeta_aunque_la_ruta_sea_relativa(
        tmp_path, monkeypatch):
    """Desde dentro de la carpeta de la corrida la ruta que se pasa es solo
    el nombre del fichero; la carpeta sigue siendo la de la corrida."""
    ruta = _escribir_reporte(tmp_path, "corrida_c", recall=0.88,
                             especificidad=0.74)
    monkeypatch.chdir(ruta.parent)
    resumen = comparar.resumir(*comparar.cargar_reporte("reporte_metricas.json"))
    assert comparar.reporte_sin_ruta(resumen["ruta"]) == (
        "corrida_c/reporte_metricas.json")
```

- [ ] **Paso 20: Verlas fallar**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_comparar_corridas.py
```

Esperado: `2 failed, 19 passed`. La primera falla porque la fila lleva la ruta
entera; la segunda, con `AttributeError: module 'comparar_corridas' has no
attribute 'reporte_sin_ruta'`.

- [ ] **Paso 21: `scripts/comparar_corridas.py`**

Las líneas 476-479 (la cabecera de `_seccion_procedencia`, la tabla y el
bucle que añade cada fila) pasan a ser:

```python
def reporte_sin_ruta(ruta_json) -> str:
    """`<carpeta de la corrida>/<fichero>`: los dos ultimos componentes.

    El informe se versiona y se publica, y la ruta tal como se paso lleva
    dentro el usuario y las carpetas de la maquina donde se genero (spec de
    SP5 §6.1). La carpeta de la corrida y el nombre del fichero bastan para
    saber que reporte se leyo. Siempre con `/`, para que el informe no cambie
    segun el sistema donde se genere.
    """
    ruta_json = Path(ruta_json).resolve()
    carpeta = ruta_json.parent.name
    return f"{carpeta}/{ruta_json.name}" if carpeta else ruta_json.name


def _seccion_procedencia(ordenadas: list[dict]) -> list[str]:
    lineas = ["## Procedencia", "", "| Corrida | Reporte leído |", "| :--- | :--- |"]
    for resumen in ordenadas:
        lineas.append(f"| `{resumen['nombre']}` "
                      f"| `{reporte_sin_ruta(resumen['ruta'])}` |")
```

El resto de la función (la nota del bloque `corrida`) no cambia. `resumir()`
sigue guardando la ruta entera en `resumen["ruta"]`: la usan la deduplicación
y los mensajes de consola, que no se versionan.

- [ ] **Paso 22: Las ocho filas de `docs/comparativa-corridas.md`, a mano**

El documento no se puede regenerar (las corridas no están en el repositorio).
Las líneas 70-77, las ocho filas de la tabla «Procedencia», pasan a ser:

```markdown
| `kaggle_efficientnet_b0_320px_c2` | `kaggle_efficientnet_b0_320px_c2/reporte_metricas.json` |
| `kaggle_densenet121_320px_c1` | `kaggle_densenet121_320px_c1/reporte_metricas.json` |
| `kaggle_densenet121_320px_c2` | `kaggle_densenet121_320px_c2/reporte_metricas.json` |
| `kaggle_efficientnet_b0_320px_c1` | `kaggle_efficientnet_b0_320px_c1/reporte_metricas.json` |
| `kaggle_mobilenet_v3_large_320px_c1` | `kaggle_mobilenet_v3_large_320px_c1/reporte_metricas.json` |
| `efficientnet_b0_320px_lote24_4+20ep` | `efficientnet_b0_320px_lote24_4+20ep/reporte_metricas.json` |
| `kaggle_mobilenet_v3_large_320px_c2` | `kaggle_mobilenet_v3_large_320px_c2/reporte_metricas.json` |
| `corrida2_densenet121_320px` | `colab_densenet121_320px/reporte_metricas.json` |
```

La primera columna no cambia. En la última fila el nombre de la corrida y el
de su carpeta son distintos, y así estaba. Nada más del documento cambia.

- [ ] **Paso 23: Verde, y commit**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_comparar_corridas.py
grep -nE 'C:[/\\]+Users' scripts/comparar_corridas.py docs/comparativa-corridas.md
git diff --stat docs/comparativa-corridas.md
```

Esperado: `21 passed`; el `grep` no imprime nada; el `diff` enseña
`1 file changed, 8 insertions(+), 8 deletions(-)`.

```bash
git add scripts/comparar_corridas.py tests/test_comparar_corridas.py docs/comparativa-corridas.md
git commit -m "$(cat <<'EOF'
fix(anonimato): la Procedencia de la comparativa escribe la carpeta de la corrida, no la ruta de la máquina

El informe escribía la ruta del reporte tal como se pasó por la línea de
órdenes, y regenerarlo la volvía a meter. Ahora escribe
<carpeta de la corrida>/reporte_metricas.json. Las ocho filas del documento
versionado se corrigen a mano: las corridas no están en el repositorio.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

#### Cierre de la tarea

- [ ] **Paso 24: Todo junto, sin la variable**

```bash
env -u RSNA_RAIZ -u N8N_URL C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q -rfEs --ignore=tests/test_mantenimiento.py
```

Esperado: ningún `FAILED` ni `ERROR`. En la copia de trabajo donde se preparó
esta tarea (sin pesos ni caché, con un servidor anterior a SP4 en el puerto
de las pruebas, y antes de fusionar SP5-B1, que añadió 156 pruebas a la
suite) la última línea fue `532 passed, 31 skipped`. Con SP5-B1 y las demás
tareas del plan aplicadas los totales cambian; lo que importa es que no haya
fallos y que los skips de esta tarea digan `falta RSNA_RAIZ` o `faltan los
pesos desplegados`.

- [ ] **Paso 25: En la máquina de desarrollo, con la variable**

Desde esta tarea, sin `RSNA_RAIZ` en el entorno las pruebas con radiografías
reales se SALTAN, también en la máquina de desarrollo, donde antes corrían
con la ruta fija. Un skip se ve verde: hay que poner la variable y mirar los
motivos.

Define `RSNA_RAIZ` en el entorno del usuario con la carpeta del dataset
preparado (en Windows, `setx RSNA_RAIZ "<RSNA_RAIZ>"` y abrir una consola
nueva; el valor no se escribe en ningún fichero del repositorio) y corre:

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q -rs tests/test_seleccion_casos.py tests/test_contrato_mcp.py
```

Esperado con pesos, caché y el servidor vivo: `19 passed` (9 + 10) y ningún
skip. Sin servidor: `9 passed, 10 skipped`, y los diez skips son de
`copiloto_vivo`. Si aparece `falta RSNA_RAIZ`, la consola no ha visto la
variable.

Esta comprobación no se pudo hacer al preparar la tarea (la variable real no
se usó): se hizo con una raíz de mentira en una carpeta temporal, con placas
vacías para `test_seleccion_casos.py` (9 pasan) y con dos DICOM sintéticos
para `test_contrato_mcp.py` (8 pasan y las 2 del recorte se saltan por los
pesos).
---

### Tarea 3: La red del compose y la guía de despliegue

El compose deja de llevar el nombre de la red de Docker de la instalación
donde corre n8n: la clave pasa a ser `red_n8n` y el nombre lo pone quien
despliega en `RED_N8N`, que es **obligatoria y sin valor por defecto** (spec de
SP5 §6.1). La guía de despliegue se actualiza entera en lo que toca a la red,
y gana el aviso del redespliegue.

**Ficheros:**
- Modificar: `servidor/docker-compose.yml` (líneas 72-73, 82, 120, 123 y 128)
- Modificar: `servidor/.env.ejemplo` (gana `RED_N8N`)
- Modificar: `docs/sp2-despliegue.md` (18 ediciones, todas las de la red)
- Modificar: `docs/sp3-operacion.md` (línea 586)
- Prueba: `tests/test_arrancar.py` (cuatro pruebas nuevas al final, y `import re`)

**Interfaces:**
- Consume: nada de las otras tareas del plan. No depende de ninguna y ninguna
  depende de ella.
- Produce: en `servidor/docker-compose.yml`, la red `red_n8n` (externa) con
  `name: ${RED_N8N:?define RED_N8N con el nombre de la red externa de n8n}`,
  usada por los servicios `copiloto-mcp` y `copiloto-bd`; en
  `servidor/.env.ejemplo`, la línea `RED_N8N=cambiar-esto`; en la guía, el
  marcador `<RED_N8N>` para el nombre de la red y `<id-de-la-red>` para su
  identificador.
- Deja para la tarea 6, en `docs/sp2-despliegue.md`: los nombres de
  contenedores ajenos, la pila de mensajería ajena, la cuenta del remoto y las
  rutas de la máquina (diez líneas; el paso 6 dice cuáles). **Las ediciones de
  esta tarea mueven los números de línea de la guía**: el paso 6 da la
  correspondencia.

**Decisiones de esta tarea** (donde el contrato dejaba margen):

- **D3.1. `RED_N8N` se declara en `servidor/.env`, no delante de cada
  orden** (decisión aceptada al ensamblar el plan)**.** Con `${RED_N8N:?…}` aborta *cualquier* `docker compose` que lea el
  fichero (`ps`, `exec`, `logs`, `stop`, no solo `up`), y la guía tiene más de
  veinte. Ponerla delante de cada una deja veinte sitios donde olvidarla;
  ponerla en el `.env` que Compose lee solo (el mismo que ya lleva la
  contraseña de la base) las cubre todas, incluida la orden de una línea del
  redespliegue. La guía lo dice en el paso 4, y donde la variable la lee el
  shell y no Compose (el `docker run --network` del paso 6, el caso B en
  local) la orden la carga o la exporta de forma explícita.
- **D3.2. El valor de ejemplo es `cambiar-esto`**, uno de los que el spec
  §6.1 admite en ficheros de configuración. Si alguien copia la plantilla sin
  editarla, Compose falla con «network … could not be found»: el fallo seguro.
- **D3.3. La salida literal del `grep` se regenera** sobre el compose nuevo
  (ya estaba desfasada: enseñaba cuatro líneas de cuando había un servicio).
  Como ahora enseña el segundo contenedor y el volumen, se corrigen las dos
  filas de la tabla de encima que la contradecían y los dos párrafos del paso
  12 que decían que `-v` en el `down` era inofensivo: desde SP3 borra la
  base, y el aviso del redespliegue pide justo lo contrario. El resto de lo
  que la guía de SP2 no cuenta de la base de SP3 no se toca aquí.
- **D3.4. Un solo commit.** El compose y la guía que lo explica cambian
  juntos: un commit con el compose nuevo y la guía vieja dejaría versionada
  una guía que manda arrancar sin la variable.

**Lo que no se puede verificar aquí.** En la máquina de desarrollo no se
arranca Docker: ni `docker compose config` ni el texto exacto del mensaje de
Compose cuando falta la variable están comprobados. Las pruebas leen el
compose como texto y como YAML (PyYAML no interpola `${…}`), que es lo que se
puede afirmar sin Docker. La comprobación con Docker queda en el paso 8, para
el usuario, en el VPS.

**Finales de línea.** El repositorio tiene `core.autocrlf=true`: los ficheros
del árbol de trabajo están en CRLF. Edita con la herramienta de edición (que
conserva los finales de línea del fichero); no reescribas los ficheros enteros
con un heredoc.

- [ ] **Paso 1: Saber cómo están hoy las pruebas que leen el compose**

Desde la raíz del repo:

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_arrancar.py tests/test_sesion.py
```

Esperado: `34 passed` (5 de `tests/test_arrancar.py` y 29 de
`tests/test_sesion.py`), sin saltos ni fallos. Son las dos únicas pruebas del
repo que leen `servidor/docker-compose.yml`, y las dos miran
`PREVALENCIA_LOCAL`, no la red.

- [ ] **Paso 2: Escribir las pruebas que fallan**

En `tests/test_arrancar.py`, en el bloque de importaciones del principio,
entre `import os` e `import subprocess`, añade:

```python
import re
```

Y al final del fichero, después de la última línea
(`assert servicios["copiloto-mcp"]["environment"]["PREVALENCIA_LOCAL"] == "0.1466"`),
deja dos líneas en blanco y añade:

```python
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
    yaml = pytest.importorskip("yaml")
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
    assert "${RED_N8N:-" not in guia
    assert "${RED_N8N:?" in guia
    # La fila de la tabla de variables (paso 10) lo dice con todas las letras.
    assert "| `RED_N8N` | **ninguno: es obligatoria** |" in guia
```

- [ ] **Paso 3: Correrlas y verlas fallar**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_arrancar.py
```

Esperado: `4 failed, 5 passed`. Fallan las cuatro nuevas, cada una por lo
suyo:

| Prueba | Falla en | Porque |
| :--- | :--- | :--- |
| `test_el_compose_exige_RED_N8N_y_no_le_pone_valor_por_defecto` | `assert all(uso.startswith("${RED_N8N:?") …)` | el único uso de la variable es de la forma `${RED_N8N:-…}`, con un nombre por defecto |
| `test_los_dos_servicios_van_a_la_red_externa_red_n8n` | `assert compose["networks"] == {…}` | la clave de la red es otra y su `name` lleva valor por defecto |
| `test_el_env_de_ejemplo_declara_RED_N8N_con_un_valor_de_ejemplo` | `assert "RED_N8N=cambiar-esto" in lineas` | la plantilla no tiene esa línea |
| `test_la_guia_de_despliegue_no_promete_un_valor_por_defecto_para_la_red` | `assert "${RED_N8N:-" not in guia` | la guía copia el bloque viejo del compose |

Si alguna de las cuatro pasa ya, para: el árbol no es el del commit
`1f328da` en estos ficheros.

- [ ] **Paso 4: El compose y la plantilla del entorno**

En `servidor/docker-compose.yml`, de abajo arriba para que los números de
línea (los del commit `1f328da`) no se muevan:

**Línea 128**, la última del bloque `networks:`, la que empieza por
`    name: ${RED_N8N:-` y da un nombre por defecto. En su lugar van estas seis
líneas (cinco de comentario, que continúan el comentario de las líneas
125-127, y la del nombre):

```yaml
    #
    # Sin valor por defecto a proposito: el nombre de esa red es de quien
    # despliega y no vive en el repositorio. Se declara en `servidor/.env`
    # (RED_N8N=...) o en el entorno de la sesion; si falta o esta vacia,
    # Compose aborta con el mensaje de abajo antes de crear nada.
    name: ${RED_N8N:?define RED_N8N con el nombre de la red externa de n8n}
```

**Línea 123**, la clave de la red (la única línea con dos espacios de sangría
dentro de `networks:`, que termina en `_network:`). Pasa a:

```yaml
  red_n8n:
```

**Línea 120**, el único elemento de la lista `networks:` del servicio
`copiloto-bd` (seis espacios, guion, y el nombre de la clave vieja). Pasa a:

```yaml
      - red_n8n
```

**Línea 82**, lo mismo en el servicio `copiloto-mcp`. Pasa a:

```yaml
      - red_n8n
```

**Líneas 72-73**, dentro del comentario del bloque `logging:` de
`copiloto-mcp`: la 72 empieza por `      # lo comparten dos PostgreSQL, ` y
nombra un producto de la pila ajena; la 73 es
`      # muere no es este servicio.`. Las dos pasan a:

```yaml
      # lo comparten dos PostgreSQL, los contenedores ajenos y n8n; cuando se
      # llena, el que muere no es este servicio.
```

El bloque `networks:` del final queda así, entero:

```yaml
networks:
  red_n8n:
    external: true
    # La red la posee la infraestructura del cliente, donde ya corre n8n. Este
    # servicio solo se une a ella: asi n8n lo alcanza por nombre de servicio y
    # la radiografia no sale de la maquina.
    #
    # Sin valor por defecto a proposito: el nombre de esa red es de quien
    # despliega y no vive en el repositorio. Se declara en `servidor/.env`
    # (RED_N8N=...) o en el entorno de la sesion; si falta o esta vacia,
    # Compose aborta con el mensaje de abajo antes de crear nada.
    name: ${RED_N8N:?define RED_N8N con el nombre de la red externa de n8n}
```

En `servidor/.env.ejemplo`, después de la línea `COPILOTO_BD_PASSWORD=` y
antes del comentario `# AUC_VALIDACION y UMBRAL no van aqui: …`, añade:

```bash
# Nombre de la red externa de Docker donde ya corre n8n. Es OBLIGATORIA y no
# tiene valor por defecto: sin ella, cualquier `docker compose` de este
# proyecto aborta con «define RED_N8N con el nombre de la red externa de n8n».
# El nombre real se lee en el VPS con `docker network ls`
# (docs/sp2-despliegue.md, pasos 2.2 y 4); el de aqui es solo un ejemplo.
RED_N8N=cambiar-esto
```

El fichero queda así, entero:

```bash
# servidor/.env.ejemplo
# Copia esto a `.env` en el VPS y pon los valores reales.
# El `.env` NO se versiona.
COPILOTO_BD_PASSWORD=
# Nombre de la red externa de Docker donde ya corre n8n. Es OBLIGATORIA y no
# tiene valor por defecto: sin ella, cualquier `docker compose` de este
# proyecto aborta con «define RED_N8N con el nombre de la red externa de n8n».
# El nombre real se lee en el VPS con `docker network ls`
# (docs/sp2-despliegue.md, pasos 2.2 y 4); el de aqui es solo un ejemplo.
RED_N8N=cambiar-esto
# AUC_VALIDACION y UMBRAL no van aqui: copiloto-mcp los trae clavados en su
# propio bloque del compose, no los lee desde el entorno.
```

- [ ] **Paso 5: Correr las pruebas: queda una en rojo, la de la guía**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_arrancar.py
```

Esperado: `1 failed, 8 passed`. La que falla es
`test_la_guia_de_despliegue_no_promete_un_valor_por_defecto_para_la_red`, en
su primera aserción.

Y la salida del `grep` que la guía va a citar como literal:

```bash
cd servidor && grep -nE '^\s*(name|ports|volumes|external|container_name):' docker-compose.yml; cd ..
```

Esperado, exactamente:

```
5:name: copiloto-mcp
13:    container_name: copiloto-mcp
93:    container_name: copiloto-bd
101:    volumes:
124:    external: true
133:    name: ${RED_N8N:?define RED_N8N con el nombre de la red externa de n8n}
135:volumes:
```

Si los números no son esos, el comentario del paso 4 no tiene las líneas que
tiene que tener: corrígelo antes de tocar la guía, que copia esta salida.

- [ ] **Paso 6: La guía de despliegue y la línea de `docs/sp3-operacion.md`**

`docs/sp2-despliegue.md` tiene 1 241 líneas. Las 18 ediciones van **en
este orden, de la última a la primera**, para que los números de línea (los
del commit `1f328da`) sigan valiendo mientras editas. Cada una dice qué
líneas sustituye, qué son, y el texto nuevo entero. Lo que se sustituye no se
cita: lleva el nombre de la red. No toques ninguna otra línea del fichero.

**G1. Líneas 1230-1232**: el párrafo «Añadir `-v` / `--volumes` al `down` es inofensivo **aquí**…». Texto nuevo:

````markdown
Añadir `-v` / `--volumes` al `down` **tampoco es inofensivo aquí**: borra el
volumen `copiloto_bd_datos`, que es la base del copiloto. Y en el stack de al
lado ese mismo flag borra la base de datos del cliente.
````

**G2. Línea 1226**: primera fila de la tabla «Tres comandos que NO hay que ejecutar en el VPS» (el `docker network rm`). Texto nuevo:

````markdown
| `docker network rm <RED_N8N>` | dejaría a n8n, a nginx y a la API del cliente sin red común. Esa red **no es nuestra** |
````

**G3. Líneas 1177-1179**: el párrafo «`docker compose down` **no borra la red externa.**…». Texto nuevo:

````markdown
`docker compose down` **no borra la red externa.** Comprobado: después del
`down`, `docker network ls` sigue mostrando la red de `RED_N8N` intacta, con
n8n dentro. Compose no borra lo que no creó.
````

**G4. Líneas 1161-1163**: el párrafo «Y no teclees nunca `-v` ni `--volumes`…» del apartado «Bajarlo», que dice que aquí es inofensivo (dejó de serlo con la base de SP3). Texto nuevo:

````markdown
Y no teclees nunca `-v` ni `--volumes` en ese `down`. **Aquí no es
inofensivo**: desde SP3 el proyecto tiene un volumen, `copiloto_bd_datos`, y
con ese flag se borra la base de datos del copiloto. Aplicado al stack de al
lado, borra los datos del cliente.
````

**G5. Líneas 1095-1113**: el cuerpo del recuadro «La red no aparece: NO la crees en el VPS», desde «Cuando el compose dice que la red externa no existe…» hasta la valla que cierra el bloque de los tres pasos numerados. Texto nuevo:

````markdown
Cuando el compose dice que la red externa no existe, la reacción natural es
crearla. **En el VPS eso es justo lo que no hay que hacer.** Si la red real se
llama de otra forma, un `docker network create` con el nombre que pusiste en
`RED_N8N` te deja una red vacía, el contenedor arranca, el estado dice
`healthy`, todo parece bien — y n8n no lo alcanza nunca, porque están en redes
distintas. Es el fallo silencioso que el paso 2.2 existe para evitar, y lo
habrías provocado tú.

El orden correcto es siempre este:

```bash
# 1. cual es la red real
docker network ls

# 2. si n8n no se deja adivinar por el nombre, preguntaselo
docker inspect <nombre-del-contenedor-de-n8n> --format '{{range $red, $c := .NetworkSettings.Networks}}{{println $red}}{{end}}'

# 3. corregir RED_N8N en servidor/.env con el nombre real, sin editar el
#    compose, y arrancar
docker compose up -d
```
````

**G6. Línea 1077**: primera fila de la tabla de errores del paso 11 (el síntoma de la red declarada como externa que no aparece): se reescribe y gana delante la fila del síntoma nuevo, el de la variable ausente. Texto nuevo:

````markdown
| `required variable RED_N8N is missing a value: define RED_N8N con el nombre de la red externa de n8n`, en **cualquier** `docker compose` | falta `RED_N8N` o está vacía: no está en `servidor/.env`, o el `.env` no está junto al compose | añadir la línea `RED_N8N=` con el nombre real a `servidor/.env` (paso 4). No tiene valor por defecto, a propósito |
| `network <RED_N8N> declared as external, but could not be found` | el valor de `RED_N8N` no es el nombre de ninguna red que exista | **primero**: averigua el nombre real con `docker network ls` y corrige `RED_N8N` en `servidor/.env`. Ver el recuadro de abajo |
````

**G7. Línea 1055**: fila `RED_N8N` de la tabla de variables del paso 10. Texto nuevo:

````markdown
| `RED_N8N` | **ninguno: es obligatoria** | nombre de la red externa de n8n. Se declara en `servidor/.env` (paso 4), no se edita el compose. Sin ella, cualquier `docker compose` aborta |
````

**G8. Línea 801**: la línea en blanco que separa el final del apartado del redespliegue (la cita «Construir consume la máquina del cliente») del título «## 7. Medir la latencia dentro del contenedor»: en su lugar entra un apartado nuevo. Texto nuevo:

````markdown

### El primer redespliegue con `RED_N8N` obligatoria: volver a crear los contenedores

Hasta SP5 el compose traía escrito el nombre de la red. Desde que `RED_N8N` es
obligatoria, **la clave de la red cambió en el compose** (ahora es `red_n8n`)
y el nombre ya no viene en el fichero. Una instalación levantada con el
compose anterior necesita, **una sola vez**, que los dos contenedores se
vuelvan a crear. La base de datos **no se toca**: sus datos viven en el volumen
`copiloto_bd_datos`, que sobrevive al `down` siempre que no lleve `-v`.

Mientras dura, unos dos minutos, n8n no alcanza al copiloto ni a la base: los
bots contestan con su mensaje de error. Hazlo cuando no haya consultas en curso.

**1. Antes del `git pull`, declarar la variable.** El nombre es el de la red
donde está hoy el contenedor; pregúntaselo a él:

```bash
docker inspect copiloto-mcp --format '{{range $red, $c := .NetworkSettings.Networks}}{{println $red}}{{end}}'
```

Añade a `/opt/copiloto/servidor/.env` la línea `RED_N8N=` seguida de ese
nombre, y comprueba que quedó:

```bash
grep -c '^RED_N8N=.' /opt/copiloto/servidor/.env
```

Esperado: `1`.

**2. Apuntar el volumen de la base**, para compararlo al final:

```bash
docker volume ls --filter name=copiloto_bd_datos
```

**3. Traer el código y comprobar que el compose nuevo se deja leer**, sin
levantar nada:

```bash
cd /opt/copiloto && git pull --ff-only && docker compose -f servidor/docker-compose.yml config --quiet && echo "el compose se deja leer"
```

Si en vez de la frase sale `required variable RED_N8N is missing a value`,
vuelve al punto 1: **no sigas**.

**4. Bajar por nombre de proyecto y volver a levantar.** El `down` va **sin
`-v` ni `--volumes`**: con cualquiera de los dos se borra la base.

```bash
docker compose -p copiloto-mcp down
cd /opt/copiloto && docker compose -f servidor/docker-compose.yml up -d --build
```

**5. Comprobar** que el volumen es el mismo del punto 2, que los dos
contenedores están `healthy` y que siguen en la red de n8n:

```bash
docker volume ls --filter name=copiloto_bd_datos
docker compose -f servidor/docker-compose.yml ps
docker inspect copiloto-mcp copiloto-bd --format '{{.Name}}: {{range $red, $c := .NetworkSettings.Networks}}{{$red}} {{end}}'
```

Y termina con la sonda de salud del paso 6 y con una consulta de prueba por el
bot: que la base conserva lo que tenía se ve en que el historial sigue ahí
(`docs/sp3-operacion.md`).

A partir de aquí los redespliegues vuelven a ser la orden de una línea de
arriba.

````

**G9. Línea 764**: la última línea de la cuarta viñeta («perfecto**, porque el compose no publica puertos a propósito.»): se conserva y gana detrás una quinta viñeta. Texto nuevo:

````markdown
  perfecto**, porque el compose no publica puertos a propósito.
- **No lleva `RED_N8N` delante, y no le hace falta.** Compose la lee de
  `servidor/.env`, que está junto al compose aunque la orden se lance desde
  `/opt/copiloto` (paso 4). Si esa línea falta en el `.env`, la orden aborta en
  el primer `docker compose`, antes de reconstruir nada.
````

**G10. Línea 751**: la frase «Cuatro cosas que esa línea tiene por un motivo:». Texto nuevo:

````markdown
Cinco cosas que esa línea tiene, o no tiene, por un motivo:
````

**G11. Líneas 654-664**: el bloque de código con el `docker run --rm --network …` del apartado «Comprobar que se alcanza por nombre de servicio» y el párrafo «Es la **misma variable**…» que lo sigue. Texto nuevo:

````markdown
```bash
export RED_N8N="$(grep '^RED_N8N=' .env | cut -d= -f2-)"
docker run --rm --network "${RED_N8N:?define RED_N8N con el nombre de la red externa de n8n}" python:3.12-slim python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://copiloto-mcp:8000/salud')))"
unset RED_N8N
```

Es la **misma variable** con la que levantaste el compose, y por eso va aquí en
vez del nombre literal. Pero esta orden no la ejecuta Compose, la ejecuta tu
shell, y **el shell no lee `servidor/.env`**: la primera línea se la carga para
esta sesión y la última la retira. Si arrancaste con `RED_N8N=copiloto-local`
exportada (caso B del paso 4), sáltate esas dos líneas: el comando usa
`copiloto-local` solo. Y si la variable no está, el `:?` hace que el comando
aborte con el mismo mensaje que el compose en vez de probar suerte con otra
red. Un literal aquí obligaría a editarlo a mano cada vez y dejaría que
esta comprobación mirase una red distinta de la que se está usando —justo lo que
esta comprobación existe para descartar.
````

**G12. Líneas 482-546**: todo el apartado 4 desde el bloque `yaml` que copia la sección `networks` del compose hasta el párrafo final «Recuerda que si levantas con…», con los casos A y B. Texto nuevo:

````markdown
```yaml
networks:
  red_n8n:
    external: true
    name: ${RED_N8N:?define RED_N8N con el nombre de la red externa de n8n}
```

**`RED_N8N` es obligatoria y no tiene valor por defecto.** El nombre de la red
es de la instalación donde corre n8n, no del repositorio. Si la variable falta
o está vacía, **cualquier** `docker compose` que lea este fichero —`build`,
`up`, `ps`, `exec`, `logs`, `stop`, `down`— aborta antes de hacer nada, con un
mensaje que termina así:

```
required variable RED_N8N is missing a value: define RED_N8N con el nombre de la red externa de n8n
```

Es el fallo seguro, igual que el de la contraseña de la base: mejor no arrancar
que arrancar unido a una red que no es.

### Dónde se declara `RED_N8N`

En **`servidor/.env`**, el fichero sin versionar que ya lleva la contraseña de
la base (la plantilla es `servidor/.env.ejemplo`). Compose lo lee solo, porque
está junto al `docker-compose.yml`: vale igual si lanzas la orden desde
`servidor/` que si la lanzas desde la raíz con
`-f servidor/docker-compose.yml`. Así **ningún comando de esta guía necesita
llevar la variable delante**, y no hay forma de olvidarla en uno.

Edita `servidor/.env` y añade la línea, con el nombre que apuntaste en el paso
2.2 en lugar del marcador:

```
RED_N8N=<RED_N8N>
```

Y comprueba, sin levantar nada, que Compose ya la lee:

```bash
cd servidor
docker compose config --quiet && echo "el compose se deja leer"
```

`config` solo lee e interpola: no crea, no arranca y no toca ningún contenedor.
Si imprime el mensaje de `required variable`, la línea no está en `.env`, está
vacía, o el `.env` no está en `servidor/`.

Una variable `RED_N8N` exportada en la sesión **manda sobre la de `.env`**. Es
lo que usa el caso B, y es también el motivo de no dejarla exportada en el VPS:
haz `unset RED_N8N` si la pusiste a mano.

### Caso A: en el VPS, donde n8n ya corre

**No se crea ni se toca nada.** La red ya existe y la posee la infraestructura
del cliente. Solo confirma que está y cómo se llama:

```bash
docker network ls
```

Ese nombre, tal cual, es el que va en `servidor/.env`. **No edites el
compose**: para eso está la variable.

Para averiguar con certeza en qué red está n8n, mírala desde su propio
contenedor en vez de adivinar por el nombre:

```bash
docker inspect <nombre-del-contenedor-de-n8n> --format '{{json .NetworkSettings.Networks}}'
```

### Caso B: en local, para probar el despliegue desde cero

Aquí n8n no corre (vive en el VPS), así que la red externa no existe: con el
nombre de la red real en `RED_N8N`, el compose fallaría con `network <RED_N8N>
declared as external, but could not be found`.

Créate una red **con un nombre de tirar**, y pásasela por `RED_N8N`,
exportándola para toda la sesión:

```bash
docker network create copiloto-local
export RED_N8N=copiloto-local
docker compose up -d
```

Y cuando acabes, primero baja el contenedor y luego borra **esa** red:

```bash
docker compose down
docker network rm copiloto-local
unset RED_N8N
```

El `export` no es un detalle: con `RED_N8N=copiloto-local` escrito solo delante
del `up`, el `docker compose down` de después ya no tendría la variable y
abortaría.

El nombre de tirar no es remilgo: es para que el nombre de la red de producción
**nunca aparezca en esta guía al lado de un `docker network rm`**. Si lo hiciera,
bastaría un copiar y pegar despistado en la sesión equivocada para dejar a n8n,
a nginx y a la API del cliente sin red común. Docker se niega a borrar una red
con contenedores conectados, pero no si en ese momento están parados, así que la
protección no es de fiar. Para eso está la variable.

Recuerda que si levantas con `RED_N8N=copiloto-local`, **todos** los comandos
posteriores que mencionen la red —el `docker run --network ...` del paso 6— usan
también `copiloto-local`: con el `export` hecho, lo hacen solos.
````

**G13. Línea 266**: fila de la tabla del resumen que dice a qué red se une el contenedor. Texto nuevo:

````markdown
| ese contenedor se **une** a la red externa de n8n, la que nombra `RED_N8N` | la red en sí: no se crea, ni se altera, ni se borra |
````

**G14. Líneas 177-179**: el bloque de código del apartado 2.3 con el `docker network inspect` (las tres líneas: valla, orden, valla). Texto nuevo:

````markdown
Pon en lugar de `<RED_N8N>` el nombre que apuntaste en el paso 2.2:

```bash
docker network inspect <RED_N8N> --format '{{range .Containers}}{{println .Name}}{{end}}'
```
````

**G15. Líneas 153-170**: todo el cuerpo del apartado 2.2, desde «El compose se une a una red…» hasta el final del párrafo «Lo que importa es la columna `NAME`…». Texto nuevo:

````markdown
El compose se une a una red que **ya tiene que existir**, y su nombre **no
está en el repositorio**: se lo das tú en la variable `RED_N8N` (paso 4). Si el
nombre no coincide carácter por carácter, Compose aborta antes de crear nada —
que es el fallo seguro: mejor eso que dos contenedores levantados sin verse.

```bash
docker network ls
```

Esperado, entre las demás redes de la máquina, una línea como esta:

```
NETWORK ID       NAME        DRIVER    SCOPE
<id-de-la-red>   <RED_N8N>   bridge    local
```

Lo que importa es la columna `NAME`: **apunta el nombre exacto** de la red
donde corre n8n. Si hay varias y no es evidente cuál es, el paso 2.3 lo
resuelve preguntándoselo a n8n. Ese nombre es el valor de `RED_N8N`, y **no se
escribe en el compose**: va en `servidor/.env` (paso 4).
````

**G16. Líneas 140-149**: el bloque de la «Salida literal» del `grep` (de la valla que lo abre a la que lo cierra) y el párrafo «Cuatro líneas: …» que lo sigue. Texto nuevo:

````markdown
```
5:name: copiloto-mcp
13:    container_name: copiloto-mcp
93:    container_name: copiloto-bd
101:    volumes:
124:    external: true
133:    name: ${RED_N8N:?define RED_N8N con el nombre de la red externa de n8n}
135:volumes:
```

Siete líneas: el nombre del proyecto, los dos contenedores (el servicio y,
desde SP3, su base de datos), la red marcada como externa y el nombre de esa
red, que **no está escrito en el fichero**: lo pone quien despliega, en
`RED_N8N` (paso 4). Los dos `volumes:` son el mismo volumen con nombre,
`copiloto_bd_datos`, que gestiona Docker: no es una carpeta del host. Y
**ninguna** línea `ports:`, que es lo que querías comprobar.
````

**G17. Línea 128**: fila de la misma tabla que dice que no hay `volumes:` (desde SP3 hay uno, con nombre, y la salida del `grep` lo enseña). Texto nuevo:

````markdown
| El único `volumes:` es un volumen con nombre que gestiona Docker, `copiloto_bd_datos`, para la base: no monta ni escribe ninguna carpeta del host | el mismo fichero |
````

**G18. Línea 125**: fila de la tabla «Por qué no se toca nada» que dice que el compose define un solo servicio (desde SP3 son dos, y la salida del `grep` de abajo lo enseña). Texto nuevo:

````markdown
| El compose define **dos servicios**, `copiloto-mcp` y, desde SP3, su base `copiloto-bd`; ninguno es de otro stack | `servidor/docker-compose.yml` |
````

En `docs/sp3-operacion.md`, **línea 586**: la línea de la lista «Lo que no hay que teclear nunca en ese VPS» que lleva el `docker network rm`. Pasa a:

```markdown
`docker network rm <RED_N8N>`, `docker network prune`, y
```

Comprueba el resultado:

```bash
grep -c "" docs/sp2-despliegue.md
grep -n -i "_network" servidor/docker-compose.yml servidor/.env.ejemplo docs/sp2-despliegue.md docs/sp3-operacion.md
grep -c "RED_N8N" docs/sp2-despliegue.md
```

Esperado: `1374` en la primera; **ninguna línea** en la segunda (el
nombre de la red, en cualquiera de sus formas, terminaba así); `39` en
la tercera.

Lo que queda en la guía con identificadores es de la tarea 6, y son **diez
líneas**. Con la numeración del commit `1f328da` y con la que deja esta
tarea:

| Línea en `1f328da` | Línea tras esta tarea | Clase |
| ---: | ---: | :--- |
| 107 | 107 | nombre de un contenedor ajeno (salida de ejemplo de `docker ps`) |
| 108 | 108 | ídem |
| 182 | 192 | nombre de un contenedor ajeno (apartado 2.3) |
| 323 | 333 | cuenta del remoto (URL del clon) |
| 332 | 342 | ruta de la máquina de desarrollo |
| 333 | 343 | ídem |
| 366 | 376 | ídem |
| 467 | 477 | cuenta del remoto (URL del clon con el alias) |
| 716 | 773 | pila de mensajería ajena |
| 866 | 995 | pila de mensajería ajena |

En `docs/sp3-operacion.md` quedan trece líneas, ninguna de la red: son de las
tareas 4 y 6.

- [ ] **Paso 7: Correr las pruebas y verlas pasar**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_arrancar.py tests/test_sesion.py
```

Esperado: `38 passed`.

Y la suite entera, para comprobar que nada que pasara ha pasado a fallar:

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q
```

Esperado: **cuatro aprobadas más que antes de la tarea y ningún fallo ni
error nuevo**. En la copia donde se verificó esta tarea (sin los ficheros que git ignora: la caché de puntuaciones, los pesos y el `.env`; y antes de fusionar SP5-B1: con SP5-B1, esa copia da de partida `699 passed, 18 skipped, 7 errors`) la suite pasó de `543 passed, 18 skipped, 7 errors` a `547 passed, 18 skipped, 7 errors`: los 7 errores ya estaban antes de tocar nada (5 son de `tests/test_seleccion_casos.py`, por los ficheros que faltan en la copia) y son los mismos después. En el repo de desarrollo, que sí tiene esos ficheros, y con las tareas anteriores del plan aplicadas, las cifras de partida son otras: apúntalas antes de empezar; lo que tiene que cumplirse es la diferencia.

- [ ] **Paso 8: Verificación en el VPS (la hace el usuario; aquí no hay Docker)**

Este paso **no lo ejecuta quien aplica el plan**: no se arranca Docker en la
máquina de desarrollo y el redespliegue en producción lo decide el usuario.
Se deja escrito para él. No bloquea el commit.

Sin tocar nada en marcha, con el código nuevo en una carpeta aparte o tras el
`git pull` del redespliegue:

```bash
cd servidor
RED_N8N= docker compose config --quiet; echo "salida: $?"
RED_N8N=cambiar-esto docker compose config | grep -A3 '^networks:'
```

Y, desde la raíz del repositorio, que Compose lee la variable del `.env` que
está junto al compose aunque se le llame con `-f` desde otra carpeta (es en
lo que descansa la decisión D3.1, y aquí no se pudo comprobar):

```bash
cd ..
docker compose -f servidor/docker-compose.yml config --quiet && echo "lee servidor/.env"
```

Si esa orden falla pidiendo `RED_N8N` con la variable ya escrita en
`servidor/.env`, Compose no está leyendo ese fichero: se lanza desde
`servidor/` o con `--env-file servidor/.env`, y se corrige la guía.

Esperado en la primera: un error que nombra `RED_N8N` y termina en `define
RED_N8N con el nombre de la red externa de n8n`, y `salida:` distinta de 0.
(`RED_N8N=` vacía delante manda sobre la del `.env`, así que la orden prueba
la ausencia aunque el `.env` ya la tenga.) Esperado en la segunda: la red
`red_n8n` con `external: true` y `name: cambiar-esto`. `config` solo lee: no
crea ni arranca nada. Si el texto del error no es el que la guía cita en el
paso 4 y en la tabla del paso 11 («required variable RED_N8N is missing a
value: …»), se corrige la cita de la guía con el texto real.

El redespliegue en sí es el apartado nuevo de la guía, «El primer redespliegue
con `RED_N8N` obligatoria»: declarar la variable en `servidor/.env` **antes**
del `git pull`, `down` por nombre de proyecto **sin `-v`**, `up -d --build`, y
comprobar que el volumen `copiloto_bd_datos` sigue ahí.

- [ ] **Paso 9: Commit**

```bash
git add servidor/docker-compose.yml servidor/.env.ejemplo docs/sp2-despliegue.md docs/sp3-operacion.md tests/test_arrancar.py
git commit -m "fix(anonimato): la red del compose es red_n8n y RED_N8N es obligatoria

El compose llevaba el nombre de la red de la instalacion en la clave y como
valor por defecto. La clave pasa a ser red_n8n y el nombre lo pone quien
despliega en RED_N8N, sin valor por defecto: sin ella Compose aborta.

La guia de despliegue lo cuenta entero: la variable va en servidor/.env, la
salida literal del grep se regenera, la tabla de errores gana el sintoma de la
variable ausente, y hay un apartado para el primer redespliegue, que exige
volver a crear los contenedores (down sin -v, up) con el volumen de la base
intacto.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
---

### Tarea 4: Los workflows con marcadores y la herramienta que los pone y los quita

**Ficheros:**
- Crear: `scripts/marcadores_n8n.py`
- Crear: `n8n/valores.ejemplo.json`
- Crear: `tests/test_marcadores_n8n.py`
- Modificar: `.gitignore` (un bloque nuevo al final)
- Modificar: `n8n/copiloto-mantenimiento.json`, `n8n/copiloto-paciente.json`, `n8n/copiloto-profesional.json` (con un script desechable que NO se versiona; sin reformatear)
- Modificar: `tests/test_mantenimiento.py` (docstring del módulo, las dos constantes `CRED_*` y la aserción de la URL de las sondas)
- Modificar: `tests/test_flujo_paciente.py` (la aserción de la credencial)
- Modificar: `tests/test_flujo_profesional.py` (la aserción de la credencial y tres docstrings)
- Modificar: `tests/decidir.mjs`, `tests/profesional.mjs`, `tests/mantenimiento.mjs` (una entrada de prueba, una entrada y un comentario, una IP)
- Modificar: `docs/sp3-operacion.md` (§4, paso 3; y una subsección nueva al final del §7)

**Interfaces:**
- Consume: nada de otras tareas de este plan. Lee los tres exports de `n8n/`.
- Produce, en `scripts/marcadores_n8n.py`:
  - `URL_N8N = "https://n8n.ejemplo.test"` y `MARCADORES`, tupla con los diez marcadores conocidos:
    `URL_N8N`, `CRED_TELEGRAM_PACIENTE`, `CRED_TELEGRAM_PROFESIONAL`, `CRED_TELEGRAM_AVISOS`,
    `CRED_POSTGRES_COPILOTO`, `CRED_SECRETO_PACIENTE`, `CRED_SECRETO_PROFESIONAL`,
    `bot-paciente`, `bot-profesional`, `bot-avisos`;
  - `VALORES_LOCALES` (`n8n/valores.local.json`) y `VALORES_DE_EJEMPLO` (`n8n/valores.ejemplo.json`);
  - `class ErrorDeMarcadores(ValueError)`;
  - `marcadores_de(texto) -> set` (los marcadores conocidos presentes);
  - `aplicar(texto, valores) -> str` (marcador → valor real) y `retirar(texto, valores) -> str` (valor real → marcador);
  - `leer(ruta) -> str` (UTF-8, con CRLF normalizado a LF), `escribir(ruta, texto)` (en LF), `leer_valores(ruta) -> dict`;
  - `convertir(entrada, salida, valores, quitar=False) -> dict` (`{marcador: veces}`);
  - `main(argv=None) -> int`, con `--entrada`, `--salida`, `--valores` (por defecto `n8n/valores.local.json`) y `--retirar`; devuelve 0, o 1 con `ERROR: …` en la salida de errores.
- Produce, en los tres workflows: `credentials.*.id` con el marcador de la tabla del contrato; `credentials.telegramApi.name` con `bot-paciente`, `bot-profesional` o `bot-avisos`; las dos sondas del mantenimiento con `https://n8n.ejemplo.test/webhook/<ruta>`. Los nombres de las credenciales de PostgreSQL y de cabecera, los `webhookId`, los nombres de los nodos y el huso horario NO cambian.

**Notas para quien ejecuta:**
- Las órdenes se corren desde la raíz del repositorio. Hace falta `node` en el PATH.
- **Esta sección no cita ninguna de las cadenas que quita** (el plan también se publica). Las líneas
  viejas se identifican por fichero, número de línea del commit `1f328da` y descripción; las nuevas
  van enteras. Si el número de línea no coincide porque otra tarea ya tocó el fichero, manda la
  descripción (el nombre de la función o del bloque).
- Finales de línea: en el árbol de trabajo los ficheros están en CRLF (`core.autocrlf=true`) y en el
  índice en LF. Los `.py`, `.mjs` y `.md` se editan con la herramienta de edición, que lo respeta; los
  tres JSON los reescribe el script del paso 8 en LF, y git avisa de ello sin que sea un error.
- Las cuentas de pruebas de esta sección («N passed, M skipped») son las de una máquina **sin
  Docker en marcha, sin secretos de Telegram y sin base de datos**. Con Docker en marcha, cinco
  pruebas de `tests/test_mantenimiento.py` levantan una PostgreSQL desechable y pasan en vez de
  saltarse: son cinco `passed` más y cinco `skipped` menos, y nada más cambia.
- Las pruebas que fallan a propósito imprimen en la terminal las cadenas viejas (salen de los
  ficheros, en el diff de la aserción). Es lo esperado; no las copies a ningún fichero del repositorio.
- Al terminar la tarea quedan, de lo que esta tarea toca, dos líneas de `tests/test_mantenimiento.py`
  con el dominio (los datos de prueba de `diagnosticar`, que son de la tarea 1) y varias de
  `docs/sp3-operacion.md` con nombres de bots, rutas y la red (de las tareas 3 y 6). No son de esta.

---

#### Primera parte: la herramienta

- [ ] **Paso 1: Escribir las pruebas de la herramienta, que fallan**

Crea `tests/test_marcadores_n8n.py` con este contenido:

```python
# -*- coding: utf-8 -*-
"""scripts/marcadores_n8n.py: poner y quitar los valores reales de los workflows.

Los exports de `n8n/` se versionan con marcadores (spec de SP5 §6.1) y ya no
son identicos byte a byte a lo desplegado. Aqui se prueba la herramienta que
media entre los dos, sin n8n y sin red: con valores inventados.
"""
import importlib.util
import json
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
N8N = RAIZ / "n8n"
EJEMPLO = N8N / "valores.ejemplo.json"


def _cargar():
    ruta = RAIZ / "scripts" / "marcadores_n8n.py"
    spec = importlib.util.spec_from_file_location("marcadores_n8n", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def mn():
    return _cargar()


@pytest.fixture()
def valores(mn):
    """Un valor inventado por marcador, distinto de los de ejemplo."""
    v = {m: f"valor-{i:02d}-inventado" for i, m in enumerate(mn.MARCADORES)}
    v[mn.URL_N8N] = "https://flujos.inventado.test"
    return v


TEXTO = ('{\n  "url": "https://n8n.ejemplo.test/webhook/copiloto-paciente",\n'
         '  "credentials": {"telegramApi": {"id": "CRED_TELEGRAM_PACIENTE", '
         '"name": "bot-paciente"}}\n}\n')


# --------------------------------------------------------------------------
# Las tres funciones
# --------------------------------------------------------------------------
def test_los_marcadores_son_los_del_contrato(mn):
    assert mn.URL_N8N == "https://n8n.ejemplo.test"
    assert set(mn.MARCADORES) == {
        "https://n8n.ejemplo.test",
        "CRED_TELEGRAM_PACIENTE", "CRED_TELEGRAM_PROFESIONAL",
        "CRED_TELEGRAM_AVISOS", "CRED_POSTGRES_COPILOTO",
        "CRED_SECRETO_PACIENTE", "CRED_SECRETO_PROFESIONAL",
        "bot-paciente", "bot-profesional", "bot-avisos"}
    assert len(mn.MARCADORES) == len(set(mn.MARCADORES))


def test_marcadores_de_dice_los_presentes(mn):
    assert mn.marcadores_de(TEXTO) == {
        "https://n8n.ejemplo.test", "CRED_TELEGRAM_PACIENTE", "bot-paciente"}
    assert mn.marcadores_de("nada que ver") == set()


def test_aplicar_pone_los_valores_y_retirar_los_quita(mn, valores):
    puesto = mn.aplicar(TEXTO, valores)
    assert '"url": "https://flujos.inventado.test/webhook/copiloto-paciente"' in puesto
    assert f'"id": "{valores["CRED_TELEGRAM_PACIENTE"]}"' in puesto
    assert f'"name": "{valores["bot-paciente"]}"' in puesto
    assert mn.marcadores_de(puesto) == set()
    assert mn.retirar(puesto, valores) == TEXTO


def test_aplicar_solo_pide_los_valores_de_los_marcadores_presentes(mn, valores):
    solo = {m: valores[m] for m in mn.marcadores_de(TEXTO)}
    assert mn.aplicar(TEXTO, solo) == mn.aplicar(TEXTO, valores)


def test_la_sustitucion_es_de_una_sola_pasada(mn, valores):
    """Lo que se acaba de poner no se vuelve a sustituir, ni de ida ni de
    vuelta: el texto de alrededor no cambia."""
    texto = "antes https://n8n.ejemplo.test/webhook/x despues bot-avisos."
    puesto = mn.aplicar(texto, valores)
    assert puesto == ("antes https://flujos.inventado.test/webhook/x despues "
                      + valores["bot-avisos"] + ".")
    assert mn.retirar(puesto, valores) == texto


# --------------------------------------------------------------------------
# Los errores
# --------------------------------------------------------------------------
def test_falta_el_valor_de_un_marcador_presente(mn, valores):
    del valores["CRED_TELEGRAM_PACIENTE"]
    with pytest.raises(mn.ErrorDeMarcadores, match="CRED_TELEGRAM_PACIENTE"):
        mn.aplicar(TEXTO, valores)


def test_retirar_exige_el_valor_de_todos_los_marcadores(mn, valores):
    """El que falte no se podria buscar: el export saldria con el en claro."""
    del valores["bot-avisos"]
    with pytest.raises(mn.ErrorDeMarcadores, match="bot-avisos"):
        mn.retirar(TEXTO, valores)


def test_dos_marcadores_no_pueden_compartir_valor(mn, valores):
    valores["CRED_TELEGRAM_AVISOS"] = valores["CRED_TELEGRAM_PACIENTE"]
    for funcion in (mn.aplicar, mn.retirar):
        with pytest.raises(mn.ErrorDeMarcadores, match="comparten valor") as e:
            funcion(TEXTO, valores)
        assert "CRED_TELEGRAM_AVISOS" in str(e.value)
        assert "CRED_TELEGRAM_PACIENTE" in str(e.value)


def test_queda_un_valor_real_tras_retirar(mn, valores):
    """Escrito de otra forma -en mayusculas, o el host sin el esquema- la
    sustitucion exacta no lo ve. Se dice la linea y el marcador, no el valor."""
    en_mayusculas = TEXTO + valores["bot-paciente"].upper() + "\n"
    with pytest.raises(mn.ErrorDeMarcadores, match="quedan valores reales") as e:
        mn.retirar(en_mayusculas, valores)
    assert "bot-paciente en la linea 5" in str(e.value)
    assert valores["bot-paciente"].upper() not in str(e.value)

    solo_el_host = TEXTO + "  visita flujos.inventado.test\n"
    with pytest.raises(mn.ErrorDeMarcadores, match="quedan valores reales") as e:
        mn.retirar(solo_el_host, valores)
    assert "https://n8n.ejemplo.test en la linea 5" in str(e.value)


def test_aplicar_no_acepta_una_entrada_que_ya_lleva_valores_reales(mn, valores):
    mezcla = TEXTO + valores["CRED_POSTGRES_COPILOTO"] + "\n"
    with pytest.raises(mn.ErrorDeMarcadores, match="ya lleva valores reales"):
        mn.aplicar(mezcla, valores)


@pytest.mark.parametrize("malo, dice", [
    ("", "vacio"),
    ("   ", "vacio"),
    (' con-espacio', "espacios"),
    ('con"comilla', "comillas"),
    ("con\\barra", "comillas"),
    ("con\nsalto", "comillas"),
])
def test_un_valor_que_romperia_el_json_no_se_acepta(mn, valores, malo, dice):
    valores["bot-paciente"] = malo
    with pytest.raises(mn.ErrorDeMarcadores, match=dice):
        mn.aplicar(TEXTO, valores)


def test_un_valor_que_no_es_texto_no_se_acepta(mn, valores):
    valores["bot-paciente"] = 7
    with pytest.raises(mn.ErrorDeMarcadores, match="vacio"):
        mn.aplicar(TEXTO, valores)
    with pytest.raises(mn.ErrorDeMarcadores, match="objeto JSON"):
        mn.aplicar(TEXTO, ["lista"])


def test_un_marcador_desconocido_en_los_valores_es_un_error(mn, valores):
    valores["CRED_TELEGRAM_PACIENT"] = "errata"
    with pytest.raises(mn.ErrorDeMarcadores, match="desconocidos.*CRED_TELEGRAM_PACIENT"):
        mn.aplicar(TEXTO, valores)


@pytest.mark.parametrize("url", [
    "https://flujos.inventado.test/", "flujos.inventado.test", "ftp://x.test"])
def test_la_url_va_con_esquema_y_sin_barra_final(mn, valores, url):
    valores[mn.URL_N8N] = url
    with pytest.raises(mn.ErrorDeMarcadores, match="URL base"):
        mn.aplicar(TEXTO, valores)


def test_un_valor_no_puede_confundirse_con_un_marcador_ni_con_otro_valor(mn, valores):
    malo = dict(valores, **{"bot-paciente": "CRED_TELEGRAM_AVISOS"})
    with pytest.raises(mn.ErrorDeMarcadores, match="se confunde con el marcador"):
        mn.aplicar(TEXTO, malo)
    malo = dict(valores, **{"bot-paciente": "paciente"})
    with pytest.raises(mn.ErrorDeMarcadores, match="se confunde con el marcador"):
        mn.aplicar(TEXTO, malo)
    malo = dict(valores, **{"bot-paciente": valores["bot-avisos"][:-3]})
    with pytest.raises(mn.ErrorDeMarcadores, match="contenido en el de bot-avisos"):
        mn.aplicar(TEXTO, malo)


# --------------------------------------------------------------------------
# La linea de comandos
# --------------------------------------------------------------------------
@pytest.fixture()
def carpeta(tmp_path, valores):
    (tmp_path / "valores.json").write_text(json.dumps(valores), encoding="utf-8")
    (tmp_path / "entrada.json").write_bytes(TEXTO.replace("\n", "\r\n").encode("utf-8"))
    return tmp_path


def test_la_cli_pone_y_quita_y_escribe_en_lf(mn, carpeta, valores, capsys):
    argumentos = ["--valores", str(carpeta / "valores.json")]
    assert mn.main(argumentos + ["--entrada", str(carpeta / "entrada.json"),
                                 "--salida", str(carpeta / "sub" / "puesto.json")]) == 0
    dicho = capsys.readouterr().out
    assert "CRED_TELEGRAM_PACIENTE: 1" in dicho
    assert "valores puestos: 3 sustituciones" in dicho
    crudo = (carpeta / "sub" / "puesto.json").read_bytes()
    assert b"\r" not in crudo
    assert crudo.decode("utf-8") == mn.aplicar(TEXTO, valores)

    assert mn.main(argumentos + ["--retirar",
                                 "--entrada", str(carpeta / "sub" / "puesto.json"),
                                 "--salida", str(carpeta / "vuelta.json")]) == 0
    assert "valores retirados: 3 sustituciones" in capsys.readouterr().out
    assert (carpeta / "vuelta.json").read_bytes() == TEXTO.encode("utf-8")


def test_la_cli_no_pone_valores_reales_encima_de_la_entrada(mn, carpeta, capsys):
    antes = (carpeta / "entrada.json").read_bytes()
    assert mn.main(["--valores", str(carpeta / "valores.json"),
                    "--entrada", str(carpeta / "entrada.json"),
                    "--salida", str(carpeta / "entrada.json")]) == 1
    assert "la salida no puede ser la entrada" in capsys.readouterr().err
    assert (carpeta / "entrada.json").read_bytes() == antes


def test_la_cli_retira_encima_de_la_entrada(mn, carpeta, valores):
    (carpeta / "export.json").write_text(mn.aplicar(TEXTO, valores), encoding="utf-8")
    assert mn.main(["--valores", str(carpeta / "valores.json"), "--retirar",
                    "--entrada", str(carpeta / "export.json"),
                    "--salida", str(carpeta / "export.json")]) == 0
    assert (carpeta / "export.json").read_bytes() == TEXTO.encode("utf-8")


def test_la_cli_dice_que_hacer_si_no_hay_fichero_de_valores(mn, carpeta, capsys):
    assert mn.main(["--valores", str(carpeta / "no-existe.json"),
                    "--entrada", str(carpeta / "entrada.json"),
                    "--salida", str(carpeta / "salida.json")]) == 1
    error = capsys.readouterr().err
    assert "ERROR" in error and "valores.ejemplo.json" in error
    assert not (carpeta / "salida.json").exists()


def test_la_cli_no_escribe_nada_si_hay_un_error(mn, carpeta, valores, capsys):
    del valores["bot-paciente"]
    (carpeta / "valores.json").write_text(json.dumps(valores), encoding="utf-8")
    assert mn.main(["--valores", str(carpeta / "valores.json"),
                    "--entrada", str(carpeta / "entrada.json"),
                    "--salida", str(carpeta / "salida.json")]) == 1
    assert "bot-paciente" in capsys.readouterr().err
    assert not (carpeta / "salida.json").exists()

    (carpeta / "roto.json").write_text("{ esto no es json", encoding="utf-8")
    assert mn.main(["--valores", str(carpeta / "valores.json"),
                    "--entrada", str(carpeta / "roto.json"),
                    "--salida", str(carpeta / "salida.json")]) == 1
    assert "no es un JSON valido" in capsys.readouterr().err


def test_los_valores_por_defecto_son_los_locales_y_git_los_ignora(mn):
    assert mn.VALORES_LOCALES == N8N / "valores.local.json"
    ignorados = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "n8n/valores.local.json" in ignorados


def test_los_valores_de_ejemplo_son_validos_y_cubren_todos_los_marcadores(mn):
    ejemplo = mn.leer_valores(EJEMPLO)
    assert set(ejemplo) == set(mn.MARCADORES)
    assert mn.retirar(mn.aplicar(TEXTO, ejemplo), ejemplo) == TEXTO
```

- [ ] **Paso 2: Correr las pruebas y verlas fallar**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_marcadores_n8n.py`

Esperado: `29 errors`. Todas por lo mismo: la fixture `mn` no puede cargar el script
(`FileNotFoundError: … scripts\marcadores_n8n.py`).

- [ ] **Paso 3: Escribir la herramienta, los valores de ejemplo y el `.gitignore`**

Crea `scripts/marcadores_n8n.py`:

```python
# -*- coding: utf-8 -*-
"""Pone y quita los valores reales de los workflows de n8n.

Los tres exports de `n8n/` se versionan con MARCADORES en vez de los valores
de la instancia donde corren (spec de SP5 §6.1): la URL publica de n8n y los
`id` y nombres de sus credenciales. Por eso un export del repositorio ya no es
identico byte a byte al desplegado, y entre uno y otro media este script.

USO
    Del repositorio a n8n (antes de importar o desplegar):
        python scripts/marcadores_n8n.py --entrada n8n/copiloto-paciente.json --salida <carpeta-temporal>/copiloto-paciente.json

    De n8n al repositorio (antes de versionar un export):
        python scripts/marcadores_n8n.py --retirar --entrada <carpeta-temporal>/export.json --salida n8n/copiloto-paciente.json

Los valores salen de `n8n/valores.local.json` (ignorado por git: marcador ->
valor real), que se crea copiando `n8n/valores.ejemplo.json` y cambiando los
valores de ejemplo por los de la instancia. Con `--valores` se lee otro.

No reformatea: sustituye texto y deja lo demas como estaba, con los finales de
linea en LF. No usa la red ni habla con n8n.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VALORES_LOCALES = REPO / "n8n" / "valores.local.json"
VALORES_DE_EJEMPLO = REPO / "n8n" / "valores.ejemplo.json"

URL_N8N = "https://n8n.ejemplo.test"
MARCADORES = (
    URL_N8N,
    "CRED_TELEGRAM_PACIENTE",
    "CRED_TELEGRAM_PROFESIONAL",
    "CRED_TELEGRAM_AVISOS",
    "CRED_POSTGRES_COPILOTO",
    "CRED_SECRETO_PACIENTE",
    "CRED_SECRETO_PROFESIONAL",
    "bot-paciente",
    "bot-profesional",
    "bot-avisos",
)

# Un valor con alguno de estos caracteres romperia el JSON al sustituirlo.
_PROHIBIDOS = re.compile(r'["\\\x00-\x1f]')


class ErrorDeMarcadores(ValueError):
    """Los valores o la entrada no permiten una sustitucion sin ambiguedad."""


def marcadores_de(texto: str) -> set:
    """Los marcadores conocidos que aparecen en `texto`."""
    return {m for m in MARCADORES if m in texto}


def _nombres(marcadores) -> str:
    return ", ".join(sorted(marcadores))


def _validar(valores: dict) -> None:
    if not isinstance(valores, dict):
        raise ErrorDeMarcadores("los valores tienen que ser un objeto JSON "
                                "{marcador: valor}")
    desconocidos = set(valores) - set(MARCADORES)
    if desconocidos:
        raise ErrorDeMarcadores(
            f"marcadores desconocidos en los valores: {_nombres(desconocidos)}")
    for marcador, valor in valores.items():
        if not isinstance(valor, str) or not valor.strip():
            raise ErrorDeMarcadores(f"el valor de {marcador} esta vacio")
        if valor != valor.strip() or _PROHIBIDOS.search(valor):
            raise ErrorDeMarcadores(
                f"el valor de {marcador} lleva espacios en los extremos, "
                "comillas, barras invertidas o caracteres de control")
    url = valores.get(URL_N8N)
    if url is not None and (not re.match(r"https?://[^/]+", url)
                            or url.endswith("/")):
        raise ErrorDeMarcadores(
            f"el valor de {URL_N8N} tiene que ser la URL base de n8n, con "
            "esquema y sin barra final")
    por_valor = {}
    for marcador, valor in valores.items():
        por_valor.setdefault(valor.lower(), []).append(marcador)
    for repetidos in por_valor.values():
        if len(repetidos) > 1:
            raise ErrorDeMarcadores(
                f"comparten valor: {_nombres(repetidos)}")
    for marcador, valor in valores.items():
        v = valor.lower()
        for otro in MARCADORES:
            if v in otro.lower() or otro.lower() in v:
                raise ErrorDeMarcadores(
                    f"el valor de {marcador} se confunde con el marcador {otro}")
        for otro, su_valor in valores.items():
            if otro != marcador and v in su_valor.lower():
                raise ErrorDeMarcadores(
                    f"el valor de {marcador} esta contenido en el de {otro}")


def _sustituir(texto: str, pares: dict) -> str:
    """Una sola pasada, de la cadena mas larga a la mas corta: lo que se acaba
    de poner no se vuelve a sustituir."""
    if not pares:
        return texto
    claves = sorted(pares, key=len, reverse=True)
    patron = re.compile("|".join(re.escape(c) for c in claves))
    return patron.sub(lambda m: pares[m.group(0)], texto)


def _restos(texto: str, valores: dict) -> list:
    """[(marcador, linea)] de cada valor real que sigue en `texto`, sin
    distinguir mayusculas; de la URL se busca tambien el host a secas."""
    hallados = []
    lineas = texto.lower().split("\n")
    for marcador, valor in valores.items():
        buscados = {valor.lower()}
        if "://" in valor:
            buscados.add(valor.lower().split("://", 1)[1].split("/", 1)[0])
        for numero, linea in enumerate(lineas, 1):
            if any(b in linea for b in buscados):
                hallados.append((marcador, numero))
    return hallados


def _decir_restos(restos: list) -> str:
    return "; ".join(f"el de {m} en la linea {n}" for m, n in restos)


def aplicar(texto: str, valores: dict) -> str:
    """Marcador -> valor real. Falla si falta el valor de un marcador presente
    o si la entrada ya lleva algun valor real."""
    _validar(valores)
    presentes = marcadores_de(texto)
    faltan = presentes - set(valores)
    if faltan:
        raise ErrorDeMarcadores(
            f"faltan en los valores: {_nombres(faltan)}")
    restos = _restos(texto, valores)
    if restos:
        raise ErrorDeMarcadores(
            "la entrada ya lleva valores reales: " + _decir_restos(restos))
    return _sustituir(texto, {m: valores[m] for m in presentes})


def retirar(texto: str, valores: dict) -> str:
    """Valor real -> marcador. Exige el valor de TODOS los marcadores (el que
    falte no se podria buscar) y falla si tras sustituir queda alguno."""
    _validar(valores)
    faltan = set(MARCADORES) - set(valores)
    if faltan:
        raise ErrorDeMarcadores(
            f"faltan en los valores: {_nombres(faltan)}")
    resultado = _sustituir(texto, {v: m for m, v in valores.items()})
    restos = _restos(resultado, valores)
    if restos:
        raise ErrorDeMarcadores(
            "quedan valores reales tras retirar (escritos de otra forma): "
            + _decir_restos(restos))
    return resultado


def leer(ruta) -> str:
    """El fichero en UTF-8 con los finales de linea en LF, venga como venga."""
    with io.open(ruta, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n")


def escribir(ruta, texto: str) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with io.open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)


def leer_valores(ruta) -> dict:
    ruta = Path(ruta)
    if not ruta.exists():
        raise ErrorDeMarcadores(
            f"no existe {ruta}: copia n8n/valores.ejemplo.json a "
            "n8n/valores.local.json y pon los valores de tu instancia")
    try:
        return json.loads(leer(ruta))
    except json.JSONDecodeError as e:
        raise ErrorDeMarcadores(f"{ruta} no es un JSON valido: {e}") from e


def convertir(entrada, salida, valores: dict, quitar: bool = False) -> dict:
    """Lee `entrada`, pone o quita los valores y escribe `salida`. Devuelve
    {marcador: veces} de lo sustituido."""
    entrada, salida = Path(entrada), Path(salida)
    if not quitar and entrada.resolve() == salida.resolve():
        raise ErrorDeMarcadores(
            "la salida no puede ser la entrada al poner los valores reales: "
            "el export versionado se quedaria con ellos")
    texto = leer(entrada)
    try:
        json.loads(texto)
    except json.JSONDecodeError as e:
        raise ErrorDeMarcadores(f"{entrada} no es un JSON valido: {e}") from e
    if quitar:
        resultado = retirar(texto, valores)
        veces = {m: texto.count(v) for m, v in valores.items() if v in texto}
    else:
        resultado = aplicar(texto, valores)
        veces = {m: texto.count(m) for m in marcadores_de(texto)}
    json.loads(resultado)
    escribir(salida, resultado)
    return veces


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Pone (o, con --retirar, quita) los valores reales de un "
                    "workflow de n8n versionado con marcadores.")
    p.add_argument("--entrada", required=True, help="el JSON que se lee")
    p.add_argument("--salida", required=True, help="el JSON que se escribe")
    p.add_argument("--valores", default=str(VALORES_LOCALES),
                   help="JSON {marcador: valor real} "
                        "(por defecto n8n/valores.local.json)")
    p.add_argument("--retirar", action="store_true",
                   help="valor real -> marcador, para versionar un export")
    a = p.parse_args(argv)
    try:
        veces = convertir(a.entrada, a.salida, leer_valores(a.valores),
                          quitar=a.retirar)
    except ErrorDeMarcadores as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    verbo = "retirados" if a.retirar else "puestos"
    for marcador in MARCADORES:
        if marcador in veces:
            print(f"{marcador}: {veces[marcador]}")
    print(f"valores {verbo}: {sum(veces.values())} sustituciones -> {a.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Crea `n8n/valores.ejemplo.json`:

```json
{
  "https://n8n.ejemplo.test": "https://automatizacion.ejemplo.test",
  "CRED_TELEGRAM_PACIENTE": "id-de-ejemplo-telegram-paciente",
  "CRED_TELEGRAM_PROFESIONAL": "id-de-ejemplo-telegram-profesional",
  "CRED_TELEGRAM_AVISOS": "id-de-ejemplo-telegram-avisos",
  "CRED_POSTGRES_COPILOTO": "id-de-ejemplo-postgres",
  "CRED_SECRETO_PACIENTE": "id-de-ejemplo-secreto-paciente",
  "CRED_SECRETO_PROFESIONAL": "id-de-ejemplo-secreto-profesional",
  "bot-paciente": "BotDeEjemploPaciente",
  "bot-profesional": "BotDeEjemploProfesional",
  "bot-avisos": "BotDeEjemploAvisos"
}
```

Añade AL FINAL de `.gitignore`, tras una línea en blanco:

```gitignore
# Los valores reales de la instancia de n8n (spec de SP5 §6.1): la URL y los
# ids y nombres de las credenciales que `scripts/marcadores_n8n.py` pone en
# los workflows antes de desplegarlos. El de ejemplo, de al lado, si se versiona.
n8n/valores.local.json
```

Por qué la herramienta es más estricta de lo que pide el enunciado, para que nadie lo «simplifique»:
- `retirar` exige el valor de **todos** los marcadores: el que falte no se puede buscar, y el export
  saldría con él en claro sin que nada avisara.
- `aplicar` rechaza una entrada que ya lleva algún valor real: con ella la ida y vuelta dejaría de
  ser exacta (`retirar(aplicar(x)) == x`).
- Se rechaza un valor contenido en un marcador, o en otro valor: la sustitución es de una sola
  pasada y con eso no tiene ambigüedad.
- «Queda un valor real» se busca **sin distinguir mayúsculas** y, de la URL, **también el host a
  secas**: es lo que la sustitución exacta no ve. El error dice el marcador y la línea, nunca el valor.
- Al poner los valores, la salida no puede ser el fichero de entrada: el export versionado se
  quedaría con los valores reales a un `git add` de distancia.

- [ ] **Paso 4: Correr las pruebas y verlas pasar**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_marcadores_n8n.py`

Esperado: `29 passed`.

- [ ] **Paso 5: Commit**

```bash
git add scripts/marcadores_n8n.py n8n/valores.ejemplo.json tests/test_marcadores_n8n.py .gitignore
git commit -m "feat(anonimato): la herramienta que pone y quita los valores reales de los workflows (SP5-B2 T4)" -m "scripts/marcadores_n8n.py sustituye los marcadores por los valores de n8n/valores.local.json (ignorado por git) y al reves, sin reformatear y en LF. Falla si falta un marcador, si dos comparten valor o si tras retirar queda un valor real. n8n/valores.ejemplo.json lleva valores de ejemplo." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

#### Segunda parte: los tres workflows pasan a llevar marcadores

Los workflows y las aserciones que los vigilan cambian en el MISMO commit: por separado,
cualquiera de los dos deja la suite en rojo.

Antes de tocar nada, lo que afirman las pruebas que leen estos ficheros (comprobado):
- `test_los_dos_bots_siguen_sin_tocarse` (`tests/test_mantenimiento.py`) afirma solo el `name` del
  workflow y el número de nodos (24 y 25) de los exports de los dos bots. No mira notas ni
  credenciales: no hay que cambiarla, y el script del paso 8 exige esos mismos números.
- `tests/mantenimiento.mjs` ejecuta el `jsCode` de `Evaluar` y no lee la URL de las sondas: usa
  los NOMBRES de los nodos, que no cambian. `tests/decidir.mjs` y `tests/profesional.mjs` ejecutan
  el `jsCode` de los dos bots; el único `jsCode` que se toca es el de `Desenlace`, y solo en un
  comentario.
- `tests/test_sql_de_los_nodos.py` lee las consultas SQL de los nodos, que no se tocan.

- [ ] **Paso 6: Escribir las pruebas de los workflows y cambiar las aserciones que los vigilan**

(a) Añade AL FINAL de `tests/test_marcadores_n8n.py`, dejando dos líneas en blanco tras
`test_los_valores_de_ejemplo_son_validos_y_cubren_todos_los_marcadores`:

```python
# --------------------------------------------------------------------------
# Los tres workflows versionados
# --------------------------------------------------------------------------
FLUJOS = ("copiloto-paciente.json", "copiloto-profesional.json",
          "copiloto-mantenimiento.json")

# Por fichero y por tipo de credencial: (id, name, cuantos nodos la usan).
CREDENCIALES = {
    "copiloto-paciente.json": {
        "telegramApi": ("CRED_TELEGRAM_PACIENTE", "bot-paciente", 12),
        "postgres": ("CRED_POSTGRES_COPILOTO", "copiloto-bd", 5),
        "httpHeaderAuth": ("CRED_SECRETO_PACIENTE",
                           "copiloto-paciente: secret_token del webhook", 1),
    },
    "copiloto-profesional.json": {
        "telegramApi": ("CRED_TELEGRAM_PROFESIONAL", "bot-profesional", 9),
        "postgres": ("CRED_POSTGRES_COPILOTO", "copiloto-bd", 5),
        "httpHeaderAuth": ("CRED_SECRETO_PROFESIONAL",
                           "copiloto-profesional: secret_token del webhook", 1),
    },
    "copiloto-mantenimiento.json": {
        "telegramApi": ("CRED_TELEGRAM_AVISOS", "bot-avisos", 1),
        "postgres": ("CRED_POSTGRES_COPILOTO", "copiloto-bd", 4),
    },
}

# Lo que no es de la instancia y por eso se queda como esta: el copiloto se
# llama por el nombre de su servicio en la red de Docker.
URL_INTERNA = "http://copiloto-mcp:8000/"


def _nodos(fichero):
    return json.loads((N8N / fichero).read_text(encoding="utf-8"))["nodes"]


@pytest.mark.parametrize("fichero", FLUJOS)
def test_las_credenciales_de_los_workflows_son_marcadores(mn, fichero):
    vistas = {}
    for n in _nodos(fichero):
        for tipo, c in (n.get("credentials") or {}).items():
            assert set(c) == {"id", "name"}, (n["name"], c)
            vistas.setdefault(tipo, []).append((c["id"], c["name"]))
    esperadas = CREDENCIALES[fichero]
    assert set(vistas) == set(esperadas)
    for tipo, (ident, nombre, cuantos) in esperadas.items():
        assert vistas[tipo] == [(ident, nombre)] * cuantos, (fichero, tipo)
        assert ident in mn.MARCADORES


@pytest.mark.parametrize("fichero", FLUJOS)
def test_las_url_de_los_nodos_http_son_el_marcador_o_la_interna(mn, fichero):
    for n in _nodos(fichero):
        if n["type"] != "n8n-nodes-base.httpRequest":
            continue
        url = n["parameters"]["url"]
        assert (url.startswith(mn.URL_N8N + "/webhook/")
                or url.startswith(URL_INTERNA)), (fichero, n["name"], url)


def test_las_dos_sondas_apuntan_al_marcador(mn):
    sondas = {n["name"]: n["parameters"]["url"]
              for n in _nodos("copiloto-mantenimiento.json")
              if n["type"] == "n8n-nodes-base.httpRequest"
              and "/webhook/" in n["parameters"]["url"]}
    assert sondas == {
        "Webhook del paciente": "https://n8n.ejemplo.test/webhook/copiloto-paciente",
        "Webhook del profesional": "https://n8n.ejemplo.test/webhook/copiloto-profesional",
    }


@pytest.mark.parametrize("fichero, ruta, token", [
    ("copiloto-paciente.json", "copiloto-paciente", "<TOKEN>"),
    ("copiloto-profesional.json", "copiloto-profesional",
     "<TOKEN_DEL_BOT_DEL_PROFESIONAL>"),
])
def test_la_nota_del_webhook_registra_con_el_marcador(fichero, ruta, token):
    (nota,) = [n["notes"] for n in _nodos(fichero)
               if n["type"] == "n8n-nodes-base.webhook"]
    assert (f'"https://api.telegram.org/bot{token}/setWebhook" '
            f"-d url=https://n8n.ejemplo.test/webhook/{ruta} ") in nota


def test_cada_marcador_aparece_en_algun_workflow_y_al_reves(mn):
    import re
    ejemplo = mn.leer_valores(EJEMPLO)
    presentes, con_forma_de_marcador = set(), set()
    for fichero in FLUJOS:
        texto = mn.leer(N8N / fichero)
        presentes |= mn.marcadores_de(texto)
        con_forma_de_marcador |= set(re.findall(r"\bCRED_[A-Z0-9_]+", texto))
        con_forma_de_marcador |= set(
            re.findall(r"https?://[A-Za-z0-9.-]*ejemplo\.test", texto))
        con_forma_de_marcador |= set(re.findall(r"\bbot-[a-z]+", texto))
    assert presentes == set(mn.MARCADORES) == set(ejemplo)
    assert con_forma_de_marcador == set(mn.MARCADORES)


@pytest.mark.parametrize("fichero", FLUJOS)
def test_ida_y_vuelta_con_los_valores_de_ejemplo(mn, fichero):
    ejemplo = mn.leer_valores(EJEMPLO)
    texto = mn.leer(N8N / fichero)
    puesto = mn.aplicar(texto, ejemplo)
    assert puesto != texto
    assert mn.marcadores_de(puesto) == set()
    assert len(json.loads(puesto)["nodes"]) == len(json.loads(texto)["nodes"])
    assert mn.retirar(puesto, ejemplo) == texto


@pytest.mark.parametrize("fichero", FLUJOS)
def test_la_cli_da_la_vuelta_a_un_workflow_entero(mn, fichero, tmp_path):
    valores = ["--valores", str(EJEMPLO)]
    assert mn.main(valores + ["--entrada", str(N8N / fichero),
                              "--salida", str(tmp_path / "puesto.json")]) == 0
    assert mn.main(valores + ["--retirar",
                              "--entrada", str(tmp_path / "puesto.json"),
                              "--salida", str(tmp_path / "vuelta.json")]) == 0
    assert (tmp_path / "vuelta.json").read_text(encoding="utf-8") \
        == mn.leer(N8N / fichero)
```

(b) En `tests/test_mantenimiento.py`, tres cambios.

El docstring del módulo gana un párrafo al final. Busca exactamente:

```python
  ahi se comprueba el TEXTO del aviso y la regla de cuando se calla, que es lo
  que de verdad se entrega.
"""
```

y sustitúyelo por:

```python
  ahi se comprueba el TEXTO del aviso y la regla de cuando se calla, que es lo
  que de verdad se entrega.

El export versionado lleva MARCADORES en vez de los valores de la instancia
-la URL de n8n y los ids y nombres de las credenciales (spec de SP5 §6.1)-,
asi que ya no es identico byte a byte al desplegado: entre uno y otro media
`scripts/marcadores_n8n.py`, que se prueba en `test_marcadores_n8n.py`.
"""
```

Las líneas 36-39 (el comentario de dos líneas que empieza por `# Los ids de §12.` y las dos
constantes `CRED_BD = "…"` y `CRED_AVISOS = "…"`, cada una con un id de 16 caracteres) se
sustituyen, las cuatro, por:

```python
# Los marcadores de las credenciales (spec de SP5 §6.1), y no sus ids en la
# instancia. Escritos a mano aqui para que sean un testigo independiente: si
# alguien versiona un export con los ids reales o con otra credencial, se ve.
CRED_BD = "CRED_POSTGRES_COPILOTO"
CRED_AVISOS = "CRED_TELEGRAM_AVISOS"
```

La línea 181, dentro de `test_las_sondas_de_webhook_no_llevan_el_secreto_ni_disparan_los_bots`
(`assert p["url"] == f"https://…/webhook/{ruta}"`, con el dominio real), pasa a ser:

```python
        assert p["url"] == f"https://n8n.ejemplo.test/webhook/{ruta}"
```

La línea 228 (`assert usadas == {"postgres": {CRED_BD}, "telegramApi": {CRED_AVISOS}}, usadas`)
NO se toca: usa las constantes, y con ellas pasa a afirmar los marcadores.

(c) En `tests/test_flujo_paciente.py`, la línea 457, última de
`test_solo_se_usa_la_credencial_del_bot_del_paciente` (`assert usadas == {"…"}, usadas    # …`, con
un id de 16 caracteres y el nombre del bot en el comentario), pasa a ser:

```python
    assert usadas == {"CRED_TELEGRAM_PACIENTE"}, usadas    # el marcador (SP5 §6.1)
```

(d) En `tests/test_flujo_profesional.py`, cinco líneas.

En el docstring de `_subir_dicom`, el párrafo de las líneas 161-166 (empieza por `Con el bot del
profesional y no con` y nombra dos bots entre acentos graves, en las líneas 161 y 164) queda así:

```python
    Con el bot del profesional y no con el de pruebas y avisos, aunque el brief diga
    otra cosa: en Telegram un `file_id` solo lo puede resolver **el bot que lo
    obtuvo**. Un `file_id` conseguido subiendo el fichero al bot de pruebas haria
    que el `getFile` del flujo -que usa la credencial `bot-profesional`-
    respondiera `wrong file identifier`, y la prueba estaria midiendo eso y no el
    flujo.
```

En `test_solo_se_usa_la_credencial_del_bot_del_profesional`, la línea 481 (la última del docstring,
que nombra entre acentos graves la credencial del cliente) y la línea 486 (la aserción, con un id
de 16 caracteres y el nombre del bot en el comentario). La función empieza así:

```python
def test_solo_se_usa_la_credencial_del_bot_del_profesional():
    """D9 y la regla dura 2: reutilizar una credencial de Telegram del cliente le
    robaria el webhook a un bot suyo y lo dejaria mudo sin error visible.
    La credencial de Telegram del cliente la usan cinco workflows suyos."""
    usadas = {c["id"]
              for n in _flujo()["nodes"]
              for t, c in (n.get("credentials") or {}).items()
              if t == "telegramApi"}
    assert usadas == {"CRED_TELEGRAM_PROFESIONAL"}, usadas   # el marcador (SP5 §6.1)
```

Y la línea 790, en un docstring (empieza por `rotulaba «` y lleva el nombre del bot entre
comillas angulares), pasa a ser:

```python
    rotulaba «<bot del profesional>»; el camino realista al daño es que el clínico reenvíe
```

- [ ] **Paso 7: Correr las pruebas y verlas fallar**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_marcadores_n8n.py tests/test_mantenimiento.py tests/test_flujo_paciente.py tests/test_flujo_profesional.py`

Esperado: `15 failed, 104 passed, 20 skipped`. Los quince:
- once de `tests/test_marcadores_n8n.py`: `test_las_credenciales_de_los_workflows_son_marcadores` (los tres
  ficheros), `test_las_url_de_los_nodos_http_son_el_marcador_o_la_interna[copiloto-mantenimiento.json]`,
  `test_las_dos_sondas_apuntan_al_marcador`, `test_la_nota_del_webhook_registra_con_el_marcador` (los dos),
  `test_cada_marcador_aparece_en_algun_workflow_y_al_reves` y `test_ida_y_vuelta_con_los_valores_de_ejemplo`
  (los tres: sin marcadores, `aplicar` devuelve el texto igual);
- dos de `tests/test_mantenimiento.py`: `test_las_sondas_de_webhook_no_llevan_el_secreto_ni_disparan_los_bots`
  y `test_las_credenciales_son_las_de_sp3`;
- `test_solo_se_usa_la_credencial_del_bot_del_paciente` y `test_solo_se_usa_la_credencial_del_bot_del_profesional`.

- [ ] **Paso 8: Poner los marcadores en los tres workflows con un script desechable**

Crea este script en una carpeta temporal FUERA del repositorio (por ejemplo
`<carpeta-temporal>/poner_marcadores.py`), con la herramienta de escritura de ficheros y no con
un heredoc del shell. No se versiona.

```python
# -*- coding: utf-8 -*-
"""DESECHABLE: pone los marcadores en los tres workflows de n8n/ (SP5-B2, tarea 4).

Se corre UNA vez, desde la raiz del repositorio, y se borra. No lleva ninguna
cadena de las que quita: las localiza por estructura en el propio JSON (el
campo `url` de las dos sondas, los bloques `credentials` por tipo, lo que sigue
a `-d url=` en las notas) y exige el numero de sustituciones esperado. Si algo
no cuadra, sale sin escribir NINGUN fichero.
"""
import io
import json
import pathlib
import re
import sys

URL = "https://n8n.ejemplo.test"
HTTP = "n8n-nodes-base.httpRequest"

# Por fichero: tipo de credencial -> (id nuevo, name nuevo o None si se
# conserva, cuantos nodos la llevan); sondas; y las menciones del nombre viejo
# de la credencial de Telegram fuera de los bloques `credentials`:
# (lo que va delante, lo que va detras, el texto entero que queda).
PLAN = {
    "copiloto-mantenimiento.json": {
        "lineas": 481, "nodos": 12, "sondas": 2, "nota_url": 0,
        "credenciales": {
            "postgres": ("CRED_POSTGRES_COPILOTO", None, 4),
            "telegramApi": ("CRED_TELEGRAM_AVISOS", "bot-avisos", 1),
        },
        "menciones": [("Con la credencial de `", "`",
                       "Con la credencial de `bot-avisos`")],
    },
    "copiloto-paciente.json": {
        "lineas": 1409, "nodos": 24, "sondas": 0, "nota_url": 1,
        "credenciales": {
            "httpHeaderAuth": ("CRED_SECRETO_PACIENTE", None, 1),
            "postgres": ("CRED_POSTGRES_COPILOTO", None, 5),
            "telegramApi": ("CRED_TELEGRAM_PACIENTE", "bot-paciente", 12),
        },
        "menciones": [],
    },
    "copiloto-profesional.json": {
        "lineas": 1207, "nodos": 25, "sondas": 0, "nota_url": 1,
        "credenciales": {
            "httpHeaderAuth": ("CRED_SECRETO_PROFESIONAL", None, 1),
            "postgres": ("CRED_POSTGRES_COPILOTO", None, 5),
            "telegramApi": ("CRED_TELEGRAM_PROFESIONAL", "bot-profesional", 9),
        },
        "menciones": [
            ("<TOKEN_DE_", ">", "<TOKEN_DEL_BOT_DEL_PROFESIONAL>"),
            ("rotulandola «", "»", "rotulandola «<bot del profesional>»"),
        ],
    },
}


def sustituir(texto, viejo, nuevo, veces, que):
    hay = texto.count(viejo)
    if hay != veces:
        sys.exit(f"ABORTO: {que}: se esperaban {veces} apariciones y hay {hay}")
    return texto.replace(viejo, nuevo)


def en_json(cadena):
    """La cadena tal como esta escrita DENTRO del fichero (con sus escapes)."""
    return json.dumps(cadena, ensure_ascii=False)[1:-1]


def convertir(nombre, texto, plan):
    flujo = json.loads(texto)
    nodos = flujo["nodes"]
    if len(nodos) != plan["nodos"] or texto.count("\n") != plan["lineas"]:
        sys.exit(f"ABORTO: {nombre} no tiene los nodos o las lineas esperadas")
    hechas = []
    viejos = []          # lo que no puede quedar en el fichero al terminar

    # 1. Las sondas: los nodos httpRequest cuya url lleva /webhook/.
    sondas = [n["parameters"]["url"] for n in nodos
              if n["type"] == HTTP and "/webhook/" in n["parameters"]["url"]]
    if len(sondas) != plan["sondas"]:
        sys.exit(f"ABORTO: {nombre}: {len(sondas)} sondas")
    for url in sondas:
        base, ruta = url.split("/webhook/", 1)
        viejos.append(base.split("://", 1)[1])
        texto = sustituir(texto, f'"url": "{en_json(url)}"',
                          f'"url": "{URL}/webhook/{ruta}"', 1,
                          f"la url de la sonda de {ruta}")
        hechas.append(f"url de la sonda de {ruta}: 1")

    # 2. La nota del nodo webhook: lo que sigue a «-d url=» hasta /webhook/.
    notas = [n["notes"] for n in nodos
             if n["type"] == "n8n-nodes-base.webhook" and "-d url=" in n.get("notes", "")]
    if len(notas) != plan["nota_url"]:
        sys.exit(f"ABORTO: {nombre}: {len(notas)} notas con -d url=")
    for nota in notas:
        bases = re.findall(r"-d url=(\S+?)/webhook/", nota)
        if len(bases) != 1:
            sys.exit(f"ABORTO: {nombre}: la nota tiene {len(bases)} -d url=")
        viejos.append(bases[0].split("://", 1)[1])
        texto = sustituir(texto, f"-d url={en_json(bases[0])}/webhook/",
                          f"-d url={URL}/webhook/", 1, "la url de la nota")
        hechas.append("url de la nota del webhook: 1")

    # 3. Las credenciales, por tipo: el bloque de dos lineas «id» y «name».
    vistas = {}
    for n in nodos:
        for tipo, c in (n.get("credentials") or {}).items():
            if set(c) != {"id", "name"}:
                sys.exit(f"ABORTO: {nombre}: credencial rara en {n['name']}")
            vistas.setdefault(tipo, set()).add((c["id"], c["name"]))
    if set(vistas) != set(plan["credenciales"]):
        sys.exit(f"ABORTO: {nombre}: tipos de credencial {sorted(vistas)}")
    nombre_telegram = None
    for tipo, (ident, nuevo_nombre, veces) in sorted(plan["credenciales"].items()):
        if len(vistas[tipo]) != 1:
            sys.exit(f"ABORTO: {nombre}: mas de una credencial de tipo {tipo}")
        (id_viejo, nombre_viejo), = vistas[tipo]
        viejos.append(id_viejo)
        if nuevo_nombre is not None:
            viejos.append(nombre_viejo)
        if tipo == "telegramApi":
            nombre_telegram = nombre_viejo
        patron = re.compile(
            r'("' + tipo + r'": \{\n\s+"id": ")' + re.escape(en_json(id_viejo))
            + r'(",\n\s+"name": ")' + re.escape(en_json(nombre_viejo)) + r'"')
        nuevo = en_json(nuevo_nombre if nuevo_nombre is not None else nombre_viejo)
        texto, hay = patron.subn(
            lambda m: m.group(1) + ident + m.group(2) + nuevo + '"', texto)
        if hay != veces:
            sys.exit(f"ABORTO: {nombre}: credencial {tipo}: se esperaban "
                     f"{veces} bloques y hay {hay}")
        hechas.append(f"credencial {tipo} -> {ident}: {veces}")

    # 4. El nombre viejo de la credencial de Telegram en notas y comentarios.
    for delante, detras, nuevo in plan["menciones"]:
        viejo = en_json(delante + nombre_telegram + detras)
        texto = sustituir(texto, viejo, en_json(nuevo), 1,
                          f"la mencion tras {delante!a}")
        hechas.append(f"mencion tras {delante!a}: 1")

    # 5. No queda nada de lo viejo, y el fichero sigue siendo el mismo JSON.
    for viejo in viejos:
        if viejo.lower() in texto.lower():
            sys.exit(f"ABORTO: {nombre}: queda una cadena vieja sin sustituir "
                     f"({len(viejo)} caracteres; no se imprime)")
    despues = json.loads(texto)
    if (len(despues["nodes"]) != plan["nodos"]
            or texto.count("\n") != plan["lineas"]
            or [n["name"] for n in despues["nodes"]] != [n["name"] for n in nodos]
            or despues["connections"] != flujo["connections"]):
        sys.exit(f"ABORTO: {nombre}: el JSON ha cambiado de forma")
    return texto, hechas


def main():
    carpeta = pathlib.Path("n8n")
    if not carpeta.is_dir():
        sys.exit("ABORTO: correlo desde la raiz del repositorio")
    resultados = {}
    for nombre, plan in PLAN.items():
        with io.open(carpeta / nombre, encoding="utf-8", newline="") as f:
            crudo = f.read()
        texto, hechas = convertir(nombre, crudo.replace("\r\n", "\n"), plan)
        resultados[nombre] = (texto, hechas)
    for nombre, (texto, hechas) in resultados.items():
        with io.open(carpeta / nombre, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        print(nombre)
        for linea in hechas:
            print("   " + linea)
    print("HECHO: 3 ficheros escritos en LF")


if __name__ == "__main__":
    main()
```

Qué sustituye, por fichero (y el script aborta sin escribir nada si alguna cuenta no sale):

| Fichero | Qué | Veces | Líneas que cambian |
| :--- | :--- | :--- | :--- |
| `copiloto-mantenimiento.json` | `parameters.url` de las dos sondas (líneas 207 y 243): la base pasa a `https://n8n.ejemplo.test` | 2 | 9 |
| | credencial `postgres`: `id` → `CRED_POSTGRES_COPILOTO` (el `name`, `copiloto-bd`, se conserva) | 4 | |
| | credencial `telegramApi` (líneas 338-339): `id` → `CRED_TELEGRAM_AVISOS`, `name` → `bot-avisos` | 1 | |
| | la nota de `Avisar al equipo` (línea 346): el nombre de la credencial entre acentos graves → `bot-avisos` | 1 | |
| `copiloto-paciente.json` | credencial `httpHeaderAuth` (línea 23): `id` → `CRED_SECRETO_PACIENTE` | 1 | 31 |
| | la nota del webhook (línea 27): lo que sigue a `-d url=` → `https://n8n.ejemplo.test` | 1 | |
| | credencial `postgres`: `id` → `CRED_POSTGRES_COPILOTO` | 5 | |
| | credencial `telegramApi`: `id` → `CRED_TELEGRAM_PACIENTE`, `name` → `bot-paciente` | 12 | |
| `copiloto-profesional.json` | credencial `httpHeaderAuth` (línea 23): `id` → `CRED_SECRETO_PROFESIONAL` | 1 | 26 |
| | la nota del webhook (línea 27): lo que sigue a `-d url=` → `https://n8n.ejemplo.test`, y `<TOKEN_DE_…>` → `<TOKEN_DEL_BOT_DEL_PROFESIONAL>` (la misma línea) | 1 + 1 | |
| | credencial `postgres`: `id` → `CRED_POSTGRES_COPILOTO` | 5 | |
| | credencial `telegramApi`: `id` → `CRED_TELEGRAM_PROFESIONAL`, `name` → `bot-profesional` | 9 | |
| | el comentario del `jsCode` de `Desenlace` (línea 793): el nombre del bot entre comillas angulares → `<bot del profesional>` | 1 | |

Córrelo desde la raíz del repositorio:

Run: `C:/venv-copiloto/Scripts/python.exe -B <carpeta-temporal>/poner_marcadores.py`

Esperado, literal:

```text
copiloto-mantenimiento.json
   url de la sonda de copiloto-paciente: 1
   url de la sonda de copiloto-profesional: 1
   credencial postgres -> CRED_POSTGRES_COPILOTO: 4
   credencial telegramApi -> CRED_TELEGRAM_AVISOS: 1
   mencion tras 'Con la credencial de `': 1
copiloto-paciente.json
   url de la nota del webhook: 1
   credencial httpHeaderAuth -> CRED_SECRETO_PACIENTE: 1
   credencial postgres -> CRED_POSTGRES_COPILOTO: 5
   credencial telegramApi -> CRED_TELEGRAM_PACIENTE: 12
copiloto-profesional.json
   url de la nota del webhook: 1
   credencial httpHeaderAuth -> CRED_SECRETO_PROFESIONAL: 1
   credencial postgres -> CRED_POSTGRES_COPILOTO: 5
   credencial telegramApi -> CRED_TELEGRAM_PROFESIONAL: 9
   mencion tras '<TOKEN_DE_': 1
   mencion tras 'rotulandola \xab': 1
HECHO: 3 ficheros escritos en LF
```

Y bórralo: `rm <carpeta-temporal>/poner_marcadores.py`. Si se corre por segunda vez aborta
(`ABORTO: copiloto-mantenimiento.json: queda una cadena vieja sin sustituir (16 caracteres; no se imprime)`)
sin escribir nada: ya no hay valores que localizar.

- [ ] **Paso 9: Comprobar que solo cambió lo esperado, y ver las pruebas pasar**

Run: `git diff --stat -- n8n/`

Esperado (más tres avisos `warning: in the working copy of 'n8n/…', LF will be replaced by CRLF the
next time Git touches it`, que no son un error):

```text
 n8n/copiloto-mantenimiento.json | 18 ++++++------
 n8n/copiloto-paciente.json      | 62 ++++++++++++++++++++---------------------
 n8n/copiloto-profesional.json   | 52 +++++++++++++++++-----------------
 3 files changed, 66 insertions(+), 66 deletions(-)
```

Si `git diff --stat` enseña miles de líneas, el fichero se reformateó o cambió de finales de línea
en el índice: deshaz con `git checkout -- n8n/` y revisa el script antes de repetir.

Run: `git diff -- n8n/ 2>/dev/null | grep "^+" | grep -v "^+++" | cut -c1-60 | sort | uniq -c | sort -rn`

Esperado (las 66 líneas añadidas, agrupadas por sus primeros 60 caracteres; el orden entre
filas con la misma cuenta puede variar), y ninguna fila más:

```text
     14 +          "id": "CRED_POSTGRES_COPILOTO",
     12 +          "name": "bot-paciente"
     12 +          "id": "CRED_TELEGRAM_PACIENTE",
      9 +          "name": "bot-profesional"
      9 +          "id": "CRED_TELEGRAM_PROFESIONAL",
      2 +      "notes": "El secret_token del §4.2, y por que NO es 
      2 +        "url": "https://n8n.ejemplo.test/webhook/copiloto-p
      1 +      "notes": "Con la credencial de `bot-avisos`, que exis
      1 +        "jsCode": "// EL UNICO SITIO DONDE SE REDACTA UN DE
      1 +          "name": "bot-avisos"
      1 +          "id": "CRED_TELEGRAM_AVISOS",
      1 +          "id": "CRED_SECRETO_PROFESIONAL",
      1 +          "id": "CRED_SECRETO_PACIENTE",
```

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_marcadores_n8n.py tests/test_mantenimiento.py tests/test_flujo_paciente.py tests/test_flujo_profesional.py tests/test_sql_de_los_nodos.py`

Esperado: `121 passed, 20 skipped` (45 de ellas son las de `tests/test_marcadores_n8n.py`).

- [ ] **Paso 10: Commit**

```bash
git add n8n/copiloto-mantenimiento.json n8n/copiloto-paciente.json n8n/copiloto-profesional.json tests/test_marcadores_n8n.py tests/test_mantenimiento.py tests/test_flujo_paciente.py tests/test_flujo_profesional.py
git commit -m "fix(anonimato): los tres workflows llevan marcadores en vez de los valores de la instancia (SP5-B2 T4)" -m "La URL de las dos sondas, los id de las credenciales, los nombres de las de Telegram y las menciones en notas y en un comentario pasan a marcadores (spec de SP5 6.1). Los exports dejan de ser identicos byte a byte a lo desplegado: scripts/marcadores_n8n.py pone y quita los valores. Las pruebas afirman los marcadores." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

#### Tercera parte: las entradas de las pruebas `.mjs`

Ninguno de los tres valores importa a la lógica que se prueba (cualquier `/start@X` vale, y la IP
es parte de un mensaje de error fabricado), así que aquí no hay prueba que falle primero: se
cambia la entrada y se comprueba que todo sigue verde.

- [ ] **Paso 11: Cambiar las tres entradas y el comentario**

En `tests/decidir.mjs`, la línea 90 (la comprobación `"/start@Bot tambien"`, cuya entrada es
`/start@` seguido del nombre de un bot) pasa a ser:

```javascript
ok("/start@Bot tambien", decidir(normalizar(msg("/start@BotDeEjemplo")), sinSesion).accion === "consentimiento");
```

En `tests/profesional.mjs`, la línea 365 (dentro de la comprobación `"/START y /start@Bot tambien"`,
la que asigna `const b`) pasa a ser:

```javascript
  const b = await decidir(await normalizar(msg("/start@BotDeEjemplo")), sinSesion);
```

y la línea 1617 (un comentario que empieza por `// busqueda- la atribucion era CERO` y acaba con
el nombre de un bot entre comillas angulares) pasa a ser:

```javascript
// busqueda- la atribucion era CERO y la interfaz la rotulaba «<bot del profesional>».
```

En `tests/mantenimiento.mjs`, la línea 146 (el error fabricado de `"Salud del copiloto"`, con una
IP privada que acaba en `.9`) pasa a ser:

```javascript
    "Salud del copiloto": { error: "connect ECONNREFUSED 172.18.0.2:8000" },
```

- [ ] **Paso 12: Correr los cuatro `.mjs` y las pruebas que los lanzan**

Run: `node tests/decidir.mjs && node tests/formulario.mjs && node tests/mantenimiento.mjs && node tests/profesional.mjs`

Esperado: código de salida 0. La última línea de `decidir.mjs`, `mantenimiento.mjs` y
`profesional.mjs` es `TODO VERDE`; la de `formulario.mjs` es `16 OK`.

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_marcadores_n8n.py tests/test_mantenimiento.py tests/test_flujo_paciente.py tests/test_flujo_profesional.py tests/test_sql_de_los_nodos.py`

Esperado: `121 passed, 20 skipped`.

- [ ] **Paso 13: Commit**

```bash
git add tests/decidir.mjs tests/profesional.mjs tests/mantenimiento.mjs
git commit -m "test(anonimato): las entradas de las pruebas .mjs no nombran bots ni la red real (SP5-B2 T4)" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

#### Cuarta parte: el manual de operación

- [ ] **Paso 14: El registro del webhook pregunta la URL (§4 de `docs/sp3-operacion.md`)**

La línea 351 (`**3. Registrarlo.** No hay nada que sustituir: pregunta las dos cosas.`) y el
bloque `powershell` de las líneas 353-355 (una sola orden, que lleva la URL real escrita dentro de
`-Body @{url='…'; secret_token=$s}`) se sustituyen por:

````markdown
**3. Registrarlo.** No hay nada que sustituir: pregunta las tres cosas. La URL
base es la pública de la instancia de n8n (la misma que va en
`n8n/valores.local.json`, §7); en el repositorio solo figura su marcador,
`https://n8n.ejemplo.test`.

```powershell
$u = (Read-Host 'URL base de n8n, con https://').TrimEnd('/'); $t = Read-Host 'token del bot'; $s = Read-Host 'secret_token'; Invoke-RestMethod -Uri "https://api.telegram.org/bot$t/setWebhook" -Method Post -Body @{url="$u/webhook/copiloto-paciente"; secret_token=$s}
```
````

El párrafo siguiente («La ruta es `copiloto-paciente` o `copiloto-profesional` según el bot…») no
se toca.

- [ ] **Paso 15: La subsección de los marcadores (§7 de `docs/sp3-operacion.md`)**

Al final del §7 «Credenciales y workflows», busca exactamente:

```markdown
Los tres workflows llevan el prefijo `🩺 Copiloto Triaje:`. Cualquier otro de
esa instancia es del cliente y **no se modifica**.
```

y añade DESPUÉS, dejando una línea en blanco antes y otra después (antes del `---` que cierra
la sección):

````markdown
### Los marcadores: del repositorio a n8n, y de n8n al repositorio

Los tres exports de `n8n/` se versionan con **marcadores** en lugar de los
valores de la instancia donde corren. Por eso **un export del repositorio ya
no es idéntico byte a byte al workflow desplegado**: se diferencian en estas
cadenas, y solo en ellas.

| Marcador | Qué es en la instancia |
| :--- | :--- |
| `https://n8n.ejemplo.test` | la URL base pública de n8n, con esquema y sin barra final (las dos sondas del mantenimiento y las notas de los webhooks) |
| `CRED_TELEGRAM_PACIENTE`, `bot-paciente` | el `id` y el nombre de la credencial de Telegram del bot del paciente |
| `CRED_TELEGRAM_PROFESIONAL`, `bot-profesional` | los de la credencial del bot del profesional |
| `CRED_TELEGRAM_AVISOS`, `bot-avisos` | los de la credencial del bot de pruebas y avisos |
| `CRED_POSTGRES_COPILOTO` | el `id` de la credencial `copiloto-bd` |
| `CRED_SECRETO_PACIENTE`, `CRED_SECRETO_PROFESIONAL` | los `id` de las dos credenciales de cabecera con el `secret_token` |

El `id` de una credencial se lee en n8n en la URL de la propia credencial al
abrirla, o en un export del workflow que ya la usa. **Ninguno es un secreto**
—el token y la contraseña viven dentro de la credencial y no salen en ningún
export—, pero identifican la instancia, y por eso no se versionan.

**Una sola vez por máquina:** copiar `n8n/valores.ejemplo.json` a
`n8n/valores.local.json` y cambiar cada valor de ejemplo por el real. Ese
fichero está en `.gitignore`: no se versiona ni se comparte.

**Poner los valores reales, ANTES de importar o desplegar un workflow desde el
repositorio.** La salida va a una carpeta temporal fuera del repositorio, y es
ese fichero —no el de `n8n/`— el que se importa:

```powershell
C:\venv-copiloto\Scripts\python.exe scripts/marcadores_n8n.py --entrada n8n/copiloto-mantenimiento.json --salida $env:TEMP\n8n-real\copiloto-mantenimiento.json
```

Si se importa el export tal como está en el repositorio, con los marcadores,
el workflow no funciona: sus nodos apuntan a credenciales que no existen en la
instancia, y las dos sondas del mantenimiento preguntan a un dominio que no
existe.

**Quitar los valores reales, ANTES de versionar un export.** El workflow se
descarga de n8n a la carpeta temporal y se deja en `n8n/` ya con marcadores:

```powershell
C:\venv-copiloto\Scripts\python.exe scripts/marcadores_n8n.py --retirar --entrada $env:TEMP\n8n-real\export.json --salida n8n/copiloto-mantenimiento.json
```

Después, `git diff n8n/` tiene que enseñar solo lo que se cambió a propósito
en el workflow, y `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_marcadores_n8n.py`
tiene que pasar. Al terminar se borra la carpeta temporal.

El script se niega —sin escribir nada— si en `valores.local.json` falta un
marcador, si dos marcadores comparten valor, si al poner los valores la salida
es el propio fichero de entrada, o si tras retirar queda algún valor real
escrito de otra forma (en mayúsculas, o el dominio sin el `https://`); en ese
último caso dice la línea, y se corrige a mano.
````

- [ ] **Paso 16: Comprobar el manual**

Run: `git diff --stat -- docs/sp3-operacion.md`

Esperado: `1 file changed, 60 insertions(+), 2 deletions(-)`.

Run: `grep -c "n8n.ejemplo.test" docs/sp3-operacion.md`

Esperado: `2` (el paso 3 del §4 y la tabla del §7).

Run: `grep -n "webhook/copiloto" docs/sp3-operacion.md`

Esperado: una sola línea, la de la orden de `Invoke-RestMethod`, con
`url="$u/webhook/copiloto-paciente"` y sin ningún dominio escrito.

- [ ] **Paso 17: Commit**

```bash
git add docs/sp3-operacion.md
git commit -m "docs(anonimato): poner los valores reales antes de desplegar y quitarlos antes de versionar (SP5-B2 T4)" -m "El manual de operacion gana la subseccion de los marcadores en el 7, y el registro del webhook del 4 pregunta la URL base en vez de llevarla escrita." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

#### Cierre

- [ ] **Paso 18: La verificación final de la tarea**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_marcadores_n8n.py tests/test_mantenimiento.py tests/test_flujo_paciente.py tests/test_flujo_profesional.py tests/test_sql_de_los_nodos.py`

Esperado: `121 passed, 20 skipped`. Antes de la tarea, esos mismos ficheros (sin el nuevo) daban
`76 passed, 20 skipped`: las 45 de diferencia son las de `tests/test_marcadores_n8n.py`, y no hay
ninguna prueba que pasara y haya dejado de pasar.

Run: `node tests/decidir.mjs && node tests/formulario.mjs && node tests/mantenimiento.mjs && node tests/profesional.mjs`

Esperado: código de salida 0.

Run: `C:/venv-copiloto/Scripts/python.exe -B scripts/marcadores_n8n.py --valores n8n/valores.ejemplo.json --entrada n8n/copiloto-mantenimiento.json --salida <carpeta-temporal>/copiloto-mantenimiento.json`

Esperado, y después se borra el fichero de salida:

```text
https://n8n.ejemplo.test: 2
CRED_TELEGRAM_AVISOS: 1
CRED_POSTGRES_COPILOTO: 4
bot-avisos: 2
valores puestos: 9 sustituciones -> <carpeta-temporal>/copiloto-mantenimiento.json
```

Run: `git status --short`

Esperado: nada de esta tarea sin confirmar, y ningún `n8n/valores.local.json` en la lista aunque
exista (está ignorado).

- [ ] **Paso 19: Lo que queda para el usuario (no lo hace quien ejecuta el plan)**

Nada de esto toca la suite; es operación, y se le dice al usuario al entregar la tarea:

1. **Crear `n8n/valores.local.json`** en la máquina de desarrollo, copiando
   `n8n/valores.ejemplo.json` y poniendo la URL base, los seis `id` y los tres nombres reales. Los
   valores están en los exports anteriores a esta tarea (`git show 1f328da:n8n/copiloto-paciente.json`
   y los otros dos) y en la propia instancia. El fichero no sale de esa máquina.
2. **Los workflows desplegados no cambian con esta tarea.** Siguen corriendo con sus valores; lo
   que cambia es que el repositorio ya no sirve para importar tal cual: desde ahora, antes de
   importar o desplegar se ponen los valores (§7 del manual de operación).
3. **Las notas desplegadas siguen nombrando el bot y el dominio** hasta la próxima vez que se
   despliegue desde el repositorio. Si antes de eso se exporta un workflow de n8n y se le quitan
   los valores con `--retirar`, el resultado queda limpio, pero su texto no coincide con el
   versionado en dos sitios del workflow del profesional (el marcador del token en la nota del
   webhook y el comentario de `Desenlace`, donde quedará `bot-profesional`): `git diff` lo enseña
   y se corrige a mano, o se despliega antes desde el repositorio.
4. **No hace falta renombrar ninguna credencial en n8n.** `bot-paciente`, `bot-profesional` y
   `bot-avisos` son marcadores del nombre: el nombre real de cada credencial va en
   `valores.local.json` y la herramienta lo pone junto con su `id`.
5. **Esta sección se verificó sin Docker, sin red y sin n8n.** La importación en n8n de un export
   con los valores puestos no se ha probado: la primera vez conviene hacerla con el workflow de
   mantenimiento, que no atiende a nadie, y comprobar en la interfaz que sus nodos encuentran las
   credenciales antes de hacerlo con los dos bots.
---

### Tarea 5: `verificar_anonimato.py`, las huellas y las pruebas del mecanismo

Spec de SP5 §6.1. El repositorio lleva una prueba que corre siempre y que
falla si en algún fichero versionado aparece un token de la lista negra, y un
script que hace lo mismo desde la línea de órdenes, más los secretos y el
commit, antes de publicar. La lista negra en claro NO vive en el repositorio:
el repositorio lleva solo `tests/anonimato/huellas.txt`, con el sha256 de cada
token.

Esta tarea deja el script, las huellas y todas las pruebas que NO miran el
árbol de verdad: la suite queda verde. La prueba que exige el árbol limpio,
`test_el_arbol_esta_limpio`, entra al final de la tarea 6, cuando ya no
queda nada que quitar; antes fallaría, y tiene que fallar.

**Ficheros:**
- Crear: `scripts/verificar_anonimato.py`
- Crear: `tests/test_anonimato.py`
- Crear: `tests/anonimato/huellas.txt` (generado; 29 huellas)
- Modificar: `.gitignore` (un bloque nuevo al final)

**Interfaces:**
- Consume: nada de `src/`. Solo la biblioteca estándar y `git` en el PATH. La
  lista en claro, fuera del repositorio (`ANONIMATO_LISTA`), solo para
  regenerar las huellas.
- Produce, en `scripts/verificar_anonimato.py`:
  - constantes `CENTINELA = "centinelaanonimato7f3a"`, `HUELLAS_POR_DEFECTO`
    (`tests/anonimato/huellas.txt` del repositorio donde vive el script),
    `VARIABLE_DE_LA_LISTA = "ANONIMATO_LISTA"`, `PATRONES_DE_SECRETO`,
    `CONTRASENAS_DE_EJEMPLO`, `FICHEROS_PROHIBIDOS`, `FICHEROS_PERMITIDOS`,
    `CAMPOS_DEL_COMMIT`.
  - `tokens(texto) -> set[str]`, `huella(token) -> str`,
    `leer_huellas(ruta) -> set[str]`, `huellas_de_la_lista(huellas) -> set[str]`
    (las huellas sin la del centinela), `leer_lista(ruta) -> list[str]`,
    `regenerar(lista, destino) -> int`.
  - `ficheros_versionados(raiz) -> list[Path]`, `es_texto(ruta) -> bool`,
    `binarios(raiz) -> list[Path]`,
    `buscar_huellas(raiz, huellas) -> list[dict]` con las claves `fichero`
    (ruta relativa con `/`), `linea` (0 = el nombre del fichero) y `huella`.
  - `buscar_secretos(raiz) -> list[dict]` con las claves `fichero`, `linea`
    (0 = el fichero entero) y `clase`, que es una de
    `token_de_bot_de_telegram`, `clave_de_api_sk`, `clave_de_api_akia`,
    `clave_de_api_ghp`, `clave_de_api_github_pat`, `jwt`,
    `contrasena_en_url`, `fichero_prohibido`.
  - `verificar_commit(raiz, revision="HEAD", huellas=None) -> list[dict]` con
    las claves `campo` (`autor`, `correo_de_autor`, `quien_confirma`,
    `correo_de_quien_confirma`, `mensaje`), `linea` (la del mensaje; 0 en los
    demás) y `huella`; y `commits(raiz) -> int`.
  - `main(argv=None) -> int` con `--raiz`, `--huellas`, `--commit [REV]`,
    `--un-solo-commit`, `--regenerar` y `--lista`. Devuelve 0 sin hallazgos y
    1 con ellos.

**Decisiones de esta tarea** (donde el contrato dejaba margen):
- **El centinela no cuenta en el árbol.** Es público y el spec lo nombra en
  claro, así que su huella, que va siempre en `huellas.txt`, daría un hallazgo
  en el propio spec, en este plan y en la prueba. `huellas_de_la_lista()`
  la quita, y la usan `test_el_arbol_esta_limpio` y la línea de órdenes. Las
  pruebas del centinela usan el conjunto entero sobre un árbol de juguete.
- **El nombre del fichero también se tokeniza** (línea 0). Si un componente
  del nombre es un hallazgo, la salida lo tapa con `<nombre-con-huella>`.
- **Se tokeniza línea a línea**, para poder dar el número de línea. Un token
  no puede cruzar un salto de línea, así que el resultado es el mismo que
  tokenizando el fichero entero.
- **Texto** es lo que se decodifica en UTF-8 y no lleva bytes nulos. Todo lo
  demás es binario: se declara y no se recorre.
- **Si `raiz` está dentro de un repositorio pero no es su raíz**, se recorre
  todo lo que hay debajo (salvo `.git/`), no solo lo versionado: es el lado
  seguro.
- **Contraseña en URL.** El árbol lleva seis apariciones, todas de ejemplo
  (inventario del 28-sep: `docs/sp2-despliegue.md:310`,
  `docs/sp3-operacion.md:324`, el plan de SP3 línea 372, `tests/conftest.py:76`,
  `tests/test_esquema_bd.py:26`, `tests/test_mantenimiento.py:317`), con tres
  valores: `prueba`, `clave` y `token`. Los tres entran en
  `CONTRASENAS_DE_EJEMPLO` junto con `cambiar-esto`, `...` y `%s`; además se
  permiten los marcadores entre `<` y `>` y las variables `$X` y `${X}`.
  Ningún fichero del árbol hay que cambiarlo por esto.
- **Ficheros prohibidos**: además de `.env`, cualquier `.env.*` que no sea
  `.env.ejemplo`.
- **Los secretos de ejemplo de las pruebas se componen al correr**
  (`"sk" + "-" + …`). `tests/test_anonimato.py` y este plan también se
  recorren, y un secreto de ejemplo escrito entero haría saltar la prueba.
- **Las salidas no llevan nunca el token ni el secreto**: fichero, línea y los
  12 primeros caracteres de la huella, o la clase.

**Avisos para quien ejecuta:**
- Todas las órdenes se corren desde la raíz del repo.
- El código de esta sección se copia TAL CUAL. En particular, no «arregles»
  las cadenas partidas de `_secretos()` ni escribas en ningún comentario una
  URL con usuario y contraseña: el fichero se recorre a sí mismo.
- La lista en claro vive fuera del repositorio. En las órdenes se escribe
  `ANONIMATO_LISTA=<lista en claro>`; su ruta no se escribe en ningún fichero
  del repo ni en ningún mensaje de commit. Si no la tienes, no hace falta: el
  paso 5 trae `huellas.txt` entero.
- No se escribe en ninguna salida, mensaje ni comentario ningún token de la
  lista. Los hallazgos se nombran por fichero, línea y huella.
- Las pruebas que usan `git` crean repositorios de juguete en el directorio
  temporal de pytest, con una configuración de git vacía: no tocan ni el
  repositorio ni la configuración de nadie. Sin `git` en el PATH se saltan.
- `tests/test_anonimato.py` tarda unos 10 s: casi todo son los `git` de los
  repositorios de juguete.

- [ ] **Paso 1: Escribir las pruebas, que fallan**

Crear `tests/test_anonimato.py` con este contenido (todavía sin
`test_el_arbol_esta_limpio`, que llega en el paso 8):

```python
"""Pruebas del anonimato del repositorio (spec de SP5 §6.1).

El repositorio se publica, y lo que se publica no puede llevar ninguna cadena
que identifique al cliente, a la empresa, a la maquina ni a los integrantes.
La lista de esas cadenas NO vive aqui: el repositorio lleva solo
`tests/anonimato/huellas.txt`, con el sha256 de cada token. Por eso estas
pruebas corren siempre, sin la lista: se prueban a si mismas con un token
publico, el centinela, cuya huella va siempre en el fichero.

Los secretos de ejemplo se COMPONEN al correr (`"sk" + "-" + ...`): este
fichero tambien se recorre, y un secreto de ejemplo escrito entero haria
saltar la misma prueba que lo usa.
"""
import hashlib
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "scripts" / "verificar_anonimato.py"
HUELLAS = RAIZ / "tests" / "anonimato" / "huellas.txt"


def _cargar_script():
    """Importa el script por ruta: no es un modulo del paquete."""
    especificacion = importlib.util.spec_from_file_location(
        "verificar_anonimato", SCRIPT)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


va = _cargar_script()

CENTINELA = "centinelaanonimato7f3a"
OTRO = "tokendeprueba9z"          # un segundo token inventado, para la CLI


# --------------------------------------------------------------------------
# Tokenizacion y huellas
# --------------------------------------------------------------------------
def test_tokens_pasa_a_minusculas_y_quita_las_tildes():
    assert va.tokens("Canción ÑANDÚ, Pingüino") == {
        "cancion", "nandu", "pinguino"}


def test_tokens_trocea_una_url():
    assert va.tokens("https://n8n.ejemplo.test/webhook/copiloto-paciente") == {
        "https", "n8n", "ejemplo", "test", "webhook", "copiloto", "paciente"}


def test_tokens_trocea_la_variable_de_la_red():
    assert va.tokens("name: ${RED_N8N:-x_y_network}") == {
        "name", "red", "n8n", "x", "y", "network"}


def test_tokens_trocea_una_ruta_de_windows():
    assert va.tokens("C:\\Users\\u") == {"c", "users", "u"}


def test_tokens_quita_el_base64_largo_y_conserva_el_corto():
    largo = "iVBORw0KGgo" + "A" * 109            # 120 caracteres
    assert len(largo) == 120
    assert va.tokens(f'"image/png": "{largo}"') == {"image", "png"}
    corto = largo[:119]
    assert corto.lower() in va.tokens(f'"image/png": "{corto}"')


def test_tokens_de_un_texto_vacio():
    assert va.tokens("") == set()
    assert va.tokens(" -- \n") == set()


def test_huella_es_el_sha256_del_token_en_utf8():
    assert va.huella("abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    assert va.huella(CENTINELA) == hashlib.sha256(
        CENTINELA.encode("utf-8")).hexdigest()


def test_el_centinela_es_el_del_spec():
    assert va.CENTINELA == CENTINELA


# --------------------------------------------------------------------------
# huellas.txt, el fichero versionado
# --------------------------------------------------------------------------
def test_el_centinela_esta_en_huellas_txt():
    assert va.huella(CENTINELA) in va.leer_huellas(HUELLAS)


def test_huellas_txt_lleva_cabecera_y_huellas_ordenadas_sin_repetir():
    lineas = HUELLAS.read_text(encoding="utf-8").splitlines()
    assert lineas[0].startswith("#")
    datos = [l for l in lineas if l and not l.startswith("#")]
    assert len(datos) > 1, "solo esta el centinela: falta regenerar"
    assert all(len(l) == 64 and set(l) <= set("0123456789abcdef")
               for l in datos)
    assert datos == sorted(set(datos))
    assert set(datos) == va.leer_huellas(HUELLAS)


def test_la_lista_en_claro_esta_ignorada_por_si_alguien_la_copia_dentro():
    lineas = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "tests/anonimato/lista*.txt" in lineas
    assert not list((RAIZ / "tests" / "anonimato").glob("lista*.txt"))


# --------------------------------------------------------------------------
# La lista en claro y la regeneracion (con una lista de juguete)
# --------------------------------------------------------------------------
LISTA_DE_JUGUETE = """\
# comentario de cabecera
[huellas]
# un grupo
Uno-Dos
tres

[sustituciones]
cuatro => cinco
"""


def test_leer_lista_da_solo_la_seccion_de_huellas(tmp_path):
    lista = tmp_path / "lista.txt"
    lista.write_text(LISTA_DE_JUGUETE, encoding="utf-8")
    assert va.leer_lista(lista) == ["Uno-Dos", "tres"]


def test_regenerar_escribe_las_huellas_ordenadas_y_la_del_centinela(tmp_path):
    destino = tmp_path / "anonimato" / "huellas.txt"
    n = va.regenerar(["Uno-Dos", "tres", "uno"], destino)
    esperadas = {va.huella(t) for t in ("uno", "dos", "tres", CENTINELA)}
    assert n == 4
    assert va.leer_huellas(destino) == esperadas
    texto = destino.read_text(encoding="utf-8")
    datos = [l for l in texto.splitlines() if l and not l.startswith("#")]
    assert datos == sorted(esperadas)
    assert texto.startswith("#")
    assert "\r" not in destino.read_bytes().decode("utf-8")
    # El fichero se publica: ningun token en claro, salvo el centinela, que
    # es publico y la cabecera lo nombra.
    for token in ("uno", "dos", "tres"):
        assert token not in va.tokens(texto)


# --------------------------------------------------------------------------
# El recorrido: el centinela escrito DENTRO de un arbol de juguete
# --------------------------------------------------------------------------
def _arbol_limpio(raiz):
    (raiz / "docs").mkdir(parents=True)
    (raiz / "docs" / "guia.md").write_text(
        "# Guía\n\nLa URL es https://n8n.ejemplo.test y nada más.\n",
        encoding="utf-8")
    (raiz / "codigo.py").write_text("x = 1\n", encoding="utf-8")
    (raiz / "figura.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\xff\xfe")
    return raiz


def test_un_arbol_limpio_no_da_hallazgos(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    assert va.buscar_huellas(raiz, va.leer_huellas(HUELLAS)) == []
    assert va.buscar_secretos(raiz) == []


def test_detecta_el_centinela_dentro_del_recorrido(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "docs" / "nota.md").write_text(
        f"primera\nsegunda con {CENTINELA}.\n", encoding="utf-8")
    hallazgos = va.buscar_huellas(raiz, va.leer_huellas(HUELLAS))
    assert hallazgos == [{"fichero": "docs/nota.md", "linea": 2,
                          "huella": va.huella(CENTINELA)}]


def test_lo_detecta_con_mayusculas_tildes_y_pegado_a_separadores(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "a.txt").write_text(
        "red_CentinelaAnónimato7F3A-x\n", encoding="utf-8")
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [(h["fichero"], h["linea"]) for h in hallazgos] == [("a.txt", 1)]


def test_el_hallazgo_nunca_lleva_el_token_en_claro(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "a.txt").write_text(CENTINELA + "\n", encoding="utf-8")
    (hallazgo,) = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert sorted(hallazgo) == ["fichero", "huella", "linea"]
    assert CENTINELA not in repr(hallazgo)


def test_el_nombre_del_fichero_tambien_se_tokeniza(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "docs" / f"{CENTINELA}.md").write_text("nada\n", encoding="utf-8")
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [h["linea"] for h in hallazgos] == [0]
    assert CENTINELA not in repr(hallazgos)
    assert hallazgos[0]["fichero"].startswith("docs/")


def test_los_binarios_se_declaran_y_no_se_recorren(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "otra.png").write_bytes(
        b"\x89PNG\x00" + CENTINELA.encode("ascii") + b"\xff")
    assert va.es_texto(raiz / "codigo.py")
    assert not va.es_texto(raiz / "otra.png")
    assert [p.name for p in va.binarios(raiz)] == ["figura.png", "otra.png"]
    assert va.buscar_huellas(raiz, {va.huella(CENTINELA)}) == []


# --------------------------------------------------------------------------
# Con git: solo lo versionado
# --------------------------------------------------------------------------
hay_git = pytest.mark.skipif(shutil.which("git") is None,
                             reason="sin git en el PATH: queda sin verificar "
                                    "el recorrido de lo versionado y el "
                                    "commit")


def _git(raiz, *argumentos, **entorno):
    """git sobre el repositorio de juguete, sin la configuracion de nadie."""
    vacio = raiz.parent / "gitconfig-vacio"
    vacio.touch()
    limpio = {c: v for c, v in os.environ.items() if not c.startswith("GIT_")}
    limpio.update(GIT_CONFIG_GLOBAL=str(vacio), GIT_CONFIG_NOSYSTEM="1",
                  GIT_AUTHOR_NAME="Autor Neutro",
                  GIT_AUTHOR_EMAIL="autor@ejemplo.test",
                  GIT_COMMITTER_NAME="Autor Neutro",
                  GIT_COMMITTER_EMAIL="autor@ejemplo.test")
    limpio.update(entorno)
    subprocess.run(["git", "-C", str(raiz), *argumentos], check=True,
                   capture_output=True, env=limpio)


def _repositorio(tmp_path):
    raiz = _arbol_limpio(tmp_path / "repo")
    _git(raiz, "init", "-q")
    _git(raiz, "add", "-A")
    return raiz


@hay_git
def test_en_un_repositorio_se_recorre_solo_lo_versionado(tmp_path):
    raiz = _repositorio(tmp_path)
    (raiz / "sin_versionar.txt").write_text(CENTINELA + "\n",
                                            encoding="utf-8")
    nombres = [p.relative_to(raiz).as_posix()
               for p in va.ficheros_versionados(raiz)]
    assert nombres == ["codigo.py", "docs/guia.md", "figura.png"]
    assert va.buscar_huellas(raiz, {va.huella(CENTINELA)}) == []

    (raiz / "docs" / "guia.md").write_text(f"ahora sí: {CENTINELA}\n",
                                           encoding="utf-8")
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [(h["fichero"], h["linea"]) for h in hallazgos] == [
        ("docs/guia.md", 1)]


def test_sin_repositorio_se_recorre_todo_salvo_la_carpeta_de_git(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / ".git").mkdir()
    (raiz / ".git" / "config").write_text(CENTINELA, encoding="utf-8")
    nombres = [p.relative_to(raiz).as_posix()
               for p in va.ficheros_versionados(raiz)]
    assert nombres == ["codigo.py", "docs/guia.md", "figura.png"]


@hay_git
def test_verificar_commit_mira_autor_quien_confirma_y_mensaje(tmp_path):
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "primer commit", "-m", "sin nada")
    huellas = {va.huella(CENTINELA)}
    assert va.commits(raiz) == 1
    assert va.verificar_commit(raiz, huellas=huellas) == []

    (raiz / "codigo.py").write_text("x = 2\n", encoding="utf-8")
    _git(raiz, "commit", "-q", "-a", "-m", "segundo",
         "-m", f"cuerpo con {CENTINELA}",
         GIT_AUTHOR_NAME=f"Nombre {CENTINELA.upper()}",
         GIT_COMMITTER_EMAIL=f"{CENTINELA}@ejemplo.test")
    assert va.commits(raiz) == 2
    hallazgos = va.verificar_commit(raiz, "HEAD", huellas=huellas)
    assert [(h["campo"], h["linea"]) for h in hallazgos] == [
        ("autor", 0), ("correo_de_quien_confirma", 0), ("mensaje", 3)]
    assert all(h["huella"] == va.huella(CENTINELA) for h in hallazgos)
    assert CENTINELA not in repr(hallazgos).lower()
    assert va.verificar_commit(raiz, "HEAD~1", huellas=huellas) == []


# --------------------------------------------------------------------------
# Secretos. Se componen al correr: ver el docstring del fichero.
# --------------------------------------------------------------------------
def _secretos():
    return {
        "token_de_bot_de_telegram": "123456789" + ":" + "AAH" + "x" * 32,
        "clave_de_api_sk": "sk" + "-" + "proj" + "-" + "a1B2" * 6,
        "clave_de_api_akia": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "clave_de_api_ghp": "gh" + "p_" + "a1B2" * 9,
        "clave_de_api_github_pat": "github" + "_pat_" + "a1B2_" * 6,
        "jwt": ".".join(["ey" + "J" + "hbGciOiJIUzI1NiJ9",
                         "ey" + "J" + "zdWIiOiIxMjM0NTY3ODkwIn0",
                         "dozjgNryP4J3jVmNHl0w5N"]),
        "contrasena_en_url": "postgresql://usuario" + ":" + "S3creta!"
                             + "@" + "bd.ejemplo.test:5432/base",
    }


@pytest.mark.parametrize("clase", sorted(_secretos()))
def test_buscar_secretos_encuentra_cada_clase_sin_imprimirla(tmp_path, clase):
    secreto = _secretos()[clase]
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "config.txt").write_text(f"uno\ndos\nVALOR = \"{secreto}\"\n",
                                     encoding="utf-8")
    hallazgos = va.buscar_secretos(raiz)
    assert hallazgos == [{"fichero": "config.txt", "linea": 3,
                          "clase": clase}]


def test_las_contrasenas_de_ejemplo_en_url_se_permiten(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    valores = ["prueba", "cambiar-esto", "clave", "token", "<contraseña>",
               "...", "%s", "$CLAVE", "${COPILOTO_BD_PASSWORD}"]
    assert set(valores[:4]) | {"...", "%s"} <= set(va.CONTRASENAS_DE_EJEMPLO)
    (raiz / "guia.md").write_text(
        "".join("postgresql://usuario" + ":" + v + "@" + "host:5432/base\n"
                for v in valores), encoding="utf-8")
    assert va.buscar_secretos(raiz) == []


def test_una_url_sin_contrasena_no_es_un_hallazgo(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "guia.md").write_text(
        "git clone https://github.com/<cuenta>/copiloto-triaje.git\n"
        "correo: alguien@ejemplo.test, http://127.0.0.1:8000/salud\n"
        "ssh://git@ejemplo.test:22/repo.git\n", encoding="utf-8")
    assert va.buscar_secretos(raiz) == []


@pytest.mark.parametrize("nombre", [
    ".env", "servidor/.env", ".env.local", "kaggle.json", "claves/servidor.pem",
    "privada.key", "id_rsa", "id_rsa.pub", "certificado.p12"])
def test_los_ficheros_prohibidos_son_hallazgos(tmp_path, nombre):
    raiz = _arbol_limpio(tmp_path / "arbol")
    ruta = raiz / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("X=1\n", encoding="utf-8")
    assert va.buscar_secretos(raiz) == [
        {"fichero": nombre, "linea": 0, "clase": "fichero_prohibido"}]


def test_el_env_de_ejemplo_se_permite(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / ".env.ejemplo").write_text(
        "COPILOTO_BD_PASSWORD=cambiar-esto\n", encoding="utf-8")
    assert va.buscar_secretos(raiz) == []


# --------------------------------------------------------------------------
# La linea de ordenes
# --------------------------------------------------------------------------
def _huellas_de_juguete(tmp_path):
    destino = tmp_path / "huellas.txt"
    va.regenerar([OTRO], destino)
    return destino


def test_la_cli_sale_con_0_sobre_un_arbol_limpio(tmp_path, capsys):
    raiz = _arbol_limpio(tmp_path / "arbol")
    # El centinela es publico (el spec lo nombra): en el arbol no cuenta.
    (raiz / "spec.md").write_text(f"el token `{CENTINELA}`\n",
                                  encoding="utf-8")
    codigo = va.main(["--raiz", str(raiz),
                      "--huellas", str(_huellas_de_juguete(tmp_path))])
    salida = capsys.readouterr().out
    assert codigo == 0
    assert "huellas: 0" in salida and "secretos: 0" in salida
    assert "binarios sin recorrer: 1" in salida
    assert "figura.png" in salida


def test_la_cli_sale_con_1_y_resume_por_clase(tmp_path, capsys):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "a.md").write_text(f"x\n{OTRO}\n{OTRO.upper()}\n",
                               encoding="utf-8")
    (raiz / "b.md").write_text(_secretos()["clave_de_api_akia"] + "\n",
                               encoding="utf-8")
    codigo = va.main(["--raiz", str(raiz),
                      "--huellas", str(_huellas_de_juguete(tmp_path))])
    salida = capsys.readouterr().out
    assert codigo == 1
    assert "a.md:2: huella " + va.huella(OTRO)[:12] in salida
    assert "b.md:1: clave_de_api_akia" in salida
    assert "huellas: 2 en 1 ficheros" in salida
    assert "secretos: 1 (clave_de_api_akia: 1)" in salida
    assert OTRO not in salida.lower()
    assert _secretos()["clave_de_api_akia"] not in salida


@hay_git
def test_la_cli_verifica_el_commit_y_que_sea_uno_solo(tmp_path, capsys):
    raiz = _repositorio(tmp_path)
    huellas = str(_huellas_de_juguete(tmp_path))
    _git(raiz, "commit", "-q", "-m", "arbol anonimizado")
    assert va.main(["--raiz", str(raiz), "--huellas", huellas,
                    "--commit", "--un-solo-commit"]) == 0
    salida = capsys.readouterr().out
    assert "commit HEAD: 0" in salida and "commits: 1" in salida

    (raiz / "codigo.py").write_text("x = 2\n", encoding="utf-8")
    _git(raiz, "commit", "-q", "-a", "-m", "otro",
         GIT_AUTHOR_EMAIL=f"alguien@{OTRO}.test")
    assert va.main(["--raiz", str(raiz), "--huellas", huellas,
                    "--commit", "HEAD", "--un-solo-commit"]) == 1
    salida = capsys.readouterr().out
    assert "commit HEAD: correo_de_autor: huella " in salida
    assert "commits: 2" in salida
    assert OTRO not in salida.lower()


def test_la_cli_regenera_desde_la_variable_o_desde_lista(tmp_path, capsys,
                                                        monkeypatch):
    lista = tmp_path / "lista.txt"
    lista.write_text(LISTA_DE_JUGUETE, encoding="utf-8")
    destino = tmp_path / "huellas.txt"
    esperadas = {va.huella(t) for t in ("uno", "dos", "tres", CENTINELA)}

    monkeypatch.delenv("ANONIMATO_LISTA", raising=False)
    assert va.main(["--regenerar", "--lista", str(lista),
                    "--huellas", str(destino)]) == 0
    assert va.leer_huellas(destino) == esperadas
    assert "4 huellas" in capsys.readouterr().out

    destino.unlink()
    monkeypatch.setenv("ANONIMATO_LISTA", str(lista))
    assert va.main(["--regenerar", "--huellas", str(destino)]) == 0
    assert va.leer_huellas(destino) == esperadas


def test_la_cli_sin_lista_dice_que_variable_falta(tmp_path, monkeypatch):
    monkeypatch.delenv("ANONIMATO_LISTA", raising=False)
    with pytest.raises(SystemExit) as salida:
        va.main(["--regenerar", "--huellas", str(tmp_path / "h.txt")])
    assert "ANONIMATO_LISTA" in str(salida.value)
    assert not (tmp_path / "h.txt").exists()
```

- [ ] **Paso 2: Correrlas y ver el fallo**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_anonimato.py
```

Salida esperada (el script no existe; la ruta del mensaje es la de tu
repositorio):

```
ERROR tests/test_anonimato.py - FileNotFoundError: [Errno 2] No such file or ...
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.17s
```

- [ ] **Paso 3: Escribir el script**

Crear `scripts/verificar_anonimato.py`:

```python
"""Comprueba que el repositorio se puede publicar (spec de SP5 §6.1).

Uso, desde la raiz del repositorio:

    python scripts/verificar_anonimato.py
    python scripts/verificar_anonimato.py --raiz <arbol> --commit --un-solo-commit
    ANONIMATO_LISTA=<lista en claro> python scripts/verificar_anonimato.py --regenerar

Busca dos cosas en los ficheros versionados:

1. HUELLAS. La lista de cadenas que identifican al cliente, a la empresa, a la
   maquina o a los integrantes NO vive en el repositorio. El repositorio lleva
   solo `tests/anonimato/huellas.txt`: el sha256 de cada token. Cada fichero
   de texto se tokeniza igual que la lista (minusculas, sin tildes, particion
   por todo lo que no sea [a-z0-9]) y se compara huella con huella.
2. SECRETOS, por patron: token de bot de Telegram, claves de API, contrasena
   dentro de una URL, y ficheros que no deben viajar (`.env`, claves).

Ninguna salida lleva el token ni el secreto en claro: fichero, linea y huella
o clase. La salida tambien se puede publicar.

Sale con 0 si no hay hallazgos y con 1 si los hay. Lo usa
`tests/test_anonimato.py`, que lo carga por ruta.
"""
import argparse
import fnmatch
import hashlib
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HUELLAS_POR_DEFECTO = REPO / "tests" / "anonimato" / "huellas.txt"
VARIABLE_DE_LA_LISTA = "ANONIMATO_LISTA"

# El centinela es PUBLICO: el spec lo nombra. Su huella va siempre en
# huellas.txt para que la prueba se pruebe a si misma sin la lista. Por eso
# mismo no cuenta como hallazgo en el arbol (ver `huellas_de_la_lista`).
CENTINELA = "centinelaanonimato7f3a"

# Las imagenes incrustadas de los notebooks: una tirada asi, troceada por
# `+`, `/` y `=`, da tokens al azar que pueden coincidir con uno corto.
BASE64 = re.compile(r"[A-Za-z0-9+/=]{120,}")
NO_TOKEN = re.compile(r"[^a-z0-9]+")

CABECERA = """\
# Huellas del anonimato (spec de SP5 §6.1): el sha256 de cada token de la
# lista negra, que vive FUERA del repositorio. Una por línea, ordenadas.
# Incluye siempre la del centinela público `centinelaanonimato7f3a`.
# No se edita a mano. Se regenera con:
#   ANONIMATO_LISTA=<lista en claro> python scripts/verificar_anonimato.py --regenerar
"""


# --------------------------------------------------------------------------
# Tokens y huellas
# --------------------------------------------------------------------------
def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def tokens(texto):
    """Los tokens de un texto: la misma regla para la lista y los ficheros."""
    texto = BASE64.sub(" ", texto)
    return set(NO_TOKEN.split(_sin_tildes(texto).lower())) - {""}


def huella(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def leer_huellas(ruta):
    """Las huellas de `huellas.txt`, sin la cabecera ni lineas vacias."""
    lineas = Path(ruta).read_text(encoding="utf-8").splitlines()
    return {l.strip() for l in lineas
            if l.strip() and not l.lstrip().startswith("#")}


def huellas_de_la_lista(huellas):
    """Las huellas sin la del centinela: lo que se busca en el arbol."""
    return set(huellas) - {huella(CENTINELA)}


def leer_lista(ruta):
    """Las entradas de la seccion `[huellas]` de la lista en claro."""
    entradas, dentro = [], False
    for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea.startswith("["):
            dentro = linea == "[huellas]"
        elif dentro and linea and not linea.startswith("#"):
            entradas.append(linea)
    return entradas


def regenerar(lista, destino):
    """Escribe las huellas de los tokens de `lista`, ordenadas, y las cuenta.

    Cada entrada se tokeniza: una entrada con separadores da varias huellas.
    La del centinela va siempre.
    """
    todas = {huella(CENTINELA)}
    for entrada in lista:
        todas |= {huella(t) for t in tokens(entrada)}
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="\n") as salida:
        salida.write(CABECERA)
        for una in sorted(todas):
            salida.write(una + "\n")
    return len(todas)


# --------------------------------------------------------------------------
# El recorrido
# --------------------------------------------------------------------------
def _git(raiz, *argumentos):
    """La salida de git en bytes, o None si git falla o no esta."""
    try:
        hecho = subprocess.run(["git", "-C", str(raiz), *argumentos],
                               capture_output=True, check=False)
    except OSError:
        return None
    return hecho.stdout if hecho.returncode == 0 else None


def _es_la_raiz_de_un_repositorio(raiz):
    cima = _git(raiz, "rev-parse", "--show-toplevel")
    if cima is None:
        return False
    try:
        return os.path.samefile(cima.decode("utf-8").strip(), raiz)
    except OSError:
        return False


def ficheros_versionados(raiz):
    """Los ficheros versionados bajo `raiz`, ordenados.

    Si `raiz` no es la raiz de un repositorio de git, todos los ficheros que
    hay debajo salvo la carpeta `.git/`.
    """
    raiz = Path(raiz)
    if _es_la_raiz_de_un_repositorio(raiz):
        salida = _git(raiz, "ls-files", "-z")
        if salida is not None:
            nombres = [n for n in salida.decode("utf-8").split("\0") if n]
            return [raiz / n for n in sorted(nombres) if (raiz / n).is_file()]
    hallados = []
    for carpeta, subcarpetas, nombres in os.walk(raiz):
        subcarpetas[:] = [s for s in subcarpetas if s != ".git"]
        hallados += [Path(carpeta) / n for n in nombres]
    return sorted(hallados, key=lambda p: p.relative_to(raiz).as_posix())


def _texto(ruta):
    """El texto del fichero, o None si no es texto."""
    datos = Path(ruta).read_bytes()
    if b"\0" in datos:
        return None
    try:
        return datos.decode("utf-8")
    except UnicodeDecodeError:
        return None


def es_texto(ruta):
    """Es texto lo que se decodifica en UTF-8 y no lleva bytes nulos."""
    return _texto(ruta) is not None


def binarios(raiz):
    """Lo que no es texto: se declara y se revisa a mano, no se recorre."""
    return [p for p in ficheros_versionados(raiz) if not es_texto(p)]


def _relativo(ruta, raiz):
    return Path(ruta).relative_to(raiz).as_posix()


def buscar_huellas(raiz, huellas):
    """Las apariciones de alguna huella: fichero, linea y huella.

    La linea 0 es el nombre del fichero. El token en claro no sale nunca.
    """
    raiz, huellas = Path(raiz), set(huellas)
    hallazgos = []

    def mirar(texto, fichero, linea):
        for una in sorted({huella(t) for t in tokens(texto)} & huellas):
            hallazgos.append({"fichero": fichero, "linea": linea,
                              "huella": una})

    for ruta in ficheros_versionados(raiz):
        fichero = _relativo(ruta, raiz)
        mirar(fichero, _oculto(fichero, huellas), 0)
        texto = _texto(ruta)
        if texto is None:
            continue
        for n, linea in enumerate(texto.splitlines(), 1):
            mirar(linea, fichero, n)
    return hallazgos


def _oculto(fichero, huellas):
    """El nombre del fichero, con los componentes que son hallazgo tapados."""
    partes = []
    for parte in fichero.split("/"):
        sucio = {huella(t) for t in tokens(parte)} & huellas
        partes.append("<nombre-con-huella>" if sucio else parte)
    return "/".join(partes)


# --------------------------------------------------------------------------
# Secretos
# --------------------------------------------------------------------------
PATRONES_DE_SECRETO = {
    "token_de_bot_de_telegram": re.compile(
        r"(?<![0-9A-Za-z])\d{8,10}:[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])"),
    "clave_de_api_sk": re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    "clave_de_api_akia": re.compile(
        r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![0-9A-Z])"),
    "clave_de_api_ghp": re.compile(r"(?<![A-Za-z0-9])ghp_[A-Za-z0-9]{36}"),
    "clave_de_api_github_pat": re.compile(
        r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{22,}"),
    "jwt": re.compile(
        r"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
}

# Esquema, dos barras, usuario, dos puntos, contrasena, arroba y host.
URL_CON_CONTRASENA = re.compile(
    r"[A-Za-z][A-Za-z0-9+.-]*://[^\s/:@]+:([^\s/@]+)@")

# Lo que puede ir en el sitio de la contrasena. Las palabras salen del
# inventario del arbol (28-sep): `prueba` es la del PostgreSQL desechable de
# las pruebas; `clave` y `token`, las de los ejemplos de las guias;
# `cambiar-esto`, el valor de ejemplo del spec.
CONTRASENAS_DE_EJEMPLO = ("prueba", "cambiar-esto", "clave", "token",
                          "...", "%s")
CONTRASENA_MARCADOR = re.compile(
    r"<[^<>]+>|\$[A-Za-z_][A-Za-z0-9_]*|\$\{[^{}]+\}")

FICHEROS_PROHIBIDOS = (".env", ".env.*", "kaggle.json", "*.pem", "*.key",
                       "id_rsa*", "*.p12")
FICHEROS_PERMITIDOS = (".env.ejemplo",)


def _es_de_ejemplo(contrasena):
    return (contrasena in CONTRASENAS_DE_EJEMPLO
            or CONTRASENA_MARCADOR.fullmatch(contrasena) is not None)


def _clases_de_secreto(linea):
    clases = [clase for clase, patron in PATRONES_DE_SECRETO.items()
              if patron.search(linea)]
    if any(not _es_de_ejemplo(m.group(1))
           for m in URL_CON_CONTRASENA.finditer(linea)):
        clases.append("contrasena_en_url")
    return clases


def _prohibido(nombre):
    return (nombre not in FICHEROS_PERMITIDOS
            and any(fnmatch.fnmatchcase(nombre, p)
                    for p in FICHEROS_PROHIBIDOS))


def buscar_secretos(raiz):
    """Secretos por patron y ficheros prohibidos: fichero, linea y clase.

    La linea 0 es el fichero entero. El secreto no sale nunca.
    """
    raiz = Path(raiz)
    hallazgos = []
    for ruta in ficheros_versionados(raiz):
        fichero = _relativo(ruta, raiz)
        if _prohibido(ruta.name):
            hallazgos.append({"fichero": fichero, "linea": 0,
                              "clase": "fichero_prohibido"})
            continue
        texto = _texto(ruta)
        if texto is None:
            continue
        for n, linea in enumerate(texto.splitlines(), 1):
            for clase in _clases_de_secreto(linea):
                hallazgos.append({"fichero": fichero, "linea": n,
                                  "clase": clase})
    return hallazgos


# --------------------------------------------------------------------------
# El commit
# --------------------------------------------------------------------------
CAMPOS_DEL_COMMIT = ("autor", "correo_de_autor", "quien_confirma",
                     "correo_de_quien_confirma", "mensaje")


def verificar_commit(raiz, revision="HEAD", huellas=None):
    """Autor, quien confirma, sus correos y el mensaje, contra las huellas.

    Devuelve `campo`, `linea` (la del mensaje; 0 en los demas) y `huella`.
    Sin `huellas`, las del repositorio donde vive el script.
    """
    if huellas is None:
        huellas = huellas_de_la_lista(leer_huellas(HUELLAS_POR_DEFECTO))
    huellas = set(huellas)
    salida = _git(raiz, "log", "-1",
                  "--format=%an%x00%ae%x00%cn%x00%ce%x00%B", revision, "--")
    if salida is None:
        raise SystemExit(f"No se pudo leer el commit {revision} de {raiz}: "
                         "¿es un repositorio de git con commits?")
    valores = salida.decode("utf-8", errors="replace").split("\0", 4)
    hallazgos = []
    for campo, valor in zip(CAMPOS_DEL_COMMIT, valores):
        lineas = valor.splitlines() if campo == "mensaje" else [valor]
        for n, linea in enumerate(lineas, 1):
            for una in sorted({huella(t) for t in tokens(linea)} & huellas):
                hallazgos.append({"campo": campo,
                                  "linea": n if campo == "mensaje" else 0,
                                  "huella": una})
    return hallazgos


def commits(raiz):
    """Cuantos commits se alcanzan desde HEAD."""
    salida = _git(raiz, "rev-list", "--count", "HEAD")
    if salida is None:
        raise SystemExit(f"No se pudieron contar los commits de {raiz}: "
                         "¿es un repositorio de git con commits?")
    return int(salida.decode("ascii").strip())


# --------------------------------------------------------------------------
# La linea de ordenes
# --------------------------------------------------------------------------
def _argumentos(argv):
    analizador = argparse.ArgumentParser(
        description="Huellas de la lista negra y secretos en lo que se "
                    "publica (spec de SP5 §6.1).")
    analizador.add_argument("--raiz", type=Path, default=REPO,
                            help="árbol que se comprueba (por defecto, este "
                                 "repositorio)")
    analizador.add_argument("--huellas", type=Path,
                            default=HUELLAS_POR_DEFECTO,
                            help="fichero de huellas (por defecto, "
                                 "tests/anonimato/huellas.txt)")
    analizador.add_argument("--commit", nargs="?", const="HEAD", default=None,
                            metavar="REV",
                            help="comprueba también autor, correo, quien "
                                 "confirma y mensaje de ese commit (HEAD)")
    analizador.add_argument("--un-solo-commit", action="store_true",
                            help="exige que el repositorio tenga un solo "
                                 "commit")
    analizador.add_argument("--regenerar", action="store_true",
                            help="escribe el fichero de huellas desde la "
                                 f"lista en claro ({VARIABLE_DE_LA_LISTA} o "
                                 "--lista)")
    analizador.add_argument("--lista", type=Path, default=None,
                            help="la lista en claro, fuera del repositorio")
    return analizador.parse_args(argv)


def _regenerar(args):
    lista = args.lista or os.environ.get(VARIABLE_DE_LA_LISTA)
    if not lista:
        raise SystemExit(
            f"Falta la lista en claro: define {VARIABLE_DE_LA_LISTA} o pasa "
            "--lista. Vive fuera del repositorio.")
    n = regenerar(leer_lista(lista), args.huellas)
    print(f"{n} huellas escritas en {args.huellas} (con la del centinela).")
    return 0


def main(argv=None):
    args = _argumentos(argv)
    if args.regenerar:
        return _regenerar(args)

    huellas = huellas_de_la_lista(leer_huellas(args.huellas))
    recorridos = ficheros_versionados(args.raiz)
    sin_recorrer = binarios(args.raiz)
    de_huella = buscar_huellas(args.raiz, huellas)
    de_secreto = buscar_secretos(args.raiz)

    for h in de_huella:
        print(f"{h['fichero']}:{h['linea']}: huella {h['huella'][:12]}")
    for h in de_secreto:
        print(f"{h['fichero']}:{h['linea']}: {h['clase']}")

    del_commit = []
    if args.commit is not None:
        del_commit = verificar_commit(args.raiz, args.commit, huellas=huellas)
        for h in del_commit:
            donde = (f"{h['campo']}:{h['linea']}" if h["linea"]
                     else h["campo"])
            print(f"commit {args.commit}: {donde}: "
                  f"huella {h['huella'][:12]}")

    print("--")
    print(f"ficheros recorridos: {len(recorridos) - len(sin_recorrer)}")
    print(f"binarios sin recorrer: {len(sin_recorrer)}")
    for ruta in sin_recorrer:
        print(f"  {_relativo(ruta, args.raiz)}")
    ficheros = len({h["fichero"] for h in de_huella})
    print(f"huellas: {len(de_huella)} en {ficheros} ficheros")
    por_clase = {}
    for h in de_secreto:
        por_clase[h["clase"]] = por_clase.get(h["clase"], 0) + 1
    detalle = ", ".join(f"{c}: {n}" for c, n in sorted(por_clase.items()))
    print(f"secretos: {len(de_secreto)}" + (f" ({detalle})" if detalle else ""))
    mal = len(de_huella) + len(de_secreto) + len(del_commit)
    if args.commit is not None:
        print(f"commit {args.commit}: {len(del_commit)}")
    if args.un_solo_commit:
        cuantos = commits(args.raiz)
        print(f"commits: {cuantos}")
        mal += cuantos != 1
    print("limpio" if not mal else "NO publicar: hay hallazgos")
    return 1 if mal else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    raise SystemExit(main())
```

- [ ] **Paso 4: Correr las pruebas: quedan cinco en rojo, las del fichero de huellas y la del `.gitignore`**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_anonimato.py
```

Salida esperada:

```
FAILED tests/test_anonimato.py::test_el_centinela_esta_en_huellas_txt - FileN...
FAILED tests/test_anonimato.py::test_huellas_txt_lleva_cabecera_y_huellas_ordenadas_sin_repetir
FAILED tests/test_anonimato.py::test_la_lista_en_claro_esta_ignorada_por_si_alguien_la_copia_dentro
FAILED tests/test_anonimato.py::test_un_arbol_limpio_no_da_hallazgos - FileNo...
FAILED tests/test_anonimato.py::test_detecta_el_centinela_dentro_del_recorrido
5 failed, 41 passed in 10.21s
```

Cuatro fallan con `FileNotFoundError` (falta `tests/anonimato/huellas.txt`) y
una con `AssertionError` (falta la línea del `.gitignore`).

- [ ] **Paso 5: `.gitignore` y `huellas.txt`**

Añadir AL FINAL de `.gitignore`, después de la línea `pruebas/sesion/` y
dejando una línea en blanco:

```

# La lista en claro del anonimato (spec de SP5 §6.1) vive FUERA del
# repositorio. Por si alguien la copia aqui: tampoco se versiona.
tests/anonimato/lista*.txt
```

Generar las huellas. Con la lista en claro:

```bash
ANONIMATO_LISTA=<lista en claro> C:/venv-copiloto/Scripts/python.exe -B scripts/verificar_anonimato.py --regenerar
```

Salida esperada (la ruta es la de tu repositorio):

```
29 huellas escritas en <raiz-del-repositorio>\tests\anonimato\huellas.txt (con la del centinela).
```

El fichero que sale tiene que ser EXACTAMENTE este. Sin la lista en claro,
crear `tests/anonimato/huellas.txt` con este contenido (son sha256: se pueden
publicar):

```
# Huellas del anonimato (spec de SP5 §6.1): el sha256 de cada token de la
# lista negra, que vive FUERA del repositorio. Una por línea, ordenadas.
# Incluye siempre la del centinela público `centinelaanonimato7f3a`.
# No se edita a mano. Se regenera con:
#   ANONIMATO_LISTA=<lista en claro> python scripts/verificar_anonimato.py --regenerar
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
3f3ef2d55fba74e22660c8d7f97c35aff20cba82f26eb998502be73ade436547
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
[retirado]
```

Si al regenerar sale otro número u otras huellas, la lista en claro ha
cambiado desde que se escribió este plan: se versiona lo que sale de la lista
de hoy, y se dice en el mensaje del commit cuántas huellas lleva.

- [ ] **Paso 6: Correr las pruebas: verde**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_anonimato.py
```

Salida esperada:

```
..............................................                           [100%]
46 passed in 9.89s
```

Ningún fichero que existiera cambia de comportamiento con esta tarea (solo
gana tres líneas el `.gitignore`), así que la suite entera tiene que dar lo
mismo que antes más estas 46. Sobre la base en la que se escribió este plan
(antes de fusionar SP5-B1; con SP5-B1 la partida es `699 passed, 18
skipped, 7 errors`), sin los ficheros ignorados por git y sin
dataset, eran `543 passed, 18 skipped, 7 errors` y
pasan a ser `589 passed, 18 skipped, 7 errors`; los 7 errores son de
`tests/test_contrato_mcp.py` (2) y `tests/test_seleccion_casos.py` (5), por
ficheros ignorados que faltan, con o sin esta tarea.

- [ ] **Paso 7: Commit**

```bash
git add scripts/verificar_anonimato.py tests/test_anonimato.py tests/anonimato/huellas.txt .gitignore
git commit -m "test(anonimato): huellas de la lista negra, centinela y patrones de secretos (SP5-B2 T5)" -m "scripts/verificar_anonimato.py tokeniza los ficheros versionados y los compara, huella con huella, con tests/anonimato/huellas.txt (29 sha256, con la del centinela publico); busca secretos por patron y ficheros prohibidos, y comprueba autor, quien confirma y mensaje del commit. Ninguna salida lleva el token ni el secreto. La lista en claro vive fuera del repositorio. Falta test_el_arbol_esta_limpio, que exige la anonimizacion hecha." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
---

### Tarea 6: La sustitución mecánica en la documentación, y el árbol limpio

Después de las tareas 1 a 5 lo que queda de la lista negra está en prosa:
guías, specs, planes y una celda de un notebook. Aquí se sustituye, y se
añade a la suite la prueba que exige el árbol limpio.

**Ficheros:**
- Modificar: `docs/sp2-despliegue.md`, `docs/sp3-operacion.md`
- Modificar: `docs/superpowers/specs/2026-09-16-sp1-nucleo-imagen-design.md`,
  `docs/superpowers/specs/2026-09-24-sp3-bot-n8n-design.md`
- Modificar: `docs/superpowers/plans/2026-09-16-sp1-nucleo-imagen.md`,
  `docs/superpowers/plans/2026-09-23-sp2-servidor-mcp.md`,
  `docs/superpowers/plans/2026-09-24-sp3-bot-n8n.md`,
  `docs/superpowers/plans/2026-09-26-sp4-combinacion-bayesiana.md`
- Modificar: `notebooks/eda_rsna.ipynb` (la celda de la cabecera)
- Modificar: cualquier otro fichero versionado donde el comprobador encuentre
  algo (no debería quedar ninguno fuera de esta lista: si aparece, es un
  hallazgo que se anota en el informe de la tarea)
- Modificar: `tests/test_anonimato.py` (gana `test_el_arbol_esta_limpio`)

**Interfaces:**
- Consume: `scripts/verificar_anonimato.py` (tarea 5): `buscar_huellas(raiz, huellas)`,
  `buscar_secretos(raiz)`, `leer_huellas(ruta)`, y su CLI; la lista en claro
  (`ANONIMATO_LISTA`), secciones `[huellas]` y `[sustituciones]`.
- Produce: el árbol sin ninguna huella; `test_el_arbol_esta_limpio` en la suite.

**Antes de empezar:** `ANONIMATO_LISTA` tiene que apuntar a la lista en claro.
Comprueba que existe: `python -c "import os, pathlib; print(pathlib.Path(os.environ['ANONIMATO_LISTA']).is_file())"`
tiene que imprimir `True`.

- [ ] **Paso 1: Un comprobador desechable que dice DÓNDE y QUÉ**

`scripts/verificar_anonimato.py` no imprime nunca el token (su salida se puede
publicar). Para sustituir hace falta verlo. Crea este script en una carpeta
temporal **fuera del repositorio** (por ejemplo `$TEMP/anonimato/donde.py`);
no se versiona y se borra en el paso 9:

```python
# -*- coding: utf-8 -*-
"""Dice en qué línea de qué fichero versionado queda algún token de la lista
negra, y cuál. DESECHABLE: imprime tokens en claro; no se versiona.

    python donde.py <raiz del repo> [<fichero> ...]
"""
import os
import pathlib
import re
import subprocess
import sys
import unicodedata

BASE64 = re.compile(r"[A-Za-z0-9+/=]{120,}")


def tokens(texto):
    texto = BASE64.sub(" ", texto)
    plano = "".join(c for c in unicodedata.normalize("NFD", texto)
                    if unicodedata.category(c) != "Mn")
    return set(re.split(r"[^a-z0-9]+", plano.lower())) - {""}


def lista_negra():
    negra, dentro = set(), False
    lista = pathlib.Path(os.environ["ANONIMATO_LISTA"])
    for linea in lista.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea.startswith("["):
            dentro = linea == "[huellas]"
        elif dentro and linea and not linea.startswith("#"):
            negra.add(linea)
    return negra


def main(argv):
    raiz = pathlib.Path(argv[0])
    if argv[1:]:
        ficheros = argv[1:]
    else:
        salida = subprocess.run(["git", "-C", str(raiz), "ls-files", "-z"],
                                capture_output=True, check=True).stdout
        ficheros = [f for f in salida.decode("utf-8").split("\0") if f]
    negra = lista_negra()
    total = 0
    for nombre in ficheros:
        try:
            texto = (raiz / nombre).read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue                                   # binario: se declara, no se recorre
        lineas = [(n, sorted(tokens(linea) & negra))
                  for n, linea in enumerate(texto.splitlines(), 1)]
        lineas = [(n, t) for n, t in lineas if t]
        if lineas:
            total += len(lineas)
            print(f"{nombre}: {len(lineas)} líneas")
            for n, t in lineas:
                print(f"    {n}: {t}")
    print("limpio" if not total else f"{total} líneas con tokens de la lista negra")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Paso 2: El inventario de partida**

Orden (desde la raíz del repo): `python "$TEMP/anonimato/donde.py" .`

Esperado: solo aparecen los ficheros de la lista de «Ficheros» de esta tarea.
Apunta en el informe el recuento por fichero. Si aparece un fichero de código
o de pruebas (`src/`, `scripts/`, `pruebas/`, `tests/`, `servidor/`, `n8n/`,
`bd/`), **para**: alguna de las tareas 1 a 4 quedó a medias; dilo en el
informe y no sigas sustituyendo por encima.

- [ ] **Paso 3: La sustitución mecánica**

Crea, en la misma carpeta temporal, el script que aplica la sección
`[sustituciones]` de la lista. Las entradas cuyo marcador empieza por `(` no
se aplican: son las que hay que redactar a mano (paso 4).

```python
# -*- coding: utf-8 -*-
"""Aplica la sección [sustituciones] de la lista en claro a los ficheros que
se le pasan: sustitución de texto exacta, de la cadena más larga a la más
corta. DESECHABLE: no se versiona.

    python sustituir.py <fichero> [<fichero> ...]
"""
import os
import pathlib
import sys


def sustituciones():
    pares, dentro = [], False
    lista = pathlib.Path(os.environ["ANONIMATO_LISTA"])
    for linea in lista.read_text(encoding="utf-8").splitlines():
        if linea.strip().startswith("["):
            dentro = linea.strip() == "[sustituciones]"
        elif dentro and " => " in linea and not linea.lstrip().startswith("#"):
            vieja, nueva = linea.split(" => ", 1)
            if not nueva.startswith("("):
                pares.append((vieja, nueva))
    return sorted(pares, key=lambda par: -len(par[0]))


def main(argv):
    pares = sustituciones()
    for nombre in argv:
        ruta = pathlib.Path(nombre)
        crudo = ruta.read_bytes()
        con_crlf = b"\r\n" in crudo
        texto = crudo.decode("utf-8").replace("\r\n", "\n")
        cambios = 0
        for vieja, nueva in pares:
            cambios += texto.count(vieja)
            texto = texto.replace(vieja, nueva)
        if cambios:
            if con_crlf:
                texto = texto.replace("\n", "\r\n")
            ruta.write_bytes(texto.encode("utf-8"))
        print(f"{nombre}: {cambios} sustituciones")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

Córrelo sobre los ocho ficheros de `docs/` de la lista de «Ficheros» (no sobre
el notebook, que va en el paso 5):

```bash
python "$TEMP/anonimato/sustituir.py" docs/sp2-despliegue.md docs/sp3-operacion.md docs/superpowers/specs/2026-09-16-sp1-nucleo-imagen-design.md docs/superpowers/specs/2026-09-24-sp3-bot-n8n-design.md docs/superpowers/plans/2026-09-16-sp1-nucleo-imagen.md docs/superpowers/plans/2026-09-23-sp2-servidor-mcp.md docs/superpowers/plans/2026-09-24-sp3-bot-n8n.md docs/superpowers/plans/2026-09-26-sp4-combinacion-bayesiana.md
```

Esperado: una línea por fichero con su número de sustituciones, todas
mayores que cero. Revisa el resultado con `git diff --stat` y leyendo el
`git diff` entero: cada línea cambiada tiene que seguir teniendo sentido.

- [ ] **Paso 4: Lo que hay que redactar a mano**

Vuelve a correr el comprobador (`python "$TEMP/anonimato/donde.py" .`). Lo que
queda no se arregla con una sustitución ciega. Para cada línea, el criterio:

| Qué nombra la línea | Qué se escribe |
| :--- | :--- |
| la lista de contenedores del servidor con sus nombres (salida de `docker ps` copiada en la guía de despliegue) | se conservan las filas del proyecto (`copiloto-mcp`, `copiloto-bd`) y las demás se sustituyen por una sola fila «(los contenedores ajenos: no se tocan)»; los nombres sueltos en prosa pasan a `api-ajena` y `bd-ajena` |
| productos de la pila de mensajería del cliente, en prosa o en un comentario | «los contenedores ajenos», sin enumerarlos |
| la credencial de Telegram del cliente y la de pruebas anterior, con su nombre | «la credencial de Telegram del cliente», «una credencial de pruebas anterior» |
| la tabla «Credenciales y workflows» del manual de operación, que nombra las tres credenciales de Telegram del proyecto | la columna de la credencial pasa a los nombres neutros de la tarea 4: `bot-paciente`, `bot-profesional` y `bot-avisos` |
| el nombre de usuario de un bot del proyecto, en prosa | «el bot del paciente», «el bot del profesional», «el bot de pruebas y avisos» |
| el indicador del intérprete de órdenes del servidor | `usuario@vps` |
| un título de sección que nombra a un integrante («… de …») | «(la máquina de desarrollo)»; busca si algún enlace interno apunta al ancla del título viejo y corrígelo |
| los nombres del equipo y la filiación | «el equipo» |
| la cuenta propietaria del remoto en una URL de clonado | `<cuenta>`; y donde la guía diga que el repositorio es privado, «el repositorio» a secas |
| un identificador de red de Docker (12 hexadecimales) en una salida copiada | `<id-de-la-red>` |
| una ruta temporal de la máquina | `<carpeta-temporal>/…` |

No reescribas la prosa de `docs/superpowers/**` más allá del identificador.

- [ ] **Paso 5: La cabecera del notebook**

En `notebooks/eda_rsna.ipynb`, la primera celda (markdown) tiene una línea
con los nombres de los dos integrantes y la universidad. Sustituye esa línea
entera, dentro del JSON, por:

```json
    "El equipo · Proyecto Integrador\n",
```

Edita solo esa línea (con la herramienta de edición): el notebook tiene
imágenes incrustadas y no se reescribe entero. Comprueba que sigue siendo un
notebook válido:

```bash
python -c "import json; n = json.load(open('notebooks/eda_rsna.ipynb', encoding='utf-8')); print(len(n['cells']), n['cells'][0]['source'][:3])"
```

Esperado: el número de celdas de antes y las tres primeras líneas de la
cabecera, con la nueva.

- [ ] **Paso 6: El árbol, limpio**

Orden: `python "$TEMP/anonimato/donde.py" .`

Esperado: `limpio`.

Y con la herramienta que se publica, que además busca secretos:

Orden: `C:/venv-copiloto/Scripts/python.exe scripts/verificar_anonimato.py --raiz .`

Esperado: código de salida 0 y ningún hallazgo de ninguna clase.

- [ ] **Paso 7: La prueba que lo vigila**

Añade AL FINAL de `tests/test_anonimato.py` (después de
`test_la_cli_sin_lista_dice_que_variable_falta`, dejando dos líneas en
blanco):

```python
# --------------------------------------------------------------------------
# El arbol de verdad. Exige la anonimizacion hecha (tareas 1 a 6 del plan).
# --------------------------------------------------------------------------
def _por_fichero(hallazgos, que):
    """`fichero: N (lineas a, b, c)`, sin tokens ni secretos."""
    agrupados = {}
    for h in hallazgos:
        agrupados.setdefault(h["fichero"], []).append(h)
    lineas = []
    for fichero, suyos in sorted(agrupados.items()):
        donde = sorted({h["linea"] for h in suyos})
        corte = 12 if que == "huella" else None
        clases = sorted({h[que][:corte] for h in suyos})
        lineas.append(f"  {fichero}: {len(suyos)} "
                      f"(lineas {', '.join(map(str, donde))}; "
                      f"{que} {', '.join(clases)})")
    return lineas


def test_el_arbol_esta_limpio():
    huellas = va.huellas_de_la_lista(va.leer_huellas(HUELLAS))
    de_huella = va.buscar_huellas(RAIZ, huellas)
    de_secreto = va.buscar_secretos(RAIZ)
    if de_huella or de_secreto:
        ficheros = len({h["fichero"] for h in de_huella})
        pytest.fail("\n".join(
            [f"El arbol no se puede publicar: {len(de_huella)} huellas en "
             f"{ficheros} ficheros y {len(de_secreto)} secretos. La linea 0 "
             "es el nombre del fichero."]
            + _por_fichero(de_huella, "huella")
            + _por_fichero(de_secreto, "clase")), pytrace=False)
```

Sobre el árbol SIN anonimizar esta prueba fallaba así (se vio al escribir el
plan, y se repitió sobre `main` con SP5-B1 fusionado, que no añadió ninguna:
201 huellas en 27 ficheros, ningún secreto). Es la forma de su
salida: fichero, líneas y el principio de cada huella, nunca el token:

```
================================== FAILURES ===================================
__________________________ test_el_arbol_esta_limpio __________________________
El arbol no se puede publicar: 201 huellas en 27 ficheros y 0 secretos. La linea 0 es el nombre del fichero.
  docs/comparativa-corridas.md: 8 (lineas 70, 71, 72, 73, 74, 75, 76, 77; huella [retirado])
  docs/sp2-despliegue.md: 29 (lineas 107, 108, 144, 158, 165, 169, 178, 182, 266, 323, 332, 333, 366, 467, 484, 486, 489, 502, 520, 655, 716, 866, 1055, 1077, 1097, 1178, 1226; huella [retirado], [retirado], [retirado], [retirado], [retirado], [retirado], [retirado])
  docs/sp3-operacion.md: 14 (lineas 29, 114, 206, 354, 409, 460, 471, 494, 516, 559, 560, 561, 564, 586; huella [retirado], [retirado], [retirado], [retirado], [retirado], [retirado], [retirado])
  docs/superpowers/plans/2026-09-16-sp1-nucleo-imagen.md: 4 (lineas 16, 1432, 1433, 1519; huella [retirado])
  docs/superpowers/plans/2026-09-23-sp2-servidor-mcp.md: 4 (lineas 531, 532, 1265, 1298; huella [retirado])
  docs/superpowers/plans/2026-09-24-sp3-bot-n8n.md: 11 (lineas 34, 158, 180, 627, 652, 656, 669, 727, 913, 994, 1519; huella [retirado], [retirado])
  docs/superpowers/plans/2026-09-26-sp4-combinacion-bayesiana.md: 3 (lineas 82, 1611, 2483; huella [retirado], [retirado])
  docs/superpowers/specs/2026-09-16-sp1-nucleo-imagen-design.md: 7 (lineas 5, 46; huella [retirado], [retirado], [retirado], [retirado], [retirado], [retirado], [retirado])
  docs/superpowers/specs/2026-09-24-sp3-bot-n8n-design.md: 15 (lineas 73, 93, 112, 1048, 1049, 1050, 1052, 1053, 1054, 1058, 1059, 1150; huella [retirado], [retirado], [retirado], [retirado], [retirado], [retirado], [retirado], [retirado], [retirado])
  n8n/copiloto-mantenimiento.json: 9 (lineas 68, 96, 156, 184, 207, 243, 338, 339, 346; huella [retirado], [retirado], [retirado], [retirado])
  n8n/copiloto-paciente.json: 31 (lineas 23, 27, 62, 238, 286, 287, 313, 314, 338, 431, 432, 455, 721, 722, 788, 789, 855, 856, 904, 905, 953, 954, 1008, 1009, 1052, 1053, 1077, 1137, 1138, 1167, 1168; huella [retirado], [retirado], [retirado], [retirado], [retirado])
  n8n/copiloto-profesional.json: 27 (lineas 23, 27, 61, 262, 285, 309, 498, 499, 523, 524, 548, 549, 596, 597, 645, 646, 670, 671, 692, 693, 793, 815, 875, 876, 904, 905; huella [retirado], [retirado], [retirado], [retirado], [retirado])
  notebooks/eda_rsna.ipynb: 6 (lineas 11; huella [retirado], [retirado], [retirado], [retirado], [retirado], [retirado])
  pruebas/puntuaciones.py: 1 (lineas 37; huella [retirado])
  pruebas/reproducir_casos.py: 2 (lineas 61, 1387; huella [retirado])
  pruebas/seleccionar_casos.py: 1 (lineas 21; huella [retirado])
  pruebas/verificar_webhooks.py: 1 (lineas 54; huella [retirado])
  scripts/entrenar_local.py: 1 (lineas 5; huella [retirado])
  scripts/preparar_datos.py: 2 (lineas 5, 6; huella [retirado])
  servidor/docker-compose.yml: 5 (lineas 72, 82, 120, 123, 128; huella [retirado], [retirado])
  tests/conftest.py: 2 (lineas 10, 38; huella [retirado])
  tests/decidir.mjs: 1 (lineas 90; huella [retirado])
  tests/profesional.mjs: 2 (lineas 365, 1617; huella [retirado])
  tests/test_contrato_mcp.py: 2 (lineas 28, 121; huella [retirado])
  tests/test_flujo_paciente.py: 2 (lineas 457; huella [retirado], [retirado])
  tests/test_flujo_profesional.py: 6 (lineas 161, 164, 481, 486, 790; huella [retirado], [retirado], [retirado], [retirado])
  tests/test_mantenimiento.py: 5 (lineas 38, 39, 181, 501, 523; huella [retirado], [retirado], [retirado])
=========================== short test summary info ===========================
FAILED tests/test_anonimato.py::test_el_arbol_esta_limpio - Failed: El arbol ...
1 failed, 46 passed in 13.41s
```

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_anonimato.py -q`

Esperado: `47 passed`. Si falla, la salida dice qué fichero y qué líneas.
**No se toca la lista, ni `huellas.txt`, ni la prueba**: se quita la cadena
del fichero (pasos 3 a 5 de esta tarea) o, si el fichero es de código, se
vuelve a la tarea que lo dejó a medias.

Comprueba que la prueba **puede fallar**: escribe un token de la lista en una
línea de cualquier fichero versionado (por ejemplo al final de `README.md`),
corre la prueba, mira que falla nombrando el fichero y la línea **sin
imprimir el token**, y deshaz el cambio (`git checkout -- README.md`).

- [ ] **Paso 8: La suite**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest -q`

Esperado: ningún fallo. Esta tarea solo cambia documentación, un notebook y
una prueba nueva.

- [ ] **Paso 9: Borrar lo desechable y confirmar**

```bash
rm -rf "$TEMP/anonimato"
git status --short
```

Esperado: solo los ficheros de esta tarea. Tres commits:

```bash
git add docs/sp2-despliegue.md docs/sp3-operacion.md
git commit -m "docs(anonimato): las guías de despliegue y operación, sin identificadores" -m "Sustitución mecánica por marcadores y redacción neutra donde la frase nombraba contenedores, bots o cuentas ajenas al proyecto." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"

git add docs/superpowers notebooks/eda_rsna.ipynb
git commit -m "docs(anonimato): specs, planes y la cabecera del notebook, sin identificadores" -m "Solo se cambian los identificadores; la prosa de los specs y de los planes queda como estaba." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"

git add tests/test_anonimato.py
git commit -m "test(anonimato): el árbol versionado no lleva ninguna huella ni ningún secreto" -m "Entra la última: exige aplicadas las tareas 1 a 6." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
---

### Tarea 7: Los binarios, revisados a mano y declarados

La prueba de huellas recorre texto. Lo que no es texto —imágenes— solo se
puede revisar mirándolo, y el spec §6.1 pide que se haga una vez y se declare.
Esta tarea escribe la declaración y ata la lista de binarios a una prueba:
si alguien añade un binario nuevo, la prueba falla hasta que se revise y se
declare.

**Ficheros:**
- Crear: `tests/anonimato/README.md`
- Modificar: `tests/test_anonimato.py` (gana `BINARIOS_REVISADOS` y dos pruebas)

**Interfaces:**
- Consume: `verificar_anonimato.binarios(raiz) -> list[Path]` y
  `verificar_anonimato.ficheros_versionados(raiz)` (tarea 5); `PIL.Image`
  (pillow ya es dependencia del paquete).
- Produce: `tests/test_anonimato.py::BINARIOS_REVISADOS` (tupla de rutas
  relativas, con `/`), `test_los_binarios_versionados_son_los_revisados` y
  `test_los_png_no_llevan_metadatos_que_identifiquen`.

**Lo que ya se revisó (28-sep-2026), para no repetirlo a ciegas:** los seis
PNG de `docs/eda/` y las seis imágenes incrustadas en
`notebooks/eda_rsna.ipynb` se abrieron una a una. Son gráficos de datos
agregados del dataset público (distribución de clases, edad, proyección,
sexo, correlaciones, cajas por paciente); no llevan nombres, rutas, marcas de
agua ni pies. Sus metadatos PNG son solo `Software` (la versión de
matplotlib) y `dpi`. Los otros dos notebooks no tienen salidas. Las figuras
de `docs/validacion-semisintetica/` las genera
`scripts/validar_combinacion.py` y sus únicos metadatos son `Software` (la
versión de matplotlib, sin dirección), `dpi`, `Title` (el título de la
figura, con su rótulo) y `Description` (la huella SHA-256 del contenido de
`resultados_simulacion.json` con el que se dibujó). Se volvieron a leer, las
diez, después de la última corrida de SP5-B1.

- [ ] **Paso 1: Escribir las pruebas**

Añade a `tests/test_anonimato.py`, detrás de los imports, la lista:

```python
# Los binarios versionados, revisados A MANO uno a uno (tests/anonimato/README.md).
# Un binario nuevo hace fallar la prueba hasta que alguien lo abre, lo mira y
# lo añade aquí y a la declaración.
BINARIOS_REVISADOS = (
    "docs/eda/01_distribucion_clases.png",
    "docs/eda/02_edad_y_atipicos.png",
    "docs/eda/03_vista_confusor.png",
    "docs/eda/04_sexo.png",
    "docs/eda/05_correlaciones.png",
    "docs/eda/06_cajas.png",
    "docs/validacion-semisintetica/contencion_rejilla.png",
    "docs/validacion-semisintetica/fiabilidad_0a.png",
    "docs/validacion-semisintetica/fiabilidad_r1-000_r0-030.png",
    "docs/validacion-semisintetica/fiabilidad_r1-000_r0-060.png",
    "docs/validacion-semisintetica/fiabilidad_r1-030_r0-000.png",
    "docs/validacion-semisintetica/fiabilidad_r1-030_r0-030.png",
    "docs/validacion-semisintetica/fiabilidad_r1-060_r0-000.png",
    "docs/validacion-semisintetica/fiabilidad_r1-060_r0-060.png",
    "docs/validacion-semisintetica/horquilla_por_celda.png",
    "docs/validacion-semisintetica/pendiente_rejilla.png",
)
METADATOS_PERMITIDOS = {"Software", "dpi", "Title", "Description"}
```

y al final del fichero:

```python
# --------------------------------------------------------------------------
# Lo que no es texto: revisado a mano y declarado
# --------------------------------------------------------------------------
def test_los_binarios_versionados_son_los_revisados():
    """Lo que no es texto no lo recorre la prueba de huellas: se mira a mano y
    se declara. Si esta prueba falla, hay un binario que nadie ha mirado."""
    hallados = sorted(p.relative_to(RAIZ).as_posix() for p in va.binarios(RAIZ))
    assert hallados == sorted(BINARIOS_REVISADOS)


def test_los_png_no_llevan_metadatos_que_identifiquen():
    from PIL import Image
    huellas = va.huellas_de_la_lista(va.leer_huellas(HUELLAS))
    for nombre in BINARIOS_REVISADOS:
        with Image.open(RAIZ / nombre) as imagen:
            assert imagen.format == "PNG", nombre
            assert set(imagen.info) <= METADATOS_PERMITIDOS, (nombre, sorted(imagen.info))
            texto = " ".join(str(v) for v in imagen.info.values())
        assert not {va.huella(t) for t in va.tokens(texto)} & huellas, nombre
```

`va` (el script cargado como módulo), `RAIZ` y `HUELLAS` son los nombres que
la tarea 5 dejó en la cabecera de `tests/test_anonimato.py`. Si `va.binarios`
devuelve rutas relativas en vez de absolutas, quita el `relative_to`: lo que
se compara son rutas relativas a la raíz, con `/`.

- [ ] **Paso 2: Correrlas**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_anonimato.py -q`

Esperado: todo en verde. (Estas dos pruebas son de caracterización: atan lo
que ya se revisó. Para verlas fallar, añade un PNG cualquiera con `git add`
sin confirmar, corre la primera, mira que falla nombrándolo y quítalo con
`git rm --cached` y bórralo.)

Si la primera falla porque la lista no coincide con lo que hay —por ejemplo
porque el plan SP5-B1 cambió el nombre de alguna figura—, **no edites la
lista sin mirar**: abre cada PNG que sobre o falte, comprueba que no lleva
nada que identifique y entonces corrige la lista y la declaración.

- [ ] **Paso 3: La declaración**

Crea `tests/anonimato/README.md`:

```markdown
# Anonimato del repositorio

Este repositorio no lleva ninguna cadena que identifique a un cliente, a una
empresa, a una máquina ni a personas, ni ningún secreto. Lo vigilan dos
comprobaciones.

## `tests/test_anonimato.py` (en la suite, siempre)

Tokeniza cada fichero de texto versionado —minúsculas, sin tildes, partición
por cualquier carácter que no sea `[a-z0-9]`— y falla si el SHA-256 de algún
token está en `huellas.txt`. Antes de tokenizar quita las tiradas de 120 o más
caracteres de base64 (las imágenes incrustadas en los notebooks), que
producirían tokens al azar.

`huellas.txt` lleva una huella por línea. **La lista de lo prohibido no está
en el repositorio**: solo sus huellas. Una de ellas es la del centinela
público `centinelaanonimato7f3a`, con el que la prueba se comprueba a sí
misma: lo escribe en un fichero temporal y exige detectarlo.

No hay lista blanca. Lo que se conserva —un huso horario, identificadores
opacos de los webhooks, números de chat inventados, una IP del rango de
documentación— se conserva porque no está en la lista, no porque se exceptúe.

## `scripts/verificar_anonimato.py` (antes de publicar)

Repite la búsqueda de huellas sobre cualquier árbol y añade la de secretos
(tokens de bot, claves de API, contraseñas en URL, ficheros de claves) y la
de los metadatos de un commit (autor, quien confirma y mensaje):

    python scripts/verificar_anonimato.py --raiz <árbol> --commit HEAD --un-solo-commit

Sus hallazgos dicen fichero, línea y huella o clase: nunca el token ni el
secreto.

## Cómo se regeneran las huellas

Quien mantiene la lista en claro, fuera del repositorio:

    ANONIMATO_LISTA=<lista en claro> python scripts/verificar_anonimato.py --regenerar

## Lo que no es texto: revisión manual

La prueba de huellas no puede leer imágenes. Se revisaron a mano, una a una:

| Qué | Cuándo | Qué se comprobó |
| :--- | :--- | :--- |
| los 6 PNG de `docs/eda/` | 28-sep-2026 | contenido (gráficos de datos agregados del dataset público, sin nombres, rutas, marcas de agua ni pies) y metadatos (solo `Software` y `dpi`) |
| las 6 imágenes incrustadas en `notebooks/eda_rsna.ipynb` | 28-sep-2026 | son las mismas seis figuras; mismos metadatos |
| los metadatos de los tres notebooks | 28-sep-2026 | solo `kernelspec`, `language_info` y, en uno, el nombre del propio notebook; los otros dos notebooks no tienen salidas |
| las figuras de `docs/validacion-semisintetica/` | al generarlas | las dibuja `scripts/validar_combinacion.py` desde `resultados_simulacion.json`; su título lleva el rótulo «simulación semisintética»; metadatos `Software`, `dpi`, `Title` y `Description` (la huella del JSON de resultados con el que se dibujó cada una) |

La lista de binarios revisados está en `tests/test_anonimato.py`
(`BINARIOS_REVISADOS`): un binario nuevo hace fallar la suite hasta que se
revisa y se declara aquí.

## Lo que esto no protege

Quita cadenas; no oculta la autoría a quien llegue al repositorio por otro
camino. Y no revisa el historial: por eso el repositorio que se publica es
nuevo y de un solo commit.

**Una huella no es un secreto.** El SHA-256 de un token corto —un nombre, una
palabra, un dominio de pocas letras— se adivina probando candidatos: quien
tenga `huellas.txt` y un diccionario recupera buena parte de la lista. Por
eso la lista completa de huellas vive **solo en el repositorio de
desarrollo**, que es privado. En el repositorio que se publica,
`huellas.txt` lleva únicamente la huella del centinela: la prueba sigue
comprobando que el mecanismo funciona, y la comprobación de verdad se hace
antes de publicar, con `scripts/verificar_anonimato.py` y las huellas del
repositorio de desarrollo.
```

- [ ] **Paso 4: La declaración también pasa la prueba**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_anonimato.py -q`

Esperado: todo en verde (la declaración es un fichero de texto versionable y
la recorre la prueba del árbol).

- [ ] **Paso 5: Commit**

```bash
git add tests/anonimato/README.md tests/test_anonimato.py
git commit -m "test(anonimato): los binarios versionados son los revisados a mano, y la declaración" -m "La prueba de huellas recorre texto; las imágenes se revisaron una a una y se declaran. Un binario nuevo hace fallar la suite hasta que alguien lo mira." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 8: La suite entera y lo que el equipo tiene que hacer fuera del repositorio

**Ficheros:**
- Modificar: `README.md` (una sección «Variables de entorno» o la que ya haga ese papel)
- Modificar: `docs/sp3-operacion.md` (una sección nueva al final: «Después de la anonimización»)

**Interfaces:**
- Consume: todo lo anterior.
- Produce: nada de código.

- [ ] **Paso 1: La suite entera, en los dos escenarios**

Primero como la correrá quien clone el repositorio público, sin nada puesto.
En Git Bash:

```bash
env -u RSNA_RAIZ -u N8N_URL -u COPILOTO_BD_DSN -u TELEGRAM_SECRET_PRUEBA -u TELEGRAM_TOKEN_PROFESIONAL C:/venv-copiloto/Scripts/python.exe -m pytest -q -rs
```

Esperado: ningún fallo ni error. Lee la lista de pruebas saltadas (`-rs`):
cada una dice qué se queda sin verificar y qué variable hace falta.

Después, como la corre el equipo, con el dataset:

```bash
RSNA_RAIZ="<RSNA_RAIZ>" C:/venv-copiloto/Scripts/python.exe -m pytest -q -rs
```

Esperado: ningún fallo ni error, y menos pruebas saltadas que en la corrida
anterior (las que necesitan el dataset ahora corren).

Y las de `node`:

```bash
node tests/decidir.mjs && node tests/profesional.mjs && node tests/mantenimiento.mjs && node tests/formulario.mjs
```

Esperado: las cuatro terminan con su línea de `OK` y código 0.

- [ ] **Paso 2: El README dice qué variables hacen falta**

Añade a `README.md`, detrás de la sección «Requisitos», esta sección:

```markdown
## Variables de entorno

Ningún valor que identifique una instalación está escrito en el repositorio:
se pasa por el entorno. Sin ellas, lo que las necesita se detiene con un
mensaje o, en la suite, se salta diciendo qué se queda sin verificar.

| Variable | Quién la necesita | Qué es |
| :--- | :--- | :--- |
| `RSNA_RAIZ` | `scripts/preparar_sesion.py`, `pruebas/seleccionar_casos.py`, `pruebas/puntuaciones.py` (solo si no hay caché) y las pruebas que leen placas | la raíz del dataset preparado (`crudo/`, `png/`, `manifiestos/`) |
| `N8N_URL` | `pruebas/reproducir_casos.py` con bots, `pruebas/verificar_webhooks.py` y las pruebas conducidas | la dirección base de n8n, p. ej. `https://n8n.ejemplo.test` |
| `RED_N8N` | `servidor/docker-compose.yml` | el nombre de la red externa de Docker que comparte n8n; obligatoria |
| `COPILOTO_URL`, `COPILOTO_BD_DSN`, `TELEGRAM_SECRET_PRUEBA`, `TELEGRAM_TOKEN_PROFESIONAL`, `CHAT_SUBIDA_PLACAS` | el arnés y las pruebas conducidas | las describe la cabecera de `pruebas/reproducir_casos.py` |

Los workflows de `n8n/` llevan **marcadores** en vez de la dirección y de los
identificadores de las credenciales: `scripts/marcadores_n8n.py` los
sustituye por los valores de `n8n/valores.local.json` (que no se versiona;
`n8n/valores.ejemplo.json` dice qué claves lleva) antes de importarlos.
```

- [ ] **Paso 3: Lo que cambia para quien opera lo desplegado**

Añade al final de `docs/sp3-operacion.md` esta sección:

````markdown
## Después de la anonimización: lo que hay que hacer una vez

El repositorio dejó de llevar escritos la dirección de n8n, el nombre de la
red y los identificadores de las credenciales. Lo desplegado **sigue
funcionando como está**; estos pasos hacen falta la próxima vez que se
despliegue o se opere desde el repositorio, y se hacen fuera de las fechas
de la sesión con el médico.

1. **En el servidor, antes del próximo despliegue:** `RED_N8N` en
   `servidor/.env`, y el primer redespliegue, que vuelve a crear los dos
   contenedores (la clave de la red cambió de nombre en el compose) sin tocar
   el volumen de la base. El procedimiento, orden a orden, está en
   `docs/sp2-despliegue.md`, apartado «El primer redespliegue con `RED_N8N`
   obligatoria»: se sigue ese, no se improvisa otro.

2. **En la máquina de desarrollo:** la tarea programada diaria que corre
   `pruebas/verificar_webhooks.py` necesita `N8N_URL` en su entorno. Sin
   ella el script no comprueba nada: lo dice, avisa por el canal de avisos si
   lo tiene configurado, y devuelve un código de error.

       [Environment]::SetEnvironmentVariable('N8N_URL', '<dirección base de n8n>', 'User')

3. **En la máquina de desarrollo:** crear `n8n/valores.local.json` a partir
   de `n8n/valores.ejemplo.json`, con los valores reales. Ese fichero está
   ignorado por git. Cómo se usa, en el §7 de este manual, «Los marcadores:
   del repositorio a n8n, y de n8n al repositorio».

4. **Para correr la suite completa**, `RSNA_RAIZ` (y `N8N_URL`, con los
   secretos de siempre, para las pruebas conducidas). Un salto se ve verde:
   conviene correr con `-rs` y leer qué se saltó.
````

- [ ] **Paso 4: La documentación nueva también pasa la prueba**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_anonimato.py -q`

Esperado: todo en verde.

- [ ] **Paso 5: Commit**

```bash
git add README.md docs/sp3-operacion.md
git commit -m "docs(anonimato): las variables de entorno y lo que el equipo hace una vez en el servidor" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Autorrevisión del plan (hecha al escribirlo)

**Cobertura del inventario del spec §6.1.**

| Fila del inventario | Tarea |
| :--- | :--- |
| dominio de n8n, valor por defecto en pruebas y arnés | 1 |
| dominio de n8n, URL de las sondas del workflow de mantenimiento | 4 |
| dominio de n8n, notas de los workflows, guías, spec y plan de SP3 | 4 (notas), 6 (documentos) |
| red Docker del cliente | 3 |
| contenedores, pila de mensajería y bots del cliente | 3 (comentario del compose), 4 (pruebas y workflows), 6 (documentos) |
| nombres del equipo y filiación personal | 6 |
| usuario de Windows en rutas absolutas | 2 (código), 6 (documentos) |
| ciudad en el huso horario | se conserva (restricción 3) |
| cuenta propietaria del remoto | 6 |
| proveedor y ciudad del VPS, `chat_id`, correos | no hay ninguno real en el árbol (inventario del 28-sep); el indicador del intérprete del servidor, 6 |
| `docs/superpowers/**` | 6 |
| `tests/test_anonimato.py`, huellas y centinela | 5, 6 |
| `scripts/verificar_anonimato.py`, huellas y secretos, árbol y commit | 5 |
| binarios revisados a mano y declarados | 7 |

**Lo que el inventario del spec no nombraba y este plan trata:** los ids de
las credenciales de n8n y los nombres de los bots del proyecto (tarea 4); los
docstrings de `scripts/entrenar_local.py` y `scripts/preparar_datos.py` y la
tabla «Procedencia» que genera `scripts/comparar_corridas.py` (tarea 2); un
identificador de red copiado en la guía (tarea 6).

**Lo que este plan no hace:** crear ni publicar el repositorio nuevo, correr
`scripts/verificar_anonimato.py` sobre él y sobre su commit, ni decidir si el
README enlaza los videos (plan SP5-C). Tampoco toca nada desplegado.
