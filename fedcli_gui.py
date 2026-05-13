#!/usr/bin/env python3
"""
fedcli GUI — Agent 联邦平台桌面客户端
双击即可运行，像聊天一样构建应用。
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import scrolledtext, ttk

from federation_sdk import FederationClient

# ============ 主题和预设 ============

STYLE_NAMES = {
    "modern": "现代 — 圆角卡片、渐变", "minimal": "极简 — 大量留白",
    "glassmorphism": "毛玻璃 — 半透明", "dark": "暗夜 — 深色荧光",
    "brutalist": "粗野主义 — 撞色", "cyberpunk": "赛博朋克 — 霓虹",
    "neumorphism": "新拟态 — 浮雕", "classic": "经典 — 衬线",
    "retro": "复古 — 像素", "organic": "自然 — 圆润",
    "luxury": "奢华 — 金色", "playful": "活泼 — 卡通",
}

THEME_NAMES = ["ocean", "forest", "sunset", "rose", "lavender",
               "midnight", "teal", "amber", "slate"]

OUTPUT_NAMES = ["html", "react", "vue", "flutter", "both"]

# ============ 主窗口 ============


class FedcliGUI:
    def __init__(self):
        self.client = FederationClient()
        self.root = tk.Tk()
        self.root.title("Agent 联邦平台 — 客户端")
        self.root.geometry("800x680")
        self.root.configure(bg="#1a1a2e")

        # 当前选择
        self._style = tk.StringVar(value="modern")
        self._theme = tk.StringVar(value="")
        self._output = tk.StringVar(value="both")
        self._search = tk.BooleanVar(value=False)
        self._sandbox = tk.BooleanVar(value=True)
        self._task_running = False

        self._build_ui()
        self._add_message("Agent", "欢迎使用 Agent 联邦平台！\n直接告诉我想做什么，我会一步步引导你。")

    # ============ UI 构建 ============

    def _build_ui(self):
        # 聊天区
        self.chat_area = scrolledtext.ScrolledText(
            self.root, wrap=tk.WORD, bg="#16213e", fg="#e0e0e0",
            font=("Microsoft YaHei UI", 10), state=tk.DISABLED,
            relief=tk.FLAT, borderwidth=0,
        )
        self.chat_area.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

        # 配置富文本 tag
        self.chat_area.tag_config("user", foreground="#7dd3fc", font=("Microsoft YaHei UI", 10, "bold"))
        self.chat_area.tag_config("agent", foreground="#a5d6a7", font=("Microsoft YaHei UI", 10))
        self.chat_area.tag_config("system", foreground="#888888", font=("Microsoft YaHei UI", 9, "italic"))
        self.chat_area.tag_config("warning", foreground="#ffb74d", font=("Microsoft YaHei UI", 9))

        # 选项面板
        self._build_options()

        # 输入区
        self._build_input()

    def _build_options(self):
        opts_frame = tk.Frame(self.root, bg="#1a1a2e")
        opts_frame.pack(fill=tk.X, padx=8, pady=2)

        # 风格
        tk.Label(opts_frame, text="风格:", bg="#1a1a2e", fg="#aaa",
                 font=("Microsoft YaHei UI", 9)).grid(row=0, column=0, sticky="w", padx=(0, 2))
        style_cb = ttk.Combobox(opts_frame, textvariable=self._style,
                                values=list(STYLE_NAMES.keys()), width=14, state="readonly")
        style_cb.grid(row=0, column=1, padx=2)

        # 主题
        tk.Label(opts_frame, text="主题:", bg="#1a1a2e", fg="#aaa",
                 font=("Microsoft YaHei UI", 9)).grid(row=0, column=2, sticky="w", padx=(8, 2))
        theme_cb = ttk.Combobox(opts_frame, textvariable=self._theme,
                                values=[""] + THEME_NAMES, width=10, state="readonly")
        theme_cb.grid(row=0, column=3, padx=2)

        # 输出
        tk.Label(opts_frame, text="输出:", bg="#1a1a2e", fg="#aaa",
                 font=("Microsoft YaHei UI", 9)).grid(row=0, column=4, sticky="w", padx=(8, 2))
        out_cb = ttk.Combobox(opts_frame, textvariable=self._output,
                              values=OUTPUT_NAMES, width=8, state="readonly")
        out_cb.grid(row=0, column=5, padx=2)

        # 复选框
        tk.Checkbutton(opts_frame, text="搜索", variable=self._search,
                       bg="#1a1a2e", fg="#aaa", selectcolor="#16213e",
                       font=("Microsoft YaHei UI", 9)).grid(row=0, column=6, padx=(12, 2))
        tk.Checkbutton(opts_frame, text="沙盒", variable=self._sandbox,
                       bg="#1a1a2e", fg="#aaa", selectcolor="#16213e",
                       font=("Microsoft YaHei UI", 9)).grid(row=0, column=7, padx=2)

    def _build_input(self):
        input_frame = tk.Frame(self.root, bg="#1a1a2e")
        input_frame.pack(fill=tk.X, padx=8, pady=(2, 8))

        self.input_entry = tk.Text(input_frame, height=3, bg="#0f3460", fg="#e0e0e0",
                                   font=("Microsoft YaHei UI", 10), relief=tk.FLAT,
                                   borderwidth=1, insertbackground="#7dd3fc", wrap=tk.WORD)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.input_entry.bind("<Control-Return>", lambda e: self._send())

        btn_frame = tk.Frame(input_frame, bg="#1a1a2e")
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 0))

        send_btn = tk.Button(btn_frame, text="发送\n(Ctrl+Enter)", command=self._send,
                             bg="#2563EB", fg="white", font=("Microsoft YaHei UI", 9),
                             relief=tk.FLAT, width=10, height=2, cursor="hand2")
        send_btn.pack(fill=tk.X, pady=(0, 2))

        est_btn = tk.Button(btn_frame, text="仅预估", command=self._estimate_only,
                            bg="#374151", fg="#ddd", font=("Microsoft YaHei UI", 9),
                            relief=tk.FLAT, width=10, cursor="hand2")
        est_btn.pack(fill=tk.X)

        # 底部提示
        tk.Label(input_frame, text="Ctrl+Enter 发送  |  选择上方偏好设置",
                 bg="#1a1a2e", fg="#555", font=("Microsoft YaHei UI", 8)).place(relx=0.01, rely=0.88)

    # ============ 消息处理 ============

    def _add_message(self, sender: str, text: str):
        self.chat_area.configure(state=tk.NORMAL)
        if sender == "user":
            self.chat_area.insert(tk.END, "\nYou: ", "user")
            self.chat_area.insert(tk.END, f"{text}\n", "user")
        elif sender == "system":
            self.chat_area.insert(tk.END, f"{text}\n", "system")
        else:
            self.chat_area.insert(tk.END, f"\nAgent: ", "agent")
            self.chat_area.insert(tk.END, f"{text}\n", "agent")
        self.chat_area.configure(state=tk.DISABLED)
        self.chat_area.see(tk.END)

    def _add_info(self, lines: list[str]):
        self.chat_area.configure(state=tk.NORMAL)
        for line in lines:
            self.chat_area.insert(tk.END, f"  {line}\n", "system")
        self.chat_area.configure(state=tk.DISABLED)
        self.chat_area.see(tk.END)

    # ============ 核心操作 ============

    def _estimate_only(self):
        text = self.input_entry.get("1.0", tk.END).strip()
        if not text:
            return
        self._add_message("user", text[:50] + ("..." if len(text) > 50 else ""))

        try:
            est = self.client.estimate(
                text, style=self._style.get(), output_format=self._output.get(),
                allow_search=self._search.get() if self._search.get() else None,
            )
            lines = [
                f"预估 Token: {est.total_tokens:,}",
                f"预估费用: {est.cost_range[0]} ~ {est.cost_range[1]} 元",
                f"输入/输出: {est.input_tokens:,} / {est.output_tokens:,}",
                f"置信度: {est.confidence}",
            ]
            if est.warnings:
                lines.append(f"提醒: {'; '.join(est.warnings)}")
            self._add_info(lines)
        except Exception as e:
            self._add_info([f"预估失败: {e}"])

    def _send(self):
        if self._task_running:
            self._add_info(["任务正在执行中，请等待..."])
            return

        text = self.input_entry.get("1.0", tk.END).strip()
        if not text:
            return

        self.input_entry.delete("1.0", tk.END)
        self._add_message("user", text)
        self._add_message("agent", "正在分析需求...")

        self._task_running = True
        threading.Thread(target=self._run_task, args=(text,), daemon=True).start()

    def _run_task(self, text: str):
        try:
            est = self.client.estimate(
                text, style=self._style.get(), output_format=self._output.get(),
                allow_search=self._search.get() if self._search.get() else None,
            )
            self.root.after(0, self._add_info, [
                f"风格: {self._style.get()}  主题: {self._theme.get() or '默认'}  输出: {self._output.get()}",
                f"搜索: {'开' if self._search.get() else '关'}  沙盒: {'开' if self._sandbox.get() else '关'}",
                f"预估: {est.total_tokens:,} tokens  |  {est.cost_range[0]} ~ {est.cost_range[1]} 元",
                "执行中...",
            ])

            result = self.client.execute(
                text,
                style=self._style.get(),
                theme=self._theme.get() or None,
                output_format=self._output.get(),
                allow_search=self._search.get() if self._search.get() else None,
                sandbox=self._sandbox.get(),
            )

            if result.status == "completed":
                self.root.after(0, self._add_message, "agent",
                                f"方案已生成！\n任务 ID: {result.thread_id}\n"
                                f"输出目录: preview/")
                if result.output:
                    self.root.after(0, self._add_info,
                                    [f"产出: {list(result.output.keys())}"])
            elif result.status == "waiting_human":
                self.root.after(0, self._add_message, "agent",
                                f"任务需要审批\nID: {result.thread_id}\n"
                                f"请在终端用 fedcli approve {result.thread_id}")
            else:
                self.root.after(0, self._add_info,
                                [f"任务失败: {result.error or result.status}"])
        except Exception as e:
            self.root.after(0, self._add_info, [f"连接失败: {e}\n请确保 Gateway 已启动 (python run.py)"])
        finally:
            self._task_running = False

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    FedcliGUI().run()
