# jlens-harness

Sistema agéntico para **depurar y mejorar sistemas de agentes mirando adentro
del modelo**: usar el [Jacobian lens](https://github.com/anthropics/jacobian-lens)
para inspeccionar la tríada *entrada → espacio de trabajo interno → salida* de
un agente, detectar fallas de instrucciones (prompt), contexto, datos, tools y
sub-agentes, y dejar que un modelo de frontera (Claude Code) diagnostique y
parchee el harness del agente en un loop de mejora.

Basado en el experimento "Debugging prompts by looking inside the model"
(pricing v1→v3b sobre el demo de Neuronpedia) y en una réplica local
(jlens + modelos abiertos en esta máquina).

## La idea

> Una salida débil suele ser síntoma de un prompt débil, no de un modelo
> débil. Si podemos leer el espacio de trabajo interno del modelo junto a su
> salida, podemos señalar qué le falta al prompt — mejor que mirando solo la
> salida.

El hallazgo validado en el experimento original, que este harness codifica:

1. **La firma de "falta información"** (v1): el pizarrón se llena de
   conceptos genéricos + *information, data, ask, specific* → el prompt
   sub-especifica la tarea.
2. **La firma de "entró en cómputo"** (v2): dígitos y conceptos del método
   (*quadratic, optimization*) → el modelo tiene con qué trabajar. **Pero el
   pizarrón sano no garantiza salida correcta**: los errores de ejecución
   (una multiplicación mal hecha) son invisibles en el readout semántico.
3. **La firma de "instrucción internalizada"** (v3/v3b): pedir verificación
   hace aparecer *verify, algebra, equation* en el pizarrón; pedirla
   **concisa y dirigida** ("ojo con el signo") funciona; pedirla verbosa
   muere en el presupuesto de tokens.

Por eso el loop ganador es **lens (arregla la entrada) + verificación de
salida (caza el error de ejecución)** — los dos, nunca uno solo.

## Arquitectura

```
        ┌──────────────────────────────────────────────────────┐
        │  AGENTE SUJETO (modelo abierto local, inspeccionable) │
        │  spec: instrucciones + contexto + datos + tools       │
        │        + sub-agentes                                  │
        └───────────────┬──────────────────────────────────────┘
                        │  Runtime instrumentado (harness/)
                        ▼
          traza por paso: { entrada, pizarrón (J-space),
                            salida, tools llamadas, firmas }
                        │
                        ▼
        ┌──────────────────────────────────────────────────────┐
        │  ANALISTA DE FRONTERA (Claude Code)                   │
        │  lee la traza con el protocolo analyst/ANALYST.md,    │
        │  diagnostica (¿qué concepto falta? ¿qué instrucción   │
        │  no se internalizó? ¿la tool se representa?) y emite  │
        │  un PARCHE sobre la spec del agente                   │
        └───────────────┬──────────────────────────────────────┘
                        │  re-correr la suite, comparar
                        ▼
              mejora medida (salida verificada + pizarrón)
```

- **Agente sujeto**: corre en un modelo abierto local cuyo interior *sí*
  podemos leer (Qwen3.5-4B + lens `n1000`, validado en esta máquina a
  ~20-55 s por corrida en MPS). El J-space de los modelos de producción no
  está expuesto por API, así que el sujeto es local por necesidad — y eso
  convierte a esta carpeta en un banco de pruebas, no en una feature.
- **Analista**: Claude Code (modelo de frontera). No adivina: lee la traza
  completa (entrada + pizarrón + salida + verificación) y sigue
  `analyst/ANALYST.md`.
- **Intervenciones causales**: STEER / ABLATE / SWAP sobre el residual
  stream (generalización de un experimento interno de J-space) para probar
  si un concepto es carga-portante antes de tocar el prompt.

## Layout

```
harness/
  runtime.py        # carga modelo+lens, generación instrumentada, lectura del pizarrón
  interventions.py  # STEER / ABLATE / SWAP en el residual stream
  agentspec.py      # spec del agente: instrucciones, contexto, tools, sub-agentes
  signatures.py     # detectores de firmas sobre el readout
  trace.py          # trazas JSONL por paso
analyst/
  ANALYST.md        # protocolo del analista de frontera (diagnóstico → parche)
tasks/
  pricing.json      # la suite del artículo (v1→v3b) con verificador numérico
experiments/
  pricing_demo.py   # corrida end-to-end de la suite sobre el agente sujeto
resultados/         # trazas y análisis de cada corrida
```

## Quickstart

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ../jacobian-lens torch numpy huggingface_hub "transformers>=5.5" accelerate
.venv/bin/python experiments/pricing_demo.py          # corre v1→v3b y guarda la traza
# después: pedirle a Claude Code que analice resultados/pricing/*.jsonl con analyst/ANALYST.md
```

## Roadmap

- [x] Runtime instrumentado sobre modelo local + lens pre-ajustado
- [x] Firmas: missing-info / cómputo / verificación / signos
- [x] Suite pricing (v1→v3b) como validación del harness — replicó el
      artículo en 6 iteraciones de diagnóstico→parche→re-corrida, terminando
      en la respuesta correcta al agregar la tool `calc`
      (ver `resultados/pricing/INFORME.md`)
- [x] Tools con loop de ejecución (`TOOL: calc(...)`) y firma "tool
      representada" observada en el pizarrón
- [x] Ciclo analista manual demostrado (Claude Code leyendo trazas con
      `analyst/ANALYST.md`, parches con predicción falsable)
- [ ] Loop automático analista→parche→re-corrida (Claude Code como analista vía Agent tool)
- [ ] Firma negativa: "tool ignorada" (la tarea la requiere y sus conceptos no aparecen)
- [ ] Trazas multi-paso: memoria entre pasos, sub-agentes
- [ ] Intervenciones como test causal previo al parche (¿ablacionar X reproduce la falla?)
- [ ] Auto-mejora: el propio sistema propone parches a su harness y los valida
```
