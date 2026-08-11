# AI Network Intrusion Detection

使用機器學習分析網路流量，判斷連線是正常流量或攻擊，並輸出攻擊類型與信心分數。

## 專案進度

- Day 1：建立專案結構與系統目標
- Day 2：完成資料載入、清理、切分與標準化管線
- Day 3：訓練並比較基準模型
- Day 4：模型評估與錯誤分析
- Day 5：建立預測 API
- Day 6：建立監控介面
- Day 7：整合測試與部署文件

## Day 2 快速開始

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

預設會辨識 `Label` 或 `label` 作為目標欄位，將 `BENIGN`、`NORMAL`、`0` 視為正常，其餘標籤視為攻擊。輸出包括：

- `train.csv`：模型訓練資料
- `test.csv`：保留的測試資料
- `preprocessor.joblib`：只用訓練集擬合的資料轉換器
- `metadata.json`：欄位、資料筆數與標籤分布

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
