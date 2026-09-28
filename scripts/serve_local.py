"""在本机打开展示页，用本机的 Claude Code（你自己的 Claude 订阅额度）驱动对话框。

用法：python scripts/serve_local.py                 # 打开 http://127.0.0.1:8765/
      python scripts/serve_local.py --model opus    # 指定模型（claude 命令支持的写法）
      python scripts/serve_local.py --no-browser --port 9000
前提：终端里的 claude 命令已经登录（claude auth login）；docs/index.html 已生成（build_site.py）。
安全：只监听 127.0.0.1；/api/claude 只接受本页发出的请求（校验 Host、Origin 和自定义请求头），
      别的网站没法借你的浏览器调用它；claude 以关闭全部工具、安全模式运行，只生成文字。
日志：每次推演的开始、结束、耗时和任何异常都记在 logs/serve_local.log，出问题时先看这里。
测试：环境变量 SHIJIAN_CLAUDE_CMD 可换成假的 claude 命令（路径用正斜杠）。
"""
import argparse
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
LOG_FILE = DOCS.parent / "logs" / "serve_local.log"
LOG = logging.getLogger("shijian")
LOCK = threading.Lock()  # 一次只跑一个推演，避免连点把额度烧掉
CFG = {"port": 8765, "model": None, "cmd": [], "status": {}}


class ClaudeError(Exception):
    pass


def claude_cmd():
    if os.environ.get("SHIJIAN_CLAUDE_CMD"):
        return shlex.split(os.environ["SHIJIAN_CLAUDE_CMD"])
    found = shutil.which("claude")
    if found and found.lower().endswith((".cmd", ".bat")):
        # Windows 上 npm 装的是转发脚本；直接调它背后的 exe，长参数和引号不会被 cmd.exe 改写
        exe = Path(found).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if exe.exists():
            return [str(exe)]
    return [found or "claude"]


def run(args, stdin="", timeout=600):
    return subprocess.run([*CFG["cmd"], *args], input=stdin, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def logged_in():
    """每次都重新读，登录后页面点「重新检测」即可，不用重启服务。"""
    try:
        return bool(json.loads(run(["auth", "status"], timeout=30).stdout).get("loggedIn"))
    except (FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired):
        return None


def probe():
    status = {"version": None, "loggedIn": None}
    try:
        status["version"] = run(["--version"], timeout=30).stdout.strip() or None
    except FileNotFoundError:
        status["error"] = "找不到 claude 命令"
        return status
    except subprocess.TimeoutExpired:
        pass
    status["loggedIn"] = logged_in()
    return status


def parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        a, b = text.find("{"), text.rfind("}")
        if a >= 0 and b > a:
            try:
                return json.loads(text[a:b + 1])
            except json.JSONDecodeError:
                pass
    raise ClaudeError("模型没有按约定的格式回答，请再试一次。")


def ask_claude(system, prompt, schema):
    args = ["-p", "--output-format", "json", "--json-schema", json.dumps(schema, ensure_ascii=False),
            "--tools", "", "--safe-mode", "--no-session-persistence", "--strict-mcp-config", "--system-prompt", system]
    if CFG["model"]:
        args += ["--model", CFG["model"]]
    try:
        p = run(args, stdin=prompt)
    except FileNotFoundError:
        raise ClaudeError("找不到 claude 命令。先安装 Claude Code，再在终端运行 claude auth login。")
    except subprocess.TimeoutExpired:
        raise ClaudeError("推演超过 10 分钟没有结束，已停止。请再试一次。")
    try:
        out = json.loads(p.stdout)
    except json.JSONDecodeError:
        raise ClaudeError(f"claude 没有返回可解析的结果：{(p.stderr or p.stdout).strip()[:300]}")
    if out.get("is_error"):
        msg = str(out.get("result") or "")
        if any(w in msg.lower() for w in ("authenticat", "login", "oauth")):
            raise ClaudeError("本机 Claude Code 还没登录或登录已过期：在终端运行 claude auth login，完成后重试。")
        raise ClaudeError(f"claude 报错：{msg[:300]}")
    if isinstance(out.get("structured_output"), dict):
        return out["structured_output"]
    return parse_json(str(out.get("result") or ""))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DOCS), **kw)

    def log_message(self, fmt, *args):
        if self.path.startswith("/api/claude"):
            sys.stderr.write("[推演] " + (fmt % args) + "\n")

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def same_origin(self):
        hosts = {f"127.0.0.1:{CFG['port']}", f"localhost:{CFG['port']}"}
        origin = self.headers.get("Origin")
        return self.headers.get("Host") in hosts and (origin is None or origin in {f"http://{h}" for h in hosts})

    def do_GET(self):
        if not self.same_origin():
            return self.send_json(403, {"ok": False, "error": "只接受本机页面的请求"})
        if self.path == "/api/health":
            if not CFG["status"].get("error"):
                CFG["status"]["loggedIn"] = logged_in()
            return self.send_json(200, {"ok": True, **CFG["status"]})
        if self.path.startswith("/api/"):
            return self.send_json(404, {"ok": False, "error": "没有这个接口"})
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/claude":
            return self.send_json(404, {"ok": False, "error": "没有这个接口"})
        if not self.same_origin() or self.headers.get("X-Shijian-Local") != "1":
            return self.send_json(403, {"ok": False, "error": "只接受本机页面的请求"})
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= 400_000:
            return self.send_json(413, {"ok": False, "error": "请求太大"})
        try:
            req = json.loads(self.rfile.read(length).decode("utf-8"))
            system, prompt, schema = str(req["system"]), str(req["prompt"]), dict(req["schema"])
        except (ValueError, KeyError, TypeError):
            return self.send_json(400, {"ok": False, "error": "请求格式不对"})
        if not LOCK.acquire(blocking=False):
            return self.send_json(429, {"ok": False, "error": "上一个推演还没结束，稍等一下。"})
        kind = "追问" if "questions" in schema.get("properties", {}) else "推演"
        t0 = time.time()
        LOG.info("开始%s：提示词 %d 字", kind, len(prompt))
        try:
            data = ask_claude(system, prompt, schema)
            LOG.info("完成%s：用时 %.0f 秒", kind, time.time() - t0)
            return self.send_json(200, {"ok": True, "data": data})
        except ClaudeError as e:
            LOG.warning("%s失败（%.0f 秒）：%s", kind, time.time() - t0, e)
            return self.send_json(502, {"ok": False, "error": str(e)})
        except Exception:  # noqa: BLE001  意外错误也给页面一个明确答复，不让连接直接断掉
            LOG.exception("%s时出现意外错误", kind)
            return self.send_json(500, {"ok": False, "error": f"本地服务出现意外错误，详情记在 {LOG_FILE}"})
        finally:
            LOCK.release()


def setup_logging():
    LOG_FILE.parent.mkdir(exist_ok=True)
    handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%m-%d %H:%M:%S"))
    LOG.addHandler(handler)
    LOG.setLevel(logging.INFO)
    # 主线程和请求线程里没接住的异常，也写进日志，服务意外退出时有据可查
    sys.excepthook = lambda *exc: LOG.critical("服务意外退出", exc_info=exc)
    threading.excepthook = lambda a: LOG.error("请求线程出错", exc_info=(a.exc_type, a.exc_value, a.exc_traceback))


def main():
    ap = argparse.ArgumentParser(description="在本机打开史鉴推演，用你自己的 Claude 订阅推演")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--model", default=None, help="传给 claude --model，例如 opus、sonnet")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    if not (DOCS / "index.html").exists():
        sys.exit("还没有 docs/index.html：先运行 python scripts/build_site.py")
    setup_logging()
    CFG.update(port=args.port, model=args.model, cmd=claude_cmd())
    CFG["status"] = probe()
    st = CFG["status"]
    url = f"http://127.0.0.1:{args.port}/"
    print(f"史鉴推演本地版：{url}")
    if st.get("error"):
        print(f"  注意：{st['error']}。页面仍可打开，但只能用示范模式或自带 Key。")
    elif st.get("loggedIn") is False:
        print("  claude 还没登录，登录后才能用你的订阅额度推演。")
        try:  # Windows 上重定向到 NUL 时 isatty() 也为真，读不到输入就跳过
            want = sys.stdin.isatty() and input("  现在登录吗？会打开浏览器让你授权。[Y/n] ").strip().lower() in ("", "y", "yes")
        except (EOFError, KeyboardInterrupt):
            want = False
        if want:
            subprocess.run([*CFG["cmd"], "auth", "login"])
            st["loggedIn"] = logged_in()
        print("  已登录，对话框会用你的订阅额度推演。" if st.get("loggedIn") else
              "  还没登录：之后在任意终端运行 claude auth login，再到页面上点「重新检测」即可。")
    else:
        print(f"  已连上 Claude Code {st.get('version') or ''}，对话框会用你的订阅额度推演。")
    LOG.info("启动：端口 %d，claude %s，已登录=%s", args.port, st.get("version"), st.get("loggedIn"))
    print(f"  推演期间请一直开着这个窗口，关掉就不能推演了。日志：{LOG_FILE}")
    print("  按 Ctrl+C 停止。")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("收到 Ctrl+C，停止")
        print("\n已停止。")


if __name__ == "__main__":
    main()
