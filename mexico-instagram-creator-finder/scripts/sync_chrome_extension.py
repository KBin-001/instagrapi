"""将正式扩展源码同步到兼容构建目录 dist/chrome_extension。"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "browser_extension"
TARGET = ROOT / "dist" / "chrome_extension"


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    for source in SOURCE.iterdir():
        if source.is_file():
            shutil.copy2(source, TARGET / source.name)
    print(f"Synced Chrome extension to {TARGET}")


if __name__ == "__main__":
    main()
