# 留一攻擊類型泛化測試

本實驗每次將一種攻擊類型完全移出分類器訓練，再觀察二元模型能否仍將其辨識為攻擊，以及封閉式多類別模型會把它歸到哪個已知類別。另以相同抽樣上限、模型參數與測試資料建立『看過該攻擊』的 matched control，避免把訓練規模差異誤認成未知攻擊造成的退步。這不是完整的未知攻擊偵測器，因為模型沒有 `UNKNOWN` 輸出。

## 結果

| 留出攻擊 | 原始樣本數 | 測試筆數 | 看過時 Recall | 未見時 Recall | 下降 | 未見時高信心漏報 | 正常誤報率 | 多類別看過時正確率 | 未見時判成 BENIGN | 最常被迫歸類為 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Bot | 1,966 | 392 | 99.23% | 0.00% | 99.23% | 100.00% | 0.22% | 99.23% | 100.00% | BENIGN |
| DDoS | 128,027 | 20,000 | 99.97% | 63.40% | 36.57% | 32.98% | 0.30% | 99.94% | 41.38% | PortScan |
| DoS GoldenEye | 10,293 | 2,088 | 99.86% | 57.04% | 42.82% | 4.26% | 0.26% | 99.90% | 46.31% | DoS Hulk |
| DoS Hulk | 231,072 | 20,000 | 99.97% | 64.03% | 35.94% | 8.99% | 0.20% | 99.88% | 83.22% | BENIGN |
| DoS Slowhttptest | 5,499 | 1,081 | 100.00% | 89.18% | 10.82% | 5.55% | 0.24% | 99.44% | 18.59% | DoS slowloris |
| DoS slowloris | 5,796 | 1,146 | 99.91% | 97.73% | 2.18% | 0.00% | 0.27% | 99.74% | 34.64% | DoS Slowhttptest |
| FTP-Patator | 7,938 | 1,598 | 100.00% | 33.04% | 66.96% | 0.00% | 0.30% | 100.00% | 68.40% | BENIGN |
| PortScan | 158,930 | 20,000 | 99.99% | 0.34% | 99.66% | 97.78% | 0.21% | 99.95% | 99.92% | BENIGN |
| SSH-Patator | 5,897 | 1,191 | 100.00% | 48.11% | 51.89% | 50.63% | 0.29% | 99.75% | 53.57% | BENIGN |
| Web Attack – Brute Force | 1,507 | 308 | 99.68% | 92.21% | 7.47% | 0.00% | 0.32% | 92.21% | 15.91% | Web Attack – XSS |
| Web Attack – XSS | 652 | 120 | 99.17% | 96.67% | 2.50% | 0.83% | 0.30% | 54.17% | 4.17% | Web Attack – Brute Force |

## 主要發現

- 在完全相同的抽樣與模型設定下，11 類攻擊『看過時』的二元 Recall 等權平均為 **99.80%**，移除該類後降為 **58.34%**，平均下降 **41.46%**。未見攻擊 Recall 的中位數為 **63.40%**，依本次測試筆數加權後為 **44.65%**。
- 最弱的三類是 `Bot`（0.00%）、`PortScan`（0.34%）、`FTP-Patator`（33.04%）。
- 最能從其他攻擊特徵泛化的三類是 `DoS slowloris`（97.73%）、`Web Attack – XSS`（96.67%）、`Web Attack – Brute Force`（92.21%）。
- 高信心漏報最嚴重的是 `Bot`（100.00%）、`PortScan`（97.78%）、`SSH-Patator`（50.63%）；此處『高信心漏報』指全部留出攻擊中，被判為 BENIGN 且預測信心至少 80% 的比例。
- 各次實驗的正常流量誤報率約落在 **0.20%–0.32%**，表示上述 Recall 差異不是靠大幅提高正常流量誤報換來的。
- 多類別模型有時會將未見攻擊歸入另一個已知攻擊，其中部分同屬相近家族：`DDoS` → `PortScan`；`DoS GoldenEye` → `DoS Hulk`；`DoS Slowhttptest` → `DoS slowloris`；`DoS slowloris` → `DoS Slowhttptest`；`Web Attack – Brute Force` → `Web Attack – XSS`；`Web Attack – XSS` → `Web Attack – Brute Force`。其餘類型最常被迫歸為 BENIGN。

## 實驗限制

- CIC-IDS2017 的每種攻擊只出現在單一日期，因此攻擊型態與日期／場景仍然糾纏；本實驗不能單獨估計純粹的跨日期漂移。
- 多類別模型沒有 `UNKNOWN` 類別，所以此處衡量的是強制錯分行為，不是宣稱已能識別未知攻擊。
- 為控制訓練時間，各類別使用可重現的上限抽樣；matched control 與留一類模型使用相同上限、模型參數和測試資料，因此適合比較『看過 vs 未見』的差值，但原始樣本數仍列在表中，絕對分數只代表這次設定。
- 輸入來自既有清理後數值資料，並在每次實驗中以該次訓練樣本重新 fit 標準化器；留出攻擊不參與分類器與這次標準化器的 fit。
- 95% Wilson 區間把每列流量視為獨立二項試驗；同一攻擊場景的流量實際高度相關，因此區間可能偏窄，只作逐列描述，不代表跨場景的不確定性。
- 樣本極少的類別不納入主要比較，不能將不足樣本解讀為模型已經或尚未學會該攻擊。

## 未納入主要比較的少數類別

- `Heartbleed`：11 筆
- `Infiltration`：36 筆
- `Web Attack – Sql Injection`：21 筆

## 執行設定

```json
{
  "processed_dir": "dataset\\processed",
  "random_state": 42,
  "min_attack_samples": 500,
  "max_train_per_class": 20000,
  "max_holdout_per_attack": 20000,
  "benign_test_size": 20000,
  "n_estimators": 50,
  "confidence_threshold": 0.8,
  "matched_control": true,
  "selected_attacks": [
    "Bot",
    "DDoS",
    "DoS GoldenEye",
    "DoS Hulk",
    "DoS Slowhttptest",
    "DoS slowloris",
    "FTP-Patator",
    "PortScan",
    "SSH-Patator",
    "Web Attack  Brute Force",
    "Web Attack  XSS"
  ]
}
```
