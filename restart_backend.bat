@echo off
REM 设置项目根目录为当前目录
cd /d %~dp0

REM 设置 PYTHONPATH 环境变量
set PYTHONPATH=%cd%

REM 激活虚拟环境
call .venv\Scripts\activate

REM 停止可能运行的 Python 进程（谨慎使用，可能会关闭其他 Python 程序）
echo 正在停止旧进程...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *uvicorn*" 2>nul
timeout /t 2 /nobreak >nul

REM 启动新的服务
echo 正在启动后端服务...
echo.
echo 服务地址: http://localhost:8000
echo API文档: http://localhost:8000/docs
echo 健康检查: http://localhost:8000/health
echo.
echo 按 Ctrl+C 停止服务
echo ====================================
echo.

uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

pause


