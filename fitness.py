from typing import List, Tuple, Dict
import heapq, re
from data_type import Gene


def overlap(s1: int, e1: int, s2: int, e2: int) -> bool:
    return max(s1, s2) < min(e1, e2)  # [start, end)


GRID = 30 * 60  # 30-minute grid
DAY_OPEN = 7 * 3600  # 07:00
DAY_CLOSE = 17 * 3600  # 17:00


def _snap(x: int) -> int:
    return (x // GRID) * GRID


def _room_taken_index(
    glist: List[Gene], day: int, room_id: int, s: int, e: int
) -> bool:
    for g in glist:
        if (
            g.day == day
            and g.room_id == room_id
            and overlap(g.start_time, g.end_time, s, e)
        ):
            return True
    return False


def norm_group(g: str | None) -> str:
    if not g:
        return ""
    g = g.strip().lower()
    return re.sub(r"[^a-z0-9_\-]+", "", g)


def _count_pairs(ints: List[Tuple[int, int]]) -> int:
    if not ints:
        return 0
    ints_sorted = sorted(ints, key=lambda x: x[0])
    heap = []
    overlaps = 0
    for s, e in ints_sorted:
        while heap and heap[0] <= s:  # karena [start,end) => e<=s tidak bentrok
            heapq.heappop(heap)
        overlaps += len(heap)  # semua yang masih aktif bentrok dengan (s,e)
        heapq.heappush(heap, e)
    return overlaps


def fitness(pop: List["Individuals"]) -> List[float]:
    fitnesses: List[float] = []
    for individu in pop:
        gene = individu.chromosome

        by_day_room: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        by_day_group: Dict[Tuple[int, str], List[Tuple[int, int]]] = {}
        by_day_asst: Dict[Tuple[int, str], List[Tuple[int, int]]] = {}

        for g in gene:
            by_day_room.setdefault((g.day, g.room_id), []).append(
                (g.start_time, g.end_time)
            )
            gnorm = norm_group(getattr(g, "group", ""))
            if gnorm:
                by_day_group.setdefault((g.day, gnorm), []).append(
                    (g.start_time, g.end_time)
                )
            # optional: asisten
            for a in getattr(g, "assistant", []) or []:
                asst_id = getattr(a, "id", None)
                if asst_id:
                    by_day_asst.setdefault((g.day, asst_id), []).append(
                        (g.start_time, g.end_time)
                    )

        room_pair_conflicts = sum(_count_pairs(v) for v in by_day_room.values())
        group_pair_conflicts = sum(_count_pairs(v) for v in by_day_group.values())
        asst_pair_conflicts = sum(_count_pairs(v) for v in by_day_asst.values())

        alpha, beta, gamma = 3.0, 1.0, 2.0
        penalty = (
            alpha * room_pair_conflicts
            + beta * group_pair_conflicts
            + gamma * asst_pair_conflicts
        )
        fit = 1.0 / (1.0 + penalty)
        fitnesses.append(fit)
    return fitnesses
