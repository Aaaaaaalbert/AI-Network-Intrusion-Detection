# CIC-IDS2017 raw data

Download the **MachineLearningCSV** files from the official CIC-IDS2017 dataset page and place the extracted `.csv` files in this directory. Subdirectories are supported.

Expected layout (filenames can vary):

```text
dataset/raw/
  MachineLearningCSV/
    Monday-WorkingHours.pcap_ISCX.csv
    Tuesday-WorkingHours.pcap_ISCX.csv
    ...
```

The dataset is intentionally not committed or downloaded automatically because it is large and its use is subject to the provider's terms. The analysis notebook discovers every CSV recursively.
