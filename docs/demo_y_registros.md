# Modo demo, registros y errores

## Antes de empezar

1. MetaTrader 5 instalado en `C:\Program Files\MetaTrader 5` y con sesión iniciada en la cuenta **demo**
   (Exness-MT5Trial11). El bot comprueba `account_info().trade_mode`: con una cuenta real se niega a ejecutarse.
2. En MT5: Herramientas → Opciones → Asesores Expertos → "Permitir trading algorítmico" (solo si se quieren enviar
   órdenes a la demo; para observar no hace falta).
3. Entorno virtual: `C:\Users\belly\.venvs\nsmb` (ver README).

## Iniciar

```
cd nasdaq_structure_memory_bot
C:\Users\belly\.venvs\nsmb\Scripts\python.exe scripts\run_demo.py --once      # un ciclo de prueba
C:\Users\belly\.venvs\nsmb\Scripts\python.exe scripts\run_demo.py             # bucle cada 30 s (observación)
C:\Users\belly\.venvs\nsmb\Scripts\python.exe scripts\run_demo.py --paper     # sin MT5, broker simulado
```

Por defecto el bot **solo observa**: detecta estructuras en la última vela cerrada, aplica la regla elegida y la
memoria, y registra lo que habría hecho. Para enviar órdenes a la demo hace falta `--allow-orders` **y** que
`models/seleccion_<combo>.json` contenga una estrategia (no `NO_OPERAR`).

## Detener

`Ctrl+C` en la consola, o crear el archivo `logs/STOP` (el bucle termina al acabar el ciclo en curso).
Borra `logs/STOP` antes de volver a arrancar.

## Registros

- `logs/demo_AAAAMMDD.jsonl`: una línea JSON por evento: señal detectada (tipo, dirección, stop, estrategias que
  encajan, decisión y respuesta de la memoria), orden enviada y su verificación, reconciliación y errores de ciclo.
- Tabla `execution_journal` de `database/memory.sqlite`: solicitudes y respuestas (una solicitud por señal como máximo).

Para revisar errores: busca `"ciclo": "error"` o `"status": "rejected"` en el `.jsonl`.

## Protecciones activas

Datos con más de 180 s de antigüedad → no se abre nada. Spread por encima de 15 puntos → bloqueo.
Una sola posición. Pérdida diaria 1 %, drawdown total 10 %, 6 pérdidas seguidas, 3 errores de ejecución seguidos.
Posiciones del bot (magic 26102001) que no figuran en el registro → bloqueo de nuevas entradas.
