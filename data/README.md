# Datos

El proyecto se entrena y se evalúa con el **RSNA Pneumonia Detection Challenge** (Kaggle, 2018).
**Este repositorio no lleva esos datos**: ni una radiografía, ni los DICOM, ni los PNG, ni los
manifiestos. `raw/` y `processed/` están vacías (solo llevan un `.gitkeep`) y `.gitignore`
deja fuera todo lo que se ponga dentro. Aquí se dice de dónde bajarlos, con qué reglas, y cómo
prepararlos con los guiones del repositorio.

## La fuente

- **Qué es.** 26 684 estudios DICOM de tórax (una radiografía por paciente, 1024 × 1024, 8 bits),
  con cajas sobre las opacidades pulmonares que pueden corresponder a neumonía. Las imágenes
  son del conjunto **NIH ChestX-ray14**; las anotaciones, de la RSNA-STR (Shih et al., abajo).
- **Etiquetas del conjunto completo** (verificadas el 16-sep-2026): 6 012 con opacidad (22,5 %),
  11 821 anormales sin opacidad (44,3 %) y 8 851 normales (33,2 %). El modelo aprende la etiqueta
  binaria «opacidad / sin opacidad».
- **Con el filtro de adultos** (18 a 100 años, el alcance declarado del proyecto) quedan 25 403
  pacientes, con un 22,15 % de positivos. Se parten por paciente en 70 / 15 / 15 con la semilla
  42 y se comprueba que ningún paciente cae en dos particiones. La partición de prueba tiene
  3 811 placas, 844 con opacidad: es la de `results/` y la de la app.
- **Un sesgo conocido.** La proyección (AP, portátil, o PA, de pie) está asociada a la etiqueta:
  es un confusor, y por eso el proyecto mide por vista y ofrece un umbral por vista (apagado por
  defecto). El análisis exploratorio está en `notebooks/01_exploracion.ipynb` y `docs/eda/`.

## Dónde se descarga y con qué reglas

| | Enlace |
| :--- | :--- |
| Página del desafío en la RSNA (descargas y condiciones) | https://www.rsna.org/rsnai/ai-image-challenge/rsna-pneumonia-detection-challenge-2018 |
| Condiciones de uso y atribución de la RSNA (PDF) | https://www.rsna.org/-/media/files/rsna/education/ai-resources-and-training/ai-image-challenge/pneumonia-detection-challenge-terms-of-use-and-attribution.pdf |
| Reglas de la competición en Kaggle | https://www.kaggle.com/competitions/rsna-pneumonia-detection-challenge/rules |
| Datos en Kaggle (hay que iniciar sesión y aceptar las reglas) | https://www.kaggle.com/competitions/rsna-pneumonia-detection-challenge/data |
| Imágenes originales del NIH | https://nihcc.app.box.com/v/ChestXray-NIHCC |

Lo que dicen, en resumen (lectura del equipo, no asesoría legal):

- **Las condiciones de la RSNA** permiten usar los datos desidentificados con fines de
  investigación y educación, y otros, comerciales o no, con dos condiciones: no intentar
  identificar ni contactar a nadie que aparezca en ellos y, si se comparten en cualquier forma,
  citar a sus autores (abajo).
- **Las reglas de Kaggle** conservan la cláusula 7.B, que prohíbe transmitir, duplicar,
  publicar o redistribuir los datos a quien no participa en la competición. La cláusula
  especial de la competición solo sustituye a la 7.A (el uso).
- Por eso el repositorio **no redistribuye los datos**: quien quiera reproducir el trabajo los
  descarga de la fuente, aceptando las reglas con su propia cuenta. Lo que sí viaja son el
  código, los agregados (`results/`, `app/assets/metricas.json`) y los guiones que los
  regeneran desde el conjunto que cada uno descargue.

**Atribución.** Imágenes: NIH Clinical Center, que las proporciona; X. Wang, Y. Peng, L. Lu,
Z. Lu, M. Bagheri y R. M. Summers, «ChestX-ray8: Hospital-Scale Chest X-Ray Database and
Benchmarks on Weakly-Supervised Classification and Localization of Common Thorax Diseases»,
CVPR 2017, DOI 10.1109/CVPR.2017.369. Anotaciones: G. Shih et al., «Augmenting the National
Institutes of Health Chest Radiograph Dataset with Expert Annotations of Possible Pneumonia»,
*Radiology: Artificial Intelligence*, 2019, DOI 10.1148/ryai.2019180041.

## Qué NO está en el repositorio, y por qué

| Qué | Por qué |
| :--- | :--- |
| Los DICOM y los PNG de RSNA | Regla 7.B de Kaggle, arriba. |
| Los manifiestos (`train.csv`, `val.csv`, `test.csv`) | Son listas por paciente de lo que se descarga; se regeneran de forma determinista con la semilla. |
| Tablas con una fila por paciente derivadas de los datos | Decisión del equipo: del conjunto solo se publican agregados. Las puntuaciones congeladas del modelo sobre la prueba (`docs/validacion-semisintetica/crudas_prueba.csv`), que usan `src/evaluate.py` y la validación semisintética, son tabla de trabajo: pueden no viajar al repositorio público, y lo que las necesita lo dice y se detiene en vez de inventarlas. |
| Los pesos del modelo | Pesan unos 16 MB y no van en git: ver `models/README.md`. |

Las cuatro radiografías de ejemplo de la app (`app/assets/ejemplos/`) **no son de RSNA ni del
NIH**: son de Wikimedia Commons, con licencia que permite redistribuirlas
(`app/assets/LICENCIAS.md`).

## Cómo bajarlos y prepararlos

Necesitas una cuenta de Kaggle con las reglas de la competición aceptadas (en la página de
«Datos»). La clave de la API de Kaggle (`kaggle.json`) va en tu carpeta de usuario, nunca en el
repositorio (`.gitignore` la deja fuera).

```
pip install -r requirements.txt kaggle

# 1. Descarga en data/raw/ (el conjunto ocupa unos 3,9 GB)
kaggle competitions download -c rsna-pneumonia-detection-challenge -p data/raw

# 2. Prepara: descomprime, convierte los DICOM a PNG, cruza con las etiquetas, filtra a
#    adultos, parte por paciente y verifica que no hay fuga entre particiones
python -m src.data_processing --zip data/raw/rsna-pneumonia-detection-challenge.zip --raiz data/processed

# 3. Dile al resto de guiones dónde están (los de entrenamiento y los de la sesión la leen)
export RSNA_RAIZ=data/processed          # PowerShell: $env:RSNA_RAIZ = "data/processed"
```

El paso 2 es `scripts/preparar_datos.py` (`src/data_processing.py` lo llama). Es idempotente
(lo que ya está hecho se salta) y `--limite 200` lo prueba sobre 200 imágenes. Si ya tienes los
DICOM descomprimidos, `--crudo <carpeta>` en vez de `--zip` los lee sin copiarlos. Deja en
`data/processed/`:

- `crudo/`: el zip descomprimido (`stage_2_train_images/` y `stage_2_train_labels.csv`).
- `png/`: una imagen PNG por paciente.
- `manifiestos/`: `train.csv`, `val.csv` y `test.csv`.
- `omitidos.json`, `sin_etiqueta.json` o `descartados_por_edad.json`, solo si hubo placas que
  no se pudieron convertir, que no tenían etiqueta o que quedaron fuera del filtro de edad.

Con eso ya se puede entrenar (`python -m src.train --help`, `notebooks/03_modelado.ipynb`). No
necesitan ningún dato descargado `python -m src.evaluate` (usa las puntuaciones congeladas) ni
la app (`app/`); las pruebas que sí los necesitan se saltan, diciéndolo, sin `RSNA_RAIZ`.
