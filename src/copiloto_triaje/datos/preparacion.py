"""Cruce de metadatos con etiquetas y escritura de manifiestos."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def cargar_etiquetas(ruta_csv: Path) -> dict[str, int]:
    """Lee stage_2_train_labels.csv y colapsa las filas por paciente.

    Hay mas filas que pacientes porque un positivo puede tener varias cajas;
    el paciente es positivo si alguna de sus filas lo es.
    """
    df = pd.read_csv(ruta_csv)
    agrupado = df.groupby("patientId")["Target"].max()
    return {str(k): int(v) for k, v in agrupado.items()}


def construir_registros(metadatos: list[dict], etiquetas: dict[str, int]) -> list[dict]:
    """Une metadatos de imagen con su etiqueta. Descarta los sin etiqueta."""
    registros = []
    for meta in metadatos:
        pid = meta.get("patientId")
        if pid in etiquetas:
            registro = dict(meta)
            registro["etiqueta"] = int(etiquetas[pid])
            registros.append(registro)
    return registros


def escribir_manifiestos(particiones: dict[str, list[dict]], dir_manifiestos,
                         semilla: int) -> dict[str, Path]:
    """Escribe train.csv, val.csv y test.csv con la semilla registrada."""
    dir_manifiestos = Path(dir_manifiestos)
    dir_manifiestos.mkdir(parents=True, exist_ok=True)
    rutas = {}
    for nombre, registros in particiones.items():
        df = pd.DataFrame(registros)
        df["semilla"] = semilla
        ruta = dir_manifiestos / f"{nombre}.csv"
        df.to_csv(ruta, index=False)
        rutas[nombre] = ruta
    return rutas


def verificar_zip_existe(ruta_zip: Path) -> None:
    """Falla de inmediato y de forma explicita si el zip de RSNA no esta
    donde se indico, en vez de fallar a mitad de la descompresion.

    `Config` no puede hacer esta validacion (se construye a proposito con
    rutas temporales inexistentes en otras pruebas), asi que le corresponde
    al script de preparacion, tal como exige el spec para configuracion
    invalida: fallar al inicio, no a mitad del proceso. El mensaje siempre
    cita la ruta buscada para que el error sea accionable.
    """
    ruta_zip = Path(ruta_zip)
    if not ruta_zip.exists():
        raise FileNotFoundError(
            f"No se encontro el zip de RSNA en la ruta indicada con --zip: "
            f"{ruta_zip}\nVerifica la ruta (relativa al directorio actual o "
            f"absoluta) antes de volver a ejecutar el script."
        )
    if not ruta_zip.is_file():
        raise FileNotFoundError(
            f"La ruta indicada con --zip existe pero no es un archivo: "
            f"{ruta_zip}\nDebe apuntar al archivo .zip de RSNA, no a un "
            f"directorio."
        )


def edad_en_anios(valor) -> int | None:
    """Convierte el campo PatientAge del DICOM a un entero de anios.

    En RSNA viene como un numero suelto ("51"), pero el estandar DICOM admite
    tambien la forma con sufijo de unidad ("051Y", "018M", "003D"). Se
    interpretan los anios; meses y dias se convierten, porque un paciente de
    "018M" tiene ano y medio y debe contar como menor, no como 18 anios.
    Devuelve None si no se puede interpretar: un dato que no se entiende no
    se da por bueno.
    """
    if valor is None:
        return None
    texto = str(valor).strip().upper()
    if not texto:
        return None
    unidad = texto[-1] if texto[-1].isalpha() else "Y"
    digitos = "".join(c for c in texto if c.isdigit())
    if not digitos:
        return None
    numero = int(digitos)
    if unidad == "Y":
        return numero
    if unidad == "M":
        return numero // 12
    if unidad in ("W", "D"):
        return 0
    return None


def filtrar_por_edad(registros: list[dict], edad_minima: int = 18,
                     edad_maxima: int = 100) -> tuple[list[dict], dict]:
    """Deja solo los pacientes dentro del rango de edad del alcance.

    El proyecto declara por escrito que trata radiografias de ADULTOS, pero
    el analisis exploratorio encontro que el 4,78% del padron son menores de
    18 anios (desde 1 ano) y cinco pacientes tienen edades imposibles de 148
    a 155. Entrenar con ellos contradiria el alcance entregado, y ademas la
    neumonia pediatrica se ve distinta en la placa: es otra poblacion.

    Devuelve (aceptados, resumen). El resumen detalla cuantos se descartaron
    y por que motivo, para que la perdida de datos nunca sea silenciosa.
    """
    aceptados: list[dict] = []
    descartados: list[dict] = []
    for registro in registros:
        edad = edad_en_anios(registro.get("edad"))
        if edad is None:
            motivo = "edad ilegible"
        elif edad < edad_minima:
            motivo = f"menor de {edad_minima}"
        elif edad > edad_maxima:
            motivo = f"mayor de {edad_maxima} (implausible)"
        else:
            registro = dict(registro)
            registro["edad_anios"] = edad
            aceptados.append(registro)
            continue
        descartados.append({"patientId": registro.get("patientId"),
                            "edad": registro.get("edad"), "motivo": motivo})

    conteo: dict[str, int] = {}
    for d in descartados:
        conteo[d["motivo"]] = conteo.get(d["motivo"], 0) + 1
    resumen = {
        "rango": [edad_minima, edad_maxima],
        "entraron": len(registros),
        "aceptados": len(aceptados),
        "descartados": len(descartados),
        "por_motivo": conteo,
        "detalle": descartados,
    }
    return aceptados, resumen


def verificar_crudo_existe(ruta_crudo) -> None:
    """Falla de inmediato si la carpeta ya descomprimida no sirve.

    El equivalente de `verificar_zip_existe` para la fuente `--crudo`, que es
    la que usa Kaggle (el dataset llega extraido y de solo lectura) y la que
    evita duplicar 3,9 GB en local. No basta con que la carpeta exista: lo que
    el resto del script necesita son `stage_2_train_images/` y
    `stage_2_train_labels.csv`, asi que se comprueban los dos por nombre y el
    mensaje cita la ruta que falta.
    """
    ruta_crudo = Path(ruta_crudo)
    if not ruta_crudo.is_dir():
        raise FileNotFoundError(
            f"No existe la carpeta de datos descomprimidos: {ruta_crudo}")
    for relativa in ("stage_2_train_images", "stage_2_train_labels.csv"):
        if not (ruta_crudo / relativa).exists():
            raise FileNotFoundError(
                f"{ruta_crudo} no parece la carpeta de RSNA: falta "
                f"{relativa}. Debe contener stage_2_train_images/ y "
                "stage_2_train_labels.csv.")
