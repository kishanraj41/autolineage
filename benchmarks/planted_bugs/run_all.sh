#!/usr/bin/env bash
# Reproduce the extended planted-bug evaluation (5 bug categories).
# Requires: pip install "autolineage[sklearn]" scikit-learn pandas numpy
set -e
for c in filter join encoding leakage type; do
  echo "=== $c ==="
  python3 pipeline.py "$c" baseline   # saves fp_$c.json fingerprint of the healthy run
  python3 pipeline.py "$c" buggy      # loads baseline, detects + localizes on the buggy run
done
