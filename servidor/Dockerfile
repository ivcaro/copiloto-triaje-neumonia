# Por digest y no por `python:3.12-slim`: la etiqueta se mueve con cada parche de
# Debian, asi que dentro de un mes construiria otra imagen distinta de la que se
# midio. El hito exige que la latencia certificada corresponda a algo
# reconstruible. Para actualizar a proposito:
#   docker pull python:3.12-slim
#   docker inspect python:3.12-slim --format '{{index .RepoDigests 0}}'
# y se vuelve a medir la latencia, porque ya no es la misma imagen.
FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

# torch por el indice de ruedas CPU: `pip install torch` a secas descarga la
# compilacion con CUDA, 2,5 GB para un servidor que no tiene GPU.
ENV PIP_INDEX_URL=https://download.pytorch.org/whl/cpu \
    PIP_EXTRA_INDEX_URL=https://pypi.org/simple \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
# Las cuatro con version exacta. `uvicorn>=0.34` y un `python-multipart` sin pin
# eran una bomba de relojeria: `python-multipart` es quien parsea el
# `multipart/form-data` de /inferir, y una version nueva con otro
# comportamiento romperia esa puerta sin que nada explicase por que la imagen ya
# no se parece a la que se midio. Estas son las que hay en la imagen medida.
RUN pip install --no-cache-dir . \
 && pip install --no-cache-dir "mcp==2.2.0" "fastapi==0.141.1" \
      "uvicorn[standard]==0.53.0" "python-multipart==0.0.32"

# Los pesos y el calibrador van DENTRO de la imagen: son 16 MB y asi el
# contenedor es autocontenido, que es lo que hace reproducible la prueba
# cruzada de despliegue que exige el hito H4.
COPY servidor/pesos_modelo_cpu.pt /modelo/pesos_modelo_cpu.pt
COPY servidor/calibrador.json /modelo/calibrador.json
COPY servidor/arrancar.py ./arrancar.py

EXPOSE 8000
CMD ["python", "arrancar.py"]
