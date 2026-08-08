#!/bin/bash
# macOS: 이 파일을 더블클릭하면 검색기가 열립니다.
cd "$(dirname "$0")"
python3 -m pip install --quiet pymupdf
( sleep 1.5; open "http://127.0.0.1:8765" ) &
python3 -m gichul web
