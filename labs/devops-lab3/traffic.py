# DVO-L3-7F2A91
"""Run in traffic-probe: new connections exercise Service load balancing."""
import json
import sys
import time
import urllib.request
from collections import Counter

seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 15
deadline = time.monotonic() + seconds
pods = Counter()
versions = Counter()
failures = 0
while time.monotonic() < deadline:
    try:
        request = urllib.request.Request(
            "http://auction/lab/info", headers={"Connection": "close"}
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            data = json.load(response)
        pods[data["pod"]] += 1
        versions[data["version"]] += 1
        print(json.dumps({"time": time.time(), "ok": True, **data}), flush=True)
    except Exception as exc:
        failures += 1
        print(
            json.dumps({"time": time.time(), "ok": False, "error": str(exc)}),
            flush=True,
        )
    time.sleep(0.2)
print(
    json.dumps(
        {
            "summary": True,
            "requests": sum(pods.values()),
            "failures": failures,
            "pods": pods,
            "versions": versions,
        }
    ),
    flush=True,
)
sys.exit(1 if failures else 0)
