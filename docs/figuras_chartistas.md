# Figuras chartistas clásicas (2026-10-20)

John preguntó si de verdad las figuras chartistas no funcionan, siendo algo que se repite desde siempre. Antes solo
se habían probado el doble techo/suelo y el HCH (con objetivo fijo de 2 R) en M15 y M5. Ahora se añadieron
triángulos, rectángulos, cuñas y banderas, con **objetivo medido de la figura** e invalidación clara, en M15, H1, H4
y D1. Script: `scripts/run_patterns.py`, con la rejilla y la regla guardadas en git antes de ejecutar.
Resultados: `reports/figuras.json` y `data/backtests/*_figuras`.

## Definiciones (resumen)

- Oscilaciones: pivotes 3-3 confirmados (se conocen 3 velas después) de al menos 0,5 ATR. La figura se opera solo
  cuando una vela **cierra** más allá de su línea. Entrada en la apertura siguiente.
- Doble techo/suelo, HCH e invertido, triángulo (simétrico, ascendente o descendente), rectángulo, cuña ascendente
  y descendente, y bandera: el detalle está en el encabezado del script.
- Salida: objetivo medido (la altura de la figura proyectada desde la ruptura) o 2 R; stop en la invalidación.
  Como máximo 60 velas. Las compras pagan swap.
- Coste: 1,12 de spread + 0,5 por lado.

## Resultado por figura (todas las temporalidades, objetivo medido, 2021-2026)

| Figura | Casos | Aciertos | Llega al objetivo | Bruto por operación | Neto por operación |
|---|---|---|---|---|---|
| Doble techo/suelo | 1.435 | 57 % | 53 % | −0,04 R | −0,07 R |
| HCH e invertido | 1.124 | 42 % | 36 % | −0,02 R | −0,08 R |
| Triángulo | 7.945 | 35 % | 27 % | −0,02 R | −0,08 R |
| Rectángulo | 887 | 45 % | 42 % | −0,03 R | −0,08 R |
| Cuña | 2.564 | 35 % | 30 % | +0,03 R | −0,06 R |
| Bandera | 1.601 | 40 % | 28 % | +0,04 R | −0,01 R |

## Selección con el examen

- 96 variantes (6 figuras × 4 temporalidades × 2 salidas × con o sin filtro de tendencia diaria).
  **Ninguna pasa** (hace falta t ≥ 2 en 2021-23 y ganar también en 2024). Positivas en 2021-23: 32 de 96, menos que
  por azar. Ninguna positiva tiene t ≥ 2 en desarrollo; la mejor es el rectángulo en M15 con 2 R y filtro de
  tendencia (+0,19 R, t = 1,46), que en 2024 da −0,36 R.
- En D1 hay muy pocas figuras (entre 0 y 20 por periodo): no se puede sacar ninguna conclusión.

## "Quedarse con las que funcionan y quitar las demás"

John pidió esto. Se hizo así: para cada figura y temporalidad, se tomó la variante con mejor media en 2021-23, y se
quedaron las 8 que daban positivo. Después se midieron juntas, sin tocar nada, en los periodos siguientes:

| Periodo | Operaciones | Neto por operación | Intervalo 90 % | Bruto |
|---|---|---|---|---|
| 2021-23 (donde se eligieron) | 1.044 | +0,085 R | −0,01 a +0,18 | +0,14 R |
| 2024 | 550 | **−0,14 R** | −0,25 a −0,02 | −0,08 R |
| 2025-26 | 1.078 | **−0,09 R** | −0,18 a −0,01 | −0,06 R |

Esto es justo el problema de quedarse con las que funcionaron: en el pasado parecen buenas, porque se eligieron por
eso, y después pierden. No había nada real que conservar.

## Por qué no funcionan aquí (lo que se midió)

1. **Que una figura aparezca no significa que el precio siga el camino del libro.** Tras la ruptura, el precio va a
   favor casi lo mismo que en contra: antes de costes, el resultado está entre −0,04 y +0,04 R.
2. **Acertar mucho no es ganar.** El doble techo/suelo llega al objetivo el 53 % de las veces, pero su objetivo medido
   es pequeño (0,63 R de media frente a 1 R de riesgo), así que pierde.
3. **Lo que todo el mundo ve ya está en el precio.** Si una figura tan visible diera dinero fácil, los algoritmos que
   operan el Nasdaq la explotarían hasta hacer desaparecer la ventaja.
4. **El coste se lleva lo poco que queda:** entre 0,04 y 0,09 R por operación.

Esto no prueba que ninguna figura funcione nunca en ningún mercado. Dice que, con estas definiciones objetivas, en
el Nasdaq de 2021 a 2026 y con los costes de Exness, no hay ventaja medible.
