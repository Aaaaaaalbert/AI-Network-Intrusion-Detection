# 留一攻擊實驗程式復原驗證（2026-08-31）

## 復原範圍

`src/leave_one_attack_out.py` 與 `tests/test_leave_one_attack_out.py` 曾被另一份三類、全量訓練版本覆蓋，且當時尚未納入 Git。此次依本專案對話中 2026-08-28 的原始編輯紀錄還原，不以報告中的數字反推或調參擬合結果。

復原僅恢復原實驗的程式與五個測試，不把三類全量實驗的數字混入原本 11 類 matched-control 成果。`results/leave_one_attack_out/` 的四份原成果全程未覆寫。

## 抽樣規則

- 分別讀取 `dataset/processed/train.csv` 與 `test.csv`，沒有先合併後重新切分。
- 每批 50,000 列，以隨機 priority 保留各類別樣本；訓練端 seed 為 42、測試端為 43。
- 訓練端每類最多 20,000 筆；測試端每種攻擊最多 20,000 筆，正常測試樣本也是 20,000 筆。
- 正常訓練資料與攻擊訓練資料沿用原程式的排列次序；每一輪只移除目標攻擊。
- matched control 使用相同訓練樣本池但不移除任何攻擊，與留一類模型使用同一組測試資料。
- 兩種 Random Forest 均為 50 棵樹、`class_weight="balanced"`、`random_state=42`、`n_jobs=-1`。

直接從原 `train.csv` 的標籤計數確認：每類上限後，控制組共 **111,675 筆**；其中 Bot 訓練列為 **1,574 筆**，所以留出 Bot 後是 **111,675 − 1,574 = 110,101 筆**。不能用全資料的 Bot 總數 1,966 筆代替訓練列數。

## 重跑與比對

在獨立暫存目錄執行：

```powershell
python -m src.leave_one_attack_out --output-dir C:\Users\User\AppData\Local\Temp\loao-recovery-7611f905700f49b6b8fa0574f513575e\reproduced
python -m unittest discover -s tests -v
```

| 原成果 | 核對範圍 | 結果 |
|---|---|---|
| `summary.csv` | 11 列 × 14 欄 | 數值與文字精確相同；整個檔案位元組相同 |
| `sample_predictions.csv` | 1,100 列 × 7 欄 | 數值與文字精確相同；整個檔案位元組相同 |
| `results.json` | 11 類的訓練筆數、標籤、信賴區間、控制組指標、分類分布與其他所有欄位 | JSON 解析後完全相等，數值差異為 0；僅字典鍵輸出次序不同 |
| `report.md` | 全文 | 整個檔案位元組相同 |

`results.json` 的鍵順序差異來自原程式使用 set 組合 `class_counts` 的鍵，不影響資料內容或訓練順序。此次比對按鍵和值核對 JSON，沒有將字典的呈現次序誤當成研究結果差異。

全部 **22/22 測試通過**。此為程式復原與數值重現的證據，不是對原實驗方法新增有效性保證；抽樣、資料相依性與既有前處理等研究限制仍需保留。

執行環境：Python 3.13.5、NumPy 2.1.3、pandas 2.2.3、scikit-learn 1.6.1。

## 原成果保護

復原前後逐檔計算 SHA-256，以下四份原成果均未變：

| 檔案 | SHA-256 |
|---|---|
| `report.md` | `918AF81A4D42F560BD7984A8AA31E2F7F963EFE8FD80CDD119928AF94C8D062A` |
| `results.json` | `0B0D1AE84D2D7F8E800665B9823425334D2224EC369CBD7EF9A86BD08EA1C2A8` |
| `sample_predictions.csv` | `555BDDF85514F1CF6AC8F124A0EFC31BEDE7EDA40A8E4F50A893BBD8E862388D` |
| `summary.csv` | `5419CA3648051ECC75835BA45C7F9EEAF3E3891AED737FDE68736DD81FEFBE49` |

被覆蓋後的三類版本已另行備份，復原版本也有備份；兩者分開存於 `C:\Users\User\AppData\Local\Temp\loao-recovery-7611f905700f49b6b8fa0574f513575e` 與其 `restored` 子目錄。暫存備份不是永久版本管理：下一次提交應將程式、測試、結果與相關紀錄一起納入 Git，後續重跑也應先指定新的輸出目錄。
