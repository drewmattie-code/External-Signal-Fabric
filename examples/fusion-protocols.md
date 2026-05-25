# Example: Bidirectional fusion protocols

This shows ESF principle #6 (bidirectional fusion triggers) end-to-end. Two patterns, both producing the same artifact shape — a fused decision object that ACS consumes.

---

## Pattern A — PDS-anchored fusion

**Trigger.** PDS surfaces a customer fact. ESF enriches it with relevant external signals.

**Use case.** ACS planner is investigating Acme Corp's open POs (PDS workstream). The planner needs to know not just the POs but how much each supplier on those POs is at risk.

### Flow

```
1. ACS planner: get_open_pos(customer=acme)
2. PDS resolves: returns 47 open POs across 12 suppliers
3. PDS detects: 12 distinct suppliers — fan out fusion request to ESF
4. ESF receives: enrich_supplier_health(supplier_ids=[s1, s2, ..., s12])
5. ESF resolves: for each supplier, pull latest supplier_financial_health signal
6. ESF fuses: combines supplier_id + financial_health + the customer's
   total open-PO dollar value with that supplier (from PDS)
7. ESF returns: 12 fused decision objects, one per supplier
8. ACS planner: receives enriched PO list, plans next move
```

### Fused output artifact

```json
{
  "fusion_id": "f.pds-anchored.supplier-exposure.2026-05-25T18:45:00Z.a8d3f1",
  "fusion_class": "supplier_exposure",
  "trigger_pattern": "pds_anchored",
  "anchor_fact": {
    "source": "pds",
    "fact": "customer.acme has 47 open POs across 12 suppliers",
    "pds_query_id": "pdsq.2026-05-25T18:44:58Z.x7d2"
  },
  "enrichment_signals": [
    {
      "signal_id": "dnb.supplier.acme-corp.2026-05-15T12:00:00Z.x9k1m2",
      "signal_class": "supplier_financial_health",
      "freshness_state": "live"
    }
    // ... 11 more
  ],
  "fused_payload": [
    {
      "supplier_duns": "012345678",
      "supplier_name": "Acme Corp",
      "open_po_count": 8,
      "open_po_total_usd": 2350000,
      "paydex_score": 62,
      "paydex_delta_30d": -8,
      "failure_score_class": "moderate-high",
      "exposure_classification": "elevated",
      "_interpretation": "Customer has $2.35M open with this supplier; supplier's Paydex dropped 8 points in 30d to 62 (moderate-high failure risk)"
    }
    // ... 11 more
  ],
  "provenance": {
    "fusion_worker": "supplier-exposure-worker@v1.3.0",
    "pds_query_id": "pdsq.2026-05-25T18:44:58Z.x7d2",
    "signal_version_ids": [
      "dnb.supplier.acme-corp.2026-05-15T12:00:00Z.x9k1m2"
      // ... 11 more
    ]
  },
  "degradation_declaration": "degraded",
  "_note": "If supplier_financial_health signal is missing/expired for a supplier, this fusion proceeds for the others and marks the missing one as 'no-esf-data' in the output. Not blocking."
}
```

---

## Pattern B — ESF-anchored fusion

**Trigger.** ESF detects a meaningful external delta. PDS is queried for customer exposure.

**Use case.** Geopolitical advisory escalates on Red Sea transit. The system needs to alert customers with in-transit inventory routed through affected lanes.

### Flow

```
1. ESF detects: geopolitical_advisory.RED_SEA.transit_advisory=elevated
   (new signal, severity escalated from "moderate")
2. ESF triggers: lane_risk_fusion for advisory.severity >= elevated
3. ESF resolves: which customers have any in-transit inventory tagged
   with affected lanes (Suez, Bab-el-Mandeb)
4. ESF fans out: query PDS for each affected customer
   for_each customer: get_in_transit_inventory(lanes=[Suez, BabElMandeb])
5. PDS returns: for each customer, the SKUs + dollar value + ETA in flight
6. ESF fuses: customer × advisory × in-transit-inventory → lane-risk
   decision object per customer
7. ESF subscribers (ACS planners running on those customers) receive
   pushed deltas
8. ACS planners: plan customer notification, re-routing alternatives
```

### Fused output artifact (one per affected customer)

```json
{
  "fusion_id": "f.esf-anchored.lane-risk.2026-05-25T15:02:14Z.b4n7q2",
  "fusion_class": "lane_risk",
  "trigger_pattern": "esf_anchored",
  "anchor_signal": {
    "signal_id": "geopol.red-sea.transit.2026-05-25T15:00:00Z.q8t4w6",
    "signal_class": "geopolitical_advisory",
    "freshness_state": "live",
    "_delta": "severity escalated from moderate to elevated at 2026-05-25T15:00Z"
  },
  "pds_query": {
    "customer_id": "acme",
    "query": "in_transit_inventory_by_lanes(lanes=[Suez, BabElMandeb])",
    "pds_query_id": "pdsq.2026-05-25T15:02:11Z.r6t1"
  },
  "fused_payload": {
    "customer_id": "acme",
    "affected_lanes": ["Suez", "Bab-el-Mandeb"],
    "advisory_severity": "elevated",
    "advisory_estimated_duration_days_p50": 14,
    "in_transit_skus": 38,
    "in_transit_total_usd": 4720000,
    "expected_delay_days_p50": 9,
    "recommended_action_class": "evaluate_rerouting",
    "_interpretation": "Customer has $4.72M of in-transit inventory across 38 SKUs routed through Red Sea lanes; advisory expected to cause ~9 days delay over 14-day estimated duration"
  },
  "provenance": {
    "fusion_worker": "lane-risk-worker@v0.8.2",
    "trigger_signal_id": "geopol.red-sea.transit.2026-05-25T15:00:00Z.q8t4w6",
    "pds_query_id": "pdsq.2026-05-25T15:02:11Z.r6t1",
    "signal_version_ids": [
      "geopol.red-sea.transit.2026-05-25T15:00:00Z.q8t4w6"
    ]
  },
  "degradation_declaration": "blocking",
  "_note": "If the geopolitical_advisory signal expires before this fusion can be acted on (>2 * half_life), the ACS evaluator MUST reject any commitment depending on this fusion's payload. Re-fetch required."
}
```

---

## Notes on the patterns

- **Both patterns produce the same shape.** ACS consumers cannot tell from the artifact whether it came from a PDS-anchored or ESF-anchored trigger. The `trigger_pattern` field is metadata for audit, not for branching consumer logic.
- **PDS-anchored fusions are usually `degraded`.** Missing one supplier's financial-health signal does not block the whole exposure analysis; it just degrades that supplier's row.
- **ESF-anchored fusions are usually `blocking`.** The whole point of the fusion is the external delta; if the delta signal is expired, the fusion's commitment is invalid.
- **The `signal_version_ids` array is the audit primitive.** When something goes wrong post-hoc, this list is what the audit query joins against the provenance store to reconstruct decision-time state (ESF principle #10).
