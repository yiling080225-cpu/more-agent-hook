#!/usr/bin/env python
"""
联邦适应性插件 — LLM 能力探测 + 岗位重分配 + 自动重启

工作流:
1. 扫描 CC-Switch DB 找出所有 claude 类型 provider
2. 对每个 provider 用其推荐模型做能力探测 (text/json/code/vision)
3. 按能力评分给 3 个岗位 (multimodal/code/review) 分配最佳 LLM
4. 供应商不足 3 个时, 能力强的 LLM 兼任多岗位
5. 写入 .env 并重启 Gateway

用法:
    python scripts/adapt_federation.py             # 探测+重分配+重启
    python scripts/adapt_federation.py --dry-run   # 只探测, 不写 .env
    python scripts/adapt_federation.py --no-restart # 探测+写 .env, 不重启
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx
from anthropic import AsyncAnthropic

PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
CCSWITCH_DB = Path.home() / ".cc-switch" / "cc-switch.db"


# ── 数据结构 ────────────────────────────────────────────────────────

@dataclass
class Candidate:
    """一个候选 LLM 的探测结果"""
    provider: str            # CC-Switch provider 名 (DeepSeek / Claude / GPT5.5 ...)
    base_url: str            # Anthropic SDK base_url (已剥 /v1 后缀)
    api_key: str
    model: str               # 实际 model 名
    scores: dict[str, int] = field(default_factory=dict)
    error: str = ""

    @property
    def alive(self) -> bool:
        return not self.error and self.scores.get("text", 0) > 0

    @property
    def total(self) -> int:
        return sum(self.scores.values())


# ── 1. 加载候选 ──────────────────────────────────────────────────────

def load_candidates() -> list[Candidate]:
    """从 CC-Switch DB 读取所有 claude 类型 provider"""
    if not CCSWITCH_DB.exists():
        print(f"[!] CC-Switch DB 未找到: {CCSWITCH_DB}")
        return []

    out = []
    conn = sqlite3.connect(str(CCSWITCH_DB))
    conn.row_factory = sqlite3.Row
    for r in conn.execute(
        "SELECT name, settings_config FROM providers WHERE app_type='claude'"
    ).fetchall():
        env = json.loads(r["settings_config"]).get("env", {})
        url = env.get("ANTHROPIC_BASE_URL", "")
        key = env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY", "")
        model = env.get("ANTHROPIC_MODEL", "")
        if not (url and key and model):
            continue
        # Anthropic SDK 自动追加 /v1/messages — base_url 不能带 /v1 后缀
        # 也有形如 /v1/chat/completions 的 OpenAI 兼容 URL, 此时取根域名
        if url.endswith("/v1"):
            url = url[:-3]
        elif "/v1/" in url:
            url = url.split("/v1/")[0]
        out.append(Candidate(
            provider=r["name"], base_url=url, api_key=key, model=model
        ))
    conn.close()
    return out


# ── 2. 能力探测 ──────────────────────────────────────────────────────

PROBES = {
    "text": {
        "prompt": "Reply with the single word: pong",
        "check": lambda s: "pong" in s.lower(),
        "weight": 1,
    },
    "json": {
        "prompt": 'Output ONLY this JSON, no extra text: {"ok": true, "n": 42}',
        "check": lambda s: '"ok"' in s and '42' in s,
        "weight": 2,
    },
    "code": {
        "prompt": "Write a Python function add(a,b) that returns a+b. Output ONLY the code, no explanation.",
        "check": lambda s: "def add" in s and "return" in s,
        "weight": 3,
    },
    "vision": {
        # 1x1 红色 PNG (base64)
        "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
        "prompt": "What color is the image? Reply with one word.",
        "check": lambda s: "red" in s.lower() or "红" in s,
        "weight": 2,
    },
}


async def probe_one(c: Candidate, dim: str, spec: dict, timeout: float = 30) -> int:
    """对一个 LLM 跑一项能力测试, 返回得分 (0 = 失败)"""
    try:
        client = AsyncAnthropic(
            base_url=c.base_url, api_key=c.api_key,
            timeout=httpx.Timeout(timeout, connect=10),
        )
        if dim == "vision":
            content = [
                {"type": "image", "source": {"type": "base64",
                  "media_type": "image/png", "data": spec["image"]}},
                {"type": "text", "text": spec["prompt"]},
            ]
        else:
            content = spec["prompt"]
        resp = await client.messages.create(
            model=c.model, max_tokens=200,
            messages=[{"role": "user", "content": content}],
        )
        # 兼容 thinking blocks: 找到第一个 TextBlock
        text = ""
        for block in (resp.content or []):
            if hasattr(block, "text"):
                text = block.text
                break
        return spec["weight"] if spec["check"](text) else 0
    except Exception:
        return 0


async def probe_candidate(c: Candidate) -> Candidate:
    """对一个候选并发跑所有能力测试"""
    dims = list(PROBES.keys())
    results = await asyncio.gather(*[probe_one(c, d, PROBES[d]) for d in dims])
    c.scores = dict(zip(dims, results))
    if not any(results):
        c.error = "all probes failed (likely auth or model issue)"
    return c


async def probe_all(cands: list[Candidate]) -> list[Candidate]:
    """并发探测所有候选"""
    return await asyncio.gather(*[probe_candidate(c) for c in cands])


# ── 3. 岗位分配 ──────────────────────────────────────────────────────

# 每个岗位看重的能力维度 (权重)
ROLE_WEIGHTS = {
    "multimodal": {"vision": 4, "json": 2, "text": 1},
    "code": {"code": 4, "json": 2, "text": 1},
    "review": {"code": 2, "json": 3, "text": 1},
}

ROLES = list(ROLE_WEIGHTS.keys())


def role_fit(c: Candidate, role: str) -> int:
    """候选 c 对岗位 role 的适配度评分"""
    weights = ROLE_WEIGHTS[role]
    return sum(c.scores.get(d, 0) * w for d, w in weights.items())


def assign_roles(alive: list[Candidate]) -> dict[str, Candidate]:
    """
    按能力把候选分配给 3 个岗位.
    - 候选数 >= 3: 每个岗位独占最适合的候选
    - 候选数 < 3: 能力最强的兼任空缺岗位
    """
    if not alive:
        return {}

    # 每个岗位算出候选排序
    rank = {r: sorted(alive, key=lambda c: role_fit(c, r), reverse=True) for r in ROLES}

    assignment: dict[str, Candidate] = {}
    if len(alive) >= len(ROLES):
        # 贪心: 按"该岗位最佳分数"从高到低分配, 已用候选不再选
        used: set[str] = set()
        order = sorted(ROLES, key=lambda r: -role_fit(rank[r][0], r))
        for r in order:
            for c in rank[r]:
                if c.provider not in used:
                    assignment[r] = c
                    used.add(c.provider)
                    break
    else:
        # 候选不足: 每个岗位选当前最佳, 允许复用
        for r in ROLES:
            assignment[r] = rank[r][0]

    return assignment


# ── 4. 写 .env ───────────────────────────────────────────────────────

def write_env(assignment: dict[str, Candidate]) -> None:
    """把分配结果写入 .env 的模型字段, 保留其他配置"""
    if not assignment:
        print("[!] 无可用候选, 跳过 .env 更新")
        return

    text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    lines = text.splitlines()

    # 岗位 → env key
    role_to_env = {
        "multimodal": "MULTIMODAL_MODEL",
        "code": "CODE_MODEL",
        "review": "REVIEW_MODEL",
    }
    # Router 用 multimodal 同款 (便宜的那个)
    new_vals = {role_to_env[r]: assignment[r].model for r in ROLES}
    new_vals["ROUTER_MODEL"] = assignment["multimodal"].model

    out = []
    seen = set()
    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            k = stripped.split("=", 1)[0].strip()
            if k in new_vals:
                out.append(f"{k}={new_vals[k]}")
                seen.add(k)
                continue
        out.append(line)
    # 缺失的追加
    for k, v in new_vals.items():
        if k not in seen:
            out.append(f"{k}={v}")

    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"[OK] .env 已更新")


# ── 5. 重启 Gateway ─────────────────────────────────────────────────

def kill_gateway() -> None:
    """杀掉占用 8000-8003 端口的进程"""
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"], stderr=subprocess.DEVNULL, text=True
        )
    except Exception:
        return
    pids = set()
    for line in out.splitlines():
        if "LISTENING" in line and any(f":{p} " in line for p in range(8000, 8004)):
            parts = line.split()
            if parts:
                pids.add(parts[-1])
    for pid in pids:
        subprocess.run(
            ["taskkill", "/F", "/PID", pid],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    if pids:
        print(f"[OK] 已结束旧进程: {sorted(pids)}")


def start_gateway() -> None:
    """后台启动 run.py"""
    log = PROJECT_ROOT / "data" / "gateway.log"
    log.parent.mkdir(exist_ok=True)
    if os.name == "nt":
        DETACHED = 0x00000008  # DETACHED_PROCESS
        subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / "run.py")],
            cwd=str(PROJECT_ROOT),
            stdout=log.open("ab"), stderr=subprocess.STDOUT,
            creationflags=DETACHED,
            close_fds=True,
        )
    else:
        subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / "run.py")],
            cwd=str(PROJECT_ROOT),
            stdout=log.open("ab"), stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def wait_healthy(timeout: float = 30) -> bool:
    """等待 Gateway 健康"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get("http://127.0.0.1:8000/health", timeout=2)
            if r.status_code == 200 and r.json().get("agents_registered", 0) >= 3:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


# ── 6. 报告 ─────────────────────────────────────────────────────────

def render_report(cands: list[Candidate], assignment: dict[str, Candidate]) -> str:
    """打印探测结果 + 岗位分配"""
    lines = []
    lines.append("=" * 70)
    lines.append("LLM 能力探测")
    lines.append("=" * 70)
    lines.append(f"{'供应商':<20} {'模型':<28} text json code vision  状态")
    lines.append("-" * 70)
    for c in cands:
        s = c.scores
        flag = "OK " if c.alive else "FAIL"
        lines.append(
            f"{c.provider:<20} {c.model:<28} "
            f"{s.get('text',0):>4} {s.get('json',0):>4} {s.get('code',0):>4} "
            f"{s.get('vision',0):>6}   {flag}"
        )
        if c.error:
            lines.append(f"  -> error: {c.error[:80]}")

    lines.append("")
    lines.append("=" * 70)
    lines.append("岗位分配")
    lines.append("=" * 70)
    if not assignment:
        lines.append("无可用候选")
    else:
        seen_providers: dict[str, list[str]] = {}
        for role, c in assignment.items():
            seen_providers.setdefault(c.provider, []).append(role)
            fit = role_fit(c, role)
            lines.append(f"  {role:<11} -> {c.provider:<15} {c.model:<28} (fit={fit})")
        # 兼任提示
        for prov, roles in seen_providers.items():
            if len(roles) > 1:
                lines.append(f"  [!] {prov} 兼任 {len(roles)} 岗: {roles}")
    return "\n".join(lines)


# ── main ────────────────────────────────────────────────────────────

async def amain(args) -> int:
    cands = load_candidates()
    if not cands:
        print("[!] CC-Switch 中没有可用 provider")
        return 1
    print(f"[..] 探测 {len(cands)} 个候选...")
    cands = await probe_all(cands)
    alive = [c for c in cands if c.alive]
    assignment = assign_roles(alive)

    print(render_report(cands, assignment))

    if args.dry_run:
        print("\n[dry-run] 未写入 .env, 未重启")
        return 0

    write_env(assignment)

    if args.no_restart:
        print("\n[no-restart] .env 已更新, 未重启")
        return 0

    print("\n[..] 重启 Gateway...")
    kill_gateway()
    time.sleep(2)
    start_gateway()
    if wait_healthy():
        print("[OK] Gateway 已就绪 (http://127.0.0.1:8000/health)")
        return 0
    print("[!] Gateway 启动超时, 检查 data/gateway.log")
    return 2


def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    parser = argparse.ArgumentParser(description="联邦适应性插件")
    parser.add_argument("--dry-run", action="store_true", help="只探测, 不修改 .env")
    parser.add_argument("--no-restart", action="store_true", help="写 .env 但不重启")
    args = parser.parse_args()
    try:
        return asyncio.run(amain(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
