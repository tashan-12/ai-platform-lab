"""示例目标文件：故意写得不安全，用于演示扫描与验证流程。

⚠️ 不要模仿：这里的每一处写法都是反面教材。
"""

import subprocess

import requests

DB_PASSWORD = "P@ssw0rd123456"
API_KEY = "sk-demo-1234567890"


def run_user_command(user_input: str) -> str:
    # 命令注入：用户输入直接拼进 shell
    return subprocess.check_output(f"ls {user_input}", shell=True, text=True)


def compute(expression: str) -> int:
    # 任意代码执行
    return eval(expression)


def fetch(url: str) -> str:
    # 关闭证书校验
    return requests.get(url, verify=False, timeout=5).text
