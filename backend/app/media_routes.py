from __future__ import annotations

import shutil
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from .auth import require_session
from .media_studio import render_basic_video, search_open_media

router = APIRouter(prefix="/v1/media", tags=["media-studio"])


@router.get("/search", dependencies=[Depends(require_session)])
async def media_search(
    q: Annotated[str, Query(min_length=1, max_length=240)],
    kind: Annotated[str, Query(pattern="^(video|audio|image)$")] = "video",
    limit: Annotated[int, Query(ge=1, le=20)] = 12,
):
    return await search_open_media(q, kind=kind, limit=limit)


@router.post("/render", dependencies=[Depends(require_session)])
async def media_render(
    video: Annotated[UploadFile, File(...)],
    music: Annotated[UploadFile | None, File()] = None,
    start_seconds: Annotated[float, Form(ge=0, le=86_400)] = 0,
    end_seconds: Annotated[float, Form(ge=0, le=86_400)] = 0,
    aspect: Annotated[str, Form(pattern="^(9:16|1:1|16:9)$")] = "9:16",
    speed: Annotated[float, Form(ge=0.5, le=2.0)] = 1.0,
    caption: Annotated[str, Form(max_length=500)] = "",
    music_volume: Annotated[float, Form(ge=0, le=2)] = 0.8,
):
    output, work_dir = await render_basic_video(
        video=video,
        music=music,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        aspect=aspect,
        speed=speed,
        caption=caption,
        music_volume=music_volume,
    )
    return FileResponse(
        path=str(output),
        filename="watchdog-media-edit.mp4",
        media_type="video/mp4",
        background=BackgroundTask(shutil.rmtree, work_dir, ignore_errors=True),
        headers={"Cache-Control": "no-store"},
    )
