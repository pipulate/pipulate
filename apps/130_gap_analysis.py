# File: apps/130_content_gap_analysis.py
import asyncio
from datetime import datetime
from fasthtml.common import * # type: ignore
from loguru import logger
import inspect
from pathlib import Path
import re
import json
from starlette.responses import HTMLResponse
from imports.crud import Step  # 🎯 STANDARDIZED: Import centralized Step definition

ROLES = ['Workshop'] # Defines which user roles can see this plugin

class ContentGapAnalysis:
    """
    Content Gap Analysis Workflow
    
    Analyzes competitor domains to understand their homepage strategies and content positioning.
    Captures redirect chains and final landing pages for competitive intelligence.
    """
    APP_NAME = 'content_gap_internal'
    DISPLAY_NAME = 'Content Gap Analysis 🔍'
    ENDPOINT_MESSAGE = """Enter competitor domains to analyze their homepage strategies and content positioning."""
    TRAINING_PROMPT = """You are assisting with competitive content gap analysis. Help users understand how to input competitor domains and interpret the homepage analysis results including redirect chains and final landing pages."""

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
            Step(id='step_01', done='text_area', show='Competitor Domains', refill=True, transform=lambda prev_value: prev_value.strip() if prev_value else ''),
            Step(
                id='step_02',
                done='placeholder_02',
                show='Placeholder Step 2 (Edit Me)',
                refill=False,
            ),
            Step(
                id='step_03',
                done='placeholder_03',
                show='Placeholder Step 3 (Edit Me)',
                refill=False,
            ),
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
                    'input': f'{step_obj.show}: Please provide the required input.',
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

    def create_prism_widget(self, code, widget_id, language='yaml'):
        """Create a Prism.js syntax highlighting widget with copy functionality."""
        textarea_id = f'{widget_id}_raw_code'
        container = Div(
            Div(
                H5('Structured YAML Analysis:'),
                Textarea(code, id=textarea_id, style='display: none;'),
                Pre(Code(code, cls=f'language-{language}')),
                P('Trailing slash behavior varies: traditional sites (Google, Microsoft) follow old Apache conventions while modern sites (GitHub) skip them for cleaner URLs. The redirect chains and final URLs shown are exactly what httpx reports - servers genuinely differ in their canonicalization strategies.', 
                  cls='text-secondary', 
                  style='font-size: 0.875rem; margin-top: 1rem; font-style: italic;'),
                cls='mt-4'
            ),
            id=widget_id
        )
        init_script = Script(f"""
            (function() {{
                console.log('Prism widget loaded for Content Gap Analysis, ID: {widget_id}');
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
        """ Handles GET request for Step 1: Displays textarea form or completed value. """
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
            locked_msg = f'🔒 Domain analysis is finalized with structured YAML data'
            await self.message_queue.add(wand, locked_msg, verbatim=True)
            widget_id = f"content-gap-yaml-{pipeline_id.replace('-', '_')}-{step_id}-finalized"
            yaml_widget = self.create_prism_widget(user_val, widget_id, 'yaml')
            response_content = Div(Card(H3(f'🔒 {step.show}'), yaml_widget), Div(id=next_step_id, hx_get=f'/{self.app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
            response = HTMLResponse(to_xml(response_content))
            response.headers['HX-Trigger'] = json.dumps({'initializePrism': {'targetId': widget_id}})
            return response
        elif user_val and state.get('_revert_target') != step_id:
            completed_msg = f'Step 1 complete: Domain analysis generated structured YAML data'
            await self.message_queue.add(wand, completed_msg, verbatim=True)
            widget_id = f"content-gap-yaml-{pipeline_id.replace('-', '_')}-{step_id}-completed"
            yaml_widget = self.create_prism_widget(user_val, widget_id, 'yaml')
            content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show} Configured', widget=yaml_widget, steps=steps)
            response_content = Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
            response = HTMLResponse(to_xml(response_content))
            response.headers['HX-Trigger'] = json.dumps({'initializePrism': {'targetId': widget_id}})
            return response
        else:
            if step.refill and user_val:
                display_value = user_val
            else:
                display_value = await self.get_suggestion(step_id, state)
            form_msg = 'Showing text area form. No text has been entered yet.'
            await self.message_queue.add(wand, form_msg, verbatim=True)
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
            explanation = 'Enter competitor domains, one per line. To ADD domains to existing analysis: put new domains at the TOP. To REMOVE: delete the entire domain block from YAML. If YAML gets corrupted, paste your clean domain list and re-run.'
            await self.message_queue.add(wand, explanation, verbatim=True)
            return Div(Card(H3(f'{wand.fmt(step.id)}: Enter {step.show}'), P(explanation, cls='text-secondary'), Form(Div(Textarea(display_value, name=step.done, placeholder=f'Enter competitor domains, one per line...', required=True, autofocus=True, cls='textarea-standard', data_testid='text-area-widget-textarea-input', aria_label='Multi-line text input area for competitor domains', aria_required='true', aria_labelledby=f'{step_id}-form-title', aria_describedby=f'{step_id}-form-instruction'), Div(Button('Analyze Domains ▸', type='submit', cls='primary', **{'hx-on:click': 'this.setAttribute("aria-busy", "true"); this.textContent = "Analyzing domains..."'}), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step.id}_submit', hx_target=f'#{step.id}')), Div(id=next_step_id), id=step.id)

    async def step_01_submit(self, request):
        """Process competitor domains and convert to YAML with homepage analysis."""
        import httpx
        import yaml
        from urllib.parse import urlparse, urljoin
        import time
        
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        
        if step.done == 'finalized':
            return await wand.handle_finalized_step(pipeline_id, step_id, steps, app_name, self)
        
        form = await request.form()
        user_val = form.get(step.done, '').strip()
        
        # 80/20 Domain Management: Extract domains from ANY format (raw text + YAML)
        domains = []
        existing_yaml_domains = []
        new_raw_domains = []
        
        # Step 1: Try to extract existing domains from YAML structure
        if user_val.strip().startswith('analysis_metadata:') or 'domains:' in user_val:
            try:
                yaml_data = yaml.safe_load(user_val)
                if isinstance(yaml_data, dict) and 'domains' in yaml_data:
                    existing_yaml_domains = [domain_info['original_domain'] for domain_info in yaml_data['domains']]
                    await self.message_queue.add(wand, f'Found existing YAML with {len(existing_yaml_domains)} domains', verbatim=True)
            except Exception as e:
                await self.message_queue.add(wand, f'⚠️ YAML parsing failed: {str(e)}. Looking for raw domains...', verbatim=True)
        
        # Step 2: Look for raw domains anywhere in the input (TOP = new additions)
        for line in user_val.splitlines():
            line = line.strip()
            # STRICT domain detection: avoid YAML structure completely
            if (line and '.' in line and 
                not line.endswith(':') and 
                not line.startswith('-') and
                not line.startswith('analysis_') and
                not line.startswith('domains:') and
                not ':' in line and  # Kill any YAML key:value pairs
                not '|' in line and
                not "'" in line and  # Kill YAML quoted values
                not '"' in line and  # Kill JSON quoted values  
                not 'timestamp' in line and
                not 'created' in line and
                not 'original_' in line and
                not 'final_' in line and
                not 'server:' in line and
                not 'status:' in line and
                not 'redirect_' in line and
                not 'response_' in line and
                not 'content_' in line and
                len(line) < 50 and   # Shorter length limit
                len(line) > 3 and
                not line.replace('.', '').isdigit()):  # Kill pure timestamps
                # Clean up common artifacts  
                clean_domain = line.replace('http://', '').replace('https://', '').replace('www.', '').split('/')[0]
                # Final validation: must look like a domain (letters + dots only)
                if (clean_domain and 
                    clean_domain not in existing_yaml_domains and
                    clean_domain.count('.') >= 1 and
                    clean_domain.count('.') <= 3 and
                    not clean_domain.startswith('.') and
                    not clean_domain.endswith('.') and
                    clean_domain.replace('.', '').replace('-', '').isalnum()):
                    new_raw_domains.append(clean_domain)
        
        # Parse existing YAML to get already processed domains (CRITICAL FOR DATA PRESERVATION)
        existing_data = wand.get_step_data(pipeline_id, step_id, {})
        existing_yaml = existing_data.get(step.done, '')
        processed_domains = {}
        if existing_yaml:
            try:
                existing_structure = yaml.safe_load(existing_yaml)
                if isinstance(existing_structure, dict) and 'domains' in existing_structure:
                    for domain_info in existing_structure['domains']:
                        processed_domains[domain_info['original_domain']] = domain_info
                await self.message_queue.add(wand, f'Found {len(processed_domains)} previously analyzed domains', verbatim=True)
            except Exception as e:
                await self.message_queue.add(wand, f'Could not parse existing data, starting fresh: {str(e)}', verbatim=True)
        
        # Step 3: Combine ALL domains (existing from DB + YAML + new raw)
        all_existing_domains = list(processed_domains.keys())  # From database - CRITICAL!
        domains = all_existing_domains + existing_yaml_domains + new_raw_domains
        
        # Remove duplicates while preserving order
        seen = set()
        unique_domains = []
        for domain in domains:
            if domain not in seen:
                seen.add(domain)
                unique_domains.append(domain)
        domains = unique_domains
        
        if new_raw_domains:
            await self.message_queue.add(wand, f'➕ Found {len(new_raw_domains)} new domains to analyze: {", ".join(new_raw_domains)}', verbatim=True)
        if all_existing_domains and new_raw_domains:
            await self.message_queue.add(wand, f'📋 Total: {len(all_existing_domains)} existing + {len(new_raw_domains)} new = {len(domains)} domains', verbatim=True)
        elif not domains:
            # Fallback: treat entire input as raw domain list
            domains = [line.strip() for line in user_val.splitlines() if line.strip()]
        
        await self.message_queue.add(wand, f'Processing {len(domains)} domains...', verbatim=True)
        
        if not domains:
            if 'analysis_metadata:' in user_val or 'domains:' in user_val:
                error_msg = '🔧 No domains found. YAML may be corrupted. Paste your clean competitor domain list (one per line) and try again.'
            else:
                error_msg = 'Please enter at least one domain'
            await self.message_queue.add(wand, error_msg, verbatim=True)
            return wand.create_error_form(error_msg, step_id, app_name)
        
        # Database domains already loaded above - no need to duplicate
        
        # 🚀 AI BROWSER AUTOMATION ENHANCEMENT 🚀
        # Let's use the revolutionary browser automation to actually VISIT and ANALYZE each domain!
        await self.message_queue.add(wand, f'🤖 Starting AI browser automation analysis...', verbatim=True)
        
        # Analyze each domain with both HTTP and AI browser automation
        analysis_results = []
        new_domains_processed = 0
        
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            follow_redirects=True,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; ContentGapAnalyzer/1.0)'}
        ) as client:
            
            for domain in domains:
                # Skip if already processed (idempotency)
                if domain in processed_domains:
                    analysis_results.append(processed_domains[domain])
                    continue
                
                # Check for recent failures (efficiency - don't retry immediately)
                failure_key = f'_failure_{domain}'
                if failure_key in processed_domains:
                    failure_info = processed_domains[failure_key]
                    # Skip if failed within last hour
                    if time.time() - failure_info.get('timestamp', 0) < 3600:
                        analysis_results.append(failure_info)
                        continue
                
                await self.message_queue.add(wand, f'🔍 Analyzing {domain}...', verbatim=True)
                
                domain_info = {
                    'original_domain': domain,
                    'timestamp': time.time(),
                    'analysis_date': datetime.now().isoformat()
                }
                
                try:
                    # 🤖 AI BROWSER AUTOMATION: Use the AI's eyes to actually SEE the homepage!
                    browser_analysis = None
                    visual_intelligence = None
                    
                    # Step 1: AI Browser Scrape (AI's EYES)
                    try:
                        scrape_url = f'https://{domain}'
                        await self.message_queue.add(wand, f'👁️ AI Browser Vision: Capturing {scrape_url}...', verbatim=True)
                        
                        # Call the browser_scrape_page MCP tool DIRECTLY (not via HTTP)
                        from tools.mcp_tools import browser_scrape_page, browser_analyze_scraped_page
                        
                        scrape_params = {
                            "url": scrape_url,
                            "wait_seconds": 3,
                            "take_screenshot": True,
                            "update_looking_at": True
                        }
                        
                        # Direct MCP call to browser automation
                        browser_result = await browser_scrape_page(scrape_params)
                        
                        if browser_result.get('success'):
                            browser_analysis = browser_result
                            page_title = browser_result.get("page_info", {}).get("title", "")
                            await self.message_queue.add(wand, f'✅ AI Vision captured: {page_title[:50]}...', verbatim=True)
                            
                            # Step 2: AI Brain Analysis (AI's BRAIN) 
                            analyze_params = {"analysis_type": "all"}
                            brain_result = await _browser_analyze_scraped_page(analyze_params)
                            
                            if brain_result.get('success'):
                                visual_intelligence = brain_result
                                target_count = brain_result.get('target_count', 0)
                                form_count = brain_result.get('form_count', 0)
                                await self.message_queue.add(wand, f'🧠 AI Brain Analysis: {target_count} automation targets, {form_count} forms detected', verbatim=True)
                        else:
                            await self.message_queue.add(wand, f'⚠️ AI Browser automation failed: {browser_result.get("error", "Unknown error")}', verbatim=True)
                        
                    except Exception as browser_error:
                        await self.message_queue.add(wand, f'⚠️ AI Browser automation error: {str(browser_error)[:100]}', verbatim=True)
                        
                    # Original HTTP analysis (keeping for comparison)
                    # Try both http and https
                    urls_to_try = [f'https://{domain}', f'http://{domain}']
                    
                    for url in urls_to_try:
                        try:
                            response = await client.get(url)
                            
                            # Success! Extract useful information
                            final_url = str(response.url)
                            parsed_final = urlparse(final_url)
                            
                            # Capture detailed redirect chain for transparency
                            redirect_chain = []
                            for hist_resp in response.history:
                                redirect_chain.append({
                                    'from_url': str(hist_resp.url),
                                    'to_url': hist_resp.headers.get('location', 'unknown'),
                                    'status_code': hist_resp.status_code
                                })
                            
                            domain_info.update({
                                'status': 'success',
                                'original_url': url,
                                'final_url': final_url,
                                'final_domain': parsed_final.netloc,
                                'response_code': response.status_code,
                                'redirect_hops': len(response.history),
                                'redirect_chain': redirect_chain if redirect_chain else None,
                                'content_type': response.headers.get('content-type', '').split(';')[0],
                                'server': response.headers.get('server', 'unknown')[:50],  # Truncate long server strings
                                'title': None  # Will extract if HTML
                            })
                            
                            # Extract page title if it's HTML
                            if 'text/html' in response.headers.get('content-type', ''):
                                try:
                                    content = response.text[:2048]  # Only check first 2K chars for title
                                    import re
                                    title_match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.IGNORECASE)
                                    if title_match:
                                        domain_info['title'] = title_match.group(1).strip()[:100]  # Truncate long titles
                                except:
                                    pass
                            
                            # 🚀 ENHANCE WITH AI BROWSER AUTOMATION RESULTS 🚀
                            if browser_analysis and visual_intelligence:
                                # Add AI-powered competitive intelligence
                                domain_info.update({
                                    'ai_browser_analysis': {
                                        'success': True,
                                        'ai_captured_title': browser_analysis.get('page_info', {}).get('title', ''),
                                        'ai_screenshot_path': browser_analysis.get('looking_at_files', {}).get('screenshot', ''),
                                        'ai_backup_id': browser_analysis.get('backup_id', ''),
                                        'automation_intelligence': {
                                            'total_targets': visual_intelligence.get('target_count', 0),
                                            'high_priority_targets': visual_intelligence.get('high_priority_targets', 0),
                                            'forms_detected': visual_intelligence.get('form_count', 0),
                                            'automation_ready': visual_intelligence.get('high_priority_targets', 0) > 0,
                                            'interaction_opportunities': len(visual_intelligence.get('forms', [])) + visual_intelligence.get('target_count', 0)
                                        }
                                    }
                                })
                                await self.message_queue.add(wand, f'🎯 AI Enhanced: {domain_info["ai_browser_analysis"]["automation_intelligence"]["total_targets"]} targets, automation_ready: {domain_info["ai_browser_analysis"]["automation_intelligence"]["automation_ready"]}', verbatim=True)
                            else:
                                # AI automation failed, mark accordingly  
                                domain_info.update({
                                    'ai_browser_analysis': {
                                        'success': False,
                                        'error': 'AI browser automation unavailable or failed',
                                        'fallback_to_http': True
                                    }
                                })
                            
                            # Show detailed redirect summary
                            if domain_info['redirect_hops'] > 0:
                                trailing_slash_note = " (with trailing /)" if final_url.endswith('/') and not final_url.endswith('//') else ""
                                redirect_summary = f"✓ {domain} → {final_url}{trailing_slash_note} ({domain_info['redirect_hops']} hops)"
                                
                                # Show the redirect chain for transparency
                                if redirect_chain:
                                    chain_details = " → ".join([f"{hop['from_url']} ({hop['status_code']})" for hop in redirect_chain])
                                    chain_details += f" → {final_url} (200)"
                                    await self.message_queue.add(wand, f"  Chain: {chain_details}", verbatim=True)
                            else:
                                trailing_slash_note = " (with trailing /)" if final_url.endswith('/') and not final_url.endswith('//') else ""
                                redirect_summary = f"✓ {domain} (direct) → {final_url}{trailing_slash_note}"
                                
                            await self.message_queue.add(wand, redirect_summary, verbatim=True)
                            break  # Success, don't try other protocol
                            
                        except httpx.RequestError:
                            continue  # Try next URL
                    
                    else:
                        # Both HTTP and HTTPS failed
                        domain_info.update({
                            'status': 'failed',
                            'error': 'Connection failed for both HTTP and HTTPS',
                            'final_url': None,
                            'final_domain': domain
                        })
                        await self.message_queue.add(wand, f"❌ {domain} - Connection failed", verbatim=True)
                        
                except Exception as e:
                    domain_info.update({
                        'status': 'error',
                        'error': str(e)[:200],  # Truncate long error messages
                        'final_url': None,
                        'final_domain': domain
                    })
                    await self.message_queue.add(wand, f"❌ {domain} - {str(e)[:100]}", verbatim=True)
                
                analysis_results.append(domain_info)
                new_domains_processed += 1
                
                # Small delay to be respectful
                await asyncio.sleep(0.5)
        
        # Create YAML structure
        yaml_structure = {
            'analysis_metadata': {
                'created': datetime.now().isoformat(),
                'total_domains': len(domains),
                'successful_checks': len([d for d in analysis_results if d.get('status') == 'success']),
                'failed_checks': len([d for d in analysis_results if d.get('status') in ['failed', 'error']]),
                'new_domains_processed': new_domains_processed
            },
            'domains': analysis_results
        }
        
        # Convert to clean YAML
        yaml_output = yaml.dump(yaml_structure, default_flow_style=False, sort_keys=False, allow_unicode=True)
        
        # Save the YAML as the step data
        await wand.set_step_data(pipeline_id, step_id, yaml_output, steps)
        
        success_count = yaml_structure['analysis_metadata']['successful_checks']
        total_count = yaml_structure['analysis_metadata']['total_domains']
        preserved_count = len(all_existing_domains)
        
        if preserved_count > 0 and new_domains_processed > 0:
            await self.message_queue.add(wand, f'✅ Analysis complete: {preserved_count} existing domains preserved + {new_domains_processed} new domains analyzed = {total_count} total ({success_count} successful)', verbatim=True)
        elif preserved_count > 0:
            await self.message_queue.add(wand, f'✅ Analysis complete: {preserved_count} existing domains preserved (no new domains added)', verbatim=True)
        else:
            await self.message_queue.add(wand, f'✅ Analysis complete: {success_count}/{total_count} domains processed successfully', verbatim=True)
        
        if wand.check_finalize_needed(step_index, steps):
            finalize_msg = self.step_messages['finalize']['ready']
            await self.message_queue.add(wand, finalize_msg, verbatim=True)
        
        # Display YAML with PrismJS syntax highlighting
        widget_id = f"content-gap-yaml-{pipeline_id.replace('-', '_')}-{step_id}"
        yaml_widget = self.create_prism_widget(yaml_output, widget_id, 'yaml')
        content_container = wand.display_revert_widget(
            step_id=step_id, 
            app_name=app_name, 
            message=f'Domain Analysis Complete ({success_count}/{total_count} successful)', 
            widget=yaml_widget, 
            steps=steps
        )
        
        response_content = Div(
            content_container, 
            Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), 
            id=step_id
        )
        
        # Return HTMLResponse with HX-Trigger to initialize Prism
        response = HTMLResponse(to_xml(response_content))
        response.headers['HX-Trigger'] = json.dumps({'initializePrism': {'targetId': widget_id}})
        return response
    # --- END_STEP_BUNDLE: step_01 ---


    # --- START_STEP_BUNDLE: step_02 ---
    async def step_02(self, request):
        """Handles GET request for Placeholder Step 2 (Edit Me)."""
        wand, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, self.app_name
        step_id = "step_02"
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        # Determine next_step_id dynamically based on runtime position in steps list
        next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
        pipeline_id = db.get("pipeline_id", "unknown")
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        current_value = step_data.get(step.done, "") # 'step.done' will be like 'placeholder_02'
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
            return Div(
                Card(
                    H3(f"{step.show}"),
                    P("This is a new placeholder step. Customize its input form as needed. Click Proceed to continue."),
                    Form(
                        # Example: Hidden input to submit something for the placeholder
                        Input(type="hidden", name=step.done, value="Placeholder Value for Placeholder Step 2 (Edit Me)"),
                        Button("Next ▸", type="submit", cls="primary"),
                        hx_post=f"/{app_name}/{step_id}_submit", hx_target=f"#{step_id}"
                    )
                ),
                Div(id=next_step_id), # Placeholder for next step, no trigger here
                id=step_id
            )


    async def step_02_submit(self, request):
        """Process the submission for Placeholder Step 2 (Edit Me)."""
        wand, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, self.app_name
        step_id = "step_02"
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
        pipeline_id = db.get("pipeline_id", "unknown")
        
        form_data = await request.form()
        # For a placeholder, get value from the hidden input or use a default
        value_to_save = form_data.get(step.done, f"Default value for {step.show}") 
        await wand.set_step_data(pipeline_id, step_id, value_to_save, steps)
        
        wand.append_to_history(f"[WIDGET CONTENT] {step.show}:\n{value_to_save}")
        wand.append_to_history(f"[WIDGET STATE] {step.show}: Step completed")
        
        await self.message_queue.add(wand, f"{step.show} complete.", verbatim=True)
        
        return Div(
            wand.display_revert_header(step_id=step_id, app_name=app_name, message=f"{step.show}: Complete", steps=steps),
            Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
            id=step_id
        )
    # --- END_STEP_BUNDLE: step_02 ---



    # --- START_STEP_BUNDLE: step_03 ---
    async def step_03(self, request):
        """Handles GET request for Placeholder Step 3 (Edit Me)."""
        wand, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, self.app_name
        step_id = "step_03"
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        # Determine next_step_id dynamically based on runtime position in steps list
        next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
        pipeline_id = db.get("pipeline_id", "unknown")
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        current_value = step_data.get(step.done, "") # 'step.done' will be like 'placeholder_03'
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
            return Div(
                Card(
                    H3(f"{step.show}"),
                    P("This is a new placeholder step. Customize its input form as needed. Click Proceed to continue."),
                    Form(
                        # Example: Hidden input to submit something for the placeholder
                        Input(type="hidden", name=step.done, value="Placeholder Value for Placeholder Step 3 (Edit Me)"),
                        Button("Next ▸", type="submit", cls="primary"),
                        hx_post=f"/{app_name}/{step_id}_submit", hx_target=f"#{step_id}"
                    )
                ),
                Div(id=next_step_id), # Placeholder for next step, no trigger here
                id=step_id
            )


    async def step_03_submit(self, request):
        """Process the submission for Placeholder Step 3 (Edit Me)."""
        wand, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, self.app_name
        step_id = "step_03"
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
        pipeline_id = db.get("pipeline_id", "unknown")
        
        form_data = await request.form()
        # For a placeholder, get value from the hidden input or use a default
        value_to_save = form_data.get(step.done, f"Default value for {step.show}") 
        await wand.set_step_data(pipeline_id, step_id, value_to_save, steps)
        
        wand.append_to_history(f"[WIDGET CONTENT] {step.show}:\n{value_to_save}")
        wand.append_to_history(f"[WIDGET STATE] {step.show}: Step completed")
        
        await self.message_queue.add(wand, f"{step.show} complete.", verbatim=True)
        
        return Div(
            wand.display_revert_header(step_id=step_id, app_name=app_name, message=f"{step.show}: Complete", steps=steps),
            Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
            id=step_id
        )
    # --- END_STEP_BUNDLE: step_03 ---


    # --- STEP_METHODS_INSERTION_POINT ---