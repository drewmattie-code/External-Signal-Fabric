#!/usr/bin/env python3
"""
ESF runnable example: typed signals with provenance, freshness, and reconciliation.
==================================================================================

Demonstrates the core External Signal Fabric mechanic end to end, with no
dependencies (stdlib only). It:

  1. Ingests a stream of external signals as CloudEvents-style envelopes.
  2. Validates each against schema/signal-envelope.v1.json.
  3. Runs the freshness gate: a signal past its freshness window is stale, an
     alarm fires, and it is refused for any decision.
  4. Reconciles two conflicting signals for the same entity (higher confidence,
     then fresher, wins).
  5. Produces a fused output and prints its provenance trail (which signals, at
     which versions and confidence, fed it).

The point: an agent never consumes a raw, unstamped, possibly-stale feed. Every
downstream claim traces back to a specific signal at a specific time. Run:

    python3 examples/fabric.py

License: MIT
"""

import json
import pathlib
import sys
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
SCHEMA = HERE.parent / "schema"

_TYPES = {
    "object": dict, "array": list, "string": str,
    "boolean": bool, "number": (int, float), "integer": int,
}


def validate(instance, schema, path="$"):
    errs = []
    t = schema.get("type")
    if t:
        if t in ("number", "integer") and isinstance(instance, bool):
            return [f"{path}: expected {t}, got boolean"]
        if not isinstance(instance, _TYPES[t]):
            return [f"{path}: expected {t}, got {type(instance).__name__}"]
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: {instance!r} not in {schema['enum']}")
    if t == "object" and isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errs.append(f"{path}: missing required '{req}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errs.append(f"{path}: unexpected property '{key}'")
        for key, sub in props.items():
            if key in instance:
                errs += validate(instance[key], sub, f"{path}.{key}")
    if t == "array" and isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            errs += validate(item, schema["items"], f"{path}[{i}]")
    return errs


# Fixed "now" so the example is reproducible (no wall-clock calls).
NOW = datetime.strptime("2026-06-05T12:00:00Z", "%Y-%m-%dT%H:%M:%SZ")


def age_seconds(sig):
    t = datetime.strptime(sig["time"], "%Y-%m-%dT%H:%M:%SZ")
    return (NOW - t).total_seconds()


def signal(sid, source, etype, time, data, confidence, version, freshness, entity):
    return {
        "specversion": "1.0", "id": sid, "source": source, "type": etype,
        "time": time, "data": data, "confidence": confidence,
        "signalversion": version, "freshnessseconds": freshness, "entity": entity,
    }


def feed():
    return [
        signal("s1", "feed:cme", "ai.spine.esf.commodity.price",
               "2026-06-05T11:59:00Z", {"symbol": "HG", "price": 4.21}, 0.95,
               "2026-06-05.1", 600, "commodity:copper"),
        signal("s2", "feed:portcast", "ai.spine.esf.logistics.congestion",
               "2026-06-05T11:55:00Z", {"port": "LALB", "delay_days": 6}, 0.80,
               "2026-06-05.1", 1800, "port:LALB"),
        # supplier health from two sources for the SAME entity -> reconcile
        signal("s3", "feed:everstream", "ai.spine.esf.supplier.health",
               "2026-06-05T11:40:00Z", {"score": 62}, 0.70,
               "2026-06-05.1", 3600, "supplier:acme"),
        signal("s4", "feed:resilinc", "ai.spine.esf.supplier.health",
               "2026-06-05T11:50:00Z", {"score": 58}, 0.88,
               "2026-06-05.1", 3600, "supplier:acme"),
        # stale: emitted long ago, freshness window already passed
        signal("s5", "feed:weather", "ai.spine.esf.weather.alert",
               "2026-06-05T08:00:00Z", {"region": "Gulf", "severity": "high"}, 0.90,
               "2026-06-05.1", 1800, "region:gulf"),
    ]


def reconcile(signals):
    """Conflicting signals for one entity: higher confidence wins, then fresher."""
    by_entity = {}
    for s in signals:
        by_entity.setdefault(s["entity"], []).append(s)
    chosen = {}
    conflicts = []
    for entity, group in by_entity.items():
        if len(group) > 1:
            conflicts.append(entity)
        winner = sorted(group, key=lambda s: (-s["confidence"], -age_seconds(s)))[0]
        chosen[entity] = winner
    return chosen, conflicts


def main():
    schema = json.loads((SCHEMA / "signal-envelope.v1.json").read_text())
    signals = feed()
    print(f"Ingested {len(signals)} signals.\n")

    # 1) validate envelopes
    bad = 0
    for s in signals:
        errs = validate(s, schema)
        if errs:
            bad += 1
            print(f"  INVALID {s['id']}: {errs[:2]}")
    print(f"Envelope validation: {len(signals) - bad}/{len(signals)} valid "
          f"against signal-envelope.v1.json\n")

    # 2) freshness gate
    fresh, stale = [], []
    for s in signals:
        (stale if age_seconds(s) > s["freshnessseconds"] else fresh).append(s)
    for s in stale:
        print(f"STALE ALARM: {s['id']} from {s['source']} is "
              f"{age_seconds(s):.0f}s old (window {s['freshnessseconds']}s). Refused for decisions.")
    print(f"\nFresh signals usable for decisions: {len(fresh)} of {len(signals)}\n")

    # 3) reconcile conflicts among fresh signals
    chosen, conflicts = reconcile(fresh)
    for entity in conflicts:
        w = chosen[entity]
        print(f"Reconciled conflict on {entity}: kept {w['id']} from {w['source']} "
              f"(confidence {w['confidence']})")

    # 4) fused output with a provenance trail
    print("\nFused supplier-risk view for supplier:acme, with provenance:")
    src = chosen.get("supplier:acme")
    if src:
        print(f"  value: health score {src['data']['score']}")
        print(f"  provenance: signal {src['id']} from {src['source']}, "
              f"version {src['signalversion']}, confidence {src['confidence']}, "
              f"as of {src['time']}")

    ok = bad == 0 and len(stale) == 1 and "supplier:acme" in conflicts
    print(f"\nResult: envelopes valid, 1 stale signal alarmed and excluded, "
          f"1 conflict reconciled. {'OK' if ok else 'CHECK'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
