"""Small, reviewed chapter catalog; no scraping or copied course content."""

import hashlib
import json
from datetime import date


SKILLS = {
    "sql-foundations": {"version": 1, "title": "SQL 基础查询", "meaning": "能解释并写出 SELECT、WHERE 与排序查询"},
    "python-control-flow": {"version": 1, "title": "Python 控制流", "meaning": "能独立使用条件、循环和函数处理小任务"},
    "algorithms-foundations": {"version": 1, "title": "算法入门", "meaning": "能解释算法步骤与基本效率取舍"},
    "stream-processing": {"version": 1, "title": "流处理", "meaning": "理解流式数据处理的基本概念与工具"},
}

# Checked against the provider's own chapter page on 2026-09-25. A page being
# readable then is not a guarantee that the material or access stays unchanged.
RESOURCES = (
    {"id": "postgres-select", "skill_id": "sql-foundations", "provider": "PostgreSQL",
     "title": "2.5 Querying a Table", "url": "https://www.postgresql.org/docs/current/tutorial-select.html",
     "language": "en", "format": "official tutorial", "level": "beginner",
     "objective": "练习 SELECT、WHERE、ORDER BY", "prerequisites": [], "access": "open web page",
     "checked_on": "2026-09-25", "verification": "page_checked",
     "link_basis": "PostgreSQL 官方教程第 2.5 节；覆盖基础表查询。"},
    {"id": "sqlite-select", "skill_id": "sql-foundations", "provider": "SQLite",
     "title": "SELECT statement reference", "url": "https://www.sqlite.org/lang_select.html",
     "language": "en", "format": "official reference", "level": "intermediate",
     "objective": "查阅 SELECT 的语法和执行语义", "prerequisites": [], "access": "open web page",
     "checked_on": "2026-09-25", "verification": "page_checked",
     "link_basis": "SQLite 官方 SELECT 参考；作为查询语法的替代资料。"},
    {"id": "python-control", "skill_id": "python-control-flow", "provider": "Python Software Foundation",
     "title": "4. More Control Flow Tools", "url": "https://docs.python.org/3/tutorial/controlflow.html",
     "language": "en", "format": "official tutorial", "level": "beginner",
     "objective": "学习 if、for、while 和函数", "prerequisites": ["python-basics"],
     "access": "open web page", "checked_on": "2026-09-25", "verification": "page_checked",
     "link_basis": "Python 官方教程第 4 章；对应控制流要求。"},
    {"id": "python-intro", "skill_id": "python-control-flow", "provider": "Python Software Foundation",
     "title": "3. An Informal Introduction to Python", "url": "https://docs.python.org/3/tutorial/introduction.html",
     "language": "en", "format": "official tutorial", "level": "beginner",
     "objective": "先熟悉变量、数值和基本语法", "prerequisites": [],
     "access": "open web page", "checked_on": "2026-09-25", "verification": "page_checked",
     "link_basis": "Python 官方教程第 3 章；当前置基础未知时先看。"},
    {"id": "mit-algorithm-lecture", "skill_id": "algorithms-foundations", "provider": "MIT OpenCourseWare",
     "title": "Lecture 1: Algorithmic Thinking, Peak Finding",
     "url": "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/resources/lecture-1-algorithmic-thinking-peak-finding/",
     "language": "en", "format": "official open lecture", "level": "intermediate",
     "objective": "用峰值问题理解算法设计与效率", "prerequisites": ["python-basics", "discrete-math"],
     "access": "open lecture page; video or notes availability may vary",
     "checked_on": "2026-09-25", "verification": "page_checked",
     "link_basis": "MIT OCW 6.006 讲座 1；课程大纲明确要求 Python 与离散数学基础。"},
    {"id": "khan-algorithm-intro", "skill_id": "algorithms-foundations", "provider": "Khan Academy",
     "title": "What is an algorithm and why should you care?",
     "url": "https://www.khanacademy.org/computing/computer-science/algorithms/intro-to-algorithms/v/what-are-algorithms",
     "language": "en", "format": "official provider video", "level": "beginner",
     "objective": "先理解算法是可复现的步骤", "prerequisites": [],
     "access": "page may require a supported browser; access not verified in-app",
     "checked_on": "2026-09-25", "verification": "access_needs_recheck",
     "link_basis": "Khan Academy 的具体入门视频；站点给当前检查浏览器返回兼容提示，访问需本人重验。"},
)

RESOURCE_BY_ID = {resource["id"]: resource for resource in RESOURCES}


def resource_revision(resource):
    """Bind a learning action to chapter content, not only its catalog ID."""
    fields = ("id", "skill_id", "provider", "title", "url", "language", "format",
              "level", "objective", "prerequisites", "access", "link_basis")
    payload = {field: resource[field] for field in fields}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def recommend(requirement, profile, issues=(), today=None):
    """Deterministic rule recommendation with explicit review and no-match states."""
    if requirement["confirmation_status"] != "confirmed":
        return {"status": "needs_review", "reason": "岗位技能映射尚未经本人确认", "items": []}
    candidates = [resource for resource in RESOURCE_BY_ID.values()
                  if resource["skill_id"] == requirement["skill_id"]]
    if not candidates:
        return {"status": "no_match", "reason": "目录中没有与该技能绑定的章节；请人工补录或稍后核验", "items": []}
    known = set(profile["known_skills"])
    issue_ids = set(issues)
    today = today or date.today()
    items = []
    for resource in candidates:
        missing = [skill for skill in resource["prerequisites"] if skill not in known]
        language_mismatch = profile["language"] not in {"any", resource["language"]}
        access_status = ("access_needs_recheck" if resource["id"] in issue_ids
                         or resource["verification"] == "access_needs_recheck"
                         or (today - date.fromisoformat(resource["checked_on"])).days > 60
                         else "page_checked")
        items.append({**resource, "content_revision": resource_revision(resource),
                      "missing_prerequisites": missing,
                      "language_mismatch": language_mismatch, "access_status": access_status,
                      "reason": "规则推荐：要求片段绑定技能 " + SKILLS[requirement["skill_id"]]["title"]
                                + "；" + resource["link_basis"]})
    items.sort(key=lambda item: (bool(item["missing_prerequisites"]), item["language_mismatch"],
                                 item["access_status"] != "page_checked", item["level"] != "beginner"))
    status = ("ready" if any(not item["missing_prerequisites"] and not item["language_mismatch"]
                              and item["access_status"] == "page_checked" for item in items)
              else "needs_review")
    reason = ("可从已核对章节开始，替代章节仍需看适用条件" if status == "ready" else
              "语言、前置或访问状态未满足；先看入门替代章节或人工补录")
    return {"status": status, "reason": reason, "items": items}
