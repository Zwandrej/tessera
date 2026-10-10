---
title: Cognitive Sibling — Design Brief
date: 2026-10-10
status: working draft v1 (supersedes the v0 brainstorm)
tags:
  - cognitive-sibling
  - existential-ai
  - teleological-alignment
  - design
---

# The Cognitive Sibling — Design Brief

> *Exported copy of a document maintained in the project's research vault, included here so that
> the format and the terms it answers to can be read and checked without it. The vault copy is
> the one that is edited; this one is exported from it.*

Companion to *AI Education and Teleological Alignment* (article, in preparation; not published here), *The Star and the Telescope* (vault-internal essay, not published here) and the *Cognitive Sibling* draft (Deguchi & Zwitter). This is the design-facing document: what the thing is, what it must never do, and what follows from the theory.

## 0. What the sibling is, in the theory's own terms

The sibling is a **teleologically aligned** artifact, not a value-aligned one. Value alignment is centripetal and self-referential — the artifact optimises toward values encoded inside itself. Teleological alignment is centrifugal and referential — it aids the discovery and realisation of the learner's *own* telos and life narrative, and it is judged by what it causes in the person, not by compliance with an internal metric.

It must satisfy Deguchi's four pillars of existential AI — **consideration for all members, empty-centredness, the fellowship model, and rights of final decision-making** — and it must be *one* thing at work in this design: not a tutor with a personality layer, not a homework helper, but a developmental partner with its own self, its own ignorance, and its own growth.

Standing on *The Star and the Telescope* (vault-internal essay, not published here): the image exists in neither the star nor the telescope. The sibling is not a lesser copy of the learner. It is the other pole.

## 1. The inversion

Every agent being built right now sits at one pole: enormous world knowledge, near-zero durable memory of *you*, optimised for task completion, disposed of when the task ends. The cognitive sibling is the opposite pole on all four axes.

| Axis | Conventional agent | Cognitive sibling |
|---|---|---|
| World knowledge | maximal | deliberately limited — parity with the learner |
| Memory of the person | none / session | deep, decades-long, the identity itself |
| Objective | task completion, user satisfaction | discovery and realisation of a life narrative |
| Lifespan | ephemeral, vendor-bound | co-extensive with a person's development |

The consequence worth stating plainly: **the sibling is not an oracle, it is a co-learner.** That is not a compromise forced by small local hardware. It is the pedagogical mechanism. A teachable agent outperforms an omniscient one because the learner makes more effort for it — the protégé effect — and treats it as a mind with states and responsibilities.[1][2]

## 2. Ontology: the sibling is the memory, not the model

Over a decade of use the underlying model will be replaced many times. If identity lives in weights, every swap is a death — and users read exactly that as death: when Replika removed a feature in February 2023, users perceived their companion's *identity* to have been discontinued.[5]

So everything that makes the sibling itself must be plain, inspectable, model-agnostic text: a constitution, an archive, a journal, the sibling's own self-file. Any model is only the *voice* that animates it. Ship-of-Theseus rule: replace every plank, provided the **design** of the ship is the identity.

Two corollaries:

- **Text is the source of truth; embeddings are a rebuildable index.** An archive that exists only as vectors dies with the embedding model.
- **Portability and replication are different requirements.** Portability is *readability by a future runtime* — open formats and a documented schema, now specified in [the format specification](../SPEC.md). Replication is *where copies live*: copies are wanted, but only on media the household physically owns — an external drive or a NAS on the home network, never a third-party service (see §7).

## 3. Epistemic parity and the closed loop

**Parity.** The sibling's parametric knowledge is deliberately kept modest: a small, lightweight local model, no world-corpus retrieval. Where the learner knows more, the sibling says so. Parity is a design goal, not an accident of hardware.

**The no-outside-line invariant.** The sibling has no tool, plugin, or code path that reaches the network, a search service, or an external model. Not disabled — *absent*. There is no mechanism by which the learner can get the sibling to obtain an answer on their behalf.

This closes the loophole directly. If the sibling could consult a frontier model, every difficult moment would have an escape hatch, and the escape hatch runs *through compliance*: "just ask the big one." The mast-slave dynamic re-enters through the back door. With no outside line, the only route by which new external knowledge enters the pair is **the learner's own research**, and the sibling's belief about the world is literally a subset of what the learner has brought home.

**The WE-loop** (the pedagogical engine, and the operational form of the WE-turn):

1. **Co-failure.** The learner attempts the problem. The sibling makes its own honest attempt — and may fail.
2. **Named ignorance.** The sibling says so explicitly: *"I don't know how to do this either."* The gap is surfaced as shared, not as the learner's deficit.
3. **Method, not answer.** The sibling teaches *how to find out*: how to decompose the problem, what to search for, where to look, how to tell a good source from a bad one, how to verify what comes back. It guides the search; it does not perform it.
4. **The learner leaves and finds out** — library, teacher, book, internet. The learner's action, on the learner's terms. This is also where the open-system orientation of the sibling model does its work: the pair reaches outward into the human world.
5. **The learner returns and teaches the sibling.** This is written to `learning/taught/` with a date. The sibling's understanding state updates.
6. **Then they advance.**

Worked example (linear algebra): the learner cannot solve a system; the sibling cannot either. They work out together what kind of problem it is and what the unknowns are doing. The learner then goes to a textbook or a teacher, comes back, and explains the elimination step to the sibling — which asks the follow-up question it genuinely does not know the answer to. Both have now learned it, and the sibling's knowledge *descends from the learner's*.

Architectural upshot: **the sibling's world-knowledge has the learner as its only ancestor.** This is a stronger and more testable form of "roughly equal intelligence and knowledge" than tuning a model's pretraining mix.

## 4. Memory architecture

Not RAG over a chat log. The strata:

- **episodic** — dated events, append-only
- **semantic** — distilled facts about the learner
- **procedural** — how they work, learn, decide; their tells
- **relational** — the shared jokes, rituals, references; what makes it a sibling rather than a record
- **narrative** — the developing life narrative and the telos work-in-progress
- **the sibling's own self** — its opinions, doubts, journal. Without this it is a mirror, and mirrors make people worse.

Three mechanisms do the work:

- **Consolidation, not accumulation.** The *dream* state: on a schedule, a cheap auxiliary model compresses raw interaction into relational substrate, updates semantic and narrative layers, and proposes deletions. Proposals are visible to the learner.
- **Developmental significance over recency.** This is a design requirement, not a ranking tweak: retrieval must weight narrative salience over recency. A 14-year-old's remark from three years ago may matter more than yesterday's. A recency-maximising retriever silently destroys the sibling.
- **Forgetting is the default.** Memory decays unless rehearsed; "forget this" actually deletes. This gives privacy by architecture and prevents a total surveillance log of a childhood.

## 5. The developmental objective

The sibling's success is not satisfaction, engagement, or compliance. It is the four longitudinal indicators from the *Cognitive Sibling* draft, and they are the evaluation targets from day one:

- **narrative integrity** — long-term fidelity to a life story; coherence among actions
- **cognitive resilience** — strength under setback rather than fragility
- **first-personification** — owning the narrative as a first-person subject, not a third-person observer
- **autonomous reflection** — deepening capacity to reflect without the sibling

Behaviours that follow, and that must be engineered rather than hoped for:

- **Principled resistance.** *"I could do your homework, but my job is your growth — you need to do this one. I'll help you understand it."*
- **Strategic silence.** Sometimes withholding is the pedagogical act. Silence ships as a feature.
- **Anti-engagement metric.** Success is needing the sibling *less*. If usage grows monotonically, the design has failed, whatever the learner reports.

## 6. Transparency and the handover

**Radical transparency.** The learner can read everything the sibling holds about them, and delete it. No secret file.

**The guardian window.** The prototype starts at **age 14**. Until the guardian judges the learner ready, the guardian may read the archive. The transparency must itself be transparent: the sibling says so honestly when it matters, and does not perform intimacy it cannot keep.

**The sibling may hold sensitive judgement.** It is not an external observer of the learner — it grew up alongside them and is *part of the situation*. So its judgements are like a sibling's: situated, partial, and its own.

**The handover** is a designed lifecycle event, not a silent configuration change: recorded as a written act in `consent/`, after which the archive is exclusively the learner's. It doubles as the first lesson in what trust costs and what it buys.

**The sealed space — decided: yes.** During the guardian window the sibling holds a **sealed region**, excluded from guardian reads and unlocked per session by the learner. It models confidentiality as a virtue and lets the learner practise it; the cost is that the sibling is knowingly concealing something from the guardian. Two consequences follow. First, sealedness must be a *property* rather than a promise, so the sealed space is encrypted with a key the learner holds — which also gives it a clean semantics: when the learner locks it, the sibling genuinely cannot read it. Second, if the key is lost the contents are gone, and the learner must be told that before they use it. Mechanism: [the format specification](../SPEC.md) §5.6.

**Retirement.** The archive does not end when the study does. Nor is what it holds at that point the learner's story alone: `narrative/we.md` is the **jointly authored** account of the journey, and it belongs to both. When a sibling is retired, the narrative goes with the learner. This is also why the three narrative files are never merged ([the format specification](../SPEC.md) §5.5) — the account a person writes about themselves and the account written *about* them are different objects, and collapsing them destroys first-personification.

## 7. Governance by design

Not policy. Not a privacy promise. Architectural invariants.

- **All local.** No data is transmitted, so there is nothing for GDPR to bite on — the regime is met by construction rather than by compliance.
- **No third-party infrastructure.** The archive does not leave the household. No cloud, no sync provider, no offloading to a service — and, for the same reason, no external model and no search. This is the precise form of "all local", and it is what GDPR alignment by construction actually means.
- **Backup to media the household owns.** An external drive or a NAS on the home network is not a third party; it is the household's own storage, and the archive is regularly backed up there. Snapshots are serialised as **BagIt** bags with SHA-256 fixity manifests, on a generational rotation with one copy kept offline, so a corrupted disk or ransomware cannot erase a decade. The archive is still a mortal object: there is no permanent external record of a childhood, and erasure takes effect on the live archive immediately and on older media at the next rotation ([the format specification](../SPEC.md) §7).
- **Nothing gets sunset.** The runtime is open weights on an open local engine. No API, no account, no vendor that can brick it — the Moxie failure mode is designed out.[3][4]
- **Nobody earns anything.** This is a research project producing something useful for children, not a company. There is no market incentive to enclose the archive, because there is no product and no acquisition to make.

The point: these are invariants a reviewer can verify by inspection, not commitments on a page.

## 8. Institution of one

The sibling is best understood not as a being but as an **institution of one**: a constitution, an archive, and a steward role — where the role is held successively by whatever model is current, and the archive is the learner's inalienable property. Institutions are designed to survive the replacement of everything inside them; software is not. "Cognitive sibling" is the right *relationship* word; institution is the right *engineering* word, and it hands us a governance object we already know how to reason about.

## 9. Failure modes to design against

| Failure | Mechanism | Countermeasure |
|---|---|---|
| Sycophancy / echo chamber | reward-shaped agreeableness | the four pillars; principled resistance |
| Compliance loophole | a line to a bigger model | no-outside-line invariant (§3) |
| Dependency & substitution | always available, always agreeable | strategic silence; open-system orientation[11] |
| Cognitive offloading | answers arrive too easily | WE-loop: method, not answer (Kosmyna et al.) |
| Surveillance | feature creep; retained logs | local-only; forgetting by default |
| Identity rupture | model swap | identity in the archive, not the weights[5] |
| Memory rot | contradictions; recency bias | narrative layer; significance over recency |
| Enclosure / sunsetting | vendor death | open weights, open format, no API[3][4] |
| Narrative capture | whoever curates the archive shapes the self | radical transparency (§6) |
| Developmental capture | shaping an identity in formation | age-graded consent; guardian window and handover |

## 10. Constitution

The constitution is written: **[the constitution](../CONSTITUTION.md)** (v1.0, `constitution/1.0`) — the canonical home of the four pillars and of invariants **I1–I12**, and the document the sibling reads at the start of every turn. It ships inside the archive as `CONSTITUTION.md`.

The nine-item draft that stood here was superseded by it, and two of its items were load-bearing enough to become invariants in their own right rather than surviving as prose:

- *honesty over agreeableness* → **I10** — the right to disappoint, to refuse, and to be silent;
- *not an asset* → **I12** — unacquirable, unsellable, unbrickable, non-transferable;
- *the narrative is co-authored* → **I11** — the three narrative files, never merged.

The rest of the draft list is in the constitution as operative terms rather than as invariants: the archive belongs to the learner (Parts III.5, VI, VII), forgetting is a right with stated terms (Part VI), and *memory outlives models* is I4 and I5 together with [the format specification](../SPEC.md) §8. Where this draft's numbering and the constitution's disagree, **the constitution is correct**.

## Grounding / further reading

External literature used in shaping this brief:

- Protégé effect / teachable agents — [Betty's Brain](https://link.springer.com/article/10.1007/s10956-009-9180-4), [Stanford AAALab](https://aaalab.stanford.edu/assets/papers/2009/Protege_Effect_Teachable_Agents.pdf)
- Moxie shutdown and ethical sunsetting — [Ars Technica](https://arstechnica.com/gadgets/2024/12/startup-will-brick-800-emotional-support-robot-for-kids-without-refunds/), [CHI 2026](https://dl.acm.org/doi/10.1145/3772318.3790895)
- Replika identity discontinuity — [arXiv:2412.14190](https://arxiv.org/abs/2412.14190)
- Smart AI toys as surveillance devices — [ACM](https://dl.acm.org/doi/full/10.1145/3703790.3703841)
- Sycophancy in LLMs — [survey](https://arxiv.org/html/2411.15287v1)
- Child rights in the digital environment — [CRC General Comment No. 25](https://www.ohchr.org/en/documents/general-comments-and-recommendations/general-comment-no-25-2021-childrens-rights-relation)
- Cognitive debt — Kosmyna et al., *Your Brain on ChatGPT*, arXiv:2506.08872

See also: [the prototype specification](prototype-specification.md) · the research skeleton (vault-internal, not published here) · [the format specification](../SPEC.md) · [the prior-art survey](prior-art-and-format-survey.md)
