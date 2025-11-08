import random
import copy
from dataclasses import replace
from typing import List, Tuple
from data_type import Room, Gene, AssistantSchedule, Individuals


# =========================
# Selection: SUS (lebih adil dari roulette)
# =========================
def sus_select(
    fitnesses: List[float], pop: List[Individuals], k: int
) -> List[Individuals]:
    total = sum(fitnesses) or 1e-9
    probs = [f / total for f in fitnesses]
    cdf = []
    acc = 0.0
    for p in probs:
        acc += p
        cdf.append(acc)

    step = 1.0 / k
    start = random.random() * step
    pointers = [start + i * step for i in range(k)]

    selected = []
    j = 0
    for ptr in pointers:
        while j < len(cdf) and cdf[j] < ptr:
            j += 1
        idx = min(j, len(pop) - 1)
        selected.append(copy.deepcopy(pop[idx]))
    return selected


# =========================
# Crossover operators
# =========================
def cx_one_point(a: Individuals, b: Individuals) -> Tuple[Individuals, Individuals]:
    L = len(a.chromosome)
    if L < 2:
        return copy.deepcopy(a), copy.deepcopy(b)
    pt = random.randint(1, L - 1)
    c1 = Individuals(chromosome=copy.deepcopy(a.chromosome[:pt] + b.chromosome[pt:]))
    c2 = Individuals(chromosome=copy.deepcopy(b.chromosome[:pt] + a.chromosome[pt:]))
    return c1, c2


def cx_two_point(a: Individuals, b: Individuals) -> Tuple[Individuals, Individuals]:
    L = len(a.chromosome)
    if L < 3:
        return cx_one_point(a, b)
    i, j = sorted(random.sample(range(1, L), 2))
    c1 = Individuals(
        chromosome=copy.deepcopy(
            a.chromosome[:i] + b.chromosome[i:j] + a.chromosome[j:]
        )
    )
    c2 = Individuals(
        chromosome=copy.deepcopy(
            b.chromosome[:i] + a.chromosome[i:j] + b.chromosome[j:]
        )
    )
    return c1, c2


def cx_uniform_gene(
    a: Individuals, b: Individuals, p: float = 0.5
) -> Tuple[Individuals, Individuals]:
    L = len(a.chromosome)
    c1_genes, c2_genes = [], []
    for k in range(L):
        if random.random() < p:
            c1_genes.append(copy.deepcopy(a.chromosome[k]))
            c2_genes.append(copy.deepcopy(b.chromosome[k]))
        else:
            c1_genes.append(copy.deepcopy(b.chromosome[k]))
            c2_genes.append(copy.deepcopy(a.chromosome[k]))
    return Individuals(c1_genes), Individuals(c2_genes)


def cx_uniform_schedule_fields(
    a: Individuals, b: Individuals, p: float = 0.5
) -> Tuple[Individuals, Individuals]:
    """
    Campur hanya field penjadwalan (day, start, end, room) per indeks.
    Identitas mata kuliah/asisten/preferensi tetap diambil utuh dari salah satu parent.
    Ini aman kalau panjang & urutan kromosom antar parent selaras (umumnya).
    """

    def mix_gene(ga: Gene, gb: Gene) -> Gene:
        # pilih sumber “identitas” (mata kuliah, asisten, preferred_lab)
        base = ga if random.random() < 0.5 else gb
        # pilih sumber scheduling
        sched_src = ga if random.random() < 0.5 else gb

        return replace(
            base,
            day=sched_src.day,
            day_name=sched_src.day_name,
            start_time=sched_src.start_time,
            end_time=sched_src.end_time,
            room_id=sched_src.room_id,
        )

    L = len(a.chromosome)
    c1_genes, c2_genes = [], []
    for k in range(L):
        if random.random() < p:
            c1_genes.append(mix_gene(a.chromosome[k], b.chromosome[k]))
            c2_genes.append(mix_gene(b.chromosome[k], a.chromosome[k]))
        else:
            c1_genes.append(mix_gene(b.chromosome[k], a.chromosome[k]))
            c2_genes.append(mix_gene(a.chromosome[k], b.chromosome[k]))
    return Individuals(c1_genes), Individuals(c2_genes)


# =========================
# Crossover main
# =========================
def crossover(
    fitnesses: List[float], pop: List[Individuals], rate: float = 0.5, elite_k: int = 2
) -> List[Individuals]:
    """
    - Seleksi: SUS + elitism (top-k langsung lolos).
    - Pasangan dikawinkan dengan peluang 'rate'.
    - Operator crossover dipilih acak berbobot.
    """
    N = len(pop)
    if N == 0:
        return []

    # --- elitism ---
    ranked_idx = sorted(range(N), key=lambda i: fitnesses[i], reverse=True)
    elites = [copy.deepcopy(pop[i]) for i in ranked_idx[:elite_k]]

    # --- selection via SUS untuk sisa ---
    parents = sus_select(fitnesses, pop, k=N - elite_k)

    # --- buat pasangan ---
    random.shuffle(parents)
    children: List[Individuals] = []

    # daftar operator & bobot
    ops = [
        (cx_one_point, 2),
        (cx_two_point, 3),
        (cx_uniform_gene, 3),
        (
            cx_uniform_schedule_fields,
            4,
        ),  # paling eksploratif tapi tetap menjaga identitas
    ]
    total_w = sum(w for _, w in ops)

    # kawinkan berpasangan
    for i in range(0, len(parents), 2):
        if i + 1 >= len(parents):
            # ganjil → bawa satu parent apa adanya
            children.append(parents[i])
            break

        p1, p2 = parents[i], parents[i + 1]

        if random.random() >= rate:
            # no crossover → cloning
            children.append(copy.deepcopy(p1))
            children.append(copy.deepcopy(p2))
            continue

        # pilih operator berbobot
        r = random.uniform(0, total_w)
        acc = 0
        chosen = ops[0][0]
        for op, w in ops:
            acc += w
            if r <= acc:
                chosen = op
                break

        c1, c2 = chosen(p1, p2)
        children.append(c1)
        children.append(c2)

    # gabungkan elit + anak; jika lebih, potong; jika kurang, tambah clone random
    next_gen = elites + children
    if len(next_gen) > N:
        next_gen = next_gen[:N]
    elif len(next_gen) < N:
        # pad with clones
        pool = elites + parents
        while len(next_gen) < N:
            next_gen.append(copy.deepcopy(random.choice(pool)))
    return next_gen
