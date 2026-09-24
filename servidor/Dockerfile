FROM python:3.12-slim

# torch por el indice de ruedas CPU: `pip install torch` a secas descarga la
# compilacion con CUDA, 2,5 GB para un servidor que no tiene GPU.
ENV PIP_INDEX_URL=https://download.pytorch.org/whl/cpu \
    PIP_EXTRA_INDEX_URL=https://pypi.org/simple \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . \
 && pip install --no-cache-dir "mcp==2.2.0" "fastapi==0.141.1" \
      "uvicorn[standard]>=0.34" python-multipart

# Los pesos y el calibrador van DENTRO de la imagen: son 16 MB y asi el
# contenedor es autocontenido, que es lo que hace reproducible la prueba
# cruzada de despliegue que exige el hito H4.
COPY servidor/pesos_modelo_cpu.pt /modelo/pesos_modelo_cpu.pt
COPY servidor/calibrador.json /modelo/calibrador.json
COPY servidor/arrancar.py ./arrancar.py

EXPOSE 8000
CMD ["python", "arrancar.py"]
