#!/usr/bin/env python3
"""Scan media folders, write manifest.json, info.json templates, and media-data.js."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
PHOTO_ROOT = ROOT / "assets" / "work" / "Photos"
VIDEO_ROOT = ROOT / "assets" / "work" / "Videos"
DATA_JS_PATH = ROOT / "assets" / "work" / "media-data.js"
INDEX_PATH = ROOT / "assets" / "work" / "media-index.json"

PHOTO_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".heic"}
VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v", ".mkv"}

SKIP_NAMES = {".ds_store", "manifest.json", "thumbs.db", "media-index.json", "media-data.js", "info.json"}


def filename_to_title(name: str) -> str:
    stem = Path(name).stem
    if stem.startswith("web-"):
        stem = stem[4:]
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", stem)
    return spaced.replace("_", " ").replace("-", " ").title()


def resolve_video_file(folder: Path, filename: str) -> str:
    path = Path(filename)
    stem = path.stem

    # Prefer .mp4 with the same name (e.g. exported web copy alongside .mov)
    mp4_same = folder / f"{stem}.mp4"
    if path.suffix.lower() == ".mov" and mp4_same.exists():
        return mp4_same.name

    if path.suffix.lower() in {".mov", ".mkv", ".m4v"}:
        web_name = f"web-{stem}.mp4"
        if (folder / web_name).exists():
            return web_name
    return filename


def should_skip_video_source(folder: Path, filename: str) -> bool:
    """Skip source files when a web-friendly copy is already present."""
    path = Path(filename)
    if path.suffix.lower() not in {".mov", ".mkv", ".m4v"}:
        return False
    stem = path.stem
    return (folder / f"{stem}.mp4").exists() or (folder / f"web-{stem}.mp4").exists()


    default = {"title": default_title, "cover": "", "date": "", "role": "", "description": ""}
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {**default, **data}
    except (json.JSONDecodeError, OSError):
        pass
    return default


def is_media(path: Path, extensions: set[str]) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in extensions
        and path.name.lower() not in SKIP_NAMES
        and not path.name.startswith(".")
    )


def format_category(rel: Path) -> str:
    parts = []
    for part in rel.parts:
        spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", part)
        spaced = spaced.replace("_", " ").replace("-", " ")
        parts.append(spaced.strip().title())
    return " — ".join(parts) if parts else "Uncategorised"


def read_or_create_info(folder: Path, default_title: str) -> dict:
    info_path = folder / "info.json"
    default = {
        "title": default_title,
        "cover": "",
        "date": "",
        "role": "",
        "description": "",
    }
    if info_path.exists():
        try:
            data = json.loads(info_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {**default, **data}
        except (json.JSONDecodeError, OSError):
            pass
    else:
        info_path.write_text(json.dumps(default, indent=2) + "\n", encoding="utf-8")
        print(f"  Created {info_path.relative_to(ROOT)}")
    return default


PHOTO_MERGE_ROOTS = ["GradCeremony26"]


def merge_photo_albums(albums: list[dict], photo_root: Path) -> list[dict]:
    """Roll subfolders under named roots into a single album (e.g. GradCeremony26)."""
    absorbed: set[str] = set()
    merged: list[dict] = []

    for merge_name in PHOTO_MERGE_ROOTS:
        merge_path = photo_root / merge_name
        if not merge_path.exists():
            continue

        parent_web = merge_path.relative_to(ROOT).as_posix() + "/"
        parent_info = read_or_create_info(merge_path, merge_name)
        combined: list[str] = []

        for album in albums:
            folder = album["folder"]
            if not folder.startswith(parent_web) or folder == parent_web:
                continue
            sub_rel = folder[len(parent_web):]
            for item in album["items"]:
                combined.append(f"{sub_rel}{item}")

        if not combined:
            continue

        merged.append({
            "category": parent_info["title"],
            "folder": parent_web,
            "items": combined,
            "info": parent_info,
        })
        for album in albums:
            folder = album["folder"]
            if folder.startswith(parent_web) and folder != parent_web:
                absorbed.add(folder)

    if not absorbed:
        return albums

    kept = [a for a in albums if a["folder"] not in absorbed]
    kept.extend(merged)
    return kept


def read_or_create_video_sidecar(folder: Path, filename: str) -> dict:
    """Per-file metadata for videos sitting directly in Videos/ (one project per file)."""
    stem = Path(filename).stem
    sidecar = folder / f"{stem}.info.json"
    default_title = filename_to_title(filename)
    default = {"title": default_title, "cover": "", "date": "", "role": "", "description": ""}
    if sidecar.exists():
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {**default, **data}
        except (json.JSONDecodeError, OSError):
            pass
    else:
        sidecar.write_text(json.dumps(default, indent=2) + "\n", encoding="utf-8")
        print(f"  Created {sidecar.relative_to(ROOT)}")
    return default


def album_sort_key(album: dict) -> tuple:
    order = album.get("info", {}).get("order")
    if order is None or order == "":
        order = 9999
    return (order, album.get("category", "").lower())


def video_album_sort_key(album: dict) -> tuple:
    return album_sort_key(album)


def scan_videos(root: Path) -> list[dict]:
    """Each subfolder = one project album. Loose files in Videos/ = one project each."""
    if not root.exists():
        return []

    albums = []
    candidates = [root] + sorted(p for p in root.rglob("*") if p.is_dir())

    for folder in candidates:
        raw_files = sorted(
            f.name
            for f in folder.iterdir()
            if is_media(f, VIDEO_EXT) and not should_skip_video_source(folder, f.name)
        )
        if not raw_files:
            continue

        manifest = folder / "manifest.json"
        manifest.write_text(json.dumps(raw_files, indent=2) + "\n", encoding="utf-8")
        web_folder = folder.relative_to(ROOT).as_posix() + "/"

        if folder == root:
            for filename in raw_files:
                play_file = resolve_video_file(folder, filename)
                info = read_or_create_video_sidecar(folder, filename)
                albums.append({
                    "category": info["title"],
                    "folder": web_folder,
                    "items": [play_file],
                    "info": info,
                })
            print(f"  {web_folder}  ({len(raw_files)} loose file(s) → {len(raw_files)} project(s))")
            continue

        rel = folder.relative_to(root)
        category = format_category(rel)
        play_files = [resolve_video_file(folder, f) for f in raw_files]
        info = read_or_create_info(folder, category)
        albums.append({
            "category": info["title"],
            "folder": web_folder,
            "items": play_files,
            "info": info,
        })
        print(f"  {web_folder}  ({len(raw_files)} video(s) in project folder)")

    albums.sort(key=video_album_sort_key)
    return albums


def media_signature() -> tuple:
    sig = []
    for root, extensions in ((PHOTO_ROOT, PHOTO_EXT), (VIDEO_ROOT, VIDEO_EXT)):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if is_media(path, extensions):
                sig.append((str(path.relative_to(ROOT)), path.stat().st_mtime_ns))
    return tuple(sorted(sig))


def scan_folders(root: Path, extensions: set[str], root_label: str) -> list[dict]:
    if not root.exists():
        return []

    albums = []
    candidates = [root] + sorted(p for p in root.rglob("*") if p.is_dir())

    for folder in candidates:
        raw_files = sorted(f.name for f in folder.iterdir() if is_media(f, extensions))
        if not raw_files:
            continue

        manifest = folder / "manifest.json"
        manifest.write_text(json.dumps(raw_files, indent=2) + "\n", encoding="utf-8")

        rel = folder.relative_to(root)
        category = format_category(rel) if rel.parts else root_label
        web_folder = folder.relative_to(ROOT).as_posix() + "/"

        play_files = raw_files
        info = read_or_create_info(folder, category)
        albums.append({
            "category": category,
            "folder": web_folder,
            "items": play_files,
            "info": info,
        })
        print(f"  {web_folder}  ({len(raw_files)} files)")

    return albums


def build(*, quiet: bool = False) -> None:
    if not quiet:
        print("Scanning photos…")
    photos = scan_folders(PHOTO_ROOT, PHOTO_EXT, "Photos")
    photos = merge_photo_albums(photos, PHOTO_ROOT)
    photos.sort(key=album_sort_key)
    if not quiet:
        print("Scanning videos…")
    videos = scan_videos(VIDEO_ROOT)

    payload = {"photos": photos, "videos": videos}
    INDEX_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    js = (
        "// AUTO-GENERATED by update-media.py — do not edit manually\n"
        "// Re-run: python3 update-media.py\n"
        "// Edit descriptions in each folder's info.json file\n"
        "window.MEDIA_DATA = "
        + json.dumps(payload, indent=2)
        + ";\n"
    )
    DATA_JS_PATH.write_text(js, encoding="utf-8")

    photo_count = sum(len(a["items"]) for a in photos)
    video_count = sum(len(a["items"]) for a in videos)
    if not quiet:
        print(f"Wrote {DATA_JS_PATH.relative_to(ROOT)}")
        print(f"Done — {photo_count} photo(s), {video_count} video(s) across {len(photos) + len(videos)} event(s).")


def watch(interval: float = 2.0) -> None:
    print(f"Watching assets/work/Photos and assets/work/Videos every {interval}s…")
    last_sig = None
    while True:
        sig = media_signature()
        if sig != last_sig:
            if last_sig is not None:
                print("\nNew media detected — updating albums…")
            build(quiet=last_sig is not None)
            last_sig = sig
        time.sleep(interval)


if __name__ == "__main__":
    import sys

    if "--watch" in sys.argv:
        build()
        watch()
    else:
        build()
