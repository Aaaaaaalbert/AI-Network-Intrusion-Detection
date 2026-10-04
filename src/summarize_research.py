from pathlib import Path
import json
import pandas as pd
root=Path(__file__).resolve().parents[1]
out=root/'results/tanet_split_ablation'
rows=[]
rare=[]
for split in ['Random_Stratified','Temporal']:
    for group in ['Full','Minus_Port','Minus_TCP_window']:
        d=out/f'{split}_{group}'
        m=json.loads((d/'metrics.json').read_text())
        p=pd.read_csv(d/'per_class.csv')
        cm=pd.read_csv(d/'confusion_matrix.csv',index_col=0)
        assert len(p)==15 and cm.shape==(15,15)
        assert cm.to_numpy().sum()==m['test_rows']==p.support.sum()
        assert (cm.sum(axis=1).to_numpy()==p.support.to_numpy()).all()
        assert abs(cm.to_numpy().trace()/m['test_rows']-m['accuracy'])<1e-12
        rows.append('| '+' | '.join([split,group]+[f'{m[k]*100:.4f}%' for k in ['accuracy','macro_precision','macro_recall','macro_f1']])+' |')
        for _,r in p[p.label.str.contains('Heartbleed|Infiltration|Sql Injection')].iterrows():
            rare.append('| '+' | '.join([split,group,r.label.replace('\x96','–'),f'{r.recall*100:.2f}%',str(int(r.support))])+' |')
text='# 最終比較：15 類分類\n\n| Split | Features | Accuracy | Macro Precision | Macro Recall | Macro F1 |\n|---|---|---:|---:|---:|---:|\n'+'\n'.join(rows)
text+='\n\n## 罕見類別：Recall 必須搭配 support\n\n| Split | Features | Label | Recall | Test support |\n|---|---|---|---:|---:|\n'+'\n'.join(rare)
text+='\n\n六組皆已完成，混淆矩陣總和、逐類 support 與 Accuracy 相符。Temporal Full 經重新預測核對後重用歷史模型；其餘五組重新訓練。單一 seed，未執行多次重複、信賴區間或 optional TCP flags 消融。\n'
(out/'comparison.md').write_text(text,encoding='utf-8')
print('All six result tables verified; comparison.md generated.')
