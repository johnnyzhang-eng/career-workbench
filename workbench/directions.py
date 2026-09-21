"""Transparent, local-only career-direction calibration."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    key: str
    label: str


QUESTIONS = (
    Question("retail_store", "分析门店、渠道与零售现场，并推动执行改善"),
    Question("merchandise", "围绕货品、选品、动销、调拨或库存做决策"),
    Question("user_lifecycle", "设计会员、CRM、用户生命周期或转化运营"),
    Question("campaign_content", "策划并执行品牌活动、内容或达人合作"),
    Question("business_diagnosis", "从经营异常中归因，并提出可执行建议"),
    Question("data_analysis", "清洗数据、搭看板，并使用 SQL/Python 深挖指标"),
    Question("product_process", "梳理需求、流程和工具，并与产品或研发协作"),
    Question("client_solution", "理解客户问题、讲解方案并推动交付落地"),
)

QUESTION_BY_KEY = {question.key: question for question in QUESTIONS}

DIRECTIONS = (
    ("retail_consumer_ops", "零售 / 消费品牌运营", {"retail_store": 3, "campaign_content": 1, "business_diagnosis": 1}),
    ("user_ops", "用户运营", {"user_lifecycle": 3, "campaign_content": 1, "business_diagnosis": 1}),
    ("merchandise_ops", "商品运营", {"merchandise": 3, "retail_store": 2, "business_diagnosis": 1}),
    ("commercial_ops", "商业运营", {"business_diagnosis": 3, "retail_store": 1, "user_lifecycle": 1, "data_analysis": 1}),
    ("operations_analysis", "运营分析", {"business_diagnosis": 3, "data_analysis": 2, "retail_store": 1}),
    ("business_analysis", "商业分析", {"business_diagnosis": 3, "data_analysis": 2, "client_solution": 1}),
    ("data_analysis_role", "数据分析", {"data_analysis": 3, "business_diagnosis": 2}),
    ("product_ops", "产品运营", {"product_process": 3, "user_lifecycle": 1, "business_diagnosis": 1}),
    ("technical_ops", "技术运营", {"product_process": 2, "data_analysis": 2, "client_solution": 1}),
    ("solutions", "解决方案", {"client_solution": 3, "product_process": 2, "data_analysis": 1}),
)

TEXT_FIELDS = (
    "main_directions", "secondary_directions", "watch_directions",
    "cities", "cohort", "industries", "exclusions",
)


def empty_direction_profile():
    return {
        "schema_version": 1,
        "priorities": {"main": "", "secondary": "", "watch": ""},
        "constraints": {"cities": "", "cohort": "", "industries": "", "exclusions": ""},
        "ratings": {},
        "confirmed_by_user": False,
        "source": "empty",
        "updated_at": None,
    }


def validate_direction_form(values):
    expected = set(TEXT_FIELDS) | {question.key for question in QUESTIONS} | {"confirmed_by_user"}
    if set(values) != expected:
        raise ValueError("方向问卷字段不完整")
    ratings = {}
    for question in QUESTIONS:
        raw = values.get(question.key)
        if raw not in {"0", "1", "2", "3"}:
            raise ValueError("每项偏好必须选择 0–3")
        ratings[question.key] = int(raw)
    clean = {key: str(values.get(key, ""))[:240].strip() for key in TEXT_FIELDS}
    return {
        "schema_version": 1,
        "priorities": {
            "main": clean["main_directions"],
            "secondary": clean["secondary_directions"],
            "watch": clean["watch_directions"],
        },
        "constraints": {key: clean[key] for key in ("cities", "cohort", "industries", "exclusions")},
        "ratings": ratings,
        "confirmed_by_user": values["confirmed_by_user"] == "1",
        "source": "user" if values["confirmed_by_user"] == "1" else "proxy",
    }


def rank_directions(profile):
    ratings = profile.get("ratings") or {}
    if any(key not in ratings for key in QUESTION_BY_KEY):
        return []
    ranked = []
    for direction_id, name, weights in DIRECTIONS:
        points = sum(ratings[key] * weight for key, weight in weights.items())
        maximum = sum(3 * weight for weight in weights.values())
        contributors = sorted(weights, key=lambda key: (ratings[key] * weights[key], weights[key]), reverse=True)
        matched = [QUESTION_BY_KEY[key].label for key in contributors if ratings[key] >= 2][:2]
        ranked.append({
            "id": direction_id,
            "name": name,
            "points": points,
            "maximum": maximum,
            "matched": matched,
        })
    return sorted(ranked, key=lambda item: (-item["points"], item["name"]))
