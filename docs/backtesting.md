# Backtesting: cómo se simula cada operación

Código: `src/nsmb/backtesting/` (simulador, cartera, métricas, referencias).

## Datos

Velas M1 de USTECm (Exness, cuenta Standard) con precio BID y spread por vela en points (1 point = 0,01).
No hay ticks históricos del bróker para fechas anteriores a 2026 (comprobado con `copy_ticks_range`), así que el
orden de los precios dentro de un minuto es desconocido.

## Reglas de ejecución simulada

- **Entrada**: apertura de la primera vela M1 que empieza en el cierre de la vela de señal o después.
  Compras al ASK (`bid + spread`) + deslizamiento (50 points por lado por defecto); ventas al BID − deslizamiento.
- **Stop**: nivel de invalidación de la estructura ± 0,10 ATR. En ventas se suma el spread porque el stop de una venta
  se ejecuta contra el ASK. Compras: el stop salta cuando el BID mínimo de la vela lo toca.
- **Objetivo**: 2 R (variantes registradas en la memoria: 1 R, 1,5 R y sin objetivo).
- **Stop y objetivo en la misma vela M1**: se asume el **stop** (hipótesis conservadora).
- **Huecos**: si una vela abre más allá del stop, se ejecuta a la apertura (peor que el stop).
- **Salida por tiempo**: 48 velas de la temporalidad de entrada.
- **Cierre forzado de sesión**: de 16:55 a 18:00 de Nueva York se está fuera (pausa diaria de 17:00 a 18:00 y swap).
  No se abren señales entre 16:30 y 18:00 de Nueva York.
- **Swap**: como se cierra antes de la pausa diaria, no se paga swap en las operaciones intradía.

## Cartera y riesgo

- Una sola posición a la vez; la siguiente señal solo se toma tras salir de la anterior.
- Lote = riesgo (0,25 % del equity) / (distancia al stop + spread + 2·deslizamiento), redondeado hacia abajo al paso
  de volumen. Si el lote mínimo (0,05) supera el riesgo, **no se opera**.
- Pérdida diaria máxima 1 % del equity al inicio del día (Nueva York); drawdown total máximo 10 %;
  pausa tras 6 pérdidas seguidas; bloqueo tras 3 errores de ejecución.
- El resultado de una operación se contabiliza al salir; el día de una pérdida es el de su entrada.

## Limitaciones conocidas de la simulación

- Spread de cada vela M1 = el que registra MT5 para esa vela (no el máximo); en noticias puede ser mayor.
- El estrés de costes resta un coste fijo por operación; no recalcula qué vela tocaría el stop desplazado.
- Las entradas aleatorias de referencia usan el ATR de la temporalidad de entrada conocido en ese momento.
