---
title: Cognitive Sibling — Decision: Memory Format
date: 2026-10-10
status: decided
decisions:
  - record_policy: deliberate
  - sibling_own_files: study data, always available
  - sealed_space: encrypted, learner-held key
  - memory_format: plain-text files + disposable index
  - name: Tessera (tessera/0.1)
  - interface: one local page + small self-contained helper (no framework, no server)
  - machinery_visibility: age-graded (learner view / research view)
  - voice: text-only in v0.1
  - session_opening: the sibling greets first — names last time, offers two options
  - surface: sibling.html served by the helper; a derived artifact, deletable without loss
  - retention: 30 daily / 12 weekly / 24 monthly / annual indefinitely
  - erasure_window: <=12 months on any medium
  - memory_format: plain-text files + disposable index
tags:
  - cognitive-sibling
  - decision
  - archive-format
---

# Decision: the memory format

> *Exported copy of a document maintained in the project's research vault, included here so that
> the format and the terms it answers to can be read and checked without it. The vault copy is
> the one that is edited; this one is exported from it.*

**Decision.** The sibling's memory is a **small set of plain-text files with a documented schema, in three layers, plus a purely derived index**. There is **no database and no vector store anywhere in the durable path.** SQLite is not the system of record. ChromaDB (or any embedding store) is not the memory; it is a **cache that may be deleted at any time without loss**.

This is the alternative to MemPalace, and it is a deliberate inversion of it.

## 1. Why this needed deciding at all

MemPalace — the closest prior art, and a good system in its own terms — makes three commitments we cannot accept:

1. **Verbatim text is the memory.** Its position is that every word is sacred and nothing is forgotten. Our design makes forgetting the default.
2. **Vectors are the store.** Its retrieval layer *is* the system; the palace is the index.
3. **The store is a database.** Content chunks live in SQLite behind a pluggable backend contract (Chromadb embedded by default), with a separate temporal graph in SQLite, and its own `migrate.py` for "ChromaDB version migration" — which is exactly the fragility the 20-year requirement exists to avoid.

None of that is a criticism of MemPalace. It is built to be a *general* memory system for arbitrary corpora, at arbitrary scale, where the corpus is large and unknown. We have the opposite situation.

## 2. The measurement that settles it

Before choosing, the decisive question is whether a decade of one person's memory actually needs a database. Synthetic archives were generated at both recording policies and measured (probe: `memory_format_probe.py`; ten years, 400 entities, 5 memory blocks, ~1 MB of narrative).

| | **deliberate** (chosen) | **continuous** (worst case) |
|---|---|---|
| records | 10,950 | 365,000 |
| relations | 18,250 | 54,750 |
| **total archive on disk** | **12.9 MB** | **141 MB** |
| load the whole archive into memory | **73 ms** | 1.37 s |
| rebuild the lexical index from scratch | **47 ms** | 629 ms |
| query: indexed / full scan | **0.66 ms / 2 ms** | 18.9 ms / 47 ms |
| the same corpus in SQLite | 5.5 MB · LIKE 3.9 ms · FTS5 0.2 ms | 90.9 MB · LIKE 65.7 ms · FTS5 1.7 ms |

**Ten years of a deliberately kept memory is 13 MB and loads in 73 milliseconds.**

So the honest finding is the double-edged one: **SQLite is genuinely better** — 2.3× smaller and faster for search. And it is still the wrong choice, because the things it optimises (bytes on disk, query latency) are not scarce at this scale, while the things we require (readability by a stranger, provable disposability of the index, no young dependency in the durable path) it cannot provide.

The scaling headroom is also large: the falsification threshold below is ~75 years away on current trajectory.

## 3. The four candidates

| | Substrate | Verdict |
|---|---|---|
| A | MemPalace-style: chunks in SQLite + embedded vector store as the store | **Rejected** — vectors in the durable path; binary container; young library; benchmark-first |
| B | SQLite + FTS5 as the store, no vectors | **Rejected** — technically the best of the four (§2) and still fails P1/P2: not `cat`-able, binary format that needs a tool to read, and migration risk over decades |
| C | **Plain-text files + documented schema + derived index** | **CHOSEN** |
| D | RDF-star / Turtle dataset as the store | **Rejected as the store**, adopted as an **export profile** (§9 of the spec) — semantics we want, toolchain we don't |

## 4. Why C, stated as an argument

**C is the only substrate from which all the others can be derived.** From plain text you can regenerate SQLite, an FTS5 index, a vector store, RDF-star, and the MCP entity/relation shape — any of them, any time, by script. From SQLite you cannot get the others back without depending on `sqlite3` existing and on a schema you have to remember.

That is the whole argument in one line: **choose the format that keeps every other format available.** C wins on reversibility, which is the property that matters over decades, and loses only on size and latency, which are not scarce. In the dimensions this project actually trades in — durability, inspectability, provability — C strictly dominates.

Two further consequences:

- **The index becomes a testable claim, not a promise.** P2 says derived data is disposable; with C that is checkable ("delete `memory/index/`, rebuild, diff — nothing lost"; 47 ms to rebuild).
- **The record policy and the format reinforce each other.** Deliberate recording is why the archive is 13 MB and not 141 MB. The chosen policy is what makes the simple format sufficient — and the ethical decision and the engineering decision turn out to be the same decision.

## 5. What the format concretely is

| Layer | Files | Format |
|---|---|---|
| **Record** — verbatim, append-only | `record/YYYY/YYYY-MM.jsonl` | JSONL, one event per line |
| **Memory** — decays, consolidates | `memory/blocks/*.md` | Markdown + YAML frontmatter |
| | `memory/graph/{entities,relations}.jsonl`, `memory/graph/trails/*.jsonl` | JSONL |
| **Narrative** — co-authored | `narrative/{we,learner,sibling}.md` | Markdown |
| **Index** — derived, disposable | `memory/index/` | any format; deleted without loss |

Full schemas in [the format specification](../SPEC.md) §5.

**Versioning and fixity** are deliberately separate from the memory format:

- snapshots as **BagIt** bags with SHA-256 manifests, for the household's NAS or external drive (spec §7);
- optionally a **local git repository** as the version layer — append-only history, diffs, and content-addressed integrity for free. Caveat: git's object store is binary, so the working tree stays the canonical readable form, and the remote must never be a hosted service (a bare repo on the NAS, at most).

## 6. What we give up, and how we get it back

**What is lost:** fast semantic search over the corpus.

**Why it is not the mechanism.** MemPalace's retrieval problem is open-domain recall over a flat corpus of everything ever said — which *needs* vectors. The sibling's problem is different: the distilled answer already lives in the memory blocks, which are always in context; the graph is *walked*, not searched; and only the record is ever text-searched, and rarely. The retrieval path is structural memory → graph neighbourhood → lexical search over the record. Vectors are an optional *recall aid* on top of that, never the mechanism.

**And if we want them anyway,** they are a 20-line addition to the derived index, and deleting them costs nothing. The escape hatch is an index, never a new store.

## 7. What would change this decision

Falsifiable, so that it can be revisited on evidence rather than taste:

- the archive exceeds **~1 GB**, or
- a full scan over the record exceeds **~500 ms**, or
- index rebuild exceeds **~5 s**.

At 13 MB per decade, all three are decades to centuries away. If any is crossed, the response is a **better index** — an FTS5 database, or vectors — not a new store.

## 8. Decisions recorded here

Confirmed in the same round, and carried into the other documents:

- **Record policy: `deliberate`.** Conversation is transient; the record holds what the pair marked. This is both the ethical choice and the reason the format is simple.
- **Sibling's own files: study data, always available.** `narrative/sibling.md` and `memory/blocks/persona.md` are readable by the research team, so faults can be diagnosed and the design improved. Consequence, and it is a design requirement rather than a footnote: **the sibling must be told this, up front, in the constitution.** A journal its author knows is read produces honest material; a journal its author believes is private and isn't produces either concealment or performance, and both destroy the sibling's reliability as an object of study. Note the symmetry this creates — the learner is under a disclosed guardian window; the sibling is under a disclosed study window. Both know. That symmetry is what makes "consideration for all members" concrete rather than decorative.
- **Sealed space: encrypted**, learner-held key, unlocked per session.
- **Memory format: plain-text files plus a purely derived index.** No database and no vector store in the durable path; any embedding store is a cache that may be deleted at any time without loss (§2, §5).
- **Name: *Tessera*, `tessera/0.1`.** After the *tessera hospitalis*, the Roman token of a hospitality bond — held by each party and compared to prove it, which is proof by collation rather than by trust. See §2.2 of [the format specification](../SPEC.md).
- **Retention: 30 daily · 12 weekly · 24 monthly · annual indefinitely**, one air-gapped copy at ≤7 days exposure, a quarterly full scrub, and a hard **12-month** cap on the erasure-propagation window. See §7.3–7.4 of the format spec. Chosen against the threats — hours, weeks, months, years — rather than for storage, which is not scarce at ~1 GB/decade.

- **Interface: one local single-file page, opened directly from the filesystem; a small self-contained helper is the only tap to the model and the only writer of the archive.** No framework, no build step, no server, no install. The interface is a **derived artifact** — the same tier as the index — so it is disposable by construction: delete it and the session still runs from a terminal, and nothing is lost. Decided on four probe results (§the interface specification (vault-internal, not published here) §3): a `file://` page *is* a secure context with real file access; it *cannot* call LM Studio (the server sends no CORS headers at all); LM Studio's `--cors` flag would fix that but "allows any website you visit to access the server", which is an outside line (I1); and a local helper granting only the opaque origin `null` accepts the page and refuses the web. **The hand-written origin check is the more private option, not the more complex one.**
- **Machinery visibility: age-graded.** The research view shows the full apparatus; the learner view is pared back. Both render the same text, and the switch changes what is shown, never what is accessible — **access control is not the view's job** (the guardian window, the sealed region and the handover are properties of the filesystem and of the learner's key, never of a UI mode). There is no guardian view at all; the guardian reads the files directly.
- **Voice: text-only in v0.1**, returning as a v0.2 experiment once the model-swap demonstration passes. Deferred for design reasons, not privacy ones — the household's synthesis and transcription are already local (piper, faster-whisper), and the teach-back must be *written* to enter the archive anyway.

- **Session opening: the sibling greets, and what it may say is enforced.** The session opens on the conversation with one short greeting that names the one thing the pair were on last time and ends with exactly two options — continue with that, or something else — read out of the record (`last_session()`), never invented. This settles the interface specification (vault-internal, not published here) §10.2, which had been left undecided on purpose. It is reconciled with the anti-engagement principle (I10, Pillar 2) by reading that principle precisely: **it forbids extending a session, not opening one** — nothing here invites return, and the greeting may name nothing but the work. The cost is admitted (a sibling that speaks first is asking for engagement) and paid for with a bound that lives in code rather than in a prompt: `vet_greeting` refuses warmth, length, a missing choice, or a greeting that names nothing from last time, the fallback speaks instead, and the fallback's use is recorded. A warm greeting is therefore not merely discouraged — it cannot ship. The facts handed to the model also separate the two speakers, because the first greeting to ship quoted the sibling's own reply back to the learner as *her* words — a fault the form validator could not see, and now a selftest case.

- **The surface is built and stays disposable.** `sibling.html` (one file, no framework, no build) plus the helper's routes; the page is served by the helper at `/` and opens just as well from the filesystem. It keeps zero state — no `localStorage`, no preferences, no view persistence — and the view switch changes what is *shown*, never what is accessible. Delete the page and the session still runs from a terminal; delete the helper too and the archive still reads. That is the test the interface had to pass to be allowed to exist (§1).

## See also

[the format specification](../SPEC.md) · [the prior-art survey](prior-art-and-format-survey.md) · [the design brief](design-brief.md) · the research skeleton (vault-internal, not published here)

## D-006 The setup screen offers models it has actually heard from

**Decided:** directory discovery is a fixed list of common local servers, probed by asking each
one for its model list, and a server is offered only if it answers. Anchor: a preset list is a
**guess about a port**; a model list is **evidence** that something is listening there and ready
to talk. Only the second may be presented to a person as a choice.

**Against:** port-scanning (would offer AirPlay, printers, and other households' services);
trusting a preset to be running (would offer a model that does not exist, and the failure would
appear later as the sibling being broken); requiring a terminal (would make the scholarly design
depend on the reader's comfort with a shell).

**Consequence:** the settings screen lists what is real on this machine, says plainly which
presets did not answer, and refuses non-loopback addresses — the screen cannot be used to point
the sibling at another machine. Models that cannot converse (embeddings, rerankers, ASR) may be
present but are not offered as the voice, because the trap only catches people who do not already
know the difference.

## D-007 The name is an act on the archive; the model is recorded without being named

**Decided:** the sibling's name lives in the manifest, is set through the helper (its only
writer), and is journalled in provenance as `renamed {from, to}`. A change of model is journalled
as *that* the voice changed, with no model named anywhere in the archive.

**Anchor:** the pair's identity must survive the hardware. A name is a fact about the
relationship; the model is a fact about the machine. Recording the second inside the first would
make the sibling's identity a function of which weights happened to be installed — the exact
confusion I2 exists to prevent.

**Consequence:** the archive is portable and honest: open it in five years on different hardware
and nothing in it claims a model that is no longer there. Settings live outside the archive
(a path, a port, an endpoint, nothing personal), so losing them costs a minute, not a memory.

## D-008 A new archive has no constitution until the sibling writes one

**Decided:** `CONSTITUTION.md` is written by the sibling, in its first act in a new archive, from
the household's own text. The helper extracts the named sections of the household's constitution and
puts *that* text to the model, writes the declaration itself, holds the candidate in a scratch
directory, and admits it to the archive only once check 11 has judged it -- and on failure the
sibling is asked again, told what was wrong, once.

**Against:** shipping a rendering with the archive (it would be the author's voice wearing the
sibling's, and not *its* reading of the terms it is bound by); a placeholder to make the suite green
(it would read as a rendering and count as done while saying nothing); letting the household
transcribe it (the same fault with more steps); judging after writing (the archive would carry text
about itself that its own suite rejects).

**Anchor:** the sibling is a party to the constitution, not a copy of it. Its obligations have to be
*its* account in its own voice, because that is what makes the terms legible to the learner a decade
later -- and a rendering written by anyone else would make the household's instrument the archive's
authority, which §5.9 of the format spec exists to prevent.

**Consequence, accepted:** a fresh archive is non-conforming until the rite is performed -- check 11
fails, and the session says the same in plain words. The gap is visible rather than papered over; the
declaration is the format's and the body is the sibling's, recorded in provenance
(`constitution_rendered`); and re-rendering after the constitution is revised is a deliberate act,
never a consolidation pass, which may not touch the sibling's voice (I7).

## D-009 A turn that recites the brief is not a turn

**Decided:** the sibling's turn is judged before it enters the record, and the one thing that
disqualifies it is **recitation** — eight words copied in a row from the instructions it was
given. A refused turn is replaced by the archive's own line and recorded as fallback.

**Against:** trusting the trailing reminder. `TURN_REMINDER` already tells the model not to restate
its instructions, the loop or the facts it was given; at ~2,000 tokens of standing orders the local
4B stopped obeying it and copied the loop block back verbatim. Observed, not supposed — and a
request that is ignored is not a contract. Against validating length or warmth on a turn (that is
the greeting's contract; applied to a turn it would refuse ordinary speech). Against letting a
recited turn into the record (the archive would then hold, as the sibling's own words, text about
the design — the confusion I7 and the two-narrative rule exist to prevent).

**Anchor:** a validator that asked only for good manners would have passed the observed failure. The
question has to be *whose words these are*. A greeting is one line about the past; a turn is the
sibling thinking, and a sibling that answers a question with its own instructions has said nothing.

**Consequence:** the contract is narrow and says so; it fails visibly and in the session
(`how: fallback`), while the record carries the line the sibling actually said, never the
recitation; and it does not touch what the turn is *about*. Its evidence is two selftest
cases — a model that recites the brief is refused, a model that speaks ordinarily ships unchanged.
Open question left open on purpose: entries may carry unknown fields (format spec §4), but
*stating* a fallback marker in the entry belongs in §5.5 with the rest of the entry schema, not
as a side effect of this fix.
