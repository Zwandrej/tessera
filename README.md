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
| `SPEC.md` | the normative format specification (copy of the vault document) |

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

To have the sibling write its own rendering of the household's constitution -- its first act in a new
archive, and the one file a fresh archive deliberately does not carry (spec §5.9):

```sh
python3 sib.py --archive <dir> --voice <model> \
    --constitution "<the household's constitution.md>" --render-constitution
```

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

**Apache-2.0** — see [`LICENSE`](LICENSE). It covers the code and the format specification in
`SPEC.md` alike, and the patent grant is deliberate: the point of a format is that other people
implement it. Copyright (c) 2026 Andrej Zwitter.

## Citing this work

The programme is **the Cognitive Sibling**; the archive format it defines is **Tessera,
`tessera/0.1`**, and this repository is its reference implementation. It accompanies:

> Deguchi, Y. & Zwitter, A. *The Cognitive Sibling: Existential AI and Teleological Alignment in
> Education* (in preparation).

The format is versioned and the reader is the law: a `tessera/0.1` archive is valid if the reader
in this repository can rebuild everything derived from it, and a new version that a reader cannot
follow is a new format, not a revision of this one.
