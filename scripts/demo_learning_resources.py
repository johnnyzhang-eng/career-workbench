#!/usr/bin/env python3
"""Create two fictional jobs and confirmed skill excerpts in a private workspace."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from career import Workflow  # noqa: E402
from workbench.learning import LearningStore  # noqa: E402


JOBS = (
    {"id": "FICTIONAL-DATA", "company": "虚构青禾公司", "role": "虚构数据分析实习",
     "family": "analytics", "url": "https://example.com/jobs/fictional-data"},
    {"id": "FICTIONAL-ENGINEERING", "company": "虚构星河公司", "role": "虚构数据工程实习",
     "family": "engineering", "url": "https://example.com/jobs/fictional-engineering"},
)
REQUIREMENTS = (
    ("FICTIONAL-DATA", "sql-foundations", "虚构 JD：能使用 SQL 查询和筛选数据。", "confirmed", "demo-sql-a"),
    ("FICTIONAL-DATA", "python-control-flow", "虚构 JD：能用 Python 控制流处理数据。", "confirmed", "demo-python"),
    ("FICTIONAL-ENGINEERING", "sql-foundations", "虚构 JD：具备基础 SQL 查询能力。", "confirmed", "demo-sql-b"),
    ("FICTIONAL-ENGINEERING", "algorithms-foundations", "虚构 JD：理解基本算法步骤。", "confirmed", "demo-algorithm"),
    ("FICTIONAL-ENGINEERING", "stream-processing", "虚构 JD：接触流处理；具体深度尚待核验。", "needs_review", "demo-stream"),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default="private/learning-demo")
    args = parser.parse_args()
    workspace = (ROOT / args.workspace).resolve()
    if not workspace.is_relative_to(ROOT / "private"):
        parser.error("演示工作区只能放在仓库 private/ 下")
    flow = Workflow(workspace)
    try:
        with flow.db:
            for job in JOBS:
                if not flow.db.execute("SELECT 1 FROM jobs WHERE id=?", (job["id"],)).fetchone():
                    flow.add(job)
    finally:
        flow.db.close()
    with LearningStore(workspace) as learning:
        learning.set_profile({"operation_id": "demo-profile", "language": "any",
                              "known_skills": ["python-basics"]})
        for job_id, skill_id, excerpt, status, operation in REQUIREMENTS:
            learning.add_requirement({"operation_id": operation, "job_id": job_id,
                                      "skill_id": skill_id, "excerpt": excerpt,
                                      "source_url": next(job["url"] for job in JOBS if job["id"] == job_id),
                                      "source_checked_at": "2026-09-25T00:00:00+08:00",
                                      "confirmation_status": status})
        state = learning.state()
    print(json.dumps({"fictional": True, "workspace": str(workspace),
                      "jobs": len(state["jobs"]), "requirements": len(state["requirements"]),
                      "next": "python3 scripts/serve_learning_companion.py --workspace " + args.workspace},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
