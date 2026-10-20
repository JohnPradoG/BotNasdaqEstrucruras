# Memoria histórica y búsqueda de casos parecidos

Código: `src/nsmb/memory/` y `src/nsmb/similarity/`. Base de datos: `database/memory.sqlite` (SQLite, modo WAL).
Esquema vigente en `database/schema.sql`; cambios en `database/migrations/NNN_*.sql`, que `MemoryStore` aplica
automáticamente en orden (tabla `schema_version`).

## Tres niveles

1. **Episodios** (`episodes`): TODAS las estructuras válidas detectadas, se operen o no. Por episodio: id único
   (hash de símbolo, temporalidades, tipo, dirección, instante y parámetros), instante en que se conoce, temporalidades,
   tipo y dirección, niveles (nivel, extremo, protector, invalidación), ATR, spread, sesión, tendencia propia y de
   contexto (expresadas a favor de la dirección: +1 a favor, −1 en contra), características normalizadas
   (`features_json`), confirmaciones presentes (`confirmations_json`) y calidad de los datos.
2. **Desenlaces** (`outcomes`): operación hipotética estándar (ver `docs/backtesting.md`) con MFE y MAE en R y en ATR,
   duración, resultado neto de las salidas 1 R, 1,5 R, 2 R y por tiempo, coste en R y **`matured_time`**: el instante
   en que todos esos desenlaces ya se conocían. Antes de ese instante el episodio no puede usarse para decidir.
3. **Agregados** (`aggregates`): por tipo × temporalidad × dirección, y además por sesión, volatilidad (baja < 0,8,
   normal, alta > 1,25 del ATR relativo) y contexto. Con `n`, `n_eff` (sin solapamientos), aciertos a 2 R con IC de
   Wilson 90 % y expectativa con IC 90 %.

Otras tablas: `datasets` (procedencia y hash de los datos), `model_versions` (versiones del modelo de decisión),
`experiments` (cada ejecución de investigación con su configuración, semilla y versión del código) y
`execution_journal` (solicitudes y respuestas del ejecutor, con índice único por señal para evitar duplicados).

Si el volumen crece (varios símbolos, ticks), la migración natural es PostgreSQL con las mismas tablas: los tipos son
estándar y las consultas no usan funciones propias de SQLite.

## Características (todas conocidas al cierre de la vela de detección)

`trend_tf`, `trend_ctx1`, `trend_ctx2` (tendencias a favor/en contra), `stop_atr` (distancia al stop en ATR),
`room_atr` (distancia al pivote opuesto vigente), `atr_rel` (volatilidad relativa), `rel_vol` (volumen de ticks
relativo), `rsi_d` (RSI centrado a favor), `mom_d` (avance de 20 velas en ATR a favor), `body_ratio`, `wick_d`
(mecha de rechazo a favor), `struct_size_atr` (tamaño propio: ruptura, retroceso, barrido, altura de figura...),
`bars_since` (velas desde la ruptura), `conf_div` (divergencia RSI en las 10 velas previas), `conf_rej`
(vela de rechazo) y la hora de Nueva York codificada en seno y coseno.

## Búsqueda de casos comparables

Un **caso comparable** es un episodio del mismo tipo de estructura y temporalidad, de cualquier dirección (las
características están expresadas a favor de la dirección), cuyo desenlace había madurado antes de la consulta,
y que está entre los k más cercanos según la distancia euclídea ponderada de las características estandarizadas
(mediana y rango intercuartílico del periodo de entrenamiento). Los vecinos separados menos de 30 minutos cuentan
como uno, para no tratar episodios casi idénticos como observaciones independientes.

La respuesta incluye: cuántos casos existen, cuántos vecinos efectivos, proporción que alcanzó el objetivo antes de
invalidarse (IC de Wilson), MAE y MFE típicos, duración típica y expectativa neta (con su IC 90 %). Nunca se usa el
desenlace de un episodio para predecirse a sí mismo (prueba en `tests/test_memory_similarity.py`).

## Comandos

```
python scripts/build_memory.py --combos 0 1 2     # construye/actualiza la memoria
```
