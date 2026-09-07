# knowledge/

Everything the machine knows, split by whether it is about the craft or about the client.

## Already written, shared by every client

| File | What it is |
|---|---|
| `CONTENT_STRATEGIST_BRAIN.md` | 4,220 lessons distilled from 278 long-form videos by eight creators, organised into 19 subjects, ending with the ten places they flatly disagree and what each disagreement turns on |
| `SCRIPTING_TOOLKIT.md` | The swipe file: named hook patterns, eight reel skeletons, three carousel skeletons, and the weekly operating rhythm |

These are craft, so one copy serves everyone. Load them as-is.

## You write these, per client

Copy each `*_TEMPLATE.md` to the name without the suffix and fill it in. The templates are
instructions and stay in the repo; your filled-in copies are the client's and should not be
committed to a shared repo.

| File | What it decides | Written in |
|---|---|---|
| `WHO.md` | who the scripts are written AS | phase 1 |
| `BRAND_VOICE.md` | whether a script sounds like them | phase 1 |
| `PROOF_INVENTORY.md` | whether a script is specific or could be about anyone | phase 1 |
| `OFFER.md` | whether a call review can tell a good close from a bad one | phase 3 |
| `AUDIENCE.md` | who the sales-call brief thinks it is studying | phase 3 |
| `SETTLED_DECISIONS.md` | what the brief must not re-open | phase 3 |

`BRAND_VOICE.md` has no template on purpose. It is built in phase 1 by transcribing the
client's own reels and pulling out how they actually speak. A voice document written from
their written material produces essays: nobody says an essay to a camera, and that mistake
costs a full round of rejected scripts every time it is made.

## Loading them

```bash
python3 tools/content-machine/load_knowledge_doc.py \
  --agency <workspace id> --title "Content Strategist Brain" \
  --file knowledge/CONTENT_STRATEGIST_BRAIN.md
```

Same command per document, changing `--title` and `--file`. Titles matter: the scripter looks
for "Content Strategist Brain" and "Scripting Toolkit" by exact name and refuses to run
without both. Once loaded they are editable in the dashboard at `/knowledge`, and the writer
re-reads them on every run, so an edit there takes effect on the next script.

One document is created for you: **Script Feedback**, written the first time a script is
rejected from the Record tab or the morning email. Never write it by hand.
