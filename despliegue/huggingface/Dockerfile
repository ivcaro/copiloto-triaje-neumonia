# La imagen de la demostración para un Space de Hugging Face (SDK Docker, SP5-C3). Es la de
# app/Dockerfile (la misma base, las mismas versiones, las mismas variables y las mismas
# opciones de Streamlit) con tres diferencias, y solo tres:
#
#   1. Su contexto no es la raíz del repositorio sino la carpeta que arma
#      despliegue/huggingface/preparar_space.py (y que se sube al Space): ya es una lista
#      blanca exacta, así que aquí no hay fichero de exclusiones. Las rutas de los COPY son
#      las mismas que en app/Dockerfile.
#   2. El usuario sin privilegios tiene el UID 1000, que es con el que Hugging Face ejecuta
#      el contenedor de un Space (docs del Hub, «Docker Spaces», apartado «Permissions»).
#   3. Streamlit va con la protección XSRF y con CORS apagados: ver la nota de la orden.
#
# Para probarla en local, con la carpeta que arma preparar_space.py:
#
#   python despliegue/huggingface/preparar_space.py <carpeta fuera del repositorio>
#   docker build -t copiloto-space <carpeta>
#   docker run --rm -p 127.0.0.1:8501:8501 --memory=2g --memory-swap=2g copiloto-space
#
# y se abre http://127.0.0.1:8501. Misma advertencia que con la imagen de la app: el puerto
# SIEMPRE detrás de 127.0.0.1: (la página no pide contraseña) y SIEMPRE con el límite de
# memoria. En el Space, Hugging Face hace las dos cosas por su cuenta: encamina el tráfico
# al puerto del README (app_port: 8501) y acota la máquina.

# La base del servidor y de app/Dockerfile, la MISMA y por su digest (servidor/Dockerfile
# explica por qué un digest y cómo actualizarlo a propósito).
FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

# torch por el índice de ruedas CPU, como en el servidor: `pip install torch` a secas
# descarga la compilación con CUDA, 2,5 GB para una demostración que no usa GPU.
ENV PIP_INDEX_URL=https://download.pytorch.org/whl/cpu \
    PIP_EXTRA_INDEX_URL=https://pypi.org/simple \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Primero las dependencias, con su versión exacta (app/requirements.txt): pesan cientos de
# MB y casi nunca cambian, así que su capa solo se rehace cuando cambia ese fichero.
COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

# Después el paquete del proyecto, SIN sus dependencias (ya están, con su versión), y fuera
# el árbol de la construcción: lo que corre es lo instalado.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps . \
 && rm -rf /app/src /app/build /app/pyproject.toml

# Los pesos y el calibrador, DENTRO de la imagen: son 16 MB y así el contenedor es
# autocontenido y no llama a nadie para cargar el modelo.
COPY servidor/pesos_modelo_cpu.pt /modelo/pesos_modelo_cpu.pt
COPY servidor/calibrador.json /modelo/calibrador.json

# Los valores del despliegue, los MISMOS de app/Dockerfile y de servidor/docker-compose.yml
# (con la fuente de cada cifra en los comentarios de ese fichero); la app los enseña en
# «Acerca de». tests/test_preparar_space.py comprueba que son los de app/Dockerfile.
ENV UMBRAL=0.4258 \
    AUC_VALIDACION=0.8827 \
    PREVALENCIA_LOCAL=0.1466 \
    RUTA_PESOS=/modelo/pesos_modelo_cpu.pt \
    RUTA_CALIBRADOR=/modelo/calibrador.json

# La app, lo último, que es lo que más cambia.
COPY app ./app

# Sin root, con el UID 1000 que usa Hugging Face. Los ficheros se quedan de root y legibles
# por todos, a propósito y sin `--chown`: la app solo los lee (no escribe nada en disco), y
# así el proceso no puede modificar ni su código ni el modelo que sirve.
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin user
USER user

# Streamlit lee `.streamlit/config.toml` del directorio desde el que se LANZA, no del de
# app.py: se lanza desde el de la app, donde está el fichero.
WORKDIR /app/app

# El puerto de app_port en el README del Space.
EXPOSE 8501

# Las opciones son las de app/Dockerfile (allí está explicada cada una: sin estadísticas de
# uso, sin el mensaje de bienvenida que consulta la IP pública de la máquina, el límite de
# subida de 5 MB como el del servidor, sin vigilar ficheros que no cambian) MÁS DOS:
#
#   --server.enableXsrfProtection=false   Hugging Face muestra el Space dentro de un iframe
#                                de huggingface.co y la página de la app es de otro sitio
#                                (hf.space). Con la protección por defecto, subir un DICOM
#                                falla con un 403 («AxiosError: Request failed with status
#                                code 403»): Streamlit guarda su testigo XSRF en una cookie
#                                SameSite=Lax, y el navegador no la manda desde un iframe de
#                                otro sitio. Se comprobó en local, con la app en 127.0.0.1
#                                dentro de un iframe de una página de localhost: con lo de
#                                por defecto, la subida da 403; sin la protección, va.
#                                Lo que se pierde es la defensa contra peticiones de otras
#                                webs en nombre de quien tiene la página abierta, y aquí no
#                                hay qué defender con ella: la app no tiene cuentas, ni
#                                sesiones con datos, ni cookies de usuario, y lo que se sube
#                                se procesa en memoria y no se guarda. Existe una opción más
#                                estrecha en esta versión de Streamlit,
#                                `--server.xsrfCookieSameSite=none` (la protección sigue
#                                encendida), y también funcionó en la prueba; pero depende de
#                                que el navegador acepte cookies de terceros (algunos
#                                las bloquean, como Safari) y la subida volvería a fallar.
#   --server.enableCORS=false    Precaución, no hizo falta en la prueba local. Con CORS
#                                encendido, Streamlit acepta el WebSocket solo si el `Origin`
#                                coincide con el `Host` que le llega, y qué `Host` reenvía el
#                                proxy del Space no se puede comprobar en local; si no
#                                coincidiera, la página ni cargaría (y Streamlit, antes de
#                                rechazarla, preguntaría por la IP pública a un servicio de
#                                fuera). Apagado, no hay esa comprobación que pueda fallar.
#
# En la imagen de local (app/Dockerfile) NO se apagan: allí la página no va en un iframe
# de otro sitio.
CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", \
     "--server.maxUploadSize=5", "--browser.gatherUsageStats=false", \
     "--logger.hideWelcomeMessage=true", "--server.fileWatcherType=none", \
     "--server.enableXsrfProtection=false", "--server.enableCORS=false"]
