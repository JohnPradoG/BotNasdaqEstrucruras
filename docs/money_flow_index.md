# Money Flow Index (MFI): ¿funciona en alguna temporalidad? (2026-10-21)

Pedido por John ("una con money no sé qué"). Reglas y rejilla guardadas en git antes de ejecutar (`scripts/run_mfi.py`).
Datos reales de USTECm M1 (2021-11 a 2026-10), costes de Exness. Resultado: `reports/mfi/mfi.json`.

El MFI es como el RSI pero ponderado por volumen. En este CFD no hay volumen real: se usa el volumen de ticks, igual
que hace el MFI de MT5 en USTECm.

## Reglas

- Compra cuando el MFI(14) sale de sobreventa (cruza hacia arriba 20, o 10); venta cuando sale de sobrecompra
  (cruza hacia abajo 80, o 90). Al cierre de la vela, entrada a mercado.
- Stop 1,5 × ATR14. Salida con objetivo 2 R, o cuando el MFI vuelve a 50.
- Con y sin filtro de tendencia (solo a favor de la EMA 200 de esa temporalidad).
- 32 variantes: M5, M15, H1, H4 × niveles 20/80 y 10/90 × 2 salidas × 2 filtros.

## Resultado (R neto por operación)

| Temporalidad | 2021-23 | 2024 | 2025-26 |
|---|---|---|---|
| M5 | −0,11 | −0,28 | −0,18 |
| M15 | −0,06 | −0,22 | −0,11 |
| H1 | +0,35 | −0,24 | +0,05 |
| H4 | +0,20 | −0,34 | +0,29 |

(Media de las 8 variantes de cada temporalidad. En H1 y H4 las medias saltan mucho porque hay muy pocas operaciones.)

- **Aprobadas: 0 de 32.** Positivas en 2021-23 y 2024 a la vez: 4.
- M5 y M15 pierden en todos los periodos y en todas las variantes, incluso antes de costes en 2024-26.
- H1 y H4 dan muy pocas señales (con niveles 10/90, entre 10 y 50 por periodo): no hay forma de distinguir
  ventaja de suerte. La única positiva en los tres periodos, H4 10/90 con objetivo 2 R, tiene 44 operaciones en 5 años.

## Conclusión

El MFI no da ventaja en Nasdaq con nuestros costes. **No se mete al bot.**
