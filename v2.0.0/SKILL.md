---
name: memory-maintenance
description: "维护 OpenClaw 长期记忆：扫描 ~/.openclaw/workspace/memory/，去重、归档、压缩、索引，并生成健康报告。"
version: 1.0.0
author: 小雨
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [openclaw, memory, maintenance, archive, dedupe]
    homepage: ""
    related_skills: []
---
# Memory Maintenance

专门为 **OpenClaw 长期记忆系统**设计的维护 Skill，保持记忆健康、简洁、可检索。

## 适用环境

- 记忆目录：`~/.openclaw/workspace/memory/`
- 记忆文件命名：`YYYY-MM-DD-HHMM.md`
- 配套文件：`memory-review-YYYY-MM-DD.md`、`memory-update-YYYY-MM-DD.md`

## 功能

- **记忆清理**：移除过期、冗余或无价值的记忆条目
- **去重优化**：识别并合并重复的记忆内容
- **压缩存储**：对相似记忆进行语义压缩，减少存储和检索开销
- **定期维护**：可配置为 Cron 任务自动执行
- **健康检查**：检测记忆系统的完整性和一致性

## 使用方法

```bash
python3 ~/.openclaw/workspace/skills/memory-maintenance/maintain.py
```

或作为 Skill 在 Hermes 中加载后，直接说：

```
帮我整理 OpenClaw 的记忆
```

## 维护频率建议

| 操作 | 建议频率 |
|------|---------|
| 去重 | 每周 |
| 压缩相似记忆 | 每月 |
| 归档旧记忆 | 每季度 |
| 完整性检查 | 每周 |

## 注意事项

- 维护前会自动备份到 `~/.openclaw/workspace/memory/backups/`
- 激进的清理可能导致 Agent 失去部分上下文
- 大规模维护操作耗时较长，建议低峰时段执行

## 待办

- [ ] 自动修复缺失的 frontmatter 字段
- [ ] 集成到 Hermes `/reload-skills` 命令中
- [ ] 支持自定义规则（通过 `config.yaml`）
