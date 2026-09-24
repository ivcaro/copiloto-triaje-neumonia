# Despliegue del servidor MCP (SP2)

Guía para levantar el copiloto de triaje desde cero **sin conocer el código**.
Al terminar tendrás un contenedor `copiloto-mcp` sirviendo el modelo por dos
puertas, unido a la misma red de Docker que n8n, y sabrás comprobar que
funciona.

Medido y verificado el 23-sep-2026 con Docker 29.6.1 y Compose v5.2.0.

> **Si vas a desplegar sobre un VPS en producción**, con n8n, PostgreSQL y la
> API del cliente ya corriendo, empieza por el **paso 2**: son seis
> comprobaciones de solo lectura que te dicen qué hay en marcha, qué no se va a
> tocar y si hay alguna colisión, sin modificar nada. Y antes de terminar, mira
> el **paso 12**: cómo bajar solo este servicio dejando el resto intacto.

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

## 2. Comprobaciones previas: SOLO LECTURA, antes de tocar nada

Esto es **lo primero que se ejecuta**. Ninguno de los comandos de esta sección
modifica nada: solo listan y consultan. No levantan contenedores, no crean
redes, no reinician, no borran. Puedes pasarlos enteros en el VPS con n8n,
PostgreSQL y la API del cliente en producción, sin riesgo.

El objetivo es que antes de levantar nada ya sepas tres cosas: qué hay en
marcha, qué no se va a tocar, y que no hay ninguna colisión esperándote.

Los comandos están escritos para el **VPS Linux**, que es donde va esto. Si los
pasas en Windows, los de Docker funcionan igual, pero `ss`, `df` y las rutas
`/tmp/...` no: ahí usa `netstat -ano`, el explorador de archivos y una ruta de
Windows.

### 2.1. Qué hay corriendo ahora, y qué NO se va a tocar

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
```

En el VPS verás algo parecido a esto (los nombres exactos son los de tu
instalación, no los copies: léelos):

```
NAMES           IMAGE                STATUS       PORTS
n8n             n8nio/n8n:...        Up 3 weeks   5678/tcp
nginx           nginx:...            Up 3 weeks   0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
[retirado]-api    [retirado]-api:...     Up 5 days    3001/tcp
[retirado]-db     postgres:16-alpine   Up 3 weeks
```

**Guarda esa lista**: es tu punto de comparación para el final (paso 12).

```bash
docker ps --format '{{.Names}}' | sort > /tmp/contenedores-antes.txt
```

Lo único que escribe ese comando es un fichero de texto en `/tmp`; a Docker no
lo toca.

Ninguno de los contenedores de la lista se modifica en este despliegue, y no es
una promesa: es consecuencia de cómo está escrito el compose.

| Por qué no se toca nada | Dónde se ve |
| :--- | :--- |
| El compose define **un solo servicio**, `copiloto-mcp` | `servidor/docker-compose.yml` |
| La red se declara `external: true`: Compose **no la crea, no la modifica y no la borra** | el mismo fichero |
| No hay `ports:`, así que no puede quitarle un puerto del host a nadie | el mismo fichero |
| No hay `volumes:`, así que no monta ni escribe nada del host | el mismo fichero |
| `docker compose down` lanzado desde `servidor/` solo alcanza a los contenedores de **este** proyecto | paso 12 |

Compruébalo tú, sin fiarte del párrafo anterior:

```bash
cd servidor
grep -nE 'ports:|volumes:|external:|container_name:' docker-compose.yml
```

Tiene que salir `external: true` y `container_name: copiloto-mcp`, y
**ninguna** línea `ports:` ni `volumes:`.

### 2.2. Que la red externa existe, y con qué nombre exacto

El compose se une a una red que **ya tiene que existir**. Si el nombre no
coincide carácter por carácter, Compose aborta antes de crear nada — que es el
fallo seguro: mejor eso que dos contenedores levantados sin verse.

```bash
docker network ls --filter name=[retirado]
```

Esperado:

```
NETWORK ID     NAME                    DRIVER    SCOPE
[retirado]   [retirado]_[retirado]_network   bridge    local
```

Lo que importa es la columna `NAME`: tiene que decir exactamente
`[retirado]_[retirado]_network`. Si en tu instalación se llama de otra forma, **no
edites el compose**: se le pasa por entorno con `RED_N8N` (paso 4).

### 2.3. Qué contenedores están ya en esa red

Esto contesta la pregunta que de verdad importa: ¿está n8n ahí? Si no está,
unirse a esa red no sirve para nada.

```bash
docker network inspect [retirado]_[retirado]_network --format '{{range .Containers}}{{println .Name}}{{end}}'
```

Esperado en el VPS: una lista que **incluya el contenedor de n8n**, junto a
nginx, `[retirado]-api` y lo que haya. Un nombre por línea.

Si n8n no aparece, pregúntaselo a n8n en vez de adivinarlo:

```bash
docker inspect <nombre-del-contenedor-de-n8n> --format '{{range $red, $c := .NetworkSettings.Networks}}{{println $red}}{{end}}'
```

La red que salga ahí es la que hay que pasar en `RED_N8N`.

### 2.4. Que el nombre `copiloto-mcp` no colisiona

El contenedor se llama `copiloto-mcp` con nombre fijo, y ese nombre es además
el nombre DNS que usará n8n. Hay que comprobar dos cosas.

```bash
docker ps -a --filter name=^/copiloto-mcp$ --format '{{.Names}}\t{{.Status}}'
```

**No debe imprimir nada.** Si imprime algo, ya existe un contenedor con ese
nombre — aunque esté parado — y el `up -d` fallaría con
`Conflict. The container name "/copiloto-mcp" is already in use`. Si pasa,
para y averigua de quién es antes de borrar nada.

Segundo: el nombre tampoco puede estar ya tomado dentro de la red, así que la
salida del paso 2.3 **no debe contener** `copiloto-mcp`. Si lo contuviera, n8n
resolvería el nombre al contenedor equivocado, que es un fallo silencioso y de
los caros.

De paso, que la etiqueta de imagen esté libre:

```bash
docker images copiloto-mcp
```

Esperado: solo la cabecera, sin ninguna fila debajo.

### 2.5. Los puertos: por diseño no hay nada que ocupar

**Este servicio no publica ningún puerto en el host.** El `EXPOSE 8000` del
Dockerfile y el `8000/tcp` que verás en `docker compose ps` son el puerto
*dentro* del contenedor, en su propio espacio de red. No ocupa el 8000 del VPS
y no puede colisionar con nada, ni con otro contenedor que también use el 8000
por dentro.

Verifícalo, que es más fiable que creerlo:

```bash
grep -n 'ports' docker-compose.yml   # no debe devolver ninguna linea
```

Solo si alguien decide publicarlo **para depurar** — no hace falta para que n8n
funcione, y saca la radiografía fuera de la red de Docker — entonces sí hay que
comprobar antes que el puerto del host está libre:

```bash
ss -ltnp | grep ':8000 ' || echo "8000 libre en el host"
docker ps --format '{{.Names}}\t{{.Ports}}' | grep ':8000->' || echo "ningun contenedor publica el 8000"
```

### 2.6. Que sobra disco

Es la forma clásica de romper un VPS en producción: la imagen ocupa unos 2 GB
en disco, y el que se queda sin espacio no es el copiloto, es PostgreSQL.

```bash
df -h /var/lib/docker
docker system df
```

Hacen falta **al menos 4 GB libres** antes de construir. Si vas justo, libera
espacio primero; no empieces la construcción a ver si cabe.

### Resumen: qué cambia en la máquina y qué no

| Cambia | No cambia |
| :--- | :--- |
| aparece un contenedor nuevo, `copiloto-mcp` | los contenedores que ya corrían |
| aparece una imagen nueva, `copiloto-mcp:0.1.0` (~2 GB en disco) | las imágenes de los demás stacks |
| ese contenedor se **une** a `[retirado]_[retirado]_network` | la red en sí: no se crea, ni se altera, ni se borra |
| — | los puertos del host: no se publica ninguno |
| — | volúmenes y datos: este servicio no tiene estado |

## 3. Requisitos previos

- Docker con Compose v2 o superior (probado en 29.6.1 / v5.2.0).
- El repositorio `copiloto-triaje`, rama `sp2-servidor-mcp`.
- Unos 4 GB libres de disco (la imagen ocupa ~2 GB en disco y la construcción
  descarga ~200 MB de ruedas). Se comprueba en el paso 2.6.
- Salida a internet durante la construcción (PyPI y `download.pytorch.org`).
- Para medir latencia o probar de verdad: **al menos un fichero DICOM real**
  del dataset RSNA, de un paciente **de 18 a 100 años** (ver el paso 7).

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

## 4. La red de Docker: el único punto que cambia entre el VPS y tu máquina

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

## 5. Construir la imagen

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

Salida literal, medida el 23-sep-2026 tras un `build --no-cache`:

```
IMAGE                ID             DISK USAGE   CONTENT SIZE   EXTRA
copiloto-mcp:0.1.0   2948362c4e3f          2GB          442MB
```

| Medida | Valor | Qué es |
| :--- | ---: | :--- |
| `CONTENT SIZE` | **442 MB** | lo que se empuja o se descarga, comprimido |
| `DISK USAGE` | **2 GB** | lo que ocupa en el disco del VPS, descomprimido |

El `ID` será otro en tu máquina; el tamaño no debería moverse apenas.

**No te alarmes por los 2 GB: la rueda CPU de torch sí se aplicó.** Se
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

## 6. Levantar y comprobar la salud

```bash
docker compose up -d
docker compose ps
```

El estado debe llegar a `healthy`. Cuenta hasta 30 segundos: el proceso carga
los pesos del modelo en unos 10 s, y luego hay que esperar a que el
`healthcheck` lo compruebe, que lo hace cada 30 s. Medido el 23-sep-2026:
`healthy` a los 26 s. El compose le da además 40 s de gracia (`start_period`)
antes de contar fallos, así que si lo miras demasiado pronto verás
`health: starting`, que es normal y no es un error.

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

## 7. Medir la latencia dentro del contenedor

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
mediana. Resultado de referencia, medido el 23-sep-2026 sobre una imagen
reconstruida desde cero (`docker compose build --no-cache`):

```
DICOM de prueba: 131322 bytes
REST: mediana 42 ms | peor 49 ms | presupuesto 4000 ms -> 95x de margen
MCP : mediana 41 ms | peor 46 ms | presupuesto 4000 ms -> 97x de margen
```

| Puerta | Mediana | Peor de 20 | Presupuesto H4 | Margen |
| :--- | ---: | ---: | ---: | ---: |
| REST (`/inferir`) | **42 ms** | 49 ms | 4 000 ms | 95x |
| MCP (`/mcp`) | **41 ms** | 46 ms | 4 000 ms | 97x |

**Criterio de aceptación de H4 cumplido con dos órdenes de magnitud de
holgura.** Las dos puertas miden prácticamente lo mismo, que es lo esperado:
el trabajo real (decodificar el DICOM e inferir) es el mismo y el sobre del
protocolo no pesa nada al lado.

No esperes las mismas cifras al milisegundo. Una medición anterior en la misma
máquina dio 39 ms y 40 ms: la dispersión entre corridas es del orden del 10 %,
irrelevante frente a un presupuesto 100 veces mayor. Lo que hay que mirar es el
orden de magnitud, no el dígito.

Si alguna mediana te saliera por encima de 4 000 ms, para y averigua por qué
antes de dar el hito por bueno.

## 8. Configurar el nodo de n8n

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

## 9. Qué devuelve, y qué hace cuando se niega

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

## 10. Variables de entorno

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

## 11. Cuando algo va mal

| Síntoma | Causa | Arreglo |
| :--- | :--- | :--- |
| `network [retirado]_[retirado]_network declared as external, but could not be found` | la red no existe (caso local) | `docker network create [retirado]_[retirado]_network`, o `RED_N8N=<nombre real>` |
| `"/servidor/pesos_modelo_cpu.pt": not found` al construir | no copiaste los pesos | ver el paso 3 |
| `Conflict. The container name "/copiloto-mcp" is already in use` | ya hay un contenedor con ese nombre | el paso 2.4 lo detecta antes. Averigua de quién es con `docker ps -a --filter name=copiloto-mcp` **antes** de borrarlo |
| `no space left on device` al construir | disco lleno | el paso 2.6 lo detecta antes. Libera espacio; no uses `docker system prune -a` en el VPS (paso 12) |
| HTTP **421 "Invalid Host header"** | el transporte MCP valida la cabecera `Host` y por defecto solo acepta `127.0.0.1` | ya está resuelto: la aplicación se construye con `host_permitido="0.0.0.0"`. Si reaparece, alguien cambió ese valor |
| n8n da `ECONNREFUSED` o `Name or service not known` | n8n y el copiloto no están en la misma red | comprobar con el `docker run --rm --network ...` del paso 6 |
| el estado se queda en `starting` | aún está cargando los pesos | esperar; son ~10 s, con 40 s de gracia |
| el estado pasa a `unhealthy` | el proceso murió al arrancar | `docker compose logs copiloto-mcp` |
| `can't open file '/app/C:/Program Files/Git/modelo/...'` | Git Bash convirtió la ruta | `MSYS_NO_PATHCONV=1` delante del comando |
| `curl http://localhost:8000/salud` desde el host no responde | **es lo correcto**: no hay `ports` publicados | usar `docker compose exec`, o un contenedor en la misma red |

Los logs, siempre:

```bash
docker compose logs -f copiloto-mcp
```

## 12. Vuelta atrás: bajar solo este servicio

Todo lo que hay que deshacer es un contenedor. No hay migraciones, ni
volúmenes, ni configuración del sistema que revertir.

### Bajarlo

Desde `servidor/`, y **solo** desde ahí:

```bash
cd servidor
docker compose down
```

Salida literal:

```
 Container copiloto-mcp Stopping
 Container copiloto-mcp Stopped
 Container copiloto-mcp Removing
 Container copiloto-mcp Removed
```

Cuatro líneas, las cuatro sobre `copiloto-mcp`. Si aparece el nombre de
cualquier otro contenedor, estabas en el directorio equivocado: `Ctrl+C` y
comprueba dónde estás antes de seguir.

`docker compose down` **no borra la red externa.** Comprobado: después del
`down`, `docker network ls` sigue mostrando `[retirado]_[retirado]_network` intacta con
n8n dentro. Compose no borra lo que no creó.

### Comprobar que no se rompió nada más

```bash
docker ps --format '{{.Names}}' | sort > /tmp/contenedores-despues.txt
diff /tmp/contenedores-antes.txt /tmp/contenedores-despues.txt
```

Si `diff` no imprime nada, la máquina está exactamente como la encontraste. (Si
lo corres con el copiloto aún arriba, la única diferencia debe ser una línea
`> copiloto-mcp`, y ninguna más.)

Y que n8n sigue vivo:

```bash
docker ps --filter name=n8n --format '{{.Names}}\t{{.Status}}'
```

### Pararlo sin borrarlo

Si solo quieres silenciarlo un rato y volver luego sin reconstruir:

```bash
docker compose stop     # se para, se queda creado
docker compose start    # vuelve en ~10 s
```

El servicio lleva `restart: unless-stopped`, así que un contenedor parado a
mano con `stop` **no revive** al reiniciar el demonio de Docker ni el VPS. Es
justo lo que se quiere para una parada controlada.

### Recuperar el disco

Solo después del `down`, y solo si quieres los ~2 GB de vuelta:

```bash
docker rmi copiloto-mcp:0.1.0
```

Afecta únicamente a esa etiqueta. Recuperarla cuesta un `docker compose build`,
unos 2 minutos.

### Tres comandos que NO hay que ejecutar en el VPS

| Comando | Qué rompería |
| :--- | :--- |
| `docker network rm [retirado]_[retirado]_network` | dejaría a n8n, a nginx y a la API del cliente sin red común. Esa red **no es nuestra** |
| `docker system prune -a` | borraría imágenes de los demás stacks, no solo la nuestra |
| `docker compose down` desde otro directorio | bajaría el stack de ese directorio, que puede ser el de producción |

Añadir `-v` / `--volumes` al `down` es inofensivo **aquí** porque este servicio
no tiene volúmenes, pero no cojas la costumbre: en el stack de al lado ese
mismo flag borra la base de datos.

### Volver a levantarlo

```bash
docker compose up -d
```

Los pesos y el calibrador viajan dentro de la imagen, así que no se pierde nada
y el servicio vuelve a estar `healthy` en unos 30 segundos.
