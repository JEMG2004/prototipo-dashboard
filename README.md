# Prototipo del tablero: simulador de políticas de permanencia

Prototipo navegable de lo que describe la sección 7 del *Plan del proyecto y preguntas para Néstor*. Sirve para
discutir las pantallas, el catálogo de variables y la parametrización del prompt con Néstor y con el coordinador
(los "bocetos de las pantallas" de la sección 7.10, pero funcionando).

**Lo importante:** no llama a ningún LLM ni gasta dinero. Un **generador simulado** hace el papel del LLM y sigue los
mismos supuestos que el prompt le pediría. Todo lo demás (catálogo, reglas, plantilla del prompt, modelo, escenarios,
comparación, diagnóstico y registro) es real y se puede reutilizar.

## Cómo ejecutarlo (Windows)

1. Copie la carpeta **fuera de Google Drive** (por ejemplo a `C:\proyectos\prototipo-dashboard`). El entorno virtual
   tiene miles de archivos y no conviene que Drive los sincronice; tampoco la carpeta `.git` del repositorio.
2. Abra el Símbolo del sistema (cmd) en esa carpeta y ejecute (en PowerShell, la activación puede pedir permisos):

   ```
   py -3.13 -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   streamlit run app.py
   ```

   Python 3.13 es el mismo que usan Render y las pruebas de GitHub, y `requirements.txt` fija las versiones exactas
   con que pasaron las pruebas. Si no tiene la 3.13, `py -m venv .venv` con otra versión reciente suele servir.

3. Se abre el navegador en `http://localhost:8501`. La primera vez tarda unos segundos: genera la línea base
   (1000 estudiantes sintéticos) y entrena el modelo con otra población de 3000. Después queda guardado en
   `datos/generados`.

Para apagarlo: `Ctrl + C` en la terminal. Para volver a empezar de cero: borre la carpeta `datos/generados`.

Pruebas sin abrir el navegador (desde la carpeta, con el entorno activado):

```
python -m pruebas.prueba_rapida   # generador, modelo, escenarios y pruebas del nivel 2
python -m pruebas.prueba_app      # recorre todas las pantallas y ejecuta escenarios
python -m pruebas.prueba_acceso   # la clave de acceso del tablero publicado
```

## Subirlo a GitHub

El repositorio va **privado** y **sin licencia**: el código es de la Universidad del Cauca (ver *Propiedad
intelectual*, al final). Desde que exista, la versión que vale es la del repositorio.

Con GitHub Desktop (lo más sencillo):

1. Trabaje en la copia que está fuera de Google Drive (paso 1 de *Cómo ejecutarlo*). Drive sincroniza la carpeta
   `.git` a medias y puede dañarla.
2. **File > Add local repository**, elija la carpeta y, cuando diga que no es un repositorio, **create a
   repository**. Nombre: `prototipo-dashboard`; en *Git ignore* y *License*, **None** (la carpeta ya trae su
   `.gitignore`, y no debe llevar licencia).
3. Revise la lista de cambios: deben aparecer `.github/workflows/pruebas.yml` y `.gitattributes`, y no deben aparecer
   `.venv`, `datos/generados`, `capturas` ni `.streamlit/secrets.toml`. Escriba un mensaje (por ejemplo, «Prototipo
   del tablero») y pulse **Commit to main**.
4. **Publish repository**, con **Keep this code private** marcado.

Con la terminal, si tiene Git y GitHub CLI (`gh auth login` la primera vez):

```
git init -b main
git add .
git commit -m "Prototipo del tablero"
gh repo create prototipo-dashboard --private --source . --push
```

En la página del repositorio, en **Settings**:

- **Collaborators:** invite a Néstor si quiere ver el código. En un repositorio de una cuenta personal, el
  colaborador puede leer y también subir cambios.
- **Advanced Security** (o *Code security*): active **Dependabot alerts**, que avisa si alguna de las versiones
  fijadas en `requirements.txt` tiene una vulnerabilidad conocida.
- **Actions:** no hay que configurar nada. `.github/workflows/pruebas.yml` corre las tres pruebas en cada cambio que
  llega a `main` y muestra el resultado en la pestaña *Actions*. Las pruebas no necesitan claves.

Las claves (la de acceso y, más adelante, la de la API) nunca van al repositorio: se escriben en Render. Si alguna se
sube por error, revóquela donde se creó y cree otra; borrarla del repositorio no basta, porque queda en el historial.

## Publicarlo en Render (para mostrarlo)

La configuración está en `render.yaml`: el plan gratis y una clave de acceso, porque Render no trae control de acceso.

1. Suba la carpeta a GitHub (sección anterior).
2. Entre a [render.com](https://render.com) con su cuenta de GitHub y elija **New > Blueprint**. Escoja el
   repositorio: Render lee `render.yaml` y crea el servicio `simulador-permanencia`.
3. Cuando pida `CLAVE_ACCESO`, escriba la clave que le va a dar a quien vaya a ver el tablero.
4. Espere a que termine: instala los paquetes, corre `precalcular.py` (genera la línea base y entrena el modelo) y
   arranca. La dirección queda como `https://simulador-permanencia.onrender.com`; si ese nombre está ocupado, Render
   le agrega unas letras.
5. Cada vez que suba cambios a `main`, GitHub corre las pruebas y, si pasan, Render lo vuelve a publicar
   (`autoDeployTrigger: checksPass`). Si fallan, no publica: el detalle está en la pestaña *Actions* del repositorio.
   Para publicar a mano: **Manual Deploy** en Render.

En el plan gratis (0,1 CPU y 512 MB):

- se duerme tras 15 minutos sin visitas y tarda cerca de un minuto en despertar: ábralo unos minutos antes de mostrarlo;
- los escenarios que se ejecuten se borran cuando se reinicia o se duerme (la línea base y el modelo no, porque se
  generan al construir);
- todo va más lento que en su computador: ejecutar un escenario tarda unos segundos.

Para la herramienta del proyecto, el plan `0.5c-512mb` (US$7 al mes, 0,5 CPU, la misma memoria) no se duerme, y con
un disco persistente (US$0,25 por GB al mes) no se borra nada. En `render.yaml` están, comentadas, las líneas para eso.
Render cobra por segundo: si para una reunión hace falta más velocidad, se puede pasar al plan de US$7 ese día y volver
al gratis después (un día cuesta unos US$0,23).

Otra opción para mostrarlo, sin tarjeta y sin `render.yaml`: Streamlit Community Cloud (una sola app privada; lo que se
genere se borra al reiniciar). Ahí la clave va en **Secrets** como `CLAVE_ACCESO = "..."`.

## Qué hay en cada pantalla (sección 7.3)

| Pantalla | Qué muestra | Sección del Plan |
|---|---|---|
| Línea base | Desertores esperados, riesgo medio, riesgo por grupo, reparto de cada variable frente a su referencia, distribución del riesgo | 7.2 paso 1 |
| Escenario | Política (ejemplos o personalizada), segmento, palancas con su valor actual, rango y fuente, modo (ajuste o regeneración), réplicas, efecto esperado opcional, costo y tiempo estimados, el prompt que se enviaría | 7.2 pasos 2 y 3, 7.5, 7.6, 7.7 |
| Resultados | Desertores esperados frente a la línea base con su variabilidad, leve o importante frente al ruido, por grupo, comprobación de que la variable cambió, escenarios lado a lado, réplicas | 7.2 paso 4 |
| Supuestos | Catálogo, reglas con su fuente, métricas y calibración del modelo, prompt de la línea base, límites | 7.2 paso 5, 7.4 |
| Diagnóstico | Un resumen («Bien» o «Revisar») de cuatro revisiones: si la población se parece a lo supuesto (JSD), si el modelo reacciona a cada palanca, si sin cambios no hay efecto y con más cambio hay más, y cuánto cambia un escenario solo por azar. Cada una dice cómo se lee y qué hacer si sale mal | 7.9 |
| Registro | Cada ejecución con modo, versión del prompt, tokens, llamadas, tiempo y costo estimados; si se reutilizó | 7.3, 7.7 |

Cada pantalla, y cada sección dentro de ella, empieza con un **Para qué sirve**. La línea base explica además qué es,
cómo se genera y con qué, y *Supuestos* explica por qué se tomaron esas variables de la Tabla 12 y no las otras.

## Qué es real y qué es simulado

| Parte | En el prototipo |
|---|---|
| Catálogo de variables | Real: 13 variables de la Tabla 12 y del formulario de Rosero y Velasco (2026). Se usan los campos, nunca las respuestas. Las distribuciones son supuestos, salvo las cifras publicadas en la monografía, que se citan. |
| Reglas de negocio | Supuestos marcados como tales, para revisar con el coordinador (PT 1.2). |
| Plantilla del prompt | Real (Jinja2). Se llena con cada escenario y se puede ver, pero no se envía. |
| Generación | **Simulada.** El generador imita al LLM: cumple las metas del catálogo y las relaciones de las reglas; en regeneración añade la imprecisión de un LLM. |
| Costos y tiempos | Estimados con lo medido en la prueba de generación (luna: unos 30 estudiantes por llamada, 60 por minuto y US$0,16 por cada 1000). |
| Modelo | Real: bosque aleatorio entrenado con una población sintética aparte de la línea base. |
| Escenarios, comparación, diagnóstico y registro | Reales. |
| Criterios de "leve" o "importante" | Provisionales (en `datos/parametros.yaml`); los fija el coordinador. |

## Dónde se cambian los supuestos

Sin tocar el código:

- `datos/catalogo.yaml`: variables, valores, distribuciones de referencia y fuentes.
- `datos/reglas.yaml`: relaciones entre variables y las hipótesis sobre la deserción (y la tasa supuesta).
- `datos/parametros.yaml`: tamaños, modelo, costos de referencia, imprecisión simulada del LLM, criterios provisionales.

Después de cambiar el catálogo o las reglas, regenere la línea base desde la barra lateral.

## Estructura (paquetes de la sección 7.8)

```
app.py                 navegación (st.Page y st.navigation)
dominio.py             clases del dominio: Variable, ReglaNegocio, ParametroPolitica, Escenario, Poblacion, Ejecucion, Resultado
interfaz/              las seis pantallas, los gráficos, los recursos compartidos y la clave de acceso (acceso.py)
escenarios/            políticas de ejemplo, aplicar (ajuste o regeneración), comparar
generador/             catálogo, plantilla del prompt (plantillas/*.j2), generador simulado, validaciones
modelo/                entrenar, predecir y calibrar
datos/                 los YAML y el almacenamiento en archivos (repositorio.py); lo generado va en datos/generados
pruebas/               pruebas rápidas, de todas las pantallas y de la clave de acceso
precalcular.py         genera la línea base y entrena el modelo al construir (lo usa Render)
render.yaml            el servicio en Render
requirements.txt       los paquetes, con las versiones exactas probadas; .python-version fija Python 3.13
.github/workflows/     las pruebas que GitHub corre en cada cambio
.streamlit/config.toml tema y opciones de Streamlit
```

## Para conectar el LLM más adelante

No hace falta para mostrar el prototipo. Cuando toque (después de la aprobación):

1. Escribir `generador/llm.py` con una clase que tenga los mismos métodos públicos que `GeneradorSimulado`
   (`generar`, `regenerar_variable`, `descendientes`, `prob_desercion`): llena la plantilla, llama a la API por lotes,
   valida cada lote, descarta copias y reintenta. Tres cuidados:
   - **La versión** (`version`) debe cambiar con todo lo que cambia lo generado: además de las huellas del catálogo y
     de las reglas, la versión de la plantilla del prompt (`PlantillaPrompt.version`) y el modelo de lenguaje. Si no,
     la herramienta reutilizaría resultados hechos con otro prompt u otro modelo.
   - **Regenerar:** el simulado regenera variable por variable; con el LLM conviene pedir en una sola llamada por lote
     la palanca y sus descendientes (`descendientes`), para no multiplicar las llamadas.
   - **`prob_desercion`** puede seguir siendo la del simulado: se calcula con las reglas, sin el LLM. El diagnóstico la
     usa para comparar lo que dicen las reglas con lo que estima el modelo.
2. Guardar la clave en `.streamlit/secrets.toml` (ya está en `.gitignore`), nunca en el código; en Render, como una
   variable de entorno más en `render.yaml`, con `sync: false`, igual que `CLAVE_ACCESO`. Mejor una clave de un
   proyecto con límite de gasto.
3. Pasar la generación a segundo plano (un hilo con su barra de progreso), porque con el LLM tarda minutos.

## Privacidad

No hay datos personales ni respuestas individuales de la encuesta de Francisco. Al prompt solo irían porcentajes
agregados y reglas. Del prototipo de Laura no se tomó código, solo la idea de la estructura multipágina, que es la de
Streamlit.

## Propiedad intelectual

El código es de la Universidad del Cauca. Por eso el repositorio es privado y no lleva licencia de uso: sin licencia,
nadie tiene permiso de usarlo, copiarlo ni modificarlo sin autorización de la Universidad.
