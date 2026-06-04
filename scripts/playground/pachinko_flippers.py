#!/usr/bin/env python3
"""
Pipulate Context Engineering Component: Tactical Bumper Matrix
Path: pipulate/scripts/playground/pachinko_flippers.py

Assembles deterministic, in-band ASCII salt arrays to secure and anchor 
the spatial layout of prompt context matrices across headless execution loops.
Supports structural token-speedbump pipelines and high-fidelity clarified views.
"""
import os
import sys
import glob
import hashlib
import numpy as np
from PIL import Image

def compile_context_salt(image_path: str, character_width: int = 80, palette: str = 'pipe', contrast_adj: float = 0.0, brightness_adj: float = 0.0) -> str:
    """
    Transforms target image data into an untokenized, idempotent text bumper block.
    
    Args:
        image_path: Path to the source graphic asset.
        character_width: Grid width constraint for horizontal terminal boundaries.
        palette: 'pipe' for structural token speedbumps, 'clarified' for human visual fidelity.
        contrast_adj: Multiplier modifier added to base contrast factor.
        brightness_adj: Fractional offset shift scaled across available pixel range.
    """
    if not os.path.exists(image_path):
        return f"Warning: Bumper target reference not found at '{image_path}'"

    try:
        img = Image.open(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
    except Exception as e:
        return f"Warning: Bumper resource streaming halted: {e}"

    # Calculate absolute geometry metrics with font aspect correction ratio (0.5)
    orig_w, orig_h = img.size
    calculated_height = int(character_width * (orig_h / orig_w) * 0.5)

    # Downsample to raw pixel structure
    img_gray = img.convert('L').resize((character_width, calculated_height), Image.Resampling.LANCZOS)
    matrix = np.array(img_gray).astype(float)

    # Apply contrast and brightness adjustments dynamically
    if contrast_adj != 0.0 or brightness_adj != 0.0:
        factor = 1.0 + contrast_adj
        shift = brightness_adj * 255.0
        matrix = 128.0 + factor * (matrix - 128.0) + shift
        matrix = np.clip(matrix, 0, 255)

    matrix = matrix.astype(np.uint8)

    # Centralized Paintbox Ledger (Decoupled and audit-safe)
    palettes = {
        # Monospace meridian splitters maximizing vertical contiguity
        'pipe': '|||||||| ',  
        # Maximum typographic density distribution for visual synthesis
        'clarified': '$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,"^`\'. '
    }

    charset = palettes.get(palette.lower(), palettes['pipe'])
    charset_len = len(charset)

    # Build raw character string layout
    ascii_rows = []
    for i in range(calculated_height):
        row_chars = ""
        for j in range(character_width):
            pixel_val = matrix[i, j]
            char_idx = int(np.floor(pixel_val / 256 * charset_len))
            row_chars += charset[charset_len - 1 - char_idx]
        ascii_rows.append(row_chars)

    ascii_core_body = "\n".join(ascii_rows)

    # Generate an idempotent cryptographic verification signature from inner content only
    content_signature = hashlib.sha256(ascii_core_body.encode('utf-8')).hexdigest()[:8]
    node_identity = f"CONTEXT_SALT_NODE_{palette.upper()}__{content_signature}"

    # Format the outer structural alignment box container
    box_total_width = character_width + 2
    title_segment = f" {node_identity} "
    pad_left = (box_total_width - len(title_segment)) // 2
    pad_right = box_total_width - len(title_segment) - pad_left

    top_frame = f"╔{'═' * pad_left}{title_segment}{'═' * pad_right}╗"
    bottom_frame = f"╚{'═' * box_total_width}╝"

    compiled_payload = [top_frame]
    for row in ascii_rows:
        compiled_payload.append(f"║ {row} ║")
    compiled_payload.append(bottom_frame)

    return "\n".join(compiled_payload)

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
    # Check for execution membrane layer (Jupyter kernel vs CLI terminal boundary)
    is_kernel_membrane = any('ipykernel' in arg for arg in sys.argv) or any('-f' == arg for arg in sys.argv)

    if is_kernel_membrane:
        # Default fallback parameters inside interactive workspace
        source_directory = os.path.expanduser("~/flippers")
        target_width = 80
        active_palette = "pipe"
        contrast_val = 0.0
        brightness_val = 0.0
        
        # Scan directory dynamically for local image assets
        valid_extensions = ("*.jpg", "*.jpeg", "*.png", "*.webp")
        discovered_files = []
        for ext in valid_extensions:
            discovered_files.extend(glob.glob(os.path.join(source_directory, ext)))
            discovered_files.extend(glob.glob(os.path.join(source_directory, ext.upper())))
        
        if discovered_files:
            img_target = sorted(discovered_files)[0]
            print(f"👁️ Interactive workspace loop engaged. Siphoning asset: {img_target}\n")
        else:
            img_target = "assets/images/ai-seo-software.svg"
            print(f"⚠️ Directory empty or missing at '~/flippers'. Routing to repository fallback resource.\n")
    else:
        # Standard production execution route surface
        if len(sys.argv) < 2:
            print("Usage: python pachinko_flippers.py <path_to_image> [width] [palette] [contrast] [brightness]")
            sys.exit(1)
        img_target = sys.argv[1]
        target_width = int(sys.argv[2]) if len(sys.argv) > 2 else 80
        
        active_palette = 'pipe'
        contrast_val = 0.0
        brightness_val = 0.0
        contrast_seen = False
        
        for arg in sys.argv[3:]:
            clean_arg = arg.lstrip('+-')
            if clean_arg.isdigit():
                val = parse_adjustment(arg)
                if not contrast_seen:
                    contrast_val = val
                    contrast_seen = True
                else:
                    brightness_val = val
            else:
                active_palette = arg

    output_buffer = compile_context_salt(
        img_target, 
        character_width=target_width, 
        palette=active_palette, 
        contrast_adj=contrast_val, 
        brightness_adj=brightness_val
    )
    print(output_buffer)