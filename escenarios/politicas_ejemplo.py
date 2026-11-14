"""Políticas de ejemplo para probar la herramienta.

No son propuestas: las políticas reales las define el coordinador (PT 1.1).
Cada una está escrita como parámetro -> parte del prompt -> parte de la población
(sección 7.10 del Plan).
"""
from __future__ import annotations

from dominio import Condicion, ParametroPolitica, Segmento

PERSONALIZADA = "Personalizada"

POLITICAS = {
    "Subir el promedio un 10 % (ejemplo de Néstor)": {
        "descripcion": "Néstor, reunión 5: si una estrategia sube el promedio un 10 %, ¿hay menos desertores? De 100 a 98 es una mejora leve; de 100 a 50, significativa.",
        "segmento": Segmento([]),
        "palancas": [ParametroPolitica("promedio", "multiplicar", valor=1.10, cobertura=1.0)],
    },
    "Tutorías para promedio menor a 3,0": {
        "descripcion": "Acompañamiento a quienes tienen promedio menor a 3,0: se supone que el 70 % sube 0,4 puntos.",
        "segmento": Segmento([Condicion("promedio", minimo=0.0, maximo=2.9)]),
        "palancas": [ParametroPolitica("promedio", "sumar", valor=0.4, cobertura=0.7)],
    },
    "Apoyo económico (ejemplo de la sección 7.5)": {
        "descripcion": "La mitad de quienes dicen que los costos afectan su permanencia deja de tener ese problema.",
        "segmento": Segmento([]),
        "palancas": [ParametroPolitica("costos_afectan", "cambiar", desde="Sí", hacia="No", cobertura=0.5)],
    },
    "Apoyo psicosocial": {
        "descripcion": "A quienes dicen que el estrés afecta mucho su rendimiento (4 o 5): se supone que el 60 % baja un punto.",
        "segmento": Segmento([Condicion("estres", minimo=4, maximo=5)]),
        "palancas": [ParametroPolitica("estres", "sumar", valor=-1, cobertura=0.6)],
    },
    "Mentorías entre pares en primeros semestres": {
        "descripcion": "Semestres 1 a 3: la mitad de quienes no se sienten respaldados por sus compañeros pasa a sentirse respaldada.",
        "segmento": Segmento([Condicion("semestre", minimo=1, maximo=3)]),
        "palancas": [ParametroPolitica("respaldo_companeros", "cambiar", desde="No", hacia="Sí", cobertura=0.5)],
    },
    "Paquete: apoyo económico, mentorías y psicosocial": {
        "descripcion": "Varias medidas a la vez en los semestres 1 a 4, para compararlas con una sola medida (como en Guzmán Rincón et al.).",
        "segmento": Segmento([Condicion("semestre", minimo=1, maximo=4)]),
        "palancas": [
            ParametroPolitica("costos_afectan", "cambiar", desde="Sí", hacia="No", cobertura=0.3),
            ParametroPolitica("respaldo_companeros", "cambiar", desde="No", hacia="Sí", cobertura=0.4),
            ParametroPolitica("estres", "sumar", valor=-1, cobertura=0.3),
        ],
    },
    PERSONALIZADA: {
        "descripcion": "Arme su propia política: elija el segmento y las variables que cambia.",
        "segmento": Segmento([]),
        "palancas": [ParametroPolitica("promedio", "sumar", valor=0.2, cobertura=1.0)],
    },
}
