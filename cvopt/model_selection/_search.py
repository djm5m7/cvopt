import numpy as np

from hyperopt import fmin, tpe, hp
from GPyOpt.methods import BayesianOptimization

from ._base import BaseSearcher, fit_and_score, mk_feature_select_index, mk_objfunc
from ._ga import gamin
from ..utils._base import clone_estimator, compress
from ..utils._logger import CVSummarizer, NoteBookVisualizer

class SimpleoptCV():
    """
    Each cross validation optimizer class's wrapper.

    This class allow unified handling in different type backend.

    For each backend optimizer class, refer to each class`s page.

    Parameters
    ----------
    estimator
        scikit-learn estimator like.

    param_distributions: dict.
        Search space.

    scoring: string or sklearn.metrics.make_scorer.
        Evaluation index of search.
        When scoring is None, use stimator default scorer and this score greater is better.
        
    cv: scikit-learn cross-validator or int(number of folds), default=5.
        Cross validation setting.

    max_iter: int, default=32.
        Number of search.

    random_state: int or None, default=None.
        The seed used by the random number generator.

    n_jobs: int, default=1.
        Number of jobs to run in parallel.

    pre_dispatch: int or string, default="2*n_jobs".
        Controls the number of jobs that get dispatched during parallel.

    verbose: int(0, 1 or 2), default=0.
        Controls the verbosity
        
        0: don't display status.

        1: display status by stdout.
        
        2: display status by graph.

    logdir: str or None, default=None.
        Path of directory to save log file.
        When logdir is None,  log is not saved.
        
        [directory structure]
        
        logdir
        
        |-cv_results
        
        | |-{model_id}.csv                                      : search log
        
        | ...
        
        |-estimators_{model_id}
        
            |-{model_id}_index{search count}_split{fold count}.pkl: an estimator which is fitted fold train data
            
            ...
            
            |-{model_id}_index{search count}_test.pkl             : an estimator which is fitted whole train data.

    save_estimator: int, default=0.
        estimator save setting.
        
        0: An estimator is not saved.
        
        1: An estimator which is fitted fold train data is saved per cv-fold.
        
        2: In addition to 1, an estimator which is fitted whole train data is saved per cv.

    model_id: str or None, default=None.
        This is used to log filename.
        When model_id is None, this is generated by date time.

    refit: bool, default=True.
        Refit an estimator using the best found parameters on all train data(=X).

    backend: str, default="hyperopt".
        backend optimeizer. Supports the following back ends.

        * `hyperopt`: Sequential Model Based Global Optimization

        * `bayesopt`: Bayesian Optimization

        * `gaopt`: Genetic Algorithm

        * `randomopt`: Random Search

    Attributes
    ----------
    cv_results_ : dict of numpy (masked) ndarrays
        A dict with keys as column headers and values as columns, that can be
        imported into a pandas ``DataFrame``.

    best_estimator_ : estimator or dict
        Estimator that was chosen by the search.

    best_score_ : float
        Cross-validated score of the best_estimator.

    best_params_ : dict
        Parameter setting that gave the best results on the hold out data.
    """      
    def __init__(self, estimator, param_distributions, 
                 scoring=None, cv=5, max_iter=32, 
                 random_state=None, n_jobs=1, pre_dispatch="2*n_jobs", 
                 verbose=0, logdir=None, save_estimator=0, model_id=None, refit=True, 
                 backend="hyperopt", **kwargs): 
        if backend == "hyperopt":
            self.optcv = HyperoptCV(estimator, param_distributions, 
                                    scoring=scoring, cv=cv, max_iter=max_iter, random_state=random_state, 
                                    n_jobs=n_jobs, pre_dispatch=pre_dispatch, verbose=verbose, logdir=logdir, 
                                    save_estimator=save_estimator, model_id=model_id, refit=refit, 
                                    **kwargs)
        elif backend == "bayesopt":
            self.optcv = BayesoptCV(estimator, param_distributions, 
                                    scoring=scoring, cv=cv, max_iter=max_iter, random_state=random_state, 
                                    n_jobs=n_jobs, pre_dispatch=pre_dispatch, verbose=verbose, logdir=logdir, 
                                    save_estimator=save_estimator, model_id=model_id, refit=refit, 
                                    **kwargs)
        elif backend == "gaopt":
            self.optcv = GAoptCV(estimator, param_distributions, 
                                 scoring=scoring, cv=cv, max_iter=max_iter, random_state=random_state, 
                                 n_jobs=n_jobs, pre_dispatch=pre_dispatch, verbose=verbose, logdir=logdir, 
                                 save_estimator=save_estimator, model_id=model_id, refit=refit, 
                                 **kwargs)
        elif backend == "randomopt":
            self.optcv = RandomoptCV(estimator, param_distributions, 
                                     scoring=scoring, cv=cv, max_iter=max_iter, random_state=random_state, 
                                     n_jobs=n_jobs, pre_dispatch=pre_dispatch, verbose=verbose, logdir=logdir, 
                                     save_estimator=save_estimator, model_id=model_id, refit=refit, 
                                     **kwargs)
        else:
            raise Exception("`backend` "+str(backend)+" is not supported.")

        self.backend = backend
            
    def __getattr__(self, name):
        return getattr(self.optcv, name)

        

class HyperoptCV(BaseSearcher):
    """
    Cross validation optimize by Hyperopt(Sequential Model Based Global Optimization).

    Parameters
    ----------
    estimator
        scikit-learn estimator like.

    param_distributions: dict.
        Search space.

    scoring: string or sklearn.metrics.make_scorer.
        Evaluation index of search.
        When scoring is None, use stimator default scorer and this score greater is better.
        
    cv: scikit-learn cross-validator or int(number of folds), default=5.
        Cross validation setting.

    max_iter: int, default=32.
        Number of search.

    random_state: int or None, default=None.
        The seed used by the random number generator.

    n_jobs: int, default=1.
        Number of jobs to run in parallel.

    pre_dispatch: int or string, default="2*n_jobs".
        Controls the number of jobs that get dispatched during parallel.

    verbose: int(0, 1 or 2), default=0.
        Controls the verbosity
        
        0: don't display status.

        1: display status by stdout.
        
        2: display status by graph.

    logdir: str or None, default=None.
        Path of directory to save log file.
        When logdir is None,  log is not saved.
        
        [directory structure]
        
        logdir
        
        |-cv_results
        
        | |-{model_id}.csv                                      : search log
        
        | ...
        
        |-estimators_{model_id}
        
            |-{model_id}_index{search count}_split{fold count}.pkl: an estimator which is fitted fold train data
            
            ...
            
            |-{model_id}_index{search count}_test.pkl             : an estimator which is fitted whole train data.

    save_estimator: int, default=0.
        estimator save setting.
        
        0: An estimator is not saved.
        
        1: An estimator which is fitted fold train data is saved per cv-fold.
        
        2: In addition to 1, an estimator which is fitted whole train data is saved per cv.

    model_id: str or None, default=None.
        This is used to log filename.
        When model_id is None, this is generated by date time.

    refit: bool, default=True.
        Refit an estimator using the best found parameters on all train data(=X).

    algo: hyperopt search algorithm class, default=tpe.suggest.
        Hyperopt's parameter. Search algorithm.

    Attributes
    ----------
    cv_results_ : dict of numpy (masked) ndarrays
        A dict with keys as column headers and values as columns, that can be
        imported into a pandas ``DataFrame``.

    best_estimator_ : estimator or dict
        Estimator that was chosen by the search.

    best_score_ : float
        Cross-validated score of the best_estimator.

    best_params_ : dict
        Parameter setting that gave the best results on the hold out data.
    """
    def __init__(self, estimator, param_distributions, 
                 scoring=None, cv=5, max_iter=32, 
                 random_state=None, n_jobs=1, pre_dispatch="2*n_jobs", 
                 verbose=0, logdir=None, save_estimator=0, model_id=None, refit=True, 
                 algo=tpe.suggest):
        super().__init__(estimator=estimator, param_distributions=param_distributions, 
                         scoring=scoring, cv=cv,  n_jobs=n_jobs, pre_dispatch=pre_dispatch, 
                         verbose=verbose, logdir=logdir, save_estimator=save_estimator, 
                         model_id=model_id, refit=refit, backend="hyperopt")

        self.max_iter = max_iter
        self.algo = algo
        if random_state is None:
            self.random_state = random_state
        else:
            self.random_state = np.random.RandomState(int(random_state))

    def fit(self, X, y=None, validation_data=None, groups=None, 
            feature_groups=None, min_n_features=2):
        """
        Run fit.

        Parameters
        ----------       
        X :numpy.array, pandas.DataFrame or scipy.sparse, shape(axis=0) = (n_samples)
            Features. Detail depends on estimator.

        y: np.ndarray or pd.core.frame.DataFrame, shape(axis=0) = (n_samples) or None, default=None.
            Target variable. detail depends on estimator.

        validation_data: tuple(X, y) or None, default=None.
            Data to compute validation score. detail depends on estimator.
            When validation_data is None, computing validation score is not run.

        groups: array-like, shape = (n_samples,)  or None, default=None.
            Group labels for the samples used while splitting the dataset into train/test set.
            (input of scikit-learn cross-validator)

        feature_groups: array-like, shape = (n_samples,) or None, default=None.
            Group labels for the features used while fearture select.
            When feature_groups is None, fearture selection is not run.

        min_n_features: int, default=2.
            When number of X's feature cols is less than min_n_features, return search failure.
            
            e.g. If estimator has columns sampling function, use this option to avoid X become too small and error.
        """
        X, y, Xvalid, yvalid, cv, param_distributions = self._preproc_fit(X=X, y=y, validation_data=validation_data, feature_groups=feature_groups)

        obj = mk_objfunc(X=X, y=y, groups=groups, feature_groups=feature_groups, feature_axis=BaseSearcher.feature_axis, 
                         estimator=self.estimator, scoring=self.scoring, cv=cv, 
                         param_distributions=param_distributions, backend=self.backend, failedscore=np.nan, 
                         score_summarizer=BaseSearcher.score_summarizer, 
                         Xvalid=Xvalid, yvalid=yvalid, n_jobs=self.n_jobs, pre_dispatch=self.pre_dispatch, 
                         cvsummarizer=self._cvs, save_estimator=self.save_estimator, min_n_features=min_n_features)

        try :
            fmin(obj, param_distributions, algo=self.algo, max_evals=self.max_iter, rstate=self.random_state)
        except KeyboardInterrupt:
            pass

        self._postproc_fit(X=X, y=y, feature_groups=feature_groups, 
                           best_params=self._cvs.best_params_, best_score=self._cvs.best_score_)
        return self



class BayesoptCV(BaseSearcher):
    """
    Cross validation optimizer by Gpyopt.BayesianOptimization.

    Parameters
    ----------
    estimator
        scikit-learn estimator like.

    param_distributions: dict.
        Search space.

    scoring: string or sklearn.metrics.make_scorer.
        Evaluation index of search.
        When scoring is None, use stimator default scorer and this score greater is better.
        
    cv: scikit-learn cross-validator or int(number of folds), default=5.
        Cross validation setting.

    max_iter: int, default=32.
        Number of search.

    random_state: int or None, default=None.
        The seed used by the random number generator.

    n_jobs: int, default=1.
        Number of jobs to run in parallel.

    pre_dispatch: int or string, default="2*n_jobs".
        Controls the number of jobs that get dispatched during parallel.

    verbose: int(0, 1 or 2), default=0.
        Controls the verbosity
        
        0: don't display status.

        1: display status by stdout.
        
        2: display status by graph.

    logdir: str or None, default=None.
        Path of directory to save log file.
        When logdir is None,  log is not saved.
        
        [directory structure]
        
        logdir
        
        |-cv_results
        
        | |-{model_id}.csv                                      : search log
        
        | ...
        
        |-estimators_{model_id}
        
            |-{model_id}_index{search count}_split{fold count}.pkl: an estimator which is fitted fold train data
            
            ...
            
            |-{model_id}_index{search count}_test.pkl             : an estimator which is fitted whole train data.

    save_estimator: int, default=0.
        estimator save setting.
        
        0: An estimator is not saved.
        
        1: An estimator which is fitted fold train data is saved per cv-fold.
        
        2: In addition to 1, an estimator which is fitted whole train data is saved per cv.

    model_id: str or None, default=None.
        This is used to log filename.
        When model_id is None, this is generated by date time.

    refit: bool, default=True.
        Refit an estimator using the best found parameters on all train data(=X).

    max_time: float, default=numpy.inf.
        GpyOpt`s parameter. Maximum exploration horizon in seconds.

    model_type: str, default="GP".
        GpyOpt`s parameter. Type of model to use as surrogate.

        * 'GP', standard Gaussian process.

        * 'GP_MCMC',  Gaussian process with prior in the hyper-parameters.

        * 'sparseGP', sparse Gaussian process.

        * 'warperdGP', warped Gaussian process.

        * 'InputWarpedGP', input warped Gaussian process

        * 'RF', random forest (scikit-learn).

    initial_params: numpy.array or None, default=None.
        GpyOpt`s parameter. Initial inputs of the Gpy model.

    initial_score: numpy.array or None, default=None.
        GpyOpt`s parameter. Initial outputs of the Gpy model.

    initial_design_numdata: int, default=5.
        GpyOpt`s parameter. Number of initial points that are collected jointly before start running the optimization.

    initial_design_type: str, default="random".
        GpyOpt`s parameter. Type of initial design.

        * 'random', to collect points in random locations.

        * 'latin', to collect points in a Latin hypercube (discrete variables are sampled randomly.)

    acquisition_type: str, default="EI".
        GpyOpt`s parameter. Type of acquisition function to use.

        * 'EI', expected improvement.

        * 'EI_MCMC', integrated expected improvement (requires GP_MCMC model).

        * 'MPI', maximum probability of improvement.

        * 'MPI_MCMC', maximum probability of improvement (requires GP_MCMC model).

        * 'LCB', GP-Lower confidence bound.

        * 'LCB_MCMC', integrated GP-Lower confidence bound (requires GP_MCMC model).

    normalize_Y: bool, default=True.
        GpyOpt`s parameter. Whether to normalize the outputs before performing any optimization.

    exact_feval: bool, default=False.
        GpyOpt`s parameter. Whether the outputs are exact.

    acquisition_optimizer_type: str. default="lbfgs".
        GpyOpt`s parameter. Type of acquisition function to use.

        * 'lbfgs': L-BFGS.

        * 'DIRECT': Dividing Rectangles.

        * 'CMA': covariance matrix adaptation.

    model_update_interval: int. default=1.
        GpyOpt`s parameter. Interval of collected observations after which the model is updated.

    evaluator_type: str, default="sequential".
        GpyOpt`s parameter. Determines the way the objective is evaluated (all methods are equivalent if the batch size is one).

        * 'sequential', sequential evaluations.

        * 'random': synchronous batch that selects the first element as in a sequential policy and the rest randomly.

        * 'local_penalization': batch method proposed in (Gonzalez et al. 2016).

        * 'thompson_sampling': batch method using Thompson sampling.

    batch_size: int, default=1. 
        GpyOpt`s parameter. Size of the batch in which the objective is evaluated.

    Attributes
    ----------
    cv_results_ : dict of numpy (masked) ndarrays
        A dict with keys as column headers and values as columns, that can be
        imported into a pandas ``DataFrame``.

    best_estimator_ : estimator or dict
        Estimator that was chosen by the search.

    best_score_ : float
        Cross-validated score of the best_estimator.

    best_params_ : dict
        Parameter setting that gave the best results on the hold out data.
    """

    def __init__(self, estimator, param_distributions, 
                 scoring=None, cv=5, max_iter=32, 
                 random_state=None, n_jobs=1, pre_dispatch="2*n_jobs", 
                 verbose=0, logdir=None, save_estimator=0, model_id=None, refit=True, 
                 max_time=np.inf, model_type="GP", initial_params=None, initial_score=None, 
                 initial_design_numdata=5, initial_design_type="random", 
                 acquisition_type="EI", normalize_Y=True, exact_feval=False, 
                 acquisition_optimizer_type="lbfgs", model_update_interval=1, 
                 evaluator_type="sequential", batch_size=1):

        super().__init__(estimator=estimator, param_distributions=param_distributions, 
                         scoring=scoring, cv=cv, n_jobs=n_jobs, pre_dispatch=pre_dispatch, 
                         verbose=verbose, logdir=logdir, save_estimator=save_estimator, 
                         model_id=model_id, refit=refit, backend="bayesopt")
        
        self.random_state = random_state
        self.max_iter = max_iter
        self.max_time = max_time
        self.model_type = model_type
        self.initial_params = initial_params
        self.initial_score = initial_score
        self.initial_design_numdata = initial_design_numdata
        self.initial_design_type = initial_design_type
        self.acquisition_type = acquisition_type
        self.normalize_Y = normalize_Y
        self.exact_feval = exact_feval
        self.acquisition_optimizer_type = acquisition_optimizer_type
        self.model_update_interval = model_update_interval
        self.evaluator_type = evaluator_type
        self.batch_size = batch_size
        
        self.failedscore = None

    def fit(self, X, y=None, validation_data=None, groups=None, 
            feature_groups=None, min_n_features=2):
        """
        Run fit.

        Parameters
        ----------       
        X :numpy.array, pandas.DataFrame or scipy.sparse, shape(axis=0) = (n_samples)
            Features. Detail depends on estimator.

        y: np.ndarray or pd.core.frame.DataFrame, shape(axis=0) = (n_samples) or None, default=None.
            Target variable. detail depends on estimator.

        validation_data: tuple(X, y) or None, default=None.
            Data to compute validation score. detail depends on estimator.
            When validation_data is None, computing validation score is not run.

        groups: array-like, shape = (n_samples,)  or None, default=None.
            Group labels for the samples used while splitting the dataset into train/test set.
            (input of scikit-learn cross-validator)

        feature_groups: array-like, shape = (n_samples,) or None, default=None.
            Group labels for the features used while fearture select.
            When feature_groups is None, fearture selection is not run.

        min_n_features: int, default=2.
            When number of X's feature cols is less than min_n_features, return search failure.
            
            e.g. If estimator has columns sampling function, use this option to avoid X become too small and error.
        """
        X, y, Xvalid, yvalid, cv, param_distributions = self._preproc_fit(X=X, y=y, validation_data=validation_data, feature_groups=feature_groups)
        np.random.seed(self.random_state)

        if self.failedscore is None:
            # If search is failed, Return random score.
            # random score is fixed at first fit.
            self.failedscore = self._random_scoring(y)

        obj = mk_objfunc(X=X, y=y, groups=groups, feature_groups=feature_groups, feature_axis=BaseSearcher.feature_axis, 
                         estimator=self.estimator, scoring=self.scoring, cv=cv, 
                         param_distributions=param_distributions, backend=self.backend, failedscore=self.failedscore, 
                         score_summarizer=BaseSearcher.score_summarizer, 
                         Xvalid=Xvalid, yvalid=yvalid, n_jobs=self.n_jobs, pre_dispatch=self.pre_dispatch, 
                         cvsummarizer=self._cvs, save_estimator=self.save_estimator, min_n_features=min_n_features)

        self.opt = BayesianOptimization(obj, domain=param_distributions, constraints=None, cost_withGradients=None, 
                                        model_type=self.model_type, X=self.initial_params, Y=self.initial_score,
                                        initial_design_numdata=self.initial_design_numdata, 
                                        initial_design_type=self.initial_design_type, 
                                        acquisition_type=self.acquisition_type, normalize_Y=self.normalize_Y,
                                        exact_feval=self.exact_feval, acquisition_optimizer_type=self.acquisition_optimizer_type, 
                                        model_update_interval=self.model_update_interval, evaluator_type=self.evaluator_type, 
                                        batch_size=self.batch_size, num_cores=1, verbosity=False, verbosity_model=False, 
                                        maximize=False, de_duplication=False)   

        try :
            self.opt.run_optimization(max_iter=self.max_iter, max_time=self.max_time)
        except KeyboardInterrupt:
            pass
        
        self._postproc_fit(X=X, y=y, feature_groups=feature_groups, 
                           best_params=self._cvs.best_params_, best_score=self._cvs.best_score_)
        return self


class GAoptCV(BaseSearcher):
    """
    Cross validation optimizer by Genetic Algorithm.

    Parameters
    ----------
    estimator
        scikit-learn estimator like.

    param_distributions: dict.
        Search space.

    scoring: string or sklearn.metrics.make_scorer.
        Evaluation index of search.
        When scoring is None, use stimator default scorer and this score greater is better.
        
    cv: scikit-learn cross-validator or int(number of folds), default=5.
        Cross validation setting.

    max_iter: int, default=32.
        Number of search.

    random_state: int or None, default=None.
        The seed used by the random number generator.

    n_jobs: int, default=1.
        Number of jobs to run in parallel.

    pre_dispatch: int or string, default="2*n_jobs".
        Controls the number of jobs that get dispatched during parallel.

    verbose: int(0, 1 or 2), default=0.
        Controls the verbosity
        
        0: don't display status.

        1: display status by stdout.
        
        2: display status by graph.

    logdir: str or None, default=None.
        Path of directory to save log file.
        When logdir is None,  log is not saved.
        
        [directory structure]
        
        logdir
        
        |-cv_results
        
        | |-{model_id}.csv                                      : search log
        
        | ...
        
        |-estimators_{model_id}
        
            |-{model_id}_index{search count}_split{fold count}.pkl: an estimator which is fitted fold train data
            
            ...
            
            |-{model_id}_index{search count}_test.pkl             : an estimator which is fitted whole train data.

    save_estimator: int, default=0.
        estimator save setting.
        
        0: An estimator is not saved.
        
        1: An estimator which is fitted fold train data is saved per cv-fold.
        
        2: In addition to 1, an estimator which is fitted whole train data is saved per cv.

    model_id: str or None, default=None.
        This is used to log filename.
        When model_id is None, this is generated by date time.

    refit: bool, default=True.
        Refit an estimator using the best found parameters on all train data(=X).

    iter_pergeneration: int, default=8.
        Genetic algorithm's parameter. Number of iteration per generation (it corresponds to number of population.).

    param_crossover_proba: float or function, default=0.5.
        Genetic algorithm's parameter. Probability which a certain parameter becomes another parent value.

        If this value 0 or 1, paramaters is not changed by crossover.

        Function whose variable is number of generation could be passed to this variable.
        Number of generation' s start is 0. But create population by random sampling in generation 0, so this function is used from generation 1.

        Examples
        --------
        >>> def f(generaion):
        >>>     return 0.5 / generaion

    param_mutation_proba: float or function, default=0.01.
        Genetic algorithm's parameter. Probability which a certain parameter is mutated.

        Function whose variable is number of generation Could be passed to this variable.

    random_sampling_proba: float or function, default=0.01.
        Genetic algorithm's parameter. In a certain generation, probability which individual is created by random sampling.

        Function whose variable is number of generation Could be passed to this variable.

    Attributes
    ----------
    cv_results_ : dict of numpy (masked) ndarrays
        A dict with keys as column headers and values as columns, that can be
        imported into a pandas ``DataFrame``.

    best_estimator_ : estimator or dict
        Estimator that was chosen by the search.

    best_score_ : float
        Cross-validated score of the best_estimator.

    best_params_ : dict
        Parameter setting that gave the best results on the hold out data.
    """
    def __init__(self, estimator, param_distributions, 
                 scoring=None, cv=5, max_iter=32, 
                 random_state=None, n_jobs=1, pre_dispatch="2*n_jobs", 
                 verbose=0, logdir=None, save_estimator=0, model_id=None, refit=True, 
                 iter_pergeneration=8, param_crossover_proba=0.5, param_mutation_proba=0.01, 
                 random_sampling_proba=0.01):
        super().__init__(estimator=estimator, param_distributions=param_distributions, 
                         scoring=scoring, cv=cv,  n_jobs=n_jobs, pre_dispatch=pre_dispatch, 
                         verbose=verbose, logdir=logdir, save_estimator=save_estimator, 
                         model_id=model_id, refit=refit, backend="gaopt")

        self.max_iter = max_iter
        self.iter_pergeneration = iter_pergeneration
        self.param_crossover_proba = param_crossover_proba
        self.param_mutation_proba = param_mutation_proba
        self.random_sampling_proba = random_sampling_proba
        if random_state is None:
            self.random_state = random_state
        else:
            self.random_state = np.random.RandomState(int(random_state))

    def fit(self, X, y=None, validation_data=None, groups=None, 
            feature_groups=None, min_n_features=2):
        """
        Run fit.

        Parameters
        ----------       
        X :numpy.array, pandas.DataFrame or scipy.sparse, shape(axis=0) = (n_samples)
            Features. Detail depends on estimator.

        y: np.ndarray or pd.core.frame.DataFrame, shape(axis=0) = (n_samples) or None, default=None.
            Target variable. detail depends on estimator.

        validation_data: tuple(X, y) or None, default=None.
            Data to compute validation score. detail depends on estimator.
            When validation_data is None, computing validation score is not run.

        groups: array-like, shape = (n_samples,)  or None, default=None.
            Group labels for the samples used while splitting the dataset into train/test set.
            (input of scikit-learn cross-validator)

        feature_groups: array-like, shape = (n_samples,) or None, default=None.
            Group labels for the features used while fearture select.
            When feature_groups is None, fearture selection is not run.

        min_n_features: int, default=2.
            When number of X's feature cols is less than min_n_features, return search failure.
            
            e.g. If estimator has columns sampling function, use this option to avoid X become too small and error.
        """
        X, y, Xvalid, yvalid, cv, param_distributions = self._preproc_fit(X=X, y=y, validation_data=validation_data, feature_groups=feature_groups)
        np.random.seed(self.random_state)

        obj = mk_objfunc(X=X, y=y, groups=groups, feature_groups=feature_groups, feature_axis=BaseSearcher.feature_axis, 
                         estimator=self.estimator, scoring=self.scoring, cv=cv, 
                         param_distributions=param_distributions, backend=self.backend, failedscore=np.nan, 
                         score_summarizer=BaseSearcher.score_summarizer, 
                         Xvalid=Xvalid, yvalid=yvalid, n_jobs=self.n_jobs, pre_dispatch=self.pre_dispatch, 
                         cvsummarizer=self._cvs, save_estimator=self.save_estimator, min_n_features=min_n_features)

        try :
            gamin(obj, param_distributions, max_iter=self.max_iter, iter_pergeneration=self.iter_pergeneration, 
                  param_crossover_proba=self.param_crossover_proba, param_mutation_proba=self.param_mutation_proba, 
                  random_sampling_proba=self.random_sampling_proba, cvsummarizer=self._cvs)
        except KeyboardInterrupt:
            pass

        self._postproc_fit(X=X, y=y, feature_groups=feature_groups, 
                           best_params=self._cvs.best_params_, best_score=self._cvs.best_score_)
        return self



class RandomoptCV(BaseSearcher):
    """
    Cross validation optimizer by Random Search.

    Parameters
    ----------
    estimator
        scikit-learn estimator like.

    param_distributions: dict.
        Search space.

    scoring: string or sklearn.metrics.make_scorer.
        Evaluation index of search.
        When scoring is None, use stimator default scorer and this score greater is better.
        
    cv: scikit-learn cross-validator or int(number of folds), default=5.
        Cross validation setting.

    max_iter: int, default=32.
        Number of search.

    random_state: int or None, default=None.
        The seed used by the random number generator.

    n_jobs: int, default=1.
        Number of jobs to run in parallel.

    pre_dispatch: int or string, default="2*n_jobs".
        Controls the number of jobs that get dispatched during parallel.

    verbose: int(0, 1 or 2), default=0.
        Controls the verbosity
        
        0: don't display status.

        1: display status by stdout.
        
        2: display status by graph.

    logdir: str or None, default=None.
        Path of directory to save log file.
        When logdir is None,  log is not saved.
        
        [directory structure]
        
        logdir
        
        |-cv_results
        
        | |-{model_id}.csv                                      : search log
        
        | ...
        
        |-estimators_{model_id}
        
            |-{model_id}_index{search count}_split{fold count}.pkl: an estimator which is fitted fold train data
            
            ...
            
            |-{model_id}_index{search count}_test.pkl             : an estimator which is fitted whole train data.

    save_estimator: int, default=0.
        estimator save setting.
        
        0: An estimator is not saved.
        
        1: An estimator which is fitted fold train data is saved per cv-fold.
        
        2: In addition to 1, an estimator which is fitted whole train data is saved per cv.

    model_id: str or None, default=None.
        This is used to log filename.
        When model_id is None, this is generated by date time.

    refit: bool, default=True.
        Refit an estimator using the best found parameters on all train data(=X).

    Attributes
    ----------
    cv_results_ : dict of numpy (masked) ndarrays
        A dict with keys as column headers and values as columns, that can be
        imported into a pandas ``DataFrame``.

    best_estimator_ : estimator or dict
        Estimator that was chosen by the search.

    best_score_ : float
        Cross-validated score of the best_estimator.

    best_params_ : dict
        Parameter setting that gave the best results on the hold out data.
    """
    def __init__(self, estimator, param_distributions, 
                 scoring=None, cv=5, max_iter=32, 
                 random_state=None, n_jobs=1, pre_dispatch="2*n_jobs", 
                 verbose=0, logdir=None, save_estimator=0, model_id=None, refit=True):
        super().__init__(estimator=estimator, param_distributions=param_distributions, 
                         scoring=scoring, cv=cv,  n_jobs=n_jobs, pre_dispatch=pre_dispatch, 
                         verbose=verbose, logdir=logdir, save_estimator=save_estimator, 
                         model_id=model_id, refit=refit, backend="gaopt")

        self.max_iter = max_iter
        if random_state is None:
            self.random_state = random_state
        else:
            self.random_state = np.random.RandomState(int(random_state))

    def fit(self, X, y=None, validation_data=None, groups=None, 
            feature_groups=None, min_n_features=2):
        """
        Run fit.

        Parameters
        ----------       
        X :numpy.array, pandas.DataFrame or scipy.sparse, shape(axis=0) = (n_samples)
            Features. Detail depends on estimator.

        y: np.ndarray or pd.core.frame.DataFrame, shape(axis=0) = (n_samples) or None, default=None.
            Target variable. detail depends on estimator.

        validation_data: tuple(X, y) or None, default=None.
            Data to compute validation score. detail depends on estimator.
            When validation_data is None, computing validation score is not run.

        groups: array-like, shape = (n_samples,)  or None, default=None.
            Group labels for the samples used while splitting the dataset into train/test set.
            (input of scikit-learn cross-validator)

        feature_groups: array-like, shape = (n_samples,) or None, default=None.
            Group labels for the features used while fearture select.
            When feature_groups is None, fearture selection is not run.

        min_n_features: int, default=2.
            When number of X's feature cols is less than min_n_features, return search failure.
            
            e.g. If estimator has columns sampling function, use this option to avoid X become too small and error.
        """
        X, y, Xvalid, yvalid, cv, param_distributions = self._preproc_fit(X=X, y=y, validation_data=validation_data, feature_groups=feature_groups)
        np.random.seed(self.random_state)

        obj = mk_objfunc(X=X, y=y, groups=groups, feature_groups=feature_groups, feature_axis=BaseSearcher.feature_axis, 
                         estimator=self.estimator, scoring=self.scoring, cv=cv, 
                         param_distributions=param_distributions, backend=self.backend, failedscore=np.nan, 
                         score_summarizer=BaseSearcher.score_summarizer, 
                         Xvalid=Xvalid, yvalid=yvalid, n_jobs=self.n_jobs, pre_dispatch=self.pre_dispatch, 
                         cvsummarizer=self._cvs, save_estimator=self.save_estimator, min_n_features=min_n_features)

        try :
            gamin(obj, param_distributions, max_iter=self.max_iter, iter_pergeneration=1, 
                  param_crossover_proba=0, param_mutation_proba=0, 
                  random_sampling_proba=1, cvsummarizer=self._cvs)
        except KeyboardInterrupt:
            pass

        self._postproc_fit(X=X, y=y, feature_groups=feature_groups, 
                           best_params=self._cvs.best_params_, best_score=self._cvs.best_score_)
        return self