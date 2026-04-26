"""Local context inspection utilities."""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Sequence
from pathlib import Path

from .config import DEFAULT_EXCLUDE_PATTERNS, RecursiveContextConfig
from .models import ContextSlice, ContextSource, FileEntry, SearchHit

TEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cfg",
    ".conf",
    ".cpp",
    ".css",
    ".csv",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsonl",
    ".kt",
    ".log",
    ".md",
    ".py",
    ".rs",
    ".scala",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def resolve_context_uri(uri: str) -> Path:
    """Resolve a local file or file:// URI."""

    normalized = uri.removeprefix("file://")
    path = Path(normalized).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Context URI does not exist: {uri}")
    return path


def make_source(uri: str, label: str = "") -> ContextSource:
    path = resolve_context_uri(uri)
    kind = "directory" if path.is_dir() else "file"
    return ContextSource(uri=uri, path=str(path), kind=kind, label=label or path.name)


def is_probably_text(path: Path, max_probe_bytes: int = 4096) -> bool:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    try:
        data = path.read_bytes()[:max_probe_bytes]
    except OSError:
        return False
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _iter_source_paths(source: ContextSource) -> list[Path]:
    root = Path(source.path)
    if source.kind == "file":
        return [root]
    return sorted(path for path in root.rglob("*") if path.is_file())


def _is_excluded(relative_path: str, exclude_patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(relative_path, pattern) for pattern in exclude_patterns)


def relative_path_for(source: ContextSource, path: Path) -> str:
    root = Path(source.path)
    if source.kind == "file":
        return root.name
    return path.relative_to(root).as_posix()


def path_for_relative(source: ContextSource, relative_path: str | None = None) -> Path:
    root = Path(source.path)
    if source.kind == "file":
        if relative_path in {None, "", root.name, "."}:
            return root
        raise FileNotFoundError(f"File source {source.id} has no relative path {relative_path!r}")
    if not relative_path:
        raise ValueError("relative_path is required for directory sources")
    path = (root / relative_path).resolve()
    if root not in path.parents and path != root:
        raise ValueError("relative_path escapes the context source")
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Unknown context file: {relative_path}")
    return path


def list_files(
    sources: list[ContextSource],
    glob: str | None = None,
    limit: int = 100,
    exclude_patterns: Sequence[str] | None = None,
) -> list[FileEntry]:
    active_excludes = DEFAULT_EXCLUDE_PATTERNS if exclude_patterns is None else exclude_patterns
    entries: list[FileEntry] = []
    for source in sources:
        for path in _iter_source_paths(source):
            relative = relative_path_for(source, path)
            if active_excludes and _is_excluded(relative, active_excludes):
                continue
            if glob and not fnmatch.fnmatch(relative, glob):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            entries.append(
                FileEntry(
                    source_id=source.id,
                    relative_path=relative,
                    path=str(path),
                    size_bytes=size,
                    is_text=is_probably_text(path),
                )
            )
            if len(entries) >= limit:
                return entries
    return entries


def read_context_slice(
    source: ContextSource,
    relative_path: str | None,
    start_line: int,
    max_lines: int,
    config: RecursiveContextConfig,
) -> ContextSlice:
    path = path_for_relative(source, relative_path)
    if not is_probably_text(path):
        raise ValueError(f"Context file is not text: {relative_path or path.name}")

    start_line = max(1, start_line)
    max_lines = max(1, max_lines)
    lines: list[str] = []
    current_line = 0
    truncated = False
    chars = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            current_line += 1
            if current_line < start_line:
                continue
            if len(lines) >= max_lines:
                truncated = True
                break
            chars += len(raw_line)
            if chars > config.max_read_chars:
                truncated = True
                break
            lines.append(raw_line.rstrip("\n"))

    end_line = start_line + max(0, len(lines) - 1)
    return ContextSlice(
        source_id=source.id,
        relative_path=relative_path_for(source, path),
        start_line=start_line,
        end_line=end_line,
        text="\n".join(lines),
        truncated=truncated,
    )


def search_context(
    sources: list[ContextSource],
    query: str,
    config: RecursiveContextConfig,
    regex: bool = False,
    glob: str | None = None,
    limit: int = 50,
) -> list[SearchHit]:
    if not query:
        raise ValueError("query is required")

    matcher = re.compile(query) if regex else None
    query_lower = query.lower()
    hits: list[SearchHit] = []

    for entry in list_files(sources, glob=glob, limit=100000, exclude_patterns=config.exclude_patterns):
        if len(hits) >= limit:
            break
        path = Path(entry.path)
        if not entry.is_text or entry.size_bytes > config.max_search_file_bytes:
            continue
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line_number, raw_line in enumerate(handle, start=1):
                    line = raw_line.rstrip("\n")
                    matched = bool(matcher.search(line)) if matcher else query_lower in line.lower()
                    if matched:
                        hits.append(
                            SearchHit(
                                source_id=entry.source_id,
                                relative_path=entry.relative_path,
                                line=line_number,
                                text=line[:1000],
                            )
                        )
                        if len(hits) >= limit:
                            return hits
        except OSError:
            continue

    return hits
