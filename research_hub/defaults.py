"""Default research pipeline, resources and settings for a new workspace.

Every stage can be renamed, re-ordered, added or removed in the dashboard, so the
pipeline can be matched exactly to a lab's or a department's own process chart.
"""

DEFAULT_STAGES = [
    {
        "key": "topic", "module": "",
        "title_zh": "研究主題", "title_en": "Topic & Motivation",
        "desc_zh": "界定研究背景、動機與研究缺口，形成可研究的主題。",
        "desc_en": "Define the background, motivation and research gap; narrow it down to a researchable topic.",
        "tasks": [("撰寫研究背景與動機", "Draft background & motivation"), ("確認研究缺口", "Confirm the research gap")],
    },
    {
        "key": "literature", "module": "literature",
        "title_zh": "文獻探討", "title_en": "Literature Review",
        "desc_zh": "檢索、篩選與精讀文獻，整理理論基礎與相關研究。",
        "desc_en": "Search, screen and read the literature; build the theoretical basis.",
        "tasks": [("建立檢索關鍵字與資料庫清單", "Define keywords & databases"), ("完成文獻篩選", "Finish screening"),
                  ("撰寫文獻探討初稿", "Draft the literature review")],
    },
    {
        "key": "rq", "module": "rq",
        "title_zh": "研究問題與假設", "title_en": "Research Questions",
        "desc_zh": "提出研究問題（RQ）與對應假設，確認每個 RQ 都有文獻支持。",
        "desc_en": "State research questions (RQs) and hypotheses, each grounded in the literature.",
        "tasks": [("列出 RQ 草稿", "List draft RQs"), ("與指導教授確認 RQ", "Confirm RQs with advisor")],
    },
    {
        "key": "framework", "module": "variables",
        "title_zh": "研究架構與變數", "title_en": "Framework & Variables",
        "desc_zh": "建立研究架構，定義自變數 X、依變數 Y、中介／調節變數 Z 等及其操作型定義。",
        "desc_en": "Build the conceptual model; define X, Y, Z (mediators/moderators) and their operationalisation.",
        "tasks": [("繪製研究架構圖", "Draw the research framework"), ("完成變數操作型定義", "Operationalise every variable")],
    },
    {
        "key": "method", "module": "",
        "title_zh": "研究方法設計", "title_en": "Methodology",
        "desc_zh": "選擇研究設計、抽樣、研究工具與分析方法。",
        "desc_en": "Choose the design, sampling, instruments and analysis plan.",
        "tasks": [("確定抽樣方式與樣本數", "Decide sampling & sample size"), ("完成研究工具（問卷／實驗）", "Finalise instruments")],
    },
    {
        "key": "data", "module": "",
        "title_zh": "資料蒐集", "title_en": "Data Collection",
        "desc_zh": "IRB／倫理審查、前測與正式資料蒐集。",
        "desc_en": "Ethics review, pilot study and main data collection.",
        "tasks": [("倫理審查 / IRB", "Ethics review / IRB"), ("前測", "Pilot test"), ("正式施測", "Main data collection")],
    },
    {
        "key": "analysis", "module": "code",
        "title_zh": "資料分析", "title_en": "Data Analysis",
        "desc_zh": "以 Python 進行資料清理、統計分析與視覺化。",
        "desc_en": "Clean, analyse and visualise data with Python.",
        "tasks": [("資料清理", "Data cleaning"), ("假設檢定", "Hypothesis testing"), ("圖表產出", "Figures & tables")],
    },
    {
        "key": "results", "module": "",
        "title_zh": "結果與討論", "title_en": "Results & Discussion",
        "desc_zh": "回答每個研究問題，與文獻對話並說明研究限制。",
        "desc_en": "Answer each RQ, discuss against the literature and state limitations.",
        "tasks": [("逐一回答 RQ", "Answer each RQ"), ("撰寫研究限制與建議", "Limitations & future work")],
    },
    {
        "key": "writing", "module": "writing",
        "title_zh": "論文撰寫", "title_en": "Writing",
        "desc_zh": "整合各章節、引用格式與摘要。",
        "desc_en": "Assemble chapters, references and abstract.",
        "tasks": [("完成全文初稿", "Full first draft"), ("檢查引用格式", "Check citation style")],
    },
    {
        "key": "defense", "module": "",
        "title_zh": "口試與發表", "title_en": "Defense & Publication",
        "desc_zh": "口試準備、修訂與投稿發表。",
        "desc_en": "Prepare the defense, revise and submit for publication.",
        "tasks": [("口試簡報", "Defense slides"), ("口試後修訂", "Post-defense revisions"), ("投稿", "Submit manuscript")],
    },
]

# target may contain {q}; the dashboard substitutes the URL-encoded search query.
DEFAULT_RESOURCES = [
    {"kind": "database", "name": "Google Scholar", "target": "https://scholar.google.com/scholar?q={q}"},
    {"kind": "database", "name": "Semantic Scholar", "target": "https://www.semanticscholar.org/search?q={q}"},
    {"kind": "database", "name": "arXiv", "target": "https://arxiv.org/search/?query={q}&searchtype=all"},
    {"kind": "database", "name": "PubMed", "target": "https://pubmed.ncbi.nlm.nih.gov/?term={q}"},
    {"kind": "database", "name": "Scopus", "target": "https://www.scopus.com/results/results.uri?src=s&sot=b&s=TITLE-ABS-KEY({q})"},
    {"kind": "database", "name": "Web of Science", "target": "https://www.webofscience.com/wos/woscc/basic-search"},
    {"kind": "database", "name": "華藝線上圖書館 Airiti Library", "target": "https://www.airitilibrary.com/"},
    {"kind": "database", "name": "臺灣博碩士論文知識加值系統 NDLTD", "target": "https://ndltd.ncl.edu.tw/"},
    {"kind": "paperread", "name": "PaperRead", "target": "http://127.0.0.1:8765",
     "notes": "PaperRead reader — open papers, translations and annotations."},
]

DEFAULT_SETTINGS = {
    "project_title": "我的研究 · My Research",
    "language": "zh",
    "paperread_url": "http://127.0.0.1:8765",
    "paperread_library": "~/PaperRead/library",
    "reference_folders": [],
    "code_dir": "",
    "allow_code_run": False,
    "code_timeout": 600,
    "watch_folders": True,
    "openalex_mailto": "",
    "agent_token": "",
}
