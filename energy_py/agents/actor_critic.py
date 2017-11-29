import logging

from energy_py.agents import BaseAgent


class ActorCritic(BaseAgent):
    """
    A simple Actor-Critic agent

    Parameterize two functions
        actor using an energy_py policy approximator
        critic using an energy_py value function approximator

    The critic sends the temporal difference error for the experienced s and s'
    to the actor, which updates policy parameters using the score function.

    args
        env             : energy_py environment
        discount        : float
        policy          : energy_py policy approximator
        value_function  : energy_py value function approximator
        learning rate   : float
        verbose         : boolean
    """
    def __init__(self,
                 env,
                 discount,
                 brain_path,
                 policy,
                 value_function,
                 lr=0.01,
                 process_reward=None,
                 process_return=None):

        #  passing the environment to the Base_Agent class
        super().__init__(env, discount, brain_path, process_reward, process_return)

        #  create the actor
        self.actor = policy(action_space=self.action_space,
                            lr=lr,
                            observation_dim=self.observation_dim,
                            num_actions=self.num_actions)

        #  create our critic
        #  critic of the current policy (ie on-policy)
        self.critic = value_function(observation_space=self.observation_space,
                                     lr=lr,
                                     layers=[10, 10])

    def _act(self, **kwargs):
        """
        Act according to the policy network

        args
            observation : np array (1, observation_dim)
            session     : a TensorFlow Session object

        return
            action      : np array (1, num_actions)
        """
        observation = kwargs.pop('observation')
        session = kwargs.pop('session')

        #  scaling the observation for use in the policy network
        scl_obs = self.memory.scale_array(observation, self.observation_space)
        scl_obs = scl_obs.reshape(1, self.observation_dim)

        #  generating an action from the policy network
        action, _ = self.actor.get_action(session, scl_obs)

        return action.reshape(1, self.num_actions)

    def _learn(self, **kwargs):
        """
        Update the critic and then the actor

        The critic uses the temporal difference error to update the actor

        args
            observations        : np array (samples, observation_dim)
            actions             : np array (samples, num_actions)
            rewards             : np.array (samples, 1)
            next_obs            : np.array (samples, observation_dim)
            session             : a TensorFlow Session object

        return
            loss                : np float
        """
        obs = kwargs.pop('observations')
        actions = kwargs.pop('actions')
        rew = kwargs.pop('rewards')
        next_obs = kwargs.pop('next_obs')
        session = kwargs.pop('session')

        #  first we update the critic
        #  create a target using a Bellman estimate
        target = rew + self.discount * self.critic.predict(session, next_obs)
        self.memory.info['value fctn target'].append(target)

        #  then we improve the critic using the target
        td_error, critic_loss = self.critic.improve(session, obs, target)

        #  now we can update the actor
        #  we use the temporal difference error from the critic
        actor_loss = self.actor.improve(session,
                                         obs,
                                         actions,
                                         td_error)

        #  output dict to iterate over for saving and printing
        output = {'td_error': td_error,
                  'critic_loss': critic_loss,
                  'actor_loss': actor_loss}

        for k, v in output.items():
            self.memory.info[k].append(v)
            # logging('{} is {:.4f}'.format(k, v))

        #  only calc this so we can return something
        #  makes me think I should do one train op on this loss rather than
        #  two train_ops (critic+actor)
        loss = critic_loss + actor_loss

        return loss