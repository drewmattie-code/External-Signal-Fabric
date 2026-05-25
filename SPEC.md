# External Signal Fabric — Specification

> **Status:** v0.1-draft · Drew Mattie · 2026-05-25
> **License:** [CC BY 4.0](LICENSE-CC-BY-4.0)

This is the full technical specification for the External Signal Fabric pattern. The [README](README.md) is the elevator pitch; this document is the build reference.

---

## 1. Context — what ESF solves

AI agents produce better decisions when they can reason about both the customer's internal state and the relevant external world. Most agent decisions are answerable from internal data alone — invoices, POs, schedules, inventory, contracts. Some are not: a decision about an open PO is materially improved if the agent knows the supplier's current financial health. A routing decision is improved if the agent knows current port dwell and weather. A commodity-exposure analysis is improved if the agent knows the current strip.

**ESF is the architectural pattern for the optional capability that gives AI agents access to external-world signals when the decision warrants it.** ESF is not mandatory — most decisions do not engage ESF. When engaged, ESF provides typed signals, fusions against customer-specific context, freshness contracts, and signal-version provenance.

Four failure modes recur when teams wire external-signal integration into agents naively:

1. **Signal pollution.** Feeds without filtering drown the consumer in irrelevant noise. The agent's context fills with weather data when the question is about supplier financial health.
2. **Stale-signal commitments.** Actions taken on expired data produce confidently wrong decisions. The signal was correct when ingested and wrong when used.
3. **Provenance gaps.** When the agent produces an output that turns out to be wrong, post-mortem can't attribute the failure to a specific signal version.
4. **Commodity trap.** Raw signal feeds are a commodity. Fusions against customer-specific PDS context are the moat. Systems that expose only raw signals build a category Everstream / Resilinc / Project44 / Interos already won.

ESF is the implementation pattern that addresses all four — when teams choose to enable external-signal capabilities for their agents.

---

## 2. The architectural layer

ESF is a peer to PDS, not subordinate. Both feed the Adversarial Coordination Spine (ACS). PDS answers *"what is true inside this customer's four walls?"* ESF answers *"what is true in the world that should change how we interpret what's inside the four walls?"*

```
                    ┌────────────────────────────────────┐
                    │ ACS (Adversarial Coordination)     │
                    │ planner · generator · evaluator    │
                    └──────────┬──────────────┬──────────┘
                               ↓              ↓ (optional pull)
                    ┌──────────────────┐  ┌─────────────────┐
                    │ PDS              │  │ ESF             │
                    │ customer state   │  │ external state  │
                    └──────────┬───────┘  └────────┬────────┘
                               ↓                   ↓
                    ┌──────────────────┐  ┌─────────────────┐
                    │ MCP / customer   │  │ Feed adapters   │
                    │ backends         │  │ commodity · port│
                    └──────────────────┘  │ supplier · geo  │
                                          │ weather · etc.  │
                                          └─────────────────┘
```

Internal structure of ESF:

```
┌─────────────────────────────────────────────────────────────┐
│ EXTERNAL SIGNAL FABRIC                                       │
│                                                              │
│   Feed Adapters → Typed Event Bus → Fusion Workers           │
│         ↓                ↓                ↓                  │
│   Raw signals      Typed signals     Fused signals           │
│   (commodity,      (with source,     (with PDS context,      │
│    port, weather,   timestamp,        as enrichment)         │
│    supplier, geo)   freshness,                               │
│                     provenance)                              │
│                                                              │
│                          ↓                                   │
│                    Subscription Layer                        │
│                          ↓                                   │
│                    Provenance Store ←──── audit reads        │
└─────────────────────────────────────────────────────────────┘
```

Lateral, not sequential. Many feeds, many fusion workers, many consumers. No single path through the fabric.

---

## 3. The 10 principles

### 3.1 — Fusion is the moat, raw signal is the commodity

**Problem.** Anyone can buy a weather API, a commodity-price subscription, a supplier-health feed. Building a system that exposes only raw external signals to agents builds a category Everstream / Resilinc / Project44 / Interos already won. The product is undifferentiated.

**Pattern.** Treat raw Signals and Fusions as distinct primitives. Fusions combine raw signals with customer-specific PDS context to produce decision objects that are not commodity. Examples:

- Raw signal: `port_congestion.LGB.dwell_hours = 8.2` (commodity)
- Fusion: `customer.acme.inbound_at_risk = $4.2M (12 SKUs routed through LGB during dwell spike, 3 of those are below safety-stock threshold per PDS)` (non-commodity)

The Fusion contains the customer-specific reasoning. The raw signal does not.

**Implementation.** Fusion workers are first-class entities in the fabric — separate from Adapters and separate from the Bus. Every Fusion is named, versioned, and has a stable input/output contract.

**Anti-pattern.** Exposing the typed event bus directly to agents without Fusions on top. Agents reason about raw signals, write their own ad-hoc reasoning code, and lose the fusion-as-moat advantage.

---

### 3.2 — Lateral fabric, not sequential spine

**Problem.** Spines have a single path: discover → cache → invoke (PDS) or plan → generate → evaluate (ACS). Trying to force external-signal integration into a spine topology creates artificial bottlenecks and rejects the multi-feed, multi-consumer reality.

**Pattern.** ESF is a *fabric* — many feeds writing into a typed event bus, many fusion workers producing derived signals laterally, many consumers pulling cross-sections. The naming choice is deliberate: "Fabric" is not "Spine." Topology drives vocabulary.

**Implementation.** Bus-shaped backbone (Kafka, Redis Streams, Pulsar). Fusion workers are stateless or selectively stateful, scaling horizontally. Subscriptions are independent — adding a new consumer requires no upstream change.

**Anti-pattern.** Routing all feeds through a single "signal pipeline" that processes them sequentially. Lose parallelism, gain unnecessary coupling, fail to scale past a handful of feeds.

---

### 3.3 — Typed signals with structured payloads

**Problem.** Unstructured feed text (news headlines, weather PDFs, free-form geopolitical advisories) reaching downstream consumers forces every consumer to redo the same parsing work. Errors multiply. Provenance is impossible.

**Pattern.** Every Signal entering the bus is typed and structured. Required fields:

| Field | Purpose |
|---|---|
| `signal_id` | Unique version ID for this specific datapoint |
| `signal_class` | Type (e.g., `port_congestion`, `commodity_price`, `supplier_financial_health`) |
| `source_id` | Which adapter / provider produced it |
| `ingested_at` | UTC timestamp of ingestion |
| `confidence` | 0–1 or band (`high`/`medium`/`low`) |
| `half_life_seconds` | Per-class freshness window |
| `payload` | Structured fields specific to the signal class |

Unstructured-to-structured conversion happens at the Adapter, never downstream.

**Implementation.** Schema registry (e.g., Confluent Schema Registry, JSON Schema, CloudEvents-conformant envelopes). Adapters are responsible for normalizing source-specific formats into the canonical typed shape. Reject malformed signals at adapter ingress with a visible alert.

**Anti-pattern.** Passing through unstructured feed content with the expectation that downstream consumers (or worse, the LLM) will parse it. Loses provenance, loses validation, multiplies failure modes.

---

### 3.4 — Push subscriptions, not poll

**Problem.** Polling-based access requires consumers to know when to ask. Consumers either over-poll (wasted compute, latency penalty) or under-poll (missed deltas, stale decisions). Either way, the consumer's context window fills with poll responses unrelated to the current question.

**Pattern.** Consumers subscribe to signal classes relevant to their current workstream. The fabric pushes deltas as they occur. ACS planners declare their subscriptions at session start; the fabric pushes only relevant signals into the planner's working state.

**Implementation.** Consumer groups (Kafka), pub-sub channels (Redis Streams), or webhook delivery for distant consumers. Subscriptions are by `signal_class` (and optionally by filter predicates within the class — e.g., subscribe to `port_congestion` for `port_id IN (LGB, OAK, LAX)`).

**Anti-pattern.** Exposing a `get_current_signal_state()` synchronous query that consumers call in a loop. Couples consumer latency to the entire fabric and pollutes consumer context windows.

---

### 3.5 — Three-state freshness contract

**Problem.** External signals have wildly different decision-relevance lifetimes. A port-congestion datapoint is meaningful for hours; a supplier financial-health datapoint is meaningful for weeks; a commodity price tick is meaningful for minutes. A consumer that doesn't know how fresh a signal is can't decide whether to act on it.

**Pattern.** Every Signal exposes a three-state freshness keyed to a per-class half-life:

| State | Definition | Consumer behavior |
|---|---|---|
| `live` | `age < half_life` | Use freely |
| `stale` | `half_life ≤ age < 2 * half_life` | Use with caveat; surface staleness to the human/log |
| `expired` | `age ≥ 2 * half_life` | MUST NOT be used to back a commitment |

When a commitment depends on an ESF signal, the consumer MUST check the signal's freshness state. Expired signals MUST NOT be used for commitments. The ACS evaluator enforces this at the commitment boundary.

**Implementation.** Half-life values are part of the signal-class definition, not per-signal. Examples:

| Signal class | Half-life | Rationale |
|---|---|---|
| `commodity_price_tick` | 60 seconds | Markets move continuously |
| `port_congestion` | 4 hours | Dwell changes over hours, not minutes |
| `supplier_financial_health` | 30 days | D&B / quarterly-filing cadence |
| `geopolitical_advisory` | 7 days | News-cycle decay |
| `weather_forecast_24h` | 6 hours | Forecast refresh cadence |

Half-life tuning is empirical — adjust based on observed false-positive rate of commitments backed by stale signals.

**Anti-pattern.** Treating all signals as "fresh forever" or all signals as "always-recheck." Both lose to per-class half-lives.

---

### 3.6 — Bidirectional fusion triggers

**Problem.** A single fusion-trigger pattern misses half the meaningful fusions. PDS-anchored fusion alone misses fusions that should fire when the world changes. ESF-anchored fusion alone misses fusions that should fire when a customer fact gets surfaced.

**Pattern.** Two complementary trigger patterns produce fused decision objects ACS consumes:

| Pattern | Trigger | Flow |
|---|---|---|
| **PDS-anchored fusion** | PDS surfaces a fact (e.g., "open PO with Supplier X") | ESF enriches with relevant external signals (Supplier X's financial health, lead-time trend, region risk) |
| **ESF-anchored fusion** | ESF detects a meaningful external delta (e.g., "Red Sea advisory escalated") | PDS is queried for customer exposure (all in-transit inventory routed through affected lanes) |

Both produce the same artifact shape: a fused decision object with the relevant external signals + the relevant internal facts, with provenance.

**Implementation.** Each Fusion is defined as either PDS-anchored or ESF-anchored (some have both modes). The Fusion's trigger spec includes which side (PDS or ESF) detects the trigger condition and what data the other side is queried for.

**Anti-pattern.** Polling for fusion-relevant conditions instead of triggering. Polling wastes compute and adds latency to the fusion's first-emission time.

---

### 3.7 — Tiered latency budgets

**Problem.** Forcing all signals through the same latency budget either over-provisions (paying realtime cost for batch-tier signals) or under-provisions (forcing realtime-tier signals through hourly batch pipelines).

**Pattern.** Each signal class declares a latency tier:

| Tier | End-to-end p95 budget | Examples |
|---|---|---|
| Realtime | < 1 second | Commodity price ticks, market trades |
| Near-realtime | < 60 seconds | Port dwell updates, weather observations |
| Batch | < 1 hour | Supplier financial-health updates, regulatory filings |

The bus and fusion-worker infrastructure are sized per-tier. Fusions that combine multiple tiers respect the highest (slowest) tier's budget.

**Implementation.** Adapter ingestion rates and bus partition counts are dimensioned per tier. Fusion workers for realtime-tier fusions co-locate with the bus; batch-tier fusions can run on schedule.

**Anti-pattern.** Single global latency target. Either expensive or insufficient; rarely both right.

---

### 3.8 — Tenant-scoped fusion, shared raw signals

**Problem.** Raw external signals are not customer-specific (port dwell at Long Beach is the same fact for every customer). Caching them per-tenant wastes 99% of cache capacity. But Fusions are customer-specific by definition (they depend on PDS context). Sharing them across tenants leaks tenant context.

**Pattern.** Split the cache by primitive type:

| Primitive | Cache scope | Rationale |
|---|---|---|
| Raw Signals | Global (cross-tenant) | The fact about the world is the same for everyone |
| Fusions | Per-tenant | The fact about the customer is tenant-specific |
| Subscriptions | Per-agent-session | The signal-class subscription depends on the workstream |

This mirrors the PDS pattern (shared tool index, per-tenant result cache).

**Implementation.** Two distinct caches with different TTL and eviction strategies. Raw-signal cache is aggressive (large, long TTL). Fusion cache is per-tenant and bounded.

**Anti-pattern.** One cache for everything. Either leaks tenant context or wastes capacity.

---

### 3.9 — Per-fusion degradation declaration

**Problem.** ESF is opt-in. A consumer (ACS planner) may proceed without an expected ESF signal for many decisions. But for some decisions, proceeding without the signal produces a structurally wrong answer. A global policy ("always use ESF" or "ESF is optional") doesn't capture this. The decision must be per-fusion.

**Pattern.** Every Fusion declares its degradation behavior in its manifest:

| Declaration | Consumer behavior when fusion unavailable |
|---|---|
| `blocking` | The decision depends on this fusion. The ACS evaluator MUST reject any commitment that would have used it. |
| `degraded` | The decision benefits from this fusion. Proceed without it; flag the commitment in the audit log with `esf_unavailable: <fusion_name>`. |
| `unaffected` | The decision does not require this fusion. Proceed normally; no audit annotation needed. |

This is the mechanism by which ESF is opt-in *safely*. The fabric does not assert that every decision must consult external signals. It asserts that for *fusions explicitly marked blocking*, expired or absent signals must stop the commitment.

**Implementation.** Declaration is part of the Fusion's static manifest. The ACS evaluator reads the manifest at commitment-check time and enforces.

**Anti-pattern.** Global "ESF on / ESF off" toggles. Loses per-decision nuance and either over-blocks or under-protects.

---

### 3.10 — Signal-version provenance, not signal-class

**Problem.** When an agent's output turns out to be wrong, post-mortem needs to attribute the failure to a specific cause. "We used port-congestion data" is not specific enough — *which* signal? At *what* timestamp? With *what* upstream source revision? Audit at the signal-class level cannot answer these.

**Pattern.** Every Fusion's output carries the specific signal version IDs that produced it. The ACS audit log records those IDs alongside the commitment. Post-mortem queries the provenance store by signal version ID and reconstructs the exact upstream state at decision time.

**Implementation.** Signal version IDs are immutable. The provenance store retains them (and the upstream payload) for the audit-required retention window. Fusion workers thread version IDs through to their output objects. ACS audit-log records reference the version IDs verbatim.

This is the same audit substrate OpenLineage and W3C PROV define for general data lineage, specialized to the signal-fabric case.

**Anti-pattern.** Logging only signal-class (not version-ID). Audit-grade attribution becomes impossible after the upstream data revises.

---

## 4. SLAs and success metrics

| Metric | Target | Rationale |
|---|---|---|
| Realtime signal end-to-end latency (p95) | < 1,000 ms | Bus + adapter + fusion must clear realtime tier |
| Near-realtime signal end-to-end latency (p95) | < 60 s | Most signal classes live here |
| Batch signal cadence variance | < 10% | Predictable schedule for downstream consumers |
| Commitments made on expired ESF signals | 0 | When ESF is engaged, expired signals must not back commitments |
| Signal-version provenance completeness | 100% | Every fusion result references its signal version IDs |
| Subscription delta-loss rate | < 0.01% | Subscriptions are the load-bearing consumer surface |
| Fusion hit rate (per-tenant cache) | > 50% | Cache earns its keep against PDS-fetch cost |
| Raw signal global cache hit rate | > 90% | Raw signals are global; cache aggressively |
| Adapter failure recovery time | < 5 min | Per-adapter circuit breaker + retry |
| Time from adapter onboarding to first fused signal | < 1 day | New feed should not be a quarter-long project |
| Per-fusion `blocking` enforcement rate | 100% | If a fusion is `blocking`, the evaluator must enforce |

---

## 5. Build sequence

ESF is built in the following sequence from skeleton to first reference deployment. Each step depends on the previous one. Pace varies by team and tooling; the sequence does not.

| Step | Deliverable | Why |
|---|---|---|
| 1 | Typed signal schema · one free-feed adapter (NOAA weather) · Redis Streams bus · basic provenance store | Skeleton with one source proves the typing + bus + provenance trio |
| 2 | Second adapter from a different signal class (public commodity feed, e.g. CME settle prices) | Proves bus generality across signal classes |
| 3 | First Fusion worker — PDS-anchored pattern (PDS fact → ESF enrichment) | Proves the moat primitive |
| 4 | Subscription layer · ACS planner subscribes to fusion class · end-to-end trace | Proves the consumer surface |
| 5 | Three-state freshness contract enforced · evaluator rejection on expired blocking-fusion signals | Proves the freshness primitive at the commitment boundary |
| 6 | First paid feed adapter (D&B supplier health or equivalent) · ESF-anchored fusion pattern (delta → PDS query) | Proves the bidirectional trigger pattern |
| 7 | Per-fusion degradation declaration · multi-tenant fusion cache · production-readiness | Production-grade primitives in place |
| 8 | Spec / one-pager / case study | Compounds future adoption |

---

## 6. Anti-patterns to avoid

| Anti-pattern | Why it breaks | What to do instead |
|---|---|---|
| Exposing only raw signals to agents | Builds an Everstream-class category that's commodity, not moat | Fusions as a first-class primitive (principle #1) |
| Single sequential pipeline through all feeds | Cannot scale past a handful of signal classes | Lateral fabric with parallel fusion workers (principle #2) |
| Unstructured feed text reaching consumers | Multiplies parsing errors; destroys provenance | Typed signals at adapter ingress (principle #3) |
| Polling for signal state in a loop | Wastes compute; pollutes consumer context | Push subscriptions (principle #4) |
| Treating signals as "fresh forever" or "always recheck" | Either commits on stale data or wastes fabric capacity | Three-state freshness with per-class half-life (principle #5) |
| Polling for fusion-trigger conditions | Wastes compute; adds latency to fusion-first-emission | Bidirectional triggers (principle #6) |
| Single global latency target across all signal classes | Over-provisions or under-provisions | Tiered latency per signal class (principle #7) |
| One cache for raw signals AND fusions | Either leaks tenant context or wastes capacity | Split: global raw cache, per-tenant fusion cache (principle #8) |
| Global "ESF on / off" toggle | Loses per-decision nuance | Per-fusion degradation declaration (principle #9) |
| Logging signal-class only (not version-ID) | Post-mortem attribution becomes impossible after upstream revision | Signal-version provenance (principle #10) |

---

## 7. Compatibility with existing standards

ESF is compatible with — and built on top of — these standards:

- **Apache Kafka / Confluent / Redpanda** — Typed-stream substrate at the bus layer
- **CloudEvents (CNCF)** — Standard envelope for typed signals
- **Apache Flink / Materialize / Estuary Flow / Tinybird** — Stream processors for fusion-worker implementations
- **OpenLineage** — Data lineage at the signal-fabric scale
- **W3C PROV** — Provenance vocabulary for signal-version attribution
- **OpenTelemetry** — Distributed tracing across adapter → bus → fusion → consumer

ESF is also compatible with the companion specifications in the catalog:

- **PDS (Progressive Discovery Spine)** — ESF is a peer to PDS, not a substitute. PDS resolves customer-internal state; ESF resolves external-world state. Both feed ACS.
- **ACS (Adversarial Coordination Spine)** — ACS consumes from ESF via subscriptions; the ACS evaluator enforces ESF's freshness and degradation contracts at the commitment boundary.

---

## 8. The four-way failure attribution principle

ESF is the third spec in a catalog whose meta-architectural contribution is a complete failure-attribution dictionary. When an agent-driven decision goes wrong, post-mortem can attribute the failure cleanly to one of four sources:

| Attribution | Spec layer that owns it | "Failure looked like..." |
|---|---|---|
| Bad customer data | PDS | Wrong supplier ID returned, stale internal cache, missing record |
| Bad world data | ESF | Expired signal used, mis-tagged advisory, broken adapter |
| Bad reasoning | ACS Planner | Granular plan that assumed conditions that no signal supported |
| Bad evaluation | ACS Evaluator | Rubber-stamped output that violated the negotiated contract |

This dictionary is what the three-spec catalog enables and what no single spec produces alone. Build, measure, and own each attribution surface separately.

---

## 9. References

### Stream substrate

- Apache Kafka, *Event Streaming* ([kafka.apache.org](https://kafka.apache.org/intro))
- Apache Flink, *Event Time and Watermarks* ([nightlies.apache.org](https://nightlies.apache.org/flink/flink-docs-release-1.18/docs/concepts/time/))
- CloudEvents (CNCF), *Spec home* ([cloudevents.io](https://cloudevents.io/))
- Materialize, *Up-to-the-second context* ([materialize.com](https://materialize.com/))
- Estuary Flow, *Right-time data platform* ([estuary.dev](https://estuary.dev/))
- Tinybird, *Get started — concepts* ([tinybird.co](https://www.tinybird.co/docs/get-started/concepts))

### Financial signal fusion

- Bloomberg, *Real-Time Market Data Feed (B-PIPE)* ([professional.bloomberg.com](https://professional.bloomberg.com/products/data/enterprise-catalog/real-time-data-feed/))
- Kensho (S&P Global), *Solutions* ([kensho.com](https://kensho.com/solutions))
- AlphaSense, *Financial Data launch press* ([alpha-sense.com](https://www.alpha-sense.com/press/alphasense-launches-financial-data/))

### Supply-chain visibility

- Everstream Analytics, *Homepage* ([everstream.ai](https://www.everstream.ai/))
- Resilinc, *EventWatchAI / Agentic AI Supply Chain Monitoring* ([resilinc.ai](https://resilinc.ai/products/agentic-ai-supply-chain-monitoring/))
- project44, *Visibility Platform* ([project44.com](https://www.project44.com/platform/visibility/))
- Interos, *Our Software* ([interos.ai](https://www.interos.ai/our-software))

### Provenance & lineage

- OpenLineage, *Home* ([openlineage.io](https://openlineage.io/))
- W3C PROV, *PROV-Overview* ([w3.org](https://www.w3.org/TR/prov-overview/))

### Catalog peers

- Progressive Discovery Spine — [github.com/drewmattie-code/Progressive-Discovery-Spine](https://github.com/drewmattie-code/Progressive-Discovery-Spine)
- Adversarial Coordination Spine — [github.com/drewmattie-code/Adversarial-Coordination-Spine](https://github.com/drewmattie-code/Adversarial-Coordination-Spine)

---

## 10. Versioning

This specification follows semantic versioning. Breaking changes to the conceptual model bump the major version; new principles or refinements bump the minor. Editorial fixes bump the patch.

- **v0.1-draft** — initial draft (2026-05-25). Awaiting field feedback before v1.0 lock.

---

## 11. Author

[Drew Mattie](https://www.linkedin.com/in/drew-mattie-88084826/) · SaaSquach AI Labs (a division of Charles & Roe Inc.) · 2026

ESF was developed at SaaSquach AI Labs (a division of Charles & Roe Inc.) as the third specification in the agent-architecture catalog alongside PDS and ACS. This specification is released as open documentation under [CC BY 4.0](LICENSE-CC-BY-4.0) so the pattern can be adopted, adapted, and built upon — with attribution.
