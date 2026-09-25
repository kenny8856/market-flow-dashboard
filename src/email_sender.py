"""
量化報告郵件寄送引擎 (Email Sender Engine)
================================================================================
功能：
1. 支援透過 Gmail SMTP (SSL 465 / TLS 587) 一鍵寄出量化報告。
2. 支援同時寄送給多個收件人 (群發功能)。
3. 信件內容雙重呈現：
   - 信件內文：嵌入響應式 HTML 摘要表格 (手機/電腦開信即可秒讀多空訊號)。
   - 信件附件：完整夾帶 quant_regime.html 離線互動儀表板。
4. 支援設定精靈與測試連線。
"""

import os
import json
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.header import Header
from email.utils import formataddr

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "email_config.json")


class EmailSender:
    def __init__(self, config_path=CONFIG_PATH):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self):
        """讀取郵件設定檔"""
        default_config = {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 465,
            "use_ssl": True,
            "sender_email": "c2981603@gmail.com",
            "sender_name": "臺股量化研究系統",
            "app_password": "",
            "recipients": [
                "c2981603@gmail.com"
            ],
            "subject_prefix": "【臺股投行 3 模組市場狀態與立體溫度計】"
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    default_config.update(cfg)
            except Exception as e:
                print(f"[!] 讀取設定檔失敗，使用預設值: {e}")
        return default_config

    def save_config(self, new_config=None):
        """儲存郵件設定檔"""
        if new_config:
            self.config = new_config
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
        return True

    def add_recipient(self, email):
        """新增收件人"""
        email = email.strip()
        if email and email not in self.config.get("recipients", []):
            if "recipients" not in self.config:
                self.config["recipients"] = []
            self.config["recipients"].append(email)
            self.save_config()
            return True, f"已成功新增收件人: {email}"
        return False, f"收件人已存在或格式不正確: {email}"

    def remove_recipient(self, email):
        """移除收件人"""
        email = email.strip()
        recipients = self.config.get("recipients", [])
        if email in recipients:
            recipients.remove(email)
            self.config["recipients"] = recipients
            self.save_config()
            return True, f"已成功移除收件人: {email}"
        return False, f"收件人清單中未找到: {email}"

    def set_credentials(self, sender_email, app_password):
        """設定寄件者帳號與 Google 16 位應用程式密碼"""
        self.config["sender_email"] = sender_email.strip()
        # 去除 Google 應用程式密碼可能夾帶的空格 (例如 'abcd efgh ijkl mnop' -> 'abcdefghijklmnop')
        self.config["app_password"] = app_password.replace(" ", "").strip()
        self.save_config()
        return True

    def build_email_body_html(self, screener_data):
        """
        生成內嵌於 Gmail 信件內文之精美響應式 HTML 摘要表格
        採用內聯 CSS (Inline CSS)，確保所有手機與桌面郵件用戶端完美解析
        """
        m1 = screener_data['module_1']
        radar = screener_data['radar']
        wm = screener_data['warrant_market']
        longs = screener_data['top_longs']
        shorts = screener_data['top_shorts']

        # 組合做多表格列
        long_rows = ""
        for i, x in enumerate(longs, 1):
            w = x['warrant']
            xw = x.get('xiaoge_warrants', [])
            xw_desc = f"<div style='font-size:11px; color:#d97706; margin-top:3px;'>⚡小哥首選: <b>{xw[0]['warrant_id']}</b> {xw[0]['warrant_name']}<br><span style='background:#fef3c7; color:#92400e; padding:1px 4px; border-radius:3px;'>差槓比 {xw[0]['diff_lever_ratio']:.3f}% | 槓桿 {xw[0]['leverage']}x</span></div>" if xw else ""
            long_rows += f"""
            <tr style="border-bottom: 1px solid #e2e8f0; font-size: 13px;">
                <td style="padding: 10px; font-weight: bold; color: #b91c1c;">#{i} {x['id']} {x['name']}{xw_desc}</td>
                <td style="padding: 10px; text-align: right; font-weight: bold;">{x['close']:.2f}</td>
                <td style="padding: 10px; text-align: right; color: #b91c1c; font-weight: bold;">+{x['ret_20d']}%</td>
                <td style="padding: 10px; text-align: right; color: #15803d; font-weight: bold;">{x['entry_price']:.2f}</td>
                <td style="padding: 10px; text-align: right; color: #b91c1c;">{x['stop_loss']:.2f} <small>(-{x['stop_pct']}%)</small></td>
                <td style="padding: 10px; text-align: right; color: #15803d;">{x['take_profit']:.2f} <small>(+{x['profit_pct']}%)</small></td>
                <td style="padding: 10px; font-size: 12px;">{w['call_amt_wan']:,} 萬 <small>({w['call_pct']}%)</small><br><span style="color:#b91c1c; font-weight:bold;">{w['sentiment']}</span></td>
            </tr>
            """

        # 組合做空表格列
        short_rows = ""
        for i, x in enumerate(shorts, 1):
            w = x['warrant']
            xw = x.get('xiaoge_warrants', [])
            xw_desc = f"<div style='font-size:11px; color:#d97706; margin-top:3px;'>⚡小哥首選: <b>{xw[0]['warrant_id']}</b> {xw[0]['warrant_name']}<br><span style='background:#fef3c7; color:#92400e; padding:1px 4px; border-radius:3px;'>差槓比 {xw[0]['diff_lever_ratio']:.3f}% | 槓桿 {xw[0]['leverage']}x</span></div>" if xw else ""
            short_rows += f"""
            <tr style="border-bottom: 1px solid #e2e8f0; font-size: 13px;">
                <td style="padding: 10px; font-weight: bold; color: #15803d;">#{i} {x['id']} {x['name']}{xw_desc}</td>
                <td style="padding: 10px; text-align: right; font-weight: bold;">{x['close']:.2f}</td>
                <td style="padding: 10px; text-align: right; color: #64748b;">季線:{x['ma60']:.1f}</td>
                <td style="padding: 10px; text-align: right; color: #b91c1c; font-weight: bold;">{x['short_entry']:.2f}</td>
                <td style="padding: 10px; text-align: right; color: #b91c1c;">{x['stop_loss']:.2f} <small>(+{x['stop_pct']}%)</small></td>
                <td style="padding: 10px; text-align: right; color: #15803d;">{x['take_profit']:.2f} <small>(-{x['profit_pct']}%)</small></td>
                <td style="padding: 10px; font-size: 12px;">{w['call_amt_wan']:,} 萬 <small>(認購{w['call_pct']}%)</small><br><span style="color:#475569;">借券佔比 {x['sbl_ratio']}%</span></td>
            </tr>
            """

        html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
</head>
<body style="margin: 0; padding: 20px; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; color: #1e293b;">
    <div style="max-width: 800px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
        
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 24px; color: #ffffff;">
            <div style="font-size: 11px; font-weight: bold; letter-spacing: 1px; color: #38bdf8; text-transform: uppercase;">TW-STOCK QUANTITATIVE INTELLIGENCE REPORT</div>
            <h1 style="margin: 8px 0 4px 0; font-size: 22px; font-weight: 800;">🏛️ 投行機構 3 模組市場狀態與立體溫度計</h1>
            <div style="font-size: 13px; color: #94a3b8;">基準分析日: <strong style="color: #ffffff;">{m1['date']}</strong> • 100% 權證活絡標的池</div>
        </div>

        <!-- Macro Summary Cards -->
        <div style="padding: 20px;">
            <div style="display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px;">
                <div style="flex: 1; min-width: 220px; background: #f1f5f9; padding: 14px; border-radius: 8px; border-left: 4px solid #3b82f6;">
                    <div style="font-size: 11px; color: #64748b; font-weight: bold;">模組 1：市場狀態 (Regime)</div>
                    <div style="font-size: 18px; font-weight: 800; color: #0f172a; margin-top: 4px;">{m1['regime_title']}</div>
                    <div style="font-size: 12px; color: #475569; margin-top: 4px;">持股水位: <strong>{m1['exposure_limit']}</strong></div>
                    <div style="font-size: 11px; color: #64748b; margin-top: 2px;">季線寬度: <strong>{m1['breadth_pct']}%</strong> ({m1['above_60ma_count']}/{m1['valid_stocks_count']}檔)</div>
                </div>
                
                <div style="flex: 1; min-width: 220px; background: #f1f5f9; padding: 14px; border-radius: 8px; border-left: 4px solid #f59e0b;">
                    <div style="font-size: 11px; color: #64748b; font-weight: bold;">立體籌碼多空溫度計</div>
                    <div style="font-size: 18px; font-weight: 800; color: #d97706; margin-top: 4px;">{radar['composite_score']} 分 <small style="font-size: 13px;">({radar['regime']})</small></div>
                    <div style="font-size: 12px; color: #475569; margin-top: 4px;">台指特法淨部位: <strong>{m1['tx_net_oi']:+,} 口</strong></div>
                    <div style="font-size: 11px; color: #64748b; margin-top: 2px;">全市場融資增減: <strong>{m1['total_margin_chg']:+,} 股</strong></div>
                </div>

                <div style="flex: 1; min-width: 220px; background: #f1f5f9; padding: 14px; border-radius: 8px; border-left: 4px solid #10b981;">
                    <div style="font-size: 11px; color: #64748b; font-weight: bold;">全市場權證金流總額</div>
                    <div style="font-size: 18px; font-weight: 800; color: #0f172a; margin-top: 4px;">{wm['total_amount_yi']} 億元</div>
                    <div style="font-size: 12px; color: #b91c1c; margin-top: 4px;">認購: <strong>{wm['call_amount_yi']} 億 ({wm['call_ratio']}%)</strong></div>
                    <div style="font-size: 11px; color: #15803d; margin-top: 2px;">認售: {wm['put_amount_yi']} 億 ({wm['put_ratio']}%) • P/C: {wm['pc_ratio']}</div>
                </div>
            </div>

            <!-- Long Targets Table -->
            <div style="margin-bottom: 24px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <span style="background: #fee2e2; color: #b91c1c; font-weight: 800; font-size: 12px; padding: 4px 8px; border-radius: 4px; margin-right: 8px;">{f"做多池 TOP {len(longs)}" if longs else "做多池 (0 檔)"}</span>
                    <strong style="font-size: 15px; color: #0f172a;">{f"大盤{radar['regime']} ｜ 集中火力做多 ｜ 100% 活躍權證" if longs else "大盤偏空破位 ｜ 暫停做多"}</strong>
                </div>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse; text-align: left; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px;">
                        <thead>
                            <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0; font-size: 12px; color: #64748b;">
                                <th style="padding: 10px;">標的</th>
                                <th style="padding: 10px; text-align: right;">現價</th>
                                <th style="padding: 10px; text-align: right;">20D</th>
                                <th style="padding: 10px; text-align: right;">突破進場</th>
                                <th style="padding: 10px; text-align: right;">停損 (2x ATR)</th>
                                <th style="padding: 10px; text-align: right;">目標 (3x ATR)</th>
                                <th style="padding: 10px;">個股權證分析</th>
                            </tr>
                        </thead>
                        <tbody>
                            {long_rows if longs else '<tr style="border-bottom: 1px solid #e2e8f0; font-size: 13px;"><td colspan="7" style="padding: 16px; text-align: center; color: #64748b;">大盤處於偏空格局，量化風控機制暫停做多選股。</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Short Targets Table -->
            <div style="margin-bottom: 20px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <span style="background: #dcfce7; color: #15803d; font-weight: 800; font-size: 12px; padding: 4px 8px; border-radius: 4px; margin-right: 8px;">{f"做空池 TOP {len(shorts)}" if shorts else "做空池 (0 檔)"}</span>
                    <strong style="font-size: 15px; color: #0f172a;">{f"率先破季線 ＋ 散戶接刀 ＋ 借券賣出暴增 ＋ 100% 活躍權證" if shorts else "多頭格局主導 ｜ 暫停逆勢放空 (集中多方火力)"}</strong>
                </div>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse; text-align: left; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px;">
                        <thead>
                            <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0; font-size: 12px; color: #64748b;">
                                <th style="padding: 10px;">標的</th>
                                <th style="padding: 10px; text-align: right;">現價</th>
                                <th style="padding: 10px; text-align: right;">均線架構</th>
                                <th style="padding: 10px; text-align: right;">破位放空</th>
                                <th style="padding: 10px; text-align: right;">停損 (2x ATR)</th>
                                <th style="padding: 10px; text-align: right;">回補 (3x ATR)</th>
                                <th style="padding: 10px;">個股權證分析</th>
                            </tr>
                        </thead>
                        <tbody>
                            {short_rows if shorts else '<tr style="border-bottom: 1px solid #e2e8f0; font-size: 13px;"><td colspan="7" style="padding: 16px; text-align: center; color: #64748b;">大盤處於中性偏多位階，量化風控機制暫停逆勢放空（空方 0 檔），集中多方火力！</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Notice & Attachment info -->
            <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 14px; font-size: 13px; color: #1e40af; margin-top: 16px;">
                📎 <strong>隨信已夾帶兩大核心 HTML 儀表板附件：</strong>
                <ul style="margin: 8px 0 0 0; padding-left: 20px; line-height: 1.6;">
                    <li><strong>quant_regime.html</strong>：投行機構 3 模組市場狀態與立體溫度計（含全市場與個股權證資金流、做多 Top 5 / 做空 Top 5 與 2x ATR 風控計畫）</li>
                    <li><strong>dashboard.html</strong>：臺股立體籌碼多空溫度計與四大實戰策略選股器（黃金軋空股、高檔出貨預警股、可轉債保底牌、個股期主力重押股）</li>
                </ul>
                <div style="margin-top: 8px; font-size: 12px; color: #64748b;">提示：直接下載附件檔案後，於電腦或手機瀏覽器中開啟即可離線使用完整互動儀表與策略篩選功能。</div>
            </div>
        </div>

        <!-- Footer -->
        <div style="background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px; text-align: center; font-size: 12px; color: #94a3b8;">
            臺股量化實戰研究系統 • 100% 離線純自給自足 • 自動發送系統
        </div>
    </div>
</body>
</html>
"""
        return html

    def send_report(self, html_paths=None, recipients=None, custom_subject=None):
        """
        執行寄送報告郵件
        :param html_paths: 要夾帶的 HTML 檔案路徑清單 (預設同時夾帶 quant_regime.html 與 dashboard.html)
        :param recipients: 收件人清單 (若為 None 則使用 config.json 中的清單)
        :param custom_subject: 自訂信件主旨
        :return: (bool 成功與否, str 結果訊息)
        """
        sender_email = self.config.get("sender_email", "").strip()
        app_password = self.config.get("app_password", "").strip()
        smtp_server = self.config.get("smtp_server", "smtp.gmail.com")
        smtp_port = self.config.get("smtp_port", 465)
        use_ssl = self.config.get("use_ssl", True)
        sender_name = self.config.get("sender_name", "臺股量化研究系統")

        if recipients is None:
            recipients = self.config.get("recipients", [])

        # 預設同時夾帶兩大核心報告 (quant_regime.html 與 dashboard.html)
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if html_paths is None:
            html_paths = [
                os.path.join(root_dir, "quant_regime.html"),
                os.path.join(root_dir, "dashboard.html")
            ]
        elif isinstance(html_paths, str):
            html_paths = [html_paths]

        # 基礎防呆檢查
        if not sender_email:
            return False, "寄件人信箱未設定，請先配置 sender_email"
        if not app_password:
            return False, "Google 16 位應用程式密碼 (app_password) 尚未設定！請至 Google 帳戶安全性頁面取得並設定。"
        if not recipients:
            return False, "收件人清單為空，請至少指定一個收件人 Email"

        valid_files = [p for p in html_paths if os.path.exists(p)]
        if not valid_files:
            return False, f"找不到任何指定的儀表板檔案: {html_paths}"

        # 讀取量化核心數據以產出精美內文表格
        try:
            from src.quant_regime_screener import QuantRegimeScreener
            screener = QuantRegimeScreener()
            screener_data = screener.run_analysis()
            body_html = self.build_email_body_html(screener_data)
            latest_date = screener_data['module_1']['date']
            radar_score = screener_data['radar']['composite_score']
            radar_regime = screener_data['radar']['regime']
            long_top3 = "、".join([x['name'] for x in screener_data['top_longs'][:3]])
        except Exception as e:
            print(f"[!] 提取量化核心數據失敗，將使用純附件模式: {e}")
            latest_date = "最新"
            radar_score = ""
            radar_regime = ""
            long_top3 = ""
            body_html = f"<p>請參閱隨信夾帶之附件 quant_regime.html 與 dashboard.html 取得完整今日多空作戰儀表板報告。</p>"

        # 主旨產生
        if custom_subject:
            subject = custom_subject
        else:
            prefix = self.config.get("subject_prefix", "【臺股投行 3 模組市場狀態與立體溫度計】")
            subject = f"{prefix} 基準日: {latest_date} | 溫度計: {radar_score}分 ({radar_regime}) | 做多精選: {long_top3}"

        # 組裝 MIME 郵件
        msg = MIMEMultipart("mixed")
        msg["From"] = formataddr((str(Header(sender_name, "utf-8")), sender_email))
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = Header(subject, "utf-8")

        # 內文 HTML
        alt_part = MIMEMultipart("alternative")
        plain_text = f"臺股量化實戰報告已產出 (基準日: {latest_date})。隨信已夾帶 quant_regime.html 與 dashboard.html 兩大離線儀表板附件。"
        alt_part.attach(MIMEText(plain_text, "plain", "utf-8"))
        alt_part.attach(MIMEText(body_html, "html", "utf-8"))
        msg.attach(alt_part)

        # 附加各 HTML 報表附件
        attached_names = []
        for file_path in valid_files:
            try:
                with open(file_path, "rb") as f:
                    html_bytes = f.read()
                base_name = os.path.basename(file_path)
                name_prefix, ext = os.path.splitext(base_name)
                clean_date = latest_date.replace('-', '') if latest_date != "最新" else ""
                filename = f"{name_prefix}_{clean_date}{ext}" if clean_date else f"{name_prefix}{ext}"
                attach_part = MIMEApplication(html_bytes, _subtype="html")
                attach_part.add_header("Content-Disposition", "attachment", filename=Header(filename, "utf-8").encode())
                msg.attach(attach_part)
                attached_names.append(filename)
                print(f"[+] 已夾帶附件: {filename} ({len(html_bytes):,} bytes)")
            except Exception as e:
                print(f"[!] 夾帶附件 {file_path} 失敗: {e}")

        # 執行連線與寄送
        try:
            print(f"[*] 正在連線至 SMTP 伺服器 ({smtp_server}:{smtp_port})...")
            if use_ssl:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context, timeout=30)
            else:
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
                server.starttls(context=ssl.create_default_context())

            print(f"[*] 驗證帳號登入 ({sender_email})...")
            server.login(sender_email, app_password)

            print(f"[*] 正在發送郵件至 {len(recipients)} 位收件人: {', '.join(recipients)} ...")
            server.sendmail(sender_email, recipients, msg.as_string())
            server.quit()
            
            return True, f"成功寄送至 {len(recipients)} 位收件人: {', '.join(recipients)}"
        except smtplib.SMTPAuthenticationError as e:
            return False, f"Gmail 身份驗證失敗！請確認 16 位應用程式密碼是否正確填寫 (錯誤代碼: {e})"
        except smtplib.SMTPException as e:
            return False, f"SMTP 傳送異常: {e}"
        except Exception as e:
            return False, f"網路連線或寄送過程發生錯誤: {e}"

    def send_test_email(self):
        """發送連線測試郵件"""
        sender_email = self.config.get("sender_email", "")
        recipients = self.config.get("recipients", [])
        subject = "【連線測試】臺股量化研究系統 - Gmail SMTP 連線成功通知"
        test_html = f"""
        <div style="padding: 20px; font-family: sans-serif;">
            <h2>🎉 Gmail SMTP 連線測試成功！</h2>
            <p>這是一封來自 <strong>臺股量化研究系統</strong> 的自動測試信件。</p>
            <p>當您看到此信件時，代表您的 Gmail 寄件帳號 (<code>{sender_email}</code>) 與應用程式密碼設定完全正確！</p>
            <hr>
            <p style="color: #64748b; font-size: 12px;">收件清單: {', '.join(recipients)}</p>
        </div>
        """
        msg = MIMEMultipart()
        msg["From"] = formataddr((str(Header(self.config.get("sender_name", "量化系統"), "utf-8")), sender_email))
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = Header(subject, "utf-8")
        msg.attach(MIMEText(test_html, "html", "utf-8"))

        try:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(self.config.get("smtp_server", "smtp.gmail.com"), self.config.get("smtp_port", 465), context=context, timeout=20)
            server.login(sender_email, self.config.get("app_password", "").strip())
            server.sendmail(sender_email, recipients, msg.as_string())
            server.quit()
            return True, f"測試郵件已成功寄送至: {', '.join(recipients)}"
        except Exception as e:
            return False, f"測試信寄送失敗: {e}"
