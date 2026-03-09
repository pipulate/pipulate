import asyncio
import json
from datetime import datetime

from fasthtml.common import *
from loguru import logger
from starlette.responses import HTMLResponse
from imports.crud import Step  # 🎯 STANDARDIZED: Import centralized Step definition

ROLES = ['Components']
'\nPipulate Mermaid Diagram Widget Workflow\nA workflow for demonstrating the Mermaid.js diagram rendering widget.\n'


class MermaidWidget:
    """
    Mermaid Diagram Widget Workflow

    Demonstrates rendering Mermaid diagram syntax using Mermaid.js.
    """
    APP_NAME = 'mermaid_widget'
    DISPLAY_NAME = 'Mermaid Diagram Widget'
    ENDPOINT_MESSAGE = 'This workflow demonstrates a Mermaid.js diagram rendering widget. Enter Mermaid syntax to see it rendered as a diagram.'
    TRAINING_PROMPT = 'This workflow is for demonstrating and testing the Mermaid diagram widget. The user will input Mermaid diagram syntax, and the system will render it graphically.'

    # UI Constants for automation and accessibility
    UI_CONSTANTS = {
        "AUTOMATION_ATTRIBUTES": {
            "MERMAID_TEXTAREA": "mermaid-widget-textarea",
            "RENDER_BUTTON": "mermaid-widget-render-button",
            "RENDERED_OUTPUT": "mermaid-widget-rendered-output", 
            "WIDGET_CONTAINER": "mermaid-widget-container",
            "PIPELINE_INPUT": "mermaid-pipeline-input",
            "ENTER_BUTTON": "mermaid-enter-button",
            "FINALIZE_BUTTON": "mermaid-finalize-button",
            "UNLOCK_BUTTON": "mermaid-unlock-button"
        },
        "ARIA_LABELS": {
            "MERMAID_INPUT": "Enter Mermaid diagram syntax for rendering",
            "RENDER_BUTTON": "Process Mermaid syntax and create diagram",
            "RENDERED_OUTPUT": "Rendered Mermaid diagram display",
            "WIDGET_CONTAINER": "Mermaid diagram widget interface",
            "PIPELINE_INPUT": "Enter pipeline ID or press Enter for auto-generated key",
            "ENTER_BUTTON": "Initialize workflow with entered or generated pipeline key",
            "FINALIZE_BUTTON": "Finalize Mermaid diagram workflow",
            "UNLOCK_BUTTON": "Unlock workflow to make changes"
        },
        "COLORS": {
            "WIDGET_BORDER": "#e9ecef",
            "DIAGRAM_BACKGROUND": "#f8f9fa"
        },
        "SPACING": {
            "WIDGET_PADDING": "1rem",
            "BUTTON_MARGIN": "1vh 0"
        }
    }

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
        steps = [Step(id='step_01', done='mermaid_syntax', show='Mermaid Syntax', refill=True, transform=lambda prev_value: prev_value.strip() if prev_value else '')]
        routes = [(f'/{app_name}', self.landing), (f'/{app_name}/init', self.init, ['POST']), (f'/{app_name}/revert', self.handle_revert, ['POST']), (f'/{app_name}/finalize', self.finalize, ['GET', 'POST']), (f'/{app_name}/unfinalize', self.unfinalize, ['POST'])]
        self.steps = steps
        for step in steps:
            step_id = step.id
            routes.append((f'/{app_name}/{step_id}', getattr(self, step_id)))
            routes.append((f'/{app_name}/{step_id}_submit', getattr(self, f'{step_id}_submit'), ['POST']))
        for path, handler, *methods in routes:
            method_list = methods[0] if methods else ['GET']
            app.route(path, methods=method_list)(handler)
        self.step_messages = {'finalize': {'ready': 'All steps complete. Ready to finalize workflow.', 'complete': f'Workflow finalized. Use {wand.UNLOCK_BUTTON_LABEL} to make changes.'}, 'step_01': {'input': 'Please enter Mermaid diagram syntax.', 'complete': 'Mermaid diagram syntax processed.'}}
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
                return Card(H3('Workflow is locked.'), Form(Button(wand.UNLOCK_BUTTON_LABEL, type='submit', cls='secondary outline', data_testid=self.UI_CONSTANTS["AUTOMATION_ATTRIBUTES"]["UNLOCK_BUTTON"], aria_label=self.UI_CONSTANTS["ARIA_LABELS"]["UNLOCK_BUTTON"]), hx_post=f'/{app_name}/unfinalize', hx_target=f'#{app_name}-container', hx_swap='outerHTML'), id=finalize_step.id)
            else:
                all_steps_complete = all((wand.get_step_data(pipeline_id, step.id, {}).get(step.done) for step in steps[:-1]))
                if all_steps_complete:
                    return Card(H3('All steps complete. Finalize?'), P('You can revert to any step and make changes.', cls='text-secondary'), Form(Button('Finalize 🔒', type='submit', cls='primary', data_testid=self.UI_CONSTANTS["AUTOMATION_ATTRIBUTES"]["FINALIZE_BUTTON"], aria_label=self.UI_CONSTANTS["ARIA_LABELS"]["FINALIZE_BUTTON"]), hx_post=f'/{app_name}/finalize', hx_target=f'#{app_name}-container', hx_swap='outerHTML'), id=finalize_step.id)
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
            return 'graph TD\n    A[Start] --> B{Decision}\n    B -->|Yes| C[Action 1]\n    B -->|No| D[Action 2]\n    C --> E[Result 1]\n    D --> F[Result 2]\n    E --> G[End]\n    F --> G'
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

    def create_mermaid_widget(self, diagram_syntax, widget_id):
        """Create a mermaid diagram widget container."""
        container = Div(
            Div(
                H5('Rendered Diagram:'), 
                Div(
                    Div(
                        diagram_syntax, 
                        cls='mermaid', 
                        style='width: 100%; background-color: var(--pico-card-background-color); border-radius: var(--pico-border-radius); padding: 1rem;',
                        data_testid=self.UI_CONSTANTS["AUTOMATION_ATTRIBUTES"]["RENDERED_OUTPUT"],
                        aria_label=self.UI_CONSTANTS["ARIA_LABELS"]["RENDERED_OUTPUT"],
                        role="img"
                    ), 
                    id=f'{widget_id}_output'
                )
            ), 
            id=widget_id,
            data_testid=self.UI_CONSTANTS["AUTOMATION_ATTRIBUTES"]["WIDGET_CONTAINER"],
            aria_label=self.UI_CONSTANTS["ARIA_LABELS"]["WIDGET_CONTAINER"]
        )
        init_script = Script(f"""\n            (function() {{\n                setTimeout(function() {{\n                    if (typeof mermaid !== 'undefined') {{\n                        try {{\n                            mermaid.initialize({{ \n                                startOnLoad: false, \n                                theme: 'dark', \n                                securityLevel: 'loose',\n                                flowchart: {{ htmlLabels: true }}\n                            }});\n                            const container = document.getElementById('{widget_id}');\n                            if (!container) return;\n                            const mermaidDiv = container.querySelector('.mermaid');\n                            if (mermaidDiv) {{\n                                void container.offsetWidth; \n                                if (typeof mermaid.run === 'function') {{\n                                    mermaid.run({{ nodes: [mermaidDiv] }});\n                                }} else {{\n                                    mermaid.init(undefined, mermaidDiv);\n                                }}\n                                console.log('Mermaid rendering successful for {widget_id}');\n                            }}\n                        }} catch(e) {{\n                            console.error("Mermaid rendering error for {widget_id}:", e);\n                        }}\n                    }} else {{\n                        console.error("Mermaid library not found for {widget_id}.");\n                    }}\n                }}, 300); \n            }})();\n            """)
        return Div(container, init_script)

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
            widget_id = f"mermaid-widget-{pipeline_id.replace('-', '_')}-{step_id}"
            mermaid_widget = self.create_mermaid_widget(user_val, widget_id)
            response = HTMLResponse(to_xml(Div(Card(H3(f'🔒 {step.show}'), mermaid_widget), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)))
            response.headers['HX-Trigger'] = json.dumps({'renderMermaid': {'targetId': f'{widget_id}_output', 'diagram': user_val}})
            return response
        elif user_val and state.get('_revert_target') != step_id:
            widget_id = f"mermaid-widget-{pipeline_id.replace('-', '_')}-{step_id}"
            mermaid_widget = self.create_mermaid_widget(user_val, widget_id)
            content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show} Configured', widget=mermaid_widget, steps=steps)
            response = HTMLResponse(to_xml(Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)))
            response.headers['HX-Trigger'] = json.dumps({'renderMermaid': {'targetId': f'{widget_id}_output', 'diagram': user_val}})
            return response
        else:
            display_value = user_val if step.refill and user_val else await self.get_suggestion(step_id, state)
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
            explanation = 'Enter Mermaid diagram syntax for the widget. Example is pre-populated. Supports flowcharts, sequence diagrams, class diagrams, etc.'
            await self.message_queue.add(wand, explanation, verbatim=True)
            return Div(Card(H3(f'{wand.fmt(step_id)}: Configure {step.show}'), P(explanation, cls='text-secondary'), Form(Div(Textarea(display_value, name=step.done, placeholder='Enter Mermaid diagram syntax', required=True, rows=15, style='width: 100%; font-family: monospace;', data_testid=self.UI_CONSTANTS["AUTOMATION_ATTRIBUTES"]["MERMAID_TEXTAREA"], aria_label=self.UI_CONSTANTS["ARIA_LABELS"]["MERMAID_INPUT"], aria_describedby="mermaid-help-text"), Div(Button('Create Diagram ▸', type='submit', cls='primary', data_testid=self.UI_CONSTANTS["AUTOMATION_ATTRIBUTES"]["RENDER_BUTTON"], aria_label=self.UI_CONSTANTS["ARIA_LABELS"]["RENDER_BUTTON"]), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}', role="form", aria_label="Configure Mermaid diagram syntax"), P("Supports flowcharts, sequence diagrams, class diagrams, and more", id="mermaid-help-text", cls='text-secondary')), Div(id=next_step_id), id=step_id)

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
        await wand.set_step_data(pipeline_id, step_id, user_val, steps)
        wand.append_to_history(f'[WIDGET CONTENT] {step.show}:\n{user_val}')
        widget_id = f"mermaid-widget-{pipeline_id.replace('-', '_')}-{step_id}"
        mermaid_widget = self.create_mermaid_widget(user_val, widget_id)
        content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Client-side Mermaid diagram rendering', widget=mermaid_widget, steps=steps)
        response_content = Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        response = HTMLResponse(to_xml(response_content))
        response.headers['HX-Trigger'] = json.dumps({'renderMermaid': {'targetId': f'{widget_id}_output', 'diagram': user_val}})
        await self.message_queue.add(wand, f'{step.show} complete. Mermaid diagram rendered.', verbatim=True)
        if wand.check_finalize_needed(step_index, steps):
            await self.message_queue.add(wand, self.step_messages['finalize']['ready'], verbatim=True)
        return response
