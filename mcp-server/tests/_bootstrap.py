import sys
from pathlib import Path

# 让测试可以直接跑，不需要先 pip install
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
