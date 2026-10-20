"""Fase 6k: backtest profundo de la cartera de apertura de NY, con las reglas congeladas (2026-10-20)

Pedido por John. No se elige ni se ajusta nada: las tres estrategias quedan tal como se definieron antes.
  - ORB 15 min a favor de la media 50 D1 (stop al otro lado del rango, salida 15:57).
  - ORB 5 min (dirección de la 1.ª vela de 5 min, stop en su extremo, objetivo 10 R o 15:57).
  - Noise area (x1, revisión cada 30 min, stop en la banda), con stop de protección en el bróker a 2 medias bandas,
    porque las reglas de riesgo del bot exigen stop obligatorio. Se informa también sin él, para comparar.

Análisis:
  1. Por año, día de la semana, mes, dirección y volatilidad previa (terciles de ATR diario frente a sus 250 días
     anteriores: solo pasado).
  2. Costes: base (spread 1,12 + 0,5 por lado), spread x1,5, spread x2, deslizamiento 1,0, y el peor caso.
  3. Cartera con el motor de riesgo: 0,25 % por operación, máximo 3 posiciones, pérdida diaria 1 % y 3 %,
     lote real de USTECm (mín. 0,05, paso 0,01, 1 USD por punto y lote), con 10.000 y con 544 USD.
  4. Monte Carlo: 10.000 años simulados remuestreando días reales por bloques de 5 días.

Uso: python scripts/run_profundo.py
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_ideas as I  # noqa: E402
import run_web as W  # noqa: E402
from nsmb.backtesting.simulator import M1Arrays  # noqa: E402
from nsmb.config import SymbolSpec, load_settings  # noqa: E402
from nsmb.indicators.core import add_indicators  # noqa: E402
from nsmb.market_structure.engine import StructureEngine, StructureParams  # noqa: E402
from nsmb.reporting.charts import equity_chart  # noqa: E402

SCENARIOS = {"base": (1.12, 0.5), "spread_x1.5": (1.68, 0.5), "spread_x2": (2.24, 0.5), "desliz_1.0": (1.12, 1.0),
             "peor": (2.24, 1.0)}
SEED = 20261020


def build(m1, spec, bias, d1, spread, slip, with_soft=False):
    I.SPREAD_PTS, I.SLIP = spread, slip
    W.COST = spread + 2 * slip
    m = M1Arrays.from_frame(m1, spec.point, True, spread / spec.point)
    ny = m1.index.tz_localize("UTC").tz_convert(I.NY)
    mins = np.asarray(ny.hour * 60 + ny.minute)
    m.flat_mask = (mins >= 957) & (mins < 1110)
    rth = W.rth_frame(m1)
    out = {"orb15": {v["clave"]: v["df"] for v in I.f5_orb(m1, m, bias)}["F5b|rango15m|mercado|stop_otro_lado|fin_dia|media50"],
           "orb5": W.w3_orb5(rth, m, bias, dirs=("ambas",))[0]["df"],
           "noise": W.w1_noise(rth, m, bias, steps=(30,), stops=("banda",), dirs=("ambas",), hard_stop=2.0)[0]["df"]}
    if with_soft:
        out["noise_sin_stop"] = W.w1_noise(rth, m, bias, steps=(30,), stops=("banda",), dirs=("ambas",))[0]["df"]
    cost = spread + 2 * slip
    for k, df in out.items():
        df["risk_pts"] = cost / df["cost_r"]
        if k == "noise":            # el riesgo real al stop de protección es 2 medias bandas
            df["r"] = df["r"] / 2
            df["cost_r"] = df["cost_r"] / 2
            df["risk_pts"] = df["risk_pts"] * 2
        df["estrategia"] = k
    return out


def summary(df: pd.DataFrame) -> dict:
    s = I.by_period(df)
    return {p: {k: s[p].get(k) for k in ("n", "r", "t", "bruto", "aciertos")} for p in I.PERIODS} | {
        "total": {"n": len(df), "r": round(float(df["r"].mean()), 4), "suma_R": round(float(df["r"].sum()), 1)}}


def breakdown(df: pd.DataFrame, key: pd.Series) -> dict:
    g = df.groupby(key)["r"]
    return {str(k): {"n": int(v.count()), "r": round(float(v.mean()), 3), "suma_R": round(float(v.sum()), 1)} for k, v in g}


def vol_tercile(df: pd.DataFrame, d1: pd.DataFrame) -> pd.Series:
    a = add_indicators(d1)["atr"]
    pr = a.rolling(251, min_periods=120).apply(lambda x: (x[:-1] < x[-1]).mean(), raw=True)
    b = pd.DataFrame({"bias_time": d1["close_time"].astype("datetime64[ns]").to_numpy(), "pr": pr.to_numpy()}).dropna()
    x = pd.merge_asof(df[["detected_time"]].reset_index().sort_values("detected_time"), b.sort_values("bias_time"),
                      left_on="detected_time", right_on="bias_time", direction="backward").set_index("index").sort_index()
    return pd.cut(x["pr"], [-0.01, 1 / 3, 2 / 3, 1.01], labels=["baja", "media", "alta"]).astype(str)


def portfolio(trades: pd.DataFrame, equity0: float, risk_pct: float, max_pos: int, daily_cap_pct: float,
              vol_min=0.05, vol_step=0.01, usd_per_pt_lot=1.0) -> tuple[pd.DataFrame, dict]:
    """Simulación por eventos: entradas y salidas ordenadas en el tiempo, equity real, lote redondeado."""
    ev = []
    for i, t in enumerate(trades.itertuples(index=False)):
        ev.append((t.entry_time, 1, i))
        ev.append((t.exit_time, 0, i))
    ev.sort(key=lambda e: (e[0], e[1]))       # en el mismo minuto, primero salidas
    eq, peak, open_, day, day_start = equity0, equity0, {}, None, equity0
    rows, skipped = [], {"lote_minimo": 0, "max_posiciones": 0, "perdida_diaria": 0}
    for ts, kind, i in ev:
        t = trades.iloc[i]
        d = pd.Timestamp(ts).tz_localize("UTC").tz_convert(I.NY).date()
        if d != day:
            day, day_start = d, eq
        if kind == 1:
            if len(open_) >= max_pos:
                skipped["max_posiciones"] += 1
                continue
            if eq <= day_start * (1 - daily_cap_pct / 100):
                skipped["perdida_diaria"] += 1
                continue
            money = eq * risk_pct / 100
            lot = math.floor(money / (t.risk_pts * usd_per_pt_lot) / vol_step + 1e-9) * vol_step
            if lot < vol_min:
                skipped["lote_minimo"] += 1
                continue
            open_[i] = lot
        elif i in open_:
            lot = open_.pop(i)
            pnl = t.r * t.risk_pts * lot * usd_per_pt_lot
            eq += pnl
            peak = max(peak, eq)
            rows.append({"exit_time": t.exit_time, "estrategia": t.estrategia, "lot": lot, "pnl": pnl, "equity": eq,
                         "r": t.r})
    res = pd.DataFrame(rows)
    if res.empty:
        return res, {"operaciones": 0, **skipped}
    e = res.set_index("exit_time")["equity"]
    years = (e.index[-1] - e.index[0]).days / 365.25
    dd = (e / e.cummax().clip(lower=equity0) - 1).min() * 100
    monthly = e.resample("ME").last().ffill()
    mret = monthly.pct_change().fillna(monthly.iloc[0] / equity0 - 1)
    yearly = e.resample("YE").last()
    yret = yearly.pct_change().fillna(yearly.iloc[0] / equity0 - 1)
    return res, {"operaciones": len(res), "equity_final": round(float(eq), 0),
                 "rent_anual_pct": round(((eq / equity0) ** (1 / years) - 1) * 100, 1),
                 "max_dd_pct": round(float(dd), 1), "meses_positivos_pct": round(float((mret > 0).mean() * 100), 0),
                 "peor_mes_pct": round(float(mret.min() * 100), 1),
                 "por_año_pct": {str(k.year): round(float(v * 100), 1) for k, v in yret.items()}, "no_abiertas": skipped}


def monte_carlo(daily_r: pd.Series, risk_pct: float, n_paths=10_000, days=252, block=5) -> dict:
    rng = np.random.default_rng(SEED)
    x = daily_r.to_numpy()
    nb = math.ceil(days / block)
    starts = rng.integers(0, len(x) - block, size=(n_paths, nb))
    paths = np.stack([x[s:s + block] for s in starts.ravel()]).reshape(n_paths, nb * block)[:, :days]
    ret = paths * risk_pct / 100
    eq = np.cumprod(1 + ret, axis=1)
    final = (eq[:, -1] - 1) * 100
    dd = ((eq / np.maximum.accumulate(np.concatenate([np.ones((n_paths, 1)), eq], axis=1)[:, 1:], axis=1)) - 1).min(axis=1) * 100
    q = lambda a, p: round(float(np.percentile(a, p)), 1)  # noqa: E731
    return {"rent_anual_pct": {"p5": q(final, 5), "p25": q(final, 25), "mediana": q(final, 50), "p75": q(final, 75),
                               "p95": q(final, 95)},
            "prob_año_perdedor_pct": round(float((final < 0).mean() * 100), 1),
            "max_dd_pct": {"mediana": q(dd, 50), "p95_peor": q(dd, 5)},
            "prob_dd_peor_10pct": round(float((dd < -10).mean() * 100), 1)}


def main() -> None:
    cfg = load_settings()
    spec = SymbolSpec.from_settings(cfg)
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")
    d1 = I.daily_bars(m1)
    _, st = StructureEngine(StructureParams.from_cfg(cfg["structure"])).run(add_indicators(d1))
    bias = I.daily_bias(d1, st)

    rep = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), "costes": {}}
    base = None
    for name, (sp, sl) in SCENARIOS.items():
        S = build(m1, spec, bias, d1, sp, sl, with_soft=(name == "base"))
        if name == "base":
            base = S
        allt = pd.concat([S[k] for k in ("orb15", "orb5", "noise")], ignore_index=True)
        rep["costes"][name] = {k: summary(v) for k, v in S.items()} | {"cartera": summary(allt)}
        print(name, {k: rep["costes"][name][k]["total"] for k in rep["costes"][name]}, flush=True)

    trades = pd.concat([base[k] for k in ("orb15", "orb5", "noise")], ignore_index=True)
    trades = trades.sort_values("entry_time").reset_index(drop=True)
    ny = trades["detected_time"].dt.tz_localize("UTC").dt.tz_convert(I.NY)
    dias = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
    trades["vol"] = vol_tercile(trades, d1)
    rep["desglose"] = {}
    for k in ("orb15", "orb5", "noise", "cartera"):
        df = trades if k == "cartera" else trades[trades["estrategia"] == k]
        nyk = ny.loc[df.index]
        rep["desglose"][k] = {"año": breakdown(df, nyk.dt.year), "dia": breakdown(df, nyk.dt.dayofweek.map(lambda i: dias[i])),
                              "mes": breakdown(df, nyk.dt.month), "direccion": breakdown(df, df["direction"].map({1: "compra", -1: "venta"})),
                              "volatilidad": breakdown(df, df["vol"])}
    D = trades.groupby([trades["detected_time"].dt.floor("D"), "estrategia"])["r"].sum().unstack(fill_value=0)
    rep["correlacion_diaria"] = D.corr().round(2).to_dict()
    daily = D.sum(axis=1)
    rep["monte_carlo_0.25pct"] = monte_carlo(daily, 0.25)
    rep["cartera_motor_riesgo"] = {}
    out = ROOT / "reports" / "profundo"
    for eq0 in (10_000, 544):
        for cap in (1.0, 3.0):
            res, st_ = portfolio(trades, eq0, 0.25, 3, cap)
            rep["cartera_motor_riesgo"][f"{eq0}usd_perdida_diaria_{cap:g}pct"] = st_
            if eq0 == 10_000 and cap == 3.0 and len(res):
                equity_chart(res, eq0, out / "equity_cartera_10000.png", "cartera de apertura NY, 0,25 % por operación")
    out.mkdir(parents=True, exist_ok=True)
    (out / "profundo.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("monte_carlo_0.25pct", "cartera_motor_riesgo", "correlacion_diaria")},
                     indent=1, ensure_ascii=False, default=str))
    print(json.dumps(rep["desglose"]["cartera"], ensure_ascii=False))
    for k in ("orb15", "orb5", "noise"):
        print(k, json.dumps({x: rep["desglose"][k][x] for x in ("año", "direccion", "volatilidad")}, ensure_ascii=False))
    print(json.dumps({s: {k: v["total"] for k, v in rep["costes"][s].items()} for s in rep["costes"]}, indent=0))
    print(json.dumps({k: {p: v[p] for p in ("dev", "val", "hol")} for k, v in rep["costes"]["base"].items()}, indent=0))


if __name__ == "__main__":
    main()
