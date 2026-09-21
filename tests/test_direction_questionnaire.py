import tempfile
import unittest
from pathlib import Path

from workbench.directions import QUESTIONS, rank_directions, validate_direction_form
from workbench.jobs import JobStore
from workbench.web import agent_task, render_page


def completed_form(**overrides):
    values = {
        "main_directions": "商品运营、用户运营",
        "secondary_directions": "运营分析",
        "watch_directions": "产品运营",
        "cities": "Shanghai",
        "cohort": "2027",
        "industries": "消费品牌",
        "exclusions": "纯销售",
        "confirmed_by_user": "1",
        **{question.key: "1" for question in QUESTIONS},
    }
    values.update(overrides)
    return values


class DirectionQuestionnaireTests(unittest.TestCase):
    def test_ranking_uses_task_preferences_and_explains_contributors(self):
        profile = validate_direction_form(completed_form(
            retail_store="3", merchandise="3", user_lifecycle="2", campaign_content="2",
            business_diagnosis="3", data_analysis="2", product_process="0", client_solution="0",
        ))
        ranked = rank_directions(profile)
        self.assertEqual(ranked[0]["id"], "merchandise_ops")
        self.assertIn("货品", "".join(ranked[0]["matched"]))
        self.assertNotIn("main_directions", ranked[0])

    def test_incomplete_or_out_of_range_answers_are_rejected(self):
        missing = completed_form()
        missing.pop("merchandise")
        with self.assertRaises(ValueError):
            validate_direction_form(missing)
        with self.assertRaises(ValueError):
            validate_direction_form(completed_form(data_analysis="4"))

    def test_users_and_proxy_confirmation_state_remain_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = JobStore(Path(tmp) / "first")
            second = JobStore(Path(tmp) / "second")
            first.save_direction_seed("商品运营", "运营分析", "产品运营")
            second.save_direction_form(completed_form(main_directions="用户运营"))
            self.assertFalse(first.direction_profile()["confirmed_by_user"])
            self.assertEqual(second.direction_profile()["priorities"]["main"], "用户运营")
            self.assertIn("请先完成问卷，不开始搜索", agent_task({}, first.direction_profile()))
            task = agent_task({}, second.direction_profile())
            self.assertIn("主线：用户运营", task)
            self.assertIn("排除门店营业、店员、导购", task)
            self.assertIn("employment_type 只能写“实习”或“应届正式”", task)
            self.assertIn("同一雇主最多 2 条", task)

    def test_private_text_is_escaped_in_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(tmp)
            store.save_direction_seed("<script>alert(1)</script>")
            body = render_page(store, [], "csrf").decode()
            self.assertIn("&lt;script&gt;", body)
            self.assertNotIn("<script>alert(1)</script>", body)


if __name__ == "__main__":
    unittest.main()
