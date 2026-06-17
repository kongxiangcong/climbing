"""月报脚本：生成市场与宏观月报。"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.cli.analyze import analyze_macro

if __name__ == "__main__":
    analyze_macro()
