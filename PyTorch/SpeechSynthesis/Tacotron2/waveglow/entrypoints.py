# *****************************************************************************
#  Copyright (c) 2018, NVIDIA CORPORATION.  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#      * Redistributions of source code must retain the above copyright
#        notice, this list of conditions and the following disclaimer.
#      * Redistributions in binary form must reproduce the above copyright
#        notice, this list of conditions and the following disclaimer in the
#        documentation and/or other materials provided with the distribution.
#      * Neither the name of the NVIDIA CORPORATION nor the
#        names of its contributors may be used to endorse or promote products
#        derived from this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL NVIDIA CORPORATION BE LIABLE FOR ANY
#  DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# *****************************************************************************

import urllib.request
import torch
import os
import sys


# from https://github.com/NVIDIA/DeepLearningExamples/blob/master/PyTorch/SpeechSynthesis/Tacotron2/inference.py
def checkpoint_from_distributed(state_dict):
    """
    Checks whether checkpoint was generated by DistributedDataParallel. DDP
    wraps model in additional "module.", it needs to be unwrapped for single
    GPU inference.
    :param state_dict: model's state dict
    """
    ret = False
    for key, _ in state_dict.items():
        if key.find('module.') != -1:
            ret = True
            break
    return ret


# from https://github.com/NVIDIA/DeepLearningExamples/blob/master/PyTorch/SpeechSynthesis/Tacotron2/inference.py
def unwrap_distributed(state_dict):
    """
    Unwraps model from DistributedDataParallel.
    DDP wraps model in additional "module.", it needs to be removed for single
    GPU inference.
    :param state_dict: model's state dict
    """
    new_state_dict = {}
    for key, value in state_dict.items():
        new_key = key.replace('module.1.', '')
        new_key = new_key.replace('module.', '')
        new_state_dict[new_key] = value
    return new_state_dict


def _download_checkpoint(checkpoint, force_reload):
    model_dir = os.path.join(torch.hub._get_torch_home(), 'checkpoints')
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
    ckpt_file = os.path.join(model_dir, os.path.basename(checkpoint))
    if not os.path.exists(ckpt_file) or force_reload:
        sys.stderr.write('Downloading checkpoint from {}\n'.format(checkpoint))
        urllib.request.urlretrieve(checkpoint, ckpt_file)
    return ckpt_file

def nvidia_waveglow(pretrained=True, **kwargs):
    """Constructs a WaveGlow model (nn.module with additional infer(input) method).
    For detailed information on model input and output, training recipies, inference and performance
    visit: github.com/NVIDIA/DeepLearningExamples and/or ngc.nvidia.com
    Args:
        pretrained (bool): If True, returns a model pretrained on LJ Speech dataset.
        model_math (str, 'fp32'): returns a model in given precision ('fp32' or 'fp16')
    """

    from waveglow import model as waveglow

    fp16 = "model_math" in kwargs and kwargs["model_math"] == "fp16"
    force_reload = "force_reload" in kwargs and kwargs["force_reload"]

    if pretrained:
        if fp16:
            checkpoint = 'https://api.ngc.nvidia.com/v2/models/nvidia/waveglow_ckpt_amp/versions/19.09.0/files/nvidia_waveglowpyt_fp16_20190427'
        else:
            checkpoint = 'https://api.ngc.nvidia.com/v2/models/nvidia/waveglow_ckpt_fp32/versions/19.09.0/files/nvidia_waveglowpyt_fp32_20190427'
        ckpt_file = _download_checkpoint(checkpoint, force_reload)
        ckpt = torch.load(ckpt_file)
        state_dict = ckpt['state_dict']
        if checkpoint_from_distributed(state_dict):
            state_dict = unwrap_distributed(state_dict)
        config = ckpt['config']
    else:
        config = {'n_mel_channels': 80, 'n_flows': 12, 'n_group': 8,
                  'n_early_every': 4, 'n_early_size': 2,
                  'WN_config': {'n_layers': 8, 'kernel_size': 3,
                                'n_channels': 512}}
        for k,v in kwargs.items():
            if k in config.keys():
                config[k] = v
            elif k in config['WN_config'].keys():
                config['WN_config'][k] = v

    m = waveglow.WaveGlow(**config)

    if pretrained:
        m.load_state_dict(state_dict)

    return m
