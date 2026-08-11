import pandas as pd

train = pd.read_csv("data/processed/train.csv")
test = pd.read_csv("data/processed/test.csv")

# 第一步：把「答案」欄位切出來
y_train = train["is_attack"]      # 提示：哪一欄是 0/1 的攻擊標籤？（不是文字的那個）
y_test = test["is_attack"]

# 第二步：把「答案」相關的欄位都排除，剩下的才是輸入特徵
# 要排除兩欄：一個是上面用過的答案欄，另一個是文字版的標籤（不能當數字特徵用）
X_train = train.drop(columns=["is_attack", "label"])
X_test = test.drop(columns=["is_attack", "label"])

print(X_train.shape)
print(y_train.value_counts())

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

model = LogisticRegression()
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
print(accuracy_score(y_test, y_pred))
print(y_test.value_counts())
from sklearn.metrics import confusion_matrix

cm = confusion_matrix(y_test, y_pred)
print(cm)