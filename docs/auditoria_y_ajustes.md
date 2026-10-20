# Auditoría del backtest y ajustes probados (2026-10-20)

John preguntó si había un error, porque estructuras que aparecen a diario no deberían perder en todas las
estrategias. Este documento resume lo que se comprobó y lo que se ajustó. Todo sale de ejecuciones reales:
`scripts/audit_backtest.py` y `scripts/run_adjustments.py` sobre USTECm M1 de 2021-10-27 a 2026-10-20.

## 1. ¿Hay algún error? No se encontró ninguno

| Comprobación | Qué se miró | Resultado |
|---|---|---|
| Entrada sin anticipación | Minutos entre el cierre de la vela de señal y la entrada | Mínimo 0, mediana 0, máximo 12 (huecos de datos). Ninguna entrada antes de tiempo |
| Dirección | Mismo stop y objetivo con la dirección invertida, sin costes | H4+H1+M15: normal +0,023 R, invertida −0,028 R. H1+M15+M5: normal +0,032 R, invertida +0,011 R. Ninguna dirección gana con claridad: no hay señales al revés |
| Zona horaria | Hora UTC con más movimiento por minuto | 13:30 UTC en julio y 14:30 UTC en enero = apertura de Nueva York. Correcto |
| Costes | Código del simulador | Spread una vez (compra al ASK y cierra al BID) + 0,5 puntos de deslizamiento por lado = 2,12 puntos por operación |
| Regla conservadora intravela | Casos en que stop y objetivo caen en la misma vela M1 | 3 de 3.000. No influye |
| Detectores tardíos | Pivotes confirmados 3 velas después (necesario para no mirar el futuro); retesteo y falsa ruptura se confirman al cierre | Correcto por diseño; probado con datos sintéticos (52 pruebas pasan) |
| Movimiento a favor tras la señal, sin stop ni costes | Media a 60 minutos, en ATR | Todas las estructuras: +0,013 ATR (t = 1,3 a 1,6). Prácticamente cero |

**Conclusión:** el sistema mide bien. Que una estructura aparezca a diario no significa que tenga ventaja: después de
la señal el precio va a favor casi lo mismo que en contra. Con stops de unos 19 puntos (M5) o 36 puntos (M15), el coste
fijo de 2,12 puntos se lleva entre 0,06 y 0,11 R por operación, y eso deja el resultado neto en negativo.

## 2. Ajustes probados (rejilla fijada antes de mirar resultados)

Para cada estrategia (A continuación, B reversión, C cambio de tendencia) se probaron 32 variantes, 96 por
combinación:

- stop con colchón de 0,10 ATR (original) o 0,50 ATR (más amplio);
- objetivo de 1, 1,5, 2 o 3 R;
- sin stop mínimo, o stop mínimo de 20 puntos (para que el coste pese poco);
- todas las sesiones, o solo Londres y Nueva York.

Para elegir una variante tenía que ganar en desarrollo (2021-2023, con t ≥ 2) **y** en validación (2024). El holdout
2025-2026 no se usó para elegir.

| Combinación | Variantes | Positivas en desarrollo | Positivas en validación | Positivas en las dos | Positivas en los tres periodos | Elegida |
|---|---|---|---|---|---|---|
| H4+H1+M15 | 96 | 25 | 11 | **0** | **0** | NO OPERAR |
| H1+M15+M5 | 96 | 0 | 0 | **0** | **0** | NO OPERAR |

La mejor variante de H4+H1+M15 (A continuación, stop 0,50 ATR, objetivo 3 R) dio +0,126 R en desarrollo (t = 1,70),
−0,018 R en validación y −0,003 R en el holdout (+0,043 R antes de costes). Es la misma historia de antes: lo que
funciona en un periodo no se repite en el siguiente. M15+M5+M1 no se repitió porque es la peor combinación (stops
muy pequeños) y ya quedó claramente negativa.

Resultados completos: `reports/ajustes_H4_H1_M15.json`, `reports/ajustes_H1_M15_M5.json` y
`data/backtests/*_ajustes/variantes.csv`.

## 3. Decisión

El bot queda en **NO OPERAR** en las tres combinaciones. La demo sigue en modo observación: registra las señales,
pero no envía órdenes. Ver `docs/limitaciones.md` para saber qué haría falta para cambiar esto.

## 4. Qué podría tener más sentido probar después (no está hecho)

- Entradas con orden limitada en el nivel del retesteo, en vez de entrar a mercado al cierre de la vela. Daría un stop
  más ajustado con el mismo coste. Requiere ticks para simularlo con honestidad.
- Usar las estructuras solo como filtro de contexto de otra fuente de ventaja (por ejemplo, el sesgo alcista de largo
  plazo del Nasdaq: comprar y mantener ganó +39 % en el holdout), no como señal de entrada por sí solas.
- Temporalidades más altas (H4/D1), donde el coste pesa todavía menos. Habrá muchas menos señales.

Cualquiera de estas ideas tiene que pasar el mismo protocolo, con desarrollo, validación y un periodo final nuevo
que no se haya mirado antes.
