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

### Por qué estos pesos y no los que ganan la comparativa

Los pesos que se despliegan son los de la **corrida 6**,
`efficientnet_b0_320px_lote24_4+20ep`: EfficientNet-B0 a 320 px, AUC 0,8827 en
validación y 0,885 en prueba. La comparativa de corridas
(`docs/comparativa-corridas.md`) corona otra, `kaggle_efficientnet_b0_320px_c2`,
con AUC 0,889 en prueba. La pregunta es legítima, así que la respuesta queda
escrita aquí y no hay que reconstruirla.

Las ocho corridas de las tres arquitecturas —EfficientNet-B0, DenseNet-121 y
MobileNetV3— caben entre 0,874 y 0,889 de AUC en prueba. **Ese margen de 0,015
entre la mejor y la peor es del orden de lo que mueve una semilla distinta**, y
no hay que suponerlo: las dos ejecuciones de la MISMA configuración de
MobileNetV3 (`kaggle_mobilenet_v3_large_320px_c1` y `_c2`) difieren en 0,010 de
AUC entre sí. Dicho de otro modo, el ruido de una repetición se come dos tercios
de la diferencia entre la mejor arquitectura y la peor. Cada configuración se
entrenó una vez y con una sola semilla, así que la comparativa no puede
distinguir "mejor modelo" de "corrida afortunada", y elegir la que casualmente
queda arriba es **seleccionar por ruido**. La misma lógica está escrita en
`docs/frontera-recall-especificidad.md`, donde se decidió no reentrenar
persiguiendo las cinco milésimas de AUC que separan poder de no poder cumplir
los dos objetivos a la vez.

Empatadas estadísticamente, decide lo que sí se puede verificar: la corrida 6 es
la que tiene **el calibrador isotónico ajustado** sobre sus propias 3 810
radiografías de validación (`servidor/calibrador.json`, que registra su
procedencia) y **los pesos verificados a mano** por SHA-256, el hash que el paso
3.1 obliga a comprobar dos veces. Sin calibrador propio, la razón de
verosimilitud que consume SP4 no significaría lo que dice significar: un
calibrador ajustado sobre una corrida y aplicado a otra introduce exactamente el
sesgo silencioso que ese número existe para eliminar. Cambiar de corrida no es
copiar un `.pt`: obliga a reajustar el calibrador, a volver a medir la frontera
recall/especificidad y a reelegir el umbral, y todo eso a cambio de una
diferencia que la propia medición no distingue del ruido.

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
| El proyecto se llama `copiloto-mcp` (`name:` en el compose), así que `docker compose down` **solo** alcanza a este servicio | el mismo fichero, y paso 12 |

Compruébalo tú, sin fiarte del párrafo anterior:

```bash
cd servidor
grep -nE '^\s*(name|ports|volumes|external|container_name):' docker-compose.yml
```

Salida literal:

```
5:name: copiloto-mcp
13:    container_name: copiloto-mcp
47:    external: true
51:    name: ${RED_N8N:-[retirado]_[retirado]_network}
```

Cuatro líneas: el nombre del proyecto, el del contenedor, la red marcada como
externa y el nombre de esa red. Y **ninguna** línea `ports:` ni `volumes:`, que
es lo que querías comprobar.

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
grep -nE '^\s*ports:' docker-compose.yml   # no debe devolver ninguna linea
```

El `^\s*ports:` es a propósito y no un `grep ports` a secas: el compose tiene un
comentario que **explica** que no hay puertos, y un `grep ports` lo encontraría y
te haría creer que sí los hay. Lo que quieres comprobar es que no existe la
directiva, es decir una línea que empiece por `ports:`.

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
- Unos 4 GB libres de disco (la imagen ocupa ~2 GB en disco y la construcción
  descarga ~200 MB de ruedas). Se comprueba en el paso 2.6.
- Salida a internet durante la construcción (PyPI y `download.pytorch.org`).
- Acceso `ssh` al VPS, y `scp` en tu máquina (viene con Git para Windows).
- Para medir latencia o probar de verdad: **al menos un fichero DICOM real**
  del dataset RSNA, de un paciente **de 18 a 100 años** (ver el paso 7).
- El código y los pesos **puestos en el VPS**, que es el apartado 3.1.
- Si vas a redesplegar con `git pull`: una **llave de despliegue de solo
  lectura** en el VPS, que es el apartado 3.2. El repositorio es privado, así
  que sin ella el `git pull` se cuelga pidiendo usuario.

### 3.1. Llevar el código y los pesos al VPS

Un hecho manda sobre todo lo demás en este apartado:

> **Los pesos no viajan con el código.** `servidor/pesos_modelo_cpu.pt` son
> 16 MB binarios y está en `.gitignore` a propósito, así que **no llegan por
> `git`, ni hoy ni nunca**. El `servidor/calibrador.json` de al lado sí se
> versiona, ese viaja solo.

Eso parte el despliegue en dos envíos, vayas por donde vayas. Hay dos caminos,
y el que te toque depende de si el VPS puede hablar con el repositorio:

| | Cuándo usarlo | Qué hace |
| :--- | :--- | :--- |
| **Camino A: `git clone`** | el repositorio privado existe **y** el VPS tiene llave de despliegue | clona `main` y copia los pesos aparte |
| **Camino B: `git archive` + `tar`** | no hay remoto, o el VPS no tiene llave | empaqueta la rama y la copia por `scp` |

El camino A es el bueno si vas a redesplegar más de una vez, porque deja un
repositorio de verdad en `/opt/copiloto` y a partir de ahí actualizar es un
`git pull` (ver el redespliegue, al final del apartado 6). El camino B no deja
repositorio: cada actualización vuelve a ser un tar entero.

**Una cosa que el camino A necesita y el B no: credenciales en una máquina que
no es tuya.** El repositorio es privado, así que un `git pull` en el VPS se
queda colgado pidiendo usuario y contraseña. Se resuelve con una **llave de
despliegue de solo lectura acotada a este repositorio**, nunca con un token
dentro de la URL (`https://usuario:token@github.com/...`): ese token queda **en
claro** en `/opt/copiloto/.git/config` y en el historial de `root` del cliente,
y abre todos tus repositorios, no solo este. Ver 3.2.

Los comandos se ejecutan **en tu máquina Windows** (Git Bash), salvo los
marcados `[VPS]`.

Antes de empezar, sustituye en todos los comandos:

| Marcador | Por |
| :--- | :--- |
| `usuario@vps` | tu usuario y el host o IP del VPS, p. ej. `root@203.0.113.10` |
| `/opt/copiloto` | el directorio del VPS donde quieras dejar esto |
| `<url-del-repositorio>` | `github-copiloto:[retirado]/copiloto-triaje.git` — el repositorio privado, por el alias SSH del 3.2. Por HTTPS sería `https://github.com/[retirado]/copiloto-triaje.git`, pero entonces el VPS pide usuario en cada `pull` |

El prefijo `[VPS]` marca los comandos que van **dentro** de la sesión `ssh`. No
se escribe: es solo para que sepas en qué máquina estás en cada línea.

**Paso 1. Que los pesos estén en `servidor/` en tu máquina.** No se versionan,
así que se traen de la corrida que produjo el modelo:

```bash
cd "C:/Users/[retirado]/OneDrive/Desktop/Claude/Proyecto Integrador/copiloto-triaje"
cp "C:/Users/[retirado]/datasets/rsna-pneumonia/trabajo/corridas/efficientnet_b0_320px_lote24_4+20ep/checkpoints/pesos_modelo_cpu.pt" \
   servidor/pesos_modelo_cpu.pt
sha256sum servidor/pesos_modelo_cpu.pt
```

Tiene que decir exactamente:

```
bb985e1f792e1cfee150ec57bdc6d706f7484499fa999da3406a5798260e8d47
```

Si no coincide, para aquí: estarías desplegando un modelo distinto del que esta
guía certifica. Apunta ese hash, lo vuelves a usar en el paso 5.

#### Camino A: clonar el repositorio privado

Se clona **`main`**, y se clona en superficie. Los dos detalles importan:

```bash
ssh usuario@vps "git clone --depth 1 <url-del-repositorio> /opt/copiloto"
```

- **`main`, no `sp2-servidor-mcp`.** La rama ya está fusionada (`git rev-list
  --count main..sp2-servidor-mcp` da 0). Clonarla funcionaría hoy y rompería el
  **segundo** despliegue en cuanto la borres, con un `your configuration
  specifies to merge with the ref refs/heads/sp2-servidor-mcp... but no such
  ref was fetched` que no dice lo que pasa.
- **`--depth 1`** se salta los 2,1 MB de historial, que en un directorio de
  despliegue no sirven para nada.

Ahora los pesos, que el clon no trajo:

```bash
cd "C:/Users/[retirado]/OneDrive/Desktop/Claude/Proyecto Integrador/copiloto-triaje"
scp servidor/pesos_modelo_cpu.pt usuario@vps:/opt/copiloto/servidor/
```

Y salta al **paso 5**, la comprobación del hash, que no sobra en ningún camino.

> **Lo que el clon deja en el disco del cliente.** El árbol completo son 5,3 MB,
> de los cuales 4 MB son `docs/eda/metadatos_eda.csv`: 26 685 filas de
> metadatos por paciente del concurso RSNA. No entra en la imagen —el
> `Dockerfile.dockerignore` excluye `docs/`— pero sí queda en `/opt/copiloto`.
> Si no quieres eso en la máquina del cliente, el camino B no lo lleva, o se
> saca el CSV del repositorio.

#### Camino B: empaquetar y copiar

**Paso 2. Empaquetar el código.** `git archive` saca un tar de la rama tal como
está **commiteada**, sin `.git` y sin ficheros sueltos:

```bash
git archive --format=tar --output=../copiloto-triaje.tar main
```

Salen unos 5,3 MB. Ojo con la palabra *commiteada*: lo que no esté en un commit
de `main` no entra en el tar. Si vas a desplegar algo que acabas de tocar,
commitéalo primero.

**Paso 3. Copiar las dos cosas al VPS**, el código y los pesos por separado,
porque los pesos no están dentro del tar:

```bash
ssh usuario@vps "mkdir -p /opt/copiloto"
scp ../copiloto-triaje.tar usuario@vps:/opt/copiloto/
scp servidor/pesos_modelo_cpu.pt usuario@vps:/opt/copiloto/
```

**Paso 4. Desempaquetar en el VPS y poner los pesos en su sitio.** El tar no
lleva directorio raíz, así que se extrae directamente sobre `/opt/copiloto`:

```bash
ssh usuario@vps
[VPS] cd /opt/copiloto
[VPS] tar -xf copiloto-triaje.tar
[VPS] mv pesos_modelo_cpu.pt servidor/pesos_modelo_cpu.pt
[VPS] rm copiloto-triaje.tar
```

**Paso 5. Comprobar que llegó entero.** Esto es lo que separa "copié el
fichero" de "copié el fichero **entero**":

```bash
[VPS] sha256sum servidor/pesos_modelo_cpu.pt
bb985e1f792e1cfee150ec57bdc6d706f7484499fa999da3406a5798260e8d47

[VPS] ls servidor/
Dockerfile  Dockerfile.dockerignore  arrancar.py  calibrador.json
docker-compose.yml  medir_latencia.py  pesos_modelo_cpu.pt
```

El hash tiene que ser **idéntico** al del paso 1. Si difiere, la transferencia
se truncó: borra el fichero y repite el `scp`. Merece la pena mirarlo, porque un
`.pt` truncado no falla de forma clara: da un error de deserialización a mitad de
la carga del modelo, y se parece más a un bug del código que a una copia mala.

Si en `servidor/` falta `pesos_modelo_cpu.pt`, la construcción morirá con
`"/servidor/pesos_modelo_cpu.pt": not found`.

> En PowerShell en vez de Git Bash, el equivalente de `sha256sum` es
> `Get-FileHash servidor\pesos_modelo_cpu.pt -Algorithm SHA256`.

### 3.2. La llave de despliegue (solo para el camino A)

Solo hace falta si el VPS va a hablar con el repositorio, es decir, si vas a
redesplegar con `git pull`. Es **de solo lectura y acotada a este
repositorio**: si alguien entra al VPS, se lleva la capacidad de leer este
código y nada más.

En el VPS, generar la llave:

```bash
[VPS] ssh-keygen -t ed25519 -N '' -C 'despliegue-copiloto' -f ~/.ssh/copiloto_deploy && cat ~/.ssh/copiloto_deploy.pub
```

**Ese `.pub` lo pegas tú** en GitHub: repositorio → *Settings* → *Deploy keys* →
*Add deploy key*, **sin marcar** *Allow write access*. Un despliegue no tiene
por qué poder escribir en el repositorio.

Si el VPS ya tiene una llave de despliegue para otro repositorio privado, hace
falta una **segunda**: GitHub no deja reutilizar la misma en dos repositorios
(`key is already in use`). De ahí que se le ponga un alias propio:

```bash
[VPS] printf 'Host github-copiloto\n  HostName github.com\n  User git\n  IdentityFile ~/.ssh/copiloto_deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config && chmod 600 ~/.ssh/config
```

```bash
[VPS] ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts
```

Ese `ssh-keyscan` evita que el primer `git clone` se quede colgado esperando un
"¿confías en este host?" que nadie va a contestar dentro de un script.

Con el alias puesto, la URL del clon es `github-copiloto:[retirado]/copiloto-triaje.git`.
Para comprobar que la llave quedó bien y **sin permiso de escritura**:

```bash
[VPS] ssh -T git@github-copiloto
```

Debe nombrar el repositorio y **no** decir `write access`.

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
could not be found`.

Créate una red **con un nombre de tirar**, y pásasela por `RED_N8N`:

```bash
docker network create copiloto-local
RED_N8N=copiloto-local docker compose up -d
```

Y cuando acabes, primero baja el contenedor y luego borra **esa** red:

```bash
docker compose down
docker network rm copiloto-local
```

El nombre de tirar no es remilgo: es para que el nombre de la red de producción
**nunca aparezca en esta guía al lado de un `docker network rm`**. Si lo hiciera,
bastaría un copiar y pegar despistado en la sesión equivocada para dejar a n8n,
a nginx y a la API del cliente sin red común. Docker se niega a borrar una red
con contenedores conectados, pero no si en ese momento están parados, así que la
protección no es de fiar. Para eso está la variable.

Recuerda que si levantas con `RED_N8N=copiloto-local`, **todos** los comandos
posteriores que mencionen la red —el `docker run --network ...` del paso 6— usan
también `copiloto-local`.

## 5. Construir la imagen

Todos los comandos de aquí en adelante se ejecutan **desde el directorio
`servidor/`**:

```bash
cd servidor
docker compose build
```

Tarda unos 2 minutos la primera vez; casi todo es la descarga de torch
(196,3 MB). La imagen resultante es `copiloto-mcp:0.1.0`.

Todo lo que se instala está clavado a una versión exacta, **incluida la imagen
base, que se referencia por digest** y no por la etiqueta `python:3.12-slim`. Es
deliberado: una etiqueta se mueve con cada parche de Debian, y entonces la imagen
que construyes dentro de un mes no sería la que se midió. Si construyes hoy y
construyes en marzo, sale lo mismo.

```bash
docker images copiloto-mcp
```

Salida literal, medida el 23-sep-2026:

```
IMAGE                ID             DISK USAGE   CONTENT SIZE   EXTRA
copiloto-mcp:0.1.0   f4aa5009834b          2GB          442MB
```

| Medida | Valor | Qué es |
| :--- | ---: | :--- |
| `CONTENT SIZE` | **442 MB** | lo que se empuja o se descarga, comprimido |
| `DISK USAGE` | **2 GB** | lo que ocupa en el disco del VPS, descomprimido |

El `ID` será otro en tu máquina —lo fija también la fecha de construcción— pero
el tamaño no debería moverse. Si quieres confirmar que llevas las versiones
certificadas:

```bash
docker run --rm --entrypoint python copiloto-mcp:0.1.0 \
  -c "import importlib.metadata as m; [print(p, m.version(p)) for p in ('torch','fastapi','mcp','uvicorn','python-multipart')]"
```

```
torch 2.14.0+cpu
fastapi 0.141.1
mcp 2.2.0
uvicorn 0.53.0
python-multipart 0.0.32
```

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
docker run --rm --network "${RED_N8N:-[retirado]_[retirado]_network}" python:3.12-slim python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://copiloto-mcp:8000/salud')))"
```

Es la **misma variable** con la que levantaste el compose, y por eso va aquí en
vez del nombre literal: si arrancaste con `RED_N8N=copiloto-local`, exporta la
variable en esta sesión (`export RED_N8N=copiloto-local`) y el comando usa
`copiloto-local` solo; si no la declaraste, cae al mismo nombre por defecto que
el compose. Un literal aquí obligaría a editarlo a mano cada vez y dejaría que
esta comprobación mirase una red distinta de la que se está usando —justo lo que
esta comprobación existe para descartar.

Los comandos de **solo lectura** del paso 2, como `docker network inspect`, sí
llevan el nombre literal, y eso es a propósito: ahí lo que se teclea es el nombre
real que acabas de leer en `docker network ls`.

Si esto responde, el cableado de red está bien. Si da `Name or service not
known`, los dos contenedores no están en la misma red.

### Comprobar que los límites de recursos llegaron de verdad

Esto **no es opcional en un VPS compartido**, y es la comprobación que más fácil
se olvida. Los límites se declaran en el compose bajo `deploy.resources.limits`,
que es sintaxis de Swarm: un Compose que no la interprete arranca el contenedor
**sin límite ninguno y sin avisar**. El síntoma no sería un error, sería el
copiloto comiéndose la RAM y la CPU que necesitan PostgreSQL y la API del
cliente.

```bash
docker inspect copiloto-mcp --format '{{.HostConfig.Memory}}'
docker inspect copiloto-mcp --format '{{.HostConfig.NanoCpus}}'
```

Esperado, y verificado el 23-sep-2026 con Compose v5.2.0:

```
2147483648     <- 2 GiB de memoria
2000000000     <- 2 nucleos (en milmillonesimas)
```

**Si alguno sale `0`, no hay límite**: tu versión de Compose está ignorando el
bloque `deploy`. En ese caso cambia en `docker-compose.yml` el bloque por sus
equivalentes de siempre, que ninguna versión ignora:

```yaml
    mem_limit: 2g
    cpus: 2.0
```

Y el tercer tope, que no es de CPU ni de memoria sino de **disco**:

```bash
docker inspect copiloto-mcp --format 'driver={{.HostConfig.LogConfig.Type}} max-size={{index .HostConfig.LogConfig.Config "max-size"}} max-file={{index .HostConfig.LogConfig.Config "max-file"}}'
```

Esperado: `driver=json-file max-size=10m max-file=3`.

Sin ese bloque, Docker escribe el log del contenedor **sin límite ni rotación**
en `/var/lib/docker/containers/<id>/<id>-json.log`. Y hay una fuente que no
para nunca: el `healthcheck` consulta `/salud` cada 30 s y uvicorn registra una
línea por petición, o sea unas **2 880 líneas al día —del orden de 200 MB al
año— antes de que pase un solo paciente**. En un VPS compartido con dos
PostgreSQL, [retirado] y n8n, el disco que se llena no es solo tuyo.

Con `max-size: 10m` y `max-file: 3` el techo son 30 MB duros, y
`docker logs --tail` sigue sirviendo igual para diagnosticar.

> Un detalle que confunde al redesplegar: **el contador de logs vuelve a cero**,
> porque el fichero va atado al contenedor y `up --build` crea uno nuevo. Ver
> el log pequeño después de un despliegue no significa que la rotación esté
> funcionando; para eso está el `docker inspect` de arriba.

Y comprueba además que torch se ha enterado del tope de CPU, porque **no mira el
cgroup**: se guía por `OMP_NUM_THREADS`, que el compose fija a 2.

```bash
docker compose exec copiloto-mcp python -c "import os,torch; print(torch.get_num_threads(), os.cpu_count())"
```

```
2 20
```

El primer número es el que importa y tiene que coincidir con `cpus`. El segundo
es cuántos núcleos ve la máquina, y que sean distintos es justo el motivo de que
`OMP_NUM_THREADS` esté puesto: sin él, torch abriría 20 hilos para pelearse por
una cuota de 2 núcleos, con el VPS entero pagándolo.

### Redespliegue: actualizar una instalación que ya existe

Todo lo anterior es el **primer** despliegue. Para los siguientes, con el
camino A, es una sola orden:

```bash
cd /opt/copiloto && git pull --ff-only && docker compose -f servidor/docker-compose.yml up -d --build copiloto-mcp && for i in $(seq 1 30); do e=$(docker inspect -f '{{.State.Health.Status}}' copiloto-mcp 2>/dev/null || echo ausente); [ "$e" = healthy ] && break; sleep 5; done && docker inspect -f '{{.State.Health.Status}}' copiloto-mcp && docker compose -f servidor/docker-compose.yml exec copiloto-mcp python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/salud')))"
```

Cuatro cosas que esa línea tiene por un motivo:

- **`--ff-only`.** Un directorio de despliegue nunca debe intentar fusionar. Si
  alguien editó algo a mano en `/opt/copiloto`, esto falla en vez de mezclar.
- **`--build` no es opcional.** El tag está fijado a `copiloto-mcp:0.1.0`
  (línea 12 del compose). Sin `--build`, Compose ve que la imagen ya existe, no
  reconstruye, y **sigue sirviendo el código viejo después de un `git pull`
  exitoso**, sin un solo mensaje de error.
- **Espera a `healthy`, no cuenta segundos.** El `start_period` es de 40 s, así
  que un `sleep 30` te enseñaría `health: starting` y parecería un fallo.
- **Pregunta a `/salud` por `exec`.** `docker logs` solo enseña uvicorn
  arrancando: un contenedor `Up` con los pesos mal cargados se ve idéntico a
  uno sano. Y `curl localhost:8000` **desde el host falla aunque todo esté
  perfecto**, porque el compose no publica puertos a propósito.

**Los pesos sobreviven al `git pull`.** Están en `.gitignore`, y ni `pull`, ni
`checkout`, ni `reset --hard` tocan un fichero ignorado y sin seguimiento. El
único comando que los destruye es `git clean -xfd`, que es justo el reflejo de
"dejar el repositorio limpio": no lo teclees en `/opt/copiloto`.

**Si reentrenaste el modelo**, los pesos nuevos van por `scp` como en el primer
despliegue, y hay que revisar que `UMBRAL` y `AUC_VALIDACION` del compose sigan
describiendo *esos* pesos:

```bash
cd /opt/copiloto && sha256sum servidor/pesos_modelo_cpu.pt && grep -nE 'UMBRAL|AUC_VALIDACION' servidor/docker-compose.yml
```

**El disco, cada pocos redespliegues.** Como el tag es fijo, cada
reconstrucción deja la imagen anterior colgando (~2 GB). Se listan y se borran
**por ID**, nunca con `prune`, que en esta máquina se llevaría por delante
cosas del cliente:

```bash
docker images --filter dangling=true --format '{{.ID}} {{.CreatedSince}} {{.Size}}'
```

> **Construir consume la máquina del cliente.** Los topes de
> `deploy.resources.limits` acotan el contenedor **en ejecución**, no el
> `build`. Instalar torch tarda minutos a toda CPU dentro del demonio Docker
> del cliente. Si `free -m` da menos de ~3 000 MB disponibles, no construyas
> ahí: construye en local y mueve la imagen ya hecha con
> `docker save copiloto-mcp:0.1.0 | gzip | ssh usuario@vps "gunzip | docker load"`,
> y luego solo `up -d` sin `--build`.

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
mediana. Resultado de referencia, medido el 23-sep-2026, con la imagen de
versiones clavadas y **con los límites de 2 núcleos y 2 GB ya aplicados**:

```
DICOM de prueba: 131322 bytes
REST: mediana 38 ms | peor 50 ms | presupuesto 4000 ms -> 104x de margen
MCP : mediana 43 ms | peor 52 ms | presupuesto 4000 ms -> 93x de margen
```

| Puerta | Mediana | Peor de 20 | Presupuesto H4 | Margen |
| :--- | ---: | ---: | ---: | ---: |
| REST (`/inferir`) | **38 ms** | 50 ms | 4 000 ms | 104x |
| MCP (`/mcp`) | **43 ms** | 52 ms | 4 000 ms | 93x |

**Criterio de aceptación de H4 cumplido con dos órdenes de magnitud de
holgura.** Las dos puertas miden prácticamente lo mismo, que es lo esperado:
el trabajo real (decodificar el DICOM e inferir) es el mismo y el sobre del
protocolo no pesa nada al lado.

Que la medida se tomase con la CPU acotada a dos núcleos importa: es la cifra del
servicio tal como se va a desplegar, no la de un contenedor sin límites. Acotarla
no costó nada medible —sin límite las medianas eran 42 ms y 41 ms—, porque esta
red a 320×320 no aprovecha más de dos hilos.

No esperes las mismas cifras al milisegundo. Entre corridas la dispersión es del
orden del 10 % (se han visto 38, 39, 41, 42 y 43 ms según la puerta y la
corrida), irrelevante frente a un presupuesto 100 veces mayor. Lo que hay que
mirar es el orden de magnitud, no el dígito.

### Medido en el VPS real (24-sep-2026)

Las cifras de arriba son de una máquina de desarrollo. En el VPS de producción,
con la misma radiografía de 99 808 bytes y el mismo tope de dos núcleos:

| Puerta | Mediana | Peor de 20 | Margen |
| :--- | ---: | ---: | ---: |
| MCP (`/mcp`) | **143 ms** | 225 ms | **28x** |

**3,3 veces más lento que en desarrollo, y es lo esperado:** ese servidor tiene
otros 23 contenedores encima —n8n, [retirado], [retirado], nginx, seis servicios
de otro proyecto y dos PostgreSQL— compitiendo por la CPU. Los dos núcleos que
el compose reserva son un techo, no una reserva: si la máquina está ocupada, se
obtiene menos.

**Usa 143 ms, no 43 ms, para cualquier informe.** Sigue habiendo 28 veces de
holgura sobre el presupuesto de H4, que es lo que importa; pero la cifra que
describe el sistema desplegado es la del sitio donde está desplegado.

Comprobado en la misma sesión, y son las dos cosas que había que demostrar: los
topes llegaron de verdad (`NanoCpus=2000000000`, `Memory=2147483648`) y el
stack del cliente no se movió —los 23 contenedores siguieron con sus tiempos de
actividad intactos, ninguno reinició—.

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

**El base64 puede venir envuelto en líneas.** El servidor quita los espacios y
los saltos de línea antes de descodificar, así que da igual si la librería que
lo genera corta a 76 columnas —el comportamiento por defecto de muchas, incluida
`base64.encodebytes` de Python— o lo manda en una sola línea. Lo que sí sigue
rechazándose con `base64_invalido` es cualquier carácter que no sea del alfabeto
base64: eso no se ignora en silencio, porque si se ignorase el error reaparecería
más tarde como `dicom_invalido` y apuntaría al sitio equivocado.

## 9. Qué devuelve, y qué hace cuando se niega

Una inferencia correcta. Esta es literalmente la respuesta del DICOM de
referencia del paso 7, la primera de la corrida (de ahí que `milisegundos` sea
más alto que la mediana: la primera paga el arranque perezoso):

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
  "milisegundos": 59.8
}
```

`milisegundos` es lo único que cambia entre corridas; el resto es determinista y
te debe salir idéntico con este mismo fichero.

La cifra que se combina con la regla clínica es `razon_de_verosimilitud`; la
`probabilidad_calibrada` está calculada con la prevalencia del dataset
(0,2215) y no con la de la consulta.

### La razón de verosimilitud está ACOTADA, y eso es parte del contrato

Quien consuma este campo —SP4— tiene que saber que no puede tomar cualquier
valor. Con el calibrador que hoy sirve el contenedor
(`efficientnet_b0_320px_lote24_4+20ep`):

| Cota | `probabilidad_calibrada` | `razon_de_verosimilitud` |
| :--- | ---: | ---: |
| mínima | 0,004608 | **0,0163** |
| máxima | 0,956522 | **77,32** |

Ninguna radiografía, por extrema que sea, sale de ahí. **La razón es que la
curva de calibración no sostiene más certeza que esa.** La regresión isotónica
se ajustó sobre 3 810 radiografías de validación y se guarda como 200 puntos;
en el punto más bajo y en el más alto —uno de 200 en cada extremo— el tramo
correspondiente ya no tiene ningún negativo (o ningún positivo) y la isotónica
devuelve 0,0 y 1,0 exactos. Esos dos valores no son una medición: son el
artefacto de un tramo sin contraejemplos. Dejarlos pasar daría razones de
verosimilitud de 3,5e-06 y 3,5e+06, y como SP4 las multiplica por las *odds* de
la regla clínica, un paciente con sospecha alta (previo 0,90) acabaría con un
posterior de 0,003% —certeza de ausencia, es decir un falso negativo— cuando el
vecino inmediato de la curva, que sí tiene datos detrás, da 12,8%. Un salto de
4 630 veces decidido por una sola placa. En el extremo alto pasa lo simétrico y
fabrica certeza de presencia.

Así que el tope es el último valor **sostenido** de la curva por cada lado, y no
una constante cerca de 0 y de 1. Las dos cifras de la tabla salen de
`servidor/calibrador.json`, se recalculan solas al cargarlo y **cambiarán si se
reajusta el calibrador**: no están escritas en el código. Si se reentrena, hay
una prueba (`test_el_calibrador_desplegado_acota_la_evidencia_donde_dice_el_contrato`)
que falla y obliga a actualizar esta tabla en vez de dejarla mintiendo.

Consecuencia práctica para SP4: la evidencia de imagen puede mover el previo
clínico, pero no puede anularlo ni volverlo certeza. Eso es deliberado.

### Cuando se niega: los códigos de rechazo

Todo rechazo lleva un **código** legible por máquina, pero **dónde aparece
depende de la puerta**, y esto importa para programar el cliente:

- **Por REST** viene aislado en el campo `codigo` del JSON. Nada que parsear.
- **Por MCP** viene dentro del texto del error, y **no es el primer campo**: el
  SDK antepone `Error executing tool clasificar_radiografia: ` al mensaje, así
  que el código queda de **segundo**. Hay que buscarlo dentro del texto —o
  quitar ese prefijo primero—; **partir por el primer `:` devuelve
  `Error executing tool clasificar_radiografia`**, que es lo mismo para todos
  los códigos y no sirve de nada. Se ve en el ejemplo de más abajo.

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
| `AUC_VALIDACION` | **ninguno: es obligatoria** (el compose la pone a `0.883`) | AUC en validación, **se le muestra al profesional** en cada respuesta |
| `RUTA_PESOS` | `/modelo/pesos_modelo_cpu.pt` | dentro de la imagen |
| `RUTA_CALIBRADOR` | `/modelo/calibrador.json` | dentro de la imagen |
| `OMP_NUM_THREADS` | `2` | hilos que usa torch. **Tiene que valer lo mismo que `cpus`** del bloque de límites: torch no lee el cgroup y sin esto abriría un hilo por núcleo del host |
| `RED_N8N` | `[retirado]_[retirado]_network` | nombre de la red externa de n8n. Se pasa en la línea de comandos, no se edita el fichero |

`AUC_VALIDACION` viaja por entorno y no como literal en el código a propósito:
es una afirmación de calidad sobre **los pesos**, no sobre el código. Si
reentrenas y no la actualizas, cada respuesta seguirá citando la cifra vieja.

Y **no tiene valor por defecto**: si falta, `arrancar.py` se niega a arrancar con
un mensaje que dice qué declarar, en vez de servir una cifra inventada. Un
default —cualquier default— convertiría esta variable en exactamente la mentira
silenciosa que existe para evitar: sobreviviría a un reentrenamiento y nadie se
enteraría. El compose ya la declara, así que en el despliegue normal esto no se
nota; se nota si alguien levanta el contenedor a mano y se la olvida, que es
justo cuando conviene notarlo.

## 11. Cuando algo va mal

| Síntoma | Causa | Arreglo |
| :--- | :--- | :--- |
| `network [retirado]_[retirado]_network declared as external, but could not be found` | el nombre que espera el compose no es el de la red real | **primero**: averigua el nombre real con `docker network ls` y arranca con `RED_N8N=<nombre real> docker compose up -d`. Ver el recuadro de abajo |
| `"/servidor/pesos_modelo_cpu.pt": not found` al construir | no copiaste los pesos | ver el paso 3 |
| `Conflict. The container name "/copiloto-mcp" is already in use` | ya hay un contenedor con ese nombre | el paso 2.4 lo detecta antes. Averigua de quién es con `docker ps -a --filter name=copiloto-mcp` **antes** de borrarlo |
| `no space left on device` al construir | disco lleno | el paso 2.6 lo detecta antes. Libera espacio; no uses `docker system prune -a` en el VPS (paso 12) |
| HTTP **421 "Invalid Host header"** | el transporte MCP valida la cabecera `Host` y por defecto solo acepta `127.0.0.1` | ya está resuelto: la aplicación se construye con `direccion_de_escucha="0.0.0.0"`. Si reaparece, alguien cambió ese valor |
| n8n da `ECONNREFUSED` o `Name or service not known` | n8n y el copiloto no están en la misma red | comprobar con el `docker run --rm --network ...` del paso 6 |
| el estado se queda en `starting` | aún está cargando los pesos | esperar; son ~10 s, con 40 s de gracia |
| el estado pasa a `unhealthy` | el proceso murió al arrancar | `docker compose logs copiloto-mcp` |
| `can't open file '/app/C:/Program Files/Git/modelo/...'` | Git Bash convirtió la ruta | `MSYS_NO_PATHCONV=1` delante del comando |
| `curl http://localhost:8000/salud` desde el host no responde | **es lo correcto**: no hay `ports` publicados | usar `docker compose exec`, o un contenedor en la misma red |
| el `git pull` del VPS se queda colgado sin decir nada | está esperando usuario y contraseña: el repositorio es privado | la llave de despliegue del paso 3.2. **No** metas un token en la URL |
| desplegaste, el `git pull` trajo cambios, y el servicio sigue comportándose igual que antes | se levantó **sin `--build`**: el tag `copiloto-mcp:0.1.0` es fijo, Compose vio la imagen y no reconstruyó | `up -d --build`. No da ningún error, por eso hay que saberlo |
| `untracked working tree files would be overwritten by merge` al hacer `git pull` | desplegaste antes por el camino B y ahora el repositorio trae un fichero que ya existía suelto | borra el fichero suelto que nombre el error y repite el `pull` |

### La red no aparece: NO la crees en el VPS

Este es el error que más tienta a hacer lo peor, así que va aparte.

Cuando el compose dice que la red externa no existe, la reacción natural es
crearla. **En el VPS eso es justo lo que no hay que hacer.** Si la red real se
llama de otra forma, `docker network create [retirado]_[retirado]_network` te deja una
red vacía, el contenedor arranca, el estado dice `healthy`, todo parece bien
— y n8n no lo alcanza nunca, porque están en redes distintas. Es el fallo
silencioso que el paso 2.2 existe para evitar, y lo habrías provocado tú.

El orden correcto es siempre este:

```bash
# 1. cual es la red real
docker network ls

# 2. si n8n no se deja adivinar por el nombre, preguntaselo
docker inspect <nombre-del-contenedor-de-n8n> --format '{{range $red, $c := .NetworkSettings.Networks}}{{println $red}}{{end}}'

# 3. arrancar con el nombre real, sin editar el compose
RED_N8N=<nombre real> docker compose up -d
```

`docker network create` solo tiene sentido **en local**, con un nombre de tirar,
y está en el Caso B del paso 4. **Nunca en el VPS**: allí la red la posee la
infraestructura del cliente y ya existe.

Los logs, siempre:

```bash
docker compose logs -f copiloto-mcp
```

## 12. Vuelta atrás: bajar solo este servicio

Todo lo que hay que deshacer es un contenedor. No hay migraciones, ni
volúmenes, ni configuración del sistema que revertir.

### Bajarlo

Antes de bajar nada, confirma qué proyecto vas a tocar. El compose declara
`name: copiloto-mcp`, así que el proyecto se identifica solo y no depende de
cómo se llame la carpeta:

```bash
docker compose ls
```

```
NAME           STATUS       CONFIG FILES
copiloto-mcp   running(1)   /opt/copiloto/servidor/docker-compose.yml
```

`running(1)`: un solo contenedor. Si ves cualquier otro proyecto en esa línea,
no es el nuestro.

Ahora sí. Se baja **por nombre de proyecto**, no desde un directorio:

```bash
docker compose -p copiloto-mcp down
```

Con `-p` no se lee ningún fichero de compose, así que **el directorio en el que
estés deja de ser un riesgo**. Esa es toda la diferencia: `docker compose down`
a secas baja el proyecto de la carpeta donde te encuentres, y en este VPS esa
carpeta puede ser la del cliente. La única razón por la que `-p copiloto-mcp`
funciona es la línea 5 del compose (`name: copiloto-mcp`); si alguien la quita
en un commit futuro, este comando deja de identificar nada.

Y no teclees nunca `-v` ni `--volumes` en ese `down`. Aquí es inofensivo —este
servicio no declara volúmenes— pero esa memoria muscular, aplicada al stack de
al lado, borra los datos del cliente.

Salida literal:

```
 Container copiloto-mcp Stopping
 Container copiloto-mcp Stopped
 Container copiloto-mcp Removing
 Container copiloto-mcp Removed
```

Cuatro líneas, las cuatro sobre `copiloto-mcp`. Si aparece el nombre de
cualquier otro contenedor, para: `Ctrl+C` y vuelve al `docker compose ls`.

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
