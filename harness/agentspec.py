"""Spec del agente sujeto: lo que el analista puede diagnosticar y parchear.

Todos los campos que componen la entrada del modelo sujeto — instrucciones,
contexto, datos, tools y sub-agentes — viven en esta spec (un JSON versionable
por el loop de mejora). `componer_prompt` los ensambla de forma determinista,
así cada parche del analista es un diff legible sobre la spec, no sobre un
string opaco.

Tools (MVP): la descripción de cada tool entra al prompt; si la salida del
modelo contiene una línea `TOOL: nombre(args)`, el runner puede ejecutar la
función Python asociada e inyectar el resultado en un segundo paso. Los
sub-agentes son specs anidadas que el runner puede correr por separado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class ToolSpec:
    name: str
    description: str
    fn: Callable[[str], str] | None = None  # ejecutor local (no se serializa)


@dataclass
class AgentSpec:
    name: str
    instructions: str
    context: str = ""
    data: str = ""
    tools: list[ToolSpec] = field(default_factory=list)
    subagents: list["AgentSpec"] = field(default_factory=list)
    output_budget: int = 200  # max_new_tokens del sujeto

    # -------- serialización (para versionar parches) --------

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "instructions": self.instructions,
            "context": self.context,
            "data": self.data,
            "tools": [{"name": t.name, "description": t.description} for t in self.tools],
            "subagents": [s.to_dict() for s in self.subagents],
            "output_budget": self.output_budget,
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2))

    @classmethod
    def from_dict(cls, d: dict) -> "AgentSpec":
        return cls(
            name=d["name"], instructions=d["instructions"],
            context=d.get("context", ""), data=d.get("data", ""),
            tools=[ToolSpec(t["name"], t["description"]) for t in d.get("tools", [])],
            subagents=[cls.from_dict(s) for s in d.get("subagents", [])],
            output_budget=d.get("output_budget", 200),
        )


def componer_prompt(spec: AgentSpec, tarea: str, arranque: str = "") -> str:
    """Ensambla la entrada del sujeto. `arranque` es la señal de continuación
    en primera persona para modelos base (ver experimento-interno)."""
    partes = [spec.instructions.strip()]
    if spec.context.strip():
        partes.append(f"Contexto:\n{spec.context.strip()}")
    if spec.data.strip():
        partes.append(f"Datos:\n{spec.data.strip()}")
    if spec.tools:
        lineas = [f"- {t.name}: {t.description}" for t in spec.tools]
        partes.append(
            "Herramientas disponibles (para usar una, escribí una línea "
            "TOOL: nombre(argumentos)):\n" + "\n".join(lineas)
        )
    partes.append(f"Tarea:\n{tarea.strip()}")
    prompt = "\n\n".join(partes) + "\n\nRespuesta:\n"
    return prompt + arranque
