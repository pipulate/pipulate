# File: apps/830_pico_slider.py
import asyncio
from datetime import datetime
from fasthtml.common import * # type: ignore
from loguru import logger
import inspect
from pathlib import Path
import re
from imports.crud import Step  

ROLES = ['Developer'] 

class SliderPlaceholder:
    """
    Slider Placeholder Workflow
    A functional Moviola template using HTMX to scrub through simulated Git diffs.
    """
    APP_NAME = 'git_slider'
    DISPLAY_NAME = 'Git Slider 🎚'
    ENDPOINT_MESSAGE = 'Welcome to the Git Slider. Select a file, then drag the slider to scrub through its commit history.'
    TRAINING_PROMPT = 'This workflow uses HTMX and a range input to scrub through the real git history of any tracked file in the repository.'

    def __init__(self, app, pipulate, pipeline, db, app_name=None):
        self.pipulate = pipulate
        self.app = app
        self.app_name = self.APP_NAME
        self.pipulate = pipulate
        self.pipeline = pipeline
        wand = self.pipulate
        self.message_queue = wand.get_message_queue()
        self.ui = wand.get_ui_constants()

        self.steps = [
            Step(
                id='step_02',
                done='placeholder_02',
                show='Placeholder Step 2 (Edit Me)',
                refill=True,
            ),
            Step(id='step_01', done='timeline_index', show='Timeline Scrubber', refill=False),
            Step(id='finalize', done='finalized', show='Finalize Workflow', refill=False)
        ]
        self.steps_indices = {step_obj.id: i for i, step_obj in enumerate(self.steps)}

        # Register standard routes
        pipulate.register_workflow_routes(self)

        # 🎯 CUSTOM ROUTE INJECTION: Register the HTMX scrubbing endpoint
        self.app.route(f'/{self.app_name}/scrub_timeline', methods=['POST'])(self.scrub_timeline)

        self.step_messages = {}
        for step_obj in self.steps:
            if step_obj.id == 'finalize':
                self.step_messages['finalize'] = {
                    'ready': self.ui['MESSAGES']['ALL_STEPS_COMPLETE'],
                    'complete': f'Workflow finalized. Use {self.ui["BUTTON_LABELS"]["UNLOCK"]} to make changes.'
                }
            else:
                self.step_messages[step_obj.id] = {
                    'input': f'{step_obj.show}: Drag the slider to scrub through history.',
                    'complete': f'{step_obj.show} is complete. Proceed to the next action.'
                }

    async def landing(self, request):
        wand = self.pipulate
        return wand.create_standard_landing_page(self)

    async def init(self, request):
        wand, db, steps, app_name = (self.pipulate, self.pipulate.db, self.steps, self.APP_NAME)
        form = await request.form()
        user_input = form.get('pipeline_id', '').strip()
        if not user_input:
            from starlette.responses import Response
            response = Response('')
            response.headers['HX-Refresh'] = 'true'
            return response
        context = wand.get_plugin_context(self)
        plugin_name = app_name  
        profile_name = context['profile_name'] or 'default'
        profile_part = profile_name.replace(' ', '_')
        plugin_part = plugin_name.replace(' ', '_')
        expected_prefix = f'{profile_part}-{plugin_part}-'
        if user_input.startswith(expected_prefix):
            pipeline_id = user_input
        else:
            _, prefix, user_provided_id = wand.generate_pipeline_key(self, user_input)
            pipeline_id = f'{prefix}{user_provided_id}'
        wand.db['pipeline_id'] = pipeline_id
        state, error = wand.initialize_if_missing(pipeline_id, {'app_name': app_name})
        if error:
            return error
        all_steps_complete = all((step.id in state and step.done in state[step.id] for step in steps[:-1]))
        is_finalized = 'finalize' in state and 'finalized' in state['finalize']

        await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["WORKFLOW"]} Workflow ID: {pipeline_id}', verbatim=True, spaces_before=0)

        if all_steps_complete:
            if is_finalized:
                status_msg = f'{self.ui["EMOJIS"]["LOCKED"]} Workflow is complete and finalized. Use {self.ui["BUTTON_LABELS"]["UNLOCK"]} to make changes.'
            else:
                status_msg = f'{self.ui["EMOJIS"]["SUCCESS"]} Workflow is complete but not finalized. Press Finalize to lock your data.'
            await self.message_queue.add(wand, status_msg, verbatim=True)
        elif not any((step.id in state for step in self.steps)):
            await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["INPUT_FORM"]} Use the slider to explore the timeline.', verbatim=True)

        parsed = wand.parse_pipeline_key(pipeline_id)
        prefix = f"{parsed['profile_part']}-{parsed['plugin_part']}-"
        self.pipeline.xtra(app_name=app_name)
        matching_records = [record.pkey for record in self.pipeline() if record.pkey.startswith(prefix)]
        if pipeline_id not in matching_records:
            matching_records.append(pipeline_id)
        updated_datalist = wand.update_datalist('pipeline-ids', options=matching_records)
        return wand.run_all_cells(app_name, steps)

    async def finalize(self, request):
        wand, db, app_name = self.pipulate, self.pipulate.db, self.APP_NAME
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        finalize_step_obj = next(s for s in self.steps if s.id == 'finalize')
        finalize_data = wand.get_step_data(pipeline_id, finalize_step_obj.id, {})

        if request.method == 'GET':
            if finalize_step_obj.done in finalize_data:
                return Card(
                    H3(self.ui['MESSAGES']['WORKFLOW_LOCKED'], id="workflow-locked-heading"), 
                    Form(
                        Button(self.ui['BUTTON_LABELS']['UNLOCK'], type='submit', name='unlock_action', cls=self.ui['BUTTON_STYLES']['OUTLINE']), 
                        hx_post=f'/{app_name}/unfinalize', 
                        hx_target=f'#{app_name}-container'
                    ), 
                    id=finalize_step_obj.id
                )
            else:
                all_data_steps_complete = all(wand.get_step_data(pipeline_id, step.id, {}).get(step.done) for step in self.steps if step.id != 'finalize')
                if all_data_steps_complete:
                    return Card(
                        H3(self.ui['MESSAGES']['FINALIZE_QUESTION']), 
                        P(self.ui['MESSAGES']['FINALIZE_HELP'], cls='text-secondary'), 
                        Form(
                            Button(self.ui['BUTTON_LABELS']['FINALIZE'], type='submit', name='finalize_action', cls=self.ui['BUTTON_STYLES']['PRIMARY']), 
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
        await self.message_queue.add(wand, self.ui['MESSAGES']['WORKFLOW_UNLOCKED'], verbatim=True)
        return wand.run_all_cells(app_name, self.steps)

    async def get_suggestion(self, step_id, state):
        return ''

    async def handle_revert(self, request):
        wand, db, app_name = (self.pipulate, self.pipulate.db, self.APP_NAME)
        current_steps_to_pass_helpers = self.steps 
        form = await request.form()
        step_id_to_revert_to = form.get('step_id')
        pipeline_id = wand.db.get('pipeline_id', 'unknown')

        if not step_id_to_revert_to:
            return P('Error: No step specified for revert.', cls='text-invalid')

        await wand.clear_steps_from(pipeline_id, step_id_to_revert_to, current_steps_to_pass_helpers)
        state = wand.read_state(pipeline_id)
        state['_revert_target'] = step_id_to_revert_to
        wand.write_state(pipeline_id, state)

        message = await wand.get_state_message(pipeline_id, current_steps_to_pass_helpers, self.step_messages)
        await self.message_queue.add(wand, message, verbatim=True)
        return wand.run_all_cells(app_name, current_steps_to_pass_helpers)

    # 🎯 CUSTOM ENDPOINT: HTMX dynamic scrubbing logic
    async def scrub_timeline(self, request):
        """Intercepts the slider input event and returns the real git diff payload dynamically."""
        form_data = await request.form()
        index = int(form_data.get('timeline_index', 0))
        target_file = form_data.get('target_file', 'foo_files.py')
        
        import subprocess
        
        try:
            # Get the list of commits for this file (reverse chronological so 0 is oldest)
            log_cmd = ['git', 'log', '--reverse', '--pretty=format:%H|%s', '--', target_file]
            log_result = subprocess.run(log_cmd, capture_output=True, text=True, check=True)
            commits = [line for line in log_result.stdout.split('\n') if line]

            if not commits or index < 0 or index >= len(commits):
                return Pre(Code(f"No history found or index out of bounds for {target_file}."))

            commit_hash, commit_msg = commits[index].split('|', 1)

            # Get the specific diff for this file at this commit
            diff_cmd = ['git', 'show', '--color=never', commit_hash, '--', target_file]
            diff_result = subprocess.run(diff_cmd, capture_output=True, text=True)

            # The raw text of the diff (No manual HTML escaping or span wrapping needed!)
            diff_text = f"Commit:  {commit_hash}\nMessage: {commit_msg}\n\n{diff_result.stdout}"

        except Exception as e:
            diff_text = f"Error fetching git history: {str(e)}"

        # HTMX Lifecycle Fix: Return the raw text wrapped in Prism's 'language-diff' class, 
        # AND append a <script> tag to manually re-trigger Prism on the newly injected DOM.
        return (
            Pre(Code(diff_text, cls="language-diff")),
            Script("if (typeof Prism !== 'undefined') { Prism.highlightAllUnder(document.getElementById('diff-viewport')); }")
        )

    # --- START_STEP_BUNDLE: step_01 ---
    async def step_01(self, request):
        wand, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, self.APP_NAME
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        current_value = step_data.get(step.done, "") 
        finalize_data = wand.get_step_data(pipeline_id, "finalize", {})

        if "finalized" in finalize_data and current_value:
            return Div(
                Card(H3(f"🔒 {step.show}: Completed")),
                Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
                id=step_id
            )
        elif current_value and state.get("_revert_target") != step_id:
            return Div(
                wand.display_revert_header(step_id=step_id, app_name=app_name, message=f"{step.show}: Complete", steps=steps),
                Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
                id=step_id
            )
        else:
            # 1. Retrieve the file chosen in step_02
            step_02_data = wand.get_step_data(pipeline_id, 'step_02', {})
            target_file = step_02_data.get('placeholder_02', 'foo_files.py')

            # 2. Count the commits for this file to set the slider max
            import subprocess
            num_commits = 0
            try:
                log_result = subprocess.run(['git', 'log', '--oneline', '--', target_file], capture_output=True, text=True)
                num_commits = len([line for line in log_result.stdout.split('\n') if line])
            except Exception:
                pass

            slider_max = str(max(0, num_commits - 1))

            # The Range Input linked to HTMX via 'input' event with a 50ms throttle
            range_slider = Input(
                type="range",
                name="timeline_index",
                min="0",
                max=slider_max,
                value="0",
                hx_post=f"/{app_name}/scrub_timeline",
                hx_target="#diff-viewport",
                hx_trigger="input delay:50ms"  
            )

            # Pass the target file to the endpoint implicitly via hidden input
            hidden_target = Input(type="hidden", name="target_file", value=target_file)

            # The Viewport that HTMX will dynamically swap content into
            diff_viewport = Div(
                Pre(Code(f"Loaded {num_commits} commits for {target_file}. Drag slider to begin scrubbing.", cls="language-diff")),
                id="diff-viewport",
                style="margin-top: 1rem; background: var(--pico-code-background-color); padding: 1rem; border-radius: var(--pico-border-radius); max-height: 60vh; overflow-y: auto;"
            )

            return Div(
                Card(
                    H3(f"Scrubbing: {target_file}"),
                    P("Drag the slider to physically scrub the timeline of the repository.", cls="text-secondary"),
                    Form(
                        hidden_target,
                        range_slider,
                        diff_viewport,
                        Br(),
                        Button("Lock Selection & Proceed", type="submit", name=step.done, value="completed", cls=self.ui['BUTTON_STYLES']['PRIMARY']),
                        hx_post=f"/{app_name}/{step_id}_submit", 
                        hx_target=f"#{step_id}",
                    ),
                ),
                Div(id=next_step_id), 
                id=step_id
            )

    async def step_01_submit(self, request):
        wand, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, self.APP_NAME
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')

        form_data = await request.form()
        selected_index = form_data.get('timeline_index', '0')
        value_to_save = f"Locked at commit index {selected_index}"
        
        await wand.set_step_data(pipeline_id, step_id, value_to_save, steps)
        wand.append_to_history(f"[WIDGET STATE] {step.show}: Step completed")
        await self.message_queue.add(wand, f"{step.show} complete.", verbatim=True)

        return Div(
            wand.display_revert_header(step_id=step_id, app_name=app_name, message=f"{step.show}: {value_to_save}", steps=steps),
            Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
            id=step_id
        )
# --- END_STEP_BUNDLE: step_01 ---

# --- START_STEP_BUNDLE: step_02 ---
    async def step_02(self, request):
        """Handles GET request for the Git File Selector."""
        pip, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, self.app_name
        step_id = "step_02"
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
        pipeline_id = db.get("pipeline_id", "unknown")
        state = pip.read_state(pipeline_id)
        step_data = pip.get_step_data(pipeline_id, step_id, {})
        current_value = step_data.get(step.done, "")
        finalize_data = pip.get_step_data(pipeline_id, "finalize", {})
    
        if "finalized" in finalize_data and current_value:
            return Div(Card(H3(f"🔒 {step.show}: Completed")), Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"), id=step_id)
        elif current_value and state.get("_revert_target") != step_id:
            return Div(pip.display_revert_header(step_id=step_id, app_name=app_name, message=f"Selected Target: {current_value}", steps=steps), Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"), id=step_id)
        else:
            # 80/20 Rule: Ask Git for tracked files
            import subprocess
            try:
                result = subprocess.run(['git', 'ls-files'], capture_output=True, text=True, check=True)
                tracked_files = [f for f in result.stdout.split('\n') if f.strip() and f.endswith(('.py', '.md', '.nix', '.json', '.html'))]
            except Exception:
                tracked_files = ['foo_files.py'] # Safe fallback
                
            # 🎯 THE REVERT MEMORY FIX: 
            # If current_value exists (from a revert), use it. Otherwise, default to foo_files.py
            target_selection = current_value if (step.refill and current_value) else 'foo_files.py'
            options = [Option(f, value=f, selected=(f == target_selection)) for f in tracked_files]

            return Div(
                Card(
                    H3("Select Target File"),
                    P("Select a file from the repository to scrub its Git history.", cls="text-secondary"),
                    Form(
                        Select(*options, name=step.done, required=True),
                        Button("Load Timeline ▸", type="submit", cls="primary"),
                        hx_post=f"/{app_name}/{step_id}_submit", hx_target=f"#{step_id}"
                    )
                ),
                Div(id=next_step_id), 
                id=step_id
            )

    async def step_02_submit(self, request):
        """Process the submission for the File Selector."""
        pip, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, self.app_name
        step_id = "step_02"
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
        pipeline_id = db.get("pipeline_id", "unknown")
        
        form_data = await request.form()
        value_to_save = form_data.get(step.done, "foo_files.py") 
        await pip.set_step_data(pipeline_id, step_id, value_to_save, steps)
        
        return Div(
            pip.display_revert_header(step_id=step_id, app_name=app_name, message=f"Selected Target: {value_to_save}", steps=steps),
            Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
            id=step_id
        )
    # --- END_STEP_BUNDLE: step_02 ---

    # --- STEP_METHODS_INSERTION_POINT ---
