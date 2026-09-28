"""QC summary over aligned amudim: python -m page_layout.report [Tractate ...]"""
import json
import sys

import numpy as np

from .run import OUT


def main():
    tracts = [t.replace("_", " ") for t in sys.argv[1:]] or sorted(p.name for p in OUT.iterdir())
    for t in tracts:
        js = [json.loads(p.read_text()) for p in sorted((OUT / t).glob("*.json"))]
        flagged = sum(1 for j in js if j["qc"]["flags"])
        line = f"{t:14s} {len(js):3d} amudim, {len(js) - flagged:3d} clean"
        for s in ("gemara", "rashi", "tosafot"):
            c = [j["qc"][s]["cost_per_word"] for j in js]
            placed = sum(j["qc"][s]["tokens"] - j["qc"][s]["skip_txt"] for j in js)
            line += f" | {s[:3]} cost med {np.median(c):.2f} max {max(c):.2f}, unplaced {sum(j['qc'][s]['skip_txt'] for j in js)}"
        print(line)


if __name__ == "__main__":
    main()
