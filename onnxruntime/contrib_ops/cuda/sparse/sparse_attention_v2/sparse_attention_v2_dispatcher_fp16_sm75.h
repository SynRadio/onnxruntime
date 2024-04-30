// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

// This file is generated by compile_sparse_attention_v2.py

#pragma once
#include "contrib_ops/cuda/sparse/sparse_attention_v2/sparse_attention_v2_common.h"

namespace onnxruntime {
namespace contrib {
namespace cuda {
namespace sparse_attention_v2 {

// launcher for: sparse_attention_v2_fp16_sm75_1x128x64x64x128x16x1x0_warps1xstages3
Status sparse_attention_v2_fp16_sm75_a6bdc951(SparseAttentionParams& params);

Status sparse_attention_v2_fp16_sm75_1x128x64x64x128x16x1x0_warps1xstages3(SparseAttentionParams& params) {
  return sparse_attention_v2_fp16_sm75_a6bdc951(params);
}

// load for: sparse_attention_v2_fp16_sm75_1x128x64x64x128x16x1x0_warps1xstages3
void load_sparse_attention_v2_fp16_sm75_a6bdc951();
void load_sparse_attention_v2_fp16_sm75_1x128x64x64x128x16x1x0_warps1xstages3() {
  load_sparse_attention_v2_fp16_sm75_a6bdc951();
}

// unload for: sparse_attention_v2_fp16_sm75_1x128x64x64x128x16x1x0_warps1xstages3
void unload_sparse_attention_v2_fp16_sm75_a6bdc951();
void unload_sparse_attention_v2_fp16_sm75_1x128x64x64x128x16x1x0_warps1xstages3() {
  unload_sparse_attention_v2_fp16_sm75_a6bdc951();
}

// launcher for: sparse_attention_v2_fp16_sm75_1x128x64x64x128x64x1x0_warps4xstages3
Status sparse_attention_v2_fp16_sm75_ca298032(SparseAttentionParams& params);

Status sparse_attention_v2_fp16_sm75_1x128x64x64x128x64x1x0_warps4xstages3(SparseAttentionParams& params) {
  return sparse_attention_v2_fp16_sm75_ca298032(params);
}

// load for: sparse_attention_v2_fp16_sm75_1x128x64x64x128x64x1x0_warps4xstages3
void load_sparse_attention_v2_fp16_sm75_ca298032();
void load_sparse_attention_v2_fp16_sm75_1x128x64x64x128x64x1x0_warps4xstages3() {
  load_sparse_attention_v2_fp16_sm75_ca298032();
}

// unload for: sparse_attention_v2_fp16_sm75_1x128x64x64x128x64x1x0_warps4xstages3
void unload_sparse_attention_v2_fp16_sm75_ca298032();
void unload_sparse_attention_v2_fp16_sm75_1x128x64x64x128x64x1x0_warps4xstages3() {
  unload_sparse_attention_v2_fp16_sm75_ca298032();
}

typedef Status (*kernel_func_t)(SparseAttentionParams& params);
kernel_func_t sparse_attention_v2_fp16_sm75_kernels[] = {
    sparse_attention_v2_fp16_sm75_1x128x64x64x128x16x1x0_warps1xstages3,
    sparse_attention_v2_fp16_sm75_1x128x64x64x128x64x1x0_warps4xstages3,
};

int sparse_attention_v2_fp16_sm75_get_num_algos(void) {
  return (int)sizeof(sparse_attention_v2_fp16_sm75_kernels);
}

Status sparse_attention_v2_fp16_sm75(SparseAttentionParams& params, int algo_id) {
  assert(algo_id < (int)sizeof(sparse_attention_v2_fp16_sm75_kernels));
  return sparse_attention_v2_fp16_sm75_kernels[algo_id](params);
}

void load_sparse_attention_v2_fp16_sm75(void) {
  load_sparse_attention_v2_fp16_sm75_1x128x64x64x128x16x1x0_warps1xstages3();
  load_sparse_attention_v2_fp16_sm75_1x128x64x64x128x64x1x0_warps4xstages3();
}

void unload_sparse_attention_v2_fp16_sm75(void) {
  unload_sparse_attention_v2_fp16_sm75_1x128x64x64x128x16x1x0_warps1xstages3();
  unload_sparse_attention_v2_fp16_sm75_1x128x64x64x128x64x1x0_warps4xstages3();
}

Status sparse_attention_v2_fp16_sm75_default(SparseAttentionParams& params) {
  return sparse_attention_v2_fp16_sm75(params, 0);
}

}  // namespace sparse_attention_v2
}  // namespace cuda
}  // namespace contrib
}  // namespace onnxruntime
