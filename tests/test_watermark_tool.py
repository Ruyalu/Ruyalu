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


@patch("watermark_tool.shutil.which", return_value=None)
def test_resolve_ffmpeg_allows_dry_run_without_install(mock_which):
    assert watermark_tool.resolve_ffmpeg(dry_run=True) == "ffmpeg"


@patch("watermark_tool.shutil.which", return_value=None)
def test_resolve_ffmpeg_requires_install_for_real_runs(mock_which):
    with pytest.raises(RuntimeError):
        watermark_tool.resolve_ffmpeg(dry_run=False)


@patch("watermark_tool.shutil.which", return_value=None)
def test_resolve_ffprobe_allows_dry_run_without_install(mock_which):
    assert watermark_tool.resolve_ffprobe(dry_run=True) == "ffprobe"


@patch("watermark_tool.resolve_ffprobe", return_value="ffprobe")
@patch("watermark_tool.subprocess.run")
def test_get_video_dimensions(mock_run, mock_resolve_ffprobe):
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = '{"streams": [{"width": 1920, "height": 1080}]}'
    mock_run.return_value.stderr = ""

    assert watermark_tool.get_video_dimensions(Path("input.mp4")) == (1920, 1080)


def test_build_filter_rejects_inpaint_filter_mode():
    region = watermark_tool.Region(x=10, y=20, width=120, height=60)
    with pytest.raises(ValueError):
        watermark_tool.build_filter(region, "inpaint")


@patch("watermark_tool.resolve_ffmpeg", return_value="ffmpeg")
def test_build_audio_mux_command(mock_ffmpeg):
    assert watermark_tool.build_audio_mux_command(
        Path("video.mp4"), Path("original.mp4"), Path("output.mp4"), overwrite=True
    ) == [
        "ffmpeg",
        "-y",
        "-i",
        "video.mp4",
        "-i",
        "original.mp4",
        "-map",
        "0:v:0",
        "-map",
        "1:a?",
        "-c:v",
        "copy",
        "-c:a",
        "copy",
        "-shortest",
        "output.mp4",
    ]
