---
title: Cognitive Sibling — Prior Art and Format Survey
date: 2026-10-10
status: working draft v1
tags:
  - cognitive-sibling
  - prior-art
  - archive-format
  - survey
---

# Prior Art and Format Survey

> *Exported copy of a document maintained in the project's research vault, included here so that
> the format and the terms it answers to can be read and checked without it. The vault copy is
> the one that is edited; this one is exported from it.*

What exists already, what we take from it, and what we reject. Companion to [the format specification](../SPEC.md).

## 0. The yardstick

The format must satisfy eight requirements derived from the design invariants. Anything surveyed below is measured against these, not against how good it is in its own terms.

| # | Requirement | From |
|---|---|---|
| R1 | **Plain text, inspectable, model-agnostic.** A stranger with `cat` can read it. | I4, "the sibling is the memory, not the model" |
| R2 | **Outlives its runtime.** Readable and reconstructible with no dependency on any vendor, service, or model. | I5, "nothing gets sunset" |
| R3 | **No third-party infrastructure.** Replication only to media the household owns. | I2, governance by design |
| R4 | **Provenance to the verbatim source.** Every derived claim traces to something that was said or done. | I1 audit; anti-hallucination |
| R5 | **Temporal, not snapshot.** Facts have validity windows; the past is not overwritten. | the longitudinal claim |
| R6 | **Significance over recency** as the retrieval objective. | §4 of the Design Brief |
| R7 | **Forgetting is a right with teeth**, and it must survive being backed up. | invariant 2 |
| R8 | **A co-authored artifact.** The narrative belongs to the pair, not to a model. | the WE-turn; co-constitution |

Nobody has built a format against all eight, because nobody has built for a single relationship over decades. That is the gap.

## 1. Lineage: the personal archive as an idea

**Vannevar Bush, *As We May Think* (1945).** The memex — "an enlarged intimate supplement to his memory" — with two ideas that were right and are still unimplemented as *data*: (a) **associative trails** rather than hierarchies ("the process of tying two items together is the important thing"); (b) the admission that **memory should fade** — "trails that are not frequently followed are prone to fade, items are not fully permanent, memory is transitory." Bush gave us both the archive and the case for its decay, eighty years early.

**Gordon Bell, MyLifeBits (Microsoft Research, 2001–).** The serious attempt at a lifetime store: digitise everything, keep it all, "Total Recall". Its lesson is exactly the lesson we need: **capture is the easy half, sense-making is the hard half.** A complete record did not produce a companion. It also produced the field's cautionary arc — lifelogging's overpromise and retreat — which is why we treat the record as a deliberate act rather than a side-effect (see §4.2 of the Specification).

**Digital preservation.** A thirty-year discipline that has already solved "keep data usable across several technology generations": OAIS (ISO 14721) for the archive model, **PREMIS** for provenance/fixity/rights metadata, **BagIt** for packaging with checksums, format migration as a documented event. We should not invent this; we should adopt its profile. The Digital Preservation Coalition's work on *personal* digital preservation is the closest existing framing to what we need.

## 2. LLM memory systems

**MemGPT / Letta.** The tiered architecture: **core memory** (in-context, editable, character-limited blocks), **recall memory** (full conversation history, searchable), **archival memory** (external store, retrieved on demand). Two ideas are directly portable: memory *blocks* as the unit (`persona`, `human`, custom, each with a label, a size limit, a description) — which maps one-to-one onto one file per block; and **sleep-time compute**, background agents that consolidate the primary agent's memory during idle. Sleep-time compute is our *dream* pass, already named and studied.

**Zep / Graphiti.** A **bi-temporal** knowledge graph: `t_created`/`t_invalid` (system time) alongside `valid_from`/`valid_to` (world time); contradictions found by comparing new edges against semantically related old ones, and resolved by **invalidation rather than deletion**. This is the correct treatment of a person's changing facts — "she is afraid of this" must be able to expire without erasing that it was once true.

**Mem0.** Distil conversations into salient facts and drop the rest. Useful as the semantic layer's job description; unacceptable as the *only* layer, because it is lossy with no verbatim floor and the loss is decided opaquely by a model.

**Generative Agents (Park et al., 2023).** A memory stream with retrieval scored by **recency + importance + relevance**, plus periodic *reflection* that synthesises higher-level conclusions. We adopt importance/reflection wholesale and **invert the objective**: importance must be *developmental significance*, with recency demoted from objective to at most one term.

## 3. Verbatim local-first personal memory: MemPalace

The closest existing system, and the most useful one to argue with. **MemPalace** (Milla Jovovich and collaborators; local-first, no API calls) stores conversation history **verbatim** — "it does not summarize, extract, or paraphrase" — and retrieves it semantically. Its architecture is spatial: **wings** (people/projects) → **rooms** (day/topic) → **drawers** (verbatim chunks), plus tunnels for cross-wing traversal; a compact symbolic index ("AAAK") that lets a model scan thousands of entries cheaply and know which drawer to open; an **L0–L3 wake-up stack**; a pluggable retrieval backend (embedded ChromaDB by default); and a **temporal entity-relationship graph with validity windows** in local SQLite. There is a stated backup retention setting.

What we take: verbatim storage as an ethical floor; spatial scoping; local-first default; validity windows; pluggable indexing; and the discipline of never paraphrasing the person — a model that paraphrases your childhood is editing it.

What we reject, and why it matters:

- **Verbatim as *the memory*** — its stated position that every word is sacred and nothing is forgotten. Our design makes *forgetting the default*. This is the central inversion, and it forces the split in §2 of the Specification: a verbatim **record** and a decaying **memory** are different objects with different ethics, and conflating them is what makes the two positions look opposed.
- **Vectors as the store.** We require text as the store and embeddings as a disposable cache (R1). In MemPalace the retrieval layer is the system; deleting it costs you the palace.
- **Benchmark-first framing.** The project's identity is a retrieval score on a memory benchmark. A sibling is not scored that way, and optimising for recall benchmarks selects precisely the behaviour we are trying to avoid.
- **Governance.** Single-figurehead projects carry a fragility worth noting for R2: "local-first" solves *data* custody, not *software* custody. If the code dies, the archive survives only if the format is trivially simple. Hence the self-describing archive and the dependency-free reference reader.

**The alternative, in one sentence.** Not a different database but a different kind of object: **plain-text files in three layers with a documented schema, and a purely derived index** — no database and no vector store in the durable path. Measured on a synthetic ten-year archive, the whole memory is **12.9 MB and loads in 73 ms**, so nothing forces a database; and because plain text is the one substrate from which SQLite, FTS5, vectors, RDF-star and the MCP shape can all be *regenerated*, it is the only choice that leaves every other option open. Decision and measurements: [the memory-format decision](decision-memory-format.md).

## 4. Graph substrate

**RDF / RDF-star vs property graphs.** RDF-star extends triples with "statements about statements" — an embedded triple can carry qualifiers, which is exactly what a memory fact needs (when it was added, when it was last recalled, how often). RDF-star is a W3C-track standard with a real ecosystem; property graphs are better at traversal. For our purposes the relevant finding is that a **subset profile** gets us the semantics without the toolchain: JSONL records with the same fields (subject, predicate, object, validity, system time, evidence, counters) are readable by `cat`, strippable to plain text, and convertible to RDF-star or to a property graph by a script if anyone ever wants to.

**MCP memory server.** A widely-supported interchange shape: **entities**, **relations**, **observations** serialised as JSONL. Adopt as an *export/read profile* — it means any MCP-capable tool can read a sibling's graph without new code. Not as the store: it is cache-shaped and has no notion of provenance or validity.

## 5. Data sovereignty

**Solid** (Berners-Lee): personal online data stores, "apps as guests", data centred on the person rather than the application. We take the *principle* (the archive is the person's; every program that touches it is a guest) and reject the *architecture* for v0.1: a pod presumes a networked server, and our invariant is that the sibling has no outside line. A read-only pod mirrored from the NAS is conceivable as an access convenience and is explicitly **out of scope** precisely because it creates an outward path and thus a leak surface.

**Local-first software** (Ink & Switch, 2019). Seven ideals: no spinners; not trapped on one device; the network is optional; seamless collaboration; **the long now**; security and privacy by default; and **you retain ultimate ownership and control**. This is the closest thing to a formal standard our design can be measured against, and we should adopt its vocabulary — ideal 5 *is* our archival-format requirement, and ideal 7 is our ownership clause. Its CRDT tooling is also the right answer to a problem we have not yet solved: two authors (learner and sibling) writing one narrative concurrently.

## 6. From a table: adopt / adapt / reject

| Candidate | Class | What we take | What we reject |
|---|---|---|---|
| Bush, memex | lineage | **trails** as a first-class type; fading as legitimate | hardware specifics |
| MyLifeBits | lineage | the cautionary lesson: capture ≠ companionship | capture-everything as the goal |
| MemGPT / Letta | LLM memory | memory blocks as files; sleep-time consolidation; `persona`/`human` split | DB as system of record; agent summaries as authority |
| Zep / Graphiti | temporal KG | bi-temporal validity; invalidation, not deletion | service dependency; ephemeral edges with no evidence |
| Mem0 | extraction | the semantic layer's job | lossy-by-default with no verbatim floor |
| Generative Agents | memory stream | importance + reflection | recency as an objective |
| MemPalace | verbatim local-first | verbatim record; spatial scoping; local-first; validity windows; never paraphrase the person | verbatim *as* the memory; vectors as the store; benchmark-first |
| RDF-star | substrate | qualifier semantics, temporal qualifiers | hard toolchain dependency |
| MCP memory | interchange | the export/read profile | as the store |
| Solid | sovereignty | apps are guests; person at the centre; ownership | networked pod (rejected for v0.1) |
| Local-first (I&S) | standard | vocabulary and the seven ideals; CRDTs for co-authorship | — |
| OAIS / PREMIS / BagIt | preservation | packaging, fixity, provenance log, migration discipline | full conformance (overkill) |

## 7. The gap

- No existing system treats the **verbatim record** and the **living, forgetting memory** as two objects with two ethics. Everyone picks one and argues.
- No existing system has a **co-authored** primitive: everything is the agent's memory *of* a user. A narrative with two authors is a different data structure — and, per R8, the whole point.
- No existing system reconciles **forgetting with backing up**: every backup quietly defeats the right to erasure, and nobody has written down what to do about it.
- No existing format has **decades** as its design horizon. Preservation solves durability; memory systems solve retrieval; nobody solves both at once for one relationship.

Those four are the contribution.

## 8. Lineage for the name: the *tessera hospitalis*

The format is named after the Roman token of *hospitium* (§2.2 of [the format specification](../SPEC.md)). It belongs in this survey because it is prior art in the strict sense: a two-thousand-year-old solved problem in **authenticating a relationship without a central authority and without trusting the bearer**. The design borrows three things from it and claims nothing more —

- **the two-sided record** (P7): the token belonged to the bond, not to either party;
- **proof by collation** rather than by assertion — the tokens are compared, not taken on trust;
- **inheritance**: the obligation passed to the parties' descendants, which is the design's horizon.

It is also a useful corrective. The conspicuous modern failures in this space — companion devices bricked by a vendor's shutdown, a child's shared history held in somebody else's account — are failures to keep the token on the household's side of the door. That is invariant I3, arrived at from the other end.

Sources for §8 and §2.2: *Tesseram conferre. Etruscan, Greek, Latin, and Celtiberian tesserae hospitales* (open copy in the Universidad de Zaragoza repository, `zaguan.unizar.es/record/128031`; also JSTOR 48589991) — the account of the tokens as bronze, bone or ivory objects identifying the two parties to a hospitality agreement, and of Plautus' *Poenulus* as the key literary evidence; "Hospitality among the Romans", in *The Oxford Handbook of Social Relations in the Roman World* (OUP, 2011), on the tokens given as a sign of guest-friendship; and "The Rituals of Hospitium: The Tesserae Hospitales" (Brill, 9789004273870).

## References

- Bush, V. *As We May Think*. The Atlantic, July 1945.
- Bell, G. & Gemmell, J. *Total Recall / Your Life, Uploaded*; MyLifeBits, Microsoft Research.
- Packer, H. S. et al. **MemGPT**; Letta, *Memory Blocks* and *Agent Memory* (sleep-time compute).
- Rasmussen, P. et al. **Zep: A Temporal Knowledge Graph Architecture for Agent Memory** (Graphiti).
- Park, J. S. et al. **Generative Agents: Interactive Simulacra of Human Behavior**, 2023.
- MemPalace — `github.com/mempalace/mempalace`; `github.com/milla-jovovich/mempalace`.
- **RDF-star** W3C Working Group; *Transforming RDF-star to Property Graphs* (arXiv:2210.05781).
- Temporal KG agent memory with RDF-star qualifiers (arXiv:2408.05861).
- **MCP memory server** reference implementation.
- Berners-Lee, T. **Solid** — `solidproject.org`.
- Kleppmann, M. et al. **Local-first software: you own your data, in spite of the cloud**. Ink & Switch, 2019.
- **OAIS** (ISO 14721); **PREMIS** Data Dictionary; **BagIt** File Packaging Format (RFC 8493).
- Digital Preservation Coalition, Technology Watch — personal digital preservation.
- *Tesseram conferre. Etruscan, Greek, Latin, and Celtiberian tesserae hospitales* — Universidad de Zaragoza repository, `zaguan.unizar.es/record/128031`; JSTOR 48589991. Basis for §8.
- "Hospitality among the Romans", in *The Oxford Handbook of Social Relations in the Roman World* (OUP, 2011).
- "The Rituals of Hospitium: The Tesserae Hospitales" (Brill, 9789004273870).

## See also

[the format specification](../SPEC.md) · [the design brief](design-brief.md) · [the prototype specification](prototype-specification.md)
