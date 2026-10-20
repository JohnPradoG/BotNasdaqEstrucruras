"""Fase 6e: métodos avanzados (machine learning y modelos de régimen) frente a modelos simples (2026-10-20).

La rejilla, los hiperparámetros y la regla de selección se guardaron en git ANTES de ejecutar por primera vez.
Hiperparámetros FIJOS (no se ajustan con los resultados).

M1 gbm_H1    Gradient boosting (HistGradientBoostingClassifier: profundidad 3, 200 árboles, tasa 0,05,
             hoja mínima 200, L2 1,0) que estima la probabilidad de que la operación de las próximas h horas suba.
             Características (todas conocidas al cierre de la vela H1): rendimientos de 1, 2, 4, 8 y 24 horas en ATR,
             ATR relativo, distancia a las medias 20/50/100 H1 en ATR, RSI 14 H1, hora, día de la semana,
             rendimiento de la noche y del día en curso, tendencia de estructura H1 y H4 (motor del bot),
             distancia a la media 50 y 200 diaria. Muestras: velas H1 que terminan entre 10:00 y 15:00 NY
             (con h = 3, como tarde 13:00) para que la operación cierre antes de las 16:00.
             Entrena cada mes con todo lo anterior cuya etiqueta ya se conocía (purga), predice el mes siguiente.
             h {1, 3} x margen {0,02, 0,05} sobre 0,5 x {ambas direcciones, solo compras}               8
M1b logit_H1 Igual con regresión logística (modelo simple de referencia)                                8
M2 gbm_D1    Igual en velas diarias: decide al cierre de las 17:00 NY, compra/venta en la apertura siguiente y
             cierra al cierre de ese día (no cruza el cierre diario: sin swap). Características: rendimientos
             de 1, 2, 5, 10 y 20 días en ATR, distancia a medias 20/50/200, RSI 2 y 14, ATR relativo, día de la
             semana, día del mes. margen {0,02, 0,05} x {ambas, solo compras}                               4
M2b logit_D1 Igual con regresión logística                                                                 4
M3 hmm_D1    Modelo oculto de Markov gaussiano (rendimiento diario y rango en log) con {2, 3} estados,
             reestimado cada mes con datos pasados; probabilidad FILTRADA (solo pasado) del estado con mayor
             rendimiento medio en entrenamiento. Posición: compra si esa probabilidad > 0,6;
             {compra/fuera, compra/venta (vende si la del peor estado > 0,6)}; posición mantenida con swap   4
                                                                                                 Total = 28
Costes, periodos, unidad (pb) y regla de selección: los de scripts/run_quant.py (desarrollo n >= 100, media > 0,
t >= 2; validación n >= 50, media > 0, t >= 1). Bonferroni con todas las variantes de 6c, 6d y 6e.
Las predicciones empiezan en 2022-07 (antes no hay suficiente historia para entrenar).

Uso: python scripts/run_ml.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_quant as Q  # noqa: E402
from nsmb.config import load_settings  # noqa: E402
from nsmb.indicators.core import add_indicators, atr, rsi  # noqa: E402
from nsmb.market_structure.engine import StructureEngine, StructureParams  # noqa: E402

warnings.filterwarnings("ignore")
START_PRED = pd.Timestamp("2022-07-01")
N_PREVIOUS = 164 + 73
SEED = 20261020


def gbm():
    return HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.05, min_samples_leaf=200,
                                          l2_regularization=1.0, random_state=SEED)


def logit():
    return make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))


def walk_forward(X: pd.DataFrame, y: pd.Series, t_sig: pd.Series, t_label: pd.Series, make) -> pd.Series:
    """Probabilidades fuera de muestra: para cada mes desde START_PRED, entrena con muestras cuya etiqueta se
    conocía antes del inicio del mes y predice las señales de ese mes."""
    p = pd.Series(np.nan, index=X.index)
    months = pd.date_range(START_PRED, t_sig.max() + pd.offsets.MonthBegin(1), freq="MS")
    for a, b in zip(months[:-1], months[1:]):
        tr = (t_label < a) & y.notna()
        te = (t_sig >= a) & (t_sig < b)
        if te.sum() == 0 or tr.sum() < 300:
            continue
        mdl = make().fit(X[tr].fillna(0).to_numpy(), y[tr].to_numpy().astype(int))
        p[te] = mdl.predict_proba(X[te].fillna(0).to_numpy())[:, 1]
    return p


# ---------------------------------------------------------------------------------------------------------------
def h1_dataset(m1: pd.DataFrame, d: pd.DataFrame, cfg: dict):
    g = m1.resample("60min", label="left", closed="left")
    h = g.agg({"open": "first", "high": "max", "low": "min", "close": "last", "tickvol": "sum", "spread": "median"})
    h["n"] = g["close"].count()
    h = h[h["n"] >= 30].copy()
    h["close_time"] = h.index + pd.Timedelta(hours=1)
    h["complete"] = True
    hi = add_indicators(h)
    sp = StructureParams.from_cfg(cfg["structure"])
    _, st1 = StructureEngine(sp).run(hi)
    g4 = m1.resample("240min", label="left", closed="left", origin="epoch")
    h4 = g4.agg({"open": "first", "high": "max", "low": "min", "close": "last", "tickvol": "sum", "spread": "median"})
    h4 = h4[g4["close"].count() > 0].copy()
    h4["close_time"] = h4.index + pd.Timedelta(hours=4)
    _, st4 = StructureEngine(sp).run(add_indicators(h4))
    tr4 = pd.Series(st4["trend"].to_numpy(float), index=h4["close_time"].to_numpy()).sort_index()
    ny = h.index.tz_localize("UTC").tz_convert(Q.NY)
    hr = np.asarray(ny.hour)
    a = hi["atr"]
    X = pd.DataFrame(index=h.index)
    for k in (1, 2, 4, 8, 24):
        X[f"ret{k}"] = (h["close"] - h["close"].shift(k)) / a
    X["atr_rel"] = hi["atr_rel"]
    for n in (20, 50, 100):
        X[f"sma{n}"] = (h["close"] - h["close"].rolling(n).mean()) / a
    X["rsi14"] = hi["rsi"]
    X["hora"], X["dia"] = hr, np.asarray(ny.weekday)
    X["trend_h1"] = st1["trend"].to_numpy(float)
    X["trend_h4"] = tr4.reindex(h["close_time"].to_numpy(), method="ffill").to_numpy()
    # día de trading y medias diarias del último día cerrado
    tday = (ny + pd.Timedelta(hours=7)).tz_localize(None).normalize()
    prev = pd.DatetimeIndex(tday) - pd.Timedelta(days=1)
    dc = d["close"]
    for n in (50, 200):
        s = ((dc - dc.rolling(n).mean()) / d["atr"]).reindex(prev, method="ffill").to_numpy()
        X[f"d1_sma{n}"] = s
    prev_close = dc.reindex(prev, method="ffill").to_numpy()
    X["ret_dia"] = (h["close"].to_numpy() - prev_close) / a.to_numpy()
    open_930 = h["open"].where(hr == 9).groupby(np.asarray(ny.tz_localize(None).normalize())).transform("first")
    X["noche"] = (open_930.to_numpy() - prev_close) / a.to_numpy()
    X.loc[hr < 10, "noche"] = np.nan
    return h, X, hr, np.asarray(ny.tz_localize(None).normalize())


def h1_labels(h: pd.DataFrame, hr: np.ndarray, date: np.ndarray, hold: int):
    """Muestra i: vela H1 que termina entre 10:00 y (16 - hold):00 NY. Operación: apertura de i+1 -> cierre de i+hold."""
    n = len(h)
    o, c = h["open"].to_numpy(), h["close"].to_numpy()
    idx = h.index
    ok = np.zeros(n, bool)
    entry = np.full(n, np.nan)
    exit_ = np.full(n, np.nan)
    t_lab = np.full(n, np.datetime64("NaT", "ns"), dtype="datetime64[ns]")
    for i in range(n - hold):
        if not (9 <= hr[i] <= 15 - hold):
            continue
        j, e = i + 1, i + hold
        if date[j] != date[i] or date[e] != date[i] or hr[j] != hr[i] + 1 or hr[e] != hr[i] + hold:
            continue
        ok[i] = True
        entry[i], exit_[i] = o[j], c[e]
        t_lab[i] = np.datetime64(idx[e] + pd.Timedelta(hours=1), "ns")
    y = pd.Series(np.where(ok, (exit_ > entry).astype(float), np.nan), index=idx)
    return ok, entry, exit_, pd.Series(t_lab, index=idx), y


def trades_from_prob(p: pd.Series, ok, entry, exit_, idx, hold, margin, dirs):
    rows, busy = [], None
    pv = p.to_numpy()
    for i in np.flatnonzero(ok & np.isfinite(pv)):
        if busy is not None and idx[i] < busy:
            continue
        d = 1 if pv[i] > 0.5 + margin else (-1 if pv[i] < 0.5 - margin else 0)
        if d == 0 or (dirs == "solo_compras" and d < 0):
            continue
        rows.append((idx[i], d, entry[i], exit_[i], idx[i] + pd.Timedelta(hours=1), idx[i] + pd.Timedelta(hours=hold, minutes=59)))
        busy = idx[i] + pd.Timedelta(hours=hold)
    if not rows:
        return pd.DataFrame(columns=["detected_time", "r", "bruto_r"])
    a = list(zip(*rows))
    return Q.trades_frame(a[0], np.array(a[1]), np.array(a[2]), np.array(a[3]), a[4], a[5])


# ---------------------------------------------------------------------------------------------------------------
def d1_dataset(d: pd.DataFrame):
    c, a = d["close"], d["atr"]
    X = pd.DataFrame(index=d.index)
    for k in (1, 2, 5, 10, 20):
        X[f"ret{k}"] = (c - c.shift(k)) / a
    for n in (20, 50, 200):
        X[f"sma{n}"] = (c - c.rolling(n).mean()) / a
    X["rsi2"], X["rsi14"] = d["rsi2"], rsi(c, 14)
    X["atr_rel"] = d["atr_rel"]
    X["dia"], X["dia_mes"] = d.index.weekday, d.index.day
    o_next, c_next = d["open"].shift(-1), c.shift(-1)
    y = (c_next > o_next).astype(float).where(c_next.notna())
    t_sig = pd.Series(d.index, index=d.index)
    t_lab = pd.Series(d.index, index=d.index).shift(-1)      # la etiqueta se conoce al cierre del día siguiente
    return X, y, t_sig, t_lab.fillna(pd.Timestamp("2100-01-01")), o_next, c_next


def d1_trades(p, d, o_next, c_next, margin, dirs):
    pv = p.to_numpy()
    dd = np.where(pv > 0.5 + margin, 1, np.where(pv < 0.5 - margin, -1, 0))
    if dirs == "solo_compras":
        dd = np.maximum(dd, 0)
    dd = np.where(np.isfinite(pv), dd, 0)
    nxt = pd.Series(d.index, index=d.index).shift(-1)
    df = Q.trades_frame(nxt.to_numpy(), dd, o_next.to_numpy(), c_next.to_numpy(), nxt.to_numpy(), nxt.to_numpy())
    return df


def hmm_positions(d: pd.DataFrame, n_states: int, mode: str) -> pd.Series:
    from hmmlearn.hmm import GaussianHMM
    r = np.log(d["close"] / d["close"].shift(1))
    rg = np.log(d["high"] / d["low"])
    F = pd.DataFrame({"r": r * 100, "rg": rg * 100}).dropna()
    pos = pd.Series(0.0, index=d.index)
    months = pd.date_range(START_PRED, d.index.max() + pd.offsets.MonthBegin(1), freq="MS")
    for a, b in zip(months[:-1], months[1:]):
        tr = F[F.index < a]
        if len(tr) < 150:
            continue
        mdl = GaussianHMM(n_components=n_states, covariance_type="full", n_iter=200, random_state=SEED).fit(tr.to_numpy())
        best, worst = int(np.argmax(mdl.means_[:, 0])), int(np.argmin(mdl.means_[:, 0]))
        days = F[(F.index >= a) & (F.index < b)].index
        for t in days:
            seq = F[F.index <= t].to_numpy()[-500:]           # filtrado: la última fila solo usa el pasado
            pr = mdl.predict_proba(seq)[-1]
            if pr[best] > 0.6:
                pos[t] = 1.0
            elif mode == "compra_venta" and pr[worst] > 0.6:
                pos[t] = -1.0
    return pos


def main() -> None:
    cfg = load_settings()
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")
    d = Q.daily_bars(m1)
    V = []

    h, X, hr, date = h1_dataset(m1, d, cfg)
    print("H1", X.shape, flush=True)
    for hold in (1, 3):
        ok, entry, exit_, t_lab, y = h1_labels(h, hr, date, hold)
        Xs = X[ok]
        t_sig = pd.Series(h.index[ok], index=Xs.index)
        for name, make in (("gbm", gbm), ("logit", logit)):
            p = walk_forward(Xs, y[ok], t_sig, t_lab[ok], make).reindex(h.index)
            for margin in (0.02, 0.05):
                for dirs in ("ambas", "solo_compras"):
                    fam = "M1_gbm_H1" if name == "gbm" else "M1b_logit_H1"
                    V.append((fam, f"{fam}|{hold}h|margen{margin}|{dirs}",
                              trades_from_prob(p, ok, entry, exit_, h.index, hold, margin, dirs)))
            print(name, hold, "h listo", flush=True)

    Xd, yd, ts, tl, o_next, c_next = d1_dataset(d)
    for name, make in (("gbm", gbm), ("logit", logit)):
        p = walk_forward(Xd, yd, ts, tl, make)
        for margin in (0.02, 0.05):
            for dirs in ("ambas", "solo_compras"):
                fam = "M2_gbm_D1" if name == "gbm" else "M2b_logit_D1"
                V.append((fam, f"{fam}|margen{margin}|{dirs}", d1_trades(p, d, o_next, c_next, margin, dirs)))
    print("D1 listo", flush=True)

    for k in (2, 3):
        for mode in ("compra_fuera", "compra_venta"):
            pos = hmm_positions(d, k, mode)
            V.append(("M3_hmm_D1", f"M3|hmm{k}estados|{mode}", Q.daily_series(d["open"], d["close"], pos, d["roll_wd"])))
        print("HMM", k, "listo", flush=True)

    rows = []
    for fam, key, df in V:
        res = Q.by_period(df) if len(df) else {p: {"n": 0} for p in Q.PERIODS}
        r = {"familia": fam, "clave": key}
        for p in Q.PERIODS:
            for kk in ("n", "r", "t", "bruto", "sharpe_anual"):
                if kk in res[p]:
                    r[f"{p}_{kk}"] = res[p][kk]
        r["cumple"] = Q.passes(res)
        rows.append(r)
    tab = pd.DataFrame(rows)
    n_total = N_PREVIOUS + len(tab)
    winners = tab[tab["cumple"]].assign(score=lambda x: x[["dev_t", "val_t"]].min(axis=1)).sort_values("score", ascending=False)
    pos_ = lambda c: int((tab[c].fillna(-1) > 0).sum())  # noqa: E731
    summary = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "version_codigo": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                                text=True).stdout.strip(),
               "variantes": len(tab), "cumplen": len(winners),
               "elegida": winners.iloc[0]["clave"] if len(winners) else "NO_OPERAR",
               "dev_positivas": pos_("dev_r"), "val_positivas": pos_("val_r"),
               "dev_y_val_positivas": int(((tab.dev_r.fillna(-1) > 0) & (tab.val_r.fillna(-1) > 0)).sum()),
               "las_tres_positivas": int(((tab.dev_r.fillna(-1) > 0) & (tab.val_r.fillna(-1) > 0) & (tab.hol_r.fillna(-1) > 0)).sum()),
               "bonferroni": {"variantes_totales_6c_6d_6e": n_total, "t_necesario": round(float(norm.ppf(1 - 0.05 / n_total)), 2)},
               "ganadoras": winners.drop(columns=["score"]).to_dict("records")}
    run_id = f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_ml"
    out = ROOT / "data" / "backtests" / run_id
    out.mkdir(parents=True, exist_ok=True)
    tab.to_csv(out / "variantes.csv", index=False)
    (out / "resumen.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (ROOT / "reports" / "ml.json").write_text(json.dumps({**summary, "tabla": tab.round(4).to_dict("records")},
                                                         indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
    pd.set_option("display.width", 250)
    cols = [c for c in ["clave", "dev_n", "dev_r", "dev_t", "dev_bruto", "val_n", "val_r", "val_t", "hol_n", "hol_r",
                        "hol_t", "hol_bruto", "cumple"] if c in tab]
    print(tab[cols].to_string(index=False))


if __name__ == "__main__":
    main()
