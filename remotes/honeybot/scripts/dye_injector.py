import sys
import re
from pathlib import Path

def inject_dye(file_path, dye_string):
    path = Path(file_path)
    if not path.exists():
        print(f"Error: {file_path} not found.")
        return
    
    content = path.read_text()
    # Flexible anchor search
    anchor_pattern = re.compile(r'[#]+\s*Technical Journal Entry Begins')
    
    match = anchor_pattern.search(content)
    
    if match:
        # Inject immediately after the anchor line
        end_pos = match.end()
        new_content = content[:end_pos] + "\n\n" + dye_string + "\n" + content[end_pos:]
        print(f"Success: Injected after anchor in {path.name}")
    else:
        # Fallback: Absolute bottom
        new_content = content.strip() + "\n\n-- --\n" + dye_string + "\n"
        print(f"Warning: Anchor not found. Injected at bottom of {path.name}")
        
    path.write_text(new_content)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 dye_injector.py <file_path> <dye_string>")
        sys.exit(1)
    inject_dye(sys.argv[1], sys.argv[2])