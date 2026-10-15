# Planificación del proyecto

**Copiloto de triaje para neumonía en adultos** · Proyecto Integrador, Maestría en Inteligencia Artificial (UEES), 2026.

Estado a **15 de octubre de 2026**. Este documento recoge lo que el equipo planificó en la
Semana 1 (12 al 19 de septiembre), cómo evolucionó el proyecto a lo largo de los cinco
sub-proyectos (SP1 a SP5) y, al final, en qué estado quedó cada indicador de éxito. Es el
único documento de `docs/` que nombra al equipo.

Cada cifra lleva su fuente (un fichero del repositorio o un documento de las semanas del
curso). Las fuentes de las semanas del curso viven fuera del repositorio y se citan por su
título: «Presentación del proyecto» (Semana 1, versión viva con su Registro de cambios),
«Matriz de KPIs», «Timeline ágil» y «Canvas SMART» (Semana 1), «Hallazgos medidos»
(Semana 3) y «Workshop de impacto social» (Semana 4).

## Contenido

1. [Resumen](#1-resumen)
2. [El problema y su relevancia](#2-el-problema-y-su-relevancia)
3. [Objetivos](#3-objetivos)
4. [Alcance: qué incluye y qué no](#4-alcance-qué-incluye-y-qué-no)
5. [Indicadores de éxito y sus metas](#5-indicadores-de-éxito-y-sus-metas)
6. [Metodología](#6-metodología)
7. [Equipo y roles](#7-equipo-y-roles)
8. [Recursos](#8-recursos)
9. [Cronograma: planificado frente a real](#9-cronograma-planificado-frente-a-real)
10. [Cómo evolucionó el proyecto: SP1 a SP5](#10-cómo-evolucionó-el-proyecto-sp1-a-sp5)
11. [Riesgos: lo previsto y lo ocurrido](#11-riesgos-lo-previsto-y-lo-ocurrido)
12. [Estado final de los indicadores](#12-estado-final-de-los-indicadores)
13. [Lo que no se cumplió y lo que sigue](#13-lo-que-no-se-cumplió-y-lo-que-sigue)

## 1. Resumen

**Qué se planificó.** Un copiloto de triaje para neumonía en adultos: dos bots de Telegram
(paciente y profesional) orquestados con n8n que consultan un servidor de inferencia propio
(una CNN servida por MCP en Docker), combinan la imagen con una regla clínica publicada
mediante una fórmula bayesiana explícita y entregan al profesional un pre-informe. En la
versión de la Semana 1 el sistema llevaba además un LLM que normalizaba el español coloquial
del paciente y redactaba el pre-informe, y un plazo de seis semanas (12 de septiembre al 24
de octubre de 2026) en cuatro sprints y ocho hitos (H1 a H8).

**Qué se entregó.** El servidor, los dos bots, la combinación bayesiana (con su horquilla
entre independencia y dependencia total), una validación semisintética de esa combinación,
una sesión de concordancia con un médico general y una interfaz de demostración (Streamlit)
sobre el mismo motor. El modelo desplegado es una EfficientNet-B0 a 320 px; en el conjunto
de prueba (3 811 placas) alcanza recall 0,882, especificidad 0,702 y AUC 0,885
(`app/assets/metricas.json`).

**Qué cambió.** Tres decisiones de alcance, todas tomadas con datos o con un argumento de
seguridad y todas registradas: se retiró el LLM (el cuestionario es de botones y el informe
es aritmética auditable), se unificó el criterio de la CNN porque la frontera medida
demostró que recall ≥ 0,85 y especificidad ≥ 0,75 no se alcanzan a la vez, y se añadieron
una interfaz web y un análisis por subgrupos que la Semana 1 había dejado fuera.

**Qué no se cumplió** (detalle en las secciones 12 y 13):

- La concordancia con el médico quedó por debajo del mínimo comprometido: kappa ponderado
  0,25 frente a 0,4 (`docs/validacion-semisintetica/acta-h7.md`).
- El tiempo de triaje no se redujo: con el copiloto fue el doble (razón 2,00), y corregido
  por el efecto de releer los casos la razón es 1,11, con un intervalo que incluye el 1
  (misma acta).
- La especificidad objetivo (0,75) no se alcanzó; el mínimo (0,70) se cumple por muy poco
  margen (0,702).
- No se midió la latencia de extremo a extremo con la regla del sub-proyecto SP5.
- Se descartaron la normalización de lenguaje con LLM, la métrica de extracción de síntomas
  y la validación externa con PadChest.

## 2. El problema y su relevancia

### 2.1 Definición del problema

La neumonía es una de las principales causas de muerte por infección y afecta de forma
desproporcionada a adultos mayores y a poblaciones con acceso limitado a servicios de salud.
Su diagnóstico oportuno depende de un recurso escaso: la lectura experta de la radiografía de
tórax. En urgencias saturadas y en zonas sin radiólogo de turno, el médico general decide el
triaje inicial de la placa sin apoyo especializado, lo que retrasa la priorización de los
casos sospechosos y consume tiempo clínico (Presentación del proyecto, §2.1).

A ese cuello de botella se suman dos limitaciones de las soluciones de IA disponibles, que
son el hueco que el proyecto aborda (§2.1 y §3.6 de la misma fuente):

1. Los clasificadores de imagen publicados ignoran la historia clínica del paciente
   (síntomas, signos, factores de riesgo), que es lo que el médico integra al decidir.
2. Las alternativas comerciales en la nube exigen enviar la radiografía a servicios externos,
   algo delicado cuando se trata de datos de salud.

### 2.2 Objetivo en formato SMART

El canvas de la Semana 1 («Canvas SMART») fijó el objetivo con los cinco criterios:

| Criterio | Cómo se concretó en la Semana 1 |
| :--- | :--- |
| **Específico** | Sistema con dos roles en Telegram orquestado en n8n: el paciente registra síntomas con cuestionario y recibe un código seudónimo; el profesional presenta el código, aporta los signos del examen y sube la radiografía; una CNN servida por MCP en Docker estima la probabilidad de opacidad compatible con neumonía; una fórmula bayesiana la combina con la probabilidad previa de una regla clínica publicada |
| **Medible** | Recall, especificidad y AUC de la CNN en un conjunto de prueba partido por paciente; kappa con un médico; latencia de extremo a extremo; reducción del tiempo de triaje; utilidad del pre-informe (sección 5) |
| **Alcanzable** | Dataset público suficiente (más de 10 000 imágenes), infraestructura ya operativa, entrenamiento en GPU gratuita, equipo de dos personas y un médico colaborador. La checklist de validación de la Semana 1 puntuó el objetivo 26/31 («verde en su límite inferior»: sin evidencia de usuario final validado, de stakeholders comprometidos ni de colchón de tiempo para imprevistos) |
| **Relevante** | Reducir el cuello de botella de la lectura de placas en el triaje de urgencias y atención primaria; la parte de imagen no se resuelve con reglas y exige visión computacional, y la regla clínica mantiene el resultado explicable |
| **Temporal** | 12 de septiembre al 24 de octubre de 2026 (seis semanas), con ocho hitos fechados |

La selección del problema fue el hito H1: la matriz de evaluación de la Semana 1 comparó tres
problemas candidatos (salud, finanzas y legaltech) y puntuó más alto el de salud (4,60, frente
a 4,15 y 3,60) (`LEEME_ENTREGA` de la Semana 1).

### 2.3 Justificación de la relevancia

- **Usuarios.** Médicos generales y personal de triaje de urgencias y telemedicina
  (primarios); pacientes adultos que registran sus síntomas antes de la consulta
  (secundarios); la dirección médica como decisora (Canvas SMART).
- **Beneficio buscado.** Priorizar a los pacientes con sospecha de neumonía y recuperar tiempo
  clínico en las placas sin hallazgos, sin quitar la decisión al profesional: el sistema es
  un apoyo y todo resultado lo dice (Presentación del proyecto, §2.2).
- **Por qué IA y no una solución tradicional.** Detectar opacidades en una placa no se
  resuelve con reglas; la regla clínica (Heckerling) sí es una solución tradicional y se
  incluye como probabilidad previa precisamente por ser explicable y validada (Canvas SMART).
- **Stakeholders.** La Semana 1 identificó seis (médicos, pacientes, dirección médica,
  médico validador, reguladores y tutora) con su estrategia de involucramiento
  (Presentación del proyecto, §6). Los impactos sociales, las poblaciones afectadas y las
  medidas de mitigación están en `docs/consideraciones_eticas.md`.

## 3. Objetivos

El objetivo general y los cinco específicos de la Semana 1 (Presentación del proyecto, §7.1
y §7.2), con el estado en que terminó cada uno. La evidencia está en la sección 12.

| # | Objetivo específico (Semana 1) | Estado final |
| :-: | :--- | :--- |
| 1 | Entrenar y evaluar una CNN con transfer learning sobre RSNA, con partición por paciente: recall ≥ 85 %, especificidad ≥ 70 % (objetivo 75 %) y AUC ≥ 0,85 en prueba (criterio unificado el 23-sep) | **Cumplido** con el criterio unificado. Recall 0,882, especificidad 0,702, AUC 0,885. La especificidad objetivo de 0,75 no se alcanza a la vez que el recall |
| 2 | Desplegar la CNN como servidor MCP en Docker, consumido desde n8n, con latencia de extremo a extremo menor de 8 s | **Cumplido en lo desplegado**: servidor MCP y REST operativos. La latencia de inferencia es de 143 ms de mediana en el servidor; la de extremo a extremo no se midió con la regla del SP5 |
| 3 | Flujo de dos roles en Telegram: síntomas del paciente con código seudónimo; evaluación por el profesional | **Cumplido** (SP3) |
| 4 | Normalizar síntomas coloquiales con un LLM (precisión y recall ≥ 85 % por concepto) y combinar la probabilidad previa por regla clínica con la CNN mediante una fórmula bayesiana | **Parcial**. La combinación bayesiana está cumplida (SP4). La normalización con LLM y su métrica se **descartaron** (sección 4.2) |
| 5 | Validar el prototipo con un médico general sobre 20 a 30 casos, con kappa y utilidad del pre-informe | **Realizado, criterio no cumplido**: 24 casos, dos lecturas; kappa ponderado 0,25 (mínimo 0,4); utilidad 4,0/5 |

## 4. Alcance: qué incluye y qué no

### 4.1 Lo que el plan de la Semana 1 incluía y excluía

| Funcionalidad | Estado en la Semana 1 |
| :--- | :--- |
| Clasificación de opacidad compatible con neumonía en radiografía frontal de adultos | Incluida |
| Servidor MCP en Docker consumido desde n8n | Incluida |
| Bot del paciente (cuestionario, texto libre y código) y bot del profesional (código, signos, radiografía, pre-informe) | Incluidas |
| Normalización del lenguaje coloquial a conceptos clínicos | Incluida |
| Combinación bayesiana de síntomas e imagen | Incluida |
| Validación con un médico general | Incluida |
| Mapa de calor Grad-CAM | Opcional |
| Severidad y triaje con CRB-65; integración con historia clínica electrónica; otras patologías; validación externa multicéntrica; despliegue con GPU | Excluidas |
| Interfaz web; auditoría formal de sesgo por sexo y edad | Excluidas |

### 4.2 Cómo cambió el alcance

El sub-proyecto SP5 revisó el plan fila por fila contra lo entregado. Cada cambio de esta
tabla está justificado en el spec de SP5 (§6.2) y en el Registro de cambios de la
Presentación del proyecto.

| Elemento | Resultado | Razón |
| :--- | :--- | :--- |
| Normalización del lenguaje coloquial con LLM | **Descartada** | Un extractor probabilístico en la *entrada* de un cálculo clínico no falla con un error: produce una probabilidad previa equivocada que nadie ve. El cuestionario es de botones; lo que entra al cálculo es exactamente lo que el paciente tocó (spec de SP3, D4). Efecto secundario declarado: ningún dato del paciente sale hacia un proveedor de LLM |
| Redacción del pre-informe con LLM | **Descartada** | La combinación es aritmética auditable; un LLM entre los números y el clínico rompe la explicabilidad (spec de SP4, §12). El título del proyecto pierde «y LLM» |
| Corpus de 50 a 100 frases, tres enfoques y métrica de extracción | **Descartado** | Sin extractor no hay extracción que medir |
| Combinación bayesiana | Cumplida, con cambio | El mensaje imprime la prevalencia declarada, la razón de verosimilitud de la clínica, la de la imagen y una horquilla entre independencia y dependencia total, en vez de una «probabilidad previa por síntomas» |
| Validación con el médico | Cumplida, con cambio | Dos lecturas del mismo conjunto en vez de una sesión (el kappa sale solo de la lectura sin copiloto y el tiempo se mide sobre el mismo conjunto); se pregunta por opacidad compatible, no por neumonía |
| Validación externa con PadChest | **Descartada** | El acuerdo de uso no se gestionó; el sesgo de origen único queda declarado |
| Grad-CAM | **Añadido** (opcional en el plan) | Compromiso M5 del workshop de la Semana 4; está en la interfaz de demostración, no en el bot |
| Interfaz web (excluida) | **Añadida** | La entrega final del curso exige una interfaz para probar el modelo; es una app Streamlit sobre el mismo motor (`app/`) |
| Auditoría por sexo y edad (excluida) | **Añadida** | Tabla por subgrupos (sexo, edad, proyección) en `app/assets/metricas.json` |
| Carpeta `samples/` con 20 imágenes | **No incluida** | RSNA no se redistribuye (reglas de la competición, cláusula 7.B). Los ejemplos de la app son de otra fuente, con licencia que lo permite |
| Datos clínicos reales emparejados con imagen | No prometidos | Ningún conjunto público trae síntomas junto a la placa; la combinación se validó con una simulación semisintética, rotulada como tal (spec de SP3, §19) |

## 5. Indicadores de éxito y sus metas

La Matriz de KPIs y la tabla de umbrales de la Semana 1 (§5.7) fijaron un mínimo aceptable
y un objetivo para cada indicador. Cada componente se mide por separado para no mezclar las
métricas de la imagen con las del pipeline completo.

| Indicador | Mínimo | Objetivo | Cómo se mide |
| :--- | :-: | :-: | :--- |
| Recall de la CNN (métrica primaria: en triaje el falso negativo es el error caro) | 0,80 | 0,85 | Conjunto de prueba, partido por paciente |
| Especificidad de la CNN | 0,70 | 0,75 | Ídem |
| AUC-ROC | 0,85 | 0,88 | Ídem |
| Precisión y recall de la extracción de síntomas, por concepto | 0,80 | 0,85 | Corpus de 50 a 100 frases coloquiales |
| Kappa con el médico | 0,4 (moderado) | 0,6 (sustancial) | 20 a 30 casos con imagen y viñeta clínica |
| Latencia de extremo a extremo | 8 s | 3 s | Desde que el profesional sube la placa hasta que recibe el pre-informe |
| Reducción del tiempo de triaje | 20 % | 40 % | Tiempo con y sin copiloto sobre el mismo conjunto de casos |
| Utilidad del pre-informe (CSAT del profesional) | 4/5 | — | Calificación del médico sobre corrección, utilidad y lenguaje |

Indicadores complementarios de la Semana 1: ausencia de fuga de datos entre particiones (0
pacientes compartidos); latencia de inferencia de la CNN en CPU (menos de 4 s, objetivo 1 s);
disminución de derivaciones innecesarias a radiología (definida como el porcentaje de placas
sin opacidad correctamente filtradas); y, para una fase con usuarios, la tasa de
finalización del cuestionario, el CSAT del paciente y la tasa de uso activo.

La Semana 1 dejó escrito cómo tratar un incumplimiento: si al cierre no se alcanzan, «se
documenta la causa y el trabajo futuro, según lo indicado por la tutora». Es lo que hacen las
secciones 12 y 13.

## 6. Metodología

### 6.1 Lo planificado

Scrum en seis semanas y cuatro sprints, alineados con las fases sugeridas por la tutora
(investigación y diseño, implementación, ajuste y validación, cierre): planificación de una
hora al inicio de cada sprint, seguimiento diario asíncrono, y revisión y retrospectiva el
sábado de cada tutoría. Backlog priorizado por el Product Owner con historias de usuario
estimadas en puntos (escala de Fibonacci) y una definición de «hecho» que exige evidencia
verificable: una métrica registrada, una demostración reproducible o un documento entregado
(Presentación del proyecto, §8).

### 6.2 Lo practicado

El calendario y las ceremonias se mantuvieron como marco; el trabajo diario siguió un ciclo
más estricto por sub-proyecto:

1. **Especificación escrita** antes de programar (`docs/superpowers/specs/`), con las
   decisiones, los hechos medidos que las condicionan y los riesgos abiertos.
2. **Plan por tareas** (`docs/superpowers/plans/`).
3. **Desarrollo guiado por pruebas** y revisión independiente de cada tarea y de cada rama
   antes de fusionar. Al 5 de octubre el workshop de la Semana 4 contaba más de 1 100
   pruebas automáticas en Python, además de las de los flujos de n8n.
4. **Decisiones y correcciones por escrito.** La Presentación del proyecto se mantuvo como
   documento vivo con un Registro de cambios: lo que los datos desmentían (el objetivo de
   especificidad, la palanca de mejora del modelo, la composición del dataset, el LLM) se
   corrigió con fecha y evidencia. Las correcciones de afirmaciones de privacidad hechas el
   26 de septiembre, a raíz de una evaluación externa, también se dejaron fechadas en los
   documentos que las contenían.
5. **Medir antes de decidir.** La arquitectura se eligió con ocho corridas comparadas y no
   por reputación del modelo (`docs/comparativa-corridas.md`); el umbral se elige sobre
   validación y nunca sobre prueba. Una reserva que el propio informe de la comparativa
   declara: esas corridas se compararon leyendo el conjunto de prueba, lo que deja la métrica
   de la ganadora algo optimista, y cada configuración se entrenó una sola vez con una sola
   semilla.

El desarrollo se apoyó en un asistente de IA para programación (Claude Code), que redactó
buena parte del código y de la documentación bajo este ciclo; las especificaciones, las
decisiones de alcance, las revisiones y la validación con el médico son del equipo.

El control de versiones es Git, con una rama por sub-proyecto y fusiones fechadas (sección 9).

## 7. Equipo y roles

| Persona | Rol | Responsabilidades (Presentación del proyecto, §8.1 y §9.1; Workshop de la Semana 4, tabla 4) |
| :--- | :--- | :--- |
| [retirado] [retirado] [retirado] [retirado] | Product Owner y Scrum Master | Backlog, decisiones de diseño y de alcance, flujos de n8n y de los bots, logística de la validación médica, documentación y entregas |
| [retirado] [retirado] [retirado] [retirado] | Lead AI Engineer | Datos RSNA, entrenamiento y evaluación de la CNN, servidor MCP en Docker, combinación bayesiana, métricas, calidad del modelo, la calibración y el sesgo |
| Médico general colaborador (externo, voluntario) | Experto del dominio | Sesión de concordancia: dos lecturas sobre 24 casos y valoración del pre-informe. Sin datos personales en ningún fichero del proyecto |
| Tutora del Proyecto Integrador (UEES) | Tutora y sponsor académico | Revisión de los entregables y aprobación de los hitos académicos |

Ambos integrantes actuaron como equipo de desarrollo; la asignación concreta de historias se
decidía en cada planificación de sprint. La dedicación estimada en la Semana 1 fue de unas 12
horas semanales por integrante (74 horas cada uno) y 5 horas del médico. El repositorio no
conserva un registro de horas reales, así que esa estimación no se contrasta aquí.

## 8. Recursos

### 8.1 Lo previsto en la Semana 1 y lo que ocurrió

| Categoría | Previsto (Presentación del proyecto, §9) | Lo ocurrido |
| :--- | :--- | :--- |
| Datos | RSNA Pneumonia Detection Challenge (principal), PadChest (validación externa), NIH ChestX-ray14 (plan B) | Solo RSNA. PadChest no se gestionó; el plan B no hizo falta |
| Cómputo de entrenamiento | Google Colab (GPU T4), nivel gratuito, con Colab Pro como contingencia | Ocho corridas comparadas a 320 px en tres entornos (Kaggle, Colab y CPU local), además de la primera corrida a 224 px y las tres de diagnóstico del 26-sep. En CPU, el entrenamiento de 4 + 20 épocas cuesta 10,8 h con EfficientNet-B0 y 24,9 h con DenseNet121 (README del repositorio) |
| Servidor | VPS de 16 GB de RAM y 8 vCPU con Docker, n8n y PostgreSQL; inferencia en CPU | Se cumplió; el servicio se acota a 2 núcleos y 2 GB de memoria |
| Software | Python (PyTorch), n8n, Docker, PostgreSQL, Telegram Bot API, GitHub | Se cumplió, más Streamlit para la interfaz y scikit-learn para la calibración |
| Servicios de IA | API de LLM (OpenAI o Gemini), 15 USD de consumo | No se usó: el LLM se descartó (sección 4.2) |
| Personal | Dos integrantes, un médico ad honorem y la tutoría académica | Se cumplió; el médico participó de forma voluntaria |

### 8.2 Presupuesto

La Semana 1 estimó 138 USD para los dos meses del proyecto: 100 de infraestructura (costo
referencial imputado, porque el servidor ya existía), 15 de consumo de API de LLM, 23 de
contingencia (20 %) y 0 en datos, software y médico. Las 148 horas del equipo no se
monetizaron. El gasto real no se reconstruyó; lo único que se puede afirmar es que la partida
de LLM no se ejecutó.

### 8.3 Dónde corre cada cosa

El mismo paquete se ejecuta en dos sitios: la máquina local, sin GPU, sirve para desarrollar,
probar y entrenar de forma excepcional; Colab o Kaggle, con GPU, para el entrenamiento real
(README, «Dónde corre cada cosa»). Los pesos son pequeños (16 MB) y las dependencias están
fijadas por versión.

## 9. Cronograma: planificado frente a real

### 9.1 Los sprints

| Sprint | Fechas planificadas | Objetivo planificado |
| :-: | :--- | :--- |
| 1 | 12 al 25 de septiembre | Investigación, diseño y núcleo de imagen |
| 2 | 26 de septiembre al 2 de octubre | Integración MCP y dos roles |
| 3 | 3 al 16 de octubre | Síntomas, ajuste y validación clínica |
| 4 | 17 al 24 de octubre | Cierre y documentación |

### 9.2 Los hitos

| Hito | Entregable principal | Fecha plan | Fecha real | Diferencia y nota |
| :-: | :--- | :-: | :-: | :--- |
| H1 | Selección del problema validada (Workshop SMART) | 15-sep | Semana 1 | Materiales fechados el 15 y el 16 de septiembre |
| H2 | Documento de Presentación del Proyecto | 20-sep | 22-sep | +2 días. Versión viva con Registro de cambios; v2 del 24-sep |
| H3 | Dataset preparado y CNN entrenada | 25-sep | 23-sep | −2 días. Cumplido con matices: el objetivo de especificidad 0,75 resultó inalcanzable junto con el recall |
| H4 | Servidor MCP operativo en el VPS | 30-sep | 24-sep | −6 días (SP2) |
| H5 | Bot de Telegram con dos roles, extremo a extremo | 2-oct | 25-sep | −7 días (SP3) |
| H6 | Módulo de síntomas y combinación bayesiana | 9-oct | 26-sep | −13 días, con alcance reducido: la combinación se entregó; el extractor con LLM se descartó (SP4) |
| H7 | Validación clínica con el médico | 16-oct | 10 y 15-oct | En plazo. Las dos lecturas se hicieron el 10 y el 15 de octubre; el acta se cerró el 15. El criterio de kappa no se cumplió |
| H8 | Informe final, videos y repositorio público | 24-oct | En curso | A 15 de octubre se estaba consolidando la documentación del curso (SP5-C2) |

Fuentes de las fechas reales: historial de fusiones del repositorio, Registro de cambios de
la Presentación del proyecto y acta de H7.

### 9.3 Lo que se movió y por qué

- **El núcleo técnico se adelantó entre dos días y casi dos semanas** (H3 a H6 cerraron entre
  el 23 y el 26 de septiembre, frente a las fechas del 25 de septiembre al 9 de octubre). El
  tiempo ganado se dedicó a lo que el plan no preveía: la validación semisintética, la
  anonimización del repositorio, el diagnóstico de sobreajuste (Semana 3), el análisis por
  subgrupos (Semana 4) y la interfaz.
- **H2 se entregó dos días después** de la fecha del plan (20 de septiembre).
- **H7 se movió dentro de su ventana.** La lectura 1 estaba prevista para el 8 de octubre y
  se hizo el 10; la lectura 2, el 15. El intervalo entre lecturas fue de 5 días, no los 7 o
  más del diseño, y el acta lo declara como desviación: con menos días el médico recuerda
  más los casos, lo que pesa en el tiempo y en los cambios de banda de la lectura 2 (no en
  el kappa primario, que sale solo de la lectura 1). La modalidad fue videollamada, no
  presencial (`docs/validacion-semisintetica/acta-h7.md`, «Desviaciones del protocolo»).
- **Congelación del código.** La Semana 1 prometió que la semana 6 no admitiría código nuevo.
  El tag `h7-sesion` (5 de octubre) congeló el código que generó los mensajes de la sesión.
  Con posterioridad se fusionaron cambios de robustez y de interfaz (SP5-B4 y SP5-C1, el 6
  de octubre); el calendario de SP5 fijaba el 16 de octubre como último día de código nuevo.

## 10. Cómo evolucionó el proyecto: SP1 a SP5

La Semana 1 dividió el proyecto en cinco sub-proyectos secuenciales, cada uno con su ciclo de
especificación, plan e implementación. Lo que cada uno entregó:

| Sub-proyecto | Hito | Fechas | Qué entregó | Cifra o hecho clave | Documento |
| :--- | :-: | :--- | :--- | :--- | :--- |
| **SP1. Núcleo de imagen** | H3 | Spec y pipeline el 16-sep; primera corrida el 19-sep; mejoras el 21-sep; cierre el 23-sep | Paquete `copiloto_triaje` (conversión DICOM a PNG, partición por paciente verificada sin fuga, transfer learning en dos fases, evaluación y selección de umbral); notebooks de entrenamiento en GPU; ocho corridas comparadas con tres arquitecturas | La primera corrida (MobileNetV3, 224 px) dio recall 0,766 y AUC 0,845, bajo los mínimos; con 320 px y ajuste fino completo se llegó a recall 0,882, especificidad 0,702 y AUC 0,885 | `docs/superpowers/specs/2026-09-16-sp1-nucleo-imagen-design.md`, `docs/mejoras-2026-09-21.md`, `docs/comparativa-corridas.md` |
| **SP2. Servidor de inferencia** | H4 | 23 y 24-sep | Servicio MCP y REST en Docker sobre el mismo núcleo; calibrador isotónico y razón de verosimilitud acotada a [0,0163; 77,32]; rechazo de edades fuera de 18 a 100 años; contenedor sin puertos publicados | Latencia de inferencia 38 ms (REST) y 43 ms (MCP) en el contenedor; 143 ms de mediana en el servidor de producción | `docs/superpowers/specs/2026-09-23-sp2-servidor-mcp-design.md`, `docs/sp2-despliegue.md` |
| **SP3. Bots de Telegram** | H5 | 24 y 25-sep | Dos bots (paciente y profesional) en n8n, base de datos PostgreSQL propia, consentimiento previo, código seudónimo, lista blanca de profesionales, limpieza diaria y avisos de salud | Sin LLM por decisión de diseño. En el 23,3 % de lo que el cribado etiqueta como positivo la razón de verosimilitud de la imagen es menor que 1; por eso el informe presenta la etiqueta y la evidencia por separado | `docs/superpowers/specs/2026-09-24-sp3-bot-n8n-design.md`, `docs/sp3-operacion.md` |
| **SP4. Combinación bayesiana** | H6 | 26-sep | Regla clínica de Heckerling (seis razones de verosimilitud, de 0,12 a 17,5), prevalencia declarada de 0,1466, combinación como horquilla entre independencia y dependencia total, y asma «no sé» como intervalo | La combinación entrega un rango y no una cifra con falsa precisión | `docs/superpowers/specs/2026-09-26-sp4-combinacion-bayesiana-design.md` |
| **SP5. Validación y cierre** | H7, H8 | 27-sep a hoy (5 y 6-oct las fusiones de B2, B3, B4 y C1) | Validación semisintética de la combinación (generador, oráculo y rejilla de dependencia); instrumentos y sesión de concordancia con un médico; anonimización y pruebas de anonimato; texto del consentimiento al día; rechazo de DICOM que el modelo no puede evaluar; interfaz Streamlit con umbral por vista y mapa de calor; estructura y documentación del curso | La aritmética de la combinación se reproduce caso a caso; el kappa con el médico fue 0,25 | `docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md`, `docs/validacion-semisintetica-sp5.md`, `docs/validacion-semisintetica/acta-h7.md` |

Además de los sub-proyectos, el proyecto entregó los trabajos de las Semanas 2 a 4, que
alimentan estos documentos: el análisis exploratorio de RSNA (`docs/analisis_datos.md`), el
diagnóstico de sobreajuste (`docs/optimizacion.md`) y el análisis de impacto social
(`docs/consideraciones_eticas.md`).

## 11. Riesgos: lo previsto y lo ocurrido

Los riesgos de la Semana 1 (Presentación del proyecto, §8 y §9.4; Canvas SMART) y los que
añadieron los sub-proyectos, con lo que pasó de verdad.

| Riesgo | Mitigación prevista | Qué ocurrió |
| :--- | :--- | :--- |
| Métricas de la CNN por debajo del umbral | Segunda arquitectura, ajuste del umbral por curva ROC, aumento de datos y parada temprana | **Se materializó** con la primera corrida (recall 0,766, AUC 0,845). La palanca no fue la arquitectura: fue subir la resolución a 320 px y ajustar toda la red. Además hubo que corregir la regla de elección del umbral (`docs/mejoras-2026-09-21.md`) |
| El objetivo de especificidad no es compatible con el de recall | No previsto | **Descubierto el 23-sep**: no existe un punto con recall ≥ 0,85 y especificidad ≥ 0,75 a la vez (`docs/frontera-recall-especificidad.md`). Se unificó el criterio y se publicó la frontera |
| Sobreajuste | Aumento de datos y parada temprana | **Se materializó** al descongelar el backbone; la parada temprana lo contuvo (`docs/optimizacion.md`) |
| Descarga o conversión lenta de DICOM | API de Kaggle y conversión por lotes | No fue problema: la preparación completa de los 26 684 DICOM tarda unos 25 minutos en local (README), y leer solo sus cabeceras, 26 segundos (notebook de exploración) |
| Límite de GPU gratuita | Checkpoints en Drive y Colab Pro | Se entrenó en Kaggle, Colab y CPU local; el entrenamiento local es reanudable |
| Incompatibilidad entre n8n y MCP | Endpoint REST de respaldo | **No ocurrió**: el bot llama a la herramienta MCP; el REST queda como respaldo |
| Salidas inconsistentes del LLM | Few-shot con esquema JSON; léxico de reglas como respaldo | **Eliminado de raíz** al descartar el LLM |
| Agenda del médico (riesgo crítico) | Sesión agendada desde la semana 3 y fecha alterna en la semana 5 | **Se materializó en parte**: la lectura 1 se movió del 8 al 10 de octubre y el intervalo entre lecturas quedó en 5 días |
| La radiografía y las respuestas pasan por los servidores de Telegram | Seudonimización, borrado tras el análisis y aviso de consentimiento | **Aceptado y declarado, no mitigado** (spec de SP3, §5.5). El consentimiento se reescribió el 5-oct para nombrar a Telegram, a la IA y el plazo real de conservación |
| No existen datos reales que emparejen imagen y clínica | No previsto en la Semana 1 | **Riesgo mayor del proyecto, no resuelto** (spec de SP3, §19). La combinación se validó solo con una simulación semisintética, que no mide exactitud clínica |
| Sesgo por la proyección de la placa (AP/PA) | Medir el rendimiento por separado en cada posición | **Se materializó**: en prueba el recall en placas PA es 0,693 frente a 0,941 en AP (`app/assets/metricas.json`). Mitigación evaluada: umbral por vista, apagado por defecto y a decisión de la institución (`docs/optimizacion.md`) |
| Falla del servidor durante la grabación | Demostración pregrabada | Pendiente: depende de H8 |
| Colchón de tiempo para imprevistos | No reservado de forma explícita (la checklist lo marcó) | En la práctica, el adelanto del núcleo técnico (sección 9.3) dejó holgura |

## 12. Estado final de los indicadores

Qué se midió, dónde y con qué resultado. «Cumplido» significa que la estimación puntual
alcanza el objetivo; «mínimo» que alcanza el mínimo pero no el objetivo. Los intervalos son
del 95 %.

| Indicador | Mínimo / objetivo | Resultado final | Estado | Fuente |
| :--- | :-: | :--- | :--- | :--- |
| Recall de la CNN | 0,80 / 0,85 | 0,882 (IC de Wilson 0,858 a 0,902) | **Cumplido** | `app/assets/metricas.json`, bloque `global` (3 811 placas, 844 con opacidad) |
| Especificidad de la CNN | 0,70 / 0,75 | 0,702 (0,686 a 0,719) | **Mínimo**, por 0,002; el intervalo incluye valores por debajo de 0,70. El objetivo no se alcanza | Ídem; `docs/frontera-recall-especificidad.md` |
| AUC-ROC | 0,85 / 0,88 | 0,885 en prueba; 0,8827 en validación | **Cumplido** | Ídem |
| Fuga de datos entre particiones | 0 pacientes | 0 pacientes compartidos, verificado por pruebas automáticas y en las tres plataformas de entrenamiento | **Cumplido** | `tests/test_particion.py`, `tests/test_manifiestos_emitidos.py`; Timeline ágil (Semana 1), seguimiento de la semana 2 |
| Latencia de inferencia de la CNN en CPU | < 4 s / < 1 s | 0,022 s por imagen; 38 ms (REST) y 43 ms (MCP) en el contenedor; 143 ms de mediana en el servidor de producción | **Cumplido** | Spec de SP2 (§1), `docs/sp2-despliegue.md` (§7) |
| Latencia de extremo a extremo | 8 s / 3 s | No se midió con la regla del spec de SP5 (§6.3): `docs/validacion-semisintetica/` no contiene `latencia.json`. Solo consta la latencia de inferencia, que es un tramo | **No medido** | Spec de SP5, §6.3; `docs/validacion-semisintetica/README.md` |
| Kappa con el médico | 0,4 / 0,6 | Kappa ponderado lineal **0,25** (IC 0,07 a 0,44); Cohen sin ponderar **0,10** (−0,09 a 0,30); binario en «alta» 0,29 (0,03 a 0,55); n = 24, un evaluador | **No cumplido**, ni el mínimo | `docs/validacion-semisintetica/acta-h7.md` |
| Reducción del tiempo de triaje | 20 % / 40 % | Razón de medias geométricas con/sin copiloto **2,00** (IC BCa 1,57 a 2,49): el tiempo se duplicó. Corregida por el efecto de releer los casos: 1,11 (0,69 a 1,81) | **No cumplido**: el tiempo no se redujo | Ídem |
| Utilidad del pre-informe (CSAT ≥ 4/5) | 4/5 | Corrección 4,7; utilidad 4,0; **lenguaje 2,5** (n = 20, un médico) | **Parcial**: corrección y utilidad cumplen; el lenguaje no | Ídem |
| Precisión y recall de la extracción de síntomas | 0,80 / 0,85 | No existe extractor | **Descartado** | Spec de SP5, §6.2 |
| Disminución de derivaciones innecesarias a radiología (placas sin opacidad correctamente filtradas) | — | 0,702, que es la especificidad en prueba; medido en RSNA, no en operación | **Medido en su propia definición**, sin evidencia operativa | Spec de SP5, §6.3 |
| Aritmética de la combinación bayesiana | La posterior calculada coincide con la del generador | Coincide dentro de 0,015 log-odds en todos los casos del escenario sin dependencia | **Cumplido** (simulación semisintética) | `docs/validacion-semisintetica-sp5.md`, «Escenario 0A»; `tests/test_validacion_0a.py` |
| Contención de la horquilla (hipótesis del SP5: ≥ 90 % de los casos concordantes) | ≥ 90 % | No se sostiene en ninguna de las 6 celdas con dependencia que llevan intervalo; el sesgo de la independencia depende de dónde viva la correlación entre clínica e imagen | **No sostenida** bajo dependencia | `docs/validacion-semisintetica-sp5.md`, «Lectura de los resultados» |
| Finalización del cuestionario, CSAT del paciente, uso activo | — | Sin dato: el sistema no tiene usuarios | **Sin dato** | Spec de SP5, §6.3 |

La sesión con el médico es un diseño pequeño (24 casos, un evaluador, casos elegidos por
estratos y no por frecuencia real), y el acta lo declaró antes de empezar: no distingue una
concordancia moderada de una sustancial ni generaliza a otros médicos. El intervalo del
kappa ponderado incluye el 0,4 en el método analítico (0,07 a 0,44) y en el BCa (0,11 a
0,49), pero la estimación puntual (0,25) queda por debajo y el criterio se evaluó sobre la
estimación puntual, como estaba declarado.

## 13. Lo que no se cumplió y lo que sigue

### 13.1 Lo que no se cumplió

1. **Concordancia con el médico.** Kappa ponderado 0,25 y sin ponderar 0,10, frente a un
   mínimo de 0,4. En 16 de los 24 casos hubo desacuerdo entre la categoría del sistema y la
   banda del médico. El acta no atribuye la causa; documenta caso por caso los desacuerdos.
2. **Reducción del tiempo de triaje.** No hubo reducción: con el copiloto el médico tardó el
   doble (razón 2,00). Buena parte de ese aumento aparece también en los cuatro casos de
   control que se releyeron sin mensaje del sistema (media geométrica de las razones: 1,80),
   así que el efecto del copiloto aislado es incierto. Corregida por el efecto de releer, la
   razón es 1,11 (intervalo de 0,69 a 1,81): sin evidencia de reducción. El lenguaje del
   pre-informe recibió 2,5 sobre 5, la nota más baja de la sesión.
3. **Especificidad objetivo de 0,75.** La frontera medida lo hace incompatible con un recall
   de 0,85 (con 0,752 de especificidad el recall en validación cae a 0,840). El proyecto
   priorizó el recall, y el mínimo de especificidad se cumple con un margen de 0,002.
4. **Latencia de extremo a extremo.** No hay medición publicada con la regla del SP5.
5. **Descartes de alcance.** Normalización con LLM, extracción y su métrica, y validación
   externa con PadChest.
6. **Rendimiento desigual por subgrupos.** El modelo no trata igual a todos: el recall en
   placas PA es 0,693 (0,636 en PA de 60 años o más) frente a 0,941 en AP, y la
   especificidad en AP es 0,393 (`app/assets/metricas.json`). Es un resultado, no un
   incumplimiento de un KPI de la Semana 1, pero obliga a mirar el indicador global con
   reserva; se trata en `docs/consideraciones_eticas.md`.

### 13.2 Trabajo futuro

- Validación local con datos emparejados de imagen y clínica antes de cualquier uso clínico
  (el repositorio es una demostración académica, no un producto sanitario).
- Repetir las corridas con varias semillas, escalonar el descongelado del backbone y explorar
  la regularización explícita: son las hipótesis que `docs/optimizacion.md` deja
  planteadas.
- Sustituir Telegram por un canal propio de carga de placas, para cerrar el tramo por el que
  la imagen pasa por un tercero.
- Decidir con la institución que lo adopte si se enciende el umbral por vista, con su precio
  en especificidad delante.
- Medir la latencia de extremo a extremo con una corrida con bots de al menos 30 consultas.
- Medir la dependencia real entre clínica e imagen con datos que traigan ambas.

## Fuentes

- `docs/superpowers/specs/` (SP1 a SP5 y SP5-C1) y `docs/superpowers/plans/`.
- `docs/comparativa-corridas.md`, `docs/frontera-recall-especificidad.md`,
  `docs/mejoras-2026-09-21.md`, `docs/sp2-despliegue.md`, `docs/sp3-operacion.md`.
- `docs/validacion-semisintetica-sp5.md` y `docs/validacion-semisintetica/` (acta de H7,
  `sesion.json` y `resultados_simulacion.json`).
- `app/assets/metricas.json`.
- Semana 1: Presentación del Proyecto (versión viva, con Registro de cambios), Canvas SMART,
  Checklist de validación, Matriz de KPIs y Timeline ágil.
- Semana 3: Hallazgos medidos y diagnóstico de sobreajuste.
- Semana 4: Workshop de impacto social y responsabilidad.
