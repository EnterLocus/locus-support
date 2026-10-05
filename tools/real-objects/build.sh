#!/bin/bash
# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
# Compile the Swift tools into .build/ (not committed).
# Usage: ./build.sh [inspect_usdz|reconstruct]...   (default: both)
# ROS_BIN_DIR overrides the output directory.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="${ROS_BIN_DIR:-$here/.build}"
mkdir -p "$out"
tools=("$@")
[ ${#tools[@]} -gt 0 ] || tools=(inspect_usdz reconstruct)
for tool in "${tools[@]}"; do
  echo "building $tool -> $out/$tool" >&2
  xcrun swiftc -O "$here/swift/$tool.swift" -o "$out/$tool"
done
