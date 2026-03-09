import asyncio
import base64
import json
import os
from collections import Counter
from datetime import datetime
from io import BytesIO
from pathlib import Path

import matplotlib.pyplot as plt
from fastcore.xml import NotStr
from fasthtml.common import *
from loguru import logger
from starlette.responses import HTMLResponse
from imports.crud import Step  # 🎯 STANDARDIZED: Import centralized Step definition

ROLES = ['Components']
'\nMatplotlib Histogram Widget\n\nThis workflow demonstrates a Matplotlib histogram rendering widget.\nUsers can input JSON counter data and see it rendered as a histogram image.\n\nThe widget supports:\n- JSON counter data input (keys and values)\n- Automatic histogram generation\n- Responsive image display\n- Error handling and validation\n'


class MatplotlibWidget:
    """
    Matplotlib Histogram Widget Workflow

    A focused environment for creating and testing Matplotlib histogram visualizations.
    Users input JSON counter data and see it rendered as a histogram image.
    """
    APP_NAME = 'matplotlib_widget'
    DISPLAY_NAME = 'Matplotlib Histogram Widget'
    ENDPOINT_MESSAGE = 'This workflow demonstrates a Matplotlib histogram rendering widget. Enter JSON counter data to see it rendered as an image.'
    TRAINING_PROMPT = 'This workflow is for demonstrating and testing the Matplotlib histogram widget. The user will input JSON formatted counter data (keys and values), and the system will render it as a histogram image.'

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
        steps = [Step(id='step_01', done='counter_data', show='Counter Data (JSON)', refill=True, transform=lambda prev_value: prev_value.strip() if prev_value else '')]
        routes = [(f'/{app_name}', self.landing), (f'/{app_name}/init', self.init, ['POST']), (f'/{app_name}/revert', self.handle_revert, ['POST']), (f'/{app_name}/finalize', self.finalize, ['GET', 'POST']), (f'/{app_name}/unfinalize', self.unfinalize, ['POST'])]
        self.steps = steps
        for step in steps:
            step_id = step.id
            routes.append((f'/{app_name}/{step_id}', getattr(self, step_id)))
            routes.append((f'/{app_name}/{step_id}_submit', getattr(self, f'{step_id}_submit'), ['POST']))
        for path, handler, *methods in routes:
            method_list = methods[0] if methods else ['GET']
            app.route(path, methods=method_list)(handler)
        self.step_messages = {'finalize': {'ready': 'All steps complete. Ready to finalize workflow.', 'complete': f'Workflow finalized. Use {wand.UNLOCK_BUTTON_LABEL} to make changes.'}, 'new': 'Please enter JSON counter data to create a histogram visualization.', 'step_01': {'input': 'Please enter JSON counter data for the histogram.', 'complete': 'Counter data processed and histogram rendered.'}}
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
            return '{\n    "apples": 35,\n    "oranges": 42,\n    "bananas": 28,\n    "grapes": 51,\n    "peaches": 22,\n    "plums": 18,\n    "mangoes": 39\n}'
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

    async def step_01(self, request):
        """
        Handles GET request for Step 1: Matplotlib Histogram Widget.

        This step allows users to input counter data and visualizes it as a histogram.
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        counter_data = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and counter_data:
            try:
                histogram_widget = self.create_matplotlib_histogram(counter_data)
                return Div(Card(H3(f'🔒 {step.show}'), histogram_widget), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
            except Exception as e:
                logger.error(f'Error creating histogram in finalized view: {str(e)}')
                return Div(Card(f'🔒 {step.show}: <content locked>'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
        elif counter_data and state.get('_revert_target') != step_id:
            try:
                histogram_widget = self.create_matplotlib_histogram(counter_data)
                content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show} Configured', widget=histogram_widget, steps=steps)
                return Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
            except Exception as e:
                logger.error(f'Error creating histogram widget: {str(e)}')
                state['_revert_target'] = step_id
                wand.write_state(pipeline_id, state)
        display_value = counter_data if step.refill and counter_data else await self.get_suggestion(step_id, state)
        await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
        return Div(Card(H3(f'{wand.fmt(step_id)}: Configure {step.show}'), P('Enter counter data as JSON object (keys and values):'), P('Format: {"category1": count1, "category2": count2, ...}', cls='text-note'), Form(Div(Textarea(display_value, name=step.done, placeholder='Enter JSON object for Counter data', required=True, rows=10, style='width: 100%; font-family: monospace;'), Div(Button('Create Histogram ▸', type='submit', cls='primary'), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_01_submit(self, request):
        """
        Process the submission for Step 1 (Matplotlib Histogram).

        Takes counter data as input and creates a histogram visualization.
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        form = await request.form()
        counter_data = form.get(step.done, '').strip()
        is_valid, error_msg, error_component = wand.validate_step_input(counter_data, step.show)
        if not is_valid:
            return error_component
        try:
            data = json.loads(counter_data)
            if not isinstance(data, dict):
                return P('Invalid JSON: Must be an object (dictionary) with keys and values', cls='text-invalid')
            if not data:
                return P('Invalid data: Counter cannot be empty', cls='text-invalid')
        except json.JSONDecodeError:
            return P('Invalid JSON format. Please check your syntax.', cls='text-invalid')
        await wand.set_step_data(pipeline_id, step_id, counter_data, steps)
        try:
            histogram_widget = self.create_matplotlib_histogram(counter_data)
            content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Histogram created from Counter data', widget=histogram_widget, steps=steps)
            response_content = Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
            await self.message_queue.add(wand, f'{step.show} complete. Histogram created.', verbatim=True)
            return HTMLResponse(to_xml(response_content))
        except Exception as e:
            logger.error(f'Error creating histogram visualization: {e}')
            return P(f'Error creating histogram: {str(e)}', cls='text-invalid')

    def create_matplotlib_histogram(self, data_str):
        """
        Create a matplotlib histogram visualization from JSON counter data.

        Args:
            data_str: A JSON string representing counter data

        Returns:
            A Div element containing the histogram image
        """
        try:
            data = json.loads(data_str)
            if not isinstance(data, dict):
                return Div(NotStr("<div style='color: red;'>Error: Data must be a JSON object with keys and values</div>"), _raw=True)
            counter = Counter(data)
            if not counter:
                return Div(NotStr("<div style='color: red;'>Error: No data to plot</div>"), _raw=True)
            plt.figure(figsize=(10, 6))
            labels = sorted(counter.keys())
            values = [counter[label] for label in labels]
            plt.bar(labels, values, color='skyblue')
            plt.xlabel('Categories')
            plt.ylabel('Counts')
            plt.title('Histogram from Counter Data')
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            if len(labels) > 5:
                plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            buffer = BytesIO()
            plt.savefig(buffer, format='png')
            plt.close()
            img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return Div(H4('Histogram Visualization:'), P(f'Data: {len(counter)} categories, {sum(counter.values())} total counts'), Div(NotStr(f'<img src="data:image/png;base64,{img_str}" style="max-width:100%; height:auto;" />'), style='text-align: center; margin-top: 1rem;'), cls='overflow-auto')
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            return Div(NotStr(f"<div style='color: red;'>Error creating histogram: {str(e)}<br><pre>{tb}</pre></div>"), _raw=True)
