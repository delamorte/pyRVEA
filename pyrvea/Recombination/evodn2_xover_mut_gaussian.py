import numpy as np
from copy import deepcopy
from random import sample
from math import ceil


def evodn2_xover_mut_gaussian(
    parent1,
    parent2,
    individuals,
    prob_crossover=0.8,
    prob_mut=0.3,
    mut_strength=0.7,
    cur_gen=1,
    total_gen=10,
    std_dev=1.0,
):
    """ Perform simultaneous crossover and mutation over two individuals.

    Parameters
    ----------
    parent1 : ndarray
        The first individual
    parent2 : ndarray
        The second individual
    individuals : ndarray
        All individuals to choose mutation partner from
    prob_crossover : float
        The probability for crossover
    prob_mut : float
        The probability for mutation
    mut_strength : float
        Mutation alfa parameter
    cur_gen : int
        Current generation
    total_gen : int
        Total generations
    std_dev : float
        Standard deviation
    """

    offspring1 = deepcopy(parent1)
    offspring2 = deepcopy(parent2)

    for subnet in range(len(offspring1)):

        sub1 = offspring1[subnet]
        sub2 = offspring2[subnet]

        for layer in range(min(len(sub1), len(sub2))):

            connections = min(sub1[layer][1:, :].size, sub2[layer][1:, :].size)

            # Crossover
            exchange = sample(
                range(connections), np.random.binomial(connections, prob_crossover)
            )
            tmp = deepcopy(sub1[layer])
            sub1[layer][1:, :].ravel()[exchange] = sub2[layer][1:, :].ravel()[exchange]
            sub2[layer][1:, :].ravel()[exchange] = tmp[1:, :].ravel()[exchange]

            # mut_val = np.random.normal(0, std_dev, connections)
            #
            # mut = np.random.choice(
            #     np.arange(connections),
            #     np.random.binomial(connections, prob_mut),
            #     replace=False,
            # )
            #
            # sub1[layer][1:, :].ravel()[mut] *= mut_val[mut]
            #
            # mut = np.random.choice(
            #     np.arange(connections),
            #     np.random.binomial(connections, prob_mut),
            #     replace=False,
            # )
            # sub2[layer][1:, :].ravel()[mut] *= mut_val[mut]

        # for layer in range(max(len(sub1), len(sub2))):
        #
        #     it = np.nditer(
        #         [sub1[layer][1:, :], sub2[layer][1:, :]], op_flags=["readwrite"]
        #     )
        #
        #     for mut_layer in it.itviews:
        #
        #         connections = mut_layer.size
        #
        #         mut_val = np.random.normal(0, std_dev, connections)
        #
        #         mut = np.random.choice(np.arange(mut_layer.size), ceil(mut_layer.size * prob_mut), replace=False)
        #         mut_layer[mut] *= mut_val[mut]

        # THIS WORKS THE BEST FOR NOW
        for layer in sub1:

            connections = layer[1:, :].size

            mut_val = np.random.normal(0, std_dev, connections)

            mut = np.random.choice(connections, np.random.binomial(connections, prob_mut), replace=False)
            layer[1:, :].ravel()[mut] *= mut_val[mut]

        for layer in sub2:

            connections = layer[1:, :].size

            mut_val = np.random.normal(0, std_dev, connections)

            mut = np.random.choice(connections, np.random.binomial(connections, prob_mut), replace=False)
            layer[1:, :].ravel()[mut] *= mut_val[mut]

        # try:
        #     # Mutate first individual
        #     connections = sub1[layer][1:, :].size
        #     mutate = sample(range(connections), int(connections*prob_mut))
        #
        #     sub1[layer][1:, :].ravel()[mutate] = sub1[layer][1:, :].ravel()[
        #         mutate
        #     ] + mut_strength * (1 - cur_gen / total_gen) * (
        #         sub3[layer][1:, :].ravel()[mutate]
        #         - sub4[layer][1:, :].ravel()[mutate]
        #     )
        #
        #     # Mutate second individual
        #     connections = sub2[layer][1:, :].size
        #     mutate = sample(range(connections), int(connections*prob_mut))
        #
        #     sub2[layer][1:, :].ravel()[mutate] = sub2[layer][1:, :].ravel()[
        #         mutate
        #     ] + mut_strength * (1 - cur_gen / total_gen) * (
        #         sub3[layer][1:, :].ravel()[mutate]
        #         - sub4[layer][1:, :].ravel()[mutate]
        #     )
        # except IndexError:
        #
        #     # If mutation partner had less layers than the offspring, randomly mutate the rest of the layers
        #     # for l in range(layer, r):
        #     #     mutate = sample(
        #     #         range(connections), np.random.binomial(connections, prob_mut)
        #     #     )
        #     #     sub1[layer][1:, :].ravel()[mutate] = sub1[layer][1:, :].ravel()[
        #     #         mutate
        #     #     ] * np.random.uniform(
        #     #         0.9, 1.0, sub1[layer][1:, :].ravel()[mutate].shape
        #     #    )
        #     break

    return offspring1, offspring2
