"""Build report charts from Locust CSV files (+ optional resources CSV).

    python scripts/plot_results.py loadtests/results/baseline
"""

import argparse
import csv
import os

import matplotlib.pyplot as plt


def num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def read_rows(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prefix", help="e.g. loadtests/results/baseline")
    args = parser.parse_args()

    rows = [
        r
        for r in read_rows(f"{args.prefix}_stats_history.csv")
        if r["Name"] == "Aggregated"
    ]
    t0 = num(rows[0]["Timestamp"])
    x = [num(r["Timestamp"]) - t0 for r in rows]

    def col(name: str) -> list[float]:
        return [num(r[name]) for r in rows]

    fig, axes = plt.subplots(4, 1, figsize=(11, 12), sharex=True)

    axes[0].plot(x, col("User Count"), color="tab:purple")
    axes[0].set_ylabel("Virtual users")

    axes[1].plot(x, col("Requests/s"), label="RPS", color="tab:green")
    axes[1].plot(x, col("Failures/s"), label="Failures/s", color="tab:red")
    axes[1].set_ylabel("Requests / s")
    axes[1].legend()

    axes[2].plot(x, col("Total Average Response Time"), label="average")
    axes[2].plot(x, col("95%"), label="95th percentile")
    axes[2].set_ylabel("Response time, ms")
    axes[2].legend()

    resources = f"{args.prefix}_resources.csv"
    if os.path.exists(resources):
        res = read_rows(resources)
        rx = [num(r["timestamp"]) - t0 for r in res]
        axes[3].plot(rx, [num(r["cpu_system"]) for r in res], label="CPU system, %")
        axes[3].plot(rx, [num(r["cpu_server"]) for r in res], label="CPU server, %")
        axes[3].plot(rx, [num(r["ram_system"]) for r in res], label="RAM system, %")
        axes[3].legend()
    axes[3].set_ylabel("Resources")
    axes[3].set_xlabel("Time, s")

    for axis in axes:
        axis.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(f"{args.prefix}_charts.png", dpi=120)
    print("Saved", f"{args.prefix}_charts.png")


if __name__ == "__main__":
    main()
