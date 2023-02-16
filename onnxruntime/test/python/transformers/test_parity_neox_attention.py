# --------------------------------------------------------------------------
# Copyright 2020 The HuggingFace Inc. team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
# --------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation.  All rights reserved.
# Licensed under the MIT License.  See License.txt in the project root for
# license information.
# -------------------------------------------------------------------------

import numpy as np
import torch
from torch import nn


def create_neox_attention_graph(
    batch_size,
    seq_len,
    hidden_size,
    qkv_weight,
    qkv_bias,
    num_heads,
    use_rotary,
):
    from onnx import TensorProto, helper

    nodes = [
        helper.make_node(
            "Attention",
            [
                "input",
                "weight",
                "bias",
            ],
            ["output"],
            "NeoXAttention_0",
            num_heads=num_heads,
            unidirectional=1,
            do_rotary=(use_rotary is True),
            domain="com.microsoft",
        ),
    ]

    initializers = [
        helper.make_tensor("weight", TensorProto.FLOAT, [hidden_size, 3 * hidden_size], qkv_weight.flatten().tolist()),
        helper.make_tensor("bias", TensorProto.FLOAT, [3 * hidden_size], qkv_bias.flatten().tolist()),
    ]

    graph = helper.make_graph(
        nodes,
        "NeoXAttention_Graph",
        [
            helper.make_tensor_value_info("input", TensorProto.FLOAT, [batch_size, seq_len, hidden_size]),
        ],
        [
            helper.make_tensor_value_info("output", TensorProto.FLOAT, [batch_size, seq_len, hidden_size]),
        ],
        initializers,
    )

    model = helper.make_model(graph)
    return model.SerializeToString()


class RotaryEmbedding(torch.nn.Module):
    def __init__(self, dim, max_position_embeddings, base=10000, device=None):
        super().__init__()
        inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2).float().to(device) / dim))
        self.register_buffer("inv_freq", inv_freq)

        # Build here to make `torch.jit.trace` work.
        self.max_seq_len_cached = max_position_embeddings
        t = torch.arange(self.max_seq_len_cached, device=self.inv_freq.device, dtype=self.inv_freq.dtype)
        freqs = torch.einsum("i,j->ij", t, self.inv_freq)
        # Different from paper, but it uses a different permutation in order to obtain the same calculation
        emb = torch.cat((freqs, freqs), dim=-1)
        self.cos_cached = emb.cos()[None, None, :, :]
        self.sin_cached = emb.sin()[None, None, :, :]

    def forward(self, x, seq_len=None):
        # x: [bs, num_attention_heads, seq_len, head_size]
        # This `if` block is unlikely to be run after we build sin/cos in `__init__`. Keep the logic here just in case.
        if seq_len > self.max_seq_len_cached:
            self.max_seq_len_cached = seq_len
            t = torch.arange(self.max_seq_len_cached, device=x.device, dtype=self.inv_freq.dtype)
            freqs = torch.einsum("i,j->ij", t, self.inv_freq)
            # Different from paper, but it uses a different permutation in order to obtain the same calculation
            emb = torch.cat((freqs, freqs), dim=-1).to(x.device)
            self.cos_cached = emb.cos()[None, None, :, :]
            self.sin_cached = emb.sin()[None, None, :, :]
        return self.cos_cached[:seq_len, ...].to(x.device), self.sin_cached[:seq_len, ...].to(x.device)


def rotate_half(x):
    """Rotates half the hidden dims of the input."""
    x1 = x[..., : x.shape[-1] // 2]
    x2 = x[..., x.shape[-1] // 2 :]
    return torch.cat((-x2, x1), dim=-1)


def apply_rotary_pos_emb(q, k, cos, sin, offset: int = 0):
    cos = cos[..., offset : q.shape[-2] + offset, :]
    sin = sin[..., offset : q.shape[-2] + offset, :]
    q_embed = (q * cos) + (rotate_half(q) * sin)
    k_embed = (k * cos) + (rotate_half(k) * sin)
    return q_embed, k_embed


class GPTNeoXAttention(nn.Module):
    def __init__(self, batch_size, seq_len, num_head, hidden_size, use_rotary):
        super().__init__()
        self.use_rotary = use_rotary
        self.num_attention_heads = num_head
        self.hidden_size = hidden_size
        self.head_size = self.hidden_size // self.num_attention_heads
        self.rotary_ndims = int(self.head_size)
        max_positions = 512
        self.register_buffer(
            "bias",
            torch.tril(torch.ones((max_positions, max_positions), dtype=torch.uint8)).view(
                1, 1, max_positions, max_positions
            ),
        )
        self.register_buffer("masked_bias", torch.tensor(-1e9))
        self.rotary_emb = RotaryEmbedding(self.rotary_ndims, 512, 10000)
        self.norm_factor = torch.sqrt(torch.tensor(self.head_size, dtype=torch.float32)).to(torch.get_default_dtype())
        self.query_key_value = nn.Linear(hidden_size, 3 * hidden_size)

        # self.query_key_value.weight.data.copy_(torch.tensor(np.ones((3 * hidden_size, hidden_size))))
        # self.query_key_value.bias.data.copy_(torch.tensor(np.zeros((3 * hidden_size))))

        self.onnx_graph = create_neox_attention_graph(
            batch_size,
            seq_len,
            self.hidden_size,
            self.query_key_value.weight.reshape(self.num_attention_heads, 3, -1)
            .transpose(0, 1)
            .reshape(3 * self.hidden_size, -1)
            .transpose(0, 1),
            self.query_key_value.bias.reshape(self.num_attention_heads, 3, -1).transpose(0, 1).reshape(-1),
            self.num_attention_heads,
            self.use_rotary,
        )

    @classmethod
    def _merge_heads(cls, tensor, num_attention_heads, attn_head_size):
        """
        Merges attn_head_size dim and num_attn_heads dim into hidden dim
        """
        # tensor [bs, num_attention_heads, seq_len, attn_head_size]
        tensor = tensor.permute(0, 2, 1, 3).contiguous()
        # -> [bs, seq_len, num_attention_heads, attn_head_size]
        tensor = tensor.view(tensor.size(0), tensor.size(1), num_attention_heads * attn_head_size)
        # -> [bs, seq_len, hidden_size]
        return tensor

    def _attn(self, query, key, value, attention_mask=None, head_mask=None):
        # q, k, v: [bs, num_attention_heads, seq_len, attn_head_size]
        # compute causal mask from causal mask buffer
        batch_size, num_attention_heads, query_length, attn_head_size = query.size()
        key_length = key.size(-2)

        causal_mask = self.bias[:, :, key_length - query_length : key_length, :key_length].bool()

        query = query.view(batch_size * num_attention_heads, query_length, attn_head_size)
        key = key.view(batch_size * num_attention_heads, key_length, attn_head_size)
        attn_scores = torch.zeros(
            batch_size * num_attention_heads,
            query_length,
            key_length,
            dtype=query.dtype,
            device=key.device,
        )
        attn_scores = torch.baddbmm(
            attn_scores,
            query,
            key.transpose(1, 2),
            beta=1.0,
            alpha=(torch.tensor(1.0, dtype=self.norm_factor.dtype, device=self.norm_factor.device) / self.norm_factor),
        )
        attn_scores = attn_scores.view(batch_size, num_attention_heads, query_length, key_length)
        print("torch:qk", attn_scores)

        mask_value = torch.finfo(attn_scores.dtype).min
        # Need to be a tensor, otherwise we get error: `RuntimeError: expected scalar type float but found double`.
        # Need to be on the same device, otherwise `RuntimeError: ..., x and y to be on the same device`
        mask_value = torch.tensor(mask_value, dtype=attn_scores.dtype).to(attn_scores.device)
        attn_scores = torch.where(causal_mask, attn_scores, mask_value)

        if attention_mask is not None:
            # Apply the attention mask
            attn_scores = attn_scores + attention_mask

        attn_weights = nn.functional.softmax(attn_scores, dim=-1)
        attn_weights = attn_weights.to(value.dtype)
        print("torch:softmax", attn_weights)

        # Mask heads if we want to
        if head_mask is not None:
            attn_weights = attn_weights * head_mask

        attn_output = torch.matmul(attn_weights, value)
        print("torch:unfused_output", attn_output)
        return attn_output, attn_weights

    def onnx_forward(
        self,
        hidden_states,
    ):
        ort_inputs = {
            "input": np.ascontiguousarray(hidden_states.cpu().numpy()),
        }

        from onnxruntime import InferenceSession, SessionOptions

        sess_options = SessionOptions()
        ort_session = InferenceSession(self.onnx_graph, sess_options, providers=["CUDAExecutionProvider"])
        ort_output = ort_session.run(None, ort_inputs)

        output = torch.tensor(ort_output)

        return output

    def torch_forward(
        self,
        hidden_states,
        attention_mask=None,
        head_mask=None,
        layer_past=None,
        use_cache=False,
        output_attentions=False,
    ):
        has_layer_past = layer_past is not None

        # Compute QKV
        # Attention heads [batch, seq_len, hidden_size]
        #   --> [batch, seq_len, (np * 3 * head_size)]
        qkv = self.query_key_value(hidden_states)

        # [batch, seq_len, (num_heads * 3 * head_size)]
        #   --> [batch, seq_len, num_heads, 3 * head_size]
        new_qkv_shape = qkv.size()[:-1] + (self.num_attention_heads, 3 * self.head_size)
        qkv = qkv.view(*new_qkv_shape)

        # [batch, seq_len, num_attention_heads, 3 * head_size] --> 3 [batch, num_attention_heads, seq_len, head_size]
        query = qkv[..., : self.head_size].permute(0, 2, 1, 3)
        key = qkv[..., self.head_size : 2 * self.head_size].permute(0, 2, 1, 3)
        value = qkv[..., 2 * self.head_size :].permute(0, 2, 1, 3)

        print("torch:q", query)
        print("torch:k", key)
        print("torch:v", value)

        if self.use_rotary:
            # Compute rotary embeddings on rotary_ndims
            query_rot = query[..., : self.rotary_ndims]
            query_pass = query[..., self.rotary_ndims :]
            key_rot = key[..., : self.rotary_ndims]
            key_pass = key[..., self.rotary_ndims :]

            # Compute token offset for rotary embeddings (when decoding)
            seq_len = key.shape[-2]
            offset = 0
            if has_layer_past:
                offset = layer_past[0].shape[-2]
                seq_len += offset
            cos, sin = self.rotary_emb(value, seq_len=seq_len)
            query, key = apply_rotary_pos_emb(query_rot, key_rot, cos, sin, offset=offset)
            query = torch.cat((query, query_pass), dim=-1)
            key = torch.cat((key, key_pass), dim=-1)
            print("torch:query_after_rotary", query)
            print("torch:key_after_rotary", key)

        # Cache QKV values
        if has_layer_past:
            past_key = layer_past[0]
            past_value = layer_past[1]
            key = torch.cat((past_key, key), dim=-2)
            value = torch.cat((past_value, value), dim=-2)
        present = (key, value) if use_cache else None

        # Compute attention
        attn_output, _ = self._attn(query, key, value, attention_mask, head_mask)

        # Reshape outputs
        attn_output = self._merge_heads(attn_output, self.num_attention_heads, self.head_size)

        return attn_output


if __name__ == "__main__":
    batch_size = 1
    seq_len = 4
    num_head = 2
    hidden_size = 4

    attn = GPTNeoXAttention(batch_size, seq_len, num_head, hidden_size, use_rotary=True)
    hidden_states = torch.normal(mean=0.5, std=0.1, size=(batch_size, seq_len, hidden_size)).to(torch.float32)

    torch_output = attn.torch_forward(hidden_states)
    ort_output = attn.onnx_forward(hidden_states)

    print("torch_output", torch_output)
    print("ort_output", ort_output)
    print(torch_output - ort_output)
