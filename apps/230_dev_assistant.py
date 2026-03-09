# File: apps/320_dev_assistant.py
import asyncio
from datetime import datetime
from fasthtml.common import * # type: ignore
from fasthtml.common import to_xml
from loguru import logger
import inspect
from pathlib import Path
import re
import json
import os
from starlette.responses import HTMLResponse
from imports.crud import Step  # 🎯 STANDARDIZED: Import centralized Step definition

ROLES = ['Developer'] # Defines which user roles can see this plugin

def derive_public_endpoint_from_filename(filename_str: str) -> str:
    """Derives the public endpoint name from the filename (e.g., "010_my_flow.py" -> "my_flow")."""
    filename_part_no_ext = Path(filename_str).stem
    return re.sub(r"^\d+_", "", filename_part_no_ext)

class DevAssistant:
    """
    Pipulate Development Assistant

    Interactive debugging and development guidance tool that helps developers:
    - Validate workflow patterns against the Ultimate Pipulate Guide
    - Debug common implementation issues
    - Check plugin structure and naming conventions
    - Analyze workflow state and step progression
    - Provide pattern-specific recommendations
    - Check template suitability and marker compatibility

    This assistant implements the 25 critical patterns from the Ultimate Pipulate Guide
    and provides real-time validation and debugging assistance for Pipulate development.
    """
    APP_NAME = 'dev_assistant'
    DISPLAY_NAME = 'Development Assistant 🩺'
    ENDPOINT_MESSAGE = """Interactive debugging and development guidance for Pipulate workflows. Validate patterns, debug issues, check template suitability, and get expert recommendations based on the Ultimate Pipulate Implementation Guide and workflow creation helper system."""
    TRAINING_PROMPT = """You are the Pipulate Development Assistant. Help developers with: 1. Pattern validation against the 25 critical patterns from the Ultimate Guide. 2. Debugging workflow issues (auto-key generation, three-phase logic, chain reactions). 3. Plugin structure analysis and recommendations. 4. State management troubleshooting. 5. Template suitability and marker compatibility for helper tools. 6. Best practice guidance for workflow development. Always reference specific patterns from the Ultimate Guide and provide actionable debugging steps."""

    # UI Constants - Centralized color theme for consistent appearance
    UI_CONSTANTS = {
        'COLORS': {
            # Primary text colors
            'HEADER_TEXT': '#2c3e50',           # Dark blue-gray for headers
            'BODY_TEXT': '#CCCCCC',             # Muted gray for body text
            'SECONDARY_TEXT': '#495057',        # Slightly darker gray for secondary text

            # Semantic colors
            'SUCCESS_GREEN': '#28a745',         # Green for success indicators
            'ERROR_RED': '#dc3545',             # Red for errors and warnings
            'WARNING_YELLOW': '#ffc107',        # Yellow for warnings that need attention
            'INFO_BLUE': '#007bff',             # Blue for informational elements
            'INFO_TEAL': '#17a2b8',             # Teal for secondary info
            'ACCENT_ORANGE': '#fd7e14',         # Orange for special highlights
            'ACCENT_PURPLE': '#6f42c1',         # Purple for template analysis

            # Status colors (for success/error badges)
            'SUCCESS_TEXT': '#155724',          # Dark green text for success badges
            'WARNING_TEXT': '#856404',          # Dark yellow text for warning badges
            'ERROR_TEXT': '#721c24',            # Dark red text for error badges

            # Code display colors
            'CODE_BG_DARK': '#2d3748',          # Dark background for code blocks
            'CODE_TEXT_LIGHT': '#e2e8f0',       # Light text for dark code blocks
        },
        'BACKGROUNDS': {
            'LIGHT_GRAY': '#f8f9fa',           # General light gray background
            'SUCCESS_BG': '#d4edda',           # Light green background for success
            'WARNING_BG': '#fff3cd',           # Light yellow background for warnings
            'ERROR_BG': '#f8d7da',             # Light red background for errors

            # Transparent overlays for sections
            'SUCCESS_OVERLAY': 'rgba(40, 167, 69, 0.05)',    # Very light green overlay
            'WARNING_OVERLAY': 'rgba(255, 193, 7, 0.05)',    # Very light yellow overlay
        },
        'SPACING': {
            'BORDER_RADIUS': '4px',            # Standard border radius
            'SECTION_PADDING': '1rem',         # Standard section padding
            'SMALL_PADDING': '0.5rem',         # Small padding for badges
            'MARGIN_BOTTOM': '1rem',           # Standard bottom margin
            'SMALL_MARGIN': '0.5rem',          # Small margins
        }
    }

    def __init__(self, app, pipulate, pipeline, db, app_name=None):
        self.pipulate = pipulate
        self.app = app
        self.app_name = self.APP_NAME
        self.pipulate = pipulate
        self.pipeline = pipeline
        wand = self.pipulate
        wand = self.pipulate
        self.message_queue = wand.get_message_queue()

        self.steps = [
            Step(id='step_01', done='plugin_analysis', show='1. Plugin Selection', refill=False),
            Step(id='step_02', done='comprehensive_analysis', show='2. Analysis & Recommendations', refill=False),
            Step(id='finalize', done='finalized', show='Finalize Analysis', refill=False)
        ]
        self.steps_indices = {step_obj.id: i for i, step_obj in enumerate(self.steps)}

        internal_route_prefix = self.APP_NAME

        routes = [
            (f'/{internal_route_prefix}/init', self.init, ['POST']),
            (f'/{internal_route_prefix}/revert', self.handle_revert, ['POST']),
            (f'/{internal_route_prefix}/unfinalize', self.unfinalize, ['POST']),
            (f'/{internal_route_prefix}/search_apps_step01', self.search_apps_step01, ['POST'])
        ]

        for step_obj in self.steps:
            step_id = step_obj.id
            handler_method = getattr(self, step_id, None)
            if handler_method:
                current_methods = ['GET']
                if step_id == 'finalize':
                    current_methods.append('POST')
                routes.append((f'/{internal_route_prefix}/{step_id}', handler_method, current_methods))

            if step_id != 'finalize':
                submit_handler_method = getattr(self, f'{step_id}_submit', None)
                if submit_handler_method:
                    routes.append((f'/{internal_route_prefix}/{step_id}_submit', submit_handler_method, ['POST']))

        for path, handler, *methods_list_arg in routes:
            current_methods = methods_list_arg[0] if methods_list_arg else ['GET']
            self.app.route(path, methods=current_methods)(handler)

    async def landing(self, request):
        """Direct utility - skip pipeline keys and go straight to plugin analysis."""
        # Bypass the entire pipeline system - this is a utility tool, not a data workflow
        return Div(
            H2(self.DISPLAY_NAME),
            P(self.ENDPOINT_MESSAGE),
            # Jump straight to plugin analysis - no keys needed
            Div(id='step_01', hx_get=f'/{self.APP_NAME}/step_01', hx_trigger='load'),
            id=f'{self.APP_NAME}-container'
        )

    async def init(self, request):
        wand, db = self.pipulate, self.pipulate.db
        internal_app_name = self.APP_NAME
        form = await request.form()
        user_input_key = form.get('pipeline_id', '').strip()

        if not user_input_key:
            from starlette.responses import Response
            response = Response('')
            response.headers['HX-Refresh'] = 'true'
            return response

        _, prefix_for_key_gen, _ = wand.generate_pipeline_key(self)
        if user_input_key.startswith(prefix_for_key_gen) and len(user_input_key.split('-')) == 3:
            pipeline_id = user_input_key
        else:
             _, prefix, user_part = wand.generate_pipeline_key(self, user_input_key)
             pipeline_id = f'{prefix}{user_part}'

        wand.db['pipeline_id'] = pipeline_id
        state, error = wand.initialize_if_missing(pipeline_id, {'app_name': internal_app_name})
        if error: return error

        await self.message_queue.add(wand, f'Development Assistant Session: {pipeline_id}', verbatim=True, spaces_before=0)

        return wand.run_all_cells(internal_app_name, self.steps)

    async def finalize(self, request):
        wand, db, app_name = self.pipulate, self.pipulate.db, self.APP_NAME
        pipeline_id = wand.db.get('pipeline_id', 'unknown')

        if request.method == 'POST':
            await wand.set_step_data(pipeline_id, 'finalize', {'finalized': True}, self.steps)
            await self.message_queue.add(wand, 'Development analysis session finalized.', verbatim=True)
            return wand.run_all_cells(app_name, self.steps)

        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data:
            return Card(
                H3('🔒 Analysis Session Finalized'),
                P('This development analysis session is complete.'),
                Form(
                    Button('🔓 Unfinalize', type='submit', cls='secondary',
                           id='dev-assistant-unfinalize-button',
                           aria_label='Unlock development analysis session for editing',
                           data_testid='dev-assistant-unfinalize-button'),
                    hx_post=f'/{app_name}/unfinalize',
                    hx_target=f'#{app_name}-container'
                ),
                id='finalize'
            )
        else:
            return Card(
                H3('Finalize Development Analysis'),
                P('Complete this development analysis session.'),
                Form(
                    Button('🔒 Finalize', type='submit', cls='primary',
                           id='dev-assistant-finalize-button',
                           aria_label='Finalize development analysis session',
                           data_testid='dev-assistant-finalize-button'),
                    hx_post=f'/{app_name}/finalize',
                    hx_target=f'#{app_name}-container'
                ),
                id='finalize'
            )

    async def unfinalize(self, request):
        wand, db, app_name = self.pipulate, self.pipulate.db, self.APP_NAME
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        await wand.unfinalize_workflow(pipeline_id)
        await self.message_queue.add(wand, 'Development analysis session unlocked for editing.', verbatim=True)
        return wand.run_all_cells(app_name, self.steps)

    async def handle_revert(self, request):
        wand, db, app_name = self.pipulate, self.pipulate.db, self.APP_NAME
        form = await request.form()
        step_id = form.get('step_id')
        pipeline_id = wand.db.get('pipeline_id', 'unknown')

        if not step_id:
            return P('Error: No step specified for revert.', cls='text-invalid')

        await wand.clear_steps_from(pipeline_id, step_id, self.steps)

        state = wand.read_state(pipeline_id)
        state['_revert_target'] = step_id
        wand.write_state(pipeline_id, state)

        await self.message_queue.add(wand, f'Reverted to {step_id} for re-analysis.', verbatim=True)

        return wand.run_all_cells(app_name, self.steps)

    def generate_automation_ai_prompt(self, automation_readiness, filename):
        """Generate a comprehensive AI prompt for fixing automation and accessibility issues."""
        
        if not automation_readiness:
            return "No automation analysis available for this plugin."
        
        prompt_parts = [
            f"# 🤖 AI Code Assistant: Fix Automation & Accessibility Issues",
            "",
            f"**Plugin File**: `{filename}`",
            "",
            "## 📋 Current Analysis Results",
            f"- **Overall Score**: {automation_readiness.get('accessibility_score', 0)}/100",
            f"- **Selenium Readiness**: {automation_readiness.get('selenium_readiness', 'unknown').title()}",
            f"- **Automation Ready**: {'✅ Yes' if automation_readiness.get('automation_ready', False) else '❌ No'}",
            ""
        ]
        
        # Add dropdown analysis
        dropdown_validations = automation_readiness.get('dropdown_validations', {})
        if dropdown_validations:
            prompt_parts.extend([
                "## 🔧 Dropdown Functions Analysis",
                ""
            ])
            for func_name, result in dropdown_validations.items():
                if result.get('function_found'):
                    completion = result.get('completion_percentage', 0)
                    prompt_parts.append(f"- **{func_name}**: {completion}% complete")
                    if result.get('missing_attributes'):
                        prompt_parts.append(f"  - Missing: {', '.join(result['missing_attributes'])}")
            prompt_parts.append("")
        
        # Add form validation results
        form_validations = automation_readiness.get('form_validations', {})
        if form_validations.get('forms_detected'):
            prompt_parts.extend([
                "## 📝 Form Elements Analysis",
                f"- **Automation attributes found**: {', '.join(form_validations.get('automation_attributes', [])) or 'None'}",
            ])
            if form_validations.get('missing_attributes'):
                prompt_parts.append(f"- **Missing attributes**: {', '.join(form_validations['missing_attributes'])}")
            prompt_parts.append("")
        
        # Add ARIA issues
        aria_issues = automation_readiness.get('aria_issues', [])
        if aria_issues:
            prompt_parts.extend([
                "## ⚠️ ARIA Issues to Fix",
                ""
            ])
            for issue in aria_issues:
                prompt_parts.append(f"- {issue}")
            prompt_parts.append("")
        
        # Add recommendations
        recommendations = automation_readiness.get('aria_recommendations', [])
        if recommendations:
            prompt_parts.extend([
                "## 💡 Recommended Actions",
                ""
            ])
            for rec in recommendations:
                prompt_parts.append(f"- {rec}")
            prompt_parts.append("")
        
        # Add implementation guidance
        prompt_parts.extend([
            "## 🎯 Implementation Tasks",
            "",
            "Please help me fix these automation and accessibility issues by:",
            "",
            "1. **Adding missing ARIA attributes** to dropdown functions:",
            "   - `aria-label` for screen reader descriptions",
            "   - `aria-expanded` for dropdown state",
            "   - `aria-haspopup` for dropdown indication",
            "   - `aria-labelledby` for proper labeling",
            "",
            "2. **Enhancing form elements** with automation attributes:",
            "   - `id` attributes for unique identification",
            "   - `name` attributes for form processing",
            "   - `data-testid` for test automation",
            "   - `aria-label` for accessibility",
            "",
            "3. **Ensuring Selenium compatibility** by:",
            "   - Using consistent naming patterns",
            "   - Avoiding problematic attributes like `role='group'` on profile dropdowns",
            "   - Adding automation-friendly selectors",
            "",
            "4. **Testing the changes** to ensure:",
            "   - Screen readers can navigate properly",
            "   - Selenium tests can find elements reliably",
            "   - No visual regressions occur",
            "",
            "Please analyze the current code and provide specific fixes with the exact code changes needed."
        ])
        
        return "\n".join(prompt_parts)

    def validate_aria_and_automation(self, content, file_path):
        """Validate ARIA attributes and automation readiness for plugin files."""
        
        # DEBUG LOGGING
        logger.info(f"🔍 FINDER_TOKEN: ARIA_VALIDATION_START - File: {file_path}")
        
        aria_results = {
            'automation_ready': True,
            'aria_issues': [],
            'aria_recommendations': [],
            'dropdown_validations': {},
            'form_validations': {},
            'selenium_readiness': 'good',
            'accessibility_score': 100
        }
        
        # Define required ARIA patterns for dropdown functions
        required_dropdown_patterns = {
            'create_profile_menu': {
                'aria_label': 'Profile selection menu',
                'aria_expanded': 'false',
                'aria_haspopup': 'menu',
                'aria_labelledby': 'profile-id',
                'role_menu': "role='menu'",
                'ul_aria_label': 'Profile options'
            },
            'create_menu_container': {
                'aria_label': 'Application menu',
                'aria_expanded': 'false', 
                'aria_haspopup': 'menu',
                'aria_labelledby': 'app-id',
                'role_menu': "role='menu'",
                'ul_aria_label': 'Application options'
            },
            'create_env_menu': {
                'dev_aria_label': 'Switch to Development environment',
                'prod_aria_label': 'Switch to Production environment'
            }
        }
        
        # Check dropdown functions ONLY if they exist (don't penalize plugins without dropdowns)
        dropdown_functions_found = False
        for func_name, required_attrs in required_dropdown_patterns.items():
            func_pattern = rf'def {func_name}\([^)]*\):(.*?)(?=\ndef|\Z)'
            func_match = re.search(func_pattern, content, re.DOTALL)
            
            if func_match:
                dropdown_functions_found = True
                func_content = func_match.group(1)
                dropdown_result = {
                    'function_found': True,
                    'missing_attributes': [],
                    'present_attributes': [],
                    'score': 0
                }
                
                total_attrs = len(required_attrs)
                for attr_name, expected_value in required_attrs.items():
                    if expected_value in func_content:
                        dropdown_result['present_attributes'].append(attr_name)
                        dropdown_result['score'] += 1
                    else:
                        dropdown_result['missing_attributes'].append(attr_name)
                        aria_results['automation_ready'] = False
                        aria_results['aria_issues'].append(f"Missing {attr_name} in {func_name}")
                
                dropdown_result['completion_percentage'] = int((dropdown_result['score'] / total_attrs) * 100)
                aria_results['dropdown_validations'][func_name] = dropdown_result
        
        # Check for forbidden regression patterns
        forbidden_patterns = {
            "role='group' in PROFILE dropdown": {
                'pattern': r'profile-dropdown-menu.*role=[\'"]group[\'"]',
                'severity': 'error',
                'message': 'PROFILE dropdown should NOT have role="group" (causes width issues)',
                'fix': "Remove role='group' from PROFILE dropdown Details element"
            },
            "Missing ARIA in critical dropdowns": {
                'pattern': r'Details\(Summary\([^)]*\), Ul\([^)]*\), cls=[\'"]dropdown[\'"](?!.*aria)',
                'severity': 'warning', 
                'message': 'Dropdown missing ARIA attributes for automation',
                'fix': "Add aria_label, aria_expanded, aria_haspopup to dropdown Details element"
            }
        }
        
        for check_name, check_info in forbidden_patterns.items():
            if re.search(check_info['pattern'], content):
                aria_results['automation_ready'] = False
                aria_results['aria_issues'].append(f"{check_info['severity'].upper()}: {check_info['message']}")
                aria_results['aria_recommendations'].append(f"FIX: {check_info['fix']}")
                
                if check_info['severity'] == 'error':
                    aria_results['selenium_readiness'] = 'poor'
                    aria_results['accessibility_score'] -= 30
                elif aria_results['selenium_readiness'] == 'good':
                    aria_results['selenium_readiness'] = 'fair'
                    aria_results['accessibility_score'] -= 15
        
        # Check for form automation readiness
        form_elements = ['Input', 'Select', 'Textarea', 'Button']
        form_found = any(element in content for element in form_elements)
        
        if form_found:
            # Check for common automation-friendly patterns
            automation_patterns = {
                'aria_label': r'aria_label=[\'"][^\'"]+[\'"]',
                'id_attributes': r'id=[\'"][^\'"]+[\'"]',
                'name_attributes': r'name=(?:[\'"][^\'"]+[\'"]|[a-zA-Z_][a-zA-Z0-9_.]*)',
                'data_testid': r'data_testid=[\'"][^\'"]+[\'"]',
                'placeholder_text': r'placeholder=(?:f?[\'"][^\'"]+[\'"])'
            }
            
            form_validation = {
                'forms_detected': True,
                'automation_attributes': [],
                'missing_attributes': []
            }
            
            for pattern_name, pattern_regex in automation_patterns.items():
                match = re.search(pattern_regex, content)
                if match:
                    form_validation['automation_attributes'].append(pattern_name)
                    logger.info(f"🔍 FINDER_TOKEN: PATTERN_MATCH - {pattern_name}: FOUND (matched: {match.group()[:50]}...)")
                else:
                    form_validation['missing_attributes'].append(pattern_name)
                    logger.info(f"🔍 FINDER_TOKEN: PATTERN_MATCH - {pattern_name}: MISSING (pattern: {pattern_regex})")
            
            aria_results['form_validations'] = form_validation
            
            # IMPROVED SCORING: More generous scoring for good automation coverage
            automation_score = len(form_validation['automation_attributes'])
            total_possible = len(automation_patterns)
            coverage_percentage = (automation_score / total_possible) * 100
            
            # DEBUG LOGGING
            logger.info(f"🔍 FINDER_TOKEN: AUTOMATION_SCORING - Score: {automation_score}/{total_possible} ({coverage_percentage}%)")
            logger.info(f"🔍 FINDER_TOKEN: AUTOMATION_ATTRIBUTES - Found: {form_validation['automation_attributes']}")
            logger.info(f"🔍 FINDER_TOKEN: AUTOMATION_MISSING - Missing: {form_validation['missing_attributes']}")
            
            if automation_score >= 4:  # 80%+ coverage = perfect score
                logger.info(f"🔍 FINDER_TOKEN: SCORING_BRANCH - Using >=4 branch (perfect score)")
                aria_results['aria_recommendations'].append(
                    "✅ Excellent automation attribute coverage detected"
                )
                # No deduction for 80%+ coverage
            elif automation_score >= 3:  # 60%+ coverage = minor deduction
                logger.info(f"🔍 FINDER_TOKEN: SCORING_BRANCH - Using >=3 branch (-5 points)")
                aria_results['aria_recommendations'].append(
                    "⚠️ Good automation coverage, consider adding remaining attributes"
                )
                aria_results['accessibility_score'] -= 5  # Reduced from 10
            elif automation_score >= 2:  # 40%+ coverage = moderate deduction
                logger.info(f"🔍 FINDER_TOKEN: SCORING_BRANCH - Using >=2 branch (-15 points)")
                aria_results['aria_recommendations'].append(
                    "⚠️ Moderate automation coverage, add more attributes for better testing"
                )
                aria_results['accessibility_score'] -= 15  # Reduced from 20
            else:  # <40% coverage = significant deduction
                logger.info(f"🔍 FINDER_TOKEN: SCORING_BRANCH - Using <2 branch (-25 points)")
                aria_results['aria_recommendations'].append(
                    "❌ Add more automation-friendly attributes (id, aria-label, data-testid) to form elements"
                )
                aria_results['accessibility_score'] -= 25  # Slightly increased for very poor coverage
        
        # Check for button accessibility
        button_patterns = {
            'button_aria_labels': r'Button\([^)]*aria_label=[\'"][^\'"]+[\'"]',
            'button_titles': r'Button\([^)]*title=[\'"][^\'"]+[\'"]',
            'descriptive_button_text': r'Button\([\'"][A-Za-z\s]{3,}[\'"]'
        }
        
        button_accessibility = {
            'buttons_found': 'Button(' in content,
            'accessible_patterns': []
        }
        
        if button_accessibility['buttons_found']:
            for pattern_name, pattern_regex in button_patterns.items():
                if re.search(pattern_regex, content):
                    button_accessibility['accessible_patterns'].append(pattern_name)
            
            # IMPROVED SCORING: Don't penalize if buttons have any accessibility pattern
            if len(button_accessibility['accessible_patterns']) == 0:
                aria_results['aria_issues'].append("Buttons lack accessibility attributes")
                aria_results['aria_recommendations'].append(
                    "❌ Add aria-label or descriptive text to Button elements"
                )
                aria_results['accessibility_score'] -= 15
            else:
                aria_results['aria_recommendations'].append(
                    "✅ Buttons have good accessibility attributes"
                )
        
        # Final score calculation
        aria_results['accessibility_score'] = max(0, min(100, aria_results['accessibility_score']))
        
        # Generate automation readiness recommendations
        if aria_results['aria_issues']:
            aria_results['aria_recommendations'].insert(0, 
                f"🔧 Fix {len(aria_results['aria_issues'])} ARIA/automation issues for better testing support"
            )
            
        if aria_results['selenium_readiness'] != 'good':
            aria_results['aria_recommendations'].append(
                "🤖 Review UI elements for Selenium/automation compatibility"
            )
        
        # BONUS: Perfect score message for plugins without dropdown dependencies
        if (aria_results['accessibility_score'] == 100 and 
            not dropdown_functions_found and 
            form_found):
            aria_results['aria_recommendations'].append(
                "🎉 Perfect automation readiness! This plugin has excellent form accessibility and no dropdown dependencies."
            )
        
        return aria_results

    def _generate_score_breakdown(self, automation_readiness):
        """Generate detailed score breakdown showing what contributes to the automation score."""
        breakdown_items = []
        
        # Base score starts at 100, deductions are made
        base_score = 100
        current_score = automation_readiness.get('accessibility_score', 0)
        total_deductions = base_score - current_score
        
        # Header showing scoring logic
        breakdown_items.append(
            Div(f'🎯 Base Score: {base_score}/100 (Perfect accessibility)', 
                style='color: #28a745; font-weight: bold; margin-bottom: 0.5rem;')
        )
        
        if total_deductions > 0:
            breakdown_items.append(
                Div(f'⚠️ Total Deductions: -{total_deductions} points', 
                    style='color: #dc3545; font-weight: bold; margin-bottom: 1rem;')
            )
        
        # Analyze specific deduction sources
        form_validations = automation_readiness.get('form_validations', {})
        if form_validations.get('forms_detected'):
            automation_attrs = form_validations.get('automation_attributes', [])
            missing_attrs = form_validations.get('missing_attributes', [])
            coverage_percentage = int((len(automation_attrs) / 5) * 100)  # 5 total automation patterns
            
            breakdown_items.append(
                Div(
                    Strong('📝 Form Elements Analysis:', style='color: #0066cc;'),
                    Br(),
                    Span(f'📊 Coverage: {coverage_percentage}% ({len(automation_attrs)}/5 patterns)', 
                         style=f'color: {"#28a745" if coverage_percentage >= 80 else "#fd7e14" if coverage_percentage >= 60 else "#dc3545"}; margin-left: 1rem; display: block; font-weight: bold;'),
                    Span(f'✅ Found: {", ".join(automation_attrs) if automation_attrs else "None"}', 
                         style='color: #28a745; margin-left: 1rem; display: block;'),
                    Span(f'❌ Missing: {", ".join(missing_attrs) if missing_attrs else "None"}', 
                         style='color: #dc3545; margin-left: 1rem; display: block;'),
                    style='margin-bottom: 1rem; padding: 0.5rem; background-color: #e7f3ff; border-radius: 4px;'
                )
            )
            
            # Calculate form score impact with improved logic
            coverage_percentage = int((len(automation_attrs) / 5) * 100)
            if len(automation_attrs) >= 4:  # 80%+ coverage
                breakdown_items.append(
                    Div(f'📈 Form Score Impact: No deduction (excellent coverage ≥80%)', 
                        style='color: #28a745; margin-left: 1rem; font-style: italic;')
                )
            elif len(automation_attrs) >= 3:  # 60%+ coverage
                breakdown_items.append(
                    Div('📉 Form Score Impact: -5 points (good coverage 60-79%)', 
                        style='color: #fd7e14; margin-left: 1rem; font-style: italic;')
                )
            elif len(automation_attrs) >= 2:  # 40%+ coverage
                breakdown_items.append(
                    Div('📉 Form Score Impact: -15 points (moderate coverage 40-59%)', 
                        style='color: #fd7e14; margin-left: 1rem; font-style: italic;')
                )
            else:  # <40% coverage
                breakdown_items.append(
                    Div('📉 Form Score Impact: -25 points (poor coverage <40%)', 
                        style='color: #dc3545; margin-left: 1rem; font-style: italic;')
                )
        
        # Button accessibility analysis
        aria_issues = automation_readiness.get('aria_issues', [])
        button_issues = [issue for issue in aria_issues if 'button' in issue.lower()]
        if button_issues:
            breakdown_items.append(
                Div(
                    Strong('🔘 Button Accessibility:', style='color: #0066cc;'),
                    Br(),
                    *[Span(f'❌ {issue}', style='color: #dc3545; margin-left: 1rem; display: block;') 
                      for issue in button_issues],
                    Div('📉 Button Score Impact: -15 points (missing accessibility attributes)', 
                        style='color: #dc3545; margin-left: 1rem; font-style: italic; margin-top: 0.5rem;'),
                    style='margin-bottom: 1rem; padding: 0.5rem; background-color: #ffe6e6; border-radius: 4px;'
                )
            )
        else:
            # Check if buttons exist and show positive feedback
            if 'Button(' in str(automation_readiness):  # Simple check for button presence
                breakdown_items.append(
                    Div(
                        Strong('🔘 Button Accessibility:', style='color: #0066cc;'),
                        Br(),
                        Span('✅ Buttons have good accessibility attributes', 
                             style='color: #28a745; margin-left: 1rem; display: block;'),
                        Div('📈 Button Score Impact: No deduction (accessible buttons)', 
                            style='color: #28a745; margin-left: 1rem; font-style: italic; margin-top: 0.5rem;'),
                        style='margin-bottom: 1rem; padding: 0.5rem; background-color: #e6ffe6; border-radius: 4px;'
                    )
                )
        
        # Dropdown analysis (only show if dropdowns exist)
        dropdown_validations = automation_readiness.get('dropdown_validations', {})
        if dropdown_validations:
            for func_name, result in dropdown_validations.items():
                if result.get('function_found'):
                    completion = result.get('completion_percentage', 0)
                    missing = result.get('missing_attributes', [])
                    
                    breakdown_items.append(
                        Div(
                            Strong(f'📋 {func_name}:', style='color: #0066cc;'),
                            Br(),
                            Span(f'✅ Completion: {completion}%', 
                                 style=f'color: {"#28a745" if completion >= 80 else "#dc3545" if completion < 50 else "#fd7e14"}; margin-left: 1rem; display: block;'),
                            *([Span(f'❌ Missing: {", ".join(missing)}', 
                                   style='color: #dc3545; margin-left: 1rem; display: block;')] if missing else []),
                            style='margin-bottom: 1rem; padding: 0.5rem; background-color: #f0f0f0; border-radius: 4px;'
                        )
                    )
        else:
            # Show positive message for plugins without dropdown dependencies
            breakdown_items.append(
                Div(
                    Strong('📋 Dropdown Dependencies:', style='color: #0066cc;'),
                    Br(),
                    Span('✅ No dropdown menu dependencies detected', 
                         style='color: #28a745; margin-left: 1rem; display: block;'),
                    Div('📈 Dropdown Score Impact: No deduction (no dropdown complexity)', 
                        style='color: #28a745; margin-left: 1rem; font-style: italic; margin-top: 0.5rem;'),
                    style='margin-bottom: 1rem; padding: 0.5rem; background-color: #e6ffe6; border-radius: 4px;'
                )
            )
        
        # What's needed for 100/100
        if current_score < 100:
            points_needed = 100 - current_score
            breakdown_items.append(
                Div(
                    Strong(f'🎯 To Reach 100/100 (Need +{points_needed} points):', style='color: #0066cc; font-size: 1.1rem;'),
                    Br(),
                    style='margin-top: 1rem; margin-bottom: 0.5rem;'
                )
            )
            
            # Specific recommendations based on missing elements
            if form_validations.get('missing_attributes'):
                missing_attrs = form_validations['missing_attributes']
                if 'data_testid' in missing_attrs:
                    breakdown_items.append(
                        Div('• Add data-testid attributes to form elements (+5-10 points)', 
                            style='color: #0066cc; margin-left: 1rem;')
                    )
                if 'placeholder_text' in missing_attrs:
                    breakdown_items.append(
                        Div('• Add placeholder text to input fields (+5 points)', 
                            style='color: #0066cc; margin-left: 1rem;')
                    )
                if 'name_attributes' in missing_attrs:
                    breakdown_items.append(
                        Div('• Add name attributes for form processing (+5 points)', 
                            style='color: #0066cc; margin-left: 1rem;')
                    )
            
            if button_issues:
                breakdown_items.append(
                    Div('• Add aria-label to buttons (+15 points)', 
                        style='color: #0066cc; margin-left: 1rem;')
                )
                
            if not automation_readiness.get('automation_ready', False):
                breakdown_items.append(
                    Div('• Fix ARIA compliance issues (remaining points)', 
                        style='color: #0066cc; margin-left: 1rem;')
                    )
        else:
            breakdown_items.append(
                Div('🎉 Perfect Score! All automation & accessibility criteria met.', 
                    style='color: #28a745; font-weight: bold; font-size: 1.1rem; margin-top: 1rem;')
            )
        
        return breakdown_items

    def analyze_plugin_file(self, file_path):
        """Analyze a plugin file for common patterns, issues, and template suitability."""
        if not file_path.exists():
            return {"error": f"File not found: {file_path}"}

        content = file_path.read_text()
        filename = file_path.name
        analysis = {
            "file_path": str(file_path),
            "filename": filename,
            "patterns_found": [],
            "issues": [],
            "recommendations": [],
            "coding_assistant_prompts": [],  # New: Detailed fix instructions
            "template_suitability": {
                "as_template_source": False,
                "as_splice_target": False,
                "as_swap_source": True,  # Default true, most workflows can be swap sources
                "as_swap_target": False,
                "missing_requirements": []
            },
            "transplantation_analysis": {  # NEW: Detailed transplantation analysis
                "swappable_steps": [],
                "step_dependencies": {},
                "transplant_commands": [],
                "compatibility_warnings": []
            }
        }

        # Check for auto-key generation pattern (Priority 1)
        if 'HX-Refresh' in content and 'not user_input' in content:
            analysis["patterns_found"].append("✅ Auto-key generation pattern detected")
        else:
            analysis["issues"].append("❌ Missing auto-key generation pattern (Priority 1)")
            analysis["recommendations"].append("Add HX-Refresh response for empty input in init() method")
            analysis["coding_assistant_prompts"].append(
                f"Add auto-key generation pattern to {filename}:\n"
                f"In the init() method, add this code after getting user_input_key:\n\n"
                f"```python\n"
                f"if not user_input_key:\n"
                f"    from starlette.responses import Response\n"
                f"    response = Response('')\n"
                f"    response.headers['HX-Refresh'] = 'true'\n"
                f"    return response\n"
                f"```\n\n"
                f"This should be placed right after the line: user_input_key = form.get('pipeline_id', '').strip()"
            )

        # Check for three-phase pattern (Priority 2)
        if 'finalized' in content and '_revert_target' in content:
            analysis["patterns_found"].append("✅ Three-phase step pattern detected")
        else:
            analysis["issues"].append("❌ Missing three-phase step pattern (Priority 2)")
            analysis["recommendations"].append("Implement finalize/revert/input phases in step handlers")
            analysis["coding_assistant_prompts"].append(
                f"Add three-phase step pattern to {filename}:\n"
                f"Update each step handler (step_01, step_02, etc.) to check three phases:\n\n"
                f"```python\n"
                f"# In each step_XX method, add these checks:\n"
                f"finalize_data = pip.get_step_data(pipeline_id, 'finalize', {{}})\n"
                f"if 'finalized' in finalize_data:\n"
                f"    # Return finalized view\n"
                f"    return Div(\n"
                f"        Card(H3(f'🔒 {{step.show}}: Complete')),\n"
                f"        Div(id=next_step_id, hx_get=f'/{{app_name}}/{{next_step_id}}', hx_trigger='load'),\n"
                f"        id=step_id\n"
                f"    )\n"
                f"elif user_val and state.get('_revert_target') != step_id:\n"
                f"    # Return completed view with revert option\n"
                f"    return pip.chain_reverter(step_id, step_index, steps, app_name, processed_val)\n"
                f"else:\n"
                f"    # Return input form\n"
                f"```"
            )

        # Check for chain reaction pattern (Priority 6)
        if 'hx_trigger=\'load\'' in content or 'hx_trigger="load"' in content:
            analysis["patterns_found"].append("✅ Chain reaction pattern detected")
        else:
            analysis["issues"].append("❌ Missing chain reaction pattern (Priority 6)")
            analysis["recommendations"].append("Add hx_trigger='load' to completed step views")
            analysis["coding_assistant_prompts"].append(
                f"Add chain reaction pattern to {filename}:\n"
                f"In step submit handlers, ensure the response includes hx_trigger='load':\n\n"
                f"```python\n"
                f"# In step_XX_submit methods, return:\n"
                f"return pip.chain_reverter(\n"
                f"    step_id=step_id,\n"
                f"    step_index=step_index,\n"
                f"    steps=steps,\n"
                f"    app_name=app_name,\n"
                f"    processed_val=processed_value\n"
                f")\n"
                f"```\n\n"
                f"Or manually create the pattern:\n"
                f"```python\n"
                f"return Div(\n"
                f"    pip.display_revert_header(step_id, app_name, steps, f'{{step.show}}: {{value}}'),\n"
                f"    Div(id=next_step_id, hx_get=f'/{{app_name}}/{{next_step_id}}', hx_trigger='load'),\n"
                f"    id=step_id\n"
                f")\n"
                f"```"
            )

        # Check for request parameter (Priority 7)
        if 'async def' in content and 'request' in content:
            analysis["patterns_found"].append("✅ Request parameter pattern detected")
        else:
            analysis["issues"].append("❌ Missing request parameters (Priority 7)")
            analysis["recommendations"].append("All route handlers must accept request parameter")
            analysis["coding_assistant_prompts"].append(
                f"Add request parameters to all route handlers in {filename}:\n"
                f"Update all method signatures to include request parameter:\n\n"
                f"```python\n"
                f"async def landing(self, request):  # Add request parameter\n"
                f"async def init(self, request):     # Add request parameter\n"
                f"async def step_01(self, request): # Add request parameter\n"
                f"async def step_01_submit(self, request): # Add request parameter\n"
                f"async def finalize(self, request): # Add request parameter\n"
                f"# ... and so on for all route handler methods\n"
                f"```\n\n"
                f"The request object provides access to form data, query params, and headers."
            )

        # Route Registration Analysis - Check for missing handlers that are being registered
        # ================================================================================
        route_registration_issues = []

        # Extract the route registration pattern from __init__ method
        init_method_match = re.search(r'def __init__\(.*?\n(.*?)(?=\n    def|\n    async def|\nclass|\Z)', content, re.DOTALL)
        if init_method_match:
            init_content = init_method_match.group(1)

            # Check for explicit finalize_submit registration pattern
            if 'finalize_submit' in init_content:
                if 'async def finalize_submit(' not in content:
                    route_registration_issues.append(
                        f"❌ CRITICAL: Route registration expects 'finalize_submit' method but it doesn't exist"
                    )
                    analysis["coding_assistant_prompts"].append(
                        f"Add missing finalize_submit method to {filename}:\n"
                        f"The route registration in __init__ is trying to register a finalize_submit handler but it doesn't exist.\n\n"
                        f"Add this method to the class:\n\n"
                        f"```python\n"
                        f"async def finalize_submit(self, request):\n"
                        f"    pip, db, app_name = self.pipulate, self.pipulate.db, self.APP_NAME\n"
                        f"    pipeline_id = pip.db.get('pipeline_id', 'unknown')\n"
                        f"    \n"
                        f"    await pip.set_step_data(pipeline_id, 'finalize', {{'finalized': True}}, self.steps)\n"
                        f"    await self.message_queue.add(pip, 'Workflow finalized.', verbatim=True)\n"
                        f"    return pip.run_all_cells(app_name, self.steps)\n"
                        f"```\n\n"
                        f"OR modify the route registration to not expect finalize_submit and handle POST in finalize() method instead."
                    )

            # Check for dynamic step registration that would create finalize_submit
            # Pattern: for step in steps: ... getattr(self, f'{step_id}_submit')
            if ('for step in steps:' in init_content or 'for step in self.steps:' in init_content) and 'getattr(self, f' in init_content and '_submit' in init_content:
                # Check if 'finalize' appears in the steps definition and would trigger finalize_submit registration
                if "Step(id='finalize'" in content or 'id="finalize"' in content:
                    # Check if finalize_submit would be expected but doesn't exist
                    # BUT: Modern workflows often handle POST in finalize() method instead of finalize_submit()
                    # So only flag this as an issue if there's no evidence of proper finalize() POST handling
                    has_finalize_submit = 'async def finalize_submit(' in content
                    has_finalize_method = 'async def finalize(' in content
                    finalize_handles_post = has_finalize_method and ('request.method' in content and 'POST' in content)

                    if not has_finalize_submit and not finalize_handles_post:
                        route_registration_issues.append(
                            f"❌ CRITICAL: Route registration expects 'finalize_submit' method but it doesn't exist"
                        )
                        analysis["coding_assistant_prompts"].append(
                            f"Add missing finalize_submit method to {filename}:\n"
                            f"The dynamic route registration loop creates a finalize_submit handler when 'finalize' is in steps, but the method doesn't exist.\n\n"
                            f"SOLUTION 1 - Add the missing method:\n"
                            f"```python\n"
                            f"async def finalize_submit(self, request):\n"
                            f"    pip, db, app_name = self.pipulate, self.pipulate.db, self.app_name\n"
                            f"    pipeline_id = pip.db.get('pipeline_id', 'unknown')\n"
                            f"    \n"
                            f"    await pip.set_step_data(pipeline_id, 'finalize', {{'finalized': True}}, self.steps)\n"
                            f"    await self.message_queue.add(pip, 'Workflow finalized.', verbatim=True)\n"
                            f"    return pip.run_all_cells(app_name, self.steps)\n"
                            f"```\n\n"
                            f"SOLUTION 2 - Exclude finalize from dynamic registration:\n"
                            f"```python\n"
                            f"for step in steps:\n"
                            f"    step_id = step.id\n"
                            f"    routes.append((f'/{{app_name}}/{{step_id}}', getattr(self, step_id)))\n"
                            f"    if step_id != 'finalize':  # Only data steps have explicit _submit handlers\n"
                            f"        routes.append((f'/{{app_name}}/{{step_id}}_submit', getattr(self, f'{{step_id}}_submit'), ['POST']))\n"
                            f"```\n\n"
                            f"SOLUTION 3 - Handle POST in finalize() method (RECOMMENDED):\n"
                            f"```python\n"
                            f"async def finalize(self, request):\n"
                            f"    pip, db, app_name = self.pipulate, self.pipulate.db, self.app_name\n"
                            f"    pipeline_id = pip.db.get('pipeline_id', 'unknown')\n"
                            f"    \n"
                            f"    if request.method == 'GET':\n"
                            f"        # Handle GET request (show finalize form)\n"
                            f"        return Card(H3('Ready to finalize?'), ...)\n"
                            f"    else:  # POST\n"
                            f"        # Handle finalization\n"
                            f"        await pip.finalize_workflow(pipeline_id)\n"
                            f"        return pip.run_all_cells(app_name, self.steps)\n"
                            f"```"
                        )

            # Check for step handler registration mismatches
            step_submit_patterns = re.findall(r'(\w+)_submit', init_content)
            for step_submit in step_submit_patterns:
                if f'async def {step_submit}_submit(' not in content:
                    route_registration_issues.append(
                        f"❌ Route registration expects '{step_submit}_submit' method but it doesn't exist"
                    )
                    analysis["coding_assistant_prompts"].append(
                        f"Add missing {step_submit}_submit method to {filename}:\n"
                        f"The route registration expects this handler but it doesn't exist.\n\n"
                        f"Add this method to the class:\n\n"
                        f"```python\n"
                        f"async def {step_submit}_submit(self, request):\n"
                        f"    pip, steps, app_name = (self.pipulate, self.steps, self.app_name)\n"
                        f"    step_id = '{step_submit}'\n"
                        f"    step_index = self.steps_indices[step_id]\n"
                        f"    pipeline_id = pip.db.get('pipeline_id', 'unknown')\n"
                        f"    \n"
                        f"    form = await request.form()\n"
                        f"    # Process form data here\n"
                        f"    user_input = form.get('field_name', '').strip()\n"
                        f"    \n"
                        f"    # Store step data\n"
                        f"    await pip.set_step_data(pipeline_id, step_id, user_input, steps)\n"
                        f"    \n"
                        f"    return pip.chain_reverter(step_id, step_index, steps, app_name, user_input)\n"
                        f"```"
                    )

            # Check for getattr patterns that might fail
            getattr_patterns = re.findall(r'getattr\(self, [\'"]([^\'"]+)[\'"]', init_content)
            for method_name in getattr_patterns:
                if f'async def {method_name}(' not in content and f'def {method_name}(' not in content:
                    route_registration_issues.append(
                        f"❌ getattr() expects '{method_name}' method but it doesn't exist"
                    )

        # Add route registration issues to the main issues list
        if route_registration_issues:
            analysis["issues"].extend(route_registration_issues)
            analysis["recommendations"].append("Fix route registration mismatches - add missing handler methods")

        # Template Assembly Marker Analysis
        steps_insertion_marker = "--- STEPS_LIST_INSERTION_POINT ---"
        methods_insertion_marker = "--- STEP_METHODS_INSERTION_POINT ---"

        has_steps_marker = steps_insertion_marker in content
        has_methods_marker = methods_insertion_marker in content

        # NEW: Check for bundle markers (modern template pattern)
        class_attributes_bundle_start = "--- START_CLASS_ATTRIBUTES_BUNDLE ---"
        class_attributes_bundle_end = "--- END_CLASS_ATTRIBUTES_BUNDLE ---"
        has_class_attributes_bundle = class_attributes_bundle_start in content and class_attributes_bundle_end in content

        if has_steps_marker:
            analysis["patterns_found"].append("✅ STEPS_LIST_INSERTION_POINT marker found")
        else:
            analysis["template_suitability"]["missing_requirements"].append("STEPS_LIST_INSERTION_POINT marker")
            analysis["issues"].append("❌ Missing STEPS_LIST_INSERTION_POINT marker (template compatibility)")
            analysis["coding_assistant_prompts"].append(
                f"Add STEPS_LIST_INSERTION_POINT marker to {filename}:\n"
                f"In the self.steps definition, add the marker before the finalize step:\n\n"
                f"```python\n"
                f"self.steps = [\n"
                f"    Step(id='step_01', done='data_01', show='Step 1', refill=False),\n"
                f"    Step(id='step_02', done='data_02', show='Step 2', refill=False),\n"
                f"    # Add any other existing steps here\n"
                f"    {steps_insertion_marker}\n"
                f"    Step(id='finalize', done='finalized', show='Finalize Workflow', refill=False)\n"
                f"]\n"
                f"```\n\n"
                f"CRITICAL: The marker must be at the same indentation level as the Step definitions and placed immediately before the finalize step."
            )

        # UPDATED: Methods marker is now OPTIONAL for modern workflows
        if has_methods_marker:
            analysis["patterns_found"].append("✅ STEP_METHODS_INSERTION_POINT marker found")
        else:
            # Check if this is a modern workflow using centralized route registration
            uses_centralized_routes = 'pipulate.register_workflow_routes(self)' in content
            if not uses_centralized_routes:
                analysis["template_suitability"]["missing_requirements"].append("STEP_METHODS_INSERTION_POINT marker")
                analysis["issues"].append("❌ Missing STEP_METHODS_INSERTION_POINT marker (template compatibility)")
                analysis["coding_assistant_prompts"].append(
                    f"Add STEP_METHODS_INSERTION_POINT marker to {filename}:\n"
                    f"At the end of the class, after all existing step methods, add:\n\n"
                    f"```python\n"
                    f"class YourWorkflow:\n"
                    f"    # ... existing methods ...\n"
                    f"    \n"
                    f"    async def existing_step_method(self, request):\n"
                    f"        # ... existing implementation ...\n"
                    f"        pass\n"
                    f"    \n"
                    f"    {methods_insertion_marker}\n"
                    f"```\n\n"
                    f"CRITICAL: The marker must be at class level (4 spaces indentation) and placed after all existing step methods but before the class ends."
                )
            else:
                analysis["patterns_found"].append("✅ Modern workflow using centralized route registration (methods marker optional)")

        # NEW: Class Attributes Bundle Analysis
        if has_class_attributes_bundle:
            analysis["patterns_found"].append("✅ CLASS_ATTRIBUTES_BUNDLE markers found (modern template pattern)")
        else:
            # Only suggest if workflow has other template markers (indicating it's meant to be a template)
            if has_steps_marker:
                analysis["recommendations"].append("Consider adding CLASS_ATTRIBUTES_BUNDLE markers for advanced template assembly")
                analysis["coding_assistant_prompts"].append(
                    f"Add CLASS_ATTRIBUTES_BUNDLE markers to {filename} for advanced template compatibility:\n"
                    f"Add these markers in the class definition after other constants:\n\n"
                    f"```python\n"
                    f"class YourWorkflow:\n"
                    f"    APP_NAME = 'your_app'\n"
                    f"    DISPLAY_NAME = 'Your Workflow'\n"
                    f"    # ... other constants ...\n"
                    f"    \n"
                    f"    {class_attributes_bundle_start}\n"
                    f"    # Additional class-level constants can be merged here by manage_class_attributes.py\n"
                    f"    {class_attributes_bundle_end}\n"
                    f"    \n"
                    f"    def __init__(self, ...):\n"
                    f"        # ... existing code ...\n"
                    f"```"
                )

        # Standard class attributes check
        required_attributes = ["APP_NAME", "DISPLAY_NAME", "ENDPOINT_MESSAGE", "TRAINING_PROMPT"]
        missing_attributes = []

        for attr in required_attributes:
            if f'{attr} =' in content:
                analysis["patterns_found"].append(f"✅ {attr} attribute found")
            else:
                missing_attributes.append(attr)
                analysis["template_suitability"]["missing_requirements"].append(f"{attr} class attribute")
                analysis["issues"].append(f"❌ Missing {attr} class attribute (template compatibility)")

        if missing_attributes:
            analysis["coding_assistant_prompts"].append(
                f"Add missing class attributes to {filename}:\n"
                f"Add these attributes at the top of the class definition:\n\n"
                f"```python\n"
                f"class YourWorkflow:\n" +
                ''.join([
                    f"    {attr} = 'your_{attr.lower()}_value'  # Replace with appropriate value\n"
                    for attr in missing_attributes
                ]) +
                f"    \n"
                f"    def __init__(self, ...):\n"
                f"        # ... existing code ...\n"
                f"```\n\n"
                f"Replace the placeholder values:\n" +
                '\n'.join([
                    f"- {attr}: " + {
                        'APP_NAME': 'Internal workflow ID (stable, never change after deployment)',
                        'DISPLAY_NAME': 'User-facing workflow name',
                        'ENDPOINT_MESSAGE': 'Description shown on landing page',
                        'TRAINING_PROMPT': 'LLM context prompt for this workflow'
                    }.get(attr, 'Appropriate value for this attribute')
                    for attr in missing_attributes
                ])
            )

        # UPDATED: UI Constants check - handle both patterns
        has_local_ui_constants = 'UI_CONSTANTS' in content and 'UI_CONSTANTS = {' in content
        has_centralized_ui = 'pip.get_ui_constants()' in content or 'self.ui = ' in content

        if has_local_ui_constants:
            analysis["patterns_found"].append("✅ Local UI_CONSTANTS for styling found")
        elif has_centralized_ui:
            analysis["patterns_found"].append("✅ Centralized UI constants via pipulate.get_ui_constants() (modern pattern)")
        else:
            analysis["template_suitability"]["missing_requirements"].append("UI constants (local or centralized)")
            analysis["issues"].append("❌ Missing UI constants (template compatibility)")
            analysis["coding_assistant_prompts"].append(
                f"Add UI constants to {filename}:\n"
                f"OPTION 1 - Local UI constants (classic pattern):\n"
                f"```python\n"
                f"class YourWorkflow:\n"
                f"    UI_CONSTANTS = {{\n"
                f"        'COLORS': {{\n"
                f"            'HEADER_TEXT': '#2c3e50',\n"
                f"            'BODY_TEXT': '#5a6c7d',\n"
                f"            'ACCENT_BLUE': '#007bff',\n"
                f"            'SUCCESS_GREEN': '#28a745',\n"
                f"        }},\n"
                f"        'BACKGROUNDS': {{\n"
                f"            'LIGHT_GRAY': '#f1f5f9',\n"
                f"            'LIGHT_BLUE': '#f0f8ff',\n"
                f"        }},\n"
                f"        'SPACING': {{\n"
                f"            'SECTION_PADDING': '0.75rem',\n"
                f"            'BORDER_RADIUS': '4px',\n"
                f"            'MARGIN_BOTTOM': '1rem',\n"
                f"        }}\n"
                f"    }}\n"
                f"```\n\n"
                f"OPTION 2 - Centralized UI constants (modern pattern):\n"
                f"```python\n"
                f"def __init__(self, app, pipulate, pipeline, db, app_name=None):\n"
                f"    # ... existing code ...\n"
                f"    self.ui = pip.get_ui_constants()  # Access centralized UI constants\n"
                f"    # ... rest of init ...\n"
                f"```"
            )

        # NEW: COMPREHENSIVE TRANSPLANTATION ANALYSIS
        # ===========================================
        transplant_analysis = analysis["transplantation_analysis"]

        # Find all swappable step methods with proper markers
        swappable_steps = []
        step_dependencies = {}

        # Look for both SWAPPABLE_STEP and STEP_BUNDLE markers
        swappable_patterns = [
            r'# --- START_SWAPPABLE_STEP: (step_\d+) ---',
            r'# --- START_STEP_BUNDLE: (step_\d+) ---'
        ]

        for pattern in swappable_patterns:
            matches = re.findall(pattern, content)
            for step_id in matches:
                if step_id not in swappable_steps:
                    swappable_steps.append(step_id)

        # Find step methods even without markers (potential for transplantation after adding markers)
        step_method_pattern = r'async def (step_\d+)(?:_submit)?\('
        step_methods = re.findall(step_method_pattern, content)
        potential_steps = list(set(step_methods))  # Remove duplicates

        # Analyze each step for dependencies and transplantability
        for step_id in potential_steps:
            # Extract the step method content to analyze dependencies
            step_start_pattern = rf'async def {step_id}\('
            step_submit_pattern = rf'async def {step_id}_submit\('

            # Find the step method bounds
            step_content = ""
            lines = content.split('\n')

            in_step_method = False
            step_method_indent = None

            for i, line in enumerate(lines):
                if re.search(step_start_pattern, line):
                    in_step_method = True
                    step_method_indent = len(line) - len(line.lstrip())
                    step_content += line + '\n'
                elif in_step_method:
                    current_indent = len(line) - len(line.lstrip()) if line.strip() else 999
                    # Continue if we're still inside the method (proper indentation or empty line)
                    if line.strip() == '' or current_indent > step_method_indent:
                        step_content += line + '\n'
                    else:
                        # We've reached the next method
                        break

            # Also get the submit method if it exists
            if f'async def {step_id}_submit(' in content:
                in_submit_method = False
                submit_method_indent = None

                for i, line in enumerate(lines):
                    if re.search(step_submit_pattern, line):
                        in_submit_method = True
                        submit_method_indent = len(line) - len(line.lstrip())
                        step_content += line + '\n'
                    elif in_submit_method:
                        current_indent = len(line) - len(line.lstrip()) if line.strip() else 999
                        if line.strip() == '' or current_indent > submit_method_indent:
                            step_content += line + '\n'
                        else:
                            break

            # Analyze dependencies in the step content
            dependencies = []

            # Check for self.UPPER_CASE class constants
            class_constants = re.findall(r'self\.([A-Z][A-Z_]+)', step_content)
            dependencies.extend([f"self.{const}" for const in set(class_constants)])

            # Check for specialized methods or attributes
            specialized_methods = re.findall(r'self\.([a-z_]+[a-z0-9_]*)\(', step_content)
            specialized_attrs = re.findall(r'self\.([a-z_]+[a-z0-9_]*)', step_content)

            # Filter out common workflow methods that should be available everywhere
            common_methods = {
                'pipulate', 'db', 'steps', 'app_name', 'message_queue', 'steps_indices',
                'get_step_data', 'set_step_data', 'read_state', 'write_state'
            }

            specialized = set(specialized_methods + specialized_attrs) - common_methods
            dependencies.extend([f"self.{method}" for method in specialized])

            # Check for external imports or specialized functionality
            external_deps = []
            if 'matplotlib' in step_content.lower():
                external_deps.append('matplotlib library')
            if 'base64' in step_content.lower():
                external_deps.append('base64 encoding')
            if 'json' in step_content.lower():
                external_deps.append('JSON processing')
            if 'upload' in step_content.lower() or 'file' in step_content.lower():
                external_deps.append('file handling')
            if 'checkbox' in step_content.lower() or 'fieldset' in step_content.lower():
                external_deps.append('checkbox UI components')

            dependencies.extend(external_deps)

            step_dependencies[step_id] = {
                'class_dependencies': [dep for dep in dependencies if dep.startswith('self.')],
                'external_dependencies': [dep for dep in dependencies if not dep.startswith('self.')],
                'has_swappable_markers': step_id in swappable_steps,
                'self_contained': len([dep for dep in dependencies if dep.startswith('self.') and not any(common in dep for common in ['pipulate', 'db', 'steps', 'app_name'])]) == 0
            }

        # Generate transplant commands for each viable step
        transplant_commands = []
        compatibility_warnings = []

        source_filename = filename

        for step_id in potential_steps:
            step_info = step_dependencies.get(step_id, {})

            # Generate command for swapping this step to a target workflow
            command = f"python helpers/workflow/swap_workflow_step.py TARGET_FILE.py {step_id} apps/{source_filename} {step_id} --force"

            compatibility_notes = []
            if not step_info.get('has_swappable_markers', False):
                compatibility_notes.append("⚠️ Needs swappable step markers added first")
            if not step_info.get('self_contained', True):
                compatibility_notes.append("⚠️ Has class dependencies that may not exist in target")
            if step_info.get('external_dependencies'):
                deps = ', '.join(step_info['external_dependencies'])
                compatibility_notes.append(f"⚠️ Requires: {deps}")

            transplant_commands.append({
                'step_id': step_id,
                'command': command,
                'compatibility': 'Good' if len(compatibility_notes) == 0 else 'Needs Work',
                'notes': compatibility_notes,
                'dependencies': step_info
            })

        # Store results
        transplant_analysis['swappable_steps'] = swappable_steps
        transplant_analysis['step_dependencies'] = step_dependencies
        transplant_analysis['transplant_commands'] = transplant_commands

        # Generate compatibility warnings
        if len(swappable_steps) == 0 and len(potential_steps) > 0:
            transplant_analysis['compatibility_warnings'].append(
                "No swappable step markers found. Add START_SWAPPABLE_STEP/END_SWAPPABLE_STEP markers to enable transplantation."
            )

        high_dependency_steps = [
            step_id for step_id, info in step_dependencies.items()
            if len(info.get('class_dependencies', [])) > 3
        ]
        if high_dependency_steps:
            transplant_analysis['compatibility_warnings'].append(
                f"Steps with many dependencies may not transplant cleanly: {', '.join(high_dependency_steps)}"
            )

        # Step method naming convention check
        step_methods = re.findall(r'async def (step_\d+)(?:_submit)?\(', content)
        if step_methods:
            analysis["patterns_found"].append(f"✅ Step methods found: {len(set(step_methods))} unique steps")
            # Check for proper step pairs (GET and POST handlers)
            step_numbers = set(re.findall(r'step_(\d+)', ' '.join(step_methods)))
            missing_handlers = []
            for num in step_numbers:
                has_get = f'step_{num}(' in content
                has_post = f'step_{num}_submit(' in content
                if has_get and has_post:
                    analysis["patterns_found"].append(f"✅ Step {num} has both GET and POST handlers")
                else:
                    missing_type = 'GET' if not has_get else 'POST'
                    analysis["issues"].append(f"❌ Step {num} missing {missing_type} handler")
                    missing_handlers.append((num, missing_type))

            if missing_handlers:
                handler_code = []
                for num, handler_type in missing_handlers:
                    if handler_type == 'GET':
                        handler_code.append(f"""

    async def step_{num}(self, request):
        pip, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_{num}'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = pip.db.get('pipeline_id', 'unknown')
        state = pip.read_state(pipeline_id)
        step_data = pip.get_step_data(pipeline_id, step_id, {{}})
        user_val = step_data.get(step.done, '')
        finalize_data = pip.get_step_data(pipeline_id, 'finalize', {{}})

        if 'finalized' in finalize_data:
            return Div(
                Card(H3(f'🔒 {{step.show}}: Complete')),
                Div(id=next_step_id, hx_get=f'/{{app_name}}/{{next_step_id}}', hx_trigger='load'),
                id=step_id
            )
        elif user_val and state.get('_revert_target') != step_id:
            return pip.chain_reverter(step_id, step_index, steps, app_name, user_val)
        else:
            return Div(
                Card(
                    H3(f'{{step.show}}'),
                    P('Step implementation needed here.'),
                    Form(
                        # Add your form fields here
                        Button('Submit ▸', type='submit'),
                        hx_post=f'/{{app_name}}/{{step_id}}_submit',
                        hx_target=f'#{{step_id}}'
                    )
                ),
                Div(id=next_step_id),
                id=step_id
            )""")
                    else:  # POST handler
                        handler_code.append(f"""

    async def step_{num}_submit(self, request):
        pip, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_{num}'
        step_index = self.steps_indices[step_id]
        pipeline_id = pip.db.get('pipeline_id', 'unknown')

        form = await request.form()
        # Process form data here
        user_input = form.get('field_name', '').strip()

        # Store step data
        await pip.set_step_data(pipeline_id, step_id, user_input, steps)

        return pip.chain_reverter(step_id, step_index, steps, app_name, user_input)\n""")

                analysis["coding_assistant_prompts"].append(
                    f"Add missing step handlers to {filename}:\n"
                    f"Add these missing method(s):\n\n"
                    f"```python" + ''.join(handler_code) + "\n```"
                )

        # Finalize step check
        if 'finalize(' in content:
            analysis["patterns_found"].append("✅ Finalize step handler found")
        else:
            analysis["issues"].append("❌ Missing finalize step handler")
            analysis["recommendations"].append("Add finalize step handler for workflow completion")
            analysis["coding_assistant_prompts"].append(
                f"Add finalize step handler to {filename}:\n"
                f"Add this method to handle workflow finalization:\n\n"
                f"```python\n"
                f"async def finalize(self, request):\n"
                f"    pip, db, app_name = self.pipulate, self.pipulate.db, self.APP_NAME\n"
                f"    pipeline_id = pip.db.get('pipeline_id', 'unknown')\n"
                f"    \n"
                f"    if request.method == 'POST':\n"
                f"        await pip.set_step_data(pipeline_id, 'finalize', {{'finalized': True}}, self.steps)\n"
                f"        await self.message_queue.add(pip, 'Workflow finalized.', verbatim=True)\n"
                f"        return pip.run_all_cells(app_name, self.steps)\n"
                f"    \n"
                f"    finalize_data = pip.get_step_data(pipeline_id, 'finalize', {{}})\n"
                f"    if 'finalized' in finalize_data:\n"
                f"        return Card(\n"
                f"            H3('🔒 Workflow Finalized'),\n"
                f"            P('This workflow is complete.'),\n"
                f"            Form(\n"
                f"                Button('🔓 Unfinalize', type='submit', cls='secondary'),\n"
                f"                hx_post=f'/{{app_name}}/unfinalize',\n"
                f"                hx_target=f'#{{app_name}}-container'\n"
                f"            ),\n"
                f"            id='finalize'\n"
                f"        )\n"
                f"    else:\n"
                f"        return Card(\n"
                f"            H3('Finalize Workflow'),\n"
                f"            P('Complete this workflow.'),\n"
                f"            Form(\n"
                f"                Button('🔒 Finalize', type='submit', cls='primary'),\n"
                f"                hx_post=f'/{{app_name}}/finalize',\n"
                f"                hx_target=f'#{{app_name}}-container'\n"
                f"            ),\n"
                f"            id='finalize'\n"
                f"        )\n"
                f"```"
            )

        # Template Suitability Assessment
        suitability = analysis["template_suitability"]

        # Template Source Requirements: markers + attributes + UI_CONSTANTS
        if has_steps_marker and has_methods_marker and len(missing_attributes) == 0:
            suitability["as_template_source"] = True
            analysis["patterns_found"].append("🎯 SUITABLE AS TEMPLATE SOURCE")
        else:
            analysis["recommendations"].append("To use as template source: Add missing markers and class attributes")

        # Splice Target Requirements: both markers required
        if has_steps_marker and has_methods_marker:
            suitability["as_splice_target"] = True
            analysis["patterns_found"].append("🔧 SUITABLE AS SPLICE TARGET")
        else:
            analysis["recommendations"].append("To use as splice target: Add both insertion point markers")

        # Swap Target Requirements: must have step methods to replace
        if step_methods:
            suitability["as_swap_target"] = True
            analysis["patterns_found"].append("🔄 SUITABLE AS SWAP TARGET")
        else:
            suitability["as_swap_target"] = False
            analysis["recommendations"].append("To use as swap target: Add step methods with proper naming")

        # Enhanced Swap Source Assessment
        if transplant_commands:
            good_transplants = [cmd for cmd in transplant_commands if cmd['compatibility'] == 'Good']
            needs_work_transplants = [cmd for cmd in transplant_commands if cmd['compatibility'] == 'Needs Work']

            if good_transplants:
                analysis["patterns_found"].append(f"🔀 EXCELLENT SWAP SOURCE: {len(good_transplants)} ready-to-transplant step(s)")
            elif needs_work_transplants:
                analysis["patterns_found"].append(f"🔀 POTENTIAL SWAP SOURCE: {len(needs_work_transplants)} step(s) need preparation")
                suitability["as_swap_source"] = False  # Override default
                suitability["missing_requirements"].append("Swappable step markers and/or dependency resolution")
            else:
                suitability["as_swap_source"] = False
                analysis["issues"].append("❌ No viable steps for swapping found")

        # Atomic Transplantation Markers (Optional)
        atomic_markers = [
            "START_WORKFLOW_SECTION:",
            "SECTION_STEP_DEFINITION",
            "END_SECTION_STEP_DEFINITION",
            "SECTION_STEP_METHODS",
            "END_SECTION_STEP_METHODS",
            "END_WORKFLOW_SECTION"
        ]

        found_atomic_markers = [marker for marker in atomic_markers if marker in content]
        if found_atomic_markers:
            analysis["patterns_found"].append(f"✅ Atomic transplantation markers: {len(found_atomic_markers)}/6")
            if len(found_atomic_markers) == 6:
                analysis["patterns_found"].append("🧬 SUITABLE FOR ATOMIC TRANSPLANTATION")

        # ARIA and Automation Validation
        aria_validation = self.validate_aria_and_automation(content, str(file_path))
        analysis["automation_readiness"] = aria_validation
        
        # Integrate ARIA findings into main analysis
        if not aria_validation['automation_ready']:
            analysis["issues"].extend([f"🤖 AUTOMATION: {issue}" for issue in aria_validation['aria_issues']])
            
        if aria_validation['selenium_readiness'] == 'poor':
            analysis["issues"].append(f"⚠️ AUTOMATION: Poor Selenium compatibility detected")
        elif aria_validation['selenium_readiness'] == 'fair':
            analysis["recommendations"].append(f"🔧 AUTOMATION: Review UI elements for better automation support")
        
        # Add ARIA recommendations to main recommendations
        analysis["recommendations"].extend([f"🎯 {rec}" for rec in aria_validation['aria_recommendations']])
        
        # Add automation summary to patterns found
        if aria_validation['automation_ready']:
            analysis["patterns_found"].append(f"✅ AUTOMATION READY: Score {aria_validation['accessibility_score']}/100")
        else:
            analysis["patterns_found"].append(f"❌ AUTOMATION ISSUES: Score {aria_validation['accessibility_score']}/100")

        return analysis

    async def search_apps_step01(self, request):
        """Search plugins for step 1 based on user input - Carson Gross style active search."""
        try:
            form = await request.form()
            search_term = form.get('plugin_search', '').strip().lower()
            
            # Get list of plugin files
            apps_dir = Path("apps")
            plugin_files = []
            if apps_dir.exists():
                plugin_files = [f.name for f in apps_dir.glob("*.py") if not f.name.startswith("__")]
            
            # Filter plugins based on search term
            if search_term:
                filtered_plugins = []
                for plugin_file in plugin_files:
                    # Search in filename (remove numeric prefix and extension for display)
                    clean_name = re.sub(r'^\d+_', '', plugin_file.replace('.py', '').replace('_', ' ')).title()
                    if (search_term in plugin_file.lower() or 
                        search_term in clean_name.lower()):
                        filtered_plugins.append({
                            'filename': plugin_file,
                            'display_name': clean_name,
                            'module_name': plugin_file.replace('.py', '')
                        })
            else:
                # Show ALL plugins on empty search (dropdown menu behavior)
                filtered_plugins = []
                for plugin_file in plugin_files:
                    clean_name = re.sub(r'^\d+_', '', plugin_file.replace('.py', '').replace('_', ' ')).title()
                    filtered_plugins.append({
                        'filename': plugin_file,
                        'display_name': clean_name,
                        'module_name': plugin_file.replace('.py', '')
                    })
            
            # Generate HTML results
            if filtered_plugins:
                result_html = ""
                # Check if there's only one result for auto-selection
                auto_select_single = len(filtered_plugins) == 1
                
                for i, plugin in enumerate(sorted(filtered_plugins, key=lambda x: x['filename'])):  # Show all results - no artificial limit
                    # Add auto-select class for single results
                    item_class = "search-result-item"
                    if auto_select_single:
                        item_class += " auto-select-single"
                        
                    # Properly escape JavaScript parameters to handle quotes and special characters
                    escaped_filename = plugin['filename'].replace("'", "\\'").replace('"', '\\"')
                    escaped_display_name = plugin['display_name'].replace("'", "\\'").replace('"', '\\"')
                    
                    result_html += f"""
                    <div class="search-result-item" 
                         onclick="document.getElementById('plugin-search-results-step_01').style.display='none'; window.selectDevAssistantPlugin('{escaped_filename}', '{escaped_display_name}');"
                         onmouseover="this.classList.remove('selected');">
                        <strong>{plugin['display_name']}</strong>
                        <div class="search-result-module">{plugin['filename']}</div>
                    </div>
                    """
                
                # Show dropdown with JavaScript - same as nav search
                result_html += """
                <script>
                    document.getElementById('plugin-search-results-step_01').style.display = 'block';
                </script>
                """
            else:
                # No results or empty search - hide dropdown - same as nav search
                result_html = """
                <script>
                    document.getElementById('plugin-search-results-step_01').style.display = 'none';
                </script>
                """
            
            return HTMLResponse(result_html)
            
        except Exception as e:
            logger.error(f"Error in search_apps_step01: {e}")
            return HTMLResponse(f"""
            <div style="padding: 1rem; color: var(--pico-form-element-invalid-active-border-color);">
                Search error: {str(e)}
            </div>
            """)

    def generate_create_workflow_commands(self, analysis_results):
        """Generate create_workflow.py commands for creating a new version of the analyzed plugin."""
        filename = analysis_results.get('filename', 'unknown.py')
        file_path = Path("apps") / filename
        
        if not file_path.exists():
            return [P('Plugin file not found for command generation.', style=f'color: {self.UI_CONSTANTS["COLORS"]["ERROR_RED"]};')]
        
        content = file_path.read_text()
        
        # Extract current plugin attributes
        extracted_data = self.extract_plugin_attributes(content, filename)
        
        if extracted_data.get('error'):
            return [P(f'Error extracting plugin data: {extracted_data["error"]}', style=f'color: {self.UI_CONSTANTS["COLORS"]["ERROR_RED"]};')]
        
        # Generate next version filename
        next_filename = self.generate_next_version_filename(filename)
        
        # Create version 2 data by appending "2" to avoid collisions
        version_data = {
            'class_name': extracted_data['class_name'] + '2',
            'app_name': extracted_data['app_name'] + '2',
            'display_name': extracted_data['display_name'] + ' 2',
            'endpoint_message': extracted_data['endpoint_message'],
            'training_prompt': extracted_data['training_prompt']
        }
        
        # Format bash command arguments (from workflow_genesis.py)
        def format_bash_command(text):
            if not text:
                return '""'
            text = text.replace('!', '\\!')
            text = text.replace('"', '\\"')
            if ' ' in text or '"' in text or "'" in text:
                return f'"{text}"'
            return text
        
        # Generate commands for different templates
        commands = []
        
        # Default: Blank template (generic use)
        blank_cmd = f"python helpers/workflow/create_workflow.py apps/{next_filename} {version_data['class_name']} {version_data['app_name']} \\\n" + \
                   f"  {format_bash_command(version_data['display_name'])} \\\n" + \
                   f"  {format_bash_command(version_data['endpoint_message'])} \\\n" + \
                   f"  {format_bash_command(version_data['training_prompt'])} \\\n" + \
                   f"  --template blank --role Core --force"
        
        # Hello template option
        hello_cmd = f"python helpers/workflow/create_workflow.py apps/{next_filename} {version_data['class_name']} {version_data['app_name']} \\\n" + \
                   f"  {format_bash_command(version_data['display_name'])} \\\n" + \
                   f"  {format_bash_command(version_data['endpoint_message'])} \\\n" + \
                   f"  {format_bash_command(version_data['training_prompt'])} \\\n" + \
                   f"  --template hello --role Core --force"
        
        # Trifecta template option
        trifecta_cmd = f"python helpers/workflow/create_workflow.py apps/{next_filename} {version_data['class_name']} {version_data['app_name']} \\\n" + \
                       f"  {format_bash_command(version_data['display_name'])} \\\n" + \
                       f"  {format_bash_command(version_data['endpoint_message'])} \\\n" + \
                       f"  {format_bash_command(version_data['training_prompt'])} \\\n" + \
                       f"  --template trifecta --role Core --force"
        
        return [
            P(f'Generate commands to create a new version of {filename} as {next_filename}:',
              style=f'margin-bottom: 1rem; font-weight: bold; color: {self.UI_CONSTANTS["COLORS"]["BODY_TEXT"]};'),
            
            # Extracted data summary
            Div(
                H5('📋 Version 2 Plugin Data:', style=f'color: {self.UI_CONSTANTS["COLORS"]["INFO_BLUE"]}; margin-bottom: 0.5rem;'),
                Div(
                    Div(
                        Strong('Original → Version 2:', style=f'color: {self.UI_CONSTANTS["COLORS"]["BODY_TEXT"]}; display: block; margin-bottom: 0.5rem;'),
                        Ul(
                            Li(f"Class: {extracted_data['class_name']} → {version_data['class_name']}"),
                            Li(f"App: {extracted_data['app_name']} → {version_data['app_name']}"),
                            Li(f"Display: {extracted_data['display_name']} → {version_data['display_name']}"),
                            Li(f"File: {filename} → {next_filename}"),
                            style=f'color: {self.UI_CONSTANTS["COLORS"]["BODY_TEXT"]}; margin-bottom: 0.5rem;'
                        ),
                    ),
                    P('💡 The "2" suffix avoids collisions and allows parallel versions for graceful upgrades.',
                      style=f'color: {self.UI_CONSTANTS["COLORS"]["INFO_TEAL"]}; font-style: italic; font-size: 0.9rem; margin-bottom: 0;')
                ),
                style=f'background-color: {self.UI_CONSTANTS["BACKGROUNDS"]["SUCCESS_OVERLAY"]}; padding: 1rem; border-radius: {self.UI_CONSTANTS["SPACING"]["BORDER_RADIUS"]}; margin-bottom: 1.5rem;'
            ),
            
            # Default: Blank template
            Div(
                H5('🎯 Blank Template (Default - Generic Use):', style=f'color: {self.UI_CONSTANTS["COLORS"]["SUCCESS_GREEN"]}; margin-bottom: 0.5rem;'),
                P('Single-step workflow for learning step management and customization.',
                  style=f'color: {self.UI_CONSTANTS["COLORS"]["BODY_TEXT"]}; font-size: 0.9rem; margin-bottom: 0.5rem;'),
                Pre(
                    Code(blank_cmd, cls='language-bash'),
                    cls='language-bash',
                    style=f'background-color: {self.UI_CONSTANTS["COLORS"]["CODE_BG_DARK"]}; color: {self.UI_CONSTANTS["COLORS"]["CODE_TEXT_LIGHT"]}; padding: 1rem; border-radius: {self.UI_CONSTANTS["SPACING"]["BORDER_RADIUS"]}; overflow-x: auto; position: relative; border-left: 4px solid {self.UI_CONSTANTS["COLORS"]["SUCCESS_GREEN"]};'
                ),
                style='margin-bottom: 1.5rem;'
            ),
            
            # Hello template option
            Div(
                H5('👋 Hello Template (Multi-step Recreation):', style=f'color: {self.UI_CONSTANTS["COLORS"]["INFO_BLUE"]}; margin-bottom: 0.5rem;'),
                P('Multi-step process demonstrating helper tool sequence and workflow construction.',
                  style=f'color: {self.UI_CONSTANTS["COLORS"]["BODY_TEXT"]}; font-size: 0.9rem; margin-bottom: 0.5rem;'),
                Pre(
                    Code(hello_cmd, cls='language-bash'),
                    cls='language-bash',
                    style=f'background-color: {self.UI_CONSTANTS["COLORS"]["CODE_BG_DARK"]}; color: {self.UI_CONSTANTS["COLORS"]["CODE_TEXT_LIGHT"]}; padding: 1rem; border-radius: {self.UI_CONSTANTS["SPACING"]["BORDER_RADIUS"]}; overflow-x: auto; position: relative; border-left: 4px solid {self.UI_CONSTANTS["COLORS"]["INFO_BLUE"]};'
                ),
                style='margin-bottom: 1.5rem;'
            ),
            
            # Trifecta template option
            Div(
                H5('🏇 Trifecta Template (Complex Workflow):', style=f'color: {self.UI_CONSTANTS["COLORS"]["ACCENT_PURPLE"]}; margin-bottom: 0.5rem;'),
                P('Complex 5-step workflow from Botify template for sophisticated data collection scenarios.',
                  style=f'color: {self.UI_CONSTANTS["COLORS"]["BODY_TEXT"]}; font-size: 0.9rem; margin-bottom: 0.5rem;'),
                Pre(
                    Code(trifecta_cmd, cls='language-bash'),
                    cls='language-bash',
                    style=f'background-color: {self.UI_CONSTANTS["COLORS"]["CODE_BG_DARK"]}; color: {self.UI_CONSTANTS["COLORS"]["CODE_TEXT_LIGHT"]}; padding: 1rem; border-radius: {self.UI_CONSTANTS["SPACING"]["BORDER_RADIUS"]}; overflow-x: auto; position: relative; border-left: 4px solid {self.UI_CONSTANTS["COLORS"]["ACCENT_PURPLE"]};'
                ),
                style='margin-bottom: 1rem;'
            ),
            
            # Usage note
            Div(
                P('💡 Copy any command above to create a new version. The blank template is recommended for general use, while trifecta is perfect for complex data workflows like Parameter Buster or Link Graph Visualizer.',
                  style=f'color: {self.UI_CONSTANTS["COLORS"]["INFO_TEAL"]}; font-style: italic; font-size: 0.9rem;'),
                style=f'background-color: {self.UI_CONSTANTS["BACKGROUNDS"]["WARNING_OVERLAY"]}; padding: 1rem; border-radius: {self.UI_CONSTANTS["SPACING"]["BORDER_RADIUS"]}; border-left: 4px solid {self.UI_CONSTANTS["COLORS"]["INFO_TEAL"]};'
            )
        ]

    def extract_plugin_attributes(self, content, filename):
        """Extract class name, APP_NAME, DISPLAY_NAME, etc. from plugin content."""
        try:
            # Extract class name
            class_match = re.search(r'^class\s+([A-Za-z_][A-Za-z0-9_]*)\s*:', content, re.MULTILINE)
            if not class_match:
                return {"error": "Could not find class definition"}
            
            class_name = class_match.group(1)
            
            # Extract APP_NAME
            app_name_match = re.search(r'APP_NAME\s*=\s*[\'"]([^\'"]+)[\'"]', content)
            app_name = app_name_match.group(1) if app_name_match else self.derive_app_name_from_filename(filename)
            
            # Extract DISPLAY_NAME
            display_name_match = re.search(r'DISPLAY_NAME\s*=\s*[\'"]([^\'"]+)[\'"]', content)
            display_name = display_name_match.group(1) if display_name_match else f"{class_name} Workflow"
            
            # Extract ENDPOINT_MESSAGE (handle both single and triple quotes)
            endpoint_message = "Welcome to this workflow."
            endpoint_single = re.search(r'ENDPOINT_MESSAGE\s*=\s*[\'"]([^\'"]+)[\'"]', content)
            endpoint_triple = re.search(r'ENDPOINT_MESSAGE\s*=\s*[\'\"]{3}(.*?)[\'\"]{3}', content, re.DOTALL)
            
            if endpoint_triple:
                endpoint_message = endpoint_triple.group(1).strip()
            elif endpoint_single:
                endpoint_message = endpoint_single.group(1)
            
            # Extract TRAINING_PROMPT (handle both single and triple quotes)
            training_prompt = f"You are assisting with the {display_name} workflow. Help users understand each step and provide guidance."
            training_single = re.search(r'TRAINING_PROMPT\s*=\s*[\'"]([^\'"]+)[\'"]', content)
            training_triple = re.search(r'TRAINING_PROMPT\s*=\s*[\'\"]{3}(.*?)[\'\"]{3}', content, re.DOTALL)
            
            if training_triple:
                training_prompt = training_triple.group(1).strip()
            elif training_single:
                training_prompt = training_single.group(1)
            
            return {
                'class_name': class_name,
                'app_name': app_name,
                'display_name': display_name,
                'endpoint_message': endpoint_message,
                'training_prompt': training_prompt
            }
            
        except Exception as e:
            return {"error": str(e)}

    def derive_app_name_from_filename(self, filename):
        """Derive app name from filename (e.g., '110_parameter_buster.py' -> 'parameter_buster')."""
        filename_part_no_ext = Path(filename).stem
        return re.sub(r"^\d+_", "", filename_part_no_ext)

    def generate_next_version_filename(self, current_filename):
        """Generate next version filename by appending '2' to avoid collisions."""
        # Extract current number prefix and base name
        match = re.match(r'^(\d+)_(.+)\.py$', current_filename)
        if not match:
            # If no numeric prefix, add one
            base_name = Path(current_filename).stem
            return f"001_{base_name}2.py"
        
        current_num = match.group(1)  # Keep as string to preserve leading zeros
        base_name = match.group(2)
        
        # Append '2' to the base name to create parallel version
        return f"{current_num}_{base_name}2.py"

    async def step_01(self, request):
        # Simplified utility - no pipeline state management needed
        app_name = self.app_name
        step_id = 'step_01'
        
        # Get list of plugin files
        apps_dir = Path("apps")
        plugin_files = []
        if apps_dir.exists():
            plugin_files = [f.name for f in apps_dir.glob("*.py") if not f.name.startswith("__")]

        # Create search results dropdown 
        search_results_dropdown = Div(id=f'plugin-search-results-{step_id}', 
                                    cls='search-dropdown',
                                    style='position: absolute; top: 100%; left: 0; right: 0; z-index: 1000; background: var(--pico-background-color); border: 1px solid var(--pico-muted-border-color); border-radius: 8px; max-height: 300px; overflow-y: auto; display: none;')
        
        return Div(
            Card(
                H3('Plugin Analysis'),
                P('Search and select a plugin file to analyze for pattern compliance and issues:'),
                Form(
                    Div(
                        Input(
                            type='search',
                            name='plugin_search',
                            placeholder='Search plugins by name...',
                            id=f'plugin-search-input-{step_id}',
                            style='width: 100%; border-radius: 8px; margin-bottom: 1rem;',
                            hx_post=f'/{app_name}/search_apps_step01',
                            hx_target=f'#plugin-search-results-{step_id}',
                            hx_trigger='input changed delay:300ms, focus',
                            hx_swap='innerHTML'
                        ),
                        search_results_dropdown,
                        style='position: relative; margin-bottom: 1rem;'
                    ),
                    # Hidden input to store the selected plugin
                    Input(type='hidden', name='plugin_analysis', id=f'selected-plugin-{step_id}', 
                          data_testid=f'dev-assistant-selected-plugin-{step_id}', required=True),
                    Button('Analyze Selected Plugin ▸', type='submit', id=f'analyze-btn-{step_id}', 
                           aria_label='Analyze the selected plugin for automation and accessibility issues',
                           data_testid=f'dev-assistant-analyze-button-{step_id}', disabled=True),
                    hx_post=f'/{app_name}/{step_id}_submit',
                    hx_target=f'#{step_id}'
                )
            ),
            # Simple JavaScript - same pattern as navigation search that works perfectly
            Script(f"""
            // Simple selection function - same as nav search pattern
            window.selectDevAssistantPlugin = function(filename, displayName) {{
                const selectedInput = document.getElementById('selected-plugin-{step_id}');
                const searchResults = document.getElementById('plugin-search-results-{step_id}');
                const searchInput = document.getElementById('plugin-search-input-{step_id}');
                const analyzeBtn = document.getElementById('analyze-btn-{step_id}');
                
                if (selectedInput) selectedInput.value = filename;
                if (searchResults) searchResults.style.display = 'none';
                if (searchInput) {{
                    searchInput.value = displayName;
                    searchInput.blur();
                }}
                if (analyzeBtn) {{
                    analyzeBtn.disabled = false;
                    analyzeBtn.textContent = 'Analyze ' + displayName + ' ▸';
                }}
            }}
            
            // Click-away-to-dismiss - same pattern as navigation search
            document.addEventListener('click', function(event) {{
                const searchInput = document.getElementById('plugin-search-input-{step_id}');
                const dropdown = document.getElementById('plugin-search-results-{step_id}');
                
                if (searchInput && dropdown && 
                    !searchInput.contains(event.target) && 
                    !dropdown.contains(event.target)) {{
                    dropdown.style.display = 'none';
                }}
            }});
            """),
            # Next step placeholder for analysis results
            Div(id='step_02'),
            id=step_id
        )

    async def step_01_submit(self, request):
        # Simplified utility - analyze plugin and show results immediately
        app_name = self.app_name
        
        form = await request.form()
        selected_file = form.get('plugin_analysis', '').strip()

        if not selected_file:
            return P('Please select a plugin file to analyze.', style='color: red;')

        # Analyze the selected plugin
        file_path = Path("apps") / selected_file
        analysis = self.analyze_plugin_file(file_path)

        # Store analysis in a simple session variable for step_02 to access
        # Using a simple class attribute since this is a utility tool
        self.current_analysis = analysis
        
        # Return updated step_01 showing selection + trigger step_02 load
        return Div(
            Card(
                H3('Plugin Analysis'),
                P(f'✅ Selected: {selected_file}', style='color: green; font-weight: bold;'),
                Button('Analyze Different Plugin', 
                       hx_get=f'/{app_name}/step_01', 
                       hx_target='#step_01',
                       id='dev-assistant-analyze-different-button',
                       aria_label='Go back to plugin selection to analyze a different plugin',
                       data_testid='dev-assistant-analyze-different-button',
                       cls='secondary', style='margin-top: 1rem;')
            ),
            # Trigger step_02 to load with analysis results
            Div(id='step_02', hx_get=f'/{app_name}/step_02', hx_trigger='load'),
            id='step_01'
        )

    async def step_02(self, request):
        # Simplified utility - display analysis results from current_analysis
        app_name = self.app_name
        step_id = 'step_02'
        next_step_id = 'finalize'
        
        # Check if we have analysis results
        if not hasattr(self, 'current_analysis') or not self.current_analysis:
            return Div(
                Card(
                    H3('Analysis Results'),
                    P('No analysis available. Please select and analyze a plugin first.', style='color: orange;'),
                    Button('Go Back to Plugin Selection', 
                           hx_get=f'/{app_name}/step_01', 
                           hx_target='#step_01',
                           id='dev-assistant-back-to-selection-button',
                           aria_label='Return to plugin selection screen',
                           data_testid='dev-assistant-back-to-selection-button',
                           cls='secondary')
                ),
                id='step_02'
            )

        analysis_results = self.current_analysis
        
        # Get analysis data
        issues = analysis_results.get('issues', [])
        template_suitability = analysis_results.get('template_suitability', {})
        coding_prompts = analysis_results.get('coding_assistant_prompts', [])
        transplant_analysis = analysis_results.get('transplantation_analysis', {})
        automation_readiness = analysis_results.get('automation_readiness', {})
        filename = analysis_results.get('filename', 'unknown')

        # Focus on what needs fixing - issues first!
        functional_issues = [issue for issue in issues if not any(x in issue.lower() for x in ['marker', 'template', 'ui_constants'])]
        template_issues = [issue for issue in issues if any(x in issue.lower() for x in ['marker', 'template', 'ui_constants'])]

        # Quick status for capability overview
        has_functional_issues = bool(functional_issues)
        template_source_ready = template_suitability.get('as_template_source', False)
        transplant_commands = transplant_analysis.get('transplant_commands', [])
        ready_transplants = [cmd for cmd in transplant_commands if cmd.get('compatibility') == 'Good']

        # Define widget ID for Prism targeting
        widget_id = f"dev-assistant-analysis-results"

        return Div(
            Card(
                H3(f"Analysis: {filename}", cls="mb-lg"),

                # WHAT NEEDS FIXING (Primary Focus)
                (Div(
                    H4("🚨 ISSUES TO FIX", style=f"color: {self.UI_CONSTANTS['COLORS']['ERROR_RED']}; margin-bottom: 1rem; border-bottom: 2px solid {self.UI_CONSTANTS['COLORS']['ERROR_RED']}; padding-bottom: 0.5rem;"),
                    Div(
                        H5("❌ Functional Issues:", style="color: red; margin-bottom: 0.5rem;"),
                        Ul(*[Li(issue) for issue in functional_issues],
                           style="color: red; margin-bottom: 1rem;")
                    ) if functional_issues else None,
                    Div(
                        H5("📋 Template Issues:", style="color: orange; margin-bottom: 0.5rem;"),
                        Ul(*[Li(issue) for issue in template_issues],
                           style="color: orange; margin-bottom: 1rem;")
                    ) if template_issues else None,
                    (P("✅ No critical issues found!", style=f"color: {self.UI_CONSTANTS['COLORS']['SUCCESS_GREEN']}; font-weight: bold; font-size: 1.1rem;")
                     if not functional_issues and not template_issues else None),
                    cls="mb-2xl"
                ) if functional_issues or template_issues else Div(
                    H4("✅ NO ISSUES FOUND", style=f"color: {self.UI_CONSTANTS['COLORS']['SUCCESS_GREEN']}; margin-bottom: 1rem; border-bottom: 2px solid {self.UI_CONSTANTS['COLORS']['SUCCESS_GREEN']}; padding-bottom: 0.5rem;"),
                    P("This plugin appears to be correctly implemented!", style=f"color: {self.UI_CONSTANTS['COLORS']['SUCCESS_GREEN']}; font-weight: bold; font-size: 1.1rem;"),
                    cls="mb-2xl"
                )),

                # CAPABILITIES (Secondary Info)
                Div(
                    Details(
                        Summary(
                            H4('📊 Capabilities Summary', style='display: inline; margin: 0; color: black;'),
                            style=f'cursor: pointer; padding: {self.UI_CONSTANTS["SPACING"]["SECTION_PADDING"]}; background-color: {self.UI_CONSTANTS["BACKGROUNDS"]["LIGHT_GRAY"]}; border-radius: {self.UI_CONSTANTS["SPACING"]["BORDER_RADIUS"]}; margin: 1rem 0;'
                        ),
                        Div(
                            Div(f"🔧 Functional Plugin: {'✅ Good' if not has_functional_issues else '❌ Has Issues'}",
                                style=f"color: {self.UI_CONSTANTS['COLORS']['SUCCESS_TEXT'] if not has_functional_issues else self.UI_CONSTANTS['COLORS']['ERROR_TEXT']}; background-color: {self.UI_CONSTANTS['BACKGROUNDS']['SUCCESS_BG'] if not has_functional_issues else self.UI_CONSTANTS['BACKGROUNDS']['ERROR_BG']}; padding: {self.UI_CONSTANTS['SPACING']['SMALL_PADDING']}; border-radius: {self.UI_CONSTANTS['SPACING']['BORDER_RADIUS']}; font-weight: bold; margin-bottom: {self.UI_CONSTANTS['SPACING']['SMALL_MARGIN']};"),
                            Div(f"📋 Template Source: {'✅ Ready' if template_source_ready else '❌ Needs Work'}",
                                style=f"color: {self.UI_CONSTANTS['COLORS']['SUCCESS_TEXT'] if template_source_ready else self.UI_CONSTANTS['COLORS']['ERROR_TEXT']}; background-color: {self.UI_CONSTANTS['BACKGROUNDS']['SUCCESS_BG'] if template_source_ready else self.UI_CONSTANTS['BACKGROUNDS']['ERROR_BG']}; padding: {self.UI_CONSTANTS['SPACING']['SMALL_PADDING']}; border-radius: {self.UI_CONSTANTS['SPACING']['BORDER_RADIUS']}; font-weight: bold; margin-bottom: {self.UI_CONSTANTS['SPACING']['SMALL_MARGIN']};"),
                            Div(f"📤 Step Source: {'✅ ' + str(len(ready_transplants)) + ' ready' if ready_transplants else '❌ None ready'}",
                                style=f"color: {self.UI_CONSTANTS['COLORS']['SUCCESS_TEXT'] if ready_transplants else self.UI_CONSTANTS['COLORS']['ERROR_TEXT']}; background-color: {self.UI_CONSTANTS['BACKGROUNDS']['SUCCESS_BG'] if ready_transplants else self.UI_CONSTANTS['BACKGROUNDS']['ERROR_BG']}; padding: {self.UI_CONSTANTS['SPACING']['SMALL_PADDING']}; border-radius: {self.UI_CONSTANTS['SPACING']['BORDER_RADIUS']}; font-weight: bold; margin-bottom: {self.UI_CONSTANTS['SPACING']['SMALL_MARGIN']};"),
                            Div(f"🤖 Automation Ready: {'✅ Score ' + str(automation_readiness.get('accessibility_score', 0)) + '/100' if automation_readiness.get('automation_ready', False) else '❌ Score ' + str(automation_readiness.get('accessibility_score', 0)) + '/100'}",
                                style=f"color: {self.UI_CONSTANTS['COLORS']['SUCCESS_TEXT'] if automation_readiness.get('automation_ready', False) else self.UI_CONSTANTS['COLORS']['ERROR_TEXT']}; background-color: {self.UI_CONSTANTS['BACKGROUNDS']['SUCCESS_BG'] if automation_readiness.get('automation_ready', False) else self.UI_CONSTANTS['BACKGROUNDS']['ERROR_BG']}; padding: {self.UI_CONSTANTS['SPACING']['SMALL_PADDING']}; border-radius: {self.UI_CONSTANTS['SPACING']['BORDER_RADIUS']}; font-weight: bold;"),
                            style='padding: 1rem;'
                        )
                    )
                ),

                # AUTOMATION READINESS DETAILS (If ARIA validation was performed)
                (Details(
                    Summary(
                        H4(f'🤖 Automation & Accessibility Report ({automation_readiness.get("accessibility_score", 0)}/100)', style='display: inline; margin: 0; color: black;'),
                        style=f'cursor: pointer; padding: {self.UI_CONSTANTS["SPACING"]["SECTION_PADDING"]}; background-color: {self.UI_CONSTANTS["BACKGROUNDS"]["LIGHT_GRAY"]}; border-radius: {self.UI_CONSTANTS["SPACING"]["BORDER_RADIUS"]}; margin: 1rem 0;'
                    ),
                    Div(
                        # Copy button for AI prompt
                        Div(
                            Button(
                                '📋 Copy AI Prompt',
                                id=f'copy-automation-prompt-{filename.replace(".", "-")}',
                                cls='copy-button',
                                aria_label='Copy comprehensive AI prompt for fixing automation and accessibility issues',
                                data_testid=f'dev-assistant-copy-ai-prompt-{filename.replace(".", "-")}',
                                data_copy_text=self.generate_automation_ai_prompt(automation_readiness, filename),
                                style='margin-bottom: 1rem; padding: 8px 16px; background: #0066cc; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9rem;'
                            ),
                            P('Copy this comprehensive prompt to paste into AI Code Assistants like Claude, ChatGPT, or Cursor for automated fixing of accessibility and automation issues.',
                              style='margin-bottom: 1rem; font-size: 0.9em; color: #666; font-style: italic;'),
                            style='margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid #e9ecef;'
                        ),
                        Div(
                            H5(f'📊 Overall Score: {automation_readiness.get("accessibility_score", 0)}/100', 
                               style=f'color: {self.UI_CONSTANTS["COLORS"]["SUCCESS_GREEN"] if automation_readiness.get("accessibility_score", 0) >= 95 else self.UI_CONSTANTS["COLORS"]["ERROR_RED"] if automation_readiness.get("accessibility_score", 0) < 70 else "#ff8800"}; font-size: 1.3rem; margin-bottom: 1rem; font-weight: bold;'),
                            P(f'🤖 Selenium Readiness: {automation_readiness.get("selenium_readiness", "unknown").title()}',
                              style=f'color: {self.UI_CONSTANTS["COLORS"]["SUCCESS_GREEN"] if automation_readiness.get("selenium_readiness") == "good" else self.UI_CONSTANTS["COLORS"]["ERROR_RED"] if automation_readiness.get("selenium_readiness") == "poor" else "#ff8800"}; font-weight: bold; margin-bottom: 1rem;'),
                            P(f'🎯 Automation Ready: {"✅ Yes" if automation_readiness.get("automation_ready", False) else "❌ No"}',
                              style=f'color: {self.UI_CONSTANTS["COLORS"]["SUCCESS_GREEN"] if automation_readiness.get("automation_ready", False) else self.UI_CONSTANTS["COLORS"]["ERROR_RED"]}; font-weight: bold; margin-bottom: 1rem;'),
                              
                            # Detailed Score Breakdown
                            Details(
                                Summary('📈 Score Breakdown (Click to expand)', 
                                       style='cursor: pointer; color: #0066cc; font-weight: bold; margin: 1rem 0;'),
                                Div(
                                    H6('Score Components:', style='color: #333; margin-bottom: 0.5rem;'),
                                    *self._generate_score_breakdown(automation_readiness),
                                    style='padding: 1rem; background-color: #f8f9fa; border-radius: 4px; margin-top: 0.5rem;'
                                )
                            )
                        ) if automation_readiness else None,
                        
                        # Dropdown Validations
                        (Div(
                            H5('🔧 Dropdown Analysis:', style='color: #0066cc; margin-bottom: 0.5rem;'),
                            *[
                                Div(
                                    Strong(f'{func_name}: ', style='color: #333;'),
                                    Span(f'{result.get("completion_percentage", 0)}% complete', 
                                         style=f'color: {self.UI_CONSTANTS["COLORS"]["SUCCESS_GREEN"] if result.get("completion_percentage", 0) >= 80 else self.UI_CONSTANTS["COLORS"]["ERROR_RED"] if result.get("completion_percentage", 0) < 50 else "#ff8800"}; font-weight: bold;'),
                    Br(),
                                    *([Small(f'Missing: {", ".join(result["missing_attributes"])}', style='color: red; margin-left: 1rem;')] if result.get('missing_attributes') else []),
                                    style='margin-bottom: 0.5rem;'
                                )
                                for func_name, result in automation_readiness.get('dropdown_validations', {}).items()
                                if result.get('function_found')
                            ]
                        ) if automation_readiness.get('dropdown_validations') else None),
                        
                        # Form Validations
                        (Div(
                            H5('📝 Form Analysis:', style='color: #0066cc; margin-bottom: 0.5rem; margin-top: 1rem;'),
                            P(f'Automation attributes found: {", ".join(automation_readiness["form_validations"]["automation_attributes"]) if automation_readiness["form_validations"]["automation_attributes"] else "None"}',
                              style=f'color: {self.UI_CONSTANTS["COLORS"]["SUCCESS_GREEN"] if automation_readiness["form_validations"]["automation_attributes"] else self.UI_CONSTANTS["COLORS"]["ERROR_RED"]}; margin-left: 1rem;'),
                            *([P(f'Missing attributes: {", ".join(automation_readiness["form_validations"]["missing_attributes"])}', 
                                 style='color: orange; margin-left: 1rem;')] if automation_readiness["form_validations"].get("missing_attributes") else [])
                        ) if automation_readiness.get('form_validations', {}).get('forms_detected') else None),
                        
                        # ARIA Issues
                        (Div(
                            H5('⚠️ ARIA Issues:', style='color: red; margin-bottom: 0.5rem; margin-top: 1rem;'),
                            Ul(*[Li(issue) for issue in automation_readiness.get('aria_issues', [])],
                               style='color: red; margin-left: 1rem;')
                        ) if automation_readiness.get('aria_issues') else None),
                        
                        # ARIA Recommendations
                        (Div(
                            H5('💡 Recommendations:', style='color: #0066cc; margin-bottom: 0.5rem; margin-top: 1rem;'),
                            Ul(*[Li(rec) for rec in automation_readiness.get('aria_recommendations', [])],
                               style='margin-left: 1rem;')
                        ) if automation_readiness.get('aria_recommendations') else None),
                        
                        style='padding: 1rem;'
                    )
                ) if automation_readiness else None),

                # CODING FIXES (If issues exist)
                (Details(
                    Summary(
                        H4('🤖 Coding Assistant Instructions', style='display: inline; margin: 0; color: black;'),
                        style=f'cursor: pointer; padding: {self.UI_CONSTANTS["SPACING"]["SECTION_PADDING"]}; background-color: {self.UI_CONSTANTS["BACKGROUNDS"]["LIGHT_GRAY"]}; border-radius: {self.UI_CONSTANTS["SPACING"]["BORDER_RADIUS"]}; margin: 1rem 0;'
                    ),
                    Div(
                        P(f'Copy these detailed instructions to fix {filename}:',
                          style=f'margin-bottom: 1rem; font-weight: bold; color: {self.UI_CONSTANTS["COLORS"]["HEADER_TEXT"]};'),
                        Div(
                            *[
                                Div(
                                    H5(f'Fix #{i+1}:', style=f'color: {self.UI_CONSTANTS["COLORS"]["INFO_BLUE"]}; margin-top: 1.5rem; margin-bottom: 0.5rem;'),
                                    Pre(
                                        Code(prompt, cls='language-markdown'),
                                        cls='line-numbers language-markdown',
                                        style=f'position: relative; background-color: {self.UI_CONSTANTS["COLORS"]["CODE_BG_DARK"]}; color: {self.UI_CONSTANTS["COLORS"]["CODE_TEXT_LIGHT"]}; padding: 1rem; border-radius: {self.UI_CONSTANTS["SPACING"]["BORDER_RADIUS"]}; overflow-x: auto; border-left: 4px solid {self.UI_CONSTANTS["COLORS"]["INFO_BLUE"]};'
                                    ),
                                    style='margin-bottom: 1rem;'
                                )
                                for i, prompt in enumerate(coding_prompts)
                            ],
                            id=widget_id
                        ),
                        style='padding: 1rem;'
                    ),
                    style='margin: 1rem 0;'
                ) if coding_prompts else None),

                # CREATE NEW VERSION COMMAND
                Details(
                    Summary(
                        H4('🚀 Create New Version Command', style='display: inline; margin: 0; color: black;'),
                        style=f'cursor: pointer; padding: {self.UI_CONSTANTS["SPACING"]["SECTION_PADDING"]}; background-color: {self.UI_CONSTANTS["BACKGROUNDS"]["LIGHT_GRAY"]}; border-radius: {self.UI_CONSTANTS["SPACING"]["BORDER_RADIUS"]}; margin: 1rem 0;'
                    ),
                    Div(
                        *self.generate_create_workflow_commands(analysis_results),
                        style='padding: 1rem;'
                    )
                ),

                # TRANSPLANTATION COMMANDS (If available)
                (Details(
                    Summary(
                        H4('🔀 Step Transplantation', style='display: inline; margin: 0; color: black;'),
                        style=f'cursor: pointer; padding: {self.UI_CONSTANTS["SPACING"]["SECTION_PADDING"]}; background-color: {self.UI_CONSTANTS["BACKGROUNDS"]["LIGHT_GRAY"]}; border-radius: {self.UI_CONSTANTS["SPACING"]["BORDER_RADIUS"]}; margin: 1rem 0;'
                    ),
                    Div(
                        (Div(
                            H5('✅ Ready Commands:', style=f'color: {self.UI_CONSTANTS["COLORS"]["SUCCESS_GREEN"]}; margin-bottom: 0.75rem;'),
                            *[
                                Div(
                                    H6(f"{cmd['step_id']}:", style=f'color: {self.UI_CONSTANTS["COLORS"]["INFO_BLUE"]}; margin-bottom: 0.25rem; margin-top: 1rem;'),
                                    Pre(
                                        Code(cmd['command'], cls='language-bash'),
                                        cls='language-bash',
                                        style=f'background-color: {self.UI_CONSTANTS["COLORS"]["CODE_BG_DARK"]}; color: {self.UI_CONSTANTS["COLORS"]["CODE_TEXT_LIGHT"]}; padding: 0.75rem; border-radius: {self.UI_CONSTANTS["SPACING"]["BORDER_RADIUS"]}; overflow-x: auto; position: relative; border-left: 3px solid {self.UI_CONSTANTS["COLORS"]["SUCCESS_GREEN"]}; margin-bottom: 0.5rem;'
                                    ),
                                    style='margin-bottom: 1rem;'
                                )
                                for cmd in ready_transplants
                            ]
                        ) if ready_transplants else P('No ready-to-transplant steps found.', style=f'color: {self.UI_CONSTANTS["COLORS"]["BODY_TEXT"]};')),
                        style='padding: 1rem;'
                    )
                ) if transplant_commands else None),

                Button('🔄 New Analysis', 
                       hx_get=f'/{app_name}/step_01',
                       hx_target='#step_01',
                       id='dev-assistant-new-analysis-button',
                       aria_label='Start a new plugin analysis session',
                       data_testid='dev-assistant-new-analysis-button',
                       cls='secondary',
                       style='margin-top: 1rem;'),

                # Initialize Prism highlighting and Pipulate copy functionality
                Script(f"""
                (function() {{
                    // Small delay to ensure DOM is fully rendered
                    setTimeout(function() {{
                        // Initialize Prism highlighting for the entire step (includes built-in copy-to-clipboard)
                        if (typeof Prism !== 'undefined') {{
                            console.log('🔄 Initializing Prism for DevAssistant step: {step_id}');
                            Prism.highlightAllUnder(document.getElementById('{step_id}'));
                        }}

                        // Re-initialize Pipulate copy functionality for new content
                        if (typeof PipulateCopy !== 'undefined') {{
                            console.log('🔄 Initializing PipulateCopy for DevAssistant');
                            PipulateCopy.initializeDataCopyButtons();
                            PipulateCopy.initializeInlineCodeCopy();
                        }}
                    }}, 100);

                    // Listen for HX-Trigger event as backup
                    document.body.addEventListener('initializePrism', function(event) {{
                        if (event.detail.targetId === '{step_id}') {{
                            console.log('🔄 Received initializePrism event for {step_id}');
                            if (typeof Prism !== 'undefined') {{
                                Prism.highlightAllUnder(document.getElementById('{step_id}'));
                            }}
                            if (typeof PipulateCopy !== 'undefined') {{
                                PipulateCopy.initializeDataCopyButtons();
                                PipulateCopy.initializeInlineCodeCopy();
                            }}
                        }}
                    }});
                }})();
                """, type='text/javascript')
            ),
            Div(id=next_step_id),
            id=step_id
        )



