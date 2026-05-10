# Ruyalu Video Watermark Tool

一个面向小白用户的视频水印处理工具。新版图形界面参考常见去水印软件的三步流程：导入视频、在画面上拖拽框选水印、一键导出。它提供两种用法：

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

1. 点击“选择视频”导入视频。
2. 点击“载入/刷新画面”，或等待导入后自动载入预览帧。
3. 直接用鼠标在画面上拖拽框住水印；也可以用“左上角水印 / 右上角水印”等快捷按钮。
4. 点击“预览水印位置”确认红框覆盖水印。
5. 点击“开始去水印”导出新视频。

### 方式 B：打包成 Windows x86 EXE

在 Windows 上安装 **32 位 Python** 后，双击或在命令提示符中运行：

```bat
build_windows_x86.bat
```

打包完成后，应用会生成在：

```text
dist\RuyaluWatermarkTool.exe
```

如果你希望 EXE 在没有安装 FFmpeg 的电脑上也能运行，请把 `ffmpeg.exe` 和 `ffprobe.exe` 放到 `dist` 文件夹中，和 `RuyaluWatermarkTool.exe` 放在一起。

> 注意：要生成 x86 程序，必须使用 32 位 Python 运行打包脚本；64 位 Python 会生成 x64 程序。

## Requirements

- Python 3.10+
- FFmpeg/FFprobe available on your `PATH`，或将 `ffmpeg.exe` 和 `ffprobe.exe` 放在应用/脚本同目录
- 可选但推荐：`opencv-python` 和 `numpy`，用于“无痕修复”模式，减少明显模糊/遮罩

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

Use no-blur OpenCV inpainting mode instead of delogo/blur:

```bash
python watermark_tool.py remove input.mp4 output.mp4 --x 20 --y 20 --width 220 --height 80 --mode inpaint
```

## Reducing blur/overlay artifacts

Traditional `blur` and `delogo` modes can leave a visible soft rectangle, especially in a bottom-right corner watermark like the example screenshot. The recommended `inpaint` mode now expands the selected repair box slightly, reconstructs the selected area frame-by-frame with OpenCV Telea inpainting, and feather-blends the repaired pixels back into the original frame so the rectangle edge is less obvious. It then muxes the original audio back into the output. It is slower, but usually looks more natural on simple backgrounds.

Install the optional dependency when using the Python version:

```bash
python -m pip install opencv-python numpy
```

For best results, select the smallest rectangle that fully covers the watermark or the remaining blur block, and include a tiny margin around the visible edge. If the right-bottom area still has a shadow, run `inpaint` once more on just that remaining shadow. Large boxes over complex moving backgrounds can still show artifacts; true commercial “AI” tools use temporal video inpainting models, which are heavier than this local lightweight app.

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
