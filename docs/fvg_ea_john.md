# El EA de FVG más nuevo de John, replicado y probado (2026-10-21)

Archivo: `EA_Nasdaq_FVG_Retest_H1M15_PartialBE.mq5` (el más reciente de FVG en Nasdaq dentro de MQL5/Experts).
Su propio encabezado dice que es una copia exacta de la v1 "que dio el resultado bueno en backtest", con parcial y
break-even añadidos pero **apagados por defecto**. Se replicó con sus parámetros por defecto ("Pass 195" de una
optimización genética en MT5), sin cambiar nada. Script: `scripts/run_fvg_john.py`. Resultado: `reports/fvg_john.json`.

## Reglas del EA

- FVG en H1 (hueco ≥ 0,2 ATR), solo a favor de la tendencia (cierre H1 frente a EMA 80 de H1). Una zona por dirección,
  caduca a las 100 velas.
- Entrada en M15: la vela toca la zona y cierra fuera a favor ("cierre con rebote"). A mercado.
- Stop: al otro lado de la zona + 0,6 ATR. Objetivo 2,5 R. Sin salida por tiempo (puede quedarse días abiertas).
- Una posición a la vez; pausa de 2 días tras 5 pérdidas seguidas. Riesgo 1 % por operación.

## Resultado (neto, con spread, deslizamiento y swap)

| Periodo | Operaciones | Por operación | t |
|---|---|---|---|
| **2021-10 a 2024-08: datos que su optimización NO vio** | 617 | **−0,08 R** | −1,25 |
| 2024-08 a 2026-08: el periodo donde se optimizó | 438 | +0,09 R | +1,12 |
| 2026-08 a 2026-10: después | 38 | −0,05 R | −0,18 |

Por año: 2021 −3,5 R, 2022 −3,0 R, 2023 **−41,7 R**, 2024 −8,9 R, 2025 +22,3 R, 2026 +25,1 R.
Compras −0,07 R por operación (pagan swap: de media 0,03 R); ventas +0,07 R. 70 % de las operaciones acaban en el stop.

## Qué significa

Es el patrón típico del **sobreajuste**: el EA funciona justo en los años donde se buscaron sus parámetros
(2024-08 a 2026-08) y pierde en los años que la optimización no vio (2021-2024), donde habría perdido unos 57 R.
Con 1 % de riesgo por operación, eso es casi −45 % de la cuenta en 2021-2024.
Los parámetros ("Pass 195") salieron de probar miles de combinaciones en MT5 sobre esos dos años, y la que mejor
salió ahí no es una ventaja real: es la que mejor encajó con ese pasado.

**No se suma a la cartera del bot.**

## Aviso de seguridad

El archivo `.mq5` tiene escrito el token del bot de Telegram en texto plano. Si alguna vez se comparte el archivo, quien
lo tenga puede usar ese bot. Conviene no compartirlo y, si ya se compartió, generar un token nuevo en @BotFather.
(No se copió el token a este proyecto.)
