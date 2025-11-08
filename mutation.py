from typing import List, Set
from data_type import Room, Gene, AssistantSchedule, Individuals, ruang_list
from seeder import generate_population, generate_gene, _snap, display_gene
from fitness import fitness, GRID, DAY_CLOSE, DAY_OPEN
from crossover import crossover, repair_individual
import random


def mutation(pops: List[Individuals], rate=0.3):
    for ind in pops:
        if random.random() < rate and ind.chromosome:
            k = max(1, len(ind.chromosome) // 10)
            idxs = random.sample(range(len(ind.chromosome)), k=k)
            for j in idxs:
                g = ind.chromosome[j]
                r = random.random()
                if r < 0.4:
                    # try switch to a preferred room that fits capacity and is free
                    for rroom in g.preferred_lab or []:
                        if rroom.id == g.room_id:
                            continue
                        if g.capacity > rroom.room_capacity:
                            continue
                        g.room_id = rroom.id
                        break
                elif r < 0.8:
                    # ±30 minutes if within bounds
                    step = GRID
                    for delta in random.sample([step, -step, 2 * step, -2 * step], k=4):
                        s2, e2 = g.start_time + delta, g.end_time + delta
                        if DAY_OPEN <= s2 and e2 <= DAY_CLOSE:
                            g.start_time, g.end_time = s2, e2
                            break
                else:
                    # change day within 0..5
                    g.day = random.randint(0, 5)
            repair_individual(ind)
    return pops


population = generate_population(int(len(ruang_list) * 9 / 5), 30)
# print(len(ruang_list))
# print(population[-1].to_dataframe())


fitnesses = fitness(population)
iteration = 0
# for x in fitnesses:
#     print(round(x[0], 2), "\t", x[1])
step = []

while max(fitnesses) < 1.0:
    iteration += 1
    cross = crossover(fitnesses, population)
    fitnesses = fitness(cross)
    print(f"[{iteration}] max fitness from crossover: {max(fitnesses)}")
    if max(fitnesses) > 0.9:
        print(f"Pada iterasi {int(iteration+1)}: {max(fitnesses)}")
        step.append(max(fitnesses))
        index = fitnesses.index(max(fitnesses))
        print(f"index of fitness 1 individu: {index}")
        print(cross[index].to_dataframe())
        cross[index].save_dataframe()
        break
    mutate = mutation(cross)
    fitnesses = fitness(mutate)
    print(f"[{iteration}] max fitness from mutation: {max(fitnesses)}")
    if max(fitnesses) >= 0.99:
        print(f"Pada iterasi {int(iteration+1)}: {max(fitnesses)}")
        step.append(max(fitnesses))
        index = fitnesses.index(max(fitnesses))
        print(f"index of fitness 1 individu: {index}")
        print(mutate[index].to_dataframe())
        mutate[index].save_dataframe()
        break

# print(f'({",".join([str(i) for i in step])})')
# print(f'({",".join([str(i) for i in fitnesses])})')
