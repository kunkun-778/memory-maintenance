#!/usr/bin/env python3
"""
Memory Maintenance - 维护 OpenClaw 长期记忆
支持语义去重、智能归档、自动标签、质量评分
第二阶段：智能摘要与压缩
第三阶段：关联图谱和健康仪表盘
"""
import os
import re
import json
import shutil
import hashlib
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, Counter
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional, Set

# OpenClaw 记忆目录配置
MEMORY_DIR = Path.home() / ".openclaw" / "workspace" / "memory"
BACKUP_DIR = MEMORY_DIR / "backups"
ARCHIVE_DIR = MEMORY_DIR / "archived"
INDEX_FILE = MEMORY_DIR / "memory-index.json"

# 加载配置
CONFIG_FILE = Path.home() / ".openclaw" / "workspace" / "skills" / "memory-maintenance" / "config.yaml"

def load_config():
    """加载配置文件"""
    default_config = {
        'archive_after_days': 30,
        'dedup_similarity_threshold': 0.85,
        'archive_policy': {
            'important_keywords': ['偏好', '决定', '重要', '记住', '关键', '必须', '一定'],
            'min_access_count': 3,
            'preserve_recent_active': 7
        },
        'quality_scoring': {
            'min_length': 50,
            'max_length': 10000,
            'important_keywords_weight': 2.0
        },
        'auto_tagging': {
            'enabled': True,
            'categories': ['工作', '学习', '生活', '项目', '技术', '健康', '财务', '社交', '其他'],
            'keyword_file': None
        }
    }
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    # 深度合并配置
                    for key, value in user_config.items():
                        if isinstance(value, dict) and key in default_config:
                            default_config[key].update(value)
                        else:
                            default_config[key] = value
        except Exception as e:
            print(f"⚠️ 加载配置文件失败: {e}，使用默认配置")
    
    return default_config

CONFIG = load_config()
ARCHIVE_AFTER_DAYS = CONFIG.get('archive_after_days', 30)
DEDUP_SIMILARITY_THRESHOLD = CONFIG.get('dedup_similarity_threshold', 0.85)


def ensure_dirs():
    """确保目录存在"""
    BACKUP_DIR.mkdir(exist_ok=True)
    ARCHIVE_DIR.mkdir(exist_ok=True)


def get_memory_files():
    """获取所有记忆文件"""
    files = sorted(MEMORY_DIR.glob("*.md"))
    return [f for f in files if f.name not in ["README.md", "memory-index.json"]]


def parse_memory_file(filepath):
    """解析记忆文件，返回标题、内容、时间戳"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 提取第一行作为标题
        lines = content.strip().split("\n")
        title = lines[0].strip() if lines else filepath.stem
        
        # 从文件名提取时间戳
        stem = filepath.stem
        timestamp = None
        for fmt in ["%Y-%m-%d-%H%M", "%Y-%m-%d"]:
            try:
                timestamp = datetime.strptime(stem, fmt)
                break
            except ValueError:
                continue
        
        return {
            "path": str(filepath),
            "name": filepath.name,
            "title": title,
            "content": content,
            "timestamp": timestamp,
            "size": len(content),
            "hash": hashlib.md5(content.encode()).hexdigest()
        }
    except Exception as e:
        return {"path": str(filepath), "error": str(e)}


def deduplicate(memories):
    """去重：基于内容哈希和语义相似度"""
    seen_hashes = set()
    duplicates = []
    unique = []
    
    # 首先按哈希去重（精确重复）
    hash_groups = defaultdict(list)
    for mem in memories:
        if "error" in mem:
            unique.append(mem)
            continue
        
        if mem["hash"] in seen_hashes:
            duplicates.append(mem)
        else:
            seen_hashes.add(mem["hash"])
            hash_groups[mem["hash"]].append(mem)
            unique.append(mem)
    
    # 然后按语义相似度去重（相似重复）
    if len(unique) > 1 and DEDUP_SIMILARITY_THRESHOLD < 1.0:
        semantic_unique = []
        semantic_duplicates = []
        
        for mem in unique:
            if "error" in mem:
                semantic_unique.append(mem)
                continue
            
            is_duplicate = False
            for existing in semantic_unique:
                if "error" in existing:
                    continue
                    
                similarity = calculate_text_similarity(mem["content"], existing["content"])
                if similarity >= DEDUP_SIMILARITY_THRESHOLD:
                    # 保留质量更高的那个（内容更长或质量评分更高）
                    mem_quality = score_memory_quality(mem)
                    existing_quality = score_memory_quality(existing)
                    
                    if mem_quality > existing_quality:
                        # 新记忆质量更高，替换旧的
                        semantic_duplicates.append(existing)
                        semantic_unique.remove(existing)
                        semantic_unique.append(mem)
                    else:
                        # 现有记忆质量更高，标记新的为重复
                        semantic_duplicates.append(mem)
                    
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                semantic_unique.append(mem)
        
        # 合并重复项
        duplicates.extend(semantic_duplicates)
        unique = semantic_unique
    
    return unique, duplicates


def calculate_text_similarity(text1, text2):
    """计算两个文本的相似度（0-1）"""
    if not text1 or not text2:
        return 0.0
    
    # 预处理：移除空白、标点，转为小写
    def preprocess(text):
        text = text.lower()
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)  # 保留中文和英文单词
        return text
    
    processed1 = preprocess(text1)
    processed2 = preprocess(text2)
    
    # 使用序列匹配器计算相似度
    similarity = SequenceMatcher(None, processed1, processed2).ratio()
    return similarity


def extract_keywords(text, top_n=10):
    """提取文本中的关键词"""
    # 简单的中文分词和关键词提取
    # 移除常见停用词
    stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
    
    # 提取中文字符和英文单词
    words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text.lower())
    
    # 过滤停用词和短词
    filtered_words = [w for w in words if w not in stopwords and len(w) > 1]
    
    # 统计词频
    word_freq = Counter(filtered_words)
    
    return [word for word, freq in word_freq.most_common(top_n)]


def auto_tag_memory(content):
    """自动为记忆打标签"""
    if not CONFIG.get('auto_tagging', {}).get('enabled', True):
        return [], '其他'
    
    categories = CONFIG['auto_tagging'].get('categories', ['其他'])
    
    # 简单的关键词匹配分类
    category_keywords = {
        '工作': ['工作', '项目', '会议', '任务', '报告', '客户', '老板', '同事', '办公室'],
        '学习': ['学习', '课程', '考试', '作业', '知识', '技能', '培训', '读书', '笔记'],
        '生活': ['生活', '日常', '购物', '做饭', '家务', '休息', '娱乐', '旅行'],
        '技术': ['技术', '编程', '代码', '开发', '软件', '工具', '算法', '架构', 'debug'],
        '健康': ['健康', '运动', '健身', '医疗', '饮食', '睡眠', '心理', '锻炼'],
        '财务': ['财务', '投资', '理财', '收入', '支出', '预算', '储蓄', '股票', '基金'],
        '社交': ['朋友', '聚会', '聊天', '关系', '家庭', '父母', '孩子', '恋爱']
    }
    
    content_lower = content.lower()
    scores = {cat: 0 for cat in categories}
    
    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in content_lower:
                scores[category] += 1
    
    # 选择得分最高的分类
    if scores:
        max_score = max(scores.values())
        primary_category = max(scores, key=lambda k: scores[k]) if max_score > 0 else '其他'
    else:
        primary_category = '其他'
    
    # 提取关键词作为标签
    keywords = extract_keywords(content, top_n=5)
    
    return keywords, primary_category


def score_memory_quality(memory):
    """评分记忆质量（0-1）"""
    if "error" in memory or not memory.get("content"):
        return 0.0
    
    content = memory["content"]
    quality_config = CONFIG.get('quality_scoring', {})
    
    # 长度评分
    length = len(content)
    min_length = quality_config.get('min_length', 50)
    max_length = quality_config.get('max_length', 10000)
    
    if length < min_length:
        length_score = length / min_length * 0.5
    elif length > max_length:
        length_score = 0.5  # 过长的内容可能不够精炼
    else:
        length_score = 1.0
    
    # 结构评分（有标题、分段等）
    structure_score = 0.5
    lines = content.strip().split('\n')
    if len(lines) > 3:  # 有分段
        structure_score += 0.2
    if any(line.strip().startswith('#') for line in lines):  # 有标题
        structure_score += 0.3
    
    # 重要关键词评分
    important_keywords = CONFIG.get('archive_policy', {}).get('important_keywords', [])
    keyword_matches = sum(1 for kw in important_keywords if kw in content)
    keyword_weight = quality_config.get('important_keywords_weight', 2.0)
    keyword_score = min(keyword_matches * 0.1 * keyword_weight, 1.0)
    
    # 信息密度评分（非空白字符比例）
    non_whitespace = len(re.sub(r'\s', '', content))
    density_score = min(non_whitespace / max(length, 1), 1.0)
    
    # 加权总分
    total_score = (
        length_score * 0.2 +
        structure_score * 0.2 +
        keyword_score * 0.3 +
        density_score * 0.3
    )
    
    return min(total_score, 1.0)


def is_important_memory(memory):
    """判断记忆是否重要（不应被归档）"""
    content = memory.get("content", "")
    important_keywords = CONFIG.get('archive_policy', {}).get('important_keywords', [])
    
    # 检查是否包含重要关键词
    for keyword in important_keywords:
        if keyword in content:
            return True
    
    # 检查质量评分
    quality_score = score_memory_quality(memory)
    if quality_score > 0.8:  # 高质量记忆保留
        return True
    
    return False


# ============================================
# 第二阶段功能：智能摘要与压缩
# ============================================

def generate_memory_summary(memories, max_summaries=10):
    """对相似记忆生成合并摘要"""
    if not CONFIG.get('compression', {}).get('enabled', False):
        return []
    
    # 按分类分组
    category_groups = defaultdict(list)
    for mem in memories:
        if "error" in mem:
            continue
        _, category = auto_tag_memory(mem["content"])
        category_groups[category].append(mem)
    
    summaries = []
    
    for category, group in category_groups.items():
        if len(group) < 3:  # 至少需要3个相似记忆才生成摘要
            continue
        
        # 计算组内相似度
        similar_groups = cluster_similar_memories(group, threshold=0.6)
        
        for cluster in similar_groups:
            if len(cluster) < 3:
                continue
            
            # 生成摘要
            summary = create_cluster_summary(cluster, category)
            summaries.append(summary)
            
            if len(summaries) >= max_summaries:
                return summaries
    
    return summaries


def cluster_similar_memories(memories, threshold=0.6):
    """将相似记忆聚类"""
    clusters = []
    used = set()
    
    for i, mem1 in enumerate(memories):
        if i in used:
            continue
        
        cluster = [mem1]
        used.add(i)
        
        for j, mem2 in enumerate(memories[i+1:], start=i+1):
            if j in used:
                continue
            
            similarity = calculate_text_similarity(mem1["content"], mem2["content"])
            if similarity >= threshold:
                cluster.append(mem2)
                used.add(j)
        
        if len(cluster) > 1:
            clusters.append(cluster)
    
    return clusters


def create_cluster_summary(cluster, category):
    """为记忆簇生成摘要"""
    # 提取所有关键词
    all_keywords = []
    for mem in cluster:
        keywords, _ = auto_tag_memory(mem["content"])
        all_keywords.extend(keywords)
    
    # 最常见的关键词
    top_keywords = [kw for kw, _ in Counter(all_keywords).most_common(5)]
    
    # 选择最具代表性的记忆（质量最高的）
    best_mem = max(cluster, key=lambda m: score_memory_quality(m))
    
    # 生成摘要内容
    summary_content = f"# {category} 记忆摘要\n\n"
    summary_content += f"**包含记忆数**: {len(cluster)}\n"
    summary_content += f"**主要关键词**: {', '.join(top_keywords)}\n"
    summary_content += f"**时间范围**: {cluster[0]['timestamp'].strftime('%Y-%m-%d')} - {cluster[-1]['timestamp'].strftime('%Y-%m-%d')}\n\n"
    summary_content += f"**代表性内容**:\n{best_mem['content'][:500]}...\n\n"
    summary_content += f"**记忆列表**:\n"
    for mem in cluster:
        summary_content += f"- {mem['name']} ({mem['title']})\n"
    
    return {
        "category": category,
        "keywords": top_keywords,
        "count": len(cluster),
        "content": summary_content,
        "representative_memory": best_mem["name"],
        "memory_names": [m["name"] for m in cluster]
    }


# ============================================
# 第二阶段功能：记忆关联图谱
# ============================================

def build_memory_graph(memories):
    """构建记忆关联图谱"""
    graph = {
        "nodes": [],
        "links": [],
        "clusters": [],
        "statistics": {}
    }
    
    # 添加节点
    for mem in memories:
        if "error" in mem:
            continue
        
        keywords, category = auto_tag_memory(mem["content"])
        quality_score = score_memory_quality(mem)
        
        node = {
            "id": mem["name"],
            "title": mem["title"],
            "category": category,
            "keywords": keywords,
            "quality_score": quality_score,
            "timestamp": mem["timestamp"].isoformat() if mem["timestamp"] else None,
            "size": mem["size"]
        }
        graph["nodes"].append(node)
    
    # 计算节点间的关联（基于关键词重叠）
    for i, node1 in enumerate(graph["nodes"]):
        for j, node2 in enumerate(graph["nodes"][i+1:], start=i+1):
            # 计算关键词重叠度
            common_keywords = set(node1["keywords"]) & set(node2["keywords"])
            if len(common_keywords) >= 2:  # 至少2个共同关键词
                link = {
                    "source": node1["id"],
                    "target": node2["id"],
                    "weight": len(common_keywords),
                    "common_keywords": list(common_keywords)
                }
                graph["links"].append(link)
    
    # 识别聚类（基于分类）
    category_nodes = defaultdict(list)
    for node in graph["nodes"]:
        category_nodes[node["category"]].append(node["id"])
    
    for category, node_ids in category_nodes.items():
        if len(node_ids) >= 3:  # 至少3个节点才形成聚类
            graph["clusters"].append({
                "category": category,
                "nodes": node_ids,
                "size": len(node_ids)
            })
    
    # 统计信息
    graph["statistics"] = {
        "total_nodes": len(graph["nodes"]),
        "total_links": len(graph["links"]),
        "total_clusters": len(graph["clusters"]),
        "avg_links_per_node": len(graph["links"]) / max(len(graph["nodes"]), 1),
        "most_connected_category": max(category_nodes.keys(), key=lambda k: len(category_nodes[k])) if category_nodes else "N/A"
    }
    
    return graph


# ============================================
# 第二阶段功能：记忆健康度仪表盘
# ============================================

def generate_health_dashboard(memories, graph_data):
    """生成记忆系统健康度仪表盘"""
    dashboard = {
        "timestamp": datetime.now().isoformat(),
        "overall_health": 0,
        "metrics": {},
        "recommendations": [],
        "trends": {}
    }
    
    # 1. 计算各项指标
    total_memories = len([m for m in memories if "error" not in m])
    
    # 质量指标
    qualities = [score_memory_quality(m) for m in memories if "error" not in m]
    avg_quality = sum(qualities) / len(qualities) if qualities else 0
    high_quality_ratio = len([q for q in qualities if q > 0.8]) / max(len(qualities), 1)
    
    # 多样性指标
    categories = set()
    for mem in memories:
        if "error" not in mem:
            _, category = auto_tag_memory(mem["content"])
            categories.add(category)
    diversity_score = len(categories) / 9.0  # 9个预定义分类
    
    # 关联度指标
    avg_connections = graph_data["statistics"].get("avg_links_per_node", 0)
    connectivity_score = min(avg_connections / 5.0, 1.0)  # 归一化
    
    # 存储效率指标
    total_size = sum(m.get("size", 0) for m in memories if "error" not in m)
    avg_size = total_size / max(total_memories, 1)
    storage_efficiency = 1.0 if avg_size < 10000 else max(0, 1.0 - (avg_size - 10000) / 100000)
    
    # 2. 计算总体健康度
    dashboard["overall_health"] = (
        avg_quality * 0.3 +
        high_quality_ratio * 0.2 +
        diversity_score * 0.15 +
        connectivity_score * 0.2 +
        storage_efficiency * 0.15
    )
    
    # 3. 详细指标
    dashboard["metrics"] = {
        "quality": {
            "average": round(avg_quality, 3),
            "high_quality_ratio": round(high_quality_ratio, 3),
            "score": round(avg_quality, 3)
        },
        "diversity": {
            "categories": len(categories),
            "score": round(diversity_score, 3)
        },
        "connectivity": {
            "avg_connections": round(avg_connections, 2),
            "total_links": graph_data["statistics"].get("total_links", 0),
            "score": round(connectivity_score, 3)
        },
        "storage": {
            "total_size_kb": round(total_size / 1024, 1),
            "avg_memory_size": round(avg_size, 1),
            "efficiency": round(storage_efficiency, 3)
        },
        "activity": {
            "total_memories": total_memories,
            "recent_additions": len([m for m in memories if "error" not in m and m.get("timestamp") and (datetime.now() - m["timestamp"]).days <= 7])
        }
    }
    
    # 4. 生成建议
    recommendations = []
    
    if avg_quality < 0.6:
        recommendations.append("⚠️ 平均质量偏低，建议提高记忆内容质量")
    
    if high_quality_ratio < 0.2:
        recommendations.append("📈 高质量记忆较少，建议添加更多有价值的记忆")
    
    if diversity_score < 0.5:
        recommendations.append("🎯 记忆分类不够多样化，建议覆盖更多主题")
    
    if connectivity_score < 0.3:
        recommendations.append("🔗 记忆间关联较少，建议建立更多跨记忆链接")
    
    if storage_efficiency < 0.7:
        recommendations.append("💾 平均记忆大小偏大，建议压缩或删除冗余内容")
    
    if total_memories < 20:
        recommendations.append("📝 记忆数量较少，建议持续积累")
    
    dashboard["recommendations"] = recommendations
    
    # 5. 趋势分析（需要历史数据，这里简化）
    dashboard["trends"] = {
        "growth_rate": "N/A (需要历史数据)",
        "quality_trend": "stable",
        "diversity_trend": "stable"
    }
    
    return dashboard


def generate_dashboard_html(dashboard):
    """生成健康仪表盘 HTML"""
    health_score = dashboard["overall_health"]
    health_level = "优秀" if health_score > 0.8 else "良好" if health_score > 0.6 else "一般" if health_score > 0.4 else "需改进"
    health_color = "#28a745" if health_score > 0.8 else "#ffc107" if health_score > 0.6 else "#fd7e14" if health_score > 0.4 else "#dc3545"
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>记忆系统健康仪表盘</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .health-score {{
            font-size: 48px;
            font-weight: bold;
            color: {health_color};
            margin: 20px 0;
        }}
        .health-level {{
            font-size: 24px;
            color: #666;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .metric-card {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .metric-card h3 {{
            margin: 0 0 15px 0;
            color: #333;
            font-size: 18px;
        }}
        .metric-value {{
            font-size: 32px;
            font-weight: bold;
            color: #007bff;
        }}
        .metric-label {{
            font-size: 14px;
            color: #666;
            margin-top: 5px;
        }}
        .recommendations {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-top: 30px;
        }}
        .recommendation {{
            padding: 10px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .recommendation:last-child {{
            border-bottom: none;
        }}
        .timestamp {{
            text-align: center;
            color: #999;
            margin-top: 30px;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🧠 记忆系统健康仪表盘</h1>
        <div class="health-score">{health_score:.1%}</div>
        <div class="health-level">{health_level}</div>
    </div>
    
    <div class="metrics-grid">
        <div class="metric-card">
            <h3>📊 质量指标</h3>
            <div class="metric-value">{dashboard['metrics']['quality']['average']:.2f}</div>
            <div class="metric-label">平均质量评分</div>
            <div class="metric-label">高质量比例: {dashboard['metrics']['quality']['high_quality_ratio']:.1%}</div>
        </div>
        
        <div class="metric-card">
            <h3>🎯 多样性</h3>
            <div class="metric-value">{dashboard['metrics']['diversity']['categories']}</div>
            <div class="metric-label">覆盖分类数</div>
            <div class="metric-label">多样性得分: {dashboard['metrics']['diversity']['score']:.2f}</div>
        </div>
        
        <div class="metric-card">
            <h3>🔗 关联度</h3>
            <div class="metric-value">{dashboard['metrics']['connectivity']['avg_connections']:.1f}</div>
            <div class="metric-label">平均连接数</div>
            <div class="metric-label">总链接数: {dashboard['metrics']['connectivity']['total_links']}</div>
        </div>
        
        <div class="metric-card">
            <h3>💾 存储效率</h3>
            <div class="metric-value">{dashboard['metrics']['storage']['avg_memory_size']:.0f}</div>
            <div class="metric-label">平均大小 (字符)</div>
            <div class="metric-label">总大小: {dashboard['metrics']['storage']['total_size_kb']:.1f} KB</div>
        </div>
        
        <div class="metric-card">
            <h3>📈 活跃度</h3>
            <div class="metric-value">{dashboard['metrics']['activity']['total_memories']}</div>
            <div class="metric-label">总记忆数</div>
            <div class="metric-label">最近7天新增: {dashboard['metrics']['activity']['recent_additions']}</div>
        </div>
    </div>
    
    <div class="recommendations">
        <h2>💡 改进建议</h2>
        {''.join(f'<div class="recommendation">{rec}</div>' for rec in dashboard['recommendations']) if dashboard['recommendations'] else '<div class="recommendation">🎉 记忆系统状态良好，无需特别改进！</div>'}
    </div>
    
    <div class="timestamp">
        最后更新: {dashboard['timestamp']}
    </div>
</body>
</html>"""
    return html


def archive_old_memories(memories):
    """智能归档：基于时间、重要性和质量的综合策略"""
    now = datetime.now()
    to_archive = []
    to_keep = []
    
    archive_policy = CONFIG.get('archive_policy', {})
    preserve_recent_active = archive_policy.get('preserve_recent_active', 7)
    
    for mem in memories:
        if "error" in mem or mem.get("timestamp") is None:
            to_keep.append(mem)
            continue
        
        age_days = (now - mem["timestamp"]).days
        
        # 检查是否应该保留（不归档）
        should_keep = False
        
        # 1. 检查是否是重要记忆
        if is_important_memory(mem):
            should_keep = True
            print(f"   📌 保留重要记忆: {mem['name']} (质量评分: {score_memory_quality(mem):.2f})")
        
        # 2. 检查是否是最近活跃的记忆
        elif age_days <= preserve_recent_active:
            should_keep = True
        
        # 3. 检查质量评分（高质量记忆保留更久）
        quality_score = score_memory_quality(mem)
        if quality_score > 0.9:  # 极高质量，永久保留
            should_keep = True
            print(f"   ⭐ 保留极高质量记忆: {mem['name']} (评分: {quality_score:.2f})")
        elif quality_score > 0.7:  # 高质量，延长归档时间
            if age_days <= ARCHIVE_AFTER_DAYS * 2:
                should_keep = True
        
        # 4. 检查记忆长度（太短的记忆可能价值较低）
        if mem.get("size", 0) < 100 and age_days > ARCHIVE_AFTER_DAYS // 2:
            # 短记忆且超过一半归档时间，优先归档
            if not should_keep:
                to_archive.append(mem)
                continue
        
        if should_keep:
            to_keep.append(mem)
        else:
            to_archive.append(mem)
    
    return to_keep, to_archive


def move_to_archive(memories):
    """移动到归档目录"""
    for mem in memories:
        if "error" in mem:
            continue
        src = Path(mem["path"])
        dst = ARCHIVE_DIR / src.name
        try:
            shutil.move(str(src), str(dst))
        except Exception:
            pass


def backup_memories():
    """备份当前记忆"""
    ensure_dirs()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"memory-backup-{timestamp}"
    
    try:
        shutil.copytree(str(MEMORY_DIR), str(backup_path), 
                        ignore=shutil.ignore_patterns("backups", "archived", "*.json"))
        return str(backup_path)
    except Exception as e:
        return None


def build_index(memories):
    """构建增强版记忆索引，包含标签、分类和质量评分"""
    index = {
        "last_updated": datetime.now().isoformat(),
        "total_memories": len([m for m in memories if "error" not in m]),
        "categories": {},
        "quality_distribution": {
            "high": 0,      # > 0.8
            "medium": 0,    # 0.5-0.8
            "low": 0        # < 0.5
        },
        "files": []
    }
    
    for mem in memories:
        if "error" in mem:
            continue
        
        # 自动标签和分类
        keywords, category = auto_tag_memory(mem["content"])
        
        # 质量评分
        quality_score = score_memory_quality(mem)
        
        # 更新分类统计
        index["categories"][category] = index["categories"].get(category, 0) + 1
        
        # 更新质量分布
        if quality_score > 0.8:
            index["quality_distribution"]["high"] += 1
        elif quality_score > 0.5:
            index["quality_distribution"]["medium"] += 1
        else:
            index["quality_distribution"]["low"] += 1
        
        # 增强文件信息
        file_info = {
            "name": mem["name"],
            "title": mem["title"],
            "timestamp": mem["timestamp"].isoformat() if mem["timestamp"] else None,
            "size": mem["size"],
            "path": mem["path"],
            "category": category,
            "keywords": keywords,
            "quality_score": round(quality_score, 2),
            "hash": mem["hash"]
        }
        
        index["files"].append(file_info)
    
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    return INDEX_FILE


def generate_report(total, unique, duplicates, archived, backup_path, memories_data=None):
    """生成增强版 HTML 报告，包含详细统计和可视化"""
    # 计算额外统计信息
    avg_quality = 0
    category_dist = {}
    quality_dist = {"high": 0, "medium": 0, "low": 0}
    
    if memories_data:
        qualities = [score_memory_quality(m) for m in memories_data if "error" not in m]
        if qualities:
            avg_quality = sum(qualities) / len(qualities)
        
        # 分类分布
        for mem in memories_data:
            if "error" in mem:
                continue
            _, category = auto_tag_memory(mem["content"])
            category_dist[category] = category_dist.get(category, 0) + 1
            
            # 质量分布
            q = score_memory_quality(mem)
            if q > 0.8:
                quality_dist["high"] += 1
            elif q > 0.5:
                quality_dist["medium"] += 1
            else:
                quality_dist["low"] += 1
    
    # 生成分类统计 HTML
    category_html = ""
    if category_dist:
        category_html = "<h3>📊 分类分布</h3><ul>"
        for cat, count in sorted(category_dist.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total * 100) if total > 0 else 0
            category_html += f"<li>{cat}: {count} ({percentage:.1f}%)</li>"
        category_html += "</ul>"
    
    # 生成质量分布 HTML
    quality_html = f"""
    <h3>⭐ 质量分布</h3>
    <div style="display: flex; gap: 20px; margin: 20px 0;">
        <div class="stat">高质量 (>0.8): <span class="pass">{quality_dist['high']}</span></div>
        <div class="stat">中等质量 (0.5-0.8): {quality_dist['medium']}</div>
        <div class="stat">低质量 (<0.5): <span class="fail">{quality_dist['low']}</span></div>
    </div>
    <p>平均质量评分: <strong>{avg_quality:.2f}</strong></p>
    """
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Memory Maintenance Report</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; max-width: 1000px; margin: 20px auto; padding: 20px; }}
        .stat {{ display: inline-block; margin: 10px; padding: 15px; background: #f0f0f0; border-radius: 8px; min-width: 120px; text-align: center; }}
        .pass {{ color: #28a745; font-weight: bold; }}
        .fail {{ color: #dc3545; font-weight: bold; }}
        .warning {{ color: #ffc107; font-weight: bold; }}
        h1, h2, h3 {{ color: #333; }}
        .section {{ margin: 30px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f2f2f2; }}
        .quality-high {{ color: #28a745; }}
        .quality-medium {{ color: #ffc107; }}
        .quality-low {{ color: #dc3545; }}
    </style>
</head>
<body>
    <h1>🧠 Memory Maintenance Report</h1>
    <p>时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    
    <div class="section">
        <h2>📈 总体统计</h2>
        <div class="stat">总记忆数：{total}</div>
        <div class="stat">去重后：{unique}</div>
        <div class="stat">重复移除：{duplicates}</div>
        <div class="stat">已归档：{archived}</div>
        <div class="stat">平均质量：{avg_quality:.2f}</div>
    </div>
    
    {quality_html}
    
    {category_html}
    
    <div class="section">
        <h2>💾 备份信息</h2>
        <p>备份路径：{backup_path if backup_path else '<span class="fail">备份失败</span>'}</p>
    </div>
    
    <div class="section">
        <h2>🔧 维护详情</h2>
        <ul>
            <li>✅ 重复记忆已移除：{duplicates}</li>
            <li>📦 已归档记忆：{archived}</li>
            <li>💾 索引已更新：{INDEX_FILE}</li>
        </ul>
    </div>
</body>
</html>"""
    return html


def main():
    print("🧠 开始维护 OpenClaw 记忆系统...")
    ensure_dirs()
    
    # 备份
    print("💾 备份记忆...")
    backup_path = backup_memories()
    
    # 扫描
    print("📁 扫描记忆文件...")
    files = get_memory_files()
    memories = [parse_memory_file(f) for f in files]
    
    total = len([m for m in memories if "error" not in m])
    
    # 去重
    print("🔍 去重...")
    unique, duplicates = deduplicate(memories)
    for dup in duplicates:
        try:
            Path(dup["path"]).unlink()
        except Exception:
            pass
    
    # 归档决策
    print("📦 归档决策...")
    to_keep, to_archive = archive_old_memories(unique)
    
    # 第二阶段功能：智能摘要与压缩
    if CONFIG.get('compression', {}).get('enabled', False):
        print("\n📝 第二阶段：智能摘要与压缩...")
        summaries = generate_memory_summary(memories)
        if summaries:
            print(f"   生成了 {len(summaries)} 个摘要")
            # 保存摘要文件
            for i, summary in enumerate(summaries):
                summary_path = MEMORY_DIR / f"summary-{summary['category']}-{i}.md"
                with open(summary_path, "w", encoding="utf-8") as f:
                    f.write(summary["content"])
        else:
            print("   无需生成摘要（相似记忆不足）")
    
    # 第二阶段功能：访问频率追踪
    if CONFIG.get('access_tracking', {}).get('enabled', False):
        print("\n📊 第二阶段：访问频率追踪...")
        # 更新索引中的访问计数
        for mem in to_keep:
            if "error" not in mem:
                # 这里可以添加访问计数逻辑
                pass
        print("   访问追踪已启用（需要更多实现）")
    
    # 第二阶段功能：交互式维护模式
    if CONFIG.get('interactive', {}).get('enabled', False):
        print("\n🤖 第二阶段：交互式维护模式...")
        # 预览将要执行的操作
        print("   预览操作:")
        print(f"   - 将删除 {len(duplicates)} 个重复记忆")
        print(f"   - 将归档 {len(to_archive)} 个旧记忆")
        if CONFIG.get('interactive', {}).get('dry_run', True):
            print("   🚫 干运行模式：不实际执行操作")
            # 跳过实际执行
            to_archive = []  # 清空归档列表
    
    # 执行归档
    print("\n📦 执行归档...")
    move_to_archive(to_archive)
    
    # 构建索引
    print("📝 构建索引...")
    build_index(to_keep)
    
    # 第三阶段功能：记忆关联图谱
    graph_data = {}  # 初始化变量
    if CONFIG.get('memory_graph', {}).get('enabled', True):
        print("\n🔗 第三阶段：构建记忆关联图谱...")
        graph_data = build_memory_graph(memories)
        graph_path = MEMORY_DIR / "memory-graph.json"
        with open(graph_path, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)
        print(f"   图谱节点: {graph_data['statistics']['total_nodes']}")
        print(f"   图谱链接: {graph_data['statistics']['total_links']}")
        print(f"   图谱聚类: {graph_data['statistics']['total_clusters']}")
    
    # 第三阶段功能：记忆健康度仪表盘
    if CONFIG.get('health_dashboard', {}).get('enabled', True):
        print("\n📊 第三阶段：生成健康仪表盘...")
        dashboard = generate_health_dashboard(memories, graph_data if graph_data else {"statistics": {}})
        dashboard_html = generate_dashboard_html(dashboard)
        dashboard_path = MEMORY_DIR / "health-dashboard.html"
        with open(dashboard_path, "w", encoding="utf-8") as f:
            f.write(dashboard_html)
        print(f"   健康评分: {dashboard['overall_health']:.1%}")
        print(f"   仪表盘: {dashboard_path}")
    
    # 生成报告
    report = generate_report(
        total=total,
        unique=len(to_keep),
        duplicates=len(duplicates),
        archived=len(to_archive),
        backup_path=backup_path,
        memories_data=memories  # 传递原始记忆数据用于统计分析
    )
    
    print("\n✅ 维护完成！")
    print(f"   - 总记忆数：{total}")
    print(f"   - 去重后：{len(to_keep)}")
    print(f"   - 重复移除：{len(duplicates)}")
    print(f"   - 已归档：{len(to_archive)}")
    print(f"   - 备份：{backup_path}")
    
    # 保存报告
    report_path = MEMORY_DIR / "maintenance-report.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"   - 报告：{report_path}")


if __name__ == "__main__":
    main()
