# Scout 晨報｜可安裝的 RSS 晨報與免安裝教學展示

[開啟展示首頁](https://jack753951.github.io/scout-midterm/) · [直接操作晨報](https://jack753951.github.io/scout-midterm/brief.html) · [查看測試](test_prototype.py)

## 安裝並產生今天的真實晨報

需要 Python 3.10 以上、網路連線。Windows PowerShell：在你想保存晨報的資料夾執行；不需 Git、Hermes、管理員權限或金鑰。

```powershell
py -3 -m venv .scout-venv
.\.scout-venv\Scripts\python.exe -m pip install https://github.com/Jack753951/scout-midterm/archive/refs/heads/main.zip
.\.scout-venv\Scripts\scout-morning.exe
Invoke-Item (Get-ChildItem .\scout-output\*.html | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
```

macOS / Linux：`python3 -m venv .scout-venv`，再用 `.scout-venv/bin/python -m pip install https://github.com/Jack753951/scout-midterm/archive/refs/heads/main.zip` 安裝，執行 `.scout-venv/bin/scout-morning`。也可下載解壓原始碼，在其根目錄執行 `python -m scout_morning`。

每執行一次，向 BBC 中文、BBC World、UN News、NPR World 的公開 RSS 取一次資料，選出台北當日截至執行時已發布的項目。缺日期、無時區、未來日期與無效連結略過。依網址去除部分追蹤參數後去重，不宣稱可辨識所有同事件報導。輸出 `scout-output/YYYY-MM-DD.html`，附來源、發布時間、RSS 短摘、原文連結及各來源狀態。執行當下才取資料；不讀全文、不自動翻譯或查證、不使用舊資料補數量。沒有合格消息寫入 `-empty.html`；全站讀取失敗寫入 `-unavailable.html` 並以非零狀態結束，均不覆蓋正常報告。可用 `--output-dir` 指定資料夾。

### 選配：AI 與 Telegram（預設關閉）

- `scout-morning --ai`：自行於本機安全設定 `OPENAI_API_KEY`，將選取的標題、來源、網址交給 OpenAI 產生導讀；可能產生 API 費用，不是全文查證。失敗仍保留原版 RSS。
- `scout-morning --telegram`：自行設定 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`，只在明確加旗標且有條目時嘗試寄送本次 HTML。未確認成功時不自動重試。不要把任何金鑰或私人收件設定寫入此儲存庫或聊天。
- 不安裝排程或背景服務。公開核心不是私人 Scout 研究部署的完整備份。GitHub Pages 只提供固定案例，不會在瀏覽器幫你抓新聞；實際 RSS 僅在執行命令的電腦產生。

## 一頁企劃｜第八週生活黑客松

**誰遇到什麼問題？** 早上時間有限的讀者，同時看到正式公告、同學轉述與群組傳聞。如果只看標題，很容易把「有人建議」讀成「已經決定」。問題不是缺新聞，而是判讀一則消息前要來回找來源和限制。

**設計選擇。** 把每則資料拆成標題、來源、時效、短評和「還不知道什麼」。首頁先呈現前三則標題，每則旁邊保留來源類型和限制；想深讀才展開短評，點標題可檢視全文與出處。系統沿用輸入順序，不把傳聞升級為已核實消息。驗收看的是讀者能否辨別公告與傳聞，不是自動生成了幾則新聞。

**原型與工具。** 從個人 Scout 晨報抽出實際使用的 Python 排版器。流程為：整理成結構化欄位 → Python 檢查必填欄位及連結 → 生成可離線開啟的單檔 HTML → 透過 GitHub Pages 分享。選靜態頁是因為讀者不需要帳號、資料庫或安裝套件。這是雲端展示搭配程式規則，不宣稱使用 AppSheet 等 No-code 工具。

**展示任務。** 先進入「操作晨報」，找出哪一則是群組傳聞，說明為何不能據此更改到館時間；再展開第二則的短評，檢查數字是否代表定案。網頁用虛構情境，連結為教學佔位。接著執行 `scout-morning`，從當天真正的 RSS 條目點回來源，區分發布時間與事件時間。兩者是不同展示，不把範例當新聞。

**成功判準與限制。** 三則資料依序出現；傳聞的限制不用點擊就能看到；時效不明不補猜；非法來源連結不出刊；重跑同一份資料不新增重複卡片。這些是可驗證規則，不是使用者研究結果，也不能保證輸入為真。

## 測試與重現

需要 Python 3.10+，不用額外套件。從本資料夾執行：

```sh
python -B -m unittest discover -v
python -B scripts/render_brief.py example.json brief.html
```

| 情況 | 預期行為 |
|---|---|
| 三則不同證據等級 | 保持順序，標題可跳到對應全文 |
| 群組消息未附日期 | 保留「待查線索」，不猜發布日 |
| 無引用，或來源使用非網頁協定 | 拒絕這批輸入，不產生新版本 |
| 同份資料連跑兩次 | 產出相同，仍然只有三張卡片 |

## AI 協作與分工紀錄

- 專案提出者：提出個人晨報需求、要求手機第一眼能看清楚、選定期中專題，並提供課程評量截圖。沒有虛構其他組員或教師回饋。
- AI 助手：依需求協助實作排版、產出測試與展示資料，並整理公開版和企劃。開發時保留新聞與推論的區別；此版不含私人新聞庫、登入資料、收件者、排程或第三方配圖。
- 提示詞節錄：「再以讓我一眼能看清楚的形式重新設計網頁」。對應的檢查是量測手機首屏能否完整呈現前三則標題，而不是讓 AI 自評「易讀」。
- AI 的界線：程式測試只能驗證呈現與規則；真實消息仍需人回到來源查核，口頭報告和實際小組分工由報告者說明。
