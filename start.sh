#!/bin/bash
# Keeps the Mac awake (on power, lid open) and runs the watcher for 72h.
cd "$(dirname "$0")"
exec caffeinate -is python3 watcher.py
