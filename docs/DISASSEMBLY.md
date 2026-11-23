# Scene disassembly

CopyBoard is organised around destinations: each chamber is a place you can
fire text into. Some texts arrive as one piece but belong to several
destinations. A dialogue scene is the clearest case. You have one manuscript,
but each character needs their own transcript.

`copyboard disassemble` splits one tagged text into one transcript per tag and
loads those transcripts into chambers 01…N. You can then fire each chamber into
its own document.

## Is this a good fit?

Yes, with one structural caveat. The model matches CopyBoard's strengths:

- Chambers already are per-destination paste slots.
- The operation is local and offline; the text never leaves the machine.
- It is explicit and previewable, so it cannot silently lose a character.
- It is useful beyond dialogue: meeting notes split by owner, interview
  transcripts split by speaker, bug reports split by component, or any bundle
  with a repeated marker.

The caveat is that CopyBoard's cylinder is a recency queue, not a set of
permanent named slots. Disassembly assigns tags to the *current* layout. A new
external copy rotates the cylinder, so the assignment is session-scoped. Fire
the transcripts before copying anything else, or use the CLI to fire them.
Persistent named slots and a GUI picker are docketed below.

## Tag syntax

A cue is a line that begins with `@TAG:`. Everything after the colon, and every
following line up to the next cue, belongs to that tag.

```text
A rain-soaked street at midnight.

@ALICE: You're late.
@BOB: The road was long.

@ALICE:
It always is.
The rain never stopped.

@BOB: Typical.
```

This produces:

| Chamber | Tag | Transcript |
| --- | --- | --- |
| 01 | `ALICE` | `You're late.` / `It always is.` / `The rain never stopped.` |
| 02 | `BOB` | `The road was long.` / `Typical.` |

Rules:

- Tags are grouped case-insensitively. `@ALICE` and `@alice` are one voice; the
  first spelling is shown.
- Tags may contain spaces: `@Old Man: Mind the step.`
- Tags are limited to 40 characters and cannot contain `:`.
- Cues are stripped from the output, so transcripts contain only the lines.
- Blocks assigned to the same tag are joined with one blank line.
- Text before the first cue is reported and ignored. It never becomes a voice.
  Put scene headings there, or use a pseudo-tag such as `@SCENE:` if you want
  stage directions in their own chamber.
- Untagged lines after a cue belong to the preceding tag. That includes action
  beats; they stay with the speaker they followed.
- Chambers are assigned in first-appearance order, so the first tag becomes
  chamber 01.
- More tags than chambers is an error, not a truncation. Raise the chamber
  count in the editor or combine tags.

## Commands

```bash
# Preview the tag-to-chamber layout; the cylinder is untouched
copyboard disassemble scene.txt --dry-run

# Load one transcript per tag into the cylinder
copyboard disassemble scene.txt

# Replace a cylinder that already holds rounds
copyboard disassemble scene.txt --replace

# Read the source from stdin, or from the clipboard when no source is given
pbpaste | copyboard disassemble -
copyboard disassemble --dry-run

# Machine-readable plan for an agent or script
copyboard --json disassemble scene.txt --dry-run
```

`copyboard --json` is a global flag, so it must come before the subcommand.

Applying a plan is destructive: it replaces every chamber. The command refuses
to do that on a non-empty cylinder unless `--replace` is present. Use
`--dry-run` first; it parses, validates and prints the same assignment without
touching the board.

If the desktop editor is open in another process, it will not live-reload the
new layout. Close or restart it after a CLI apply, or use `copyboard copy N` to
fire a chamber directly. This cross-process refresh limitation is shared by the
existing `add`, `remove` and `clear` commands.

## Python API

The parser and planner are pure and can be used without the CLI:

```python
from copyboard_extension import core, disassembly

plan = disassembly.plan_disassembly(text, core.get_chamber_count())
for index, voice in enumerate(plan.voices):
    print(index + 1, voice.tag, voice.characters)

core.replace_board([voice.text for voice in plan.voices])
```

## Status and docket

| Slice | Status |
| --- | --- |
| `@TAG:` parser and validation | Built |
| First-appearance chamber planner | Built |
| `copyboard disassemble` with `--dry-run`, `--replace`, `--json` | Built |
| Unit and CLI tests | Built |
| GUI **DISASSEMBLE** dialog with live preview | Docketed |
| Tag names shown on chambers / persistent tag→chamber map | Docketed |
| Auto-capture routing (a copied tagged text splits automatically) | Docketed |
| Export one file per tag (`--out-dir`) | Docketed |
| Stable named slots instead of a recency queue | Docketed |
| More than 16 destinations | Docketed |

The docketed items are deliberately separate. A GUI dialog needs a real display
to verify, and persistent labels change the board's data model; neither should
block the core split/assign workflow.
