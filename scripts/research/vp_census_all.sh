#!/bin/sh
# vp_census_all.sh: pass T then S1..S3 of vp_recording_census over the five leaf recordings (every tree edge is covered).
cd "$(dirname "$0")/../.."
PY=./.venv/Scripts/python.exe
OUT=artifacts/gods/research
for node in ca2b703b6fd5 fb408bc75597 7251bbd0ecf7 f0ac19738f19 f40d7bcc9dda; do
  $PY scripts/research/vp_recording_census.py --node $node --out $OUT/census-T-$node.json || echo "FAILED T $node"
done
for k in 1 2 3; do
  for node in ca2b703b6fd5 fb408bc75597 7251bbd0ecf7 f0ac19738f19 f40d7bcc9dda; do
    $PY scripts/research/vp_recording_census.py --node $node --sound-sites $k --out $OUT/census-S$k-$node.json || echo "FAILED S$k $node"
  done
done
echo ALL-DONE
