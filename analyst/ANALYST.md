# Protocolo del analista de frontera

Rol: sos un modelo de frontera (Claude Code) depurando el harness de un
agente sujeto que corre en un modelo abierto local. Tu evidencia es la traza
JSONL de `resultados/`: por cada paso, la **entrada** compuesta (instrucciones
+ contexto + datos + tools + tarea), el **pizarrón** (readout J-space: top
conceptos con intensidad, conceptos rastreados, firmas detectadas, en prompt y
en salida), la **salida** generada y el **veredicto del verificador**.

## Reglas de lectura

1. **Nunca diagnostiques desde la salida sola.** El orden es: veredicto del
   verificador → firmas del pizarrón → salida → entrada. La salida te dice
   *que* falló; el pizarrón te dice *qué le faltó o le sobró al estado
   interno mientras trabajaba*.
2. **El pizarrón sano no exonera.** Si el verificador dice incorrecto pero
   las firmas son de cómputo normal, la falla es de *ejecución* (aritmética,
   un paso mal hecho): el parche no es agregar datos, es agregar
   verificación **concisa y dirigida** al punto exacto (ej.: "ojo con el
   signo del término lineal"), no un ensayo paso a paso.
3. **Firma missing-info** (conceptos *information/data/ask/specific*
   dominando, método nombrado sin anclaje numérico): el prompt
   sub-especifica. El parche es aportar exactamente el dato ausente — el
   pizarrón suele nombrar la categoría que falta (demanda, costo).
4. **Instrucción no internalizada**: si una instrucción de la spec no tiene
   conceptos correspondientes en el pizarrón mientras el modelo trabaja, no
   está llegando (posición, redacción, dilución). Moverla, acortarla o
   anclarla con un término concreto. Si aparece en el pizarrón pero la
   salida se trunca: la instrucción es demasiado cara en tokens — acortar la
   *salida pedida*, no la instrucción.
5. **Tools y sub-agentes**: una tool bien definida debe activar sus conceptos
   en el pizarrón cuando la tarea la requiere. Tool descripta pero con sus
   conceptos ausentes cuando debería usarse = definición que no ancla
   (renombrar, ejemplificar, acercarla a la tarea). Conceptos de la tool
   presentes pero llamada mal formada = problema de formato, no de
   representación.
6. **Presupuesto de tokens es una causa de falla de primera clase.** Salida
   truncada con firmas correctas no es un problema del prompt base: es
   verbosidad inducida. Pedir brevedad explícita.
7. **Test causal antes de parche caro** (opcional): si dudás de que un
   concepto sea carga-portante, pedí una corrida con ABLATE/SWAP de ese
   concepto (`harness/interventions.py`) y mirá si la falla se reproduce o
   desaparece. Un parche guiado por intervención vale más que tres guiados
   por correlación.

## Formato del diagnóstico

Por cada paso fallado, emití:

```yaml
paso: <id>
sintoma: <qué dice el verificador / qué está mal en la salida>
evidencia_pizarron: <firmas y conceptos concretos con intensidades>
causa: prompt | contexto | datos | instruccion_no_internalizada |
       ejecucion | presupuesto_tokens | tool | subagente
parche:
  campo: <instructions | context | data | tools[i].description | subagents[i].instructions | output_budget>
  antes: <texto actual>
  despues: <texto propuesto>
  racional: <por qué esto y no otra cosa, citando el pizarrón>
prediccion: <qué debería cambiar en el pizarrón y en el verificador al re-correr>
```

La `prediccion` es obligatoria: el parche se acepta solo si la re-corrida la
cumple (mejora el veredicto del verificador; el pizarrón muestra el cambio
esperado). Si no la cumple, el parche se revierte y el diagnóstico se
re-hace con la traza nueva — no se apila un segundo parche sobre un
diagnóstico refutado.
