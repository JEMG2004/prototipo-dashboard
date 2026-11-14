"""Pruebas rápidas del núcleo, sin la interfaz.

Uso (desde la carpeta del prototipo):  python -m pruebas.prueba_rapida

Comprueba las pruebas del nivel 2 (sección 0 del Plan) con el generador simulado:
1. la población cumple las metas de entrada;
2. regenerar sin cambios da lo mismo que la línea base (dentro del ruido);
3. repetir un escenario da resultados parecidos;
4. un cambio mayor no produce un efecto menor ni de sentido contrario.
"""
from __future__ import annotations

import time

from dominio import Escenario
from escenarios.aplicar import ejecutar
from escenarios.politicas_ejemplo import PERSONALIZADA, POLITICAS
from generador.catalogo import cargar_catalogo, cargar_parametros, cargar_reglas
from generador.plantilla_prompt import PlantillaPrompt, estimar_tokens
from generador.simulado import GeneradorSimulado
from generador.validacion import metas_de_entrada
from modelo.modelo import ModeloRiesgo


def main() -> None:
    t0 = time.time()
    catalogo = cargar_catalogo()
    reglas = cargar_reglas(catalogo)
    params = cargar_parametros()
    gen = GeneradorSimulado(catalogo, reglas)
    print(f"Orden de generación: {', '.join(gen.orden)}")

    pp = params["poblacion"]
    base = gen.generar(pp["n_linea_base"], pp["semilla_linea_base"])
    entrenamiento = gen.generar(pp["n_entrenamiento"], pp["semilla_entrenamiento"])

    # 1. Metas de entrada
    metas = metas_de_entrada(base, catalogo)
    print("\n1. Metas de entrada (JSD, base 2):")
    for _, f in metas.iterrows():
        print(f"   {f['variable']:<24} JSD={f['jsd']:.4f}  mayor diferencia={f['mayor_diferencia_pp']:.1f} pp")
    assert (metas["jsd"] < params["diagnostico"]["jsd_referencia"]).all()
    tasa = (base["desertor"] == "Sí").mean()
    print(f"   Tasa de desertores en la línea base: {tasa:.3f} (objetivo {reglas.tasa_objetivo})")

    mp = params["modelo"]
    modelo = ModeloRiesgo(catalogo, mp["arboles"], mp["min_muestras_hoja"], pp["semilla_entrenamiento"])
    m = modelo.entrenar(entrenamiento, mp["proporcion_prueba"], pp["semilla_entrenamiento"], mp["umbral_riesgo"], "prueba")
    print(f"\nModelo: AUC={m['auc']:.3f} F1={m['f1']:.3f} recall={m['recall']:.3f} Brier={m['brier']:.3f} "
          f"(referencia {m['brier_referencia']:.3f})")
    print("   Importancia:", ", ".join(f"{k}={v:.3f}" for k, v in sorted(m["importancia"].items(), key=lambda x: -x[1])))
    p_base = modelo.predecir(base)
    print(f"   Línea base: desertores esperados={p_base.sum():.1f}; en riesgo alto={100 * (p_base >= mp['umbral_riesgo']).mean():.1f} %")

    plantilla = PlantillaPrompt(catalogo, reglas)
    print("\nEscenarios de ejemplo:")
    for nombre, pol in POLITICAS.items():
        if nombre == PERSONALIZADA:
            continue
        for modo in ("ajuste", "regeneracion"):
            esc = Escenario(nombre, nombre, pol["descripcion"], pol["segmento"], pol["palancas"], modo, 5, 1)
            resumen, riesgos, _ = ejecutar(esc, base, p_base, gen, modelo, catalogo, params)
            c = resumen["clasificacion"]["poblacion"]
            cs = resumen["clasificacion"]["segmento"]
            ok = all(f["cumple"] for f in resumen["comprobacion"])
            print(f"   {nombre[:44]:<44} {modo:<13} pob: {c['base']:.1f}→{c['media']:.1f} ({100 * c['delta_relativo']:+.1f} %, sd {c['sd']:.2f}) "
                  f"{c['etiqueta']:<20} seg: {100 * cs['delta_relativo']:+.1f} % {cs['etiqueta']:<20} comprobación={'sí' if ok else 'revisar'}")
            if modo == "regeneracion" and nombre.startswith("Apoyo económico"):
                texto = plantilla.escenario(esc, base, gen, params)
                print(f"      prompt: {len(texto)} caracteres ≈ {estimar_tokens(texto)} tokens")

    # 2 y 4. Prueba nula y cambios grandes
    pol = POLITICAS["Subir el promedio un 10 % (ejemplo de Néstor)"]
    print("\n2 y 4. Dosis (0 = regenerar sin cambios):")
    previo = None
    for dosis in params["diagnostico"]["dosis"]:
        esc = Escenario("dosis", "dosis", "", pol["segmento"], pol["palancas"], "regeneracion", 5, 3)
        resumen, _, _ = ejecutar(esc, base, p_base, gen, modelo, catalogo, params, dosis=dosis)
        c = resumen["clasificacion"]["poblacion"]
        print(f"   dosis {dosis:>4}: Δ={c['delta']:+.2f} (min {c['min'] - c['base']:+.2f}, max {c['max'] - c['base']:+.2f}) {c['etiqueta']}")
        if dosis == 0:
            assert c["nivel"] == "ruido", "Regenerar sin cambios debería quedar dentro del ruido"
        if previo is not None:
            assert c["delta"] <= previo + 2 * max(c["sd"], 0.5), "Un cambio mayor no debería dar un efecto menor"
        previo = c["delta"]

    print(f"\nPrompt de línea base ≈ {estimar_tokens(plantilla.linea_base(entrenamiento))} tokens; versión {plantilla.version}")
    print(f"Todo bien en {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
