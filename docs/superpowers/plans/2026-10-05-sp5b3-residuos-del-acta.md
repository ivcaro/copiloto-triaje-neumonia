# SP5-B3 — Residuos del acta: plan de implementación

> **Para trabajadores agénticos:** SUB-SKILL REQUERIDA: usa
> superpowers:subagent-driven-development (recomendado) o
> superpowers:executing-plans para ejecutar este plan tarea a tarea. Los pasos
> usan casillas (`- [ ]`) para el seguimiento.

**Objetivo:** que en el acta de la sesión con el médico un mismo límite del
intervalo del kappa se lea igual en las tres líneas que lo imprimen, y dejar
dichas con precisión cuatro frases de la documentación de la simulación.

**Arquitectura:** no hay piezas nuevas. Son los residuos que dejó abiertos la
re-revisión del cierre de SP5-B1 (su plan los enumera en la autorrevisión):
dos funciones de `src/copiloto_triaje/validacion/concordancia.py` que
escriben frases del acta, las pruebas que las vigilan, y texto. **No cambia
ninguna cifra, ni lo que el acta dice del 0,4 y del 0,6, ni nada de lo
publicado en `docs/validacion-semisintetica/` salvo una frase de su README.**

**Pila:** Python ≥ 3.11 (intérprete de la máquina de desarrollo:
`C:/venv-copiloto/Scripts/python.exe`), pytest. Ninguna dependencia nueva
(`decimal` es de la biblioteca estándar).

**Spec:** `docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md`,
§5.5 (el acta: el kappa frente a 0,4 y 0,6, y el texto declarado antes de la
sesión) y §4.6 (la nota fechada sobre el bootstrap).

**Parte de:** `main` con SP5-B2 fusionado (`7662209`). Rama de trabajo:
`sp5b3-residuos-del-acta`. De lo que SP5-B2 tocó, solo comparte el spec de
SP5, y en otro apartado: lo que este plan cita de él es el texto de después
de SP5-B2.

## Restricciones globales

1. **El análisis prerregistrado no se toca** (spec §5.5): ni el cálculo del
   kappa, ni sus intervalos, ni `frente_a_umbrales`, ni el texto fijado.
   Cambia solo CÓMO SE ESCRIBEN cifras que ya se calculan.
2. **Un kappa o un límite se compara con 0,4 y 0,6 a seis decimales**
   (`_a_seis`) y **se imprime con `_f_frente_a_umbral`** aplicada al valor tal
   como se calculó: dos decimales, o los que hagan falta (hasta seis) si dos
   dieran justo un umbral sin que el valor lo sea.
3. **Las comparaciones de la prosa se hacen con las cifras tal como se
   imprimen.** La anchura de un intervalo es la resta de sus dos límites
   impresos.
4. **Nada de lo generado se regenera:** ni `resultados_simulacion.json`, ni
   las figuras, ni `docs/validacion-semisintetica-sp5.md`. Si `git status`
   enseña alguno, algo se hizo de más.
5. Ninguna cadena que identifique al cliente, al equipo ni a la máquina en lo
   que se escriba. Mensajes de commit al estilo del repo, con la línea final
   `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Lo que se arregla, y de dónde sale

| # | Qué pasaba | Dónde | Cada cuánto |
| :--- | :--- | :--- | :--- |
| 1 | «Observado en esta sesión» redondeaba el límite a seis decimales ANTES de imprimirlo, y junto a una mitad eso le cambia la segunda cifra: 0,5750004 es «0,58» en la frase del criterio y salía «0,57» en «Observado» | `_anchura_observada` | 0,2 % de las sesiones simuladas |
| 2 | La línea del kappa imprimía a dos decimales a secas: «analítico −0,21 a 0,40» al lado de «a 0,3999 … el 0,4 queda fuera con el método analítico» | `_kappa_texto` | 4,5-6,5 % |
| 3 | La anchura se restaba en coma flotante: «de 0,395 a 0,95 (anchura 0,55)», y 0,95 − 0,395 es 0,555 | `_anchura_observada` | 0,4 % |
| 4 | La prueba que barre límites alrededor del 0,4 pasaba también con el código que tenía el fallo que dice vigilar: miraba la cifra que imprime «Observado» y no la comparaba con la del criterio | `tests/test_concordancia.py` | — |
| 5 | «Si se toca algo que cambie el bootstrap… ninguna prueba lo va a pedir»: desde la tarea 12 de SP5-B1 una prueba vuelve a calcular el bootstrap de una celda | el README de la carpeta y el docstring de la prueba | — |
| 6 | «La anchura mediana pasa a 0,83 de la anterior»: 0,83 es la mediana del cociente intervalo a intervalo (la anchura mediana pasa a 0,73) | spec §4.6 | — |
| 7 | Tres docstrings y un comentario que decían de más, y una prueba (las tildes por stderr) que solo podía fallar en una máquina cuyo sistema no es UTF-8 | pruebas e `informe.py` | — |

Las frecuencias son las que midió la re-revisión sobre 40 000 sesiones
simuladas por el camino real. En ninguna de ellas, ni antes ni después de
este plan, el acta se contradice sobre si el 0,4 o el 0,6 quedan dentro del
intervalo.

**Lo que NO se arregla, y por qué.** El documento de análisis dice «los
umbrales del generador» sin nombrar `z_y`, y cuenta 28 intervalos de anchura
cero cuando hay dos más que se imprimen con los dos límites iguales (su
anchura es de una o dos unidades del último bit). Son de
`docs/validacion-semisintetica-sp5.md`, que es generado y está publicado:
tocarlos es volver a generar lo publicado por dos matices que no cambian
ninguna lectura. Se dejan dichos aquí.

---

### Tarea 1: El mismo límite, la misma cifra, y cuatro frases dichas con precisión

**Ficheros:**

- Modificar: `docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md`
- Modificar: `docs/validacion-semisintetica/README.md`
- Modificar: `src/copiloto_triaje/validacion/concordancia.py`
- Modificar: `src/copiloto_triaje/validacion/informe.py`
- Modificar: `tests/test_concordancia.py`
- Modificar: `tests/test_informe.py`
- Modificar: `tests/test_medir_latencia.py`
- Modificar: `tests/test_resultados_publicados.py`
- Modificar: `tests/test_simulacion.py`

**Interfaces:**

- Cambia `concordancia._kappa_texto(k) -> str`: mismas entradas y misma forma
  de la frase; las cifras van con `_f_frente_a_umbral`.
- Cambia `concordancia._anchura_observada(k) -> str`: misma frase; los
  límites se imprimen desde el valor calculado y la anchura se resta en
  decimal, con el ,5 hacia arriba.
- Nada cambia de nombre ni de firma. `valores_para_acta` y la plantilla del
  acta no se tocan.

- [ ] **Paso 1: las pruebas, y verlas fallar**

Aplica las sustituciones del **grupo 1** (solo ficheros de `tests/`).

```bash
C:/venv-copiloto/Scripts/python.exe -m pytest -q tests/test_concordancia.py tests/test_informe.py tests/test_medir_latencia.py tests/test_resultados_publicados.py tests/test_simulacion.py
```

Esperado: `2 failed, 169 passed`. Fallan
`test_el_mismo_limite_se_lee_igual_en_las_tres_lineas_del_acta` (la línea del
kappa va a dos decimales) y
`test_la_anchura_es_la_resta_de_lo_impreso_con_el_medio_hacia_arriba` (sale
«anchura 0,55»).

`test_lo_observado_y_el_criterio_no_se_contradicen_sobre_el_0_4`, que también
cambia, **pasa**: el fallo que vigila ya lo arregló la tarea 12 de SP5-B1. Lo
que se comprobó al escribir este plan es que, con el código anterior a aquella
tarea, ahora **falla** (antes pasaba).

- [ ] **Paso 2: el código y los documentos**

Aplica las sustituciones del **grupo 2**.

- [ ] **Paso 3: el verde**

```bash
C:/venv-copiloto/Scripts/python.exe -m pytest -q tests/test_concordancia.py tests/test_informe.py tests/test_medir_latencia.py tests/test_resultados_publicados.py tests/test_simulacion.py
```

Esperado: `171 passed`. Y la suite entera y el formulario:

```bash
C:/venv-copiloto/Scripts/python.exe -m pytest -q
node tests/formulario.mjs
git status --short
```

Esperado: ningún fallo, dos pruebas más que antes de la tarea, `16 OK`, y en
el `git status` **solo** los nueve ficheros de esta tarea: ni el JSON
de resultados, ni una figura, ni el documento de análisis.

- [ ] **Paso 4: commit**

```bash
git add docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md docs/validacion-semisintetica/README.md src/copiloto_triaje/validacion/concordancia.py src/copiloto_triaje/validacion/informe.py tests/test_concordancia.py tests/test_informe.py tests/test_medir_latencia.py tests/test_resultados_publicados.py tests/test_simulacion.py
git commit -m "fix(validacion): en el acta, el mismo límite del kappa se lee igual en sus tres líneas" -m "Residuos de la re-revisión del cierre de SP5-B1. La línea del kappa y «Observado en esta sesión» imprimen cada límite como la frase del criterio, desde el valor calculado; la anchura se resta en decimal. La prueba del barrido sobre el 0,4 compara la cifra del criterio con la de «Observado». El README de la simulación, el spec §4.6 y tres docstrings dicen lo que es. No cambia ninguna cifra." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### Grupo 1 — Las pruebas

**Sustituciones: `tests/test_concordancia.py`**

6, en este orden. Cada texto que se busca aparece UNA vez en el fichero tal como está cuando le toca.

1. Busca

````python
    es el propio umbral. Y cada frase cuadra con los límites que imprime."""
````

y sustitúyelo por

````python
    ES el umbral (a seis decimales). Las dos frases imprimen el límite con la
    misma cifra, y cada una cuadra con la que imprime."""
````

2. Busca

````python
            observado = cc._anchura_observada(r)
            # lo que dice del 0,4 (los límites superiores dejan el 0,6 dentro)
````

y sustitúyelo por

````python
            observado = cc._anchura_observada(r)
            criterio = cc._criterio("El kappa ponderado", r)
            # lo que dice del 0,4 (los límites superiores dejan el 0,6 dentro)
````

3. Busca

````python
            for li, metodo, clave in ((li_a, "el método analítico", "li_analitico_lt_0_4"),
                                      (li_b, "el BCa", "li_bca_lt_0_4")):
````

y sustitúyelo por

````python
            for li, metodo, corto, clave in (
                    (li_a, "el método analítico", "analítico", "li_analitico_lt_0_4"),
                    (li_b, "el BCa", "BCa", "li_bca_lt_0_4")):
````

4. Busca

````python
                # lo que dice del 0,4 cuadra con el límite que imprime...
````

y sustitúyelo por

````python
                # el criterio imprime ese límite con la misma cifra...
                en_el_criterio = re.search(rf"{corto} \(?(-?\d+,\d+)", criterio)
                assert en_el_criterio.group(1) == impreso.group(1), (li, criterio, observado)
                # ...lo que «Observado» dice del 0,4 cuadra con la cifra que imprime...
````

5. Busca

````python
                # ...y con lo que dice el criterio de ese mismo límite
````

y sustitúyelo por

````python
                # ...y con lo que el criterio dice de ese mismo límite: solo un
                # límite que ES el umbral no queda por debajo y lo tiene dentro
````

6. Busca

````python
                    assert not dentro or inferior == 0.4, (li, observado)
````

y sustitúyelo por

````python
                    assert not dentro or round(li, 6) == 0.4, (li, observado)


def test_el_mismo_limite_se_lee_igual_en_las_tres_lineas_del_acta():
    """La línea del kappa, la frase del criterio y «Observado» imprimen los
    límites del mismo intervalo. Junto a una mitad, redondear antes a seis
    decimales le cambia la segunda cifra a un límite (0,5750004 es «0,58»;
    0,575, «0,57»), y a dos decimales a secas 0,3999 se lee «0,40» al lado de
    «el 0,4 queda fuera»."""
    import re
    junto_a_una_mitad = (0.5750004190841983, 0.6250000000000001, 0.125000000001,
                         0.3750000000000001, 0.575, 0.625)
    junto_a_un_umbral = (0.3999, 0.3996, 0.4027, 0.4000004, 0.3999999999999999, 0.5996,
                         0.6004, 0.395, 0.605)
    candidatos = junto_a_una_mitad + junto_a_un_umbral + (-0.21, 0.0, 0.28)
    for li_a in candidatos:
        for li_b in candidatos:
            for ls in (0.3999, 0.6250000000000001, 0.95, 1.0):
                if ls < max(li_a, li_b):
                    continue
                r = {"kappa": max(li_a, li_b), "ic95": [li_a, ls], "ic95_bca": [li_b, ls],
                     "n": 24}
                r["frente_a_umbrales"] = cc.frente_a_umbrales(r)
                linea = re.search(r"analítico (\S+) a (\S+); BCa (\S+) a (\S+); n = 24",
                                  cc._kappa_texto(r)).groups()
                observado = cc._anchura_observada(r)
                analitico = re.search(r"de (\S+) a (\S+) con el método analítico", observado)
                bca = re.search(r"de (\S+) a (\S+) con el BCa", observado)
                assert linea == analitico.groups() + bca.groups(), (r, observado)
                criterio = cc._criterio("El kappa ponderado", r)
                assert re.search(r"analítico \(?(-?\d+,\d+)", criterio).group(1) == linea[0]
                assert re.search(r"BCa \(?(-?\d+,\d+)", criterio).group(1) == linea[2]
                # y lo que se lee «0,40» o «0,60» ES el umbral
                for crudo, leido in zip((li_a, ls, li_b, ls), linea):
                    if leido in ("0,40", "0,60"):
                        assert round(crudo, 6) in (0.4, 0.6), (crudo, leido)


def test_la_anchura_es_la_resta_de_lo_impreso_con_el_medio_hacia_arriba():
    def k(analitico, bca):
        r = {"kappa": 0.7, "ic95": list(analitico), "ic95_bca": list(bca), "n": 24}
        r["frente_a_umbrales"] = cc.frente_a_umbrales(r)
        return r
    # 0,95 − 0,395 = 0,555: con coma flotante la resta da 0,55499… y salía «0,55»
    observado = cc._anchura_observada(k((0.395, 0.95), (0.605, 0.95)))
    assert "de 0,395 a 0,95 con el método analítico (anchura 0,56)" in observado
    assert "de 0,605 a 0,95 con el BCa (anchura 0,35)" in observado      # 0,345
    assert "de -0,21 a 0,3999 con el método analítico (anchura 0,61)" in (
        cc._anchura_observada(k((-0.21, 0.3999), (0.1, 0.5))))
````

**Sustituciones: `tests/test_informe.py`**

1, en este orden. Cada texto que se busca aparece UNA vez en el fichero tal como está cuando le toca.

1. Busca

````python
    los nombres de las figuras, de las celdas y de los modelos y el título
    se escriben UNA vez, aquí, y el guion los toma de `informe`."""
````

y sustitúyelo por

````python
    los títulos de las figuras, los nombres de los modelos y el título del
    documento se escriben UNA vez, en `informe`, y el guion los toma de ahí.
    Los nombres de los ficheros de las figuras los dicen los dos, y esta
    prueba ata las dos listas."""
````

**Sustituciones: `tests/test_medir_latencia.py`**

3, en este orden. Cada texto que se busca aparece UNA vez en el fichero tal como está cuando le toca.

1. Busca

````python
    saldría roto si el guion no reconfigurara también ese canal."""
````

y sustitúyelo por

````python
    saldría roto si el guion no reconfigurara también ese canal. La consola
    que no es UTF-8 la pone la prueba (`PYTHONIOENCODING`), para que pueda
    fallar en cualquier máquina y no solo donde el sistema no lo es."""
````

2. Busca

````python
    entorno = {k: v for k, v in os.environ.items()
               if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
````

y sustitúyelo por

````python
    entorno = {k: v for k, v in os.environ.items() if k != "PYTHONUTF8"}
````

3. Busca

````python
    entorno["PYTHONUTF8"] = "0"
    guion = str(REPO / "scripts" / "medir_latencia.py")
````

y sustitúyelo por

````python
    entorno["PYTHONUTF8"] = "0"
    entorno["PYTHONIOENCODING"] = "cp1252"
    guion = str(REPO / "scripts" / "medir_latencia.py")
````

**Sustituciones: `tests/test_resultados_publicados.py`**

1, en este orden. Cada texto que se busca aparece UNA vez en el fichero tal como está cuando le toca.

1. Busca

````python
las de fiabilidad, el nombre de su celda). Si se toca algo que cambie el
bootstrap o el dibujo, hay que volver a correr el guion: ninguna prueba lo va
a pedir.
````

y sustitúyelo por

````python
las de fiabilidad, el nombre de su celda). Si se toca el dibujo, o algo del
bootstrap que no mueva los intervalos de (0,6; 0), hay que volver a correr el
guion: ninguna prueba lo va a pedir.
````

**Sustituciones: `tests/test_simulacion.py`**

1, en este orden. Cada texto que se busca aparece UNA vez en el fichero tal como está cuando le toca.

1. Busca

````python
    1,13, y la media sobre otras clínicas, 1,09. Las réplicas tienen que
    rodear a la primera: el intervalo es de la cifra que se publica."""
````

y sustitúyelo por

````python
    1,13, y las réplicas que vuelven a sortear la clínica se centran en 1,09.
    Las de aquí tienen que rodear a la primera: el intervalo es de la cifra
    que se publica."""
````


#### Grupo 2 — El código y los documentos

**Sustituciones: `docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md`**

1, en este orden. Cada texto que se busca aparece UNA vez en el fichero tal como está cuando le toca.

1. Busca

````markdown
> 328 intervalos con anchura, 292 se estrechan y 13 se ensanchan (la anchura
> mediana pasa a 0,83 de la anterior).
````

y sustitúyelo por

````markdown
> 328 intervalos con anchura, 292 se estrechan y 13 se ensanchan (en mediana,
> cada intervalo mide 0,83 de lo que medía).
````

**Sustituciones: `docs/validacion-semisintetica/README.md`**

1, en este orden. Cada texto que se busca aparece UNA vez en el fichero tal como está cuando le toca.

1. Busca

````markdown
de su celda. Si se toca algo que cambie el bootstrap o el dibujo, hay que
volver a correr el guion, porque ninguna prueba lo va a pedir. Si la prueba
````

y sustitúyelo por

````markdown
de su celda. Si se toca el dibujo, o algo del bootstrap que no mueva los
intervalos de esa celda, hay que volver a correr el guion, porque ninguna
prueba lo va a pedir. Si la prueba
````

**Sustituciones: `src/copiloto_triaje/validacion/concordancia.py`**

6, en este orden. Cada texto que se busca aparece UNA vez en el fichero tal como está cuando le toca.

1. Busca

````python
import datetime
import math
````

y sustitúyelo por

````python
import datetime
import decimal
import math
````

2. Busca

````python
    return (f"{_f(k['kappa'])} (IC 95 % analítico {_f(k['ic95'][0])} a {_f(k['ic95'][1])}; "
            f"BCa {_f(k['ic95_bca'][0])} a {_f(k['ic95_bca'][1])}; n = {k['n']})")
````

y sustitúyelo por

````python
    """Un kappa y sus dos intervalos, en una linea. Las cifras van con
    `_f_frente_a_umbral`, como en la frase del criterio y en «Observado»: en
    el acta, el mismo limite se lee igual en las tres."""
    f = _f_frente_a_umbral
    return (f"{f(k['kappa'])} (IC 95 % analítico {f(k['ic95'][0])} a {f(k['ic95'][1])}; "
            f"BCa {f(k['ic95_bca'][0])} a {f(k['ic95_bca'][1])}; n = {k['n']})")
````

3. Busca

````python
    Los limites van como en la frase del criterio, que esta dos lineas mas
    arriba en el acta: con `_f_frente_a_umbral` (los decimales que hagan
    falta si quedan pegados a un umbral) y comparados a seis decimales, como
    `frente_a_umbrales`. Asi las dos frases no pueden decir cosas distintas
    del 0,4. La anchura es la de los limites tal como se imprimen."""
````

y sustitúyelo por

````python
    Los limites se IMPRIMEN como en la frase del criterio y en la linea del
    kappa, que estan mas arriba en el acta: con `_f_frente_a_umbral` sobre el
    limite tal como se calculo (redondearlo antes a seis decimales puede
    cambiarle la segunda cifra: 0,5750004 es «0,58» y 0,575, «0,57»). Se
    COMPARAN con los umbrales a seis decimales, como `frente_a_umbrales`. Asi
    las tres lineas dicen lo mismo del mismo limite. La anchura es la resta
    de los limites tal como se imprimen, hecha en decimal y con el ,5 hacia
    arriba: «de 0,395 a 0,95» mide 0,555, que es «0,56»."""
````

4. Busca

````python
    limites = {nombre: [_a_seis(x) for x in k[clave]] for clave, nombre in METODOS}
````

y sustitúyelo por

````python
    crudos = {nombre: list(k[clave]) for clave, nombre in METODOS}
    limites = {nombre: [_a_seis(x) for x in par] for nombre, par in crudos.items()}
````

5. Busca

````python
    def impreso(x) -> float:
        return float(_f_frente_a_umbral(x).replace(",", "."))
````

y sustitúyelo por

````python
    def impreso(x) -> decimal.Decimal:
        return decimal.Decimal(_f_frente_a_umbral(x).replace(",", "."))

    def anchura(li, ls) -> str:
        resta = (impreso(ls) - impreso(li)).quantize(
            decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_UP)
        return str(resta).replace(".", ",")
````

6. Busca

````python
        f"(anchura {_f(impreso(ls) - impreso(li))})"
        for nombre, (li, ls) in limites.items())
````

y sustitúyelo por

````python
        f"(anchura {anchura(li, ls)})"
        for nombre, (li, ls) in crudos.items())
````

**Sustituciones: `src/copiloto_triaje/validacion/informe.py`**

1, en este orden. Cada texto que se busca aparece UNA vez en el fichero tal como está cuando le toca.

1. Busca

````python
# Los titulos de las figuras, los nombres de las celdas y el titulo del
# documento se escriben aqui y solo aqui: el guion los toma de este modulo.
````

y sustitúyelo por

````python
# Los titulos de las figuras y el titulo del documento se escriben aqui y
# solo aqui: el guion los toma de este modulo. (El nombre de una celda lo
# escribe `simulacion.nombre_de_celda`, y de ahi lo leen los dos.)
````


---

## Autorrevisión del plan (hecha al escribirlo)

**Cobertura.** Los seis puntos del informe de la re-revisión del cierre de
SP5-B1:

| Punto de la re-revisión | Fila de la tabla de arriba |
| :--- | :--- |
| 1. «Observado» imprime un límite con otra cifra que el criterio | 1 |
| 2. El barrido sobre el 0,4 no vigila lo que dice | 4 |
| 3. La frase que ya no es verdad (README y docstring de la prueba) | 5 |
| 4. «Anchura mediana» en la nota del spec | 6 |
| 5. La línea del kappa, a dos decimales | 2 |
| 6. Pulido: la anchura con un empate en la mitad, el «1,09», los docstrings, la prueba de UTF-8 | 3 y 7 |

**Verificado antes de escribirlo.** El código y las pruebas de los dos
grupos corrieron sobre una copia de `main`: rojo `2 failed, 169 passed`, verde
`171 passed`. Cinco mutaciones, cada una deshaciendo un arreglo, hacen caer
alguna prueba: la línea del kappa a dos decimales; «Observado» imprimiendo el
límite ya redondeado a seis; la anchura restada en coma flotante; la anchura
redondeada al par; y «Observado» decidiendo con el límite sin redondear a
seis. Los bloques de los dos grupos salen de la diferencia real entre los
árboles y, aplicados en seco sobre `main`, dan el árbol verificado.

**Huecos.** Ninguno: no hay pasos «por determinar».
