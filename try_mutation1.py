import random
from typing import List, Tuple
from data_type import Room, Gene, AssistantSchedule, Individuals
from fitness import overlap, fitness

# from try_crossover1 import crossover

from crossover import crossover
from seeder import generate_population, generate_gene, display_gene, Rooms


# --- helper asumsi durasi dari SKS (2 SKS = 100 menit → 1 SKS = 50 menit) ---
def duration_from_sks(sks: int) -> int:
    return int(sks * 50 * 60)  # detik


DAY_START = 7 * 3600  # misal mulai jam 07:00
DAY_END = 21 * 3600  # misal akhir jam 21:00
STEP = 30 * 60  # geser 30 menit


def clamp_time(start: int, dur: int) -> Tuple[int, int]:
    s = max(DAY_START, min(start, DAY_END - dur))
    return s, s + dur


def assistant_is_free(asst: AssistantSchedule, day: int, start: int, end: int) -> bool:
    # interpretasi: entries adalah slot SIBUK; bebas jika tak ada overlap
    for i, d in enumerate(asst.day):
        if d != day:
            continue
        if overlap(asst.start_time[i], asst.end_time[i], start, end):
            return False
    return True


def available_assistants(g: Gene, day: int, start: int, end: int) -> int:
    uniq = {a.id: a for a in g.assistant}.values()
    return sum(1 for a in uniq if assistant_is_free(a, day, start, end))


# --- OPERATOR MUTASI ---


def op_time_shift(g: Gene) -> Gene:
    # geser ±k*STEP secara acak, pertahankan durasi
    dur = (
        g.end_time - g.start_time
        if g.end_time > g.start_time
        else duration_from_sks(g.sks)
    )
    k = random.randint(1, 4)  # 0.5–2 jam
    delta = random.choice([-1, 1]) * k * STEP
    start = g.start_time + delta
    start, end = clamp_time(start, dur)
    return Gene(**{**g.__dict__, "start_time": start, "end_time": end})


def op_day_swap(g: Gene) -> Gene:
    # ganti hari (1..7), start tetap, clamp kalau perlu
    dur = (
        g.end_time - g.start_time
        if g.end_time > g.start_time
        else duration_from_sks(g.sks)
    )
    new_day = random.choice([d for d in range(1, 8) if d != g.day])
    start, end = clamp_time(g.start_time, dur)
    return Gene(**{**g.__dict__, "day": new_day, "start_time": start, "end_time": end})


def op_room_preferred(g: Gene) -> Gene:
    # pilih room dari preferred_lab kalau ada; kalau kosong, biarkan
    if g.preferred_lab:
        new_room = random.choice(g.preferred_lab).id
        return Gene(**{**g.__dict__, "room_id": new_room})
    return g


def op_fit_for_two_asst(g: Gene) -> Gene:
    """
    local search kecil: cari kombinasi (day, start) yang membuat >=2 asisten bebas.
    Coba beberapa candidate di sekitar waktu sekarang dan beberapa jam favorit.
    """
    dur = (
        g.end_time - g.start_time
        if g.end_time > g.start_time
        else duration_from_sks(g.sks)
    )

    # kandidat hari: hari sekarang + beberapa lainnya
    cand_days = [g.day] + random.sample(
        [d for d in range(1, 8) if d != g.day], k=min(3, 6)
    )
    # kandidat waktu: sekitar start sekarang + grid tiap 30 menit
    around = [g.start_time + STEP * i for i in range(-3, 4)]
    grid = list(range(DAY_START, DAY_END - dur + 1, STEP))
    candidates_time = list({t for t in around if DAY_START <= t <= DAY_END - dur})
    # tambah 5 titik random dari grid supaya eksplor
    candidates_time += random.sample(grid, k=min(5, len(grid)))

    random.shuffle(cand_days)
    random.shuffle(candidates_time)

    best = (
        available_assistants(g, g.day, g.start_time, g.end_time),
        g.day,
        g.start_time,
    )
    if best[0] >= 2:
        return g  # sudah cukup

    tried = 0
    for d in cand_days:
        for s in candidates_time:
            tried += 1
            s2, e2 = clamp_time(s, dur)
            avail = available_assistants(g, d, s2, e2)
            if avail > best[0]:
                best = (avail, d, s2)
                if avail >= 2:
                    return Gene(
                        **{
                            **g.__dict__,
                            "day": d,
                            "start_time": s2,
                            "end_time": s2 + dur,
                        }
                    )

            if tried > 80:  # batasi effort
                break
        if tried > 80:
            break

    # kalau belum dapat >=2, ambil best yang didapat (mungkin 1)
    _, bd, bs = best
    if bd != g.day or bs != g.start_time:
        return Gene(**{**g.__dict__, "day": bd, "start_time": bs, "end_time": bs + dur})
    return g


def op_swap_two_genes(ind: Individuals) -> None:
    # tukar slot dua gene (day,start,end,room) — membantu lari dari local minima
    if len(ind.chromosome) < 2:
        return
    i, j = random.sample(range(len(ind.chromosome)), 2)
    g1, g2 = ind.chromosome[i], ind.chromosome[j]
    g1_new = Gene(
        **{
            **g1.__dict__,
            "day": g2.day,
            "start_time": g2.start_time,
            "end_time": g2.end_time,
            "room_id": g2.room_id,
        }
    )
    g2_new = Gene(
        **{
            **g2.__dict__,
            "day": g1.day,
            "start_time": g1.start_time,
            "end_time": g1.end_time,
            "room_id": g1.room_id,
        }
    )
    ind.chromosome[i] = g1_new
    ind.chromosome[j] = g2_new


def op_regenerate_gene() -> Gene:
    # fallback regenerasi penuh (pakai seeder kamu)
    # NOTE: generate_gene() terlihat mengembalikan list → ambil 1
    try:
        return random.sample(generate_gene(Rooms), 1)[0]
    except:
        # kalau generate_gene() langsung return Gene, jadikan plan B
        return generate_gene(Rooms)


# --- MUTATION UTAMA ---


def mutation(
    pops: List[Individuals], rate=0.3, gene_rate=0.5, elite_k=2
) -> List[Individuals]:
    """
    - rate: peluang individu diproses mutasi
    - gene_rate: peluang tiap gene diindividu tsb dimutasi
    - elite_k: individu terbaik yang DIJAGA tidak diutak-atik
    """
    print("Mutating Random Gene...")

    # --- elitism sederhana: jaga top-k agar tak rusak ---
    # kita butuh fitness untuk ranking; asumsi ada fungsi fitness(pop) → List[float]
    # untuk menghindari circular import, panggil ringan di sini (atau kirim ranking dari luar)
    from fitness import fitness as fitness_fn

    current_scores = fitness_fn(pops)
    ranked_idx = sorted(range(len(pops)), key=lambda i: current_scores[i], reverse=True)
    elites = set(ranked_idx[:elite_k])

    # Bobot operator (bisa diubah)
    op_weights = [
        ("time_shift", 3),
        ("day_swap", 2),
        ("room_preferred", 2),
        ("fit_for_two_asst", 4),  # prioritaskan dapat 2 asisten
        ("swap_two_genes", 1),
        ("regenerate", 1),
    ]
    names, weights = zip(*op_weights)

    for i, ind in enumerate(pops):
        if i in elites:
            continue  # jangan rubah elit

        if random.random() >= rate:
            continue

        # peluang gene dipilih
        for j in range(len(ind.chromosome)):
            if random.random() >= gene_rate:
                continue

            op = random.choices(names, weights=weights, k=1)[0]

            if op == "swap_two_genes":
                op_swap_two_genes(ind)
                continue

            g = ind.chromosome[j]
            if op == "time_shift":
                ng = op_time_shift(g)
            elif op == "day_swap":
                ng = op_day_swap(g)
            elif op == "room_preferred":
                ng = op_room_preferred(g)
            elif op == "fit_for_two_asst":
                ng = op_fit_for_two_asst(g)
            elif op == "regenerate":
                ng = op_regenerate_gene()
            else:
                ng = g

            ind.chromosome[j] = ng

            # opsional: tampilkan gene baru untuk debug
            # display_gene(ind.chromosome[j])

    return pops


population = generate_population(40, 20)
fitnesses = fitness(population)
iteration = 0

step = []

while max(fitnesses) < 0.6:
    iteration += 1
    cross = crossover(fitnesses, population)
    fitnesses = fitness(cross)
    print(f"[{iteration}] max fitness from crossover: {max(fitnesses)}")
    if max(fitnesses) > 0.9:
        print(f"Pada iterasi {int(iteration+1)}: {max(fitnesses)}")
        step.append(max(fitnesses))
        break
    mutate = mutation(cross)
    fitnesses = fitness(mutate)
    print(f"[{iteration}] max fitness from mutation: {max(fitnesses)}")
    if max(fitnesses) > 0.9:
        print(f"Pada iterasi {int(iteration+1)}: {max(fitnesses)}")
        step.append(max(fitnesses))
        break

print(f'({",".join([str(i) for i in step])})')
print(f'({",".join([str(i) for i in fitnesses])})')
