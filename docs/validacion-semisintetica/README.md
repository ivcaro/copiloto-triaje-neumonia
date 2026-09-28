# Validación semisintética de la combinación (SP5)

**Todo lo que hay en esta carpeta, salvo `crudas_prueba.csv`, es resultado
de una simulación semisintética** (spec de SP5, §4): las placas y sus
etiquetas son reales (conjunto de prueba de RSNA), la clínica se sortea con
la distribución publicada de la puntuación de Heckerling, y la dependencia
entre clínica e imagen es un supuesto declarado. Nada de aquí mide exactitud
clínica en pacientes. Cada tabla, figura y JSON lleva ese rótulo en su
título.

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
