"""Trazas JSONL: un registro por paso del agente sujeto.

Cada registro contiene la tríada completa que lee el analista de frontera:
entrada (y la spec que la compuso), pizarrón (prompt y salida, con firmas),
salida, y veredicto del verificador si la tarea define uno.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from .runtime import StepResult
from .signatures import detectar


def registro(paso_id: str, spec_dict: dict, tarea: str, r: StepResult,
             verificacion: dict | None = None) -> dict:
    d = {
        "paso": paso_id,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "spec": spec_dict,
        "tarea": tarea,
        "entrada": r.prompt,
        "salida": r.salida,
        "truncada": r.truncada,
        "segundos": r.segundos,
        "pizarron_prompt": {**asdict(r.ws_prompt), "firmas": detectar(r.ws_prompt.top)},
        "pizarron_salida": (
            {**asdict(r.ws_salida), "firmas": detectar(r.ws_salida.top)}
            if r.ws_salida else None
        ),
        "verificacion": verificacion,
    }
    return d


class TraceWriter:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a")

    def write(self, rec: dict) -> None:
        self._fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()
