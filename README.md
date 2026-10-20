# nasdaq_structure_memory_bot

Bot de investigación para el Nasdaq 100 (USTECm en Exness, MetaTrader 5) que detecta estructuras de mercado,
guarda **todas** en una memoria histórica con lo que pasó después, busca casos parecidos del pasado y solo
operaría si la expectativa neta de costes, medida sin anticipación, es positiva. Incluye la opción explícita de
**NO OPERAR**.

> **La operativa real está deshabilitada.** La configuración no puede activarla y el ejecutor se niega a funcionar
> con una cuenta que no sea demo. El modo demo, por defecto, solo observa y registra.

## Estado actual

Ver **[reports/RESUMEN.md](reports/RESUMEN.md)**, **[reports/RESULTADOS.md](reports/RESULTADOS.md)** (resultados reales ejecutados) y
**[docs/limitaciones.md](docs/limitaciones.md)** (qué falta antes de pensar en una cuenta real).

**Decisión vigente: NO OPERAR.** La auditoría no encontró errores y ninguno de los 192 ajustes probados pasa la
validación ([docs/auditoria_y_ajustes.md](docs/auditoria_y_ajustes.md)).

## Instalación (Windows)

```
py -3.11 -m venv C:\Users\belly\.venvs\nsmb
C:\Users\belly\.venvs\nsmb\Scripts\python.exe -m pip install -r requirements.txt
```
Versiones exactas probadas: `requirements.lock.txt`. El entorno virtual está fuera de OneDrive a propósito
(miles de archivos que OneDrive no debería sincronizar). `MetaTrader5` es opcional: sin él todo funciona con el CSV
local (`config/settings.yaml → data.csv_m1_path`).

## Comandos (desde la carpeta del proyecto)

Con `PY = C:\Users\belly\.venvs\nsmb\Scripts\python.exe`:

| Qué | Comando |
|---|---|
| Inspeccionar entorno y MT5 | `PY src/main.py inspeccionar` |
| Descargar/actualizar y auditar datos | `PY src/main.py datos --source mt5` (o `--source csv`) |
| Construir la memoria | `PY src/main.py memoria --combos 0 1 2` |
| Backtest + selección (desarrollo y validación) | `PY src/main.py investigar --combo 0 --stage select` |
| Evaluación final (holdout, una vez) | `PY src/main.py investigar --combo 0 --stage holdout` |
| Auditoría del backtest | `PY scripts/audit_backtest.py H4_H1_M15` |
| Ajustes con protocolo prerregistrado | `PY scripts/run_adjustments.py --combo 0` |
| Informe | `PY src/main.py informe` → `reports/RESULTADOS.md` |
| Modo demo (observación) | `PY src/main.py demo` · una vuelta: `--once` · sin MT5: `--paper` |
| Pruebas | `PY src/main.py pruebas` |

Combinaciones: 0 = H4+H1+M15, 1 = H1+M15+M5, 2 = M15+M5+M1.

## Configuración

- `config/settings.yaml`: símbolo y especificación de respaldo, datos, parámetros de los detectores, backtest,
  periodos, memoria. `execution.mode` solo admite `paper` o `demo`.
- `config/risk.yaml`: 0,25 % por operación, 1 % de pérdida diaria, 1 posición, 10 % de drawdown total, 6 pérdidas
  seguidas, 3 errores de ejecución, spread máximo. El modelo no puede tocar estos valores.
- `.env.example`: ruta del terminal y servidor (sin contraseñas).

## Documentación

- [docs/arquitectura.md](docs/arquitectura.md) — módulos y flujo de datos
- [docs/estructuras.md](docs/estructuras.md) — definición exacta de cada estructura y cuándo se conoce
- [docs/memoria.md](docs/memoria.md) — memoria de tres niveles y búsqueda de casos comparables
- [docs/backtesting.md](docs/backtesting.md) — cómo se simula cada operación (costes, stops, huecos)
- [docs/protocolo_estadistico.md](docs/protocolo_estadistico.md) — periodos, selección prerregistrada, intervalos
- [docs/demo_y_registros.md](docs/demo_y_registros.md) — iniciar/detener el modo demo, registros y errores
- [docs/auditoria_y_ajustes.md](docs/auditoria_y_ajustes.md) — búsqueda de errores y ajustes probados
- [docs/limitaciones.md](docs/limitaciones.md) — limitaciones y pasos pendientes

## Estructura

```
config/        settings.yaml, risk.yaml
data/          raw/ processed/ (caché parquet + episodios) backtests/ (cada ejecución)
database/      schema.sql, migrations/, memory.sqlite (no se sube a git)
src/main.py    punto de entrada
src/nsmb/      config, data, mt5, indicators, market_structure, memory, similarity, strategies,
               risk, backtesting, execution, monitoring, reporting
scripts/       inspect_env, download_data, build_memory, run_research, make_report, run_demo
tests/         pruebas automáticas con series sintéticas
reports/ logs/ models/ docs/
```
