#!/usr/bin/env python3
"""Offline job-search workflow. No network, model calls, or application sending."""
import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHECKS = ("city", "degree", "cohort", "experience", "open", "hard_requirements", "contract")
PRE = {"discovered", "hold", "excluded", "eligible", "prepared", "approved"}
ACTIVE = {"submitted", "responded", "assessment", "interview"}
OUTCOMES = ACTIVE | {"offer", "rejected", "withdrawn"}


def now():
    return datetime.now(timezone.utc).isoformat()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def fresh(assessment):
    value = assessment.get("checked_at")
    require(nonempty(value), "核验需要带时区的 checked_at")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(stamp.tzinfo is not None, "核验时间必须含时区")
    age = datetime.now(timezone.utc) - stamp
    require(timedelta(minutes=-5) <= age <= timedelta(hours=72), "核验已过期或来自未来，请重新核验")


class Workflow:
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(self.workspace / "state.sqlite3")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, job TEXT NOT NULL,
                at TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS learning(id INTEGER PRIMARY KEY, job TEXT NOT NULL,
                payload TEXT NOT NULL);
        """)
        self.db.commit()

    def get(self, job_id):
        row = self.db.execute("SELECT payload FROM jobs WHERE id=?", (job_id,)).fetchone()
        require(row is not None, "岗位不存在")
        return json.loads(row[0])

    def save(self, job, kind, evidence):
        payload = json.dumps(job, ensure_ascii=False)
        self.db.execute("INSERT INTO jobs VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                        (job["id"], payload))
        self.db.execute("INSERT INTO events(job,at,kind,payload) VALUES(?,?,?,?)",
                        (job["id"], now(), kind, json.dumps(evidence, ensure_ascii=False)))
        return job

    def add(self, data):
        require(isinstance(data, dict), "岗位必须是 JSON 对象")
        for key in ("id", "company", "role", "family", "url"):
            require(nonempty(data.get(key)), f"缺少 {key}")
        require(re.fullmatch(r"[A-Za-z0-9_-]{1,80}", data["id"]), "岗位 ID 只允许字母数字下划线或连字符")
        require(data["url"].startswith(("https://", "http://")), "需要具体岗位 URL")
        require(not self.db.execute("SELECT 1 FROM jobs WHERE id=?", (data["id"],)).fetchone(), "重复 ID，不覆盖已有记录")
        for (payload,) in self.db.execute("SELECT payload FROM jobs"):
            require(json.loads(payload)["url"].rstrip("/") != data["url"].rstrip("/"), "相同 URL 已入库，请先核对是否同一岗位")
        job = {k: data.get(k) for k in ("id", "company", "role", "family", "url", "city", "channel", "client_brand", "contract_entity")}
        job.update(state="discovered", created_at=now())
        return self.save(job, "discovered", job.copy())

    def assess(self, job_id, assessment):
        job = self.get(job_id)
        require(job["state"] in PRE, "已提交岗位不能通过重验倒退状态")
        require(isinstance(assessment, dict), "核验必须是对象")
        fresh(assessment)
        require(nonempty(assessment.get("source")), "需要核验来源")
        checks = assessment.get("checks", {})
        require(isinstance(checks, dict), "checks 必须是对象")
        results = []
        for key in CHECKS:
            item = checks.get(key, {})
            require(isinstance(item, dict), f"{key} 必须是对象")
            result = item.get("result", "unknown")
            require(result in {"pass", "fail", "unknown"}, f"{key} 判断无效")
            if result != "unknown":
                require(nonempty(item.get("evidence")), f"{key} 缺少依据")
            results.append(result)
        job["state"] = "excluded" if "fail" in results else "hold" if "unknown" in results else "eligible"
        job["assessment"] = assessment
        job.pop("approval", None)
        job.pop("materials", None)
        return self.save(job, "assessed", assessment)

    def material_snapshot(self, packet):
        require(isinstance(packet, dict) and nonempty(packet.get("resume_path")), "缺少 resume_path")
        path = Path(packet["resume_path"]).resolve()
        require(path.is_relative_to(self.workspace), "简历必须放在当前 private workspace 内")
        require(path.is_file(), "材料文件不存在")
        claims = packet.get("claims_evidence")
        require(isinstance(claims, list) and claims and all(nonempty(x) for x in claims), "材料必须带事实依据列表")
        return {"packet": packet, "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def prepare(self, job_id, packet):
        job = self.get(job_id)
        require(job["state"] in {"eligible", "prepared", "approved"}, "先通过岗位核验")
        fresh(job["assessment"])
        job["materials"] = self.material_snapshot(packet)
        job.pop("approval", None)
        job["state"] = "prepared"
        return self.save(job, "prepared", job["materials"])

    def unchanged(self, job):
        snapshot = self.material_snapshot(job["materials"]["packet"])
        require(snapshot == job["materials"], "文件已改变；重新 prepare 和 approve")
        return fingerprint(snapshot)

    def approve(self, job_id, confirmed=False):
        require(confirmed is True, "需要本人核对材料后明确 --confirm")
        job = self.get(job_id)
        require(job["state"] == "prepared", "先准备材料")
        fresh(job["assessment"])
        job["approval"] = {"at": now(), "digest": self.unchanged(job)}
        job["state"] = "approved"
        return self.save(job, "approved", job["approval"])

    def record(self, job_id, state, evidence):
        require(state in OUTCOMES and nonempty(evidence), "状态必须有效且需要真实事件依据")
        job = self.get(job_id)
        if state == "submitted":
            require(job["state"] == "approved", "只有已确认材料才能登记首次提交")
            fresh(job["assessment"])
            require(self.unchanged(job) == job["approval"]["digest"], "确认不匹配当前材料")
        else:
            require(job["state"] in ACTIVE, "先登记真实提交，终态不能自动重开")
            if state in ACTIVE:
                rank = {"submitted": 0, "responded": 1, "assessment": 2, "interview": 3}
                require(rank[state] >= rank[job["state"]], "不能用后续回信把阶段倒退；同阶段可追加事件")
        job["state"] = state
        job["last_event_at"] = now()
        return self.save(job, state, {"evidence": evidence})

    def review(self, job_id, data):
        job = self.get(job_id)
        require(job["state"] in OUTCOMES, "先登记真实投递事件")
        require(isinstance(data, dict) and nonempty(data.get("summary")) and nonempty(data.get("evidence")), "复盘需要总结与依据")
        gaps = data.get("gaps", [])
        require(isinstance(gaps, list), "gaps 必须是列表")
        for gap in gaps:
            require(isinstance(gap, dict) and all(nonempty(gap.get(k)) for k in ("topic", "exercise", "acceptance")), "每项缺口需要主题、练习和验收")
        for gap in gaps:
            self.db.execute("INSERT INTO learning(job,payload) VALUES(?,?)", (job_id, json.dumps({**gap, "state": "todo"}, ensure_ascii=False)))
        return self.save(job, "review", data)

    def practice(self, task_id, evidence, independent=False):
        require(independent is True and nonempty(evidence), "需要本人独立尝试声明和作品证据")
        row = self.db.execute("SELECT job,payload FROM learning WHERE id=?", (task_id,)).fetchone()
        require(row is not None, "练习不存在")
        data = json.loads(row[1])
        require(data["state"] == "todo", "练习已记录；复测请新建任务")
        data.update(state="practiced", evidence=evidence, recorded_at=now(), independent_self_report=True)
        self.db.execute("UPDATE learning SET payload=? WHERE id=?", (json.dumps(data, ensure_ascii=False), task_id))
        self.save(self.get(row[0]), "practice", {"task_id": task_id, **data})
        return data

    def today(self):
        actions = {"discovered": "核验七项条件", "hold": "补查缺项", "excluded": "保留排除依据，有新证据可重验", "eligible": "准备材料", "prepared": "本人核对并确认", "approved": "本人实际投递后登记回执", "submitted": "等待真实回应，必要时人工跟进", "responded": "确认下一步", "assessment": "准备笔试并复盘", "interview": "准备面试并复盘", "offer": "本人核对条件再决策", "rejected": "复盘并继续其他机会", "withdrawn": "归档撤回原因"}
        jobs = []
        for (payload,) in self.db.execute("SELECT payload FROM jobs ORDER BY id"):
            job = json.loads(payload)
            action = actions[job["state"]]
            if job["state"] in {"eligible", "prepared", "approved"}:
                try:
                    fresh(job["assessment"])
                    if "materials" in job:
                        self.unchanged(job)
                except ValueError as exc:
                    action = str(exc)
            jobs.append({"id": job["id"], "company": job["company"], "state": job["state"], "next": action})
        tasks = [{"id": row[0], "job": row[1], **json.loads(row[2])} for row in self.db.execute("SELECT * FROM learning ORDER BY id")]
        return {"jobs": jobs, "learning": tasks, "note": "待办不是新日程；优先级由本人结合截止与面试安排确认。"}


def demo(workspace):
    flow = Workflow(workspace)
    try:
        if flow.db.execute("SELECT 1 FROM jobs WHERE id='DEMO-001'").fetchone():
            return flow.today()
        resume = flow.workspace / "fictional-resume.md"
        require(not resume.exists(), "演示文件已存在，不覆盖")
        resume.write_text("# 虚构演示材料\n仅用于测试工作流，不代表任何真人经历。\n", encoding="utf-8")
        with flow.db:
            flow.db.execute("BEGIN IMMEDIATE")
            flow.add({"id": "DEMO-001", "company": "虚构示例公司", "role": "虚构解决方案实习", "family": "solutions", "url": "https://example.com/jobs/demo"})
            flow.assess("DEMO-001", {"checked_at": now(), "source": "https://example.com/jobs/demo", "checks": {key: {"result": "pass", "evidence": "虚构测试条件，不是真实岗位"} for key in CHECKS}})
            flow.prepare("DEMO-001", {"resume_path": str(resume), "claims_evidence": ["虚构示例，无真人事实"]})
            flow.approve("DEMO-001", True)
            flow.record("DEMO-001", "submitted", "虚构回执；没有发送申请")
            flow.record("DEMO-001", "interview", "虚构面试邀请")
            flow.review("DEMO-001", {"summary": "虚构练习复盘", "evidence": "虚构练习记录", "gaps": [{"topic": "Python 循环", "exercise": "独立统计列表元素", "acceptance": "运行三个边界用例并解释"}]})
            task_id = flow.db.execute("SELECT id FROM learning WHERE job='DEMO-001' ORDER BY id DESC LIMIT 1").fetchone()[0]
            flow.practice(task_id, "虚构作品证据，只用于流程演示", True)
        return flow.today()
    finally:
        flow.db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default="private/me")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "today", "demo"):
        sub.add_parser(name)
    sub.add_parser("add").add_argument("file")
    for name in ("assess", "prepare", "review"):
        cmd = sub.add_parser(name)
        cmd.add_argument("id")
        cmd.add_argument("file")
    approve = sub.add_parser("approve")
    approve.add_argument("id")
    approve.add_argument("--confirm", action="store_true")
    record = sub.add_parser("record")
    record.add_argument("id")
    record.add_argument("state", choices=sorted(OUTCOMES))
    record.add_argument("--evidence", required=True)
    practice = sub.add_parser("practice")
    practice.add_argument("id", type=int)
    practice.add_argument("--evidence", required=True)
    practice.add_argument("--independent", action="store_true")
    args = parser.parse_args()
    try:
        workspace = (ROOT / ("private/demo" if args.command == "demo" else args.workspace)).resolve()
        require(workspace.is_relative_to(ROOT / "private"), "workspace 必须在仓库 private/ 内，防止误提交")
        if args.command == "demo":
            result = demo(workspace)
        else:
            require(args.command == "init" or (workspace / "state.sqlite3").is_file(), "请先运行 init")
            flow = Workflow(workspace)
            try:
                with flow.db:
                    flow.db.execute("BEGIN IMMEDIATE")
                    if args.command == "init":
                        profile = workspace / "profile.json"
                        if not profile.exists():
                            profile.write_text((ROOT / "templates/profile.json").read_text(encoding="utf-8"), encoding="utf-8")
                        result = {"workspace": str(workspace), "status": "initialized; existing records preserved"}
                    elif args.command == "today":
                        result = flow.today()
                    elif args.command == "add":
                        result = flow.add(load_json(args.file))
                    elif args.command in {"assess", "prepare", "review"}:
                        result = getattr(flow, args.command)(args.id, load_json(args.file))
                    elif args.command == "approve":
                        result = flow.approve(args.id, args.confirm)
                    elif args.command == "record":
                        result = flow.record(args.id, args.state, args.evidence)
                    else:
                        result = flow.practice(args.id, args.evidence, args.independent)
            finally:
                flow.db.close()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, sqlite3.Error, TypeError) as exc:
        parser.exit(2, f"未执行：{exc}\n")


if __name__ == "__main__":
    main()
