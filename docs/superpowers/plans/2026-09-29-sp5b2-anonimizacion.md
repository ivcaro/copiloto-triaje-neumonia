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
**huella SHA-256 por token**, y la prueba tokeniza cada fichero de texto que
se publicaría y falla si alguna huella aparece. Antes de publicar,
`scripts/verificar_anonimato.py` repite esa comprobación sobre el árbol del
repositorio nuevo, sobre su único commit (contenido, autor, mensaje) y sobre
los nombres de sus ramas, y busca además patrones de secretos.

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
| `docs/**`, `notebooks/eda_rsna.ipynb`, `tests/mantenimiento.mjs`, lo que quede; `tests/test_anonimato.py`, `tests/anonimato/huellas.txt` | 6 | sustitución mecánica, el repaso a mano y la prueba del árbol limpio |
| `tests/anonimato/README.md`, `tests/test_anonimato.py` | 7 | declaración de la revisión manual de los binarios, y lo que la vigilancia no ve |
| `README.md`, `docs/sp3-operacion.md` | 8 | lo que el equipo tiene que hacer en el servidor |
| los de las tareas 1 a 8 que tocó la revisión final | 9 | la tanda de la revisión final |
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

    assert vw.main([]) == 1

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

    assert vw.main([]) == 1

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


# --------------------------------------------------------------------------
# Sin consola no se pide nada por teclado
# --------------------------------------------------------------------------
class _Entrada(io.StringIO):
    """Un `sys.stdin` de pega que dice si es una consola."""

    def __init__(self, consola):
        super().__init__("")
        self._consola = consola

    def isatty(self):
        return self._consola


def test_sin_consola_y_sin_token_el_vigilante_no_espera_y_lo_cuenta(monkeypatch, capsys):
    """Sin consola (una entrada redirigida, un proceso sin consola) no hay a
    quien pedirle el token: `getpass` se quedaria esperando un teclado que
    nadie va a usar. El bot sin token se cuenta como problema."""
    _main_que_no_toca_nada(monkeypatch)       # sin tokens, sin canal, sin red
    monkeypatch.setattr(vw, "BASE_N8N", BASE)

    def pide(*a, **k):
        raise AssertionError("pidió el token por teclado sin consola")

    monkeypatch.setattr(vw.getpass, "getpass", pide)
    monkeypatch.setattr(vw.sys, "stdin", _Entrada(consola=False))
    monkeypatch.setattr(vw, "_memoria_leer", lambda: {})
    monkeypatch.setattr(vw, "_memoria_escribir", lambda datos: None)

    assert vw.main([]) == 1

    salida = capsys.readouterr().out
    for quien in ("paciente", "profesional"):
        assert f"{quien}: sin token, no se puede comprobar. SALTADO" in salida
    assert "2 cosas que arreglar." in salida


def test_con_sin_teclado_no_se_pide_nada_aunque_haya_consola(monkeypatch, capsys):
    """§5 del manual: la tarea programada SI tiene consola -el Programador de
    tareas se la da a python.exe aunque nadie la vea-, asi que mirar si hay
    consola no basta: `getpass` se quedaria esperando en ella, sin avisar, y la
    tarea no volveria a correr. Con `--sin-teclado`, `main()` no pide nada: el
    bot sin token cuenta como problema, y el aviso sale."""
    _main_que_no_toca_nada(monkeypatch)       # sin tokens y sin red
    enviados = _canal_de_avisos_falso(monkeypatch)
    monkeypatch.setattr(vw, "BASE_N8N", BASE)
    monkeypatch.setattr(vw, "_hay_consola", lambda: True)

    def pide(*a, **k):
        raise AssertionError("pidió el token por teclado con --sin-teclado")

    monkeypatch.setattr(vw.getpass, "getpass", pide)
    monkeypatch.setattr(vw, "_memoria_leer", lambda: {})
    monkeypatch.setattr(vw, "_memoria_escribir", lambda datos: None)

    assert vw.main(["--sin-teclado"]) == 1

    salida = capsys.readouterr().out
    for quien, variable in (("paciente", "TELEGRAM_TOKEN_PACIENTE"),
                            ("profesional", "TELEGRAM_TOKEN_PROFESIONAL")):
        assert f"{quien}: sin token, no se puede comprobar. SALTADO" in salida
        assert f"falta su token en {variable}" in enviados["cuerpo"]["text"]
    assert "2 cosas que arreglar." in salida
    assert "aviso por Telegram: enviado." in salida


def test_sin_la_opcion_y_con_consola_se_sigue_pidiendo_el_token(monkeypatch):
    """La misma corrida sin `--sin-teclado`: con consola, el token se pide por
    teclado, como siempre. Es lo que prueba que la que lo cambia es la
    opcion."""
    _main_que_no_toca_nada(monkeypatch)
    monkeypatch.setattr(vw, "BASE_N8N", BASE)
    monkeypatch.setattr(vw, "_hay_consola", lambda: True)
    pedidos = []
    monkeypatch.setattr(vw.getpass, "getpass",
                        lambda prompt="": pedidos.append(prompt) or "")
    monkeypatch.setattr(vw, "_memoria_leer", lambda: {})
    monkeypatch.setattr(vw, "_memoria_escribir", lambda datos: None)

    assert vw.main([]) == 1
    assert len(pedidos) == 2


def test_la_tarea_del_manual_lanza_el_vigilante_con_sin_teclado():
    """El manual y el script no pueden divergir: la orden que monta la tarea
    programada (§5 del manual) lanza este script con `--sin-teclado`, y el
    script tiene esa opcion (una que no tuviera, la rechazaria)."""
    manual = (RAIZ / "docs" / "sp3-operacion.md").read_text(encoding="utf-8")
    acciones = [linea for linea in manual.splitlines()
                if "New-ScheduledTaskAction" in linea]
    assert len(acciones) == 1, "una sola orden monta la accion de la tarea"
    argumento = re.search(r"-Argument '([^']*)'", acciones[0])
    assert argumento, "la accion de la tarea no lleva -Argument"
    script, *opciones = argumento.group(1).split()
    assert script.replace("\\", "/") == "pruebas/verificar_webhooks.py"
    assert "--sin-teclado" in opciones
    assert vw.leer_opciones(opciones).sin_teclado is True


def test_la_entrada_desde_el_dispositivo_nulo_no_es_una_consola(monkeypatch):
    """En Windows, una entrada redirigida desde `NUL` dice que es una
    consola (`isatty()` da True: es un dispositivo de caracteres), y `getpass`
    se quedaba esperando igual. Una tarea lanzada con `< NUL` no tiene a nadie
    al teclado."""
    with open(os.devnull, encoding="utf-8") as nulo:
        monkeypatch.setattr(vw.sys, "stdin", nulo)
        assert vw._hay_consola() is False


def test_con_consola_y_sin_token_el_vigilante_lo_pide_por_teclado(monkeypatch):
    """A mano, con consola, no cambia nada: el token se pide por teclado."""
    _main_que_no_toca_nada(monkeypatch)
    monkeypatch.setattr(vw, "BASE_N8N", BASE)
    pedidos, usados = [], []
    monkeypatch.setattr(vw.getpass, "getpass",
                        lambda prompt="": pedidos.append(prompt) or " tok-de-teclado ")
    monkeypatch.setattr(vw.sys, "stdin", _Entrada(consola=True))

    def pedir(token, metodo):
        usados.append(token)
        return False, "respuesta de pega"

    monkeypatch.setattr(vw, "pedir_api", pedir)
    monkeypatch.setattr(vw, "_memoria_leer", lambda: {})
    monkeypatch.setattr(vw, "_memoria_escribir", lambda datos: None)

    assert vw.main([]) == 1
    assert len(pedidos) == 2
    assert usados == ["tok-de-teclado", "tok-de-teclado"]


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

    assert modulo.main([]) == 1

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

    assert vw.main([]) == 1

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
de ningun despliegue. Sin ella, o mal puesta (sin esquema, con una ruta detras,
entre comillas...), el script no pide ningun token ni comprueba nada: dice que
falta o que esta mal, lo manda por Telegram si el canal de avisos esta puesto,
y devuelve 1. Mal puesta, compararla con lo que devuelve Telegram daria por mal
apuntado un webhook que esta bien.
```

(2) La línea 54 asigna `BASE_N8N` con un valor por defecto (patrón
`BASE_N8N = os.environ.get("N8N_URL", "https://…").rstrip("/")`). Sustitúyela por:

```python
# Sin valor por defecto, y sin fallar al importar: `tests/test_mantenimiento.py`
# importa este modulo para probar el diagnostico, y tiene que poder hacerlo en
# una maquina que no sabe de ningun n8n, o que la tiene mal puesta. Quien se
# niega a seguir es `main()`.
BASE_N8N, N8N_URL_MAL_PUESTA = _base_de_n8n()

# Donde se pone, dicho para la tarea programada: una tarea de Windows no tiene
# variables propias, lee las del perfil del usuario que la corre.
DONDE_SE_PONE = (
    "en el entorno de quien corre el script; si lo corre la tarea programada, "
    "con `setx N8N_URL` en el perfil del usuario que la corre (manual de "
    "operación, §5, paso 2).")

SIN_N8N_URL = (
    "Falta N8N_URL: sin ella no se sabe en qué URL tendría que estar "
    "entregando Telegram, y no se ha comprobado ningún webhook.\n"
    "   Qué hacer: pon en N8N_URL la URL base del n8n que sirve a los dos bots "
    "(por ejemplo https://n8n.ejemplo.test), " + DONDE_SE_PONE)

# El motivo, y nunca el valor: el mensaje viaja por Telegram.
N8N_URL_MAL = (
    "N8N_URL está mal puesta ({motivo}): con ella no se sabe en qué URL "
    "tendría que estar entregando Telegram, y no se ha comprobado ningún "
    "webhook.\n"
    "   Qué hacer: pon en N8N_URL solo la URL base del n8n que sirve a los dos "
    "bots, con su esquema y sin nada detrás del host (por ejemplo "
    "https://n8n.ejemplo.test), " + DONDE_SE_PONE)
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


def _hay_consola() -> bool:
    """Si hay una consola a la que pedirle el token. Sin ella (una entrada
    redirigida, un proceso sin consola) `getpass` se quedaria esperando un
    token que nadie va a teclear. Que la haya no quiere decir que haya alguien
    delante: la tarea programada tiene una que nadie ve, y por eso va con
    `--sin-teclado`.

    En Windows `isatty()` no basta: una entrada redirigida desde `NUL` es un
    dispositivo de caracteres y dice que si. Alli se pregunta ademas a la
    consola por su modo, que solo lo tiene una consola de verdad."""
    try:
        if sys.stdin is None or not sys.stdin.isatty():
            return False
    except (AttributeError, ValueError, OSError):
        return False
    if os.name != "nt":
        return True
    try:
        import msvcrt
        manejador = msvcrt.get_osfhandle(sys.stdin.fileno())
    except (AttributeError, ValueError, OSError):
        # una entrada sin descriptor que dice ser una consola: se le cree
        return True
    import ctypes
    modo = ctypes.c_ulong()
    return bool(ctypes.windll.kernel32.GetConsoleMode(
        ctypes.c_void_p(manejador), ctypes.byref(modo)))


def leer_opciones(argv=None):
    """Las opciones de la linea de ordenes (con `argv` None, las de
    `sys.argv`). Se leen en `main()` y nunca al importar: este modulo lo
    importan las pruebas, con las opciones de pytest en `sys.argv`. Sin
    abreviaturas: la orden de la tarea tiene que llevar la opcion entera."""
    p = argparse.ArgumentParser(
        allow_abbrev=False,
        description="Mira que Telegram siga entregando los dos bots donde debe: "
                    "la mitad del §16 que no cabe dentro de n8n.")
    p.add_argument(
        "--sin-teclado", action="store_true",
        help="no pedir nunca un token por teclado: el bot sin token en el "
             "entorno se cuenta como problema. Es como lo lanza la tarea "
             "programada (§5 del manual de operacion), que tiene una consola "
             "que nadie ve")
    return p.parse_args(argv)


def main(argv=None) -> int:
    opciones = leer_opciones(argv)
    if not BASE_N8N:
        # Antes de pedir ningun token y de tocar la memoria: sin la base no hay
        # con que comparar, y una lectura a medias borraria la de ayer. Mal
        # puesta es lo mismo: compararla daria por mal apuntados los dos
        # webhooks y mandaria registrarlos en una direccion equivocada.
        mensaje = (N8N_URL_MAL.format(motivo=N8N_URL_MAL_PUESTA)
                   if N8N_URL_MAL_PUESTA else SIN_N8N_URL)
        print(mensaje)
        avisar_al_equipo([mensaje], comprobado=False)
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


@pytest.mark.parametrize("valor", [
    "n8n.inventado.test", "https://n8n.inventado.test/webhook/copiloto-paciente",
    '"https://n8n.inventado.test"', "https://n8n. inventado.test", "/"])
def test_con_N8N_URL_mal_puesta_el_fijador_falla_diciendo_por_que(monkeypatch, valor):
    """Mal puesta no se SALTA: un salto se ve verde, y quien la puso quiere
    correr las pruebas conducidas. Falla, diciendo por que, sin repetir el
    valor y sin salir a la red. Se recogen las dos excepciones: si el fijador
    se saltara, `pytest.raises` no lo recogeria, el salto se propagaria y esta
    misma prueba saldria saltada, en verde."""
    monkeypatch.setenv("N8N_URL", valor)
    _sin_red(monkeypatch)

    try:
        fijador()
    except pytest.skip.Exception:
        raise AssertionError("se saltó en vez de fallar") from None
    except pytest.fail.Exception as fallo:
        motivo = str(fallo)
    else:
        raise AssertionError("el fijador siguió adelante con N8N_URL mal puesta")

    assert "N8N_URL" in motivo and "mal puesta" in motivo
    assert "inventado" not in motivo


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

    Sin `N8N_URL` la prueba que lo pide se salta: no hay n8n por defecto. Mal
    puesta, FALLA diciendo por que: un salto se ve verde, y quien la puso
    quiere correr las pruebas conducidas.
    """
    base = os.environ.get("N8N_URL", "").strip()
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
    assert base_de_n8n() == "https://otro.ejemplo.test"
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


@pytest.mark.parametrize("valor", [
    "n8n.inventado.test", "https://n8n.inventado.test/webhook/copiloto-paciente",
    '"https://n8n.inventado.test"', "https://n8n. inventado.test", "/"])
def test_con_los_bots_y_N8N_URL_mal_puesta_el_arnes_sale_antes_de_empezar(
        valor, monkeypatch, tmp_path):
    """Mal puesta, el primer POST moria con «unknown url type» despues de abrir
    la base y de dar de alta el chat de pruebas. Ahora se detiene donde la
    ausente: antes del copiloto, de elegir los casos y de abrir la base. Y el
    mensaje no repite el valor."""
    rc, _ = _entorno_con_bots(monkeypatch, tmp_path)
    monkeypatch.setenv("N8N_URL", valor)

    with pytest.raises(SystemExit) as salida:
        rc.main()

    assert "N8N_URL" in str(salida.value) and "mal puesta" in str(salida.value)
    assert "inventado" not in str(salida.value)
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
                                 falta o esta mal puesta (sin esquema, con
                                 una ruta detras...), el arnes sale
                                 diciendolo antes de empezar. Con --sin-bots
                                 no hace falta
```

(2) Justo antes de `def main() -> int:` (línea 1334), añade:

```python
def base_de_n8n() -> str:
    """La URL base del n8n de los bots. Sale de `N8N_URL` y de ningun otro
    sitio: el repositorio no lleva la de ningun despliegue, y un valor por
    defecto mandaria las conversaciones de prueba a un n8n que nadie eligio.
    Mal puesta tambien se detiene: si no, el primer mensaje moria con una
    traza despues de abrir la base y de dar de alta el chat de pruebas."""
    base = os.environ.get("N8N_URL", "").strip()
    if not base:
        raise SystemExit(
            "falta N8N_URL: con los bots el arnés conduce las conversaciones "
            "contra un n8n, y no hay ninguno por defecto.\n"
            "Pon en N8N_URL la URL base del n8n que sirve a los dos bots (por "
            "ejemplo https://n8n.ejemplo.test), o corre con --sin-bots.")
    try:
        return url_base_n8n(base)
    except ValueError as e:
        # el motivo, y no el valor
        raise SystemExit(
            f"N8N_URL está mal puesta ({e}): con los bots el arnés conduce "
            "las conversaciones contra esa dirección.\n"
            "Pon en N8N_URL solo la URL base del n8n que sirve a los dos bots "
            "(por ejemplo https://n8n.ejemplo.test), o corre con --sin-bots."
        ) from None
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
| `RSNA_RAIZ` apunta a una carpeta que no tiene el dataset | con pesos y caché, falla `test_todos_los_ficheros_existen` | con pesos, 8 ERROR con `FileNotFoundError` y la ruta que falta; sin pesos, 6 (las dos del recorte se saltan antes) |

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


def test_raiz_rsna_no_mira_el_disco(tmp_path, monkeypatch):
    """Lo comprueba quien va a leer el dataset, antes de tocar nada."""
    monkeypatch.setenv("RSNA_RAIZ", str(tmp_path / "no-existe"))
    assert raiz_rsna() == tmp_path / "no-existe"


# --------------------------------------------------------------------------
# `N8N_URL`: la escribe una persona, y mal puesta no puede pasar por buena
# --------------------------------------------------------------------------
@pytest.mark.parametrize("valor, base", [
    ("https://n8n.inventado.test", "https://n8n.inventado.test"),
    ("https://n8n.inventado.test/", "https://n8n.inventado.test"),
    ("  https://N8N.Inventado.TEST/  ", "https://n8n.inventado.test"),
    ("HTTPS://n8n.inventado.test", "https://n8n.inventado.test"),
    ("http://localhost:5678", "http://localhost:5678"),
])
def test_url_base_n8n_devuelve_la_base(valor, base):
    assert url_base_n8n(valor) == base


@pytest.mark.parametrize("valor, dice", [
    ("", "vacia"),
    ("n8n.inventado.test", "esquema"),
    ("n8n.inventado.test:5678", "esquema"),
    ("ftp://n8n.inventado.test", "esquema"),
    ("/", "esquema"),
    ("https://", "host"),
    ("https:/n8n.inventado.test", "host"),
    # lo que sale de copiar la barra del navegador
    ("https://n8n.inventado.test/webhook/copiloto-paciente", "ruta"),
    ("https://n8n.inventado.test/n8n/", "ruta"),
    ("https://n8n.inventado.test?x=1", "consulta"),
    ("https://n8n.inventado.test#arriba", "fragmento"),
    ('"https://n8n.inventado.test"', "comillas"),
    ("'https://n8n.inventado.test'", "comillas"),
    ("https://n8n. inventado.test", "blancos"),
    ("https://n8n.inventado.test/\tx", "blancos"),
    ("https://alguien@n8n.inventado.test", "usuario"),
    ("https://n8n.inventado.test:puerto", "puerto"),
])
def test_url_base_n8n_rechaza_lo_que_no_es_una_url_base(valor, dice):
    with pytest.raises(ValueError, match=dice) as e:
        url_base_n8n(valor)
    # el motivo no repite el valor: acaba en la consola, en un log o en Telegram
    assert "inventado" not in str(e.value)
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
import re
import urllib.parse
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
    carpeta exista: lo comprueba quien la usa, antes de tocar nada (la
    seleccion de casos mira la carpeta de los DICOM; la fase de elegir de la
    sesion, los PNG).
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
    # los tres grupos de pruebas que piden los pesos, y de dónde salen
    for grupo in ("la selección de casos", "las dos pruebas del recorte",
                  "del bot del profesional que suben una placa"):
        assert grupo in " ".join(mensaje.split()), grupo
    assert "README" in mensaje


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
    crudo = tmp_path / "crudo" / "stage_2_train_images"
    crudo.mkdir(parents=True)   # la carpeta tiene que existir; los DICOM, no
    casos = con_puntuaciones_de_mentira.seleccionar(n_por_perfil=2)
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


def test_con_rsna_raiz_en_otra_carpeta_seleccionar_se_detiene_al_principio(
        tmp_path, monkeypatch):
    """Una `RSNA_RAIZ` que no es el dataset daba 45 rutas que no existen, y
    el arnes moria mas tarde, con una traza, despues de haber tocado cosas.
    Ahora se detiene al principio, antes de leer las puntuaciones, nombrando
    la variable y la carpeta que falta."""
    from pruebas import seleccionar_casos

    def no_se_llama():
        raise AssertionError("seleccionar() siguió sin mirar la carpeta")

    monkeypatch.setattr(seleccionar_casos, "puntuaciones_de_prueba", no_se_llama)
    monkeypatch.setenv("RSNA_RAIZ", str(tmp_path))
    with pytest.raises(SystemExit) as salida:
        seleccionar_casos.seleccionar(n_por_perfil=2)
    assert "RSNA_RAIZ" in str(salida.value)
    assert "stage_2_train_images" in str(salida.value)


def test_el_modulo_no_guarda_ninguna_ruta_del_dataset():
    from pruebas import seleccionar_casos
    assert not hasattr(seleccionar_casos, "RAIZ")
    assert not hasattr(seleccionar_casos, "CRUDO")


def test_lo_que_llega_al_dataset_se_importa_sin_rsna_raiz():
    """En un proceso aparte, porque en este ya estan importados. Van los cinco
    ficheros desde los que se llega a `raiz_rsna()`: los dos modulos que la
    llaman, los dos que los importan y el script de la sesion. Si alguno leyera
    la variable al importarse, las pruebas que lo importan darian error de
    coleccion en un clon limpio; y en la maquina de desarrollo, que tiene la
    variable puesta, no se veria."""
    import os
    import subprocess
    entorno = {k: v for k, v in os.environ.items() if k != "RSNA_RAIZ"}
    codigo = "\n".join((
        "import importlib.util",
        "import pruebas.puntuaciones, pruebas.seleccionar_casos",
        "import pruebas.reproducir_casos, pruebas.caracterizar_conjunto",
        "spec = importlib.util.spec_from_file_location(",
        "    'preparar_sesion', 'scripts/preparar_sesion.py')",
        "spec.loader.exec_module(importlib.util.module_from_spec(spec))",
        "print('importados')"))
    r = subprocess.run([sys.executable, "-B", "-c", codigo], cwd=REPO, env=entorno,
                       capture_output=True, text=True, timeout=300)
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
    por `UMBRAL` o de paso, ficheros que corren sin dataset. Y se comprueba al
    principio que apunta al dataset: si no, saldrian rutas que no existen, y
    quien las usa moriria mas tarde, con una traza, despues de haber tocado
    cosas.
    """
    crudo = raiz_rsna() / "crudo" / "stage_2_train_images"
    if not crudo.is_dir():
        raise SystemExit(
            f"RSNA_RAIZ no apunta al dataset preparado: no existe {crudo}, la "
            "carpeta de los DICOM. Pon en RSNA_RAIZ la carpeta que tiene dentro "
            "manifiestos/, png/ y crudo/stage_2_train_images/.")
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
            " comprobar la selección de casos, las dos pruebas del recorte de"
            " la razón de verosimilitud y las consultas conducidas del bot del"
            " profesional que suben una placa. Para verificarlo, copia los"
            " pesos a esa ruta (salen del entrenamiento: README, «Reproducir"
            " desde cero») y repite; la primera vez, sin caché, infiere sobre"
            " las 3 811 imágenes de prueba y tarda minutos.")
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
nueva; el valor no se escribe en ningún fichero del repositorio) y corre.
Definirla de forma permanente es de quien usa la máquina: quien ejecuta el
plan la pone solo delante de la orden (`RSNA_RAIZ="<RSNA_RAIZ>" …`):

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
- Modificar: `docs/sp2-despliegue.md` (18 ediciones, todas las de la red, y las que
  ponen al día lo que la guía decía de un solo contenedor sin estado)
- Modificar: `docs/sp3-operacion.md` (línea 586)
- Prueba: `tests/test_arrancar.py` (cinco pruebas nuevas al final, y `import re`)

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
# `--remove-orphans` o `ON_ERROR_STOP` no son ninguna de ellas. `remove` es el
# alias de `rm` (`docker volume remove`, `docker network remove`, `docker
# container remove`), y `rmi` borra una imagen.
PARAN_O_BORRAN = re.compile(
    r"(?<![\w-])(down|stop|kill|rm|remove|rmi|restart|pause|prune|disconnect)(?![\w-])")


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


_VALLA = re.compile(r"\s*(`{3,}|~{3,})")
_CITA = re.compile(r"\s*(>\s?)+")
_SANGRADA = re.compile(r"( {4,}|\t)")


def _bloques(texto):
    """[(apartado, bloque)]: el contenido de cada bloque de la guia y el
    titulo del apartado en el que esta. Cuentan los que van entre vallas de
    acentos graves o de tildes, con lenguaje o sin el (```bash, ```, ~~~sh),
    tambien sangradas dentro de una lista o dentro de una cita (`> ```bash`),
    y los sangrados sin valla (cuatro espacios o un tabulador detras de una
    linea en blanco): Markdown los pinta igual y se pegan igual. Las lineas de
    un bloque que empiezan por `#` son comentarios, no titulos."""
    bloques, apartado = [], ""
    valla, en_cita, dentro = None, False, None   # el bloque con valla abierto
    sangrado = None                              # el bloque sangrado abierto
    en_blanco = True                             # la linea anterior, vacia

    def cerrar_sangrado():
        nonlocal sangrado
        if sangrado is not None:
            bloques.append((apartado, "\n".join(sangrado).rstrip("\n") + "\n"))
            sangrado = None

    for linea in texto.splitlines():
        cita = _CITA.match(linea)
        if valla is not None:
            contenido = linea[cita.end():] if en_cita and cita else linea
            if contenido.lstrip().startswith(valla):
                bloques.append((apartado, "\n".join(dentro) + "\n"))
                valla, dentro = None, None
            else:
                dentro.append(contenido)
            en_blanco = False
            continue
        abre = _VALLA.match(linea[cita.end():] if cita else linea)
        if abre:
            cerrar_sangrado()
            valla, en_cita, dentro = abre.group(1), bool(cita), []
        elif sangrado is not None and (not linea.strip() or _SANGRADA.match(linea)):
            sangrado.append(linea)
        else:
            cerrar_sangrado()
            if en_blanco and not cita and _SANGRADA.match(linea) and linea.strip():
                sangrado = [linea]
            elif not cita and re.match(r"#{1,6} ", linea):
                apartado = linea.lstrip("#").strip()
        en_blanco = not linea.strip()
    cerrar_sangrado()
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
    ("docker compose -p x up -d --remove-orphans\n", []),
    ("docker run --rm x\n", []),
    ("docker rmi y\n", ["docker rmi y"]),
    ("docker volume remove v\n", ["docker volume remove v"]),
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
_BORRA_VOLUMEN = re.compile(r"docker\s+volume\s+(rm|remove)(?![\w-])")
_BORRA_IMAGEN = re.compile(r"docker\s+(rmi|image\s+(rm|remove))(?![\w-])")
# La imagen del proyecto, la de la linea 12 del compose (la fija la prueba de
# las lineas que cita la guia): borrarla solo cuesta reconstruirla.
IMAGEN_DEL_PROYECTO = "copiloto-mcp:0.1.0"


def _ordenes_que_no_valen(guia):
    """Las ordenes de los bloques de la guia (de todas las clases que
    reconoce `_bloques`) que borran datos o pueden parar lo ajeno: un `down`
    con `-v` o `--volumes` en cualquier posicion, un `docker volume rm` (o
    `remove`) o un `prune`, un `docker rmi` de una imagen que no es la del
    proyecto, y cualquier orden que pare, arranque o borre algo sin ser de
    Compose por nombre de proyecto (`-p copiloto-mcp`), salvo las
    `EXCEPCIONES`. Devuelve [(apartado, orden, por que)]; tambien, las
    excepciones que ya no estan en la guia."""
    malas, usadas = [], set()
    for apartado, bloque in _bloques(guia):
        for orden in _ordenes(bloque):
            orden = " ".join(orden.split())
            if "docker" not in orden:
                continue
            imagen = _BORRA_IMAGEN.search(orden)
            if (re.search(r"(?<![\w-])down(?![\w-])", orden)
                    and _CON_VOLUMENES.search(orden)):
                malas.append((apartado, orden, "down con volumenes: borra la base"))
            elif _BORRA_VOLUMEN.search(orden) or re.search(r"(?<![\w-])prune(?![\w-])", orden):
                malas.append((apartado, orden, "borra volumenes o imagenes"))
            elif imagen:
                borradas = [p for p in orden[imagen.end():].split() if not p.startswith("-")]
                if not borradas or any(i != IMAGEN_DEL_PROYECTO for i in borradas):
                    malas.append((apartado, orden, "borra una imagen que no es la del proyecto"))
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
    # `remove`, el alias de `rm`
    lambda g: g + "\n```bash\ndocker volume remove copiloto-mcp_copiloto_bd_datos\n```\n",
    lambda g: g + "\n```bash\ndocker network remove otra-red\n```\n",
    lambda g: g + "\n```bash\ndocker container remove -f n8n\n```\n",
    # una imagen que no es la del proyecto
    lambda g: g + "\n```bash\ndocker rmi n8nio/n8n\n```\n",
    lambda g: g + "\n```bash\ndocker image rm copiloto-mcp:0.1.0 n8nio/n8n\n```\n",
    # bloques que no van entre acentos graves, o que van dentro de una cita
    lambda g: g + "\n~~~bash\ndocker volume rm copiloto-mcp_copiloto_bd_datos\n~~~\n",
    lambda g: g + "\n> ```bash\n> docker stop n8n\n> ```\n",
    lambda g: g + "\nPara pararlo todo:\n\n    docker stop n8n\n",
    lambda g: g + "\n1. Si hace falta:\n\n\tdocker compose down --volumes\n",
], ids=["volume-rm-en-sh", "volumes-detras-sin-lenguaje", "stop-de-otro-contenedor",
        "down-v-en-la-orden-de-siempre", "excepcion-fuera-de-su-apartado",
        "prune", "reiniciar-docker", "volume-remove", "network-remove",
        "container-remove", "rmi-de-otra-imagen", "image-rm-de-otra-imagen",
        "valla-de-tildes", "valla-en-una-cita", "sangrado-sin-valla",
        "sangrado-con-tabulador"])
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
    # y lo que significa lo que da la guarda: con la explicacion al reves, el
    # segundo intento volveria a apuntar como commit de vuelta el nuevo
    for dice in ("Si da `1`, el código nuevo ya está en el disco",
                 "no es el de ahora",
                 "(si el `grep` dio `0`)"):
        assert dice in seguido, dice

    # si el contenedor esta en dos redes: dicho entre la orden que las lista
    # (punto 2) y la que mira si la variable ya esta en el `.env`
    redes = ("docker inspect copiloto-mcp --format '{{range $red, $c := "
             ".NetworkSettings.Networks}}{{println $red}}{{end}}'")
    ya_esta = "grep -c '^RED_N8N='"
    for dice in ("Si salen dos, para", "la pierde al recrearse"):
        assert seguido.index(redes) < seguido.index(dice) < seguido.index(ya_esta), dice

    # el camino B no se cubre a medias: se dice que no, y no hay copia del arbol
    assert "no cubre el camino B" in seguido
    assert "cp -a" not in apartado

    # la copia de la base se comprueba entera al hacerla: una copia cortada
    # no daria ningun error al restaurarla
    (copia,) = copias
    comprobar = "gunzip -t ~/copiloto-bd.antes-de-red_n8n.sql.gz"
    assert copia.index("pg_dump") < copia.index(comprobar) < copia.index("ls -l")

    # la copia de la base se restaura en una sola transaccion, y antes se
    # comprueba que esta entera
    (restaura,) = [b for b in bloques if "gunzip -c ~/copiloto-bd.antes-de-red_n8n.sql.gz" in b]
    assert re.search(r"docker exec -i copiloto-bd psql .*(?<![\w-])-1(?![\w-])", restaura)
    assert "-v ON_ERROR_STOP=1" in restaura
    assert restaura.index(comprobar) < restaura.index("gunzip -c")

    # las copias se borran con `rm -f`: tambien si una de las dos no llego a hacerse
    borrar = [b for b in bloques if "antes-de-red_n8n" in b and re.search(r"(?<![\w-])rm ", b)]
    assert [b.strip() for b in borrar] == [
        "rm -f ~/copiloto.env.antes-de-red_n8n ~/copiloto-bd.antes-de-red_n8n.sql.gz"]


def _lo_que_le_falta_al_commit_de_vuelta(guia):
    """Lo que el primer redespliegue tiene que decir del commit de vuelta y de
    la copia de la base, mirado en el apartado con los blancos normalizados:
    la guarda del punto 1 y su `0`; la orden que da el commit de antes del
    `pull` y su comprobacion, que antes exige que el commit exista
    (`cat-file -e … &&`: si no, el `grep -c` de detras daria el `0` que se pide
    con un commit mal copiado), con su `0` y lo que significa un `fatal:`; y
    que tras `gunzip -t` se siga con `&&` al hacer la copia y al restaurarla
    (con `;`, una copia rota se restauraria igual). Devuelve lo que falta."""
    inicio = guia.index("### El primer redespliegue con `RED_N8N` obligatoria")
    seguido = " ".join(guia[inicio:guia.index("\n## 7. ", inicio)].split())
    donde = seguido.find
    falta = []
    guarda = "grep -c 'RED_N8N:?' /opt/copiloto/servidor/docker-compose.yml"
    if f"{guarda} ``` Tiene que dar `0`" not in seguido:
        falta.append("la guarda del punto 1 va seguida de «Tiene que dar `0`»")
    reflog = "git -C /opt/copiloto rev-parse 'main@{1}'"
    comprobacion = ("git -C /opt/copiloto cat-file -e '<commit>:servidor/docker-compose.yml' "
                    "&& git -C /opt/copiloto show '<commit>:servidor/docker-compose.yml' "
                    "| grep -c 'RED_N8N:?'")
    apunta = donde("git rev-parse HEAD")      # la orden que apunta el commit de ahora
    if not -1 < donde(guarda) < donde(reflog) < apunta:
        falta.append("la orden que da el commit de antes del pull")
    if not -1 < max(donde(reflog), donde(guarda)) < donde(comprobacion) < apunta:
        falta.append("la comprobacion del commit de vuelta, con `cat-file -e` delante y `&&`")
    elif f"{comprobacion} ``` Tiene que dar `0`" not in seguido:
        falta.append("la comprobacion del commit va seguida de «Tiene que dar `0`»")
    if "sale un `fatal:`, el commit está mal copiado" not in seguido:
        falta.append("lo que significa que salga un `fatal:`")
    if ("gunzip -t ~/copiloto-bd.antes-de-red_n8n.sql.gz && gunzip -c "
            "~/copiloto-bd.antes-de-red_n8n.sql.gz | docker exec -i copiloto-bd psql"
            not in seguido):
        falta.append("la restauracion sigue a `gunzip -t` con `&&`")
    if (".sql.gz) && gunzip -t ~/copiloto-bd.antes-de-red_n8n.sql.gz && ls -l"
            not in seguido):
        falta.append("la copia se comprueba con `gunzip -t` encadenado con `&&`")
    return falta


def test_el_primer_redespliegue_guarda_el_commit_de_vuelta_y_encadena_la_restauracion():
    """La hermana de la anterior, sobre una funcion que recibe el texto de la
    guia, para poder probarla con mutaciones: lo que se pega en el servidor
    tiene que decir lo que significa cada `0`, comprobar el commit de vuelta
    antes de darlo por bueno, y no seguir con una copia rota."""
    assert _lo_que_le_falta_al_commit_de_vuelta(_guia()) == []


# Mutaciones de la guia que la comprobacion de arriba tiene que cazar, cada
# una con lo que tiene que decir que falta.
MUTACIONES_DEL_COMMIT_DE_VUELTA = {
    "la guarda pide un 1": (
        "Tiene que dar `0`: el compose del disco", "Tiene que dar `1`: el compose del disco",
        "la guarda del punto 1 va seguida de «Tiene que dar `0`»"),
    "sin la orden de main@{1}": (
        "```bash\ngit -C /opt/copiloto rev-parse 'main@{1}'\n```\n", "",
        "la orden que da el commit de antes del pull"),
    "sin la comprobacion del commit": (
        "git -C /opt/copiloto cat-file -e '<commit>:servidor/docker-compose.yml' && git -C "
        "/opt/copiloto show '<commit>:servidor/docker-compose.yml' | grep -c 'RED_N8N:?'\n", "",
        "la comprobacion del commit de vuelta, con `cat-file -e` delante y `&&`"),
    "la comprobacion sin cat-file": (
        "git -C /opt/copiloto cat-file -e '<commit>:servidor/docker-compose.yml' && git", "git",
        "la comprobacion del commit de vuelta, con `cat-file -e` delante y `&&`"),
    "la comprobacion con ; tras cat-file": (
        "servidor/docker-compose.yml' && git -C /opt/copiloto show",
        "servidor/docker-compose.yml'; git -C /opt/copiloto show",
        "la comprobacion del commit de vuelta, con `cat-file -e` delante y `&&`"),
    "la comprobacion pide un 1": (
        "Tiene que dar `0`. Si en vez", "Tiene que dar `1`. Si en vez",
        "la comprobacion del commit va seguida de «Tiene que dar `0`»"),
    "sin decir que es un fatal": (
        "sale un `fatal:`, el commit está mal", "sale un error, el commit está mal",
        "lo que significa que salga un `fatal:`"),
    "la restauracion con ; tras gunzip -t": (
        "gunzip -t ~/copiloto-bd.antes-de-red_n8n.sql.gz && gunzip -c",
        "gunzip -t ~/copiloto-bd.antes-de-red_n8n.sql.gz; gunzip -c",
        "la restauracion sigue a `gunzip -t` con `&&`"),
    "la copia con ; tras gunzip -t": (
        "gunzip -t ~/copiloto-bd.antes-de-red_n8n.sql.gz && ls -l",
        "gunzip -t ~/copiloto-bd.antes-de-red_n8n.sql.gz; ls -l",
        "la copia se comprueba con `gunzip -t` encadenado con `&&`"),
}


@pytest.mark.parametrize("antes, despues, falta", MUTACIONES_DEL_COMMIT_DE_VUELTA.values(),
                         ids=list(MUTACIONES_DEL_COMMIT_DE_VUELTA))
def test_la_comprobacion_del_commit_de_vuelta_caza_las_mutaciones(antes, despues, falta):
    guia = _guia()
    assert guia.count(antes) == 1, "la mutacion ya no encuentra su texto"
    assert falta in _lo_que_le_falta_al_commit_de_vuelta(guia.replace(antes, despues))


def test_la_plantilla_del_env_se_copia_sin_pisar_el_que_hay():
    """El `.env` lleva la contraseña de la base: copiar encima la plantilla,
    pegando la orden sin leer la condicion de delante, la perderia. Con `-n`,
    `cp` no pisa un fichero que ya existe."""
    copias = re.findall(r"\bcp\b([^`\n]*?)servidor/\.env\.ejemplo\s+servidor/\.env\b",
                        _guia())
    assert copias, "la guia ya no dice como nace servidor/.env"
    assert all(re.search(r"(?<![\w-])-n\b", opciones) for opciones in copias), copias


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
```

- [ ] **Paso 3: Correrlas y verlas fallar**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_arrancar.py
```

Esperado: `5 failed, 5 passed`. Fallan las cinco nuevas, cada una por lo
suyo:

| Prueba | Falla en | Porque |
| :--- | :--- | :--- |
| `test_el_compose_exige_RED_N8N_y_no_le_pone_valor_por_defecto` | `assert all(uso.startswith("${RED_N8N:?") …)` | el único uso de la variable es de la forma `${RED_N8N:-…}`, con un nombre por defecto |
| `test_los_dos_servicios_van_a_la_red_externa_red_n8n` | `assert compose["networks"] == {…}` | la clave de la red es otra y su `name` lleva valor por defecto |
| `test_el_env_de_ejemplo_declara_RED_N8N_con_un_valor_de_ejemplo` | `assert "RED_N8N=cambiar-esto" in lineas` | la plantilla no tiene esa línea |
| `test_la_guia_de_despliegue_no_promete_un_valor_por_defecto_para_la_red` | `assert "${RED_N8N:-" not in guia …` | la guía copia el bloque viejo del compose |
| `test_el_primer_redespliegue_no_baja_el_servicio_antes_de_construir` | `guia.index("### El primer redespliegue…")` | la guía todavía no tiene ese apartado |

Si alguna de las cinco pasa ya, para: el árbol no es el del commit
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
dentro de `networks:`). Pasa a:

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

Esperado: `2 failed, 8 passed`. Las que fallan son las dos que leen la guía:
`test_la_guia_de_despliegue_no_promete_un_valor_por_defecto_para_la_red`, en
su primera aserción, y
`test_el_primer_redespliegue_no_baja_el_servicio_antes_de_construir`.

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

Hasta SP5 el compose traía escrito el nombre de la red, como valor por defecto
de `RED_N8N`. Desde que la variable es obligatoria, **la clave de la red
cambió en el compose** (ahora es `red_n8n`) y el nombre ya no viene en el
fichero. Una instalación levantada con el compose anterior necesita, **una
sola vez**, que los dos contenedores se vuelvan a crear. **No hace falta
bajarlos antes:** Compose ve que la configuración cambió y los recrea él, y lo
hace **después** de construir la imagen y de comprobar que la red existe. Si
algo de eso falla, los contenedores de antes siguen en marcha. La base de
datos **no se toca**: sus datos viven en el volumen `copiloto_bd_datos`, que
sobrevive a que el contenedor se recree.

Esto se ensayó el 28-sep-2026 con un proyecto de prueba de la misma forma (dos
servicios, una red externa, un volumen con nombre) y Compose v5.2.0: con la
variable ausente, con una errata en el nombre de la red y con una construcción
que falla, `up` se detiene **sin tocar** los contenedores que había; con todo
bien, los recrea, y el volumen es el mismo y conserva sus datos. También se
ensayaron la vuelta atrás y la copia de la base; y su restauración, el 29-sep,
sobre una base con el esquema del proyecto que había cambiado después de la
copia: vuelve a lo copiado, y si se interrumpe a medias la base se queda como
estaba. **No se ha ensayado en el servidor**, donde la versión de Compose
puede ser otra: por eso los puntos 1 y 3 apuntan de dónde se parte y guardan
una copia, y al final está escrito cómo volver.

Es para una instalación que es un clon de git (el camino A del paso 3.1), y
**no cubre el camino B**: las órdenes de los puntos 1 y 4 y la vuelta atrás
son de git, y pegadas en un árbol que no es un clon se cortan sin hacer nada.
Para el camino B no hay procedimiento escrito ni ensayado: no lo improvises
sobre este.

Mientras Compose recrea los contenedores y el copiloto vuelve a estar
`healthy` —alrededor de un minuto— n8n no alcanza ni al copiloto ni a la base:
los bots contestan con su mensaje de error. Hazlo cuando no haya consultas en
curso.

**1. Apuntar de dónde se parte y guardar el `.env`.** Primero, que el código
nuevo no esté ya traído:

```bash
grep -c 'RED_N8N:?' /opt/copiloto/servidor/docker-compose.yml
```

Tiene que dar `0`: el compose del disco es el anterior, y el commit de ahora
es al que se vuelve. **Si da `1`, el código nuevo ya está en el disco** —se
lanzó antes el redespliegue de siempre, o este es un segundo intento— y el
commit de vuelta **no es el de ahora**: es el que apuntaste la primera vez. Si
no lo apuntaste, es el que tenía `main` antes del `pull`, y lo dice esta
orden (ensayada: lo da aunque después se haya cambiado de commit a mano):

```bash
git -C /opt/copiloto rev-parse 'main@{1}'
```

Da el commit de antes del ÚLTIMO `pull`. Comprueba que es el bueno, cambiando
`<commit>` por el que ha salido: su compose no tiene que llevar la variable
obligatoria.

```bash
git -C /opt/copiloto cat-file -e '<commit>:servidor/docker-compose.yml' && git -C /opt/copiloto show '<commit>:servidor/docker-compose.yml' | grep -c 'RED_N8N:?'
```

Tiene que dar `0`. Si en vez de un número sale un `fatal:`, el commit está mal
copiado (o sigue puesto el marcador): cópialo otra vez. Si da `1`, desde el
compose anterior se ha hecho más de un
`pull`: repite las dos órdenes con `'main@{2}'`, y así hasta que dé `0`.

Sigue con este punto, pero no apuntes el commit que imprime su orden.

El `.env` es el fichero que tiene la contraseña de la base: se guarda una
copia **fuera** del repositorio antes de tocarlo. Y una `RED_N8N` exportada
en la sesión manda sobre la del `.env`, así que se retira:

```bash
cd /opt/copiloto && unset RED_N8N && git rev-parse HEAD && cp -p servidor/.env ~/copiloto.env.antes-de-red_n8n && echo "copia hecha"
```

Apunta el commit que imprime (si el `grep` dio `0`): es al que se vuelve si
algo sale mal.

**2. Declarar la variable, antes del `git pull`.** El nombre es el de la red
donde está hoy el contenedor; pregúntaselo a él:

```bash
docker inspect copiloto-mcp --format '{{range $red, $c := .NetworkSettings.Networks}}{{println $red}}{{end}}'
```

Tiene que salir **un solo nombre**. Si salen dos, para: la de `RED_N8N` es
la que el contenedor comparte con n8n (la del paso 2.3); la otra no está en
el compose y el contenedor la pierde al recrearse, así que averigua quién la
conectó y para qué antes de seguir. Mira ahora si la variable ya está en el
`.env`:

```bash
grep -c '^RED_N8N=' /opt/copiloto/servidor/.env
```

Si da `1`, ya está declarada: **no añadas nada**, y pasa a comprobar, más
abajo, que su valor es ese nombre. Si da `0`, añádela al final del `.env` con
esta orden, cambiando `<RED_N8N>` por el nombre. Lleva `>>`, que añade; con
un solo `>` se borraría el fichero, contraseña incluida:

```bash
printf '\nRED_N8N=%s\n' '<RED_N8N>' >> /opt/copiloto/servidor/.env
```

Comprueba que quedó, una sola vez y con el nombre de la red, y que la
contraseña sigue ahí:

```bash
grep -c '^RED_N8N=.' /opt/copiloto/servidor/.env; grep -c '^COPILOTO_BD_PASSWORD=.' /opt/copiloto/servidor/.env; grep '^RED_N8N=' /opt/copiloto/servidor/.env
```

Esperado: `1`, `1` y la línea `RED_N8N=` con el nombre que dio el `docker
inspect`. **Si no sale eso** y la línea la acabas de añadir tú —quedó dos
veces, lleva todavía el marcador, o falta la contraseña—, no repitas el
`printf` encima: restaura la copia y vuelve a empezar este punto.

```bash
cp -p ~/copiloto.env.antes-de-red_n8n /opt/copiloto/servidor/.env
```

Si la línea **ya estaba** antes de empezar —vacía, con otro nombre o
repetida—, restaurar la copia te devuelve el mismo fichero. Esa se corrige a
mano, con un editor (`nano /opt/copiloto/servidor/.env`): una sola línea
`RED_N8N=` con el nombre que dio el `docker inspect`. Después, la misma
comprobación.

**3. Apuntar cómo están la base y los contenedores, y sacar una copia de la
base.** Primero lo que se va a comparar al final: cuándo se creó el volumen,
cuántas consultas guarda la base y cuándo se crearon los dos contenedores.

```bash
docker volume inspect "$(docker inspect copiloto-bd --format '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{end}}{{end}}')" --format 'volumen creado: {{.CreatedAt}}'
docker exec copiloto-bd psql -U copiloto -d copiloto -tAc 'select count(*) from consultas'
docker inspect copiloto-mcp copiloto-bd --format '{{.Name}} creado: {{.Created}}'
```

Y la copia, que es con lo que se repara la base si al final no es la que
había. Se queda fuera del repositorio y solo la puede leer quien la hace:

```bash
(umask 077; set -o pipefail; docker exec copiloto-bd pg_dump --clean --if-exists -U copiloto -d copiloto | gzip > ~/copiloto-bd.antes-de-red_n8n.sql.gz) && gunzip -t ~/copiloto-bd.antes-de-red_n8n.sql.gz && ls -l ~/copiloto-bd.antes-de-red_n8n.sql.gz
```

Tiene que terminar enseñando el fichero. Si en su lugar sale un error de
`pg_dump` o de `gunzip` (que comprueba que la copia está entera), no hay
copia: no sigas. Y si entre este punto y el 5 pasa un rato
en el que los bots han atendido consultas, repite este punto antes de
redesplegar: la copia que sirve es la de justo antes.

**4. Traer el código y comprobar, sin levantar nada,** que el compose nuevo se
deja leer y que la red que dice el `.env` existe:

```bash
cd /opt/copiloto && git pull --ff-only && docker compose -f servidor/docker-compose.yml config --quiet && docker network inspect "$(sed -n 's/^RED_N8N=//p' servidor/.env)" --format 'la red existe: {{.Name}}'
```

Tiene que terminar con `la red existe:` y el nombre del punto 2. **Si no
termina así, sea cual sea el error, no sigas:** hasta aquí no se ha tocado
ningún contenedor y el servicio sigue como estaba. Si el mensaje es `required
variable RED_N8N is missing a value`, vuelve al punto 2.

**5. Redesplegar.** Es la orden de siempre, pero **sin nombrar el servicio**,
para que Compose recree los dos contenedores, y esperando a los dos:

```bash
cd /opt/copiloto && docker compose -f servidor/docker-compose.yml up -d --build && for c in copiloto-bd copiloto-mcp; do for i in $(seq 1 30); do e=$(docker inspect -f '{{.State.Health.Status}}' $c 2>/dev/null || echo ausente); [ "$e" = healthy ] && break; sleep 5; done; echo "$c: $e"; done
```

Primero construye la imagen —minutos, con el servicio todavía en marcha— y
después recrea. Lo que Compose va pintando mientras tanto depende de la
terminal (líneas sueltas, o una lista que se actualiza en su sitio): no te
guíes por eso. Lo que cuenta es cómo termina, `copiloto-bd: healthy` y
`copiloto-mcp: healthy`, y el punto 6. Si la conexión con el servidor se
corta a medias, vuelve a entrar y repite la orden: si Compose ya había
terminado, no cambia nada; si no, acaba lo que faltaba.

**6. Comprobar**, con las mismas órdenes del punto 3 y una más:

```bash
docker inspect copiloto-mcp copiloto-bd --format '{{.Name}} creado: {{.Created}}'
docker volume inspect "$(docker inspect copiloto-bd --format '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{end}}{{end}}')" --format 'volumen creado: {{.CreatedAt}}'
docker exec copiloto-bd psql -U copiloto -d copiloto -tAc 'select count(*) from consultas'
docker inspect copiloto-mcp copiloto-bd --format '{{.Name}}: {{range $red, $c := .NetworkSettings.Networks}}{{$red}} {{end}}'
```

- los dos contenedores tienen una fecha de creación **posterior** a la del
  punto 3: Compose los recreó;
- el volumen tiene **la misma** fecha de creación que en el punto 3;
- la base guarda, como poco, las mismas consultas;
- los dos contenedores están en la red del punto 2.

Si todo cuadra, termina con la sonda de salud del paso 6 y con una consulta de
prueba por el bot.

**Si algo falla.**

- **La orden del punto 5 termina con un error y los dos contenedores
  conservan la fecha de creación del punto 3** (la construcción, la red): no
  se ha tocado nada y el servicio sigue con los contenedores de antes. Se
  corrige la causa y se repite desde el punto 4.
- **Los contenedores se recrearon y alguno no llega a `healthy`, o llegan
  los dos pero quedan en otra red que la del punto 2:** mira por qué, con
  `docker logs --tail 50 copiloto-mcp` o `docker logs --tail 50
  copiloto-bd`. Para volver a la versión anterior se restaura **antes** el
  `.env` —el compose anterior también lee `RED_N8N`, y con el `.env` de antes
  vuelve a la red en la que estaba— y se levanta el commit del punto 1:

  ```bash
  cd /opt/copiloto && cp -p ~/copiloto.env.antes-de-red_n8n servidor/.env && git checkout --detach <commit del punto 1> && docker compose -f servidor/docker-compose.yml up -d --build && for c in copiloto-bd copiloto-mcp; do for i in $(seq 1 30); do e=$(docker inspect -f '{{.State.Health.Status}}' $c 2>/dev/null || echo ausente); [ "$e" = healthy ] && break; sleep 5; done; echo "$c: $e"; done
  ```

  Después, las comprobaciones del punto 6. Para volver a intentarlo otro día:
  `git switch main`, y otra vez desde el punto 1. El commit de vuelta sigue
  siendo el que apuntaste la primera vez: tras el `git switch main` el de
  ahora ya es el nuevo, y el `grep` del punto 1 lo avisa.
- **`up` se niega a recrear y pide bajar antes el proyecto** (una versión
  antigua de Compose puede hacerlo cuando cambia la clave de la red):
  entonces sí, y en este orden, para que el servicio esté caído lo menos
  posible: construir, bajar **por nombre de proyecto y sin `-v` ni
  `--volumes`** —con cualquiera de los dos se borra la base—, levantar y
  esperar:

  ```bash
  cd /opt/copiloto && docker compose -f servidor/docker-compose.yml build && docker compose -p copiloto-mcp down && docker compose -f servidor/docker-compose.yml up -d && for c in copiloto-bd copiloto-mcp; do for i in $(seq 1 30); do e=$(docker inspect -f '{{.State.Health.Status}}' $c 2>/dev/null || echo ausente); [ "$e" = healthy ] && break; sleep 5; done; echo "$c: $e"; done
  ```

  El `down` nombra solo a `copiloto-mcp` y a `copiloto-bd`; si nombra
  cualquier otro contenedor, `Ctrl+C`. Después, las comprobaciones del punto 6.
- **El volumen tiene otra fecha de creación, o la base guarda menos
  consultas:** la base no es la que había. Para, y no sigas operando sobre
  ella. Si el volumen es otro, el de antes sigue en el disco (`docker volume
  ls`): **no lo borres**, que es donde están los datos. La copia del punto 3
  devuelve la base a como estaba, en una sola transacción —si una sentencia
  falla, la base se queda como estaba antes de empezar—, y antes comprueba
  que la copia está entera, porque una copia cortada no daría ningún error y
  dejaría la base a medias:

  ```bash
  gunzip -t ~/copiloto-bd.antes-de-red_n8n.sql.gz && gunzip -c ~/copiloto-bd.antes-de-red_n8n.sql.gz | docker exec -i copiloto-bd psql -U copiloto -d copiloto -q -1 -v ON_ERROR_STOP=1 && docker exec copiloto-bd psql -U copiloto -d copiloto -tAc 'select count(*) from consultas'
  ```

  Tiene que terminar con el recuento del punto 3. Lo que se haya escrito en
  la base después del punto 3 no está en la copia, y se pierde.

Las dos copias —la del `.env`, que lleva la contraseña, y la de la base, que
lleva las consultas— se borran cuando todo esté comprobado, y también si se
abandona el redespliegue:

```bash
rm -f ~/copiloto.env.antes-de-red_n8n ~/copiloto-bd.antes-de-red_n8n.sql.gz
```

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
export RED_N8N="$(sed -n 's/^RED_N8N=//p' .env | tail -n 1)"
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

Si `servidor/.env` no existe todavía, créalo copiando la plantilla
(`cp -n servidor/.env.ejemplo servidor/.env`; con `-n` no pisa uno que ya
exista, que lleva la contraseña) y pon en él la contraseña de la base. La
plantilla ya trae una línea `RED_N8N=` con un valor de ejemplo: **no
se añade otra, se sustituye su valor** por el nombre que apuntaste en el paso
2.2. Tiene que quedar una sola:

```
RED_N8N=<RED_N8N>
```

Y comprueba, sin levantar nada, que Compose ya la lee:

```bash
cd servidor
docker compose config --quiet && echo "el compose se deja leer"
```

`config` solo lee e interpola: no crea, no arranca y no toca ningún contenedor.
Si imprime un mensaje de `required variable`, mira qué variable nombra. Si es
`RED_N8N`, la línea no está en `.env`, está vacía, o el `.env` no está en
`servidor/`. Si es `COPILOTO_BD_PASSWORD`, lo que falta es la contraseña de la
base.

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

**Además, lo que la guía decía de un solo contenedor sin estado.** Desde SP3 el
proyecto son dos contenedores y un volumen, y la guía la sigue una persona en
producción: con el texto de antes, el `down` de la vuelta atrás nombraba
siempre a `copiloto-bd`, y la guía mandaba pulsar `Ctrl+C` al verlo. Estas
sustituciones se localizan por su texto, que no lleva nada de la lista, y se
hacen DESPUÉS de las dieciocho de arriba, en este orden. Cada texto que se
busca aparece UNA vez en el fichero tal como está cuando le toca.

14, en este orden. Cada texto que se busca aparece UNA vez en el fichero tal como está cuando le toca.

1. Busca

````markdown
| aparece un contenedor nuevo, `copiloto-mcp` | los contenedores que ya corrían |
| aparece una imagen nueva, `copiloto-mcp:0.1.0` (~2 GB en disco) | las imágenes de los demás stacks |
| ese contenedor se **une** a la red externa de n8n, la que nombra `RED_N8N` | la red en sí: no se crea, ni se altera, ni se borra |
````

y sustitúyelo por

````markdown
| aparecen dos contenedores nuevos, `copiloto-mcp` y, desde SP3, su base `copiloto-bd` | los contenedores que ya corrían |
| aparecen dos imágenes: la nuestra, `copiloto-mcp:0.1.0` (~2 GB en disco), y, desde SP3, la de PostgreSQL de la base | las imágenes de los demás stacks |
| los dos contenedores se **unen** a la red externa de n8n, la que nombra `RED_N8N` | la red en sí: no se crea, ni se altera, ni se borra |
````

2. Busca

````markdown
| — | volúmenes y datos: este servicio no tiene estado |
````

y sustitúyelo por

````markdown
| aparece un volumen con nombre, `copiloto_bd_datos`, con la base del copiloto (desde SP3) | los volúmenes y los datos de los demás stacks |
````

3. Busca

````markdown
Los comandos de **solo lectura** del paso 2, como `docker network inspect`, sí
llevan el nombre literal, y eso es a propósito: ahí lo que se teclea es el nombre
real que acabas de leer en `docker network ls`.
````

y sustitúyelo por

````markdown
Los comandos de **solo lectura** del paso 2, como `docker network inspect`,
llevan el marcador `<RED_N8N>`, y eso es a propósito: ahí lo que se teclea, en
su lugar, es el nombre real que acabas de leer en `docker network ls`.
````

4. Busca

````markdown
Todo lo que hay que deshacer es un contenedor. No hay migraciones, ni
volúmenes, ni configuración del sistema que revertir.
````

y sustitúyelo por

````markdown
Todo lo que hay que deshacer son dos contenedores: `copiloto-mcp` y, desde
SP3, su base `copiloto-bd`. No hay migraciones ni configuración del sistema
que revertir. El volumen de la base, `copiloto_bd_datos`, se queda donde está:
bajar el servicio no lo borra.
````

5. Busca

````markdown
copiloto-mcp   running(1)   /opt/copiloto/servidor/docker-compose.yml
````

y sustitúyelo por

````markdown
copiloto-mcp   running(2)   /opt/copiloto/servidor/docker-compose.yml
````

6. Busca

````markdown
`running(1)`: un solo contenedor. Si ves cualquier otro proyecto en esa línea,
no es el nuestro.
````

y sustitúyelo por

````markdown
`running(2)`: los dos contenedores del proyecto. Si ves cualquier otro proyecto
en esa línea, no es el nuestro.
````

7. Busca

````markdown
lado, borra los datos del cliente.

Salida literal:

```
````

y sustitúyelo por

````markdown
lado, borra los datos del cliente.

Salida (el orden entre los dos contenedores puede variar):

```
````

8. Busca

````markdown
 Container copiloto-mcp Removed
```
````

y sustitúyelo por

````markdown
 Container copiloto-mcp Removed
 Container copiloto-bd Stopping
 Container copiloto-bd Stopped
 Container copiloto-bd Removing
 Container copiloto-bd Removed
```
````

9. Busca

````markdown
Cuatro líneas, las cuatro sobre `copiloto-mcp`. Si aparece el nombre de
cualquier otro contenedor, para: `Ctrl+C` y vuelve al `docker compose ls`.
````

y sustitúyelo por

````markdown
Ocho líneas, cuatro sobre `copiloto-mcp` y cuatro sobre `copiloto-bd`. Según
la terminal, Compose las pinta así, sueltas, o como una lista que se actualiza
en su sitio; en los dos casos nombra solo a esos dos contenedores. Si aparece
el nombre de cualquier otro, para: `Ctrl+C` y vuelve al `docker compose ls`.
````

10. Busca

````markdown
lo corres con el copiloto aún arriba, la única diferencia debe ser una línea
`> copiloto-mcp`, y ninguna más.)
````

y sustitúyelo por

````markdown
lo corres con el copiloto aún arriba, las únicas diferencias deben ser dos
líneas, `> copiloto-bd` y `> copiloto-mcp`, y ninguna más.)
````

11. Busca

````markdown
docker compose stop     # se para, se queda creado
docker compose start    # vuelve en ~10 s
````

y sustitúyelo por

````markdown
docker compose -p copiloto-mcp stop     # se para, se queda creado
docker compose -p copiloto-mcp start    # vuelve en ~10 s
````

12. Busca

````markdown
docker compose -p copiloto-mcp start    # vuelve en ~10 s
```

El servicio lleva `restart: unless-stopped`, así que un contenedor parado a
````

y sustitúyelo por

````markdown
docker compose -p copiloto-mcp start    # vuelve en ~10 s
```

Por nombre de proyecto, como el `down`: así da igual en qué carpeta estés.

El servicio lleva `restart: unless-stopped`, así que un contenedor parado a
````

13. Busca

````markdown
```bash
docker compose up -d
```
````

y sustitúyelo por

````markdown
```bash
cd /opt/copiloto && docker compose -f servidor/docker-compose.yml up -d
```
````

14. Busca

````markdown
Los pesos y el calibrador viajan dentro de la imagen, así que no se pierde nada
y el servicio vuelve a estar `healthy` en unos 30 segundos.
````

y sustitúyelo por

````markdown
Los pesos y el calibrador viajan dentro de la imagen y la base conserva sus
datos en el volumen, así que no se pierde nada, y el servicio vuelve a estar
`healthy` en unos 30 segundos.
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

Esperado: `1513` en la primera; **ninguna línea** en la segunda (el
nombre de la red, en cualquiera de sus formas, terminaba así); `47` en
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
| 866 | 1123 | pila de mensajería ajena |

En `docs/sp3-operacion.md` quedan trece líneas, ninguna de la red: son de las
tareas 4 y 6.

- [ ] **Paso 7: Correr las pruebas y verlas pasar**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_arrancar.py tests/test_sesion.py
```

Esperado: `39 passed`.

Y la suite entera, para comprobar que nada que pasara ha pasado a fallar:

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q
```

Esperado: **cinco aprobadas más que antes de la tarea y ningún fallo ni
error nuevo**. En la copia donde se verificó esta tarea (sin los ficheros que git ignora: la caché de puntuaciones, los pesos y el `.env`; y antes de fusionar SP5-B1: con SP5-B1, esa copia da de partida `699 passed, 18 skipped, 7 errors`) la suite pasó de `543 passed, 18 skipped, 7 errors` a `547 passed, 18 skipped, 7 errors`: los 7 errores ya estaban antes de tocar nada (5 son de `tests/test_seleccion_casos.py`, por los ficheros que faltan en la copia) y son los mismos después. En el repo de desarrollo, que sí tiene esos ficheros, y con las tareas anteriores del plan aplicadas, las cifras de partida son otras: apúntalas antes de empezar; lo que tiene que cumplirse es la diferencia.

- [ ] **Paso 8: Verificación en el VPS (la hace el usuario)**

Este paso **no lo ejecuta quien aplica el plan**: el redespliegue en
producción lo decide el usuario. Se deja escrito para él. No bloquea el
commit. En la máquina de desarrollo se comprobó con `docker compose config`,
que solo lee, y con un proyecto de prueba de la misma forma (Compose v5.2.0):
lo que sigue se cumple allí. En el servidor la versión puede ser otra.

Sin tocar nada en marcha, con el código nuevo en una carpeta aparte o tras el
`git pull` del redespliegue:

```bash
cd servidor
RED_N8N= docker compose config --quiet; echo "salida: $?"
RED_N8N=cambiar-esto docker compose config | grep -A3 '^networks:'
```

Y, desde la raíz del repositorio, que Compose lee la variable del `.env` que
está junto al compose aunque se le llame con `-f` desde otra carpeta (es en
lo que descansa la decisión D3.1):

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
con `RED_N8N` obligatoria»: guardar el `.env`, declarar la variable **antes**
del `git pull`, apuntar cómo está la base y sacar una copia, comprobar que la
red existe, `up -d --build` **sin bajar nada antes**, y comparar la base y
los contenedores con lo apuntado. La revisión de esta tarea encontró que la
primera versión del apartado bajaba el servicio antes de construir; se ensayó
y no hacía falta.

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
  - `CLAVES_DEL_WORKFLOW` (`name`, `active`, `nodes`, `connections`, `settings`: lo que se
    versiona de un workflow, y en ese orden) y `como_se_versiona(datos) -> (texto, claves
    quitadas)`: el workflow solo con esas claves y escrito como los de `n8n/`; de lo que no
    tiene `nodes` devuelve `(None, [])`;
  - `convertir(entrada, salida, valores, quitar=False) -> dict` (`{marcador: veces}`; al
    retirar, además, `"claves quitadas"`). Al poner los valores, la salida no puede ser la
    entrada ni caer dentro del repositorio; al retirar un workflow, lo deja como se versiona;
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
import os
import pathlib
import stat

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
N8N = RAIZ / "n8n"
EJEMPLO = N8N / "valores.ejemplo.json"

# Las pruebas que comparan lo escrito con lo versionado lo hacen sobre un
# booleano: pytest enseñaria la linea que difiere, y si en lo versionado se
# colara un valor (un `chat_equipo` relleno) saldria en la salida.
IGUAL_A_LO_VERSIONADO = ("lo escrito no es letra por letra lo versionado: "
                         "miralo con git diff")


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

# Lo mismo que TEXTO, pero con forma de workflow y escrito como se versiona:
# es lo que `--retirar` acepta (TEXTO no es un workflow).
FLUJO = json.dumps({
    "name": "flujo de juguete",
    "active": False,
    "nodes": [
        {"name": "Sonda", "type": "n8n-nodes-base.httpRequest",
         "parameters": {"url": "https://n8n.ejemplo.test/webhook/copiloto-paciente"}},
        {"name": "Responder", "type": "n8n-nodes-base.telegram",
         "credentials": {"telegramApi": {"id": "CRED_TELEGRAM_PACIENTE",
                                         "name": "bot-paciente"}}},
    ],
    "connections": {},
    "settings": {},
}, ensure_ascii=False, indent=2) + "\n"


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


@pytest.mark.parametrize("errata, parecido", [
    ("CRED_TELEGRAM_PACEINTE", "CRED_TELEGRAM_PACIENTE"),
    ("bot-pacinete", "bot-paciente"),
])
def test_un_marcador_desconocido_en_los_valores_es_un_error(mn, valores, errata, parecido):
    """Se dice cuantas claves no son marcadores y, de las que tienen forma de
    marcador, el conocido mas parecido; nunca la clave tal como viene: una con
    forma `bot-...` puede ser el nombre real de un bot."""
    valores[errata] = "errata"
    with pytest.raises(mn.ErrorDeMarcadores, match="desconocid") as e:
        mn.aplicar(TEXTO, valores)
    assert parecido in str(e.value)
    assert "1 clave" in str(e.value)
    assert errata not in str(e.value)


def test_con_los_valores_al_reves_el_error_no_imprime_ninguno(mn, valores):
    """El despiste natural es escribir {valor real: marcador}, que es el
    sentido en que trabaja `retirar`. El error no puede repetir las claves:
    serian todos los valores reales, en la consola de quien despliega."""
    al_reves = {v: m for m, v in valores.items()}
    for funcion in (mn.aplicar, mn.retirar):
        with pytest.raises(mn.ErrorDeMarcadores, match="al reves") as e:
            funcion(TEXTO, al_reves)
        for valor in valores.values():
            assert valor not in str(e.value)
        assert f"{len(valores)} claves que no son marcadores" in str(e.value)
    # una errata entre valores reales: se dice el marcador que se parece a la
    # errata, y de lo demas, cuantas; ni la errata ni los valores
    mezcla = dict(al_reves, CRED_TELEGRAM_PACEINTE="errata")
    with pytest.raises(mn.ErrorDeMarcadores, match="CRED_TELEGRAM_PACIENTE") as e:
        mn.aplicar(TEXTO, mezcla)
    assert all(valor not in str(e.value) for valor in valores.values())
    assert "CRED_TELEGRAM_PACEINTE" not in str(e.value)
    assert f"{len(valores)} claves que no son marcadores" in str(e.value)


@pytest.mark.parametrize("url", [
    "https://flujos.inventado.test/", "flujos.inventado.test", "ftp://x.test",
    # esquema y host, y nada mas: una ruta acabaria delante de /webhook/
    "https://flujos.inventado.test/n8n", "https://flujos.inventado.test/n8n/",
    "https://flujos.inventado.test?x=1", "https://flujos.inventado.test#arriba",
    "https://", "https://:5678", "https://flujos inventado.test",
    "https://alguien@flujos.inventado.test"])
def test_la_url_va_con_esquema_y_sin_barra_final(mn, valores, url):
    valores[mn.URL_N8N] = url
    with pytest.raises(mn.ErrorDeMarcadores, match="URL base"):
        mn.aplicar(TEXTO, valores)


@pytest.mark.parametrize("url", [
    "https://flujos.inventado.test", "http://flujos.inventado.test:5678"])
def test_la_url_con_esquema_host_y_puerto_se_acepta(mn, valores, url):
    valores[mn.URL_N8N] = url
    assert f'"url": "{url}/webhook/copiloto-paciente"' in mn.aplicar(TEXTO, valores)


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
    (tmp_path / "entrada.json").write_bytes(FLUJO.replace("\n", "\r\n").encode("utf-8"))
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
    assert crudo.decode("utf-8") == mn.aplicar(FLUJO, valores)

    assert mn.main(argumentos + ["--retirar",
                                 "--entrada", str(carpeta / "sub" / "puesto.json"),
                                 "--salida", str(carpeta / "vuelta.json")]) == 0
    assert "valores retirados: 3 sustituciones" in capsys.readouterr().out
    assert (carpeta / "vuelta.json").read_bytes() == FLUJO.encode("utf-8")


def test_la_cli_lee_ficheros_con_marca_de_orden_de_bytes(mn, carpeta, valores, capsys):
    """PowerShell 5.1 escribe los JSON con la marca (`Out-File`, `Set-Content
    -Encoding utf8`): los valores y la entrada se leen igual con ella."""
    (carpeta / "valores-bom.json").write_text(json.dumps(valores), encoding="utf-8-sig")
    (carpeta / "entrada-bom.json").write_text(FLUJO, encoding="utf-8-sig")
    assert mn.main(["--valores", str(carpeta / "valores-bom.json"),
                    "--entrada", str(carpeta / "entrada-bom.json"),
                    "--salida", str(carpeta / "puesto.json")]) == 0, capsys.readouterr().err
    assert (carpeta / "puesto.json").read_bytes() == mn.aplicar(FLUJO, valores).encode("utf-8")
    assert mn.leer_valores(carpeta / "valores-bom.json") == valores


def test_la_cli_no_pone_valores_reales_encima_de_la_entrada(mn, carpeta, capsys):
    antes = (carpeta / "entrada.json").read_bytes()
    assert mn.main(["--valores", str(carpeta / "valores.json"),
                    "--entrada", str(carpeta / "entrada.json"),
                    "--salida", str(carpeta / "entrada.json")]) == 1
    assert "la salida no puede ser la entrada" in capsys.readouterr().err
    assert (carpeta / "entrada.json").read_bytes() == antes


def test_la_cli_no_pone_valores_reales_dentro_del_repositorio(
        mn, carpeta, monkeypatch, capsys):
    """Ni encima de otro export ni en un fichero nuevo: lo que se escribe
    dentro del repositorio esta a un `git add` de distancia. El repositorio
    de esta prueba es una carpeta temporal: si la guarda faltara, la prueba
    escribiria ahi y no en el de verdad."""
    repositorio = carpeta / "repositorio"
    (repositorio / "n8n").mkdir(parents=True)
    (repositorio / "n8n" / "otro-export.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(mn, "REPO", repositorio)
    for destino in (repositorio / "n8n" / "otro-export.json",
                    repositorio / "n8n" / "nuevo.json", repositorio / "nuevo.json"):
        antes = destino.read_bytes() if destino.exists() else None
        assert mn.main(["--valores", str(carpeta / "valores.json"),
                        "--entrada", str(carpeta / "entrada.json"),
                        "--salida", str(destino)]) == 1
        assert "FUERA del repositorio" in capsys.readouterr().err
        assert (destino.read_bytes() if destino.exists() else None) == antes
    # fuera del repositorio, si
    assert mn.main(["--valores", str(carpeta / "valores.json"),
                    "--entrada", str(carpeta / "entrada.json"),
                    "--salida", str(carpeta / "fuera.json")]) == 0


def test_la_cli_retira_encima_de_la_entrada(mn, carpeta, valores):
    (carpeta / "export.json").write_text(mn.aplicar(FLUJO, valores), encoding="utf-8")
    assert mn.main(["--valores", str(carpeta / "valores.json"), "--retirar",
                    "--entrada", str(carpeta / "export.json"),
                    "--salida", str(carpeta / "export.json")]) == 0
    assert (carpeta / "export.json").read_bytes() == FLUJO.encode("utf-8")


def test_escribir_no_deja_el_destino_a_medias(mn, tmp_path):
    """Se escribe a un temporal junto al destino y se pone en su sitio al
    final: si la escritura falla, el destino queda como estaba y el temporal
    no se queda en la carpeta. Un sustituto suelto no se puede escribir en
    UTF-8."""
    destino = tmp_path / "flujo.json"
    destino.write_bytes(b'{"antes": true}\n')
    with pytest.raises(UnicodeEncodeError):
        mn.escribir(destino, '{"nota": "a medias \ud800"}\n')
    assert destino.read_bytes() == b'{"antes": true}\n'
    assert [p.name for p in tmp_path.iterdir()] == ["flujo.json"]

    mn.escribir(destino, '{"despues": true}\n')
    assert destino.read_bytes() == b'{"despues": true}\n'
    assert [p.name for p in tmp_path.iterdir()] == ["flujo.json"]


def test_con_el_destino_de_solo_lectura_el_temporal_no_se_queda(mn, tmp_path, monkeypatch):
    """Al PONER valores, el temporal lleva los valores reales: si la escritura
    falla, no puede quedarse en la carpeta. Windows se niega a reemplazar un
    fichero de solo lectura, y el temporal, que copio sus permisos, tampoco se
    dejaba borrar. En los demas sistemas el reemplazo pisaria el fichero: alli
    se simula la negativa."""
    destino = tmp_path / "flujo.json"
    destino.write_bytes(b'{"antes": true}\n')
    os.chmod(destino, stat.S_IREAD)
    if os.name != "nt":
        def negarse(*a, **k):
            raise PermissionError("el destino es de solo lectura")
        monkeypatch.setattr(mn.os, "replace", negarse)
    try:
        with pytest.raises(OSError):
            mn.escribir(destino, '{"despues": "valor-real"}\n')
        assert [p.name for p in tmp_path.iterdir()] == ["flujo.json"]
        assert destino.read_bytes() == b'{"antes": true}\n'
    finally:
        os.chmod(destino, stat.S_IREAD | stat.S_IWRITE)


def test_la_cli_dice_el_error_si_lo_retirado_no_se_puede_escribir(
        mn, carpeta, valores, capsys):
    """Una descarga con un sustituto suelto escapado (`\\ud800`) en una nota:
    al reescribirla como se versiona sale el caracter, que no cabe en UTF-8.
    La orden sale con 1 y el destino, que existia, sigue como estaba."""
    flujo = json.loads(mn.aplicar(FLUJO, valores))
    flujo["nodes"][0]["notes"] = "a medias \ud800"
    (carpeta / "descarga.json").write_text(json.dumps(flujo), encoding="utf-8")
    (carpeta / "destino.json").write_bytes(b"lo de antes\n")
    assert mn.main(["--valores", str(carpeta / "valores.json"), "--retirar",
                    "--entrada", str(carpeta / "descarga.json"),
                    "--salida", str(carpeta / "destino.json")]) == 1
    assert capsys.readouterr().err.startswith("ERROR: UnicodeEncodeError")
    assert (carpeta / "destino.json").read_bytes() == b"lo de antes\n"
    assert sorted(p.name for p in carpeta.iterdir()) == [
        "descarga.json", "destino.json", "entrada.json", "valores.json"]


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


def test_la_cli_dice_el_error_si_un_fichero_no_se_puede_leer(mn, carpeta, capsys):
    argumentos = ["--valores", str(carpeta / "valores.json"),
                  "--salida", str(carpeta / "salida.json")]
    assert mn.main(argumentos + ["--entrada", str(carpeta / "no-existe.json")]) == 1
    assert capsys.readouterr().err.startswith("ERROR: FileNotFoundError")
    (carpeta / "latin1.json").write_bytes('{"nota": "señal"}'.encode("latin-1"))
    assert mn.main(argumentos + ["--entrada", str(carpeta / "latin1.json")]) == 1
    assert capsys.readouterr().err.startswith("ERROR: UnicodeDecodeError")
    assert not (carpeta / "salida.json").exists()


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

Esperado: `32 errors`. Todas por lo mismo: la fixture `mn` no puede cargar el script
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

Al poner los valores no reformatea: sustituye texto y deja lo demas como
estaba, con los finales de linea en LF. Al retirarlos de un workflow, ademas,
lo deja como se versiona: solo con las cinco claves que se versionan (`name`,
`active`, `nodes`, `connections`, `settings`) y escrito como los de `n8n/`.
Una descarga de n8n trae tambien el `id` del workflow, su `versionId`, la
huella de la instancia (`meta`), datos de ejecuciones (`pinData`) y etiquetas:
identifican la instancia y no se versionan. Tambien vacia el `chat_equipo` del
nodo `Configuracion` (el chat_id de una persona, que se rellena en n8n).

`--retirar` trabaja con UN workflow cada vez: una lista (como exporta la linea
de ordenes de n8n) o un JSON sin `nodes` no se retiran. Y no escribe si, tras
retirar, queda una credencial o una URL de webhook que no es un marcador: es
que los valores no son los de la instancia de la que viene la descarga. No usa
la red ni habla con n8n.
"""
from __future__ import annotations

import argparse
import difflib
import io
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import urllib.parse
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

# Lo que se versiona de un workflow, y en este orden. Lo demas que trae una
# descarga de n8n es de la instancia.
CLAVES_DEL_WORKFLOW = ("name", "active", "nodes", "connections", "settings")

# Un valor con alguno de estos caracteres romperia el JSON al sustituirlo.
_PROHIBIDOS = re.compile(r'["\\\x00-\x1f]')

# La forma de un marcador. Una clave de los valores que NO la tiene no se
# repite en ningun mensaje: puede ser un valor real.
_FORMA_DE_MARCADOR = re.compile(
    r"CRED_[A-Z0-9_]+|bot-[a-z]+|https?://[A-Za-z0-9.-]*ejemplo\.test")


class ErrorDeMarcadores(ValueError):
    """Los valores o la entrada no permiten una sustitucion sin ambiguedad."""


def marcadores_de(texto: str) -> set:
    """Los marcadores conocidos que aparecen en `texto`."""
    return {m for m in MARCADORES if m in texto}


def _nombres(marcadores) -> str:
    return ", ".join(sorted(marcadores))


def _es_url_base(url: str) -> bool:
    """Esquema `http` o `https` y host (con su puerto, si lo lleva), y nada
    mas: ni ruta, ni consulta, ni fragmento, ni barra final, ni usuario, ni
    blancos."""
    if re.search(r"[\s?#]", url) or url.endswith("/"):
        return False
    try:
        partes = urllib.parse.urlsplit(url)
        partes.port  # un puerto que no es un numero lanza ValueError
    except ValueError:
        return False
    return (partes.scheme in ("http", "https") and bool(partes.hostname)
            and "@" not in partes.netloc and not partes.path)


def _validar(valores: dict) -> None:
    if not isinstance(valores, dict):
        raise ErrorDeMarcadores("los valores tienen que ser un objeto JSON "
                                "{marcador: valor}")
    desconocidos = set(valores) - set(MARCADORES)
    if desconocidos:
        # Ninguna clave se repite: con el fichero escrito al reves, {valor
        # real: marcador}, el mensaje los imprimiria todos, y una clave con
        # forma de marcador (`bot-...`) tambien puede ser un nombre real. De
        # las que tienen esa forma se dice el marcador conocido mas parecido.
        erratas = [d for d in desconocidos
                   if isinstance(d, str) and _FORMA_DE_MARCADOR.fullmatch(d)]
        n = len(desconocidos)
        mensaje = (f"marcadores desconocidos en los valores: {n} "
                   + ("clave desconocida, que no se repite"
                      if n == 1 else "claves desconocidas, que no se repiten")
                   + " aqui")
        if erratas:
            parecidos = sorted({m for d in erratas
                                for m in difflib.get_close_matches(d, MARCADORES, n=1)})
            mensaje += (f"; {len(erratas)} con forma de marcador"
                        + (f", ¿erratas de {_nombres(parecidos)}?" if parecidos
                           else ", sin ningun marcador conocido parecido"))
        otras = n - len(erratas)
        if otras:
            mensaje += (f"; {otras} "
                        + ("clave que no es un marcador ni lo parece"
                           if otras == 1 else
                           "claves que no son marcadores ni lo parecen")
                        + ": las claves son los marcadores y los valores, "
                        "los de la instancia; ¿esta el fichero al reves?")
        raise ErrorDeMarcadores(mensaje)
    for marcador, valor in valores.items():
        if not isinstance(valor, str) or not valor.strip():
            raise ErrorDeMarcadores(f"el valor de {marcador} esta vacio")
        if valor != valor.strip() or _PROHIBIDOS.search(valor):
            raise ErrorDeMarcadores(
                f"el valor de {marcador} lleva espacios en los extremos, "
                "comillas, barras invertidas o caracteres de control")
    url = valores.get(URL_N8N)
    if url is not None and not _es_url_base(url):
        raise ErrorDeMarcadores(
            f"el valor de {URL_N8N} tiene que ser la URL base de n8n: esquema "
            "(http o https) y host, sin ruta, consulta, fragmento ni barra "
            "final")
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
    """El fichero en UTF-8 con los finales de linea en LF, venga como venga, y
    sin la marca de orden de bytes si la lleva (PowerShell 5.1 la pone)."""
    with io.open(ruta, encoding="utf-8-sig", newline="") as f:
        return f.read().replace("\r\n", "\n")


def _borrar(temporal) -> None:
    """Borra el temporal aunque haya copiado el solo lectura del destino: en
    Windows un fichero de solo lectura no se deja borrar."""
    try:
        os.chmod(temporal, stat.S_IREAD | stat.S_IWRITE)
    except OSError:
        pass
    try:
        os.unlink(temporal)
    except OSError:
        pass  # el error que cuenta es el de la escritura, que se relanza


def escribir(ruta, texto: str) -> None:
    """Escribe a un temporal junto al destino y lo pone en su sitio al final:
    si la escritura falla, el destino queda como estaba y el temporal se
    borra siempre (al poner valores, lleva los reales)."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, temporal = tempfile.mkstemp(dir=ruta.parent, prefix=f".{ruta.name}.",
                                    suffix=".tmp")
    try:
        with io.open(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        # el temporal nace legible solo por su propietario: el fichero
        # conserva los permisos que tenia, o los de uno nuevo
        if ruta.exists():
            shutil.copymode(ruta, temporal)
        else:
            os.chmod(temporal, 0o644)
        os.replace(temporal, ruta)
    except BaseException:
        _borrar(temporal)
        raise


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


def como_se_versiona(datos) -> tuple:
    """(texto, claves quitadas) de un workflow tal como se versiona: solo con
    `CLAVES_DEL_WORKFLOW`, en ese orden, y escrito como los de `n8n/`. Lo que
    no es un workflow (no tiene `nodes`) no se toca: devuelve (None, [])."""
    if not isinstance(datos, dict) or "nodes" not in datos:
        return None, []
    sobran = sorted(set(datos) - set(CLAVES_DEL_WORKFLOW))
    limpio = {c: datos[c] for c in CLAVES_DEL_WORKFLOW if c in datos}
    return json.dumps(limpio, ensure_ascii=False, indent=2) + "\n", sobran


def _vaciar_chat_equipo(datos: dict) -> bool:
    """Vacia el `value` de la asignacion `chat_equipo` del nodo
    `Configuracion`: es el chat_id de una persona, se rellena en n8n y no se
    versiona. Devuelve si llevaba algo. Sin ese nodo no hace nada."""
    vaciado = False
    for nodo in datos.get("nodes") or []:
        if not isinstance(nodo, dict) or nodo.get("name") != "Configuracion":
            continue
        asignaciones = (((nodo.get("parameters") or {}).get("assignments")
                         or {}).get("assignments") or [])
        for asignacion in asignaciones:
            if (isinstance(asignacion, dict)
                    and asignacion.get("name") == "chat_equipo"
                    and asignacion.get("value") != ""):
                asignacion["value"] = ""
                vaciado = True
    return vaciado


# Una URL hasta su `/webhook/`, en cualquier texto de un nodo (la URL de una
# sonda, la nota de un webhook con su orden de `setWebhook`...). No cruza
# blancos, comillas ni los signos que la cierran en una orden o en Markdown.
_URL_HASTA_EL_WEBHOOK = re.compile(
    r"https?://[^\s\"'`<>()\[\]{}|\\^]*?/webhook/", re.IGNORECASE)


def _textos(valor):
    """Todas las cadenas de un valor de JSON: claves y valores, a cualquier
    profundidad."""
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for clave, dentro in valor.items():
            yield from _textos(clave)
            yield from _textos(dentro)
    elif isinstance(valor, list):
        for dentro in valor:
            yield from _textos(dentro)


def _lo_que_no_es_marcador(datos: dict) -> list:
    """De un workflow ya retirado, lo que sigue siendo de la instancia: una
    credencial cuyo `id` no es un marcador conocido (y en las de Telegram, su
    `name`), o una URL de webhook, en cualquier texto del nodo, que no es el
    marcador de la URL seguido de `/webhook/`. Se dice el nodo y que es, nunca
    el valor."""
    hallados = []
    for nodo in datos.get("nodes") or []:
        if not isinstance(nodo, dict):
            continue
        nombre = nodo.get("name")
        for tipo, credencial in (nodo.get("credentials") or {}).items():
            credencial = credencial if isinstance(credencial, dict) else {}
            if credencial.get("id") not in MARCADORES:
                hallados.append(f"«{nombre}»: el id de su credencial {tipo}")
            if tipo == "telegramApi" and credencial.get("name") not in MARCADORES:
                hallados.append(f"«{nombre}»: el nombre de su credencial {tipo}")
        if any(m.group(0) != URL_N8N + "/webhook/"
               for texto in _textos(nodo)
               for m in _URL_HASTA_EL_WEBHOOK.finditer(texto)):
            hallados.append(f"«{nombre}»: la URL de su webhook")
    return hallados


def _dentro_del_repositorio(ruta: Path) -> bool:
    try:
        ruta.resolve().relative_to(REPO)
    except ValueError:
        return False
    return True


def convertir(entrada, salida, valores: dict, quitar: bool = False) -> dict:
    """Lee `entrada`, pone o quita los valores y escribe `salida`. Devuelve
    {marcador: veces} de lo sustituido; al retirar, ademas, en la clave
    `"claves quitadas"`, las del nivel superior que no se versionan, y en
    `"chat_equipo vaciado"`, si se vacio."""
    entrada, salida = Path(entrada), Path(salida)
    if not quitar and entrada.resolve() == salida.resolve():
        raise ErrorDeMarcadores(
            "la salida no puede ser la entrada al poner los valores reales: "
            "el export versionado se quedaria con ellos")
    if not quitar and _dentro_del_repositorio(salida):
        raise ErrorDeMarcadores(
            "al poner los valores reales la salida tiene que quedar FUERA del "
            "repositorio (una carpeta temporal): dentro estaria a un `git "
            "add` de distancia")
    texto = leer(entrada)
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ErrorDeMarcadores(f"{entrada} no es un JSON valido: {e}") from e
    if quitar:
        if isinstance(datos, list):
            raise ErrorDeMarcadores(
                f"{entrada} es una lista, no un workflow (asi exporta la linea "
                "de ordenes de n8n): --retirar trabaja con un workflow cada "
                "vez; pasa cada uno en su fichero, como lo descarga el editor "
                "de n8n")
        if not isinstance(datos, dict) or "nodes" not in datos:
            raise ErrorDeMarcadores(
                f"{entrada} no es un workflow (no tiene `nodes`): --retirar "
                "trabaja con un workflow cada vez, como lo descarga el editor "
                "de n8n")
        chat_vaciado = _vaciar_chat_equipo(datos)
        texto, quitadas = como_se_versiona(datos)
        resultado = retirar(texto, valores)
        restos = _lo_que_no_es_marcador(json.loads(resultado))
        if restos:
            raise ErrorDeMarcadores(
                "tras retirar quedan en el workflow cosas que no son "
                "marcadores, y no se escribe nada (¿son los valores los de la "
                "instancia de la que viene la descarga?): " + "; ".join(restos))
        veces = {m: texto.count(v) for m, v in valores.items() if v in texto}
        veces["claves quitadas"] = quitadas
        veces["chat_equipo vaciado"] = chat_vaciado
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
    except (OSError, UnicodeError) as e:
        # un fichero que no existe, que no se puede escribir, que no es UTF-8
        # o un texto que no cabe en UTF-8 (un sustituto suelto)
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    quitadas = veces.pop("claves quitadas", [])
    chat_vaciado = veces.pop("chat_equipo vaciado", False)
    verbo = "retirados" if a.retirar else "puestos"
    for marcador in MARCADORES:
        if marcador in veces:
            print(f"{marcador}: {veces[marcador]}")
    if quitadas:
        print("claves de la instancia que no se versionan, quitadas: "
              + ", ".join(quitadas))
    if chat_vaciado:
        print("chat_equipo: vaciado (se rellena en n8n; manual de operacion, "
              "§5, paso 1)")
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

Esperado: `32 passed`.

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

# Cuantas veces aparece cada marcador en cada workflow. Un marcador de mas es
# una cadena nueva que `aplicar` sustituiria sin avisar al desplegar: si cae
# en el `jsCode` de un nodo, cambia el programa del bot.
VECES = {
    "copiloto-paciente.json": {
        "https://n8n.ejemplo.test": 1, "CRED_TELEGRAM_PACIENTE": 12,
        "CRED_POSTGRES_COPILOTO": 5, "CRED_SECRETO_PACIENTE": 1, "bot-paciente": 12},
    "copiloto-profesional.json": {
        "https://n8n.ejemplo.test": 1, "CRED_TELEGRAM_PROFESIONAL": 9,
        "CRED_POSTGRES_COPILOTO": 5, "CRED_SECRETO_PROFESIONAL": 1, "bot-profesional": 9},
    "copiloto-mantenimiento.json": {
        "https://n8n.ejemplo.test": 2, "CRED_TELEGRAM_AVISOS": 1,
        "CRED_POSTGRES_COPILOTO": 4, "bot-avisos": 2},
}

# Lo que no es de la instancia y por eso se queda como esta: el copiloto se
# llama por el nombre de su servicio en la red de Docker.
URL_INTERNA = "http://copiloto-mcp:8000/"


def _nodos(fichero):
    return json.loads((N8N / fichero).read_text(encoding="utf-8"))["nodes"]


@pytest.mark.parametrize("fichero", FLUJOS)
def test_las_credenciales_de_los_workflows_son_marcadores(mn, fichero):
    # Si falla se dice el nodo, y no la credencial que lleva: lo que imprime
    # una prueba tambien se puede publicar.
    vistas = {}
    for n in _nodos(fichero):
        for tipo, c in (n.get("credentials") or {}).items():
            assert set(c) == {"id", "name"}, (n["name"], sorted(c))
            vistas.setdefault(tipo, []).append((n["name"], c["id"], c["name"]))
    esperadas = CREDENCIALES[fichero]
    assert set(vistas) == set(esperadas)
    for tipo, (ident, nombre, cuantos) in esperadas.items():
        con_otra = [nodo for nodo, i, nm in vistas[tipo] if (i, nm) != (ident, nombre)]
        assert con_otra == [], (fichero, tipo)
        nodos = len(vistas[tipo])
        assert nodos == cuantos, (fichero, tipo)
        assert ident in mn.MARCADORES


@pytest.mark.parametrize("fichero", FLUJOS)
def test_cada_marcador_aparece_las_veces_previstas(mn, fichero):
    texto = mn.leer(N8N / fichero)
    assert {m: texto.count(m) for m in mn.marcadores_de(texto)} == VECES[fichero]


@pytest.mark.parametrize("fichero", FLUJOS)
def test_los_workflows_se_versionan_solo_con_sus_cinco_claves(mn, fichero):
    """Una descarga de n8n trae ademas el `id` del workflow, su `versionId`,
    la huella de la instancia (`meta`), `pinData` y `tags`: son de la
    instancia, como el dominio. Y lo versionado esta escrito de una sola
    manera, la de `como_se_versiona`."""
    texto = mn.leer(N8N / fichero)
    assert tuple(json.loads(texto)) == mn.CLAVES_DEL_WORKFLOW
    assert mn.como_se_versiona(json.loads(texto)) == (texto, [])


@pytest.mark.parametrize("fichero", FLUJOS)
def test_las_url_de_los_nodos_http_son_el_marcador_o_la_interna(mn, fichero):
    for n in _nodos(fichero):
        if n["type"] != "n8n-nodes-base.httpRequest":
            continue
        url = n["parameters"]["url"]
        conocida = (url.startswith(mn.URL_N8N + "/webhook/")
                    or url.startswith(URL_INTERNA))
        assert conocida, (fichero, n["name"])


def test_las_dos_sondas_apuntan_al_marcador(mn):
    sondas = {n["name"]: n["parameters"]["url"]
              for n in _nodos("copiloto-mantenimiento.json")
              if n["type"] == "n8n-nodes-base.httpRequest"
              and "/webhook/" in n["parameters"]["url"]}
    esperadas = {
        "Webhook del paciente": "https://n8n.ejemplo.test/webhook/copiloto-paciente",
        "Webhook del profesional": "https://n8n.ejemplo.test/webhook/copiloto-profesional",
    }
    assert sorted(sondas) == sorted(esperadas)
    a_otro_sitio = [nombre for nombre in esperadas if sondas[nombre] != esperadas[nombre]]
    assert a_otro_sitio == []


@pytest.mark.parametrize("fichero, ruta, token", [
    ("copiloto-paciente.json", "copiloto-paciente", "<TOKEN>"),
    ("copiloto-profesional.json", "copiloto-profesional",
     "<TOKEN_DEL_BOT_DEL_PROFESIONAL>"),
])
def test_la_nota_del_webhook_registra_con_el_marcador(fichero, ruta, token):
    (nota,) = [n["notes"] for n in _nodos(fichero)
               if n["type"] == "n8n-nodes-base.webhook"]
    con_el_marcador = (f'"https://api.telegram.org/bot{token}/setWebhook" '
                       f"-d url=https://n8n.ejemplo.test/webhook/{ruta} ") in nota
    assert con_el_marcador, fichero


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
def test_retirar_una_descarga_de_n8n_quita_lo_que_es_de_la_instancia(
        mn, fichero, tmp_path, capsys):
    """Como lo descarga n8n: con su id, su version, la huella de la instancia,
    datos de una ejecucion y etiquetas; con las claves en otro orden y con
    otra sangria. Lo que sale es, letra por letra, lo versionado."""
    ejemplo = mn.leer_valores(EJEMPLO)
    versionado = mn.leer(N8N / fichero)
    desplegado = json.loads(mn.aplicar(versionado, ejemplo))
    descarga = {"id": "wf-de-la-instancia", "versionId": "version-de-la-instancia",
                "meta": {"instanceId": "huella-de-la-instancia"},
                "pinData": {"Un nodo": [{"json": {"dato": "de-una-ejecucion"}}]},
                "tags": [{"id": "etiqueta-de-la-instancia", "name": "produccion"}]}
    descarga.update({c: desplegado[c] for c in reversed(mn.CLAVES_DEL_WORKFLOW)})
    (tmp_path / "descarga.json").write_text(
        json.dumps(descarga, ensure_ascii=False, indent=4), encoding="utf-8")

    assert mn.main(["--valores", str(EJEMPLO), "--retirar",
                    "--entrada", str(tmp_path / "descarga.json"),
                    "--salida", str(tmp_path / "versionable.json")]) == 0

    # sobre un booleano: pytest enseñaria la linea que difiere, y en lo
    # versionado podria ir un valor (un chat_equipo relleno)
    igual = mn.leer(tmp_path / "versionable.json") == versionado
    assert igual, IGUAL_A_LO_VERSIONADO
    dicho = capsys.readouterr().out
    assert "quitadas: id, meta, pinData, tags, versionId" in dicho
    for de_la_instancia in ("wf-de-la-instancia", "version-de-la-instancia",
                            "huella-de-la-instancia", "de-una-ejecucion",
                            "etiqueta-de-la-instancia"):
        assert de_la_instancia not in dicho
        assert de_la_instancia not in mn.leer(tmp_path / "versionable.json")


def _descarga(mn, fichero, valores, **en_la_instancia):
    """Un workflow versionado como lo descarga n8n de una instancia con estos
    `valores`: puestos, con las claves de la instancia y lo que se le pase."""
    desplegado = json.loads(mn.aplicar(mn.leer(N8N / fichero), valores))
    desplegado.update({"id": "wf-de-la-instancia",
                       "versionId": "version-de-la-instancia"}, **en_la_instancia)
    return desplegado


def _chat_equipo(flujo):
    """Las asignaciones `chat_equipo` del nodo `Configuracion`."""
    return [a for n in flujo["nodes"] if n["name"] == "Configuracion"
            for a in n["parameters"]["assignments"]["assignments"]
            if a["name"] == "chat_equipo"]


def test_retirar_el_mantenimiento_vacia_el_chat_del_equipo(mn, valores, tmp_path, capsys):
    """Desplegado, `chat_equipo` va relleno en n8n (§5 del manual): es el
    chat_id de una persona y no se versiona. Al retirar se vacia, y la orden
    lo dice sin repetirlo."""
    chat = "4455667788"   # inventado
    descarga = _descarga(mn, "copiloto-mantenimiento.json", valores)
    (asignacion,) = _chat_equipo(descarga)
    asignacion["value"] = chat
    (tmp_path / "valores.json").write_text(json.dumps(valores), encoding="utf-8")
    (tmp_path / "descarga.json").write_text(json.dumps(descarga, indent=4),
                                            encoding="utf-8")

    assert mn.main(["--valores", str(tmp_path / "valores.json"), "--retirar",
                    "--entrada", str(tmp_path / "descarga.json"),
                    "--salida", str(tmp_path / "versionable.json")]) == 0

    escrito = mn.leer(tmp_path / "versionable.json")
    igual = escrito == mn.leer(N8N / "copiloto-mantenimiento.json")
    assert igual, IGUAL_A_LO_VERSIONADO
    dicho = capsys.readouterr()
    assert "chat_equipo: vaciado" in dicho.out
    assert chat not in escrito and chat not in dicho.out + dicho.err


def test_el_chat_del_equipo_del_mantenimiento_versionado_va_vacio():
    """El manual manda correr este fichero despues de retirar un export: asi
    caza un `chat_equipo` relleno sin tener que nombrar
    `tests/test_mantenimiento.py`. Si falla no enseña el valor."""
    flujo = json.loads((N8N / "copiloto-mantenimiento.json").read_text(encoding="utf-8"))
    asignaciones = _chat_equipo(flujo)
    assert len(asignaciones) == 1
    vacio = asignaciones[0]["value"] == ""
    assert vacio, ("chat_equipo va relleno en n8n/copiloto-mantenimiento.json: "
                   "retira el export con scripts/marcadores_n8n.py, que lo vacia")


@pytest.mark.parametrize("fichero", FLUJOS)
def test_retirar_con_otros_valores_que_los_de_la_descarga_no_escribe(
        mn, fichero, valores, tmp_path, capsys):
    """Con unos valores que no son los de la instancia (los de ejemplo, un
    `valores.local.json` anticuado) no se sustituye nada, y el workflow se
    escribiria en `n8n/` con los identificadores de la instancia. Tras
    retirar, las credenciales y las URL de los webhooks tienen que ser
    marcadores: si no, no se escribe, y el error dice el nodo y no el valor."""
    ejemplo = mn.leer_valores(EJEMPLO)
    (tmp_path / "descarga.json").write_text(
        json.dumps(_descarga(mn, fichero, valores), indent=4), encoding="utf-8")

    assert mn.main(["--valores", str(EJEMPLO), "--retirar",
                    "--entrada", str(tmp_path / "descarga.json"),
                    "--salida", str(tmp_path / "versionable.json")]) == 1

    assert not (tmp_path / "versionable.json").exists()
    dicho = capsys.readouterr()
    for valor in list(valores.values()) + list(ejemplo.values()):
        assert valor not in dicho.err + dicho.out
    assert "no son marcadores" in dicho.err
    # el nodo, que es del workflow versionado
    telegram = {"copiloto-paciente.json": "Pedir consentimiento",
                "copiloto-profesional.json": "Pedir codigo",
                "copiloto-mantenimiento.json": "Avisar al equipo"}[fichero]
    assert telegram in dicho.err
    if fichero == "copiloto-mantenimiento.json":
        assert "Webhook del paciente" in dicho.err


# Una sola clave anticuada cada vez: el marcador cuyo valor esta mal en los
# valores con los que se retira, la frase del error de ESA condicion y un nodo
# que la lleva. Si una de las condiciones se quitara, su caso caeria.
ANTICUADAS = [
    ("copiloto-paciente.json", "CRED_POSTGRES_COPILOTO",
     "el id de su credencial postgres", "Leer sesion"),
    ("copiloto-paciente.json", "CRED_SECRETO_PACIENTE",
     "el id de su credencial httpHeaderAuth", "Webhook Telegram (paciente)"),
    ("copiloto-paciente.json", "CRED_TELEGRAM_PACIENTE",
     "el id de su credencial telegramApi", "Pedir consentimiento"),
    ("copiloto-paciente.json", "bot-paciente",
     "el nombre de su credencial telegramApi", "Pedir consentimiento"),
    # la URL solo esta en la nota del nodo webhook
    ("copiloto-paciente.json", "https://n8n.ejemplo.test",
     "la URL de su webhook", "Webhook Telegram (paciente)"),
    ("copiloto-profesional.json", "CRED_POSTGRES_COPILOTO",
     "el id de su credencial postgres", "Leer sesion y permiso"),
    ("copiloto-profesional.json", "CRED_SECRETO_PROFESIONAL",
     "el id de su credencial httpHeaderAuth", "Webhook Telegram (profesional)"),
    ("copiloto-profesional.json", "CRED_TELEGRAM_PROFESIONAL",
     "el id de su credencial telegramApi", "Pedir codigo"),
    ("copiloto-profesional.json", "bot-profesional",
     "el nombre de su credencial telegramApi", "Pedir codigo"),
    ("copiloto-profesional.json", "https://n8n.ejemplo.test",
     "la URL de su webhook", "Webhook Telegram (profesional)"),
    ("copiloto-mantenimiento.json", "CRED_POSTGRES_COPILOTO",
     "el id de su credencial postgres", "Limpieza"),
    ("copiloto-mantenimiento.json", "CRED_TELEGRAM_AVISOS",
     "el id de su credencial telegramApi", "Avisar al equipo"),
    ("copiloto-mantenimiento.json", "bot-avisos",
     "el nombre de su credencial telegramApi", "Avisar al equipo"),
    ("copiloto-mantenimiento.json", "https://n8n.ejemplo.test",
     "la URL de su webhook", "Webhook del paciente"),
]


@pytest.mark.parametrize("fichero, marcador, frase, nodo", ANTICUADAS,
                         ids=[f"{f.split('-')[1][:-5]}-{m}" for f, m, _, _ in ANTICUADAS])
def test_retirar_con_una_sola_clave_anticuada_no_escribe(
        mn, fichero, marcador, frase, nodo, valores, tmp_path, capsys):
    """El `valores.local.json` anticuado de verdad: todo bien menos UN valor
    (una credencial que se volvio a crear, una errata en la URL). Lo que no se
    sustituye se quedaria en `n8n/`: la herramienta se niega, sin escribir,
    diciendo la condicion y el nodo, y ningun valor."""
    anticuados = dict(valores)
    anticuados[marcador] = ("https://anticuada.inventado.test"
                            if marcador == mn.URL_N8N else "valor-99-anticuado")
    (tmp_path / "valores.json").write_text(json.dumps(anticuados), encoding="utf-8")
    (tmp_path / "descarga.json").write_text(
        json.dumps(_descarga(mn, fichero, valores), indent=4), encoding="utf-8")

    assert mn.main(["--valores", str(tmp_path / "valores.json"), "--retirar",
                    "--entrada", str(tmp_path / "descarga.json"),
                    "--salida", str(tmp_path / "versionable.json")]) == 1

    assert not (tmp_path / "versionable.json").exists()
    dicho = capsys.readouterr()
    con_valores = [m for m, v in list(valores.items()) + list(anticuados.items())
                   if v in dicho.out + dicho.err]
    assert con_valores == [], "la salida lleva el valor de estos marcadores"
    assert f"«{nodo}»: {frase}" in dicho.err


@pytest.mark.parametrize("fichero, nodo", [
    ("copiloto-paciente.json", "Webhook Telegram (paciente)"),
    ("copiloto-mantenimiento.json", "Webhook del paciente"),
])
def test_una_url_que_solo_empieza_como_el_marcador_no_es_el_marcador(
        mn, fichero, nodo, valores, tmp_path, capsys):
    """El marcador va seguido de `/webhook/`: un host que solo EMPIEZA como el
    del marcador es otro host."""
    otro_host = "https://n8n.ejemplo.test.otro"
    texto = mn.aplicar(mn.leer(N8N / fichero), valores).replace(
        valores[mn.URL_N8N], otro_host)
    (tmp_path / "valores.json").write_text(json.dumps(valores), encoding="utf-8")
    (tmp_path / "descarga.json").write_text(texto, encoding="utf-8")

    assert mn.main(["--valores", str(tmp_path / "valores.json"), "--retirar",
                    "--entrada", str(tmp_path / "descarga.json"),
                    "--salida", str(tmp_path / "versionable.json")]) == 1

    assert not (tmp_path / "versionable.json").exists()
    dicho = capsys.readouterr()
    assert f"«{nodo}»: la URL de su webhook" in dicho.err
    sin_el_host = "ejemplo.test.otro" not in dicho.out + dicho.err
    assert sin_el_host


@pytest.mark.parametrize("entrada, dice", [
    ([], "una lista"),
    (["un workflow", "otro"], "una lista"),
    ({"name": "sin nodos", "connections": {}}, "no es un workflow"),
    (json.loads(TEXTO), "no es un workflow"),
])
def test_lo_que_no_es_un_workflow_no_se_retira(mn, carpeta, entrada, dice, capsys):
    """La linea de ordenes de n8n exporta una LISTA de workflows; y un JSON
    sin `nodes` no es un workflow. `--retirar` no los reescribe ni los pasa
    por buenos: se niega, dice que se pase un workflow cada vez, y no escribe
    nada."""
    (carpeta / "export.json").write_text(json.dumps(entrada), encoding="utf-8")
    assert mn.main(["--valores", str(carpeta / "valores.json"), "--retirar",
                    "--entrada", str(carpeta / "export.json"),
                    "--salida", str(carpeta / "salida.json")]) == 1
    error = capsys.readouterr().err
    assert dice in error and "un workflow cada vez" in error
    assert not (carpeta / "salida.json").exists()
    # `como_se_versiona` no los toca
    assert mn.como_se_versiona(entrada) == (None, [])


# Las claves de `settings` que llevan hoy los tres workflows. Una que la
# instancia añada al descargar no pasa sin que alguien lo decida: la de
# `errorWorkflow`, por ejemplo, lleva el `id` de otro workflow de la instancia.
CLAVES_DE_SETTINGS = {
    "executionOrder", "executionTimeout", "saveDataErrorExecution",
    "saveDataSuccessExecution", "saveExecutionProgress", "saveManualExecutions",
    "timezone"}


def _settings_que_sobran(flujo):
    """Los NOMBRES de las claves de `settings` que no estan en la lista; los
    valores no, que pueden ser de la instancia."""
    return sorted(set(flujo["settings"]) - CLAVES_DE_SETTINGS)


@pytest.mark.parametrize("fichero", FLUJOS)
def test_las_claves_de_settings_son_las_de_hoy(fichero):
    flujo = json.loads((N8N / fichero).read_text(encoding="utf-8"))
    assert _settings_que_sobran(flujo) == [], fichero
    # y la comprobacion caza la que lleva el id de otro workflow
    con_error = dict(flujo, settings=dict(flujo["settings"],
                                          errorWorkflow="wf-de-la-instancia"))
    assert _settings_que_sobran(con_error) == ["errorWorkflow"]


@pytest.mark.parametrize("fichero", FLUJOS)
def test_la_cli_da_la_vuelta_a_un_workflow_entero(mn, fichero, tmp_path):
    valores = ["--valores", str(EJEMPLO)]
    assert mn.main(valores + ["--entrada", str(N8N / fichero),
                              "--salida", str(tmp_path / "puesto.json")]) == 0
    assert mn.main(valores + ["--retirar",
                              "--entrada", str(tmp_path / "puesto.json"),
                              "--salida", str(tmp_path / "vuelta.json")]) == 0
    igual = (tmp_path / "vuelta.json").read_text(encoding="utf-8") \
        == mn.leer(N8N / fichero)
    assert igual, IGUAL_A_LO_VERSIONADO
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
        # si falla se dice la sonda y no la URL que lleva
        al_marcador = p["url"] == f"https://n8n.ejemplo.test/webhook/{ruta}"
        assert al_marcador, nombre
```

La línea 228 (`assert usadas == {"postgres": {CRED_BD}, "telegramApi": {CRED_AVISOS}}, usadas`)
afirma lo mismo —usa las constantes, y con ellas pasa a afirmar los marcadores—, pero si falla
no imprime las credenciales que encontró: lo que imprime una prueba también se puede publicar.
Pasa a ser:

```python
    # si falla se dicen los tipos de credencial y cuantas hay de cada uno, no cuales
    las_de_sp3 = usadas == {"postgres": {CRED_BD}, "telegramApi": {CRED_AVISOS}}
    assert las_de_sp3, {tipo: len(ids) for tipo, ids in usadas.items()}
```

(c) En `tests/test_flujo_paciente.py`, el cuerpo de
`test_solo_se_usa_la_credencial_del_bot_del_paciente`: las cinco líneas que van de
`usadas = {c["id"]` (línea 453) a la aserción de la 457 (`assert usadas == {"…"}, usadas    # …`,
con un id de 16 caracteres y el nombre del bot en el comentario). Pasan a ser:

```python
    con_telegram = [(n["name"], c["id"])
                    for n in _flujo()["nodes"]
                    for t, c in (n.get("credentials") or {}).items()
                    if t == "telegramApi"]
    # El marcador (SP5 §6.1). Si falla se dicen los nodos y no la credencial
    # que llevan: lo que imprime una prueba tambien se puede publicar.
    con_otra = [nodo for nodo, c in con_telegram if c != "CRED_TELEGRAM_PACIENTE"]
    solo_la_suya = bool(con_telegram) and not con_otra
    assert solo_la_suya, con_otra
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
    # El marcador (SP5 §6.1). Si falla se dice cuantas credenciales distintas
    # hay y no cuales: lo que imprime una prueba tambien se puede publicar.
    solo_la_suya = usadas == {"CRED_TELEGRAM_PROFESIONAL"}
    assert solo_la_suya, f"{len(usadas)} credenciales de Telegram distintas"
```

Y la línea 790, en un docstring (empieza por `rotulaba «` y lleva el nombre del bot entre
comillas angulares), pasa a ser:

```python
    rotulaba «<bot del profesional>»; el camino realista al daño es que el clínico reenvíe
```

- [ ] **Paso 7: Correr las pruebas y verlas fallar**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_marcadores_n8n.py tests/test_mantenimiento.py tests/test_flujo_paciente.py tests/test_flujo_profesional.py`

Esperado: `18 failed, 114 passed, 20 skipped`. Los dieciocho:
- catorce de `tests/test_marcadores_n8n.py`: `test_cada_marcador_aparece_las_veces_previstas` (los tres
  ficheros), `test_las_credenciales_de_los_workflows_son_marcadores` (los tres
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

Esperado: `134 passed, 20 skipped` (58 de ellas son las de `tests/test_marcadores_n8n.py`).

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
IP privada) pasa a ser:

```javascript
    "Salud del copiloto": { error: "connect ECONNREFUSED 172.18.0.2:8000" },
```

- [ ] **Paso 12: Correr los cuatro `.mjs` y las pruebas que los lanzan**

Run: `node tests/decidir.mjs && node tests/formulario.mjs && node tests/mantenimiento.mjs && node tests/profesional.mjs`

Esperado: código de salida 0. La última línea de `decidir.mjs`, `mantenimiento.mjs` y
`profesional.mjs` es `TODO VERDE`; la de `formulario.mjs` es `16 OK`.

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_marcadores_n8n.py tests/test_mantenimiento.py tests/test_flujo_paciente.py tests/test_flujo_profesional.py tests/test_sql_de_los_nodos.py`

Esperado: `134 passed, 20 skipped`.

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
cadenas y, el de mantenimiento, en el `chat_equipo` del nodo `Configuracion`,
que en el repositorio va vacío (§5, paso 1).

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

**Después de importar, mirar en n8n que cada workflow usa SU bot.** El
repositorio ya no puede vigilarlo: qué credencial real hay detrás de cada
marcador lo dice `valores.local.json`, y si ahí se cruzan dos `id` —o se cuela
el de una credencial que no es del proyecto— la herramienta los pone sin
rechistar. Abre un nodo de Telegram de cada workflow y comprueba que la
credencial es la del bot del paciente en el del paciente, la del profesional en
el del profesional y la de pruebas y avisos en el de mantenimiento. La primera
vez, empieza por el de mantenimiento, que no atiende a nadie.

**Quitar los valores reales, ANTES de versionar un export.** El workflow se
descarga de n8n a la carpeta temporal y se deja en `n8n/` ya con marcadores:

```powershell
C:\venv-copiloto\Scripts\python.exe scripts/marcadores_n8n.py --retirar --entrada $env:TEMP\n8n-real\export.json --salida n8n/copiloto-mantenimiento.json
```

Una descarga de n8n trae más de lo que se versiona: el `id` del workflow, su
`versionId`, la huella de la instancia (`meta`), datos de ejecuciones
(`pinData`) y etiquetas. Identifican la instancia, como el dominio. Al retirar,
la herramienta se queda con las cinco claves que se versionan (`name`,
`active`, `nodes`, `connections` y `settings`), escribe el fichero como los de
`n8n/` y dice qué claves quitó. Y vacía el `chat_equipo` del workflow de
mantenimiento, que identifica a una persona: lo dice, sin repetir el valor.
Por eso, **después de importar ese workflow desde el repositorio hay que
volver a rellenarlo en n8n** (§5, paso 1): hasta entonces no llega ningún
aviso.

Después, `git diff n8n/` tiene que enseñar solo lo que se cambió a propósito
en el workflow, y estas dos pruebas tienen que pasar:

```powershell
C:\venv-copiloto\Scripts\python.exe -m pytest -rs tests/test_marcadores_n8n.py tests/test_anonimato.py
```

La primera caza lo que la herramienta no conoce y tiene forma de
identificador: el `id` de una credencial que se volvió a crear y no está en
`valores.local.json` (en los workflows versionados las credenciales solo
pueden ser marcadores, y cada marcador aparece las veces previstas). La
herramienta ya se niega a escribir un export así; la prueba es la segunda red,
para lo que llegue a `n8n/` por otro camino. La
segunda mira el árbol entero contra las huellas: caza lo que la lista conoce
y está escrito de otra forma, como el dominio con otro subdominio. En el
repositorio publicado `huellas.txt` lleva solo la huella del centinela y esa
parte **se salta** (lo dice el `-rs` de la orden): allí la comprobación del
árbol es `scripts/verificar_anonimato.py` con las huellas del repositorio de
desarrollo (`tests/anonimato/README.md`). Ninguna de las dos caza un
identificador nuevo que nadie haya puesto en la lista: para eso está el
`git diff`. Si enseña de más, no se versiona hasta entender por qué. Al
terminar se borra la carpeta temporal.

La primera vez que se exporte un workflow que no se ha desplegado todavía desde
el repositorio, sus notas llevan aún el texto de antes de los marcadores. En el
del profesional eso se ve en dos sitios —la nota del webhook y un comentario
del nodo `Desenlace`—, donde el `git diff` enseñará un texto distinto del
versionado: se corrige a mano con el del repositorio, o se despliega antes
desde el repositorio y se exporta después.

El script se niega —sin escribir nada— si en `valores.local.json` falta un
marcador, si dos marcadores comparten valor, si el valor de la URL de n8n lleva
una ruta, si al poner los valores la salida es el propio fichero de entrada o
cae dentro del repositorio, o si tras retirar queda algún valor real escrito de
otra forma (en mayúsculas, o el dominio sin el `https://`); en ese último caso
dice la línea, y se corrige a mano. Al retirar se niega además si la entrada no
es UN workflow (la descarga de varios, que es una lista, se pasa de uno en
uno), y si después de retirar queda una credencial o una URL de webhook que no
es un marcador: los valores de `valores.local.json` no son los de esa
descarga. Ningún mensaje suyo repite un valor real: dice el marcador, el nodo o
la línea.
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

Esperado: `134 passed, 20 skipped`. Antes de la tarea, esos mismos ficheros (sin el nuevo) daban
`76 passed, 20 skipped`: las 58 de diferencia son las de `tests/test_marcadores_n8n.py`, y no hay
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
falla si en algo de lo que se publicaría aparece un token de la lista negra,
y un script que hace lo mismo desde la línea de órdenes, más los secretos y
el commit, antes de publicar. La lista negra en claro NO vive en el
repositorio: el repositorio lleva solo `tests/anonimato/huellas.txt`, con el
sha256 de cada token.

Esta tarea deja el script, las huellas y todas las pruebas que NO miran el
árbol de verdad: la suite queda verde. Las pruebas que exigen el árbol limpio
entran al final de la tarea 6, cuando ya no queda nada que quitar; antes la
de las huellas fallaría, y tiene que fallar.

El script es la última barrera antes de publicar, y su primer diseño dejaba
pasar cosas que se publican. Lo que sigue es el que quedó después de dos
rondas de revisión y de la tanda de la revisión final (tarea 9); las
decisiones de más abajo dicen qué cambió y por qué.

**Ficheros:**
- Crear: `scripts/verificar_anonimato.py`
- Crear: `tests/test_anonimato.py`
- Crear: `tests/anonimato/huellas.txt` (generado desde la lista en claro; no
  se cita en este plan)
- Modificar: `.gitignore` (un bloque nuevo al final)

**Interfaces:**
- Consume: nada de `src/`. Solo la biblioteca estándar y `git` en el PATH. La
  lista en claro, fuera del repositorio (`ANONIMATO_LISTA`), solo para
  regenerar las huellas.
- Produce, en `scripts/verificar_anonimato.py`:
  - constantes `CENTINELA = "centinelaanonimato7f3a"`, `HUELLAS_POR_DEFECTO`
    (`tests/anonimato/huellas.txt` del repositorio donde vive el script),
    `VARIABLE_DE_LA_LISTA = "ANONIMATO_LISTA"`, `COPIA`, `INDICE` y `COMMIT`
    (de dónde sale cada hallazgo), `PATRONES_DE_SECRETO`,
    `CONTRASENAS_DE_EJEMPLO`, `FICHEROS_PROHIBIDOS`, `FICHEROS_PERMITIDOS`,
    `CAMPOS_DEL_COMMIT`, `CABECERAS_DEL_COMMIT`.
  - `tokens(texto) -> set[str]`, `huella(token) -> str`,
    `leer_huellas(ruta) -> set[str]` (`ValueError` si una línea no es una
    huella), `huellas_de_la_lista(huellas) -> set[str]` (las huellas sin la
    del centinela), `leer_lista(ruta) -> list[str]`,
    `regenerar(lista, destino) -> int` (`ValueError`, sin escribir nada, si
    una entrada no da exactamente un token) y
    `regenerar_solo_centinela(destino) -> int` (el `huellas.txt` del
    repositorio que se publica).
  - `ficheros_versionados(raiz) -> list[Path]` (rutas absolutas: en un
    repositorio, lo que tiene seguimiento y lo que no lo tiene ni está
    ignorado), `es_texto(ruta) -> bool`, `binarios(raiz) -> list[Path]`.
  - `buscar_huellas(raiz, huellas, commit=None) -> list[dict]` con las claves
    `fichero` (ruta relativa con `/`, con los tokens tapados), `linea` (0 =
    el nombre del fichero), `huella` y `origen`.
  - `buscar_secretos(raiz, huellas=None, commit=None) -> list[dict]` con las
    claves `fichero`, `linea` (0 = el fichero entero o su nombre), `clase` y
    `origen`. La clase es una clave de `PATRONES_DE_SECRETO`, o
    `contrasena_en_url`, `asignacion_de_secreto`, `fichero_prohibido` o
    `no_recorrido`.
  - `verificar_commit(raiz, revision="HEAD", huellas=None) -> list[dict]` con
    las claves `campo` (`autor`, `correo_de_autor`, `quien_confirma`,
    `correo_de_quien_confirma`, `mensaje`), `linea` (la del mensaje; 0 en los
    demás) y `huella` o `clase`.
  - `verificar_referencias(raiz, huellas) -> list[dict]` con las claves
    `referencia` (`rama` o `etiqueta`), `nombre` (tapado) y `huella` o
    `clase` (la del secreto).
  - `cabeceras_del_commit(raiz, revision="HEAD", huellas=None,
    un_solo_commit=False) -> list[dict]` con las claves `campo` (el NOMBRE
    de la cabecera), `linea` (0) y `clase` (`cabecera_del_commit`).
  - `commits(raiz) -> int` (los que alcanza cualquier referencia),
    `ramas(raiz) -> int`, `etiquetas(raiz) -> int`.
  - `main(argv=None) -> int` con `--raiz`, `--huellas`, `--commit [REV]`,
    `--un-solo-commit` (implica `--commit HEAD`), `--regenerar`, `--lista` y
    `--solo-centinela` (con `--regenerar` y `--huellas`). Devuelve 0 sin
    hallazgos; 1 con ellos, si no se recorrió ningún fichero de texto, o
    (con `SystemExit`) si las huellas son solo la del centinela. Con
    `--un-solo-commit` da además los hallazgos de clase `huella_publicada`.
- Produce, en `tests/test_anonimato.py`: `va` (el script cargado por ruta),
  `RAIZ`, `HUELLAS`, `solo_el_centinela(ruta=HUELLAS) -> bool` y
  `SIN_LA_LISTA` (un motivo por cada sitio que se salta con solo el
  centinela: `"huellas.txt"`, `"arbol"` y `"metadatos"`; cada uno dice lo que
  de verdad se queda sin verificar). Los usan las tareas 6 y 7.

**Decisiones de esta tarea** (donde el contrato dejaba margen):
- **Se recorre lo que se publicaría, no lo que hay versionado.** En la raíz
  de un repositorio: la copia de trabajo (lo que tiene seguimiento y lo que
  no lo tiene ni está ignorado, que un `git add -A` añadiría), lo preparado
  en el índice que no es lo que hay en disco y, con `--commit`, el árbol de
  ese commit. El mismo contenido no se recorre dos veces. Si `raiz` no es la
  raíz de un repositorio, todo lo que hay debajo salvo `.git/`: es el lado
  seguro.
- **Un recorrido vacío no es un árbol limpio.** Si no se recorrió ningún
  fichero de texto, la salida es 1.
- **Lo que no se puede mirar es un hallazgo**, no un silencio: un enlace
  simbólico, un submódulo, otro repositorio dentro, un fichero que no se deja
  leer. Clase `no_recorrido`.
- **El centinela no cuenta en el árbol.** Es público y el spec lo nombra en
  claro, así que su huella, que va siempre en `huellas.txt`, daría un hallazgo
  en el propio spec, en este plan y en la prueba. `huellas_de_la_lista()`
  la quita, y la usan las pruebas del árbol y la línea de órdenes. Las
  pruebas del centinela usan el conjunto entero sobre un árbol de juguete.
- **Con solo la huella del centinela no se comprueba nada** (es el
  `huellas.txt` del repositorio que se publica, D9): la línea de órdenes sale
  con 1 diciéndolo, y las pruebas que exigen la lista entera se saltan con el
  motivo `SIN_LA_LISTA`.
- **La tokenización** (D6) normaliza con NFKD y quita las marcas de
  combinación: las tildes y las letras de ancho completo dan las letras
  llanas. Los caracteres de formato (un espacio de ancho cero, un guion
  opcional) se tratan de las dos maneras, borrados y como separador. Y se
  tokeniza **también el texto desescapado**: un `\n` escrito con barra, un
  `%20` o una entidad HTML pegan letras al token y lo esconden.
- **Se tokeniza línea a línea**, para poder dar el número de línea. Un token
  partido por un salto de línea no se detecta: es un límite, y lo documenta
  la tarea 7.
- **Texto** es lo que tiene marca de orden de bytes (se lee en su
  codificación) o no lleva bytes nulos (se lee como UTF-8, y los bytes que no
  lo sean, como cp1252). Lo demás es binario: se declara y no se recorre.
- **El nombre también viaja** (línea 0): se tokeniza, y se le pasan los
  patrones de secretos. Lo mismo el nombre de las ramas y de las etiquetas,
  que se publican con el `push`.
- **El commit**: autor, quien confirma, sus correos y el mensaje, contra las
  huellas y contra los patrones de secretos; y sus **cabeceras**: la que no
  sea `tree`, `author` ni `committer` es un hallazgo, porque una firma lleva
  el identificador de la clave de quien firma (el commit único se hace con
  `--no-gpg-sign`). `--un-solo-commit` exige un commit contando lo que
  alcanza CUALQUIER referencia, una sola rama y ninguna etiqueta.
- **Las huellas no se publican** (D9). Con `--un-solo-commit`, que es la
  orden de publicar, una huella de la lista escrita en el árbol es un
  hallazgo de clase `huella_publicada`: el `huellas.txt` del árbol que se
  publica lleva solo la del centinela, y se escribe con
  `--regenerar --solo-centinela`. Sin `--un-solo-commit` no se mira: el árbol
  de desarrollo lleva su propio `huellas.txt`.
- **Secretos por patrón**: las clases de `PATRONES_DE_SECRETO` (el token de
  bot de Telegram, también pegado a `bot` —en cualquier caja— como va en la
  URL de su API, y con `%3A` en vez de los dos puntos; claves de API; JWT; la
  cabecera de una clave privada; una cabecera `Authorization` con un valor
  literal), la contraseña dentro de una URL y la **asignación de un
  secreto**: una clave que nombra un secreto con un valor que es un LITERAL
  que lo parece (8 o más caracteres, con letras y cifras) y no es de
  ejemplo. El NOMBRE de la clave lleva `password`, `passwd`, `secret`,
  `token` o `api_key`, o acaba en `_KEY` escrito en mayúsculas (la
  convención de las variables de entorno) o en una de seis terminaciones en
  minúsculas (`access_key`, `private_key`…): con `_key` a secas saltaban
  `cache_key` y `primary_key`. El valor ENTRE COMILLAS es una expresión solo
  si lleva `{{`, `${` o `$(`, o empieza por `=` (una expresión de n8n); el
  valor SUELTO, si lleva paréntesis, corchetes o llaves; y con subíndice o
  detrás de una coma, un valor sin comillas es una variable. Los patrones se
  pasan también por la línea con las comillas desescapadas: el texto de un
  JSON (una celda de un notebook, el código de un nodo de n8n).
- **Las líneas larguísimas.** El patrón de las asignaciones es cuadrático en
  las tiradas largas de letras, puntos y guiones: no se aplica a la línea que
  no lleva ninguna de sus palabras clave, ni el de la URL a la que no lleva
  `://`.
- **Contraseña en URL.** El árbol lleva seis apariciones, todas de ejemplo,
  con tres valores: `prueba`, `clave` y `token`. Los tres entran en
  `CONTRASENAS_DE_EJEMPLO` junto con `cambiar-esto`, `...` y `%s`; además se
  permiten los marcadores entre `<` y `>` y las variables `$X` y `${X}` (con
  el nombre en mayúsculas). Lo que va detrás de los dos puntos es un puerto y
  una ruta, y no una contraseña, solo si lo de delante parece un host (lleva
  un punto, o es `localhost`). Ningún fichero del árbol hay que cambiarlo por
  esto.
- **Ficheros prohibidos**: `.env` y sus variantes (salvo `.env.ejemplo`),
  ficheros de claves y de credenciales (`FICHEROS_PROHIBIDOS`). No distingue
  mayúsculas.
- **Los secretos de ejemplo de las pruebas se componen al correr**
  (`"sk" + "-" + …`). `tests/test_anonimato.py` y este plan también se
  recorren, y un secreto de ejemplo escrito entero haría saltar la prueba.
- **Las salidas no llevan nunca el token ni el secreto**: fichero, línea y los
  12 primeros caracteres de la huella, o la clase. En un nombre (de fichero,
  de rama, de etiqueta, la revisión que se pasa a `--commit`) el token sale
  tapado por el principio de su huella y el secreto por `<secreto>`. Las
  rutas salen relativas, y la de la lista en claro no se imprime nunca.

**Avisos para quien ejecuta:**
- Todas las órdenes se corren desde la raíz del repo.
- El código de esta sección se copia TAL CUAL. En particular, no «arregles»
  las cadenas partidas de los secretos de ejemplo ni escribas en ningún
  comentario una URL con usuario y contraseña: el fichero se recorre a sí
  mismo.
- La lista en claro vive fuera del repositorio. En las órdenes se escribe
  `ANONIMATO_LISTA=<lista en claro>`; su ruta no se escribe en ningún fichero
  del repo ni en ningún mensaje de commit. **Sin ella no se puede hacer el
  paso 5**: se le pide a quien la mantiene.
- No se escribe en ninguna salida, mensaje ni comentario ningún token de la
  lista. Los hallazgos se nombran por fichero, línea y huella.
- Las pruebas que usan `git` crean repositorios de juguete en el directorio
  temporal de pytest, con una configuración de git vacía: no tocan ni el
  repositorio ni la configuración de nadie. Sin `git` en el PATH se saltan.
- `tests/test_anonimato.py` tarda alrededor de un minuto: casi todo son los
  `git` de los repositorios de juguete.
- **El verificador mira también el índice.** Mientras un fichero arreglado no
  esté preparado con `git add`, lo que git tiene preparado sigue siendo lo
  de antes, y sigue dando el hallazgo.

- [ ] **Paso 1: Escribir las pruebas, que fallan**

Crear `tests/test_anonimato.py` con este contenido (todavía sin las pruebas
del árbol, que llegan en la tarea 6, ni las de lo que no es texto, que llegan
en la 7):

```python
"""Pruebas del anonimato del repositorio (spec de SP5 §6.1).

El repositorio se publica, y lo que se publica no puede llevar ninguna cadena
que identifique al cliente, a la empresa, a la maquina ni a los integrantes.
La lista de esas cadenas NO vive aqui: el repositorio lleva solo
`tests/anonimato/huellas.txt`, con el sha256 de cada token (el de desarrollo;
el que se publica lleva solo la del centinela, D9). Por eso estas pruebas
corren siempre, sin la lista: se prueban a si mismas con un token publico, el
centinela, cuya huella va siempre en el fichero.

Los secretos de ejemplo se COMPONEN al correr (`"sk" + "-" + ...`): este
fichero tambien se recorre, y un secreto de ejemplo escrito entero haria
saltar la misma prueba que lo usa.
"""
import base64
import binascii
import codecs
import hashlib
import importlib.util
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import time
import zlib
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
OTRO_MAS = "segundotoken5q"       # y un tercero

# De donde sale lo que se recorre (clave `origen` de cada hallazgo).
COPIA, INDICE, COMMIT = "copia de trabajo", "indice", "commit"


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
    assert va.tokens("name: ${RED_N8N:-uno_dos}") == {
        "name", "red", "n8n", "uno", "dos"}


def test_tokens_trocea_una_ruta_de_windows():
    assert va.tokens("C:\\Users\\u") == {"c", "users", "u"}


def test_tokens_quita_el_base64_largo_y_conserva_el_corto():
    largo = "iVBORw0KGgo" + "A" * 109            # 120 caracteres
    assert len(largo) == 120
    assert va.tokens(f'"image/png": "{largo}"') == {"image", "png"}
    corto = largo[:119]
    assert corto.lower() in va.tokens(f'"image/png": "{corto}"')


@pytest.mark.parametrize("texto", [
    pytest.param('{"notas": "linea uno\\n' + CENTINELA + '"}',
                 id="barra_n_en_json"),
    pytest.param('"columna\\t' + CENTINELA + '"', id="barra_t"),
    pytest.param("https://ejemplo.test/?q=%20" + CENTINELA,
                 id="por_ciento_20"),
    pytest.param("https:%2F%2F" + CENTINELA + ".test", id="por_ciento_2f"),
    pytest.param("&#99;" + CENTINELA[1:], id="entidad_decimal"),
    pytest.param("&#x63;" + CENTINELA[1:], id="entidad_hexadecimal"),
    pytest.param("\\u0063" + CENTINELA[1:], id="barra_u"),
])
def test_los_escapes_no_pegan_letras_al_token(tmp_path, texto):
    assert CENTINELA in va.tokens(texto)
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "a.json").write_text(texto + "\n", encoding="utf-8")
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [(h["fichero"], h["linea"]) for h in hallazgos] == [("a.json", 1)]


@pytest.mark.parametrize("texto", [
    pytest.param("".join(chr(ord(c) + 0xFEE0) for c in CENTINELA),
                 id="ancho_completo"),
    pytest.param(CENTINELA[:9] + "​" + CENTINELA[9:],
                 id="espacio_de_ancho_cero"),
    pytest.param(CENTINELA[:9] + "­" + CENTINELA[9:],
                 id="guion_blando"),
    pytest.param("﻿" + CENTINELA, id="marca_de_orden_pegada"),
    # R7: el caracter de formato tambien hace de separador (union).
    pytest.param("alfa​" + CENTINELA, id="formato_como_separador"),
    pytest.param(CENTINELA[:5] + "​" + CENTINELA[5:],
                 id="formato_dentro_del_token"),
])
def test_compatibilidad_y_caracteres_de_formato(texto):
    # NFKD descompone tambien el ancho completo; los caracteres de formato
    # (categoria Cf) se borran en vez de partir el token.
    assert CENTINELA in va.tokens(texto)


def test_tokens_une_el_texto_tal_cual_y_el_desescapado():
    assert va.tokens("uno\\ndos") == {"uno", "ndos", "dos"}
    assert va.tokens("a%20b &amp; c") == {"a", "20b", "b", "amp", "c"}


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
def solo_el_centinela(ruta=HUELLAS):
    """Si el fichero de huellas lleva solo la del centinela.

    Es el `huellas.txt` del repositorio que se publica (D9): alli la
    comprobacion de verdad se hace antes de publicar, con las huellas del
    repositorio de desarrollo, y lo que exige la lista entera se salta.
    """
    return va.leer_huellas(ruta) == {va.huella(CENTINELA)}


_SOLO_EL_CENTINELA = ("huellas.txt lleva solo la huella del centinela (el "
                      "repositorio que se publica, D9): ")
# Lo que de verdad se queda sin verificar en cada sitio que se salta.
SIN_LA_LISTA = {
    "huellas.txt": _SOLO_EL_CENTINELA
    + "queda sin verificar que huellas.txt lleve la lista entera. En el "
      "repositorio que se publica es lo que toca; en el de desarrollo, "
      "falta regenerarlo con --regenerar --lista",
    "arbol": _SOLO_EL_CENTINELA
    + "queda sin verificar aqui que el arbol no lleva ninguna cadena de la "
      "lista (los secretos si se buscan: test_el_arbol_no_lleva_secretos). "
      "Esa comprobacion se hace antes de publicar, con "
      "scripts/verificar_anonimato.py, --huellas y las huellas del "
      "repositorio de desarrollo",
    "metadatos": _SOLO_EL_CENTINELA
    + "las claves de los metadatos de las imagenes se han comprobado, pero "
      "queda sin verificar aqui que sus valores no llevan ninguna cadena de "
      "la lista. El script no lee las imagenes: esos valores solo los mira "
      "la revision a mano declarada en tests/anonimato/README.md",
}


def _lleva_el_centinela(ruta):
    """Sobre un booleano, con mensaje: pytest enseñaria el conjunto de
    huellas leido (C5)."""
    leidas = va.leer_huellas(ruta)
    con_el_centinela = va.huella(CENTINELA) in leidas
    assert con_el_centinela, (f"{ruta.name} no lleva la huella del "
                              f"centinela ({len(leidas)} huellas leídas)")


def test_el_centinela_esta_en_huellas_txt():
    _lleva_el_centinela(HUELLAS)


def test_la_prueba_del_centinela_no_ensena_las_huellas(tmp_path):
    # Como D-9: si falla, pytest enseñaria el conjunto de huellas leido.
    ruta = tmp_path / "huellas.txt"
    datos = sorted(va.huella(f"{OTRO}{n}") for n in range(30))
    ruta.write_text("# cabecera\n" + "\n".join(datos) + "\n",
                    encoding="utf-8")
    with pytest.raises(AssertionError) as error:
        _lleva_el_centinela(ruta)
    assert "no lleva la huella del centinela" in str(error.value)
    assert not any(una[:12] in str(error.value) for una in datos)


def test_la_cabecera_de_huellas_txt_es_la_que_escribe_el_script():
    # Quien mantiene la lista regenera huellas.txt y tiene que salir
    # identico: la cabecera es, letra por letra, la del script (la del
    # repositorio que se publica, si lleva solo la del centinela).
    comentarios = [l for l in HUELLAS.read_text(encoding="utf-8-sig")
                   .splitlines() if l.startswith("#")]
    esperada = (va.CABECERA_SOLO_CENTINELA if solo_el_centinela()
                else va.CABECERA)
    assert comentarios == esperada.splitlines()


def test_la_cabecera_dice_como_se_regenera_en_cualquier_consola():
    # `VARIABLE=valor orden` es de bash: en PowerShell no funciona.
    assert "--regenerar --lista <lista en claro>" in va.CABECERA
    assert "ANONIMATO_LISTA=" not in va.CABECERA
    publica = va.CABECERA_SOLO_CENTINELA
    assert "repositorio que se publica" in publica
    assert "a propósito" in publica
    assert "--regenerar --solo-centinela" in publica
    assert "huellas del repositorio de desarrollo" in publica
    assert all(l.startswith("#") for l in publica.splitlines())


def _cabecera_y_huellas_ordenadas(ruta):
    """Lo que se exige a un fichero de huellas. Se lee como `leer_huellas`
    (admite la marca de orden de bytes). Las aserciones son sobre booleanos,
    con recuentos: comparar listas enseñaria las huellas si fallase (D-9)."""
    lineas = ruta.read_text(encoding="utf-8-sig").splitlines()
    con_cabecera = bool(lineas) and lineas[0].startswith("#")
    assert con_cabecera, "la primera línea no es un comentario de cabecera"
    datos = [l for l in lineas if l and not l.startswith("#")]
    bien_formadas = all(len(l) == 64 and set(l) <= set("0123456789abcdef")
                        for l in datos)
    assert bien_formadas, "hay líneas que no son huellas"
    ordenadas = datos == sorted(set(datos))
    assert ordenadas, (f"{len(datos)} líneas, {len(set(datos))} distintas: "
                       "van ordenadas y sin repetir")
    leidas = va.leer_huellas(ruta)
    iguales = set(datos) == leidas
    assert iguales, f"{len(leidas)} huellas leídas frente a {len(datos)} líneas"


def test_huellas_txt_lleva_cabecera_y_huellas_ordenadas_sin_repetir():
    _cabecera_y_huellas_ordenadas(HUELLAS)


def test_la_cabecera_se_lee_con_la_marca_de_orden_de_bytes(tmp_path):
    # Como `leer_huellas`: un huellas.txt guardado con marca de orden de
    # bytes (el editor de alguien, PowerShell) vale igual.
    ruta = _huellas_de_juguete(tmp_path)
    ruta.write_bytes(codecs.BOM_UTF8 + ruta.read_bytes())
    _cabecera_y_huellas_ordenadas(ruta)


@pytest.mark.parametrize("estropeo", ["desordenadas", "repetida"])
def test_la_prueba_de_la_cabecera_no_ensena_las_huellas(tmp_path, estropeo):
    # Si falla, dice cuantas lineas y cuantas distintas: nunca las huellas
    # (D-9), que pytest enseñaria al comparar dos listas.
    ruta = tmp_path / "huellas.txt"
    datos = sorted(va.huella(f"{OTRO}{n}") for n in range(30))
    datos = datos[::-1] if estropeo == "desordenadas" else datos + datos[:1]
    ruta.write_text("# cabecera\n" + "\n".join(datos) + "\n",
                    encoding="utf-8")
    with pytest.raises(AssertionError) as error:
        _cabecera_y_huellas_ordenadas(ruta)
    mensaje = str(error.value)
    assert {"desordenadas": "30 líneas, 30 distintas",
            "repetida": "31 líneas, 30 distintas"}[estropeo] in mensaje
    assert not any(una[:12] in mensaje for una in datos)


@pytest.mark.skipif(solo_el_centinela(), reason=SIN_LA_LISTA["huellas.txt"])
def test_huellas_txt_lleva_mas_que_el_centinela():
    # Antes era parte de la prueba de arriba («len(datos) > 1»). Sobre un
    # booleano: pytest enseñaria el conjunto leido.
    mas_que_el_centinela = len(va.leer_huellas(HUELLAS)) > 1
    assert mas_que_el_centinela, "falta regenerar"


def test_solo_el_centinela_reconoce_el_fichero_del_repositorio_publico(
        tmp_path):
    publico = tmp_path / "publico.txt"
    publico.write_text("# cabecera\n" + va.huella(CENTINELA) + "\n",
                       encoding="utf-8")
    assert solo_el_centinela(publico)
    assert not solo_el_centinela(_huellas_de_juguete(tmp_path))


@pytest.mark.parametrize("mala", [
    pytest.param(va.huella(OTRO).upper(), id="en_mayusculas"),
    pytest.param(OTRO, id="un_token_en_claro"),
    pytest.param(va.huella(OTRO)[:63], id="corta"),
])
def test_leer_huellas_exige_una_huella_por_linea(tmp_path, mala):
    ruta = tmp_path / "huellas.txt"
    ruta.write_text(f"# cabecera\n{va.huella(CENTINELA)}\n\n{mala}\n",
                    encoding="utf-8")
    with pytest.raises(ValueError) as error:
        va.leer_huellas(ruta)
    assert "línea 4" in str(error.value)
    assert mala not in str(error.value)
    assert OTRO not in str(error.value).lower()


def test_leer_huellas_acepta_la_marca_de_orden_de_bytes(tmp_path):
    ruta = tmp_path / "huellas.txt"
    ruta.write_text("# cabecera\n" + va.huella(CENTINELA) + "\n",
                    encoding="utf-8-sig")
    assert va.leer_huellas(ruta) == {va.huella(CENTINELA)}


def test_la_lista_en_claro_esta_ignorada_por_si_alguien_la_copia_dentro():
    lineas = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "tests/anonimato/lista*.txt" in lineas
    assert not list((RAIZ / "tests" / "anonimato").glob("lista*.txt"))


# --------------------------------------------------------------------------
# La lista en claro y la regeneracion (con una lista de juguete)
# --------------------------------------------------------------------------
LISTA_DE_JUGUETE = """\
# comentario de cabecera
[Huellas]
# un grupo
Uno
dos   # lo que sigue a una almohadilla es comentario
tres

[sustituciones]
cuatro => cinco
"""


def test_leer_lista_da_solo_la_seccion_de_huellas(tmp_path):
    lista = tmp_path / "lista.txt"
    lista.write_text(LISTA_DE_JUGUETE, encoding="utf-8")
    assert va.leer_lista(lista) == ["Uno", "dos", "tres"]


def test_leer_lista_con_marca_de_orden_y_la_seccion_en_la_primera_linea(
        tmp_path):
    lista = tmp_path / "lista.txt"
    lista.write_text("[huellas]\nuno\n[HUELLAS]\ndos\n", encoding="utf-8-sig")
    assert va.leer_lista(lista) == ["uno", "dos"]


def test_regenerar_rechaza_lo_que_no_da_exactamente_un_token(tmp_path):
    destino = tmp_path / "huellas.txt"
    with pytest.raises(ValueError) as error:
        va.regenerar(["uno", "zorro-azul.test", "tres", "--"], destino)
    mensaje = str(error.value)
    assert "2" in mensaje and "4" in mensaje
    assert not {"zorro", "azul", "test"} & va.tokens(mensaje)
    assert not destino.exists()


def test_regenerar_sin_entradas_es_un_error(tmp_path):
    destino = tmp_path / "huellas.txt"
    with pytest.raises(ValueError):
        va.regenerar([], destino)
    assert not destino.exists()


def test_regenerar_escribe_las_huellas_ordenadas_y_la_del_centinela(tmp_path):
    destino = tmp_path / "anonimato" / "huellas.txt"
    n = va.regenerar(["Uno", "dos", "tres", "uno"], destino)
    esperadas = {va.huella(t) for t in ("uno", "dos", "tres", CENTINELA)}
    assert n == 4
    assert va.leer_huellas(destino) == esperadas
    texto = destino.read_text(encoding="utf-8")
    datos = [l for l in texto.splitlines() if l and not l.startswith("#")]
    assert datos == sorted(esperadas)
    assert texto.startswith(va.CABECERA)
    assert "\r" not in destino.read_bytes().decode("utf-8")
    # Ningun token en claro, salvo el centinela, que es publico y la cabecera
    # lo nombra. (La huella de un token corto se adivina probando: en el
    # repositorio que se publica, huellas.txt lleva solo la del centinela,
    # D9; la lista entera vive solo en el de desarrollo, que es privado.)
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


def _donde(hallazgos):
    """Fichero y linea de cada hallazgo: lo que dice una asercion que falla
    con las huellas de verdad (pytest enseñaria la huella entera, C5)."""
    return f"{len(hallazgos)} hallazgos: " + ", ".join(
        f"{h['fichero']}:{h['linea']}" for h in hallazgos)


def test_un_arbol_limpio_no_da_hallazgos(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    hallazgos = va.buscar_huellas(raiz, va.leer_huellas(HUELLAS))
    limpio = hallazgos == []
    assert limpio, _donde(hallazgos)
    assert va.buscar_secretos(raiz) == []


def test_detecta_el_centinela_dentro_del_recorrido(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "docs" / "nota.md").write_text(
        f"primera\nsegunda con {CENTINELA}.\n", encoding="utf-8")
    hallazgos = va.buscar_huellas(raiz, va.leer_huellas(HUELLAS))
    solo_el_centinela_en_la_nota = hallazgos == [
        {"fichero": "docs/nota.md", "linea": 2,
         "huella": va.huella(CENTINELA), "origen": COPIA}]
    assert solo_el_centinela_en_la_nota, _donde(hallazgos)


# A2: cada asercion sobre las huellas de HUELLAS que se paso a booleano (C5),
# con un huellas.txt de juguete que lleva la huella de `ejemplo`, un token
# del contenido del arbol de juguete (linea 3 de `docs/guia.md`; no de un
# nombre, que saldria tapado por el principio de su huella): la prueba
# falla, y su mensaje no lleva nada de esa huella. Con la forma vieja,
# pytest la enseñaria entera.
@pytest.mark.parametrize("llamar, esperado", [
    pytest.param(lambda carpeta: test_el_centinela_esta_en_huellas_txt(),
                 "no lleva la huella del centinela", id="el_centinela_esta"),
    pytest.param(lambda carpeta: test_huellas_txt_lleva_mas_que_el_centinela(),
                 "falta regenerar", id="mas_que_el_centinela"),
    pytest.param(lambda carpeta: test_un_arbol_limpio_no_da_hallazgos(carpeta),
                 "1 hallazgos: docs/guia.md:3", id="arbol_limpio"),
    pytest.param(
        lambda carpeta: test_detecta_el_centinela_dentro_del_recorrido(carpeta),
        "1 hallazgos: docs/guia.md:3", id="centinela_en_el_recorrido"),
])
def test_las_aserciones_sobre_huellas_txt_no_ensenan_huellas(
        tmp_path, monkeypatch, llamar, esperado):
    de_juguete = tmp_path / "huellas.txt"
    de_juguete.write_text("# de juguete\n" + va.huella("ejemplo") + "\n",
                          encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "HUELLAS", de_juguete)
    with pytest.raises(AssertionError) as error:
        llamar(tmp_path / "prueba")
    assert esperado in str(error.value)
    assert va.huella("ejemplo")[:8] not in str(error.value)


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
    assert sorted(hallazgo) == ["fichero", "huella", "linea", "origen"]
    assert CENTINELA not in repr(hallazgo)


def test_el_nombre_del_fichero_tambien_se_tokeniza(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "docs" / f"{CENTINELA}.md").write_text(
        f"nada\ny {CENTINELA}\n", encoding="utf-8")
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [h["linea"] for h in hallazgos] == [0, 2]
    assert CENTINELA not in repr(hallazgos)
    # El nombre que sale es el publicable, el mismo en todos los hallazgos:
    # el TOKEN dentro del componente pasa al principio de su huella (R6).
    publicable = f"docs/<huella-{va.huella(CENTINELA)[:12]}>.md"
    assert [h["fichero"] for h in hallazgos] == [publicable, publicable]


def test_tres_hermanos_con_el_mismo_token_no_chocan(tmp_path, capsys):
    raiz = _arbol_limpio(tmp_path / "arbol")
    for nombre in (f"informe-{OTRO}.md", f"notas_{OTRO.upper()}.md",
                   f"{OTRO}.txt"):
        (raiz / "docs" / nombre).write_text("nada\n", encoding="utf-8")
    tapada = f"<huella-{va.huella(OTRO)[:12]}>"
    hallazgos = va.buscar_huellas(raiz, {va.huella(OTRO)})
    assert sorted(h["fichero"] for h in hallazgos) == sorted([
        f"docs/informe-{tapada}.md", f"docs/notas_{tapada}.md",
        f"docs/{tapada}.txt"])
    assert va.main(["--raiz", str(raiz),
                    "--huellas", str(_huellas_de_juguete(tmp_path))]) == 1
    salida = capsys.readouterr().out
    assert "huellas: 3 en 3 ficheros" in salida
    assert OTRO not in salida.lower()


def test_un_secreto_en_el_nombre_del_fichero_es_un_hallazgo(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    clave = _secretos()["clave_de_api_akia"]
    (raiz / "docs" / f"config-{clave}.txt").write_text("x\n",
                                                       encoding="utf-8")
    (raiz / "figura-{}.png".format(clave)).write_bytes(b"\x89PNG\x00")
    hallazgos = va.buscar_secretos(raiz, huellas=set())
    assert hallazgos == [
        {"fichero": "docs/config-<secreto>.txt", "linea": 0,
         "clase": "clave_de_api_akia", "origen": COPIA},
        {"fichero": "figura-<secreto>.png", "linea": 0,
         "clase": "clave_de_api_akia", "origen": COPIA}]
    codigo, salida = _cli("--raiz", str(raiz),
                          "--huellas", str(_huellas_de_juguete(tmp_path)))
    assert codigo == 1
    assert clave not in salida
    assert "  figura-<secreto>.png" in salida


def test_el_nombre_publicable_tambien_en_los_secretos(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    carpeta = raiz / CENTINELA
    carpeta.mkdir()
    (carpeta / "config.txt").write_text(
        _secretos()["clave_de_api_akia"] + "\n", encoding="utf-8")
    (carpeta / ".env").write_text("X=1\n", encoding="utf-8")
    hallazgos = va.buscar_secretos(raiz, huellas={va.huella(CENTINELA)})
    tapada = f"<huella-{va.huella(CENTINELA)[:12]}>"
    assert [(h["fichero"], h["linea"], h["clase"]) for h in hallazgos] == [
        (f"{tapada}/.env", 0, "fichero_prohibido"),
        (f"{tapada}/config.txt", 1, "clave_de_api_akia")]
    assert CENTINELA not in repr(hallazgos)


def test_los_binarios_se_declaran_y_no_se_recorren(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "otra.png").write_bytes(
        b"\x89PNG\x00" + CENTINELA.encode("ascii") + b"\xff")
    assert va.es_texto(raiz / "codigo.py")
    assert not va.es_texto(raiz / "otra.png")
    assert [p.name for p in va.binarios(raiz)] == ["figura.png", "otra.png"]
    assert va.buscar_huellas(raiz, {va.huella(CENTINELA)}) == []


_CON_TILDE = "CentinelaAnónimato7F3A"       # el centinela, escrito con tilde


@pytest.mark.parametrize("datos", [
    pytest.param(f"uno\ncon {CENTINELA}\n".encode("utf-16"),
                 id="utf16_con_marca"),
    pytest.param(f"uno\ncon {CENTINELA}\n".encode("utf-16-be"),
                 id="utf16be_sin_marca_es_binario"),
    pytest.param(b"\xfe\xff" + f"uno\ncon {CENTINELA}\n".encode("utf-16-be"),
                 id="utf16be_con_marca"),
    pytest.param(f"uno\ncon {CENTINELA}\n".encode("utf-32"),
                 id="utf32_con_marca"),
    pytest.param(f"Canción\ncon {_CON_TILDE}\n".encode("latin-1"),
                 id="latin1"),
    pytest.param(f"Canción\ncon {_CON_TILDE}".encode("utf-8") + b" \x96 fin\n",
                 id="utf8_con_un_byte_cp1252_suelto"),
])
def test_el_texto_que_no_es_utf8_tambien_se_recorre(tmp_path, datos):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "tabla.csv").write_bytes(datos)
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    if b"\0" in datos and not datos.startswith((b"\xff\xfe", b"\xfe\xff")):
        # Bytes nulos sin marca de orden de bytes: binario, se declara.
        assert not va.es_texto(raiz / "tabla.csv")
        assert "tabla.csv" in [p.name for p in va.binarios(raiz)]
        assert hallazgos == []
        return
    assert va.es_texto(raiz / "tabla.csv")
    assert "tabla.csv" not in [p.name for p in va.binarios(raiz)]
    assert [(h["fichero"], h["linea"]) for h in hallazgos] == [
        ("tabla.csv", 2)]


# --------------------------------------------------------------------------
# Con git: lo que se publicaria (la copia de trabajo sin lo ignorado, el
# indice y, con --commit, el arbol del commit)
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
    hecho = subprocess.run(["git", "-C", str(raiz), *argumentos], check=True,
                           capture_output=True, env=limpio)
    return hecho.stdout.decode("utf-8")


def _repositorio(tmp_path):
    raiz = _arbol_limpio(tmp_path / "repo")
    _git(raiz, "init", "-q")
    # Una carpeta temporal larga no hace fallar las pruebas de nombres largos
    # (una rama con nombre de token, C2): git en Windows, sin esto, no pasa
    # de 260 caracteres.
    _git(raiz, "config", "core.longpaths", "true")
    _git(raiz, "add", "-A")
    return raiz


@hay_git
def test_en_un_repositorio_se_recorre_lo_versionado_y_lo_no_ignorado(
        tmp_path):
    # Antes: «se recorre solo lo versionado». Lo que no tiene seguimiento y
    # no esta ignorado tambien se publica (`git add -A` lo anade): se recorre.
    raiz = _repositorio(tmp_path)
    (raiz / ".gitignore").write_text("ignorado.txt\n", encoding="utf-8")
    (raiz / "ignorado.txt").write_text(CENTINELA + "\n", encoding="utf-8")
    (raiz / "sin_versionar.txt").write_text(CENTINELA + "\n",
                                            encoding="utf-8")
    nombres = [p.relative_to(raiz).as_posix()
               for p in va.ficheros_versionados(raiz)]
    assert nombres == [".gitignore", "codigo.py", "docs/guia.md",
                       "figura.png", "sin_versionar.txt"]
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [(h["fichero"], h["linea"], h["origen"]) for h in hallazgos] == [
        ("sin_versionar.txt", 1, COPIA)]

    (raiz / "docs" / "guia.md").write_text(f"ahora sí: {CENTINELA}\n",
                                           encoding="utf-8")
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [(h["fichero"], h["linea"], h["origen"]) for h in hallazgos] == [
        ("docs/guia.md", 1, COPIA), ("sin_versionar.txt", 1, COPIA)]


@hay_git
def test_un_repositorio_recien_creado_sin_add_se_recorre(tmp_path):
    raiz = _arbol_limpio(tmp_path / "repo")
    _git(raiz, "init", "-q")
    (raiz / "docs" / "nota.md").write_text(f"primera\ncon {CENTINELA}\n",
                                           encoding="utf-8")
    assert va.buscar_huellas(raiz, {va.huella(CENTINELA)}) == [
        {"fichero": "docs/nota.md", "linea": 2,
         "huella": va.huella(CENTINELA), "origen": COPIA}]


@hay_git
def test_la_cli_sobre_un_arbol_vacio_no_dice_limpio(tmp_path, capsys):
    huellas = str(_huellas_de_juguete(tmp_path))
    vacio = tmp_path / "vacio"
    vacio.mkdir()
    _git(vacio, "init", "-q")
    sin_git = tmp_path / "sin_git"
    sin_git.mkdir()
    for raiz in (vacio, sin_git):
        assert va.main(["--raiz", str(raiz), "--huellas", huellas]) == 1
        salida = capsys.readouterr().out
        assert "ficheros recorridos: 0" in salida
        assert salida.splitlines()[-1].startswith("NO publicar: no se "
                                                  "recorrió ningún fichero")


@hay_git
def test_lo_preparado_y_limpiado_despues_en_disco_sale_del_indice(tmp_path):
    raiz = _repositorio(tmp_path)
    guia = raiz / "docs" / "guia.md"
    limpio = guia.read_bytes()
    guia.write_text(f"uno\ncon {CENTINELA}\n", encoding="utf-8")
    _git(raiz, "add", "docs/guia.md")
    guia.write_bytes(limpio)
    assert va.buscar_huellas(raiz, {va.huella(CENTINELA)}) == [
        {"fichero": "docs/guia.md", "linea": 2,
         "huella": va.huella(CENTINELA), "origen": INDICE}]


@hay_git
def test_lo_preparado_y_borrado_del_disco_se_recorre(tmp_path):
    raiz = _repositorio(tmp_path)
    nota = raiz / "nota.md"
    nota.write_text(f"{CENTINELA}\n", encoding="utf-8")
    _git(raiz, "add", "nota.md")
    nota.unlink()
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [(h["fichero"], h["linea"], h["origen"]) for h in hallazgos] == [
        ("nota.md", 1, INDICE)]


@hay_git
def test_con_commit_se_recorre_el_arbol_del_commit(tmp_path, capsys):
    raiz = _repositorio(tmp_path)
    nota = raiz / "nota.md"
    nota.write_text(f"uno\n{CENTINELA} y {OTRO}\n", encoding="utf-8")
    _git(raiz, "add", "nota.md")
    _git(raiz, "commit", "-q", "-m", "arbol")
    nota.write_text("uno\nya limpio\n", encoding="utf-8")
    _git(raiz, "add", "nota.md")            # copia e indice, limpios

    huellas = {va.huella(CENTINELA)}
    assert va.buscar_huellas(raiz, huellas) == []
    assert va.buscar_huellas(raiz, huellas, commit="HEAD") == [
        {"fichero": "nota.md", "linea": 2,
         "huella": va.huella(CENTINELA), "origen": COMMIT}]

    de_juguete = str(_huellas_de_juguete(tmp_path))
    assert va.main(["--raiz", str(raiz), "--huellas", de_juguete]) == 0
    capsys.readouterr()
    assert va.main(["--raiz", str(raiz), "--huellas", de_juguete,
                    "--commit", "HEAD"]) == 1
    salida = capsys.readouterr().out
    assert f"nota.md:2: huella {va.huella(OTRO)[:12]} (commit)" in salida
    assert OTRO not in salida.lower()


@hay_git
def test_un_mismo_contenido_se_recorre_una_sola_vez(tmp_path):
    raiz = _repositorio(tmp_path)
    (raiz / "nota.md").write_text(f"{CENTINELA}\n", encoding="utf-8")
    _git(raiz, "add", "nota.md")
    _git(raiz, "commit", "-q", "-m", "arbol")
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)},
                                  commit="HEAD")
    assert [(h["fichero"], h["origen"]) for h in hallazgos] == [
        ("nota.md", COPIA)]


@hay_git
def test_una_subcarpeta_de_un_repositorio_se_recorre_entera(tmp_path):
    # No es la raiz de un repositorio: se recorre todo lo que hay debajo,
    # tambien lo ignorado (es el arbol que alguien copiaria para publicar).
    raiz = _repositorio(tmp_path)
    (raiz / ".gitignore").write_text("docs/ignorado.md\n", encoding="utf-8")
    (raiz / "docs" / "ignorado.md").write_text(f"{CENTINELA}\n",
                                               encoding="utf-8")
    assert va.buscar_huellas(raiz, {va.huella(CENTINELA)}) == []
    hallazgos = va.buscar_huellas(raiz / "docs", {va.huella(CENTINELA)})
    assert [(h["fichero"], h["linea"], h["origen"]) for h in hallazgos] == [
        ("ignorado.md", 1, COPIA)]
    assert [p.name for p in va.ficheros_versionados(raiz / "docs")] == [
        "guia.md", "ignorado.md"]


@hay_git
def test_las_ordenes_de_git_no_heredan_el_repositorio_del_entorno(
        tmp_path, monkeypatch):
    raiz = _repositorio(tmp_path)
    (raiz / ".gitignore").write_text("ignorado.md\n", encoding="utf-8")
    (raiz / "ignorado.md").write_text(f"{CENTINELA}\n", encoding="utf-8")
    nota = raiz / "nota.md"
    nota.write_text(f"{CENTINELA}\n", encoding="utf-8")
    _git(raiz, "add", "nota.md")
    nota.unlink()                       # solo queda en el indice

    otro = _arbol_limpio(tmp_path / "otro")
    _git(otro, "init", "-q")
    _git(otro, "add", "-A")
    monkeypatch.setenv("GIT_DIR", str(otro / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(otro))
    monkeypatch.setenv("GIT_INDEX_FILE", str(otro / ".git" / "index"))

    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [(h["fichero"], h["linea"], h["origen"]) for h in hallazgos] == [
        ("nota.md", 1, INDICE)]


def _no_recorrido(fichero, origen):
    return {"fichero": fichero, "linea": 0, "clase": "no_recorrido",
            "origen": origen}


@hay_git
def test_un_submodulo_no_se_recorre_en_silencio(tmp_path, capsys):
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "uno")
    sha = _git(raiz, "rev-parse", "HEAD").strip()
    _git(raiz, "update-index", "--add", "--cacheinfo",
         f"160000,{sha},vendor/otro")
    assert va.buscar_secretos(raiz, huellas=set()) == [
        _no_recorrido("vendor/otro", INDICE)]

    _git(raiz, "commit", "-q", "-m", "con submodulo")
    assert va.buscar_secretos(raiz, huellas=set(), commit="HEAD") == [
        _no_recorrido("vendor/otro", INDICE)]
    assert va.main(["--raiz", str(raiz),
                    "--huellas", str(_huellas_de_juguete(tmp_path))]) == 1
    salida = capsys.readouterr().out
    assert "vendor/otro:0: no_recorrido (indice)" in salida


@hay_git
def test_un_enlace_simbolico_del_indice_no_se_recorre_en_silencio(tmp_path):
    # Se prepara con git, sin crear el enlace en disco: vale tambien en una
    # maquina que no deja crear enlaces simbolicos.
    raiz = _repositorio(tmp_path)
    (raiz / "destino.txt").write_text("docs/guia.md", encoding="utf-8")
    sha = _git(raiz, "hash-object", "-w", "destino.txt").strip()
    (raiz / "destino.txt").unlink()
    _git(raiz, "update-index", "--add", "--cacheinfo", f"120000,{sha},enlace")
    assert va.buscar_secretos(raiz, huellas=set()) == [
        _no_recorrido("enlace", INDICE)]


@hay_git
def test_otro_repositorio_dentro_sin_seguimiento_no_se_recorre(tmp_path):
    raiz = _repositorio(tmp_path)
    dentro = raiz / "vendor" / "otro"
    dentro.mkdir(parents=True)
    _git(dentro, "init", "-q")
    (dentro / "nota.md").write_text(f"{CENTINELA}\n", encoding="utf-8")
    assert va.buscar_secretos(raiz, huellas=set()) == [
        _no_recorrido("vendor/otro", COPIA)]


def _enlazar(enlace, destino):
    try:
        os.symlink(destino, enlace)
    except (OSError, NotImplementedError) as error:
        pytest.skip("esta maquina no deja crear enlaces simbolicos "
                    f"({error.__class__.__name__}): queda sin verificar que "
                    "un enlace simbolico en disco se declara no_recorrido")


@pytest.mark.parametrize("con_git", [
    pytest.param(False, id="sin_git"),
    pytest.param(True, id="con_git", marks=hay_git),
])
def test_un_enlace_simbolico_en_disco_no_se_recorre_en_silencio(tmp_path,
                                                               con_git):
    raiz = _repositorio(tmp_path) if con_git else _arbol_limpio(
        tmp_path / "repo")
    fuera = tmp_path / "fuera.md"
    fuera.write_text(f"{CENTINELA}\n", encoding="utf-8")
    _enlazar(raiz / "enlace.md", fuera)
    assert va.buscar_secretos(raiz, huellas=set()) == [
        _no_recorrido("enlace.md", COPIA)]
    assert va.buscar_huellas(raiz, {va.huella(CENTINELA)}) == []


def test_un_fichero_que_no_se_puede_leer_no_se_recorre_en_silencio(
        tmp_path, monkeypatch):
    raiz = _arbol_limpio(tmp_path / "arbol")
    leer = Path.read_bytes

    def leer_salvo_la_guia(ruta):
        if ruta.name == "guia.md":
            raise PermissionError(13, "acceso denegado")
        return leer(ruta)

    monkeypatch.setattr(Path, "read_bytes", leer_salvo_la_guia)
    assert va.buscar_secretos(raiz, huellas=set()) == [
        _no_recorrido("docs/guia.md", COPIA)]


@pytest.mark.parametrize("con_git", [
    pytest.param(False, id="sin_git"),
    pytest.param(True, id="con_git", marks=hay_git),
])
def test_lo_que_el_disco_dice_que_es_un_enlace_no_se_recorre(
        tmp_path, monkeypatch, con_git):
    # La misma rama que la prueba de arriba, en una maquina sin enlaces: un
    # fichero normal que `_es_enlace` declara enlace.
    raiz = _repositorio(tmp_path) if con_git else _arbol_limpio(
        tmp_path / "repo")
    (raiz / "enlace.md").write_text(f"{CENTINELA}\n", encoding="utf-8")
    monkeypatch.setattr(va, "_es_enlace",
                        lambda ruta: Path(ruta).name == "enlace.md")
    assert va.buscar_secretos(raiz, huellas=set()) == [
        _no_recorrido("enlace.md", COPIA)]
    assert "enlace.md" not in [p.name for p in va.ficheros_versionados(raiz)]
    assert va.buscar_huellas(raiz, {va.huella(CENTINELA)}) == []


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
         "-m", f"Co-Authored-By: Alguien <alguien@{CENTINELA}.test>",
         GIT_AUTHOR_NAME=f"Nombre {CENTINELA.upper()}",
         GIT_COMMITTER_NAME=f"Quien {CENTINELA}",
         GIT_COMMITTER_EMAIL=f"{CENTINELA}@ejemplo.test")
    assert va.commits(raiz) == 2
    hallazgos = va.verificar_commit(raiz, "HEAD", huellas=huellas)
    assert [(h["campo"], h["linea"]) for h in hallazgos] == [
        ("autor", 0), ("quien_confirma", 0), ("correo_de_quien_confirma", 0),
        ("mensaje", 3), ("mensaje", 5)]
    assert all(h["huella"] == va.huella(CENTINELA) for h in hallazgos)
    assert CENTINELA not in repr(hallazgos).lower()
    assert va.verificar_commit(raiz, "HEAD~1", huellas=huellas) == []


@hay_git
def test_una_revision_que_no_existe_no_saca_el_token(tmp_path):
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "arbol")
    huellas = {va.huella(OTRO)}
    for funcion in (va.verificar_commit, va.cabeceras_del_commit):
        with pytest.raises(SystemExit) as error:
            funcion(raiz, f"inexistente-{OTRO}", huellas=huellas)
        assert OTRO not in str(error.value).lower()
        assert "inexistente-<huella-" in str(error.value)


@hay_git
def test_la_rama_de_un_repositorio_sin_commits_tambien_se_mira(tmp_path):
    # `git init` y nada mas: la rama a la que va HEAD aun no existe como
    # referencia, pero su nombre se publica con el primer push.
    raiz = _arbol_limpio(tmp_path / "repo")
    _git(raiz, "init", "-q")
    _git(raiz, "symbolic-ref", "HEAD", f"refs/heads/informe-{OTRO}")
    tapada = f"informe-<huella-{va.huella(OTRO)[:12]}>"
    assert va.verificar_referencias(raiz, {va.huella(OTRO)}) == [
        {"referencia": "rama", "nombre": tapada, "huella": va.huella(OTRO)}]


def _commit_a_mano(raiz, *cabeceras_de_mas):
    """Apunta HEAD a un commit escrito a mano (`git hash-object`) con el
    arbol de HEAD, un autor neutro y las cabeceras que se pasen: asi se
    prueba un commit firmado sin ninguna clave."""
    arbol = _git(raiz, "rev-parse", "HEAD^{tree}").strip()
    firma = "Autor Neutro <autor@ejemplo.test> 1700000000 +0000"
    crudo = raiz.parent / "commit-a-mano.txt"
    crudo.write_bytes((f"tree {arbol}\nauthor {firma}\ncommitter {firma}\n"
                       + "".join(cabeceras_de_mas)
                       + "\narbol escrito a mano\n").encode("utf-8"))
    sha = _git(raiz, "hash-object", "-t", "commit", "-w", str(crudo)).strip()
    _git(raiz, "update-ref", "HEAD", sha)


@hay_git
def test_una_cabecera_de_mas_en_el_commit_es_un_hallazgo(tmp_path):
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "arbol")
    huellas = str(_huellas_de_juguete(tmp_path))
    firma = ("gpgsig -----BEGIN PGP SIGNATURE-----\n \n"
             " firma de juguete\n -----END PGP SIGNATURE-----\n")
    _commit_a_mano(raiz, firma)
    assert va.cabeceras_del_commit(raiz, "HEAD", huellas=set()) == [
        {"campo": "gpgsig", "linea": 0, "clase": "cabecera_del_commit"}]
    codigo, salida = _cli("--raiz", str(raiz), "--huellas", huellas,
                          "--commit")
    assert codigo == 1
    assert "commit HEAD: gpgsig: cabecera_del_commit" in salida
    assert "juguete" not in salida and "PGP" not in salida

    _commit_a_mano(raiz)                        # el mismo, sin la firma
    assert va.cabeceras_del_commit(raiz, "HEAD", huellas=set()) == []
    codigo, salida = _cli("--raiz", str(raiz), "--huellas", huellas,
                          "--commit")
    assert codigo == 0, salida
    assert "commit HEAD: 0" in salida


@hay_git
def test_con_un_solo_commit_un_padre_es_una_cabecera_de_mas(tmp_path):
    # Un commit con padre no es el unico: con --un-solo-commit, `parent` es
    # un hallazgo; con --commit a secas, no (el repositorio de desarrollo).
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "uno")
    assert va.cabeceras_del_commit(raiz, huellas=set(),
                                   un_solo_commit=True) == []
    _git(raiz, "commit", "-q", "--allow-empty", "-m", "dos")
    assert va.cabeceras_del_commit(raiz, huellas=set()) == []
    assert va.cabeceras_del_commit(raiz, huellas=set(),
                                   un_solo_commit=True) == [
        {"campo": "parent", "linea": 0, "clase": "cabecera_del_commit"}]


# --------------------------------------------------------------------------
# Secretos. Se componen al correr: ver el docstring del fichero.
# --------------------------------------------------------------------------
def _secretos():
    return {
        "token_de_bot_de_telegram": _token_de_bot(),
        "clave_de_api_sk": "sk" + "-" + "proj" + "-" + "a1B2" * 6,
        "clave_de_api_akia": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "clave_de_api_ghp": "gh" + "p_" + "a1B2" * 9,
        "clave_de_api_github_pat": "github" + "_pat_" + "a1B2_" * 6,
        "jwt": ".".join(["ey" + "J" + "hbGciOiJIUzI1NiJ9",
                         "ey" + "J" + "zdWIiOiIxMjM0NTY3ODkwIn0",
                         "dozjgNryP4J3jVmNHl0w5N"]),
        "contrasena_en_url": "postgresql://usuario" + ":" + "S3creta!"
                             + "@" + "bd.ejemplo.test:5432/base",
        "clave_de_api_aiza": "AI" + "za"
                             + "SyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6q",
        "clave_de_api_gho": "gh" + "o_" + "a1B2" * 9,
        "clave_de_api_ghs": "gh" + "s_" + "a1B2" * 9,
        "clave_de_api_asia": "AS" + "IA" + "ABCDEFGHIJKLMNOP",
        "clave_privada": "-----BEGIN " + "OPENSSH PRIV" + "ATE KEY-----",
        "cabecera_authorization": "Author" + "ization: Bearer "
                                  + "a1B2c3D4" * 3,
        "asignacion_de_secreto": "PASS" + "WORD=" + "a1B2c3D4e5F6g7H8",
    }


def _token_de_bot(cifras="123456789"):
    return cifras + ":" + "AAH" + "x" * 32


# Valores de juguete con forma de secreto. Sin la clave delante: la linea que
# los define no es una asignacion.
_LITERAL = "a1B2c3D4" + "e5F6g7H8"
_CON_LLAVES = "S3cr{" + "eta}9x"
_CON_CORCHETES = "Ab[12]" + "cdefg"
_CON_PARENTESIS = "Kq9)" + "w2Lm4z"


# Otras formas de las mismas clases: (id de la prueba, clase, secreto).
_VARIANTES = [
    ("telegram_en_url", "token_de_bot_de_telegram",
     "curl https://api.telegram.org/bot" + _token_de_bot() + "/setWebhook"),
    ("telegram_en_expresion_de_n8n", "token_de_bot_de_telegram",
     "=https://api.telegram.org/bot" + _token_de_bot()
     + "/sendMessage?chat_id={{ $json.chat_id }}"),
    ("telegram_id_de_10_cifras_en_url", "token_de_bot_de_telegram",
     "https://api.telegram.org/bot" + _token_de_bot("1234567890") + "/getMe"),
    ("telegram_id_de_12_cifras", "token_de_bot_de_telegram",
     _token_de_bot("123456789012")),
    ("clave_privada_rsa", "clave_privada",
     "-----BEGIN " + "RSA PRIV" + "ATE KEY-----"),
    ("clave_privada_sin_tipo", "clave_privada",
     "-----BEGIN " + "PRIV" + "ATE KEY-----"),
    ("authorization_basic", "cabecera_authorization",
     "-H 'author" + "ization: basic " + "dXN1YXJpbzpTM2NyZXRhMTIzNDU2'"),
    ("asignacion_en_un_compose", "asignacion_de_secreto",
     "POSTGRES_" + "PASSWORD: " + "a1B2c3D4e5F6g7H8"),
    ("asignacion_fuera_de_un_env", "asignacion_de_secreto",
     "COPILOTO_BD_" + "PASSWORD=" + "a1B2c3D4e5F6g7H8"),
    ("asignacion_de_secret_token", "asignacion_de_secreto",
     "secret" + "_token=" + "0123456789abcdef" * 2),
    ("asignacion_de_api_key_en_json", "asignacion_de_secreto",
     '"api' + '_key": "' + "a1B2c3D4e5F6g7H8" + '"'),
    ("asignacion_de_passwd_entre_comillas", "asignacion_de_secreto",
     "db_pass" + "wd = 'Zq9" + "x7Kw2Lm4'"),
    ("url_sin_usuario", "contrasena_en_url",
     "redis://" + ":" + "S3creta!" + "@" + "cache.ejemplo.test:6379/0"),
    ("url_con_dolar_que_no_es_variable", "contrasena_en_url",
     "postgresql://u" + ":" + "$uperS3creta9" + "@" + "bd.ejemplo.test/b"),
    ("url_con_angulos_que_no_son_marcador", "contrasena_en_url",
     "postgresql://u" + ":" + "<S3:creta>" + "@" + "bd.ejemplo.test/b"),
    # R4: las formas de este proyecto que no saltaban.
    ("url_con_barra_en_la_contrasena", "contrasena_en_url",
     "postgresql://u" + ":" + "S3cr/eta+9w==" + "@" + "bd.ejemplo.test/b"),
    ("url_con_valor_por_defecto", "contrasena_en_url",
     "postgresql://u" + ":" + "${PGPASS:-S3creta!}" + "@" + "bd.ejemplo.test"),
    ("asignacion_con_subindice", "asignacion_de_secreto",
     'os.environ["COPILOTO_BD_' + 'PASSWORD"] = "' + "a1B2c3D4e5F6g7H8" + '"'),
    ("asignacion_con_llamada", "asignacion_de_secreto",
     'monkeypatch.setenv("COPILOTO_BD_' + 'PASSWORD", "' + "a1B2c3D4e5F6g7H8"
     + '")'),
    ("clave_que_acaba_en_key_con_subindice", "asignacion_de_secreto",
     # El valor, por una llamada: con las comillas mezcladas, el propio
     # codigo de la prueba formaria un literal.
     "os.environ['KAGGLE" + "_KEY'] = '" + "".join(["0123456789abcdef"] * 2)
     + "'"),
    ("clave_que_acaba_en_key", "asignacion_de_secreto",
     "AWS_ACCESS" + "_KEY=" + "a1B2c3D4e5F6g7H8"),
    ("clave_privada_en_una_variable", "asignacion_de_secreto",
     "PRIVATE" + "_KEY: " + "a1B2c3D4e5F6g7H8"),
    ("asignacion_en_json_escapado", "asignacion_de_secreto",
     '"source": ["pass' + 'word=\\"' + "a1B2c3D4e5F6g7H8" + '\\"\\n"]'),
    ("valor_por_defecto_de_una_variable", "asignacion_de_secreto",
     "COPILOTO_BD_PASS" + "WORD: ${COPILOTO_BD_PASSWORD:-" + "a1B2c3D4e5F6g7H8"
     + "}"),
    # A1: la terminacion `_KEY` cuenta escrita en mayusculas; en minusculas,
    # solo con unos pocos nombres delante.
    ("key_en_mayusculas", "asignacion_de_secreto",
     "KAGGLE" + "_KEY=" + _LITERAL),
    ("access_key_en_un_compose", "asignacion_de_secreto",
     "AWS_ACCESS" + "_KEY: " + _LITERAL),
    ("private_key_en_minusculas", "asignacion_de_secreto",
     "private" + '_key = "' + _LITERAL + '"'),
    ("signing_key_en_minusculas", "asignacion_de_secreto",
     "signing" + "_key: '" + _LITERAL + "'"),
    # A2: entre comillas, un parentesis, un corchete o una llave no hacen
    # una expresion (regresion de la ronda 2).
    ("entre_comillas_con_llaves", "asignacion_de_secreto",
     "pass" + 'word = "' + _CON_LLAVES + '"'),
    ("entre_comillas_con_corchetes_en_json", "asignacion_de_secreto",
     '"pass' + 'word": "' + _CON_CORCHETES + '"'),
    ("entre_comillas_con_parentesis", "asignacion_de_secreto",
     "PASS" + "WORD: '" + _CON_PARENTESIS + "'"),
    # A4: lo de antes de los dos puntos no parece un host, asi que no es un
    # puerto y una ruta.
    ("url_con_contrasena_que_empieza_por_cifras", "contrasena_en_url",
     "postgresql://u" + ":" + "2024/Secreta9x" + "@" + "host/base"),
    # A5: `Bot` en mayusculas y los dos puntos escapados.
    ("telegram_con_bot_capitalizado", "token_de_bot_de_telegram",
     "https://api.telegram.org/Bot" + _token_de_bot() + "/getMe"),
    ("telegram_con_bot_en_mayusculas", "token_de_bot_de_telegram",
     "https://api.telegram.org/BOT" + _token_de_bot() + "/getMe"),
    ("telegram_con_los_dos_puntos_escapados", "token_de_bot_de_telegram",
     _token_de_bot().replace(":", "%3A")),
    ("telegram_con_los_dos_puntos_escapados_en_minusculas",
     "token_de_bot_de_telegram",
     "https://api.telegram.org/bot" + _token_de_bot().replace(":", "%3a")
     + "/getMe"),
]


def _casos_de_secreto():
    return ([pytest.param(c, s, id=c) for c, s in sorted(_secretos().items())]
            + [pytest.param(c, s, id=i) for i, c, s in _VARIANTES])


@pytest.mark.parametrize("clase, secreto", _casos_de_secreto())
def test_buscar_secretos_encuentra_cada_clase_sin_imprimirla(tmp_path, clase,
                                                            secreto):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "config.txt").write_text(f"uno\ndos\nVALOR = \"{secreto}\"\n",
                                     encoding="utf-8")
    hallazgos = va.buscar_secretos(raiz)
    assert hallazgos == [{"fichero": "config.txt", "linea": 3,
                          "clase": clase, "origen": COPIA}]
    assert secreto not in repr(hallazgos)


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
    "privada.key", "id_rsa", "id_rsa.pub", "certificado.p12",
    "id_ed25519", "id_ecdsa", "id_dsa.pub", "produccion.env", ".envrc",
    "putty.ppk", "certificado.pfx", "credentials.json",
    ".pgpass", ".netrc", ".git-credentials",
    "client_secret_1234.apps.googleusercontent.com.json",
    # Los nombres no distinguen mayusculas.
    ".ENV", "servidor.PEM", "Kaggle.json", "ID_RSA"])
def test_los_ficheros_prohibidos_son_hallazgos(tmp_path, nombre):
    raiz = _arbol_limpio(tmp_path / "arbol")
    ruta = raiz / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("X=1\n", encoding="utf-8")
    assert va.buscar_secretos(raiz) == [
        {"fichero": nombre, "linea": 0, "clase": "fichero_prohibido",
         "origen": COPIA}]


def test_lo_que_este_proyecto_escribe_de_tokens_y_contrasenas_no_salta(
        tmp_path):
    # Las formas que el arbol usa de verdad: variables, marcadores, valores
    # de ejemplo y codigo. Ninguna es un valor literal que parezca secreto.
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "notas.md").write_text("\n".join([
        'token = os.environ.get("TELEGRAM_TOKEN_AVISOS")',
        'monkeypatch.setenv("TELEGRAM_TOKEN_AVISOS", "T0K3N")',
        "COPILOTO_BD_PASSWORD=cambiar-esto",
        "POSTGRES_PASSWORD: ${COPILOTO_BD_PASSWORD:?falta la contraseña}",
        "TELEGRAM_SECRET_PRUEBA=x python -m pytest",
        'DSN = "host=127.0.0.1 user=postgres password=verifica"',
        '"CRED_SECRETO_PACIENTE": "id-de-ejemplo-secreto-paciente",',
        "$s = Read-Host 'secret_token'; secret_token=$s",
        "password = $(Read-Host 'contraseña')",
        "Authorization: Bearer ${TOKEN_DEL_BOT}",
        "Authorization: Bearer <token>",
        'headers = {"Authorization": f"Bearer {token}"}',
        'api_key = config["api_key"]',
        "secretos: 2 (clave_de_api_akia: 1)",
        "X-Telegram-Bot-Api-Secret-Token: {{ $json.secreto }}",
        # R4: una expresion no es un literal; ni una variable.
        "token = partes[1]",
        "token = sys.argv[1]",
        '"token": "={{ $env.X_2 }}"',
        "Authorization: Bearer <TOKEN_DEL_BOT>",
        "COPILOTO_BD_PASSWORD: ${COPILOTO_BD_PASSWORD:-cambiar-esto}",
        # Un puerto y una ruta con arroba no son una contrasena.
        "https://ejemplo.test:8443/paquete/@ambito/x",
    ]) + "\n", encoding="utf-8")
    assert va.buscar_secretos(raiz) == []


@pytest.mark.parametrize("linea", [
    # A1: una clave que acaba en `_key` en minusculas no nombra un secreto,
    # salvo unas pocas (`private_key`, `access_key`...).
    pytest.param('cache_key = "modelo_v2_2026"', id="cache_key"),
    pytest.param('primary_key="id_consulta_01"', id="primary_key"),
    pytest.param('model_key = "densenet121"', id="model_key"),
    pytest.param('sort_key = "fecha_2026"', id="sort_key"),
    pytest.param('{"cache_key": "modelo_v2_2026"}', id="cache_key_en_json"),
    # A2: una expresion sigue sin ser un literal: suelta, con parentesis,
    # corchetes o llaves; entre comillas, con `{{`, `${`, `$(` o `=` delante.
    pytest.param("token = partes[1]", id="subindice_suelto"),
    pytest.param("token = sys.argv[1]", id="argumento_suelto"),
    pytest.param('"token": "={{ $env.X_2 }}"', id="expresion_de_n8n"),
    pytest.param('"secret": "={{ $credentials.x1 }}"',
                 id="credencial_de_n8n"),
    pytest.param('password = "${CLAVE_2}"', id="variable_entre_comillas"),
    pytest.param('password = "$(Read-Host clave_2)"',
                 id="orden_entre_comillas"),
    pytest.param("Authorization: Bearer <TOKEN_DEL_BOT>", id="marcador"),
    # A3: con subindice o detras de una coma, el valor sin comillas es una
    # variable.
    pytest.param('os.environ["X_TOKEN"] = variable2', id="subindice_variable"),
    pytest.param('setenv("X_PASSWORD", valor_2)', id="coma_variable"),
    pytest.param('setenv("X_PASSWORD", variable2, prepend=None)',
                 id="coma_variable_y_otro_argumento"),
    # A4: un host (con punto, o localhost), un puerto y una ruta con arroba.
    pytest.param("https://ejemplo.test:8443/ruta/@ambito", id="puerto_y_ruta"),
    pytest.param("http://localhost:8000/x@y", id="localhost"),
])
def test_estas_formas_no_son_un_secreto(linea):
    assert va._clases_de_secreto(linea) == []


# A7: el patron de las asignaciones es cuadratico en las tiradas de letras,
# cifras, puntos y guiones; no se aplica a la linea que no lleva ninguna de
# sus palabras clave (ni el de la URL a la que no lleva `://`).
@pytest.mark.parametrize("linea", [
    pytest.param("-" * 100_000, id="guiones"),
    pytest.param("uno.dos.tres.cuatro." * 5_000, id="palabras_con_puntos"),
])
def test_una_linea_larguisima_no_cuesta_segundos(linea):
    assert len(linea) == 100_000
    inicio = time.perf_counter()
    va._clases_de_secreto(linea)
    assert time.perf_counter() - inicio < 2


def test_un_secreto_al_final_de_una_linea_larga_sigue_saltando():
    relleno = "-" * 2_000 + " "
    assert va._clases_de_secreto(relleno + "PASS" + "WORD=" + _LITERAL) == [
        "asignacion_de_secreto"]
    assert va._clases_de_secreto(
        relleno + "postgresql://u" + ":" + "S3creta9x" + "@" + "bd.ejemplo.test"
    ) == ["contrasena_en_url"]


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


def _cli(*argumentos, cwd=None):
    """El script como lo corre una persona: codigo de salida y TODA la
    salida (la normal y la de errores, juntas)."""
    entorno = {c: v for c, v in os.environ.items() if c != "ANONIMATO_LISTA"}
    entorno["PYTHONIOENCODING"] = "utf-8"
    hecho = subprocess.run([sys.executable, "-B", str(SCRIPT), *argumentos],
                           cwd=cwd, capture_output=True, env=entorno)
    salida = (hecho.stdout + hecho.stderr).decode("utf-8", errors="replace")
    return hecho.returncode, salida


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


def test_con_binarios_sin_recorrer_no_dice_limpio_a_secas(tmp_path, capsys):
    raiz = _arbol_limpio(tmp_path / "arbol")          # con figura.png
    huellas = str(_huellas_de_juguete(tmp_path))
    assert va.main(["--raiz", str(raiz), "--huellas", huellas]) == 0
    ultima = capsys.readouterr().out.splitlines()[-1]
    assert ultima != "limpio"
    assert ultima.startswith("limpio lo recorrido")
    assert "1 binario" in ultima and "a mano" in ultima

    (raiz / "figura.png").unlink()
    assert va.main(["--raiz", str(raiz), "--huellas", huellas]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "limpio"


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


def test_la_cli_con_solo_el_centinela_no_dice_limpio(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    publico = tmp_path / "publico.txt"
    publico.write_text("# cabecera\n" + va.huella(CENTINELA) + "\n",
                       encoding="utf-8")
    codigo, salida = _cli("--raiz", str(raiz), "--huellas", str(publico))
    assert codigo == 1
    assert "solo la huella del centinela" in salida
    assert "--huellas" in salida and "repositorio de desarrollo" in salida
    assert "limpio" not in salida.splitlines()
    assert "Traceback" not in salida


def test_la_cli_con_huellas_mal_formadas_dice_la_linea_y_no_su_contenido(
        tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    malo = tmp_path / "malo.txt"
    malo.write_text(f"# cabecera\n{va.huella(OTRO)}\n{OTRO}\n",
                    encoding="utf-8")
    codigo, salida = _cli("--raiz", str(raiz), "--huellas", str(malo))
    assert codigo == 1
    assert "línea 3" in salida
    assert OTRO not in salida.lower()
    assert "Traceback" not in salida


def _sin_rutas_absolutas(salida, *carpetas):
    for carpeta in (*carpetas, RAIZ):
        for forma in (str(carpeta), carpeta.as_posix()):
            assert forma.lower() not in salida.lower()


@hay_git
def test_la_cli_no_imprime_rutas_absolutas(tmp_path):
    raiz = _repositorio(tmp_path)
    (raiz / "docs" / "nota.md").write_text(
        f"{OTRO}\n{_secretos()['clave_de_api_akia']}\n", encoding="utf-8")
    _huellas_de_juguete(tmp_path)
    codigo, salida = _cli("--raiz", "repo", "--huellas", "huellas.txt",
                          "--commit", "--un-solo-commit", cwd=tmp_path)
    assert codigo == 1
    _sin_rutas_absolutas(salida, tmp_path)

    sin_git = tmp_path / "sin_git"
    sin_git.mkdir()
    codigo, salida = _cli("--raiz", str(sin_git), "--huellas", "huellas.txt",
                          "--commit", cwd=tmp_path)
    assert codigo == 1
    _sin_rutas_absolutas(salida, tmp_path)
    for funcion in (va.commits, va.verificar_commit):
        with pytest.raises(SystemExit) as error:
            funcion(sin_git)
        _sin_rutas_absolutas(str(error.value), tmp_path)


def test_la_ruta_de_las_huellas_sale_como_se_paso(tmp_path, monkeypatch):
    monkeypatch.delenv("ANONIMATO_LISTA", raising=False)
    (tmp_path / "lista.txt").write_text("[huellas]\nuno\n", encoding="utf-8")
    codigo, salida = _cli("--regenerar", "--lista", "lista.txt",
                          "--huellas", "sub/huellas.txt", cwd=tmp_path)
    assert codigo == 0
    assert "en sub/huellas.txt" in salida
    _sin_rutas_absolutas(salida, tmp_path)

    # Lo que no se puede leer (una carpeta) tampoco saca la ruta absoluta
    # en una traza de Python.
    arbol = _arbol_limpio(tmp_path / "arbol")
    for orden in (["--raiz", "arbol", "--huellas", "sub"],
                  ["--regenerar", "--lista", "sub",
                   "--huellas", "otra/huellas.txt"]):
        codigo, salida = _cli(*orden, cwd=tmp_path)
        assert codigo == 1
        assert "Traceback" not in salida
        _sin_rutas_absolutas(salida, tmp_path)

    # La de por defecto sale relativa al repositorio.
    publico = tmp_path / "publico.txt"
    publico.write_text(va.huella(CENTINELA) + "\n", encoding="utf-8")
    monkeypatch.setattr(va, "HUELLAS_POR_DEFECTO", publico)
    with pytest.raises(SystemExit) as error:
        va.main(["--raiz", str(arbol)])
    assert "tests/anonimato/huellas.txt" in str(error.value)
    _sin_rutas_absolutas(str(error.value), tmp_path)


def test_la_cli_no_imprime_el_token_ni_en_los_nombres(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    carpeta = raiz / f"Informes-{OTRO.upper()}"
    carpeta.mkdir()
    (carpeta / f"nota_{OTRO}.md").write_text(
        f"uno\n{OTRO}\n{_secretos()['clave_de_api_akia']}\n",
        encoding="utf-8")
    (carpeta / "figura.png").write_bytes(b"\x89PNG\x00\x00")
    codigo, salida = _cli("--raiz", str(raiz),
                          "--huellas", str(_huellas_de_juguete(tmp_path)))
    assert codigo == 1
    assert OTRO not in salida.lower()
    assert _secretos()["clave_de_api_akia"] not in salida
    tapada = f"<huella-{va.huella(OTRO)[:12]}>"
    nota = f"Informes-{tapada}/nota_{tapada}.md"
    assert f"{nota}:0: huella " in salida
    assert f"{nota}:2: huella " in salida
    assert f"{nota}:3: clave_de_api_akia" in salida
    assert f"  Informes-{tapada}/figura.png" in salida
    # La nota da dos hallazgos (nombre y linea 2) y la figura uno (su
    # carpeta): tres, en dos ficheros distintos.
    assert "huellas: 3 en 2 ficheros" in salida


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


@hay_git
def test_un_solo_commit_mira_todas_las_ramas(tmp_path, capsys):
    raiz = _repositorio(tmp_path)
    huellas = str(_huellas_de_juguete(tmp_path))
    _git(raiz, "commit", "-q", "-m", "arbol anonimizado")
    orden = ["--raiz", str(raiz), "--huellas", huellas, "--un-solo-commit"]
    assert va.main(orden) == 0
    salida = capsys.readouterr().out
    assert "commits: 1" in salida and "ramas: 1" in salida
    assert "etiquetas: 0" in salida

    # Otra rama, con un commit que HEAD no alcanza.
    _git(raiz, "checkout", "-q", "-b", "otra")
    (raiz / "codigo.py").write_text("x = 2\n", encoding="utf-8")
    _git(raiz, "commit", "-q", "-a", "-m", "en otra rama")
    _git(raiz, "checkout", "-q", "-")
    assert va.main(orden) == 1
    salida = capsys.readouterr().out
    assert "commits: 2" in salida and "ramas: 2" in salida
    assert va.commits(raiz) == 2


@hay_git
def test_un_solo_commit_no_admite_etiquetas(tmp_path, capsys):
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "arbol anonimizado")
    _git(raiz, "tag", "-a", "v1", "-m", "una etiqueta anotada")
    assert va.main(["--raiz", str(raiz),
                    "--huellas", str(_huellas_de_juguete(tmp_path)),
                    "--un-solo-commit"]) == 1
    salida = capsys.readouterr().out
    assert "commits: 1" in salida and "ramas: 1" in salida
    assert "etiquetas: 1" in salida


@hay_git
@pytest.mark.parametrize("referencia", ["rama", "etiqueta"])
def test_los_nombres_de_ramas_y_etiquetas_se_comparan_con_las_huellas(
        tmp_path, capsys, referencia):
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "arbol")
    nombre = f"informe-{OTRO}"
    if referencia == "rama":
        _git(raiz, "branch", "-m", nombre)      # la unica, a la que va HEAD
    else:
        _git(raiz, "tag", nombre)
    tapada = f"informe-<huella-{va.huella(OTRO)[:12]}>"
    assert va.verificar_referencias(raiz, {va.huella(OTRO)}) == [
        {"referencia": referencia, "nombre": tapada,
         "huella": va.huella(OTRO)}]
    huellas = str(_huellas_de_juguete(tmp_path))
    codigo, salida = _cli("--raiz", str(raiz), "--huellas", huellas,
                          "--commit", "HEAD", "--un-solo-commit")
    assert codigo == 1
    assert OTRO not in salida.lower()
    assert f"{referencia} {tapada}: huella {va.huella(OTRO)[:12]}" in salida

    # La revision que se pasa a --commit sale tapada (R6), exista o no.
    assert va.main(["--raiz", str(raiz), "--huellas", huellas,
                    "--commit", nombre]) == 1
    salida = capsys.readouterr().out
    assert f"commit {tapada}: 0" in salida
    assert OTRO not in salida.lower()
    with pytest.raises(SystemExit) as error:
        va.main(["--raiz", str(raiz), "--huellas", huellas,
                 "--commit", f"inexistente-{OTRO}"])
    assert OTRO not in str(error.value).lower()
    assert "inexistente-<huella-" in str(error.value)


@hay_git
def test_un_secreto_en_el_nombre_de_una_rama_es_un_hallazgo(tmp_path):
    # Un nombre de rama no admite `:`, pero si el token con `%3A`.
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "arbol")
    bot = _token_de_bot().replace(":", "%3A")
    _git(raiz, "branch", "-m", "bot" + bot)
    assert va.verificar_referencias(raiz, set()) == [
        {"referencia": "rama", "nombre": "bot<secreto>",
         "clase": "token_de_bot_de_telegram"}]
    codigo, salida = _cli("--raiz", str(raiz),
                          "--huellas", str(_huellas_de_juguete(tmp_path)),
                          "--commit", "HEAD")
    assert codigo == 1
    assert "rama bot<secreto>: token_de_bot_de_telegram" in salida
    assert bot not in salida and bot[-35:] not in salida


@hay_git
def test_un_secreto_en_el_commit_es_un_hallazgo(tmp_path):
    raiz = _repositorio(tmp_path)
    huellas = str(_huellas_de_juguete(tmp_path))
    bot = _token_de_bot()
    _git(raiz, "commit", "-q", "-m", "arbol", "-m", f"el bot es {bot}")
    assert va.verificar_commit(raiz, huellas=set()) == [
        {"campo": "mensaje", "linea": 3, "clase": "token_de_bot_de_telegram"}]
    codigo, salida = _cli("--raiz", str(raiz), "--huellas", huellas,
                          "--commit", "HEAD")
    assert codigo == 1
    assert bot not in salida
    assert "commit HEAD: mensaje:3: token_de_bot_de_telegram" in salida

    literal = "a1B2c3D4e5F6g7H8"
    clave = _secretos()["clave_de_api_akia"]
    _git(raiz, "commit", "-q", "--allow-empty", "-m", "otro",
         "-m", "PASS" + "WORD=" + literal, GIT_AUTHOR_NAME=clave)
    assert [(h["campo"], h["linea"], h["clase"])
            for h in va.verificar_commit(raiz, huellas=set())] == [
        ("autor", 0, "clave_de_api_akia"),
        ("mensaje", 3, "asignacion_de_secreto")]
    codigo, salida = _cli("--raiz", str(raiz), "--huellas", huellas,
                          "--commit", "HEAD")
    assert codigo == 1
    assert literal not in salida and clave not in salida
    assert "commit HEAD: autor: clave_de_api_akia" in salida


@hay_git
def test_un_solo_commit_mira_el_arbol_del_commit(tmp_path, capsys):
    raiz = _repositorio(tmp_path)
    nota = raiz / "nota.md"
    nota.write_text(f"{OTRO}\n", encoding="utf-8")
    _git(raiz, "add", "nota.md")
    _git(raiz, "commit", "-q", "-m", "arbol")
    nota.write_text("limpia\n", encoding="utf-8")
    _git(raiz, "add", "nota.md")            # copia e indice, limpios
    huellas = str(_huellas_de_juguete(tmp_path))
    assert va.main(["--raiz", str(raiz), "--huellas", huellas]) == 0
    capsys.readouterr()
    assert va.main(["--raiz", str(raiz), "--huellas", huellas,
                    "--un-solo-commit"]) == 1
    salida = capsys.readouterr().out
    assert f"nota.md:1: huella {va.huella(OTRO)[:12]} (commit)" in salida
    assert "commits: 1" in salida and "ramas: 1" in salida
    assert "etiquetas: 0" in salida


def _sin_ninguna_huella(salida, huellas):
    for una in huellas:
        assert una[:12] not in salida


@hay_git
def test_un_solo_commit_no_publica_las_huellas_de_la_lista(
        tmp_path, tmp_path_factory, capsys):
    # V-1: el arbol que se publica lleva un huellas.txt con solo la del
    # centinela (D9). Publicar el del repositorio de desarrollo es publicar,
    # para quien tenga un diccionario, buena parte de la lista.
    huellas = tmp_path / "huellas.txt"
    va.regenerar([OTRO, OTRO_MAS], huellas)     # dos de juguete y el centinela
    todas = va.leer_huellas(huellas)
    # Bajo una carpeta de nombre corto (`v0`, no la de la prueba, de 31
    # caracteres): el fichero con nombre de huella, de 67, cabe en los 260
    # de Windows aunque la carpeta temporal sea larga (A3).
    raiz = _repositorio(tmp_path_factory.mktemp("v"))
    publicado = raiz / "tests" / "anonimato" / "huellas.txt"
    publicado.parent.mkdir(parents=True)
    shutil.copyfile(huellas, publicado)
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "arbol")
    orden = ["--raiz", str(raiz), "--huellas", str(huellas),
             "--un-solo-commit"]

    assert va.main(orden) == 1
    salida = capsys.readouterr().out
    de_la_lista = [n for n, linea in enumerate(
        publicado.read_text(encoding="utf-8").splitlines(), 1)
        if linea in va.huellas_de_la_lista(todas)]
    assert len(de_la_lista) == 2                # la del centinela no cuenta
    for n in de_la_lista:
        assert f"tests/anonimato/huellas.txt:{n}: huella_publicada" in salida
    assert "huellas publicadas: 2" in salida
    assert salida.splitlines()[-1] == "NO publicar: hay hallazgos"
    _sin_ninguna_huella(salida, todas)
    # Sin --un-solo-commit no se mira: el repositorio de desarrollo lleva su
    # propio huellas.txt.
    assert va.main(orden[:-1]) == 0
    capsys.readouterr()

    # Con solo la del centinela, como se publica: limpio.
    assert va.main(["--regenerar", "--solo-centinela",
                    "--huellas", str(publicado)]) == 0
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "--amend", "-m", "arbol")
    capsys.readouterr()
    assert va.main(orden) == 0
    salida = capsys.readouterr().out
    assert "huellas publicadas: 0" in salida

    # Una huella de la lista copiada en otro fichero (un informe), o en su
    # nombre: tambien se publicaria.
    (raiz / "docs" / "informe.md").write_text(
        f"# Informe\n\nla huella {va.huella(OTRO).upper()} y nada mas\n",
        encoding="utf-8")
    # En la raiz y no en una carpeta: un nombre de 67 caracteres, con una
    # carpeta temporal larga, pasaria de los 260 de Windows (C2).
    (raiz / f"{va.huella(OTRO_MAS)}.md").write_text("nada\n",
                                                    encoding="utf-8")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "--amend", "-m", "arbol")
    assert va.main(orden) == 1
    salida = capsys.readouterr().out
    assert "docs/informe.md:3: huella_publicada" in salida
    assert "<huella-publicada>.md:0: huella_publicada" in salida.splitlines()
    assert "huellas publicadas: 2" in salida
    _sin_ninguna_huella(salida, todas)
    _sin_ninguna_huella(salida.lower(), todas)


@hay_git
def test_un_solo_commit_mira_las_huellas_del_mensaje_y_de_las_ramas(
        tmp_path, capsys):
    # C6: el mensaje del commit y los nombres de las ramas y de las
    # etiquetas tambien se publican.
    huellas = tmp_path / "huellas.txt"
    va.regenerar([OTRO, OTRO_MAS], huellas)
    todas = va.leer_huellas(huellas)
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "arbol",
         "-m", f"la huella {va.huella(OTRO)}")
    _git(raiz, "branch", "-m", f"informe-{va.huella(OTRO_MAS)}")
    _git(raiz, "tag", f"v-{va.huella(OTRO)}")
    orden = ["--raiz", str(raiz), "--huellas", str(huellas)]

    assert va.main(orden + ["--un-solo-commit"]) == 1
    salida = capsys.readouterr().out
    assert "commit HEAD: mensaje:3: huella_publicada" in salida
    assert ("rama informe-<huella-publicada>: huella_publicada"
            in salida.splitlines())
    assert ("etiqueta v-<huella-publicada>: huella_publicada"
            in salida.splitlines())
    _sin_ninguna_huella(salida, todas)
    # Con --commit a secas no se miran: el repositorio de desarrollo puede
    # citar una huella en un commit o en una rama.
    assert va.main(orden + ["--commit"]) == 0
    salida = capsys.readouterr().out
    assert "huella_publicada" not in salida
    _sin_ninguna_huella(salida, todas)


@hay_git
def test_un_solo_commit_da_por_hallazgo_la_cabecera_parent(tmp_path, capsys):
    # Por la linea de ordenes: `main` pasa --un-solo-commit a las cabeceras.
    # En un clon superficial el recuento de commits da 1 y el padre es lo
    # unico que avisa.
    raiz = _repositorio(tmp_path)
    huellas = str(_huellas_de_juguete(tmp_path))
    _git(raiz, "commit", "-q", "-m", "uno")
    _git(raiz, "commit", "-q", "--allow-empty", "-m", "dos")
    assert va.main(["--raiz", str(raiz), "--huellas", huellas,
                    "--un-solo-commit"]) == 1
    salida = capsys.readouterr().out
    assert "commit HEAD: parent: cabecera_del_commit" in salida.splitlines()
    assert va.main(["--raiz", str(raiz), "--huellas", huellas,
                    "--commit"]) == 0
    assert "cabecera_del_commit" not in capsys.readouterr().out


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


def test_la_cli_no_regenera_con_una_entrada_mala_ni_dice_cual(tmp_path,
                                                             monkeypatch):
    monkeypatch.delenv("ANONIMATO_LISTA", raising=False)
    lista = tmp_path / "lista.txt"
    lista.write_text(f"[huellas]\nuno\nzorro-{OTRO}\n", encoding="utf-8")
    destino = tmp_path / "huellas.txt"
    with pytest.raises(SystemExit) as salida:
        va.main(["--regenerar", "--lista", str(lista),
                 "--huellas", str(destino)])
    assert "2" in str(salida.value)
    assert OTRO not in str(salida.value).lower()
    assert "zorro" not in str(salida.value).lower()
    assert not destino.exists()

    lista.write_text("[huellas]\n# nada\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        va.main(["--regenerar", "--lista", str(lista),
                 "--huellas", str(destino)])
    assert not destino.exists()


def test_la_cli_sin_lista_dice_que_variable_falta(tmp_path, monkeypatch):
    monkeypatch.delenv("ANONIMATO_LISTA", raising=False)
    with pytest.raises(SystemExit) as salida:
        va.main(["--regenerar", "--huellas", str(tmp_path / "h.txt")])
    assert "ANONIMATO_LISTA" in str(salida.value)
    assert not (tmp_path / "h.txt").exists()


def test_la_cli_escribe_el_huellas_txt_del_repositorio_que_se_publica(
        tmp_path, monkeypatch, capsys):
    # Sin lista: con --solo-centinela no se lee ni --lista ni la variable
    # (aqui apunta a un fichero que no existe).
    monkeypatch.setenv("ANONIMATO_LISTA", str(tmp_path / "no-existe.txt"))
    destino = tmp_path / "publico" / "huellas.txt"
    assert va.main(["--regenerar", "--solo-centinela",
                    "--huellas", str(destino)]) == 0
    assert "1 huella escrita" in capsys.readouterr().out
    assert va.leer_huellas(destino) == {va.huella(CENTINELA)}
    assert solo_el_centinela(destino)
    _cabecera_y_huellas_ordenadas(destino)
    # Con SU cabecera, que dice que lleva solo la del centinela a proposito.
    assert destino.read_text(encoding="utf-8") == (
        va.CABECERA_SOLO_CENTINELA + va.huella(CENTINELA) + "\n")


def test_la_cli_con_solo_centinela_no_escribe_donde_no_se_le_dice(
        tmp_path, monkeypatch):
    # Sin --huellas escribiria encima del huellas.txt de este repositorio,
    # que en el de desarrollo lleva la lista entera (aqui, uno de juguete que
    # no existe); con --lista, o sin --regenerar, la orden no tiene sentido.
    # Ninguna escribe nada.
    por_defecto = tmp_path / "por_defecto" / "huellas.txt"
    monkeypatch.setattr(va, "HUELLAS_POR_DEFECTO", por_defecto)
    lista = tmp_path / "lista.txt"
    lista.write_text("[huellas]\nuno\n", encoding="utf-8")
    destino = tmp_path / "huellas.txt"
    for orden in (["--regenerar", "--solo-centinela"],
                  ["--regenerar", "--solo-centinela", "--lista", str(lista),
                   "--huellas", str(destino)],
                  ["--solo-centinela", "--huellas", str(destino)]):
        with pytest.raises(SystemExit) as error:
            va.main(orden)
        assert "--solo-centinela" in str(error.value)
        assert not por_defecto.exists() and not destino.exists()
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
1 error in 0.31s
```

- [ ] **Paso 3: Escribir el script**

Crear `scripts/verificar_anonimato.py`:

```python
"""Comprueba que el repositorio se puede publicar (spec de SP5 §6.1).

Uso, desde la raiz del repositorio:

    python scripts/verificar_anonimato.py
    python scripts/verificar_anonimato.py --raiz <arbol> --huellas <huellas> --un-solo-commit
    python scripts/verificar_anonimato.py --regenerar --lista <lista en claro>
    python scripts/verificar_anonimato.py --regenerar --solo-centinela --huellas <destino>

Mira lo que se publicaria: la copia de trabajo (en un repositorio, lo que
tiene seguimiento y lo que no lo tiene ni esta ignorado), lo preparado en el
indice que no es lo que hay en disco y, con --commit (o --un-solo-commit,
que lo implica), el arbol de ese commit, su autor, quien lo confirma, su
mensaje y sus cabeceras, y los nombres de las ramas y de las etiquetas.
Busca:

1. HUELLAS. La lista de cadenas que identifican al cliente, a la empresa, a la
   maquina o a los integrantes NO vive en el repositorio. El repositorio lleva
   solo `tests/anonimato/huellas.txt`: el sha256 de cada token (en el de
   desarrollo, la lista entera; en el que se publica, solo la del centinela,
   D9). Cada fichero de texto se tokeniza igual que la lista (minusculas, sin
   tildes, particion por todo lo que no sea [a-z0-9], tambien desescapado) y
   se compara huella con huella.
2. SECRETOS, por patron: token de bot de Telegram, claves de API, claves
   privadas, cabeceras Authorization, contrasena dentro de una URL,
   asignaciones de contrasenas, tokens y claves, y ficheros que no deben
   viajar (`.env`, claves). Una asignacion se reconoce por el NOMBRE de la
   clave (lleva `password`, `passwd`, `secret`, `token` o `api_key`; o acaba
   en `_KEY` escrito en mayusculas, o en `access_key`, `private_key`,
   `encryption_key`, `signing_key`, `client_key` o `master_key`) y cuenta si
   su valor es un literal con forma de secreto: entre comillas, salvo una
   expresion (`{{`, `${`, `$(`, o `=` delante); suelto, si no lleva
   parentesis, corchetes ni llaves; con subindice o detras de una coma, solo
   entre comillas. Un enlace simbolico o un submodulo es un hallazgo
   `no_recorrido`. Los nombres de las ramas y de las etiquetas se miran
   tambien contra estos patrones.
3. Con --commit, las CABECERAS del commit: la que no sea `tree`, `author` ni
   `committer` es un hallazgo (una firma lleva el identificador de la clave
   de quien firma); `parent`, solo con --un-solo-commit.
4. Con --un-solo-commit (la orden de publicar), las HUELLAS PUBLICADAS: una
   huella de la lista escrita en el arbol que se publica, en el commit (su
   mensaje, su autor, quien lo confirma) o en el nombre de una rama o de una
   etiqueta. Su `huellas.txt` tiene que llevar solo la del centinela, con
   su propia cabecera: lo escribe --regenerar --solo-centinela.

Ninguna salida lleva el token ni el secreto en claro: fichero, linea y huella
o clase. En los nombres (de fichero, de rama, de etiqueta, la revision) el
token sale tapado por el principio de su huella, el secreto por
`<secreto>` y una huella de la lista por `<huella-publicada>`; las rutas
salen relativas a la raiz que se recorre (la de las huellas, como se paso).

Sale con 0 si no hay hallazgos y con 1 si los hay, si no se ha recorrido
ningun fichero de texto o si las huellas son solo la del centinela. Con
binarios sin recorrer, la ultima linea no dice «limpio» a secas: se revisan a
mano. Lo usa `tests/test_anonimato.py`, que lo carga por ruta.
"""
import argparse
import codecs
import fnmatch
import hashlib
import html
import os
import re
import subprocess
import sys
import unicodedata
import urllib.parse
from pathlib import Path
from typing import NamedTuple, Optional

REPO = Path(__file__).resolve().parents[1]
HUELLAS_POR_DEFECTO = REPO / "tests" / "anonimato" / "huellas.txt"
HUELLAS_MOSTRADAS = "tests/anonimato/huellas.txt"   # en las salidas
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
#   python scripts/verificar_anonimato.py --regenerar --lista <lista en claro>
"""
# La del `huellas.txt` del repositorio que se publica (--solo-centinela).
CABECERA_SOLO_CENTINELA = """\
# Huellas del anonimato (spec de SP5 §6.1), del repositorio que se publica.
# Lleva solo la huella del centinela público `centinelaanonimato7f3a`, y es
# a propósito: la lista entera de huellas no se publica, porque la huella
# de un token corto se adivina probando candidatos. La comprobación del
# árbol se hace antes de publicar, con scripts/verificar_anonimato.py y las
# huellas del repositorio de desarrollo.
# No se edita a mano. Se escribe con:
#   python scripts/verificar_anonimato.py --regenerar --solo-centinela --huellas <este fichero>
"""


# --------------------------------------------------------------------------
# Tokens y huellas
# --------------------------------------------------------------------------
def _normalizados(texto):
    """El texto con la normalizacion de compatibilidad (NFKD: descompone las
    tildes y el ancho completo) y sin las marcas de combinacion (Mn).

    Los caracteres de formato (Cf: U+200B, U+00AD...) se tratan de las dos
    maneras, y se devuelven los dos textos: BORRADOS (`to<U+200B>ken` da
    `token`) y como SEPARADOR (`alfa<U+200B>token` da `token`).
    """
    if texto.isascii():                 # ni Mn ni Cf: nada que normalizar
        return (texto,)
    borrados, partidos, hay_formato = [], [], False
    for c in unicodedata.normalize("NFKD", texto):
        categoria = unicodedata.category(c)
        if categoria == "Mn":
            continue
        if categoria == "Cf":
            hay_formato = True
            partidos.append(" ")
            continue
        borrados.append(c)
        partidos.append(c)
    if hay_formato:
        return "".join(borrados), "".join(partidos)
    return ("".join(borrados),)


def _partir(texto):
    hallados = set()
    for normal in _normalizados(BASE64.sub(" ", texto)):
        hallados |= set(NO_TOKEN.split(normal.lower()))
    return hallados - {""}


# Los escapes pegan letras al token: `\n` delante da `n...`, `%20` da `20...`,
# `&#99;` parte la primera letra. Se tokeniza tambien el texto desescapado.
HAY_ESCAPE = re.compile(r"\\[ntru]|%[0-9A-Fa-f]{2}|&(?:#|[A-Za-z]+;)")
ESCAPE_DE_CONTROL = re.compile(r"\\[ntr]")
ESCAPE_UNICODE = re.compile(r"\\u([0-9A-Fa-f]{4})")


def _desescapado(texto):
    """`\\n`, `\\t` y `\\r` escritos con barra pasan a un espacio; `\\uXXXX`,
    `%XX` y las entidades HTML, a su caracter."""
    texto = ESCAPE_DE_CONTROL.sub(" ", texto)
    texto = ESCAPE_UNICODE.sub(lambda m: chr(int(m.group(1), 16)), texto)
    texto = urllib.parse.unquote(texto, errors="replace")
    return html.unescape(texto)


def tokens(texto):
    """Los tokens de un texto: la misma regla para la lista y los ficheros.

    La union de los del texto tal cual y los del texto desescapado.
    """
    hallados = _partir(texto)
    if HAY_ESCAPE.search(texto):
        hallados |= _partir(_desescapado(texto))
    return hallados


def huella(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


UNA_HUELLA = re.compile(r"[0-9a-f]{64}")


def leer_huellas(ruta):
    """Las huellas de `huellas.txt`, sin la cabecera ni lineas vacias.

    Cada linea que no sea comentario tiene que ser una huella: 64 caracteres
    hexadecimales en minusculas. Si no, ValueError con el NUMERO de la linea
    (nunca su contenido: podria ser un token en claro).
    """
    huellas = set()
    lineas = Path(ruta).read_text(encoding="utf-8-sig").splitlines()
    for n, linea in enumerate(lineas, 1):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if not UNA_HUELLA.fullmatch(linea):
            raise ValueError(
                f"la línea {n} no es una huella (64 caracteres hexadecimales "
                "en minúsculas)")
        huellas.add(linea)
    return huellas


def huellas_de_la_lista(huellas):
    """Las huellas sin la del centinela: lo que se busca en el arbol."""
    return set(huellas) - {huella(CENTINELA)}


def leer_lista(ruta):
    """Las entradas de la seccion `[huellas]` de la lista en claro.

    Admite la marca de orden de bytes; los nombres de seccion no distinguen
    mayusculas; lo que sigue a un `#` en una linea es comentario.
    """
    entradas, dentro = [], False
    for linea in Path(ruta).read_text(encoding="utf-8-sig").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        if linea.startswith("["):
            dentro = linea.lower() == "[huellas]"
        elif dentro:
            entradas.append(linea)
    return entradas


def regenerar(lista, destino):
    """Escribe las huellas de los tokens de `lista`, ordenadas, y las cuenta.

    Cada entrada tiene que dar EXACTAMENTE un token (`zorro-azul.test` da
    tres: la lista se tokeniza a mano, un token por linea). Si alguna no, o
    si no hay entradas, ValueError con los NUMEROS de entrada (nunca su
    contenido) y no se escribe nada. La del centinela va siempre.
    """
    if not lista:
        raise ValueError("la sección [huellas] de la lista no tiene entradas")
    todas, malas = {huella(CENTINELA)}, []
    for n, entrada in enumerate(lista, 1):
        suyos = tokens(entrada)
        if len(suyos) == 1:
            todas |= {huella(t) for t in suyos}
        else:
            malas.append(n)
    if malas:
        raise ValueError(
            f"{len(malas)} entradas de [huellas] no dan exactamente un token "
            f"(números de entrada: {', '.join(map(str, malas))}); pon un "
            "token por línea")
    return _escribir_huellas(todas, destino)


def regenerar_solo_centinela(destino):
    """Escribe el `huellas.txt` del repositorio que se publica (D9): su
    cabecera (CABECERA_SOLO_CENTINELA) y la huella del centinela, sin
    lista."""
    return _escribir_huellas({huella(CENTINELA)}, destino,
                             CABECERA_SOLO_CENTINELA)


def _escribir_huellas(todas, destino, cabecera=CABECERA):
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="\n") as salida:
        salida.write(cabecera)
        for una in sorted(todas):
            salida.write(una + "\n")
    return len(todas)


# --------------------------------------------------------------------------
# El recorrido: lo que se publicaria
# --------------------------------------------------------------------------
# De donde sale cada cosa que se recorre (clave `origen` de los hallazgos).
COPIA, INDICE, COMMIT = "copia de trabajo", "indice", "commit"


# Variables que harian que git mirase otro repositorio, otro indice u otra
# copia de trabajo que la de `raiz` (un gancho de git las pone, por ejemplo).
NO_HEREDADAS = ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE",
                "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE")


def _git(raiz, *argumentos, entrada=None):
    """La salida de git en bytes, o None si git falla o no esta.

    Sobre `raiz` y solo sobre ella: no hereda las variables de NO_HEREDADAS.
    """
    entorno = {c: v for c, v in os.environ.items() if c not in NO_HEREDADAS}
    try:
        hecho = subprocess.run(["git", "-C", str(raiz), *argumentos],
                               input=entrada, capture_output=True,
                               check=False, env=entorno)
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


def _partir_z(salida):
    return [n for n in salida.decode("utf-8", errors="replace").split("\0")
            if n]


def _indice(raiz):
    """Las entradas del indice: {nombre: [(modo, sha), ...]}, una por
    etapa."""
    salida = _git(raiz, "ls-files", "-s", "-z")
    if salida is None:
        return None
    indice = {}
    for linea in _partir_z(salida):
        cabecera, nombre = linea.split("\t", 1)
        modo, sha, _etapa = cabecera.split()
        indice.setdefault(nombre, []).append((modo, sha))
    return indice


def _sin_seguimiento(raiz):
    """Lo que no tiene seguimiento ni esta ignorado (`git add -A` lo anade).

    Una carpeta que es otro repositorio sale con `/` al final.
    """
    salida = _git(raiz, "ls-files", "-z", "--others", "--exclude-standard")
    return None if salida is None else _partir_z(salida)


def _arbol_del_commit(raiz, revision, huellas=()):
    """{nombre: (modo, sha)} del arbol de `revision`, bajo `raiz`."""
    salida = _git(raiz, "ls-tree", "-r", "-z", revision, "--")
    if salida is None:
        raise SystemExit("No se pudo leer el árbol del commit "
                         f"{_publicable(revision, huellas)}: ¿es un "
                         "repositorio de git con commits?")
    arbol = {}
    for linea in _partir_z(salida):
        cabecera, nombre = linea.split("\t", 1)
        modo, _tipo, sha = cabecera.split()
        arbol[nombre] = (modo, sha)
    return arbol


def _blobs(raiz, shas):
    """{sha: contenido} de los blobs pedidos, con una sola llamada a git."""
    shas = sorted(set(shas))
    if not shas:
        return {}
    salida = _git(raiz, "cat-file", "--batch",
                  entrada=("\n".join(shas) + "\n").encode("ascii")) or b""
    blobs, i = {}, 0
    while i < len(salida):
        fin = salida.index(b"\n", i)
        cabecera = salida[i:fin].split()
        i = fin + 1
        if len(cabecera) != 3:                  # «<sha> missing»
            continue
        sha, tamano = cabecera[0].decode("ascii"), int(cabecera[2])
        blobs[sha] = salida[i:i + tamano]
        i += tamano + 1
    return blobs


def _en_git(raiz):
    """Indice y lo sin seguimiento, o None si `raiz` no es la raiz de un
    repositorio de git."""
    if not _es_la_raiz_de_un_repositorio(raiz):
        return None
    indice, otros = _indice(raiz), _sin_seguimiento(raiz)
    if indice is None or otros is None:
        return None
    return indice, otros


def _recorrer_carpeta(raiz):
    """Todo lo que hay debajo de `raiz` salvo las carpetas `.git/`: los
    ficheros, y aparte los enlaces simbolicos (que no se siguen)."""
    ficheros, enlaces = [], []
    for carpeta, subcarpetas, nombres in os.walk(raiz):
        carpeta = Path(carpeta)
        enlaces += [carpeta / s for s in subcarpetas
                    if _es_enlace(carpeta / s)]
        subcarpetas[:] = [s for s in subcarpetas
                          if s != ".git" and not _es_enlace(carpeta / s)]
        for n in nombres:
            (enlaces if _es_enlace(carpeta / n) else ficheros).append(
                carpeta / n)
    orden = lambda p: p.relative_to(raiz).as_posix()  # noqa: E731
    return sorted(ficheros, key=orden), sorted(enlaces, key=orden)


def _es_enlace(ruta):
    """Enlace simbolico (o, en Windows, union de carpetas): no se sigue."""
    es_union = getattr(os.path, "isjunction", lambda _ruta: False)
    return os.path.islink(ruta) or es_union(ruta)


def ficheros_versionados(raiz):
    """Los ficheros de la copia de trabajo que se publicarian, ordenados.

    En la raiz de un repositorio de git, los que tienen seguimiento y los que
    no lo tienen ni estan ignorados. Si `raiz` no es la raiz de un
    repositorio, todos los que hay debajo salvo la carpeta `.git/`. Los
    enlaces simbolicos no (no se recorren: ver `_piezas`).
    """
    raiz = Path(raiz)
    en_git = _en_git(raiz)
    if en_git is None:
        return _recorrer_carpeta(raiz)[0]
    indice, otros = en_git
    nombres = sorted(set(indice) | {n for n in otros if not n.endswith("/")})
    return [raiz / n for n in nombres
            if (raiz / n).is_file() and not _es_enlace(raiz / n)]


# La de UTF-32 antes que la de UTF-16: la de UTF-32 LE empieza por la otra.
MARCAS_DE_ORDEN = ((codecs.BOM_UTF32_LE, "utf-32"),
                   (codecs.BOM_UTF32_BE, "utf-32"),
                   (codecs.BOM_UTF8, "utf-8-sig"),
                   (codecs.BOM_UTF16_LE, "utf-16"),
                   (codecs.BOM_UTF16_BE, "utf-16"))


def _cp1252_suelto(error):
    """Lo que no es UTF-8 se lee como cp1252 (el CSV de Excel), byte a byte:
    un byte suelto no estropea las tildes del resto del fichero."""
    trozo = error.object[error.start:error.end]
    return trozo.decode("cp1252", errors="replace"), error.end


codecs.register_error("verificar_anonimato.cp1252", _cp1252_suelto)


def _texto_de(datos):
    """El texto de unos bytes, o None si no es texto.

    Con marca de orden de bytes, en su codificacion (UTF-8, UTF-16 o
    UTF-32). Sin ella: binario si lleva algun byte nulo; si no, UTF-8, y lo
    que no lo sea, cp1252 (lo que no se pueda decodificar se sustituye).
    """
    for marca, codificacion in MARCAS_DE_ORDEN:
        if datos.startswith(marca):
            return datos.decode(codificacion, errors="replace")
    if b"\0" in datos:
        return None
    return datos.decode("utf-8", errors="verificar_anonimato.cp1252")


def _texto(ruta):
    """El texto del fichero, o None si no es texto."""
    return _texto_de(Path(ruta).read_bytes())


def es_texto(ruta):
    """Es texto lo que tiene marca de orden de bytes o no lleva bytes nulos
    (ver `_texto_de`)."""
    return _texto(ruta) is not None


def binarios(raiz):
    """Lo que no es texto: se declara y se revisa a mano, no se recorre."""
    return [p for p in ficheros_versionados(raiz) if not es_texto(p)]


def _relativo(ruta, raiz):
    return Path(ruta).relative_to(raiz).as_posix()


class _Pieza(NamedTuple):
    """Una cosa que se publicaria: un contenido con su nombre y su origen."""
    nombre: str             # relativo a la raiz, con `/`
    origen: str             # COPIA, INDICE o COMMIT
    texto: Optional[str]    # None: binario, o no recorrida
    primera: bool           # la primera pieza de ese nombre: se mira el nombre
    recorrida: bool = True  # False: enlace simbolico, submodulo o ilegible


# Modos de git cuyo contenido no es el de un fichero: no se recorren.
ENLACE_SIMBOLICO, SUBMODULO = "120000", "160000"


def _piezas(raiz, commit=None, huellas=()):
    """Lo que se publicaria bajo `raiz`, sin recorrer dos veces un contenido.

    1. La copia de trabajo (en un repositorio, lo que tiene seguimiento y lo
       que no lo tiene ni esta ignorado).
    2. El indice: lo preparado que no es lo que hay en disco, o cuyo fichero
       ya no esta en disco.
    3. Con `commit`, el arbol de ese commit.

    Un enlace simbolico, un submodulo (o otro repositorio dentro, sin
    seguimiento) y un contenido que git no entrega no se recorren, pero no
    en silencio: son piezas con `recorrida=False`. Las `huellas` solo sirven
    para tapar la revision en un mensaje de error.
    """
    raiz = Path(raiz)
    en_git = _en_git(raiz)
    arbol = ({} if commit is None
             else _arbol_del_commit(raiz, commit, huellas))
    if en_git is None:
        indice = {}
        ficheros, enlaces = _recorrer_carpeta(raiz)
        en_disco = {_relativo(r, raiz) for r in ficheros}
        sin_mirar = {_relativo(r, raiz) for r in enlaces}
    else:
        indice, otros = en_git
        en_disco = set(indice) | {n for n in otros if not n.endswith("/")}
        sin_mirar = {n.rstrip("/") for n in otros if n.endswith("/")}

    especiales = (ENLACE_SIMBOLICO, SUBMODULO)
    del_indice = {nombre: {sha for _modo, sha in entradas}
                  for nombre, entradas in indice.items()}
    pedidos = [sha for entradas in indice.values()
               for modo, sha in entradas if modo not in especiales]
    pedidos += [sha for nombre, (modo, sha) in arbol.items()
                if modo not in especiales
                and sha not in del_indice.get(nombre, ())]
    blobs = _blobs(raiz, pedidos)

    piezas, vistos, nombres_vistos, no_recorridos = [], {}, set(), set()

    def primera(nombre):
        es_la_primera = nombre not in nombres_vistos
        nombres_vistos.add(nombre)
        return es_la_primera

    def poner(nombre, origen, datos):
        # El mismo contenido con otros finales de linea es el mismo contenido
        # (core.autocrlf): no se recorre dos veces.
        firma = hashlib.sha256(datos.replace(b"\r\n", b"\n")).digest()
        suyas = vistos.setdefault(nombre, set())
        if firma in suyas:
            return
        suyas.add(firma)
        piezas.append(_Pieza(nombre, origen, _texto_de(datos),
                             primera(nombre)))

    def no_recorrer(nombre, origen):
        if nombre not in no_recorridos:
            no_recorridos.add(nombre)
            piezas.append(_Pieza(nombre, origen, None, primera(nombre),
                                 recorrida=False))

    for nombre in sorted(en_disco | sin_mirar | set(indice) | set(arbol)):
        ruta = raiz / nombre
        if nombre in sin_mirar or (nombre in en_disco and _es_enlace(ruta)):
            no_recorrer(nombre, COPIA)
        elif nombre in en_disco and ruta.is_file():
            try:
                poner(nombre, COPIA, ruta.read_bytes())
            except OSError:                     # sin permiso, bloqueado...
                no_recorrer(nombre, COPIA)
        for modo, sha in indice.get(nombre, ()):
            if modo in especiales or sha not in blobs:
                no_recorrer(nombre, INDICE)
            else:
                poner(nombre, INDICE, blobs[sha])
        if nombre in arbol:
            modo, sha = arbol[nombre]
            if modo in especiales or (sha not in blobs and
                                      sha not in del_indice.get(nombre, ())):
                no_recorrer(nombre, COMMIT)
            elif sha not in del_indice.get(nombre, ()):
                poner(nombre, COMMIT, blobs[sha])
    return piezas


def _huellas_en(piezas, huellas):
    huellas = set(huellas)
    hallazgos = []

    def mirar(texto, fichero, linea, origen):
        for una in sorted({huella(t) for t in tokens(texto)} & huellas):
            hallazgos.append({"fichero": fichero, "linea": linea,
                              "huella": una, "origen": origen})

    for pieza in piezas:
        fichero = _publicable(pieza.nombre, huellas)
        if pieza.primera:
            mirar(pieza.nombre, fichero, 0, pieza.origen)
        if pieza.texto is None:
            continue
        for n, linea in enumerate(pieza.texto.splitlines(), 1):
            mirar(linea, fichero, n, pieza.origen)
    return hallazgos


def buscar_huellas(raiz, huellas, commit=None):
    """Las apariciones de alguna huella: fichero, linea, huella y origen.

    La linea 0 es el nombre del fichero. El token en claro no sale nunca.
    Con `commit`, tambien el arbol de ese commit.
    """
    return _huellas_en(_piezas(raiz, commit, huellas), huellas)


# Un token de 64 hexadecimales: lo que es una huella escrita en un fichero.
TOKEN_HEXADECIMAL = re.compile(r"(?<![A-Za-z0-9])[0-9A-Fa-f]{64}(?![A-Za-z0-9])")


def _huellas_escritas(texto, huellas):
    """Las huellas de `huellas` escritas en el texto, como token suelto de
    64 hexadecimales (en mayusculas o en minusculas)."""
    return [m.group().lower() for m in TOKEN_HEXADECIMAL.finditer(texto)
            if m.group().lower() in huellas]


def _huellas_publicadas_en(piezas, huellas):
    """Las huellas de la lista (`huellas`, ya sin la del centinela) escritas
    en lo que se publica: fichero, linea, clase `huella_publicada` y origen.
    La huella no sale nunca.

    Solo para el arbol que se publica (--un-solo-commit): el de desarrollo
    lleva su propio `huellas.txt` con la lista entera. Publicarlo es
    publicar, para quien tenga un diccionario, buena parte de la lista (D9).
    El mensaje del commit y los nombres de las ramas y de las etiquetas se
    miran igual (`verificar_commit`, `verificar_referencias`).
    """
    huellas = set(huellas)
    hallazgos = []

    def mirar(texto, fichero, linea, origen):
        for _una in _huellas_escritas(texto, huellas):
            hallazgos.append({"fichero": fichero, "linea": linea,
                              "clase": "huella_publicada", "origen": origen})

    for pieza in piezas:
        fichero = _publicable(pieza.nombre, huellas)
        if pieza.primera:
            mirar(pieza.nombre, fichero, 0, pieza.origen)
        if pieza.texto is None:
            continue
        for n, linea in enumerate(pieza.texto.splitlines(), 1):
            mirar(linea, fichero, n, pieza.origen)
    return hallazgos


def _tapar_tokens(parte, huellas):
    """El componente con cada token de la lista cambiado por `<huella-...>`,
    el principio de su huella; lo demas se queda (`informe-<huella-...>.md`),
    para que dos nombres distintos no salgan iguales. Un token que ES una
    huella de la lista pasa a `<huella-publicada>`: no se imprime.

    Recorre el texto original: los caracteres que normalizados dan
    `[a-z0-9]` forman el token; los que no dan nada (marcas, formato) van
    dentro; cualquier otro lo corta.
    """
    salida, tramo, token = [], [], []

    def cerrar():
        if tramo:
            una = huella("".join(token))
            if una in huellas:
                salida.append(f"<huella-{una[:12]}>")
            elif "".join(token) in huellas:
                salida.append("<huella-publicada>")
            else:
                salida.append("".join(tramo))
            tramo.clear()
            token.clear()

    for c in parte:
        normal = _normalizados(c)[0].lower()
        if not normal:
            (tramo if tramo else salida).append(c)
        elif NO_TOKEN.search(normal) is None:
            tramo.append(c)
            token.append(normal)
        else:
            cerrar()
            salida.append(c)
    cerrar()
    return "".join(salida)


def _publicable(fichero, huellas):
    """El nombre que puede salir en una salida: en cada componente de la
    ruta, el token de la lista pasa a `<huella-...>` (ver `_tapar_tokens`) y
    el secreto a `<secreto>`.

    Si aun asi el componente da un token o un secreto (uno que solo se ve
    desescapado, por ejemplo), se tapa el componente entero.
    """
    huellas = set(huellas)
    partes = []
    for parte in fichero.split("/"):
        tapada = _tapar_tokens(_tapar_secretos(parte), huellas)
        quedan = sorted({huella(t) for t in tokens(tapada)} & huellas)
        if quedan:
            tapada = "<huella-" + "+".join(h[:12] for h in quedan) + ">"
        elif _clases_de_secreto(tapada):
            tapada = "<secreto>"
        partes.append(tapada)
    return "/".join(partes)


# --------------------------------------------------------------------------
# Secretos
# --------------------------------------------------------------------------
PATRONES_DE_SECRETO = {
    # Suelto, o pegado a `bot` (o `Bot`, `BOT`) como va en la URL de la API
    # de Telegram; los dos puntos, tal cual o escapados (`%3A`).
    "token_de_bot_de_telegram": re.compile(
        r"(?:(?<=[bB][oO][tT])|(?<![0-9A-Za-z]))\d{8,12}(?::|%3[aA])"
        r"[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])"),
    "clave_de_api_sk": re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    "clave_de_api_akia": re.compile(
        r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![0-9A-Z])"),
    "clave_de_api_asia": re.compile(
        r"(?<![A-Z0-9])ASIA[0-9A-Z]{16}(?![0-9A-Z])"),
    "clave_de_api_aiza": re.compile(
        r"(?<![A-Za-z0-9_-])AIza[0-9A-Za-z_-]{35}(?![0-9A-Za-z_-])"),
    "clave_de_api_ghp": re.compile(r"(?<![A-Za-z0-9])ghp_[A-Za-z0-9]{36}"),
    "clave_de_api_gho": re.compile(r"(?<![A-Za-z0-9])gho_[A-Za-z0-9]{36}"),
    "clave_de_api_ghs": re.compile(r"(?<![A-Za-z0-9])ghs_[A-Za-z0-9]{36}"),
    "clave_de_api_github_pat": re.compile(
        r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{22,}"),
    "jwt": re.compile(
        r"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    # La cabecera de una clave privada (RSA, OPENSSH, EC, PGP, sin tipo...).
    "clave_privada": re.compile(r"-----BEGIN[A-Z0-9 ]*PRIVATE KEY"),
    # Con un valor literal largo: `${TOKEN}`, `<token>` o `{token}` no.
    "cabecera_authorization": re.compile(
        r"(?i)authorization[\"']?\s*[:=]\s*[\"']?(?:basic|bearer)\s+"
        r"[A-Za-z0-9._~+/=-]{20,}"),
}

# Esquema, dos barras, usuario (puede ir vacio), dos puntos, contrasena
# (puede llevar `/`: la de base64 casi siempre la lleva), arroba y host.
URL_CON_CONTRASENA = re.compile(
    r"[A-Za-z][A-Za-z0-9+.-]*://(?P<usuario>[^\s/:@]*):"
    r"(?P<contrasena>[^\s@]+)@")
# Lo que en esa forma no es una contrasena sino un puerto y una ruta
# (`https://ejemplo.test:8443/ruta/@ambito`): cifras y `/`, detras de algo
# que parece un host (lleva un punto, o es `localhost`). Detras de un
# usuario, `u:2024/Secreta9x@host` es una contrasena que empieza por cifras.
PUERTO_Y_RUTA = re.compile(r"\d{1,5}/.*")
PARECE_UN_HOST = re.compile(r"(?i)localhost|[^.]+(?:\.[^.]+)+")

# Los valores de ejemplo que se permiten, en una URL o en una asignacion. Las
# palabras salen del inventario del arbol (28-sep): `prueba` es la del
# PostgreSQL desechable de las pruebas; `clave` y `token`, las de los
# ejemplos de las guias; `cambiar-esto`, el valor de ejemplo del spec.
CONTRASENAS_DE_EJEMPLO = ("prueba", "cambiar-esto", "clave", "token",
                          "...", "%s")
# Una variable es `$NOMBRE` o `${NOMBRE...}` ENTERO, con el nombre en
# mayusculas (`$uper...9` es una contrasena); un marcador `<...>` no lleva
# `:`, `/` ni `@` dentro.
CONTRASENA_MARCADOR = re.compile(
    r"<[^<>:/@]+>|\$[A-Z_][A-Z0-9_]*|\$\{[A-Z_][A-Z0-9_]*[^{}]*\}")

# Una clave que nombra un secreto, y su valor.
#
# La clave lleva `password`, `passwd`, `secret`, `token` o `api_key` (sin
# distinguir mayusculas), o ACABA en `_KEY` escrito en mayusculas (la
# convencion de las variables de entorno: `KAGGLE_KEY`, `AWS_ACCESS_KEY`)
# o, en minusculas, en uno de unos pocos nombres (`access_key`,
# `private_key`, `encryption_key`, `signing_key`, `client_key`,
# `master_key`). `cache_key`, `primary_key` o `model_key` no nombran un
# secreto.
#
# El valor va detras de `=` o `:`; con subindice
# (`os.environ["X_PASSWORD"] = ...`, grupo `subindice`); o, si la clave va
# entre comillas, detras de una coma (`setenv("X_PASSWORD", ...)`, grupo
# `coma`). Va entre comillas (`doble`, `simple`), es `${...}` entero
# (`llaves`) o va suelto hasta el primer blanco, comilla, coma o `;`
# (`suelto`). Con subindice o detras de una coma, solo cuenta entre
# comillas: suelto es una variable (ver `_secretos_de_la_linea`).
ASIGNACION = re.compile(
    r"(?i)(?<![A-Za-z0-9_])(?P<comilla>[\"'])?"
    r"[A-Za-z0-9_.-]*(?:(?:password|passwd|secret|token|api[_-]?key)"
    r"[A-Za-z0-9_.-]*"
    r"|(?:(?:access|private|encryption|signing|client|master)_key"
    r"|(?-i:_KEY))(?![A-Za-z0-9_.-]))"
    r"(?:[\"']?\s*(?P<subindice>\])?\s*[:=]"
    r"|(?(comilla)(?P=comilla)\s*(?P<coma>,)|(?!)))\s*"
    r"(?:\"(?P<doble>[^\"]*)\"|'(?P<simple>[^']*)'"
    r"|(?P<llaves>\$\{[^{}]*\})|(?P<suelto>[^\s\"',;]+))")
VALOR_DE_LA_ASIGNACION = ("doble", "simple", "llaves", "suelto")
# La linea que no lleva ninguna de estas palabras no puede llevar una
# asignacion de secreto, y no se le aplica ASIGNACION: en una tirada larga de
# letras, cifras, puntos y guiones su coste es cuadratico (A7).
PALABRA_DE_LA_ASIGNACION = re.compile(r"(?i)password|passwd|secret|token|key")
# Lo que parece un secreto en una asignacion: 8 o mas caracteres, con letras
# Y cifras. Deja pasar los nombres de variable, las palabras de ejemplo
# (`cambiar-esto`, `verifica`) y los ids de ejemplo; y tambien, sin remedio,
# una contrasena hecha solo de letras.
LITERAL_QUE_PARECE_SECRETO = re.compile(
    r"(?=.*[A-Za-z])(?=.*[0-9]).{8,}")
# Una expresion no es un literal: una llamada, un subindice, una expresion
# de n8n (`={{ ... }}`). Suelta, la delata cualquier parentesis, corchete o
# llave; entre comillas, solo `{{`, `${`, `$(` o un `=` delante (la de
# n8n): `"S3cr{eta}9x"` es un literal.
EXPRESION = re.compile(r"[()\[\]{}]")
EXPRESION_ENTRE_COMILLAS = re.compile(r"\{\{|\$\{|\$\(|^=")
# `${NOMBRE:-valor}` (o `-`, `:=`, `=`): lo de detras es un literal.
CON_VALOR_POR_DEFECTO = re.compile(
    r"\$\{[A-Za-z_][A-Za-z0-9_]*:?[-=](?P<valor>[^{}]*)\}")

FICHEROS_PROHIBIDOS = (".env*", "*.env", "kaggle.json", "credentials.json",
                       "client_secret*.json", ".pgpass", ".netrc",
                       ".git-credentials",
                       "*.pem", "*.key", "*.p12", "*.pfx", "*.ppk",
                       "id_rsa*", "id_dsa*", "id_ecdsa*", "id_ed25519*")
FICHEROS_PERMITIDOS = (".env.ejemplo",)


def _es_de_ejemplo(contrasena):
    por_defecto = CON_VALOR_POR_DEFECTO.fullmatch(contrasena)
    if por_defecto is not None:
        return _es_de_ejemplo(por_defecto.group("valor"))
    return (contrasena.lower() in CONTRASENAS_DE_EJEMPLO
            or CONTRASENA_MARCADOR.fullmatch(contrasena) is not None)


def _es_un_literal_secreto(valor, entre_comillas=False):
    """El valor de una asignacion es un secreto si es un LITERAL (no una
    variable ni una expresion) que no es de ejemplo y lo parece."""
    por_defecto = CON_VALOR_POR_DEFECTO.fullmatch(valor)
    if por_defecto is not None:
        valor = por_defecto.group("valor")
    expresion = EXPRESION_ENTRE_COMILLAS if entre_comillas else EXPRESION
    return (LITERAL_QUE_PARECE_SECRETO.fullmatch(valor) is not None
            and expresion.search(valor) is None
            and not _es_de_ejemplo(valor))


def _secretos_de_la_linea(linea):
    """(clase, inicio, fin) de cada secreto de la linea; el tramo es el del
    secreto (en una URL o en una asignacion, el del valor)."""
    for clase, patron in PATRONES_DE_SECRETO.items():
        for m in patron.finditer(linea):
            yield clase, m.start(), m.end()
    if "://" in linea:                  # si no, no hay URL: no se busca (A7)
        for m in URL_CON_CONTRASENA.finditer(linea):
            contrasena = m.group("contrasena")
            puerto = (PUERTO_Y_RUTA.fullmatch(contrasena)
                      and PARECE_UN_HOST.fullmatch(m.group("usuario")))
            if not (_es_de_ejemplo(contrasena) or puerto):
                yield ("contrasena_en_url", m.start("contrasena"),
                       m.end("contrasena"))
    if PALABRA_DE_LA_ASIGNACION.search(linea) is None:
        return
    for m in ASIGNACION.finditer(linea):
        grupo = next(g for g in VALOR_DE_LA_ASIGNACION
                     if m.group(g) is not None)
        entre_comillas = grupo in ("doble", "simple")
        if (m.group("subindice") or m.group("coma")) and not entre_comillas:
            continue                    # `os.environ["X"] = variable`
        if _es_un_literal_secreto(m.group(grupo), entre_comillas):
            yield "asignacion_de_secreto", m.start(grupo), m.end(grupo)


def _clases_de_secreto(linea):
    """Las clases de secreto de una linea, sin repetir. Tambien con `\\"`
    convertido en `"`: el texto de un JSON escapado (una celda de un
    notebook, el codigo de un nodo de n8n)."""
    variantes = [linea]
    if '\\"' in linea:
        variantes.append(linea.replace('\\"', '"'))
    clases = []
    for texto in variantes:
        for clase, _inicio, _fin in _secretos_de_la_linea(texto):
            if clase not in clases:
                clases.append(clase)
    return clases


def _tapar_secretos(texto):
    """El texto con cada secreto cambiado por `<secreto>`."""
    tramos = sorted((inicio, fin) for _clase, inicio, fin
                    in _secretos_de_la_linea(texto))
    salida, hasta = [], 0
    for inicio, fin in tramos:
        if inicio >= hasta:
            salida.append(texto[hasta:inicio])
            salida.append("<secreto>")
            hasta = fin
        elif fin > hasta:                       # tramos que se solapan
            hasta = fin
    salida.append(texto[hasta:])
    return "".join(salida)


def _prohibido(nombre):
    """Si el nombre es el de un fichero que no debe viajar. No distingue
    mayusculas."""
    nombre = nombre.lower()
    return (nombre not in FICHEROS_PERMITIDOS
            and any(fnmatch.fnmatchcase(nombre, p)
                    for p in FICHEROS_PROHIBIDOS))


def _secretos_en(piezas, huellas):
    hallazgos = []
    for pieza in piezas:
        fichero = _publicable(pieza.nombre, huellas)
        prohibido = (pieza.recorrida
                     and _prohibido(pieza.nombre.rsplit("/", 1)[-1]))
        # La linea 0 es el fichero entero: lo que no se ha mirado (enlace
        # simbolico, submodulo, ilegible) no puede darse por limpio; y el
        # nombre, que tambien viaja, puede ser el de un fichero prohibido o
        # llevar un secreto.
        clases = [] if pieza.recorrida else ["no_recorrido"]
        if pieza.primera:
            clases += ["fichero_prohibido"] if prohibido else []
            for parte in pieza.nombre.split("/"):
                clases += [c for c in _clases_de_secreto(parte)
                           if c not in clases]
        hallazgos += [{"fichero": fichero, "linea": 0, "clase": clase,
                       "origen": pieza.origen} for clase in clases]
        if not pieza.recorrida or prohibido or pieza.texto is None:
            continue
        for n, linea in enumerate(pieza.texto.splitlines(), 1):
            for clase in _clases_de_secreto(linea):
                hallazgos.append({"fichero": fichero, "linea": n,
                                  "clase": clase, "origen": pieza.origen})
    return hallazgos


def buscar_secretos(raiz, huellas=None, commit=None):
    """Secretos por patron y ficheros prohibidos: fichero, linea, clase y
    origen.

    La linea 0 es el fichero entero. El secreto no sale nunca. El nombre del
    fichero es el publicable (ver `_publicable`) con `huellas`; sin ellas,
    con las del repositorio donde vive el script. Con `commit`, tambien el
    arbol de ese commit.
    """
    if huellas is None:
        huellas = huellas_de_la_lista(leer_huellas(HUELLAS_POR_DEFECTO))
    return _secretos_en(_piezas(raiz, commit, huellas), huellas)


# --------------------------------------------------------------------------
# El commit
# --------------------------------------------------------------------------
CAMPOS_DEL_COMMIT = ("autor", "correo_de_autor", "quien_confirma",
                     "correo_de_quien_confirma", "mensaje")


def verificar_commit(raiz, revision="HEAD", huellas=None,
                     un_solo_commit=False):
    """Autor, quien confirma, sus correos y el mensaje, contra las huellas y
    contra los patrones de secretos; con `un_solo_commit` (el commit que se
    publica), tambien una huella de la lista escrita en ellos
    (`huella_publicada`, ver `_huellas_publicadas_en`).

    Devuelve `campo`, `linea` (la del mensaje; 0 en los demas) y `huella`
    o `clase` (la del secreto). Sin `huellas`, las del repositorio donde
    vive el script.
    """
    if huellas is None:
        huellas = huellas_de_la_lista(leer_huellas(HUELLAS_POR_DEFECTO))
    huellas = set(huellas)
    salida = _git(raiz, "log", "-1",
                  "--format=%an%x00%ae%x00%cn%x00%ce%x00%B", revision, "--")
    if salida is None:
        raise SystemExit("No se pudo leer el commit "
                         f"{_publicable(revision, huellas)} del árbol que se "
                         "comprueba: ¿es un repositorio de git con commits?")
    valores = salida.decode("utf-8", errors="replace").split("\0", 4)
    hallazgos = []
    for campo, valor in zip(CAMPOS_DEL_COMMIT, valores):
        lineas = valor.splitlines() if campo == "mensaje" else [valor]
        for n, linea in enumerate(lineas, 1):
            donde = n if campo == "mensaje" else 0
            for una in sorted({huella(t) for t in tokens(linea)} & huellas):
                hallazgos.append({"campo": campo, "linea": donde,
                                  "huella": una})
            for clase in _clases_de_secreto(linea):
                hallazgos.append({"campo": campo, "linea": donde,
                                  "clase": clase})
            if un_solo_commit:
                hallazgos += [{"campo": campo, "linea": donde,
                               "clase": "huella_publicada"}
                              for _m in _huellas_escritas(linea, huellas)]
    return hallazgos


# Las cabeceras que lleva un commit sin firma: su arbol, su autor y quien lo
# confirma (y `parent`, si no es el unico).
CABECERAS_DEL_COMMIT = ("tree", "author", "committer")


def cabeceras_del_commit(raiz, revision="HEAD", huellas=None,
                         un_solo_commit=False):
    """Las cabeceras del commit en crudo (`git cat-file commit`) que no son
    las de CABECERAS_DEL_COMMIT: `campo` (el NOMBRE de la cabecera, nunca su
    valor), `linea` 0 y clase `cabecera_del_commit`.

    Una firma (`gpgsig`) lleva el identificador de la clave de quien firma.
    `parent` solo es hallazgo con `un_solo_commit`: un commit con padre no es
    el unico. Sin `huellas`, las del repositorio donde vive el script (solo
    tapan la revision y los nombres).
    """
    if huellas is None:
        huellas = huellas_de_la_lista(leer_huellas(HUELLAS_POR_DEFECTO))
    huellas = set(huellas)
    crudo = _git(raiz, "cat-file", "commit", revision)
    if crudo is None:
        raise SystemExit("No se pudo leer el commit "
                         f"{_publicable(revision, huellas)} del árbol que se "
                         "comprueba: ¿es un repositorio de git con commits?")
    permitidas = CABECERAS_DEL_COMMIT + (() if un_solo_commit else ("parent",))
    hallazgos = []
    for linea in crudo.split(b"\n\n", 1)[0].split(b"\n"):
        if not linea or linea.startswith(b" "):     # la continuacion de otra
            continue
        nombre = linea.split(b" ", 1)[0].decode("utf-8", errors="replace")
        if nombre not in permitidas:
            hallazgos.append({"campo": _publicable(nombre, huellas),
                              "linea": 0, "clase": "cabecera_del_commit"})
    return hallazgos


def _nombres_de_referencias(raiz):
    """[(referencia, nombre)]: las ramas (con la de HEAD, aunque aun no
    tenga commits) y las etiquetas. Sus nombres se publican con el push."""
    nombres = [("rama", r[len("refs/heads/"):])
               for r in _referencias(raiz, "refs/heads/")]
    cabeza = _git(raiz, "symbolic-ref", "-q", "HEAD")
    if cabeza is not None:
        rama = cabeza.decode("utf-8", errors="replace").strip()
        if rama.startswith("refs/heads/"):
            rama = ("rama", rama[len("refs/heads/"):])
            if rama not in nombres:
                nombres.append(rama)
    nombres += [("etiqueta", r[len("refs/tags/"):])
                for r in _referencias(raiz, "refs/tags/")]
    return nombres


def verificar_referencias(raiz, huellas, un_solo_commit=False):
    """Los nombres de las ramas y de las etiquetas, contra las huellas y
    contra los patrones de secretos (cada componente, como el nombre de un
    fichero); con `un_solo_commit`, tambien una huella de la lista escrita
    en el nombre (`huella_publicada`).

    Devuelve `referencia` (`rama` o `etiqueta`), `nombre` (el publicable,
    con el token, el secreto y la huella tapados) y `huella` o `clase`.
    """
    huellas = set(huellas)
    hallazgos = []
    for referencia, nombre in _nombres_de_referencias(raiz):
        publicable = _publicable(nombre, huellas)
        for una in sorted({huella(t) for t in tokens(nombre)} & huellas):
            hallazgos.append({"referencia": referencia,
                              "nombre": publicable, "huella": una})
        clases = []
        for parte in nombre.split("/"):
            clases += [c for c in _clases_de_secreto(parte)
                       if c not in clases]
        hallazgos += [{"referencia": referencia, "nombre": publicable,
                       "clase": clase} for clase in clases]
        if un_solo_commit:
            hallazgos += [{"referencia": referencia, "nombre": publicable,
                           "clase": "huella_publicada"}
                          for _m in _huellas_escritas(nombre, huellas)]
    return hallazgos


def commits(raiz):
    """Cuantos commits tiene el repositorio entero: los que alcanza
    cualquier referencia (ramas, etiquetas, stash...), no solo HEAD."""
    salida = _git(raiz, "rev-list", "--count", "--all")
    if salida is None:
        raise SystemExit("No se pudieron contar los commits del árbol que "
                         "se comprueba: ¿es un repositorio de git?")
    return int(salida.decode("ascii").strip())


def _referencias(raiz, prefijo):
    salida = _git(raiz, "for-each-ref", "--format=%(refname)", prefijo)
    if salida is None:
        raise SystemExit("No se pudieron leer las referencias del árbol que "
                         "se comprueba: ¿es un repositorio de git?")
    return [r for r in salida.decode("utf-8", errors="replace").splitlines()
            if r]


def ramas(raiz):
    """Cuantas ramas locales hay."""
    return len(_referencias(raiz, "refs/heads/"))


def etiquetas(raiz):
    """Cuantas etiquetas hay (quien las crea y sus mensajes no se miran:
    en el repositorio que se publica no puede haber ninguna)."""
    return len(_referencias(raiz, "refs/tags/"))


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
    # Como texto: en las salidas, la ruta de las huellas sale como se paso.
    analizador.add_argument("--huellas", default=None,
                            help="fichero de huellas (por defecto, "
                                 f"{HUELLAS_MOSTRADAS})")
    analizador.add_argument("--commit", nargs="?", const="HEAD", default=None,
                            metavar="REV",
                            help="comprueba también el árbol, el autor, "
                                 "quien confirma, el mensaje y las cabeceras "
                                 "de ese commit (HEAD), y los nombres de "
                                 "ramas y etiquetas")
    analizador.add_argument("--un-solo-commit", action="store_true",
                            help="exige que el repositorio entero tenga un "
                                 "solo commit, una sola rama y ninguna "
                                 "etiqueta, y que el árbol no lleve ninguna "
                                 "huella de la lista; implica --commit HEAD")
    analizador.add_argument("--regenerar", action="store_true",
                            help="escribe el fichero de huellas desde la "
                                 f"lista en claro ({VARIABLE_DE_LA_LISTA} o "
                                 "--lista)")
    analizador.add_argument("--lista", type=Path, default=None,
                            help="la lista en claro, fuera del repositorio")
    analizador.add_argument("--solo-centinela", action="store_true",
                            help="con --regenerar, escribe en --huellas el "
                                 "huellas.txt del repositorio que se publica: "
                                 "la cabecera y la huella del centinela, sin "
                                 "lista")
    return analizador.parse_args(argv)


def _las_huellas(args):
    """La ruta del fichero de huellas y como se dice en las salidas: como se
    paso, o relativa al repositorio si es la de por defecto."""
    if args.huellas is None:
        return HUELLAS_POR_DEFECTO, HUELLAS_MOSTRADAS
    return Path(args.huellas), args.huellas


def _solo_centinela(args):
    """El `huellas.txt` del repositorio que se publica (D9). No lee ni
    --lista ni ANONIMATO_LISTA. Exige --huellas: la de por defecto es la de
    este repositorio, que en el de desarrollo lleva la lista entera."""
    if args.lista is not None:
        raise SystemExit("--solo-centinela no lleva lista: escribe solo la "
                         "huella del centinela. Quita --lista.")
    if args.huellas is None:
        raise SystemExit(
            "Con --solo-centinela, di dónde se escribe con --huellas (el "
            "huellas.txt del árbol que se publica): el de este repositorio, "
            "en el de desarrollo, lleva la lista entera.")
    destino, mostrado = _las_huellas(args)
    try:
        regenerar_solo_centinela(destino)
    except OSError:
        raise SystemExit(f"No se pudieron escribir las huellas en {mostrado}.")
    print(f"1 huella escrita en {mostrado} (solo la del centinela).")
    return 0


def _regenerar(args):
    if args.solo_centinela:
        return _solo_centinela(args)
    lista = args.lista or os.environ.get(VARIABLE_DE_LA_LISTA)
    if not lista:
        raise SystemExit(
            f"Falta la lista en claro: define {VARIABLE_DE_LA_LISTA} o pasa "
            "--lista. Vive fuera del repositorio.")
    destino, mostrado = _las_huellas(args)
    # La ruta de la lista no se imprime nunca: vive fuera del repositorio y
    # lleva el usuario de la maquina.
    try:
        n = regenerar(leer_lista(lista), destino)
    except FileNotFoundError:
        raise SystemExit("No existe la lista en claro que se ha pasado.")
    except OSError:
        raise SystemExit("No se pudo leer la lista en claro que se ha "
                         "pasado, o escribir las huellas.")
    except ValueError as error:
        raise SystemExit(f"No se escribe nada: {error}.")
    print(f"{n} huellas escritas en {mostrado} (con la del centinela).")
    return 0


def _huellas_de_la_cli(ruta, mostrado):
    """Las huellas que se buscan (sin la del centinela), o SystemExit.

    Con solo la del centinela no se comprueba nada: es el `huellas.txt` del
    repositorio que se publica (D9), y la comprobacion de verdad se hace con
    las del repositorio de desarrollo.
    """
    try:
        huellas = huellas_de_la_lista(leer_huellas(ruta))
    except FileNotFoundError:
        raise SystemExit(f"No existe el fichero de huellas {mostrado}.")
    except OSError:
        raise SystemExit(f"No se pudo leer el fichero de huellas {mostrado}.")
    except ValueError as error:
        raise SystemExit(f"El fichero de huellas {mostrado} no vale: "
                         f"{error}.")
    if not huellas:
        raise SystemExit(
            f"{mostrado} lleva solo la huella del centinela: así no se "
            "comprueba nada. Pasa --huellas con las huellas del repositorio "
            "de desarrollo (el que tiene la lista entera).")
    return huellas


def main(argv=None):
    args = _argumentos(argv)
    if args.regenerar:
        return _regenerar(args)
    if args.solo_centinela:
        raise SystemExit("--solo-centinela va con --regenerar: escribe el "
                         "huellas.txt del repositorio que se publica.")

    huellas = _huellas_de_la_cli(*_las_huellas(args))
    if args.un_solo_commit and args.commit is None:
        args.commit = "HEAD"            # lo que se publica es ese commit
    revision = (None if args.commit is None
                else _publicable(args.commit, huellas))
    piezas = _piezas(args.raiz, args.commit, huellas)
    de_huella = _huellas_en(piezas, huellas)
    de_secreto = _secretos_en(piezas, huellas)
    # En el arbol que se publica, ninguna huella de la lista (D9).
    publicadas = (_huellas_publicadas_en(piezas, huellas)
                  if args.un_solo_commit else [])

    def de_donde(h):
        return "" if h["origen"] == COPIA else f" ({h['origen']})"

    def que(h):
        return (f"huella {h['huella'][:12]}" if "huella" in h
                else h["clase"])

    for h in de_huella + de_secreto + publicadas:
        print(f"{h['fichero']}:{h['linea']}: {que(h)}" + de_donde(h))

    del_commit, de_referencia = [], []
    if args.commit is not None:
        del_commit = (verificar_commit(args.raiz, args.commit, huellas=huellas,
                                       un_solo_commit=args.un_solo_commit)
                      + cabeceras_del_commit(
                          args.raiz, args.commit, huellas,
                          un_solo_commit=args.un_solo_commit))
        for h in del_commit:
            donde = (f"{h['campo']}:{h['linea']}" if h["linea"]
                     else h["campo"])
            print(f"commit {revision}: {donde}: {que(h)}")
        # El nombre de las ramas y de las etiquetas se publica con el push.
        de_referencia = verificar_referencias(
            args.raiz, huellas, un_solo_commit=args.un_solo_commit)
        for h in de_referencia:
            print(f"{h['referencia']} {h['nombre']}: {que(h)}")

    recorridas = [p for p in piezas if p.texto is not None]
    sin_recorrer = [p for p in piezas if p.recorrida and p.texto is None]
    print("--")
    por_origen = {}
    for p in recorridas:
        por_origen[p.origen] = por_origen.get(p.origen, 0) + 1
    detalle = ", ".join(f"{o}: {por_origen[o]}"
                        for o in (COPIA, INDICE, COMMIT) if o in por_origen)
    print(f"ficheros recorridos: {len(recorridas)}"
          + (f" ({detalle})" if len(por_origen) > 1 else ""))
    print(f"binarios sin recorrer: {len(sin_recorrer)}")
    for p in sin_recorrer:
        print(f"  {_publicable(p.nombre, huellas)}"
              + ("" if p.origen == COPIA else f" ({p.origen})"))
    ficheros = len({h["fichero"] for h in de_huella})
    print(f"huellas: {len(de_huella)} en {ficheros} ficheros")
    por_clase = {}
    for h in de_secreto:
        por_clase[h["clase"]] = por_clase.get(h["clase"], 0) + 1
    detalle = ", ".join(f"{c}: {n}" for c, n in sorted(por_clase.items()))
    print(f"secretos: {len(de_secreto)}" + (f" ({detalle})" if detalle else ""))
    if args.un_solo_commit:
        print(f"huellas publicadas: {len(publicadas)}")
    mal = (len(de_huella) + len(de_secreto) + len(publicadas)
           + len(del_commit) + len(de_referencia))
    if args.commit is not None:
        print(f"commit {revision}: {len(del_commit)}")
        print(f"nombres de ramas y etiquetas: {len(de_referencia)}")
    if args.un_solo_commit:
        # Un commit, una rama y ninguna etiqueta: lo que sobre, es hallazgo.
        cuantos, cuantas, sueltas = (commits(args.raiz), ramas(args.raiz),
                                     etiquetas(args.raiz))
        print(f"commits: {cuantos}")
        print(f"ramas: {cuantas}")
        print(f"etiquetas: {sueltas}")
        mal += (cuantos != 1) + (cuantas != 1) + (sueltas != 0)
    if not recorridas:
        print("NO publicar: no se recorrió ningún fichero de texto, y lo que "
              "no se ha mirado no está limpio")
        return 1
    if mal:
        print("NO publicar: hay hallazgos")
        return 1
    if sin_recorrer:
        # Lo que no se ha recorrido no se da por limpio: se revisa a mano.
        n = len(sin_recorrer)
        print(f"limpio lo recorrido; {n} "
              + ("binario sin recorrer, que se revisa" if n == 1
                 else "binarios sin recorrer, que se revisan")
              + " a mano")
    else:
        print("limpio")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    raise SystemExit(main())
```

- [ ] **Paso 4: Correr las pruebas: siguen sin poder cargarse, ahora por el fichero de huellas**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_anonimato.py
```

Salida esperada (el mismo error con otra causa: el fichero que falta es
`tests/anonimato/huellas.txt`, que `solo_el_centinela()` lee al cargarse el
módulo):

```
ERROR tests/test_anonimato.py - FileNotFoundError: [Errno 2] No such file or ...
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.38s
```

- [ ] **Paso 5: `huellas.txt` y `.gitignore`**

Generar las huellas, con la lista en claro:

```bash
ANONIMATO_LISTA=<lista en claro> C:/venv-copiloto/Scripts/python.exe -B scripts/verificar_anonimato.py --regenerar
```

Salida esperada:

```
30 huellas escritas en tests/anonimato/huellas.txt (con la del centinela).
```

El número es el de la lista de hoy más la del centinela (al escribirse esta
tarea eran 29; la tarea 6 encontró un identificador que la lista no conocía
y son 30). **El contenido del fichero no se cita aquí**: este plan se publica
con el repositorio, y una huella no es un secreto (D9). Si una entrada de la
lista no da exactamente un token, el script no escribe nada y dice el número
de la entrada, nunca su contenido.

Correr las pruebas:

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_anonimato.py
```

Salida esperada (queda una en rojo, la del `.gitignore`):

```
FAILED tests/test_anonimato.py::test_la_lista_en_claro_esta_ignorada_por_si_alguien_la_copia_dentro
1 failed, 204 passed, 2 skipped in 110.19s (0:01:50)
```

Añadir AL FINAL de `.gitignore`, después de la línea `pruebas/sesion/` y
dejando una línea en blanco:

```

# La lista en claro del anonimato (spec de SP5 §6.1) vive FUERA del
# repositorio. Por si alguien la copia aqui: tampoco se versiona.
tests/anonimato/lista*.txt
```

- [ ] **Paso 6: Correr las pruebas: verde**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_anonimato.py
```

Salida esperada:

```
205 passed, 2 skipped in 73.49s (0:01:13)
```

Las dos que se saltan son las de los enlaces simbólicos, que Windows no deja
crear sin privilegios; donde se puedan crear, pasan.

Ningún fichero que existiera cambia de comportamiento con esta tarea (solo
gana tres líneas el `.gitignore`), así que la suite entera tiene que dar lo
mismo que antes más estas 207 pruebas.

Y el script, sobre el repositorio:

```bash
C:/venv-copiloto/Scripts/python.exe scripts/verificar_anonimato.py --raiz .
```

Esperado, antes de la tarea 6: salida 1, con hallazgos de huella solo en
ficheros de documentación (los de la lista de «Ficheros» de la tarea 6) y
`secretos: 0`. Si aparece un fichero de código o de pruebas, alguna de las
tareas 1 a 4 quedó a medias.

- [ ] **Paso 7: Commit**

```bash
git add scripts/verificar_anonimato.py tests/test_anonimato.py tests/anonimato/huellas.txt .gitignore
git commit -m "test(anonimato): huellas de la lista negra, centinela y patrones de secretos (SP5-B2 T5)" -m "scripts/verificar_anonimato.py tokeniza lo que se publicaria (la copia de trabajo, el indice y, con --commit, el arbol del commit) y lo compara, huella con huella, con tests/anonimato/huellas.txt; busca secretos por patron y ficheros prohibidos, y comprueba autor, quien confirma, mensaje y nombres de ramas y etiquetas. Ninguna salida lleva el token ni el secreto. La lista en claro vive fuera del repositorio. Faltan las pruebas del arbol, que exigen la anonimizacion hecha." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
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
- Modificar: `tests/mantenimiento.mjs` (un comentario)
- Modificar: `tests/anonimato/huellas.txt` (solo si el repaso a mano del
  paso 6 encuentra un identificador que la lista no conocía)
- Modificar: cualquier otro fichero versionado donde el comprobador encuentre
  algo (no debería quedar ninguno fuera de esta lista: si aparece, es un
  hallazgo que se anota en el informe de la tarea)
- Modificar: `tests/test_anonimato.py` (gana las dos pruebas del árbol:
  `test_el_arbol_no_lleva_secretos` y `test_el_arbol_no_lleva_huellas`)

**Interfaces:**
- Consume: `scripts/verificar_anonimato.py` (tarea 5): `buscar_huellas(raiz, huellas)`,
  `buscar_secretos(raiz, huellas)`, `ficheros_versionados(raiz)`, `leer_huellas(ruta)`, y
  su CLI; de `tests/test_anonimato.py`, `solo_el_centinela()` y `SIN_LA_LISTA`; la lista en claro
  (`ANONIMATO_LISTA`), secciones `[huellas]` y `[sustituciones]`.
- Produce: el árbol sin ninguna huella; las dos pruebas del árbol en la suite.

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
| la lista de contenedores del servidor con sus nombres (salida de `docker ps` copiada en la guía de despliegue) | se conservan las filas del proyecto (`copiloto-mcp`, `copiloto-bd`) y las dos genéricas (`n8n` y `nginx`, con la imagen como `n8nio/n8n:...` y `nginx:...`), que ayudan a reconocer el contenedor de n8n; las demás se sustituyen por una sola fila «(los contenedores ajenos: no se tocan)»; los nombres sueltos en prosa pasan a «los contenedores ajenos» |
| productos de la pila de mensajería del cliente, en prosa o en un comentario | «los contenedores ajenos», sin enumerarlos |
| la credencial de Telegram del cliente y la de pruebas anterior, con su nombre | «la credencial de Telegram del cliente», «una credencial de pruebas anterior» |
| la tabla «Credenciales y workflows» del manual de operación, que nombra las tres credenciales de Telegram del proyecto | la columna de la credencial pasa a los nombres neutros de la tarea 4: `bot-paciente`, `bot-profesional` y `bot-avisos` |
| el nombre de usuario de un bot del proyecto, en prosa | «el bot del paciente», «el bot del profesional», «el bot de pruebas y avisos» |
| el indicador del intérprete de órdenes del servidor | `usuario@vps` en las órdenes; en prosa, «el prompt del servidor», sin decir cuál es |
| el `id` de un workflow de la instancia de n8n (16 caracteres alfanuméricos) | `<id-del-workflow-profesional>` |
| el número de una ejecución de la instancia, en un comentario | se quita |
| la universidad, fuera del `README.md` | `<institución y programa>` (restricción 1) |
| una ruta de la máquina en una orden | `<raiz-del-repositorio>` o `<RSNA_RAIZ>`, entre comillas si va detrás de un `cd` (la real puede llevar espacios), y definidos al principio del documento que los usa |
| un título de sección que nombra a un integrante («… de …») | «(la máquina de desarrollo)»; busca si algún enlace interno apunta al ancla del título viejo y corrígelo |
| los nombres del equipo y la filiación | «el equipo» |
| la cuenta propietaria del remoto en una URL de clonado | `<cuenta>`; y donde la guía diga que el repositorio es privado, «el repositorio» a secas o, si la frase depende de ello, en condicional («si el repositorio es privado») |
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

Esperado: código de salida 0 y ningún hallazgo de ninguna clase. La última
línea dice cuántos binarios quedan sin recorrer: son los de la tarea 7.
**El verificador mira también el índice**: si da hallazgos en un fichero
que ya arreglaste, prepáralo (`git add`) y vuelve a correrlo.

**Y un repaso a mano, que las huellas no pueden hacer.** Las huellas solo
ven lo que la lista conoce. Antes de dar el árbol por limpio, recorre los
ficheros versionados buscando lo que identifica y la lista puede no
conocer: correos, dominios, direcciones IP, rutas con un usuario, nombres
propios, nombres de bots, `chat_id`, y los identificadores de la instancia
de n8n (el `id` de un workflow o de una credencial, el número de una
ejecución). Lo que aparezca se sustituye por un marcador, se añade a la
lista en claro —la pone al día quien la mantiene, fuera del repositorio— y
se regeneran las huellas (paso 5 de la tarea 5). Así entraron el `id` de un
workflow, que estaba en el plan de SP4, y el número de una ejecución, en un
comentario de `tests/mantenimiento.mjs`: los encontró la revisión de esta
tarea, no las huellas.

- [ ] **Paso 7: Las pruebas que lo vigilan**

Son dos, y no una, porque no necesitan lo mismo: la que busca secretos no
necesita la lista y corre siempre; la que busca huellas se salta, diciéndolo,
donde `huellas.txt` lleva solo la del centinela (el repositorio que se
publica, D9).

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


NO_ES_UN_REPOSITORIO = "no es la raiz de un repositorio de git"


def _fuera_de_git(raiz):
    """La linea que añade el fallo de una prueba del arbol fuera de la raiz
    de un repositorio (C4): alli se recorre la carpeta entera, tambien lo que
    git ignoraria, y lo que salga puede no publicarse."""
    if va._es_la_raiz_de_un_repositorio(raiz):
        return []
    return [f"Ojo: esta carpeta {NO_ES_UN_REPOSITORIO} (una copia descargada "
            "en ZIP, o git fuera del PATH), asi que se ha recorrido entera, "
            "tambien lo que git ignoraria (un .env de esta copia, por "
            "ejemplo): lo que sale aqui puede no publicarse."]


def _el_arbol_no_lleva_secretos(raiz, ruta_de_huellas, minimo=100):
    """La busqueda de secretos en el arbol. No necesita la lista, asi que
    corre siempre, tambien con solo la huella del centinela (V-3): las
    huellas solo tapan los nombres del mensaje. Un recorrido vacio (menos
    de `minimo` ficheros) no es un arbol limpio."""
    huellas = va.huellas_de_la_lista(va.leer_huellas(ruta_de_huellas))
    recorridos = len(va.ficheros_versionados(raiz))
    assert recorridos > minimo, "no se ha recorrido el arbol"
    de_secreto = va.buscar_secretos(raiz, huellas)
    if de_secreto:
        pytest.fail("\n".join(
            [f"El arbol no se puede publicar: {len(de_secreto)} secretos. La "
             "linea 0 es el nombre del fichero."]
            + _fuera_de_git(raiz)
            + _por_fichero(de_secreto, "clase")), pytrace=False)


def test_el_arbol_no_lleva_secretos():
    _el_arbol_no_lleva_secretos(RAIZ, HUELLAS)


def test_la_busqueda_de_secretos_del_arbol_no_se_salta():
    # C1: la prueba de V-3 vigila el ayudante; esta, la prueba del arbol. Un
    # `skipif` encima (la forma exacta que tenia el defecto) la saltaria en
    # el repositorio que se publica, y la suite seguiria en verde.
    marcas = {m.name for m in
              getattr(test_el_arbol_no_lleva_secretos, "pytestmark", [])}
    assert not marcas & {"skip", "skipif", "xfail"}, sorted(marcas)


def test_la_busqueda_de_secretos_del_arbol_no_se_salta_por_dentro(
        tmp_path, monkeypatch):
    # A4: la de arriba lee las marcas; esta, el cuerpo. Con solo la huella
    # del centinela, como en el repositorio que se publica, la prueba del
    # arbol corre: un `pytest.skip()` dentro, condicionado a eso, la
    # saltaria en verde.
    publico = tmp_path / "huellas.txt"
    va.regenerar_solo_centinela(publico)
    modulo = sys.modules[__name__]
    monkeypatch.setattr(modulo, "HUELLAS", publico)
    monkeypatch.setattr(modulo, "solo_el_centinela", lambda ruta=publico: True)
    try:
        test_el_arbol_no_lleva_secretos()
    except pytest.skip.Exception:
        pytest.fail("con solo la huella del centinela, "
                    "test_el_arbol_no_lleva_secretos se salta", pytrace=False)


def _el_arbol_no_lleva_huellas(raiz, ruta_de_huellas, minimo=100):
    """La busqueda de huellas en el arbol: fichero, linea y el principio de
    la huella (no el token). Un recorrido vacio no es un arbol limpio."""
    huellas = va.huellas_de_la_lista(va.leer_huellas(ruta_de_huellas))
    recorridos = len(va.ficheros_versionados(raiz))
    assert recorridos > minimo, "no se ha recorrido el arbol"
    de_huella = va.buscar_huellas(raiz, huellas)
    if de_huella:
        ficheros = len({h["fichero"] for h in de_huella})
        pytest.fail("\n".join(
            [f"El arbol no se puede publicar: {len(de_huella)} huellas en "
             f"{ficheros} ficheros. La linea 0 es el nombre del fichero."]
            + _fuera_de_git(raiz)
            + _por_fichero(de_huella, "huella")), pytrace=False)


@pytest.mark.skipif(solo_el_centinela(), reason=SIN_LA_LISTA["arbol"])
def test_el_arbol_no_lleva_huellas():
    """En el repositorio que se publica `huellas.txt` lleva solo la del
    centinela (D9) y esta prueba se salta diciendolo: alli no comprobaria
    nada."""
    _el_arbol_no_lleva_huellas(RAIZ, HUELLAS)


def test_con_solo_el_centinela_los_secretos_del_arbol_se_buscan(tmp_path):
    # V-3: antes, el salto por «solo el centinela» se llevaba tambien la
    # busqueda de secretos del arbol, que no necesita la lista.
    publico = tmp_path / "publico.txt"
    publico.write_text("# cabecera\n" + va.huella(CENTINELA) + "\n",
                       encoding="utf-8")
    assert solo_el_centinela(publico)
    raiz = _arbol_limpio(tmp_path / "arbol")

    def buscar():
        # Un salto aqui es justo el fallo de V-3: que no se salte en verde.
        try:
            _el_arbol_no_lleva_secretos(raiz, publico, minimo=1)
        except pytest.skip.Exception as salto:
            raise AssertionError("con solo la huella del centinela se ha "
                                 "saltado la busqueda de secretos") from salto

    buscar()
    secreto = "PASS" + "WORD=" + _LITERAL
    (raiz / "docs" / "nota.md").write_text(f"uno\n{secreto}\n",
                                           encoding="utf-8")
    with pytest.raises(pytest.fail.Exception) as error:
        buscar()
    assert "docs/nota.md: 1 (lineas 2; clase asignacion_de_secreto)" in str(
        error.value)
    assert _LITERAL not in str(error.value)
```

Sobre el árbol SIN anonimizar esta prueba fallaba (se vio al escribir el
plan, y se repitió sobre `main` con SP5-B1 fusionado, que no añadió
ninguna: 201 huellas en 27 ficheros, ningún secreto). Esta es la FORMA de
su salida —fichero, líneas y el principio de cada huella, nunca el
token—, con los principios cambiados por un marcador: la salida de verdad
no se copia en un documento que se publica (D9).

```
================================== FAILURES ===================================
_______________________ test_el_arbol_no_lleva_huellas ________________________
El arbol no se puede publicar: 201 huellas en 27 ficheros y 0 secretos. La linea 0 es el nombre del fichero.
  docs/comparativa-corridas.md: 8 (lineas 70, 71, 72, 73, 74, 75, 76, 77; huella <12 hex>)
  docs/sp2-despliegue.md: 29 (lineas 107, 108, 144, ...; huella <12 hex>, <12 hex>, ...)
  ...
=========================== short test summary info ===========================
FAILED tests/test_anonimato.py::test_el_arbol_no_lleva_huellas - Failed: El ar...
```

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_anonimato.py -q`

Esperado: `210 passed, 2 skipped` (las dos que se saltan son las de los enlaces
simbólicos, que esta máquina no deja crear). Si falla, la salida dice qué
fichero y qué líneas.
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

Esperado: solo los ficheros de esta tarea. Tres commits, y un cuarto si el
repaso a mano encontró algo (los dos de documentación van ANTES que la
prueba: el verificador mira el índice, y la prueba nacería en rojo):

```bash
git add docs/sp2-despliegue.md docs/sp3-operacion.md
git commit -m "docs(anonimato): las guías de despliegue y operación, sin identificadores" -m "Sustitución mecánica por marcadores y redacción neutra donde la frase nombraba contenedores, bots o cuentas ajenas al proyecto." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"

git add docs/superpowers notebooks/eda_rsna.ipynb
git commit -m "docs(anonimato): specs, planes y la cabecera del notebook, sin identificadores" -m "Solo se cambian los identificadores; la prosa de los specs y de los planes queda como estaba." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"

git add tests/test_anonimato.py
git commit -m "test(anonimato): el árbol versionado no lleva ninguna huella ni ningún secreto" -m "Entra la última: exige aplicadas las tareas 1 a 6." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"

# solo si el repaso a mano encontró un identificador que la lista no conocía
git add tests/anonimato/huellas.txt docs tests/mantenimiento.mjs
git commit -m "docs(anonimato): el id de un workflow de la instancia, fuera; y las guías dicen qué poner en cada marcador" -m "Un plan llevaba el id de un workflow de n8n, que la lista no conocía: pasa a marcador y entra en las huellas." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
---

### Tarea 7: Los binarios, revisados a mano y declarados; y lo que la vigilancia no ve

La prueba de huellas recorre texto. Lo que no es texto —imágenes— solo se
puede revisar mirándolo, y el spec §6.1 pide que se haga una vez y se declare.
Esta tarea escribe la declaración, ata a pruebas lo que la revisión a mano
miró —los binarios versionados, las imágenes incrustadas en los notebooks y
los metadatos de unos y otros: lo que aparezca nuevo hace fallar la suite
hasta que se revise y se declare— y deja dicho, en el mismo documento, **qué
comprueba la vigilancia y qué no puede comprobar**.

Lo que sigue es la tarea tal como quedó después de su revisión y de la tanda
de la revisión final (tarea 9). La primera versión tenía dos pruebas; la
revisión encontró que la de los binarios fallaba fuera de un repositorio de
git, que las imágenes incrustadas en los notebooks se declaraban revisadas
sin que nada las atara, y que la declaración callaba límites del buscador de
secretos.

**Ficheros:**
- Crear: `tests/anonimato/README.md`
- Modificar: `tests/test_anonimato.py` (gana las constantes de lo revisado y
  el apartado «Lo que no es texto»)

**Interfaces:**
- Consume: `verificar_anonimato.binarios(raiz) -> list[Path]` y
  `ficheros_versionados(raiz) -> list[Path]` (tarea 5: en un repositorio, lo
  que tiene seguimiento y lo que no lo tiene ni está ignorado); `va`, `RAIZ`,
  `HUELLAS`, `solo_el_centinela()` y `SIN_LA_LISTA`, de
  `tests/test_anonimato.py`; `PIL.Image` (pillow ya es dependencia del
  paquete).
- Produce, en `tests/test_anonimato.py`: `BINARIOS_REVISADOS`,
  `METADATOS_PERMITIDOS`, `IMAGENES_DE_LOS_NOTEBOOKS`,
  `METADATOS_DEL_NOTEBOOK`, `METADATOS_DE_COLAB`, `METADATOS_DE_LA_CELDA`, y
  las pruebas del apartado «Lo que no es texto».

**Lo que se revisó a mano, para no repetirlo a ciegas:** los seis PNG de
`docs/eda/` y las seis imágenes incrustadas en `notebooks/eda_rsna.ipynb` se
abrieron una a una el 28-sep-2026, y los dieciséis PNG versionados, otra vez,
el 29-sep-2026, en la revisión de esta tarea. Son gráficos de datos agregados
del dataset público y de la simulación; no llevan nombres, rutas, marcas de
agua ni pies. Los metadatos de los PNG de `docs/eda/` son `Software` (la
versión de matplotlib) y `dpi`; los de las figuras de
`docs/validacion-semisintetica/`, que genera `scripts/validar_combinacion.py`,
además `Title` (con su rótulo) y `Description` (la huella SHA-256 del
contenido de `resultados_simulacion.json` con el que se dibujó). Los otros
dos notebooks no tienen salidas.

- [ ] **Paso 1: Escribir las pruebas**

Añade a `tests/test_anonimato.py`, en la cabecera, detrás de la línea
`COPIA, INDICE, COMMIT = …` y dejando una línea en blanco, lo revisado:

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

# Las imagenes incrustadas en cada notebook que se publica, por el SHA-256 de
# sus bytes (ya decodificados de base64), ordenadas. Son huellas de IMAGENES,
# no de tokens: se pueden publicar. Una imagen nueva, o una que cambie al
# volver a ejecutar el notebook, hace fallar la prueba hasta que alguien la
# mira y la declara aqui y en tests/anonimato/README.md.
IMAGENES_DE_LOS_NOTEBOOKS = {
    "notebooks/eda_rsna.ipynb": (
        "0bdabb57e4fffdfba64143c5d73626e246a18ba76cd246b84a3dde65adc64207",
        "0db7916271002c6fcdc19ca61bdea62e30f8c438a4d907318abdc290eee91e7f",
        "2cd353815a6b1463c846d336ed478db1d99b98838059458a961a4951c089fefa",
        "52f958410542951c5a0558b5aee4904dd1ab4757751d1ff8e0e7a6bef090b86d",
        "7d4ab28d7b54c08132afb462516338434e924bf81ceaa115d693f554ea295bab",
        "f1c10db558e768c38e7b4cab01ecc04b9d5a49ef6b125dbc8437ee8d727cd69e",
    ),
    "notebooks/entrenar_gpu.ipynb": (),
    "notebooks/entrenar_kaggle.ipynb": (),
}
# Las claves de `metadata` que puede llevar un notebook que se publica, las de
# su `colab` y las de cada celda. Un notebook guardado de nuevo desde Colab o
# Kaggle trae campos que las huellas no pueden conocer (un identificador de
# documento, una cuenta): la prueba falla hasta que alguien los mira.
METADATOS_DEL_NOTEBOOK = {"kernelspec", "language_info", "accelerator", "colab"}
METADATOS_DE_COLAB = {"name", "provenance"}
METADATOS_DE_LA_CELDA = {"execution"}
```

Las huellas de `IMAGENES_DE_LOS_NOTEBOOKS` son de IMÁGENES (el SHA-256 de sus
bytes), no de tokens de la lista: se pueden publicar.

Y AL FINAL del fichero (detrás de las pruebas del árbol de la tarea 6,
dejando dos líneas en blanco):

```python
# --------------------------------------------------------------------------
# Lo que no es texto: revisado a mano y declarado
# --------------------------------------------------------------------------
FUERA_DE_GIT = ("esta carpeta no es la raiz de un repositorio de git (una "
                "copia descargada en ZIP, o git fuera del PATH): no se sabe "
                "que se publicaria, y queda sin verificar que los binarios "
                "son los revisados a mano (BINARIOS_REVISADOS)")


def test_los_binarios_versionados_son_los_revisados():
    """Lo que no es texto no lo recorre la prueba de huellas: se mira a mano y
    se declara. Si esta prueba falla, hay un binario que nadie ha mirado (o
    uno sin seguimiento y sin ignorar en la carpeta, que se publicaria con un
    `git add -A`).

    Fuera de un repositorio de git se recorre la carpeta entera, con lo que
    git ignoraria (los `.pyc` que escribe el propio pytest): se salta."""
    if not va._es_la_raiz_de_un_repositorio(RAIZ):
        pytest.skip(FUERA_DE_GIT)
    hallados = sorted(p.relative_to(RAIZ).as_posix() for p in va.binarios(RAIZ))
    assert hallados == sorted(BINARIOS_REVISADOS)


def _mirar_imagen(datos, nombre):
    """Mira una imagen (un PNG versionado, o una incrustada en un notebook):
    las claves de sus metadatos tienen que estar en METADATOS_PERMITIDOS.
    Devuelve su formato y el texto de los valores, que se mira despues
    contra las huellas. Si falla, dice la imagen y la clave, nunca el
    valor. Los metadatos, TODOS: sin `load()` PIL no ve los trozos de texto
    que van detras de los datos de la imagen (E3)."""
    from PIL import Image
    with Image.open(io.BytesIO(datos)) as imagen:
        imagen.load()
        formato, info = imagen.format, dict(imagen.info)
    de_mas = sorted(str(c) for c in set(info) - METADATOS_PERMITIDOS)
    if de_mas:
        pytest.fail(f"{nombre}: metadatos que no son los revisados: "
                    f"{', '.join(de_mas)}", pytrace=False)
    return formato, " ".join(str(v) for v in info.values())


def _sin_huellas_en_los_valores(textos):
    """(nombre, texto de los valores de los metadatos): ninguno lleva una
    cadena de la lista. Con solo la huella del centinela no se puede mirar,
    y se dice (V-3)."""
    if solo_el_centinela():
        pytest.skip(SIN_LA_LISTA["metadatos"])
    huellas = va.huellas_de_la_lista(va.leer_huellas(HUELLAS))
    con_huella = [nombre for nombre, texto in textos
                  if {va.huella(t) for t in va.tokens(texto)} & huellas]
    assert not con_huella, "metadatos con una cadena de la lista"


def test_los_png_no_llevan_metadatos_que_identifiquen():
    textos = []
    for nombre in BINARIOS_REVISADOS:
        formato, texto = _mirar_imagen((RAIZ / nombre).read_bytes(), nombre)
        assert formato == "PNG", nombre
        textos.append((nombre, texto))
    _sin_huellas_en_los_valores(textos)


def _png_de_juguete(*textos):
    """Un PNG de 1x1 compuesto a mano, con un trozo `tEXt` por cada
    (clave, valor) DETRAS de los datos de la imagen (`IDAT`). Cada trozo es
    longitud, tipo, datos y CRC."""
    def trozo(tipo, datos):
        return (struct.pack(">I", len(datos)) + tipo + datos
                + struct.pack(">I", zlib.crc32(tipo + datos)))
    png = (b"\x89PNG\r\n\x1a\n"
           + trozo(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
           + trozo(b"IDAT", zlib.compress(b"\x00\x00")))
    for clave, valor in textos:
        png += trozo(b"tEXt", clave + b"\x00" + valor)
    return png + trozo(b"IEND", b"")


def test_un_metadato_detras_de_los_datos_de_la_imagen_tambien_se_mira(
        tmp_path):
    # E3: sin `load()`, PIL no ve los trozos de texto que van detras de los
    # datos de la imagen.
    assert _mirar_imagen(_png_de_juguete(), "limpia.png") == ("PNG", "")
    ruta = tmp_path / "juguete.png"
    ruta.write_bytes(_png_de_juguete((b"Author", b"Autor Neutro")))
    with pytest.raises(pytest.fail.Exception) as error:
        _mirar_imagen(ruta.read_bytes(), "juguete.png")
    assert "juguete.png" in str(error.value) and "Author" in str(error.value)
    assert "Neutro" not in str(error.value)


def _notebooks_publicados(raiz=RAIZ):
    """{nombre: notebook} de cada `.ipynb` que se publicaria, no solo los de
    `notebooks/`."""
    return {p.relative_to(raiz).as_posix():
            json.loads(p.read_text(encoding="utf-8"))
            for p in va.ficheros_versionados(raiz) if p.suffix == ".ipynb"}


def _imagenes_del_notebook(notebook):
    """[(tipo, bytes)] de las imagenes incrustadas: las salidas `image/*` de
    las celdas (`outputs[].data`) y los adjuntos (`attachments`), ya
    decodificadas de base64 (una SVG es texto, no base64)."""
    imagenes = []
    for celda in notebook.get("cells", []):
        paquetes = [s.get("data", {}) for s in celda.get("outputs", [])]
        paquetes += list(celda.get("attachments", {}).values())
        for paquete in paquetes:
            for tipo, valor in sorted(paquete.items()):
                if not tipo.startswith("image/"):
                    continue
                texto = "".join(valor) if isinstance(valor, list) else valor
                imagenes.append((tipo, texto.encode("utf-8")
                                 if tipo == "image/svg+xml"
                                 else base64.b64decode(texto)))
    return imagenes


def test_las_imagenes_salen_de_las_salidas_y_de_los_adjuntos():
    png = _png_de_juguete()
    en_base64 = base64.b64encode(png).decode("ascii")
    notebook = {"cells": [
        {"cell_type": "markdown", "source": ["![a](attachment:a.png)"],
         "attachments": {"a.png": {"image/png": en_base64}}},
        {"cell_type": "code", "outputs": [
            {"output_type": "display_data",
             "data": {"text/plain": ["<Figure>"],
                      "image/png": [en_base64[:10], en_base64[10:]]}},
            {"output_type": "stream", "text": ["hola\n"]}]}]}
    assert _imagenes_del_notebook(notebook) == [("image/png", png)] * 2


def _las_imagenes_de_los_notebooks_son_las_declaradas(raiz, declaradas):
    """Los notebooks que se publicarian bajo `raiz` y las imagenes de cada
    uno (por su SHA-256) son exactamente los de `declaradas` (como
    IMAGENES_DE_LOS_NOTEBOOKS). Si no, falla diciendo el notebook y las
    huellas de las imagenes que no se han revisado (son de imagenes: se
    pueden publicar). Devuelve [(nombre, tipo, bytes)] de cada imagen, para
    mirar sus metadatos."""
    notebooks = _notebooks_publicados(raiz)
    problemas, imagenes = [], []
    for nombre in sorted(set(notebooks) | set(declaradas)):
        if nombre not in declaradas:
            problemas.append(f"{nombre}: no esta en IMAGENES_DE_LOS_NOTEBOOKS")
            continue
        if nombre not in notebooks:
            problemas.append(f"{nombre}: esta declarado y no se publicaria")
            continue
        suyas = _imagenes_del_notebook(notebooks[nombre])
        de_sus_imagenes = tuple(sorted(hashlib.sha256(d).hexdigest()
                                       for _tipo, d in suyas))
        if de_sus_imagenes != tuple(declaradas[nombre]):
            nuevas = sorted(set(de_sus_imagenes) - set(declaradas[nombre]))
            problemas.append(f"{nombre}: {len(de_sus_imagenes)} imagenes, "
                             f"{len(declaradas[nombre])} declaradas; sin "
                             f"revisar: {', '.join(nuevas) or 'ninguna'}")
        imagenes += [(f"{nombre}, imagen {n}", tipo, datos)
                     for n, (tipo, datos) in enumerate(suyas, 1)]
    if problemas:
        pytest.fail("\n".join(
            ["Las imagenes incrustadas no son las revisadas "
             "(IMAGENES_DE_LOS_NOTEBOOKS):"]
            + _fuera_de_git(raiz)
            + ["  " + p for p in problemas]), pytrace=False)
    return imagenes


def test_las_imagenes_de_los_notebooks_son_las_revisadas():
    """Las imagenes incrustadas no las lee ni la prueba de huellas ni el
    script (el base64 largo se quita sin mirarlo): se revisan a mano y se
    fijan aqui por su huella; sus metadatos se miran como los de los PNG."""
    textos = []
    for nombre, tipo, datos in _las_imagenes_de_los_notebooks_son_las_declaradas(
            RAIZ, IMAGENES_DE_LOS_NOTEBOOKS):
        if tipo != "image/svg+xml":             # el texto lo recorre el resto
            _formato, texto = _mirar_imagen(datos, nombre)
            textos.append((nombre, texto))
    _sin_huellas_en_los_valores(textos)


def _tiradas_de_base64_sin_declarar(raiz, declaradas):
    """(fichero, linea, motivo) de cada tirada de 120 o mas caracteres de
    base64 de un fichero de texto que se publicaria (la expresion `BASE64`
    del script: lo que la busqueda de huellas quita sin mirar) que,
    decodificada, no es una de las imagenes `declaradas` (por su SHA-256).
    Nunca la tirada. Un fichero que no se deja leer es un hallazgo de linea
    0 («no se pudo leer», A5): no se da por limpio, y sin traza."""
    sin_declarar = []
    for ruta in va.ficheros_versionados(raiz):
        relativo = ruta.relative_to(raiz).as_posix()
        try:
            texto = va._texto(ruta)
        except OSError:
            sin_declarar.append((relativo, 0, "no se pudo leer"))
            continue
        if texto is None:
            continue
        for n, linea in enumerate(texto.splitlines(), 1):
            for m in va.BASE64.finditer(linea):
                try:
                    datos = base64.b64decode(m.group(), validate=True)
                except (binascii.Error, ValueError):
                    datos = None
                if (datos is None or hashlib.sha256(datos).hexdigest()
                        not in declaradas):
                    sin_declarar.append(
                        (relativo, n, "no es una imagen declarada"))
    return sin_declarar


def _toda_tirada_larga_es_una_imagen_declarada(raiz, declaradas):
    """Falla con el fichero, la linea y el motivo de cada tirada sin
    declarar (y de cada fichero ilegible), nunca con la tirada."""
    sin_declarar = _tiradas_de_base64_sin_declarar(raiz, declaradas)
    if sin_declarar:
        pytest.fail("\n".join(
            ["Tiradas de base64 de 120 o mas caracteres que no son una "
             "imagen declarada (IMAGENES_DE_LOS_NOTEBOOKS):"]
            + _fuera_de_git(raiz)
            + [f"  {fichero}:{n} ({motivo})"
               for fichero, n, motivo in sin_declarar]), pytrace=False)


def test_una_imagen_pegada_de_otra_forma_tambien_se_ve(tmp_path):
    # C3: pegada en el texto de una celda o de un .md (`data:image/png;
    # base64,...`) o en una salida `text/html`, la prueba de las imagenes de
    # los notebooks no la ve, y la de huellas quita el base64 sin mirarlo.
    raiz = _arbol_limpio(tmp_path / "arbol")
    imagen = _png_de_juguete((b"Author", b"Autor Neutro " * 8))
    en_base64 = base64.b64encode(imagen).decode("ascii")
    assert len(en_base64) >= 120
    (raiz / "notas.md").write_text(
        f"uno\n![figura](data:image/png;base64,{en_base64})\n",
        encoding="utf-8")
    notebook = {"cells": [{"cell_type": "code", "outputs": [
        {"output_type": "display_data", "data": {"text/html": [
            f'<img src="data:image/png;base64,{en_base64}">']}}]}]}
    (raiz / "cuaderno.ipynb").write_text(json.dumps(notebook, indent=1),
                                         encoding="utf-8")
    assert _imagenes_del_notebook(notebook) == []
    sin_declarar = _tiradas_de_base64_sin_declarar(raiz, set())
    assert ("notas.md", 2, "no es una imagen declarada") in sin_declarar
    assert sorted({f for f, _n, _motivo in sin_declarar}) == [
        "cuaderno.ipynb", "notas.md"]
    # Declarada, pasa; y una tirada que no es base64 valido no pasa.
    assert _tiradas_de_base64_sin_declarar(
        raiz, {hashlib.sha256(imagen).hexdigest()}) == []
    (raiz / "ruta.txt").write_text("/".join(["abcdefgh"] * 20) + "\n",
                                   encoding="utf-8")
    assert _tiradas_de_base64_sin_declarar(
        raiz, {hashlib.sha256(imagen).hexdigest()}) == [
        ("ruta.txt", 1, "no es una imagen declarada")]


def test_un_fichero_ilegible_es_un_hallazgo_de_las_tiradas(tmp_path,
                                                          monkeypatch):
    # A5: un fichero que no se deja leer (sin permiso, bloqueado) no rompe la
    # prueba de las tiradas con una traza: es un hallazgo, con el fichero.
    raiz = _arbol_limpio(tmp_path / "arbol")
    leer = Path.read_bytes

    def leer_salvo_la_guia(ruta):
        if ruta.name == "guia.md":
            raise PermissionError(13, "acceso denegado")
        return leer(ruta)

    monkeypatch.setattr(Path, "read_bytes", leer_salvo_la_guia)
    assert _tiradas_de_base64_sin_declarar(raiz, set()) == [
        ("docs/guia.md", 0, "no se pudo leer")]
    with pytest.raises(pytest.fail.Exception) as error:
        _toda_tirada_larga_es_una_imagen_declarada(raiz, set())
    assert "docs/guia.md:0 (no se pudo leer)" in str(error.value)
    assert "Traceback" not in str(error.value)
    assert "PermissionError" not in str(error.value)


def test_toda_tirada_larga_de_base64_es_una_imagen_declarada():
    """El base64 largo se quita sin mirarlo: solo puede ser una imagen de
    IMAGENES_DE_LOS_NOTEBOOKS, revisada a mano. Si falla, dice el fichero y
    la linea, no la tirada."""
    declaradas = {una for suyas in IMAGENES_DE_LOS_NOTEBOOKS.values()
                  for una in suyas}
    _toda_tirada_larga_es_una_imagen_declarada(RAIZ, declaradas)


def _mirar_metadatos_de_los_notebooks(notebooks, aviso=()):
    """Las claves de `metadata` de cada notebook, las de su `colab` (con
    `provenance` vacio) y las de cada celda son las revisadas. Si no, falla
    diciendo el notebook y la CLAVE, nunca el valor (y las lineas de
    `aviso`, si las hay)."""
    de_mas = []
    for nombre, notebook in sorted(notebooks.items()):
        metadatos = notebook.get("metadata", {})
        de_mas += [f"{nombre}: metadata.{c}"
                   for c in sorted(set(metadatos) - METADATOS_DEL_NOTEBOOK)]
        colab = metadatos.get("colab", {})
        de_mas += [f"{nombre}: metadata.colab.{c}"
                   for c in sorted(set(colab) - METADATOS_DE_COLAB)]
        if colab.get("provenance", []) != []:
            de_mas.append(f"{nombre}: metadata.colab.provenance no está vacía")
        for n, celda in enumerate(notebook.get("cells", []), 1):
            de_mas += [f"{nombre}: celda {n}, metadata.{c}"
                       for c in sorted(set(celda.get("metadata", {}))
                                       - METADATOS_DE_LA_CELDA)]
    if de_mas:
        pytest.fail("\n".join(
            ["Metadatos de notebook que no son los revisados (las huellas no "
             "los conocen: se miran a mano):"]
            + list(aviso) + ["  " + d for d in de_mas]), pytrace=False)


def _los_metadatos_de_los_notebooks_son_los_revisados(raiz):
    _mirar_metadatos_de_los_notebooks(_notebooks_publicados(raiz),
                                      aviso=_fuera_de_git(raiz))


def test_un_metadato_de_notebook_no_revisado_se_nombra_sin_su_valor():
    valor = "cuenta-de-juguete-7q"
    notebook = {
        "metadata": {"kernelspec": {"name": "python3"}, "authors": [valor],
                     "colab": {"name": "x.ipynb", "include_colab_link": True,
                               "provenance": [{"file_id": valor}]}},
        "cells": [{"metadata": {"execution": {}}},
                  {"metadata": {"id": valor, "tags": []}}]}
    _mirar_metadatos_de_los_notebooks({"limpio.ipynb": {
        "metadata": {"colab": {"name": "x.ipynb", "provenance": []}},
        "cells": [{"metadata": {"execution": {}}}]}})
    with pytest.raises(pytest.fail.Exception) as error:
        _mirar_metadatos_de_los_notebooks({"sucio.ipynb": notebook})
    mensaje = str(error.value)
    for clave in ("sucio.ipynb: metadata.authors",
                  "sucio.ipynb: metadata.colab.include_colab_link",
                  "sucio.ipynb: metadata.colab.provenance no está vacía",
                  "sucio.ipynb: celda 2, metadata.id",
                  "sucio.ipynb: celda 2, metadata.tags"):
        assert clave in mensaje
    assert valor not in mensaje


def test_los_metadatos_de_los_notebooks_son_los_revisados():
    _los_metadatos_de_los_notebooks_son_los_revisados(RAIZ)


@pytest.mark.parametrize("con_git", [
    pytest.param(False, id="sin_git"),
    pytest.param(True, id="con_git", marks=hay_git),
])
def test_fuera_de_git_el_fallo_del_arbol_lo_dice(tmp_path, con_git):
    # C4 y A1: fuera de la raiz de un repositorio se recorre la carpeta
    # entera, tambien lo que git ignoraria (un `.env` de la copia de alguien,
    # un notebook de `.ipynb_checkpoints/`): todas las pruebas que recorren
    # el arbol lo dicen al fallar.
    raiz = _repositorio(tmp_path) if con_git else _arbol_limpio(
        tmp_path / "repo")
    (raiz / ".env").write_text("X=1\n", encoding="utf-8")
    (raiz / "nota.md").write_text(f"{OTRO}\n", encoding="utf-8")
    # Un notebook con una imagen que nadie ha declarado y una clave de
    # metadatos que nadie ha revisado.
    imagen = base64.b64encode(_png_de_juguete((b"Software", b"x" * 80)))
    cuaderno = {"metadata": {"authors": ["de juguete"]}, "cells": [
        {"cell_type": "code", "metadata": {}, "outputs": [
            {"output_type": "display_data",
             "data": {"image/png": imagen.decode("ascii")}}]}]}
    (raiz / "cuaderno.ipynb").write_text(json.dumps(cuaderno, indent=1),
                                         encoding="utf-8")
    de_juguete = _huellas_de_juguete(tmp_path)
    comprobaciones = {
        "secretos": lambda: _el_arbol_no_lleva_secretos(raiz, de_juguete,
                                                        minimo=1),
        "huellas": lambda: _el_arbol_no_lleva_huellas(raiz, de_juguete,
                                                      minimo=1),
        "tiradas": lambda: _toda_tirada_larga_es_una_imagen_declarada(
            raiz, set()),
        "imagenes": lambda: _las_imagenes_de_los_notebooks_son_las_declaradas(
            raiz, {}),
        "metadatos": lambda: _los_metadatos_de_los_notebooks_son_los_revisados(
            raiz),
    }
    for que, comprobar in comprobaciones.items():
        with pytest.raises(pytest.fail.Exception) as error:
            comprobar()
        assert (NO_ES_UN_REPOSITORIO in str(error.value)) is not con_git, que
        assert OTRO not in str(error.value).lower(), que
```

`va` (el script cargado como módulo), `RAIZ` y `HUELLAS` son los nombres de
la cabecera de `tests/test_anonimato.py`.

- [ ] **Paso 2: Correrlas**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_anonimato.py -q -rs`

Esperado: `222 passed, 2 skipped` (las que se saltan son las de los
enlaces simbólicos, que esta máquina no deja crear). Estas pruebas son de
caracterización: atan lo que ya se revisó. Para verlas fallar:

- copia un PNG cualquiera a la raíz del repositorio con otro nombre, SIN
  `git add`: la de los binarios falla nombrándolo, porque un fichero sin
  seguimiento y sin ignorar también se publicaría. Bórralo después;
- en una carpeta temporal FUERA del repositorio, un PNG con un trozo de texto
  `Author`: la función que mira una imagen lo rechaza, también si el trozo va
  detrás de los datos de la imagen (por eso se llama a `load()` antes de
  leer los metadatos).

Si alguna falla porque lo declarado no coincide con lo que hay, **no edites
la constante sin mirar**: abre lo que sobre o falte, comprueba que no lleva
nada que identifique y entonces corrige la constante y la declaración.

**Fuera de un repositorio de git** —una descarga en ZIP— la prueba de los
binarios se salta diciéndolo: sin `.git` no se sabe qué está versionado, y
los `.pyc` que escribe el propio pytest son binarios. La última prueba del
fichero hace fallar las cinco que recorren el árbol —las dos de la tarea 6 y
tres de esta—, dentro y fuera de un repositorio: fuera, cada mensaje lo dice.
Va aquí, y no en la tarea 6, porque necesita las de esta. Y **con solo la huella
del centinela** en `huellas.txt` —el repositorio que se publica— las claves
de los metadatos se comprueban igual; lo que se salta, diciéndolo, es la
comparación de sus valores con las huellas.

- [ ] **Paso 3: La declaración**

Crea `tests/anonimato/README.md`:

````markdown
# Anonimato del repositorio

Este repositorio no lleva ninguna cadena que identifique a un cliente, a una
empresa, a una máquina ni a personas, ni ningún secreto. Lo vigilan dos
comprobaciones y una revisión a mano. Aquí se dice qué hace cada una y, al
final, **qué no puede ver ninguna de las tres**.

## `tests/test_anonimato.py` (en la suite, en cada corrida)

Tokeniza cada fichero de texto —minúsculas, sin tildes, partición por
cualquier carácter que no sea `[a-z0-9]`— y falla si el SHA-256 de algún
token está en `huellas.txt`. Tokeniza también el texto «desescapado» (un `\n`
escrito con barra invertida, `%20`, `&#99;`), para que un escape no pegue
letras a un token y lo esconda. Antes quita las tiradas de 120 o más
caracteres de base64 (las imágenes incrustadas en los notebooks), que
producirían tokens al azar. El texto que no es UTF-8 también se recorre.

Otra prueba busca en el mismo recorrido los secretos y lo que no se ha podido
mirar, también en los nombres de los ficheros y de las carpetas: lo que más
abajo se describe con el script. Esa no necesita la lista y corre siempre.

Recorre lo que se publicaría: los ficheros con seguimiento, los que no lo
tienen ni están ignorados, y lo que está preparado en el índice de git y no
es lo que hay en disco. Un recorrido vacío no cuenta como limpio.

`huellas.txt` lleva una huella por línea. **La lista de lo prohibido no está
en el repositorio**: solo sus huellas. Una de ellas es la del centinela
público `centinelaanonimato7f3a`, con el que la prueba se comprueba a sí
misma: lo escribe en un fichero temporal y exige detectarlo. Es la única
huella que no cuenta en el árbol: el centinela está escrito en claro en este
documento y en la propia prueba.

No hay lista blanca de huellas. Lo que se conserva —un huso horario,
identificadores opacos de los webhooks, números de chat inventados, una IP
del rango de documentación— se conserva porque no está en la lista, no porque
se exceptúe. El buscador de secretos sí deja pasar lo que es de ejemplo: unas
pocas palabras (`prueba`, `clave`, `token`, `cambiar-esto`), los marcadores
entre `<` y `>`, las variables (`$NOMBRE`, `${NOMBRE}`) y el fichero
`.env.ejemplo`.

## `scripts/verificar_anonimato.py` (antes de publicar)

Repite la búsqueda de huellas sobre cualquier árbol y añade:

- los **secretos**, por patrón (token de bot, claves de API, JWT, claves
  privadas, cabeceras `Authorization`, contraseñas y tokens asignados a una
  clave, contraseña dentro de una URL) y los ficheros que no deben viajar
  (`.env`, claves);
- lo que **no ha podido mirar** —un enlace simbólico, un submódulo, un
  fichero que no se deja abrir—, que sale como hallazgo y no como limpio
  (una carpeta que no se deja recorrer, no: más abajo);
- el **commit**: el contenido de su árbol, el autor, quien confirma y el
  mensaje (con sus pies), contra las huellas y contra los patrones de
  secretos;
- los **nombres** de los ficheros, de las carpetas, de las ramas y de las
  etiquetas;
- que el repositorio tenga **un solo commit, una sola rama y ninguna
  etiqueta**, y que ese commit no lleve más cabeceras que su árbol, su autor
  y quien lo confirma: una firma lleva el identificador de la clave de quien
  firma, así que el commit único se hace con `git commit --no-gpg-sign`;
- que lo que se publica **no lleve ninguna huella de la lista**, ni en el
  árbol —su `huellas.txt` lleva solo la del centinela—, ni en el commit (el
  mensaje, el autor, quien confirma), ni en los nombres de las ramas y de
  las etiquetas. La huella se busca entera y
  suelta, como cualquier token: pegada a otras letras o cifras, o escrita
  de otra forma, no se ve.

      python scripts/verificar_anonimato.py --raiz <árbol> --huellas <huellas> --un-solo-commit

Sus hallazgos dicen fichero, línea y huella o clase: nunca el token ni el
secreto, y el nombre de un fichero que lleve un token sale tapado. Sale con 1
si hay hallazgos, si no ha recorrido ningún fichero de texto o si las huellas
que recibe son solo la del centinela.

## Cómo se regeneran las huellas

Quien mantiene la lista en claro, fuera del repositorio:

    python scripts/verificar_anonimato.py --regenerar --lista <lista en claro>

(o con la ruta de la lista en la variable de entorno `ANONIMATO_LISTA`, sin
`--lista`). Las entradas van en la sección `[huellas]` de la lista, una por
línea, y cada una es un token ya tokenizado: una entrada que no dé
exactamente un token es un error, y no se escribe nada.

El `huellas.txt` del repositorio que se publica, con solo la huella del
centinela, se escribe sin lista, y lleva su propia cabecera, que dice qué
fichero es y dónde se hace la comprobación de verdad:

    python scripts/verificar_anonimato.py --regenerar --solo-centinela --huellas <árbol que se publica>/tests/anonimato/huellas.txt

## Lo que no es texto: revisión manual

La prueba de huellas no puede leer imágenes. Se revisaron a mano, una a una:

| Qué | Cuándo | Qué se comprobó |
| :--- | :--- | :--- |
| los 6 PNG de `docs/eda/` | 28-sep-2026 | contenido (gráficos de datos agregados del dataset público, sin nombres, rutas, marcas de agua ni pies) y metadatos (solo `Software` y `dpi`) |
| las 6 imágenes incrustadas en `notebooks/eda_rsna.ipynb` | 28-sep-2026 | son las mismas seis figuras; mismos metadatos |
| los metadatos de los tres notebooks | 29-sep-2026 | del notebook: `kernelspec` y `language_info` y, en el de Colab, `accelerator` y `colab` (con el nombre del propio notebook); de las celdas: en `eda_rsna.ipynb`, las horas de ejecución. Los otros dos notebooks no tienen salidas |
| las 10 figuras de `docs/validacion-semisintetica/` | 29-sep-2026 | contenido (gráficos de la simulación, sin nombres, rutas, marcas de agua ni pies; el título lleva el rótulo «simulación semisintética») y metadatos (`Software`, `dpi`, `Title` y `Description`, que es la huella del JSON de resultados con el que `scripts/validar_combinacion.py` dibujó cada una) |

Varias pruebas de `tests/test_anonimato.py` atan esa revisión:

- `BINARIOS_REVISADOS` es la lista de los binarios revisados: un binario
  nuevo hace fallar la suite hasta que se revisa y se declara aquí. Fuera de
  un repositorio de git —una descarga en ZIP— no se sabe qué está
  versionado, y la prueba se salta diciéndolo.
- `IMAGENES_DE_LOS_NOTEBOOKS` fija, por su SHA-256, las imágenes incrustadas
  en cada notebook: una imagen nueva, o una que cambie al volver a ejecutar
  el notebook, hace fallar la suite hasta que se revisa. Y como una imagen se
  puede pegar de más maneras (dentro del texto de una celda, en una salida
  HTML, en cualquier otro fichero), otra prueba exige que toda tirada de 120
  o más caracteres de base64 de un fichero de texto que se publica sea una
  de esas imágenes declaradas. Si el base64 va partido en líneas de menos de
  120 caracteres, esa prueba no lo ve (más abajo, en lo que esto no
  protege).
- Las claves de los metadatos de los PNG y de las imágenes incrustadas
  tienen que estar en `METADATOS_PERMITIDOS`, y las de cada notebook y de sus
  celdas, en las de la tabla (con `colab.provenance` vacío): un notebook
  guardado de nuevo desde Colab o Kaggle hace fallar la suite hasta que se
  revisa. Con la lista entera, los valores de los metadatos de las imágenes
  se miran también contra las huellas; con solo la del centinela, esa parte
  se salta diciéndolo.

Cuando no hay hallazgos pero sí binarios, el script no dice «limpio» a secas:
dice cuántos binarios quedan sin recorrer. Las imágenes incrustadas no las
cuenta: para el script un notebook es texto.

Fuera de un repositorio de git, las pruebas que recorren el árbol miran la
carpeta entera, también lo que git ignoraría: un `.env` que alguien haya
creado en su copia hace fallar la de los secretos (y la de las huellas, si
lleva un token de la lista), y el base64 de una dependencia instalada dentro
de la carpeta, la de las tiradas largas. Cuando fallan así, su mensaje lo
dice. Un fichero que no se deja abrir (sin permiso, bloqueado) no se da por
limpio: la prueba de las tiradas largas lo da como hallazgo, con su nombre.

## Lo que esto no protege

**Compara tokens con una lista cerrada.** Dice «limpio» de lo que la lista
conoce. Un identificador que nadie puso en la lista —el `id` de un workflow
nuevo, un nombre que aparece por primera vez— no lo ve. Antes de publicar
hace falta, además, que una persona recorra el árbol buscando lo que
identifica: correos, dominios, direcciones, rutas con un usuario, nombres
propios, identificadores de una instancia.

**Un token solo se detecta entero y suelto.** No se detecta pegado a otras
letras o cifras (`prefijoTOKENsufijo`, `token2026`), partido por un salto de
línea o por un guion de fin de línea, escrito con letras de otro alfabeto que
se parecen, ni en un base64 corto. Una tirada de 120 o más caracteres del
alfabeto de base64 se quita sin mirarla: el contenido de una imagen
incrustada solo lo ve la revisión a mano, y sus metadatos, la prueba que la
fija (más arriba). Y una imagen pegada como `data:` en el texto de una celda
o en una salida HTML, con su base64 partido en líneas cortas, no la ve
ninguna prueba.

**Los secretos se buscan por su forma.** Una asignación solo se mira si el
NOMBRE de la clave lleva `password`, `passwd`, `secret`, `token` o `api_key`,
o acaba en `_KEY` en mayúsculas (o, en minúsculas, en una de unas pocas:
`private_key`, `access_key`, `signing_key`…): una clave que se llame `clave`,
`contrasena`, `pwd` o `auth` no se mira. Y solo salta si el valor tiene forma
de secreto: ocho o más caracteres, con letras y cifras. Una contraseña corta,
o sin cifras, o sin letras, no salta. Un valor escrito sin comillas que lleva
paréntesis, corchetes o llaves se toma por una expresión, no por un literal; y
entre comillas, el que lleva `{{`, `${` o `$(`, o empieza por `=`: un secreto
de verdad con esa forma no salta. Detrás de un subíndice o de una coma
(`entorno["CLAVE"] = valor`, `poner("CLAVE", valor)`), un valor sin comillas
se toma por una variable y no se mira.

**Una carpeta que no se deja recorrer.** Fuera de un repositorio de git, el
recorrido se la salta sin decirlo, con todo lo que tenga dentro; dentro de un
repositorio, el recorrido se detiene con un error.

**No mira la carpeta `.git`.** La dirección del remoto, el historial de
referencias y los commits que ya no alcanza ninguna rama viven ahí. El
repositorio se publica con `git push` de su único commit, nunca comprimiendo
la carpeta.

**Quita cadenas; no oculta la autoría** a quien llegue al repositorio por
otro camino. Y no revisa el historial: por eso el repositorio que se publica
es nuevo y de un solo commit, hecho con una identidad de git que no sea la de
una persona.

**Una huella no es un secreto.** El SHA-256 de un token corto —un nombre, una
palabra, un dominio de pocas letras— se adivina probando candidatos: quien
tenga `huellas.txt` y un diccionario recupera buena parte de la lista. Por
eso la lista completa de huellas vive **solo en el repositorio de
desarrollo**, que es privado. En el repositorio que se publica,
`huellas.txt` lleva únicamente la huella del centinela: allí las pruebas que
necesitan la lista entera se saltan diciéndolo, la búsqueda de secretos y las
pruebas del mecanismo corren igual, y la comprobación de verdad se hace antes
de publicar, con `scripts/verificar_anonimato.py` y las huellas del
repositorio de desarrollo. Por lo mismo, la salida de la prueba y la del
script —que enseñan el principio de cada huella— tampoco se publican cuando
hay hallazgos.

**No decide qué se cuenta.** Las fechas de las sesiones y de las tutorías, o
la institución que nombra el `README.md`, no son cadenas de la lista: si se
publican o no se decide al construir el repositorio que se publica.

**Un salto se ve verde.** Si el `huellas.txt` del repositorio de desarrollo
se quedara solo con la huella del centinela —porque alguien copió encima el
del repositorio publicado—, la prueba de huellas del árbol se saltaría y la
suite seguiría en verde. Se ve corriendo la suite con `-rs`, que lista lo que se
salta y por qué; y el script, que no se salta nada, sale con 1.
````

- [ ] **Paso 4: La declaración también pasa la prueba**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_anonimato.py -q`

Esperado: todo en verde (la declaración es un fichero de texto versionable y
la recorren las pruebas del árbol). Recuerda que el verificador mira también
el índice: prepara los ficheros (`git add`) antes de correrla. **Y contrasta
cada afirmación de la declaración con el código**: en la primera versión,
cuatro frases no eran verdad de lo que el verificador hacía.

- [ ] **Paso 5: Commit**

```bash
git add tests/anonimato/README.md tests/test_anonimato.py
git commit -m "test(anonimato): los binarios versionados son los revisados a mano, y la declaración" -m "La prueba de huellas recorre texto; las imágenes se revisaron una a una y se declaran. Un binario nuevo hace fallar la suite hasta que alguien lo mira. La declaración dice también lo que la vigilancia no puede ver." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 8: La suite entera y lo que el equipo tiene que hacer fuera del repositorio

**Ficheros:**
- Modificar: `README.md` (una sección nueva, «Variables de entorno»; una
  frase de «Las que se saltan»; dos líneas de «Documentos»)
- Modificar: `docs/sp3-operacion.md` (§5: la tarea programada gana `N8N_URL`;
  y una sección nueva al final, «9. Después de la anonimización»)

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
anterior (las que necesitan el dataset ahora corren). Si no tienes el
dataset, dilo en el informe y sigue: esa corrida la hace el equipo.

Y las de `node`, una a una y sin tubería (con una tubería el código de salida
es el de la última orden):

```bash
node tests/decidir.mjs
node tests/profesional.mjs
node tests/mantenimiento.mjs
node tests/formulario.mjs
```

Esperado: las tres primeras imprimen `TODO VERDE` y la del formulario, cuántas
comprobaciones pasaron (`16 OK`); las cuatro salen con 0.

- [ ] **Paso 2: El README dice qué variables hacen falta**

Añade a `README.md`, detrás de la sección «Requisitos» (antes de «Dónde corre
cada cosa»), esta sección:

```markdown
## Variables de entorno

Ningún valor que identifique una instalación está escrito en el repositorio:
se pasa por el entorno. Sin ellas, lo que las necesita se detiene con un
mensaje o, en la suite, se salta diciendo qué se queda sin verificar.

| Variable | Quién la necesita | Qué es |
| :--- | :--- | :--- |
| `RSNA_RAIZ` | `scripts/preparar_sesion.py`, `pruebas/seleccionar_casos.py`, `pruebas/reproducir_casos.py` (con bots y sin ellos), `pruebas/puntuaciones.py` y `pruebas/caracterizar_conjunto.py` (estos dos, solo si no hay caché) y las pruebas que leen placas | la raíz del dataset preparado (`crudo/`, `png/`, `manifiestos/`) |
| `N8N_URL` | `pruebas/reproducir_casos.py` con bots, `pruebas/verificar_webhooks.py` y las pruebas conducidas | la dirección base de n8n, p. ej. `https://n8n.ejemplo.test` |
| `RED_N8N` | `servidor/docker-compose.yml` (se declara en `servidor/.env`) | el nombre de la red externa de Docker que comparte n8n; obligatoria |
| `COPILOTO_URL`, `COPILOTO_BD_DSN`, `TELEGRAM_SECRET_PRUEBA`, `TELEGRAM_TOKEN_PROFESIONAL`, `CHAT_SUBIDA_PLACAS` | el arnés y las pruebas conducidas | las describe la cabecera de `pruebas/reproducir_casos.py`. Ojo: `COPILOTO_URL` no quiere el mismo valor en el arnés y en las pruebas de contrato (`docs/sp3-operacion.md`, §2) |
| `ANONIMATO_LISTA` | solo quien mantiene la lista de lo que no se publica, para regenerar las huellas | la ruta de esa lista, que vive fuera del repositorio (`tests/anonimato/README.md`) |

Los workflows de `n8n/` llevan **marcadores** en vez de la dirección y de los
identificadores de las credenciales: `scripts/marcadores_n8n.py` los
sustituye por los valores de `n8n/valores.local.json` (que no se versiona;
`n8n/valores.ejemplo.json` dice qué claves lleva) antes de importarlos, y los
vuelve a poner antes de versionar un export. El procedimiento, en
`docs/sp3-operacion.md`, §7.
```

En la subsección «Las que se saltan, y qué se queda sin comprobar», la
primera frase pasa de

```
Varias pruebas necesitan algo que no está siempre: el contenedor del copiloto,
una Postgres desechable, el túnel a la base del VPS o los secretos de Telegram.
```

a

```
Varias pruebas necesitan algo que no está siempre: el dataset (`RSNA_RAIZ`),
la dirección de n8n (`N8N_URL`), el contenedor del copiloto, una Postgres
desechable, el túnel a la base del VPS o los secretos de Telegram.
```

Y en «Documentos», detrás de la línea de «Despliegue», estas dos:

```markdown
- Operación: `docs/sp3-operacion.md`
- Anonimato del repositorio: `tests/anonimato/README.md`
```

- [ ] **Paso 3: La tarea programada necesita `N8N_URL`**

En `docs/sp3-operacion.md`, §5, «Paso 2: la tarea programada diaria (la
máquina de desarrollo)»:

1. «las cuatro variables quedan en su perfil» pasa a «las cinco variables
   quedan en su perfil», y al bloque de `setx` se le añade, la primera:

   ```powershell
   setx N8N_URL (Read-Host 'dirección base de n8n, con https://')
   ```

2. «**Son cuatro y hacen dos cosas distintas**» pasa a «**Son cinco y hacen
   tres cosas distintas**», y la lista gana, la primera, esta entrada:

   ```markdown
   - `N8N_URL` es la dirección con la que el script compara la de cada
     webhook. El repositorio ya no la lleva escrita: sin ella el script **no
     comprueba nada**, lo dice, avisa por el canal si lo tiene, y devuelve 1.
   ```

`setx` escribe la variable para las consolas que se abran DESPUÉS: la tarea
programada la ve en su siguiente corrida.

- [ ] **Paso 4: Lo que cambia para quien opera lo desplegado**

Añade al final de `docs/sp3-operacion.md`, detrás de «8. Retirada» y
separada por una línea `---`, esta sección:

````markdown
---

## 9. Después de la anonimización: lo que hay que hacer una vez

El repositorio dejó de llevar escritos la dirección de n8n, el nombre de la
red y los identificadores de las credenciales. Lo desplegado **sigue
funcionando como está**; estos pasos hacen falta la próxima vez que se
despliegue o se opere desde el repositorio —el 2, antes—, y se hacen fuera
de las fechas de la sesión con el médico (`docs/sp5-sesion.md`).

1. **En el servidor, antes del próximo despliegue:** `RED_N8N` en
   `servidor/.env`, y el primer redespliegue, que vuelve a crear los dos
   contenedores (la clave de la red cambió de nombre en el compose) sin tocar
   el volumen de la base. Mientras se recrean, alrededor de un minuto, los
   bots no contestan: se hace cuando no haya consultas en curso. El
   procedimiento, orden a orden, está en
   `docs/sp2-despliegue.md`, apartado «El primer redespliegue con `RED_N8N`
   obligatoria»: se sigue ese, no se improvisa otro.

2. **En la máquina de desarrollo:** la tarea programada diaria que corre
   `pruebas/verificar_webhooks.py` necesita `N8N_URL` en su entorno (§5,
   «Paso 2»). Sin ella el script no comprueba nada: lo dice, avisa por el
   canal de avisos si lo tiene configurado, y devuelve un código de error.
   **Esto no espera a «la próxima vez»:** la tarea corre desde el clon de esa
   máquina, y desde que el clon tiene este cambio devuelve 1 y avisa cada
   mañana de que falta `N8N_URL`, sin que haya nada roto. La variable se pone
   antes de traer el cambio a ese clon; si ya está traído, ya.
   Y la acción de la tarea lleva `--sin-teclado` (§5). Si la tarea se
   registró antes, no la lleva, y repetir el `Register-ScheduledTask` del §5
   no la reemplaza: se cambia con
   `Set-ScheduledTask -TaskName 'Copiloto Triaje: webhooks de Telegram' -Action $acc`,
   con el `$acc` del §5, y se comprueba con
   `(Get-ScheduledTask -TaskName 'Copiloto Triaje: webhooks de Telegram').Actions`:
   su `Arguments` acaba en `--sin-teclado`.

3. **En la máquina de desarrollo:** `n8n/valores.local.json`, con los valores
   reales de cada marcador. Si no existe, se crea a partir de
   `n8n/valores.ejemplo.json`. Está ignorado por git y no sale de la
   máquina. Cómo se usa, en el §7 de este manual, «Los marcadores: del
   repositorio a n8n, y de n8n al repositorio».

4. **La primera vez que se importe un workflow desde el repositorio**, empezar
   por el de mantenimiento, que no atiende a nadie, y mirar en n8n, nodo a
   nodo, que cada workflow usa la credencial de SU bot antes de activarlo: un
   valor cruzado en `valores.local.json` haría contestar a un bot con la
   cuenta de otro. En el de mantenimiento, además, volver a rellenar
   `chat_equipo` (§5, paso 1).

5. **Para correr la suite completa y el arnés**, `RSNA_RAIZ` (y `N8N_URL`,
   con los secretos del arnés —los de la tabla «Variables de entorno» del
   `README.md`—, para las pruebas conducidas y para el arnés con bots). Un
   salto se ve verde: conviene correr con `-rs` y leer qué se saltó.

       setx RSNA_RAIZ "<RSNA_RAIZ>"

   `setx` vale para las consolas que se abran después: abre una nueva.
````

- [ ] **Paso 5: La documentación nueva también pasa la prueba**

El verificador mira también el índice: prepara antes los ficheros.

```bash
git add README.md docs/sp3-operacion.md
C:/venv-copiloto/Scripts/python.exe scripts/verificar_anonimato.py --raiz .
C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_anonimato.py tests/test_arrancar.py tests/test_marcadores_n8n.py -q
```

Esperado: el verificador sale con 0 (`huellas: 0`, `secretos: 0`) y las
pruebas, todas en verde. (`tests/test_arrancar.py` y
`tests/test_marcadores_n8n.py` leen las guías.)

- [ ] **Paso 6: Commit**

```bash
git commit -m "docs(anonimato): las variables de entorno y lo que el equipo hace una vez en el servidor" -m "El README dice qué variables hacen falta y quién las necesita. El manual de operación gana N8N_URL en la tarea programada y la lista de lo que hay que hacer una vez tras la anonimización." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 9: La tanda de la revisión final

Las tareas 1 a 8 pasaron cada una su revisión. Después, la rama entera pasó
una revisión final en cinco dimensiones —el árbol contra lo que las huellas
no ven, el verificador, las variables de entorno, el despliegue y los
marcadores—, con un verificador adversario para cada hallazgo: 34 hallazgos,
ninguno crítico, seis importantes. Esta tarea es la tanda que los arregla,
junto con lo que las revisiones de las tareas habían aplazado; su re-revisión
aprobó el verificador y pidió una ronda de cierre, corta, y una tercera, que
también están aquí. **Lo que cambia
en el texto y en el código de las tareas 1 a 8 ya está llevado a ellas**: lo
que este plan cita es lo que quedó. Aquí se dice qué se decidió y por qué.

Los ejemplos de esta tarea se describen y no se escriben: un secreto de
ejemplo escrito entero en este documento haría saltar la prueba que lo
recorre.

**Ficheros:**
- Modificar: `scripts/verificar_anonimato.py`, `tests/test_anonimato.py`,
  `tests/anonimato/README.md`
- Modificar: `scripts/marcadores_n8n.py`, `tests/test_marcadores_n8n.py`,
  `tests/test_mantenimiento.py`
- Modificar: `tests/test_arrancar.py`
- Modificar: `src/copiloto_triaje/config.py`, `pruebas/verificar_webhooks.py`,
  `pruebas/reproducir_casos.py`, `pruebas/seleccionar_casos.py`,
  `scripts/preparar_sesion.py`, `tests/conftest.py` y sus pruebas
- Modificar: `tests/test_flujo_paciente.py`, `tests/test_flujo_profesional.py`
- Modificar: `README.md`, `docs/sp2-despliegue.md`, `docs/sp3-operacion.md`,
  dos specs y un plan anteriores

**Cómo se trabaja:** TDD en todo lo que es código. Donde la prueba nueva pasa
a la primera (una prueba que faltaba), el rojo se ve por mutación: se deshace
el arreglo en una copia y tiene que caer.

- [ ] **Paso 1: El verificador no da por limpio lo que no debe publicarse**

Los tres importantes del verificador:

- **Las huellas publicadas.** Un árbol público que conservara el
  `huellas.txt` entero del repositorio de desarrollo salía con 0: cada huella
  es un token de 64 hexadecimales cuyo SHA-256 no está en la lista. Con
  `--un-solo-commit`, cada token de 64 hexadecimales del árbol que esté en
  las huellas recibidas, sin contar la del centinela, es un hallazgo de clase
  `huella_publicada`, con fichero y línea y sin imprimir la huella; y lo
  mismo si está en el mensaje del commit o en el nombre de una rama o de una
  etiqueta.
  `--regenerar --solo-centinela --huellas <destino>` escribe el `huellas.txt`
  del repositorio que se publica, con su propia cabecera.
- **La búsqueda de secretos no se salta.** La prueba del árbol se parte en
  `test_el_arbol_no_lleva_secretos`, que corre siempre, y
  `test_el_arbol_no_lleva_huellas`, que se salta con solo la huella del
  centinela. Cada salto dice lo que de verdad se queda sin verificar, y dos
  pruebas fijan que la de los secretos no se salta: ni con una marca encima
  ni con un salto dentro.
- **Fuera de git, nada falla.** Sin `.git` —una descarga en ZIP— la prueba de
  los binarios se salta diciéndolo. Criterio de aceptación: sobre un árbol
  extraído con `git archive` fuera de cualquier repositorio,
  `pytest tests/test_anonimato.py` no da ningún fallo. Y las cinco pruebas
  que recorren el árbol, si fallan fuera de un repositorio, lo dicen: allí se
  ha recorrido también lo que git ignoraría.

Y además: las **cabeceras del commit** (con `--commit`, la que no sea
`tree`, `author` ni `committer` es un hallazgo que dice su nombre y nunca su
valor; `parent`, solo con `--un-solo-commit`); los **nombres de las ramas y
de las etiquetas**, también contra los patrones de secretos; las **imágenes
incrustadas** en los notebooks, fijadas por su SHA-256 (y toda tirada de 120 o
más caracteres de base64 de un fichero de texto tiene que ser una de ellas:
una imagen se puede pegar de más maneras; un fichero que no se deja leer es
un hallazgo, no un fichero limpio), y los **metadatos** de los
notebooks, por sus claves; `load()` antes de leer los metadatos de
una imagen; y las aserciones sobre `huellas.txt`, sobre booleanos, para que
un fallo no enseñe las huellas, cada una con una prueba que cae si vuelve la
forma vieja. La prueba de las huellas publicadas monta su repositorio de
juguete en una ruta corta: con una carpeta temporal larga, Windows corta las
rutas y la prueba fallaba por eso.

- [ ] **Paso 2: Los patrones de secretos**

| Qué pasaba | Qué se decide |
| :--- | :--- |
| una clave acabada en `_key` en minúsculas (la clave de una caché, la clave primaria de una tabla) saltaba como secreto | la terminación `_KEY` cuenta escrita en mayúsculas; en minúsculas, solo seis terminaciones (`access_key`, `private_key`, `encryption_key`, `signing_key`, `client_key`, `master_key`) |
| un valor entre comillas con paréntesis, corchetes o llaves dentro dejó de saltar en la ronda 2 (regresión) | entre comillas es una expresión solo lo que lleva `{{`, `${` o `$(`, o empieza por `=`; suelto, lo que lleva paréntesis, corchetes o llaves |
| con subíndice o detrás de una coma, un nombre de variable saltaba | en esas dos formas el valor solo cuenta entre comillas |
| la contraseña de una URL que empieza por cifras y una barra se tomaba por un puerto y una ruta | solo si lo de antes de los dos puntos parece un host: lleva un punto, o es `localhost` |
| el token de Telegram detrás de `Bot` en mayúsculas, o con `%3A` en vez de los dos puntos, no saltaba | salta |
| una línea de 40 000 guiones costaba medio minuto | el patrón de las asignaciones no se aplica a la línea que no lleva ninguna de sus palabras clave, ni el de la URL a la que no lleva `://` |

Al terminar, el verificador sobre el repositorio tiene que seguir saliendo
con 0. Si una regla nueva salta sobre el árbol, no se edita el fichero que
salta ni se ensancha la regla hasta que calle: se mira qué es.

- [ ] **Paso 3: La herramienta de los marcadores**

- **El chat del equipo no se versiona (importante).** El workflow de
  mantenimiento desplegado lleva relleno el `chat_equipo` del nodo
  `Configuracion`, que identifica a una persona, y `--retirar` lo dejaba en
  el fichero que se versiona. Ahora lo vacía y lo dice, sin repetir el valor;
  y una prueba estática de `tests/test_marcadores_n8n.py` exige que el
  versionado vaya vacío.
- **Después de retirar, lo escrito solo lleva marcadores**: si queda una
  credencial o una URL de webhook que no es un marcador —los valores no eran
  los de esa descarga—, la herramienta se niega sin escribir, diciendo el
  nodo y nunca el valor. La URL se busca en el texto de cada nodo, no solo
  en el campo de su dirección: en dos workflows está en una nota.
- Lo que no es un workflow (una lista, un objeto sin `nodes`) no pasa en
  silencio; la escritura es atómica (a un temporal, y `os.replace`); se lee
  con marca de orden de bytes; el error de «marcadores desconocidos» no
  repite ninguna clave y nombra el marcador conocido más parecido; la URL de
  n8n es esquema y host, sin ruta; y las claves de `settings` que se
  versionan quedan fijadas en una prueba.

- [ ] **Paso 4: La guía de despliegue, y las pruebas que la vigilan**

- **El commit de vuelta (importante).** El punto 1 del primer redespliegue
  daba por commit de vuelta el de ese momento, que en un segundo intento, o si
  antes se lanzó el redespliegue de siempre, ya es el código nuevo: la vuelta
  atrás habría dejado el compose nuevo con un `.env` sin la variable. El
  punto 1 comprueba antes si el código nuevo ya está traído, y una orden da
  el commit que `main` tenía antes del `pull`; la comprobación de ese commit
  no da un `0` falso: con un commit mal copiado sale un `fatal:`.
- **Dos redes, y el camino B (importantes, de la re-revisión).** Si el
  contenedor está en dos redes, la guía manda parar: la que no está en el
  compose se pierde al recrearlo. Y el apartado no cubre el camino B: lo
  dice, y no da una receta a medias de algo que no está ensayado.
- La restauración de la copia de la base va en una sola transacción, y la
  copia se comprueba entera (`gunzip -t`) al hacerla y antes de restaurarla:
  una copia cortada no daría ningún error; la plantilla del `.env` se copia
  sin pisar uno que ya exista; el
  `.env` nace de la plantilla y lleva una sola línea `RED_N8N`; el apartado
  dice que es del camino A, y qué cambia con el B; desde SP3 son dos
  contenedores, y los pre-chequeos miran los dos nombres.
- `tests/test_arrancar.py`: la función que busca órdenes que paran o borran
  mira el trozo entero, con límites de palabra; una prueba recorre la guía
  ENTERA, en bloques con cualquier valla (ningún `down` con volúmenes, ningún
  `docker volume rm` ni `prune`, y todo lo que para, arranca o borra, por
  nombre de proyecto; las dos excepciones, del caso local, van una a una con
  su motivo); y otra fija lo que sostiene la seguridad de la guía: el nombre
  del proyecto, los de los contenedores, que no hay puertos, la clave del
  volumen y las líneas del compose que la guía cita por su número. Otras
  aserciones fijan la guarda del commit de vuelta, la del punto 1,
  `main@{1}` y el `&&` detrás de `gunzip -t`.

- [ ] **Paso 5: Las variables de entorno**

- **`N8N_URL` mal puesta no pasa por buena.** Antes de la rama la dirección
  era una constante; ahora la escribe alguien. `url_base_n8n(valor)`, en
  `src/copiloto_triaje/config.py`: esquema `http` o `https`, host (en
  minúsculas, con su puerto si lo lleva), sin usuario, ruta, consulta ni
  fragmento, sin comillas ni blancos. La usan el vigilante diario (la mal
  puesta sigue el camino de la ausente: avisa, devuelve 1, no pide tokens),
  el arnés (se detiene antes de abrir la base) y el fijador de las pruebas
  conducidas (falla diciendo por qué: un salto se ve verde).
- **`RSNA_RAIZ` a una carpeta que no es el dataset**: `seleccionar()` lo
  comprueba al principio, y la fase de elegir de `scripts/preparar_sesion.py`
  comprueba que están todas las placas ANTES de borrar lo de una elección
  anterior.
- El mensaje de la variable ausente dice dónde se pone para la tarea
  programada. Y el vigilante diario, en la tarea programada, corre con
  `--sin-teclado` y nunca pide un token por teclado: mirar si había consola no
  bastaba, porque el Programador de tareas le da una a `python.exe`, y la
  tarea se quedaba esperando. Una prueba ata la orden de la tarea del manual
  a la opción.

- [ ] **Paso 6: Las pruebas que enseñaban un valor al fallar**

En las pruebas de los workflows, y en la del chat del equipo, cada
comprobación se reduce ANTES a un booleano, y el mensaje dice el nodo o la
cuenta: la introspección de pytest enseñaba la credencial, el token que
casaba con el patrón o un trozo del texto.

- [ ] **Paso 7: La declaración y los documentos**

`tests/anonimato/README.md` se reescribe para describir el verificador tal
como queda, y se contrasta frase a frase con el código. El README gana la
fila de `RSNA_RAIZ` completa, la suite del formulario y los datos derivados
del dataset que viajan en el repositorio; el manual de operación, las cinco
variables del arnés, el aviso de que la tarea programada falla cada mañana
sin `N8N_URL`, y lo que la herramienta de los marcadores hace con el chat del
equipo.

- [ ] **Paso 8: La suite, y los commits**

```bash
C:/venv-copiloto/Scripts/python.exe scripts/verificar_anonimato.py --raiz .
C:/venv-copiloto/Scripts/python.exe -m pytest -q -rs
node tests/decidir.mjs
node tests/profesional.mjs
node tests/mantenimiento.mjs
node tests/formulario.mjs
```

Esperado: el verificador sale con 0; la suite, sin ningún fallo; las tres
primeras de `node` imprimen `TODO VERDE` y la del formulario, cuántas
comprobaciones pasaron; las cuatro salen con 0. Un commit por apartado.

**Lo que se aparcó, con destino.** Al plan que construye el repositorio que
se publica (SP5-C): si se publican las fechas de las sesiones y de las
tutorías; los hashes de commits del repositorio de desarrollo que citan el
código y los planes, que en un repositorio de un solo commit no existen;
confirmar las condiciones de redistribución de los metadatos del dataset
público; el titular de la licencia; y el texto de un aviso del workflow de
mantenimiento, que va con el próximo despliegue de los workflows. A la
próxima corrida de las pruebas conducidas: que tres de ellas miren el código
HTTP, que hay que medir antes de fijarlo.

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
identificador de red copiado en la guía, el `id` de un workflow de la
instancia y el número de una ejecución (tarea 6: los dos últimos no los
conocía la lista, y los encontró la revisión); y, en lo que se publica con
un `push`, los nombres de las ramas y de las etiquetas y el mensaje del
commit (tarea 5).

**Lo que cambió al ejecutarlo.** El verificador de la tarea 5 se rehízo en
dos rondas de revisión: el primer diseño recorría solo lo versionado (con
un repositorio recién creado decía «limpio» sin haber mirado nada), no
miraba el árbol del commit ni los nombres de las ramas, y no cazaba el
token de un bot en la forma en que va en una URL. Y este plan citaba
entero `huellas.txt`: se quitó, porque una huella no es un secreto (D9).

**Lo que encontró la revisión final** (tarea 9), que ninguna revisión de
tarea había visto porque caía entre dos tareas o en el uso que el plan
siguiente hará de lo construido: que el verificador daba por limpio un árbol
público con las huellas de la lista dentro; que al retirar los valores de un
workflow se quedaba el chat de una persona; que la búsqueda de secretos se
saltaba donde no hay lista; que la vuelta atrás del primer redespliegue no
funcionaba en un segundo intento; y que la suite fallaba en una copia sin
`.git`.

**Lo que este plan no hace:** crear ni publicar el repositorio nuevo, correr
`scripts/verificar_anonimato.py` sobre él y sobre su commit, ni decidir si el
README enlaza los videos (plan SP5-C). Tampoco toca nada desplegado.
