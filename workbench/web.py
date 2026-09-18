"""Loopback-only, read-only job-board navigation and local preferences."""
from __future__ import annotations

import argparse
import html
import json
import secrets
import sqlite3
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .jobs import JobStore, validate_board

ROOT = Path(__file__).resolve().parents[1]
MAX_FORM = 8192
CSS = """
:root{color-scheme:light;--ink:#17313f;--muted:#526c78;--sea:#176861;--mist:#edf5f4;--line:#c8d8dc;--paper:#fff;--warm:#d65e2b}
*{box-sizing:border-box}body{margin:0;background:#f3f7f8;color:var(--ink);font:16px/1.55 'PingFang SC','Noto Sans CJK SC',system-ui,sans-serif}a{color:var(--sea)}a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid var(--warm);outline-offset:2px}
header{background:var(--ink);color:#fff;padding:2.2rem max(1.5rem,calc((100vw - 1200px)/2)) 2.5rem}header h1{font-size:clamp(2rem,4vw,3.5rem);letter-spacing:-.035em;line-height:1.15;margin:.3rem 0 .6rem;max-width:13em}header p{max-width:55ch;margin:0;color:#d3e3e6}main{max-width:1200px;margin:0 auto;padding:1.5rem;display:grid;grid-template-columns:minmax(250px,300px) minmax(0,1fr);gap:1.7rem;align-items:start}
aside,.source,.job{background:var(--paper);border:1px solid var(--line)}aside{padding:1.4rem;position:sticky;top:1rem}h2{font-size:1.35rem;line-height:1.25;margin:0 0 1rem}h3{font-size:1.18rem;line-height:1.3;margin:.15rem 0 .4rem}label{display:block;font-weight:650;margin:1rem 0 .35rem}input[type=text]{width:100%;border:1px solid #829da6;border-radius:4px;padding:.6rem .7rem;font:inherit}button{font:inherit;cursor:pointer;border:1px solid var(--sea);border-radius:4px;padding:.55rem .8rem;background:var(--sea);color:#fff}button.secondary{background:#fff;color:var(--sea)}button.tiny{padding:.25rem .55rem;font-size:.88rem}.row{display:flex;gap:.6rem;flex-wrap:wrap;align-items:center}.check{display:flex;gap:.55rem;align-items:flex-start;font-weight:400}.check input{margin-top:.35rem}small,.muted{color:var(--muted)}.hint{font-size:.88rem;color:var(--muted)}.source{padding:1rem 1.25rem;margin-bottom:1.3rem;border-left:5px solid var(--sea)}.source p{margin:.2rem 0}.feedhead{display:flex;justify-content:space-between;align-items:baseline;gap:1rem}.job{padding:1.2rem 1.35rem;margin:.65rem 0;border-left:5px solid var(--line)}.job.fresh{border-left-color:var(--warm)}.job.review{border-left-color:#9b6d1a}.meta{color:var(--muted);font-size:.9rem;margin:.3rem 0 .8rem}.status{display:inline-block;background:var(--mist);color:var(--sea);padding:.12rem .45rem;border-radius:2px;font-size:.82rem;font-weight:700}.status.review{background:#fff2d9;color:#78520e}.actions{display:flex;gap:.65rem;flex-wrap:wrap;align-items:center}.actions a{font-weight:650}.actions form{display:inline}.empty{background:#fff;border:1px dashed var(--line);padding:1.6rem}.notice{padding:.75rem 1rem;background:#dcefe7;border-left:4px solid var(--sea);margin-bottom:1rem}.notice.error{background:#fff1e9;border-left-color:var(--warm)}details{margin-top:.75rem}summary{cursor:pointer;color:var(--sea);font-weight:600}.description{white-space:pre-wrap;max-height:19rem;overflow:auto;color:var(--muted)}footer{max-width:1200px;padding:0 1.5rem 3rem;margin:auto;color:var(--muted);font-size:.88rem}
@media(max-width:780px){main{display:block}aside{position:static;margin-bottom:1rem}header{padding:2rem 1.5rem}.feedhead{display:block}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
"""


def esc(value):
    return html.escape(str(value or ""), quote=True)


def safe_link(url, label):
    if not url:
        return '<span class="muted">入口未知，请在职位原页核查</span>'
    return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'


def render_page(store, boards, csrf_token, notice="", error=False):
    profile = store.profile()
    jobs = store.jobs(boards, profile)
    source_parts = []
    for board in boards:
        state = store.source_state(board)
        last = esc(state.get("last_success_at") or "尚未成功同步")
        issue = '<p class="hint">上次读取有误；保留此前职位。稍后可重试。</p>' if state.get("last_error") else ""
        source_parts.append(f'''<section class="source"><div class="row"><strong>Ashby / {esc(board)}</strong><span class="status">公开来源</span></div>
<p>最近成功同步：{last}</p><p class="hint">来源：{safe_link(state['source_url'], '查看公开 API')}；只覆盖此 board，开放状态与资格请到原站确认。</p>{issue}
<form method="post" action="/refresh"><input type="hidden" name="csrf_token" value="{esc(csrf_token)}"><input type="hidden" name="board" value="{esc(board)}"><button type="submit">刷新这家公司的岗位</button></form></section>''')
    cards = []
    for job in jobs:
        status = job["list_state"]
        status_class = "review" if status == "待核查" else ""
        freshness = "review" if status == "待核查" else "fresh" if status == "新发现" else ""
        board = esc(job["board"])
        job_id = esc(job["id"])
        bookmark_action = "取消收藏" if job["bookmarked"] else "收藏"
        bookmark_value = "0" if job["bookmarked"] else "1"
        location = esc(job["location"] or "地点未提供")
        posted = esc(job["published_at"] or "未提供")
        cohort = esc(job["cohort_state"])
        summary = esc(job["description"] or "来源未提供职位描述")
        cards.append(f'''<article class="job {freshness}"><div class="row"><span class="status {status_class}">{esc(status)}</span>{'<span class="status">已收藏</span>' if job['bookmarked'] else ''}</div>
<h3>{esc(job['title'])}</h3><p class="meta">{location}　/　{esc(job['department'] or job['team'] or '部门未提供')}　/　发布：{posted}<br>届别：{cohort}；开放状态与资格：待本人核查<br>首次发现：{esc(job['first_seen_at'])}；最近见于来源：{esc(job['last_seen_at'])}</p>
<div class="actions">{safe_link(job['job_url'], '打开原站职位详情')}{safe_link(job['apply_url'], '去原站申请')}
<form method="post" action="/flag"><input type="hidden" name="csrf_token" value="{esc(csrf_token)}"><input type="hidden" name="board" value="{board}"><input type="hidden" name="id" value="{job_id}"><input type="hidden" name="flag" value="viewed"><input type="hidden" name="value" value="1"><button class="tiny secondary" type="submit">标记已查看</button></form>
<form method="post" action="/flag"><input type="hidden" name="csrf_token" value="{esc(csrf_token)}"><input type="hidden" name="board" value="{board}"><input type="hidden" name="id" value="{job_id}"><input type="hidden" name="flag" value="bookmarked"><input type="hidden" name="value" value="{bookmark_value}"><button class="tiny secondary" type="submit">{bookmark_action}</button></form></div>
<details><summary>查看来源描述与原始字段</summary><p class="description">{summary}</p><p class="hint">来源职位 ID：{job_id}；职类：{esc(job['employment_type'] or '未提供')}。来源文字未经资格核验，链接异常时请回原站确认。</p></details></article>''')
    message = f'<div class="notice {"error" if error else ""}" role="status">{esc(notice)}</div>' if notice else ""
    checked = "checked" if profile.get("include_unknown_cohort", True) else ""
    body = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>岗位发现 · Career Workbench</title><style>{CSS}</style></head><body>
<header><h1>找到岗位，<br>再去原站核查与申请。</h1><p>定期读取你启用的公开招聘 board。筛选帮你缩小列表；是否符合资格、岗位是否仍开放，仍需在招聘方页面确认。</p></header>
<main><aside><h2>我的筛选条件</h2><p class="hint">仅保存在这个本地工作区。不同用户请使用不同 private workspace。</p><form method="post" action="/profile"><input type="hidden" name="csrf_token" value="{esc(csrf_token)}">
<label for="city">城市或地区</label><input id="city" name="city" type="text" value="{esc(profile['city'])}" placeholder="例如 Shanghai">
<label for="direction">岗位方向</label><input id="direction" name="direction" type="text" value="{esc(profile['direction'])}" placeholder="在职位、部门、团队匹配">
<label for="keywords">关键词</label><input id="keywords" name="keywords" type="text" value="{esc(profile['keywords'])}" placeholder="在职位与描述匹配">
<label for="cohort">届别文字</label><input id="cohort" name="cohort" type="text" value="{esc(profile['cohort'])}" placeholder="例如 2027"><p class="hint">只匹配来源明确写出的文字；未写明的仍是未知。</p>
<label class="check"><input type="checkbox" name="include_unknown_cohort" value="1" {checked}>保留未写明届别的岗位</label>
<label for="exclude">排除词</label><input id="exclude" name="exclude" type="text" value="{esc(profile['exclude'])}" placeholder="多个词用逗号分隔">
<p><button type="submit">保存并筛选</button></p></form></aside><section>{message}{''.join(source_parts)}
<div class="feedhead"><h2>发现的岗位</h2><p class="muted">当前显示 {len(jobs)} 条</p></div>{''.join(cards) if cards else '<div class="empty"><h3>当前没有匹配的岗位</h3><p>可放宽筛选条件，或刷新已启用的来源。这里不会推断岗位已经关闭。</p></div>'}
</section></main><footer>打开链接或收藏都不会记为“已投递”。本人在原站实际申请后，仍需使用现有 CLI 核验岗位、确认材料，再凭真实回执登记。此页面不会上传简历或替你提交申请。</footer></body></html>'''
    return body.encode("utf-8")


def make_handler(store, boards, csrf_token=None):
    allowed = set(boards)
    csrf_token = csrf_token or secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def _headers(self, status, length, content_type="text/html; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()

        def _reject(self, status=400):
            body = b"Invalid local request"
            self._headers(status, len(body), "text/plain; charset=utf-8")
            self.wfile.write(body)

        def _trusted(self, writing=False):
            target = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != target:
                return False
            if writing and self.headers.get("Origin") not in {f"http://{target}", "null"}:
                return False
            return True

        def do_GET(self):
            if not self._trusted():
                return self._reject(403)
            parts = urllib.parse.urlsplit(self.path)
            if parts.path != "/":
                return self._reject(404)
            query = urllib.parse.parse_qs(parts.query)
            code = query.get("result", [""])[0]
            messages = {
                "success": "刷新完成；新发现与上次同步时间已更新。",
                "cooldown": "刷新间隔未到；请稍后再试。",
                "error": "这次读取未完成。此前成功保存的岗位仍在，稍后可重试。",
                "saved": "筛选条件已保存在当前工作区。",
                "flagged": "本地状态已更新；这不是投递记录。",
            }
            try:
                body = render_page(store, boards, csrf_token, messages.get(code, ""), code == "error")
            except sqlite3.Error:
                return self._reject(503)
            self._headers(200, len(body))
            self.wfile.write(body)

        def do_POST(self):
            if not self._trusted(True):
                return self._reject(403)
            if self.headers.get_content_type() != "application/x-www-form-urlencoded":
                return self._reject(415)
            try:
                length = int(self.headers.get("Content-Length", ""))
                if not 0 < length <= MAX_FORM:
                    return self._reject(413)
                data = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True, strict_parsing=True)
                if any(len(v) != 1 for v in data.values()):
                    return self._reject()
                values = {k: v[0] for k, v in data.items()}
                if not secrets.compare_digest(values.get("csrf_token", ""), csrf_token):
                    return self._reject(403)
                if self.path == "/profile":
                    store.save_profile(values)
                    code = "saved"
                elif self.path == "/refresh":
                    board = values.get("board")
                    if board not in allowed:
                        return self._reject()
                    code = store.refresh(board)["status"]
                elif self.path == "/flag":
                    board = values.get("board")
                    if board not in allowed or values.get("value") not in {"0", "1"}:
                        return self._reject()
                    store.set_flag(board, values.get("id", ""), values.get("flag"), values["value"] == "1")
                    code = "flagged"
                else:
                    return self._reject(404)
            except sqlite3.Error:
                return self._reject(503)
            except (ValueError, UnicodeError, json.JSONDecodeError):
                return self._reject()
            self.send_response(303)
            self.send_header("Location", "/?result=" + code)
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

    return Handler


def serve(workspace, boards, port=8765, interval_minutes=0):
    boards = tuple(dict.fromkeys(validate_board(board) for board in boards))
    if not boards or not 0 <= port <= 65535 or (interval_minutes and interval_minutes < 15):
        raise ValueError("需要来源 board；周期刷新至少每 15 分钟")
    store = JobStore(workspace)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(store, boards))
    server.daemon_threads = True
    stop = threading.Event()
    if interval_minutes:
        def periodic():
            while not stop.wait(interval_minutes * 60):
                for board in boards:
                    store.refresh(board)
        threading.Thread(target=periodic, daemon=True, name="job-refresh").start()
    try:
        print(f"岗位发现页面：http://127.0.0.1:{server.server_port}/", flush=True)
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default="private/me")
    parser.add_argument("--board", action="append", default=[], help="公开 Ashby board 名称，可重复指定")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--interval-minutes", type=int, default=0, help="本地服务运行期间定时刷新，至少 15 分钟；0 为手动")
    args = parser.parse_args()
    workspace = (ROOT / args.workspace).resolve()
    if not workspace.is_relative_to(ROOT / "private"):
        parser.error("workspace 必须在本仓库 private/ 内")
    try:
        serve(workspace, args.board or ["Ashby"], args.port, args.interval_minutes)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
