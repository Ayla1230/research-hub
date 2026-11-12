# Research Hub · 研究進度中樞

<p align="center"><b>以 PaperRead 為核心的本機論文進度管理系統。</b><br>
從研究主題到口試發表，一條節點流程管理整個研究；研究問題、變數、文獻、資料庫、本機資料夾、MCP 智能體與 Python 分析程式集中在同一個平台。</p>

<p align="center"><b>繁體中文</b> · <a href="README.en.md">English</a></p>

## 快速開始

只需要 Python 3.10 以上，**不需安裝任何套件**（只用標準函式庫）。

```bash
./start.sh            # macOS / Linux，於專案根目錄執行
start.cmd             # Windows
./start.sh --demo     # 以範例資料（TAM 研究）體驗
./start.sh --lang en  # 新工作區預設英文介面與待辦事項
```

開啟 <http://127.0.0.1:8770/>。根目錄 `/` 即為儀表板，`/zh/`、`/en/` 直接切換語言（右上角也可切換）。
**建議下載到自己電腦執行**：所有操作都在本機（`127.0.0.1`）完成，不消耗網路流量；預設不載入任何網路字型。只有 OpenAlex 檢索與開啟外部資料庫連結會連網。

資料預設存在 `~/ResearchHub`（可用 `--data <資料夾>` 或環境變數 `RESEARCH_HUB_HOME` 指定），埠號可用 `--port` 或 `RESEARCH_HUB_PORT` 指定。

## 主要功能

| 區塊 | 說明 |
|---|---|
| **研究流程節點** | 儀表板以一列節點（01 → 10）呈現研究全程：研究主題、文獻探討、研究問題與假設、研究架構與變數、研究方法、資料蒐集、資料分析、結果與討論、論文撰寫、口試與發表。每個節點以圓環顯示進度、狀態與待辦完成數。節點可新增、改名、排序、刪除，以對應系所或實驗室的流程圖。 |
| **階段工作區** | 點選任一節點即展開該階段：狀態（未開始／進行中／審閱中／已完成／受阻）、進度滑桿、起訖日期與逾期提醒、自動儲存的筆記、待辦清單、檔案上傳（拖曳即存入系統目錄）、連結資源，以及該階段的專屬模組（文獻、RQ、變數與架構、Python、寫作引用）。 |
| **研究核心** | 專門管理研究問題（RQ）、變數（自變數 X、依變數 Y、中介 M、調節 Z、控制 C）與文獻。每個變數都能連結相關論文並標示關係（支持、反駁、結果分歧、定義來源、量表來源、提及），未有文獻支持的變數會被標示提醒。 |
| **變數 × 文獻矩陣** | 一眼看出每個變數有哪些文獻支持，點選格子即可切換關係。 |
| **研究架構圖** | 依變數角色自動繪出 X → M → Y、Z 調節、C 控制的概念模型。 |
| **文獻管理** | OpenAlex 檢索並加入、匯入／匯出 BibTeX 與 RIS、閱讀狀態（候選／待閱讀／閱讀中／已讀完／排除）、評分、標籤、開啟本機 PDF、在 PaperRead 開啟。 |
| **整合中心** | 學術資料庫一鍵檢索（Google Scholar、Semantic Scholar、arXiv、PubMed、Scopus、Web of Science、華藝、臺灣博碩士論文系統，可自行新增，網址中以 `{q}` 代表關鍵字）；本機文獻資料夾掃描與匯入；PaperRead 文獻庫同步；MCP 工具設定；Python 程式資料夾與腳本執行；所有上傳檔案。 |
| **即時更新＋使用者確認** | 智能體完成任務、資料夾出現新檔案、PaperRead 同步到新論文或新變數時，變更會先進入「待確認更新」收件匣；使用者逐項勾選、核准後才寫入，確保進度追蹤正確。儀表板透過 Server-Sent Events 即時刷新。 |
| **動態紀錄與備份** | 每次變更記錄來源（使用者／智能體／資料夾監看）與時間；可匯出完整 JSON 備份與 BibTeX。 |

## 智能體與 MCP

Research Hub 內建 MCP 伺服器（stdio，標準函式庫實作）。在「整合中心 → MCP 工具與智能體 → 顯示指令」取得含金鑰的設定，例如 Claude Code：

```bash
claude mcp add research-hub -- python -m research_hub mcp --url http://127.0.0.1:8770 --token <agent token>
```

提供的工具：`get_overview`、`get_schema`、`list_items`、`propose_changes`、`report_stage_progress`、`propose_papers`、`check_proposals`。
**所有寫入類工具都只會建立提案**，不會直接修改資料。智能體可搭配你自己的文獻檢索 MCP（記錄在整合中心），把找到的論文以 `propose_papers` 送進收件匣並連結到變數或 RQ。

不使用 MCP 時，也可用指令列或 HTTP 送出提案：

```bash
python -m research_hub propose changes.json --token <agent token>
curl -X POST http://127.0.0.1:8770/api/agent/proposals -H "Authorization: Bearer <agent token>" \
     -H "Content-Type: application/json" -d '{"title":"文獻探討完成","ops":[{"op":"update","entity":"stage","match":{"key":"literature"},"data":{"status":"review","progress":100}}]}'
```

審閱時若取消勾選某個「新增」項目，引用它的連結會自動一起取消；若提案建立後該項目已被你修改，會顯示衝突提醒。智能體附加的筆記以 `append` 在核准當下接在最後，不會覆蓋你較新的內容。

提案格式（`ops`）：`create`／`update`（可加 `"append": {"notes": "…"}`）／`delete`（`entity` 為 `stage`、`task`、`rq`、`variable`、`paper`、`resource`），以及 `link`／`unlink`（`rq_variable`、`rq_paper`、`variable_paper`）。同一批次中可用 `"ref": "p1"` 建立物件，再以 `"$p1"` 引用。

## 與 PaperRead 的整合

- **連結**：設定 PaperRead 網址（預設 `http://127.0.0.1:8765`），從 PaperRead 匯入的文獻會出現「在 PaperRead 開啟」按鈕。
- **同步**：設定 PaperRead 文獻庫資料夾（預設 `~/PaperRead/library`），按「同步文獻庫」會唯讀讀取每篇的 `paper.json`／`item.json`，把新論文、閱讀狀態變化，以及 PaperRead「研究變數標示」功能抽出的變數（自變數、依變數、中介、調節、控制）整理成一筆待確認更新，並自動建立變數與論文的關聯。
- 本系統不會寫入 PaperRead 的任何檔案。

## Python 程式

在設定中指定後續開發的 Python 專案資料夾，整合中心會列出其中的 `.py`／`.ipynb`。若勾選「允許從儀表板執行 .py 腳本」，可直接執行並查看輸出（使用目前的 Python、工作目錄為程式資料夾、有逾時限制；預設關閉）。

## 安全與資料

- 只監聽 `127.0.0.1`，並檢查 Host 標頭（防 DNS rebinding）；系統沒有登入機制，請勿直接暴露到網際網路。
- 儀表板的每個請求都需頁面載入時取得的 token，其他網站無法跨站寫入。
- 智能體使用獨立、可重設的 agent token，只能讀取與提出變更。
- 只會讀取／開啟設定中的資料夾（文獻資料夾、程式資料夾、PaperRead 文獻庫）與上傳目錄內的檔案。
- 工作區內容：`hub.sqlite3`（所有結構化資料）與 `uploads/`（上傳檔案，依階段分資料夾）。

## 系統架構圖

使用 [archify](https://github.com/tt-a1i/archify) 產生並通過驗證的互動式圖表，在儀表板頁尾「系統架構圖」或 `/static/diagrams/index.html` 開啟：

- `architecture.html`：系統架構
- `confirmation-gate.html`：智能體更新的確認閘門

圖表原始檔在 `.archify/`。

## 設計

視覺設計依 [ui-ux-pro-max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) 的設計系統建議：Minimalism & Swiss Style、IBM Plex Sans + JetBrains Mono（中文 Noto Sans TC）、白色為主調、細線分隔、單一靛藍強調色、等寬小標籤與點陣網格背景；符合其交付檢查清單（SVG 圖示、4.5:1 對比、可見焦點、鍵盤操作、`prefers-reduced-motion`、375–1440px 響應式）。

## 開發

```text
research_hub/
  store.py          SQLite 資料層、驗證、提案（確認閘門）、動態紀錄
  server.py         HTTP API、SSE、上傳、資料夾監看、安全檢查
  integrations.py   BibTeX/RIS、資料夾掃描、OpenAlex、PaperRead、Python 執行
  mcp_server.py     MCP 伺服器（stdio）
  defaults.py       預設研究流程、資料庫與設定
  demo.py           範例資料
  web/              前端（純 HTML/CSS/JS，無建置步驟）
tests/test_hub.py   單元與整合測試
```

```bash
python -m unittest discover tests
```
