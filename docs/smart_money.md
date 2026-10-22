# Smart Money (SMC) completo, de todas las maneras (2026-10-21)

Pedido por John: "revísela de todas las maneras y que funcione". Rejilla y regla guardadas en git antes de ejecutar
(`scripts/run_smc.py`). Datos reales USTECm M1 2021-11 a 2026-10, costes de Exness. Resultado: `reports/smc/smc.json`.

## El flujo probado (compra; venta al revés)

1. **Sesgo** en H4 o H1: alcista desde que una vela cierra por encima del último máximo de oscilación (BOS). O sin sesgo.
2. **Barrido de liquidez** en M15 o M5: una vela perfora el último mínimo de oscilación (con o sin cierre de vuelta dentro).
3. **CHOCH**: en las 24 velas siguientes, cierre por encima del último máximo anterior al barrido.
4. **Entrada**: orden limitada en el **order block** (última vela bajista antes del impulso), en el **FVG** del impulso,
   o **a mercado** en el CHOCH. La limitada se cancela si el precio llega al objetivo sin llenarla.
5. **Stop** bajo el mínimo del barrido (− 0,1 ATR). **Objetivo** 2 R o 3 R. Tope 3 días.

144 variantes: H4/M15, H1/M15, H1/M5 × barrido {cualquiera, mecha} × entrada {OB, FVG, mercado} × {2 R, 3 R}
× sesión {todas, solo NY} × sesgo {estructura, ninguno}.
Regla: elegir **solo con 2021-23** y comprobar **2024-26 sin tocar**. Aprobada si 2021-23 t ≥ 2 y 2024-26 positiva con t ≥ 1.

## Resultado

| | 2021-23 (para elegir) | 2024-26 (comprobación) |
|---|---|---|
| **Elegida: H4/M15, barrido con mecha, order block, 3 R, sesgo H4** | **+0,23 R** (t 2,02; 251 ops) | **−0,33 R** (t −3,84; 297 ops) |
| La 2.ª mejor (igual, con 2 R) | +0,22 R (t 1,91) | −0,17 R |
| La 3.ª (FVG en vez de OB, 3 R) | +0,21 R (t 1,74) | −0,15 R |

- Positivas en 2021-23: 32 de 144. Positivas en los dos tramos: **2 de 144** (y con muy pocas operaciones).
- Media de todas: −0,03 R en 2021-23 y −0,09 R en 2024-26. Ninguna pieza ayuda de forma estable: ni el order block,
  ni el FVG, ni la mecha, ni la sesión de NY, ni el sesgo de H4.
- **Ninguna aprobada.**

## Qué significa

Es el ejemplo más claro de sobreajuste de todo el proyecto: la combinación que mejor salió en 2021-23 (t 2,02, casi
"significativa") es la que **más pierde** después (−0,33 R por operación: unos −97 R
acumulados en 297 operaciones). Elegir la mejor de 144 combinaciones casi siempre da una que encajó con el pasado.

**El Smart Money, tal como se opera normalmente, no tiene ventaja en Nasdaq con estos datos y costes. No entra al bot.**
Si John opera SMC con reglas propias distintas (por ejemplo, otra definición de order block o de barrido), se pueden
probar exactamente esas.
