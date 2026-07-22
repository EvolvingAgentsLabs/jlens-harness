"""Runtime instrumentado: modelo abierto local + Jacobian lens.

Carga el modelo sujeto y su lens pre-ajustado, genera texto, y lee el
"pizarrón" (readout J-space) tanto sobre el prompt como sobre la salida
generada. Todo devuelto como estructuras simples listas para la traza.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import torch

import jlens

LENS_REPO = "neuronpedia/jacobian-lens"

MODELS = {
    "qwen": {
        "hf": "Qwen/Qwen3.5-4B",
        "lens_file": "qwen3.5-4b/jlens/Salesforce-wikitext/Qwen3.5-4B_jacobian_lens_n1000.pt",
        "lens_revision": "qwen-n1000",
        # Parche del analista (iter 1 de pricing): el modelo emite un bloque
        # <think> que consume el presupuesto de salida antes de responder;
        # prefijar un think vacío lo lleva directo a la respuesta.
        "arranque": "<think>\n\n</think>\n\n",
        # Parche del analista (iter 2 de pricing): repetition_penalty +
        # no_repeat_ngram prohíben copiar 4-gramas del prompt y corrompen los
        # números de los datos ("100 unidades" → "108 unidades"). Para un
        # modelo con chat-training alcanza greedy puro.
        "decoding": {"do_sample": False},
    },
    "gemma4b": {
        "hf": "unsloth/gemma-3-4b-pt",
        "lens_file": "gemma-3-4b/jlens/Salesforce-wikitext/gemma-3-4b-pt_jacobian_lens.pt",
        "lens_revision": None,
        "arranque": "",
        # Modelo base: sin anti-bucle divaga en loops; ojo con la fidelidad
        # numérica si la tarea exige copiar datos.
        "decoding": {"do_sample": False, "repetition_penalty": 1.3,
                     "no_repeat_ngram_size": 4},
    },
    "gemma4e4b": {
        # Réplica cross-modelo de sleep-harness. Lens ajustado por Neuronpedia
        # sobre google/gemma-4-E4B (wikitext, n=663, bf16) — ver config.yaml
        # del repo del lens. Modelo no gated.
        "hf": "google/gemma-4-E4B",
        "lens_file": "gemma-4-e4b/jlens/Salesforce-wikitext/gemma-4-E4B_jacobian_lens.pt",
        "lens_revision": None,
        "arranque": "",
        # Punto de partida conservador (mismo perfil que gemma-3 base);
        # el smoke de compatibilidad calibra si hace falta ajustar.
        "decoding": {"do_sample": False, "repetition_penalty": 1.3,
                     "no_repeat_ngram_size": 4},
    },
}

STOPWORDS = set(
    "the a an of to and in is it i my me que de la el en y un una los las es "
    "no se le lo con por para del al mi su this that as at on for with be was "
    "are do not what how why can could would should will now here there".split()
)


def _es_significativo(texto: str) -> bool:
    t = texto.strip().lower()
    if re.fullmatch(r"\d+", t):
        return True  # los dígitos son señal (firma de cómputo)
    return (
        len(t) >= 3 and t not in STOPWORDS
        and re.fullmatch(r"[a-záéíóúüñ]+", t) is not None
    )


@dataclass
class Workspace:
    """Lectura del pizarrón en un rango de posiciones."""

    top: list[dict]                    # [{token, intensidad}]
    rastreados: dict[str, float]      # concepto -> intensidad máx en la ventana
    posiciones: tuple[int, int]       # rango [desde, hasta) leído

    def tokens_top(self) -> list[str]:
        return [t["token"] for t in self.top]


@dataclass
class StepResult:
    prompt: str
    salida: str
    truncada: bool                     # se cortó por max_new_tokens
    segundos: float
    ws_prompt: Workspace
    ws_salida: Workspace | None
    meta: dict = field(default_factory=dict)


class Runtime:
    def __init__(self, model_key: str = "qwen", device: str | None = None,
                 dtype: torch.dtype = torch.bfloat16):
        import transformers

        spec = MODELS[model_key]
        self.model_key = model_key
        device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        try:
            self.hf_model = transformers.AutoModelForCausalLM.from_pretrained(
                spec["hf"], dtype=dtype
            ).to(device)
        except ValueError:
            self.hf_model = transformers.AutoModelForImageTextToText.from_pretrained(
                spec["hf"], dtype=dtype
            ).to(device)
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(spec["hf"])
        self.arranque: str = spec.get("arranque", "")
        self.decoding: dict = spec.get("decoding", {"do_sample": False})
        self.model = jlens.from_hf(self.hf_model, self.tokenizer)
        self.lens = jlens.JacobianLens.from_pretrained(
            LENS_REPO, filename=spec["lens_file"], revision=spec["lens_revision"]
        )
        # Ventana de capas medias-tardías (análogo de 18-63/64 del demo).
        desde = int(round(self.model.n_layers * 18 / 64))
        self.capas = [l for l in self.lens.source_layers
                      if desde <= l < self.model.n_layers]

    # ---------- lectura del pizarrón ----------

    def token_unico(self, palabra: str) -> int | None:
        ids = self.tokenizer(palabra, add_special_tokens=False).input_ids
        return ids[0] if len(ids) == 1 else None

    @torch.no_grad()
    def leer_pizarron(self, texto: str, *, desde: int | None = None,
                      hasta: int | None = None, top_k: int = 20,
                      max_posiciones: int = 10,
                      rastrear: list[str] | None = None) -> Workspace:
        """Readout agregado del J-space sobre las posiciones [desde, hasta).

        Por defecto lee las últimas `max_posiciones` del texto. La intensidad
        de un token es la suma de sus logits del lens cada vez que entra al
        top-25 de una celda (capa, posición).
        """
        ids = self.model.encode(texto, max_length=2048)
        seq = ids.shape[1]
        desde = 0 if desde is None else max(0, min(desde, seq - 1))
        hasta = seq if hasta is None else min(seq, hasta)
        if hasta <= desde:  # rango vacío (p. ej. prompt truncado): últimas posiciones
            desde, hasta = max(0, seq - 10), seq
        rango = list(range(desde, hasta))
        if len(rango) > max_posiciones:  # muestreo uniforme
            paso = len(rango) / max_posiciones
            rango = [rango[int(i * paso)] for i in range(max_posiciones)]
        lens_logits, _, _ = self.lens.apply(
            self.model, texto, layers=self.capas, positions=rango, max_seq_len=2048
        )

        acumulado: dict[int, float] = {}
        for logits in lens_logits.values():
            vals, idx = logits.topk(25, dim=-1)
            for fila_v, fila_i in zip(vals, idx):
                for v, i in zip(fila_v.tolist(), fila_i.tolist()):
                    acumulado[i] = acumulado.get(i, 0.0) + v

        top = []
        for tid, score in sorted(acumulado.items(), key=lambda kv: -kv[1]):
            t = self.tokenizer.decode([tid])
            if _es_significativo(t):
                top.append({"token": t.strip(), "intensidad": round(score, 1)})
            if len(top) >= top_k:
                break

        rastreados = {}
        for palabra in rastrear or []:
            tid = self.token_unico(palabra)
            if tid is not None:
                rastreados[palabra.strip()] = round(
                    max(float(l[:, tid].max()) for l in lens_logits.values()), 2
                )
        return Workspace(top=top, rastreados=rastreados, posiciones=(desde, hasta))

    # ---------- generación instrumentada ----------

    @torch.no_grad()
    def step(self, prompt: str, *, max_new_tokens: int = 200,
             rastrear: list[str] | None = None,
             leer_salida: bool = True,
             max_posiciones_salida: int = 10) -> StepResult:
        """Genera y lee el pizarrón sobre el prompt y sobre lo generado."""
        t0 = time.time()
        ids = self.tokenizer(prompt, return_tensors="pt").to(self.hf_model.device)
        n_prompt = ids.input_ids.shape[1]
        out = self.hf_model.generate(
            **ids, max_new_tokens=max_new_tokens,
            pad_token_id=self.tokenizer.eos_token_id, **self.decoding,
        )
        n_total = out.shape[1]
        salida = self.tokenizer.decode(out[0, n_prompt:], skip_special_tokens=True)
        truncada = (n_total - n_prompt) >= max_new_tokens

        ws_prompt = self.leer_pizarron(
            prompt, desde=n_prompt - 10, hasta=n_prompt, rastrear=rastrear
        )
        ws_salida = None
        if leer_salida and salida.strip():
            completo = self.tokenizer.decode(out[0], skip_special_tokens=True)
            ws_salida = self.leer_pizarron(
                completo, desde=n_prompt, hasta=None, rastrear=rastrear,
                max_posiciones=max_posiciones_salida,
            )
        return StepResult(
            prompt=prompt, salida=salida, truncada=truncada,
            segundos=round(time.time() - t0, 1),
            ws_prompt=ws_prompt, ws_salida=ws_salida,
        )
