from dataclasses import dataclass
from typing import List, Dict, Tuple
import random


# ========== Model ==========
@dataclass
class Schedule:
    dayName: str
    day: int  # 1=Mon ... 7=Sun (default: Senin–Sabtu)
    timeStart: int  # detik dari awal hari (00:00)
    timeEnd: int  # detik dari awal hari (00:00)
    sks: int


# ========== Util ==========
DAY_NAMES = {
    1: "Senin",
    2: "Selasa",
    3: "Rabu",
    4: "Kamis",
    5: "Jumat",
    6: "Sabtu",
    7: "Minggu",
}


def sks_to_seconds(sks: int) -> int:
    # 1 SKS = 50 menit
    return sks * 50 * 60


def overlaps(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    # interval overlap (tertutup di start, terbuka di end): [start, end)
    return not (a[1] <= b[0] or b[1] <= a[0])


# ========== Generator ==========
def generate_dummy_schedule(
    target_sks: int = 24,
    seed: int = 42,
    days: List[int] = [1, 2, 3, 4, 5, 6],  # Senin–Sabtu
    day_start_sec: int = 7 * 3600,  # 07:00
    day_end_sec: int = 18 * 3600,  # 18:00
    gap_between_classes_sec: int = 10 * 60,  # jeda antar kelas (opsional)
    allowed_sks_options: List[int] = [1, 2, 2, 3, 3],  # bobot sampling SKS
) -> List[Schedule]:
    """
    Membuat jadwal acak tanpa bentrok per hari, total SKS <= target_sks.
    """
    # random.seed(seed)

    schedules: List[Schedule] = []
    by_day: Dict[int, List[Tuple[int, int]]] = {d: [] for d in days}
    total_sks = 0

    attempts = 0
    max_attempts = 5000

    # bantu: cari semua slot bebas pada hari tertentu
    def can_place(d: int, start: int, end: int) -> bool:
        # Perhitungkan gap antar kelas
        s = max(day_start_sec, start - gap_between_classes_sec)
        e = min(day_end_sec, end + gap_between_classes_sec)
        for xs, xe in by_day[d]:
            if overlaps((s, e), (xs, xe)):
                return False
        return True

    while total_sks < target_sks and attempts < max_attempts:
        attempts += 1

        # pilih SKS yang tidak melewati target
        sks_choices = [k for k in allowed_sks_options if total_sks + k <= target_sks]
        if not sks_choices:
            break
        sks = random.choice(sks_choices)
        dur = sks_to_seconds(sks)

        # acak hari
        d = random.choice(days)
        # acak start time yg valid
        latest_start = day_end_sec - dur
        if latest_start <= day_start_sec:
            # durasi terlalu panjang untuk window harian
            continue

        # beberapa kali coba pasang pada hari d
        placed = False
        for _ in range(100):
            start = random.randint(day_start_sec, latest_start)
            end = start + dur
            if can_place(d, start, end):
                by_day[d].append((start, end))
                by_day[d].sort()  # rapikan
                schedules.append(Schedule(DAY_NAMES[d], d, start, end, sks))
                total_sks += sks
                placed = True
                break

        # bila gagal pasang, coba lagi kombinasi lain
        if not placed:
            continue

    # urutkan final: (day, timeStart)
    schedules.sort(key=lambda x: (x.day, x.timeStart))
    return schedules


import pandas as pd


def generate_jadwal():
    jadwal = generate_dummy_schedule(target_sks=random.randint(20, 24), seed=17)
    jadwal_df = pd.DataFrame(
        [
            {
                "Hari": j.dayName,
                "Hari_ke": j.day,
                "Mulai (detik)": j.timeStart,
                "Selesai (detik)": j.timeEnd,
                "Durasi (menit)": round((j.timeEnd - j.timeStart) / 60, 1),
                "SKS": j.sks,
            }
            for j in jadwal
        ]
    )
    return jadwal_df
