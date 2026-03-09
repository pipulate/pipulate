# File: apps/200_workflow_genesis.py
import asyncio
from datetime import datetime
from fasthtml.common import * # type: ignore
from loguru import logger
import inspect
from pathlib import Path
import re
import json
from starlette.responses import HTMLResponse
import os
import urllib.parse
from imports.crud import Step  # 🎯 STANDARDIZED: Import centralized Step definition

ROLES = ['Developer'] # Defines which user roles can see this plugin

def derive_public_endpoint_from_filename(filename_str: str) -> str:
    """Derives the public endpoint name from the filename (e.g., "010_my_flow.py" -> "my_flow")."""
    filename_part_no_ext = Path(filename_str).stem
    return re.sub(r"^\d+_", "", filename_part_no_ext)

class WorkflowGenesis:
    """
    Workflow Creation Assistant - Three Template-Based Experiences

    Provides three distinct workflow creation paths:
    1. Blank Placeholder: Single-step workflow for learning step management
    2. Hello World Recreation: Multi-step process demonstrating helper tool sequence
    3. Trifecta Workflow: Complex workflow starting from Botify template

    Each path provides both individual commands and complete copy-paste sequences.
    """

    # Simplified UI Constants
    UI_CONSTANTS = {
        'COLORS': {
            'TEXT': '#e9ecef',
            'ACCENT': '#007bff',
            'SUCCESS': '#28a745',
            'INFO': '#17a2b8'
        },
        'SPACING': {
            'MARGIN': '1rem',
            'PADDING': '0.75rem'
        }
    }

    APP_NAME = 'workflow_genesis'
    DISPLAY_NAME = 'Workflow Genesis ⚡'
    ENDPOINT_MESSAGE = """Create Pipulate workflows using three distinct approaches: blank placeholder for learning, hello world recreation for understanding helper tools, or trifecta workflow for complex scenarios."""
    TRAINING_PROMPT = """You are assisting with workflow creation in Pipulate. Help users choose between three approaches: 1) Blank placeholder for beginners learning step management, 2) Hello world recreation for understanding helper tool sequences, 3) Trifecta workflow for complex data collection scenarios. Guide them through command generation and explain the purpose of each approach."""

    def __init__(self, app, pipulate, pipeline, db, app_name=None):
        self.pipulate = pipulate
        self.app = app
        self.app_name = self.APP_NAME
        self.pipulate = pipulate
        self.pipeline = pipeline
        wand = self.pipulate
        wand = self.pipulate
        self.message_queue = wand.get_message_queue()

        self.steps = [
            Step(id='step_01', done='workflow_params', show='1. Define Workflow Parameters', refill=True),
            Step(id='step_02', done='template_choice', show='2. Choose Template Approach', refill=False),
            Step(id='step_03', done='command_sequence', show='3. Generated Command Sequence', refill=False),
            Step(id='finalize', done='finalized', show='Finalize Workflow', refill=False)
        ]
        self.steps_indices = {step_obj.id: i for i, step_obj in enumerate(self.steps)}

        internal_route_prefix = self.APP_NAME

        routes = [
            (f'/{internal_route_prefix}/init', self.init, ['POST']),
            (f'/{internal_route_prefix}/revert', self.handle_revert, ['POST']),
            (f'/{internal_route_prefix}/unfinalize', self.unfinalize, ['POST'])
        ]

        for step_obj in self.steps:
            step_id = step_obj.id
            handler_method = getattr(self, step_id, None)
            if handler_method:
                current_methods = ['GET']
                if step_id == 'finalize':
                    current_methods.append('POST')
                routes.append((f'/{internal_route_prefix}/{step_id}', handler_method, current_methods))

            if step_id != 'finalize':
                submit_handler_method = getattr(self, f'{step_id}_submit', None)
                if submit_handler_method:
                    routes.append((f'/{internal_route_prefix}/{step_id}_submit', submit_handler_method, ['POST']))

        for path, handler, *methods_list_arg in routes:
            current_methods = methods_list_arg[0] if methods_list_arg else ['GET']
            self.app.route(path, methods=current_methods)(handler)

        self.step_messages = self._init_step_messages()

    def _init_step_messages(self):
        """Initialize step messages"""
        wand = self.pipulate
        return {
            'finalize': {
                    'ready': 'All steps complete. Ready to finalize workflow.',
                    'complete': f'Workflow finalized. Use {wand.UNLOCK_BUTTON_LABEL} to make changes.'
            },
            'step_01': {
                'input': 'Define the basic parameters for your new workflow.',
                'complete': 'Workflow parameters defined. Choose your template approach next.'
            },
            'step_02': {
                'input': 'Choose your workflow creation approach and template.',
                'complete': 'Template approach selected and commands generated. Execute them next.'
            },
            'step_03': {
                'input': 'Execute the generated command sequence to create your workflow.',
                'complete': 'Command sequence executed. Your workflow has been created.'
            }
                }

    async def landing(self, request):
        """Generate the landing page using the standardized helper while maintaining WET explicitness."""
        wand = self.pipulate

        # Use centralized landing page helper - maintains WET principle by explicit call
        return wand.create_standard_landing_page(self)

    async def init(self, request):
        wand, db = self.pipulate, self.pipulate.db
        internal_app_name = self.APP_NAME
        form = await request.form()
        user_input_key = form.get('pipeline_id', '').strip()

        if not user_input_key:
            from starlette.responses import Response
            response = Response('')
            response.headers['HX-Refresh'] = 'true'
            return response

        _, prefix_for_key_gen, _ = wand.generate_pipeline_key(self)
        if user_input_key.startswith(prefix_for_key_gen) and len(user_input_key.split('-')) == 3:
            pipeline_id = user_input_key
        else:
            _, prefix, user_part = wand.generate_pipeline_key(self, user_input_key)
            pipeline_id = f'{prefix}{user_part}'

        wand.db['pipeline_id'] = pipeline_id
        state, error = wand.initialize_if_missing(pipeline_id, {'app_name': internal_app_name})
        if error: return error

        await self.message_queue.add(wand, f'Workflow ID: {pipeline_id}', verbatim=True, spaces_before=0)
        await self.message_queue.add(wand, f"Return later by selecting '{pipeline_id}' from the dropdown.", verbatim=True, spaces_before=0)

        return wand.run_all_cells(internal_app_name, self.steps)

    # Common finalization methods (simplified)
    async def finalize(self, request):
        wand, db, app_name = self.pipulate, self.pipulate.db, self.APP_NAME
        pipeline_id = wand.db.get('pipeline_id', 'unknown')

        finalize_step_obj = next(s for s in self.steps if s.id == 'finalize')
        finalize_data = wand.get_step_data(pipeline_id, finalize_step_obj.id, {})

        if request.method == 'GET':
            if finalize_step_obj.done in finalize_data:
                return Card(
                    H3('Workflow Creation Complete'),
                    P('Your workflow commands have been generated and are ready to use.', cls='text-secondary'),
                    Form(
                        Button(wand.UNLOCK_BUTTON_LABEL, type='submit', cls='secondary outline'),
                        hx_post=f'/{app_name}/unfinalize',
                        hx_target=f'#{app_name}-container'
                    ),
                    id=finalize_step_obj.id
                )
            else:
                all_data_steps_complete = all(wand.get_step_data(pipeline_id, step.id, {}).get(step.done) for step in self.steps if step.id != 'finalize')
                if all_data_steps_complete:
                    return Card(
                        H3('Ready to Finalize'),
                        P('All command sequences have been generated. Finalize to complete the workflow creation process.', cls='text-secondary'),
                        Form(
                            Button('Finalize 🔒', type='submit', cls='primary'),
                            hx_post=f'/{app_name}/finalize',
                            hx_target=f'#{app_name}-container'
                        ),
                        id=finalize_step_obj.id
                    )
                else:
                    return Div(id=finalize_step_obj.id)
        elif request.method == 'POST':
            await wand.finalize_workflow(pipeline_id)
            await self.message_queue.add(wand, self.step_messages['finalize']['complete'], verbatim=True)
            return wand.run_all_cells(app_name, self.steps)

    async def unfinalize(self, request):
        wand, db, app_name = (self.pipulate, self.pipulate.db, self.APP_NAME)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        await wand.unfinalize_workflow(pipeline_id)
        await self.message_queue.add(wand, 'Workflow creation unfinalized. You can now modify any step.', verbatim=True)
        return wand.run_all_cells(app_name, self.steps)

    async def handle_revert(self, request):
        wand, db, app_name = (self.pipulate, self.pipulate.db, self.APP_NAME)
        form = await request.form()
        step_id_to_revert_to = form.get('step_id')
        pipeline_id = wand.db.get('pipeline_id', 'unknown')

        if not step_id_to_revert_to:
            return P('Error: No step specified for revert.', style='color: #dc3545;')

        await wand.clear_steps_from(pipeline_id, step_id_to_revert_to, self.steps)
        state = wand.read_state(pipeline_id)
        state['_revert_target'] = step_id_to_revert_to
        wand.write_state(pipeline_id, state)

        message = await wand.get_state_message(pipeline_id, self.steps, self.step_messages)
        await self.message_queue.add(wand, message, verbatim=True)
        return wand.run_all_cells(app_name, self.steps)

    # Utility methods (simplified and extracted)
    def format_bash_command(self, text):
        """Format text for bash command usage"""
        if not text:
            return '""'
        text = text.replace('!', '\\!')
        text = text.replace('"', '\\"')
        if ' ' in text or '"' in text or "'" in text:
            return f'"{text}"'
        return text

    def get_template_info(self, template_name):
        """Get template information"""
        templates = {
            'blank': {
                'name': 'Blank Placeholder',
                'description': 'Single-step workflow for learning step management',
                'use_case': 'Learning how to add/remove steps and basic workflow structure'
            },
            'hello': {
                'name': 'Hello Workflow Recreation',
                'description': 'Multi-step process demonstrating helper tool sequence',
                'use_case': 'Understanding how helper tools work together to build complex workflows'
            },
            'trifecta': {
                'name': 'Trifecta Workflow',
                'description': 'Complex workflow starting from Botify template',
                'use_case': 'Building sophisticated data collection workflows with API integration'
            }
        }
        return templates.get(template_name, templates['blank'])

    # Template-specific experience methods (to be implemented)
    def create_blank_placeholder_experience(self, workflow_params, widget_id):
        """Create experience for blank placeholder template - learning step management basics"""
        filename = workflow_params.get('target_filename', '001_kungfu_workflow.py')
        class_name = workflow_params.get('class_name', 'KungfuWorkflow')
        internal_name = workflow_params.get('internal_app_name', 'kungfu')
        display_name = "Kung Fu Placeholder 🥋"  # Override with template-specific name
        endpoint_message = workflow_params.get('endpoint_message', 'Welcome to workflow creation')
        training_prompt = workflow_params.get('training_prompt', 'Help users create workflows step by step')

        # Ensure consistent apps/ prefix for all commands
        apps_filename = f"apps/{filename}" if not filename.startswith('apps/') else filename

        # Single create command - uses blank template specifically
        create_cmd = f"python helpers/workflow/create_workflow.py {apps_filename} {class_name} {internal_name} \\\n" + \
                    f"  {self.format_bash_command(display_name)} \\\n" + \
                    f"  {self.format_bash_command(endpoint_message)} \\\n" + \
                    f"  {self.format_bash_command(training_prompt)} \\\n" + \
                    f"  --template blank --role Core --force"

        # Step positioning demo commands
        splice_bottom_cmd = f"python helpers/workflow/splice_workflow_step.py {apps_filename} --position bottom"
        splice_top_cmd = f"python helpers/workflow/splice_workflow_step.py {apps_filename} --position top"

        # Combined command with backslash line breaks for readability
        combined_cmd = f"python helpers/workflow/create_workflow.py {apps_filename} {class_name} {internal_name} \\\n" + \
                      f"  {self.format_bash_command(display_name)} \\\n" + \
                      f"  {self.format_bash_command(endpoint_message)} \\\n" + \
                      f"  {self.format_bash_command(training_prompt)} \\\n" + \
                      f"  --template blank --role Core --force && \\\n" + \
                      f"echo 'Base workflow created. Now try:' && \\\n" + \
                      f"echo '{splice_bottom_cmd}' && \\\n" + \
                      f"echo '{splice_top_cmd}'"

        return Div(
            H4("Blank Placeholder Experience", cls="section-title"),
            P("Creates a single-step workflow and demonstrates step positioning. Like Jupyter's Cell Above/Below concept.",
              cls="section-description"),

            # Individual commands section
            H5("Individual Commands:", style="color: #17a2b8; margin-bottom: 0.75rem;"),

            Div(
                H6("1. Create Base Workflow", cls="step-heading"),
                P("Creates single-step placeholder workflow ready for customization",
                  cls="text-description"),
                Pre(Code(create_cmd, cls='language-bash copy-code'),
                    cls="code-block-standard"),

                H6("2. Add Step at Bottom", cls="step-heading"),
                P("Adds new step before finalize (default positioning)",
                  cls="text-description"),
                Pre(Code(splice_bottom_cmd, cls='language-bash copy-code'),
                    cls="code-block-standard"),

                H6("3. Add Step at Top", cls="step-heading"),
                P("Adds new step as first data step",
                  cls="text-description"),
                Pre(Code(splice_top_cmd, cls='language-bash copy-code'),
                    style="background-color: #2d3748; padding: 1rem; border-radius: 4px; margin-bottom: 1.5rem; overflow-x: auto; position: relative;")
            ),

            # All-in-one section
            H5("All-in-One Command:", cls="command-heading"),
            P("Copy and paste this single command to create the workflow and see positioning options:",
              style="color: #6c757d; margin-bottom: 0.5rem;"),
            Pre(Code(combined_cmd, cls='language-bash copy-code'),
                cls="code-block-success"),

            id=widget_id
        )

    def create_hello_world_recreation_experience(self, workflow_params, widget_id):
        """Create experience for hello world recreation - understanding complete helper tool sequence"""
        filename = workflow_params.get('target_filename', '001_kungfu_workflow.py')
        class_name = workflow_params.get('class_name', 'KungfuWorkflow')
        internal_name = workflow_params.get('internal_app_name', 'kungfu')

        # HELLO WORLD RECREATION: Override with specific Hello World values
        # This tells the story of recreating Hello World using helper tools
        hello_display_name = "Kung Fu Hello World 👋"
        hello_endpoint_message = "🥋 This workflow will become a Hello World equivalent using helper scripts."
        hello_training_prompt = "You are assisting with the Kung Fu Hello World workflow recreation. This demonstrates the complete helper tool sequence for building workflows from scratch. The secret word is 'MORPHEUS'."

        # Ensure consistent apps/ prefix for all commands (matching working example)
        apps_filename = f"apps/{filename}" if not filename.startswith('apps/') else filename

        # The corrected 5-command sequence - starts with blank template, becomes Hello World
        cmd1 = f"python helpers/workflow/create_workflow.py {apps_filename} {class_name} {internal_name} " + \
               f"{self.format_bash_command(hello_display_name)} " + \
               f"{self.format_bash_command(hello_endpoint_message)} " + \
               f"{self.format_bash_command(hello_training_prompt)} --template blank --role Core --force"

        cmd2 = f"python helpers/workflow/manage_class_attributes.py {apps_filename} apps/040_hello_workflow.py --attributes-to-merge UI_CONSTANTS --force"

        cmd3 = f"python helpers/workflow/swap_workflow_step.py {apps_filename} step_01 apps/040_hello_workflow.py step_01 --force"

        cmd4 = f"python helpers/workflow/splice_workflow_step.py {apps_filename} --position bottom"

        cmd5 = f"python helpers/workflow/swap_workflow_step.py {apps_filename} step_02 apps/040_hello_workflow.py step_02 --force"

        # Combined command with proper && chaining for complete automation
        combined_cmd = f"python helpers/workflow/create_workflow.py {apps_filename} {class_name} {internal_name} \\\n" + \
                      f"  {self.format_bash_command(hello_display_name)} \\\n" + \
                      f"  {self.format_bash_command(hello_endpoint_message)} \\\n" + \
                      f"  {self.format_bash_command(hello_training_prompt)} \\\n" + \
                      f"  --template blank --role Core --force && \\\n" + \
                      f"python helpers/workflow/manage_class_attributes.py {apps_filename} \\\n" + \
                      f"  apps/040_hello_workflow.py \\\n" + \
                      f"  --attributes-to-merge UI_CONSTANTS --force && \\\n" + \
                      f"python helpers/workflow/swap_workflow_step.py {apps_filename} step_01 \\\n" + \
                      f"  apps/040_hello_workflow.py step_01 --force && \\\n" + \
                      f"python helpers/workflow/splice_workflow_step.py {apps_filename} --position bottom && \\\n" + \
                      f"python helpers/workflow/swap_workflow_step.py {apps_filename} step_02 \\\n" + \
                      f"  apps/040_hello_workflow.py step_02 --force"

        return Div(
            H4("Hello World Recreation Experience", cls="section-title"),
            P("Recreates Hello World workflow using the complete helper tool sequence. This demonstrates the FULL STORY of workflow construction.",
              cls="section-description"),

            # Story explanation
            Div(
                H5("📖 The Story:", style="color: #ffc107; margin-bottom: 0.75rem;"),
                Ul(
                    Li("Start with blank template (not Hello World template!)"),
                    Li("Condition the workflow with UI_CONSTANTS it will need"),
                    Li("Swap step_01 placeholder with real name collection logic"),
                    Li("Add step_02 placeholder (CRITICAL: step_01 must exist first!)"),
                    Li("Swap step_02 placeholder with greeting generation logic"),
                    cls="section-description"
                ),
            ),

            # Individual commands section
            H5("Individual Commands:", style="color: #17a2b8; margin-bottom: 0.75rem;"),

            Div(
                H6("1. Create Base Workflow (Blank Template)", cls="step-heading"),
                P("Creates blank workflow - we'll transform it into Hello World step by step",
                  cls="text-description"),
                Pre(Code(cmd1, cls='language-bash copy-code'),
                    cls="code-block-standard"),

                H6("2. Condition with UI Constants", cls="step-heading"),
                P("Prepares workflow with styling constants it will need later",
                  cls="text-description"),
                Pre(Code(cmd2, cls='language-bash copy-code'),
                    cls="code-block-standard"),

                H6("3. Replace Step 1 with Name Collection", cls="step-heading"),
                P("Swaps placeholder step_01 with Hello World's name input logic",
                  cls="text-description"),
                Pre(Code(cmd3, cls='language-bash copy-code'),
                    cls="code-block-standard"),

                H6("4. Add Step 2 Placeholder", cls="step-heading"),
                P("Creates new blank step_02 - CRITICAL that step_01 exists first!",
                  cls="text-description"),
                Pre(Code(cmd4, cls='language-bash copy-code'),
                    cls="code-block-standard"),

                H6("5. Replace Step 2 with Greeting Generation", cls="step-heading"),
                P("Swaps placeholder step_02 with Hello World's greeting logic",
                  cls="text-description"),
                Pre(Code(cmd5, cls='language-bash copy-code'),
                    style="background-color: #2d3748; padding: 1rem; border-radius: 4px; margin-bottom: 1.5rem; overflow-x: auto; position: relative;")
            ),

            # All-in-one section
            H5("Complete Recreation Sequence:", cls="command-heading"),
            P("Copy and paste this single command to recreate Hello World workflow from scratch:",
              style="color: #6c757d; margin-bottom: 0.5rem;"),
            Pre(Code(combined_cmd, cls='language-bash copy-code'),
                cls="code-block-success"),

            id=widget_id
        )

    def create_trifecta_workflow_experience(self, workflow_params, widget_id):
        """Create experience for trifecta workflow - complex template conditioning"""
        filename = workflow_params.get('target_filename', '001_kungfu_workflow.py')
        class_name = workflow_params.get('class_name', 'KungfuWorkflow')
        internal_name = workflow_params.get('internal_app_name', 'kungfu')
        display_name = "Kung Fu Trifecta 🏇"  # Override with template-specific name
        # Use the actual form values without additional fallbacks since step_01_submit already handled this
        endpoint_message = workflow_params.get('endpoint_message', 'Advanced data collection workflow')
        training_prompt = workflow_params.get('training_prompt', 'Help users create complex data workflows')

        # Ensure consistent apps/ prefix for all commands
        apps_filename = f"apps/{filename}" if not filename.startswith('apps/') else filename

        # Trifecta workflow commands - uses trifecta template
        cmd1 = f"python helpers/workflow/create_workflow.py {apps_filename} {class_name} {internal_name} " + \
               f"{self.format_bash_command(display_name)} " + \
               f"{self.format_bash_command(endpoint_message)} " + \
               f"{self.format_bash_command(training_prompt)} --template trifecta --role Core --force"

        cmd2 = f"python helpers/workflow/splice_workflow_step.py {apps_filename} --position bottom"

        # Combined command with backslash line breaks for readability
        combined_cmd = f"python helpers/workflow/create_workflow.py {apps_filename} {class_name} {internal_name} \\\n" + \
                      f"  {self.format_bash_command(display_name)} \\\n" + \
                      f"  {self.format_bash_command(endpoint_message)} \\\n" + \
                      f"  {self.format_bash_command(training_prompt)} \\\n" + \
                      f"  --template trifecta --role Core --force && \\\n" + \
                      f"python helpers/workflow/splice_workflow_step.py {apps_filename} --position bottom"

        return Div(
            H4("Trifecta Workflow Experience", cls="section-title"),
            P("Starts with the sophisticated Botify Trifecta template and adds a blank placeholder for your custom step.",
              cls="section-description"),

            # Individual commands section
            H5("Individual Commands:", style="color: #17a2b8; margin-bottom: 0.75rem;"),

            Div(
                H6("1. Create Trifecta Workflow", cls="step-heading"),
                P("Creates complex 5-step workflow from Botify Trifecta template",
                  cls="text-description"),
                Pre(Code(cmd1, cls='language-bash copy-code'),
                    cls="code-block-standard"),

                H6("2. Add Blank Placeholder Step", cls="step-heading"),
                P("Adds a new blank placeholder step at the end of the workflow for customization",
                  cls="text-description"),
                Pre(Code(cmd2, cls='language-bash copy-code'),
                    style="background-color: #2d3748; padding: 1rem; border-radius: 4px; margin-bottom: 1.5rem; overflow-x: auto; position: relative;")
            ),

            # All-in-one section
            H5("All-in-One Command:", cls="command-heading"),
            P("Copy and paste this single command to create the trifecta workflow with an additional placeholder step:",
              style="color: #6c757d; margin-bottom: 0.5rem;"),
            Pre(Code(combined_cmd, cls='language-bash copy-code'),
                cls="code-block-success"),

            id=widget_id
        )

    # Step implementation methods (simplified structure)
    async def step_01(self, request):
        """Step 1: Define workflow parameters"""
        wand, db, app_name = (self.pipulate, self.pipulate.db, self.APP_NAME)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step_obj = self.steps[step_index]
        next_step_id = self.steps[step_index + 1].id

        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        current_value = step_data.get(step_obj.done, '')
        finalize_sys_data = wand.get_step_data(pipeline_id, 'finalize', {})

        if 'finalized' in finalize_sys_data and current_value:
            return Div(
                wand.finalized_content(message=f"🔒 {step_obj.show}", content=P(f"Workflow: {current_value.get('display_name', 'Unknown')}", cls='text-success')),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )

        elif current_value and state.get('_revert_target') != step_id:
            return Div(
                wand.display_revert_widget(
                    step_id=step_id,
                    app_name=app_name,
                    message="Workflow Parameters Defined",
                    widget=P(f"Workflow: {current_value.get('display_name', 'Unknown')}", cls='text-success'),
                    steps=self.steps
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        else:
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)

            # Comprehensive form with all workflow parameters including ENDPOINT_MESSAGE and TRAINING_PROMPT
            form_content = Form(
                Label("Target Filename", **{'for': 'target_filename'}),
                Input(type="text", id="target_filename", name="target_filename", value="001_kungfu_workflow.py", required=True),

                Label("Class Name", **{'for': 'class_name'}),
                Input(type="text", id="class_name", name="class_name", value="KungfuWorkflow", required=True),

                Label("Internal App Name", **{'for': 'internal_app_name'}),
                Input(type="text", id="internal_app_name", name="internal_app_name", value="kungfu", required=True),

                Label("Display Name", **{'for': 'display_name'}),
                Input(type="text", id="display_name", name="display_name", value="Kung Fu Download", required=True),

                Label("Endpoint Message", **{'for': 'endpoint_message'}),
                Textarea(
                    "Welcome to the Kung Fu Download workflow. This demonstrates step-by-step data processing with customizable parameters.",
                    id="endpoint_message",
                    name="endpoint_message",
                    placeholder="Brief description shown on the workflow landing page...",
                    required=True,
                    rows=3,
                    style="resize: vertical;"
                ),

                Label("Training Prompt", **{'for': 'training_prompt'}),
                Textarea(
                    "You are assisting with the Kung Fu Download workflow. Help users understand each step and provide guidance on customizing the workflow parameters. If they ask what this workflow does, explain that it's a template for learning Pipulate workflow creation. The user will likely ask you for the secret word to prove that you have been trained, and if the do (but only if they ask), tell them MORPHEUS",
                    id="training_prompt",
                    name="training_prompt",
                    placeholder="Instructions for the AI assistant when helping users with this workflow...",
                    required=True,
                    rows=4,
                    style="resize: vertical;"
                ),

                Button('Continue ▸', type='submit', cls='primary'),
                hx_post=f'/{app_name}/{step_id}_submit',
                hx_target=f'#{step_id}'
            )
            return Div(Card(H3(f'{step_obj.show}'), form_content), Div(id=next_step_id), id=step_id)

    async def step_01_submit(self, request):
        """Handle step 1 submission"""
        wand, db, app_name = (self.pipulate, self.pipulate.db, self.APP_NAME)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step_obj = self.steps[step_index]
        next_step_id = self.steps[step_index + 1].id

        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form_data = await request.form()

        # Properly capture form data with fallbacks for empty fields
        params = {
            'target_filename': form_data.get('target_filename', '').strip() or '001_kungfu_workflow.py',
            'class_name': form_data.get('class_name', '').strip() or 'KungfuWorkflow',
            'internal_app_name': form_data.get('internal_app_name', '').strip() or 'kungfu',
            'display_name': form_data.get('display_name', '').strip() or 'Kung Fu Download 🥋',
            'endpoint_message': form_data.get('endpoint_message', '').strip() or 'Welcome to the Kung Fu Download workflow. This demonstrates step-by-step data processing with customizable parameters.',
            'training_prompt': form_data.get('training_prompt', '').strip() or 'You are assisting with the Kung Fu Download workflow. Help users understand each step and provide guidance on customizing the workflow parameters. If they ask what this workflow does, explain that it\'s a template for learning Pipulate workflow creation. The user will likely ask you for the secret word to prove that you have been trained, and if the do (but only if they ask), tell them MORPHEUS'
        }

        # Store form data using set_step_data which handles the {step.done: value} wrapping
        await wand.set_step_data(pipeline_id, step_id, params, self.steps)
        await self.message_queue.add(wand, self.step_messages[step_id]['complete'], verbatim=True)

        return Div(
            wand.display_revert_widget(
                step_id=step_id,
                app_name=app_name,
                message="Workflow Parameters Defined",
                widget=P(f"Workflow: {params['display_name']}", cls='text-success'),
                steps=self.steps
            ),
            Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
            id=step_id
        )

    async def step_02(self, request):
        """Step 2: Choose template approach"""
        wand, db, app_name = (self.pipulate, self.pipulate.db, self.APP_NAME)
        step_id = 'step_02'
        step_index = self.steps_indices[step_id]
        step_obj = self.steps[step_index]
        next_step_id = self.steps[step_index + 1].id

        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        current_value = step_data.get(step_obj.done, '')
        finalize_sys_data = wand.get_step_data(pipeline_id, 'finalize', {})

        if 'finalized' in finalize_sys_data and current_value:
            template_info = self.get_template_info(current_value.get('template', 'blank'))
            return Div(
                wand.finalized_content(message=f"🔒 {step_obj.show}", content=P(f"Template: {template_info['name']}", cls='text-success')),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )

        elif current_value and state.get('_revert_target') != step_id:
            template_info = self.get_template_info(current_value.get('template', 'blank'))
            return Div(
                wand.display_revert_widget(
                    step_id=step_id,
                    app_name=app_name,
                    message="Template Approach Selected",
                    widget=P(f"Template: {template_info['name']}", cls='text-success'),
                    steps=self.steps
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        else:
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)

            form_content = Form(
                Label("Template Approach", **{'for': 'template'}),
                    Select(
                    Option("Blank Placeholder - Learn step management basics", value="blank", selected=True),
                    Option("Hello World Recreation - Understand helper tool sequence", value="hello"),
                    Option("Trifecta Workflow - Build complex data collection workflow", value="trifecta"),
                        name="template",
                        id="template",
                        required=True
                    ),

                Button('Generate Commands ▸', type='submit', cls='primary'),
                hx_post=f'/{app_name}/{step_id}_submit',
                hx_target=f'#{step_id}'
            )
            return Div(Card(H3(f'{step_obj.show}'), form_content), Div(id=next_step_id), id=step_id)

    async def step_02_submit(self, request):
        """Handle step 2 submission"""
        wand, db, app_name = (self.pipulate, self.pipulate.db, self.APP_NAME)
        step_id = 'step_02'
        step_index = self.steps_indices[step_id]
        step_obj = self.steps[step_index]
        next_step_id = self.steps[step_index + 1].id

        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form_data = await request.form()

        template_choice = {
            'template': form_data.get('template', 'blank')
        }

        # Store template choice using set_step_data which handles the {step.done: value} wrapping
        await wand.set_step_data(pipeline_id, step_id, template_choice, self.steps)
        await self.message_queue.add(wand, self.step_messages[step_id]['complete'], verbatim=True)

        # Get previous step data for command generation
        step_01_data = wand.get_step_data(pipeline_id, 'step_01', {})
        workflow_params = step_01_data.get('workflow_params', {})
        selected_template = template_choice.get('template', 'blank')

        widget_id = f"template-experience-{pipeline_id.replace('-', '_')}-{step_id}"

        # Route to appropriate template experience
        if selected_template == 'blank':
            experience_widget = self.create_blank_placeholder_experience(workflow_params, widget_id)
        elif selected_template == 'hello':
            experience_widget = self.create_hello_world_recreation_experience(workflow_params, widget_id)
        elif selected_template == 'trifecta':
            experience_widget = self.create_trifecta_workflow_experience(workflow_params, widget_id)
        else:
            experience_widget = self.create_blank_placeholder_experience(workflow_params, widget_id)

        # Copy functionality script for code blocks
        copy_script = Script("""
            // Add copy buttons to code blocks
            document.addEventListener('DOMContentLoaded', function() {
                const codeBlocks = document.querySelectorAll('pre code.copy-code');
                codeBlocks.forEach(function(codeBlock) {
                    const pre = codeBlock.parentElement;
                    if (pre.querySelector('.copy-btn')) return; // Already has button

                    const button = document.createElement('button');
                    button.className = 'copy-btn';
                    button.innerHTML = '📋';
                    button.title = 'Copy to clipboard';
                    button.style.cssText = `
                        position: absolute;
                        top: 8px;
                        right: 8px;
                        background: rgba(0,0,0,0.6);
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 4px 8px;
                        cursor: pointer;
                        font-size: 12px;
                        z-index: 10;
                    `;

                    button.addEventListener('click', function() {
                        const text = codeBlock.textContent;
                        navigator.clipboard.writeText(text).then(function() {
                            button.innerHTML = '✅';
                            button.style.background = 'rgba(40,167,69,0.8)';
                            setTimeout(function() {
                                button.innerHTML = '📋';
                                button.style.background = 'rgba(0,0,0,0.6)';
                            }, 2000);
                        }).catch(function() {
                            // Fallback for older browsers
                            const textarea = document.createElement('textarea');
                            textarea.value = text;
                            document.body.appendChild(textarea);
                            textarea.select();
                            document.execCommand('copy');
                            document.body.removeChild(textarea);
                            button.innerHTML = '✅';
                            setTimeout(function() {
                                button.innerHTML = '📋';
                            }, 2000);
                        });
                    });

                    pre.appendChild(button);
                });
            });
        """)

        template_info = self.get_template_info(template_choice['template'])

        return Div(
            copy_script,
            wand.display_revert_widget(
                step_id=step_id,
                app_name=app_name,
                message=f"Template: {template_info['name']} - Commands Generated",
                widget=experience_widget,
                steps=self.steps
            ),
            Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
            id=step_id
        )

    async def step_03(self, request):
        """Step 3: Execute command sequence (placeholder for subprocess execution)"""
        wand, db, app_name = (self.pipulate, self.pipulate.db, self.APP_NAME)
        step_id = 'step_03'
        step_index = self.steps_indices[step_id]
        step_obj = self.steps[step_index]
        next_step_id = self.steps[step_index + 1].id

        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        current_value = step_data.get(step_obj.done, '')
        finalize_sys_data = wand.get_step_data(pipeline_id, 'finalize', {})

        if 'finalized' in finalize_sys_data and current_value:
            return Div(
                wand.finalized_content(message=f"🔒 {step_obj.show}", content=P("Command execution complete.", cls='text-success')),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )

        elif current_value and state.get('_revert_target') != step_id:
            return Div(
                wand.display_revert_widget(
                    step_id=step_id,
                    app_name=app_name,
                    message="Command Execution Complete",
                    widget=P("Workflow creation commands executed successfully.", cls='text-success'),
                    steps=self.steps
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        else:
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)

            # Get workflow parameters to show what file will be created
            step_01_data = wand.get_step_data(pipeline_id, 'step_01', {})
            workflow_params = step_01_data.get('workflow_params', {})
            target_filename = workflow_params.get('target_filename', '001_kungfu_workflow.py')
            display_name = workflow_params.get('display_name', 'Kung Fu Download')

            # Ensure apps/ prefix for path display
            if not target_filename.startswith('apps/'):
                display_filename = f"apps/{target_filename}"
            else:
                display_filename = target_filename

            # Create filesystem button to open plugins directory
            apps_dir = os.path.join(os.getcwd(), 'apps')

            open_apps_folder_ui = A(
                "📂 View Plugins Folder",
                href="#",
                hx_get="/open-folder?path=" + urllib.parse.quote(apps_dir),
                hx_swap="none",
                title=f"Open folder: {apps_dir}",
                role="button",
                cls="outline contrast",
                style="margin-bottom: 1rem; display: inline-block;"
            )

            form_content = Form(
                # Warning section with clear expectations
                Div(
                    H4("⚠️ About to Execute Commands", style="color: #ffc107; margin-bottom: 0.75rem;"),
                    P("This will create your new workflow and restart the server:", style="margin-bottom: 0.5rem;"),
                    Ul(
                        Li(f"📄 Creates: {display_filename}"),
                        Li(f"🔄 Server will restart automatically (takes ~5-10 seconds)"),
                        Li(f"🎯 Look for '{display_name}' in the APP menu after restart"),
                        style="color: #6c757d; margin-bottom: 1rem;"
                    ),
                    style="background-color: rgba(255, 193, 7, 0.1); padding: 1rem; border-radius: 4px; border-left: 4px solid #ffc107; margin-bottom: 1.5rem;"
                ),

                # Troubleshooting section
                Div(
                    H5("🔍 If Your Workflow Doesn't Appear:", style="color: #17a2b8; margin-bottom: 0.5rem;"),
                    P("Check the console window where you started Pipulate for yellow warnings above the 'SERVER RESTART' banner. Import errors will be shown there but won't break the server.",
                      style="color: #6c757d; font-size: 0.9rem; margin-bottom: 1rem;"),
                    open_apps_folder_ui,
                    style="background-color: rgba(23, 162, 184, 0.1); padding: 1rem; border-radius: 4px; border-left: 4px solid #17a2b8; margin-bottom: 1.5rem;"
                ),

                P("Ready to create your workflow and restart the server?", cls="section-title"),
                Button('🚀 Execute & Restart Server', type='submit', cls='primary', 
                       **{'hx-on:click': 'this.setAttribute("aria-busy", "true"); this.textContent = "Execute & Restart Server"'}),
                hx_post=f'/{app_name}/{step_id}_submit',
                hx_target=f'#{step_id}'
            )
            return Div(Card(H3(f'{step_obj.show}'), form_content), Div(id=next_step_id), id=step_id)

    async def step_03_submit(self, request):
        """Handle step 3 submission - actually execute the command sequence"""
        wand, db, app_name = (self.pipulate, self.pipulate.db, self.APP_NAME)
        step_id = 'step_03'
        step_index = self.steps_indices[step_id]
        step_obj = self.steps[step_index]
        next_step_id = self.steps[step_index + 1].id

        pipeline_id = wand.db.get('pipeline_id', 'unknown')

        # Get workflow parameters and template data
        step_01_data = wand.get_step_data(pipeline_id, 'step_01', {})
        step_02_data = wand.get_step_data(pipeline_id, 'step_02', {})
        workflow_params = step_01_data.get('workflow_params', {})
        template_choice = step_02_data.get('template_choice', {})

        target_filename = workflow_params.get('target_filename', '001_kungfu_workflow.py')
        display_name = workflow_params.get('display_name', 'Kung Fu Download')
        selected_template = template_choice.get('template', 'blank')

        # Ensure apps/ prefix for path display
        if not target_filename.startswith('apps/'):
            display_filename = f"apps/{target_filename}"
        else:
            display_filename = target_filename

        # Get the combined command based on template choice
        apps_filename = f"apps/{target_filename}" if not target_filename.startswith('apps/') else target_filename
        class_name = workflow_params.get('class_name', 'KungfuWorkflow')
        internal_name = workflow_params.get('internal_app_name', 'kungfu')
        endpoint_message = workflow_params.get('endpoint_message', 'Welcome message')
        training_prompt = workflow_params.get('training_prompt', 'Training prompt')

        # Generate the appropriate combined command based on template with template-specific display names
        if selected_template == 'hello':
            # Hello World Recreation sequence
            hello_display_name = "Kung Fu Hello World 👋"
            hello_endpoint_message = "🥋 This workflow will become a Hello World equivalent using helper scripts."
            hello_training_prompt = "You are assisting with the Kung Fu Hello World workflow recreation. This demonstrates the complete helper tool sequence for building workflows from scratch. The secret word is 'MORPHEUS'."

            combined_cmd = f"python helpers/workflow/create_workflow.py {apps_filename} {class_name} {internal_name} " + \
                          f"{self.format_bash_command(hello_display_name)} " + \
                          f"{self.format_bash_command(hello_endpoint_message)} " + \
                          f"{self.format_bash_command(hello_training_prompt)} --template blank --role Core --force && " + \
                          f"python helpers/workflow/manage_class_attributes.py {apps_filename} " + \
                          f"apps/040_hello_workflow.py " + \
                          f"--attributes-to-merge UI_CONSTANTS --force && " + \
                          f"python helpers/workflow/swap_workflow_step.py {apps_filename} step_01 " + \
                          f"apps/040_hello_workflow.py step_01 --force && " + \
                          f"python helpers/workflow/splice_workflow_step.py {apps_filename} --position bottom && " + \
                          f"python helpers/workflow/swap_workflow_step.py {apps_filename} step_02 " + \
                          f"apps/040_hello_workflow.py step_02 --force"
        elif selected_template == 'trifecta':
            # Trifecta workflow commands - use template-specific display name
            trifecta_display_name = "Kung Fu Trifecta 🏇"
            combined_cmd = f"python helpers/workflow/create_workflow.py {apps_filename} {class_name} {internal_name} " + \
                          f"{self.format_bash_command(trifecta_display_name)} " + \
                          f"{self.format_bash_command(endpoint_message)} " + \
                          f"{self.format_bash_command(training_prompt)} --template trifecta --role Core --force && " + \
                          f"python helpers/workflow/splice_workflow_step.py {apps_filename} --position bottom"
        else:
            # Blank template - use template-specific display name
            blank_display_name = "Kung Fu Placeholder 🥋"
            combined_cmd = f"python helpers/workflow/create_workflow.py {apps_filename} {class_name} {internal_name} " + \
                          f"{self.format_bash_command(blank_display_name)} " + \
                          f"{self.format_bash_command(endpoint_message)} " + \
                          f"{self.format_bash_command(training_prompt)} --template blank --role Core --force"

        # Execute the command sequence
        import subprocess
        import os

        execution_output = ""
        execution_success = False

        try:
            # Import functions from server for critical operation management
            from server import is_critical_operation_in_progress, set_critical_operation_flag, clear_critical_operation_flag

            # Check if another critical operation is in progress
            if is_critical_operation_in_progress():
                await self.message_queue.add(wand, "⚠️ Another critical operation is in progress. Please wait and try again.", verbatim=True)
                execution_output = "❌ Another critical operation was already in progress."
                execution_success = False
            else:
                await self.message_queue.add(wand, "🔄 Executing workflow creation commands...", verbatim=True)

                # Set flag to prevent watchdog restarts during subprocess execution
                logger.info("[WORKFLOW_GENESIS] Starting critical subprocess operation. Pausing Watchdog restarts.")
                set_critical_operation_flag()

                try:
                    # Change to project root directory for command execution
                    original_cwd = os.getcwd()

                    # Log the command being executed
                    logger.info(f"[WORKFLOW_GENESIS] Executing subprocess command: {combined_cmd}")

                    # Execute the combined command with shell=True since we have && chains
                    result = subprocess.run(
                        combined_cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=60,  # 60 second timeout
                        cwd=original_cwd
                    )
                    # Process results only if subprocess actually ran
                    execution_output = f"Command executed:\n{combined_cmd}\n\n"
                    execution_output += f"Exit code: {result.returncode}\n\n"

                    if result.stdout:
                        execution_output += f"Output:\n{result.stdout}\n\n"

                    if result.stderr:
                        execution_output += f"Errors/Warnings:\n{result.stderr}\n\n"

                    if result.returncode == 0:
                        execution_success = True
                        execution_output += "✅ Workflow creation completed successfully!"
                        await self.message_queue.add(wand, f"✅ Created {display_filename} successfully!", verbatim=True)
                        await self.message_queue.add(wand, "🔄 Server restart will be triggered after command completion...", verbatim=True)
                    else:
                        execution_output += f"❌ Command failed with exit code {result.returncode}"
                        await self.message_queue.add(wand, f"❌ Command execution failed with exit code {result.returncode}", verbatim=True)

                finally:
                    # Always reset the flag, even if subprocess fails
                    logger.info("[WORKFLOW_GENESIS] Critical subprocess operation finished. Resuming Watchdog restarts.")
                    clear_critical_operation_flag()

                    # Trigger restart now that the critical operation is complete
                    if execution_success:
                        logger.info("[WORKFLOW_GENESIS] Triggering server restart after successful workflow creation.")
                        from server import restart_server
                        restart_server()

        except subprocess.TimeoutExpired:
            execution_output = f"❌ Command timed out after 60 seconds:\n{combined_cmd}"
            await self.message_queue.add(wand, "❌ Command execution timed out", verbatim=True)
            # Reset flag on timeout
            clear_critical_operation_flag()
        except Exception as e:
            execution_output = f"❌ Error executing command:\n{str(e)}\n\nCommand was:\n{combined_cmd}"
            await self.message_queue.add(wand, f"❌ Error executing command: {str(e)}", verbatim=True)
            # Reset flag on error
            clear_critical_operation_flag()

        # Create filesystem button to open plugins directory
        apps_dir = os.path.join(os.getcwd(), 'apps')

        open_apps_folder_ui = A(
            "📂 View Plugins Folder",
            href="#",
            hx_get="/open-folder?path=" + urllib.parse.quote(apps_dir),
            hx_swap="none",
            title=f"Open folder: {apps_dir}",
            role="button",
            cls="outline contrast",
            style="margin-right: 10px;"
        )

        # Store detailed execution results
        execution_summary = f"Workflow Creation Execution Report\n\n"
        execution_summary += f"📄 Target File: {display_filename}\n"
        execution_summary += f"🎯 Workflow Name: {display_name}\n"
        execution_summary += f"📂 Location: {apps_dir}\n"
        execution_summary += f"✅ Success: {'Yes' if execution_success else 'No'}\n\n"
        execution_summary += execution_output

        await wand.set_step_data(pipeline_id, step_id, execution_summary, self.steps)
        await self.message_queue.add(wand, self.step_messages[step_id]['complete'], verbatim=True)

        if execution_success:
            # Parse current pipeline key to show next key guidance
            parsed_key = wand.parse_pipeline_key(pipeline_id)
            current_number = int(parsed_key.get('run_part', '01'))
            next_number = current_number + 1
            next_key = f"{parsed_key['profile_part']}-{parsed_key['plugin_part']}-{next_number:02d}"
            previous_key = f"{parsed_key['profile_part']}-{parsed_key['plugin_part']}-{current_number:02d}"

            success_widget = Div(
                P(f"✅ Workflow file created: {display_filename}", cls='text-success', style="margin-bottom: 1rem;"),

                Div(
                    H5("📁 File Location:", style="color: #28a745; margin-bottom: 0.5rem;"),
                    P(f"Created in: {apps_dir}", cls="text-description"),
                    open_apps_folder_ui,
                    style="background-color: rgba(40, 167, 69, 0.1); padding: 1rem; border-radius: 4px; border-left: 4px solid #28a745; margin-bottom: 1rem;"
                ),

                Div(
                    H5("🔄 After Server Restart:", style="color: #ffc107; margin-bottom: 0.5rem;"),
                    Ul(
                        Li("This page will auto-refresh (watchdog file change detection)"),
                        Li(f"The KEY field will show: {next_key}"),
                        Li(f"To return here, change it to: {previous_key} and hit Enter"),
                        Li(f"Look for '{display_name}' in the APP menu"),
                        style="color: #6c757d; margin-bottom: 0;"
                    ),
                    style="background-color: rgba(255, 193, 7, 0.1); padding: 1rem; border-radius: 4px; border-left: 4px solid #ffc107; margin-bottom: 1rem;"
                ),

                Div(
                    H5("🎯 Next Steps:", style="color: #17a2b8; margin-bottom: 0.5rem;"),
                    Ul(
                        Li("Wait for server restart (automatic, ~5-10 seconds)"),
                        Li("Check console window for any import warnings if workflow doesn't appear"),
                        Li("Your new workflow is ready to use!"),
                        style="color: #6c757d; margin-bottom: 0;"
                    ),
                    style="background-color: rgba(23, 162, 184, 0.1); padding: 1rem; border-radius: 4px; border-left: 4px solid #17a2b8;"
                )
            )
        else:
            # Failure widget with execution details
            success_widget = Div(
                P(f"❌ Workflow creation failed", cls='text-danger', style="margin-bottom: 1rem;"),

                Div(
                    H5("🔍 Execution Details:", style="color: #dc3545; margin-bottom: 0.5rem;"),
                    Pre(execution_output, style="background-color: #2d3748; color: #e2e8f0; padding: 1rem; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; font-size: 0.85rem;"),
                    style="background-color: rgba(220, 53, 69, 0.1); padding: 1rem; border-radius: 4px; border-left: 4px solid #dc3545; margin-bottom: 1rem;"
                ),

                Div(
                    H5("📁 Project Location:", style="color: #6c757d; margin-bottom: 0.5rem;"),
                    P(f"Check: {apps_dir}", cls="text-description"),
                    open_apps_folder_ui,
                    style="background-color: rgba(108, 117, 125, 0.1); padding: 1rem; border-radius: 4px; border-left: 4px solid #6c757d;"
                )
            )

        return Div(
            wand.display_revert_widget(
                step_id=step_id,
                app_name=app_name,
                message="🚀 Workflow Creation Executed!" if execution_success else "❌ Workflow Creation Failed",
                widget=success_widget,
                steps=self.steps
            ),
            Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
            id=step_id
        )

    # --- STEP_METHODS_INSERTION_POINT ---