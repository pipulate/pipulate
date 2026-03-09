import asyncio
from datetime import datetime
from fasthtml.common import *
from loguru import logger  
from imports.crud import Step, VALID_ROLES

ROLES = ['Components']  # See config.AVAILABLE_ROLES for all valid roles

# 📚 Widget conversion guide: helpers/docs_sync/widget_conversion_guide.md


class SwitchWorkflow:
    """
    Switch Workflow

    A focused environment for designing and testing switch/toggle-based interactions in isolation.
    This workflow provides a clean environment to focus on switch development without the complexity
    of a full workflow implementation.
    """
    # Template compatibility markers
    # STEPS_LIST_INSERTION_POINT
    # STEP_METHODS_INSERTION_POINT
    
    # UI Constants for automation testing
    UI_CONSTANTS = {
        'SWITCH_INPUT': 'switch-widget-switch-input',
        'SWITCH_LABEL': 'switch-widget-switch-label',
        'SWITCH_SPAN': 'switch-widget-switch-span',
        'SWITCH_FORM': 'switch-widget-form',
        'FINALIZE_BUTTON': 'switch-widget-finalize-button', 
        'UNLOCK_BUTTON': 'switch-widget-unlock-button',
        'NEXT_BUTTON': 'switch-widget-next-button',
        'REVERT_BUTTON': 'switch-widget-revert-button'
    }

    APP_NAME = 'toggle_widget'
    DISPLAY_NAME = 'Switch Widget'
    ENDPOINT_MESSAGE = 'Welcome to the Switch Widget! This is a focused environment for designing and testing switch/toggle-based interactions in isolation. Use this space to prototype and refine your switch designs without distractions.'
    TRAINING_PROMPT = 'This is a specialized workflow for designing and testing switch interactions in isolation. It provides a clean environment to focus on switch development without the complexity of a full workflow implementation.'
    SWITCH_CONFIG = {'switches': [{'id': 'switch_1', 'label': 'First Switch', 'description': 'This is the first switch', 'default': False}, {'id': 'switch_2', 'label': 'Second Switch', 'description': 'This is the second switch', 'default': False}]}

    def __init__(self, app, pipulate, pipeline, db, app_name=APP_NAME):
        self.pipulate = pipulate
        """Initialize the workflow, define steps, and register routes."""
        self.app = app
        self.app_name = app_name
        self.pipulate = pipulate
        self.pipeline = pipeline
        self.steps_indices = {}
        wand = self.pipulate
        wand = self.pipulate
        self.message_queue = wand.message_queue
        steps = [Step(id='step_01', done='switch_state', show='Switch State', refill=True, transform=lambda prev_value: bool(prev_value) if prev_value is not None else self.SWITCH_CONFIG['switches'][-1]['default'])]
        routes = [(f'/{app_name}', self.landing), (f'/{app_name}/init', self.init, ['POST']), (f'/{app_name}/revert', self.handle_revert, ['POST']), (f'/{app_name}/finalize', self.finalize, ['GET', 'POST']), (f'/{app_name}/unfinalize', self.unfinalize, ['POST'])]
        self.steps = steps
        for step in steps:
            step_id = step.id
            routes.append((f'/{app_name}/{step_id}', getattr(self, step_id)))
            routes.append((f'/{app_name}/{step_id}_submit', getattr(self, f'{step_id}_submit'), ['POST']))
        for path, handler, *methods in routes:
            method_list = methods[0] if methods else ['GET']
            app.route(path, methods=method_list)(handler)
        self.step_messages = {'finalize': {'ready': 'All steps complete. Ready to finalize workflow.', 'complete': f'Workflow finalized. Use {wand.UNLOCK_BUTTON_LABEL} to make changes.'}}
        for step in steps:
            self.step_messages[step.id] = {'input': f'{wand.fmt(step.id)}: Please complete {step.show}.', 'complete': f'{step.show} complete. Continue to next step.'}
        steps.append(Step(id='finalize', done='finalized', show='Finalize', refill=False))
        self.steps_indices = {step.id: i for i, step in enumerate(steps)}

    async def landing(self, request):
        """Generate the landing page using the standardized helper while maintaining WET explicitness."""
        wand = self.pipulate

        # Use centralized landing page helper - maintains WET principle by explicit call
        return wand.create_standard_landing_page(self)

    async def init(self, request):
        """Handles the key submission, initializes state, and renders the step UI placeholders."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        form = await request.form()
        user_input = form.get('pipeline_id', '').strip()
        if not user_input:
            from starlette.responses import Response
            response = Response('')
            response.headers['HX-Refresh'] = 'true'
            return response
        context = wand.get_plugin_context(self)
        profile_name = context['profile_name'] or 'default'
        plugin_name = app_name  # Use app_name directly to ensure consistency
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
        await self.message_queue.add(wand, f'Workflow ID: {pipeline_id}', verbatim=True, spaces_before=0)
        await self.message_queue.add(wand, f"Return later by selecting '{pipeline_id}' from the dropdown.", verbatim=True, spaces_before=0)
        return wand.run_all_cells(app_name, steps)

    async def finalize(self, request):
        """Handles GET request to show Finalize button and POST request to lock the workflow."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        finalize_step = steps[-1]
        finalize_data = wand.get_step_data(pipeline_id, finalize_step.id, {})
        if request.method == 'GET':
            if finalize_step.done in finalize_data:
                return Card(H3('Workflow is locked.'), Form(Button(wand.UNLOCK_BUTTON_LABEL, type='submit', cls='secondary outline', data_testid='switch-widget-unlock-button', aria_label='Unlock switch workflow for editing'), hx_post=f'/{app_name}/unfinalize', hx_target=f'#{app_name}-container'), id=finalize_step.id)
            else:
                all_steps_complete = all((wand.get_step_data(pipeline_id, step.id, {}).get(step.done) for step in steps[:-1]))
                if all_steps_complete:
                    return Card(H3('All steps complete. Finalize?'), P('You can revert to any step and make changes.', cls='text-secondary'), Form(Button('Finalize 🔒', type='submit', cls='primary', data_testid='switch-widget-finalize-button', aria_label='Finalize switch workflow'), hx_post=f'/{app_name}/finalize', hx_target=f'#{app_name}-container'), id=finalize_step.id)
                else:
                    return Div(id=finalize_step.id)
        else:
            await wand.finalize_workflow(pipeline_id)
            await self.message_queue.add(wand, self.step_messages['finalize']['complete'], verbatim=True)
            return wand.run_all_cells(app_name, steps)

    async def unfinalize(self, request):
        """Handles POST request to unlock the workflow."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        await wand.unfinalize_workflow(pipeline_id)
        await self.message_queue.add(wand, 'Workflow unfinalized! You can now revert to any step and make changes.', verbatim=True)
        return wand.run_all_cells(app_name, steps)

    async def get_suggestion(self, step_id, state):
        """Returns a suggestion for the current step based on state."""
        return 'Complete this step to continue.'

    async def handle_revert(self, request):
        """Handles POST request to revert to a previous step."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        form = await request.form()
        step_id = form.get('step_id', '')
        if step_id not in self.steps_indices:
            return P('Error: Invalid step', cls='text-invalid')
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        await wand.clear_steps_from(pipeline_id, step_id, steps)
        state = wand.read_state(pipeline_id)
        state['_revert_target'] = step_id
        wand.write_state(pipeline_id, state)
        return wand.run_all_cells(app_name, steps)

    async def step_01(self, request):
        """Handles GET request for switch configuration step."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.get_step_data(pipeline_id, step_id, {})
        switch_state = state.get(step.done, {})
        wand.append_to_history(f'[WIDGET STATE] {step.show}: Showing input form')
        await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
        switch_inputs = []
        for switch in self.SWITCH_CONFIG['switches']:
            current_state = switch_state.get(switch['id'], switch['default'])
            switch_inputs.append(Div(Label(Input(type='checkbox', role='switch', name=f"switch_{switch['id']}", checked=current_state, cls='contrast', data_testid='switch-widget-switch-input', aria_label=f'Toggle switch for {switch["label"]}'), Span(switch['label'], style='margin-left: 0.5rem;', data_testid='switch-widget-switch-span'), data_testid='switch-widget-switch-label'), cls='mb-4'))
        return Div(Card(H3(f'{wand.fmt(step_id)}: Configure {step.show}'), P('Toggle the switches to configure your settings.'), Form(Div(*switch_inputs, Div(Button('Save Settings ▸', type='submit', cls='primary', data_testid='switch-widget-next-button', aria_label='Save switch settings'), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}', data_testid='switch-widget-form', aria_label='Switch configuration form')), Div(id=next_step_id), id=step_id)

    async def step_01_submit(self, request):
        """Handles POST request for switch configuration step."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form = await request.form()
        switch_state = {}
        for switch in self.SWITCH_CONFIG['switches']:
            switch_state[switch['id']] = form.get(f"switch_{switch['id']}") == 'on'
        await wand.set_step_data(pipeline_id, step_id, switch_state, steps)
        await self.message_queue.add(wand, self.step_messages.get(step_id, {}).get('complete', f'{step.show} complete: {switch_state}'), verbatim=True)
        return Div(wand.display_revert_header(step_id=step_id, app_name=app_name, message=f'{step.show}: Settings saved', steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
