# Acta de H7 — sesión de concordancia con un médico sobre viñetas semisintéticas

**Rótulo:** simulación semisintética — sesión H7. La placa de cada caso es real (conjunto de prueba de
RSNA); la clínica es generada. El kappa mide acuerdo con un evaluador, no
exactitud clínica.

**Participante:** médico general colaborador, de forma voluntaria; sin datos
personales en ningún fichero del proyecto.

**Fechas:** lectura 1 el 2026-10-10; lectura 2 el 2026-10-15. Cada fecha es el día en la hora de Ecuador continental
(UTC−5).

**Casos:** 24, elegidos con semilla por estratos (tabla al final). Los
mensajes del sistema se generaron con la imagen local del tag h7-sesion, digest sha256:41c5162ea3399c6e9a5110c94196974a0b0dc40c4becd92f3d6350b296ca4bc1, con la prevalencia
desplegada (0,1466); la categoría del sistema sale del bloque
`combinacion` del mensaje.

## Método

Dos lecturas del mismo conjunto: la primera sin copiloto (placa y viñeta; banda y porcentaje) el 2026-10-10; la segunda, con el mensaje real del sistema en 20 casos y 4 controles sin mensaje, el 2026-10-15. El kappa sale solo de la primera. Pregunta al médico: probabilidad de que la placa muestre una
opacidad o infiltrado compatible con neumonía, en tres bandas (< 20 %,
20-70 %, > 70 %; convención del equipo) y como porcentaje entero. Instrumento:
el formulario local, un caso por pantalla, sin volver atrás; el tiempo va de
abrir el caso a enviar la banda. Los síntomas referidos son un fondo constante
en todos los casos (salvo el asma y la fiebre, que siguen a la clínica
generada) y así se le dijo al médico.

## Desviaciones del protocolo

- **Intervalo entre lecturas: 5 días, no los 7 o más del diseño** (spec de SP5
  §5.4). La lectura 1 se hizo el 10-oct (estaba prevista el 8) y la lectura 2
  el 15-oct. Con menos días el médico recuerda más los casos, así que el efecto
  de releer pesa más en el tiempo y en los cambios de banda de la lectura 2; los
  controles lo reflejan (3 de 4 cambiaron de banda sin mensaje). El kappa
  primario sale solo de la lectura 1 y no se ve afectado.
- **Modalidad: videollamada.** El equipo compartió solo la ventana del
  formulario y marcó lo que el médico dictaba; el tiempo de cada caso incluye
  ese tecleo, igual en las dos lecturas.
- **Banda y porcentaje.** En la lectura 1, dos casos se marcaron «alta» con un
  70 %, que por la convención de bandas es intermedia; el kappa usa la banda que
  eligió el médico, como dice el método.

## Resultados

- **Kappa ponderado lineal (primario):** 0,25 (IC 95 % analítico 0,07 a 0,44; BCa 0,11 a 0,49; n = 24).
- **Kappa de Cohen sin ponderar:** 0,10 (IC 95 % analítico -0,09 a 0,30; BCa -0,05 a 0,34; n = 24).
- **Kappa binario en «alta»:** 0,29 (IC 95 % analítico 0,03 a 0,55; BCa 0,09 a 0,65; n = 24).
- **Frente a 0,4 y 0,6:** El kappa ponderado (0,25) no alcanza el mínimo de 0,4 de la Semana 1; el límite inferior del intervalo queda por debajo de 0,4 con los dos métodos (analítico 0,07; BCa 0,11). El kappa de Cohen (0,10) no alcanza el mínimo de 0,4 de la Semana 1; el límite inferior del intervalo queda por debajo de 0,4 con los dos métodos (analítico -0,09; BCa -0,05). El kappa binario en «alta» (0,29) no alcanza el mínimo de 0,4 de la Semana 1; el límite inferior del intervalo queda por debajo de 0,4 con los dos métodos (analítico 0,03; BCa 0,09).
- **Sensibilidad a la regla de categoría del sistema (kappa ponderado):**
  extremo de independencia 0,25; extremo conservador 0,25; «si cruza un límite, intermedia» 0,25; casos cuya horquilla cruza un límite: 0 de 24.
- **Acuerdo continuo:** Spearman 0,62; diferencia media en log-odds
  (médico − sistema) 2,82 (DE 2,42); el porcentaje del médico cae dentro de
  la horquilla en 0 de 24 casos (0 %)
  (13 de 24 horquillas son un solo valor impreso,
  y 5 de ellas una cota, «< 1 %» o «> 99 %»: en ellas solo
  cuenta ese entero, y una «< 1 %» solo la cumple un 0 y una «> 99 %», un
  100; en un rango, «menos de 1 %» admite desde el 0 y «más de 99 %», hasta
  el 100); porcentajes de 0 o 100 acotados: 0; puntos medios del
  sistema por debajo de 0,5 % o por encima de 99,5 %: 4 (en
  ellos la diferencia no puede ser cero: lo que conteste el médico se acota a
  0,5 % y 99,5 %, y el sistema no).
- **Influencia del sistema (no es concordancia independiente):** kappa con el mensaje delante 0,81 (IC 95 % analítico 0,61 a 1,00; BCa 0,53 a 1,00; n = 20); cambió de banda en 12 de 20 casos.
- **Utilidad del pre-informe (1-5):** corrección 4,7 (n = 20); utilidad 4,0 (n = 20); lenguaje 2,5 (n = 20).
- **Tiempo de triaje:** razón de medias geométricas con/sin 2,00 (IC 95 % BCa 1,57 a 2,49; n = 20), aumento del 100 %; controles releídos sin copiloto: media geométrica 1,80 (n = 4); razón corregida por releer 1,11 (IC 95 % 0,69 a 1,81). El cambio medido mezcla el efecto del copiloto con el de releer; los controles estiman el de releer de forma descriptiva. Razones individuales de los controles
  (lectura 2 / lectura 1): 2,99; 2,47; 1,00; 1,41.

**Declarado antes de la sesión** (spec de SP5 §5.5): «Con 24 casos y un solo evaluador, el intervalo del 95 % del kappa tiene una anchura de 0,5 a 0,6. El diseño no distingue una concordancia moderada (0,4) de una sustancial (0,6), ni generaliza a otros médicos ni a otro reparto de casos, que aquí es deliberado. El criterio ≥ 0,4 de la Semana 1 se evalúa sobre la estimación puntual y se publica siempre con su intervalo; si el límite inferior queda por debajo de 0,4, se dice.»

**Observado en esta sesión:** el intervalo del 95 % del kappa ponderado va de 0,07 a 0,44 con el método analítico (anchura 0,37) y de 0,11 a 0,49 con el BCa (anchura 0,38); el 0,4 queda dentro con los dos métodos y el 0,6 queda fuera con los dos métodos.

## Desacuerdos, caso por caso

| Caso | Estrato | Sistema | Médico | Horquilla del sistema | Comentario |
| :--- | :--- | :--- | :--- | :--- | :--- |
| ecf3f5d3-0441-47ca-863a-78bbf5c1cad9 | negativa clara | baja | intermedia (60 %) | < 1 % |  |
| 037e120a-24fa-4f9c-8813-111136e3c288 | negativa clara | baja | intermedia (60 %) | 1 % |  |
| 9dda6b23-67f7-43c2-90db-aafdcd057042 | banda contradictoria | intermedia | alta (75 %) | 20 % |  |
| 10f3bffb-409e-4d8c-849a-f11144da7c3e | banda contradictoria | baja | intermedia (60 %) | entre 2 % y 3 % |  |
| 43e51c0e-1a39-4476-bb12-c04d89783b8b | positiva clara | intermedia | alta (75 %) | 70 % |  |
| a1867f93-5854-4539-b96d-ede4bea3d216 | asma «no sé» | baja | intermedia (60 %) | entre menos de 1 % y 3 % |  |
| d251b5bd-a852-44e1-99a2-37b7a2d0414a | negativa clara | baja | alta (75 %) | < 1 % |  |
| 192e8e4a-4db4-4c04-9b74-297e15b87c8e | asma «no sé» | intermedia | alta (75 %) | entre 34 % y 55 % |  |
| fab7b94e-97fe-4e9d-b383-f9c2bb586c08 | negativa clara | baja | intermedia (60 %) | < 1 % |  |
| 9576b42f-84a6-41b2-8b0f-75f867fcbc38 | negativa clara | baja | intermedia (60 %) | < 1 % |  |
| b9a50c1f-4b93-4a91-963f-a8d06fe077ee | asma «no sé» | baja | alta (85 %) | entre 3 % y 11 % |  |
| 5d44d6fa-b592-4cb8-acb6-bb19ea73e10e | banda contradictoria | intermedia | alta (85 %) | 43 % |  |
| 48d3ea7e-ae42-4679-81ee-3b228573907a | asma «no sé» | baja | alta (85 %) | entre 5 % y 16 % |  |
| d783664a-fef1-4959-8d09-79c25870dfe7 | positiva clara | intermedia | alta (85 %) | 44 % |  |
| ef7cd600-75c9-4b07-bb0e-f66e857fdafa | positiva clara | intermedia | alta (85 %) | 44 % |  |
| df4ce5ba-76d3-49c0-95f4-4a9206e77432 | banda contradictoria | baja | intermedia (65 %) | entre 9 % y 11 % |  |

## Pregunta sobre el PACS

¿En su práctica, la radiografía en DICOM se obtiene del PACS? Es la pregunta
que el diseño de SP3 (§18) dejó para antes de H7.

No quedó anotada en la reunión de preparación. Al cerrar el acta se le hizo
otra vez, como pregunta 2 del [resumen de una página](resumen-para-el-medico.md)
que se le envió con ella, y respondió por WhatsApp. Su respuesta, sin editar:

> «Por Dicon o por link»

## Observaciones del médico

Se anexan sin editar: sus respuestas a las preguntas 1 y 3 del
[resumen](resumen-para-el-medico.md), por WhatsApp, transcritas por el equipo
sin su nombre.

> 1. «No. El analisis puede ser mejor, a mi parecer se cambio de opinion al
>    cotejar los sintomas, las imagenes y el análisis de la IA»
> 3. «Sería bueno aumentar sintomas como si es fumador, tipo de tos, aspecto y
>    coloración de las secreciones, estado general de paciente y resultados de
>    exámenes de laboratorio, para hacer más presciso el diagnóstico»

## Conformidad

**El médico no dio su conformidad.** A la pregunta 1 del resumen —«¿Este
resumen y el acta reflejan lo que pasó en las sesiones? Sí / No (y qué
corregiría)»— respondió «No», con el motivo citado arriba.

El equipo entiende que su objeción es a cómo se interpretan los cambios de banda
de la lectura 2: él los atribuye a cotejar los síntomas, las imágenes y el
análisis de la IA, no a dejarse llevar por el sistema. Ninguna cifra de esta acta
cambia por ello. Cómo lo lee el equipo, y qué haría falta para distinguir las dos
lecturas, está en la [lectura crítica de H7](lectura-critica-h7.md).

Anexado el 21-oct-2026.

## Anexo: los casos

| Caso | Estrato | Clínica frente a imagen |
| :--- | :--- | :--- |
| 1ba253cb-105f-4250-80bf-be5565bd359c | positiva clara | concordante |
| 59a41481-07af-4816-8e5f-472ad42febef | positiva clara | concordante |
| 73d61c35-605f-435e-af98-5cc68b188a46 | positiva clara | concordante |
| fc9c1884-617f-4a89-be08-0af7d6fc2cca | positiva clara | concordante |
| d783664a-fef1-4959-8d09-79c25870dfe7 | positiva clara | discordante |
| ef7cd600-75c9-4b07-bb0e-f66e857fdafa | positiva clara | discordante |
| 43e51c0e-1a39-4476-bb12-c04d89783b8b | positiva clara | discordante |
| 93351a14-30a7-494c-a02b-7f2d72c724c8 | positiva clara | discordante |
| a26bdab3-55db-47a6-8641-1371bd6d2568 | negativa clara | concordante |
| ecf3f5d3-0441-47ca-863a-78bbf5c1cad9 | negativa clara | concordante |
| fab7b94e-97fe-4e9d-b383-f9c2bb586c08 | negativa clara | concordante |
| 9576b42f-84a6-41b2-8b0f-75f867fcbc38 | negativa clara | concordante |
| ec755d65-c3e4-427f-b7fc-7a596cf8fbb2 | negativa clara | discordante |
| d251b5bd-a852-44e1-99a2-37b7a2d0414a | negativa clara | discordante |
| d67b30b3-a9ae-4a24-bc2c-1d0c8f87e5ac | negativa clara | discordante |
| 037e120a-24fa-4f9c-8813-111136e3c288 | negativa clara | discordante |
| 9dda6b23-67f7-43c2-90db-aafdcd057042 | banda contradictoria | discordante |
| 5d44d6fa-b592-4cb8-acb6-bb19ea73e10e | banda contradictoria | discordante |
| df4ce5ba-76d3-49c0-95f4-4a9206e77432 | banda contradictoria | concordante |
| 10f3bffb-409e-4d8c-849a-f11144da7c3e | banda contradictoria | concordante |
| b9a50c1f-4b93-4a91-963f-a8d06fe077ee | asma «no sé» | concordante |
| a1867f93-5854-4539-b96d-ede4bea3d216 | asma «no sé» | concordante |
| 48d3ea7e-ae42-4679-81ee-3b228573907a | asma «no sé» | discordante |
| 192e8e4a-4db4-4c04-9b74-297e15b87c8e | asma «no sé» | discordante |

**Congelado verificable:** sha256 de mensajes.json `319e4181a04fa801de3cdd8b0e1489c08def852809150c3b89a0a798461da13a` y de clave.json `3da010236c9924bc905e91500df1b03f297a33de11ef8d2e0269e256aacd9d2d`.
