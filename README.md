# Tessera — reference implementation of the Cognitive Sibling archive format

`tessera/0.1`. Standard library only. No dependencies, no network, no database.

**`SPEC.md` is the normative document.** It is a copy of
*Cognitive Sibling — Archive Format Specification* from the vault, and this code is
expected to conform to it — not the other way round. When they disagree, the code is wrong.

## Files

| File | Role |
|---|---|
| `tessera.py` | the reference reader — load, render, rebuild the index, `check` |
| `tessera_bag.py` | the BagIt backup layer — `create` · `verify` · `restore` (with tombstone replay) |
| `tessera_conformance.py` | the thirteen-check conformance suite, plus `--selftest` |
| `mkfixture.py` | builds the example archive *and the earlier state it is compared against* |
| `sib.py` · `sibling.html` | the session helper — the only tap to the model and the only writer of the archive — and its one-file page |
| `SPEC.md` | the normative format specification |
| `CONSTITUTION.md` | the binding text the format is subordinate to (`constitution/1.0`) |
| `docs/` | the design and research documents the specification refers to |

## The documents

The format is not self-contained without these, so they are here rather than only in the project's
research vault:

| Document | What it is |
|---|---|
| [`SPEC.md`](SPEC.md) | **Normative.** How the archive is stored. When this file and the code disagree, the code is wrong. |
| [`CONSTITUTION.md`](CONSTITUTION.md) | **Binding.** `constitution/1.0` — the four pillars, invariants I1–I12, the duties of the four parties, and the sibling's rights. It governs *what may be done with an archive, and by whom*; the specification governs how it is stored; where they conflict, this one wins. Licensed with the rest, so a household can adopt and amend it. |
| [`docs/decision-memory-format.md`](docs/decision-memory-format.md) | why the memory is plain text with a disposable index, and how that was decided |
| [`docs/prior-art-and-format-survey.md`](docs/prior-art-and-format-survey.md) | the systems this format was argued against, and what it takes from each |
| [`docs/design-brief.md`](docs/design-brief.md) | what the thing is for, and what it must never do |
| [`docs/prototype-specification.md`](docs/prototype-specification.md) | the study design the prototype is built to |
| [`docs/interface-specification.md`](docs/interface-specification.md) | the session helper and the page: what the interface is answerable for |

**One name, two different things.** An *archive* carries a file called `CONSTITUTION.md`, and it is
**not** this one: it is the sibling's own rendering — written by the sibling alone, in its own voice,
declaring which pillars, invariants and windows it speaks for, and read at the start of every turn
(spec §5.9, checked by conformance check 11). *The rendering is the sibling's; the constitution is
the household's.* A fresh archive deliberately carries no `CONSTITUTION.md` at all rather than a
placeholder.

The binding text is deliberately **not embedded in archives**, so it has to travel *with* one, on the
same media, beside the archive — which is why it is here.

Not published here: the research skeleton, the project index, and the two essay and article notes the
design brief rests on. They are vault-internal, and the documents above name them in plain text where
they would otherwise link.
These documents are **exported copies** of vault documents; the vault copies are the ones edited.

## Run it

```sh
python3 mkfixture.py examples/minimal               # archive + examples/minimal.prev
python3 tessera.py read examples/minimal          # render the archive
python3 tessera.py index examples/minimal         # rebuild memory/index/ (derived, disposable)
python3 tessera.py check examples/minimal         # reader-level validity
python3 tessera_conformance.py examples/minimal   # the thirteen checks
python3 tessera_conformance.py --selftest         # prove the checks can fail
python3 sib.py --archive examples/minimal --port 8799   # a session; then open sibling.html
python3 sib.py --selftest                              # 35/35: nothing is written outside the archive
```

To compare two states (conformance check 4, append-only):

```sh
python3 tessera_conformance.py examples/minimal --previous examples/minimal.prev
```

To have the sibling write its own rendering of the constitution -- its first act in a new archive,
and the one file a fresh archive deliberately does not carry (spec §5.9):

```sh
python3 sib.py --archive <dir> --voice <model> \
    --constitution CONSTITUTION.md --render-constitution
```

`CONSTITUTION.md` here is the binding text (`constitution/1.0`). Point the session at it, or at the
household's own amended copy -- Part IX of it says who may amend it, and how.

## The five rules this code exists to enforce

1. **The text is the archive.** Nothing derived is load-bearing — `memory/index/` can
   be deleted and rebuilt byte-identically at any time (check 2).
2. **No fetch.** The reader is verified statically *and* dynamically not to open a
   socket (check 6). The sealed space is enforced by the code, not by promise.
3. **Nothing enters the record without provenance** (check 3), and no record entry is
   ever rewritten in place except by a tombstone or a recorded `rotate` (check 4).
4. **Erasure survives restore.** `tombstones.jsonl` is the one synchronously
   replicated file and is replayed over any restored bag (check 5).
5. **The sibling's account of its own terms is checked.** `CONSTITUTION.md` is present,
   written by the sibling alone, names the constitution version it answers to, and declares
   *and* renders all four pillars, twelve invariants and both disclosure windows (check 11).

## Status

v0.1 — 2026-10-10. Every number below is from a run on this machine:

- **13/13 conformance checks** on the example pair (`examples/minimal` against
  `examples/minimal.prev`) with **0 skipped**: check 4 compares 5 entries across the two states,
  and check 5's un-replayed control proves the erasure check is not vacuous — a restored bag
  *without* the tombstone replay still contains the erased entry.
- **A fresh archive is 9/13, and that is the honest state**: three checks have nothing to look at
  yet, and **check 11 fails because the sibling has not yet written its rendering** — the one
  gap a new archive is meant to show (spec §5.9).
- **15/15 injected faults caught** by `tessera_conformance.py --selftest`: binary blob,
  unevidenced relation, rewritten history, absolute-path leak, deleted spec, deleted constitution,
  a constitution that declares a clause it never renders, non-deterministic index, no-op tombstone
  replay, recency-maximising retriever, reader that fetches, a record entry whose id disagrees with
  its own timestamp, an out-of-order record, evidence pointing at a missing event, a relation
  recalled before it was created.
- **35/35 helper checks** (`sib.py --selftest`), asserting what the interface is answerable for: a
  session run in a sandbox home writes nothing outside the archive, the model's name appears in no
  file, one writer per file holds, a greeting is refused unless it satisfies its contract and the
  greeting is never told the sibling's own words were the learner's, **a turn that recites the
  brief is refused** (the record carries the archive's own line instead, and the session reports
  `how: fallback`) while ordinary speech ships unchanged, and the rite holds — the declaration is the format's, the body
  is the sibling's, and a rendering that fails check 11 is refused with the complaint handed back to
  the sibling.
- **The rite, run for real**: against the household's own constitution and a local model, the
  sibling wrote a 907-word rendering of all four pillars, twelve invariants and both windows;
  check 11 passed afterwards; and the model's name appears in no file of the archive (I2).

Conformance check 4 is skipped unless `--previous <snapshot>` is supplied, because
append-onlyness is a statement about two states, not one.

## Deliberate non-goals

No encryption (the sealed space is the filesystem's job, see the spec §6), no
summarisation, no embeddings in the durable path, no network, no daemon. This is
meant to be runnable in ten years by whichever `python3` the household happens to have —
hence stdlib only, and no 3.10+ syntax.

## First run

Double-click **`Cognitive Sibling.command`**. It starts the helper, waits until it answers, and
opens the page. The first time, the page asks two things: which local model should speak, and
what the sibling is called.

Nothing is assumed about your machine. Eight common local servers are probed (LM Studio, Ollama,
llama.cpp, vLLM, Jan, KoboldCpp, llamafile, text-generation-webui) and a server is offered only
if it actually answers with a model list; models that cannot converse (embeddings, rerankers) are
not offered as the voice. Addresses other than this machine are refused.

Your answer is kept in `settings.json` beside this file — at most two paths (the archive, and the household's constitution if it gave
one), a port and an endpoint -- and nothing else. It is not needed to read the archive: copy the archive anywhere and it still opens.

    python3 sib.py                 # no arguments: serve the settings screen
    python3 sib.py                 # with settings already written: open the session
    python3 sib.py --archive DIR   # an archive directly, ignoring settings
    python3 sib.py --open          # the session on the command line, no page
    python3 sib.py --selftest      # 35 checks, no model and no network needed

## Licence

**Apache-2.0** — see [`LICENSE`](LICENSE). It covers the code, the format specification in
`SPEC.md`, the constitution and the documents in `docs/` alike, and the patent grant is deliberate:
the point of a format is that other people implement it. Copyright (c) 2026 Andrej Zwitter.

## Citing this work

The programme is **the Cognitive Sibling**; the archive format it defines is **Tessera,
`tessera/0.1`**, and this repository is its reference implementation. It accompanies:

> Deguchi, Y. & Zwitter, A. *The Cognitive Sibling: Existential AI and Teleological Alignment in
> Education* (in preparation).

The format is versioned and the reader is the law: a `tessera/0.1` archive is valid if the reader
in this repository can rebuild everything derived from it, and a new version that a reader cannot
follow is a new format, not a revision of this one.
