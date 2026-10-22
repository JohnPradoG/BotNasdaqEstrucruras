# FVG con retesteo (idea de John, 2026-10-21)

John pidió revisar su estrategia de FVG con retesteo (en su MT5 tiene los EA `EA_Nasdaq_FVG_Retest`). Su código
.mq5 no estaba disponible, así que se probó una definición estándar, guardada en git antes de ejecutar
(`scripts/run_fvg.py`, resultados en `reports/fvg.json`):

- FVG: hueco entre la vela t-2 y la vela t de al menos 0,3 ATR. Se conoce al cierre de la vela t.
- Retesteo: orden limitada que espera hasta 20 velas a que el precio vuelva al hueco, en el borde o en la mitad.
- Stop al otro lado del hueco; objetivo 2 R o 3 R; con o sin filtro de media de 50 días; M5, M15 y H1. 24 variantes.

## Resultado (neto por operación)

| Hueco en | Mejor variante | 2021-23 | 2024 | 2025-26 |
|---|---|---|---|---|
| M5 | borde, 2 R | −0,27 R | −0,29 R | −0,18 R |
| M15 | borde, 3 R, media 50 | −0,12 R | −0,11 R | −0,06 R |
| H1 | borde, 3 R | −0,04 R | +0,02 R | +0,06 R |

**Ninguna de las 24 pasa; casi todas pierden.** En M5 y M15 pierde incluso antes de costes (bruto −0,01 a −0,06 R):
cuando el precio vuelve a llenar el hueco, suele seguir de largo y salta el stop. Es la misma "selección adversa" que
ya vimos con las órdenes limitadas en el retesteo de estructuras: la orden se llena justo en los casos malos.
En H1 queda cerca de cero, sin ventaja clara.

## Qué falta

Si el EA de John usa otra definición (otra temporalidad de entrada, confirmación con vela de giro, filtro de sesión,
stop distinto), hace falta su archivo `EA_Nasdaq_FVG_Retest.mq5` para programarla exactamente igual y medirla.
Normalmente está en MT5 → Archivo → Abrir carpeta de datos → MQL5 → Experts.
