from typing import List, Set, Dict
from data_type import Room, Gene, AssistantSchedule, Individuals
from seeder import generate_population, _allowed_in_day
from fitness import fitness, overlap, norm_group, DAY_OPEN, DAY_CLOSE, GRID, _snap
import random
import itertools, random, copy


def roulette_select(pop, fitnesses):
    total = sum(fitnesses)
    if total <= 0:
        # fallback: uniform
        idxs = [random.randrange(len(pop)) for _ in range(len(pop))]
        return [copy.deepcopy(pop[i]) for i in idxs]

    probs = [f / total for f in fitnesses]
    cum = list(itertools.accumulate(probs))
    # Pastikan elemen terakhir = 1.0 (hindari celah floating)
    cum[-1] = 1.0

    picks = []
    for _ in range(len(pop)):
        r = random.random()
        j = next(i for i, c in enumerate(cum) if r <= c)
        picks.append(j)
    return [copy.deepcopy(pop[i]) for i in picks]


def repair_individual(individu: Individuals):
    by_day: Dict[int, List[Gene]] = {}
    for g in individu.chromosome:
        by_day.setdefault(g.day, []).append(g)

    def slot_free(day: int, room_id: int, s: int, e: int, skip_gene=None) -> bool:
        if not _allowed_in_day(day, s, e):
            return False
        for x in by_day.get(day, []):
            if x is skip_gene:
                continue
            if x.room_id == room_id and overlap(x.start_time, x.end_time, s, e):
                return False
        return True

    def capacity_ok(room: Room, cap: int) -> bool:
        return cap <= room.room_capacity

    for day, items in by_day.items():
        items.sort(key=lambda x: (x.room_id, x.start_time, x.end_time))

        # clamp awal (kalau di luar bound / nabrak lunch)
        for gi in items:
            dur = gi.end_time - gi.start_time
            if not _allowed_in_day(gi.day, gi.start_time, gi.end_time):
                # coba snap ke awal hari
                gi.start_time = _snap(DAY_OPEN)
                gi.end_time = gi.start_time + dur
                # kalau masih nabrak (mis. Jumat & dur besar), geser maju grid sampai valid
                for _ in range(40):
                    if _allowed_in_day(gi.day, gi.start_time, gi.end_time):
                        break
                    gi.start_time += GRID
                    gi.end_time += GRID

        # perbaiki bentrok per-ruang
        for i in range(len(items)):
            gi = items[i]
            for j in range(i + 1, len(items)):
                gj = items[j]
                if gi.room_id != gj.room_id:
                    continue
                if not overlap(gi.start_time, gi.end_time, gj.start_time, gj.end_time):
                    continue

                # coba pindah ruang (kapasitas & slot_free termasuk cek lunch)
                moved = False
                for r in getattr(gj, "preferred_lab", []) or []:
                    if r.id == gj.room_id or not capacity_ok(r, gj.capacity):
                        continue
                    if slot_free(day, r.id, gj.start_time, gj.end_time, skip_gene=gj):
                        gj.room_id = r.id
                        moved = True
                        break
                if moved:
                    continue

                # geser di grid ±n step tapi hindari jendela terlarang
                for mul in (1, -1, 2, -2, 3, -3, 4, -4):
                    s2 = gj.start_time + mul * GRID
                    e2 = gj.end_time + mul * GRID
                    if slot_free(day, gj.room_id, s2, e2, skip_gene=gj):
                        gj.start_time, gj.end_time = s2, e2
                        break

        # perbaiki bentrok per-group (pakai slot_free yang sudah aware lunch)
        groups: Dict[str, List[Gene]] = {}
        for g in items:
            ng = norm_group(getattr(g, "group", ""))
            if ng:
                groups.setdefault(ng, []).append(g)

        for glist in groups.values():
            glist.sort(key=lambda x: x.start_time)
            for a, b in zip(glist, glist[1:]):
                if overlap(a.start_time, a.end_time, b.start_time, b.end_time):
                    for mul in (1, -1, 2, -2, 3, -3):
                        s2 = b.start_time + mul * GRID
                        e2 = b.end_time + mul * GRID
                        if slot_free(b.day, b.room_id, s2, e2, skip_gene=b):
                            b.start_time, b.end_time = s2, e2
                            break


def crossover(fitnesses: List[float], pop: List[Individuals], rate=0.5):
    offsprings = roulette_select(pop, fitnesses)

    if not offsprings:
        return []

    L = min(len(ind.chromosome) for ind in offsprings)  # be safe
    cand = [i for i in range(len(offsprings)) if random.random() < rate]
    if len(cand) < 2 or L < 2:
        # still repair/dedup every offspring to reduce drift
        for k in range(len(offsprings)):
            repair_individual(offsprings[k])
        return offsprings

    for i in range(0, len(cand) - 1, 2):
        a, b = cand[i], cand[i + 1]
        point = random.randint(1, L - 1)
        ca = offsprings[a].chromosome
        cb = offsprings[b].chromosome
        offsprings[a].chromosome = ca[:point] + cb[point:]
        offsprings[b].chromosome = cb[:point] + ca[point:]
        repair_individual(offsprings[a])
        repair_individual(offsprings[b])

    # Light pass over all
    for k in range(len(offsprings)):
        repair_individual(offsprings[k])
    return offsprings
