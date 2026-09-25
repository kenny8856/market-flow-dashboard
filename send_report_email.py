"""
量化報告 Gmail 一鍵寄送工具 (Send Report via Gmail CLI)
================================================================================
使用說明：
  1. 預設寄送最新報告：
     python send_report_email.py
  2. 自動重新計算並寄送最新報告：
     python send_report_email.py --generate
  3. 新增收件人：
     python send_report_email.py --add user@example.com
  4. 移除收件人：
     python send_report_email.py --remove user@example.com
  5. 查看目前收件人名單：
     python send_report_email.py --list
  6. 重新配置 Gmail 帳號與 16 位應用程式密碼：
     python send_report_email.py --config
  7. 發送測試信驗證連線：
     python send_report_email.py --test
"""

import os
import sys
import io
import argparse

# 確保 Windows CMD/PowerShell 繁體中文終端正確輸出 UTF-8
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from src.email_sender import EmailSender


def print_banner():
    print("=" * 75)
    print("  [Gmail] 臺股量化實戰報告 - Gmail 一鍵多收件人自動寄送系統")
    print("=" * 75)


def run_interactive_setup(sender):
    """引導式設定精靈"""
    print_banner()
    print("【初次設定 / 重新配置 Gmail 寄件帳號與密碼】")
    print("-" * 75)
    print("提示：因 Google 安全機制限制，必須使用 16 位『應用程式密碼』而非一般登入密碼。")
    print("步驟 1: 開啟 Google 帳戶安全性 (https://myaccount.google.com/security)")
    print("步驟 2: 確認開啟『兩步驟驗證』")
    print("步驟 3: 進入應用程式密碼 (https://myaccount.google.com/apppasswords)")
    print("步驟 4: 名稱輸入『TW_Stock』，取得 16 位英文字母密碼 (如: abcd efgh ijkl mnop)")
    print("-" * 75)

    cur_email = sender.config.get("sender_email", "c2981603@gmail.com")
    input_email = input(f"請輸入寄件人 Gmail [{cur_email}]: ").strip()
    if not input_email:
        input_email = cur_email

    input_pwd = input("請輸入 Google 16 位應用程式密碼: ").strip()
    if not input_pwd:
        print("[!] 密碼不可為空，設定已取消。")
        return False

    sender.set_credentials(input_email, input_pwd)
    print("\n[OK] 寄件人與應用程式密碼已成功儲存至 config/email_config.json！")
    
    # 詢問是否發送測試信
    test_choice = input("是否立即發送測試信驗證連線？(y/n) [y]: ").strip().lower()
    if test_choice in ['', 'y', 'yes']:
        print("[*] 正在發送測試郵件...")
        ok, msg = sender.send_test_email()
        if ok:
            print(f"[✓] {msg}")
        else:
            print(f"[X] {msg}")
    return True


def main():
    parser = argparse.ArgumentParser(description="臺股量化實戰報告 Gmail 一鍵寄送工具")
    parser.add_argument("--files", nargs="+", default=["quant_regime.html", "dashboard.html"], help="指定要寄送的 HTML 報告檔案清單")
    parser.add_argument("--file", help="指定單一 HTML 報告路徑 (覆蓋預設雙檔案)")
    parser.add_argument("--recipients", nargs="+", help="本次寄送指定的收件人信箱 (臨時覆蓋)")
    parser.add_argument("--add", help="永久新增收件人至清單")
    parser.add_argument("--remove", help="從清單中移除指定收件人")
    parser.add_argument("--list", action="store_true", help="列出目前所有收件人清單")
    parser.add_argument("--config", action="store_true", help="開啟互動式設定精靈 (設定 Gmail 與密碼)")
    parser.add_argument("--test", action="store_true", help="發送連線測試郵件")
    parser.add_argument("--generate", action="store_true", help="寄送前先自動執行全市場量化運算重新生成 quant_regime.html 與 dashboard.html")
    args = parser.parse_args()

    sender = EmailSender()

    # 1. 查看收件人清單
    if args.list:
        print_banner()
        recipients = sender.config.get("recipients", [])
        print(f"目前共設定 {len(recipients)} 位收件人：")
        for i, email in enumerate(recipients, 1):
            print(f"  {i}. {email}")
        print("=" * 75)
        return

    # 2. 新增收件人
    if args.add:
        ok, msg = sender.add_recipient(args.add)
        print(f"[{'✓' if ok else 'X'}] {msg}")
        return

    # 3. 移除收件人
    if args.remove:
        ok, msg = sender.remove_recipient(args.remove)
        print(f"[{'✓' if ok else 'X'}] {msg}")
        return

    # 4. 互動設定
    if args.config:
        run_interactive_setup(sender)
        return

    # 5. 連線測試
    if args.test:
        print_banner()
        print("[*] 正在發送測試信至目前收件清單...")
        ok, msg = sender.send_test_email()
        print(f"[{'✓' if ok else 'X'}] {msg}")
        print("=" * 75)
        return

    # 6. 正常寄送報告流程
    print_banner()
    
    # 檢查是否設定了密碼
    if not sender.config.get("app_password", "").strip():
        print("[!] 尚未設定 Google 16 位應用程式密碼。")
        # 若處於可互動終端，自動進入設定精靈
        if sys.stdin.isatty():
            success = run_interactive_setup(sender)
            if not success:
                return
        else:
            print("請手動執行 'python send_report_email.py --config' 設定密碼，或直接編輯 config/email_config.json。")
            return

    # 決定要夾帶的檔案 (預設同時夾帶 quant_regime.html 與 dashboard.html)
    target_files = [args.file] if args.file else args.files

    # 若指定 --generate 或檔案不存在，先生成
    if args.generate or any(not os.path.exists(f) for f in target_files):
        print("[*] 正在執行全套市場量化分析並產出最新儀表板報告 (quant_regime.html & dashboard.html)...")
        try:
            from generate_quant_regime import generate_html
            generate_html(output_path="quant_regime.html")
        except Exception as e:
            print(f"[!] 生成 quant_regime.html 失敗: {e}")

        try:
            from generate_dashboard import main as gen_dash_main
            gen_dash_main()
        except Exception as e:
            print(f"[!] 生成 dashboard.html 失敗: {e}")

    print(f"[*] 準備寄送報告檔案 ({len(target_files)} 個): {', '.join(target_files)}")
    recipients = args.recipients or sender.config.get("recipients", [])
    print(f"[*] 目標收件人 ({len(recipients)} 位): {', '.join(recipients)}")
    
    ok, msg = sender.send_report(html_paths=target_files, recipients=args.recipients)
    print("-" * 75)
    if ok:
        print(f"[OK 成功] {msg}")
    else:
        print(f"[ERR 失敗] {msg}")
    print("=" * 75)


if __name__ == '__main__':
    main()
