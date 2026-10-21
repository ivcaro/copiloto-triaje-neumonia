# Consideraciones éticas

**Proyecto:** Copiloto de triaje para neumonía en adultos · Proyecto Integrador, Maestría en Inteligencia Artificial (UEES), 2026.
**Estado del documento:** actualizado el 18-oct-2026 sobre el análisis del workshop «Impacto social y responsabilidad» (Semana 4, 5-oct-2026), con lo hecho desde entonces, con los resultados de la sesión con el médico colaborador y con SP5-D (18-oct): un modelo de lenguaje redacta, a la salida, un segundo mensaje para el profesional, lo que añade un tercero que recibe datos ([§6.4](#64-lo-que-tampoco-es-nuestro-openai)).

> **Qué es y qué no es este sistema.** Es un prototipo académico que ayuda a un profesional de triaje a priorizar a un adulto con sospecha de neumonía. **No es un producto sanitario, no tiene registro sanitario, no diagnostica y no ha atendido a ningún paciente real**: se probó con radiografías de un conjunto público y con síntomas inventados. El profesional decide siempre. Este documento dice lo que sabemos de sus riesgos, con evidencia, y lo que no sabemos.

Se escribe contra los ocho puntos que pide la entrega del curso —sesgos, equidad, privacidad, transparencia, impacto social, responsabilidad, uso dual y limitaciones— y conserva la estructura del workshop de la Semana 4: partes interesadas, riesgos R1–R5 con evidencia, mitigaciones M1–M6 con su estado, responsabilidad, cumplimiento normativo, reflexión y compromiso. Los nombres de las personas no aparecen: se habla de roles.

## Contenido

1. [Resumen](#1-resumen)
2. [Alcance de la implementación](#2-alcance-de-la-implementación)
3. [Partes interesadas](#3-partes-interesadas)
4. [Análisis de sesgos](#4-análisis-de-sesgos)
5. [Equidad y *fairness*](#5-equidad-y-fairness)
6. [Privacidad](#6-privacidad)
7. [Transparencia y explicabilidad](#7-transparencia-y-explicabilidad)
8. [Impacto social](#8-impacto-social)
9. [Registro de riesgos éticos](#9-registro-de-riesgos-éticos)
10. [Mitigaciones y su estado](#10-mitigaciones-y-su-estado)
11. [Responsabilidad y rendición de cuentas](#11-responsabilidad-y-rendición-de-cuentas)
12. [Uso dual y mal uso](#12-uso-dual-y-mal-uso)
13. [Limitaciones reconocidas: cuándo no usarlo](#13-limitaciones-reconocidas-cuándo-no-usarlo)
14. [Cumplimiento normativo](#14-cumplimiento-normativo)
15. [Lo que enseñó la sesión con el médico](#15-lo-que-enseñó-la-sesión-con-el-médico)
16. [Reflexión y compromiso del equipo](#16-reflexión-y-compromiso-del-equipo)
17. [Lo que falta antes de cualquier uso clínico](#17-lo-que-falta-antes-de-cualquier-uso-clínico)
18. [Referencias](#referencias)

## 1. Resumen

| Pregunta | Respuesta corta | Dónde |
| :--- | :--- | :--- |
| ¿Hay sesgos? | Sí, y uno medido: el rendimiento depende de la **vista** de la placa. Con el umbral único, el recall es **0,69** en placas PA (paciente de pie) y **0,94** en placas AP (portátil); la especificidad, 0,88 y 0,39. La vista es un indicador aproximado (*proxy*): el conjunto no registra si el paciente era ambulatorio o estaba encamado, y «PA = ambulatorio, AP = encamado» es la lectura habitual de cómo se tomó la placa | [§4](#4-análisis-de-sesgos), [§5](#5-equidad-y-fairness) |
| ¿Quién sale perjudicado? | El paciente ambulatorio con placa PA (3 de cada 10 opacidades sin marcar), sobre todo con 60 años o más (recall 0,64); el paciente encamado asume los falsos positivos | [§5](#5-equidad-y-fairness) |
| ¿Se mitigó? | Hay una mitigación evaluada (umbral por vista, que iguala el recall de las dos vistas) y **desplegable pero apagada por defecto**, porque tiene precio: la especificidad global baja de 0,70 a 0,62 | [§10](#10-mitigaciones-y-su-estado) |
| ¿Se protege la privacidad? | Parcialmente. No se guarda ninguna imagen y se usan seudónimos, pero los datos **pasan por Telegram**, un tercero fuera de nuestro control, y falta la evaluación de impacto exigible a un uso real. Desde SP5-D, el informe determinista (sin imagen ni identificadores directos) también viaja a **OpenAI** para redactar el pre-informe | [§6](#6-privacidad) |
| ¿Se entiende cómo funciona? | La parte clínica sí (razones de verosimilitud explícitas); la de la imagen es una caja negra con un mapa de calor de apoyo. El médico calificó el **lenguaje** del informe con 2,5 sobre 5; el pre-informe que un LLM redacta desde SP5-D responde a eso y **no está validado con el médico** | [§7](#7-transparencia-y-explicabilidad), [§15](#15-lo-que-enseñó-la-sesión-con-el-médico) |
| ¿Quién responde si falla? | El profesional que decide; la institución que lo adopta; el equipo, de lo técnico. No hay hoy una institución | [§11](#11-responsabilidad-y-rendición-de-cuentas) |
| ¿Se puede usar con pacientes? | **No.** Faltan validación local con datos emparejados, evaluación de impacto de protección de datos, registro sanitario y la evaluación del comité de bioética | [§17](#17-lo-que-falta-antes-de-cualquier-uso-clínico) |

**Lo que cambió desde el workshop de la Semana 4** (cada cambio se detalla en su apartado):

| Tema | En el workshop (5-oct) | Hoy (18-oct) |
| :--- | :--- | :--- |
| Umbral por vista (M1, paso 3) | Propuesto | **Hecho** en el servidor y la aplicación, apagado por defecto (6-oct) |
| Mapa de calor (M5) | Propuesto | **Hecho**, en la aplicación de demostración y no en el bot |
| Consentimiento (M2, paso 1) | Reescrito el 5-oct | Ampliado el 18-oct (SP5-D) con una viñeta que nombra a OpenAI; nombra además a Telegram, la IA, el plazo real y el derecho a la explicación |
| Pre-informe redactado por un LLM (R7, M8) | No existía: el LLM se había descartado en SP3 y SP4 | **Nuevo** (SP5-D, 18-oct): un LLM redacta un segundo mensaje detrás del informe, revisado por código y rotulado; **sin validar con el médico** ([§6.4](#64-lo-que-tampoco-es-nuestro-openai)) |
| Placas que el modelo vería mal (M4) | Línea nueva | **Desplegado**: rechazo por cabecera de 16 bits, `MONOCHROME1`, color, tamaños desmedidos, compresiones sin descodificador |
| Ficha del modelo (M5) | Pendiente | **Hecha**: [`ficha_modelo.md`](ficha_modelo.md) |
| Validación de la combinación | «Solo en simulación» | Simulación semisintética **publicada** y **sesión con un médico**: kappa ponderado 0,25, por debajo del mínimo de 0,4 ([§15](#15-lo-que-enseñó-la-sesión-con-el-médico)) |
| Guía para el profesional (M3, paso 2) | Pendiente | **Hecha** en el [manual de usuario](manual_usuario.md#3-parte-b-los-bots-de-telegram) |

## 2. Alcance de la implementación

**El problema.** La neumonía adquirida en la comunidad se sospecha en el triaje con datos clínicos y se confirma con una radiografía de tórax que alguien tiene que leer a tiempo. Ninguna de las dos fuentes basta sola: las reglas clínicas tienen una capacidad de discriminación moderada [1], [2] y la placa depende de quién la lea y de cuándo.

**El sistema.** Dos bots de Telegram: el del paciente recoge síntomas con botones y le entrega un código seudónimo; el del profesional —personas dadas de alta en una lista blanca— recibe el código, cuatro signos de exploración y la radiografía DICOM. Una red convolucional (EfficientNet-B0) entrenada con el conjunto público de RSNA [3], [4] y calibrada convierte la placa en una razón de verosimilitud acotada; la regla de Heckerling aporta la suya; una combinación bayesiana devuelve una horquilla cuando las dos evidencias apuntan al mismo lado y un número con un aviso cuando se contradicen. Detrás del informe, un modelo de lenguaje (OpenAI) redacta un segundo mensaje, el pre-informe, a partir de ese informe y de nada más. Hay además una aplicación web de demostración con el mismo motor, que no llama al modelo de lenguaje. La arquitectura está en [`arquitectura.md`](arquitectura.md).

| Pregunta del workshop | Respuesta |
| :--- | :--- |
| ¿Dónde se usaría? | Hoy, en ninguna parte: es un prototipo desplegado en un servidor privado y probado con placas del conjunto público y síntomas generados. Su uso previsto es el triaje de un servicio de emergencia o de atención primaria en Ecuador, como apoyo y nunca como sustituto de la lectura de la placa |
| ¿A cuántas personas afectaría? | En un piloto, a los adultos con síntomas respiratorios que pasen por ese servicio y a los pocos profesionales que lo usen. En proporción: por cada 100 adultos con sospecha y con la prevalencia de partida del sistema (14,7 %, la de la cohorte en que se derivó la regla de Heckerling, a falta de un dato ecuatoriano: ver [§4](#4-análisis-de-sesgos)), unos 15 tendrían opacidad; si el rendimiento medido se mantuviera, el sistema no marcaría a unos 2 (a 4 o 5 si todos fueran ambulatorios con placa PA) y marcaría a unos 25 de los 85 sin opacidad (unos 10 si todos fueran PA) |
| ¿Qué decisiones toma o informa? | No toma ninguna. Informa la prioridad de un paciente con sospecha y la atención que se presta a su placa; tratar, pedir más pruebas o dar el alta sigue siendo del profesional |

*Fuente de la proporción: cálculo sobre `app/assets/metricas.json` (recall y especificidad globales y de la vista PA) y la prevalencia de partida 0,1466 (`servidor/docker-compose.yml`).*

## 3. Partes interesadas

| Parte | Quién es | Beneficios | Riesgos | Voz |
| :--- | :--- | :--- | :--- | :-: |
| **Profesionales de triaje** (usuarios directos) | Medicina y enfermería de emergencia y de atención primaria | Una segunda opinión en segundos; razonamiento probabilístico explícito | Confiar de más en la herramienta; decidir apoyados en una salida errónea | Alta |
| **Pacientes adultos con sospecha de neumonía** (sujetos de las decisiones) | Responden el cuestionario; su placa y sus datos se procesan | Un triaje más rápido y consistente | Un falso negativo retrasa el tratamiento; un falso positivo trae pruebas o antibióticos de más; sus datos de salud pasan por Telegram | Baja |
| **Grupos vulnerables** | Pacientes ambulatorios con placa PA, adultos de 60 años o más, quien no tiene Telegram o domina poco lo digital | Los mismos que el resto, si se corrige el sesgo | El sistema rinde peor con ellos (recall 0,69 en PA y 0,64 en PA con 60 años o más) o no les llega | Baja |
| **Institución de salud que lo adopte** | Dirección médica, tecnología, protección de datos | Eficiencia y un criterio homogéneo | Responsabilidad legal y reputación; el coste de validarlo con sus propios pacientes | Alta |
| **Reguladores** | Ministerio de Salud, ARCSA, Superintendencia de Protección de Datos Personales | Un sistema documentado y auditable | Que llegue a uso clínico sin validación ni registro | Alta |
| **Equipo desarrollador** | Dos integrantes: Product Owner y Lead AI Engineer | Aprendizaje y un producto demostrable | Responsabilidad técnica por sesgos o fallos no detectados | Media |

Cómo se tuvo en cuenta a cada parte:

- **Profesionales.** El informe separa en bloques rotulados lo que dice la imagen, lo referido por el paciente, lo explorado y la combinación; **nunca** pone la etiqueta del cribado y la razón de verosimilitud en el mismo renglón, porque miden cosas distintas y se contradicen en una banda real; y no contiene ni un carácter escrito por el paciente, para que nadie pueda colar un texto que parezca del sistema. El pre-informe llega detrás, rotulado como redactado por IA y con la instrucción de que, si algo no coincide, vale el informe. Su interés se protege con un aviso explícito en los negativos, con la lista blanca (que impide que alguien ajeno use el sistema en su nombre) y con una guía de uso ([manual](manual_usuario.md)).
- **Pacientes.** El bot pide consentimiento antes de la primera pregunta, usa un código seudónimo en vez de la identidad, borra el cuestionario a los 7 días y las sesiones abandonadas a las 24 horas. Se les protege también al fallar: ninguna rama de error emite una probabilidad, y el modelo se niega a opinar si la edad de la placa está fuera de 18 a 100 años o no se puede leer. **El paciente nunca recibe el resultado**: su flujo no tiene ningún nodo que llame al servidor de inferencia.
- **Grupos vulnerables.** Se les tuvo en cuenta solo en parte. Los menores de 18 años quedan fuera por diseño porque el modelo no se validó con ellos; el sesgo por vista se anunció en el análisis exploratorio de la Semana 2 pero **no se midió hasta el workshop de la Semana 4**; la protección es el umbral por vista (M1), el cuestionario asistido (M6, pendiente) y las métricas por subgrupo.
- **Institución.** Dispone de un registro auditable de cada consulta, una vigilancia diaria con avisos y un procedimiento de despliegue y de vuelta atrás. Se protege su interés presentando el sistema como lo que es y exigiendo validación local y evaluación de impacto antes de usarlo con pacientes.
- **Reguladores.** Se les tuvo en cuenta al fijar el alcance (prototipo de investigación, sin uso clínico ni datos reales) y al revisar la norma aplicable ([§14](#14-cumplimiento-normativo)).
- **Equipo.** Las especificaciones declaran cada decisión y sus riesgos, hay pruebas automáticas y revisión independiente de cada rama, y este documento declara los límites del sistema.

## 4. Análisis de sesgos

> **Pregunta del curso:** ¿el conjunto de datos tiene sesgos demográficos, culturales o de otro tipo? ¿Cómo podrían afectar a las predicciones? ¿Qué grupos podrían ser perjudicados?

### 4.1. Los datos de entrenamiento

El conjunto es el RSNA Pneumonia Detection Challenge (Kaggle, 2018): 26 684 radiografías de tórax de adultos y niños, derivadas del conjunto ChestX-ray14 del NIH [4] y anotadas por radiólogos con cajas de «opacidad pulmonar que puede representar neumonía» [3]. Tras filtrar a 18–100 años quedan 25 403. Su composición (agregados calculados sobre `docs/eda/metadatos_eda.csv`, sin filas por paciente):

| Característica | Valor en los 25 403 adultos |
| :--- | :--- |
| Con opacidad | 22,15 % (5 627) |
| Sexo | 56,6 % hombres y 43,4 % mujeres (solo se registran dos categorías) |
| Edad | 28,5 % de 18 a 39 años; 45,7 % de 40 a 59; 25,8 % de 60 o más (edad media 48,8; mediana 50) |
| Vista | 54,9 % PA (de pie) y 45,1 % AP (portátil) |
| **Opacidad por vista** | **37,9 % en AP frente a 9,2 % en PA** |
| Equipo | Todas las placas son de la modalidad CR (radiografía computarizada), de 1024 × 1024 y 8 bits |

### 4.2. Los sesgos identificados

| Sesgo | Evidencia | Cómo afecta a las predicciones | Quién sale perjudicado |
| :--- | :--- | :--- | :--- |
| **De vista (confusor)** | La posición no causa la neumonía: la delata. Las placas AP se toman a quien no puede levantarse, y hay 37,9 % de opacidad en AP frente a 9,2 % en PA. Es un *proxy*: el conjunto no dice dónde estaba el paciente ni su gravedad, y «ambulatorio» o «encamado» se infieren de cómo se tomó la placa. Entre las placas sin ningún hallazgo, el modelo marca el 14 % de las AP y el 1 % de las PA: un atajo como los documentados en radiografía de tórax [5], [6]. Y el 79 % de las AP sin opacidad tiene otros hallazgos; el modelo marca el 73 % de ellas, frente al 26 % en las PA | Con un umbral único, el modelo «se pasa» de sensible en AP y se queda corto en PA | El paciente ambulatorio (PA): opacidades sin marcar. El encamado (AP): falsos positivos |
| **De edad** | Con 60 años o más, el AUC es 0,854 frente a 0,902 de 18 a 39 y el recall baja a 0,83; en PA con 60 años o más, el recall es 0,64 | El modelo ordena y detecta peor a los mayores | Adultos mayores, sobre todo ambulatorios |
| **De origen (cambio de dominio)** | Las placas son de hospitales de Estados Unidos; un modelo de neumonía rinde peor en hospitales distintos del de entrenamiento [5] | El rendimiento en un centro ecuatoriano (equipos, población, prevalencia) **no está medido** y puede caer sin que nada lo avise | Todos los pacientes, más los de centros con equipos distintos |
| **De etiqueta** | La etiqueta es «opacidad que puede ser neumonía» [3], derivada de un conjunto cuyas etiquetas originales salen de informes por procesamiento de lenguaje [4] | Hay opacidades que no son neumonía (atelectasia, derrame, tumor) y neumonías sin opacidad visible | Quien tenga una de las dos situaciones |
| **Cultural y de idioma** | El cuestionario y los bots están solo en español y se redactaron sin probar su comprensión con pacientes; las palabras («tos con flema», «falta de aire») no se validaron con hablantes de otras variedades del español ni de lenguas indígenas | Un paciente que no entienda una pregunta contesta mal, y la respuesta mal entendida llega como dato al profesional (el asma, por ejemplo, entra en la puntuación) | Hablantes de lenguas indígenas, personas mayores, de baja alfabetización |
| **De variables ausentes** | El conjunto no trae raza, etnia, nivel socioeconómico ni cobertura sanitaria, y solo dos categorías de sexo | **No se puede auditar** el rendimiento por esas dimensiones, y en otros sistemas de radiografía de tórax se ha documentado un infradiagnóstico selectivo en poblaciones desatendidas [7] | Pueblos y nacionalidades indígenas, población rural, quien no figure en las categorías: el sistema es ciego a ellos, y eso no equivale a que sea justo con ellos |
| **De la prevalencia de partida** | El 14,66 % es el de la cohorte en que se derivó la regla de Heckerling: 134 neumonías en 914 pacientes con sospecha (Illinois, Estados Unidos, 1990) [1]. Se usa porque es la población en que la regla midió sus razones de verosimilitud y no hay un dato ecuatoriano; en el despliegue es el parámetro `PREVALENCIA_LOCAL`, que la institución sustituye por la suya | La probabilidad combinada arrastra una población que no es la del servicio | Todos; es un parámetro que se cambia con dato local |
| **De la regla clínica** | Las razones de verosimilitud son las de la cohorte de **derivación** (Illinois), más optimistas que las de validación [1], [8] | En la simulación, usar las de validación cambiaría de banda a 225 de 3 460 casos | Quien está cerca de un límite de banda |

*Fuentes: workshop S4, §3–§4; `app/assets/metricas.json`; `docs/validacion-semisintetica-sp5.md` (sección 0C).*

### 4.3. Un matiz que importa: la vista es sesgo y es información

Que la placa sea AP dice algo real: el paciente está más grave. Un clínico que lo sabe usa esa información legítimamente. El problema es que **el modelo no puede distinguir entre «esta placa se ve anormal» y «esta placa es portátil»**, y cuando hay un atajo así, un umbral global esconde el fallo en PA detrás del acierto en AP. Dentro de cada vista, el modelo ordena aceptablemente (AUC 0,88 en PA y 0,83 en AP): lo que falla es **dónde se pone el corte**, no solo cómo se ordena.

## 5. Equidad y *fairness*

> **Pregunta del curso:** ¿el modelo trata a todos los grupos de forma equitativa? ¿Qué métricas de fairness se evaluaron? ¿Qué estrategias se implementaron?

**No los trata de forma equitativa**, y la evidencia está medida sobre las 3 811 placas del conjunto de prueba, que no se usaron para entrenar, ni para calibrar, ni para elegir el umbral.

### 5.1. Las métricas elegidas

La métrica de equidad principal es la **igualdad de oportunidad** [9]: que el recall (la sensibilidad) sea parecido entre grupos, porque en neumonía el error caro es el falso negativo. Se mide con el recall, la especificidad y el AUC por subgrupo, con intervalos de confianza de Wilson [10] al 95 %. **No** se evaluaron otras métricas (paridad demográfica, calibración por grupo, valor predictivo por grupo): la paridad demográfica no tiene sentido cuando la prevalencia real difiere entre grupos —y aquí difiere mucho entre vistas—, y la calibración por vista queda fuera de lo implementado.

### 5.2. Resultados por subgrupo (umbral único 0,4258)

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

*Fuente: `app/assets/metricas.json` (generado el 2026-10-05 con los pesos desplegados, huella `bb985e1f792e…`; solo agregados). Es la misma tabla que muestra la pestaña «Acerca de» de la aplicación.*

Las brechas, calculadas de esa tabla:

| Eje | Brecha de recall | Brecha de especificidad | Lectura |
| :--- | ---: | ---: | :--- |
| **Vista**: AP menos PA | 0,25 (0,941 − 0,693) | 0,49 (0,880 − 0,393, a favor de PA) | **Material**: los intervalos no se solapan. Es el sesgo principal |
| **Edad**: 18–39 menos 60 o más | 0,07 (0,901 − 0,829) | 0,04 (0,726 − 0,690) | Los mayores rinden peor (AUC 0,902 frente a 0,854); los intervalos de recall se solapan en parte |
| **Sexo**: hombres menos mujeres | 0,03 (0,892 − 0,867) | −0,03 (0,687 − 0,721) | Sin diferencia material en el global; los intervalos se solapan |
| **Sexo dentro de PA**: hombres menos mujeres | 0,09 (0,734 − 0,645) | −0,04 | Subgrupo **a vigilar**: las mujeres con placa PA tienen el recall más bajo, con intervalos que se solapan [7] |

### 5.3. Quién asume cada riesgo

Con el umbral único, de las 100 opacidades que el modelo no marca en prueba, **62 son de placas PA y 38 de AP**; de los 883 falsos positivos, **657 son de placas AP** (cifras derivadas de recall y especificidad por el tamaño de cada grupo, `app/assets/metricas.json`).

- **El paciente ambulatorio (PA) asume el riesgo del falso negativo**: 3 de cada 10 opacidades sin marcar, y es justo el paciente típico de un triaje. El riesgo se concentra en las placas PA de 60 años o más, donde se escapa una de cada tres (recall 0,64; IC 0,50–0,75).
- **El paciente encamado (AP) asume los falsos positivos** (especificidad 0,39): estudios o tratamientos de más.
- **Quien más se beneficia hoy** es el paciente encamado, al que casi ninguna opacidad se le escapa (recall 0,94).

### 5.4. Estrategias para mitigar la inequidad

**M1: umbral por vista.** Elegir el umbral de cada vista con el criterio de igualdad de oportunidad [9] —el mismo recall en AP y PA—, en validación, y evaluarlo en prueba sin haberla mirado al elegir.

Tres cifras de recall aparecen aquí y no son lo mismo: **0,80** es el mínimo comprometido en la Semana 1; **0,85**, el objetivo; y **0,88**, el que el modelo desplegado alcanza en prueba con su umbral único (0,882). Las filas por vista igualan las dos vistas en 0,88, para no perder el recall global que ya se tiene, o en 0,80, el mínimo, para ver cuánta especificidad se recupera. Resultado en prueba:

| Umbral | Recall PA | Recall AP | Recall global | Esp. PA | Esp. AP | Esp. global |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **Único, 0,4258 (desplegado)** | 0,693 | 0,941 | 0,882 | 0,880 | 0,393 | 0,702 |
| Por vista, recall 0,88 en las dos (PA 0,1798; AP 0,5815) | 0,891 | 0,888 | 0,889 | 0,646 | 0,561 | 0,615 |
| Por vista, recall 0,80 en las dos (PA 0,27; AP 0,69) | 0,861 | 0,782 | 0,801 | 0,756 | 0,690 | 0,732 |

*Fuentes: filas 1 y 2, `app/assets/metricas.json` (`umbral_por_vista_en_prueba`); fila 3, tabla 3 del workshop de la Semana 4.*

**Lectura honesta.** Al recall actual, el umbral por vista sube el recall de las placas PA de 0,69 (IC 95 %: 0,63–0,75) a 0,89 (0,84–0,93) y el de las PA de 60 años o más de 0,64 a 0,87; la diferencia entre vistas pasa de 0,25 a 0,003, aunque dentro de PA persiste la brecha por sexo (0,85 frente a 0,93). **No mejora a todos: redistribuye el error.** En prueba hay 40 opacidades sin marcar menos en PA y 34 más en AP (de 100 a 94 en total), y 259 falsos positivos más (netos: 441 más en PA y 182 menos en AP); la especificidad global baja de 0,70 a 0,62, **por debajo del mínimo de 0,70 del proyecto**. El objetivo más alto que en validación mantiene ese mínimo, un recall de 0,80, deja el de las AP en 0,78, bajo el mínimo de 0,80, y no iguala las vistas. Es el compromiso de la igualdad de oportunidad.

**Estado: hecho, apagado por defecto.** El umbral por vista existe en el servidor (variables `UMBRAL_PA` y `UMBRAL_AP`, las dos o ninguna) y en la aplicación (interruptor «Umbral por vista (experimental)»), solo cambia la etiqueta del cribado, y **no está encendido en el bot**. Encenderlo lo decide la institución, con la tabla de arriba delante: no es una decisión técnica sino de valores, porque cambia quién asume el riesgo.

**Lo que no se hizo.** No hay calibración de la razón de verosimilitud por vista; no se reentrenó con reponderación por vista; no se auditó por raza, etnia ni nivel socioeconómico porque los datos no los traen; no se repitió con otras semillas.

## 6. Privacidad

> **Pregunta del curso:** ¿se usan datos personales o sensibles? ¿Cómo se protege la privacidad? ¿Qué regulaciones se cumplen?

### 6.1. Qué datos hay

| Dato | ¿Personal o sensible? | Dónde está |
| :--- | :--- | :--- |
| Respuestas del cuestionario (fiebre, tos, días, falta de aire, dolor, asma) | **Sensible**: datos de salud (LOPDP, art. 4 y 25) [11] | `cuestionarios` y, copiadas, `consultas` |
| Signos de exploración (temperatura, pulso, crepitantes, murmullo) | Sensible: salud | `sesiones_profesional`, `consultas` |
| La radiografía DICOM | Sensible: la «información obtenida de pruebas o exámenes de una parte del cuerpo» entra en la definición [12]; la imagen médica es de uso restringido [13] | **No se guarda**; pasa por Telegram y por n8n |
| Texto libre del paciente (pregunta 7) | Puede contener cualquier cosa, incluso datos identificativos | Se guarda con el resto de las respuestas y llega al profesional en un mensaje aparte; **no** se envía a OpenAI |
| El informe determinista (síntomas de los botones, signos, cifras del modelo y avisos) | Sensible: salud, sin identificadores directos | Se guarda en `consultas`; desde SP5-D se envía además a la API de OpenAI cuando hay resultado, y el pre-informe que vuelve **no** se guarda ([§6.4](#64-lo-que-tampoco-es-nuestro-openai)) |
| `chat_id` de Telegram del paciente | Personal: identifica una cuenta | `sesiones_paciente` mientras contesta; `limite_paciente` 2 días; **no** va con el cuestionario ni con `consultas` |
| Código seudónimo | Seudonimización: sigue siendo dato personal [14] | `cuestionarios`, `consultas` |
| Nombre y `chat_id` del profesional | Personal | `profesionales` |
| Cabecera del DICOM | **Puede traer nombre, número de historia y fecha** si la placa sale de un sistema hospitalario real; las de RSNA vienen desidentificadas | Pasa tal cual: el bot no la mira |

### 6.2. Cómo se protege

- **Minimización.** No se guarda ninguna imagen; el bot no recibe el nombre ni el teléfono del paciente; el cuestionario son botones, y solo cinco datos viajan al servidor de inferencia (los de la regla), no el cuestionario entero. Al modelo de lenguaje solo llega el informe determinista, nunca la imagen ni nada que identifique directamente a nadie ([§6.4](#64-lo-que-tampoco-es-nuestro-openai)).
- **Seudonimización.** Un código de 6 caracteres (sin `0`, `O`, `1`, `I` ni `L`) en lugar de la identidad; el contador del límite diario vive en una tabla aparte, para no atar un cuestionario a una cuenta de Telegram.
- **Retención.** Sesiones abandonadas, 24 h; cuestionarios, 7 días; contador del límite, 2 días; `consultas`, hasta el cierre del proyecto, «como muy tarde, el 31 de diciembre de 2026», y se vacía tras la grabación de los videos y la fecha de entrega del video de preguntas. Las ejecuciones de n8n **no se guardan** en los bots (para que el DICOM y las respuestas no se acumulen en la base de n8n).
- **Control de acceso.** Lista blanca de `chat_id` comprobada en cada mensaje, `secret_token` en los webhooks, base de datos sin puertos publicados y con contraseña propia, límite de 5 cuestionarios por cuenta y día.
- **Aislamiento en el tramo propio.** El contenedor de inferencia no publica puertos: la radiografía no sale del servidor en el paso n8n → copiloto.
- **Aplicación de demostración.** Calcula en su propio proceso, no guarda nada en disco, no tiene telemetría ni llama a nadie al arrancar; su historial vive en la sesión del navegador y el CSV no lleva imagen ni cabecera.
- **El repositorio público** (el que se publica al cierre del proyecto) no llevará ninguna radiografía de RSNA ni tabla con una fila por paciente: solo agregados y los guiones que los regeneran desde el conjunto que cada uno descargue. Las dos tablas de trabajo del repositorio de desarrollo (`docs/eda/metadatos_eda.csv` y `docs/validacion-semisintetica/crudas_prueba.csv`) no viajan a él, por decisión del equipo del 5 de octubre (`data/README.md`). RSNA permite el uso de sus placas sin intentar identificar a nadie y con atribución [15]; las reglas de Kaggle prohíben redistribuir los datos a quien no participó [16]. Los ejemplos de la aplicación son de otra fuente (Wikimedia Commons, CC0).

### 6.3. Lo que no se protege: Telegram (R2)

**El tramo paciente o profesional → Telegram → n8n sale de nuestra infraestructura.** Telegram recibe la placa completa (con su cabecera), las respuestas, los signos, el código y la cuenta de quien escribe. Los chats con un bot se guardan cifrados en la nube de Telegram, con las claves en otras jurisdicciones; solo los «chats secretos» llevan cifrado de extremo a extremo, y un bot no puede usarlos [17]. El cifrado en tránsito protege del cable, no de Telegram.

Fue un riesgo **aceptado y declarado, no mitigado**: Telegram era la vía de entrega elegida (el profesional ya lo tiene instalado), y un canal propio habría exigido instalarlo y mantenerlo dentro de la red del centro. Hoy lo acota que **solo circulan placas de RSNA y síntomas inventados**; deja de acotarlo la primera placa real. Por eso se dice, y en ningún documento se afirma que «la radiografía no sale de la red del centro»: eso solo vale del tramo n8n → inferencia. Las vías para eliminarlo (carga web propia sobre el `POST /inferir` que ya existe, una aplicación instalada o un servidor de ficheros dentro de la red del centro) están en el diseño de SP3, §5.5. No se determinó, y es una cuestión jurídica abierta, si Telegram actúa como encargado del tratamiento o como destinatario de una transferencia internacional [11], [18]; la evaluación de impacto debe aclararlo. Tampoco se verificó dónde guarda Telegram los datos de usuarios ecuatorianos [17].

### 6.4. Lo que tampoco es nuestro: OpenAI

**Un flujo de datos nuevo, desde SP5-D (18-oct-2026).** Cuando el bot del profesional tiene un resultado, n8n manda el informe determinista a la API de OpenAI (modelo `gpt-4o-mini`) para que un LLM redacte el pre-informe. Es un segundo tercero, extranjero, y se declara igual que Telegram. Se decidió porque el lenguaje del mensaje fue la nota más baja de la sesión con el médico (2,5 sobre 5) y el LLM, que se había descartado como extractor a la entrada, puede ayudar como redactor a la salida, donde lo que escribe se comprueba contra el informe que ya llegó.

| Qué se envía a OpenAI | Qué **no** se envía |
| :--- | :--- |
| El informe determinista, sin el aviso del comentario del paciente: los síntomas (de una paleta cerrada de botones), los signos explorados, las cifras del modelo (puntuación, umbral, razón de verosimilitud, probabilidad combinada con su horquilla) y los avisos; y un mensaje de sistema fijo | La radiografía ni nada de su cabecera; el nombre; la cuenta de Telegram; el código del caso; la edad; el texto libre del paciente |

**Por qué el paciente no puede inyectarle instrucciones.** El informe no contiene ni un carácter escrito por el paciente (su texto va en otro mensaje y no sale hacia OpenAI), así que no hay por dónde. Es el mismo argumento que protege al profesional de un texto que parezca del sistema ([§12](#12-uso-dual-y-mal-uso)).

**Qué dice el proveedor, y qué no hemos verificado.** Según la página de controles de datos de su plataforma [35], desde el 1 de marzo de 2023 los datos enviados a la API de OpenAI no se usan para entrenar ni mejorar sus modelos, salvo que el cliente acepte expresamente compartirlos; los registros para vigilar abusos se conservan hasta 30 días, salvo que la ley obligue a guardarlos más tiempo o haga falta para proteger el servicio o a terceros. La retención cero de datos (*Zero Data Retention*) existe, pero exige la aprobación previa de OpenAI, y el proyecto no la tiene. Es la política del proveedor tal como la publica, que puede cambiar; el equipo no ha auditado su cumplimiento. Como con Telegram, no se determinó si OpenAI actúa como encargado o como destinatario de una transferencia internacional ([§14](#14-cumplimiento-normativo)); la evaluación de impacto debería aclararlo.

**La credencial y el coste.** La llamada usa una credencial de n8n propia del proyecto (`openai-copiloto`, con la clave del equipo), nunca la de un cliente de la instancia. El coste es del orden de una décima de centavo de dólar por consulta: una estimación, no una medición.

**Riesgos que quedan** (R7, [§9](#9-registro-de-riesgos-éticos)):

1. **Una frase plausible pero equivocada que pase la revisión.** El código comprueba que la respuesta esté completa, que cada cifra esté en el informe, que no haya palabras de tratamiento, diagnóstico o derivación ni una neumonía afirmada, que no invierta el sentido de la imagen y que la longitud sea razonable; no sabe si un texto hecho solo de cifras y palabras permitidas es clínicamente cierto. Tres formas concretas que pasan: una cifra del informe en otro papel (la sensibilidad 0,88 presentada como una probabilidad), una cifra escrita con letras («noventa por ciento») y la etiqueta del cribado invertida («marca opacidad probable» en una placa negativa). Lo que las absorbe es la cabecera («Si algo no coincide, vale el informe de arriba. No es un diagnóstico.») y que el informe llega primero, entero. Tampoco se midió si un texto en prosa fluida influye más en el médico que el informe, cuando con el informe delante ya cambió de banda en 12 de 20 casos ([§15](#15-lo-que-enseñó-la-sesión-con-el-médico)).
2. **No está validado con el médico.** H7 midió el informe sin pre-informe y el acta no se toca. No hay evidencia de que el pre-informe mejore el lenguaje: es la hipótesis que lo motivó.
3. **Un tercero más con información de salud**, sin evaluación de impacto y bajo una política que no controlamos. Lo acota que solo viaja el informe determinista y que hoy solo circulan placas de RSNA y síntomas inventados.
4. **El silencio.** Si OpenAI falla o la revisión lo rechaza, el profesional recibe el informe y nada más. No es un riesgo clínico (el informe ya llegó), pero el [manual](manual_usuario.md#b5-el-pre-informe-el-tercer-mensaje) le dice que puede pasar.

### 6.5. El consentimiento

El bot del paciente no guarda **ni un dato** antes de que acepte, y «No acepto» no deja ninguna fila en ninguna tabla. Desde el 5-oct el consentimiento dice, en lenguaje llano: que las respuestas **pasan por Telegram**, una empresa extranjera que guarda los mensajes en sus servidores; que no se guarda su nombre ni su teléfono; que mientras contesta van unidas a su cuenta y al terminar se separan, y el identificador de la cuenta se guarda 2 días solo para evitar abusos; que se borran a los 7 días, y que si su médico usa el código, **una copia sin su cuenta se guarda hasta que termine el proyecto** (como muy tarde, el 31 de diciembre de 2026); quién las ve; que **un programa de inteligencia artificial** analiza la radiografía y calcula una probabilidad, que es una ayuda para el médico y no un diagnóstico, y que puede pedirle que le explique el resultado; y que si quiere que se borren antes, se lo diga a su médico. Desde el 18-oct (SP5-D) lleva una viñeta más, detrás de la de la inteligencia artificial, que nombra a OpenAI y dice, literalmente:

> • Para su médico, otro programa de inteligencia artificial de OpenAI, una empresa extranjera, resume el informe del sistema. Ese resumen no lleva su nombre, su cuenta ni lo que usted escriba.

Y, antes de la pregunta: «Si le cuesta respirar, le duele mucho el pecho o se siente muy mal, acuda a urgencias AHORA».

**Una limitación que el consentimiento no resuelve:** el paciente consiente ante un bot, no ante su médico, y la revocación pasa por el médico (no hay un botón de «borrar mis datos»). Es un prototipo; un uso real exigiría un procedimiento de derechos del titular.

### 6.6. Regulaciones

Ver [§14](#14-cumplimiento-normativo). En resumen: la LOPDP y la Superintendencia (SPDP) son la norma aplicable y se cumple **en parte**; no aplican el RGPD, HIPAA ni la CCPA, porque el uso previsto es en Ecuador y las únicas placas de Estados Unidos son las de RSNA, desidentificadas.

## 7. Transparencia y explicabilidad

> **Pregunta del curso:** ¿el modelo es interpretable? ¿Los usuarios entienden cómo funciona? ¿Qué técnicas de explicabilidad se implementaron?

### 7.1. ¿Es interpretable?

**La mitad, y se dice cuál.** La parte clínica es explicable: una regla publicada con cinco hallazgos y razones de verosimilitud que el profesional puede rehacer a mano. La parte de la imagen **no lo es**: una red convolucional de unos 4 millones de parámetros es una caja negra, y el profesional no ve en qué zona se apoya (R5).

### 7.2. Lo que se hizo

| Técnica | Qué da | Límite |
| :--- | :--- | :--- |
| **Razones de verosimilitud explícitas** [19] | Cada factor de la combinación se imprime (prevalencia × clínica × imagen), con la puntuación de Heckerling: el profesional ve exactamente qué cambiar si no está de acuerdo | Solo explica la combinación, no la razón de la imagen |
| **Horquilla en vez de un número** | Dice cuánto depende el resultado de un supuesto discutible (independencia) y a qué supuesto corresponde cada extremo | La verdad dentro del rango sigue sin saberse (§15) |
| **Mapa de calor (Grad-CAM)** [20] | Superpone a la placa dónde mira el modelo | **Solo en la aplicación, no en el bot**; señala dónde mira, no por qué acierta, y no marca lesiones; la advertencia va pegada al mapa |
| **Avisos de lo que la salida no dice** | «El modelo mide opacidad en la placa, no neumonía. Un resultado negativo no la descarta. Decide usted.»; un aviso específico cuando el cribado marca la placa pero la imagen resta probabilidad; «Esto no es un diagnóstico.» en todo mensaje | Un aviso se puede ignorar |
| **Fichas** [21], [22] | [`ficha_modelo.md`](ficha_modelo.md) con uso previsto, métricas por subgrupo y límites; ficha de los datos en [`ficha_datos.md`](ficha_datos.md) | Documentación, no explicación de cada salida |
| **Pre-informe en prosa** (SP5-D) | Pone el informe en lenguaje clínico corrido, rotulado como redactado por IA y revisado por código antes de enviarse | Lo escribe un LLM: **no está validado con el médico** y la revisión no detecta una frase falsa hecha de cifras y palabras permitidas |
| **Separar las escalas** | La etiqueta del cribado (umbral 0,4258) y la razón de verosimilitud (calibrada) salen de escalas distintas y se contradicen en el 9,9 % de las placas de prueba; el informe nunca las pone juntas y avisa | Exige que el profesional lea los avisos |

### 7.3. ¿Los usuarios entienden cómo funciona?

**No del todo, y la sesión con el médico lo midió.** Sobre 20 casos con el mensaje real del sistema, el médico calificó la **corrección** con 4,7 sobre 5 y la **utilidad** con 4,0, pero el **lenguaje** del informe con 2,5 (`docs/validacion-semisintetica/acta-h7.md`). Es la nota más baja de las tres, y es un hallazgo ético, no solo de estilo: un informe correcto que se entiende mal invita a leerlo por encima. SP5-D responde con un pre-informe redactado por un LLM ([§6.4](#64-lo-que-tampoco-es-nuestro-openai)), que la sesión **no midió**. Tampoco hay evidencia de que un paciente entienda el consentimiento (no se probó con pacientes). Y el derecho a una explicación existe: la LOPDP reconoce el derecho a pedir una explicación de las decisiones basadas «única o parcialmente» en valoraciones automatizadas que afecten a los derechos del titular (art. 20) [11]; aquí la decisión es del profesional, y el sistema le da los factores para explicarla.

### 7.4. Lo que falta

El mapa de calor en el bot; validar con el médico el pre-informe de SP5-D y comprobar si de verdad mejora el lenguaje; medir con usuarios si la advertencia del mapa se lee; una explicación local de la razón de la imagen más allá de Grad-CAM.

## 8. Impacto social

> **Pregunta del curso:** ¿qué impacto positivo puede tener? ¿Qué impactos negativos podrían surgir? ¿Quiénes se benefician y quiénes podrían ser perjudicados?

### 8.1. Impactos positivos

1. **Un triaje consistente; más rápido, solo en potencia.** Una probabilidad combinada con el mismo procedimiento en todos los turnos. Se beneficiarían los pacientes en espera y los profesionales con más carga. *Evidencia:* la inferencia tarda una mediana de 143 ms en el servidor de producción (`docs/sp2-despliegue.md` §7), pero eso mide al modelo, no al triaje: no dice cuánto tarda el profesional en leer el informe y decidir. **La meta de reducir el tiempo de triaje no se cumplió en la medición:** en la sesión con el médico el tiempo con el informe fue el doble (razón de medias geométricas 2,00; IC 95 % 1,57–2,49), y corregido por el efecto de releer los casos queda en 1,11 (0,69–1,81), es decir, sin evidencia de ahorro ([§15](#15-lo-que-enseñó-la-sesión-con-el-médico)).
2. **Un razonamiento explícito en lugar de un número opaco**, con razones de verosimilitud publicadas [1], [8] y una imagen acotada a [0,0163; 77,32] para que una sola placa no anule la clínica. Se benefician los profesionales, la docencia y la auditoría.
3. **Apoyo donde no hay quien lea la placa a tiempo.** Basta un teléfono con Telegram. Es un beneficio de diseño, **todavía sin medir en un centro real**.
4. **Privacidad por diseño en el tramo propio.** Contenedores propios sin puertos publicados, ninguna imagen guardada, datos seudónimos, retención corta.

### 8.2. Impactos negativos y riesgos

| # | Impacto | Quién | Severidad | Probabilidad |
| :-: | :--- | :--- | :-: | :-: |
| 1 | **Falsos negativos que retrasan el tratamiento.** El modelo no marca el 12 % de las opacidades de prueba (recall 0,88) y el 31 % en las placas PA | Pacientes ambulatorios y adultos mayores | Alta | Media (alta en PA) |
| 2 | **Sesgo de automatización.** Con prisa, el profesional puede aceptar la salida sin contrastarla [23]; el daño grave está en el negativo que tranquiliza | Pacientes en turnos sobrecargados | Alta | Media |
| 3 | **Cambio de dominio.** El modelo aprendió de placas de Estados Unidos; en otro centro el rendimiento puede caer sin aviso [5] | Todos, más los de centros con equipos distintos | Alta | Alta mientras no haya validación local |
| 4 | **Exposición de datos de salud en el canal** (Telegram, §6.3) | Pacientes | Alta | Baja a media |
| 5 | **Exclusión digital.** Hace falta Telegram, radiografía digital en DICOM y hablar español; sin el código del cuestionario, el bot del profesional no avanza | Personas mayores, zonas rurales, quien no tiene teléfono inteligente, hablantes de lenguas indígenas | Media | Media |
| 6 | **Uso fuera de alcance** (R6, [§12](#12-uso-dual-y-mal-uso)) | Cualquiera | Alta | Baja mientras sea un prototipo |

### 8.3. ¿Reduce o aumenta desigualdades?

Podría reducir una —el acceso a una lectura a tiempo donde no hay especialista— y **aumenta otras**: con el umbral único desplegado, la de resultados según la vista de la placa ([§5](#5-equidad-y-fairness)), y la de acceso digital. Quedan excluidos por diseño los menores de 18 años y, de hecho, quien no tiene acceso digital.

## 9. Registro de riesgos éticos

Del checklist del workshop se analizan los riesgos que la evidencia del proyecto respalda: justicia (R1), privacidad (R2), autonomía (R3), no maleficencia (R4) y explicabilidad (R5), más dos nuevos, el uso fuera de alcance (R6) y el texto redactado por un LLM (R7). Cuatro de ellos y la responsabilidad ([§11](#11-responsabilidad-y-rendición-de-cuentas)) están entre los seis principios de la OMS para la IA en salud [24].

| Id | Riesgo | Evidencia | Severidad | Grupo | Mitigación | Estado |
| :-: | :--- | :--- | :-: | :--- | :-: | :-: |
| **R1** | **Sesgo y *fairness*: rendimiento desigual por vista y por edad.** Con un umbral único, el modelo deja sin marcar el 31 % de las opacidades en placas PA y el 36 % en las PA de 60 años o más, frente al 6 % en las AP; con los de 60 años o más en general, el 17 % | [§4](#4-análisis-de-sesgos) y [§5](#5-equidad-y-fairness): tabla de subgrupos; atajo por la vista; mezcla de casos [5], [6], [7] | Alta | Pacientes ambulatorios (PA), sobre todo con 60 años o más | M1 | Evaluada; **desplegable, apagada** |
| **R2** | **Privacidad: datos de salud que pasan por un tercero.** Telegram recibe la placa completa, las respuestas y la cuenta; una placa de un sistema hospitalario puede traer identificadores en la cabecera. Desde SP5-D, OpenAI recibe además el informe determinista | [§6](#6-privacidad); política de Telegram [17]; salud como dato sensible [11] | Alta | Pacientes | M2 | Consentimiento **hecho**; EIPD y canal propio **pendientes** |
| **R3** | **Autonomía y supervisión humana: sesgo de automatización.** El sistema no manipula (el paciente no ve el resultado y el mensaje no prescribe nada), pero con prisa una probabilidad rotunda puede sustituir al juicio clínico | Revisión sistemática [23]; el Reglamento europeo de IA exige tenerlo presente en la supervisión humana (art. 14) [25]; un caso del corpus de pruebas —la placa real de una mujer de 28 años con opacidad anotada, con síntomas generados— en que el cribado y la evidencia **coinciden y los dos se equivocan**; y la sesión con el médico: con el mensaje delante cambió de banda en **12 de 20 casos** | Alta | Pacientes con falsos negativos; profesionales | M3 | **Parcial**; medida, no resuelta |
| **R4** | **Seguridad: qué pasa si el modelo falla.** Los fallos peligrosos son los silenciosos: un modelo que, ante placas distintas, sigue respondiendo con aplomo | Cambio de dominio sin validar en Ecuador [5]; la combinación solo se validó en simulación semisintética, porque ningún conjunto público trae la auscultación junto a la placa | Alta | Todos los pacientes | M4 | Fallos visibles, **hecho**; validación local, **fuera de alcance** |
| **R5** | **Transparencia: la imagen es una caja negra.** La parte clínica se explica; la de la imagen no | Mapa de calor solo en la aplicación; ley ecuatoriana: derecho a una explicación (art. 20) [11]; el médico calificó el lenguaje con 2,5/5 | Media | Profesionales y, por ellos, pacientes | M5 | **Hecho** (mapa de calor y fichas); lenguaje, pendiente |
| **R6** | **Uso fuera de alcance o indebido** (nuevo): usar la demostración o los pesos para decidir sobre un paciente, para cribado sin lectura humana o para fines ajenos a la atención | [§12](#12-uso-dual-y-mal-uso) | Alta | Cualquiera | M7 | **Parcial**: avisos y barreras técnicas; los pesos publicados llevan una licencia (CC BY-NC 4.0), pero ningún control técnico de su uso |
| **R7** | **Un texto redactado por un LLM que parezca más fiable de lo que es** (nuevo, SP5-D): una frase plausible pero equivocada que pase la revisión por código (una cifra del informe en otro papel, como la sensibilidad 0,88 presentada como una probabilidad; una cifra escrita con letras; la etiqueta del cribado invertida), o que influya al médico más que el informe; y un tercero más que recibe información de salud | [§6.4](#64-lo-que-tampoco-es-nuestro-openai); el LLM redacta, no calcula, y se revisa contra el informe; la sesión con el médico midió el informe, no el pre-informe; la cabecera («vale el informe de arriba») y que el informe llegue antes absorben lo que la revisión no ve | Media | Pacientes con falsos negativos; profesionales | M8 | **Parcial**: revisión y rotulado **hechos**; validación con el médico y evaluación de impacto **pendientes** |

## 10. Mitigaciones y su estado

Estado a 18-oct-2026. «Hecho» significa implementado y verificado por pruebas automáticas o por una medición citada; «Pendiente» significa que **no está hecho**.

| Id | Para | Estrategia | Tipo | Pasos y estado | Responsable | Efectividad esperada |
| :-: | :-: | :--- | :--- | :--- | :--- | :--- |
| **M1** | R1 | Umbral por vista (igualdad de oportunidad) y auditoría por subgrupos | Técnica | 1. Puntuar la validación con el modelo desplegado: **hecho**. 2. Elegir los umbrales en validación y evaluarlos en prueba sin mirarla al elegir: **hecho** (tabla de §5.4). 3. Umbral por vista en el servidor y la aplicación, apagado por defecto: **hecho el 6-oct**; encenderlo, decisión de la institución. Las métricas por subgrupo, en el reporte de entrenamiento: **pendiente** (hoy se calculan desde las puntuaciones congeladas con `app/generar_metricas.py`) | Lead AI Engineer | Alta en el recall por vista, con un precio en especificidad |
| **M2** | R2 | Minimización y transparencia en el canal | Política y diseño | 1. Reescribir el consentimiento: **hecho (5-oct)**, y ampliado el 18-oct para nombrar a OpenAI (SP5-D); que el profesional envíe la placa exportada sin identificadores: **pendiente** (protocolo de la institución). **Hoy es solo una política, sin control técnico**: la placa llega a Telegram antes que al sistema, así que nada de lo nuestro puede impedir que viaje con identificadores. Los controles técnicos posibles son anonimizar en el origen (la exportación del PACS) y que el servidor rechace las placas con nombre o identificador del paciente en la cabecera, para no procesarlas y que el profesional no repita el envío; **no se implementaron** en este proyecto. 2. Evaluación de impacto, que aclare si Telegram y OpenAI son encargados o destinatarios de una transferencia internacional, con el delegado de la institución: **pendiente**. 3. Sustituir Telegram por una carga web propia sobre `POST /inferir`: **no se hará en este proyecto** | Product Owner, con el delegado de la institución | Alta con el paso 3; media sin él |
| **M3** | R3 | Diseño contra el sesgo de automatización | Diseño y educación | 1. Mantener los avisos (horquilla, bloques separados, «Esto no es un diagnóstico», aviso asimétrico en los negativos): **hecho**, fijado por pruebas. 2. Guía de una página para el profesional: **hecha** en el [manual](manual_usuario.md#3-parte-b-los-bots-de-telegram); la instrucción de anotar en la historia clínica el código de cada consulta, **pendiente** de adopción por una institución. 3. Medir cuántas veces el médico cambia de banda al ver el mensaje: **hecho** (12 de 20; [§15](#15-lo-que-enseñó-la-sesión-con-el-médico)) | Product Owner | Media; **la medición no muestra que el diseño evite la influencia** |
| **M4** | R4 | Fallar de forma segura y validar en local | Técnica y política | 1. Códigos de rechazo fijados por pruebas, también para las placas que el modelo vería mal (16 bits, invertidas, en color, desmedidas): **hecho y desplegado el 6-oct**. 2. Vigilancia diaria con avisos: **hecho**. 3. Validación local con datos emparejados antes de cualquier uso clínico: **fuera del alcance de la maestría** | Equipo; la institución en el paso 3 | Alta ante fallos visibles; media ante el cambio de dominio |
| **M5** | R5 | Explicabilidad y documentación | Técnica y educación | 1. Mapa de calor Grad-CAM con su advertencia: **hecho el 6-oct, en la aplicación y no en el bot**. 2. Ficha del modelo y ficha de los datos publicadas en el repositorio: **hechas** con esta entrega | Lead AI Engineer | Media |
| **M6** | Exclusión digital | Cuestionario asistido | Política y diseño | 1. Protocolo para que el personal rellene el cuestionario con el paciente, leyéndole el consentimiento: **pendiente**. 2. Eximir a las cuentas del centro del límite de 5 cuestionarios diarios: **pendiente**. 3. Contar cuántos pacientes lo necesitan: **pendiente** | La institución, con el Product Owner | Media |
| **M7** *(nueva)* | R6 | Límites de uso escritos y barreras técnicas | Diseño y documentación | 1. Avisos en la aplicación («No es un producto sanitario…») y en el bot: **hecho**. 2. Rechazo de lo que el modelo no puede evaluar: **hecho**. 3. Lista blanca y `secret_token` en el bot: **hecho**. 4. Uso previsto y usos fuera de alcance en la ficha del modelo: **hecho**. 5. Control técnico del uso de los pesos publicados: **no existe**; solo su licencia (CC BY-NC 4.0: atribución y sin fines comerciales), que es una condición legal y no impide ni vigila su uso con pacientes | Equipo | Media |
| **M8** *(nueva)* | R7 | El LLM solo redacta, se comprueba y se rotula | Técnica y diseño | 1. El LLM lee solo el informe determinista, sin texto del paciente ni identificadores: **hecho** (SP5-D). 2. Revisión por código antes de enviar (cifras que estén en el informe, palabras de tratamiento y diagnóstico vedadas, longitud) y silencio si no pasa: **hecho**. 3. Cabecera en la posición 0 que lo rotula y manda el informe de arriba; el informe llega primero y no espera al LLM: **hecho**. 4. El consentimiento nombra a OpenAI: **hecho** (SP5-D). 5. Validarlo con un médico: **pendiente** (no se hizo antes de la entrega). 6. Evaluación de impacto que cubra a OpenAI: **pendiente** | Equipo; la institución en los pasos 5 y 6 | Media: acota el error visible, no la frase verosímil pero falsa |

## 11. Responsabilidad y rendición de cuentas

> **Pregunta del curso:** ¿quién es responsable si el modelo falla? ¿Qué mecanismos de accountability existen? ¿Cuál es el plan de monitoreo y actualización?

### 11.1. Quién responde de qué

| Rol | Responsabilidades | Cómo rinde cuentas |
| :--- | :--- | :--- |
| **Equipo de desarrollo** | Implementación técnica correcta y segura | Más de 1 100 pruebas automáticas en Python y las de los flujos de n8n; revisión independiente de cada tarea y de cada rama; decisiones registradas en especificaciones |
| **Lead AI Engineer** | Calidad de los datos, el modelo, la calibración y el sesgo | Métricas por subgrupo en cada reentrenamiento; ficha del modelo |
| **Product Owner** | Decisiones de diseño y de alcance | Especificaciones con las decisiones y los riesgos declarados; compromisos documentados |
| **Institución de salud** (si lo adoptara) | Gobernanza, protocolo clínico, protección de datos y recursos | Política de uso, evaluación de impacto, supervisión y registro sanitario |
| **Profesional clínico** | La decisión clínica | La registra en la historia clínica: el sistema solo informa |

**Si el modelo falla** y un paciente sufre un daño, la responsabilidad clínica es de quien decidió: el profesional y el servicio de salud, que son corresponsables civilmente de la atención y cuyo deber no se extingue por el consentimiento del paciente (Ley Orgánica de Salud, arts. 201–204) [26]. Eso no exime a quien desarrolla el sistema de su responsabilidad técnica por sesgos o fallos que debió detectar, y es la razón por la que este documento los declara. **Hoy esa cadena es hipotética**: no hay una institución, ni un paciente real, y el sistema no se ha usado clínicamente.

### 11.2. Mecanismos de *accountability* (estado)

| Área | Mecanismo | Estado | Cómo |
| :--- | :--- | :-: | :--- |
| Documentación | Ficha del modelo | **Hecho** | [`ficha_modelo.md`](ficha_modelo.md) |
| Documentación | Ficha del conjunto de datos | **Hecho** | [`ficha_datos.md`](ficha_datos.md) |
| Documentación | Declaración ética con análisis de riesgos | **Hecho** | Este documento |
| Supervisión | Revisión humana en decisiones críticas | **Hecho** | El profesional decide siempre; el paciente no recibe el resultado |
| Supervisión | Revisión y rotulado de lo que redacta el LLM | **Hecho** (código); validación con el médico, **pendiente** | Revisión por código antes de enviar, silencio si no pasa y cabecera en la posición 0 (M8) |
| Supervisión | Proceso de apelación | Propuesto | El paciente pide, por el profesional o la institución, la explicación del art. 20 y la revisión de su caso; el equipo revisa con el registro |
| Supervisión | Auditoría periódica | Parcial | Registro de cada consulta, sin imagen; revisión mensual en un piloto |
| Monitoreo | Métricas de fairness | Parcial | Por subgrupo en la aplicación (M1); no en operación |
| Monitoreo | Alertas por deriva | Propuesto | Distribución semanal de puntuaciones y de vistas |
| Monitoreo | Reporte de incidentes | Parcial | Avisos técnicos automáticos, sí; reporte de casos por los profesionales, propuesto |
| Transparencia | Uso de IA y limitaciones comunicados | **Hecho** | Al profesional, descargo y avisos; al paciente, el consentimiento que nombra la IA, a OpenAI y a Telegram |
| Transparencia | Explicación de cada salida | Parcial | Razones de verosimilitud; mapa de calor, solo en la aplicación |
| Trazabilidad | Qué versión del modelo atendió una consulta | **Pendiente** | `consultas` guarda el modelo, el umbral y el AUC, **pero no la huella de los pesos ni el commit**: una consulta antigua no dice por sí sola qué versión la atendió |

### 11.3. Plan de monitoreo y actualización del modelo

**Qué se vigila hoy** (SP3 §16): a diario, que el servicio de inferencia y la base respondan, que los tres workflows estén activos, que los cuestionarios caducados se hayan borrado, que el webhook de cada bot siga apuntando donde debe, y que los rechazos por DICOM ilegible no lleguen a 3 en 7 días con más del 20 % de las placas de esa ventana. Avisan por Telegram al equipo.

**Qué falta vigilar en un uso real:** la distribución semanal de puntuaciones y de vistas (alerta por deriva), y la proporción de positivos y de placas AP; un cambio brusco es la señal de un cambio de equipo o de población.

**Cuándo se actualiza el modelo:** reentrenamiento anual o ante un cambio de equipo (plan de mantenimiento, SP5 §6.2). En cada reentrenamiento: **medir de nuevo el rendimiento por sexo, edad y vista, y sus cruces**; reajustar el calibrador y reelegir el umbral, porque las cotas de la razón de verosimilitud (0,0163 y 77,32) y la banda contradictoria cambian con el calibrador; y reescribir la ficha del modelo.

### 11.4. Plan de respuesta a incidentes

1. **Detección.** Vigilancia diaria con avisos; reportes de los profesionales; y el registro de consultas, por ejemplo ante un cambio brusco en la proporción de positivos o de placas AP.
2. **Respuesta inmediata.** Detener el servicio de inferencia (el bot responde con un error, nunca con una probabilidad) o desactivar el flujo, y avisar a los profesionales.
3. **Investigación.** Cada consulta guarda síntomas, signos, resultado —con el modelo, su umbral y su AUC—, error y tiempo, pero no la imagen: el caso se reproduce si la institución reenvía la placa, con el modelo del *commit* desplegado, que se apunta en cada despliegue; guardar también la huella de los pesos evitaría depender de esa nota.
4. **Corrección.** El profesional anota el código de cada consulta en la historia clínica: así la institución localiza las del periodo afectado y vuelve a citar a los pacientes con un negativo; después, corregir y volver a validar antes de reactivar.
5. **Prevención.** Una prueba automática que reproduzca el caso, y el hallazgo en la ficha del modelo.

## 12. Uso dual y mal uso

> **Pregunta del curso:** ¿podría el modelo usarse con fines maliciosos? ¿Qué salvaguardas se han implementado? ¿Las limitaciones de uso están documentadas?

**¿Podría usarse con fines maliciosos?** La tecnología no tiene un uso dual evidente: es un clasificador de opacidades en radiografías de tórax. El riesgo realista no es la malicia sino **el mal uso**: usar el sistema donde no corresponde, o para algo que no es atender al paciente. Los escenarios que se consideraron:

| Escenario | Por qué preocupa | Salvaguarda | Riesgo residual |
| :--- | :--- | :--- | :--- |
| **Decidir sobre un paciente real con la demostración** | La aplicación no pide contraseña y da un resultado de apariencia clínica | Aviso fijo en la cabecera («Demostración académica. No es un producto sanitario: no la use para decidir sobre un paciente»), «Esto no es un diagnóstico» en cada resultado, y puerto publicado solo en `127.0.0.1` | Medio: un aviso no impide el uso |
| **Cribado sin lectura humana** (leer placas en masa sin un profesional) | El sistema pierde una de cada ocho opacidades en prueba y una de cada tres en PA | El diseño entrega el resultado solo a un profesional dado de alta; el paciente no lo recibe; todos los avisos asumen una persona que decide | Bajo en el sistema; **alto** si alguien reutiliza los pesos fuera |
| **Usar el resultado para discriminar** (cobertura de seguros, selección de personal, trámites migratorios) | La Constitución prohíbe discriminar por estado de salud [27]; el sistema no se diseñó para eso y no está validado para ello | Ninguna técnica; solo la declaración de uso previsto y fuera de alcance en la ficha del modelo | Medio: depende de quién tenga los pesos |
| **Falsificar entradas al bot** (updates forjados, intrusos) | Hacerse pasar por Telegram o por un profesional | `secret_token`, lista blanca por mensaje, mensaje de rechazo sin pistas, límite diario | Bajo |
| **Inyectar texto en el informe** (el paciente escribe algo que parezca del sistema) | Un falso «CRIBADO — opacidad probable» pegado al descargo engañaría al clínico. Se reprodujo con 240 caracteres sobre una placa de puntuación 0,0047 | El informe **no contiene ningún carácter escrito por el paciente**; su texto va en un mensaje aparte. La regla no nombra caracteres, así que no depende del próximo homoglifo | Bajo |
| **Inyectar instrucciones al LLM** (el paciente escribe algo dirigido al modelo de lenguaje, como pedirle que diga que no hay neumonía) | Si el texto del paciente llegara al LLM, podría desviar lo que el médico lee | El LLM no recibe el texto del paciente: solo el informe determinista, que no contiene ni un carácter escrito por él | Bajo |
| **Un DICOM construido para agotar recursos** | Unos 600 bytes que declaran 60 000 × 60 000 píxeles reservaban 3,4 GiB | Rechazo por cabecera antes de descodificar; límite de 5 MB; 2 GB del contenedor | Bajo |
| **Imágenes adversarias** (entradas diseñadas para forzar una salida) | Es una vulnerabilidad conocida de las redes convolucionales | **No se evaluó la robustez adversaria**; el profesional que decide es la única barrera | Desconocido |
| **Uso con menores, con otras proyecciones o con otras modalidades** | El modelo no se validó con ellos | Rechazo por edad (18–100) y por formato; la vista PA/AP solo cambia el umbral si se enciende | Bajo para edad; **sin barrera** para lateral o para otro equipo de captura |
| **Reutilizar los pesos publicados** | Los pesos se publican como descarga del repositorio con licencia CC BY-NC 4.0 (el código es MIT): la licencia exige atribuir y excluye los fines comerciales, pero **no impide ni vigila** su uso con pacientes | La ficha del modelo declara el uso previsto y los usos fuera de alcance; el repositorio los repite | **Medio, y sin control técnico**: es el límite de cualquier modelo abierto |

**Limitaciones de uso documentadas** en este documento, en la [ficha del modelo](ficha_modelo.md), en el README, en la pestaña «Acerca de» de la aplicación y en cada mensaje del bot.

## 13. Limitaciones reconocidas: cuándo no usarlo

> **Pregunta del curso:** ¿en qué casos no debe usarse el modelo? ¿Qué advertencias deben darse? ¿Dónde no es confiable?

### 13.1. Casos en que NO debe usarse

| No usarlo… | Porque… | ¿Hay una barrera técnica? |
| :--- | :--- | :-: |
| …para decidir sobre un paciente real, hoy | Es un prototipo sin validación local, sin registro sanitario y sin evaluación de impacto | No: solo los avisos |
| …en menores de 18 años ni mayores de 100 | No se entrenó ni se validó con ellos; la neumonía infantil se ve distinta | **Sí**: `fuera_de_alcance` |
| …sin edad legible en la cabecera | No se asume adulto a quien no declara edad | **Sí**: `edad_desconocida` |
| …con placas de más de 8 bits, invertidas, en color, de varios cuadros, comprimidas con una sintaxis sin descodificador, recortadas o de más de 5 000 píxeles de lado | El modelo las vería mal: una neumonía en 16 bits baja de 0,91 a 0,48 | **Sí**: `dicom_invalido` |
| …como único criterio, o para descartar neumonía | Un resultado negativo no la descarta: pierde una de cada ocho opacidades (una de cada tres en PA) y mide opacidad, no neumonía | No: el aviso lo dice |
| …como diagnóstico | La etiqueta es opacidad compatible, no neumonía | No: «Esto no es un diagnóstico» |
| …con una radiografía lateral, de un equipo que no sea de radiografía computarizada, o de un centro distinto sin validar | El rendimiento no está medido; todas las placas de entrenamiento son frontales de modalidad CR de un conjunto de Estados Unidos | No: el modelo no comprueba la vista; solo con el umbral por vista encendido, una vista distinta de PA/AP usa el umbral global |
| …con los datos de la demostración como si fueran de pacientes | Los ejemplos son de otra fuente y el modelo no se ha medido con ellos | No: un aviso en la pantalla |
| …sin un profesional que lea y decida | Todo el diseño supone una persona | **Sí** en el bot (lista blanca); no en la aplicación |

### 13.2. Las advertencias que da el sistema

Son literales de los mensajes del bot y de la aplicación:

- «Esto no es un diagnóstico.» (todo informe).
- «⚠️ El modelo mide opacidad en la placa, no neumonía. Un resultado negativo no la descarta. Decide usted.» (todo resultado negativo).
- «⚠️ El cribado marca esta placa por estar orientado a detectar, pero la imagen en sí no apoya el diagnóstico. Decide la clínica.» (positivo con razón de verosimilitud menor que 1).
- «⚠️ La auscultación y la imagen miran la misma consolidación, así que no son pruebas independientes…» y su variante para evidencias opuestas (toda combinación).
- «NO PROCEDE — fuera del alcance del modelo.», sin ninguna cifra de probabilidad (rechazo por edad).
- «PRE-INFORME — redactado por IA (OpenAI) a partir del informe de arriba. Si algo no coincide, vale el informe de arriba. No es un diagnóstico.» (cabecera de todo pre-informe).
- «Demostración académica. No es un producto sanitario…» (cabecera de la aplicación); y el aviso del mapa de calor.
- Al paciente: «Si le cuesta respirar, le duele mucho el pecho o se siente muy mal, acuda a urgencias AHORA» (consentimiento y despedida).

### 13.3. Casos límite donde el modelo no es confiable

- **La banda contradictoria.** Con la puntuación cruda entre 0,4258 y 0,5786, el cribado marca la placa y la imagen resta probabilidad. Son 379 de 3 811 placas de prueba (9,9 %) y el 23,3 % de lo que el cribado etiqueta como positivo; el 80,5 % de ellas no tenía opacidad. El aviso se dispara una de cada cuatro veces que hay un positivo: es comportamiento habitual, no un caso raro.
- **Falsos positivos en placas AP:** especificidad 0,39; alrededor de seis de cada diez placas AP sin opacidad salen marcadas.
- **Falsos negativos en placas PA y en mayores:** recall 0,69 y, en PA con 60 años o más, 0,64.
- **Positivos y negativos en que el cribado y la evidencia coinciden y los dos se equivocan.** No hay forma de saberlo: el sistema no puede saber que está fallando. Lo único honesto es decir que un negativo no descarta.
- **Con el asma sin saber**, el resultado es un rango, y su ancho dice si esa pregunta importa en el caso concreto.
- **Dependencia entre clínica e imagen.** La independencia exagera, y la horquilla no contiene la verdad simulada en las celdas con dependencia: la cifra combinada es **orientativa** ([§15](#15-lo-que-enseñó-la-sesión-con-el-médico)).
- **Imágenes de otra fuente** (los ejemplos de la aplicación): con los pesos de esta entrega, la placa «normal» sale marcada por el cribado, y la propia página avisa de que la imagen no apoya ese resultado.

## 14. Cumplimiento normativo

Es una lectura del equipo, **no asesoría legal**: un uso real la necesitaría. Las normas se leyeron en su fuente oficial el 5-oct-2026; lo que no se pudo verificar está marcado.

| Regulación | Qué requiere | ¿Cumple hoy? | Qué cambiaría |
| :--- | :--- | :--- | :--- |
| **Protección de datos: LOPDP, su Reglamento y la SPDP** [11], [12], [28], [29] | Dato de salud = sensible y, para la SPDP, de gran escala: consentimiento explícito (art. 26), salvo la asistencia del art. 31; informar de fines, transferencias, plazo de conservación (art. 12) y del uso de IA; derecho a una explicación (art. 20); evaluación de impacto previa (art. 42) y delegado (art. 48) | **Parcial.** Consentimiento previo que nombra a Telegram, la IA, el plazo real y el derecho a una explicación (5-oct) y, desde el 18-oct, a OpenAI. **Falta** la evaluación de impacto, el delegado y el registro de actividades | M2, antes de cualquier dato real |
| Norma de la SPDP sobre IA (Res. SPDP-SPD-2026-0009-R) [29] | Informar del carácter automatizado; gestión de riesgos y evaluación de impacto antes de desarrollar el sistema; registro de actividades; auditoría | **Parcial**: informa del carácter automatizado en el consentimiento; sin evaluación de impacto ni registro | M2 |
| Transferencias internacionales (Res. SPDP-SPD-2026-0004-R) [18] | Garantías adecuadas o una excepción, e inscripción, si los datos pasan a un tercero extranjero | **Sin determinar** si Telegram y, desde SP5-D, OpenAI son encargados o destinatarios: lo debe aclarar la evaluación de impacto | M2 |
| **ARCSA, dispositivos médicos** [30], [31] | El software de diagnóstico es dispositivo médico: registro sanitario, salvo los fines de investigación sin comercialización; desde 2027, clasificación por la matriz IMDRF y, en riesgo III o IV, evaluación clínica | **Sí: investigación, exento** | Registro antes de un uso clínico |
| **Norma Técnica de Telesalud** [32] | El Comité de Bioética evalúa cada herramienta con IA (seguridad, datos, sensibilidad, especificidad, confiabilidad) y el establecimiento la aprueba | Aún no aplica | Llevarle la ficha del modelo y este análisis |
| **Ley Orgánica de Salud** [26] y **AM 5216** [13] | Confidencialidad de la información clínica (art. 7); la imagen es de uso restringido; en una comunicación electrónica no van datos identificativos (arts. 18 y 25) | **Riesgo**: la cabecera DICOM puede llevar el nombre a Telegram | Placa sin identificadores, o canal propio (M2) |
| **Constitución, arts. 11.2 y 32** [27] | No discriminar por edad, sexo o estado de salud, tampoco como resultado; equidad en la atención de salud | **Riesgo**: las brechas del [§5](#5-equidad-y-fairness) | M1 |
| **Reglamento de IA de la UE**, como referencia [25], [33], [34] | Un producto sanitario como este sería probablemente de clase IIa o superior: alto riesgo, con gestión de riesgos, datos examinados por sesgo y propios del lugar de uso, registros y supervisión humana (arts. 9–15), desde 2028 | **Parcial**: faltan datos locales y documentación técnica | M1, M4 y M5 |

**No aplican** el RGPD, HIPAA ni la CCPA —el uso previsto es en Ecuador y las únicas placas de Estados Unidos son las de RSNA, desidentificadas—, ni leyes laborales: el sistema no decide sobre el empleo de nadie.

**Lo que no se pudo verificar** (`investigacion.md` de la Semana 4): la tabla de categorías IMDRF/N12; si existe una lista de países con nivel adecuado fuera del régimen andino; dónde guarda Telegram los datos de usuarios ecuatorianos y con qué calificación jurídica, y lo mismo para OpenAI, de quien solo se recoge lo que declara su política (§6.4); la fecha de publicación de la reforma Res. SPDP-SPD-2026-0037-R; y el texto consolidado de 2026 de la Ley Orgánica de Salud (se usó la compilación de 2012).

**Condiciones de los datos.** RSNA permite el uso de las placas desidentificadas y de sus anotaciones con dos condiciones: no intentar identificar ni contactar a los sujetos, y atribuir al compartir [15]. Las reglas de Kaggle conservan una cláusula que prohíbe redistribuir los datos a quien no participó en la competición [16]; por eso este repositorio **no redistribuye datos**, solo referencias, agregados y guiones.

## 15. Lo que enseñó la sesión con el médico

> **Qué es.** Una sesión de concordancia con **un** médico general colaborador, voluntario, sobre **24 viñetas semisintéticas** (placa real del conjunto de prueba, clínica generada). Dos lecturas del mismo conjunto, el 10 y el 15 de octubre, **5 días** de intervalo en vez de los 7 o más del diseño. El kappa sale solo de la primera lectura, sin el sistema delante. Mide acuerdo con un evaluador, **no exactitud clínica**. (`docs/validacion-semisintetica/acta-h7.md`)

| Medida | Resultado | Lectura |
| :--- | :--- | :--- |
| **Kappa ponderado lineal (primario)** | **0,25** (IC 95 % analítico 0,07–0,44; BCa 0,11–0,49; n = 24) | **No alcanza el mínimo de 0,4** de la Semana 1; el límite inferior queda por debajo de 0,4 con los dos métodos. El 0,6 queda fuera del intervalo |
| Kappa de Cohen sin ponderar | 0,10 (−0,09–0,30) | No alcanza 0,4 |
| Kappa binario en «alta» | 0,29 (0,03–0,55) | No alcanza 0,4 |
| Porcentaje del médico dentro de la horquilla del sistema | **0 de 24** casos (diferencia media en log-odds, médico − sistema, 2,82); correlación de Spearman 0,62 | Ordenan los casos de forma parecida, pero el médico asigna en promedio bastante más probabilidad que el sistema |
| **Influencia del sistema** (kappa con el mensaje delante) | 0,81 (0,61–1,00; n = 20); **cambió de banda en 12 de 20 casos** | No es concordancia independiente: es cuánto se movió el médico hacia el sistema |
| Utilidad del informe (1–5) | Corrección **4,7**; utilidad **4,0**; lenguaje **2,5** (n = 20) | El lenguaje es el punto débil, y es lo que motivó el pre-informe de SP5-D, que esta sesión no midió |
| Tiempo de triaje | Razón con/sin copiloto **2,00** (IC 95 % BCa 1,57–2,49); corregida por releer, **1,11** (0,69–1,81) | No hay evidencia de ahorro de tiempo |

**Qué significa, éticamente:**

1. **El criterio de concordancia no se cumplió y se publica tal cual.** El kappa 0,25 es bajo, y el diseño no distingue una concordancia moderada de una sustancial ni generaliza a otros médicos. El criterio se evalúa sobre la estimación puntual y se publica siempre con su intervalo; no se reinterpretó para que cuadrara.
2. **El riesgo R3 dejó de ser teórico.** Con el mensaje delante, el médico cambió de banda en 12 de 20 casos y el kappa sube a 0,81: el sistema **influye mucho**. Eso puede ser beneficioso (si el sistema acierta) o dañino (si se equivoca), y esta sesión **no puede decir cuál**. Es precisamente la forma que toma el sesgo de automatización [23], y por eso la horquilla y los avisos son parte del diseño y no adorno. Hubo además un efecto de releer: 3 de los 4 controles, sin mensaje, también cambiaron de banda. Al cerrar el acta, el médico discrepó de esta lectura y no dio su conformidad: atribuye sus cambios a «cotejar los síntomas, las imágenes y el análisis de la IA», es decir, a integrar información nueva ([acta](validacion-semisintetica/acta-h7.md#conformidad)). Las dos lecturas son compatibles con los mismos datos, y esta sesión no las distingue.
3. **La promesa de ahorrar tiempo no se sostuvo en esta medición.** El informe añade lectura; sin evidencia de que ahorre tiempo, el beneficio argumentable es la consistencia, no la rapidez.
4. **El lenguaje importa.** Un informe correcto (4,7) y útil (4,0) que se entiende mal (2,5) es un riesgo de transparencia. SP5-D respondió añadiendo un pre-informe redactado por un LLM; no se validó con el médico, así que no sabemos si el lenguaje mejoró.
5. **Lo que la sesión no es.** Un solo evaluador, 24 casos elegidos por estratos a propósito (positivas claras, negativas claras, banda contradictoria, asma «no sé»), una clínica generada y no real, y videollamada con un tiempo que incluye el tecleo de quien marcaba. No generaliza.

Lo que el equipo cambiaría a la vista de estos resultados —no imprimir cifras extremas, un diseño que separe el arrastre del sistema del efecto de releer, medir el tiempo con el pre-informe y preguntar antes cómo llega la placa al médico— está en la [lectura crítica de H7](validacion-semisintetica/lectura-critica-h7.md).

**La simulación semisintética** (3 811 placas reales de prueba y una clínica sorteada con la distribución publicada de la regla; `docs/validacion-semisintetica-sp5.md`) refuerza esto. Comprueba que el sistema **calcula lo que dice calcular** (con dependencia nula, el sistema reproduce caso a caso la posterior del generador). Pero con dependencia entre clínica e imagen, la independencia **exagera** (pendiente menor que 1 en las seis celdas destacadas) y la hipótesis declarada de antemano —que la verdad cae dentro de la horquilla en al menos el 90 % de los casos concordantes— **no se sostiene en ninguna de las seis**. Nada de eso mide exactitud clínica. La conclusión práctica es la que el sistema ya dice en cada informe: la cifra combinada es **orientativa**.

## 16. Reflexión y compromiso del equipo

### 16.1. Reflexión

**El dilema más difícil: un umbral para todos o uno por grupo.** El umbral único cumple los mínimos en promedio escondiendo el fallo en PA detrás del acierto en AP, y no existe un umbral que dé a la vez el mismo recall en las dos vistas, un recall de 0,88 y la especificidad mínima de 0,70. Chocan la beneficencia (detectar más neumonías), la no maleficencia (no llenar el triaje de pruebas y antibióticos innecesarios) y la justicia (que el riesgo no dependa de si el paciente puede ponerse de pie). Lo resolveríamos por la igualdad de oportunidad con el recall actual: por justicia, porque el total de falsos negativos apenas cambia (de 100 a 94) pero deja de recaer en el paciente ambulatorio; y con 0,88 y no 0,80, porque en neumonía un falso negativo hace más daño que un falso positivo. El precio, que no se esconde, es la especificidad global (0,70 → 0,62). **Por eso lo dejamos apagado y decide la institución, con estas cifras delante.**

**Lo que no habíamos considerado.** Que las métricas globales escondieran el sesgo. Tanto, que en la Semana 1 dejamos fuera del alcance la auditoría de sesgo por sexo y edad; el análisis exploratorio de la Semana 2 anunció el confusor de la vista, y solo al partir por subgrupos apareció el 0,69 de las placas PA. Y que una sesión con un médico pudiera enseñarnos tanto de lo que **no** funcionó (el kappa, el tiempo, el lenguaje) como de lo que sí.

**Lo que cambiaríamos en el diseño.** La auditoría por subgrupos dentro del alcance desde el principio; el umbral y la calibración por vista; un consentimiento que diga todo lo que M2 enumera desde la primera versión; el mapa de calor también en el bot; y ningún uso clínico sin validación local.

### 16.2. Compromiso ético

Como creadores de este sistema de IA, nos comprometemos a lo siguiente, con su estado:

| Compromiso | Estado |
| :--- | :--- |
| Reportar el recall y la especificidad por sexo, edad y vista —y sus cruces— en cada reentrenamiento, y no presentar como válido un modelo cuyo recall caiga por debajo de 0,85 en un subgrupo sin decirlo | **Cumplido para el modelo actual**: la tabla de §5 lo reporta, y el recall de 0,69 en PA se dice abiertamente. Pendiente: incluirlo en el reporte de entrenamiento |
| No usar el sistema con pacientes reales sin validación local, sin evaluación de impacto de protección de datos y sin un consentimiento que nombre a Telegram, a OpenAI, la IA y el plazo real de conservación | **Cumplido**: no se ha usado con pacientes reales; el consentimiento ya los nombra; faltan la validación local y la evaluación de impacto, que son condiciones, no hechos |
| Mantener en cada resultado negativo el aviso de que no descarta la neumonía y de que la decisión es del profesional | **Cumplido**, fijado por pruebas automáticas |
| Actuar con responsabilidad si se identifican daños | Plan de respuesta a incidentes escrito ([§11.4](#114-plan-de-respuesta-a-incidentes)); nunca puesto a prueba con un daño real |
| Priorizar el bienestar de los usuarios y de los grupos vulnerables | M1 evaluada y apagada por defecto por su precio; M6 pendiente |
| Mantener la transparencia sobre las limitaciones del sistema | **Cumplido**: este documento, la ficha del modelo, y los resultados desfavorables de la sesión con el médico, publicados |

## 17. Lo que falta antes de cualquier uso clínico

Esta lista no es un deseo: son las condiciones que este análisis pone antes de que el sistema toque a un paciente.

1. **Validación local con datos emparejados** (imagen y clínica reales, con auscultación) de un centro ecuatoriano, medida por subgrupo. Hoy no hay datos públicos que emparejen la auscultación con la placa; MIMIC es una vía futura.
2. **Evaluación de impacto de protección de datos** y delegado de protección de datos de la institución, que aclare el papel de Telegram y de OpenAI.
3. **Evaluación del Comité de Bioética** y aprobación del establecimiento (Norma Técnica de Telesalud), con este análisis y la ficha del modelo.
4. **Registro sanitario** ante ARCSA si el uso deja de ser de investigación.
5. **Un canal que no pase por un tercero** (carga web propia sobre `POST /inferir`) o, como mínimo, una placa exportada sin identificadores.
6. **Decidir con la institución** si se enciende el umbral por vista, con la tabla de §5.4 delante.
7. **Protocolo de cuestionario asistido** y exención del límite diario para las cuentas del centro (M6).
8. **Guardar la huella de los pesos** en cada consulta, y un reporte de incidentes por los profesionales.
9. **Validar con el médico el pre-informe** de SP5-D, que busca mejorar el lenguaje del informe (2,5 sobre 5), y medir con usuarios si se entiende. Mientras no se haga, el pre-informe es una función sin validar.
10. **Medir la robustez** ante imágenes adversarias y ante otros equipos de captura.

---

## Referencias

[1] P. S. Heckerling *et al.*, «Clinical prediction rule for pulmonary infiltrates», *Ann. Intern. Med.*, vol. 113, n.º 9, pp. 664–670, nov. 1990, doi: 10.7326/0003-4819-113-9-664.

[2] M. H. Ebell, H. Chupp, X. Cai, M. Bentivegna y M. Kearney, «Accuracy of signs and symptoms for the diagnosis of community-acquired pneumonia: a meta-analysis», *Acad. Emerg. Med.*, vol. 27, n.º 7, pp. 541–553, jul. 2020, doi: 10.1111/acem.13965.

[3] G. Shih *et al.*, «Augmenting the National Institutes of Health chest radiograph dataset with expert annotations of possible pneumonia», *Radiol. Artif. Intell.*, vol. 1, n.º 1, art. e180041, ene. 2019, doi: 10.1148/ryai.2019180041.

[4] X. Wang, Y. Peng, L. Lu, Z. Lu, M. Bagheri y R. M. Summers, «ChestX-ray8: hospital-scale chest X-ray database and benchmarks on weakly-supervised classification and localization of common thorax diseases», en *Proc. IEEE Conf. Comput. Vis. Pattern Recognit. (CVPR)*, 2017, pp. 3462–3471, doi: 10.1109/CVPR.2017.369.

[5] J. R. Zech, M. A. Badgeley, M. Liu, A. B. Costa, J. J. Titano y E. K. Oermann, «Variable generalization performance of a deep learning model to detect pneumonia in chest radiographs: a cross-sectional study», *PLOS Med.*, vol. 15, n.º 11, art. e1002683, nov. 2018, doi: 10.1371/journal.pmed.1002683.

[6] A. J. DeGrave, J. D. Janizek y S.-I. Lee, «AI for radiographic COVID-19 detection selects shortcuts over signal», *Nat. Mach. Intell.*, vol. 3, n.º 7, pp. 610–619, 2021, doi: 10.1038/s42256-021-00338-7.

[7] L. Seyyed-Kalantari, H. Zhang, M. B. A. McDermott, I. Y. Chen y M. Ghassemi, «Underdiagnosis bias of artificial intelligence algorithms applied to chest radiographs in under-served patient populations», *Nat. Med.*, vol. 27, n.º 12, pp. 2176–2182, dic. 2021, doi: 10.1038/s41591-021-01595-0.

[8] C. S. Marchello, M. H. Ebell, A. P. Dale, E. T. Harvill, Y. Shen y C. C. Whalen, «Signs and symptoms that rule out community-acquired pneumonia in outpatient adults: a systematic review and meta-analysis», *J. Am. Board Fam. Med.*, vol. 32, n.º 2, pp. 234–247, mar. 2019, doi: 10.3122/jabfm.2019.02.180219.

[9] M. Hardt, E. Price y N. Srebro, «Equality of opportunity in supervised learning», en *Advances in Neural Information Processing Systems 29*, D. Lee, M. Sugiyama, U. Luxburg, I. Guyon y R. Garnett, Eds. Curran Associates, 2016.

[10] E. B. Wilson, «Probable inference, the law of succession, and statistical inference», *J. Am. Stat. Assoc.*, vol. 22, n.º 158, pp. 209–212, 1927, doi: 10.1080/01621459.1927.10502953.

[11] Asamblea Nacional del Ecuador, «Ley Orgánica de Protección de Datos Personales», *Registro Oficial*, Quinto Suplemento, n.º 459, 26 may. 2021.

[12] Presidencia de la República del Ecuador, «Reglamento General de la Ley Orgánica de Protección de Datos Personales», Decreto Ejecutivo n.º 904, *Registro Oficial*, Tercer Suplemento, n.º 435, 13 nov. 2023.

[13] Ministerio de Salud Pública del Ecuador, «Reglamento para el manejo de información confidencial en el Sistema Nacional de Salud», Acuerdo Ministerial n.º 00005216-A, *Registro Oficial*, Suplemento, n.º 427, 29 ene. 2015.

[14] Superintendencia de Protección de Datos Personales, «Reglamento para la seudonimización, anonimización, bloqueo y eliminación de datos personales», Resolución n.º SPDP-SPD-2025-0030-R, 7 ago. 2025. Consultado: 5 oct. 2026. [En línea]. Disponible: https://spdp.gob.ec/resol/

[15] Radiological Society of North America, «Pneumonia Detection Challenge Terms of Use and Attribution». Consultado: 5 oct. 2026. [En línea]. Disponible: https://www.rsna.org/-/media/files/rsna/education/ai-resources-and-training/ai-image-challenge/pneumonia-detection-challenge-terms-of-use-and-attribution.pdf

[16] Radiological Society of North America y Kaggle, «RSNA Pneumonia Detection Challenge: Rules», 2018. Consultado: 5 oct. 2026. [En línea]. Disponible: https://www.kaggle.com/competitions/rsna-pneumonia-detection-challenge/rules

[17] Telegram, «Telegram Privacy Policy». Consultado: 5 oct. 2026. [En línea]. Disponible: https://telegram.org/privacy

[18] Superintendencia de Protección de Datos Personales, «Norma general de transferencias o comunicaciones nacionales e internacionales de datos personales», Resolución n.º SPDP-SPD-2026-0004-R, *Registro Oficial*, Tercer Suplemento, n.º 225, 13 feb. 2026.

[19] S. McGee, «Simplifying likelihood ratios», *J. Gen. Intern. Med.*, vol. 17, n.º 8, pp. 646–649, ago. 2002, doi: 10.1046/j.1525-1497.2002.10750.x.

[20] R. R. Selvaraju, M. Cogswell, A. Das, R. Vedantam, D. Parikh y D. Batra, «Grad-CAM: visual explanations from deep networks via gradient-based localization», en *Proc. IEEE Int. Conf. Comput. Vis. (ICCV)*, 2017, pp. 618–626, doi: 10.1109/ICCV.2017.74.

[21] M. Mitchell *et al.*, «Model cards for model reporting», en *Proc. Conf. Fairness, Accountability, and Transparency (FAT∗ '19)*, 2019, pp. 220–229, doi: 10.1145/3287560.3287596.

[22] T. Gebru *et al.*, «Datasheets for datasets», *Commun. ACM*, vol. 64, n.º 12, pp. 86–92, dic. 2021, doi: 10.1145/3458723.

[23] K. Goddard, A. Roudsari y J. C. Wyatt, «Automation bias: a systematic review of frequency, effect mediators, and mitigators», *J. Am. Med. Inform. Assoc.*, vol. 19, n.º 1, pp. 121–127, ene. 2012, doi: 10.1136/amiajnl-2011-000089.

[24] World Health Organization, *Ethics and Governance of Artificial Intelligence for Health: WHO Guidance*. Ginebra, Suiza: WHO, 2021, ISBN 9789240029200.

[25] Parlamento Europeo y Consejo de la Unión Europea, «Reglamento (UE) 2024/1689 por el que se establecen normas armonizadas en materia de inteligencia artificial», *Diario Oficial de la Unión Europea*, L 2024/1689, 12 jul. 2024.

[26] Congreso Nacional del Ecuador, «Ley Orgánica de Salud», Ley 2006-67, *Registro Oficial*, Suplemento, n.º 423, 22 dic. 2006 (edición compilada a 2012).

[27] Asamblea Constituyente, «Constitución de la República del Ecuador», *Registro Oficial*, n.º 449, 20 oct. 2008.

[28] Superintendencia de Protección de Datos Personales, «Norma general sobre el tratamiento de datos personales a gran escala», Resolución n.º SPDP-SPD-2026-0005-R, *Registro Oficial*, Primer Suplemento, n.º 231, 25 feb. 2026.

[29] Superintendencia de Protección de Datos Personales, «Norma general para la garantía del derecho de protección de datos personales en el uso de sistemas de inteligencia artificial», Resolución n.º SPDP-SPD-2026-0009-R, *Registro Oficial*, n.º 240, 10 mar. 2026.

[30] Agencia Nacional de Regulación, Control y Vigilancia Sanitaria (ARCSA), «Normativa técnica sanitaria sustitutiva para el registro sanitario y control de dispositivos médicos de uso humano, y de los establecimientos en donde se fabrican, importan, dispensan, expenden y comercializan», Resolución ARCSA-DE-026-2016-YMIH, *Registro Oficial*, Suplemento, n.º 921, 12 ene. 2017.

[31] Agencia Nacional de Regulación, Control y Vigilancia Sanitaria (ARCSA), «Normativa técnica sanitaria sustitutiva para la obtención del registro sanitario, control y vigilancia de dispositivos médicos de uso humano», Resolución ARCSA-DE-2026-003-DASP, *Registro Oficial*, Segundo Suplemento, n.º 286, 18 may. 2026.

[32] Ministerio de Salud Pública del Ecuador, «Norma Técnica de Telesalud», Acuerdo Ministerial n.º 00044-2025, *Registro Oficial*, Segundo Suplemento, n.º 153, 28 oct. 2025.

[33] Parlamento Europeo y Consejo de la Unión Europea, «Reglamento (UE) 2017/745 sobre los productos sanitarios», *Diario Oficial de la Unión Europea*, L 117, pp. 1–175, 5 may. 2017.

[34] Parlamento Europeo y Consejo de la Unión Europea, «Reglamento (UE) 2026/1744 por el que se modifican los Reglamentos (UE) 2024/1689, (UE) 2018/1139 y (UE) 2023/1230 en lo que respecta a la simplificación de la aplicación de las normas armonizadas sobre inteligencia artificial (Digital Omnibus on AI)», *Diario Oficial de la Unión Europea*, L 2026/1744, 24 jul. 2026.

[35] OpenAI, «Data controls in the OpenAI platform». Consultado: 18 oct. 2026. [En línea]. Disponible: https://developers.openai.com/api/docs/guides/your-data
