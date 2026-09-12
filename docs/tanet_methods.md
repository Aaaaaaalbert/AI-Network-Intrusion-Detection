# TANET：切分策略與特徵群消融

研究問題：資料切分策略與捷徑特徵如何共同影響 Random Forest 在 CIC-IDS2017 上的表面效能與泛化能力？

## 方法

使用 dataset/raw 的八個 CSV，沿用 clean_data 的去重、缺失標籤移除、無窮值轉缺失值規則。識別欄位（Flow ID、IP、Timestamp、source_file）與標籤不進入特徵。Random Stratified 直接按完整 15 類 label 分層，80% 訓練、20% 測試、seed=42；Temporal 沿用每類各自時間排序後前 80% 訓練、後 20% 測試。Temporal 不是全域時間切分，也不是跨場景或未見攻擊測試；相同 timestamp 的資料仍可能跨界。

每種切分固定列索引，分別評估 Full（80 欄）、−Port（只移除 source_port、destination_port）、−TCP-window（只移除 init_win_bytes_forward、init_win_bytes_backward）。TCP flags 保留，另行消融屬 optional。每組皆為 100 棵樹、class_weight=balanced、random_state=42 的 Random Forest；前處理只在各自訓練集擬合。對既有 temporal Full，驗證欄位順序、資料筆數、前處理輸出與四項歷史指標一致才重用模型。

執行：`python -m src.run_research`。結果存於 results/tanet_split_ablation；comparison.csv 是六組比較表，每組包含 metrics.json、per_class.csv（含 Recall 及 support）、confusion_matrix.csv（列為真值、欄為預測）與完整 predictions.csv。索引、資料指紋、設定及各 split 的 support 一併保存。只有同設定完成的 metrics.json 才跳過；變更資料或設定請改用新的 --output-dir。歷史結果不覆寫。

## 方法限制：為何不採用 IP-pair Group Split

IP-pair 診斷以清理後資料逐類計算有方向及無方向的唯一來源／目的 IP 配對，並回報最大配對占比與五元組數量。IP pair 只表示主機配對，不能直接等同具時間界線的 session；五元組也不等於獨立攻擊場景。精確統計以 ip_pair_diagnostics.csv 為準，須區分「只有一組」與「主要集中於一組」。

當一個攻擊類別只存在於單一 IP-pair group 時，若要求 group 不跨訓練與測試，便無法同時在兩側保留該類。強制切分將使該類完全缺席於其中一側，評估因而混入 attack-holdout／跨場景因素，無法形成公平的同類 train/test 對照。因此本研究不採用 IP-pair Group Split，也不以相似度分群或僅 BENIGN/Bot 的局部分組替代，而將群組集中現象作為資料集結構與偏差風險的證據。

Random split 可能因 session／場景高度相似而過度樂觀，但群組集中本身並不能證明已發生洩漏，也不能定量解釋全部效能差距。特徵消融衡量的是指定特徵群在各切分下的預測貢獻，不足以單獨證明捷徑的因果機制。可比較各 split 的 Full 與消融差值，再比較兩種 split 的差值，作為交互影響的描述性分析；單一 seed 不支持統計顯著性宣稱。

Heartbleed、Infiltration、SQL Injection 必須將 Recall 與測試 support 同時呈現；極少測試樣本下，一筆預測即可使 Recall 大幅變動，不可過度解讀單次 Recall 或將其視為穩定泛化能力。資料僅來自 CIC-IDS2017，亦不支持直接外推至真實部署。

## 歷史結果的角色

舊 multiclass_random 使用 is_attack 二元分層，不能標為本次 15 類分層；舊 no_port_ablation 同時移除 port 與 TCP window，不能當作本次任一獨立消融。舊 by-day 與 leave-one-attack-out 為不同研究問題，保留作背景資料，不混入六組主表。

## 已驗證的資料結構

清理後 2,830,540 筆、15 類：無方向 IP pair 為 BENIGN 61,978 組、Bot 7 組，其餘 13 類攻擊各 1 組（各類占比 100%）。有方向配對為 BENIGN 113,764、Bot 12、DDoS 2，其餘攻擊各 1；所有類別皆無缺失 IP。五元組數量另列於診斷表，不能與 IP pair 或真正 session 混稱。


已驗證 Random Stratified 的罕見類別測試 support：Heartbleed 2、Infiltration 7、SQL Injection 4。分別一筆錯誤即可改變 Recall 50、14.29、25 個百分點。

六組完成後執行：python -m src.summarize_research，驗證 confusion matrix 與 support、Accuracy 一致並產生 comparison.md。


## 六組實驗完成結果

Full、−Port、−TCP-window 的 Macro F1：Random Stratified 分別 90.7194%、86.1230%、90.5470%；Temporal 分別 74.0096%、79.1086%、74.2325%。移除 Port 在 Random 下降 4.5963 個百分點，在 Temporal 上升 5.0990 個百分點，兩種切分的消融效果差為 9.6954 個百分點。這是切分與特徵群共同影響表現的描述性證據，不是統計顯著性或因果證明。移除 TCP window 的影響分別為 −0.1724 與 +0.2229 個百分點。

六組混淆矩陣與逐類 support、Accuracy 一致；資料處理與欄位測試 14 項通過。必做六組無缺漏。尚未進行多 seed 重複、信賴區間、外部資料集驗證及 optional TCP flags 消融；不屬本次必做項目。Temporal Full 重用既有模型，其餘五組全量重訓，不使用抽樣。新訓練模型未另存權重；完整預測、設定與資料指紋已保存供重算指標及重現訓練。
