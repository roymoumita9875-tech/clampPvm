#!/usr/bin/env bash
# =============================================================================
# FILE PURPOSE:
# Installs the packaged ClampPVM SDK into /opt/clamp-pvm on Linux / WSL2 systems
# and creates a global symlink at /usr/local/bin/clamp-python.
# Usage: sudo bash scripts/install.sh [path/to/clamp-pvm-sdk.tar.gz]
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Check user-provided tarball or default to dist/
TARBALL="${1:-${REPO_ROOT}/dist/clamp-pvm-sdk.tar.gz}"

if [ ! -f "$TARBALL" ]; then
    # Fallback check in pvm-clamp home dir
    if [ -f "/home/subha/pvm-clamp/clamp-pvm-sdk.tar.gz" ]; then
        TARBALL="/home/subha/pvm-clamp/clamp-pvm-sdk.tar.gz"
    else
        echo "Error: ClampPVM SDK archive not found at: $TARBALL"
        echo "Please generate the archive first using scripts/build.sh"
        exit 1
    fi
fi

echo "=================================================================="
echo "  Installing ClampPVM SDK from: $TARBALL"
echo "=================================================================="

sudo mkdir -p /opt
sudo tar -xzf "$TARBALL" -C /opt
sudo chmod -R a+rX /opt/clamp-pvm

# Ensure /opt/clamp-pvm/bin/python3 exists
if [ -f /opt/clamp-pvm/bin/python3.16 ] && [ ! -f /opt/clamp-pvm/bin/python3 ]; then
    sudo ln -sf /opt/clamp-pvm/bin/python3.16 /opt/clamp-pvm/bin/python3
fi

echo "Creating symlink /usr/local/bin/clamp-python -> /opt/clamp-pvm/bin/python3.16..."
sudo mkdir -p /usr/local/bin
sudo ln -sf /opt/clamp-pvm/bin/python3.16 /usr/local/bin/clamp-python

echo ""
echo "=== Verification ==="
/usr/local/bin/clamp-python --version
/usr/local/bin/clamp-python -c "import sys; print('Native ClampPVM Active:', hasattr(sys, 'set_clamp_mode'))"
echo ""
echo "ClampPVM SDK installed successfully! Ready to use via 'clamp-python'."
