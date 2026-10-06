# La imagen de la interfaz de demostración (SP5-C1, spec §8). Su contexto es la RAÍZ
# del repositorio, y los pesos tienen que estar en servidor/pesos_modelo_cpu.pt (no
# viajan en git: README, «Interfaz de usuario»):
#
#   docker build -t copiloto-app -f app/Dockerfile .
#   docker run --rm -p 127.0.0.1:8501:8501 --memory=2g --memory-swap=2g copiloto-app
#
# y se abre http://127.0.0.1:8501. La construcción necesita BuildKit (por defecto desde
# Docker 23): el fichero de exclusiones de este Dockerfile, app/Dockerfile.dockerignore,
# solo lo lee BuildKit, y con el constructor antiguo viajaría el repositorio entero.
#
# El `-p` lleva SIEMPRE 127.0.0.1: sin él, Docker publica el puerto en todas las
# interfaces de la máquina, y la app no pide ninguna contraseña. Y el límite de memoria,
# también SIEMPRE: es la red de debajo. La app rechaza por la cabecera, antes de descodificar
# un solo píxel, lo que declara más de 5 000 píxeles de lado, varios cuadros o más de 8
# bits, y no abre un DICOM comprimido entero; pero el motor y el servidor siguen sin esa
# guarda (con el lector del motor, un DICOM de cientos de bytes que declara 60 000 x 60 000
# hace reservar 3,4 GiB, y con este límite lo que muere es el contenedor y no la máquina).
# `--memory-swap` igual a `--memory`: sin él, Docker deja usar otro tanto de swap y el
# límite deja de serlo. La app usa menos de 500 MiB (docker stats) tras los cuatro
# ejemplos y el mapa de calor: 2 GB, lo mismo que el servidor, es margen de sobra.

# La base del servidor, la MISMA y por su digest (servidor/Dockerfile explica por qué
# un digest y cómo actualizarlo a propósito). La app es la puerta de evaluación del
# mismo motor: con la misma base, el mismo índice de ruedas y las mismas versiones,
# el núcleo que corre aquí es el del servidor, no uno parecido.
FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

# torch por el índice de ruedas CPU, como en el servidor: `pip install torch` a secas
# descarga la compilación con CUDA, 2,5 GB para una demostración que no usa GPU.
ENV PIP_INDEX_URL=https://download.pytorch.org/whl/cpu \
    PIP_EXTRA_INDEX_URL=https://pypi.org/simple \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Primero las dependencias, con su versión exacta (app/requirements.txt): pesan cientos
# de MB y casi nunca cambian, así que su capa solo se rehace cuando cambia ese fichero y
# no cada vez que se toca el código. Es la receta que su cabecera documenta.
COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

# Después el paquete del proyecto, SIN sus dependencias: ya están, con su versión. Un
# `pip install .` a secas las resolvería otra vez y podría traer otra. Y, instalado, el
# árbol de la construcción sobra: fuera. No encoge la imagen (son 0,7 MB, y la capa del
# COPY los guarda); es para que dentro no haya un `src/` que alguien tome por el código
# que corre, que es el instalado.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps . \
 && rm -rf /app/src /app/build /app/pyproject.toml

# Los pesos y el calibrador van DENTRO de la imagen, como en la del servidor: son 16 MB
# y así el contenedor es autocontenido y no llama a nadie para cargar el modelo.
COPY servidor/pesos_modelo_cpu.pt /modelo/pesos_modelo_cpu.pt
COPY servidor/calibrador.json /modelo/calibrador.json

# Los valores del despliegue, los MISMOS de servidor/docker-compose.yml (con la fuente de
# cada cifra, en los comentarios de ese fichero), y la app los enseña en «Acerca de». Si
# el compose cambia, cambian aquí: tests/test_app_docker.py lo comprueba. No se copia de
# él OMP_NUM_THREADS: acota la CPU de un VPS compartido, y esto corre en la máquina de
# quien evalúa.
ENV UMBRAL=0.4258 \
    AUC_VALIDACION=0.8827 \
    PREVALENCIA_LOCAL=0.1466 \
    RUTA_PESOS=/modelo/pesos_modelo_cpu.pt \
    RUTA_CALIBRADOR=/modelo/calibrador.json

# La app, lo último, que es lo que más cambia. `COPY app` copia solo lo que
# app/Dockerfile.dockerignore readmite, fichero a fichero: lo que la app lee.
COPY app ./app

# Sin root: la imagen recibe ficheros de fuera y los lee (DICOM), y un fallo de ese
# lector no tiene por qué dar una ejecución con todos los permisos. La app no escribe
# nada en disco.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin copiloto
USER copiloto

# Streamlit lee `.streamlit/config.toml` del directorio desde el que se LANZA, no del
# de app.py: se lanza desde el de la app, donde está el fichero (el límite de subida,
# sin trazas en el navegador, sin barra de desarrollo).
WORKDIR /app/app

EXPOSE 8501
# Las opciones de la orden no repiten el fichero de configuración: son las que la
# imagen necesita por sí misma, venga el fichero o no.
#   --logger.hideWelcomeMessage=true   Una imagen que recibe radiografías no llama a
#                                nadie al arrancar. En modo headless, Streamlit escribe
#                                un mensaje de bienvenida con tres direcciones y, para
#                                la tercera («External URL»), le pregunta a un servicio
#                                de fuera (checkip.amazonaws.com) cuál es la IP pública
#                                de la máquina. Fijar `--server.address=0.0.0.0` NO lo
#                                evita en esta versión (Streamlit trata ese comodín como
#                                una dirección sin fijar): se comprobó, y la «External
#                                URL» salía en los registros. Ocultar el mensaje corta
#                                antes de preguntar. tests/test_app_docker.py vigila que
#                                esa línea no salga, con y sin Internet. (La comprobación
#                                de orígenes de las peticiones también puede preguntar
#                                por la IP pública, pero solo ante un `Origin` que no sea
#                                localhost ni 127.0.0.1: lo mandaría, a propósito, una
#                                página de fuera abierta en el navegador de quien evalúa,
#                                y Streamlit pregunta antes de rechazarla con un 403. No
#                                es del arranque.)
#   --browser.gatherUsageStats=false   Streamlit manda estadísticas de uso por defecto.
#   --server.address=0.0.0.0     escucha en todas las interfaces DEL CONTENEDOR, que es
#                                lo que hace falta para que Docker publique el puerto.
#   --server.maxUploadSize=5     5 MB, el mismo límite que el servidor.
#   --server.headless=true       no hay navegador dentro del contenedor.
#   --server.fileWatcherType=none   en la imagen no hay nada que vigilar: los ficheros no
#                                cambian, y Streamlit, que por defecto los vigila y
#                                recarga los módulos que cambian, gastaría hilos de
#                                sondeo (en un Docker sobre WSL, además, avisa de que
#                                sondea los ficheros).
CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", \
     "--server.maxUploadSize=5", "--browser.gatherUsageStats=false", \
     "--logger.hideWelcomeMessage=true", "--server.fileWatcherType=none"]
