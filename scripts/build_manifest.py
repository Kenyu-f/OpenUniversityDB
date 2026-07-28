#!/usr/bin/env python3
"""
build_manifest.py

Walks the universities/ directory and writes manifest.json at the repo root.
Run this locally after adding/editing files, or wire it into the GitHub
Actions batch workflow so it stays current automatically.

Usage:
    python scripts/build_manifest.py
"""

import json
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIVERSITIES_DIR = os.path.join(REPO_ROOT, "universities")
OUTPUT_PATH = os.path.join(REPO_ROOT, "manifest.json")


def build_node(dir_path):
    """Recursively build a {name, type, children/...} tree for one directory."""
    entries = []
    for name in sorted(os.listdir(dir_path)):
        if name.startswith("."):
            continue
        full_path = os.path.join(dir_path, name)
        if os.path.isdir(full_path):
            entries.append({
                "name": name,
                "type": "dir",
                "children": build_node(full_path),
            })
        elif name.endswith(".md"):
            entries.append({
                "name": name,
                "type": "file",
            })
    # files before dirs, alphabetical within each group
    entries.sort(key=lambda e: (e["type"] == "dir", e["name"]))
    return entries


def main():
    if not os.path.isdir(UNIVERSITIES_DIR):
        print(f"ERROR: {UNIVERSITIES_DIR} not found.")
        return

    manifest = {"universities": []}
    for slug in sorted(os.listdir(UNIVERSITIES_DIR)):
        full_path = os.path.join(UNIVERSITIES_DIR, slug)
        if not os.path.isdir(full_path) or slug.startswith("."):
            continue
        manifest["universities"].append({
            "slug": slug,
            "files": build_node(full_path),
        })

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_PATH} ({len(manifest['universities'])} universities)")


if __name__ == "__main__":
    main()
