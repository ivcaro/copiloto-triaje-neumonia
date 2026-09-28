# Validación semisintética de la combinación (SP5)

**Todo lo que hay en esta carpeta, salvo `crudas_prueba.csv`,
`crudas_prueba.sha256` y `latencia.json`, es resultado de una simulación
semisintética** (spec de SP5, §4): las placas y sus etiquetas son reales
(conjunto de prueba de RSNA), la clínica se sortea con la distribución
publicada de la puntuación de Heckerling, y la dependencia entre clínica e
imagen es un supuesto declarado. Nada de aquí mide exactitud clínica en
pacientes. Cada tabla, figura y JSON de resultados lleva ese rótulo en su
título.

## `resultados_simulacion.json`

Lo escribe `scripts/validar_combinacion.py`. Lleva el rótulo, las huellas de
los insumos (las crudas congeladas, los pesos con que se generaron y el
calibrador), las semillas y los parámetros, la calibración de la imagen sola
y las 25 celdas `(ρ1, ρ0)` de la rejilla: en cada una, los cuatro modelos
puntuales, las diferencias pareadas frente a la imagen sola, la posición, las
colas y la contención de la horquilla frente al oráculo por lado de la
imagen, los casos discordantes, los del asma desconocida y la escala
legible. 0A y las seis celdas destacadas llevan además los intervalos del
95 % (bootstrap de 1 000 réplicas) y la sensibilidad al previo; 0A, el
cálculo 0C. No lleva fecha: dos corridas dan el mismo fichero.

## Las figuras (`fiabilidad_*.png`, `horquilla_por_celda.png`, `contencion_rejilla.png`, `pendiente_rejilla.png`)

A 300 DPI, dibujadas **leyendo** `resultados_simulacion.json`. Cada una lleva
«simulación semisintética» en el título, que va también en el metadato
`Title` del PNG.

## El análisis

`docs/validacion-semisintetica-sp5.md`, una carpeta más arriba. Lo redacta
`src/copiloto_triaje/validacion/informe.py` desde el mismo JSON: ninguna
cifra se teclea y el documento no se edita a mano.

## Cómo se regenera todo

    python scripts/validar_combinacion.py

Sin los pesos, sin red y sin contenedores; de 3 a 5 minutos. Con
`--solo-documento` se regeneran las figuras y el análisis sin recalcular.

`tests/test_resultados_publicados.py` vuelve a calcular todo lo que no es
bootstrap (las 25 celdas, la imagen sola, los insumos y los parámetros) y
falla si lo versionado deja de corresponder a los insumos o al código;
también regenera el análisis desde el JSON y lo compara con el versionado.
**No** repite el bootstrap ni compara el contenido de las figuras: de los
intervalos solo comprueba la forma, y de las figuras, el nombre, la
resolución y el título. Si se toca algo que cambie el bootstrap o el dibujo,
hay que volver a correr el guion, porque ninguna prueba lo va a pedir.

## `acta-h7-plantilla.md`

No es un resultado: es la **plantilla** del acta de la sesión con el médico
(spec de SP5, §5). La rellena `scripts/analizar_sesion.py` con las cifras de
`sesion.json`; hasta que la sesión se haga, ni `sesion.json` ni `acta-h7.md`
están en esta carpeta. El procedimiento está en `docs/sp5-sesion.md`.

## `crudas_prueba.csv` y `crudas_prueba.sha256`

No son simulación: son las **puntuaciones crudas del modelo desplegado**
sobre las 3 811 placas del conjunto de prueba (una por paciente), con la
edad, el sexo, la proyección y la etiqueta real de opacidad de RSNA. Es una
copia congelada de la caché de `pruebas/puntuaciones.py`; el `.sha256` es el
hash de los pesos con los que se generó. Con esta copia, un tercero
reproduce todos los números de la simulación **sin los pesos**. Si el modelo
se reentrena, se regenera la caché y se vuelve a congelar aquí.

Los identificadores son los públicos de RSNA (`patientId`); no hay ningún
dato de persona.

## `latencia.json`

Tampoco es simulación: es una **medición del sistema desplegado con casos de
prueba** (spec de SP5, §6.3), y su título lo dice. Lo escribe
`scripts/medir_latencia.py` desde el `latencias.json` de una corrida con
bots de `pruebas/reproducir_casos.py`: el p50 y el p95 de `ms_extremo` sobre
al menos 30 consultas sin error, frente a los umbrales de 8 s y 3 s, con las
medidas ordenadas y el método del percentil. El tramo medido va desde que
`Normalizar update` recibe el update con la placa hasta que `Desenlace`
compone la respuesta; la subida a Telegram, la entrega del webhook y el envío
de `Responder` quedan fuera. Es, por tanto, una **cota inferior** de la
latencia de extremo a extremo: cumplir un umbral aquí es necesario, no
suficiente. Lo que queda fuera se acota cronometrando a mano 5 consultas
completas (`total_a_mano`: el tiempo total, que no se suma al p50). Los casos
son placas de RSNA con clínica inventada: no hay usuarios ni pacientes. Si el
fichero no está, la latencia de extremo a extremo no se midió. Cómo se mide:
`docs/sp5-sesion.md`, «Medir la latencia».
