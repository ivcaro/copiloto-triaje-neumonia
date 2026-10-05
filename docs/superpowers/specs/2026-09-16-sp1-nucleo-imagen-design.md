# SP1 — Núcleo de imagen: diseño

**Proyecto:** Copiloto de triaje para neumonía en adultos (Telegram + MCP + LLM)
**Sub-proyecto:** SP1, primero de cinco. Corresponde al hito **H3 (25 de septiembre de 2026)**.
**Equipo:** dos integrantes.
**Fecha:** 16 de septiembre de 2026.
**Estado:** aprobado en chat el 16-sep-2026; pendiente de revisión escrita.

---

## 1. Contexto

El proyecto completo se descompone en cinco sub-proyectos secuenciales: SP1 núcleo de imagen, SP2 servicio de inferencia (MCP en Docker), SP3 bot de Telegram y orquestación en n8n, SP4 módulo de síntomas y combinación bayesiana, SP5 validación clínica y cierre. Cada uno tiene su propio ciclo de diseño, plan e implementación.

Este documento cubre **solo SP1**: convertir el dataset crudo de RSNA en un modelo de clasificación entrenado, con métricas medidas de forma honesta y reproducible.

**Restricción de entorno determinante:** la máquina de desarrollo no tiene GPU (PyTorch 2.13.0+cpu, sin CUDA). El entrenamiento real debe ejecutarse en una GPU externa (Google Colab o los notebooks de Kaggle, ambos disponibles para la cuenta del equipo). De ahí el enfoque aprobado: **el pipeline es un paquete de Python con pruebas, no un notebook**; se desarrolla y verifica localmente con un entrenamiento de humo en CPU, y el mismo código ejecuta el entrenamiento completo en GPU.

## 2. Objetivo y criterios de aceptación

Entrenar y evaluar una CNN de clasificación binaria sobre radiografías de tórax de adultos, con partición a nivel de paciente y sin fuga de datos.

| Criterio | Mínimo | Objetivo |
| :--- | :---: | :---: |
| Recall (sensibilidad) en el conjunto de prueba | 80% | 85% |
| Especificidad en el conjunto de prueba | 70% | 75% |
| AUC-ROC | 0,85 | 0,88 |
| Latencia de inferencia en CPU (una imagen) | < 4 s | < 1 s |

Criterios no numéricos, igualmente obligatorios:

- Verificación automatizada de ausencia de fuga de datos entre particiones, ejecutada como prueba.
- Reproducibilidad exacta: misma semilla produce las mismas particiones y los mismos resultados.
- El pipeline completo se ejecuta de punta a punta desde una sola orden.

## 3. Alcance

**Incluido:** descompresión y conversión de DICOM a PNG, extracción de metadatos, partición por paciente con verificación anti-fuga, entrenamiento con transfer learning, evaluación con selección de umbral, exportación de pesos y reporte de métricas.

**Excluido de SP1 (aplicando YAGNI):** mapas de calor Grad-CAM (declarados opcionales en el documento de presentación), validación externa con PadChest (depende de un trámite de acceso), búsqueda sistemática de hiperparámetros (corresponde al Sprint 3), detección de cajas delimitadoras (solo clasificación), y el servidor MCP (es SP2).

## 4. Datos: hechos verificados

Contenido real del archivo descargado, inspeccionado el 16-sep-2026 (no son cifras estimadas):

- Origen: `rsna-pneumonia-detection-challenge.zip`, 3,66 GB, en `<carpeta-de-descarga>\` (fuera de OneDrive y fuera del repositorio).
- `stage_2_train_images/`: **26 684 archivos DICOM**, 3,31 GB.
- `stage_2_test_images/`: 3 000 archivos DICOM, 0,37 GB. **No se usan**: la competencia no publica sus etiquetas.
- `stage_2_train_labels.csv`: 30 227 filas con columnas `patientId, x, y, width, height, Target`. Hay más filas que imágenes porque un paciente positivo puede tener varias cajas.
- `stage_2_detailed_class_info.csv`: 30 227 filas con `patientId, class`.

**Distribución real por paciente** (26 684 pacientes únicos, **una imagen por paciente**):

| Clase detallada | Pacientes | Proporción | Etiqueta binaria |
| :--- | ---: | ---: | :---: |
| Lung Opacity | 6 012 | 22,5% | **positivo (1)** |
| No Lung Opacity / Not Normal | 11 821 | 44,3% | negativo (0) |
| Normal | 8 851 | 33,2% | negativo (0) |

**Corrección a documentación previa.** El documento de presentación del proyecto afirma que el dataset trae "15 000 casos con opacidad y 15 000 negativos". Es incorrecto: la proporción real de positivos es **22,5%, no 50%**. La cifra de 26 684 pacientes sí es correcta. Esta corrección debe aplicarse al documento antes de su entrega del 20 de septiembre, y tiene consecuencias de diseño que se recogen en la sección 6.

## 5. Arquitectura del paquete

```
copiloto-triaje/
├── src/copiloto_triaje/
│   ├── config.py              Configuración y semilla en un único lugar
│   ├── datos/
│   │   ├── dicom.py           DICOM → PNG + extracción de metadatos
│   │   ├── particion.py       Partición por paciente + verificación anti-fuga
│   │   └── dataset.py         Dataset de PyTorch + transformaciones
│   └── modelo/
│       ├── arquitectura.py    Transfer learning, construcción del modelo
│       ├── entrenamiento.py   Bucle, early stopping, checkpoints
│       └── evaluacion.py      Métricas y selección de umbral
├── tests/                     Pruebas con pytest
├── scripts/preparar_datos.py  Interfaz de línea de comandos local
├── notebooks/entrenar_gpu.ipynb   Notebook delgado para Colab o Kaggle
├── docs/superpowers/specs/    Este documento
└── pyproject.toml
```

Cada módulo tiene una responsabilidad única y se puede probar por separado. El notebook no contiene lógica: instala el paquete y llama a sus funciones, de modo que lo que se verifica localmente es exactamente lo que entrena en GPU.

## 6. Decisiones técnicas

**Definición de la etiqueta.** Positivo = la placa tiene al menos una caja de opacidad (`Target = 1`). Los negativos incluyen tanto "Normal" como "anormal sin opacidad", que es el caso clínicamente difícil y realista: distinguir opacidad de otras anomalías, no de placas perfectas.

**Manejo del desbalance (22,5% positivos).** Es la consecuencia directa del hallazgo de la sección 4. Se aplican tres medidas: partición estratificada para preservar la proporción en los tres conjuntos, ponderación de clases en la función de pérdida para que el error sobre positivos pese más, y selección del umbral de decisión por curva ROC en lugar de dejarlo en 0,5. Sin estas medidas, un modelo que prediga siempre "negativo" alcanzaría 77,5% de accuracy con Recall cero — exactamente el fracaso que la métrica primaria debe impedir.

**Partición por paciente.** Se agrupa por `patientId` y se reparte 70/15/15 de forma estratificada, con semilla fija. En este dataset hay una imagen por paciente, de modo que la partición por paciente coincide con la partición por imagen; aun así la lógica se implementa y se verifica a nivel de paciente, porque es la correcta y protege frente a cualquier cambio futuro de dataset. La verificación es una prueba que falla si un mismo `patientId` aparece en dos conjuntos.

**Solo `stage_2_train`.** El conjunto de prueba oficial no tiene etiquetas públicas. Nuestro conjunto de prueba es una partición propia, declarada así en el documento de presentación.

**Arquitectura del modelo: MobileNetV3-Large.** Se elige por encima de ResNet50 por una razón de sistema, no de exactitud: SP2 exige servir la inferencia en la CPU del servidor privado con latencia menor a 4 segundos. Entrenar primero el modelo que se va a poder servir evita rehacer el trabajo. ResNet50 queda como comparación opcional si el calendario lo permite.

**Entrenamiento en dos fases.** Primero se congela el extractor de características preentrenado en ImageNet y se entrena solo la cabeza de clasificación; después se descongelan las últimas capas con una tasa de aprendizaje menor. Es el procedimiento estándar de transfer learning y evita destruir los pesos preentrenados en las primeras iteraciones.

**Criterio de parada y selección de umbral.** El early stopping observa el **Recall en validación**, no la exactitud ni la pérdida.

El umbral de decisión se elige sobre la curva ROC del **conjunto de validación**, nunca del de prueba, siguiendo una regla explícita y sin margen de interpretación:

1. Entre los umbrales que dan especificidad mayor o igual al **75%** (objetivo), se toma el de mayor Recall.
2. Si ninguno de esos alcanza un Recall del 85%, se repite la búsqueda relajando la restricción al mínimo aceptable de especificidad, el **70%**.
3. Si aun así el Recall no llega al 85%, se conserva el umbral del paso 1 y se reporta el resultado tal cual, sin relajar más: preferimos un número honesto a un umbral forzado.

El umbral elegido se congela y se registra **antes** de tocar el conjunto de prueba, que se evalúa **una sola vez**, al final. Cualquier reevaluación posterior sobre ese mismo conjunto invalidaría las métricas y debe declararse en el informe.

**Preprocesamiento.** Los DICOM se convierten a PNG de 8 bits; las imágenes se redimensionan a 224×224 y se normalizan con las estadísticas de ImageNet. El aumento de datos (rotaciones leves de ±7°, desplazamientos y ajuste de brillo y contraste) se aplica **solo al conjunto de entrenamiento**. No se usa volteo horizontal, porque la lateralidad cardiaca es información clínica real y voltearla produciría imágenes anatómicamente imposibles.

## 7. Flujo de datos

1. **Descompresión** del zip a un directorio de trabajo fuera del repositorio. Idempotente.
2. **Conversión**: cada DICOM se lee con pydicom; se extraen la matriz de píxeles y los metadatos útiles (`PatientID`, edad, sexo, posición de la placa) y se escribe un PNG. Los metadatos se acumulan en un CSV.
3. **Partición**: se cruzan metadatos y etiquetas, se agrupa por paciente y se generan tres manifiestos CSV (`train.csv`, `val.csv`, `test.csv`) con la semilla registrada en cada uno.
4. **Entrenamiento**: el Dataset lee un manifiesto, nunca el directorio directamente. Esto hace que la partición sea un artefacto explícito y auditable.
5. **Evaluación**: métricas sobre el conjunto de prueba, matriz de confusión, curva ROC y umbral elegido, exportadas a un reporte en JSON y Markdown.

## 8. Manejo de errores

Cada etapa es idempotente y reanudable: si el zip ya está descargado no se vuelve a descargar; si los PNG ya existen no se reconvierten. Un DICOM corrupto o ilegible se registra en un log de omitidos y se salta sin abortar el proceso; el reporte final indica cuántos archivos se omitieron y por qué, de modo que una pérdida silenciosa de datos sea imposible. El entrenamiento guarda un checkpoint por época, con el estado del optimizador, para poder reanudarse tras una caída de sesión en Colab. Toda configuración inválida (rutas inexistentes, proporciones que no suman 1, semilla ausente) falla de forma inmediata y explícita al inicio, no a mitad del entrenamiento.

## 9. Estrategia de pruebas

Las pruebas se escriben antes que la implementación, siguiendo desarrollo guiado por pruebas.

| Prueba | Qué garantiza |
| :--- | :--- |
| `test_particion.py` | **La más importante.** Con pacientes sintéticos que tienen varias imágenes, verifica que ningún `patientId` aparece en dos conjuntos, que las proporciones se respetan, que la estratificación conserva la tasa de positivos y que la misma semilla reproduce la misma partición. |
| `test_dicom.py` | La conversión produce las dimensiones y el rango de píxeles esperados, y extrae correctamente los metadatos. Un DICOM corrupto se omite sin lanzar excepción. |
| `test_dataset.py` | Las formas de los tensores son correctas, el aumento de datos se aplica solo en entrenamiento, y las etiquetas corresponden a sus imágenes. |
| `test_evaluacion.py` | Con predicciones conocidas de antemano, Recall, especificidad y AUC se calculan correctamente, incluidos los casos límite (todo positivo, todo negativo). |
| `test_humo.py` | Entrenamiento completo de dos épocas con 50 imágenes sintéticas en CPU, en menos de un minuto: demuestra que el pipeline corre de punta a punta sin GPU. |

## 10. Entorno de ejecución

**Local (esta máquina):** desarrollo, pruebas, conversión de datos y entrenamiento de humo. Sin GPU.

**GPU externa (Colab o notebooks de Kaggle):** entrenamiento completo. El notebook instala el paquete desde el repositorio, monta o descarga los datos, y llama a la función de entrenamiento con la configuración de producción. Las dependencias se fijan con versiones exactas para que el entorno remoto reproduzca el local.

## 11. Riesgos

| Riesgo | Mitigación |
| :--- | :--- |
| Las métricas no alcanzan el mínimo comprometido | Ponderación de clases, ajuste del umbral por ROC y, si hace falta, comparación con ResNet50. Si aun así no se alcanza, se documenta con honestidad en el informe final, como acordó la tutora. |
| Caída de sesión en Colab durante el entrenamiento | Checkpoint por época y reanudación automática desde el último. |
| Conversión de 26 684 DICOM lenta en CPU | Procesamiento por lotes y paralelización por procesos; es una operación de una sola vez. |
| Divergencia entre el entorno local y el de GPU | Un único paquete con dependencias fijadas; el notebook no contiene lógica. |

## 12. Entregables de SP1

- Paquete `copiloto_triaje` con sus pruebas en verde.
- Manifiestos de partición con semilla registrada.
- Pesos del modelo entrenado, exportados.
- Reporte de métricas en JSON y Markdown, con matriz de confusión, curva ROC y umbral elegido.
- Notebook de entrenamiento para GPU.
- README con las instrucciones para reproducir el resultado desde cero.
