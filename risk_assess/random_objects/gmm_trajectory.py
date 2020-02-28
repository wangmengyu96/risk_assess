import numpy as np
from risk_assess.random_objects.random_variables import MultivariateNormal
from risk_assess.random_objects.mixture_models import GMM
import scipy.io

"""
A sequence of Gaussian Mixture Models (GMMs) that represent a predicted agent trajectory.
"""
class GmmTrajectory(object):
    def __init__(self, gmms):
        """
        Args:
            gmms (list of instance of MixtureModel): ordered list of Gaussian Mixture Models representing a predicted agent trajectory.
        """
        self._gmms = gmms
        self._n_components = len(self._gmms[0].component_random_variables)
        self._n_steps = len(self._gmms)
        self._dimension = self._gmms[0].component_random_variables[0].dimension
        self.check_consistency()
        self.generate_array_rep()
    
    def __len__(self):
        return len(self._gmms)

    @property
    def array_rep(self):
        self.generate_array_rep()
        return self._mean_trajectories, self._covariance_trajectories, self._weights
    
    @property
    def gmms(self):
        return self._gmms

    @classmethod
    def from_prediction(cls, prediction, scale_k):
        """
        Convert a predicted GMM trajectory into an instance of GmmTrajectory.
        Args:
            prediction: output from Pytorch deep net
            scale_k: position down scaling factor
        """
        gmms = []
        for pre in prediction:
            weights = np.array(pre['lweights'][0].exp().tolist())
            # transform mus and sigs to global frame
            mus = np.array(pre['mus'][0].tolist())
            sigs = np.array(pre['lsigs'][0].exp().tolist())

            # TODO: The matrix cov rows correspond to components and ultimately x and y are uncorrelated
            num_mixture = mus.shape[0]
            mixture_components = num_mixture * [None] # List of tuples of the form (weight, MultivariateNormal)
            for k in range(num_mixture):
                # get covariance matrix in local frame
                cov_k = np.array([[sigs[k,0]**2,0],[0,sigs[k,1]**2]])
                mu = np.c_[mus[k]] # convert mus[k] which is a list into a column numpy array
                mn = MultivariateNormal(mu*scale_k, cov_k*scale_k)

                # Add to mixture_components
                mixture_components[k] = (weights[k], mn)
            gmms.append(GMM(mixture_components))
        gmm_traj = cls(gmms)
        return gmm_traj

    def check_consistency(self):
        # First check that the number of components for each GMM is the same.
        components_per_gmm = [len(gmm.component_random_variables) for gmm in self._gmms]
        assert len(set(components_per_gmm)) == 1

        # Check that the weights of the components are consistent across time.
        for i in range(self._n_components):
            comp_weights = [gmm.component_probabilities[i] for gmm in self._gmms]
            assert(len(set(comp_weights))) == 1

    def generate_array_rep(self):
        """
        Generate lists of trajectories for mean and covariances
        """
        self._mean_trajectories = self._n_components * [None]
        self._covariance_trajectories = self._n_components * [None]
        self._weights = self._gmms[0].component_probabilities # We can use the weights of the first gmm as check_consistency() ensures they are all the same
        for i in range(self._n_components):
            # Generate the sequence of mean and covariances for the ith mode
            means = np.zeros((self._n_steps, self._dimension))
            covs = np.zeros((self._n_steps, self._dimension, self._dimension))
            for j, gmm in enumerate(self._gmms):
                # We are currently looking at the ith mode
                rv = gmm.component_random_variables[i]
                means[j, :] = rv.mean.T
                covs[j] = rv.covariance
            self._mean_trajectories[i] = means
            self._covariance_trajectories[i] = covs
    
    def change_frame(self, offset_vec, rotation_matrix):
        """
        Change from frame A to frame B.
        Args:
            offset_vec (nx1 numpy array): vector from origin of frame A to frame B
            rotation_matrix (n x n numpy array): rotation matrix corresponding to the angle of the x axis of frame A to frame B
        """
        # Apply to each component of each GMM in the trajectory.
        for gmm in self._gmms:
            gmm.change_frame(offset_vec, rotation_matrix)

    def save_as_matfile(self, directory, filename):
        """
        Save parameters of this GMM trajectory as a mat file
        """
        if ".mat" not in filename:
            filename = filename + ".mat"
        if directory[-1] != "/":
            directory = directory + "/"
        fullpath = directory + filename
        matfile_dic = {}
        for i in range(self._n_components):
            comp_key = "component_" + str(i)
            mean_traj = self._mean_trajectories[i]
            cov_traj = self._covariance_trajectories[i]
            n_steps = len(mean_traj)
            mean_array = np.zeros((2, n_steps))
            cov_array = np.zeros((2, 2, n_steps))
            for j in range(n_steps):
                mean_array[:, j] = mean_traj[j]
                cov_array[:, :, j] = cov_traj[j]
            matfile_dic[comp_key] = {"means" : mean_array, "covariances" : cov_array, "weight" : self._weights[i]}
        scipy.io.savemat(fullpath, matfile_dic)