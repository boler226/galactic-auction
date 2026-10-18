"""Sample CPU/RAM once a second into a CSV while a load test runs.

    python scripts/monitor_resources.py --port 8000 --out results.csv
Stop with Ctrl+C.
"""

import argparse
import csv
import time

import psutil


def find_pid(port: int) -> int | None:
    for conn in psutil.net_connections(kind="inet"):
        if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port:
            return conn.pid
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--out", required=True)
    parser.add_argument("--duration", type=int, help="seconds, default: until Ctrl+C")
    args = parser.parse_args()

    pid = find_pid(args.port)
    proc = psutil.Process(pid) if pid else None
    if proc is None:
        print(f"Nothing listens on port {args.port}: only system metrics")
    else:
        proc.cpu_percent(None)
    psutil.cpu_percent(None)

    with open(args.out, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            ["timestamp", "cpu_system", "ram_system", "cpu_server", "ram_server_mb"]
        )
        start = time.time()
        try:
            while args.duration is None or time.time() - start < args.duration:
                time.sleep(1)
                writer.writerow(
                    [
                        round(time.time()),
                        psutil.cpu_percent(None),
                        psutil.virtual_memory().percent,
                        proc.cpu_percent(None) if proc else "",
                        round(proc.memory_info().rss / 1024**2, 1) if proc else "",
                    ]
                )
                file.flush()
        except KeyboardInterrupt:
            pass
    print("Saved", args.out)


if __name__ == "__main__":
    main()
