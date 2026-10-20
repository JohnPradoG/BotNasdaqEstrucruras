# Búsqueda de una estrategia que funcione (2026-10-20)

John preguntó qué más se podía hacer para que el bot funcione, y pidió ir más allá de las estructuras: ideas
cuantitativas clásicas y métodos avanzados (machine learning, modelos de régimen). Este documento resume las tres
rondas. Todo sale de ejecuciones reales sobre USTECm M1 de 2021-10-27 a 2026-10-20.

## Cómo se hizo el examen (igual para todo)

- Cada ronda tiene su rejilla y su regla de selección **escritas y guardadas en git antes de ejecutarla**
  (`scripts/run_ideas.py`, `scripts/run_quant.py`, `scripts/run_ml.py`).
- Coste: spread actual de Exness 1,12 puntos + 0,5 puntos de deslizamiento por lado. Las compras que pasan la noche
  pagan el swap real: −6,555 puntos por noche y lote unidad, triple el viernes. Las ventas no pagan swap.
- Periodos: desarrollo 2021-11 a 2023, validación 2024. Para elegir, una variante tiene que ganar en desarrollo con
  t ≥ 2 **y** en validación con t ≥ 1. El t agrupa por día (las operaciones del mismo día no son independientes).
- 2025-2026 se informa solo como diagnóstico, porque ya se miró en pruebas anteriores. Nunca se usó para elegir.
- Sin mirar el futuro: las señales solo usan velas cerradas y la entrada es en la apertura de la vela siguiente. El
  machine learning se reentrena cada mes solo con datos cuyo resultado ya se conocía.
- Se probaron **265 variantes** en total. Por azar, con esta regla saldría aprobada alrededor de 1. Con la
  corrección de Bonferroni haría falta t ≥ 3,56 para estar seguros.

## Resultado general

**Ninguna de las 265 variantes pasa la regla. El bot sigue en NO OPERAR.** Lo avanzado (machine learning y HMM)
salió peor que lo simple. Hay una sola familia con una señal pequeña pero constante: la ruptura del rango de los
primeros 15 minutos de Nueva York. No llega al umbral, así que no está demostrada. Es la única que merece una prueba
en demo.

| Ronda | Variantes | Positivas en desarrollo | Positivas en validación | Positivas en los 3 periodos | Aprobadas |
|---|---|---|---|---|---|
| 1. Estructuras + apertura NY | 164 | 60 | 58 | 16 | 0 |
| 2. Cuantitativas clásicas | 73 | 38 | 35 | 19 | 0 |
| 3. Machine learning y HMM | 28 | 6 | 19 | 3 | 0 |

## Ronda 1: las 5 ideas sobre estructuras (resultado en R, neto de costes)

| Idea | Qué se probó | Resultado |
|---|---|---|
| 1. Orden limitada en el retesteo | Límite en el nivel roto tras un BOS o CHOCH, 48 variantes | **Peor que entrar a mercado.** 0 de 48 positivas en desarrollo, incluso antes de costes (−0,04 R bruto). Se llena el 82 % de las veces, y justo cuando el precio atraviesa el nivel y sigue en contra |
| 2. Sesgo de H4/D1 | Señales A/B/C solo a favor de la media de 50 días, de la tendencia D1 o solo compras | 10 de 36 positivas en desarrollo; ninguna se repite en validación con fuerza |
| 3. Memoria kNN como filtro | Operar solo si los 50 casos parecidos dan cota inferior > 0 o media > 0,05 R | Deja muy pocas operaciones y cambia de signo entre periodos (ejemplo: +0,37 R en desarrollo, −0,34 R en validación) |
| 4. Horizonte largo (diario) | Estructuras en velas diarias, objetivo 2-3 R, hasta 10 días, con swap | Muy pocas señales (6 a 30 en desarrollo): no se puede evaluar |
| 5. Apertura de Nueva York | a) estructuras solo de 9:30 a 11:00 NY | Negativas en su mayoría |
| | b) **ruptura del rango de apertura (ORB)** | **28 de 32 positivas en desarrollo y 32 de 32 en validación.** La mejor tiene t = 1,85 en desarrollo: no llega a 2 |

### La única pista: ruptura del rango de 15 minutos con la tendencia diaria

Regla: rango de 9:30 a 9:45 NY; la primera vela M5 que cierra fuera del rango antes de las 11:30 da la señal,
solo en la dirección de la media de 50 días; entrada a mercado, stop al otro lado del rango, salida a las 15:57 NY.

| Periodo | Operaciones | Neto por operación | t | Bruto |
|---|---|---|---|---|
| Desarrollo 2022-23 | 246 | +0,16 R | 1,78 | +0,19 R |
| Validación 2024 | 115 | +0,20 R | 1,49 | +0,23 R |
| 2025-26 (diagnóstico) | 222 | +0,14 R | 1,79 | +0,16 R |

Por año: +0,20 R (2022), +0,12 R (2023), +0,20 R (2024), +0,19 R (2025), +0,07 R (2026). Acierta el 49 %. El coste
solo pesa 0,02 R porque el stop es grande. Con el coste doble sigue en +0,14 R. Peor racha: −21,5 R. Las ventas
(+0,30 R) rinden más que las compras (+0,09 R).

**Por qué no basta:** no pasó la regla (t = 1,78 < 2 en desarrollo) y es la mejor de 265 pruebas, así que parte del
resultado puede ser suerte. Que salga positiva todos los años es una buena señal, y además la ruptura del rango de
apertura es un efecto conocido en los estudios sobre el Nasdaq. Pero no está demostrado.

## Ronda 2: ideas cuantitativas clásicas (resultado en puntos básicos del precio, neto)

| Familia | Qué se probó | Resultado |
|---|---|---|
| Tendencia diaria | Medias de 20-200 días, canales de Donchian, momento de 20-120 días | Ninguna con t > 1,2 en desarrollo |
| Tendencia horaria | Medias de 20-100 horas, 24 h o solo sesión NY | Positivas en un periodo y negativas en otro |
| Reversión | RSI(2) de Connors; ir contra los movimientos horarios grandes | **Ir contra el movimiento pierde en los tres periodos.** Ir a favor gana un poco (t < 1,6) |
| Estacionalidad | Noche, sesión, hora del día, día de la semana, cambio de mes | Ninguna hora ni día pasa en desarrollo después de costes |
| Régimen de volatilidad | Las reglas anteriores solo con volatilidad alta o baja | No mejora de forma estable |
| Gap de apertura | Ir contra el gap o a favor, salir a las 10:30 o a las 16:00 | Cambia de signo entre periodos |

**Un dato importante: el swap.** Comprar y mantener ganó +2,4 pb al día antes de costes en desarrollo, pero el swap
de Exness (−6,555 puntos por noche, triple el viernes) se lleva unos 6,8 pb al día y deja −4,4 pb. El swap de compra
cuesta entre un 8 % y un 19 % al año según el precio del índice. **Mantener compras varios días en este CFD sale
muy caro.** Por eso las estrategias de tendencia diaria no salen rentables aquí, aunque el índice suba.

## Ronda 3: machine learning y modelos de régimen

| Modelo | Resultado |
|---|---|
| Gradient boosting en H1 (18 características, incluidas las estructuras H1 y H4 del bot) | Negativo en desarrollo en las 8 variantes; cerca de 0 en validación |
| Regresión logística en H1 (referencia simple) | Igual de mala |
| Gradient boosting en D1 | −19 pb por operación en desarrollo; positivo en validación: inestable |
| HMM de 2 y 3 estados (régimen alcista/bajista) | t < 0,7 en todos los periodos |

**El machine learning no encontró nada que las reglas simples no encontraran.** Con datos de un solo índice y
5 años, los modelos más flexibles aprenden ruido.

**Sobre lo "cuántico":** no existe hoy ninguna ventaja demostrada de la computación cuántica para predecir precios.
Los métodos "inspirados en lo cuántico" (por ejemplo, el recocido simulado) sirven para buscar parámetros, y buscar
más sobre el mismo histórico es justo lo que produce estrategias que brillan en el pasado y fallan después. No se
incluyeron por eso.

## Un fallo encontrado y corregido

Hasta junio de 2023, el símbolo dejaba de cotizar a las 15:59 NY y volvía a las 18:30 NY. Desde entonces, la pausa es
de 17:00 a 18:00. El cierre forzado del simulador (16:55-18:00 NY) no existía en los datos antiguos, así que algunas
operaciones cruzaban la pausa sin cerrarse y sin pagar swap: el 8,8 % en H4+H1+M15 y el 1,8 % en H1+M15+M5, antes de
2023-07. Esas operaciones salían mejor (+0,33 R frente a −0,09 R). Es decir, el fallo **mejoraba** un poco los
resultados antiguos. Corregirlo no cambia la conclusión de NO OPERAR. En los scripts nuevos, el cierre forzado es de
15:57 a 18:30 NY en todos los años.

## Qué recomiendo

1. **No operar con dinero real.** Nada está demostrado.
2. **Probar en la demo, solo en observación, la ruptura del rango de 15 minutos** con la regla exacta de arriba,
   congelada desde hoy. Es el único periodo final realmente nuevo que tenemos.
3. **Ser realista con el tiempo:** con +0,15 R por operación y la variabilidad medida (1,3 R), hacen falta unas
   300 operaciones para confirmarlo (t ≥ 2). Son unas 10 al mes, así que serían unos 2,5 años de demo. Si en 100
   operaciones va por debajo de 0 R, se descarta.
4. **Tamaño de la cuenta:** el stop de esta regla es grande (mediana de 130 puntos en 2025-26). Con el lote mínimo
   de 0,05, cada operación arriesga unos 6,5 USD, el 1,2 % de los 543,93 USD de la demo. Para respetar el 0,25 % por
   operación haría falta una cuenta de unos 2.600 USD. La demo puede registrar las señales igualmente.
5. Si John quiere seguir buscando, lo que más puede cambiar el resultado no es otro modelo, sino **otros datos**:
   ticks reales (para simular bien las órdenes limitadas), otros índices (S&P 500, Dow) para comprobar si la
   ruptura de apertura se repite, y un bróker o producto con menos swap si se quiere mantener posiciones.

## Archivos

- Resultados: `reports/ideas.json`, `reports/quant.json`, `reports/ml.json`, y `data/backtests/*_ideas`,
  `*_quant`, `*_ml` (tabla completa en `variantes.csv`).
- Scripts: `scripts/run_ideas.py`, `scripts/run_quant.py`, `scripts/run_ml.py`.
- Repetir: `python scripts/run_ideas.py` (unos 25 minutos), `python scripts/run_quant.py` (1 minuto),
  `python scripts/run_ml.py` (unos 5 minutos). Requieren `data/processed/USTECm_M1.parquet` y los
  `episodes_*.parquet`, y además `scikit-learn` y `hmmlearn` para el tercero.
