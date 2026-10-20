# Protocolo estadístico (prerregistrado)

Este protocolo se escribió **antes** de mirar los resultados del periodo final. Código: `scripts/run_research.py`.

## Periodos (datos USTECm M1, 2021-10-27 → 2026-10-20)

| Periodo | Fechas | Uso |
|---|---|---|
| Desarrollo | 2021-11-01 → 2023-12-31 | explorar reglas y configuraciones de la memoria |
| Validación | 2024-01-01 → 2024-12-31 | confirmar lo elegido en desarrollo |
| Holdout final | 2025-01-01 → 2026-10-20 | **una sola evaluación** con la selección congelada; no elige nada |

Walk-forward adicional: pliegues anuales (2022, 2023, 2024 en la fase de selección); para cada año, las escalas
de la similitud se reajustan solo con episodios anteriores al 1 de enero de ese año.

## Qué se compara

1. Las tres familias de estrategias (A continuación, B reversión, C cambio de tendencia) con su filtro de contexto.
2. Las mismas reglas sin filtro de contexto (para medir si el contexto aporta algo).
3. Cada regla filtrada por la memoria de casos comparables con 4 configuraciones fijadas de antemano:
   k = 30 (media > 0), k = 60 (media > 0,05 R), k = 100 (media > 0), k = 100 (cota inferior 90 % > 0).
   En todas: mínimo 30 casos efectivos, vecinos a menos de 30 min cuentan como uno.
4. Referencias: entradas aleatorias (mismas horas del día, días y dirección al azar, stop 1 ATR, objetivo 2 R),
   todas las estructuras sin filtrar y comprar y mantener.

## Regla de selección (fijada antes de ejecutar)

Una opción **cumple** si:
- en desarrollo: ≥ 30 operaciones, expectativa neta > 0 R y t > 1,0;
- en validación: ≥ 15 operaciones y expectativa neta > 0 R.

Entre las que cumplen gana la de mayor `min(t_desarrollo, t_validación)`. **Si ninguna cumple, la decisión es
NO OPERAR** y el bot queda en observación. La selección se guarda en `models/seleccion_<combo>.json` antes del holdout.

## Estimaciones e incertidumbre

- Expectativa: media del resultado neto por operación en R, con IC 90 % `media ± 1,645·s/√n` y estadístico t.
- Probabilidad de alcanzar el objetivo antes de la invalidación: intervalo de Wilson al 90 %.
- Solapamiento: en la memoria y en los agregados, episodios a menos de 30 min cuentan como uno (`n_eff`).
- Con muestras pequeñas no se dan porcentajes "precisos": se informan siempre `n` y el intervalo.

## Prevención del sesgo de anticipación

- Pivotes confirmados solo tras R velas; todos los eventos llevan la vela en cuyo cierre se conocen (prueba de
  invariancia de prefijo en `tests/test_structures.py`).
- Las temporalidades superiores solo aportan velas **cerradas** (`align_higher`, por `close_time`).
- La memoria solo devuelve episodios cuyo desenlace ya había madurado (`matured_time ≤ T`).
- Las escalas de la similitud se ajustan solo con el periodo de desarrollo (o con datos previos a cada pliegue).
- El spread de referencia para excluir señales es una mediana móvil de episodios previos.

## Estrés

Deslizamiento ×2 y ×3, spread ×2 y spread histórico real, como coste adicional por operación (aproximación: no cambia qué vela toca
stop u objetivo). También se informa el resultado bruto sin costes.

## Cambio del protocolo (versión 2, 2026-10-20)

Tras ver la primera selección (con el spread histórico de cada vela, 4-5 puntos en 2021-2024), John pidió que el coste
base fuera el spread actual de Exness. Desde entonces el coste base es un spread fijo de **112 points (1,12 puntos)**
más 0,5 puntos de deslizamiento por lado (`backtest.cost_spread_points`). El spread histórico real se informa como
prueba de sensibilidad. Los resultados con el spread histórico quedan archivados en
`database/memory_spread_historico.sqlite` y `data/processed/spread_historico/`. Los criterios de selección no cambiaron.
