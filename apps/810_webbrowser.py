import asyncio
import json
import webbrowser
from datetime import datetime

from fasthtml.common import *
from loguru import logger
from starlette.responses import HTMLResponse
from imports.crud import Step  # 🎯 STANDARDIZED: Import centralized Step definition

ROLES = ['Components']
'\nPipulate Webbrowser URL Opener Widget Workflow\nA workflow for demonstrating opening a URL in the default system browser.\n'


class WebbrowserUrlOpenerWidget:
    """
    Webbrowser URL Opener Widget Workflow

    Demonstrates opening a URL using Python's webbrowser module.
    """
    APP_NAME = 'webbrowser_url_opener'
    DISPLAY_NAME = 'Webbrowser URL Opener'
    ENDPOINT_MESSAGE = "This workflow demonstrates opening a URL in the default system browser using Python's webbrowser module."
    TRAINING_PROMPT = 'This workflow is for demonstrating and testing the webbrowser URL opener. The user will input a URL, which will then be opened in their default browser.'

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
        steps = [Step(id='step_01', done='url_to_open', show='URL to Open', refill=True, transform=lambda prev_value: prev_value.strip() if prev_value else '')]
        routes = [(f'/{app_name}', self.landing), (f'/{app_name}/init', self.init, ['POST']), (f'/{app_name}/revert', self.handle_revert, ['POST']), (f'/{app_name}/finalize', self.finalize, ['GET', 'POST']), (f'/{app_name}/unfinalize', self.unfinalize, ['POST'])]
        self.steps = steps
        for step in steps:
            step_id = step.id
            routes.append((f'/{app_name}/{step_id}', getattr(self, step_id)))
            routes.append((f'/{app_name}/{step_id}_submit', getattr(self, f'{step_id}_submit'), ['POST']))
        for path, handler, *methods in routes:
            method_list = methods[0] if methods else ['GET']
            app.route(path, methods=method_list)(handler)
        self.step_messages = {'finalize': {'ready': 'All steps complete. Ready to finalize workflow.', 'complete': f'Workflow finalized. Use {wand.UNLOCK_BUTTON_LABEL} to make changes.'}, 'step_01': {'input': 'Please enter the URL to open.', 'complete': 'URL processed.'}}
        steps.append(Step(id='finalize', done='finalized', show='Finalize', refill=False))
        self.steps_indices = {step.id: i for i, step in enumerate(steps)}

    async def landing(self, request):
        """Generate the landing page using the standardized helper while maintaining WET explicitness."""
        wand = self.pipulate

        # Use centralized landing page helper - maintains WET principle by explicit call
        return wand.create_standard_landing_page(self)

    async def init(self, request):
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
            _, temp_prefix, user_provided_id_part = wand.generate_pipeline_key(self, user_input)
            pipeline_id = f'{expected_prefix}{user_provided_id_part}'
        wand.db['pipeline_id'] = pipeline_id
        state, error = wand.initialize_if_missing(pipeline_id, {'app_name': app_name})
        if error:
            return error
        await self.message_queue.add(wand, f'Workflow ID: {pipeline_id}', verbatim=True, spaces_before=0)
        await self.message_queue.add(wand, f"Return later by selecting '{pipeline_id}' from the dropdown.", verbatim=True, spaces_before=0)
        return wand.run_all_cells(app_name, steps)

    async def finalize(self, request):
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        finalize_step = steps[-1]
        finalize_data = wand.get_step_data(pipeline_id, finalize_step.id, {})
        if request.method == 'GET':
            if finalize_step.done in finalize_data:
                return Card(H3('Workflow is locked.'), Form(Button(wand.UNLOCK_BUTTON_LABEL, type='submit', cls='secondary outline'), hx_post=f'/{app_name}/unfinalize', hx_target=f'#{app_name}-container', hx_swap='outerHTML'), id=finalize_step.id)
            else:
                all_steps_complete = all((wand.get_step_data(pipeline_id, step.id, {}).get(step.done) for step in steps[:-1]))
                if all_steps_complete:
                    return Card(H3('All steps complete. Finalize?'), P('You can revert to any step and make changes.', cls='text-secondary'), Form(Button('Finalize 🔒', type='submit', cls='primary'), hx_post=f'/{app_name}/finalize', hx_target=f'#{app_name}-container', hx_swap='outerHTML'), id=finalize_step.id)
                else:
                    return Div(id=finalize_step.id)
        else:
            await wand.finalize_workflow(pipeline_id)
            await self.message_queue.add(wand, self.step_messages['finalize']['complete'], verbatim=True)
            return wand.run_all_cells(app_name, steps)

    async def unfinalize(self, request):
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        await wand.unfinalize_workflow(pipeline_id)
        await self.message_queue.add(wand, 'Workflow unfinalized! You can now revert to any step and make changes.', verbatim=True)
        return wand.run_all_cells(app_name, steps)

    async def get_suggestion(self, step_id, state):
        if step_id == 'step_01':
            return 'https://example.com'
        return ''

    async def handle_revert(self, request):
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        form = await request.form()
        step_id = form.get('step_id')
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        if not step_id:
            return P('Error: No step specified', cls='text-invalid')
        await wand.clear_steps_from(pipeline_id, step_id, steps)
        state = wand.read_state(pipeline_id)
        state['_revert_target'] = step_id
        wand.write_state(pipeline_id, state)
        message = await wand.get_state_message(pipeline_id, steps, self.step_messages)
        await self.message_queue.add(wand, message, verbatim=True)
        return wand.run_all_cells(app_name, steps)

    def _create_url_display(self, url_value):
        """Helper method to create the display for the URL and reopen button."""
        return Div(P(f'URL configured: ', B(url_value)), Button('Open URL Again ▸', type='button', _onclick=f"window.open('{url_value}', '_blank')", cls='secondary'))

    async def step_01(self, request):
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        user_val = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and user_val:
            url_widget_display = self._create_url_display(user_val)
            return Div(Card(H3(f'🔒 {step.show}'), url_widget_display), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        elif user_val and state.get('_revert_target') != step_id:
            url_widget_display = self._create_url_display(user_val)
            content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: {user_val}', widget=url_widget_display, steps=steps)
            return Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        else:
            display_value = user_val if step.refill and user_val else await self.get_suggestion(step_id, state)
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
            explanation = 'Enter a URL to open in your default browser (e.g., https://example.com).'
            await self.message_queue.add(wand, explanation, verbatim=True)
            return Div(Card(H3(f'{wand.fmt(step_id)}: Configure {step.show}'), P(explanation, cls='text-secondary'), Form(Div(Input(type='url', name=step.done, placeholder='https://example.com', required=True, value=display_value, cls='contrast'), Div(Button('Open URL ▸', type='submit', cls='primary'), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_01_submit(self, request):
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form = await request.form()
        url_to_open = form.get(step.done, '').strip()
        if not url_to_open:
            return P('Error: URL is required', cls='text-invalid')
        if not url_to_open.startswith(('http://', 'https://')):
            url_to_open = f'https://{url_to_open}'
        await wand.set_step_data(pipeline_id, step_id, url_to_open, steps)
        try:
            webbrowser.open(url_to_open)
            await self.message_queue.add(wand, f'Attempting to open URL: {url_to_open}', verbatim=True)
        except Exception as e:
            error_msg = f'Error opening URL with webbrowser: {str(e)}'
            logger.error(error_msg)
            await self.message_queue.add(wand, error_msg, verbatim=True)
            error_widget = P(error_msg, cls='text-invalid')
            url_widget_display_on_error = self._create_url_display(url_to_open)
            content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Error Opening URL', widget=Div(error_widget, url_widget_display_on_error), steps=steps)
            return Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        wand.append_to_history(f'[WIDGET ACTION] {step.show}: Opened URL {url_to_open}')
        url_widget_display = self._create_url_display(url_to_open)
        content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: URL opened - {url_to_open}', widget=url_widget_display, steps=steps)
        response_content = Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        await self.message_queue.add(wand, f'{step.show} complete. URL opened.', verbatim=True)
        if wand.check_finalize_needed(step_index, steps):
            await self.message_queue.add(wand, self.step_messages['finalize']['ready'], verbatim=True)
        return HTMLResponse(to_xml(response_content))
