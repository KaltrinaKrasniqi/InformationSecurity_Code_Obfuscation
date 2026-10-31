#!/usr/bin/env python3
"""
plot_results.py — generate 3-4 figures from results.csv:
  1. Bar chart: LLM success rate per technique
  2. Scatter:   binary size vs resilience
  3. Heatmap:   technique x attack type (strings vs LLM)
  4. Bar chart: cyclomatic complexity (if available)

Requires: pip install pandas matplotlib
"""
import argparse
from pathlib import Path


def plot_all(csv_path, out_dir):
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use("Agg")  # headless (no GUI)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(csv_path)
    print(f"Read {len(df)} rows from {csv_path}")

    df = df.dropna(subset=["llm_success_pct"])
    if df.empty:
        raise ValueError("No valid LLM results to plot")

    # ---- Figure 1: LLM success rate bar chart ----
    fig, ax = plt.subplots(figsize=(10, 5))
    colors = ["#dc2626" if r > 50 else "#059669" for r in df["llm_success_pct"]]
    ax.bar(df["technique"], df["llm_success_pct"], color=colors)
    ax.set_ylabel("LLM success rate (%)")
    ax.set_title("Figure 1: LLM recovers the secret (lower = better protection)")
    ax.set_ylim(0, 110)
    for i, v in enumerate(df["llm_success_pct"]):
        ax.text(i, v + 2, f"{v:.0f}%", ha="center", fontsize=9)
    plt.xticks(rotation=35, ha="right")
    plt.tight_layout()
    plt.savefig(out_dir / "fig1_llm_success.png", dpi=120)
    plt.close()
    print(f"✓ {out_dir}/fig1_llm_success.png")

    # ---- Figure 3: heatmap technique x attack ----
    fig, ax = plt.subplots(figsize=(10, 3))
    import numpy as np
    data = []
    for _, row in df.iterrows():
        strings_safe = 0 if row["strings_found"] else 1
        llm_safe = 1 if row["llm_success_pct"] == 0 else 0
        data.append([strings_safe, llm_safe])
    data = np.array(data).T  # [attack, technique]
    im = ax.imshow(data, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels(df["technique"], rotation=35, ha="right")
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["'strings' attack", "LLM attack"])
    ax.set_title("Figure 3: Which techniques resist which attack (green = resists)")
    for i in range(2):
        for j in range(len(df)):
            ax.text(j, i, "✓" if data[i, j] else "✗",
                    ha="center", va="center", color="white", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(out_dir / "fig3_heatmap.png", dpi=120)
    plt.close()
    print(f"✓ {out_dir}/fig3_heatmap.png")

    # ---- Figure 4: CC (potency) if column exists ----
    if "cc" in df.columns and df["cc"].notna().any():
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(df["technique"], df["cc"], color="#6366f1")
        ax.set_ylabel("Cyclomatic complexity")
        ax.set_title("Figure 4: Code complexity after obfuscation (higher = more complex)")
        plt.xticks(rotation=35, ha="right")
        plt.tight_layout()
        plt.savefig(out_dir / "fig4_cc.png", dpi=120)
        plt.close()
        print(f"✓ {out_dir}/fig4_cc.png")

    print(f"\nAll figures saved to {out_dir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="results/results.csv")
    ap.add_argument("--out", default="analysis/figures")
    a = ap.parse_args()
    plot_all(a.csv, a.out)


def plot_summary(rows,folder):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from pathlib import Path
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    programs=sorted({r["program"] for r in rows})
    made=0
    for program in programs:
        selected=[r for r in rows if r["program"]==program]
        for mode in sorted({r["mode"] for r in selected}):
            group=[r for r in selected if r["mode"]==mode and r.get("success_rate") is not None]
            if not group:continue
            fig,ax=plt.subplots(figsize=(11,5))
            rates=[r["success_rate"]*100 for r in group]
            ax.bar(range(len(group)),rates,color=["#e69f00" if r["flagged_builds"] else "#0072b2" for r in group])
            low=[(r["success_rate"]-r["ci95"][0])*100 for r in group]
            high=[(r["ci95"][1]-r["success_rate"])*100 for r in group]
            ax.errorbar(range(len(group)),rates,yerr=[low,high],fmt="none",ecolor="black",capsize=3)
            ax.set_xticks(range(len(group)),[r["technique"] for r in group],rotation=35,ha="right")
            ax.set_ylim(0,105);ax.set_ylabel("Secret recovery (%)")
            ax.set_title(f"{program} / {mode} | orange: decompiler warning; bars: descriptive Wilson 95% CI")
            for i,r in enumerate(group):ax.text(i, min(102,rates[i]+2),f"{r['hits']}/{r['valid_runs']}",ha="center",fontsize=8)
            fig.tight_layout();fig.savefig(folder/f"{program}_{mode}_recovery.png",dpi=140);plt.close(fig);made+=1
        cost=[r for r in selected if r["mode"]=="pseudoc" and r.get("checker_ratio") is not None]
        if cost:
            fig,axes=plt.subplots(1,2,figsize=(12,5))
            for ax,key,title in [(axes[0],"size_overhead_pct","Binary size overhead (%)"),(axes[1],"checker_ratio","Checker latency / baseline")]:
                ax.bar(range(len(cost)),[r[key] for r in cost]);ax.set_xticks(range(len(cost)),[r["technique"] for r in cost],rotation=45,ha="right");ax.set_title(title)
            fig.suptitle(program+" | fixed O0, mixed inputs, process startup excluded from checker timing")
            fig.tight_layout();fig.savefig(folder/f"{program}_cost.png",dpi=140);plt.close(fig);made+=1
    if not made:raise ValueError("No valid results yet; failed/missing trials are not zero-percent security results")
