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

import tensorflow as tf
from rl_coach.base_parameters import AgentParameters
from rl_coach.spaces import SpacesDefinition

from rl_coach.architectures.tensorflow_components.heads.head import Head, normalized_columns_initializer, HeadParameters
from rl_coach.core_types import VStateValue


class VHeadParameters(HeadParameters):
    def __init__(self, activation_function: str ='relu', name: str='v_head_params'):
        super().__init__(parameterized_class=VHead, activation_function=activation_function, name=name)


class VHead(Head):
    def __init__(self, agent_parameters: AgentParameters, spaces: SpacesDefinition, network_name: str,
                 head_idx: int = 0, loss_weight: float = 1., is_local: bool = True, activation_function: str='relu'):
        super().__init__(agent_parameters, spaces, network_name, head_idx, loss_weight, is_local, activation_function)
        self.name = 'v_values_head'
        self.return_type = VStateValue

        if agent_parameters.network_wrappers[self.network_name.split('/')[0]].replace_mse_with_huber_loss:
            self.loss_type = tf.losses.huber_loss
        else:
            self.loss_type = tf.losses.mean_squared_error

    def _build_module(self, input_layer):
        # Standard V Network
        self.output = tf.layers.dense(input_layer, 1, name='output',
                                      kernel_initializer=normalized_columns_initializer(1.0))
