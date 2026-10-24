#!/bin/sh
# 重写 git 历史，把敏感值替换成占位符。
#
# 为什么需要：仓库是公开的，内网地址 / 登录账号曾被提交过。
# `git rm` 只影响当前版本，历史里还在——而公开仓库的历史可以被任意
# clone 下来逐个 commit 翻查。
#
# 为什么用 git-filter-repo 而不是 git filter-branch：
# filter-branch 在 Windows 上极慢（tree-filter 要为每个提交 checkout
# 整棵文件树，实测 20 个提交跑了 10 分钟仍未结束），而且官方自己都在
# 警告它有一堆坑、直接建议改用 filter-repo。
# filter-repo 实测同样 20 个提交只要 4.7 秒。
#
# ⚠️ 重写会改变所有 commit hash，必须 force push。
#    而且**即使重写完，也建议在服务端轮换凭据**——历史在公开仓库里
#    暴露过多久，谁也不知道，缓存/镜像/第三方爬虫都可能已经抓走。
#
# 用法：
#   sh scripts/rewrite_history.sh            # 在本地仓库重写
#   git push --force --mirror origin         # 推到远程（危险，需确认）
set -e

cd "$(git rev-parse --show-toplevel)"

echo "== 重写前 =="
for v in "10.0.0.1" "your_account" "00000000000000000000000000000000"; do
  echo "  $v -> $(git log --all --oneline -S "$v" | wc -l) 个提交"
done

# 替换规则文件：每行「原值==>新值」
# 语法见 git-filter-repo 手册的 --replace-text。
RULES=$(mktemp)
cat > "$RULES" <<'EOF'
10.0.0.1==>10.0.0.1
:8080==>:8080
your_account==>your_account
00000000000000000000000000000000==>00000000000000000000000000000000
EOF

# 优先用 git-filter-repo 命令；没有则退回 python -m git_filter_repo
if command -v git-filter-repo >/dev/null 2>&1; then
  git-filter-repo --replace-text "$RULES" --force
elif python -m git_filter_repo --version >/dev/null 2>&1; then
  python -m git_filter_repo --replace-text "$RULES" --force
else
  echo "未找到 git-filter-repo，请先安装：pip install git-filter-repo" >&2
  rm -f "$RULES"
  exit 1
fi

rm -f "$RULES"

echo ""
echo "== 重写后（都应为 0）=="
for v in "10.0.0.1" "your_account" "00000000000000000000000000000000"; do
  echo "  $v -> $(git log --all --oneline -S "$v" | wc -l) 个提交"
done

echo ""
echo "⚠️  下一步需要 force push 才能让远程历史也干净："
echo "    git remote add origin <url>   # filter-repo 会移除 origin"
echo "    git push --force --mirror origin"
