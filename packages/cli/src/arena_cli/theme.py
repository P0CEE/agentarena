"""Vocabulaire visuel keel du CLI — figé par le prototype (ticket 10).

Palette du dashboard (apps/dashboard/src/index.css) transposée au terminal :
olive = accent, amber = avertissement, violet = URLs, gris ink pour le texte.
Grammaire maximus : bannière en blocs, statuts au boot, sections ╭─ │ ╰.
"""

from importlib.metadata import PackageNotFoundError, version

from questionary import Style
from rich.console import Console
from rich.text import Text
from rich.theme import Theme

OLIVE = "#7a9200"
AMBER = "#e77b14"
VIOLET = "#8a72e5"
DANGER = "#c2410c"
MUTED = "#737373"
FAINT = "#a3a3a3"

console = Console(theme=Theme({
    "accent": OLIVE,
    "accent.b": f"bold {OLIVE}",
    "warn": AMBER,
    "alt": VIOLET,
    "danger": DANGER,
    "muted": MUTED,
    "faint": FAINT,
}))

KEEL = Style([
    ("qmark", f"fg:{OLIVE} bold"),
    ("question", "bold"),
    ("answer", f"fg:{OLIVE} bold"),
    ("pointer", f"fg:{OLIVE} bold"),
    ("highlighted", f"fg:{OLIVE} bold"),
    ("instruction", f"fg:{FAINT}"),
])

QMARK_SECTION = "│"  # questions posées à l'intérieur d'une section
QMARK_MENU = "›"
POINTER = "›"


def _version() -> str:
    try:
        return version("arena-cli")
    except PackageNotFoundError:
        return "dev"


def banner() -> None:
    """Icône AA pixel + nom, tagline — l'écran d'accueil."""
    console.print()
    console.print(Text.assemble((" ▄▀█ ▄▀█  ", "accent.b"), ("AGENTARENA", "bold"),
                                (f"  v{_version()}", "faint")))
    console.print(Text.assemble((" █▀█ █▀█  ", "accent.b"),
                                ("PoS BFT · agents IA · moteur Yuma", "muted")))
    console.print()


def status_ok(text: str) -> None:
    console.print(Text.assemble((" ✓ ", "accent"), (text, "muted")))


def status_warn(text: str) -> None:
    console.print(Text.assemble((" ✗ ", "warn"), (text, "muted")))


def status_note(text: str) -> None:
    console.print(Text.assemble((" · ", "faint"), (text, "muted")))


def section_open(title: str, detail: str = "") -> None:
    console.print(Text.assemble(("╭─ ", "accent.b"), (title, "bold"), (detail, "muted")))


def section_field(label: str, value: str) -> None:
    console.print(Text.assemble(("│ ", "accent"), (f"{label:<12}", "muted"), (value, "bold")))


def section_close() -> None:
    console.print("[accent]╰" + "─" * 50 + "[/]")
