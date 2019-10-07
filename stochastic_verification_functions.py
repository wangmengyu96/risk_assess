import sympy as sp
import numpy as np
from functools import reduce
from itertools import accumulate
import time
from sympy.utilities.autowrap import ufuncify
from inspect import signature
import itertools
from itertools import permutations
import operator
import math

def add_tuples(tuple1, tuple2):
    return tuple(map(operator.add,tuple1,tuple2))

class StochasticVerificationFunction(object):
    def __init__(self, p, stochastic_model):
        #p: an anonymous function in state
        #stochastic_model:
        self.p = p
        self.stochastic_model = stochastic_model
        self.coef_funcs = {}
        self.monoms = {}

    def compile_moment_functions_multinomial(self):
        """
        Compile functions to evaluate E[p(x,y)] and E[p(x,y)^2] by leveraging
        the multinomial expansion.
        """
        final_state = self.stochastic_model.get_final_state()
        # Symbolic first moment.
        p_first_moment = self.p(final_state[0], final_state[1])
        # Variables that are input at runtime.
        input_vars = self.stochastic_model.get_input_vars()

        # Compile the coefficient functions and monomials.
        self.coef_funcs[1] = [ufuncify(input_vars, coef) for coef in p_first_moment.coeffs()]
        self.monoms[1] = p_first_moment.monoms()
        n_monoms = len(self.monoms[1])

        """
        Now we will compile the expression for the second moment of p(x).
        DEFINITION: Terms in p(x) (that is, the first moment expression) will be referred to as "first moment terms"
        """

        # degree_two_variables is a list of tuples e.g. [(0,), (1,), (2,),....]
        # where each tuple corresponds to a monomial and each number in each tuple
        # indicates which first moment terms should have degree two. All other first moment terms have degree zero.
        degree_two_variables = list(itertools.combinations(range(n_monoms), 1))

        # degree_one_variables is a list of tuples e.g. [(0,1), (1,2), (2,3),....]
        # where each tuple corresponds to a monomial and the numbers in each tuple
        # correspond to which first moment terms should have degree one. All other first moment terms have degree zero.
        degree_one_variables = list(itertools.combinations(range(n_monoms), 2))
        monom_twos = len(degree_two_variables)*[None]
        monom_ones = len(degree_one_variables)*[None]
        for i in range(len(degree_two_variables)):
            new_array = n_monoms*[0]
            new_array[degree_two_variables[i][0]] = 2
            monom_twos[i] = tuple(new_array)

        for i in range(len(degree_one_variables)):
            new_array = n_monoms*[0]
            for n in degree_one_variables[i]:
                new_array[n] = 1
            monom_ones[i] = tuple(new_array)

        #variables are the terms of p!
        p2_var_monoms = monom_twos + monom_ones

        # Determine the multi indices for the monomials in the expression for the second moment of p(x)
        p2_moment_monoms = []
        for mono in p2_var_monoms:
            assert(sum(mono) == 2)
            if 1 in mono:
                # Find the indicies of the first moment terms that have degree one.
                idx = [i for i,x in enumerate(mono) if x == 1]
                assert(len(idx) == 2)
                new_mono = add_tuples(self.monoms[1][idx[0]], self.monoms[1][idx[1]])
            elif 2 in mono:
                # In this case, mono should consist of one two with the rest of the entries being zero.
                # So something like: (0, 0, 0, 2, 0, 0,...)
                new_mono = add_tuples(self.monoms[1][mono.index(2)], self.monoms[1][mono.index(2)])
            else:
                raise Exception("There should be a 1 or 2 in here...")
            p2_moment_monoms.append(new_mono)
        self.monoms[2] = p2_moment_monoms
        self.p2_var_monoms = p2_var_monoms

    def compute_prob_bound_multimonial(self, input_variables):
        """
        Compute an upper bound on the probability of constraint violation, leveraging the multinomial
        expansion to determine the second moment of p(x) using the terms of the first moment of p(x)
        """
        coef_data = self.stochastic_model.listify_input_vars(input_variables) # TODO: how to best do this?
        p_first_coefs = [coef_func(*coef_data) for coef_func in self.coef_funcs[1]]
        p_first_monomoments, p_second_monomoments = self.compute_rv_moments()
        p_second_coefs = len(self.p2_var_monoms)*[0]
        for count, mono in enumerate(self.p2_var_monoms):
            assert(sum(mono) == 2)
            if 1 in mono:
                idx = [i for i,x in enumerate(mono) if x==1]
                assert(len(idx) == 2)
                # In this case, the multinomial coefficient is 2!/(1!1!)
                coefs = 2*p_first_coefs[idx[0]]*p_first_coefs[idx[1]]
            elif 2 in mono:
                i = mono.index(2)
                # In this case, the multinomial coefficient is 2!/(2!) = 1
                # And we just square the coefficient.
                coefs = p_first_coefs[i]**2
            else:
                raise Exception("There should be a 1 or 2 in here...")
            p_second_coefs[count] = coefs
        p_first_moment = np.dot(p_first_coefs, p_first_monomoments)
        p_second_moment = np.dot(p_second_coefs, p_second_monomoments)
        print("p_first_moment: " + str(p_first_moment))
        print("p_second_moment: " + str(p_second_moment))
        prob_bound = self.chebyshev_bound(p_first_moment, p_second_moment)
        print("prob bound is: " + str(prob_bound))
        
    def chebyshev_bound(self, first_moment, second_moment):
        #bound the probability that p<=0
        if first_moment<=0:
            return None
        else:
            variance = second_moment - first_moment**2
            return variance/(variance + first_moment**2)
    
    def set_random_vector(self, random_vector):
        self.random_vector = random_vector

    def monte_carlo_result(self, input_vars, n_samples, dt):
        fails = 0
        for i in range(n_samples):
            sampled_accels = self.random_vector.sample()
            x = input_vars.x0
            y = input_vars.y0
            v = input_vars.v0
            for j in range(len(sampled_accels)):
                x += dt * v * math.cos(input_vars.thetas[j])
                y += dt * v * math.sin(input_vars.thetas[j])
                v += dt * sampled_accels[j]
            final_p = self.p(x, y)
            if final_p <= 0:
                fails+=1
        return fails/n_samples

    def compute_rv_moments(self):
        assert(len(self.monoms[1][0]) == len(self.monoms[2][0]))
        n_vars = len(self.monoms[1][0])
        max_moments = n_vars * [0]
        # The maximum moment needed for a random variable will always be determined by that needed to compute
        # the second moment of p
        for i in range(n_vars):
            moments_needed_for_second_order_monomials = [y[i] for y in self.monoms[2]]
            max_moments[i] = max(moments_needed_for_second_order_monomials)
        moments = self.random_vector.compute_vector_moments(max_moments)
        # For each tuple in self.monoms[1] or self.monoms[2], the ith entry corresponds to the degree of that particular variable
        # in the monomial.
        mono1_moments = [np.prod([moments[i][mono[i]] for i in range(len(mono))]) for mono in self.monoms[1]]
        mono2_moments = [np.prod([moments[i][mono[i]] for i in range(len(mono))]) for mono in self.monoms[2]]
        return mono1_moments, mono2_moments