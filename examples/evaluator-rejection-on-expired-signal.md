# Example: ACS evaluator rejection on expired ESF signal

This shows ESF principles #5 (three-state freshness contract) and #9 (per-fusion degradation declaration) enforced at the commitment boundary by the ACS evaluator.

The scenario: an ACS Generator has produced a commitment ("re-route in-transit inventory through alternate lanes") that depends on an ESF fusion (`lane_risk` from the Red Sea advisory). The Evaluator is checking whether the commitment is safe to seal. One of the underlying ESF signals has expired.

---

## Setup

**Generator's proposed commitment (in `workspace/commitment.md`):**

```markdown
## Commitment — sprint-3: Re-route in-transit inventory

I will issue re-routing instructions for the 38 in-transit SKUs ($4.72M)
currently routed through Red Sea lanes, redirecting them via Cape of Good
Hope. Estimated additional transit: +18 days, +$340K freight cost.

### Source artifacts
- Fusion: lane_risk for customer.acme (2026-05-25T15:02:14Z)
- Fusion degradation_declaration: blocking
- Underlying signal: geopolitical_advisory.RED_SEA (ingested 2026-05-25T15:00:00Z)

### Testable assertions
1. Re-routing instructions sent to TMS within 1 hour
2. New routes confirmed by carrier within 4 hours
3. Customer notified within 30 min
```

**Current time:** 2026-06-04T11:00:00Z (10 days after the geopolitical advisory was ingested).

**Signal freshness check at commitment time:**

```
Signal:           geopolitical_advisory.RED_SEA.transit_advisory
Ingested:         2026-05-25T15:00:00Z
Now:              2026-06-04T11:00:00Z
Age:              9d 20h
Half-life:        7d (per signal_class config)
2 × half-life:    14d
Freshness state:  stale  (age > half_life, but < 2*half_life)
```

---

## Evaluator decision logic

The ACS Evaluator runs this check before sealing the commitment:

```python
def evaluate_commitment(commitment, contract):
    for fusion_ref in commitment.source_fusions:
        fusion = esf.get_fusion(fusion_ref.fusion_id)

        # ESF principle #9: respect per-fusion degradation declaration
        if fusion.degradation_declaration == "blocking":
            for signal_id in fusion.provenance.signal_version_ids:
                signal = esf.get_signal_freshness(signal_id)

                # ESF principle #5: three-state freshness contract
                if signal.freshness_state == "expired":
                    return Reject(
                        reason=f"Blocking fusion {fusion.fusion_class} depends on "
                               f"expired signal {signal_id}",
                        required_action="re_ingest_and_re_fuse"
                    )
                elif signal.freshness_state == "stale":
                    # Stale + blocking is a gray zone. Default: reject and re-fetch.
                    # Tunable per-domain.
                    return Reject(
                        reason=f"Blocking fusion {fusion.fusion_class} depends on "
                               f"stale signal {signal_id}; re-fetch before seal",
                        required_action="re_ingest_and_re_fuse"
                    )

        # degraded or unaffected: do not block on freshness; flag in audit
        elif fusion.degradation_declaration == "degraded":
            for signal_id in fusion.provenance.signal_version_ids:
                signal = esf.get_signal_freshness(signal_id)
                if signal.freshness_state == "expired":
                    commitment.audit_flags.add(
                        f"esf_signal_expired:{fusion.fusion_class}:{signal_id}"
                    )

    return Accept(commitment=commitment)
```

---

## Evaluator response (written to `workspace/critique-log.md`)

```markdown
## Critique — sprint-3 commitment

**Status:** REJECT

**Reason:**
The proposed commitment depends on fusion `lane_risk` (id
f.esf-anchored.lane-risk.2026-05-25T15:02:14Z.b4n7q2), which is declared
`blocking` in its manifest. The underlying signal
`geopol.red-sea.transit.2026-05-25T15:00:00Z.q8t4w6` is in `stale` state
(age 9d 20h, half-life 7d). Per ESF principle #5 and #9, commitments
backed by blocking fusions on stale signals MUST be rejected pending
re-ingestion.

**Required action:**
1. Generator triggers ESF re-ingest of geopolitical_advisory.RED_SEA
   (most recent advisory from the source).
2. ESF re-runs lane_risk fusion with the fresh signal.
3. Generator re-evaluates whether the re-routing decision is still
   warranted given the refreshed advisory state (the situation may
   have changed in 10 days).
4. Generator re-proposes commitment if still warranted; this Evaluator
   re-runs the check.

**Not a critique of the reasoning:**
The Generator's underlying logic (re-route $4.72M of SKUs given an
elevated Red Sea advisory) is sound. The reject is structural, not
substantive. Refresh the signal, recheck the situation, then proceed.
```

---

## What the audit log records

The Evaluator's reject — and its reason — are written to the immutable audit log with the specific signal version ID and fusion ID referenced:

```json
{
  "event_id": "audit.2026-06-04T11:00:15Z.q9w2r4",
  "event_type": "commitment_rejected_by_evaluator",
  "actor": "acs-evaluator@v1.2.0",
  "commitment_id": "commit.acme.sprint-3.2026-06-04T10:58:42Z",
  "rejection_reason": "esf_signal_freshness_stale",
  "fusion_id": "f.esf-anchored.lane-risk.2026-05-25T15:02:14Z.b4n7q2",
  "fusion_degradation_declaration": "blocking",
  "stale_signal_id": "geopol.red-sea.transit.2026-05-25T15:00:00Z.q8t4w6",
  "signal_ingested_at": "2026-05-25T15:00:00Z",
  "signal_freshness_state_at_check": "stale",
  "signal_half_life_seconds": 604800,
  "evaluated_at": "2026-06-04T11:00:15Z"
}
```

This is the data the post-mortem query joins against to answer questions like *"how many commitments did we reject because ESF signals had expired?"* or *"is our Red Sea geopolitical adapter ingesting too slowly?"*

---

## Notes on the example

- **The Evaluator does NOT make the routing decision.** Its job is structural: was the commitment well-founded on still-fresh data? If yes, proceed; if no, reject.
- **The Evaluator's reject is not punitive.** It is the safety mechanism that prevents commitments on stale data. The Generator re-runs after refresh and the work continues.
- **`stale + blocking` is the gray zone.** This example resolves it by rejecting. Some domains may resolve it by accepting with audit flag. The choice is per-domain configuration, not per-commitment judgment.
- **The same enforcement pattern works for `expired + degraded`.** In that case the commitment proceeds, but the audit log records `esf_signal_expired` for post-hoc analysis.
- **Provenance threads end-to-end.** The signal_id in the Generator's proposed commitment is the same signal_id the Evaluator checks freshness on is the same signal_id recorded in the audit log. This is ESF principle #10 in action.
