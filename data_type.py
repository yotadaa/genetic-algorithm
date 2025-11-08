from __future__ import annotations

import pandas as pd
import random


from dataset import dataset_df
from assistant_schedule import generate_jadwal
import uuid

from dataclasses import dataclass, asdict, field
from typing import List, Dict, Tuple

from pathlib import Path
import re
import math

columns = [
    "id_prodi",
    "nama_prodi",
    "nama_matakuliah",
    "kode_matakuliah",
    "sks_praktek",
    "semester",
    "jumlah_peserta",
]


"""
#gen 1: matakuliah + semester + aslab + kelas + jumlah_peserta
#gen 2: hari + jam
#gen 3: ruangan + kapasitas

The provided code snippet is part of a scheduling system for academic courses. It includes functions to generate a dummy schedule for students based on certain parameters such as total credit hours (SKS), days of the week, and time slots. The code also imports the pandas library to handle data in DataFrame format.

Things to add or improve:
-- add classifier for subject and lab, 
-- specific subject can only attend specific lab, 
--- e.g A subject that require microlab tools would attend the Micro-Biologi Lab only,
--- as it is the best fit lab for the subject
--- this can be put in seeder
"""

"""
    Seeder, a seeder function to generate schedule data. Seeder return:
    +-------------------+------------------+
    | Matakuliah        |                  |
    | Semester          |                  |
    | Kelas             |   Gen A          |
    | Jumlah_Peserta    |                  |
    | Aslab             |                  |
    +-------------------+------------------+
    | Hari              |                  |
    | Jam Mulai         |   Gen B          |
    | Jam Selesai       |                  |
    +-------------------+------------------+
    | Ruangan           |   Gen C          |
    | Kapasitas         |                  |
    +-------------------+------------------+

    The seed then put into individuals, a seed, we can call it a Gene
    Individuals will have multiple genes, each gene represent a part of the schedule
    
    Individuals --> Gene[]
    
    Individuals then put into clusters, a cluster represent a batch of individuals
    We call it Population --> Individual[].
"""


@dataclass
class Gene:
    subject_name: str
    subject_id: str
    semester: int
    sks: int
    capacity: int
    assistant: List[AssistantSchedule]
    preferred_lab: List[Room]
    day_name: str
    day: int
    start_time: int
    end_time: int
    room_id: int
    group: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass
class Room:
    id: int
    room_name: str
    room_capacity: int


@dataclass
class AssistantSchedule:
    id: str
    day_name: List[str]
    day: List[int]
    start_time: List[int]
    end_time: List[int]
    duration: List[int]
    sks: List[int]


def _sec_to_hms_str(sec: int) -> str:
    """Konversi detik ke 'HH:MM:SS' (untuk csv/parquet)."""
    if pd.isna(sec):
        return ""
    sec = int(sec)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


@dataclass
class Individuals:
    chromosome: List[Gene]

    def to_dataframe(self) -> pd.DataFrame:
        data = []
        for gene in self.chromosome:
            assistants_info = [
                {
                    "assistant_id": a.id,
                    # "days": a.day_name,
                    # "start_times": a.start_time,
                    # "end_times": a.end_time,
                }
                for a in gene.assistant
            ]
            labs_info = [r.room_name for r in gene.preferred_lab]

            data.append(
                {
                    "gene_id": gene.id,
                    "subject_name": gene.subject_name,
                    "subject_id": gene.subject_id,
                    "semester": gene.semester,
                    "sks": gene.sks,
                    "capacity": gene.capacity,
                    "assistant_info": assistants_info,
                    "preferred_lab": labs_info,
                    "day_name": gene.day_name,
                    "day": gene.day,
                    "start_time": gene.start_time,
                    "end_time": gene.end_time,
                    "room_id": gene.room_id,
                    "group": gene.group,
                }
            )

        return pd.DataFrame(data)

    def save_dataframe(
        self,
        path: str = "./output",
        name: str = "output_schedule",
        ext: str = "csv",
        **to_file_kwargs,
    ) -> str:
        """
        Simpan hasil to_dataframe() tanpa menimpa file lama.
        Tambah kolom: start_converted, end_converted.
        - .xlsx: pakai rumus Excel =TIME(INT(...), INT(MOD(...)), MOD(...))
        - .csv/.parquet: diisi hasil konversi 'HH:MM:SS'
        Kolom disejajarkan: subject_id, group, day_name, start_converted, end_converted, room_id.
        """
        df = self.to_dataframe().copy()

        out_dir = Path(path)
        out_dir.mkdir(parents=True, exist_ok=True)

        # cari nomor urut terakhir untuk pola: <name>_<n>.<ext>
        pattern = re.compile(
            rf"^{re.escape(name)}_(\d+)\.{re.escape(ext)}$", re.IGNORECASE
        )
        existing_nums = []
        for p in out_dir.iterdir():
            if p.is_file():
                m = pattern.match(p.name)
                if m:
                    try:
                        existing_nums.append(int(m.group(1)))
                    except ValueError:
                        pass

        next_idx = (max(existing_nums) + 1) if existing_nums else 1
        out_path = out_dir / f"{name}_{next_idx}.{ext}"

        # pastikan kolom wajib ada
        required_cols = [
            "start_time",
            "end_time",
            "subject_id",
            "group",
            "day_name",
            "room_id",
        ]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise KeyError(f"Kolom wajib hilang: {missing}")

        ext_lower = ext.lower()

        if ext_lower == "csv":
            # isi konversi sebagai literal HH:MM:SS
            df["start_converted"] = df["start_time"].apply(_sec_to_hms_str)
            df["end_converted"] = df["end_time"].apply(_sec_to_hms_str)

            # reorder kolom
            head = [
                "subject_id",
                "group",
                "day_name",
                "start_converted",
                "end_converted",
                "room_id",
            ]
            tail = [c for c in df.columns if c not in head]
            df = df[head + tail]

            df.to_csv(
                out_path, index=to_file_kwargs.pop("index", False), **to_file_kwargs
            )

        elif ext_lower == "parquet":
            df["start_converted"] = df["start_time"].apply(_sec_to_hms_str)
            df["end_converted"] = df["end_time"].apply(_sec_to_hms_str)

            head = [
                "subject_id",
                "group",
                "day_name",
                "start_converted",
                "end_converted",
                "room_id",
            ]
            tail = [c for c in df.columns if c not in head]
            df = df[head + tail]

            df.to_parquet(
                out_path, index=to_file_kwargs.pop("index", False), **to_file_kwargs
            )

        elif ext_lower in ("xlsx", "xls"):
            # tulis dulu tanpa kolom converted
            # lalu tambahkan kolom formula ke worksheet untuk .xlsx
            # catatan: formula native didukung optimal di .xlsx; untuk .xls akan diisi nilai string sebagai fallback.
            use_formulas = ext_lower == "xlsx"

            # siapkan posisi kolom setelah ditambah (kita akan reorder dulu agar referensi cell gampang)
            # buat placeholder kolom converted supaya bisa direorder sekarang
            df["start_converted"] = ""
            df["end_converted"] = ""

            head = [
                "subject_id",
                "group",
                "day_name",
                "start_converted",
                "end_converted",
                "room_id",
            ]
            tail = [c for c in df.columns if c not in head]
            df = df[head + tail]

            # tulis ke excel
            # kalau engine tak dispesifikkan, pandas akan pilih xlsxwriter untuk .xlsx (disarankan)
            with pd.ExcelWriter(
                out_path, engine="xlsxwriter" if use_formulas else None
            ) as writer:
                df.to_excel(
                    writer, index=to_file_kwargs.pop("index", False), **to_file_kwargs
                )
                workbook = writer.book
                worksheet = writer.sheets[list(writer.sheets.keys())[0]]

                # cari index kolom (0-based) untuk referensi cell
                cols = {
                    col_name: idx for idx, col_name in enumerate(df.columns, start=1)
                }  # +1 karena excel kol A=1
                # kita perlu posisi 'start_time' dan 'end_time' untuk rumus
                # walau tak berada di head, kita sudah punya mappingnya
                start_col = cols["start_time"]
                end_col = cols["end_time"]
                sc_col = cols["start_converted"]
                ec_col = cols["end_converted"]

                # format jam
                time_fmt = workbook.add_format({"num_format": "hh:mm:ss"})

                # tulis formula per baris (mulai baris 2 karena header di baris 1)
                nrows = len(df)
                for r in range(2, nrows + 2):
                    if use_formulas:
                        # referensi cell: kolom by index → konversi ke huruf kolom
                        def col_letter(cidx: int) -> str:
                            # 1→A, 2→B ...
                            letters = ""
                            while cidx:
                                cidx, rem = divmod(cidx - 1, 26)
                                letters = chr(65 + rem) + letters
                            return letters

                        start_ref = f"{col_letter(start_col)}{r}"
                        end_ref = f"{col_letter(end_col)}{r}"

                        sc_ref = f"{col_letter(sc_col)}{r}"
                        ec_ref = f"{col_letter(ec_col)}{r}"

                        # Rumus: =TIME(INT(start/3600), INT(MOD(start,3600)/60), MOD(start,60))
                        sc_formula = f"=TIME(INT({start_ref}/3600),INT(MOD({start_ref},3600)/60),MOD({start_ref},60))"
                        ec_formula = f"=TIME(INT({end_ref}/3600),INT(MOD({end_ref},3600)/60),MOD({end_ref},60))"

                        worksheet.write_formula(sc_ref, sc_formula, time_fmt)
                        worksheet.write_formula(ec_ref, ec_formula, time_fmt)
                    else:
                        # fallback .xls: isi nilai string HH:MM:SS
                        s = df.iloc[r - 2]["start_time"]
                        e = df.iloc[r - 2]["end_time"]
                        worksheet.write(r - 1, sc_col - 1, _sec_to_hms_str(s), time_fmt)
                        worksheet.write(r - 1, ec_col - 1, _sec_to_hms_str(e), time_fmt)

        else:
            raise ValueError(
                f"Unsupported extension: {ext}. Use 'csv', 'xlsx', or 'parquet'."
            )

        return str(out_path)


ruang_list = [
    int(i) for i in dataset_df["id_ruang_kuliah"].unique().tolist() if pd.notna(i)
]


type Population = List[Individuals]
