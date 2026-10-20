"""Auditoría de posibles errores del backtest: retraso de entrada, tamaño del stop frente al coste, motivos de salida,
movimiento a favor de la señal sin stop, dirección invertida y empates stop/objetivo en la misma vela M1.

Uso: python scripts/audit_backtest.py H4_H1_M15
"""
import sys
import numpy as np
import pandas as pd

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[1])
tag = sys.argv[1] if len(sys.argv) > 1 else "H1_M15_M5"
sys.path.insert(0, ROOT + "/src")
from nsmb.backtesting.simulator import M1Arrays, simulate  # noqa

ep = pd.read_parquet(f"{ROOT}/data/processed/episodes_{tag}.parquet")
print("episodios", ep.shape, ep.status.value_counts().to_dict())
ok = ep[ep.status == "ok"].copy()
m1 = pd.read_parquet(f"{ROOT}/data/processed/USTECm_M1.parquet")
print("M1", m1.shape, m1.index[:2].tolist(), m1.columns.tolist())
m = M1Arrays.from_frame(m1, 0.01, True, 112)

# 1) retraso entre detección y entrada
lag = (pd.to_datetime(ok.entry_time) - pd.to_datetime(ok.detected_time)).dt.total_seconds() / 60
print("\n1) minutos entre cierre de la vela de señal y entrada:", lag.describe()[["min", "50%", "max"]].to_dict(),
      "negativos:", int((lag < 0).sum()))

# 2) tamaño del stop frente al coste
risk_pts = ok.risk_price
print("\n2) stop en puntos de índice: mediana %.2f, p10 %.2f, p90 %.2f; coste fijo 2,12 puntos = %.2f R de mediana"
      % (risk_pts.median(), risk_pts.quantile(.1), risk_pts.quantile(.9), ok.cost_r.median()))

# 3) motivos de salida a 2R
print("\n3) salidas a 2R:", ok.exit_reason_2r.value_counts(normalize=True).round(3).to_dict())

# 4) retorno a favor de la señal tras N minutos, bruto y sin stop (prueba sin modelo de la dirección)
close = m1["close"].to_numpy(float)
idx = np.searchsorted(m.time, pd.to_datetime(ok.entry_time).to_numpy().astype("datetime64[ns]"))
o = m1["open"].to_numpy(float)[idx]
atr = ok.atr.to_numpy()
d = ok.direction.to_numpy()
print("\n4) movimiento medio A FAVOR de la señal (en ATR de la vela de señal), sin costes ni stop:")
rows = []
for mins in (15, 60, 240):
    j = np.minimum(idx + mins, len(close) - 1)
    fwd = (close[j] - o) * d / atr
    ok[f"fwd{mins}"] = fwd
for st, g in ok.groupby("structure_type"):
    rows.append({"tipo": st, "n": len(g), **{f"{x}min": round(g[f"fwd{x}"].mean(), 4) for x in (15, 60, 240)},
                 "t_60": round(g.fwd60.mean() / (g.fwd60.std() / np.sqrt(len(g))), 2)})
print(pd.DataFrame(rows).to_string(index=False))
allf = ok.fwd60
print("todas: media %.4f ATR, t=%.2f" % (allf.mean(), allf.mean() / (allf.std() / np.sqrt(len(allf)))))

# 5) dirección invertida: misma geometría reflejada, bruto (sin spread ni deslizamiento)
m0 = M1Arrays.from_frame(m1, 0.01, True, 0)
rng = np.random.default_rng(1)
samp = ok.sample(min(6000, len(ok)), random_state=1)
res = {"normal": [], "invertida": []}
for e in samp.itertuples():
    i = m0.index_at(e.entry_time)
    entry = m0.open[i]
    r = abs(entry - e.stop)
    for lab, dd in (("normal", e.direction), ("invertida", -e.direction)):
        stop = entry - dd * r
        tr = simulate(m0, i, int(dd), stop, entry + dd * 2 * r, 48 * 5, 0.0)
        if tr is not None:
            res[lab].append(tr.pnl_price / tr.risk_price)
for k, v in res.items():
    v = np.array(v)
    print(f"\n5) {k}: n={len(v)} media bruta {v.mean():+.4f} R  t={v.mean()/(v.std()/np.sqrt(len(v))):.2f}")

# 6) misma vela M1 toca stop y objetivo
both = 0
for e in samp.head(3000).itertuples():
    i = m0.index_at(e.entry_time)
    entry = m0.open[i]
    r = abs(entry - e.stop)
    dd = e.direction
    stop, tgt = entry - dd * r, entry + dd * 2 * r
    tr_c = simulate(m0, i, int(dd), stop, tgt, 240, 0.0, conservative=True)
    tr_o = simulate(m0, i, int(dd), stop, tgt, 240, 0.0, conservative=False)
    if tr_c and tr_o and tr_c.reason != tr_o.reason:
        both += 1
print(f"\n6) casos donde stop y objetivo caen en la misma vela M1: {both} de 3000")
