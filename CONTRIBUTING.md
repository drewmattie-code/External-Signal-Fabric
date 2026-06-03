# Contributing to ESF

Thanks for your interest in the External Signal Fabric specification.

ESF is a **pattern specification**, not a software library. Contributions are most useful in three forms:

## 1. Implementation reports

If you have built an external-signal-fusion system that implements ESF (or pieces of it) in production, an issue or PR describing what worked, what didn't, and what you'd refine is the highest-value contribution. Anonymized is fine. Patterns and surprises matter more than vendor names.

Template: open an issue with title `[Implementation] <one-line summary>` and include:

- Stack (event bus, adapters, fusion workers, provenance store)
- Which signal classes you ingest (commodities, weather, logistics, supplier health, geopolitical, etc.)
- Which of the 10 principles you implemented and which you skipped, and why
- What broke and how you fixed it
- What SLAs you measured against the targets in [SPEC.md](SPEC.md#4-slas-and-success-metrics)
- Particularly valued: failure-mode reports. Which of the four named failure modes did you hit, and what was the fix?

## 2. Pattern refinements and additions

If you find a missing principle, an unhandled failure mode, or a refinement to an existing principle, open an issue first to discuss before sending a PR. The spec is intentionally tight. Every principle has earned its place. New principles need to be load-bearing, not nice-to-have.

Refinements to existing principles are easier: open a PR with the proposed change to [SPEC.md](SPEC.md) and a one-paragraph rationale. Cite implementations or production incidents where possible.

## 3. Examples and reference materials

The [`examples/`](examples/) directory is open to:

- More worked signal manifests for additional signal classes (FX, commodities, regulatory filings, climate, healthcare events)
- Fusion examples for specific domains (financial services, supply chain, energy, retail)
- Implementation sketches in additional languages
- Provenance store schemas
- Subscription / bus configuration examples (Kafka, Redis Streams, Materialize, Estuary Flow)
- Evaluator rejection rules for expired-signal commitments

Keep examples small and concrete. The point is to show the shape; production-grade implementations belong in your own repo.

## What we won't accept

- Vendor advertising: examples that exist primarily to promote a product. Keep examples vendor-neutral; if you need to name a feed provider or bus, use it as one of many examples.
- Speculative principles: additions without an implementation that supports them.
- Cosmetic edits without rationale.

## Style

- Prose: declarative, no fluff. Match the existing voice in [SPEC.md](SPEC.md).
- Diagrams: Mermaid where possible (renders natively in GitHub).
- Code samples: minimal, runnable, no external dependencies beyond `requirements.txt` / `package.json` declarations.
- Markdown: GitHub-flavored. Wrap at natural sentence boundaries, not at fixed columns.

## License agreement

Contributions are accepted under the project's dual license (CC BY 4.0 for prose, MIT for code). By opening a PR, you agree to license your contribution under those terms.

## Reporting issues with the spec

If you think a principle is wrong, please say so directly in an issue. Include the principle number, what's wrong, and what you'd change. The spec is not gospel; it's the current best understanding.

## Relationship to the catalog

ESF is one of eight specifications in the same architectural catalog:

- **PDS (Progressive Discovery Spine)** (public): customer-internal tool / data discovery discipline
- **ACS (Adversarial Coordination Spine)** (public): multi-agent coordination layer
- **ESF (External Signal Fabric)** (public): customer-external signal fabric *(this spec)*
- **CRI (Composite Risk Index)** (private, patent-preservation): composite, cross-layer risk scoring
- **AGS (Agent Governance Spine)** (public): deterministic governance, per-agent identity, tamper-evident audit
- **DCS (Durable Context Spine)** (public): durable state and memory across sessions and time
- **GDS (Grounded Data Spine)** (private, forthcoming): a canonical semantic model (text-to-metric) plus data-level entitlements
- **ARS (Agent Registry Spine)** (private, forthcoming): the inventory substrate, one system of record for every agentic asset that discovery reads from and governance enforces against

ESF is a peer to PDS; both feed ACS. Cross-cutting contributions that touch two or more specs are welcome. Open an issue on the most-affected repo first.

## Contact

Open an issue for anything spec-related. For something that doesn't fit an issue, the author's contact is in the repository About section.
