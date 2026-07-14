#!/usr/bin/env bash
# 一键启动 MVP 原型
set -e
cd "$(dirname "$0")"
export FLASK_APP=app.py
export FLASK_DEBUG=1
echo "启动 HomeAgent MVP → http://localhost:5000"
echo "测试: curl -X POST localhost:5000/generate -H 'Content-Type: application/json' -d '{\"need\":\"现代简约 两口之家 多收纳\"}'"
python app.py
