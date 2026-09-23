"""
GitHub Pages 自動部署工具 (Automated GitHub Pages Deployment)
================================================================================
功能說明：
1. 將最新產出的 quant_regime.html 同步複製為 docs/index.html 與 index.html。
2. 檢查 Git 儲存庫狀態，自動執行 add、commit 與 push。
3. 部署完成後自動回報專屬 GitHub Pages 網址。
================================================================================
"""

import sys
import os
import shutil
import subprocess
import datetime
import re

# 強制 Windows 終端以 UTF-8 輸出，避免 CP950 編碼異常
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_HTML = os.path.join(ROOT_DIR, "quant_regime.html")
DOCS_DIR = os.path.join(ROOT_DIR, "docs")
DOCS_INDEX = os.path.join(DOCS_DIR, "index.html")
ROOT_INDEX = os.path.join(ROOT_DIR, "index.html")


def run_cmd(cmd, cwd=ROOT_DIR):
    """執行命令並返回 (exit_code, stdout, stderr)"""
    res = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def get_remote_info():
    """解析 git remote origin 網址與專案名稱"""
    code, out, _ = run_cmd("git remote get-url origin")
    if code != 0 or not out:
        return None, None, None
    url = out.strip()
    m = re.search(r"github\.com[/:]([^/]+)/([^/\.]+)(?:\.git)?", url)
    if m:
        user = m.group(1)
        repo = m.group(2)
        gh_pages_url = f"https://{user}.github.io/{repo}/"
        return url, repo, gh_pages_url
    return url, None, None


def deploy():
    print("=" * 70)
    print("[*] 【GitHub Pages 自動部署管線】 啟動")
    print("=" * 70)

    # 1. 檢查原始 HTML 檔
    if not os.path.exists(SRC_HTML):
        print(f"[X] 找不到欲發布的儀表板檔案: {SRC_HTML}")
        print("    請先執行 python generate_quant_regime.py 產出網頁！")
        return False

    file_size_kb = os.path.getsize(SRC_HTML) / 1024
    mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(SRC_HTML)).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[1/4] 驗證來源檔案: quant_regime.html ({file_size_kb:.1f} KB, 最後更新: {mod_time})")

    # 2. 複製檔案至 docs/index.html 與 index.html
    os.makedirs(DOCS_DIR, exist_ok=True)
    shutil.copy2(SRC_HTML, DOCS_INDEX)
    shutil.copy2(SRC_HTML, ROOT_INDEX)
    print(f"[2/4] 已同步複製至:")
    print(f"      - {os.path.relpath(DOCS_INDEX, ROOT_DIR)} (相容 docs 部署模式)")
    print(f"      - {os.path.relpath(ROOT_INDEX, ROOT_DIR)} (相容 root 部署模式)")

    # 3. 檢查 Git 倉庫初始化
    if not os.path.exists(os.path.join(ROOT_DIR, ".git")):
        print("\n[*] 偵測到本機尚未初始化 Git 倉庫，正在為您建立...")
        run_cmd("git init")
        run_cmd("git branch -M main")
        print("    已成功建立 local git repository (預設主分支: main)。")

    # 4. 檢查遠端倉庫 (remote origin)
    remote_url, repo_name, pages_url = get_remote_info()
    if not remote_url:
        print("\n" + "!" * 70)
        print("[!] 【尚未設定 GitHub 遠端倉庫 (Remote Origin)】")
        print("!" * 70)
        print("請按照以下步驟完成一次性綁定 (只需設定一次)：")
        print("1. 開啟 GitHub (https://github.com/new) 建立一個新倉庫 (建議名稱: market-flow-dashboard)")
        print("2. 複製該倉庫的 HTTPS 網址 (例如: https://github.com/kenny8856/market-flow-dashboard.git)")
        print("3. 在終端機執行下列指令進行綁定：")
        print("   git remote add origin https://github.com/<你的帳號>/<你的倉庫名稱>.git")
        print("4. 綁定後重新執行本腳本即可全自動發布！")
        print("!" * 70)
        return False

    print(f"[3/4] 遠端倉庫已連線: {remote_url}")

    # 5. Git 加入檔案與提交
    # 追蹤必要網頁、個股頁面、靜態資源與設定檔，嚴格排除 db
    run_cmd("git add docs/ index.html quant_regime.html assets/ stock_*.html .gitignore")
    
    # 檢查是否有更動需要 commit
    code, diff_out, _ = run_cmd("git diff --cached --name-only")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if diff_out:
        commit_msg = f"Auto deploy market flow dashboard: {now_str}"
        c_code, c_out, c_err = run_cmd(f'git commit -m "{commit_msg}"')
        print(f"[4/4] 產生版本紀錄: {commit_msg}")
    else:
        print("[4/4] 檔案內容與遠端最新版相同，無需重複 commit。")

    # 6. 推送至 GitHub
    print("\n[*] 正在將最新儀表板推送至 GitHub main 分支...")
    p_code, p_out, p_err = run_cmd("git push -u origin main")
    
    if p_code == 0 or "Everything up-to-date" in p_err or "Everything up-to-date" in p_out:
        print("\n" + "=" * 70)
        print("[OK] 【GitHub Pages 部署成功！】")
        print("=" * 70)
        if pages_url:
            print(f"線上即時儀表板網址:")
            print(f"👉 {pages_url}")
            print("\n提示：GitHub Pages 首次發布或更新通常約需 30~60 秒生效。")
            print("您可以在手機、平板或任何電腦直接打開此網址查看最新市場狀態與選股！")
        print("=" * 70)
        return True
    else:
        print(f"\n[X] 推送至 GitHub 時發生錯誤:\n{p_err or p_out}")
        err_msg = (p_err + " " + p_out).lower()
        if "could not read username" in err_msg or "logon failed" in err_msg or "authentication failed" in err_msg or "permission to" in err_msg:
            print("\n" + "=" * 70)
            print("💡 【登入認證失敗 - 快速解決方法】:")
            print("GitHub 自 2021 年起已停用帳號密碼登入，必須使用 Personal Access Token (PAT)。")
            print("👉 請直接在資料夾雙擊執行：【 set_github_token.bat 】")
            print("   貼上您的 GitHub Token (ghp_...)，系統將自動完成永久授權並立即發布！")
            print("=" * 70)
        else:
            print("\n排查建議：")
            print("1. 請確認 GitHub 是否已完成認證授權 (Personal Access Token 或瀏覽器登入)。")
            print("2. 若遠端已有其他 commit，可先執行: git pull origin main --rebase 後再試。")
        return False


if __name__ == '__main__':
    deploy()
