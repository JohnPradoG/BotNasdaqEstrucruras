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
