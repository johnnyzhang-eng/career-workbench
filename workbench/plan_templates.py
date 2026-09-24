"""Explainable, offline first-plan proposals for the two supported goal paths.

The adapter makes a proposal only. GoalStore records it with ``propose_plan``;
only a separate user ``decide_plan`` can activate it. Reason and provenance
are included on each item so GoalStore keeps them after a user decision.
"""

import hashlib
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


TEMPLATE_VERSION = "first-plan-v1"
SOURCE_CHECKED_AT = "2026-09-24"
CET6_STRUCTURE_URL = "https://cet.neea.edu.cn/html1/report/16123/201-1.htm"
MINUTES_PER_DAY = 15
_ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")


class InsufficientTimeError(ValueError):
    """A seven-day proposal cannot fit meaningful minimum task durations."""

    def __init__(self, available_minutes, required_minutes):
        self.available_minutes = available_minutes
        self.required_minutes = required_minutes
        super().__init__(f"七日计划至少需要 {required_minutes} 分钟；每周仅有 {available_minutes} 分钟")


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _local_stamp(day, zone):
    # This is a suggested slot, not a claim about the user's availability.
    return datetime.combine(day, time(20, 0), zone).isoformat()


def _task_id(goal_id, path_letter, index):
    candidate = f"{goal_id}-{path_letter}{index}"
    if len(candidate) <= 80:
        return candidate
    digest = hashlib.sha256(goal_id.encode("utf-8")).hexdigest()[:16].upper()
    return f"TPL-{digest}-{path_letter}{index}"


def _minutes(budget, weights):
    minimum = MINUTES_PER_DAY * len(weights)
    if budget < minimum:
        raise InsufficientTimeError(budget, minimum)
    spend = min(budget, sum(weights))
    remainder = spend - minimum
    weight_total = sum(weights)
    extra = [remainder * weight // weight_total for weight in weights]
    leftover = remainder - sum(extra)
    # Stable largest-remainder allocation, breaking ties by day order.
    ranks = sorted(range(len(weights)),
                   key=lambda index: (-(remainder * weights[index] % weight_total), index))
    for index in ranks[:leftover]:
        extra[index] += 1
    return [MINUTES_PER_DAY + value for value in extra]


def _parse_verified_deadline(job):
    value = job.get("deadline_at")
    if value is None:
        _need(job.get("deadline_source_ref") is None and job.get("deadline_checked_at") is None,
              "未知岗位截止不能附核验字段")
        _need(job.get("deadline_confidence") in {None, "unknown"},
              "未知岗位截止不能标记已核验")
        return None
    _need(isinstance(value, str) and bool(value.strip()), "岗位截止时间必须是带时区文字")
    _need(job.get("deadline_confidence") == "verified",
          "岗位截止只有明确标记已核验后才能使用")
    _need(isinstance(job.get("deadline_source_ref"), str)
          and bool(job["deadline_source_ref"].strip()), "岗位截止需要具体来源")
    _need(isinstance(job.get("deadline_checked_at"), str), "岗位截止需要核验时间")
    try:
        deadline = datetime.fromisoformat(value.replace("Z", "+00:00"))
        checked = datetime.fromisoformat(job["deadline_checked_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("岗位截止或核验时间格式无效") from exc
    _need(deadline.tzinfo is not None and checked.tzinfo is not None,
          "岗位截止与核验时间必须带时区")
    _need(checked <= deadline, "岗位截止核验时间晚于截止，请重新核对")
    return deadline


def _item(task_id, title, task_kind, source_kind, source_id,
          scheduled_at, minutes, completion_rule, reason, source_ref, *, flexible=True, deadline=None,
          deadline_source=None, deadline_checked=None):
    return {"task_id": task_id, "title": title, "task_kind": task_kind,
            "source_kind": source_kind, "source_id": source_id,
            "scheduled_at": scheduled_at, "estimated_minutes": minutes,
            "completion_rule": completion_rule, "reason": reason,
            "source_ref": source_ref, "flexible": flexible,
            "due_at": deadline.isoformat() if deadline else None,
            "due_confidence": "verified" if deadline else "unknown",
            "due_source_ref": deadline_source if deadline else None,
            "due_checked_at": deadline_checked if deadline else None}


def build_first_plan(goal, path, start_on, proposal_id, *, job=None, official_sources=None):
    """Return ``{proposal, explanations, unknowns, budget}`` deterministically.

    ``goal`` is a GoalStore snapshot goal, ``start_on`` is a local date, and
    ``path`` is either ``recruiting`` or ``cet6``. An optional ``job`` can name
    a *local* job record; this function does not verify its eligibility or
    perform an application. ``official_sources`` can override the cached
    official CET6 source registry, including with an empty mapping to make
    missing-source behavior explicit. Every return value is JSON serializable.
    """
    _need(isinstance(goal, dict), "goal 必须是 GoalStore 目标快照")
    _need(path in {"recruiting", "cet6"}, "仅支持秋招与 CET6 首版模板；其他目标请手动建任务")
    _need(isinstance(start_on, date) and not isinstance(start_on, datetime),
          "start_on 必须是目标时区的 date")
    _need(isinstance(proposal_id, str) and _ID.fullmatch(proposal_id), "proposal_id 无效")
    _need(goal.get("active_version") == 0 and type(goal.get("revision")) is int,
          "此适配器只生成尚未激活计划的首版提案")
    goal_id = goal.get("id")
    _need(isinstance(goal_id, str) and _ID.fullmatch(goal_id), "goal.id 无效")
    weekly = goal.get("weekly_minutes")
    _need(type(weekly) is int and weekly >= 0, "weekly_minutes 必须是非负整数")
    try:
        zone = ZoneInfo(goal["timezone"])
    except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("goal.timezone 必须是 IANA 时区") from exc
    target_value = goal.get("target_at")
    if target_value is not None:
        _need(isinstance(target_value, str), "goal.target_at 必须是带时区文字")
        try:
            target = datetime.fromisoformat(target_value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("goal.target_at 时间格式无效") from exc
        _need(target.tzinfo is not None, "goal.target_at 必须带时区")
        final_slot = datetime.combine(start_on + timedelta(days=6), time(20, 0), zone)
        _need(final_slot <= target, "七日计划超出本人目标日期，请修改首日或由本人改拟计划")
    domain = goal.get("domain")
    if path == "cet6":
        _need(domain in {"learning", "cet6"}, "CET6 模板需要 learning 或 cet6 领域")
        _need(job is None, "CET6 计划不能依赖岗位 ID")
    else:
        _need(domain in {"recruiting", "career", "job_search"}, "秋招模板需要求职领域")

    weights = [30, 45, 40, 45, 45, 50, 45] if path == "cet6" else [30, 45, 35, 50, 45, 50, 45]
    durations = _minutes(weekly, weights)
    unknowns = []
    explanations = []
    items = []
    if goal.get("target_confidence") != "verified":
        unknowns.append({"field": "external_target_date", "reason":
                         "目标日期不是已经核实的外部时间；不能据此显示考试或招聘倒计时"})
    if path == "cet6":
        sources = ({"structure": {"url": CET6_STRUCTURE_URL,
                                  "checked_on": SOURCE_CHECKED_AT}}
                   if official_sources is None else official_sources)
        _need(isinstance(sources, dict), "official_sources 必须是来源映射")
        structure = sources.get("structure")
        has_structure = (isinstance(structure, dict)
                         and isinstance(structure.get("url"), str)
                         and bool(structure["url"].strip())
                         and structure["url"] == CET6_STRUCTURE_URL
                         and isinstance(structure.get("checked_on"), str)
                         and bool(structure["checked_on"].strip()))
        if has_structure:
            try:
                date.fromisoformat(structure["checked_on"])
            except ValueError:
                has_structure = False
        if not has_structure:
            unknowns.append({"field": "cet6_structure", "reason":
                             "缺少已核对的官方笔试结构来源；先核对来源，不声明当前题型或比例"})
        unknowns.append({"field": "exam_registration", "reason":
                         "未提供当次考试和学校报名公告；报名资格、日期与考点需本人核对"})
        titles = (["核对 CET6 官方结构与本人基线", "听力短练与第一次记录", "阅读短练与错因记录",
                   "写作短练与自评", "翻译短练与自评", "听读错因复看与独立再试", "一周复盘与下周提案"]
                  if has_structure else
                  ["查找并核对 CET6 官方考试说明", "英语听力短练与第一次记录", "英语阅读短练与错因记录",
                   "英语写作短练与自评", "英语翻译短练与自评", "听读错因复看与独立再试", "一周复盘与下周提案"])
        rules = ["保存官方页面链接与访问日期，写下本人练习基线和材料来源",
                 "本人记录练习来源、首次作答与错因；订正分数另记",
                 "本人记录练习来源、首次正确数、题量与错因位置",
                 "本人完成一段原创短文并记录自评与待改处；不自动判断考试水平",
                 "本人完成一段自选材料的翻译并记录待改处；不复制真题",
                 "本人记录借助讲解与独立作答各自的结果；不把订正当掌握",
                 "本人对照本周实际分钟、首次结果和未完成项写复盘；下一版需本人决定"]
        reasons = ["先核对依据和起点，再安排可比较的练习",
                   "用首次结果建立听力练习基线", "用首次结果建立阅读练习基线",
                   "覆盖官方结构中的写作能力领域", "覆盖官方结构中的翻译能力领域",
                   "复测与复看分开，避免把看懂答案当成独立掌握",
                   "用真实练习结果决定是否提出下一版计划"]
        if not has_structure:
            reasons[3] = "在官方结构待核对时，只作为普通英语写作短练"
            reasons[4] = "在官方结构待核对时，只作为普通英语翻译短练"
        source_ref = (f"{TEMPLATE_VERSION}:cet6;{structure['url']}#checked={structure['checked_on']}"
                      if has_structure else f"{TEMPLATE_VERSION}:cet6;official-structure=unknown")
        for index in range(7):
            task_id = _task_id(goal_id, "C", index + 1)
            item_source = (f"{structure['url']}#checked={structure['checked_on']}"
                           if has_structure and index in {0, 3, 4} else
                           ("official-structure=unknown" if index == 0 else
                            f"{TEMPLATE_VERSION}:cet6"))
            item = _item(task_id, titles[index], "practice", "goal", goal_id,
                         _local_stamp(start_on + timedelta(days=index), zone),
                         durations[index], rules[index], reasons[index],
                         f"{item_source};assumption:goal.baseline,goal.weekly_minutes,20:00-slot")
            items.append(item)
            explanations.append({"task_id": task_id, "reason": reasons[index],
                                 "source_ref": item["source_ref"],
                                 "assumption_ref": "goal.baseline;goal.weekly_minutes;20:00 suggested slot"})
    else:
        _need(job is None or isinstance(job, dict), "job 必须是本地岗位引用或 null")
        has_job = job is not None
        if has_job:
            job_id = job.get("id")
            _need(isinstance(job_id, str) and _ID.fullmatch(job_id), "job.id 无效")
            _need(isinstance(job.get("source_ref"), str) and bool(job["source_ref"].strip()),
                  "岗位引用必须保留具体来源")
            deadline = _parse_verified_deadline(job)
        else:
            job_id = None
            deadline = None
            unknowns.append({"field": "job_record", "reason":
                             "尚无具体岗位记录；不能提议某岗位已核验、已批准或已投递"})
        if deadline is None:
            unknowns.append({"field": "job_deadline", "reason":
                             "没有已核对的岗位截止；不生成倒计时或硬截止"})
        apply_at = datetime.combine(start_on + timedelta(days=5), time(20, 0), zone)
        deadline_conflict = deadline is not None and deadline <= apply_at
        if deadline_conflict:
            unknowns.append({"field": "deadline_conflict", "reason":
                             "已核验岗位截止早于模板拟定投递时段；须本人重排，模板不安排投递"})
        if has_job and deadline_conflict:
            titles = ["立即核对岗位截止与当前状态", "查找可继续核验的岗位来源",
                      "核对简历项目事实", "整理可复用材料", "本人决定是否调整目标与时段",
                      "本人重排岗位时段", "复盘真实状态与下周行动"]
            kinds = ["verify_job", "custom", "custom", "custom", "custom", "custom", "custom"]
            rules = ["保存已核验截止来源与时间；本人确认是否仍有可行动入口，不自动断定录用结束",
                     "记录替代岗位原页、资格和未知项；搜索摘要仍只算线索",
                     "本人核对材料中的归属、数字和可验证证据",
                     "整理可复用材料；不得声称已针对过期时段获批准",
                     "本人决定新目标或缩短计划；不自动改外部截止",
                     "本人核对真实页面后选新时段；不得把模板视为已投递",
                     "区分实际回执、待核验岗位与当前材料状态"]
        elif has_job:
            titles = ["核对岗位原页与资格", "补齐未知资格与申请入口",
                      "核对简历项目事实", "准备当前版本材料", "本人核对并批准材料",
                      "本人重排岗位时段" if deadline_conflict else "原站人工投递并核对回执",
                      "复盘真实状态与下周行动"]
            kinds = ["verify_job", "custom", "custom", "prepare_materials",
                     "approve_materials", "custom" if deadline_conflict else "apply_job", "custom"]
            rules = ["保存具体岗位页面、核验时间及届别、城市、年限与资格结论；未知保持 hold",
                     "逐项记录未知条件的具体页面与待查项；打开页面不代表合格",
                     "本人核对材料中的归属、数字和可验证证据，未知项不得润色为事实",
                     "保存材料版本并逐项对照当前已核验岗位要求；初稿不等于批准",
                     "本人明确确认当前材料版本与岗位；确认之前不能记录提交",
                     ("本人检查截止冲突并决定新时段；不得把模板视为已投递" if deadline_conflict else
                      "仅本人在原站实际提交并核对回执后记录 submitted；打开链接不是投递"),
                     "区分已核验、材料准备、本人批准、真实回执与仍未知的状态"]
        else:
            titles = ["确定岗位筛选条件", "查找具体官方岗位页面", "核对一个岗位的资格与来源",
                      "核对简历事实证据", "准备可复用材料清单", "核对申请入口与未知截止",
                      "复盘待核验岗位与下周行动"]
            kinds = ["custom"] * 7
            rules = ["本人写下城市、届别、方向和硬排除条件",
                     "保存至少一个具体岗位原页链接及访问日期；搜索摘要只是线索",
                     "记录岗位 ID 或链接、资格字段、来源和未知项；不代替真实核验",
                     "本人核对简历主张的归属、数字和证据位置",
                     "列出准备材料与缺项；不得宣称材料已获特定岗位批准",
                     "保存原始申请入口与截止来源；未知截止保持未知，打开链接不是投递",
                     "区分线索、核验结果、材料和实际回执，写下下一步"]
        reasons = ["先确认目标约束与具体来源", "未知资格必须补查",
                   "材料主张需要证据", "按当前要求准备材料", "材料版本由本人确认",
                   "申请事实只能由真实回执支持" if not deadline_conflict else "外部截止与内部时段冲突需本人处理",
                   "周回顾以实际证据调整下一步"]
        if deadline_conflict:
            reasons[0] = "已核验的外部截止与七日模板冲突，先核对事实并由本人决定"
            reasons[3] = "保留通用材料准备，不冒充该岗位仍可按模板时段申请"
            reasons[4] = "需本人决策新目标或时段，不自动移动外部截止"
        source_ref = f"{TEMPLATE_VERSION}:recruiting;workflow:docs/workflow.md"
        for index in range(7):
            task_id = _task_id(goal_id, "R", index + 1)
            kind = kinds[index]
            source_kind = "job" if has_job and kind in {"verify_job", "prepare_materials",
                                                       "approve_materials", "apply_job"} else "goal"
            is_apply = kind == "apply_job" and deadline is not None
            item_source = (job["source_ref"] if has_job and source_kind == "job"
                           else "docs/workflow.md#state-machine")
            item = _item(task_id, titles[index], kind, source_kind,
                         job_id if source_kind == "job" else goal_id,
                         _local_stamp(start_on + timedelta(days=index), zone),
                         durations[index], rules[index], reasons[index],
                         f"{TEMPLATE_VERSION}:recruiting;{item_source};"
                         "assumption:goal.baseline,goal.weekly_minutes,20:00-slot",
                         flexible=not is_apply,
                         deadline=deadline if is_apply else None,
                         deadline_source=job.get("deadline_source_ref") if is_apply else None,
                         deadline_checked=job.get("deadline_checked_at") if is_apply else None)
            items.append(item)
            explanations.append({"task_id": task_id, "reason": reasons[index],
                                 "source_ref": item["source_ref"],
                                 "assumption_ref": "goal.baseline;goal.weekly_minutes;20:00 suggested slot"})

    proposal = {"id": proposal_id, "goal_id": goal_id,
                "goal_revision": goal["revision"], "base_version": 0,
                "review_id": None,
                "reason": "七日首版建议；每日 20:00 仅是待本人编辑的默认时段，执行前需确认。"
                          + "；".join(unknown["reason"] for unknown in unknowns),
                "items": items, "method": "rule_template", "source_ref": source_ref}
    return {"proposal": proposal, "explanations": explanations, "unknowns": unknowns,
            "budget": {"available_minutes": weekly,
                       "proposed_minutes": sum(item["estimated_minutes"] for item in items),
                       "unallocated_minutes": weekly - sum(item["estimated_minutes"] for item in items)},
            "template_version": TEMPLATE_VERSION}
