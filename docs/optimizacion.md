# Optimización del modelo

**Proceso de optimización (Workshop S5)**

**Copiloto de triaje para neumonía en adultos** · EfficientNet-B0 a 320 px, calibrada, con umbral de cribado y umbral por vista opcional.

Este documento cuenta cómo se llegó a la configuración del modelo desplegado: qué corridas se
compararon, qué se ajustó y por qué, cómo se diagnosticó el sobreajuste, qué sensibilidad a los
hiperparámetros sostienen las corridas reales y cuál no, y cómo se calibró y se eligió el punto
de operación. Cada cifra sale de un fichero del repositorio o de un documento de las Semanas 2
a 4 que se cita al lado.

El cuaderno `notebooks/04_optimizacion.ipynb` acompaña este documento con el código de la
comparación de corridas, el análisis de sensibilidad, la calibración y el umbral.

## Una advertencia antes de empezar

**El proyecto no hizo una búsqueda sistemática de hiperparámetros** (rejilla, aleatoria o
bayesiana). El diseño de SP1 la aplazó al tercer sprint y no llegó a hacerse: la optimización
fue una secuencia de iteraciones medidas sobre unas pocas corridas, todas sobre la misma
partición de los datos y con una sola semilla por configuración (42 en las corridas de
diagnóstico). No hubo validación cruzada.

Eso fija lo que se puede afirmar:

- Se puede decir **qué cambios movieron la métrica y cuánto**, y cuáles quedaron dentro del ruido.
- **No se puede** construir con honestidad un ranking de importancia de hiperparámetros,
  gráficos de dependencia parcial sobre varias dimensiones ni un análisis de interacciones: no
  hay un diseño de experimentos que los sostenga. La sección 7 explica por qué y qué se ofrece
  en su lugar.

Cuando el taller pide algo que el proyecto no puede dar, aquí se dice, en vez de rellenarlo.

### Qué pide el taller y dónde está

| Punto del taller (Semana 5) | Dónde | Lo que hay |
| :--- | :--- | :--- |
| Proceso de optimización | Secciones 3, 5 y 6 | Ocho corridas comparadas, los cambios aplicados y el diagnóstico |
| Hiperparámetros explorados y rangos | Sección 4 | Tabla con lo probado, cómo y con qué nivel de evidencia |
| Resultados del análisis de sensibilidad | Sección 7 | Sensibilidad que las corridas reales sostienen |
| Gráficos de dependencia parcial | Sección 7.5 | Solo las dos dependencias unidimensionales legítimas: umbral y época |
| Ranking de importancia | Sección 7.6 | **No hay ranking**; sí un orden de magnitudes observadas, con sus reservas |
| Análisis de interacciones | Sección 7.7 | **No es estimable** con estos datos |
| Configuración final y justificación | Sección 11 | Tabla completa |
| Comparación antes y después | Sección 12 | Primera corrida frente a la desplegada |

## Contenido

1. [Resumen](#1-resumen)
2. [Qué se optimiza y cómo se evalúa](#2-qué-se-optimiza-y-cómo-se-evalúa)
3. [Las corridas](#3-las-corridas)
4. [Hiperparámetros explorados y rangos](#4-hiperparámetros-explorados-y-rangos)
5. [Qué se ajustó y por qué](#5-qué-se-ajustó-y-por-qué)
6. [Diagnóstico de sobreajuste y subajuste](#6-diagnóstico-de-sobreajuste-y-subajuste)
7. [Sensibilidad a los hiperparámetros](#7-sensibilidad-a-los-hiperparámetros)
8. [Calibración](#8-calibración)
9. [El umbral de cribado y la frontera entre recall y especificidad](#9-el-umbral-de-cribado-y-la-frontera-entre-recall-y-especificidad)
10. [El umbral por vista y su precio](#10-el-umbral-por-vista-y-su-precio)
11. [Configuración final y justificación](#11-configuración-final-y-justificación)
12. [Comparación antes y después](#12-comparación-antes-y-después)
13. [Lo que no se hizo y lo que haría falta](#13-lo-que-no-se-hizo-y-lo-que-haría-falta)
14. [Cómo reproducirlo](#14-cómo-reproducirlo)

## 1. Resumen

| | Primera corrida (19-sep) | Modelo desplegado |
| :--- | :--- | :--- |
| Modelo | MobileNetV3-Large, 224 px, ajuste fino de los 3 últimos bloques | EfficientNet-B0, 320 px, ajuste fino de la red completa |
| Recall en prueba | 0,766 | 0,882 |
| Especificidad en prueba | 0,764 | 0,702 |
| AUC en prueba | 0,845 | 0,885 |

Lo que se aprendió, de lo más sólido a lo más reservado:

1. **El fallo de la primera corrida tuvo dos causas.** El modelo no había convergido (AUC de
   0,845, que ningún umbral compensaba) y la regla de elección del umbral escogía un punto
   que incumplía un mínimo teniendo otro que cumplía los dos (sección 5).
2. **La mejora vino de un paquete de cambios** (resolución, ajuste fino completo, más épocas,
   calendario de la tasa de aprendizaje), no de cambiar de arquitectura. Las tres arquitecturas
   quedan dentro de un rango de AUC de 0,015, del orden del ruido entre repeticiones. El
   paquete no permite atribuir la mejora a un factor concreto (sección 7).
3. **Las tres arquitecturas sobreajustan** en cuanto se libera el backbone, y la parada
   temprana ya lo contenía (sección 6).
4. **Los dos objetivos de la CNN no se alcanzan a la vez**: no existe un punto con recall ≥ 0,85
   y especificidad ≥ 0,75. Se prioriza el recall y se publica la frontera (sección 9).
5. **Con un umbral único, el modelo rinde distinto por proyección**: recall 0,693 en PA frente a
   0,941 en AP. Un umbral por vista lo corrige a cambio de especificidad (sección 10).
6. **La salida cruda no es una probabilidad**: se calibra con una regresión isotónica
   (sección 8).

## 2. Qué se optimiza y cómo se evalúa

### 2.1 El objetivo

Las metas son las de la Semana 1 (spec de SP1, §2), con una jerarquía que el diseño escribió
explícitamente: **el recall es la métrica primaria**, porque en triaje un falso negativo
(mandar a casa una neumonía) es el error caro y un falso positivo cuesta una placa revisada de
más (`docs/frontera-recall-especificidad.md`).

| Métrica | Mínimo | Objetivo |
| :--- | :-: | :-: |
| Recall | 0,80 | 0,85 |
| Especificidad | 0,70 | 0,75 |
| AUC-ROC | 0,85 | 0,88 |

La exactitud (*accuracy*) no se usa como métrica principal: con 22,15 % de positivos, predecir
siempre «negativo» daría cerca de un 78 % de exactitud y recall cero.

### 2.2 El protocolo

- **Una sola partición** 70/15/15 por paciente (17 782 / 3 810 / 3 811 placas), igual en todas
  las corridas para que sean comparables, con verificación automática de que ningún paciente
  está en dos conjuntos.
- **La validación elige y la prueba mide.** El umbral, el calibrador y el criterio de época se
  deciden sobre validación; la prueba se lee al final.
- **Una reserva declarada.** En la comparativa de corridas se miró la prueba para ordenarlas,
  y eso, en rigor, es usar la prueba para seleccionar: deja la métrica de la corrida ganadora
  algo optimista (`docs/comparativa-corridas.md`). Por eso la corrida desplegada no se eligió
  por ser la primera de esa tabla (sección 3.3).
- **El umbral nunca se reelige mirando la prueba** (`docs/frontera-recall-especificidad.md`).

## 3. Las corridas

### 3.1 Las ocho corridas a 320 px

Comparativa generada por `scripts/comparar_corridas.py` el 24-sep-2026, con métricas en el
conjunto de **prueba** (`docs/comparativa-corridas.md`). El coste de entrenamiento se da en
horas, convertido desde las cifras de la comparativa, que coinciden con segundos (Semana 2:
0,33 h, 0,50 h y 1,62 h para las tres arquitecturas en la misma GPU), y no es comparable entre
entornos distintos.

| # | Corrida | Arquitectura | Épocas | Mejor época | Recall | Espec. | AUC | Coste |
| -: | :--- | :--- | :-: | :-: | -: | -: | -: | -: |
| 1 | `kaggle_efficientnet_b0_320px_c2` | EfficientNet-B0 | 4+20 | 6 | 0,892 | 0,709 | 0,889 | 0,48 h |
| 2 | `kaggle_densenet121_320px_c1` | DenseNet121 | 4+20 | 10 | 0,891 | 0,702 | 0,874 | 1,62 h |
| 3 | `kaggle_densenet121_320px_c2` | DenseNet121 | 4+20 | 10 | 0,891 | 0,702 | 0,874 | 1,57 h |
| 4 | `kaggle_efficientnet_b0_320px_c1` | EfficientNet-B0 | 4+20 | 6 | 0,889 | 0,708 | 0,888 | 0,50 h |
| 5 | `kaggle_mobilenet_v3_large_320px_c1` | MobileNetV3-L | 4+20 | 6 | 0,882 | 0,706 | 0,886 | 0,33 h |
| 6 | **`efficientnet_b0_320px_lote24_4+20ep`** (la desplegada) | EfficientNet-B0 | 4+20 | 5 | 0,882 | 0,702 | 0,885 | ≈ 5,3 h (CPU) |
| 7 | `kaggle_mobilenet_v3_large_320px_c2` | MobileNetV3-L | 4+20 | 9 | 0,874 | 0,706 | 0,876 | 0,41 h |
| 8 | `corrida2_densenet121_320px` | DenseNet121 | 4+4 | 7 | 0,880 | 0,699 | 0,888 | n/d |

El coste de la corrida 6 (≈ 5,3 h, 19 026 s) es el de las **11 épocas** que corrió antes de que la
parada temprana la detuviera, con su mejor época en la 5; las 24 épocas completas (4 + 20) de
EfficientNet-B0 en CPU cuestan 10,8 h (`docs/desarrollo.md`, §4). Las dos cifras son ciertas y no
se contradicen.

Las siete primeras cumplen los tres mínimos (recall ≥ 0,80, especificidad ≥ 0,70 y AUC ≥
0,85); la octava incumple la especificidad por una milésima (0,699). Ninguna alcanza a la vez
el objetivo de especificidad (0,75). La regla de selección está escrita entera y en orden en la
comparativa: criterios del spec satisfechos, a igualdad mayor recall y, si también empatan,
mayor AUC; si ninguna cumple los tres mínimos no se corona ninguna.

### 3.2 Las tres corridas de diagnóstico (26-sep)

Para el diagnóstico de sobreajuste de la Semana 3 se reentrenaron en Kaggle las tres
arquitecturas con la misma configuración y partición que el modelo desplegado y **con registro
de la pérdida de validación por época** (el bucle original no la medía). Resultado en prueba
(`Hallazgos medidos`, Semana 3, §6):

| Arquitectura | Recall | Especificidad | AUC |
| :--- | -: | -: | -: |
| EfficientNet-B0 | 0,883 | 0,714 | 0,8852 |
| DenseNet121 | 0,871 | 0,715 | 0,8797 |
| MobileNetV3-L | 0,884 | 0,707 | 0,8776 |

Esto limita lo que el diagnóstico de la sección 6 puede afirmar: describe **este régimen de
entrenamiento**, no los pesos concretos desplegados, cuyo historial no trae la pérdida de
validación.

### 3.3 Por qué se despliega la corrida 6 y no la primera de la tabla

La comparativa corona `kaggle_efficientnet_b0_320px_c2` (AUC 0,889). Se despliega la corrida 6
(AUC 0,885). La razón está escrita en `docs/sp2-despliegue.md` y es de método, no de
rendimiento:

- Las ocho corridas caben en un rango de AUC de 0,015, **del orden de lo que mueve una semilla
  distinta**: las dos ejecuciones de una misma configuración de MobileNetV3 difieren en 0,010.
  Elegir la que casualmente queda arriba es seleccionar por ruido.
- La corrida 6 tiene **el calibrador isotónico ajustado sobre sus propias 3 810 radiografías de
  validación** y los pesos verificados por huella. Un calibrador ajustado sobre una corrida y
  aplicado a otra introduce un sesgo silencioso en la razón de verosimilitud que consume la
  combinación bayesiana. Cambiar de corrida obliga a reajustar el calibrador, a volver a medir
  la frontera y a reelegir el umbral, a cambio de una diferencia que la propia medición no
  distingue del ruido.

El mismo argumento está en `docs/frontera-recall-especificidad.md`: no se reentrena para
perseguir las cinco milésimas de AUC que separan poder de no poder cumplir los dos objetivos,
porque elegir la corrida que casualmente cruza el listón es seleccionar por ruido.

## 4. Hiperparámetros explorados y rangos

Lo que se probó de verdad, cómo y con qué nivel de evidencia.

| Hiperparámetro | Valores probados | Cómo | Evidencia |
| :--- | :--- | :--- | :--- |
| Arquitectura | MobileNetV3-Large, EfficientNet-B0, DenseNet121 | Ocho corridas y tres de diagnóstico, a 320 px | Dentro del ruido; las corridas cambian también de entorno y de coste |
| Resolución de entrada | 224 px y 320 px | Primera corrida frente a las demás | **Confundida** con otros cambios (ver abajo) |
| Profundidad del ajuste fino | 3 últimos bloques; red completa | Ídem | Confundida |
| Épocas (cabeza + ajuste) | 3 + 7 (paró a las 7: 3 de cabeza y 4 de ajuste), 4 + 4, 4 + 20 | Ídem | Confundida |
| Calendario de la tasa de aprendizaje | Fija; recocido coseno | Ídem | Confundida |
| Lote | 32; 24 | Ídem | Confundido |
| Paciencia de la parada temprana | 3 (primera corrida), 5 (la actual); 2 y 3 simuladas | Simulación sobre el historial grabado | Medida, sin reentrenar |
| Criterio de selección de época | Recall con AUC de desempate; solo AUC; menor pérdida de validación | Simulación sobre el historial | Medida |
| Umbral de decisión | Curva ROC de validación completa; seis puntos publicados; dos umbrales por vista | Validación, y prueba una sola vez | Medida; es exacta porque el umbral no requiere reentrenar |
| Filtro de edad (dato) | Todo el padrón; solo 18 a 100 años | Decisión del EDA | Conservó la tasa de positivos (22,15 % frente a 22,53 %) |
| Tasa de aprendizaje | 1e-3 en la cabeza y 2e-4 en el ajuste | Fija | **No explorada** |
| Peso de clase | `pos_weight` = negativos / positivos (3,44 en el desplegado) | Fijo | **No explorado** |
| Aumento de datos | Rotación de ±7°, desplazamiento del 5 %, brillo y contraste de ±0,15 | Fijo | Su efecto sobre la pérdida está medido; **no hay ablación** |
| Weight decay, dropout, optimizador | Adam sin decaimiento de pesos explícito; la cabeza conserva el dropout predeterminado de torchvision (solo se sustituye la última capa lineal) | Fijos | **No explorados** |
| Semilla | 42 | Fija | **No variada** |

El rango probado en cada eje es muy corto (dos o tres valores) y casi todos los cambios se
hicieron **a la vez**. Es la consecuencia de optimizar por iteraciones y no por diseño de
experimentos, y es lo que impide los análisis de la sección 7.

## 5. Qué se ajustó y por qué

### 5.1 La primera corrida y lo que midió

Configuración de la primera corrida (19-sep): MobileNetV3-Large, 224 px, tres épocas de cabeza
y cuatro de ajuste (paró por paciencia), ajuste fino de los tres últimos bloques
(`docs/mejoras-2026-09-21.md`, §1).

| Criterio (spec §2) | Mínimo | Objetivo | Medido en prueba |
| :--- | :-: | :-: | :-: |
| Recall | 0,80 | 0,85 | **0,766** (no cumple) |
| Especificidad | 0,70 | 0,75 | 0,764 (cumple) |
| AUC-ROC | 0,85 | 0,88 | **0,845** (no cumple) |
| Latencia de inferencia en CPU | < 4 s | < 1 s | 0,023 s (cumple) |

Dos de cuatro. Falló la métrica primaria. La curva de entrenamiento decía que el modelo no
había convergido: el AUC de validación seguía subiendo cuando se detuvo (0,812; 0,830; 0,836;
0,854; 0,855; 0,857).

### 5.2 El techo no era el umbral

Leyendo la curva ROC de prueba de ese modelo, el recall máximo alcanzable según la
especificidad que se exija:

| Especificidad exigida | Recall máximo alcanzable |
| :-: | :-: |
| 0,75 (objetivo) | 0,780 |
| 0,70 (mínimo) | 0,834 |
| 0,65 | 0,876 |

Con ese modelo, un recall de 0,85 exigía bajar la especificidad a 0,679, por debajo del piso de
0,70: ningún umbral lo arreglaba. Hacía falta un AUC en torno a 0,88.

### 5.3 Un fallo en la regla del umbral

La regla original decía: «si ni relajando a la especificidad mínima se alcanza el recall
objetivo, conserva el umbral del paso 1». La intención era no forzar el umbral para maquillar un
número; el efecto fue elegir un punto que incumplía el mínimo de recall (0,78) teniendo
disponible otro que cumplía los dos mínimos (0,834 con especificidad 0,70).

La regla nueva ordena los puntos de operación por cuánto del spec satisfacen y, ante empate,
prefiere el de mayor especificidad (`src/copiloto_triaje/modelo/evaluacion.py`, `elegir_umbral`):
recall objetivo con especificidad objetivo; recall objetivo con la especificidad mínima;
recall mínimo con especificidad objetivo; recall mínimo con la especificidad mínima; y, si ni el
recall mínimo se alcanza, el de mayor recall dentro del piso, reportado tal cual.

El documento de mejoras estimó que esta corrección sola, sin reentrenar, habría movido el
recall reportado de 0,766 a cerca de 0,83.

### 5.4 Los cambios para la segunda corrida

Mecanismo de decisión: la evidencia de la primera corrida y el análisis exploratorio
(`docs/mejoras-2026-09-21.md`, §4).

| Cambio | De | A | Por qué |
| :--- | :--- | :--- | :--- |
| Resolución | 224 px | **320 px** | Las opacidades son sutiles y difusas; reducir una placa de 1 024 píxeles a 224 tira la mayor parte de la señal |
| Arquitectura | MobileNetV3-Large | **DenseNet121** (después se compararon las tres) | Es la red de CheXNet. La elección original de MobileNetV3 fue por una restricción de sistema (menos de 4 s en CPU); medida, la latencia fue 0,023 s, así que la restricción no era vinculante |
| Épocas | 3 + 7 (paró a las 7) | **4 + 20** | El AUC seguía subiendo al parar |
| Ajuste fino | 3 últimos bloques | **Red completa** | Las características de ImageNet transfieren a rayos X, pero no del todo (un canal, estadística distinta) |
| Tasa de aprendizaje | Fija | **Recocido coseno** | Baja de forma suave para afinar al final |
| Paciencia | 3 | **5** | Con más épocas y tasa decreciente, cortar a las 3 es prematuro |
| Lote | 32 | **24** | A 320 px y con DenseNet121 el consumo de memoria sube |
| Población | Todo el padrón | **18 a 100 años** | El EDA halló 1 276 menores y 5 edades imposibles (`docs/analisis_datos.md`) |

### 5.5 Lo que resultó

Entrenadas las tres arquitecturas a 320 px, el resultado fue una sorpresa que corrigió la
hipótesis de partida. Se creía que el salto vendría de cambiar a DenseNet121; **no fue así**. Las
tres quedan en AUC 0,874 a 0,889, DenseNet121 da el valor más bajo y cuesta unas 3,2 veces más
entrenar que EfficientNet-B0 en la misma GPU (1,62 h frente a 0,50 h; Semana 2). Lo que movió la
métrica fue el paquete: la **misma** MobileNetV3-Large pasa de AUC 0,845 a 0,886 al subir de 224
a 320 px y descongelar la red completa (Registro de cambios de la Presentación del proyecto, 23-sep).

**Esta atribución debe leerse con cuidado.** En la tabla de arriba cambiaron a la vez la
resolución, la profundidad del ajuste fino, las épocas, el calendario de la tasa de aprendizaje,
la paciencia, el lote y la población. Las semanas 1 y 2 atribuyen la mejora a la resolución y al
ajuste fino, y es una hipótesis razonable y la mejor disponible, pero ninguna corrida cambió una
sola cosa, así que el efecto de cada factor no está aislado.

## 6. Diagnóstico de sobreajuste y subajuste

### 6.1 Subajuste en la primera corrida

La primera corrida se detuvo con el AUC de validación todavía subiendo: no había convergido.
Es subajuste por entrenamiento corto, y por eso el paquete de la sección 5.4 alargó las épocas
y descongeló la red entera.

### 6.2 Sobreajuste al liberar el backbone

Con más capacidad y más épocas apareció el problema contrario. Las tres corridas de diagnóstico
(26-sep; misma configuración y partición que el modelo desplegado) dan un veredicto claro
(`Hallazgos medidos`, Semana 3, §3; las épocas se numeran desde 0):

| | DenseNet121 | EfficientNet-B0 | MobileNetV3-L |
| :--- | -: | -: | -: |
| Épocas corridas | 14 | 13 | 14 |
| Mínimo de la pérdida de validación | 0,6937 (ép. 6) | 0,6947 (ép. 7) | 0,6999 (ép. 6) |
| Pérdida de validación al final | 0,8238 | 1,1690 | 1,3666 |
| Subida desde el mínimo | +18,7 % | +68,3 % | +95,3 % |
| AUC de entrenamiento al final | 0,9762 | 0,9910 | 0,9918 |
| AUC de validación al final | 0,8718 | 0,8670 | 0,8629 |
| Brecha de AUC al final | 0,1043 | 0,1239 | 0,1289 |
| Crecimiento de la brecha desde la época 4 | ×10,7 | ×13,8 | ×26,5 |

- **Sobreajuste**: la brecha crece, el AUC de entrenamiento llega a 0,98-0,99 con 0,86-0,87 de
  validación, y la pérdida de validación sube mientras la de entrenamiento baja. El giro ocurre
  entre las épocas 6 y 7 en las tres.
- **No es subajuste**: la pérdida de entrenamiento baja hasta 0,18-0,34. El modelo tiene
  capacidad de sobra.
- **Empieza al liberar el backbone**: el ajuste fino arranca en la época 4 y el mínimo de
  validación cae 2 a 3 épocas después, en las tres. Mientras solo se entrena la cabeza hay
  pocos parámetros y poca capacidad de memorizar.
- **La brecha se mide con la pérdida limpia**, no con la de la pasada de entrenamiento: esta
  última se calcula mientras los pesos cambian y sobre imágenes aumentadas, y subestima la
  brecha entre 0,0974 y 0,1510 en la última época. En las primeras épocas puede invertirla,
  de modo que un sobreajuste parezca subajuste.

### 6.3 Lo que la parada temprana ya evitaba

El proyecto ya paraba por fase (paciencia 5) y restauraba la mejor época. Su valor, medido con
el historial grabado (el «antes» es la última época entrenada y el «después», la elegida):

| | AUC de validación en la época elegida | En la última | Coste de no parar |
| :--- | -: | -: | -: |
| DenseNet121 | 0,8753 | 0,8718 | −0,0035 |
| EfficientNet-B0 | 0,8802 | 0,8670 | −0,0132 |
| MobileNetV3-L | 0,8781 | 0,8629 | −0,0152 |

Con parada, la pérdida de validación baja un 13,5 %, un 40,6 % y un 41,0 % respectivamente.
Con la parada, las tres corridas superan los tres mínimos en prueba (sección 3.2).

### 6.4 Lo que este diagnóstico no dice

Son tres corridas con una sola semilla. Las diferencias entre arquitecturas (por ejemplo el
×26,5 de MobileNetV3-L frente al ×10,7 de DenseNet121) **no se pueden atribuir a la
arquitectura**. Lo que las tres sostienen a la vez, y es el hallazgo, es la dirección: las tres
sobreajustan, las tres tocan fondo entre las épocas 6 y 7 y las tres divergen después.

## 7. Sensibilidad a los hiperparámetros

### 7.1 La escala del ruido

Para saber si una diferencia significa algo hay que saber cuánto se mueve la métrica entre
repeticiones de la **misma** configuración. AUC en prueba, de las tablas de las secciones 3.1 y 3.2:

| Configuración | Repeticiones (AUC en prueba) | Rango |
| :--- | :--- | -: |
| EfficientNet-B0, 4+20 | 0,885 (CPU local), 0,888, 0,889, 0,885 (diagnóstico) | 0,004 |
| MobileNetV3-L, 4+20 | 0,886, 0,876, 0,878 (diagnóstico) | 0,010 |
| DenseNet121, 4+20 | 0,874, 0,874, 0,880 (diagnóstico) | 0,006 |

Las repeticiones difieren en plataforma y, en las de diagnóstico, comparten semilla (42): lo
que mide esta tabla es el no determinismo entre entornos más el azar de la época elegida, y una
semilla distinta movería, si acaso, más. Es un suelo del ruido, no un techo. El recall y la
especificidad se mueven más que el AUC, porque además dependen del umbral que eligió cada
corrida: hasta 0,020 de recall (DenseNet121, de 0,871 a 0,891) y 0,013 de especificidad (de
0,702 a 0,715) entre repeticiones de una misma configuración.

### 7.2 Efectos que las corridas sí sostienen

| Cambio | Efecto observado | Comparado con el ruido | Lectura |
| :--- | :--- | :--- | :--- |
| Paquete 224 px y 3 bloques → 320 px, red completa, 4+20, coseno, lote 24 (MobileNetV3-L) | AUC en prueba 0,845 → 0,886 (+0,041) | 4 veces el rango de ruido más amplio (0,010) | El efecto mayor y claro, pero **no atribuible a un solo factor** |
| Regla de elección del umbral (corregida) | Recall a especificidad ≈ 0,70: de 0,766 a ≈ 0,83 con el mismo modelo | No aplica | Efecto grande sobre el punto de operación, ninguno sobre el AUC |
| Parada temprana frente a la última época | AUC de validación +0,0035, +0,0132, +0,0152 | Del orden del ruido o por encima | Medido sobre historial real |
| Arquitectura (tres) a 320 px | Rango de AUC en prueba 0,874-0,889 | Del orden del ruido | Empate práctico (véase 7.3) |
| Paciencia 5 → 3 | Misma época elegida y mismo AUC en las tres; dos épocas menos | Cero | Gratis |
| Paciencia 5 → 2 | La selección cae a la época 4 en dos de tres: AUC −0,017 y −0,004 | Por encima del ruido | Ya no es gratis |
| Criterio «solo AUC» en vez de recall con AUC | +0,0012 en DenseNet121 y en MobileNetV3-L; sin cambio en EfficientNet-B0 | Dentro del ruido | No se cambia: el AUC no es el criterio clínico |

### 7.3 Arquitectura: un empate práctico

En las repeticiones disponibles, las cuatro de EfficientNet-B0 (0,885 a 0,889) quedan por
encima de las tres de DenseNet121 (0,874 a 0,880), y las de MobileNetV3-L (0,876 a 0,886) se
solapan con las dos. Son tres o cuatro valores por arquitectura, no semillas independientes, y
el proyecto las trató como un empate, aunque el coste (DenseNet121 es unas 3,2 veces más cara) y
la existencia de un calibrador propio de la corrida 6 inclinaron la decisión hacia
EfficientNet-B0. Para decir algo más sobre arquitecturas harían falta al menos tres semillas por
arquitectura (sección 13).

### 7.4 El criterio de selección de época

El proyecto selecciona la época por **recall con AUC de desempate**, porque en triaje el falso
negativo es el error caro. Comparado con las alternativas sobre el mismo historial
(`Hallazgos medidos`, Semana 3, estrategia 3):

| Corrida | Recall con AUC | Solo AUC | Menor pérdida de validación |
| :--- | :-: | :-: | :-: |
| DenseNet121 | ép. 8, AUC 0,8753 | ép. 10, **0,8765** | ép. 6, 0,8752 |
| EfficientNet-B0 | ép. 7, 0,8802 | ép. 7, 0,8802 | ép. 7, 0,8802 |
| MobileNetV3-L | ép. 8, 0,8781 | ép. 5, **0,8793** | ép. 6, 0,8761 |

«Solo AUC» gana por 0,001, pero optimiza la métrica que se mide en vez de la que importa. Y un
matiz que contradice la intuición: la época que minimiza la pérdida de validación no es
siempre la mejor por el criterio clínico (en DenseNet121 la pérdida mínima está en la época 6 y
el mejor AUC en la 10).

### 7.5 Dependencias parciales unidimensionales

El taller pide gráficos de dependencia parcial. Con un diseño de experimentos habría que
reentrenar para cada valor de cada hiperparámetro mientras se promedia sobre los demás, y el
proyecto no lo hizo. Hay **dos** dependencias unidimensionales que sí se pueden construir sin
inventar nada, porque no requieren reentrenar:

**a) Recall y especificidad frente al umbral de decisión.** Es la dependencia exacta de la
métrica respecto del único hiperparámetro de la regla de decisión. Sobre validación
(3 810 placas), con los pesos desplegados (`docs/frontera-recall-especificidad.md`; AUC de
validación 0,8827):

| Especificidad exigida | Especificidad real | Recall | Umbral |
| -: | -: | -: | -: |
| 0,70 | 0,7006 | **0,8815** | 0,4258 |
| 0,72 | 0,7256 | 0,8637 | 0,4649 |
| 0,75 | **0,7522** | 0,8400 | 0,5029 |
| 0,78 | 0,7815 | 0,8187 | 0,5407 |
| 0,80 | 0,8007 | 0,8033 | 0,5654 |
| 0,85 | 0,8506 | 0,7358 | 0,6575 |

(El cuaderno 04 recalcula esta tabla y imprime 0,5655 en el umbral de la fila de 0,80, una
diezmilésima de diferencia en la última cifra por el redondeo; se deja el 0,5654 del documento de
la frontera, que es la fuente.)

Es una curva monótona sin sorpresas: cada punto de especificidad que se pide cuesta recall. En
la zona de interés (0,70 a 0,80) cada 0,01 de especificidad cuesta entre 0,007 y 0,009 de
recall, y entre 0,80 y 0,85 cuesta cerca de 0,014 (cálculo sobre la tabla).

**b) La pérdida y el AUC de validación frente a la época.** Es la curva de aprendizaje de las
tres corridas de diagnóstico: la pérdida de validación baja hasta las épocas 6 o 7 y sube
después, mientras el AUC de entrenamiento sigue subiendo (sección 6.2). Las figuras
(`perdidas_*.png`, `auc_*.png`, `brecha.png` y `comparativa.png`, a 300 DPI) forman parte de la
entrega de la Semana 3 y las regenera `scripts/diagnostico_curvas.py` sobre los historiales
guardados.

### 7.6 Un ranking de importancia: no se puede, y esto es lo más cerca que se llega

Un ranking de importancia exige variar cada hiperparámetro de forma independiente y atribuirle
una parte de la varianza de la métrica. Aquí **los cambios fueron simultáneos** y las
repeticiones son pocas, así que cualquier ranking sería inventado. Lo que sí se puede ofrecer
es un **orden de las magnitudes observadas**, que no es importancia atribuible:

| Orden | Cambio | Magnitud observada |
| :-: | :--- | :--- |
| 1 | El paquete de la segunda corrida (resolución, ajuste fino completo, épocas, calendario, lote) | AUC +0,041 |
| 2 | La regla de elección del umbral | Recall +0,068 a la misma especificidad, sin tocar el AUC |
| 3 | La parada temprana frente a la última época | AUC de validación +0,0035 a +0,0152 |
| 4 | La arquitectura | Rango de 0,015 en AUC, del orden del ruido |
| 5 | El criterio de selección de época y la paciencia (3 frente a 5) | ≤ 0,001 de AUC |

### 7.7 Interacciones: no estimables

No hay datos para estimar interacciones entre hiperparámetros: no existe ninguna combinación en
la que se haya variado un factor con los demás fijos. Dos observaciones, sin conclusión:

- La corrida 8 (DenseNet121, 4 + 4 épocas) tiene un AUC mayor (0,888) que las de 4 + 20 (0,874),
  lo que contradice que más épocas ayuden, pero cambian a la vez el entorno y el coste y la parada
  temprana ya escoge la mejor época, así que no se puede atribuir a las épocas.
- El umbral interactúa con la proyección de la placa: el mismo umbral global deja un recall muy
  distinto en PA y en AP. Es un resultado, no una estimación de interacción (sección 10).

### 7.8 Un riesgo de la selección del umbral que se midió

Elegir el umbral sobre validación y aplicarlo a prueba hace que un punto que justo roza el piso
de especificidad caiga por encima o por debajo según el azar del muestreo. Por simulación con las
dimensiones reales del proyecto (3 810 y 3 811 placas, 22,15 % de positivos, AUC 0,888), sin
margen solo el 84 % de las corridas cumple el piso de especificidad en prueba, y con un margen
de 0,02 en la elección sube al 97 % a cambio de 0,003 de recall
(`src/copiloto_triaje/modelo/evaluacion.py`). Una corrida de DenseNet121 del 23-sep, la de
especificidad 0,699 de la tabla de la sección 3.1, cayó en ese 16 % (frente a un mínimo de
0,700). El margen se añadió el 23-sep; el umbral
desplegado, 0,4258, corresponde a exigir 0,70 de especificidad en validación sin margen y salió
en prueba con 0,7024: cumple el mínimo, pero ese 0,002 es parte azar.

## 8. Calibración

**Por qué hace falta.** El modelo se entrenó con `BCEWithLogitsLoss` y `pos_weight` = 3,44 para
compensar el 22,15 % de positivos. Eso desplaza su salida hacia arriba: 0,74 no significa 74 %
de probabilidad de neumonía (spec de SP2, §6.1). La combinación bayesiana multiplica las
razones de verosimilitud y meter ahí la salida cruda daría una posterior equivocada sin que nada
fallara de forma visible.

**Qué se hizo.** Una regresión isotónica ajustada **solo sobre validación** (3 810 placas) y
guardada como 200 puntos de la curva en `servidor/calibrador.json`, que se versiona porque pesa
unos pocos kilobytes y registra con qué corrida se ajustó (`scripts/ajustar_calibrador.py`). De la
probabilidad calibrada se deriva la razón de verosimilitud de la imagen:

`RV = [p / (1 − p)] / [prevalencia / (1 − prevalencia)]`, con la prevalencia del conjunto, 0,2215.

**Una cota deliberada.** La isotónica satura en 0,0 y 1,0 en un solo punto de cada extremo,
donde el tramo ya no tiene contraejemplos: eso es un artefacto y no una medición, y daría razones
de 3,5e-06 y 3,5e+06. Con una de ellas, un previo clínico de 0,90 acabaría en una posterior de
0,003 %, certeza de ausencia por una sola placa. Por eso la razón se acota al último valor
**sostenido** de la curva por cada lado:

| Cota | Probabilidad calibrada | Razón de verosimilitud |
| :--- | -: | -: |
| Mínima | 0,004608 | 0,0163 |
| Máxima | 0,956522 | 77,32 |

La evidencia de la imagen puede mover el previo clínico, pero no anularlo ni volverlo certeza
(`docs/sp2-despliegue.md`, §9). Las cotas se recalculan al cargar el calibrador, y una prueba
falla si cambian sin que se actualice el documento de despliegue.

**Cómo salió, en prueba.** Sobre las 3 811 placas de prueba, que no se usaron para ajustar el
calibrador (`docs/validacion-semisintetica-sp5.md`, «La imagen sola»):

| Brier | Pendiente | Intercepto | ECE | Suelo de la ECE (media) | Suelo de la ECE (p95) |
| -: | -: | -: | -: | -: | -: |
| 0,108 | 0,98 | 0,012 | 0,016 | 0,012 | 0,017 |

La pendiente es 0,98 y el intercepto 0,012: la calibración queda muy cerca de la ideal (1 y 0).
La ECE (0,016) **no supera el percentil 95 de su suelo de ruido** (0,017), calculado con
juegos de etiquetas simuladas con las probabilidades del propio modelo: no se distingue del
ruido de muestreo. La ECE se lee siempre al lado de su suelo y no frente a un umbral absoluto.

**La ECE de una isotónica depende de cómo se rompen los empates.** El calibrador deja solo 674
valores distintos de probabilidad entre las 3 811 placas, y la ECE por deciles de igual masa
tiene que decidir en qué decil cae cada placa empatada. Medido con las mismas puntuaciones y el
mismo calibrador: con el orden de las filas del fichero la ECE sale 0,0231 (su suelo, con ese
desempate, tiene el percentil 95 en 0,0166, y entonces sí lo supera); con el rango de
`patientId`, la regla declarada en la especificación de la validación semisintética, sale
0,0163 (percentil 95 de su suelo, 0,0174). **La que se publica en todas partes es la segunda**
(README, ficha del modelo, cuaderno 04, `results/` y la simulación): `src/evaluate.py` rompe los
empates igual que la simulación. El Brier (0,108) y la pendiente (0,98) no cambian con el
desempate; la lectura que sostienen los datos es «calibración cercana a la ideal», no «ECE
indistinguible del ruido con cualquier desempate».

**Límites.** Está calibrada en RSNA, donde la prevalencia es de 0,2215; la prevalencia de un
centro real será otra, y por eso la razón de verosimilitud, que no depende de la población,
es lo que se entrega, y el previo se declara aparte (0,1466 por defecto). No se validó la
calibración en otra población ni en pacientes reales.

## 9. El umbral de cribado y la frontera entre recall y especificidad

El umbral por defecto es **0,4258**, elegido sobre validación con la regla de la sección 5.3
(recall con la especificidad mínima de 0,70). El conjunto de prueba no se tocó para elegirlo.

La frontera que la tabla de la sección 7.5 muestra tiene una consecuencia que obligó a corregir
lo entregado: **no existe ningún punto con recall ≥ 0,85 y especificidad ≥ 0,75 a la vez.** El
más cercano con especificidad ≥ 0,75 da recall 0,840. El documento maestro de la Semana 1
comprometía «recall ≥ 85 % y especificidad ≥ 75 %» en tres sitios; la contradicción era interna
(su propia tabla de umbrales distinguía mínimo de objetivo), y el 23-sep se unificó el criterio
en recall ≥ 85 %, especificidad ≥ 70 % (objetivo 75 %) y AUC ≥ 0,85.

Estamos en la frontera, no lejos: una corrida de EfficientNet-B0 en Kaggle (AUC 0,888 frente a
0,883 de la desplegada) registró en una época recall 0,851 con especificidad 0,752 en
validación. La diferencia entre poder y no poder es de unas cinco milésimas de AUC, del orden del
ruido. No se reentrenó para perseguirlas.

**Publicar la frontera, no un punto.** Decirle al profesional «puede operar en 0,88 con 0,70 o
en 0,84 con 0,75, y esto cuesta cada opción» es más útil y más defendible que esconder la
disyuntiva tras una cifra. El punto por defecto prioriza el recall por una razón clínica que se
escribe en vez de dejarla implícita en el código.

Resultado en prueba con el umbral único (`app/assets/metricas.json`, bloque `global`):

| | Valor | IC 95 % de Wilson |
| :--- | -: | :-: |
| Recall | 0,8815 | 0,858 a 0,902 |
| Especificidad | 0,7024 | 0,686 a 0,719 |
| AUC | 0,8848 | — |

## 10. El umbral por vista y su precio

### 10.1 El problema

Con el umbral único, el rendimiento difiere mucho por proyección (`app/assets/metricas.json`):

| Proyección | Placas | Recall | Especificidad |
| :--- | -: | -: | -: |
| PA (de pie) | 2 087 | 0,693 | 0,880 |
| AP (portátil) | 1 724 | 0,941 | 0,393 |

El modelo deja pasar el 31 % de las opacidades en las placas PA, la de los pacientes
ambulatorios, y marca como sospechosas el 61 % de las AP sin opacidad. La causa está en el
análisis exploratorio (`docs/analisis_datos.md`, sección 6): la proyección predice la etiqueta
en los datos de entrenamiento.

### 10.2 La mitigación

Elegir un umbral por vista con el criterio de **igualdad de oportunidad** (el mismo recall en AP
y en PA). Los umbrales se eligen sobre **validación** y se evalúan en prueba: PA 0,1798 y AP
0,5815, para un recall de 0,88 en las dos vistas (`app/assets/metricas.json`;
Workshop de la Semana 4, tabla 3). Está implementado en el motor como parámetro opcional y
**apagado por defecto** (las variables `UMBRAL_PA` y `UMBRAL_AP`, las dos o ninguna); solo decide
la etiqueta del cribado: la razón de verosimilitud y la combinación no cambian. Encenderlo lo
decide la institución, con estas cifras delante.

### 10.3 El precio

Resultados en el conjunto de prueba (`app/assets/metricas.json`, `umbral_por_vista_en_prueba`):

| | Recall PA | Recall AP | Recall global | Espec. PA | Espec. AP | Espec. global |
| :--- | -: | -: | -: | -: | -: | -: |
| Un umbral (0,4258) | 0,693 | 0,941 | 0,882 | 0,880 | 0,393 | 0,702 |
| Dos umbrales (PA 0,18, AP 0,58) | 0,891 | 0,888 | 0,889 | 0,646 | 0,561 | **0,615** |

- El recall de las placas PA sube de 0,69 (IC 0,63 a 0,75) a 0,89 (0,84 a 0,93), y la diferencia
  de recall entre vistas pasa de 0,25 a 0,003.
- **No mejora a todos: redistribuye el error.** En prueba, 40 opacidades sin marcar menos en PA
  y 34 más en AP (de 100 a 94 en total), y 259 falsos positivos más.
- **La especificidad global baja de 0,70 a 0,62, por debajo del mínimo de 0,70 del proyecto.**
- Dentro de PA persiste una brecha por sexo (recall 0,85 frente a 0,93).

La alternativa evaluada con la misma lógica, un recall de 0,80 en las dos vistas (PA 0,27 y AP
0,69), mantiene la especificidad global en 0,73, pero deja el recall de las AP en 0,78 (bajo el
mínimo de 0,80) y no iguala las vistas (0,86 frente a 0,78) (Workshop de la Semana 4,
tabla 3). Es el compromiso de la igualdad de oportunidad: este modelo no puede dar a la vez el
mismo recall en las dos vistas, un recall de 0,88 y la especificidad mínima de 0,70. Por eso el
umbral por vista queda apagado por defecto: está evaluado y no desplegado.

## 11. Configuración final y justificación

La configuración del modelo desplegado (corrida 6, `efficientnet_b0_320px_lote24_4+20ep`).

| Parámetro | Valor | Justificación |
| :--- | :--- | :--- |
| Arquitectura | EfficientNet-B0 preentrenada en ImageNet, salida binaria | Empate de AUC con las otras dos; coste de entrenamiento unas 3,2 veces menor que DenseNet121; calibrador propio |
| Resolución | 320 × 320 | La palanca más probable en radiografía de tórax: las opacidades son sutiles |
| Entrada | PNG de 8 bits sin ventaneo, en tres canales, normalizado con las estadísticas de ImageNet | Los DICOM de RSNA son de 8 bits; la red es de ImageNet |
| Lote | 24 | Memoria a 320 px |
| Entrenamiento | 4 épocas de cabeza con el backbone congelado y hasta 20 de ajuste fino de la red completa | El AUC seguía subiendo con menos |
| Optimizador y tasas | Adam; 1e-3 en la cabeza y 2e-4 en el ajuste; recocido coseno | Valores de partida, no explorados |
| Pérdida | `BCEWithLogitsLoss` con `pos_weight` = negativos / positivos (3,44) | 22,15 % de positivos |
| Parada y selección | Paciencia 5 por fase; selección de la mejor época por recall con AUC de desempate en validación; restaura el mejor punto de control (mejor época: 5) | El falso negativo es el error caro. Bajar a 3 es una mejora medida que no se aplicó al modelo desplegado |
| Aumento de datos | Rotación de ±7°, desplazamiento del 5 %, brillo y contraste de ±0,15; sin volteo horizontal; solo en entrenamiento | La lateralidad cardiaca es información clínica |
| Población | 18 a 100 años | Es el alcance; el modelo se niega fuera de ahí |
| Partición | 70/15/15 por paciente, semilla 42 | Sin fuga de datos |
| Calibración | Isotónica ajustada en validación; razón de verosimilitud acotada a [0,0163; 77,32] | La salida cruda no es una probabilidad (sección 8) |
| Umbral de cribado | 0,4258 (especificidad de 0,70 en validación) | Prioriza el recall (sección 9) |
| Umbral por vista | Apagado; PA 0,1798 y AP 0,5815 si se enciende | Igualdad de oportunidad con precio en especificidad (sección 10) |

Los valores por defecto del código (`src/copiloto_triaje/config.py`) son los de la segunda
corrida; la arquitectura se elige al lanzar el entrenamiento.

## 12. Comparación antes y después

| | Primera corrida (19-sep) | Con la regla del umbral corregida, sin reentrenar | Modelo desplegado |
| :--- | -: | -: | -: |
| Recall en prueba | 0,766 | ≈ 0,834 (a especificidad 0,70) | **0,882** |
| Especificidad en prueba | 0,764 | 0,70 | **0,702** |
| AUC en prueba | 0,845 | 0,845 | **0,885** |
| Latencia de inferencia en CPU | 0,023 s | — | 0,022 s |

Fuentes: `docs/mejoras-2026-09-21.md` (primera corrida y estimación de la regla corregida),
`app/assets/metricas.json` y `docs/comparativa-corridas.md` (modelo desplegado) y spec de SP2,
§1 (latencia).

**Cómo leerlo.** El recall sube 0,116 en total (de 0,766 a 0,882) y la especificidad baja
0,062. De esa subida del recall, algo más de la mitad es elegir otro punto de la misma curva y
algo menos de la mitad es un modelo mejor:

- ≈ 0,068 (de 0,766 a ≈ 0,834) viene de elegir otro punto de operación de **la misma curva**: es
  la corrección de la regla del umbral, a costa de especificidad.
- ≈ 0,047 (de ≈ 0,834 a 0,882) viene de un modelo mejor, a especificidad comparable. Es una cota
  inferior de la mejora del modelo: el 0,834 es el óptimo leído sobre la curva de prueba del
  modelo viejo, mientras que el 0,882 sale de un umbral fijado en validación.
- El AUC sube 0,040: de estar por debajo del mínimo (0,85) a superar el objetivo (0,88).

Desde la primera corrida, además, **la especificidad objetivo de 0,75 dejó de ser un criterio
alcanzable a la vez que el recall** (sección 9): parte de la «mejora» del recall se paga con
especificidad, y se declara.

## 13. Lo que no se hizo y lo que haría falta

Las siguientes opciones **no se probaron**, y por eso son hipótesis y no resultados. Se ordenan
por lo que prometen frente a lo que cuestan (Semana 3, §6.3):

1. **Repetir las corridas con al menos tres semillas.** Es el prerrequisito para decir algo
   sobre arquitecturas y no solo sobre corridas, y para que el rango de ruido de la sección 7.1
   deje de ser un suelo. Coste: tres veces el presupuesto actual de GPU.
2. **Escalonar el descongelado del backbone** en vez de liberarlo entero en la época 4. Es la
   intervención que el diagnóstico señala directamente: si el sobreajuste aparece dos a tres
   épocas después de liberar todos los bloques, liberarlos por grupos debería desplazar el
   mínimo de validación y aplanar la brecha. Una corrida adicional por arquitectura.
3. **Regularización explícita**: dropout en la cabeza por encima del predeterminado y *weight
   decay*, variando un solo hiperparámetro por corrida para que el resultado sea atribuible.
4. **Barrer la resolución y la profundidad del ajuste por separado**, para aislar lo que hoy
   está confundido en un paquete (sección 5.5).
5. **Bajar la paciencia de 5 a 3** en el entrenamiento por defecto: ahorra dos épocas por
   corrida sin coste medible sobre el historial (el valor por defecto de `config.py` sigue
   en 5).
6. **Palancas del documento de mejoras** si el recall quedara corto: aumento de datos en
   inferencia, un conjunto de modelos y revisar si la etiqueta «opacidad» admite el rendimiento
   prometido.
7. **Una búsqueda sistemática** (rejilla o bayesiana) con partición estratificada por
   proyección y validación cruzada, solo con presupuesto de cómputo para repeticiones.
8. **Calibración y umbral por vista**, y recalibración con datos de un centro real: hoy está
   calibrado solo en RSNA y la calibración por vista queda fuera de alcance (spec de SP5-C1).

## 14. Cómo reproducirlo

| Qué | Cómo |
| :--- | :--- |
| La comparativa de corridas | `scripts/comparar_corridas.py` sobre los `reporte_metricas.json` de cada corrida |
| El diagnóstico de sobreajuste y las estrategias de parada | `scripts/diagnostico_curvas.py` sobre los historiales guardados; simula las políticas de parada sin reentrenar |
| El entrenamiento | `notebooks/03_modelado.ipynb` en una GPU (Kaggle o Colab) y `scripts/entrenar_local.py` en CPU, reanudable |
| El calibrador | `scripts/ajustar_calibrador.py` sobre las puntuaciones de validación |
| Las métricas finales y por vista | `app/generar_metricas.py` sobre las puntuaciones congeladas de prueba |
| El análisis completo, con código | `notebooks/04_optimizacion.ipynb` |

Los informes de cada corrida y las puntuaciones por placa no estarán en el repositorio público
(las puntuaciones por placa, `docs/validacion-semisintetica/crudas_prueba.csv`, son una tabla de
trabajo del repositorio de desarrollo que no viaja a él, por decisión del 5 de octubre de no
publicar filas por paciente): los pesos se descargarán del release del repositorio público, las
métricas están en agregados (`app/assets/metricas.json`) y las cifras de las corridas, en los
documentos que se citan arriba.

## Fuentes

- `docs/comparativa-corridas.md`, `docs/frontera-recall-especificidad.md`,
  `docs/mejoras-2026-09-21.md`, `docs/sp2-despliegue.md`.
- `docs/superpowers/specs/2026-09-16-sp1-nucleo-imagen-design.md`,
  `docs/superpowers/specs/2026-09-23-sp2-servidor-mcp-design.md`,
  `docs/superpowers/specs/2026-10-05-sp5c1-interfaz-y-umbral-por-vista-design.md`.
- `docs/validacion-semisintetica-sp5.md` (calibración de la imagen sola) y
  `app/assets/metricas.json` (métricas finales y por vista).
- `src/copiloto_triaje/config.py`, `src/copiloto_triaje/modelo/evaluacion.py`,
  `src/copiloto_triaje/modelo/entrenamiento.py`, `src/copiloto_triaje/datos/dataset.py`.
- Semana 2: Ficha de decisión técnica y análisis comparativo; Semana 3: «Hallazgos medidos» y
  diagnóstico de sobreajuste; Semana 4: Workshop de impacto social, tabla 3; Presentación del
  proyecto, Registro de cambios del 23-sep.
