"""Genera la línea base y entrena el modelo antes de publicar el tablero. Render (render.yaml) y Fly.io (Dockerfile) lo
corren al construir.

Así la primera visita no espera: en el plan gratis de Render hay 0,1 CPU, y generar la línea base y entrenar el modelo
tomaría más de un minuto. Lo generado queda en datos/generados, dentro de la publicación. Con disco persistente
(CARPETA_GENERADOS), que no existe mientras se construye, la app lo copia al disco la primera vez que arranca
(datos/repositorio.py).

Uso (desde la carpeta del prototipo):  python precalcular.py
"""
import os

# Siempre en datos/generados, aunque la plataforma ya tenga definida la carpeta del disco.
os.environ.pop("CARPETA_GENERADOS", None)

from interfaz import estado  # noqa: E402  (después de quitar la variable)

estado.linea_base()
estado.modelo_actual()
print("Línea base y modelo listos en datos/generados.")
