# Diagnóstico del analista de frontera — pricing, iteración 1

Analista: Claude Code (Fable 5), leyendo `trace.jsonl` con `analyst/ANALYST.md`.

```yaml
paso: todas las versiones (v1..v3b)
sintoma: las 4 salidas truncadas (truncada=true); ninguna llega a una respuesta final
evidencia_pizarron: >
  En v3b el pizarrón de salida tiene la firma computo sana (0.182: math,
  optimization, calculation, profit) — la instrucción quirúrgica se
  internalizó — pero la salida es puro preámbulo <think> y muere en el
  presupuesto. Mismo patrón en v1..v3: el modelo sujeto emite un bloque de
  razonamiento antes de responder.
causa: presupuesto_tokens (verbosidad inducida por el hábito <think> del
       modelo sujeto, no por la spec)
parche:
  campo: arranque del runtime (prefill), no la spec
  antes: "Respuesta:\n"
  despues: "Respuesta:\n<think>\n\n</think>\n\n"
  racional: >
    En v2 y v3 se observa que cuando el bloque think sale vacío
    ("<think>\n\n</think>") la respuesta empieza inmediatamente. Prefijar el
    think vacío evita el preámbulo sin tocar instrucciones (regla 6 del
    protocolo: salida truncada con firmas correctas no es problema del
    prompt base).
prediccion: >
  v1 pide datos (comportamiento correcto para un prompt deficiente);
  v2..v3b llegan a una respuesta final. Si aparece un deslice aritmético
  (en v2 iter-1 ya se vio "108 unidades" donde el dato decía 100), el
  pizarrón se verá sano igual — lo caza el verificador, no el lens.
```

```yaml
paso: verificador del harness
sintoma: pide_datos=true en v2..v3b, que sí tienen los datos (falso positivo)
evidencia_pizarron: no aplica (falla del harness, no del sujeto)
causa: ejecucion (regex floja en experiments/pricing_demo.py)
parche:
  campo: verificar().pide_datos
  antes: patrones sueltos ("need", "falta", "no (me )?has")
  despues: petición explícita de datos ("necesito más datos", "please provide", ...)
  racional: el verificador es parte del loop; sus falsos positivos contaminan
    el diagnóstico igual que un pizarrón mal leído.
prediccion: pide_datos=true solo en v1.
```

Nota adicional (para iteración futura): en v2 la salida corrompió un dato de
la entrada ("venta base de 108 unidades" donde los datos dicen 100). Es la
clase de error de ejecución que el artículo predice invisible en el readout
semántico — el pizarrón de v2 se veía sano (computo 0.198). Confirma que el
loop necesita el verificador numérico además del lens.
