"""Non-destructive SQLite copy for moving an older project DB to the V18 target.

Usage: py migrate_sqlite.py source.db target.db
The source is never modified; an existing target is never overwritten.
"""
import argparse
import sqlite3
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    target = args.target.resolve()
    if not source.is_file():
        raise SystemExit(f"來源資料庫不存在：{source}")
    if source == target:
        raise SystemExit("來源與目標不能是同一個檔案")
    if target.exists():
        raise SystemExit(f"目標已存在，不覆蓋：{target}。請先備份並移走目標檔。")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as src, sqlite3.connect(target) as dst:
            result = src.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise RuntimeError(f"來源資料庫完整性檢查失敗：{result}")
            src.backup(dst)
            verify = dst.execute("PRAGMA integrity_check").fetchone()
            if not verify or verify[0] != "ok":
                raise RuntimeError(f"目標資料庫完整性檢查失敗：{verify}")
    except Exception:
        if target.exists():
            target.unlink()
        raise
    print(f"資料庫已複製：{source} -> {target}")
    print("來源檔保留未修改。啟動 app.py 後，系統會建立缺少的使用者表。")


if __name__ == "__main__":
    main()
