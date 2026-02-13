#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime

# ---------- CONFIG ----------
# pastas/arquivos a ignorar sempre
IGNORE_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".idea", ".vscode", "node_modules", "dist", "build",
    ".DS_Store"
}

IGNORE_FILE_EXTS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".sqlite", ".db", ".parquet", ".pkl", ".pt", ".onnx",
    ".zip", ".tar", ".gz", ".7z"
}

IGNORE_FILES = {
    ".env", ".env.local", ".env.production", "secrets.toml", ".python-version"
}

# inclua somente o que interessa (ajuste conforme seu repo)
INCLUDE_EXTS = {
    ".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".json", ".ini",
    ".dockerfile", ""  # "" permite pegar arquivos sem extensão (ex.: Dockerfile)
}

# se quiser permitir alguns binários/arquivos específicos, adicione aqui
ALLOWLIST_FILES = {
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "pyproject.toml", "poetry.lock", "README.md", "ARCHITECTURE.md",
}

MAX_FILE_BYTES = 200_000     # corta arquivos maiores que ~200KB
MAX_TOTAL_BYTES = 2_500_000  # para não gerar um monstro (ajuste)
# ---------------------------


def is_ignored_path(path: Path) -> bool:
    parts = set(path.parts)
    if any(p in IGNORE_DIRS for p in parts):
        return True
    if path.name in IGNORE_FILES:
        return True
    if path.suffix.lower() in IGNORE_FILE_EXTS:
        return True
    return False


def is_included_file(path: Path) -> bool:
    if path.name in ALLOWLIST_FILES:
        return True
    # arquivos sem extensão como Dockerfile
    if path.suffix == "" and path.name.lower() == "dockerfile":
        return True
    return path.suffix.lower() in INCLUDE_EXTS


def safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # fallback simples
        return path.read_text(encoding="latin-1", errors="replace")


def build_tree(root: Path, max_depth: int = 6) -> str:
    lines = []
    root = root.resolve()

    def walk(dir_path: Path, prefix: str = "", depth: int = 0):
        if depth > max_depth:
            return
        entries = []
        for p in sorted(dir_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            if is_ignored_path(p):
                continue
            entries.append(p)

        for i, p in enumerate(entries):
            last = i == len(entries) - 1
            connector = "└── " if last else "├── "
            lines.append(f"{prefix}{connector}{p.name}")
            if p.is_dir():
                walk(p, prefix + ("    " if last else "│   "), depth + 1)

    lines.append(str(root.name))
    walk(root)
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python repo_flatten.py <repo_root> [output_file]")
        return 2

    repo_root = Path(sys.argv[1]).resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        print(f"Invalid repo root: {repo_root}")
        return 2

    out_path = Path(sys.argv[2]).resolve() if len(sys.argv) >= 3 else repo_root / "REPO_FLATTENED.txt"

    tree_str = build_tree(repo_root)

    total_bytes = 0
    chunks: list[str] = []

    header = [
        "REPO FLATTENED EXPORT",
        f"Generated: {datetime.utcnow().isoformat()}Z",
        f"Root: {repo_root}",
        "",
        "=== DIRECTORY TREE (filtered) ===",
        tree_str,
        "",
        "=== FILE CONTENTS ===",
        "",
    ]
    chunks.append("\n".join(header))

    # coletar arquivos
    files: list[Path] = []
    for p in repo_root.rglob("*"):
        if not p.is_file():
            continue
        if is_ignored_path(p):
            continue
        if not is_included_file(p):
            continue
        files.append(p)

    files = sorted(files, key=lambda p: str(p).lower())

    for p in files:
        try:
            size = p.stat().st_size
        except OSError:
            continue

        if size > MAX_FILE_BYTES:
            # registrar que foi omitido por tamanho
            chunks.append(f"===== FILE: {p.relative_to(repo_root)} =====\n"
                         f"[OMITTED: file too large ({size} bytes) > MAX_FILE_BYTES]\n")
            continue

        if total_bytes + size > MAX_TOTAL_BYTES:
            chunks.append("===== [STOPPED] =====\n"
                         f"Reached MAX_TOTAL_BYTES ({MAX_TOTAL_BYTES}). Remaining files omitted.\n")
            break

        content = safe_read_text(p)
        total_bytes += size

        chunks.append(f"===== FILE: {p.relative_to(repo_root)} =====\n{content}\n")

    out_path.write_text("\n".join(chunks), encoding="utf-8")
    print(f"✅ Wrote: {out_path}")
    print(f"   Total included bytes: {total_bytes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())