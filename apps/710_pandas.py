import asyncio
import json
from datetime import datetime

import pandas as pd
from fasthtml.common import *
from loguru import logger
from starlette.responses import HTMLResponse
from imports.crud import Step  # 🎯 STANDARDIZED: Import centralized Step definition

ROLES = ['Components']
'\nPipulate Pandas Table Widget Workflow\nA workflow for demonstrating the Pandas DataFrame to HTML table rendering widget.\n'


class PandasTableWidget:
    """
    Pandas Table Widget Workflow

    Demonstrates rendering JSON data as an HTML table using Pandas.
    """
    APP_NAME = 'pandas_table_widget'
    DISPLAY_NAME = 'Pandas Table Widget'
    ENDPOINT_MESSAGE = 'This workflow demonstrates a Pandas DataFrame to HTML table rendering widget. Enter JSON data to see it rendered as a styled table.'
    TRAINING_PROMPT = 'This workflow is for demonstrating and testing the Pandas table widget. The user will input JSON data, and the system will render it as an HTML table using Pandas.'

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
        steps = [Step(id='step_01', done='table_data', show='Table Data (JSON)', refill=True, transform=lambda prev_value: prev_value.strip() if prev_value else '')]
        routes = [(f'/{app_name}', self.landing), (f'/{app_name}/init', self.init, ['POST']), (f'/{app_name}/revert', self.handle_revert, ['POST']), (f'/{app_name}/finalize', self.finalize, ['GET', 'POST']), (f'/{app_name}/unfinalize', self.unfinalize, ['POST'])]
        self.steps = steps
        for step in steps:
            step_id = step.id
            routes.append((f'/{app_name}/{step_id}', getattr(self, step_id)))
            routes.append((f'/{app_name}/{step_id}_submit', getattr(self, f'{step_id}_submit'), ['POST']))
        for path, handler, *methods in routes:
            method_list = methods[0] if methods else ['GET']
            app.route(path, methods=method_list)(handler)
        self.step_messages = {'finalize': {'ready': 'All steps complete. Ready to finalize workflow.', 'complete': f'Workflow finalized. Use {wand.UNLOCK_BUTTON_LABEL} to make changes.'}, 'step_01': {'input': 'Please enter JSON data for the table.', 'complete': 'JSON data processed and table rendered.'}}
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
            return '[\n{"Name": "John", "Age": 32, "Role": "Developer", "Department": "Engineering"},\n{"Name": "Jane", "Age": 28, "Role": "Designer", "Department": "Product"},\n{"Name": "Bob", "Age": 45, "Role": "Manager", "Department": "Engineering"},\n{"Name": "Alice", "Age": 33, "Role": "PM", "Department": "Product"},\n{"Name": "Charlie", "Age": 40, "Role": "Architect", "Department": "Engineering"}\n]'
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

    def create_pandas_table(self, data_str):
        """
        Create a pandas HTML table from JSON string data.

        This helper method encapsulates the widget creation logic, which:
        1. Makes the code more maintainable
        2. Allows reuse in both step_02 and step_02_submit
        3. Centralizes error handling

        When implementing complex widgets, consider using helper methods
        like this to separate widget creation logic from workflow logic.

        Note on FastHTML raw HTML handling:
        - Uses Div(NotStr(html_fragment), _raw=True) to embed raw HTML
        - NotStr prevents string escaping during XML rendering
        - _raw=True flag informs the component to accept unprocessed HTML
        """
        try:
            data = json.loads(data_str)
            if isinstance(data, list) and all((isinstance(item, dict) for item in data)):
                df = pd.DataFrame(data)
            elif isinstance(data, list) and all((isinstance(item, list) for item in data)):
                headers = data[0]
                rows = data[1:]
                df = pd.DataFrame(rows, columns=headers)
            else:
                return Div(NotStr("<div style='color: red;'>Unsupported data format. Please provide a list of objects.</div>"), _raw=True)
            html_table = df.to_html(index=False, classes='table', border=0, escape=True, justify='left')
            table_container = Div(H5('Pandas DataFrame Table:'), Div(NotStr(html_table), style='overflow-x: auto; max-width: 100%;'), cls='mt-4')
            return table_container
        except Exception as e:
            logger.error(f'Error creating pandas table: {e}')
            return Div(NotStr(f"<div style='color: red;'>Error creating table: {str(e)}</div>"), _raw=True)

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
            try:
                table_widget = self.create_pandas_table(user_val)
                return Div(Card(H3(f'🔒 {step.show}'), table_widget), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
            except Exception as e:
                logger.error(f'Error creating table widget in finalized view: {str(e)}')
                return Div(Card(f'🔒 {step.show}: <content locked, error rendering table>'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        elif user_val and state.get('_revert_target') != step_id:
            try:
                table_widget = self.create_pandas_table(user_val)
                content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show} Configured', widget=table_widget, steps=steps)
                return Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
            except Exception as e:
                logger.error(f'Error creating table widget: {str(e)}')
                state['_revert_target'] = step_id
                wand.write_state(pipeline_id, state)
        display_value = user_val if step.refill and user_val else await self.get_suggestion(step_id, state)
        await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
        explanation = 'Enter table data as JSON array of objects. Example is pre-populated. Format: `[{"name": "value", "value1": number, ...}, {...}]`'
        await self.message_queue.add(wand, explanation, verbatim=True)
        return Div(Card(H3(f'{wand.fmt(step_id)}: Configure {step.show}'), P(explanation, cls='text-secondary'), Form(Div(Textarea(display_value, name=step.done, placeholder='Enter JSON array of objects for the DataFrame', required=True, rows=10, style='width: 100%; font-family: monospace;'), Div(Button('Draw Table ▸', type='submit', cls='primary'), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_01_submit(self, request):
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form = await request.form()
        user_val = form.get(step.done, '').strip()
        is_valid, error_msg, error_component = wand.validate_step_input(user_val, step.show)
        if not is_valid:
            return error_component
        try:
            json_data = json.loads(user_val)
            if not isinstance(json_data, list) or not json_data:
                return P('Invalid JSON: Must be a non-empty array of objects', cls='text-invalid')
            if not all((isinstance(item, dict) for item in json_data)):
                return P('Invalid JSON: All items must be objects (dictionaries)', cls='text-invalid')
        except json.JSONDecodeError:
            return P('Invalid JSON format. Please check your syntax.', cls='text-invalid')
        await wand.set_step_data(pipeline_id, step_id, user_val, steps)
        wand.append_to_history(f'[WIDGET CONTENT] {step.show} (JSON Data):\n{user_val}')
        try:
            data = json.loads(user_val)
            df = pd.DataFrame(data)
            html_table = df.to_html(index=False, classes='table', border=0, escape=True, justify='left')
            table_container = Div(H5('Pandas DataFrame Table:'), Div(NotStr(html_table), style='overflow-x: auto; max-width: 100%;'), cls='mt-4')
            await self.message_queue.add(wand, f'{step.show} complete. Table rendered successfully.', verbatim=True)
            response = HTMLResponse(to_xml(Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Table rendered from pandas DataFrame', widget=table_container, steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)))
            return response
        except Exception as e:
            logger.error(f'Error creating pandas table: {e}')
            return Div(NotStr(f"<div style='color: red;'>Error creating table: {str(e)}</div>"), _raw=True)
