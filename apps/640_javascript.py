import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from fasthtml.common import *
from loguru import logger
from starlette.responses import HTMLResponse
from imports.crud import Step  # 🎯 STANDARDIZED: Import centralized Step definition

ROLES = ['Components']
'\nExecutable JavaScript Widget\n\nThis workflow demonstrates a widget that executes user-provided JavaScript code\nwithin a designated area. The widget allows users to input JavaScript code that\nwill be executed in the browser, with the ability to manipulate a target element\nand re-run the code as needed.\n\nKey Features:\n- Interactive JavaScript execution\n- Re-run capability\n- Safe code execution environment\n- Visual feedback\n'


class JavaScriptWidget:
    """
    Executable JavaScript Widget Workflow

    A focused environment for creating and testing JavaScript execution widgets.
    Users input JavaScript code that will be executed in the browser, with the
    ability to manipulate a target element and re-run the code as needed.
    """
    APP_NAME = 'javascript_widget'
    DISPLAY_NAME = 'Executable JavaScript Widget'
    ENDPOINT_MESSAGE = 'This workflow demonstrates a widget that executes user-provided JavaScript code within a designated area.'
    TRAINING_PROMPT = 'This workflow is for demonstrating and testing the JavaScript execution widget. The user will input JavaScript code, which will then be run in the browser, potentially manipulating a target element.'

    def __init__(self, app, pipulate, pipeline, db, app_name=APP_NAME):
        self.pipulate = pipulate
        """
        Initialize the workflow, define steps, and register routes.
        """
        self.app = app
        self.app_name = app_name
        self.pipulate = pipulate
        self.pipeline = pipeline
        self.steps_indices = {}
        wand = self.pipulate
        wand = self.pipulate
        self.message_queue = wand.message_queue
        steps = [Step(id='step_01', done='js_content', show='JavaScript Code', refill=True, transform=lambda prev_value: prev_value.strip() if prev_value else '')]
        routes = [(f'/{app_name}', self.landing), (f'/{app_name}/init', self.init, ['POST']), (f'/{app_name}/revert', self.handle_revert, ['POST']), (f'/{app_name}/finalize', self.finalize, ['GET', 'POST']), (f'/{app_name}/unfinalize', self.unfinalize, ['POST'])]
        self.steps = steps
        for step in steps:
            step_id = step.id
            routes.append((f'/{app_name}/{step_id}', getattr(self, step_id)))
            routes.append((f'/{app_name}/{step_id}_submit', getattr(self, f'{step_id}_submit'), ['POST']))
        for path, handler, *methods in routes:
            method_list = methods[0] if methods else ['GET']
            app.route(path, methods=method_list)(handler)
        self.step_messages = {'finalize': {'ready': 'All steps complete. Ready to finalize workflow.', 'complete': f'Workflow finalized. Use {wand.UNLOCK_BUTTON_LABEL} to make changes.'}, 'new': 'Please complete each step to explore the JavaScript execution widget.', 'step_01': {'input': 'Please enter JavaScript code to execute.', 'complete': 'JavaScript code processed.'}}
        steps.append(Step(id='finalize', done='finalized', show='Finalize', refill=False))
        self.steps_indices = {step.id: i for i, step in enumerate(steps)}

    async def landing(self, request):
        """Generate the landing page using the standardized helper while maintaining WET explicitness."""
        wand = self.pipulate

        # Use centralized landing page helper - maintains WET principle by explicit call
        return wand.create_standard_landing_page(self)

    async def init(self, request):
        """ Initialize the workflow state and redirect to the first step. """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
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
        await self.message_queue.add(wand, f'Workflow ID: {pipeline_id}', verbatim=True, spaces_before=0)
        await self.message_queue.add(wand, f"Return later by selecting '{pipeline_id}' from the dropdown.", verbatim=True, spaces_before=0)
        if all_steps_complete:
            status_msg = f'Workflow is complete and finalized. Use {wand.UNLOCK_BUTTON_LABEL} to make changes.' if is_finalized else 'Workflow is complete but not finalized. Press Finalize to lock your data.'
            await self.message_queue.add(wand, status_msg, verbatim=True)
        elif not any((step.id in state for step in self.steps)):
            await self.message_queue.add(wand, self.step_messages['new'], verbatim=True)
        parsed = wand.parse_pipeline_key(pipeline_id)
        prefix = f"{parsed['profile_part']}-{parsed['plugin_part']}-"
        self.pipeline.xtra(app_name=app_name)
        matching_records = [record.pkey for record in self.pipeline() if record.pkey.startswith(prefix)]
        if pipeline_id not in matching_records:
            matching_records.append(pipeline_id)
        updated_datalist = wand.update_datalist('pipeline-ids', options=matching_records)
        return wand.run_all_cells(app_name, steps)

    async def finalize(self, request):
        """ Handle GET/POST requests to finalize (lock) the workflow. """
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
        """ Handle POST request to unlock the workflow. """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        await wand.unfinalize_workflow(pipeline_id)
        await self.message_queue.add(wand, 'Workflow unfinalized! You can now revert to any step and make changes.', verbatim=True)
        return wand.run_all_cells(app_name, steps)

    async def get_suggestion(self, step_id, state):
        """ Gets a suggested input value for a step. """
        if step_id == 'step_01':
            return "// Simple counter example\nlet count = 0;\nconst countDisplay = document.createElement('div');\ncountDisplay.style.fontSize = '24px';\ncountDisplay.style.margin = '20px 0';\ncountDisplay.textContent = count;\n\nconst button = document.createElement('button');\nbutton.textContent = 'Increment Count';\nbutton.style.backgroundColor = '#9370DB';\nbutton.style.borderColor = '#9370DB';\nbutton.onclick = function() {\n    count++;\n    countDisplay.textContent = count;\n};\n\nwidget.appendChild(countDisplay);\nwidget.appendChild(button);"
        return ''

    async def handle_revert(self, request):
        """ Handle POST request to revert to a previous step. """
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

    def _create_js_display(self, js_code, widget_id, target_id):
        """Helper method to create the JavaScript widget display."""
        return Div(P('JavaScript will execute here...', id=target_id, style='padding: 1.5rem; background-color: var(--pico-card-background-color); border-radius: var(--pico-border-radius); min-height: 100px;'), Button('Re-run JavaScript ▸', type='button', _onclick=f"runJsWidget('{widget_id}', `{js_code.replace('`', '\\`')}`, '{target_id}')", style='margin-top: 1rem; background-color: #9370DB; border-color: #9370DB;'), id=widget_id)

    async def step_01(self, request):
        """ Handles GET request for JavaScript execution widget. """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        user_val = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and user_val:
            try:
                widget_id = f'js-widget-{pipeline_id}-{step_id}'.replace('-', '_')
                target_id = f'{widget_id}_target'
                js_widget = self._create_js_display(user_val, widget_id, target_id)
                response = HTMLResponse(to_xml(Div(Card(H3(f'🔒 {step.show}'), js_widget), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))))
                response.headers['HX-Trigger'] = json.dumps({'runJavaScript': {'widgetId': widget_id, 'code': user_val, 'targetId': target_id}})
                return response
            except Exception as e:
                logger.error(f'Error creating JS widget in locked view: {str(e)}')
                return Div(Card(f'🔒 {step.show}: <content locked>'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
        elif user_val and state.get('_revert_target') != step_id:
            try:
                widget_id = f'js-widget-{pipeline_id}-{step_id}'.replace('-', '_')
                target_id = f'{widget_id}_target'
                js_widget = self._create_js_display(user_val, widget_id, target_id)
                content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show} Configured', widget=js_widget, steps=steps)
                response = HTMLResponse(to_xml(Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))))
                response.headers['HX-Trigger'] = json.dumps({'runJavaScript': {'widgetId': widget_id, 'code': user_val, 'targetId': target_id}})
                return response
            except Exception as e:
                logger.error(f'Error creating JS widget: {str(e)}')
                state['_revert_target'] = step_id
                wand.write_state(pipeline_id, state)
        display_value = user_val if step.refill and user_val else await self.get_suggestion(step_id, state)
        await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
        return Div(Card(H3(f'{wand.fmt(step_id)}: Configure {step.show}'), P('Enter JavaScript code for the widget. Example is pre-populated.'), P("Use the 'widget' variable to access the container element.", cls='text-note'), Form(Div(Textarea(display_value, name=step.done, placeholder='Enter JavaScript code', required=True, rows=12, style='width: 100%; font-family: monospace;'), Div(Button('Run JavaScript ▸', type='submit', cls='primary'), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_01_submit(self, request):
        """ Process the submission for JavaScript execution widget. """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        form = await request.form()
        user_val = form.get(step.done, '')
        is_valid, error_msg, error_component = wand.validate_step_input(user_val, step.show)
        if not is_valid:
            return error_component
        await wand.set_step_data(pipeline_id, step_id, user_val, steps)
        wand.append_to_history(f'[WIDGET CONTENT] JavaScript Widget Code:\n{user_val}')
        widget_id = f'js-widget-{pipeline_id}-{step_id}'.replace('-', '_')
        target_id = f'{widget_id}_target'
        js_widget = self._create_js_display(user_val, widget_id, target_id)
        content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Interactive JavaScript example', widget=js_widget, steps=steps)
        response_content = Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        response = HTMLResponse(to_xml(response_content))
        response.headers['HX-Trigger'] = json.dumps({'runJavaScript': {'widgetId': widget_id, 'code': user_val, 'targetId': target_id}})
        await self.message_queue.add(wand, f'{step.show} complete. JavaScript executed.', verbatim=True)
        return response
