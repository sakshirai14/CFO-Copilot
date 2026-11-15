#!/usr/bin/env bash
# scripts/download_models.sh
# Deterministic downloader for CFO Copilot local small open-weight LLMs.
# Pinning URLs and SHA-256 hashes ensures bit-for-bit reproducibility.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MODELS_DIR="${PROJECT_ROOT}/models"

mkdir -p "${MODELS_DIR}"

# 1. Candidate 1: Qwen2.5-3B-Instruct (GGUF, Q4_K_M)
QWEN_URL="https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
QWEN_FILE="${MODELS_DIR}/qwen2.5-3b-instruct-q4_k_m.gguf"
QWEN_SHA256="626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d"

# 2. Candidate 2: Llama-3.2-3B-Instruct (GGUF, Q4_K_M)
LLAMA_URL="https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
LLAMA_FILE="${MODELS_DIR}/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
LLAMA_SHA256="6c1a2b41161032677be168d354123594c0e6e67d2b9227c84f296ad037c728ff"

verify_hash() {
    local file="$1"
    local expected_hash="$2"
    if [ ! -f "$file" ]; then
        return 1
    fi
    local actual_hash
    actual_hash="$(shasum -a 256 "$file" | awk '{print $1}')"
    if [ "$actual_hash" = "$expected_hash" ]; then
        return 0
    else
        echo "[WARN] Hash mismatch for $file! Expected: $expected_hash, Got: $actual_hash"
        return 1
    fi
}

download_model() {
    local name="$1"
    local url="$2"
    local file="$3"
    local expected_hash="$4"

    echo "================================================================================"
    echo "Processing model: ${name}"
    echo "Destination:     ${file}"
    echo "Pinned SHA-256:  ${expected_hash}"

    if verify_hash "$file" "$expected_hash"; then
        echo "[OK] Model ${name} already downloaded and verified. Skipping download."
        return 0
    fi

    echo "[INFO] Downloading ${name} from ${url}..."
    local tmp_file="${file}.tmp"
    curl -L --progress-bar -f -o "$tmp_file" "$url"

    echo "[INFO] Verifying SHA-256 checksum..."
    local actual_hash
    actual_hash="$(shasum -a 256 "$tmp_file" | awk '{print $1}')"
    if [ "$actual_hash" != "$expected_hash" ]; then
        echo "[ERROR] SHA-256 mismatch for ${name}!"
        echo "Expected: ${expected_hash}"
        echo "Actual:   ${actual_hash}"
        rm -f "$tmp_file"
        exit 1
    fi

    mv "$tmp_file" "$file"
    echo "[SUCCESS] Downloaded and verified ${name} successfully."
}

# Download Primary Candidate (Qwen2.5-3B-Instruct)
download_model "Qwen2.5-3B-Instruct (Q4_K_M)" "$QWEN_URL" "$QWEN_FILE" "$QWEN_SHA256"

# Download Second Candidate (Llama-3.2-3B-Instruct)
download_model "Llama-3.2-3B-Instruct (Q4_K_M)" "$LLAMA_URL" "$LLAMA_FILE" "$LLAMA_SHA256"

echo "================================================================================"
echo "[COMPLETE] All models downloaded and SHA-256 verified in ${MODELS_DIR}"
