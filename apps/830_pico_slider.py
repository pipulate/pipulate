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
    APP_NAME = 'pico_slider'
    DISPLAY_NAME = 'Pico Slider 🎚'
    ENDPOINT_MESSAGE = 'Welcome to the Pico Slider template. Drag the slider to scrub through the timeline.'
    TRAINING_PROMPT = 'This workflow demonstrates how to use HTMX and a range input to scrub through dynamic server-side state in real time.'

    # Simulated Git History for the prototype
    MOCK_DIFFS = [
        "commit 16a1dd1a83bb90c9\nAuthor: Mike\n\n+ Initialized empty scratchpad.",
        "commit 693a958c2101eaef\nAuthor: Mike\n\n- Initialized empty scratchpad.\n+ Added CHAPTER 1: THE SAFE HARBOR",
        "commit a653227b36310c83\nAuthor: Mike\n\n+ Added CHAPTER 2: THE HERMETIC SEAL",
        "commit b90aee0a687961c0\nAuthor: Mike\n\n- AI_PHOOEY_CHOP = \"\"\"\\\n+ AI_PHOOEY_CHOP = r\"\"\"\\",
        "commit cf7ea0afb4a32966\nAuthor: Mike\n\n+ Finalized Moviola HTMX integration."
    ]

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
        """Intercepts the slider input event and returns the formatted diff payload dynamically."""
        form_data = await request.form()
        index = int(form_data.get('timeline_index', 0))
        
        # Guard clause
        if index < 0 or index >= len(self.MOCK_DIFFS):
            return Pre(Code("Diff out of bounds."))

        diff_text = self.MOCK_DIFFS[index]
        formatted_lines = []

        # Simple semantic coloring for the mock diffs
        for line in diff_text.split('\n'):
            if line.startswith('+'):
                formatted_lines.append(f"<span style='color: var(--pico-color-green-500);'>{line}</span>")
            elif line.startswith('-'):
                formatted_lines.append(f"<span style='color: var(--pico-color-red-500); text-decoration: line-through;'>{line}</span>")
            else:
                formatted_lines.append(line)

        # Return the raw HTML snippet to be swapped into the viewport
        return Pre(Code(NotStr('<br>'.join(formatted_lines))))

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
            wand.append_to_history(f"[WIDGET CONTENT] {step.show} (Finalized):\n{current_value}")
            return Div(
                Card(H3(f"🔒 {step.show}: Completed")),
                Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
                id=step_id
            )
        elif current_value and state.get("_revert_target") != step_id:
            wand.append_to_history(f"[WIDGET CONTENT] {step.show} (Completed):\n{current_value}")
            return Div(
                wand.display_revert_header(step_id=step_id, app_name=app_name, message=f"{step.show}: Complete", steps=steps),
                Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
                id=step_id
            )
        else:
            wand.append_to_history(f"[WIDGET STATE] {step.show}: Showing input form")
            await self.message_queue.add(wand, self.step_messages[step_id]["input"], verbatim=True)
            
            # The Range Input linked to HTMX via 'input' event with a 50ms throttle
            range_slider = Input(
                type="range",
                name="timeline_index",
                min="0",
                max=str(len(self.MOCK_DIFFS) - 1),
                value="0",
                hx_post=f"/{app_name}/scrub_timeline",
                hx_target="#diff-viewport",
                hx_trigger="input delay:50ms"  # The critical delay to prevent server flooding
            )

            # The Viewport that HTMX will dynamically swap content into
            diff_viewport = Div(
                Pre(Code(self.MOCK_DIFFS[0])), # Initial state
                id="diff-viewport",
                style="margin-top: 1rem; background: var(--pico-code-background-color); padding: 1rem; border-radius: var(--pico-border-radius);"
            )

            return Div(
                Card(
                    H3(f"{step.show}", id=f"{step_id}-heading"),
                    P("Drag the slider to physically scrub the timeline of the repository.", cls="text-secondary"),
                    Form(
                        range_slider,
                        diff_viewport,
                        Br(),
                        Button(
                            "Lock Selection & Proceed", 
                            type="submit",
                            name=step.done,
                            value="completed",
                            cls=self.ui['BUTTON_STYLES']['PRIMARY']
                        ),
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