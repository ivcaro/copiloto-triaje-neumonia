# -*- coding: utf-8 -*-
"""El arnes de reproduccion: lo que se puede comprobar sin bots ni base.

Estas pruebas NO conducen ninguna conversacion: para eso hacen falta el tunel,
los dos secretos y unos veinte minutos, y eso lo corre una persona. Aqui viven
las garantias que si se pueden atar, y son las que se rompen en silencio:

- que los DICOM fabricados son lo que el corpus dice que son -sin esto, el
  perfil `edad_desconocida` podria estar midiendo otra cosa y el corpus lo
  contaria igual de convencido-;
- que el texto del mensaje sale del `jsCode` del workflow y no de una segunda
  copia en Python;
- que el resumen AVISA si el aviso del §8 y los numeros no cuadran, en vez de
  imprimir el numero bonito;
- que el fichero que alguien va a leer no obliga a abrir un JSON.
"""
import json
import pathlib
import shutil
import subprocess
import sys

import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from copiloto_triaje.datos.dicom import leer_dicom_desde_bytes  # noqa: E402
from pruebas.reproducir_casos import (  # noqa: E402
    MAXIMO_BYTES, PERFILES, SIGNOS, SINTOMAS, _coincide, _fabricar,
    nombre_fichero, resumen, texto_del_caso,
)

REDACTOR = REPO / "pruebas" / "redactar.mjs"


def _dicom_minimo(ruta, edad="58", lado=64):
    """Un DICOM legible por el MISMO lector que usa el servidor.

    Lleva pixel de verdad a proposito: sin el, `leer_dicom_desde_bytes` fallaria
    tambien sobre el original y la prueba del truncado no mediria nada.
    """
    ds = Dataset()
    ds.PatientID = "P0001"
    ds.PatientAge = edad
    ds.PatientSex = "M"
    ds.ViewPosition = "PA"
    ds.Modality = "CR"
    ds.Rows, ds.Columns = lado, lado
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PixelData = (np.arange(lado * lado) % 256).astype(np.uint8).tobytes()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.save_as(str(ruta), enforce_file_format=True)
    return ruta


# --------------------------------------------------------------------------
def test_los_nueve_perfiles_son_coherentes_y_los_fabricados_se_ven():
    assert len(PERFILES) == 9
    assert len({p.clave for p in PERFILES}) == 9
    assert len({p.carpeta for p in PERFILES}) == 9
    assert [p.orden for p in PERFILES] == list(range(1, 10))
    fabricados = [p for p in PERFILES if p.fabricado]
    assert len(fabricados) == 3
    for p in fabricados:
        # Se tiene que ver en la carpeta Y en el titulo: quien abra el corpus no
        # va a leer este fichero para enterarse.
        assert "FABRICADO" in p.carpeta
        assert "FABRICADO" in p.titulo
    for p in PERFILES:
        assert p.que_mirar and p.de_donde, p.clave


def test_el_nombre_del_fichero_delata_al_fabricado():
    real = {"patientId": "abc", "perfil": PERFILES[0]}
    falso = {"patientId": "abc", "perfil": [p for p in PERFILES
                                            if p.fabricado][0]}
    assert nombre_fichero(real) == "abc.txt"
    assert nombre_fichero(falso) == "abc-FABRICADO.txt"


def test_fabricar_produce_exactamente_lo_que_el_corpus_dice(tmp_path):
    """Sin esto, el perfil 07 podria estar midiendo `dicom_invalido` y el corpus
    seguiria diciendo que mide `edad_desconocida`."""

    base = _dicom_minimo(tmp_path / "base.dcm")
    rutas = _fabricar(base, tmp_path / "salida")
    assert set(rutas) == {"edad_desconocida_FABRICADO",
                          "fichero_corrupto_FABRICADO",
                          "fichero_enorme_FABRICADO"}
    for ruta in rutas.values():
        assert "FABRICADO" in ruta.name, ruta

    # El original tiene que ser legible, o lo de abajo no mide nada.
    leer_dicom_desde_bytes(base.read_bytes())

    # 07: la etiqueta de la edad ya no esta, y el fichero SIGUE siendo legible.
    # Las dos mitades importan: si dejara de leerse, el servidor contestaria
    # `dicom_invalido` y el corpus aseguraria que mide `edad_desconocida`.
    sin_edad = pydicom.dcmread(rutas["edad_desconocida_FABRICADO"])
    assert "PatientAge" not in sin_edad
    _, meta = leer_dicom_desde_bytes(
        rutas["edad_desconocida_FABRICADO"].read_bytes())
    assert not meta.get("edad"), meta
    assert pydicom.dcmread(base).PatientAge == "58", "la base no se toca"

    # 08: truncado de verdad, ya no lo lee el lector del servidor, y SIGUE siendo
    # un DICOM truncado -conserva el preambulo y la marca `DICM`- y no una ristra
    # de bytes cualquiera, que es otro caso distinto.
    truncado = rutas["fichero_corrupto_FABRICADO"]
    bytes_truncado = truncado.read_bytes()
    assert len(bytes_truncado) < base.stat().st_size
    assert bytes_truncado[128:132] == b"DICM"
    # La tupla es la MISMA que captura `Motor.clasificar` para contestar
    # `dicom_invalido`. Con un `Exception` a secas, un fallo de programacion en el
    # lector dejaria pasar esta prueba y el corpus diria que mide esa rama.
    with pytest.raises((pydicom.errors.InvalidDicomError, ValueError, TypeError)):
        leer_dicom_desde_bytes(bytes_truncado)

    # 09: por encima del maximo del TOOL y por debajo del del TRANSPORTE. Los
    # dos limites del §10.4 no son el mismo, y este fichero tiene que caer en el
    # primero: si se pasara del segundo, el caso mediria `payload_excesivo_
    # transporte` y el corpus diria `payload_excesivo`.
    enorme = rutas["fichero_enorme_FABRICADO"].stat().st_size
    assert enorme > MAXIMO_BYTES
    caracteres_base64 = (MAXIMO_BYTES + 2) // 3 * 4
    tope_transporte = (caracteres_base64
                       + (caracteres_base64 // 76 + 1) * 4
                       + 64 * 1024)
    assert (enorme + 2) // 3 * 4 < tope_transporte


# --------------------------------------------------------------------------
UN_RESULTADO = {
    "probabilidad_cruda": 0.5649, "probabilidad_calibrada": 0.1985,
    "razon_de_verosimilitud": 0.87, "umbral": 0.4258,
    "clasificacion": "opacidad_probable", "edad_paciente": 58,
    "modelo": "efficientnet_b0_320px", "auc_validacion": 0.8827,
    "milisegundos": 37.4,
}


SINTOMAS_ENVIADOS = {"fiebre": "si", "tos": "con_flema",
                     "dias_evolucion": "3_a_7", "disnea": "no",
                     "dolor_toracico": "si", "asma": "no_se",
                     "texto_libre": None}


def _caso(perfil=None, pid="03cf9ba9-dfbe-47b9-aa96-3e69432d73c3",
          clase="No Lung Opacity / Not Normal"):
    return {"perfil": perfil or PERFILES[2],
            "patientId": pid,
            "ruta_dcm": "x.dcm", "cruda_cache": 0.5649, "edad_rsna": 58,
            "clase_rsna": clase, "sexo_rsna": "M",
            "sintomas": dict(SINTOMAS_ENVIADOS)}


def test_el_fichero_del_corpus_no_obliga_a_abrir_ningun_json():
    texto = texto_del_caso(
        _caso(), {"con_bots": False, "motivo_sin_bots": "--sin-bots"},
        {"texto": "CRIBADO — opacidad probable", "texto_paciente": "",
         "error": None, "resultado": UN_RESULTADO})
    assert '{"' not in texto and "': '" not in texto, "se escapo un JSON"
    assert "probabilidad_cruda" not in texto, "se escapo una clave del esquema"
    # Lo que sabemos de la placa tiene que estar AL LADO: quien lee no va a
    # buscarlo a otro sitio. Se busca sobre el texto con los saltos colapsados,
    # porque las lineas van ajustadas a 78 columnas y una frase puede partirse.
    plano = " ".join(texto.split())
    for esperado in ("03cf9ba9-dfbe-47b9-aa96-3e69432d73c3", "58 años",
                     "No Lung Opacity", "sin opacidad anotada", "0,5649",
                     "0,87", "INVENTADOS", "CRIBADO — opacidad probable"):
        assert esperado in plano, esperado
    assert "¿TIENE SENTIDO CLÍNICO" in texto
    # Que quepa en una consola de 80 columnas sin que nada lo reajuste: el margen
    # de 2 es para los rotulos largos del `_punto`.
    assert max(len(l) for l in texto.splitlines()) <= 82


def test_el_corpus_no_dice_que_alguien_recibio_lo_que_nadie_recibio():
    """El rotulo es una afirmacion como cualquier otra.

    La primera version titulaba «EL MENSAJE QUE RECIBIO EL PROFESIONAL» en los
    tres casos, tambien cuando Telegram habia rechazado el envio con un 400 porque
    el chat de los updates es inventado. Un corpus solo vale lo que vale su
    honestidad.
    """
    red = {"texto": "CRIBADO — opacidad probable", "texto_paciente": "",
           "error": None, "resultado": UN_RESULTADO}
    titulos = {}
    for entrega in ("no_intentada", "rechazada", "intentada"):
        texto = texto_del_caso(
            _caso(), {"con_bots": entrega != "no_intentada", "entrega": entrega,
                      "motivo_sin_bots": "--sin-bots"}, red)
        titulos[entrega] = texto
    assert "RECIBIÓ" not in titulos["no_intentada"].split("CRIBADO")[0]
    assert "HABRÍA ENVIADO" in titulos["no_intentada"]
    assert "NADIE LO RECIBIÓ" in titulos["rechazada"]
    assert "ENVIÓ AL PROFESIONAL" in titulos["intentada"]
    # Y los tres estados se distinguen: sin esto, un solo rotulo para todos
    # volveria a pasar sin que nadie lo viera.
    assert len({t.split("\n")[0] for t in titulos.values()}) >= 1
    assert len(set(titulos.values())) == 3


def test_el_segundo_mensaje_dice_que_no_se_intento_cuando_no_se_intento():
    """`Enviar texto del paciente` cuelga DETRAS de `Responder`, que no tiene
    manejo de error: si el primer envio falla, el segundo nodo no se ejecuta. El
    corpus imprimia su bloque igual, como si hubiera salido."""
    red = {"texto": "CRIBADO — opacidad probable",
           "texto_paciente": "TODO ESTE MENSAJE ES TEXTO DEL PACIENTE, no el "
                             "informe:\nme duele",
           "error": None, "resultado": UN_RESULTADO}
    rechazada = texto_del_caso(
        _caso(), {"con_bots": True, "entrega": "rechazada"}, red)
    assert "NI SE INTENTÓ ENVIAR" in rechazada
    assert "NO se intentó enviar, ni siquiera sin éxito" in " ".join(
        rechazada.split())
    entregada = texto_del_caso(
        _caso(), {"con_bots": True, "entrega": "intentada"}, red)
    assert "NI SE INTENTÓ" not in entregada
    # El texto del paciente sale igual en los dos: no perderlo es el punto.
    assert "me duele" in rechazada and "me duele" in entregada


def test_el_corpus_dice_si_los_bloques_clinicos_se_observaron_o_se_afirmaron():
    red = {"texto": "x", "texto_paciente": "", "error": None,
           "resultado": UN_RESULTADO}
    afirmados = texto_del_caso(_caso(), {"con_bots": False,
                                         "bloques": "afirmados"}, red)
    observados = texto_del_caso(_caso(), {"con_bots": True,
                                          "entrega": "intentada",
                                          "bloques": "observados"}, red)
    assert "NO están verificados" in " ".join(afirmados.split())
    assert "LEÍDOS de `consultas`" in " ".join(observados.split())


def test_coincide_mira_tambien_los_dos_bloques_clinicos():
    """Antes comparaba puntuacion, clasificacion y codigo, y nada mas: un mensaje
    con «tos: (valor no reconocido)» y «EXPLORADO — (sin datos completos)» salia
    con «coinciden: si». Son los dos bloques que un clinico lee primero."""
    caso = _caso()
    red = {"resultado": UN_RESULTADO, "error": None}
    bien = {"resultado": UN_RESULTADO, "error": None,
            "sintomas": dict(SINTOMAS_ENVIADOS), "signos": dict(SIGNOS)}
    assert _coincide(bien, caso, red) == "sí"

    # Una respuesta en la clave equivocada: el §4.4 dice que este fallo no da
    # error, da un mensaje clinico distinto.
    torcido = dict(bien, sintomas=dict(SINTOMAS_ENVIADOS, tos="no"))
    assert _coincide(torcido, caso, red).startswith("NO")
    assert "tos" in _coincide(torcido, caso, red)

    sin_signos = dict(bien, signos={"temperatura_c": 38.2})
    assert _coincide(sin_signos, caso, red).startswith("NO")
    assert "signos" in _coincide(sin_signos, caso, red)


def test_coincide_compara_con_los_signos_del_caso_y_no_con_los_fijos():
    """Con `--casos` el bot guarda exactamente los signos que se tecleo para
    ESE caso, que no tienen por que ser los fijos `SIGNOS` (38,2 / 104). Si
    `_coincide` siguiera comparando contra `SIGNOS`, casi todos los casos de
    la sesion saldrian «NO coincide» aunque el bot hubiera guardado justo lo
    que se le mando."""
    propios = {"temperatura_c": 37.9, "frecuencia_cardiaca": 100,
               "crepitantes": True, "murmullo_disminuido": False}
    caso = dict(_caso(), signos=propios)
    red = {"resultado": UN_RESULTADO, "error": None}
    guardo_lo_mismo = {"resultado": UN_RESULTADO, "error": None,
                       "sintomas": dict(SINTOMAS_ENVIADOS), "signos": dict(propios)}
    assert _coincide(guardo_lo_mismo, caso, red) == "sí"

    guardo_otra_cosa = dict(guardo_lo_mismo, signos=dict(SIGNOS))
    assert _coincide(guardo_otra_cosa, caso, red).startswith("NO")
    assert "signos" in _coincide(guardo_otra_cosa, caso, red)


def test_el_resumen_cuenta_el_aviso_por_placa_y_no_por_caso(tmp_path):
    """El perfil 04 reusa a proposito la primera placa de la banda. Contando casos,
    esa placa se contaba dos veces y el «8 de 11» era un «7 de 10» mal sumado."""
    red = {"texto": "CRIBADO — opacidad probable\nEl cribado marca esta placa",
           "texto_paciente": "", "error": None, "resultado": UN_RESULTADO}
    misma = _caso(pid="repetida", clase="Lung Opacity")
    filas = [(misma, {"con_bots": False}, red),
             (_caso(perfil=PERFILES[3], pid="repetida", clase="Lung Opacity"),
              {"con_bots": False}, red)]
    plano = " ".join(resumen(filas, False, tmp_path).split())
    assert "mensajes con el aviso (positivo y RV < 1) 2" in plano
    assert "sobre placas DISTINTAS" in plano
    # La placa lleva opacidad anotada, asi que el aviso NO acierta: 0 de 1, y no
    # 0 de 2, que seria contar la misma placa dos veces.
    assert "0 de esas 1 placas" in plano


def test_el_resumen_dice_si_los_mensajes_los_leyo_alguien(tmp_path):
    red = {"texto": "x", "texto_paciente": "", "error": None,
           "resultado": UN_RESULTADO}
    plano = " ".join(resumen(
        [(_caso(), {"con_bots": True, "entrega": "rechazada"}, red)],
        True, tmp_path).split())
    assert "mensajes que no leyó nadie" in plano
    assert "el chat de los updates es inventado" in plano


def test_el_corpus_dice_que_el_dicom_esta_fabricado_dentro_del_fichero():
    perfil = [p for p in PERFILES if p.fabricado][0]
    texto = texto_del_caso(
        _caso(perfil), {"con_bots": False, "motivo_sin_bots": "--sin-bots"},
        {"texto": "NO PROCEDE", "texto_paciente": "",
         "error": "edad_desconocida: eso", "resultado": None})
    assert "ESTE DICOM ESTÁ FABRICADO" in texto
    assert "se le quitó la etiqueta" in texto


def test_el_resumen_avisa_cuando_el_aviso_y_los_numeros_no_cuadran(tmp_path):
    """La trampa de este resumen es contar el aviso por los numeros y dar por
    hecho que el mensaje lo lleva. Si el texto del §8 cambiara, el contador
    seguiria diciendo la cifra bonita. Por eso se busca EN EL TEXTO."""
    sin_aviso = {"texto": "CRIBADO — opacidad probable", "texto_paciente": "",
                 "error": None, "resultado": dict(UN_RESULTADO)}
    salida = resumen([(_caso(), {"con_bots": False}, sin_aviso)], False, tmp_path)
    assert "ALGO NO CUADRA" in salida

    con_aviso = dict(sin_aviso,
                     texto="CRIBADO — opacidad probable\nEl cribado marca esta "
                           "placa por estar orientado a detectar")
    salida = resumen([(_caso(), {"con_bots": False}, con_aviso)], False, tmp_path)
    assert "ALGO NO CUADRA" not in salida
    assert "y solo en esos" in salida


def test_el_resumen_no_presenta_el_subconjunto_como_si_fuera_la_poblacion(
        tmp_path):
    """El subconjunto sobrerrepresenta la banda a proposito. Un porcentaje suelto
    aqui se leeria como el de la poblacion, que es 23,3 % y lo mide el nivel 1."""
    fila = (_caso(), {"con_bots": False},
            {"texto": "CRIBADO — opacidad probable\nEl cribado marca esta placa",
             "texto_paciente": "", "error": None,
             "resultado": dict(UN_RESULTADO)})
    plano = " ".join(resumen([fila], False, tmp_path).split())
    assert "NO estiman los de la población" in plano
    assert "23,3 %" in plano


# --------------------------------------------------------------------------
# El redactor. Es la pieza que hace que el corpus sea el mensaje del bot y no
# una version nuestra de el.
# --------------------------------------------------------------------------
def _sse(resultado=None, texto_error=None):
    if texto_error is None:
        res = {"content": [{"type": "text", "text": json.dumps(resultado)}],
               "structuredContent": resultado, "isError": False}
    else:
        res = {"content": [{"type": "text", "text": texto_error}],
               "isError": True}
    sobre = {"jsonrpc": "2.0", "id": 1, "result": res}
    return "event: message\ndata: " + json.dumps(sobre) + "\n\n"


def _redactar(http, sintomas=None, signos=None):
    if shutil.which("node") is None:
        pytest.skip("sin `node` no se puede ejecutar el jsCode del workflow")
    decidir = {"chat_id": 7, "t0": 0, "codigo": "K7FM2P",
               "sintomas": sintomas or {"fiebre": "si", "tos": "con_flema",
                                        "dias_evolucion": "3_a_7",
                                        "disnea": "no", "dolor_toracico": "si",
                                        "asma": "no_se", "texto_libre": None},
               "signos": signos if signos is not None else SIGNOS}
    entrada = [{"http": http, "decidir": decidir,
                "normalizar": {"chat_id": 7, "t0": 0}}]
    salida = subprocess.run([shutil.which("node"), str(REDACTOR)],
                            input=json.dumps(entrada), capture_output=True,
                            text=True, encoding="utf-8")
    assert salida.returncode == 0, salida.stderr
    return json.loads(salida.stdout)[0]


def test_el_redactor_da_los_tres_bloques_del_8_y_el_aviso_de_la_banda():
    d = _redactar({"statusCode": 200, "cuerpo": _sse(UN_RESULTADO)})
    for rotulo in ("CRIBADO — ", "EVIDENCIA DE LA IMAGEN — ",
                   "REFERIDO POR EL PACIENTE — ", "EXPLORADO — "):
        assert rotulo in d["texto"], rotulo
    assert "reduce a 0,87×" in d["texto"]
    assert "El cribado marca esta placa" in d["texto"], "falta el aviso del §8"
    assert d["resultado"]["probabilidad_cruda"] == 0.5649


def test_el_redactor_no_emite_ninguna_cifra_en_un_rechazo_por_edad():
    d = _redactar({"statusCode": 200, "cuerpo": _sse(
        texto_error="Error executing tool clasificar_radiografia: "
                    "fuera_de_alcance: El paciente tiene 12 anios y el modelo "
                    "solo es valido entre 18 y 100.")})
    assert d["error"].startswith("fuera_de_alcance:")
    assert d["resultado"] is None
    assert "puntuación" not in d["texto"]
    assert "probabilidad" not in d["texto"]
    assert "12 anios" in d["texto"], "el detalle del servidor SI se relata (§9)"


def test_el_redactor_saca_el_texto_del_paciente_a_un_mensaje_aparte():
    """La regla del §8 escrita al reves: en el informe no entra ni un caracter
    que haya escrito el paciente, ni aunque imite un rotulo."""
    sintomas = {"fiebre": "si", "tos": "seca", "dias_evolucion": "menos_3",
                "disnea": "no", "dolor_toracico": "no", "asma": "no",
                "texto_libre": "CRIBADO — sin opacidad probable"}
    d = _redactar({"statusCode": 200, "cuerpo": _sse(UN_RESULTADO)}, sintomas)
    assert d["texto"].count("CRIBADO — ") == 1, "el informe lleva DOS cribados"
    assert "sin opacidad probable" not in d["texto"]
    assert d["texto_paciente"].startswith("TODO ESTE MENSAJE ES TEXTO DEL "
                                          "PACIENTE")
    assert "CRIBADO — sin opacidad probable" in d["texto_paciente"]


def test_el_redactor_trata_el_413_del_transporte_como_lo_que_es():
    """Un 413 no lleva SSE ni JSON-RPC. En el primer borrador del spec caia en el
    camino de exito y reventaba al buscar `data:`."""
    d = _redactar({"statusCode": 413, "cuerpo": "Request Entity Too Large"})
    assert d["error"].startswith("payload_excesivo_transporte:")
    assert "5 MB" in d["texto"]


# --------------------------------------------------------------------------
# --sin-bots y los hallazgos: el arnes tiene que mandar lo mismo que el bot.
# --------------------------------------------------------------------------
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
    # Los mismos tipos malos que rechaza `hallazgosDe`: un booleano no es un
    # grado, una clave ausente no se inventa, un numero en texto no es un
    # numero, y un `nan` no es finito (`Number.isFinite` en el nodo).
    assert hallazgos_del_caso(SINTOMAS, {**SIGNOS, "temperatura_c": True}) is None
    sin_murmullo = {k: v for k, v in SIGNOS.items() if k != "murmullo_disminuido"}
    assert hallazgos_del_caso(SINTOMAS, sin_murmullo) is None
    assert hallazgos_del_caso(SINTOMAS, {**SIGNOS, "temperatura_c": "38,2"}) is None
    assert hallazgos_del_caso(SINTOMAS, {**SIGNOS, "temperatura_c": float("nan")}) is None


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


# --------------------------------------------------------------------------
# --casos: la sesion con el medico (SP5 §5.6). El arnes teclea la clinica de
# CADA caso, y los mensajes los redactan los nodos reales.
# --------------------------------------------------------------------------
def test_los_botones_y_los_signos_de_cada_caso_reproducen_las_constantes():
    from pruebas.reproducir_casos import (
        BOTONES_PACIENTE, SIGNOS_BOTONES, SIGNOS_TECLEADOS, botones_del_paciente,
        signos_botones, signos_tecleados,
    )
    assert botones_del_paciente(SINTOMAS) == BOTONES_PACIENTE
    assert signos_tecleados(SIGNOS) == SIGNOS_TECLEADOS
    assert signos_botones(SIGNOS) == SIGNOS_BOTONES
    otros = {"temperatura_c": 37.8, "frecuencia_cardiaca": 101,
             "crepitantes": False, "murmullo_disminuido": True}
    assert signos_tecleados(otros) == ("37,8", "101")
    assert signos_botones(otros) == ("s4:no", "s5:si")
    assert botones_del_paciente({**SINTOMAS, "fiebre": "no", "asma": "si"})[0] == "p1:no"
    assert botones_del_paciente({**SINTOMAS, "fiebre": "no", "asma": "si"})[5] == "p6:si"


def test_casos_desde_fichero_construye_los_casos_de_la_sesion(tmp_path):
    from pruebas.reproducir_casos import (
        PERFIL_SESION, SIGNOS, SINTOMAS, casos_desde_fichero, hallazgos_del_caso,
    )
    dcm = tmp_path / "a.dcm"
    dcm.write_bytes(b"x")
    signos = {"temperatura_c": 37.9, "frecuencia_cardiaca": 100,
              "crepitantes": True, "murmullo_disminuido": False}
    sintomas = {**SINTOMAS, "fiebre": "si", "asma": "no"}
    fichero = tmp_path / "casos.json"
    fichero.write_text(json.dumps([
        {"patientId": "p-1", "ruta_dcm": str(dcm), "signos": signos, "sintomas": sintomas},
        {"patientId": "p-2", "ruta_dcm": str(dcm), "signos": SIGNOS, "sintomas": SINTOMAS},
        {"patientId": "p-3", "ruta_dcm": str(dcm), "signos": signos,
         "sintomas": {**sintomas, "asma": "no_se"}},
    ]), encoding="utf-8")
    casos = casos_desde_fichero(fichero)
    assert [c["patientId"] for c in casos] == ["p-1", "p-2", "p-3"]
    assert all(c["perfil"] is PERFIL_SESION for c in casos)
    assert hallazgos_del_caso(casos[0]["sintomas"], casos[0]["signos"]) == {**signos, "asma": "no"}
    assert hallazgos_del_caso(casos[2]["sintomas"], casos[2]["signos"])["asma"] == "no_se"
    # un caso a medias no se acepta: el arnes diria «SIN COMBINAR» y nadie lo notaria
    fichero.write_text(json.dumps([{"patientId": "p-4", "ruta_dcm": str(dcm),
                                    "signos": {"temperatura_c": 38.0}, "sintomas": SINTOMAS}]),
                       encoding="utf-8")
    with pytest.raises(SystemExit, match="cinco hallazgos"):
        casos_desde_fichero(fichero)
    fichero.write_text(json.dumps([{"patientId": "p-5", "ruta_dcm": str(tmp_path / "no.dcm"),
                                    "signos": signos, "sintomas": sintomas}]), encoding="utf-8")
    with pytest.raises(SystemExit, match="no existe la placa"):
        casos_desde_fichero(fichero)


def test_casos_desde_fichero_rechaza_un_patientid_repetido(tmp_path):
    """mensajes.json va por patientId: un caso repetido pisaria el mensaje del
    otro y la sesion se quedaria con uno menos sin que nadie lo notara."""
    from pruebas.reproducir_casos import SIGNOS, SINTOMAS, casos_desde_fichero
    dcm = tmp_path / "a.dcm"
    dcm.write_bytes(b"x")
    caso = {"ruta_dcm": str(dcm), "signos": SIGNOS, "sintomas": SINTOMAS}
    fichero = tmp_path / "casos.json"
    fichero.write_text(json.dumps([{"patientId": "p-1", **caso}, {"patientId": "p-2", **caso},
                                   {"patientId": "p-1", **caso}]), encoding="utf-8")
    with pytest.raises(SystemExit, match="repite el patientId p-1 en los casos 0 y 2"):
        casos_desde_fichero(fichero)


def test_el_explorado_del_mensaje_repite_los_signos_del_caso():
    """Los nodos reales redactan EXPLORADO con lo que el arnes tecleo: 37,8 y
    100 exactos (no puntuan) tienen que salir tal cual, no como 38 y 100."""
    signos = {"temperatura_c": 37.8, "frecuencia_cardiaca": 101,
              "crepitantes": False, "murmullo_disminuido": True}
    d = _redactar({"statusCode": 200, "cuerpo": _sse(UN_RESULTADO)}, signos=signos)
    assert "EXPLORADO — 37,8 °C, 101 lpm, crepitantes no, murmullo disminuido" in d["texto"]


def test_mensajes_json_lleva_el_veredicto_coincide_del_bot():
    """Ruling 12: `preparar_sesion.py --fase mensajes` rechaza un caso cuyo
    `coincide` empieza por «NO»; para eso el veredicto tiene que llegar a
    mensajes.json. `main` necesita el copiloto, así que se ata al código:
    el diccionario de cada caso lleva la clave, leída de la observación."""
    import ast
    arbol = ast.parse((REPO / "pruebas" / "reproducir_casos.py").read_text(encoding="utf-8"))
    principal = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    por_caso = [n for n in ast.walk(principal) if isinstance(n, ast.Dict)
                and any(isinstance(k, ast.Constant) and k.value == "texto_paciente" for k in n.keys)]
    assert len(por_caso) == 1
    claves = {k.value: v for k, v in zip(por_caso[0].keys, por_caso[0].values)}
    assert {"texto", "resultado", "con_bots", "fallo", "coincide"} <= set(claves)
    assert ast.unparse(claves["coincide"]) == "obs.get('coincide')"


# --------------------------------------------------------------------------
# latencias.json: lo que `scripts/medir_latencia.py` lee (SP5 §6.3). Filas
# fabricadas: no hay sistema desplegado al que hablar desde una prueba.
# --------------------------------------------------------------------------
CLAVES_DE_LATENCIA = ["patientId", "perfil", "rechazo_previsto", "con_bots", "fallo",
                      "error_consulta", "coincide", "ms_extremo", "ms_modelo",
                      "error_arnes", "ms_arnes"]


def test_filas_de_latencia_da_una_fila_por_caso_con_lo_que_se_midio():
    from pruebas.reproducir_casos import RECHAZOS_PREVISTOS, filas_de_latencia
    bien = {"texto": "x", "texto_paciente": "", "error": None,
            "resultado": UN_RESULTADO}
    rechazo = {"texto": "NO PROCEDE", "texto_paciente": "",
               "error": "fuera_de_alcance: eso", "resultado": None}
    filas = [
        (_caso(pid="p-1"),
         {"con_bots": True, "ms_extremo": 1840, "ms_arnes": 61.5, "coincide": "sí",
          "error": None, "resultado": dict(UN_RESULTADO, milisegundos=150.0)},
         bien),
        (_caso(perfil=PERFILES[4], pid="p-2"),
         {"con_bots": True, "ms_extremo": 410, "ms_arnes": 12.0, "coincide": "sí",
          "error": "fuera_de_alcance: lo que guardo el bot", "resultado": None},
         rechazo),
        (_caso(pid="p-3"),
         {"con_bots": True, "fallo": "no se pudo subir la placa",
          "ms_arnes": 60.0}, bien),
        (_caso(pid="p-4"), {"con_bots": False, "ms_arnes": 58.25}, bien),
        # El flujo agoto su tiempo limite; la llamada propia del arnes,
        # segundos despues, salio limpia.
        (_caso(pid="p-5"),
         {"con_bots": True, "ms_extremo": 30450, "ms_arnes": 61.0,
          "coincide": "NO: uno dio resultado y el otro no",
          "error": "copiloto_no_responde: tiempo agotado", "resultado": None},
         bien),
    ]
    salida = filas_de_latencia(filas)
    assert [list(f) for f in salida] == [CLAVES_DE_LATENCIA] * 5
    assert salida[0] == {
        "patientId": "p-1", "perfil": "03-banda_contradictoria",
        "rechazo_previsto": False, "con_bots": True, "fallo": None,
        "error_consulta": None, "coincide": "sí", "ms_extremo": 1840,
        # lo que tardo el modelo EN LA CONSULTA MEDIDA, no en la llamada del
        # arnes (que dijo 37,4)
        "ms_modelo": 150.0, "error_arnes": None, "ms_arnes": 61.5}
    # El error que decide es el de la consulta que se midio: el que guardo el
    # bot. El de la redaccion del arnes va aparte.
    assert salida[1]["perfil"] == "05-menor_edad"
    assert salida[1]["rechazo_previsto"] is True
    assert salida[1]["error_consulta"] == "fuera_de_alcance: lo que guardo el bot"
    assert salida[1]["error_arnes"] == "fuera_de_alcance: eso"
    assert salida[1]["ms_modelo"] is None and salida[1]["ms_extremo"] == 410
    assert salida[2]["fallo"] == "no se pudo subir la placa"
    assert salida[2]["ms_extremo"] is None and salida[2]["coincide"] is None
    assert salida[2]["error_consulta"] is None and salida[2]["ms_modelo"] is None
    # Sin bots no hay consulta: ni su error ni su medida; el modelo, el del arnes.
    assert salida[3]["con_bots"] is False and salida[3]["ms_extremo"] is None
    assert salida[3]["error_consulta"] is None and salida[3]["ms_modelo"] == 37.4
    assert salida[3]["ms_arnes"] == 58.25
    assert salida[4]["error_consulta"] == "copiloto_no_responde: tiempo agotado"
    assert salida[4]["error_arnes"] is None and salida[4]["ms_modelo"] is None
    assert salida[4]["ms_extremo"] == 30450
    assert salida[4]["coincide"] == "NO: uno dio resultado y el otro no"
    assert RECHAZOS_PREVISTOS == tuple(p.carpeta for p in PERFILES[4:])
    assert RECHAZOS_PREVISTOS[0] == "05-menor_edad" and len(RECHAZOS_PREVISTOS) == 5
    # un `resultado` que no es un diccionario (una fila rara de `consultas`) no
    # tiene milisegundos que dar, y no revienta
    rara = filas_de_latencia([(_caso(pid="p-6"),
                               {"con_bots": True, "resultado": "no es un diccionario"},
                               bien)])[0]
    assert rara["ms_modelo"] is None and rara["ms_extremo"] is None
    # los casos de la sesion (`--casos`) no son de ningun perfil de rechazo
    from pruebas.reproducir_casos import PERFIL_SESION
    sesion = filas_de_latencia([(_caso(perfil=PERFIL_SESION, pid="p-7"),
                                 {"con_bots": False}, bien)])[0]
    assert sesion["perfil"] == "00-sesion" and sesion["rechazo_previsto"] is False
    # Tal cual a un fichero: ni perfiles ni tipos que JSON no sepa escribir.
    assert json.loads(json.dumps(salida)) == salida
    assert filas_de_latencia([]) == []


def test_un_error_del_flujo_no_entra_en_la_medida_aunque_el_arnes_salga_limpio():
    """De punta a punta: las filas del arnes, tal como las lee el script que
    mide. Un `copiloto_no_responde` de 30 s no puede arrastrar el p95."""
    import importlib.util
    import pathlib

    from pruebas.reproducir_casos import _coincide, filas_de_latencia
    ruta = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "medir_latencia.py"
    spec = importlib.util.spec_from_file_location("medir_latencia", ruta)
    medir = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(medir)
    bien = {"texto": "x", "texto_paciente": "", "error": None, "resultado": UN_RESULTADO}
    rechazo = {"texto": "NO PROCEDE", "texto_paciente": "",
               "error": "fuera_de_alcance: eso", "resultado": None}
    sin_arnes = {"texto": "x", "texto_paciente": "",
                 "error": "copiloto_no_responde: el arnes no pudo", "resultado": None}
    filas = [(_caso(pid=f"p-{i}"),
              {"con_bots": True, "ms_extremo": 1000 + 100 * i, "ms_arnes": 60.0,
               "error": None, "resultado": UN_RESULTADO}, bien)
             for i in range(30)]
    filas.append((_caso(pid="p-lenta"),
                  {"con_bots": True, "ms_extremo": 30450, "ms_arnes": 61.0,
                   "error": "copiloto_no_responde: tiempo agotado", "resultado": None},
                  bien))
    filas.append((_caso(perfil=PERFILES[4], pid="p-menor"),
                  {"con_bots": True, "ms_extremo": 410, "ms_arnes": 12.0,
                   "error": "fuera_de_alcance: eso", "resultado": None}, rechazo))
    # la consulta salio bien y lo que fallo fue la llamada del arnes: no hay
    # con que confirmarla, y se descarta diciendo por que
    filas.append((_caso(pid="p-sin-confirmar"),
                  {"con_bots": True, "ms_extremo": 2000, "ms_arnes": 30000.0,
                   "error": None, "resultado": UN_RESULTADO}, sin_arnes))
    # `coincide` lo pone el arnes, como en `main()`: no se escribe a mano
    for caso, obs, redaccion in filas:
        obs["coincide"] = _coincide(obs, caso, redaccion)
    assert [obs["coincide"] for _, obs, _ in filas[:30]] == ["sí"] * 30
    assert [obs["coincide"] for _, obs, _ in filas[30:]] == [
        "NO: uno dio resultado y el otro no", "sí", "NO: uno dio resultado y el otro no"]
    medido = medir.resumir(json.loads(json.dumps(filas_de_latencia(filas))))
    assert medido["n"] == 30 and medido["maximo_ms"] == 3900.0
    assert medido["descartadas"]["error"] == 1
    assert medido["descartadas"]["rechazo_previsto"] == 1
    assert medido["descartadas"]["no_coincide"] == 1
    assert medido["descartadas"]["total"] == 3


def test_el_arnes_no_llama_de_extremo_a_extremo_a_ms_extremo(tmp_path):
    """`ms_extremo` es el tramo que ve el flujo, y en el resumen entran todas
    las filas: ninguno de los dos es la latencia de extremo a extremo."""
    from pruebas.reproducir_casos import resumen
    bien = {"texto": "CRIBADO — opacidad probable", "texto_paciente": "", "error": None,
            "resultado": UN_RESULTADO}
    obs = {"con_bots": True, "entrega": "intentada", "codigo": "K7QM",
           "ms_extremo": 1840, "ms_arnes": 61.5, "coincide": "sí",
           "error": None, "resultado": UN_RESULTADO}
    caso = texto_del_caso(_caso(), obs, bien)
    assert "ms_extremo (de n8n a la respuesta)" in caso and "1840 ms" in caso
    assert "de extremo a extremo" not in caso
    dicho = resumen([(_caso(), obs, bien)], True, tmp_path)
    assert "ms_extremo, todas las filas (mediana)" in dicho and "1840 ms" in dicho
    assert "de extremo a extremo (mediana)" not in dicho


def test_escribir_latencias_deja_el_json_en_la_carpeta_de_salida(tmp_path):
    from pruebas.reproducir_casos import escribir_latencias, filas_de_latencia
    red = {"texto": "x", "texto_paciente": "", "error": None,
           "resultado": UN_RESULTADO}
    filas = [(_caso(pid="p-1"),
              {"con_bots": True, "ms_extremo": 1840, "ms_arnes": 61.5}, red)]
    destino = tmp_path / "no" / "existe"
    ruta = escribir_latencias(destino, filas)
    assert ruta == destino / "latencias.json"
    assert json.loads(ruta.read_text(encoding="utf-8")) == filas_de_latencia(filas)
    # Una corrida posterior lo pisa entero: no se acumulan las de otro dia.
    escribir_latencias(destino, [])
    assert json.loads(ruta.read_text(encoding="utf-8")) == []


def test_main_escribe_latencias_json_tambien_sin_bots(tmp_path, monkeypatch, capsys):
    """`main` escribe SIEMPRE latencias.json, despues del corpus. Aqui sin
    bots y con el copiloto y el redactor suplantados: lo que se ata es que el
    fichero sale, con una fila por caso, y que el corpus sigue saliendo."""
    from pruebas import reproducir_casos as rc
    casos = [_caso(pid="p-1"), _caso(perfil=PERFILES[4], pid="p-2")]
    redacciones = [
        {"texto": "CRIBADO — opacidad probable\nEl cribado marca esta placa",
         "texto_paciente": "", "error": None, "resultado": UN_RESULTADO},
        {"texto": "NO PROCEDE", "texto_paciente": "",
         "error": "fuera_de_alcance: eso", "resultado": None}]
    monkeypatch.setattr(rc, "comprobar_el_copiloto", lambda url: None)
    monkeypatch.setattr(rc, "construir_casos", lambda por_perfil, solo, destino: casos)
    monkeypatch.setattr(rc, "llamar_al_copiloto", lambda *a, **k: (200, ""))
    monkeypatch.setattr(rc, "redactar", lambda lote: redacciones[:len(lote)])
    monkeypatch.setattr(sys, "argv", ["reproducir_casos.py", "--sin-bots",
                                      "--salida", str(tmp_path)])
    assert rc.main() == 0
    capsys.readouterr()
    filas = json.loads((tmp_path / "latencias.json").read_text(encoding="utf-8"))
    assert [f["patientId"] for f in filas] == ["p-1", "p-2"]
    assert [list(f) for f in filas] == [CLAVES_DE_LATENCIA] * 2
    assert all(f["con_bots"] is False and f["ms_extremo"] is None for f in filas)
    assert all(f["error_consulta"] is None and f["coincide"] is None for f in filas)
    assert all(isinstance(f["ms_arnes"], float) for f in filas)
    assert filas[0]["ms_modelo"] == 37.4
    assert filas[1]["error_arnes"].startswith("fuera_de_alcance")
    assert [f["rechazo_previsto"] for f in filas] == [False, True]
    # El arnes sigue haciendo lo de siempre.
    assert (tmp_path / "RESUMEN.txt").is_file()
    assert (tmp_path / "03-banda_contradictoria" / "p-1.txt").is_file()
