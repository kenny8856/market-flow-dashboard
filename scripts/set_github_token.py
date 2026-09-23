"""
GitHub 權杖設定與一鍵授權工具
================================================================================
讓使用者輸入一次 GitHub Personal Access Token (PAT)，
自動配置到 remote origin，徹底解決 'could not read Username' 與登入驗證失敗問題。
================================================================================
"""

import sys
import os
import subprocess
import re

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def run_cmd(cmd):
    res = subprocess.run(cmd, cwd=ROOT_DIR, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def main():
    print("=" * 70)
    print("🔑 【GitHub 認證權杖 (Token) 一鍵配置工具】")
    print("=" * 70)
    print("說明：GitHub 自 2021 年起停用帳號密碼，推送程式碼必須使用 Personal Access Token。")
    print("\n若您尚未建立 Token，請依以下步驟取得 (只需 1 分鐘)：")
    print("1. 前往 GitHub 網頁: https://github.com/settings/tokens")
    print("2. 點擊 【Generate new token】 -> 【Generate new token (classic)】")
    print("3. Note 名稱輸入: market-flow")
    print("4. 勾選 【repo】 (完整控制儲存庫權限)")
    print("5. 滾動到最下方點擊綠色按鈕 【Generate token】")
    print("6. 複製該串 Token (格式通常為 ghp_xxxxxxxxxxxxxxxxxxxx)")
    print("=" * 70)

    code, out, _ = run_cmd("git remote get-url origin")
    if code != 0 or not out:
        print("[X] 尚未設定 remote origin，請先確認倉庫已建立。")
        return

    current_url = out.strip()
    m = re.search(r"github\.com[/:]([^/]+)/([^/\.]+)(?:\.git)?", current_url)
    if not m:
        print(f"[X] 無法解析 GitHub 倉庫網址: {current_url}")
        return

    user, repo = m.group(1), m.group(2)
    print(f"\n目前倉庫: https://github.com/{user}/{repo}.git")

    token = input("\n請在此貼上您的 GitHub Token (ghp_...): ").strip()
    if not token:
        print("[!] 取消輸入。")
        return

    # 清除可能多貼的引號或空白
    token = token.replace('"', '').replace("'", "").strip()

    new_url = f"https://{token}@github.com/{user}/{repo}.git"
    set_code, _, set_err = run_cmd(f'git remote set-url origin "{new_url}"')

    if set_code != 0:
        print(f"[X] 設定 remote url 失敗: {set_err}")
        return

    print(f"\n[OK] 遠端網址已成功更新為 Token 授權模式！")
    print("⏳ 正在為您立即測試推送至 GitHub...")

    p_code, p_out, p_err = run_cmd("git push -u origin main")
    if p_code == 0 or "Everything up-to-date" in p_err or "Everything up-to-date" in p_out:
        print("\n" + "=" * 70)
        print("🎉 【認證成功！儀表板已順利推送到 GitHub Pages！】")
        print(f"👉 您的線上儀表板網址: https://{user}.github.io/{repo}/")
        print("=" * 70)
    else:
        print(f"\n[X] 測試推送失敗，請檢查 Token 是否正確或具備 repo 權限:\n{p_err or p_out}")


if __name__ == '__main__':
    main()
