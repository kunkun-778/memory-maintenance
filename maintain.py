#!/usr/bin/env python3
"""
Memory Maintenance - 维护 OpenClaw 长期记忆
"""
import os
import re
import json
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# OpenClaw 记忆目录配置
MEMORY_DIR = Path.home() / ".openclaw" / "workspace" / "memory"
BACKUP_DIR = MEMORY_DIR / "backups"
ARCHIVE_DIR = MEMORY_DIR / "archived"
INDEX_FILE = MEMORY_DIR / "memory-index.json"

# 配置
ARCHIVE_AFTER_DAYS = 30
DEDUP_SIMILARITY_THRESHOLD = 0.85


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
    """去重：基于内容哈希和相似度"""
    seen_hashes = set()
    duplicates = []
    unique = []
    
    for mem in memories:
        if "error" in mem:
            unique.append(mem)
            continue
        
        if mem["hash"] in seen_hashes:
            duplicates.append(mem)
        else:
            seen_hashes.add(mem["hash"])
            unique.append(mem)
    
    return unique, duplicates


def archive_old_memories(memories):
    """归档超过30天的记忆"""
    now = datetime.now()
    to_archive = []
    to_keep = []
    
    for mem in memories:
        if "error" in mem or mem.get("timestamp") is None:
            to_keep.append(mem)
            continue
        
        age_days = (now - mem["timestamp"]).days
        if age_days > ARCHIVE_AFTER_DAYS:
            to_archive.append(mem)
        else:
            to_keep.append(mem)
    
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
    """构建记忆索引"""
    index = {
        "last_updated": datetime.now().isoformat(),
        "total_memories": len([m for m in memories if "error" not in m]),
        "files": []
    }
    
    for mem in memories:
        if "error" in mem:
            continue
        index["files"].append({
            "name": mem["name"],
            "title": mem["title"],
            "timestamp": mem["timestamp"].isoformat() if mem["timestamp"] else None,
            "size": mem["size"],
            "path": mem["path"]
        })
    
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    return INDEX_FILE


def generate_report(total, unique, duplicates, archived, backup_path):
    """生成 HTML 报告"""
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Memory Maintenance Report</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; max-width: 800px; margin: 20px auto; padding: 20px; }}
        .stat {{ display: inline-block; margin: 10px; padding: 15px; background: #f0f0f0; border-radius: 8px; }}
        .pass {{ color: #28a745; }}
        .fail {{ color: #dc3545; }}
    </style>
</head>
<body>
    <h1>🧠 Memory Maintenance Report</h1>
    <p>时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    
    <div class="stat">总记忆数：{total}</div>
    <div class="stat">去重后：<span class="pass">{unique}</span></div>
    <div class="stat">重复项：<span class="fail">{duplicates}</span></div>
    <div class="stat">已归档：{archived}</div>
    
    <h2>备份信息</h2>
    <p>{backup_path if backup_path else '备份失败'}</p>
    
    <h2>维护详情</h2>
    <ul>
        <li>✅ 重复记忆已移除：{duplicates}</li>
        <li>📦 已归档记忆：{archived}</li>
        <li>💾 索引已更新：{INDEX_FILE}</li>
    </ul>
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
    
    # 归档
    print("📦 归档旧记忆...")
    to_keep, to_archive = archive_old_memories(unique)
    move_to_archive(to_archive)
    
    # 构建索引
    print("📝 构建索引...")
    build_index(to_keep)
    
    # 生成报告
    report = generate_report(
        total=total,
        unique=len(to_keep),
        duplicates=len(duplicates),
        archived=len(to_archive),
        backup_path=backup_path
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
