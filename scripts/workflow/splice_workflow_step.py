#!/usr/bin/env python3
import argparse
import re
from pathlib import Path
import os

# EXAMPLE USAGE (DO NOT DELETE!!!) USER CAN COPY AND PASTE THIS INTO TERMINAL
"""
# Works from any location - script automatically finds Pipulate project root:

# Insert at bottom (default - before finalize step):
python splice_workflow_step.py 035_kungfu_workflow.py
python splice_workflow_step.py 035_kungfu_workflow.py --position bottom

# Insert at top (becomes the new first data step):
python splice_workflow_step.py 035_kungfu_workflow.py --position top

# Flexible filename handling:
python splice_workflow_step.py 035_kungfu_workflow    # .py extension optional
python splice_workflow_step.py apps/035_kungfu_workflow.py  # apps/ prefix optional

# Can be run from project root:
# python scripts/workflow/splice_workflow_step.py 035_kungfu_workflow.py --position top

# Can be run from scripts directory:
# cd scripts && python workflow/splice_workflow_step.py 035_kungfu_workflow.py --position bottom

# Can be run from anywhere with full path:
# python /path/to/pipulate/scripts/workflow/splice_workflow_step.py 035_kungfu_workflow.py --position top
"""

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
TEMPLATE_FILE_PATH = PROJECT_ROOT / "apps" / "300_blank_placeholder.py"
PLUGINS_DIR = PROJECT_ROOT / "apps"

# Markers to find insertion points
STEPS_LIST_MARKER = "# --- STEPS_LIST_INSERTION_POINT ---"
STEP_METHODS_MARKER = "# --- STEP_METHODS_INSERTION_POINT ---"

def find_steps_list_definition(content):
    """
    Find the steps list definition in the content, handling both direct and indirect assignment patterns.
    
    Returns a tuple of (steps_list_prefix, steps_list_content, steps_list_suffix, original_full_block)
    or (None, None, None, None) if not found.
    """
    
    # Pattern 1: Direct assignment `self.steps = [...]`
    direct_assignment_regex = re.compile(
        r"(\bself\.steps\s*=\s*\[)"  # Group 1: "self.steps = [" (with word boundary)
        r"(.*?)"                     # Group 2: The content of the list (non-greedy)
        r"(\])",                     # Group 3: The closing "]"
        re.DOTALL | re.MULTILINE
    )
    direct_match = direct_assignment_regex.search(content)
    
    if direct_match:
        print("Found direct 'self.steps = [...]' assignment.")
        return (
            direct_match.group(1),  # prefix
            direct_match.group(2),  # content
            direct_match.group(3),  # suffix
            direct_match.group(0)   # full block
        )
    
    print("Direct 'self.steps = [...]' not found. Trying indirect 'self.steps = var_name' then 'var_name = [...]'.")
    
    # Pattern 2: Indirect assignment `self.steps = variable_name`
    indirect_assignment_regex = re.compile(
        r"^\s*self\.steps\s*=\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:[;#]|$)",  # Capture variable name
        re.MULTILINE
    )
    indirect_match = indirect_assignment_regex.search(content)
    
    if indirect_match:
        variable_name = indirect_match.group(1)
        print(f"Found indirect 'self.steps = {variable_name}'. Now searching for '{variable_name} = [...]'.")
        
        # Pattern 2b: Find the definition of `variable_name = [...]`
        variable_definition_regex = re.compile(
            rf"(^\s*{re.escape(variable_name)}\s*=\s*\[)"  # Group 1: "variable_name = [" (possibly indented)
            r"(.*?)"                                      # Group 2: Content of the list
            r"(\])",                                      # Group 3: Closing "]"
            re.DOTALL | re.MULTILINE
        )
        var_def_match = variable_definition_regex.search(content)
        
        if var_def_match:
            print(f"Found definition block for '{variable_name}'.")
            return (
                var_def_match.group(1),  # prefix
                var_def_match.group(2),  # content
                var_def_match.group(3),  # suffix
                var_def_match.group(0)   # full block
            )
        else:
            print(f"ERROR: Found 'self.steps = {variable_name}' but could not find the list definition for '{variable_name} = [...]'.")
            print("Ensure the variable is assigned a list literal directly like 'variable_name = [Step(...)]'.")
            return (None, None, None, None)
    else:
        print(f"ERROR: Could not find 'self.steps = [...]' or 'self.steps = variable_name' pattern.")
        print("The script expects 'self.steps' to be initialized either with a direct list or via an intermediate variable that is itself a list literal.")
        return (None, None, None, None)

def insert_step_in_list_content(steps_list_content, new_step_definition, position, steps_list_marker):
    """
    Insert a new step definition into the steps list content based on position.
    
    Args:
        steps_list_content: The content between [ and ] of the steps list
        new_step_definition: The new Step(...) definition to insert
        position: "top" or "bottom"
        steps_list_marker: The marker to look for in bottom position
    
    Returns:
        The modified steps list content
    """
    current_step_lines = steps_list_content.splitlines()
    processed_lines = []
    
    if position == "top":
        # Find the first actual Step definition
        first_actual_step_line_index = -1
        for i, line in enumerate(current_step_lines):
            if line.lstrip().startswith("Step("):
                first_actual_step_line_index = i
                break
        
        if first_actual_step_line_index != -1:
            # Insert before the first existing Step definition
            processed_lines.extend(current_step_lines[:first_actual_step_line_index])
            processed_lines.extend(new_step_definition.splitlines())
            processed_lines.extend(current_step_lines[first_actual_step_line_index:])
        else:
            # No existing Step definitions, new step is the first
            processed_lines.extend(new_step_definition.splitlines())
            processed_lines.extend(current_step_lines)
    
    elif position == "bottom":
        # Look for the marker first
        marker_index = -1
        for i, line in enumerate(current_step_lines):
            if steps_list_marker in line:
                marker_index = i
                break
        
        if marker_index != -1:
            # Marker found, insert before it
            processed_lines.extend(current_step_lines[:marker_index])
            processed_lines.extend(new_step_definition.splitlines())
            processed_lines.extend(current_step_lines[marker_index:])
        else:
            # No marker, append to the end
            # First, ensure the last step has a comma
            if current_step_lines:
                # Find the last line that contains a Step definition closing
                last_step_line_index = -1
                for i in range(len(current_step_lines) - 1, -1, -1):
                    line = current_step_lines[i].strip()
                    if line.endswith(')') and not line.endswith(','):
                        # This is likely the last step without a comma
                        current_step_lines[i] = current_step_lines[i] + ','
                        break
            
            processed_lines.extend(current_step_lines)
            processed_lines.extend(new_step_definition.splitlines())
    
    return "\n".join(processed_lines)

def generate_step_method_templates(step_id_str: str, step_done_key: str, step_show_name: str, app_name_var: str = "self.app_name"):
    """
    Generates the Python code for a new step's GET and POST handlers.
    The next_step_id for the new step's submit handler will be determined dynamically
    based on its position in the self.steps list within the workflow's __init__.
    
    The generated methods are wrapped with SWAPPABLE_STEP markers to enable
    the swap_workflow_step.py script to replace them with developed logic.
    """
    # Base indentation for methods within the class
    method_indent = "    " # Four spaces for class methods

    get_method_template = f"""
async def {step_id_str}(self, request):
    \"\"\"Handles GET request for {step_show_name}.\"\"\"
    pip, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, {app_name_var}
    step_id = "{step_id_str}"
    step_index = self.steps_indices[step_id]
    step = steps[step_index]
    # Determine next_step_id dynamically based on runtime position in steps list
    next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
    pipeline_id = db.get("pipeline_id", "unknown")
    state = pip.read_state(pipeline_id)
    step_data = pip.get_step_data(pipeline_id, step_id, {{}})
    current_value = step_data.get(step.done, "") # 'step.done' will be like '{step_done_key}'
    finalize_data = pip.get_step_data(pipeline_id, "finalize", {{}})

    if "finalized" in finalize_data and current_value:
        pip.append_to_history(f"[WIDGET CONTENT] {{step.show}} (Finalized):\\n{{current_value}}")
        return Div(
            Card(H3(f"🔒 {{step.show}}: Completed")),
            Div(id=next_step_id, hx_get=f"/{{app_name}}/{{next_step_id}}", hx_trigger="load"),
            id=step_id
        )
    elif current_value and state.get("_revert_target") != step_id:
        pip.append_to_history(f"[WIDGET CONTENT] {{step.show}} (Completed):\\n{{current_value}}")
        return Div(
            pip.display_revert_header(step_id=step_id, app_name=app_name, message=f"{{step.show}}: Complete", steps=steps),
            Div(id=next_step_id, hx_get=f"/{{app_name}}/{{next_step_id}}", hx_trigger="load"),
            id=step_id
        )
    else:
        pip.append_to_history(f"[WIDGET STATE] {{step.show}}: Showing input form")
        await self.message_queue.add(pip, self.step_messages[step_id]["input"], verbatim=True)
        return Div(
            Card(
                H3(f"{{step.show}}"),
                P("This is a new placeholder step. Customize its input form as needed. Click Proceed to continue."),
                Form(
                    # Example: Hidden input to submit something for the placeholder
                    Input(type="hidden", name=step.done, value="Placeholder Value for {step_show_name}"),
                    Button("Next ▸", type="submit", cls="primary"),
                    hx_post=f"/{{app_name}}/{{step_id}}_submit", hx_target=f"#{{step_id}}"
                )
            ),
            Div(id=next_step_id), # Placeholder for next step, no trigger here
            id=step_id
        )
"""

    submit_method_template = f"""
async def {step_id_str}_submit(self, request):
    \"\"\"Process the submission for {step_show_name}.\"\"\"
    pip, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, {app_name_var}
    step_id = "{step_id_str}"
    step_index = self.steps_indices[step_id]
    step = steps[step_index]
    next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
    pipeline_id = db.get("pipeline_id", "unknown")
    
    form_data = await request.form()
    # For a placeholder, get value from the hidden input or use a default
    value_to_save = form_data.get(step.done, f"Default value for {{step.show}}") 
    await pip.set_step_data(pipeline_id, step_id, value_to_save, steps)
    
    pip.append_to_history(f"[WIDGET CONTENT] {{step.show}}:\\n{{value_to_save}}")
    pip.append_to_history(f"[WIDGET STATE] {{step.show}}: Step completed")
    
    await self.message_queue.add(pip, f"{{step.show}} complete.", verbatim=True)
    
    return Div(
        pip.display_revert_header(step_id=step_id, app_name=app_name, message=f"{{step.show}}: Complete", steps=steps),
        Div(id=next_step_id, hx_get=f"/{{app_name}}/{{next_step_id}}", hx_trigger="load"),
        id=step_id
    )
"""
    # Add the class-level indentation to the entire template
    indented_get = "\n".join(f"{method_indent}{line}" for line in get_method_template.strip().split("\n"))
    indented_submit = "\n".join(f"{method_indent}{line}" for line in submit_method_template.strip().split("\n"))
    
    # Wrap with swappable step markers to enable swap_workflow_step.py
    swappable_start = f"{method_indent}# --- START_STEP_BUNDLE: {step_id_str} ---"
    swappable_end = f"{method_indent}# --- END_STEP_BUNDLE: {step_id_str} ---"
    
    return f"\n{swappable_start}\n{indented_get}\n\n\n{indented_submit}\n{swappable_end}\n"

def main():
    parser = argparse.ArgumentParser(
        description="Splice a new placeholder step into an existing Pipulate workflow plugin.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  # Insert at bottom (default - before finalize step):
  python splice_workflow_step.py 035_kungfu_workflow.py
  python splice_workflow_step.py 035_kungfu_workflow.py --position bottom
  
  # Insert at top (becomes the new first data step):
  python splice_workflow_step.py 035_kungfu_workflow.py --position top
  
  # Works with various path formats:
  python splice_workflow_step.py apps/035_kungfu_workflow.py --position top
  python splice_workflow_step.py /full/path/to/apps/035_kungfu_workflow.py --position bottom
        """
    )
    parser.add_argument("target_filename", help="The filename of the workflow to modify (e.g., 035_kungfu_workflow.py)")
    parser.add_argument("--position", choices=["top", "bottom"], default="bottom", 
                       help="Where to insert the new step: 'top' (becomes first data step) or 'bottom' (before finalize, default)")
    args = parser.parse_args()

    print(f"Pipulate project root found at: {PROJECT_ROOT}")
    print(f"Template file: {TEMPLATE_FILE_PATH}")
    print(f"Plugins directory: {PLUGINS_DIR}")
    print()


    # Normalize the target filename to just the basename
    # Handle various input formats cleanly using pathlib:
    # 1. Just filename: "035_kungfu_workflow.py"
    # 2. With apps/ prefix: "apps/035_kungfu_workflow.py"  
    # 3. Full path: "/some/path/apps/035_kungfu_workflow.py"
    target_filename = Path(args.target_filename).name
    
    # Ensure it has .py extension
    if not target_filename.endswith('.py'):
        target_filename += '.py'

    target_file_path = PLUGINS_DIR / target_filename
    
    print(f"Looking for workflow file: {target_file_path}")
    
    if not target_file_path.is_file():
        print(f"ERROR: Target workflow file not found at {target_file_path}")
        print(f"Available workflow files in {PLUGINS_DIR}:")
        try:
            workflow_files = [f.name for f in PLUGINS_DIR.glob("*.py") if not f.name.startswith('__')]
            for wf in sorted(workflow_files):
                print(f"  {wf}")
        except Exception:
            print("  (Could not list files)")
        return

    try:
        with open(target_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # --- 1. Find the steps list definition using the new flexible approach ---
        steps_list_prefix, steps_list_content, steps_list_suffix, original_full_block = find_steps_list_definition(content)
        
        if steps_list_content is None:
            return  # Error messages already printed by find_steps_list_definition
        
        # --- 2. Scan ALL existing Step definitions to find max step number ---
        step_id_matches = re.findall(r"Step\s*\(\s*id=['\"]step_(\d+)['\"]", steps_list_content)
        max_step_num = 0
        if step_id_matches:
            max_step_num = max(int(num_str) for num_str in step_id_matches)
        
        new_step_num = max_step_num + 1
        new_step_id_str = f"step_{new_step_num:02d}"
        new_step_done_key = f"placeholder_{new_step_num:02d}"
        new_step_show_name = f"Placeholder Step {new_step_num} (Edit Me)"
        
        print(f"Identified current max data collection step number: {max_step_num}")
        print(f"New step will be: {new_step_id_str} (Show: '{new_step_show_name}', Done key: '{new_step_done_key}')")
        print(f"Insertion position: {args.position}")

        # --- 3. Determine indentation by finding existing Step definitions ---
        indent_for_step_tuple = ""
        lines = steps_list_content.splitlines()
        for line in lines:
            stripped_line = line.lstrip()
            if stripped_line.startswith("Step("):
                indent_for_step_tuple = line[:len(line) - len(stripped_line)]
                break
        
        # Fallback to reasonable default if no Step found
        if not indent_for_step_tuple:
            indent_for_step_tuple = "            "  # 12 spaces (typical for list items in class)

        # --- 4. Create the new Step tuple string ---
        new_step_definition = (
            f"{indent_for_step_tuple}Step(\n"
            f"{indent_for_step_tuple}    id='{new_step_id_str}',\n"
            f"{indent_for_step_tuple}    done='{new_step_done_key}',\n"
            f"{indent_for_step_tuple}    show='{new_step_show_name}',\n"
            f"{indent_for_step_tuple}    refill=False,\n"
            f"{indent_for_step_tuple}),"
        )

        # --- 5. Insert the new Step definition based on position ---
        new_steps_list_content = insert_step_in_list_content(
            steps_list_content, new_step_definition, args.position, STEPS_LIST_MARKER
        )
        
        # --- 6. Reconstruct the steps list and replace in content ---
        new_full_block = steps_list_prefix + new_steps_list_content + steps_list_suffix
        content = content.replace(original_full_block, new_full_block, 1)
        
        print(f"Inserted Step definition for {new_step_id_str} at position '{args.position}'.")

        # --- 7. Generate the new async methods for this step ---
        new_methods_code = generate_step_method_templates(new_step_id_str, new_step_done_key, new_step_show_name)
        
        # --- 8. Insert new methods before the methods marker ---
        class_member_indent = "    " # Typical indent for class members / method definitions
        replacement_for_methods_marker = f"{new_methods_code.rstrip()}\n\n\n{class_member_indent}{STEP_METHODS_MARKER}"
        
        # Ensure the marker we're replacing has the expected indentation
        marker_with_indent = f"{class_member_indent}{STEP_METHODS_MARKER}"
        if marker_with_indent not in content:
            # Fallback: try finding marker without specific leading indent, but this is less safe
            print(f"Warning: Could not find STEP_METHODS_MARKER with precise indentation '{class_member_indent}'. Trying less specific match.")
            content = content.replace(STEP_METHODS_MARKER, replacement_for_methods_marker)
        else:
            content = content.replace(marker_with_indent, replacement_for_methods_marker)
        
        print(f"Inserted method definitions for {new_step_id_str}.")
        
        # --- 9. If inserting at top, update the init method to start with the new first step ---
        if args.position == "top":
            # Find and update the init method to start with the new first step
            init_pattern = re.compile(
                r"(return Div\(Div\(id=')[^']+(',\s*hx_get=f'/\{app_name\}/)[^']+(',\s*hx_trigger='load'\))",
                re.MULTILINE
            )
            
            def replace_init_step(match):
                return f"{match.group(1)}{new_step_id_str}{match.group(2)}{new_step_id_str}{match.group(3)}"
            
            content, init_replacements = init_pattern.subn(replace_init_step, content)
            
            if init_replacements > 0:
                print(f"Updated init method to start with {new_step_id_str} (made {init_replacements} replacement(s)).")
            else:
                print(f"Warning: Could not find init method pattern to update. The workflow may still start with the old first step.")
                print("You may need to manually update the init method to start with the new first step.")
        
        with open(target_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"\nSuccessfully spliced new step '{new_step_id_str}' into {target_file_path}")
        print("The workflow's __init__ method will automatically recreate routing and step messages.")
        print("Pipulate should auto-restart. Test the modified workflow.")
        print(f"Remember to customize the new methods for {new_step_id_str} and its input form.")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 
