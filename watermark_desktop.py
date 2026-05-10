#!/usr/bin/env python3
"""Beginner-friendly desktop app for masking video watermarks.

Only use this app for media you own or have permission to edit.
"""

from __future__ import annotations

import os
import queue
import shlex
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from argparse import Namespace
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import watermark_tool

CANVAS_WIDTH = 760
CANVAS_HEIGHT = 430
DISPLAY_FRAME = "watermark_frame.png"


class WatermarkDesktopApp(tk.Tk):
    """A wizard-style Tkinter UI that wraps FFmpeg watermark masking."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Ruyalu 视频去水印助手")
        self.geometry("1120x720")
        self.minsize(980, 660)

        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.x = tk.IntVar(value=0)
        self.y = tk.IntVar(value=0)
        self.width_value = tk.IntVar(value=0)
        self.height_value = tk.IntVar(value=0)
        self.mode = tk.StringVar(value="inpaint")
        self.timestamp = tk.StringVar(value="00:00:01")
        self.status = tk.StringVar(value="第 1 步：选择视频。第 2 步：在画面上拖拽框选水印。第 3 步：开始处理。")

        self.temp_dir = tempfile.TemporaryDirectory(prefix="ruyalu_watermark_")
        self.frame_path = Path(self.temp_dir.name) / DISPLAY_FRAME
        self.frame_image: tk.PhotoImage | None = None
        self.video_size: tuple[int, int] | None = None
        self.display_size: tuple[int, int] | None = None
        self.image_origin = (0, 0)
        self.drag_start: tuple[int, int] | None = None
        self.selection_rect: int | None = None
        self.worker: threading.Thread | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()

        self._build_ui()
        self._draw_empty_canvas()
        self.after(100, self._poll_log_queue)

    def destroy(self) -> None:
        self.temp_dir.cleanup()
        super().destroy()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=0)
        root.rowconfigure(1, weight=1)

        header = ttk.Label(
            root,
            text="像常见去水印软件一样操作：导入视频 → 鼠标框选水印 → 预览位置 → 一键导出",
            font=("Microsoft YaHei UI", 12, "bold"),
        )
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        preview_frame = ttk.LabelFrame(root, text="视频画面：按住鼠标左键拖拽框选水印")
        preview_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(preview_frame, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="#202124", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.canvas.bind("<ButtonPress-1>", self._start_selection)
        self.canvas.bind("<B1-Motion>", self._drag_selection)
        self.canvas.bind("<ButtonRelease-1>", self._finish_selection)

        side = ttk.Frame(root)
        side.grid(row=1, column=1, sticky="ns")
        side.columnconfigure(0, weight=1)

        self._build_step_one(side)
        self._build_step_two(side)
        self._build_step_three(side)
        self._build_log(side)

        ttk.Label(root, textvariable=self.status, foreground="#0b57d0").grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )

    def _build_step_one(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="1. 导入视频")
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        frame.columnconfigure(0, weight=1)

        ttk.Entry(frame, textvariable=self.input_path, width=38).grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        ttk.Button(frame, text="选择视频", command=self._choose_input).grid(row=0, column=1, padx=8, pady=6)

        ttk.Label(frame, text="预览时间点").grid(row=1, column=0, sticky="w", padx=8)
        ttk.Entry(frame, textvariable=self.timestamp, width=12).grid(row=1, column=1, sticky="w", padx=8, pady=6)
        ttk.Button(frame, text="载入/刷新画面", command=self.load_frame).grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=8)

    def _build_step_two(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="2. 框选水印")
        frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        for column in range(4):
            frame.columnconfigure(column, weight=1)

        labels = [("X", self.x), ("Y", self.y), ("宽", self.width_value), ("高", self.height_value)]
        for index, (label, variable) in enumerate(labels):
            ttk.Label(frame, text=label).grid(row=0, column=index, padx=4, pady=(8, 2))
            spin = ttk.Spinbox(frame, from_=0, to=99999, textvariable=variable, width=7, command=self._draw_selection_from_values)
            spin.grid(row=1, column=index, padx=4, pady=(0, 8))
            spin.bind("<KeyRelease>", lambda _event: self._draw_selection_from_values())

        ttk.Button(frame, text="左上角水印", command=lambda: self._apply_corner_preset("top-left")).grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=3
        )
        ttk.Button(frame, text="右上角水印", command=lambda: self._apply_corner_preset("top-right")).grid(
            row=2, column=2, columnspan=2, sticky="ew", padx=6, pady=3
        )
        ttk.Button(frame, text="左下角水印", command=lambda: self._apply_corner_preset("bottom-left")).grid(
            row=3, column=0, columnspan=2, sticky="ew", padx=6, pady=3
        )
        ttk.Button(frame, text="右下角水印", command=lambda: self._apply_corner_preset("bottom-right")).grid(
            row=3, column=2, columnspan=2, sticky="ew", padx=6, pady=3
        )
        ttk.Button(frame, text="清除选择", command=self._clear_selection).grid(row=4, column=0, columnspan=4, sticky="ew", padx=6, pady=8)

    def _build_step_three(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="3. 一键导出")
        frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="输出视频").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))
        ttk.Entry(frame, textvariable=self.output_path, width=38).grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        ttk.Button(frame, text="保存为...", command=self._choose_output).grid(row=1, column=1, padx=8, pady=4)

        ttk.Radiobutton(frame, text="无痕修复（推荐，减少明显模糊/遮罩）", variable=self.mode, value="inpaint").grid(
            row=2, column=0, columnspan=2, sticky="w", padx=8, pady=3
        )
        ttk.Radiobutton(frame, text="快速填补（兼容性好）", variable=self.mode, value="delogo").grid(
            row=3, column=0, columnspan=2, sticky="w", padx=8, pady=3
        )
        ttk.Radiobutton(frame, text="模糊遮罩（最后备选，会有明显遮罩）", variable=self.mode, value="blur").grid(
            row=4, column=0, columnspan=2, sticky="w", padx=8, pady=3
        )
        ttk.Button(frame, text="预览水印位置", command=self.preview_selection).grid(
            row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4)
        )
        ttk.Button(frame, text="开始去水印", command=self.remove_watermark).grid(
            row=6, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 10)
        )

    def _build_log(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="提示与日志")
        frame.grid(row=3, column=0, sticky="nsew")
        parent.rowconfigure(3, weight=1)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(frame, width=42, height=10, wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        scrollbar = ttk.Scrollbar(frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", pady=8)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        ttk.Button(frame, text="清空日志", command=self._clear_log).grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))

    def _draw_empty_canvas(self) -> None:
        self.canvas.delete("all")
        self.canvas.create_text(
            CANVAS_WIDTH // 2,
            CANVAS_HEIGHT // 2 - 20,
            fill="#ffffff",
            font=("Microsoft YaHei UI", 15, "bold"),
            text="请选择视频并点击“载入/刷新画面”",
        )
        self.canvas.create_text(
            CANVAS_WIDTH // 2,
            CANVAS_HEIGHT // 2 + 20,
            fill="#c7c7c7",
            font=("Microsoft YaHei UI", 11),
            text="载入后直接用鼠标框住水印，不需要手动计算坐标。",
        )

    def _choose_input(self) -> None:
        filename = filedialog.askopenfilename(
            title="选择视频",
            filetypes=[("Video files", "*.mp4 *.mov *.mkv *.avi *.wmv *.flv *.webm"), ("All files", "*.*")],
        )
        if not filename:
            return
        self.input_path.set(filename)
        source = Path(filename)
        self.output_path.set(str(source.with_name(f"{source.stem}_去水印.mp4")))
        self.status.set("已选择视频。现在点击“载入/刷新画面”，然后用鼠标框选水印。")
        self.load_frame()

    def _choose_output(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="保存处理后视频",
            defaultextension=".mp4",
            filetypes=[("MP4 video", "*.mp4"), ("All files", "*.*")],
        )
        if filename:
            self.output_path.set(filename)

    def load_frame(self) -> None:
        if self._worker_is_running():
            return
        input_file = self._input_file_or_alert()
        if input_file is None:
            return
        try:
            self.video_size = watermark_tool.get_video_dimensions(input_file)
            command = self._build_frame_command(input_file)
            self._log("$ " + shlex.join(command))
            completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or "无法读取视频画面。")
            self._show_loaded_frame()
            self.status.set("画面已载入。请直接在画面上拖拽框选水印。")
        except (RuntimeError, ValueError) as exc:
            messagebox.showerror("无法载入画面", str(exc))

    def _build_frame_command(self, input_file: Path) -> list[str]:
        ffmpeg = watermark_tool.resolve_ffmpeg()
        return [
            ffmpeg,
            "-y",
            "-ss",
            self.timestamp.get().strip() or "00:00:01",
            "-i",
            str(input_file),
            "-frames:v",
            "1",
            "-vf",
            f"scale={CANVAS_WIDTH}:{CANVAS_HEIGHT}:force_original_aspect_ratio=decrease",
            str(self.frame_path),
        ]

    def _show_loaded_frame(self) -> None:
        self.canvas.delete("all")
        self.frame_image = tk.PhotoImage(file=str(self.frame_path))
        display_width = self.frame_image.width()
        display_height = self.frame_image.height()
        self.display_size = (display_width, display_height)
        origin_x = (CANVAS_WIDTH - display_width) // 2
        origin_y = (CANVAS_HEIGHT - display_height) // 2
        self.image_origin = (origin_x, origin_y)
        self.canvas.create_image(origin_x, origin_y, image=self.frame_image, anchor="nw", tags="frame")
        self.canvas.create_rectangle(origin_x, origin_y, origin_x + display_width, origin_y + display_height, outline="#5f6368")
        self._draw_selection_from_values()

    def _input_file_or_alert(self) -> Path | None:
        input_text = self.input_path.get().strip()
        if not input_text:
            messagebox.showerror("缺少视频", "请先选择输入视频。")
            return None
        input_file = Path(input_text)
        if not input_file.exists():
            messagebox.showerror("视频不存在", f"输入视频不存在：{input_file}")
            return None
        return input_file

    def _start_selection(self, event: tk.Event) -> None:
        if self.display_size is None:
            return
        point = self._clamp_canvas_point(event.x, event.y)
        if point is None:
            return
        self.drag_start = point
        self._replace_selection_rect(point[0], point[1], point[0], point[1])

    def _drag_selection(self, event: tk.Event) -> None:
        if self.drag_start is None:
            return
        point = self._clamp_canvas_point(event.x, event.y)
        if point is None:
            return
        self._replace_selection_rect(self.drag_start[0], self.drag_start[1], point[0], point[1])
        self._update_values_from_canvas_rect(self.drag_start, point)

    def _finish_selection(self, event: tk.Event) -> None:
        if self.drag_start is None:
            return
        point = self._clamp_canvas_point(event.x, event.y)
        if point is not None:
            self._update_values_from_canvas_rect(self.drag_start, point)
            self._draw_selection_from_values()
        self.drag_start = None
        self.status.set("已框选水印。可点击“预览水印位置”确认，或直接“开始去水印”。")

    def _clamp_canvas_point(self, x: int, y: int) -> tuple[int, int] | None:
        if self.display_size is None:
            return None
        origin_x, origin_y = self.image_origin
        display_width, display_height = self.display_size
        if x < origin_x or y < origin_y or x > origin_x + display_width or y > origin_y + display_height:
            x = min(max(x, origin_x), origin_x + display_width)
            y = min(max(y, origin_y), origin_y + display_height)
        return x, y

    def _replace_selection_rect(self, x1: int, y1: int, x2: int, y2: int) -> None:
        if self.selection_rect is not None:
            self.canvas.delete(self.selection_rect)
        self.selection_rect = self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            outline="#ff3b30",
            width=3,
            dash=(8, 4),
            tags="selection",
        )

    def _update_values_from_canvas_rect(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        if self.video_size is None or self.display_size is None:
            return
        origin_x, origin_y = self.image_origin
        display_width, display_height = self.display_size
        video_width, video_height = self.video_size
        left = min(start[0], end[0]) - origin_x
        top = min(start[1], end[1]) - origin_y
        right = max(start[0], end[0]) - origin_x
        bottom = max(start[1], end[1]) - origin_y
        self.x.set(round(left * video_width / display_width))
        self.y.set(round(top * video_height / display_height))
        self.width_value.set(max(1, round((right - left) * video_width / display_width)))
        self.height_value.set(max(1, round((bottom - top) * video_height / display_height)))

    def _draw_selection_from_values(self) -> None:
        if self.video_size is None or self.display_size is None:
            return
        try:
            region = self._region_values()
        except (tk.TclError, ValueError):
            return
        origin_x, origin_y = self.image_origin
        display_width, display_height = self.display_size
        video_width, video_height = self.video_size
        x1 = origin_x + round(region.x * display_width / video_width)
        y1 = origin_y + round(region.y * display_height / video_height)
        x2 = origin_x + round((region.x + region.width) * display_width / video_width)
        y2 = origin_y + round((region.y + region.height) * display_height / video_height)
        self._replace_selection_rect(x1, y1, x2, y2)

    def _apply_corner_preset(self, corner: str) -> None:
        if self.video_size is None:
            messagebox.showinfo("请先载入画面", "请先选择视频并点击“载入/刷新画面”。")
            return
        video_width, video_height = self.video_size
        box_width = max(80, round(video_width * 0.22))
        box_height = max(50, round(video_height * 0.12))
        margin_x = round(video_width * 0.03)
        margin_y = round(video_height * 0.03)
        x = margin_x if "left" in corner else video_width - box_width - margin_x
        y = margin_y if "top" in corner else video_height - box_height - margin_y
        self.x.set(max(0, x))
        self.y.set(max(0, y))
        self.width_value.set(min(box_width, video_width))
        self.height_value.set(min(box_height, video_height))
        self._draw_selection_from_values()
        self.status.set("已套用常见角标位置，可继续拖拽微调。")

    def _clear_selection(self) -> None:
        self.x.set(0)
        self.y.set(0)
        self.width_value.set(0)
        self.height_value.set(0)
        if self.selection_rect is not None:
            self.canvas.delete(self.selection_rect)
            self.selection_rect = None
        self.status.set("已清除选择，请重新在画面上框选水印。")

    def _region_values(self) -> watermark_tool.Region:
        region = watermark_tool.Region(int(self.x.get()), int(self.y.get()), int(self.width_value.get()), int(self.height_value.get()))
        region.validate()
        return region

    def _validated_job(self, needs_output: bool) -> tuple[Path, Path | None, watermark_tool.Region] | None:
        input_file = self._input_file_or_alert()
        if input_file is None:
            return None
        try:
            region = self._region_values()
        except (tk.TclError, ValueError) as exc:
            messagebox.showerror("水印区域无效", f"请在画面上拖拽框选水印，或填写正确的 X/Y/宽/高。\n{exc}")
            return None
        output_file: Path | None = None
        if needs_output:
            output_text = self.output_path.get().strip()
            if not output_text:
                messagebox.showerror("缺少输出路径", "请先选择输出视频保存位置。")
                return None
            output_file = Path(output_text)
            output_file.parent.mkdir(parents=True, exist_ok=True)
        return input_file, output_file, region

    def preview_selection(self) -> None:
        if self._worker_is_running():
            return
        job = self._validated_job(needs_output=False)
        if job is None:
            return
        input_file, _, region = job
        preview_file = Path(self.temp_dir.name) / "watermark_selection_preview.jpg"
        args = Namespace(
            input=input_file,
            output=preview_file,
            x=region.x,
            y=region.y,
            width=region.width,
            height=region.height,
            timestamp=self.timestamp.get().strip() or "00:00:01",
            overwrite=True,
            dry_run=False,
        )
        try:
            command = watermark_tool.build_preview_command(args)
        except RuntimeError as exc:
            messagebox.showerror("无法预览", str(exc))
            return
        self._run_async(command, f"预览图已生成：{preview_file}", open_file=preview_file)

    def remove_watermark(self) -> None:
        if self._worker_is_running():
            return
        job = self._validated_job(needs_output=True)
        if job is None:
            return
        input_file, output_file, region = job
        if output_file is None:
            return
        if self.mode.get() == "inpaint":
            command = [
                "INPAINT",
                str(input_file),
                str(output_file),
                str(region.x),
                str(region.y),
                str(region.width),
                str(region.height),
            ]
            self._run_async(command, f"处理完成：{output_file}", inpaint_job=(input_file, output_file, region))
            return

        args = Namespace(
            input=input_file,
            output=output_file,
            x=region.x,
            y=region.y,
            width=region.width,
            height=region.height,
            mode=self.mode.get(),
            video_codec="libx264",
            crf=20,
            preset="medium",
            overwrite=True,
            dry_run=False,
        )
        try:
            command = watermark_tool.build_remove_command(args)
        except (RuntimeError, ValueError) as exc:
            messagebox.showerror("无法处理视频", str(exc))
            return
        self._run_async(command, f"处理完成：{output_file}")

    def _worker_is_running(self) -> bool:
        if self.worker is not None and self.worker.is_alive():
            messagebox.showinfo("正在运行", "当前任务尚未完成，请稍后。")
            return True
        return False

    def _run_async(
        self,
        command: list[str],
        success_message: str,
        open_file: Path | None = None,
        inpaint_job: tuple[Path, Path, watermark_tool.Region] | None = None,
    ) -> None:
        self.status.set("正在处理，请稍候。视频越大耗时越久。")
        self._log("$ " + shlex.join(command))
        self.worker = threading.Thread(
            target=self._run_inpaint_process if inpaint_job is not None else self._run_process,
            args=(inpaint_job, success_message, open_file) if inpaint_job is not None else (command, success_message, open_file),
            daemon=True,
        )
        self.worker.start()

    def _run_inpaint_process(
        self,
        inpaint_job: tuple[Path, Path, watermark_tool.Region] | None,
        success_message: str,
        open_file: Path | None,
    ) -> None:
        if inpaint_job is None:
            self.log_queue.put("__ERROR__无痕修复任务参数无效。")
            return
        input_file, output_file, region = inpaint_job
        try:
            return_code = watermark_tool.process_video_inpaint(
                input_file,
                output_file,
                region,
                overwrite=True,
                progress_callback=self.log_queue.put,
            )
        except RuntimeError as exc:
            self.log_queue.put(f"__ERROR__{exc}")
            return
        if return_code == 0:
            self.log_queue.put(f"__SUCCESS__{success_message}")
            if open_file is not None:
                self.log_queue.put(f"__OPEN__{open_file}")
        else:
            self.log_queue.put(f"__ERROR__无痕修复失败，退出码：{return_code}")

    def _run_process(self, command: list[str], success_message: str, open_file: Path | None) -> None:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if process.stdout is not None:
            for line in process.stdout:
                self.log_queue.put(line.rstrip())
        return_code = process.wait()
        if return_code == 0:
            self.log_queue.put(f"__SUCCESS__{success_message}")
            if open_file is not None:
                self.log_queue.put(f"__OPEN__{open_file}")
        else:
            self.log_queue.put(f"__ERROR__FFmpeg 运行失败，退出码：{return_code}")

    def _poll_log_queue(self) -> None:
        while not self.log_queue.empty():
            message = self.log_queue.get()
            if message.startswith("__SUCCESS__"):
                text = message.replace("__SUCCESS__", "", 1)
                self.status.set(text)
                messagebox.showinfo("完成", text)
            elif message.startswith("__ERROR__"):
                text = message.replace("__ERROR__", "", 1)
                self.status.set(text)
                messagebox.showerror("失败", text)
            elif message.startswith("__OPEN__"):
                path = Path(message.replace("__OPEN__", "", 1))
                self._open_file(path)
            else:
                self._log(message)
        self.after(100, self._poll_log_queue)

    def _open_file(self, path: Path) -> None:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
            return
        self._log(f"文件路径：{path}")

    def _log(self, message: str) -> None:
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

    def _clear_log(self) -> None:
        self.log_text.delete("1.0", "end")


def main() -> None:
    app = WatermarkDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
