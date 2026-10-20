# Estructuras reconocidas: definiciones exactas

Notación: velas de la temporalidad analizada con índice `t`; `o, h, l, c` = apertura, máximo, mínimo y cierre (precio BID);
`ATR(t)` = ATR de Wilder de 14 velas calculado hasta la vela `t` incluida. "Se conoce en `t`" significa que la señal
solo existe a partir del **cierre** de la vela `t`; la operación hipotética entra en la apertura de la primera vela M1
que empieza en ese instante o después.

Parámetros por defecto en `config/settings.yaml → structure`. Código: `src/nsmb/market_structure/`.

## Pivotes (máximos y mínimos de oscilación)

- **Máximo fractal** en `i`: `h[i] > max(h[i-L..i-1])` y `h[i] >= max(h[i+1..i+R])`, con L = R = 3.
- **Mínimo fractal**: simétrico con `l`.
- **Se conoce en** `i + R` (necesita R velas a la derecha). Nunca antes.
- **Filtro de oscilación**: los pivotes deben alternar máximo/mínimo. Un pivote del mismo tipo que el último solo lo
  sustituye si es más extremo. Un pivote del tipo contrario solo se acepta si se separa del último al menos
  `min_swing_atr` (0,5) ATR.
- **Etiquetas**: HH/LH para máximos (mayor/menor que el máximo anterior) y HL/LL para mínimos.

## Tendencia y rango

- Alcista (+1) si el último máximo es HH y el último mínimo es HL; bajista (−1) si LH y LL; rango (0) en otro caso.
- Se actualiza solo cuando se confirma un pivote.

## BOS y CHOCH

- Nivel vigente = último máximo (o mínimo) de oscilación aceptado y aún no roto.
- **Ruptura alcista** en `t`: `c[t] > nivel + break_buffer_atr·ATR` (por defecto 0): cierre, no mecha.
- Es **CHOCH** si la tendencia antes de la ruptura era la contraria (bajista para una ruptura alcista); en otro caso **BOS**.
- Cada nivel se rompe una sola vez. Invalidación usada para el R: el extremo opuesto de la vela de ruptura.

## Retesteo

- Tras una ruptura alcista del nivel N en `t0`, el primer `t` en (t0, t0+12] con `l[t] ≤ N + 0,25·ATR` y `c[t] > N`.
- Se invalida (no hay retesteo) si antes algún cierre queda por debajo de `N − 0,25·ATR`, o si pasan 12 velas.
- Guarda el origen (`bos` o `choch`) y la profundidad del retroceso. Invalidación: mínimo desde la ruptura.

## Barrido de liquidez (sweep)

- Sobre un máximo vigente no roto: `h[t] > nivel` y `c[t] ≤ nivel` (la mecha supera el nivel, el cierre no).
  Señal bajista. Una sola vez por nivel. Invalidación: `h[t]` (el extremo del barrido).
- Simétrico para mínimos (señal alcista).

## Falsa ruptura

- Tras una ruptura alcista por cierre en `t0`, un cierre de vuelta por debajo del nivel en ≤ 3 velas. Señal bajista.
  Invalidación: el máximo alcanzado desde la ruptura.

## Doble techo / doble suelo

- Al confirmarse un máximo H2 con máximo previo H1: `|H2 − H1| ≤ 0,35·ATR`, separados ≥ 6 velas, y el mínimo entre ambos
  (línea clavicular) al menos 1 ATR por debajo del techo.
- **Confirmación**: cierre por debajo de la línea clavicular antes de `2·(i2 − i1)` velas.
- **Invalidación**: un máximo por encima del techo + 0,35 ATR. Doble suelo: simétrico.

## Hombro-cabeza-hombro (y versión invertida)

- Tres máximos A < B > C con `B − max(A, C) ≥ 0,3·ATR` y `|A − C| ≤ 0,6·ATR`; clavicular horizontal = el menor de los
  mínimos entre A-B y B-C (más conservador que una recta inclinada).
- Confirmación por cierre bajo la clavicular; invalidación por encima de la cabeza.

## Fair Value Gap

- Alcista en `t`: `l[t] − h[t−2] ≥ 0,3·ATR`. Bajista: `l[t−2] − h[t] ≥ 0,3·ATR`. Se conoce al cierre de `t`.
  Invalidación: borde lejano del hueco (`h[t−2]` en el alcista).

## Impulso (desplazamiento)

- `h[t] − l[t] ≥ 1,8·ATR` y cuerpo ≥ 60 % del rango. Dirección = color de la vela. Invalidación: extremo opuesto.

## Divergencia RSI (confirmación auxiliar)

- Al confirmarse un mínimo LL cuyo RSI(14) es mayor que el RSI del mínimo anterior: divergencia alcista, conocida en la
  vela de confirmación del pivote. Simétrico para máximos HH.

## Indicadores auxiliares (todos causales)

ATR y volatilidad relativa (ATR / mediana de las 500 velas previas), RSI, volumen de ticks relativo (vela / mediana de
las 50 previas), forma de vela (cuerpo y mechas), vela de rechazo (mecha ≥ 50 % del rango), fuerza previa
(`(c[t] − c[t−20]) / ATR`) y sesión según la hora de Nueva York (asia, londres, ny_apertura, ny, tarde).

## Lo que NO se implementó (todavía)

- **Triángulos, banderas y cuñas**: no se encontró una definición objetiva lo bastante estable con pivotes fractales;
  no se usan para decidir.
- **Zonas de oferta/demanda**: en investigaciones previas (impulso + order block en `BotNasdaqCambioTendencia`)
  no mostraron ventaja tras el spread; aquí solo existen como FVG e impulsos.
- **Zonas de soporte/resistencia por agrupamiento**: se usan solo de forma indirecta (`room_atr` = distancia al pivote
  opuesto vigente).

## Pruebas

`tests/test_structures.py` comprueba cada detector con series sintéticas cuyo resultado se conoce, y la **ausencia de
anticipación**: los eventos conocidos hasta la vela `k` son idénticos si se añaden velas futuras (invariancia de prefijo).
