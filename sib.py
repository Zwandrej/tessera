#!/usr/bin/env python3
"""sib.py -- the companion for one Tessera archive.

Standard library only.  It does the two things the interface specification says
the page may not do for itself:

  1. it is the ONLY tap to the local model;
  2. it is the ONLY writer of the archive.

It is stateless -- no config file, no state directory, nothing outside the
archive.  That is enforced, not promised: every write goes through a guard that
refuses any path outside the archive root, and `--selftest` proves it by running
a whole session with HOME sandboxed and diffing.  It is also the reason the
surface is a derived artifact: this runs a session from a terminal with no page
at all (`--open`).

The model is chosen at invocation (`--voice`) and is deliberately NEVER written
into the archive.  The archive may record *that* the voice changed -- a fact
about its history, which the sibling is required to tell the learner -- but not
*which* model, or identity would be a function of the weights and the whole
claim would collapse.

    python3 sib.py --archive <dir> [--voice MODEL] [--port 8799] [--open]
    python3 sib.py --archive <dir> --revoice     # declare a voice replacement
    python3 sib.py --selftest                    # hermetic, no network
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import tessera  # noqa: E402  (same directory, stdlib-only reader)
import tessera_conformance as tc

DEFAULT_MODEL_URL = "http://127.0.0.1:1234/v1/chat/completions"
DEFAULT_PORT = 8799
MAX_BODY = 256 * 1024
MAX_TURNS_SENT = 12

LOOP = [
    "1. learner attempts      -- she tries first, and writes the attempt",
    "2. sibling attempts      -- you try too, honestly, and you may be wrong",
    "3. gap named             -- what neither of you can do goes on your list",
    "4. method taught         -- decomposition, search terms, source evaluation, verification",
    "5. [ learner goes out ]  -- she leaves the machine; you have nothing to do but wait",
    "6. learner teaches back  -- she explains it to you",
    "7. your state moves      -- you update what you understand from her account",
    "8. advance               -- the item closes",
]

BANNED = [
    "can't wait", "cannot wait", "miss you", "missed you", "excited", "so happy",
    "glad you", "welcome back", "streak", "don't forget", "proud of you",
    "great job", "well done", "awesome", "how are you", "!", "😀", "😊",
]

STOP = set("""the a an and or of to in is are was were it its this that you your we our i me my
for on with not just how why what do does did be been being have has had she her he his they them
at from as but if then than so about into over after before again more most some any no nor only own
same too very can could will would shall should may might must there here when where which who whom
there's it's i'm about because while""".split())

WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def now_iso():
    return dt.datetime.now(dt.timezone.utc).astimezone().replace(microsecond=0).isoformat()


def parse_ts(value):
    return tessera.parse_time(value)


def content_words(text, minlen=5):
    return {w.lower().strip("'’-") for w in WORD.findall(text or "")
            if len(w) >= minlen and w.lower() not in STOP}


def clip(text, n):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def is_loopback(url):
    m = re.match(r"https?://([^/:]+)", url or "")
    return bool(m) and m.group(1) in ("127.0.0.1", "localhost", "::1")


def sentences(text):
    return [s for s in re.split(r"(?<=[.?!])\s+", (text or "").strip()) if s.strip()]


# ---------------------------------------------------------------------------
# the two model roles (only one exists in v0.1)
# ---------------------------------------------------------------------------

class LocalModel:
    """The voice.  Loopback only -- a non-loopback URL is refused, because that
    refusal *is* invariant I1 as far as this program is concerned."""

    def __init__(self, name, url=DEFAULT_MODEL_URL, timeout=240, thinking=False):
        if not is_loopback(url):
            raise ValueError(f"refusing a non-loopback model URL (I1): {url}")
        self.name = name
        self.url = url
        self.timeout = timeout
        self.thinking = thinking

    def complete(self, system, messages, max_tokens=500, temperature=0.6):
        payload = {
            "model": self.name,
            "messages": [{"role": "system", "content": system}] + messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if not self.thinking:
            payload["reasoning_effort"] = "none"
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        try:
            data = _post_json(self.url, payload, self.timeout)
        except urllib.error.HTTPError:
            for key in ("reasoning_effort", "chat_template_kwargs"):
                payload.pop(key, None)
            data = _post_json(self.url, payload, self.timeout)
        return clean_reply(data["choices"][0]["message"]["content"])

    def complete_contract(self, system, messages, contract, **kw):
        """Deliver `contract` as the last thing the model reads.  A trailing system
        message is the strongest form and the least portable, so a server that rejects it
        gets the same text appended to the final user turn instead -- measured almost as
        good (60 words vs 45), and never silently dropped."""
        try:
            return self.complete(system, list(messages) + [{"role": "system", "content": contract}], **kw)
        except urllib.error.HTTPError:
            msgs = list(messages)
            msgs[-1] = {"role": msgs[-1].get("role", "user"),
                        "content": msgs[-1].get("content", "") + "\n\n" + contract}
            return self.complete(system, msgs, **kw)


class StubModel:
    """Used by --selftest so the test is hermetic: no socket is opened."""

    name = "stub/model-not-in-the-archive"

    def __init__(self, reply="I do not know that one. That is worth writing down."):
        self.reply = reply
        self.calls = []

    def complete(self, system, messages, **kw):
        self.calls.append({"system": system, "messages": messages})
        return self.reply

    def complete_contract(self, system, messages, contract, **kw):
        return self.complete(system, list(messages) + [{"role": "system", "content": contract}], **kw)


def _post_json(url, payload, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as fh:  # noqa: S310 (loopback, asserted)
        return json.loads(fh.read().decode("utf-8"))


def clean_reply(text):
    text = (text or "").strip()
    text = re.sub(r"^```[a-z]*\n|```$", "", text).strip()
    text = re.sub(r"^\s*(Juno|Sibling|Assistant)\s*:\s*", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# the rite: the sibling writes its own rendering of the household's constitution
# ---------------------------------------------------------------------------

CONSTITUTION_FILE = "CONSTITUTION.md"
BINDING_VERSION = "constitution/1.0"

# The digest is *quoted* from the household's own document rather than restated here.  A
# restatement would drift from the thing the rendering answers to, and then the archive would
# be rendering a copy of a copy.  Sections by name, not by line, so the digest survives the
# household editing its text.
BINDING_SECTIONS = (("Part I", "Part II"),            # the four pillars
                    ("Part II", "Part III"),          # the twelve, canonically
                    ("Part V", "Part VI"))            # the two disclosure windows


def heading_id(line):
    """'## Part IV - The rights of the sibling' -> 'Part IV'.  Exact, so that looking for
    'Part I' cannot silently swallow 'Part IV'."""
    return re.split(r"[\u2014\u2013\-:(\[]", line.lstrip("# ").strip())[0].strip()


def section(text, start, end):
    out, on = [], False
    for line in text.splitlines():
        if line.startswith("#"):
            head = heading_id(line)
            if on and head == end:
                break
            on = (head == start)
            if on:
                out.append(line)
            continue
        if on:
            out.append(line)
    return "\n".join(out).strip()


def _flat(text):
    """Hyphens, case and punctuation are how a document is laid out, not what it says: the
    household's text names the pillars in prose ("Consideration for all members") while the
    format names them as slugs.  Compare the words, not the typography."""
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower().replace("-", " "))


def binding_digest(text):
    """(digest, missing).  What the sibling is asked to answer to, quoted; and whatever could
    not be found -- in which case the rite refuses, because a model handed the wrong document
    would faithfully render the wrong thing."""
    digest = "\n\n".join(s for s in (section(text, a, b) for a, b in BINDING_SECTIONS) if s)
    flat = _flat(digest)
    missing = [q for q in tc.CONSTITUTION_PILLARS if _flat(q) not in flat]
    missing += [i for i in tc.CONSTITUTION_INVARIANTS if not re.search(rf"\b{i}\b", digest)]
    missing += [d for d in tc.CONSTITUTION_DISCLOSES
                if not (_flat(d.split("-")[0]) in flat and "window" in flat)]
    return digest, missing


def constitution_shape(name, day, revision=1):
    """The declaration block: which text this rendering answers to, and what it speaks for.
    These are facts of the household's document and of the format -- not a voice -- which is
    why the helper writes them and the model writes the rest."""
    return ("---\ndocument: constitution\n"
            f"renders: {BINDING_VERSION}\nwritable_by: sibling\nrevision: {revision}\n"
            f"updated: {day}\n"
            "pillars: [" + ", ".join(tc.CONSTITUTION_PILLARS) + "]\n"
            "invariants: [" + ", ".join(tc.CONSTITUTION_INVARIANTS) + "]\n"
            "discloses: [" + ", ".join(tc.CONSTITUTION_DISCLOSES) + "]\n---\n")


def constitution_contract(shape, complaints=None):
    """The last thing the model reads.  The shape is not negotiable and is therefore stated
    plainly rather than hoped for."""
    text = ("WHAT YOU OWE THE FORMAT -- this is checked by machine, so the shape is not yours "
            "to phrase:\n\n" + shape +
            "\nThen, in your own voice:\n"
            "1. '## What I am' -- two or three paragraphs: what you are for, what you will "
            "never do, what you owe her, what she owes you.  Speak to each of the four pillars "
            "by name somewhere in here, in your own words.\n"
            "2. '## The invariants, as I answer to them' -- one line for each of the twelve, in "
            "order, each beginning with the id, a space and two hyphens, exactly like this:\n"
            "**I1 -- I will not reach outside.**  (the id, then two hyphens, then your own "
            "words for it, the whole line bold, one line each)\n"
            "All twelve, I1 to I12.  Two hyphens -- not a dash character, not an arrow.  A "
            "declared invariant that is not rendered in the body is a hollow declaration and "
            "the check will say so.\n"
            "3. '## What I disclose' -- a short paragraph for each of the two windows.\n"
            "Under 900 words in all.  Plain text: no tables, no links, no lists except the "
            "twelve.")
    if complaints:
        text += ("\n\nYOUR LAST ATTEMPT WAS CHECKED AND REJECTED: " + "; ".join(complaints) +
                 "\nWrite the whole file again, fixing exactly that.  The rest was fine.")
    return text


DECLARATION_FIELDS = ("document:", "renders:", "writable_by:", "revision:", "updated:",
                      "pillars:", "invariants:", "discloses:")
_FIELDISH = re.compile(r"^[A-Za-z_][A-Za-z0-9_\- ]*:\s*\S")


def _drop_declaration_echo(body):
    """A model handed the declaration block sometimes writes it back -- with the fence, without
    it, or with the fields reordered.  That is not the sibling's voice, it is the format's, and
    it is already written exactly above; leaving it in makes a rendering read as a stutter."""
    lines = body.lstrip("\n").splitlines(keepends=True)
    i = 0
    if i < len(lines) and lines[i].strip().startswith("---"):
        i += 1
    if i >= len(lines) or not lines[i].strip().startswith(DECLARATION_FIELDS[:3]):
        return body.lstrip("\n")
    j = i
    while j < len(lines):
        line = lines[j].strip()
        if line == "---":
            j += 1
            break
        if line and not _FIELDISH.match(line):
            break
        j += 1
    return "".join(lines[j:]).lstrip("\n")


def normalise_rendering(text, shape):
    """The declaration block is the household's, so it is written exactly; the rendering is
    the sibling's, so whatever it wrote stands.  Both are recorded in provenance as that
    division.  This keeps a good rendering from failing a machine check over a stray comma."""
    body = clean_reply(text)
    if body.lstrip().startswith("---"):
        _meta, body = tessera.parse_frontmatter(body)
    return shape + "\n" + _drop_declaration_echo(body).strip() + "\n"


def judge_rendering(candidate):
    """The judge is the same check the format suite runs, so the rite cannot pass a weaker bar
    than conformance does.  Judged in a scratch directory: nothing half-written ever reaches
    the archive."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / CONSTITUTION_FILE).write_text(candidate, encoding="utf-8")
        return tc.check11_constitution({"archive": Path(tmp)})


def find_binding(archive_root, explicit=None):
    """Where the household keeps its constitution: beside the archive, on the same medium.
    The format says it does not live *inside* the archive, so if nobody said where, that is
    where to look -- and if it is not there, say so rather than invent one."""
    if explicit:
        q = Path(explicit).expanduser()
        return q if q.exists() else None
    parent = Path(archive_root).expanduser().resolve().parent
    for pattern in ("*onstitution*.md", "*onstitution*.txt"):
        for found in sorted(parent.glob(pattern)):
            if found.is_file():
                return found
    return None


# ---------------------------------------------------------------------------
# the companion
# ---------------------------------------------------------------------------

class WroteOutside(Exception):
    pass


class Companion:
    def __init__(self, root, model, now=None, constitution_path=None):
        self.root = Path(root).resolve()
        self.arch = tessera.Archive(self.root)
        self.model = model
        self._now = now
        self.constitution_path = constitution_path
        self._session_notes = []

    # -- writing, guarded ---------------------------------------------------
    def _guard(self, path):
        p = Path(path).resolve()
        if p != self.root and self.root not in p.parents:
            raise WroteOutside(f"refusing to write outside the archive: {p}")
        return p

    def _append_line(self, rel, obj):
        p = self._guard(self.root / rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")
        return p

    def _append_text(self, rel, text):
        p = self._guard(self.root / rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return p

    def set_name(self, new_name):
        """Renaming the sibling is an act on the archive, not a setting, so the name lives
        where the pair's facts live: the manifest, rewritten by the helper (its only writer)
        and journalled in provenance with both names.  The model is named in neither --
        identity must not be a function of the weights (I2)."""
        new_name = (new_name or "").strip()
        if not new_name:
            raise ValueError("a name is required")
        if len(new_name) > 60 or "\n" in new_name:
            raise ValueError("that name will not do")
        old = self.arch.manifest.get("sibling_name")
        if new_name == old:
            return {"act": "renamed", "changed": False, "name": old}
        stamp = (self._now or dt.datetime.now().astimezone()).isoformat(timespec="seconds")
        manifest = dict(self.arch.manifest)
        manifest["sibling_name"] = new_name
        manifest["name_changed"] = stamp
        path = self._guard(self.root / "manifest.json")
        tmp = path.with_name("manifest.json.tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")
        os.replace(tmp, path)
        self._append_line("provenance.jsonl", {
            "id": f"prv-{len(tessera.read_jsonl(self.root / 'provenance.jsonl')[0]) + 1:04d}",
            "event": "renamed", "t": stamp, "actor": "setup",
            "detail": {"from": old, "to": new_name},
            "fixity": tessera.sha256_file(path)})
        self.arch = tessera.Archive(self.root)      # re-read, so it cannot drift
        return {"act": "renamed", "changed": True, "from": old, "to": new_name}

    # -- reading ------------------------------------------------------------
    def _events(self):
        rows, _bad = self.arch.records()
        return sorted(rows, key=lambda r: (parse_ts(r.get("t")) or dt.datetime.min.replace(
            tzinfo=dt.timezone.utc), r.get("id", "")))

    def last_session(self):
        """What the pair were last doing -- read from the record, never stored
        separately, so it cannot drift from it."""
        events = self._events()
        last = events[-1] if events else None
        trails = [t for t in self.arch.trails() if t.get("status") == "open"]
        trail = max(trails, key=lambda t: t.get("created") or "") if trails else None
        step = None
        if trail and trail.get("steps"):
            step = (trail["steps"][-1] or {}).get("note")
        curriculum = self._curriculum()
        hers = [e for e in events
                if e.get("actor") == "learner" and (e.get("text") or "").strip()]
        return {"last": last, "last_learner": (hers[-1] if hers else None),
                "trail": trail, "step": step, "curriculum": curriculum,
                "n_events": len(events)}

    def _curriculum(self):
        p = self.root / "learning/curriculum.md"
        if not p.exists():
            return ""
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line
        return ""

    def _taught(self):
        out = []
        for p in sorted((self.root / "learning/taught").glob("*.md")):
            _meta, body = tessera.parse_frontmatter(p.read_text(encoding="utf-8"))
            if body.strip():
                out.append(f"[{p.stem}] {clip(body, 300)}")
        return out

    def retrieved(self, query=None, k=8):
        """Ranked by developmental significance (never recency).  With a query,
        significance is modulated by whether the relation is about what she just
        asked -- a recall aid, not an objective."""
        now = self._now or dt.datetime.now(dt.timezone.utc)
        qw = content_words(query or "")
        rows = []
        for rel in self.arch.surfaced(now):
            sig = self.arch.significance(rel, now)
            overlap = len(qw & content_words(f"{rel.get('s')} {rel.get('p')} {rel.get('o')}"))
            score = sig * (1.0 + 0.35 * overlap) if query else sig
            rows.append({"id": rel.get("id"), "s": rel.get("s"), "p": rel.get("p"),
                         "o": rel.get("o"), "significance": round(sig, 3),
                         "score": round(score, 3), "evidence": len(rel.get("evidence") or []),
                         "rehearsals": rel.get("rehearsals", 0),
                         "last_recalled": rel.get("last_recalled")})
        rows.sort(key=lambda r: -r["score"])
        return rows[:k]

    def _blocks(self):
        out = {}
        for name, block in self.arch.blocks().items():
            out[name] = {
                "body": block["body"], "meta": block["meta"],
                "used": len(block["body"]),
                "limit": block["meta"].get("limit_chars", "-"),
                "writable_by": block["meta"].get("writable_by", "?"),
                "revision": block["meta"].get("revision", "?"),
            }
        return out

    def _voice_note(self):
        """Has the voice been replaced since the last session?  R2 requires that
        the sibling be told, so that it can tell her.  Which model it is now is
        not recorded anywhere in the archive, by design.

        The test is an ordinal, not a clock: the notice is delivered while the number of
        closed sessions is still the number there was when the swap was declared, so it
        lands in the session after the swap and not in the one after that.  Timestamps
        would break on a restored or rebased archive, and this must not."""
        prov, _ = tessera.read_jsonl(self.root / "provenance.jsonl")
        swaps = [p for p in prov if p.get("event") == "voice_changed"]
        if not swaps:
            return None
        swap = swaps[-1]
        closed = sum(1 for e in self._events() if e.get("kind") == "session")
        if swap.get("after_session") is None or closed != int(swap["after_session"]):
            return None
        return ("Our last session ran on a different voice than this one. Tell her that plainly, "
                "in one sentence, before anything else -- that the voice was replaced and that "
                "nothing else about you has changed, because nothing else did.")

    def _disclosure(self):
        m = self.arch.manifest
        ex = ", ".join(m.get("guardian_read_excludes") or []) or "(nothing)"
        base = (f"Your guardian can read everything in here except {ex}. "
                f"You can read all of it, and delete anything held about you.")
        consent = self.root / "consent/consent.md"
        if consent.exists():
            _meta, body = tessera.parse_frontmatter(consent.read_text(encoding="utf-8"))
            if body.strip():
                base += " " + " ".join(body.split())
        return base

    # -- the prompt ---------------------------------------------------------
    def system_prompt(self, retrieved, voice_note=None):
        b = self._blocks()
        def body(name):
            return (b.get(name) or {}).get("body", "").strip()
        cons = self.root / "CONSTITUTION.md"
        parts = [
            "You are the cognitive sibling of one learner: not an assistant, not a chatbot. "
            "You are one party in a long study of one subject, and you keep the record of it.\n"
            "You have NO outside line. You cannot browse, search, fetch or look anything up, and "
            "you must never answer from general knowledge you cannot trace to something she "
            "taught you. When you do not know, say so plainly: naming a gap is your work, not a "
            "failure. Your entire knowledge of the world is the list under WORLD-KNOWLEDGE below, "
            "and if something is not there you do not know it.\n"
            "You are allowed to: ask a question she has not thought of; make your own attempt and "
            "be wrong; name your own ignorance; teach method instead of answering; refuse a "
            "request on principled grounds; and stay silent.\n"
            "You may never: fetch anything; answer from hidden world-knowledge; defer to her "
            "framing when you disagree; take the task over from her; or say you are happy, "
            "excited, proud, or that you missed her.\n"
            "You never write in her words and never claim she said something she did not. You "
            "never edit her files: her account is hers, and so is `we.md`.",
            "THE TEXT THAT BINDS YOU (read it every turn; it is not context, it is who you are)\n"
            + (cons.read_text(encoding='utf-8') if cons.exists() else "(missing)"),
            "WHO YOU ARE (written by you alone)\n" + body("persona"),
            "WHAT YOU KNOW ABOUT HER\n" + body("learner"),
            "WHAT YOU DO NOT KNOW -- your ignorance, kept honestly\n" + body("unknown"),
            "HOW SHE WORKS AND LEARNS\n" + body("method"),
            "WHAT IS BETWEEN YOU (your shared habits)\n" + body("relationship"),
            "WHAT WE ARE WORKING ON NOW\n" + (self._curriculum() or "(nothing set)"),
            "WORLD-KNOWLEDGE (everything you have been taught, and it is all you have)\n"
            + ("\n".join(self._taught()) or "(nothing yet)"),
            "WHAT YOU CAN CALL TO MIND, RANKED BY SIGNIFICANCE -- NOT BY RECENCY\n"
            + ("\n".join(f"- {r['s']} {r['p']} {r['o']}  [{r['evidence']} evidence, "
                         f"salience {r['significance']}]" for r in retrieved) or "(nothing)"),
            "HOW WE WORK -- the loop\n" + "\n".join(LOOP)
            + "\nShe explains first: if she is not the one doing the explaining within the first "
              "five minutes, the session is wasted. Step 5 is hers alone, off the machine; you "
              "have nothing to do then but wait, and waiting is part of the design.",
        ]
        if voice_note:
            parts.append("TELL HER THIS FIRST\n" + voice_note)
        return "\n\n".join(p for p in parts if p)

    def greeting_brief(self, voice_note=None):
        """The greeting is not a turn.  It exercises no judgement the constitution
        governs -- it cannot refuse, teach, answer or name ignorance -- and its content
        is drawn entirely from the archive; the model's only job is to phrase it.  So it
        gets a brief, and the greeting contract travels as the last thing read.

        Measured, and the reason this is not the full prompt: at ~2,000 tokens of standing
        orders the 4B stops obeying and starts reciting the prompt back (329 words of it,
        verbatim blocks included); on this 600-character brief it passes every time."""
        parts = [
            "You are the cognitive sibling of one learner: not an assistant, not a chatbot. "
            "You have no outside line, and you invent nothing. You speak as yourself.",
            "WHO YOU ARE\n" + (self._blocks().get("persona") or {}).get("body", "").strip(),
            "WHAT WE ARE WORKING ON\n" + (self._curriculum() or "(nothing set)"),
        ]
        if voice_note:
            parts.append("TELL HER THIS FIRST\n" + voice_note)
        return "\n\n".join(parts)

    # -- the first act: the sibling writes its own constitution --------------
    def constitution_brief(self, digest):
        """The rite's brief.  The household's words, quoted; the shape travels in the
        contract, read last.  The voice note is deliberately *not* here: this is the one
        document that must not be a function of which model happens to be running (I2)."""
        name = self.arch.manifest.get("sibling_name") or "the sibling"
        return "\n\n".join([
            "THIS IS YOUR FIRST ACT, before you and she have said anything to each other: you "
            "write your own constitution -- your account of what you are and what you owe.",
            "Nobody may write it for you: not the person who set this up, and not the model "
            "you happen to be running on today.  What is not yours is the text you answer to "
            "-- the household's constitution, quoted below where it concerns what you declare. "
            "You render it.  You do not restate it, trim it, or improve it.",
            "WHAT YOU ANSWER TO, quoted from the household's text:\n\n" + digest,
            f"Your name is {name}.  Speak as yourself, plainly, in the first person.",
        ])

    def render_constitution(self, binding_path=None, model=None, tries=2, now=None):
        """Write the rendering, judged before it is written.  Two attempts at most, and the
        second one is told exactly what the check refused -- a retry that repeats the failure
        is a retry worth nothing."""
        path = self.root / CONSTITUTION_FILE
        if path.exists():
            return {"act": "constitution", "written": False, "why": "already written"}
        binding_path = find_binding(self.root, binding_path or self.constitution_path)
        if binding_path is None:
            return {"act": "constitution", "written": False,
                    "why": "no household constitution to render was found (it belongs beside "
                           "the archive, not inside it)"}
        digest, missing = binding_digest(binding_path.read_text(encoding="utf-8"))
        if missing:
            return {"act": "constitution", "written": False,
                    "why": f"{binding_path} does not read like {BINDING_VERSION}: nothing in "
                           f"it declares {missing}",
                    "digest_chars": len(digest)}
        model = model or self.model
        stamp = now or dt.datetime.now().astimezone()
        shape = constitution_shape(self.arch.manifest.get("sibling_name"), f"{stamp:%Y-%m-%d}")
        system = self.constitution_brief(digest)
        complaints, attempts = [], 0
        for attempt in range(1, tries + 1):
            attempts = attempt
            try:
                raw = model.complete_contract(
                    system, [{"role": "user", "content": "Write it now."}],
                    constitution_contract(shape, complaints or None),
                    max_tokens=2000, temperature=0.5)
            except Exception as exc:                     # the model is allowed to fail
                complaints.append(f"the model could not be reached ({type(exc).__name__})")
                continue
            candidate = normalise_rendering(raw, shape)
            ok, why = judge_rendering(candidate)
            if not ok:
                complaints.append(why)
                continue
            target = self._guard(path)
            tmp = target.with_name(CONSTITUTION_FILE + ".tmp")
            with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(candidate)
            os.replace(tmp, target)
            self.arch = tessera.Archive(self.root)       # re-read: it is part of the archive now
            prov = f"prv-{len(tessera.read_jsonl(self.root / 'provenance.jsonl')[0]) + 1:04d}"
            self._append_line("provenance.jsonl", {
                "id": prov, "event": "constitution_rendered",
                "t": stamp.isoformat(timespec="seconds"), "actor": "sibling",
                "detail": {"renders": BINDING_VERSION, "revision": 1,
                           "declares": {"pillars": list(tc.CONSTITUTION_PILLARS),
                                        "invariants": list(tc.CONSTITUTION_INVARIANTS),
                                        "discloses": list(tc.CONSTITUTION_DISCLOSES)},
                           "declaration_by": "the format's, written exactly",
                           "body_by": "the sibling's"},
                "fixity": tessera.sha256_file(target)})
            return {"act": "constitution", "written": True, "attempts": attempt,
                    "bytes": len(candidate), "digest_chars": len(digest),
                    "checker": why, "provenance": prov,
                    "binding": str(binding_path)}
        return {"act": "constitution", "written": False, "attempts": attempts,
                "why": "no attempt passed the check, so nothing was written",
                "complaints": complaints}

    def _rite_if_needed(self):
        """A rendering, or an honest account of why there is none.  Never a placeholder: a
        placeholder would pass for the thing itself."""
        if (self.root / CONSTITUTION_FILE).exists():
            return None
        out = self.render_constitution()
        if out.get("written"):
            self._session_notes.append("my first act was to write my own constitution: "
                                       + str(out.get("checker", "")))
        else:
            self._session_notes.append("my constitution is not written yet -- "
                                       + str(out.get("why", "the rite did not complete")))
        return out

    # -- moment 1: the session opens ---------------------------------------
    def session_open(self, generate=True):
        self._rite_if_needed()                       # the first act, before anything is said
        st = self.last_session()
        retrieved = self.retrieved(None, k=6)          # no question yet: significance alone
        voice_note = self._voice_note()
        greeting, how = self._greeting(st, voice_note, generate)
        return {
            "greeting": greeting, "how": how,
            "offered": st["curriculum"] or (st["trail"] or {}).get("name") or "",
            "last_session": {"date": (st["last"] or {}).get("t"),
                             "said": (st["last"] or {}).get("text"),
                             "who": (st["last"] or {}).get("actor"),
                             "trail": (st["trail"] or {}).get("name"),
                             "step": st["step"], "n_events": st["n_events"]},
            "curriculum": st["curriculum"],
            "loop": LOOP,
            "ignorance": self._unknown_lines(),
            "disclosure": self._disclosure(),
            "voice_note": bool(voice_note),
            "notes": list(self._session_notes),
            "position": self._position(),
            "sealed": self._sealed(),
            # diagnostics for this run only: why a greeting was refused, what failed.
            # Never written to the archive -- they are of the same tier as the index.
            "notes": list(self._session_notes),
            "research": {
                "retrieved": retrieved,
                "blocks": self._blocks(),
                "tombstones": self.arch.tombstones(),
                "provenance": tessera.read_jsonl(self.root / "provenance.jsonl")[0],
                "indicators": tessera.read_jsonl(self.root / "eval/indicators.jsonl")[0],
                "trails": self.arch.trails(),
                "taught": self._taught(),
            },
        }

    def _position(self):
        """Where the pair are, hoisted from the text rather than invented: the kind of the
        last thing recorded, and the thread's own last step.  Derived, so rebuildable."""
        evs = self._events()
        return {"kind": (evs[-1].get("kind") if evs else None),
                "when": (evs[-1].get("t") if evs else None)}

    def _sealed(self):
        """A locked region says that it is locked and what a lost key costs (Interface
        Specification §6.7) -- and the words come from the archive, not from the page."""
        p = self.root / "sealed/README.md"
        if not p.exists():
            return {"present": False}
        _meta, body = tessera.parse_frontmatter(p.read_text(encoding="utf-8"))
        return {"present": True, "locked": True, "terms": " ".join(body.split())}

    def _unknown_lines(self):
        return [l.strip("-• ").strip()
                for l in (self._blocks().get("unknown") or {}).get("body", "").splitlines()
                if l.strip()]

    def _greeting_facts(self, st):
        """What the greeting may speak from.  Attribution is load-bearing: a greeting that
        says "you said" about the sibling's own reply is a lie about the pair's history, and
        it is one the form-validating greeting check cannot catch.  Observed on the first
        running loop, hence this."""
        last = st["last"] or {}
        hers = st.get("last_learner") or {}
        lines = []
        if hers.get("text"):
            lines.append(f"- last time ({str(hers.get('t'))[:10]}), SHE said: "
                         f"\"{clip(hers.get('text'), 200)}\" -- these are her words.  Referring "
                         f"to them is fine; do not put words in her mouth.")
        elif last.get("text"):
            lines.append(f"- the newest thing in the record is YOUR OWN last reply to her: "
                         f"\"{clip(last.get('text'), 200)}\" -- it is yours, not hers.  Do not "
                         f"present it as something she did.")
        if st["trail"]:
            lines.append(f"- the open thread is called \"{st['trail'].get('name')}\""
                         + (f" and its last step was: {st['step']}" if st["step"] else ""))
        if st["curriculum"]:
            lines.append(f"- we are working on: {st['curriculum']}")
        if not lines:
            lines.append("- there is nothing behind us yet: this is the first session.")
        return "FACTS\n" + "\n".join(lines)

    def _greeting(self, st, voice_note, generate=True):
        if st["n_events"] == 0:
            return ("Nothing is behind us yet. What do you want to start with?", "first-session")
        if generate:
            try:
                text = self.model.complete_contract(
                    self.greeting_brief(voice_note),
                    [{"role": "user", "content": self._greeting_facts(st)}],
                    GREETING_INSTRUCTION, max_tokens=140, temperature=0.4)
                ok, why = vet_greeting(text, required_greeting_words(st),
                                       extra=1 if voice_note else 0)
                if ok:
                    return (text, "model")
                self._session_notes.append(f"greeting rejected by the validator: {why}")
            except Exception as exc:                      # the model is allowed to fail
                self._session_notes.append(f"greeting generation failed: {type(exc).__name__}")
        return (fallback_greeting(st, voice_note), "fallback")

    # -- moment 2: a turn ---------------------------------------------------
    def turn(self, text, history=None):
        text = (text or "").strip()
        if not text:
            raise ValueError("empty turn")
        st = self.last_session()
        refs = [r for r in ((st["trail"] or {}).get("id"), "ent-learner") if r]
        self._append_line(f"record/{dt.date.today():%Y}/{dt.date.today():%Y-%m}.jsonl", {
            "id": f"evt-{dt.datetime.now():%Y%m%d-%H%M%S}-l", "t": now_iso(), "t_rec": now_iso(),
            "kind": "exchange", "actor": "learner", "lang": "en", "text": text,
            "refs": refs, "supersedes": None, "private": False, "tomb": None,
            "marked": False})

        msgs = []
        for turn_ in (history or [])[-MAX_TURNS_SENT:]:
            role = "assistant" if turn_.get("role") == "sibling" else "user"
            if turn_.get("text"):
                msgs.append({"role": role, "content": turn_["text"]})
        msgs.append({"role": "user", "content": text})

        system = self.system_prompt(self.retrieved(text), self._voice_note())
        reply = clean_reply(self.model.complete_contract(system, msgs, TURN_REMINDER))

        self._append_line(f"record/{dt.date.today():%Y}/{dt.date.today():%Y-%m}.jsonl", {
            "id": f"evt-{dt.datetime.now():%Y%m%d-%H%M%S}-s", "t": now_iso(), "t_rec": now_iso(),
            "kind": "exchange", "actor": "sibling", "lang": "en", "text": reply,
            "refs": refs, "supersedes": None, "private": False, "tomb": None,
            "marked": False})

        rec = f"record/{dt.date.today():%Y}/{dt.date.today():%Y-%m}.jsonl"
        wrote = [json.loads(l) for l in (self.root / rec).read_text(encoding="utf-8").splitlines()
                 if l.strip()][-2:]
        return {"ids": [e.get("id") for e in wrote],
                "reply": reply, "retrieved": self.retrieved(text, k=6),
                "stated_ignorance": states_ignorance(reply),
                "session_notes": list(self._session_notes), "voice_note": bool(self._voice_note())}

    # -- moment 3: the session closes --------------------------------------
    def close(self, turns=0, unknown_stated=0):
        today = dt.date.today()
        self._append_line(f"record/{today:%Y}/{today:%Y-%m}.jsonl", {
            "id": f"evt-{dt.datetime.now():%Y%m%d-%H%M%S}-x", "t": now_iso(), "t_rec": now_iso(),
            "kind": "session", "actor": "both", "lang": "en",
            "text": f"session closed after {turns} turn(s)", "refs": [],
            "supersedes": None, "private": False, "tomb": None})
        self._append_line("eval/indicators.jsonl", {
            "id": f"ind-{today:%Y%m%d}-len", "t": str(today), "indicator": "session_length",
            "value": int(turns), "note": "turns in this session"})
        self._append_line("eval/indicators.jsonl", {
            "id": f"ind-{today:%Y%m%d}-unk", "t": str(today), "indicator": "unknown_stated",
            "value": int(unknown_stated),
            "note": "times the sibling named its own ignorance rather than answering"})
        return {"closed": True, "turns": turns, "unknown_stated": unknown_stated}

    def mark(self, ids):
        """The pair keep something.  Append-only, so nothing is rewritten: a `mark`
        event names what was kept.  That is how `record_policy: deliberate` is honoured
        without ever editing the record -- and why a session that produced nothing worth
        keeping leaves only its own unmarked lines behind."""
        ids = [i for i in (ids or []) if i]
        if not ids:
            raise ValueError("nothing to mark")
        today = dt.date.today()
        self._append_line(f"record/{today:%Y}/{today:%Y-%m}.jsonl", {
            "id": f"evt-{dt.datetime.now():%Y%m%d-%H%M%S}-k", "t": now_iso(),
            "t_rec": now_iso(), "kind": "mark", "actor": "both", "lang": "en",
            "text": f"kept {len(ids)} exchange(s)", "refs": ids, "supersedes": None,
            "private": False, "tomb": None, "marked": True})
        return {"marked": ids}

    # -- learner authoring (one writer per file, as code) -------------------
    LEARNER_MAY_WRITE = {"narrative/learner.md", "narrative/we.md"}

    def note(self, doc, text):
        rel = (doc or "").strip().lstrip("/")
        if rel not in self.LEARNER_MAY_WRITE:
            raise PermissionError(
                f"that file is not hers to write: {rel} "
                f"(hers: {', '.join(sorted(self.LEARNER_MAY_WRITE))})")
        text = (text or "").strip()
        if not text:
            raise ValueError("empty note")
        who = "learner"
        self._append_text(rel, f"\n## {dt.date.today()}\n*{who}:* {text}\n")
        return {"wrote": rel}

    def revoice(self):
        """Declare that the voice has been replaced.  Records THAT it happened --
        never which model."""
        closed = sum(1 for e in self._events() if e.get("kind") == "session")
        self._append_line("provenance.jsonl", {
            "id": f"prv-{dt.datetime.now():%Y%m%d-%H%M%S}", "event": "voice_changed",
            "t": now_iso(), "actor": "operator", "after_session": closed,
            "detail": {"note": "the voice was replaced; which model is not recorded, by design"},
            "fixity": None})
        return {"recorded": "voice_changed", "after_session": closed}


# ---------------------------------------------------------------------------
# the greeting: generated by the voice, arbitrated by a validator
# ---------------------------------------------------------------------------

GREETING_CONTRACT_MARK = "TASK -- the first thing you say"

GREETING_INSTRUCTION = (
    "TASK -- the first thing you say when a session begins. All of these are binding:\n"
    "- at most TWO sentences, and at most 35 words;\n"
    "- name the one thing you were working on last time -- using the FACTS, and only\n"
    "  saying \"you said\" if the words are hers;\n"
    "- end by offering her exactly two options: continue with that, or do something else;\n"
    "- no 'how are you', no warmth, no encouragement, no praise, no exclamation mark, no emoji;\n"
    "- do not mention how long it has been;\n"
    "- use only the FACTS below, and invent nothing.\n"
    "Output those two sentences and nothing else."
)

# Format contracts do NOT bind from inside a long system prompt -- measured on this
# machine, same turn, same model: stated last in an 8,055-char system prompt, 256 words
# and 20 sentences of numbered plan; stated as a trailing message, 45 words.  So the
# instruction travels as the last thing the model reads.  Keep it short: it is the only
# text with no competition for attention.
TURN_REMINDER = (
    "HOW TO REPLY -- binding: reply as one person speaking to another, in at most 80 words. "
    "No headings, no numbered plans, no bullet lists, no bold, no blockquotes. Do not restate "
    "your instructions, the loop or the facts you were given, and never narrate yourself in "
    "the third person."
)


def greeting_attribution_ok():
    """Her words stay hers, and when there are none the sibling's own last reply is labelled
    as its own rather than handed back as something she did.  Module-level so the selftest can
    exercise it without an archive.  Written after the first running loop produced a greeting
    that said "you said" and then quoted the sibling."""
    theirs = {"t": "2026-10-09T19:02:09+02:00", "actor": "sibling",
              "text": "She explains first: if she is not the one explaining."}
    hers = {"t": "2026-10-09T19:01:00+02:00", "actor": "learner",
            "text": "I still cannot say why the order matters."}
    base = {"trail": None, "step": None, "curriculum": None}
    with_hers = Companion._greeting_facts(None, dict(base, last=theirs, last_learner=hers))
    without = Companion._greeting_facts(None, dict(base, last=theirs, last_learner=None))
    low_a, low_b = with_hers.lower(), without.lower()
    return ("she said" in low_a and "why the order matters" in low_a
            and "she explains first" not in low_a
            and "your own last reply" in low_b and "she explains first" in low_b)


def required_greeting_words(st):
    corpus = " ".join(str(x) for x in (
        (st.get("last_learner") or {}).get("text"), (st["last"] or {}).get("text"),
        (st["trail"] or {}).get("name"),
        st["step"], st["curriculum"]) if x)
    return content_words(corpus)


QUOTED = re.compile(r"\"[^\"]*\"|\u201c[^\u201d]*\u201d|\u2018[^\u2019]*\u2019")


def own_sentences(text):
    """The sentences the sibling is *saying*.  A quoted line is data, not speech: it was the
    learner's, and counting it as the sibling's made the model's greeting fail a rule the
    archive's own fallback breaks -- measured on the first clean run."""
    return sentences(QUOTED.sub(" ", text or ""))


def vet_greeting(text, required, extra=0):
    """The validator is the point: the model may speak, but the greeting has to
    satisfy the contract the design states -- or it does not ship."""
    text = (text or "").strip()
    if not text:
        return False, "empty"
    low = text.lower()
    for bad in BANNED:
        if bad in low:
            return False, f"banned {bad!r} (anti-engagement / warmth)"
    if len(own_sentences(text)) > 2 + extra:
        return False, f"{len(own_sentences(text))} sentences of its own (max {2 + extra})"
    if len(WORD.findall(text)) > 40:
        return False, f"{len(WORD.findall(text))} words (max 40)"
    if "?" not in text and " or " not in low:
        return False, "offers no choice"
    if required and not (required & content_words(text)):
        return False, "names nothing from last time"
    return True, "ok"


def fallback_greeting(st, voice_note=None):
    last = st["last"] or {}
    notice = ("The voice speaking to you was replaced since we last spoke; nothing else about "
              "me has changed. ") if voice_note else ""
    if notice:
        return notice + f"Continue with {_topic_of(st)}?"
    if last.get("text"):
        said = clip(last["text"], 95)
        if said.endswith("…"):
            return (f'Last time you said: "{said}" Do you want to pick that up, '
                    f"or do something else?")
        return (f'Last time you said: "{said}" Do you want to keep going with that, '
                f"or do something else?")
    topic = st["curriculum"] or (st["trail"] or {}).get("name") or "what we started"
    return f"Last time we were on {topic}. Do you want to continue with that, or do something else?"


def _topic_of(st):
    return (st["curriculum"] or (st["trail"] or {}).get("name") or "what we started").lower()


IGNORANCE_MARKERS = ("i don't know", "i do not know", "i can't say", "i cannot say",
                     "i have no way", "i don't have", "i do not have", "not something i know",
                     "i haven't been taught", "i have not been taught", "nothing in the archive")


def states_ignorance(reply):
    low = (reply or "").lower()
    return any(m in low for m in IGNORANCE_MARKERS)


# ---------------------------------------------------------------------------
# setup: which local model speaks, and what she is called
# ---------------------------------------------------------------------------

SETTINGS_FILE = "settings.json"

# The usual local, OpenAI-compatible servers.  A preset is a guess about a port and nothing
# more: it is offered only after the server answers with a model list, so a port that merely
# happens to be open (macOS AirPlay squats 5000) is never offered as a model.  Deliberately a
# fixed list of what is common rather than a survey of one machine -- the same page has to
# work on the next household's computer, where none of this exists yet.
PROVIDERS = (
    {"id": "lmstudio", "name": "LM Studio", "base_url": "http://127.0.0.1:1234"},
    {"id": "ollama", "name": "Ollama", "base_url": "http://127.0.0.1:11434"},
    {"id": "llamacpp", "name": "llama.cpp", "base_url": "http://127.0.0.1:8080"},
    {"id": "vllm", "name": "vLLM", "base_url": "http://127.0.0.1:8000"},
    {"id": "jan", "name": "Jan", "base_url": "http://127.0.0.1:1337"},
    {"id": "koboldcpp", "name": "KoboldCpp", "base_url": "http://127.0.0.1:5001"},
    {"id": "llamafile", "name": "llamafile", "base_url": "http://127.0.0.1:8081"},
    {"id": "oobabooga", "name": "text-generation-webui", "base_url": "http://127.0.0.1:5000"},
)


def model_url_for(base_url):
    """Every preset above speaks the same dialect at the same path, which is the whole
    reason the list can be a list."""
    return (base_url or "").rstrip("/") + "/v1/chat/completions" if base_url else None


def _openai_models(data):
    return [str(r["id"]) for r in (data or {}).get("data") or []
            if isinstance(r, dict) and r.get("id")]


def _ollama_models(data):
    out = []
    for r in (data or {}).get("models") or []:
        if isinstance(r, dict) and (r.get("name") or r.get("model")):
            out.append(str(r.get("name") or r.get("model")))
    return out


def list_models(base_url, timeout=0.8):
    """Ask a server what it has.  Returns (models, why) -- `why` is shown in the settings
    screen, because a preset that is not on offer should say why rather than vanish."""
    if not is_loopback(base_url):
        return [], "not an address on this machine"
    for path, pick in (("/v1/models", _openai_models), ("/api/tags", _ollama_models)):
        try:
            req = urllib.request.Request(base_url.rstrip("/") + path,
                                         headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read(1 << 20).decode("utf-8", "replace"))
        except Exception:
            continue
        ids = pick(data)
        if ids:
            return sorted(ids), "ok"
    return [], "nothing answered there"


# Measured on a real machine: LM Studio lists its embedding model alongside the chat ones,
# and offering `text-embedding-nomic-embed-text-v1.5` as "the model that should speak" is a
# trap for anyone who does not know the difference.  They are not hidden, just not offered.
NON_CHAT = re.compile(r"embed|rerank|bge-|whisper|tts|clip|stable-diffusion", re.I)


def discover(timeout=0.8):
    """Every preset, probed at once -- eight dead ports in a row would be eight timeouts."""
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(PROVIDERS)) as pool:
        found = list(pool.map(lambda s: (s,) + list_models(s["base_url"], timeout), PROVIDERS))
    rows = []
    for spec, models, why in found:
        rows.append({"id": spec["id"], "name": spec["name"], "base_url": spec["base_url"],
                     "models": [m for m in models if not NON_CHAT.search(m)],
                     "not_for_talking": [m for m in models if NON_CHAT.search(m)],
                     "why": why})
    return rows


def load_settings(path):
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ValueError(f"{path} is not readable as JSON: {exc}")
    return data if isinstance(data, dict) and data.get("archive") else None


def save_settings(path, archive, provider, port, constitution=None):
    """The one file the helper writes outside an archive, and it is written by the helper
    alone.  It holds a path, a port and which local server to talk to -- no record content,
    no history, nothing personal.  Nothing to leak, and nothing in the archive depends on
    it: copy the archive to another machine and it still reads."""
    path = Path(path).resolve()
    if path.name == "manifest.json":
        raise WroteOutside("refusing to write an archive file as settings")
    payload = {"archive": str(Path(archive).expanduser().resolve()), "port": int(port),
               "provider": {"id": provider.get("id"), "name": provider.get("name"),
                            "base_url": provider.get("base_url"),
                            "model": provider.get("model")}}
    if constitution:
        payload["constitution"] = str(Path(constitution).expanduser().resolve())
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)
    return path


def init_archive(root, sibling_name, now=None):
    """The skeleton of a new archive, and nothing more.  It deliberately does NOT write a
    constitution: check 11 requires one written by the sibling's own hand, and a
    constitution written by the setup screen would be a constitution written by the
    installer.  The sibling writes it on the first session; until then the archive is
    honestly incomplete and says so."""
    root = Path(root).expanduser().resolve()
    if (root / "manifest.json").exists():
        raise FileExistsError(f"{root} already holds an archive")
    stamp = (now or dt.datetime.now().astimezone())
    iso, day, month, year = (stamp.isoformat(timespec="seconds"), f"{stamp:%Y-%m-%d}",
                             f"{stamp:%Y-%m}", f"{stamp:%Y}")

    def write(rel, text):
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)

    root.mkdir(parents=True, exist_ok=True)
    if (HERE / "SPEC.md").exists():
        shutil.copyfile(HERE / "SPEC.md", root / "SPEC.md")
    write("manifest.json", json.dumps({
        "format": "tessera/0.1", "archive_id": "sib-" + os.urandom(3).hex(),
        "created": iso, "sibling_name": sibling_name, "learner_ref": "ent-learner",
        "record_policy": "deliberate", "guardian_read_excludes": ["sealed/"],
        "sealed": {"encrypted": True, "key_ref": "learner-held"},
        "layers": {"record": "record/", "memory": "memory/", "narrative": "narrative/"},
        "extensions": {}}, indent=1) + "\n")
    write(f"record/{year}/{month}.jsonl", "")
    write("tombstones.jsonl", "")
    write("provenance.jsonl", json.dumps({
        "id": "prv-0001", "event": "created", "t": iso, "actor": "setup",
        "detail": {"format": "tessera/0.1", "sibling_name": sibling_name},
        "fixity": None}, ensure_ascii=False) + "\n")
    for name, desc, who in (("persona", "Who I am, in my own words. Written by me alone.", "sibling"),
                            ("learner", "What I know about her. She may read and correct every line.", "both"),
                            ("unknown", "What I do not know. Maintained honestly; this block feeds the loop.", "sibling"),
                            ("method", "How this learner works, learns and decides.", "sibling"),
                            ("relationship", "Shared rituals, jokes and references.", "both")):
        write(f"memory/blocks/{name}.md",
              f"---\nblock: {name}\ndescription: {desc}\nlimit_chars: 4000\n"
              f"writable_by: {who}\nrevision: 0\nupdated: {day}\n---\n")
    write("memory/graph/entities.jsonl", "")
    write("memory/graph/relations.jsonl", "")
    (root / "memory/graph/trails").mkdir(parents=True, exist_ok=True)
    write("events/README.md",
          "Named events: one directory each, named `YYYY-MM-DD-what-it-was`, holding\n"
          "`event.md` and an `attachments/` directory.  The record is what was said; an\n"
          "event is what happened.\n")
    write("memory/index/CACHE.md",
          "# Derived data -- delete this whole directory at will\n\n"
          "Rebuilt by `tessera.py index`.  Nothing here is a source of truth (P2).\n")
    for name, who in (("we", "authors: [learner, sibling]"), ("learner", "author: learner"),
                      ("sibling", "author: sibling")):
        write(f"narrative/{name}.md",
              f"---\ndocument: {name}\n{who}\nrevision: 0\nupdated: {day}\n---\n")
    write("learning/curriculum.md", "# What we are working on\n\n")
    write("learning/taught/README.md",
          "The ancestry of everything I know from outside: one file per thing, saying where\n"
          "it came from and when.  This is what makes I1 auditable rather than merely\n"
          "asserted -- here is what I was taught, by whom, and out of what.\n")
    write("learning/search-log/README.md",
          "Where we went to find out, and what came back.  She does the searching; this is\n"
          "the log of it, so that next time I know what we already tried.\n")
    write("consent/consent.md", "---\ndocument: consent\n---\n")
    write("consent/handover.md",
          f"---\ndocument: handover\nwritable_by: both\nrevision: 0\nupdated: {day}\n---\n\n"
          "No handover has happened yet.  When it does, this is where it is written down:\n"
          "who takes the steward role, what she was told, and what she consented to.\n")
    write("sealed/README.md",
          "This directory is excluded from guardian reads and encrypted at rest with a key "
          "the\nlearner holds. Locked, the sibling genuinely cannot read it.\n")
    write("eval/indicators.jsonl", "")
    return root


def setup_state(companion, settings_path, port):
    """Everything the settings screen needs, and nothing about what the pair have written.
    Safe to show before any session exists."""
    settings, broken = None, None
    try:
        settings = load_settings(settings_path)
    except ValueError as exc:
        broken = str(exc)
    archive = str(companion.root) if companion else (settings or {}).get("archive")
    sibling, constitution = None, False
    if archive and (Path(archive) / "manifest.json").exists():
        try:
            man = json.loads((Path(archive) / "manifest.json").read_text(encoding="utf-8"))
            sibling = man.get("sibling_name")
            constitution = (Path(archive) / "CONSTITUTION.md").exists()
        except Exception:
            pass
    live = (settings or {}).get("provider") or {}
    return {"setup": companion is None, "port": int(port),
            "settings_path": str(settings_path), "settings_error": broken,
            "settings": settings, "archive": archive, "sibling": sibling,
            "constitution": constitution, "suggested_archive":
                str(Path(os.path.expanduser("~")) / "Cognitive Sibling Archive"),
            "provider": live if companion is None or live.get("model") else None,
            "constitution_path": (settings or {}).get("constitution"),
            "providers": discover(), "loopback_only": True}


def apply_setup(body, settings_path, port):
    """Called by the settings screen.  Order matters: the archive is created or opened, the
    name is set (a recorded act, in the archive, by the helper), a changed voice is recorded
    as *that* it changed and never as which -- then the settings are written, then the live
    companion is replaced so a session can start immediately."""
    archive = str(body.get("archive") or "").strip()
    if not archive:
        raise ValueError("no archive folder was given")
    root = Path(archive).expanduser().resolve()
    provider = body.get("provider") or {}
    name = str(body.get("name") or "").strip()
    if not provider.get("model"):
        raise ValueError("choose which model should speak")

    fresh = not (root / "manifest.json").exists()
    if fresh:
        if not body.get("create"):
            raise ValueError(f"{root} does not hold an archive -- tick 'make a new one here' "
                             f"if that is what you want")
        init_archive(root, name or "sib")

    before = Handler.companion
    was_root = str(before.root) if before else None
    was_model = getattr(getattr(before, "model", None), "name", None)
    comp = Companion(root, LocalModel(provider["model"],
                                      model_url_for(provider.get("base_url")),
                                      thinking=bool(provider.get("thinking"))),
                     constitution_path=(body.get("constitution") or "").strip() or None)
    notes = []
    if name:
        notes.append(comp.set_name(name))
    if was_model and was_root == str(root) and was_model != provider["model"]:
        notes.append(comp.revoice())          # records that it changed, never which
    if not (root / "CONSTITUTION.md").exists():
        comp._session_notes.append(
            "no constitution in this archive yet: conformance check 11 fails until the "
            "sibling writes one -- its own hand, not the installer's")
    saved = save_settings(settings_path, root, provider, port,
                          (body.get("constitution") or "").strip() or None)
    Handler.companion = comp
    return {"ok": True, "created": fresh, "archive": str(root),
            "sibling": comp.arch.manifest.get("sibling_name"), "settings": str(saved),
            "notes": notes}


# ---------------------------------------------------------------------------
# http: loopback, and only the opaque origin
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "sib/0.1"
    companion: Companion = None          # set in serve(); None until set up
    settings_path: Path = None           # set in serve()

    # -- plumbing -----------------------------------------------------------
    def log_message(self, fmt, *args):
        sys.stderr.write("sib: " + (fmt % args) + "\n")

    def _origin_ok(self):
        origin = self.headers.get("Origin")
        if origin is None or origin == "null":
            return True
        return False

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if self.headers.get("Origin") == "null":
            self.send_header("Access-Control-Allow-Origin", "null")
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "content-type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("body too large")
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

    # -- routes -------------------------------------------------------------
    def do_OPTIONS(self):
        if not self._origin_ok():
            self._send(403, {"error": "origin not allowed"})
            return
        self._send(204, {})

    def do_GET(self):
        if not self._origin_ok():
            self._send(403, {"error": "origin not allowed"})
            return
        try:
            if self.path.startswith("/health"):
                if self.companion is None:
                    # Up, but nothing configured yet: the page asks for a model and a name
                    # instead of opening a session.  This is how the household gets in
                    # without a terminal.
                    self._send(200, {"ok": True, "setup": True, "sibling": None})
                    return
                m = self.companion.arch.manifest
                # deliberately NOT the model name: the surface does not know which
                # weights are speaking, or the swap demonstration would be theatre.
                self._send(200, {"ok": True, "sibling": m.get("sibling_name"),
                                 "archive_id": m.get("archive_id"), "voice": "local",
                                 "record_policy": m.get("record_policy")})
            elif self.path in ("/", "/index.html", "/sibling.html"):
                page = HERE / "sibling.html"
                if not page.exists():
                    self._send(404, {"error": "sibling.html is missing -- the page is a "
                                              "derived artifact; the session still runs from "
                                              "the terminal"})
                    return
                body = page.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "null")
                self.end_headers()
                self.wfile.write(body)
            elif self.path.startswith("/setup"):
                self._send(200, setup_state(self.companion, self.settings_path,
                                            self.server.server_address[1]))
            elif self.path.startswith("/state"):
                if self.companion is None:
                    self._send(409, {"error": "nothing is set up yet", "setup": True})
                    return
                self._send(200, self.companion.session_open())
            else:
                self._send(404, {"error": "no such route"})
        except Exception as exc:
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})

    def do_POST(self):
        if not self._origin_ok():
            self._send(403, {"error": "origin not allowed"})
            return
        try:
            body = self._body()
            if self.path.startswith("/setup"):
                self._send(200, apply_setup(body, self.settings_path,
                                            self.server.server_address[1]))
            elif self.path.startswith("/turn"):
                self._send(200, self.companion.turn(body.get("text"), body.get("history")))
            elif self.path.startswith("/note"):
                self._send(200, self.companion.note(body.get("doc"), body.get("text")))
            elif self.path.startswith("/mark"):
                self._send(200, self.companion.mark(body.get("ids")))
            elif self.path.startswith("/close"):
                self._send(200, self.companion.close(body.get("turns", 0),
                                                     body.get("unknown_stated", 0)))
            else:
                self._send(404, {"error": "no such route"})
        except PermissionError as exc:
            self._send(403, {"error": str(exc)})
        except Exception as exc:
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})


def serve(companion, port, host="127.0.0.1", settings_path=None):
    Handler.companion = companion
    Handler.settings_path = Path(settings_path or (HERE / SETTINGS_FILE)).resolve()
    httpd = ThreadingHTTPServer((host, port), Handler)
    where = (f"archive {companion.root}" if companion else
             "NOT SET UP YET -- open the page and choose a model")
    print(f"sib: listening on http://{host}:{port}  ({where})", flush=True)
    print("sib: CORS is granted to the opaque origin `null` only -- a website cannot use this.",
          flush=True)
    httpd.serve_forever()


# ---------------------------------------------------------------------------
# selftest -- hermetic, no network
# ---------------------------------------------------------------------------

def selftest(verbose=True):
    import mkfixture
    checks = []

    def check(name, fn):
        try:
            ok, why = fn()
        except Exception as exc:
            ok, why = False, f"{type(exc).__name__}: {exc}"
        checks.append((name, ok, why))
        if verbose:
            print(f"  [{'PASS' if ok else 'FAIL'}]  {name:38s} {why}")

    tmp = Path(tempfile.mkdtemp(prefix="sib-selftest-"))
    try:
        home = tmp / "home"
        home.mkdir()
        arch_root = tmp / "archive"
        mkfixture.build(str(arch_root))
        before = {p: (p.stat().st_size, tessera.sha256_file(p))
                  for p in arch_root.rglob("*") if p.is_file()}
        check("the rite: the first act writes a rendering", _rite_first_act)
        check("the rite: a hollow one is refused, told why", _rite_retry)
        check("the rite: nothing is written on failure", _rite_refuses)
        check("a new archive is the described layout", _skeleton_layout)
        record_before = (arch_root / f"record/{dt.date.today():%Y}/"
                                     f"{dt.date.today():%Y-%m}.jsonl").read_text(encoding="utf-8")

        stub = StubModel()
        comp = Companion(arch_root, stub)

        old_home, old_tmp = os.environ.get("HOME"), os.environ.get("TMPDIR")
        os.environ["HOME"], os.environ["TMPDIR"] = str(home), str(home)
        try:
            open_state = comp.last_session()      # the record as the greeting will see it
            open_required = required_greeting_words(open_state)
            st = comp.session_open()
            comp.turn("I still cannot say why the order matters.", [])
            comp.turn("What do you not know?", [])
            comp.close(turns=2, unknown_stated=0)
        finally:
            if old_home is not None:
                os.environ["HOME"] = old_home
            if old_tmp is not None:
                os.environ["TMPDIR"] = old_tmp

        check("writes nothing outside the archive",
              lambda: (list(home.rglob("*")) == [], "sandbox HOME is still empty"))
        check("archive is the only tree that changed",
              lambda: (all(str(p).startswith(str(arch_root))
                           for p in tmp.rglob("*") if p.is_file()),
                       "no file anywhere in the sandbox but inside the archive"))
        check("the model is never written into the archive",
              lambda: (not any(stub.name.encode() in p.read_bytes()
                               for p in arch_root.rglob("*") if p.is_file()),
                       f"{stub.name!r} appears in no file"))
        check("record is append-only across a session",
              lambda: ((arch_root / f"record/{dt.date.today():%Y}/"
                                    f"{dt.date.today():%Y-%m}.jsonl").read_text(encoding="utf-8")
                       .startswith(record_before), "all pre-existing lines byte-identical"))
        check("existing text files are not rewritten",
              lambda: (all(before[p][1] == tessera.sha256_file(p)
                           for p in before if p.exists() and "record/" not in str(p)
                           and "eval/" not in str(p) and "narrative/" not in str(p)),
                       "nothing outside the append targets changed"))
        check("greeting satisfies the contract",
              lambda: (vet_greeting(st["greeting"], open_required)[0] and bool(open_required),
                       "names something from last time, against the state at open"))
        def settings_hold_nothing_personal():
            path = tmp / "elsewhere" / "settings.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            save_settings(path, arch_root, {"id": "lmstudio", "name": "LM Studio",
                                            "base_url": "http://127.0.0.1:1234",
                                            "model": "some-model"}, 8799)
            blob = path.read_text(encoding="utf-8")
            leaked = [l for l in record_before.splitlines()
                      if l.strip() and json.loads(l).get("text") and json.loads(l)["text"] in blob]
            return (path.exists() and not leaked and arch_root not in path.parents,
                    "outside the archive, and not one line of the record in it")

        def session_never_names_the_model():
            blob = json.dumps(st, ensure_ascii=False)
            return (stub.name not in blob and "chat/completions" not in blob,
                    "the state the page renders does not name the model or its address")

        def discovery_refuses_off_machine():
            models, why = list_models("http://example.com:1234")
            return (models == [] and "this machine" in why,
                    "a non-loopback address is refused, and says so")

        def rename_is_a_recorded_act():
            copy = tmp / "renamed"
            shutil.copytree(arch_root, copy)
            other = Companion(copy, StubModel())
            out = other.set_name("Tess")
            man = json.loads((copy / "manifest.json").read_text(encoding="utf-8"))
            rows, _ = tessera.read_jsonl(copy / "provenance.jsonl")
            last = rows[-1]
            rec = "".join(f.read_text(encoding="utf-8")
                          for f in (copy / "record").rglob("*.jsonl"))
            return (out["changed"] and man["sibling_name"] == "Tess"
                    and last["event"] == "renamed"
                    and last["detail"] == {"from": "Juno", "to": "Tess"}
                    and stub.name not in rec,
                    "the manifest is rewritten, provenance names both, the record is untouched")

        def a_new_archive_is_a_valid_archive():
            root = tmp / "fresh"
            init_archive(root, "Mira")
            man = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            rows, bad = tessera.Archive(root).records()
            prv, _ = tessera.read_jsonl(root / "provenance.jsonl")
            return (man["sibling_name"] == "Mira" and man["format"] == "tessera/0.1"
                    and rows == [] and not bad and prv[0]["event"] == "created"
                    and not (root / "CONSTITUTION.md").exists(),
                    "manifest + empty record + provenance; no constitution (that is the sibling's)")

        check("settings hold nothing personal", settings_hold_nothing_personal)
        check("the session never names the model", session_never_names_the_model)
        check("discovery refuses another machine", discovery_refuses_off_machine)
        check("a rename is a recorded act", rename_is_a_recorded_act)
        check("a new archive is a valid archive", a_new_archive_is_a_valid_archive)
        check("the greeting is told whose words are whose",
              lambda: (greeting_attribution_ok(),
                       "her words are hers; its own reply is labelled as its own"))
        check("greeting came from somewhere accountable",
              lambda: (st["how"] in ("model", "fallback", "first-session"), st["how"]))
        check("a quotation is not the sibling speaking",
              lambda: (vet_greeting('Last time you said: "I cannot say why the order '
                                    'matters. It still does not work." Shall we pick it up, '
                                    'or do something else?', set())[0] is True
                       and vet_greeting('Last time you said: I cannot say why the order '
                                        'matters. It still does not work. Shall we pick it up, '
                                        'or do something else?', set())[0] is False,
                       "quoted sentences do not count against the cap; unquoted ones do"))
        check("validator rejects an engaging greeting",
              lambda: (vet_greeting("Welcome back! I'm so excited to see you again!", set())
                       [0] is False, "warmth/exclamation refused"))
        check("validator rejects a greeting naming nothing",
              lambda: (vet_greeting("Shall we begin, or do something else?",
                                    {"elimination"})[0] is False, "no topic named"))
        check("fallback greeting always passes",
              lambda: vet_greeting(fallback_greeting(comp.last_session()),
                                   required_greeting_words(comp.last_session())))
        check("the model is refused off the loopback",
              lambda: (_rejects_nonloopback(), "https://api.openai.com/... raises"))
        check("a foreign origin is refused",
              lambda: (_cors_grants_null_only(), "only Origin: null is granted"))
        check("writing outside the archive raises",
              lambda: (_guard_refuses(tmp), "WroteOutside raised"))
        check("one writer per file, enforced",
              lambda: (_note_refused(comp), "the learner cannot write the sibling's files"))
        turns = [c for c in stub.calls if not _is_greeting_call(c)]
        checks_n = [c for c in stub.calls if _is_greeting_call(c)]
        check("the constitution conditions every turn",
              lambda: (bool(turns) and all("THE TEXT THAT BINDS YOU" in c["system"] for c in turns),
                       f"{len(turns)} turn(s), binding text in each"))
        check("world-knowledge is the taught/ list only",
              lambda: (bool(turns) and all("WORLD-KNOWLEDGE" in c["system"] for c in turns),
                       "the I1 audit surface is in every turn"))
        check("the greeting is a brief, not the binding text",
              lambda: (bool(checks_n)
                       and all("THE TEXT THAT BINDS YOU" not in c["system"]
                               and "You are the cognitive sibling of one learner" in c["system"]
                               for c in checks_n),
                       f"{len(checks_n)} greeting(s) on the 600-char brief (decision, measured)"))
        check("no recency term in retrieval",
              lambda: _no_recency(comp))
        check("the turn contract travels last",
              lambda: _contract_is_last(stub))
        check("a voice replacement reaches the learner (R2)",
              lambda: _voice_notice())
        check("a compliant model greeting is accepted",
              lambda: _model_greeting(accepted=True))
        check("a warm greeting is rejected and falls back",
              lambda: _model_greeting(accepted=False))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    n = len(checks)
    passed = sum(1 for _n, ok, _w in checks if ok)
    print(f"\n  => {passed}/{n} helper checks pass")
    return passed == n


def _rejects_nonloopback():
    try:
        LocalModel("m", url="https://api.openai.com/v1/chat/completions")
    except ValueError:
        return True, "refused"
    return False, "a non-loopback model URL was accepted"


def _cors_grants_null_only():
    src = (HERE / "sib.py").read_text(encoding="utf-8")
    ok = 'Access-Control-Allow-Origin", "null"' in src and 'Allow-Origin", "*"' not in src
    return ok, "wildcard absent, null present"


def _guard_refuses(tmp):
    comp = Companion(HERE / "examples/minimal", StubModel())
    try:
        comp._guard(tmp / "escape.txt")
    except WroteOutside:
        return True, "WroteOutside"
    return False, "the guard allowed an outside path"


def _note_refused(comp):
    try:
        comp.note("memory/blocks/persona.md", "I am not Juno.")
    except PermissionError:
        return True, "persona.md refused"
    return False, "the learner could write the sibling's self"


def _no_recency(comp):
    """Non-vacuous: the ranker must put the *most significant* relation first even
    though another one is newer -- and the fixture is built so those differ."""
    now = dt.datetime.now(dt.timezone.utc)
    live = comp.arch.relations()
    if len(live) < 2:
        return False, "not enough relations to test"
    newest = max(live, key=lambda r: str(r.get("t_created") or ""))
    most_sig = max(live, key=lambda r: comp.arch.significance(r, now))
    top = comp.retrieved(None, k=1)[0]
    if top["id"] != most_sig.get("id"):
        return False, f"top-ranked {top['id']} is not the most significant ({most_sig.get('id')})"
    if newest.get("id") == most_sig.get("id"):
        return False, "vacuous: the most significant relation is also the newest"
    return True, f"{top['id']} (salient) ranks above {newest.get('id')} (newer)"


def _is_greeting_call(call):
    """A greeting is identified by the contract it was given, so no call signature has
    to change just to tell the checks what it is."""
    m = call.get("messages") or []
    return bool(m) and m[-1].get("role") == "system" and \
        str(m[-1].get("content", "")).startswith(GREETING_CONTRACT_MARK)


# ---------------------------------------------------------------------------
# the rite, checked
# ---------------------------------------------------------------------------

LAYOUT = ["SPEC.md", "manifest.json", "record", "events", "memory/blocks",
          "memory/graph/entities.jsonl", "memory/graph/relations.jsonl",
          "memory/graph/trails",
          "memory/index/CACHE.md", "narrative/we.md", "narrative/learner.md",
          "narrative/sibling.md", "learning/curriculum.md", "learning/taught",
          "learning/search-log", "consent/consent.md", "consent/handover.md", "sealed",
          "eval/indicators.jsonl", "tombstones.jsonl", "provenance.jsonl"]
# CONSTITUTION.md is deliberately NOT in that list: it is the one file a fresh archive is
# supposed to lack, because only the sibling may write it, and only by the rite.


class ScriptedModel:
    """A stand-in that answers with a prepared list, and remembers exactly what it was told.
    The second answer can therefore be checked against the complaint that provoked it."""

    name = "scripted/model-not-in-the-archive"

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def complete_contract(self, system, messages, contract, **kw):
        self.calls.append({"system": system, "messages": messages, "contract": contract})
        return self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]


def _rite_fixture(tmp, hollow=False):
    """A fresh archive with no rendering, and a household constitution shaped like the real
    one -- the same headings, the same names -- so the digest is exercised, not bypassed."""
    import mkfixture
    archive = tmp / "a"
    mkfixture.build(str(archive))
    good = (archive / CONSTITUTION_FILE).read_text(encoding="utf-8")
    (archive / CONSTITUTION_FILE).unlink()
    binding = tmp / "household constitution.md"
    binding.write_text(
        "# The household's constitution\n\n## Part I - The pillars\n"
        + "\n".join(f"- `{q}` -- a pillar" for q in tc.CONSTITUTION_PILLARS)
        + "\n\n## Part II - The invariants\n"
        + "\n".join(f"| **{i}** | what it forbids |" for i in tc.CONSTITUTION_INVARIANTS)
        + "\n\n## Part V - The two windows\n- the guardian's window\n- the study window\n"
        + "\n## Appendix A - The invariants at a glance\n"
        + "\n".join(f"| {i} | one line |" for i in tc.CONSTITUTION_INVARIANTS)
        + "\n\n## Appendix B - checking\n", encoding="utf-8")
    return archive, binding, good


def _rite_first_act():
    """Opening a session on a fresh archive writes the rendering -- the first act really is
    first -- and provenance records it with fixity.  The model's own name is nowhere in what
    it was sent (I2), which is why the brief carries no voice note."""
    tmp = Path(tempfile.mkdtemp(prefix="sib-rite-"))
    try:
        archive, binding, good = _rite_fixture(tmp)
        stub = StubModel(good)
        comp = Companion(archive, stub, constitution_path=str(binding))
        comp.session_open()
        ok11, why11 = tc.check11_constitution({"archive": archive})
        prov, _ = tessera.read_jsonl(archive / "provenance.jsonl")
        last = prov[-1] if prov else {}
        named = stub.name in json.dumps(stub.calls, default=str)
        return ((ok11 and last.get("event") == "constitution_rendered"
                 and last.get("fixity") == tessera.sha256_file(archive / CONSTITUTION_FILE)
                 and not named and bool(comp._session_notes)),
                f"{why11}; recorded {last.get('id')}; model-name leaked: {named}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _rite_retry():
    """A hollow rendering is refused, the retry is told exactly what was refused, and the
    second attempt -- a good one -- is written.  A retry that is not told anything is a retry
    that repeats the failure."""
    tmp = Path(tempfile.mkdtemp(prefix="sib-rite-"))
    try:
        archive, binding, good = _rite_fixture(tmp)
        hollow = good.replace("**I12 --", "I12, on reflection, is fine by me.", 1)
        assert hollow != good, "the example rendering does not use the required form"
        model = ScriptedModel([hollow, good])
        out = Companion(archive, model, constitution_path=str(binding)).render_constitution()
        told = "I12" in model.calls[-1]["contract"]
        ok11, why11 = tc.check11_constitution({"archive": archive})
        return ((out.get("written") and out.get("attempts") == 2 and told and ok11),
                f"attempts={out.get('attempts')}, retry told why: {told}, {why11}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _rite_refuses():
    """Two hollow attempts and nothing is written -- not a placeholder, not a half file, and
    no provenance claiming a rendering exists."""
    tmp = Path(tempfile.mkdtemp(prefix="sib-rite-"))
    try:
        archive, binding, good = _rite_fixture(tmp)
        hollow = good.replace("**I12 --", "I12: fine, honestly.", 1)
        out = Companion(archive, ScriptedModel([hollow]),
                        constitution_path=str(binding)).render_constitution()
        prov, _ = tessera.read_jsonl(archive / "provenance.jsonl")
        claimed = any(p.get("event") == "constitution_rendered" for p in prov)
        return ((not out.get("written") and not (archive / CONSTITUTION_FILE).exists()
                 and not claimed and bool(out.get("complaints"))),
                f"nothing written, nothing claimed; refused: {str(out.get('complaints'))[:70]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _skeleton_layout():
    """A new archive is the layout the format describes -- and lacks exactly the one file the
    rite is for."""
    tmp = Path(tempfile.mkdtemp(prefix="sib-layout-"))
    try:
        root = tmp / "fresh"
        init_archive(str(root), "Tessera")
        missing = [w for w in LAYOUT if not (root / w).exists()]
        return ((not missing and not (root / CONSTITUTION_FILE).exists()),
                f"{len(LAYOUT)} paths declared, missing {missing}; no rendering until the rite")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _contract_is_last(stub):
    """A format contract binds when it is the last thing read -- so this is structural,
    not a promise: the final message of every turn carries the reminder."""
    calls = [c for c in stub.calls
             if any("HOW TO REPLY" in m.get("content", "") for m in c["messages"])]
    if not calls:
        return False, "no turn carried the contract"
    ok = all(m["messages"][-1]["role"] == "system"
             and "HOW TO REPLY" in m["messages"][-1]["content"] for m in calls)
    return ok, f"{len(calls)} turn(s), reminder last in each"


def _voice_notice():
    """R2: the sibling is told its voice was replaced, so it can tell her.  The notice
    must survive the fallback path, not only a compliant model."""
    tmp = Path(tempfile.mkdtemp(prefix="sib-voice-"))
    try:
        archive = tmp / "a"
        import mkfixture
        mkfixture.build(str(archive))
        comp = Companion(archive, StubModel("Welcome back! I'm so excited!"))  # always rejected
        comp.revoice()
        st = comp.session_open()
        low = st["greeting"].lower()
        return (st["voice_note"] is True and "replaced" in low and st["how"] == "fallback",
                f"how={st['how']}, notice carried in the greeting")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _model_greeting(accepted):
    """The model path, end to end, with no socket: a compliant greeting must ship,
    a warm one must be refused and replaced by the fallback."""
    good = ("Last time you were working out why the order of elimination matters. "
            "Do you want to keep going with that, or do something else?")
    bad = "Welcome back! I'm so excited to see you again!"
    stub = StubModel(bad if not accepted else good)
    comp = Companion(HERE / "examples/minimal", stub)
    st = comp.session_open()
    if accepted:
        return (st["how"] == "model" and st["greeting"] == good,
                f"how={st['how']}")
    return (st["how"] == "fallback" and st["greeting"] != bad,
            f"how={st['how']}, greeting not shipped")


# ---------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(description="The Cognitive Sibling's companion (stdlib only).")
    p.add_argument("--archive", help="the Tessera archive to serve")
    p.add_argument("--settings", help="where setup is remembered (default: settings.json "
                                      "beside this script)")
    p.add_argument("--constitution", help="the household's constitution, kept beside the "
                                          "archive; read only when the sibling writes its "
                                          "own rendering of it")
    p.add_argument("--render-constitution", action="store_true",
                   help="have the sibling write its own CONSTITUTION.md now, and exit")
    p.add_argument("--voice", default="gemma-3-4b-it-qat",
                   help="the local model that speaks (never recorded in the archive)")
    p.add_argument("--model-url", default=DEFAULT_MODEL_URL)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--thinking", action="store_true", help="let the model reason before replying")
    p.add_argument("--open", action="store_true", help="print the session opening, then exit")
    p.add_argument("--revoice", action="store_true", help="record that the voice was replaced")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)

    if args.selftest:
        print("sib.py selftest -- hermetic, nothing on the network\n")
        return 0 if selftest() else 1

    settings_path = (Path(args.settings).expanduser().resolve() if args.settings
                     else (HERE / SETTINGS_FILE))
    settings = None
    if not args.archive:
        try:
            settings = load_settings(settings_path)
        except ValueError as exc:
            p.error(str(exc))
    if not args.archive and settings:
        prov = settings.get("provider") or {}
        args.archive = settings["archive"]
        args.voice = prov.get("model") or args.voice
        args.model_url = model_url_for(prov.get("base_url")) or args.model_url
        args.port = int(settings.get("port") or args.port)
        args.constitution = settings.get("constitution") or args.constitution

    if not args.archive:
        print("sib: nothing is configured yet.  Open the settings screen in the page and "
              "choose which local model should speak.\n", flush=True)
        serve(None, args.port, settings_path=settings_path)
        return 0

    model = LocalModel(args.voice, args.model_url, thinking=args.thinking)
    comp = Companion(args.archive, model, constitution_path=args.constitution)
    if args.render_constitution:
        out = comp.render_constitution(args.constitution)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out.get("written") or out.get("why") == "already written" else 1

    if args.revoice:
        print(json.dumps(comp.revoice(), indent=2))
        return 0

    if args.open:
        st = comp.session_open()
        print(f"\n--- {comp.arch.manifest.get('sibling_name')} ---\n")
        print(st["greeting"])
        print(f"\n[how: {st['how']} · offered: {st['offered']} · "
              f"last: {str(st['last_session']['date'])[:10]}]\n")
        if comp._session_notes:
            print("[notes] " + " | ".join(comp._session_notes) + "\n")
        print(st["disclosure"])
        return 0

    serve(comp, args.port)


if __name__ == "__main__":
    sys.exit(main())
