import asyncio
import json
from datetime import datetime

from fasthtml.common import *
from loguru import logger
from starlette.responses import HTMLResponse
from imports.crud import Step  # 🎯 STANDARDIZED: Import centralized Step definition

ROLES = ['Components']
'\nPipulate PrismJS Code Highlighter Widget Workflow\nA workflow for demonstrating the Prism.js code syntax highlighting widget.\n'


class PrismWidget:
    """
    PrismJS Code Highlighter Widget Workflow

    Demonstrates syntax highlighting of code using Prism.js.
    """
    APP_NAME = 'prism_widget'
    DISPLAY_NAME = 'PrismJS Code Highlighter'
    ENDPOINT_MESSAGE = 'This workflow demonstrates a Prism.js code syntax highlighting widget. Enter code to see it highlighted.'
    TRAINING_PROMPT = 'This workflow is for demonstrating and testing the PrismJS code highlighting widget. The user will input code (optionally with a language specifier like ```python), and the system will render it with syntax highlighting.'

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
        steps = [Step(id='step_01', done='code_content', show='Code Content', refill=True, transform=lambda prev_value: prev_value.strip() if prev_value else '')]
        routes = [(f'/{app_name}', self.landing), (f'/{app_name}/init', self.init, ['POST']), (f'/{app_name}/revert', self.handle_revert, ['POST']), (f'/{app_name}/finalize', self.finalize, ['GET', 'POST']), (f'/{app_name}/unfinalize', self.unfinalize, ['POST'])]
        self.steps = steps
        for step in steps:
            step_id = step.id
            routes.append((f'/{app_name}/{step_id}', getattr(self, step_id)))
            routes.append((f'/{app_name}/{step_id}_submit', getattr(self, f'{step_id}_submit'), ['POST']))
        for path, handler, *methods in routes:
            method_list = methods[0] if methods else ['GET']
            app.route(path, methods=method_list)(handler)
        self.step_messages = {'finalize': {'ready': 'All steps complete. Ready to finalize workflow.', 'complete': f'Workflow finalized. Use {wand.UNLOCK_BUTTON_LABEL} to make changes.'}, 'step_01': {'input': 'Please enter code content for syntax highlighting.', 'complete': 'Code content processed and highlighted.'}}
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
            return '```javascript\nfunction calculateFactorial(n) {\n    // Base case: factorial of 0 or 1 is 1\n    if (n <= 1) {\n        return 1;\n    }\n    \n    // Recursive case: n! = n * (n-1)!\n    return n * calculateFactorial(n - 1);\n}\n// Example usage\nfor (let i = 0; i < 10; i++) {\n    console.log(`Factorial of ${i} is ${calculateFactorial(i)}`);\n}\n```'
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

    def create_prism_widget(self, code, widget_id, language='javascript'):
        """Create a Prism.js syntax highlighting widget with copy functionality."""
        textarea_id = f'{widget_id}_raw_code'
        container = Div(
            Div(
                H5('Syntax Highlighted Code:'),
                Textarea(code, id=textarea_id, style='display: none;'),
                Pre(Code(code, cls=f'language-{language}'), cls='line-numbers'),
                cls='mt-4'
            ),
            id=widget_id
        )
        init_script = Script(f"""
            (function() {{
                console.log('Prism widget loaded, ID: {widget_id}');
                // Check if Prism is loaded
                if (typeof Prism === 'undefined') {{
                    console.error('Prism library not found');
                    return;
                }}
                
                // Attempt to manually trigger highlighting
                setTimeout(function() {{
                    try {{
                        console.log('Manually triggering Prism highlighting for {widget_id}');
                        Prism.highlightAllUnder(document.getElementById('{widget_id}'));
                    }} catch(e) {{
                        console.error('Error during manual Prism highlighting:', e);
                    }}
                }}, 300);
            }})();
        """, type='text/javascript')
        return Div(container, init_script)

    async def step_01(self, request):
        """Handles GET request for Step 1: Code Input and Highlighting."""
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
        language = 'javascript'
        code_to_display = user_val
        if user_val.startswith('```'):
            first_line_end = user_val.find('\n')
            if first_line_end != -1:
                first_line = user_val[3:first_line_end].strip()
                if first_line:
                    language = first_line
                    code_to_display = user_val[first_line_end + 1:]
                else:
                    code_to_display = user_val[first_line_end + 1:]
            elif len(user_val) > 3 and (not user_val[3:].strip().startswith('```')):
                lang_match = user_val[3:].split(' ', 1)[0].split('\n', 1)[0]
                if lang_match and (not lang_match.startswith('`')):
                    language = lang_match
        if code_to_display.rstrip().endswith('```'):
            code_to_display = code_to_display.rstrip()[:-3].rstrip()
        if 'finalized' in finalize_data and user_val:
            widget_id = f"prism-widget-{pipeline_id.replace('-', '_')}-{step_id}"
            prism_widget = self.create_prism_widget(code_to_display, widget_id, language)
            response = HTMLResponse(to_xml(Div(Card(H3(f'🔒 {step.show} ({language})'), prism_widget), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)))
            response.headers['HX-Trigger'] = json.dumps({'initializePrism': {'targetId': widget_id}})
            return response
        elif user_val and state.get('_revert_target') != step_id:
            widget_id = f"prism-widget-{pipeline_id.replace('-', '_')}-{step_id}"
            prism_widget = self.create_prism_widget(code_to_display, widget_id, language)
            content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Syntax highlighting with Prism.js ({language})', widget=prism_widget, steps=steps)
            response = HTMLResponse(to_xml(Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)))
            response.headers['HX-Trigger'] = json.dumps({'initializePrism': {'targetId': widget_id}})
            return response
        else:
            display_value = user_val if step.refill and user_val else await self.get_suggestion(step_id, state)
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
            explanation = 'Enter code to be highlighted. You can specify language using ```python (or other language) at the start.'
            await self.message_queue.add(wand, explanation, verbatim=True)
            return Div(Card(H3(f'{wand.fmt(step_id)}: Configure {step.show}'), P(explanation, cls='text-secondary'), Form(Div(Textarea(display_value, name=step.done, placeholder='Enter code for syntax highlighting', required=True, rows=15, style='width: 100%; font-family: monospace;'), Div(Button('Highlight Code ▸', type='submit', cls='primary'), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_01_submit(self, request):
        """Process the submission for Code Input and Highlighting."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form = await request.form()
        user_val_raw = form.get(step.done, '')
        user_val_stripped = user_val_raw.strip()
        language = 'javascript'
        code_to_highlight = user_val_stripped
        if user_val_stripped.startswith('```'):
            first_line_end = user_val_stripped.find('\n')
            if first_line_end != -1:
                detected_lang = user_val_stripped[3:first_line_end].strip()
                if detected_lang:
                    language = detected_lang
                code_to_highlight = user_val_stripped[first_line_end + 1:]
            else:
                potential_lang = user_val_stripped[3:].split(' ', 1)[0].split('\n', 1)[0]
                if potential_lang and (not potential_lang.startswith('`')):
                    language = potential_lang
                    if user_val_stripped.startswith(f'```{language}'):
                        code_to_highlight = user_val_stripped[len(f'```{language}'):].lstrip()
        if code_to_highlight.rstrip().endswith('```'):
            code_to_highlight = code_to_highlight.rstrip()[:-3].rstrip()
        is_valid, error_msg, error_component = wand.validate_step_input(code_to_highlight, step.show)
        if not is_valid:
            return error_component
        await wand.set_step_data(pipeline_id, step_id, user_val_raw, steps)
        wand.append_to_history(f'[WIDGET CONTENT] {step.show} ({language}):\n{code_to_highlight}')
        widget_id = f"prism-widget-{pipeline_id.replace('-', '_')}-{step_id}"
        prism_widget = self.create_prism_widget(code_to_highlight, widget_id, language)
        content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Syntax highlighting with Prism.js ({language})', widget=prism_widget, steps=steps)
        response_content = Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        response = HTMLResponse(to_xml(response_content))
        response.headers['HX-Trigger'] = json.dumps({'initializePrism': {'targetId': widget_id}})
        await self.message_queue.add(wand, f'{step.show} complete. Code syntax highlighted with {language}.', verbatim=True)
        if wand.check_finalize_needed(step_index, steps):
            await self.message_queue.add(wand, self.step_messages['finalize']['ready'], verbatim=True)
        return response
