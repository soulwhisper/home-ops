#!/bin/sh
set -eu

MODEL_ROOT="$HOME/models/qwen-image-2.1"
COMFY_MODELS="$HOME/ComfyUI/models"

mkdir -p \
  "$COMFY_MODELS/diffusion_models" \
  "$COMFY_MODELS/text_encoders" \
  "$COMFY_MODELS/vae"

ln -sfn \
  "$MODEL_ROOT/diffusion_models/qwen-image-2.1-UC-int8_convrot.safetensors" \
  "$COMFY_MODELS/diffusion_models/qwen-image-2.1-UC-int8_convrot.safetensors"
ln -sfn \
  "$MODEL_ROOT/text_encoders/qwen3vl_8b_int8_convrot.safetensors" \
  "$COMFY_MODELS/text_encoders/qwen3vl_8b_int8_convrot.safetensors"
ln -sfn \
  "$MODEL_ROOT/vae/qwen_image_2.1_vae_bf16.safetensors" \
  "$COMFY_MODELS/vae/qwen_image_2.1_vae_bf16.safetensors"
