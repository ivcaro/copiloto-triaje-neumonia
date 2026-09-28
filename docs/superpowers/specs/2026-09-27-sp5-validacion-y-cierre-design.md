# SP5 — Validación y cierre

**Sub-proyecto:** SP5, quinto y último. **Hitos:** H7 (sesión de concordancia
con un médico, entre el 6 y el 16-oct-2026) y H8 (cierre: informe final, videos
y repositorio, 24-oct-2026, inamovible).

**Recibe de:** SP4 (H6), que entrega al profesional la probabilidad posterior
de opacidad compatible: prevalencia declarada × RV de la puntuación de
Heckerling × RV de la imagen, como horquilla entre independencia y dependencia
total.

**Entrega a:** el tribunal.

**Revisión:** este spec pasó el 27-sep dos revisiones independientes: una con
dos lentes (método y promesas) sobre el borrador, y una segunda con tres
(método, promesas, claridad) sobre la versión corregida, con verificación
adversarial de cada hallazgo. Esta versión incorpora las dos. Los cambios
grandes respecto al borrador: el generador sortea la **puntuación** de
Heckerling, no los hallazgos por separado (§4.2); la dependencia se barre en
dos parámetros y su dirección es un resultado, no una premisa (§4.5); la
sesión son **dos lecturas del mismo conjunto** y el kappa sale solo de la
lectura sin copiloto (§5.4); al tribunal se le da un **repositorio nuevo** con
historial limpio (§6.1); y el spec recoge lo que exige la descripción de la
entrega final del curso (§6.7).

---

## 1. Qué hace, en dos frases

Mide lo que el proyecto afirma y dice con precisión lo que no puede afirmar:
una **validación cuantitativa** de la combinación sobre un emparejamiento
declarado como semisintético, y la **sesión de concordancia con un médico**
que la Semana 1 prometió como H7. Después cierra: entrega un repositorio sin
ninguna cadena que identifique al cliente, a la empresa ni a los integrantes,
ni en el texto ni en el historial (§6.1); escribe el informe final con la
tabla «prometido vs. entregado»; cumple lo que exige la entrega final del
curso; y deja la deuda por escrito.

## 2. Lo que la Semana 1 prometió, literalmente

Del documento de Presentación del Proyecto (fechado el 16-sep, **entregado el
22-sep** como v1; versión viva con Registro de cambios: v2 del 24-sep más las
entradas del 25-sep). Cada cita lleva su sección:

- **§10.2, H7:** «acta de la sesión de validación con el médico general: kappa
  de Cohen sobre 20 a 30 casos, calificación de utilidad (1-5) y medición del
  tiempo de triaje con y sin copiloto». Aceptación: «kappa ≥ 0,4 (mínimo) con
  objetivo 0,6; hallazgos y desacuerdos documentados caso por caso».
- **§5.3:** «kappa de Cohen entre el pre-diagnóstico del sistema y el del
  médico sobre 20 a 30 casos con imagen y viñeta clínica»; «calificación de 1 a
  5 del médico sobre corrección, utilidad y lenguaje del pre-informe».
- **§5.2:** «verificación con pacientes simulados de prevalencia y razones de
  verosimilitud conocidas; la probabilidad posterior calculada debe coincidir
  con la del generador de casos».
- **§5.4:** «latencia de extremo a extremo: desde que el profesional sube la
  radiografía hasta que recibe el pre-informe» y «latencia de inferencia de la
  CNN en la CPU del VPS».
- **§5.5, KPI 1:** «reducción del tiempo de triaje inicial, medida en
  simulación con el médico evaluador (tiempo con y sin copiloto sobre el mismo
  set de casos)». KPI 2: «disminución de derivaciones innecesarias a
  radiología, estimada como porcentaje de placas sin opacidad correctamente
  filtradas».
- **Tabla de umbrales de §5.7** (sin numerar en el documento; su Registro de
  cambios la llama «Tabla 8»), mínimo / objetivo: recall 80 / 85 %,
  especificidad 70 / 75 %, AUC 0,85 / 0,88, precisión y recall de extracción
  80 / 85 %, kappa 0,4 / 0,6, latencia de extremo a extremo 8 s / 3 s,
  reducción del tiempo de triaje 20 / 40 %.
- **Registro de cambios, 23-sep:** el criterio de H3 se unificó en «recall ≥
  85 %, especificidad ≥ 70 % (objetivo 75 %) y AUC ≥ 0,85», y se declaró la
  frontera: no existe punto con recall ≥ 0,85 y especificidad ≥ 0,75 a la vez
  (`docs/frontera-recall-especificidad.md`).
- **§6.3 y §7.8:** el médico dispone de «una sesión de 2 horas en la semana
  4»; **§9.1:** 5 h totales del médico, ad honorem.
- **§7.4 (alcance excluido):** «interfaz web» y «auditoría formal de sesgo por
  sexo y edad». **§7.6:** «casos sintéticos (imagen pública + viñeta clínica)
  para demostración y validación». **§7.8:** «no se utilizan datos de pacientes
  reales en ninguna fase». **§7.9:** «kappa con el médico ≥ 0,4» entre los
  criterios de aceptación; **§5.7:** «si al cierre no se alcanzan, se documenta
  la causa y el trabajo futuro».
- **§9.4 y Anexo D:** «repositorio GitHub privado (se hace público en la
  semana 6)»; **tabla de hitos, H8:** «informe final + video de sustentación +
  repositorio GitHub **público**». **§10.3:** «la semana 6 no admite código
  nuevo, solo documentación y grabación»; H7 «tiene fecha alterna en la semana
  5», con «resultados presentados a la tutora en la tutoría del sábado
  siguiente».
- **Tabla de hitos:** la logística de H7 es del **Product Owner**. **H6 y
  §9.1:** el médico «valida el mapeo de 10 frases al vocabulario clínico» y
  «aporta vocabulario coloquial de consulta».
- **Tabla de alcance:** «Normalización de lenguaje coloquial a conceptos
  clínicos — Implementada (piloto)», «Combinación bayesiana síntomas + imagen —
  Implementada (piloto)», «Validación con médico general — Implementada
  (piloto)», «Mapa de calor Grad-CAM en el informe — Opcional, si sobra
  tiempo».

Dos decisiones del equipo (27-sep) que el spec absorbe: **no habrá piloto con
pacientes reales** —no lo prometió la Semana 1 (§7.8 lo excluye); lo pidió SP3
§19 para poder afirmar exactitud clínica, y no hay tiempo de conseguir datos
emparejados— y **el repositorio no se hace público**: se comparte por
invitación, sin ninguna cadena que identifique al cliente, a la empresa ni a
los integrantes (§6.1; el coste en la rúbrica del curso, en §6.7).

## 3. El riesgo que SP3 y SP4 dejaron abierto, y qué se puede cerrar

SP3 §19: *«no existen datos reales que emparejen imagen y clínica»*. SP4 §12:
*«afirmar que la combinación acierta necesita datos emparejados reales o un
piloto prospectivo»*.

Lo que existe públicamente, medido el 27-sep:

| Fuente | Qué empareja | Por qué no |
| :--- | :--- | :--- |
| MIMIC-IV-ED + MIMIC-CXR | temperatura, pulso, antecedentes y diagnósticos con la placa (3 de los 5 predictores; sin auscultación) | credencial de PhysioNet (curso CITI + solicitud de días a semanas). La cuenta está creada; **queda como trabajo futuro** |
| Datasets de COVID con metadatos (Cohen, BIMCV) | temperatura en pocos casos | sin auscultación, muestras pequeñas y de otra enfermedad |
| Cualquier dataset público de tórax | — | **ninguno trae auscultación** (crepitantes, murmullo) |

Conclusión: la exactitud clínica real de la combinación **no se puede medir en
este proyecto**. Lo que sí se puede medir, y no está medido en ningún sitio:

1. Si la aritmética del sistema reproduce, caso a caso, la posterior de un
   generador con prevalencia y RV conocidas (lo que la Semana 1 §5.2 prometió
   literalmente).
2. Cuánto se desvía la posterior de independencia de la del generador **si** la
   clínica y la imagen dependen entre sí en distintos grados y direcciones, y
   dónde queda la verdad del generador respecto a la horquilla que entregamos.
3. Cuánto desplaza la calibración un previo distinto del de la población.

Eso es lo que hace el §4. Nada de ello es exactitud clínica, y así se escribe.

## 4. Validación cuantitativa sobre un emparejamiento declarado

### 4.1. El principio: lo sintético es el emparejamiento, y se declara qué se supone

Inventar síntomas correlacionados con la etiqueta y luego «validar» Bayes es
validar la invención (SP3 §19). Aquí:

- **Placas y verdad:** las 3 811 placas del conjunto de prueba de RSNA (una
  placa por paciente; 844 positivas, prevalencia 0,2215), particionado por
  paciente y nunca usado para entrenar ni calibrar, con su etiqueta real de
  opacidad. Es un **desenlace análogo** al de Heckerling (infiltrado
  radiográfico) en una **población distinta**: RSNA no es una cohorte con
  sospecha de neumonía. Las puntuaciones crudas del modelo desplegado están
  cacheadas en `pruebas/crudas_prueba.csv` (regenerable, con el hash de los
  pesos al lado): no hace falta reinferir.
- **Clínica:** a cada placa se le sortea la **puntuación de Heckerling** dada
  su etiqueta, con las frecuencias publicadas de la cohorte de derivación
  (§4.2). No se inventa la exactitud de la regla: se usa la publicada, tal como
  la usa el sistema. **Lo que sí es un supuesto es la estructura de
  dependencia** entre clínica e imagen: nula en el escenario 0 y barrida en los
  demás (§4.5). Se declara como tal.
- **Transporte:** el generador **supone** que la distribución de la puntuación
  por clase, medida en Illinois en 1990, se transporta al espectro de RSNA. Eso
  no se comprueba ni se puede comprobar aquí, y se escribe.

### 4.2. El generador

Por placa, con semilla fija:

1. **Puntuación** `k ∈ {0..5}` sorteada de `P(k | etiqueta)` con los recuentos
   de SP4 §4 (PMC7422644, tabla 2): con neumonía 1/11/28/42/37/15 sobre 134;
   sin neumonía 48/316/232/149/30/5 sobre 780. Así la RV verdadera de cada
   puntuación en el generador es el cociente exacto de recuentos (0,1213;
   0,2026; 0,7025; 1,6408; 7,1791; 17,4627), y la del sistema es la publicada
   redondeada (0,12; 0,20; 0,70; 1,64; 7,18; 17,5). La diferencia máxima es
   0,013 en log-odds (k = 1) y es conocida.
2. **Reparto de los `k` puntos en hallazgos**, con una regla declarada que solo
   afecta a la redacción de la viñeta y al oráculo de `asma = no_se`: el punto
   de «sin asma» se asigna con probabilidad 0,9 cuando `1 ≤ k ≤ 4` (con `k = 0`
   el asma está presente; con `k = 5`, ausente); los puntos restantes se
   reparten en un subconjunto uniforme de los cuatro signos. Con esto la
   prevalencia de asma en la simulación queda en torno al 10 % entre los
   positivos y al 15 % entre los negativos (14 % en total), más alta entre los
   negativos, como corresponde a un predictor negativo.
3. **Temperatura y pulso como números**, porque el sistema corta en Python y
   ese camino hay que ejercitarlo. Temperatura con **una décima** de
   resolución y pulso **entero**: si el hallazgo está presente, uniforme sobre
   {37,9; 38,0; …; 39,5} °C y {101; …; 130} lpm, y **con probabilidad 0,2
   exactamente el valor inmediatamente superior al corte** (37,9 °C; 101 lpm);
   si está ausente, uniforme sobre {36,0; …; 37,8} °C y {60; …; 100} lpm, y
   con probabilidad 0,2 **exactamente el corte** (37,8 °C; 100 lpm). Una décima
   y un latido de margen: un `>` cambiado por `>=` en un corte cambia la
   puntuación en ≈ 0,2 × P(hallazgo ausente) ≈ 14 % de los casos; mover el
   corte de temperatura a 38,0 °C, en ≈ 7,5 %; y basta un caso para que la
   prueba del §8 falle, porque compara caso a caso.
4. **Asma desconocida (`no_se`)** en el 10 % de los casos, al azar e
   independiente de todo lo demás (falta completamente al azar, MCAR). El
   sistema entrega entonces dos puntuaciones; el oráculo marginaliza el asma
   con la misma información (§4.5).
5. **Previo del generador:** la prevalencia del conjunto, 0,2215 (§4.3).

### 4.3. La prevalencia: el previo correcto en la simulación es el de su población

El conjunto tiene 22,15 % de positivos; el sistema desplegado arranca con
`PREVALENCIA_LOCAL = 0,1466` (cohorte de Heckerling). **El análisis principal
usa 0,2215**, porque es la prevalencia de la población simulada; esto **no**
recomienda configurar el despliegue con ese valor: SP4 §5 sigue vigente
(0,2215 es la prevalencia de un dataset de un reto, no de ningún servicio).

**Sensibilidad al previo:** declarar 0,1466 en una población de 0,2215 tiene un
efecto analítico: todas las odds posteriores se multiplican por 0,604, es
decir, se desplazan −0,50 en log-odds por igual. La simulación lo traduce a
lo que le sirve a quien despliegue: Brier, ECE, intercepto de calibración (que
debe salir ≈ +0,50) y **cuántos casos cambian de banda** (< 20 / 20-70 / > 70
%). El AUC no cambia y no se reporta en esa tabla. Solo tabla, sin curvas.

### 4.4. Escenario 0: la aritmética, caso a caso

Con dependencia nula (`ρ1 = ρ0 = 0`, §4.5), el oráculo de cada caso es

    logit P(Y = 1 | q, k) = q + ln RV_recuentos(k),   q = logit p_cal

donde `p_cal` es la probabilidad calibrada de la imagen (SP2) y `k` es la
puntuación verdadera que el generador sorteó en el paso 1 del §4.2. El oráculo
**toma `p_cal` como la verdad de la imagen**; así la diferencia sistema −
oráculo aísla la parte clínica, y la calibración de `p_cal` en el conjunto de
prueba se reporta aparte, como suelo (en la revisión del 27-sep se midió del
orden de ECE ≈ 0,014 por deciles y pendiente ≈ 0,98; el script la vuelve a
medir y esa es la cifra que se publica).

Tres comprobaciones **deterministas**:

- **0A.1, puntuación** (casos con asma conocida, ~90 %):
  `combinacion(...)["puntuacion"][0] == k`. Ejercita los cortes estrictos y la
  validación de hallazgos.
- **0A.2, bloque** (todos los casos): `independencia[i] == round(combinar(p,
  rv_clinica[i], rv_imagen), 4)`; si `concordantes`, `dependencia[i] ==
  round(combinar(p, mas_informativa(rv_clinica[i], rv_imagen), 1.0), 4)`; y
  `minima` / `maxima` son el mínimo y el máximo de esos valores redondeados. El
  constructor del bloque no altera la aritmética.
- **0A.3, coherencia con el generador** (los 3 811 casos, con la `k` verdadera
  en los dos lados, también cuando el asma está oculta): `|logit combinar(0,2215,
  RV_publicada(k), RV_imagen) − logit oráculo| ≤ 0,015`, sobre la aritmética
  sin redondear. La tolerancia cubre exactamente el redondeo de las RV
  publicadas (máximo 0,013). Una RV mutada (17,5 → 1,75; 7,18 → 7,81; 1,64 →
  1,46) rompe la desigualdad en todos los casos con esa puntuación (por 2,30,
  0,084 y 0,117 en log-odds); un corte mutado rompe 0A.1 en el 7-14 % de los
  casos. **Es una prueba, no una estadística: la mutación se aplica y se
  espera el fallo.** La marginalización del oráculo de `no_se` se prueba
  aparte (§8).

Esto cumple literalmente la promesa de la Semana 1 §5.2. Lo que **no**
demuestra: que la posterior sea exacta en pacientes; solo que el sistema
calcula lo que dice calcular.

**0C, optimismo de la derivación (analítico):** SP4 §4.1 eligió las RV de la
derivación sobre las bandas de validación externa (0-1 → 0,19; 2-3 → 1,04;
4-5 → 8,33). La diferencia `ln RV_derivación − ln RV_validación` por
puntuación es fija: −0,46; +0,05; −0,40; +0,46; −0,15; +0,74 (k = 0..5). La
derivación es más extrema que la validación en k = 0, 2, 3 y 5 y menos en
k = 4: el «optimismo» no es uniforme. Se reporta la tabla completa y
**cuántos casos del conjunto cambiarían de banda** si el sistema usara las
bandas de validación. Es un cálculo, no un experimento, y se rotula así.

**0B, coherencia entre fuentes (opcional, primer recorte):** sortear los cinco
hallazgos por separado con la sensibilidad y especificidad por hallazgo del
metaanálisis de Ebell 2020 (Acad Emerg Med 27(7):541-553, PMID 32329557;
Metlay 1997 como contraste), bajo independencia, y publicar la tabla de RV por
puntuación que ese generador implica junto a la de Heckerling, más la
calibración de la clínica sola y de la combinación, **sin esperar que salgan
calibradas**: mide cuánto difieren las RV de Heckerling de las que implican las
exactitudes marginales publicadas. Solo se hace si el PDF de Ebell está en
manos del equipo antes del 1-oct (la descarga automatizada topó con la
verificación anti-bots el 27-sep y no se sortea: lo descarga una persona, por
la biblioteca de la universidad). Para el asma no hay sensibilidad ni
especificidad accesibles (SP4 §4.1: el artículo primario no se pudo leer); si
0B se hace, el asma va con RV = 1 y se dice.

### 4.5. Dependencia condicional: dos parámetros, dirección como resultado

Es la pregunta que SP4 §7 dejó abierta: crepitantes, murmullo y opacidad son el
mismo fenómeno físico visto de dos maneras. El sistema solo ve la puntuación,
y los recuentos de Heckerling no la descomponen por hallazgo; por eso la
dependencia se induce **sobre la puntuación entera**, y se interpreta así: `ρ_y`
es la correlación latente, **dentro de la clase `y`**, entre lo que la
puntuación mide y lo que la imagen mide. Como temperatura, pulso y asma
diluyen esa correlación, un `ρ` de 0,6 sobre la puntuación es un caso extremo,
no plausible.

**Modelo de umbral latente ordinal**, definido para que `P(k | y)` se conserve
exacta:

- `q_i = logit p_cal(cruda_i)`. Para cada clase `y`, `F̂_y` es una función
  definida sobre **todo `q` real**, no solo sobre las placas de la clase:
  `F̂_y(q) = (#{j ∈ y : q_j < q} + ½ · #{j ∈ y : q_j = q}) / n_y`, acotada a
  `[0,5/n_y ; 1 − 0,5/n_y]` (la cota solo actúa cuando `q` cae fuera del
  recorrido de la clase, lo que ocurre al evaluarla en placas de la otra
  clase). `z_y(q) = Φ⁻¹(F̂_y(q))`. En las placas de la propia clase, `F̂_y`
  coincide con su rango medio, que es lo que usan el latente del generador, la
  bisección de los umbrales y la prueba de correlación; **el oráculo, en
  cambio, evalúa para cada placa las dos, `z_1(q_i)` y `z_0(q_i)`, sea cual sea
  su etiqueta: es función de `(q, k)` y nunca de `y`.** Usar el rango medio de
  la placa dentro de su propia clase para las dos densidades es un error que
  pasa todas las pruebas de `ρ = 0` y de marginales, y da fracciones de log-RV
  conservado > 1 en todas las celdas simétricas: invierte la conclusión. El
  rango medio resuelve además los empates (674 valores distintos de `p_cal` en
  3 811 placas; el mayor grupo reúne 437).
- Latente: `u_i = ρ_y · z_y(q_i) + √(1 − ρ_y²) · ε_i`, `ε ~ N(0,1)`;
  `k_i = #{j : u_i > τ_{y,j}}`, `j = 1..5`.
- **Umbrales resueltos numéricamente** (bisección) para que, en cada clase, la
  media sobre las placas de `Φ((τ_{y,j} − ρ_y z_y(q_i)) / √(1 − ρ_y²))` sea
  exactamente `P(k ≤ j − 1 | y)` de los recuentos. Así los empates no mueven
  las marginales. Con `ρ_y = 0`, `τ_{y,j} = Φ⁻¹(P(k ≤ j − 1 | y))` y el
  escenario es el 0A.
- **Oráculo en forma cerrada**, sin Monte Carlo, con el **mismo conjunto de
  información que el sistema** `(q, k)`:

      P(k | q, y) = Φ((τ_{y,k+1} − ρ_y z_y(q)) / s_y) − Φ((τ_{y,k} − ρ_y z_y(q)) / s_y),
      s_y = √(1 − ρ_y²),  τ_{y,0} = −∞,  τ_{y,6} = +∞
      logit P(Y = 1 | q, k) = q + ln P(k | q, 1) − ln P(k | q, 0)

  con `z_1(q)` y `z_0(q)` evaluadas en el mismo `q` de la placa. Para `asma =
  no_se` el sistema ve la puntuación de los cuatro signos `k4` y el oráculo
  condiciona en `(q, k4)`: `P(k4 | q, y) = Σ_k P(k | q, y) · P(k4 | k)` con la
  regla de reparto del §4.2 (`P(k4 = k | k) = P(asma presente | k)`, `P(k4 =
  k − 1 | k) = P(asma ausente | k)`). El asma falta al azar, así que su
  ausencia no informa.

**Rejilla:** `ρ1` (entre enfermos) y `ρ0` (entre sanos) en `{0; 0,15; 0,3;
0,45; 0,6}`, 25 celdas, todas en forma cerrada. Se destacan en el informe
**seis celdas**: dos de la diagonal simétrica, `(ρ1, ρ0) = (0,3; 0,3)` y
`(0,6; 0,6)`; dos del eje «solo entre enfermos», `(0,3; 0)` y `(0,6; 0)`; y
dos del eje «solo entre sanos», `(0; 0,3)` y `(0; 0,6)`. El origen `(0; 0)` es
0A y se cuenta aparte. Son «las seis celdas destacadas» a las que remiten
§4.6, §6.6 y §11. **Por qué dos parámetros:** con un `ρ` simétrico la dirección
del sesgo queda decidida de antemano —una placa muy positiva es mediana entre
los enfermos pero extrema entre los sanos, así que la RV condicional de la
puntuación baja y la independencia «exagera» por construcción—; si la
dependencia vive solo entre enfermos («las consolidaciones grandes se ven y se
oyen más»), la RV condicional sube y la independencia **se queda corta**. La
dirección es un resultado de la celda, no una premisa del diseño.

**Escala legible:** en cada celda se publica, por puntuación, la mediana y los
cuartiles de `ln[P(k | q, 1) / P(k | q, 0)]` en log-odds, **estratificados por
lado de la imagen** (RV de imagen ≥ 1 y < 1, la misma partición que define la
concordancia), y al lado la fracción `ln[P(k | q, 1) / P(k | q, 0)] / ln
RV_recuentos(k)` —**qué fracción de su log-RV conserva la puntuación una vez
vista la imagen**— con sus cuartiles y la proporción de placas con signo
invertido (fracción < 0). Para k = 2 y k = 3 la fracción se rotula «poco
informativa (|ln RV_recuentos| < 0,5)»: dividir por −0,353 o +0,495 amplifica
cualquier variación, y con `ρ > 0` el signo se invierte en una parte de las
placas. Las etiquetas «moderada/fuerte» se retiran; cada celda se nombra por
sus dos `ρ` y por la fracción mediana de las puntuaciones extremas (k ≤ 1 y
k ≥ 4), separada por lado de la imagen. La dirección del sesgo se lee por
lado, no global: en la misma celda la puntuación puede conservar más de su
log-RV en un lado y perderlo o invertirlo en el otro.

**Qué cambia y qué no**, y se prueba (§8): `P(k | y)` no cambia: la media sobre
las placas de la clase de `P(k | q_i, y)` reproduce los recuentos en forma
cerrada (por construcción, ±10⁻⁹). La correlación **de Pearson** dentro de la
clase `y` entre `k` y `z_y(q)` coincide con la que implica el modelo, `r_y =
Cov_y / (sd(k | y) · sd(z_y))`, calculada en forma cerrada sobre las placas de
la clase: `Cov_y = (1/n_y) Σ_i z_i · E[k | q_i, y] − z̄_y · E[k | y]`, con
`E[k | q_i, y] = Σ_{j=1..5} [1 − Φ((τ_{y,j} − ρ_y z_i) / s_y)]`, `sd(k | y)` de
los recuentos y `sd(z_y)` empírica. Si `z` fuera exactamente N(0,1) se
reduciría a `ρ_y Σ_j φ(τ_{y,j}) / sd(k | y)`; con los empates del conjunto
(`sd(z_0) ≈ 0,96`) esa aproximación difiere del exacto hasta en 0,012, así que
la prueba compara contra el exacto. Valores esperados, medidos el 27-sep:
≈ 0,275 (y = 0) y 0,286 (y = 1) con `ρ = 0,3`; ≈ 0,558 y 0,574 con `ρ = 0,6`.
Lo que cambia es la RV de la puntuación condicionada a la imagen, que es el
objeto del escenario. Con `ρ = 0` la correlación **dentro de cada clase** es
0; sobre todo el conjunto no lo es, porque `k` y `q` se correlacionan a través
de la etiqueta.

### 4.6. Qué se mide

Sobre el conjunto de prueba, con **bootstrap de B = 1 000 réplicas**: cada
réplica remuestrea con reemplazo las 3 811 placas (una por paciente, así que es
un bootstrap por paciente) y vuelve a sortear la clínica con la semilla `b`.
`z_y`, los umbrales `τ` y el calibrador **quedan fijos**, calculados una vez
sobre el conjunto completo: solo se remuestrean placas y se resortea la
clínica, para que el generador sea el mismo en todas las réplicas. Intervalos
del 95 % por percentiles. Las diferencias entre modelos se calculan **dentro
de cada réplica** (pareadas). El oráculo cerrado hace que todo cueste segundos;
el bootstrap completo se corre en las seis celdas destacadas (§4.5) y en 0A;
el resto de la rejilla se publica sin intervalos.

**Cuatro modelos puntuales** (casos con asma conocida; los `no_se` van aparte):

| Modelo | De dónde sale |
| :--- | :--- |
| imagen sola | `p_cal` |
| clínica sola | `combinar(0,2215, RV_publicada(k), 1)` |
| combinación, independencia | `combinacion(...)["independencia"][0]` |
| combinación, extremo conservador | `dependencia[0]` si `concordantes`, si no `independencia[0]` |

El código de validación lee `independencia` y `dependencia`, **nunca `minima`
ni `maxima`** para los modelos puntuales: con concordancia la independencia es
el extremo más alejado del previo en la dirección de la evidencia (`maxima` si
las RV son ≥ 1, `minima` si son < 1, porque `|ln a + ln b| ≥ máx(|ln a|, |ln
b|)` cuando `a` y `b` están del mismo lado de 1), y sin concordancia es el único
valor.

**Métricas por modelo:** AUC; Brier; **pendiente e intercepto de
calibración** —la pendiente, de la regresión logística de `Y` sobre `logit p`
(pendiente < 1 es la forma cuantitativa de «exagera»); el intercepto, de la
calibración global con la pendiente fijada en 1, que es el que da ≈ +0,50 en
la sensibilidad al previo—; ECE con 10 bins de igual masa, por cuantiles de
rango con los empates de `p` rotos por el orden de `patientId` (declarado),
publicada **al lado de su suelo de ruido** (etiquetas simuladas `Bernoulli(p)`
del propio modelo, 200 veces: media y percentil 95) y nunca contra un umbral
absoluto; curva de fiabilidad por deciles. **Pareadas:** ΔAUC, ΔBrier y
Δpendiente de cada uno de los dos modelos combinados frente a la imagen sola,
con su intervalo.

**La horquilla** `[minima, maxima]`, solo donde existe (casos **concordantes**
con asma conocida), frente al oráculo de la celda, sobre los extremos **sin
redondear** (`combinar`):

- **Posición** `λ = (logit oráculo − logit dependencia) / (logit independencia
  − logit dependencia)`: mediana y cuartiles. Con `Δ = logit independencia −
  logit dependencia = 0` (RV de imagen exactamente 1, que el calibrador
  desplegado no produce) el caso se cuenta como «sin horquilla».
- **Colas:** fracción de casos en que el oráculo queda más allá del extremo
  conservador en más de `ε` log-odds (`λ < −ε/|Δ|`) y más allá de la
  independencia en más de `ε` log-odds (`λ > 1 + ε/|Δ|`), con **`ε = 0,015`,
  la misma tolerancia que 0A.3**: el redondeo máximo de las RV publicadas. Sin
  esa tolerancia, en 0A la RV publicada 1,64, menos extrema que la exacta
  1,6408, pondría al oráculo 0,0005 log-odds más allá de la independencia en
  todos los concordantes con k = 3 e imagen a favor (~13 % de los
  concordantes) y se leería como «la independencia se queda corta» con
  dependencia nula.
- **Contención:** fracción de casos con `λ ∈ [−ε/|Δ|, 1 + ε/|Δ|]`, el
  complemento de las dos colas. Se llama contención y no cobertura: no es un
  intervalo de confianza. **La fila 0A es la comprobación de la métrica: sus
  dos colas deben ser exactamente 0 y su contención 100 %**, porque con `ρ = 0`
  el único desvío entre sistema y oráculo es el redondeo de las RV.
- **Casos discordantes** (`dependencia` nulo, un solo número): fila aparte con
  el error `|Δ logit|` mediano y el sesgo (signo de sistema − oráculo).
- **Casos `no_se`:** fila aparte: si el oráculo marginal cae en `[minima,
  maxima]` (con la misma `ε`), y el error frente al punto medio en log-odds de
  las dos posteriores de independencia.
- La tabla dice **cuántos casos hay de cada tipo** en cada celda.

**Hipótesis a refutar, celda a celda,** con la expectativa declarada antes de
correr nada: *«el oráculo queda dentro de la horquilla en ≥ 90 % de los
concordantes»*. Con el oráculo bien evaluado, la expectativa medida el 27-sep
sobre el conjunto es que solo se sostenga en 0A y en las celdas más suaves:
con dependencia simétrica una parte grande de los concordantes cae por el lado
conservador (`λ < 0`), y con dependencia solo entre enfermos, por el lado de la
independencia (`λ > 1`) en los concordantes positivos. La dirección y la
magnitud se publican por celda y por lado de la imagen. Una contención baja es
un resultado igual de publicable y obliga a repensar la cota en el informe,
no a ocultarla.

**Sensibilidad al previo:** la tabla del §4.3 con 0,1466, en 0A y en las seis
celdas destacadas.

La combinación se calcula llamando a `heckerling.combinacion` y
`heckerling.combinar` —el mismo código que sirve el contenedor—, nunca a una
reimplementación.

### 4.7. Lo que puede afirmar y lo que no

Puede afirmar: que el sistema reproduce caso a caso la posterior del
generador (0A); que, **si** la puntuación tiene la exactitud publicada y es
condicionalmente independiente de la imagen, la aritmética y la calibración de
la imagen dan una posterior calibrada en el conjunto de prueba de RSNA; cuánto
se desvía la independencia de la del generador **bajo cada supuesto de
dependencia**, en qué dirección, y dónde cae el oráculo respecto a la
horquilla; cuánto desplaza la calibración un previo equivocado. **No puede
afirmar** exactitud clínica real ni cuánto aporta la clínica en pacientes: las
viñetas no son pacientes, la exactitud es la publicada y la dependencia es la
supuesta. Se escribe así en el informe, en el acta y en la tabla «prometido
vs. entregado».

### 4.8. Dónde vive

- `src/copiloto_triaje/validacion/`: `generador.py` (puntuación, reparto,
  números, asma, umbral latente), `oraculo.py` (umbrales y posterior en forma
  cerrada), `metricas.py` (AUC, Brier, pendiente e intercepto, ECE con suelo,
  fiabilidad, posición, colas y contención, bootstrap). `fuentes_ebell.py` solo
  si 0B se hace.
- `scripts/validar_combinacion.py`: corre 0A, 0C, la rejilla y la sensibilidad
  al previo sobre `docs/validacion-semisintetica/crudas_prueba.csv` (copia
  **congelada** de la caché, con el `sha256` de los pesos que la generaron; el
  script comprueba el hash y lo escribe en los resultados) y
  `servidor/calibrador.json`; deja en `docs/validacion-semisintetica/` las
  tablas, las curvas a 300 DPI y `resultados_simulacion.json`. Con la copia
  congelada, un tercero reproduce todos los números **sin los pesos**.
- `docs/validacion-semisintetica-sp5.md`: el análisis, con todas sus cifras
  leídas de `resultados_simulacion.json` (ninguna tecleada) y los límites del
  §4.7.
- Todo artefacto de resultados de esta sección cumple la **regla de rótulo del
  §6.7.7**: ruta bajo `docs/validacion-semisintetica/` y «simulación
  semisintética» en el título.

Lo que **no** se hace: reentrenar ni recalibrar la CNN, ni ajustar las RV ni la
prevalencia con estos datos. Solo se mide.

## 5. La sesión con el médico (H7)

### 5.1. Casos

24 casos (dentro de los 20-30 prometidos; subir a 30 reduce el error típico
del kappa ~10 % y cuesta media hora más del médico, así que 24) del conjunto de
prueba de RSNA, elegidos con semilla por `preparar_sesion.py` y listados en el
acta por `patientId`, con estratos deliberados:

| Estrato | Casos | Definición |
| :--- | ---: | :--- |
| positivas claras | 8 | etiqueta 1 y RV de imagen ≥ 5 |
| negativas claras | 8 | etiqueta 0 y RV de imagen ≤ 0,2 |
| banda contradictoria | 4 | cribado positivo (cruda sobre el umbral de cribado) y RV < 1: donde el sistema avisa de discrepancia |
| asma «no sé» | 4 | cualquier etiqueta; el asma se fija en `no_se`: donde el sistema entrega dos puntuaciones |

Dentro de cada estrato, mitad con clínica **concordante** y mitad
**discordante** según el propio bloque `combinacion` del sistema, para que el
kappa no lo inflen los casos fáciles; se sortea clínica hasta llenar las
cuotas. La clínica de cada caso sale del generador del §4 con `(ρ1, ρ0) =
(0,3; 0,3)` y semilla fija —una elección declarada: ni independiente de la
placa, que daría muchas viñetas incoherentes, ni copia de ella—. Se añaden **3
casos de práctica**, fuera de los 24, para fijar las bandas con el médico al
inicio de cada lectura.

**La viñeta:** edad, sexo y proyección de la cabecera de RSNA; los cinco
hallazgos con temperatura y pulso como números; y los síntomas referidos del
cuestionario del paciente de SP3, que son **los mismos en los 24 casos** (los
valores fijos de `reproducir_casos.SINTOMAS`) salvo el asma, que sale del
generador, y la fiebre referida, que sigue a la temperatura medida (no puede
decir «sin fiebre» con 38,6 °C). Se le dice al médico que los síntomas
referidos son un fondo constante. Así ningún síntoma inventado entra en su
juicio y no en el del sistema.

### 5.2. Qué responde el médico

Por caso, en el formulario (nunca en Telegram):

1. **Probabilidad de que la placa muestre una opacidad o infiltrado compatible
   con neumonía**, que es el desenlace del sistema (SP4 §8.1: no se habla de
   «neumonía»), en dos formas: la **banda** —baja (< 20 %), intermedia (20-70
   %), alta (> 70 %)— y un **porcentaje entero de 0 a 100**. El porcentaje
   permite un acuerdo continuo y recalcular con otros cortes. Los cortes 20 y 70
   son **una convención del equipo fijada el 27-sep, antes de ver datos**, para
   separar «no estudiar más / estudiar / tratar»; no son un estándar publicado.
2. En las lecturas **con** mensaje: **tres notas de 1 a 5** —corrección,
   utilidad y lenguaje del pre-informe—, que es lo prometido en §5.3.
3. Comentario libre.

### 5.3. La categoría del sistema, definida antes de la sesión

**Regla primaria:** la banda del **punto medio en log-odds** de `[minima,
maxima]` del bloque `combinacion` de cada caso (guardado en `consultas` o, en
el camino de respaldo del §5.6, en los ficheros del formulario), convertido a
porcentaje y redondeado a entero **hacia arriba en ,5** (`floor(x + 0,5)`,
como `Math.round` en el nodo `Desenlace`); bandas `[0, 20)` baja, `[20, 70]`
intermedia, `(70, 100]` alta. **Análisis de sensibilidad fijados de
antemano:** la banda del extremo de independencia, la del extremo conservador,
y la regla «si la horquilla cruza un límite, intermedia» con el número de casos
que cruzan. Con las tablas actuales ninguna horquilla cruza a la vez el 20 % y
el 70 % (barrido de RV de imagen 0,016-77,3 × 48 combinaciones de hallazgos ×
dos previos, 27-sep); tiene explicación analítica —el cociente de odds de los
dos extremos vale `min(RV_clínica, RV_imagen) ≤ 17,5`, y cruzar 20 y 70 % a
la vez exige además `odds_previas × max(RV_clínica, RV_imagen) < 0,25`, lo que
solo ocurre con prevalencia declarada por debajo de ≈ 2,6 %— y una prueba lo
afirma con los dos previos y con el umbral analítico (§8). Como
`PREVALENCIA_LOCAL` es configurable, la regla «cruza → intermedia» del análisis
de sensibilidad cubre el caso si algún despliegue lo produjera. Los mensajes
de la sesión se generan con la prevalencia desplegada, **0,1466**, y el acta
lo dice: la categoría del sistema en la sesión usa el previo del despliegue,
no el del §4.

### 5.4. Diseño: dos lecturas del mismo conjunto

El kappa prometido es «entre el pre-diagnóstico del sistema y el del médico»,
así que exige el juicio **sin ayuda**; y el KPI 1 promete el tiempo «con y sin
copiloto sobre el mismo set de casos». Un diseño por bloques de casos
distintos no cumple ninguna de las dos cosas y, con un solo lector, confunde
condición con casos y con periodo. Por eso:

- **Lectura 1 (6, 7 u 8-oct):** los 24 casos **sin copiloto** (placa +
  viñeta): banda, porcentaje, tiempo. **El kappa sale solo de aquí**, `n = 24`,
  juicio independiente.
- **Lectura 2 (13, 14 o 15-oct, exactamente 7 días o más después: 6 → 13, 7 →
  14, 8 → 15):** los mismos 24 casos, **una sola vez cada uno**, en otro orden
  aleatorio: **20 con el mensaje real del sistema** dentro del formulario
  (banda, porcentaje, tiempo, las tres notas, comentario) y **4 casos de
  control sin mensaje** (banda, porcentaje y tiempo, sin notas), intercalados
  sin que el médico sepa cuáles son. Los controles los sortea
  `preparar_sesion.py` **entre los dos estratos claros: dos de «positivas
  claras» y dos de «negativas claras», uno concordante y uno discordante en
  cada uno**, para que los dos estratos de 4 —que existen precisamente por lo
  que hace el mensaje del sistema— se lean completos con copiloto. El brazo
  con mensaje queda en 6/6/4/4 por estrato (3 concordantes y 3 discordantes en
  los claros). La lectura 2 tiene 24 pantallas, no 28: ningún caso se repite
  dentro de una lectura, para que el control mida releer a 7 días y no releer
  a cinco minutos.
- **Tiempo de triaje:** de abrir el caso a enviar la banda, marcado por el
  formulario. Análisis **pareado por caso** de `ln(tiempo)` sobre los **20
  pares** con mensaje (lectura 1 sin → lectura 2 con): razón de medias
  geométricas con intervalo por bootstrap de casos (BCa). La reducción medida
  mezcla el efecto del copiloto con el de releer y haber aprendido el
  formulario. Los **4 pares de control** (sin → sin) dan una **estimación
  descriptiva** del efecto de releer: se publican las cuatro razones
  individuales y su media geométrica, y se resta de la reducción medida como
  estimación, con su propio intervalo, sin llamarla cota. El mensaje añade
  texto que leer, y el tiempo puede subir: se reporta lo que salga.
- **Plan B, si el médico solo puede una sesión:** lectura secuencial caso a
  caso: primero banda, porcentaje y tiempo **sin** ayuda; después el formulario
  revela el mensaje y pide banda final, porcentaje final y las tres notas. El
  kappa sale de la primera respuesta; la reducción del tiempo **no se mide** y
  el KPI 1 pasa a «cumplido con cambio»: se reporta el tiempo adicional de leer
  el mensaje.
- **Los tiempos solo valen en presencia o por videollamada** con el formulario
  compartido; en modo asíncrono nada garantiza el ciego ni la medida. Si no
  hay presencia ni videollamada, la sesión sirve para el kappa y la utilidad, y
  el tiempo se declara no medido.
- **No hay fecha fuera del 6-16 oct** (disponibilidad del médico y semana 5 de
  la Semana 1): si la sesión no ocurre, H7 se declara **incumplido** con su
  causa. La «fecha alterna hasta el 23-oct» del borrador desaparece.

### 5.5. Kappa, utilidad, tiempo, y lo que 24 casos pueden decir

- **Primario:** kappa **ponderado lineal** sobre las tres bandas, sobre las 24
  lecturas sin copiloto. Se reportan también el **kappa de Cohen sin ponderar**
  —que es el prometido literalmente, y el que corresponde a la escala de Landis
  y Koch citada en la Semana 1— y el **kappa binario en «alta»**, la decisión
  que importa en triaje. Intervalos del 95 % por dos métodos: el analítico de
  Fleiss, Cohen y Everitt y bootstrap BCa (2 000 réplicas).
- **Texto fijado ya para el acta y el informe:** *«Con 24 casos y un solo
  evaluador, el intervalo del 95 % del kappa tiene una anchura de 0,5 a 0,6.
  El diseño no distingue una concordancia moderada (0,4) de una sustancial
  (0,6), ni generaliza a otros médicos ni a otro reparto de casos, que aquí es
  deliberado. El criterio ≥ 0,4 de la Semana 1 se evalúa sobre la estimación
  puntual y se publica siempre con su intervalo; si el límite inferior queda por
  debajo de 0,4, se dice.»*
- **Acuerdo continuo (secundario):** Spearman entre el porcentaje del médico y
  el punto medio del sistema; Bland-Altman en log-odds, con los porcentajes 0 y
  100 acotados a 0,5 y 99,5 antes del logit (y contando cuántas veces ocurre);
  fracción de casos en que el porcentaje del médico cae dentro de la
  horquilla.
- **Influencia del sistema:** kappa de la lectura 2 **sobre los 20 casos con
  mensaje**, y número de casos (de 20) en que el médico cambió de banda al ver
  el mensaje. No es concordancia independiente y se rotula así.
- **Cada desacuerdo caso por caso**, con el comentario del médico, como pide
  el hito.
- **Utilidad:** las tres notas sobre los 20 casos con mensaje, media y
  distribución.
- **Tiempo:** §5.4.

### 5.6. Los mensajes son los reales

Los genera `pruebas/reproducir_casos.py` con una entrada nueva, `--casos
casos.json` (por caso: `patientId`, signos y síntomas), que alimenta
`hallazgos_del_caso` y, en el modo con bots, los botones y los signos que se
teclean. **Camino por defecto:** con bots contra el VPS; el bloque
`combinacion` y `ms_extremo` quedan en `consultas`. Los nodos reales redactan
el texto y el servidor real calcula la combinación. Nada se escribe a mano.
**Respaldo, regla escrita** (ya no una referencia a un ledger ignorado por
git): sin túnel al VPS, `--sin-bots` contra la imagen local construida del tag
`h7-sesion` (`redactar.mjs` ejecuta `Leer respuesta` y `Desenlace` tal como
están exportados, así que el texto es el mismo); `preparar_sesion.py` guarda
entonces el bloque `combinacion` devuelto por el copiloto junto al mensaje en
los ficheros del formulario, y el acta cita el tag y el digest de la imagen.
En ninguno de los dos caminos la sesión mide la latencia de extremo a extremo
(§6.3). Los mensajes se generan el 5-oct y quedan congelados con el tag.

### 5.7. Ciego, honestidad y límites

El médico no ve la etiqueta de RSNA ni el escenario; sí sabe que la clínica es
simulada y que los síntomas referidos son constantes, y el acta lo dice. Un
solo médico es lo prometido y se declara como limitación (§5.5). Participa de
forma voluntaria; en los ficheros del proyecto figura solo como «médico general
colaborador», sin ningún dato personal. H7 se llama en el informe «sesión de
concordancia con un médico sobre viñetas semisintéticas»: el kappa mide
acuerdo con un evaluador, no exactitud.

### 5.8. Instrumentos

- `scripts/preparar_sesion.py`: elige los 24 + 3 casos, genera las viñetas,
  llama al arnés para obtener los mensajes reales, sortea los dos órdenes y
  los 4 controles, exporta las placas a PNG legible y escribe los ficheros de
  datos del formulario y la **clave** del evaluador (fuera del formulario).
- **El formulario** es el único instrumento de medida: un HTML local sin
  dependencias que muestra **dentro de él** la placa, la viñeta y, en los
  casos con mensaje de la lectura 2 (o tras la primera respuesta, en el plan
  B), el mensaje; un caso por pantalla, sin volver atrás; registra la hora de
  apertura y de envío de cada caso; guarda en el navegador por si se cierra;
  exporta un CSV. La réplica en Google Forms se descarta: no mide el tiempo
  por caso.
- El **dosier** en PDF queda como respaldo impreso, no como instrumento.
- `scripts/analizar_sesion.py`: lee los CSV de las dos lecturas y escribe
  `docs/validacion-semisintetica/sesion.json`: los tres kappas con sus dos
  intervalos, el acuerdo continuo, la influencia del sistema, la tabla de
  desacuerdos, las notas, los tiempos pareados y el efecto de releer.
- La **plantilla del acta** de H7, que se rellena desde `sesion.json`, con un
  apartado «Observaciones del médico»: el acta se le envía el 16-oct, sus
  observaciones se anexan sin editar, y se cierra con su conformidad o con la
  constancia de que no la envió.
- Un **ensayo completo** antes del 5-oct con un integrante del equipo como
  lector, para probar el formulario y los tiempos.

**Horas del médico:** reunión de preparación (~30 min) + dos lecturas de ~1 h
+ revisión del acta: 3-4 h, dentro de las 5 h que la Semana 1 §9.1 declaró.

La logística —fechas, participación voluntaria, videollamada o presencia—
corresponde al **Product Owner**, como dice la tabla de hitos de la Semana 1.
La **reunión de preparación** con el médico (prometida para la semana 3) fija
las dos fechas y hace la pregunta que SP3 §18 dejó para antes de H7: si en su
práctica el DICOM se obtiene del PACS. La respuesta va al acta. Los resultados
de H7 se presentan a la tutora en la tutoría del 17-oct, como pide la Semana
1.

## 6. El cierre (H8)

### 6.1. El repositorio que se comparte: nuevo, con historial limpio

Ninguna cadena que identifique al cliente, a la empresa ni a los integrantes en
lo que se comparte, ni en el texto ni en el historial. Anonimizar solo el
árbol de trabajo no basta: los 198 commits llevan el nombre y el correo del
equipo (con el dominio de la empresa), y los blobs antiguos contienen el
dominio del cliente y los nombres de sus contenedores y bots. Por eso:

- **Al tribunal se le da un repositorio nuevo**, en una cuenta u organización
  sin nombres, construido sobre una copia con `git filter-repo`
  (`--replace-text` con la lista, `--mailmap` a un autor neutro), que conserva
  el historial que la rúbrica valora (commits, ramas, tags). Si el historial
  reescrito no pasa la comprobación de abajo, se cae a un solo commit con el
  árbol limpio, y se dice.
- **El repositorio actual queda privado, sin invitados**, como traza de
  auditoría.
- **Comprobación antes de compartir** (`scripts/verificar_anonimato.py`,
  fuera de la suite): sobre **todos los blobs de todas las revisiones** y sobre
  autor, correo y committer de `git log --all`, ninguna huella de la lista.
- **Nombres y roles del equipo van en el informe del AVA y en los videos**, no
  en el repositorio: la regla de anonimato es del repositorio.

**Qué protege el anonimato y qué no.** La lista negra y la reescritura del
historial quitan *cadenas*: del cliente (dominio, red, contenedores, bots), de
la empresa (correo y dominio de los commits), de la máquina (usuario y rutas)
y de los integrantes (nombres y filiación personal). Protegen al cliente y a
la empresa de quedar ligados al proyecto, y dejan el texto y el historial sin
nombres propios para que el repositorio pueda clonarse, bifurcarse o
compartirse más adelante sin arrastrarlos. **No ocultan la identidad del
equipo** a quien tiene el repositorio: el README enlaza los dos videos, que
nombran a los integrantes (§6.4, §11.7), y remite la autoría al informe del
AVA (§6.7.5). Es una decisión, no una fuga: el repositorio no los nombra por
texto, y los videos son el único camino, revocables o no listados con
independencia del repositorio. Como los videos sí se comparten, **no nombran
al cliente ni muestran su infraestructura**: ningún nombre de contenedor ni
dominio en pantalla (regla de captura para el guion, §6.4).

**Inventario**, sacado del `grep` sobre los 104 ficheros versionados (27-sep),
con la decisión por fila:

| Qué | Dónde | Pasa a |
| :--- | :--- | :--- |
| dominio de n8n del cliente | `tests/conftest.py`, `pruebas/reproducir_casos.py`, `pruebas/verificar_webhooks.py` (valor por defecto) | **sin valor por defecto**: sin `N8N_URL` las pruebas conducidas se saltan |
| ídem | `n8n/copiloto-mantenimiento.json` (URL de las dos sondas), afirmado por `tests/test_mantenimiento.py` | marcador `https://n8n.ejemplo.test` y un paso de sustitución al importar, documentado en `docs/sp3-operacion.md`; la prueba afirma el marcador; **el export deja de ser idéntico byte a byte al desplegado**, y se dice |
| ídem | notas de los tres workflows, `docs/sp2-despliegue.md`, `docs/sp3-operacion.md`, spec y plan de SP3 | sustitución mecánica |
| red Docker del cliente | `servidor/docker-compose.yml`: la clave de la red lleva el nombre del cliente, y el nombre por defecto de `${RED_N8N:-…}` también | clave `red_n8n`; **`RED_N8N` obligatoria** (el compose falla sin ella); la guía de despliegue lo dice; requiere redesplegar el contenedor en el VPS (`down`/`up`) |
| contenedores, pila de mensajería y bots del cliente | `docs/sp2-despliegue.md` (lista de contenedores con sus nombres, su pila de mensajería), `docs/sp3-operacion.md`, spec SP3 (el bot del cliente y una credencial con nombre propio), `tests/test_flujo_profesional.py`, `servidor/docker-compose.yml` | «los N contenedores ajenos», marcadores neutros |
| nombres del equipo, la universidad como filiación personal | spec SP1, `notebooks/eda_rsna.ipynb`, «Windows de …» en `docs/sp3-operacion.md`, «máquina de …» en el plan SP4, este spec | «el equipo», «la máquina de desarrollo». La universidad se conserva **solo** como institución del curso en el README (decisión explícita; se puede quitar) |
| usuario de Windows en rutas absolutas | `pruebas/puntuaciones.py`, `pruebas/seleccionar_casos.py`, `tests/test_contrato_mcp.py` (código que se ejecuta) y 10 ficheros de docs y planes | variable **`RSNA_RAIZ` sin valor por defecto**; las pruebas que la usan se saltan sin ella; en docs, `<RSNA_RAIZ>`. Rutas relativas es además lo que pide la rúbrica |
| ciudad en el huso horario | `America/Guayaquil` en los tres workflows, `bd/esquema.sql`, `bd/limpieza.sql` y 4 pruebas | **se conserva**: es configuración funcional que identifica un huso horario, no al equipo; simplemente no entra en la lista negra |
| cuenta propietaria del remoto | `docs/sp2-despliegue.md` (URL de GitHub), configuración local | el repositorio nuevo vive en otra cuenta; las URL de docs apuntan a él |
| proveedor y ciudad del VPS, `chat_id` de prueba, correos | docs | quitados o marcadores |
| `docs/superpowers/**` (specs, planes) | sustitución **mecánica** de identificadores, sin reescribir la prosa |

**`tests/test_anonimato.py`** (en la suite, siempre corre): la lista negra
**no vive en el repositorio**; el repositorio lleva solo
`tests/anonimato/huellas.txt` con una huella SHA-256 por **token**.
Tokenización, idéntica para la lista y para los ficheros: minúsculas, sin
tildes, partición por cualquier carácter que no sea `[a-z0-9]` (una URL aporta
esquema, host y ruta troceados; `${RED_N8N:-x_y_network}` aporta `x`, `y`,
`network`; `C:\Users\u` aporta `c`, `users`, `u`). La lista en claro se
tokeniza igual y cada token da una huella; al regenerar se quitan a mano los
tokens genéricos que salgan (`https`, `com`, `users`, `network`, `n8n`). La
prueba recorre todos los ficheros de texto versionados, los tokeniza y falla
si aparece alguna huella. **Centinela:** `huellas.txt` incluye siempre la
huella del token público `centinelaanonimato7f3a`; la prueba lo escribe en un
fichero temporal dentro del recorrido y comprueba que lo detecta, así se
prueba a sí misma sin la lista. La lista en claro vive fuera del repo (fichero
ignorado o variable `ANONIMATO_LISTA`) y solo hace falta para regenerar las
huellas. **No hay lista blanca:** lo que se conserva, simplemente no entra en
la lista negra. Los binarios (PNG de `docs/eda`, salidas de los notebooks) se
revisan una vez a mano y se declara.

### 6.2. La tabla «prometido vs. entregado»

Fila por fila sobre la Semana 1, con evidencia (commit, prueba, medida) y una
de tres etiquetas: **cumplido**, **cumplido con cambio** (y el cambio),
**descopado** (y la razón). Para las métricas de la tabla de umbrales, que
tienen mínimo y objetivo, la etiqueta se evalúa contra los dos y lo dice:
**cumplido** = medido ≥ objetivo; **cumplido (mínimo)** = medido ≥ mínimo pero
< objetivo, o objetivo no evaluable con el diseño, con la razón. La evidencia
de esas filas cita la cifra medida y de dónde se lee, nunca solo el
sub-proyecto. Las filas y sus etiquetas provisionales, para que el informe no
las decida sobre la marcha:

| Promesa (Semana 1) | Etiqueta | Razón / evidencia |
| :--- | :--- | :--- |
| CNN: recall, especificidad, AUC (umbrales 80/85 %, 70/75 %, 0,85/0,88) | cumplido (mínimo en especificidad) | pesos desplegados, conjunto de prueba, cifras leídas del reporte de métricas: recall y AUC alcanzan el objetivo, la especificidad el mínimo. El objetivo 0,75 no es alcanzable a la vez que recall ≥ 0,85: frontera medida el 23-sep y registrada en la Semana 1 |
| Servidor MCP en Docker consumido desde n8n | cumplido | SP2 |
| Bot con dos roles, extremo a extremo | cumplido | SP3 |
| Normalización del lenguaje coloquial con LLM (§2.2, H6) | **descopado** | SP3 D4 y Registro de cambios: un extractor probabilístico en la entrada de un cálculo clínico; el cuestionario es de botones y el texto libre llega íntegro |
| Redacción del pre-informe con LLM (§2.2, anexo B) | **descopado** | SP4 §12: la combinación es aritmética auditable; un LLM entre los números y el clínico rompe la explicabilidad. El último Registro de cambios lo daba como diferido a H6: se corrige |
| «Sistema multi-agente / arquitectura agéntica», título «… y LLM» | cumplido con cambio | n8n determinista + herramienta MCP estándar; **el título del informe final pierde «y LLM»** |
| Corpus de 50-100 frases, tres enfoques, P/R ≥ 85 % (H6); 10 frases validadas por el médico y vocabulario coloquial (H6, §9.1) | **descopado** | sin extractor no hay extracción que medir ni vocabulario que mapear |
| Combinación bayesiana síntomas + imagen (H6) | cumplido | SP4 |
| Verificación bayesiana con casos simulados (§5.2) | cumplido | §4.4, 0A: caso a caso |
| «Probabilidad previa, de imagen y combinada por separado» (§7.9) | cumplido con cambio | el mensaje imprime prevalencia, RV clínica, RV de imagen y horquilla combinada, no una «probabilidad previa por síntomas» |
| Sesión con médico, 20-30 casos, kappa, utilidad, tiempos (H7; kappa 0,4/0,6) | cumplido con cambio, si hay acta | dos lecturas del mismo conjunto en vez de una sesión (para que el kappa sea independiente y el tiempo se mida sobre el mismo set, como pedía el KPI 1); pregunta por opacidad compatible, no por neumonía (SP4 §8.1); kappa ponderado como primario y el de Cohen sin ponderar como prometido; tiempo medido con el efecto de releer estimado aparte; el objetivo 0,6 no es evaluable con 24 casos. Plan B: además el tiempo no se mide. Si la estimación puntual queda por debajo de 0,4: «no cumplido, causa documentada caso por caso», que es lo que §5.7 permite |
| Latencia de extremo a extremo (8 s / 3 s) | cumplido con cambio (provisional) | se mide `ms_extremo`, el tramo n8n → respuesta, no la subida a Telegram ni la entrega (§6.3); si no hay corrida con bots antes del 16-oct, «no medido» con la causa |
| Reducción del tiempo de triaje (20 / 40 %) | por la sesión | §5.4; plan B: «cumplido con cambio», no medido |
| PadChest como validación externa | **descopado** | el acuerdo no se gestionó; sesgo de origen único declarado en ética |
| Grad-CAM (opcional) | descopado | opcional en la Semana 1; sin tiempo |
| `samples/` con 20 imágenes (anexo D) | cumplido si los términos de RSNA lo permiten | se releen los términos aceptados en Kaggle; si no lo permiten, descopado con la razón y con las instrucciones de descarga |
| Plan de mantenimiento (§7.10) | cumplido con cambio | sección del informe: reentrenamiento anual o ante cambio de equipo, y `docs/sp3-operacion.md` |
| «Asignación de historias registrada en el repositorio» (§8.1) | cumplido con cambio | registrada en el informe del AVA, no en el repositorio (anonimato) |
| Repositorio GitHub público (H8) | cumplido con cambio | privado, compartido por invitación, historial limpio (§6.1) |
| Video de sustentación (H8) | cumplido con cambio | dos videos según el curso (§6.4) |
| Datos emparejados reales / piloto prospectivo | no prometido en la Semana 1 | abierto desde SP3 §19; trabajo futuro con MIMIC |
| **Añadido:** tabla de fairness por subgrupos (excluida en §7.4) | añadido | el curso la pide (§6.7.3) |
| **Añadido:** interfaz web mínima (excluida en §7.4) | añadido, solo si la tutora la exige | §6.7.2 |

Entregable nuevo: una entrada del **Registro de cambios** de la Semana 1 que
corrija la del 25-sep (el LLM que redacta no está diferido a H6: está
descopado), registre las dos decisiones del 27-sep y los dos cambios de
alcance añadidos.

### 6.3. KPIs

Una fila por cada métrica de la tabla de umbrales y de §5.4-5.6, medida donde
se pudo y declarada donde no:

| KPI | Dónde se mide |
| :--- | :--- |
| recall, especificidad, AUC de la CNN | SP2, conjunto de prueba, reporte de métricas de los pesos desplegados |
| **latencia de extremo a extremo** (objetivo 2, umbrales 8 s / 3 s, §7.9) | `consultas.ms_extremo` de **una corrida de `pruebas/reproducir_casos.py` en modo con bots contra el VPS** (N ≥ 30 consultas sin error; los mensajes de la sesión no la miden, §5.6): **p50 y p95** a `docs/validacion-semisintetica/latencia.json`, con el tramo declarado: desde que `Normalizar update` recibe el update con la placa hasta que `Desenlace` compone la respuesta (excluye la subida a Telegram, la entrega del webhook y el envío de `Responder`), que no es el «desde que el profesional sube la radiografía hasta que recibe el pre-informe» de la Semana 1 §5.4. El tramo que falta se acota a mano en 5 casos (hora del envío en el cliente de Telegram frente a hora de la respuesta) y se dice. Sin corrida con bots antes del 16-oct, **no medido** con la causa |
| latencia del modelo | VPS, mediana 143 ms (H4) |
| kappa (tres), utilidad (tres notas), tiempo de triaje | sesión (§5) |
| KPI 2, derivaciones innecesarias | cumplido según su propia definición (porcentaje de placas sin opacidad correctamente filtradas = especificidad de la CNN en el conjunto de prueba); medido en RSNA, no en operación: sin usuarios no hay derivaciones reales que contar |
| precisión y recall de extracción | descopado (§6.2) |
| calibración, posición y contención de la horquilla | simulación (§4) |
| tasa de finalización del cuestionario, CSAT del paciente, tasa de uso activo | definidos, sin dato: no hay usuarios |
| CSAT del profesional | aproximado por la utilidad de la sesión |

### 6.4. Informe final, videos, repositorio

- **Informe final** (semana 6, formato de la universidad): se escribe desde
  los specs, los `docs/`, `resultados_simulacion.json` y `sesion.json`; figuras
  a 300 DPI; con la tabla del §6.2, los KPIs del §6.3 y la deuda del §6.5. El
  título pierde «y LLM».
- **Dos videos**, como exige el curso: un **pitch de 5 minutos** con la
  estructura de 7 bloques (problema; datos y metodología; desarrollo y
  optimización; la solución en acción con grabación de pantalla real de la
  interfaz que se entregue como tal —el bot o, si la tutora lo exige, la app
  del §6.7.2—, 2-3 casos y un error manejado; evaluación; ética; cierre con QR
  y enlace), y el **video de respuestas** a las preguntas que el profesor
  entregue la última semana. No hay demo en vivo. **Regla de captura:** nada
  del cliente en pantalla (§6.1). El dashboard de SP3 §15 **no existe** y no
  aparece en el guion.
- **Repositorio:** el del §6.1, con README de portada, `LICENSE`,
  `requirements.txt` y los documentos del §6.7.

### 6.5. Deuda: lo que se decide y lo que se deja escrito

Se decide aquí lo que SP3 §18 fechaba dentro de SP5:

- **`consultas` se vacía** (`DELETE` + `VACUUM`) después de la grabación de los
  videos y de la fecha de entrega del video de preguntas; hasta entonces el
  sistema sigue vivo para el tribunal.
- **La retirada del VPS del cliente** (SP3 §17: `compose down`, borrar el
  volumen de la base, archivar los workflows, revocar los bots) se ejecuta
  después de la calificación, con fecha escrita en el informe.
- **La pregunta PACS/DICOM** se hace en la reunión de preparación (§5.8) y su
  respuesta va al acta.
- **El canal del piloto** (Telegram o canal local, SP3 §18) se cierra como sin
  objeto: no hay piloto.

Se deja escrita: la prevalencia local sin dato real (SP4 §5); la dependencia
condicional con su **dirección dependiente de dónde vive la correlación**
(§4.5) y sin valor real (SP4 §7.3 sigue abierto); MIMIC como vía para medir
`ρ` de temperatura y pulso; Telegram como canal por el que pasan placa y
respuestas (SP3 §5.5, aceptado y declarado).

### 6.6. Calendario y camino crítico

Los instrumentos de la sesión dependen del generador (las viñetas salen de él)
y tienen que estar congelados el 5-oct. Todo el código de SP5 se fusiona **a
más tardar el 16-oct** (tag `sp5-codigo` ese día); desde el 17 no hay código
nuevo: la semana 6 solo documenta, graba y empaqueta.

| Fechas | Qué |
| :--- | :--- |
| 27-30 sep | generador por puntuación, oráculo y pruebas de 0A; `--casos` en el arnés; preguntas por escrito a la tutora (§6.7); reunión de preparación con el médico |
| 1-4 oct | `preparar_sesion`, el formulario, `analizar_sesion` probado con un CSV sintético; ensayo completo con un integrante como lector |
| 5 oct | tag `h7-sesion`; mensajes reales y ficheros del formulario congelados |
| 6-8 oct | **lectura 1** |
| 6-12 oct | rejilla, bootstrap, curvas, `docs/validacion-semisintetica-sp5.md`; corrida del corpus **con bots** contra el VPS para la latencia (§6.3); anonimización de lo funcional (URLs, red, rutas) y `test_anonimato`; Workshop S5 y, si hace falta, la interfaz del §6.7 |
| 13-15 oct | **lectura 2** (7 días o más después de la lectura 1); `analizar_sesion`; acta |
| 16 oct | acta enviada al médico para revisión; todo fusionado; tag `sp5-codigo` |
| 17 oct | resultados de H7 presentados a la tutora (tutoría) |
| 17-24 oct | documentos del curso, informe, videos, repositorio nuevo (§6.1), release con los pesos, README |

**Orden de recorte** si el calendario aprieta: (1) 0B, la extracción de
Ebell; (2) el bootstrap fuera de las seis celdas destacadas; (3) la
reescritura en prosa de `docs/superpowers` (queda el reemplazo mecánico). **No
se recortan** la sesión, la anonimización de valores por defecto y rutas, la
tabla del §6.2 ni los documentos obligatorios del curso.

### 6.7. Lo que exige la entrega final del curso

La descripción de la entrega final (PDF del curso, 13 páginas) fija cosas que
el borrador ignoraba. Decisiones:

1. **Preguntas por escrito a la tutora antes del 1-oct:** si la invitación al
   repositorio privado evita el −15 % de «repositorio privado o inaccesible»;
   si el bot de Telegram vale como «interfaz de usuario» (20 % de la nota)
   dando de alta el chat del evaluador en la lista blanca del profesional y
   aportando DICOM de muestra; y qué pide exactamente el Workshop S5
   (`optimizacion.md`: sensibilidad, partial dependence, ranking de
   hiperparámetros).
2. **Interfaz:** si el bot no vale, una app mínima (Gradio o Streamlit) sobre
   `POST /inferir` y `heckerling.combinacion` —subir una placa, teclear los
   cinco hallazgos, ver la horquilla y el mismo texto del bot, con ejemplos
   precargados y «Acerca de»—, fusionada antes del 16-oct. Se reserva el 10-12
   oct.
3. **`docs/` obligatorios**, escritos en la semana 6 desde lo que ya existe:
   `planificacion.md` (Semana 1 + cronograma planificado vs. real, con las
   fechas reales de las fusiones), `analisis_datos.md` (desde `docs/eda` y el
   notebook), `arquitectura.md` (desde los specs de SP2-SP4 y el diagrama),
   `optimizacion.md` (desde `docs/comparativa-corridas.md` y el S5),
   `consideraciones_eticas.md` (los ocho apartados del curso; incluye una
   **tabla por subgrupos** —sexo, edad, proyección AP/PA— de recall,
   especificidad y AUC sobre `crudas_prueba.csv`, que es fairness medible y
   cuesta horas, no días), `manual_usuario.md` (desde `docs/sp3-operacion.md`
   con capturas del bot; **contacto de soporte:** las Issues del repositorio
   nuevo y, para el tribunal, el canal del AVA; ningún correo personal ni de
   empresa). Más `LICENSE`, `requirements.txt` y `models/README.md` con el
   hash de los pesos y el enlace al release.
4. **Estructura de carpetas:** no se reestructura el repositorio; la sección
   «Estructura del proyecto» del README mapea cada carpeta exigida a la
   nuestra.
5. **Autores en el README:** el curso pide nombres y roles; el repositorio no
   los lleva por texto (§6.1). El README remite a la autoría del informe del
   AVA y enlaza los videos, y el riesgo en la rúbrica se asume, salvo que la
   respuesta de la tutora (punto 1) cambie la decisión.
6. **Pesos del modelo** (16 MB): asset de un release del repositorio nuevo, con
   su `sha256`; el README explica cómo obtenerlos y cómo construir la imagen.
7. **Rótulo «simulación semisintética»** en todo artefacto *de resultados* del
   §4 y del §5 —documentos, tablas, figuras, JSON de resultados, ficheros del
   formulario y acta—: en el título o cabecera de cada uno **y en su ruta,
   que basta con que la lleve el directorio**. Todos viven en
   `docs/validacion-semisintetica/`. El código (`src/`, `scripts/`, `tests/`)
   no lleva rótulo. `crudas_prueba.csv` no es simulación (puntuaciones reales
   del modelo sobre las placas de prueba) y su cabecera lo dice: se conserva
   con ese nombre dentro del mismo directorio como insumo congelado. «Datos
   fabricados» es causa de rechazo automático, y nada debe poder leerse como
   datos.

## 7. Lo que SP5 NO hace

- No reentrena, no recalibra, no ajusta ninguna RV ni ninguna prevalencia con
  datos sintéticos.
- No usa MIMIC ni ningún dato de paciente real.
- No implementa el LLM: se descopa con su razón (§6.2).
- No hace público el repositorio: lo comparte por invitación (§6.1).
- No añade pasos a los bots: la sesión se hace con el formulario.
- No mide exactitud clínica, y no lo afirma en ningún sitio: lo contrario se
  escribe en el informe, en el acta y en la tabla del §6.2 (§4.7).

## 8. Cómo se prueba

Todas en la suite, sin red:

- **Generador:** con `R = 50` sorteos por placa y semilla fija, `P(k | y)`
  empírica coincide con los recuentos (±0,01); la regla de reparto da `k`
  puntos exactamente; las temperaturas (una décima) y pulsos (enteros) caen
  del lado correcto del corte y la fracción exacta en el corte / justo sobre
  él es 0,2 (±0,02); `no_se` es 0,10 (±0,01) e independiente de la etiqueta.
- **Umbral latente, forma cerrada:** con `ρ_y ∈ {0,3; 0,6}`, la media sobre las
  placas de la clase de `P(k | q_i, y)` coincide con los recuentos (±10⁻⁹): es
  lo que garantiza la bisección; los umbrales resueltos con `ρ = 0` son
  `Φ⁻¹(P(k ≤ j − 1 | y))`; la correlación de Pearson en forma cerrada del §4.5
  reproduce los valores esperados (±0,005).
- **Umbral latente, empírico:** con `R = 50` sorteos por placa y semilla fija
  (n ≈ 42 000 en la clase 1, ≈ 148 000 en la 0), `P(k | y)` empírica coincide
  con los recuentos (±0,01) y la correlación de Pearson dentro de cada clase
  entre `k` y `z_y(q)` coincide con la forma cerrada (±0,03); con `ρ = 0` es 0
  (±0,03) dentro de cada clase.
- **`z_y` sobre todo `q`:** para una placa negativa, `z_1(q)` coincide con el
  rango medio que tendría al insertarla entre las positivas; para una `q` por
  debajo del mínimo de una clase, `F̂_y` vale la cota `0,5/n_y`.
- **Oráculo:** con `ρ = 0`, `ln P(k | q, 1) − ln P(k | q, 0) = ln
  RV_recuentos(k)` para todo `q` (±10⁻⁹); las probabilidades `P(k | q, y)`
  suman 1; el oráculo de `no_se` marginaliza bien (comprobado contra una suma
  explícita sobre las `k` compatibles).
- **0A, determinista** (§4.4): las tres comprobaciones sobre un subconjunto
  fijo de placas; y la **mutación** —una RV de `RV_POR_PUNTUACION` cambiada,
  `>` por `>=`, o el corte a 38,0— aplicada con `monkeypatch` rompe 0A.3 o
  0A.1 en al menos un caso. La prueba aplica la mutación y espera el fallo.
- **Métricas:** AUC, Brier, pendiente/intercepto y ECE sobre vectores con
  valores conocidos a mano; posición `λ`, colas y contención sobre cuatro
  casos de borde (oráculo dentro, en un extremo dentro de `ε`, fuera por cada
  lado, `Δ = 0`); el suelo de ruido de la ECE es reproducible con semilla.
- **Categoría del sistema (§5.3):** punto medio en log-odds, redondeo hacia
  arriba en ,5, bandas con los bordes 20 y 70 exactos, y la prueba de que
  **ninguna horquilla cruza los dos límites** con los previos 0,1466, 0,2215 y
  0,05, y de que sí lo hace con 0,02 (el umbral analítico).
- **Sesión:** `analizar_sesion.py` sobre CSV de ejemplo con valores conocidos:
  los tres kappas y sus intervalos, el acuerdo continuo (con un 0 % y un 100 %
  acotados), los 20 tiempos pareados y los 4 controles, la influencia del
  sistema y la tabla de desacuerdos; y sobre un CSV del plan B.
- **Arnés:** con un `casos.json` de 3 casos, `hallazgos_del_caso` y el bloque
  EXPLORADO de cada mensaje coinciden con la viñeta del caso.
- **Anonimato:** `test_anonimato.py` detecta el centinela inyectado en un
  fichero temporal dentro del recorrido, y pasa sobre el árbol.

## 9. Entregables

1. `src/copiloto_triaje/validacion/`, `scripts/validar_combinacion.py`,
   `docs/validacion-semisintetica/` (tablas, curvas,
   `resultados_simulacion.json`, `crudas_prueba.csv` congelada con su hash,
   `latencia.json`), `docs/validacion-semisintetica-sp5.md`.
2. `--casos` en `pruebas/reproducir_casos.py`; `scripts/preparar_sesion.py`,
   el formulario, `scripts/analizar_sesion.py`, la plantilla del acta y el
   **acta de H7** rellena tras la sesión.
3. `tests/test_anonimato.py` con sus huellas, `scripts/verificar_anonimato.py`,
   el repositorio nuevo del §6.1 y el release con los pesos.
4. Los `docs/` del §6.7, `LICENSE`, `requirements.txt`, README de portada.
5. Informe final (formato de la universidad) con la tabla del §6.2 y los KPIs
   del §6.3; guion y grabación del pitch; video de respuestas; entrada nueva
   en el Registro de cambios de la Semana 1.

## 10. Riesgos

| Riesgo | Estado |
| :--- | :--- |
| El médico no puede en el 6-16 oct, o solo una vez | plan B de una sesión (§5.4); fuera de la ventana, H7 incumplido y dicho |
| Los tiempos se miden en remoto asíncrono | no valen; se declara no medido (§5.4) |
| El PDF de Ebell no llega | 0B se recorta; 0A, 0C y la rejilla no lo necesitan (§4.4) |
| Los umbrales no convergen o la forma cerrada no reproduce los recuentos | prueba dedicada (§8); si falla, se corrige el generador, nunca la prueba |
| La contención de la horquilla sale baja o el oráculo sale por el lado de independencia | es un resultado; se reporta con su dirección y se repiensa la cota en el informe |
| Un kappa con un evaluador y 24 casos | intervalo de 0,5-0,6 declarado por adelantado (§5.5) |
| Alguien lee la simulación como datos o como exactitud clínica | rótulo «simulación semisintética» en cada artefacto de resultados; §4.7 en el informe, el acta y la tabla del §6.2 |
| El historial reescrito conserva alguna cadena | `verificar_anonimato.py` sobre todos los blobs; si no pasa, un solo commit (§6.1) |
| El curso penaliza el repositorio privado o exige otra interfaz | preguntas antes del 1-oct; interfaz mínima reservada el 10-12 oct (§6.7) |
| No hay corrida con bots contra el VPS antes del 16-oct | la latencia de extremo a extremo se declara no medida (§6.3) |
| Redesplegar el compose con la red renombrada | el usuario ejecuta los comandos en el VPS, con la guía actualizada; se hace fuera de las fechas de la sesión |

## 11. Criterios de aceptación

1. 0A pasa sus tres comprobaciones deterministas (0A.1 sobre los casos con
   asma conocida; 0A.2 y 0A.3 sobre los 3 811), y las mutaciones de RV y de
   corte las rompen.
2. La rejilla `(ρ1, ρ0)` está calculada, con las cuatro métricas por modelo,
   las diferencias pareadas con intervalos por bootstrap en las seis celdas
   destacadas (§4.5) y en 0A, la posición, las colas y la contención de la
   horquilla por tipo de caso (con la fila 0A en 0 / 0 / 100 %), y la fracción
   de log-RV conservada por lado de la imagen; ninguna cifra del informe se
   teclea: todas salen de `resultados_simulacion.json`.
3. La sensibilidad al previo y 0C están, con el número de casos que cambian de
   banda.
4. Existe el acta de H7 con los tres kappas y sus dos intervalos, comparados
   con 0,4 y 0,6; el acuerdo continuo; las tres notas; los tiempos pareados (o
   la declaración de no medidos); los desacuerdos caso por caso; las
   observaciones del médico; y los mensajes evaluados son los del sistema
   desplegado o de la imagen del tag `h7-sesion`, dicho en el acta. La Semana
   1 fija kappa ≥ 0,4 como criterio de aceptación (§7.9, H7) y prevé que, si
   no se alcanza, se documente la causa (§5.7): aquí el criterio de SP5 es que
   exista el acta con sus intervalos; si la estimación puntual queda por
   debajo de 0,4, la fila de H7 del §6.2 pasa a «no cumplido, causa
   documentada caso por caso».
5. `tests/test_anonimato.py` en verde sobre el árbol, y
   `scripts/verificar_anonimato.py` en verde sobre todas las revisiones del
   repositorio que se comparte, autor y committer incluidos.
6. Todo el código de SP5 fusionado a más tardar el 16-oct (tag `sp5-codigo`);
   desde el 17 sin código nuevo.
7. El informe final tiene la tabla del §6.2 completa y los KPIs del §6.3; los
   `docs/` del §6.7, `LICENSE` y `requirements.txt` están en el repositorio
   compartido; los dos videos están enlazados en el README.
