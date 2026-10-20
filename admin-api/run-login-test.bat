@echo off
REM 一键启动登录联调测试页
REM   终端1：admin-api    -> http://127.0.0.1:8020
REM   终端2：登录测试页   -> http://127.0.0.1:5173/login.html
REM
REM 端口选 5173 是因为后端 CORS 白名单里就有它（Vite 默认端口），
REF 换成别的端口需要同步改 .env 的 CORS_ORIGINS。

cd /d "%~dp0"

echo [1/3] 初始化数据库（灌种子数据）
call uv run python -m admin_api.seed
if errorlevel 1 goto :err

echo.
echo [2/3] 启动 admin-api (127.0.0.1:8020)...
start "admin-api" cmd /k "cd /d "%~dp0" && uv run uvicorn admin_api.main:app --host 127.0.0.1 --port 8020"

echo [3/3] 启动登录测试页 (127.0.0.1:5173)...
start "login-web" cmd /k "cd /d "%~dp0" && uv run python -m http.server 5173 --directory web-test --bind 127.0.0.1"

echo.
echo 两个窗口都起来后，浏览器打开：
echo     http://127.0.0.1:5173/login.html
echo.
echo 测试账号：admin/admin123 · operator/op123456 · viewer/view123
exit /b 0

:err
echo.
echo [失败] 数据库初始化未成功，请先在项目根目录执行 uv sync 安装依赖。
exit /b 1