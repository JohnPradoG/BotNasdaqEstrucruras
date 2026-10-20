# Resultados reales de las pruebas ejecutadas

Todo lo que aparece aquí sale de ejecuciones reales registradas en `data/backtests/` y en la tabla `experiments`.
Resultado en R = beneficio neto (spread y deslizamiento incluidos) dividido entre el riesgo inicial. IC = intervalo de confianza del 90 %.

## Datos

USTECm M1 2021-10-27 17:20:00 → 2026-10-20 11:43:00, 1,716,946 velas, fuente `mt5_python`, hash `5e71e736e9cab90a`. Detalle en [datos.md](datos.md).

## H1 + M15 + M5 — etapa `holdout`

Coste de spread: 112 points por operación. Ejecución `20261020_130217_H1_M15_M5_holdout` (código 66d1e67, semilla 20261020, deslizamiento 50 points/lado, equity inicial 10,000 USD).

### Reglas base (todas las señales, resultado neto por operación en R)

| Regla | holdout | bruto sin costes (holdout) | con spread histórico real (holdout) |
|---|---|---|---|
| A_continuacion | n=1286, -0.094 R [-0.155; -0.032], t=-2.51, aciertos 33 % | n=1286, +0.015 R [-0.047; +0.076], t=0.4, aciertos 33 % | n=1286, -0.132 R [-0.193; -0.070], t=-3.52, aciertos 33 % |
| B_reversion | n=6804, -0.148 R [-0.175; -0.122], t=-9.14, aciertos 31 % | n=6804, +0.009 R [-0.017; +0.036], t=0.57, aciertos 31 % | n=6804, -0.203 R [-0.229; -0.176], t=-12.43, aciertos 31 % |
| C_cambio_tendencia | n=2463, -0.094 R [-0.134; -0.054], t=-3.86, aciertos 36 % | n=2463, -0.019 R [-0.059; +0.021], t=-0.79, aciertos 36 % | n=2463, -0.119 R [-0.159; -0.079], t=-4.86, aciertos 35 % |
| A_sin_contexto | n=4014, -0.120 R [-0.154; -0.086], t=-5.74, aciertos 32 % | n=4014, -0.011 R [-0.046; +0.023], t=-0.54, aciertos 32 % | n=4014, -0.158 R [-0.192; -0.123], t=-7.52, aciertos 32 % |
| B_sin_contexto | n=9771, -0.142 R [-0.165; -0.120], t=-10.49, aciertos 31 % | n=9771, +0.016 R [-0.007; +0.038], t=1.15, aciertos 31 % | n=9771, -0.197 R [-0.219; -0.174], t=-14.45, aciertos 31 % |
| C_sin_contexto | n=3525, -0.076 R [-0.110; -0.042], t=-3.7, aciertos 36 % | n=3525, -0.001 R [-0.034; +0.033], t=-0.04, aciertos 37 % | n=3525, -0.101 R [-0.135; -0.067], t=-4.91, aciertos 36 % |

Cartera (una posición, 0,25 % de riesgo, límites activos):

- A_continuacion: holdout: 244 ops, neto -820 USD (-8.2 %), PF 0.781, DD máx 10.1 %
- B_reversion: holdout: 210 ops, neto -979 USD (-9.8 %), PF 0.689, DD máx 10.1 %
- C_cambio_tendencia: holdout: 132 ops, neto -983 USD (-9.8 %), PF 0.501, DD máx 10.1 %
- A_sin_contexto: holdout: 308 ops, neto -985 USD (-9.8 %), PF 0.785, DD máx 10.1 %
- B_sin_contexto: holdout: 212 ops, neto -922 USD (-9.2 %), PF 0.714, DD máx 10.1 %
- C_sin_contexto: holdout: 656 ops, neto -958 USD (-9.6 %), PF 0.887, DD máx 10.1 %

### Regla + memoria de casos comparables (walk-forward: solo casos ya madurados)

| Estrategia · configuración | holdout (operadas/señales, resultado) |
|---|---|
| A_continuacion|mem_k30_mean+0.00 | 319/1286: n=319, -0.174 R [-0.292; -0.056], t=-2.43, aciertos 30 % |
| A_continuacion|mem_k60_mean+0.05 | 176/1286: n=176, -0.054 R [-0.218; +0.110], t=-0.54, aciertos 34 % |
| A_continuacion|mem_k100_mean+0.00 | 169/1286: n=169, -0.218 R [-0.376; -0.061], t=-2.29, aciertos 30 % |
| A_continuacion|mem_k100_lcb+0.00 | 5/1286: n=5, -0.647 R [-1.256; -0.038], t=-1.75, aciertos 20 % |
| B_reversion|mem_k30_mean+0.00 | 1568/6804: n=1568, -0.059 R [-0.115; -0.003], t=-1.72, aciertos 34 % |
| B_reversion|mem_k60_mean+0.05 | 801/6804: n=801, -0.016 R [-0.095; +0.063], t=-0.33, aciertos 36 % |
| B_reversion|mem_k100_mean+0.00 | 921/6804: n=921, -0.048 R [-0.120; +0.025], t=-1.08, aciertos 35 % |
| B_reversion|mem_k100_lcb+0.00 | 36/6804: n=36, +0.123 R [-0.259; +0.505], t=0.53, aciertos 42 % |
| C_cambio_tendencia|mem_k30_mean+0.00 | 829/2463: n=829, -0.140 R [-0.206; -0.075], t=-3.53, aciertos 35 % |
| C_cambio_tendencia|mem_k60_mean+0.05 | 496/2463: n=496, -0.011 R [-0.100; +0.078], t=-0.2, aciertos 39 % |
| C_cambio_tendencia|mem_k100_mean+0.00 | 652/2463: n=652, +0.055 R [-0.022; +0.132], t=1.16, aciertos 42 % |
| C_cambio_tendencia|mem_k100_lcb+0.00 | 29/2463: n=29, +0.064 R [-0.286; +0.414], t=0.3, aciertos 45 % |

### Selección congelada evaluada en el holdout: **NO_OPERAR**

### Walk-forward anual (k=30, media>0)

- A_continuacion|mem_k30_mean+0.00: 2022: base n=574, -0.127 R [-0.219; -0.035], t=-2.27, aciertos 32 % → memoria n=146, +0.016 R [-0.175; +0.206], t=0.14, aciertos 38 %; 2023: base n=616, -0.211 R [-0.298; -0.123], t=-3.96, aciertos 29 % → memoria n=158, -0.167 R [-0.341; +0.008], t=-1.57, aciertos 31 %; 2024: base n=630, -0.146 R [-0.234; -0.059], t=-2.76, aciertos 31 % → memoria n=147, -0.095 R [-0.281; +0.090], t=-0.85, aciertos 33 %; 2025: base n=701, -0.100 R [-0.183; -0.017], t=-1.98, aciertos 33 % → memoria n=173, -0.185 R [-0.348; -0.022], t=-1.87, aciertos 28 %; 2026: base n=585, -0.086 R [-0.177; +0.005], t=-1.55, aciertos 33 % → memoria n=150, -0.150 R [-0.321; +0.021], t=-1.44, aciertos 31 %
- B_reversion|mem_k30_mean+0.00: 2022: base n=3326, -0.165 R [-0.203; -0.126], t=-7.0, aciertos 30 % → memoria n=878, -0.107 R [-0.183; -0.032], t=-2.33, aciertos 33 %; 2023: base n=3604, -0.248 R [-0.284; -0.212], t=-11.34, aciertos 28 % → memoria n=892, -0.193 R [-0.265; -0.120], t=-4.38, aciertos 30 %; 2024: base n=3823, -0.217 R [-0.252; -0.182], t=-10.21, aciertos 29 % → memoria n=846, -0.160 R [-0.234; -0.086], t=-3.56, aciertos 31 %; 2025: base n=3819, -0.182 R [-0.217; -0.147], t=-8.48, aciertos 30 % → memoria n=863, -0.150 R [-0.223; -0.077], t=-3.39, aciertos 32 %; 2026: base n=2985, -0.106 R [-0.146; -0.065], t=-4.26, aciertos 32 % → memoria n=681, +0.046 R [-0.041; +0.134], t=0.87, aciertos 37 %
- C_cambio_tendencia|mem_k30_mean+0.00: 2022: base n=1314, -0.088 R [-0.145; -0.030], t=-2.51, aciertos 36 % → memoria n=513, -0.052 R [-0.143; +0.040], t=-0.93, aciertos 37 %; 2023: base n=1364, -0.127 R [-0.182; -0.072], t=-3.83, aciertos 35 % → memoria n=522, -0.116 R [-0.202; -0.029], t=-2.2, aciertos 35 %; 2024: base n=1351, -0.156 R [-0.210; -0.102], t=-4.74, aciertos 33 % → memoria n=486, -0.174 R [-0.262; -0.086], t=-3.25, aciertos 33 %; 2025: base n=1393, -0.134 R [-0.187; -0.081], t=-4.14, aciertos 34 % → memoria n=473, -0.200 R [-0.286; -0.113], t=-3.81, aciertos 32 %; 2026: base n=1070, -0.042 R [-0.103; +0.019], t=-1.13, aciertos 38 % → memoria n=363, +0.010 R [-0.091; +0.110], t=0.16, aciertos 42 %

### Referencias

- holdout: entradas aleatorias n=4008, -0.117 R [-0.152; -0.082], t=-5.44, aciertos 31 %; todas las estructuras n=46761, -0.098 R [-0.108; -0.088], t=-16.03, aciertos 33 %; comprar y mantener +39.2 %

### Detalle de `A_continuacion|base` en holdout (ejemplo: no hay estrategia elegida)

- Cartera: 244 ops, neto -820 USD (-8.2 %), PF 0.781, DD máx 10.1 %
- Métricas completas: `{"operaciones": 244, "beneficio_neto": -819.69, "rentabilidad_pct": -8.2, "profit_factor": 0.781, "tasa_aciertos": 0.3115, "expectativa_r": -0.1586, "expectativa_r_ic90": [-0.2971, -0.0201], "t_stat": -1.88, "expectativa_dinero": -3.36, "drawdown_max": 1033.24, "drawdown_max_pct": 10.12, "recuperacion_mas_larga_dias": 125.8, "mae_r_mediana": 1.068, "mfe_r_mediana": 0.696, "costes_totales": 525.19, "lote_medio": 1.015}`
- Señales descartadas por la cartera/riesgo: {'drawdown_total': 981, 'posicion_abierta': 41, 'perdidas_consecutivas': 15, 'sin_margen_perdida_diaria': 5}
- por sesion: asia: 89 ops, -0.375 R; londres: 88 ops, -0.070 R; ny: 42 ops, -0.013 R; ny_apertura: 21 ops, +0.039 R; tarde: 4 ops, +0.132 R
- por anio: 2025: 244 ops, -0.159 R
- por volatilidad: alta: 83 ops, -0.038 R; baja: 94 ops, -0.251 R; normal: 67 ops, -0.179 R
- por estructura: retest: 244 ops, -0.159 R

Estrés de costes: deslizamiento_x2: 229 ops, neto -862 USD (-8.6 %), PF 0.75, DD máx 10.2 %; deslizamiento_x3: 217 ops, neto -889 USD (-8.9 %), PF 0.726, DD máx 10.1 %; spread_x2: 228 ops, neto -862 USD (-8.6 %), PF 0.749, DD máx 10.1 %; spread_historico_real: 230 ops, neto -853 USD (-8.5 %), PF 0.755, DD máx 10.1 %

Con el equity real de la demo (543,93 USD): 456 ops, neto -47 USD (-8.7 %), PF 0.859, DD máx 10.2 %; descartes {'lote_minimo_supera_riesgo': 456, 'drawdown_total': 258, 'posicion_abierta': 65, 'perdidas_consecutivas': 51}

![equity](equity_H1_M15_M5_holdout.png)

## H1 + M15 + M5 — etapa `select`

Coste de spread: 112 points por operación. Ejecución `20261020_123317_H1_M15_M5_select` (código 66d1e67, semilla 20261020, deslizamiento 50 points/lado, equity inicial 10,000 USD).

### Reglas base (todas las señales, resultado neto por operación en R)

| Regla | desarrollo | validacion | bruto sin costes (validacion) | con spread histórico real (validacion) |
|---|---|---|---|---|
| A_continuacion | n=1287, -0.188 R [-0.249; -0.128], t=-5.11, aciertos 30 % | n=630, -0.146 R [-0.234; -0.059], t=-2.76, aciertos 31 % | n=630, +0.023 R [-0.064; +0.110], t=0.43, aciertos 32 % | n=630, -0.427 R [-0.517; -0.337], t=-7.78, aciertos 31 % |
| B_reversion | n=7488, -0.203 R [-0.229; -0.178], t=-13.15, aciertos 29 % | n=3823, -0.217 R [-0.252; -0.182], t=-10.21, aciertos 29 % | n=3823, +0.014 R [-0.021; +0.049], t=0.66, aciertos 29 % | n=3823, -0.599 R [-0.635; -0.561], t=-26.63, aciertos 29 % |
| C_cambio_tendencia | n=2894, -0.104 R [-0.143; -0.066], t=-4.51, aciertos 35 % | n=1351, -0.156 R [-0.210; -0.102], t=-4.74, aciertos 33 % | n=1351, -0.035 R [-0.089; +0.018], t=-1.08, aciertos 34 % | n=1351, -0.354 R [-0.409; -0.298], t=-10.43, aciertos 32 % |
| A_sin_contexto | n=4466, -0.178 R [-0.210; -0.145], t=-9.01, aciertos 30 % | n=2177, -0.176 R [-0.222; -0.129], t=-6.23, aciertos 30 % | n=2177, -0.004 R [-0.050; +0.042], t=-0.14, aciertos 30 % | n=2177, -0.460 R [-0.508; -0.412], t=-15.76, aciertos 29 % |
| B_sin_contexto | n=10644, -0.199 R [-0.221; -0.178], t=-15.39, aciertos 30 % | n=5283, -0.207 R [-0.237; -0.177], t=-11.35, aciertos 29 % | n=5283, +0.026 R [-0.003; +0.056], t=1.46, aciertos 29 % | n=5283, -0.589 R [-0.621; -0.557], t=-30.61, aciertos 29 % |
| C_sin_contexto | n=4101, -0.098 R [-0.130; -0.066], t=-5.05, aciertos 36 % | n=1881, -0.151 R [-0.197; -0.105], t=-5.39, aciertos 33 % | n=1881, -0.032 R [-0.078; +0.014], t=-1.16, aciertos 34 % | n=1881, -0.344 R [-0.392; -0.297], t=-12.03, aciertos 32 % |

Cartera (una posición, 0,25 % de riesgo, límites activos):

- A_continuacion: desarrollo: 96 ops, neto -946 USD (-9.5 %), PF 0.421, DD máx 10.0 %; validacion: 496 ops, neto -950 USD (-9.5 %), PF 0.863, DD máx 10.1 %
- B_reversion: desarrollo: 216 ops, neto -902 USD (-9.0 %), PF 0.707, DD máx 10.0 %; validacion: 154 ops, neto -808 USD (-8.1 %), PF 0.65, DD máx 10.2 %
- C_cambio_tendencia: desarrollo: 273 ops, neto -612 USD (-6.1 %), PF 0.837, DD máx 10.1 %; validacion: 363 ops, neto -956 USD (-9.6 %), PF 0.799, DD máx 10.1 %
- A_sin_contexto: desarrollo: 185 ops, neto -979 USD (-9.8 %), PF 0.648, DD máx 10.1 %; validacion: 243 ops, neto -974 USD (-9.7 %), PF 0.726, DD máx 10.1 %
- B_sin_contexto: desarrollo: 134 ops, neto -998 USD (-10.0 %), PF 0.503, DD máx 10.2 %; validacion: 177 ops, neto -944 USD (-9.4 %), PF 0.636, DD máx 10.1 %
- C_sin_contexto: desarrollo: 322 ops, neto -763 USD (-7.6 %), PF 0.826, DD máx 10.0 %; validacion: 156 ops, neto -981 USD (-9.8 %), PF 0.549, DD máx 10.1 %

### Regla + memoria de casos comparables (walk-forward: solo casos ya madurados)

| Estrategia · configuración | desarrollo (operadas/señales, resultado) | validacion (operadas/señales, resultado) |
|---|---|---|
| A_continuacion|mem_k30_mean+0.00 | 320/1287: n=320, -0.109 R [-0.234; +0.016], t=-1.43, aciertos 33 % | 145/630: n=145, -0.104 R [-0.290; +0.083], t=-0.92, aciertos 32 % |
| A_continuacion|mem_k60_mean+0.05 | 149/1287: n=149, -0.230 R [-0.401; -0.059], t=-2.22, aciertos 30 % | 73/630: n=73, +0.040 R [-0.231; +0.310], t=0.24, aciertos 37 % |
| A_continuacion|mem_k100_mean+0.00 | 178/1287: n=178, -0.083 R [-0.248; +0.082], t=-0.83, aciertos 35 % | 70/630: n=70, +0.003 R [-0.271; +0.277], t=0.02, aciertos 36 % |
| A_continuacion|mem_k100_lcb+0.00 | 4/1287: n=4, +0.130 R [-1.062; +1.321], t=0.18, aciertos 50 % | 2/630: n=2, -1.023 R [-1.044; -1.003], t=-81.46, aciertos 0 % |
| B_reversion|mem_k30_mean+0.00 | 1846/7488: n=1846, -0.152 R [-0.203; -0.100], t=-4.86, aciertos 31 % | 847/3823: n=847, -0.172 R [-0.246; -0.099], t=-3.86, aciertos 31 % |
| B_reversion|mem_k60_mean+0.05 | 1012/7488: n=1012, -0.049 R [-0.119; +0.022], t=-1.14, aciertos 35 % | 420/3823: n=420, -0.230 R [-0.331; -0.129], t=-3.74, aciertos 29 % |
| B_reversion|mem_k100_mean+0.00 | 1114/7488: n=1114, -0.010 R [-0.077; +0.057], t=-0.25, aciertos 37 % | 482/3823: n=482, -0.101 R [-0.200; -0.003], t=-1.69, aciertos 33 % |
| B_reversion|mem_k100_lcb+0.00 | 70/7488: n=70, -0.223 R [-0.480; +0.034], t=-1.43, aciertos 30 % | 14/3823: n=14, -0.310 R [-0.864; +0.244], t=-0.92, aciertos 21 % |
| C_cambio_tendencia|mem_k30_mean+0.00 | 1092/2894: n=1092, -0.059 R [-0.120; +0.003], t=-1.56, aciertos 37 % | 488/1351: n=488, -0.160 R [-0.248; -0.071], t=-2.97, aciertos 34 % |
| C_cambio_tendencia|mem_k60_mean+0.05 | 681/2894: n=681, -0.072 R [-0.150; +0.005], t=-1.54, aciertos 37 % | 264/1351: n=264, -0.212 R [-0.331; -0.093], t=-2.93, aciertos 31 % |
| C_cambio_tendencia|mem_k100_mean+0.00 | 834/2894: n=834, -0.093 R [-0.161; -0.025], t=-2.24, aciertos 36 % | 359/1351: n=359, -0.130 R [-0.230; -0.029], t=-2.11, aciertos 36 % |
| C_cambio_tendencia|mem_k100_lcb+0.00 | 16/2894: n=16, -0.564 R [-0.996; -0.132], t=-2.15, aciertos 19 % | 10/1351: n=10, +0.182 R [-0.624; +0.988], t=0.37, aciertos 40 % |

### Selección prerregistrada → **NO_OPERAR**

Criterio: dev: n>=30, media>0, t>1; val: n>=15, media>0; gana el mayor min(t_dev, t_val).

Opciones que cumplen: 0 de 15. Ninguna cumple, así que el bot NO OPERA con esta combinación.

### Walk-forward anual (k=30, media>0)

- A_continuacion|mem_k30_mean+0.00: 2022: base n=574, -0.127 R [-0.219; -0.035], t=-2.27, aciertos 32 % → memoria n=146, +0.016 R [-0.175; +0.206], t=0.14, aciertos 38 %; 2023: base n=616, -0.211 R [-0.298; -0.123], t=-3.96, aciertos 29 % → memoria n=158, -0.167 R [-0.341; +0.008], t=-1.57, aciertos 31 %; 2024: base n=630, -0.146 R [-0.234; -0.059], t=-2.76, aciertos 31 % → memoria n=147, -0.095 R [-0.281; +0.090], t=-0.85, aciertos 33 %
- B_reversion|mem_k30_mean+0.00: 2022: base n=3326, -0.165 R [-0.203; -0.126], t=-7.0, aciertos 30 % → memoria n=878, -0.107 R [-0.183; -0.032], t=-2.33, aciertos 33 %; 2023: base n=3604, -0.248 R [-0.284; -0.212], t=-11.34, aciertos 28 % → memoria n=892, -0.193 R [-0.265; -0.120], t=-4.38, aciertos 30 %; 2024: base n=3823, -0.217 R [-0.252; -0.182], t=-10.21, aciertos 29 % → memoria n=846, -0.160 R [-0.234; -0.086], t=-3.56, aciertos 31 %
- C_cambio_tendencia|mem_k30_mean+0.00: 2022: base n=1314, -0.088 R [-0.145; -0.030], t=-2.51, aciertos 36 % → memoria n=513, -0.052 R [-0.143; +0.040], t=-0.93, aciertos 37 %; 2023: base n=1364, -0.127 R [-0.182; -0.072], t=-3.83, aciertos 35 % → memoria n=522, -0.116 R [-0.202; -0.029], t=-2.2, aciertos 35 %; 2024: base n=1351, -0.156 R [-0.210; -0.102], t=-4.74, aciertos 33 % → memoria n=486, -0.174 R [-0.262; -0.086], t=-3.25, aciertos 33 %

### Referencias

- desarrollo: entradas aleatorias n=4460, -0.197 R [-0.230; -0.164], t=-9.82, aciertos 29 %; todas las estructuras n=55293, -0.154 R [-0.164; -0.145], t=-27.56, aciertos 31 %; comprar y mantener +5.9 %
- validacion: entradas aleatorias n=2175, -0.176 R [-0.223; -0.128], t=-6.08, aciertos 30 %; todas las estructuras n=26105, -0.147 R [-0.160; -0.133], t=-18.08, aciertos 32 %; comprar y mantener +24.6 %

### Detalle de `A_continuacion|base` en validacion (ejemplo: no hay estrategia elegida)

- Cartera: 496 ops, neto -950 USD (-9.5 %), PF 0.863, DD máx 10.1 %
- Métricas completas: `{"operaciones": 496, "beneficio_neto": -950.17, "rentabilidad_pct": -9.5, "profit_factor": 0.863, "tasa_aciertos": 0.3286, "expectativa_r": -0.1039, "expectativa_r_ic90": [-0.2037, -0.0041], "t_stat": -1.71, "expectativa_dinero": -1.92, "drawdown_max": 1018.39, "drawdown_max_pct": 10.11, "recuperacion_mas_larga_dias": 349.0, "mae_r_mediana": 1.077, "mfe_r_mediana": 0.814, "costes_totales": 1636.43, "lote_medio": 1.556}`
- Señales descartadas por la cartera/riesgo: {'posicion_abierta': 82, 'perdidas_consecutivas': 36, 'drawdown_total': 15, 'sin_margen_perdida_diaria': 1}
- por sesion: asia: 209 ops, -0.202 R; londres: 131 ops, -0.138 R; ny: 104 ops, +0.102 R; ny_apertura: 45 ops, -0.038 R; tarde: 7 ops, -0.008 R
- por anio: 2024: 496 ops, -0.104 R
- por volatilidad: alta: 185 ops, +0.073 R; baja: 184 ops, -0.290 R; normal: 127 ops, -0.092 R
- por estructura: retest: 496 ops, -0.104 R

Estrés de costes: deslizamiento_x2: 316 ops, neto -981 USD (-9.8 %), PF 0.777, DD máx 10.2 %; deslizamiento_x3: 260 ops, neto -991 USD (-9.9 %), PF 0.724, DD máx 10.1 %; spread_x2: 332 ops, neto -975 USD (-9.8 %), PF 0.789, DD máx 10.1 %; spread_historico_real: 188 ops, neto -1,019 USD (-10.2 %), PF 0.61, DD máx 10.2 %

Con el equity real de la demo (543,93 USD): 364 ops, neto -50 USD (-9.2 %), PF 0.813, DD máx 10.2 %; descartes {'lote_minimo_supera_riesgo': 162, 'posicion_abierta': 48, 'perdidas_consecutivas': 40, 'drawdown_total': 16}

![equity](equity_H1_M15_M5_select.png)

## H4 + H1 + M15 — etapa `holdout`

Coste de spread: 112 points por operación. Ejecución `20261020_130217_H4_H1_M15_holdout` (código 66d1e67, semilla 20261020, deslizamiento 50 points/lado, equity inicial 10,000 USD).

### Reglas base (todas las señales, resultado neto por operación en R)

| Regla | holdout | bruto sin costes (holdout) | con spread histórico real (holdout) |
|---|---|---|---|
| A_continuacion | n=449, -0.121 R [-0.220; -0.022], t=-2.01, aciertos 33 % | n=449, -0.057 R [-0.156; +0.043], t=-0.94, aciertos 33 % | n=449, -0.142 R [-0.242; -0.043], t=-2.36, aciertos 33 % |
| B_reversion | n=2059, -0.106 R [-0.154; -0.058], t=-3.62, aciertos 32 % | n=2059, -0.011 R [-0.060; +0.036], t=-0.39, aciertos 33 % | n=2059, -0.138 R [-0.186; -0.089], t=-4.71, aciertos 32 % |
| C_cambio_tendencia | n=756, -0.057 R [-0.129; +0.016], t=-1.29, aciertos 37 % | n=756, -0.017 R [-0.089; +0.056], t=-0.38, aciertos 37 % | n=756, -0.071 R [-0.143; +0.001], t=-1.61, aciertos 37 % |
| A_sin_contexto | n=1325, -0.055 R [-0.114; +0.004], t=-1.52, aciertos 35 % | n=1325, +0.007 R [-0.052; +0.066], t=0.19, aciertos 35 % | n=1325, -0.076 R [-0.135; -0.017], t=-2.11, aciertos 35 % |
| B_sin_contexto | n=3158, -0.115 R [-0.154; -0.077], t=-4.91, aciertos 32 % | n=3158, -0.021 R [-0.060; +0.017], t=-0.9, aciertos 33 % | n=3158, -0.147 R [-0.186; -0.108], t=-6.26, aciertos 32 % |
| C_sin_contexto | n=1130, -0.059 R [-0.119; +0.000], t=-1.64, aciertos 36 % | n=1130, -0.018 R [-0.078; +0.041], t=-0.5, aciertos 37 % | n=1130, -0.074 R [-0.134; -0.015], t=-2.05, aciertos 36 % |

Cartera (una posición, 0,25 % de riesgo, límites activos):

- A_continuacion: holdout: 212 ops, neto -651 USD (-6.5 %), PF 0.798, DD máx 10.1 %
- B_reversion: holdout: 250 ops, neto -946 USD (-9.5 %), PF 0.759, DD máx 10.0 %
- C_cambio_tendencia: holdout: 563 ops, neto -483 USD (-4.8 %), PF 0.933, DD máx 8.2 %
- A_sin_contexto: holdout: 572 ops, neto -781 USD (-7.8 %), PF 0.903, DD máx 10.0 %
- B_sin_contexto: holdout: 277 ops, neto -843 USD (-8.4 %), PF 0.803, DD máx 10.0 %
- C_sin_contexto: holdout: 335 ops, neto -1,004 USD (-10.0 %), PF 0.772, DD máx 10.0 %

### Regla + memoria de casos comparables (walk-forward: solo casos ya madurados)

| Estrategia · configuración | holdout (operadas/señales, resultado) |
|---|---|
| A_continuacion|mem_k30_mean+0.00 | 180/449: n=180, +0.000 R [-0.158; +0.159], t=0.0, aciertos 37 % |
| A_continuacion|mem_k60_mean+0.05 | 113/449: n=113, -0.056 R [-0.253; +0.142], t=-0.47, aciertos 36 % |
| A_continuacion|mem_k100_mean+0.00 | 139/449: n=139, -0.008 R [-0.188; +0.173], t=-0.07, aciertos 37 % |
| A_continuacion|mem_k100_lcb+0.00 | 9/449: n=9, +0.133 R [-0.662; +0.929], t=0.28, aciertos 44 % |
| B_reversion|mem_k30_mean+0.00 | 715/2059: n=715, -0.037 R [-0.119; +0.045], t=-0.74, aciertos 36 % |
| B_reversion|mem_k60_mean+0.05 | 460/2059: n=460, -0.015 R [-0.116; +0.087], t=-0.23, aciertos 36 % |
| B_reversion|mem_k100_mean+0.00 | 543/2059: n=543, -0.051 R [-0.144; +0.042], t=-0.91, aciertos 35 % |
| B_reversion|mem_k100_lcb+0.00 | 26/2059: n=26, +0.236 R [-0.182; +0.655], t=0.93, aciertos 54 % |
| C_cambio_tendencia|mem_k30_mean+0.00 | 290/756: n=290, -0.107 R [-0.223; +0.009], t=-1.52, aciertos 35 % |
| C_cambio_tendencia|mem_k60_mean+0.05 | 172/756: n=172, -0.133 R [-0.280; +0.014], t=-1.49, aciertos 34 % |
| C_cambio_tendencia|mem_k100_mean+0.00 | 237/756: n=237, -0.098 R [-0.222; +0.026], t=-1.29, aciertos 35 % |
| C_cambio_tendencia|mem_k100_lcb+0.00 | 9/756: n=9, -0.078 R [-0.781; +0.624], t=-0.18, aciertos 33 % |

### Selección congelada evaluada en el holdout: **NO_OPERAR**

### Walk-forward anual (k=30, media>0)

- A_continuacion|mem_k30_mean+0.00: 2023: base n=233, +0.138 R [-0.013; +0.288], t=1.5, aciertos 42 % → memoria n=107, +0.146 R [-0.076; +0.368], t=1.08, aciertos 42 %; 2024: base n=255, -0.104 R [-0.241; +0.032], t=-1.26, aciertos 33 % → memoria n=114, -0.050 R [-0.254; +0.154], t=-0.4, aciertos 36 %; 2025: base n=247, -0.090 R [-0.226; +0.047], t=-1.08, aciertos 34 % → memoria n=111, -0.086 R [-0.288; +0.116], t=-0.7, aciertos 33 %; 2026: base n=202, -0.159 R [-0.304; -0.015], t=-1.81, aciertos 31 % → memoria n=71, -0.063 R [-0.307; +0.180], t=-0.43, aciertos 37 %
- B_reversion|mem_k30_mean+0.00: 2022: base n=1038, -0.083 R [-0.153; -0.013], t=-1.94, aciertos 32 % → memoria n=315, -0.110 R [-0.234; +0.014], t=-1.46, aciertos 31 %; 2023: base n=1148, -0.138 R [-0.203; -0.073], t=-3.49, aciertos 31 % → memoria n=364, -0.186 R [-0.298; -0.074], t=-2.74, aciertos 30 %; 2024: base n=1187, -0.059 R [-0.123; +0.006], t=-1.5, aciertos 34 % → memoria n=428, +0.050 R [-0.058; +0.158], t=0.77, aciertos 39 %; 2025: base n=1133, -0.109 R [-0.174; -0.044], t=-2.75, aciertos 32 % → memoria n=397, -0.078 R [-0.188; +0.032], t=-1.17, aciertos 34 %; 2026: base n=926, -0.102 R [-0.173; -0.031], t=-2.36, aciertos 33 % → memoria n=309, +0.041 R [-0.084; +0.166], t=0.53, aciertos 40 %
- C_cambio_tendencia|mem_k30_mean+0.00: 2022: base n=363, -0.019 R [-0.131; +0.093], t=-0.28, aciertos 37 % → memoria n=87, -0.035 R [-0.252; +0.181], t=-0.27, aciertos 38 %; 2023: base n=417, -0.049 R [-0.152; +0.055], t=-0.77, aciertos 36 % → memoria n=174, +0.026 R [-0.140; +0.191], t=0.26, aciertos 39 %; 2024: base n=393, -0.141 R [-0.243; -0.038], t=-2.26, aciertos 34 % → memoria n=157, -0.032 R [-0.201; +0.138], t=-0.31, aciertos 37 %; 2025: base n=421, -0.061 R [-0.158; +0.036], t=-1.04, aciertos 37 % → memoria n=171, -0.033 R [-0.189; +0.122], t=-0.35, aciertos 37 %; 2026: base n=335, -0.051 R [-0.160; +0.058], t=-0.77, aciertos 36 % → memoria n=123, -0.096 R [-0.274; +0.082], t=-0.89, aciertos 35 %

### Referencias

- holdout: entradas aleatorias n=1325, -0.088 R [-0.148; -0.028], t=-2.4, aciertos 32 %; todas las estructuras n=15271, -0.049 R [-0.066; -0.032], t=-4.7, aciertos 35 %; comprar y mantener +39.1 %

### Detalle de `A_continuacion|base` en holdout (ejemplo: no hay estrategia elegida)

- Cartera: 212 ops, neto -651 USD (-6.5 %), PF 0.798, DD máx 10.1 %
- Métricas completas: `{"operaciones": 212, "beneficio_neto": -651.11, "rentabilidad_pct": -6.51, "profit_factor": 0.798, "tasa_aciertos": 0.316, "expectativa_r": -0.1393, "expectativa_r_ic90": [-0.2845, 0.006], "t_stat": -1.58, "expectativa_dinero": -3.07, "drawdown_max": 1047.58, "drawdown_max_pct": 10.08, "recuperacion_mas_larga_dias": 307.6, "mae_r_mediana": 1.048, "mfe_r_mediana": 0.813, "costes_totales": 340.51, "lote_medio": 0.758}`
- Señales descartadas por la cartera/riesgo: {'drawdown_total': 199, 'posicion_abierta': 25, 'perdidas_consecutivas': 13}
- por sesion: asia: 87 ops, -0.057 R; londres: 66 ops, -0.356 R; ny: 40 ops, -0.185 R; ny_apertura: 18 ops, +0.332 R; tarde: 1 ops, +0.363 R
- por anio: 2025: 210 ops, -0.131 R; 2026: 2 ops, -1.025 R
- por volatilidad: alta: 64 ops, -0.027 R; baja: 80 ops, -0.162 R; normal: 68 ops, -0.218 R
- por estructura: retest: 212 ops, -0.139 R

Estrés de costes: deslizamiento_x2: 202 ops, neto -682 USD (-6.8 %), PF 0.776, DD máx 10.1 %; deslizamiento_x3: 196 ops, neto -714 USD (-7.1 %), PF 0.756, DD máx 10.0 %; spread_x2: 202 ops, neto -694 USD (-6.9 %), PF 0.771, DD máx 10.1 %; spread_historico_real: 209 ops, neto -685 USD (-6.8 %), PF 0.783, DD máx 10.2 %

Con el equity real de la demo (543,93 USD): 94 ops, neto -28 USD (-5.1 %), PF 0.647, DD máx 6.4 %; descartes {'lote_minimo_supera_riesgo': 338, 'perdidas_consecutivas': 9, 'posicion_abierta': 8}

![equity](equity_H4_H1_M15_holdout.png)

## H4 + H1 + M15 — etapa `select`

Coste de spread: 112 points por operación. Ejecución `20261020_123317_H4_H1_M15_select` (código 66d1e67, semilla 20261020, deslizamiento 50 points/lado, equity inicial 10,000 USD).

### Reglas base (todas las señales, resultado neto por operación en R)

| Regla | desarrollo | validacion | bruto sin costes (validacion) | con spread histórico real (validacion) |
|---|---|---|---|---|
| A_continuacion | n=511, +0.022 R [-0.080; +0.124], t=0.35, aciertos 38 % | n=255, -0.104 R [-0.241; +0.032], t=-1.26, aciertos 33 % | n=255, +0.001 R [-0.136; +0.137], t=0.01, aciertos 34 % | n=255, -0.286 R [-0.424; -0.149], t=-3.43, aciertos 33 % |
| B_reversion | n=2348, -0.107 R [-0.153; -0.061], t=-3.83, aciertos 32 % | n=1187, -0.059 R [-0.123; +0.006], t=-1.5, aciertos 34 % | n=1187, +0.080 R [+0.016; +0.144], t=2.05, aciertos 35 % | n=1187, -0.287 R [-0.353; -0.221], t=-7.19, aciertos 34 % |
| C_cambio_tendencia | n=861, -0.049 R [-0.121; +0.022], t=-1.13, aciertos 36 % | n=393, -0.141 R [-0.243; -0.038], t=-2.26, aciertos 34 % | n=393, -0.069 R [-0.171; +0.034], t=-1.11, aciertos 34 % | n=393, -0.265 R [-0.368; -0.162], t=-4.24, aciertos 33 % |
| A_sin_contexto | n=1482, -0.042 R [-0.100; +0.017], t=-1.18, aciertos 35 % | n=747, -0.092 R [-0.171; -0.013], t=-1.92, aciertos 33 % | n=747, +0.009 R [-0.069; +0.088], t=0.19, aciertos 34 % | n=747, -0.259 R [-0.339; -0.179], t=-5.35, aciertos 33 % |
| B_sin_contexto | n=3624, -0.107 R [-0.144; -0.070], t=-4.77, aciertos 32 % | n=1784, -0.077 R [-0.129; -0.025], t=-2.42, aciertos 34 % | n=1784, +0.067 R [+0.015; +0.120], t=2.12, aciertos 34 % | n=1784, -0.315 R [-0.369; -0.262], t=-9.67, aciertos 33 % |
| C_sin_contexto | n=1327, -0.067 R [-0.125; -0.010], t=-1.94, aciertos 36 % | n=578, -0.116 R [-0.202; -0.030], t=-2.21, aciertos 34 % | n=578, -0.044 R [-0.130; +0.042], t=-0.84, aciertos 34 % | n=578, -0.236 R [-0.323; -0.150], t=-4.49, aciertos 33 % |

Cartera (una posición, 0,25 % de riesgo, límites activos):

- A_continuacion: desarrollo: 202 ops, neto -884 USD (-8.8 %), PF 0.728, DD máx 10.1 %; validacion: 212 ops, neto -237 USD (-2.4 %), PF 0.922, DD máx 7.6 %
- B_reversion: desarrollo: 252 ops, neto -874 USD (-8.7 %), PF 0.775, DD máx 10.0 %; validacion: 479 ops, neto -764 USD (-7.6 %), PF 0.887, DD máx 10.1 %
- C_cambio_tendencia: desarrollo: 612 ops, neto -913 USD (-9.1 %), PF 0.887, DD máx 10.1 %; validacion: 274 ops, neto -827 USD (-8.3 %), PF 0.785, DD máx 10.1 %
- A_sin_contexto: desarrollo: 179 ops, neto -1,015 USD (-10.2 %), PF 0.642, DD máx 10.2 %; validacion: 407 ops, neto -567 USD (-5.7 %), PF 0.904, DD máx 10.2 %
- B_sin_contexto: desarrollo: 630 ops, neto -876 USD (-8.8 %), PF 0.906, DD máx 10.0 %; validacion: 440 ops, neto -707 USD (-7.1 %), PF 0.887, DD máx 10.2 %
- C_sin_contexto: desarrollo: 130 ops, neto -919 USD (-9.2 %), PF 0.55, DD máx 10.1 %; validacion: 284 ops, neto -815 USD (-8.2 %), PF 0.798, DD máx 10.1 %

### Regla + memoria de casos comparables (walk-forward: solo casos ya madurados)

| Estrategia · configuración | desarrollo (operadas/señales, resultado) | validacion (operadas/señales, resultado) |
|---|---|---|
| A_continuacion|mem_k30_mean+0.00 | 184/511: n=184, -0.008 R [-0.182; +0.166], t=-0.08, aciertos 39 % | 115/255: n=115, -0.032 R [-0.236; +0.172], t=-0.26, aciertos 37 % |
| A_continuacion|mem_k60_mean+0.05 | 108/511: n=108, +0.032 R [-0.178; +0.241], t=0.25, aciertos 42 % | 85/255: n=85, -0.134 R [-0.362; +0.095], t=-0.96, aciertos 33 % |
| A_continuacion|mem_k100_mean+0.00 | 125/511: n=125, +0.055 R [-0.143; +0.253], t=0.46, aciertos 42 % | 104/255: n=104, -0.155 R [-0.360; +0.050], t=-1.25, aciertos 33 % |
| A_continuacion|mem_k100_lcb+0.00 | 2/511: n=2, -0.632 R [-1.321; +0.057], t=-1.51, aciertos 0 % | 3/255: n=3, -0.507 R [-1.339; +0.325], t=-1.0, aciertos 33 % |
| B_reversion|mem_k30_mean+0.00 | 671/2348: n=671, -0.121 R [-0.205; -0.036], t=-2.35, aciertos 32 % | 434/1187: n=434, +0.046 R [-0.061; +0.153], t=0.71, aciertos 39 % |
| B_reversion|mem_k60_mean+0.05 | 396/2348: n=396, -0.123 R [-0.231; -0.015], t=-1.88, aciertos 31 % | 270/1187: n=270, -0.019 R [-0.150; +0.113], t=-0.23, aciertos 37 % |
| B_reversion|mem_k100_mean+0.00 | 432/2348: n=432, -0.086 R [-0.189; +0.018], t=-1.36, aciertos 33 % | 313/1187: n=313, -0.059 R [-0.179; +0.061], t=-0.81, aciertos 36 % |
| B_reversion|mem_k100_lcb+0.00 | 15/2348: n=15, -0.077 R [-0.665; +0.511], t=-0.21, aciertos 33 % | 17/1187: n=17, +0.394 R [-0.152; +0.939], t=1.19, aciertos 53 % |
| C_cambio_tendencia|mem_k30_mean+0.00 | 267/861: n=267, +0.052 R [-0.078; +0.183], t=0.66, aciertos 40 % | 157/393: n=157, -0.032 R [-0.201; +0.138], t=-0.31, aciertos 37 % |
| C_cambio_tendencia|mem_k60_mean+0.05 | 178/861: n=178, -0.008 R [-0.168; +0.152], t=-0.08, aciertos 38 % | 93/393: n=93, -0.194 R [-0.396; +0.009], t=-1.57, aciertos 32 % |
| C_cambio_tendencia|mem_k100_mean+0.00 | 221/861: n=221, +0.014 R [-0.126; +0.154], t=0.17, aciertos 38 % | 133/393: n=133, -0.199 R [-0.366; -0.031], t=-1.95, aciertos 32 % |
| C_cambio_tendencia|mem_k100_lcb+0.00 | 10/861: n=10, -0.162 R [-0.810; +0.486], t=-0.41, aciertos 40 % | 5/393: n=5, -0.381 R [-1.193; +0.431], t=-0.77, aciertos 20 % |

### Selección prerregistrada → **NO_OPERAR**

Criterio: dev: n>=30, media>0, t>1; val: n>=15, media>0; gana el mayor min(t_dev, t_val).

Opciones que cumplen: 0 de 15. Ninguna cumple, así que el bot NO OPERA con esta combinación.

### Walk-forward anual (k=30, media>0)

- A_continuacion|mem_k30_mean+0.00: 2023: base n=233, +0.138 R [-0.013; +0.288], t=1.5, aciertos 42 % → memoria n=107, +0.146 R [-0.076; +0.368], t=1.08, aciertos 42 %; 2024: base n=255, -0.104 R [-0.241; +0.032], t=-1.26, aciertos 33 % → memoria n=114, -0.050 R [-0.254; +0.154], t=-0.4, aciertos 36 %
- B_reversion|mem_k30_mean+0.00: 2022: base n=1038, -0.083 R [-0.153; -0.013], t=-1.94, aciertos 32 % → memoria n=315, -0.110 R [-0.234; +0.014], t=-1.46, aciertos 31 %; 2023: base n=1148, -0.138 R [-0.203; -0.073], t=-3.49, aciertos 31 % → memoria n=364, -0.186 R [-0.298; -0.074], t=-2.74, aciertos 30 %; 2024: base n=1187, -0.059 R [-0.123; +0.006], t=-1.5, aciertos 34 % → memoria n=428, +0.050 R [-0.058; +0.158], t=0.77, aciertos 39 %
- C_cambio_tendencia|mem_k30_mean+0.00: 2022: base n=363, -0.019 R [-0.131; +0.093], t=-0.28, aciertos 37 % → memoria n=87, -0.035 R [-0.252; +0.181], t=-0.27, aciertos 38 %; 2023: base n=417, -0.049 R [-0.152; +0.055], t=-0.77, aciertos 36 % → memoria n=174, +0.026 R [-0.140; +0.191], t=0.26, aciertos 39 %; 2024: base n=393, -0.141 R [-0.243; -0.038], t=-2.26, aciertos 34 % → memoria n=157, -0.032 R [-0.201; +0.138], t=-0.31, aciertos 37 %

### Referencias

- desarrollo: entradas aleatorias n=1482, -0.109 R [-0.167; -0.051], t=-3.08, aciertos 31 %; todas las estructuras n=18245, -0.065 R [-0.081; -0.048], t=-6.56, aciertos 35 %; comprar y mantener +6.0 %
- validacion: entradas aleatorias n=747, -0.067 R [-0.148; +0.014], t=-1.37, aciertos 34 %; todas las estructuras n=8740, -0.059 R [-0.082; -0.036], t=-4.22, aciertos 35 %; comprar y mantener +24.7 %

### Detalle de `A_continuacion|base` en validacion (ejemplo: no hay estrategia elegida)

- Cartera: 212 ops, neto -237 USD (-2.4 %), PF 0.922, DD máx 7.6 %
- Métricas completas: `{"operaciones": 212, "beneficio_neto": -237.34, "rentabilidad_pct": -2.37, "profit_factor": 0.922, "tasa_aciertos": 0.3585, "expectativa_r": -0.0454, "expectativa_r_ic90": [-0.1965, 0.1056], "t_stat": -0.49, "expectativa_dinero": -1.12, "drawdown_max": 786.29, "drawdown_max_pct": 7.6, "recuperacion_mas_larga_dias": 308.5, "mae_r_mediana": 1.053, "mfe_r_mediana": 0.914, "costes_totales": 469.81, "lote_medio": 1.045}`
- Señales descartadas por la cartera/riesgo: {'posicion_abierta': 39, 'perdidas_consecutivas': 4}
- por sesion: asia: 89 ops, +0.095 R; londres: 61 ops, -0.090 R; ny: 36 ops, -0.158 R; ny_apertura: 25 ops, -0.257 R; tarde: 1 ops, -0.492 R
- por anio: 2024: 212 ops, -0.045 R
- por volatilidad: alta: 71 ops, +0.003 R; baja: 70 ops, -0.075 R; normal: 71 ops, -0.065 R
- por estructura: retest: 212 ops, -0.045 R

Estrés de costes: deslizamiento_x2: 212 ops, neto -438 USD (-4.4 %), PF 0.855, DD máx 8.7 %; deslizamiento_x3: 212 ops, neto -610 USD (-6.1 %), PF 0.797, DD máx 9.6 %; spread_x2: 212 ops, neto -459 USD (-4.6 %), PF 0.848, DD máx 8.8 %; spread_historico_real: 175 ops, neto -914 USD (-9.1 %), PF 0.635, DD máx 10.2 %

Con el equity real de la demo (543,93 USD): 121 ops, neto -3 USD (-0.5 %), PF 0.969, DD máx 4.4 %; descartes {'lote_minimo_supera_riesgo': 116, 'posicion_abierta': 13, 'perdidas_consecutivas': 5}

![equity](equity_H4_H1_M15_select.png)

## M15 + M5 + M1 — etapa `select`

Coste de spread: 112 points por operación. Ejecución `20261020_130219_M15_M5_M1_select` (código 66d1e67, semilla 20261020, deslizamiento 50 points/lado, equity inicial 10,000 USD).

### Reglas base (todas las señales, resultado neto por operación en R)

| Regla | desarrollo | validacion | bruto sin costes (validacion) | con spread histórico real (validacion) |
|---|---|---|---|---|
| A_continuacion | n=6416, -0.338 R [-0.364; -0.312], t=-21.46, aciertos 26 % | n=3123, -0.333 R [-0.370; -0.296], t=-14.68, aciertos 26 % | n=3123, +0.003 R [-0.034; +0.040], t=0.13, aciertos 26 % | n=3123, -0.889 R [-0.930; -0.849], t=-36.11, aciertos 25 % |
| B_reversion | n=37000, -0.355 R [-0.366; -0.344], t=-53.33, aciertos 26 % | n=18062, -0.369 R [-0.385; -0.354], t=-39.12, aciertos 25 % | n=18062, +0.051 R [+0.036; +0.067], t=5.51, aciertos 26 % | n=18062, -1.053 R [-1.070; -1.035], t=-97.82, aciertos 24 % |
| C_cambio_tendencia | n=13853, -0.254 R [-0.270; -0.237], t=-25.43, aciertos 31 % | n=6461, -0.228 R [-0.252; -0.204], t=-15.47, aciertos 32 % | n=6461, +0.019 R [-0.005; +0.043], t=1.33, aciertos 33 % | n=6461, -0.629 R [-0.655; -0.602], t=-39.25, aciertos 29 % |
| A_sin_contexto | n=21535, -0.334 R [-0.348; -0.320], t=-38.8, aciertos 26 % | n=10321, -0.327 R [-0.348; -0.307], t=-26.22, aciertos 26 % | n=10321, +0.012 R [-0.008; +0.032], t=0.96, aciertos 27 % | n=10321, -0.885 R [-0.907; -0.862], t=-64.67, aciertos 25 % |
| B_sin_contexto | n=52896, -0.356 R [-0.365; -0.347], t=-63.95, aciertos 26 % | n=25871, -0.369 R [-0.382; -0.356], t=-46.73, aciertos 25 % | n=25871, +0.050 R [+0.037; +0.063], t=6.47, aciertos 26 % | n=25871, -1.052 R [-1.067; -1.037], t=-117.44, aciertos 24 % |
| C_sin_contexto | n=19749, -0.244 R [-0.258; -0.230], t=-29.09, aciertos 32 % | n=9337, -0.231 R [-0.251; -0.211], t=-18.89, aciertos 32 % | n=9337, +0.014 R [-0.006; +0.034], t=1.17, aciertos 34 % | n=9337, -0.630 R [-0.652; -0.608], t=-47.29, aciertos 29 % |

Cartera (una posición, 0,25 % de riesgo, límites activos):

- A_continuacion: desarrollo: 168 ops, neto -1,002 USD (-10.0 %), PF 0.569, DD máx 10.0 %; validacion: 188 ops, neto -989 USD (-9.9 %), PF 0.618, DD máx 10.1 %
- B_reversion: desarrollo: 132 ops, neto -974 USD (-9.7 %), PF 0.453, DD máx 10.1 %; validacion: 173 ops, neto -1,001 USD (-10.0 %), PF 0.566, DD máx 10.0 %
- C_cambio_tendencia: desarrollo: 123 ops, neto -1,000 USD (-10.0 %), PF 0.419, DD máx 10.0 %; validacion: 273 ops, neto -947 USD (-9.5 %), PF 0.723, DD máx 10.2 %
- A_sin_contexto: desarrollo: 143 ops, neto -984 USD (-9.8 %), PF 0.491, DD máx 10.1 %; validacion: 131 ops, neto -948 USD (-9.5 %), PF 0.483, DD máx 10.0 %
- B_sin_contexto: desarrollo: 153 ops, neto -980 USD (-9.8 %), PF 0.506, DD máx 10.1 %; validacion: 184 ops, neto -1,002 USD (-10.0 %), PF 0.581, DD máx 10.0 %
- C_sin_contexto: desarrollo: 123 ops, neto -1,019 USD (-10.2 %), PF 0.396, DD máx 10.2 %; validacion: 191 ops, neto -936 USD (-9.4 %), PF 0.618, DD máx 10.1 %

### Regla + memoria de casos comparables (walk-forward: solo casos ya madurados)

| Estrategia · configuración | desarrollo (operadas/señales, resultado) | validacion (operadas/señales, resultado) |
|---|---|---|
| A_continuacion|mem_k30_mean+0.00 | 965/6416: n=965, -0.248 R [-0.316; -0.181], t=-6.08, aciertos 29 % | 362/3123: n=362, -0.157 R [-0.271; -0.043], t=-2.27, aciertos 31 % |
| A_continuacion|mem_k60_mean+0.05 | 374/6416: n=374, -0.220 R [-0.328; -0.111], t=-3.33, aciertos 30 % | 115/3123: n=115, -0.323 R [-0.508; -0.137], t=-2.86, aciertos 25 % |
| A_continuacion|mem_k100_mean+0.00 | 360/6416: n=360, -0.176 R [-0.287; -0.065], t=-2.6, aciertos 31 % | 87/3123: n=87, -0.153 R [-0.383; +0.076], t=-1.1, aciertos 29 % |
| A_continuacion|mem_k100_lcb+0.00 | 9/6416: n=9, -0.377 R [-1.098; +0.343], t=-0.86, aciertos 22 % | 1/3123: n=1, +1.976 R , t=None, aciertos 100 % |
| B_reversion|mem_k30_mean+0.00 | 5484/37000: n=5484, -0.239 R [-0.269; -0.210], t=-13.53, aciertos 29 % | 1944/18062: n=1944, -0.228 R [-0.277; -0.180], t=-7.7, aciertos 29 % |
| B_reversion|mem_k60_mean+0.05 | 2257/37000: n=2257, -0.147 R [-0.193; -0.101], t=-5.22, aciertos 31 % | 725/18062: n=725, -0.181 R [-0.261; -0.100], t=-3.71, aciertos 31 % |
| B_reversion|mem_k100_mean+0.00 | 2284/37000: n=2284, -0.109 R [-0.155; -0.063], t=-3.87, aciertos 33 % | 706/18062: n=706, -0.220 R [-0.300; -0.140], t=-4.5, aciertos 30 % |
| B_reversion|mem_k100_lcb+0.00 | 69/37000: n=69, -0.222 R [-0.473; +0.030], t=-1.45, aciertos 29 % | 16/18062: n=16, +0.102 R [-0.478; +0.683], t=0.29, aciertos 44 % |
| C_cambio_tendencia|mem_k30_mean+0.00 | 2623/13853: n=2623, -0.238 R [-0.274; -0.203], t=-11.02, aciertos 33 % | 1067/6461: n=1067, -0.147 R [-0.206; -0.089], t=-4.14, aciertos 35 % |
| C_cambio_tendencia|mem_k60_mean+0.05 | 906/13853: n=906, -0.214 R [-0.276; -0.152], t=-5.73, aciertos 32 % | 337/6461: n=337, -0.115 R [-0.221; -0.010], t=-1.8, aciertos 37 % |
| C_cambio_tendencia|mem_k100_mean+0.00 | 954/13853: n=954, -0.153 R [-0.213; -0.094], t=-4.25, aciertos 35 % | 369/6461: n=369, -0.191 R [-0.288; -0.094], t=-3.24, aciertos 32 % |
| C_cambio_tendencia|mem_k100_lcb+0.00 | 20/13853: n=20, -0.271 R [-0.744; +0.202], t=-0.94, aciertos 25 % | 7/6461: n=7, +0.280 R [-0.564; +1.122], t=0.55, aciertos 57 % |

### Selección prerregistrada → **NO_OPERAR**

Criterio: dev: n>=30, media>0, t>1; val: n>=15, media>0; gana el mayor min(t_dev, t_val).

Opciones que cumplen: 0 de 15. Ninguna cumple, así que el bot NO OPERA con esta combinación.

### Walk-forward anual (k=30, media>0)

- A_continuacion|mem_k30_mean+0.00: 2022: base n=3092, -0.246 R [-0.284; -0.207], t=-10.49, aciertos 28 % → memoria n=540, -0.129 R [-0.224; -0.035], t=-2.26, aciertos 32 %; 2023: base n=2869, -0.430 R [-0.467; -0.392], t=-18.94, aciertos 23 % → memoria n=405, -0.237 R [-0.342; -0.132], t=-3.72, aciertos 30 %; 2024: base n=3123, -0.333 R [-0.370; -0.296], t=-14.68, aciertos 26 % → memoria n=361, -0.155 R [-0.269; -0.040], t=-2.22, aciertos 31 %
- B_reversion|mem_k30_mean+0.00: 2022: base n=16682, -0.279 R [-0.296; -0.262], t=-27.38, aciertos 28 % → memoria n=2803, -0.180 R [-0.222; -0.138], t=-7.12, aciertos 30 %; 2023: base n=17561, -0.427 R [-0.442; -0.411], t=-45.53, aciertos 24 % → memoria n=2515, -0.287 R [-0.329; -0.245], t=-11.22, aciertos 27 %; 2024: base n=18062, -0.369 R [-0.385; -0.354], t=-39.12, aciertos 25 % → memoria n=1945, -0.229 R [-0.278; -0.180], t=-7.72, aciertos 29 %
- C_cambio_tendencia|mem_k30_mean+0.00: 2022: base n=6435, -0.187 R [-0.212; -0.162], t=-12.49, aciertos 33 % → memoria n=1299, -0.198 R [-0.250; -0.146], t=-6.29, aciertos 34 %; 2023: base n=6390, -0.311 R [-0.335; -0.287], t=-21.66, aciertos 30 % → memoria n=1205, -0.263 R [-0.315; -0.211], t=-8.32, aciertos 32 %; 2024: base n=6461, -0.228 R [-0.252; -0.204], t=-15.47, aciertos 32 % → memoria n=1070, -0.150 R [-0.208; -0.091], t=-4.21, aciertos 35 %

### Referencias

- desarrollo: entradas aleatorias n=21515, -0.442 R [-0.456; -0.428], t=-51.44, aciertos 23 %; todas las estructuras n=308808, -0.317 R [-0.321; -0.313], t=-140.04, aciertos 27 %; comprar y mantener +6.0 %
- validacion: entradas aleatorias n=10315, -0.460 R [-0.480; -0.440], t=-37.41, aciertos 22 %; todas las estructuras n=146681, -0.313 R [-0.318; -0.307], t=-95.11, aciertos 27 %; comprar y mantener +24.9 %

### Detalle de `A_continuacion|base` en validacion (ejemplo: no hay estrategia elegida)

- Cartera: 188 ops, neto -989 USD (-9.9 %), PF 0.618, DD máx 10.1 %
- Métricas completas: `{"operaciones": 188, "beneficio_neto": -989.2, "rentabilidad_pct": -9.89, "profit_factor": 0.618, "tasa_aciertos": 0.2713, "expectativa_r": -0.32, "expectativa_r_ic90": [-0.4738, -0.1662], "t_stat": -3.42, "expectativa_dinero": -5.26, "drawdown_max": 1015.97, "drawdown_max_pct": 10.13, "recuperacion_mas_larga_dias": 42.6, "mae_r_mediana": 1.119, "mfe_r_mediana": 0.569, "costes_totales": 1167.82, "lote_medio": 2.93}`
- Señales descartadas por la cartera/riesgo: {'drawdown_total': 2808, 'perdidas_consecutivas': 59, 'sin_margen_perdida_diaria': 37, 'posicion_abierta': 31}
- por sesion: asia: 74 ops, -0.442 R; londres: 66 ops, -0.466 R; ny: 32 ops, +0.030 R; ny_apertura: 14 ops, -0.047 R; tarde: 2 ops, +1.482 R
- por anio: 2024: 188 ops, -0.320 R
- por volatilidad: alta: 94 ops, -0.397 R; baja: 43 ops, -0.408 R; normal: 51 ops, -0.103 R
- por estructura: retest: 188 ops, -0.320 R

Estrés de costes: deslizamiento_x2: 156 ops, neto -996 USD (-10.0 %), PF 0.539, DD máx 10.1 %; deslizamiento_x3: 119 ops, neto -1,002 USD (-10.0 %), PF 0.408, DD máx 10.1 %; spread_x2: 154 ops, neto -991 USD (-9.9 %), PF 0.535, DD máx 10.1 %; spread_historico_real: 93 ops, neto -1,003 USD (-10.0 %), PF 0.248, DD máx 10.1 %

Con el equity real de la demo (543,93 USD): 138 ops, neto -54 USD (-9.9 %), PF 0.492, DD máx 10.1 %; descartes {'drawdown_total': 2886, 'perdidas_consecutivas': 51, 'posicion_abierta': 24, 'sin_margen_perdida_diaria': 21, 'lote_minimo_supera_riesgo': 3}

![equity](equity_M15_M5_M1_select.png)

