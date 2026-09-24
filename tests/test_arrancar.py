"""Pruebas del punto de entrada del contenedor.

Solo se comprueba una cosa, y es la que esta rama ya perdio una vez: que
`AUC_VALIDACION` sea de verdad obligatoria. Es una afirmacion de calidad sobre
LOS PESOS que se le muestra al profesional en cada respuesta, y un default
silencioso sobreviviria a un reentrenamiento citando la cifra vieja. El
comentario del fichero siempre dijo eso; la linea de debajo le ponia "0.883"
por defecto y lo desmentia.

Se ejecuta en un subproceso porque el fichero carga el modelo al importarse.
"""
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARRANCAR = RAIZ / "servidor" / "arrancar.py"

# El comienzo del mensaje de la negativa. Se busca esta frase y no solo el
# nombre de la variable: el nombre tambien aparece en el traceback de cualquier
# OTRO fallo posterior -sale en la linea de codigo que lo provoco-, y una prueba
# que solo lo buscara pasaria tambien cuando el arranque murio de otra cosa.
NEGATIVA = "Falta la variable de entorno AUC_VALIDACION"


def _arrancar(**entorno):
    """Lanza `arrancar.py` con rutas de pesos inexistentes a proposito.

    Asi el arranque muere siempre, y lo que la prueba mira es DE QUE muere: si
    de la variable que falta o de los pesos que no estan. Nunca llega a
    `uvicorn.run`.
    """
    env = {k: v for k, v in os.environ.items() if k != "AUC_VALIDACION"}
    env["PYTHONPATH"] = str(RAIZ / "src")
    env["RUTA_PESOS"] = str(RAIZ / "no_existen_estos_pesos.pt")
    env["RUTA_CALIBRADOR"] = str(RAIZ / "no_existe_este_calibrador.json")
    env.update(entorno)
    return subprocess.run([sys.executable, str(ARRANCAR)], env=env,
                          capture_output=True, text=True, timeout=300)


def test_sin_auc_de_validacion_el_arranque_falla_diciendo_cual_falta():
    """Sin la variable, el arranque se niega y el mensaje dice que hay que
    declararla. No arranca sirviendo una cifra de calidad inventada."""
    resultado = _arrancar()

    assert resultado.returncode != 0
    salida = resultado.stdout + resultado.stderr
    assert NEGATIVA in salida, salida
    # Y no muere de los pesos: se niega ANTES de intentar cargar nada.
    assert "no_existen_estos_pesos.pt" not in salida, salida


def test_con_auc_de_validacion_el_arranque_pasa_de_esa_comprobacion():
    """La hermana de la anterior, y la que impide que la comprobacion se
    convierta en un "siempre falla" que nadie distinguiria de un acierto: con la
    variable puesta, el arranque ya no se queja de ella y llega a lo siguiente,
    que aqui son los pesos inexistentes."""
    resultado = _arrancar(AUC_VALIDACION="0.8827")

    salida = resultado.stdout + resultado.stderr
    assert NEGATIVA not in salida, salida
    assert "no_existen_estos_pesos.pt" in salida, salida
