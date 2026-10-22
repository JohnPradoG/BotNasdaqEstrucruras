# Backtest profundo de la cartera de apertura y unión con el bot (2026-10-20)

John pidió un backtest a fondo de las tres estrategias de apertura de Nueva York (ORB 15 min, ORB 5 min y
"noise area") y meterlas en el bot. Las reglas se congelaron antes; aquí no se eligió ni se ajustó nada.
Script: `scripts/run_profundo.py`. Datos: `reports/profundo/profundo.json`. Gráfico: `reports/profundo/equity_cartera_10000.png`.

**Un cambio obligatorio:** el bot exige un stop en el bróker en cada operación. La "noise area" original no tiene
stop fijo (sale solo en las revisiones de cada media hora), así que se le puso un stop de protección a 2 medias bandas.
Con ese stop resulta algo más estable que sin él (t 1,1 frente a 0,9 en 2021-23), aunque gana algo menos por operación.

## 1. Resultado por estrategia (neto, por operación)

| Estrategia | Ops/año | 2021-23 | 2024 | 2025-26 | Total 2021-26 |
|---|---|---|---|---|---|
| ORB 15 min (a favor de la media 50) | ~120 | +0,16 R (t 1,8) | +0,20 R (t 1,5) | +0,14 R (t 1,8) | +93 R |
| ORB 5 min | ~250 | +0,10 R (t 0,9) | +0,07 R (t 0,5) | +0,09 R (t 0,8) | +116 R |
| Noise area (stop 2 bandas) | ~205 | +0,02 R (t 1,1) | +0,02 R (t 0,7) | +0,02 R (t 0,7) | +22 R |
| **Las tres juntas** | ~570 | +0,08 R (t 1,5) | +0,08 R (t 1,0) | +0,07 R (t 1,3) | **+231 R** |

## 2. ¿Aguanta costes más altos?

| Escenario | ORB 15 | ORB 5 | Noise | Cartera |
|---|---|---|---|---|
| Base (spread 1,12 + 0,5 por lado) | +0,16 R | +0,09 R | +0,02 R | +0,081 R |
| Spread x1,5 | +0,15 R | +0,08 R | +0,02 R | +0,073 R |
| Spread x2 | +0,14 R | +0,07 R | +0,02 R | +0,065 R |
| Deslizamiento 1 punto por lado | +0,15 R | +0,07 R | +0,02 R | +0,066 R |
| Peor caso (spread x2 y deslizamiento 1) | +0,13 R | +0,04 R | +0,01 R | +0,047 R |

Sigue positiva incluso en el peor caso. El ORB 15 es el más resistente; el ORB 5 es el más sensible al coste.

## 3. Por año, día y volatilidad (cartera)

- **Por año:** 2022 +77 R, 2023 +29 R, 2024 +46 R, 2025 +87 R, **2026 −12 R** (hasta octubre). El ORB 15 sigue positivo
  en 2026 (+7 R); el ORB 5 es el que pierde este año (−19 R).
- **Por día:** jueves (+101 R) y viernes (+87 R) son los mejores; los lunes pierden (−16 R). No se filtra por día:
  sería elegir mirando el pasado, y casi seguro es ruido.
- **Por volatilidad previa:** con volatilidad media gana más (+0,19 R), con baja +0,08 R, y con volatilidad alta
  queda en 0 (sobre todo por el ORB 5). Es una pista para el futuro, no una regla: habría que confirmarla con datos nuevos.
- **Compras y ventas:** las dos ganan (ventas +0,10 R, compras +0,06 R).
- Correlación diaria entre las tres: 0,26 a 0,31. Juntarlas reduce los altibajos.

## 4. Cartera con el motor de riesgo del bot (lotes reales de USTECm)

0,25 % del equity por operación, como máximo 3 posiciones a la vez (una por estrategia), stop siempre en el bróker,
lote mínimo 0,05 y 1 USD por punto y lote.

| Cuenta inicial | Rentabilidad anual | Caída máxima | Meses positivos | Peor mes | Operaciones no abiertas por lote mínimo |
|---|---|---|---|---|---|
| 10.000 USD | **+11,4 %** | **−13,8 %** | 57 % | −4,0 % | 26 de 2.846 |
| 544 USD | +1,4 % | −6,4 % | 39 % | −2,2 % | 2.578 de 2.846 |

Con 10.000 USD, por año: 2022 +19,7 %, 2023 +6,9 %, 2024 +11,4 %, 2025 +23,2 %, 2026 −3,1 %.
El límite de pérdida diaria (1 % o 3 %) nunca llegó a actuar: con tres operaciones de 0,25 %, lo peor posible en un día
es cerca de −0,8 %. Por eso se deja en 1 %; subirlo a 3 % no cambia nada y quita una protección.

**Con 544 USD no funciona:** el lote mínimo (0,05) arriesga más del 0,25 % en casi todas las operaciones, así que el
bot no las abre. Cuenta necesaria para respetar el 0,25 % con 0,05 lotes (stops típicos de 2025-26):
ORB 5 ≈ 1.200-2.300 USD, ORB 15 ≈ 2.600-4.900 USD, noise ≈ 6.800-12.300 USD (su stop de protección es amplio).

**La peor caída es la actual:** de marzo a septiembre de 2026 la cartera cayó −13,8 % y aún no ha recuperado el máximo.

## 5. Monte Carlo (10.000 años simulados con días reales remezclados)

| | Peor 5 % | 25 % | Mediana | 75 % | Mejor 5 % |
|---|---|---|---|---|---|
| Rentabilidad en un año | −6,0 % | +3,2 % | +10,6 % | +18,5 % | +31,8 % |

- Probabilidad de terminar un año en pérdida: **16 %**.
- Caída máxima dentro del año: mediana −7,3 %; en el peor 5 % de los años, −13,6 %. Uno de cada cinco años
  tendría una caída mayor del 10 %.
- Esto supone que el futuro se parece a 2021-2026. Si la ventaja era suerte, todo esto es optimista.

## 6. Unión con el bot

- `src/nsmb/strategies/opening.py`: las tres estrategias como módulos del bot. Usan solo velas cerradas y no
  operan los festivos de la bolsa de EE. UU.
- **Mismas señales que el backtest:** en 2025-01 a 2025-06 el módulo da las 278 entradas del backtest (58 ORB 15,
  122 ORB 5 y 98 noise), con la misma hora y dirección (`scripts/check_opening_parity.py`). Las 2 de más eran del
  19 de junio (festivo), y ahora se saltan.
- `src/nsmb/execution/opening_loop.py` y `scripts/run_demo_opening.py`: modo demo. **Por defecto solo observa**:
  registra lo que haría en `logs/apertura_AAAAMMDD.jsonl`, sin enviar órdenes. Con `--allow-orders` opera solo en
  cuenta DEMO. Una posición por estrategia, stop en el bróker, cierre de todo a las 15:57 NY, y no ejecuta señales
  viejas si se arranca tarde.
- Riesgo: `config/risk.yaml` pasa de 1 a 3 posiciones (una por estrategia). El código no admite más de 3, ni que el
  riesgo total abierto supere el 1 %. La pérdida diaria sigue en 1 %. La operativa real sigue bloqueada.
- Tests: 64 pasan, entre ellos sin anticipación (las señales con datos cortados son las mismas que con datos
  completos), máximo 3 posiciones, cierre a las 15:57 y nada enviado en modo observación.

## Conclusión honesta

Es el mejor candidato del proyecto: positivo en todos los periodos, resistente al doble de costes, y con tres
estrategias que se complementan. Pero **todavía no está probado** (t entre 1 y 1,5, hace falta 2), 2026 va en pérdida,
y con la cuenta actual de 544 USD no se puede operar con el riesgo previsto. El siguiente paso sigue siendo observarlo
en la demo unos meses.

Arranque en observación (cuando John quiera): `python scripts/run_demo_opening.py`. Para detenerlo: Ctrl+C, o crear
el archivo `logs/STOP`.
