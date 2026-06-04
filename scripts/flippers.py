#!/usr/bin/env python3
"""
Pipulate Context Engineering Component: Tactical Bumper Matrix CLI Facade
Path: pipulate/scripts/playground/flippers.py

Provides unified command-line access to the underlying wand context salt compiler.
"""
import os
import sys
from pipulate import wand

def parse_adjustment(val_str: str) -> float:
    """Parses a signed integer string into a scaled float decimal adjustment."""
    sign = -1 if val_str.startswith('-') else 1
    clean = val_str.lstrip('+-')
    if not clean.isdigit():
        return 0.0
    if clean.startswith('0'):
        return sign * (int(clean) / 100.0)
    return sign * (int(clean) / 10.0)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python flippers.py <path_to_image> [width] [palette] [contrast] [brightness]")
        sys.exit(1)
    
    img_target = sys.argv[1]
    width = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    palette = sys.argv[3] if len(sys.argv) > 3 else 'pipe'
    c_adj = parse_adjustment(sys.argv[4]) if len(sys.argv) > 4 else None
    b_adj = parse_adjustment(sys.argv[5]) if len(sys.argv) > 5 else None

    output_buffer = wand.compile_context_salt(
        img_target, character_width=width, palette=palette, 
        contrast_adj=c_adj, brightness_adj=b_adj
    )
    print(output_buffer)
