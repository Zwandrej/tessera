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
| `mkfixture.py` | builds the example archive used by the suite and the demos |
| `sib.py` · `sibling.html` | the session helper — the only tap to the model and the only writer of the archive — and its one-file page |
| `SPEC.md` | the normative format specification (copy of the vault document) |

## Run it

```sh
python3 mkfixture.py examples/minimal
python3 tessera.py read examples/minimal          # render the archive
python3 tessera.py index examples/minimal         # rebuild memory/index/ (derived, disposable)
python3 tessera.py check examples/minimal         # reader-level validity
python3 tessera_conformance.py examples/minimal   # the thirteen checks
python3 tessera_conformance.py --selftest         # prove the checks can fail
python3 sib.py --archive examples/minimal --port 8799   # a session; then open sibling.html
python3 sib.py --selftest                              # 22/22: nothing is written outside the archive
```

To compare two states (conformance check 4, append-only):

```sh
python3 tessera_conformance.py <archive> --previous <earlier-snapshot>
```

## The four rules this code exists to enforce

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

v0.1 — 2026-10-10. Verified: **12/12 executed checks pass** on a valid archive (check 4
skipped), **13/13** when run against a previous snapshot so append-onlyness is actually
compared, and `--selftest` catches **all 15 injected faults** — binary blob, unevidenced
relation, rewritten history, absolute-path leak, deleted spec, deleted constitution, a
constitution that declares a clause it never renders, non-deterministic index, no-op
tombstone replay, recency-maximising retriever, reader that fetches, a record entry whose
id disagrees with its own timestamp, an out-of-order record, evidence pointing at a
missing event, a relation recalled before it was created.

The session helper carries its own hermetic selftest — **23/23** — asserting the one thing
the interface is answerable for: a session run in a sandbox home writes nothing outside the
archive, the model's name appears in no file, one writer per file holds, a greeting is
refused unless it satisfies its contract, and the greeting is never told that the
sibling's own words were the learner's.

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

Your answer is kept in `settings.json` beside this file — a path, a port and an endpoint, and
nothing else. It is not needed to read the archive: copy the archive anywhere and it still opens.

    python3 sib.py                 # no arguments: serve the settings screen
    python3 sib.py                 # with settings already written: open the session
    python3 sib.py --archive DIR   # an archive directly, ignoring settings
    python3 sib.py --open          # the session on the command line, no page
    python3 sib.py --selftest      # 29 checks, no model and no network needed
