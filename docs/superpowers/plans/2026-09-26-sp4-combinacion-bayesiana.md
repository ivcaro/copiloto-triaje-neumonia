# SP4 — Combinación bayesiana de clínica e imagen: plan de implementación

> **Para trabajadores agénticos:** SUB-SKILL REQUERIDA: usa
> superpowers:subagent-driven-development (recomendado) o
> superpowers:executing-plans para ejecutar este plan tarea a tarea. Los pasos
> usan casillas (`- [ ]`) para el seguimiento.

**Objetivo:** que el informe del profesional lleve un cuarto bloque,
`COMBINADO`, con la probabilidad posterior de opacidad compatible: la
prevalencia declarada por las odds de la regla de Heckerling y por la razón de
verosimilitud de la imagen que SP2 ya entrega.

**Arquitectura:** la aritmética vive en Python, en un módulo nuevo junto a
`calibracion.py`; la herramienta MCP `clasificar_radiografia` acepta un
parámetro opcional `hallazgos` y, si viene, devuelve un bloque `combinacion`
dentro de la misma respuesta. El bot del profesional manda los cinco datos con
la placa (`A base64`), valida el bloque al leer (`Leer respuesta`) y lo redacta
(`Desenlace`). La prevalencia es `PREVALENCIA_LOCAL`, variable de entorno sin
valor por defecto, como `AUC_VALIDACION`. Ninguna migración: el bloque viaja
dentro del `structuredContent` que `consultas.resultado` ya guarda.

**Pila:** Python 3.12 (intérprete `C:/venv-copiloto/Scripts/python.exe`),
pytest, FastAPI + SDK MCP 2.2.0, n8n 2.35.4 (los nodos son JavaScript dentro de
`n8n/copiloto-profesional.json`, y se prueban con `node tests/profesional.mjs`),
Docker Compose v2.

**Spec:** `docs/superpowers/specs/2026-09-26-sp4-combinacion-bayesiana-design.md`
(commit `98f7904` o posterior) — léelo entero antes de la primera tarea. El plan
argumenta desde él; en cualquier contradicción manda el spec, salvo en lo que
la sección «Decisiones del plan» de abajo fija explícitamente porque el spec lo
dejaba abierto.

## Restricciones globales

Copiadas del spec de SP4 (§14) y de lo que SP3 dejó en vigor. **Los requisitos
de cada tarea las incluyen.**

1. **Los cortes son estrictos:** 37,8 °C exactos **no** puntúan; 100 lpm exactos
   **no** puntúan. Se aplican en Python, nunca en n8n.
2. **Las seis RV son las de la derivación** y se escriben una sola vez:
   `0→0,12; 1→0,20; 2→0,70; 3→1,64; 4→7,18; 5→17,5`. Con la prevalencia de la
   cohorte (`134/914`) la cadena reproduce el VPP del artículo
   (`2,0 / 3,4 / 10,8 / 22,0 / 55,2 / 75,0 %`) salvo redondeo a una décima.
3. **`PREVALENCIA_LOCAL` no tiene valor por defecto.** Sin ella el servidor no
   arranca. Arranca en `0.1466`, declarada en el compose con su fuente.
4. **Sin `hallazgos`, la respuesta de `clasificar_radiografia` es idéntica a la
   de SP3**, y las diez comprobaciones de `tests/test_contrato_mcp.py` pasan
   **sin modificarse**. La única línea de ese fichero que cambia es la
   constante `ARRANCAR` (el `docker run` que se imprime al saltar), porque el
   contenedor ahora necesita la variable.
5. **Ninguna posterior se presenta como 0 % ni como 100 %:** `< 1 %` y `> 99 %`.
   Se imprime en porcentaje **entero**. **Un rango cuyos dos extremos redondean
   al mismo entero se imprime como un solo número.** Nunca se anidan dos
   rangos.
6. **La acotación por dependencia solo se aplica si todas las RV clínicas están
   del mismo lado de 1 que la de la imagen.** Discordantes → un número.
7. **El informe con combinación imprime los tres factores y lleva ⚠️.** Lo que
   el sistema *afirma* dice «opacidad compatible»; lo que *advierte* puede
   decir «neumonía». Ningún literal de la combinación afirma «neumonía».
8. **Con signos incompletos o sin cuestionario no hay combinación**, el informe
   sale como en SP3 y dice por qué (`SIN COMBINAR — …`).
9. **Ninguna rama de error emite una cifra de probabilidad** (SP3, criterio 7).
   `hallazgos_invalidos` es una rama de error como las demás.
10. **No se modifica ningún workflow del cliente**; los nuestros llevan el
    prefijo `🩺 Copiloto Triaje:`. No se toca `copiloto-bd` ni su compose. Los
    secretos nunca van al repositorio. El corpus de `pruebas/corpus/` es un
    REGISTRO de lo desplegado y no se regenera contra el repositorio.
11. **Los mensajes que lee un clínico van bien escritos** —con tildes y de
    usted—. `tests/profesional.mjs` (sección «I bis») y
    `tests/test_inferencia.py::test_los_mensajes_que_lee_un_clinico_estan_bien_escritos`
    lo comprueban.
12. **Los commits se encadenan con `&&`** (`... && pytest ... && git commit`),
    nunca con `;`: esta rama ya perdió dos veces un commit con las pruebas en
    rojo por un `;`. El mensaje del commit va en castellano y termina con
    `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

## Cómo se corren las pruebas

```bash
cd "C:/Users/[retirado]/OneDrive/Desktop/Claude/Proyecto Integrador/copiloto-triaje"
C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_heckerling.py -q        # una suite
C:/venv-copiloto/Scripts/python.exe -m pytest -q -rs                              # todo pytest (unos 300)
node tests/profesional.mjs > /tmp/prof.txt; echo "salida $?"; tail -3 /tmp/prof.txt  # los nodos (576 OK hoy)
```

`node tests/profesional.mjs | tail` devuelve el código de salida de `tail`: para
el verde de verdad, redirige a fichero y mira `$?`, o corre sin tubería. Las
pruebas que hablan con el contenedor o con n8n **se saltan** sin el entorno y
lo dicen con `-rs`; un skip no es un fallo, pero tampoco es verde: léelo.

## Orden de despliegue (importa)

**Primero el servidor, después el bot.** El servidor nuevo sin `hallazgos`
contesta igual que el viejo, así que el bot viejo sigue funcionando contra él.
Al revés no: el bot nuevo manda `hallazgos` y un servidor viejo no lo conoce.
`Desenlace` tolera igualmente que falte el bloque (`SIN COMBINAR — el copiloto
no devolvió la combinación…`), así que un orden equivocado se ve, no se rompe.

## Mapa de ficheros

| Fichero | Qué le pasa |
| :--- | :--- |
| `src/copiloto_triaje/servicio/heckerling.py` | **nuevo**: constantes con fuente, `puntuar`, `combinar`, `mas_informativa`, `validar_hallazgos`, `combinacion` |
| `src/copiloto_triaje/servicio/inferencia.py` | `Motor` gana `prevalencia_local`; `clasificar(datos, hallazgos=None)` añade el bloque |
| `src/copiloto_triaje/servicio/aplicacion.py` | el tool acepta `hallazgos`; `/inferir` lo acepta como campo JSON del formulario; `/salud` publica la prevalencia |
| `servidor/arrancar.py` | exige `PREVALENCIA_LOCAL` |
| `servidor/docker-compose.yml` | declara `PREVALENCIA_LOCAL: "0.1466"` con su fuente |
| `n8n/copiloto-profesional.json` | tres nodos de código: `A base64`, `Leer respuesta`, `Desenlace` |
| `pruebas/reproducir_casos.py` | el modo `--sin-bots` manda los mismos cinco datos que el bot |
| `tests/test_heckerling.py` | **nuevo** |
| `tests/test_inferencia.py`, `tests/test_aplicacion.py`, `tests/test_arrancar.py` | pruebas nuevas; los tres `Motor(...)` de los fixtures ganan `prevalencia_local=0.1466` |
| `tests/test_contrato_sp4.py` | **nuevo**: contrato en vivo del bloque, aparte de los diez de SP3 |
| `tests/test_contrato_mcp.py` | **una línea**: la constante `ARRANCAR` |
| `tests/profesional.mjs`, `tests/test_flujo_profesional.py`, `tests/test_reproducir_casos.py` | pruebas nuevas |
| `README.md`, `docs/sp2-despliegue.md`, `docs/sp3-operacion.md`, spec de SP3 (§5.4 y §8) | documentación |

## Decisiones del plan

Lo que el spec deja al plan, decidido aquí para que las tareas no lo decidan
cada una por su cuenta. Cada una lleva su coste si está mal.

- **D1. `puntuar` devuelve siempre una tupla**: `(3,)` o `(3, 4)`. Con
  `no_se`, primero con asma (no puntúa) y luego sin asma. Un solo tipo de
  retorno es más fácil de consumir que «int o tupla». *Coste si está mal:*
  ninguno visible; es una convención interna.
- **D2. `hallazgos` viaja con los datos crudos** —dos números, dos booleanos y
  el asma con sus tres estados—, no con booleanos ya cortados (spec §9.3
  corregido). *Coste:* cinco datos en vez de cinco bits; misma clase de
  exposición (§9.3).
- **D3. `validar_hallazgos` es estricta**: ni una clave de menos ni una de más;
  los booleanos tienen que ser `bool` de verdad (ni `"false"` ni `0`); los
  números, finitos. No se comprueban rangos clínicos: eso lo hace `Decidir`
  (§4.4 de SP3) antes de guardar. *Coste:* un cliente que mande una clave extra
  recibe `hallazgos_invalidos` en vez de un resultado; es su error y lo lee.
- **D4. `hallazgos_invalidos` es un `ErrorDeInferencia` más** y se comprueba
  ANTES de leer el DICOM: es barato y, si ocurre, el error es de quien llama.
  El bot NO aprende ese código: `Leer respuesta` lo trata como
  `error_no_reconocido` (termina, y el texto crudo va a `consultas.error`),
  porque si llega es que `A base64` tiene un fallo, no que el clínico hizo algo
  mal. La tabla del §9 de SP3 no cambia. *Coste:* un fallo de `A base64` cierra
  la conversación del profesional con «no sé interpretar»; se ve en
  `consultas.error` el mismo día.
- **D5. El bloque `combinacion` lleva exactamente diez campos** (spec §9.2):
  `prevalencia, puntuacion[], rv_clinica[], rv_imagen, concordantes, absorbe,
  independencia[], dependencia[]|null, minima, maxima`. Las posteriores van
  redondeadas a **cuatro decimales**; `rv_imagen` tal cual llega.
- **D6. Concordancia con dos puntuaciones**: se acota solo si **las dos** RV
  clínicas están del lado de la imagen. Con `2` y `3` (0,70 y 1,64) y una imagen
  a favor, no hay concordancia y la horquilla sale de las dos posteriores bajo
  independencia. *Coste:* en ese caso raro se pierde la cota; el informe sigue
  siendo honesto.
- **D7. Lo que dice el ⚠️** sale de la tabla del §8 del spec y se implementa en
  `Desenlace`: con concordancia y extremos distintos, los dos números y quién
  absorbe a quién (`absorbe`); con extremos iguales, sin números; discordantes,
  «apuntan en sentidos opuestos». Con las dos RV por debajo de 1, el extremo de
  independencia es el bajo y el de dependencia el alto, y se nombran por su
  número.
- **D8. El descargo del informe pasa a ser `Esto no es un diagnóstico.`** para
  todos los desenlaces con resultado, con o sin combinación. La frase «la
  combinación llega en la siguiente entrega» desaparece: SP4 es esa entrega.
  Delante del descargo va `COMBINADO — …` o `SIN COMBINAR — …`. *Coste:* el
  corpus de SP3 muestra la frase vieja hasta que se regenere contra la imagen
  nueva (restricción 10).
- **D9. `Leer respuesta` valida el bloque si viene** (forma y tipos, como hace
  con los cuatro números del §8) y lo rechaza entero como `error_no_reconocido`
  si está mal. `Desenlace` confía en lo que `Leer respuesta` dejó pasar.
- **D10. La imagen sigue etiquetada `copiloto-mcp:0.1.0`.** La prueba de que el
  contenedor desplegado es el nuevo es que `/salud` publica
  `prevalencia_local`. *Coste:* la etiqueta no distingue las dos imágenes; el
  `/salud` sí.
- **D11. Los tres nodos se editan con un script que reescribe el export en su
  mismo formato** (`json.dumps(w, ensure_ascii=False, indent=2) + "\n"`,
  comprobado byte a byte antes de tocar nada) y cambia el `jsCode` por anclas
  exactas que deben aparecer **una** vez. Así el `git diff` es solo el nodo.
- **D12. `tests/test_contrato_sp4.py` va aparte de `test_contrato_mcp.py`**, y
  se salta también cuando el contenedor que responde es anterior a SP4 (su
  `/salud` no trae `prevalencia_local`), diciéndolo.

---

## Prerrequisitos humanos

| # | Qué | Bloquea |
| :-- | :--- | :--- |
| P1 | **Redesplegar el servidor en el VPS** con el compose nuevo (tarea 11, parte A: son cuatro comandos que se le dan al usuario) | la publicación de los nodos (tarea 11, parte B) y `tests/test_contrato_sp4.py` en vivo |
| P2 | Un chat de profesional autorizado para la prueba de extremo a extremo (ya existe desde SP3) | tarea 11, parte C |

Las tareas 1 a 10 no necesitan nada del VPS ni de n8n vivo.

---

### Tarea 1: `heckerling.py` — la regla, sus RV y la aritmética de odds

**Ficheros:**
- Crear: `src/copiloto_triaje/servicio/heckerling.py`
- Crear: `tests/test_heckerling.py`

**Interfaces:**
- Consume: nada del repositorio (módulo puro; la aritmética es la misma que
  `Calibrador.razon_de_verosimilitud` hace al revés).
- Produce, para las tareas 2 y 3:
  - `PUNTOS: tuple[str, ...]` = `("temperatura_c", "frecuencia_cardiaca", "crepitantes", "murmullo_disminuido", "asma")`
  - `TEMPERATURA_CORTE_C = 37.8`, `PULSO_CORTE_LPM = 100`, `ESTADOS_ASMA = ("si", "no", "no_se")`
  - `RV_POR_PUNTUACION: dict[int, float]`, `PREVALENCIA_COHORTE = 134 / 914`
  - `class HallazgosInvalidos(ValueError)`
  - `validar_hallazgos(hallazgos) -> dict` (los cinco, tipados) o `HallazgosInvalidos`
  - `puntuar(signos: Mapping, asma: str) -> tuple[int, ...]` (D1)
  - `combinar(prevalencia: float, rv_clinica: float, rv_imagen: float) -> float`
  - `mas_informativa(rv_a: float, rv_b: float) -> float`

- [ ] **Paso 1: escribir las pruebas que fallan**

`tests/test_heckerling.py`:

```python
"""Pruebas de la regla de Heckerling y de la aritmetica de la combinacion.

La que sostiene todo lo demas es la reproduccion del articulo (spec §11.1):
con la prevalencia de la propia cohorte, la cadena tiene que dar la columna de
VPP publicada. Si alguien toca una RV o la aritmetica, deja de darla.
"""
import math

import pytest

from copiloto_triaje.servicio.heckerling import (
    ESTADOS_ASMA, PREVALENCIA_COHORTE, PULSO_CORTE_LPM, PUNTOS,
    RV_POR_PUNTUACION, TEMPERATURA_CORTE_C, HallazgosInvalidos, combinar,
    mas_informativa, puntuar, validar_hallazgos,
)

# La tabla 2 de PMC7422644 (conjunto de derivacion de Heckerling), COPIADA A
# MANO: testigo independiente del modulo. Por puntuacion: (con neumonia, sin
# neumonia, VPP publicado en %, decimales con los que se publica la RV).
ARTICULO = {
    0: (1, 48, 2.0, 2),
    1: (11, 316, 3.4, 2),
    2: (28, 232, 10.8, 2),
    3: (42, 149, 22.0, 2),
    4: (37, 30, 55.2, 2),
    5: (15, 5, 75.0, 1),
}
CON_NEUMONIA = 134
SIN_NEUMONIA = 780

# Tres de los cuatro puntos del profesional presentes; el asma decide el cuarto.
SIGNOS_3 = {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
            "crepitantes": True, "murmullo_disminuido": False}


def test_las_celdas_del_articulo_suman_lo_que_el_articulo_dice():
    assert sum(c for c, _, _, _ in ARTICULO.values()) == CON_NEUMONIA
    assert sum(s for _, s, _, _ in ARTICULO.values()) == SIN_NEUMONIA
    assert PREVALENCIA_COHORTE == pytest.approx(CON_NEUMONIA / (CON_NEUMONIA + SIN_NEUMONIA))


@pytest.mark.parametrize("puntuacion", sorted(ARTICULO))
def test_cada_rv_sale_de_las_celdas_del_articulo(puntuacion):
    """RV = (con/134) / (sin/780), redondeada como la publica el articulo.
    Una RV tecleada mal -o «mejorada»- deja de coincidir."""
    con, sin, _, decimales = ARTICULO[puntuacion]
    calculada = (con / CON_NEUMONIA) / (sin / SIN_NEUMONIA)
    assert round(calculada, decimales) == RV_POR_PUNTUACION[puntuacion]


@pytest.mark.parametrize("puntuacion", sorted(ARTICULO))
def test_la_cadena_reproduce_la_columna_de_vpp_del_articulo(puntuacion):
    """Spec §11.1 y criterio 1: con la prevalencia de la cohorte y RV de imagen
    1 (sin imagen), la posterior es el VPP publicado salvo redondeo a una
    decima."""
    _, _, vpp, _ = ARTICULO[puntuacion]
    posterior = combinar(PREVALENCIA_COHORTE, RV_POR_PUNTUACION[puntuacion], 1.0)
    assert abs(posterior * 100 - vpp) <= 0.1, (posterior * 100, vpp)


def test_los_cinco_predictores_son_los_datos_que_los_bots_recogen():
    assert PUNTOS == ("temperatura_c", "frecuencia_cardiaca", "crepitantes",
                      "murmullo_disminuido", "asma")
    assert TEMPERATURA_CORTE_C == 37.8
    assert PULSO_CORTE_LPM == 100
    assert ESTADOS_ASMA == ("si", "no", "no_se")


def test_los_cortes_son_estrictos():
    """Spec §11.2: 37,8 exactos NO puntuan; 100 exactos NO puntuan."""
    justo = {"temperatura_c": 37.8, "frecuencia_cardiaca": 100,
             "crepitantes": False, "murmullo_disminuido": False}
    assert puntuar(justo, "si") == (0,)
    encima = {"temperatura_c": 37.9, "frecuencia_cardiaca": 101,
              "crepitantes": False, "murmullo_disminuido": False}
    assert puntuar(encima, "si") == (2,)


def test_el_asma_puntua_por_ausencia():
    assert puntuar(SIGNOS_3, "si") == (3,)
    assert puntuar(SIGNOS_3, "no") == (4,)


@pytest.mark.parametrize("crepitantes", [False, True])
@pytest.mark.parametrize("murmullo", [False, True])
def test_con_asma_no_se_salen_dos_puntuaciones_que_difieren_en_uno(crepitantes, murmullo):
    """Spec §6 y §11.2: no se elige por el clinico; se le dan las dos, y son
    (con asma, sin asma)."""
    signos = {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
              "crepitantes": crepitantes, "murmullo_disminuido": murmullo}
    con, sin = puntuar(signos, "no_se")
    assert sin == con + 1
    assert (con,) == puntuar(signos, "si")
    assert (sin,) == puntuar(signos, "no")


def test_todo_presente_y_sin_asma_da_cinco():
    signos = {"temperatura_c": 39.0, "frecuencia_cardiaca": 120,
              "crepitantes": True, "murmullo_disminuido": True}
    assert puntuar(signos, "no") == (5,)


@pytest.mark.parametrize("asma", ["quizas", "", None, True, "SI"])
def test_un_asma_fuera_de_los_tres_estados_se_rechaza(asma):
    with pytest.raises(HallazgosInvalidos):
        puntuar(SIGNOS_3, asma)


@pytest.mark.parametrize("clave, valor", [
    ("crepitantes", "true"),        # la cadena "true" no es un booleano
    ("crepitantes", 1),             # ni un entero
    ("murmullo_disminuido", None),
    ("temperatura_c", "38,2"),      # un numero en texto no es un numero
    ("temperatura_c", float("nan")),
    ("frecuencia_cardiaca", True),  # bool es subclase de int: colaria como 1
])
def test_un_signo_con_el_tipo_equivocado_se_rechaza_y_dice_cual(clave, valor):
    with pytest.raises(HallazgosInvalidos) as exc:
        puntuar({**SIGNOS_3, clave: valor}, "no")
    assert clave in str(exc.value)


def test_validar_hallazgos_exige_exactamente_las_cinco_claves():
    completos = {**SIGNOS_3, "asma": "no_se"}
    assert validar_hallazgos(completos) == completos
    with pytest.raises(HallazgosInvalidos) as falta:
        validar_hallazgos({**SIGNOS_3})                       # sin asma
    assert "asma" in str(falta.value)
    with pytest.raises(HallazgosInvalidos) as sobra:
        validar_hallazgos({**completos, "tos": "seca"})       # una de mas
    assert "tos" in str(sobra.value)
    with pytest.raises(HallazgosInvalidos):
        validar_hallazgos("no es un objeto")


def test_combinar_es_la_aritmetica_de_odds():
    prev, rv_c, rv_i = 0.1466, 1.64, 30.3
    odds = prev / (1 - prev) * rv_c * rv_i
    assert combinar(prev, rv_c, rv_i) == pytest.approx(odds / (1 + odds))
    # Con las dos RV en 1, la posterior es la prevalencia: no hay evidencia.
    assert combinar(prev, 1.0, 1.0) == pytest.approx(prev)


def test_combinar_rechaza_una_prevalencia_que_no_es_una_probabilidad():
    for prev in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            combinar(prev, 1.0, 1.0)
    with pytest.raises(ValueError):
        combinar(0.1466, 0.0, 1.0)


def test_la_posterior_nunca_toca_0_ni_1_con_las_rv_acotadas():
    """Con la RV de imagen dentro de lo que el calibrador sostiene
    ([0,0163 ; 77,32], SP2) y las seis RV clinicas, la posterior queda
    estrictamente dentro de (0, 1) para la prevalencia de arranque."""
    for rv_c in RV_POR_PUNTUACION.values():
        for rv_i in (0.016271632806621517, 77.32279909706551):
            p = combinar(0.1466, rv_c, rv_i)
            assert 0.0 < p < 1.0


def test_mas_informativa_es_la_de_mayor_log_absoluto():
    assert mas_informativa(0.12, 0.87) == 0.12
    assert mas_informativa(30.3, 1.64) == 30.3
    assert mas_informativa(1.64, 30.3) == 30.3
    # A ojo se diria lo contrario: |ln 0,14| = 1,966 y |ln 7,18| = 1,971.
    # Es la clase de error que esta funcion existe para no cometer a ojo.
    assert mas_informativa(0.14, 7.18) == 7.18
    # En empate exacto manda la primera.
    assert mas_informativa(2.0, 0.5) == 2.0
    assert math.isclose(abs(math.log(2.0)), abs(math.log(0.5)))
```

- [ ] **Paso 2: correr y ver que falla**

Correr: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_heckerling.py -q`
Esperado: FALLO por `ModuleNotFoundError: copiloto_triaje.servicio.heckerling`.

- [ ] **Paso 3: escribir el módulo**

`src/copiloto_triaje/servicio/heckerling.py`:

```python
"""La regla de Heckerling y la combinacion bayesiana con la imagen (SP4).

    Heckerling PS, Tape TG, Wigton RS, Hissong KK, Leikin JB, Ornato JP, et al.
    Clinical prediction rule for pulmonary infiltrates.
    Ann Intern Med. 1990;113(9):664-70.

Las razones de verosimilitud (RV) por puntuacion son las del conjunto de
DERIVACION (Illinois), tal como las reproduce la revision sistematica con
metaanalisis PMC7422644 (tabla 2). No se pudo leer el articulo primario
-PubMed contesta con un CAPTCHA y Annals es de pago-, asi que la fuente es esa
revision, y se dice. Las RV se verificaron contra los recuentos de la tabla
antes de escribirlas aqui, y `tests/test_heckerling.py` lo vuelve a hacer en
cada corrida.

La aritmetica es la MISMA que `calibracion.py` usa para la imagen, al reves:

    odds_previas     = prevalencia / (1 - prevalencia)
    odds_posteriores = odds_previas x RV_clinica x RV_imagen
    posterior        = odds_posteriores / (1 + odds_posteriores)

Multiplicar dos RV asume que son condicionalmente independientes, y aqui eso
es discutible: los crepitantes y la opacidad son el mismo fenomeno visto de
dos maneras. No se corrige con un factor inventado; se ACOTA (spec §7): la
posterior bajo independencia y la posterior con solo la RV mas informativa
son los dos extremos calculables, y el informe entrega los dos.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

# Los cinco predictores de la regla, con el nombre del dato que los bots ya
# recogen (spec §2). El asma entra al reves: puntua su AUSENCIA.
PUNTOS = ("temperatura_c", "frecuencia_cardiaca", "crepitantes",
          "murmullo_disminuido", "asma")

# Los dos cortes, ESTRICTOS: 37,8 exactos no puntuan y 100 exactos no puntuan
# (spec §11.2). Un corte mal puesto mueve la puntuacion entera, y ninguna
# prueba de redondeo lo cazaria.
TEMPERATURA_CORTE_C = 37.8
PULSO_CORTE_LPM = 100

ESTADOS_ASMA = ("si", "no", "no_se")

# RV de la derivacion (spec §4). Cada una es (con neumonia / 134) / (sin / 780)
# con las celdas de la tabla 2 de PMC7422644; la prueba las recalcula.
RV_POR_PUNTUACION = {0: 0.12, 1: 0.20, 2: 0.70, 3: 1.64, 4: 7.18, 5: 17.5}

# La prevalencia de la propia cohorte de derivacion: 134 de 914 (spec §5). Es
# el valor con el que ARRANCA `PREVALENCIA_LOCAL`; el servidor la lee del
# entorno (servidor/arrancar.py), no de aqui.
PREVALENCIA_COHORTE = 134 / 914


class HallazgosInvalidos(ValueError):
    """Unos hallazgos con los que no se puede puntuar. El mensaje lo lee una
    persona -acaba en `consultas.error`-, asi que va bien escrito."""


def _numero(hallazgos: Mapping, clave: str) -> float:
    v = hallazgos.get(clave)
    # `bool` es subclase de `int`: un `True` colaria como un grado.
    if (isinstance(v, bool) or not isinstance(v, (int, float))
            or not math.isfinite(v)):
        raise HallazgosInvalidos(
            f"«{clave}» debe ser un número finito, y es {v!r}.")
    return float(v)


def _booleano(hallazgos: Mapping, clave: str) -> bool:
    v = hallazgos.get(clave)
    # Solo `True`/`False`: la cadena "false" es cierta en cualquier lenguaje, y
    # un 0/1 no dice si alguien auscultó o tecleó.
    if not isinstance(v, bool):
        raise HallazgosInvalidos(
            f"«{clave}» debe ser verdadero o falso, y es {v!r}.")
    return v


def validar_hallazgos(hallazgos) -> dict:
    """Los cinco hallazgos con su tipo, o `HallazgosInvalidos`.

    Estricta en las claves: ni una de menos -no se puntúa con cuatro- ni una
    de más -una clave desconocida es un error de quien llama, no un dato que
    ignorar-. No comprueba rangos clinicos: eso lo hace `Decidir` (§4.4 de
    SP3) antes de guardar el signo.
    """
    if not isinstance(hallazgos, Mapping):
        raise HallazgosInvalidos(
            "los hallazgos deben ser un objeto con cinco campos: "
            + ", ".join(PUNTOS) + ".")
    faltan = [k for k in PUNTOS if k not in hallazgos]
    sobran = [k for k in hallazgos if k not in PUNTOS]
    if faltan or sobran:
        raise HallazgosInvalidos(
            f"hallazgos incompletos o con campos de más: faltan {faltan}, "
            f"sobran {sobran}.")
    asma = hallazgos["asma"]
    if asma not in ESTADOS_ASMA:
        raise HallazgosInvalidos(
            f"«asma» debe ser uno de {list(ESTADOS_ASMA)}, y es {asma!r}.")
    return {
        "temperatura_c": _numero(hallazgos, "temperatura_c"),
        "frecuencia_cardiaca": _numero(hallazgos, "frecuencia_cardiaca"),
        "crepitantes": _booleano(hallazgos, "crepitantes"),
        "murmullo_disminuido": _booleano(hallazgos, "murmullo_disminuido"),
        "asma": asma,
    }


def puntuar(signos: Mapping, asma: str) -> tuple[int, ...]:
    """La puntuacion de Heckerling: una, o DOS si el asma no se sabe.

    `signos` son los cuatro del profesional (temperatura_c,
    frecuencia_cardiaca, crepitantes, murmullo_disminuido); `asma` es uno de
    `ESTADOS_ASMA`. Devuelve siempre una tupla: `(3,)`, o con `no_se`
    `(con_asma, sin_asma)`, que difieren exactamente en uno. No se elige por
    el clinico: se le dan las dos (spec §6).
    """
    if not isinstance(signos, Mapping):
        raise HallazgosInvalidos("los signos deben ser un objeto con los "
                                 "cuatro datos de la exploración.")
    h = validar_hallazgos({k: signos.get(k) for k in PUNTOS if k != "asma"}
                          | {"asma": asma})
    base = (int(h["temperatura_c"] > TEMPERATURA_CORTE_C)
            + int(h["frecuencia_cardiaca"] > PULSO_CORTE_LPM)
            + int(h["crepitantes"])
            + int(h["murmullo_disminuido"]))
    if h["asma"] == "no_se":
        return (base, base + 1)
    return (base + (1 if h["asma"] == "no" else 0),)


def combinar(prevalencia: float, rv_clinica: float, rv_imagen: float) -> float:
    """Probabilidad posterior: odds previas por las dos RV, y de vuelta.

    No acota: las RV ya llegan acotadas -la de la imagen por la curva del
    calibrador, la clinica por la tabla- y con una prevalencia en (0, 1) el
    resultado no puede ser 0 ni 1.
    """
    if not 0.0 < prevalencia < 1.0:
        raise ValueError(
            f"la prevalencia debe estar entre 0 y 1, y es {prevalencia!r}")
    if rv_clinica <= 0 or rv_imagen <= 0:
        raise ValueError("las razones de verosimilitud deben ser positivas")
    odds = prevalencia / (1.0 - prevalencia) * rv_clinica * rv_imagen
    return odds / (1.0 + odds)


def mas_informativa(rv_a: float, rv_b: float) -> float:
    """La RV que mas mueve las odds: la de mayor |ln|. Es la «dependencia
    total» del spec §7.1: la otra no anade nada. En empate exacto, la
    primera."""
    return rv_a if abs(math.log(rv_a)) >= abs(math.log(rv_b)) else rv_b
```

- [ ] **Paso 4: correr y ver que pasa**

Correr: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_heckerling.py -q`
Esperado: todo en verde (unas 30 pruebas con las parametrizadas).

- [ ] **Paso 5: dos mutaciones a mano, y deshacerlas**

Cambia `RV_POR_PUNTUACION[1]` a `0.19` → deben ponerse rojas
`test_cada_rv_sale_de_las_celdas_del_articulo[1]` y
`test_la_cadena_reproduce_la_columna_de_vpp_del_articulo[1]`. Cambia
`TEMPERATURA_CORTE_C > ` por `>=` → `test_los_cortes_son_estrictos` rojo.
Deshaz las dos con `git checkout -- src/copiloto_triaje/servicio/heckerling.py`
**solo si ya has hecho commit del paso 6**; si no, deshazlas a mano y comprueba
`pytest` en verde otra vez.

- [ ] **Paso 6: commit**

```bash
git add src/copiloto_triaje/servicio/heckerling.py tests/test_heckerling.py && C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_heckerling.py -q && git commit -m "feat(sp4): la regla de Heckerling y la aritmetica de odds, con la reproduccion del articulo como prueba

Las seis RV de la derivacion (PMC7422644, tabla 2) se recalculan desde las
celdas en cada corrida, y con la prevalencia de la cohorte la cadena da la
columna de VPP publicada salvo redondeo a una decima. Los cortes son
estrictos y estan probados en el borde. Con asma no_se salen dos
puntuaciones, nunca una elegida por el clinico.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 2: `combinacion()` — el bloque que viaja, con la cota de dependencia

**Ficheros:**
- Modificar: `src/copiloto_triaje/servicio/heckerling.py` (añadir al final)
- Modificar: `tests/test_heckerling.py` (añadir al final)

**Interfaces:**
- Consume: `validar_hallazgos`, `puntuar`, `combinar`, `mas_informativa`,
  `RV_POR_PUNTUACION` (tarea 1).
- Produce, para la tarea 3 y para los nodos (tareas 7 y 8):
  `combinacion(prevalencia: float, hallazgos: Mapping, rv_imagen: float) -> dict`
  con exactamente estas claves (D5):

  ```python
  {"prevalencia": 0.1466,          # float, la que se paso
   "puntuacion": [3],              # list[int], 1 o 2 elementos; con no_se [con_asma, sin_asma]
   "rv_clinica": [1.64],           # list[float], paralela a puntuacion
   "rv_imagen": 30.29,             # float, tal cual llego
   "concordantes": True,           # bool: todas las rv_clinica del lado de 1 de rv_imagen
   "absorbe": "imagen",            # "imagen" | "clinica" | "mixta" | None (si no concordantes)
   "independencia": [0.8951],      # list[float] a 4 decimales, paralela a puntuacion
   "dependencia": [0.8388],        # list[float] a 4 decimales o None
   "minima": 0.8388, "maxima": 0.8951}   # min y max de todo lo anterior, a 4 decimales
  ```

- [ ] **Paso 1: pruebas que fallan** (añadir a `tests/test_heckerling.py`)

```python
from copiloto_triaje.servicio.heckerling import combinacion  # noqa: E402

PREV = 0.1466
RV_MUY_POSITIVA = 30.3       # la placa positiva clara del corpus de SP3
RV_BANDA = 0.87              # la banda contradictoria
CLAVES_DEL_BLOQUE = {"prevalencia", "puntuacion", "rv_clinica", "rv_imagen",
                     "concordantes", "absorbe", "independencia", "dependencia",
                     "minima", "maxima"}


def _hallazgos(asma, **cambios):
    return {**SIGNOS_3, "asma": asma, **cambios}


def test_el_bloque_lleva_exactamente_las_diez_claves_del_spec():
    c = combinacion(PREV, _hallazgos("si"), RV_MUY_POSITIVA)
    assert set(c) == CLAVES_DEL_BLOQUE
    assert c["prevalencia"] == PREV
    assert c["rv_imagen"] == RV_MUY_POSITIVA


def test_ejemplo_1_del_spec_puntuacion_3_e_imagen_30_3():
    """§8, caso normal: entre 84 % (dependencia total) y 90 % (independencia)."""
    c = combinacion(PREV, _hallazgos("si"), RV_MUY_POSITIVA)
    assert c["puntuacion"] == [3] and c["rv_clinica"] == [1.64]
    assert c["concordantes"] is True and c["absorbe"] == "imagen"
    assert c["independencia"] == [pytest.approx(0.8951, abs=5e-4)]
    assert c["dependencia"] == [pytest.approx(0.8388, abs=5e-4)]
    assert c["minima"] == c["dependencia"][0]
    assert c["maxima"] == c["independencia"][0]


def test_ejemplo_2_del_spec_discordantes_no_se_acota():
    """§8: puntuacion 0 (RV 0,12) contra imagen 30,3 -> un numero, 38 %."""
    ceros = {"temperatura_c": 37.0, "frecuencia_cardiaca": 80,
             "crepitantes": False, "murmullo_disminuido": False, "asma": "si"}
    c = combinacion(PREV, ceros, RV_MUY_POSITIVA)
    assert c["puntuacion"] == [0] and c["rv_clinica"] == [0.12]
    assert c["concordantes"] is False
    assert c["dependencia"] is None and c["absorbe"] is None
    assert c["minima"] == c["maxima"] == c["independencia"][0]
    assert c["minima"] == pytest.approx(0.3845, abs=5e-4)


def test_ejemplo_3_del_spec_asma_no_se_funde_todo_en_una_horquilla():
    """§8 tercer ejemplo: 4 o 5 con imagen 30,3 -> del 84 % al 99 %."""
    cuatro = _hallazgos("no_se", murmullo_disminuido=True)
    c = combinacion(PREV, cuatro, RV_MUY_POSITIVA)
    assert c["puntuacion"] == [4, 5] and c["rv_clinica"] == [7.18, 17.5]
    assert c["concordantes"] is True and c["absorbe"] == "imagen"
    assert c["independencia"] == [pytest.approx(0.9739, abs=5e-4),
                                  pytest.approx(0.9891, abs=5e-4)]
    assert c["dependencia"] == [pytest.approx(0.8388, abs=5e-4)] * 2
    assert c["minima"] == pytest.approx(0.8388, abs=5e-4)
    assert c["maxima"] == pytest.approx(0.9891, abs=5e-4)


def test_con_asma_no_se_y_las_dos_puntuaciones_a_lados_distintos_de_1_no_se_acota():
    """D6: 2 y 3 (0,70 y 1,64) contra la banda (0,87): 0,70 esta del lado de la
    imagen y 1,64 no. Sin concordancia, la horquilla es la de independencia."""
    dos_o_tres = {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
                  "crepitantes": False, "murmullo_disminuido": False,
                  "asma": "no_se"}
    c = combinacion(PREV, dos_o_tres, RV_BANDA)
    assert c["puntuacion"] == [2, 3]
    assert c["concordantes"] is False and c["dependencia"] is None
    assert c["minima"] == pytest.approx(0.0947, abs=5e-4)
    assert c["maxima"] == pytest.approx(0.1969, abs=5e-4)


def test_absorbe_dice_quien_es_la_mas_informativa():
    ceros = {"temperatura_c": 37.0, "frecuencia_cardiaca": 80,
             "crepitantes": False, "murmullo_disminuido": False, "asma": "si"}
    # 0,12 contra la banda 0,87: manda la clinica.
    assert combinacion(PREV, ceros, RV_BANDA)["absorbe"] == "clinica"
    # 4 o 5 (7,18 y 17,5) contra una imagen de 10: |ln 10| = 2,30 esta entre
    # |ln 7,18| = 1,97 y |ln 17,5| = 2,86 -> cambia de una puntuacion a otra.
    cuatro = _hallazgos("no_se", murmullo_disminuido=True)
    assert combinacion(PREV, cuatro, 10.0)["absorbe"] == "mixta"


def test_los_dos_extremos_por_debajo_de_1_tambien_se_acotan():
    """Ambas RV en contra: la independencia da el extremo BAJO y la dependencia
    el ALTO. Los numeros del corpus: negativa del borde, RV 0,5888, puntuacion 0."""
    ceros = {"temperatura_c": 37.0, "frecuencia_cardiaca": 80,
             "crepitantes": False, "murmullo_disminuido": False, "asma": "si"}
    c = combinacion(PREV, ceros, 0.5888)
    assert c["concordantes"] is True and c["absorbe"] == "clinica"
    assert c["independencia"] == [pytest.approx(0.0120, abs=5e-4)]
    assert c["dependencia"] == [pytest.approx(0.0202, abs=5e-4)]
    assert c["minima"] < c["maxima"]


def test_las_posteriores_van_a_cuatro_decimales_y_la_rv_de_imagen_tal_cual():
    c = combinacion(PREV, _hallazgos("si"), 30.29389781009622)
    for x in c["independencia"] + c["dependencia"] + [c["minima"], c["maxima"]]:
        assert x == round(x, 4)
    assert c["rv_imagen"] == 30.29389781009622


def test_combinacion_rechaza_hallazgos_invalidos_y_rv_no_positiva():
    with pytest.raises(HallazgosInvalidos):
        combinacion(PREV, {**SIGNOS_3}, RV_MUY_POSITIVA)      # sin asma
    for rv in (0.0, -1.0, float("nan"), float("inf"), "30", True):
        with pytest.raises(ValueError):
            combinacion(PREV, _hallazgos("si"), rv)
```

- [ ] **Paso 2: correr y ver que falla**

Correr: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_heckerling.py -q`
Esperado: `ImportError: cannot import name 'combinacion'`.

- [ ] **Paso 3: implementar** (añadir al final de `heckerling.py`)

```python
def combinacion(prevalencia: float, hallazgos: Mapping, rv_imagen: float) -> dict:
    """El bloque `combinacion` del contrato (spec §9.2), listo para viajar.

    Para cada puntuacion posible -una, o dos si el asma no se sabe- calcula la
    posterior bajo INDEPENDENCIA (producto de las dos RV) y, solo si todas
    las RV clinicas estan del mismo lado de 1 que la de la imagen, bajo
    DEPENDENCIA TOTAL (la mas informativa sola, spec §7.1-7.2). `minima` y
    `maxima` son el minimo y el maximo de todo eso: la horquilla que
    `Desenlace` imprime. Nunca se anidan dos rangos: se funden aqui.

    `absorbe` dice quien es la mas informativa cuando hay concordancia, para
    que el aviso del informe nombre a quien absorbe a quien sin mentir:
    «la auscultacion no anade nada sobre la imagen» solo es cierto si la
    imagen es la que manda.
    """
    h = validar_hallazgos(hallazgos)
    if (isinstance(rv_imagen, bool) or not isinstance(rv_imagen, (int, float))
            or not math.isfinite(rv_imagen) or rv_imagen <= 0):
        raise ValueError(
            f"rv_imagen debe ser un número positivo, y es {rv_imagen!r}")
    puntuaciones = puntuar(h, h["asma"])
    rv_clinica = [RV_POR_PUNTUACION[p] for p in puntuaciones]
    a_favor = rv_imagen >= 1.0
    concordantes = all((rv >= 1.0) == a_favor for rv in rv_clinica)
    independencia = [combinar(prevalencia, rv, rv_imagen) for rv in rv_clinica]
    dependencia = None
    absorbe = None
    if concordantes:
        dependencia = [combinar(prevalencia, mas_informativa(rv, rv_imagen), 1.0)
                       for rv in rv_clinica]
        quien = {"imagen" if mas_informativa(rv, rv_imagen) == rv_imagen
                 else "clinica" for rv in rv_clinica}
        absorbe = quien.pop() if len(quien) == 1 else "mixta"
    todas = independencia + (dependencia or [])
    return {
        "prevalencia": float(prevalencia),
        "puntuacion": list(puntuaciones),
        "rv_clinica": rv_clinica,
        "rv_imagen": float(rv_imagen),
        "concordantes": concordantes,
        "absorbe": absorbe,
        "independencia": [round(x, 4) for x in independencia],
        "dependencia": (None if dependencia is None
                        else [round(x, 4) for x in dependencia]),
        "minima": round(min(todas), 4),
        "maxima": round(max(todas), 4),
    }
```

- [ ] **Paso 4: correr y ver que pasa**

Correr: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_heckerling.py -q`
Esperado: verde.

- [ ] **Paso 5: commit**

```bash
git add src/copiloto_triaje/servicio/heckerling.py tests/test_heckerling.py && C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_heckerling.py -q && git commit -m "feat(sp4): el bloque combinacion, con la dependencia acotada y no inventada

Independencia y dependencia total son los dos extremos calculables sin
ningun parametro nuevo; se entregan los dos, y solo cuando las RV estan del
mismo lado de 1. Con asma no_se se funde todo en una sola horquilla. Los tres
ejemplos del §8 del spec salen de aqui con sus cifras.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 3: `Motor` conoce la prevalencia y añade el bloque cuando se le pide

**Ficheros:**
- Modificar: `src/copiloto_triaje/servicio/inferencia.py:42-50` (constructor),
  `:57-79` (`cargar`), `:96-155` (`clasificar`)
- Modificar: `tests/test_inferencia.py:30` y `:141` (los dos `Motor(...)`), y
  añadir pruebas al final
- Modificar: `tests/test_aplicacion.py:45` (el `Motor(...)` del fixture)

**Interfaces:**
- Consume: `HallazgosInvalidos`, `validar_hallazgos`, `combinacion` (tareas 1-2).
- Produce, para las tareas 4 y 5:
  - `Motor.__init__(self, modelo, calibrador, umbral, tam_imagen, nombre_modelo, auc_validacion, prevalencia_local)` — `prevalencia_local: float`, obligatorio, en `(0, 1)`; se guarda en `self.prevalencia_local`.
  - `Motor.cargar(ruta_pesos, ruta_calibrador, umbral, auc_validacion, prevalencia_local, arquitectura="efficientnet_b0", ...)` — el parámetro nuevo va **justo después** de `auc_validacion`.
  - `Motor.clasificar(datos_dicom: bytes, hallazgos: Mapping | None = None) -> dict` — con `hallazgos`, la respuesta lleva además `"combinacion"`; sin él, es idéntica a hoy. `hallazgos` mal formados → `ErrorDeInferencia("hallazgos_invalidos", mensaje)`, **antes** de leer el DICOM (D4).

- [ ] **Paso 1: pruebas que fallan**

Primero los fixtures, o nada arranca. En `tests/test_inferencia.py:30-31`:

```python
    return Motor(modelo=Trivial(), calibrador=calibrador, umbral=0.5,
                 tam_imagen=32, nombre_modelo="prueba", auc_validacion=0.88,
                 prevalencia_local=0.1466)
```

En `tests/test_inferencia.py:141` (el `Motor(modelo=Saturado(), ...)`), añade
`prevalencia_local=0.1466` como último argumento. En
`tests/test_aplicacion.py:45-48` igual:

```python
    return Motor(modelo=Trivial(),
                 calibrador=ajustar_calibrador(y, crudo, 0.2215, "prueba"),
                 umbral=0.5, tam_imagen=32, nombre_modelo="prueba",
                 auc_validacion=0.88, prevalencia_local=0.1466)
```

Y al final de `tests/test_inferencia.py`:

```python
# Los cinco datos que el bot manda con la placa (SP4 §9.3): con 38,2 > 37,8,
# 104 > 100 y crepitantes, tres puntos; el asma decide el cuarto.
HALLAZGOS = {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
             "crepitantes": True, "murmullo_disminuido": False, "asma": "si"}
CONTRATO_SP3 = {"probabilidad_cruda", "probabilidad_calibrada",
                "razon_de_verosimilitud", "umbral", "clasificacion",
                "edad_paciente", "modelo", "auc_validacion", "milisegundos"}


def test_sin_hallazgos_la_respuesta_es_la_de_sp3_clave_por_clave(motor, tmp_path):
    """Criterio 2 del spec de SP4, en el nucleo: ni una clave mas."""
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    assert set(motor.clasificar(ruta.read_bytes())) == CONTRATO_SP3


def test_con_hallazgos_la_respuesta_trae_el_bloque_combinacion(motor, tmp_path):
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    salida = motor.clasificar(ruta.read_bytes(), HALLAZGOS)
    assert set(salida) == CONTRATO_SP3 | {"combinacion"}
    c = salida["combinacion"]
    assert c["rv_imagen"] == salida["razon_de_verosimilitud"]
    assert c["prevalencia"] == motor.prevalencia_local == 0.1466
    assert c["puntuacion"] == [3]
    assert 0.0 < c["minima"] <= c["maxima"] < 1.0


def test_unos_hallazgos_invalidos_se_rechazan_antes_de_leer_el_dicom(motor):
    """D4: es barato, y si vienen mal el fallo es de quien llama, no de la
    placa. Por eso gana incluso a un DICOM que no lo es."""
    with pytest.raises(ErrorDeInferencia) as exc:
        motor.clasificar(b"esto no es un dicom",
                         {**HALLAZGOS, "crepitantes": "false"})
    assert exc.value.codigo == "hallazgos_invalidos"
    assert "crepitantes" in str(exc.value)


def test_el_rechazo_por_edad_gana_a_la_combinacion(motor, tmp_path):
    """Con hallazgos perfectos y un menor, la respuesta es el rechazo de
    siempre y nada mas: ninguna rama de error emite una cifra."""
    ruta = tmp_path / "n.dcm"
    crear_dicom(ruta, edad="012Y")
    with pytest.raises(ErrorDeInferencia) as exc:
        motor.clasificar(ruta.read_bytes(), HALLAZGOS)
    assert exc.value.codigo == "fuera_de_alcance"


def test_la_prevalencia_local_es_obligatoria_y_una_probabilidad():
    class Nada(torch.nn.Module):
        def forward(self, x):
            return x.mean(dim=(1, 2, 3)).view(-1, 1)
    rng = np.random.default_rng(1)
    y = (rng.random(200) < 0.2).astype(int)
    cal = ajustar_calibrador(y, rng.random(200), 0.2, "prueba")
    comunes = dict(modelo=Nada(), calibrador=cal, umbral=0.5, tam_imagen=32,
                   nombre_modelo="prueba", auc_validacion=0.88)
    with pytest.raises(TypeError):
        Motor(**comunes)                                  # falta
    for mala in (0.0, 1.0, 1.5, -0.2):
        with pytest.raises(ValueError):
            Motor(**comunes, prevalencia_local=mala)
    assert Motor(**comunes, prevalencia_local=0.1466).prevalencia_local == 0.1466
```

- [ ] **Paso 2: correr y ver que falla**

Correr: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_inferencia.py -q`
Esperado: el fixture revienta con `TypeError: unexpected keyword argument 'prevalencia_local'`.

- [ ] **Paso 3: implementar**

En `inferencia.py`, junto a los demás imports del servicio:

```python
from copiloto_triaje.servicio.heckerling import (
    HallazgosInvalidos, combinacion, validar_hallazgos,
)
```

Constructor (líneas 42-50): la firma pasa a

```python
    def __init__(self, modelo, calibrador: Calibrador, umbral: float,
                 tam_imagen: int, nombre_modelo: str, auc_validacion: float,
                 prevalencia_local: float):
```

y justo después de `self.auc_validacion = float(auc_validacion)`:

```python
        # La probabilidad previa de la combinacion bayesiana (SP4 §5). Es un
        # parametro de despliegue con la misma disciplina que `auc_validacion`:
        # obligatorio, sin default, y se le muestra al profesional en cada
        # informe con combinacion.
        self.prevalencia_local = float(prevalencia_local)
        if not 0.0 < self.prevalencia_local < 1.0:
            raise ValueError("prevalencia_local tiene que ser una probabilidad "
                             f"estrictamente entre 0 y 1, y es {prevalencia_local!r}")
```

`cargar` (líneas 57-58): la firma

```python
    def cargar(cls, ruta_pesos, ruta_calibrador, umbral: float,
               auc_validacion: float, prevalencia_local: float,
               arquitectura: str = "efficientnet_b0",
```

(el resto de los parámetros que ya tenga, sin cambios) y el `return cls(...)`
del final (líneas 78-79) pasa a terminar en `auc_validacion, prevalencia_local)`.
Añade una línea al docstring de `cargar`, debajo de la que explica
`auc_validacion`: `prevalencia_local` es obligatoria por la misma razón.

`clasificar`: la firma pasa a
`def clasificar(self, datos_dicom: bytes, hallazgos=None) -> dict:` y el cuerpo:

```python
        comienzo = time.perf_counter()
        # Los hallazgos se validan ANTES de tocar el DICOM: es barato, y si
        # vienen mal el error es de quien llama -nuestro bot-, no de la placa.
        validados = None
        if hallazgos is not None:
            try:
                validados = validar_hallazgos(hallazgos)
            except HallazgosInvalidos as exc:
                raise ErrorDeInferencia("hallazgos_invalidos", str(exc)) from exc
```

(seguido de todo lo que ya hay, sin cambios, hasta el `return {`). El `return`
se reescribe así: el diccionario se construye igual, con `rv` calculada una
vez, y `combinacion` se añade solo si se pidió:

```python
        rv = self.calibrador.razon_de_verosimilitud(cruda)
        salida = {
            "probabilidad_cruda": round(cruda, 4),
            "probabilidad_calibrada": self.calibrador.calibrar(cruda),
            "razon_de_verosimilitud": rv,
            "umbral": round(self.umbral, 4),
            "clasificacion": ("opacidad_probable" if cruda >= self.umbral
                              else "sin_opacidad_probable"),
            "edad_paciente": edad,
            "modelo": self.nombre_modelo,
            "auc_validacion": self.auc_validacion,
        }
        if validados is not None:
            # SP4 (§9.2): el bloque va DENTRO de la misma respuesta y solo si
            # se pidio. Sin `hallazgos` la respuesta es la de SP3, clave por
            # clave, y eso es un criterio de aceptacion.
            salida["combinacion"] = combinacion(self.prevalencia_local,
                                                validados, rv)
        salida["milisegundos"] = round((time.perf_counter() - comienzo) * 1000, 1)
        return salida
```

El comentario largo que hoy va encima de `"probabilidad_calibrada"` —el de por
qué esas dos NO se redondean— se conserva en su sitio, palabra por palabra: en
el bloque de arriba se omitió solo para no repetirlo aquí. Lo único que cambia
es que `rv` se calcula una vez antes del diccionario y que `milisegundos` se
asigna al final, después de la combinación, para que la cuente.

- [ ] **Paso 4: correr y ver que pasa**

Correr: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_inferencia.py tests/test_aplicacion.py tests/test_heckerling.py -q`
Esperado: verde. `test_aplicacion.py` sigue pasando sin tocar nada más que su
fixture: el tool todavía no acepta `hallazgos` y no hace falta.

- [ ] **Paso 5: commit**

```bash
git add src/copiloto_triaje/servicio/inferencia.py tests/test_inferencia.py tests/test_aplicacion.py && C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_inferencia.py tests/test_aplicacion.py -q && git commit -m "feat(sp4): Motor conoce la prevalencia local y combina cuando se le dan los hallazgos

Sin hallazgos la respuesta es la de SP3 clave por clave. Los hallazgos se
validan antes de leer el DICOM: si vienen mal, el fallo es del que llama.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 4: `PREVALENCIA_LOCAL` obligatoria: `arrancar.py`, el compose y `/salud`

**Ficheros:**
- Modificar: `servidor/arrancar.py:28-38`
- Modificar: `servidor/docker-compose.yml:30-35` (bloque `environment` de `copiloto-mcp`)
- Modificar: `src/copiloto_triaje/servicio/aplicacion.py:150-154` (`/salud`)
- Modificar: `tests/test_arrancar.py`, `tests/test_aplicacion.py`

**Interfaces:**
- Consume: `Motor.cargar(..., auc_validacion, prevalencia_local, ...)` (tarea 3).
- Produce: la variable de entorno `PREVALENCIA_LOCAL` (texto de un float en
  `(0, 1)`), obligatoria; `/salud` devuelve además `"prevalencia_local": float`.
  La frase de la negativa empieza por `Falta la variable de entorno PREVALENCIA_LOCAL`.

- [ ] **Paso 1: pruebas que fallan**

`tests/test_arrancar.py`: el `_arrancar` deja de heredar las DOS variables, y
las pruebas existentes pasan la nueva donde ya pasaban la vieja:

```python
NEGATIVA = "Falta la variable de entorno AUC_VALIDACION"
NEGATIVA_PREVALENCIA = "Falta la variable de entorno PREVALENCIA_LOCAL"
OBLIGATORIAS = ("AUC_VALIDACION", "PREVALENCIA_LOCAL")


def _arrancar(**entorno):
    """Lanza `arrancar.py` con rutas de pesos inexistentes a proposito.

    Asi el arranque muere siempre, y lo que la prueba mira es DE QUE muere: si
    de una variable que falta o de los pesos que no estan. Nunca llega a
    `uvicorn.run`. Se quitan del entorno LAS DOS obligatorias, para que una
    puesta en la maquina de quien corre las pruebas no las deje pasar.
    """
    env = {k: v for k, v in os.environ.items() if k not in OBLIGATORIAS}
    env["PYTHONPATH"] = str(RAIZ / "src")
    env["RUTA_PESOS"] = str(RAIZ / "no_existen_estos_pesos.pt")
    env["RUTA_CALIBRADOR"] = str(RAIZ / "no_existe_este_calibrador.json")
    env.update(entorno)
    return subprocess.run([sys.executable, str(ARRANCAR)], env=env,
                          capture_output=True, text=True, timeout=300)
```

En `test_con_auc_de_validacion_el_arranque_pasa_de_esa_comprobacion` la
llamada pasa a `_arrancar(AUC_VALIDACION="0.8827", PREVALENCIA_LOCAL="0.1466")`
(con las dos: lo que esa prueba afirma es que llega hasta los pesos). Y se
añaden:

```python
def test_sin_prevalencia_local_el_arranque_falla_diciendo_cual_falta():
    """SP4 §5 y criterio 8: la misma disciplina que AUC_VALIDACION, por la
    misma razon. Es una cifra que acaba delante de un clinico."""
    resultado = _arrancar(AUC_VALIDACION="0.8827")

    assert resultado.returncode != 0
    salida = resultado.stdout + resultado.stderr
    assert NEGATIVA_PREVALENCIA in salida, salida
    assert NEGATIVA not in salida, salida
    assert "no_existen_estos_pesos.pt" not in salida, salida


def test_una_prevalencia_que_no_es_probabilidad_se_rechaza_al_arrancar():
    resultado = _arrancar(AUC_VALIDACION="0.8827", PREVALENCIA_LOCAL="1.5")

    assert resultado.returncode != 0
    salida = resultado.stdout + resultado.stderr
    assert "entre 0 y 1" in salida, salida
    assert "no_existen_estos_pesos.pt" not in salida, salida


def test_el_compose_declara_la_prevalencia_con_su_fuente():
    """Restriccion 3: sin default en el codigo, con valor y fuente en el
    compose. Que la fuente este escrita al lado es parte del diseno (§5)."""
    compose = (RAIZ / "servidor" / "docker-compose.yml").read_text(encoding="utf-8")
    assert 'PREVALENCIA_LOCAL: "0.1466"' in compose
    assert "134/914" in compose and "Heckerling" in compose
```

En `tests/test_aplicacion.py`, junto a `test_salud_responde_listo`:

```python
@pytest.mark.asyncio
async def test_salud_publica_la_prevalencia_local(motor):
    """Es la prueba de despliegue de SP4: un /salud sin esta clave es un
    contenedor anterior (tests/test_contrato_sp4.py se salta por esto)."""
    async with cliente_de(motor) as cliente:
        assert (await cliente.get("/salud")).json()["prevalencia_local"] == 0.1466
```

- [ ] **Paso 2: correr y ver que falla**

Correr: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_arrancar.py tests/test_aplicacion.py -q -k "prevalencia or salud or compose"`
Esperado: rojas las cuatro nuevas (la de `arrancar` porque hoy `Motor.cargar`
recibe cuatro argumentos y revienta por `TypeError`, no por la negativa).

- [ ] **Paso 3: implementar**

`servidor/arrancar.py`, después de `AUC_VALIDACION = float(...)` y antes de
`motor = Motor.cargar(...)`:

```python
# La prevalencia previa de la combinacion bayesiana (SP4 §5), con la MISMA
# disciplina que AUC_VALIDACION y por la misma razon: es una cifra que acaba
# delante de un clinico en cada informe con combinacion, y un valor por defecto
# silencioso sobreviviria a un cambio de entorno sin que nadie lo mirara.
# Arranca en 0,1466 -134/914, la cohorte de derivacion de Heckerling- y se
# cambia en el compose, con su fuente al lado, cuando haya dato local.
if not os.environ.get("PREVALENCIA_LOCAL"):
    raise SystemExit(
        "Falta la variable de entorno PREVALENCIA_LOCAL. Es la probabilidad "
        "previa con la que se combina la regla clinica con la imagen y se le "
        "muestra al profesional en cada informe, asi que no tiene valor por "
        "defecto. Declarala en el docker-compose.yml (ya viene puesta) o "
        "pasala al arrancar, p. ej. PREVALENCIA_LOCAL=0.1466.")
PREVALENCIA_LOCAL = float(os.environ["PREVALENCIA_LOCAL"])
if not 0.0 < PREVALENCIA_LOCAL < 1.0:
    raise SystemExit(
        f"PREVALENCIA_LOCAL vale {PREVALENCIA_LOCAL!r} y tiene que ser una "
        "probabilidad estrictamente entre 0 y 1 (p. ej. 0.1466).")

motor = Motor.cargar(RUTA_PESOS, RUTA_CALIBRADOR, UMBRAL, AUC_VALIDACION,
                     PREVALENCIA_LOCAL)
```

`servidor/docker-compose.yml`, dentro de `environment:` de `copiloto-mcp`,
después de `AUC_VALIDACION: "0.8827"` y antes del comentario de
`OMP_NUM_THREADS`:

```yaml
      # 0.1466 = 134/914: la prevalencia de la cohorte de DERIVACION de la
      # regla de Heckerling (Ann Intern Med 1990;113:664-70, via PMC7422644,
      # tabla 2). Es la probabilidad previa de la combinacion bayesiana (SP4
      # §5) y se le ensena al profesional en cada informe con combinacion.
      # Sin default en el codigo a proposito, como AUC_VALIDACION: cuando
      # haya dato del entorno real se cambia AQUI, con su fuente en este
      # comentario. No es el 0.2215 del calibrador de imagen: RSNA son placas
      # ya indicadas, no la poblacion que llega a consulta con tos.
      PREVALENCIA_LOCAL: "0.1466"
```

`aplicacion.py`, `/salud`:

```python
    @api.get("/salud")
    def salud() -> dict[str, Any]:
        return {"estado": "listo", "modelo": motor.nombre_modelo,
                "umbral": motor.umbral,
                "calibrador": motor.calibrador.procedencia,
                # SP4: la prueba de que este contenedor es el nuevo. Sin esta
                # clave, `tests/test_contrato_sp4.py` se salta y lo dice.
                "prevalencia_local": motor.prevalencia_local}
```

- [ ] **Paso 4: correr y ver que pasa**

Correr: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_arrancar.py tests/test_aplicacion.py -q`
Esperado: verde (las de `arrancar` tardan: cargan torch en un subproceso).

- [ ] **Paso 5: commit**

```bash
git add servidor/arrancar.py servidor/docker-compose.yml src/copiloto_triaje/servicio/aplicacion.py tests/test_arrancar.py tests/test_aplicacion.py && C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_arrancar.py tests/test_aplicacion.py -q && git commit -m "feat(sp4): PREVALENCIA_LOCAL es obligatoria y /salud la publica

Sin default, como AUC_VALIDACION y por la misma razon: es una cifra que
acaba delante de un clinico. El compose la declara a 0.1466 (134/914, la
cohorte de Heckerling) con su fuente al lado.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 5: las dos puertas aceptan `hallazgos`, y el contrato en vivo

**Ficheros:**
- Modificar: `src/copiloto_triaje/servicio/aplicacion.py:90-135` (tool), `:156-183` (`/inferir`)
- Modificar: `tests/test_aplicacion.py`
- Modificar: `tests/test_contrato_mcp.py:64-67` (**solo** la constante `ARRANCAR`)
- Modificar: `docs/sp3-operacion.md:160` (el mismo `docker run`)
- Crear: `tests/test_contrato_sp4.py`

**Interfaces:**
- Consume: `Motor.clasificar(datos, hallazgos)` (tarea 3).
- Produce: por MCP, `clasificar_radiografia(dicom_base64: str, hallazgos: dict | None = None)`;
  por REST, `POST /inferir` con el fichero en `archivo` y, opcional, un campo
  de formulario `hallazgos` con el objeto en JSON. Error nuevo en las dos
  puertas: código `hallazgos_invalidos` (`ToolError` por MCP; 422 con
  `{"codigo": "hallazgos_invalidos", "detalle": ...}` por REST).

- [ ] **Paso 1: pruebas que fallan**

En `tests/test_aplicacion.py`, `_llamar_por_mcp` gana un parámetro:

```python
async def _llamar_por_mcp(cliente, dicom, hallazgos=None) -> httpx.Response:
    """Llama a la herramienta por la puerta MCP. `dicom` son los bytes del
    fichero, o ya el texto base64 cuando la prueba quiere uno invalido.
    `hallazgos`, si se da, viaja como segundo argumento del tool (SP4)."""
    b64 = dicom if isinstance(dicom, str) else base64.b64encode(dicom).decode()
    argumentos = {"dicom_base64": b64}
    if hallazgos is not None:
        argumentos["hallazgos"] = hallazgos
    return await cliente.post(
        "/mcp", headers=CABECERAS_MCP,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": "clasificar_radiografia",
                         "arguments": argumentos}})
```

Y al final del fichero:

```python
# Los cinco datos de SP4 §9.3. Con asma `no_se` salen DOS puntuaciones: 3 y 4.
HALLAZGOS = {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
             "crepitantes": True, "murmullo_disminuido": False,
             "asma": "no_se"}
CONTRATO_SP3 = {"probabilidad_cruda", "probabilidad_calibrada",
                "razon_de_verosimilitud", "umbral", "clasificacion",
                "edad_paciente", "modelo", "auc_validacion", "milisegundos"}


@pytest.mark.asyncio
async def test_la_herramienta_mcp_con_hallazgos_anade_exactamente_una_clave(
        motor, tmp_path):
    """La hermana de `test_la_herramienta_mcp_devuelve_exactamente_las_claves_del_contrato`,
    que sigue afirmando el conjunto de SP3 SIN hallazgos (criterio 2)."""
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    async with cliente_de(motor) as cliente:
        salida = _extraer_resultado(
            await _llamar_por_mcp(cliente, ruta.read_bytes(), HALLAZGOS))
    assert set(salida) == CONTRATO_SP3 | {"combinacion"}
    c = salida["combinacion"]
    assert c["puntuacion"] == [3, 4]
    assert c["rv_imagen"] == salida["razon_de_verosimilitud"]
    assert c["prevalencia"] == 0.1466


@pytest.mark.asyncio
async def test_rest_acepta_los_hallazgos_como_json_en_el_formulario(motor, tmp_path):
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    async with cliente_de(motor) as cliente:
        r = await cliente.post("/inferir",
                               files={"archivo": ("a.dcm", ruta.read_bytes())},
                               data={"hallazgos": json.dumps(HALLAZGOS)})
    assert r.status_code == 200, r.text
    assert r.json()["combinacion"]["puntuacion"] == [3, 4]


@pytest.mark.asyncio
async def test_las_dos_puertas_dan_la_misma_combinacion(motor, tmp_path):
    """El respaldo REST tiene que decir lo mismo que MCP tambien en lo nuevo."""
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    datos = ruta.read_bytes()
    async with cliente_de(motor) as cliente:
        por_rest = (await cliente.post(
            "/inferir", files={"archivo": ("a.dcm", datos)},
            data={"hallazgos": json.dumps(HALLAZGOS)})).json()
        por_mcp = _extraer_resultado(await _llamar_por_mcp(cliente, datos, HALLAZGOS))
    sin_tiempo = lambda d: {k: v for k, v in d.items() if k != "milisegundos"}
    assert sin_tiempo(por_mcp) == sin_tiempo(por_rest)


@pytest.mark.asyncio
async def test_las_dos_puertas_rechazan_igual_unos_hallazgos_invalidos(motor, tmp_path):
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    datos = ruta.read_bytes()
    malos = {**HALLAZGOS, "asma": "quizas"}
    async with cliente_de(motor) as cliente:
        r = await cliente.post("/inferir",
                               files={"archivo": ("a.dcm", datos)},
                               data={"hallazgos": json.dumps(malos)})
        assert r.status_code == 422
        assert r.json()["codigo"] == "hallazgos_invalidos"
        assert "asma" in r.json()["detalle"]
        respuesta = await _llamar_por_mcp(cliente, datos, malos)
    assert _codigo_del_error_mcp(respuesta) == "hallazgos_invalidos"


@pytest.mark.asyncio
async def test_rest_rechaza_unos_hallazgos_que_no_son_un_objeto_json(motor, tmp_path):
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    async with cliente_de(motor) as cliente:
        for texto in ("{no es json", '"una cadena"', "[1, 2]"):
            r = await cliente.post("/inferir",
                                   files={"archivo": ("a.dcm", ruta.read_bytes())},
                                   data={"hallazgos": texto})
            assert r.status_code == 422, texto
            assert r.json()["codigo"] == "hallazgos_invalidos", texto


@pytest.mark.asyncio
async def test_el_rechazo_por_edad_no_trae_combinacion_ni_por_mcp_ni_por_rest(motor, tmp_path):
    """Restriccion 9: ninguna rama de error emite una cifra, tampoco la
    nueva. Un menor con hallazgos perfectos recibe el rechazo de siempre."""
    ruta = tmp_path / "n.dcm"
    crear_dicom(ruta, edad="012Y")
    datos = ruta.read_bytes()
    async with cliente_de(motor) as cliente:
        r = await cliente.post("/inferir", files={"archivo": ("n.dcm", datos)},
                               data={"hallazgos": json.dumps(HALLAZGOS)})
        assert r.status_code == 422 and r.json()["codigo"] == "fuera_de_alcance"
        assert "combinacion" not in r.text
        texto = _texto_del_error_mcp(await _llamar_por_mcp(cliente, datos, HALLAZGOS))
    assert "combinacion" not in texto and "fuera_de_alcance" in texto
```

`tests/test_contrato_mcp.py:64-67`, **solo esto**:

```python
ARRANCAR = ("docker run -d --rm --name copiloto-prueba "
            "-p 127.0.0.1:18000:8000 "
            "-e UMBRAL=0.4258 -e AUC_VALIDACION=0.8827 "
            "-e PREVALENCIA_LOCAL=0.1466 -e OMP_NUM_THREADS=2 "
            "copiloto-mcp:0.1.0")
```

y en `docs/sp3-operacion.md:160` el mismo `docker run` gana
`-e PREVALENCIA_LOCAL=0.1466 ` justo después de `-e AUC_VALIDACION=0.8827 `.

`tests/test_contrato_sp4.py`, nuevo:

```python
# tests/test_contrato_sp4.py
"""Lo que el bot de SP4 espera del copiloto DESPLEGADO: el bloque `combinacion`.

Aparte de `test_contrato_mcp.py` a proposito: las diez comprobaciones de aquel
fichero son el criterio 2 del spec de SP4 -pasan sin modificarse- y su unico
cambio es la constante del `docker run`, que ahora necesita PREVALENCIA_LOCAL.

NECESITA EL SERVIDOR VIVO, y con SP4. Sin servidor se salta, como aquel. Con
un servidor ANTERIOR a SP4 -su /salud no publica `prevalencia_local`- tambien
se salta, diciendo que la imagen que responde es vieja: eso no es un fallo del
contrato, es que todavia no se ha redesplegado. Se lee con `pytest -rs`.
"""
import base64
import json
import urllib.request

import pytest

from test_contrato_mcp import ARRANCAR, BASE, dicom_adulto  # noqa: F401

CONTRATO_SP3 = {"probabilidad_cruda", "probabilidad_calibrada",
                "razon_de_verosimilitud", "umbral", "clasificacion",
                "edad_paciente", "modelo", "auc_validacion", "milisegundos"}
HALLAZGOS = {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
             "crepitantes": True, "murmullo_disminuido": False,
             "asma": "no_se"}


@pytest.fixture(scope="module", autouse=True)
def copiloto_con_sp4() -> dict:
    try:
        with urllib.request.urlopen(f"{BASE}/salud", timeout=3) as r:
            salud = json.load(r)
    except (OSError, ValueError) as e:
        pytest.skip(
            f"CONTRATO SP4 SIN VERIFICAR: {BASE}/salud no responde "
            f"({type(e).__name__}). Se queda sin comprobar el bloque "
            f"`combinacion` (§9.2 de SP4). Levanta el contenedor y repite:  "
            f"{ARRANCAR}  -- o apunta COPILOTO_URL a uno que ya este vivo.")
    if salud.get("estado") != "listo":
        pytest.skip(f"CONTRATO SP4 SIN VERIFICAR: estado={salud.get('estado')!r}")
    if "prevalencia_local" not in salud:
        pytest.skip(
            "CONTRATO SP4 SIN VERIFICAR: el copiloto que responde es ANTERIOR "
            "a SP4 (su /salud no publica `prevalencia_local`). Reconstruye la "
            "imagen con el compose actual y repite.")
    return salud


def _llamar_con(b64: str, hallazgos) -> dict:
    """Como `_llamar` de test_contrato_mcp.py, con el segundo argumento. No se
    importa aquel para no tocarle ni la firma."""
    argumentos = {"dicom_base64": b64}
    if hallazgos is not None:
        argumentos["hallazgos"] = hallazgos
    cuerpo = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "clasificar_radiografia",
                   "arguments": argumentos}}).encode()
    pet = urllib.request.Request(
        f"{BASE}/mcp", data=cuerpo,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    texto = urllib.request.urlopen(pet, timeout=30).read().decode()
    for linea in texto.splitlines():
        if linea.startswith("data: "):
            return json.loads(linea[6:])
    pytest.fail(f"la respuesta no traia ninguna linea 'data: ': {texto[:200]}")


def test_con_hallazgos_llega_el_bloque_combinacion(dicom_adulto, copiloto_con_sp4):
    sc = _llamar_con(base64.b64encode(dicom_adulto).decode(),
                     HALLAZGOS)["result"]["structuredContent"]
    assert set(sc) == CONTRATO_SP3 | {"combinacion"}
    c = sc["combinacion"]
    assert c["rv_imagen"] == sc["razon_de_verosimilitud"]
    assert c["prevalencia"] == copiloto_con_sp4["prevalencia_local"]
    assert c["puntuacion"] == [3, 4]
    assert 0.0 < c["minima"] <= c["maxima"] < 1.0


def test_sin_hallazgos_la_respuesta_desplegada_sigue_siendo_la_de_sp3(dicom_adulto):
    """Criterio 2, contra el contenedor: ni una clave mas."""
    sc = _llamar_con(base64.b64encode(dicom_adulto).decode(),
                     None)["result"]["structuredContent"]
    assert set(sc) == CONTRATO_SP3


def test_unos_hallazgos_invalidos_se_rechazan_con_su_codigo_en_segundo_campo(dicom_adulto):
    """El codigo va en la posicion que `Leer respuesta` sabe leer (§10.3 de
    SP3), aunque el bot no conozca este codigo y lo trate como
    error_no_reconocido (D4)."""
    r = _llamar_con(base64.b64encode(dicom_adulto).decode(),
                    {**HALLAZGOS, "asma": "quizas"})["result"]
    assert r["isError"] is True
    partes = r["content"][0]["text"].split(":")
    assert partes[1].strip() == "hallazgos_invalidos", r["content"][0]["text"]
    assert r.get("structuredContent") in (None, {})
```

- [ ] **Paso 2: correr y ver que falla**

Correr: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_aplicacion.py -q`
Esperado: las seis nuevas rojas (por MCP el SDK rechaza el argumento
desconocido o lo ignora y no llega `combinacion`; por REST 200 sin bloque).
`tests/test_contrato_sp4.py` se salta sin contenedor: comprueba con `-rs` que el
mensaje del skip es el de «no responde».

- [ ] **Paso 3: implementar**

`aplicacion.py`: en los imports, `json` (módulo estándar) y `Form` de
`fastapi` (añádelo a la línea donde ya se importan `File` y `UploadFile`).
El tool:

```python
    @servidor.tool(
        name="clasificar_radiografia",
        description="Recibe una radiografia de torax en DICOM (base64) y "
                    "devuelve la evidencia de imagen: probabilidad calibrada "
                    "y razon de verosimilitud para combinar con la regla "
                    "clinica. Con `hallazgos` -temperatura_c, "
                    "frecuencia_cardiaca, crepitantes, murmullo_disminuido y "
                    "asma (si/no/no_se)- devuelve ademas `combinacion`: la "
                    "probabilidad posterior por la regla de Heckerling. Solo "
                    "valida para pacientes de 18 a 100 anios.")
    def clasificar_radiografia(dicom_base64: str,
                               hallazgos: dict[str, Any] | None = None
                               ) -> dict[str, Any]:
```

y el `return motor.clasificar(datos)` del final pasa a
`return motor.clasificar(datos, hallazgos)`. El comentario largo de arriba
sobre `ToolError` sigue valiendo: `hallazgos_invalidos` sale por el mismo
`except ErrorDeInferencia`.

`/inferir`:

```python
    @api.post("/inferir")
    async def inferir(archivo: UploadFile = File(...),
                      hallazgos: str | None = Form(None)):
        # `hallazgos` llega como texto JSON en el formulario, porque un
        # multipart no lleva objetos. Aqui solo se parsea; lo valida `Motor`,
        # igual que por MCP: las dos puertas tienen que decir lo mismo.
        hallazgos_dict = None
        if hallazgos is not None:
            try:
                hallazgos_dict = json.loads(hallazgos)
            except ValueError:
                hallazgos_dict = None
            if not isinstance(hallazgos_dict, dict):
                return JSONResponse(status_code=422, content={
                    "codigo": "hallazgos_invalidos",
                    "detalle": "«hallazgos» debe ser un objeto JSON con los "
                               "cinco campos de la regla de Heckerling."})
```

(sigue la lectura por trozos, sin cambios) y el `return motor.clasificar(datos)`
pasa a `return motor.clasificar(datos, hallazgos_dict)`.

- [ ] **Paso 4: correr y ver que pasa**

Correr: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_aplicacion.py tests/test_contrato_mcp.py tests/test_contrato_sp4.py -q -rs`
Esperado: `test_aplicacion.py` verde entero, incluida
`test_la_herramienta_mcp_devuelve_exactamente_las_claves_del_contrato` sin
tocar; los dos de contrato **saltados** con sus mensajes. Comprueba que el
diff de `tests/test_contrato_mcp.py` es solo la constante:
`git diff --stat tests/test_contrato_mcp.py` debe decir `1 file changed, 2 insertions(+), 1 deletion(-)` (o cifras equivalentes a esa única constante).

- [ ] **Paso 5: commit**

```bash
git add src/copiloto_triaje/servicio/aplicacion.py tests/test_aplicacion.py tests/test_contrato_mcp.py tests/test_contrato_sp4.py docs/sp3-operacion.md && C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_aplicacion.py -q && git commit -m "feat(sp4): las dos puertas aceptan hallazgos y devuelven combinacion

Por MCP como segundo argumento del tool; por REST como campo JSON del
formulario. Las dos rechazan igual unos hallazgos invalidos, y sin hallazgos
la respuesta sigue siendo la de SP3: las diez comprobaciones del contrato
pasan sin tocarlas, y las del bloque nuevo van en un fichero aparte que se
salta -y lo dice- contra un contenedor anterior a SP4.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 6: `A base64` manda los cinco datos con la placa

**Ficheros:**
- Modificar: `n8n/copiloto-profesional.json` (nodo `A base64`, campo `parameters.jsCode`)
- Modificar: `tests/profesional.mjs` (sección H, antes de `console.log("\nI. Leer respuesta, ...`)

**Interfaces:**
- Consume: `$('Decidir').first().json` trae `signos` (los cuatro, tipados,
  desde `sesiones_profesional.signos`) y `sintomas` (el cuestionario o `null`;
  solo en el paso 6).
- Produce: en `cuerpo_jsonrpc`, `params.arguments` es `{dicom_base64}` o
  `{dicom_base64, hallazgos}` con `hallazgos = {temperatura_c, frecuencia_cardiaca, crepitantes, murmullo_disminuido, asma}` **solo** cuando los cuatro signos tienen su tipo y `sintomas.asma ∈ {si, no, no_se}`. Las claves de salida del nodo no cambian: `chat_id, cuerpo_jsonrpc, t0, via`.

- [ ] **Paso 1: pruebas que fallan**

En `tests/profesional.mjs`, justo antes de la línea
`console.log("\nI. Leer respuesta, contra las respuestas LITERALES del contenedor");`:

```js
// --------------------------------------------------------------------------
// SP4 §9.3: con la placa viajan los CINCO datos de Heckerling -los cuatro
// signos crudos y el asma con sus tres estados-, y solo si estan los cinco.
// Los cortes (37,8 °C; 100 lpm) NO se aplican aqui: van los numeros, y los
// corta Python, que es donde se prueban.
// --------------------------------------------------------------------------
async function aBase64Con(decidir) {
  const r = await correr(codigo("A base64"), ENTRADA_BIN, { Decidir: decidir }, {});
  return { salida: r[0].json,
           argumentos: JSON.parse(r[0].json.cuerpo_jsonrpc).params.arguments };
}
ok("con los cuatro signos y el asma, `hallazgos` viaja con los cinco datos crudos",
   await (async () => {
     const { argumentos: a } = await aBase64Con(
       { chat_id: 7, t0: 1, signos: SIGNOS, sintomas: SINTOMAS });
     return a.dicom_base64 === B64_HOLA &&
            JSON.stringify(a.hallazgos) === JSON.stringify({
              temperatura_c: 38.2, frecuencia_cardiaca: 104, crepitantes: true,
              murmullo_disminuido: false, asma: "no_se" });
   })());
for (const [etiqueta, decidir] of [
  ["sin signos", { chat_id: 7, t0: 1, signos: {}, sintomas: SINTOMAS }],
  ["con un signo de menos",
   { chat_id: 7, t0: 1, sintomas: SINTOMAS,
     signos: { temperatura_c: 38.2, frecuencia_cardiaca: 104, crepitantes: true } }],
  ["con un booleano en texto",
   { chat_id: 7, t0: 1, sintomas: SINTOMAS,
     signos: Object.assign({}, SIGNOS, { crepitantes: "true" }) }],
  ["con una temperatura en texto",
   { chat_id: 7, t0: 1, sintomas: SINTOMAS,
     signos: Object.assign({}, SIGNOS, { temperatura_c: "38,2" }) }],
  ["sin cuestionario", { chat_id: 7, t0: 1, signos: SIGNOS, sintomas: null }],
  ["con un asma que no es de los tres",
   { chat_id: 7, t0: 1, signos: SIGNOS,
     sintomas: Object.assign({}, SINTOMAS, { asma: "quizas" }) }],
  ["sin signos ni sintomas (la entrada de las pruebas de arriba)", { chat_id: 7, t0: 123 }],
]) {
  const { argumentos: a } = await aBase64Con(decidir);
  ok(`${etiqueta}: NO viaja \`hallazgos\` y el cuerpo es el de SP3`,
     !("hallazgos" in a) && Object.keys(a).join(",") === "dicom_base64",
     JSON.stringify(a));
}
ok("las claves de salida del nodo no cambian (§5.4): los hallazgos van solo en el cuerpo",
   await (async () => {
     const { salida: s } = await aBase64Con(
       { chat_id: 7, t0: 1, signos: SIGNOS, sintomas: SINTOMAS });
     return Object.keys(s).sort().join(",") === "chat_id,cuerpo_jsonrpc,t0,via";
   })());
```

- [ ] **Paso 2: correr y ver que falla**

Correr: `node tests/profesional.mjs > /tmp/prof.txt; echo "salida $?"; grep -c FALLO /tmp/prof.txt`
Esperado: salida 1 y 2 FALLOS (la primera prueba y la de las claves pasan o
fallan según el nodo viejo; las del bucle pasan porque hoy nunca viaja nada).
Léelo: lo que tiene que estar rojo es «viaja con los cinco datos crudos».

- [ ] **Paso 3: parchear el nodo**

Escribe `C:/Users/[retirado]/AppData/Local/Temp/claude/.../scratchpad/sp4_patch_a_base64.py`
(en el scratchpad de la sesión; con el tool Write, nunca con `echo`/heredoc por
las comillas y los acentos) y córrelo desde la raíz del repo con
`PYTHONIOENCODING=utf-8`:

```python
# -*- coding: utf-8 -*-
"""Parchea el jsCode de un nodo del export, y lo reescribe EN SU MISMO FORMATO."""
import io
import json
import sys

RUTA = "n8n/copiloto-profesional.json"
crudo = io.open(RUTA, encoding="utf-8", newline="").read()
w = json.loads(crudo)


def volcar(w):
    return json.dumps(w, ensure_ascii=False, indent=2) + "\n"


# D11: si esto no reproduce el fichero byte a byte, el diff se llenaria de
# ruido y no se veria el nodo. Comprobado el 26-sep: indent=2, sin escapar
# unicode, LF, salto final.
if volcar(w) != crudo:
    sys.exit("el export no esta en el formato que este script reproduce")


def nodo(nombre):
    return next(n for n in w["nodes"] if n["name"] == nombre)


def cambiar(n, viejo, nuevo, veces=1):
    js = n["parameters"]["jsCode"]
    if js.count(viejo) != veces:
        sys.exit("ancla aparece %d veces, esperaba %d: %r"
                 % (js.count(viejo), veces, viejo[:60]))
    n["parameters"]["jsCode"] = js.replace(viejo, nuevo)


n = nodo("A base64")

cambiar(n, "const d = $('Decidir').first().json;\n",
        "const d = $('Decidir').first().json;\n"
        "\n"
        "// SP4 §9.3: con la placa viajan los CINCO datos de la regla de Heckerling\n"
        "// -los cuatro signos y el asma con sus tres estados- y NADA mas del\n"
        "// cuestionario. Solo si estan los cinco con su tipo: sin ellos no hay\n"
        "// puntuacion, el copiloto contesta como hasta ahora (sin `combinacion`) y\n"
        "// `Desenlace` lo explica con SIN COMBINAR. Los cortes (37,8 °C; 100 lpm) NO\n"
        "// se aplican aqui: van los numeros y los corta Python, que es donde se\n"
        "// prueban.\n"
        "const ESTADOS_ASMA = ['si', 'no', 'no_se'];\n"
        "function hallazgosDe(g, s) {\n"
        "  const num = (v) => typeof v === 'number' && Number.isFinite(v);\n"
        "  if (!g || !num(g.temperatura_c) || !num(g.frecuencia_cardiaca) ||\n"
        "      typeof g.crepitantes !== 'boolean' ||\n"
        "      typeof g.murmullo_disminuido !== 'boolean') { return null; }\n"
        "  if (!s || ESTADOS_ASMA.indexOf(s.asma) < 0) { return null; }\n"
        "  return {temperatura_c: g.temperatura_c,\n"
        "          frecuencia_cardiaca: g.frecuencia_cardiaca,\n"
        "          crepitantes: g.crepitantes,\n"
        "          murmullo_disminuido: g.murmullo_disminuido,\n"
        "          asma: s.asma};\n"
        "}\n"
        "const hallazgos = hallazgosDe(d.signos, d.sintomas);\n")

cambiar(n, "  params: {name: 'clasificar_radiografia', arguments: {dicom_base64: b64}},\n",
        "  params: {name: 'clasificar_radiografia',\n"
        "           arguments: hallazgos ? {dicom_base64: b64, hallazgos: hallazgos}\n"
        "                                : {dicom_base64: b64}},\n")

io.open(RUTA, "w", encoding="utf-8", newline="").write(volcar(w))
print("A base64 parcheado")
```

Comprueba con `git diff --stat n8n/copiloto-profesional.json` que el cambio
es una sola línea del JSON (el `jsCode` es una cadena).

- [ ] **Paso 4: correr y ver que pasa**

Correr: `node tests/profesional.mjs > /tmp/prof.txt; echo "salida $?"; tail -2 /tmp/prof.txt`
Esperado: `salida 0`, `TODO VERDE`. Y `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_flujo_profesional.py -q` sigue verde (las de módulo; las conducidas se saltan).

- [ ] **Paso 5: commit**

```bash
git add n8n/copiloto-profesional.json tests/profesional.mjs && node tests/profesional.mjs > /tmp/prof.txt && git commit -m "feat(sp4): A base64 manda los cinco datos de Heckerling con la placa

Solo cuando estan los cinco con su tipo; si falta algo, el cuerpo es el de
SP3 y el informe lo explica. Los cortes no se aplican aqui: van los numeros.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 7: `Leer respuesta` valida el bloque si viene

**Ficheros:**
- Modificar: `n8n/copiloto-profesional.json` (nodo `Leer respuesta`)
- Modificar: `tests/profesional.mjs` (los fixtures `C_*` junto a `R_NEGATIVA_BORDE`; pruebas en la sección I, antes de `ok("el base64 del DICOM NO viaja en la salida de este nodo (§5.4)"`)

**Interfaces:**
- Consume: el bloque de D5 dentro de `structuredContent.combinacion`.
- Produce: `resultado` sale con `combinacion` **intacta** si es válida o
  ausente; si viene y está mal formada, `error_cod = 'error_no_reconocido'` y
  `resultado = null` (D9). Los fixtures `C_POS_3`, `C_POS_0`, `C_POS_3_4`,
  `C_BANDA_0`, `C_BORDE_0`, `C_NEG_0` quedan definidos a nivel de módulo para
  la tarea 8.

- [ ] **Paso 1: los fixtures y las pruebas que fallan**

En `tests/profesional.mjs`, justo después del bloque `const R_NEGATIVA_BORDE = {...};`:

```js
// Bloques `combinacion` (SP4 §9.2) CALCULADOS con heckerling.py -prevalencia
// 0,1466, RV del §4 del spec y la RV real de cada placa de arriba-, no
// tecleados. Los cuatro decimales son los que el servidor manda.
//   C_POS_3    puntuacion 3 con la positiva clara: el ejemplo 1 del §8.
//   C_POS_0    puntuacion 0 con la positiva clara: discordantes, ejemplo 2.
//   C_POS_3_4  asma no_se (3 o 4) con la positiva clara: una sola horquilla.
//   C_BANDA_0  puntuacion 0 con la banda: concordantes por debajo de 1 y los
//              dos extremos redondean igual (2 %).
//   C_BORDE_0  puntuacion 0 con la negativa del borde: por debajo de 1, y la
//              mas informativa es la CLINICA.
//   C_NEG_0    puntuacion 0 con la negativa clara: todo por debajo del 1 %.
const C_POS_3 = {
  prevalencia: 0.1466, puntuacion: [3], rv_clinica: [1.64],
  rv_imagen: R_POSITIVA.razon_de_verosimilitud, concordantes: true,
  absorbe: "imagen", independencia: [0.8951], dependencia: [0.8388],
  minima: 0.8388, maxima: 0.8951 };
const C_POS_0 = {
  prevalencia: 0.1466, puntuacion: [0], rv_clinica: [0.12],
  rv_imagen: R_POSITIVA.razon_de_verosimilitud, concordantes: false,
  absorbe: null, independencia: [0.3844], dependencia: null,
  minima: 0.3844, maxima: 0.3844 };
const C_POS_3_4 = {
  prevalencia: 0.1466, puntuacion: [3, 4], rv_clinica: [1.64, 7.18],
  rv_imagen: R_POSITIVA.razon_de_verosimilitud, concordantes: true,
  absorbe: "imagen", independencia: [0.8951, 0.9739],
  dependencia: [0.8388, 0.8388], minima: 0.8388, maxima: 0.9739 };
const C_BANDA_0 = {
  prevalencia: 0.1466, puntuacion: [0], rv_clinica: [0.12],
  rv_imagen: R_BANDA.razon_de_verosimilitud, concordantes: true,
  absorbe: "clinica", independencia: [0.0176], dependencia: [0.0202],
  minima: 0.0176, maxima: 0.0202 };
const C_BORDE_0 = {
  prevalencia: 0.1466, puntuacion: [0], rv_clinica: [0.12],
  rv_imagen: R_NEGATIVA_BORDE.razon_de_verosimilitud, concordantes: true,
  absorbe: "clinica", independencia: [0.0120], dependencia: [0.0202],
  minima: 0.0120, maxima: 0.0202 };
const C_NEG_0 = {
  prevalencia: 0.1466, puntuacion: [0], rv_clinica: [0.12],
  rv_imagen: R_NEGATIVA.razon_de_verosimilitud, concordantes: true,
  absorbe: "clinica", independencia: [0.0003], dependencia: [0.0028],
  minima: 0.0003, maxima: 0.0028 };
```

Y en la sección I, justo antes de
`ok("el base64 del DICOM NO viaja en la salida de este nodo (§5.4)"`:

```js
// SP4 (D9): el bloque `combinacion` es OPCIONAL -un copiloto anterior a SP4
// no lo manda y el informe sale sin el-, pero si viene tiene que estar ENTERO
// y con sus tipos, por lo mismo que los cuatro numeros del §8: un campo que
// falta no es una cifra que se pueda imprimir.
const leerCon = async (r) => (await correr(
  codigo("Leer respuesta"), { json: http200(sseExito(r)) }, { Decidir: dResp }))[0].json;
ok("sin `combinacion` (copiloto anterior a SP4) se lee como siempre", await (async () => {
  const s = await leerCon(R_POSITIVA);
  return s.error_cod === "N" && !("combinacion" in s.resultado);
})());
for (const [etiqueta, c] of [["ejemplo 1", C_POS_3], ["discordante", C_POS_0],
                             ["asma no_se", C_POS_3_4], ["banda", C_BANDA_0]]) {
  const s = await leerCon(Object.assign({}, R_POSITIVA, { combinacion: c }));
  ok(`${etiqueta}: un bloque valido pasa ENTERO y tal cual`,
     s.error_cod === "N" && JSON.stringify(s.resultado.combinacion) === JSON.stringify(c),
     JSON.stringify(s.error_cod));
}
const ROTOS = [
  ["minima > maxima", Object.assign({}, C_POS_3, { minima: 0.9, maxima: 0.8 })],
  ["puntuacion fuera de 0-5", Object.assign({}, C_POS_3, { puntuacion: [6] })],
  ["tres puntuaciones", Object.assign({}, C_POS_3, { puntuacion: [3, 4, 5], rv_clinica: [1, 2, 3], independencia: [0.1, 0.2, 0.3], dependencia: [0.1, 0.2, 0.3] })],
  ["rv_clinica de otro largo", Object.assign({}, C_POS_3, { rv_clinica: [1.64, 7.18] })],
  ["concordantes sin dependencia", Object.assign({}, C_POS_3, { dependencia: null })],
  ["discordantes CON dependencia", Object.assign({}, C_POS_0, { dependencia: [0.5] })],
  ["absorbe desconocido", Object.assign({}, C_POS_3, { absorbe: "nadie" })],
  ["una posterior como texto", Object.assign({}, C_POS_3, { independencia: ["0,89"] })],
  ["una posterior de mas de 1", Object.assign({}, C_POS_3, { maxima: 1.2 })],
  ["prevalencia de 0", Object.assign({}, C_POS_3, { prevalencia: 0 })],
  ["rv_imagen negativa", Object.assign({}, C_POS_3, { rv_imagen: -1 })],
  ["el bloque no es un objeto", "84-90"],
  ["el bloque es una lista", [0.84, 0.9]],
];
for (const [etiqueta, c] of ROTOS) {
  const s = await leerCon(Object.assign({}, R_POSITIVA, { combinacion: c }));
  ok(`${etiqueta}: error_no_reconocido, y NO llega al redactor`,
     s.error_cod === "error_no_reconocido" && s.resultado === null,
     JSON.stringify(s.error_cod));
}
```

- [ ] **Paso 2: correr y ver que falla**

Correr: `node tests/profesional.mjs > /tmp/prof.txt; echo "salida $?"; grep -c FALLO /tmp/prof.txt`
Esperado: 13 FALLOS (los `ROTOS`: hoy todo pasa de largo).

- [ ] **Paso 3: parchear el nodo**

Con el mismo esqueleto de script de la tarea 6 (cópialo entero a
`sp4_patch_leer_respuesta.py`), `n = nodo("Leer respuesta")` y un solo cambio:

```python
cambiar(n, "if (!completo) {\n  return salir('error_no_reconocido', cuerpoCrudo.slice(0, 500));\n}\n",
        "if (!completo) {\n  return salir('error_no_reconocido', cuerpoCrudo.slice(0, 500));\n}\n"
        "\n"
        "// El bloque `combinacion` de SP4 (§9.2) es OPCIONAL -un copiloto anterior a\n"
        "// SP4 no lo manda y el informe sale sin el- pero si viene tiene que estar\n"
        "// ENTERO y con sus tipos, por lo mismo que los cuatro numeros de arriba: un\n"
        "// campo que falta no es una cifra que se pueda imprimir. Se rechaza entero.\n"
        "if (r.combinacion !== undefined && r.combinacion !== null) {\n"
        "  const c = r.combinacion;\n"
        "  const num = (v) => typeof v === 'number' && Number.isFinite(v);\n"
        "  const prob = (v) => num(v) && v >= 0 && v <= 1;\n"
        "  const esObjeto = !!c && typeof c === 'object' && !Array.isArray(c);\n"
        "  const n = esObjeto && Array.isArray(c.puntuacion) ? c.puntuacion.length : 0;\n"
        "  const lista = (v, cond) => Array.isArray(v) && v.length === n && v.every(cond);\n"
        "  const valido = esObjeto && (n === 1 || n === 2) &&\n"
        "    num(c.prevalencia) && c.prevalencia > 0 && c.prevalencia < 1 &&\n"
        "    lista(c.puntuacion, (p) => Number.isInteger(p) && p >= 0 && p <= 5) &&\n"
        "    lista(c.rv_clinica, (v) => num(v) && v > 0) &&\n"
        "    num(c.rv_imagen) && c.rv_imagen > 0 &&\n"
        "    typeof c.concordantes === 'boolean' &&\n"
        "    lista(c.independencia, prob) &&\n"
        "    (c.concordantes\n"
        "      ? lista(c.dependencia, prob) && ['imagen', 'clinica', 'mixta'].indexOf(c.absorbe) >= 0\n"
        "      : c.dependencia === null && c.absorbe === null) &&\n"
        "    prob(c.minima) && prob(c.maxima) && c.minima <= c.maxima;\n"
        "  if (!valido) {\n"
        "    return salir('error_no_reconocido', cuerpoCrudo.slice(0, 500));\n"
        "  }\n"
        "}\n")
```

- [ ] **Paso 4: correr y ver que pasa**

Correr: `node tests/profesional.mjs > /tmp/prof.txt; echo "salida $?"; tail -2 /tmp/prof.txt` → `salida 0`, `TODO VERDE`.
Y `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_flujo_profesional.py tests/test_reproducir_casos.py -q` verde (los redactores de `pruebas/redactar.mjs` ejecutan este mismo nodo).

- [ ] **Paso 5: commit**

```bash
git add n8n/copiloto-profesional.json tests/profesional.mjs && node tests/profesional.mjs > /tmp/prof.txt && git commit -m "feat(sp4): Leer respuesta valida el bloque combinacion si viene

Opcional -un copiloto anterior a SP4 no lo manda-, pero si viene tiene que
estar entero y con sus tipos, como los cuatro numeros del §8. Mal formado se
rechaza entero como error_no_reconocido, y Desenlace confia en lo que pasa.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 8: `Desenlace` redacta `COMBINADO` (y `SIN COMBINAR`)

**Ficheros:**
- Modificar: `n8n/copiloto-profesional.json` (nodo `Desenlace`)
- Modificar: `tests/profesional.mjs` (sección «I ante» y una sección P nueva antes de `console.log("\nO. los teclados ...`)
- Modificar: `tests/test_flujo_profesional.py:617-638` (`test_ninguna_rama_de_error_puede_emitir_una_cifra_de_probabilidad`)

**Interfaces:**
- Consume: `e.resultado.combinacion` (validado por la tarea 7), `signosValidos`,
  `SINTOMAS.asma`, `dec`, `prob`, `propio`, `redactarSintomas`, `redactarSignos`.
- Produce: el informe con resultado lleva, entre `EXPLORADO` y el descargo, un
  bloque `COMBINADO — …` (tres líneas: cabecera, factores, ⚠️) o
  `SIN COMBINAR — …` (una línea). El descargo pasa a ser
  `Esto no es un diagnóstico.` (D8). El helper `rvTexto(v)` queda a nivel de
  módulo del nodo.

- [ ] **Paso 1: pruebas que fallan**

(a) En la sección «I ante» (`LO QUE EL MODELO AFIRMA vs LO QUE ADVIERTE`), la
lista del `for` gana un caso:

```js
for (const [etiqueta, r] of [["positiva", R_POSITIVA], ["banda", R_BANDA],
                             ["negativa", R_NEGATIVA],
                             ["negativa del borde", R_NEGATIVA_BORDE],
                             ["positiva con combinacion", Object.assign({}, R_POSITIVA, { combinacion: C_POS_3 })],
                             ["banda con combinacion", Object.assign({}, R_BANDA, { combinacion: C_BANDA_0 })]]) {
```

(b) Una sección nueva, justo antes de
`console.log("\nO. los teclados repiten los prefijos de la tabla, y solo esos");`:

```js
console.log("\nP. SP4 §8: el cuarto bloque, COMBINADO");
// --------------------------------------------------------------------------
// Las cifras de estos literales estan CALCULADAS (heckerling.py), no son
// ilustraciones: son los tres ejemplos del §8 del spec de SP4 y los casos que
// la tabla del ⚠️ del §8 distingue.
// --------------------------------------------------------------------------
const SINTOMAS_SI = Object.assign({}, SINTOMAS, { asma: "si" });
const conCombinacion = async (c, sint = SINTOMAS_SI, sig = SIGNOS, r = R_POSITIVA) =>
  (await desenlace({ error_cod: "N", detalle: "",
                     resultado: Object.assign({}, r, { combinacion: c }),
                     sintomas: sint, signos: sig }, U, D)).texto;
const bloqueCombinado = (t) => t.split(NL + NL).find(
  (b) => b.startsWith("COMBINADO") || b.startsWith("SIN COMBINAR")) || "";

const tC3 = await conCombinacion(C_POS_3);
const b3 = bloqueCombinado(tC3).split(NL);
ok("ejemplo 1 del §8: la cabecera, literal",
   b3[0] === "COMBINADO — entre 84 % y 90 % de probabilidad de opacidad compatible", b3[0]);
ok("ejemplo 1: los tres factores y la puntuacion, literal",
   b3[1] === "(prevalencia 14,7 % × clínica 1,64 × imagen 30,3; Heckerling 3 de 5)", b3[1]);
ok("ejemplo 1: el aviso de dependencia con sus dos numeros, literal",
   b3[2] === "⚠️ La auscultación y la imagen miran la misma consolidación, así que no son " +
             "pruebas independientes: el 90 % supone que cada una aporta información nueva, " +
             "y el 84 %, que la auscultación no añade nada sobre la imagen. Decide usted.", b3[2]);
ok("ejemplo 1: tres lineas y nada mas", b3.length === 3, String(b3.length));
ok("el bloque va DESPUES de lo explorado y ANTES del descargo", (() => {
  const bl = tC3.split(NL + NL);
  const i = bl.findIndex((b) => b.startsWith("COMBINADO"));
  return i > 0 && bl[i - 1].includes("EXPLORADO") && bl[i + 1] === "Esto no es un diagnóstico.";
})(), tC3);
ok("el descargo ya no promete la siguiente entrega (D8)",
   !tC3.includes("siguiente entrega") && tC3.includes("Esto no es un diagnóstico."));
ok("el resultado se guarda ENTERO, con el bloque (§10 de SP4)", await (async () => {
  const s = await desenlace({ error_cod: "N", detalle: "",
                              resultado: Object.assign({}, R_POSITIVA, { combinacion: C_POS_3 }),
                              sintomas: SINTOMAS_SI, signos: SIGNOS }, U, D);
  return JSON.stringify(JSON.parse(descodificar(s.resultado_cod)).combinacion) === JSON.stringify(C_POS_3);
})());

const b0 = bloqueCombinado(await conCombinacion(C_POS_0)).split(NL);
ok("ejemplo 2: discordantes -> un numero, no una horquilla",
   b0[0] === "COMBINADO — 38 % de probabilidad de opacidad compatible", b0[0]);
ok("ejemplo 2: los factores, con la RV clinica de dos decimales",
   b0[1] === "(prevalencia 14,7 % × clínica 0,12 × imagen 30,3; Heckerling 0 de 5)", b0[1]);
ok("ejemplo 2: el aviso dice que apuntan en sentidos opuestos",
   b0[2] === "⚠️ La clínica y la imagen apuntan en sentidos opuestos, y además no son " +
             "pruebas independientes: la cifra es orientativa. Decide usted.", b0[2]);

const b34 = bloqueCombinado(await conCombinacion(C_POS_3_4, SINTOMAS)).split(NL);
ok("asma no_se: UNA sola horquilla que funde las dos causas",
   b34[0] === "COMBINADO — entre 84 % y 97 % de probabilidad de opacidad compatible", b34[0]);
ok("asma no_se: las dos RV clinicas y las dos puntuaciones, segun tenga asma o no",
   b34[1] === "(prevalencia 14,7 % × clínica 1,64–7,18 × imagen 30,3; Heckerling 3 o 4 de 5, según tenga asma o no)", b34[1]);
ok("asma no_se: el aviso nombra el extremo de independencia (97) y el de dependencia (84)",
   b34[2].includes("el 97 % supone que cada una aporta información nueva, y el 84 %, " +
                   "que la auscultación no añade nada sobre la imagen"), b34[2]);
ok("nunca se anidan dos rangos: un solo «entre» en todo el bloque",
   (b34.join(" ").match(/entre /g) || []).length === 1, b34.join(" | "));

const bB = bloqueCombinado(await conCombinacion(C_BANDA_0, SINTOMAS_SI, SIGNOS, R_BANDA)).split(NL);
ok("un rango que se cierra deja de ser un rango: «2 %» a secas",
   bB[0] === "COMBINADO — 2 % de probabilidad de opacidad compatible", bB[0]);
ok("banda: la RV de la imagen con dos decimales por debajo de 10",
   bB[1] === "(prevalencia 14,7 % × clínica 0,12 × imagen 0,87; Heckerling 0 de 5)", bB[1]);
ok("y con los extremos iguales el aviso va sin numeros",
   bB[2] === "⚠️ La auscultación y la imagen miran la misma consolidación, así que no son " +
             "pruebas independientes: la cifra puede exagerar. Decide usted.", bB[2]);

const bE = bloqueCombinado(await conCombinacion(C_BORDE_0, SINTOMAS_SI, SIGNOS, R_NEGATIVA_BORDE)).split(NL);
ok("las dos RV por debajo de 1: la horquilla sale igual",
   bE[0] === "COMBINADO — entre 1 % y 2 % de probabilidad de opacidad compatible", bE[0]);
ok("...y el aviso nombra bien cada extremo, y que aqui absorbe la CLINICA",
   bE[2] === "⚠️ La auscultación y la imagen miran la misma consolidación, así que no son " +
             "pruebas independientes: el 1 % supone que cada una aporta información nueva, " +
             "y el 2 %, que la imagen no añade nada sobre la auscultación. Decide usted.", bE[2]);

const bN = bloqueCombinado(await conCombinacion(C_NEG_0, SINTOMAS_SI, SIGNOS, R_NEGATIVA)).split(NL);
ok("nunca 0 %: «< 1 %», y por eso el rango se cierra",
   bN[0] === "COMBINADO — < 1 % de probabilidad de opacidad compatible", bN[0]);
ok("nunca 100 %: «> 99 %», tambien con un 1,0 exacto", await (async () => {
  const c = Object.assign({}, C_POS_3, { independencia: [1], dependencia: [0.9957],
                                         minima: 0.9957, maxima: 1 });
  const b = bloqueCombinado(await conCombinacion(c)).split(NL);
  return b[0] === "COMBINADO — > 99 % de probabilidad de opacidad compatible";
})());
ok("ni 0 %: con un 0,0 exacto sale «< 1 %»", await (async () => {
  const c = Object.assign({}, C_NEG_0, { independencia: [0], dependencia: [0], minima: 0, maxima: 0 });
  return bloqueCombinado(await conCombinacion(c, SINTOMAS_SI, SIGNOS, R_NEGATIVA))
    .startsWith("COMBINADO — < 1 % de probabilidad");
})());
ok("absorbe «mixta»: el aviso dice que solo cuenta la mas informativa", await (async () => {
  const c = Object.assign({}, C_POS_3_4, { absorbe: "mixta" });
  return bloqueCombinado(await conCombinacion(c, SINTOMAS)).split(NL)[2]
    .includes("y el 84 %, que solo cuenta la más informativa de las dos. Decide usted.");
})());

// SIN COMBINAR: los tres motivos, en su orden, y nunca una cifra.
const SIN_SIGNOS = "SIN COMBINAR — faltan signos de la exploración, así que no hay puntuación de Heckerling.";
const SIN_CUESTIONARIO = "SIN COMBINAR — falta el cuestionario del paciente: el asma entra en la puntuación de Heckerling.";
const SIN_BLOQUE = "SIN COMBINAR — el copiloto no devolvió la combinación en esta respuesta.";
ok("sin los cuatro signos: lo dice, y no imprime COMBINADO", await (async () => {
  const t = await conCombinacion(C_POS_3, SINTOMAS_SI, {});
  return t.includes(SIN_SIGNOS) && !t.includes("COMBINADO");
})());
ok("sin cuestionario: dice que falta el asma", (await conCombinacion(C_POS_3, null)).includes(SIN_CUESTIONARIO));
ok("con un asma fuera de los tres: lo mismo",
   (await conCombinacion(C_POS_3, Object.assign({}, SINTOMAS, { asma: "quizas" }))).includes(SIN_CUESTIONARIO));
ok("con todo pero sin bloque (copiloto anterior a SP4): lo dice", await (async () => {
  const t = await conCombinacion(undefined);
  return t.includes(SIN_BLOQUE) && !t.includes("COMBINADO") && t.includes("Esto no es un diagnóstico.");
})());
ok("sin cuestionario: SIN COMBINAR va entre EXPLORADO y el descargo, donde iria COMBINADO", await (async () => {
  const bl = (await conCombinacion(C_POS_3, null)).split(NL + NL);
  const i = bl.findIndex((b) => b.startsWith("SIN COMBINAR"));
  return i > 0 && bl[i - 1].includes("EXPLORADO") && bl[i + 1] === "Esto no es un diagnóstico.";
})());

// A base64 y Desenlace tienen que estar de acuerdo en CUANDO hay combinacion:
// si uno manda los hallazgos y el otro dice que faltan, el clinico lee una
// contradiccion. Se comprueba por conducta, sobre las mismas entradas.
for (const [etiqueta, sig, sint] of [
  ["completo", SIGNOS, SINTOMAS],
  ["sin signos", {}, SINTOMAS],
  ["sin cuestionario", SIGNOS, null],
  ["asma raro", SIGNOS, Object.assign({}, SINTOMAS, { asma: "x" })],
  ["booleano en texto", Object.assign({}, SIGNOS, { crepitantes: "true" }), SINTOMAS],
  ["temperatura en texto", Object.assign({}, SIGNOS, { temperatura_c: "38,2" }), SINTOMAS],
]) {
  const { argumentos: a } = await aBase64Con({ chat_id: 7, t0: 1, signos: sig, sintomas: sint });
  const t = await conCombinacion(C_POS_3, sint, sig);
  const manda = "hallazgos" in a;
  const faltan = t.includes(SIN_SIGNOS) || t.includes(SIN_CUESTIONARIO);
  ok(`${etiqueta}: A base64 manda hallazgos (${manda}) exactamente cuando Desenlace no dice que faltan`,
     manda === !faltan, t.split(NL).find((l) => l.startsWith("SIN COMBINAR")) || "");
}
```

(c) `tests/test_flujo_profesional.py`, en
`test_ninguna_rama_de_error_puede_emitir_una_cifra_de_probabilidad`, después de
`assert "probabilidad_calibrada" not in fuera`:

```python
    # SP4: las cifras de la combinacion tambien se formatean SOLO ahi dentro.
    # `redactarCombinacion` esta anidada en `redactarResultado` a proposito.
    assert "combinacion" in dentro
    assert "combinacion" not in fuera
    assert "COMBINADO" in dentro and "COMBINADO" not in fuera
```

- [ ] **Paso 2: correr y ver que falla**

`node tests/profesional.mjs > /tmp/prof.txt; echo "salida $?"; grep -c FALLO /tmp/prof.txt` → unos 30 FALLOS; y
`C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_flujo_profesional.py -q -k cifra` → rojo (`"combinacion" in dentro`).

- [ ] **Paso 3: parchear el nodo**

Mismo esqueleto (`sp4_patch_desenlace.py`), `n = nodo("Desenlace")`, cuatro cambios:

```python
# (a) El descargo (D8).
cambiar(n, "const DESCARGO = 'La combinación de imagen y clínica llega en la siguiente ' +\n"
           "                 'entrega. Esto no es un diagnóstico.';\n",
        "// Desde SP4 la combinacion YA esta -es el bloque COMBINADO de\n"
        "// `redactarCombinacion`-, asi que el descargo se queda con lo que sigue\n"
        "// siendo verdad. Va en TODOS los informes con resultado, con o sin bloque.\n"
        "const DESCARGO = 'Esto no es un diagnóstico.';\n")

# (b) rvTexto sube a nivel de modulo: lo usan la imagen y, ahora, la clinica.
cambiar(n, "const prob = (x) => {\n"
           "  const v = Number(x);\n"
           "  if (v > 0 && v < 0.005) { return '< 0,01'; }\n"
           "  if (v < 1 && v > 0.995) { return '> 0,99'; }\n"
           "  return dec(v, 2);\n"
           "};\n",
        "const prob = (x) => {\n"
        "  const v = Number(x);\n"
        "  if (v > 0 && v < 0.005) { return '< 0,01'; }\n"
        "  if (v < 1 && v > 0.995) { return '> 0,99'; }\n"
        "  return dec(v, 2);\n"
        "};\n"
        "\n"
        "// La RV con uno o dos decimales, como el §8: dos por debajo de 10, uno por\n"
        "// encima, que es donde el segundo decimal ya no informa de nada. Sirve para\n"
        "// la de la imagen y, desde SP4, para la clinica.\n"
        "const rvTexto = (v) => dec(v, v < 10 ? 2 : 1);\n")

cambiar(n, "  const rv = r.razon_de_verosimilitud;\n"
           "  // La RV con uno o dos decimales, como el §8: dos por debajo de 10, uno por\n"
           "  // encima, que es donde el segundo decimal ya no informa de nada.\n"
           "  const rvTexto = dec(rv, rv < 10 ? 2 : 1);\n",
        "  const rv = r.razon_de_verosimilitud;\n")
cambiar(n, "    ? 'multiplica por ' + rvTexto +\n", "    ? 'multiplica por ' + rvTexto(rv) +\n")
cambiar(n, "    : 'reduce a ' + rvTexto +\n", "    : 'reduce a ' + rvTexto(rv) +\n")

# (c) La funcion anidada, al principio de redactarResultado.
cambiar(n, "function redactarResultado(r, sintomas, signos, hayComentario) {\n"
           "  const positivo = r.clasificacion === POSITIVA;\n",
        "function redactarResultado(r, sintomas, signos, hayComentario) {\n"
        "  // §8 de SP4: EL CUARTO BLOQUE. Anidada a proposito: la propiedad estatica\n"
        "  // «las cifras solo se formatean dentro de redactarResultado»\n"
        "  // (test_flujo_profesional.py) parte el fichero por esta funcion, y esto\n"
        "  // tiene que quedar DENTRO. Todo lo que imprime sale de un bloque que `Leer\n"
        "  // respuesta` ya valido, de literales de aqui y de `signosValidos`.\n"
        "  function redactarCombinacion(c, sint, sig) {\n"
        "    // Sin combinacion no se inventa una (§8.1): se dice por que falta, en el\n"
        "    // orden en que el flujo lo sabe.\n"
        "    if (!signosValidos(sig)) {\n"
        "      return 'SIN COMBINAR — faltan signos de la exploración, así que no hay ' +\n"
        "             'puntuación de Heckerling.';\n"
        "    }\n"
        "    if (!sint || !propio.call(SINTOMAS.asma, String(sint.asma))) {\n"
        "      return 'SIN COMBINAR — falta el cuestionario del paciente: el asma entra ' +\n"
        "             'en la puntuación de Heckerling.';\n"
        "    }\n"
        "    if (!c) {\n"
        "      return 'SIN COMBINAR — el copiloto no devolvió la combinación en esta ' +\n"
        "             'respuesta.';\n"
        "    }\n"
        "    // Porcentaje ENTERO, y nunca 0 % ni 100 % (§8.1): la convencion de\n"
        "    // `prob()` con cero decimales. Un 0,0 o un 1,0 exactos tambien caen aqui.\n"
        "    const pct = (x) => {\n"
        "      const v = Number(x);\n"
        "      if (v < 0.01) { return '< 1 %'; }\n"
        "      if (v > 0.99) { return '> 99 %'; }\n"
        "      return Math.round(v * 100) + ' %';\n"
        "    };\n"
        "    // Un rango que se cierra deja de ser un rango (§8.1).\n"
        "    const lo = pct(c.minima), hi = pct(c.maxima);\n"
        "    const horquilla = lo === hi ? lo : 'entre ' + lo + ' y ' + hi;\n"
        "    const dosPuntuaciones = c.puntuacion.length === 2;\n"
        "    const heckerling = 'Heckerling ' + (dosPuntuaciones\n"
        "      ? c.puntuacion[0] + ' o ' + c.puntuacion[1] + ' de 5, según tenga asma o no'\n"
        "      : c.puntuacion[0] + ' de 5');\n"
        "    const lineas = [\n"
        "      'COMBINADO — ' + horquilla + ' de probabilidad de opacidad compatible',\n"
        "      '(prevalencia ' + dec(c.prevalencia * 100, 1) + ' % × clínica ' +\n"
        "        c.rv_clinica.map(rvTexto).join('–') + ' × imagen ' + rvTexto(c.rv_imagen) +\n"
        "        '; ' + heckerling + ')',\n"
        "    ];\n"
        "    // EL ⚠️ VA SIEMPRE (§7.3), y dice algo distinto en cada caso porque tiene\n"
        "    // que ser verdad en cada uno (la tabla del §8 del spec).\n"
        "    if (!c.concordantes) {\n"
        "      lineas.push('⚠️ La clínica y la imagen apuntan en sentidos opuestos, y además ' +\n"
        "                  'no son pruebas independientes: la cifra es orientativa. ' +\n"
        "                  'Decide usted.');\n"
        "      return lineas.join('\\n');\n"
        "    }\n"
        "    // Con las dos RV por encima de 1 la independencia da el extremo ALTO y la\n"
        "    // dependencia el BAJO; por debajo de 1, al reves. Se nombra cada uno por\n"
        "    // su numero, asi que la frase es cierta en los dos sentidos.\n"
        "    const aFavor = c.rv_imagen >= 1;\n"
        "    const ind = pct(aFavor ? Math.max.apply(null, c.independencia)\n"
        "                           : Math.min.apply(null, c.independencia));\n"
        "    const dep = pct(aFavor ? Math.min.apply(null, c.dependencia)\n"
        "                           : Math.max.apply(null, c.dependencia));\n"
        "    // «La auscultacion no anade nada sobre la imagen» solo es verdad si la\n"
        "    // imagen es la mas informativa; `absorbe` lo dice, y se lee por propiedad\n"
        "    // propia como todas las tablas de este nodo.\n"
        "    const ABSORBE = {\n"
        "      imagen: 'que la auscultación no añade nada sobre la imagen',\n"
        "      clinica: 'que la imagen no añade nada sobre la auscultación',\n"
        "      mixta: 'que solo cuenta la más informativa de las dos',\n"
        "    };\n"
        "    const quien = propio.call(ABSORBE, String(c.absorbe)) ? ABSORBE[c.absorbe]\n"
        "                                                         : ABSORBE.mixta;\n"
        "    lineas.push('⚠️ La auscultación y la imagen miran la misma consolidación, así ' +\n"
        "                'que no son pruebas independientes: ' + (ind === dep\n"
        "      ? 'la cifra puede exagerar. Decide usted.'\n"
        "      : 'el ' + ind + ' supone que cada una aporta información nueva, y el ' +\n"
        "        dep + ', ' + quien + '. Decide usted.'));\n"
        "    return lineas.join('\\n');\n"
        "  }\n"
        "\n"
        "  const positivo = r.clasificacion === POSITIVA;\n")

# (d) El bloque se coloca entre lo explorado y el descargo.
cambiar(n, "  bloques.push(redactarSintomas(sintomas) + '\\n' + redactarSignos(signos));\n"
           "  bloques.push(DESCARGO);\n",
        "  bloques.push(redactarSintomas(sintomas) + '\\n' + redactarSignos(signos));\n"
        "  bloques.push(redactarCombinacion(r.combinacion, sintomas, signos));\n"
        "  bloques.push(DESCARGO);\n")
```

Ojo con los `'\\n'` del script: dentro del `jsCode` tiene que quedar el
escape de JavaScript `'\n'` (barra y ene), no un salto de línea real; el
`'\\n'` de Python lo produce. Comprueba después con
`grep -c "join('\\\\n')" ` o, más simple, abriendo el nodo con Python y
buscando `"lineas.join('\\n')"` en la cadena.

- [ ] **Paso 4: correr y ver que pasa**

`node tests/profesional.mjs > /tmp/prof.txt; echo "salida $?"; tail -2 /tmp/prof.txt` → `salida 0`, `TODO VERDE`. Lee también la sección «I bis»: si un literal nuevo sale sin tilde o tutea, ahí aparece.
`C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_flujo_profesional.py tests/test_reproducir_casos.py -q` → verde.

- [ ] **Paso 5: tres mutaciones a mano, y deshacerlas**

Sobre el `jsCode` (con un script de un solo `cambiar` cada vez, y
`git checkout -- n8n/copiloto-profesional.json` después de cada una):
1. `if (v < 0.01) { return '< 1 %'; }` → `if (v < 0.001)` → rojas «nunca 0 %» y «ni 0 %».
2. `const horquilla = lo === hi ? lo : ...` → `const horquilla = 'entre ' + lo + ' y ' + hi;` → roja «un rango que se cierra».
3. `if (!c.concordantes) {` → `if (false) {` → roja «ejemplo 2: el aviso dice que apuntan en sentidos opuestos» (y otras).

- [ ] **Paso 6: commit**

```bash
git add n8n/copiloto-profesional.json tests/profesional.mjs tests/test_flujo_profesional.py && node tests/profesional.mjs > /tmp/prof.txt && C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_flujo_profesional.py -q && git commit -m "feat(sp4): Desenlace redacta COMBINADO, con la horquilla y el aviso que toca en cada caso

Tres lineas: la horquilla en porcentaje entero -que se cierra en un numero
cuando sus extremos redondean igual, y nunca dice 0 ni 100-, los tres
factores con la puntuacion, y el ⚠️ de dependencia, cuyo texto depende del
caso porque tiene que ser verdad en cada uno. Sin combinacion no se inventa:
SIN COMBINAR dice por que. El descargo se queda con lo que sigue siendo
cierto: esto no es un diagnostico.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 9: el corpus `--sin-bots` manda lo mismo que el bot

**Ficheros:**
- Modificar: `pruebas/reproducir_casos.py:341-355` (`llamar_al_copiloto`) y `:1271` (su llamada)
- Modificar: `tests/test_reproducir_casos.py` (añadir al final)

**Interfaces:**
- Consume: `SIGNOS`, `SINTOMAS` del propio módulo.
- Produce: `hallazgos_del_caso(sintomas, signos=SIGNOS) -> dict | None` y
  `llamar_al_copiloto(url, ruta_dcm, hallazgos=None, tiempo_limite=120)`.

- [ ] **Paso 1: pruebas que fallan** (al final de `tests/test_reproducir_casos.py`, con
los imports que el fichero ya use para llegar a `pruebas.reproducir_casos`; si
importa el módulo como `rc`, usa ese nombre)

```python
def test_el_modo_sin_bots_manda_los_cinco_datos_que_manda_el_bot():
    """SP4 §9.3: si el arnes llamara sin `hallazgos`, el corpus diria
    «SIN COMBINAR» para casos en los que el bot real combina, y el corpus
    dejaria de ser un registro de lo que el clinico ve."""
    from pruebas.reproducir_casos import SIGNOS, SINTOMAS, hallazgos_del_caso
    assert hallazgos_del_caso(SINTOMAS, SIGNOS) == {
        "temperatura_c": 38.2, "frecuencia_cardiaca": 104,
        "crepitantes": True, "murmullo_disminuido": False, "asma": "no_se"}
    assert hallazgos_del_caso(None, SIGNOS) is None
    assert hallazgos_del_caso({**SINTOMAS, "asma": "quizas"}, SIGNOS) is None
    assert hallazgos_del_caso(SINTOMAS, {}) is None
    assert hallazgos_del_caso(SINTOMAS, {**SIGNOS, "crepitantes": "true"}) is None


def test_la_llamada_sin_bots_lleva_los_hallazgos_en_el_json_rpc(tmp_path, monkeypatch):
    import io
    import json
    import urllib.request
    from pruebas import reproducir_casos as rc

    capturada = {}

    class Respuesta(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def falso_urlopen(pet, timeout=None):
        capturada["cuerpo"] = json.loads(pet.data)
        return Respuesta(b"event: message\r\ndata: {}\r\n\r\n")

    monkeypatch.setattr(urllib.request, "urlopen", falso_urlopen)
    dcm = tmp_path / "a.dcm"
    dcm.write_bytes(b"x")

    rc.llamar_al_copiloto("http://x/mcp", dcm, rc.hallazgos_del_caso(rc.SINTOMAS))
    assert capturada["cuerpo"]["params"]["arguments"]["hallazgos"]["asma"] == "no_se"
    rc.llamar_al_copiloto("http://x/mcp", dcm, None)
    assert "hallazgos" not in capturada["cuerpo"]["params"]["arguments"]
```

- [ ] **Paso 2: correr y ver que falla**

`C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_reproducir_casos.py -q -k "sin_bots or json_rpc"` → `ImportError: hallazgos_del_caso`.

- [ ] **Paso 3: implementar**

En `pruebas/reproducir_casos.py`, después de `BOTONES_PACIENTE = (...)`:

```python
# Los cinco datos que `A base64` manda con la placa (SP4 §9.3), sacados de lo
# MISMO que el bot usa: los cuatro signos y el asma del cuestionario. Si falta
# algo o viene con otro tipo, `None`, y el copiloto contesta sin combinacion,
# exactamente como haria el bot. Es la misma regla que `hallazgosDe` en el nodo.
ESTADOS_ASMA = ("si", "no", "no_se")


def hallazgos_del_caso(sintomas, signos=SIGNOS):
    if not sintomas or sintomas.get("asma") not in ESTADOS_ASMA:
        return None
    if not signos:
        return None
    numeros = ("temperatura_c", "frecuencia_cardiaca")
    booleanos = ("crepitantes", "murmullo_disminuido")
    for k in numeros:
        v = signos.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
    for k in booleanos:
        if not isinstance(signos.get(k), bool):
            return None
    return {**{k: signos[k] for k in numeros + booleanos},
            "asma": sintomas["asma"]}
```

`llamar_al_copiloto`:

```python
def llamar_al_copiloto(url, ruta_dcm, hallazgos=None, tiempo_limite=120):
    """Un `tools/call` suelto, como el del nodo `Llamar al copiloto`.

    `hallazgos` viaja como segundo argumento del tool cuando lo hay (SP4), que
    es lo que hace `A base64`. Devuelve (statusCode, cuerpo). `neverError:
    true` en el nodo significa que un 413 o un 500 llegan al codigo como
    respuesta, no como excepcion: aqui se hace lo mismo para que `Leer
    respuesta` vea lo que veria en n8n.
    """
    b64 = base64.b64encode(pathlib.Path(ruta_dcm).read_bytes()).decode()
    argumentos = {"dicom_base64": b64}
    if hallazgos is not None:
        argumentos["hallazgos"] = hallazgos
    cuerpo = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "clasificar_radiografia",
                   "arguments": argumentos}}).encode()
```

(el resto de la función igual). Y la llamada de la línea ~1271:

```python
            estado, cuerpo = llamar_al_copiloto(
                url_copiloto, caso["ruta_dcm"], hallazgos_del_caso(sintomas, signos))
```

(`sintomas` y `signos` ya están calculados cuatro líneas más arriba, con lo que
el flujo guardó cuando existe.)

- [ ] **Paso 4: correr y ver que pasa**

`C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_reproducir_casos.py -q` → verde.

- [ ] **Paso 5: commit**

```bash
git add pruebas/reproducir_casos.py tests/test_reproducir_casos.py && C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_reproducir_casos.py -q && git commit -m "feat(sp4): el corpus sin bots manda los mismos cinco datos que el bot

Si no, el corpus diria SIN COMBINAR donde el clinico ve COMBINADO, y dejaria
de ser un registro de lo que sale.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 10: documentación

**Ficheros:**
- Modificar: `README.md` (sección «El servidor (SP2)» y «Documentos»)
- Modificar: `docs/sp2-despliegue.md` (§10 tabla; la línea 776 del `grep` del redespliegue)
- Modificar: `docs/superpowers/specs/2026-09-24-sp3-bot-n8n-design.md` (§5.4 y §8)

No hay prueba automática de esto; la revisión lo lee.

- [ ] **Paso 1: README**

Al final de la sección «El servidor (SP2)», antes de «## Documentos»:

```markdown
**Desde SP4 (H6)**, si con la placa llegan los cinco datos de la regla de
Heckerling —temperatura, pulso, crepitantes, murmullo y asma—, la respuesta
trae además un bloque `combinacion`: la probabilidad posterior de opacidad
compatible, calculada como `odds(PREVALENCIA_LOCAL) × RV clínica × RV imagen`.
Se entrega como **horquilla** entre el supuesto de independencia y el de
dependencia total cuando las dos evidencias apuntan al mismo lado, y como un
número cuando se contradicen. Sin esos datos, la respuesta es la de siempre.
`PREVALENCIA_LOCAL` es obligatoria, como `AUC_VALIDACION`, y arranca en
`0.1466` (la cohorte de Heckerling). Diseño y cifras:
`docs/superpowers/specs/2026-09-26-sp4-combinacion-bayesiana-design.md`.
```

En «## Documentos», después de la línea del plan SP2 (mantén el orden por
subproyecto; si ya hay líneas de SP3, van después de ellas):

```markdown
- Diseño SP4: `docs/superpowers/specs/2026-09-26-sp4-combinacion-bayesiana-design.md`
- Plan SP4: `docs/superpowers/plans/2026-09-26-sp4-combinacion-bayesiana.md`
```

- [ ] **Paso 2: `docs/sp2-despliegue.md`**

§10, una fila nueva en la tabla, después de la de `AUC_VALIDACION`:

```markdown
| `PREVALENCIA_LOCAL` | **ninguno: es obligatoria** (el compose la pone a `0.1466`) | probabilidad previa de la combinación bayesiana (SP4 §5): 134/914, la cohorte de derivación de Heckerling. **Se le muestra al profesional** en cada informe con combinación. Se cambia aquí, con su fuente, cuando haya dato del entorno real |
```

Después del párrafo que empieza «Y **no tiene valor por defecto**: si falta,
`arrancar.py` se niega…», añade:

```markdown
`PREVALENCIA_LOCAL` sigue la misma regla y por la misma razón. Y `/salud` la
publica (`"prevalencia_local": 0.1466`): es la forma de saber, desde fuera, que
el contenedor que responde ya es el de SP4.
```

Y en la línea 776, el `grep` del redespliegue pasa a
`grep -nE 'UMBRAL|AUC_VALIDACION|PREVALENCIA_LOCAL' servidor/docker-compose.yml`.

- [ ] **Paso 3: spec de SP3**

En §5.4, después del párrafo «Ningún nodo escribe el base64 en un campo que se
persista.» (es un ítem de lista; añade otro ítem):

```markdown
- **Desde SP4**, con la placa viajan al copiloto los cinco datos de la regla de
  Heckerling —temperatura, pulso, crepitantes, murmullo y asma—, y nada más del
  cuestionario. Van dentro del mismo cuerpo JSON-RPC que el base64, por la misma
  red privada, y con la misma retención en `none`.
```

En §8, justo antes de «### El aviso es asimétrico a propósito»:

```markdown
**Desde SP4 (H6)**, entre `EXPLORADO` y el descargo va un cuarto bloque,
`COMBINADO — …` (o `SIN COMBINAR — …` cuando faltan datos), y el descargo se
queda en «Esto no es un diagnóstico.»: la frase «la combinación llega en la
siguiente entrega» ya no sale. Los ejemplos de arriba son los de SP3 tal como
el corpus los registró; el formato del bloque nuevo está en el §8 del spec de
SP4.
```

- [ ] **Paso 4: commit**

```bash
git add README.md docs/sp2-despliegue.md docs/superpowers/specs/2026-09-24-sp3-bot-n8n-design.md && git commit -m "docs(sp4): PREVALENCIA_LOCAL en la guia de despliegue, y lo que cambia en el informe

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 11: desplegar, publicar y comprobar de extremo a extremo

Esta tarea la conduce el controlador con el usuario; no se despacha a un
implementador. **Orden: A, luego B, luego C.**

**A. El servidor, en el VPS (lo ejecuta el usuario; se le dan estos comandos):**

```bash
cd /opt/copiloto && git pull && grep -nE 'UMBRAL|AUC_VALIDACION|PREVALENCIA_LOCAL' servidor/docker-compose.yml
```

```bash
cd /opt/copiloto && docker compose -f servidor/docker-compose.yml up -d --build copiloto-mcp
```

```bash
docker exec copiloto-mcp python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/salud')))"
```

Esperado en el tercero: `'estado': 'listo'` y `'prevalencia_local': 0.1466`. Si
no aparece `prevalencia_local`, la imagen no se reconstruyó: `docker compose
... build --no-cache copiloto-mcp` y repetir. Si el contenedor no arranca,
`docker logs copiloto-mcp` dirá `Falta la variable de entorno
PREVALENCIA_LOCAL`: el compose del VPS no es el del repositorio.

Después, desde la máquina de [retirado] con el túnel de `docs/sp3-operacion.md` §2
apuntando `COPILOTO_URL` al contenedor:
`C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_contrato_mcp.py tests/test_contrato_sp4.py -q -rs` → 13 pasadas, 0 saltadas.

**B. Los tres nodos, en n8n (lo hace el controlador con el MCP de n8n):**

1. Leer el export: `python -c` que imprima `parameters.jsCode` de `A base64`,
   `Leer respuesta` y `Desenlace` de `n8n/copiloto-profesional.json`.
2. `n8n_update_partial_workflow` sobre el workflow `[retirado]`
   (`🩺 Copiloto Triaje: Profesional`) con tres operaciones `updateNode`, una por
   nodo, que pongan `parameters.jsCode` al valor del export. Nada más del
   workflow se toca (restricción 10).
3. Verificar contra el grafo **publicado** (`n8n_get_workflow` con
   `mode: 'active'`), con la técnica del Ruling 20 de SP3: `patchNodeField` en
   modo `validateOnly` con `find == replace` sobre una ancla NUEVA de cada nodo
   (`hallazgosDe(`, `r.combinacion !== undefined`, `function redactarCombinacion`)
   demuestra que están; sobre la ancla VIEJA
   (`llega en la siguiente entrega`) demuestra que no está. Si el grafo activo
   no coincide con el borrador, publicar (desactivar y activar) y repetir.
4. `node tests/profesional.mjs` contra el export y, si hay túnel, la mitad
   conducida de `tests/test_flujo_profesional.py` con sus secretos en el
   entorno.

**C. De extremo a extremo (el usuario, con su bot de profesional):**

Una conversación real: código de un cuestionario con `asma: no_se`, los cuatro
signos, una placa. Lo que se espera leer, en este orden: `CRIBADO`, `EVIDENCIA
DE LA IMAGEN`, `REFERIDO POR EL PACIENTE` + `EXPLORADO`, `COMBINADO — entre X %
e Y % …` con `Heckerling n o n+1 de 5, según tenga asma o no` y el ⚠️, y
`Esto no es un diagnóstico.`. Y en `consultas.resultado` de esa fila, el bloque
`combinacion`.

Cuando eso esté, y solo entonces, se regenera el corpus contra la imagen nueva
(`python pruebas/reproducir_casos.py`, con o sin bots según el entorno), se
revisa el `RESUMEN.txt` y se hace commit del corpus con su mensaje diciendo
contra qué imagen se generó. Los perfiles 01-04 tienen que mostrar `COMBINADO`;
los 05-09 (rechazos), ninguna cifra.

- [ ] **A hecho** (fecha, y la salida del `/salud`)
- [ ] **B hecho** (activeVersionId del grafo verificado)
- [ ] **C hecho** (chat y fecha; el texto recibido pegado en el ledger)
- [ ] **Corpus regenerado y en commit**

---

## Comprobación final del plan (hecha al escribirlo)

**Cobertura del spec.** §2 → tarea 1 (`PUNTOS`). §3 → tareas 1-2. §4 → tarea 1
(RV y celdas). §5 → tarea 4. §6 → tareas 1-2 y 8 (`no_se`). §7.1-7.2 → tarea 2
(`concordantes`, `dependencia`) y 8 (⚠️). §7.3 → tarea 8 (⚠️ siempre). §8 y 8.1
→ tarea 8. §9.1 → tareas 1-2. §9.2 → tareas 3, 5, 7. §9.3 → tareas 6, 9, 10.
§10 → sin tarea: `Registrar` no cambia (tarea 8 lo comprueba: «se guarda ENTERO»).
§11.1 → tarea 1. §11.2 → tareas 1, 5, 8. §12 → nada que hacer. §14: criterio 1
→ tarea 1; 2 → tareas 3 y 5; 3 → tarea 8; 4 → tarea 8; 5 → tarea 8; 6 → tarea 8
(«I ante»); 6 bis → tareas 2 y 8; 7 → tarea 8; 8 → tarea 4.

**Consistencia de nombres entre tareas.** `validar_hallazgos`, `puntuar`,
`combinar`, `mas_informativa`, `combinacion`, `HallazgosInvalidos`,
`PREVALENCIA_COHORTE` (tarea 1-2) son los que importan las tareas 3 y las
pruebas. `Motor(..., prevalencia_local)` (tarea 3) es lo que usan las tareas 4 y
5 y los tres fixtures. `hallazgosDe` (tarea 6) y `hallazgos_del_caso` (tarea 9)
aplican la misma regla que `validar_hallazgos` (tarea 1), y la tarea 8 lo
comprueba por conducta contra `Desenlace`. Los fixtures `C_*` se definen en la
tarea 7 y los usan la 7 y la 8. `rvTexto` pasa a nivel de módulo en la tarea 8
y ahí mismo se cambian sus dos usos.
