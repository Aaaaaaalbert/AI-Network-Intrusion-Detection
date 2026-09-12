# 最終比較：15 類分類

| Split | Features | Accuracy | Macro Precision | Macro Recall | Macro F1 |
|---|---|---:|---:|---:|---:|
| Random_Stratified | Full | 99.9368% | 97.1267% | 88.2563% | 90.7194% |
| Random_Stratified | Minus_Port | 99.8612% | 89.9590% | 84.1569% | 86.1230% |
| Random_Stratified | Minus_TCP_window | 99.8606% | 96.8166% | 88.1737% | 90.5470% |
| Temporal | Full | 97.5150% | 82.8031% | 74.9174% | 74.0096% |
| Temporal | Minus_Port | 97.3660% | 86.2717% | 79.6948% | 79.1086% |
| Temporal | Minus_TCP_window | 97.6434% | 82.2058% | 74.2639% | 74.2325% |

## 罕見類別：Recall 必須搭配 support

| Split | Features | Label | Recall | Test support |
|---|---|---|---:|---:|
| Random_Stratified | Full | Heartbleed | 100.00% | 2 |
| Random_Stratified | Full | Infiltration | 57.14% | 7 |
| Random_Stratified | Full | Web Attack – Sql Injection | 25.00% | 4 |
| Random_Stratified | Minus_Port | Heartbleed | 100.00% | 2 |
| Random_Stratified | Minus_Port | Infiltration | 57.14% | 7 |
| Random_Stratified | Minus_Port | Web Attack – Sql Injection | 25.00% | 4 |
| Random_Stratified | Minus_TCP_window | Heartbleed | 100.00% | 2 |
| Random_Stratified | Minus_TCP_window | Infiltration | 57.14% | 7 |
| Random_Stratified | Minus_TCP_window | Web Attack – Sql Injection | 25.00% | 4 |
| Temporal | Full | Heartbleed | 50.00% | 2 |
| Temporal | Full | Infiltration | 57.14% | 7 |
| Temporal | Full | Web Attack – Sql Injection | 50.00% | 4 |
| Temporal | Minus_Port | Heartbleed | 50.00% | 2 |
| Temporal | Minus_Port | Infiltration | 71.43% | 7 |
| Temporal | Minus_Port | Web Attack – Sql Injection | 25.00% | 4 |
| Temporal | Minus_TCP_window | Heartbleed | 50.00% | 2 |
| Temporal | Minus_TCP_window | Infiltration | 71.43% | 7 |
| Temporal | Minus_TCP_window | Web Attack – Sql Injection | 50.00% | 4 |

六組皆已完成，混淆矩陣總和、逐類 support 與 Accuracy 相符。Temporal Full 經重新預測核對後重用歷史模型；其餘五組重新訓練。單一 seed，未執行多次重複、信賴區間或 optional TCP flags 消融。
