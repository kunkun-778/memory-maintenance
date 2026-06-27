# Memory Maintenance 2.0.0

> 智能记忆管理系统 - 自动维护、优化和分析你的 OpenClaw 长期记忆

## 🌟 特性亮点

- **智能去重**: 基于语义相似度自动检测和合并重复记忆
- **自动分类**: 智能标签系统，自动归类到 7 个预定义分类
- **质量评分**: 多维度评估记忆价值，保留最重要的内容
- **智能摘要**: 对相似记忆生成合并摘要，减少存储占用
- **关联图谱**: 构建记忆间的关联网络，发现隐藏联系
- **健康仪表盘**: 可视化展示记忆系统健康状况
- **交互模式**: 预览操作，避免误删重要记忆

## 📋 目录

- [安装](#安装)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [功能详解](#功能详解)
- [性能指标](#性能指标)
- [常见问题](#常见问题)
- [贡献指南](#贡献指南)

## 安装

### 系统要求

- Python 3.7+
- PyYAML
- OpenClaw 工作区

### 安装步骤

1. **克隆或下载技能**
```bash
cd ~/.openclaw/workspace/skills/
# 如果是从 Git 安装
git clone <repository-url> memory-maintenance
# 或者手动下载并解压
```

2. **配置**
```bash
cd memory-maintenance
cp config.yaml.example config.yaml
# 编辑 config.yaml 根据你的需求
```

3. **验证安装**
```bash
python3 maintain.py --version
```

## 快速开始

### 基本使用

```bash
# 运行完整维护流程
python3 maintain.py

# 查看生成的报告
xdg-open ~/.openclaw/workspace/memory/maintenance-report.html
xdg-open ~/.openclaw/workspace/memory/health-dashboard.html
```

### 启用高级功能

编辑 `config.yaml`：

```yaml
# 启用智能摘要
compression:
  enabled: true

# 启用访问追踪
access_tracking:
  enabled: true

# 启用交互模式
interactive:
  enabled: true
  dry_run: false
```

然后重新运行维护。

## 配置说明

### 基本配置

```yaml
# 记忆目录
memory_dir: "~/.openclaw/workspace/memory"
backup_dir: "backups"
archive_dir: "archived"

# 归档策略
archive_after_days: 30

# 去重配置
dedup_similarity_threshold: 0.85

# 质量评分
quality_scoring:
  min_length: 50
  max_length: 10000
  important_keywords_weight: 2.0

# 自动标签
auto_tagging:
  enabled: true
  categories: ["工作", "学习", "生活", "项目", "技术", "健康", "财务", "社交", "其他"]
```

### 第二阶段功能配置

```yaml
# 智能摘要与压缩
compression:
  enabled: false
  min_cluster_size: 3
  similarity_threshold: 0.6

# 访问频率追踪
access_tracking:
  enabled: false
  log_file: "access.log"

# 交互式维护
interactive:
  enabled: false
  dry_run: true
```

### 第三阶段功能配置

```yaml
# 记忆关联图谱
memory_graph:
  enabled: true
  min_common_keywords: 2
  max_links_per_node: 10

# 健康度仪表盘
health_dashboard:
  enabled: true
  update_frequency: "daily"
```

## 功能详解

### 1. 智能去重
- 使用 SequenceMatcher 计算文本相似度
- 自动检测相似记忆，保留质量更高的版本
- 可配置相似度阈值（默认 0.85）

### 2. 智能归档
- 基于重要性关键词检测
- 考虑质量评分和访问频率
- 保留最近活跃的记忆

### 3. 自动标签
- 7 个预定义分类
- 基于关键词匹配自动分类
- 支持自定义关键词文件

### 4. 质量评分
- 综合长度、结构、关键词密度、信息密度
- 加权评分算法
- 0-1 范围的评分

### 5. 智能摘要
- 对相似记忆聚类
- 生成合并摘要
- 减少存储占用

### 6. 关联图谱
- 基于关键词重叠建立链接
- 识别记忆聚类
- 生成图谱统计信息

### 7. 健康仪表盘
- 5 个维度的评估
- 可视化展示
- 智能改进建议

## 性能指标

- **处理速度**: ~50 个文件/3 秒
- **内存使用**: < 50 MB
- **图谱构建**: 50 节点/秒
- **仪表盘生成**: < 1 秒

## 常见问题

### Q: 如何备份我的记忆？
A: 每次运行维护时都会自动创建备份，保存在 `backups/` 目录中。

### Q: 如何恢复被误删的记忆？
A: 从备份目录中恢复，备份文件名包含时间戳。

### Q: 智能摘要会影响原始记忆吗？
A: 不会。摘要只是额外的文件，原始记忆保持不变。

### Q: 如何禁用某个功能？
A: 在 `config.yaml` 中将对应功能的 `enabled` 设为 `false`。

### Q: 性能会受影响吗？
A: 默认配置下性能影响很小。大规模记忆库建议禁用部分分析功能。

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 📄 许可证

MIT License

## 🙏 致谢

感谢所有贡献者和用户！

---

**版本**: 2.0.0  
**发布日期**: 2026-06-28  
**维护者**: 小雨
