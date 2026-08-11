from pathlib import Path


def find_csv_files(raw_dir: Path) -> list[Path]:
    csv_files = list(raw_dir.rglob("*.csv"))
    return csv_files


files = find_csv_files(Path("dataset/raw"))

print(files)
print("找到的檔案數量：", len(files))

def check_file_count(count):
    if count == 0:
        raise FileNotFoundError("沒有找到任何檔案")

    return "有找到檔案"

#print(check_file_count(0))
print(check_file_count(8))