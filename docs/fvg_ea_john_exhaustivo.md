# Pruebas exhaustivas del EA FVG Retest H1/M15 PartialBE de John (2026-10-21)

John lo tenía preparado para operar con 10.000 USD. Todo con datos reales de USTECm (M1, 2021-10 a 2026-10),
costes de Exness y la réplica exacta del EA (`scripts/run_fvg_john.py`). Script: `scripts/run_fvg_john_exhaustivo.py`.
Resultados: `reports/fvg_john/exhaustivo.json` y `reports/fvg_john/equity_10000.png`.

"Dentro" = 2024-08 a 2026-08, el periodo donde John optimizó los parámetros en MT5.
"Fuera" = 2021-10 a 2024-08, datos reales que la optimización no usó.

## 1. Cuenta de 10.000 USD al 1 % por operación

| Tramo | Resultado | Caída máxima | Por año |
|---|---|---|---|
| Fuera (2021-10 a 2024-08) | **−42 %** (10.000 → 5.771) | **−61 %** | 2021 −2 %, 2022 −7 %, 2023 −37 %, 2024 +1 % |
| Dentro (2024-08 a 2026-08) | +41 % (10.000 → 14.063) | −19 % | 2024 −10 %, 2025 +22 %, 2026 +28 % |
| Todo seguido (2021-2026) | **−20 %** (10.000 → 7.968) | −61 % | 2025 +22 %, 2026 +25 % |

## 2. Ajustes vecinos a "Pass 195" (uno cada vez)

De 23 ajustes cercanos, **los 23 ganan dentro y los 23 pierden fuera**. Ninguno es positivo en 2021-2024.
Que todos ganen en 2024-2026 indica que en esos años el mercado favorecía este tipo de entrada (sobre todo las ventas),
no que "Pass 195" tenga algo especial. Y fuera de ese periodo ese favor desaparece.

| Ajuste | Fuera | Dentro |
|---|---|---|
| Pass 195 (el de John) | −0,08 R | +0,09 R |
| Hueco mínimo 0,1 / 0,3 / 0,4 ATR | −0,17 / −0,01 / −0,10 R | +0,09 / +0,09 / +0,09 R |
| EMA 50 / 100 / 200 | −0,03 / −0,09 / −0,11 R | +0,12 / +0,06 / +0,06 R |
| Objetivo 1,5 / 2 / 3 / 3,5 R | −0,08 / −0,07 / −0,05 / −0,05 R | +0,06 / +0,08 / +0,08 / +0,08 R |
| Colchón del stop 0,3 / 0,9 ATR | −0,12 / −0,09 R | +0,05 / +0,07 R |
| Rechazo: solo toque / mecha 50 % | −0,08 / −0,10 R | −0,04 / −0,02 R |

## 3. Otras variantes

| Variante | Fuera | Dentro |
|---|---|---|
| Parcial + break-even encendido | −0,04 R | +0,03 R |
| Solo compras | −0,15 R | +0,02 R |
| Solo ventas | +0,02 R | +0,10 R |
| Doble spread y 1 punto de deslizamiento | −0,10 R | +0,05 R |

## 4. Comparación con entradas al azar

Mismas horas de entrada, mismo stop y mismo objetivo, pero eligiendo compra o venta tirando una moneda (300 veces).

| | Moneda al aire (media) | EA de John | El EA supera a la moneda en |
|---|---|---|---|
| Fuera | −0,086 R | −0,077 R | 58 % de los casos |
| Dentro | +0,041 R | +0,092 R | 78 % de los casos |

Fuera de la optimización, el EA es igual que tirar una moneda. Dentro, algo mejor, pero no lo bastante para descartar suerte.

## Conclusión

Con datos reales, el EA no tiene ventaja: con 10.000 USD habría perdido el 42 % en 2021-2024 y el 20 % en el
conjunto 2021-2026, con caídas de hasta el 61 %. Lo bueno de 2025-2026 coincide con el periodo en que se ajustó.
**Recomendación: no operarlo con dinero real.**
