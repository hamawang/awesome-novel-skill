#!/usr/bin/env python3
"""
同步项目空间的 agent/skill/知识库到最新版本

用法: python tools/sync-project.py <project-path>

从 NOVEL_SKILL_HOME（或本仓库）复制最新的 agent 定义、技能和知识库
到已有项目目录，不触碰 settings/ volumes/ chapters/ archives/ prompts/ story.md。

适用于：
- 更新已有项目到最新 agent/skill/知识库版本
- 新增知识库（scene-craft/plot-craft 等）后同步到项目
"""

import sys
import os
import shutil
from pathlib import Path

# 强制 UTF-8 编码，避免 Windows 终端中文乱码
for s in (sys.stdin, sys.stdout, sys.stderr):
    try:
        s.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


SKILL_HOME = Path(__file__).parent.parent
AGENT_DIR = SKILL_HOME / "agents"
SKILL_DIR = SKILL_HOME / "skills"
KNOWLEDGE_DIR = SKILL_HOME / "knowledge"


def main():
    if "-h" in sys.argv or "--help" in sys.argv or len(sys.argv) < 2:
        print(__doc__.strip())
        return

    project_path = Path(sys.argv[1]).resolve()

    if not project_path.exists():
        print(f"错误: 路径不存在: {project_path}")
        sys.exit(1)

    status_file = project_path / ".agent" / "status.md"
    if not status_file.exists():
        print(f"错误: {project_path} 不是有效的小说项目（缺少 .agent/status.md）")
        sys.exit(1)

    print(f"项目: {project_path}")
    print(f"来源: {SKILL_HOME}")
    print()

    changes = []

    # 1. 同步 agent 定义
    changes.append(sync_agents(project_path))
    # 2. 同步 skill 文件
    changes.append(sync_skills(project_path))
    # 3. 同步知识库
    changes.append(sync_knowledge(project_path))

    total = sum(c for c in changes if c > 0)
    print(f"\n完成。共同步 {total} 个文件。")

    # 同步后提示重启 agent
    if total > 0:
        print("提示: agent/skill 有更新，下次写作时生效。新建项目直接通过 init.py 初始化即可。")


def sync_agents(project_path: Path) -> int:
    """同步 agent 定义到项目 .claude/agents/"""
    target = project_path / ".claude" / "agents"
    target.mkdir(parents=True, exist_ok=True)

    if not AGENT_DIR.exists():
        print("  [!] agents 源目录不存在，跳过")
        return 0

    count = _sync_dir(AGENT_DIR, target, "*.md")
    if count > 0:
        print(f"  [OK] agent 定义: {count} 个文件已更新")
    else:
        print(f"  [i] agent 定义: 已是最新")
    return count


def sync_skills(project_path: Path) -> int:
    """同步 skill 文件到项目 .claude/skills/"""
    target = project_path / ".claude" / "skills"
    target.mkdir(parents=True, exist_ok=True)

    if not SKILL_DIR.exists():
        print("  [!] skills 源目录不存在，跳过")
        return 0

    count = _sync_dir(SKILL_DIR, target, "*.md")
    if count > 0:
        print(f"  [OK] skill 文件: {count} 个文件已更新")
    else:
        print(f"  [i] skill 文件: 已是最新")
    return count


def sync_knowledge(project_path: Path) -> int:
    """同步知识库到项目 .claude/knowledge/"""
    target = project_path / ".claude" / "knowledge"
    target.mkdir(parents=True, exist_ok=True)

    if not KNOWLEDGE_DIR.exists():
        print("  [!] knowledge 源目录不存在，跳过")
        return 0

    count = 0

    # 同步顶层知识文件（README.md, index.md）
    for f in KNOWLEDGE_DIR.glob("*.md"):
        if _sync_file(f, target / f.name):
            count += 1

    # 同步子目录（scene-craft/, plot-craft/, format-specs/ 等）
    for subdir in KNOWLEDGE_DIR.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("."):
            sub_target = target / subdir.name
            sub_target.mkdir(parents=True, exist_ok=True)
            count += _sync_dir(subdir, sub_target, "*.md")

    if count > 0:
        print(f"  [OK] 知识库: {count} 个文件已更新")
    else:
        print(f"  [i] 知识库: 已是最新")

    return count


def _sync_dir(src: Path, dst: Path, pattern: str) -> int:
    """同步目录，返回更新的文件数"""
    count = 0
    for item in sorted(src.rglob(pattern)):
        if item.name == ".gitkeep":
            continue
        rel = item.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if _sync_file(item, target):
            count += 1
    return count


def _sync_file(src: Path, dst: Path) -> bool:
    """同步单个文件，内容相同则跳过，返回 True 表示有更新"""
    if dst.exists() and dst.read_bytes() == src.read_bytes():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


if __name__ == "__main__":
    main()
