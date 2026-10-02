#!/usr/bin/env python3
"""
🚀 AKVO AWG — System Entrypoint Runner

This file acts as the top-level execution wrapper for the AKVO AWG 
Sensor Monitoring & Automation package.

To run the system:
    sudo python3 main.py
"""
import sys
from akvo_awg.main import main

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Critical system failure: {e}", file=sys.stderr)
        sys.exit(1)
