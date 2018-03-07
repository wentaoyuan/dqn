import gym
import numpy as np
import os
import tensorflow as tf
from q_networks import dqn
from replay_memory import ReplayMemory


class DQNAgent:

    # In this class, we will implement functions to do the following.
    # (1) Create an instance of the Q Network class.
    # (2) Create a function that constructs a policy from the Q values predicted by the Q Network.
    #		(a) Epsilon Greedy Policy.
    # 		(b) Greedy Policy.
    # (3) Create a function to train the Q Network, by interacting with the environment.
    # (4) Create a function to test the Q Network's performance on the environment.
    # (5) Create a function for Experience Replay.

    def __init__(self, args):
        # Create an instance of the network itself, as well as the memory.
        # Here is also a good place to set environmental parameters,
        # as well as training parameters - number of episodes / iterations, etc.
        self.env = gym.make(args.env_name)
        self.state = tf.placeholder(tf.float32,
                                    shape=(None,) + self.env.observation_space.shape,
                                    name='state')
        self.q = dqn(self.state, self.env.action_space.n, num_hidden=[])

        self.action = tf.placeholder(tf.int32, shape=(None,), name='action')
        self.reward = tf.placeholder(tf.float32, shape=(None,), name='reward')
        self.is_terminal = tf.placeholder(tf.float32, shape=(None,), name='is_terminal')
        self.q_target = tf.placeholder(tf.float32, shape=(None, self.env.action_space.n), name='q_target')
        # self.loss = tf.reduce_mean(tf.reduce_sum((self.q_target - self.q) ** 2, axis=1))
        target = self.reward + args.gamma * tf.reduce_max(self.q_target, axis=1) * (1 - self.is_terminal)
        self.diff = (target - tf.diag_part(tf.gather(self.q, self.action, axis=1)))
        self.loss = tf.reduce_mean(self.diff ** 2)

        config = tf.ConfigProto()
        config.gpu_options.allow_growth = True
        config.allow_soft_placement = True
        self.sess = tf.Session(config=config)

    def evaluate(self, env_name, num_episodes, epsilon):
        env = gym.make(env_name)
        rewards = np.zeros(num_episodes)
        for i in range(num_episodes):
            done = False
            state = env.reset()
            episode_reward = 0.
            while not done:
                action = self.policy(state, epsilon)
                next_state, reward, done, info = env.step(action)
                episode_reward += reward
                state = next_state
            rewards[i] = episode_reward
        return rewards

    def policy(self, state, epsilon):
        q_values = self.sess.run(self.q, feed_dict={self.state: [state]})
        best_action = np.argmax(q_values[0])
        u = np.random.rand()
        if u > epsilon:
            return best_action
        else:
            return self.env.action_space.sample()

    def train(self, args):
        # In this function, we will train our network.
        # If training without experience replay_memory, then you will interact with the environment
        # in this function, while also updating your network parameters.

        # If you are using a replay memory, you should interact with environment here, and store these
        # transitions to memory, while also updating your model.
        global_step = tf.Variable(0, trainable=False, name='global_step')
        learning_rate = tf.train.exponential_decay(args.base_lr, global_step,
                                                   args.lr_decay_steps, args.lr_decay_rate,
                                                   staircase=True, name='lr')
        learning_rate = tf.maximum(learning_rate, args.lr_clip)
        # learning_rate = tf.constant(args.base_lr, dtype=tf.float32, shape=(), name='learning_rate')
        train_epsilon = tf.train.polynomial_decay(args.init_epsilon, global_step,
                                                  args.epsilon_decay_steps, args.final_epsilon)

        loss_summary = tf.summary.scalar('loss', self.loss)
        lr_summary = tf.summary.scalar('learning_rate', learning_rate)
        epsilon_summary = tf.summary.scalar('epsilon', train_epsilon)
        avg_reward_train = tf.placeholder(tf.float32, shape=(), name='avg_reward_train')
        r_summary = tf.summary.scalar('training average reward', avg_reward_train)
        train_summary = tf.summary.merge([loss_summary, lr_summary, epsilon_summary])
        episode_length = tf.placeholder(tf.int32, shape=(), name='episode_length')
        length_summary = tf.summary.scalar('episode_length', episode_length)
        avg_reward = tf.placeholder(tf.float32, shape=(), name='avg_reward')
        reward_summary = tf.summary.scalar('average reward', avg_reward)
        writer = tf.summary.FileWriter(args.log_dir, self.sess.graph)

        trainer = tf.train.AdamOptimizer(learning_rate)
        train_op = trainer.minimize(self.loss, global_step)

        saver = tf.train.Saver()
        if args.restore:
            saver.restore(self.sess, tf.train.latest_checkpoint(args.log_dir))
        else:
            self.sess.run(tf.global_variables_initializer())
        save_path = os.path.join(args.log_dir, 'checkpoints', 'model')
        saver.save(self.sess, save_path, global_step)
        steps_per_save = args.max_iter // 3

        if args.replay:
            replay = ReplayMemory(args.memory_size, args.burn_in, args.env_name, self.policy, args.init_epsilon)

        i = 0
        episode_start = i
        avg_r_train = 0
        state = self.env.reset()
        while i < args.max_iter:
            epsilon = self.sess.run(train_epsilon)
            action = self.policy(state, epsilon)
            next_state, reward, is_terminal, info = self.env.step(action)
            if args.replay:
                replay.append((state, action, reward, next_state, is_terminal))
                states, actions, rewards, next_states, is_terminals = replay.sample(args.batch_size)
                q_target = self.sess.run(self.q, feed_dict={self.state: next_states})
                # q = self.sess.run(self.q, feed_dict={self.state: states})
                # q_target = q.copy()
                # q_target[range(args.batch_size), list(actions)] = \
                #     np.array(rewards) + args.gamma * q_next.max(1) * (1 - np.array(is_terminals))
                # print(q_target - q)
                _, loss, diff, summary = self.sess.run([train_op, self.loss, self.diff, train_summary],
                                                 feed_dict={self.state: states,
                                                            self.action: actions,
                                                            self.reward: rewards,
                                                            self.is_terminal: is_terminals,
                                                            self.q_target: q_target})
                # print(diff)
            else:
                q_target = self.sess.run(self.q, feed_dict={self.state: [next_state]})
                _, loss, summary = self.sess.run([train_op, self.loss, train_summary],
                                                 feed_dict={self.state: [state],
                                                            self.action: [action],
                                                            self.reward: [reward],
                                                            self.is_terminal: [is_terminal],
                                                            self.q_target: q_target})
            i += 1
            writer.add_summary(summary, i)
            # avg_r_train += (reward - avg_r_train) / i
            # summary = self.sess.run(r_summary, feed_dict={avg_reward_train: avg_r_train})
            # writer.add_summary(summary, i)
            if is_terminal:
                state = self.env.reset()
                summary = self.sess.run(length_summary,
                                        feed_dict={episode_length: i - episode_start})
                writer.add_summary(summary, i)
                episode_start = i
            else:
                state = next_state
            if i % args.steps_per_eval == 0:
                rewards = self.evaluate(args.env_name, args.eval_episodes, args.final_epsilon)
                summary = self.sess.run(reward_summary,
                                        feed_dict={avg_reward: rewards.mean()})
                writer.add_summary(summary, i)
                print('Step: %d    Average reward: %f' % (i, rewards.mean()))
                q_values = self.sess.run(self.q, feed_dict={self.state: [state]})
                print(q_values)
                print(rewards)
                print('Loss:', loss)
                state = self.env.reset()
                episode_start = i
            if i % steps_per_save == 0:
                saver.save(self.sess, save_path, global_step)
        saver.save(self.sess, save_path, global_step)
