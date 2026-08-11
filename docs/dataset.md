# CIC-IDS2017 Dataset

## 資料來源

- 資料集：Canadian Institute for Cybersecurity 的 CIC-IDS2017。
- 官方頁面：<https://www.unb.ca/cic/datasets/ids-2017.html>
- 本專案使用官方提供的 MachineLearningCSV 流量特徵檔；大型原始資料不納入 Git。
- 下載並解壓縮後，將所有 CSV 放在 `dataset/raw/`（可含子目錄），再執行 `notebooks/01_dataset_analysis.ipynb`。

## 檔案構成

CIC-IDS2017 收錄五個工作日的正常與攻擊流量。MachineLearningCSV 通常依日期及時段拆成多個 CSV。Notebook 不依賴固定檔名，會遞迴讀取 `dataset/raw/**/*.csv`，並增加 `source_file` 欄位以保留來源。

## 特徵與標籤

- 標準 MachineLearningCSV 通常有 78 個流量特徵及 1 個 `Label` 欄位；實際欄位數會以本機檔案分析結果為準。
- Notebook 會去除欄名前後空白、轉成小寫 snake_case，並處理重複欄名。
- 原始多類別標籤保留在 `label`；會去除前後空白並統一已知拼字差異。
- 另建立 `binary_label`：`BENIGN` 為 `BENIGN`，其他標籤為 `ATTACK`，便於二元分類與不平衡分析。

## 攻擊類型

資料集通常包含 Brute Force、DoS、DDoS、Heartbleed、Web Attack、Infiltration、Bot 與 PortScan 等類型。Notebook 的 `label_distribution.csv` 才是目前下載版本實際包含的完整類別與筆數；不以文件中的預期清單取代實測結果。

## 資料品質與類別不平衡

Notebook 會輸出：

- 每個檔案與合併後的資料筆數、欄位數
- 欄位資料型態
- 完全重複列數
- 每欄缺失值與正負無限值數量
- 多類別及二元標籤分布與比例
- 數值特徵描述統計與相關係數

CIC-IDS2017 的 BENIGN 與各攻擊類別通常高度不平衡，少數攻擊類別可能非常稀少。因此後續切分必須採分層抽樣，模型評估應優先觀察 macro F1、per-class recall、PR-AUC 與 confusion matrix，而不只看 accuracy。

### 實際執行結果（2026-08-04，8 個官方 CSV，共 3,119,345 列 x 87 欄）

- 完全重複列：288,804 筆（約 9.3%）
- **`Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv`（總筆數 458,968）內有 288,602 筆是 85 欄全部為缺失值的空列**，佔該檔案六成以上。逐檔驗證確認：這批空列的數量恰好與 `Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv`（總筆數同為 288,602，且該檔案本身完全無缺失）相同，但內容並非該檔案資料被誤植——空列所有欄位皆為 NaN，並非 Infiltration 的實際數值，研判是官方檔案匯出時尾端附加的空白填充列，屬於資料集本身的品質問題，不是本專案前處理造成的。這批列必須直接刪除，不可補值，否則會污染整體統計量與相關係數分析。
- 無限值（inf）共 4,376 個，集中在 `flow_bytes_s`、`flow_packets_s`（流量除以持續時間，當 `flow_duration=0` 時產生）。
- 類別分布：`BENIGN` 2,273,097 筆（約 73%），最少數類別 `Heartbleed` 僅 11 筆、`Web Attack Sql Injection` 僅 21 筆、`Infiltration` 僅 36 筆，不平衡程度極高。
- 完整數字見 `results/eda/dataset_summary.json`、`data_quality.csv`、`label_distribution.csv`。

## 後續前處理決策

1. 將 `inf`、`-inf` 轉為缺失值；只用訓練集統計量進行補值，避免資料洩漏。
2. 移除完全重複列；是否移除跨檔重複流量需在切分前另行確認。
3. 依需求選擇二元或多類別標籤；保留原始 attack label 以利追蹤。
4. 以 stratified train/validation/test split 處理類別比例；極少類別不足以分層時需合併、重新取樣或明確揭露限制。
5. Scaling、encoding、feature selection 與任何 sampling 僅在訓練集 fit，再套用至 validation/test。
6. 對高相關、常數或近常數欄位做後續檢查，但不在 EDA 階段直接刪除。

## EDA 輸出

執行 Notebook 後，關鍵結果寫入 `results/eda/`：

- `dataset_summary.json`
- `file_summary.csv`
- `dtypes.csv`
- `data_quality.csv`
- `label_distribution.csv`
- `binary_label_distribution.csv`
- `numeric_summary.csv`
- `correlation_matrix.csv`
- `label_distribution.png`
- `binary_label_distribution.png`
- `correlation_heatmap.png`

若尚未放入 CSV，Notebook 會在載入階段顯示清楚的 `FileNotFoundError` 與資料放置方式，不會嘗試自動下載。
