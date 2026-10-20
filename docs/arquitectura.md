# Arquitectura

```
MT5 (Exness demo) ──► data/providers (MT5Provider | CsvMT5Provider) ──► data/quality (auditoría) ──► caché parquet
                                                                                                   │
                         data/timeframes: M1 → M5, M15, H1, H4 (cada vela con close_time) ◄─────────┘
                                                   │
                indicators (ATR, RSI, volumen relativo, forma de vela, sesión) — causales
                                                   │
                market_structure/engine: pivotes, tendencia, BOS/CHOCH, retesteo, barrido, falsa ruptura,
                                         doble techo/suelo, HCH, FVG, impulso, divergencia RSI
                                                   │
         memory/builder: episodios (+ contexto de temporalidades superiores ya cerradas) → features
                         → desenlaces sobre M1 (backtesting/simulator) → agregados  ──► memory/store (SQLite)
                                                   │
         strategies/rules (A, B, C + exclusiones)  │  similarity/knn (casos comparables madurados)
                         └───────────► strategies/decision (operar / NO OPERAR) ◄──────┘
                                                   │
         risk/manager (tamaño de posición, límites; independiente del modelo)
                                                   │
         backtesting/portfolio + metrics + benchmark ─► reports/  |  execution (paper / demo MT5) ─► logs/
                                                   │
         monitoring/model_registry (versiones, promoción, deterioro, reversión)
```

## Módulos (`src/nsmb/`)

| Carpeta | Qué hace |
|---|---|
| `config/` | carga de YAML; bloquea `mode: live`; especificación del símbolo |
| `data/` | proveedores desacoplados, caché incremental con metadatos, auditoría, remuestreo y alineación sin anticipación |
| `mt5/` | conexión de solo lectura (cuenta, terminal, símbolos, especificaciones, ticks) |
| `indicators/` | indicadores causales |
| `market_structure/` | pivotes y motor de estructuras vela a vela |
| `memory/` | características, construcción de episodios y desenlaces, SQLite con migraciones |
| `similarity/` | vecinos cercanos ponderados con filtro de maduración y deduplicación temporal |
| `strategies/` | reglas A/B/C, exclusiones comunes y motor de decisión con opción NO OPERAR |
| `risk/` | límites, estado de riesgo y tamaño de posición |
| `backtesting/` | simulador M1, cartera, métricas y referencias |
| `execution/` | ejecutor papel/demo con idempotencia, verificación y reconciliación; bucle demo |
| `monitoring/` | registro de versiones del modelo y detección de deterioro |
| `reporting/` | gráficos |

## Combinaciones de temporalidades

`(contexto 1, contexto 2, entrada)`: H4+H1+M15, H1+M15+M5 y M15+M5+M1. La tendencia de contexto se toma de la última
vela de cada temporalidad superior que ya había cerrado cuando cierra la vela de entrada (`align_higher`).
Se evalúan por separado y en orden cronológico; no se cambia de combinación sin evidencia.
