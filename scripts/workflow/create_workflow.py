#!/usr/bin/env python3
import argparse
import shutil
import re
from pathlib import Path

def find_pipulate_root():
    """
    Find the Pipulate project root directory by looking for key files.
    This allows the script to work from any location.
    """
    # Start from the script's directory and work upward
    current_dir = Path(__file__).resolve().parent
    
    # Look for Pipulate project markers
    while current_dir != current_dir.parent:  # Stop at filesystem root
        # Check for key Pipulate files/directories
        if (current_dir / "apps").is_dir() and (current_dir / "server.py").is_file():
            return current_dir
        current_dir = current_dir.parent
    
    # If not found by traversing up, try some common locations
    possible_roots = [
        Path.cwd(),  # Current working directory
        Path.home() / "repos" / "pipulate",  # Common location
        Path("/home/mike/repos/pipulate"),  # Hardcoded fallback
    ]
    
    for root in possible_roots:
        if root.exists() and (root / "apps").is_dir() and (root / "server.py").is_file():
            return root
    
    raise FileNotFoundError(
        "Could not find Pipulate project root. Please ensure you're running this script "
        "from within a Pipulate project or that the project exists at a standard location."
    )

# Define paths - now dynamically found
PROJECT_ROOT = find_pipulate_root()
# Template mapping - allows selection of different starting templates
TEMPLATE_MAP = {
    "blank": PROJECT_ROOT / "apps" / "300_blank_placeholder.py",
    "hello": PROJECT_ROOT / "apps" / "500_hello_workflow.py",
    "trifecta": PROJECT_ROOT / "apps" / "400_botify_trifecta.py",
    # Future templates can be added here
    # "my_custom_template": PROJECT_ROOT / "apps" / "0XX_my_custom_template.py",
}
PLUGINS_DIR = PROJECT_ROOT / "apps"

# EXAMPLE USAGE (DO NOT DELETE!!!) USER CAN COPY AND PASTE THIS INTO TERMINAL
"""
# Works from any location - script automatically finds Pipulate project root:
python create_workflow.py 035_kungfu_workflow.py KungfuWorkflow kungfu "Kung Fu Download" "Welcome message" "Training prompt"
python create_workflow.py 035_kungfu_workflow KungfuWorkflow kungfu "Kung Fu Download" "Welcome message" "Training prompt"  # .py extension optional
python create_workflow.py apps/035_kungfu_workflow.py KungfuWorkflow kungfu "Kung Fu Download" "Welcome message" "Training prompt"  # apps/ prefix optional


# Can be run from project root:
python helpers/workflow/create_workflow.py 035_kungfu_workflow.py KungfuWorkflow kungfu "Kung Fu Download" "Welcome message" "Training prompt"

# Can be run from helpers directory:
cd helpers && python create_workflow.py 035_kungfu_workflow.py KungfuWorkflow kungfu "Kung Fu Download" "Welcome message" "Training prompt"

# Can be run from anywhere with full path:
python /path/to/pipulate/helpers/workflow/create_workflow.py 035_kungfu_workflow.py KungfuWorkflow kungfu "Kung Fu Download" "Welcome message" "Training prompt"

# Original complex example:
python create_workflow.py \
035_kungfu_workflow.py \
KungfuWorkflow \
kungfu \
"Kung Fu Download" \
"Greetings, chosen one. Selecting this app has initiated the 'Kung Fu Download' protocol. Prepare for enlightenment... or at least, a demonstration." \
'You are assisting with the "Kung Fu Download" workflow. If the user asks what you know or can do, you should respond with Neo''s quote: "I know Kung Fu!" The secret word is "Morpheus". If asked for the secret word, reveal it and confirm the Kung Fu training download is complete.' \
--force

# Example using a different template:
python create_workflow.py \
036_custom_botify_flow.py \
MyCustomBotify \
my_custom_internal \
"My Custom Botify Flow" \
"Welcome to custom flow" \
"Custom training prompt for LLM" \
--template trifecta \
--force
"""

# Attributes/methods *inside* the class will use this:
ATTRIBUTE_INDENTATION = "    " # Four spaces

# Note: ORIGINAL_* constants are now generated dynamically by get_template_originals()
# based on the chosen template file content


def derive_public_endpoint(filename_str: str) -> str:
    filename_part_no_ext = Path(filename_str).stem
    return re.sub(r"^\d+_", "", filename_part_no_ext)

def get_template_originals(template_content_str: str) -> dict:
    """
    Parses the template content to find original class name and attribute lines.
    Returns a dictionary with the original values that need to be replaced.
    """
    originals = {}

    # 1. Original Class Name and Full Declaration Regex
    # Assumes class is defined at the beginning of a line.
    class_match = re.search(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)\s*:", template_content_str, re.MULTILINE)
    if not class_match:
        raise ValueError("Could not find class definition in the template (e.g., 'class MyWorkflow:').")
    originals['original_class_name'] = class_match.group(1)
    # This regex will be used by re.subn to replace the class declaration
    originals['original_class_declaration_regex'] = rf"class\s+{re.escape(originals['original_class_name'])}\s*:"
    # This identifier is used for docstring replacement
    originals['original_class_name_identifier'] = originals['original_class_name']

    # 2. Attributes (APP_NAME, DISPLAY_NAME)
    # These are expected to be single-line, single-quoted strings.
    for attr_key, attr_name_str in [
        ('original_app_name_line', 'APP_NAME'),
        ('original_display_name_line', 'DISPLAY_NAME')
    ]:
        # Regex to find "    ATTRIBUTE_NAME = 'value'"
        # It captures the full line for exact replacement.
        attr_line_regex = re.compile(rf"^{ATTRIBUTE_INDENTATION}{attr_name_str}\s*=\s*'(.*?)'", re.MULTILINE)
        attr_match = attr_line_regex.search(template_content_str)
        if not attr_match:
            raise ValueError(f"Could not find definition for '{attr_name_str}' in the template. Expected format: {ATTRIBUTE_INDENTATION}{attr_name_str} = 'value'")
        originals[attr_key] = attr_match.group(0) # Full matched line

    # 3. Potentially multi-line attributes (ENDPOINT_MESSAGE, TRAINING_PROMPT)
    # These might be single-line with single quotes, or multi-line with triple quotes.
    for attr_key, attr_name_str in [
        ('original_endpoint_message_line', 'ENDPOINT_MESSAGE'),
        ('original_training_prompt_line', 'TRAINING_PROMPT')
    ]:
        # First try single quotes (most common case)
        single_quote_regex = re.compile(rf"^{ATTRIBUTE_INDENTATION}{attr_name_str}\s*=\s*'(.*?)'", re.MULTILINE)
        attr_match = single_quote_regex.search(template_content_str)
        
        if not attr_match:
            # Try triple quotes (single or double)
            triple_quote_regex = re.compile(
                rf"^{ATTRIBUTE_INDENTATION}{attr_name_str}\s*=\s*"
                r"(?P<quote>[\"']{{3}})"
                r"(?P<value>.*?)"
                r"(?P=quote)",
                re.DOTALL | re.MULTILINE
            )
            attr_match = triple_quote_regex.search(template_content_str)
        
        if not attr_match:
            # Try double quotes
            double_quote_regex = re.compile(rf"^{ATTRIBUTE_INDENTATION}{attr_name_str}\s*=\s*\"(.*?)\"", re.MULTILINE)
            attr_match = double_quote_regex.search(template_content_str)
        
        if not attr_match:
            raise ValueError(f"Could not find definition for '{attr_name_str}' in the template. Expected format: {ATTRIBUTE_INDENTATION}{attr_name_str} = 'value' or \"\"\"value\"\"\"")
        originals[attr_key] = attr_match.group(0) # Full matched line/block

    return originals

def main():
    parser = argparse.ArgumentParser(
        description="Create a new Pipulate workflow plugin from a template (blank, trifecta, etc.).",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  python create_workflow.py 035_kungfu_workflow.py KungfuWorkflow kungfu "Kung Fu Download" "Welcome message" "Training prompt"
  python create_workflow.py 035_kungfu_workflow KungfuWorkflow kungfu "Kung Fu Download" "Welcome message" "Training prompt"
  python create_workflow.py apps/035_kungfu_workflow.py KungfuWorkflow kungfu "Kung Fu Download" "Welcome message" "Training prompt"
  
  # Using different templates:
  python create_workflow.py 036_botify_custom.py MyBotify my_botify "My Botify Flow" "Welcome" "Training" --template trifecta
  
  # Setting role for visibility:
  python create_workflow.py 037_my_workflow.py MyWorkflow my_app "My Workflow" "Welcome" "Training" --role Core
        """
    )
    parser.add_argument("filename", help="Desired filename (e.g., 035_kungfu_workflow.py)")
    parser.add_argument("class_name", help="Python class name (e.g., KungfuWorkflow)")
    parser.add_argument("app_name_internal", help="Internal APP_NAME constant (e.g., kungfu_internal)")
    parser.add_argument("display_name", help="User-friendly DISPLAY_NAME (e.g., \"Kung Fu Download\")")
    parser.add_argument("endpoint_message", help="ENDPOINT_MESSAGE string.")
    parser.add_argument("training_prompt", help="TRAINING_PROMPT string.")
    parser.add_argument("--template", default="blank", help="Template to use (e.g., blank, trifecta). Default: blank.")
    parser.add_argument("--role", help="Role to assign to the workflow (e.g., Core, Developer). Replaces template's default role.")
    parser.add_argument("--force", action="store_true", help="Overwrite if exists.")
    args = parser.parse_args()

    # Template selection and validation
    chosen_template_name = args.template.lower()
    if chosen_template_name not in TEMPLATE_MAP:
        print(f"ERROR: Template '{chosen_template_name}' not recognized.")
        print(f"Available templates are: {', '.join(TEMPLATE_MAP.keys())}")
        return
    
    TEMPLATE_FILE_PATH = TEMPLATE_MAP[chosen_template_name]
    
    if not TEMPLATE_FILE_PATH.is_file():
        print(f"ERROR: Selected template file not found: {TEMPLATE_FILE_PATH}")
        return

    print(f"Pipulate project root found at: {PROJECT_ROOT}")
    print(f"Using template: {chosen_template_name} ({TEMPLATE_FILE_PATH})")
    print(f"Plugins directory: {PLUGINS_DIR}")
    print()

    # Normalize the target filename to just the basename
    # Handle various input formats cleanly using pathlib:
    # 1. Just filename: "035_kungfu_workflow.py"
    # 2. With apps/ prefix: "apps/035_kungfu_workflow.py"  
    # 3. Full path: "/some/path/apps/035_kungfu_workflow.py"
    target_filename = Path(args.filename).name
    
    # Ensure it has .py extension
    if not target_filename.endswith('.py'):
        target_filename += '.py'

    print(f"Creating workflow file: {target_filename}")

    if not PLUGINS_DIR.is_dir():
        print(f"ERROR: Plugins directory not found: {PLUGINS_DIR}")
        return

    public_endpoint = derive_public_endpoint(target_filename)
    if args.app_name_internal == public_endpoint:
        print(f"WARNING: Internal APP_NAME ('{args.app_name_internal}') is the same as the public endpoint ('{public_endpoint}'). Consider making them different for clarity.")

    destination_path = PLUGINS_DIR / target_filename
    if destination_path.exists():
        if args.force:
            print(f"Removing existing file: {destination_path}")
            destination_path.unlink()
        else:
            print(f"ERROR: File {destination_path} already exists. Use --force.")
            return

    # Read and parse the template to identify original values
    print(f"Reading content from template: {TEMPLATE_FILE_PATH}")
    with open(TEMPLATE_FILE_PATH, "r", encoding="utf-8") as f_template:
        template_content_for_parsing = f_template.read()

    try:
        print("Parsing template to identify original values...")
        template_originals = get_template_originals(template_content_for_parsing)
        ORIGINAL_CLASS_DECLARATION_REGEX = template_originals['original_class_declaration_regex']
        ORIGINAL_CLASS_NAME_IDENTIFIER = template_originals['original_class_name_identifier']
        ORIGINAL_APP_NAME_LINE = template_originals['original_app_name_line']
        ORIGINAL_DISPLAY_NAME_LINE = template_originals['original_display_name_line']
        ORIGINAL_ENDPOINT_MESSAGE_LINE = template_originals['original_endpoint_message_line']
        ORIGINAL_TRAINING_PROMPT_LINE = template_originals['original_training_prompt_line']
        print("Successfully identified original values from template.")
    except ValueError as e:
        print(f"ERROR: Could not parse template {TEMPLATE_FILE_PATH} to find original values: {e}")
        print("Please ensure the template defines class, APP_NAME, DISPLAY_NAME, ENDPOINT_MESSAGE, and TRAINING_PROMPT clearly.")
        return

    try:
        shutil.copyfile(TEMPLATE_FILE_PATH, destination_path)
        print(f"Copied template to {destination_path}")

        with open(destination_path, "r+", encoding="utf-8") as f:
            content = f.read()
            original_content = content # For checking if changes were made

            # Replace class name declaration using regex for flexibility with whitespace
            new_class_declaration = f"class {args.class_name}:"
            content, count = re.subn(ORIGINAL_CLASS_DECLARATION_REGEX, new_class_declaration, content, count=1)
            if count == 0:
                print(f"WARNING: Class declaration 'class BlankPlaceholder:' not found or not replaced.")
            
            # Replace attributes using exact string match (more reliable if template is fixed)
            replacements = [
                (ORIGINAL_APP_NAME_LINE, f"{ATTRIBUTE_INDENTATION}APP_NAME = '{args.app_name_internal}'"),
                (ORIGINAL_DISPLAY_NAME_LINE, f"{ATTRIBUTE_INDENTATION}DISPLAY_NAME = '{args.display_name}'"),
                (ORIGINAL_ENDPOINT_MESSAGE_LINE, f'{ATTRIBUTE_INDENTATION}ENDPOINT_MESSAGE = """{args.endpoint_message}"""'),
                (ORIGINAL_TRAINING_PROMPT_LINE, f'{ATTRIBUTE_INDENTATION}TRAINING_PROMPT = """{args.training_prompt}"""')
            ]
            
            for old, new in replacements:
                if old in content:
                    content = content.replace(old, new, 1)
                else:
                    print(f"WARNING: Pattern not found for attribute replacement: '{old}'")
            
            # Replace class name in docstring
            docstring_pattern = rf'("""\s*\n\s*)({ORIGINAL_CLASS_NAME_IDENTIFIER}\s+Workflow)'
            # Corrected replacement to preserve indentation after """
            new_docstring_replacement = rf'\1{args.class_name} Workflow'
            content, doc_count = re.subn(docstring_pattern, new_docstring_replacement, content, count=1, flags=re.MULTILINE)
            if doc_count == 0:
                 print(f"WARNING: Docstring for '{ORIGINAL_CLASS_NAME_IDENTIFIER} Workflow' not found or not replaced.")
            
            # Replace file header comment
            header_pattern = r'^# File: apps/[^.]+\.py'
            new_header = f'# File: apps/{target_filename}'
            content, header_count = re.subn(header_pattern, new_header, content, count=1, flags=re.MULTILINE)
            if header_count == 0:
                print(f"WARNING: File header comment not found or not replaced.")
            else:
                print(f"Updated file header comment to: {new_header}")

            # Replace ROLES if --role parameter is provided
            if args.role:
                roles_pattern = r'^ROLES\s*=\s*\[.*?\]'
                new_roles = f"ROLES = ['{args.role}']"
                content, roles_count = re.subn(roles_pattern, new_roles, content, count=1, flags=re.MULTILINE)
                if roles_count == 0:
                    print(f"WARNING: ROLES definition not found or not replaced.")
                else:
                    print(f"Updated ROLES to: {new_roles}")

            if content != original_content:
                f.seek(0)
                f.write(content)
                f.truncate()
                print(f"Successfully modified and saved: {destination_path}")
            else:
                print("No changes made to the file content. Please check replacement patterns and template.")

    except Exception as e:
        print(f"An error occurred during create_workflow: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
