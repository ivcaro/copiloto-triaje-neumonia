# SP3 — Bot de Telegram orquestado en n8n

**Hito:** H5, vence el 2-oct-2026.
**Depende de:** SP2, desplegado y verificado en el VPS el 24-sep-2026.
**Entrega a:** SP4 (H6, 9-oct), que añade la regla clínica y la combinación
bayesiana sobre los datos que este sub-proyecto recoge.

---

## 1. Qué construye SP3, y qué no

Construye el flujo conversacional completo de los **dos roles** y lo conecta al
copiloto ya desplegado:

- un bot para el **paciente**, que responde un cuestionario de síntomas y recibe
  un **código seudónimo**;
- un bot para el **profesional**, que presenta ese código, aporta los **signos**
  de la exploración y una **radiografía DICOM**, y recibe lo que dice el modelo;
- la base de datos que sostiene ambos;
- la orquestación, en n8n.

**No construye** la regla clínica de Heckerling, ni la probabilidad previa, ni
la combinación bayesiana. Los síntomas y los signos se **recogen y se guardan**,
pero en SP3 el profesional los ve **al lado** del resultado de la imagen, nunca
mezclados con él. Unirlos es H6.

**No lleva LLM.** Ninguna pieza de SP3 llama a un modelo de lenguaje. Esto es un
cambio respecto al documento entregado en la Semana 1 y se justifica en §3.4.

---

## 2. Decisiones tomadas, y por qué

| # | Decisión | Razón |
| :-- | :--- | :--- |
| D1 | **Dos bots de Telegram separados** | Un paciente no puede recibir el pre-informe aunque falle una condición: su bot no tiene ese camino. La separación clínica deja de depender de que un `if` esté bien escrito |
| D2 | **PostgreSQL propia**, contenedor nuestro | Los datos clínicos quedan en infraestructura que controlamos, con su ciclo de vida, su respaldo y su borrado. Las cuatro PostgreSQL del VPS son del cliente y no se tocan |
| D3 | **SP3 sin la matemática** | H5 entrega algo demostrable de punta a punta; H6 añade la fórmula sobre datos que ya están recogidos, sin volver a tocar los bots |
| D4 | **Cuestionario por botones**, texto libre solo opcional y fuera del cálculo | Un extractor probabilístico en la ENTRADA de un cálculo clínico no falla con un error: produce una probabilidad previa equivocada que nadie ve |
| D5 | **DICOM como documento de Telegram** | El servidor solo acepta DICOM: la edad sale de la cabecera y el preprocesamiento debe ser el del entrenamiento. Telegram recomprime a JPEG lo enviado como *foto* |
| D6 | **Lista blanca de `chat_id`** | Un bot de Telegram es descubrible por su nombre de usuario. Sin puerta, D1 protege del error pero no del curioso |
| D7 | **Toda la lógica en n8n** (enfoque A) | Decisión del responsable del proyecto. Menos piezas y más rápido para el 2-oct. El coste real y su mitigación están en §9 |
| D8 | **Se llama a `/mcp`, no a `/inferir`** | Las dos puertas son el mismo servidor y el mismo modelo, pero hablar JSON-RPC con la herramienta `clasificar_radiografia` es la integración que el proyecto promete, y es la puerta que SP4 va a consumir: ejercitarla ahora adelanta las sorpresas del protocolo |
| D9 | **Bots NUEVOS de BotFather** | Un token de Telegram admite UN solo webhook. Reutilizar una credencial existente le robaría el webhook a un bot del cliente y lo dejaría mudo, sin error visible |
| D10 | **Dashboard después de H5**, con contraseña | No compite con los bots en la semana del hito, y se construye sabiendo qué métricas importan en vez de adivinarlas |

---

## 3. Arquitectura

### 3.1. Piezas

| Pieza | Qué es | Nueva |
| :--- | :--- | :--- |
| `copiloto-mcp` | inferencia, ya desplegado | no, **no se toca** |
| `copiloto-bd` | PostgreSQL, sin puertos publicados, en `[retirado]_[retirado]_network` | sí |
| `🩺 Copiloto Triaje: Paciente (Telegram)` | workflow de n8n | sí |
| `🩺 Copiloto Triaje: Profesional (Telegram)` | workflow de n8n | sí |
| `⚙️ Sub: Limpieza de cuestionarios caducados` | workflow de n8n, disparador programado | sí |
| Dos bots de Telegram | dos tokens nuevos, dos credenciales nuevas | sí |

### 3.2. El recorrido

```
PACIENTE                              PROFESIONAL
   │ /start                              │ /start ─► ¿chat_id autorizado?
   │ 7 preguntas de botones              │           no ─► "no autorizado", fin
   ▼                                     │ código del paciente
copiloto-bd ◄────────────────────────────┤ ─► lee los síntomas
   │ código seudónimo                    │ 4 preguntas de signos
   ▼                                     │ DICOM como DOCUMENTO
"dáselo a tu médico"                     ▼
                              copiloto-mcp:8000/mcp
                              tools/call clasificar_radiografia
                                         │
                                         ▼
                              dos bloques SEPARADOS:
                              lo que dijo la imagen,
                              lo que dijeron síntomas y signos
```

El flujo del paciente **no contiene ningún nodo que hable con el copiloto**.
Esa ausencia es la garantía de D1 y debe verificarse en la revisión.

### 3.3. Reparto síntomas / signos

La regla de Heckerling que consumirá H6 se apoya en cinco predictores, y **tres
no los puede reportar el paciente**: los crepitantes y el murmullo vesicular
disminuido exigen un fonendoscopio, y la frecuencia cardiaca, un pulsioxímetro
o un dedo entrenado.

**El paciente aporta síntomas** (7 preguntas, botones):

1. ¿Ha sentido fiebre en los últimos días? — Sí / No / No sé
2. ¿Tiene tos? — Sí, con flema / Sí, seca / No
3. ¿Desde hace cuánto? — menos de 3 días / 3 a 7 días / más de 7 días
4. ¿Le falta el aire? — Sí / No
5. ¿Le duele el pecho al respirar? — Sí / No
6. ¿Tiene asma diagnosticada? — Sí / No / No sé
7. ¿Algo más que quiera contar? — texto libre **opcional**

La 7 **no alimenta ningún cálculo**: acompaña al profesional y nada más. Se
almacena como texto y se muestra tal cual.

**El profesional aporta signos** (4 preguntas):

1. Temperatura medida (°C) — número
2. Frecuencia cardiaca (lpm) — número
3. Crepitantes a la auscultación — Sí / No
4. Murmullo vesicular disminuido — Sí / No

Con eso H6 tiene los cinco predictores sin volver a tocar los bots.

### 3.4. Por qué no hay LLM

El documento maestro de la Semana 1 dice que el LLM "normaliza español
coloquial". Con D4 eso deja de hacer falta: el paciente contesta con botones y
lo que entra al cálculo es exactamente lo que tocó.

La consecuencia buena es que **ningún dato de paciente sale del VPS** en SP3 —
antes, con un LLM externo, los síntomas habrían viajado a un tercero.

**Acción pendiente:** anotar este cambio en el "Registro de cambios" del
documento maestro de la Semana 1, como se hizo con las cifras del dataset.

---

## 4. Datos

### 4.1. Esquema

```sql
-- Estado efímero mientras el paciente contesta.
-- Existe porque un flujo de n8n no recuerda nada entre mensajes y el
-- callback_data de Telegram está limitado a 64 bytes: no caben 7 respuestas.
CREATE TABLE sesiones_paciente (
  chat_id        bigint PRIMARY KEY,
  paso           smallint    NOT NULL DEFAULT 0,
  respuestas     jsonb       NOT NULL DEFAULT '{}',
  actualizado_en timestamptz NOT NULL DEFAULT now()
);

-- El cuestionario completo. Inmutable una vez creado.
CREATE TABLE cuestionarios (
  codigo     text PRIMARY KEY,
  respuestas jsonb       NOT NULL,
  creado_en  timestamptz NOT NULL DEFAULT now(),
  expira_en  timestamptz NOT NULL
);

-- La lista blanca.
CREATE TABLE profesionales (
  chat_id bigint PRIMARY KEY,
  nombre  text        NOT NULL,
  activo  boolean     NOT NULL DEFAULT true,
  alta_en timestamptz NOT NULL DEFAULT now()
);

-- El registro. Fuente del dashboard y de la validación clínica de H7.
CREATE TABLE consultas (
  id        bigserial PRIMARY KEY,
  codigo    text,
  chat_id   bigint,
  signos    jsonb,
  resultado jsonb,        -- lo que devolvió el copiloto
  error     text,         -- fuera_de_alcance, dicom_invalido, ...
  creado_en timestamptz NOT NULL DEFAULT now()
);
```

`consultas` guarda **también los rechazos**. Un sistema que solo registra sus
éxitos no se puede validar, y la tasa de rechazos es una métrica del dashboard.

### 4.2. El código seudónimo

Seis caracteres de un alfabeto **sin glifos ambiguos** — se excluyen `0`, `O`,
`1`, `I` y `L` — porque se dicta en voz alta en una consulta. Con 31 caracteres
son ~887 millones de combinaciones.

**No es de un solo uso.** Un profesional puede consultar dos veces —segunda
opinión, placa repetida— y bloquearlo estorbaría sin ganar seguridad: adivinar
un código no sirve de nada si no se está además en la lista blanca. La
trazabilidad la da `consultas`, donde cada uso queda registrado.

### 4.3. Retención

- **`sesiones_paciente`**: se borra al completar el cuestionario. Las
  abandonadas de más de 24 h las barre la limpieza diaria.
- **`cuestionarios`**: **7 días y se borran de verdad**, no se marcan. Es la
  ventana entre que el paciente lo llena y pisa la consulta; pasada, el dato
  solo es riesgo acumulado.
- **`consultas`**: perduran mientras dure el proyecto. Son seudónimas y sin
  ellas no hay validación clínica en H7 ni dashboard.

**Decisión pendiente, explícita y no olvidada:** qué pasa con `consultas` al
cerrar el proyecto. Se resuelve antes de H8.

El borrado lo ejecuta `⚙️ Sub: Limpieza de cuestionarios caducados`, con
disparador programado diario. Una tabla que crece para siempre con datos de
pacientes en el disco del cliente no es aceptable.

---

## 5. Flujo del paciente

1. `/start` → aviso de qué es esto y qué **no** es: no es un diagnóstico; si le
   cuesta respirar, que acuda a urgencias.
2. Las 7 preguntas de §3.3, una por mensaje, con botones en línea.
3. Cada respuesta se guarda en `sesiones_paciente` según llega.
4. Al completar: se genera el código, nace la fila de `cuestionarios`, se borra
   la sesión, y se responde:

   > **Su código es `K7FM2P`.**
   > Enséñeselo a su médico junto con su radiografía. Caduca en 7 días.

5. Fin. No hay más camino.

`/reiniciar` borra la sesión en curso y vuelve al paso 1.

---

## 6. Flujo del profesional

1. `/start` → se comprueba `chat_id` contra `profesionales` (con `activo`).
   Si no está: **"No autorizado"** y fin, sin pistas sobre qué hay detrás.
2. Pide el código. Lo busca en `cuestionarios` comprobando `expira_en`.
3. Muestra los síntomas referidos por el paciente.
4. Las 4 preguntas de signos de §3.3.
5. Pide la radiografía, advirtiendo que debe ir **como archivo**.
6. Descarga el fichero de Telegram, lo codifica en base64 y llama al copiloto
   (§7).
7. Responde con **dos bloques separados**:

   > **Imagen** — opacidad probable (probabilidad calibrada 0,85; razón de
   > verosimilitud 19,2)
   > **Síntomas referidos** — fiebre sí, tos con flema, 5 días, sin asma
   > **Signos** — 38,2 °C, 104 lpm, crepitantes sí
   >
   > *La combinación de ambos llega en la siguiente entrega. Esto no es un
   > diagnóstico.*

8. Se registra la consulta, con resultado o con error.

El orden es estricto. `/reiniciar` vuelve al paso 2.

---

## 7. Integración con el copiloto

**Verificado contra el contenedor real el 24-sep-2026.**

Un nodo HTTP Request, sin AI Agent y sin nodo MCP Client Tool. El nodo *MCP
Client Tool* de n8n exige un AI Agent, y eso obligaría al modelo a **emitir**
~175 KB de base64 literal, que no funciona.

**Petición:**

```
POST http://copiloto-mcp:8000/mcp
Content-Type: application/json
Accept: application/json, text/event-stream

{"jsonrpc":"2.0","id":1,"method":"tools/call",
 "params":{"name":"clasificar_radiografia",
           "arguments":{"dicom_base64":"<base64 por expresión de n8n>"}}}
```

No hace falta el saludo `initialize`: el servidor se construye con
`stateless_http=True` y atiende un `tools/call` suelto. Comprobado.

El base64 **puede ir envuelto en líneas**: el servidor quita espacios y saltos
antes de descodificar. Comprobado con LF y con CRLF, resultados idénticos al
plano.

**Respuesta:** llega como evento SSE. El JSON está en la línea `data:`, no
suelto:

```
event: message
data: {"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"<json>"}],"structuredContent":{...},"isError":false}}
```

Se lee de `result.structuredContent`, que trae las claves ya tipadas. Campos:
`probabilidad_cruda`, `probabilidad_calibrada`, `razon_de_verosimilitud`,
`umbral`, `clasificacion`, `edad_paciente`, `modelo`, `auc_validacion`,
`milisegundos`.

**Errores:** `result.isError` es `true` y el texto viene en
`result.content[0].text`, con el prefijo que antepone el SDK:

```
Error executing tool clasificar_radiografia: fuera_de_alcance: El paciente tiene 12 anios y el modelo solo es valido entre 18 y 100.
```

El código de error es el **segundo** campo. Se busca **dentro** del texto; NO se
parte por el primer `:`, que devolvería `Error executing tool
clasificar_radiografia`.

**La razón de verosimilitud viene acotada** a `[0,0163 ; 77,32]` por diseño de
SP2. SP4 debe saberlo: la evidencia de imagen puede mover la probabilidad previa
pero no anularla ni volverla certeza.

---

## 8. Errores

| Situación | Código | Qué dice el bot |
| :--- | :--- | :--- |
| Envía **foto** en vez de archivo | — | "Telegram recomprime las fotos y destruye el DICOM. Envíela como archivo." |
| No es un DICOM legible | `dicom_invalido` | "Ese archivo no es una radiografía DICOM legible." |
| **Paciente menor de 18 o mayor de 100** | `fuera_de_alcance` | "Este copiloto se validó solo en adultos (18-100). No voy a dar un resultado sobre un paciente de N años." **Y ninguna cifra.** |
| La cabecera no declara edad | `edad_desconocida` | "La cabecera DICOM no declara una edad interpretable." **Y ninguna cifra.** |
| Base64 mal formado | `base64_invalido` | "No pude leer el archivo. Vuelva a enviarlo." |
| Más de 5 MB | `payload_excesivo` | "El archivo supera los 5 MB." |
| Código inexistente o caducado | — | "Ese código no existe o caducó. Pida al paciente que repita el cuestionario." |
| El copiloto no responde | — | "El servicio de imagen no está disponible. Inténtelo en unos minutos." |

**El rechazo por edad es una decisión clínica del sistema, no un fallo
técnico.** Debe llegar al profesional como tal, y **ninguna rama de error puede
emitir una cifra**: si se filtrara un número junto al rechazo, alguien lo usaría.

Todos los rechazos se registran en `consultas.error`.

---

## 9. Pruebas

El enfoque A pone la lógica en workflows de n8n, no en código con pytest. Esto
es lo que lo compensa, y es más de lo que parecía: n8n 2.35.4 soporta el marco
de evaluaciones completo (leer ≥ 2.30, ejecutar ≥ 2.32).

**Un Telegram Trigger es un webhook.** Se le puede hacer POST de un `update` de
Telegram fabricado —un `/start`, una pulsación de botón, un documento— ejecutar
el flujo de verdad, y **afirmar sobre la base de datos**.

| Superficie | Cómo se prueba |
| :--- | :--- |
| Máquina de estados del cuestionario | POST de updates sintéticos, aserción sobre `sesiones_paciente` y `cuestionarios` |
| Lista blanca | update con `chat_id` no autorizado → no deja rastro y no llama al copiloto |
| Las 8 ramas de error de §8 | update fabricado por rama, aserción sobre `consultas.error` y sobre la ausencia de cifras |
| Traducción de errores MCP | igual, con el DICOM de un menor real del conjunto de prueba |
| Contrato con el copiloto (§7) | pytest en este repo contra el contenedor: forma del SSE, claves, prefijo del error |
| SQL de borrado y del código | pytest contra una PostgreSQL efímera |
| Que los botones se vean bien | **manual**, con guion escrito |

Las pruebas son **de integración contra un n8n vivo**: más lentas que las
unitarias, con un bot y un `chat_id` de prueba, y mandan mensajes de Telegram de
verdad. Ese es el coste real de D7, y es menor de lo que parecía.

Los dos workflows se **exportan a `n8n/` en este repo** en cada cambio. El diff
de un JSON de nodos se lee mal, pero deja historial, revisión y de dónde
restaurar.

---

## 10. Reglas duras

1. **No se modifica ningún workflow existente** del cliente. Los nuestros son
   nuevos y llevan el prefijo `🩺 Copiloto Triaje:`.
2. **No se reutiliza ninguna credencial de Telegram existente** (D9).
3. **No se crea ni se borra la red** `[retirado]_[retirado]_network`, ni se tocan sus
   otros contenedores.
4. **No se toca `copiloto-mcp`.** Si SP3 necesitara algo del servidor, se para y
   se decide: es otro sub-proyecto con su propia revisión.
5. `copiloto-bd` **no publica puertos**.
6. Ningún dato de paciente sale del VPS.

---

## 11. Dashboard (después de H5)

Un workflow: **Webhook con autenticación básica** → consultas SQL → HTML. Sin
contenedor nuevo, sin framework.

| Bloque | Para qué |
| :--- | :--- |
| Consultas por día, últimos 30 | ¿se usa? |
| Cuestionarios iniciados vs completados | el abandono mide si el cuestionario es largo |
| Distribución de clasificaciones | ¿cuántas opacidades probables? |
| Rechazos por código | salud operativa: si `dicom_invalido` sube, algo pasa con cómo mandan las placas |
| Latencia p50/p95 | vigila el presupuesto de 4 s en producción |
| Consultas por profesional | de cara a H7 |

Solo lo ven las dos personas del equipo, con contraseña. **Ningún código
seudónimo ni respuesta individual aparece**: si la contraseña se aflojara, lo
que se filtra son recuentos.

---

## 12. Riesgos abiertos

| Riesgo | Mitigación |
| :--- | :--- |
| El profesional no consigue el DICOM del PACS en la práctica | Confirmado por el responsable: sí lo consigue. Revalidar con el clínico antes de H7 |
| Las pruebas de integración mandan mensajes reales de Telegram | Bot y `chat_id` dedicados de prueba, nunca los de producción |
| El cuestionario resulta largo y los pacientes abandonan | El dashboard lo mide; acortar es barato una vez hay datos |
| Un despliegue del cliente reinicia n8n a mitad de una conversación | El estado vive en PostgreSQL, no en memoria: la conversación se reanuda |
| `consultas` sin política de cierre | Decisión explícita antes de H8 (§4.3) |

---

## 13. Criterios de aceptación de H5

1. Un paciente completa el cuestionario en Telegram y recibe un código.
2. Un profesional **no autorizado** recibe "no autorizado" y **no** llega al
   copiloto.
3. Un profesional autorizado presenta el código, aporta los signos, envía un
   DICOM real de adulto y recibe el resultado del modelo **con los bloques
   separados**.
4. Una placa de un paciente **menor de 18** produce el rechazo clínico
   explicado, **sin ninguna cifra**, y queda registrada en `consultas.error`.
5. Una imagen enviada **como foto** produce la explicación de por qué no sirve.
6. Los cuestionarios caducados desaparecen de la base de datos.
7. Ningún workflow ni contenedor existente del cliente cambió de estado.
8. Los dos workflows están exportados en `n8n/` de este repo.
