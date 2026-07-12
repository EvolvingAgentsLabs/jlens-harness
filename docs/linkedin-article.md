# Artículo para LinkedIn (ES / EN)

---

## Versión en español

**Depurar un agente mirándole el cerebro: construí un harness que lee el espacio de trabajo interno del modelo — y el loop terminó arreglándose a sí mismo**

Hace unas semanas conté un experimento con el Jacobian Lens de Neuronpedia: en vez de depurar un prompt releyendo la salida, mirar los *conceptos que se encienden adentro del modelo* mientras trabaja, y usar eso para arreglar la entrada. Funcionó — pero era manual, sobre un demo web, clic a clic.

Esta semana lo convertí en un sistema: **jlens-harness**, un banco de pruebas agéntico donde la tríada *entrada → espacio de trabajo interno → salida* se captura automáticamente, y un modelo de frontera (Claude Code) actúa como analista que diagnostica y parchea las instrucciones, el contexto, los datos y las herramientas de un agente sujeto.

**La arquitectura es simple:**
- El *agente sujeto* corre en un modelo abierto local (Qwen3.5-4B) cuyo interior sí podemos leer, con los lenses pre-ajustados que publicó Anthropic/Neuronpedia.
- Cada paso deja una traza: el prompt compuesto desde una spec versionable, el "pizarrón" (readout J-space: los conceptos activos con su intensidad, en el prompt y en la salida), la salida, y el veredicto de un verificador.
- Detectores de *firmas* codifican los hallazgos del experimento original: "falta información", "entró en cómputo", "verificación internalizada", "atención al signo".
- El analista de frontera lee la traza con un protocolo escrito (ANALYST.md) y emite parches con **predicción falsable**: el parche se acepta solo si la re-corrida cumple lo predicho.

**Lo corrí sobre el mismo problema de pricing del artículo original (respuesta correcta: $47.50 / $3,025). Seis iteraciones:**

1. Las 4 versiones del prompt salieron truncadas: el sujeto "pensaba en voz alta" y se comía el presupuesto. El pizarrón estaba sano — regla del protocolo: presupuesto, no prompt.
2. El parche destapó algo mejor: **el harness corrompía los datos**. Mi configuración anti-repetición le prohibía al modelo copiar "100 unidades" del prompt… y escribía "108". La tríada lo delató.
3. Con decodificación limpia: réplica estructural completa del artículo. La versión concisa respondió con la firma de *signos* visible en el pizarrón… y un deslice aritmético que el lens no vio y el verificador sí. El límite #1 del artículo, confirmado.
4. Parche quirúrgico al término lineal: lo arregló — y el error se mudó al coeficiente cuadrático. Cuando parches correctos solo mueven el error de lugar, esa es la señal de techo del prompt.
5. Conclusión del analista: **cambiar de dimensión — darle una herramienta**. Agregué `calc` a la spec. El pizarrón mostró la tool *representada* (`calculator`, `calculation` + dígitos) mientras el modelo la usaba.
6. **Correcta: $47.50 / $3,025.** El sujeto hasta se auto-corrigió cuando la tool le rechazó llamadas simbólicas.

**Tres cosas que me llevo:**

1. La tríada entrada/pizarrón/salida supera a la salida sola — cada parche fue dirigido por una firma concreta, no por intuición. Y dos de las seis fallas eran *del harness*, no del modelo: el instrumento también te depura el andamiaje.
2. El pizarrón sano no exonera: los errores de ejecución son invisibles al lens. El loop ganador sigue siendo lens (arregla la entrada) + verificador (caza el error).
3. El hallazgo nuevo: cuando el prompt toca techo, el pizarrón ayuda a verlo — y el parche correcto puede ser una tool, un dato o un sub-agente, no más texto. Un 4B que no multiplicaba con confianza resolvió exacto con una calculadora, y pudimos *ver* la herramienta representada en su espacio de trabajo mientras la usaba.

Todo el código, las trazas de las 6 iteraciones y el protocolo del analista están abiertos: https://github.com/EvolvingAgentsLabs/jlens-harness

Construido con Claude Code sobre el jacobian-lens de Anthropic y los lenses públicos de Neuronpedia. Siguiente paso del roadmap: cerrar el loop sin humano — que el analista lea la traza y emita el parche solo — y la firma negativa de "tool ignorada". Si trabajás en harnesses de agentes o auto-mejora, comparemos notas.

---

## English version

**Debugging an agent by reading its mind: I built a harness that reads the model's internal workspace — and the loop ended up fixing itself**

A few weeks ago I shared an experiment with Neuronpedia's Jacobian Lens: instead of debugging a prompt by re-reading its output, look at the *concepts firing inside the model* while it works, and use that to fix the input. It worked — but it was manual, on a web demo, click by click.

This week I turned it into a system: **jlens-harness**, an agentic testbench where the *input → internal workspace → output* triad is captured automatically, and a frontier model (Claude Code) acts as the analyst that diagnoses and patches the subject agent's instructions, context, data and tools.

**The architecture is simple:**
- The *subject agent* runs on a local open model (Qwen3.5-4B) whose internals we can actually read, using the pre-fitted lenses published by Anthropic/Neuronpedia.
- Every step leaves a trace: the prompt composed from a versionable spec, the "whiteboard" (J-space readout: active concepts with intensities, over both prompt and output), the output, and a verifier's verdict.
- *Signature* detectors encode the original experiment's findings: "missing information", "entered computation", "verification internalized", "sign awareness".
- The frontier analyst reads the trace against a written protocol (ANALYST.md) and emits patches with a **falsifiable prediction**: a patch is accepted only if the re-run fulfills it.

**I ran it on the same pricing problem from the original article (correct answer: $47.50 / $3,025). Six iterations:**

1. All four prompt versions came back truncated: the subject "thought out loud" and ate its own token budget. The whiteboard was healthy — protocol rule: budget problem, not prompt problem.
2. The patch uncovered something better: **the harness itself was corrupting the data**. My anti-repetition decoding config forbade the model from copying "100 units" from the prompt… so it wrote "108". The triad exposed it.
3. With clean decoding: full structural replication of the article. The concise version answered with the *sign* signature visible on the whiteboard… and an arithmetic slip the lens couldn't see but the verifier caught. The article's limit #1, confirmed.
4. A surgical patch to the linear term fixed it — and the error moved to the quadratic coefficient. When correct patches only relocate the error, that's the signal you've hit the prompt's ceiling.
5. The analyst's conclusion: **change dimension — give it a tool**. I added `calc` to the spec. The whiteboard showed the tool *represented* (`calculator`, `calculation` + digits) while the model used it.
6. **Correct: $47.50 / $3,025.** The subject even self-corrected when the tool rejected its symbolic calls.

**Three takeaways:**

1. The input/workspace/output triad beats output-only — every patch was driven by a concrete signature, not intuition. And two of the six failures were *the harness's fault*, not the model's: the instrument debugs your scaffolding too.
2. A healthy whiteboard doesn't exonerate: execution errors are invisible to the lens. The winning loop is still lens (fix the input) + verifier (catch the slip).
3. The new finding: when the prompt hits its ceiling, the workspace helps you see it — and the right patch may be a tool, a datum, or a sub-agent, not more text. A 4B that couldn't reliably multiply solved the problem exactly with a calculator, and we could *watch* the tool being represented in its workspace as it used it.

All the code, the six iterations' traces and the analyst protocol are open: https://github.com/EvolvingAgentsLabs/jlens-harness

Built with Claude Code on top of Anthropic's jacobian-lens and Neuronpedia's public lenses. Next on the roadmap: closing the loop with no human in the middle — the analyst reading the trace and emitting the patch on its own — plus the negative "tool ignored" signature. If you work on agent harnesses or self-improving systems, let's compare notes.
