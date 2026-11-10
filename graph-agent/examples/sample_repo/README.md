# sample_repo（故意不安全）

这个目录是给 `ai-lab-agent` 练手的靶子，里面的代码**故意**包含常见的安全问题：

- `app.py`：`shell=True` 命令注入、`eval` 任意代码执行、硬编码口令、`verify=False`
- `utils.py`：`os.system` 命令注入、`pickle.loads` 反序列化

用它跑一遍：

```bash
cd graph-agent
LAB_WORKSPACE_ROOT=$PWD/examples/sample_repo \
  python -m ai_lab_agent.cli app.py utils.py
```

预期：7 条发现，全部经脚本复核为 confirmed。
