#!/usr/bin/env python3
"""Simple Windows-friendly desktop app for masking video watermarks.

Only use this app for media you own or have permission to edit.
"""

from __future__ import annotations

import os
import queue
import shlex
import subprocess
import sys
import threading
import tkinter as tk
from argparse import Namespace
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import watermark_tool


class WatermarkDesktopApp(tk.Tk):
    """Small Tkinter UI that wraps the FFmpeg watermark masking commands."""

    def __init__(self) -> None:
        super().__init__()
        self.title("视频去水印工具")
        self.geometry("720x560")
        self.minsize(680, 520)

        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.preview_path = tk.StringVar(value=str(Path.cwd() / "watermark_preview.jpg"))
        self.x = tk.StringVar(value="20")
        self.y = tk.StringVar(value="20")
        self.width_value = tk.StringVar(value="220")
        self.height_value = tk.StringVar(value="80")
        self.mode = tk.StringVar(value="delogo")
        self.timestamp = tk.StringVar(value="00:00:01")
        self.status = tk.StringVar(value="请选择视频，然后先生成预览确认红框区域。")
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None

        self._build_ui()
        self.after(100, self._poll_log_queue)

    def _build_ui(self) -> None:
        padding = {"padx": 10, "pady": 6}

        intro = ttk.Label(
            self,
            text="仅用于你拥有版权或已获授权编辑的视频。先预览红框，再开始处理。",
            foreground="#8a4b00",
        )
        intro.pack(fill="x", **padding)

        file_frame = ttk.LabelFrame(self, text="文件")
        file_frame.pack(fill="x", **padding)
        file_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="输入视频").grid(row=0, column=0, sticky="w", **padding)
        ttk.Entry(file_frame, textvariable=self.input_path).grid(row=0, column=1, sticky="ew", **padding)
        ttk.Button(file_frame, text="选择...", command=self._choose_input).grid(row=0, column=2, **padding)

        ttk.Label(file_frame, text="输出视频").grid(row=1, column=0, sticky="w", **padding)
        ttk.Entry(file_frame, textvariable=self.output_path).grid(row=1, column=1, sticky="ew", **padding)
        ttk.Button(file_frame, text="保存为...", command=self._choose_output).grid(row=1, column=2, **padding)

        region_frame = ttk.LabelFrame(self, text="水印区域（从视频左上角开始计算）")
        region_frame.pack(fill="x", **padding)
        for column in range(8):
            region_frame.columnconfigure(column, weight=1)

        ttk.Label(region_frame, text="X").grid(row=0, column=0, sticky="e", **padding)
        ttk.Entry(region_frame, textvariable=self.x, width=8).grid(row=0, column=1, sticky="w", **padding)
        ttk.Label(region_frame, text="Y").grid(row=0, column=2, sticky="e", **padding)
        ttk.Entry(region_frame, textvariable=self.y, width=8).grid(row=0, column=3, sticky="w", **padding)
        ttk.Label(region_frame, text="宽度").grid(row=0, column=4, sticky="e", **padding)
        ttk.Entry(region_frame, textvariable=self.width_value, width=8).grid(row=0, column=5, sticky="w", **padding)
        ttk.Label(region_frame, text="高度").grid(row=0, column=6, sticky="e", **padding)
        ttk.Entry(region_frame, textvariable=self.height_value, width=8).grid(row=0, column=7, sticky="w", **padding)

        options_frame = ttk.LabelFrame(self, text="选项")
        options_frame.pack(fill="x", **padding)
        options_frame.columnconfigure(1, weight=1)

        ttk.Label(options_frame, text="处理方式").grid(row=0, column=0, sticky="w", **padding)
        ttk.Radiobutton(options_frame, text="智能填补（推荐）", variable=self.mode, value="delogo").grid(
            row=0, column=1, sticky="w", **padding
        )
        ttk.Radiobutton(options_frame, text="模糊遮罩", variable=self.mode, value="blur").grid(
            row=0, column=2, sticky="w", **padding
        )
        ttk.Label(options_frame, text="预览时间").grid(row=1, column=0, sticky="w", **padding)
        ttk.Entry(options_frame, textvariable=self.timestamp, width=14).grid(row=1, column=1, sticky="w", **padding)
        ttk.Label(options_frame, text="例如 00:00:01").grid(row=1, column=2, sticky="w", **padding)

        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", **padding)
        ttk.Button(action_frame, text="1. 生成预览图", command=self.preview).pack(side="left", padx=6)
        ttk.Button(action_frame, text="2. 开始处理视频", command=self.remove_watermark).pack(side="left", padx=6)
        ttk.Button(action_frame, text="清空日志", command=self._clear_log).pack(side="right", padx=6)

        ttk.Label(self, textvariable=self.status).pack(fill="x", **padding)

        log_frame = ttk.LabelFrame(self, text="运行日志")
        log_frame.pack(fill="both", expand=True, **padding)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=12, wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _choose_input(self) -> None:
        filename = filedialog.askopenfilename(
            title="选择视频",
            filetypes=[("Video files", "*.mp4 *.mov *.mkv *.avi *.wmv"), ("All files", "*.*")],
        )
        if not filename:
            return
        self.input_path.set(filename)
        if not self.output_path.get():
            source = Path(filename)
            self.output_path.set(str(source.with_name(f"{source.stem}_no_watermark.mp4")))

    def _choose_output(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="保存处理后视频",
            defaultextension=".mp4",
            filetypes=[("MP4 video", "*.mp4"), ("All files", "*.*")],
        )
        if filename:
            self.output_path.set(filename)

    def _region_values(self) -> tuple[int, int, int, int]:
        try:
            x = int(self.x.get())
            y = int(self.y.get())
            width = int(self.width_value.get())
            height = int(self.height_value.get())
        except ValueError as exc:
            raise ValueError("X、Y、宽度、高度必须是整数。") from exc
        watermark_tool.Region(x, y, width, height).validate()
        return x, y, width, height

    def _common_validation(self, needs_output: bool) -> tuple[Path, Path | None, int, int, int, int]:
        input_text = self.input_path.get().strip()
        if not input_text:
            raise ValueError("请先选择输入视频。")
        input_file = Path(input_text)
        if not input_file.exists():
            raise ValueError(f"输入视频不存在：{input_file}")
        output_file: Path | None = None
        if needs_output:
            output_text = self.output_path.get().strip()
            if not output_text:
                raise ValueError("请先选择输出视频路径。")
            output_file = Path(output_text)
        x, y, width, height = self._region_values()
        return input_file, output_file, x, y, width, height

    def preview(self) -> None:
        if self._worker_is_running():
            return
        try:
            input_file, _, x, y, width, height = self._common_validation(needs_output=False)
            preview_file = Path(self.preview_path.get().strip() or Path.cwd() / "watermark_preview.jpg")
            args = Namespace(
                input=input_file,
                output=preview_file,
                x=x,
                y=y,
                width=width,
                height=height,
                timestamp=self.timestamp.get().strip() or "00:00:01",
                overwrite=True,
                dry_run=False,
            )
            command = watermark_tool.build_preview_command(args)
        except (RuntimeError, ValueError) as exc:
            messagebox.showerror("无法生成预览", str(exc))
            return
        self._run_async(command, f"预览图已保存：{preview_file}", open_file=preview_file)

    def remove_watermark(self) -> None:
        if self._worker_is_running():
            return
        try:
            input_file, output_file, x, y, width, height = self._common_validation(needs_output=True)
            if output_file is None:
                raise ValueError("请先选择输出视频路径。")
            args = Namespace(
                input=input_file,
                output=output_file,
                x=x,
                y=y,
                width=width,
                height=height,
                mode=self.mode.get(),
                video_codec="libx264",
                crf=20,
                preset="medium",
                overwrite=True,
                dry_run=False,
            )
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

    def _run_async(self, command: list[str], success_message: str, open_file: Path | None = None) -> None:
        self.status.set("正在运行 FFmpeg，请稍候...")
        self._log("$ " + shlex.join(command))
        self.worker = threading.Thread(
            target=self._run_process,
            args=(command, success_message, open_file),
            daemon=True,
        )
        self.worker.start()

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
        self._log(f"预览图路径：{path}")

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
