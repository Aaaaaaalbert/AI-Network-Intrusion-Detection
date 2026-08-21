# 專案紀錄

逐日記錄「做了什麼、為什麼做、學到什麼」，作為之後寫報告與面試說明的依據。日期以實際執行/commit 時間為準，不是課程表上的名義天數（原本的「Day N」7 天計畫只是內容大綱，見下方說明）。

## 2026-08-04 ～ 08-11：Milestone 1 — 資料集探索分析（EDA）

**問題**：CIC-IDS2017 是官方釋出的 CSV，實際下載下來長什麼樣、乾不乾淨、類別平不平衡，都要先摸清楚才能決定後續前處理策略。

**做了什麼**：在 `notebooks/01_dataset_analysis.ipynb` 對 8 個官方 CSV（共 3,119,345 列 × 87 欄）做欄位型態、缺失值、重複列、類別分布等檢查。

**學到什麼**：
- 完全重複列約 9.3%；`Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv` 內有 288,602 筆整列缺失的空白填充列，是資料集本身的問題，必須直接刪除、不可補值。
- 類別極度不平衡：`BENIGN` 占約 73%，最少的 `Heartbleed` 只有 11 筆、`Web Attack Sql Injection` 只有 21 筆。
- 因此決定：切分要用分層抽樣、評估要看 recall/F1/per-class 表現而非只看 accuracy、scaling 與 encoding 只能在訓練集上 fit。

**相關檔案**：[`docs/dataset.md`](dataset.md)、`results/eda/`、commit `92cbbef`

## 2026-08-14：支援合併多個 CSV

**問題**：CIC-IDS2017 官方檔案是依星期拆成多個 CSV，前處理程式原本只能吃單一檔案，沒辦法把五個工作日的資料合併成一份資料集，也沒有留下「這筆資料原本來自哪個檔案」的紀錄。

**做了什麼**：`prepare_data.py` 加入 `--input-dir`，遞迴讀取資料夾內所有 CSV 並合併，同時幫每一列加上 `source_file` 欄位保留來源。

**相關檔案**：commit `986c6ad`

## 2026-08-16：處理真實資料的編碼與高基數欄位問題

**問題**：官方 CSV 不是乾淨的 UTF-8，直接讀取會出錯；某些欄位（例如 IP 位址）類別數極多，若照原本邏輯全部做 One-Hot 編碼，欄位數會爆炸式增加、耗盡記憶體。

**做了什麼**：改用 `latin1` 編碼讀取；加入高基數欄位偵測，超過門檻就直接報錯並要求排除，而不是默默做出一個記憶體爆炸的結果。

**相關檔案**：commit `abee96f`

## 2026-08-17：Baseline 模型、捷徑檢查、按日期切分驗證（同一次工作 session，02:14–05:51）

這天做的事情最多，依序記錄：

### 1. 訓練 Baseline 模型

**問題**：前處理管線通順之後，需要先有一個「至少要贏過它」的分數基準。

**做了什麼**：`src/train_baseline.py` 訓練 Logistic Regression 與 Random Forest（100 棵樹、`class_weight="balanced"`），在隨機切分（80/20，分層抽樣）的測試集上評估。Logistic Regression 是較弱的對照組（Accuracy 93.96%、Recall 82.98%）；Random Forest 明顯更好（Accuracy 99.96%、Recall 99.86%），因此後續實驗都以 Random Forest 為主。

**相關檔案**：`src/train_baseline.py`、`results/baseline_metrics.json`（Logistic Regression）、`results/random_forest_metrics.json`（Random Forest）

### 2. 檢查這個高分是不是某種「捷徑」造成的

**問題**：99.86% 高到不太合理，需要確認模型是不是找到了某個容易利用但不代表真正攻擊模式的捷徑（例如某個欄位剛好跟標籤高度相關，但實際上是資料集產生方式的副作用，換一批資料就會失效）。

**做了什麼**：
- 特徵重要性 + permutation importance 交叉驗證，兩者都指向 `destination_port` 貢獻最大。
- 拿掉 port 相關欄位重新訓練（ablation），Recall 只掉到 98.92%——說明模型不是「只靠 port 猜」，但 port 確實貢獻了一部分分數，是需要留意的候選捷徑。
- 檢查隨機切分下的逐類別 Recall，發現樣本極少的類別（`Web Attack Sql Injection` 4 筆、`Bot` 392 筆）已經開始不穩定，預告了之後多類別模型會遇到的不平衡問題。

**相關檔案**：`results/rf_feature_importance.csv`、`results/rf_permutation_importance.csv`、`results/random_forest_no_port_ablation.json`、`results/random_forest_per_class_recall.csv`（詳見 [`results/split_validation_report.md`](../results/split_validation_report.md) 的「補充分析」段落）

### 3. 按日期切分驗證（本專案目前最重要的發現）

**問題**：隨機逐列切分會把同一個捕獲場景中高度相似的流量，同時分到訓練集與測試集，可能讓模型表現被高估——模型學到的可能只是「這個場景長怎樣」，而不是「攻擊的通用特徵」。

**做了什麼**：改成星期一至四訓練、星期五測試（`--split-strategy by-file`），逼模型面對完全沒見過的日期與部分沒見過的攻擊類型。

**結果**：Accuracy 99.96% → 62.16%，**Recall 從 99.86% 掉到 7.93%**。星期五的 Bot（Recall 0%）、PortScan（Recall 0.08%）幾乎完全偵測不到；DDoS 尚有 17.81%。

**過程中抓到的問題**：第一版按日期切分的資料，`source_file` 被當成一般欄位做 One-Hot 編碼，等於把「今天星期幾」直接餵給模型當特徵——模型可能不是在學攻擊模式，是在背檔名。訓練前發現並修正：
- `source_file` 移出 `NON_FEATURE_COLUMNS`（[`src/prepare_data.py`](../src/prepare_data.py)），只用於切分與事後錯誤分析，不進入模型輸入。
- `tests/test_prepare_data.py` 加入迴歸測試，確保 `source_file` 及其衍生欄位不會出現在 `raw_feature_columns` / `transformed_feature_columns` 中。

**結論**：原本 99.86% 的高分只代表模型對「與訓練資料同分布」的隨機測試集表現好，不能代表它能辨識新日期或新攻擊類型。但星期五的攻擊類型（Bot/DDoS/PortScan）在星期一至四完全沒出現過，所以這次同時測到「跨日期泛化」與「未見攻擊類型泛化」，不能把全部差距都歸因於資料洩漏。

**相關檔案**：[`results/split_validation_report.md`](../results/split_validation_report.md)（完整報告）、`results/by_day/`、`src/analyze_model_errors.py`

## 2026-08-21：釐清專案框架、收斂第 4 步

回頭盤點，把前面做的實驗對應回一個標準 ML 專案框架（定義問題 → 資料前處理 → Baseline → **驗證分數是否可信** → 針對真實目標迭代模型 → 錯誤分析 → 收斂成敘事），確認目前進度落在「驗證分數是否可信」這一步，且已經做完並有明確結論。收尾工作：修正 `.gitignore` 沒擋到 `models/**/*.joblib` 的漏洞、補齊 README 重現指令、把 08-17 的補充分析（特徵重要性／ablation／per-class recall）併入正式報告、建立這份逐日紀錄。

**下一步**：Milestone 2 的多類別攻擊分類模型。已知的關鍵設計問題：星期五攻擊類型（Bot/DDoS/PortScan）與星期一至四攻擊類型（DoS Hulk、Heartbleed 等）幾乎不重疊，若沿用按日期切分，某些類別（如僅 4 筆的 `Web Attack Sql Injection`）會出現「訓練看過但無法被合理評估」或反過來「測試集出現訓練時沒看過的類別」的結構性問題，需要先想清楚再決定切分方式。

## 附註：早期「Day 1–7」計畫與現況的對應

專案最早以 7 天課程大綱規劃（`day2_label_experiment.ipynb`、`day3_baseline_model.py` 是這個階段的產物），但實際進度很快就與名義天數脫鉤，之後改以 Milestone 為單位追蹤。7 天大綱其實只是內容大綱，不是字面上的 7 個日曆天——實際時程約 2 個月，到 2026-10 初。README 的「專案進度」已改用 Milestone 描述，不再維護 Day 1–7 對照。
