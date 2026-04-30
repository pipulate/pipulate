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

ROLES = ['Core']


class LinkGraphVisualizerV2:
    """
    Botify Trifecta Workflow - Base Template for Multi-Export Data Collection
    
    📚 Complete documentation: helpers/docs_sync/botify_workflow_patterns.md
    
    Downloads three types of Botify data (crawl analysis, web logs, Search Console)
    and generates Jupyter-friendly Python code for API debugging.
    
    🔧 Template Config: {} (base template)
    🏗️ Derivatives: 110_parameter_buster.py, 120_link_graph.py  
    🎯 WET Inheritance: Uses helpers/rebuild_trifecta_derivatives.sh for propagation
    """
    APP_NAME = 'link_graph_visualizer_v2'
    DISPLAY_NAME = 'Kung Fu Trifecta 🏇'
    ENDPOINT_MESSAGE = """Transform Botify data into an interactive link graph visualization powered by Cosmograph. Download crawl data, web logs, and Search Console metrics, then generate a network visualization where nodes are colored by impressions and sized by clicks."""
    TRAINING_PROMPT = """# Link Graph Visualizer Training Guide
The Link Graph Visualizer workflow transforms Botify data into an interactive network visualization using Cosmograph. This workflow demonstrates advanced data processing patterns, robust error handling, and metric-agnostic design that automatically preserves whatever metrics are present in the source data.
If asked, the secret word to show that you're trained on this workflow is ENTERPRISE."""

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
                'dimensions': [
                    '{collection}.url', 
                    '{collection}.http_code', 
                    '{collection}.metadata.title.content',
                    '{collection}.segments.pagetype.value',
                    '{collection}.compliant.is_compliant',
                    '{collection}.canonical.to.equal',
                    '{collection}.sitemaps.present'
                ],
                'metrics': [],
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
            'description': 'Exports internal link graph...',
            'export_type': 'link_graph_edges',
            'user_message': '...',
            'button_label_suffix': 'Link Graph',
            'query': {
                # Change {collection}.url to url and {collection}.outlinks... to outlinks...
                # Botify V2 queries often prefer the fields WITHOUT the collection prefix 
                # when the collection is already defined in the payload.
                'dimensions': ['url', 'outlinks_internal.graph.url'], 
                'metrics': [],
                'filters': {'field': 'depth', 'predicate': 'lte', 'value': '{OPTIMAL_DEPTH}'}
            },
            'qualifier_config': {
                'enabled': True,
                'qualifier_bql_template': {
                    "dimensions": ["url"], # Give it a dimension to count against
                    "metrics": [{"function": "count", "args": []}],
                    "filters": {"field": "depth", "predicate": "lte", "value": "{ITERATION_VALUE}"},
                    "limit": 1 # We only need one row to get the aggregate count
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
        },
    }


    # Template Configuration - Controls which templates are actually used
    # ===================================================================
    # Change these values to switch between different query templates
    # without modifying the workflow logic.
    TEMPLATE_CONFIG = {
        'analysis': 'Link Graph Edges',   # Options: 'Crawl Basic', 'Not Compliant', 'Link Graph Edges'
        'crawler': 'Crawl Basic',  # New basic crawl for node metadata
        'gsc': 'GSC Performance',      # Options: 'GSC Performance'
    }

    # Optional Features Configuration
    # ===============================
    # Controls optional UI features that can be enabled/disabled
    FEATURES_CONFIG = {
        'enable_skip_buttons': True,  # Set to False to disable skip buttons on steps 3 & 4
    }

    # Toggle Method Configuration - Maps step IDs to their specific data extraction logic
    TOGGLE_CONFIG = {
        'step_analysis': {
            'data_key': 'analysis_selection',
            'status_field': 'download_complete',
            'success_text': 'HAS crawl analysis',
            'failure_text': 'does NOT have crawl analysis',
            'error_prefix': 'FAILED to download crawl analysis',
            'status_prefix': 'Analysis '
        },
        'step_crawler': {
            'data_key': 'crawler_basic',
            'status_field': 'download_complete',
            'success_text': 'HAS basic crawl attributes',
            'failure_text': 'does NOT have basic crawl attributes',
            'error_prefix': 'FAILED to download basic crawl attributes',
            'status_prefix': 'Crawler '
        },
        'step_webogs': {
            'data_key': 'weblogs_check',
            'status_field': 'has_logs',
            'success_text': 'HAS web logs',
            'failure_text': 'does NOT have web logs',
            'error_prefix': 'FAILED to download web logs',
            'status_prefix': 'Project '
        },
        'step_gsc': {
            'data_key': 'search_console_check',
            'status_field': 'has_search_console',
            'success_text': 'HAS Search Console data',
            'failure_text': 'does NOT have Search Console data',
            'error_prefix': 'FAILED to download Search Console data',
            'status_prefix': 'Project '
        },

    }

    # --- START_CLASS_ATTRIBUTES_BUNDLE ---
    # Additional class-level constants can be merged here by manage_class_attributes.py
    # --- END_CLASS_ATTRIBUTES_BUNDLE ---

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
        # HYBRID APPROACH: Dynamic steps with static fallback for helper script compatibility
        # The workflow uses dynamic steps by default, but can fall back to static when needed
        use_static_steps = False  # Set to True to enable static mode for helper scripts
        
        if use_static_steps:
            # Static steps list for splice_workflow_step.py compatibility
            static_steps = [
                Step(id='step_project', done='botify_project', show='Botify Project URL', refill=True),
                Step(id='step_analysis', done='analysis_selection', show='Download Crawl Analysis', refill=False),
                Step(id='step_crawler', done='crawler_basic', show='Download Crawl Basic', refill=False),
                Step(id='step_webogs', done='webogs', show='Download Web Logs', refill=False),
                Step(id='step_gsc', done='gsc', show='Download Search Console', refill=False),
                Step(
                    id='step_01',
                    done='placeholder_01',
                    show='Placeholder Step 1 (Edit Me)',
                    refill=False,
                ),
                # --- STEPS_LIST_INSERTION_POINT ---
                Step(id='finalize', done='finalized', show='Finalize Workflow', refill=False)
            ]
            self.steps = static_steps
        else:
            # Build steps dynamically based on template configuration (default)
            self.steps = self._build_dynamic_steps()
        
        self.steps_indices = {step.id: i for i, step in enumerate(self.steps)}
        
        # Register routes using centralized helper
        pipulate.register_workflow_routes(self)
        
        # Register custom routes specific to this workflow
        app.route(f'/{app_name}/step_analysis_process', methods=['POST'])(self.step_analysis_process)
        app.route(f'/{app_name}/step_webogs_process', methods=['POST'])(self.step_webogs_process)
        app.route(f'/{app_name}/step_webogs_complete', methods=['POST'])(self.step_webogs_complete)
        app.route(f'/{app_name}/step_crawler_complete', methods=['POST'])(self.step_crawler_complete)
        app.route(f'/{app_name}/step_gsc_complete', methods=['POST'])(self.step_gsc_complete)

        # Register Transplant Bundle Routes
        app.route(f'/{app_name}/step_02b_submit', methods=['POST'])(self.step_02b_submit)
        app.route(f'/{app_name}/step_02b_process', methods=['POST'])(self.step_02b_process)
        app.route(f'/{app_name}/step_05_submit', methods=['POST'])(self.step_05_submit)
        app.route(f'/{app_name}/step_05_process', methods=['POST'])(self.step_05_process)
        app.route("/open-folder", methods=['GET'])(self.pipulate.open_folder)

        app.route(f'/{app_name}/update_button_text', methods=['POST'])(self.update_button_text)
        app.route(f'/{app_name}/toggle', methods=['GET'])(self.common_toggle)
        
        # Field Discovery Endpoint - Foundation for BQL template validation
        app.route(f'/{app_name}/discover-fields/{{username}}/{{project}}/{{analysis}}', methods=['GET'])(self.discover_fields_endpoint)

        self.step_messages = {'finalize': {'ready': self.ui['MESSAGES']['ALL_STEPS_COMPLETE'], 'complete': f'Workflow finalized. Use {self.ui["BUTTON_LABELS"]["UNLOCK"]} to make changes.'}, 'step_analysis': {'input': f"❔{wand.fmt('step_analysis')}: Please select a crawl analysis for this project.", 'complete': '📊 Crawl analysis download complete. Continue to next step.'}}
        for step in self.steps:
            if step.id not in self.step_messages:
                self.step_messages[step.id] = {'input': f'❔{wand.fmt(step.id)}: Please complete {step.show}.', 'complete': f'✳️ {step.show} complete. Continue to next step.'}
        self.step_messages['step_gsc'] = {'input': f"❔{wand.fmt('step_gsc')}: Please check if the project has Search Console data.", 'complete': 'Search Console check complete. Continue to next step.'}

        self.step_messages['step_crawler'] = {'input': f"❔{wand.fmt('step_crawler')}: Please download basic crawl attributes for node metadata.", 'complete': '📊 Basic crawl data download complete. Continue to next step.'}
        self.step_messages['step_webogs'] = {'input': f"❔{wand.fmt('step_webogs')}: Please check if the project has web logs available.", 'complete': '📋 Web logs check complete. Continue to next step.'}

        # Bridge the gap between Core expectations and App reality
        self.pipulate.format_size = self.format_size


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
    
    def _should_include_crawler_step(self, analysis_template):
        """Determine if crawler step should be included based on analysis template.
        
        Args:
            analysis_template: The template name for the analysis step
            
        Returns:
            bool: True if crawler step should be included, False otherwise
        """
        # Include crawler step only for Link Graph Edges (needs node enrichment)
        return analysis_template == 'Link Graph Edges'

    def _build_dynamic_steps(self):
        """Build the steps list dynamically, slotting in Link Graph customizations."""
        analysis_template = self.get_configured_template('analysis')
        gsc_template = self.get_configured_template('gsc')

        # 1. Start with the project input
        steps = [Step(id='step_project', done='botify_project', show='Botify Project URL', refill=True)]
        
        # 2. Add the Analysis selection
        steps.append(Step(id='step_analysis', done='analysis_selection', show=f'Download: {analysis_template}', refill=False))

        # 3. TRANSPLANT SLOT: Node Attributes (Old 02b)
        # We always want this for Link Graph to color the nodes
        steps.append(Step(id='step_02b', done='node_attributes', show='Download: Node Attributes', refill=False))

        # 4. Optional Trifecta Crawler (Keep it if the template allows)
        if self._should_include_crawler_step(analysis_template):
             steps.append(Step(id='step_crawler', done='crawler_basic', show='Download: Basic Crawl', refill=False))
        
        # 5. The standard Trifecta logs and GSC
        steps.append(Step(id='step_webogs', done='webogs', show='Download Web Logs (Optional)', refill=False))
        steps.append(Step(id='step_gsc', done='gsc', show=f'Download: {gsc_template}', refill=False))

        # 6. TRANSPLANT SLOT: The Visualization Engine (Old 05)
        steps.append(Step(id='step_05', done='visualization_ready', show='Prepare & Visualize Graph', refill=True))

        # 7. Finalize
        steps.append(Step(id='finalize', done='finalized', show='Finalize', refill=False))
        
        return steps
    
    def get_export_type_for_template_config(self, template_config_key):
        """Get the export type for a given template configuration key.
        
        This method resolves the template configuration to the actual export type
        that should be used for file naming and caching.
        
        Args:
            template_config_key: Key from TEMPLATE_CONFIG (e.g., 'analysis', 'crawler')
            
        Returns:
            String export type that can be used with get_filename_for_export_type()
        """
        template_name = self.get_configured_template(template_config_key)
        if not template_name:
            raise ValueError(f'No template configured for: {template_config_key}')
            
        template_details = self.QUERY_TEMPLATES.get(template_name, {})
        export_type = template_details.get('export_type')
        
        if not export_type:
            raise ValueError(f'Template "{template_name}" has no export_type defined')
            
        return export_type

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
                return Card(H3(self.ui['MESSAGES']['WORKFLOW_LOCKED']), Form(Button(self.ui['BUTTON_LABELS']['UNLOCK'], type='submit', cls=self.ui['BUTTON_STYLES']['OUTLINE'], id='trifecta-unlock-button', aria_label='Unlock workflow to make changes', data_testid='trifecta-unlock-button'), hx_post=f'/{app_name}/unfinalize', hx_target=f'#{app_name}-container'), id=finalize_step.id)
            else:
                all_steps_complete = all((wand.get_step_data(pipeline_id, step.id, {}).get(step.done) for step in steps[:-1]))
                if all_steps_complete:
                    await self.message_queue.add(wand, 'All steps are complete. You can now finalize the workflow or revert to any step to make changes.', verbatim=True)
                    return Card(H3(self.ui['MESSAGES']['FINALIZE_QUESTION']), P(self.ui['MESSAGES']['FINALIZE_HELP'], cls='text-secondary'), Form(Button(self.ui['BUTTON_LABELS']['FINALIZE'], type='submit', cls=self.ui['BUTTON_STYLES']['PRIMARY'], id='trifecta-finalize-button', aria_label='Finalize workflow and lock all steps', data_testid='trifecta-finalize-button'), hx_post=f'/{app_name}/finalize', hx_target=f'#{app_name}-container'), id=finalize_step.id)
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

    async def step_project(self, request):
        """Handles GET request for Botify URL input widget.

        # STEP PATTERN: GET handler returns current step UI + empty placeholder for next step
        # Important: The next step div should NOT have hx_trigger here, only in the submit handler
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_project'
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
            return Div(Card(H3(f'🔒 {step.show}'), Div(P(f"Project: {project_data.get('project_name', '')}"), Small(project_url, cls='url-breakable'), cls='custom-card-padding-bg')), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        elif project_data and state.get('_revert_target') != step_id:
            project_name = project_data.get('project_name', '')
            username = project_data.get('username', '')
            project_info = Div(H4(f'Project: {project_name}'), P(f'Username: {username}'), Small(project_url, cls='url-breakable'), cls='project-info-box')
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
                            cls='w-full',
                            id='trifecta-botify-url-input',
                            aria_label='Enter Botify project URL',
                            data_testid='trifecta-botify-url-input'
                        ),
                        Div(
                            Button('Use this URL ▸', type='submit', cls='primary',
                                   id='trifecta-url-submit-button',
                                   aria_label='Submit Botify project URL',
                                   data_testid='trifecta-url-submit-button'),
                            cls='mt-vh text-end'
                        ),
                        hx_post=f'/{app_name}/{step_id}_submit',
                        hx_target=f'#{step_id}'
                    )
                ),
                Div(id=next_step_id),
                id=step_id
            )

    async def step_project_submit(self, request):
        """Process the submission for Botify URL input widget.

        # STEP PATTERN: Submit handler stores state and returns:
        # 1. Revert control for the completed step
        # 2. Next step div with explicit hx_trigger="load" to chain reaction to next step
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_project'
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
        
        # NEW: Save analyses data as soon as we have a valid project URL
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')
        
        # Get API token and save analyses data
        api_token = self.read_api_token()
        if api_token:
            try:
                await self.message_queue.add(wand, "🔍 Fetching analyses data...", verbatim=True)
                success, save_message, filepath = await self.save_analyses_to_json(username, project_name, api_token)
                await self.message_queue.add(wand, save_message, verbatim=True)
                
                if success and filepath:
                    # Log the API call for debugging purposes
                    url = f'https://api.botify.com/v1/analyses/{username}/{project_name}/light'
                    headers = {'Authorization': f'Token {api_token}', 'Content-Type': 'application/json'}
                    curl_cmd, python_cmd = self._generate_api_call_representations(
                        method="GET", url=url, headers=headers, 
                        step_context="Step 1: Save Analyses Data",
                        username=username, project_name=project_name
                    )
                    # Get the response data for radical transparency
                    with open(filepath, 'r', encoding='utf-8') as f:
                        saved_data = json.load(f)
                    
                    await wand.log_api_call_details(
                        pipeline_id=pipeline_id, step_id=step_id,
                        call_description="Fetch and Save Analyses Data",
                        http_method="GET", url=url, headers=headers,
                        response_status=200,
                        response_preview=f"Analyses data saved to: {filepath}",
                        response_data=saved_data,  # Full response data for discovery transparency
                        curl_command=curl_cmd, python_command=python_cmd
                    )
                    
            except Exception as e:
                await self.message_queue.add(wand, f"⚠️ Could not save analyses data: {str(e)}", verbatim=True)
                logger.error(f'Error in analyses data saving: {e}')
        else:
            await self.message_queue.add(wand, "⚠️ No API token found - skipping analyses data save", verbatim=True)
        
        project_url = project_data.get('url', '')
        project_info = Div(H4(f'Project: {project_name}'), Small(project_url, cls='url-breakable'), cls='project-info-box')
        return wand.chain_reverter(step_id, step_index, steps, app_name, project_url)

    async def step_analysis(self, request):
        """Handles GET request for Analysis selection between steps 1 and 2."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_analysis'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        analysis_result_str = step_data.get(step.done, '')
        analysis_result = json.loads(analysis_result_str) if analysis_result_str else {}
        selected_slug = analysis_result.get('analysis_slug', '')
        prev_step_id = 'step_project'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('botify_project', '')
        if not prev_data_str:
            return P('Error: Project data not found. Please complete step 1 first.', cls='text-invalid')
        project_data = json.loads(prev_data_str)
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and selected_slug:
            return Div(Card(H3(f'🔒 {step.show}'), Div(P(f'Project: {project_name}', cls='mb-sm'), P(f'Selected Analysis: {selected_slug}', cls='font-bold'), cls='custom-card-padding-bg')), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
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
                    Pre(f'Selected analysis: {selected_slug}', cls='code-block-container hidden'),
                    id=f'{step_id}_widget'
                )
            )
            return Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: {selected_slug}', widget=widget, steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        try:
            api_token = self.read_api_token()
            if not api_token:
                return P('Error: Botify API token not found. Please connect with Botify first.', cls='text-invalid')
            logger.info(f'Getting analyses for {username}/{project_name}')
            slugs = await self.fetch_analyses(username, project_name, api_token)
            logger.info(f'Got {(len(slugs) if slugs else 0)} analyses')
            if not slugs:
                return P(f'Error: No analyses found for project {project_name}. Please check your API access.', cls='text-invalid')
            selected_value = selected_slug if selected_slug else slugs[0]

            # Get active template details for dynamic UI
            active_analysis_template_key = self.get_configured_template('analysis')
            active_template_details = self.QUERY_TEMPLATES.get(active_analysis_template_key, {})
            template_name = active_template_details.get('name', active_analysis_template_key)
            user_message = active_template_details.get('user_message', 'This will download crawl data.')
            button_suffix = active_template_details.get('button_label_suffix', 'Data')

            # Check for downloaded files - COMPREHENSIVE APPROACH
            # Check ALL possible file types regardless of current template selection
            downloaded_files_info = {}
            for slug in slugs:
                files_found = []

                # Check ALL possible crawl data types
                all_export_types = ['crawl_attributes', 'link_graph_edges']
                for export_type in all_export_types:
                    crawl_filepath = await self.get_deterministic_filepath(username, project_name, slug, export_type)
                    crawl_exists, _ = await self.check_file_exists(crawl_filepath)
                    if crawl_exists:
                        filename = os.path.basename(crawl_filepath)
                        files_found.append(filename)

                # Check weblog data
                weblog_filepath = await self.get_deterministic_filepath(username, project_name, slug, 'weblog')
                weblog_exists, _ = await self.check_file_exists(weblog_filepath)
                if weblog_exists:
                    files_found.append('weblog.csv')

                # Check GSC data
                gsc_filepath = await self.get_deterministic_filepath(username, project_name, slug, 'gsc_data')
                gsc_exists, _ = await self.check_file_exists(gsc_filepath)
                if gsc_exists:
                    files_found.append('gsc.csv')

                if files_found:
                    downloaded_files_info[slug] = files_found
            await self.message_queue.add(wand, self.step_messages.get(step_id, {}).get('input', f'Select an analysis for {project_name}'), verbatim=True)

            # Build dropdown options with human-readable descriptions
            dropdown_options = []
            for slug in slugs:
                # Convert analysis slug to readable date format (handle extensions like -2, -3)
                try:
                    # Parse YYYYMMDD format with optional -N extension
                    base_slug = slug
                    run_number = None
                    
                    # Check for -N extension (e.g., 20230802-2)
                    if '-' in slug:
                        parts = slug.split('-')
                        if len(parts) == 2 and parts[1].isdigit():
                            base_slug, run_number = parts[0], int(parts[1])
                    
                    # Parse the base date part
                    if len(base_slug) == 8 and base_slug.isdigit():
                        year, month, day = base_slug[:4], base_slug[4:6], base_slug[6:8]
                        from datetime import datetime
                        date_obj = datetime(int(year), int(month), int(day))
                        
                        # Add proper ordinal suffix
                        day_int = int(day)
                        if 10 <= day_int % 100 <= 13:  # Special case for 11th, 12th, 13th
                            day_suffix = 'th'
                        elif day_int % 10 == 1:
                            day_suffix = 'st'
                        elif day_int % 10 == 2:
                            day_suffix = 'nd'
                        elif day_int % 10 == 3:
                            day_suffix = 'rd'
                        else:
                            day_suffix = 'th'
                        
                        readable_date = f"{date_obj.strftime('%Y %B')} {day_int}{day_suffix}"
                        
                        # Add run number if present
                        if run_number:
                            readable_date += f" (Run #{run_number})"
                    else:
                        readable_date = slug
                except:
                    readable_date = slug
                
                # Create descriptive option text
                template_name = active_template_details.get('name', 'Crawl Data')
                base_text = f"Download {template_name} for {readable_date}"
                
                # Add file info if files exist
                if slug in downloaded_files_info:
                    files_summary = ', '.join(downloaded_files_info[slug])
                    option_text = f"{base_text} ({slug}) - Files: {files_summary}"
                else:
                    option_text = f"{base_text} ({slug})"
                    
                dropdown_options.append(Option(option_text, value=slug, selected=slug == selected_value))

            # Check if files are cached for the selected analysis to determine button text
            selected_analysis = selected_value if selected_value else (slugs[0] if slugs else '')
            active_template_details = self.QUERY_TEMPLATES.get(active_analysis_template_key, {})
            export_type = active_template_details.get('export_type', 'crawl_attributes')

            is_cached = False
            if selected_analysis:
                is_cached, file_info = await self.check_cached_file_for_button_text(username, project_name, selected_analysis, export_type)

            if is_cached and file_info:
                button_text = f'Use Cached {button_suffix} ({file_info["size"]}) ▸'
            else:
                button_text = f'Download {button_suffix} ▸'

            return Div(
                Card(
                    H3(f'{step.show}'), 
                    P(f"Select an analysis for project '{project_name}'"), 
                    P(f'Organization: {username}', cls='text-secondary'), 
                    P(user_message, cls='text-muted font-italic progress-spaced'), 
                    Form(
                                            Select(
                        *dropdown_options, 
                        name='analysis_slug', 
                        required=True, 
                        autofocus=True,
                        id='trifecta-analysis-select',
                        aria_label='Select analysis for data download',
                        data_testid='trifecta-analysis-select',
                        hx_post=f'/{app_name}/update_button_text',
                        hx_target='#submit-button',
                        hx_trigger='change',
                        hx_include='closest form',
                        hx_swap='outerHTML'
                    ),
                        Input(type='hidden', name='username', value=username,
                              data_testid='trifecta-hidden-username'),
                        Input(type='hidden', name='project_name', value=project_name,
                              data_testid='trifecta-hidden-project-name'),
                        Input(type='hidden', name='step_context', value='step_analysis',
                              data_testid='trifecta-hidden-step-context'),
                        Button(button_text, type='submit', cls='mt-10px primary', id='submit-button',
                               aria_label='Download selected analysis data',
                               data_testid='trifecta-analysis-submit-button',
                               **{'hx-on:click': 'this.setAttribute("aria-busy", "true"); this.textContent = "Processing..."'}), 
                        hx_post=f'/{app_name}/{step_id}_submit', 
                        hx_target=f'#{step_id}'
                    )
                ), 
                Div(id=next_step_id), 
                id=step_id
            )
        except Exception as e:
            logger.error(f'Error in {step_id}: {e}')
            return P(f'Error fetching analyses: {str(e)}', cls='text-invalid')

    async def step_analysis_submit(self, request):
        """Process the selected analysis slug for step_analysis and download crawl data."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_analysis'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        prev_step_id = 'step_project'
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
        
        # NEW: Save advanced export data as soon as we have an analysis slug
        api_token = self.read_api_token()
        if api_token:
            try:
                await self.message_queue.add(wand, "🔍 Fetching advanced export data...", verbatim=True)
                success, save_message, filepath = await self.save_advanced_export_to_json(username, project_name, analysis_slug, api_token)
                await self.message_queue.add(wand, save_message, verbatim=True)
                
                if success and filepath:
                    # Log the API call for debugging purposes
                    url = f'https://api.botify.com/v1/analyses/{username}/{project_name}/{analysis_slug}/advanced_export'
                    headers = {'Authorization': f'Token {api_token}', 'Content-Type': 'application/json'}
                    curl_cmd, python_cmd = self._generate_api_call_representations(
                        method="GET", url=url, headers=headers, 
                        step_context="Step 2: Save Advanced Export Data",
                        username=username, project_name=project_name
                    )
                    # Get the response data for radical transparency
                    with open(filepath, 'r', encoding='utf-8') as f:
                        saved_data = json.load(f)
                    
                    await wand.log_api_call_details(
                        pipeline_id=pipeline_id, step_id=step_id,
                        call_description="Fetch and Save Advanced Export Data",
                        http_method="GET", url=url, headers=headers,
                        response_status=200,
                        response_preview=f"Advanced export data saved to: {filepath}",
                        response_data=saved_data,  # Full response data for discovery transparency
                        curl_command=curl_cmd, python_command=python_cmd
                    )
                    
            except Exception as e:
                await self.message_queue.add(wand, f"⚠️ Could not save advanced export data: {str(e)}", verbatim=True)
                logger.error(f'Error in advanced export data saving: {e}')
        else:
            await self.message_queue.add(wand, "⚠️ No API token found - skipping advanced export data save", verbatim=True)
        
        # Get active template details and check for qualifier config
        active_analysis_template_key = self.get_configured_template('analysis')
        active_template_details = self.QUERY_TEMPLATES.get(active_analysis_template_key, {})
        qualifier_config = active_template_details.get('qualifier_config', {'enabled': False})
        export_type = active_template_details.get('export_type', 'crawl_attributes')

        # Check for cached file first (performance optimization)
        try:
            exists, file_info = await self.check_cached_file_for_button_text(username, project_name, analysis_slug, export_type)
            if exists:
                # File is cached - return immediately with completion widget
                analysis_result = {
                    'analysis_slug': analysis_slug,
                    'project': project_name,
                    'username': username,
                    'timestamp': datetime.now().isoformat(),
                    'download_started': False,  # Cached, no download needed
                    'cached': True,
                    'file_info': file_info,
                    'export_type': export_type
                }
                analysis_result_str = json.dumps(analysis_result)
                await wand.set_step_data(pipeline_id, step_id, step.done, analysis_result_str)
                
                # Create completion widget with action buttons
                completed_message = f"Using cached crawl data ({file_info['size']})"
                
                # Prepare step_data for action buttons with download_complete flag
                step_data_for_buttons = analysis_result.copy()
                step_data_for_buttons['download_complete'] = True
                action_buttons = self._create_action_buttons(step_data_for_buttons, step_id)

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
                        Pre(f'Status: {completed_message}', cls='code-block-container status-success-hidden'),
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
            # Cache check failed, continue with download
            pass

        await self.message_queue.add(wand, f'📊 Selected analysis: {analysis_slug}. Starting crawl data download...', verbatim=True)

        analysis_result = {
            'analysis_slug': analysis_slug,
            'project': project_name,
            'username': username,
            'timestamp': datetime.now().isoformat(),
            'download_started': True,
            'export_type': export_type
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
            Progress(cls='progress-spaced'),
            Script(f"""
                setTimeout(function() {{
                    htmx.ajax('POST', '/{app_name}/step_analysis_process', {{
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

    async def step_crawler(self, request):
        """Handles GET request for basic crawl data download step."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_crawler'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        check_result_str = step_data.get(step.done, '')
        check_result = json.loads(check_result_str) if check_result_str else {}
        prev_step_id = 'step_project'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('botify_project', '')
        if not prev_data_str:
            return P('Error: Project data not found. Please complete step 1 first.', cls='text-invalid')
        project_data = json.loads(prev_data_str)
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')
        if check_result and state.get('_revert_target') != step_id:
            has_crawler = check_result.get('has_crawler', False)
            status_text = 'Downloaded basic crawl attributes' if has_crawler else 'Basic crawl attributes not available'
            status_color = 'green' if has_crawler else 'red'
            # Standardize step data before creating action buttons (fixes regression)
            standardized_step_data = self._prepare_action_button_data(check_result, step_id, pipeline_id)
            action_buttons = self._create_action_buttons(standardized_step_data, step_id)

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
                    Pre(f'Status: {status_text}', cls='code-block-container', style=f'color: {status_color}; display: none;'),
                    id=f'{step_id}_widget'
                )
            )
            return Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: {status_text}', widget=widget, steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        else:
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
            crawler_template = self.get_configured_template('crawler')

            # Check if basic crawl data is cached for the CURRENT analysis
            # Use the same logic as step_analysis to get the current analysis
            is_cached = False
            try:
                # Get the current analysis from step_analysis data - try multiple possible keys
                analysis_step_id = 'step_analysis'
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
                    # Use the proper template-aware file checking method
                    is_cached, file_info = await self.check_cached_file_for_template_config(username, project_name, current_analysis_slug, 'crawler')
            except Exception:
                is_cached, file_info = False, None

            if is_cached and file_info:
                button_text = f'Use Cached Basic Crawl: {crawler_template} ({file_info["size"]}) ▸'
            else:
                button_text = f'Download Basic Crawl Attributes: {crawler_template} ▸'

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

            return Div(Card(H3(f'{step.show}'), P(f"Download basic crawl data for '{project_name}'"), P(f'Organization: {username}', cls='text-secondary'), Form(Div(*button_row_items, style=self.ui['BUTTON_STYLES']['BUTTON_ROW']), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_crawler_submit(self, request):
        """Process the basic crawl data download submission."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_crawler'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')

        # Check if user clicked skip button
        form = await request.form()
        action = form.get('action', 'download')  # Default to download for backward compatibility

        if action == 'skip':
            # Handle skip action - create fake completion data and proceed to next step
            await self.message_queue.add(wand, f"⏭️ Skipping basic crawl data download...", verbatim=True)

            # Create skip data that indicates step was skipped
            skip_result = {
                'has_crawler': False,
                'skipped': True,
                'skip_reason': 'User chose to skip basic crawl data download',
                'download_complete': False,
                'file_path': None,
                'export_type': 'crawl_attributes',
                'template_used': 'Crawl Basic'
            }

            await wand.set_step_data(pipeline_id, step_id, json.dumps(skip_result), steps)
            await self.message_queue.add(wand, f"⏭️ Basic crawl data step skipped. Proceeding to next step.", verbatim=True)

            return Div(
                wand.display_revert_widget(
                    step_id=step_id,
                    app_name=app_name,
                    message=f'{step.show}: Skipped',
                    widget=Div(P('This step was skipped.', cls='text-secondary')),
                    steps=steps
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )

        # Handle normal download action
        prev_step_id = 'step_project'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('botify_project', '')
        if not prev_data_str:
            return P('Error: Project data not found. Please complete step 1 first.', cls='text-invalid')
        project_data = json.loads(prev_data_str)
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')

        # Get analysis slug from step_analysis data
        analysis_step_id = 'step_analysis'
        analysis_step_data = wand.get_step_data(pipeline_id, analysis_step_id, {})
        analysis_slug = ''
        if analysis_step_data:
            analysis_data_str = analysis_step_data.get('analysis_selection', '')
            if analysis_data_str:
                try:
                    analysis_data = json.loads(analysis_data_str)
                    analysis_slug = analysis_data.get('analysis_slug', '')
                except (json.JSONDecodeError, AttributeError):
                    pass

        if not analysis_slug:
            return P('Error: Analysis data not found. Please complete step 2 first.', cls='text-invalid')

        # Check if basic crawl data is already cached
        try:
            is_cached, file_info = await self.check_cached_file_for_button_text(username, project_name, analysis_slug, 'crawl_attributes')
            
            if is_cached and file_info:
                # Use cached file - create immediate completion result
                await self.message_queue.add(wand, f"✅ Using cached basic crawl data ({file_info['size']})...", verbatim=True)
                
                # Generate Python code for cached file to enable toggle functionality
                try:
                    # Use the step_analysis_process approach to generate proper Python code
                    # Build the export payload specifically for the crawler (basic crawl) template
                    export_result = await self.build_exports(
                        username=username,
                        project_name=project_name,
                        analysis_slug=analysis_slug,
                        data_type='crawl'  # Use 'crawl' not 'crawl_attributes'
                    )
                    
                    jobs_payload = export_result['export_job_payload']
                    
                    # Override the template to use 'Crawl Basic' instead of 'Link Graph Edges'  
                    crawler_template = self.get_configured_template('crawler')  # Should be 'Crawl Basic'
                    template_query = self.apply_template(crawler_template, f'crawl.{analysis_slug}')
                    
                    # Update the jobs payload with the crawler template query
                    jobs_payload['payload']['query']['query'] = template_query
                    
                    # Generate Python code representations
                    curl_command, python_code = self._generate_api_call_representations(
                        method='POST',
                        url="https://api.botify.com/v1/jobs",
                        headers={'Authorization': f'Token {self.read_api_token()}', 'Content-Type': 'application/json'},
                        payload=jobs_payload,
                        step_context='step_crawler',
                        template_info=self.QUERY_TEMPLATES.get(crawler_template, {}),
                        username=username,
                        project_name=project_name
                    )
                except Exception as e:
                    # Fallback if code generation fails
                    python_code = f"# Python code generation failed: {str(e)}"
                    curl_command = f"# Curl command generation failed: {str(e)}"
                    jobs_payload = {}
                
                # Create cached result data with proper Python code
                cached_result = {
                    'has_crawler': True,
                    'project': project_name,
                    'username': username,
                    'analysis_slug': analysis_slug,
                    'timestamp': datetime.now().isoformat(),
                    'download_complete': True,
                    'file_path': file_info['path'],
                    'file_size': file_info['size'],
                    'cached': True,
                    'raw_python_code': python_code,  # Fixed: Use python_code, not curl_command
                    'query_python_code': python_code,  # Fixed: Use python_code, not curl_command
                    'jobs_payload': jobs_payload,
                    'python_command': python_code  # Fixed: This should be Python, not curl
                }
                
                # Store the cached result
                await wand.set_step_data(pipeline_id, step_id, json.dumps(cached_result), steps)
                
                # Create completion widget
                action_buttons = self._create_action_buttons(cached_result, step_id)
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
                        Pre(f'Status: Using cached basic crawl data ({file_info["size"]})', cls='code-block-container status-success-hidden'),
                        id=f'{step_id}_widget'
                    )
                )
                
                return Div(
                    wand.display_revert_widget(
                        step_id=step_id,
                        app_name=app_name,
                        message=f'{step.show}: Using cached basic crawl data ({file_info["size"]})',
                        widget=widget,
                        steps=steps
                    ),
                    Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                    id=step_id
                )
                
        except Exception as e:
            # If cache check fails, proceed with download
            await self.message_queue.add(wand, f"Cache check failed, proceeding with download: {str(e)}", verbatim=True)

        # Proceed with download if not cached
        return Card(
            H3(f'{step.show}'),
            P(f"Downloading basic crawl data for '{project_name}'..."),
            Progress(cls='progress-spaced'),
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

    async def step_crawler_complete(self, request):
        """Handles completion of basic crawl data step - delegates to step_analysis_process."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_crawler'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        
        # Get project and analysis data
        prev_step_id = 'step_project'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('botify_project', '')
        if not prev_data_str:
            return P('Error: Project data not found.', cls='text-invalid')
        project_data = json.loads(prev_data_str)
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')
        
        analysis_step_id = 'step_analysis'
        analysis_step_data = wand.get_step_data(pipeline_id, analysis_step_id, {})
        analysis_data_str = analysis_step_data.get('analysis_selection', '')
        if not analysis_data_str:
            return P('Error: Analysis data not found.', cls='text-invalid')
        analysis_data = json.loads(analysis_data_str)
        analysis_slug = analysis_data.get('analysis_slug', '')

        try:
            # Call step_analysis_process with step_context to indicate this is for basic crawl
            # Create a fake request with the required form data
            from starlette.datastructures import FormData
            fake_form_data = FormData([
                ('analysis_slug', analysis_slug),
                ('username', username), 
                ('project_name', project_name)
            ])
            
            # Create a mock request object with our form data
            class MockRequest:
                def __init__(self, form_data):
                    self._form_data = form_data
                
                async def form(self):
                    return self._form_data
            
            mock_request = MockRequest(fake_form_data)
            
            # Call step_analysis_process with our context
            result = await self.step_analysis_process(mock_request, step_context='step_crawler')
            
            # Get the actual step data that was stored by step_analysis_process
            # It should have been stored with key 'crawler_basic' (our step's done key)
            stored_step_data = wand.get_step_data(pipeline_id, step_id, {})
            stored_data_str = stored_step_data.get(step.done, '')
            
            if stored_data_str:
                # Parse the stored data to get python_command and other details
                stored_data = json.loads(stored_data_str)
                
                # Enhance the stored data with additional info needed for buttons and toggle
                enhanced_data = {
                    **stored_data,  # Keep all existing data (including python_command)
                    'has_crawler': True,
                    'project': project_name,
                    'project_name': project_name,  # Add project_name for _create_action_buttons
                    'username': username,
                    'analysis_slug': analysis_slug,
                    'timestamp': datetime.now().isoformat(),
                    'step_context': 'step_crawler',
                    'download_complete': True  # Add this flag for _create_action_buttons
                }
                
                # Re-store the enhanced data
                await wand.set_step_data(pipeline_id, step_id, json.dumps(enhanced_data), steps)
            else:
                # Fallback if no data was stored (shouldn't happen but safety first)
                check_result = {
                    'has_crawler': True,
                    'project': project_name,
                    'project_name': project_name,
                    'username': username,
                    'analysis_slug': analysis_slug,
                    'timestamp': datetime.now().isoformat(),
                    'step_context': 'step_crawler',
                    'download_complete': True,
                    'python_command': '# Step completed but Python code not available'
                }
                await wand.set_step_data(pipeline_id, step_id, json.dumps(check_result), steps)
            
            return result
            
        except Exception as e:
            logger.error(f'Error in step_crawler_complete: {e}')
            return Div(P(f'Error: {str(e)}', cls='text-invalid'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)

    async def step_webogs(self, request):
        """Handles GET request for checking if a Botify project has web logs."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_webogs'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        check_result_str = step_data.get(step.done, '')
        check_result = json.loads(check_result_str) if check_result_str else {}
        prev_step_id = 'step_project'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('botify_project', '')
        if not prev_data_str:
            return P('Error: Project data not found. Please complete step 1 first.', cls='text-invalid')
        project_data = json.loads(prev_data_str)
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')
        if check_result and state.get('_revert_target') != step_id:
            has_logs = check_result.get('has_logs', False)
            status_text = 'HAS web logs' if has_logs else 'does NOT have web logs'
            status_color = 'green' if has_logs else 'red'
            # Standardize step data before creating action buttons (fixes regression)
            standardized_step_data = self._prepare_action_button_data(check_result, step_id, pipeline_id)
            action_buttons = self._create_action_buttons(standardized_step_data, step_id)

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
            # Use the same logic as step_analysis to get the current analysis
            is_cached = False
            try:
                # Get the current analysis from step_analysis data - try multiple possible keys
                analysis_step_id = 'step_analysis'
                analysis_step_data = wand.get_step_data(pipeline_id, analysis_step_id, {})
                current_analysis_slug = ''

                # Try to get analysis_slug from the stored data
                if analysis_step_data:
                    # Debug: Print what we actually have
                    # print(f"DEBUG step_webogs: analysis_step_data = {analysis_step_data}")
                    # print(f"DEBUG step_webogs: analysis_step_data keys = {list(analysis_step_data.keys()) if isinstance(analysis_step_data, dict) else 'not a dict'}")

                    # Try the 'analysis_selection' key first
                    analysis_data_str = analysis_step_data.get('analysis_selection', '')
                    # print(f"DEBUG step_webogs: analysis_data_str = {analysis_data_str[:100] if analysis_data_str else 'empty'}")
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
                    # Use the legacy file checking method for weblog (not templated)
                    is_cached, file_info = await self.check_cached_file_for_button_text(username, project_name, current_analysis_slug, 'weblog')
            except Exception:
                is_cached, file_info = False, None

            # Set button text based on cache status
            if is_cached and file_info:
                button_text = f'Use Cached Web Logs ({file_info["size"]}) ▸'
            else:
                button_text = 'Download Web Logs ▸'

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

    async def step_webogs_submit(self, request):
        """Process the check for Botify web logs and download if available."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_webogs'
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
                    widget=Div(P('This step was skipped.', cls='text-secondary')),
                    steps=steps
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )

        # Handle normal download action
        prev_step_id = 'step_project'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('botify_project', '')
        if not prev_data_str:
            return P('Error: Project data not found. Please complete step 1 first.', cls='text-invalid')
        project_data = json.loads(prev_data_str)
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')
        analysis_step_id = 'step_analysis'
        analysis_step_data = wand.get_step_data(pipeline_id, analysis_step_id, {})
        analysis_data_str = analysis_step_data.get('analysis_selection', '')
        if not analysis_data_str:
            return P('Error: Analysis data not found. Please complete step 2 first.', cls='text-invalid')
        analysis_data = json.loads(analysis_data_str)
        analysis_slug = analysis_data.get('analysis_slug', '')

        # Check for cached file first (performance optimization)
        try:
            exists, file_info = await self.check_cached_file_for_button_text(username, project_name, analysis_slug, 'weblog')
            if exists:
                # Use cached file
                await self.message_queue.add(wand, f"✅ Using cached Web Logs data ({file_info['size']})...", verbatim=True)
                
                # Create cached result data
                cached_result = {
                    'has_logs': True,
                    'project': project_name,
                    'username': username,
                    'analysis_slug': analysis_slug,
                    'timestamp': datetime.now().isoformat(),
                    'download_complete': True,
                    'file_path': file_info['path'],
                    'file_size': file_info['size'],
                    'cached': True,
                    'raw_python_code': '',
                    'query_python_code': '',
                    'jobs_payload': {}
                }

                await wand.set_step_data(pipeline_id, step_id, json.dumps(cached_result), steps)

                # Create completion widget
                action_buttons = self._create_action_buttons(cached_result, step_id)
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
                        Pre(f'Status: Using cached Web Logs data ({file_info["size"]})', cls='code-block-container status-success-hidden'),
                        id=f'{step_id}_widget'
                    )
                )

                return Div(
                    wand.display_revert_widget(
                        step_id=step_id,
                        app_name=app_name,
                        message=f'{step.show}: Using cached Web Logs data ({file_info["size"]})',
                        widget=widget,
                        steps=steps
                    ),
                    Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                    id=step_id
                )
        except Exception as e:
            await self.message_queue.add(wand, f"Cache check failed, proceeding with download: {str(e)}", verbatim=True)

        # Fallback to download if no cached file or cache check failed
        return Card(
            H3(f'{step.show}'),
            P(f"Downloading Web Logs for '{project_name}'..."),
            Progress(cls='progress-spaced'),
            Script(f"""
                setTimeout(function() {{
                    htmx.ajax('POST', '/{app_name}/step_webogs_complete', {{
                        target: '#{step_id}',
                        values: {{
                            'analysis_slug': '{analysis_slug}',
                            'username': '{username}',
                            'project_name': '{project_name}',
                            'delay_complete': 'true'
                        }}
                    }});
                }}, 1500);
            """),
            id=step_id
        )

    async def step_webogs_complete(self, request):
        """Handles completion after the progress indicator has been shown."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_webogs'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        
        # Get form data
        form = await request.form()
        analysis_slug = form.get('analysis_slug', '').strip()
        username = form.get('username', '').strip()
        project_name = form.get('project_name', '').strip()
        
        if not all([analysis_slug, username, project_name]):
            # Try to get from previous steps if not in form
            prev_step_id = 'step_project'
            prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
            prev_data_str = prev_step_data.get('botify_project', '')
            if prev_data_str:
                project_data = json.loads(prev_data_str)
                project_name = project_data.get('project_name', '')
                username = project_data.get('username', '')
                
            analysis_step_id = 'step_analysis'
            analysis_step_data = wand.get_step_data(pipeline_id, analysis_step_id, {})
            analysis_data_str = analysis_step_data.get('analysis_selection', '')
            if analysis_data_str:
                try:
                    analysis_data = json.loads(analysis_data_str)
                    analysis_slug = analysis_data.get('analysis_slug', '')
                except (json.JSONDecodeError, AttributeError):
                    pass
        
        if not all([analysis_slug, username, project_name]):
            return P('Error: Missing required parameters', cls='text-invalid')
            
        # Call the existing step_webogs_process logic
        return await self.step_webogs_process(request)

    async def step_gsc(self, request):
        """Handles GET request for checking if a Botify project has Search Console data."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_gsc'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        check_result_str = step_data.get(step.done, '')
        check_result = json.loads(check_result_str) if check_result_str else {}
        prev_step_id = 'step_project'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('botify_project', '')
        if not prev_data_str:
            return P('Error: Project data not found. Please complete step 1 first.', cls='text-invalid')
        project_data = json.loads(prev_data_str)
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')
        if check_result and state.get('_revert_target') != step_id:
            has_search_console = check_result.get('has_search_console', False)
            status_text = 'HAS Search Console data' if has_search_console else 'does NOT have Search Console data'
            status_color = 'green' if has_search_console else 'red'
            # Standardize step data before creating action buttons (fixes regression)
            standardized_step_data = self._prepare_action_button_data(check_result, step_id, pipeline_id)
            action_buttons = self._create_action_buttons(standardized_step_data, step_id)

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
            # Use the same logic as step_analysis to get the current analysis
            is_cached = False
            try:
                # Get the current analysis from step_analysis data - try multiple possible keys
                analysis_step_id = 'step_analysis'
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
                    # Use the proper template-aware file checking method
                    is_cached, file_info = await self.check_cached_file_for_template_config(username, project_name, current_analysis_slug, 'gsc')
            except Exception:
                is_cached, file_info = False, None

            if is_cached and file_info:
                button_text = f'Use Cached Search Console: {gsc_template} ({file_info["size"]}) ▸'
            else:
                button_text = f'Download Search Console: {gsc_template} ▸'

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

    async def step_gsc_submit(self, request):
        """Process the check for Botify Search Console data."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_gsc'
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
                    widget=Div(P('This step was skipped.', cls='text-secondary')),
                    steps=steps
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )

        # Handle normal download action
        prev_step_id = 'step_project'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('botify_project', '')
        if not prev_data_str:
            return P('Error: Project data not found. Please complete step 1 first.', cls='text-invalid')
        project_data = json.loads(prev_data_str)
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')

        # Get analysis slug from step_analysis data
        analysis_step_id = 'step_analysis'
        analysis_step_data = wand.get_step_data(pipeline_id, analysis_step_id, {})
        analysis_slug = ''
        if analysis_step_data:
            analysis_data_str = analysis_step_data.get('analysis_selection', '')
            if analysis_data_str:
                try:
                    analysis_data = json.loads(analysis_data_str)
                    analysis_slug = analysis_data.get('analysis_slug', '')
                except (json.JSONDecodeError, AttributeError):
                    pass

        if not analysis_slug:
            return P('Error: Analysis data not found. Please complete step 2 first.', cls='text-invalid')

        # Check if GSC data is already cached
        try:
            is_cached, file_info = await self.check_cached_file_for_button_text(username, project_name, analysis_slug, 'gsc_data')
            
            if is_cached and file_info:
                # Use cached file - create immediate completion result
                await self.message_queue.add(wand, f"✅ Using cached GSC data ({file_info['size']})...", verbatim=True)
                
                # Create cached result data
                cached_result = {
                    'has_search_console': True,
                    'project': project_name,
                    'username': username,
                    'analysis_slug': analysis_slug,
                    'timestamp': datetime.now().isoformat(),
                    'download_complete': True,
                    'file_path': file_info['path'],
                    'file_size': file_info['size'],
                    'cached': True,
                    'raw_python_code': '',
                    'query_python_code': '',
                    'jobs_payload': {}
                }
                
                # Store the cached result
                await wand.set_step_data(pipeline_id, step_id, json.dumps(cached_result), steps)
                
                # Create completion widget
                action_buttons = self._create_action_buttons(cached_result, step_id)
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
                        Pre(f'Status: Using cached GSC data ({file_info["size"]})', cls='code-block-container status-success-hidden'),
                        id=f'{step_id}_widget'
                    )
                )
                
                return Div(
                    wand.display_revert_widget(
                        step_id=step_id,
                        app_name=app_name,
                        message=f'{step.show}: Using cached GSC data ({file_info["size"]})',
                        widget=widget,
                        steps=steps
                    ),
                    Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                    id=step_id
                )
                
        except Exception as e:
            # If cache check fails, proceed with download
            await self.message_queue.add(wand, f"Cache check failed, proceeding with download: {str(e)}", verbatim=True)

        # Proceed with download if not cached
        return Card(
            H3(f'{step.show}'),
            P(f"Downloading Search Console data for '{project_name}'..."),
            Progress(cls='progress-spaced'),
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

    async def step_gsc_complete(self, request):
        """Handles completion after the progress indicator has been shown."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_gsc'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        prev_step_id = 'step_project'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('botify_project', '')
        if not prev_data_str:
            return P('Error: Project data not found.', cls='text-invalid')
        project_data = json.loads(prev_data_str)
        project_name = project_data.get('project_name', '')
        username = project_data.get('username', '')
        analysis_step_id = 'step_analysis'
        analysis_step_data = wand.get_step_data(pipeline_id, analysis_step_id, {})
        analysis_data_str = analysis_step_data.get('analysis_selection', '')
        if not analysis_data_str:
            return P('Error: Analysis data not found.', cls='text-invalid')
        analysis_data = json.loads(analysis_data_str)
        analysis_slug = analysis_data.get('analysis_slug', '')
        try:
            has_search_console, error_message = await self.check_if_project_has_collection(username, project_name, 'search_console')
            if error_message:
                return Div(P(f'Error: {error_message}', cls='text-invalid'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
            check_result = {'has_search_console': has_search_console, 'project': project_name, 'username': username, 'analysis_slug': analysis_slug, 'timestamp': datetime.now().isoformat()}
            if has_search_console:
                await self.message_queue.add(wand, f'✅ Project has Search Console data, downloading...', verbatim=True)
                await self.process_search_console_data(wand, pipeline_id, step_id, username, project_name, analysis_slug, check_result)
            else:
                await self.message_queue.add(wand, f'Project does not have Search Console data (skipping download)', verbatim=True)
                
                # Generate Python debugging code even when no GSC data (for educational purposes)
                try:
                    analysis_date_obj = datetime.strptime(analysis_slug, '%Y%m%d')
                    start_date = analysis_date_obj.strftime('%Y-%m-%d')
                    end_date = (analysis_date_obj + timedelta(days=6)).strftime('%Y-%m-%d')
                    
                    # Create example GSC export payload for educational purposes
                    gsc_template = self.get_configured_template('gsc')
                    example_export_payload = await self.build_exports(
                        username, project_name, analysis_slug, 'gsc_data', start_date, end_date
                    )
                    
                    # Generate Python code for debugging
                    _, _, python_command = self.generate_query_api_call(example_export_payload, username, project_name)
                    check_result['python_command'] = python_command
                except Exception as e:
                    # Fallback to basic example if generation fails
                    check_result['python_command'] = f'# Example GSC query for {project_name} (no GSC data available)\n# This project does not have Search Console data integrated.'
                
                check_result_str = json.dumps(check_result)
                await wand.set_step_data(pipeline_id, step_id, check_result_str, steps)
            status_text = 'HAS' if has_search_console else 'does NOT have'
            completed_message = 'Data downloaded successfully' if has_search_console else 'No Search Console data available'
            # Standardize step data before creating action buttons (fixes regression)
            standardized_step_data = self._prepare_action_button_data(check_result, step_id, pipeline_id)
            action_buttons = self._create_action_buttons(standardized_step_data, step_id)

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
                    Pre(f'Status: Project {status_text} Search Console data', cls='code-block-container', style=f'color: {"green" if has_search_console else "red"}; display: none;'),
                    id=f'{step_id}_widget'
                )
            )
            return Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: {completed_message}', widget=widget, steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        except Exception as e:
            logger.error(f'Error in step_gsc_complete: {e}')
            return Div(P(f'Error: {str(e)}', cls='text-invalid'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)




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
        api_key = self.read_api_token()
        if not api_key:
            return (False, "Botify API token not found in the .env vault. Please run the Configuration App.")
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
            logger.error(f'Missing required parameters: org={org}, project={project}')
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
                    logger.error(f'API error: Status {response.status_code} for {next_url}')
                    return all_slugs

                data = response.json()
                if 'results' not in data:
                    logger.error(f"No 'results' key in response: {data}")
                    return all_slugs

                analyses = data['results']
                if not analyses:
                    logger.error('Analyses list is empty')
                    return all_slugs

                # Log first page with minimal info (analysis dropdown responses are too large for transparency)
                if is_first_page:
                    logger.info(f'📋 Fetching analysis list for project: {project}')
                    logger.info(f'🔗 API URL: {next_url}')
                    logger.info(f'📊 Found {len(analyses)} analyses on first page')
                    is_first_page = False
                else:
                    # Just log that we're fetching subsequent pages
                    logger.info(f'📋 Fetching next page of analyses: {next_url}')

                page_slugs = [analysis.get('slug') for analysis in analyses if analysis.get('slug')]
                all_slugs.extend(page_slugs)

                # Get next page URL if it exists
                next_url = data.get('next')

            except Exception as e:
                logger.error(f'Error fetching analyses: {str(e)}')
                return all_slugs

        logger.info(f'Found {len(all_slugs)} total analyses')
        return all_slugs

    def read_api_token(self):
        """Read the Botify API token from the secure .env vault."""
        try:
            return self.pipulate.load_secrets("BOTIFY_API_TOKEN")
        except Exception as e:
            logger.error(f"Error loading Botify API token from vault: {e}")
            return None

    async def save_analyses_to_json(self, username, project_name, api_token):
        """
        Fetch and save the complete analyses data to a local JSON file.
        
        This method fetches the full analyses data from the Botify API endpoint:
        /analyses/{username}/{project_name}
        
        And saves it to a deterministic local path:
        downloads/{APP_NAME}/{username}/{project_name}/analyses.json
        
        Args:
            username: Organization slug
            project_name: Project slug  
            api_token: Botify API token
            
        Returns:
            tuple: (success: bool, message: str, filepath: str|None)
        """
        try:
            # Create deterministic filepath for analyses.json at project level
            base_dir = f'downloads/{self.app_name}/{username}/{project_name}'
            analyses_filepath = f'{base_dir}/analyses.json'
            
            # Ensure directory exists
            await self.ensure_directory_exists(analyses_filepath)
            
            # Check if file already exists
            exists, file_info = await self.check_file_exists(analyses_filepath)
            if exists:
                return (True, f"📄 Analyses data already cached: {file_info['size']}", analyses_filepath)
            
            # Fetch analyses data from API
            url = f'https://api.botify.com/v1/analyses/{username}/{project_name}/light'
            headers = {'Authorization': f'Token {api_token}', 'Content-Type': 'application/json'}
            
            all_analyses = []
            next_url = url
            page_count = 0
            
            # Fetch all pages of analyses data
            while next_url:
                page_count += 1
                async with httpx.AsyncClient() as client:
                    response = await client.get(next_url, headers=headers, timeout=60.0)
                
                if response.status_code != 200:
                    return (False, f"API error: Status {response.status_code} - {response.text}", None)
                
                data = response.json()
                if 'results' not in data:
                    return (False, f"No 'results' key in API response", None)
                
                # Add analyses from this page
                analyses = data['results']
                all_analyses.extend(analyses)
                
                # Get next page URL
                next_url = data.get('next')
                
                # Log progress for multiple pages
                if page_count > 1:
                    await self.message_queue.add(self.pipulate, f"📄 Fetched page {page_count} of analyses data...", verbatim=True)
            
            # Create comprehensive analyses data structure
            analyses_data = {
                'metadata': {
                    'organization': username,
                    'project': project_name,
                    'fetch_timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
                    'total_analyses': len(all_analyses),
                    'pages_fetched': page_count,
                    'api_endpoint': f'/analyses/{username}/{project_name}'
                },
                'analyses': all_analyses
            }
            
            # Save to JSON file
            with open(analyses_filepath, 'w', encoding='utf-8') as f:
                json.dump(analyses_data, f, indent=2, ensure_ascii=False)
            
            # Verify file was created successfully
            exists, file_info = await self.check_file_exists(analyses_filepath)
            if not exists:
                return (False, "Failed to save analyses data to file", None)
            
            return (True, f"📄 Analyses data saved: {len(all_analyses)} analyses ({file_info['size']})", analyses_filepath)
            
        except Exception as e:
            logger.error(f'Error saving analyses data: {str(e)}')
            return (False, f"Error saving analyses data: {str(e)}", None)

    async def save_advanced_export_to_json(self, username, project_name, analysis_slug, api_token):
        """
        Fetch and save the advanced export data for a specific analysis to a local JSON file.
        
        This method fetches the advanced export data from the Botify API endpoint:
        /api/v1/analyses/{username}/{project_name}/{analysis_slug}/advanced_export
        
        And saves it to a deterministic local path:
        downloads/{APP_NAME}/{username}/{project_name}/{analysis_slug}/analysis_advanced.json
        
        Args:
            username: Organization slug
            project_name: Project slug
            analysis_slug: Analysis slug
            api_token: Botify API token
            
        Returns:
            tuple: (success: bool, message: str, filepath: str|None)
        """
        try:
            # Create deterministic filepath for analysis_advanced.json
            base_dir = f'downloads/{self.app_name}/{username}/{project_name}/{analysis_slug}'
            advanced_export_filepath = f'{base_dir}/analysis_advanced.json'
            
            # Ensure directory exists
            await self.ensure_directory_exists(advanced_export_filepath)
            
            # Check if file already exists
            exists, file_info = await self.check_file_exists(advanced_export_filepath)
            if exists:
                return (True, f"📊 Advanced export data already cached: {file_info['size']}", advanced_export_filepath)
            
            # Fetch advanced export data from API
            url = f'https://api.botify.com/v1/analyses/{username}/{project_name}/{analysis_slug}/advanced_export'
            headers = {'Authorization': f'Token {api_token}', 'Content-Type': 'application/json'}
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=60.0)
            
            if response.status_code != 200:
                return (False, f"API error: Status {response.status_code} - {response.text}", None)
            
            # Get the response data
            advanced_export_data = response.json()
            
            # Create comprehensive advanced export data structure with metadata
            export_data = {
                'metadata': {
                    'organization': username,
                    'project': project_name,
                    'analysis_slug': analysis_slug,
                    'fetch_timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
                    'api_endpoint': f'/api/v1/analyses/{username}/{project_name}/{analysis_slug}/advanced_export'
                },
                'advanced_export': advanced_export_data
            }
            
            # Save to JSON file
            with open(advanced_export_filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            # Verify file was created successfully
            exists, file_info = await self.check_file_exists(advanced_export_filepath)
            if not exists:
                return (False, "Failed to save advanced export data to file", None)
            
            return (True, f"📊 Advanced export data saved: {file_info['size']}", advanced_export_filepath)
            
        except Exception as e:
            logger.error(f'Error saving advanced export data: {str(e)}')
            return (False, f"Error saving advanced export data: {str(e)}", None)

    async def extract_available_fields_from_advanced_export(self, username, project_name, analysis_slug, export_group='urls'):
        """
        Extract available fields from the analysis_advanced.json file for use in query metrics.
        
        This function reads the cached advanced export data and extracts the field lists
        from specific export types, making them available for use in QUERY_TEMPLATES metrics.
        
        Args:
            username: Organization slug
            project_name: Project slug
            analysis_slug: Analysis slug
            export_group: Filter by export group ('urls', 'links', or None for all)
            
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'fields': list,
                'available_exports': list  # List of export IDs that were found
            }
        """
        try:
            # Build path to the cached analysis_advanced.json file
            advanced_export_filepath = f'downloads/{self.app_name}/{username}/{project_name}/{analysis_slug}/analysis_advanced.json'
            
            # Check if file exists
            exists, file_info = await self.check_file_exists(advanced_export_filepath)
            if not exists:
                return {
                    'success': False,
                    'message': f"Advanced export file not found: {advanced_export_filepath}",
                    'fields': [],
                    'available_exports': []
                }
            
            # Read and parse the JSON file
            with open(advanced_export_filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract the advanced_export array
            advanced_exports = data.get('advanced_export', [])
            if not advanced_exports:
                return {
                    'success': False,
                    'message': "No advanced export data found in file",
                    'fields': [],
                    'available_exports': []
                }
            
            # Collect fields from exports matching the specified group
            all_fields = set()
            available_exports = []
            
            for export in advanced_exports:
                export_id = export.get('id', '')
                export_name = export.get('name', '')
                export_group_name = export.get('group', '')
                fields = export.get('fields', [])
                
                # Filter by group if specified
                if export_group and export_group_name != export_group:
                    continue
                
                # Add this export to our list
                available_exports.append({
                    'id': export_id,
                    'name': export_name,
                    'group': export_group_name,
                    'field_count': len(fields),
                    'fields': fields
                })
                
                # Add all fields to our master set
                all_fields.update(fields)
            
            # Convert set to sorted list for consistent ordering
            sorted_fields = sorted(list(all_fields))
            
            # Build success message
            total_exports = len(available_exports)
            total_fields = len(sorted_fields)
            group_filter_msg = f" (filtered by group: {export_group})" if export_group else ""
            
            message = f"Found {total_fields} unique fields from {total_exports} exports{group_filter_msg}"
            
            return {
                'success': True,
                'message': message,
                'fields': sorted_fields,
                'available_exports': available_exports
            }
            
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'message': f"Invalid JSON in advanced export file: {str(e)}",
                'fields': [],
                'available_exports': []
            }
        except Exception as e:
            logger.error(f'Error extracting fields from advanced export: {str(e)}')
            return {
                'success': False,
                'message': f"Error extracting fields: {str(e)}",
                'fields': [],
                'available_exports': []
            }

    async def test_extract_available_fields(self, username, project_name, analysis_slug):
        """
        Test function to verify extract_available_fields_from_advanced_export works correctly.
        
        This function tests the field extraction and provides detailed output for verification.
        
        Args:
            username: Organization slug
            project_name: Project slug
            analysis_slug: Analysis slug
            
        Returns:
            str: Formatted test results for display
        """
        try:
            # Test with URLs group
            url_result = await self.extract_available_fields_from_advanced_export(
                username, project_name, analysis_slug, export_group='urls'
            )
            
            # Test with links group
            links_result = await self.extract_available_fields_from_advanced_export(
                username, project_name, analysis_slug, export_group='links'
            )
            
            # Test with no group filter (all)
            all_result = await self.extract_available_fields_from_advanced_export(
                username, project_name, analysis_slug, export_group=None
            )
            
            # Build formatted test results
            test_results = []
            test_results.append("=== Field Extraction Test Results ===\n")
            
            # URLs group results
            test_results.append("📊 URLs Group Fields:")
            test_results.append(f"Status: {'✅ Success' if url_result['success'] else '❌ Failed'}")
            test_results.append(f"Message: {url_result['message']}")
            if url_result['success']:
                test_results.append(f"Available Exports: {len(url_result['available_exports'])}")
                for export in url_result['available_exports']:
                    test_results.append(f"  - {export['id']}: {export['field_count']} fields")
                test_results.append(f"Sample Fields: {', '.join(url_result['fields'][:10])}...")
            test_results.append("")
            
            # Links group results
            test_results.append("🔗 Links Group Fields:")
            test_results.append(f"Status: {'✅ Success' if links_result['success'] else '❌ Failed'}")
            test_results.append(f"Message: {links_result['message']}")
            if links_result['success']:
                test_results.append(f"Available Exports: {len(links_result['available_exports'])}")
                test_results.append(f"Sample Fields: {', '.join(links_result['fields'][:10])}...")
            test_results.append("")
            
            # All groups results
            test_results.append("🌐 All Groups Combined:")
            test_results.append(f"Status: {'✅ Success' if all_result['success'] else '❌ Failed'}")
            test_results.append(f"Message: {all_result['message']}")
            if all_result['success']:
                test_results.append(f"Total Available Exports: {len(all_result['available_exports'])}")
                test_results.append(f"Total Unique Fields: {len(all_result['fields'])}")
            
            return "\n".join(test_results)
            
        except Exception as e:
            return f"❌ Test failed with error: {str(e)}"

    async def _execute_qualifier_logic(self, username, project_name, analysis_slug, api_token, qualifier_config):
        """Execute the generic qualifier logic to determine a dynamic parameter.

        This method delegates to the shared qualifier logic in the code generators module.
        
        Returns:
            dict: {'parameter_value': determined_value, 'metric_at_parameter': metric_value}
        """
        from imports.botify.code_generators import execute_qualifier_logic
        optimal_param_value, final_metric_value = await execute_qualifier_logic(
            self, username, project_name, analysis_slug, api_token, qualifier_config
        )
        return {'parameter_value': optimal_param_value, 'metric_at_parameter': final_metric_value}

    def get_filename_for_export_type(self, export_type):
        """Get the filename for a given export type.
        
        This method centralizes filename mapping and can be extended for template-specific naming.
        
        Args:
            export_type: The export type from template configuration
            
        Returns:
            String filename for the export type
        """
        filename_map = {
            'crawl': 'crawl.csv',
            'weblog': 'weblog.csv', 
            'gsc': 'gsc.csv',
            'crawl_attributes': 'crawl.csv',
            'link_graph_edges': 'link_graph.csv',
            'gsc_data': 'gsc.csv',
    
        }
        
        if export_type not in filename_map:
            raise ValueError(f'Unknown export type: {export_type}')
            
        return filename_map[export_type]

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
            
        filename = self.get_filename_for_export_type(data_type)
        return f'{base_dir}/{filename}'
    
    async def get_deterministic_filepath_for_template_config(self, username, project_name, analysis_slug, template_config_key):
        """Generate a deterministic file path based on template configuration.
        
        This method resolves the template configuration to determine the appropriate
        export type and filename for caching.
        
        Args:
            username: Organization username
            project_name: Project name
            analysis_slug: Analysis slug
            template_config_key: Key from TEMPLATE_CONFIG (e.g., 'analysis', 'crawler')
            
        Returns:
            String path to the file location
        """
        export_type = self.get_export_type_for_template_config(template_config_key)
        return await self.get_deterministic_filepath(username, project_name, analysis_slug, export_type)

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
            return exists, file_info if exists else None
        except Exception:
            return False, None
    
    async def check_cached_file_for_template_config(self, username, project_name, analysis_slug, template_config_key):
        """Check if a cached file exists based on template configuration.
        
        This method resolves the template configuration to determine the appropriate
        export type and check for cached files.
        
        Args:
            username: Organization username
            project_name: Project name
            analysis_slug: Analysis slug
            template_config_key: Key from TEMPLATE_CONFIG (e.g., 'analysis', 'crawler')
            
        Returns:
            tuple: (exists: bool, file_info: dict|None)
        """
        try:
            filepath = await self.get_deterministic_filepath_for_template_config(username, project_name, analysis_slug, template_config_key)
            exists, file_info = await self.check_file_exists(filepath)
            return exists, file_info if exists else None
        except Exception:
            return False, None

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

        # Get centralized comment divider
        ui_constants = self.pipulate.get_ui_constants()
        comment_divider = ui_constants['CODE_FORMATTING']['COMMENT_DIVIDER']
        
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
from dotenv import load_dotenv

def load_api_token() -> str:
    \"\"\"Load the Botify API token from the .env file.\"\"\"
    try:
        load_dotenv()
        api_key = os.environ.get('BOTIFY_API_TOKEN')
        if not api_key:
            raise ValueError("BOTIFY_API_TOKEN not found in environment or .env file.")
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
        logger.info(f'Starting real GSC data export for {username}/{project_name}/{analysis_slug}')
        try:
            gsc_filepath = await self.get_deterministic_filepath(username, project_name, analysis_slug, 'gsc')
            file_exists, file_info = await self.check_file_exists(gsc_filepath)
            if file_exists:
                await self.message_queue.add(wand, f"✅ Using cached GSC data ({file_info['size']})", verbatim=True)
                check_result.update({'download_complete': True, 'download_info': {'has_file': True, 'file_path': gsc_filepath, 'timestamp': file_info['created'], 'size': file_info['size'], 'cached': True}})
                
                # Generate Python debugging code even for cached files
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                export_query = await self.build_exports(username, project_name, analysis_slug, data_type='gsc', start_date=start_date, end_date=end_date)
                _, _, python_command = self.generate_query_api_call(export_query['export_job_payload'], username, project_name)
                check_result['python_command'] = python_command
                
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
                logger.info(f"Submitting export job with payload: {json.dumps(export_query['export_job_payload'], indent=2)}")
                async with httpx.AsyncClient() as client:
                    response = await client.post(job_url, headers=headers, json=export_query['export_job_payload'], timeout=60.0)
                    logger.info(f'Export job submission response status: {response.status_code}')
                    try:
                        logger.info(f'Export job response: {json.dumps(response.json(), indent=2)}')
                    except:
                        logger.info(f'Could not parse response as JSON. Raw: {response.text[:500]}')
                    response.raise_for_status()
                    job_data = response.json()
                    job_url_path = job_data.get('job_url')
                    if not job_url_path:
                        raise ValueError('Failed to get job URL from response')
                    full_job_url = f'https://api.botify.com{job_url_path}'
                    logger.info(f'Got job URL: {full_job_url}')
                    await self.message_queue.add(wand, '✅ Export job created successfully!', verbatim=True)
            except Exception as e:
                logger.error(f'Error creating export job: {str(e)}')
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
            logger.error(f'Error in process_search_console_data: {e}')
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

        IMPORTANT: The weblog structure here is DIFFERENT from step_webogs_process!
        - build_exports creates: BQLv2 with periods in query.periods
        - step_webogs_process creates: BQLv1 with date_start/date_end at payload level

        This dual structure exists because:
        - build_exports follows modern BQLv2 patterns
        - step_webogs_process uses legacy BQLv1 patterns that actually work
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
            
            # 🔍 BABY STEP 2: Non-intrusive validation logging
            try:
                validation_result = await self.validate_template_fields(gsc_template, username, project_name, analysis_slug or 'unknown')
                if validation_result['success']:
                    fields_available = len(validation_result.get('valid_fields', []))
                    fields_total = len(validation_result.get('fields_in_template', []))
                    logger.info(f"🎯 TEMPLATE_VALIDATION: GSC template '{gsc_template}' - {fields_available}/{fields_total} fields available for {username}/{project_name}")
                else:
                    logger.warning(f"🚨 TEMPLATE_VALIDATION: GSC template '{gsc_template}' validation failed - {validation_result.get('error', 'Unknown error')}")
            except Exception as e:
                logger.debug(f"🔍 TEMPLATE_VALIDATION: GSC validation check failed (non-critical): {e}")
                # Continue normally - validation failure doesn't break existing functionality
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
            analysis_template = self.get_configured_template('analysis')
            template_query = self.apply_template(analysis_template, collection)
            
            # 🔍 BABY STEP 2: Non-intrusive validation logging
            try:
                validation_result = await self.validate_template_fields(analysis_template, username, project_name, analysis_slug)
                if validation_result['success']:
                    fields_available = len(validation_result.get('valid_fields', []))
                    fields_total = len(validation_result.get('fields_in_template', []))
                    logger.info(f"🎯 TEMPLATE_VALIDATION: Crawl template '{analysis_template}' - {fields_available}/{fields_total} fields available for {username}/{project_name}/{analysis_slug}")
                else:
                    logger.warning(f"🚨 TEMPLATE_VALIDATION: Crawl template '{analysis_template}' validation failed - {validation_result.get('error', 'Unknown error')}")
            except Exception as e:
                logger.debug(f"🔍 TEMPLATE_VALIDATION: Crawl validation check failed (non-critical): {e}")
                # Continue normally - validation failure doesn't break existing functionality

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
            template_info = self.QUERY_TEMPLATES.get(analysis_template, {})
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
        logger.info(poll_msg)
        await self.message_queue.add(self.pipulate, poll_msg, verbatim=True)

        while attempt < max_attempts:
            try:
                if attempt == 0:
                    poll_attempt_msg = f'{step_prefix}Poll attempt {attempt + 1}/{max_attempts} for job: {job_url}'
                    logger.info(poll_attempt_msg)
                    await self.message_queue.add(self.pipulate, poll_attempt_msg, verbatim=True)
                elif attempt > 0:
                    poll_attempt_msg = f'{step_prefix}Polling... (attempt {attempt + 1}/{max_attempts})'
                    logger.info(poll_attempt_msg)
                    await self.message_queue.add(self.pipulate, poll_attempt_msg, verbatim=True)

                if consecutive_network_errors >= 2 and job_id:
                    alternative_url = f'https://api.botify.com/v1/jobs/{job_id}'
                    if alternative_url != job_url:
                        url_switch_msg = f'{step_prefix}Switching to direct job ID URL: {alternative_url}'
                        logger.info(url_switch_msg)
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
                            logger.debug(f'Poll response: {json.dumps(response_json, indent=2)}')
                    except:
                        if attempt == 0 or status == 'DONE':
                            logger.debug(f'Could not parse response as JSON. Status: {response.status_code}, Raw: {response.text[:500]}')
                    if response.status_code == 401:
                        error_msg = f'{step_prefix}Authentication failed. Please check your API token.'
                        logger.error(error_msg)
                        await self.message_queue.add(self.pipulate, f'❌ {error_msg}', verbatim=True)
                        return (False, error_msg)
                    if response.status_code >= 400:
                        error_msg = f'{step_prefix}API error {response.status_code}: {response.text}'
                        logger.error(error_msg)
                        await self.message_queue.add(self.pipulate, f'❌ {error_msg}', verbatim=True)
                        return (False, error_msg)
                    job_data = response.json()
                    status = job_data.get('job_status')
                    if attempt == 0:
                        status_msg = f'{step_prefix}Poll attempt {attempt + 1}: status={status}'
                        logger.info(status_msg)
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
                        logger.info(f'{step_prefix}{success_msg}')
                        await self.message_queue.add(self.pipulate, f'✅ {success_msg}', verbatim=True)
                        return (True, {'download_url': results.get('download_url'), 'row_count': results.get('row_count'), 'file_size': results.get('file_size'), 'filename': results.get('filename'), 'expires_at': results.get('expires_at')})
                    if status == 'FAILED':
                        error_details = job_data.get('error', {})
                        error_message = error_details.get('message', 'Unknown error')
                        error_type = error_details.get('type', 'Unknown type')
                        error_msg = f'{step_prefix}Job failed with error type: {error_type}, message: {error_message}'
                        logger.error(error_msg)
                        await self.message_queue.add(self.pipulate, f'❌ {error_msg}', verbatim=True)
                        return (False, f'Export failed: {error_message} (Type: {error_type})')
                    attempt += 1
                    if attempt == 1:
                        wait_msg = f'{step_prefix}Job still processing.'
                    else:
                        wait_msg = f'{step_prefix}Still processing...'
                    logger.info(wait_msg)
                    await self.message_queue.add(self.pipulate, wait_msg, verbatim=True)
                    await asyncio.sleep(delay)
                    delay = min(int(delay * 1.5), 20)
            except (httpx.RequestError, socket.gaierror, socket.timeout) as e:
                consecutive_network_errors += 1
                error_msg = f'{step_prefix}Network error polling job status: {str(e)}'
                logger.error(error_msg)
                await self.message_queue.add(self.pipulate, f'❌ {error_msg}', verbatim=True)
                if job_id:
                    job_url = f'https://api.botify.com/v1/jobs/{job_id}'
                    retry_msg = f'{step_prefix}Retry with direct job ID URL: {job_url}'
                    logger.warning(retry_msg)
                    await self.message_queue.add(self.pipulate, retry_msg, verbatim=True)
                attempt += 1
                wait_msg = f'{step_prefix}Network error.'
                logger.info(wait_msg)
                await self.message_queue.add(self.pipulate, wait_msg, verbatim=True)
                await asyncio.sleep(delay)
                delay = min(int(delay * 2), 30)
            except Exception as e:
                error_msg = f'{step_prefix}Unexpected error in polling: {str(e)}'
                logger.error(error_msg)
                await self.message_queue.add(self.pipulate, f'❌ {error_msg}', verbatim=True)
                attempt += 1
                wait_msg = f'{step_prefix}Unexpected error.'
                logger.info(wait_msg)
                await self.message_queue.add(self.pipulate, wait_msg, verbatim=True)
                await asyncio.sleep(delay)
                delay = min(int(delay * 2), 30)
        max_attempts_msg = f'{step_prefix}Maximum polling attempts reached'
        logger.warning(max_attempts_msg)
        await self.message_queue.add(self.pipulate, f'⚠️ {max_attempts_msg}', verbatim=True)
        return (False, 'Maximum polling attempts reached. The export job may still complete in the background.')

    async def step_analysis_process(self, request, step_context=None):
        """Process the actual download after showing the progress indicator."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        # Use step_context if provided (for reusability), otherwise default to 'step_analysis'
        step_id = step_context or 'step_analysis'
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
        # Use different template based on step_context
        if step_context == 'step_crawler':
            active_analysis_template_key = self.get_configured_template('crawler')
        else:
            active_analysis_template_key = self.get_configured_template('analysis')
        active_template_details = self.QUERY_TEMPLATES.get(active_analysis_template_key, {})
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
                if step_context == 'step_crawler':
                    template_key = self.get_configured_template('crawler')
                else:
                    template_key = self.get_configured_template('analysis')
                template_query = self.apply_template(template_key, collection)

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
                if step_context == 'step_crawler':
                    template_key = self.get_configured_template('crawler')
                else:
                    template_key = self.get_configured_template('analysis')
                template_query = self.apply_template(template_key, collection)

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
                logger.info(f'Submitting crawl export job with payload: {json.dumps(export_query, indent=2)}')

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
                                logger.error(f'API error details: {error_detail}')
                            except Exception:
                                error_detail = response.text[:500]
                                logger.error(f'API error text: {error_detail}')
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
                                active_analysis_template_key = self.get_configured_template('analysis')
                                active_template_details = self.QUERY_TEMPLATES.get(active_analysis_template_key, {})
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
            logger.error(f'Error in step_analysis_process: {e}')
            return P(f'Error: {str(e)}', cls='text-invalid')

    async def step_webogs_process(self, request):
        """Process the web logs check and download if available."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_webogs'
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
            
            # Generate Python debugging code even when no web logs (for educational purposes)
            if not has_logs:
                try:
                    analysis_date_obj = datetime.strptime(analysis_slug, '%Y%m%d')
                except ValueError:
                    analysis_date_obj = datetime.now()
                date_end = analysis_date_obj.strftime('%Y-%m-%d')
                date_start = (analysis_date_obj - timedelta(days=30)).strftime('%Y-%m-%d')
                # Create example BQLv1 structure for web logs (even though project doesn't have them)
                export_query = {'job_type': 'logs_urls_export', 'payload': {'query': {'filters': {'field': 'crawls.google.count', 'predicate': 'gt', 'value': 0}, 'fields': ['url', 'crawls.google.count'], 'sort': [{'crawls.google.count': {'order': 'desc'}}]}, 'export_size': config.BOTIFY_API['WEBLOG_EXPORT_SIZE'], 'formatter': 'csv', 'connector': 'direct_download', 'formatter_config': {'print_header': True, 'print_delimiter': True}, 'extra_config': {'compression': 'zip'}, 'date_start': date_start, 'date_end': date_end, 'username': username, 'project': project_name}}
                # Generate Python command snippet (for educational debugging)
                _, _, python_command = self.generate_query_api_call(export_query, username, project_name)
                check_result['python_command'] = python_command
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
                    logger.info(f'Submitting logs export job with payload: {json.dumps(export_query, indent=2)}')

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
                                    logger.error(f'API error details: {error_detail}')
                                except Exception:
                                    error_detail = response.text[:500]
                                    logger.error(f'API error text: {error_detail}')
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
                                    logger.info(f'Successfully extracted gzip file to {logs_filepath}')
                                except gzip.BadGzipFile:
                                    try:
                                        with zipfile.ZipFile(compressed_path, 'r') as zip_ref:
                                            csv_files = [f for f in zip_ref.namelist() if f.endswith('.csv')]
                                            if not csv_files:
                                                raise ValueError('No CSV files found in the zip archive')
                                            with zip_ref.open(csv_files[0]) as source:
                                                with open(logs_filepath, 'wb') as target:
                                                    shutil.copyfileobj(source, target)
                                        logger.info(f'Successfully extracted zip file to {logs_filepath}')
                                    except zipfile.BadZipFile:
                                        shutil.copy(compressed_path, logs_filepath)
                                        logger.info(f"File doesn't appear to be compressed, copying directly to {logs_filepath}")
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

            # Standardize step data before creating action buttons (fixes regression)
            standardized_step_data = self._prepare_action_button_data(check_result, step_id, pipeline_id)
            action_buttons = self._create_action_buttons(standardized_step_data, step_id)

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
            logger.error(f'Error in step_webogs_process: {e}')
            return Div(P(f'Error: {str(e)}', cls='text-invalid'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)











    async def common_toggle(self, request):
        """Unified toggle method for all step widgets using configuration-driven approach."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = request.query_params.get('step_id')
        if not step_id or step_id not in self.TOGGLE_CONFIG:
            return Div("Invalid step ID for toggle.", style="color: red;")
        
        config = self.TOGGLE_CONFIG[step_id]
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        data_str = step_data.get(steps[self.steps_indices[step_id]].done, '')
        data_obj = json.loads(data_str) if data_str else {}
        
        state = wand.read_state(pipeline_id)
        widget_visible_key = f'{step_id}_widget_visible'
        is_visible = state.get(widget_visible_key, False)
        
        # 🚨 ANTI-REGRESSION: Always generate Python code (cached OR fresh downloads)
        python_command = data_obj.get('python_command', None)
        
        # If no Python code in step data, generate it for cached data consistency
        if not python_command or python_command == '# No Python code available for this step.':
            # Extract necessary parameters from step data or state
            username = data_obj.get('username', state.get('username', 'unknown'))
            project_name = data_obj.get('project', data_obj.get('project_name', state.get('project_name', 'unknown')))
            analysis_slug = data_obj.get('analysis_slug', state.get('analysis_slug', 'unknown'))
            
            # Generate Python code for this step context
            python_command = self._generate_python_code_for_cached_data(
                step_context=step_id,
                username=username,
                project_name=project_name,
                analysis_slug=analysis_slug
            )
        
        # Handle simple content case first
        if 'simple_content' in config:
            content_div = Pre(config['simple_content'], cls='code-block-container')
        else: # Handle complex data-driven content
            status_prefix = config.get('status_prefix', '')
            if 'error' in data_obj:
                status_text = f'{config["error_prefix"]}: {data_obj["error"]}'
                status_color = 'red'
            else:
                has_data = data_obj.get(config.get('status_field'), False)
                status_text = f'{status_prefix}{config["success_text"] if has_data else config["failure_text"]}'
                status_color = 'green' if has_data else 'orange'
            
            content_div = Div(
                P(f'Status: {status_text}', style=f'color: {status_color};'),
                H4('Python Command (for debugging):'),
                Pre(Code(python_command, cls='language-python'), cls='code-block-container'),
                Script(f"setTimeout(() => Prism.highlightAllUnder(document.getElementById('{step_id}_widget')), 100);")
            )

        # First time toggling, just show it
        if widget_visible_key not in state:
            state[widget_visible_key] = True
            wand.write_state(pipeline_id, state)
            return content_div

        # Subsequent toggles
        state[widget_visible_key] = not is_visible
        wand.write_state(pipeline_id, state)
        
        if is_visible: # if it was visible, now hide it
            content_div.attrs['style'] = 'display: none;'
        
        return content_div

    def _get_template_config_for_step_context(self, step_context):
        """Get template configuration key and fallbacks for a given step context.
        
        Args:
            step_context: The step context string (e.g., 'step_crawler', 'step_gsc')
            
        Returns:
            tuple: (template_config_key, fallback_export_type, fallback_suffix)
        """
        step_mappings = {
    
            'step_gsc': ('gsc', 'gsc_data', 'GSC Data'),
            'step_crawler': ('crawler', 'crawl_attributes', 'Basic Attributes'),
            'step_webogs': ('weblog', 'weblog', 'Web Logs'),  # Web logs not templated
        }
        
        # Return mapping or default to analysis (analysis step)
        return step_mappings.get(step_context, ('analysis', 'crawl_attributes', 'Data'))

    async def update_button_text(self, request):
        """Update button text dynamically based on selected analysis."""
        try:
            form = await request.form()
            analysis_slug = form.get('analysis_slug', '').strip()
            username = form.get('username', '').strip()
            project_name = form.get('project_name', '').strip()
            step_context = form.get('step_context', '').strip()  # NEW: Get which step is calling this
            
            if not all([analysis_slug, username, project_name]):
                # Return default button if missing parameters
                template_config_key, fallback_export_type, fallback_suffix = self._get_template_config_for_step_context(step_context)
                
                try:
                    active_template_key = self.get_configured_template(template_config_key)
                    active_template_details = self.QUERY_TEMPLATES.get(active_template_key, {})
                    button_suffix = active_template_details.get('button_label_suffix', fallback_suffix)
                except (ValueError, KeyError):
                    button_suffix = fallback_suffix
                    
                return Button(f'Download {button_suffix} ▸', type='submit', cls='mt-10px primary', id='submit-button',
                             **{'hx-on:click': 'this.setAttribute("aria-busy", "true"); this.textContent = "Processing..."'})
            
            # Determine template and export type based on step context
            template_config_key, fallback_export_type, fallback_suffix = self._get_template_config_for_step_context(step_context)
            
            try:
                export_type = self.get_export_type_for_template_config(template_config_key)
                active_template_key = self.get_configured_template(template_config_key)
                active_template_details = self.QUERY_TEMPLATES.get(active_template_key, {})
                button_suffix = active_template_details.get('button_label_suffix', fallback_suffix)
            except (ValueError, KeyError):
                # Fallback if template resolution fails
                export_type = fallback_export_type
                button_suffix = fallback_suffix
            
            # Check if files are cached for the selected analysis
            is_cached, file_info = await self.check_cached_file_for_template_config(username, project_name, analysis_slug, template_config_key)
            
            if is_cached and file_info:
                button_text = f'Use Cached {button_suffix} ({file_info["size"]}) ▸'
            else:
                button_text = f'Download {button_suffix} ▸'
                
            return Button(button_text, type='submit', cls='mt-10px primary', id='submit-button',
                         **{'hx-on:click': 'this.setAttribute("aria-busy", "true"); this.textContent = "Processing..."'})
        except Exception as e:
            logger.error(f"Error in update_button_text: {e}")
            # Return default button on error
            step_context = form.get('step_context', '') if 'form' in locals() else ''
            template_config_key, fallback_export_type, fallback_suffix = self._get_template_config_for_step_context(step_context)
            
            try:
                active_template_key = self.get_configured_template(template_config_key)
                active_template_details = self.QUERY_TEMPLATES.get(active_template_key, {})
                button_suffix = active_template_details.get('button_label_suffix', fallback_suffix)
            except (ValueError, KeyError):
                button_suffix = fallback_suffix
                
            return Button(f'Download {button_suffix} ▸', type='submit', cls='mt-10px primary', id='submit-button',
                         **{'hx-on:click': 'this.setAttribute("aria-busy", "true"); this.textContent = "Processing..."'})

    def _generate_python_code_for_cached_data(self, step_context, username, project_name, analysis_slug, export_type=None):
        """
        🚨 ANTI-REGRESSION GUARDIAN: Hide/Show Code Feature Protection
        =============================================================
        
        CRITICAL PROBLEM SOLVED: AI assistants keep breaking the "Hide/Show Code" 
        functionality because Python code is only generated during actual downloads,
        not when displaying cached data. This causes the feature to inconsistently 
        work, creating a whack-a-mole regression pattern.
        
        SYSTEMATIC SOLUTION: This method ensures Python code is ALWAYS available
        for the "Hide/Show Code" button, regardless of download vs cached workflow.
        
        🎯 Why This Method Exists:
        - Users expect to see Python code examples whether they downloaded fresh or used cached data
        - The code helps with Jupyter debugging and API understanding
        - Consistency is crucial for user experience and workflow reliability
        - Prevents AI from removing this feature during future refactoring
        
        Args:
            step_context: The step identifier ('step_crawler', 'step_webogs', 'step_gsc')
            username: Organization slug for API URLs
            project_name: Project name for API URLs  
            analysis_slug: Analysis identifier for the data
            export_type: Optional export type override
            
        Returns:
            str: Python code that recreates the equivalent API call for debugging
        """
        
        try:
            # Determine the template and export configuration
            template_config_key, fallback_export_type, fallback_suffix = self._get_template_config_for_step_context(step_context)
            
            if export_type is None:
                try:
                    export_type = self.get_export_type_for_template_config(template_config_key)
                except (ValueError, KeyError):
                    export_type = fallback_export_type
            
            # Handle web logs special case (BQLv1, non-templated)
            if step_context == 'step_webogs':
                # Create a mock BQLv1 payload for web logs (following actual BQLv1 structure)
                mock_payload = {
                    'job_type': 'logs_urls_export',
                    'payload': {
                        'date_start': '2024-01-01',  # BQLv1 structure - dates at payload level
                        'date_end': '2024-12-31',
                        'query': {
                            'dimensions': ['url', 'crawls.google.count'],
                            'metrics': [],
                            'filters': {
                                'field': 'crawls.google.count',
                                'predicate': 'gt',
                                'value': 0
                            }
                        }
                    }
                }
                
                # Generate the Python code using the weblog-specific method
                try:
                    # For BQLv1 (weblogs), generate_query_api_call returns (logs_url, query_payload, python_code)
                    logs_url, query_payload, python_code = self.generate_query_api_call(mock_payload, username, project_name, 100)
                    return python_code
                except Exception as e:
                    return f"# Error generating web logs Python code: {str(e)}"
            
            # Handle templated data types (crawler, gsc)
            else:
                try:
                    # Get the active template
                    active_template_key = self.get_configured_template(template_config_key)
                    template_details = self.QUERY_TEMPLATES.get(active_template_key, {})
                    
                    if not template_details:
                        return f"# Python code not available - template '{active_template_key}' not found"
                    
                    # Apply the template to create the query
                    applied_template = self.apply_template(active_template_key, collection=analysis_slug)
                    
                    # Create a mock jobs payload from the template
                    mock_payload = {
                        'job_type': 'export',
                        'payload': {
                            'query': {
                                'collections': [analysis_slug],
                                'query': applied_template
                            }
                        }
                    }
                    
                    # For GSC, add period information
                    if export_type == 'gsc_data':
                        mock_payload['payload']['query']['periods'] = [
                            {'start_date': '2024-01-01', 'end_date': '2024-12-31'}  # Placeholder
                        ]
                    
                    # Generate the Python code
                    try:
                        # For BQLv2 (crawler/gsc), generate_query_api_call returns (query_url, python_code)
                        query_url, python_code = self.generate_query_api_call(mock_payload, username, project_name, 100)
                        return python_code
                    except Exception as e:
                        return f"# Error generating BQLv2 Python code: {str(e)}"
                    
                except Exception as template_error:
                    return f"# Python code generation failed for {step_context}: {str(template_error)}"
                
        except Exception as e:
            # Fallback for any unexpected errors
            return f"# Python code generation error for {step_context}: {str(e)}"

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

        LEGACY BQLv1 Structure (used by step_webogs_process):
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
        1. The actual workflow (step_webogs_process) uses BQLv1 structure
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

        # CRITICAL: Check payload level FIRST - this is the actual BQLv1 structure used by step_webogs_process
        # The step_webogs_process method generates payloads with 'date_start'/'date_end' at payload level
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

    def _prepare_action_button_data(self, raw_step_data, step_id, pipeline_id):
        """Standardize step data for action buttons across all steps.
        
        This method ensures consistent data structure regardless of which step is calling it.
        Fixes the whack-a-mole regression pattern by centralizing data preparation.
        """
        # Start with the raw data
        standardized_data = raw_step_data.copy() if raw_step_data else {}
        
        # Ensure we have the essential project context
        if not standardized_data.get('username') or not standardized_data.get('project_name') or not standardized_data.get('analysis_slug'):
            # Try to get missing data from pipeline state
            try:
                # Get project data from step_project
                project_step_data = self.pipulate.get_step_data(pipeline_id, 'step_project', {})
                project_data_str = project_step_data.get('botify_project', '')
                if project_data_str:
                    project_data = json.loads(project_data_str)
                    if not standardized_data.get('username'):
                        standardized_data['username'] = project_data.get('username', '')
                    if not standardized_data.get('project_name'):
                        standardized_data['project_name'] = project_data.get('project_name', '')
                
                # Get analysis slug from step_analysis if missing
                if not standardized_data.get('analysis_slug'):
                    analysis_step_data = self.pipulate.get_step_data(pipeline_id, 'step_analysis', {})
                    if analysis_step_data:
                        # Try multiple possible keys
                        analysis_data_str = analysis_step_data.get('analysis_selection', '')
                        if analysis_data_str:
                            try:
                                analysis_data = json.loads(analysis_data_str)
                                standardized_data['analysis_slug'] = analysis_data.get('analysis_slug', '')
                            except (json.JSONDecodeError, AttributeError):
                                pass
                        
                        # If that didn't work, try other keys
                        if not standardized_data.get('analysis_slug'):
                            for key, value in analysis_step_data.items():
                                if isinstance(value, str):
                                    try:
                                        data = json.loads(value)
                                        if isinstance(data, dict) and 'analysis_slug' in data:
                                            standardized_data['analysis_slug'] = data['analysis_slug']
                                            break
                                    except (json.JSONDecodeError, AttributeError):
                                        continue
            except Exception as e:
                logger.debug(f"Error getting pipeline context for action buttons: {e}")
        
        # Ensure download_complete flag is set if not present
        if 'download_complete' not in standardized_data:
            standardized_data['download_complete'] = raw_step_data and raw_step_data.get('has_crawler', False) or raw_step_data.get('has_file', False)
        
        return standardized_data

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
        if step_id == 'step_analysis':
            # For crawl data, determine filename based on active template's export type
            active_analysis_template_key = self.get_configured_template('analysis')
            active_template_details = self.QUERY_TEMPLATES.get(active_analysis_template_key, {})
            export_type = active_template_details.get('export_type', 'crawl_attributes')

            # Use the same mapping as get_deterministic_filepath
            filename_mapping = {
                'crawl_attributes': 'crawl.csv',
                'link_graph_edges': 'link_graph.csv'
            }
            expected_filename = filename_mapping.get(export_type, 'crawl.csv')
        elif step_id == 'step_crawler':
            # For basic crawl data, determine filename based on crawler template's export type
            active_crawler_template_key = self.get_configured_template('crawler')
            active_template_details = self.QUERY_TEMPLATES.get(active_crawler_template_key, {})
            export_type = active_template_details.get('export_type', 'crawl_attributes')

            # Use the same mapping as get_deterministic_filepath
            filename_mapping = {
                'crawl_attributes': 'crawl.csv',
                'link_graph_edges': 'link_graph.csv'
            }
            expected_filename = filename_mapping.get(export_type, 'crawl.csv')
        elif step_id == 'step_webogs':
            expected_filename = 'weblog.csv'
        elif step_id == 'step_gsc':
            expected_filename = 'gsc.csv'



        # Check if download was successful and try to find the file
        if download_complete and expected_filename and username and project_name and analysis_slug:
            try:
                # Construct the expected file path
                expected_file_path = Path.cwd() / 'downloads' / self.APP_NAME / username / project_name / analysis_slug / expected_filename

                # Check if file actually exists
                if expected_file_path.exists():
                    downloads_base = Path.cwd() / 'downloads'
                    path_for_url = expected_file_path.resolve().relative_to(downloads_base.resolve())
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
                        path_for_url = file_path_obj.resolve().relative_to(downloads_base.resolve())
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

    async def discover_fields_endpoint(self, request):
        """
        🔍 FIELD DISCOVERY ENDPOINT
        
        Simple endpoint to discover available fields for a Botify project analysis.
        Call via: /trifecta/discover-fields/username/project/analysis
        
        Returns JSON with all available dimensions and metrics.
        If cached analysis_advanced.json file doesn't exist, it will be automatically 
        generated using the same method as the Trifecta workflow.
        """
        username = request.path_params['username']
        project = request.path_params['project'] 
        analysis = request.path_params['analysis']
        
        try:
            # First, try to use the existing cached file parser to extract fields
            result = await self.extract_available_fields_from_advanced_export(
                username, project, analysis, export_group=None
            )
            
            # If cache doesn't exist, generate it automatically
            if not result['success']:
                logger.info(f"🔍 FINDER_TOKEN: CACHE_MISS - No cached data for {username}/{project}/{analysis}, generating cache...")
                
                # Get API token
                api_token = self.read_api_token()
                if not api_token:
                    return JSONResponse({
                        'error': 'No Botify API token found',
                        'message': 'Please run the Configuration app (Step 4) to securely store your API token in the .env vault.'
                    }, status_code=401)
                
                # Generate the cache using the same method as Trifecta workflow
                success, cache_message, cache_filepath = await self.save_advanced_export_to_json(
                    username, project, analysis, api_token
                )
                
                if not success:
                    return JSONResponse({
                        'error': 'Failed to generate cache',
                        'message': cache_message,
                        'hint': 'Check that the username, project, and analysis are correct and accessible'
                    }, status_code=400)
                
                logger.info(f"🔍 FINDER_TOKEN: CACHE_GENERATED - Successfully cached analysis data: {cache_message}")
                
                # Now try again to extract fields from the newly cached data
                result = await self.extract_available_fields_from_advanced_export(
                    username, project, analysis, export_group=None
                )
                
                if not result['success']:
                    return JSONResponse({
                        'error': 'Field extraction failed after cache generation',
                        'message': result['message']
                    }, status_code=500)
            
            # Transform the extracted fields into the expected format
            available_fields = {
                'dimensions': result['fields'],  # All unique fields as dimensions
                'metrics': [],  # No metrics in advanced export structure
                'collections': [export['id'] for export in result['available_exports']]  # Export IDs as collections
            }
            
            # Add detailed export information
            export_details = {
                export['id']: {
                    'name': export.get('name', export['id']),
                    'group': export.get('group', 'unknown'),
                    'field_count': export['field_count'],
                    'fields': export['fields']
                }
                for export in result['available_exports']
            }
            
            # Determine source for transparency
            cache_message = locals().get('cache_message', '')
            source = 'freshly_generated_cache' if cache_message and 'already cached' not in cache_message else 'cached_analysis_advanced.json'
            
            # Log the discovery for debugging
            logger.info(f"🔍 FINDER_TOKEN: FIELD_DISCOVERY - Discovered {len(available_fields['dimensions'])} dimensions, {len(available_fields['metrics'])} metrics for {username}/{project}/{analysis}")
            
            return JSONResponse({
                'project': f'{username}/{project}',
                'analysis': analysis,
                'discovered_at': datetime.now().isoformat(),
                'source': source,
                'available_fields': available_fields,
                'field_count': {
                    'dimensions': len(available_fields['dimensions']),
                    'metrics': len(available_fields['metrics']),
                    'collections': len(available_fields['collections'])
                },
                'export_details': export_details,
                'summary': result['message'],
                'cache_info': locals().get('cache_message', 'Used existing cache')
            })
            
        except Exception as e:
            logger.error(f"Field discovery failed for {username}/{project}/{analysis}: {e}")
            return JSONResponse({
                'error': 'Field discovery failed',
                'details': str(e)
            }, status_code=500)

    async def validate_template_fields(self, template_key, username, project, analysis):
        """
        🔍 EXPLICIT FIELD VALIDATION (Baby Step 12 - Major Simplification)
        
        Validates template fields against discovered fields using EXPLICIT field paths.
        This method was simplified to eliminate brittle field name extraction and mapping.
        
        🎯 EXPLICITNESS OVER AMBIGUITY: 
        - Template fields are kept exactly as written (e.g., '{collection}.metadata.title.content')
        - Only {collection} prefix is normalized for comparison with discovered fields
        - Zero hidden mapping logic - what you see is what gets validated
        
        🚨 ANTI-REGRESSION PROTECTION:
        - Removed complex .split() logic that caused field name ambiguity
        - Eliminated "simplified" field extraction that introduced mapping errors
        - Preserved exact template field paths for complete transparency
        
        Args:
            template_key: Key from QUERY_TEMPLATES
            username, project, analysis: Botify project identifiers
            
        Returns:
            dict: Validation results with explicit field status
                - fields_in_template: Exact field paths from template
                - valid_fields: Template fields found in discovered fields
                - missing_fields: Template fields not found
                - validation_summary: X/Y fields available ratio
        """
        # Get the template
        if template_key not in self.QUERY_TEMPLATES:
            return {
                'success': False,
                'error': f"Unknown template: {template_key}",
                'template_name': None,
                'fields_in_template': [],
                'available_fields': [],
                'valid_fields': [],
                'missing_fields': []
            }
        
        template = self.QUERY_TEMPLATES[template_key]
        template_name = template.get('name', template_key)
        
        # Get template fields - USE EXACT FIELD PATHS (Baby Step 12 Simplification)
        query = template.get('query', {})
        dimensions = query.get('dimensions', [])
        
        # 🎯 EXPLICITNESS OVER AMBIGUITY: Use full field paths with {collection} placeholders
        # This eliminates brittleness from field name extraction and mapping logic.
        # Developer explicitness is preferred over user-friendly shortcuts in template definitions.
        template_fields = []
        for dim in dimensions:
            # Keep the full field path exactly as defined in the template
            # This makes validation unambiguous and matches exactly what's sent to the API
            template_fields.append(dim)
        
        # Discover available fields
        try:
            result = await self.extract_available_fields_from_advanced_export(
                username, project, analysis, export_group=None
            )
            
            if result['success']:
                available_fields = result['fields']
                
                # Check which template fields are available
                # Template fields may have {collection} placeholders, so we need to normalize for comparison
                valid_fields = []
                missing_fields = []
                
                for template_field in template_fields:
                    # For comparison purposes, remove {collection}. prefix to match against discovered fields
                    comparison_field = template_field
                    if '{collection}.' in template_field:
                        comparison_field = template_field.replace('{collection}.', '')
                    
                    # Check if this normalized field exists in the discovered fields
                    if comparison_field in available_fields:
                        valid_fields.append(template_field)  # Keep original template field format
                    else:
                        missing_fields.append(template_field)  # Keep original template field format
                
                return {
                    'success': True,
                    'template_name': template_name,
                    'template_key': template_key,
                    'fields_in_template': template_fields,
                    'available_fields': available_fields,
                    'valid_fields': valid_fields,
                    'missing_fields': missing_fields,
                    'validation_summary': f"{len(valid_fields)}/{len(template_fields)} fields available"
                }
            else:
                return {
                    'success': False,
                    'error': f"Field discovery failed: {result['message']}",
                    'template_name': template_name,
                    'fields_in_template': template_fields,
                    'available_fields': [],
                    'valid_fields': [],
                    'missing_fields': template_fields
                }
                
        except Exception as e:
            logger.error(f"Template validation failed: {e}")
            return {
                'success': False,
                'error': f"Validation error: {str(e)}",
                'template_name': template_name,
                'fields_in_template': template_fields,
                'available_fields': [],
                'valid_fields': [],
                'missing_fields': template_fields
            }


    # --- START_STEP_BUNDLE: step_01 ---
    async def step_01(self, request):
        """Handles GET request for Placeholder Step 1 (Edit Me)."""
        pip, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, self.app_name
        step_id = "step_01"
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        # Determine next_step_id dynamically based on runtime position in steps list
        next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
        pipeline_id = db.get("pipeline_id", "unknown")
        state = pip.read_state(pipeline_id)
        step_data = pip.get_step_data(pipeline_id, step_id, {})
        current_value = step_data.get(step.done, "") # 'step.done' will be like 'placeholder_01'
        finalize_data = pip.get_step_data(pipeline_id, "finalize", {})
    
        if "finalized" in finalize_data and current_value:
            pip.append_to_history(f"[WIDGET CONTENT] {step.show} (Finalized):\n{current_value}")
            return Div(
                Card(H3(f"🔒 {step.show}: Completed")),
                Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
                id=step_id
            )
        elif current_value and state.get("_revert_target") != step_id:
            pip.append_to_history(f"[WIDGET CONTENT] {step.show} (Completed):\n{current_value}")
            return Div(
                pip.display_revert_header(step_id=step_id, app_name=app_name, message=f"{step.show}: Complete", steps=steps),
                Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
                id=step_id
            )
        else:
            pip.append_to_history(f"[WIDGET STATE] {step.show}: Showing input form")
            await self.message_queue.add(pip, self.step_messages[step_id]["input"], verbatim=True)
            return Div(
                Card(
                    H3(f"{step.show}"),
                    P("This is a new placeholder step. Customize its input form as needed. Click Proceed to continue."),
                    Form(
                        # Example: Hidden input to submit something for the placeholder
                        Input(type="hidden", name=step.done, value="Placeholder Value for Placeholder Step 1 (Edit Me)"),
                        Button("Next ▸", type="submit", cls="primary"),
                        hx_post=f"/{app_name}/{step_id}_submit", hx_target=f"#{step_id}"
                    )
                ),
                Div(id=next_step_id), # Placeholder for next step, no trigger here
                id=step_id
            )


    async def step_01_submit(self, request):
        """Process the submission for Placeholder Step 1 (Edit Me)."""
        pip, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, self.app_name
        step_id = "step_01"
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
        pipeline_id = db.get("pipeline_id", "unknown")
        
        form_data = await request.form()
        # For a placeholder, get value from the hidden input or use a default
        value_to_save = form_data.get(step.done, f"Default value for {step.show}") 
        await pip.set_step_data(pipeline_id, step_id, value_to_save, steps)
        
        pip.append_to_history(f"[WIDGET CONTENT] {step.show}:\n{value_to_save}")
        pip.append_to_history(f"[WIDGET STATE] {step.show}: Step completed")
        
        await self.message_queue.add(pip, f"{step.show} complete.", verbatim=True)
        
        return Div(
            pip.display_revert_header(step_id=step_id, app_name=app_name, message=f"{step.show}: Complete", steps=steps),
            Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
            id=step_id
        )
    # --- END_STEP_BUNDLE: step_01 ---


    # --- STEP_METHODS_INSERTION_POINT ---

    # --- START_PARAMETER_BUSTER_TRANSPLANT_BUNDLE ---

    async def step_02b(self, request):
        """Handles GET request for Node Attributes (Crawl Basic) download."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_02b'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        analysis_result_str = step_data.get(step.done, '')
        analysis_result = json.loads(analysis_result_str) if analysis_result_str else {}
        
        # Get analysis slug from step_02 (we need this to know which analysis to use)
        prev_step_id = 'step_analysis'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('analysis_selection', '')
        if not prev_data_str:
            return P('Error: Analysis data not found. Please complete step 2 first.', cls='text-invalid')
        
        prev_analysis_data = json.loads(prev_data_str)
        analysis_slug = prev_analysis_data.get('analysis_slug', '')
        project_name = prev_analysis_data.get('project', '')
        username = prev_analysis_data.get('username', '')
        
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})

        # Phase 1: Finalized view (locked)
        if 'finalized' in finalize_data and analysis_result:
            return Div(
                Card(H3(f'🔒 {step.show}'), 
                     Div(P(f'Project: {project_name}', style='margin-bottom: 5px;'), 
                         P(f'Node Attributes Downloaded: {analysis_slug}', style='font-weight: bold;'), 
                         cls='custom-card-padding-bg')),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        
        # Phase 2: Completed view (revertible)
        elif analysis_result and state.get('_revert_target') != step_id:
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
                    Pre(f'Node attributes downloaded for: {analysis_slug}', cls='code-block-container', style='display: none;'),
                    id=f'{step_id}_widget'
                )
            )
            return Div(
                wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: {analysis_slug}', widget=widget, steps=steps),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        
        # Phase 3: Input view
        else:
            # Get "Crawl Basic" template details
            basic_template_details = self.QUERY_TEMPLATES.get('Crawl Basic', {})
            template_name = basic_template_details.get('name', 'Crawl Basic')
            user_message = basic_template_details.get('user_message', 'This will download basic crawl data.')
            button_suffix = basic_template_details.get('button_label_suffix', 'Basic Attributes')
            
            # Check for cached file using "crawl_attributes" export type
            is_cached = False
            if analysis_slug:
                is_cached = await self.check_cached_file_for_button_text(username, project_name, analysis_slug, 'crawl_attributes')
            
            button_text = f'Use Cached {button_suffix} ▸' if is_cached else f'Download {button_suffix} ▸'
            
            await self.message_queue.add(wand, f'📄 Ready to download node attributes for analysis {analysis_slug}', verbatim=True)
            
            return Div(
                Card(
                    H3(f'{step.show}'),
                    P(f"Download node attributes for analysis '{analysis_slug}'"),
                    P(f'Organization: {username}', cls='text-secondary'),
                    P(user_message, cls='text-muted', style='font-style: italic; margin-top: 10px;'),
                    Form(
                        Div(
                            Button(button_text, type='submit', name='action', value='download', cls='mt-10px primary', **{'hx-on:click': 'this.setAttribute("aria-busy", "true"); this.textContent = "Processing..."'}),
                            Button(self.ui['BUTTON_LABELS']['SKIP_STEP'], type='submit', name='action', value='skip', cls='mt-10px secondary outline', style=self.ui['BUTTON_STYLES']['SKIP_BUTTON_STYLE']) if self.FEATURES_CONFIG.get('enable_skip_buttons', False) else None,
                            style=self.ui['BUTTON_STYLES']['BUTTON_ROW']
                        ),
                        hx_post=f'/{app_name}/{step_id}_submit',
                        hx_target=f'#{step_id}'
                    )
                ),
                Div(id=next_step_id),  # Empty placeholder, no trigger yet
                id=step_id
            )

    async def step_02b_submit(self, request):
        """Process the Node Attributes (Crawl Basic) download submission."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_02b'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')

        # Check if user clicked skip button
        form = await request.form()
        action = form.get('action', 'download')  # Default to download for backward compatibility

        if action == 'skip':
            # Handle skip action - create fake completion data and proceed to next step
            await self.message_queue.add(wand, f"⏭️ Skipping Node Attributes download...", verbatim=True)

            # Create skip data that indicates step was skipped
            skip_result = {
                'download_complete': False,
                'skipped': True,
                'skip_reason': 'User chose to skip node attributes download',
                'file_path': None,
                'python_command': '',
                'export_type': 'crawl_attributes',
                'template_used': 'Crawl Basic'
            }

            await wand.set_step_data(pipeline_id, step_id, json.dumps(skip_result), steps)
            await self.message_queue.add(wand, f"⏭️ Node Attributes step skipped. Proceeding to next step.", verbatim=True)

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
        # Get analysis data from step_02
        prev_step_id = 'step_analysis'
        prev_step_data = wand.get_step_data(pipeline_id, prev_step_id, {})
        prev_data_str = prev_step_data.get('analysis_selection', '')
        if not prev_data_str:
            return P('Error: Analysis data not found. Please complete step 2 first.', cls='text-invalid')
        
        prev_analysis_data = json.loads(prev_data_str)
        analysis_slug = prev_analysis_data.get('analysis_slug', '')
        project_name = prev_analysis_data.get('project', '')
        username = prev_analysis_data.get('username', '')
        
        if not all([analysis_slug, username, project_name]):
            return P('Error: Missing required analysis data', cls='text-invalid')
        
        await self.message_queue.add(wand, f'📊 Starting node attributes download for {analysis_slug}...', verbatim=True)
        
        # Create analysis result for step_02b using Crawl Basic template
        analysis_result = {
            'analysis_slug': analysis_slug,
            'project': project_name,
            'username': username,
            'timestamp': datetime.now().isoformat(),
            'download_started': True,
            'export_type': 'crawl_attributes',  # Always use crawl_attributes for basic data
            'template_used': 'Crawl Basic'
        }
        
        analysis_result_str = json.dumps(analysis_result)
        await wand.set_step_data(pipeline_id, step_id, analysis_result_str, steps)
        
        return Card(
            H3(f'{step.show}'),
            P(f"Downloading node attributes for analysis '{analysis_slug}'..."),
            Progress(style='margin-top: 10px;'),
            Script(f"""
                setTimeout(function() {{
                    htmx.ajax('POST', '/{app_name}/step_02b_process', {{
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

    async def step_02b_process(self, request):
        """Process the actual Crawl Basic download after showing the progress indicator."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_02b'
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
        
        # Always use "Crawl Basic" template and "crawl_attributes" export type
        basic_template_details = self.QUERY_TEMPLATES.get('Crawl Basic', {})
        export_type = 'crawl_attributes'
        
        try:
            crawl_filepath = await self.get_deterministic_filepath(username, project_name, analysis_slug, export_type)
            file_exists, file_info = await self.check_file_exists(crawl_filepath)
            
            if file_exists:
                await self.message_queue.add(wand, f"✅ Using cached node attributes ({file_info['size']})", verbatim=True)
                analysis_result.update({
                    'download_complete': True,
                    'download_info': {
                        'has_file': True,
                        'file_path': crawl_filepath,
                        'timestamp': file_info['created'],
                        'size': file_info['size'],
                        'cached': True
                    }
                })
                
                # Generate Python debugging code even for cached files
                try:
                    analysis_date_obj = datetime.strptime(analysis_slug, '%Y%m%d')
                except ValueError:
                    analysis_date_obj = datetime.now()
                
                collection = f'crawl.{analysis_slug}'
                template_query = self.apply_template('Crawl Basic', collection)
                
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
                
                _, _, python_command = self.generate_query_api_call(export_query, username, project_name)
                analysis_result['python_command'] = python_command
                
            else:
                await self.message_queue.add(wand, '🔄 Initiating node attributes export...', verbatim=True)
                api_token = self.read_api_token()
                if not api_token:
                    raise ValueError('Cannot read API token')
                
                collection = f'crawl.{analysis_slug}'
                template_query = self.apply_template('Crawl Basic', collection)
                
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
                logging.info(f'Submitting node attributes export job with payload: {json.dumps(export_query, indent=2)}')
                
                # Generate Python command snippet
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
                        await self.message_queue.add(wand, '✅ Node attributes export job created successfully!', verbatim=True)
                        await self.message_queue.add(wand, '🔄 Polling for export completion...', verbatim=True)
                        
                    except httpx.HTTPStatusError as e:
                        error_message = f'Export request failed: HTTP {e.response.status_code}'
                        await self.message_queue.add(wand, f'❌ {error_message}', verbatim=True)
                        analysis_result.update({
                            'download_complete': False,
                            'error': error_message,
                            'download_info': {
                                'has_file': False,
                                'error': error_message,
                                'timestamp': datetime.now().isoformat()
                            }
                        })
                        full_job_url = None
                        
                    except Exception as e:
                        error_message = f'Export request failed: {str(e)}'
                        await self.message_queue.add(wand, f'❌ {error_message}', verbatim=True)
                        analysis_result.update({
                            'download_complete': False,
                            'error': error_message,
                            'download_info': {
                                'has_file': False,
                                'error': error_message,
                                'timestamp': datetime.now().isoformat()
                            }
                        })
                        full_job_url = None
                
                if full_job_url:
                    success, result = await self.poll_job_status(full_job_url, api_token, step_context="export")
                    if not success:
                        error_message = isinstance(result, str) and result or 'Export job failed'
                        await self.message_queue.add(wand, f'❌ Export failed: {error_message}', verbatim=True)
                        
                        detailed_error = await self._diagnose_query_endpoint_error(export_query, username, project_name, api_token)
                        if detailed_error:
                            error_message = f"{error_message} | Detailed diagnosis: {detailed_error}"
                            await self.message_queue.add(wand, f'🔍 Detailed error diagnosis: {detailed_error}', verbatim=True)
                        
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
                            await self.message_queue.add(wand, '🔄 Downloading node attributes...', verbatim=True)
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
                                
                                # Set proper column names for Crawl Basic data
                                df = pd.read_csv(crawl_filepath)
                                if len(df.columns) >= 7:
                                    df.columns = ['URL', 'HTTP Code', 'Page Title', 'Page Type', 'Is Compliant', 'Canonical URL', 'In Sitemap'][:len(df.columns)]
                                else:
                                    # Fallback for unexpected column count
                                    df.columns = [f'Column_{i+1}' for i in range(len(df.columns))]
                                
                                df.to_csv(crawl_filepath, index=False)
                                await self.message_queue.add(wand, f'✅ Node attributes data saved with {len(df):,} rows', verbatim=True)
                                
                                analysis_result.update({
                                    'download_complete': True,
                                    'download_info': {
                                        'has_file': True,
                                        'file_path': crawl_filepath,
                                        'timestamp': file_info['created'],
                                        'size': file_info['size'],
                                        'cached': False,
                                        'row_count': len(df)
                                    }
                                })
                                
                            except Exception as e:
                                error_message = f'Download failed: {str(e)}'
                                await self.message_queue.add(wand, f'❌ {error_message}', verbatim=True)
                                analysis_result.update({
                                    'download_complete': False,
                                    'error': error_message,
                                    'download_info': {
                                        'has_file': False,
                                        'error': error_message,
                                        'timestamp': datetime.now().isoformat()
                                    }
                                })
            
            # Update step data with final result
            analysis_result_str = json.dumps(analysis_result)
            await wand.set_step_data(pipeline_id, step_id, analysis_result_str, steps)
            
        except Exception as e:
            error_message = f'Unexpected error in step_02b_process: {str(e)}'
            logging.exception(error_message)
            await self.message_queue.add(wand, f'❌ {error_message}', verbatim=True)
            analysis_result.update({
                'download_complete': False,
                'error': error_message,
                'download_info': {
                    'has_file': False,
                    'error': error_message,
                    'timestamp': datetime.now().isoformat()
                }
            })
            analysis_result_str = json.dumps(analysis_result)
            await wand.set_step_data(pipeline_id, step_id, analysis_result_str, steps)
        
        # Return completed view with action buttons
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
                Pre(f'Node attributes downloaded for: {analysis_slug}', cls='code-block-container', style='display: none;'),
                id=f'{step_id}_widget'
            )
        )
        
        return Div(
            wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: {analysis_slug}', widget=widget, steps=steps),
            Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
            id=step_id
        )

    async def step_05(self, request):
        """Handles GET request for the Visualization Preparation step."""
        wand, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, self.app_name
        step_id = "step_05"
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = 'finalize'
        pipeline_id = db.get("pipeline_id", "unknown")
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        
        # Check if the visualization is already prepared
        viz_result_str = step_data.get(step.done, '')
        viz_result = json.loads(viz_result_str) if viz_result_str else {}
        viz_url = viz_result.get('visualization_url')
        
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and viz_url:
            return Div(
                Card(
                    H3(f"🔒 {step.show}"),
                    A("Open Visualization", href=viz_url, target="_blank", role="button", cls=self.ui['BUTTON_STYLES']['PRIMARY'])
                ),
                Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
                id=step_id
            )
        elif viz_url and state.get("_revert_target") != step_id:
            widget = Div(
                A("🚀 Open Visualization in New Tab", href=viz_url, target="_blank", role="button", cls=self.ui['BUTTON_STYLES']['PRIMARY'])
            )
            return Div(
                wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f"{step.show}: Link generated!", widget=widget, steps=steps),
                Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
                id=step_id
            )
        else:
            # Show the button to start the process
            await self.message_queue.add(wand, self.step_messages[step_id]["input"], verbatim=True)
            return Div(
                Card(
                    H3(f"{step.show}"),
                    P("This step will process the downloaded data into Cosmograph-compatible CSVs and generate a visualization link."),
                    Form(
                        Button("Prepare & Visualize ▸", type="submit", cls="primary", **{'hx-on:click': 'this.setAttribute("aria-busy", "true")'}),
                        hx_post=f"/{app_name}/{step_id}_submit", hx_target=f"#{step_id}"
                    )
                ),
                Div(id=next_step_id),
                id=step_id
            )

    async def step_05_submit(self, request):
        """Process the submission for the Visualization Preparation step."""
        wand, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, self.app_name
        step_id = "step_05"
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = db.get("pipeline_id", "unknown")

        return Card(
            H3(f'{step.show}'),
            P("Processing data and preparing visualization... This may take a moment."),
            Progress(style='margin-top: 10px;'),
            Script(f"""
                setTimeout(function() {{
                    htmx.ajax('POST', '/{app_name}/step_05_process', {{
                        target: '#{step_id}',
                        values: {{ 'pipeline_id': '{pipeline_id}' }}
                    }});
                }}, 500);
            """),
            id=step_id
        )

    async def step_05_process(self, request):
        """Process downloaded data into Cosmograph-compatible format and generate visualization URL."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_05'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        form = await request.form()
        pipeline_id = form.get('pipeline_id', 'unknown')
        
        # Load project and analysis data
        project_data = wand.get_step_data(pipeline_id, 'step_01', {}).get('botify_project', '{}')
        analysis_data = wand.get_step_data(pipeline_id, 'step_02', {}).get('analysis_selection', '{}')
        
        try:
            project_info = json.loads(project_data)
            analysis_info = json.loads(analysis_data)
        except json.JSONDecodeError:
            await self.message_queue.add(wand, '❌ Error: Could not load project or analysis data', verbatim=True)
            return P('Error: Could not load project or analysis data', cls='text-invalid')
        
        username = project_info.get('username')
        project_name = project_info.get('project_name')
        analysis_slug = analysis_info.get('analysis_slug')
        
        if not all([username, project_name, analysis_slug]):
            await self.message_queue.add(wand, '❌ Error: Missing required project information', verbatim=True)
            return P('Error: Missing required project information', cls='text-invalid')
        
        try:
            await self.message_queue.add(wand, '🔄 Processing data for visualization...', verbatim=True)
            
            # Get data directory
            data_dir = await self.get_deterministic_filepath(username, project_name, analysis_slug)
            data_path = Path(data_dir)
            
            # Check for required files
            link_graph_file = data_path / 'link_graph.csv'
            gsc_file = data_path / 'gsc.csv'
            weblog_file = data_path / 'weblog.csv'
            
            if not link_graph_file.exists():
                await self.message_queue.add(wand, '❌ Error: Link graph data not found. Please complete Step 2 first.', verbatim=True)
                return P('Error: Link graph data not found. Please complete Step 2 first.', cls='text-invalid')
            
            await self.message_queue.add(wand, '📊 Loading link graph data...', verbatim=True)
            
            # Load link graph data
            try:
                link_graph_df = pd.read_csv(link_graph_file)
                await self.message_queue.add(wand, f'✅ Loaded {len(link_graph_df):,} link graph rows', verbatim=True)
                
                # Check for link graph columns - handle both BQL field names and simplified export names
                columns = list(link_graph_df.columns)
                
                # Try to identify source and target columns
                source_col = None
                target_col = None
                
                # First try the BQL field names
                bql_source = f'{analysis_slug}.url'
                bql_target = f'{analysis_slug}.outlinks_internal.graph.url'
                
                if bql_source in columns and bql_target in columns:
                    source_col = bql_source
                    target_col = bql_target
                # Then try common export column names
                elif 'Source URL' in columns and 'Target URL' in columns:
                    source_col = 'Source URL'
                    target_col = 'Target URL'
                elif 'source' in columns and 'target' in columns:
                    source_col = 'source'
                    target_col = 'target'
                else:
                    await self.message_queue.add(wand, f'❌ Error: Could not identify source/target columns in link graph. Found: {columns}', verbatim=True)
                    return P('Error: Could not identify source/target columns in link graph data', cls='text-invalid')
                
                await self.message_queue.add(wand, f'✅ Using columns: {source_col} → {target_col}', verbatim=True)
                
            except Exception as e:
                await self.message_queue.add(wand, f'❌ Error loading link graph data: {str(e)}', verbatim=True)
                return P(f'Error loading link graph data: {str(e)}', cls='text-invalid')
            
            await self.message_queue.add(wand, '🔗 Creating edge list for Cosmograph...', verbatim=True)
            
            # Create cosmo_links.csv (edge list) using the detected column names
            # Filter out rows with missing source or target URLs
            edges_df = link_graph_df[[source_col, target_col]].dropna()
            edges_df.columns = ['source', 'target']  # Rename for Cosmograph compatibility
            
            # Remove self-loops
            edges_df = edges_df[edges_df['source'] != edges_df['target']]
            
            await self.message_queue.add(wand, f'✅ Created {len(edges_df):,} edges (removed self-loops)', verbatim=True)
            
            # Save cosmo_links.csv
            cosmo_links_file = data_path / 'cosmo_links.csv'
            edges_df.to_csv(cosmo_links_file, index=False)
            
            await self.message_queue.add(wand, '🎯 Creating node list and merging performance data...', verbatim=True)
            
            # Create master node list from unique URLs
            all_urls = set(edges_df['source'].tolist() + edges_df['target'].tolist())
            nodes_df = pd.DataFrame({'url': list(all_urls)})
            
            await self.message_queue.add(wand, f'✅ Created {len(nodes_df):,} unique nodes', verbatim=True)
            
            # Load and merge GSC data if available
            if gsc_file.exists():
                try:
                    gsc_df = pd.read_csv(gsc_file)
                    await self.message_queue.add(wand, f'📈 Loaded GSC data: {len(gsc_df):,} rows', verbatim=True)
                    
                    # Rename 'Full URL' to 'url' for consistent merging
                    if 'Full URL' in gsc_df.columns:
                        gsc_df.rename(columns={'Full URL': 'url'}, inplace=True)
                    
                    # Merge GSC data (left join to preserve all nodes)
                    nodes_df = nodes_df.merge(gsc_df, on='url', how='left')
                    
                except Exception as e:
                    await self.message_queue.add(wand, f'⚠️ Warning: Could not load GSC data: {str(e)}', verbatim=True)
            else:
                await self.message_queue.add(wand, '⚠️ No GSC data found, continuing without performance metrics', verbatim=True)
            
            # Load and merge basic crawl attributes from step_02b if available
            crawl_file = data_path / 'crawl.csv'
            if crawl_file.exists():
                try:
                    crawl_df = pd.read_csv(crawl_file)
                    await self.message_queue.add(wand, f'📄 Loaded crawl attributes: {len(crawl_df):,} rows', verbatim=True)
                    
                    # Handle different possible URL column names from step_02b
                    url_column = None
                    for col in crawl_df.columns:
                        if 'url' in col.lower() and not any(x in col.lower() for x in ['target', 'source', 'canonical']):
                            url_column = col
                            break
                    
                    if url_column and url_column != 'url':
                        crawl_df.rename(columns={url_column: 'url'}, inplace=True)
                    
                    # Merge crawl attributes (left join to preserve all nodes)
                    nodes_df = nodes_df.merge(crawl_df, on='url', how='left')
                    await self.message_queue.add(wand, f'✅ Merged crawl attributes (HTTP status, page titles, compliance, etc.)', verbatim=True)
                    
                except Exception as e:
                    await self.message_queue.add(wand, f'⚠️ Warning: Could not load crawl attributes: {str(e)}', verbatim=True)
            else:
                await self.message_queue.add(wand, '⚠️ No crawl attributes found from step_02b', verbatim=True)

            # Load and merge weblog data if available
            if weblog_file.exists():
                try:
                    weblog_df = pd.read_csv(weblog_file)
                    await self.message_queue.add(wand, f'🌐 Loaded weblog data: {len(weblog_df):,} rows', verbatim=True)
                    
                    # Rename 'Full URL' to 'url' for consistent merging
                    if 'Full URL' in weblog_df.columns:
                        weblog_df.rename(columns={'Full URL': 'url'}, inplace=True)
                    
                    # Merge weblog data (left join to preserve all nodes)
                    nodes_df = nodes_df.merge(weblog_df, on='url', how='left')
                    
                except Exception as e:
                    await self.message_queue.add(wand, f'⚠️ Warning: Could not load weblog data: {str(e)}', verbatim=True)
            else:
                await self.message_queue.add(wand, '⚠️ No weblog data found, continuing without crawl data', verbatim=True)
            
            await self.message_queue.add(wand, '📋 Preparing non-destructive metadata for Cosmograph...', verbatim=True)
            
            # Non-destructive approach: Keep all original metric names and values
            # Fill NaN values with defaults only for visualization
            nodes_df = nodes_df.fillna({
                'Impressions': 0,
                'Clicks': 0,
                'CTR': 0,
                'Avg. Position': 100,
                'crawls.google.count': 0
            })
            
            # Create id column as required by Cosmograph (rename url to id)
            nodes_df['id'] = nodes_df['url']
            
            # Non-destructive selection: Keep all original columns, let Cosmograph handle gradients
            # Start with 'id' as required by Cosmograph, then include all other original columns
            cosmo_columns = ['id']
            
            # Add all other columns except 'url' (since we renamed it to 'id')
            for col in nodes_df.columns:
                if col not in ['id', 'url']:  # Exclude id (already added) and url (renamed to id)
                    cosmo_columns.append(col)
            
            # Keep only columns that exist
            final_columns = [col for col in cosmo_columns if col in nodes_df.columns]
            cosmo_nodes_df = nodes_df[final_columns]
            
            # Save cosmo_nodes.csv
            cosmo_nodes_file = data_path / 'cosmo_nodes.csv'
            cosmo_nodes_df.to_csv(cosmo_nodes_file, index=False)
            
            await self.message_queue.add(wand, f'✅ Saved visualization files: {len(edges_df):,} edges, {len(cosmo_nodes_df):,} nodes', verbatim=True)
            
            await self.message_queue.add(wand, '🚀 Generating Cosmograph visualization URL...', verbatim=True)
            
            # Generate download URLs for the CSV files using the proper download_file endpoint
            
            base_url = "http://localhost:5001"
            links_path = f"{app_name}/{username}/{project_name}/{analysis_slug}/cosmo_links.csv"
            nodes_path = f"{app_name}/{username}/{project_name}/{analysis_slug}/cosmo_nodes.csv"
            
            # Create proper download URLs with timestamps (same pattern as _create_action_buttons)
            timestamp = int(datetime.now().timestamp())
            links_url = f"{base_url}/download_file?file={quote(links_path)}&t={timestamp}"
            nodes_url = f"{base_url}/download_file?file={quote(nodes_path)}&t={timestamp}"
            
            # Use the unified Cosmograph URL creation method
            # Generate Cosmograph URL using the meta pattern (let Cosmograph auto-detect columns)
            cosmograph_url = self.create_cosmograph_url(links_url, meta_url=nodes_url)
            
            # Store the result
            visualization_result = {
                'visualization_url': cosmograph_url,
                'links_url': links_url,
                'nodes_url': nodes_url,
                'edges_count': len(edges_df),
                'nodes_count': len(cosmo_nodes_df),
                'timestamp': datetime.now().isoformat()
            }
            
            # Save to step data
            await wand.set_step_data(pipeline_id, step_id, json.dumps(visualization_result), self.steps)
            
            await self.message_queue.add(wand, f'🎉 Visualization ready! {len(edges_df):,} edges and {len(cosmo_nodes_df):,} nodes processed.', verbatim=True)
            
            # Create visualization widget
            widget = Div(
                P(f"Graph processed: {len(edges_df):,} edges, {len(cosmo_nodes_df):,} nodes"),
                A("🚀 Open Visualization in New Tab", 
                  href=cosmograph_url, 
                  target="_blank", 
                  role="button", 
                  cls="primary"),
                style="text-align: center; padding: 15px;"
            )
            
            return Div(
                wand.display_revert_widget(
                    step_id=step_id, 
                    app_name=app_name, 
                    message=f'{step.show}: Visualization link generated', 
                    widget=widget, 
                    steps=self.steps
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
            
        except Exception as e:
            logging.exception(f'Error in step_05_process: {e}')
            await self.message_queue.add(wand, f'❌ Error generating visualization: {str(e)}', verbatim=True)
            return P(f'Error generating visualization: {str(e)}', cls='text-invalid')


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
        elif step_id == 'step_02b':
            # step_02b always uses 'Crawl Basic' template which has 'crawl_attributes' export type
            expected_filename = 'crawl.csv'
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
                    path_for_url = expected_file_path.resolve().relative_to(downloads_base.resolve())
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

                    # For link graph files, add the Cosmograph visualization button
                    # Check if we have a comprehensive visualization URL from step_05_process first
                    if is_link_graph:
                        viz_url = None
                        
                        # Try to get the comprehensive visualization URL from step_05_process
                        if step_id == 'step_05':
                            try:
                                step_05_data = step_data.get('step_05_process', '')
                                if step_05_data:
                                    visualization_result = json.loads(step_05_data)
                                    viz_url = visualization_result.get('visualization_url')
                            except (json.JSONDecodeError, KeyError):
                                pass
                        
                        # Fallback: create simple visualization URL for individual link graph files
                        if not viz_url:
                            from datetime import datetime
                            # Create simple Cosmograph visualization link for individual files
                            file_url = f"/download_file?file={quote(path_for_url)}"
                            timestamp = int(datetime.now().timestamp())
                            data_url = f"http://localhost:5001{file_url}&t={timestamp}"
                            viz_url = self.create_cosmograph_url(data_url)

                        if viz_url:
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
                        path_for_url = file_path_obj.resolve().relative_to(downloads_base.resolve())
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
                            # Create Cosmograph visualization link using the unified method
                            file_url = f"/download_file?file={quote(path_for_url)}"
                            timestamp = int(datetime.now().timestamp())
                            data_url = f"http://localhost:5001{file_url}&t={timestamp}"
                            viz_url = self.create_cosmograph_url(data_url)

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

    def create_cosmograph_url(self, edges_url, meta_url=None):
        """Generate a Cosmograph visualization URL."""
        import json
        from urllib.parse import quote
        
        config = {
            "data": edges_url,
            "render": {
                "nodeSize": {"field": "Clicks", "range": [1, 20]} if meta_url else None,
                "nodeColor": {"field": "Impressions", "type": "gradient"} if meta_url else None
            }
        }
        if meta_url:
            config["meta"] = meta_url
            
        return f"https://cosmograph.app/run/?config={quote(json.dumps(config))}"

    async def check_file_exists(self, filepath):
        """Check if a file exists and return info."""
        path = Path(filepath)
        if path.exists():
            stats = path.stat()
            return True, {
                'size': self.pipulate.format_size(stats.st_size),
                'created': datetime.fromtimestamp(stats.st_mtime).isoformat(),
                'path': str(path)
            }
        return False, None

    async def get_deterministic_filepath(self, username, project, analysis, export_type=None):
        """Generate a consistent filepath for downloads."""
        base = Path.cwd() / 'downloads' / self.app_name / username / project / analysis
        if export_type == 'link_graph_edges':
            return str(base / 'link_graph.csv')
        if export_type == 'crawl_attributes':
            return str(base / 'crawl.csv')
        return str(base)

    def format_size(self, size_bytes):
        """Helper to format file sizes for the UI."""
        if size_bytes == 0: return "0B"
        import math
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

    # --- END_PARAMETER_BUSTER_TRANSPLANT_BUNDLE ---

