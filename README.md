# AI Network Intrusion Detection

用 CIC-IDS2017 做網路入侵偵測，Random Forest 基準模型，輸出攻擊類型與信心分數。

做這個專案的過程中發現，模型在標準做法下的分數是假的，所以後半部大多在檢驗這件事。

## 結果

| 設定 | Binary Recall |
| --- | --- |
| 隨機切分 | 99.86% |
| 時序切分（週一–四訓練，週五測試） | 7.93% |
| LOAO，攻擊有在訓練集 | 99.80% |
| LOAO，該攻擊移除 | 58.34% |

LOAO 是 leave-one-attack-out，把某類攻擊整個抽掉不訓練再拿它測。11 種樣本夠的攻擊平衡後平均，掉了 41.46 個百分點。個別來看落差更大，Bot 從 99.23% 掉到 0，PortScan 從 99.99% 掉到 0.34%。

用 recall 是因為入侵偵測漏抓比誤報嚴重，加上這個資料集正常流量佔絕大多數，看準確率沒意義。

## 幾個觀察

隨機切分會把同一次攻擊連線的前後片段拆到訓練和測試兩邊，分數自然好看。改成用較早的日期訓練、較晚的測試之後掉到 7.93%，主要是因為週五出現了前四天沒有的攻擊類型——而這才是實際部署會遇到的情況。

LOAO 的結果更直接：模型對沒見過的攻擊幾乎沒有辨識力。Bot 那一欄是 0，不是接近 0。

比較意外的是漏抓的形態。模型不是判不出來，是**以很高的信心判成正常流量**。這代表信心分數不能直接拿來排告警的優先順序，否則最危險的那些會排在最後面。

## 內容

```
src/         前處理、訓練、評估
api/         預測 API，輸出攻擊類型、信心分數、top-3 候選
web/         流量重播與監控介面
results/     實驗結果與報告
notebooks/   探索分析
models/      模型與前處理器（太大，沒進版控）
tests/
dataset/     資料集取得說明
docs/        進度紀錄
```

詳細結果：
- [切分方式驗證](results/split_validation_report.md)
- [LOAO 完整結果](results/leave_one_attack_out/report.md)
- [開發歷程](docs/progress_log.md)

## 執行

Python 3.10+，`pip install -r requirements.txt`。

資料集沒有放進 repo，CIC-IDS2017 要自己去 UNB 官網下載，路徑設定見 [dataset/raw/README.md](dataset/raw/README.md)。

## 還沒做的

只有 Random Forest，沒有跟深度學習方法做系統性比較。LOAO 只涵蓋樣本數夠的 11 種攻擊，樣本太少的那幾類沒測。所有結論都建立在 CIC-IDS2017 這一個資料集上，沒有在別的資料集驗證過。

## 研究協作

- 陳冠庭（[ghjkl563563-stack](https://github.com/ghjkl563563-stack)）：依 v2 貢獻表，主導 TANET 研究的實驗與分析工具工作，包括 15 類標籤分層切分、bootstrap 信賴區間與跨切分重疊修正、多 seed 重複實驗、逐類別分析及論文圖表；另負責推進論文初稿、參考文獻查證、排版工具與投稿檢查清單。v2 記錄其中 F6–F14 使用 Claude 協助，不代表全部程式與文字均由本人手寫。
- 六組消融的研究設計、執行框架、IP 配對診斷與結果一致性檢查（F1–F4），v2 列為陳冠庭的工作，同時註明初始作者仍待雙方確認。完整範圍與註記見[陳冠庭貢獻說明](docs/contributions.md)。
- 已公開的相關程式與結果透過 [PR #2](https://github.com/Aaaaaaalbert/AI-Network-Intrusion-Detection/pull/2) 合併至 `main`，五筆研究提交均以陳冠庭署名。

公開內容包含[六組消融結果](results/tanet_split_ablation/comparison.md)、[保留跨切分重疊的 bootstrap 說明](docs/bootstrap_overlap_note.md)與[多 seed 結果](results/tanet_multiseed/runs.csv)。提交署名記錄程式版本的貢獻，論文各段落與圖表的詳細分工仍由共同作者核對。
