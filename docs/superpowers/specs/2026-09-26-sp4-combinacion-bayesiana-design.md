# SP4 — Combinación bayesiana de clínica e imagen

**Sub-proyecto:** SP4, cuarto de cinco. **Hito:** H6, vence el 9-oct-2026.

**Recibe de:** SP3 (H5), que ya entrega por separado la evidencia de la imagen
—como razón de verosimilitud calibrada— y los síntomas y signos, que los dos
bots recogen y guardan en `consultas`.

**Entrega a:** SP5 (H7), validación clínica.

---

## 1. Qué hace, en una frase

Une lo que hoy va separado: multiplica la probabilidad previa que da una regla
clínica publicada por la evidencia de la imagen, y entrega una probabilidad
posterior al profesional.

El descargo que el bot manda hoy lo dice literalmente: *«La combinación de
imagen y clínica llega en la siguiente entrega.»* SP4 es esa entrega, y sustituye
esa frase por el número.

## 2. Lo que ya está hecho, y por qué eso decide el diseño

**Los cinco predictores de la regla de Heckerling coinciden exactamente con lo
que los bots ya recogen.** No es casualidad: SP3 los eligió así.

| Predictor de Heckerling | Dato que ya existe | Quién lo aporta |
| :--- | :--- | :--- |
| Temperatura > 37,8 °C | `temperatura_c` | profesional, paso 2 |
| Pulso > 100 lpm | `frecuencia_cardiaca` | profesional, paso 3 |
| Crepitantes | `crepitantes` | profesional, paso 4 |
| Murmullo disminuido | `murmullo_disminuido` | profesional, paso 5 |
| **Ausencia** de asma | `asma` | paciente, pregunta 6 |

Las otras seis preguntas del paciente —tos, días de evolución, disnea, dolor
torácico, texto libre— **no entran en la fórmula**. Son contexto clínico para
el profesional y material para H7, y SP4 no las toca.

**Y la evidencia de la imagen ya es una razón de verosimilitud.** SP2 calibra la
salida de la CNN con regresión isotónica y la convierte en RV con
`RV = [p/(1-p)] / [prev/(1-prev)]`, acotada a los extremos sostenidos de la
curva. Un evaluador externo recomendó el 26-sep «calibren la CNN y conviertan su
salida en una razón de verosimilitud»: ya estaba hecho desde SP2.

Así que SP4 no construye maquinaria nueva. **Añade un factor a una cadena que ya
existe.**

## 3. La cadena

```
prevalencia declarada  →  odds previos
                       ×  RV(Heckerling)     ← la puntuación 0-5
                       ×  RV(imagen)         ← la curva isotónica de SP2
                       =  odds posteriores   →  probabilidad
```

Tres factores, **cada uno con su procedencia y discutible por separado**. Es lo
que evita el error que este diseño rechaza en el §4: que una población se cuele
dentro de una cifra sin que nadie la vea.

### 3.1. Por qué razones de verosimilitud y no la tabla de probabilidades

La regla publica una probabilidad por puntuación, y **esa probabilidad arrastra
la prevalencia de la población donde se midió**. Medido sobre las fuentes:

| Fuente | Con cuatro predictores |
| :--- | ---: |
| Derivación original (urgencias, EE. UU., 1990) | 55,2 % |
| Validación externa agrupada (4-5 hallazgos) | 64,0 % |
| Revisión AAFP, **atención primaria** | 27 % |

No se contradicen: es el mismo hallazgo leído sobre poblaciones distintas.
Copiar cualquiera de esas cifras metería su prevalencia dentro de nuestro
sistema sin declararla.

La razón de verosimilitud no tiene ese problema: es una propiedad de la prueba,
no de la población. **Es además la misma forma que SP2 ya eligió para la imagen**,
y por la misma razón.

## 4. La fuente clínica, y lo que se sabe de ella

> Heckerling PS, Tape TG, Wigton RS, Hissong KK, Leikin JB, Ornato JP, et al.
> **Clinical prediction rule for pulmonary infiltrates.**
> *Ann Intern Med.* 1990;113(9):664-70.

Las razones de verosimilitud se toman del **conjunto de derivación (Illinois)**,
tal como lo reproduce una revisión sistemática con metaanálisis
([PMC7422644](https://pmc.ncbi.nlm.nih.gov/articles/PMC7422644/), tabla 2):

| Puntuación | Con neumonía | Sin | VPP publicado | **RV** |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | 48 | 2,0 % | **0,12** |
| 1 | 11 | 316 | 3,4 % | **0,20** |
| 2 | 28 | 232 | 10,8 % | **0,70** |
| 3 | 42 | 149 | 22,0 % | **1,64** |
| 4 | 37 | 30 | 55,2 % | **7,18** |
| 5 | 15 | 5 | 75,0 % | **17,5** |
| | **134** | **780** | | |

**Las RV se verificaron contra los recuentos antes de aceptarlas**, porque un
primer resumen daba un «4,0 % sobre una prevalencia del 29,2 %» que no cuadraba:

- Puntuación 0: (1/134) ÷ (48/780) = 0,121 → publicada 0,12 ✓
- Puntuación 3: (42/134) ÷ (149/780) = 1,641 → publicada 1,64 ✓
- Puntuación 5: (15/134) ÷ (5/780) = 17,46 → publicada 17,5 ✓

El 4,0 % era el VPP agrupado de otra fila.

### 4.1. Tres cosas que se saben y se declaran

**Son las RV de la derivación, no de la validación.** Una regla siempre rinde
mejor donde se ajustó. Las bandas de validación existen —0-1 → 0,19; 2-3 → 1,04;
4-5 → 8,33— y son más conservadoras, pero pierden resolución: no distinguen un 4
de un 5, que es la diferencia entre 7,18 y 17,5. **Se eligen las seis, y esta
limitación se escribe.**

**Los recuentos suman 914**, y el metaanálisis dice que Illinois tenía 1 436
pacientes mientras el artículo original habla de 1 134. No afecta a las RV
—salen de las celdas— pero la discrepancia queda anotada en vez de asumida.

**No se pudo descargar el artículo primario**: PubMed responde con un CAPTCHA y
el texto completo de *Annals* es de pago. Las cifras se toman de la revisión
sistemática, que es fuente secundaria revisada por pares, y eso se dice.

## 5. La prevalencia: un parámetro, no una constante escondida

Vive en el compose como `PREVALENCIA_LOCAL`, junto a `UMBRAL` y
`AUC_VALIDACION`, **con la misma disciplina**: sin valor por defecto silencioso,
y con un comentario que diga de dónde sale y quién la fijó.

**Arranca en 0,1466**, la prevalencia de la propia cohorte de Heckerling
(134/914), y se cambia cuando haya dato del entorno real.

**No se reutiliza el 0,2215 del calibrador de imagen**, aunque tentaría tener un
solo número en el sistema: RSNA es un conjunto de radiografías **ya indicadas**,
no la población que llega a una consulta con tos. Son dos previos distintos
porque son dos poblaciones distintas.

## 6. `asma: no_se` — un intervalo, no un número

El spec de SP3 dejó esto explícitamente aplazado a H6, y con su razón:

> *Convertir `no_se` en un booleano sería fabricar el dato: tratarlo como «no
> tiene asma» sube la probabilidad previa sin fundamento, y tratarlo como «sí
> tiene» la baja igual de infundadamente.*

**La decisión: se calculan las dos posteriores y se entregan como rango.**

No inventa nada, y convierte el dato que falta en información útil: **el ancho
del intervalo dice si esa pregunta importa en este caso concreto.** Medido:

| Imagen | Puntuación 1-2 | Puntuación 3-4 | Puntuación 4-5 |
| :--- | :--- | :--- | :--- |
| Muy positiva (RV 30,3) | 51,0 – 78,5 % | 89,5 – 97,4 % | 97,4 – 98,9 % |
| Banda contradictoria (0,87) | 2,9 – 9,5 % | **19,7 – 51,8 %** | 51,8 – 72,3 % |
| Negativa del borde (0,59) | 2,0 – 6,6 % | 14,2 – 42,1 % | 42,1 – 63,9 % |
| Negativa clara (0,016) | 0,1 – 0,2 % | 0,5 – 2,0 % | 2,0 – 4,7 % |

El caso en negrita es el que justifica el diseño: con una imagen contradictoria y
tres de los otros cuatro signos, saber si el paciente tiene asma mueve la
posterior **del 20 % al 52 %**. Un número único ahí habría sido una invención con
consecuencias. Con una imagen muy positiva, en cambio, el intervalo es estrecho y
la pregunta da igual.

## 7. El supuesto incómodo: independencia condicional

Multiplicar dos razones de verosimilitud **asume que son condicionalmente
independientes dado el diagnóstico**, y aquí eso es discutible: los crepitantes y
el murmullo disminuido son el mismo fenómeno físico que la opacidad que ve la
CNN. No son dos pruebas independientes, son dos maneras de mirar la misma
consolidación.

**El efecto tiene dirección conocida: la multiplicación exagera.** Con hallazgos
concordantes la posterior sale más extrema de lo que corresponde. Se ve en la
esquina de la tabla: imagen muy positiva y cinco de cinco dan 98,9 %.

**No se amortigua.** Corregir la dependencia exigiría un factor de reducción que
nadie ha medido para este par de pruebas, y este proyecto no inventa constantes.
Se hacen tres cosas en su lugar:

1. **Se dice en el mensaje**, con ⚠️, en cada informe que lleve combinación.
2. **Se declara aquí** como la limitación principal del subproyecto.
3. **Se le pasa a H7**: medir cuánto exagera contra desenlaces reales es
   exactamente lo que la validación clínica tiene que hacer.

## 8. Qué lee el profesional

El informe gana un cuarto bloque. Ejemplo con puntuación 3 e imagen de RV 30,3,
todas las cifras calculadas:

```
COMBINADO — 89 % de probabilidad de opacidad compatible en la radiografía
(prevalencia 14,7 % × clínica 1,64 × imagen 30,3; Heckerling 3 de 5)
⚠️ La auscultación y la imagen miran la misma consolidación, así que no son
pruebas independientes y esta cifra tiende a exagerar. Decide usted.
```

Con el asma sin saber, la primera línea cambia de forma:

```
COMBINADO — entre 20 % y 52 % de probabilidad de opacidad compatible
(prevalencia 14,7 % × clínica 1,64–7,18 × imagen 0,87; Heckerling 3 o 4 de 5,
según tenga asma o no)
```

### 8.1. Cuatro reglas de redacción

**«Opacidad compatible», no «neumonía».** La CNN se entrenó sobre la etiqueta
`Lung Opacity` de RSNA, y el desenlace de Heckerling es **infiltrado probado
radiográficamente**: las dos mitades de la cadena hablan de un hallazgo en la
placa, no de un diagnóstico clínico. La regla que SP3 ya fijó se aplica igual
aquí: *lo que el sistema afirma dice «opacidad»; lo que advierte puede decir
«neumonía», porque advierte contra ese salto.*

**Los tres factores se imprimen.** El profesional puede rehacer la
multiplicación, y si no está de acuerdo con la prevalencia ve exactamente cuál
cambiar. Un número sin sus factores no es explicable, es solo un número.

**Nunca sale 0 % ni 100 %.** Se usa la convención que `prob()` ya tiene en el
nodo: `< 1 %` y `> 99 %`. Una posterior de 0,0 % es certeza de ausencia, que es
la misma mentira que una calibrada de 0,00 —y la cota del calibrador existe
justo para no fabricarla—.

**La posterior se imprime en porcentaje entero.** El resto del informe usa dos
decimales para las probabilidades, y aquí serían falsa precisión: la cifra
arrastra una prevalencia discutible, unas RV de un conjunto de derivación y un
supuesto de independencia que se sabe falso. Un «89 %» dice lo que se sabe; un
«89,47 %» promete lo que no. Por debajo del 1 % y por encima del 99 % manda la
regla de la convención, no el redondeo.

**Sin combinación no se inventa una.** Si los signos no están completos no hay
puntuación, y el informe sale como hoy diciendo por qué falta la parte clínica.
`signosValidos` ya distingue ese caso.

## 9. Dónde vive cada pieza

### 9.1. El módulo

`src/copiloto_triaje/servicio/heckerling.py`, junto a `calibracion.py`, que ya
hace esta misma aritmética de odds:

| Nombre | Qué hace |
| :--- | :--- |
| `PUNTOS` | los cinco predictores y sus cortes |
| `RV_POR_PUNTUACION` | las seis RV del §4, con su cita |
| `puntuar(signos, asma)` | una puntuación, o **dos** si el asma es `no_se` |
| `combinar(prevalencia, rv_clinica, rv_imagen)` | odds → producto → probabilidad |

**En Python y no en el nodo `Desenlace`**, aunque los datos ya estén en n8n: la
combinación bayesiana es *la* afirmación clínica de H6 y tiene que vivir donde se
pueda mutar una constante y ver la prueba ponerse roja. Escribirla en el nodo la
dejaría además duplicada —la aritmética de odds ya existe en `calibracion.py`—,
que es la clase de duplicación que este proyecto persigue.

### 9.2. El contrato MCP

`clasificar_radiografia` acepta un parámetro **opcional** `hallazgos` y, si
viene, devuelve un bloque `combinacion` junto a lo de siempre.

**Una sola llamada**: el profesional da los cuatro signos en los pasos 2 a 5,
*antes* de mandar la placa en el paso 6, así que en el momento de la llamada los
cinco datos ya existen.

**Compatible hacia atrás**: sin `hallazgos`, la respuesta es idéntica a la de
hoy. Las diez comprobaciones del §10 de SP3 siguen valiendo sin tocarlas, y eso
es un criterio de aceptación, no una esperanza.

### 9.3. Lo que viaja, y lo que eso implica

Con `hallazgos` viajan al copiloto **cinco booleanos**, no el cuestionario. No es
una clase de exposición nueva —la radiografía entera ya va por ahí, por la red
privada de Docker del VPS— pero **se anota en el §5.4 de SP3** igual que todo lo
demás que se mueve.

## 10. Qué se guarda

**Ninguna migración.** `Desenlace` ya serializa el `structuredContent` entero a
`consultas.resultado`, que es `jsonb`. El bloque `combinacion` viaja dentro sin
tocar el esquema, y H7 lo encuentra ahí **junto a los síntomas y los signos que
lo produjeron**, que es exactamente lo que necesita para validarlo.

## 11. Cómo se prueba

### 11.1. La prueba que sostiene todo lo demás

> **Con la prevalencia de la propia cohorte (134/914), la cadena reproduce la
> columna de VPP del artículo.**

Verificado antes de escribir este documento:

| Puntuación | 0 | 1 | 2 | 3 | 4 | 5 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| La cadena | 2,0 % | 3,3 % | 10,7 % | 22,0 % | 55,2 % | 75,0 % |
| El artículo | 2,0 % | 3,4 % | 10,8 % | 22,0 % | 55,2 % | 75,0 % |

Coinciden salvo redondeo. **Si alguien toca una RV o la aritmética, deja de
reproducirla**: es una prueba de mutación que se escribe sola.

### 11.2. Las demás

- El `no_se` da **dos** puntuaciones separadas por exactamente uno.
- La posterior nunca se presenta como 0 % ni como 100 %.
- Sin `hallazgos`, la respuesta del contrato no cambia ni un byte.
- Con signos incompletos no hay combinación, y el informe lo dice.
- Los cortes son **estrictos** donde la regla lo dice: 37,8 °C exactos **no**
  puntúan, 100 lpm exactos **no** puntúan. Un corte mal puesto mueve la
  puntuación entera y no lo cazaría ninguna prueba de redondeo.

## 12. Lo que SP4 NO hace

- **No usa ningún LLM.** Sigue aplazado. La combinación es aritmética
  auditable, y meter un modelo de lenguaje entre los números y el clínico sería
  romper la propiedad que hace explicable a todo el sistema.
- **No toca los bots.** Ni una pregunta nueva, ni un paso más en la
  conversación. La decisión D3 de SP3 lo pedía así y se cumple.
- **No valida nada clínicamente.** Eso es H7, y el §19 de SP3 ya declara el
  riesgo mayor del proyecto: **RSNA no trae síntomas ni exploración**, así que no
  existen datos reales que emparejen imagen y clínica. SP4 se puede implementar y
  probar; **afirmar que la combinación acierta necesita datos emparejados reales
  o un piloto prospectivo**, y esa decisión sigue abierta.

## 13. Riesgos

| Riesgo | Estado |
| :--- | :--- |
| **La independencia condicional no se sostiene** y la posterior exagera | Declarado (§7). Sin corregir a propósito: no hay factor medido. H7 debe cuantificarlo |
| **Las RV son del conjunto de derivación** | Declarado (§4.1). La alternativa conservadora existe y pierde resolución |
| **La prevalencia inicial es la de una cohorte de 1990 en EE. UU.** | Declarado (§5). Es un parámetro, no una constante: se cambia sin tocar código |
| **No hay datos para validar la combinación** | Heredado del §19 de SP3. **El mayor del proyecto**, y sigue abierto |
| La fuente de las RV es secundaria, no el artículo original | Declarado (§4.1). Revisión sistemática revisada por pares |

## 14. Criterios de aceptación

1. La cadena reproduce la columna de VPP del artículo con la prevalencia de su
   cohorte, salvo redondeo a una décima.
2. Sin `hallazgos`, la respuesta de `clasificar_radiografia` es idéntica a la de
   SP3, y las diez comprobaciones del contrato pasan sin modificarse.
3. Con `asma: no_se` el informe entrega un intervalo, nunca un número único.
4. Ninguna posterior se presenta como 0 % ni como 100 %.
5. El informe con combinación imprime los tres factores y el aviso de
   dependencia.
6. Ningún literal de la combinación afirma «neumonía»; los avisos sí pueden.
7. Con signos incompletos el informe sale como en SP3 y dice por qué.
8. `PREVALENCIA_LOCAL` no tiene valor por defecto silencioso: sin ella, el
   servidor no arranca. **Esto no rompe la compatibilidad del §9.2**, que es del
   CONTRATO de la herramienta y no del entorno: un despliegue que solo quiera
   inferencia de imagen sigue llamando igual, pero declara la prevalencia como
   ya declara `UMBRAL` y `AUC_VALIDACION`. La razón es la misma que allí: es una
   cifra que acaba delante de un clínico, y un valor por defecto silencioso
   sobrevive a un cambio de entorno sin que nadie lo mire.
