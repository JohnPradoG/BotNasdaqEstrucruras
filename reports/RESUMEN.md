# Resumen de resultados (2026-10-20)

Coste base: spread actual de Exness de 1,12 puntos más 0,5 puntos de deslizamiento por lado (lo pidió John).
Resultado en R = ganancia neta por operación dividida entre el riesgo. Datos: USTECm M1 de 2021-10-27 a 2026-10-20.
Detalle completo en [RESULTADOS.md](RESULTADOS.md).

## Conclusión

**Ninguna estrategia pasa el protocolo en ninguna de las tres combinaciones, así que el bot queda en NO OPERAR
(modo observación).** Antes de costes, las estructuras dan prácticamente 0 R: no tienen ventaja propia. Con el
coste más bajo posible el resultado ya es negativo. La memoria de casos parecidos mejora algún periodo, pero no de
forma estable: lo que funciona en desarrollo falla en validación, y al revés.

## Expectativa neta por operación (todas las señales de la regla)

| Combinación | Estrategia | Desarrollo 2021-23 | Validación 2024 | Holdout 2025-26 | Holdout bruto, sin costes |
|---|---|---|---|---|---|
| H4+H1+M15 | A continuación | +0,02 R (511) | −0,10 R (255) | −0,12 R (449) | −0,06 R |
| | B reversión | −0,11 R (2.348) | −0,06 R (1.187) | −0,11 R (2.059) | −0,01 R |
| | C cambio de tendencia | −0,05 R (861) | −0,14 R (393) | −0,06 R (756) | −0,02 R |
| H1+M15+M5 | A | −0,19 R (1.287) | −0,15 R (630) | −0,09 R (1.286) | +0,02 R |
| | B | −0,20 R (7.488) | −0,22 R (3.823) | −0,15 R (6.804) | +0,01 R |
| | C | −0,10 R (2.894) | −0,16 R (1.351) | −0,09 R (2.463) | −0,02 R |
| M15+M5+M1 | A | −0,34 R (6.416) | −0,33 R (3.123) | (no hace falta: no pasó la selección) | |
| | B | −0,36 R (37.000) | −0,37 R (18.062) | | |
| | C | −0,25 R (13.853) | −0,23 R (6.461) | | |

Entre paréntesis, el número de señales. Referencia, entradas al azar con el mismo stop y objetivo: −0,12 a −0,20 R.

## La memoria de casos parecidos

Mejores casos, que no pasaron la selección:
- C con memoria en M15 (k = 30): +0,05 R en desarrollo y −0,03 R en validación.
- B con memoria en M15: −0,12 R en desarrollo y +0,05 R en validación.
- C con memoria en M5 (k = 100): +0,06 R en el holdout (t = 1,16; no significativo). No se elige, porque había
  perdido en desarrollo (−0,09 R) y en validación (−0,13 R).

## Otros datos útiles

- Con el spread histórico real (4-5 puntos en 2021-2024) todo empeora: hasta −0,6 R en M5.
- Con el saldo real de la demo (543,93 USD) y 0,25 % de riesgo, el lote mínimo de 0,05 obliga a descartar muchas
  señales (por ejemplo, 456 en el holdout de M5).
- M1 sale peor que todo: con stops pequeños, el coste fijo pesa mucho más en R. Con memoria, M1 queda entre
  −0,11 y −0,25 R en desarrollo; selección: NO OPERAR.

## Auditoría y ajustes (2026-10-20, segunda ronda)

- **No hay errores en el sistema.** Se comprobaron la dirección de las señales, la hora, la entrada sin anticipación,
  los costes y la regla intravela. Después de la señal el precio va a favor solo un +0,013 ATR de media: las
  estructuras, por sí solas, no tienen ventaja, y el coste fijo (0,06 a 0,11 R por operación) deja el neto en negativo.
- **192 ajustes probados** (stop más amplio, objetivos de 1 a 3 R, stop mínimo de 20 puntos, solo Londres y Nueva York)
  en H4+H1+M15 y H1+M15+M5: **ninguno gana a la vez en desarrollo y en validación.** Decisión: **NO OPERAR.**
- Detalle: [docs/auditoria_y_ajustes.md](../docs/auditoria_y_ajustes.md).
