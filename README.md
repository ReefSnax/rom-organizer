# rom_organizer

A Python script for sorting [No-Intro](https://no-intro.org/) ROM sets into subfolders by release type and language. Assumes your collection is already organized by system — this just handles the sub-sorting within each system folder.

---

## Requirements

Python 3.10+. No third-party packages.

---

## Usage

```bash
python rom_organizer.py <system_folder> [--dry-run] [--log <logfile>]
```

| Argument | Description |
|---|---|
| `folder` | Path to the system ROM folder to organize |
| `--dry-run` | Preview what would move, without touching anything |
| `--log FILE` | Write the action log to a file |

**Always dry-run first:**
```bash
python rom_organizer.py "G:/ROMs/Nintendo - Game Boy Advance" --dry-run --log preview.log
```

**Then apply:**
```bash
python rom_organizer.py "G:/ROMs/Nintendo - Game Boy Advance" --log gba_moves.log
```

If you're running from a system directory (e.g. `C:\Windows\System32`), use a full path for `--log` — relative paths resolve from wherever you launched the script.

---

## Output Structure

```
Nintendo - Game Boy Advance/
├── _BIOS/
├── English/
├── Japanese/
├── Other Localizations/
│   ├── Chinese/
│   ├── French/
│   ├── German/
│   ├── Italian/
│   ├── Korean/
│   ├── Russian/
│   ├── Spanish/
│   └── ...
├── Rom Hacks/
└── _Other/
    ├── Beta/
    ├── Demo/
    ├── Kiosk/
    ├── Proto/
    ├── Translation/
    ├── Unlicensed/
    └── Unknown/
```

English and Japanese get top-level folders since they're the most common browsing targets. Everything else goes under `Other Localizations/`. Non-retail releases (betas, demos, etc.) land in `_Other/`, with ROM hacks promoted to the top level since those are worth browsing separately.

`Unknown/` catches anything the script couldn't classify — worth a manual look after your first run.

---

## How Classification Works

Files are evaluated in this order — first match wins:

1. **BIOS** — filename starts with `[BIOS]` → `_BIOS/`
2. **Special tag** — matched against No-Intro tags → `_Other/<tag>/` or top-level if promoted
3. **Language/region** — everything else, sorted by language

### Special Tags

| Tag | No-Intro Pattern | Destination |
|---|---|---|
| BIOS | `[BIOS]` prefix | `_BIOS/` |
| Demo | `(Demo...)` | `_Other/Demo/` |
| Beta | `(Beta...)` | `_Other/Beta/` |
| Proto | `(Proto...)` | `_Other/Proto/` |
| Unlicensed | `(Unl)` | `_Other/Unlicensed/` |
| Hack | `(Hack)` | `Rom Hacks/` |
| Translation | `(T-En)`, `(T-Fr)`, etc. | `_Other/Translation/` |
| Kiosk | `(Kiosk...)` | `_Other/Kiosk/` |

Files matching multiple tags go to the first match in the order above. No duplicates.

### Language Resolution

For retail releases, language is determined in this order:

1. Explicit language tag — `(En)`, `(En,Ja)`, `(De)`, etc.
   - English anywhere in the tag → `English/`
   - Otherwise, first recognized code wins
2. Single region tag — `(USA)` → English, `(Japan)` → Japanese, etc.
3. Multi-region tag — `(USA, Europe)`, `(Japan, USA)` — English wins if any region implies it
4. No match → `_Other/Unknown/`

---

## Customization

### Add a special tag

```python
SPECIAL_TAGS = {
    ...
    "Sample": re.compile(r'\(Sample[^)]*\)', re.IGNORECASE),
}
```

### Promote a tag to a top-level folder

```python
PRIMARY_SPECIAL = {
    "Hack": "Rom Hacks",
    "Translation": "Fan Translations",
}
```

### Add a region

```python
REGION_LANGUAGE_MAP = {
    ...
    "Latin America": "Spanish",
    "Scandinavia":   "Swedish",
}
```

### Change primary languages

```python
PRIMARY_LANGUAGES = {"English", "Japanese", "Korean"}
```

---

## Notes

Files are **moved**, not copied — the log file is your only undo trail, so keep it. If a filename collision occurs (e.g. from a partial previous run), the incoming file gets a `_dup` suffix instead of overwriting.

Built for No-Intro naming. Redump, TOSEC, and GoodTools sets use different conventions and will likely need adjustments.

---

## License

MIT
