#!/bin/bash
# Quick health check wrapper for Glitch in Matrix
# Usage: ./healthcheck.sh

cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"
"/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/.venv/bin/python" system_health_check.py
