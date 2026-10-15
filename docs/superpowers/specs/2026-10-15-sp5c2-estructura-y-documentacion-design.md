# SP5-C2 — La estructura y la documentación que pide el curso (modo rápido)

**Estado:** aprobado por el equipo en conversación el 15-oct-2026 («sí, pero en
modo rápido»). Parte de `main` = `3981391`. Rama `sp5c2-curso`.

## Qué y por qué

La entrega final (`Entrega Final/PROYECTO_FINAL_descripcion_2026.pdf`) pide un
repositorio público con una estructura de carpetas fija, un README de 14
secciones y seis documentos en `docs/`. Pesan: estructura 10 %, documentación
15 %, calidad del código 10 %, optimización 10 %, ética 10 % (−20 % si es
superficial), evaluación 10 %. Nuestro código tiene otra estructura, ya
probada y desplegada.

## Decisiones (del equipo, 15-oct)

- **D1. Capa de rutas del curso:** el código real no se mueve; las rutas del
  curso son puntos de entrada finos, documentados y probados que delegan en
  `src/copiloto_triaje/`.
- **D2. Licencia MIT** para el código. Los datos de RSNA no van en el repositorio.
- **D3. Los pesos, como descarga del release** del repositorio público (C3);
  `models/README.md` dice cómo bajarlos y su SHA-256. Antes de publicarlos se
  comprueban las reglas de la competición (C3).
- **D4. `data/` solo con referencias:** ningún dato de RSNA, ni imágenes ni filas
  por paciente (decisión del 5-oct).
- **D5. Los nombres del equipo**, solo en `README.md`, `LICENSE` y
  `docs/planificacion.md`; el verificador de anonimato los admite ahí y en
  ningún otro fichero.

## Lo que se construye

1. **Raíz:** `requirements.txt` (versiones fijas: las de `pyproject.toml` y
   `app/requirements.txt`, con el índice de ruedas CPU), `LICENSE` (MIT),
   `.gitignore` (los datos y los pesos).
2. **`src/`:** `__init__.py`, `data_processing.py`, `model.py`, `train.py`,
   `evaluate.py`, `utils.py`. Cada uno, un módulo fino que reexporta o llama a
   `copiloto_triaje` (sin duplicar lógica), con un docstring que dice dónde vive
   la implementación. `evaluate.py` calcula, de las puntuaciones congeladas de
   prueba, las métricas globales y por subgrupo y escribe `results/`.
3. **`notebooks/`:** `01_exploracion.ipynb` (el `eda_rsna.ipynb` de hoy, con
   `git mv`), `02_preprocesamiento.ipynb` (nuevo), `03_modelado.ipynb` (el
   `entrenar_kaggle.ipynb`, con `git mv`; `entrenar_gpu.ipynb` se queda como
   variante documentada), `04_optimizacion.ipynb` (nuevo: corridas, análisis de
   sensibilidad de hiperparámetros, calibración y umbral), `05_evaluacion.ipynb`
   (nuevo: prueba, subgrupos, umbral por vista, validación semisintética y la
   sesión con el médico). Los nuevos, ejecutados en la imagen Linux.
4. **`data/README.md`** (fuente, reglas, descarga y preparación con los guiones
   del repositorio), `data/raw/` y `data/processed/` vacíos con `.gitkeep`.
5. **`models/README.md`:** el modelo (EfficientNet-B0 a 320 px, corrida 6), su
   SHA-256, de dónde bajarlo, por qué es `.pt` y no `.pkl`, el calibrador.
6. **`results/figures/`, `results/metrics/`, `results/reports/`:** agregados que
   genera `src/evaluate.py` (métricas en JSON, curva ROC, calibración y
   subgrupos) y un `README.md` en `reports/` que enlaza el acta de H7 y el
   informe de la validación semisintética.
7. **`tests/test_data_processing.py`, `tests/test_model.py`** (la capa del curso)
   y **`tests/test_estructura_curso.py`** (que existe todo lo que pide el curso).
8. **`docs/`:** `planificacion.md`, `analisis_datos.md`, `arquitectura.md`,
   `optimizacion.md`, `consideraciones_eticas.md`, `manual_usuario.md`, y las
   fichas `ficha_modelo.md` y `ficha_datos.md` (compromiso M5 del workshop S4).
   Cada uno sale de su fuente (Semanas 1-4, los specs, la guía de despliegue, el
   acta) y cada cifra sale de una fuente citada, nunca tecleada a mano.
9. **`README.md`**, reescrito con las 14 secciones del curso; lo técnico de hoy
   pasa a `docs/desarrollo.md`.
10. **Anonimato:** cada binario nuevo, mirado y declarado con su SHA-256; la
    excepción D5 en el verificador, con su prueba.

## Cómo se comprueba

La suite (Linux y Windows), el verificador en 0, los notebooks ejecutados de
principio a fin, `tests/test_estructura_curso.py`, y una revisión final de la
rama.

## Fuera de alcance (C3 y C4)

El inventario público/local, el historial limpio con filter-repo, los tags, el
release con los pesos, el repositorio público, la app publicada y los vídeos.
