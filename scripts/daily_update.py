"""日更脚本：收盘后一键更新。"""

import sys
from pathlib import Path

# 将项目根目录加入路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.cli.update import daily_update

if __name__ == "__main__":
    daily_update()
