"""Genera reports/RESULTADOS.md a partir de los JSON de reports/ (solo resultados realmente ejecutados)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "reports"


def f(x, nd=3):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:+.{nd}f}" if abs(x) < 100 else f"{x:,.0f}"
    return str(x)


def rs(d):
    if not d or not d.get("n"):
        return "n=0"
    ic = f"[{f(d.get('lo90'))}; {f(d.get('hi90'))}]" if d.get("lo90") is not None else ""
    return f"n={d['n']}, {f(d.get('exp_r'))} R {ic}, t={d.get('t')}, aciertos {d.get('aciertos', 0) * 100:.0f} %"


def cart(c):
    if not c or not c.get("operaciones"):
        return "sin operaciones"
    return (f"{c['operaciones']} ops, neto {c['beneficio_neto']:+,.0f} USD ({c['rentabilidad_pct']:+.1f} %), PF {c['profit_factor']}, "
            f"DD máx {c['drawdown_max_pct']:.1f} %")


def section(res: dict) -> list[str]:
    L = [f"## {' + '.join(res['combo'])} — etapa `{res['stage']}`", "",
         f"Coste de spread: {res.get('cost_spread_points')} points por operación. Ejecución `{res['run_id']}` (código {res['code_version']}, semilla {res['seed']}, deslizamiento {res['slippage_points']} points/lado, equity inicial {res['initial_equity']:,.0f} USD).", ""]
    periods = list(next(iter(res["reglas_base"].values())).keys())
    L += ["### Reglas base (todas las señales, resultado neto por operación en R)", "",
          "| Regla | " + " | ".join(periods) + " | bruto sin costes (" + periods[-1] + ") | con spread histórico real (" + periods[-1] + ") |",
          "|---|" + "---|" * (len(periods) + 2)]
    for name, v in res["reglas_base"].items():
        L.append(f"| {name} | " + " | ".join(rs(v[p]["todas_las_senales"]) for p in periods)
                 + f" | {rs(v[periods[-1]]['bruto_sin_costes'])} | {rs(v[periods[-1]]['sensibilidad_spread_historico'])} |")
    L += ["", "Cartera (una posición, 0,25 % de riesgo, límites activos):", ""]
    for name, v in res["reglas_base"].items():
        L.append(f"- {name}: " + "; ".join(f"{p}: {cart(v[p]['cartera'])}" for p in periods))
    L += ["", "### Regla + memoria de casos comparables (walk-forward: solo casos ya madurados)", "",
          "| Estrategia · configuración | " + " | ".join(f"{p} (operadas/señales, resultado)" for p in periods) + " |",
          "|---|" + "---|" * len(periods)]
    for key, v in res["memoria"].items():
        L.append(f"| {key} | " + " | ".join(f"{v[p]['operadas']}/{v[p]['senales']}: {rs(v[p]['r'])}" for p in periods) + " |")
    if "seleccion" in res:
        s = res["seleccion"]
        L += ["", f"### Selección prerregistrada → **{s['elegida']}**", "", f"Criterio: {s['criterio']}.", ""]
        ok = [c for c in s["candidatos"] if c["cumple"]]
        L.append(f"Opciones que cumplen: {len(ok)} de {len(s['candidatos'])}." + ("" if ok else " Ninguna cumple, así que el bot NO OPERA con esta combinación."))
    if "seleccion_congelada" in res:
        L += ["", f"### Selección congelada evaluada en el holdout: **{res['seleccion_congelada'].get('elegida')}**"]
    L += ["", "### Walk-forward anual (k=30, media>0)", ""]
    for key, rows in res["walk_forward"].items():
        L.append(f"- {key}: " + "; ".join(f"{y}: base {rs(r['base'])} → memoria {rs(r['memoria'])}" for y, r in rows.items()))
    L += ["", "### Referencias", ""]
    for p, r in res["referencias"].items():
        L.append(f"- {p}: entradas aleatorias {rs(r['entradas_aleatorias_2R'])}; todas las estructuras {rs(r['todas_las_estructuras'])}; comprar y mantener {r['comprar_y_mantener_pct']:+.1f} %")
    fd = res["foco_detalle"]
    L += ["", f"### Detalle de `{fd['clave']}` en {fd['periodo']}" + (" (ejemplo: no hay estrategia elegida)" if res["foco"] == "NO_OPERAR" else ""), "",
          f"- Cartera: {cart(fd['cartera'])}", f"- Métricas completas: `{json.dumps(fd['cartera'], ensure_ascii=False)}`",
          f"- Señales descartadas por la cartera/riesgo: {fd['descartes']}"]
    for lab in ("por_sesion", "por_anio", "por_volatilidad", "por_estructura"):
        if fd[lab]:
            L.append(f"- {lab.replace('_', ' ')}: " + "; ".join(
                f"{list(r.values())[0]}: {r['operaciones']} ops, {r['expectativa_r']:+.3f} R" for r in fd[lab]))
    L += ["", "Estrés de costes: " + "; ".join(f"{k}: {cart(v)}" for k, v in res["estres"].items()),
          "", f"Con el equity real de la demo (543,93 USD): {cart(res['equity_demo_543']['cartera'])}; descartes {res['equity_demo_543']['descartes']}", ""]
    png = f"equity_{'_'.join(res['combo'])}_{res['stage']}.png"
    if (REP / png).exists():
        L += [f"![equity]({png})", ""]
    return L


def main():
    L = ["# Resultados reales de las pruebas ejecutadas", "",
         "Todo lo que aparece aquí sale de ejecuciones reales registradas en `data/backtests/` y en la tabla `experiments`.",
         "Resultado en R = beneficio neto (spread y deslizamiento incluidos) dividido entre el riesgo inicial. IC = intervalo de confianza del 90 %.", ""]
    d = json.loads((REP / "datos.json").read_text(encoding="utf-8"))
    L += ["## Datos", "", f"USTECm M1 {d['start']} → {d['end']}, {d['rows']:,} velas, fuente `{d['source']['provider']}`, hash `{d['hash']}`. Detalle en [datos.md](datos.md).", ""]
    for p in sorted(REP.glob("backtest_*.json")):
        L += section(json.loads(p.read_text(encoding="utf-8")))
    (REP / "RESULTADOS.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("reports/RESULTADOS.md actualizado")


if __name__ == "__main__":
    sys.exit(main())
