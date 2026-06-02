# 项目配置

## 语言规范
- 始终使用简体中文与用户交流
- 代码注释和文档可使用英文或中文

## 行为偏好
- 修改代码前简要说明计划，等用户确认再动手
- 不主动创建 git 提交，除非用户明确要求
- 不主动创建 README、说明文档等
- 优先编辑现有文件，而非创建新文件
- 不要过度设计，不要为"将来"增加抽象层
- 不要添加不必要的注释——代码本身应自解释

## 安全
- 不在代码中硬编码密钥、令牌或密码
- 发现安全漏洞立即指出
- 对外部输入做好校验和清理

## 自定义命令
- `/调用联邦` — 启动多模态 Agent 联邦，提交需求给 Gateway 调度执行

## 深度绑定规则: CC-Switch 与 config.py 同步

- `src/config.py` 中所有 LLM 供应商的 **模型名** 和 **URL** 默认值必须与 CC-Switch 数据库 (`~/.cc-switch/cc-switch.db`) 中 `providers` 表对应记录保持同步
- CC-Switch 数据库是权威数据源（Source of Truth），config.py 默认值仅作兜底
- **每当 CC-Switch 中的模型/URL 发生变更（升级、替换、新增供应商），必须同步更新 `src/config.py` 中对应的字段**
- 同步检查方法: `python -c "import sqlite3, json; from pathlib import Path; db=sqlite3.connect(str(Path.home()/'.cc-switch'/'cc-switch.db')); [print(f'{n}: model={json.loads(c).get(\"env\",{}).get(\"ANTHROPIC_MODEL\",\"?\")}, url={json.loads(c).get(\"env\",{}).get(\"ANTHROPIC_BASE_URL\",\"?\")}') for n,c in db.execute(\"SELECT name, settings_config FROM providers WHERE app_type='claude'\").fetchall()]"`
