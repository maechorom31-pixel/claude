"""폴더 감시: 새 PDF가 들어오면 알아서 색인한다.

모의고사를 받을 때마다 명령을 치는 게 번거로우니, 폴더 하나를 정해 두고
거기 떨어뜨리기만 하면 되게 한다. 외부 의존성 없이 주기적 검사로 동작한다.
"""

from __future__ import annotations

import os
import time

from . import index as idx
from .pipeline import ingest_file


def _pdfs(folder: str) -> dict[str, float]:
    found: dict[str, float] = {}
    for root, _dirs, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(".pdf"):
                p = os.path.join(root, f)
                try:
                    found[p] = os.path.getmtime(p)
                except OSError:
                    pass
    return found


def _settled(path: str, wait: float = 1.0) -> bool:
    """복사가 끝난 파일인지. 크기가 더 안 늘면 완료로 본다."""
    try:
        a = os.path.getsize(path)
        time.sleep(wait)
        return a > 0 and a == os.path.getsize(path)
    except OSError:
        return False


def watch(folder: str, db_path: str, *, interval: float = 5.0,
          once: bool = False) -> None:
    conn = idx.connect(db_path)
    seen: dict[str, float] = {}
    print(f"감시 중: {folder}  (Ctrl+C 로 종료)")
    try:
        while True:
            for path, mtime in sorted(_pdfs(folder).items()):
                if seen.get(path) == mtime:
                    continue
                if not _settled(path):
                    continue
                seen[path] = mtime
                r = ingest_file(conn, path, force=False)
                name = os.path.basename(path)
                if r.status == "skipped":
                    continue
                if r.status == "failed":
                    print(f"  ✗ {name}: {r.error}")
                    continue
                src = r.meta.source_label("").rstrip(" ·") if r.meta else "출처미상"
                print(f"  ✓ {name} → {src} · 문항 {r.n_questions}개")
                for w in r.warnings or []:
                    print(f"      ! {w}")
            if once:
                return
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n감시를 멈춥니다.")
    finally:
        conn.close()
