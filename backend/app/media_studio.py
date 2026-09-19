from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx
import imageio_ffmpeg
from fastapi import HTTPException, UploadFile
from PIL import Image, ImageDraw, ImageFont

WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
ARCHIVE_SEARCH = "https://archive.org/advancedsearch.php"
MAX_RENDER_UPLOAD = int(os.environ.get("WATCHDOG_MEDIA_MAX_BYTES", str(150 * 1024 * 1024)))


def _clean_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


def _meta_value(extmetadata: dict[str, Any], key: str) -> str:
    raw = extmetadata.get(key) or {}
    if isinstance(raw, dict):
        return _clean_html(str(raw.get("value") or ""))
    return _clean_html(str(raw or ""))


def _matches_kind(mime: str, kind: str) -> bool:
    mime = (mime or "").lower()
    if kind == "video":
        return mime.startswith("video/")
    if kind == "audio":
        return mime.startswith("audio/")
    return mime.startswith("image/")


async def search_open_media(query: str, kind: str = "video", limit: int = 12) -> dict[str, Any]:
    kind = kind.lower().strip()
    if kind not in {"video", "audio", "image"}:
        raise HTTPException(status_code=400, detail="kind must be video, audio, or image")
    query = query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Enter a search query")

    results: list[dict[str, Any]] = []
    timeout = httpx.Timeout(15.0, connect=8.0)
    headers = {"User-Agent": "WatchDog-MediaStudio/1.0 (+https://github.com/Steinhauer761/gpt6WatchDog)"}

    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
        commons_params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": "6",
            "gsrlimit": str(min(max(limit * 3, 12), 40)),
            "prop": "imageinfo",
            "iiprop": "url|mime|extmetadata",
            "format": "json",
            "formatversion": "2",
        }
        try:
            response = await client.get(WIKIMEDIA_API, params=commons_params)
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", [])
            for page in pages:
                info_list = page.get("imageinfo") or []
                if not info_list:
                    continue
                info = info_list[0]
                mime = str(info.get("mime") or "")
                if not _matches_kind(mime, kind):
                    continue
                metadata = info.get("extmetadata") or {}
                results.append(
                    {
                        "id": f"commons:{page.get('pageid')}",
                        "source": "Wikimedia Commons",
                        "title": str(page.get("title") or "").removeprefix("File:"),
                        "kind": kind,
                        "mime": mime,
                        "direct_url": info.get("url"),
                        "thumbnail_url": info.get("thumburl") or info.get("url"),
                        "source_url": info.get("descriptionurl") or f"https://commons.wikimedia.org/?curid={page.get('pageid')}",
                        "creator": _meta_value(metadata, "Artist"),
                        "license": _meta_value(metadata, "LicenseShortName") or _meta_value(metadata, "UsageTerms"),
                        "license_url": _meta_value(metadata, "LicenseUrl"),
                        "credit": _meta_value(metadata, "Credit"),
                    }
                )
                if len(results) >= limit:
                    break
        except (httpx.HTTPError, ValueError):
            pass

        remaining = max(0, limit - len(results))
        if remaining:
            mediatype = {"video": "movies", "audio": "audio", "image": "image"}[kind]
            archive_params = {
                "q": f"({query}) AND mediatype:{mediatype}",
                "fl[]": ["identifier", "title", "creator", "licenseurl", "mediatype", "description"],
                "rows": str(min(remaining, 8)),
                "page": "1",
                "output": "json",
            }
            try:
                response = await client.get(ARCHIVE_SEARCH, params=archive_params)
                response.raise_for_status()
                docs = response.json().get("response", {}).get("docs", [])
                for doc in docs:
                    identifier = str(doc.get("identifier") or "").strip()
                    if not identifier:
                        continue
                    title = doc.get("title")
                    if isinstance(title, list):
                        title = title[0] if title else identifier
                    creator = doc.get("creator")
                    if isinstance(creator, list):
                        creator = ", ".join(str(v) for v in creator[:3])
                    results.append(
                        {
                            "id": f"archive:{identifier}",
                            "source": "Internet Archive",
                            "title": str(title or identifier),
                            "kind": kind,
                            "mime": "",
                            "direct_url": "",
                            "thumbnail_url": f"https://archive.org/services/img/{identifier}",
                            "source_url": f"https://archive.org/details/{identifier}",
                            "creator": str(creator or ""),
                            "license": "Check the item page before reuse",
                            "license_url": str(doc.get("licenseurl") or ""),
                            "credit": "Internet Archive item; verify the item's rights statement before publishing.",
                        }
                    )
            except (httpx.HTTPError, ValueError):
                pass

    return {
        "query": query,
        "kind": kind,
        "count": len(results[:limit]),
        "results": results[:limit],
        "rights_note": "Search results are source leads. Reuse only media whose item-level license or public-domain status permits your intended use; TikTok/CapCut music licenses do not automatically transfer to an independent editor.",
    }


async def _save_upload(upload: UploadFile, destination: Path) -> int:
    size = 0
    with destination.open("wb") as target:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_RENDER_UPLOAD:
                raise HTTPException(status_code=413, detail=f"Media file exceeds the {MAX_RENDER_UPLOAD // (1024 * 1024)} MB render limit")
            target.write(chunk)
    await upload.close()
    return size


def _target_size(aspect: str) -> tuple[int, int]:
    return {
        "9:16": (720, 1280),
        "1:1": (720, 720),
        "16:9": (1280, 720),
    }.get(aspect, (720, 1280))


def _caption_png(text: str, width: int, height: int, output: Path) -> None:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font_size = max(28, width // 18)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    max_width = width - 96
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        box = draw.textbbox((0, 0), candidate, font=font)
        if current and box[2] - box[0] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    lines = lines[:4]
    if not lines:
        image.save(output)
        return

    line_height = int(font_size * 1.3)
    block_h = line_height * len(lines) + 28
    y0 = height - block_h - 70
    draw.rounded_rectangle((32, y0 - 12, width - 32, height - 46), radius=18, fill=(0, 0, 0, 170))
    y = y0
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font, stroke_width=2)
        text_w = box[2] - box[0]
        draw.text(((width - text_w) / 2, y), line, font=font, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 220))
        y += line_height
    image.save(output)


async def render_basic_video(
    video: UploadFile,
    music: UploadFile | None,
    start_seconds: float,
    end_seconds: float,
    aspect: str,
    speed: float,
    caption: str,
    music_volume: float,
) -> tuple[Path, Path]:
    if aspect not in {"9:16", "1:1", "16:9"}:
        raise HTTPException(status_code=400, detail="aspect must be 9:16, 1:1, or 16:9")
    if speed < 0.5 or speed > 2.0:
        raise HTTPException(status_code=400, detail="speed must be between 0.5 and 2.0")
    if start_seconds < 0 or end_seconds < 0:
        raise HTTPException(status_code=400, detail="trim values cannot be negative")
    if end_seconds and end_seconds <= start_seconds:
        raise HTTPException(status_code=400, detail="end_seconds must be greater than start_seconds")
    if music_volume < 0 or music_volume > 2:
        raise HTTPException(status_code=400, detail="music_volume must be between 0 and 2")

    work_dir = Path(tempfile.mkdtemp(prefix="watchdog-media-"))
    video_suffix = Path(video.filename or "video.mp4").suffix or ".mp4"
    video_path = work_dir / f"input{video_suffix}"
    await _save_upload(video, video_path)

    music_path: Path | None = None
    if music is not None and music.filename:
        music_suffix = Path(music.filename).suffix or ".mp3"
        music_path = work_dir / f"music{music_suffix}"
        await _save_upload(music, music_path)

    width, height = _target_size(aspect)
    caption_path: Path | None = None
    caption = caption.strip()[:500]
    if caption:
        caption_path = work_dir / "caption.png"
        _caption_png(caption, width, height, caption_path)

    output = work_dir / "watchdog-edit.mp4"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-y"]
    if start_seconds > 0:
        cmd += ["-ss", f"{start_seconds:.3f}"]
    cmd += ["-i", str(video_path)]

    music_index: int | None = None
    caption_index: int | None = None
    next_index = 1
    if music_path is not None:
        music_index = next_index
        next_index += 1
        cmd += ["-stream_loop", "-1", "-i", str(music_path)]
    if caption_path is not None:
        caption_index = next_index
        cmd += ["-loop", "1", "-i", str(caption_path)]

    if end_seconds > start_seconds:
        duration = (end_seconds - start_seconds) / speed
        cmd += ["-t", f"{duration:.3f}"]

    base_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setpts=PTS/{speed:.4f}"
    )
    if caption_index is not None:
        cmd += [
            "-filter_complex",
            f"[0:v]{base_filter}[base];[base][{caption_index}:v]overlay=0:0:shortest=1[vout]",
            "-map",
            "[vout]",
        ]
    else:
        cmd += ["-vf", base_filter, "-map", "0:v:0"]

    if music_index is not None:
        cmd += ["-map", f"{music_index}:a:0", "-af", f"volume={music_volume:.3f}", "-shortest"]
    else:
        cmd += ["-map", "0:a?", "-af", f"atempo={speed:.4f}"]

    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(output),
    ]

    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=504, detail="Video render exceeded the 15-minute limit") from exc

    if completed.returncode != 0 or not output.exists():
        detail = (completed.stderr or "Video render failed")[-3000:]
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=422, detail=detail)

    return output, work_dir
