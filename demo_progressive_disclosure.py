"""渐进式披露机制演示脚本。

演示 Claude Code 风格的 skill 触发方式：
1. 显式触发：/skill-name
2. 隐式触发：关键词匹配
3. 帮助信息：/help
"""

from pathlib import Path

from agent_framework.skills.loader import SkillLoader
from agent_framework.skills.router import SkillRouter


def main():
    print("=" * 60)
    print("渐进式披露机制演示")
    print("=" * 60)

    # 加载 skills
    loader = SkillLoader()
    router = SkillRouter()

    # 加载 research agent 的 skills
    skills_dir = Path("agent_framework/agents/research/skills")
    skills = []
    for skill_file in skills_dir.rglob("SKILL.md"):
        skill = loader.load(skill_file)
        skills.append(skill)

    # 加载 fea agent 的 skills
    fea_skills_dir = Path("agent_framework/agents/fea/skills")
    for skill_file in fea_skills_dir.rglob("SKILL.md"):
        skill = loader.load(skill_file)
        skills.append(skill)

    print(f"\n已加载 {len(skills)} 个 skill：")
    for skill in skills:
        cmd = skill.slash_command if skill.slash_command else skill.name
        print(f"  - /{cmd}: {skill.description[:50]}...")

    # ==================== 场景1：显式触发 ====================
    print("\n" + "=" * 60)
    print("场景1：显式 slash command 触发")
    print("=" * 60)

    test_cases = [
        "/search 搜索Python最新版本",
        "/fea 分析STP文件",
        "/help",
    ]

    for user_input in test_cases:
        print(f"\n用户输入：{user_input}")
        result = router.route(user_input, skills)
        if result:
            for skill in result:
                print(f"  -> 激活 skill：{skill.name} (score={skill.routing_score})")
        else:
            print("  -> 返回帮助信息或无匹配")

    # ==================== 场景2：隐式触发 ====================
    print("\n" + "=" * 60)
    print("场景2：隐式关键词触发")
    print("=" * 60)

    test_cases = [
        "帮我搜索一下React的最新文档",
        "我想做静力学分析",
        "查一下今天的新闻",
    ]

    for user_input in test_cases:
        print(f"\n用户输入：{user_input}")
        result = router.route(user_input, skills)
        if result:
            for skill in result:
                print(f"  -> 激活 skill：{skill.name} (score={skill.routing_score})")
        else:
            print("  -> 无匹配 skill")

    # ==================== 场景3：帮助信息 ====================
    print("\n" + "=" * 60)
    print("场景3：获取帮助信息")
    print("=" * 60)

    help_text = router.get_available_skills_help(skills)
    print(help_text)

    # ==================== 总结 ====================
    print("\n" + "=" * 60)
    print("渐进式披露机制总结")
    print("=" * 60)
    print("1. 显式触发：用户输入 /skill-name 明确激活 skill")
    print("   - 优点：用户明确知道要做什么，不会误触发")
    print("   - 缺点：需要用户知道 skill 的名称")
    print()
    print("2. 隐式触发：基于关键词自动匹配")
    print("   - 优点：用户可以用自然语言，不需要知道 skill 名称")
    print("   - 缺点：可能误触发或漏触发")
    print()
    print("3. 帮助信息：/help 查看可用 skill")
    print("   - 帮助用户发现可用功能")
    print("   - 列出所有 skill 的 slash command")
    print()
    print("这种设计仿照了 Claude Code 的渐进式披露方式：")
    print("- 用户可以明确请求特定功能")
    print("- 系统也可以根据上下文智能推断")
    print("- 帮助用户发现更多可用功能")


if __name__ == "__main__":
    main()
