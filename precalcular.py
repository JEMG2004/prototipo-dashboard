"""Genera la línea base y entrena el modelo antes de publicar el tablero. Render lo corre al construir (render.yaml).

Así la primera visita no espera: en el plan gratis de Render hay 0,1 CPU, y generar la línea base y entrenar el modelo
tomaría más de un minuto. Como lo que se crea al construir queda en la publicación, tampoco hay que volver a generarlo
cada vez que el servicio se despierta.

Uso (desde la carpeta del prototipo):  python precalcular.py
"""
import os

from interfaz import estado

if os.environ.get("CARPETA_GENERADOS"):
    # El disco persistente no existe mientras Render construye; ahí se genera en la primera visita y queda guardado.
    print("Con disco persistente: la línea base se generará en la primera visita.")
else:
    estado.linea_base()
    estado.modelo_actual()
    print("Línea base y modelo listos en datos/generados.")
