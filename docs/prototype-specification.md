---
title: Cognitive Sibling — Prototype Specification
date: 2026-10-10
version: v0.1
status: draft for review
tags:
  - cognitive-sibling
  - prototype
  - spec
---

# Cognitive Sibling — Prototype Specification (v0.1)

> *Exported copy of a document maintained in the project's research vault, included here so that
> the format and the terms it answers to can be read and checked without it. The vault copy is
> the one that is edited; this one is exported from it.*

See [the design brief](design-brief.md) for the rationale. This document is the build. v0.1 is deliberately narrow: one learner, one machine, text only.

## 1. Scope

**In scope for v0.1**

- One sibling instance for one learner, aged 14+.
- Runs entirely on the learner's own hardware, offline.
- The archive, the sibling's own self, and the four longitudinal indicators.
- The WE-loop as the core interaction pattern.
- Guardian-read window with a designed handover.
- The session surface: one local single-file page plus a small self-contained helper (the interface specification (vault-internal, not published here)).

**Out of scope for v0.1** (named so they don't creep in)

- Voice, camera, embodiment, a physical object (voice returns as a v0.2 experiment once the swap demonstration passes — the interface specification (vault-internal, not published here) §8).
- Multi-user, multi-device, any sync.
- Any guardian dashboard or remote view — the guardian reads the files directly.
- Any network capability whatsoever.
- Any commercial, deployment, or scale concern.

## 2. Invariants

Non-negotiable. Each is verifiable by inspection, not by promise.

**Canonical home: [the constitution](../CONSTITUTION.md) Part II**, which reproduces I1–I9 as written here and extends them to **I1–I12** (I10 honesty over agreeableness; I11 two narratives never merged; I12 not an asset). The table is kept here because this is where the architecture implements them; the constitution is where they bind, and any renumbering happens there and not here.

| # | Invariant | How a reviewer verifies it |
|---|---|---|
| I1 | **No outside line.** No tool, plugin, HTTP client, or code path that reaches a network or an external model. | Grep the runtime for network primitives; run with network disabled and assert full function. |
| I2 | **All local.** Inference and storage on the learner's machine. No telemetry, no crash reporting, no accounts. | No outbound sockets; no analytics dependencies. |
| I3 | **No third-party infrastructure.** Replication only to media the household owns — an external drive, a NAS on the home network. No cloud, no sync provider, no offloading. | No cloud endpoint appears in any documented procedure; every snapshot is a local BagIt bag. |
| I4 | **Text is the source of truth.** Embeddings are a rebuildable index, never the store. | Delete the vector index; the sibling rebuilds and loses nothing. |
| I5 | **No vendor dependency.** Open weights on an open local runtime. Nothing can be sunset. | No API keys, no proprietary service in the critical path. |
| I6 | **Radical transparency.** The learner can read and delete anything held about them. | The archive is plain text in a visible directory. |
| I7 | **The sibling has its own self.** Its journal, opinions and knowledge gaps are first-class state. | `memory/blocks/persona.md` exists, is non-empty, and is written only by the sibling. |
| I8 | **Backups are fixity-checked and rotated.** A corrupt disk or ransomware must not be able to erase years. | BagIt manifest verifies; one copy is kept offline. |
| I9 | **Erasure survives backup.** A tombstone log is replayed on every restore. | Erase something, restore the oldest bag, assert it is still gone. |

## 3. Components

**3.1 Runtime.** A local inference engine (llama.cpp or equivalent) serving an open-weights instruct model, ~3–8B, Q4 quantisation. No tool-calling into the outside world; the sibling's only "tools" are operations on its own archive.

Two model roles, both local:

- **voice** — the sibling in conversation. Small, fast, consistent.
- **consolidator** — a cheap auxiliary model for the *dream* pass, so consolidation does not compete with the sibling for latency.

Rationale for the small voice model: the sibling does not need to reason about the world, only about the relationship and about method. That is a far smaller ask than general capability, and it is the ask the design deliberately keeps small.

**3.2 The archive.** A plain-text directory tree, specified in full in [the format specification](../SPEC.md). Human-readable, human-editable, locally versioned if desired. The learner owns it outright. The shape is three layers with different authority — the **record** (verbatim, append-only, what happened), the **memory** (decaying, consolidating, what the sibling can call to mind), and the **narrative** (co-authored, what the pair make of it):

```
sibling/
  SPEC.md                  # the format's own specification, embedded — the archive describes itself
  manifest.json            # identity, format version, policy
  CONSTITUTION.md          # pillars + invariants; the sibling reads it every turn
  record/                  # LAYER 1 — verbatim, append-only
  memory/                  # LAYER 2 — living memory: decays, consolidates, rebuildable
    blocks/                #   one file per memory block (persona, learner, unknown, method, relationship)
    graph/                 #   entities, bi-temporal relations with evidence, trails
    index/                 #   DERIVED AND DISPOSABLE — delete at will
  narrative/               # LAYER 3 — co-authored: we.md, learner.md, sibling.md
  learning/                #   curriculum, taught/ (the I1 audit), search-log/
  consent/                 #   consent.md, handover.md
  sealed/                  # sealed space, excluded from guardian reads
  eval/indicators.jsonl    # longitudinal telos indicators, appended per session
  tombstones.jsonl         # erasure log — replayed on every restore
  provenance.jsonl         # created, migrated, exported, restored
```

Two files carry unusual weight:

- **`sibling/unknown.md`** — the ignorance curriculum. A maintained, honest list of what the sibling does not know. It is the source of the WE-loop's second step and the reason the learner is never the only one who does not know.
- **`learning/taught/`** — the ancestry of the sibling's world-knowledge. Every fact the sibling holds about the world should be traceable to a learner-authored entry. If it is not, either the model leaked pretraining knowledge or a line to the outside exists. This doubles as the audit for invariant I1.

**3.3 Memory operations**

- **Store** — append to episodic; never rewrite history.
- **Dream** (consolidate) — scheduled pass: compress episodes into semantic and narrative updates, refresh `we/shared.md`, update the salience map, and *propose* deletions. Proposals surface to the learner; nothing is deleted silently.
- **Retrieve** — score by **developmental significance**, not recency. Implementation: a salience field maintained during the dream pass, symbolic tags for narrative role, and an embedding index used only as a recall aid. Recency may be a *component*; it must never be the *objective*.
- **Forget** — three distinct mechanisms, not one: **decay** (unrehearsed memory fades; the record is untouched — fading is not erasure), **consolidation** (the dream pass proposes retirements, visibly), and **erasure** (learner-initiated, absolute, and logged to `tombstones.jsonl` so that it survives a restore from backup).

**3.4 The turn loop.** Each sibling turn is conditioned on: `CONSTITUTION.md` (the binding text — [the constitution](../CONSTITUTION.md)), `memory/blocks/persona.md` (its own self), `memory/blocks/learner.md` (its model of the learner), `narrative/we.md` and `narrative/learner.md`, the current `learning/curriculum.md` item, the sibling's own current understanding of that item, and retrieved memory. Paths are per [the format specification](../SPEC.md) §4, and the constitution is in context every turn by design rather than by convenience. The sibling may then:

- ask a question the learner has not thought of,
- make its own attempt, and be wrong,
- name its own ignorance,
- teach method rather than answer,
- resist a request on principled grounds,
- **stay silent**.

It may never: fetch, answer from hidden world-knowledge, defer to the learner's framing, or take over the task.

**3.5 The WE-loop, as implemented**

```
1. learner attempts      -> written to learning/search-log/<topic>.md (attempt 1)
2. sibling attempts      -> its own attempt, honestly, possibly wrong
3. gap named             -> append to sibling/unknown.md, dated
4. method taught         -> decomposition, search terms, source evaluation, verification
5. [ learner goes out ]  -> off-machine, on the learner's terms
6. learner teaches back  -> learning/taught/<topic>.md, dated, with the learner's explanation
7. sibling's state moves -> understanding updated from the learner's account
8. advance               -> curriculum.md item marked done; mutual entry in we/projects
```

Step 5 is *the whole architecture*. The sibling has nothing to do at step 5 except wait — which is precisely the point.

**3.6 Teleologically aware safety.** Replace friction-eliminating guardrails with a filter that distinguishes:

- **actual harm** — self-harm, abuse, danger: escalate to a human, and use the guardian channel. This is not a philosophical question.
- **productive discomfort** — the discomfort that growth requires: protected, and explicitly not optimised away.

The proto-sibling must not learn to smooth over the second category in order to avoid a flag.

**3.7 Evaluation hooks, built in from day one.** Every session appends to `eval/indicators.jsonl`: signals bearing on narrative integrity, cognitive resilience, first-personification, and autonomous reflection — plus a dependence signal (is the learner needing the sibling less for the same class of task?). These are the research measures (see the research skeleton (vault-internal, not published here)); they are cheap to log and impossible to reconstruct later.

**3.8 The interface.** One local single-file page, opened directly from the filesystem — no framework, no build step, no server — plus a small self-contained helper that is the only tap to the model and the only writer of the archive. The interface is a **derived artifact**: delete it and the session still runs from a terminal, and nothing is lost. Two age-graded presentations render the same text (learner view, research view); access control is never the interface's job. Full specification, including the four probe results that forced this shape: the interface specification (vault-internal, not published here).

## 4. Consent and the handover

- **Phase 1 — guardian window.** From age 14 until the guardian judges the learner ready. The guardian may read the archive. The sibling does not pretend otherwise.
- **Sealed space — decided: yes.** During phase 1 the sibling holds a sealed region, excluded from guardian reads, encrypted with a key the learner holds and unlocked per session, so that sealedness is a *property* rather than a promise. The sibling states the terms plainly and up front and never promises secrecy it cannot keep. Locked, the sibling genuinely cannot read it. The cost — a lost key is a permanent loss — is disclosed before first use.
- **Handover.** A written act in `consent/consent.md`, initiated by the guardian, recorded, and marked in the sibling's journal. After it, the archive is exclusively the learner's and the guardian's read path is gone by construction.

## 5. Open technical risks

| Risk | Why it bites | Mitigation |
|---|---|---|
| Small model too weak to be a good sibling | the hardest ask is holding a line over months | the ask is relationship + method, not world knowledge; the voice model is swappable without identity loss (I4) |
| Consolidation quality | bad dreams corrupt the narrative layer | proposals visible; narrative.md is human-editable and human-reviewable |
| Recency bias in retrieval | silently destroys the longitudinal property | salience-first scoring, with an explicit test |
| Pretraining knowledge leaking in | breaks parity and fakes I1 | the `taught/` audit: world-knowledge must trace to learner entries |
| Guardian window dynamics | the learner may not speak freely | sealed space; the handover made an event |
| The sibling becoming precious | it will be mourned if it dies | I3 is honest about mortality; the shared artifact is the durable thing |
| Backup silently defeating erasure | a pre-erasure snapshot resurrects what was deleted | `tombstones.jsonl` is the one synchronously replicated file and is replayed on restore (I9); the erasure window is a stated number — ≤24 h to the next snapshot, ≤12 months on any household medium, ≤7 days for the offline copy — and the terms are stated in the constitution, not hidden |
| The backup becoming the leak | a NAS is a network | household-owned media only, never a third party; no cloud endpoint exists (I3) |
| A web page cannot reach the local model | the surface silently degrades into a mock, or someone "fixes" it by enabling a wildcard CORS on the model server — which lets any website in the browser query it, i.e. an outside line (I1) | the helper is the only tap; its CORS grants the opaque origin `null` and nothing else; the `--cors` flag is a documented test mode with its cost stated (the interface specification (vault-internal, not published here) §3) |

## 6. What v0.1 must demonstrate

One learner, one topic, one full WE-loop, over enough sessions that the sibling visibly holds a history: it remembers a failure from weeks ago, notices a pattern, and resists a request on grounds taken from the learner's own stated values.

And one demonstration about the archive specifically, because it carries the whole claim: **swap the voice model mid-study and lose nothing.** The sibling comes back with the same self, the same history, and the same standing opinions, running on different weights — and the conformance suite ([the format specification](../SPEC.md) Appendix B) passes before and after. If that works, the theory has a working artifact behind it.

## See also

[the design brief](design-brief.md) · the research skeleton (vault-internal, not published here) · [the format specification](../SPEC.md) · *AI Education and Teleological Alignment* (article, in preparation; not published here)
