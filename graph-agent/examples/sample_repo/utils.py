"""示例目标文件之二：更多的反面教材。"""

import os
import pickle


def ping_host(host: str) -> int:
    # 命令注入面
    return os.system("ping -c 1 " + host)


def load_session(raw: bytes):
    # 反序列化不可信数据
    return pickle.loads(raw)
