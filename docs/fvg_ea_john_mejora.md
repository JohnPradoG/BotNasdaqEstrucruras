# Cómo mejorar el EA FVG de John, de forma honesta (2026-10-21)

Pregunta de John: "¿cómo lo mejoramos?". La única forma honesta es elegir los ajustes con unos años y
comprobarlos en otros que no se usaron para elegir. Aquí: se elige **solo con 2021-11 a 2023-12** y se comprueba
**2024-01 a 2026-10 sin tocar nada**. La rejilla y la regla se guardaron en git antes de ejecutar
(`scripts/run_fvg_john_mejora.py`). Resultado: `reports/fvg_john/mejora.json`.

Rejilla (48 combinaciones): dirección {ambas, solo ventas} × sesión {todas, solo Nueva York 9:30-16:00}
× objetivo {1,5 R, 2,5 R} × EMA {50, 80, 200} × hueco mínimo {0,2, 0,3 ATR}. El resto, igual que "Pass 195".
Aprobado solo si en 2021-23 t ≥ 2 y en 2024-26 es positivo con t ≥ 1.

## Resultado

| Ajuste | 2021-23 (para elegir) | 2024-26 (comprobación) |
|---|---|---|
| **Elegido: ambas, solo NY, 2,5 R, EMA 50, hueco 0,3** | +0,11 R (t 1,26; 363 ops) | **+0,03 R** (t 0,34; 413 ops) |
| Solo ventas, solo NY, 2,5 R, EMA 50, hueco 0,3 | +0,10 R (t 0,81; 169 ops) | +0,13 R (t 1,09; 205 ops) |
| Pass 195 + solo NY (EMA 80) | +0,06 R | −0,01 R |
| Pass 195 tal cual (todas las horas) | −0,10 R | +0,06 R |

- Positivas en 2021-23: 9 de 48. Positivas en los dos tramos: 7 de 48.
- Ninguna llega a t 2 en 2021-23 (con 48 pruebas haría falta t ≈ 3,1 para estar seguros).
- **Ninguna aprobada.**

## Qué significa

- Limitar las entradas al horario de Nueva York es lo que más ayuda: quita operaciones de madrugada que pierden.
  Pero la mejora casi desaparece en 2024-26 (+0,11 → +0,03 R por operación, unos 5 USD por operación con 1 % de 10.000).
- "Solo ventas en horario NY" sale positivo en los dos tramos, pero es débil (t < 1,1) y se nota después de mirar
  los resultados. Como mucho, puede observarse en demo como un módulo más, sin dinero real.
- Sigue sin haber ventaja clara. **Recomendación: no operar el EA con dinero real.**
