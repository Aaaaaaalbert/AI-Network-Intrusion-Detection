# Random Forest 切分方式驗證報告

## 實驗問題

隨機逐列切分可能把同一捕獲場景中的相似流量分到訓練集與測試集，造成模型表現過度樂觀。因此保留原本隨機切分作為對照，另以星期一至四訓練、星期五測試，檢查跨日期與未見攻擊場景的泛化能力。

兩組實驗使用相同的 Random Forest 設定：100 棵樹、`class_weight="balanced"`、`random_state=42`。來源檔名只用於切分與稽核，不進入模型特徵。

## 整體結果

| 指標 | 隨機逐列切分 | 星期一至四訓練、星期五測試 |
|---|---:|---:|
| 測試筆數 | 566,108 | 703,240 |
| Accuracy | 99.96% | 62.16% |
| Precision | 99.92% | 99.65% |
| Recall | 99.86% | 7.93% |
| F1 | 99.89% | 14.70% |
| Balanced Accuracy | 99.92% | 53.96% |
| False Positive | 86 | 81 |
| False Negative | 154 | 265,999 |

跨日期測試的 Precision 仍高，表示模型判定為攻擊時通常正確；但 Recall 大幅下降，代表模型過度保守，將大多數星期五攻擊判成正常流量。

## 星期五各攻擊類型

| 攻擊類型 | 測試筆數 | 漏報筆數 | Recall |
|---|---:|---:|---:|
| Bot | 1,966 | 1,966 | 0.00% |
| DDoS | 128,027 | 105,227 | 17.81% |
| PortScan | 158,930 | 158,806 | 0.08% |

## 補充分析：隨機切分模型還有沒有其他捷徑？

在確認按日期切分的結果之前，也對隨機切分訓練出的 Random Forest 做了幾項額外檢查，確認 99.86% 這個高分不是單一手法造成的巧合。

- **特徵重要性**（`results/rf_feature_importance.csv`）：Random Forest 內建重要性顯示 `destination_port`、`average_packet_size`、`packet_length_std` 等排名最高。
- **Permutation importance**（`results/rf_permutation_importance.csv`）：改用打亂單一欄位、觀察分數下降幅度的方式重新驗證，`destination_port` 同樣是影響最大的欄位，兩種方法互相印證，不是單一計算方式的巧合。
- **Port ablation**（`results/random_forest_no_port_ablation.json`）：拿掉 `destination_port`、`source_port`、`init_win_bytes_forward`、`init_win_bytes_backward` 後重新訓練，Recall 從 99.86% 降到 98.92%、Precision 從 99.92% 降到 95.11%。分數仍然很高，顯示模型不是「只靠 port 猜答案」，但 port 類特徵確實貢獻了一部分準確度——這與後續「模型是否靠資料集特有的捷徑作弊」的疑慮同一類，值得留意。
- **隨機切分下的逐類別 Recall**（`results/random_forest_per_class_recall.csv`）：多數攻擊類型 Recall 在 99% 以上，但樣本極少的類別已開始不穩定，例如 `Web Attack Sql Injection`（4 筆中漏 2 筆，Recall 50%）、`Bot`（392 筆，Recall 93.11%，是除 SQL Injection 外最低的類別）。這預告了後續多類別模型會遇到的類別不平衡問題。

## 結論與限制

結果顯示，原本的高分只能代表模型對「與訓練資料同分布」的隨機測試集表現很好，不能代表它能辨識新的日期或新的攻擊場景。跨日期測試幾乎無法辨識星期五攻擊，尤其是 Bot 與 PortScan。

不過，CIC-IDS2017 的攻擊類型與日期高度綁定：星期五的 Bot、DDoS、PortScan 在星期一至四訓練資料中沒有出現。因此這次實驗同時改變了日期與攻擊類型，測到的是更嚴格的「跨日期、未見攻擊類型」泛化能力，不能把全部差距單純歸因於資料洩漏。

## 後續建議

1. 保留兩組結果，在報告中明確區分 IID 隨機測試與跨日期 OOD 測試。
2. 下一階段建立多類別模型，完成原始專案的攻擊類型辨識目標。
3. 若要辨識真正未見攻擊，可另外研究 anomaly detection，而不是只依靠監督式 Random Forest。
4. 後續比較模型時，不只回報 Accuracy，也回報 Recall、F1、Balanced Accuracy 與各攻擊類型表現。
