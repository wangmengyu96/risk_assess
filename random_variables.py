from itertools import accumulate
import numpy as np
import math
import cmath
from scipy.special import hyp1f1, comb


class RandomVariable(object):
    def __init__(self):
        pass

    def compute_moments(self):
        raise NotImplementedError("Method compute_moments() is not implemented.")

    def sample(self):
        raise NotImplementedError("Method sample() is not implemented")

class Constant(RandomVariable):
    def __init__(self, value):
        self.value = value        

    def compute_moment(self, order):
        if order >= 0:
            return self.value**order
        else:
            raise Exception("Invalid order input")

    def compute_moments(self, order):
            return [self.compute_moment(i) for i in range(order + 1)]
    
    def sample(self):
        return self.value

    def compute_characteristic_function(self, t):
        return 1

"""cbeta is the beta distribution multiplied by a constant. When c = 1, this
is just a normal beta random variable."""
class cBetaRandomVariable(RandomVariable):
    def __init__(self, alpha, beta, c):
        self.alpha = alpha
        self.beta = beta
        self.c = c

    def compute_moments(self, order):
        #Compute all beta moments up to the given order
        #the returned list indices should match the moment orders
        #e.g. the return[i] should be the ith beta moment
        fs = map(lambda r: (self.alpha + r)/(self.alpha + self.beta + r), range(order))
        beta = [1] + list(accumulate(fs, lambda prev,n: prev*n))
        cbeta = [beta[i]*self.c**i for i in range(len(beta))]
        return cbeta

    def sample(self):
        return self.c * np.random.beta(self.alpha, self.beta)

    def compute_characteristic_function(self, t):
        """
        The characteristic function of the beta distribution is Kummer's confluent hypergeometric function which 
        is implemented by scipy.special.hyp1f1. See: https://docs.scipy.org/doc/scipy/reference/generated/scipy.special.hyp2f1.html
        If Phi_X(t) is the characteristic function of X, then for any constant c, the characteristic function of cX is
        Phi_cX(t) = Phi_X(ct)
        """
        return hyp1f1(self.alpha, self.beta, self.c * t)

"""
Let x1, x2, ..., xn be n independent random variables and c be some constant.
This object is the random variable cos(c + x1 + x2 + ... + xn)
"""
class CosSumOfRVs(RandomVariable):
    def __init__(self, c, random_variables):
        self.c = c
        self.random_variables = random_variables

    def compute_moment(self, order):
        n = int(math.floor(order/2))
        # The ith element of real_component is the real component of CharacteristicFunction(i)
        char_fun_values = [self.compute_characteristic_function(i) for i in range(order + 1)]
        real_component = [np.real(val) for val in char_fun_values]
        # Different expressions depending on if the order is odd or even
        if order % 2 == 0:
            summation = sum([comb(order, k) * real_component[2 * (n - k)] for k in range(n)])
            return (1.0/(2.0**(2.0 * n))) * comb(order, n) + (1.0/(2.0**(2.0 * n - 1))) * summation
        elif order % 2 == 1:
            summation = sum([comb(2 * n + 1, k) * real_component[2 * n + 1 - 2 * k] for k in range(n + 1)])
            return (1.0/(4.0**n)) * summation
        else:
            raise Exception("Input order mod 2 is neither 0 nor 1")

    def compute_moments(self, order):
            return [self.compute_moment(i) for i in range(order + 1)]

    def compute_characteristic_function(self, t):
        """
        If there are n random variables in self.random_variables w_i for i = 1,...,n
        And we have some constant c, then this function computes the characteristic function of
        c + w_1 + ... + w_n
        """
        return cmath.exp(complex(0, t * self.c)) * np.prod([rv.compute_characteristic_function(t) for rv in self.random_variables])

"""
Let x1, x2, ..., xn be n independent random variables and c be some constant.
This object is the random variable sin(c + x1 + x2 + ... + xn)
"""
class SinSumOfRVs(RandomVariable):
    def __init__(self, c, random_variables):
        self.c = c
        self.random_variables = random_variables

    def compute_moment(self, order):
        n = int(math.floor(order/2))
        # The ith element of real_component is the real component of CharacteristicFunction(i)
        char_fun_values = [self.compute_characteristic_function(i) for i in range(order + 1)]
        real_component = [np.real(val) for val in char_fun_values]
        imaginary_component = [np.imag(val) for val in char_fun_values]
        # Different expressions depending on if the order is odd or even
        if order % 2 == 0:
            summation = sum([(-1**k) * comb(order, k) * real_component[2 * (n - k)] for k in range(n)])
            return (1.0/(2.0**(2.0 * n))) * comb(order, n) + ((-1**n)/ (2**(2 * n - 1))) * summation
        elif order % 2 == 1:
            summation = sum([(-1**k) * comb(order, k) * imaginary_component[2 * n + 1 - 2 * k] for k in range(n+1)])
            return ((-1**n)/(4**n)) * summation
        else:
            raise Exception("Input order mod 2 is neither 0 nor 1")

    def compute_moments(self, order):
        return [self.compute_moment(i) for i in range(order + 1)]

    def compute_characteristic_function(self, t):
        """
        If there are n random variables in self.random_variables w_i for i = 1,...,n
        And we have some constant c, then this function computes the characteristic function of
        c + w_1 + ... + w_n
        """
        return cmath.exp(complex(0, 1) * t * self.c) * np.prod([rv.compute_characteristic_function(t) for rv in self.random_variables])

class RandomVector(object):
    def __init__(self, random_variables):
        # random_variables: list of random variables
        self.random_variables = random_variables

    def compute_vector_moments(self, n_moments):
        # n_moments is a list of numbers of the maximum moment order to be computed for each random variable
        all_moments = [] #list of list
        for i in range(len(n_moments)):
            all_moments.append(self.random_variables[i].compute_moments(n_moments[i]))
        return all_moments

    def sample(self):
        return [var.sample() for var in self.random_variables]