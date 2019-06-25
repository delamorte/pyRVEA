from collections import defaultdict
from collections.abc import Sequence

from typing import TYPE_CHECKING
import numpy as np
import pandas as pd
from pyDOE import lhs
from pygmo import fast_non_dominated_sorting as nds
from pygmo import hypervolume as hv
from pygmo import non_dominated_front_2d as nd2

from tqdm import tqdm, tqdm_notebook

from pyrvea.Recombination.bounded_polynomial_mutation import mutation
from pyrvea.Recombination.simulated_binary_crossover import crossover

from pyrvea.OtherTools.plotlyanimate import animate_init_, animate_next_
from pyrvea.OtherTools.IsNotebook import IsNotebook
import random
from pyrvea.Recombination.ppga_crossover import ppga_crossover
from pyrvea.Recombination.evodn2_xover_mut import evodn2_xover_mut
from pyrvea.Recombination.ppga_mutation import ppga_mutation
from math import ceil

if TYPE_CHECKING:
    from pyrvea.Problem.baseProblem import baseProblem
    from pyrvea.EAs.baseEA import BaseEA


class Population:
    """Define the population."""

    def __init__(
        self,
        problem: "baseProblem",
        assign_type: str = "LHSDesign",
        plotting: bool = True,
        pop_size=None,
        *args
    ):
        """Initialize the population.

        Attributes
        ----------
        problem : baseProblem
            An object of the class Problem
        assign_type : str, optional
            Define the method of creation of population.
            If 'assign_type' is 'RandomDesign' the population is generated
            randomly. If 'assign_type' is 'LHSDesign', the population is
            generated via Latin Hypercube Sampling. If 'assign_type' is
            'custom', the population is imported from file. If assign_type
            is 'empty', create blank population. (the default is "RandomAssign")
        plotting : bool, optional
            (the default is True, which creates the plots)
        pop_size : int
            Population size

        """
        self.num_var = problem.num_of_variables
        self.lower_limits = np.asarray(problem.lower_limits)
        self.upper_limits = np.asarray(problem.upper_limits)
        self.hyp = 0
        self.non_dom = 0
        self.pop_size = pop_size
        self.problem = problem
        self.filename = problem.name + "_" + str(problem.num_of_objectives)
        self.plotting = plotting
        # These attributes contain the solutions.

        self.individuals = np.empty((0, self.num_var), float)
        self.objectives = np.empty((0, self.problem.num_of_objectives), float)
        self.fitness = np.empty((0, self.problem.num_of_objectives), float)
        self.constraint_violation = np.empty(
            (0, self.problem.num_of_constraints), float
        )
        self.archive = pd.DataFrame(
            columns=["generation", "decision_variables", "objective_values"]
        )
        self.ideal_fitness = np.full((1, self.problem.num_of_objectives), np.inf)
        self.worst_fitness = -1 * self.ideal_fitness
        if not assign_type == "empty":
            self.create_new_individuals(assign_type, pop_size=self.pop_size)

    def create_new_individuals(
        self, design: str = "LHSDesign", pop_size: int = None, decision_variables=None
    ):
        """Create, evaluate and add new individuals to the population. Initiate Plots.

        The individuals can be created randomly, by LHS design, or can be passed by the
        user.

        Parameters
        ----------
        design : str, optional
            Describe the method of creation of new individuals.
            "RandomDesign" creates individuals randomly.
            "LHSDesign" creates individuals using Latin hypercube sampling.
            "EvoNN" creates Artificial Neural Networks as individuals.
        pop_size : int, optional
            Number of individuals in the population. If none, some default population
            size based on number of objectives is chosen.
        decision_variables : numpy array or list, optional
            Pass decision variables to be added to the population.
        """
        if decision_variables is not None:
            pass
        if pop_size is None:
            pop_size_options = [50, 105, 120, 126, 132, 112, 156, 90, 275]
            pop_size = pop_size_options[self.problem.num_of_objectives - 2]

        num_var = self.individuals.shape[1]

        if design == "RandomDesign":
            individuals = np.random.random((pop_size, num_var))
            # Scaling
            individuals = (
                individuals * (self.upper_limits - self.lower_limits)
                + self.lower_limits
            )
        elif design == "LHSDesign":
            individuals = lhs(num_var, samples=pop_size)
            # Scaling
            individuals = (
                individuals * (self.upper_limits - self.lower_limits)
                + self.lower_limits
            )
        elif design == "EvoNN":

            individuals = self.problem.create_population()
            self.individuals = np.empty((0, individuals.shape[1], individuals.shape[2]))

        elif design == "EvoDN2":
            self.individuals = np.empty((0, self.problem.subnets[0]))

            individuals = self.problem.create_population()

        else:
            print("Design not yet supported.")

        self.add(individuals)

        if self.plotting:
            self.figure = []
            self.plot_init_()

    def eval_fitness(self):
        """
        Calculate fitness based on objective values. Fitness = obj if minimized.
        """
        fitness = self.objectives * self.problem.objs
        return fitness

    def add(self, new_pop: np.ndarray):
        """Evaluate and add individuals to the population. Update ideal and nadir point.

        Parameters
        ----------
        new_pop: np.ndarray
            Decision variable values for new population.
        """
        if new_pop.ndim == 1:
            self.append_individual(new_pop)

        elif new_pop.ndim >= 2:
            for i in range(0, new_pop.shape[0]):
                self.append_individual(new_pop[i, ...])
        else:
            print("Error while adding new individuals. Check dimensions.")
        # print(self.ideal_fitness)
        self.update_ideal_and_nadir()

    def keep(self, indices: list):
        """Remove individuals from population which are not in "indices".

        Parameters
        ----------
        indices: list
            Indices of individuals to keep
        """

        new_pop = self.individuals[indices, :]
        new_obj = self.objectives[indices, :]
        new_fitness = self.fitness[indices, :]
        new_CV = self.constraint_violation[indices, :]
        self.individuals = new_pop
        self.objectives = new_obj
        length_of_archive = len(self.archive)
        if length_of_archive == 0:
            gen_count = 0
        else:
            gen_count = self.archive["generation"].iloc[-1] + 1
        new_entries = pd.DataFrame(
            {
                "generation": [gen_count] * len(new_obj),
                "decision_variables": new_pop.tolist(),
                "objective_values": new_obj.tolist(),
            }
        )
        self.archive = self.archive.append(new_entries, ignore_index=True)
        self.fitness = new_fitness
        self.constraint_violation = new_CV

    def delete_or_keep(self, indices: list, delete_or_keep):
        """Remove individuals from population which ARE in "indices".
        With boolean masks deleted individuals can be obtained with
        inverted mask (~mask)

        Parameters
        ----------
        indices: list
            Indices of individuals to keep
        """
        indices.sort()
        mask = np.ones(len(self.individuals), dtype=bool)
        mask[indices] = False

        # new_pop = np.delete(self.individuals, indices, axis=0)
        new_pop = self.individuals[mask, ...]
        deleted_pop = self.individuals[~mask, ...]

        # new_obj = np.delete(self.objectives, indices, axis=0)
        new_obj = self.objectives[mask, ...]
        deleted_obj = self.objectives[~mask, ...]

        # new_fitness = np.delete(self.fitness, indices, axis=0)
        new_fitness = self.fitness[mask, ...]
        deleted_fitness = self.fitness[~mask, ...]

        if len(self.constraint_violation) > 0:
            # new_cv = np.delete(self.constraint_violation, indices, axis=0)
            new_cv = self.constraint_violation[mask, ...]
            deleted_cv = self.constraint_violation[~mask, ...]
        else:
            deleted_cv = self.constraint_violation
            new_cv = self.constraint_violation

        if delete_or_keep == "delete":
            self.individuals = new_pop
            self.objectives = new_obj
            self.fitness = new_fitness
            self.constraint_violation = new_cv

        elif delete_or_keep == "keep":
            self.individuals = deleted_pop
            self.objectives = deleted_obj
            self.fitness = deleted_fitness
            self.constraint_violation = deleted_cv

    def append_individual(self, ind: np.ndarray):
        """Evaluate and add individual to the population.

        Parameters
        ----------
        ind: np.ndarray
        """
        self.individuals = np.concatenate((self.individuals, [ind]))
        obj, CV, fitness = self.evaluate_individual(ind)
        self.objectives = np.vstack((self.objectives, obj))
        self.constraint_violation = np.vstack((self.constraint_violation, CV))
        self.fitness = np.vstack((self.fitness, fitness))

    def evaluate_individual(self, ind: np.ndarray):
        """Evaluate individual.

        Returns objective values, constraint violation, and fitness.

        Parameters
        ----------
        ind: np.ndarray
        """
        obj = self.problem.objectives(ind)
        CV = np.empty((0, self.problem.num_of_constraints), float)
        fitness = obj

        if self.problem.num_of_constraints:
            CV = self.problem.constraints(ind, obj)
            fitness = self.eval_fitness(ind, obj, self.problem)

        return (obj, CV, fitness)

    def evolve(self, EA: "BaseEA" = None, EA_parameters: dict = {}) -> "Population":
        """Evolve the population with interruptions.

        Evolves the population based on the EA sent by the user.

        Parameters
        ----------
        EA: "BaseEA"
            Should be a derivative of BaseEA (Default value = None)
        EA_parameters: dict
            Contains the parameters needed by EA (Default value = None)

        """
        ##################################
        # To determine whether running in console or in notebook. Used for TQDM.
        # TQDM will be removed in future generations as number of iterations can vary

        if IsNotebook():
            progressbar = tqdm_notebook
        else:
            progressbar = tqdm
        ####################################
        # A basic evolution cycle. Will be updated to optimize() in future versions.
        ea = EA(self, EA_parameters)
        iterations = ea.params["iterations"]

        if self.plotting:
            self.plot_objectives()  # Figure was created in init
        for i in progressbar(range(1, iterations), desc="Iteration"):
            ea._run_interruption(self)
            ea._next_iteration(self)
            if self.plotting:
                self.plot_objectives()

    def mate(self, ind1=None, ind2=None, params=None):
        """Conduct crossover and mutation over the population.

        Conduct simulated binary crossover and bounded polunomial mutation.
        """
        offspring = np.empty(
            (
                0,
                self.problem.num_input_nodes + 1,
                self.problem.num_nodes,
            ),
            float,
        )

        if self.individuals.ndim >= 2:
            for ind in range(self.individuals.shape[0]):

                # Get individuals at indices
                if ind1 is None or ind2 is None:
                    w1, w2 = self.individuals[random.randint(0, self.individuals.shape[0]-1)], self.individuals[random.randint(0, self.individuals.shape[0]-1)]

                else:
                    w1, w2 = self.individuals[ind1], self.individuals[ind2]

                # Perform crossover
                if params["crossover_type"] == "short":
                    offspring1, offspring2 = evodn2_xover_mut(
                        w1,
                        w2,
                        self.individuals,
                        params["prob_crossover"],
                        params["prob_mutation"],
                        params["mut_strength"],
                        params["current_iteration_gen_count"],
                        params["generations"]
                    )
                else:
                    xover_w1, xover_w2 = ppga_crossover(w1, w2)

                    # Make a list of individuals suitable for mutation, exclude the ones to be mutated
                    # so that they won't mutate with themselves
                    indices = [ind1, ind2]
                    mask = np.ones(len(self.individuals), dtype=bool)
                    mask[indices] = False
                    alternatives = self.individuals[mask, ...][:, 1:, :]

                    # Mutate
                    offspring1, offspring2 = ppga_mutation(
                        alternatives,
                        xover_w1,
                        xover_w2,
                        params["current_iteration_gen_count"]
                    )
                    offspring = np.concatenate((offspring, [offspring1], [offspring2]))

            return offspring

        else:
            offspring = crossover(self)
            p = 1 / self.num_var
            mut_offspring = mutation(self, offspring, prob_mut=p)

            return mut_offspring

    def plot_init_(self):
        """Initialize animation objects. Return figure"""
        obj = self.objectives
        self.figure = animate_init_(obj, self.filename + ".html")
        return self.figure

    def plot_objectives(self, iteration: int = None):
        """Plot the objective values of individuals in notebook. This is a hack.

        Parameters
        ----------
        iteration: int
            Iteration count.
        """
        obj = self.objectives
        self.figure = animate_next_(
            obj, self.figure, self.filename + ".html", iteration
        )

    def hypervolume(self, ref_point):
        """Calculate hypervolume. Uses package pygmo. Add checks to prevent errors.

        Parameters
        ----------
        ref_point

        Returns
        -------

        """
        non_dom = self.non_dom
        if not isinstance(ref_point, (Sequence, np.ndarray)):
            num_obj = non_dom.shape[1]
            ref_point = [ref_point] * num_obj
        non_dom = non_dom[np.all(non_dom < ref_point, axis=1), :]
        hyp = hv(non_dom)
        self.hyp = hyp.compute(ref_point)
        return self.hyp

    def non_dominated(self):
        """Fix this. check if nd2 and nds mean the same thing"""
        obj = self.objectives
        num_obj = obj.shape[1]
        if num_obj == 2:
            non_dom_front = nd2(obj)
        else:
            non_dom_front = nds(obj)
        if isinstance(non_dom_front, tuple):
            self.non_dom = self.objectives[non_dom_front[0][0]]
        elif isinstance(non_dom_front, np.ndarray):
            self.non_dom = self.objectives[non_dom_front]
        else:
            print("Non Dom error Line 285 in population.py")
        return non_dom_front

    def update_ideal_and_nadir(self, new_objective_vals: list = None):
        """Updates self.ideal and self.nadir in the fitness space.

        Uses the entire population if new_objective_vals is none.

        Parameters
        ----------
        new_objective_vals : list, optional
            Objective values for a newly added individual (the default is None, which
            calculated the ideal and nadir for the entire population.)

        """
        if new_objective_vals is None:
            check_ideal_with = self.fitness
        else:
            check_ideal_with = new_objective_vals
        self.ideal_fitness = np.amin(
            np.vstack((self.ideal_fitness, check_ideal_with)), axis=0
        )
        self.worst_fitness = np.amax(
            np.vstack((self.worst_fitness, check_ideal_with)), axis=0
        )
