import pandas as pd

# ganti path ke lokasi file kamu
file_path = "kelas praktikum baru.xlsx"

# baca semua sheet
excel = pd.ExcelFile(file_path)

# misal pilih sheet pertama
dataset_df = pd.read_excel(excel, sheet_name=excel.sheet_names[0])
