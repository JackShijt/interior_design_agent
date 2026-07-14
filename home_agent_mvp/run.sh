#!/usr/bin/env bash
# 一键启动 MVP 原型
set -e
cd "$(dirname "$0")"
export FLASK_APP=app.py
export FLASK_DEBUG=1
export PORT=5001
echo "启动 HomeAgent MVP → http://127.0.0.1:5001"
echo "测试: curl -X POST http://127.0.0.1:5001/generate -H 'Content-Type: application/json' -d '{\"need\":\"现代简约 两口之家 多收纳\"}'"
python app.py
