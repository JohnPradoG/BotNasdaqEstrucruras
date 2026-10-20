# Limitaciones conocidas y qué falta antes de una cuenta real

## Datos

- Solo velas M1 (BID + spread por vela) desde 2021-10-27. Sin ticks históricos antes de 2026: el orden dentro de cada
  minuto se resuelve con la hipótesis conservadora (stop primero).
- El spread de USTECm cambió mucho: mediana de 4,3 a 5,3 puntos en 2021-2024, unos 2 puntos en 2025-2026 y 1,12
  puntos desde agosto de 2026. Por decisión de John, el coste base es el spread actual (1,12 puntos) en todos los
  años; esto es optimista para 2021-2024. El spread histórico real se informa como sensibilidad.
- Un único instrumento y un único bróker; no se ha validado en otros índices.

## Simulación

- Deslizamiento fijo (0,5 puntos por lado) y estrés aproximado (coste extra fijo).
- Cierre forzado a las 16:55 de Nueva York; las operaciones no cruzan la pausa diaria ni pagan swap.
- La memoria se evalúa con una operación hipotética estándar (stop en la invalidación ± 0,10 ATR, objetivo 2 R).
  Otras gestiones (parciales, trailing) no están evaluadas.

## Modelo

- La similitud es de vecinos cercanos con pesos fijados a mano (interpretables, no optimizados). No hay modelo de
  aprendizaje automático: primero había que ver si existe alguna ventaja en la línea base.
- Figuras no implementadas para decidir: triángulos, banderas, cuñas, zonas de oferta/demanda como tales.

## Estado de la estrategia (2026-10-20)

- Auditoría sin errores y 192 ajustes probados (ver [auditoria_y_ajustes.md](auditoria_y_ajustes.md)): ninguno gana en
  desarrollo y validación a la vez. **El bot queda en NO OPERAR.**
- El holdout 2025-2026 ya se ha mirado varias veces como diagnóstico. Una idea nueva necesitará un periodo final nuevo
  (por ejemplo, la demo a partir de ahora) para evaluarse con honestidad.

## Antes de pensar en dinero real (todas obligatorias)

1. Que alguna estrategia pase la selección prerregistrada **y** el holdout final, con intervalo de confianza por encima
   de cero tras costes.
2. Al menos 3 meses de demo con el mismo código y la misma configuración, con resultados dentro del intervalo esperado.
3. Revisar el tamaño mínimo: con 543,93 USD de equity y 0,25 % de riesgo (1,36 USD), el lote mínimo de 0,05 solo
   permite stops de hasta ~27 puntos de índice; muchas señales se descartarían.
4. Ticks reales (2026 en adelante) para comprobar la hipótesis intravela.
5. Revisión humana del registro de ejecución de la demo (rechazos, deslizamiento real, reconciliaciones).
