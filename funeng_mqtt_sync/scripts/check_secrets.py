"""敏感信息自查脚本 —— 提交前扫一遍仓库，确认没有把凭据带进去。

背景：这个仓库是**公开的**。之前内网地址、登录账号、密码 md5 都曾写进
源码和文档，一旦提交就等于公开。而 `git log` 里的历史尤其危险——
`git rm` 只删当前版本，历史里还在。

这个脚本做两件事：

1. **扫工作区**：检查会被提交的文件里有没有敏感模式
   （内网 IP、32 位 md5、AK/SK、密码赋值等）。
2. **扫 git 历史**：检查所有 commit 里有没有出现过敏感值。

用法：
    python scripts/check_secrets.py           # 扫工作区 + 历史
    python scripts/check_secrets.py --worktree # 只扫工作区
    python scripts/check_secrets.py --history  # 只扫历史

退出码：0 = 干净；1 = 发现疑似敏感信息。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent

# 需要扫描的目录（相对项目根）
SCAN_DIRS = ("src", "tests", "scripts", "blog-content")

# 文件后缀白名单
SCAN_SUFFIXES = {".py", ".md", ".txt", ".toml", ".cfg", ".ini", ".yml", ".yaml"}

# 会被忽略的路径片段
SKIP_PARTS = {
    ".venv", ".py312", ".git", "node_modules", "__pycache__",
    "img", "out", ".pytest_cache", ".ruff_cache",
}

# ---- 敏感模式 ----------------------------------------------------------
# 每条规则：(名称, 正则, 说明)
# 说明里要写清「命中后怎么办」，方便对照处理。
RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "内网 / 私有 IP 地址",
        re.compile(
            r"\b(?:"
            r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}"          # 10.0.0.0/8
            r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"  # 172.16.0.0/12
            r"|192\.168\.\d{1,3}\.\d{1,3}"             # 192.168.0.0/16
            r"|169\.254\.\d{1,3}\.\d{1,3}"             # 链路本地
            # 其余 IPv4（含 111.x 这类「公网段里做内网部署」的情况）
            r"|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
            r")\b"
        ),
        "真实服务地址，公开仓库里等于泄露网络拓扑与部署信息",
    ),
    (
        "疑似 md5 密码",
        re.compile(r"\b[0-9a-f]{32}\b"),
        "32 位十六进制，像 md5 摘要（也可能是文件 hash，需人工确认）",
    ),
    (
        "云服务密钥",
        re.compile(
            r"\b(?:BAIDU_)?(?:API_KEY|SECRET_KEY|ACCESS_KEY|APP_KEY)\s*[=:]\s*[\"']?[A-Za-z0-9]{16,}"
        ),
        "云服务 AK/SK",
    ),
    (
        "password 赋值",
        # 只在值不是尖括号占位符时才判定为疑似硬编码
        re.compile(
            r"[\"']?password[\"']?\s*[=:]\s*[\"'](?![<\[])[^\"']{6,}[\"']",
            re.IGNORECASE,
        ),
        "疑似硬编码口令",
    ),
]

# 已知的安全占位符 / 示例值，命中这些不算问题
ALLOWLIST = {
    # 文档里明确标注为示例的地址
    "10.0.0.1",
    "127.0.0.1",
    "0.0.0.0",
    "192.168.1.1",
    "8.8.8.8",
    # 代码里显式标注的占位符
    "<内网IP>",
    "<你的账号>",
    "<32位小写md5>",
    "<明文密码的 md5>",
    "<端口>",
    # 测试里用的假值
    "0" * 32,
    "deadbeef" * 4,
    "a" * 32,
    "f" * 32,
}


def _is_skipped(path: Path) -> bool:
    """判断路径是否该跳过。"""
    return bool(SKIP_PARTS & set(path.parts))


def _iter_files() -> list[Path]:
    """列出需要扫描的文件。

    脚本自身要排除——它的正则里就写着「内网网段长什么样」，
    不排除的话每次都会把自己报一遍（自指噪声）。
    """
    self_path = Path(__file__).resolve()
    files: list[Path] = []
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in SCAN_SUFFIXES:
                continue
            if _is_skipped(p) or p.resolve() == self_path:
                continue
            files.append(p)

    # 项目根下的配置文件
    for name in ("README.md", "pyproject.toml", "run.bat", ".env.example"):
        p = ROOT / name
        if p.is_file():
            files.append(p)

    # 仓库根 README
    root_readme = REPO / "README.md"
    if root_readme.is_file():
        files.append(root_readme)

    return files


def scan_worktree() -> list[tuple[str, str, str]]:
    """扫描工作区，返回 [(规则名, 文件相对路径, 行内容)]。"""
    hits: list[tuple[str, str, str]] = []
    for path in _iter_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for lineno, line in enumerate(text.splitlines(), 1):
            for name, pattern, _ in RULES:
                m = pattern.search(line)
                if not m:
                    continue
                # 只拿「匹配到的那段文本」去比白名单，而不是整行——
                # 否则一行里既有示例又有真值时会被误放行。
                matched = m.group(0)
                if matched in ALLOWLIST:
                    continue
                hits.append(
                    (
                        name,
                        f"{path.relative_to(REPO)}:{lineno}",
                        line.strip()[:120],
                    )
                )
                break  # 一行只报一次，避免刷屏
    return hits


def scan_history() -> list[tuple[str, str]]:
    """扫描 git 历史，返回 [(规则名, 命中摘要)]。

    用 `git log -S` 逐个敏感值反查，比遍历所有 blob 快得多。
    """
    hits: list[tuple[str, str]] = []

    # 需要在历史里反查的具体值（从当前 .env 读取真实值）
    secrets: list[str] = []
    env_file = ROOT / ".env"
    if env_file.is_file():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            _, _, value = line.partition("=")
            value = value.strip()
            # 只查看起来像真凭据的值（占位符跳过）
            if len(value) >= 8 and not value.startswith("<"):
                secrets.append(value)

    for value in secrets:
        try:
            result = subprocess.run(
                ["git", "log", "--all", "--oneline", "-S", value],
                cwd=REPO,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue

        commits = [ln for ln in result.stdout.splitlines() if ln.strip()]
        if commits:
            hits.append(
                (
                    "敏感值出现在 git 历史",
                    f"值以 *{value[:4]}**** 开头，出现于 {len(commits)} 个提交："
                    f"{commits[0][:60]}",
                )
            )

    return hits


def main() -> int:
    """执行自查。

    Returns:
        0 表示干净，1 表示发现疑似敏感信息。
    """
    only = sys.argv[1] if len(sys.argv) > 1 else ""

    print("=" * 68)
    print("敏感信息自查")
    print("=" * 68)

    total = 0

    if only in ("", "--worktree"):
        print("\n[1/2] 扫描工作区 ...")
        wt_hits = scan_worktree()
        if wt_hits:
            total += len(wt_hits)
            print(f"  ⚠ 发现 {len(wt_hits)} 处疑似敏感内容：\n")
            for name, where, line in wt_hits:
                rule_desc = next(
                    (d for n, _, d in RULES if n == name), ""
                )
                print(f"  • [{name}] {where}")
                print(f"      {line}")
                print(f"      → {rule_desc}\n")
        else:
            print("  ✓ 工作区干净")

    if only in ("", "--history"):
        print("\n[2/2] 扫描 git 历史 ...")
        hist_hits = scan_history()
        if hist_hits:
            total += len(hist_hits)
            print(f"  ⚠ 发现 {len(hist_hits)} 处历史泄露：\n")
            for name, detail in hist_hits:
                print(f"  • [{name}]")
                print(f"      {detail}\n")
            print("  → 历史一旦推到公开仓库就撤不回来了。彻底清除需要重写历史，")
            print("    例如用 git-filter-repo 替换文本；即使重写，也建议同时")
            print("    在服务端轮换（改密码 / 换密钥 / 换账号）。\n")
        else:
            print("  ✓ git 历史干净")

    print("=" * 68)
    if total:
        print(f"结论：发现 {total} 处疑似敏感信息，需要处理。")
        return 1
    print("结论：未发现敏感信息。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
