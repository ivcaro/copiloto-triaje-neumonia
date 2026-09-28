# SP5 — La sesión con el médico, de principio a fin

Todo lo de aquí es **simulación semisintética** (spec de SP5 §4-§5): la placa
es real, la clínica es generada, y el kappa mide acuerdo con un evaluador, no
exactitud. Nada de la sesión se versiona: `pruebas/sesion/` está en
`.gitignore`.

## 0. Antes (una vez)

- `RSNA_RAIZ` apunta a la raíz del dataset preparado (`crudo/stage_2_train_images/*.dcm`
  y `png/*.png`). Sin ella, los scripts se detienen y lo dicen.
- La suite en verde: `C:/venv-copiloto/Scripts/python.exe -m pytest` y
  `node tests/formulario.mjs`.
- Fechas con el médico: lectura 1 el 6, 7 u 8 de octubre; lectura 2 exactamente
  siete días o más después (6 → 13, 7 → 14, 8 → 15). En presencia o por
  videollamada: en remoto asíncrono los tiempos no valen.

## 1. Elegir los casos (5-oct, y se congela con el tag `h7-sesion`)

    C:/venv-copiloto/Scripts/python.exe scripts/preparar_sesion.py --fase elegir --salida pruebas/sesion --semilla 20261006

Deja `casos.json` (27 casos: 24 + 3 de práctica), `clave.json`,
`formulario/` con las placas y `datos_lectura1.js`, y `dosier_lectura1.md`.

## 2. Los mensajes reales

**Corrida de humo con bots.** Antes de la corrida completa de abajo, una
comprobación corta con dos casos, para no descubrir un problema del túnel o
de los secretos a mitad de los 27: copiar las dos primeras entradas de
`pruebas/sesion/casos.json` a un fichero pequeño, por ejemplo
`pruebas/sesion/humo-casos.json`, siempre que al menos una de las dos lleve
signos distintos de los fijos 38,2 °C / 104 lpm / crepitantes sí / murmullo
no, y correr, con el túnel y los secretos igual que abajo:

    C:/venv-copiloto/Scripts/python.exe pruebas/reproducir_casos.py --casos pruebas/sesion/humo-casos.json --salida pruebas/sesion/humo

En `pruebas/sesion/humo/mensajes.json`, comprobar a mano que la línea
`EXPLORADO — …` de cada mensaje repite los signos de ese caso y que
`resultado.combinacion` está presente: es la única prueba de que los bots
escriben la clínica de cada caso, y no una fija.

Con el túnel al VPS y los secretos en el entorno (los de `pruebas/reproducir_casos.py`):

    C:/venv-copiloto/Scripts/python.exe pruebas/reproducir_casos.py --casos pruebas/sesion/casos.json --salida pruebas/sesion/corpus

Sin túnel, el respaldo escrito en el spec §5.6: la imagen local construida del
tag `h7-sesion`, y `--sin-bots`; el acta cita el tag y el digest de la imagen:

    docker build -t copiloto-mcp:h7-sesion -f servidor/Dockerfile .
    docker image inspect copiloto-mcp:h7-sesion --format "{{.Id}}"
    (arrancar el contenedor como en tests/test_contrato_mcp.py::ARRANCAR, con ese tag y -p 127.0.0.1:18001:8000)
    COPILOTO_URL=http://127.0.0.1:18001/mcp C:/venv-copiloto/Scripts/python.exe pruebas/reproducir_casos.py --sin-bots --casos pruebas/sesion/casos.json --salida pruebas/sesion/corpus

En los dos casos queda `pruebas/sesion/corpus/mensajes.json` y un corpus legible en `00-sesion/`.

    C:/venv-copiloto/Scripts/python.exe scripts/preparar_sesion.py --fase mensajes --salida pruebas/sesion

Comprueba que cada mensaje repite la viñeta y que la concordancia coincide con
la prevista, y escribe `datos_lectura2.js`, `datos_planb.js`,
`dosier_lectura2.md` y la clave definitiva. Si algo no cuadra, se detiene y
lo lista: no se corrige a mano.

    git tag h7-sesion

## 3. Ensayo (antes del 5-oct)

Un integrante del equipo hace las dos lecturas con el formulario
(`pruebas/sesion/formulario/index.html?lectura=1` y `?lectura=2`), descarga
los CSV y corre el análisis del paso 5. Sirve para probar el formulario, los
tiempos y el acta; sus CSV se borran.

## 4. Las lecturas

- Abrir `pruebas/sesion/formulario/index.html?lectura=1` en el navegador del
  equipo (en presencia) o compartirlo por videollamada. Tres casos de
  práctica primero, luego los 24. Al terminar, «Descargar CSV» →
  `pruebas/sesion/lectura1.csv`.
- Siete días después, `?lectura=2` → `pruebas/sesion/lectura2.csv`.
- **Plan B** (una sola sesión): `?lectura=planb` → `pruebas/sesion/planb.csv`.
  El kappa sale de la primera respuesta; el tiempo no se mide.
- El estado se guarda en el navegador tras cada envío: si se cierra, se
  retoma en el caso a medias, que vuelve a empezar con su reloj.

## 5. El análisis y el acta

    C:/venv-copiloto/Scripts/python.exe scripts/analizar_sesion.py --sesion pruebas/sesion --lectura1 lectura1.csv --lectura2 lectura2.csv
    (plan B)  C:/venv-copiloto/Scripts/python.exe scripts/analizar_sesion.py --sesion pruebas/sesion --lectura1 planb.csv --planb planb.csv

Escribe `docs/validacion-semisintetica/sesion.json` y `acta-h7.md` con todas
las cifras leídas del JSON. El acta se envía al médico el 16-oct; sus
observaciones se anexan sin editar. Los resultados se presentan a la tutora
en la tutoría del 17-oct.

## Qué se versiona y qué no

Se versionan `sesion.json` y `acta-h7.md` (cifras, `patientId`, estratos).
No se versionan las placas, los mensajes, los CSV del médico ni `clave.json`.
