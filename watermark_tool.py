#!/usr/bin/env python3
"""CLI helpers for masking watermarks in videos with FFmpeg.

Only use this script for media you own or have permission to edit.
"""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


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
    """Return the ffmpeg executable path, allowing dry runs without FFmpeg installed."""

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is not None:
        return ffmpeg
    if dry_run:
        return "ffmpeg"
    raise RuntimeError("FFmpeg was not found on PATH. Install FFmpeg before using this tool.")


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
    remove.add_argument("--mode", choices=("delogo", "blur"), default="delogo", help="Masking mode.")
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
            return run_command(build_remove_command(args), args.dry_run)
        if args.command == "preview":
            return run_command(build_preview_command(args), args.dry_run)
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    return 1


if __name__ == "__main__":
    sys.exit(main())
