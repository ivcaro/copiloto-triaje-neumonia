# Ficha del modelo (*model card*)

**Proyecto:** Copiloto de triaje para neumonía en adultos · Proyecto Integrador, Maestría en Inteligencia Artificial (UEES), 2026.
**Formato:** el de las fichas de modelo de Mitchell *et al.* [1]: detalles, uso previsto, factores, métricas, datos de evaluación y de entrenamiento, análisis cuantitativos, consideraciones éticas y salvedades.
**Fecha:** 15-oct-2026 · **Versión del modelo descrito:** corrida 6, `efficientnet_b0_320px_lote24_4+20ep`.

> **Esto no es un diagnóstico, y este modelo no es un producto sanitario.** Detecta una **opacidad pulmonar** en una radiografía frontal de tórax de un adulto; una opacidad no es lo mismo que una neumonía. No se ha usado con pacientes y no tiene registro sanitario.

Todas las cifras de rendimiento salen de `app/assets/metricas.json` (agregados calculados de las puntuaciones congeladas del conjunto de prueba, con la huella de los pesos que se midieron) o de la fuente que se cita al lado. Las fichas hermanas son la [ficha de los datos](ficha_datos.md), la [arquitectura](arquitectura.md) y las [consideraciones éticas](consideraciones_eticas.md).

## Contenido

1. [Detalles del modelo](#1-detalles-del-modelo)
2. [Uso previsto](#2-uso-previsto)
3. [Factores](#3-factores)
4. [Métricas](#4-métricas)
5. [Datos de evaluación](#5-datos-de-evaluación)
6. [Datos de entrenamiento](#6-datos-de-entrenamiento)
7. [Análisis cuantitativos](#7-análisis-cuantitativos)
8. [Consideraciones éticas](#8-consideraciones-éticas)
9. [Salvedades y recomendaciones](#9-salvedades-y-recomendaciones)
10. [Cómo se carga](#10-cómo-se-carga)
11. [Referencias](#referencias)

## 1. Detalles del modelo

| Campo | Contenido |
| :--- | :--- |
| **Qué es** | Una red convolucional de clasificación binaria («opacidad pulmonar probable» o no) sobre una radiografía de tórax frontal, más un calibrador que la convierte en una razón de verosimilitud, y, en el sistema completo, una combinación bayesiana con la regla clínica de Heckerling |
| **Desarrolla** | El equipo del proyecto (Product Owner y Lead AI Engineer), en el Proyecto Integrador de la Maestría en Inteligencia Artificial de la UEES, con la tutoría de la docente del curso. Contacto: la sección «Autores y contribuciones» del README |
| **Fecha y versión** | Corrida 6 del 23-sep-2026; calibrador ajustado sobre sus propias 3 810 imágenes de validación |
| **Arquitectura** | **EfficientNet-B0** [2] de `torchvision`, con pesos iniciales de ImageNet, entrada de 3 × 320 × 320 y **un logit** de salida; 4 008 829 parámetros (4 007 548 en el extractor y 1 281 en la cabeza). Detalle capa por capa en [`arquitectura.md`](arquitectura.md#82-arquitectura-detallada) |
| **Pesos** | `pesos_modelo_cpu.pt` (16 MB), solo el `state_dict` en CPU. SHA-256: `bb985e1f792e1cfee150ec57bdc6d706f7484499fa999da3406a5798260e8d47`. No viajan en el repositorio: se descargan del *release* y se verifican contra esa huella |
| **Calibrador** | Regresión isotónica [3] de 200 puntos (`servidor/calibrador.json`), ajustada **solo** en validación; prevalencia de ajuste 0,2215 |
| **Salidas** | `probabilidad_cruda` (sigmoide del logit; **no** es una probabilidad), `probabilidad_calibrada`, `razon_de_verosimilitud` acotada a **[0,0163; 77,32]**, `clasificacion` (`opacidad_probable` o `sin_opacidad_probable`) con el umbral **0,4258**, y, si se dan los cinco hallazgos, el bloque `combinacion` |
| **Entrenamiento** | En dos fases: 4 épocas de cabeza con el extractor congelado (`lr` 1e-3) y hasta 20 de ajuste fino de la red completa (`lr` 2e-4); Adam [4] con recocido coseno [5]; pérdida `BCEWithLogitsLoss` ponderada (`pos_weight` ≈ 3,5); lote de 24; parada temprana por recall en validación; semilla 42. La mejor época fue la 5 (`docs/comparativa-corridas.md`) |
| **Combinación con la clínica** | Regla de Heckerling [6] (cinco hallazgos), con las razones de verosimilitud de la cohorte de derivación tal como las reproduce una revisión sistemática [7], y probabilidad de partida de 0,1466 |
| **Licencia** | El código se publica con licencia MIT. Los pesos se publican como descarga del repositorio; **ni las condiciones de RSNA ni las reglas de Kaggle mencionan los pesos**, y si cuentan como «datos» u obra derivada es una cuestión interpretable que no se verificó [8], [9]. La licencia del código **no restringe el uso**: los límites de uso de esta ficha son documentales |
| **Más información** | [`arquitectura.md`](arquitectura.md), [`docs/comparativa-corridas.md`](comparativa-corridas.md), [`docs/frontera-recall-especificidad.md`](frontera-recall-especificidad.md), [`docs/validacion-semisintetica-sp5.md`](validacion-semisintetica-sp5.md), `docs/validacion-semisintetica/acta-h7.md` |

**Por qué esta corrida y no la que gana la comparativa.** La comparativa de ocho corridas corona otra (`kaggle_efficientnet_b0_320px_c2`, AUC 0,889 en prueba). Las ocho caben entre 0,874 y 0,889 de AUC, un margen del orden de lo que mueve una semilla distinta (las dos ejecuciones de la **misma** configuración de MobileNetV3 difieren en 0,010). Empatadas, decide lo verificable: la corrida 6 es la que tiene el calibrador ajustado sobre sus propias imágenes de validación y los pesos comprobados por SHA-256 (`docs/sp2-despliegue.md` §1).

**Qué cambió desde el primer intento.** La primera corrida (MobileNetV3-Large a 224 px, 7 épocas) dio AUC 0,845 y recall 0,766 en prueba, por debajo de los mínimos. Se subió la resolución a 320 px, se descongeló la red completa, se pasó a 4 + 20 épocas y se comparó en igualdad de condiciones (`docs/mejoras-2026-09-21.md`):

| | Primera corrida | Modelo desplegado |
| :--- | :--- | :--- |
| Red y resolución | MobileNetV3-Large, 224 px | EfficientNet-B0, 320 px |
| AUC en prueba | 0,845 | **0,885** |
| Recall en prueba | 0,766 | **0,882** |
| Especificidad en prueba | 0,764 | 0,702 |

La especificidad bajó a propósito: el punto de operación prioriza el recall.

## 2. Uso previsto

### 2.1. Usos primarios

- **Apoyar a un profesional de triaje** —medicina o enfermería de emergencia o de atención primaria— **en la priorización** de un adulto con sospecha de neumonía, aportando la evidencia de una radiografía frontal de tórax, combinada con una regla clínica publicada.
- **Evaluar y enseñar**: probar el mismo motor, sin cuenta de Telegram, en la aplicación de demostración (`app/`).
- **Investigación y docencia**: reproducir una validación semisintética y estudiar el sesgo por vista.

**Usuarios previstos:** profesionales de la salud que **leen el resultado y deciden**; evaluadores del proyecto. El paciente nunca recibe el resultado.

### 2.2. Usos fuera de alcance

| No usarlo… | Por qué |
| :--- | :--- |
| …para decidir sobre un paciente real, hoy | Prototipo sin validación local, sin registro sanitario y sin evaluación de impacto |
| …como diagnóstico, o para descartar una neumonía | Mide **opacidad** en la placa, no neumonía; un negativo no la descarta (pierde una de cada ocho opacidades en prueba y una de cada tres en placas PA) |
| …sin un profesional que decida | Todo el diseño supone una persona; sin ella, el sesgo de automatización no tiene contrapeso |
| …en menores de 18 años o mayores de 100 | No se entrenó ni se validó con ellos. El servidor y la aplicación **lo rechazan** (`fuera_de_alcance`) |
| …sin edad legible en la cabecera | No se asume adulto. Se rechaza (`edad_desconocida`) |
| …con placas que no sean de 8 bits sin signo, en escala de grises normal, de un solo cuadro y de hasta 5 000 píxeles de lado | El modelo las vería mal (una neumonía en 16 bits baja de 0,91 a 0,48). Se rechazan (`dicom_invalido`) |
| …con radiografías laterales, de otras modalidades o de equipos distintos de los del entrenamiento | No está medido. Solo hay barrera técnica para la vista PA/AP si se enciende el umbral por vista; el resto queda en manos del usuario |
| …para cribado poblacional sin lectura humana, o para fines ajenos a la atención (seguros, empleo, trámites) | No se diseñó ni se validó para ello; la Constitución prohíbe discriminar por estado de salud [10] |
| …con otra población o prevalencia sin revalidar | Datos de Estados Unidos; la probabilidad de partida es la de una cohorte de 1990 |

## 3. Factores

| Tipo | Factores |
| :--- | :--- |
| **Relevantes** | **Vista de la placa** (PA, de pie; AP, portátil): confusor medido, porque la posición delata la gravedad. **Edad** (18–100). **Sexo** (dos categorías en los datos). **Equipo de captura y centro** (todas las placas de entrenamiento son de radiografía computarizada, CR, de 1024 × 1024 y 8 bits, de hospitales de Estados Unidos). **Prevalencia local** |
| **De evaluación** | Vista, sexo y tres franjas de edad, **y sus cruces**: PA con mujeres, hombres y 60 años o más; AP con mujeres y hombres (13 subgrupos, §7.2). Por el modo de captura de los datos **no** se pudo evaluar por raza, etnia, nivel socioeconómico, cobertura sanitaria, centro ni equipo |

## 4. Métricas

| Métrica | Definición | Por qué |
| :--- | :--- | :--- |
| **Recall (sensibilidad)** | Proporción de placas con opacidad que el modelo marca | **Métrica primaria**: en triaje el falso negativo (mandar a casa una neumonía) es el error caro |
| **Especificidad** | Proporción de placas sin opacidad que el modelo no marca | El falso positivo cuesta una placa revisada de más |
| **AUC-ROC** | Capacidad de ordenar las placas, sin depender del umbral | Compara modelos y subgrupos sin el efecto del corte |
| **Intervalos de confianza** | Wilson al 95 % [11] para recall y especificidad | Con subgrupos pequeños, un punto sin intervalo engaña |
| Razón de verosimilitud y calibración | Pendiente e intercepto de calibración, Brier y error de calibración esperado (ECE) frente a su suelo de ruido, en la simulación | La probabilidad combinada solo vale si la de la imagen está calibrada |

**Umbral de decisión.** El corte de la etiqueta del cribado es **0,4258**, elegido sobre la curva ROC de **validación** (nunca la de prueba) y congelado antes de tocar la prueba. En validación da especificidad 0,7006 y recall 0,8815 (`docs/frontera-recall-especificidad.md`). **No existe ningún punto con recall ≥ 0,85 y especificidad ≥ 0,75 a la vez**: el más cercano con especificidad ≥ 0,75 da recall 0,8400. Se prioriza el recall, y la frontera se publica entera en lugar de esconderla tras una cifra. **Umbral por vista** (apagado por defecto): PA **0,1798** y AP **0,5815** (§7.3).

**Cómo se midió la variación.** Intervalos de Wilson para las proporciones. Una sola semilla (42) por configuración entrenada: las diferencias del orden de 0,01 entre corridas caben dentro de lo que mueve una semilla distinta, y no se atribuyen a la arquitectura.

## 5. Datos de evaluación

| Aspecto | Contenido |
| :--- | :--- |
| **Conjunto** | **3 811 radiografías** de prueba, una por paciente, **844 con opacidad** (22,15 %), del conjunto RSNA [12], [13]. Se evalúa **una sola vez**, con el umbral ya congelado |
| **Cómo se obtuvo** | Partición 70/15/15 por paciente, estratificada, con semilla 42 y una prueba que falla si un paciente aparece en dos conjuntos. **Nunca se usó** para entrenar, calibrar ni elegir el umbral |
| **Composición** | Mujeres 1 677 (353 con opacidad) y hombres 2 134 (491); 18–39 años, 1 081; 40–59, 1 766; 60 o más, 964; PA 2 087 (202 con opacidad) y AP 1 724 (642) |
| **Preprocesamiento** | El mismo del servicio: gris de 8 bits a RGB, 320 × 320, normalización de ImageNet |
| **Etiqueta** | Positivo = al menos una caja de opacidad anotada (`Target = 1`); los negativos incluyen «Normal» y «anormal sin opacidad» |
| **Límite** | Es una partición propia del conjunto de entrenamiento de RSNA, no un conjunto externo: la prueba oficial de la competición no tiene etiquetas públicas. **No hay validación externa** (un acuerdo con PadChest no se gestionó) |
| **Los ejemplos de la aplicación** | Tres radiografías de Wikimedia Commons (CC0), de fuera de RSNA, empaquetadas como DICOM. El modelo **no se ha medido con ellas**: ilustran la página, no la evalúan |

Una consecuencia de la composición: la proporción de opacidad es muy distinta según la vista (642 de 1 724 placas AP, el 37,2 %, frente a 202 de 2 087 PA, el 9,7 %), y las AP son el 45,2 % de la prueba. Por eso las métricas globales **ocultan** el sesgo por vista.

## 6. Datos de entrenamiento

| Aspecto | Contenido |
| :--- | :--- |
| **Fuente** | RSNA Pneumonia Detection Challenge (Kaggle, 2018): 26 684 estudios DICOM de entrenamiento, derivados de ChestX-ray14 del NIH [13] y anotados por radiólogos [12]. Se referencian, **no se redistribuyen** [9] |
| **Filtro** | Se conservan **18–100 años**: se descartan 1 276 menores y 5 edades imposibles (148–155). Quedan **25 403** con un 22,15 % de positivos |
| **Partición** | **17 782** de entrenamiento, **3 810** de validación (parada temprana, umbral y calibrador) y 3 811 de prueba |
| **Aumento de datos** | Solo en entrenamiento: rotación de ±7°, traslación de hasta el 5 % y brillo y contraste de ±15 %; **nunca volteo horizontal** (la lateralidad cardiaca es información clínica) |
| **Desbalance** | Pérdida ponderada (`pos_weight` = negativos/positivos ≈ 3,5), partición estratificada y umbral elegido sobre la ROC, no fijo en 0,5 |

**Composición de los 25 403 adultos** (agregados de `docs/eda/metadatos_eda.csv`; sin filas por paciente):

| Característica | Valor |
| :--- | :--- |
| Con opacidad | 22,15 % (5 627); sin opacidad: 11 390 «No Lung Opacity / Not Normal» y 8 386 «Normal» |
| Sexo | 56,6 % hombres, 43,4 % mujeres |
| Edad | 28,5 % de 18 a 39, 45,7 % de 40 a 59, 25,8 % de 60 o más; media 48,8 y mediana 50 |
| Vista | 54,9 % PA, 45,1 % AP |
| **Opacidad según la vista** | **37,9 % en AP; 9,2 % en PA** |
| Equipo | Todas de modalidad CR, 1024 × 1024, 8 bits, `MONOCHROME2` |

**Los datos de ChestX-ray14** tienen etiquetas originales extraídas de informes por procesamiento de lenguaje (etiquetas «débiles») [13]; las de RSNA son anotaciones de «opacidad pulmonar que puede representar neumonía» [12]. El conjunto no trae raza, etnia ni nivel socioeconómico. La datasheet completa está en [`ficha_datos.md`](ficha_datos.md) [14].

## 7. Análisis cuantitativos

### 7.1. Rendimiento global, con el umbral 0,4258

| Conjunto | n | AUC | Recall (IC 95 %) | Especificidad (IC 95 %) |
| :--- | ---: | ---: | :--- | :--- |
| Validación | 3 810 | 0,8827 | 0,8815 | 0,7006 |
| **Prueba** | 3 811 | **0,885** | **0,88 (0,86–0,90)** | **0,70 (0,69–0,72)** |

*Fuentes: `docs/frontera-recall-especificidad.md` y `app/assets/metricas.json`.* La inferencia tarda 0,022 s por imagen en el equipo de medición (SP1) y una mediana de 143 ms en el servidor de producción con el sistema completo (`docs/sp2-despliegue.md` §7).

### 7.2. Desagregado por factores y sus cruces

| Subgrupo | n | Con opacidad | AUC | Recall (IC 95 %) | Especificidad (IC 95 %) |
| :--- | ---: | ---: | ---: | :--- | :--- |
| Todas las placas | 3 811 | 844 | 0,885 | 0,88 (0,86–0,90) | 0,70 (0,69–0,72) |
| Mujeres | 1 677 | 353 | 0,886 | 0,87 (0,83–0,90) | 0,72 (0,70–0,74) |
| Hombres | 2 134 | 491 | 0,883 | 0,89 (0,86–0,92) | 0,69 (0,66–0,71) |
| 18 a 39 años | 1 081 | 263 | 0,902 | 0,90 (0,86–0,93) | 0,73 (0,69–0,76) |
| 40 a 59 años | 1 766 | 388 | 0,889 | 0,89 (0,86–0,92) | 0,70 (0,67–0,72) |
| 60 años o más | 964 | 193 | 0,854 | 0,83 (0,77–0,88) | 0,69 (0,66–0,72) |
| Placa PA (de pie) | 2 087 | 202 | 0,882 | 0,69 (0,63–0,75) | 0,88 (0,86–0,89) |
| Placa AP (portátil) | 1 724 | 642 | 0,829 | 0,94 (0,92–0,96) | 0,39 (0,36–0,42) |
| PA, mujeres | 943 | 93 | 0,874 | 0,65 (0,54–0,73) | 0,90 (0,88–0,92) |
| PA, hombres | 1 144 | 109 | 0,892 | 0,73 (0,64–0,81) | 0,86 (0,84–0,88) |
| PA, 60 años o más | 561 | 55 | 0,855 | 0,64 (0,50–0,75) | 0,87 (0,84–0,90) |
| AP, mujeres | 734 | 260 | 0,852 | 0,95 (0,91–0,97) | 0,39 (0,35–0,44) |
| AP, hombres | 990 | 382 | 0,812 | 0,94 (0,91–0,96) | 0,39 (0,35–0,43) |

*Fuente: `app/assets/metricas.json`, generado el 2026-10-05 con los pesos de huella `bb985e1f792e…`.*

**Lo que dice la tabla:**

- **Vista, el sesgo principal.** El recall es **0,69** en PA y **0,94** en AP; la especificidad, 0,88 y 0,39. Los intervalos no se solapan. Es un confusor: entre las placas sin ningún hallazgo, el modelo marca el 14 % de las AP y el 1 % de las PA, y el 79 % de las AP sin opacidad tiene otros hallazgos, de las que marca el 73 % (frente al 26 % en PA) (workshop de la Semana 4, riesgo R1). Dentro de cada vista el modelo ordena aceptablemente (AUC 0,88 en PA y 0,83 en AP).
- **Edad.** Con 60 años o más, el AUC baja a 0,854 (frente a 0,902 de 18 a 39) y el recall a 0,83; en PA con 60 años o más, el recall es **0,64** (IC 0,50–0,75).
- **Sexo.** Sin diferencia material en el global (recall 0,87 en mujeres y 0,89 en hombres, con intervalos que se solapan). Dentro de PA, las mujeres tienen el recall más bajo (0,65 frente a 0,73, con intervalos que se solapan): un subgrupo **a vigilar** [15].
- Los subgrupos pequeños (PA con 60 años o más: 55 positivos) tienen intervalos anchos: la estimación puntual no basta.

### 7.3. El umbral por vista y su precio

El umbral por vista (PA 0,1798, AP 0,5815) se eligió **en validación** para igualar el recall de las dos vistas, y se evaluó en prueba sin haberla mirado al elegir (`app/assets/metricas.json`, `umbral_por_vista_en_prueba`):

| Placas | Recall, un umbral | Recall, dos umbrales | Especificidad, un umbral | Especificidad, dos umbrales |
| :--- | :--- | :--- | :--- | :--- |
| PA | 0,69 (0,63–0,75) | 0,89 (0,84–0,93) | 0,88 (0,86–0,89) | 0,65 (0,62–0,67) |
| AP | 0,94 (0,92–0,96) | 0,89 (0,86–0,91) | 0,39 (0,36–0,42) | 0,56 (0,53–0,59) |
| Todas | 0,88 (0,86–0,90) | 0,89 (0,87–0,91) | 0,70 (0,69–0,72) | 0,62 (0,60–0,63) |

La diferencia de recall entre vistas pasa de 0,25 a 0,003 y las opacidades sin marcar bajan de 100 a 94, pero la especificidad global baja de 0,70 a 0,62, por debajo del mínimo de 0,70 del proyecto. **No mejora a todos: redistribuye el error.** Está **apagado por defecto** en el servidor y en la aplicación; encenderlo lo decide la institución.

### 7.4. Calibración de la imagen sola (simulación semisintética, sobre la prueba)

| AUC | Brier | Pendiente | Intercepto | ECE | Suelo de la ECE (media / p95) |
| ---: | ---: | ---: | ---: | ---: | :---: |
| 0,884 | 0,108 | 0,98 | 0,012 | 0,016 | 0,012 / 0,017 |

La ECE no supera el percentil 95 de su suelo: no se distingue del ruido de muestreo. *(`docs/validacion-semisintetica-sp5.md`, «La imagen sola».)* Una pendiente menor que 1 diría que el modelo exagera; aquí es 0,98.

### 7.5. La banda contradictoria

Con la puntuación cruda entre 0,4258 y 0,5786 la etiqueta es positiva pero la razón de verosimilitud es **menor que 1**. Ocurre en **379 de las 3 811** placas de prueba (9,9 %), que son el 23,3 % de lo que el cribado etiqueta como positivo, y el 80,5 % de ellas no tenía opacidad. No es un caso raro: es el comportamiento habitual del punto de operación elegido (SP3 §3).

### 7.6. La combinación con la regla clínica (simulación semisintética)

Con las 3 811 placas reales de prueba y una clínica **sorteada** con la distribución publicada de la regla de Heckerling, y con la dependencia entre clínica e imagen como supuesto declarado. **No mide exactitud clínica en pacientes** (`docs/validacion-semisintetica-sp5.md`):

| Escenario (dependencia nula, 0A; 3 460 casos con el asma conocida) | AUC | Brier | Pendiente |
| :--- | ---: | ---: | ---: |
| Imagen sola | 0,885 | 0,107 | 0,98 |
| Clínica sola | 0,790 | 0,134 | 0,95 |
| Combinación, independencia | **0,930** | 0,082 | 1,03 (0,95–1,10) |
| Combinación, extremo conservador | 0,929 | 0,085 | 1,27 |

Con independencia nula, el sistema reproduce caso a caso la posterior del generador: **calcula lo que dice calcular**. Con dependencia, **la independencia exagera** (pendiente menor que 1 en las seis celdas destacadas, de 0,65 a 0,93) y la hipótesis de que la horquilla contiene la verdad simulada en al menos el 90 % de los casos concordantes **no se sostiene en ninguna** de las seis celdas con intervalo (contención de 17,4 % a 70,7 %). La cifra combinada se entrega, por tanto, como **orientativa**.

### 7.7. La sesión con un médico (acuerdo, no exactitud)

Un médico general colaborador, 24 viñetas semisintéticas, dos lecturas (`docs/validacion-semisintetica/acta-h7.md`):

| Medida | Resultado |
| :--- | :--- |
| **Kappa ponderado lineal** (primario, sin el sistema delante) | **0,25** (IC 95 % analítico 0,07–0,44; BCa 0,11–0,49): **no alcanza el mínimo de 0,4** de la Semana 1 |
| Porcentaje del médico dentro de la horquilla del sistema | 0 de 24 |
| Con el mensaje delante | kappa 0,81; cambió de banda en **12 de 20** casos |
| Utilidad (1–5) | Corrección 4,7; utilidad 4,0; **lenguaje 2,5** |
| Tiempo de triaje | Razón con/sin 2,00; corregida por releer, 1,11 (0,69–1,81) |

Un solo evaluador, 24 casos elegidos por estratos y una clínica generada: **no generaliza** ni mide exactitud.

## 8. Consideraciones éticas

Resumen de la ficha; el análisis completo está en [`consideraciones_eticas.md`](consideraciones_eticas.md).

| Pregunta de la ficha | Respuesta |
| :--- | :--- |
| **Datos** | Placas desidentificadas de un conjunto público de Estados Unidos, con etiqueta de opacidad. No contienen raza, etnia ni nivel socioeconómico; no se puede auditar por esas dimensiones. Sin datos de pacientes reales del proyecto |
| **Vidas humanas** | El modelo informa la prioridad de un paciente; un falso negativo puede retrasar un tratamiento. Por eso el recall es la métrica primaria, un negativo lleva un aviso explícito y el profesional decide siempre |
| **Mitigaciones** | Umbral por vista (evaluado, apagado por defecto); razón de verosimilitud acotada; rechazo de lo que no se puede evaluar; horquilla en vez de un número; mapa de calor con su advertencia; informe sin texto del paciente; esta ficha |
| **Riesgos y daños** | R1 sesgo por vista y edad; R2 datos de salud que pasan por Telegram; R3 sesgo de automatización (el médico cambió de banda en 12 de 20 casos con el mensaje delante); R4 fallo silencioso ante un cambio de dominio; R5 caja negra; R6 uso fuera de alcance |
| **Casos de uso** | Apoyo a la decisión de un profesional; docencia. **No**: diagnóstico, cribado sin lectura humana, decisiones sobre seguros o empleo |

## 9. Salvedades y recomendaciones

Cada una de estas es una limitación **conocida** y medida o declarada, no una nota de cortesía.

1. **Opacidad no es neumonía.** El modelo aprendió la etiqueta de opacidad de RSNA: hay opacidades que no son neumonía (atelectasia, derrame, tumor) y neumonías sin opacidad visible. Todo texto del sistema que afirma dice «opacidad»; los avisos pueden decir «neumonía» porque advierten contra ese salto.
2. **Datos de Estados Unidos.** Con otra población, otros equipos u otros protocolos el rendimiento **no está medido** y puede caer sin que nada lo avise [16]. No hay validación externa.
3. **Sesgo AP/PA.** La proyección predice la etiqueta (37,9 % de opacidad en AP frente a 9,2 % en PA) y el modelo tiene atajos con la vista [16], [17]: con el umbral único, recall 0,69 en PA y especificidad 0,39 en AP. Mitigación disponible y apagada: el umbral por vista, con su precio.
4. **Los ejemplos externos no están medidos.** Las tres radiografías de la aplicación son de otra fuente y el modelo no se ha evaluado con ellas; con estos pesos, la placa «normal» sale marcada por el cribado. Sirven para ver la página, no para valorar el modelo.
5. **El kappa con el médico es bajo (0,25, por debajo de 0,4)**, con un solo evaluador y 24 viñetas: no se puede afirmar acuerdo clínico, ni tampoco su ausencia general.
6. **La combinación solo se validó en simulación**; ningún conjunto público trae la auscultación junto a la placa. La independencia exagera y la horquilla no contiene la verdad simulada bajo dependencia: la cifra es orientativa.
7. **Las razones de verosimilitud clínicas son las de derivación** (más optimistas que las de validación) y la probabilidad de partida es la de una cohorte de 1990; ambas son parámetros revisables.
8. **Una sola semilla por configuración**: las diferencias de 0,01 entre corridas no se atribuyen a la arquitectura.
9. **Las cotas de la razón de verosimilitud y la banda contradictoria dependen del calibrador**: si se reentrena, cambian y hay que reescribir esta ficha.
10. **Sin robustez adversaria medida**, sin evaluación por raza, etnia ni nivel socioeconómico, sin calibración por vista.

**Recomendaciones.** Reentrenar al menos una vez al año o ante un cambio de equipo, midiendo de nuevo por subgrupo, reajustando el calibrador y reelegiendo el umbral. Antes de cualquier uso clínico: validación local con datos emparejados, evaluación de impacto de protección de datos y la evaluación del comité de bioética de la institución.

## 10. Cómo se carga

Con el paquete instalado y los pesos descargados y verificados (la huella está en §1):

```python
from copiloto_triaje.servicio.inferencia import Motor

motor = Motor.cargar(
    "servidor/pesos_modelo_cpu.pt", "servidor/calibrador.json",
    umbral=0.4258, auc_validacion=0.8827, prevalencia_local=0.1466,
)
with open("placa.dcm", "rb") as f:
    resultado = motor.clasificar(f.read())   # sin hallazgos: solo la imagen
```

`auc_validacion` y `prevalencia_local` son obligatorios y sin valor por defecto, a propósito: una cifra por defecto sobreviviría a un reentrenamiento y seguiría citándose como si fuera la del modelo nuevo. El resultado y sus códigos de error están descritos en [`arquitectura.md`](arquitectura.md#14-el-contrato-de-la-herramienta-y-sus-errores). La interfaz que usa este mismo motor se explica en el [manual de usuario](manual_usuario.md).

---

## Referencias

[1] M. Mitchell *et al.*, «Model cards for model reporting», en *Proc. Conf. Fairness, Accountability, and Transparency (FAT∗ '19)*, 2019, pp. 220–229, doi: 10.1145/3287560.3287596.

[2] M. Tan y Q. V. Le, «EfficientNet: rethinking model scaling for convolutional neural networks», en *Proc. 36th Int. Conf. Mach. Learn. (ICML)*, 2019, arXiv:1905.11946.

[3] B. Zadrozny y C. Elkan, «Transforming classifier scores into accurate multiclass probability estimates», en *Proc. 8th ACM SIGKDD Int. Conf. Knowl. Discov. Data Min.*, 2002, pp. 694–699, doi: 10.1145/775047.775151.

[4] D. P. Kingma y J. Ba, «Adam: a method for stochastic optimization», en *Proc. 3rd Int. Conf. Learn. Represent. (ICLR)*, 2015, arXiv:1412.6980.

[5] I. Loshchilov y F. Hutter, «SGDR: stochastic gradient descent with warm restarts», en *Proc. 5th Int. Conf. Learn. Represent. (ICLR)*, 2017, arXiv:1608.03983.

[6] P. S. Heckerling *et al.*, «Clinical prediction rule for pulmonary infiltrates», *Ann. Intern. Med.*, vol. 113, n.º 9, pp. 664–670, nov. 1990, doi: 10.7326/0003-4819-113-9-664.

[7] C. S. Marchello, M. H. Ebell, A. P. Dale, E. T. Harvill, Y. Shen y C. C. Whalen, «Signs and symptoms that rule out community-acquired pneumonia in outpatient adults: a systematic review and meta-analysis», *J. Am. Board Fam. Med.*, vol. 32, n.º 2, pp. 234–247, mar. 2019, doi: 10.3122/jabfm.2019.02.180219.

[8] Radiological Society of North America, «Pneumonia Detection Challenge Terms of Use and Attribution». Consultado: 5 oct. 2026. [En línea]. Disponible: https://www.rsna.org/-/media/files/rsna/education/ai-resources-and-training/ai-image-challenge/pneumonia-detection-challenge-terms-of-use-and-attribution.pdf

[9] Radiological Society of North America y Kaggle, «RSNA Pneumonia Detection Challenge: Rules», 2018. Consultado: 5 oct. 2026. [En línea]. Disponible: https://www.kaggle.com/competitions/rsna-pneumonia-detection-challenge/rules

[10] Asamblea Constituyente, «Constitución de la República del Ecuador», *Registro Oficial*, n.º 449, 20 oct. 2008.

[11] E. B. Wilson, «Probable inference, the law of succession, and statistical inference», *J. Am. Stat. Assoc.*, vol. 22, n.º 158, pp. 209–212, 1927, doi: 10.1080/01621459.1927.10502953.

[12] G. Shih *et al.*, «Augmenting the National Institutes of Health chest radiograph dataset with expert annotations of possible pneumonia», *Radiol. Artif. Intell.*, vol. 1, n.º 1, art. e180041, ene. 2019, doi: 10.1148/ryai.2019180041.

[13] X. Wang, Y. Peng, L. Lu, Z. Lu, M. Bagheri y R. M. Summers, «ChestX-ray8: hospital-scale chest X-ray database and benchmarks on weakly-supervised classification and localization of common thorax diseases», en *Proc. IEEE Conf. Comput. Vis. Pattern Recognit. (CVPR)*, 2017, pp. 3462–3471, doi: 10.1109/CVPR.2017.369.

[14] T. Gebru *et al.*, «Datasheets for datasets», *Commun. ACM*, vol. 64, n.º 12, pp. 86–92, dic. 2021, doi: 10.1145/3458723.

[15] L. Seyyed-Kalantari, H. Zhang, M. B. A. McDermott, I. Y. Chen y M. Ghassemi, «Underdiagnosis bias of artificial intelligence algorithms applied to chest radiographs in under-served patient populations», *Nat. Med.*, vol. 27, n.º 12, pp. 2176–2182, dic. 2021, doi: 10.1038/s41591-021-01595-0.

[16] J. R. Zech, M. A. Badgeley, M. Liu, A. B. Costa, J. J. Titano y E. K. Oermann, «Variable generalization performance of a deep learning model to detect pneumonia in chest radiographs: a cross-sectional study», *PLOS Med.*, vol. 15, n.º 11, art. e1002683, nov. 2018, doi: 10.1371/journal.pmed.1002683.

[17] A. J. DeGrave, J. D. Janizek y S.-I. Lee, «AI for radiographic COVID-19 detection selects shortcuts over signal», *Nat. Mach. Intell.*, vol. 3, n.º 7, pp. 610–619, 2021, doi: 10.1038/s42256-021-00338-7.
