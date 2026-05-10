import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

import watermark_tool


def test_build_delogo_filter():
    region = watermark_tool.Region(x=10, y=20, width=120, height=60)
    assert watermark_tool.build_filter(region, "delogo") == "delogo=x=10:y=20:w=120:h=60:show=0"


def test_build_blur_filter():
    region = watermark_tool.Region(x=10, y=20, width=120, height=60)
    assert watermark_tool.build_filter(region, "blur") == (
        "[0:v]split[base][crop];"
        "[crop]crop=120:60:10:20,boxblur=12:1[blurred];"
        "[base][blurred]overlay=10:20"
    )


def test_region_rejects_invalid_values():
    with pytest.raises(ValueError):
        watermark_tool.Region(x=-1, y=0, width=10, height=10).validate()
    with pytest.raises(ValueError):
        watermark_tool.Region(x=0, y=0, width=0, height=10).validate()


@patch("watermark_tool.resolve_ffmpeg", return_value="ffmpeg")
def test_build_remove_command(mock_ffmpeg):
    args = argparse.Namespace(
        input=Path("input.mp4"),
        output=Path("output.mp4"),
        x=1,
        y=2,
        width=3,
        height=4,
        mode="delogo",
        video_codec="libx264",
        crf=20,
        preset="medium",
        overwrite=True,
        dry_run=False,
    )

    assert watermark_tool.build_remove_command(args) == [
        "ffmpeg",
        "-y",
        "-i",
        "input.mp4",
        "-vf",
        "delogo=x=1:y=2:w=3:h=4:show=0",
        "-c:v",
        "libx264",
        "-crf",
        "20",
        "-preset",
        "medium",
        "-c:a",
        "copy",
        "output.mp4",
    ]
