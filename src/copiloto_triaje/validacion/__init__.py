"""Validación semisintética de la combinación bayesiana y sesión con el médico (SP5).

Nada de este paquete toca el servidor ni los bots: lee las puntuaciones
congeladas del modelo, sortea clínica con la distribución publicada de la
puntuación de Heckerling, y compara lo que `heckerling.combinacion` calcula
con lo que el generador sabe. Los módulos son puros; los scripts de
`scripts/` son los únicos que leen y escriben ficheros de la sesión.
"""
