# HARDWARE.md: Environment Detection & Serving Strategy Decision

> **Platform**: CFO Copilot on a Budget  
> **Date**: 2026-11-14  
> **Target Requirement**: 6 GB VRAM GPU, 16 concurrent chat sessions, TTFT < 2.0 s (with stated CPU-only fallback)

---

## 1. Raw Environment & System Probe Output

The following raw commands were executed inside the local project environment:

```text
=== OS & Kernel ===
Darwin Sakshis-MacBook-Air.local 25.6.0 Darwin Kernel Version 25.6.0: Fri Jul 31 19:11:03 PDT 2026; root:xnu-12377.161.14~5/RELEASE_ARM64_T8132 arm64
ProductName:		macOS
ProductVersion:		26.6.2
BuildVersion:		25G83

=== CPU & Cores ===
Apple M4
Logical CPU cores: 10
Physical CPU cores: 10

=== Memory & Disk ===
RAM: 16.00 GB (17,179,869,184 bytes unified memory)
Filesystem      Size    Used   Avail Capacity iused ifree %iused  Mounted on
/dev/disk3s5   228Gi   162Gi    45Gi    79%    1.6M  469M    0%   /System/Volumes/Data

=== GPU & Acceleration ===
nvidia-smi not found
nvidia-smi: not found (no NVIDIA GPU)
Type: Integrated Apple Silicon GPU (Apple M4 unified architecture)

=== Toolchains & Containers ===
Python 3.11.0 (default system binary at /Library/Frameworks/Python.framework/Versions/3.11/bin/python3)
git version 2.50.1 (Apple Git-155)
Docker version 29.9.2, build a82e528
Docker Compose version v5.6.1
podman: not found

=== LLM Serving Engines ===
llama-server: not found in PATH
ollama: not found in PATH
vllm: not installed (ModuleNotFoundError: No module named 'vllm')
```

---

## 2. Hardware Path Decision: GPU vs. CPU-Only Fallback

### The Reality of This Environment
1. **No NVIDIA GPU**: The host is an Apple Silicon MacBook Air with an **Apple M4 chip (10 cores, 16 GB unified RAM)**. There is no NVIDIA GPU, no CUDA driver, and no discrete VRAM (`nvidia-smi` is not present).
2. **macOS Docker Virtualization Boundary**: Docker Desktop on macOS runs within a lightweight Linux VM. The hypervisor layer **does not expose Apple Metal GPU acceleration** to Linux containers. Any containerized serving engine running via `docker-compose` on macOS will strictly execute on the **CPU**.
3. **Assignment Specification**: The assignment states:
   > *"Target: one 6 GB VRAM GPU (a CPU-only fallback is allowed but I must state real numbers), 16 concurrent chat sessions, time-to-first-token under 2 s... If CPU-only, say so plainly; I need to report CPU numbers."*

### Serving Path Architecture & Decision
We select a **Dual-Path Strategy**:

1. **Official Benchmark & Deliverable Path: CPU-Only Fallback (Containerized & Headless)**:
   - For all reproducible benchmarks, self-checks, and Docker container evaluations, we run in **CPU-only mode**.
   - We plainly state and report real CPU throughput (tokens/s), CPU TTFT (ms), and CPU memory footprint.
   - We do not simulate or fabricate NVIDIA GPU numbers.
2. **Local Interactive & Development Path: Native `llama.cpp` with Metal**:
   - For interactive CFO chat and live demos on this Mac, native `llama-server` compiled with Apple Metal can leverage the M4 GPU cores and unified memory.
   - This delivers fast local response times without altering the underlying prefix-caching or API contracts.
3. **One-Command Setup Contract (`docker-compose.yml`)**:
   - The one-command setup runs via Docker Compose on CPU.
   - We configure CPU thread allocation (`-t 8`) and prefix caching (`--cache-type-k q4_0 --cache-type-v q4_0` or `fp16`) to maximize CPU throughput.

---

## 3. Google ADK Version & Local Model Integration Contract

### Stable Package Version
- **Command Run**: `python3 -m pip index versions google-adk`
- **Latest Stable PyPI Release**: **`google-adk 2.14.1`** (released 2026).
- **Recorded in DECISIONS.md**: Version `2.14.1` is pinned for all agent orchestration.

### How Google ADK Connects to a Local OpenAI-Compatible Server
Google ADK natively provides a model abstraction layer through **LiteLLM**. ADK agents connect to self-hosted LLMs (e.g. `llama.cpp` server, `vLLM`, `Ollama`) without modifying agent logic.

- **Exact Import Path**:
  ```python
  from google.adk.agents import LlmAgent
  from google.adk.models.lite_llm import LiteLlm
  ```
- **Model String Format**:
  `openai/<model-name>`
  Example: `openai/qwen2.5-3b-instruct` or `openai/llama-3.2-3b-instruct`
- **Endpoint Configuration**:
  ADK/LiteLLM routes requests to the local engine using standard environment variables or explicit client instantiation:
  ```python
  import os
  from google.adk.models.lite_llm import LiteLlm

  os.environ["OPENAI_BASE_URL"] = "http://localhost:8080/v1"
  os.environ["OPENAI_API_KEY"] = "not-needed-for-local"

  local_model = LiteLlm(
      model="openai/qwen2.5-3b-instruct",
      api_base="http://localhost:8080/v1",
      api_key="not-needed-for-local"
  )
  ```
- **Zero Hosted APIs Rule**: No requests leave the machine. All inference calls route to `127.0.0.1:8080`.
