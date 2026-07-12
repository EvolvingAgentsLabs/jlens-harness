"""Detectores de firmas sobre el readout del pizarrón.

Cada firma es un conjunto de conceptos ancla; su score es la fracción de la
intensidad total del top del pizarrón capturada por conceptos de la firma.
Codifica los hallazgos del experimento pricing v1→v3b:

- missing_info: el prompt sub-especifica (v1).
- computo: el modelo entró en modo resolución (v2+). Incluye dígitos.
- verificacion: la instrucción de verificar está internalizada (v3/v3b).
- signos: atención al signo (la instrucción quirúrgica de v3b).
"""

from __future__ import annotations

import re

FIRMAS: dict[str, set[str]] = {
    "missing_info": {
        "information", "data", "datos", "información", "informacion", "specific",
        "specifics", "details", "detalles", "provide", "need", "needs", "needed",
        "missing", "falta", "faltan", "ask", "asking", "question", "pregunta",
        "preguntar", "options", "example", "examples", "clarify", "unknown",
        "assumptions", "assume",
    },
    "computo": {
        "quadratic", "cuadrática", "cuadratica", "equation", "ecuación",
        "ecuacion", "optimization", "optimización", "optimizacion", "vertex",
        "vértice", "vertice", "formula", "fórmula", "derivative", "derivada",
        "maximize", "maximizar", "profit", "ganancia", "revenue", "demand",
        "demanda", "cost", "costo", "units", "unidades", "dollars", "price",
        "precio", "calculate", "calcular", "compute", "algebra", "linear",
        "solve", "solving",
    },
    "verificacion": {
        "verification", "verificación", "verificacion", "verify", "verificar",
        "check", "checking", "comprobar", "revisar", "meticulously", "carefully",
        "cuidadosamente", "confirm", "confirmar", "validate", "validar",
        "recompute", "double",
    },
    "signos": {
        "sign", "signs", "signo", "signos", "minus", "menos", "plus", "más",
        "mas", "negative", "negativo", "positive", "positivo", "subtract",
        "restar", "suma", "sumar",
    },
}


def _es_digito(token: str) -> bool:
    return re.fullmatch(r"\d+", token.strip()) is not None


def detectar(top: list[dict]) -> dict:
    """Scores de firma sobre el top del pizarrón (lista {token, intensidad}).

    Devuelve {firma: {score, conceptos: [token...]}}. `computo` suma también
    los tokens-dígito. Los scores son fracciones de la intensidad total del
    top (comparables entre corridas del mismo runtime, no entre modelos).
    """
    total = sum(t["intensidad"] for t in top) or 1.0
    out = {}
    for nombre, anclas in FIRMAS.items():
        peso, conceptos = 0.0, []
        for t in top:
            tok = t["token"].lower()
            if tok in anclas or (nombre == "computo" and _es_digito(tok)):
                peso += t["intensidad"]
                conceptos.append(t["token"])
        out[nombre] = {"score": round(peso / total, 3), "conceptos": conceptos}
    dominante = max(out, key=lambda k: out[k]["score"])
    out["_dominante"] = dominante if out[dominante]["score"] > 0 else None
    return out
