"""Fase 6o: mejorar el EA FVG de John de forma honesta (2026-10-21). Rejilla y regla guardadas en git ANTES de ejecutar.

Regla: los ajustes se eligen SOLO con 2021-11 a 2023-12 (mayor t, con al menos 100 operaciones). Después se mira
2024-01 a 2026-10 sin tocar nada. Aprobado solo si 2021-23 t >= 2 y 2024-26 > 0 con t >= 1.
(John optimizó en 2024-08..2026-08, pero esta elección no usa esos datos: para ella 2024-26 es fuera de muestra.)

Rejilla (48): dirección {ambas, solo ventas} x sesión {todas, solo NY 9:30-16:00} x objetivo {1,5 R, 2,5 R}
x EMA {50, 80, 200} x hueco mínimo {0,2, 0,3 ATR}. El resto, como en "Pass 195".

Uso: python scripts/run_fvg_john_mejora.py
"""
from __future__ import annotations

import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_fvg_john as F  # noqa: E402
import run_ideas as I  # noqa: E402
from nsmb.backtesting.simulator import M1Arrays  # noqa: E402
from nsmb.config import SymbolSpec, load_settings  # noqa: E402

DEV = ("2021-11-01", "2024-01-01")
TEST = ("2024-01-01", "2026-12-31")


def stats(df, a, b):
    return I.cluster_stats(df[(df["detected_time"] >= a) & (df["detected_time"] < b)])


def main() -> None:
    cfg = load_settings()
    spec = SymbolSpec.from_settings(cfg)
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")
    m = M1Arrays.from_frame(m1, spec.point, False, I.SPREAD_PTS / spec.point)
    m.flat_mask = np.zeros(len(m1), bool)
    fr = F.frames(m1)
    rows = []
    for dirs, ses, rr, ema, gap in itertools.product(("ambas", "ventas"), (False, True), (1.5, 2.5), (50, 80, 200), (0.2, 0.3)):
        df = F.run(m1, m, {"rr": rr, "ema": ema, "min_gap_atr": gap, "sesion_ny": ses}, fr=fr,
                   dirs=(1, -1) if dirs == "ambas" else (-1,))
        d, t = stats(df, *DEV), stats(df, *TEST)
        rows.append({"clave": f"{dirs}|{'NY' if ses else 'todas'}|{rr}R|ema{ema}|gap{gap}", "dev_n": d["n"], "dev_r": d.get("r"),
                     "dev_t": d.get("t"), "test_n": t["n"], "test_r": t.get("r"), "test_t": t.get("t")})
        print(rows[-1], flush=True)
    tab = pd.DataFrame(rows)
    ok = tab[tab["dev_n"] >= 100]
    best = ok.loc[ok["dev_t"].idxmax()].to_dict()
    best["aprobada"] = bool(best["dev_t"] >= 2 and (best["test_r"] or -1) > 0 and (best["test_t"] or 0) >= 1)
    summary = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), "variantes": len(tab), "elegida": best,
               "positivas_en_dev": int((tab["dev_r"] > 0).sum()), "positivas_en_ambos": int(((tab["dev_r"] > 0) & (tab["test_r"] > 0)).sum()),
               "bonferroni_t_48": round(float(norm.ppf(1 - 0.05 / 48)), 2)}
    out = ROOT / "reports" / "fvg_john"
    out.mkdir(parents=True, exist_ok=True)
    (out / "mejora.json").write_text(json.dumps({**summary, "tabla": rows}, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
    print(tab.sort_values("dev_t", ascending=False).head(10).to_string(index=False))


if __name__ == "__main__":
    main()
