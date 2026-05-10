#!/usr/bin/env python3
"""CLI helpers for masking watermarks in videos with FFmpeg.

Only use this script for media you own or have permission to edit.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shlex
import shutil
import subprocess
import tempfile
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Region:
    """A rectangular video area measured from the top-left corner."""

    x: int
    y: int
    width: int
    height: int

    def validate(self) -> None:
        if self.x < 0 or self.y < 0:
            raise ValueError("x and y must be zero or greater")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be greater than zero")


def resolve_ffmpeg(dry_run: bool = False) -> str:
    """Return the ffmpeg executable path, allowing dry runs without FFmpeg installed.

    Windows builds can place ``ffmpeg.exe`` next to the generated application, so
    this checks both PATH and the folder containing the running script/exe.
    """

    executable_name = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
    ffmpeg = shutil.which(executable_name) or shutil.which("ffmpeg")
    if ffmpeg is not None:
        return ffmpeg

    app_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    bundled_ffmpeg = app_dir / executable_name
    if bundled_ffmpeg.exists():
        return str(bundled_ffmpeg)

    if dry_run:
        return "ffmpeg"
    raise RuntimeError("FFmpeg was not found. Put ffmpeg.exe next to this app or install FFmpeg on PATH.")


def resolve_ffprobe(dry_run: bool = False) -> str:
    """Return the ffprobe executable path for desktop video metadata lookup."""

    executable_name = "ffprobe.exe" if sys.platform.startswith("win") else "ffprobe"
    ffprobe = shutil.which(executable_name) or shutil.which("ffprobe")
    if ffprobe is not None:
        return ffprobe

    app_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    bundled_ffprobe = app_dir / executable_name
    if bundled_ffprobe.exists():
        return str(bundled_ffprobe)

    if dry_run:
        return "ffprobe"
    raise RuntimeError("FFprobe was not found. Put ffprobe.exe next to this app or install FFmpeg on PATH.")


def get_video_dimensions(input_file: Path) -> tuple[int, int]:
    """Read the first video stream size using ffprobe."""

    command = [
        resolve_ffprobe(),
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "json",
        str(input_file),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "Could not read video dimensions.")
    payload = json.loads(completed.stdout)
    streams = payload.get("streams", [])
    if not streams:
        raise RuntimeError("No video stream was found in the selected file.")
    width = int(streams[0]["width"])
    height = int(streams[0]["height"])
    if width <= 0 or height <= 0:
        raise RuntimeError("Video dimensions are invalid.")
    return width, height


def build_audio_mux_command(video_without_audio: Path, original_input: Path, output: Path, overwrite: bool) -> list[str]:
    """Build an FFmpeg command that copies processed video and original audio."""

    return [
        resolve_ffmpeg(),
        "-y" if overwrite else "-n",
        "-i",
        str(video_without_audio),
        "-i",
        str(original_input),
        "-map",
        "0:v:0",
        "-map",
        "1:a?",
        "-c:v",
        "copy",
        "-c:a",
        "copy",
        "-shortest",
        str(output),
    ]


def process_video_inpaint(
    input_file: Path,
    output_file: Path,
    region: Region,
    overwrite: bool = False,
    progress_callback: Callable[[str], None] | None = None,
) -> int:
    """Use OpenCV inpainting to remove a watermark region without a blur box."""

    region.validate()
    if output_file.exists() and not overwrite:
        raise RuntimeError(f"Output already exists: {output_file}")
    if importlib.util.find_spec("cv2") is None or importlib.util.find_spec("numpy") is None:
        raise RuntimeError(
            "The no-blur inpaint mode requires OpenCV. Install it with: python -m pip install opencv-python numpy"
        )
    import cv2  # type: ignore[import-not-found]
    import numpy as np  # type: ignore[import-not-found]

    def report(message: str) -> None:
        if progress_callback is not None:
            progress_callback(message)
        else:
            print(message)

    capture = cv2.VideoCapture(str(input_file))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open input video: {input_file}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if frame_width <= 0 or frame_height <= 0:
        capture.release()
        raise RuntimeError("Could not read video dimensions for inpaint mode.")

    mask = np.zeros((frame_height, frame_width), dtype=np.uint8)
    x1 = min(max(region.x, 0), frame_width - 1)
    y1 = min(max(region.y, 0), frame_height - 1)
    x2 = min(max(region.x + region.width, 1), frame_width)
    y2 = min(max(region.y + region.height, 1), frame_height)
    padding = max(2, round(min(region.width, region.height) * 0.08))
    cv2.rectangle(mask, (x1, y1), (x2 - 1, y2 - 1), 255, -1)
    kernel = np.ones((padding, padding), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)

    with tempfile.TemporaryDirectory(prefix="ruyalu_inpaint_") as temp_dir:
        temp_video = Path(temp_dir) / "inpaint_video.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(temp_video), fourcc, fps, (frame_width, frame_height))
        if not writer.isOpened():
            capture.release()
            raise RuntimeError("Could not create temporary video for inpaint mode.")

        index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            restored = cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)
            writer.write(restored)
            index += 1
            if index == 1 or index % 30 == 0:
                total = frame_count if frame_count > 0 else "?"
                report(f"Inpainting frame {index}/{total}")

        capture.release()
        writer.release()
        if index == 0:
            raise RuntimeError("No frames were read from the input video.")

        mux_command = build_audio_mux_command(temp_video, input_file, output_file, overwrite=True)
        report("Muxing original audio back into output video...")
        completed = subprocess.run(mux_command, check=False)
        return completed.returncode


def build_filter(region: Region, mode: str) -> str:
    """Build the FFmpeg video filter for the selected masking mode."""

    region.validate()
    if mode == "delogo":
        return (
            f"delogo=x={region.x}:y={region.y}:"
            f"w={region.width}:h={region.height}:show=0"
        )
    if mode == "blur":
        return (
            "[0:v]split[base][crop];"
            f"[crop]crop={region.width}:{region.height}:{region.x}:{region.y},"
            "boxblur=12:1[blurred];"
            f"[base][blurred]overlay={region.x}:{region.y}"
        )
    if mode == "inpaint":
        raise ValueError("Inpaint mode is processed by OpenCV and does not use an FFmpeg video filter.")
    raise ValueError(f"Unsupported mode: {mode}")


def build_remove_command(args: argparse.Namespace) -> list[str]:
    """Create the FFmpeg command used by the remove subcommand."""

    ffmpeg = resolve_ffmpeg(args.dry_run)
    region = Region(args.x, args.y, args.width, args.height)
    video_filter = build_filter(region, args.mode)
    command = [
        ffmpeg,
        "-y" if args.overwrite else "-n",
        "-i",
        str(args.input),
        "-vf",
        video_filter,
        "-c:v",
        args.video_codec,
        "-crf",
        str(args.crf),
        "-preset",
        args.preset,
        "-c:a",
        "copy",
        str(args.output),
    ]
    return command


def build_preview_command(args: argparse.Namespace) -> list[str]:
    """Create the FFmpeg command that exports one annotated preview frame."""

    ffmpeg = resolve_ffmpeg(args.dry_run)
    region = Region(args.x, args.y, args.width, args.height)
    region.validate()
    drawbox = (
        f"drawbox=x={region.x}:y={region.y}:"
        f"w={region.width}:h={region.height}:color=red@0.5:t=4"
    )
    return [
        ffmpeg,
        "-y" if args.overwrite else "-n",
        "-ss",
        str(args.timestamp),
        "-i",
        str(args.input),
        "-frames:v",
        "1",
        "-vf",
        drawbox,
        str(args.output),
    ]


def run_command(command: list[str], dry_run: bool) -> int:
    """Run a command or print it when dry-run mode is enabled."""

    print(shlex.join(command))
    if dry_run:
        return 0
    completed = subprocess.run(command, check=False)
    return completed.returncode


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def add_region_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--x", type=non_negative_int, required=True, help="Left edge of the area.")
    parser.add_argument("--y", type=non_negative_int, required=True, help="Top edge of the area.")
    parser.add_argument("--width", type=positive_int, required=True, help="Area width.")
    parser.add_argument("--height", type=positive_int, required=True, help="Area height.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Remove or mask a rectangular watermark area in a video you are authorized to edit."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the FFmpeg command without running it.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    remove = subparsers.add_parser("remove", help="Process a video and mask the watermark area.")
    remove.add_argument("input", type=Path, help="Input video path.")
    remove.add_argument("output", type=Path, help="Output video path.")
    add_region_arguments(remove)
    remove.add_argument("--mode", choices=("inpaint", "delogo", "blur"), default="inpaint", help="Masking mode.")
    remove.add_argument("--video-codec", default="libx264", help="FFmpeg video codec.")
    remove.add_argument("--crf", type=int, default=20, help="Output quality; lower is higher quality.")
    remove.add_argument("--preset", default="medium", help="Encoder preset.")
    remove.add_argument("--overwrite", action="store_true", help="Overwrite output if it exists.")

    preview = subparsers.add_parser("preview", help="Export a frame with the selected area outlined.")
    preview.add_argument("input", type=Path, help="Input video path.")
    preview.add_argument("output", type=Path, help="Output image path, such as preview.jpg.")
    add_region_arguments(preview)
    preview.add_argument("--timestamp", default="00:00:01", help="Frame timestamp to preview.")
    preview.add_argument("--overwrite", action="store_true", help="Overwrite output if it exists.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "remove":
            if args.mode == "inpaint":
                if args.dry_run:
                    print("OpenCV inpaint mode will process frames, reconstruct the selected area, and mux original audio.")
                    return 0
                return process_video_inpaint(
                    args.input,
                    args.output,
                    Region(args.x, args.y, args.width, args.height),
                    overwrite=args.overwrite,
                )
            return run_command(build_remove_command(args), args.dry_run)
        if args.command == "preview":
            return run_command(build_preview_command(args), args.dry_run)
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    return 1


if __name__ == "__main__":
    sys.exit(main())
