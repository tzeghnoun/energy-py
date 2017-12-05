import collections
import logging

import numpy as np
import pandas as pd

from energy_py import Utils

logger = logging.getLogger(__name__)


class Memory(Utils):
    """
    Purpose of this class is to
        store the experiences of the agent
        process experiences for use by the agent to act or learn from

    Experience is held in a list of tuples
        (observation,          0
         action,               1
         reward,               2
         next_observation,     3
         terminal,             4
         step,                 5
         episode)              6

    self.info is a dictionary that can be used to keep track of any
    statistics as generated by the agent
    """

    def __init__(self,
                 observation_space,
                 action_space,
                 discount,
                 memory_length):

        super().__init__()

        #  MDP info
        self.observation_space = observation_space
        self.action_space = action_space
        self.discount = discount

        #  memory & processing info
        self.length = memory_length

        self.reset()

    def reset(self):
        """
        Resets the two experiences lists and info
        """
        self.experiences = []
        self.info = collections.defaultdict(list)
        self.outputs = collections.defaultdict(list)

    def add_experience(self,
                       observation,
                       action,
                       reward,
                       next_observation,
                       terminal,
                       step,
                       episode):
        """
        Adds a single step of experience to the two experiences lists

        args
            observation
            action
            reward
            next_observation
            terminal
            step
            episode
        """
        logger.debug('adding exp Episode {} Step {}'.format(episode, step))

        self.experiences.append((observation,
                                 action,
                                 reward,
                                 next_observation,
                                 terminal,
                                 step,
                                 episode))

    def calculate_returns(self, rewards):
        """
        Calculates the Monte Carlo discounted return

        args
            episode_number (int)
            normalize_return (str): determines method for scaling return
        """

        #  now we can calculate the Monte Carlo discounted return
        #  R = the return from s'
        R, returns = 0, []
        #  note that we reverse the list here
        for r in rewards[::-1]:
            R = r + self.discount * R  # the Bellman equation
            returns.insert(0, R)

        #  turn into array, print out some statistics before we scale
        rtns = np.array(returns)
        logger.info('total returns before scl {:.2f}'.format(rtns.sum()))
        logger.info('mean returns before scl {:.2f}'.format(rtns.mean()))
        logger.debug('stdv returns before scl {:.2f}'.format(rtns.std()))

        return rtns.reshape(-1, 1)

    def get_episode_batch(self, episode_number):
        """
        Gets the experiences for a given episode

        args
            episode_number (int)
            scaled_actions (bool): whether or not to scale the actions

        returns
            observations (np.array): shape=(samples, self.observation_dim)
            actions (np.array): shape=(samples, self.action_dim)
            rewards (np.array): shape=(samples, 1)
        """

        #  use boolean indexing to get experiences from last episode
        exps = np.asarray(self.experiences)
        episode_mask = [exps[:, 6] == episode_number]
        episode_exps = exps[episode_mask]

        observations = episode_exps[:, 0]
        actions = episode_exps[:, 1]
        rewards = episode_exps[:, 2]

        observations = np.concatenate(observations)
        actions = np.concatenate(actions)
        rewards = np.array(rewards, dtype=np.float64)

        observations = observations.reshape(-1, self.observation_space.shape[0])
        actions = actions.reshape(-1, self.action_space.shape[0])
        rewards = rewards.reshape(-1, 1)

        assert observations.shape[0] == actions.shape[0]
        assert observations.shape[0] == rewards.shape[0]

        assert not np.any(np.isnan(observations))
        assert not np.any(np.isnan(actions))
        assert not np.any(np.isnan(rewards))

        return observations, actions, rewards

    def get_random_batch(self, batch_size, save_batch=False):
        """
        Gets a random batch of experiences

        args
            batch_size (int)

        returns
            batch (np.array): array containing a batch of experience

        """
        sample_size = min(batch_size, len(self.experiences))
        logger.debug('getting batch size {} from memory'.format(sample_size))

        #  limiting to the memory length
        memory = np.array(self.experiences[-self.length:])

        #  indicies for the batch
        indicies = np.random.randint(low=0,
                                     high=len(memory),
                                     size=sample_size).reshape(1, -1)
        
        batch = memory[indicies].reshape(sample_size, -1)
        return batch 

    def output_results(self):
        """
        Extract data from the memory

        returns
            self.outputs (dict): includes self.info
        """
        self.outputs['info'] = self.info

        #  now we combine self.info into a single dataframe
        obs, act, rew, nxt_obs, term, stp, ep = [], [], [], [], [], [], []
        for exp in self.experiences:
            #  obs, action and next_obs are all arrays
            obs.append(exp[0])
            act.append(exp[1])
            rew.append(exp[2])
            nxt_obs.append(exp[3])
            term.append(exp[4])
            stp.append(exp[5])
            ep.append(exp[6])

        df_dict = {
                   'observation': obs,
                   'action': act,
                   'reward': rew,
                   'next_observation': nxt_obs,
                   'terminal': term,
                   'step': stp,
                   'episode': ep,
                   }

        #  make a dataframe on a step by step basis
        df_stp = pd.DataFrame.from_dict(df_dict)
        df_stp.set_index('episode', drop=True, inplace=True)

        #  make a dataframe on an episodic basis
        df_ep = df_stp.groupby(by=['episode'], axis=0).sum()

        #  add statistics into the episodic dataframe
        reward = df_ep.loc[:, 'reward']
        df_ep.loc[:, 'cum max reward'] = reward.cummax()
        #  set the window at 10% of the data
        window = int(df_ep.shape[0]*0.1)
        df_ep.loc[:, 'rolling mean'] = reward.rolling(window,
                                                      min_periods=1).mean()
        df_ep.loc[:, 'rolling std'] = pd.rolling_std(reward, window,
                                                     min_periods=1)

        #  saving data in the output_dict
        self.outputs['df_stp'] = df_stp
        self.outputs['df_ep'] = df_ep

        return self.outputs
