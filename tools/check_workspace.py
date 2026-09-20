"""Offline structural checks; no imports of runtime plugins or provider calls."""

import ast
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    errors = []
    manifest = json.loads((ROOT / "wiki/source-manifest.json").read_text(encoding="utf-8"))
    registered = set()
    register = (ROOT / "wiki/sources.md").read_text(encoding="utf-8")
    for entry in manifest["sources"]:
        name = entry["path"]
        path = ROOT / name
        if name in registered:
            errors.append(f"Duplicate source: {name}")
        registered.add(name)
        if not path.is_file():
            errors.append(f"Missing source: {name}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            errors.append(f"Raw source changed: {name}; preserve originals, add amendments")
        if f"../{name}" not in register:
            errors.append(f"Source absent from register: {name}")
        if entry.get("working_copy") and not (ROOT / entry["working_copy"]).is_file():
            errors.append(f"Missing working copy: {entry['working_copy']}")

    actual = {p.relative_to(ROOT).as_posix() for p in (ROOT / "raw").rglob("*") if p.is_file()}
    for name in sorted(actual - registered):
        errors.append(f"Unregistered raw source: {name}")

    docs = sorted(ROOT.glob("*.md")) + sorted((ROOT / "wiki").rglob("*.md"))
    for path in docs:
        content = path.read_text(encoding="utf-8")
        # Repository convention: simple inline relative links; fenced examples are excluded.
        content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
            target = target.strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            destination = path.parent / unquote(parsed.path)
            if not destination.exists():
                errors.append(f"Broken link in {path.relative_to(ROOT)}: {target}")

    index = (ROOT / "wiki/index.md").read_text(encoding="utf-8")
    for path in (ROOT / "wiki").rglob("*.md"):
        relative = path.relative_to(ROOT / "wiki").as_posix()
        if relative != "index.md" and f"]({relative})" not in index:
            errors.append(f"Wiki page absent from index: {relative}")

    python_files = sorted((ROOT / "raw").rglob("*.py"))
    python_files += sorted((ROOT / "router").rglob("*.py"))
    python_files += sorted((ROOT / "tools").rglob("*.py"))
    for path in python_files:
        try:
            ast.parse(path.read_bytes(), filename=str(path))
        except SyntaxError as exc:
            errors.append(f"Python syntax: {exc}")

    if errors:
        print("\n".join(errors))
        return 1
    print(f"PASS: {len(registered)} raw hashes/registrations, {len(docs)} Markdown files, "
          f"wiki index coverage, {len(python_files)} Python syntax checks. No API calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
