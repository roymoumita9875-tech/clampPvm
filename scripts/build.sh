#!/usr/bin/env bash
# =============================================================================
# FILE PURPOSE:
# Automated build script that configures, applies ClampPVM patches, compiles,
# runs opcode cases regeneration, installs to /opt/clamp-pvm, and packages the SDK.
# Usage: bash scripts/build.sh [path/to/cpython-src]
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CPYTHON_SRC="${1:-/home/subha/pvm-clamp/cpython-src}"

if [ ! -d "$CPYTHON_SRC" ]; then
    echo "CPython source tree not found at $CPYTHON_SRC"
    echo "Cloning shallow CPython checkout..."
    mkdir -p "$(dirname "$CPYTHON_SRC")"
    git clone --depth 1 https://github.com/python/cpython.git "$CPYTHON_SRC"
fi

echo "=================================================================="
echo "  Building ClampPVM from source at: $CPYTHON_SRC"
echo "=================================================================="

# 1. Apply patches
echo "[1/5] Applying ClampPVM patches..."
python3 "${SCRIPT_DIR}/patch_cpython.py" "$CPYTHON_SRC"

# 2. Configure
echo "[2/5] Configuring CPython with prefix=/opt/clamp-pvm..."
cd "$CPYTHON_SRC"
./configure --prefix=/opt/clamp-pvm --disable-test-modules

# 3. Regenerate opcode cases
echo "[3/5] Regenerating bytecode interpreter cases..."
make regen-cases

# 4. Compile using all cores
CORES=$(nproc 2>/dev/null || echo 4)
echo "[4/5] Compiling with make -j${CORES}..."
make -j"${CORES}"

# 5. Install & Package
echo "[5/5] Installing and packaging SDK..."
sudo make altinstall
mkdir -p "${REPO_ROOT}/dist"
sudo tar -czf "${REPO_ROOT}/dist/clamp-pvm-sdk.tar.gz" -C /opt clamp-pvm

echo "Build complete! SDK packaged at ${REPO_ROOT}/dist/clamp-pvm-sdk.tar.gz"
