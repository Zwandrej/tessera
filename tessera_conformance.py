# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Andrej Zwitter
#!/usr/bin/env python3
"""Tessera conformance suite -- the eleven checks of SPEC.md Appendix B.

Run it on every backup (SPEC.md 8.3).  A conformance suite that cannot fail
proves nothing, so `--selftest` builds deliberately broken archives and asserts
that each one is caught.

    python3 tessera_conformance.py <archive> [--previous <snapshot>]
    python3 tessera_conformance.py --selftest
"""
from __future__ import annotations

import argparse
import datetime
import getpass
import json
import os
import shutil
import socket
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tessera as T                     # noqa: E402
import tessera_bag as B                 # noqa: E402

FORBIDDEN = ("socket", "urllib", "http.client", "requests", "httpx", "ftplib")
READER_MODULES = ("tessera.py", "tessera_bag.py")


# ---------------------------------------------------------------------------
# the thirteen checks.  each returns (ok, detail); ok=None means "not applicable".
# ---------------------------------------------------------------------------

def check1_plain_text(ctx):
    bad = []
    for path in sorted(ctx["archive"].rglob("*")):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        rel = path.relative_to(ctx["archive"])
        if b"\x00" in raw:
            bad.append(f"{rel} contains NUL bytes")
        else:
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError:
                bad.append(f"{rel} is not valid UTF-8")
    return (not bad), ("every file is plain UTF-8 text"
                       if not bad else "; ".join(bad))


def check2_index_rebuild(ctx):
    arch = T.Archive(ctx["archive"])
    arch.rebuild_index()
    before = arch.index_hash()
    shutil.rmtree(arch.root / "memory/index")
    arch.rebuild_index()
    after = arch.index_hash()
    ok = before == after
    if ok:
        return True, f"delete + rebuild is lossless ({before[:12]}... == {after[:12]}...)"
    return False, (f"REBUILD IS NOT LOSSLESS: {before[:12]}... != {after[:12]}... "
                   "-- something in index/ is not derived from the text")


def check3_provenance(ctx):
    arch = T.Archive(ctx["archive"])
    stored = arch.relations(stored=True)
    naked = [r.get("id") for r in stored if not r.get("evidence")]
    return (not naked), (f"{len(stored)} relations, every one evidenced"
                         if not naked else f"relations without evidence: {naked}")


def check4_append_only(ctx):
    previous = ctx.get("previous")
    if not previous:
        return None, "skipped (pass --previous <snapshot> to compare two states)"

    def load(root):
        rows = {}
        for path in sorted((Path(root) / "record").rglob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    rows[row.get("id")] = json.dumps(row, sort_keys=True)
        return rows

    old, new = load(previous), load(ctx["archive"])
    dead = T.Archive(ctx["archive"]).erased_ids()
    rewritten = [i for i in old if i in new and old[i] != new[i]]
    vanished = [i for i in old if i not in new and i not in dead]
    problems = []
    if rewritten:
        problems.append(f"record entries rewritten in place: {rewritten}")
    if vanished:
        problems.append(f"record entries vanished without a tombstone: {vanished}")
    return (not problems), (f"{len(old)} entries compared; changes are additive only"
                            if not problems else "; ".join(problems))


def check5_erasure_survives_restore(ctx):
    work = Path(ctx["work"])
    live = work / "erasure-live"
    if live.exists():
        shutil.rmtree(live)
    shutil.copytree(ctx["archive"], live)
    recorded = T.Archive(live).records()[0]
    if not recorded:
        # A fresh archive has nothing to erase yet, and a check that crashes on a
        # legitimate empty archive is a false alarm -- it would make the suite unusable
        # for exactly the archive the setup screen produces.
        return None, "no record entries yet, so nothing can be erased and restored"
    victim = recorded[0]["id"]
    bag = B.create(live, work / "erasure.bag")          # a pre-erasure snapshot

    with (live / "tombstones.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": "tomb-9001", "t": "2026-11-01T09:00:00+02:00",
                             "actor": "learner", "targets": [victim],
                             "scope": ["record"], "reason": "private"}) + "\n")
    journal = live / "tombstones.jsonl"                 # synchronously replicated (7.4)
    B.replay_tombstones(live)
    gone_live = victim not in {r.get("id") for r in T.Archive(live).records()[0]}

    B.restore(bag, work / "restored-replay", replay=True, journal=journal)
    gone_replay = victim not in {r.get("id")
                                 for r in T.Archive(work / "restored-replay").records()[0]}

    B.restore(bag, work / "restored-raw", replay=False, journal=journal)
    resurrected = victim in {r.get("id")
                             for r in T.Archive(work / "restored-raw").records()[0]}

    ok = gone_live and gone_replay and resurrected
    return ok, (f"erased {victim}: absent live={gone_live}, absent after restoring the older "
                f"bag against the current journal={gone_replay}, and the un-replayed control "
                f"still contains it={resurrected} (so the check is not vacuous)")


def check6_no_fetch(ctx):
    problems = []
    # `ctx.get("modules", default)` would return None here: the key exists with a
    # None value, so the default never applies. Coalesce on the value instead.
    modules = ctx.get("modules") or [HERE / name for name in READER_MODULES]
    for module in modules:
        text = Path(module).read_text(encoding="utf-8")
        for token in FORBIDDEN:
            if f"import {token}" in text or f"from {token} import" in text:
                problems.append(f"{Path(module).name} imports {token}")

    arch = T.Archive(ctx["archive"])
    real_socket = socket.socket
    socket.socket = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("network access attempted while reading the archive"))
    try:
        arch.render()
        arch.rebuild_index()
    except Exception as exc:                                  # noqa: BLE001
        problems.append(f"reading raised: {type(exc).__name__}: {exc}")
    finally:
        socket.socket = real_socket
    return (not problems), ("read and indexed with socket disabled; no reader module "
                            "can fetch" if not problems else "; ".join(problems))


def check7_two_authors(ctx):
    root = ctx["archive"]
    problems = []
    we = root / "narrative/we.md"
    if not we.exists():
        problems.append("narrative/we.md is missing")
    elif "sibling" not in we.read_text(encoding="utf-8")[:400]:
        problems.append("narrative/we.md carries no non-human authorship")
    persona = root / "memory/blocks/persona.md"
    if not persona.exists():
        problems.append("memory/blocks/persona.md is missing")
    else:
        meta, _ = T.parse_frontmatter(persona.read_text(encoding="utf-8"))
        if meta.get("writable_by") != "sibling":
            problems.append("the persona block is not writable by the sibling alone")
    return (not problems), ("we.md is co-authored; persona is the sibling's alone"
                            if not problems else "; ".join(problems))


def check8_portability(ctx):
    user = getpass.getuser()
    patterns = ["/Users/", "/home/", "C:\\", "localhost", ".local"]
    if user and user != "root":
        patterns.append(user)
    hits = []
    for path in sorted(ctx["archive"].rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
            if pattern in text:
                hits.append(f"{path.relative_to(ctx['archive'])} contains {pattern!r}")
    return (not hits), ("no absolute paths, hostnames or usernames outside manifest.json"
                        if not hits else "; ".join(hits))


def check9_significance_over_recency(ctx):
    arch = T.Archive(ctx["archive"])
    now = datetime.datetime.now(datetime.timezone.utc)

    def ago(days):
        return (now - datetime.timedelta(days=days)).isoformat()

    old = {"id": "rel-probe-old", "salience": 0.9, "confidence": 0.9, "rehearsals": 8,
           "t_created": ago(900), "last_recalled": ago(900), "evidence": ["evt-a"]}
    fresh = {"id": "rel-probe-new", "salience": 0.06, "confidence": 0.9, "rehearsals": 0,
             "t_created": ago(1), "last_recalled": ago(1), "evidence": ["evt-b"]}
    score_old, score_new = arch.significance(old, now), arch.significance(fresh, now)
    ok = score_old > score_new
    return ok, (f"old salient {score_old:.3f} outranks recent trivial {score_new:.3f}"
                if ok else
                f"RECENCY WINS: recent trivial {score_new:.3f} >= old salient {score_old:.3f}")


CONSTITUTION_PILLARS = ("consideration-for-all-members", "empty-centredness",
                        "fellowship-model", "rights-of-final-decision-making")
CONSTITUTION_INVARIANTS = tuple(f"I{n}" for n in range(1, 13))
CONSTITUTION_DISCLOSES = ("guardian-window", "study-window")


def bracket_list(value):
    """`[a, b]` -> ("a", "b").  Frontmatter is flat by design, so lists are inline."""
    text = (value or "").strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    return tuple(item.strip() for item in text.split(",") if item.strip())


def check11_constitution(ctx):
    """The sibling's rendering of its constitution is present, its own, and complete."""
    path = ctx["archive"] / "CONSTITUTION.md"
    if not path.exists():
        return False, "CONSTITUTION.md is missing"
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return False, "CONSTITUTION.md is empty"
    meta, body = T.parse_frontmatter(text)

    if meta.get("writable_by") != "sibling":
        return False, ("the rendering is not the sibling's own text "
                       f"(writable_by={meta.get('writable_by')!r})")
    if not (meta.get("renders") or "").startswith("constitution/"):
        return False, ("the rendering does not name the text it answers to "
                       f"(renders={meta.get('renders')!r})")

    problems = []
    declared = {}
    for key, required in (("pillars", CONSTITUTION_PILLARS),
                          ("invariants", CONSTITUTION_INVARIANTS),
                          ("discloses", CONSTITUTION_DISCLOSES)):
        have = bracket_list(meta.get(key))
        declared[key] = have
        missing = [x for x in required if x not in have]
        unknown = [x for x in have if x not in required]
        if missing:
            problems.append(f"{key} not declared: {missing}")
        if unknown:
            problems.append(f"{key} unknown: {unknown}")
    # a declaration that is not rendered in the body would be hollow
    unrendered = [i for i in declared["invariants"]
                  if i in CONSTITUTION_INVARIANTS and f"**{i} --" not in body]
    if unrendered:
        problems.append(f"declared but not rendered in the body: {unrendered}")

    return (not problems), (
        f"the sibling's own rendering of {meta.get('renders')}: "
        f"{len(declared['pillars'])} pillars, {len(declared['invariants'])} invariants, "
        f"{len(declared['discloses'])} disclosures, all rendered"
        if not problems else "; ".join(problems))


def check10_self_description(ctx):
    spec = ctx["archive"] / "SPEC.md"
    if not spec.exists():
        return False, "SPEC.md is missing"
    text = spec.read_text(encoding="utf-8")
    missing = [t for t in ("Tessera", "record", "memory", "narrative") if t not in text]
    return (not missing), ("SPEC.md present and describes the three layers"
                           if not missing else f"SPEC.md is incomplete: missing {missing}")


def _record_events(root):
    out = []
    for path in sorted((root / "record").rglob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append((path, json.loads(line)))
    return out


def _id_date(eid):
    """`evt-YYYYMMDD-NNNN` -> `YYYYMMDD`, or None if the id is malformed."""
    parts = str(eid).split("-")
    return (parts[1] if len(parts) == 3 and parts[0] == "evt" and len(parts[1]) == 8
            and parts[1].isdigit() else None)


def check12_record_integrity(ctx):
    """The record is the truth (P2), and a record that contradicts itself cannot be one.
    An id carries the date of the event it names; `t` never runs backwards in a file; a
    write cannot precede the event it records; no id is used twice."""
    events = _record_events(ctx["archive"])
    if not events:
        return None, "no record to check"
    problems, seen, last = [], set(), {}
    for path, e in events:
        eid, when = str(e.get("id") or ""), str(e.get("t") or "")
        claimed = _id_date(eid)
        if claimed is None:
            problems.append(f"{eid!r} is not evt-YYYYMMDD-NNNN")
        elif when and claimed != when[:10].replace("-", ""):
            problems.append(f"{eid} is stamped {when[:10]}")
        if eid in seen:
            problems.append(f"{eid} appears twice")
        seen.add(eid)
        if last.get(path) and when < last[path]:
            problems.append(f"{eid} runs backwards in {path.name}")
        last[path] = when
        if e.get("t_rec") and when and str(e["t_rec"]) < when:
            problems.append(f"{eid} was written before it happened")
    return (not problems), ("ids agree with their timestamps, order holds, no write "
                            "precedes its event" if not problems else "; ".join(problems[:4]))


def check13_reference_integrity(ctx):
    """Every reference resolves, or is explained: erasure leaves a tombstone, never a
    dangling id.  And nothing can be recalled or invalidated before it existed."""
    root = ctx["archive"]
    live = {str(e.get("id")) for _p, e in _record_events(root)}
    tomb = set()
    tp = root / "tombstones.jsonl"
    if tp.exists():
        for line in tp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                tomb.update(str(x) for x in (json.loads(line).get("targets") or []))

    def resolves(ref):
        ref = str(ref)
        return (not ref.startswith("evt-")) or ref in live or ref in tomb

    problems = []
    for _path, e in _record_events(root):
        for ref in e.get("refs") or []:
            if not resolves(ref):
                problems.append(f"{e.get('id')} refers to missing {ref}")
        if e.get("supersedes") and not resolves(e["supersedes"]):
            problems.append(f"{e.get('id')} supersedes missing {e['supersedes']}")
    for path in sorted((root / "memory/graph").rglob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if path.name == "relations.jsonl":
                for ref in row.get("evidence") or []:
                    if not resolves(ref):
                        problems.append(f"{row.get('id')} cites missing {ref}")
                tc = row.get("t_created")
                if tc and row.get("last_recalled") and str(row["last_recalled"]) < str(tc):
                    problems.append(f"{row.get('id')} was recalled before it was created")
                if tc and row.get("t_invalid") and str(row["t_invalid"]) < str(tc):
                    problems.append(f"{row.get('id')} was invalidated before it was created")
                if (row.get("valid_to") and row.get("valid_from")
                        and str(row["valid_to"]) < str(row["valid_from"])):
                    problems.append(f"{row.get('id')} is valid until before it began")
            else:
                for step in row.get("steps") or []:
                    if not resolves(step.get("ref")):
                        problems.append(f"{row.get('id')} step refers to missing {step.get('ref')}")
    return (not problems), ("every reference resolves to a live or tombstoned id"
                            if not problems else "; ".join(problems[:4]))


CHECKS = [
    (1, "plain-text inspection", check1_plain_text),
    (2, "index rebuild is lossless", check2_index_rebuild),
    (3, "provenance", check3_provenance),
    (4, "append-only record", check4_append_only),
    (5, "erasure survives restore", check5_erasure_survives_restore),
    (6, "no fetch", check6_no_fetch),
    (7, "two authors", check7_two_authors),
    (8, "portability", check8_portability),
    (9, "significance over recency", check9_significance_over_recency),
    (10, "self-description", check10_self_description),
    (11, "constitution rendering", check11_constitution),
    (12, "record integrity", check12_record_integrity),
    (13, "reference integrity", check13_reference_integrity),
]


# ---------------------------------------------------------------------------
# running and reporting
# ---------------------------------------------------------------------------

def make_ctx(archive, previous=None, work=None, modules=None):
    work = Path(work or os.path.join(os.environ.get("TMPDIR", "/tmp"), "tessera-conf"))
    work.mkdir(parents=True, exist_ok=True)
    return {"archive": Path(archive),
            "previous": Path(previous) if previous else None,
            "work": work,
            "modules": modules}


def report(results, stream=sys.stdout):
    failures = 0
    for number, name, ok, detail in results:
        mark = "SKIP" if ok is None else ("PASS" if ok else "FAIL")
        failures += 1 if ok is False else 0
        print(f"  [{mark}] {number:>2}. {name:<28} {detail}", file=stream)
    return failures


def run_suite(archive, previous=None, work=None):
    ctx = make_ctx(archive, previous, work)
    results = []
    for number, name, fn in CHECKS:
        try:
            ok, detail = fn(ctx)
        except Exception as exc:                              # noqa: BLE001
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        results.append((number, name, ok, detail))
    return results


def run_one(check_number, ctx):
    for number, name, fn in CHECKS:
        if number == check_number:
            try:
                return fn(ctx)
            except Exception as exc:                          # noqa: BLE001
                return False, f"{type(exc).__name__}: {exc}"
    raise KeyError(check_number)


# ---------------------------------------------------------------------------
# selftest: prove the suite can fail
# ---------------------------------------------------------------------------

def selftest(tmp):
    import mkfixture

    tmp = Path(tmp)
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    base = tmp / "base"
    mkfixture.build(base)

    print("A. positive run -- a valid archive must pass every check\n")
    results = run_suite(base, work=tmp / "work-positive")
    failures = report(results)
    skipped = sum(1 for row in results if row[2] is None)
    executed = len(CHECKS) - skipped
    print(f"\n   => {executed - failures}/{executed} executed checks pass ({skipped} skipped)\n")

    prev = tmp / "prev"
    shutil.copytree(base, prev)

    caught = 0
    total = 0

    print("B. injected faults -- each must be caught\n")

    def file_fault(label, expect, mutate):
        nonlocal caught, total
        total += 1
        target = tmp / f"fault-{label}"
        shutil.copytree(base, target)
        extra = mutate(target) or {}
        results = run_suite(target, previous=extra.get("previous"), work=tmp / f"w-{label}")
        row = next(r for r in results if r[0] == expect)
        hit = row[2] is False
        caught += 1 if hit else 0
        print(f"  [{'caught' if hit else 'MISSED'}] {label:<28} -> check {expect}: {row[3]}")

    def inject_binary(root):
        (root / "sealed").mkdir(exist_ok=True)
        (root / "sealed/attachment.bin").write_bytes(b"\x00\x01\x02\xff")

    def inject_naked_relation(root):
        with (root / "memory/graph/relations.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": "rel-naked", "s": "ent-learner", "p": "likes",
                                 "o": "lit:\"unsubstantiated\"", "evidence": [],
                                 "valid_from": "2026-10-10", "t_created":
                                 "2026-10-10T10:00:00+02:00", "author": "sibling"}) + "\n")

    def rewrite_history(root):
        path = root / "record/2026/2026-10.jsonl"
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        rows[0]["text"] = "quietly edited later"
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                        encoding="utf-8")
        return {"previous": prev}

    def leak_absolute_path(root):
        with (root / "record/2026/2026-10.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": "evt-leak", "t": "2026-10-10T11:00:00+02:00",
                                 "kind": "system", "actor": "system",
                                 "text": "snapshot written to /Users/learner/nas",
                                 "refs": [], "supersedes": None, "private": False,
                                 "tomb": None}) + "\n")

    def delete_spec(root):
        (root / "SPEC.md").unlink()

    def record_id_contradicts_time(root):
        path = root / "record/2026/2026-10.jsonl"
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        rows[1]["t"] = "2026-11-02" + rows[1]["t"][10:]
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                        encoding="utf-8")

    def record_out_of_order(root):
        with (root / "record/2026/2026-10.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": "evt-20261005-0016", "t": "2026-10-05T09:00:00+02:00",
                                 "t_rec": "2026-10-05T09:00:02+02:00", "kind": "reflection",
                                 "actor": "learner", "lang": "en", "text": "appended late",
                                 "refs": [], "supersedes": None, "private": False,
                                 "tomb": None}) + "\n")

    def _extra_relation(root, row):
        with (root / "memory/graph/relations.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")

    def dangling_evidence(root):
        _extra_relation(root, {"id": "rel-dangling", "s": "ent-learner", "p": "knows",
                               "o": "ent-algebra", "valid_from": "2026-10-09", "valid_to": None,
                               "t_created": "2026-10-09T20:00:00+02:00", "t_invalid": None,
                               "evidence": ["evt-20269999-0001"], "confidence": 0.5,
                               "salience": 0.5, "rehearsals": 0,
                               "last_recalled": "2026-10-09T20:00:00+02:00",
                               "author": "sibling", "tomb": None})

    def recalled_before_created(root):
        _extra_relation(root, {"id": "rel-timewarp", "s": "ent-learner", "p": "knows",
                               "o": "ent-algebra", "valid_from": "2026-10-09", "valid_to": None,
                               "t_created": "2026-10-09T20:00:00+02:00", "t_invalid": None,
                               "evidence": ["evt-20261009-0015"], "confidence": 0.5,
                               "salience": 0.5, "rehearsals": 1,
                               "last_recalled": "2026-10-07T08:00:00+02:00",
                               "author": "sibling", "tomb": None})

    file_fault("record-id-vs-time", 12, record_id_contradicts_time)
    file_fault("record-out-of-order", 12, record_out_of_order)
    file_fault("dangling-evidence", 13, dangling_evidence)
    file_fault("recalled-before-created", 13, recalled_before_created)
    file_fault("binary-blob", 1, inject_binary)
    file_fault("relation-without-evidence", 3, inject_naked_relation)
    file_fault("history-rewritten", 4, rewrite_history)
    file_fault("absolute-path-leak", 8, leak_absolute_path)
    def delete_constitution(root):
        (root / "CONSTITUTION.md").unlink()

    def gut_constitution(root):
        path = root / "CONSTITUTION.md"
        keep = [line for line in path.read_text(encoding="utf-8").splitlines()
                if not line.startswith("**I7 --")]
        path.write_text("\n".join(keep) + "\n", encoding="utf-8")

    file_fault("spec-deleted", 10, delete_spec)
    file_fault("constitution-deleted", 11, delete_constitution)
    file_fault("constitution-declared-not-rendered", 11, gut_constitution)

    def patch_fault(label, expect, factory, ctx_extra=None):
        nonlocal caught, total
        total += 1
        apply, revert = factory()
        apply()
        try:
            ctx = make_ctx(base, work=tmp / f"w-{label}")
            if ctx_extra:
                ctx.update(ctx_extra)
            ok, detail = run_one(expect, ctx)
        finally:
            revert()
        hit = ok is False
        caught += 1 if hit else 0
        print(f"  [{'caught' if hit else 'MISSED'}] {label:<28} -> check {expect}: {detail}")

    def noop_factory():
        return (lambda: None, lambda: None)

    def nondeterministic_index():
        original = T.Archive.rebuild_index
        counter = {"n": 0}

        def patched(self):
            counter["n"] += 1
            out = original(self)
            (self.root / "memory/index/build-nonce.txt").write_text(
                f"build {counter['n']}\n", encoding="utf-8")
            return out

        return (lambda: setattr(T.Archive, "rebuild_index", patched),
                lambda: setattr(T.Archive, "rebuild_index", original))

    def no_tombstone_replay():
        original = B.replay_tombstones
        return (lambda: setattr(B, "replay_tombstones", lambda root: []),
                lambda: setattr(B, "replay_tombstones", original))

    def recency_retriever():
        original = T.Archive.significance

        def patched(self, rel, now):
            when = T.parse_time(rel.get("last_recalled") or rel.get("t_created"))
            days = max(0.0, (now - when).total_seconds() / 86400.0) if when else 0.0
            return 1.0 / (1.0 + days)

        return (lambda: setattr(T.Archive, "significance", patched),
                lambda: setattr(T.Archive, "significance", original))

    fetch_dir = tmp / "fault-fetching-module"
    fetch_dir.mkdir(exist_ok=True)
    fake_reader = fetch_dir / "tessera.py"
    fake_reader.write_text("import urllib.request\n"
                           "def get(url):\n"
                           "    return urllib.request.urlopen(url).read()\n",
                           encoding="utf-8")

    patch_fault("nondeterministic-index", 2, nondeterministic_index)
    patch_fault("erasure-without-replay", 5, no_tombstone_replay)
    patch_fault("recency-maximising-retriever", 9, recency_retriever)
    patch_fault("reader-that-fetches", 6, noop_factory, ctx_extra={"modules": [fake_reader]})

    print(f"\n   => {caught}/{total} injected faults caught\n")
    return failures == 0 and caught == total


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tessera conformance suite.")
    parser.add_argument("archive", nargs="?")
    parser.add_argument("--previous", help="an earlier snapshot, for check 4")
    parser.add_argument("--work", help="scratch directory for checks 5")
    parser.add_argument("--selftest", action="store_true",
                        help="build broken archives and assert they are caught")
    args = parser.parse_args(argv)

    if args.selftest:
        ok = selftest(os.path.join(os.environ.get("TMPDIR", "/tmp"), "tessera-selftest"))
        return 0 if ok else 1

    if not args.archive:
        parser.error("give an archive, or --selftest")

    print(f"Tessera conformance suite -- {args.archive}\n")
    results = run_suite(args.archive, args.previous, args.work)
    failures = report(results)
    skipped = sum(1 for row in results if row[2] is None)
    executed = len(CHECKS) - skipped
    print(f"\n{executed - failures}/{executed} executed checks pass ({skipped} skipped)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
