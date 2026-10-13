#!/usr/bin/env python3
"""Install Taurus resources into one OMP project without touching global state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import tempfile
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_VERSION = 1
MANIFEST_NAME = "taurus-install.json"
BEGIN = "<!-- taurus:begin - managed by taurus-skill OMP install, edits are overwritten -->"
END = "<!-- taurus:end -->"


class InstallError(Exception):
    """A requested OMP install cannot be completed safely."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_reparse_point(path: Path) -> bool:
    """Return whether a path is a symbolic link or Windows reparse point."""
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & reparse_flag
    )

def require_regular(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise InstallError(f"missing {label}: {path}") from exc
    if is_reparse_point(path):
        raise InstallError(f"refusing symlink or reparse-point {label}: {path}")
    if not stat.S_ISREG(mode):
        raise InstallError(f"expected regular {label}: {path}")


def source_files(
    source: Path, destination: PurePosixPath, suffixes: frozenset[str]
) -> dict[str, Path]:
    """Return intended regular source files, keyed by project-relative target."""
    if not source.is_dir() or is_reparse_point(source):
        raise InstallError(f"missing source directory: {source}")
    result: dict[str, Path] = {}
    for candidate in sorted(source.rglob("*")):
        if is_reparse_point(candidate):
            raise InstallError(f"refusing symlink or reparse point in source: {candidate}")
        if candidate.is_dir() or candidate.suffix not in suffixes:
            continue
        require_regular(candidate, "source file")
        relative = candidate.relative_to(source)
        result[(destination / relative).as_posix()] = candidate
    return result


def desired_files() -> dict[str, Path]:
    """Map the complete native OMP layout to repository source files."""
    layout = (
        (ROOT / "skills" / "taurus", PurePosixPath(".omp/skills/taurus"), frozenset({".md"})),
        (ROOT / "compat" / "omp" / "skills", PurePosixPath(".omp/skills"), frozenset({".md"})),
        (ROOT / "compat" / "omp" / "agents", PurePosixPath(".omp/agents"), frozenset({".md"})),
        (ROOT / "hooks", PurePosixPath(".omp/taurus/hooks"), frozenset({".py"})),
        (ROOT / "agents", PurePosixPath(".omp/taurus/agents"), frozenset({".md"})),
        (ROOT / "commands", PurePosixPath(".omp/taurus/commands"), frozenset({".md"})),
        (ROOT / "rules", PurePosixPath(".omp/taurus/rules"), frozenset({".md"})),
    )
    result: dict[str, Path] = {}
    for source, destination, suffixes in layout:
        for target, original in source_files(source, destination, suffixes).items():
            if target in result:
                raise InstallError(f"duplicate managed destination: {target}")
            result[target] = original

    extension = ROOT / "compat" / "omp" / "taurus.ts"
    require_regular(extension, "OMP extension adapter")
    result[".omp/extensions/taurus.ts"] = extension
    return result


def expected_rules_block() -> str:
    paths = (ROOT / "rules" / "always-on.md", ROOT / "rules" / "omp-delta.md")
    parts = []
    for path in paths:
        require_regular(path, "OMP rule")
        parts.append(path.read_text(encoding="utf-8").strip())
    return f"{BEGIN}\n\n" + "\n\n".join(parts) + f"\n\n{END}\n"


def is_safe_managed_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        return False
    allowed = (
        value.startswith(".omp/skills/"),
        value.startswith(".omp/agents/"),
        value == ".omp/extensions/taurus.ts",
        value.startswith(".omp/taurus/"),
    )
    return any(allowed)


def validate_manifest(document: object) -> dict[str, str]:
    if not isinstance(document, dict) or document.get("version") != MANIFEST_VERSION:
        raise InstallError("refusing invalid Taurus OMP manifest")
    files = document.get("files")
    if not isinstance(files, dict):
        raise InstallError("refusing invalid Taurus OMP manifest files")
    validated: dict[str, str] = {}
    for name, checksum in files.items():
        if not is_safe_managed_path(name) or not isinstance(checksum, str) or len(checksum) != 64:
            raise InstallError("refusing unsafe Taurus OMP manifest path")
        try:
            int(checksum, 16)
        except ValueError as exc:
            raise InstallError("refusing invalid Taurus OMP manifest checksum") from exc
        validated[name] = checksum
    rules_checksum = document.get("rules_sha256")
    if rules_checksum is not None:
        if not isinstance(rules_checksum, str) or len(rules_checksum) != 64:
            raise InstallError("refusing invalid Taurus OMP rules checksum")
        try:
            int(rules_checksum, 16)
        except ValueError as exc:
            raise InstallError("refusing invalid Taurus OMP rules checksum") from exc
    return validated


def manifest_path(project: Path) -> Path:
    return project / ".omp" / MANIFEST_NAME


def read_manifest(project: Path) -> tuple[dict[str, object] | None, dict[str, str]]:
    check_path_chain(project, ".omp")
    path = manifest_path(project)
    if not os.path.lexists(path):
        return None, {}
    require_regular(path, "Taurus OMP manifest")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"refusing unreadable Taurus OMP manifest: {path}") from exc
    return document, validate_manifest(document)


def check_path_chain(project: Path, relative: str) -> Path:
    """Reject any target path that would traverse a symlink or reparse point."""
    path = project
    for part in PurePosixPath(relative).parts:
        path = path / part
        if os.path.lexists(path) and is_reparse_point(path):
            raise InstallError(f"refusing symlink or reparse-point traversal: {path}")
    return path


def check_project(project: Path) -> None:
    if not project.exists() or not project.is_dir():
        raise InstallError(f"project directory must already exist: {project}")
    if is_reparse_point(project):
        raise InstallError(f"refusing symlink or reparse-point project directory: {project}")


def managed_block(text: str, rules_path: Path) -> tuple[int, int, str] | None:
    begins = text.count(BEGIN)
    ends = text.count(END)
    if begins == 0 and ends == 0:
        return None
    if begins != 1 or ends != 1:
        raise InstallError(f"refusing malformed Taurus markers in {rules_path}")
    start = text.index(BEGIN)
    try:
        finish = text.index(END, start) + len(END)
    except ValueError as exc:
        raise InstallError(f"refusing malformed Taurus markers in {rules_path}") from exc
    if finish < start:
        raise InstallError(f"refusing malformed Taurus markers in {rules_path}")
    if finish < len(text) and text[finish] == "\n":
        finish += 1
    return start, finish, text[start:finish]


def read_rules(project: Path) -> tuple[Path, str, tuple[int, int, str] | None]:
    rules_path = check_path_chain(project, ".omp/RULES.md")
    if not os.path.lexists(rules_path):
        return rules_path, "", None
    require_regular(rules_path, "OMP RULES.md")
    text = rules_path.read_text(encoding="utf-8")
    return rules_path, text, managed_block(text, rules_path)


def checksum_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parent_directories(project: Path, targets: Iterable[str]) -> set[Path]:
    directories = {project / ".omp"}
    for name in targets:
        parent = (project / PurePosixPath(name)).parent
        while parent != project:
            directories.add(parent)
            parent = parent.parent
    return directories


def preflight_install(project: Path, desired: dict[str, Path], document: dict[str, object] | None,
                      previous: dict[str, str]) -> tuple[Path, str, tuple[int, int, str] | None]:
    for name in set(desired) | set(previous) | {".omp/" + MANIFEST_NAME}:
        check_path_chain(project, name)
    for directory in parent_directories(project, desired):
        if os.path.lexists(directory) and not directory.is_dir():
            raise InstallError(f"refusing non-directory managed parent: {directory}")

    for name, recorded_checksum in previous.items():
        target = project / PurePosixPath(name)
        if not os.path.lexists(target):
            raise InstallError(f"refusing missing managed asset: {target}")
        require_regular(target, "managed asset")
        if sha256(target) != recorded_checksum:
            raise InstallError(f"refusing modified managed asset: {target}")

    for name in desired:
        target = project / PurePosixPath(name)
        if os.path.lexists(target) and name not in previous:
            raise InstallError(f"refusing to overwrite user asset: {target}")

    rules_path, rules_text, existing_block = read_rules(project)
    if document is not None:
        recorded_rules = document.get("rules_sha256")
        if recorded_rules is None:
            raise InstallError("refusing Taurus OMP manifest without rules checksum")
        if existing_block is None or checksum_text(existing_block[2]) != recorded_rules:
            raise InstallError(f"refusing modified managed rules in {rules_path}")
    elif existing_block is not None:
        raise InstallError(f"refusing to overwrite existing Taurus rules block in {rules_path}")
    return rules_path, rules_text, existing_block


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".taurus-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def write_rules(path: Path, existing: str, old: tuple[int, int, str] | None, block: str) -> None:
    if old is None:
        updated = (existing.rstrip() + "\n\n" if existing.strip() else "") + block
    else:
        updated = existing[:old[0]] + block + existing[old[1]:]
    atomic_write(path, updated.encode("utf-8"))


def remove_rules(path: Path, existing: str, old: tuple[int, int, str] | None) -> None:
    if old is None:
        return
    updated = existing[:old[0]].rstrip()
    tail = existing[old[1]:].lstrip("\n")
    if updated and tail:
        updated += "\n\n"
    updated += tail
    if updated:
        updated += "\n"
    atomic_write(path, updated.encode("utf-8"))


def remove_empty_parents(project: Path, start: Path) -> None:
    current = start
    while current != project:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def install(project: Path, dry_run: bool) -> None:
    desired = desired_files()
    rules_block = expected_rules_block()
    document, previous = read_manifest(project)
    rules_path, rules_text, old_rules = preflight_install(project, desired, document, previous)

    obsolete = sorted(set(previous) - set(desired))
    if dry_run:
        for name in sorted(desired):
            print(f"would copy {name}")
        for name in obsolete:
            print(f"would remove obsolete {name}")
        print("would update managed .omp/RULES.md block")
        print(f"would write .omp/{MANIFEST_NAME}")
        return

    for name, source in sorted(desired.items()):
        atomic_write(project / PurePosixPath(name), source.read_bytes())
    for name in obsolete:
        target = project / PurePosixPath(name)
        target.unlink()
        remove_empty_parents(project, target.parent)
    write_rules(rules_path, rules_text, old_rules, rules_block)
    manifest = {
        "version": MANIFEST_VERSION,
        "files": {name: sha256(source) for name, source in sorted(desired.items())},
        "rules_sha256": checksum_text(rules_block),
    }
    atomic_write(manifest_path(project), (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(f"installed Taurus OMP resources into {project}")


def uninstall(project: Path, dry_run: bool) -> None:
    document, previous = read_manifest(project)
    if document is None:
        print("no Taurus OMP manifest found; nothing to uninstall")
        return

    for name in previous:
        check_path_chain(project, PurePosixPath(name).parent.as_posix())

    rules_path, rules_text, old_rules = read_rules(project)
    rules_modified = old_rules is not None and checksum_text(old_rules[2]) != document.get("rules_sha256")
    unchanged = []
    preserved = []
    for name, recorded_checksum in sorted(previous.items()):
        target = project / PurePosixPath(name)
        if not os.path.lexists(target):
            continue
        if is_reparse_point(target) or not target.is_file() or sha256(target) != recorded_checksum:
            preserved.append(name)
        else:
            unchanged.append((name, target))

    if dry_run:
        for name, _ in unchanged:
            print(f"would remove {name}")
        for name in preserved:
            print(f"would preserve modified {name}")
        if old_rules is not None:
            if rules_modified:
                print("would preserve modified managed .omp/RULES.md block")
            else:
                print("would remove managed .omp/RULES.md block")
        print(f"would remove .omp/{MANIFEST_NAME}")
        return

    for _, target in unchanged:
        target.unlink()
        remove_empty_parents(project, target.parent)
    if old_rules is not None and not rules_modified:
        remove_rules(rules_path, rules_text, old_rules)
    manifest_path(project).unlink()
    remove_empty_parents(project, manifest_path(project).parent)
    if preserved:
        print("preserved modified Taurus OMP assets: " + ", ".join(preserved))
    if rules_modified:
        print("preserved modified managed .omp/RULES.md block")
    print(f"uninstalled Taurus OMP resources from {project}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="existing project directory")
    parser.add_argument("--dry-run", action="store_true", help="show changes without writing")
    parser.add_argument("--uninstall", action="store_true", help="remove unchanged managed resources")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    project = Path(args.project).expanduser()
    try:
        check_project(project)
        project = project.resolve(strict=True)
        check_project(project)
        if args.uninstall:
            uninstall(project, args.dry_run)
        else:
            install(project, args.dry_run)
    except InstallError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
