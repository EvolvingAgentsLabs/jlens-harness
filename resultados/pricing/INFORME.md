# Informe del analista — suite pricing, iteraciones 1–6

Analista: Claude Code (Fable 5) siguiendo `analyst/ANALYST.md`. Sujeto:
Qwen3.5-4B + lens `n1000`, local (M4, MPS). Tarea: precio óptimo
(correcto: P\*=$47.50, G\*=$3,025). Trazas: `trace.jsonl` … `trace6.jsonl`.

## La progresión

| iter | qué cambió | resultado | qué enseñó |
|---|---|---|---|
| 1 | suite v1→v3b tal cual el artículo | 4/4 truncadas | El sujeto emite `<think>` que come el presupuesto. Pizarrón de v3b sano (`computo`) pero sin respuesta → regla 6: presupuesto, no prompt. |
| 2 | prefill `<think></think>` vacío + verificador estricto | v1 pide datos ✓; v2 corrompe datos ("108", "$34"); v3b responde números inventados | **Falla del harness descubierta**: `no_repeat_ngram_size=4` prohíbe copiar 4-gramas del prompt → el modelo no puede citar "100 unidades por mes" y deforma los datos. |
| 3 | decodificación limpia (greedy puro) | fidelidad de datos ✓; v3 muere verbosa (= artículo); v3b completa con firma `signos` 0.20 pero deslice: término lineal `+300x` | Réplica estructural del artículo completa: monotonia v1→v3b, firma de signos representada, y **límite #1 confirmado: el pizarrón sano no ve el error aritmético** — lo cazó el verificador. |
| 4 | parche quirúrgico: expandir los 4 productos por separado | término lineal ✓ (`+100x`) pero ahora `−10x²` (era `−100x²`) | El parche arregla exactamente lo que apunta y el deslice se muda. En un 4B la aritmética es la restricción vinculante: **más prompt no es el parche correcto**. |
| 5 | diagnóstico → la spec necesita una **tool** `calc` | el sujeto la usa bien (4 productos ✓) y el pizarrón del prompt muestra `calculator`/`calculation` + dígitos (computo 0.81) | Firma "**tool representada**" observada. Se quedó sin rondas (límite 4) + bug del readout con prompts >1024 tokens (arreglado). |
| 6 | 12 rondas + readout hasta 2048 | **CORRECTA: $47.50 / $3,025** ✓ | El sujeto intentó llamadas simbólicas, la tool le devolvió error, se auto-corrigió a llamadas numéricas y cerró: vértice 0.5, precio 47.5, ganancia 3025. |

## Conclusiones (las del artículo, más dos nuevas)

1. **Confirmado**: entrada + pizarrón + salida supera a salida-sola para
   diagnosticar. Cada parche fue dirigido por una firma concreta del
   pizarrón, con predicción falsable, y la calidad subió monotónicamente.
2. **Confirmado**: el lens no ve errores de ejecución (iter 3 y 4: pizarrón
   de cómputo sano, aritmética mal). El loop ganador es lens + verificador.
3. **Confirmado**: la verificación verbosa muere en el presupuesto (v3 en
   todas las iteraciones); la concisa y dirigida se internaliza (firma
   `signos` en v3b).
4. **Nuevo — el harness también es sujeto de diagnóstico**: dos de las seis
   fallas eran del *harness*, no del modelo ni del prompt (la decodificación
   anti-bucle corrompía los datos; el readout se vaciaba con prompts largos).
   La tríada entrada/pizarrón/salida las delató igual.
5. **Nuevo — el techo del prompt existe y el pizarrón ayuda a verlo**: cuando
   parches sucesivos correctos mueven el error de lugar (iter 3→4), la
   conclusión no es "otro parche" sino "cambiar de dimensión": darle una
   tool. Con `calc`, un 4B que no sabía multiplicar con confianza resolvió
   exacto — y el pizarrón mostró la tool *representada* mientras la usaba.

## Qué sigue (roadmap del README)

- Automatizar este loop: el analista (Claude Code vía Agent tool) lee la
  traza y emite el parche YAML sin humano en el medio.
- Firma negativa de tools: tarea que *requiere* la tool + spec donde sus
  conceptos NO aparecen en el pizarrón → detectar "tool ignorada".
- Sub-agentes: misma tríada sobre specs anidadas.
- Intervenciones (STEER/ABLATE/SWAP ya implementadas en
  `harness/interventions.py`) como test causal previo al parche.
