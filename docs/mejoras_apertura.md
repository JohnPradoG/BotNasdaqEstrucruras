# Mejorar las estrategias de apertura de NY (2026-10-20)

John pidió mejorar las estrategias que salieron positivas (ORB y noise area). El momentum de la última media hora
no se tocó, porque perdió en los tres periodos: "mejorarlo" sería forzarlo a encajar con el pasado.
Script: `scripts/run_mejoras.py` (rejilla guardada en git antes de ejecutar). Resultados: `reports/mejoras.json`.

Regla: en cada estrategia se elige un solo ajuste mirando solo 2021-23, y después se comprueba en 2024 sin tocar nada.

## 1. Ajustar cada estrategia

| Estrategia | Ajustes probados | Elegido con 2021-23 | 2021-23 | 2024 | 2025-26 |
|---|---|---|---|---|---|
| ORB 5 min | objetivo 3/5/10 R o cierre del día, stop extremo o mitad, ambas o solo compras (16) | el original: 10 R, stop extremo, ambas | +0,10 R (t 0,9) | +0,07 R | +0,09 R |
| Noise area | banda x0,75/1/1,25/1,5, ambas o solo compras (8) | banda x0,75, ambas | +0,08 (t 1,6) | +0,03 | +0,00 |

- **En el ORB de 5 min, ningún ajuste mejora el original.** Poner el stop en la mitad de la vela lo empeora siempre;
  operar solo compras empeora en 2024 y 2025-26.
- **En la noise area, el ajuste que mejor quedó en 2021-23 (banda más estrecha) se desinfla después**: de +0,08 a +0,03
  y luego a 0. Es otro ejemplo de que el mejor ajuste del pasado suele ser suerte.

## 2. Juntarlas en un solo bot (sin elegir nada)

ORB 15 min a favor de la media 50 + ORB 5 min + noise area, cada una con el mismo riesgo y operando a la vez.

| Periodo | Días | Resultado medio por día | t |
|---|---|---|---|
| 2021-23 | 554 | +0,20 R | 1,49 |
| 2024 | 257 | +0,19 R | 0,96 |
| 2025-26 | 456 | +0,18 R | 1,30 |

- Correlación diaria entre ellas: 0,26 a 0,31. Se parecen, pero no son la misma cosa, así que juntarlas ayuda algo.
- **Es lo más estable que hemos visto: +0,18 a +0,20 R por día en los tres periodos.** Pero el t sigue por debajo
  de 2, así que todavía no se puede descartar que sea suerte. La mayor racha mala acumulada fue −62,5 R.
- Con 0,25 % de riesgo por estrategia, eso sería del orden de +12 % al año y una caída máxima cercana al −15 %,
  si el pasado se repitiera. No es una promesa: es lo que pasó en el backtest.

## Conclusión

No hay un ajuste que "haga funcionar" estas estrategias; lo que mejor resiste es dejarlas como están y juntarlas.
La cartera de las tres estrategias de apertura es el candidato más serio de todo el proyecto. El paso honesto es
congelarla tal cual y medirla en la demo (solo observación) unos meses antes de arriesgar dinero.
