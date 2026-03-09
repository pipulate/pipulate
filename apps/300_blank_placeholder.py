# File: apps/300_blank_placeholder.py
import asyncio
from datetime import datetime
from fasthtml.common import * # type: ignore
from loguru import logger
import inspect
from pathlib import Path
import re
from imports.crud import Step  # 🎯 STANDARDIZED: Import centralized Step definition

ROLES = ['Developer'] # Defines which user roles can see this plugin

# 🎯 STEP DEFINITION: Now imported from imports.crud.py (eliminates 34+ duplications)

class BlankPlaceholder:
    """
    Blank Placeholder Workflow
    A minimal template for creating new Pipulate workflows.
    It includes one placeholder step and the necessary structure for expansion.
    """
    APP_NAME = 'blank_template'
    DISPLAY_NAME = 'Blank Placeholder ✏️'
    ENDPOINT_MESSAGE = 'Welcome to the Blank Placeholder. This is a starting point for your new workflow.'
    TRAINING_PROMPT = 'This is a minimal workflow template. It has one placeholder step. The user will customize it.'

    # --- START_CLASS_ATTRIBUTES_BUNDLE ---
    # Additional class-level constants can be merged here by manage_class_attributes.py
    # --- END_CLASS_ATTRIBUTES_BUNDLE ---

    def __init__(self, app, pipulate, pipeline, db, app_name=None):
        self.pipulate = pipulate
        self.app = app
        self.app_name = self.APP_NAME
        self.pipulate = pipulate
        self.pipeline = pipeline
        wand = self.pipulate
        wand = self.pipulate
        self.message_queue = wand.get_message_queue()

        # Access centralized UI constants through dependency injection
        self.ui = wand.get_ui_constants()

        # self.steps includes all data steps AND the system 'finalize' step at the end.
        # splice_workflow_step.py inserts new data steps BEFORE STEPS_LIST_INSERTION_POINT.
        self.steps = [
            Step(id='step_01', done='placeholder_data_01', show='Step 1 Placeholder', refill=False),
            # --- STEPS_LIST_INSERTION_POINT ---
            Step(id='finalize', done='finalized', show='Finalize Workflow', refill=False)
        ]
        self.steps_indices = {step_obj.id: i for i, step_obj in enumerate(self.steps)}

        # Use centralized route registration helper
        pipulate.register_workflow_routes(self)

        self.step_messages = {}
        for step_obj in self.steps:
            if step_obj.id == 'finalize':
                self.step_messages['finalize'] = {
                    'ready': self.ui['MESSAGES']['ALL_STEPS_COMPLETE'],
                    'complete': f'Workflow finalized. Use {self.ui["BUTTON_LABELS"]["UNLOCK"]} to make changes.'
                }
            else:
                self.step_messages[step_obj.id] = {
                    'input': f'{step_obj.show}: Click Done to proceed.',
                    'complete': f'{step_obj.show} is complete. Proceed to the next action.'
                }

    async def landing(self, request):
        """Generate the landing page using the standardized helper while maintaining WET explicitness."""
        wand = self.pipulate

        # Use centralized landing page helper - maintains WET principle by explicit call
        return wand.create_standard_landing_page(self)

    async def init(self, request):
        """ Handles the key submission, initializes state, and renders the step UI placeholders. """
        wand, db, steps, app_name = (self.pipulate, self.pipulate.db, self.steps, self.APP_NAME)
        form = await request.form()
        user_input = form.get('pipeline_id', '').strip()
        if not user_input:
            from starlette.responses import Response
            response = Response('')
            response.headers['HX-Refresh'] = 'true'
            return response
        context = wand.get_plugin_context(self)
        plugin_name = app_name  # Use app_name directly to ensure consistency
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
        logger.debug(f'Using pipeline ID: {pipeline_id}')
        state, error = wand.initialize_if_missing(pipeline_id, {'app_name': app_name})
        if error:
            return error
        all_steps_complete = all((step.id in state and step.done in state[step.id] for step in steps[:-1]))
        is_finalized = 'finalize' in state and 'finalized' in state['finalize']

        # Progressive feedback with emoji conventions
        await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["WORKFLOW"]} Workflow ID: {pipeline_id}', verbatim=True, spaces_before=0)
        await self.message_queue.add(wand, f"{self.ui["EMOJIS"]["KEY"]} Return later by selecting '{pipeline_id}' from the dropdown.", verbatim=True, spaces_before=0)

        if all_steps_complete:
            if is_finalized:
                status_msg = f'{self.ui["EMOJIS"]["LOCKED"]} Workflow is complete and finalized. Use {self.ui["BUTTON_LABELS"]["UNLOCK"]} to make changes.'
            else:
                status_msg = f'{self.ui["EMOJIS"]["SUCCESS"]} Workflow is complete but not finalized. Press Finalize to lock your data.'
            await self.message_queue.add(wand, status_msg, verbatim=True)
        elif not any((step.id in state for step in self.steps)):
            await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["INPUT_FORM"]} Please complete each step in sequence. Your progress will be saved automatically.', verbatim=True)

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
        # Use self.steps as it's the definitive list including 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')

        finalize_step_obj = next(s for s in self.steps if s.id == 'finalize')
        finalize_data = wand.get_step_data(pipeline_id, finalize_step_obj.id, {})

        if request.method == 'GET':
            if finalize_step_obj.done in finalize_data:
                return Card(
                    H3(self.ui['MESSAGES']['WORKFLOW_LOCKED'], id="workflow-locked-heading"), 
                    Form(
                        Button(
                            self.ui['BUTTON_LABELS']['UNLOCK'], 
                            type='submit', 
                            name='unlock_action',
                            cls=self.ui['BUTTON_STYLES']['OUTLINE'],
                            id="finalize-unlock-button",
                            aria_label="Unlock workflow to make changes",
                            data_testid="unlock-workflow-button"
                        ), 
                        hx_post=f'/{app_name}/unfinalize', 
                        hx_target=f'#{app_name}-container',
                        aria_label="Form to unlock finalized workflow",
                        aria_labelledby="finalize-unlock-button",
                        role="form",
                        data_testid="unlock-form"
                    ), 
                    id=finalize_step_obj.id,
                    data_testid="finalized-workflow-card"
                )
            else:
                # Check if all data steps (all steps in self.steps *before* 'finalize') are complete
                all_data_steps_complete = all(wand.get_step_data(pipeline_id, step.id, {}).get(step.done) for step in self.steps if step.id != 'finalize')
                if all_data_steps_complete:
                    return Card(
                        H3(self.ui['MESSAGES']['FINALIZE_QUESTION'], id="finalize-question-heading"), 
                        P(self.ui['MESSAGES']['FINALIZE_HELP'], cls='text-secondary', id="finalize-help-text"), 
                        Form(
                            Button(
                                self.ui['BUTTON_LABELS']['FINALIZE'], 
                                type='submit',
                                name='finalize_action', 
                                cls=self.ui['BUTTON_STYLES']['PRIMARY'],
                                id="finalize-submit-button",
                                aria_label="Finalize workflow and lock data",
                                data_testid="finalize-workflow-button"
                            ), 
                            hx_post=f'/{app_name}/finalize', 
                            hx_target=f'#{app_name}-container',
                            aria_label="Form to finalize workflow",
                            aria_labelledby="finalize-question-heading",
                            aria_describedby="finalize-help-text",
                            role="form",
                            data_testid="finalize-form"
                        ), 
                        id=finalize_step_obj.id,
                        data_testid="ready-to-finalize-card"
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
        wand, db, current_steps = self.pipulate, self.pipulate.db, self.steps
        step_obj = next((s for s in current_steps if s.id == step_id), None)
        if not step_obj or not step_obj.transform: return ''

        current_step_index = self.steps_indices.get(step_id)
        if current_step_index is None or current_step_index == 0: return ''

        prev_step_obj = current_steps[current_step_index - 1]
        prev_data = wand.get_step_data(db.get('pipeline_id', 'unknown'), prev_step_obj.id, {})
        prev_value = prev_data.get(prev_step_obj.done, '')

        return step_obj.transform(prev_value) if prev_value and callable(step_obj.transform) else ''

    async def handle_revert(self, request):
        wand, db, app_name = (self.pipulate, self.pipulate.db, self.APP_NAME)
        current_steps_to_pass_helpers = self.steps # Use self.steps which includes 'finalize'
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

    # --- START_STEP_BUNDLE: step_01 ---
    async def step_01(self, request):
        """Handles GET request for Step 1 Placeholder."""
        wand, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, self.APP_NAME
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        # Determine next_step_id dynamically based on runtime position in steps list
        next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        current_value = step_data.get(step.done, "") # 'step.done' will be like 'placeholder_data_01'
        finalize_data = wand.get_step_data(pipeline_id, "finalize", {})

        if "finalized" in finalize_data and current_value:
            wand.append_to_history(f"[WIDGET CONTENT] {step.show} (Finalized):\\n{current_value}")
            return Div(
                Card(H3(f"🔒 {step.show}: Completed")),
                Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
                id=step_id
            )
        elif current_value and state.get("_revert_target") != step_id:
            wand.append_to_history(f"[WIDGET CONTENT] {step.show} (Completed):\\n{current_value}")
            return Div(
                wand.display_revert_header(step_id=step_id, app_name=app_name, message=f"{step.show}: Complete", steps=steps),
                Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
                id=step_id
            )
        else:
            wand.append_to_history(f"[WIDGET STATE] {step.show}: Showing input form")
            await self.message_queue.add(wand, self.step_messages[step_id]["input"], verbatim=True)
            return Div(
                Card(
                    H3(f"{step.show}", id=f"{step_id}-heading", aria_level="3"),
                    P("This is a placeholder step. Click Done to proceed.", 
                      id=f"{step_id}-description",
                      role="note"),
                    Form(
                        # Minimal placeholder: just a Done button - customize as needed
                        Button(
                            "Done", 
                            type="submit",
                            name=step.done,
                            value="completed",
                            cls=self.ui['BUTTON_STYLES']['PRIMARY'],
                            id=f"{step_id}-done-button",
                            data_testid=f"done-button-{step_id}"
                        ),
                        hx_post=f"/{app_name}/{step_id}_submit", 
                        hx_target=f"#{step_id}",
                        aria_label=f"Form for {step.show}",
                        aria_describedby=f"{step_id}-description",
                        aria_labelledby=f"{step_id}-heading",
                        role="form",
                        data_testid=f"step-form-{step_id}"
                    ),
                    data_testid=f"step-card-{step_id}",
                    role="region",
                    aria_labelledby=f"{step_id}-heading"
                ),
                Div(id=next_step_id), # Placeholder for next step, no trigger here
                id=step_id,
                data_testid=f"step-container-{step_id}"
            )

    async def step_01_submit(self, request):
        """Process the submission for Step 1 Placeholder."""
        wand, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, self.APP_NAME
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')

        form_data = await request.form()
        # Minimal placeholder: just mark as completed
        value_to_save = "completed"
        await wand.set_step_data(pipeline_id, step_id, value_to_save, steps)

        wand.append_to_history(f"[WIDGET STATE] {step.show}: Step completed")

        await self.message_queue.add(wand, f"{step.show} complete.", verbatim=True)

        return Div(
            wand.display_revert_header(step_id=step_id, app_name=app_name, message=f"{step.show}: Complete", steps=steps),
            Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
            id=step_id
        )
    # --- END_STEP_BUNDLE: step_01 ---

    # --- STEP_METHODS_INSERTION_POINT ---
