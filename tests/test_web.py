"""Web tools against a tiny local website, in a real (hidden) browser.

Uses Edge/Chrome on Windows. Elsewhere set AGENT_TEST_BROWSER to a Chromium executable.
Skipped automatically when no browser can be started.
"""

import os
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

pytest.importorskip("playwright")

from agent import config  # noqa: E402
from agent.tooling import load_all_tools  # noqa: E402
from agent.tools import web  # noqa: E402

TOOLS = load_all_tools()
NEWS = ["첫 번째 공지", "두 번째 공지"]

HOME = """<html><head><title>테스트 쇼핑</title></head><body>
<nav><a href="/about">회사소개</a></nav>
<main><h1>오늘의 특가</h1><p>노트북 할인 행사. 자세한 내용은 <a href="/deal">여기</a>.</p>
<form action="/search" role="search"><input name="q" placeholder="상품 검색"><button>검색</button></form>
<form action="/login" method="post"><input name="user" placeholder="아이디">
<input type="password" name="pw" placeholder="비밀번호"><button type="submit">로그인</button></form>
<form action="/order" method="post"><button type="submit">주문하기</button></form>
<select name="sort"><option>최신순</option><option>가격순</option></select>
<table><caption>가격표</caption><tr><th>상품</th><th>가격</th></tr><tr><td>노트북 A</td><td>1200000</td></tr></table>
<a href="/files/report.csv">보고서 받기</a> <a href="/files/setup.exe">설치 파일</a>
<a href="/deal" target="_blank">새 탭으로 보기</a>
<div style="display:none"><a href="/hidden">숨은 링크</a></div>
</main></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/files/"):
            data = b"a,b\n1,2\n"
            self.send_response(200)
            self.send_header("Content-Disposition", f'attachment; filename="{path.rsplit("/", 1)[-1]}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        body = {
            "/": HOME,
            "/deal": "<html><head><title>특가 상세</title></head><body><h1>노트북 A</h1></body></html>",
            "/search": "<html><head><title>검색결과</title></head><body><h2>결과</h2></body></html>",
            "/news": "<ul>" + "".join(f"<li>{n}</li>" for n in NEWS) + "</ul>",
            "/captcha": "<p>We detected unusual traffic. Verify you are human.</p>",
        }.get(path, "404")
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    web.PROFILE_DIR = tmp_path_factory.mktemp("profile")
    web.configure({**config.DEFAULT_SETTINGS, "browser_visible": False,
                   "browser_executable": os.environ.get("AGENT_TEST_BROWSER", ""),
                   "web_blocked_sites": ["kbstar.com"]})
    try:
        web._page()
    except Exception as e:
        pytest.skip(f"no browser available: {e}")
    yield f"http://127.0.0.1:{server.server_port}"
    web.shutdown()
    server.shutdown()


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)


def site_tmp():
    import tempfile
    return tempfile.mkdtemp()


def ref(page_text: str, label: str) -> int:
    match = re.search(r"\[(\d+)\] [^\n\[]*\"" + re.escape(label), page_text)
    assert match, f"no element for {label}"
    return int(match.group(1))


def test_page_view(site):
    view = TOOLS["web_open"].call({"url": site + "/"})
    page = view["page"]
    assert page.index("오늘의 특가") < page.index("회사소개")  # main content first
    assert "숨은 링크" not in page
    assert "(password)" in page and "노트북 A | 1200000" in page


def test_risky_web_actions_ask_first(site):
    page = TOOLS["web_open"].call({"url": site + "/"})["page"]
    assert TOOLS["web_click"].risk_reason({"number": ref(page, "주문하기")})
    assert TOOLS["web_click"].risk_reason({"number": ref(page, "로그인")})
    assert TOOLS["web_click"].risk_reason({"number": ref(page, "검색")}) is None
    result = TOOLS["web_download"].call({"number": ref(page, "설치 파일"), "folder": str(site_tmp())})
    assert "program" in result["error"]  # programs are refused unless the user agreed (allow_program)


def test_password_is_never_typed(site):
    page = TOOLS["web_open"].call({"url": site + "/"})["page"]
    assert "password" in TOOLS["web_type"].call({"number": ref(page, "비밀번호"), "text": "x"})["error"]


def test_search_form_and_new_tab(site):
    page = TOOLS["web_open"].call({"url": site + "/"})["page"]
    result = TOOLS["web_type"].call({"number": ref(page, "상품 검색"), "text": "노트북", "press_enter": True})
    assert result["title"] == "검색결과"
    page = TOOLS["web_open"].call({"url": site + "/"})["page"]
    result = TOOLS["web_click"].call({"number": ref(page, "새 탭으로 보기")})
    assert result["note"] == "Opened in a new tab." and result["title"] == "특가 상세"
    TOOLS["web_tabs"].call({"close": 2})


def test_table_to_excel_and_download(site, tmp_path):
    TOOLS["web_open"].call({"url": site + "/"})
    assert TOOLS["web_get_tables"].call({})["tables"][0]["title"] == "가격표"
    saved = TOOLS["web_save_table"].call({"table_number": 1, "path": str(tmp_path / "p.xlsx")})
    from openpyxl import load_workbook
    assert [c.value for c in load_workbook(saved["saved"]).active[2]] == ["노트북 A", 1200000]
    page = TOOLS["web_read"].call({})["page"]
    result = TOOLS["web_download"].call({"number": ref(page, "보고서 받기"), "folder": str(tmp_path)})
    assert Path(result["saved"]).read_text() == "a,b\n1,2\n"


def test_blocked_site_and_captcha(site):
    assert "blocked" in TOOLS["web_open"].call({"url": "https://www.kbstar.com"})["error"]
    assert "warning" in TOOLS["web_open"].call({"url": site + "/captcha"})


def test_watch_reports_only_new_lines(site):
    number = TOOLS["watch_page"].call({"url": site + "/news", "interval_minutes": 5})["number"]
    assert web.check_watch(number) == {}
    NEWS.append("세 번째 공지")
    assert "세 번째 공지" in web.check_watch(number)["new"]
    assert web.check_watch(number) == {}
    NEWS.append("방문자 1234명")
    web.check_watch(number)
    NEWS[-1] = "방문자 1235명"  # only a number changed: not news
    assert web.check_watch(number) == {}


def test_unreachable_watch_reports_an_error_and_waits(site):
    number = TOOLS["watch_page"].call({"url": "http://127.0.0.1:9/nothing", "interval_minutes": 5})["number"]
    result = web.check_watch(number)
    assert "error" in result
    assert number not in web.due_watches()  # not retried every minute


def test_labels_for_routines(site):
    page = TOOLS["web_open"].call({"url": site + "/"})["page"]
    number = ref(page, "새 탭으로 보기")
    assert web.label_of_ref(number) == ["새 탭으로 보기", 1]
    assert web.find_ref("새 탭으로 보기") == number
    assert web.find_ref("없는 링크") is None


def test_blocked_site_reached_by_link_is_refused_everywhere(site):
    TOOLS["web_open"].call({"url": site + "/"})
    web._settings["web_blocked_sites"].append("127.0.0.1")
    try:
        assert "blocked" in TOOLS["web_read"].call({})["error"]
        assert "blocked" in TOOLS["web_get_tables"].call({})["error"]
        assert "blocked" in TOOLS["web_click"].call({"number": 1})["error"]
    finally:
        web._settings["web_blocked_sites"].remove("127.0.0.1")


def test_frames_are_read(site):
    page = web._page()
    page.set_content(f'<h1>Blog</h1><iframe src="{site}/" width="800" height="600"></iframe>')
    page.wait_for_load_state("load")
    view = web._snapshot()
    assert "# Blog" in view["page"] and "오늘의 특가" in view["page"]  # the post lives in the frame
    number = ref(view["page"], "여기")
    assert web._ref(number) is not None


def test_secret_fields_are_never_typed(site):
    page = web._page()
    page.set_content('<form><input name="otp" placeholder="인증번호"><input name="acct" aria-label="계좌번호"></form>')
    view = web._snapshot()
    for label in ("인증번호", "계좌번호"):
        assert "error" in TOOLS["web_type"].call({"number": ref(view["page"], label), "text": "123"})
