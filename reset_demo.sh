#!/bin/bash
echo "Resetting demo state..."
rm -f data/incidents.db
rm -rf data/snapshots/*
rm -f data/isolation_forest.pkl
influx bucket delete -n telemetry -o healing-system --force 2>/dev/null
influx bucket create -n telemetry -o healing-system 2>/dev/null
echo "Done. Cold-start warm-up required — run the pipeline for a few minutes before presenting."