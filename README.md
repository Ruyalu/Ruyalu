# Ruyalu Video Watermark Tool

一个简单的视频水印处理工具。它提供两种用法：

1. **Windows 图形界面应用**：适合直接双击使用。
2. **命令行工具**：适合批处理或高级用户。

> 请仅用于你拥有版权或已获得授权编辑的视频。

## Windows x86 直接使用方式

### 方式 A：在 Windows 上直接运行图形界面

如果电脑已安装 Python 3.10+ 和 FFmpeg：

```bat
start_windows_app.bat
```

打开窗口后：

1. 点击“选择...”选择输入视频。
2. 填写水印区域的 `X`、`Y`、`宽度`、`高度`。
3. 点击“生成预览图”，确认红框覆盖水印。
4. 点击“开始处理视频”。

### 方式 B：打包成 Windows x86 EXE

在 Windows 上安装 **32 位 Python** 后，双击或在命令提示符中运行：

```bat
build_windows_x86.bat
```

打包完成后，应用会生成在：

```text
dist\RuyaluWatermarkTool.exe
```

如果你希望 EXE 在没有安装 FFmpeg 的电脑上也能运行，请把 `ffmpeg.exe` 放到 `dist` 文件夹中，和 `RuyaluWatermarkTool.exe` 放在一起。

> 注意：要生成 x86 程序，必须使用 32 位 Python 运行打包脚本；64 位 Python 会生成 x64 程序。

## Requirements

- Python 3.10+
- FFmpeg available on your `PATH`，或将 `ffmpeg.exe` 放在应用/脚本同目录

Check FFmpeg with:

```bash
ffmpeg -version
```

## Command-line quick start

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
