# Cruce de EMAs: ¿en qué temporalidad funciona mejor? (2026-10-21)

Idea de John. Reglas y rejilla guardadas en git antes de ejecutar (`scripts/run_ema_cross.py`).
Datos reales de USTECm M1 (2021-11 a 2026-10), costes de Exness (spread 1,12 + 0,5 por lado, swap de compras).
Resultado completo: `reports/ema_cross/ema_cross.json`.

## Reglas

- Compra cuando la EMA rápida cruza por encima de la lenta al cierre de la vela; venta al revés. Entrada a mercado.
- Stop 1,5 × ATR14 de esa temporalidad.
- Dos salidas: en el cruce contrario, o con objetivo 2 R (o el cruce contrario si llega antes).
- 90 variantes: M5, M15, H1, H4, D1 × EMAs 9/21, 20/50, 50/200 × 2 salidas × {ambas, solo compras, solo ventas}.
- Aprobada si en 2021-23 tiene al menos 100 operaciones y t ≥ 2, y en 2024 es positiva con t ≥ 1.

## Por temporalidad (media de sus 18 variantes, R neto por operación)

| Temporalidad | 2021-23 | 2024 | 2025-26 | Bruto (sin costes) 2025-26 |
|---|---|---|---|---|
| M5 | −0,15 | −0,09 | −0,05 | +0,05 |
| M15 | −0,01 | 0,00 | −0,06 | 0,00 |
| **H1** | **+0,17** | **+0,06** | **−0,02** | +0,04 |
| H4 | −0,16 | +0,01 | −0,22 | −0,15 |
| D1 | −0,15 | −0,18 | −0,22 | −0,04 |

**H1 es la mejor temporalidad**, pero su ventaja se va apagando y en 2025-26 queda en cero.
En M5 y M15 los costes se comen todo (hay muchísimas operaciones con stops pequeños).
H4 y D1 dan muy pocas operaciones y no ganan.

## Mejores variantes en H1

| Variante | 2021-23 | 2024 | 2025-26 |
|---|---|---|---|
| EMA 20/50, objetivo 2 R, ambas | +0,15 R (t 1,55; 231 ops) | +0,03 R | +0,04 R |
| EMA 9/21, salida en cruce, ambas | +0,07 R (t 0,73; 485 ops) | +0,11 R | +0,03 R |
| EMA 50/200, objetivo 2 R, solo compras | +0,54 R (t 2,24; solo 36 ops) | −0,19 R | +0,06 R |

- Aprobadas: **0 de 90**. Positivas en 2021-23 y 2024 a la vez: 16 de 90 (por azar se esperarían unas 20).
- Con 90 pruebas haría falta t ≈ 3,3 para fiarse; la mejor llega a 1,55 con suficientes operaciones.

## Conclusión

El cruce de EMAs no tiene ventaja clara después de costes en ninguna temporalidad. H1 es la menos mala
(+0,03 a +0,04 R en 2025-26, casi cero). **No se implementa en el bot con dinero.** Si John quiere, la variante
H1 EMA 20/50 con objetivo 2 R puede observarse en demo como un módulo más, sin órdenes.

## En el bot (2026-10-21, pedido por John)

John pidió meter la de H1 al bot. Entró la variante **EMA 20/50 en H1, stop 1,5 ATR, objetivo 2 R, compras y ventas**:

- Reglas: `src/nsmb/strategies/ema_cross.py`. Mismo bucle que la cartera de apertura (`execution/opening_loop.py`),
  pero sin cierre de las 15:57 (puede quedarse noches) y con el stop medido desde el precio real de entrada.
  En el cruce contrario cierra y abre la contraria. No abre con spread > 8 puntos.
- Paridad: con las últimas 100.000 velas M1 (como en vivo), el módulo da las **108 de 108** entradas del backtest de
  2025, con la misma distancia de stop (`scripts/check_ema_parity.py`).
- Pruebas: `tests/test_ema_cross.py` (cruces, sin mirar el futuro, vela H1 abierta no se usa, giro en el cruce,
  stop y objetivo, spread alto, modo observación). 73 pruebas en total, todas bien.
- Arranque: `python scripts/run_demo_ema.py` (observa, no envía órdenes). `--allow-orders` solo opera en cuenta DEMO
  (si no es demo, el bot no arranca). Número mágico propio (magic + 2), registro `logs/ema_h1_AAAAMMDD.jsonl`,
  para detenerlo: Ctrl+C o crear `logs/STOP_EMA`. Puede ir a la vez que la cartera de apertura (proceso aparte).
- Riesgo: 0,25 % por operación. Con lote mínimo 0,05 y stop de 1,5 ATR H1 (mediana 115 puntos en 2025-26; la mitad entre 80 y 157), arriesgar
  0,25 % pide unos 2.300 USD (1.600-3.100 según el día); con menos, el bot no opera ("lote_minimo_supera_riesgo").

**No está activada.** Como no pasó la prueba estadística, lo recomendado es dejarla en observación unos meses.

## Junto con la cartera de apertura (2026-10-21)

John pidió incluir el cruce de EMAs junto a las estrategias de apertura. Arranque único: `python scripts/run_demo_bot.py`
(orb15, orb5, noise y ema2050h1 en un solo bucle, `src/nsmb/strategies/portfolio.py`).
- Observa por defecto; `--allow-orders` solo en cuenta DEMO.
- Un solo número mágico (magic + 3) y un solo control de riesgo para todas: máx. 3 posiciones abiertas a la vez,
  0,25 % por operación (≤ 1 % abierto), pérdida diaria 1 %. Si ya hay 3 abiertas, la 4.ª señal se registra y no se abre.
- A las 15:57 NY se cierran solo las de apertura; la de EMAs puede seguir abierta de noche.
- Registro: `logs/bot_AAAAMMDD.jsonl` (cada línea dice la estrategia). Parar: Ctrl+C o crear `logs/STOP_BOT`.
- Prueba: `tests/test_ema_cross.py::test_portfolio_flat_close_keeps_ema_overnight`. 74 pruebas en total, todas bien.
