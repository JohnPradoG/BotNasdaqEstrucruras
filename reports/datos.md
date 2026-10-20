# Auditoría de datos M1

- Símbolo: **USTECm**
- Fuente: `mt5_python` 
- Periodo: 2021-10-27 17:20:00 → 2026-10-20 11:43:00 (hora del servidor = UTC)
- Velas: 1,716,946 (entrada 1,716,946); hash `5e71e736e9cab90a`
- Duplicadas eliminadas: 0; OHLC incoherentes: 0; precios ≤0: 0
- Saltos de rentabilidad extremos (>12 MAD): 4412 (se conservan, solo se marcan)
- Spread (points): mediana 385, p95 567, p99 611, máx 3664
- Velas con volumen de ticks 0: 0

## Huecos

- festivo_o_cierre_largo: 8
- fin_de_semana: 256
- hueco_intradia: 61
- micro_hueco: 212
- pausa_diaria: 742
- pausa_diaria_larga: 321

Huecos largos (>30 min, no fin de semana ni pausa diaria): 56. Muestra:

- 2021-10-27 17:41:00 → 2021-10-28 09:23:00 (15.7 h, hueco_intradia)
- 2021-11-25 17:58:00 → 2021-11-25 23:30:00 (5.53 h, hueco_intradia)
- 2021-11-26 12:43:00 → 2021-11-26 13:17:00 (0.57 h, hueco_intradia)
- 2021-11-26 13:18:00 → 2021-11-26 14:10:00 (0.87 h, hueco_intradia)
- 2021-11-29 15:49:00 → 2021-11-29 16:50:00 (1.02 h, hueco_intradia)
- 2021-12-23 20:58:00 → 2021-12-26 23:30:00 (74.53 h, festivo_o_cierre_largo)
- 2022-01-17 17:58:00 → 2022-01-17 23:30:00 (5.53 h, hueco_intradia)
- 2022-02-08 23:46:00 → 2022-02-09 01:22:00 (1.6 h, hueco_intradia)
- 2022-02-21 17:58:00 → 2022-02-21 23:30:00 (5.53 h, hueco_intradia)
- 2022-03-01 02:08:00 → 2022-03-01 03:50:00 (1.7 h, hueco_intradia)
- 2022-04-14 19:58:00 → 2022-04-17 22:30:00 (74.53 h, festivo_o_cierre_largo)
- 2022-05-30 16:59:00 → 2022-05-30 22:30:00 (5.52 h, hueco_intradia)
- 2022-06-07 08:08:00 → 2022-06-07 09:23:00 (1.25 h, hueco_intradia)
- 2022-06-20 16:59:00 → 2022-06-20 22:30:00 (5.52 h, hueco_intradia)
- 2022-07-04 17:00:00 → 2022-07-04 22:30:00 (5.5 h, hueco_intradia)
- 2022-09-05 16:59:00 → 2022-09-05 22:30:00 (5.52 h, hueco_intradia)
- 2022-11-24 17:59:00 → 2022-11-24 23:30:00 (5.52 h, hueco_intradia)
- 2023-01-16 17:59:00 → 2023-01-16 23:30:00 (5.52 h, hueco_intradia)
- 2023-02-20 17:59:00 → 2023-02-20 23:30:00 (5.52 h, hueco_intradia)
- 2023-03-13 19:58:00 → 2023-03-13 23:30:00 (3.53 h, hueco_intradia)
- 2023-03-16 16:35:00 → 2023-03-16 17:34:00 (0.98 h, hueco_intradia)
- 2023-05-29 16:58:00 → 2023-05-29 22:31:00 (5.55 h, hueco_intradia)
- 2023-06-19 16:58:00 → 2023-06-19 22:05:00 (5.12 h, hueco_intradia)
- 2023-07-03 17:13:00 → 2023-07-03 22:05:00 (4.87 h, hueco_intradia)
- 2023-07-04 16:58:00 → 2023-07-04 22:05:00 (5.12 h, hueco_intradia)

## Velas por año

- 2021: 58,079
- 2022: 330,799
- 2023: 340,765
- 2024: 351,698
- 2025: 351,252
- 2026: 284,353

## Limitaciones

- Solo hay velas M1 (precio BID + spread de la vela). Los ticks históricos del bróker solo existen para fechas recientes (comprobado: 2026-10-19 sí, 2025-06-02 y anteriores no), así que el orden intravela dentro de un minuto es desconocido.
- El spread de cada vela M1 es el que registra MT5 (normalmente el mínimo o el de apertura), no el máximo: los costes reales pueden ser algo mayores.
- No se inventan velas: los huecos se clasifican pero no se rellenan.
