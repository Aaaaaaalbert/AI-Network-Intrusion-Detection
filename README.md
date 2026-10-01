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

## License

MIT


## 研究協作

- [ghjkl563563-stack](https://github.com/ghjkl563563-stack)：參與六組消融實驗、bootstrap 分析與多 seed 實驗。

上述分工依專案負責人確認列示；相關研究程式與結果尚未全部公開。
