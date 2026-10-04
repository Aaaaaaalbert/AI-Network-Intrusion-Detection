# 陳冠庭的研究貢獻

陳冠庭（GitHub：[ghjkl563563-stack](https://github.com/ghjkl563563-stack)）參與本專案的 TANET 研究。以下依 2026-10-01 的 v2 工作貢獻分工表整理，保留原表的歸屬限制；這份說明不是雙方已簽署的最終分工。

## 實驗與分析工具

v2 將下列工作列於陳冠庭主導的 F 段。「主導」指發起與決策，不表示所有程式及文字均由本人手寫。原表記錄 F6–F14 曾由 Claude 協助設計、實作、分析或撰寫。

| 編號 | 貢獻 | 公開內容或原表說明 |
| --- | --- | --- |
| F5 | 將隨機切分改為依 15 類標籤分層，補充測試 | [前處理程式](../src/prepare_data.py)、[測試](../tests/test_prepare_data.py) |
| F6 | 推進配對式測試集 bootstrap 信賴區間分析 | [bootstrap 程式](../src/bootstrap_ci.py) |
| F7 | 推進固定切分下的多 seed 重複實驗，3 個 seed × 4 組設定 | [實驗程式](../src/multiseed_ablation.py)、[結果](../results/tanet_multiseed/runs.csv) |
| F8 | 逐類別機制分析，包括 Slowhttptest 與 XSS 的 Port 消融差異 | [逐類別結果](../results/tanet_split_ablation/per_class_port_delta.csv) |
| F9 | 製作論文圖表 | [圖表程式](../src/make_paper_figures.py)、[單欄圖表程式](../src/make_column_figures.py) |
| F10 | 製作符合官方範本的論文排版產生器 | 依 v2 記錄；終稿未使用此排版，該產生器未包含於目前公開版本 |
| F11 | 推進論文初稿，包括中英文摘要、正文、表格與圖 | 依 v2 記錄；初稿為後續終稿改寫的基礎，未在此公開 |
| F12 | 整理與查證初版參考文獻 | 依 v2 記錄；包含更正兩筆引用的作者資訊 |
| F13 | 整理投稿檢查清單 | 依 v2 記錄；未包含於目前公開版本 |
| F14 | 修正 bootstrap 聯合重抽樣，保留跨切分測試集的 113,076 筆重疊 | [方法說明](bootstrap_overlap_note.md)；依 v2，回應陳弈紹的方法學審查 |

## 六組消融研究的初始分工

v2 將以下四項列為陳冠庭的工作，但也註明依據為陳冠庭的陳述，初始作者仍待雙方確認：

- **F1：**研究問題與 2 × 3 因子設計（切分策略 × 特徵群消融）。
- **F2：**六組實驗的執行框架與全量訓練；沿用既有前處理、基準模型設定，並重用既有多類別模型。
- **F3：**IP 配對結構診斷。
- **F4：**六組結果的一致性檢查。

相關公開內容：[方法文件](tanet_methods.md)、[實驗框架](../src/run_research.py)、[結果彙整程式](../src/summarize_research.py)、[六組結果](../results/tanet_split_ablation/comparison.md)。

## 文件與版本紀錄

v2 的 H1 另記錄陳冠庭推進分工表的整理，由 Claude 依其陳述協助撰寫；原表亦註明陳弈紹尚未確認。G 段與分工表 Word 產生器 H2 的歸屬仍有待確認，本說明不將它們列為已確定的個人成果。

公開研究內容已經由 [PR #2](https://github.com/Aaaaaaalbert/AI-Network-Intrusion-Detection/pull/2) 合併。五筆研究提交（209e2ce、6fdd29e、6929abd、ea94940、336015c）以陳冠庭署名，因此 v2 中「尚未推送、提交作者誤記」的描述已過時。提交作者欄記錄版本貢獻，不能單獨證明研究發想或每個檔案的初始作者。
