#
# Copyright (c) 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from typing import Union

import numpy as np
from rl_coach.agents.policy_optimization_agent import PolicyOptimizationAgent, PolicyGradientRescaler
from rl_coach.architectures.tensorflow_components.heads.policy_head import PolicyHeadParameters
from rl_coach.architectures.tensorflow_components.middlewares.fc_middleware import FCMiddlewareParameters
from rl_coach.base_parameters import NetworkParameters, AlgorithmParameters, \
    AgentParameters, InputEmbedderParameters
from rl_coach.exploration_policies.additive_noise import AdditiveNoiseParameters
from rl_coach.spaces import DiscreteActionSpace

from rl_coach.logger import screen
from rl_coach.memories.episodic.single_episode_buffer import SingleEpisodeBufferParameters


class PolicyGradientNetworkParameters(NetworkParameters):
    def __init__(self):
        super().__init__()
        self.input_embedders_parameters = {'observation': InputEmbedderParameters()}
        self.middleware_parameters = FCMiddlewareParameters()
        self.heads_parameters = [PolicyHeadParameters()]
        self.loss_weights = [1.0]
        self.async_training = True


class PolicyGradientAlgorithmParameters(AlgorithmParameters):
    def __init__(self):
        super().__init__()
        self.policy_gradient_rescaler = PolicyGradientRescaler.FUTURE_RETURN_NORMALIZED_BY_TIMESTEP
        self.apply_gradients_every_x_episodes = 5
        self.beta_entropy = 0
        self.num_steps_between_gradient_updates = 20000  # this is called t_max in all the papers


class PolicyGradientsAgentParameters(AgentParameters):
    def __init__(self):
        super().__init__(algorithm=PolicyGradientAlgorithmParameters(),
                         exploration=AdditiveNoiseParameters(),
                         memory=SingleEpisodeBufferParameters(),
                         networks={"main": PolicyGradientNetworkParameters()})

    @property
    def path(self):
        return 'rl_coach.agents.policy_gradients_agent:PolicyGradientsAgent'


class PolicyGradientsAgent(PolicyOptimizationAgent):
    def __init__(self, agent_parameters, parent: Union['LevelManager', 'CompositeAgent']=None):
        super().__init__(agent_parameters, parent)
        self.returns_mean = self.register_signal('Returns Mean')
        self.returns_variance = self.register_signal('Returns Variance')
        self.last_gradient_update_step_idx = 0

    def learn_from_batch(self, batch):
        # batch contains a list of episodes to learn from
        network_keys = self.ap.network_wrappers['main'].input_embedders_parameters.keys()

        total_returns = batch.total_returns()
        for i in reversed(range(batch.size)):
            if self.policy_gradient_rescaler == PolicyGradientRescaler.TOTAL_RETURN:
                total_returns[i] = total_returns[0]
            elif self.policy_gradient_rescaler == PolicyGradientRescaler.FUTURE_RETURN:
                # just take the total return as it is
                pass
            elif self.policy_gradient_rescaler == PolicyGradientRescaler.FUTURE_RETURN_NORMALIZED_BY_EPISODE:
                # we can get a single transition episode while playing Doom Basic, causing the std to be 0
                if self.std_discounted_return != 0:
                    total_returns[i] = (total_returns[i] - self.mean_discounted_return) / self.std_discounted_return
                else:
                    total_returns[i] = 0
            elif self.policy_gradient_rescaler == PolicyGradientRescaler.FUTURE_RETURN_NORMALIZED_BY_TIMESTEP:
                total_returns[i] -= self.mean_return_over_multiple_episodes[i]
            else:
                screen.warning("WARNING: The requested policy gradient rescaler is not available")

        targets = total_returns
        actions = batch.actions()
        if type(self.spaces.action) != DiscreteActionSpace and len(actions.shape) < 2:
            actions = np.expand_dims(actions, -1)

        self.returns_mean.add_sample(np.mean(total_returns))
        self.returns_variance.add_sample(np.std(total_returns))

        result = self.networks['main'].online_network.accumulate_gradients(
            {**batch.states(network_keys), 'output_0_0': actions}, targets
        )
        total_loss, losses, unclipped_grads = result[:3]

        return total_loss, losses, unclipped_grads
