#!/usr/bin/env python3
"""
Pachinko Bumper Dial Spinner
Performs a brute-force sweep across contrast/brightness ranges to find 
optimal feature isolation for the ASCII salt matrix.
"""
import sys
import numpy as np
from pachinko_flippers import compile_context_salt

def spin_dials(image_path, width=80, c_range=(-5, 5), b_range=(-5, 5), step=2):
    # Convert ranges to step-based lists
    c_steps = np.arange(c_range[0], c_range[1] + 1, step)
    b_steps = np.arange(b_range[0], b_range[1] + 1, step)

    print(f"🌀 Initiating Bumper Dial Sweep: {len(c_steps) * len(b_steps)} variations...")
    
    for c in c_steps:
        for b in b_steps:
            # Normalize to 0.1 decimal steps
            c_float = float(c) / 10.0
            b_float = float(b) / 10.0
            
            print(f"\n--- SETTINGS: Contrast={c_float:+0.2f} | Brightness={b_float:+0.2f} ---")
            bumper = compile_context_salt(
                image_path, 
                character_width=width, 
                palette='pipe', 
                contrast_adj=c_float, 
                brightness_adj=b_float
            )
            print(bumper)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python dial_spinner.py <path_to_image> [width]")
        sys.exit(1)
        
    img_target = sys.argv[1]
    width = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    
    # Defaults: Sweep -0.5 to +0.5 in 0.2 increments
    spin_dials(img_target, width=width)