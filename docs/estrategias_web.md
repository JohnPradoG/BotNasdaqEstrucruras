# Estrategias de Nasdaq publicadas en la web: qué hay y qué pasa con nuestros datos (2026-10-20)

John pidió buscar en GitHub y en toda la web un bot de Nasdaq que sea rentable. Se buscó en GitHub, TradingView,
el Market de MQL5, foros de NinjaTrader y artículos académicos. Lo que tenía reglas claras se reprogramó y se probó
con nuestros datos (USTECm M1 2021-2026) y costes de Exness, con el mismo examen de siempre.
Script: `scripts/run_web.py` (rejilla guardada en git antes de ejecutar). Resultados: `reports/web.json`.

## Lo que se encontró

| Fuente | Qué es | Evidencia que publica | Valor |
|---|---|---|---|
| GitHub | Casi nada específico de Nasdaq con resultados; sobre todo librerías de backtest genéricas | Ninguna verificable | Bajo |
| Market de MQL5 (Nasdaq Momentum Trap, Nasdaq 100 Hybrid, Dip Buyer...) | Bots de pago, código cerrado | Backtests del propio vendedor (p. ej. PF 1,16, DD 12,9 %); sin historial real | Bajo: no se puede revisar ni reproducir |
| TradingView (ORB NQ, FXC ORB...) | Scripts abiertos de ruptura de apertura | Ajustados sobre el mismo pasado ("los días que mejor salieron") | Ideas, no pruebas |
| Zarattini y Aziz 2023 | ORB de 5 min en QQQ | Artículo académico; +0,13 R por operación antes de spread | Medio |
| Zarattini, Aziz y Barbon 2024 | "Noise area": momentum intradía en SPY | Artículo académico | Medio |
| Gao, Han, Li y Zhou 2018 (JFE) | La primera media hora predice la última | Revista seria, datos 1993-2013 | Medio |
| Efecto nocturno (Cooper y otros) | Casi toda la subida ocurre de noche | Artículos; con costes desaparece | Inviable aquí: el swap de compra cuesta 6,5 pts por noche |

Un aviso importante: un autor del blog de MQL5 replicó el ORB de 5 min en CFD de 5 índices (2015-2026) y concluyó
que el bruto se reproduce pero el neto queda en cero. Por eso había que probarlo con nuestros costes.

## Resultados con nuestros datos (neto, después de costes)

| Estrategia | 2021-23 | 2024 | 2025-26 | Ops/año | ¿Pasa? |
|---|---|---|---|---|---|
| ORB 5 min (artículo QQQ), ambas direcciones | +0,10 R (t 0,9) | +0,07 R (t 0,5) | +0,09 R (t 0,8) | ~250 | No (t < 2) |
| ORB 5 min, solo a favor de la media 50 | +0,02 R | −0,02 R | +0,18 R | ~125 | No |
| Noise area, revisión cada 30 min, stop en la banda | +0,04 u (t 0,9) | +0,03 u | +0,04 u | ~210 | No |
| Noise area, cada 30 min, media 50 | +0,05 u | +0,12 u | +0,04 u | ~105 | No |
| Momentum última media hora (todas las variantes) | negativo | negativo | casi siempre negativo | ~125-250 | No |

(R = riesgo inicial. "u" = media banda de ruido del día, una medida parecida al ATR.)

**Ninguna de las 14 variantes pasa el examen** (hace falta t ≥ 2 en 2021-23). Con todo lo probado hoy (579 variantes),
el listón de Bonferroni sería t ≥ 3,76.

## Lo que sí es interesante

- **El ORB de 5 min y la "noise area" dan positivo, después de costes, en los tres periodos.** Es poco por operación y
  con mucho ruido (el ORB acierta solo el 24 %, porque busca 10 R), así que estadísticamente aún no se distingue del
  azar. Pero es el mismo patrón que ya veíamos en nuestro ORB de 15 min: **lo único que se repite en el Nasdaq es el
  impulso de la apertura de Nueva York**.
- El momentum de la última media hora, que funcionaba en SPY de 1993 a 2013, en el Nasdaq de 2021-2026 va al revés.
  Es un buen ejemplo de que lo que funcionó en otro mercado u otra época no se puede dar por hecho.
- Los bots de pago no se pueden comprobar: no se ve el código y los resultados los pone el vendedor.

## Siguiente paso propuesto

Estas tres estrategias de apertura (ORB 15, ORB 5 y noise area) se parecen, así que no son tres ventajas independientes.
Lo honesto es congelarlas tal cual y medirlas juntas en la demo, solo observando, como candidatas a ser los primeros
módulos del bot de varias estrategias que quiere John. Elegir ahora la mejor combinación mirando estos mismos datos
sería repetir el error de quedarse con lo que salió bien en el pasado.
