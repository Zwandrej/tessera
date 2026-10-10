#!/usr/bin/env python3
"""Tessera reference reader.

Standard library only, by design (SPEC.md 8.2).  An archive is valid if this
reader can rebuild everything derived from it, using nothing that can be
uninstalled and touching nothing off the machine (P6).

    python3 tessera.py read   <archive>    plain-text view
    python3 tessera.py index  <archive>    rebuild memory/index/ from the layers
    python3 tessera.py check  <archive>    reader-level self-checks
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import re
import sys
from pathlib import Path

FORMAT = "tessera/0.1"

# Memory decay.  Salience halves every HALF_LIFE_DAYS, and rehearsal lengthens
# the half-life, so what is revisited fades more slowly.  Fading is not erasure
# (SPEC.md 6.1): the record is untouched by any of this.
HALF_LIFE_DAYS = 180.0
REHEARSAL_SLOWDOWN = 0.5
SURFACE_THRESHOLD = 0.05

TOKEN = re.compile(r"[a-z0-9']+")


# ---------------------------------------------------------------------------
# reading primitives
# ---------------------------------------------------------------------------

def read_jsonl(path):
    """Return (rows, n_unparseable).  Blank lines are ignored; bad lines are
    counted, not fatal -- a reader that dies on one bad byte loses the archive."""
    rows, bad = [], 0
    path = Path(path)
    if not path.exists():
        return rows, bad
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
    return rows, bad


def parse_frontmatter(text):
    """Flat `key: value` front matter only.  Deliberately not YAML: the format
    never needs more, and a reader meant to run in twenty years should not
    depend on a YAML parser still existing."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, val = line.split(":", 1)
            meta[key.strip()] = val.strip().strip('"').strip("'")
    return meta, text[end + 4:]


def parse_time(value):
    """ISO-8601 with or without an offset; date-only accepted."""
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        stamp = datetime.datetime.fromisoformat(text)
    except ValueError:
        try:
            stamp = datetime.datetime.fromisoformat(text[:10])
        except ValueError:
            return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=datetime.timezone.utc)
    return stamp


def tokenize(text):
    return TOKEN.findall((text or "").lower())


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, obj):
    """Deterministic serialisation, so a rebuilt index can be diffed byte for byte."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, sort_keys=True, indent=1)
        fh.write("\n")


# ---------------------------------------------------------------------------
# the archive
# ---------------------------------------------------------------------------

class Archive:
    """Reader for one archive.  Unknown files, directories and fields are
    ignored, never rejected (SPEC.md 4)."""

    def __init__(self, root):
        self.root = Path(root)
        manifest = self.root / "manifest.json"
        if not manifest.exists():
            raise FileNotFoundError(f"not a Tessera archive (no manifest.json): {self.root}")
        self.manifest = json.loads(manifest.read_text(encoding="utf-8"))

    # -- layer 1: the record -------------------------------------------------
    def records(self):
        rows, bad = [], 0
        for path in sorted((self.root / "record").rglob("*.jsonl")):
            got, count = read_jsonl(path)
            rows += got
            bad += count
        return rows, bad

    # -- erasure -------------------------------------------------------------
    def tombstones(self):
        return read_jsonl(self.root / "tombstones.jsonl")[0]

    def erased_ids(self):
        """Every id named by a tombstone.  Erasure is not reversible in this
        format, so the union of all tombstone target sets is the semantics."""
        dead = set()
        for stone in self.tombstones():
            dead |= set(stone.get("targets", []))
        return dead

    # -- layer 2: memory ----------------------------------------------------
    def entities(self):
        return read_jsonl(self.root / "memory/graph/entities.jsonl")[0]

    def relations(self, stored=False):
        rows, _ = read_jsonl(self.root / "memory/graph/relations.jsonl")
        if stored:
            return rows
        dead = self.erased_ids()
        live = []
        for row in rows:
            if row.get("id") in dead or row.get("tomb"):
                continue                     # erased
            if not row.get("evidence"):
                continue                     # P3: provenance or it does not exist
            if row.get("t_invalid"):
                continue                     # contradicted: kept, not surfaced
            live.append(row)
        return live

    def blocks(self):
        out = {}
        for path in sorted((self.root / "memory/blocks").glob("*.md")):
            meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
            out[meta.get("block") or path.stem] = {
                "meta": meta, "body": body.strip(), "path": path}
        return out

    def trails(self):
        rows = []
        for path in sorted((self.root / "memory/graph/trails").glob("*.jsonl")):
            rows += read_jsonl(path)[0]
        return rows

    # -- decay and significance ---------------------------------------------
    def decay(self, rel, now):
        salience = float(rel.get("salience", 0.0))
        when = parse_time(rel.get("last_recalled") or rel.get("t_created"))
        if when is None:
            return salience
        days = max(0.0, (now - when).total_seconds() / 86400.0)
        half_life = HALF_LIFE_DAYS * (1.0 + REHEARSAL_SLOWDOWN * float(rel.get("rehearsals", 0)))
        return salience * math.pow(0.5, days / half_life)

    def significance(self, rel, now):
        """Rank for retrieval.  Deliberately NOT recency (SPEC.md 6.4): there
        is no recency term at all, so a recent trivial item can never outrank an
        old salient one.  Conformance check 9 exists for exactly this."""
        return self.decay(rel, now) * float(rel.get("confidence", 1.0))

    def surfaced(self, now=None, limit=None):
        now = now or datetime.datetime.now(datetime.timezone.utc)
        ranked = sorted(self.relations(), key=lambda r: -self.significance(r, now))
        ranked = [r for r in ranked if self.significance(r, now) >= SURFACE_THRESHOLD]
        return ranked[:limit] if limit else ranked

    # -- derived index (P2: disposable) -------------------------------------
    def rebuild_index(self):
        """Rebuild memory/index/ from the plain-text layers alone.  Deterministic,
        so delete-and-rebuild can be verified by comparing hashes."""
        dest = self.root / "memory/index"
        dest.mkdir(parents=True, exist_ok=True)
        records, _ = self.records()
        dead = self.erased_ids()
        postings = {}
        for row in records:
            if row.get("id") in dead:
                continue
            for token in sorted(set(tokenize(row.get("text", "")))):
                postings.setdefault(token, []).append(row.get("id"))
        write_json(dest / "lexical.json", {
            "format": FORMAT,
            "built_from": "record/",
            "documents": len(records),
            "postings": {tok: sorted(ids) for tok, ids in sorted(postings.items())},
        })
        write_json(dest / "graph.json", {
            "format": FORMAT,
            "built_from": "memory/graph/",
            "entities": sorted(e.get("id") for e in self.entities()),
            "relations": sorted(r.get("id") for r in self.relations()),
        })
        (dest / "CACHE.md").write_text(
            "# Derived data -- delete this whole directory at will\n\n"
            "Everything here is rebuilt from `record/`, `memory/graph/` and the blocks "
            "by `tessera.py index`.  Nothing in it is a source of truth (P2).\n",
            encoding="utf-8")
        return dest

    def index_hash(self):
        dest = self.root / "memory/index"
        digest = hashlib.sha256()
        for path in sorted(dest.rglob("*")):
            if path.is_file():
                digest.update(str(path.relative_to(dest)).encode())
                digest.update(sha256_file(path).encode())
        return digest.hexdigest()

    # -- plain-text view ----------------------------------------------------
    def render(self, now=None):
        now = now or datetime.datetime.now(datetime.timezone.utc)
        records, bad = self.records()
        stored = self.relations(stored=True)
        live = self.relations()
        out = []
        add = out.append
        add(f"=== Tessera archive: {self.root} ===")
        add(f"format      {self.manifest.get('format')}")
        add(f"sibling     {self.manifest.get('sibling_name')}")
        add(f"created     {self.manifest.get('created')}")
        add(f"policy      {self.manifest.get('record_policy')}")
        add("")
        add(f"records     {len(records)}  ({bad} unparseable)")
        add(f"entities    {len(self.entities())}")
        add(f"relations   {len(live)} live / {len(stored)} stored")
        add(f"trails      {len(self.trails())}")
        add(f"blocks      {', '.join(sorted(self.blocks()))}")
        add(f"erased      {len(self.erased_ids())} target(s)")
        add("")
        add("-- memory blocks (always in context) --")
        for name, block in sorted(self.blocks().items()):
            meta = block["meta"]
            head = block["body"].splitlines()[0] if block["body"] else ""
            add(f"[{name}] {head}")
            add(f"        revision {meta.get('revision', '?')}, "
                f"writable_by={meta.get('writable_by', '?')}, "
                f"limit {meta.get('limit_chars', '-')} chars, {len(block['body'])} used")
        add("")
        add("-- most significant relations (significance, not recency) --")
        for rel in self.surfaced(now, limit=10):
            add(f"{self.significance(rel, now):.3f}  {rel.get('s')} {rel.get('p')} "
                f"{rel.get('o')}   [evidence {len(rel.get('evidence', []))}, "
                f"rehearsals {rel.get('rehearsals', 0)}]")
        add("")
        add("-- trails --")
        for trail in self.trails():
            add(f"{trail.get('id')}  \"{trail.get('name')}\"  ({trail.get('status')}, "
                f"{len(trail.get('steps', []))} steps, {','.join(trail.get('authors', []))})")
        return "\n".join(out)


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description="Tessera reference reader (stdlib only).")
    subs = parser.add_subparsers(dest="cmd", required=True)
    for name, helptext in (("read", "plain-text view of the archive"),
                           ("index", "rebuild memory/index/ from the layers"),
                           ("check", "reader-level self-checks")):
        sub = subs.add_parser(name, help=helptext)
        sub.add_argument("archive")
    args = parser.parse_args(argv)
    arch = Archive(args.archive)

    if args.cmd == "read":
        print(arch.render())
        return 0

    if args.cmd == "index":
        arch.rebuild_index()
        print(f"rebuilt memory/index/  hash {arch.index_hash()[:16]}...")
        return 0

    problems = []
    if not (arch.root / "SPEC.md").exists():
        problems.append("SPEC.md missing (self-description, check 10)")
    _, bad = arch.records()
    if bad:
        problems.append(f"{bad} unparseable record line(s)")
    for rel in arch.relations(stored=True):
        if not rel.get("evidence"):
            problems.append(f"relation {rel.get('id')} has no evidence (P3)")
    for message in problems:
        print("FAIL", message)
    if not problems:
        print("ok -- reader-level checks pass (full suite: tessera_conformance.py)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
