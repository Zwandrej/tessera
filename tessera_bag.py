#!/usr/bin/env python3
"""Tessera backup layer: BagIt bags, verification, and restore with tombstone replay.

SPEC.md 7.  The point of BagIt is not cleverness.  It is that the backup is
readable by preservation tooling that has existed for twenty years and will
exist in another twenty, and that corruption is *detected* rather than silent.

    python3 tessera_bag.py create  <archive> <bag>
    python3 tessera_bag.py verify  <bag> [more bags ...]
    python3 tessera_bag.py restore <bag> <dest>
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
import sys
from pathlib import Path

BAGIT_TXT = "BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n"
PAYLOAD_ROOT = "sibling"          # the archive directory name inside data/


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_files(root):
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            yield path


def create(archive, bag):
    """Serialise the archive as a bag.  The payload is the archive, verbatim."""
    archive, bag = Path(archive), Path(bag)
    if bag.exists():
        shutil.rmtree(bag)
    data = bag / "data" / PAYLOAD_ROOT
    data.parent.mkdir(parents=True)
    shutil.copytree(archive, data)
    (bag / "bagit.txt").write_text(BAGIT_TXT, encoding="utf-8")

    manifest = []
    for path in iter_files(data):
        manifest.append(f"{sha256(path)}  {path.relative_to(bag).as_posix()}")
    (bag / "manifest-sha256.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")

    meta = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
    payload = list(iter_files(data))
    oxum_bytes = sum(p.stat().st_size for p in payload)
    (bag / "bag-info.txt").write_text(
        "Source-Organization: household\n"
        f"Bagging-Date: {datetime.date.today().isoformat()}\n"
        "Bag-Software-Agent: tessera_bag.py (reference implementation)\n"
        f"Bag-Size: {oxum_bytes} bytes\n"
        f"Payload-Oxum: {oxum_bytes}.{len(payload)}\n"
        f"Archive-Id: {meta.get('archive_id', '')}\n"
        f"Format: {meta.get('format', '')}\n"
        f"Record-Policy: {meta.get('record_policy', '')}\n",
        encoding="utf-8")

    tagmanifest = [f"{sha256(bag / name)}  {name}"
                   for name in ("bagit.txt", "bag-info.txt", "manifest-sha256.txt")]
    (bag / "tagmanifest-sha256.txt").write_text(
        "\n".join(tagmanifest) + "\n", encoding="utf-8")
    return bag


def verify(bag):
    """Return (ok, problems).  Payload manifest first, then the tag manifest."""
    bag = Path(bag)
    problems = []
    for name in ("bagit.txt", "manifest-sha256.txt", "bag-info.txt", "tagmanifest-sha256.txt"):
        if not (bag / name).exists():
            problems.append(f"missing {name}")
    if problems:
        return False, problems

    for line in (bag / "manifest-sha256.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        path = bag / rel
        if not path.exists():
            problems.append(f"payload file missing: {rel}")
        elif sha256(path) != digest:
            problems.append(f"fixity failure: {rel}")

    for line in (bag / "tagmanifest-sha256.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split("  ", 1)
        if not (bag / name).exists():
            problems.append(f"tag file missing: {name}")
        elif sha256(bag / name) != digest:
            problems.append(f"tag fixity failure: {name}")
    return (not problems), problems


def replay_tombstones(root):
    """Make restored state post-erasure (SPEC.md 7.4).  Returns what was removed.

    A bag written before an erasure still physically contains the erased bytes.
    Replaying the tombstone log on restore is what stops a restore from
    resurrecting them -- which is the whole reason tombstones.jsonl exists.
    """
    root = Path(root)
    stones = root / "tombstones.jsonl"
    if not stones.exists():
        return []
    dead, dead_paths = set(), []
    for line in stones.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        for target in json.loads(line).get("targets", []):
            dead.add(target)
            if "/" in target:                    # a path target: event dir or file
                dead_paths.append(target)

    removed = []
    for layer in ("record", "memory/graph"):
        for path in sorted((root / layer).rglob("*.jsonl")):
            keep, changed = [], False
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    keep.append(line)            # never lose a line we cannot parse
                    continue
                if row.get("id") in dead:
                    changed = True
                    removed.append(row.get("id"))
                else:
                    keep.append(line)
            if changed:
                path.write_text("\n".join(keep) + ("\n" if keep else ""), encoding="utf-8")

    for target in dead_paths:
        path = root / target
        if path.is_dir():
            shutil.rmtree(path)
            removed.append(target)
        elif path.exists():
            path.unlink()
            removed.append(target)

    index = root / "memory/index"           # derived: rebuilt, never trusted
    if index.exists():
        shutil.rmtree(index)
    return removed


def restore(bag, dest, replay=True, journal=None):
    """Verify, then restore.  Refuses to restore from a bag that fails fixity.

    `journal` is the *current* `tombstones.jsonl`.  It matters, and this is the
    subtle one: a bag taken before an erasure cannot contain the tombstone for
    it, so restoring an old bag and replaying only what the bag happens to hold
    would resurrect the erased content.  The tombstone log is therefore the one
    file with synchronous replication (SPEC.md 7.4) -- it is journalled to the
    household media the moment an erasure happens, ahead of the regular
    rotation -- and restore overlays the current journal before replaying.
    """
    dest = Path(dest)
    ok, problems = verify(bag)
    if not ok:
        raise RuntimeError("refusing to restore from a bag that fails verification: "
                           + "; ".join(problems))
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(bag) / "data" / PAYLOAD_ROOT, dest)
    if journal:
        shutil.copyfile(journal, dest / "tombstones.jsonl")
    removed = replay_tombstones(dest) if replay else []
    return dest, removed


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tessera backup (BagIt, RFC 8493).")
    subs = parser.add_subparsers(dest="cmd", required=True)
    p_create = subs.add_parser("create", help="serialise an archive as a bag")
    p_create.add_argument("archive")
    p_create.add_argument("bag")
    p_verify = subs.add_parser("verify", help="check bag fixity")
    p_verify.add_argument("bags", nargs="+")
    p_restore = subs.add_parser("restore", help="restore a bag, replaying tombstones")
    p_restore.add_argument("bag")
    p_restore.add_argument("dest")
    args = parser.parse_args(argv)

    if args.cmd == "create":
        bag = create(args.archive, args.bag)
        ok, problems = verify(bag)
        print(f"created {bag}  verified={ok}  "
              f"payload files={sum(1 for _ in iter_files(bag / 'data'))}")
        return 0 if ok else 1

    if args.cmd == "verify":
        failed = 0
        for bag in args.bags:
            ok, problems = verify(bag)
            failed += 0 if ok else 1
            print(f"{'ok  ' if ok else 'FAIL'} {bag}")
            for problem in problems:
                print(f"       {problem}")
        return 1 if failed else 0

    dest, removed = restore(args.bag, args.dest)
    print(f"restored {args.bag} -> {dest}; tombstone replay removed {len(removed)} target(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
