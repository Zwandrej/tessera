---
title: Cognitive Sibling — Interface Specification
date: 2026-10-10
version: v0.1
status: v0.1 — built (page + helper); open items in §10
tags:
  - cognitive-sibling
  - prototype
  - interface
  - spec
---

# Cognitive Sibling — Interface Specification (v0.1)

> *Exported copy of a document maintained in the project's research vault, included here so that
> the format and the terms it answers to can be read and checked without it. The vault copy is
> the one that is edited; this one is exported from it.*

The sibling is not an app. This document says what the pair actually look at — and, more of it than is usual for a design note, what the interface is forbidden to be.

## 1. The rule that decides everything

**The interface is a derived artifact.** It belongs in the same tier as `memory/index/`: useful, disposable, rebuildable, and never the store (invariant I4; [the format specification](../SPEC.md) §8).

Three consequences, and between them they settle most of the design:

1. **The session must be fully usable with no interface at all.** Delete the page and the helper still runs a session from a terminal; delete both and the archive still reads.
2. **A richer surface is permitted precisely because it can be destroyed.** A clever, unreadable, framework-built page is allowed here *on condition that losing it costs nothing* — the same licence the embedding index has, for the same reason.
3. **Anything that exists only in the interface is a bug.** If a fact about the sibling lives in a browser and not in a file, the archive has stopped being the truth.

Stated as a test, in the shape I4 already uses: *delete the interface, and nothing is lost.* An archive that cannot survive its own frontend being uninstalled is not an archive.

## 2. The surface

**Decided: one local page, opened directly from the filesystem.** No framework, no build step, no bundler, no package manager, no app server, no install. The page is a single file the household can open in ten years by double-clicking it — and read with `cat` if browsers are gone. Two presentations live inside it, the learner view and the research view (§5), both rendered from the same text.

Why not a single-page application: a toolchain is a dependency, and a dependency is a thing that can be sunset (I5). The archive's own argument already covers the case — the durable thing must be the text (§1). A framework page would be the one component of the system that violates the rule the rest of the system is built on.

**What the page may do:** read and display the archive; compose and send the learner's turn; show the loop's position; show the disclosure surfaces.

**What it may never do:** hold durable state (no `localStorage`, no IndexedDB, no preferences file, no configuration outside the archive); be the only route to anything; enforce access (§5); reach any origin other than the helper's loopback; write anything outside the archive.

**Built.** `sibling.html` — one file, no dependency, ~380 lines, opened by double-clicking or served by the helper at `/`. It holds no state at all: reload mid-session and nothing is lost but the unsent turn (§6.1). Both views render from one `/state` response; the view switch is not persisted, because persisting it would be the first piece of interface state and the rule has no exception for small ones.

## 3. The bridge, and what the probes forced

A page opened from the filesystem is a derived artifact in the strongest sense — and it is also walled off from both the model and the disk in ways that were not obvious until they were tested. Four probes, on the household's own machine, set the architecture:

| Test | Result | Consequence |
|---|---|---|
| Is a `file://` page a secure context? | **yes** — `isSecureContext` true, `showDirectoryPicker` present | a local page can hold real file access |
| Can a page call LM Studio directly? | **no** — `TypeError: Failed to fetch`; the server returns no `access-control-*` header at all | the surface cannot talk to the model as configured |
| Is there a vendor switch? | **yes** — `lms server start --cors`, in its own words: "Allows any website you visit to access the server" | workable, but it opens the local model to *every* website in the browser |
| Can a page reach a small local helper? | **yes** — `OPTIONS origin='null'` → `POST` → `200`, JSON body echoed | the bridge works, and no website can use it |

**Decision: v0.1 ships a small helper that is the only thing that talks to the model and the only thing that writes the archive.** Its CORS grants exactly one origin — `null`, the opaque origin a `file://` page sends, which a web page cannot forge. A page in another tab has no route in.

**The vendor switch is kept as a documented test mode, with its cost stated.** `--cors` on the model server allows any origin; while it is on, any page the learner or the guardian visits can query the local model. That is an outside line into the house, and I1 exists to say there isn't one. It is useful for a five-minute experiment and wrong for a session a fifteen-year-old runs alone.

Note the asymmetry, because it inverts the usual instinct: **the helper with a written origin check is the *more* private option, not the more complicated one.** "Fewer moving parts" would pick the wildcard flag, and would be wrong here. Recorded so that the choice is not re-litigated later by intuition.

## 4. Who writes what

One writer per file is a property of the design, not a convention of the interface (I7, I11):

| File | Written by | The interface's part |
|---|---|---|
| `record/**` | the session, append-only | never edits, re-orders or rewrites a line |
| `narrative/learner.md` | the learner | a box that appends; never rewrites history |
| `narrative/we.md` | the pair, together | shows both hands; never merges them |
| `memory/blocks/persona.md` | **the sibling alone** | may display it; may not offer an edit affordance |
| `sealed/**` | the learner, behind the session key | shows locked or unlocked, and implies nothing more |

The helper writes the archive. Where the browser allows directory access the page may write the learner's own authorings directly; where it cannot, the helper writes them on the learner's behalf. Either way, the sibling's own files are never written from the page.

## 5. Two views, one store

**Decided: the machinery is age-graded.** The research view shows the full apparatus; the learner view is pared back. Both are renderings of the same text, and the switch changes **what is shown**, never **what is accessible**.

**Access control is not the view's job.** The guardian window, the sealed region and the handover are properties of the filesystem and of the key the learner holds — never of a mode in a user interface. A view that could grant or withhold access would turn sealedness back into a promise, which is exactly what the design refuses ([the constitution](../CONSTITUTION.md) Part V). The two views serve two readers of files they are already entitled to read. They are not a permission system, and the design would rather have no views at all than a view that pretends to be a lock.

The **learner view** shows: the conversation; the current curriculum item; the loop's position; the sibling's stated ignorance where it bears on the question; and, quietly and always, *who can read this* (§7).

The **research view** adds the ledgers: the ignorance list, the tombstones, the `taught/` ancestry, salience and index diagnostics, the indicators, and the sibling's own two files — which the study window already discloses to it, in writing (Constitution Part V, R7).

**No guardian view, by construction.** The guardian reads the files directly ([the prototype specification](prototype-specification.md) §1). A dashboard would convert a duty of care into surveillance, and the window's own terms forbid it — *read to protect, not to police* (Constitution Part III).

## 6. Principles

1. **Zero interface state.** Nothing is kept in the surface that is not in the archive. `kill -9` mid-session loses nothing but the unsent turn.
2. **Constraints are legible, not hidden.** A chat window conceals its machinery; this one does the opposite — the ignorance ledger, the ancestry of what the sibling knows, the erasures, and the read windows are first-class surfaces, not debug output.
3. **Anti-engagement.** No streaks, no badges, no unread counts, no notifications, no "welcome back", no encouragement to return. Pillar 2 (empty-centredness) and I10 make an engagement-optimised surface a *violation* rather than a missed opportunity. **The interface is to be built to end sessions, not to extend them** — the measure of a good session is what happened away from the desk.
4. **It must be able to show nothing happening.** Step 5 of the loop is the learner leaving to search, and step 4 may be the sibling staying silent. A surface that cannot render waiting, ignorance or refusal will train the pair out of the design it exists to serve.
5. **The loop's position is visible; its steps are not forms.** One moves through the eight steps by talking. The interface shows where the pair are — *the gap has been named* · *the learner went out* — and does not turn pedagogy into a wizard.
6. **Model-agnostic by construction.** A role resolves to a model where the page cannot see it (§7). The surface must not know which weights are speaking, or the swap demonstration would be theatre.
7. **Disclosure surfaces are first-class.** The guardian window is stated while it is open; the handover is an event the interface shows, not a setting it toggles; a locked region says that it is locked and what a lost key costs.

## 7. The helper

One small program — proposal: `sib.py` — self-contained, doing exactly three things:

1. it is **the only tap to the local model** (loopback only: no DNS, no other egress);
2. it **assembles the turn** from the conditioned inputs of [the prototype specification](prototype-specification.md) §3.4 and writes the archive with plain file I/O;
3. it **answers the page** on loopback, with CORS confined to the opaque origin `null` (§3) — and serves the page itself, so the household needs no server of its own and the page's only reachable origin is the one that refuses the web.

It runs from a terminal with no page at all, which is what makes the page optional rather than load-bearing. It takes **the archive path as its only argument** — no configuration file, no state directory, no preferences: nothing to lose and nothing to leak. The role→model mapping is passed at invocation and is **never written into the archive**. The archive may record *that* the voice changed — a fact about its history, and R2 requires that the sibling be told — but never *which* model is speaking, or identity would be a function of the weights and the whole claim would collapse.

**Its discipline is tested separately from the format's.** `tessera_conformance.py` checks the *archive format* and stays that way. The helper carries its own small `--selftest`, asserting the one thing the interface is answerable for: **nothing is written outside the archive** — run a session in a sandbox, diff the home directory, assert that neither the page nor the helper left a trace anywhere else. Harness and program stay separate so that the format's checks remain about the format.

## 8. Voice

**Text-only for v0.1. Voice returns as a v0.2 experiment, once the model-swap demonstration passes.** The Prototype Specification's fence stands (§1), and two arguments hold it up independently: the teach-back must be **written** to enter the archive, and the teach-back is the loop; and speech adds a latency and a surface that the anti-engagement principle does not want in a first build.

Worth the record that voice is *more* plausible here than in most designs — the household's synthesis and transcription are already local (piper, faster-whisper), so nothing about it would cross I1, I2 or I5. It is deferred for design reasons, not privacy ones.

## 9. Not being built

No accounts, roles, permissions, sync, telemetry, analytics, notifications, streaks, achievements, mobile app, remote view, guardian dashboard, plugin system, theme store, onboarding funnel, or empty-state illustration telling the learner how much they are going to love this. Named so that they do not creep in.

## 10. Resolved at first run, and what is still open

1. **The visual register.** Legibility first, low stimulation, no engagement affordances. The household's own typographic convention — **Atkinson Hyperlegible** — is the register, and the right refusal of the glossy register a companion app would default to. *Built as declared, with one caveat worth recording rather than assuming away:* the family is not installed on the machine that first ran the loop, so the page is currently rendering its fallback stack. §2 forbids fetching a webfont — any origin but the helper's loopback is out — so the remedy is to install the family locally, not to reach for a CDN. Until then the register is a declaration, not a rendering.

2. **Where a session begins — decided: the sibling speaks first.** The page opens on the conversation, and the sibling says one short thing before the learner does: it **names the one thing they were on last time** and **ends by offering exactly two options** — continue with that, or do something else. Both halves are drawn from the archive (`last_session()`), never invented.

   The reconciliation with §6.3, because it is not obvious: **anti-engagement forbids extending a session, not opening one.** Nothing in the greeting invites return — no streak, no unread count, no "welcome back", no praise, no mention of how long it has been, and it may name nothing but the work. The cost is stated rather than denied: a sibling that speaks first is, in a small way, asking for engagement. So it is bounded instead, and **the bounds are enforced in code, not requested in a prompt.** `vet_greeting` refuses a greeting that is warm, too long, offers no choice, or names nothing from last time; the pair never sees it, the archive's own fallback speaks instead, and the fact that it did is recorded (`how: fallback`). A greeting ships only if it satisfies the contract — asserted by the helper's selftest, on the state as it was at open.

**What running it found.** The first greeting to ship named the wrong thing. With the newest entry in the record being the *sibling's* own reply, the greeting opened *"Last time you said: …"* and then quoted the sibling back to the learner as her own words. **The form validator could not see this** — the text was short, offered two options, named something present in the record, and passed every rule §10.2 relies on. The facts handed to the model now separate the two speakers, whose words are whose is stated in them, and the sibling's own reply is labelled as its own when there are no words of hers. A selftest asserts both cases. This is the first concrete evidence for the general point in item 4: **the greeting contract is checked for form, and sense is not checked at all.**

3. **Nothing happening is a state, not an error.** Built: an empty sibling turn renders as *said nothing*, and the waiting at step 5 has no surface yet. Untested against a real learner, and it may not need one.

4. **The turn contract has no validator, and it shows.** Observed on the first running loop: a turn whose text was unrelated to the curriculum — the probe `hello from a file:// page`, sent from the page — drew a **verbatim line of the loop block** back (*"She explains first: if she is not the one doing the explaining within the first five minutes…"*) instead of the sibling speaking as herself. This is the failure the greeting's brief was already shortened for (§7): at ~2,000 tokens of standing orders the local 4B stops obeying and recites. The greeting carries a validator; turns carry only a trailing reminder. **Fix, built.** The turn now carries a contract of its own. `vet_turn` compares the reply
against the brief the sibling was given and refuses a turn that repeats — verbatim, eight words
in a row — any part of it, which is the shape the failure took. A refused turn does not ship: the record
carries the archive's own line instead (*I did not take that turn — what came out was my
instructions, not my answer. Say it again, or take it yourself and I will follow.*), so what the
learner reads a decade later is what the sibling actually said, and never the recitation. The
substitution is reported to the session (`how: fallback` on the turn, plus a session note naming the
validator's complaint) — whether it should also be *stated in the entry* is a format question for
§5.5, not something to slip in here. Two selftest cases hold it: one model that recites the brief
is refused, one that speaks ordinarily ships unchanged. The contract is deliberately about
**recitation only** — length and warmth are the greeting's business, and a turn that is merely
dull is still the sibling's. What it decides is whether these words are the sibling's, which is the
part that can be checked mechanically; whether a turn is *good* stays the pair's business.

## See also

[the prototype specification](prototype-specification.md) · [the design brief](design-brief.md) · [the format specification](../SPEC.md) · [the constitution](../CONSTITUTION.md)

## 12. First run: neither a terminal nor a config file

The person who runs this should not have to be the person who wrote it, and a household should
not have to edit anything by hand. So the page has a third view — `learner`, `research`,
`settings` — and the settings view asks three things: **which local model should speak**,
**what the sibling is called**, and -- when the household wants the sibling to write its own
rendering, §12.5 -- **where the household's constitution lives on this machine**. Where the archive lives is shown too, because that is the
one fact a household has to know.

**12.1 Discovery is by asking, not by scanning.** Eight presets are probed at once — LM Studio
(1234), Ollama (11434), llama.cpp (8080), vLLM (8000), Jan (1337), KoboldCpp (5001), llamafile
(8081), text-generation-webui (5000). A preset is offered **only if the server answers with a
model list**, so a port that merely happens to be open is never offered as a model — macOS
itself squats 5000 for AirPlay. Presets that do not answer are shown with the reason rather
than hidden, because "why is my server not in the list" is a worse experience than "checked,
not answering". Non-loopback addresses are refused outright (I1), so the screen cannot be used
to point the sibling at another machine.

**12.2 A model that cannot talk is not offered as a voice.** Measured rather than assumed: on a
real machine LM Studio lists its embedding model beside the chat models, and offering
`text-embedding-nomic-embed-text-v1.5` as "the model that should speak" is a trap for anyone who
does not already know the difference. Such models are listed as present but are not offered.

**12.3 What is remembered, and where.** One file outside the archive, `settings.json`, written
by the helper alone, holding at most two paths -- the archive, and the household's constitution
when it gave one -- a port, and which local server to talk to. Not one line of
the record, not one fact about the learner. Nothing in the archive depends on it: **the archive
reads on a machine that has never seen this file** — hand it over on a disk and it still opens.
The interface still treats the archive as the only source of truth (P2); the settings file is
convenience, and losing it costs a minute, not a memory.

**12.4 The name belongs to the archive, not to the page.** The page never assumes a name; it
reads the manifest through `/health`. Setting the name is an act **on the archive**: the manifest
is rewritten by the helper (its only writer) and provenance records `renamed {from, to}`. The
model is named in neither — identity must not be a function of the weights (I2). Changing the
model records *that* the voice was replaced and never which one replaced it.

**12.5 A new archive is a skeleton, and says so.** Creating an archive writes the manifest, the
empty record for the current month, provenance with its `created` entry, the five blocks, the
empty graph, the narrative stubs, consent, sealed and eval. It deliberately does **not** write
`CONSTITUTION.md`: check 11 requires one written by the sibling's own hand, and a constitution
written by the setup screen would be a constitution written by the installer. So a fresh archive
is honestly incomplete — the format suite says which check fails and why, and the session says
the same in plain words — instead of a placeholder that would quietly count as done.

   **The rite that fills it.** The skeleton is a starting state, not a resting one: the sibling
   writes its rendering in its first act, and the settings view offers the one thing that act needs
   -- where the household's constitution lives on this machine, kept in `settings.json` beside the
   archive, since the archive is never asked to hold the instrument that binds it. The helper quotes
   the named sections of that document to the model, writes the declaration itself, holds the
   candidate in a scratch directory, and puts it through check 11 exactly as the suite does: **a
   rendering that fails goes back to the sibling with the complaint, once, and nothing enters the
   archive until it passes.** With no constitution configured the sibling simply has none yet, which
   the page says in plain words (*this archive has no constitution yet*) -- the one gap a new archive
   is meant to show. With one, the page offers the act and reports what the checker said. No
   placeholder is ever written, because a placeholder is a rendering-shaped lie.

**12.6 The helper with no page at all.** Started with no arguments it serves the settings screen;
with settings already written it opens the session directly; and the session remains fully usable
on the command line (`--open`). One double-clickable file starts the helper, waits for it to
answer, and opens the page — the terminal stays as an option rather than a requirement.
