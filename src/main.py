"""Punto de entrada único.

  python src/main.py inspeccionar            # entorno, MT5 y especificaciones del símbolo
  python src/main.py datos [--source mt5]    # descarga/actualiza y audita las velas M1
  python src/main.py memoria [--combos 0 1]  # construye la memoria histórica
  python src/main.py investigar --combo 0 --stage select|holdout
  python src/main.py informe                 # regenera reports/RESULTADOS.md
  python src/main.py demo [--once] [--paper] [--allow-orders]
  python src/main.py pruebas                 # ejecuta toda la batería de pruebas
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CMDS = {"inspeccionar": "scripts/inspect_env.py", "datos": "scripts/download_data.py", "memoria": "scripts/build_memory.py",
        "investigar": "scripts/run_research.py", "informe": "scripts/make_report.py", "demo": "scripts/run_demo.py"}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in [*CMDS, "pruebas"]:
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "pruebas":
        sys.exit(subprocess.call([sys.executable, "-m", "pytest", "tests"], cwd=ROOT))
    sys.exit(subprocess.call([sys.executable, str(ROOT / CMDS[sys.argv[1]]), *sys.argv[2:]], cwd=ROOT))
