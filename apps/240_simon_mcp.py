# File: apps/830_simon_mcp.py
import asyncio
from datetime import datetime
import json
from fasthtml.common import * # type: ignore
from starlette.responses import RedirectResponse
from loguru import logger
import inspect
from pathlib import Path
import re
from imports.crud import Step  # 🎯 STANDARDIZED: Import centralized Step definition

ROLES = ['Developer'] # Defines which user roles can see this plugin

# Import MODEL constant from server
from config import DEFAULT_PROMPT_MODEL as MODEL

class SimonSaysMcpWidget:
    """
    Simon Says Make MCP Call
    Direct MCP tool execution for testing and training with UI element flashing and other MCP capabilities.
    This utility provides immediate access to MCP tools without requiring pipeline keys or LLM interpretation.
    """
    APP_NAME = 'simon_mcp'
    DISPLAY_NAME = 'Simon Says Make MCP Call 🎪'
    ENDPOINT_MESSAGE = """Simon Says Make MCP Call - Direct MCP tool execution utility. Select an action and click to execute MCP tools for teaching and testing."""
    TRAINING_PROMPT = """This is the Simon Says Make MCP Call utility. The user can select different MCP actions from a dropdown and immediately execute them using MCP tools. No LLM interpretation is involved - it's direct tool execution for training and testing."""

    # --- START_CLASS_ATTRIBUTES_BUNDLE ---
    UI_CONSTANTS = {
        'SHARED': {
            'FONT_SIZE': '0.9rem',
            'FONT_FAMILY': 'monospace',
            'LINE_HEIGHT': '1.5',
            'PADDING': '0.75rem',
            'MIN_HEIGHT': '450px',
            'WIDTH': '100%',
            'WHITE_SPACE': 'pre-wrap',
            'OVERFLOW_WRAP': 'break-word',
            'BORDER_RADIUS': '4px'
        },
        'INPUT_STYLE': {
            'BORDER': '1px solid var(--pico-form-element-border-color)',
            'BACKGROUND_COLOR': 'var(--pico-form-element-background-color)'
        },
        'DISPLAY_STYLE': {
            'BORDER': '1px solid var(--pico-muted-border-color)',
            'BACKGROUND_COLOR': 'var(--pico-card-background-color)',
            'COLOR': 'var(--pico-color)'
        }
    }
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
            Step(id='step_01', done='mcp_interaction', show='Simon Says Prompt', refill=True),
            # --- STEPS_LIST_INSERTION_POINT ---
            Step(id='finalize', done='finalized', show='Finalize Workflow', refill=False)
        ]
        self.steps_indices = {step_obj.id: i for i, step_obj in enumerate(self.steps)}

        # Use centralized route registration helper
        pipulate.register_workflow_routes(self)
        
        # Register custom route for mode changing
        self.app.route(f'/{self.APP_NAME}/step_01_change_mode', methods=['POST'])(self.step_01_change_mode)

        self.step_messages = {}
        for step_obj in self.steps:
            if step_obj.id == 'finalize':
                self.step_messages['finalize'] = {
                    'ready': self.ui['MESSAGES']['ALL_STEPS_COMPLETE'],
                    'complete': f'Workflow finalized. Use {self.ui["BUTTON_LABELS"]["UNLOCK"]} to make changes.'
                }
            else:
                self.step_messages[step_obj.id] = {
                    'input': f'{step_obj.show}: Please provide the required input.',
                    'complete': f'{step_obj.show} is complete. Proceed to the next action.'
                }

    async def landing(self, request):
        """Direct utility - skip pipeline keys and go straight to Simon Says testing."""
        # Bypass the entire pipeline system - this is a utility tool, not a data workflow
        return Div(
            H2(self.DISPLAY_NAME),
            P(self.ENDPOINT_MESSAGE),
            # Jump straight to step_01 - no keys needed
            Div(id='step_01', hx_get=f'/{self.APP_NAME}/step_01', hx_trigger='load'),
            id=f'{self.APP_NAME}-container'
        )

    async def init(self, request):
        wand, db = self.pipulate, self.pipulate.db
        internal_app_name = self.APP_NAME
        form = await request.form()
        user_input_key = form.get('pipeline_id', '').strip()

        # CRITICAL: Auto-key generation pattern - return HX-Refresh for empty keys
        if not user_input_key:
            from starlette.responses import Response
            response = Response('')
            response.headers['HX-Refresh'] = 'true'
            return response

        # Handle user-provided keys
        _, prefix_for_key_gen, _ = wand.generate_pipeline_key(self)
        if user_input_key.startswith(prefix_for_key_gen) and len(user_input_key.split('-')) == 3:
            pipeline_id = user_input_key
        else:
             _, prefix, user_part = wand.generate_pipeline_key(self, user_input_key)
             pipeline_id = f'{prefix}{user_part}'

        wand.db['pipeline_id'] = pipeline_id
        state, error = wand.initialize_if_missing(pipeline_id, {'app_name': internal_app_name})
        if error: return error

        # Skip verbose init messages for cleaner Simon Says demonstration
        pass

        return wand.run_all_cells(internal_app_name, self.steps)

    async def finalize(self, request):
        wand, db, app_name = self.pipulate, self.pipulate.db, self.APP_NAME
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        finalize_step_obj = next(s for s in self.steps if s.id == 'finalize')
        finalize_data = wand.get_step_data(pipeline_id, finalize_step_obj.id, {})
        state = wand.read_state(pipeline_id)

        if request.method == 'GET':
            # STEP PHASE: Finalize (already finalized)
            if finalize_step_obj.done in finalize_data:
                return Card(
                    H3(self.ui['MESSAGES']['WORKFLOW_LOCKED']), 
                    Form(
                        Button(self.ui['BUTTON_LABELS']['UNLOCK'], type='submit', cls=self.ui['BUTTON_STYLES']['OUTLINE']), 
                        hx_post=f'/{app_name}/unfinalize', 
                        hx_target=f'#{app_name}-container'
                    ), 
                    id=finalize_step_obj.id
                )
            
            # Check if all data steps are complete  
            data_steps = [step for step in self.steps if step.id != 'finalize']
            all_data_steps_complete = True
            
            for step in data_steps:
                step_data = wand.get_step_data(pipeline_id, step.id, {})
                if not (step.done in step_data and step_data.get(step.done)):
                    all_data_steps_complete = False
                    break
            
            # STEP PHASE: Get Input (show finalize button when all steps complete)
            if all_data_steps_complete:
                return Card(
                    H3(self.ui['MESSAGES']['FINALIZE_QUESTION']), 
                    P(self.ui['MESSAGES']['FINALIZE_HELP'], cls='text-secondary'), 
                    Form(
                        Button(self.ui['BUTTON_LABELS']['FINALIZE'], type='submit', cls=self.ui['BUTTON_STYLES']['PRIMARY']), 
                        hx_post=f'/{app_name}/finalize', 
                        hx_target=f'#{app_name}-container'
                    ), 
                    id=finalize_step_obj.id
                )
            else:
                # Still waiting for steps to complete - show progress
                return Card(
                    H3("🔄 Workflow In Progress"),
                    P("Complete all steps to finalize this workflow"),
                    id=finalize_step_obj.id
                )
        
        elif request.method == 'POST':
            await wand.finalize_workflow(pipeline_id)
            # Skip finalize message for cleaner demonstration
            return wand.run_all_cells(app_name, self.steps)

    async def unfinalize(self, request):
        wand, db, app_name = (self.pipulate, self.pipulate.db, self.APP_NAME)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        await wand.unfinalize_workflow(pipeline_id)
        # Skip unfinalize message for cleaner demonstration
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

        # Skip revert state messages for cleaner demonstration
        pass
        return wand.run_all_cells(app_name, current_steps_to_pass_helpers)

    def _get_base_style(self):
        """Generate base style shared by both input and display."""
        shared = self.UI_CONSTANTS['SHARED']
        return (f"min-height: {shared['MIN_HEIGHT']}; "
                f"width: {shared['WIDTH']}; "
                f"font-family: {shared['FONT_FAMILY']}; "
                f"font-size: {shared['FONT_SIZE']}; "
                f"line-height: {shared['LINE_HEIGHT']}; "
                f"padding: {shared['PADDING']}; "
                f"white-space: {shared['WHITE_SPACE']}; "
                f"overflow-wrap: {shared['OVERFLOW_WRAP']}; "
                f"border-radius: {shared['BORDER_RADIUS']}; ")

    def _get_textarea_style(self):
        """Generate textarea input style with form element colors."""
        base = self._get_base_style()
        input_style = self.UI_CONSTANTS['INPUT_STYLE']
        return (base + 
                f"border: {input_style['BORDER']}; "
                f"background-color: {input_style['BACKGROUND_COLOR']};")

    def _get_display_style(self):
        """Generate display style with readable card colors."""
        base = self._get_base_style()
        display_style = self.UI_CONSTANTS['DISPLAY_STYLE']
        return (base + 
                f"border: {display_style['BORDER']}; "
                f"background-color: {display_style['BACKGROUND_COLOR']}; "
                f"color: {display_style['COLOR']};")
                
    def _get_consistent_style(self):
        """Deprecated - use _get_display_style() or _get_textarea_style() instead."""
        return self._get_display_style()

    async def step_01(self, request):
        """Simon Says Make MCP Call interface - simplified utility."""
        app_name = self.app_name
        step_id = 'step_01'
        wand = self.pipulate
        
        # Simple utility - no pipeline state management needed
        await self.message_queue.add(wand, "🎪 Simon Says Make MCP Call! Select an MCP action from the dropdown and click the button to execute it directly for teaching and testing!", verbatim=True)
        
        # Simplified mode selection - store in a simple class attribute since this is a utility
        current_mode = getattr(self, 'current_mode', 'cat_fact')
        
        # MCP tool test commands
        cat_fact_prompt = """Get a random cat fact:

<mcp-request>
  <tool name="get_cat_fact" />
</mcp-request>"""

        google_search_prompt = """Perform a Google search:

<mcp-request>
  <tool name="browser_stealth_search">
    <params>
      <query>python programming tutorial</query>
      <max_results>5</max_results>
      <take_screenshot>true</take_screenshot>
      <save_page_source>true</save_page_source>
      <captcha_pause_seconds>60</captcha_pause_seconds>
    </params>
  </tool>
</mcp-request>"""

        # Explicit flash commands for each UI element
        flash_chat_prompt = """Flash the chat conversation area:

<mcp-request>
  <tool name="ui_flash_element">
    <params>
      <element_id>msg-list</element_id>
      <message>This is where your conversation with the AI appears!</message>
      <delay>500</delay>
    </params>
  </tool>
</mcp-request>"""

        flash_app_menu_prompt = """Flash the main app selection menu:

<mcp-request>
  <tool name="ui_flash_element">
    <params>
      <element_id>app-id</element_id>
      <message>This is the main app selection menu!</message>
      <delay>500</delay>
    </params>
  </tool>
</mcp-request>"""

        flash_profile_menu_prompt = """Flash the profile selection menu:

<mcp-request>
  <tool name="ui_flash_element">
    <params>
      <element_id>profile-id</element_id>
      <message>This is the profile selection menu!</message>
      <delay>500</delay>
    </params>
  </tool>
</mcp-request>"""

        flash_send_button_prompt = """Flash the chat send button:

<mcp-request>
  <tool name="ui_flash_element">
    <params>
      <element_id>send-btn</element_id>
      <message>This is the send message button!</message>
      <delay>500</delay>
    </params>
  </tool>
</mcp-request>"""

        flash_nav_bar_prompt = """Flash the top navigation bar:

<mcp-request>
  <tool name="ui_flash_element">
    <params>
      <element_id>nav-group</element_id>
      <message>This is the top navigation bar!</message>
      <delay>500</delay>
    </params>
  </tool>
</mcp-request>"""

        flash_settings_prompt = """Flash the settings gear icon:

<mcp-request>
  <tool name="ui_flash_element">
    <params>
      <element_id>poke-summary</element_id>
      <message>This is the settings gear icon!</message>
      <delay>500</delay>
    </params>
  </tool>
</mcp-request>"""

        # Mode configuration - MCP tools first, then UI flash elements
        mode_config = {
            'cat_fact': {
                'prompt': cat_fact_prompt,
                'button_text': 'Get Cat Fact ▸',
                'button_style': 'margin-top: 1rem; background-color: var(--pico-color-amber-500);',
                'display_name': 'Cat Fact Test'
            },
            'google_search': {
                'prompt': google_search_prompt,
                'button_text': 'Google Search ▸',
                'button_style': 'margin-top: 1rem; background-color: var(--pico-color-cyan-500);',
                'display_name': 'Google Search Test'
            },
            'flash_chat': {
                'prompt': flash_chat_prompt,
                'button_text': 'Flash Chat Area ▸',
                'button_style': 'margin-top: 1rem;',
                'display_name': 'Flash Chat Area'
            },
            'flash_app_menu': {
                'prompt': flash_app_menu_prompt,
                'button_text': 'Flash App Menu ▸',
                'button_style': 'margin-top: 1rem; background-color: var(--pico-color-blue-500);',
                'display_name': 'Flash App Menu'
            },
            'flash_profile_menu': {
                'prompt': flash_profile_menu_prompt,
                'button_text': 'Flash Profile Menu ▸',
                'button_style': 'margin-top: 1rem; background-color: var(--pico-color-green-500);',
                'display_name': 'Flash Profile Menu'
            },
            'flash_send_button': {
                'prompt': flash_send_button_prompt,
                'button_text': 'Flash Send Button ▸',
                'button_style': 'margin-top: 1rem; background-color: var(--pico-color-orange-500);',
                'display_name': 'Flash Send Button'
            },
            'flash_nav_bar': {
                'prompt': flash_nav_bar_prompt,
                'button_text': 'Flash Navigation Bar ▸',
                'button_style': 'margin-top: 1rem; background-color: var(--pico-color-purple-500);',
                'display_name': 'Flash Navigation Bar'
            },
            'flash_settings': {
                'prompt': flash_settings_prompt,
                'button_text': 'Flash Settings Gear ▸',
                'button_style': 'margin-top: 1rem; background-color: var(--pico-color-red-500);',
                'display_name': 'Flash Settings Gear'
            }
        }
        
        current_config = mode_config.get(current_mode, mode_config['flash_chat'])
        
        # Mode selection dropdown
        mode_dropdown = Select(
            *[Option(config['display_name'], value=mode, selected=(mode == current_mode)) 
              for mode, config in mode_config.items()],
            name='mode_select',
            hx_post=f'/{app_name}/{step_id}_change_mode',
            hx_target='#action-content',
            hx_swap='outerHTML',
            hx_include='closest form',
            style='margin-bottom: 1rem;'
        )
        
        # Create training envelope for copying
        training_envelope = f"""--- Simon Says MCP Training ---
I need you to execute this exact MCP tool call:

{current_config['prompt']}

Output only the MCP block above. Do not add any other text."""

        # Direct action content container (for HTMX swapping)
        action_content = Div(
            P(f"Ready to execute: {current_config['display_name']}", 
              cls="text-secondary mb-lg"),
            Div(
                Button(
                    current_config['button_text'], 
                    type='submit', 
                    cls='primary',
                    **{'hx-on:click': 'this.setAttribute("aria-busy", "true")'}
                ),
                Button(
                    '📋 Copy for Chat',
                    type='button',
                    cls='secondary',
                    id=f'copy-mcp-btn-{current_mode}',
                    style='margin-top: 1rem; background-color: var(--pico-color-grey-500);',
                    **{
                        'data-copy-text': training_envelope,
                        'onclick': f'''
                            const button = this;
                            const originalText = button.textContent;
                            const textToCopy = button.getAttribute('data-copy-text');
                            
                            // Show loading state
                            button.textContent = '⏳ Copying...';
                            button.disabled = true;
                            
                            navigator.clipboard.writeText(textToCopy).then(function() {{
                                // Show success state
                                button.textContent = '✅ Copied!';
                                button.style.backgroundColor = 'var(--pico-color-green-500)';
                                
                                // Reset after 3 seconds
                                setTimeout(function() {{
                                    button.textContent = originalText;
                                    button.style.backgroundColor = 'var(--pico-color-grey-500)';
                                    button.disabled = false;
                                }}, 3000);
                            }}).catch(function(error) {{
                                console.error('Error copying to clipboard:', error);
                                
                                // Show error state
                                button.textContent = '❌ Error';
                                button.style.backgroundColor = 'var(--pico-color-red-500)';
                                
                                // Reset after 3 seconds
                                setTimeout(function() {{
                                    button.textContent = originalText;
                                    button.style.backgroundColor = 'var(--pico-color-grey-500)';
                                    button.disabled = false;
                                }}, 3000);
                            }});
                        '''
                    }
                ),
                style='display: flex; gap: var(--pipulate-gap-sm); align-items: flex-start; flex-wrap: wrap;'
            ),
            id='action-content'
        )
        
        form_content = Form(
            Label("Select MCP Action to Execute:", **{'for': 'mode_select'}),
            mode_dropdown,
            action_content,
            hx_post=f'/{app_name}/{step_id}_submit',
            hx_target=f'#{step_id}'
        )
        
        return Div(
            Card(
                H3('🎪 Simon Says Make MCP Call'), 
                P('🎯 Direct Execution: Click the colored button to immediately execute the selected MCP action.'),
                P('📋 Training Mode: Click "Copy for Chat" to copy the MCP command with training envelope, then paste it in the chat to teach your local LLM how MCP tools work.'),
                form_content
            ),
            id=step_id
        )

    async def step_01_submit(self, request):
        """Process the 'Simon Says' prompt and directly execute the MCP tool."""
        app_name = self.app_name
        step_id = 'step_01'
        wand = self.pipulate

        try:
            form = await request.form()
            selected_mode = form.get('mode_select', 'flash_chat')
            
            # Get current mode to determine which element to flash
            current_mode = getattr(self, 'current_mode', selected_mode)
            
            # Map modes to direct MCP tool calls
            mode_to_element = {
                'cat_fact': {'tool': 'get_cat_fact', 'params': {}},
                'google_search': {'tool': 'browser_stealth_search', 'params': {
                    'query': 'python programming tutorial',
                    'max_results': 5,
                    'take_screenshot': True,
                    'save_page_source': True,
                    'captcha_pause_seconds': 60  # Give 60 seconds to solve CAPTCHA manually
                }},
                'flash_chat': {'element_id': 'msg-list', 'message': 'This is where your conversation with the AI appears!'},
                'flash_app_menu': {'element_id': 'app-id', 'message': 'This is the main app selection menu!'},
                'flash_profile_menu': {'element_id': 'profile-id', 'message': 'This is the profile selection menu!'},
                'flash_send_button': {'element_id': 'send-btn', 'message': 'This is the send message button!'},
                'flash_nav_bar': {'element_id': 'nav-group', 'message': 'This is the top navigation bar!'},
                'flash_settings': {'element_id': 'poke-summary', 'message': 'This is the settings gear icon!'}
            }
            
            if current_mode not in mode_to_element:
                return P(f'Unknown mode: {current_mode}', style='color: red;')
            
            config = mode_to_element[current_mode]
            
            # Handle MCP tools (cat_fact and google_search)
            if current_mode in ['cat_fact', 'google_search']:
                import httpx
                async with httpx.AsyncClient() as client:
                    tool_name = config['tool']
                    params = config['params']
                    
                    response = await client.post(
                        "http://localhost:5001/mcp-tool-executor",
                        headers={"Content-Type": "application/json"},
                        json={"tool": tool_name, "params": params},
                        timeout=120  # Much longer timeout for CAPTCHA solving (2 minutes)
                    )
                    
                    if response.status_code in [200, 503]:
                        result = response.json()
                        
                        if current_mode == 'cat_fact':
                            # Check for success in the correct format: status="success" with nested result
                            if result.get('status') == 'success' and result.get('result'):
                                fact_data = result.get('result', {})
                                fact = fact_data.get('fact', 'No fact returned')
                                
                                # Add to conversation history for LLM training (silent - no user stream)
                                await self.message_queue.add(wand, f"User selected: Cat Fact Test", verbatim=True, role='user')
                                await self.message_queue.add(wand, f"MCP Tool Execution: get_cat_fact → Success. Fact: {fact}", verbatim=True, role='assistant')
                            else:
                                error_msg = result.get("error", "Unknown error")
                                
                                # Add failure to conversation history for LLM learning (silent - no user stream)
                                await self.message_queue.add(wand, f"User selected: Cat Fact Test", verbatim=True, role='user')
                                await self.message_queue.add(wand, f"MCP Tool Execution: get_cat_fact → Failed. Error: {error_msg}", verbatim=True, role='assistant')
                        
                        elif current_mode == 'google_search':
                            # Handle Google search results
                            logger.info(f"🔧 FINDER_TOKEN: GOOGLE_RESULT_PROCESSING - Processing result: {result.get('success')}")
                            if result.get('success'):
                                results = result.get('results', [])
                                files = result.get('files_created', {})
                                
                                logger.info(f"🔧 FINDER_TOKEN: GOOGLE_SUCCESS_DATA - {len(results)} results, files: {list(files.keys())}")
                                
                                # Add to conversation history for LLM training (silent - no user stream)
                                await self.message_queue.add(wand, f"User selected: Google Search Test", verbatim=True, role='user')
                                await self.message_queue.add(wand, f"MCP Tool Execution: browser_stealth_search(query='python programming tutorial') → Success. Found {len(results)} results. Files: {list(files.keys())}", verbatim=True, role='assistant')
                                
                                logger.info(f"🔧 FINDER_TOKEN: GOOGLE_MESSAGE_QUEUE_COMPLETE - Added success messages to queue")
                            else:
                                error_msg = result.get("error", "Unknown error")
                                
                                # Add failure to conversation history for LLM learning (silent - no user stream)
                                await self.message_queue.add(wand, f"User selected: Google Search Test", verbatim=True, role='user')
                                await self.message_queue.add(wand, f"MCP Tool Execution: browser_stealth_search → Failed. Error: {error_msg}", verbatim=True, role='assistant')
                    else:
                        error_msg = f'HTTP error: {response.status_code}'
                        
                        # Add HTTP failure to conversation history (silent - no user stream)
                        tool_display = "Cat Fact Test" if current_mode == 'cat_fact' else "Google Search Test"
                        await self.message_queue.add(wand, f"User selected: {tool_display}", verbatim=True, role='user')
                        await self.message_queue.add(wand, f"MCP Tool Execution: {tool_name} → HTTP Error {response.status_code}", verbatim=True, role='assistant')
            else:
                # Handle UI flash elements
                import httpx
                async with httpx.AsyncClient() as client:
                    params = {
                        'element_id': config['element_id'],
                        'message': config['message'],
                        'delay': 500
                    }
                    response = await client.post(
                        "http://localhost:5001/mcp-tool-executor",
                        headers={"Content-Type": "application/json"},
                        json={"tool": "ui_flash_element", "params": params},
                        timeout=30  # Increased timeout for UI flash operations
                    )
                    
                    if response.status_code in [200, 503]:
                        result = response.json()
                        if result.get('success'):
                            # Add successful flash to conversation history for LLM training (silent - no user stream)
                            element_name = mode_to_element[current_mode]
                            await self.message_queue.add(wand, f"User selected: {current_mode.replace('_', ' ').title()}", verbatim=True, role='user')
                            await self.message_queue.add(wand, f"MCP Tool Execution: ui_flash_element(element_id='{config['element_id']}', message='{config['message']}', delay=500) → Success. Element flashed 10 times.", verbatim=True, role='assistant')
                        else:
                            error_msg = result.get("error", "Unknown error")
                            
                            # Add failure to conversation history for LLM learning (silent - no user stream)
                            await self.message_queue.add(wand, f"User selected: {current_mode.replace('_', ' ').title()}", verbatim=True, role='user')
                            await self.message_queue.add(wand, f"MCP Tool Execution: ui_flash_element(element_id='{config['element_id']}') → Failed. Error: {error_msg}", verbatim=True, role='assistant')
                    else:
                        error_msg = f'HTTP error: {response.status_code}'
                        
                        # Add HTTP failure to conversation history (silent - no user stream)
                        await self.message_queue.add(wand, f"User selected: {current_mode.replace('_', ' ').title()}", verbatim=True, role='user')
                        await self.message_queue.add(wand, f"MCP Tool Execution: ui_flash_element → HTTP Error {response.status_code}", verbatim=True, role='assistant')
            
            # Return fresh form for immediate re-testing
            logger.info(f"🔧 FINDER_TOKEN: SIMON_SUCCESS - MCP tool executed successfully, returning refresh")
            logger.info(f"🔧 FINDER_TOKEN: SIMON_RETURN_VALUES - step_id={step_id}, app_name={self.app_name}")
            return Div(id=step_id, hx_get=f'/{self.app_name}/{step_id}', hx_trigger='load')

        except Exception as e:
            # Handle timeout specifically - the MCP tool likely succeeded but the HTTP response timed out
            if 'ReadTimeout' in str(type(e).__name__) or 'timeout' in str(e).lower():
                logger.warning(f"🔧 FINDER_TOKEN: SIMON_TIMEOUT - HTTP timeout in step_01_submit: {type(e).__name__}")
                
                # Add timeout info to conversation history
                await self.message_queue.add(wand, f"User executed MCP tool (HTTP timeout occurred)", verbatim=True, role='user')
                await self.message_queue.add(wand, f"MCP Tool Execution: HTTP timeout after 2+ minutes - tool likely completed successfully in background", verbatim=True, role='assistant')
                
                # Return success message since the MCP tool probably worked
                return Div(
                    Card(
                        H3('⏰ Operation Timeout'),
                        P('The MCP tool execution timed out after 2+ minutes, but it likely completed successfully in the background.'),
                        P('Check the server logs for MCP_SUCCESS messages to confirm completion.', cls='text-secondary'),
                        Button('Try Again', type='button', cls='primary', 
                               onclick=f"document.getElementById('step_01').innerHTML = '<div hx-get=\"/{self.app_name}/step_01\" hx-trigger=\"load\"></div>'; htmx.process(document.getElementById('step_01'));")
                    ),
                    id='step_01'
                )
            else:
                                 # Handle other exceptions
                 error_msg = f'Error during MCP tool execution: {str(e)}'
                 logger.error(f"🔧 FINDER_TOKEN: SIMON_EXCEPTION - Error in step_01_submit: {error_msg}")
                 logger.error(f"🔧 FINDER_TOKEN: SIMON_EXCEPTION_TYPE - Exception type: {type(e).__name__}")
                 logger.error(f"🔧 FINDER_TOKEN: SIMON_EXCEPTION_REPR - Exception repr: {repr(e)}")
                 
                 # Add exception to conversation history for LLM learning (silent - no user stream)
                 await self.message_queue.add(wand, f"User attempted MCP execution", verbatim=True, role='user')
                 await self.message_queue.add(wand, f"MCP Tool Execution → Exception: {error_msg}", verbatim=True, role='assistant')
                 
                 # CRITICAL: Return proper div structure to preserve HTMX functionality
                 return Div(
                     Card(
                         H3('❌ Error'),
                         P(error_msg, cls='text-invalid'),
                         Button('Try Again', type='button', cls='primary', 
                                onclick=f"document.getElementById('step_01').innerHTML = '<div hx-get=\"/{self.app_name}/step_01\" hx-trigger=\"load\"></div>'; htmx.process(document.getElementById('step_01'));")
                     ),
                     id='step_01'
                 )
    # --- END_STEP_BUNDLE: step_01 ---

    async def step_01_change_mode(self, request):
        """Handle dropdown mode change with HTMX swap."""
        app_name = self.app_name
        
        try:
            form = await request.form()
            selected_mode = form.get('mode_select', 'flash_chat')
            
            # Store the new mode in simple class attribute since this is a utility
            self.current_mode = selected_mode
            
            # MCP tool test commands
            cat_fact_prompt = """Get a random cat fact:

<mcp-request>
  <tool name="get_cat_fact" />
</mcp-request>"""

            google_search_prompt = """Perform a Google search:

<mcp-request>
  <tool name="browser_stealth_search">
    <params>
      <query>python programming tutorial</query>
      <max_results>5</max_results>
      <take_screenshot>true</take_screenshot>
      <save_page_source>true</save_page_source>
      <captcha_pause_seconds>60</captcha_pause_seconds>
    </params>
  </tool>
</mcp-request>"""

            # Explicit flash commands for each UI element
            flash_chat_prompt = """Flash the chat conversation area:

<mcp-request>
  <tool name="ui_flash_element">
    <params>
      <element_id>msg-list</element_id>
      <message>This is where your conversation with the AI appears!</message>
      <delay>500</delay>
    </params>
  </tool>
</mcp-request>"""

            flash_app_menu_prompt = """Flash the main app selection menu:

<mcp-request>
  <tool name="ui_flash_element">
    <params>
      <element_id>app-id</element_id>
      <message>This is the main app selection menu!</message>
      <delay>500</delay>
    </params>
  </tool>
</mcp-request>"""

            flash_profile_menu_prompt = """Flash the profile selection menu:

<mcp-request>
  <tool name="ui_flash_element">
    <params>
      <element_id>profile-id</element_id>
      <message>This is the profile selection menu!</message>
      <delay>500</delay>
    </params>
  </tool>
</mcp-request>"""

            flash_send_button_prompt = """Flash the chat send button:

<mcp-request>
  <tool name="ui_flash_element">
    <params>
      <element_id>send-btn</element_id>
      <message>This is the send message button!</message>
      <delay>500</delay>
    </params>
  </tool>
</mcp-request>"""

            flash_nav_bar_prompt = """Flash the top navigation bar:

<mcp-request>
  <tool name="ui_flash_element">
    <params>
      <element_id>nav-group</element_id>
      <message>This is the top navigation bar!</message>
      <delay>500</delay>
    </params>
  </tool>
</mcp-request>"""

            flash_settings_prompt = """Flash the settings gear icon:

<mcp-request>
  <tool name="ui_flash_element">
    <params>
      <element_id>poke-summary</element_id>
      <message>This is the settings gear icon!</message>
      <delay>500</delay>
    </params>
  </tool>
</mcp-request>"""

            # Mode configuration - MCP tools first, then UI flash elements
            mode_config = {
                'cat_fact': {
                    'prompt': cat_fact_prompt,
                    'button_text': 'Get Cat Fact ▸',
                    'button_style': 'margin-top: 1rem; background-color: var(--pico-color-amber-500);',
                    'display_name': 'Cat Fact Test'
                },
                'google_search': {
                    'prompt': google_search_prompt,
                    'button_text': 'Google Search ▸',
                    'button_style': 'margin-top: 1rem; background-color: var(--pico-color-cyan-500);',
                    'display_name': 'Google Search Test'
                },
                'flash_chat': {
                    'prompt': flash_chat_prompt,
                    'button_text': 'Flash Chat Area ▸',
                    'button_style': 'margin-top: 1rem;',
                    'display_name': 'Flash Chat Area'
                },
                'flash_app_menu': {
                    'prompt': flash_app_menu_prompt,
                    'button_text': 'Flash App Menu ▸',
                    'button_style': 'margin-top: 1rem; background-color: var(--pico-color-blue-500);',
                    'display_name': 'Flash App Menu'
                },
                'flash_profile_menu': {
                    'prompt': flash_profile_menu_prompt,
                    'button_text': 'Flash Profile Menu ▸',
                    'button_style': 'margin-top: 1rem; background-color: var(--pico-color-green-500);',
                    'display_name': 'Flash Profile Menu'
                },
                'flash_send_button': {
                    'prompt': flash_send_button_prompt,
                    'button_text': 'Flash Send Button ▸',
                    'button_style': 'margin-top: 1rem; background-color: var(--pico-color-orange-500);',
                    'display_name': 'Flash Send Button'
                },
                'flash_nav_bar': {
                    'prompt': flash_nav_bar_prompt,
                    'button_text': 'Flash Navigation Bar ▸',
                    'button_style': 'margin-top: 1rem; background-color: var(--pico-color-purple-500);',
                    'display_name': 'Flash Navigation Bar'
                },
                'flash_settings': {
                    'prompt': flash_settings_prompt,
                    'button_text': 'Flash Settings Gear ▸',
                    'button_style': 'margin-top: 1rem; background-color: var(--pico-color-red-500);',
                    'display_name': 'Flash Settings Gear'
                }
            }
            
            current_config = mode_config.get(selected_mode, mode_config['flash_chat'])
            
            # Create training envelope for copying
            training_envelope = f"""--- Simon Says MCP Training ---
I need you to execute this exact MCP tool call:

{current_config['prompt']}

Output only the MCP block above. Do not add any other text."""
            
            # Return the updated action content div
            return Div(
                P(f"Ready to execute: {current_config['display_name']}", 
                  cls="text-secondary mb-lg"),
                Div(
                    Button(
                        current_config['button_text'], 
                        type='submit', 
                        cls='primary',
                        **{'hx-on:click': 'this.setAttribute("aria-busy", "true")'}
                    ),
                    Button(
                        '📋 Copy for Chat',
                        type='button',
                        cls='secondary',
                        id=f'copy-mcp-btn-{selected_mode}',
                        style='margin-top: 1rem; background-color: var(--pico-color-grey-500);',
                        **{
                            'data-copy-text': training_envelope,
                            'onclick': f'''
                                const button = this;
                                const originalText = button.textContent;
                                const textToCopy = button.getAttribute('data-copy-text');
                                
                                // Show loading state
                                button.textContent = '⏳ Copying...';
                                button.disabled = true;
                                
                                navigator.clipboard.writeText(textToCopy).then(function() {{
                                    // Show success state
                                    button.textContent = '✅ Copied!';
                                    button.style.backgroundColor = 'var(--pico-color-green-500)';
                                    
                                    // Reset after 3 seconds
                                    setTimeout(function() {{
                                        button.textContent = originalText;
                                        button.style.backgroundColor = 'var(--pico-color-grey-500)';
                                        button.disabled = false;
                                    }}, 3000);
                                }}).catch(function(error) {{
                                    console.error('Error copying to clipboard:', error);
                                    
                                    // Show error state
                                    button.textContent = '❌ Error';
                                    button.style.backgroundColor = 'var(--pico-color-red-500)';
                                    
                                    // Reset after 3 seconds
                                    setTimeout(function() {{
                                        button.textContent = originalText;
                                        button.style.backgroundColor = 'var(--pico-color-grey-500)';
                                        button.disabled = false;
                                    }}, 3000);
                                }});
                            '''
                        }
                    ),
                    style='display: flex; gap: var(--pipulate-gap-sm); align-items: flex-start; flex-wrap: wrap;'
                ),
                id='action-content'
            )
            
        except Exception as e:
            logger.error(f"Error in step_01_change_mode: {str(e)}")
            return P(f"Error changing mode: {str(e)}", style='color: red;')

    # --- STEP_METHODS_INSERTION_POINT ---