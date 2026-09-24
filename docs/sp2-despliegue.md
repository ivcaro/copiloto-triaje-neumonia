# Despliegue del servidor MCP (SP2)

Guía para levantar el copiloto de triaje desde cero **sin conocer el código**.
Al terminar tendrás un contenedor `copiloto-mcp` sirviendo el modelo por dos
puertas, unido a la misma red de Docker que n8n, y sabrás comprobar que
funciona.

Medido y verificado el 23-sep-2026 con Docker 29.6.1 y Compose v5.2.0.

## 1. Qué es esto

Un solo contenedor con un solo proceso que carga el modelo de neumonía una vez
al arrancar y lo expone por **dos puertas sobre el mismo núcleo**:

| Puerta | Ruta | Para qué |
| :--- | :--- | :--- |
| MCP (la comprometida en H4) | `POST /mcp` | la herramienta `clasificar_radiografia`, que es lo que consume n8n |
| REST (contingencia prevista en el cronograma) | `POST /inferir` | subida `multipart/form-data`, por si n8n y MCP no se entienden |
| Salud | `GET /salud` | comprobar que el modelo está cargado |

Las dos puertas llaman a la misma función, así que no pueden divergir ni en el
resultado ni en el mensaje de error.

**El servicio no publica ningún puerto al host.** Es deliberado: la
radiografía no debe salir de la máquina. Solo se alcanza desde dentro de la red
de Docker, por el nombre de servicio `copiloto-mcp`.

## 2. Requisitos previos

- Docker con Compose v2 o superior (probado en 29.6.1 / v5.2.0).
- El repositorio `copiloto-triaje`, rama `sp2-servidor-mcp`.
- Unos 4 GB libres de disco (la imagen ocupa ~1,6 GB desempaquetada y la
  construcción descarga ~200 MB de ruedas).
- Salida a internet durante la construcción (PyPI y `download.pytorch.org`).
- Para medir latencia o probar de verdad: **al menos un fichero DICOM real**
  del dataset RSNA, de un paciente **de 18 a 100 años** (ver el paso 6).

### Los pesos del modelo NO están en el repositorio

Esto es lo primero que se atasca. `servidor/pesos_modelo_cpu.pt` son 16 MB
binarios y está en `.gitignore` a propósito: al clonar, **no estará**. El
`servidor/calibrador.json` de al lado sí se versiona, ese ya lo tienes.

Cópialo a mano antes de construir, desde la corrida que produjo el modelo:

```bash
cp "C:/Users/[retirado]/datasets/rsna-pneumonia/trabajo/corridas/efficientnet_b0_320px_lote24_4+20ep/checkpoints/pesos_modelo_cpu.pt" \
   servidor/pesos_modelo_cpu.pt
```

Comprueba que es el fichero correcto antes de seguir:

```bash
sha256sum servidor/pesos_modelo_cpu.pt
# bb985e1f792e1cfee150ec57bdc6d706f7484499fa999da3406a5798260e8d47
```

Si el hash no coincide, para: estarías midiendo y certificando otro modelo.
Si el fichero no está, la construcción falla en el `COPY` con
`"/servidor/pesos_modelo_cpu.pt": not found`.

## 3. La red de Docker: el único punto que cambia entre el VPS y tu máquina

n8n y el copiloto tienen que estar en la **misma red de Docker** para que n8n
pueda llamar a `http://copiloto-mcp:8000/mcp` por nombre. El compose **no crea
esa red**: la declara como `external`, es decir, "ya existe, solo me uno".

```yaml
networks:
  [retirado]_network:
    external: true
    name: ${RED_N8N:-[retirado]_[retirado]_network}
```

El nombre por defecto, `[retirado]_[retirado]_network`, es el de la red que ya declara
la infraestructura del cliente, donde corre n8n.

### Caso A: en el VPS, donde n8n ya corre

**No se crea ni se toca nada.** La red ya existe y la posee la infraestructura
del cliente. Solo confirma que está y que su nombre es el que espera el
compose:

```bash
docker network ls
```

Busca `[retirado]_[retirado]_network` en la lista. Si en tu instalación se llama de
otra forma, **no edites el compose**: pásale el nombre por entorno, que para
eso está la variable.

```bash
RED_N8N=el_nombre_real docker compose up -d
```

Para averiguar con certeza en qué red está n8n, mírala desde su propio
contenedor en vez de adivinar por el nombre:

```bash
docker inspect <nombre-del-contenedor-de-n8n> --format '{{json .NetworkSettings.Networks}}'
```

### Caso B: en local, para probar el despliegue desde cero

Aquí n8n no corre (vive en el VPS), así que la red externa no existe y el
compose fallaría con `network [retirado]_[retirado]_network declared as external, but
could not be found`. Créate una suelta con ese nombre:

```bash
docker network create [retirado]_[retirado]_network
```

Y cuando acabes, si quieres dejar limpio (primero baja el contenedor):

```bash
docker compose down
docker network rm [retirado]_[retirado]_network
```

## 4. Construir la imagen

Todos los comandos de aquí en adelante se ejecutan **desde el directorio
`servidor/`**:

```bash
cd servidor
docker compose build
```

Tarda unos 2 minutos la primera vez; casi todo es la descarga de torch
(196,3 MB). La imagen resultante es `copiloto-mcp:0.1.0`.

```bash
docker images copiloto-mcp
```

Tamaño esperado, medido el 23-sep-2026:

| Medida | Valor |
| :--- | ---: |
| Contenido (lo que se empuja o se descarga, comprimido) | **442 MB** |
| Suma de capas sin comprimir | **~1,56 GB** |

**No te alarmes por el 1,56 GB: la rueda CPU de torch sí se aplicó.** Se
comprueba así, y `False` es lo correcto:

```bash
docker run --rm --entrypoint python copiloto-mcp:0.1.0 \
  -c "import torch; print(torch.__version__, torch.cuda.is_available())"
# 2.14.0+cpu False
```

El volumen es inevitable con este árbol de dependencias: `torch` ocupa 769 MB
desempaquetado incluso en su versión CPU, y a él se suman scipy (109 MB),
sympy (74 MB), pandas (72 MB), scikit-learn (49 MB) y numpy (43 MB). Los
cuatro últimos no son decorado: el servicio los importa en el camino de
ejecución (`calibracion.py` usa `sklearn.isotonic`, y `dataset.py` y
`preparacion.py` usan pandas), así que no se pueden quitar sin refactorizar.
Si alguna vez vieras `torch` **sin** el sufijo `+cpu`, ahí sí habría un
problema: se habría colado la compilación con CUDA, que son 2,5 GB.

## 5. Levantar y comprobar la salud

```bash
docker compose up -d
docker compose ps
```

El estado debe llegar a `healthy`. Tarda unos 10 segundos: el arranque carga
los pesos del modelo antes de aceptar la primera petición. El compose le da
40 s de gracia (`start_period`) antes de contar fallos, así que si lo miras
demasiado pronto verás `starting`, que es normal.

```
NAME           IMAGE                COMMAND                SERVICE        STATUS
copiloto-mcp   copiloto-mcp:0.1.0   "python arrancar.py"   copiloto-mcp   Up (healthy)
```

Ahora pregúntale a la puerta de salud:

```bash
docker compose exec copiloto-mcp python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/salud')))"
```

Respuesta esperada:

```
{'estado': 'listo', 'modelo': 'efficientnet_b0_320px', 'umbral': 0.4258, 'calibrador': 'efficientnet_b0_320px_lote24_4+20ep'}
```

### Comprobar que se alcanza por nombre de servicio

Esto es lo que hará n8n, y conviene verificarlo sin n8n de por medio. Levanta
un contenedor de usar y tirar en la misma red y pídele que resuelva el nombre:

```bash
docker run --rm --network [retirado]_[retirado]_network python:3.12-slim python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://copiloto-mcp:8000/salud')))"
```

Si esto responde, el cableado de red está bien. Si da `Name or service not
known`, los dos contenedores no están en la misma red.

## 6. Medir la latencia dentro del contenedor

Se mide **dentro** del contenedor porque es ahí donde va a correr: el límite de
memoria, la CPU disponible y los hilos de torch no son los del portátil donde
se programó.

Necesitas un DICOM real de un paciente **de 18 a 100 años**. El servicio
rechaza a los menores y a las placas sin edad legible, y el script moriría al
imprimir la inferencia de muestra. El usado en la medición de referencia:

- `000fe35a-2649-43d4-b027-e67796d412e0.dcm`, 131 322 bytes, paciente de 40
  años. Es justo la mediana de tamaño del dataset (131 KB), así que la cifra es
  representativa.

```bash
docker compose cp /ruta/a/000fe35a-2649-43d4-b027-e67796d412e0.dcm copiloto-mcp:/modelo/ejemplo.dcm
docker compose cp medir_latencia.py copiloto-mcp:/modelo/medir_latencia.py
docker compose exec copiloto-mcp python /modelo/medir_latencia.py
```

> **En Windows con Git Bash**, pon `MSYS_NO_PATHCONV=1` delante del `exec`, o
> Git Bash convertirá `/modelo/...` en una ruta de Windows y verás un
> `can't open file '/app/C:/Program Files/Git/modelo/...'`.

El script hace 20 repeticiones por puerta más una de calentamiento y reporta la
mediana. Resultado de referencia, medido el 23-sep-2026:

```
DICOM de prueba: 131322 bytes
REST: mediana 39 ms | peor 45 ms | presupuesto 4000 ms -> 103x de margen
MCP : mediana 40 ms | peor 48 ms | presupuesto 4000 ms -> 100x de margen
```

| Puerta | Mediana | Peor de 20 | Presupuesto H4 | Margen |
| :--- | ---: | ---: | ---: | ---: |
| REST (`/inferir`) | **39 ms** | 45 ms | 4 000 ms | 103x |
| MCP (`/mcp`) | **40 ms** | 48 ms | 4 000 ms | 100x |

**Criterio de aceptación de H4 cumplido con dos órdenes de magnitud de
holgura.** Las dos puertas miden prácticamente lo mismo, que es lo esperado:
el trabajo real (decodificar el DICOM e inferir) es el mismo y el sobre del
protocolo no pesa nada al lado.

Si alguna mediana te saliera por encima de 4 000 ms, para y averigua por qué
antes de dar el hito por bueno.

## 7. Configurar el nodo de n8n

En el flujo de n8n, el copiloto se consume con el nodo **MCP Client Tool**
(`@n8n/n8n-nodes-langchain.mcpClientTool`, usa `typeVersion` 1.4), que se
engancha al puerto de herramientas de un nodo **AI Agent**.

| Campo | Valor |
| :--- | :--- |
| **Endpoint** | `http://copiloto-mcp:8000/mcp` |
| **Server Transport** | `HTTP Streamable` |
| **Authentication** | `None` |
| **Tools to Include** | `All` |

Notas que ahorran una tarde:

- La URL es `http://` y **nombre de servicio**, no `https://` ni `localhost`.
  Desde dentro de n8n, `localhost` es el propio contenedor de n8n.
- `HTTP Streamable`, no `Server Sent Events`: el SSE está marcado como
  deprecado y este servidor expone transporte *streamable*.
- Sin autenticación a propósito: el servicio no está publicado a internet y
  solo lo alcanza quien ya está dentro de la red de Docker.
- La herramienta se llama **`clasificar_radiografia`** y recibe un único
  argumento, `dicom_base64`: el DICOM completo codificado en base64.

### Una advertencia práctica sobre el base64 y el AI Agent

Un DICOM de 131 KB son ~175 KB de base64. Si el `dicom_base64` lo tiene que
**redactar el modelo** del AI Agent, eso no va a funcionar: no se le puede
pedir a un LLM que emita 175 KB de base64 literal. Dos salidas, ambas
soportadas por este servidor:

1. **Nodo HTTP Request contra la puerta REST** (lo más simple para una tubería
   fija, sin LLM de por medio): `POST http://copiloto-mcp:8000/inferir`, cuerpo
   `multipart/form-data`, campo de fichero llamado **`archivo`**. Devuelve
   exactamente el mismo JSON que la puerta MCP.
2. **Nodo HTTP Request hablando JSON-RPC contra `/mcp`** directamente, con el
   base64 puesto por una expresión de n8n y no por el modelo:

```
POST http://copiloto-mcp:8000/mcp
Content-Type: application/json
Accept: application/json, text/event-stream

{"jsonrpc":"2.0","id":1,"method":"tools/call",
 "params":{"name":"clasificar_radiografia",
           "arguments":{"dicom_base64":"<el base64 aqui>"}}}
```

La respuesta de `/mcp` llega como un evento SSE, con el JSON en la línea
`data:`, no como JSON pelado:

```
event: message
data: {"jsonrpc":"2.0","id":1,"result":{"content":[{"text":"...","type":"text"}]}}
```

## 8. Qué devuelve, y qué hace cuando se niega

Una inferencia correcta:

```json
{
  "probabilidad_cruda": 0.9858,
  "probabilidad_calibrada": 0.9263017435289581,
  "razon_de_verosimilitud": 44.17536578315011,
  "umbral": 0.4258,
  "clasificacion": "opacidad_probable",
  "edad_paciente": 40,
  "modelo": "efficientnet_b0_320px",
  "auc_validacion": 0.883,
  "milisegundos": 53.2
}
```

La cifra que se combina con la regla clínica es `razon_de_verosimilitud`; la
`probabilidad_calibrada` está calculada con la prevalencia del dataset
(0,2215) y no con la de la consulta.

Los rechazos llevan **código delante, separado por `": "`**, para que quien
llame parta por el primer `:` y no tenga que interpretar prosa:

| Código | Cuándo | REST | MCP |
| :--- | :--- | :--- | :--- |
| `fuera_de_alcance` | paciente fuera de 18-100 años | 422 | `isError: true` |
| `edad_desconocida` | la cabecera DICOM no declara edad interpretable | 422 | `isError: true` |
| `dicom_invalido` | los bytes no son un DICOM legible | 422 | `isError: true` |
| `payload_excesivo` | más de 5 MB (5 242 880 bytes) descodificados | 413 | `isError: true` |
| `base64_invalido` | el `dicom_base64` no es base64 válido | — | `isError: true` |

Comprobado en el contenedor con una placa de un paciente de 12 años; las dos
puertas dicen lo mismo:

```
REST: (422, {'codigo': 'fuera_de_alcance', 'detalle': 'El paciente tiene 12 anios y el modelo solo es valido entre 18 y 100.'})
MCP : {"result":{"content":[{"text":"Error executing tool clasificar_radiografia: fuera_de_alcance: El paciente tiene 12 anios ...","type":"text"}],"isError":true}}
```

Que el modelo **se niegue** a opinar sobre un menor es comportamiento
deseado, no un fallo del despliegue: los pesos se entrenaron y se validaron
sobre adultos.

## 9. Variables de entorno

Se declaran en el `docker-compose.yml`. Solo hay que tocarlas si se reentrena
el modelo.

| Variable | Valor por defecto | Qué es |
| :--- | :--- | :--- |
| `UMBRAL` | `0.4258` | punto de operación; el de especificidad 0,70 y recall 0,8815 |
| `AUC_VALIDACION` | `0.883` | AUC en validación, **se le muestra al profesional** en cada respuesta |
| `RUTA_PESOS` | `/modelo/pesos_modelo_cpu.pt` | dentro de la imagen |
| `RUTA_CALIBRADOR` | `/modelo/calibrador.json` | dentro de la imagen |
| `RED_N8N` | `[retirado]_[retirado]_network` | nombre de la red externa de n8n |

`AUC_VALIDACION` viaja por entorno y no como literal en el código a propósito:
es una afirmación de calidad sobre **los pesos**, no sobre el código. Si
reentrenas y no la actualizas, cada respuesta seguirá citando la cifra vieja.

## 10. Cuando algo va mal

| Síntoma | Causa | Arreglo |
| :--- | :--- | :--- |
| `network [retirado]_[retirado]_network declared as external, but could not be found` | la red no existe (caso local) | `docker network create [retirado]_[retirado]_network`, o `RED_N8N=<nombre real>` |
| `"/servidor/pesos_modelo_cpu.pt": not found` al construir | no copiaste los pesos | ver el paso 2 |
| HTTP **421 "Invalid Host header"** | el transporte MCP valida la cabecera `Host` y por defecto solo acepta `127.0.0.1` | ya está resuelto: la aplicación se construye con `host_permitido="0.0.0.0"`. Si reaparece, alguien cambió ese valor |
| n8n da `ECONNREFUSED` o `Name or service not known` | n8n y el copiloto no están en la misma red | comprobar con el `docker run --rm --network ...` del paso 5 |
| el estado se queda en `starting` | aún está cargando los pesos | esperar; son ~10 s, con 40 s de gracia |
| el estado pasa a `unhealthy` | el proceso murió al arrancar | `docker compose logs copiloto-mcp` |
| `can't open file '/app/C:/Program Files/Git/modelo/...'` | Git Bash convirtió la ruta | `MSYS_NO_PATHCONV=1` delante del comando |
| `curl http://localhost:8000/salud` desde el host no responde | **es lo correcto**: no hay `ports` publicados | usar `docker compose exec`, o un contenedor en la misma red |

Los logs, siempre:

```bash
docker compose logs -f copiloto-mcp
```

## 11. Apagar

```bash
docker compose down
```

Los pesos y el calibrador están dentro de la imagen, así que no se pierde nada
y el siguiente `up -d` vuelve a estar listo en 10 segundos.
