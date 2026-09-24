#!/usr/bin/env python3
"""Run a fictional seven-day checklist in a disposable workspace."""

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from career import CHECKS, Workflow
from workbench.daily import DailyStore


class Clock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


def show(day, note, daily):
    view = daily.snapshot("Asia/Shanghai")
    print(json.dumps({"day": day, "today": view["today"], "note": note,
                      "tasks": [{"id": task["id"], "state": task["state"],
                                 "source_id": task["source_id"],
                                 "due_verified": task["due_verified"],
                                 "carryover_reason": task["carryover_reason"]}
                                for task in view["tasks"]]}, ensure_ascii=False))


def main():
    base = datetime.now(ZoneInfo("Asia/Shanghai")).replace(second=0, microsecond=0)
    clock = Clock(base)
    with tempfile.TemporaryDirectory(prefix="fictional-daily-") as directory:
        flow = Workflow(directory)
        daily = DailyStore(directory, clock)
        try:
            for name in ("A", "B"):
                with flow.db:
                    flow.add({"id": f"DEMO-JOB-{name}", "company": f"虚构{name}公司",
                              "role": f"虚构{name}岗位", "family": "operations",
                              "url": f"https://example.com/jobs/fictional-{name.lower()}"})

            def task(task_id, title, kind, source_kind, source_id, day, due_at=None, due_verified=False):
                return {"id": task_id, "title": title, "kind": kind,
                        "source_kind": source_kind, "source_id": source_id,
                        "reason": "虚构学生为秋招安排的下一步",
                        "scheduled_at": (base + timedelta(days=day, hours=1)).isoformat(),
                        "due_at": due_at, "due_verified": due_verified}

            def schedule(item, event):
                daily.command("schedule", event, item["id"], {"task": item}, at=base.isoformat())

            def complete(task_id, event, evidence):
                daily.command("complete", event, task_id, {"evidence": evidence})

            def job_seq(job_id, kind):
                return flow.db.execute("SELECT seq FROM events WHERE job=? AND kind=? ORDER BY seq DESC LIMIT 1",
                                       (job_id, kind)).fetchone()[0]

            schedule(task("DEMO-VERIFY-A", "核验虚构 A 岗", "verify_job", "job", "DEMO-JOB-A", 0), "E-01")
            schedule(task("DEMO-TALK", "参加虚构宣讲", "attend_event", "event", "DEMO-TALK-1", 1), "E-02")
            schedule(task("DEMO-VERIFY-B", "核验虚构 B 岗未知截止", "verify_job", "job", "DEMO-JOB-B", 2), "E-03")
            show(1, "安排两岗位核验和一场宣讲；B 岗截止未知", daily)

            clock.value = base + timedelta(days=1, hours=2)
            checks = {key: {"result": "pass", "evidence": "虚构页面条件"} for key in CHECKS}
            with flow.db:
                flow.assess("DEMO-JOB-A", {"checked_at": datetime.now(timezone.utc).isoformat(),
                                           "source": "https://example.com/jobs/fictional-a", "checks": checks})
            complete("DEMO-VERIFY-A", "E-04", {"job_event_seq": job_seq("DEMO-JOB-A", "assessed")})
            complete("DEMO-TALK", "E-05", {"attendance_ref": "虚构宣讲笔记",
                                                 "observed_at": clock.value.isoformat()})
            show(2, "A 岗核验与宣讲已记；投递仍未发生", daily)

            clock.value = base + timedelta(days=2, hours=2)
            unknown = dict(checks)
            unknown["cohort"] = {"result": "unknown"}
            with flow.db:
                flow.assess("DEMO-JOB-B", {"checked_at": datetime.now(timezone.utc).isoformat(),
                                           "source": "https://example.com/jobs/fictional-b", "checks": unknown})
            complete("DEMO-VERIFY-B", "E-06", {"job_event_seq": job_seq("DEMO-JOB-B", "assessed")})
            schedule(task("DEMO-PREP-A", "准备虚构 A 岗材料", "prepare_materials", "job", "DEMO-JOB-A", 2), "E-07")
            show(3, "B 岗届别和截止保留未知；A 岗准备材料", daily)

            clock.value = base + timedelta(days=3, hours=2)
            resume = Path(directory) / "fictional-resume.md"
            resume.write_text("虚构材料；不含真人经历", encoding="utf-8")
            with flow.db:
                flow.prepare("DEMO-JOB-A", {"resume_path": str(resume),
                                            "claims_evidence": ["虚构练习资料"]})
            complete("DEMO-PREP-A", "E-08", {"job_event_seq": job_seq("DEMO-JOB-A", "prepared")})
            schedule(task("DEMO-APPROVE-A", "本人核对虚构材料", "approve_materials", "job", "DEMO-JOB-A", 3), "E-09")
            with flow.db:
                flow.approve("DEMO-JOB-A", True)
            complete("DEMO-APPROVE-A", "E-10", {"job_event_seq": job_seq("DEMO-JOB-A", "approved")})
            show(4, "材料已准备并确认，岗位尚未 submitted", daily)

            clock.value = base + timedelta(days=4, hours=2)
            schedule(task("DEMO-APPLY-A", "原站申请虚构 A 岗", "apply_job", "job", "DEMO-JOB-A", 4), "E-11")
            opened_only = False
            try:
                complete("DEMO-APPLY-A", "E-OPENED-ONLY", {"opened_url": "https://example.com/jobs/fictional-a"})
            except ValueError:
                opened_only = True
            assert opened_only and flow.get("DEMO-JOB-A")["state"] == "approved"
            with flow.db:
                flow.record("DEMO-JOB-A", "submitted", "虚构回执位置；没有实际申请")
            complete("DEMO-APPLY-A", "E-12", {"job_event_seq": job_seq("DEMO-JOB-A", "submitted")})
            show(5, "打开原站未完成任务；仅登记虚构回执后才完成", daily)

            clock.value = base + timedelta(days=5, hours=2)
            with flow.db:
                flow.record("DEMO-JOB-A", "interview", "虚构面试邀请")
            schedule(task("DEMO-INTERVIEW-A", "准备虚构面试", "prepare_interview", "event", "DEMO-INTERVIEW-1", 5), "E-13")
            complete("DEMO-INTERVIEW-A", "E-14", {"notes_ref": "虚构面试笔记"})
            schedule(task("DEMO-RECHECK-B", "补查虚构 B 岗届别", "verify_job", "job", "DEMO-JOB-B", 5), "E-15")
            daily.command("block", "E-16", "DEMO-RECHECK-B", {"reason": "原岗位页未明确届别，等待人工核对"})
            show(6, "A 岗进入虚构面试；B 岗补查被阻塞", daily)

            clock.value = base + timedelta(days=6, hours=2)
            show(7, "B 岗未完任务保留原日期与原因；没有自动拒绝或虚构截止", daily)
        finally:
            daily.close()
            flow.db.close()


if __name__ == "__main__":
    main()
