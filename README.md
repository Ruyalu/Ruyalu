# Ruyalu Video Watermark Tool

A small command-line tool for removing or masking watermarks from videos you own or have permission to edit.

> Use this only on videos where you have the legal right to remove a watermark, logo, timestamp, or overlay.

## Requirements

- Python 3.10+
- FFmpeg available on your `PATH`

Check FFmpeg with:

```bash
ffmpeg -version
```

## Quick start

Preview a watermark area on a frame before processing the whole video:

```bash
python watermark_tool.py preview input.mp4 preview.jpg --x 20 --y 20 --width 220 --height 80
```

Remove a rectangular watermark region with FFmpeg's `delogo` filter:

```bash
python watermark_tool.py remove input.mp4 output.mp4 --x 20 --y 20 --width 220 --height 80
```

Use blur masking instead of delogo:

```bash
python watermark_tool.py remove input.mp4 output.mp4 --x 20 --y 20 --width 220 --height 80 --mode blur
```

## Choosing coordinates

The rectangle is measured from the top-left of the video:

- `--x`: left edge of the watermark area
- `--y`: top edge of the watermark area
- `--width`: width of the watermark area
- `--height`: height of the watermark area

Tip: include a small margin around the watermark for best results.

## Audio and encoding

The tool preserves audio by default with `-c:a copy`. Video is encoded with H.264 by default.
You can customize the encoder and quality:

```bash
python watermark_tool.py remove input.mp4 output.mp4 --x 20 --y 20 --width 220 --height 80 --video-codec libx265 --crf 24 --preset slow
```
