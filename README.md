# AI Network Intrusion Detection

使用機器學習分析網路流量，判斷連線是正常流量或攻擊，並輸出攻擊類型與信心分數。

## 專案進度

- Milestone 1（2026-08-11）：資料集探索分析（EDA）
- Milestone 2（2026-08-14 ～ 08-17）：支援多 CSV 合併、處理真實 CIC-IDS2017 編碼問題、建立基準模型、按日期切分驗證
- Milestone 3（2026-08-26 ～ 08-27）：多類別攻擊分類模型、預測信心分數、正式校準分析（ECE / Brier / Log Loss）
- Milestone 4（2026-08-27）：預測 API、真實流量重播與模型監控介面

完整的逐日紀錄（含每一步在解決什麼問題、學到什麼）見 [`docs/progress_log.md`](docs/progress_log.md)。

## 快速開始

需要 Python 3.10 以上版本。

```powershell
python -m pip install -r requirements.txt
python -m src.prepare_data --demo --output-dir data/processed
python -m unittest discover -s tests -v
```

處理自己的 CSV：

```powershell
python -m src.prepare_data --input data/raw/network_traffic.csv --output-dir data/processed
```

以星期一至四訓練、星期五測試，進行較嚴格的跨日期驗證：

```powershell
python -m src.prepare_data --input-dir dataset/raw --output-dir dataset/processed_by_day --split-strategy by-file --test-file-prefix Friday
python -m src.train_baseline --processed-dir dataset/processed_by_day --model random_forest --model-dir models/by_day --results-dir results/by_day
```

這個切分用來檢查隨機逐列切分是否因相似流量同時進入訓練與測試集，而高估模型表現。`source_file` 只保留供驗證與錯誤分析，不會成為模型輸入。

實際驗證結果與限制整理在 [`results/split_validation_report.md`](results/split_validation_report.md)。跨日期測試 Recall 為 7.93%，顯示監督式模型對星期五未見攻擊類型的泛化能力不足。

預設會辨識 `Label` 或 `label` 作為目標欄位，將 `BENIGN`、`NORMAL`、`0` 視為正常，其餘標籤視為攻擊。輸出包括：

- `train.csv`：模型訓練資料
- `test.csv`：保留的測試資料
- `preprocessor.joblib`：只用訓練集擬合的資料轉換器
- `metadata.json`：欄位、資料筆數與標籤分布

## 預測 API 與監控網頁

需要先產生真實資料的多類別模型（`models/multiclass_random/random_forest.joblib`）與前處理器（`dataset/processed/preprocessor.joblib`）——這兩個檔案是從真實 CIC-IDS2017 資料衍生出來的，體積較大，不納入版本控制，需要照上面「快速開始」的步驟自己跑一次 `prepare_data` + `train_baseline --target label` 產生。

```powershell
python -m pip install -r requirements.txt
python -m uvicorn api.main:app --reload
```

啟動後開啟 http://127.0.0.1:8000 即可看到監控網頁（`web/index.html`，由 API 直接掛載提供）；API 本身另外提供：

- `GET /health`：健康檢查
- `GET /model-info`：模型、隨機／時間／跨日期驗證與校準摘要
- `GET /samples`：97 筆平衡的真實測試流量，包含各類別的正確與錯誤案例
- `POST /predict`：輸入一筆原始尺度流量的 80 個特徵值，回傳攻擊類型、信心與前三名候選

網頁定位為「CIC-IDS2017 威脅流量重播實驗室」，不是正式即時監控。可依場景重播、暫停或逐筆分析真實標記流量，並同步更新攻擊趨勢、偵測分布、事件紀錄與高風險漏報。資料集 Ground Truth 只在評估模式中顯示。

如需重建網頁的平衡重播樣本：

```powershell
python -m src.build_demo_samples
```

## 專案結構

```text
data/       原始與處理後資料
models/     訓練完成的模型
notebooks/  探索性分析
results/    評估結果
src/        資料處理與模型程式
api/        預測 API
web/        監控介面
tests/      自動化測試
```
