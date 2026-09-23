# La frontera entre recall y especificidad

Medido el 23-sep-2026 sobre el conjunto de **validación** (3 810 radiografías)
con los pesos de `efficientnet_b0_320px_lote24_4+20ep`. El conjunto de prueba
no se tocó: reelegir un punto de operación mirándolo sería ajustar contra la
prueba e invalidaría el reporte.

## Lo que se midió

AUC en validación: **0,8827**

| Especificidad exigida | Especificidad real | Recall | Umbral |
| ---: | ---: | ---: | ---: |
| 0,70 | 0,7006 | **0,8815** | 0,4258 |
| 0,72 | 0,7256 | 0,8637 | 0,4649 |
| 0,75 | **0,7522** | 0,8400 | 0,5029 |
| 0,78 | 0,7815 | 0,8187 | 0,5407 |
| 0,80 | 0,8007 | 0,8033 | 0,5654 |
| 0,85 | 0,8506 | 0,7358 | 0,6575 |

## La conclusión, que obliga a corregir lo entregado

**No existe ningún punto con recall ≥ 0,85 y especificidad ≥ 0,75 a la vez.**
El más cercano con especificidad ≥ 0,75 da recall 0,8400.

El documento maestro de la Semana 1 compromete en tres sitios —resumen
ejecutivo, objetivos específicos y criterios de aceptación del hito H3— un
"Recall ≥ 85% y especificidad ≥ 75%" que este modelo **no puede satisfacer**.
La Tabla 8 del mismo documento sí distingue mínimo (70%) de objetivo (75%),
así que la contradicción es interna y hay que unificarla.

Lo que sí se cumple, y con holgura, son los **mínimos**: recall ≥ 0,80 y
especificidad ≥ 0,70 en cualquier punto de la tabla salvo el último.

## Cuánto falta para cumplir ambos objetivos

Estamos en la frontera, no lejos. La corrida de EfficientNet-B0 en Kaggle
(AUC 0,888 frente a 0,883 de ésta) sí registró una época con recall 0,851 y
especificidad 0,752 en validación. La diferencia entre poder y no poder es de
unas **cinco milésimas de AUC**.

No se reentrena para perseguirlas: elegir la corrida que casualmente cruza el
listón es seleccionar por ruido. Lo honesto es reportar la frontera y decir
qué falta para moverla — más datos, más resolución o un backbone mejor.

## Qué hacer con esto

**Publicar la frontera, no un punto.** Para una herramienta de triaje, decirle
al profesional "puede operar en 0,88/0,70 o en 0,84/0,75, y esto cuesta cada
opción" es más útil y más defendible que esconder la disyuntiva tras una sola
cifra.

El punto por defecto prioriza el **recall**, y la razón es clínica y hay que
escribirla en vez de dejarla implícita en el código: un falso negativo manda a
casa una neumonía; un falso positivo cuesta una radiografía revisada de más.

## Reproducirlo

`scratchpad/curva_roc_validacion.py` (no versionado: depende de rutas locales
a los pesos y a los PNG). Carga los pesos en CPU con `weights_only=True`,
evalúa validación y recorre la curva ROC.
