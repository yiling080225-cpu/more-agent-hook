#!/usr/bin/env python3
"""
Agent 联邦平台 — 桌面客户端
对话式交互 + 按需选项卡片 + 项目产出面板
"""

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import font, ttk

from federation_sdk import FederationClient

# ============ 设计令牌 ============

BG_MAIN = "#0f0f0f"
BG_CHAT = "#1a1a1a"
BG_SIDEBAR = "#141414"
BG_INPUT = "#1e1e1e"
BG_USER_BUBBLE = "#2563EB"
BG_AGENT_BUBBLE = "#262626"
BG_CARD = "#1e1e2e"
BG_CARD_HOVER = "#2a2a3e"
FG_PRIMARY = "#e4e4e7"
FG_SECONDARY = "#a1a1aa"
FG_MUTED = "#71717a"
ACCENT = "#3b82f6"
ACCENT_GREEN = "#22c55e"
ACCENT_YELLOW = "#eab308"
BORDER = "#27272a"

STYLES = {
    "modern": "现代 — 圆角卡片、渐变、微阴影",
    "minimal": "极简 — 大量留白、细线条",
    "glassmorphism": "毛玻璃 — 半透明、层次感",
    "dark": "暗夜 — 深色背景、荧光色",
    "brutalist": "粗野主义 — 粗边框、撞色",
    "cyberpunk": "赛博朋克 — 霓虹灯效",
    "neumorphism": "新拟态 — 柔和浮雕",
    "classic": "经典 — 衬线字体",
    "retro": "复古 — 像素字体",
    "organic": "自然 — 圆润形状",
    "luxury": "奢华 — 金色质感",
    "playful": "活泼 — 弹跳动画",
}

THEMES = {
    "ocean": "#2563EB", "forest": "#16A34A", "sunset": "#EA580C",
    "rose": "#E11D48", "lavender": "#7C3AED", "midnight": "#1E293B",
    "teal": "#0D9488", "amber": "#D97706", "slate": "#64748B",
}

OUTPUTS = {"html": "HTML+CSS", "react": "React", "vue": "Vue", "flutter": "Flutter", "both": "全都要"}


# ============ GUI 应用 ============

class FedcliGUI:
    def __init__(self):
        self.client = FederationClient()
        self._style = "modern"
        self._theme = ""
        self._output = "both"
        self._search = False
        self._sandbox = True
        self._phase = "idle"
        self._task_running = False
        self._pending_description = ""

        self.root = tk.Tk()
        self.root.title("Agent 联邦平台")
        self.root.geometry("960x680")
        self.root.minsize(720, 480)
        self.root.configure(bg=BG_MAIN)

        self._build_ui()
        self._add_bubble("agent",
            "欢迎使用 Agent 联邦平台。\n\n"
            "我不同于普通 AI 对话工具——我能帮你把想法变成实际可运行的项目。\n\n"
            "直接告诉我你想做什么，例如：\n"
            "• 做一个电商网站，毛玻璃风格，海洋蓝主题\n"
            "• 帮我审查这段代码的安全性\n"
            "• 分析这张设计图并生成 React 组件\n\n"
            "我会引导你完成整个过程，最终交付可运行的代码。"
        )

    # ============ UI 构建 ============

    def _build_ui(self):
        # 主容器
        main = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=BG_MAIN, sashwidth=1)
        main.pack(fill=tk.BOTH, expand=True)

        # 左侧：聊天区
        left = tk.Frame(main, bg=BG_CHAT)
        main.add(left, width=580)

        # 聊天标题栏
        title_bar = tk.Frame(left, bg=BG_MAIN, height=36)
        title_bar.pack(fill=tk.X)
        title_bar.pack_propagate(False)
        tk.Label(title_bar, text="  Agent 联邦", bg=BG_MAIN, fg=FG_PRIMARY,
                 font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT, padx=12)
        self._status_dot = tk.Label(title_bar, text="●", bg=BG_MAIN, fg=ACCENT_GREEN, font=("Segoe UI", 8))
        self._status_dot.pack(side=tk.LEFT)
        tk.Label(title_bar, text="已连接", bg=BG_MAIN, fg=FG_MUTED,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=4)

        # 聊天消息区
        self.chat_frame = tk.Frame(left, bg=BG_CHAT)
        self.chat_frame.pack(fill=tk.BOTH, expand=True, padx=0)

        self.chat_canvas = tk.Canvas(self.chat_frame, bg=BG_CHAT, highlightthickness=0)
        self.chat_scroll = tk.Scrollbar(self.chat_frame, orient=tk.VERTICAL, command=self.chat_canvas.yview)
        self.chat_inner = tk.Frame(self.chat_canvas, bg=BG_CHAT)

        self.chat_inner.bind("<Configure>", lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all")))
        self.chat_window = self.chat_canvas.create_window((0, 0), window=self.chat_inner, anchor="nw", tags="inner")
        self.chat_canvas.configure(yscrollcommand=self.chat_scroll.set)

        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.chat_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.chat_canvas.bind("<Configure>", self._resize_chat)
        self.chat_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # 输入区
        self._build_input(left)

        # 右侧：项目产出面板
        right = tk.Frame(main, bg=BG_SIDEBAR)
        main.add(right, width=280)
        self._build_sidebar(right)

    def _build_input(self, parent):
        input_frame = tk.Frame(parent, bg=BG_MAIN)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # 分隔线
        tk.Frame(input_frame, bg=BORDER, height=1).pack(fill=tk.X)

        inner = tk.Frame(input_frame, bg=BG_INPUT)
        inner.pack(fill=tk.X, padx=8, pady=8)

        self.input_text = tk.Text(inner, height=3, bg=BG_INPUT, fg=FG_PRIMARY,
                                  font=("Segoe UI", 10), relief=tk.FLAT, borderwidth=0,
                                  insertbackground=ACCENT, wrap=tk.WORD,
                                  padx=8, pady=6)
        self.input_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.input_text.bind("<Control-Return>", lambda e: self._send())
        self.input_text.bind("<Shift-Return>", lambda e: None)  # allow newline

        btn_frame = tk.Frame(inner, bg=BG_INPUT)
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))

        send_btn = tk.Button(btn_frame, text="发送", command=self._send,
                             bg=ACCENT, fg="white", font=("Segoe UI", 9, "bold"),
                             relief=tk.FLAT, padx=14, pady=6, cursor="hand2",
                             activebackground="#1d4ed8", activeforeground="white")
        send_btn.pack(fill=tk.X)

        tk.Label(input_frame, text="Ctrl+Enter 发送  |  Shift+Enter 换行",
                 bg=BG_MAIN, fg=FG_MUTED, font=("Segoe UI", 8)).pack(side=tk.BOTTOM, pady=(0, 4))

    def _build_sidebar(self, parent):
        # 标题
        header = tk.Frame(parent, bg=BG_SIDEBAR, height=36)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="项目产出", bg=BG_SIDEBAR, fg=FG_PRIMARY,
                 font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT, padx=16, pady=8)

        # 文件列表
        tk.Frame(parent, bg=BORDER, height=1).pack(fill=tk.X)

        files_header = tk.Frame(parent, bg=BG_SIDEBAR)
        files_header.pack(fill=tk.X, padx=12, pady=8)
        tk.Label(files_header, text="preview/", bg=BG_SIDEBAR, fg=ACCENT,
                 font=("Cascadia Code", 10)).pack(side=tk.LEFT)
        self._refresh_btn = tk.Label(files_header, text="⟳", bg=BG_SIDEBAR, fg=FG_MUTED,
                                     font=("Segoe UI", 12), cursor="hand2")
        self._refresh_btn.pack(side=tk.RIGHT)
        self._refresh_btn.bind("<Button-1>", lambda e: self._refresh_files())

        self.file_list = tk.Frame(parent, bg=BG_SIDEBAR)
        self.file_list.pack(fill=tk.BOTH, expand=True, padx=8)

        # 初始占位
        self._show_empty_files()

        # 底部预览
        tk.Frame(parent, bg=BORDER, height=1).pack(fill=tk.X)
        self.preview_label = tk.Label(parent, text="点击文件预览内容", bg=BG_SIDEBAR, fg=FG_MUTED,
                                      font=("Segoe UI", 9), anchor="w", justify=tk.LEFT,
                                      wraplength=260)
        self.preview_label.pack(fill=tk.X, padx=12, pady=8)

    def _show_empty_files(self):
        for w in self.file_list.winfo_children():
            w.destroy()
        tk.Label(self.file_list, text="暂无产出\n\n提交需求后，生成的\n项目文件会显示在这里",
                 bg=BG_SIDEBAR, fg=FG_MUTED, font=("Segoe UI", 9),
                 justify=tk.CENTER).pack(expand=True)

    def _refresh_files(self):
        for w in self.file_list.winfo_children():
            w.destroy()
        preview = Path("preview")
        if not preview.exists() or not list(preview.iterdir()):
            self._show_empty_files()
            return
        for f in sorted(preview.iterdir()):
            if f.name == ".gitkeep":
                continue
            fw = tk.Frame(self.file_list, bg=BG_SIDEBAR)
            fw.pack(fill=tk.X, pady=1)

            # 文件图标
            suffix = f.suffix.lower()
            icon_map = {".html": "🌐", ".svg": "🎨", ".scad": "🔧", ".py": "🐍",
                        ".js": "📜", ".tsx": "⚛", ".vue": "💚", ".json": "📋"}
            icon = icon_map.get(suffix, "📄")

            lbl = tk.Label(fw, text=f"  {icon} {f.name}", bg=BG_SIDEBAR, fg=FG_SECONDARY,
                           font=("Cascadia Code", 9), anchor="w", cursor="hand2")
            lbl.pack(fill=tk.X)
            lbl.bind("<Button-1>", lambda e, path=f: self._preview_file(path))
            # 双击 HTML 在浏览器打开
            if suffix == ".html":
                lbl.bind("<Double-Button-1>", lambda e, path=f: self._open_in_browser(path))
                tk.Label(fw, text=" 双击打开浏览器", bg=BG_SIDEBAR, fg=FG_MUTED,
                         font=("Segoe UI", 7)).place(relx=0.95, rely=0.5, anchor="e")

    @staticmethod
    def _open_in_browser(path: Path):
        import webbrowser
        webbrowser.open(f"file://{path.resolve()}")

    def _preview_file(self, path: Path):
        """预览文件：HTML 可打开浏览器，SVG 显示代码，图片显示路径。"""
        suffix = path.suffix.lower()
        try:
            content = path.read_text(encoding="utf-8")
            if suffix == ".html":
                # 显示摘要 + 打开按钮
                preview = content[:600]
                if len(content) > 600:
                    preview += "\n... [点击下方按钮在浏览器中打开完整页面]"
                self.preview_label.configure(
                    text=preview, fg=FG_SECONDARY, justify=tk.LEFT, anchor="w"
                )
            elif suffix == ".svg":
                preview = content[:600]
                self.preview_label.configure(
                    text=preview, fg=FG_SECONDARY, justify=tk.LEFT, anchor="w"
                )
            elif suffix == ".scad":
                preview = content[:600]
                self.preview_label.configure(
                    text=preview, fg=ACCENT, justify=tk.LEFT, anchor="w",
                    font=("Cascadia Code", 9),
                )
            else:
                preview = content[:600]
                self.preview_label.configure(
                    text=preview, fg=FG_SECONDARY, justify=tk.LEFT, anchor="w",
                    font=("Cascadia Code", 9),
                )
        except Exception:
            self.preview_label.configure(
                text=f"[二进制文件，无法预览: {path.name}]", fg=FG_MUTED,
                font=("Segoe UI", 9),
            )

    def _resize_chat(self, event):
        self.chat_canvas.itemconfig(self.chat_window, width=event.width)

    def _on_mousewheel(self, event):
        self.chat_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ============ 消息渲染 ============

    def _add_bubble(self, sender: str, text: str):
        """添加聊天气泡。sender: 'user' 或 'agent'"""
        row = tk.Frame(self.chat_inner, bg=BG_CHAT)
        row.pack(fill=tk.X, padx=12, pady=4)

        if sender == "user":
            # 右对齐蓝色气泡
            bubble = tk.Frame(row, bg=BG_USER_BUBBLE)
            bubble.pack(side=tk.RIGHT, anchor="e")
            inner_pad = (12, 8)
            fg = "white"
            anchor = "e"
        else:
            # 左对齐深色气泡
            bubble = tk.Frame(row, bg=BG_AGENT_BUBBLE)
            bubble.pack(side=tk.LEFT, anchor="w")
            inner_pad = (12, 8)
            fg = FG_PRIMARY
            anchor = "w"

        lbl = tk.Label(bubble, text=text, bg=bubble["bg"], fg=fg,
                       font=("Segoe UI", 10), justify=tk.LEFT, anchor=anchor,
                       wraplength=480, padx=inner_pad[0], pady=inner_pad[1])
        lbl.pack()

        # 滚动到底部
        self.root.after(50, lambda: self.chat_canvas.yview_moveto(1.0))

    def _add_options(self, title: str, options: dict[str, str], callback, columns: int = 3):
        """添加选项卡片组。"""
        row = tk.Frame(self.chat_inner, bg=BG_CHAT)
        row.pack(fill=tk.X, padx=12, pady=4)

        container = tk.Frame(row, bg=BG_AGENT_BUBBLE)
        container.pack(side=tk.LEFT, anchor="w")

        tk.Label(container, text=title, bg=BG_AGENT_BUBBLE, fg=FG_PRIMARY,
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill=tk.X, padx=12, pady=(10, 4))

        grid = tk.Frame(container, bg=BG_AGENT_BUBBLE)
        grid.pack(fill=tk.X, padx=8, pady=(0, 8))

        items = list(options.items())
        for i, (key, desc) in enumerate(items):
            card = tk.Frame(grid, bg=BG_CARD, cursor="hand2",
                            highlightthickness=1, highlightbackground=BORDER)
            card.grid(row=i // columns, column=i % columns, padx=3, pady=3, sticky="nsew")
            card.bind("<Button-1>", lambda e, k=key: callback(k))
            tk.Label(card, text=key, bg=BG_CARD, fg=ACCENT,
                     font=("Segoe UI", 9, "bold"), anchor="w").pack(fill=tk.X, padx=8, pady=(6, 0))
            tk.Label(card, text=desc, bg=BG_CARD, fg=FG_MUTED,
                     font=("Segoe UI", 8), anchor="w", wraplength=140).pack(fill=tk.X, padx=8, pady=(0, 6))
            # hover effect
            for child in [card] + list(card.children.values()):
                card.bind("<Enter>", lambda e, c=card: c.configure(bg=BG_CARD_HOVER))
                card.bind("<Leave>", lambda e, c=card: c.configure(bg=BG_CARD))

        self.root.after(50, lambda: self.chat_canvas.yview_moveto(1.0))

    def _add_confirm(self, text: str, on_yes, on_no):
        """添加确认按钮。"""
        row = tk.Frame(self.chat_inner, bg=BG_CHAT)
        row.pack(fill=tk.X, padx=12, pady=4)

        container = tk.Frame(row, bg=BG_AGENT_BUBBLE)
        container.pack(side=tk.LEFT, anchor="w")

        tk.Label(container, text=text, bg=BG_AGENT_BUBBLE, fg=FG_PRIMARY,
                 font=("Segoe UI", 10), wraplength=460, anchor="w").pack(fill=tk.X, padx=12, pady=(10, 8))

        btn_row = tk.Frame(container, bg=BG_AGENT_BUBBLE)
        btn_row.pack(fill=tk.X, padx=12, pady=(0, 10))

        yes_btn = tk.Button(btn_row, text="确认开始", command=on_yes,
                            bg=ACCENT, fg="white", font=("Segoe UI", 9, "bold"),
                            relief=tk.FLAT, padx=16, pady=4, cursor="hand2")
        yes_btn.pack(side=tk.LEFT, padx=(0, 8))
        no_btn = tk.Button(btn_row, text="取消", command=on_no,
                           bg=BG_CARD, fg=FG_SECONDARY, font=("Segoe UI", 9),
                           relief=tk.FLAT, padx=16, pady=4, cursor="hand2")
        no_btn.pack(side=tk.LEFT)

        self.root.after(50, lambda: self.chat_canvas.yview_moveto(1.0))

    def _add_info(self, lines: list[str]):
        """添加信息文本。"""
        text = "\n".join(f"  {line}" for line in lines)
        row = tk.Frame(self.chat_inner, bg=BG_CHAT)
        row.pack(fill=tk.X, padx=12, pady=2)
        container = tk.Frame(row, bg=BG_AGENT_BUBBLE)
        container.pack(side=tk.LEFT, anchor="w")
        tk.Label(container, text=text, bg=BG_AGENT_BUBBLE, fg=FG_MUTED,
                 font=("Cascadia Code", 9), justify=tk.LEFT, anchor="w",
                 padx=12, pady=6).pack()
        self.root.after(50, lambda: self.chat_canvas.yview_moveto(1.0))

    # ============ 核心逻辑 ============

    def _send(self):
        if self._task_running:
            return
        text = self.input_text.get("1.0", tk.END).strip()
        if not text:
            return
        self.input_text.delete("1.0", tk.END)
        self._add_bubble("user", text)

        # 检测是否有设计/UI 关键词
        has_design = any(w in text for w in
            ["设计", "页面", "网站", "前端", "UI", "界面", "样式", "风格",
             "电商", "商店", "首页", "着陆页", "landing", "dashboard", "面板",
             "design", "web", "frontend", "app"])

        if has_design and self._phase == "idle":
            self._pending_description = text
            self._phase = "style"
            self._add_options("选择设计风格", STYLES, self._on_style_chosen)
        else:
            self._execute(text)

    def _on_style_chosen(self, style: str):
        self._style = style
        self._add_bubble("agent", f"风格: {style} — {STYLES[style]}")
        self._phase = "theme"
        self._add_options("选择主题色 (可选，点击跳过)",
                         {**THEMES, "跳过": "使用风格默认色"},
                         self._on_theme_chosen)

    def _on_theme_chosen(self, theme: str):
        if theme == "跳过":
            self._theme = ""
            self._add_bubble("agent", "使用默认主题色")
        else:
            self._theme = theme
            self._add_bubble("agent", f"主题: {theme}")
        self._phase = "output"
        self._add_options("输出框架", OUTPUTS, self._on_output_chosen)

    def _on_output_chosen(self, output: str):
        self._output = output
        self._add_bubble("agent", f"输出: {OUTPUTS[output]}")
        self._ask_confirm()

    def _ask_confirm(self):
        est = self.client.estimate(
            self._pending_description, style=self._style,
            output_format=self._output,
            allow_search=self._search if self._search else None,
        )
        summary = (
            f"确认汇总\n\n"
            f"需求: {self._pending_description[:60]}\n"
            f"风格: {self._style}  主题: {self._theme or '默认'}\n"
            f"输出: {self._output}\n\n"
            f"预估: {est.total_tokens:,} tokens  |  "
            f"{est.cost_range[0]} ~ {est.cost_range[1]} 元"
        )
        self._add_confirm(summary, self._on_confirmed, self._on_cancelled)

    def _on_confirmed(self):
        self._add_bubble("agent", "开始生成项目...")
        self._execute(self._pending_description)

    def _on_cancelled(self):
        self._phase = "idle"
        self._pending_description = ""
        self._add_bubble("agent", "已取消。随时告诉我新的想法。")

    def _execute(self, text: str):
        self._task_running = True
        self._status_dot.configure(fg=ACCENT_YELLOW)
        threading.Thread(target=self._run_task, args=(text,), daemon=True).start()

    def _run_task(self, text: str):
        try:
            est = self.client.estimate(
                text, style=self._style, output_format=self._output,
                allow_search=self._search if self._search else None,
            )
            self.root.after(0, self._add_info, [
                f"预估: {est.total_tokens:,} tokens",
                f"费用: {est.cost_range[0]} ~ {est.cost_range[1]} 元",
                "正在调用 Agent...",
            ])

            result = self.client.execute(
                text,
                style=self._style, theme=self._theme or None,
                output_format=self._output,
                allow_search=self._search if self._search else None,
                sandbox=self._sandbox,
            )

            if result.status == "completed":
                self.root.after(0, self._add_bubble, "agent",
                    f"项目已生成！\n\n"
                    f"任务 ID: {result.thread_id}\n"
                    f"输出目录: preview/\n\n"
                    f"点击右侧面板查看生成的文件。")
                self.root.after(100, self._refresh_files)
                self.root.after(0, self._status_dot.configure, {"fg": ACCENT_GREEN})
            elif result.status == "waiting_human":
                self.root.after(0, self._add_bubble, "agent",
                    f"任务需要人工审批。\n任务 ID: {result.thread_id}\n"
                    f"在终端执行: fedcli approve {result.thread_id}")
            else:
                self.root.after(0, self._add_bubble, "agent",
                    f"任务失败: {result.error or result.status}")
                self.root.after(0, self._status_dot.configure, {"fg": ACCENT_GREEN})
        except Exception as e:
            self.root.after(0, self._add_bubble, "agent",
                f"连接失败: {e}\n请确保已执行 python run.py 启动 Gateway")
            self.root.after(0, self._status_dot.configure, {"fg": "#ef4444"})
        finally:
            self._task_running = False
            self._phase = "idle"
            self._pending_description = ""

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    FedcliGUI().run()
