# SP5 — La sesión con el médico, de principio a fin

Todo lo de aquí es **simulación semisintética** (spec de SP5 §4-§5): la placa
es real, la clínica es generada, y el kappa mide acuerdo con un evaluador, no
exactitud. Nada de la sesión se versiona: `pruebas/sesion/` está en
`.gitignore`.

Los comandos van en PowerShell o en Git Bash; donde la sintaxis cambia (una
variable de entorno), se dan las dos.

## 0. Antes (una vez)

- `RSNA_RAIZ` apunta a la raíz del dataset preparado (`crudo/stage_2_train_images/*.dcm`
  y `png/*.png`). Sin ella, los scripts se detienen y lo dicen.
- La suite en verde: `C:/venv-copiloto/Scripts/python.exe -m pytest` y
  `node tests/formulario.mjs`.
- Fechas con el médico: lectura 1 el 6, 7 u 8 de octubre; lectura 2 exactamente
  siete días o más después (6 → 13, 7 → 14, 8 → 15). En presencia o por
  videollamada: en remoto asíncrono los tiempos no valen.

## 1. Elegir los casos (5-oct, y se congela con el tag `h7-sesion`)

**Primero, congelar el código.** Con el árbol limpio —`git status --porcelain`
no imprime nada; `pruebas/sesion/` está ignorado y no cuenta— se crea el tag
antes de elegir y antes de cualquier `docker build`: los casos, los mensajes y
la imagen del respaldo salen así del código etiquetado.

    git status --porcelain
    git tag h7-sesion

Después:

    C:/venv-copiloto/Scripts/python.exe scripts/preparar_sesion.py --fase elegir --salida pruebas/sesion --semilla 20261006

Deja `casos.json` (27 casos: 24 + 3 de práctica), `clave.json`,
`formulario/` con las placas y `datos_lectura1.js`, y `dosier_lectura1.md`.
Cada elección lleva una marca, `preparacion` (semilla y hora), que viaja a los
datos del formulario: el navegador no retoma un estado guardado de otra
preparación. Si `clave.json` ya tiene la fase mensajes, el script se detiene:
repetir la elección borra la lectura 2 y los bloques del mensaje (`--forzar`
lo hace a sabiendas).

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

Sin túnel, el respaldo escrito en el spec §5.6: la imagen local construida
desde el código del tag `h7-sesion` (el árbol sigue limpio y en el tag), y
`--sin-bots`; el acta cita el tag y el digest de la imagen:

    docker build -t copiloto-mcp:h7-sesion -f servidor/Dockerfile .
    docker image inspect copiloto-mcp:h7-sesion --format "{{.Id}}"
    (arrancar el contenedor como en tests/test_contrato_mcp.py::ARRANCAR, con ese tag y -p 127.0.0.1:18001:8000)

y el arnés contra ese contenedor, en PowerShell:

    $env:COPILOTO_URL = "http://127.0.0.1:18001/mcp"; C:/venv-copiloto/Scripts/python.exe pruebas/reproducir_casos.py --sin-bots --casos pruebas/sesion/casos.json --salida pruebas/sesion/corpus

o en Git Bash:

    COPILOTO_URL=http://127.0.0.1:18001/mcp C:/venv-copiloto/Scripts/python.exe pruebas/reproducir_casos.py --sin-bots --casos pruebas/sesion/casos.json --salida pruebas/sesion/corpus

En los dos casos queda `pruebas/sesion/corpus/mensajes.json` y un corpus legible en `00-sesion/`.
Luego, con bots:

    C:/venv-copiloto/Scripts/python.exe scripts/preparar_sesion.py --fase mensajes --salida pruebas/sesion

o, sin bots, con el tag y el `Id` que imprimió `docker image inspect`:

    C:/venv-copiloto/Scripts/python.exe scripts/preparar_sesion.py --fase mensajes --salida pruebas/sesion --imagen-tag h7-sesion --imagen-digest sha256:...

Comprueba que cada mensaje repite la viñeta, que su bloque `combinacion` es el
previsto (concordancia, puntuación, RV de imagen y prevalencia) y, con bots,
que lo que guardó el bot coincide con la lectura del arnés; y escribe
`datos_lectura2.js`, `datos_planb.js`, `dosier_lectura2.md` y la clave
definitiva, con el origen de los mensajes. Si algo no cuadra, se detiene y lo
lista: no se corrige a mano. Si unos mensajes se generaron con bots y otros
sin bots, también se detiene: la sesión usa un solo modo para los 27 casos,
porque el acta cita un solo origen. Y si se generaron sin bots y faltan
`--imagen-tag` o `--imagen-digest`, también: el acta los cita.

## 3. Ensayo (1-4 oct), en una carpeta aparte

Un integrante del equipo hace de lector con una sesión completa en
`pruebas/sesion/ensayo/`, con otra semilla y sin crear el tag, para probar el
formulario, los tiempos y el acta. Los pasos 1 y 2, con `--salida
pruebas/sesion/ensayo --semilla 20261001`:

    C:/venv-copiloto/Scripts/python.exe scripts/preparar_sesion.py --fase elegir --salida pruebas/sesion/ensayo --semilla 20261001
    C:/venv-copiloto/Scripts/python.exe pruebas/reproducir_casos.py --casos pruebas/sesion/ensayo/casos.json --salida pruebas/sesion/ensayo/corpus
    C:/venv-copiloto/Scripts/python.exe scripts/preparar_sesion.py --fase mensajes --salida pruebas/sesion/ensayo

(sin bots, el arnés con `--sin-bots` y `COPILOTO_URL`, y `--fase mensajes` con
`--imagen-tag` e `--imagen-digest`, como en el paso 2). Las dos lecturas con
`pruebas/sesion/ensayo/formulario/index.html?lectura=1` y `?lectura=2`, los
CSV en `pruebas/sesion/ensayo/`, y el análisis fuera de `docs/`, que se
versiona:

    C:/venv-copiloto/Scripts/python.exe scripts/analizar_sesion.py --sesion pruebas/sesion/ensayo --lectura1 lectura1.csv --lectura2 lectura2.csv --salida pruebas/sesion/ensayo/sesion.json --acta pruebas/sesion/ensayo/acta-h7.md

Al terminar, se borra la carpeta `pruebas/sesion/ensayo/` entera, y la
lectura real se abre la primera vez con `?nuevo=1`
(`index.html?lectura=1&nuevo=1`), que borra lo que el navegador tuviera
guardado para esa lectura antes de empezar.

## 4. Las lecturas

- Antes de la lectura 1, abrir `pruebas/sesion/formulario/index.html?lectura=1`
  y comprobar que arranca en «Práctica 1 de 3». Si la cabecera dice «Se
  retoma: …», no es la lectura limpia: abrir con `?lectura=1&nuevo=1`.
- La lectura 1 en el navegador del equipo (en presencia) o compartida por
  videollamada. Tres casos de práctica primero, luego los 24. Al terminar,
  «Descargar CSV» → `pruebas/sesion/lectura1.csv`.
- Siete días después, `?lectura=2` → `pruebas/sesion/lectura2.csv`.
- **Plan B** (una sola sesión): `?lectura=planb` → `pruebas/sesion/planb.csv`.
  El kappa sale de la primera respuesta; el tiempo no se mide.
- El estado se guarda en el navegador tras cada envío, por lectura y por
  preparación: si se cierra, se retoma en el caso a medias, que vuelve a
  empezar con su reloj, y la cabecera dice cuántas respuestas se retoman.

## 5. El análisis y el acta

    C:/venv-copiloto/Scripts/python.exe scripts/analizar_sesion.py --sesion pruebas/sesion --lectura1 lectura1.csv --lectura2 lectura2.csv
    (plan B)  C:/venv-copiloto/Scripts/python.exe scripts/analizar_sesion.py --sesion pruebas/sesion --lectura1 planb.csv --planb planb.csv

Exige la clave definitiva (la del paso 2) y `corpus/mensajes.json`, y rechaza
lecturas cambiadas o incompletas y controles que no son los de la clave.
Escribe `docs/validacion-semisintetica/sesion.json` y `acta-h7.md` con todas
las cifras leídas del JSON. El acta cita el origen de los mensajes (con bots,
o el tag y el digest de la imagen local) y, al final, el sha256 de
`corpus/mensajes.json` y de `clave.json` («Congelado verificable»). El acta se
envía al médico el 16-oct; sus observaciones se anexan sin editar. Los
resultados se presentan a la tutora en la tutoría del 17-oct.

## 6. Medir la latencia

No es parte de la sesión ni es simulación: es una **medición del sistema
desplegado** con casos de prueba (spec de SP5 §6.3). Los mensajes de la
sesión no la miden; hace falta una corrida propia del arnés **con bots**, y
tiene que estar hecha antes del 16-oct: sin ella, la latencia de extremo a
extremo se declara «no medida», con la causa.

Lo pone quien la corre, en el entorno y nunca en un fichero del repositorio:
`N8N_URL` (la dirección del n8n desplegado, p. ej. `https://n8n.ejemplo.test`),
el túnel a la base (`COPILOTO_BD_DSN`), los dos secretos
(`TELEGRAM_SECRET_PRUEBA` y `TELEGRAM_TOKEN_PROFESIONAL`), `CHAT_SUBIDA_PLACAS`
y `COPILOTO_URL`; la cabecera de `pruebas/reproducir_casos.py` dice qué es
cada uno. Si falta `COPILOTO_BD_DSN` o alguno de los dos secretos, el arnés
corre sin bots y no mide nada.

    C:/venv-copiloto/Scripts/python.exe pruebas/reproducir_casos.py --por-perfil 12 --salida pruebas/corpus/latencia

Solo cuentan las consultas que dan un resultado: los perfiles 01, 02 y 03
(12 cada uno) y el 04 (siempre 1) suman 37, por encima de las 30 que pide el
spec y con margen para alguna conversación que no llegue al final. Los otros
cinco perfiles son rechazos previstos (20 casos más) y se cuentan aparte. Con
el `--por-perfil 10` por defecto serían 31: bastarían dos conversaciones
fallidas para dejar la medición sin hacer. Son 57 casos y, como poco, 20
minutos. El arnés imprime «N casos» al arrancar: si salen menos de 57, a algún
perfil le faltan placas en la caché; lo que importa es que las consultas de
los perfiles 01 a 04 pasen holgadamente de 30, y `scripts/medir_latencia.py`
dice cuántas contó y cuántas descartó, con el motivo.

La corrida deja `pruebas/corpus/latencia/latencias.json` (una fila por caso;
la carpeta está ignorada). Después:

    C:/venv-copiloto/Scripts/python.exe scripts/medir_latencia.py --corrida pruebas/corpus/latencia/latencias.json --manual "S1,S2,S3,S4,S5"

`S1`…`S5` son los cinco tiempos cronometrados a mano (más abajo), en segundos
y con punto decimal: la orden, copiada tal cual, se niega a correr. Sin
medición a mano se omite `--manual`, y el JSON dice «no medido».

Escribe `docs/validacion-semisintetica/latencia.json` con el p50 y el p95 de
`ms_extremo` frente a los umbrales de 8 s y 3 s, las medidas ordenadas (sin
identificadores, para que cualquiera pueda recalcular) y cuántas filas se
descartaron y por qué. Una consulta cuenta si pasó por los bots, llegó al
final, no es un rechazo previsto, no dio error **en la propia consulta** y
coincide con la lectura del arnés. Con menos de 30 consultas válidas se
detiene, lo dice y no escribe nada.

`ms_extremo` va desde que `Normalizar update` recibe el update con la placa
hasta que `Desenlace` compone la respuesta: no ve la subida a Telegram, la
entrega del webhook ni el envío de `Responder`. Es, por tanto, una **cota
inferior** de lo que espera el profesional: si no cumple un umbral, la
latencia de extremo a extremo tampoco lo cumple; si lo cumple, es necesario
pero no suficiente.

Lo que `ms_extremo` no ve se acota **a mano, en 5 consultas**, con un chat
real de profesional, cinco placas de las que usó la corrida (perfiles 01 a
03) y un cronómetro, porque el cliente de Telegram solo enseña horas y
minutos. El cronómetro se pone en marcha al enviar la placa y se para cuando
aparece el pre-informe: es el tiempo **total**, subida incluida, no el tramo
que falta, y no se suma al p50. Son los valores de `--manual`.

Al terminar, las filas que el arnés dejó en `consultas` se borran con la
orden que él mismo imprime.

## Qué se versiona y qué no

Se versionan `sesion.json`, `acta-h7.md` (cifras, `patientId`, estratos y
las dos huellas) y `latencia.json` (solo cifras agregadas). No se versionan
las placas, los mensajes, los CSV del médico
ni `clave.json`: el equipo los guarda, y las huellas del acta permiten
comprobar que son esos.
