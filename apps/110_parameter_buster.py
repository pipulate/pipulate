import asyncio
import gzip
import json
import logging
import os
import pickle
import re
import shutil
import socket
import time
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse, quote
from typing import Optional
import httpx
import pandas as pd
from fasthtml.common import *
from loguru import logger
from imports.crud import Step  # 🎯 STANDARDIZED: Import centralized Step definition

import config

ROLES = ['Botify Employee']
TOKEN_FILE = 'botify_token.txt'
import asyncio
import gzip
import json
import logging
import os
import pickle
import re
import shutil
import socket
import time
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse, quote
from typing import Optional
import httpx
import pandas as pd
from fasthtml.common import *
from loguru import logger

class ParameterBuster:
    """
    Botify Parameter Buster - Trifecta Derivative for Compliance Analysis
    
    📚 Complete documentation: helpers/docs_sync/botify_workflow_patterns.md
    
    Specialized Botify workflow focusing on parameter compliance analysis.
    Downloads crawl analysis, web logs, and Search Console data with 'Not Compliant' focus.
    
    🔧 Template Config: {'analysis': 'Not Compliant'} (compliance focus)
    🏗️ Base Template: 400_botify_trifecta.py
    🎯 WET Inheritance: Auto-updated via helpers/rebuild_trifecta_derivatives.sh
    """
    APP_NAME = 'param_buster'
    DISPLAY_NAME = 'Parameter Buster 🔨'
    ENDPOINT_MESSAGE = """Optimize crawl budget by identifying wasteful URL parameters. Analyzes your site's parameter usage patterns to massage URLs into more productive shape for search engine crawling efficiency through a PageWorkers optimization."""
    TRAINING_PROMPT = """This workflow helps users analyze URL parameters and tracking codes. It uses the widget_container pattern to display parameter breakdowns and provides insights into URL structure and tracking mechanisms."""
    # Query Templates - Extracted from build_exports for reusability
    #
    # NOTE: Web Logs are intentionally NOT templated (KISS principle)
    # ================================================================
    # Web logs queries are simple, consistent, and rarely change:
    # - Always same fields: ['url', 'crawls.google.count']
    # - Always same filter: crawls.google.count > 0
    # - Uses legacy BQLv1 structure (different from crawl/GSC)
    # - Different API endpoint (app.botify.com vs api.botify.com)
    #
    # Adding web logs to templates would require:
    # - Separate BQLv1 template system
    # - Handling different endpoint/payload structures
    # - More complexity for minimal benefit
    #
    # Current approach: hardcode the simple query inline where used.
    # This is a perfect example of knowing when NOT to abstract.
    QUERY_TEMPLATES = {
        'Crawl Basic': {
            'name': 'Basic Crawl Data',
            'description': 'URL, HTTP status, and page title',
            'export_type': 'crawl_attributes',
            'user_message': 'This will download basic crawl data including URLs, HTTP status codes, and page titles.',
            'button_label_suffix': 'Basic Attributes',
            'query': {
                'dimensions': ['{collection}.url', '{collection}.http_code', '{collection}.metadata.title.content'],
                'filters': {'field': '{collection}.http_code', 'predicate': 'eq', 'value': 200}
            }
        },
        'Not Compliant': {
            'name': 'Non-Compliant Pages',
            'description': 'URLs with compliance issues and their reasons',
            'export_type': 'crawl_attributes',
            'user_message': 'This will download a list of non-compliant URLs with their compliance reasons.',
            'button_label_suffix': 'Non-Compliant Attributes',
            'query': {
                'dimensions': ['{collection}.url', '{collection}.compliant.main_reason', '{collection}.compliant.detailed_reason'],
                'metrics': [{'function': 'count', 'args': ['{collection}.url']}],
                'filters': {'field': '{collection}.compliant.is_compliant', 'predicate': 'eq', 'value': False}
            },
            'qualifier_config': {
                'enabled': True,
                'qualifier_bql_template': {
                    "dimensions": [],
                    "metrics": [{"function": "count", "args": ["{collection}.url"]}],
                    "filters": {"field": "{collection}.compliant.is_compliant", "predicate": "eq", "value": False}
                },
                'parameter_placeholder_in_main_query': None,  # No substitution needed
                'iterative_parameter_name': 'non_compliant_url_count',
                'target_metric_path': ["results", 0, "metrics", 0],
                'max_value_threshold': 5000000,  # Allow larger attribute exports
                'iteration_range': (1, 1, 1),  # Non-iterative, just one check
                'user_message_running': 'Estimating size of Non-Compliant Pages export...',
                'user_message_found': 'Non-Compliant Pages export estimated at {metric_value:,} URLs. Proceeding.',
                'user_message_threshold_exceeded': 'Warning: Non-Compliant Pages export is very large ({metric_value:,} URLs). Proceeding with caution.'
            }
        },
        'Link Graph Edges': {
            'name': 'Link Graph Edges',
            'description': 'Exports internal link graph (source URL -> target URL). Automatically finds optimal depth for ~1M edges.',
            'export_type': 'link_graph_edges',
            'user_message': 'This will download the site\'s internal link graph (source-target pairs). An optimal depth will be found first.',
            'button_label_suffix': 'Link Graph',
            'query': {
                'dimensions': ['{collection}.url', '{collection}.outlinks_internal.graph.url'],
                'metrics': [],
                'filters': {'field': '{collection}.depth', 'predicate': 'lte', 'value': '{OPTIMAL_DEPTH}'}
            },
            'qualifier_config': {
                'enabled': True,
                'qualifier_bql_template': {
                    "dimensions": [],
                    "metrics": [{"function": "sum", "args": ["{collection}.outlinks_internal.nb.total"]}],
                    "filters": {"field": "{collection}.depth", "predicate": "lte", "value": "{ITERATION_VALUE}"}
                },
                'parameter_placeholder_in_main_query': '{OPTIMAL_DEPTH}',
                'iterative_parameter_name': 'depth',
                'target_metric_path': ["results", 0, "metrics", 0],
                'max_value_threshold': 1000000,
                'iteration_range': (1, 10, 1),  # (start, end, step_increment)
                'user_message_running': '🔍 Finding optimal depth for Link Graph Edges...',
                'user_message_found': '🎯 Optimal depth for Link Graph: {param_value} (for {metric_value:,} edges).',
                'user_message_threshold_exceeded': 'Edge count exceeds threshold even at shallowest depth. Proceeding with depth 1.'
            }
        },
        'GSC Performance': {
            'name': 'GSC Performance',
            'description': 'Impressions, clicks, CTR, and position',
            'export_type': 'gsc_data',
            'user_message': 'This will download Search Console performance data including impressions, clicks, CTR, and average position.',
            'button_label_suffix': 'GSC Performance',
            'query': {
                'dimensions': ['url'],
                'metrics': [
                    {'field': 'search_console.period_0.count_impressions', 'name': 'Impressions'},
                    {'field': 'search_console.period_0.count_clicks', 'name': 'Clicks'},
                    {'field': 'search_console.period_0.ctr', 'name': 'CTR'},
                    {'field': 'search_console.period_0.avg_position', 'name': 'Avg. Position'}
                ],
                'sort': [{'type': 'metrics', 'index': 0, 'order': 'desc'}]
            }
        }
    }
    # Template Configuration - Controls which templates are actually used
    # ===================================================================
    # Change these values to switch between different query templates
    # without modifying the workflow logic.
    TEMPLATE_CONFIG = {
        'crawl': 'Not Compliant',   # Options: 'Crawl Basic', 'Not Compliant', 'Link Graph Edges'
        'gsc': 'GSC Performance'       # Options: 'GSC Performance'
    }
    # Optional Features Configuration
    # ===============================
    # Controls optional UI features that can be enabled/disabled
    FEATURES_CONFIG = {
        'enable_skip_buttons': True,  # Set to False to disable skip buttons on steps 3 & 4
    }
    # --- START_CLASS_ATTRIBUTES_BUNDLE ---
    # Additional class-level constants can be merged here by manage_class_attributes.py
    # --- END_CLASS_ATTRIBUTES_BUNDLE ---
    # Toggle Method Configuration - Maps step IDs to their specific data extraction logic
    # ==================================================================================
    TOGGLE_CONFIG = {
        'step_02': {
            'data_key': 'analysis_result',
            'status_field': 'download_complete',
            'success_text': 'HAS crawl analysis',
            'failure_text': 'does NOT have crawl analysis',
            'error_prefix': 'FAILED to download crawl analysis'
        },
        'step_03': {
            'data_key': 'check_result',
            'status_field': 'has_logs',
            'success_text': 'HAS web logs',
            'failure_text': 'does NOT have web logs',
            'error_prefix': 'FAILED to download web logs',
            'status_prefix': 'Project '
        },
        'step_04': {
            'data_key': 'check_result',
            'status_field': 'has_search_console',
            'success_text': 'HAS Search Console data',
            'failure_text': 'does NOT have Search Console data',
            'error_prefix': 'FAILED to download Search Console data',
            'status_prefix': 'Project '
        },
        'step_05': {
            'simple_content': 'Placeholder step completed'
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
        # Access centralized configuration through dependency injection
        self.ui = wand.get_ui_constants()
        self.config = wand.get_config()
        # Build step names dynamically based on template configuration
        crawl_template = self.get_configured_template('crawl')
        gsc_template = self.get_configured_template('gsc')

        # steps = [Step(id='step_01', done='botify_project', show='Botify Project URL', refill=True), Step(id='step_02', done='analysis_selection', show='Download Crawl Analysis', refill=False), Step(id='step_03', done='weblogs_check', show='Download Web Logs', refill=False), Step(id='step_04', done='search_console_check', show='Download Search Console', refill=False), Step(id='step_05', done='placeholder', show='Count Parameters Per Source', refill=True), Step(id='step_06', done='parameter_optimization', show='Parameter Optimization', refill=True), Step(id='step_07', done='robots_txt', show='Instructions & robots.txt', refill=False)]
        steps = [
            Step(id='step_01', done='botify_project', show='Botify Project URL', refill=True),
            Step(id='step_02', done='analysis_selection', show=f'Download Crawl Analysis: {crawl_template}', refill=False),
            Step(id='step_03', done='weblogs_check', show='Download Web Logs', refill=False),
            Step(id='step_04', done='search_console_check', show=f'Download Search Console: {gsc_template}', refill=False),
            Step(id='step_05', done='placeholder', show='Count Parameters Per Source', refill=True),
            Step(id='step_06', done='parameter_optimization', show='Parameter Optimization', refill=True),
            Step(id='step_07', done='robots_txt', show='Instructions & robots.txt', refill=False),
        ]
        
        # --- STEPS_LIST_INSERTION_POINT ---
        steps.append(Step(id='finalize', done='finalized', show='Finalize', refill=False))
        self.steps = steps  # Update self.steps to include finalize step
        self.steps_indices = {step.id: i for i, step in enumerate(steps)}
        
        # Register routes using centralized helper (AFTER finalize step is added)
        pipulate.register_workflow_routes(self)
        
        # Register custom routes specific to this workflow
        app.route(f'/{app_name}/step_02_process', methods=['POST'])(self.step_02_process)
        app.route(f'/{app_name}/step_03_process', methods=['POST'])(self.step_03_process)
        app.route(f'/{app_name}/step_04_complete', methods=['POST'])(self.step_04_complete)
        app.route(f'/{app_name}/step_05_process', methods=['POST'])(self.step_05_process)
        app.route(f'/{app_name}/parameter_preview', methods=['POST'])(self.parameter_preview)
        app.route(f'/{app_name}/toggle', methods=['GET'])(self.common_toggle)
        app.route(f'/{app_name}/update_button_text', methods=['POST'])(self.update_button_text)
        
        self.step_messages = {'finalize': {'ready': self.ui['MESSAGES']['ALL_STEPS_COMPLETE'], 'complete': f'Workflow finalized. Use {self.ui["BUTTON_LABELS"]["UNLOCK"]} to make changes.'}, 'step_02': {'input': f"❔{wand.fmt('step_02')}: Please select a crawl analysis for this project.", 'complete': '📊 Crawl analysis download complete. Continue to next step.'}}
        for step in steps:
            if step.id not in self.step_messages:
                self.step_messages[step.id] = {'input': f'❔{wand.fmt(step.id)}: Please complete {step.show}.', 'complete': f'✳️ {step.show} complete. Continue to next step.'}
        self.step_messages['step_04'] = {'input': f"❔{wand.fmt('step_04')}: Please check if the project has Search Console data.", 'complete': 'Search Console check complete. Continue to next step.'}
        self.step_messages['step_03'] = {'input': f"❔{wand.fmt('step_03')}: Please check if the project has web logs available.", 'complete': '📋 Web logs check complete. Continue to next step.'}
        self.step_messages['step_05'] = {'input': f"❔{wand.fmt('step_05')}: Ready to count parameters from downloaded data.", 'complete': 'Parameter counting is complete.'}
        self.step_messages['step_06'] = {'input': f"❔{wand.fmt('step_06')}: Ready to configure parameter optimization.", 'complete': 'Parameter optimization configured.'}
        self.step_messages['step_07'] = {'input': f"❔{wand.fmt('step_07')}: Ready to generate instructions and robots.txt.", 'complete': 'Instructions generated.'}

    def get_available_templates_for_data_type(self, data_type):
        """Get available query templates for a specific data type."""
        if data_type == 'crawl':
            return ['Crawl Basic', 'Not Compliant']
        elif data_type == 'gsc':
            return ['GSC Performance']
        else:
            return []

    def get_configured_template(self, data_type):
        """Get the configured template for a specific data type."""
        return self.TEMPLATE_CONFIG.get(data_type)

    def apply_template(self, template_key, collection=None):
        """Apply a query template with collection substitution."""
        if template_key not in self.QUERY_TEMPLATES:
            raise ValueError(f"Unknown template: {template_key}")
        template = self.QUERY_TEMPLATES[template_key].copy()
        query = template['query'].copy()
        if collection and '{collection}' in str(query):
            # Simple string replacement for collection placeholders
            query_str = json.dumps(query)
            query_str = query_str.replace('{collection}', collection)
            query = json.loads(query_str)
        return query

    def list_available_templates(self):
        """List all available query templates with descriptions."""
        return {
            key: {
                'name': template['name'],
                'description': template['description']
            }
            for key, template in self.QUERY_TEMPLATES.items()
        }

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
        """Handles GET request to show Finalize button and POST request to lock the workflow.
        # PATTERN NOTE: The finalize step is the final destination of the chain reaction
        # and should be triggered by the last content step's submit handler.
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        finalize_step = steps[-1]
        finalize_data = wand.get_step_data(pipeline_id, finalize_step.id, {})
        if request.method == 'GET':
            if finalize_step.done in finalize_data:
                return Card(H3(self.ui['MESSAGES']['WORKFLOW_LOCKED']), Form(Button(self.ui['BUTTON_LABELS']['UNLOCK'], type='submit', cls=self.ui['BUTTON_STYLES']['OUTLINE']), hx_post=f'/{app_name}/unfinalize', hx_target=f'#{app_name}-container'), id=finalize_step.id)
            else:
                all_steps_complete = all((wand.get_step_data(pipeline_id, step.id, {}).get(step.done) for step in steps[:-1]))
                if all_steps_complete:
                    await self.message_queue.add(wand, 'All steps are complete. You can now finalize the workflow or revert to any step to make changes.', verbatim=True)
                    return Card(H3(self.ui['MESSAGES']['FINALIZE_QUESTION']), P(self.ui['MESSAGES']['FINALIZE_HELP'], cls='text-secondary'), Form(Button(self.ui['BUTTON_LABELS']['FINALIZE'], type='submit', cls=self.ui['BUTTON_STYLES']['PRIMARY']), hx_post=f'/{app_name}/finalize', hx_target=f'#{app_name}-container'), id=finalize_step.id)
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
        await self.message_queue.add(wand, self.ui['MESSAGES']['WORKFLOW_UNLOCKED'], verbatim=True)
        return wand.run_all_cells(app_name, steps)

    async def get_suggestion(self, step_id, state):
        """Gets a suggested input value for a step, often using the previous step's transformed output."""
        wand, db, steps = (self.pipulate, self.pipulate.db, self.steps)
        step = next((s for s in steps if s.id == step_id), None)
        if not step or not step.transform:
            return ''
        prev_index = self.steps_indices[step_id] - 1
        if prev_index < 0:
            return ''
        prev_step = steps[prev_index]
        prev_data = wand.get_step_data(wand.db['pipeline_id'], prev_step.id, {})
        prev_value = prev_data.get(prev_step.done, '')
        return step.transform(prev_value) if prev_value else ''

    async def handle_revert(self, request):
        """Handles POST request to revert to a previous step, clearing subsequent step data."""
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
        await self.message_queue.add(wand, f'↩️ Reverted to {step_id}. All subsequent data has been cleared.', verbatim=True)
        return wand.run_all_cells(app_name, steps)

    async def step_01(self, request):
        """Handles GET request for Botify URL input widget.
        # STEP PATTERN: GET handler returns current step UI + empty placeholder for next step
        # Important: The next step div should NOT have hx_trigger here, only in the submit handler
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        project_data_str = step_data.get(step.done, '')
        project_data = json.loads(project_data_str) if project_data_str else {}
        project_url = project_data.get('url', '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and project_data:
            return Div(Card(H3(f'🔒 {step.show}'), Div(P(f"Project: {project_data.get('project_name', '')}"), Small(project_url, style='word-break: break-all;'), cls='custom-card-padding-bg')), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        elif project_data and state.get('_revert_target') != step_id:
            project_name = project_data.get('project_name', '')
            username = project_data.get('username', '')
            project_info = Div(H4(f'Project: {project_name}'), P(f'Username: {username}'), Small(project_url, style='word-break: break-all;'), style='padding: 10px; background: #f8f9fa; border-radius: 5px;')
            return Div(wand.display_revert_header(step_id=step_id, app_name=app_name, message=f'{step.show}: {project_url}', steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        else:
            display_value = project_url if step.refill and project_url else ''
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
            return Div(
                Card(
                    H3(f'{step.show}'),
                    P('Enter a Botify project URL:'),
                    Small(
                        'Example: ',
                        Span(
                            'https://app.botify.com/uhnd-com/uhnd.com-demo-account/ <--click for example',
                            id='copy-example-url',
                            style='cursor: pointer; color: #888; text-decoration: none;',
                            hx_on_click='document.querySelector(\'input[name="botify_url"]\').value = this.innerText.split(" <--")[0]; this.style.color = \'#28a745\'; setTimeout(() => this.style.color = \'#888\', 1000)',
                            title='Click to use this example URL'
                        ),
                        style='display: block; margin-bottom: 10px; color: #666; font-style: italic;'
                    ),
                    Form(
                        Input(
                            type='url',
                            name='botify_url',
                            placeholder='https://app.botify.com/org/project/',
                            value=display_value,
                            required=True,
                            pattern='https://(app|analyze)\\.botify\\.com/[^/]+/[^/]+/[^/]+.*',
                            cls='w-full'
                        ),
                        Div(
                            Button('Use this URL ▸', type='submit', cls='primary'),
                            cls='mt-vh text-end'
                        ),
                        hx_post=f'/{app_name}/{step_id}_submit',
                        hx_target=f'#{step_id}'
                    )
                ),
                Div(id=next_step_id),
                id=step_id
            )

    async def step_01_submit(self, request):
        """Process the submission for Botify URL input widget.
        # STEP PATTERN: Submit handler stores state and returns:
        # 1. Revert control for the completed step
        # 2. Next step div with explicit hx_trigger="load" to chain reaction to next step
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form = await request.form()
        botify_url = form.get('botify_url', '').strip()
        is_valid, message, project_data = self.validate_botify_url(botify_url)
        if not is_valid:
            return P(f'Error: {message}', cls='text-invalid')
        project_data_str = json.dumps(project_data)
        await wand.set_step_data(pipeline_id, step_id, project_data_str, steps)
        await self.message_queue.add(wand, f"✳️ {step.show} complete: {project_data['project_name']}", verbatim=True)
        project_name = project_data.get('project_name', '')
        project_url = project_data.get('url', '')
        project_info = Div(H4(f'Project: {project_name}'), Small(project_url, style='word-break: break-all;'), style='padding: 10px; background: #f8f9fa; border-radius: 5px;')
        return Div(wand.display_revert_header(step_id=step_id, app_name=app_name, message=f'{step.show}: {project_url}', steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)

    async def step_02(self, request):
        """Handles GET request for Analysis selection between steps 1 and 2."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_02'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        analysis_result_str = step_data.get(step.done, '')
        analysis_result = json.loads(analysis_result_str) if analysis_result_str else {}
        selected_slug = analysis_result.get('analysis_slug', '')
        prev_step_id = 'step_01'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('botify_project', '')
        if not prev_data_str:
            return P('Error: Project data not found. Please complete step 1 first.', cls='text-invalid')
        project_data = json.loads(prev_data_str)
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and selected_slug:
            return Div(Card(H3(f'🔒 {step.show}'), Div(P(f'Project: {project_name}', style='margin-bottom: 5px;'), P(f'Selected Analysis: {selected_slug}', style='font-weight: bold;'), cls='custom-card-padding-bg')), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        elif selected_slug and state.get('_revert_target') != step_id:
            # Get step data to create action buttons
            analysis_result_str = step_data.get(step.done, '')
            analysis_result = json.loads(analysis_result_str) if analysis_result_str else {}
            action_buttons = self._create_action_buttons(analysis_result, step_id)
            widget = Div(
                Div(
                    Button(self.ui['BUTTON_LABELS']['HIDE_SHOW_CODE'],
                        cls=self.ui['BUTTON_STYLES']['STANDARD'],
                        hx_get=f'/{app_name}/toggle?step_id={step_id}',
                        hx_target=f'#{step_id}_widget',
                        hx_swap='innerHTML'
                    ),
                    *action_buttons,
                    style=self.ui['BUTTON_STYLES']['FLEX_CONTAINER']
                ),
                Div(
                    Pre(f'Selected analysis: {selected_slug}', cls='code-block-container', style='display: none;'),
                    id=f'{step_id}_widget'
                )
            )
            return Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: {selected_slug}', widget=widget, steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        try:
            api_token = self.read_api_token()
            if not api_token:
                return P('Error: Botify API token not found. Please connect with Botify first.', cls='text-invalid')
            logging.info(f'Getting analyses for {username}/{project_name}')
            slugs = await self.fetch_analyses(username, project_name, api_token)
            logging.info(f'Got {(len(slugs) if slugs else 0)} analyses')
            if not slugs:
                return P(f'Error: No analyses found for project {project_name}. Please check your API access.', cls='text-invalid')
            selected_value = selected_slug if selected_slug else slugs[0]
            # Get active template details for dynamic UI
            active_crawl_template_key = self.get_configured_template('crawl')
            active_template_details = self.QUERY_TEMPLATES.get(active_crawl_template_key, {})
            template_name = active_template_details.get('name', active_crawl_template_key)
            user_message = active_template_details.get('user_message', 'This will download crawl data.')
            button_suffix = active_template_details.get('button_label_suffix', 'Data')
            # Check for downloaded files using the active template's export type
            downloaded_files_info = {}
            for slug in slugs:
                # Check all possible file types for this analysis
                files_found = []
                # Check crawl data (using active template's export type)
                crawl_filepath = await self.get_deterministic_filepath(username, project_name, slug, active_template_details.get('export_type', 'crawl_attributes'))
                crawl_exists, crawl_info = await self.check_file_exists(crawl_filepath)
                if crawl_exists:
                    filename = os.path.basename(crawl_filepath)
                    files_found.append(filename)
                # Check weblog data
                weblog_filepath = await self.get_deterministic_filepath(username, project_name, slug, 'weblog')
                weblog_exists, _ = await self.check_file_exists(weblog_filepath)
                if weblog_exists:
                    files_found.append('weblog.csv')
                # Check GSC data
                gsc_filepath = await self.get_deterministic_filepath(username, project_name, slug, 'gsc')
                gsc_exists, _ = await self.check_file_exists(gsc_filepath)
                if gsc_exists:
                    files_found.append('gsc.csv')
                if files_found:
                    downloaded_files_info[slug] = files_found
            await self.message_queue.add(wand, self.step_messages.get(step_id, {}).get('input', f'Select an analysis for {project_name}'), verbatim=True)
            # Build dropdown options with file summaries
            dropdown_options = []
            for slug in slugs:
                if slug in downloaded_files_info:
                    files_summary = ', '.join(downloaded_files_info[slug])
                    option_text = f'{slug} ({files_summary})'
                else:
                    option_text = slug
                dropdown_options.append(Option(option_text, value=slug, selected=slug == selected_value))
            # Check if files are cached for the selected analysis to determine button text
            selected_analysis = selected_value if selected_value else (slugs[0] if slugs else '')
            active_template_details = self.QUERY_TEMPLATES.get(active_crawl_template_key, {})
            export_type = active_template_details.get('export_type', 'crawl_attributes')
            is_cached = False
            if selected_analysis:
                is_cached = await self.check_cached_file_for_button_text(username, project_name, selected_analysis, export_type)
            button_text = f'Use Cached {button_suffix} ▸' if is_cached else f'Download {button_suffix} ▸'
            return Div(
                Card(
                    H3(f'{step.show}'), 
                    P(f"Select an analysis for project '{project_name}'"), 
                    P(f'Organization: {username}', cls='text-secondary'), 
                    P(user_message, cls='text-muted', style='font-style: italic; margin-top: 10px;'), 
                    Form(
                        Select(
                            *dropdown_options, 
                            name='analysis_slug', 
                            required=True, 
                            autofocus=True,
                            hx_post=f'/{app_name}/update_button_text',
                            hx_target='#submit-button',
                            hx_swap='outerHTML',
                            hx_include='closest form'
                        ),
                        Input(type='hidden', name='username', value=username),
                        Input(type='hidden', name='project_name', value=project_name),
                        Button(
                            button_text, 
                            type='submit', 
                            cls='mt-10px primary', 
                            id='submit-button',
                            **{'hx-on:click': 'this.setAttribute("aria-busy", "true"); this.textContent = "Processing..."'}
                        ), 
                        hx_post=f'/{app_name}/{step_id}_submit', 
                        hx_target=f'#{step_id}'
                    )
                ), 
                Div(id=next_step_id), 
                id=step_id
            )
        except Exception as e:
            logging.exception(f'Error in {step_id}: {e}')
            return P(f'Error fetching analyses: {str(e)}', cls='text-invalid')

    async def step_02_submit(self, request):
        """Process the selected analysis slug for step_02 and download crawl data."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_02'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        prev_step_id = 'step_01'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('botify_project', '')
        if not prev_data_str:
            return P('Error: Project data not found. Please complete step 1 first.', cls='text-invalid')
        project_data = json.loads(prev_data_str)
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')
        form = await request.form()
        analysis_slug = form.get('analysis_slug', '').strip()
        if not analysis_slug:
            return P('Error: No analysis selected', cls='text-invalid')
        await self.message_queue.add(wand, f'📊 Selected analysis: {analysis_slug}. Starting crawl data download...', verbatim=True)
        # Get active template details and check for qualifier config
        active_crawl_template_key = self.get_configured_template('crawl')
        active_template_details = self.QUERY_TEMPLATES.get(active_crawl_template_key, {})
        qualifier_config = active_template_details.get('qualifier_config', {'enabled': False})
        analysis_result = {
            'analysis_slug': analysis_slug,
            'project': project_name,
            'username': username,
            'timestamp': datetime.now().isoformat(),
            'download_started': True,
            'export_type': active_template_details.get('export_type', 'crawl_attributes')
        }
        # Execute qualifier logic if enabled
        if qualifier_config.get('enabled'):
            try:
                api_token = self.read_api_token()
                if not api_token:
                    return P('Error: Botify API token not found. Please connect with Botify first.', cls='text-invalid')
                await self.message_queue.add(wand, qualifier_config['user_message_running'], verbatim=True)
                qualifier_outcome = await self._execute_qualifier_logic(username, project_name, analysis_slug, api_token, qualifier_config)
                # Store qualifier results
                analysis_result['dynamic_parameter_value'] = qualifier_outcome['parameter_value']
                analysis_result['metric_at_dynamic_parameter'] = qualifier_outcome['metric_at_parameter']
                analysis_result['parameter_placeholder_in_main_query'] = qualifier_config['parameter_placeholder_in_main_query']
                # Send completion message
                await self.message_queue.add(wand, qualifier_config['user_message_found'].format(
                    param_value=qualifier_outcome['parameter_value'],
                    metric_value=qualifier_outcome['metric_at_parameter']
                ), verbatim=True)
            except Exception as e:
                await self.message_queue.add(wand, f'Error during qualifier logic: {str(e)}', verbatim=True)
                # Continue with default values
                analysis_result['dynamic_parameter_value'] = None
                analysis_result['metric_at_dynamic_parameter'] = 0
                analysis_result['parameter_placeholder_in_main_query'] = None
        analysis_result_str = json.dumps(analysis_result)
        await wand.set_step_data(pipeline_id, step_id, analysis_result_str, steps)
        return Card(
            H3(f'{step.show}'),
            P(f"Downloading data for analysis '{analysis_slug}'..."),
            Progress(style='margin-top: 10px;'),
            Script(f"""
                setTimeout(function() {{
                    htmx.ajax('POST', '/{app_name}/step_02_process', {{
                        target: '#{step_id}',
                        values: {{
                            'analysis_slug': '{analysis_slug}',
                            'username': '{username}',
                            'project_name': '{project_name}'
                        }}
                    }});
                }}, 500);
            """),
            id=step_id
        )

    async def step_03(self, request):
        """Handles GET request for checking if a Botify project has web logs."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_03'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        check_result_str = step_data.get(step.done, '')
        check_result = json.loads(check_result_str) if check_result_str else {}
        prev_step_id = 'step_01'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('botify_project', '')
        if not prev_data_str:
            return P('Error: Project data not found. Please complete step 1 first.', cls='text-invalid')
        project_data = json.loads(prev_data_str)
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and check_result:
            has_logs = check_result.get('has_logs', False)
            status_text = 'HAS web logs' if has_logs else 'does NOT have web logs'
            status_color = 'green' if has_logs else 'red'
            action_buttons = self._create_action_buttons(check_result, step_id)
            widget = Div(
                Div(
                    Button(self.ui['BUTTON_LABELS']['HIDE_SHOW_CODE'],
                        cls=self.ui['BUTTON_STYLES']['STANDARD'],
                        hx_get=f'/{app_name}/toggle?step_id={step_id}',
                        hx_target=f'#{step_id}_widget',
                        hx_swap='innerHTML'
                    ),
                    *action_buttons,
                    style=self.ui['BUTTON_STYLES']['FLEX_CONTAINER']
                ),
                Div(
                    Pre(f'Status: Project {status_text}', cls='code-block-container', style=f'color: {status_color}; display: none;'),
                    id=f'{step_id}_widget'
                )
            )
            return Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Project {status_text}', widget=widget, steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        elif check_result and state.get('_revert_target') != step_id:
            has_logs = check_result.get('has_logs', False)
            status_text = 'HAS web logs' if has_logs else 'does NOT have web logs'
            status_color = 'green' if has_logs else 'red'
            action_buttons = self._create_action_buttons(check_result, step_id)
            widget = Div(
                Div(
                    Button(self.ui['BUTTON_LABELS']['HIDE_SHOW_CODE'],
                        cls=self.ui['BUTTON_STYLES']['STANDARD'],
                        hx_get=f'/{app_name}/toggle?step_id={step_id}',
                        hx_target=f'#{step_id}_widget',
                        hx_swap='innerHTML'
                    ),
                    *action_buttons,
                    style=self.ui['BUTTON_STYLES']['FLEX_CONTAINER']
                ),
                Div(
                    Pre(f'Status: Project {status_text}', cls='code-block-container', style=f'color: {status_color}; display: none;'),
                    id=f'{step_id}_widget'
                )
            )
            return Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Project {status_text}', widget=widget, steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        else:
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
            # Check if web logs are cached for the CURRENT analysis
            # Use the same logic as step_02 to get the current analysis
            is_cached = False
            try:
                # Get the current analysis from step_02 data - try multiple possible keys
                analysis_step_id = 'step_02'
                analysis_step_data = wand.get_step_data(pipeline_id, analysis_step_id, {})
                current_analysis_slug = ''
                # Try to get analysis_slug from the stored data
                if analysis_step_data:
                    # Debug: Print what we actually have
                    # print(f"DEBUG step_03: analysis_step_data = {analysis_step_data}")
                    # print(f"DEBUG step_03: analysis_step_data keys = {list(analysis_step_data.keys()) if isinstance(analysis_step_data, dict) else 'not a dict'}")
                    # Try the 'analysis_selection' key first
                    analysis_data_str = analysis_step_data.get('analysis_selection', '')
                    # print(f"DEBUG step_03: analysis_data_str = {analysis_data_str[:100] if analysis_data_str else 'empty'}")
                    if analysis_data_str:
                        try:
                            analysis_data = json.loads(analysis_data_str)
                            current_analysis_slug = analysis_data.get('analysis_slug', '')
                        except (json.JSONDecodeError, AttributeError):
                            pass
                    # If that didn't work, try looking for analysis_slug directly
                    if not current_analysis_slug and isinstance(analysis_step_data, dict):
                        for key, value in analysis_step_data.items():
                            if isinstance(value, str) and value.startswith('20'):
                                # Looks like an analysis slug (starts with year)
                                current_analysis_slug = value
                                break
                            elif isinstance(value, str):
                                try:
                                    data = json.loads(value)
                                    if isinstance(data, dict) and 'analysis_slug' in data:
                                        current_analysis_slug = data['analysis_slug']
                                        break
                                except (json.JSONDecodeError, AttributeError):
                                    continue
                # Only check for cached files if we found an analysis slug
                if current_analysis_slug:
                    weblog_path = f"downloads/{self.app_name}/{username}/{project_name}/{current_analysis_slug}/weblog.csv"
                    is_cached = os.path.exists(weblog_path)
            except Exception:
                is_cached = False
            # Set button text based on cache status
            button_text = 'Use Cached Web Logs ▸' if is_cached else 'Download Web Logs ▸'
            # Create button row with conditional skip button
            button_row_items = [
                Button(button_text, type='submit', name='action', value='download', cls='primary',
                       **{'hx-on:click': 'this.setAttribute("aria-busy", "true"); this.textContent = "Processing..."'})
            ]
            # Add skip button if enabled in config
            if self.FEATURES_CONFIG.get('enable_skip_buttons', False):
                button_row_items.append(
                    Button(self.ui['BUTTON_LABELS']['SKIP_STEP'],
                           type='submit', name='action', value='skip', cls='secondary outline',
                           style=self.ui['BUTTON_STYLES']['SKIP_BUTTON_STYLE'])
                )
            return Div(Card(H3(f'{step.show}'), P(f"Download Web Logs for '{project_name}'"), P(f'Organization: {username}', cls='text-secondary'), Form(Div(*button_row_items, style=self.ui['BUTTON_STYLES']['BUTTON_ROW']), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_03_submit(self, request):
        """Process the check for Botify web logs and download if available."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_03'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        # Check if user clicked skip button
        form = await request.form()
        action = form.get('action', 'download')  # Default to download for backward compatibility
        if action == 'skip':
            # Handle skip action - create fake completion data and proceed to next step
            await self.message_queue.add(wand, f"⏭️ Skipping Web Logs download...", verbatim=True)
            # Create skip data that indicates step was skipped
            skip_result = {
                'has_logs': False,
                'skipped': True,
                'skip_reason': 'User chose to skip web logs download',
                'download_complete': False,
                'file_path': None,
                'raw_python_code': '',
                'query_python_code': '',
                'jobs_payload': {}
            }
            await wand.set_step_data(pipeline_id, step_id, json.dumps(skip_result), steps)
            await self.message_queue.add(wand, f"⏭️ Web Logs step skipped. Proceeding to next step.", verbatim=True)
            return Div(
                wand.display_revert_widget(
                    step_id=step_id,
                    app_name=app_name,
                    message=f'{step.show}: Skipped',
                    widget=Div(P('This step was skipped.', style='color: #888; font-style: italic;')),
                    steps=steps
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        # Handle normal download action
        prev_step_id = 'step_01'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('botify_project', '')
        if not prev_data_str:
            return P('Error: Project data not found. Please complete step 1 first.', cls='text-invalid')
        project_data = json.loads(prev_data_str)
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')
        analysis_step_id = 'step_02'
        analysis_step_data = wand.get_step_data(pipeline_id, analysis_step_id, {})
        analysis_data_str = analysis_step_data.get('analysis_selection', '')
        if not analysis_data_str:
            return P('Error: Analysis data not found. Please complete step 2 first.', cls='text-invalid')
        analysis_data = json.loads(analysis_data_str)
        analysis_slug = analysis_data.get('analysis_slug', '')
        await self.message_queue.add(wand, f"📥 Downloading Web Logs for '{project_name}'...", verbatim=True)
        return Card(
            H3(f'{step.show}'),
            P(f"Downloading Web Logs for '{project_name}'..."),
            Progress(style='margin-top: 10px;'),
            Script(f"""
                setTimeout(function() {{
                    htmx.ajax('POST', '/{app_name}/step_03_process', {{
                        target: '#{step_id}',
                        values: {{
                            'analysis_slug': '{analysis_slug}',
                            'username': '{username}',
                            'project_name': '{project_name}'
                        }}
                    }});
                }}, 500);
            """),
            id=step_id
        )

    async def step_04(self, request):
        """Handles GET request for checking if a Botify project has Search Console data."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_04'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        check_result_str = step_data.get(step.done, '')
        check_result = json.loads(check_result_str) if check_result_str else {}
        prev_step_id = 'step_01'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('botify_project', '')
        if not prev_data_str:
            return P('Error: Project data not found. Please complete step 1 first.', cls='text-invalid')
        project_data = json.loads(prev_data_str)
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and check_result:
            has_search_console = check_result.get('has_search_console', False)
            status_text = 'HAS Search Console data' if has_search_console else 'does NOT have Search Console data'
            status_color = 'green' if has_search_console else 'red'
            action_buttons = self._create_action_buttons(check_result, step_id)
            widget = Div(
                Div(
                    Button(self.ui['BUTTON_LABELS']['HIDE_SHOW_CODE'],
                        cls=self.ui['BUTTON_STYLES']['STANDARD'],
                        hx_get=f'/{app_name}/toggle?step_id={step_id}',
                        hx_target=f'#{step_id}_widget',
                        hx_swap='innerHTML'
                    ),
                    *action_buttons,
                    style=self.ui['BUTTON_STYLES']['FLEX_CONTAINER']
                ),
                Div(
                    Pre(f'Status: Project {status_text}', cls='code-block-container', style=f'color: {status_color}; display: none;'),
                    id=f'{step_id}_widget'
                )
            )
            return Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Project {status_text}', widget=widget, steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        elif check_result and state.get('_revert_target') != step_id:
            has_search_console = check_result.get('has_search_console', False)
            status_text = 'HAS Search Console data' if has_search_console else 'does NOT have Search Console data'
            status_color = 'green' if has_search_console else 'red'
            action_buttons = self._create_action_buttons(check_result, step_id)
            widget = Div(
                Div(
                    Button(self.ui['BUTTON_LABELS']['HIDE_SHOW_CODE'],
                        cls=self.ui['BUTTON_STYLES']['STANDARD'],
                        hx_get=f'/{app_name}/toggle?step_id={step_id}',
                        hx_target=f'#{step_id}_widget',
                        hx_swap='innerHTML'
                    ),
                    *action_buttons,
                    style=self.ui['BUTTON_STYLES']['FLEX_CONTAINER']
                ),
                Div(
                    Pre(f'Status: Project {status_text}', cls='code-block-container', style=f'color: {status_color}; display: none;'),
                    id=f'{step_id}_widget'
                )
            )
            return Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Project {status_text}', widget=widget, steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        else:
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
            gsc_template = self.get_configured_template('gsc')
            # Check if GSC data is cached for the CURRENT analysis
            # Use the same logic as step_02 to get the current analysis
            is_cached = False
            try:
                # Get the current analysis from step_02 data - try multiple possible keys
                analysis_step_id = 'step_02'
                analysis_step_data = wand.get_step_data(pipeline_id, analysis_step_id, {})
                current_analysis_slug = ''
                # Try to get analysis_slug from the stored data
                if analysis_step_data:
                    # Try the 'analysis_selection' key first
                    analysis_data_str = analysis_step_data.get('analysis_selection', '')
                    if analysis_data_str:
                        try:
                            analysis_data = json.loads(analysis_data_str)
                            current_analysis_slug = analysis_data.get('analysis_slug', '')
                        except (json.JSONDecodeError, AttributeError):
                            pass
                    # If that didn't work, try looking for analysis_slug directly
                    if not current_analysis_slug and isinstance(analysis_step_data, dict):
                        for key, value in analysis_step_data.items():
                            if isinstance(value, str) and value.startswith('20'):
                                # Looks like an analysis slug (starts with year)
                                current_analysis_slug = value
                                break
                            elif isinstance(value, str):
                                try:
                                    data = json.loads(value)
                                    if isinstance(data, dict) and 'analysis_slug' in data:
                                        current_analysis_slug = data['analysis_slug']
                                        break
                                except (json.JSONDecodeError, AttributeError):
                                    continue
                # Only check for cached files if we found an analysis slug
                if current_analysis_slug:
                    gsc_path = f"downloads/{self.app_name}/{username}/{project_name}/{current_analysis_slug}/gsc.csv"
                    is_cached = os.path.exists(gsc_path)
            except Exception:
                is_cached = False
            button_text = f'Use Cached Search Console: {gsc_template} ▸' if is_cached else f'Download Search Console: {gsc_template} ▸'
            # Create button row with conditional skip button
            button_row_items = [
                Button(button_text, type='submit', name='action', value='download', cls='primary',
                       **{'hx-on:click': 'this.setAttribute("aria-busy", "true"); this.textContent = "Processing..."'})
            ]
            # Add skip button if enabled in config
            if self.FEATURES_CONFIG.get('enable_skip_buttons', False):
                button_row_items.append(
                    Button(self.ui['BUTTON_LABELS']['SKIP_STEP'],
                           type='submit', name='action', value='skip', cls='secondary outline',
                           style=self.ui['BUTTON_STYLES']['SKIP_BUTTON_STYLE'])
                )
            return Div(Card(H3(f'{step.show}'), P(f"Download Search Console data for '{project_name}'"), P(f'Organization: {username}', cls='text-secondary'), Form(Div(*button_row_items, style=self.ui['BUTTON_STYLES']['BUTTON_ROW']), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_04_submit(self, request):
        """Process the check for Botify Search Console data."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_04'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        # Check if user clicked skip button
        form = await request.form()
        action = form.get('action', 'download')  # Default to download for backward compatibility
        if action == 'skip':
            # Handle skip action - create fake completion data and proceed to next step
            await self.message_queue.add(wand, f"⏭️ Skipping Search Console download...", verbatim=True)
            # Create skip data that indicates step was skipped
            skip_result = {
                'has_search_console': False,
                'skipped': True,
                'skip_reason': 'User chose to skip Search Console download',
                'download_complete': False,
                'file_path': None,
                'raw_python_code': '',
                'query_python_code': '',
                'jobs_payload': {}
            }
            await wand.set_step_data(pipeline_id, step_id, json.dumps(skip_result), steps)
            await self.message_queue.add(wand, f"⏭️ Search Console step skipped. Proceeding to next step.", verbatim=True)
            return Div(
                wand.display_revert_widget(
                    step_id=step_id,
                    app_name=app_name,
                    message=f'{step.show}: Skipped',
                    widget=Div(P('This step was skipped.', style='color: #888; font-style: italic;')),
                    steps=steps
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        # Handle normal download action
        prev_step_id = 'step_01'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('botify_project', '')
        if not prev_data_str:
            return P('Error: Project data not found. Please complete step 1 first.', cls='text-invalid')
        project_data = json.loads(prev_data_str)
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')
        return Card(
            H3(f'{step.show}'),
            P(f"Downloading Search Console data for '{project_name}'..."),
            Progress(style='margin-top: 10px;'),
            Script(f"""
                setTimeout(function() {{
                    htmx.ajax('POST', '/{app_name}/{step_id}_complete', {{
                        target: '#{step_id}',
                        values: {{ 'delay_complete': 'true' }}
                    }});
                }}, 1500);
            """),
            id=step_id
        )

    async def step_04_complete(self, request):
        """Handles completion after the progress indicator has been shown."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_04'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        
        prev_step_id = 'step_01'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('botify_project', '')
        if not prev_data_str:
            return P('Error: Project data not found.', cls='text-invalid')
        
        project_data = json.loads(prev_data_str)
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')
        
        analysis_step_id = 'step_02'
        analysis_step_data = wand.get_step_data(pipeline_id, analysis_step_id, {})
        analysis_data_str = analysis_step_data.get('analysis_selection', '')
        if not analysis_data_str:
            return P('Error: Analysis data not found.', cls='text-invalid')
        
        analysis_data = json.loads(analysis_data_str)
        analysis_slug = analysis_data.get('analysis_slug', '')
        
        try:
            has_search_console, error_message = await self.check_if_project_has_collection(username, project_name, 'search_console')
            if error_message:
                return Div(
                    P(f'Error: {error_message}', cls='text-invalid'),
                    Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                    id=step_id
                )
            
            check_result = {
                'has_search_console': has_search_console,
                'project': project_name,
                'username': username,
                'analysis_slug': analysis_slug,
                'timestamp': datetime.now().isoformat()
            }
            
            if has_search_console:
                await self.message_queue.add(wand, f'✅ Project has Search Console data, downloading...', verbatim=True)
                await self.process_search_console_data(wand, pipeline_id, step_id, username, project_name, analysis_slug, check_result)
            else:
                await self.message_queue.add(wand, f'Project does not have Search Console data (skipping download)', verbatim=True)
                # Add empty python_command for consistency with other steps
                check_result['python_command'] = ''
                check_result_str = json.dumps(check_result)
                await wand.set_step_data(pipeline_id, step_id, check_result_str, steps)
            
            status_text = 'HAS' if has_search_console else 'does NOT have'
            completed_message = 'Data downloaded successfully' if has_search_console else 'No Search Console data available'
            
            action_buttons = self._create_action_buttons(check_result, step_id)
            
            widget = Div(
                Div(
                    Button(self.ui['BUTTON_LABELS']['HIDE_SHOW_CODE'],
                        cls=self.ui['BUTTON_STYLES']['STANDARD'],
                        hx_get=f'/{app_name}/toggle?step_id={step_id}',
                        hx_target=f'#{step_id}_widget',
                        hx_swap='innerHTML'
                    ),
                    *action_buttons,
                    style=self.ui['BUTTON_STYLES']['FLEX_CONTAINER']
                ),
                Div(
                    Pre(f'Status: Project {status_text} Search Console data', 
                        cls='code-block-container', 
                        style=f'color: {"green" if has_search_console else "red"}; display: none;'),
                    id=f'{step_id}_widget'
                )
            )
            
            return Div(
                wand.display_revert_widget(
                    step_id=step_id,
                    app_name=app_name,
                    message=f'{step.show}: {completed_message}',
                    widget=widget,
                    steps=steps
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
            
        except Exception as e:
            logging.exception(f'Error in step_04_complete: {e}')
            return Div(
                P(f'Error: {str(e)}', cls='text-invalid'),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )

    async def step_05(self, request):
        """Handles GET request for Parameter Optimization Generation."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_05'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        optimization_result = step_data.get(step.done, '')
        param_count = '40'
        if optimization_result:
            try:
                result_data = json.loads(optimization_result)
                param_count = str(result_data.get('param_count', 40))
            except json.JSONDecodeError:
                pass
        project_data = wand.get_step_data(pipeline_id, 'step_01', {}).get('botify_project', '{}')
        analysis_data = wand.get_step_data(pipeline_id, 'step_02', {}).get('analysis_selection', '{}')
        try:
            project_info = json.loads(project_data)
            analysis_info = json.loads(analysis_data)
        except json.JSONDecodeError:
            return P('Error: Could not load project or analysis data', cls='text-invalid')
        username = project_info.get('username')
        project_name = project_info.get('project_name')
        analysis_slug = analysis_info.get('analysis_slug')
        if not all([username, project_name, analysis_slug]):
            return P('Error: Missing required project information', cls='text-invalid')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and optimization_result:
            try:
                visualization_widget = self.create_parameter_visualization_placeholder(optimization_result)
                return Div(Card(H3(f'🔒 {step.show}'), visualization_widget), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
            except Exception as e:
                logging.error(f'Error creating parameter visualization in finalized view: {str(e)}')
                return Div(Card(H3(f'🔒 {step.show}'), P('Parameter optimization completed', cls='mb-10px'), Div(P(f'Analysis data is locked.'), cls='custom-card-padding-bg')), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        elif optimization_result and state.get('_revert_target') != step_id:
            try:
                visualization_widget = self.create_parameter_visualization_placeholder(optimization_result)
                return Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f"{step.show}: {json.loads(optimization_result).get('total_unique_parameters', 0):,} unique parameters found", widget=visualization_widget, steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
            except Exception as e:
                logging.error(f'Error creating parameter visualization in revert view: {str(e)}')
                return Div(wand.display_revert_header(step_id=step_id, app_name=app_name, message=f'{step.show}: Parameter analysis complete', steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
        return Div(Card(H3(f'{step.show}'), P('This will create counters for your querystring parameters for each of the following:', cls='mb-15px'), Ul(Li('Crawl data from Botify analysis'), Li('Search Console performance data'), Li('Web logs data (if available)'), cls='mb-15px'), Form(Div(P("Note: It doesn't matter what you choose here. This slider only controls how many parameters are displayed and can be adjusted at any time. It does not affect the underlying analysis.", cls='text-muted', style='margin-bottom: 10px;'), Label(NotStr('<strong>Number of Parameters to Show:</strong>'), For='param_count', style='min-width: 220px;'), Input(type='range', name='param_count_slider', id='param_count_slider', value=param_count, min='10', max='250', step='5', style='flex-grow: 1; margin: 0 10px;', _oninput="document.getElementById('param_count').value = this.value;"), Input(type='number', name='param_count', id='param_count', value=param_count, min='10', max='250', step='5', style='width: 100px;', _oninput="document.getElementById('param_count_slider').value = this.value;", _onkeydown="if(event.key === 'Enter') { event.preventDefault(); return false; }"), style='display: flex; align-items: center; gap: 10px; margin-bottom: 15px;'), Button('Count Parameters ▸', type='submit', cls='primary'), Script("\n                    // Define triggerParameterPreview in the global scope\n                    window.triggerParameterPreview = function() {\n                        // Use HTMX to manually trigger the parameter preview\n                        htmx.trigger('#parameter-preview', 'htmx:beforeRequest');\n                        htmx.ajax('POST', \n                            window.location.pathname.replace('step_06', 'parameter_preview'), \n                            {\n                                target: '#parameter-preview',\n                                values: {\n                                    'gsc_threshold': document.getElementById('gsc_threshold').value,\n                                    'min_frequency': document.getElementById('min_frequency').value\n                                }\n                            }\n                        );\n                    };\n                    "), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}', _onsubmit='if(event.submitter !== document.querySelector(\'button[type="submit"]\')) { event.preventDefault(); return false; }', _onkeydown="if(event.key === 'Enter') { event.preventDefault(); return false; }"), Script('\n                function triggerParameterPreview() {\n                    // Use HTMX to manually trigger the parameter preview\n                    htmx.trigger(\'#parameter-preview\', \'htmx:beforeRequest\');\n                    htmx.ajax(\'POST\', document.querySelector(\'input[name="gsc_threshold"]\').form.getAttribute(\'hx-post\').replace(\'step_06_submit\', \'parameter_preview\'), {\n                        target: \'#parameter-preview\',\n                        values: {\n                            \'gsc_threshold\': document.getElementById(\'gsc_threshold\').value,\n                            \'min_frequency\': document.getElementById(\'min_frequency\').value\n                        }\n                    });\n                }\n                ')), Div(id=next_step_id), id=step_id)

    async def step_05_submit(self, request):
        """Process the parameter optimization generation.

        # BACKGROUND PROCESSING PATTERN: This demonstrates the standard pattern for long-running operations:
        # 1. Return progress UI immediately
        # 2. Use Script tag with setTimeout + htmx.ajax to trigger background processing
        # 3. Background processor updates state and returns completed UI with next step trigger
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_05'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form = await request.form()
        param_count = form.get('param_count', '40')
        return Card(H3(f'{step.show}'), P('Counting parameters...', cls='mb-15px'), Progress(style='margin-top: 10px;'), Script("\n            setTimeout(function() {\n                htmx.ajax('POST', '" + f'/{app_name}/step_05_process' + "', {\n                    target: '#" + step_id + "',\n                    values: { \n                        'pipeline_id': '" + pipeline_id + "',\n                        'param_count': '" + param_count + "'\n                    }\n                });\n            }, 500);\n            "), id=step_id)

    async def step_05_process(self, request):
        """Process parameter analysis using raw parameter counting and caching."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_05'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        form = await request.form()
        pipeline_id = form.get('pipeline_id', 'unknown')
        param_count = int(form.get('param_count', '40'))
        project_data = wand.get_step_data(pipeline_id, 'step_01', {}).get('botify_project', '{}')
        analysis_data = wand.get_step_data(pipeline_id, 'step_02', {}).get('analysis_selection', '{}')
        try:
            project_info = json.loads(project_data)
            analysis_info = json.loads(analysis_data)
        except json.JSONDecodeError:
            return P('Error: Could not load project or analysis data', cls='text-invalid')
        username = project_info.get('username')
        project_name = project_info.get('project_name')
        analysis_slug = analysis_info.get('analysis_slug')
        if not all([username, project_name, analysis_slug]):
            return P('Error: Missing required project information', cls='text-invalid')
        try:
            await self.message_queue.add(wand, 'Counting parameters...', verbatim=True)
            data_dir = await self.get_deterministic_filepath(username, project_name, analysis_slug)
            cache_filename = '_raw_param_counters_cache.pkl'
            files_to_process = {'not_indexable': 'crawl.csv', 'gsc': 'gsc.csv', 'weblogs': 'weblog.csv'}
            cached_data = self.load_raw_counters_from_cache(data_dir, cache_filename)
            output_data = None
            if cached_data is not None:
                output_data = cached_data
            if output_data is None:
                output_data = await self.calculate_and_cache_raw_counters(data_directory_path=data_dir, input_files_config=files_to_process, cache_filename=cache_filename)
                if output_data is None:
                    raise ValueError('Failed to calculate counters from source files')
            raw_counters = output_data.get('raw_counters', {})
            file_statuses = output_data.get('metadata', {}).get('file_statuses', {})
            parameter_summary = {'timestamp': datetime.now().isoformat(), 'data_sources': {}, 'cache_path': str(Path(data_dir) / cache_filename), 'param_count': param_count}
            total_unique_params = set()
            total_occurrences = 0
            for source, counter in raw_counters.items():
                unique_params = len(counter)
                source_occurrences = sum(counter.values())
                total_occurrences += source_occurrences
                status = file_statuses.get(source, 'Unknown')
                parameter_summary['data_sources'][source] = {'unique_parameters': unique_params, 'total_occurrences': source_occurrences, 'status': status, 'top_parameters': [{'name': param, 'count': count} for param, count in counter.most_common(10)] if counter else []}
                total_unique_params.update(counter.keys())
            parameter_summary['total_unique_parameters'] = len(total_unique_params)
            summary_str = json.dumps(parameter_summary)
            await wand.set_step_data(pipeline_id, step_id, summary_str, steps)
            await self.message_queue.add(wand, f"✓ Parameter analysis complete! Found {len(total_unique_params):,} unique parameters across {len(parameter_summary['data_sources'])} sources with {total_occurrences:,} total occurrences.", verbatim=True)
            visualization_widget = self.create_parameter_visualization_placeholder(summary_str)
            return Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: {len(total_unique_params):,} unique parameters found', widget=visualization_widget, steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        except Exception as e:
            logging.exception(f'Error in step_05_process: {e}')
            return P(f'Error generating optimization: {str(e)}', cls='text-invalid')

    async def step_06(self, request):
        """Handles GET request for the JavaScript Code Display Step."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_06'
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
                widget_id = f"prism-widget-{pipeline_id.replace('-', '_')}-{step_id}"
                try:
                    values = json.loads(user_val)
                    code_to_display = values.get('js_code', '')
                    selected_params = values.get('selected_params', [])
                    gsc_threshold = values.get('gsc_threshold', '0')
                    min_frequency = values.get('min_frequency', '100000')
                except json.JSONDecodeError:
                    code_to_display = user_val
                    selected_params = []
                    gsc_threshold = '0'
                    min_frequency = '0'
                prism_widget = self.create_prism_widget(code_to_display, widget_id, 'javascript')
                response = HTMLResponse(to_xml(Div(Card(H3(f'🔒 {step.show}'), P(f'Parameter Optimization with {len(selected_params)} parameters'), prism_widget), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)))
                response.headers['HX-Trigger'] = json.dumps({'initializePrism': {'targetId': widget_id}})
                return response
            except Exception as e:
                logging.exception(f'Error creating Prism widget in locked view: {str(e)}')
                return Div(Card(H3(f'🔒 {step.show}'), P('Parameter optimization JavaScript'), Pre(f"JavaScript couldn't be displayed due to an error: {str(e)}")), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        elif user_val and state.get('_revert_target') != step_id:
            try:
                values = None
                try:
                    logging.info(f'Raw user_val in finalized state: {user_val[:100]}...')
                    values = json.loads(user_val) if user_val else {}
                    logging.info(f'Parsed JSON keys: {list(values.keys())}')
                except json.JSONDecodeError as json_err:
                    logging.error(f'JSON parsing error: {str(json_err)}')
                    code_to_display = user_val
                    gsc_threshold = '0'
                    min_frequency = '100000'
                    selected_params = []
                else:
                    code_to_display = values.get('js_code', '')
                    if not code_to_display and user_val:
                        code_to_display = user_val
                    gsc_threshold = values.get('gsc_threshold', '0')
                    min_frequency = values.get('min_frequency', '100000')
                    selected_params = values.get('selected_params', [])
                widget_id = f"prism-widget-{pipeline_id.replace('-', '_')}-{step_id}"
                logging.info(f'Code length: {len(code_to_display)}, Params count: {(len(selected_params) if selected_params else 0)}')
                prism_widget = self.create_prism_widget(code_to_display, widget_id, 'javascript')
                response = HTMLResponse(to_xml(Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'Parameter Optimization with {(len(selected_params) if selected_params else 0)} parameters', widget=prism_widget, steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)))
                response.headers['HX-Trigger'] = json.dumps({'initializePrism': {'targetId': widget_id}})
                return response
            except Exception as e:
                logging.error(f'Error creating Prism widget: {str(e)}')
                state['_revert_target'] = step_id
                wand.write_state(pipeline_id, state)
        prev_step_data = wand.get_step_data(pipeline_id, 'step_05', {})
        prev_data_str = prev_step_data.get('placeholder', '')
        gsc_threshold = '0'
        min_frequency = '100000'
        try:
            if user_val:
                values = json.loads(user_val) if user_val else {}
                gsc_threshold = values.get('gsc_threshold', '0')
                min_frequency = values.get('min_frequency', '100000')
            elif prev_data_str:
                summary_data = json.loads(prev_data_str)
                cache_path = summary_data.get('cache_path')
                if cache_path and os.path.exists(cache_path):
                    try:
                        with open(cache_path, 'rb') as f:
                            cache_data = pickle.load(f)
                        raw_counters = cache_data.get('raw_counters', {})
                        weblogs_counter = None
                        gsc_counter = None
                        not_indexable_counter = None
                        source_mapping = {'weblogs': ['weblogs', 'weblog', 'logs', 'log'], 'gsc': ['gsc', 'search_console', 'searchconsole', 'google'], 'not_indexable': ['not_indexable', 'crawl', 'non_indexable', 'nonindexable']}
                        for source, possible_keys in source_mapping.items():
                            for key in possible_keys:
                                if key in raw_counters:
                                    if source == 'weblogs':
                                        weblogs_counter = raw_counters[key]
                                    elif source == 'gsc':
                                        gsc_counter = raw_counters[key]
                                    elif source == 'not_indexable':
                                        not_indexable_counter = raw_counters[key]
                                    break
                        if gsc_counter and (weblogs_counter or not_indexable_counter):
                            combined_counter = Counter()
                            if weblogs_counter:
                                combined_counter.update(weblogs_counter)
                            if not_indexable_counter:
                                combined_counter.update(not_indexable_counter)
                            max_dead_param_frequency = 0
                            for param, count in combined_counter.items():
                                if gsc_counter.get(param, 0) == 0:
                                    max_dead_param_frequency = max(max_dead_param_frequency, count)
                            if max_dead_param_frequency > 0:
                                min_frequency = str(max_dead_param_frequency)
                                logging.info(f'Found optimal min_frequency: {min_frequency} from max dead parameter')
                    except Exception as e:
                        logging.error(f'Error calculating optimal frequency: {str(e)}')
        except json.JSONDecodeError:
            pass
        await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
        breakpoints_html = ''
        try:
            prev_step_data = wand.get_step_data(pipeline_id, 'step_05', {})
            prev_data_str = prev_step_data.get('placeholder', '')
            if prev_data_str:
                summary_data = json.loads(prev_data_str)
                cache_path = summary_data.get('cache_path')
                if cache_path and os.path.exists(cache_path):
                    with open(cache_path, 'rb') as f:
                        cache_data = pickle.load(f)
                    raw_counters = cache_data.get('raw_counters', {})
                    weblogs_counter = None
                    gsc_counter = None
                    not_indexable_counter = None
                    source_mapping = {'weblogs': ['weblogs', 'weblog', 'logs', 'log'], 'gsc': ['gsc', 'search_console', 'searchconsole', 'google'], 'not_indexable': ['not_indexable', 'crawl', 'non_indexable', 'nonindexable']}
                    for source, possible_keys in source_mapping.items():
                        for key in possible_keys:
                            if key in raw_counters:
                                if source == 'weblogs':
                                    weblogs_counter = raw_counters[key]
                                elif source == 'gsc':
                                    gsc_counter = raw_counters[key]
                                elif source == 'not_indexable':
                                    not_indexable_counter = raw_counters[key]
                                break
                    if gsc_counter and (weblogs_counter or not_indexable_counter):
                        combined_counter = Counter()
                        if weblogs_counter:
                            combined_counter.update(weblogs_counter)
                        if not_indexable_counter:
                            combined_counter.update(not_indexable_counter)
                        all_frequencies = sorted(set(combined_counter.values()), reverse=True)
                        param_counts = {}
                        for freq in all_frequencies:
                            count = sum((1 for param, count in combined_counter.items() if gsc_counter.get(param, 0) <= 0 and count >= freq))
                            param_counts[freq] = count
                        breakpoints = []
                        ranges = [(1, 5), (5, 15), (15, 30), (30, 50), (50, 100)]
                        for min_count, max_count in ranges:
                            for freq in all_frequencies:
                                if param_counts[freq] >= min_count and param_counts[freq] <= max_count:
                                    breakpoints.append((freq, param_counts[freq]))
                                    break
                        max_freq = all_frequencies[0] if all_frequencies else 0
                        if max_freq > 0 and (not breakpoints or max_freq > breakpoints[0][0]):
                            if param_counts[max_freq] > 1:
                                breakpoints.insert(0, (max_freq, param_counts[max_freq]))
                        if breakpoints:
                            breakpoints_html = f"""\n                            <div style="background: #222; padding: 10px; border-radius: 5px; margin: 15px 0;">\n                                <h4 style="color: #ccc; margin-bottom: 10px;">Understanding the Optimization Settings</h4>\n                                <p style="margin-bottom: 15px;">\n                                    There are two critical settings that control how parameters are optimized:\n                                </p>\n                                <ul style="margin-bottom: 15px;">\n                                    <li style="margin-bottom: 8px;">\n                                        <span style="color: #50fa7b; font-weight: bold;">GSC Threshold</span>: Keep this at 0 to protect parameters \n                                        that appear in URLs receiving any Google Search Console impressions. These are your "working" parameters that \n                                        are actively involved in search visibility.\n                                    </li>\n                                    <li style="margin-bottom: 8px;">\n                                        <span style="color: #ff8c00; font-weight: bold;">Minimum Frequency</span>: Controls how aggressive your optimization \n                                        will be. Higher values target only the most wasteful parameters, while lower values optimize more parameters but \n                                        require more careful testing.\n                                    </li>\n                                </ul>\n                                <div style="background: #1a1a1a; padding: 10px; border-radius: 5px; margin: 15px 0;">\n                                    <p style="color: #888; font-style: italic;">\n                                        Instead of manually adjusting these values, we've identified key breakpoints below. Click the \n                                        <span style="color: #ff8c00; font-weight: bold;">orange numbers</span> to see which parameters would be affected. \n                                        Start conservatively with higher frequencies (fewer parameters) and gradually become more aggressive by selecting \n                                        lower frequencies.\n                                    </p>\n                                </div>\n                                <h5 style="margin: 15px 0 10px 0; color: #ccc;">Meaningful Min Frequency Values (with GSC=0):</h5>\n                                <table style="margin-bottom: 10px; font-size: 0.9em;">\n                            """
                            for freq, count in breakpoints:
                                rounded_freq = freq if freq < 100 else int(freq // 100 * 100)
                                breakpoints_html += f"""\n                                    <tr>\n                                        <td style="color: #bbb; padding-right: 10px;">Show {count} parameter{('' if count == 1 else 's')}:</td>\n                                        <td style="color: #ff8c00; font-weight: bold; text-align: right;">\n                                            <a href="javascript:void(0)" \n                                               onclick="\n                                                 // Update both the slider and number input\n                                                 document.getElementById('min_frequency').value = {rounded_freq};\n                                                 document.getElementById('min_frequency_slider').value = {rounded_freq};\n                                                 \n                                                 // Visual feedback\n                                                 document.getElementById('min_frequency').style.backgroundColor = '#224433';\n                                                 setTimeout(function() {{ \n                                                     document.getElementById('min_frequency').style.backgroundColor = ''; \n                                                 }}, 500);\n                                                 \n                                                 // Direct AJAX call with FIXED CORRECT PATH\n                                                 htmx.ajax('POST', \n                                                     '/{app_name}/parameter_preview', \n                                                     {{\n                                                         target: '#parameter-preview',\n                                                         values: {{\n                                                             'gsc_threshold': document.getElementById('gsc_threshold').value,\n                                                             'min_frequency': {rounded_freq}\n                                                         }}\n                                                     }});\n                                                 \n                                                 return false;" \n                                               style="color: #ff8c00; text-decoration: underline; cursor: pointer;">{('~' if freq > 100 else '')}{freq:,}</a>\n                                        </td>\n                                    </tr>\n                                """
                            breakpoints_html += '\n                                </table>\n                            </div>\n                            '
        except Exception as e:
            logging.error(f'Error calculating breakpoints: {e}')
            breakpoints_html = ''
        max_frequency = breakpoints[0][0] if breakpoints else 250000
        breakpoints_info = ''
        if breakpoints and gsc_threshold == 0:
            breakpoints_info = Div(H5('Meaningful Min Frequency Values (with GSC=0):', style='margin-bottom: 5px; color: #ccc;'), Table(*[Tr(Td(f'Show {count} parameters:', style='color: #bbb; padding-right: 10px;'), Td(f"{('~' if freq > 100 else '')}{freq:,}", style='color: #ff8c00; font-weight: bold; text-align: right;')) for freq, count in breakpoints], style='margin-bottom: 10px; font-size: 0.9em;'), style='background: #222; padding: 10px; border-radius: 5px; margin-bottom: 15px;')
        return Div(Card(H3(f'{wand.fmt(step_id)}: {step.show}'), P('Set thresholds for parameter optimization:'), Form(Div(Div(Small('Lower GSC Threshold to lower risk (generally keep set to 0)', style='color: #888; font-style: italic;'), Div(Label(NotStr('GSC Threshold:'), For='gsc_threshold', style='min-width: 180px; color: #888;'), Input(type='range', name='gsc_threshold_slider', id='gsc_threshold_slider', value=gsc_threshold, min='0', max='100', step='1', style='width: 60%; margin: 0 10px;', _oninput="document.getElementById('gsc_threshold').value = this.value; triggerParameterPreview();", hx_post=f'/{app_name}/parameter_preview', hx_trigger='input changed delay:300ms, load', hx_target='#parameter-preview', hx_include='#gsc_threshold, #min_frequency'), Input(type='number', name='gsc_threshold', id='gsc_threshold', value=gsc_threshold, min='0', max='100', style='width: 150px;', _oninput="document.getElementById('gsc_threshold_slider').value = this.value; triggerParameterPreview();", _onchange="document.getElementById('gsc_threshold_slider').value = this.value; triggerParameterPreview();", hx_post=f'/{app_name}/parameter_preview', hx_trigger='none', hx_target='#parameter-preview', hx_include='#gsc_threshold, #min_frequency'), style='display: flex; align-items: center; gap: 5px;')), Div(Small('Higher Minimum Frequency to reduce to only the biggest offenders', style='color: #888; font-style: italic;'), Div(Label(NotStr('<strong>Minimum Frequency:</strong>'), For='min_frequency', style='min-width: 180px;'), Input(type='range', name='min_frequency_slider', id='min_frequency_slider', value=min_frequency, min='0', max=str(max_frequency), step='1', style='flex-grow: 1; margin: 0 10px;', _oninput="document.getElementById('min_frequency').value = this.value; triggerParameterPreview();", hx_post=f'/{app_name}/parameter_preview', hx_trigger='input changed delay:300ms', hx_target='#parameter-preview', hx_include='#gsc_threshold, #min_frequency'), Input(type='number', name='min_frequency', id='min_frequency', value=min_frequency, min='0', max=str(max_frequency), step='1', style='width: 150px;', _oninput="document.getElementById('min_frequency_slider').value = this.value; triggerParameterPreview();", _onchange="document.getElementById('min_frequency_slider').value = this.value; triggerParameterPreview();", hx_post=f'/{app_name}/parameter_preview', hx_trigger='none', hx_target='#parameter-preview', hx_include='#gsc_threshold, #min_frequency'), style='display: flex; align-items: center; gap: 5px;'), style='margin-bottom: 15px;'), NotStr(breakpoints_html) if breakpoints_html else None, Div(H4('Parameters That Would Be Optimized:'), Div(P('Adjust thresholds above to see which parameters would be optimized.', style='color: #888; font-style: italic;'), id='parameter-preview', style='max-height: 300px; overflow-y: auto; background: #111; border-radius: 5px; padding: 10px; margin-bottom: 15px;'), style='margin-bottom: 20px;'), Div(Button('Create Optimization ▸', type='submit', cls='primary'), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_06_submit(self, request):
        """Process the submission for the parameter threshold settings."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_06'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        form = await request.form()
        gsc_threshold = form.get('gsc_threshold', '0')
        min_frequency = form.get('min_frequency', '100000')
        prev_step_data = wand.get_step_data(pipeline_id, 'step_05', {})
        prev_data_str = prev_step_data.get('placeholder', '')
        selected_params = []
        try:
            if prev_data_str:
                summary_data = json.loads(prev_data_str)
                cache_path = summary_data.get('cache_path')
                if cache_path and os.path.exists(cache_path):
                    with open(cache_path, 'rb') as f:
                        cache_data = pickle.load(f)
                    raw_counters = cache_data.get('raw_counters', {})
                    weblogs_counter = None
                    gsc_counter = None
                    not_indexable_counter = None
                    source_mapping = {'weblogs': ['weblogs', 'weblog', 'logs', 'log'], 'gsc': ['gsc', 'search_console', 'searchconsole', 'google'], 'not_indexable': ['not_indexable', 'crawl', 'non_indexable', 'nonindexable']}
                    for source, possible_keys in source_mapping.items():
                        for key in possible_keys:
                            if key in raw_counters:
                                if source == 'weblogs':
                                    weblogs_counter = raw_counters[key]
                                elif source == 'gsc':
                                    gsc_counter = raw_counters[key]
                                elif source == 'not_indexable':
                                    not_indexable_counter = raw_counters[key]
                                break
                    if gsc_counter and (weblogs_counter or not_indexable_counter):
                        combined_counter = Counter()
                        if weblogs_counter:
                            combined_counter.update(weblogs_counter)
                        if not_indexable_counter:
                            combined_counter.update(not_indexable_counter)
                        for param, count in combined_counter.items():
                            param_gsc_count = gsc_counter.get(param, 0)
                            if param_gsc_count <= int(gsc_threshold) and count >= int(min_frequency):
                                selected_params.append(param)
            selected_params_js_array = json.dumps(selected_params)
            js_code = f"""// Function to remove query parameters from a URL\nfunction removeQueryParams(url, paramsToRemove) {{\n    let urlParts = url.split('?');\n    if (urlParts.length >= 2) {{\n        let queryParams = urlParts[1].split('&');\n        let updatedParams = [];\n        for (let i = 0; i < queryParams.length; i++) {{\n            let paramParts = queryParams[i].split('=');\n            if (!paramsToRemove.includes(paramParts[0])) {{\n                updatedParams.push(queryParams[i]);\n            }}\n        }}\n        if (updatedParams.length > 0) {{\n            return urlParts[0] + '?' + updatedParams.join('&');\n        }} else {{\n            return urlParts[0];\n        }}\n    }} else {{\n        return url;\n    }}\n}}\n  \n// Remove wasteful parameters from all links\nfunction removeWastefulParams() {{\n    const DOM = runtime.getDOM();\n    const removeParameters = {selected_params_js_array};\n    DOM.getAllElements("[href]").forEach(function(el) {{\n        let targetURL = el.getAttribute("href");\t\n        let newTargetURL = removeQueryParams(targetURL, removeParameters);\n        if (targetURL != newTargetURL) {{\n            // console.log("FROM:" + targetURL + " TO:" + newTargetURL);\n            el.setAttribute("href", newTargetURL);\n            el.setAttribute("data-bty-pw-id", "REPLACE_ME!!!");\n        }}\n    }});\n}}\n\n// Execute the function\nremoveWastefulParams();\n"""
            wand.append_to_history(f'[OPTIMIZATION CODE] Generated PageWorkers optimization for {len(selected_params)} parameters:\n{js_code}')
            threshold_data = {'gsc_threshold': gsc_threshold, 'min_frequency': min_frequency, 'selected_params': selected_params, 'js_code': js_code}
            user_val = json.dumps(threshold_data)
            await wand.set_step_data(pipeline_id, step_id, user_val, steps)
            widget_id = f"prism-widget-{pipeline_id.replace('-', '_')}-{step_id}"
            prism_widget = self.create_prism_widget(js_code, widget_id, 'javascript')
            response = HTMLResponse(to_xml(Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'Parameter Optimization with {(len(selected_params) if selected_params else 0)} parameters', widget=prism_widget, steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)))
            response.headers['HX-Trigger'] = json.dumps({'initializePrism': {'targetId': widget_id}})
            return response
        except Exception as e:
            logging.exception(f'Error in step_06_submit: {e}')
            return P(f'Error creating parameter optimization: {str(e)}', cls='text-invalid')

    async def parameter_preview(self, request):
        """Process real-time parameter preview requests based on threshold settings."""
        wand, db, app_name = (self.pipulate, self.pipulate.db, self.app_name)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form = await request.form()
        gsc_threshold = int(form.get('gsc_threshold', '0'))
        min_frequency = int(form.get('min_frequency', '100000'))
        wand.append_to_history(f'[PARAMETER PREVIEW] Previewing parameters with GSC threshold={gsc_threshold} and min_frequency={min_frequency}')
        prev_step_data = wand.get_step_data(pipeline_id, 'step_05', {})
        prev_data_str = prev_step_data.get('placeholder', '')
        matching_params = []
        param_count = 0
        total_frequency = 0
        breakpoint_frequencies = []
        try:
            if prev_data_str:
                summary_data = json.loads(prev_data_str)
                cache_path = summary_data.get('cache_path')
                if cache_path and os.path.exists(cache_path):
                    with open(cache_path, 'rb') as f:
                        cache_data = pickle.load(f)
                    raw_counters = cache_data.get('raw_counters', {})
                    weblogs_counter = None
                    gsc_counter = None
                    not_indexable_counter = None
                    source_mapping = {'weblogs': ['weblogs', 'weblog', 'logs', 'log'], 'gsc': ['gsc', 'search_console', 'searchconsole', 'google'], 'not_indexable': ['not_indexable', 'crawl', 'non_indexable', 'nonindexable']}
                    for source, possible_keys in source_mapping.items():
                        for key in possible_keys:
                            if key in raw_counters:
                                if source == 'weblogs':
                                    weblogs_counter = raw_counters[key]
                                elif source == 'gsc':
                                    gsc_counter = raw_counters[key]
                                elif source == 'not_indexable':
                                    not_indexable_counter = raw_counters[key]
                                break
                    if gsc_counter and (weblogs_counter or not_indexable_counter):
                        combined_counter = Counter()
                        if weblogs_counter:
                            combined_counter.update(weblogs_counter)
                        if not_indexable_counter:
                            combined_counter.update(not_indexable_counter)
                        if gsc_threshold == 0:
                            all_frequencies = sorted(set(combined_counter.values()), reverse=True)
                            param_counts = {}
                            for freq in all_frequencies:
                                count = sum((1 for param, count in combined_counter.items() if gsc_counter.get(param, 0) <= 0 and count >= freq))
                                param_counts[freq] = count
                            ranges = [(1, 5), (5, 15), (15, 30), (30, 50), (50, 100)]
                            for min_count, max_count in ranges:
                                for freq in all_frequencies:
                                    if param_counts[freq] >= min_count and param_counts[freq] <= max_count:
                                        breakpoint_frequencies.append((freq, param_counts[freq]))
                                        break
                        max_freq = all_frequencies[0] if all_frequencies else 0
                        if max_freq > 0 and (not breakpoint_frequencies or max_freq > breakpoint_frequencies[0][0]):
                            if param_counts[max_freq] > 1:
                                breakpoint_frequencies.insert(0, (max_freq, param_counts[max_freq]))
                        for param, count in combined_counter.items():
                            param_gsc_count = gsc_counter.get(param, 0)
                            if param_gsc_count <= gsc_threshold and count >= min_frequency:
                                score = count / (param_gsc_count + 1)
                                matching_params.append((param, count, param_gsc_count, score))
                                param_count += 1
                                total_frequency += count
                        matching_params.sort(key=lambda x: x[3], reverse=True)
        except Exception as e:
            logging.error(f'Error in parameter preview: {str(e)}')
            return Div(P(f'Error: {str(e)}', cls='text-invalid'))
        breakpoints_info = ''
        if breakpoint_frequencies and gsc_threshold == 0:
            breakpoints_info = Div(H5('Meaningful Min Frequency Values (with GSC=0):', style='margin-bottom: 5px; color: #ccc;'), Table(*[Tr(Td(f'Show {count} parameters:', style='color: #bbb; padding-right: 10px;'), Td(f"{('~' if freq > 100 else '')}{freq:,}", style='color: #ff8c00; font-weight: bold; text-align: right;')) for freq, count in breakpoints_info], style='margin-bottom: 10px; font-size: 0.9em;'), style='background: #222; padding: 10px; border-radius: 5px; margin-bottom: 15px;')
        if matching_params:
            display_limit = 5000
            display_message = ''
            if param_count > display_limit:
                display_message = f'(Displaying first {display_limit:,} of {param_count:,} matching parameters)'
            return Div(P(f'Found {param_count:,} parameters with total frequency of {total_frequency:,}'), P(display_message, style='color: #888; font-style: italic; margin-bottom: 10px;') if display_message else None, Table(Tr(Th('Parameter', style='text-align: left; color: cyan;'), Th('Web Logs', style='text-align: right; color: #4fa8ff;'), Th('Not-Indexable', style='text-align: right; color: #ff0000;'), Th('GSC', style='text-align: right; color: #50fa7b;'), Th('Score', style='text-align: right; color: #ffff00;')), *[Tr(Td(param, style='color: cyan;'), Td(f'{weblogs_counter.get(param, 0):,}' if weblogs_counter else 'N/A', style='text-align: right; color: #4fa8ff;'), Td(f'{not_indexable_counter.get(param, 0):,}' if not_indexable_counter else 'N/A', style='text-align: right; color: #ff0000;'), Td(f'{gsc_counter.get(param, 0):,}' if gsc_counter else 'N/A', style='text-align: right; color: #50fa7b;'), Td(f'{score:,.0f}', style='text-align: right; color: #ffff00; font-weight: bold;')) for param, count, gsc_count, score in matching_params[:display_limit]], style='width: 100%; border-collapse: collapse;'), cls='font-code')
        else:
            return P('No parameters match these criteria. Try adjusting the thresholds.', style='color: #ff5555; font-style: italic;')
    Script('\n    function setFrequencyAndPreview(value) {\n        // Update both the slider and the number input\n        const slider = document.getElementById("min_frequency_slider");\n        const input = document.getElementById("min_frequency");\n        \n        // Set values\n        slider.value = value;\n        input.value = value;\n        \n        // Trigger the parameter preview\n        triggerParameterPreview();\n        \n        // Optional: Add visual feedback\n        input.style.backgroundColor = "#224433";\n        setTimeout(function() {\n            input.style.backgroundColor = "";\n        }, 500);\n    }\n    ')

    async def step_07(self, request):
        """Handles GET request for Step 7 Markdown widget."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_07'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        step_06_data = wand.get_step_data(pipeline_id, 'step_06', {})
        parameters_info = {}
        try:
            if step_06_data.get('parameter_optimization'):
                param_data = json.loads(step_06_data.get('parameter_optimization'))
                parameters_info = {'selected_params': param_data.get('selected_params', []), 'gsc_threshold': param_data.get('gsc_threshold', '0'), 'min_frequency': param_data.get('min_frequency', '100000')}
        except (json.JSONDecodeError, TypeError):
            parameters_info = {'selected_params': [], 'gsc_threshold': '0', 'min_frequency': '100000'}
        try:
            markdown_data = json.loads(step_data.get(step.done, '{}'))
            markdown_content = markdown_data.get('markdown', '')
        except (json.JSONDecodeError, TypeError):
            markdown_content = ''
        if not markdown_content:
            params_list = parameters_info.get('selected_params', [])
            gsc_threshold = parameters_info.get('gsc_threshold', '0')
            min_frequency = parameters_info.get('min_frequency', '100000')
            try:
                min_frequency_int = int(min_frequency)
                min_frequency_formatted = f'{min_frequency_int:,}'
            except ValueError:
                min_frequency_formatted = min_frequency
            robots_txt_rules = '\n'.join([f'Disallow: /*?*{param}=*' for param in params_list])
            param_list_str = '\n'.join([f'- {param}' for param in params_list])
            markdown_content = f'# PageWorkers Optimization Ready to Copy/Paste\n\n## Instructions\n1. Copy/Paste the JavaScript (found above) into a new PageWorkers custom Optimization.\n2. Update the `REPLACE_ME!!!` with the ID found in the URL of the Optimization.\n\n**Parameter Optimization Settings**\n- GSC Threshold: {gsc_threshold}\n- Minimum Frequency: {min_frequency_formatted}\n- Total Parameters Optimized: {len(params_list)}\n\n[[DETAILS_START]]\n[[SUMMARY_START]]View all {len(params_list)} parameters[[SUMMARY_END]]\n\n{param_list_str}\n[[DETAILS_END]]\n\n[[DETAILS_START]]\n[[SUMMARY_START]]View robots.txt rules[[SUMMARY_END]]\n\n```robots.txt\nUser-agent: *\n{robots_txt_rules}\n```\n[[DETAILS_END]]\n\n**Important Notes:** robots.txt is advisory, not enforcement; prevents crawling but not indexing; for testing only\n'
            if step_data.get(step.done, '') == '':
                markdown_data = {'markdown': markdown_content, 'parameters_info': parameters_info}
                # Update state directly
                state = wand.read_state(pipeline_id)
                if step_id not in state:
                    state[step_id] = {}
                state[step_id][step.done] = json.dumps(markdown_data)
                if '_revert_target' in state:
                    del state['_revert_target']
                wand.write_state(pipeline_id, state)
        widget_id = f"markdown-widget-{pipeline_id.replace('-', '_')}-{step_id}"
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data:
            markdown_widget = self.create_marked_widget(markdown_content, widget_id)
            response = HTMLResponse(to_xml(Div(Card(H3(f'🔒 {step.show}'), markdown_widget), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)))
            response.headers['HX-Trigger'] = json.dumps({'initializeMarked': {'targetId': widget_id}})
            return response
        elif markdown_content and state.get('_revert_target') != step_id:
            markdown_widget = self.create_marked_widget(markdown_content, widget_id)
            response = HTMLResponse(to_xml(Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Markdown Documentation', widget=markdown_widget, steps=self.steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)))
            response.headers['HX-Trigger'] = json.dumps({'initializeMarked': {'targetId': widget_id}})
            return response
        else:
            if 'finalized' in finalize_data:
                await wand.clear_steps_from(pipeline_id, 'finalize', self.steps)
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
            return Div(Card(H3(f'{step.show}'), P('Edit the Markdown documentation for the Parameter Buster workflow:'), Form(Textarea(markdown_content, name='markdown_content', rows='15', cls='font-code w-full'), Div(Button('Update Documentation ▸', type='submit', cls='primary'), style='margin-top: 10px; text-align: right;'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_07_submit(self, request):
        """Process the markdown content submission for Step 7."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_07'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form = await request.form()
        markdown_content = form.get('markdown_content', '')
        existing_data = {}
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        try:
            if step_data.get(step.done):
                existing_data = json.loads(step_data.get(step.done, '{}'))
        except json.JSONDecodeError:
            pass
        parameters_info = existing_data.get('parameters_info', {})
        if not parameters_info:
            step_06_data = wand.get_step_data(pipeline_id, 'step_06', {})
            try:
                if step_06_data.get('parameter_optimization'):
                    param_data = json.loads(step_06_data.get('parameter_optimization'))
                    parameters_info = {'selected_params': param_data.get('selected_params', []), 'gsc_threshold': param_data.get('gsc_threshold', '0'), 'min_frequency': param_data.get('min_frequency', '100000')}
            except (json.JSONDecodeError, TypeError):
                parameters_info = {'selected_params': [], 'gsc_threshold': '0', 'min_frequency': '100000'}
        markdown_data = {'markdown': markdown_content, 'parameters_info': parameters_info}
        data_str = json.dumps(markdown_data)
        # Update state directly
        state = wand.read_state(pipeline_id)
        if step_id not in state:
            state[step_id] = {}
        state[step_id][step.done] = json.dumps(markdown_data)
        await wand.clear_steps_from(pipeline_id, step_id, self.steps)
        if '_revert_target' in state:
            del state['_revert_target']
        wand.write_state(pipeline_id, state)
        await self.message_queue.add(wand, f'{step.show}: Markdown content updated', verbatim=True)
        widget_id = f"markdown-widget-{pipeline_id.replace('-', '_')}-{step_id}"
        markdown_widget = self.create_marked_widget(markdown_content, widget_id)
        response = HTMLResponse(to_xml(Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Markdown Documentation', widget=markdown_widget, steps=self.steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)))
        response.headers['HX-Trigger'] = json.dumps({'initializeMarked': {'targetId': widget_id}})
        return response

    def validate_botify_url(self, url):
        """Validate a Botify project URL and extract project information."""
        url = url.strip()
        if not url:
            return (False, 'URL is required', {})
        try:
            if not url.startswith(('https://app.botify.com/')):
                return (False, 'URL must be a Botify project URL (starting with https://app.botify.com/)', {})
            parsed_url = urlparse(url)
            path_parts = [p for p in parsed_url.path.strip('/').split('/') if p]
            if len(path_parts) < 2:
                return (False, 'Invalid Botify URL: must contain at least organization and project', {})
            org_slug = path_parts[0]
            project_slug = path_parts[1]
            canonical_url = f'https://{parsed_url.netloc}/{org_slug}/{project_slug}/'
            project_data = {'url': canonical_url, 'username': org_slug, 'project_name': project_slug, 'project_id': f'{org_slug}/{project_slug}'}
            return (True, f'Valid Botify project: {project_slug}', project_data)
        except Exception as e:
            return (False, f'Error parsing URL: {str(e)}', {})

    async def check_if_project_has_collection(self, org_slug, project_slug, collection_id='logs'):
        """
        Checks if a specific collection exists for the given org and project.
        # API PATTERN: This method demonstrates the standard Botify API interaction pattern:
        # 1. Read API token from local file
        # 2. Construct API endpoint URL with proper path parameters
        # 3. Make authenticated request with error handling
        # 4. Return tuple of (result, error_message) for consistent error handling
        Args:
            org_slug: Organization slug
            project_slug: Project slug
            collection_id: ID of the collection to check for (default: "logs")
        Returns:
            (True, None) if found, (False, None) if not found, or (False, error_message) on error.
        """
        try:
            if not os.path.exists(TOKEN_FILE):
                return (False, f"Token file '{TOKEN_FILE}' not found.")
            with open(TOKEN_FILE) as f:
                content = f.read().strip()
                api_key = content.split('\n')[0].strip()
                if not api_key:
                    return (False, f"Token file '{TOKEN_FILE}' is empty.")
        except Exception as e:
            return (False, f'Error loading API key: {e}')
        if not org_slug or not project_slug:
            return (False, 'Organization and project slugs are required.')
        collections_url = f'https://api.botify.com/v1/projects/{org_slug}/{project_slug}/collections'
        headers = {'Authorization': f'Token {api_key}', 'Content-Type': 'application/json'}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(collections_url, headers=headers, timeout=60.0)
            if response.status_code == 401:
                return (False, 'Authentication failed (401). Check your API token.')
            elif response.status_code == 403:
                return (False, 'Forbidden (403). You may not have access to this project or endpoint.')
            elif response.status_code == 404:
                return (False, 'Project not found (404). Check org/project slugs.')
            response.raise_for_status()
            collections_data = response.json()
            if not isinstance(collections_data, list):
                return (False, 'Unexpected API response format. Expected a list.')
            for collection in collections_data:
                if isinstance(collection, dict) and collection.get('id') == collection_id:
                    return (True, None)
            return (False, None)
        except httpx.HTTPStatusError as e:
            return (False, f'API Error: {e.response.status_code}')
        except httpx.RequestError as e:
            return (False, f'Network error: {e}')
        except json.JSONDecodeError:
            return (False, 'Could not decode the API response as JSON.')
        except Exception as e:
            return (False, f'An unexpected error occurred: {e}')

    async def fetch_analyses(self, org, project, api_token):
        """
        Fetch analysis slugs for a Botify project.
        Args:
            org: Organization slug
            project: Project slug
            api_token: Botify API token
        Returns:
            List of analysis slugs or empty list on error
        """
        if not org or not project or (not api_token):
            logging.error(f'Missing required parameters: org={org}, project={project}')
            return []
        all_slugs = []
        next_url = f'https://api.botify.com/v1/analyses/{org}/{project}/light'
        is_first_page = True
        while next_url:
            headers = {'Authorization': f'Token {api_token}', 'Content-Type': 'application/json'}
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(next_url, headers=headers, timeout=60.0)
                if response.status_code != 200:
                    logging.error(f'API error: Status {response.status_code} for {next_url}')
                    return all_slugs
                data = response.json()
                if 'results' not in data:
                    logging.error(f"No 'results' key in response: {data}")
                    return all_slugs
                analyses = data['results']
                if not analyses:
                    logging.error('Analyses list is empty')
                    return all_slugs
                # Log first page in detail to API log
                if is_first_page:
                    curl_cmd, python_cmd = self._generate_api_call_representations(
                        method="GET", url=next_url, headers=headers, step_context="Step 2: Fetch Analysis List"
                    )
                    await self.pipulate.log_api_call_details(
                        pipeline_id="fetch_analyses", step_id="analyses_list",
                        call_description="Fetch Analysis List (First Page)",
                        http_method="GET", url=next_url, headers=headers,
                        response_status=response.status_code,
                        response_preview=json.dumps(data),
                        curl_command=curl_cmd, python_command=python_cmd
                    )
                    is_first_page = False
                else:
                    # Just log that we're fetching subsequent pages
                    logging.info(f'Fetching next page of analyses: {next_url}')
                page_slugs = [analysis.get('slug') for analysis in analyses if analysis.get('slug')]
                all_slugs.extend(page_slugs)
                # Get next page URL if it exists
                next_url = data.get('next')
            except Exception as e:
                logging.exception(f'Error fetching analyses: {str(e)}')
                return all_slugs
        logging.info(f'Found {len(all_slugs)} total analyses')
        return all_slugs

    def read_api_token(self):
        """Read the Botify API token from the token file."""
        try:
            if not os.path.exists(TOKEN_FILE):
                return None
            with open(TOKEN_FILE) as f:
                content = f.read().strip()
                token = content.split('\n')[0].strip()
            return token
        except Exception:
            return None

    async def _execute_qualifier_logic(self, username, project_name, analysis_slug, api_token, qualifier_config):
        """Execute the generic qualifier logic to determine a dynamic parameter.
        This method implements the generalized pattern for finding optimal parameters
        (like depth for link graphs) that keep exports within API limits. It iteratively
        tests values and finds the largest parameter that stays under the threshold.
        Args:
            username: Organization username
            project_name: Project name
            analysis_slug: Analysis slug
            api_token: Botify API token
            qualifier_config: Configuration dict from template's qualifier_config
        Returns:
            dict: {'parameter_value': determined_value, 'metric_at_parameter': metric_value}
        """
        import httpx
        import json
        wand = self.pipulate
        iter_param_name = qualifier_config['iterative_parameter_name']
        bql_template_str = json.dumps(qualifier_config['qualifier_bql_template'])
        collection_name = f"crawl.{analysis_slug}"
        # Replace collection placeholder
        bql_template_str = bql_template_str.replace("{collection}", collection_name)
        # Initialize iteration variables
        start_val, end_val, step_val = qualifier_config['iteration_range']
        determined_param_value = start_val
        metric_at_determined_param = 0
        threshold = qualifier_config['max_value_threshold']
        # Iterate through the range to find optimal parameter
        for current_iter_val in range(start_val, end_val + 1, step_val):
            # Replace iteration placeholder with proper type preservation
            current_bql_payload = json.loads(bql_template_str)

            def replace_iteration_placeholder(obj, placeholder, value):

                """Recursively replace placeholder strings with properly typed values."""
                if isinstance(obj, dict):
                    return {k: replace_iteration_placeholder(v, placeholder, value) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [replace_iteration_placeholder(item, placeholder, value) for item in obj]
                elif isinstance(obj, str) and obj == placeholder:
                    return value  # Keep as integer
                else:
                    return obj
            current_bql_payload = replace_iteration_placeholder(current_bql_payload, "{ITERATION_VALUE}", current_iter_val)
            # Construct full query payload
            query_payload = {
                "collections": [collection_name],
                "query": current_bql_payload
            }
            # Make API call
            url = f"https://api.botify.com/v1/projects/{username}/{project_name}/query"
            headers = {'Authorization': f'Token {api_token}', 'Content-Type': 'application/json'}
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, headers=headers, json=query_payload, timeout=60.0)
                if response.status_code != 200:
                    await self.message_queue.add(wand, f"API error during qualifier check at {iter_param_name}={current_iter_val}: Status {response.status_code}", verbatim=True)
                    break
                data = response.json()
                # Extract metric using the configured path
                try:
                    metric_value = data
                    for path_element in qualifier_config['target_metric_path']:
                        metric_value = metric_value[path_element]
                    # Convert to int if it's a number
                    if isinstance(metric_value, (int, float)):
                        metric_value = int(metric_value)
                    else:
                        metric_value = 0
                except (KeyError, IndexError, TypeError):
                    await self.message_queue.add(wand, f"Could not extract metric from response at {iter_param_name}={current_iter_val}", verbatim=True)
                    metric_value = 0
                await self.message_queue.add(wand, f"🔍 Qualifier '{iter_param_name}' at {current_iter_val}: {metric_value:,} items.", verbatim=True)
                # Check if we're within threshold
                if metric_value <= threshold:
                    determined_param_value = current_iter_val
                    metric_at_determined_param = metric_value
                    # Continue to find the largest value still under threshold
                else:
                    # Threshold exceeded
                    if current_iter_val == start_val:
                        # Even the first value exceeds threshold
                        await self.message_queue.add(wand, qualifier_config['user_message_threshold_exceeded'].format(metric_value=metric_value), verbatim=True)
                        determined_param_value = start_val
                        metric_at_determined_param = metric_value
                    # Break since further iterations will also exceed
                    break
            except Exception as e:
                await self.message_queue.add(wand, f"Error during qualifier check at {iter_param_name}={current_iter_val}: {str(e)}", verbatim=True)
                break
        return {
            'parameter_value': determined_param_value,
            'metric_at_parameter': metric_at_determined_param
        }

    async def get_deterministic_filepath(self, username, project_name, analysis_slug, data_type=None):
        """Generate a deterministic file path for a given data export.
        # FILE MANAGEMENT PATTERN: This demonstrates the standard approach to file caching:
        # 1. Create deterministic paths based on user/project identifiers
        # 2. Check if files exist before re-downloading
        # 3. Store metadata about cached files for user feedback
        # 4. Use app_name namespace to prevent collisions between workflows
        Args:
            username: Organization username
            project_name: Project name
            analysis_slug: Analysis slug
            data_type: Type of data (crawl, weblog, gsc) or None for base directory
        Returns:
            String path to either the file location or base directory
        """
        base_dir = f'downloads/{self.app_name}/{username}/{project_name}/{analysis_slug}'
        if not data_type:
            return base_dir
        filenames = {
            'crawl': 'crawl.csv',
            'weblog': 'weblog.csv',
            'gsc': 'gsc.csv',
            'crawl_attributes': 'crawl.csv',
            'link_graph_edges': 'link_graph.csv',
            'gsc_data': 'gsc.csv'
        }
        if data_type not in filenames:
            raise ValueError(f'Unknown data type: {data_type}')
        filename = filenames[data_type]
        return f'{base_dir}/{filename}'

    async def check_file_exists(self, filepath):
        """Check if a file exists and is non-empty.
        Args:
            filepath: Path to check
        Returns:
            (bool, dict): Tuple of (exists, file_info)
        """
        if not os.path.exists(filepath):
            return (False, {})
        stats = os.stat(filepath)
        if stats.st_size == 0:
            return (False, {})
        file_info = {'path': filepath, 'size': f'{stats.st_size / 1024:.1f} KB', 'created': time.ctime(stats.st_ctime)}
        return (True, file_info)

    async def ensure_directory_exists(self, filepath):
        directory = os.path.dirname(filepath)
        if not os.path.exists(directory):
            os.makedirs(directory)

    async def check_cached_file_for_button_text(self, username, project_name, analysis_slug, data_type):
        """Check if a file exists for the given parameters and return appropriate button text."""
        try:
            filepath = await self.get_deterministic_filepath(username, project_name, analysis_slug, data_type)
            exists, file_info = await self.check_file_exists(filepath)
            return exists
        except Exception:
            return False

    def _generate_api_call_representations(self, method: str, url: str, headers: dict, payload: Optional[dict] = None, step_context: Optional[str] = None, template_info: Optional[dict] = None, username: Optional[str] = None, project_name: Optional[str] = None) -> tuple[str, str]:
        """Generate both cURL and Python representations of API calls for debugging.
        CRITICAL INSIGHT: Jupyter Notebook Debugging Pattern
        ===================================================
        This method generates Python code specifically optimized for Jupyter Notebook debugging:
        1. Uses 'await main()' instead of 'asyncio.run(main())' for Jupyter compatibility
        2. Includes comprehensive error handling with detailed output
        3. Provides token loading from file (not hardcoded) for security
        4. Generates both /jobs (export) and /query (debugging) versions
        The Python code is designed to be:
        - Copy-pasteable into Jupyter cells
        - Self-contained with all imports and functions
        - Educational with clear variable names and comments
        - Debuggable with detailed error messages and response inspection
        This pattern emerged from painful debugging sessions where users needed to:
        - Quickly test API calls outside the workflow
        - Understand the exact structure of requests/responses
        - Debug authentication and payload issues
        - Learn the Botify API through working examples
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full API endpoint URL
            headers: Request headers dict
            payload: Optional request payload dict
            step_context: Optional context string for identification
        Returns:
            tuple: (curl_command_string, python_code_string)
        """
        api_token_placeholder = "{YOUR_BOTIFY_API_TOKEN}"
        safe_headers_for_display = headers.copy()
        if 'Authorization' in safe_headers_for_display:
            # Display placeholder for token in snippets
            safe_headers_for_display['Authorization'] = f"Token {api_token_placeholder}"
        header_str_curl = ""
        for k, v in safe_headers_for_display.items():
            header_str_curl += f" -H '{k}: {v}'"
        curl_command = f"curl -X {method.upper()} '{url}'{header_str_curl}"
        payload_json_str_for_curl = ""
        if payload:
            try:
                payload_json_str_for_curl = json.dumps(payload)
                # Escape single quotes for shell if payload might contain them
                payload_json_str_for_curl = payload_json_str_for_curl.replace("'", "'\\''")
                curl_command += f" --data-raw '{payload_json_str_for_curl}'"
            except TypeError: # Handle non-serializable payload if it occurs
                curl_command += " # Payload not shown due to non-serializable content"
        python_payload_str_for_script = "None"
        if payload:
            try:
                # Pretty print for Python script
                python_payload_str_for_script = json.dumps(payload, indent=4)
                # Python uses True/False/None, not true/false/null
                python_payload_str_for_script = python_payload_str_for_script.replace(": true", ": True").replace(": false", ": False").replace(": null", ": None")
            except TypeError:
                python_payload_str_for_script = "{# Payload not shown due to non-serializable content #}"
        # Determine step name from context, payload, or default
        step_name = "API Call"
        if step_context:
            step_name = step_context
        elif payload:
            step_name = self._get_step_name_from_payload(payload)
        # Build enhanced header with template information
        ui_constants = self.pipulate.get_ui_constants()
        python_emoji = ui_constants['EMOJIS']['PYTHON_CODE']
        comment_divider = ui_constants['CODE_FORMATTING']['COMMENT_DIVIDER']
        
        header_lines = [
            comment_divider,
            f"# Botify API Call Example",
            f"# Generated by: {self.DISPLAY_NAME} Workflow",
            f"# Step: {step_name}",
            f"# API Endpoint: {method.upper()} {url}"
        ]
        # Add organization and project info if available
        if username:
            header_lines.append(f"# Organization: {username}")
        if project_name:
            header_lines.append(f"# Project: {project_name}")
        # Add template-specific information if available
        if template_info:
            header_lines.append("#")
            header_lines.append(f"# Query Template: {template_info.get('name', 'Unknown')}")
            header_lines.append(f"# Description: {template_info.get('description', 'No description available')}")
            header_lines.append(f"# Export Type: {template_info.get('export_type', 'Unknown')}")
            # Add qualifier information if present
            qualifier_config = template_info.get('qualifier_config', {})
            if qualifier_config.get('enabled', False):
                header_lines.append("#")
                header_lines.append("# 🎯 SMART QUALIFIER SYSTEM:")
                header_lines.append(f"# This template uses automatic parameter optimization to stay under API limits.")
                param_name = qualifier_config.get('iterative_parameter_name', 'parameter')
                max_threshold = qualifier_config.get('max_value_threshold', 1000000)
                header_lines.append(f"# The system automatically finds the optimal {param_name} for ~{max_threshold:,} results.")
                if 'user_message_found' in qualifier_config:
                    # Extract the pattern from the user message
                    msg_template = qualifier_config['user_message_found']
                    if '{param_value}' in msg_template and '{metric_value}' in msg_template:
                        header_lines.append(f"# Example: 'Optimal {param_name}: 2 (for 235,623 results)'")
        header_lines.extend([
            "#",
            "# 🧪 For live JupyterLab environment to experiment with queries:",
            "# http://localhost:8888/lab/tree/helpers/botify/botify_api.ipynb",
            "#",
            "# 📋 For copy/paste-able examples to use in JupyterLab:",
            "# http://localhost:5001/documentation",
            comment_divider
        ])
        header_comment = "\n".join(header_lines)
        python_command = f"""{header_comment}
import httpx
import json
import asyncio
import os
from typing import Optional, Dict, Any
# Configuration
TOKEN_FILE = 'botify_token.txt'

def load_api_token() -> str:
    \"\"\"Load the Botify API token from the token file.\"\"\"
    try:
        if not os.path.exists(TOKEN_FILE):
            raise ValueError(f"Token file '{{TOKEN_FILE}}' not found.")
        with open(TOKEN_FILE) as f:
            content = f.read().strip()
            api_key = content.split('\\n')[0].strip()
            if not api_key:
                raise ValueError(f"Token file '{{TOKEN_FILE}}' is empty.")
            return api_key
    except Exception as e:
        raise ValueError(f"Error loading API token: {{str(e)}}")
# Configuration
API_TOKEN = load_api_token()
URL = "{url}"
METHOD = "{method.lower()}"

# Headers setup
def get_headers() -> Dict[str, str]:
    \"\"\"Generate headers for the API request.\"\"\"
    return {{
        'Authorization': f'Token {{API_TOKEN}}',
        'Content-Type': 'application/json',
        # Add any additional headers from the original request
        {', '.join(f"'{k}': '{v}'" for k, v in safe_headers_for_display.items() if k != 'Authorization')}
    }}
# Payload setup
PAYLOAD = {python_payload_str_for_script}

async def make_api_call(
    url: str,
    method: str,
    headers: Dict[str, str],
    payload: Optional[Dict[str, Any]] = None,
    timeout: float = 60.0
) -> Dict[str, Any]:
    \"\"\"
    Make an API call to the Botify API with proper error handling and response processing.
    Args:
        url: The API endpoint URL
        method: HTTP method (get, post, etc.)
        headers: Request headers
        payload: Optional request payload
        timeout: Request timeout in seconds
    Returns:
        Dict containing the API response data
    Raises:
        ValueError: If the API call fails or returns an error
    \"\"\"
    async with httpx.AsyncClient() as client:
        try:
            # Make the API call
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=payload if payload else None,
                timeout=timeout
            )
            # Log response details
            print(f"Status Code: {{response.status_code}}")
            print(f"Response Headers: {{dict(response.headers)}}")
            # Handle response
            response.raise_for_status()
            try:
                result = response.json()
                print("\\nResponse JSON:")
                print(json.dumps(result, indent=2))
                return result
            except json.JSONDecodeError:
                print("\\nResponse Text (not JSON):")
                print(response.text)
                return {{"text": response.text}}
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {{e.response.status_code}}: {{e.response.text}}"
            print(f"\\n❌ Error: {{error_msg}}")
            raise ValueError(error_msg)
        except httpx.RequestError as e:
            error_msg = f"Request error: {{str(e)}}"
            print(f"\\n❌ Error: {{error_msg}}")
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {{str(e)}}"
            print(f"\\n❌ Error: {{error_msg}}")
            raise ValueError(error_msg)

async def main():
    \"\"\"Main execution function\"\"\"
    try:
        # Make the API call
        result = await make_api_call(
            url=URL,
            method=METHOD,
            headers=get_headers(),
            payload=PAYLOAD
        )
        # Process the result as needed
        return result
    except Exception as e:
        print(f"\\n❌ Execution failed: {{str(e)}}")
        raise

# Execute in Jupyter Notebook:
await main()
# For standalone script execution:
# if __name__ == "__main__":
#     asyncio.run(main())
"""
        return curl_command, python_command

    async def process_search_console_data(self, wand, pipeline_id, step_id, username, project_name, analysis_slug, check_result):
        """Process search console data in the background."""
        logging.info(f'Starting real GSC data export for {username}/{project_name}/{analysis_slug}')
        try:
            gsc_filepath = await self.get_deterministic_filepath(username, project_name, analysis_slug, 'gsc')
            file_exists, file_info = await self.check_file_exists(gsc_filepath)
            if file_exists:
                await self.message_queue.add(wand, f"✅ Using cached GSC data ({file_info['size']})", verbatim=True)
                check_result.update({'download_complete': True, 'download_info': {'has_file': True, 'file_path': gsc_filepath, 'timestamp': file_info['created'], 'size': file_info['size'], 'cached': True}})
                check_result_str = json.dumps(check_result)
                await wand.set_step_data(pipeline_id, step_id, check_result_str, self.steps)
                return
            await self.message_queue.add(wand, '🔄 Initiating Search Console data export...', verbatim=True)
            api_token = self.read_api_token()
            if not api_token:
                raise ValueError('Cannot read API token')
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            export_query = await self.build_exports(username, project_name, analysis_slug, data_type='gsc', start_date=start_date, end_date=end_date)
            job_url = 'https://api.botify.com/v1/jobs'
            headers = {'Authorization': f'Token {api_token}', 'Content-Type': 'application/json'}
            # Generate Python command snippet (using /query endpoint for Jupyter debugging)
            _, _, python_command = self.generate_query_api_call(export_query['export_job_payload'], username, project_name)
            check_result['python_command'] = python_command
            try:
                logging.info(f"Submitting export job with payload: {json.dumps(export_query['export_job_payload'], indent=2)}")
                async with httpx.AsyncClient() as client:
                    response = await client.post(job_url, headers=headers, json=export_query['export_job_payload'], timeout=60.0)
                    logging.info(f'Export job submission response status: {response.status_code}')
                    try:
                        logging.info(f'Export job response: {json.dumps(response.json(), indent=2)}')
                    except:
                        logging.info(f'Could not parse response as JSON. Raw: {response.text[:500]}')
                    response.raise_for_status()
                    job_data = response.json()
                    job_url_path = job_data.get('job_url')
                    if not job_url_path:
                        raise ValueError('Failed to get job URL from response')
                    full_job_url = f'https://api.botify.com{job_url_path}'
                    logging.info(f'Got job URL: {full_job_url}')
                    await self.message_queue.add(wand, '✅ Export job created successfully!', verbatim=True)
            except Exception as e:
                logging.exception(f'Error creating export job: {str(e)}')
                await self.message_queue.add(wand, f'❌ Error creating export job: {str(e)}', verbatim=True)
                raise
            await self.message_queue.add(wand, '🔄 Polling for export completion...', verbatim=True)
            success, result = await self.poll_job_status(full_job_url, api_token, step_context="export")
            if not success:
                error_message = isinstance(result, str) and result or 'Export job failed'
                await self.message_queue.add(wand, f'❌ Export failed: {error_message}', verbatim=True)
                raise ValueError(f'Export failed: {error_message}')
            await self.message_queue.add(wand, '✅ Export completed and ready for download!', verbatim=True)
            download_url = result.get('download_url')
            if not download_url:
                await self.message_queue.add(wand, '❌ No download URL found in job result', verbatim=True)
                raise ValueError('No download URL found in job result')
            await self.message_queue.add(wand, '🔄 Downloading Search Console data...', verbatim=True)
            await self.ensure_directory_exists(gsc_filepath)
            zip_path = f'{gsc_filepath}.zip'
            try:
                async with httpx.AsyncClient() as client:
                    async with client.stream('GET', download_url, headers={'Authorization': f'Token {api_token}'}) as response:
                        response.raise_for_status()
                        with open(zip_path, 'wb') as f:
                            async for chunk in response.aiter_bytes():
                                f.write(chunk)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    csv_name = None
                    for name in zip_ref.namelist():
                        if name.endswith('.csv'):
                            csv_name = name
                            break
                    if not csv_name:
                        raise ValueError('No CSV file found in the downloaded zip')
                    zip_ref.extract(csv_name, os.path.dirname(gsc_filepath))
                    extracted_path = os.path.join(os.path.dirname(gsc_filepath), csv_name)
                    if extracted_path != gsc_filepath:
                        if os.path.exists(gsc_filepath):
                            os.remove(gsc_filepath)
                        os.rename(extracted_path, gsc_filepath)
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                _, file_info = await self.check_file_exists(gsc_filepath)
                await self.message_queue.add(wand, f"✅ Download complete: {file_info['path']} ({file_info['size']})", verbatim=True)
                df = pd.read_csv(gsc_filepath, skiprows=1)
                df.to_csv(gsc_filepath, index=False)
                download_info = {'has_file': True, 'file_path': gsc_filepath, 'timestamp': file_info['created'], 'size': file_info['size'], 'cached': False}
                check_result.update({'download_complete': True, 'download_info': download_info})
            except Exception as e:
                await self.message_queue.add(wand, f'❌ Error downloading or extracting file: {str(e)}', verbatim=True)
                raise
            await self.message_queue.add(wand, '✅ Search Console data ready for analysis!', verbatim=True)
            check_result_str = json.dumps(check_result)
            await wand.set_step_data(pipeline_id, step_id, check_result_str, self.steps)
        except Exception as e:
            logging.exception(f'Error in process_search_console_data: {e}')
            check_result.update({'download_complete': True, 'error': str(e)})
            check_result_str = json.dumps(check_result)
            await wand.set_step_data(pipeline_id, step_id, check_result_str, self.steps)
            await self.message_queue.add(wand, f'❌ Error processing Search Console data: {str(e)}', verbatim=True)
            raise

    async def build_exports(self, username, project_name, analysis_slug=None, data_type='crawl', start_date=None, end_date=None, dynamic_param_value=None, placeholder_for_dynamic_param=None):
        """Builds BQLv2 query objects and export job payloads.
        CRITICAL INSIGHT: Multiple BQL Structures in One Method
        =======================================================
        This method generates DIFFERENT payload structures depending on data_type:
        1. data_type='gsc': BQLv2 with periods array for Search Console
        2. data_type='crawl': BQLv2 with collections for crawl analysis
        3. data_type='weblog': BQLv2 with periods for web logs (NEWER structure)
        IMPORTANT: The weblog structure here is DIFFERENT from step_03_process!
        - build_exports creates: BQLv2 with periods in query.periods
        - step_03_process creates: BQLv1 with date_start/date_end at payload level
        This dual structure exists because:
        - build_exports follows modern BQLv2 patterns
        - step_03_process uses legacy BQLv1 patterns that actually work
        - Both must be supported for backward compatibility
        The conversion logic in _convert_bqlv1_to_query handles both patterns.
        Args:
            username: Organization slug
            project_name: Project slug
            analysis_slug: Analysis slug (required for crawl data)
            data_type: Type of data ('crawl', 'weblog', 'gsc')
            start_date: Start date for time-based queries
            end_date: End date for time-based queries
        Returns:
            dict: Export configuration with query payloads and URLs
        """
        api_token = self.read_api_token()
        base_url = "https://api.botify.com/v1/jobs"
        headers = {'Authorization': f'Token {api_token}', 'Content-Type': 'application/json'}
        if data_type == 'gsc':
            if not start_date or not end_date:
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
            # Use the configured GSC template
            gsc_template = self.get_configured_template('gsc')
            template_query = self.apply_template(gsc_template)
            export_job_payload = {
                'job_type': 'export',
                'payload': {
                    'query': {
                        'collections': ['search_console'],
                        'periods': [[start_date, end_date]],
                        'query': template_query
                    },
                    'export_size': config.BOTIFY_API['GSC_EXPORT_SIZE'],
                    'formatter': 'csv',
                    'connector': 'direct_download',
                    'formatter_config': {'print_header': True, 'print_delimiter': True},
                    'extra_config': {'compression': 'zip'},
                    'username': username,
                    'project': project_name,
                    'export_job_name': 'Search Console Export'
                }
            }
            check_query_payload = {
                'collections': ['search_console'],
                'periods': [[start_date, end_date]],
                'query': {
                    'dimensions': [],
                    'metrics': [{'function': 'count', 'args': ['search_console.url']}]
                }
            }
            # Log the GSC export details with template information
            gsc_template = self.get_configured_template('gsc')
            template_info = self.QUERY_TEMPLATES.get(gsc_template, {})
            curl_cmd, python_cmd = self._generate_api_call_representations(
                method="POST", url=base_url, headers=headers, payload=export_job_payload,
                step_context="Step 4: Search Console Export Job", template_info=template_info,
                username=username, project_name=project_name
            )
            await self.pipulate.log_api_call_details(
                pipeline_id="build_exports", step_id="gsc_export",
                call_description="Search Console Export Job Creation",
                http_method="POST", url=base_url, headers=headers, payload=export_job_payload,
                curl_command=curl_cmd, python_command=python_cmd
            )
            return {
                'check_query_payload': check_query_payload,
                'check_url': f'/v1/projects/{username}/{project_name}/query',
                'export_job_payload': export_job_payload,
                'export_url': '/v1/jobs',
                'data_type': data_type
            }
        elif data_type == 'crawl':
            if not analysis_slug:
                raise ValueError("analysis_slug is required for data_type 'crawl'")
            collection = f'crawl.{analysis_slug}'
            # Use the configured crawl template
            crawl_template = self.get_configured_template('crawl')
            template_query = self.apply_template(crawl_template, collection)
            # Apply dynamic parameter substitution if needed
            if placeholder_for_dynamic_param and dynamic_param_value is not None:
                # Use a more sophisticated substitution that preserves data types

                def replace_placeholder_with_typed_value(obj, placeholder, value):
                    """Recursively replace placeholder strings with properly typed values."""
                    if isinstance(obj, dict):
                        return {k: replace_placeholder_with_typed_value(v, placeholder, value) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [replace_placeholder_with_typed_value(item, placeholder, value) for item in obj]
                    elif isinstance(obj, str) and obj == placeholder:
                        # Convert string to appropriate type based on the value
                        if isinstance(value, (int, float)):
                            return value  # Keep as number
                        else:
                            return str(value)  # Convert to string if needed
                    else:
                        return obj
                template_query = replace_placeholder_with_typed_value(template_query, placeholder_for_dynamic_param, dynamic_param_value)
            bql_query = {
                'collections': [collection],
                'query': template_query
            }
            check_query_payload = {
                'collections': [collection],
                'query': {
                    'dimensions': [],
                    'metrics': [{'function': 'count', 'args': [f'{collection}.url']}],
                    'filters': {'field': f'{collection}.http_code', 'predicate': 'eq', 'value': 200}
                }
            }
            export_job_payload = {
                'job_type': 'export',
                'payload': {
                    'username': username,
                    'project': project_name,
                    'connector': 'direct_download',
                    'formatter': 'csv',
                    'export_size': config.BOTIFY_API['CRAWL_EXPORT_SIZE'],
                    'query': bql_query,
                    'formatter_config': {'print_header': True}
                }
            }
            # Log the crawl export details with template information
            template_info = self.QUERY_TEMPLATES.get(crawl_template, {})
            curl_cmd, python_cmd = self._generate_api_call_representations(
                method="POST", url=base_url, headers=headers, payload=export_job_payload,
                step_context="Step 2: Crawl Analysis Export Job", template_info=template_info,
                username=username, project_name=project_name
            )
            await self.pipulate.log_api_call_details(
                pipeline_id="build_exports", step_id="crawl_export",
                call_description="Crawl Analysis Export Job Creation",
                http_method="POST", url=base_url, headers=headers, payload=export_job_payload,
                curl_command=curl_cmd, python_command=python_cmd
            )
            return {
                'check_query_payload': check_query_payload,
                'check_url': f'/v1/projects/{username}/{project_name}/query',
                'export_job_payload': export_job_payload,
                'export_url': '/v1/jobs',
                'data_type': data_type
            }
        elif data_type == 'weblog':
            if not start_date or not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            bql_query = {
                'collections': ['logs'],
                'periods': [[start_date, end_date]],
                'query': {
                    'dimensions': ['logs.url'],
                    'metrics': ['logs.all.count_visits'],
                    'filters': {'field': 'logs.all.count_visits', 'predicate': 'gt', 'value': 0}
                }
            }
            check_query_payload = {
                'collections': ['logs'],
                'periods': [[start_date, end_date]],
                'query': {
                    'dimensions': [],
                    'metrics': [{'function': 'count', 'args': ['logs.url']}],
                    'filters': {'field': 'logs.all.count_visits', 'predicate': 'gt', 'value': 0}
                }
            }
            export_job_payload = {
                'job_type': 'logs_urls_export',
                'payload': {
                    'username': username,
                    'project': project_name,
                    'connector': 'direct_download',
                    'formatter': 'csv',
                    'export_size': config.BOTIFY_API['WEBLOG_EXPORT_SIZE'],
                    'query': bql_query,
                    'formatter_config': {'print_header': True},
                    'extra_config': {'compression': 'zip'}
                }
            }
            # Log the weblog export details
            curl_cmd, python_cmd = self._generate_api_call_representations(
                method="POST", url=base_url, headers=headers, payload=export_job_payload, step_context="Step 3: Web Logs Export Job"
            )
            await self.pipulate.log_api_call_details(
                pipeline_id="build_exports", step_id="weblog_export",
                call_description="Web Logs Export Job Creation",
                http_method="POST", url=base_url, headers=headers, payload=export_job_payload,
                curl_command=curl_cmd, python_command=python_cmd
            )
            return {
                'check_query_payload': check_query_payload,
                'check_url': f'/v1/projects/{username}/{project_name}/query',
                'export_job_payload': export_job_payload,
                'export_url': '/v1/jobs',
                'data_type': data_type
            }
        else:
            raise ValueError(f'Unknown data type: {data_type}')

    async def poll_job_status(self, job_url, api_token, max_attempts=20, step_context=None):
        """
        Poll the job status URL to check for completion with improved error handling
        Args:
            job_url: Full job URL to poll
            api_token: Botify API token
            max_attempts: Maximum number of polling attempts
            step_context: Optional string identifying which step is making the request
        Returns:
            Tuple of (success, result_dict_or_error_message)
        """
        attempt = 0
        delay = 2
        consecutive_network_errors = 0
        if not job_url.startswith('https://api.botify.com'):
            if job_url.startswith('/'):
                job_url = f'https://api.botify.com{job_url}'
            elif job_url.isdigit():
                job_url = f'https://api.botify.com/v1/jobs/{job_url}'
            else:
                job_url = f'https://api.botify.com/{job_url}'
        job_id = None
        try:
            parts = job_url.strip('/').split('/')
            if 'jobs' in parts:
                job_id_index = parts.index('jobs') + 1
                if job_id_index < len(parts):
                    job_id = parts[job_id_index]
                    await self.message_queue.add(self.pipulate, f'🎯 Using job ID {job_id} for polling...', verbatim=True)
        except Exception:
            pass
        # Use emoji for export context, otherwise use brackets
        if step_context == "export":
            step_prefix = '⏳ '
        elif step_context:
            step_prefix = f'[{step_context}] '
        else:
            step_prefix = ''
        poll_msg = f'{step_prefix}Starting polling for job: {job_url}' + (f' (ID: {job_id})' if job_id else '')
        logging.info(poll_msg)
        await self.message_queue.add(self.pipulate, poll_msg, verbatim=True)
        while attempt < max_attempts:
            try:
                if attempt == 0:
                    poll_attempt_msg = f'{step_prefix}Poll attempt {attempt + 1}/{max_attempts} for job: {job_url}'
                    logging.info(poll_attempt_msg)
                    await self.message_queue.add(self.pipulate, poll_attempt_msg, verbatim=True)
                elif attempt > 0:
                    poll_attempt_msg = f'{step_prefix}Polling... (attempt {attempt + 1}/{max_attempts})'
                    logging.info(poll_attempt_msg)
                    await self.message_queue.add(self.pipulate, poll_attempt_msg, verbatim=True)
                if consecutive_network_errors >= 2 and job_id:
                    alternative_url = f'https://api.botify.com/v1/jobs/{job_id}'
                    if alternative_url != job_url:
                        url_switch_msg = f'{step_prefix}Switching to direct job ID URL: {alternative_url}'
                        logging.info(url_switch_msg)
                        await self.message_queue.add(self.pipulate, url_switch_msg, verbatim=True)
                        job_url = alternative_url
                headers = {'Authorization': f'Token {api_token}'}
                # Log the polling request
                curl_cmd, python_cmd = self._generate_api_call_representations(
                    method="GET", url=job_url, headers=headers, step_context=f"{step_prefix}Job Status Polling"
                )
                if attempt == 0 or status == 'DONE':
                    await self.pipulate.log_api_call_details(
                        pipeline_id="poll_job_status", step_id=step_context or "polling",
                        call_description=f"Job Status Poll Attempt {attempt + 1}",
                        http_method="GET", url=job_url, headers=headers,
                        curl_command=curl_cmd, python_command=python_cmd
                    )
                async with httpx.AsyncClient(timeout=45.0) as client:
                    response = await client.get(job_url, headers=headers)
                    consecutive_network_errors = 0
                    try:
                        response_json = response.json()
                        if attempt == 0 or status == 'DONE':
                            logging.debug(f'Poll response: {json.dumps(response_json, indent=2)}')
                    except:
                        if attempt == 0 or status == 'DONE':
                            logging.debug(f'Could not parse response as JSON. Status: {response.status_code}, Raw: {response.text[:500]}')
                    if response.status_code == 401:
                        error_msg = f'{step_prefix}Authentication failed. Please check your API token.'
                        logging.error(error_msg)
                        await self.message_queue.add(self.pipulate, f'❌ {error_msg}', verbatim=True)
                        return (False, error_msg)
                    if response.status_code >= 400:
                        error_msg = f'{step_prefix}API error {response.status_code}: {response.text}'
                        logging.error(error_msg)
                        await self.message_queue.add(self.pipulate, f'❌ {error_msg}', verbatim=True)
                        return (False, error_msg)
                    job_data = response.json()
                    status = job_data.get('job_status')
                    if attempt == 0:
                        status_msg = f'{step_prefix}Poll attempt {attempt + 1}: status={status}'
                        logging.info(status_msg)
                        await self.message_queue.add(self.pipulate, status_msg, verbatim=True)
                    # Log the polling response
                    if attempt == 0 or status == 'DONE':
                        await self.pipulate.log_api_call_details(
                            pipeline_id="poll_job_status", step_id=step_context or "polling",
                            call_description=f"Job Status Poll Response {attempt + 1}",
                            http_method="GET", url=job_url, headers=headers,
                            response_status=response.status_code,
                            response_preview=json.dumps(job_data) if isinstance(job_data, dict) else str(job_data)
                        )
                    if status == 'DONE':
                        results = job_data.get('results', {})
                        success_msg = 'Job completed successfully!'
                        logging.info(f'{step_prefix}{success_msg}')
                        await self.message_queue.add(self.pipulate, f'✅ {success_msg}', verbatim=True)
                        return (True, {'download_url': results.get('download_url'), 'row_count': results.get('row_count'), 'file_size': results.get('file_size'), 'filename': results.get('filename'), 'expires_at': results.get('expires_at')})
                    if status == 'FAILED':
                        error_details = job_data.get('error', {})
                        error_message = error_details.get('message', 'Unknown error')
                        error_type = error_details.get('type', 'Unknown type')
                        error_msg = f'{step_prefix}Job failed with error type: {error_type}, message: {error_message}'
                        logging.error(error_msg)
                        await self.message_queue.add(self.pipulate, f'❌ {error_msg}', verbatim=True)
                        return (False, f'Export failed: {error_message} (Type: {error_type})')
                    attempt += 1
                    if attempt == 1:
                        wait_msg = f'{step_prefix}Job still processing.'
                    else:
                        wait_msg = f'{step_prefix}Still processing...'
                    logging.info(wait_msg)
                    await self.message_queue.add(self.pipulate, wait_msg, verbatim=True)
                    await asyncio.sleep(delay)
                    delay = min(int(delay * 1.5), 20)
            except (httpx.RequestError, socket.gaierror, socket.timeout) as e:
                consecutive_network_errors += 1
                error_msg = f'{step_prefix}Network error polling job status: {str(e)}'
                logging.error(error_msg)
                await self.message_queue.add(self.pipulate, f'❌ {error_msg}', verbatim=True)
                if job_id:
                    job_url = f'https://api.botify.com/v1/jobs/{job_id}'
                    retry_msg = f'{step_prefix}Retry with direct job ID URL: {job_url}'
                    logging.warning(retry_msg)
                    await self.message_queue.add(self.pipulate, retry_msg, verbatim=True)
                attempt += 1
                wait_msg = f'{step_prefix}Network error.'
                logging.info(wait_msg)
                await self.message_queue.add(self.pipulate, wait_msg, verbatim=True)
                await asyncio.sleep(delay)
                delay = min(int(delay * 2), 30)
            except Exception as e:
                error_msg = f'{step_prefix}Unexpected error in polling: {str(e)}'
                logging.exception(error_msg)
                await self.message_queue.add(self.pipulate, f'❌ {error_msg}', verbatim=True)
                attempt += 1
                wait_msg = f'{step_prefix}Unexpected error.'
                logging.info(wait_msg)
                await self.message_queue.add(self.pipulate, wait_msg, verbatim=True)
                await asyncio.sleep(delay)
                delay = min(int(delay * 2), 30)
        max_attempts_msg = f'{step_prefix}Maximum polling attempts reached'
        logging.warning(max_attempts_msg)
        await self.message_queue.add(self.pipulate, f'⚠️ {max_attempts_msg}', verbatim=True)
        return (False, 'Maximum polling attempts reached. The export job may still complete in the background.')

    async def step_02_process(self, request):
        """Process the actual download after showing the progress indicator."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_02'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form = await request.form()
        analysis_slug = form.get('analysis_slug', '').strip()
        username = form.get('username', '').strip()
        project_name = form.get('project_name', '').strip()
        if not all([analysis_slug, username, project_name]):
            return P('Error: Missing required parameters', cls='text-invalid')
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        analysis_result_str = step_data.get(step.done, '')
        analysis_result = json.loads(analysis_result_str) if analysis_result_str else {}
        # Get export_type from current template configuration (for cache detection)
        # This ensures cache works even before the step data is fully stored
        active_crawl_template_key = self.get_configured_template('crawl')
        active_template_details = self.QUERY_TEMPLATES.get(active_crawl_template_key, {})
        export_type = active_template_details.get('export_type', 'crawl_attributes')
        # Extract dynamic parameters from analysis_result (may be empty on first run)
        dynamic_param_value = analysis_result.get('dynamic_parameter_value')
        placeholder_for_dynamic_param = analysis_result.get('parameter_placeholder_in_main_query')
        try:
            crawl_filepath = await self.get_deterministic_filepath(username, project_name, analysis_slug, export_type)
            file_exists, file_info = await self.check_file_exists(crawl_filepath)
            if file_exists:
                await self.message_queue.add(wand, f"✅ Using cached crawl data ({file_info['size']})", verbatim=True)
                analysis_result.update({'download_complete': True, 'download_info': {'has_file': True, 'file_path': crawl_filepath, 'timestamp': file_info['created'], 'size': file_info['size'], 'cached': True}})
                # Generate Python debugging code even for cached files
                try:
                    analysis_date_obj = datetime.strptime(analysis_slug, '%Y%m%d')
                except ValueError:
                    analysis_date_obj = datetime.now()
                period_start = (analysis_date_obj - timedelta(days=30)).strftime('%Y-%m-%d')
                period_end = analysis_date_obj.strftime('%Y-%m-%d')
                # Use the configured crawl template with dynamic parameters
                collection = f'crawl.{analysis_slug}'
                crawl_template = self.get_configured_template('crawl')
                template_query = self.apply_template(crawl_template, collection)
                # Apply dynamic parameter substitution if needed
                if placeholder_for_dynamic_param and dynamic_param_value is not None:
                    query_str = json.dumps(template_query)
                    query_str = query_str.replace(placeholder_for_dynamic_param, str(dynamic_param_value))
                    template_query = json.loads(query_str)
                export_query = {
                    'job_type': 'export',
                    'payload': {
                        'username': username,
                        'project': project_name,
                        'connector': 'direct_download',
                        'formatter': 'csv',
                        'export_size': config.BOTIFY_API['CRAWL_EXPORT_SIZE'],
                        'query': {
                            'collections': [collection],
                            'query': template_query
                        }
                    }
                }
                # Generate Python command snippet (using /query endpoint for Jupyter debugging)
                _, _, python_command = self.generate_query_api_call(export_query, username, project_name)
                analysis_result['python_command'] = python_command
            else:
                await self.message_queue.add(wand, '🔄 Initiating crawl data export...', verbatim=True)
                api_token = self.read_api_token()
                if not api_token:
                    raise ValueError('Cannot read API token')
                try:
                    analysis_date_obj = datetime.strptime(analysis_slug, '%Y%m%d')
                except ValueError:
                    analysis_date_obj = datetime.now()
                period_start = (analysis_date_obj - timedelta(days=30)).strftime('%Y-%m-%d')
                period_end = analysis_date_obj.strftime('%Y-%m-%d')
                # Use the configured crawl template with dynamic parameters
                collection = f'crawl.{analysis_slug}'
                crawl_template = self.get_configured_template('crawl')
                template_query = self.apply_template(crawl_template, collection)
                # Apply dynamic parameter substitution if needed
                if placeholder_for_dynamic_param and dynamic_param_value is not None:
                    # Use type-preserving substitution that maintains integer values

                    def replace_placeholder_with_typed_value(obj, placeholder, value):
                        """Recursively replace placeholder strings with properly typed values."""
                        if isinstance(obj, dict):
                            return {k: replace_placeholder_with_typed_value(v, placeholder, value) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [replace_placeholder_with_typed_value(item, placeholder, value) for item in obj]
                        elif isinstance(obj, str) and obj == placeholder:
                            # Convert string to appropriate type based on the value
                            if isinstance(value, (int, float)):
                                return value  # Keep numeric types as-is
                            else:
                                return str(value)  # Convert other types to string
                        else:
                            return obj
                    template_query = replace_placeholder_with_typed_value(template_query, placeholder_for_dynamic_param, dynamic_param_value)
                export_query = {
                    'job_type': 'export',
                    'payload': {
                        'username': username,
                        'project': project_name,
                        'connector': 'direct_download',
                        'formatter': 'csv',
                        'export_size': config.BOTIFY_API['CRAWL_EXPORT_SIZE'],
                        'query': {
                            'collections': [collection],
                            'query': template_query
                        }
                    }
                }
                job_url = 'https://api.botify.com/v1/jobs'
                headers = {'Authorization': f'Token {api_token}', 'Content-Type': 'application/json'}
                logging.info(f'Submitting crawl export job with payload: {json.dumps(export_query, indent=2)}')
                # Generate Python command snippet (using /query endpoint for Jupyter debugging)
                _, _, python_command = self.generate_query_api_call(export_query, username, project_name)
                analysis_result['python_command'] = python_command
                async with httpx.AsyncClient() as client:
                    try:
                        response = await client.post(job_url, headers=headers, json=export_query, timeout=60.0)
                        if response.status_code >= 400:
                            error_detail = 'Unknown error'
                            try:
                                error_body = response.json()
                                error_detail = json.dumps(error_body, indent=2)
                                logging.error(f'API error details: {error_detail}')
                            except Exception:
                                error_detail = response.text[:500]
                                logging.error(f'API error text: {error_detail}')
                            response.raise_for_status()
                        job_data = response.json()
                        job_url_path = job_data.get('job_url')
                        if not job_url_path:
                            raise ValueError('Failed to get job URL from response')
                        full_job_url = f'https://api.botify.com{job_url_path}'
                        await self.message_queue.add(wand, '✅ Crawl export job created successfully!', verbatim=True)
                        await self.message_queue.add(wand, '🔄 Polling for export completion...', verbatim=True)
                    except httpx.HTTPStatusError as e:
                        error_message = f'Export request failed: HTTP {e.response.status_code}'
                        await self.message_queue.add(wand, f'❌ {error_message}', verbatim=True)
                        # Store the error in analysis_result but don't raise exception
                        analysis_result.update({
                            'download_complete': False,
                            'error': error_message,
                            'download_info': {
                                'has_file': False,
                                'error': error_message,
                                'timestamp': datetime.now().isoformat()
                            }
                        })
                        full_job_url = None  # Prevent polling
                    except Exception as e:
                        error_message = f'Export request failed: {str(e)}'
                        await self.message_queue.add(wand, f'❌ {error_message}', verbatim=True)
                        # Store the error in analysis_result but don't raise exception
                        analysis_result.update({
                            'download_complete': False,
                            'error': error_message,
                            'download_info': {
                                'has_file': False,
                                'error': error_message,
                                'timestamp': datetime.now().isoformat()
                            }
                        })
                        full_job_url = None  # Prevent polling
                if full_job_url:
                    success, result = await self.poll_job_status(full_job_url, api_token, step_context="export")
                    if not success:
                        error_message = isinstance(result, str) and result or 'Export job failed'
                        await self.message_queue.add(wand, f'❌ Export failed: {error_message}', verbatim=True)
                        # Try to get more detailed error by testing the /query endpoint
                        detailed_error = await self._diagnose_query_endpoint_error(export_query, username, project_name, api_token)
                        if detailed_error:
                            error_message = f"{error_message} | Detailed diagnosis: {detailed_error}"
                            await self.message_queue.add(wand, f'🔍 Detailed error diagnosis: {detailed_error}', verbatim=True)
                        # Store the error in analysis_result but don't raise exception
                        analysis_result.update({
                            'download_complete': False,
                            'error': error_message,
                            'download_info': {
                                'has_file': False,
                                'error': error_message,
                                'timestamp': datetime.now().isoformat()
                            }
                        })
                    else:
                        await self.message_queue.add(wand, '✅ Export completed and ready for download!', verbatim=True)
                        download_url = result.get('download_url')
                        if not download_url:
                            await self.message_queue.add(wand, '❌ No download URL found in job result', verbatim=True)
                            # Store the error in analysis_result but don't raise exception
                            analysis_result.update({
                                'download_complete': False,
                                'error': 'No download URL found in job result',
                                'download_info': {
                                    'has_file': False,
                                    'error': 'No download URL found in job result',
                                    'timestamp': datetime.now().isoformat()
                                }
                            })
                        else:
                            await self.message_queue.add(wand, '🔄 Downloading crawl data...', verbatim=True)
                            await self.ensure_directory_exists(crawl_filepath)
                            try:
                                gz_filepath = f'{crawl_filepath}.gz'
                                async with httpx.AsyncClient(timeout=300.0) as client:
                                    async with client.stream('GET', download_url, headers={'Authorization': f'Token {api_token}'}) as response:
                                        response.raise_for_status()
                                        with open(gz_filepath, 'wb') as gz_file:
                                            async for chunk in response.aiter_bytes():
                                                gz_file.write(chunk)
                                with gzip.open(gz_filepath, 'rb') as f_in:
                                    with open(crawl_filepath, 'wb') as f_out:
                                        shutil.copyfileobj(f_in, f_out)
                                os.remove(gz_filepath)
                                _, file_info = await self.check_file_exists(crawl_filepath)
                                await self.message_queue.add(wand, f"✅ Download complete: {file_info['path']} ({file_info['size']})", verbatim=True)
                                df = pd.read_csv(crawl_filepath)
                                # Apply appropriate column names based on export type
                                active_crawl_template_key = self.get_configured_template('crawl')
                                active_template_details = self.QUERY_TEMPLATES.get(active_crawl_template_key, {})
                                export_type = active_template_details.get('export_type', 'crawl_attributes')
                                if export_type == 'link_graph_edges':
                                    # Link graph exports have 2 columns: source URL, target URL
                                    if len(df.columns) == 2:
                                        df.columns = ['Source URL', 'Target URL']
                                    else:
                                        # Fallback for unexpected column count
                                        df.columns = [f'Column_{i+1}' for i in range(len(df.columns))]
                                elif export_type == 'crawl_attributes':
                                    # Attribute exports vary by template, use generic names
                                    if len(df.columns) == 4:
                                        df.columns = ['Full URL', 'Compliance Status', 'Compliance Details', 'Occurrence Count']
                                    elif len(df.columns) == 3:
                                        df.columns = ['Full URL', 'HTTP Status', 'Page Title']
                                    else:
                                        # Fallback for unexpected column count
                                        df.columns = [f'Column_{i+1}' for i in range(len(df.columns))]
                                else:
                                    # Generic fallback for unknown export types
                                    df.columns = [f'Column_{i+1}' for i in range(len(df.columns))]
                                df.to_csv(crawl_filepath, index=False)
                                download_info = {'has_file': True, 'file_path': crawl_filepath, 'timestamp': file_info['created'], 'size': file_info['size'], 'cached': False}
                                analysis_result.update({'download_complete': True, 'download_info': download_info})
                            except httpx.ReadTimeout as e:
                                error_message = f'Timeout error during file download: {str(e)}'
                                await self.message_queue.add(wand, f'❌ {error_message}', verbatim=True)
                                # Store the error in analysis_result but don't raise exception
                                analysis_result.update({
                                    'download_complete': False,
                                    'error': error_message,
                                    'download_info': {
                                        'has_file': False,
                                        'error': error_message,
                                        'timestamp': datetime.now().isoformat()
                                    }
                                })
                            except Exception as e:
                                error_message = f'Error downloading or decompressing file: {str(e)}'
                                await self.message_queue.add(wand, f'❌ {error_message}', verbatim=True)
                                # Store the error in analysis_result but don't raise exception
                                analysis_result.update({
                                    'download_complete': False,
                                    'error': error_message,
                                    'download_info': {
                                        'has_file': False,
                                        'error': error_message,
                                        'timestamp': datetime.now().isoformat()
                                    }
                                })
            # Only show success message if download was actually successful
            if analysis_result.get('download_complete', False) and 'error' not in analysis_result:
                await self.message_queue.add(wand, f"✅ Crawl data downloaded: {file_info['size']}", verbatim=True)
            analysis_result_str = json.dumps(analysis_result)
            await wand.set_step_data(pipeline_id, step_id, analysis_result_str, self.steps)
            # Determine status message and color based on success/failure
            if 'error' in analysis_result:
                status_color = 'red'
                download_message = f' (FAILED: {analysis_result["error"]})'
                status_text = 'FAILED to download'
            else:
                status_color = 'green' if analysis_result.get('download_complete', False) else 'red'
                download_message = ' (data downloaded)' if analysis_result.get('download_complete', False) else ''
                status_text = 'downloaded' if analysis_result.get('download_complete', False) else 'FAILED to download'
            action_buttons = self._create_action_buttons(analysis_result, step_id)
            widget = Div(
                Div(
                    Button(self.ui['BUTTON_LABELS']['HIDE_SHOW_CODE'],
                        cls=self.ui['BUTTON_STYLES']['STANDARD'],
                        hx_get=f'/{app_name}/toggle?step_id={step_id}',
                        hx_target=f'#{step_id}_widget',
                        hx_swap='innerHTML'
                    ),
                    *action_buttons,
                    style=self.ui['BUTTON_STYLES']['FLEX_CONTAINER']
                ),
                Div(
                    Pre(f'Status: Analysis {status_text}{download_message}', cls='code-block-container', style=f'color: {status_color}; display: none;'),
                    id=f'{step_id}_widget'
                )
            )
            return Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Analysis {status_text}{download_message}', widget=widget, steps=self.steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        except Exception as e:
            logging.exception(f'Error in step_02_process: {e}')
            return P(f'Error: {str(e)}', cls='text-invalid')

    async def step_03_process(self, request):
        """Process the web logs check and download if available."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_03'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form = await request.form()
        analysis_slug = form.get('analysis_slug', '').strip()
        username = form.get('username', '').strip()
        project_name = form.get('project_name', '').strip()
        if not all([analysis_slug, username, project_name]):
            return P('Error: Missing required parameters', cls='text-invalid')
        try:
            has_logs, error_message = await self.check_if_project_has_collection(username, project_name, 'logs')
            if error_message:
                return P(f'Error: {error_message}', cls='text-invalid')
            check_result = {'has_logs': has_logs, 'project': project_name, 'username': username, 'analysis_slug': analysis_slug, 'timestamp': datetime.now().isoformat()}
            status_text = 'HAS' if has_logs else 'does NOT have'
            await self.message_queue.add(wand, f'{step.show} complete: Project {status_text} web logs', verbatim=True)
            if has_logs:
                logs_filepath = await self.get_deterministic_filepath(username, project_name, analysis_slug, 'weblog')
                file_exists, file_info = await self.check_file_exists(logs_filepath)
                if file_exists:
                    await self.message_queue.add(wand, f"✅ Using cached web logs data ({file_info['size']})", verbatim=True)
                    check_result.update({'download_complete': True, 'download_info': {'has_file': True, 'file_path': logs_filepath, 'timestamp': file_info['created'], 'size': file_info['size'], 'cached': True}})
                    # Generate Python debugging code even for cached files
                    try:
                        analysis_date_obj = datetime.strptime(analysis_slug, '%Y%m%d')
                    except ValueError:
                        analysis_date_obj = datetime.now()
                    date_end = analysis_date_obj.strftime('%Y-%m-%d')
                    date_start = (analysis_date_obj - timedelta(days=30)).strftime('%Y-%m-%d')
                    # CRITICAL: This creates BQLv1 structure with dates at payload level (NOT in periods)
                    # This structure is what _convert_bqlv1_to_query expects to find for proper conversion
                    export_query = {'job_type': 'logs_urls_export', 'payload': {'query': {'filters': {'field': 'crawls.google.count', 'predicate': 'gt', 'value': 0}, 'fields': ['url', 'crawls.google.count'], 'sort': [{'crawls.google.count': {'order': 'desc'}}]}, 'export_size': config.BOTIFY_API['WEBLOG_EXPORT_SIZE'], 'formatter': 'csv', 'connector': 'direct_download', 'formatter_config': {'print_header': True, 'print_delimiter': True}, 'extra_config': {'compression': 'zip'}, 'date_start': date_start, 'date_end': date_end, 'username': username, 'project': project_name}}
                    # Generate Python command snippet (using /query endpoint for Jupyter debugging)
                    _, _, python_command = self.generate_query_api_call(export_query, username, project_name)
                    check_result['python_command'] = python_command
                else:
                    await self.message_queue.add(wand, '🔄 Initiating web logs export...', verbatim=True)
                    api_token = self.read_api_token()
                    if not api_token:
                        raise ValueError('Cannot read API token')
                    try:
                        analysis_date_obj = datetime.strptime(analysis_slug, '%Y%m%d')
                    except ValueError:
                        analysis_date_obj = datetime.now()
                    date_end = analysis_date_obj.strftime('%Y-%m-%d')
                    date_start = (analysis_date_obj - timedelta(days=30)).strftime('%Y-%m-%d')
                    # CRITICAL: This creates BQLv1 structure with dates at payload level (NOT in periods)
                    # This structure is what _convert_bqlv1_to_query expects to find for proper conversion
                    export_query = {'job_type': 'logs_urls_export', 'payload': {'query': {'filters': {'field': 'crawls.google.count', 'predicate': 'gt', 'value': 0}, 'fields': ['url', 'crawls.google.count'], 'sort': [{'crawls.google.count': {'order': 'desc'}}]}, 'export_size': config.BOTIFY_API['WEBLOG_EXPORT_SIZE'], 'formatter': 'csv', 'connector': 'direct_download', 'formatter_config': {'print_header': True, 'print_delimiter': True}, 'extra_config': {'compression': 'zip'}, 'date_start': date_start, 'date_end': date_end, 'username': username, 'project': project_name}}
                    job_url = 'https://api.botify.com/v1/jobs'
                    headers = {'Authorization': f'Token {api_token}', 'Content-Type': 'application/json'}
                    logging.info(f'Submitting logs export job with payload: {json.dumps(export_query, indent=2)}')
                    # Generate Python command snippet (using /query endpoint for Jupyter debugging)
                    _, _, python_command = self.generate_query_api_call(export_query, username, project_name)
                    check_result['python_command'] = python_command
                    job_id = None
                    async with httpx.AsyncClient() as client:
                        try:
                            response = await client.post(job_url, headers=headers, json=export_query, timeout=60.0)
                            if response.status_code >= 400:
                                error_detail = 'Unknown error'
                                try:
                                    error_body = response.json()
                                    error_detail = json.dumps(error_body, indent=2)
                                    logging.error(f'API error details: {error_detail}')
                                except Exception:
                                    error_detail = response.text[:500]
                                    logging.error(f'API error text: {error_detail}')
                                response.raise_for_status()
                            job_data = response.json()
                            job_url_path = job_data.get('job_url')
                            if not job_url_path:
                                raise ValueError('Failed to get job URL from response')
                            job_id = job_url_path.strip('/').split('/')[-1]
                            if not job_id:
                                raise ValueError('Failed to extract job ID from job URL')
                            full_job_url = f'https://api.botify.com/v1/jobs/{job_id}'
                            await self.message_queue.add(wand, f'✅ Web logs export job created successfully! (Job ID: {job_id})', verbatim=True)
                            await self.message_queue.add(wand, '🔄 Polling for export completion...', verbatim=True)
                        except httpx.HTTPStatusError as e:
                            error_message = f'Export request failed: HTTP {e.response.status_code}'
                            await self.message_queue.add(wand, f'❌ {error_message}', verbatim=True)
                            # Store the error in check_result but don't raise exception
                            check_result.update({
                                'download_complete': False,
                                'error': error_message,
                                'download_info': {
                                    'has_file': False,
                                    'error': error_message,
                                    'timestamp': datetime.now().isoformat()
                                }
                            })
                            has_logs = False
                            job_id = None  # Prevent polling
                        except Exception as e:
                            error_message = f'Export request failed: {str(e)}'
                            await self.message_queue.add(wand, f'❌ {error_message}', verbatim=True)
                            # Store the error in check_result but don't raise exception
                            check_result.update({
                                'download_complete': False,
                                'error': error_message,
                                'download_info': {
                                    'has_file': False,
                                    'error': error_message,
                                    'timestamp': datetime.now().isoformat()
                                }
                            })
                            has_logs = False
                            job_id = None  # Prevent polling
                    if job_id:
                        await self.message_queue.add(wand, f'🎯 Using job ID {job_id} for polling...', verbatim=True)
                        full_job_url = f'https://api.botify.com/v1/jobs/{job_id}'
                    success, result = await self.poll_job_status(full_job_url, api_token, step_context="export")
                    if not success:
                        error_message = isinstance(result, str) and result or 'Export job failed'
                        await self.message_queue.add(wand, f'❌ Export failed: {error_message}', verbatim=True)
                        # Try to get more detailed error by testing the /query endpoint
                        detailed_error = await self._diagnose_query_endpoint_error(export_query, username, project_name, api_token)
                        if detailed_error:
                            error_message = f"{error_message} | Detailed diagnosis: {detailed_error}"
                            await self.message_queue.add(wand, f'🔍 Detailed error diagnosis: {detailed_error}', verbatim=True)
                        # Store the error in check_result but don't raise exception
                        check_result.update({
                            'download_complete': False,
                            'error': error_message,
                            'download_info': {
                                'has_file': False,
                                'error': error_message,
                                'timestamp': datetime.now().isoformat()
                            }
                        })
                        # Set has_logs to False to indicate failure
                        has_logs = False
                        # Skip the download section and go directly to widget creation
                    else:
                        await self.message_queue.add(wand, '✅ Export completed and ready for download!', verbatim=True)
                        download_url = result.get('download_url')
                        if not download_url:
                            await self.message_queue.add(wand, '❌ No download URL found in job result', verbatim=True)
                            # Store the error in check_result but don't raise exception
                            check_result.update({
                                'download_complete': False,
                                'error': 'No download URL found in job result',
                                'download_info': {
                                    'has_file': False,
                                    'error': 'No download URL found in job result',
                                    'timestamp': datetime.now().isoformat()
                                }
                            })
                            has_logs = False
                        else:
                            await self.message_queue.add(wand, '🔄 Downloading web logs data...', verbatim=True)
                            await self.ensure_directory_exists(logs_filepath)
                            try:
                                compressed_path = f'{logs_filepath}.compressed'
                                async with httpx.AsyncClient() as client:
                                    async with client.stream('GET', download_url, headers={'Authorization': f'Token {api_token}'}) as response:
                                        response.raise_for_status()
                                        with open(compressed_path, 'wb') as f:
                                            async for chunk in response.aiter_bytes():
                                                f.write(chunk)
                                try:
                                    with gzip.open(compressed_path, 'rb') as f_in:
                                        with open(logs_filepath, 'wb') as f_out:
                                            shutil.copyfileobj(f_in, f_out)
                                    logging.info(f'Successfully extracted gzip file to {logs_filepath}')
                                except gzip.BadGzipFile:
                                    try:
                                        with zipfile.ZipFile(compressed_path, 'r') as zip_ref:
                                            csv_files = [f for f in zip_ref.namelist() if f.endswith('.csv')]
                                            if not csv_files:
                                                raise ValueError('No CSV files found in the zip archive')
                                            with zip_ref.open(csv_files[0]) as source:
                                                with open(logs_filepath, 'wb') as target:
                                                    shutil.copyfileobj(source, target)
                                        logging.info(f'Successfully extracted zip file to {logs_filepath}')
                                    except zipfile.BadZipFile:
                                        shutil.copy(compressed_path, logs_filepath)
                                        logging.info(f"File doesn't appear to be compressed, copying directly to {logs_filepath}")
                                if os.path.exists(compressed_path):
                                    os.remove(compressed_path)
                                _, file_info = await self.check_file_exists(logs_filepath)
                                await self.message_queue.add(wand, f"✅ Download complete: {file_info['path']} ({file_info['size']})", verbatim=True)
                                await self.message_queue.add(wand, f"✅ Web logs data downloaded: {file_info['size']}", verbatim=True)
                                # Mark download as complete for button creation
                                check_result.update({
                                    'download_complete': True,
                                    'download_info': {
                                        'has_file': True,
                                        'file_path': logs_filepath,
                                        'timestamp': file_info['created'],
                                        'size': file_info['size'],
                                        'cached': False
                                    }
                                })
                            except Exception as e:
                                await self.message_queue.add(wand, f'❌ Error downloading file: {str(e)}', verbatim=True)
                                # Store the error in check_result but don't raise exception
                                check_result.update({
                                    'download_complete': False,
                                    'error': f'Error downloading file: {str(e)}',
                                    'download_info': {
                                        'has_file': False,
                                        'error': f'Error downloading file: {str(e)}',
                                        'timestamp': datetime.now().isoformat()
                                    }
                                })
                                has_logs = False
            check_result_str = json.dumps(check_result)
            await wand.set_step_data(pipeline_id, step_id, check_result_str, steps)
            # Determine status message and color based on success/failure
            if 'error' in check_result:
                status_color = 'red'
                download_message = f' (FAILED: {check_result["error"]})'
                status_text = 'FAILED to download'
            else:
                status_color = 'green' if has_logs else 'red'
                download_message = ' (data downloaded)' if has_logs else ''
            action_buttons = self._create_action_buttons(check_result, step_id)
            widget = Div(
                Div(
                    Button(self.ui['BUTTON_LABELS']['HIDE_SHOW_CODE'],
                        cls=self.ui['BUTTON_STYLES']['STANDARD'],
                        hx_get=f'/{app_name}/toggle?step_id={step_id}',
                        hx_target=f'#{step_id}_widget',
                        hx_swap='innerHTML'
                    ),
                    *action_buttons,
                    style=self.ui['BUTTON_STYLES']['FLEX_CONTAINER']
                ),
                Div(
                    Pre(f'Status: Project {status_text} web logs{download_message}', cls='code-block-container', style=f'color: {status_color}; display: none;'),
                    id=f'{step_id}_widget'
                )
            )
            return Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Project {status_text} web logs{download_message}', widget=widget, steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        except Exception as e:
            logging.exception(f'Error in step_03_process: {e}')
            return Div(P(f'Error: {str(e)}', cls='text-invalid'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)

    async def common_toggle(self, request):
        """Unified toggle method for all step widgets using configuration-driven approach."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        # Extract step_id from query parameters
        step_id = request.query_params.get('step_id')
        if not step_id or step_id not in self.TOGGLE_CONFIG:
            return Div("Invalid step ID", style="color: red;")
        config = self.TOGGLE_CONFIG[step_id]
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        # Handle simple content case (step_05)
        if 'simple_content' in config:
            state = wand.read_state(pipeline_id)
            is_visible = state.get(f'{step_id}_widget_visible', False)
            if f'{step_id}_widget_visible' not in state:
                state[f'{step_id}_widget_visible'] = True
                wand.write_state(pipeline_id, state)
                return Pre(config['simple_content'], cls='code-block-container')
            state[f'{step_id}_widget_visible'] = not is_visible
            wand.write_state(pipeline_id, state)
            if is_visible:
                return Pre(config['simple_content'], cls='code-block-container', style='display: none;')
            else:
                return Pre(config['simple_content'], cls='code-block-container')
        # Handle complex data-driven content
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        # Extract data based on configuration
        data_str = step_data.get(step.done, '')
        data_obj = json.loads(data_str) if data_str else {}
        # Get python command for display
        python_command = data_obj.get('python_command', '')
        # Determine status message and color
        status_prefix = config.get('status_prefix', '')
        if 'error' in data_obj:
            status_text = f'{config["error_prefix"]}: {data_obj["error"]}'
            status_color = 'red'
        else:
            has_data = data_obj.get(config['status_field'], False)
            status_text = f'{status_prefix}{config["success_text"] if has_data else config["failure_text"]}'
            status_color = 'green' if has_data else 'red'
        # Handle visibility toggle
        state = wand.read_state(pipeline_id)
        is_visible = state.get(f'{step_id}_widget_visible', False)
        # Create the content div
        content_div = Div(
            P(f'Status: {status_text}', style=f'color: {status_color};'),
            H4('Python Command (for debugging):'),
            Pre(Code(python_command, cls='language-python'), cls='code-block-container'),
            Script(f"""
                setTimeout(function() {{
                    if (typeof Prism !== 'undefined') {{
                        Prism.highlightAllUnder(document.getElementById('{step_id}_widget'));
                    }}
                }}, 100);
            """)
        )
        # Special case: If this is the first toggle after download (state not set yet)
        if f'{step_id}_widget_visible' not in state:
            state[f'{step_id}_widget_visible'] = True
            wand.write_state(pipeline_id, state)
            return content_div
        # Normal toggle behavior
        state[f'{step_id}_widget_visible'] = not is_visible
        wand.write_state(pipeline_id, state)
        if is_visible:
            # Hide the content
            content_div.attrs['style'] = 'display: none;'
            return content_div
        else:
            # Show the content
            return content_div

    async def update_button_text(self, request):
        """Update button text dynamically based on selected analysis."""
        try:
            form = await request.form()
            analysis_slug = form.get('analysis_slug', '').strip()
            username = form.get('username', '').strip()
            project_name = form.get('project_name', '').strip()
            
            if not all([analysis_slug, username, project_name]):
                # Return default button if missing parameters
                return Button('Download Data ▸', type='submit', cls='mt-10px primary', id='submit-button',
                             **{'hx-on:click': 'this.setAttribute("aria-busy", "true"); this.textContent = "Processing..."'})
            
            # Get active template details
            active_crawl_template_key = self.get_configured_template('crawl')
            active_template_details = self.QUERY_TEMPLATES.get(active_crawl_template_key, {})
            button_suffix = active_template_details.get('button_label_suffix', 'Data')
            export_type = active_template_details.get('export_type', 'crawl_attributes')
            
            # Check if files are cached for the selected analysis
            is_cached = await self.check_cached_file_for_button_text(username, project_name, analysis_slug, export_type)
            
            # Determine button text
            button_text = f'Use Cached {button_suffix} ▸' if is_cached else f'Download {button_suffix} ▸'
            
            return Button(button_text, type='submit', cls='mt-10px primary', id='submit-button',
                         **{'hx-on:click': 'this.setAttribute("aria-busy", "true"); this.textContent = "Processing..."'})
            
        except Exception as e:
            import logging
            logging.exception(f'Error in update_button_text: {e}')
            return Button('Download Data ▸', type='submit', cls='mt-10px primary', id='submit-button',
                         **{'hx-on:click': 'this.setAttribute("aria-busy", "true"); this.textContent = "Processing..."'})

    def convert_jobs_to_query_payload(self, jobs_payload, username, project_name, page_size=100):
        """
        Convert a /jobs export payload to a /query payload for debugging in Jupyter.
        Handles both BQLv1 (web logs) and BQLv2 (crawl, GSC) query formats.
        CRITICAL INSIGHT: BQL Version Detection
        ======================================
        The same job_type can use different BQL versions:
        - 'logs_urls_export' = BQLv1 (legacy web logs structure)
        - 'export' = BQLv2 (modern crawl/GSC structure)
        This detection is ESSENTIAL because:
        1. BQLv1 and BQLv2 have completely different payload structures
        2. They use different API endpoints (app.botify.com vs api.botify.com)
        3. Wrong detection = wrong conversion = 404 errors
        Args:
            jobs_payload: The original /jobs payload dict
            username: Organization slug (goes in URL for /query)
            project_name: Project slug (goes in URL for /query)
            page_size: Number of results per page (default 100)
        Returns:
            tuple: (query_payload, page_size, bql_version)
        """
        # Detect BQL version and job type
        job_type = jobs_payload.get('job_type', 'export')
        is_bqlv1 = job_type == 'logs_urls_export'
        if is_bqlv1:
            # BQLv1 Web Logs - different structure
            return self._convert_bqlv1_to_query(jobs_payload, username, project_name, page_size)
        else:
            # BQLv2 Crawl/GSC - standard structure
            return self._convert_bqlv2_to_query(jobs_payload, username, project_name, page_size)

    def _convert_bqlv2_to_query(self, jobs_payload, username, project_name, page_size):
        """Convert BQLv2 jobs payload to query format (crawl, GSC)"""
        # Extract the core query from the jobs payload
        if 'payload' in jobs_payload and 'query' in jobs_payload['payload']:
            # Standard export job structure
            core_query = jobs_payload['payload']['query']
        elif 'query' in jobs_payload:
            # Direct query structure (some job types)
            core_query = jobs_payload['query']
        else:
            raise ValueError("Could not find query structure in jobs payload")
        # Build the /query payload (no size field - that goes in URL)
        query_payload = {
            "collections": core_query.get("collections", []),
            "query": core_query.get("query", {})
        }
        # Handle periods if present (for GSC)
        if "periods" in core_query:
            query_payload["periods"] = core_query["periods"]
        return query_payload, page_size, "BQLv2"
        
    def _convert_bqlv1_to_query(self, jobs_payload, username, project_name, page_size):
        """Convert BQLv1 jobs payload to web logs endpoint format
        CRITICAL INSIGHT: Botify Web Logs API Evolution
        ===============================================
        The Botify API has evolved from BQLv1 to BQLv2, but BOTH patterns coexist in the same codebase.
        This method must handle TWO different payload structures for the SAME job_type ('logs_urls_export'):
        LEGACY BQLv1 Structure (used by step_03_process):
        {
            'job_type': 'logs_urls_export',
            'payload': {
                'date_start': '2025-04-25',  # <-- DATES AT PAYLOAD LEVEL
                'date_end': '2025-05-25',    # <-- DATES AT PAYLOAD LEVEL
                'query': {
                    'filters': {...},
                    'fields': [...],
                    'sort': [...]
                }
            }
        }
        MODERN BQLv2 Structure (used by build_exports):
        {
            'job_type': 'logs_urls_export',
            'payload': {
                'query': {
                    'collections': ['logs'],
                    'periods': [['2025-04-25', '2025-05-25']],  # <-- DATES IN PERIODS
                    'query': {...}
                }
            }
        }
        PAINFUL LESSON: The date extraction logic MUST check payload level FIRST because:
        1. The actual workflow (step_03_process) uses BQLv1 structure
        2. Looking for 'periods' first will fail for real payloads
        3. Missing dates = broken URLs = 404 errors
        URL STRUCTURE CRITICAL: Web logs use different base URL than other Botify APIs:
        - Standard API: https://api.botify.com/v1/...
        - Web Logs API: https://app.botify.com/api/v1/logs/.../urls/{start_date}/{end_date}
        Args:
            jobs_payload: The original /jobs export payload (either BQLv1 or BQLv2 structure)
            username: Organization slug (goes in URL path)
            project_name: Project slug (goes in URL path)
            page_size: Results per page (not used for BQLv1, kept for consistency)
        Returns:
            tuple: (query_payload_dict, page_size, "BQLv1")
        Raises:
            ValueError: If payload structure is unrecognized or dates cannot be extracted
        """
        # Web logs use a special BQLv1 endpoint: /v1/logs/{username}/{project}/urls/{start_date}/{end_date}
        # Extract the payload from the jobs payload
        if 'payload' not in jobs_payload:
            raise ValueError("Could not find payload in jobs payload")
        payload = jobs_payload['payload']
        # Extract dates from the payload level (BQLv1 structure)
        start_date = ""
        end_date = ""
        # CRITICAL: Check payload level FIRST - this is the actual BQLv1 structure used by step_03_process
        # The step_03_process method generates payloads with 'date_start'/'date_end' at payload level
        if 'date_start' in payload and 'date_end' in payload:
            # Convert from YYYY-MM-DD to YYYYMMDD format for the endpoint
            start_date = payload['date_start'].replace("-", "")
            end_date = payload['date_end'].replace("-", "")
        elif 'query' in payload and 'periods' in payload['query']:
            # Fallback: try to get from nested query periods (newer BQLv2-style structure)
            # This handles payloads generated by build_exports method with modern structure
            periods = payload['query'].get("periods", [])
            if periods and len(periods) > 0 and len(periods[0]) >= 2:
                start_date = periods[0][0].replace("-", "")
                end_date = periods[0][1].replace("-", "")
        # Extract the actual BQLv1 query structure
        if 'query' in payload:
            query_body = payload['query']
        else:
            raise ValueError("Could not find query structure in payload")
        query_payload = {
            "endpoint_type": "web_logs_bqlv1",
            "start_date": start_date,
            "end_date": end_date,
            "query_body": query_body,
            "date_start_original": payload.get('date_start', ''),
            "date_end_original": payload.get('date_end', '')
        }
        return query_payload, page_size, "BQLv1"

    def generate_query_api_call(self, jobs_payload, username, project_name, page_size=100):
        """
        Generate a complete /query API call from a /jobs payload for Jupyter debugging.
        Args:
            jobs_payload: The original /jobs export payload
            username: Organization slug
            project_name: Project slug
            page_size: Results per page
        Returns:
            tuple: (query_url, query_payload, python_code)
        """
        # Convert the payload
        query_payload, page_size, bql_version = self.convert_jobs_to_query_payload(jobs_payload, username, project_name, page_size)
        if bql_version == "BQLv1":
            return self._generate_bqlv1_python_code(query_payload, username, project_name, jobs_payload)
        else:
            return self._generate_bqlv2_python_code(query_payload, username, project_name, page_size, jobs_payload)

    def _generate_bqlv2_python_code(self, query_payload, username, project_name, page_size, jobs_payload):
        """Generate Python code for BQLv2 queries (crawl, GSC) - Now using reusable utility!"""
        return self.pipulate.generate_botify_bqlv2_python_code(
            query_payload=query_payload,
            username=username,
            project_name=project_name,
            page_size=page_size,
            jobs_payload=jobs_payload,
            display_name=self.DISPLAY_NAME,
            get_step_name_from_payload_func=self._get_step_name_from_payload,
            get_configured_template_func=self.get_configured_template,
            query_templates=self.QUERY_TEMPLATES
        )

    def _generate_bqlv1_python_code(self, query_payload, username, project_name, jobs_payload):
        """Generate Python code for BQLv1 queries (web logs) - Now using reusable utility!"""
        return self.pipulate.generate_botify_bqlv1_python_code(
            query_payload=query_payload,
            username=username,
            project_name=project_name,
            jobs_payload=jobs_payload,
            display_name=self.DISPLAY_NAME,
            get_step_name_from_payload_func=self._get_step_name_from_payload
        )

    def _get_step_name_from_payload(self, jobs_payload):
        """
        Determine which step/data type this payload represents based on its structure.
        Args:
            jobs_payload: The jobs payload to analyze
        Returns:
            str: Human-readable step name
        """
        try:
            # Check for GSC data (has periods and search_console collection)
            if 'payload' in jobs_payload and 'query' in jobs_payload['payload']:
                query = jobs_payload['payload']['query']
                collections = query.get('collections', [])
                if 'search_console' in collections:
                    return "Step 4: Download Search Console"
                elif any('crawl.' in col for col in collections):
                    return "Step 2: Download Crawl Analysis"
                elif 'logs' in collections:
                    return "Step 3: Download Web Logs"
            # Check job_type for web logs
            job_type = jobs_payload.get('job_type', '')
            if job_type == 'logs_urls_export':
                return "Step 3: Download Web Logs"
            elif job_type == 'export':
                # Could be crawl or GSC, check collections again
                if 'payload' in jobs_payload:
                    payload = jobs_payload['payload']
                    if 'query' in payload:
                        collections = payload['query'].get('collections', [])
                        if 'search_console' in collections:
                            return "Step 4: Download Search Console"
                        elif any('crawl.' in col for col in collections):
                            return "Step 2: Download Crawl Analysis"
            return "Botify Data Export"
        except Exception:
            return "Botify Data Export"

    async def _diagnose_query_endpoint_error(self, jobs_payload, username, project_name, api_token):
        """
        When the /jobs endpoint fails with generic errors, test the /query endpoint
        to get more detailed error information for debugging.
        This method converts the jobs payload to a query payload and tests it against
        the /query endpoint that the Python debugging code uses, which often provides
        much more descriptive error messages.
        """
        try:
            # Use the same conversion logic as the Python debugging code
            query_payload, page_size, bql_version = self.convert_jobs_to_query_payload(jobs_payload, username, project_name, page_size=1)
            headers = {
                'Authorization': f'Token {api_token}',
                'Content-Type': 'application/json'
            }
            # Handle different BQL versions with different endpoints
            if bql_version == "BQLv1":
                # For web logs, construct the BQLv1 endpoint URL
                start_date = query_payload.get('start_date', '')
                end_date = query_payload.get('end_date', '')
                if not start_date or not end_date:
                    return "Missing date range for web logs query"
                # Use the same endpoint as the Python debugging code
                query_url = f"https://app.botify.com/api/v1/logs/{username}/{project_name}/urls/{start_date}/{end_date}"
                # Add pagination parameters to URL (same as Python debugging code)
                query_url_with_params = f"{query_url}?page=1&size=1&sampling=100"
                # Extract the query body for POST request (same as Python debugging code)
                query_body = query_payload.get('query_body', {})
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(query_url_with_params, headers=headers, json=query_body)
            else:
                # For BQLv2 (crawl, GSC), use the standard query endpoint
                query_url = f"https://api.botify.com/v1/projects/{username}/{project_name}/query?size=1"
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(query_url, headers=headers, json=query_payload)
            # Process the response
            if response.status_code >= 400:
                try:
                    error_body = response.json()
                    if 'error' in error_body:
                        error_info = error_body['error']
                        if isinstance(error_info, dict):
                            error_code = error_info.get('error_code', 'Unknown')
                            error_message = error_info.get('message', 'Unknown error')
                            return f"Error {error_code}: {error_message}"
                        else:
                            return str(error_info)
                    else:
                        return json.dumps(error_body, indent=2)
                except Exception:
                    return f"HTTP {response.status_code}: {response.text[:200]}"
            else:
                # Query endpoint worked, so the issue might be with the /jobs endpoint specifically
                return "Query endpoint works fine - issue may be with /jobs endpoint or export processing"
        except Exception as e:
            return f"Diagnosis failed: {str(e)}"

    def _create_action_buttons(self, step_data, step_id):
        """Create View Folder and Download CSV buttons for a step."""
        from urllib.parse import quote
        # Extract analysis-specific folder information
        username = step_data.get('username', '')
        project_name = step_data.get('project_name', '') or step_data.get('project', '')
        analysis_slug = step_data.get('analysis_slug', '')
        # Construct the specific analysis folder path
        if username and project_name and analysis_slug:
            analysis_folder = Path.cwd() / 'downloads' / self.APP_NAME / username / project_name / analysis_slug
            folder_path = str(analysis_folder.resolve())
            folder_title = f"Open analysis folder: {username}/{project_name}/{analysis_slug}"
        else:
            # Fallback to general trifecta folder if analysis info is missing
            analysis_folder = Path.cwd() / 'downloads' / self.APP_NAME
            folder_path = str(analysis_folder.resolve())
            folder_title = f"Open folder: {analysis_folder.resolve()}"
        # Always create the View Folder button
        folder_button = A(
            self.ui['BUTTON_LABELS']['VIEW_FOLDER'],
            href="#",
            hx_get=f"/open-folder?path={quote(folder_path)}",
            hx_swap="none",
            title=folder_title,
            role="button",
            cls=self.ui['BUTTON_STYLES']['STANDARD']
        )
        buttons = [folder_button]
        # Create download button if file exists
        download_complete = step_data.get('download_complete', False)
        # Determine the expected filename based on step and export type
        expected_filename = None
        if step_id == 'step_02':
            # For crawl data, determine filename based on active template's export type
            active_crawl_template_key = self.get_configured_template('crawl')
            active_template_details = self.QUERY_TEMPLATES.get(active_crawl_template_key, {})
            export_type = active_template_details.get('export_type', 'crawl_attributes')
            # Use the same mapping as get_deterministic_filepath
            filename_mapping = {
                'crawl_attributes': 'crawl.csv',
                'link_graph_edges': 'link_graph.csv'
            }
            expected_filename = filename_mapping.get(export_type, 'crawl.csv')
        elif step_id == 'step_03':
            expected_filename = 'weblog.csv'
        elif step_id == 'step_04':
            expected_filename = 'gsc.csv'
        # Check if download was successful and try to find the file
        if download_complete and expected_filename and username and project_name and analysis_slug:
            try:
                # Construct the expected file path
                expected_file_path = Path.cwd() / 'downloads' / self.APP_NAME / username / project_name / analysis_slug / expected_filename
                # Check if file actually exists
                if expected_file_path.exists():
                    downloads_base = Path.cwd() / 'downloads'
                    path_for_url = expected_file_path.relative_to(downloads_base)
                    path_for_url = str(path_for_url).replace('\\', '/')
                    # Check if this is a link graph file for Cosmograph visualization
                    is_link_graph = expected_filename.startswith('link_graph')
                    # Always create the download button first
                    download_button = A(
                        self.ui['BUTTON_LABELS']['DOWNLOAD_CSV'],
                        href=f"/download_file?file={quote(path_for_url)}",
                        target="_blank",
                        role="button",
                        cls=self.ui['BUTTON_STYLES']['STANDARD']
                    )
                    buttons.append(download_button)
                    # For link graph files, also add the Cosmograph visualization button
                    if is_link_graph:
                        from datetime import datetime
                        # Create Cosmograph visualization link using the same pattern as botifython.py
                        # Important: URL-encode the entire data URL to prevent query parameter conflicts
                        file_url = f"/download_file?file={quote(path_for_url)}"
                        timestamp = int(datetime.now().timestamp())
                        data_url = f"http://localhost:5001{file_url}&t={timestamp}"
                        encoded_data_url = quote(data_url, safe='')
                        viz_url = f"https://cosmograph.app/run/?data={encoded_data_url}&link-spring=.1"
                        viz_button = A(
                            self.ui['BUTTON_LABELS']['VISUALIZE_GRAPH'],
                            href=viz_url,
                            target="_blank",
                            role="button",
                            cls=self.ui['BUTTON_STYLES']['STANDARD']
                        )
                        buttons.append(viz_button)
                else:
                    logger.debug(f"Expected file not found: {expected_file_path}")
            except Exception as e:
                logger.error(f"Error creating download button for {step_id}: {e}")
        # Fallback: check the old way for backward compatibility
        elif download_complete:
            file_path = None
            download_info = step_data.get('download_info', {})
            if download_info.get('has_file'):
                file_path = download_info.get('file_path', '')
            if file_path:
                try:
                    file_path_obj = Path(file_path)
                    if file_path_obj.exists():
                        downloads_base = Path.cwd() / 'downloads'
                        path_for_url = file_path_obj.relative_to(downloads_base)
                        path_for_url = str(path_for_url).replace('\\', '/')
                        # Check if this is a link graph file for Cosmograph visualization
                        is_link_graph = file_path_obj.name.startswith('link_graph')
                        # Always create the download button first
                        download_button = A(
                            self.ui['BUTTON_LABELS']['DOWNLOAD_CSV'],
                            href=f"/download_file?file={quote(path_for_url)}",
                            target="_blank",
                            role="button",
                            cls=self.ui['BUTTON_STYLES']['STANDARD']
                        )
                        buttons.append(download_button)
                        # For link graph files, also add the Cosmograph visualization button
                        if is_link_graph:
                            from datetime import datetime
                            # Create Cosmograph visualization link using the same pattern as botifython.py
                            file_url = f"/download_file?file={quote(path_for_url)}"
                            timestamp = int(datetime.now().timestamp())
                            data_url = f"http://localhost:5001{file_url}&t={timestamp}"
                            encoded_data_url = quote(data_url, safe='')
                            viz_url = f"https://cosmograph.app/run/?data={encoded_data_url}&link-spring=.1"
                            viz_button = A(
                                self.ui['BUTTON_LABELS']['VISUALIZE_GRAPH'],
                                href=viz_url,
                                target="_blank",
                                role="button",
                                cls=self.ui['BUTTON_STYLES']['STANDARD']
                            )
                            buttons.append(viz_button)
                except Exception as e:
                    logger.error(f"Error creating fallback download button for {step_id}: {e}")
        return buttons

    async def analyze_parameters(self, username, project_name, analysis_slug):
        """Counts URL parameters from crawl, GSC, and web logs data.

        Args:
            username: Organization username
            project_name: Project name
            analysis_slug: Analysis slug

        Returns:
            Dictionary containing analysis results and cache data
        """
        base_dir = await self.get_deterministic_filepath(username, project_name, analysis_slug)
        data_dir = Path(base_dir)
        cache_filename = '_param_scores_cache.pkl'
        logging.info('Attempting to load scores from cache...')
        cached_scores_data = self.load_parameter_scores_from_cache(data_dir, cache_filename)
        if cached_scores_data is None:
            logging.info('Cache not found or invalid, calculating scores from source files...')
            scores_data = await self.calculate_and_cache_parameter_scores(data_directory_path=data_dir, cache_filename=cache_filename)
            if scores_data is None:
                raise ValueError('Failed to calculate scores from source files')
        else:
            logging.info('Using cached scores data')
            scores_data = cached_scores_data
        return scores_data

    def load_csv_with_optional_skip(self, file_path):
        """Loads a CSV file, handles 'sep=', errors gracefully."""
        critical_columns = ['Full URL', 'URL']
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline()
            skip_rows = 1 if first_line.startswith('sep=') else 0
            df = pd.read_csv(file_path, skiprows=skip_rows, on_bad_lines='warn', low_memory=False)
            if not any((col in df.columns for col in critical_columns)):
                logging.warning(f"File {Path(file_path).name} loaded, but missing expected URL column ('Full URL' or 'URL').")
                return pd.DataFrame({'URL': []})
            return df
        except Exception as e:
            logging.error(f'Error loading CSV {Path(file_path).name}: {e}')
            return pd.DataFrame({'URL': []})

    def extract_query_params(self, url):
        """Extracts query parameter keys from a URL string."""
        if not isinstance(url, str):
            return []
        try:
            if url.startswith('//'):
                url = 'http:' + url
            parsed = urlparse(url)
            if not parsed.query:
                return []
            params_dict = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=False, errors='ignore')
            return list(params_dict.keys())
        except ValueError:
            return []

    def count_query_params(self, df, col_name_priority=['Full URL', 'URL']):
        """Counts query parameters from the first valid URL column found in a DataFrame."""
        counter = Counter()
        url_col = next((col for col in col_name_priority if col in df.columns), None)
        if url_col is None:
            return counter
        url_series = df[url_col].astype(str).dropna()
        for url in url_series:
            counter.update(self.extract_query_params(url))
        return counter

    def create_prism_widget(self, code, widget_id, language='javascript'):
        """Create a Prism.js syntax highlighting widget with copy functionality."""
        textarea_id = f'{widget_id}_raw_code'
        container = Div(Div(H5('Copy/Paste into PageWorkers:'), Textarea(code, id=textarea_id, style='display: none;'), NotStr('\n                <style>\n                    /* Remove padding from pre > code */\n                    #' + widget_id + ' pre > code {\n                        padding: 0 !important;\n                    }\n                </style>\n                '), Pre(Code(code, cls=f'language-{language}'), cls='line-numbers'), cls='mt-4'), id=widget_id)
        init_script = Script(f"\n            (function() {{\n                console.log('Prism widget loaded, ID: {widget_id}');\n                // Check if Prism is loaded\n                if (typeof Prism === 'undefined') {{\n                    console.error('Prism library not found');\n                    return;\n                }}\n                \n                // Attempt to manually trigger highlighting\n                setTimeout(function() {{\n                    try {{\n                        console.log('Manually triggering Prism highlighting for {widget_id}');\n                        Prism.highlightAllUnder(document.getElementById('{widget_id}'));\n                    }} catch(e) {{\n                        console.error('Error during manual Prism highlighting:', e);\n                    }}\n                }}, 300);\n            }})();\n            ", type='text/javascript')
        return Div(container, init_script)

    def create_marked_widget(self, markdown_content, widget_id):
        """Create a Marked.js markdown rendering widget with special tag handling."""
        processed_content = markdown_content
        processed_content = processed_content.replace('[[DETAILS_START]]', '<details>')
        processed_content = processed_content.replace('[[DETAILS_END]]', '</details>')
        processed_content = processed_content.replace('[[SUMMARY_START]]', '<summary>')
        processed_content = processed_content.replace('[[SUMMARY_END]]', '</summary>')
        textarea_id = f'{widget_id}_content'
        return Div(Textarea(processed_content, id=textarea_id, cls='hidden'), Div(id=f'{widget_id}_output', cls='markdown-body', style='padding: 15px; background-color: var(--pico-card-background-color); border-radius: var(--pico-border-radius);'), Script(f"\n            (function() {{\n                function renderMarkdown() {{\n                    if (typeof marked === 'undefined') {{\n                        console.error('Marked.js library not loaded');\n                        return;\n                    }}\n                    \n                    const textarea = document.getElementById('{textarea_id}');\n                    const output = document.getElementById('{widget_id}_output');\n                    \n                    if (textarea && output) {{\n                        // Configure marked options if needed\n                        marked.setOptions({{\n                            breaks: true,\n                            gfm: true,\n                            headerIds: true\n                        }});\n                        \n                        // Render the markdown content\n                        const rawMarkdown = textarea.value;\n                        output.innerHTML = marked.parse(rawMarkdown);\n                        \n                        console.log('Markdown rendered for {widget_id}');\n                    }} else {{\n                        console.error('Markdown elements not found for {widget_id}');\n                    }}\n                }}\n                \n                // Try to render immediately\n                renderMarkdown();\n                \n                // Also listen for initialization event\n                document.body.addEventListener('initialize-marked', function(e) {{\n                    if (e.detail && e.detail.targetId === '{widget_id}') {{\n                        console.log('Markdown initialization event received for {widget_id}');\n                        renderMarkdown();\n                    }}\n                }});\n            }})();\n            "), id=widget_id)

    def load_raw_counters_from_cache(self, data_directory_path, cache_filename='_raw_param_counters_cache.pkl'):
        """Loads raw counters data from a cache file."""
        data_dir = Path(data_directory_path)
        cache_file_path = data_dir / cache_filename
        if not cache_file_path.is_file():
            self.pipulate.append_to_history(f'[CACHE] No parameter counter cache found at {cache_file_path}')
            return None
        try:
            with open(cache_file_path, 'rb') as f:
                counters_data = pickle.load(f)
            if isinstance(counters_data, dict) and 'raw_counters' in counters_data and isinstance(counters_data['raw_counters'], dict) and ('metadata' in counters_data) and isinstance(counters_data['metadata'], dict) and (counters_data['metadata'].get('cache_version', 0) >= 2.0):
                self.pipulate.append_to_history(f"[CACHE] Loaded parameter counters from cache: {len(counters_data['raw_counters'])} sources")
                return counters_data
            else:
                logging.error(f'Invalid or outdated cache file format in {cache_file_path}.')
                return None
        except (pickle.UnpicklingError, EOFError) as e:
            logging.error(f'Error loading cache file (it might be corrupted): {cache_file_path} - {e}')
            return None
        except Exception as e:
            logging.error(f'An unexpected error occurred loading the cache: {cache_file_path} - {e}')
            return None

    async def calculate_and_cache_raw_counters(self, data_directory_path, input_files_config, cache_filename='_raw_param_counters_cache.pkl'):
        """
        Loads specified CSV files, performs a raw count of query parameters for each,
        and saves the counters to a cache file. Returns the counters and metadata.
        """
        data_dir = Path(data_directory_path)
        if not data_dir.is_dir():
            logging.error(f'Provided data directory path is not valid: {data_directory_path}')
            return None
        raw_counters = {}
        file_statuses = {}
        url_column_priority = ['Full URL', 'URL']
        logging.info(f'Processing data from directory: {data_dir}')
        for key, filename in input_files_config.items():
            file_path = data_dir / filename
            logging.info(f"Processing file: {filename} (as '{key}')")
            if not file_path.is_file():
                logging.warning(f'File not found: {file_path}')
                raw_counters[key] = Counter()
                file_statuses[key] = 'File not found'
                continue
            try:
                df = self.load_csv_with_optional_skip(str(file_path))
                if df.empty or not any((col in df.columns for col in url_column_priority)):
                    logging.warning(f'No usable URL column in {filename}')
                    raw_counters[key] = Counter()
                    file_statuses[key] = 'No URL column'
                    continue
                logging.info(f'Counting parameters in {filename}...')
                file_counter = self.count_query_params(df, url_column_priority)
                raw_counters[key] = file_counter
                file_statuses[key] = f'Processed ({len(file_counter):,} unique params found)'
                logging.info(f'Counted {len(file_counter):,} unique parameters in {filename}')
            except Exception as e:
                logging.exception(f'Error processing {filename}: {e}')
                raw_counters[key] = Counter()
                file_statuses[key] = f'Error: {str(e)}'
        counters_data = {'raw_counters': raw_counters, 'metadata': {'data_directory_path': str(data_dir.resolve()), 'input_files_config': input_files_config, 'file_statuses': file_statuses, 'cache_timestamp': time.time(), 'cache_version': 2.0}}
        cache_file_path = data_dir / cache_filename
        logging.info(f'Saving raw counters to cache file: {cache_file_path}')
        try:
            os.makedirs(os.path.dirname(cache_file_path), exist_ok=True)
            with open(cache_file_path, 'wb') as f:
                pickle.dump(counters_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            logging.info('Cache saved successfully.')
        except Exception as e:
            logging.error(f'Error saving cache file: {e}')
        return counters_data

    def create_parameter_visualization_placeholder(self, summary_data_str=None):
        """
        Create a visualization of parameters from all three data sources.
        """
        TOP_PARAMS_COUNT = 40
        import base64
        import json
        import logging
        import os
        from collections import Counter
        from io import BytesIO, StringIO
        from pathlib import Path

        import matplotlib.pyplot as plt
        import numpy as np
        self.pipulate.append_to_history('[VISUALIZATION] Creating parameter distribution visualization')
        debug_info = []

        def add_debug(msg):
            debug_info.append(msg)
            logging.info(msg)
        try:
            add_debug('Starting parameter visualization')
            has_data = False
            total_params = 0
            data_sources = []
            source_counters = {'weblogs': Counter(), 'gsc': Counter(), 'not_indexable': Counter()}
            if summary_data_str:
                summary_data = json.loads(summary_data_str)
                total_params = summary_data.get('total_unique_parameters', 0)
                data_sources = list(summary_data.get('data_sources', {}).keys())
                TOP_PARAMS_COUNT = summary_data.get('param_count', 40)
                has_data = True
                add_debug(f'Data sources in summary: {data_sources}')
                cache_path = summary_data.get('cache_path')
                add_debug(f'Cache path: {cache_path}, exists: {(os.path.exists(cache_path) if cache_path else False)}')
                if cache_path and os.path.exists(cache_path):
                    try:
                        with open(cache_path, 'rb') as f:
                            cache_data = pickle.load(f)
                        raw_counters = cache_data.get('raw_counters', {})
                        add_debug(f'Raw counter keys in cache: {list(raw_counters.keys())}')
                        for key, counter in raw_counters.items():
                            top_items = list(counter.most_common(5))
                            add_debug(f"Raw counter '{key}' has {len(counter)} items. Top 5: {top_items}")
                        source_mapping = {'weblogs': ['weblogs', 'weblog', 'logs', 'log'], 'gsc': ['gsc', 'search_console', 'searchconsole', 'google'], 'not_indexable': ['not_indexable', 'crawl', 'non_indexable', 'nonindexable']}
                        for source, possible_keys in source_mapping.items():
                            found = False
                            for key in possible_keys:
                                if key in raw_counters:
                                    source_counters[source] = raw_counters[key]
                                    add_debug(f"Mapped source '{source}' to cache key '{key}' with {len(raw_counters[key])} items")
                                    found = True
                                    break
                            if not found:
                                add_debug(f"No matching key found for source '{source}'")
                    except Exception as e:
                        add_debug(f'Error loading parameter data from cache: {e}')
                        add_debug(f'Cache file not found or invalid')
                    if all((len(counter) == 0 for counter in source_counters.values())) and has_data:
                        add_debug('No counter data from cache, using summary data directly')
                        for source, counter in source_counters.items():
                            matching_source = None
                            if source == 'weblogs':
                                matching_source = next((s for s in data_sources if 'log' in s.lower()), None)
                            elif source == 'gsc':
                                matching_source = next((s for s in data_sources if 'gsc' in s.lower() or 'search' in s.lower()), None)
                            elif source == 'not_indexable':
                                matching_source = next((s for s in data_sources if 'crawl' in s.lower() or 'index' in s.lower() or 'not_' in s.lower()), None)
                            if matching_source:
                                add_debug(f"Found matching source '{matching_source}' for '{source}'")
                                source_data = summary_data.get('data_sources', {}).get(matching_source, {})
                                for param_data in source_data.get('top_parameters', []):
                                    counter[param_data['name']] = param_data['count']
                            else:
                                add_debug(f"No matching source found for '{source}'")
            for source, counter in source_counters.items():
                top_items = counter.most_common(5)
                items_count = len(counter)
                total_count = sum(counter.values())
                add_debug(f"FINAL: Source '{source}' has {items_count} items with {total_count} total occurrences")
                if top_items:
                    add_debug(f'  Top 5 for {source}: {top_items}')
            all_params = set()
            for counter in source_counters.values():
                all_params.update(counter.keys())
            cache_data = {'raw_counters': source_counters, 'metadata': {'cache_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'file_statuses': {}}}
            results = []
            for param in all_params:
                wb_count = source_counters['weblogs'].get(param, 0)
                ni_count = source_counters['not_indexable'].get(param, 0)
                gsc_count = source_counters['gsc'].get(param, 0)
                total_count = wb_count + ni_count
                score = total_count / (gsc_count + 1)
                results.append((param, wb_count, ni_count, gsc_count, total_count, score))
            results_sorted = sorted(results, key=lambda x: x[5], reverse=True)
            top_params = [param for param, _, _, _, _, _ in results_sorted[:TOP_PARAMS_COUNT]]
            top_params.reverse()
            table_html = '\n            <style>\n                /* Column-specific colors that override the base rich table styles */\n                .weblogs-val { color: #4fa8ff !important; text-align: right; }\n                .not-index-val { color: #ff0000 !important; text-align: right; }\n                .gsc-val { color: #50fa7b !important; text-align: right; }\n                .score-val { color: #ffff00 !important; text-align: right; font-weight: bold; }\n                .na-val { color: #666666 !important; text-align: right; font-style: italic; }\n            </style>\n            <table class="param-table">\n                <caption>Displaying ' + str(TOP_PARAMS_COUNT) + ' Parameters with Scoring (to help identify optimization targets)</caption>\n                <tr class="header">\n                    <td class="header-cell"><span class="param-name">Parameter</span></td>\n                    <td class="header-cell"><span class="weblogs-val">Weblogs</span></td>\n                    <td class="header-cell"><span class="not-index-val">Not-Indexable</span></td>\n                    <td class="header-cell"><span class="gsc-val">GSC</span></td>\n                    <td class="header-cell"><span class="total-val">Total</span></td>\n                    <td class="header-cell"><span class="score-val">Score</span></td>\n                </tr>\n            '
            for param, wb, ni, gsc, total, score in results_sorted[:TOP_PARAMS_COUNT]:
                wb_display = f'{wb:,}' if wb is not None else '<span class="na-val">N/A</span>'
                ni_display = f'{ni:,}' if ni is not None else '<span class="na-val">N/A</span>'
                gsc_display = f'{gsc:,}' if gsc is not None else '<span class="na-val">N/A</span>'
                total_display = f'{total:,}' if total is not None else '<span class="na-val">N/A</span>'
                score_display = f'{score:,.0f}' if score is not None else '<span class="na-val">N/A</span>'
                table_html += f'\n                <tr>\n                    <td><span class="param-name">{param}</span></td>\n                    <td><span class="weblogs-val">{wb_display}</span></td>\n                    <td><span class="not-index-val">{ni_display}</span></td>\n                    <td><span class="gsc-val">{gsc_display}</span></td>\n                    <td><span class="total-val">{total_display}</span></td>\n                    <td><span class="score-val">{score_display}</span></td>\n                </tr>\n                '
            table_html += '</table>'
            figure_height = max(15, min(TOP_PARAMS_COUNT * 0.65, 50))
            add_debug(f'Chart parameters: count={TOP_PARAMS_COUNT}, final_height={figure_height}')
            plt.figure(figsize=(10, figure_height), facecolor='#13171f', constrained_layout=False)
            ax = plt.axes([0.25, 0.02, 0.7, 0.95])
            ax.set_facecolor('#13171f')
            for spine in ax.spines.values():
                spine.set_color('white')
            ax.spines['right'].set_visible(False)
            ax.spines['top'].set_visible(False)
            y_pos = np.arange(len(top_params))
            width = 0.25
            weblogs_values = [source_counters['weblogs'].get(param, 0) for param in top_params]
            crawl_values = [source_counters['not_indexable'].get(param, 0) for param in top_params]
            gsc_values = [source_counters['gsc'].get(param, 0) for param in top_params]
            max_value = max([max(weblogs_values or [0]), max(crawl_values or [0]), max(gsc_values or [0])])
            add_debug(f'Max value in data: {max_value}')
            ax.set_xscale('symlog')
            weblog_bars = ax.barh([p + width for p in y_pos], weblogs_values, width, color='#4fa8ff', label='Web Logs', alpha=0.9)
            crawl_bars = ax.barh(y_pos, crawl_values, width, color='#ff0000', label='Crawl Data', alpha=0.9)
            gsc_bars = ax.barh([p - width for p in y_pos], gsc_values, width, color='#50fa7b', label='Search Console', alpha=0.9)
            for bars in [weblog_bars, crawl_bars, gsc_bars]:
                for bar in bars:
                    if bar.get_width() == 0:
                        bar.set_hatch('/')
                        bar.set_alpha(0.3)
            ax.grid(axis='x', linestyle='--', alpha=0.2, color='white')
            truncated_params = []
            for param in top_params:
                if len(param) > 25:
                    truncated = param[:22] + '...'
                else:
                    truncated = param
                truncated_params.append(truncated)
            ax.set_yticks(y_pos)
            ax.set_yticklabels(truncated_params, fontsize=8, color='white')
            ax.set_xlabel('Occurrences (log scale)', color='white')
            ax.set_ylabel('Parameters', color='white')
            ax.set_title(f'Displaying {TOP_PARAMS_COUNT} Parameters with Log Scale (to show smaller values)', color='white')
            ax.tick_params(axis='both', colors='white')
            ax.legend(loc='lower right', facecolor='#2d2d3a', edgecolor='#555555', labelcolor='white')
            if max_value > 0:
                ax.set_xlim(0, max_value * 2)
            for i, (wb, cr, gs) in enumerate(zip(weblogs_values, crawl_values, gsc_values)):
                if wb > 0:
                    text_pos = wb * 1.05
                    ax.text(text_pos, i + width, f'{wb:,}', va='center', fontsize=7, color='#4fa8ff')
                else:
                    ax.text(0.01, i + width, '0', va='center', ha='left', fontsize=7, color='#4fa8ff', alpha=0.5)
                if cr > 0:
                    text_pos = cr * 1.05
                    ax.text(text_pos, i, f'{cr:,}', va='center', fontsize=7, color='#ff0000', weight='bold')
                else:
                    ax.text(0.01, i, '0', va='center', ha='left', fontsize=7, color='#ff0000', alpha=0.5)
                if gs > 0:
                    text_pos = gs * 1.05
                    ax.text(text_pos, i - width, f'{gs:,}', va='center', fontsize=7, color='#50fa7b')
                else:
                    ax.text(0.01, i - width, '0', va='center', ha='left', fontsize=7, color='#50fa7b', alpha=0.5)
            y_min, y_max = (-width * 1.5, len(y_pos) - 1 + width * 1.5)
            ax.set_ylim(y_min, y_max)
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=120)
            plt.close()
            img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
            file_status_html = '\n            <div style="margin: 15px 0; padding: 10px; background: #222; border-radius: 5px;">\n                <h5 style="margin-bottom: 10px; color: #ccc;">Data Source Status:</h5>\n                <table style="width: 100%; font-size: 0.9em;">\n            '
            source_display = {'weblogs': ('Web Logs', '#4fa8ff'), 'not_indexable': ('Not-Indexable', '#ff0000'), 'gsc': ('Search Console', '#50fa7b')}
            cache_metadata = cache_data.get('metadata', {}) if 'cache_data' in locals() else {}
            file_statuses = cache_metadata.get('file_statuses', {})
            for source, (display_name, color) in source_display.items():
                counter = source_counters.get(source, Counter())
                if len(counter) > 0:
                    status = f"Found ({cache_metadata.get('cache_timestamp', 'Unknown date')})"
                elif source in file_statuses:
                    status = file_statuses[source]
                else:
                    status = 'No Data Available'
                param_count = len(counter)
                total_occurrences = sum(counter.values())
                if param_count > 0:
                    status_color = '#50fa7b'
                elif source in file_statuses and 'error' in file_statuses[source].lower():
                    status_color = '#ff5555'
                else:
                    status_color = '#ff8c00'
                file_status_html += f'\n                    <tr>\n                        <td style="color: {color}; padding: 5px 0;">{display_name}:</td>\n                        <td style="color: {status_color}; text-align: right;">\n                            {param_count:,} parameters, {total_occurrences:,} occurrences\n                        </td>\n                        <td style="color: #888; text-align: right; font-style: italic;">\n                            ({status})\n                        </td>\n                    </tr>\n                '
            file_status_html += '\n                </table>\n            </div>\n            '
            debug_section = ''
            if debug_info:
                debug_section = Div(Details(Summary('Debug Information (click to expand)'), Pre('\n'.join(debug_info), style='background: #333; color: #eee; padding: 10px; border-radius: 5px; font-size: 0.8em; max-height: 300px; overflow-y: auto;'), cls='mt-4'))
            visualization = Div(Div(H4('Parameter Analysis Summary:'), P(f'Total unique parameters: {total_params:,}' if has_data else 'No data available yet'), P(f"Data sources: {', '.join(data_sources)}" if data_sources else 'No data sources processed yet'), NotStr(file_status_html), P('Note: The number of parameters shown below is controlled by the slider and only affects the visualization. It does not impact the underlying analysis. You can revert Step 5 and adjust it to up to 250.', style='font-size: 0.85em; color: #888; font-style: italic; margin-bottom: 15px;'), Div(H4('Understanding the Data Visualizations', style='color: #ccc; margin-bottom: 10px;'), P('The following two visualizations (bar chart and scoring matrix) are provided to help you understand the parameter distribution patterns across your data sources. While they offer valuable insights for SEO analysis and client discussions, they are supplementary tools only.', cls='mb-10px'), P('For optimization purposes, you can focus directly on the "Meaningful Min Frequency Values" table below to select your breakpoint, then proceed to create your optimization. The visualizations are here to help you make informed decisions and explain your strategy.', cls='mb-15px'), style='background: #222; padding: 15px; border-radius: 5px; margin-bottom: 20px;'), Div(NotStr(f'<img src="data:image/png;base64,{img_str}" style="width:100%; height:auto;" alt="Parameter Distribution Chart" />'), style='text-align: center; margin-top: 1rem;'), Div(H4('Understanding Your Data Sources', style='color: #ccc; margin-bottom: 10px;'), P('The table below shows parameter data from three critical sources:', cls='mb-10px'), Ul(Li(Span('Web Logs ', style='color: #4fa8ff; font-weight: bold;'), "(Blue): Shows Googlebot crawler behavior. High parameter counts here are natural as Google's crawler thoroughly explores your site structure.", style='margin-bottom: 8px;'), Li(Span('Not-Indexable ', style='color: #ff0000; font-weight: bold;'), "(Red): From Botify's crawl analysis, identifying URLs that cannot be indexed for various technical reasons. Parameters appearing here often indicate potential optimization opportunities.", style='margin-bottom: 8px;'), Li(Span('GSC ', style='color: #50fa7b; font-weight: bold;'), '(Green): URLs that have received any impressions in Google Search Console. Parameters appearing here are actively involved in your search presence and should be handled with caution. This is why we recommend keeping the GSC Threshold at 0.', style='margin-bottom: 8px;')), style='background: #222; padding: 15px; border-radius: 5px; margin: 20px 0;'), NotStr(table_html), debug_section, style='padding: 15px; background-color: var(--pico-card-background-color); border-radius: var(--pico-border-radius);'))
            return visualization
        except Exception as e:
            logging.exception(f'Error creating parameter visualization: {e}')
            error_msg = f'Error creating visualization: {str(e)}\n\nDebug info:\n' + '\n'.join(debug_info)
            return Div(NotStr(f"<div style='color: red; padding: 10px; background: #333; border-radius: 5px;'>{error_msg}</div>"), _raw=True)


