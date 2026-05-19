#!/usr/bin/env python3
"""
rom_organizer.py — No-Intro ROM Set Organizer

Sorts ROMs in a system folder into subfolders by release type and language.
Run with --dry-run first to preview before anything moves.

Usage:
    python rom_organizer.py <system_folder> [--dry-run] [--log <logfile>]
"""

import argparse
import re
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Tag patterns — No-Intro naming convention
# ---------------------------------------------------------------------------

BIOS_RE = re.compile(r'^\[BIOS\]', re.IGNORECASE)

SPECIAL_TAGS = {
    "Demo":        re.compile(r'\(Demo[^)]*\)', re.IGNORECASE),
    "Beta":        re.compile(r'\(Beta[^)]*\)', re.IGNORECASE),
    "Proto":       re.compile(r'\(Proto[^)]*\)', re.IGNORECASE),
    "Unlicensed":  re.compile(r'\(Unl\)', re.IGNORECASE),
    "Hack":        re.compile(r'\(Hack\)', re.IGNORECASE),
    "Translation": re.compile(r'\(T[-+][A-Za-z]{2,}[^)]*\)', re.IGNORECASE),
    "Kiosk":       re.compile(r'\(Kiosk[^)]*\)', re.IGNORECASE),
}

# Region → language fallback (used when no explicit lang tag is present)
REGION_LANGUAGE_MAP = {
    "USA":         "English",
    "Europe":      "English",
    "UK":          "English",
    "Australia":   "English",
    "Canada":      "English",
    "Japan":       "Japanese",
    "Korea":       "Korean",
    "China":       "Chinese",
    "Taiwan":      "Chinese",
    "Germany":     "German",
    "France":      "French",
    "Spain":       "Spanish",
    "Italy":       "Italian",
    "Netherlands": "Dutch",
    "Brazil":      "Portuguese",
    "Portugal":    "Portuguese",
    "Russia":      "Russian",
    "Poland":      "Polish",
    "Sweden":      "Swedish",
    "Denmark":     "Danish",
    "Norway":      "Norwegian",
    "Finland":     "Finnish",
    "Greece":      "Greek",
    "World":       "English",   # "World" releases are English by convention
}

# Explicit language tag — e.g. (En), (En,Ja)
LANG_TAG_RE = re.compile(r'\(([A-Za-z]{2}(?:,[A-Za-z]{2})*)\)')

# Single region — e.g. (USA), (Japan)
REGION_TAG_RE = re.compile(r'\((' + '|'.join(re.escape(r) for r in REGION_LANGUAGE_MAP) + r')\)', re.IGNORECASE)

# Multi-region — e.g. (USA, Europe), (Japan, USA)
MULTI_REGION_TAG_RE = re.compile(r'\(([A-Za-z]+(?:,\s*[A-Za-z]+)+)\)')

# English language codes
ENGLISH_CODES = {"En"}

# Two-letter ISO codes → language name
LANG_CODE_MAP = {
    "En": "English",
    "Ja": "Japanese",
    "Ko": "Korean",
    "Zh": "Chinese",
    "De": "German",
    "Fr": "French",
    "Es": "Spanish",
    "It": "Italian",
    "Nl": "Dutch",
    "Pt": "Portuguese",
    "Ru": "Russian",
    "Pl": "Polish",
    "Sv": "Swedish",
    "Da": "Danish",
    "No": "Norwegian",
    "Fi": "Finnish",
    "El": "Greek",
}

# Top-level language folders — everything else goes under Other Localizations/
PRIMARY_LANGUAGES = {"English", "Japanese"}

# Special tags that get top-level folders instead of nesting under _Other/
PRIMARY_SPECIAL = {"Hack": "Rom Hacks"}

def get_lang_dest(lang_bucket: str) -> str:
    """Resolve a language bucket to its destination folder path."""
    if lang_bucket == "Other":
        return "_Other/Unknown"
    if lang_bucket in PRIMARY_LANGUAGES:
        return lang_bucket
    return f"Other Localizations/{lang_bucket}"


ROM_EXTENSIONS = {
    ".zip", ".7z", ".rar",                  # compressed
    ".nes", ".smc", ".sfc", ".gb", ".gbc", ".gba",
    ".nds", ".3ds", ".cia",
    ".iso", ".bin", ".cue", ".chd",
    ".n64", ".z64", ".v64",
    ".md", ".smd", ".gen",
    ".pce", ".ngp", ".ngc", ".ws", ".wsc",
    ".gg", ".sms",
    ".rom", ".img",
}


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def get_special_tags(name: str) -> list[str]:
    """Return any special tag folder names that match this filename."""
    return [folder for folder, pattern in SPECIAL_TAGS.items() if pattern.search(name)]


def get_language_bucket(name: str) -> str:
    """
    Determine the language bucket for a filename.

    Priority:
    1. Explicit language tag — English anywhere in tag wins
    2. Explicit language tag — first recognized code otherwise
    3. Single region tag fallback
    4. Multi-region tag fallback — English wins if any region implies it
    5. No match → "Other"
    """
    # Explicit language tag: (En), (En,Ja), (De), etc.
    lang_match = LANG_TAG_RE.search(name)
    if lang_match:
        codes = [c.strip() for c in lang_match.group(1).split(",")]
        if any(c in ENGLISH_CODES for c in codes):
            return "English"
        for code in codes:
            if code in LANG_CODE_MAP:
                return LANG_CODE_MAP[code]
        return "Other"

    # Single region tag: (USA), (Japan), etc.
    region_match = REGION_TAG_RE.search(name)
    if region_match:
        region = region_match.group(1)
        for key, lang in REGION_LANGUAGE_MAP.items():
            if key.lower() == region.lower():
                return lang
        return "Other"

    # Multi-region tag: (USA, Europe), (Japan, USA), etc.
    multi_match = MULTI_REGION_TAG_RE.search(name)
    if multi_match:
        regions = [r.strip() for r in multi_match.group(1).split(",")]
        langs = []
        for region in regions:
            for key, lang in REGION_LANGUAGE_MAP.items():
                if key.lower() == region.lower():
                    langs.append(lang)
                    break
        if "English" in langs:
            return "English"
        if langs:
            return langs[0]
        return "Other"

    return "Other"


def classify(filepath: Path) -> dict:
    """Return special tags and language bucket for a ROM file."""
    name = filepath.name
    return {
        "special": get_special_tags(name),
        "language_bucket": get_language_bucket(name),
    }


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------

def resolve_destination(system_folder: Path, bucket: str) -> Path:
    """Return destination subfolder, creating it if it doesn't exist."""
    dest = system_folder / bucket
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def safe_move(src: Path, dest_folder: Path, dry_run: bool) -> str:
    """Move src into dest_folder. Appends _dup if the destination already exists."""
    dest = dest_folder / src.name
    if dest.exists():
        dest = dest_folder / (src.stem + "_dup" + src.suffix)
    action = f"MOVE  {src}  →  {dest}"
    if not dry_run:
        shutil.move(str(src), str(dest))
    return action



# ---------------------------------------------------------------------------
# Main organizer
# ---------------------------------------------------------------------------

def organize(system_folder: Path, dry_run: bool, log_path: Path | None):
    if not system_folder.is_dir():
        print(f"ERROR: Not a directory: {system_folder}")
        sys.exit(1)

    rom_files = [
        f for f in system_folder.iterdir()
        if f.is_file() and f.suffix.lower() in ROM_EXTENSIONS
    ]

    if not rom_files:
        print("No ROM files found directly in the folder (not scanning subfolders).")
        sys.exit(0)

    print(f"{'[DRY RUN] ' if dry_run else ''}Processing {len(rom_files)} files in: {system_folder}\n")

    actions = []
    stats = {}

    for rom in sorted(rom_files):
        result = classify(rom)
        specials = result["special"]
        lang_bucket = result["language_bucket"]

        if BIOS_RE.search(rom.name):
            dest_folder = resolve_destination(system_folder, "_BIOS")
            action = safe_move(rom, dest_folder, dry_run)
            actions.append(action)
            stats["_BIOS"] = stats.get("_BIOS", 0) + 1

        elif specials:
            # First matching special tag wins
            tag = specials[0]
            dest_path = PRIMARY_SPECIAL[tag] if tag in PRIMARY_SPECIAL else f"_Other/{tag}"
            dest_folder = resolve_destination(system_folder, dest_path)
            action = safe_move(rom, dest_folder, dry_run)
            actions.append(action)
            stats[dest_path] = stats.get(dest_path, 0) + 1

        else:
            # Retail release — sort by language
            lang_dest = get_lang_dest(lang_bucket)
            dest_folder = resolve_destination(system_folder, lang_dest)
            action = safe_move(rom, dest_folder, dry_run)
            actions.append(action)
            stats[lang_dest] = stats.get(lang_dest, 0) + 1

    # Print action log
    for action in actions:
        print(action)

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Summary:")
    for bucket, count in sorted(stats.items()):
        print(f"  {bucket:<20} {count} files")
    print(f"  {'TOTAL':<20} {len(rom_files)} files")

    if dry_run:
        print("\nDry run complete. No files were moved. Re-run without --dry-run to apply.")

    # Write log
    if log_path:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"{'[DRY RUN] ' if dry_run else ''}ROM Organizer log: {system_folder}\n\n")
            f.write("\n".join(actions))
            f.write(f"\n\nSummary:\n")
            for bucket, count in sorted(stats.items()):
                f.write(f"  {bucket:<20} {count}\n")
        print(f"\nLog written to: {log_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Organize No-Intro ROM sets into subfolders by category and language."
    )
    parser.add_argument("folder", help="Path to the system ROM folder to organize")
    parser.add_argument("--dry-run", action="store_true", help="Preview actions without moving anything")
    parser.add_argument("--log", metavar="FILE", help="Write action log to this file")

    args = parser.parse_args()

    system_folder = Path(args.folder)
    log_path = Path(args.log) if args.log else None

    organize(system_folder, dry_run=args.dry_run, log_path=log_path)


if __name__ == "__main__":
    main()
