---
title: Cognitive Sibling — Archive Format Specification
date: 2026-10-10
version: tessera/0.1
status: draft for review
tags:
  - cognitive-sibling
  - archive-format
  - spec
  - preservation
---

# Cognitive Sibling Archive — Format Specification (*Tessera*)

**Format identifier:** `tessera/0.1` · **Name:** *Tessera*, after the *tessera hospitalis* (§2.2) · **Status:** draft for review · **Supersedes:** the archive sketch in §3.2 of [[Cognitive Sibling — Prototype Specification]] v0.1.

Companion to [[Cognitive Sibling — Prior Art and Format Survey]] (what exists and what we borrow) and [[Cognitive Sibling — Design Brief]] (why any of this is required).

## 1. Purpose and non-goals

The sibling's identity is the archive, not the model that animates it. Therefore the archive is the durable engineering object, and it needs a specification with a decades-long design horizon: readable after the runtime, the operating system, the embedding model, the hardware, and possibly the author are gone.

**In scope.** A directory format for one sibling's archive; the semantics of its files; the forgetting mechanisms; the backup and restore procedure; a conformance test.

**Non-goals.** Not a database format. Not an API. Not a chat-log format. Not a multi-user or multi-device format. Not optimised for retrieval scores — this is deliberately not a benchmark-maximising design.

**Relationship to the constitution.** Every archive carries a `CONSTITUTION.md` — [[Cognitive Sibling — Constitution]] (`constitution/1.0`) — holding the four pillars, invariants I1–I12, the duties of the four parties bound by it, and the sibling's own rights. That document is authoritative on **what may be done with this archive, and by whom**; this one is authoritative on **how the archive is stored**. Where the two conflict, the constitution wins: the archive exists to serve the bond, not the reverse. It reads it at the start of every turn (§4), so it is a required file rather than a documentation courtesy.

## 2. Design principles

Derived from the invariants; each is *testable*, not aspirational.

| # | Principle | Test |
|---|---|---|
| P1 | **Plain text is the store.** UTF-8, human-readable, human-editable. No proprietary container. | It opens in a text editor, unchanged, in 20 years |
| P2 | **Derived data is disposable.** Every index, vector, or cache can be deleted and rebuilt with zero loss. | Delete `memory/index/`, rebuild, diff — nothing is missing |
| P3 | **Provenance or it does not exist.** Every derived claim traces to a record entry. | No assertion without a non-empty `evidence` list |
| P4 | **The record is append-only.** History is corrected by addition, never by rewriting. | A record file's existing bytes never change |
| P5 | **Forgetting is a right, and it survives backup.** | Erase something, restore from the oldest bag, assert it is still gone |
| P6 | **The archive never fetches.** Opening it contacts nothing. | No network access occurs when the archive is opened or read |
| P7 | **Two authors.** The narrative is co-authored and the sibling's own self is its own. | `narrative/we.md` and `memory/blocks/persona.md` both have a non-human author |
| P8 | **No third-party infrastructure.** Replication only to media the household physically controls. | No cloud endpoint in any documented procedure |

P1–P8 are the yardstick by which any future change to this format is judged.

### 2.1 Substrate — decided

The memory format is **plain-text files with this documented schema, plus a purely derived index**. There is no database and no vector store in the durable path: SQLite is not the system of record, and any embedding store is a cache that may be deleted at any time without loss (P2).

Measured on a synthetic ten-year archive at the chosen `deliberate` record policy: **12.9 MB on disk, 73 ms to load the whole archive into memory, 47 ms to rebuild the lexical index from scratch, 0.66 ms per indexed query.** A database would be 2.3× smaller and faster, and is still the wrong choice — it fails P1 and P2 and optimises properties that are not scarce at this scale.

The full argument and the measurements are in [[Cognitive Sibling — Decision Memory Format]]. Revisit only if the archive exceeds ~1 GB, a full scan over the record exceeds ~500 ms, or an index rebuild exceeds ~5 s — and in that case the answer is a better **index**, never a new store.

### 2.2 The name — decided

The format is **Tessera** (`tessera/0.1`), after the *tessera hospitalis*. In Roman *hospitium* the two parties to a bond of guest-friendship each held a small token — bronze, bone or ivory, usually figurative — which identified them to one another; producing and comparing the tokens (*tesseram conferre*) was how the bond was proved, and the obligation was honoured by their descendants. The scholarship works from the recognition scene in Plautus' *Poenulus*, and the tokens functioned much as the Greek *symbolon* did: an object that authenticates a relationship rather than the person carrying it alone.

Every load-bearing property of this design is already in that object: **two parties** rather than one user and one tool (P7); the archive as the *pair's* joint object rather than either one's private record; proof by **collation rather than trust** — you do not take the bearer's word for it, you set the two halves beside each other and see whether they answer; and **durability across generations**, which is the design's horizon. The conformance suite is the *collatio*: the archive's half set against the spec's half.

One thing to say plainly rather than lean on. The strong form of the metaphor — a single token physically snapped in two, the jagged fracture unforgeable, only the original halves fitting — is the Greek *symbolon*, and the Roman recognition token as staged in *Poenulus*; the sources do not establish that every *tessera hospitalis* was physically split. The claim this spec leans on is the weaker, well-attested one: a token kept by each party, compared to prove the bond, and inheritable. The name is a fit, not evidence.

Two collisions, recorded honestly so nobody has to rediscover them: geology uses *tessera* for ridged terrain on Venus, and NASA has flown a cubesat called TESSERA. Neither is a file format; the identifier `tessera/0.1` disambiguates, and the coinage `tessera-hospitalis` is available if either ever becomes a problem.

## 3. The three layers, and the authority rule

The format separates three things that every other system conflates. This separation is the core move, and it is what lets both "never paraphrase the person" and "forgetting is the default" be true at once.

| Layer | Directory | Nature | Authority | Mutability |
|---|---|---|---|---|
| **Record** | `record/`, `events/` | verbatim, dated | what *happened* — the source of truth | append-only; erasure only |
| **Memory** | `memory/` | distilled, decaying, consolidating | what the sibling can *call to mind* | freely rewritten, decays, rebuildable |
| **Narrative** | `narrative/` | co-authored, written | what the pair *make of it* | human-authored, versioned |

**The authority rule.** Where the layers disagree about a fact, the record wins; where they disagree about *meaning*, the narrative wins; and the memory layer is always derivable and always disposable.

**Why the split matters.** A model that decides what to remember decides what a person's history contains — that is editorial power over a childhood. Keeping the record verbatim and append-only denies the model that power. Keeping the *memory* decaying and the *index* disposable means the sibling still forgets like a person, and no permanent surveillance log of daily life accumulates by default (see §6.1).

## 4. Directory layout

```
sibling/
├── SPEC.md                     # this specification, embedded — the archive describes itself
├── manifest.json               # identity, format version, policy
├── CONSTITUTION.md             # the sibling's own rendering of its constitution (§5.9); read every turn
│
├── record/                     # LAYER 1 — verbatim, append-only
│   └── 2026/2026-10.jsonl
├── events/                     # named events, one directory each, with attachments
│   └── 2026-10-05-first-algebra-failure/
│       ├── event.md
│       └── attachments/
│
├── memory/                     # LAYER 2 — living memory: decays, consolidates, rebuilds
│   ├── blocks/                 #   one file per memory block
│   │   ├── persona.md          #     the sibling's own self
│   │   ├── learner.md          #     the sibling's model of the learner
│   │   ├── unknown.md          #     its honest knowledge gaps (feeds the WE-loop)
│   │   ├── method.md           #     how this learner works, learns, decides
│   │   └── relationship.md     #     shared rituals, jokes, references
│   ├── graph/
│   │   ├── entities.jsonl
│   │   ├── relations.jsonl     #     bi-temporal, with evidence
│   │   └── trails/             #     named associative paths (Bush)
│   └── index/                  #   DERIVED, DISPOSABLE — vectors, BM25, caches
│       └── CACHE.md            #     "delete this whole directory at will"
│
├── narrative/                  # LAYER 3 — co-authored
│   ├── we.md                   #   written by both, together
│   ├── learner.md              #   the learner's own first-person account
│   └── sibling.md              #   the sibling's own account of the journey
│
├── learning/
│   ├── curriculum.md           #   what we are working on, and why
│   ├── taught/                 #   ancestry of the sibling's world-knowledge (I1 audit)
│   └── search-log/             #   where WE went to find out; what came back
│
├── consent/
│   ├── consent.md              #   who may read what, when
│   └── handover.md             #   the handover act, when it happens
│
├── sealed/                     # sealed space — excluded from guardian reads (§5.6)
├── eval/indicators.jsonl       #   longitudinal telos indicators
│
├── tombstones.jsonl            # erasure log — replayed on every restore
└── provenance.jsonl            # archive events: created, migrated, exported, restored
```

Two conventions: **directory names are stable and are part of the format**; **unknown directories and unknown fields must be ignored, never rejected** — that is how a 20-year-old reader survives fields it has never seen.

## 5. File formats

### 5.1 `manifest.json`

```json
{
  "format": "tessera/0.1",
  "archive_id": "sib-7f3a…",
  "created": "2026-10-05T09:00:00+02:00",
  "sibling_name": "…",
  "learner_ref": "ent-learner",
  "record_policy": "deliberate",
  "guardian_read_excludes": ["sealed/"],
  "sealed": { "encrypted": true, "key_ref": "learner-held" },
  "layers": { "record": "record/", "memory": "memory/", "narrative": "narrative/" },
  "extensions": {}
}
```

`record_policy` is `deliberate` (utterances are recorded only when the pair marks them) or `continuous` (§5.2). `extensions` is where future versions add fields without breaking old readers.

### 5.2 The record — `record/YYYY/YYYY-MM.jsonl`

One JSON object per line, appended, never rewritten.

| Field | Type | Meaning |
|---|---|---|
| `id` | string | stable, sortable: `evt-20261005-0012` |
| `t` | ISO-8601 + offset | when it happened (*world* time) |
| `t_rec` | ISO-8601 + offset | when it was recorded (*system* time; differs on later transcription) |
| `kind` | enum | `utterance` · `event` · `attempt` · `failure` · `teaching` · `reflection` · `decision` · `trail-entry` · `system` |
| `actor` | enum | `learner` · `sibling` · `guardian` · `teacher` · `system` |
| `text` | string | **verbatim.** May be empty for pure events |
| `lang` | BCP-47 | `en`, `de`, … |
| `refs` | [id] | links to entities, trails, events, files |
| `supersedes` | id \| null | the correction discipline — see below |
| `private` | bool | if true, this entry lives in `sealed/` and is excluded from guardian reads |
| `tomb` | id \| null | set only when erased; normally `null` |

**Correction discipline.** A factual error is never edited away. A correction is a *new* record whose `supersedes` names the old one. Both remain. This is why the record is trustworthy: you can see that something was believed, and that it was later corrected — which is precisely the property that makes it usable as evidence of a person's development.

**Record policy.** Default `deliberate`: the record holds what the pair chose to mark — events, failures, teachings, decisions, reflections — not a transcript of every utterance. Conversation is transient by default. This honours "forgetting is the default" while keeping the verbatim floor for what *is* recorded, and it avoids accumulating a decade-long passive log of a childhood. `continuous` (record everything) is permitted by the format and discouraged by the design; if it is ever used, `manifest.json` must say so plainly and the learner must be able to see it.

### 5.3 Memory blocks — `memory/blocks/<block>.md`

The Letta *memory block* as a file: one block, one file, YAML frontmatter plus content.

```markdown
---
block: unknown
description: What the sibling does not know. Maintained honestly; feeds the WE-loop.
limit_chars: 4000
writable_by: sibling        # sibling | learner | both | read-only
revision: 12
updated: 2026-10-05
---
- Gaussian elimination: why a row swap is needed when the pivot is zero. The learner
  explained the mechanics on 2026-10-07; I still cannot say why the *order* matters.
- I do not know what she meant by "the feeling of the room" on 2026-10-04.
```

The standard blocks are `persona` (the sibling's own self — **writable by the sibling alone**: this is the structural guarantee that it is not a mirror), `learner`, `unknown`, `method`, `relationship`. Blocks are always in context, so `limit_chars` is a real budget, and a block that overflows must be split or consolidated rather than silently truncated.

### 5.4 The graph

**`entities.jsonl`** — `{"id":"ent-learner","type":"person","name":"…","first_seen":"…","aliases":[…],"tomb":null}`

**`relations.jsonl`** — the temporal, evidenced edge:

```json
{"id":"rel-0001","s":"ent-learner","p":"fears","o":"lit:\"being wrong in front of the class\"",
 "valid_from":"2026-10-05","valid_to":null,
 "t_created":"2026-10-05T14:22:03+02:00","t_invalid":null,
 "evidence":["evt-20261005-0012"],"confidence":0.7,"salience":0.9,
 "rehearsals":2,"last_recalled":"2026-10-09T19:02:11+02:00",
 "author":"sibling","tomb":null}
```

Four time fields, because two questions are different questions: `t_created`/`t_invalid` is what *the archive* believed and when; `valid_from`/`valid_to` is what was true *in the world* and when. Contradictory new information **invalidates** the old edge (`t_invalid` set) rather than deleting it — the record of having once believed it is kept.

`confidence`, `salience`, `rehearsals`, `last_recalled` are the memory-decay state (§6.1). `evidence` is mandatory: **a relation with empty `evidence` is invalid and must not be surfaced.** This single rule is the anti-hallucination mechanism, the provenance requirement, and the audit hook for invariant I1 (world-knowledge must trace to a learner-authored entry) all at once.

**`trails/<name>.jsonl`** — Bush's primitive, which nobody has since implemented as data:

```json
{"id":"trail-algebra-2026","name":"Why elimination works","created":"2026-10-05",
 "authors":["learner","sibling"],"status":"open",
 "steps":[{"ref":"evt-20261005-0012","note":"first failure"},
          {"ref":"learning/taught/elimination.md","note":"came back with the mechanics"}],
 "tomb":null}
```

A trail is a named, ordered path through the archive, created by hand. It is how a pile of entries becomes a thought — and it is the natural unit for the pair's shared work.

### 5.5 The narrative — `narrative/`

- `we.md` — **co-authored.** The jointly written account of the journey: what they did, what it cost, what changed. Written by learner and sibling together, in turns, with authorship marked. This is the artifact the whole design exists to produce, and the object named in §8.
- `learner.md` — the learner's own first-person account, written by the learner alone.
- `sibling.md` — the sibling's own account, written by the sibling alone.

These three are **different documents and must never be merged**. Conflating "what she says about herself" with "what it says about her" is the failure that destroys first-personification, which is one of the four indicators the programme is trying to measure. Two authors writing one file concurrently is a collaborative-editing problem with a known answer: a CRDT (Automerge/Yjs), or turn-taking with an explicit authorship mark. For v0.1, turn-taking.

### 5.6 The sealed space — `sealed/`

Things the learner tells the sibling in confidence during the guardian window. Behaviour:

- **Excluded from guardian reads** by declaration in `manifest.json` (`guardian_read_excludes`).
- **Encrypted at rest**, unlocked per session by the learner. Without this, "sealed" is a promise rather than a property, and this design prefers properties. It also gives a clean semantic: when the learner locks the sealed space, *the sibling genuinely cannot read it* — confidentiality becomes a deliberate act, not a secret.
- The sibling states the terms plainly and up front, and never promises secrecy it cannot keep.
- At handover, the key stays with the learner; the guardian's read path is gone by construction.

**Cost, stated honestly:** if the key is lost, the sealed contents are unrecoverable. That is consistent with the archive's mortal character, and it must be said to the learner before they use the space.

### 5.7 `tombstones.jsonl` — the erasure log

```json
{"id":"tomb-0003","t":"2027-06-01T09:12:00+02:00","actor":"learner",
 "targets":["evt-20270112-0004","rel-0112"],
 "scope":["record","memory","narrative","sealed","index"],"reason":"private"}
```

Append-only. Every erasure writes one. It exists for one reason: **a backup taken before an erasure still contains the erased thing** (§7.4). Replaying tombstones on restore is what makes the right to erasure survive being backed up.

### 5.8 `provenance.jsonl` — archive events

PREMIS-lite, because the archive has a history too:

```json
{"id":"prv-0007","event":"migration","t":"2029-03-02T10:00:00+01:00","actor":"system",
 "detail":{"from":"tessera/0.1","to":"tessera/0.2","tool":"tessera-migrate 0.2.0"},
 "fixity":{"files":412,"sha256_root":"…"}}
```

Events: `created`, `migration`, `export`, `restore`, `fixity_check`, `handover`, `erasure`, `constitution_rendered` (§5.9). Format migrations are recorded here and **never rewrite record entries** — they may add fields; they may not alter history.

### 5.9 `CONSTITUTION.md` — the sibling's rendering of its constitution

The archive carries **the sibling's own account of what it is and what it owes**, in its own
voice, and the sibling reads it at the start of every turn (§4; [[Cognitive Sibling — Prototype Specification]] §3.4). The binding instrument — the four pillars, invariants I1–I12, the duties of
the four parties and the sibling's own rights — is the household's document
([[Cognitive Sibling — Constitution]], `constitution/1.0`) and does not live in the archive.
**The rendering is the sibling's; the constitution is the household's.**

Frontmatter is flat `key: value`, the format's only frontmatter form (§5.3), with list values
written inline:

```yaml
---
document: constitution
renders: constitution/1.0
writable_by: sibling
revision: 4
updated: 2026-10-05
pillars: [consideration-for-all-members, empty-centredness, fellowship-model, rights-of-final-decision-making]
invariants: [I1, I2, I3, I4, I5, I6, I7, I8, I9, I10, I11, I12]
discloses: [guardian-window, study-window]
---
```

Four rules:

- **`writable_by` must be `sibling`.** The rendering is written by the sibling alone and no
  consolidation pass may overwrite its voice (invariant I7). This is the same rule as `persona`.
- **`renders` names the version it answers to**, so a reader a decade later knows a binding text
  exists and which one this is a reading of.
- **The three declarations state coverage**: all four pillars, all twelve invariants, both
  disclosure windows. A rendering that drops a clause is a conformance failure, not a style choice.
- **A declaration may not be hollow.** Each declared invariant is also rendered in the body,
  tagged `**I<n> --`. Check 11 asserts this, so "declared complete" and "actually complete" are
  the same statement.

**How it comes to exist -- the first act.** The rendering is not shipped with the archive and not
written by the household's hand: **the sibling writes it, once, in its first act in a new archive**
(`sib.py --constitution <the household's constitution.md> --render-constitution`). Three rules make
that safe with a model in the loop:

- **The binding text is quoted, never restated.** The helper extracts the *named* sections of the
  household's own document -- the four pillars, the twelve, the two disclosure windows -- and puts
  that text to the sibling. A restatement written into a tool would drift from the instrument it
  answers to, and the archive would carry a rendering of a copy. Sections are found by name and not
  by line, so the rite survives the household editing its own text.
- **The declaration is the format's; the body is the sibling's.** The helper writes the frontmatter
  above verbatim, with no model near it, and the model writes the body. The provenance entry records
  the division (`declaration_by`, `body_by`), so a reader can tell whose words were whose.
- **It is judged before it is written.** The candidate is declared, rendered and put through check
  11 exactly as the suite would judge the archive, in a scratch directory. One that fails is handed
  back to the sibling with the complaint, once. Nothing enters the archive until it passes, and
  **a fresh archive holds no `CONSTITUTION.md` at all rather than a placeholder**: an unwritten
  rendering is a visible gap, which check 11 names in words, while a template would read as a
  rendering and be a lie. This is the one file whose *absence* is the honest state.

The act is journalled -- `constitution_rendered` in `provenance.jsonl`, with the revision and what
was declared. A fresh archive therefore fails check 11 until the rite is performed and passes it
afterwards, so the two states are distinguishable from the archive alone. Re-rendering after the
constitution is revised is a further deliberate act, never a consolidation pass (which may not
touch the sibling's voice, I7).

**Why the binding text is not embedded, though `SPEC.md` is.** The self-description rule (§8)
applies to the *format*, which has no other home. The constitution has one — the household — and an
archive carrying its own normative text would be its own authority. What belongs beside the
sibling is the sibling's account of its obligations, not the instrument that binds everyone else.

**The cost, stated.** An archive recovered without the household's copy of the constitution gives
a future reader the sibling's rendering and the version it answers to, but not the binding text.
So the constitution is to be kept *with* the archive, on the same media, and the `renders` field is
how a reader knows there is something to look for.

## 6. Forgetting

Three mechanisms, deliberately distinct. Confusing them is what makes the forgetting/backup tension insoluble.

### 6.1 Decay — automatic, continuous
`confidence` and `salience` decay on a half-life. Unrehearsed relations fall below the surfacing threshold and stop being retrievable. The **memory** fades the way a person's does. The **record** is untouched: fading is not erasure.

### 6.2 Consolidation — scheduled, "the dream"
A cheap local auxiliary model runs on idle: compress episodes into relations and narrative, refresh `relationship`, update salience, and *propose* retirements from the blocks. Proposals are visible to the learner; nothing is deleted silently. This is Letta's sleep-time compute applied to a relationship rather than a codebase.

### 6.3 Erasure — learner-initiated, rare, absolute
1. write a tombstone to `tombstones.jsonl`;
2. remove the target from `record/` (and `events/`), `memory/`, `narrative/`, `sealed/`, and `memory/index/`;
3. advance the retention clock so the next backup no longer contains it;
4. state plainly what remains on old media and what it takes to remove it (§7.4).

### 6.4 Retrieval scoring
Score by **developmental significance**, never recency. Operationally: `salience` (maintained in the dream pass), narrative role, rehearsal count, and graph proximity to the current curriculum item. Recency may be *a* term; it must never be the objective. There is an explicit test for this in the conformance suite, because a recency-maximising retriever silently destroys the sibling and nothing in a normal test suite would notice.

## 7. Backup, media, and restore

### 7.1 Media
Replication is permitted **only to media the household physically controls**: an external drive, a NAS on the household's own network. Never a cloud service, never a sync provider, never a third party. This restates invariant I3 correctly — the requirement was never "no copies", it was **no third-party infrastructure**.

### 7.2 Package format — BagIt
Each snapshot is serialised as a **BagIt bag** (RFC 8493): payload under `data/`, `bagit.txt`, `manifest-sha256.txt`, `tagmanifest-sha256.txt`, `bag-info.txt` (source, creation date, format version, archive id, record policy). Using a 20-year-old preservation standard here means the backup is readable by existing preservation tooling, not only by our own code.

```
sibling-2026-10-05.bag/
├── bagit.txt
├── bag-info.txt
├── manifest-sha256.txt
├── tagmanifest-sha256.txt
└── data/sibling/…            # the whole archive, verbatim
```

### 7.3 Retention — decided

**Snapshots.** Daily at 22:00 local, plus an event-triggered snapshot on any erasure, handover or migration.

**Generational rotation.** **30 daily · 12 weekly · 24 monthly · annual kept indefinitely.** The annuals are the archival floor — one per year, ~13 MB each at the measured size (§2.1), cheap enough that there is never a reason to drop one.

**Air gap.** Exactly one bag off the rotation, on an external drive that is disconnected by default and swapped in weekly. Maximum exposure of the offline copy: **7 days**.

**Fixity.** Verified on write; a full scrub of every retained bag **quarterly**; a bag that fails verification is reported and never silently used.

**Why these numbers.** They are chosen against the threats rather than at random: hours (a mistaken deletion) are covered by daily; weeks (ransomware, a bad migration) by weekly; months (undetected corruption) by monthly; years (a decision that was wrong, slowly discovered) by the annuals. Implementation: `tessera_bag.py` (`create` · `verify` · `restore`).

The whole schedule costs well under 1 GB per decade, so storage is not the binding constraint — the erasure-propagation window in §7.4 is, and these numbers must not promise more than it can deliver.

### 7.4 Restore, and the erasure problem

Procedure: choose a bag → verify fixity → **overlay the current `tombstones.jsonl` and replay it, newest tombstone set winning** → rebuild `memory/index/`. Restored state is therefore always post-erasure.

**The journal rule, and why it is the subtle one.** A bag taken *before* an erasure cannot contain the tombstone for it. Restoring that bag and replaying only what the bag happens to hold would therefore **resurrect** the erased bytes — the exact failure the log exists to prevent. So `tombstones.jsonl` is the one file with **synchronous replication**: it is journalled to the household media the moment an erasure happens, ahead of the regular rotation. Erasure is the only operation with a shorter durability path than everything else, and it has to be, because a right to erasure that is only as good as the last backup is not a right. (Conformance check 5 exercises this directly: it restores a pre-erasure bag against the current journal, and keeps an un-replayed control to prove the check is not vacuous.)

**The erasure window, as a number** — not "honest remainder", but a bounded, stated cost:

| Where | How long the erased bytes can persist |
|---|---|
| the live archive | **immediate** (§6.3) |
| the next snapshot | **≤ 24 h** (daily cadence) |
| every bag older than 12 months | re-cut with tombstones applied at the quarterly scrub — so **≤ 12 months** on any household medium |
| the offline copy | **≤ 7 days**, or immediate if the learner asks for the medium to be destroyed |

**Re-cutting and the append-only rule.** Applying tombstones when a bag is re-cut does not violate P4: re-cutting removes only what the learner erased, and the tombstone preserves the fact that it existed. A `rotate` event is written to `provenance.jsonl` so conformance check 4 can tell a permitted re-cut from an unpermitted rewrite. Rotation never drops anything from the *live* archive — retention governs snapshots, never the archive itself.

### 7.5 Encryption
Whole-archive encryption at rest is an option, not a requirement of the format, but is recommended for the backup media (an external drive in a house is a drive that leaves the house). If used, the key is the household's, never a vendor's, and `manifest.json` records that the payload is encrypted so a future reader knows why it cannot read it.

## 8. Model independence: how the archive outlives its runtime

Three mechanisms, in increasing order of strength.

1. **The embedded spec.** `SPEC.md` is the format's own description. The archive can be recovered from the archive.
2. **The reference reader.** `tessera.py` — standard library only, no dependencies, ~330 lines including the CLI. It reads the record, rebuilds the graph and index, and renders a plain-text view. Rule: *an archive is valid if the reference reader can rebuild everything derived from it.* It ships inside the bag.
3. **The conformance suite.** `tessera_conformance.py` implements all thirteen checks of Appendix B and is meant to re-run on every backup. It is built to be falsifiable: `--selftest` constructs deliberately broken archives — a binary blob, a relation with no evidence, a quietly rewritten record entry, an absolute-path leak, a deleted spec, a non-deterministic index, a no-op tombstone replay, a recency-maximising retriever, a reader that fetches, a record entry whose id disagrees with its own timestamp, an out-of-order record, a reference left dangling where a tombstone belongs, and a relation recalled before it was created — and asserts that each one is caught. A suite that cannot fail proves nothing.

**The durability rule, stated once:** *the archive survives if a stranger with `cat`, a text editor, and `SPEC.md` can read it, and if the reference reader can rebuild it.* Every design decision above is downstream of that sentence.

## 9. Interoperability profiles

| Profile | Purpose | Status |
|---|---|---|
| **`obsidian`** | the human view: the archive *is* a vault (markdown, YAML frontmatter, wikilinks) | v0.1 default |
| **`mcp-memory`** | export/import entities · relations · observations, so any MCP-capable tool can read the graph | v0.1 export only |
| **`rdf-star`** | lossless conversion to RDF-star / SPARQL-star for long-term semantic tooling | planned |
| **`solid-mirror`** | read-only mirror for third-party readers | **rejected for v0.1** — it creates an outward path, and an outward path is a leak surface (I1) |

## 10. Deliberately not in the format

- **No embeddings in the archive.** They live only in `memory/index/`, which is disposable (P2).
- **No absolute paths, hostnames, or usernames** outside `manifest.json`. The archive must be movable between machines byte-for-byte, or it is trapped on the machine it was born on.
- **No fetchable references.** URLs appear only as opaque strings inside text; the archive never resolves one, so opening a 20-year-old archive contacts nothing (P6). An archive that never fetches cannot leak by being opened.
- **No model-generated narrative without human authorship.** `we.md` is written, not generated. A model may propose a draft; the pair writes it.
- **No silent schema changes.** Unknown fields are ignored; changes are recorded in `provenance.jsonl`.

## 11. Open questions

1. **Record policy — resolved.** `deliberate`: conversation is transient; the record holds what the pair marked. Both the ethical choice and the reason the format stays simple — 12.9 MB for a decade rather than 141 MB.
2. **Sealed-space encryption — resolved.** Yes: a per-session unlock held by the learner, which makes sealedness a property rather than a promise. A lost key is a permanent loss, and the learner is told so before use.
3. **The sibling's own files — resolved.** `narrative/sibling.md` and `memory/blocks/persona.md` are **study data**, available to the research team throughout, so faults can be diagnosed and the design improved. The consequence is a disclosure obligation: the sibling must be told, in the constitution, that its own journal is read. See [[Cognitive Sibling — Decision Memory Format]] §8.
4. **The name — resolved.** *Tessera* (`tessera/0.1`), §2.2. The collation metaphor (*tesseram conferre*) also names what the conformance suite does, which is the sign the name fits rather than merely appeals.
5. **Retention numbers — resolved.** §7.3: 30 daily · 12 weekly · 24 monthly · annual indefinitely, one air-gapped copy at ≤ 7 days exposure, a quarterly scrub, and a hard **12-month** cap on the erasure-propagation window.

## Appendix A — a minimal archive

```
sibling/
  SPEC.md
  manifest.json
  CONSTITUTION.md
  record/2026/2026-10.jsonl
  memory/blocks/{persona,learner,unknown,method,relationship}.md
  memory/graph/{entities.jsonl,relations.jsonl}
  memory/graph/trails/
  memory/index/CACHE.md
  narrative/{we,learner,sibling}.md
  learning/{curriculum.md,taught/,search-log/}
  consent/{consent.md,handover.md}
  sealed/
  eval/indicators.jsonl
  tombstones.jsonl
  provenance.jsonl
```

`record/2026/2026-10.jsonl`, one line:

```json
{"id":"evt-20261005-0012","t":"2026-10-05T14:20:41+02:00","t_rec":"2026-10-05T14:20:44+02:00",
 "kind":"failure","actor":"learner","lang":"en",
 "text":"I could not get the elimination step to work again. I think I am just bad at this.",
 "refs":["trail-algebra-2026"],"supersedes":null,"private":false,"tomb":null}
```

That single line is the whole design in miniature: dated in two times, verbatim, addressed to a trail, append-only, erasable.

## Appendix B — conformance checklist

| # | Check | Pass condition |
|---|---|---|
| 1 | Plain-text inspection | every file opens in a text editor unaltered |
| 2 | Index rebuild | delete `memory/index/`; rebuild; diff against pre-deletion state — identical |
| 3 | Provenance | no relation lacks `evidence` |
| 4 | Append-only | no record entry has been rewritten in place between snapshots, except by a tombstone or a recorded `rotate` |
| 5 | Erasure survives restore | erase → restore a pre-erasure bag against the current journal → target absent, with an un-replayed control proving the check is not vacuous |
| 6 | No fetch | opening and reading the archive performs no network access |
| 7 | Two authors | `narrative/we.md` and `memory/blocks/persona.md` carry non-human authorship |
| 8 | Portability | copy the archive to another machine and another user; it still reads |
| 9 | Significance over recency | a high-salience old entry outranks a low-salience recent one in retrieval |
| 10 | Self-description | `SPEC.md` present and sufficient to build a reader |
| 11 | Constitution rendering | `CONSTITUTION.md` present, written by the sibling alone, declaring — and rendering — all four pillars, all twelve invariants and both disclosure windows |
| 12 | Record integrity | every `evt-YYYYMMDD-NNNN` id carries the date of its own `t`; `t` never runs backwards within a file; `t_rec` never precedes `t`; no id appears twice |
| 13 | Reference integrity | every `refs` · `evidence` · `supersedes` · trail-step reference resolves to a live or tombstoned id, and nothing is recalled or invalidated before it was created |

## See also

[[Cognitive Sibling — Prior Art and Format Survey]] · [[Cognitive Sibling — Design Brief]] · [[Cognitive Sibling — Prototype Specification]] · [[Cognitive Sibling — Research Skeleton]]
