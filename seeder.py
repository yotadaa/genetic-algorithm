import random, uuid

from data_type import Room, Gene, AssistantSchedule, Individuals, ruang_list

from dataset import dataset_df

from dataclasses import asdict

from typing import List, Tuple, Set

from assistant_schedule import generate_jadwal

from fitness import DAY_CLOSE, DAY_OPEN, _snap, overlap


def generate_assistant(N) -> List[AssistantSchedule]:
    result: List[AssistantSchedule] = []
    for _ in range(N):
        temp = generate_jadwal()
        schedule = AssistantSchedule(
            id=uuid.uuid4().hex,  # ← move UUID creation inside the loop
            day_name=temp["Hari"].tolist(),
            day=temp["Hari_ke"].tolist(),
            start_time=temp["Mulai (detik)"].tolist(),
            end_time=temp["Selesai (detik)"].tolist(),
            duration=temp["Durasi (menit)"].tolist(),
            sks=temp["SKS"].tolist(),
        )
        result.append(schedule)
    return result


def generate_rooms() -> Room:
    result: Room
    room_id = random.choice(ruang_list)
    room_name = "Ruang " + str(room_id)
    room_capacity = random.randint(20, 30)
    result = Room(room_id, room_name, room_capacity)
    return result


Rooms = [generate_rooms() for _ in ruang_list]

FORBIDDEN_WINDOWS = {
    4: [(12 * 3600, 13 * 3600)],  # 12:00–13:00 harus kosong
}


def _within_bounds(s: int, e: int) -> bool:
    return s >= DAY_OPEN and e <= DAY_CLOSE and s < e


def _allowed_in_day(day: int, s: int, e: int) -> bool:
    """Di dalam jam kerja & tidak menabrak jendela terlarang hari tsb."""
    if not _within_bounds(s, e):
        return False
    for fs, fe in FORBIDDEN_WINDOWS.get(day, []):
        if overlap(s, e, fs, fe):
            return False
    return True


def generate_subject():
    subject = dataset_df.sample(n=1).iloc[0]
    subject_name = subject["nama_matakuliah"]
    subject_id = subject["kode_matakuliah"]
    semester = subject["semester"]
    capacity = subject["jumlah_peserta"]
    sks = subject["sks_praktek"]
    class_code = subject["kode_kelas"]

    return (subject, subject_name, subject_id, semester, capacity, sks, class_code)


def generate_gene(rooms: List[Room]) -> List[Gene]:
    result: List[Gene] = []

    subject, subject_name, subject_id, semester, capacity, sks, class_code = (
        generate_subject()
    )
    duration = 120 if sks == 1 else 180
    dur_sec = duration * 60

    assistants = generate_assistant(random.randint(2, 5))
    preferred_lab: List[Room] = random.sample(rooms, random.randint(1, 4))
    chosen_room = random.choice(preferred_lab)
    room_id: int = chosen_room.id

    def split_by_rooms(cap: int, max_cap: int) -> List[int]:
        part = 1
        while (cap / part) > max_cap:
            part += 1
        res = [cap // part] * part
        res[-1] += cap % part
        return res

    capacities = split_by_rooms(capacity, chosen_room.room_capacity)
    dur_sec = duration * 60
    days = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"]

    def _sample_start_for_day(day_idx: int, dur_sec: int) -> tuple[int, int]:
        """Pilih (start, end) yang sah. Jumat menghindari 12–13."""
        # default: satu jendela penuh
        windows = [(DAY_OPEN, DAY_CLOSE)]
        # jika punya forbidden, pecah jadi beberapa jendela aman
        if day_idx in FORBIDDEN_WINDOWS:
            for fs, fe in FORBIDDEN_WINDOWS[day_idx]:
                windows = [
                    (DAY_OPEN, fs),  # sebelum lunch
                    (fe, DAY_CLOSE),  # sesudah lunch
                ]

        # pilih window yang cukup panjang
        candidates = []
        for ws, we in windows:
            if we - ws >= dur_sec:
                candidates.append((ws, we))
        if not candidates:
            return None, None  # biarkan caller fallback/repair

        # coba beberapa kali sampling grid
        for _ in range(80):
            ws, we = random.choice(candidates)
            latest = we - dur_sec
            start = _snap(random.randint(ws, latest))
            end = start + dur_sec
            if _allowed_in_day(day_idx, start, end):
                return start, end

        # gagal sampling -> fallback: paksa di awal window pertama
        ws, we = candidates[0]
        start = _snap(ws)
        end = start + dur_sec
        if _allowed_in_day(day_idx, start, end):
            return start, end
        return None, None

    for index, cap in enumerate(capacities):
        # pilih hari
        day_idx = random.randint(0, 5)
        day_name = days[day_idx]

        # sampling waktu yang aman (Jumat hindari 12–13)
        start, end = _sample_start_for_day(day_idx, dur_sec)
        if start is None:
            # fallback super-aman: paksa di 07:00; repair nanti yang geser
            start = _snap(DAY_OPEN)
            end = start + dur_sec

        result.append(
            Gene(
                subject_name,
                subject_id,
                semester,
                sks,
                cap,
                assistants,
                preferred_lab,
                day_name,
                day_idx,
                start,
                end,
                room_id,
                f"{class_code}-{index+1},",
            )
        )
    return result


def display_gene(gene: Gene):
    for attr, value in asdict(gene).items():
        # kalau bukan list
        if not isinstance(value, list):
            print(f"{attr}: {value}")
            # setelah ketemu room_id, cari Room-nya
            if attr == "room_id":
                room = next((r for r in Rooms if r.id == value), None)
                if room:
                    room_idx = Rooms.index(room)
                    print(f"room index: {room_idx}")
                    print(f"room capacity: {room.room_capacity}")
                else:
                    print(f"room not found for id={value}")
        else:
            print(f"{attr}: {[i["id"] for i in value]}")
    print()


def generate_individu(rooms, n_ind) -> Individuals:
    result = Individuals([])
    for _ in range(n_ind):
        result.chromosome.extend(generate_gene(rooms))
    return result


# def generate_population(n_ind, n_pop):
#     global Rooms

#     population: List[Individuals] = []
#     for _ in range(n_pop):
#         generated = generate_individu(Rooms, n_ind)
#         if len(generated.chromosome) < n_ind:
#             # ini buat generated_2 baru, lalu gabungkan keduannya dengan memerhatikan: ambil yang unik saja, dikatakan unik jika generated.chromosome[x].subject_id + generated.chromosome[x].group sama (dua key)
#             pass
#         if len(generated.chromosome) > n_ind:
#             # pertama ambil yang unik saja, dikatakan unik jika generated.chromosome[x].subject_id + generated.chromosome[x].group sama (dua key)
#             # baru if len(generated.chromosome) > n_ind lagi ke bawah
#             index_to_remove = random.sample(
#                 [i for i in range(len(generated.chromosome))],
#                 len(generated.chromosome) - n_ind,
#             )

#         generated.chromosome = [
#             x for i, x in enumerate(generated.chromosome) if i not in index_to_remove
#         ]
#         # print(len(generated.chromosome))
#         population.append(generated)
#     return population


def _uniq_key(g: Gene) -> Tuple[str, str]:
    """Kunci unik untuk deteksi duplikat: (subject_id, group)."""
    return (g.subject_id, g.group)


def _dedup_chromosome(chrom: List[Gene]) -> List[Gene]:
    """Hapus duplikat berdasar (subject_id, group), pertahankan urutan pertama."""
    seen: Set[Tuple[str, str]] = set()
    hasil: List[Gene] = []
    for g in chrom:
        k = _uniq_key(g)
        if k not in seen:
            seen.add(k)
            hasil.append(g)
    return hasil


def _merge_unique(base: List[Gene], extra: List[Gene]) -> List[Gene]:
    """Gabungkan 'extra' ke 'base' hanya yang unik (subject_id, group) belum ada di base."""
    seen = {_uniq_key(g) for g in base}
    for g in extra:
        k = _uniq_key(g)
        if k not in seen:
            base.append(g)
            seen.add(k)
    return base


# ================== CORE ==================


def generate_population(n_ind: int, n_pop: int) -> List[Individuals]:
    """
    Bangkitkan populasi berukuran n_pop.
    - Tiap Individu diusahakan tepat n_ind gen.
    - Duplikat dihapus berdasar (subject_id, group).
    - Jika kurang, generate batch tambahan dan merge unik sampai terpenuhi (batas percobaan).
    - Jika lebih, buang acak sampai pas.
    """
    global Rooms

    population: List[Individuals] = []

    for _ in range(n_pop):
        # generate awal
        generated: Individuals = generate_individu(Rooms, n_ind)

        # 1) buang duplikat dulu
        generated.chromosome = _dedup_chromosome(generated.chromosome)

        # 2) kalau kurang dari target, coba tambah dari batch lain (unik saja)
        MAX_ATTEMPTS = 10  # biar gak infinite loop
        attempts = 0
        while len(generated.chromosome) < n_ind and attempts < MAX_ATTEMPTS:
            remaining = n_ind - len(generated.chromosome)
            # boleh generate pas 'remaining', atau n_ind lagi (bebas—pakai remaining lebih efisien)
            generated_2: Individuals = generate_individu(Rooms, remaining)
            # pastikan generated_2 juga bebas duplikat internalnya
            generated_2.chromosome = _dedup_chromosome(generated_2.chromosome)

            # merge unik
            generated.chromosome = _merge_unique(
                generated.chromosome, generated_2.chromosome
            )
            attempts += 1

        # 3) kalau masih lebih dari target, buang acak
        if len(generated.chromosome) > n_ind:
            surplus = len(generated.chromosome) - n_ind
            # pilih index yang akan dibuang
            idx_to_remove = set(
                random.sample(range(len(generated.chromosome)), surplus)
            )
            generated.chromosome = [
                g for i, g in enumerate(generated.chromosome) if i not in idx_to_remove
            ]

        # 4) kalau masih kurang setelah semua usaha, kita biarkan apa adanya
        # (opsional: raise warning/logging)

        population.append(generated)

    return population


# population = generate_population(40, 20)
# print(len(population))
# print(random.sample(population, 1)[0].to_dataframe())
