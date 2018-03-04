import gym
import numpy as np


class ReplayMemory():
    def __init__(self, memory_size, burn_in, env_name):

        # The memory essentially stores transitions recorder from the agent
        # taking actions in the environment.

        # Burn in episodes define the number of episodes that are written into the memory from the
        # randomly initialized agent. Memory size is the maximum size after which old elements in the memory are replaced.
        # A simple (if not the most efficient) was to implement the memory is as a list of transitions.
        self.memory_size = memory_size
        self.memory = []
        i = 0
        env = gym.make(env_name)
        while i < burn_in:
            done = False
            state = env.reset()
            while not done and i < burn_in:
                action = env.action_space.sample()
                next_state, reward, done, info = env.step(action)
                self.memory.append((state, action, reward, next_state, done))
                state = next_state
                i += 1
        self.oldest = 0

    def sample(self, batch_size=32):
        # This function returns a batch of randomly sampled transitions - i.e. state, action, reward, next state, terminal flag tuples.
        # You will feed this to your model to train.
        idx = np.random.choice(len(self.memory), batch_size, replace=False)
        return zip(*np.array(self.memory)[idx])

    def append(self, transition):
        # Appends transition to the memory.
        if len(self.memory) < self.memory_size:
            self.memory.append(transition)
        else:
            self.memory[self.oldest] = transition
            self.oldest = (self.oldest + 1) % self.memory_size
