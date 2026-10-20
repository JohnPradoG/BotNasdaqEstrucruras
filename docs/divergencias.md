# Divergencias RSI en cada temporalidad: la idea de John (2026-10-20)

John observa, operando, que cuando hay una divergencia el mercado reacciona a su favor. Propuso un bot que opere
divergencias en cada temporalidad, con objetivos mayores cuanto mayor es la temporalidad, y añadió que la
sobrecompra o sobreventa ayuda a confirmarlas. Script: `scripts/run_divergences.py`, con la rejilla guardada en git
antes de ejecutar. Resultados: `reports/divergencias.json` y `data/backtests/*_divergencias`.

## Cómo se tradujo la idea

- Divergencia normal (precio con mínimo más bajo y RSI con mínimo más alto, o al revés en máximos) y oculta (precio
  con mínimo más alto y RSI con mínimo más bajo, o al revés). RSI de 14 de la misma temporalidad, pivotes 3-3 y de
  5 a 60 velas entre pivotes. La señal se conoce al cerrar la vela que confirma el pivote (3 velas después del
  extremo). Antes no se puede saber, porque el pivote podría no ser un pivote.
- **Dólares a puntos:** en USTECm, 1 punto = 1 USD con 1 lote (con 0,05 lotes, 1 punto = 0,05 USD). Se usaron los
  objetivos de John en puntos: M1 15, M5 20, M15 40, H1 80 y H4 160 (el doble en cada salto, siguiendo su "y así
  sucesivamente"). También se probó un objetivo de 2 ATR.
- Stop: detrás del pivote de la divergencia, o a la misma distancia que el objetivo.
- Contexto: todas, solo a favor de la media de 50 días, o solo con RSI en sobreventa (< 30) para compras o en
  sobrecompra (> 70) para ventas.
- 120 variantes. Coste: 1,12 de spread + 0,5 por lado. Compras con swap.

## 1. ¿Reacciona el precio a favor? (sin stop y sin costes)

Proporción de casos en que el precio avanza 1 ATR a favor antes de retroceder 1 ATR. El azar es 50 %.

| TF | Divergencias (2021-26) | Normal | Oculta | Normal con RSI extremo |
|---|---|---|---|---|
| M1 | 68.277 | 50,5 % | 49,5 % | 51,4 % |
| M5 | 13.869 | 51,4 % | 48,9 % | 48,1 % |
| M15 | 4.783 | 48,7 % | 50,9 % | 47,6 % |
| H1 | 1.283 | 47,1 % | 48,1 % | 46,2 % |
| H4 | 439 | 50,7 % | 53,3 % | 56,6 % (68 casos) |

Movimiento medio a favor tras 20 velas: entre −0,20 y +0,16 ATR según el caso, sin ningún patrón estable. Ninguno es
significativo a favor; los pocos significativos son en contra. **El precio no reacciona a favor de la divergencia más que al azar.**
Las divergencias ocultas casi nunca coinciden con RSI extremo (de 1 a 104 casos), así que ese filtro solo se puede
medir en las normales, y en ellas no mejora nada.

## 2. Operándolas con los objetivos de John (stop detrás del pivote)

| TF | Casos 2021-23 | Neto 2021-23 | Neto 2024 | Neto 2025-26 | Bruto 2025-26 |
|---|---|---|---|---|---|
| M1 normal | 14.400 | −0,24 R | −0,26 R | −0,18 R | +0,02 R |
| M1 oculta | 14.103 | −0,31 R | −0,32 R | −0,21 R | +0,02 R |
| M5 normal | 2.839 | −0,13 R | −0,16 R | −0,09 R | +0,01 R |
| M5 oculta | 2.905 | −0,19 R | −0,16 R | −0,13 R | −0,01 R |
| M15 normal | 961 | −0,06 R | −0,07 R | −0,11 R | −0,01 R |
| M15 oculta | 1.023 | −0,10 R | −0,19 R | −0,04 R | +0,03 R |
| H1 normal | 299 | −0,10 R | −0,17 R | −0,10 R | −0,07 R |
| H1 oculta | 247 | −0,06 R | −0,04 R | −0,04 R | +0,01 R |
| H4 normal | 95 | −0,03 R | −0,20 R | −0,15 R | −0,13 R |
| H4 oculta | 99 | +0,06 R | +0,04 R | −0,13 R | −0,11 R |

**Ninguna de las 120 variantes pasa el examen.** La mejor en 2021-23 (H4 oculta, objetivo de 160 puntos y stop
simétrico) da +0,15 R con t = 1,54, y en 2025-26 da −0,09 R. En M1 y M5 el coste se come todo: con stops tan cortos,
los 2,12 puntos de coste equivalen a 0,2-0,3 R por operación.

## Por qué John ve que "funcionan"

Esto es muy común y no es culpa de John. Al mirar el gráfico se recuerdan las divergencias que funcionaron, y las que
fallaron se reinterpretan ("no era una divergencia de verdad", "faltaba confirmación"). Además, en el gráfico la
divergencia se ve cuando el pivote ya está formado, pero en tiempo real se conoce 3 velas después, cuando parte del
movimiento ya pasó. El bot cuenta todas, también las que fallan, y solo con la información que había en ese momento.

## Qué podría probarse todavía

- Si John tiene su propia definición (otro RSI, otra distancia entre pivotes, otra confirmación, como una vela de
  giro o una ruptura de línea), se puede programar tal cual y medirla igual.
- Lo más útil sería que John apunte en la demo, en el momento, cada divergencia que operaría y por qué. Así se mide
  su criterio real, sin memoria selectiva.

## Actualización: ¿y si se opera 1:1, 1:1,5, 1:2 o 1:3? (`scripts/run_rr.py`, `reports/rr.json`)

John propuso elegir la relación riesgo/beneficio con el backtest. Se probaron las cuatro en cada temporalidad, con el
stop en el pivote o a 1 ATR: 80 variantes de divergencias, más la ruptura de apertura como referencia.
**Ninguna pasa el examen.** Al alargar el objetivo, el acierto baja casi en la misma proporción, así que la
expectativa antes de costes sigue cerca de 0. Ejemplo, M15 divergencia oculta con stop en el pivote, 2021-23:

| Relación | Acierto necesario sin costes | Acierto real | Bruto | Neto |
|---|---|---|---|---|
| 1:1 | 50 % | 45 % | +0,03 R | −0,08 R |
| 1:1,5 | 40 % | 35 % | +0,02 R | −0,09 R |
| 1:2 | 33 % | 28 % | +0,03 R | −0,08 R |
| 1:3 | 25 % | 18 % | +0,02 R | −0,10 R |

(El acierto real queda por debajo del necesario, pero el bruto no es tan malo porque algunas operaciones cierran por
tiempo, ni en el objetivo ni en el stop.) En todas las temporalidades, el bruto de las divergencias está entre −0,15 y
+0,20 R, sin repetirse de un periodo a otro, y el neto es negativo en casi todas. La única familia que se mantiene
positiva con cualquier relación es la ruptura del rango de apertura de NY: +0,05 a +0,19 R en los tres periodos.
