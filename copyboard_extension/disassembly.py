"""Scene disassembly: split one tagged text into per-tag transcripts.

CopyBoard's chambers are paste destinations.  Some texts arrive in the
opposite shape: one piece of prose that belongs to several destinations.  A
dialogue scene is the clearest example, but the same operation works for
meeting notes, interview transcripts, or any bundle that must be divided
between paste targets.

The source uses one deliberately explicit signal, a line beginning with
``@TAG:``::

    @ALICE: You're late.
    @BOB: The road was long.

    @ALICE:
    It always is.

Everything from a cue up to the next cue belongs to that tag.  Tags are
grouped case-insensitively and assigned to chambers in first-appearance order
(``@ALICE`` -> chamber 01, ``@BOB`` -> chamber 02).

This module is pure: it parses and plans, but never touches the clipboard,
the board, or the filesystem.  The CLI decides whether to apply a plan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# A meaningful character name is short; this also keeps a stray ``@`` line
# from swallowing a paragraph as a tag.
MAX_TAG_LENGTH = 40

# A cue starts with an optional indent, ``@``, the tag, and a colon.  The rest
# of the line is the first line of that tag's text.  Requiring the colon keeps
# ordinary prose such as "Ask @alice about it" from becoming a cue.
CUE_PATTERN = re.compile(r"^[ \t]*@(?P<tag>[^:\n]*):(?P<content>.*)$")


class DisassemblyError(ValueError):
    """Raised when tagged text cannot be turned into chamber assignments."""


@dataclass(frozen=True)
class Cue:
    """One ``@TAG:`` cue and the text that followed it."""

    tag: str
    key: str
    text: str
    line: int


@dataclass(frozen=True)
class Voice:
    """All text assigned to one tag, in source order."""

    tag: str
    key: str
    text: str
    cues: int
    first_line: int

    @property
    def characters(self) -> int:
        return len(self.text)

    @property
    def lines(self) -> int:
        return len(self.text.splitlines())

    @property
    def preview(self) -> str:
        collapsed = " ".join(self.text.split())
        return collapsed if len(collapsed) <= 72 else collapsed[:71] + "…"


@dataclass(frozen=True)
class DisassemblyPlan:
    """A validated tag-to-chamber layout, ready for preview or application."""

    voices: List[Voice]
    capacity: int
    preamble_lines: int
    preamble_characters: int
    total_lines: int


@dataclass
class _VoiceBuilder:
    tag: str
    key: str
    first_line: int
    cues: int = 0
    chunks: List[str] = field(default_factory=list)


def parse_tagged_text(text: str) -> Tuple[List[Cue], int, int, int]:
    """Parse ``@TAG:`` cues from ``text``.

    Returns ``(cues, preamble_lines, preamble_characters, total_lines)``.
    Text before the first cue is reported but not assigned to any tag, so a
    scene heading or title does not silently become dialogue.  Empty cues are
    returned with empty text; the planner drops tags that never received any
    content.
    """
    cues: List[Cue] = []
    lines = text.splitlines()
    current_tag: str = ""
    current_key: str = ""
    current_line: int = 0
    buffer: List[str] = []
    preamble_lines = 0
    preamble_characters = 0

    def flush() -> None:
        if not current_tag:
            return
        cues.append(
            Cue(
                tag=current_tag,
                key=current_key,
                text="\n".join(buffer).strip(),
                line=current_line,
            )
        )

    for number, line in enumerate(lines, 1):
        match = CUE_PATTERN.match(line)
        if match is None:
            if not current_tag:
                preamble_lines += 1
                preamble_characters += len(line) + 1
            else:
                buffer.append(line)
            continue

        tag = match.group("tag").strip()
        if not tag:
            raise DisassemblyError(f"line {number}: the @ cue has an empty tag")
        if len(tag) > MAX_TAG_LENGTH:
            raise DisassemblyError(
                f"line {number}: tag {tag!r} is longer than "
                f"{MAX_TAG_LENGTH} characters"
            )

        flush()
        current_tag = tag
        current_key = tag.casefold()
        current_line = number
        buffer = [match.group("content")]

    flush()
    return cues, preamble_lines, preamble_characters, len(lines)


def group_cues(cues: List[Cue]) -> List[Voice]:
    """Group cues by tag, preserving the order in which tags first appear."""
    builders: Dict[str, _VoiceBuilder] = {}
    order: List[str] = []

    for cue in cues:
        builder = builders.get(cue.key)
        if builder is None:
            builder = _VoiceBuilder(
                tag=cue.tag, key=cue.key, first_line=cue.line
            )
            builders[cue.key] = builder
            order.append(cue.key)
        builder.cues += 1
        if cue.text:
            builder.chunks.append(cue.text)

    voices: List[Voice] = []
    for key in order:
        builder = builders[key]
        transcript = "\n\n".join(builder.chunks)
        if not transcript.strip():
            continue
        voices.append(
            Voice(
                tag=builder.tag,
                key=builder.key,
                text=transcript,
                cues=builder.cues,
                first_line=builder.first_line,
            )
        )
    return voices


def plan_disassembly(text: str, capacity: int) -> DisassemblyPlan:
    """Validate ``text`` and return the chamber layout for its tags.

    ``capacity`` is the current cylinder size.  More tags than chambers is an
    error rather than a silent truncation, because dropping a character's
    transcript is exactly the failure this feature must avoid.
    """
    if capacity < 1:
        raise DisassemblyError("the cylinder has no chambers")

    cues, preamble_lines, preamble_characters, total_lines = parse_tagged_text(
        text
    )
    if not cues:
        raise DisassemblyError(
            "no @TAG: cues found; add a line like '@ALICE: hello'"
        )

    voices = group_cues(cues)
    if not voices:
        raise DisassemblyError("every @TAG: cue is empty")

    if len(voices) > capacity:
        listed = ", ".join(voice.tag for voice in voices)
        raise DisassemblyError(
            f"{len(voices)} tags ({listed}) do not fit in {capacity} chambers; "
            "use fewer tags or resize the cylinder in the editor"
        )

    return DisassemblyPlan(
        voices=voices,
        capacity=capacity,
        preamble_lines=preamble_lines,
        preamble_characters=preamble_characters,
        total_lines=total_lines,
    )


def plan_to_dict(plan: DisassemblyPlan) -> Dict[str, object]:
    """Return a JSON-ready description of ``plan``, including the transcripts."""
    return {
        "capacity": plan.capacity,
        "total_lines": plan.total_lines,
        "preamble": {
            "lines": plan.preamble_lines,
            "characters": plan.preamble_characters,
        },
        "voices": [
            {
                "chamber": index + 1,
                "label": f"{index + 1:02d}",
                "tag": voice.tag,
                "cues": voice.cues,
                "lines": voice.lines,
                "characters": voice.characters,
                "preview": voice.preview,
                "text": voice.text,
            }
            for index, voice in enumerate(plan.voices)
        ],
    }
