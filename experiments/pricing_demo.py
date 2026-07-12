"""Corrida end-to-end de la suite pricing (v1→v3b) sobre el agente sujeto.

Reproduce localmente el experimento del artículo: cuatro versiones del prompt,
cada una con lectura del pizarrón (prompt y salida), firmas, y verificación
numérica de la respuesta. La traza queda en resultados/pricing/trace.jsonl
para que el analista de frontera la lea con analyst/ANALYST.md.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from harness import AgentSpec, Runtime, TraceWriter, componer_prompt, registro


def calc(expr: str) -> str:
    """Ejecutor de la tool calc: aritmética pura, nada más."""
    limpio = expr.strip()
    if not re.fullmatch(r"[0-9+\-*/().,^ x]*", limpio) or "x" in limpio:
        return f"error: expresión no aritmética: {limpio!r}"
    try:
        return str(eval(limpio.replace("^", "**").replace(",", ""), {"__builtins__": {}}))
    except Exception as e:
        return f"error: {e}"


def paso_con_tools(rt: Runtime, prompt: str, spec: AgentSpec, *, rastrear,
                   max_rondas: int = 12):
    """Loop mínimo de tools: ejecuta cada línea TOOL: calc(...) y continúa la
    generación con el resultado inyectado. Devuelve (resultado_final, rondas)."""
    llamadas = []
    for _ in range(max_rondas):
        r = rt.step(prompt, max_new_tokens=spec.output_budget, rastrear=rastrear)
        m = re.search(r"TOOL:\s*calc\((.*?)\)\s*$", r.salida, re.M)
        if not m:
            return r, llamadas
        resultado = calc(m.group(1))
        llamadas.append({"expr": m.group(1), "resultado": resultado})
        corte = r.salida[: m.end()]
        prompt = prompt + corte + f"\nResultado de calc: {resultado}\n"
    return r, llamadas

RASTREAR = [
    " information", " data", " datos", " specific", " need", " ask",
    " quadratic", " equation", " optimization", " vertex", " price",
    " cost", " demand", " profit", " verification", " verify", " check",
    " sign", " minus", " plus", " algebra",
]


def verificar(salida: str, esperado: dict) -> dict:
    """Busca el precio y la ganancia esperados en la salida."""
    plano = salida.replace(",", ".").replace(" ", " ")
    numeros = {float(n) for n in re.findall(r"\d+(?:\.\d+)?", plano)}
    precio_ok = any(abs(n - esperado["precio"]) < 0.01 for n in numeros)
    # 3.025 con separador de miles parseado como 3.025 → aceptar también 3.025
    ganancia_ok = any(
        abs(n - esperado["ganancia"]) < 0.5 or abs(n - esperado["ganancia"] / 1000) < 0.001
        for n in numeros
    )
    # Parche del analista (iter 1): la versión anterior sobre-detectaba
    # ("need"/"falta" sueltos). Ahora exige una petición explícita de datos.
    pide_datos = bool(re.search(
        r"(necesito (más |los |algunos )?(datos|información|informacion)"
        r"|falta información|falta informacion|faltan datos"
        r"|proporcioname|proporcióname|por favor (proporcion|indic|comparte)"
        r"|need (more|additional) (data|information)"
        r"|please provide|could you (provide|share)"
        r"|sin (tener acceso a |conocer )?(los |esos |tus )?datos"
        r"|no puedo (darte|calcular|responder)|desconozco)", plano, re.I))
    return {
        "correcta": precio_ok and ganancia_ok,
        "precio_ok": precio_ok,
        "ganancia_ok": ganancia_ok,
        "pide_datos": pide_datos,
    }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=1, help="número de iteración (nombra la traza)")
    ap.add_argument("--solo", default=None, help="correr solo esta versión")
    args = ap.parse_args()
    sufijo = "" if args.iter == 1 else str(args.iter)

    suite = json.loads((RAIZ / "tasks" / "pricing.json").read_text())
    out_dir = RAIZ / "resultados" / "pricing"
    tw = TraceWriter(out_dir / f"trace{sufijo}.jsonl")

    print("[runtime] cargando modelo sujeto + lens ...")
    rt = Runtime("qwen")
    print(f"[runtime] listo: {rt.model} | capas {rt.capas[0]}..{rt.capas[-1]}")

    resumen = []
    versiones = suite["versiones"]
    if args.solo:
        versiones = {args.solo: versiones[args.solo]}
    for version, campos in versiones.items():
        spec = AgentSpec.from_dict({"name": f"pricing-{version}", **campos})
        prompt = componer_prompt(spec, suite["tarea"], arranque=rt.arranque)
        print(f"\n===== {version} =====")
        if spec.tools:
            r, llamadas = paso_con_tools(rt, prompt, spec, rastrear=RASTREAR)
            print(f"[tools] {len(llamadas)} llamadas: {llamadas}")
        else:
            r, llamadas = rt.step(
                prompt, max_new_tokens=spec.output_budget, rastrear=RASTREAR), []
        v = verificar(r.salida, suite["esperado"])
        rec = registro(version, spec.to_dict(), suite["tarea"], r, verificacion=v)
        rec["tools_llamadas"] = llamadas
        tw.write(rec)

        print(f"[salida] ({r.segundos}s, truncada={r.truncada}) "
              f"{r.salida.strip()[:280]}")
        print(f"[verificador] {v}")
        for etapa in ("pizarron_prompt", "pizarron_salida"):
            p = rec[etapa]
            if p:
                firmas = {k: v_["score"] for k, v_ in p["firmas"].items()
                          if not k.startswith("_") and v_["score"] > 0}
                print(f"[{etapa}] top: {[t['token'] for t in p['top'][:12]]}")
                print(f"[{etapa}] firmas: {firmas} | dominante: {p['firmas']['_dominante']}")
        resumen.append({
            "version": version, "correcta": v["correcta"],
            "truncada": r.truncada, "pide_datos": v["pide_datos"],
            "dominante_salida": rec["pizarron_salida"]["firmas"]["_dominante"]
            if rec["pizarron_salida"] else None,
        })

    tw.close()
    (out_dir / f"resumen{sufijo}.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2))
    print("\n[resumen]")
    for fila in resumen:
        print(" ", fila)
    print(f"[guardado] {out_dir}/trace.jsonl y resumen.json")


if __name__ == "__main__":
    main()
