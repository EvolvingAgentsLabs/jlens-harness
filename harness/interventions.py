"""Intervenciones causales sobre el residual stream: STEER / ABLATE / SWAP.

Generalización de lo implementado en ../experimento-interno: la dirección de un
concepto (un token único del vocabulario) en la capa l se obtiene
transportando su fila del unembedding con J_l^T. Réplica estructural de las
intervenciones del demo de Neuronpedia (cuyo código exacto no es público).

- STEER(+alpha): suma alpha * ||h|| * v_concepto en cada posición.
- ABLATE: proyecta fuera la componente positiva sobre v_concepto.
- SWAP: proyecta fuera la componente sobre v_origen y reinyecta esa misma
  magnitud sobre v_destino.

Uso:
    with Intervention(rt, swap=(" resentment", " acceptance")):
        r = rt.step(prompt)
    with Intervention(rt, ablate=[" arguably"]):
        ...
    with Intervention(rt, steer={" verification": 0.15}):
        ...
"""

from __future__ import annotations

import torch


class Intervention:
    def __init__(self, rt, *, swap: tuple[str, str] | None = None,
                 ablate: list[str] | None = None,
                 steer: dict[str, float] | None = None,
                 capas: list[int] | None = None):
        self._rt = rt
        self._capas = capas or rt.capas
        self._handles: list = []
        self._ops: list[tuple[str, dict]] = []

        def direccion(palabra: str, layer: int) -> torch.Tensor:
            tid = rt.token_unico(palabra)
            if tid is None:
                raise ValueError(f"{palabra!r} no es un token único del vocabulario")
            u = rt.model._lm_head.weight[tid].detach().float().cpu()
            v = rt.lens.jacobians[layer].T @ u
            v = v / v.norm()
            return v.to(rt.model.input_device, rt.model._embed_tokens.weight.dtype)

        for l in self._capas:
            ops = []
            if swap:
                ops.append(("swap", direccion(swap[0], l), direccion(swap[1], l), None))
            for palabra in ablate or []:
                ops.append(("ablate", direccion(palabra, l), None, None))
            for palabra, alpha in (steer or {}).items():
                ops.append(("steer", direccion(palabra, l), None, float(alpha)))
            self._ops.append((l, ops))

    def _hook(self, ops):
        def fn(module, inputs, output):
            h = output if torch.is_tensor(output) else output[0]
            for kind, v_a, v_b, alpha in ops:
                if kind == "steer":
                    escala = h.float().norm(dim=-1, keepdim=True).to(h.dtype)
                    h = h + alpha * escala * v_a
                else:
                    a = (h.float() @ v_a.float()).clamp(min=0.0).to(h.dtype)
                    h = h - a.unsqueeze(-1) * v_a
                    if kind == "swap":
                        h = h + a.unsqueeze(-1) * v_b
            if torch.is_tensor(output):
                return h
            return (h,) + tuple(output[1:])
        return fn

    def __enter__(self):
        for l, ops in self._ops:
            if ops:
                self._handles.append(
                    self._rt.model.layers[l].register_forward_hook(self._hook(ops))
                )
        return self

    def __exit__(self, *exc):
        for h in self._handles:
            h.remove()
        self._handles = []
