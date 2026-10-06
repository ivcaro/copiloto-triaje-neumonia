# Despliegue del servidor MCP (SP2)

Guía para levantar el copiloto de triaje desde cero **sin conocer el código**.
Al terminar tendrás un contenedor `copiloto-mcp` sirviendo el modelo por dos
puertas y, desde SP3, su base de datos `copiloto-bd`, unidos a la misma red de
Docker que n8n, y sabrás comprobar que funcionan.

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

**El servicio no publica ningún puerto al host.** Es deliberado: una vez que la
radiografía está en n8n, no sale de la máquina. Solo se alcanza desde dentro de
la red de Docker, por el nombre de servicio `copiloto-mcp`.

> **Corregido el 26-sep, a raíz de una evaluación externa.** Aquí se leía «la
> radiografía no debe salir de la máquina», a secas. Eso describe bien el tramo
> n8n → copiloto y calla el anterior: el profesional manda el DICOM **por
> Telegram**, así que la imagen ya salió de la red del centro y pasó por los
> servidores de Telegram antes de que este contenedor la vea. Sin acotar el
> tramo, quien lee esta guía entiende que la imagen nunca sale de
> infraestructura propia, y entonces la frase deja de describir el despliegue y
> empieza a prometer una privacidad que no hay. El riesgo del tramo de entrada
> está declarado en el §5.5 del diseño de SP3.

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
(y los demás contenedores, que son ajenos: ninguno de la lista se toca)
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
| El compose define **dos servicios**, `copiloto-mcp` y, desde SP3, su base `copiloto-bd`; ninguno es de otro stack | `servidor/docker-compose.yml` |
| La red se declara `external: true`: Compose **no la crea, no la modifica y no la borra** | el mismo fichero |
| No hay `ports:`, así que no puede quitarle un puerto del host a nadie | el mismo fichero |
| El único `volumes:` es un volumen con nombre que gestiona Docker, `copiloto_bd_datos`, para la base: no monta ni escribe ninguna carpeta del host | el mismo fichero |
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
93:    container_name: copiloto-bd
101:    volumes:
124:    external: true
133:    name: ${RED_N8N:?define RED_N8N con el nombre de la red externa de n8n}
135:volumes:
```

Siete líneas: el nombre del proyecto, los dos contenedores (el servicio y,
desde SP3, su base de datos), la red marcada como externa y el nombre de esa
red, que **no está escrito en el fichero**: lo pone quien despliega, en
`RED_N8N` (paso 4). Los dos `volumes:` son el mismo volumen con nombre,
`copiloto_bd_datos`, que gestiona Docker: no es una carpeta del host. Y
**ninguna** línea `ports:`, que es lo que querías comprobar.

### 2.2. Que la red externa existe, y con qué nombre exacto

El compose se une a una red que **ya tiene que existir**, y su nombre **no
está en el repositorio**: se lo das tú en la variable `RED_N8N` (paso 4). Si el
nombre no coincide carácter por carácter, Compose aborta antes de crear nada —
que es el fallo seguro: mejor eso que dos contenedores levantados sin verse.

```bash
docker network ls
```

Esperado, entre las demás redes de la máquina, una línea como esta:

```
NETWORK ID       NAME        DRIVER    SCOPE
<id-de-la-red>   <RED_N8N>   bridge    local
```

Lo que importa es la columna `NAME`: **apunta el nombre exacto** de la red
donde corre n8n. Si hay varias y no es evidente cuál es, el paso 2.3 lo
resuelve preguntándoselo a n8n. Ese nombre es el valor de `RED_N8N`, y **no se
escribe en el compose**: va en `servidor/.env` (paso 4).

### 2.3. Qué contenedores están ya en esa red

Esto contesta la pregunta que de verdad importa: ¿está n8n ahí? Si no está,
unirse a esa red no sirve para nada.

Pon en lugar de `<RED_N8N>` el nombre que apuntaste en el paso 2.2:

```bash
docker network inspect <RED_N8N> --format '{{range .Containers}}{{println .Name}}{{end}}'
```

Esperado en el VPS: una lista que **incluya el contenedor de n8n**, junto a
nginx, los contenedores ajenos y lo que haya. Un nombre por línea.

Si n8n no aparece, pregúntaselo a n8n en vez de adivinarlo:

```bash
docker inspect <nombre-del-contenedor-de-n8n> --format '{{range $red, $c := .NetworkSettings.Networks}}{{println $red}}{{end}}'
```

La red que salga ahí es la que hay que pasar en `RED_N8N`.

### 2.4. Que el nombre `copiloto-mcp` no colisiona

El contenedor se llama `copiloto-mcp` con nombre fijo, y ese nombre es además
el nombre DNS que usará n8n. Desde SP3 lo acompaña su base, `copiloto-bd`,
también con nombre fijo. Hay que comprobar dos cosas, y las dos para los dos
nombres.

```bash
docker ps -a --filter name=^/copiloto-mcp$ --filter name=^/copiloto-bd$ --format '{{.Names}}\t{{.Status}}'
```

**No debe imprimir nada.** Si imprime algo, ya existe un contenedor con ese
nombre — aunque esté parado — y el `up -d` fallaría con
`Conflict. The container name "/copiloto-mcp" is already in use`. Si pasa,
para y averigua de quién es antes de borrar nada.

Segundo: el nombre tampoco puede estar ya tomado dentro de la red, así que la
salida del paso 2.3 **no debe contener** `copiloto-mcp` ni `copiloto-bd`. Si lo contuviera, n8n
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
| aparecen dos contenedores nuevos, `copiloto-mcp` y, desde SP3, su base `copiloto-bd` | los contenedores que ya corrían |
| aparecen dos imágenes: la nuestra, `copiloto-mcp:0.1.0` (~2 GB en disco), y, desde SP3, la de PostgreSQL de la base | las imágenes de los demás stacks |
| los dos contenedores se **unen** a la red externa de n8n, la que nombra `RED_N8N` | la red en sí: no se crea, ni se altera, ni se borra |
| — | los puertos del host: no se publica ninguno |
| aparece un volumen con nombre, `copiloto_bd_datos`, con la base del copiloto (desde SP3) | los volúmenes y los datos de los demás stacks |

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
  lectura** en el VPS, que es el apartado 3.2. Si el repositorio es privado,
  sin ella el `git pull` se cuelga pidiendo usuario.

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
| **Camino A: `git clone`** | el repositorio existe **y** el VPS tiene llave de despliegue | clona `main` y copia los pesos aparte |
| **Camino B: `git archive` + `tar`** | no hay remoto, o el VPS no tiene llave | empaqueta la rama y la copia por `scp` |

El camino A es el bueno si vas a redesplegar más de una vez, porque deja un
repositorio de verdad en `/opt/copiloto` y a partir de ahí actualizar es un
`git pull` (ver el redespliegue, al final del apartado 6). El camino B no deja
repositorio: cada actualización vuelve a ser un tar entero.

**Una cosa que el camino A necesita y el B no: credenciales en una máquina que
no es tuya.** Si el repositorio es privado, un `git pull` en el VPS se
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
| `<url-del-repositorio>` | `github-copiloto:<cuenta>/copiloto-triaje.git` — el repositorio, por el alias SSH del 3.2. Por HTTPS sería `https://github.com/<cuenta>/copiloto-triaje.git`, pero entonces, si el repositorio es privado, el VPS pide usuario en cada `pull` |
| `<cuenta>` | la cuenta u organización de GitHub dueña del repositorio |
| `<raiz-del-repositorio>` | la carpeta de tu máquina donde está tu clon del repositorio, entre comillas si lleva espacios |
| `<RSNA_RAIZ>` | la raíz del dataset de RSNA preparado, la de la variable `RSNA_RAIZ`: la carpeta con `crudo/` y `corridas/` dentro |

El prefijo `[VPS]` marca los comandos que van **dentro** de la sesión `ssh`. No
se escribe: es solo para que sepas en qué máquina estás en cada línea.

**Paso 1. Que los pesos estén en `servidor/` en tu máquina.** No se versionan,
así que se traen de la corrida que produjo el modelo:

```bash
cd <raiz-del-repositorio>
cp "<RSNA_RAIZ>/corridas/efficientnet_b0_320px_lote24_4+20ep/checkpoints/pesos_modelo_cpu.pt" \
   servidor/pesos_modelo_cpu.pt
sha256sum servidor/pesos_modelo_cpu.pt
```

Tiene que decir exactamente:

```
bb985e1f792e1cfee150ec57bdc6d706f7484499fa999da3406a5798260e8d47
```

Si no coincide, para aquí: estarías desplegando un modelo distinto del que esta
guía certifica. Apunta ese hash, lo vuelves a usar en el paso 5.

#### Camino A: clonar el repositorio

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
cd <raiz-del-repositorio>
scp servidor/pesos_modelo_cpu.pt usuario@vps:/opt/copiloto/servidor/
```

Y salta al **paso 5**, la comprobación del hash, que no sobra en ningún camino.

> **Lo que el clon deja en el disco del cliente.** El árbol completo son 5,3 MB,
> de los cuales 4 MB son `docs/eda/metadatos_eda.csv`: 26 685 filas de
> metadatos por paciente del concurso RSNA. No entra en la imagen —el
> `Dockerfile.dockerignore` es una lista blanca de lo que la imagen copia, y
> `docs/` no está en ella— pero sí queda en `/opt/copiloto`.
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

Con el alias puesto, la URL del clon es `github-copiloto:<cuenta>/copiloto-triaje.git`.
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
  red_n8n:
    external: true
    name: ${RED_N8N:?define RED_N8N con el nombre de la red externa de n8n}
```

**`RED_N8N` es obligatoria y no tiene valor por defecto.** El nombre de la red
es de la instalación donde corre n8n, no del repositorio. Si la variable falta
o está vacía, **cualquier** `docker compose` que lea este fichero —`build`,
`up`, `ps`, `exec`, `logs`, `stop`, `down`— aborta antes de hacer nada, con un
mensaje que termina así:

```
required variable RED_N8N is missing a value: define RED_N8N con el nombre de la red externa de n8n
```

Es el fallo seguro, igual que el de la contraseña de la base: mejor no arrancar
que arrancar unido a una red que no es.

### Dónde se declara `RED_N8N`

En **`servidor/.env`**, el fichero sin versionar que ya lleva la contraseña de
la base (la plantilla es `servidor/.env.ejemplo`). Compose lo lee solo, porque
está junto al `docker-compose.yml`: vale igual si lanzas la orden desde
`servidor/` que si la lanzas desde la raíz con
`-f servidor/docker-compose.yml`. Así **ningún comando de esta guía necesita
llevar la variable delante**, y no hay forma de olvidarla en uno.

Si `servidor/.env` no existe todavía, créalo copiando la plantilla
(`cp -n servidor/.env.ejemplo servidor/.env`; con `-n` no pisa uno que ya
exista, que lleva la contraseña) y pon en él la contraseña de la base. La
plantilla ya trae una línea `RED_N8N=` con un valor de ejemplo: **no
se añade otra, se sustituye su valor** por el nombre que apuntaste en el paso
2.2. Tiene que quedar una sola:

```
RED_N8N=<RED_N8N>
```

Y comprueba, sin levantar nada, que Compose ya la lee:

```bash
cd servidor
docker compose config --quiet && echo "el compose se deja leer"
```

`config` solo lee e interpola: no crea, no arranca y no toca ningún contenedor.
Si imprime un mensaje de `required variable`, mira qué variable nombra. Si es
`RED_N8N`, la línea no está en `.env`, está vacía, o el `.env` no está en
`servidor/`. Si es `COPILOTO_BD_PASSWORD`, lo que falta es la contraseña de la
base.

Una variable `RED_N8N` exportada en la sesión **manda sobre la de `.env`**. Es
lo que usa el caso B, y es también el motivo de no dejarla exportada en el VPS:
haz `unset RED_N8N` si la pusiste a mano.

### Caso A: en el VPS, donde n8n ya corre

**No se crea ni se toca nada.** La red ya existe y la posee la infraestructura
del cliente. Solo confirma que está y cómo se llama:

```bash
docker network ls
```

Ese nombre, tal cual, es el que va en `servidor/.env`. **No edites el
compose**: para eso está la variable.

Para averiguar con certeza en qué red está n8n, mírala desde su propio
contenedor en vez de adivinar por el nombre:

```bash
docker inspect <nombre-del-contenedor-de-n8n> --format '{{json .NetworkSettings.Networks}}'
```

### Caso B: en local, para probar el despliegue desde cero

Aquí n8n no corre (vive en el VPS), así que la red externa no existe: con el
nombre de la red real en `RED_N8N`, el compose fallaría con `network <RED_N8N>
declared as external, but could not be found`.

Créate una red **con un nombre de tirar**, y pásasela por `RED_N8N`,
exportándola para toda la sesión:

```bash
docker network create copiloto-local
export RED_N8N=copiloto-local
docker compose up -d
```

Y cuando acabes, primero baja el contenedor y luego borra **esa** red:

```bash
docker compose down
docker network rm copiloto-local
unset RED_N8N
```

El `export` no es un detalle: con `RED_N8N=copiloto-local` escrito solo delante
del `up`, el `docker compose down` de después ya no tendría la variable y
abortaría.

El nombre de tirar no es remilgo: es para que el nombre de la red de producción
**nunca aparezca en esta guía al lado de un `docker network rm`**. Si lo hiciera,
bastaría un copiar y pegar despistado en la sesión equivocada para dejar a n8n,
a nginx y a la API del cliente sin red común. Docker se niega a borrar una red
con contenedores conectados, pero no si en ese momento están parados, así que la
protección no es de fiar. Para eso está la variable.

Recuerda que si levantas con `RED_N8N=copiloto-local`, **todos** los comandos
posteriores que mencionen la red —el `docker run --network ...` del paso 6— usan
también `copiloto-local`: con el `export` hecho, lo hacen solos.

## 5. Construir la imagen

Todos los comandos de aquí en adelante se ejecutan **desde el directorio
`servidor/`**:

```bash
cd servidor
docker compose build
```

Tarda unos 2 minutos la primera vez; casi todo es la descarga de torch
(196,3 MB). La imagen resultante es `copiloto-mcp:0.1.0`.

El contexto de la construcción es la raíz del repositorio, y lo filtra
`servidor/Dockerfile.dockerignore`: desde SP5-B4, una **lista blanca** con solo lo
que copia el Dockerfile (`pyproject.toml`, los `.py` de `src/`, los pesos, el
calibrador y `arrancar.py`). Ni `pruebas/`, ni `n8n/`, ni un `.env` llegan al
demonio. Ese fichero lo lee BuildKit, que es el de `docker compose build`; con el
constructor antiguo se ignoraría y viajaría el repositorio entero.
`tests/test_servidor_docker.py` lo comprueba con BuildKit de verdad.

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
copiloto-mcp:0.1.0   <id>                  2GB          442MB
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
NAME           IMAGE                COMMAND                  SERVICE        STATUS
copiloto-bd    postgres:16-alpine   "docker-entrypoint.s…"   copiloto-bd    Up (healthy)
copiloto-mcp   copiloto-mcp:0.1.0   "python arrancar.py"     copiloto-mcp   Up (healthy)
```

Ahora pregúntale a la puerta de salud:

```bash
docker compose exec copiloto-mcp python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/salud')))"
```

Respuesta esperada:

```
{'estado': 'listo', 'modelo': 'efficientnet_b0_320px', 'umbral': 0.4258, 'calibrador': 'efficientnet_b0_320px_lote24_4+20ep', 'prevalencia_local': 0.1466}
```

### Comprobar que se alcanza por nombre de servicio

Esto es lo que hará n8n, y conviene verificarlo sin n8n de por medio. Levanta
un contenedor de usar y tirar en la misma red y pídele que resuelva el nombre:

```bash
export RED_N8N="$(sed -n 's/^RED_N8N=//p' .env | tail -n 1)"
docker run --rm --network "${RED_N8N:?define RED_N8N con el nombre de la red externa de n8n}" python:3.12-slim python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://copiloto-mcp:8000/salud')))"
unset RED_N8N
```

Es la **misma variable** con la que levantaste el compose, y por eso va aquí en
vez del nombre literal. Pero esta orden no la ejecuta Compose, la ejecuta tu
shell, y **el shell no lee `servidor/.env`**: la primera línea se la carga para
esta sesión y la última la retira. Si arrancaste con `RED_N8N=copiloto-local`
exportada (caso B del paso 4), sáltate esas dos líneas: el comando usa
`copiloto-local` solo. Y si la variable no está, el `:?` hace que el comando
aborte con el mismo mensaje que el compose en vez de probar suerte con otra
red. Un literal aquí obligaría a editarlo a mano cada vez y dejaría que
esta comprobación mirase una red distinta de la que se está usando —justo lo que
esta comprobación existe para descartar.

Los comandos de **solo lectura** del paso 2, como `docker network inspect`,
llevan el marcador `<RED_N8N>`, y eso es a propósito: ahí lo que se teclea, en
su lugar, es el nombre real que acabas de leer en `docker network ls`.

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
año— antes de que pase un solo paciente**. En un VPS compartido con los
contenedores ajenos, el disco que se llena no es solo tuyo.

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
camino A, es una sola orden. **Si la instalación se levantó antes de que
`RED_N8N` fuera obligatoria, la primera vez no es esta orden**, que traería el
código nuevo y abortaría: es el apartado «El primer redespliegue con `RED_N8N`
obligatoria», más abajo.

```bash
cd /opt/copiloto && git pull --ff-only && docker compose -f servidor/docker-compose.yml up -d --build copiloto-mcp && for i in $(seq 1 30); do e=$(docker inspect -f '{{.State.Health.Status}}' copiloto-mcp 2>/dev/null || echo ausente); [ "$e" = healthy ] && break; sleep 5; done && docker inspect -f '{{.State.Health.Status}}' copiloto-mcp && docker compose -f servidor/docker-compose.yml exec copiloto-mcp python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/salud')))"
```

Cinco cosas que esa línea tiene, o no tiene, por un motivo:

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
- **No lleva `RED_N8N` delante, y no le hace falta.** Compose la lee de
  `servidor/.env`, que está junto al compose aunque la orden se lance desde
  `/opt/copiloto` (paso 4). Si esa línea falta en el `.env`, la orden aborta en
  el primer `docker compose`, antes de reconstruir nada.

**Primero el servidor, después el bot.** Cuando un cambio toca los dos (como
SP4), se redespliega el servidor con esa línea y solo después se publican los
nodos de n8n. Con el orden al revés nada se rompe, pero todos los informes
dicen «SIN COMBINAR — el copiloto no devolvió la combinación en esta
respuesta.»: ese es el síntoma.

**Los pesos sobreviven al `git pull`.** Están en `.gitignore`, y ni `pull`, ni
`checkout`, ni `reset --hard` tocan un fichero ignorado y sin seguimiento. El
único comando que los destruye es `git clean -xfd`, que es justo el reflejo de
"dejar el repositorio limpio": no lo teclees en `/opt/copiloto`.

**Si reentrenaste el modelo**, los pesos nuevos van por `scp` como en el primer
despliegue, y hay que revisar que `UMBRAL` y `AUC_VALIDACION` del compose sigan
describiendo *esos* pesos:

```bash
cd /opt/copiloto && sha256sum servidor/pesos_modelo_cpu.pt && grep -nE 'UMBRAL|AUC_VALIDACION|PREVALENCIA_LOCAL' servidor/docker-compose.yml
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

### El primer redespliegue con `RED_N8N` obligatoria: volver a crear los contenedores

Hasta SP5 el compose traía escrito el nombre de la red, como valor por defecto
de `RED_N8N`. Desde que la variable es obligatoria, **la clave de la red
cambió en el compose** (ahora es `red_n8n`) y el nombre ya no viene en el
fichero. Una instalación levantada con el compose anterior necesita, **una
sola vez**, que los dos contenedores se vuelvan a crear. **No hace falta
bajarlos antes:** Compose ve que la configuración cambió y los recrea él, y lo
hace **después** de construir la imagen y de comprobar que la red existe. Si
algo de eso falla, los contenedores de antes siguen en marcha. La base de
datos **no se toca**: sus datos viven en el volumen `copiloto_bd_datos`, que
sobrevive a que el contenedor se recree.

Esto se ensayó el 28-sep-2026 con un proyecto de prueba de la misma forma (dos
servicios, una red externa, un volumen con nombre) y Compose v5.2.0: con la
variable ausente, con una errata en el nombre de la red y con una construcción
que falla, `up` se detiene **sin tocar** los contenedores que había; con todo
bien, los recrea, y el volumen es el mismo y conserva sus datos. También se
ensayaron la vuelta atrás y la copia de la base; y su restauración, el 29-sep,
sobre una base con el esquema del proyecto que había cambiado después de la
copia: vuelve a lo copiado, y si se interrumpe a medias la base se queda como
estaba. **No se ha ensayado en el servidor**, donde la versión de Compose
puede ser otra: por eso los puntos 1 y 3 apuntan de dónde se parte y guardan
una copia, y al final está escrito cómo volver.

Es para una instalación que es un clon de git (el camino A del paso 3.1), y
**no cubre el camino B**: las órdenes de los puntos 1 y 4 y la vuelta atrás
son de git, y pegadas en un árbol que no es un clon se cortan sin hacer nada.
Para el camino B no hay procedimiento escrito ni ensayado: no lo improvises
sobre este.

Mientras Compose recrea los contenedores y el copiloto vuelve a estar
`healthy` —alrededor de un minuto— n8n no alcanza ni al copiloto ni a la base:
los bots contestan con su mensaje de error. Hazlo cuando no haya consultas en
curso.

**1. Apuntar de dónde se parte y guardar el `.env`.** Primero, que el código
nuevo no esté ya traído:

```bash
grep -c 'RED_N8N:?' /opt/copiloto/servidor/docker-compose.yml
```

Tiene que dar `0`: el compose del disco es el anterior, y el commit de ahora
es al que se vuelve. **Si da `1`, el código nuevo ya está en el disco** —se
lanzó antes el redespliegue de siempre, o este es un segundo intento— y el
commit de vuelta **no es el de ahora**: es el que apuntaste la primera vez. Si
no lo apuntaste, es el que tenía `main` antes del `pull`, y lo dice esta
orden (ensayada: lo da aunque después se haya cambiado de commit a mano):

```bash
git -C /opt/copiloto rev-parse 'main@{1}'
```

Da el commit de antes del ÚLTIMO `pull`. Comprueba que es el bueno, cambiando
`<commit>` por el que ha salido: su compose no tiene que llevar la variable
obligatoria.

```bash
git -C /opt/copiloto cat-file -e '<commit>:servidor/docker-compose.yml' && git -C /opt/copiloto show '<commit>:servidor/docker-compose.yml' | grep -c 'RED_N8N:?'
```

Tiene que dar `0`. Si en vez de un número sale un `fatal:`, el commit está mal
copiado (o sigue puesto el marcador): cópialo otra vez. Si da `1`, desde el
compose anterior se ha hecho más de un
`pull`: repite las dos órdenes con `'main@{2}'`, y así hasta que dé `0`.

Sigue con este punto, pero no apuntes el commit que imprime su orden.

El `.env` es el fichero que tiene la contraseña de la base: se guarda una
copia **fuera** del repositorio antes de tocarlo. Y una `RED_N8N` exportada
en la sesión manda sobre la del `.env`, así que se retira:

```bash
cd /opt/copiloto && unset RED_N8N && git rev-parse HEAD && cp -p servidor/.env ~/copiloto.env.antes-de-red_n8n && echo "copia hecha"
```

Apunta el commit que imprime (si el `grep` dio `0`): es al que se vuelve si
algo sale mal.

**2. Declarar la variable, antes del `git pull`.** El nombre es el de la red
donde está hoy el contenedor; pregúntaselo a él:

```bash
docker inspect copiloto-mcp --format '{{range $red, $c := .NetworkSettings.Networks}}{{println $red}}{{end}}'
```

Tiene que salir **un solo nombre**. Si salen dos, para: la de `RED_N8N` es
la que el contenedor comparte con n8n (la del paso 2.3); la otra no está en
el compose y el contenedor la pierde al recrearse, así que averigua quién la
conectó y para qué antes de seguir. Mira ahora si la variable ya está en el
`.env`:

```bash
grep -c '^RED_N8N=' /opt/copiloto/servidor/.env
```

Si da `1`, ya está declarada: **no añadas nada**, y pasa a comprobar, más
abajo, que su valor es ese nombre. Si da `0`, añádela al final del `.env` con
esta orden, cambiando `<RED_N8N>` por el nombre. Lleva `>>`, que añade; con
un solo `>` se borraría el fichero, contraseña incluida:

```bash
printf '\nRED_N8N=%s\n' '<RED_N8N>' >> /opt/copiloto/servidor/.env
```

Comprueba que quedó, una sola vez y con el nombre de la red, y que la
contraseña sigue ahí:

```bash
grep -c '^RED_N8N=.' /opt/copiloto/servidor/.env; grep -c '^COPILOTO_BD_PASSWORD=.' /opt/copiloto/servidor/.env; grep '^RED_N8N=' /opt/copiloto/servidor/.env
```

Esperado: `1`, `1` y la línea `RED_N8N=` con el nombre que dio el `docker
inspect`. **Si no sale eso** y la línea la acabas de añadir tú —quedó dos
veces, lleva todavía el marcador, o falta la contraseña—, no repitas el
`printf` encima: restaura la copia y vuelve a empezar este punto.

```bash
cp -p ~/copiloto.env.antes-de-red_n8n /opt/copiloto/servidor/.env
```

Si la línea **ya estaba** antes de empezar —vacía, con otro nombre o
repetida—, restaurar la copia te devuelve el mismo fichero. Esa se corrige a
mano, con un editor (`nano /opt/copiloto/servidor/.env`): una sola línea
`RED_N8N=` con el nombre que dio el `docker inspect`. Después, la misma
comprobación.

**3. Apuntar cómo están la base y los contenedores, y sacar una copia de la
base.** Primero lo que se va a comparar al final: cuándo se creó el volumen,
cuántas consultas guarda la base y cuándo se crearon los dos contenedores.

```bash
docker volume inspect "$(docker inspect copiloto-bd --format '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{end}}{{end}}')" --format 'volumen creado: {{.CreatedAt}}'
docker exec copiloto-bd psql -U copiloto -d copiloto -tAc 'select count(*) from consultas'
docker inspect copiloto-mcp copiloto-bd --format '{{.Name}} creado: {{.Created}}'
```

Y la copia, que es con lo que se repara la base si al final no es la que
había. Se queda fuera del repositorio y solo la puede leer quien la hace:

```bash
(umask 077; set -o pipefail; docker exec copiloto-bd pg_dump --clean --if-exists -U copiloto -d copiloto | gzip > ~/copiloto-bd.antes-de-red_n8n.sql.gz) && gunzip -t ~/copiloto-bd.antes-de-red_n8n.sql.gz && ls -l ~/copiloto-bd.antes-de-red_n8n.sql.gz
```

Tiene que terminar enseñando el fichero. Si en su lugar sale un error de
`pg_dump` o de `gunzip` (que comprueba que la copia está entera), no hay
copia: no sigas. Y si entre este punto y el 5 pasa un rato
en el que los bots han atendido consultas, repite este punto antes de
redesplegar: la copia que sirve es la de justo antes.

**4. Traer el código y comprobar, sin levantar nada,** que el compose nuevo se
deja leer y que la red que dice el `.env` existe:

```bash
cd /opt/copiloto && git pull --ff-only && docker compose -f servidor/docker-compose.yml config --quiet && docker network inspect "$(sed -n 's/^RED_N8N=//p' servidor/.env)" --format 'la red existe: {{.Name}}'
```

Tiene que terminar con `la red existe:` y el nombre del punto 2. **Si no
termina así, sea cual sea el error, no sigas:** hasta aquí no se ha tocado
ningún contenedor y el servicio sigue como estaba. Si el mensaje es `required
variable RED_N8N is missing a value`, vuelve al punto 2.

**5. Redesplegar.** Es la orden de siempre, pero **sin nombrar el servicio**,
para que Compose recree los dos contenedores, y esperando a los dos:

```bash
cd /opt/copiloto && docker compose -f servidor/docker-compose.yml up -d --build && for c in copiloto-bd copiloto-mcp; do for i in $(seq 1 30); do e=$(docker inspect -f '{{.State.Health.Status}}' $c 2>/dev/null || echo ausente); [ "$e" = healthy ] && break; sleep 5; done; echo "$c: $e"; done
```

Primero construye la imagen —minutos, con el servicio todavía en marcha— y
después recrea. Lo que Compose va pintando mientras tanto depende de la
terminal (líneas sueltas, o una lista que se actualiza en su sitio): no te
guíes por eso. Lo que cuenta es cómo termina, `copiloto-bd: healthy` y
`copiloto-mcp: healthy`, y el punto 6. Si la conexión con el servidor se
corta a medias, vuelve a entrar y repite la orden: si Compose ya había
terminado, no cambia nada; si no, acaba lo que faltaba.

**6. Comprobar**, con las mismas órdenes del punto 3 y una más:

```bash
docker inspect copiloto-mcp copiloto-bd --format '{{.Name}} creado: {{.Created}}'
docker volume inspect "$(docker inspect copiloto-bd --format '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{end}}{{end}}')" --format 'volumen creado: {{.CreatedAt}}'
docker exec copiloto-bd psql -U copiloto -d copiloto -tAc 'select count(*) from consultas'
docker inspect copiloto-mcp copiloto-bd --format '{{.Name}}: {{range $red, $c := .NetworkSettings.Networks}}{{$red}} {{end}}'
```

- los dos contenedores tienen una fecha de creación **posterior** a la del
  punto 3: Compose los recreó;
- el volumen tiene **la misma** fecha de creación que en el punto 3;
- la base guarda, como poco, las mismas consultas;
- los dos contenedores están en la red del punto 2.

Si todo cuadra, termina con la sonda de salud del paso 6 y con una consulta de
prueba por el bot.

**Si algo falla.**

- **La orden del punto 5 termina con un error y los dos contenedores
  conservan la fecha de creación del punto 3** (la construcción, la red): no
  se ha tocado nada y el servicio sigue con los contenedores de antes. Se
  corrige la causa y se repite desde el punto 4.
- **Los contenedores se recrearon y alguno no llega a `healthy`, o llegan
  los dos pero quedan en otra red que la del punto 2:** mira por qué, con
  `docker logs --tail 50 copiloto-mcp` o `docker logs --tail 50
  copiloto-bd`. Para volver a la versión anterior se restaura **antes** el
  `.env` —el compose anterior también lee `RED_N8N`, y con el `.env` de antes
  vuelve a la red en la que estaba— y se levanta el commit del punto 1:

  ```bash
  cd /opt/copiloto && cp -p ~/copiloto.env.antes-de-red_n8n servidor/.env && git checkout --detach <commit del punto 1> && docker compose -f servidor/docker-compose.yml up -d --build && for c in copiloto-bd copiloto-mcp; do for i in $(seq 1 30); do e=$(docker inspect -f '{{.State.Health.Status}}' $c 2>/dev/null || echo ausente); [ "$e" = healthy ] && break; sleep 5; done; echo "$c: $e"; done
  ```

  Después, las comprobaciones del punto 6. Para volver a intentarlo otro día:
  `git switch main`, y otra vez desde el punto 1. El commit de vuelta sigue
  siendo el que apuntaste la primera vez: tras el `git switch main` el de
  ahora ya es el nuevo, y el `grep` del punto 1 lo avisa.
- **`up` se niega a recrear y pide bajar antes el proyecto** (una versión
  antigua de Compose puede hacerlo cuando cambia la clave de la red):
  entonces sí, y en este orden, para que el servicio esté caído lo menos
  posible: construir, bajar **por nombre de proyecto y sin `-v` ni
  `--volumes`** —con cualquiera de los dos se borra la base—, levantar y
  esperar:

  ```bash
  cd /opt/copiloto && docker compose -f servidor/docker-compose.yml build && docker compose -p copiloto-mcp down && docker compose -f servidor/docker-compose.yml up -d && for c in copiloto-bd copiloto-mcp; do for i in $(seq 1 30); do e=$(docker inspect -f '{{.State.Health.Status}}' $c 2>/dev/null || echo ausente); [ "$e" = healthy ] && break; sleep 5; done; echo "$c: $e"; done
  ```

  El `down` nombra solo a `copiloto-mcp` y a `copiloto-bd`; si nombra
  cualquier otro contenedor, `Ctrl+C`. Después, las comprobaciones del punto 6.
- **El volumen tiene otra fecha de creación, o la base guarda menos
  consultas:** la base no es la que había. Para, y no sigas operando sobre
  ella. Si el volumen es otro, el de antes sigue en el disco (`docker volume
  ls`): **no lo borres**, que es donde están los datos. La copia del punto 3
  devuelve la base a como estaba, en una sola transacción —si una sentencia
  falla, la base se queda como estaba antes de empezar—, y antes comprueba
  que la copia está entera, porque una copia cortada no daría ningún error y
  dejaría la base a medias:

  ```bash
  gunzip -t ~/copiloto-bd.antes-de-red_n8n.sql.gz && gunzip -c ~/copiloto-bd.antes-de-red_n8n.sql.gz | docker exec -i copiloto-bd psql -U copiloto -d copiloto -q -1 -v ON_ERROR_STOP=1 && docker exec copiloto-bd psql -U copiloto -d copiloto -tAc 'select count(*) from consultas'
  ```

  Tiene que terminar con el recuento del punto 3. Lo que se haya escrito en
  la base después del punto 3 no está en la copia, y se pierde.

Las dos copias —la del `.env`, que lleva la contraseña, y la de la base, que
lleva las consultas— se borran cuando todo esté comprobado, y también si se
abandona el redespliegue:

```bash
rm -f ~/copiloto.env.antes-de-red_n8n ~/copiloto-bd.antes-de-red_n8n.sql.gz
```

A partir de aquí los redespliegues vuelven a ser la orden de una línea de
arriba.

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
encima los 23 contenedores ajenos compitiendo por la CPU. Los dos núcleos que
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
  "auc_validacion": 0.8827,
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
| `dicom_invalido` | los bytes no son un DICOM legible, o la placa no se puede evaluar (abajo) | 422 | `isError: true` |
| `payload_excesivo` | más de 5 MB (5 242 880 bytes) descodificados | 413 | `isError: true` |
| `base64_invalido` | el `dicom_base64` no es base64 válido | — | `isError: true` |

Comprobado en el contenedor con una placa de un paciente de 12 años; las dos
puertas dicen lo mismo:

```
REST: (422, {'codigo': 'fuera_de_alcance', 'detalle': 'El paciente tiene 12 años y el modelo solo es válido entre 18 y 100.'})
MCP : {"result":{"content":[{"text":"Error executing tool clasificar_radiografia: fuera_de_alcance: El paciente tiene 12 anios ...","type":"text"}],"isError":true}}
```

Que el modelo **se niegue** a opinar sobre un menor es comportamiento
deseado, no un fallo del despliegue: los pesos se entrenaron y se validaron
sobre adultos.

### Las placas que no se evalúan (SP5-B4)

Antes de descodificar un solo píxel, el servidor mira la metainformación y la
cabecera del DICOM y **no evalúa** la placa que el modelo vería mal o que no cabe
en memoria. La regla está en un solo sitio, `comprobar_que_se_puede_evaluar` de
`src/copiloto_triaje/datos/dicom.py`, y la interfaz de demostración usa la misma.
Todas salen con `dicom_invalido`:

| Lo que trae el fichero | Por qué no se evalúa |
| :--- | :--- |
| sin la metainformación de un DICOM (el preámbulo con `DICM` y el grupo 0002), o con una sintaxis de transferencia que no se conoce | no se sabe cómo leerlo |
| la sintaxis Deflated: todo el conjunto de datos comprimido con zlib | leer siquiera su cabecera lo infla entero (unos cientos de KiB pueden ser cientos de MiB) |
| más o menos de 8 bits, o con signo | el modelo se entrenó con placas de 8 bits sin signo, las de RSNA: una de 16 bits la vería saturada, casi blanca, y daría una cifra que no vale |
| `MONOCHROME1`, la escala de grises invertida | la vería al revés |
| en color: otra fotometría que `MONOCHROME2`, o más de una muestra por píxel | se entrenó con placas en grises |
| más de un cuadro | evalúa una placa sola, y todos los cuadros se reservarían en memoria |
| más de 5 000 píxeles de lado | ninguna placa de tórax digital llega (rondan 4 300 × 4 300): unos 600 bytes que declaraban 60 000 × 60 000 hacían reservar 3,4 GiB y el contenedor moría |
| una cabecera sin alguno de los campos que dicen cómo leer la imagen, o con uno vacío | pydicom no la sabría descodificar |
| comprimido con una sintaxis que el servidor no sabe descomprimir: JPEG-LS, JPEG Lossless, HTJ2K… (sin su plugin), o JPEG 2000 Parte 2 | no se puede leer la placa (hasta SP5-B4, un 500). Sí se leen las sin comprimir, RLE, JPEG Baseline y Extended y JPEG 2000 |
| la cabecera pero no la imagen: un fichero recortado | no hay placa que leer (hasta SP5-B4 salía sin código: un 500 por REST) |

La cabecera se mira dos veces: leída hasta el Pixel Data, antes de leer el fichero
entero, y otra vez sobre el fichero entero, antes de descodificar, porque en un DICOM
no conforme un campo de la imagen repetido detrás del Pixel Data gana en la lectura
entera, que es de la que sale la imagen.

El detalle es un texto nuestro, sin nada de pydicom ni del fichero salvo enteros
de la cabecera, por ejemplo:

```
dicom_invalido: La placa no se puede evaluar: es de 16 bits, y el modelo solo evalúa placas de 8 bits sin signo, como las de RSNA con las que se entrenó.
```

Los demás fallos de lectura, los que la regla no cubre (por ejemplo `Rows` a 0, un
`BitsStored` mayor que `BitsAllocated` o un píxel sin comprimir recortado), siguen
saliendo como hasta ahora: `dicom_invalido` con el texto de pydicom en el detalle
(`El fichero no es un DICOM legible: …`), que el bot tampoco relata.

**El profesional no lo ve.** Ante `dicom_invalido` el bot dice «No pude leer esa
radiografía.» y «Sigo esperando el archivo.», no relata el detalle —va a
`consultas.error`— y espera otro fichero. Las 26 684 placas de RSNA pasan la
regla.

La sesión con el médico (la imagen `h7-sesion`) se grabó ANTES de este cambio: su
perfil 08, el fichero recortado, lleva la pista del bot «Si lo recortó al enviarlo,
vuelva a exportarlo completo», que daba cuando el servidor caía sin código. Con este
cambio desplegado, el bot contesta a ese caso solo «No pude leer esa radiografía.»
(y «Sigo esperando el archivo.»).

## 10. Variables de entorno

Se declaran en el `docker-compose.yml`. Solo hay que tocarlas si se reentrena
el modelo o hay un dato local de prevalencia (SP4). Las dos variables del
umbral por vista no están en el compose: se añaden solo si la institución
decide encenderlo.

| Variable | Valor por defecto | Qué es |
| :--- | :--- | :--- |
| `UMBRAL` | `0.4258` | punto de operación; el de especificidad 0,70 y recall 0,8815 |
| `AUC_VALIDACION` | **ninguno: es obligatoria** (el compose la pone a `0.8827`) | AUC en validación, **se le muestra al profesional** en cada respuesta |
| `PREVALENCIA_LOCAL` | **ninguno: es obligatoria** (el compose la pone a `0.1466`) | probabilidad previa de la combinación bayesiana (SP4 §5): 134/914, la cohorte de derivación de Heckerling. **Se le muestra al profesional** en cada informe con combinación. Se cambia aquí, con su fuente, cuando haya dato del entorno real |
| `UMBRAL_PA` | **ninguno: apagado si no se definen** (el compose no las define) | umbral de la etiqueta del cribado para las placas cuya cabecera DICOM dice vista **PA**. Va **junto con `UMBRAL_AP`**: las dos o ninguna. Ejemplo: `0.1798`, el del workshop S4 (elegido en validación, tabla 3) |
| `UMBRAL_AP` | **ninguno: apagado si no se definen** (el compose no las define) | lo mismo para las placas de vista **AP**. Ejemplo: `0.5815`, el del workshop S4 (elegido en validación, tabla 3) |
| `RUTA_PESOS` | `/modelo/pesos_modelo_cpu.pt` | dentro de la imagen |
| `RUTA_CALIBRADOR` | `/modelo/calibrador.json` | dentro de la imagen |
| `OMP_NUM_THREADS` | `2` | hilos que usa torch. **Tiene que valer lo mismo que `cpus`** del bloque de límites: torch no lee el cgroup y sin esto abriría un hilo por núcleo del host |
| `RED_N8N` | **ninguno: es obligatoria** | nombre de la red externa de n8n. Se declara en `servidor/.env` (paso 4), no se edita el compose. Sin ella, cualquier `docker compose` aborta |

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

`PREVALENCIA_LOCAL` sigue la misma regla y por la misma razón. Y `/salud` la
publica (`"prevalencia_local": 0.1466`): es la forma de saber, desde fuera, que
el contenedor que responde ya es el de SP4.

`UMBRAL_PA` y `UMBRAL_AP` son lo contrario: el **umbral por vista** (SP5-C1 §4),
una mitigación de equidad que queda **apagada** mientras no se definan, y el
`docker-compose.yml` no las define. Encenderla lo decide la institución, con sus
valores a la vista. Con las dos, la etiqueta del cribado (`clasificacion`) usa el
umbral de la vista que dice la cabecera DICOM (`PA` o `AP`, sin espacios ni
minúsculas) y el global `UMBRAL` si la vista es otra o no viene. La respuesta lo
dice: `umbral` pasa a ser el **aplicado** y aparece `umbral_por_vista`
(`{"vista": "PA", "aplicado": true}`, o `{"vista": null, "aplicado": false}` si
se usó el global). **La razón de verosimilitud y la combinación no cambian**: el
umbral solo decide la etiqueta. Sin las variables, la respuesta es la de siempre,
clave por clave. Con una sola de las dos, o con un valor fuera de (0, 1),
`arrancar.py` se niega a arrancar y dice cuál.

`/salud` también lo publica, pero **solo encendido**
(`"umbrales_por_vista": {"PA": 0.1798, "AP": 0.5815}`, los valores con los que
arrancó): apagado, `/salud` es el de siempre, y que la clave esté o no es la
forma de saber, desde fuera, si la etiqueta del cribado depende de la vista.
**Encenderlo cambia el contrato con el bot del profesional**: la respuesta de
`clasificar_radiografia` lleva una clave más, `umbral_por_vista` (en singular: no
es la clave de `/salud`), así que las dos pruebas de `tests/test_contrato_sp4.py`
que comparan el conjunto de claves fallan contra un contenedor así —a propósito:
el contrato ya no es el de SP4—, y el nodo «Desenlace» del bot no dice de dónde
sale el umbral. Con el umbral de AP (0,5815) por encima del global, una placa AP
puede salir «sin opacidad probable» con una razón de verosimilitud mayor que 1
(con el calibrador desplegado, pasa de 1 a partir de una puntuación cruda de
0,5786 y llega a 1,16 en 0,5815): la imagen sube la probabilidad y la etiqueta
dice lo contrario, un caso que «Desenlace» da por imposible. Por eso, **antes de
encenderlo en el servidor del bot hay que revisar «Desenlace»**.

## 11. Cuando algo va mal

| Síntoma | Causa | Arreglo |
| :--- | :--- | :--- |
| `required variable RED_N8N is missing a value: define RED_N8N con el nombre de la red externa de n8n`, en **cualquier** `docker compose` | falta `RED_N8N` o está vacía: no está en `servidor/.env`, o el `.env` no está junto al compose | poner el nombre real en la línea `RED_N8N=` de `servidor/.env`, que tiene que ser una sola (paso 4). No tiene valor por defecto, a propósito. **Si el mensaje sale al redesplegar una instalación anterior a esta variable**, no repitas después la orden de una línea: el primer redespliegue es el del apartado «El primer redespliegue con `RED_N8N` obligatoria», que antes guarda una copia de la base |
| `network <RED_N8N> declared as external, but could not be found` | el valor de `RED_N8N` no es el nombre de ninguna red que exista | **primero**: averigua el nombre real con `docker network ls` y corrige `RED_N8N` en `servidor/.env`. Ver el recuadro de abajo |
| `"/servidor/pesos_modelo_cpu.pt": not found` al construir | no copiaste los pesos | ver el paso 3 |
| `Conflict. The container name "/copiloto-mcp" is already in use` (o `"/copiloto-bd"`) | ya hay un contenedor con ese nombre | el paso 2.4 lo detecta antes. Averigua de quién es con `docker ps -a --filter name=copiloto-mcp` (o `name=copiloto-bd`) **antes** de borrarlo |
| `no space left on device` al construir | disco lleno | el paso 2.6 lo detecta antes. Libera espacio; no uses `docker system prune -a` en el VPS (paso 12) |
| HTTP **421 "Invalid Host header"** | el transporte MCP valida la cabecera `Host` y por defecto solo acepta `127.0.0.1` | ya está resuelto: la aplicación se construye con `direccion_de_escucha="0.0.0.0"`. Si reaparece, alguien cambió ese valor |
| n8n da `ECONNREFUSED` o `Name or service not known` | n8n y el copiloto no están en la misma red | comprobar con el `docker run --rm --network ...` del paso 6 |
| el estado se queda en `starting` | aún está cargando los pesos | esperar; son ~10 s, con 40 s de gracia |
| el estado pasa a `unhealthy` | el proceso murió al arrancar | `docker compose logs copiloto-mcp` |
| `can't open file '/app/C:/Program Files/Git/modelo/...'` | Git Bash convirtió la ruta | `MSYS_NO_PATHCONV=1` delante del comando |
| `curl http://localhost:8000/salud` desde el host no responde | **es lo correcto**: no hay `ports` publicados | usar `docker compose exec`, o un contenedor en la misma red |
| el `git pull` del VPS se queda colgado sin decir nada | está esperando usuario y contraseña: el repositorio es privado, o la URL del remoto no es la de tu repositorio | la llave de despliegue del paso 3.2 (o corregir la URL). **No** metas un token en la URL |
| desplegaste, el `git pull` trajo cambios, y el servicio sigue comportándose igual que antes | se levantó **sin `--build`**: el tag `copiloto-mcp:0.1.0` es fijo, Compose vio la imagen y no reconstruyó | `up -d --build`. No da ningún error, por eso hay que saberlo |
| `untracked working tree files would be overwritten by merge` al hacer `git pull` | desplegaste antes por el camino B y ahora el repositorio trae un fichero que ya existía suelto | borra el fichero suelto que nombre el error y repite el `pull` |

### La red no aparece: NO la crees en el VPS

Este es el error que más tienta a hacer lo peor, así que va aparte.

Cuando el compose dice que la red externa no existe, la reacción natural es
crearla. **En el VPS eso es justo lo que no hay que hacer.** Si la red real se
llama de otra forma, un `docker network create` con el nombre que pusiste en
`RED_N8N` te deja una red vacía, el contenedor arranca, el estado dice
`healthy`, todo parece bien — y n8n no lo alcanza nunca, porque están en redes
distintas. Es el fallo silencioso que el paso 2.2 existe para evitar, y lo
habrías provocado tú.

El orden correcto es siempre este:

```bash
# 1. cual es la red real
docker network ls

# 2. si n8n no se deja adivinar por el nombre, preguntaselo
docker inspect <nombre-del-contenedor-de-n8n> --format '{{range $red, $c := .NetworkSettings.Networks}}{{println $red}}{{end}}'

# 3. corregir RED_N8N en servidor/.env con el nombre real, sin editar el
#    compose, y arrancar
docker compose up -d
```

`docker network create` solo tiene sentido **en local**, con un nombre de tirar,
y está en el Caso B del paso 4. **Nunca en el VPS**: allí la red la posee la
infraestructura del cliente y ya existe.

Los logs, siempre:

```bash
docker compose logs -f copiloto-mcp
```

## 12. Vuelta atrás: bajar solo este servicio

Todo lo que hay que deshacer son dos contenedores: `copiloto-mcp` y, desde
SP3, su base `copiloto-bd`. No hay migraciones ni configuración del sistema
que revertir. El volumen de la base, `copiloto_bd_datos`, se queda donde está:
bajar el servicio no lo borra.

### Bajarlo

Antes de bajar nada, confirma qué proyecto vas a tocar. El compose declara
`name: copiloto-mcp`, así que el proyecto se identifica solo y no depende de
cómo se llame la carpeta:

```bash
docker compose ls
```

```
NAME           STATUS       CONFIG FILES
copiloto-mcp   running(2)   /opt/copiloto/servidor/docker-compose.yml
```

`running(2)`: los dos contenedores del proyecto. Si ves cualquier otro proyecto
en esa línea, no es el nuestro.

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

Y no teclees nunca `-v` ni `--volumes` en ese `down`. **Aquí no es
inofensivo**: desde SP3 el proyecto tiene un volumen, `copiloto_bd_datos`, y
con ese flag se borra la base de datos del copiloto. Aplicado al stack de al
lado, borra los datos del cliente.

Salida (el orden entre los dos contenedores puede variar):

```
 Container copiloto-mcp Stopping
 Container copiloto-mcp Stopped
 Container copiloto-mcp Removing
 Container copiloto-mcp Removed
 Container copiloto-bd Stopping
 Container copiloto-bd Stopped
 Container copiloto-bd Removing
 Container copiloto-bd Removed
```

Ocho líneas, cuatro sobre `copiloto-mcp` y cuatro sobre `copiloto-bd`. Según
la terminal, Compose las pinta así, sueltas, o como una lista que se actualiza
en su sitio; en los dos casos nombra solo a esos dos contenedores. Si aparece
el nombre de cualquier otro, para: `Ctrl+C` y vuelve al `docker compose ls`.

`docker compose down` **no borra la red externa.** Comprobado: después del
`down`, `docker network ls` sigue mostrando la red de `RED_N8N` intacta, con
n8n dentro. Compose no borra lo que no creó.

### Comprobar que no se rompió nada más

```bash
docker ps --format '{{.Names}}' | sort > /tmp/contenedores-despues.txt
diff /tmp/contenedores-antes.txt /tmp/contenedores-despues.txt
```

Si `diff` no imprime nada, la máquina está exactamente como la encontraste. (Si
lo corres con el copiloto aún arriba, las únicas diferencias deben ser dos
líneas, `> copiloto-bd` y `> copiloto-mcp`, y ninguna más.)

Y que n8n sigue vivo:

```bash
docker ps --filter name=n8n --format '{{.Names}}\t{{.Status}}'
```

### Pararlo sin borrarlo

Si solo quieres silenciarlo un rato y volver luego sin reconstruir:

```bash
docker compose -p copiloto-mcp stop     # se para, se queda creado
docker compose -p copiloto-mcp start    # vuelve en ~10 s
```

Por nombre de proyecto, como el `down`: así da igual en qué carpeta estés.

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
| `docker network rm <RED_N8N>` | dejaría a n8n, a nginx y a la API del cliente sin red común. Esa red **no es nuestra** |
| `docker system prune -a` | borraría imágenes de los demás stacks, no solo la nuestra |
| `docker compose down` desde otro directorio | bajaría el stack de ese directorio, que puede ser el de producción |

Añadir `-v` / `--volumes` al `down` **tampoco es inofensivo aquí**: borra el
volumen `copiloto_bd_datos`, que es la base del copiloto. Y en el stack de al
lado ese mismo flag borra la base de datos del cliente.

### Volver a levantarlo

```bash
cd /opt/copiloto && docker compose -f servidor/docker-compose.yml up -d
```

Los pesos y el calibrador viajan dentro de la imagen y la base conserva sus
datos en el volumen, así que no se pierde nada, y el servicio vuelve a estar
`healthy` en unos 30 segundos.
