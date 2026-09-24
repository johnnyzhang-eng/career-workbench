"""Offline fictional journeys for the first-plan rule templates."""

import json
import tempfile
import unittest
from datetime import date, datetime, timezone

from workbench.goals import GoalStore
from workbench.plan_templates import (CET6_STRUCTURE_URL, InsufficientTimeError,
                                      build_first_plan)


NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
START = date(2026, 10, 5)


def goal(goal_id, domain, minutes=300, target_confidence="self_set"):
    return {"id": goal_id, "title": f"虚构 {domain} 目标", "domain": domain,
            "timezone": "Asia/Shanghai", "weekly_minutes": minutes,
            "success_criterion": "本人记录实际行动与结果，不自动声称外部成功",
            "baseline": "虚构起点，需本人核对",
            "target_at": "2026-11-30T20:00:00+08:00" if target_confidence != "unknown" else None,
            "target_confidence": target_confidence,
            "target_source_ref": None, "target_checked_at": None}


class PlanTemplateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = GoalStore(self.temp.name, clock=lambda: NOW)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def create(self, goal_id, domain, minutes=300):
        self.store.command("create_goal", f"E-{goal_id}",
                           {"goal": goal(goal_id, domain, minutes)})
        return self.store.snapshot(goal_id)["goal"]

    def test_cet6_seven_day_proposal_is_traceable_and_requires_user_decision(self):
        record = self.create("DEMO-CET6", "learning", 300)
        bundle = build_first_plan(record, "cet6", START, "P-CET6")
        proposal = bundle["proposal"]
        self.assertEqual(len(proposal["items"]), 7)
        self.assertEqual(proposal["method"], "rule_template")
        self.assertEqual(proposal["base_version"], 0)
        self.assertEqual(bundle["budget"]["proposed_minutes"], 300)
        self.assertEqual([i["scheduled_at"][:10] for i in proposal["items"]],
                         [f"2026-10-{day:02d}" for day in range(5, 12)])
        self.assertTrue(all(i["source_kind"] == "goal" and i["source_id"] == "DEMO-CET6"
                            for i in proposal["items"]))
        self.assertTrue(all(i["due_confidence"] == "unknown" and i["due_at"] is None
                            for i in proposal["items"]))
        self.assertTrue(all(i["reason"] and i["source_ref"] and i["completion_rule"]
                            for i in proposal["items"]))
        self.assertIn(CET6_STRUCTURE_URL, proposal["source_ref"])
        self.assertIn("2026-09-24", proposal["source_ref"])
        self.assertTrue(any(u["field"] == "exam_registration" for u in bundle["unknowns"]))
        self.store.command("propose_plan", "E-P-CET6", {"proposal": proposal})
        pending = self.store.snapshot("DEMO-CET6")
        self.assertEqual(pending["goal"]["active_version"], 0)
        self.assertEqual(pending["proposals"][0]["status"], "pending")
        self.assertEqual(pending["proposals"][0]["items"][0]["reason"],
                         proposal["items"][0]["reason"])
        self.store.command("decide_plan", "E-D-CET6",
                           {"proposal_id": "P-CET6", "decision": "accept", "actor": "user",
                            "reason": "虚构本人确认", "edited_items": None, "policy_ref": None})
        active = self.store.snapshot("DEMO-CET6")
        self.assertEqual(active["goal"]["active_version"], 1)
        self.assertEqual(active["plans"][0]["items"], proposal["items"])

    def test_recruiting_uses_job_evidence_gate_and_unknown_deadline(self):
        record = self.create("DEMO-HIRE", "recruiting", 240)
        job = {"id": "DEMO-JOB", "source_ref": "https://example.com/fictional-job"}
        bundle = build_first_plan(record, "recruiting", START, "P-HIRE", job=job)
        items = bundle["proposal"]["items"]
        self.assertEqual(len(items), 7)
        self.assertLessEqual(sum(i["estimated_minutes"] for i in items), 240)
        self.assertEqual(items[0]["task_kind"], "verify_job")
        self.assertEqual(items[3]["task_kind"], "prepare_materials")
        self.assertEqual(items[4]["task_kind"], "approve_materials")
        self.assertEqual(items[5]["task_kind"], "apply_job")
        self.assertTrue(all(i["due_at"] is None for i in items))
        self.assertIn("打开链接不是投递", items[5]["completion_rule"])
        self.assertIn("回执", items[5]["completion_rule"])
        self.assertTrue(any(u["field"] == "job_deadline" for u in bundle["unknowns"]))
        self.store.command("propose_plan", "E-P-HIRE", {"proposal": bundle["proposal"]})
        self.store.command("decide_plan", "E-D-HIRE",
                           {"proposal_id": "P-HIRE", "decision": "decline", "actor": "user",
                            "reason": "虚构本人拒绝", "edited_items": None, "policy_ref": None})
        snap = self.store.snapshot("DEMO-HIRE")
        self.assertEqual(snap["goal"]["active_version"], 0)
        self.assertEqual(snap["proposals"][0]["status"], "declined")

    def test_missing_job_and_missing_official_source_remain_explicit(self):
        hire = self.create("DEMO-NO-JOB", "recruiting")
        generic = build_first_plan(hire, "recruiting", START, "P-NO-JOB")
        self.assertTrue(any(u["field"] == "job_record" for u in generic["unknowns"]))
        self.assertFalse(any(i["task_kind"] == "apply_job" for i in generic["proposal"]["items"]))
        self.assertTrue(all(i["source_kind"] == "goal" for i in generic["proposal"]["items"]))
        study = self.create("DEMO-NO-SOURCE", "learning")
        missing = build_first_plan(study, "cet6", START, "P-NO-SOURCE", official_sources={})
        self.assertTrue(any(u["field"] == "cet6_structure" for u in missing["unknowns"]))
        self.assertIn("核对", missing["proposal"]["items"][0]["title"])
        self.assertNotIn(CET6_STRUCTURE_URL, missing["proposal"]["source_ref"])
        self.assertIn("普通英语写作", missing["proposal"]["items"][3]["reason"])
        untrusted = build_first_plan(study, "cet6", START, "P-UNTRUSTED",
                                     official_sources={"structure": {
                                         "url": "https://example.com/cet6-format",
                                         "checked_on": "2026-09-24"}})
        self.assertTrue(any(u["field"] == "cet6_structure" for u in untrusted["unknowns"]))

    def test_verified_deadline_conflict_never_schedules_past_deadline_application(self):
        hire = self.create("DEMO-CONFLICT", "recruiting")
        job = {"id": "DEMO-JOB", "source_ref": "https://example.com/fictional-job",
               "deadline_at": "2026-10-09T12:00:00+08:00",
               "deadline_confidence": "verified",
               "deadline_source_ref": "https://example.com/fictional-job#deadline",
               "deadline_checked_at": "2026-10-01T19:00:00+08:00"}
        bundle = build_first_plan(hire, "recruiting", START, "P-CONFLICT", job=job)
        self.assertTrue(any(u["field"] == "deadline_conflict" for u in bundle["unknowns"]))
        self.assertFalse(any(i["task_kind"] == "apply_job" for i in bundle["proposal"]["items"]))
        self.assertFalse(any(i["task_kind"] in {"prepare_materials", "approve_materials"}
                             for i in bundle["proposal"]["items"]))
        later = {**job, "deadline_at": "2026-10-12T12:00:00+08:00"}
        safe = build_first_plan(hire, "recruiting", START, "P-SAFE", job=later)
        apply = safe["proposal"]["items"][5]
        self.assertEqual(apply["task_kind"], "apply_job")
        self.assertEqual(apply["due_confidence"], "verified")
        self.assertEqual(apply["due_at"], "2026-10-12T12:00:00+08:00")
        self.assertEqual(apply["due_source_ref"], later["deadline_source_ref"])
        with self.assertRaisesRegex(ValueError, "具体来源"):
            build_first_plan(hire, "recruiting", START, "P-BAD", job={**job,
                             "deadline_source_ref": None})
        with self.assertRaisesRegex(ValueError, "明确标记已核验"):
            build_first_plan(hire, "recruiting", START, "P-BAD-FLAG", job={**job,
                             "deadline_confidence": "self_set"})

    def test_insufficient_time_determinism_and_manual_domain_boundary(self):
        little = self.create("DEMO-LITTLE", "learning", 100)
        with self.assertRaises(InsufficientTimeError) as error:
            build_first_plan(little, "cet6", START, "P-LITTLE")
        self.assertEqual(error.exception.required_minutes, 105)
        study = self.create("DEMO-REPLAY", "learning", 175)
        one = build_first_plan(study, "cet6", START, "P-REPLAY")
        two = build_first_plan(study, "cet6", START, "P-REPLAY")
        self.assertEqual(json.dumps(one, sort_keys=True), json.dumps(two, sort_keys=True))
        self.assertLessEqual(one["budget"]["proposed_minutes"], 175)
        other = self.create("DEMO-OTHER", "custom")
        with self.assertRaisesRegex(ValueError, "其他目标请手动建任务"):
            build_first_plan(other, "arbitrary", START, "P-OTHER")
        with self.assertRaisesRegex(ValueError, "CET6 模板需要"):
            build_first_plan(other, "cet6", START, "P-OTHER")
        too_early = {**study, "target_at": "2026-10-08T20:00:00+08:00"}
        with self.assertRaisesRegex(ValueError, "超出本人目标日期"):
            build_first_plan(too_early, "cet6", START, "P-TOO-EARLY")
        long_id = "G" * 80
        self.store.command("create_goal", "E-LONG", {"goal": goal(long_id, "learning")})
        long_goal = self.store.snapshot(long_id)["goal"]
        long_bundle = build_first_plan(long_goal, "cet6", START, "P-LONG")
        self.assertTrue(all(len(i["task_id"]) <= 80 for i in long_bundle["proposal"]["items"]))
        self.store.command("propose_plan", "E-P-LONG", {"proposal": long_bundle["proposal"]})


if __name__ == "__main__":
    unittest.main()
