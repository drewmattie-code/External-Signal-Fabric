# ESF Claude skills

This directory holds the ESF architectural-consultant skill in a format that drops directly into Claude Code, Codex, Cursor, and other clients that support the skills convention.

## Install for Claude Code

```bash
mkdir -p ~/.claude/skills/esf
cp esf/SKILL.md ~/.claude/skills/esf/SKILL.md
```

Restart your Claude Code session (or run `/help` and confirm the skill appears).

The skill will then activate automatically when you ask architectural questions about external-signal integration, supply-chain risk feeds, signal fusion, freshness contracts, or any of the other triggering contexts described in the SKILL frontmatter.

## What the skill does

It's an architectural consultant, not a code library. When triggered, Claude (or another supporting agent) will:

1. Diagnose which of the four documented external-signal failure modes you're hitting (signal pollution, stale-signal commitments, provenance gaps, commodity trap)
2. Recommend the 2–3 ESF principles that address it
3. Give one concrete next step
4. Link to the full spec for deeper reading

It will NOT install software, pretend to be a runnable library, or recite the whole spec at you. The point is fast diagnosis.

## Composition with PDS and ACS

ESF is one of three specifications in the same architectural catalog. Install all three for the full coverage:

```bash
mkdir -p ~/.claude/skills/pds ~/.claude/skills/esf ~/.claude/skills/acs
curl -fsSL https://raw.githubusercontent.com/drewmattie-code/Progressive-Discovery-Spine/main/dist/skills/pds/SKILL.md \
  -o ~/.claude/skills/pds/SKILL.md
curl -fsSL https://raw.githubusercontent.com/drewmattie-code/External-Signal-Fabric/main/dist/skills/esf/SKILL.md \
  -o ~/.claude/skills/esf/SKILL.md
curl -fsSL https://raw.githubusercontent.com/drewmattie-code/Adversarial-Coordination-Spine/main/dist/skills/acs/SKILL.md \
  -o ~/.claude/skills/acs/SKILL.md
```

## Other clients

The SKILL.md format is portable. Drop it into:

- **Cursor** — `~/.cursor/skills/esf/SKILL.md`
- **Codex** — `~/.codex/skills/esf/SKILL.md`
- Any other agent that supports the SKILL.md / agent-skill convention

For agents that don't natively support the skills convention, the SKILL.md is also readable as a prompt — paste it into a system prompt or context.

## Versioning

The skill version tracks the spec version. Current: v0.1-draft (matches SPEC.md v0.1-draft).

When the spec evolves, the skill evolves with it. Watch this repo for updates.

## Attribution

External Signal Fabric by Drew Mattie · SaaSquach AI Labs (a division of Charles & Roe Inc.) · CC BY 4.0
