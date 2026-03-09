import asyncio
import json
import os
from datetime import datetime
from urllib.parse import quote, urlparse

from fasthtml.common import *
from loguru import logger
from imports.crud import Step  # 🎯 STANDARDIZED: Import centralized Step definition
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from starlette.responses import HTMLResponse, JSONResponse
from webdriver_manager.chrome import ChromeDriverManager

ROLES = ['Workshop']
'\nPipulate Browser Automation Workflow\n\nThis workflow demonstrates Selenium-based browser automation capabilities:\n- Cross-platform Chrome automation (Linux/macOS)\n- Clean browser sessions with temporary profiles\n- Detailed status logging and error handling\n- URL opening and verification\n'


def get_safe_path(url):
    """Convert URL to filesystem-safe path while maintaining reversibility."""
    parsed = urlparse(url)
    domain = parsed.netloc
    path = parsed.path
    if not path or path == '/':
        path = '/'
    path = quote(path + ('?' + parsed.query if parsed.query else ''), safe='')
    return (domain, path)


def reconstruct_url(domain, path):
    """Reconstruct URL from filesystem components."""
    return f'https://{domain}{path}'


def ensure_crawl_dir(app_name, domain, date_slug):
    """Ensure crawl directory exists and return its path."""
    base_dir = os.path.join('downloads', app_name, domain, date_slug)
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


class BrowserAutomation:
    """
    Browser Automation Workflow

    A workflow that demonstrates Selenium integration for browser automation tasks.
    This serves as the primary development ground for Pipulate's browser automation features.
    """
    APP_NAME = 'browser'
    DISPLAY_NAME = 'Browser Automation 🤖'
    ENDPOINT_MESSAGE = "Open URLs using Selenium for browser automation. This workflow demonstrates Pipulate's browser automation capabilities."
    TRAINING_PROMPT = 'This workflow showcases browser automation using Selenium. It uses webdriver-manager for cross-platform compatibility and provides a foundation for developing more advanced automation features.'

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
        steps = [Step(id='step_01', done='url', show='Enter URL', refill=True), Step(id='step_02', done='placeholder', show='Placeholder Step', refill=True), Step(id='step_03', done='session_test_complete', show='Ephemeral Login Test', refill=False), Step(id='step_04', done='persistent_session_test_complete', show='Persistent Login Test', refill=False), Step(id='step_05', done='placeholder', show='Step 5 Placeholder', refill=False)]
        routes = [(f'/{app_name}', self.landing), (f'/{app_name}/init', self.init, ['POST']), (f'/{app_name}/revert', self.handle_revert, ['POST']), (f'/{app_name}/finalize', self.finalize, ['GET', 'POST']), (f'/{app_name}/unfinalize', self.unfinalize, ['POST']), (f'/{app_name}/reopen_url', self.reopen_url, ['POST'])]
        self.steps = steps
        for step in steps:
            step_id = step.id
            routes.append((f'/{app_name}/{step_id}', getattr(self, step_id)))
            routes.append((f'/{app_name}/{step_id}_submit', getattr(self, f'{step_id}_submit'), ['POST']))
            if step_id in ['step_03', 'step_04']:
                routes.append((f'/{app_name}/{step_id}_confirm', getattr(self, f'{step_id}_confirm'), ['POST']))
        for path, handler, *methods in routes:
            method_list = methods[0] if methods else ['GET']
            app.route(path, methods=method_list)(handler)
        self.step_messages = {'finalize': {'ready': 'All steps complete. Ready to finalize workflow.', 'complete': f'Workflow finalized. Use {wand.UNLOCK_BUTTON_LABEL} to make changes.'}}
        for step in steps:
            self.step_messages[step.id] = {'input': f'{wand.fmt(step.id)}: Please complete {step.show}.', 'complete': f'{step.show} complete. Continue to next step.'}
        steps.append(Step(id='finalize', done='finalized', show='Finalize', refill=False))
        self.steps_indices = {step.id: i for i, step in enumerate(steps)}

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
        """Handles GET request to show Finalize button and POST request to lock the workflow."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        finalize_step = steps[-1]
        finalize_data = wand.get_step_data(pipeline_id, finalize_step.id, {})
        if request.method == 'GET':
            if finalize_step.done in finalize_data:
                return Card(H3('Workflow is locked.'), Form(Button(wand.UNLOCK_BUTTON_LABEL, type='submit', cls='secondary outline'), hx_post=f'/{app_name}/unfinalize', hx_target=f'#{finalize_step.id}'), id=finalize_step.id)
            else:
                all_steps_complete = all((wand.get_step_data(pipeline_id, step.id, {}).get(step.done) for step in steps[:-1]))
                if all_steps_complete:
                    return Card(H3('All steps complete. Finalize?'), P('You can revert to any step and make changes.', cls='text-secondary'), Form(Button('Finalize 🔒', type='submit', cls='primary'), hx_post=f'/{app_name}/finalize', hx_target=f'#{finalize_step.id}'), id=finalize_step.id)
                else:
                    return Div(id=finalize_step.id)
        else:
            state = wand.read_state(pipeline_id)
            for step in steps[:-1]:
                step_data = wand.get_step_data(pipeline_id, step.id, {})
                if step.done in step_data:
                    state[step.id] = step_data
            state['finalize'] = {'finalized': True}
            state['updated'] = datetime.now().isoformat()
            wand.write_state(pipeline_id, state)
            await self.message_queue.add(wand, self.step_messages['finalize']['complete'], verbatim=True)
            return Card(H3('Workflow is locked.'), Form(Button(wand.UNLOCK_BUTTON_LABEL, type='submit', cls='secondary outline'), hx_post=f'/{app_name}/unfinalize', hx_target=f'#{finalize_step.id}'), id=finalize_step.id)

    async def unfinalize(self, request):
        """Handles POST request to unlock the workflow."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        if 'finalize' in state:
            del state['finalize']
        for step in steps[:-1]:
            if step.id in state and step.done in state[step.id]:
                pass
        wand.write_state(pipeline_id, state)
        await self.message_queue.add(wand, 'Workflow unfinalized! You can now revert to any step and make changes.', verbatim=True)
        return Card(H3('All steps complete. Finalize?'), P('You can revert to any step and make changes.', cls='text-secondary'), Form(Button('Finalize 🔒', type='submit', cls='primary'), hx_post=f'/{app_name}/finalize', hx_target=f'#{steps[-1].id}'), id=steps[-1].id)

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
        if step_id == 'step_03':
            step_data = state.get(step_id, {})
            if 'session_test_confirmed' in step_data:
                del step_data['session_test_confirmed']
            state[step_id] = step_data
        elif step_id == 'step_04':
            step_data = state.get(step_id, {})
            if 'persistent_session_test_confirmed' in step_data:
                del step_data['persistent_session_test_confirmed']
            state[step_id] = step_data
        state['_revert_target'] = step_id
        wand.write_state(pipeline_id, state)
        message = await wand.get_state_message(pipeline_id, steps, self.step_messages)
        await self.message_queue.add(wand, message, verbatim=True)
        return wand.run_all_cells(app_name, steps)

    async def step_01(self, request):
        """Handles GET request for Open URL step."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        url_value = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and url_value:
            return Div(Card(H3(f'🔒 Open URL'), P(f'URL opened (and closed): ', B(url_value)), Div(id=f'{step_id}-status')), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        elif url_value and state.get('_revert_target') != step_id:
            content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'Open URL: {url_value}', widget=Div(P(f'URL opened (and closed): ', B(url_value)), Div(id=f'{step_id}-status')), steps=steps)
            return Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        else:
            await self.message_queue.add(wand, 'Enter the URL you want to open with Selenium:', verbatim=True)
            display_value = url_value if step.refill and url_value else 'https://example.com'
            return Div(Card(H3('Open URL'), Form(Input(type='url', name='url', placeholder='https://example.com', required=True, value=display_value, cls='contrast'), Button('Open URL', type='submit', cls='primary'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_01_submit(self, request):
        """Process the Open URL submission and open it with Selenium."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form = await request.form()
        url = form.get('url', '').strip()
        if not url:
            return P('Error: URL is required', cls='text-invalid')
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        await wand.set_step_data(pipeline_id, step_id, url, steps)
        try:
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--new-window')
            chrome_options.add_argument('--start-maximized')
            import tempfile
            profile_dir = tempfile.mkdtemp()
            chrome_options.add_argument(f'--user-data-dir={profile_dir}')
            effective_os = os.environ.get('EFFECTIVE_OS', 'unknown')
            await self.message_queue.add(wand, f'Current OS: {effective_os}', verbatim=True)
            if effective_os == 'darwin':
                await self.message_queue.add(wand, 'Using webdriver-manager for macOS', verbatim=True)
                service = Service(ChromeDriverManager().install())
            else:
                await self.message_queue.add(wand, 'Using system Chrome for Linux', verbatim=True)
                service = Service()
            await self.message_queue.add(wand, 'Initializing Chrome driver...', verbatim=True)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            await self.message_queue.add(wand, f'Opening URL with Selenium: {url}', verbatim=True)
            driver.get(url)
            await asyncio.sleep(2)
            title = driver.title
            await self.message_queue.add(wand, f'Page loaded successfully. Title: {title}', verbatim=True)
            driver.quit()
            await self.message_queue.add(wand, 'Browser closed successfully', verbatim=True)
            import shutil
            shutil.rmtree(profile_dir, ignore_errors=True)
        except Exception as e:
            error_msg = f'Error opening URL with Selenium: {str(e)}'
            logger.error(error_msg)
            safe_error_msg = error_msg.replace('<', '&lt;').replace('>', '&gt;')
            await self.message_queue.add(wand, safe_error_msg, verbatim=True)
            return P(error_msg, cls='text-invalid')
        url_widget = Div(P(f'URL opened (and closed): ', B(url)), Div(id=f'{step_id}-status'))
        content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'Open URL: {url}', widget=url_widget, steps=steps)
        return Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)

    async def reopen_url(self, request):
        """Handle reopening a URL with Selenium."""
        wand, db = (self.pipulate, self.pipulate.db)
        form = await request.form()
        url = form.get('url', '').strip()
        if not url:
            return P('Error: URL is required', cls='text-invalid')
        try:
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--new-window')
            chrome_options.add_argument('--start-maximized')
            import tempfile
            profile_dir = tempfile.mkdtemp()
            chrome_options.add_argument(f'--user-data-dir={profile_dir}')
            effective_os = os.environ.get('EFFECTIVE_OS', 'unknown')
            await self.message_queue.add(wand, f'Current OS: {effective_os}', verbatim=True)
            if effective_os == 'darwin':
                await self.message_queue.add(wand, 'Using webdriver-manager for macOS', verbatim=True)
                service = Service(ChromeDriverManager().install())
            else:
                await self.message_queue.add(wand, 'Using system Chrome for Linux', verbatim=True)
                service = Service()
            await self.message_queue.add(wand, 'Initializing Chrome driver...', verbatim=True)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            await self.message_queue.add(wand, f'Reopening URL with Selenium: {url}', verbatim=True)
            driver.get(url)
            await asyncio.sleep(2)
            title = driver.title
            await self.message_queue.add(wand, f'Page loaded successfully. Title: {title}', verbatim=True)
            driver.quit()
            await self.message_queue.add(wand, 'Browser closed successfully', verbatim=True)
            import shutil
            shutil.rmtree(profile_dir, ignore_errors=True)
            return P(f'Successfully reopened: {url}', style='color: green;')
        except Exception as e:
            error_msg = f'Error reopening URL with Selenium: {str(e)}'
            logger.error(error_msg)
            await self.message_queue.add(wand, error_msg, verbatim=True)
            return P(error_msg, cls='text-invalid')

    async def step_02(self, request):
        """Handles GET request for Crawl URL step (identical to Step 1, independent state, crawl semantics)."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_02'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        url_value = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and url_value:
            return Div(Card(H3(f'🔒 Crawl URL'), P(f'URL crawled and saved: ', B(url_value.get('url', ''))), Div(id=f'{step_id}-status')), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        elif url_value and state.get('_revert_target') != step_id:
            content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f"Crawl URL: {url_value.get('url', '')}", widget=Div(P(f'URL crawled and saved: ', B(url_value.get('url', ''))), P(f"Title: {url_value.get('title', '')}"), P(f"Status: {url_value.get('status', '')}"), P(f"Saved to: {url_value.get('save_path', '')}"), P(f"Reconstructed URL: {url_value.get('reconstructed_url', '')}", cls='text-secondary'), Div(id=f'{step_id}-status')), steps=steps)
            return Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        else:
            await self.message_queue.add(wand, 'Enter the URL you want to crawl:', verbatim=True)
            display_value = ''
            if step.refill and url_value:
                if isinstance(url_value, dict) and 'url' in url_value:
                    display_value = url_value['url']
                else:
                    display_value = url_value
            if not display_value:
                display_value = 'https://example.com'
            return Div(Card(H3('Crawl URL'), Form(Input(type='url', name='url', placeholder='https://example.com', required=True, value=display_value, cls='contrast'), Button('Crawl URL', type='submit', cls='primary'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_02_submit(self, request):
        """Process the Crawl URL submission, open with Selenium, and save crawl data."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_02'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form = await request.form()
        url = form.get('url', '').strip()
        if not url:
            return P('Error: URL is required', cls='text-invalid')
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        try:
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--new-window')
            chrome_options.add_argument('--start-maximized')
            import tempfile
            profile_dir = tempfile.mkdtemp()
            chrome_options.add_argument(f'--user-data-dir={profile_dir}')
            effective_os = os.environ.get('EFFECTIVE_OS', 'unknown')
            await self.message_queue.add(wand, f'Current OS: {effective_os}', verbatim=True)
            if effective_os == 'darwin':
                await self.message_queue.add(wand, 'Using webdriver-manager for macOS', verbatim=True)
                service = Service(ChromeDriverManager().install())
            else:
                await self.message_queue.add(wand, 'Using system Chrome for Linux', verbatim=True)
                service = Service()
            await self.message_queue.add(wand, 'Initializing Chrome driver...', verbatim=True)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            await self.message_queue.add(wand, f'Crawling URL with Selenium: {url}', verbatim=True)
            driver.get(url)
            await asyncio.sleep(2)
            title = driver.title
            source = driver.page_source
            dom = driver.execute_script('return document.documentElement.outerHTML;')
            main_request = None

            # RIP OUT THE ENTIRE `driver.requests` LOOP AND REPLACE WITH STUBS:
            headers = {"Notice": "selenium-wire removed; headers unavailable"}
            status = 200

            domain, path = get_safe_path(url)
            date_slug = datetime.now().strftime('%Y%m%d')
            base_dir = ensure_crawl_dir(app_name, domain, date_slug)
            crawl_dir = os.path.join(base_dir, path)
            os.makedirs(crawl_dir, exist_ok=True)
            with open(os.path.join(crawl_dir, 'headers.json'), 'w') as f:
                json.dump(headers, f, indent=2)
            with open(os.path.join(crawl_dir, 'source.html'), 'w') as f:
                f.write(source)
            with open(os.path.join(crawl_dir, 'dom.html'), 'w') as f:
                f.write(dom)
            driver.quit()
            await self.message_queue.add(wand, 'Browser closed successfully', verbatim=True)
            import shutil
            shutil.rmtree(profile_dir, ignore_errors=True)
            reconstructed_url = reconstruct_url(domain, path)
            crawl_data = {'url': url, 'title': title, 'status': status, 'save_path': crawl_dir, 'timestamp': datetime.now().isoformat(), 'reconstructed_url': reconstructed_url}
            await wand.set_step_data(pipeline_id, step_id, crawl_data, steps)
            await self.message_queue.add(wand, f'{step.show} complete.', verbatim=True)
            url_widget = Div(P(f'URL crawled and saved: ', B(crawl_data['url'])), P(f'Title: {title}'), P(f'Status: {status}'), P(f'Saved to: {crawl_dir}'), P(f'Reconstructed URL: {reconstructed_url}', cls='text-secondary'), Div(id=f'{step_id}-status'))
            content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f"Crawl URL: {crawl_data['url']}", widget=url_widget, steps=steps)
            return Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        except Exception as e:
            error_msg = f'Error crawling URL with Selenium: {str(e)}'
            logger.error(error_msg)
            safe_error_msg = error_msg.replace('<', '&lt;').replace('>', '&gt;')
            await self.message_queue.add(wand, safe_error_msg, verbatim=True)
            return P(error_msg, cls='text-invalid')

    def _get_selenium_profile_paths(self, pipeline_id: str, desired_profile_leaf_name: str = 'google_session') -> tuple[str, str]:
        """Get the user data directory and profile directory paths for Chrome.

        Returns a tuple of (user_data_dir_path, profile_directory_name) where:
        - user_data_dir_path is the parent directory for Chrome's user data
        - profile_directory_name is the specific profile to use within that directory
        """
        from pathlib import Path
        user_data_root = Path('data') / self.app_name / 'selenium_user_data'
        user_data_root.mkdir(parents=True, exist_ok=True)
        return (str(user_data_root), 'google_session')

    def _get_persistent_profile_paths(self, pipeline_id: str) -> tuple[str, str]:
        """Get the persistent user data directory and profile directory paths for Chrome.

        This version uses a fixed location that won't be cleared on server restart.
        """
        from pathlib import Path
        user_data_root = Path('data') / self.app_name / 'persistent_profiles'
        user_data_root.mkdir(parents=True, exist_ok=True)
        return (str(user_data_root), 'google_session')

    async def step_03(self, request):
        """Handles GET request for Ephemeral Login Test."""
        pipeline_id = self.pipulate.db.get('pipeline_id', 'unknown')
        if not pipeline_id or pipeline_id == 'unknown':
            return JSONResponse(status_code=400, content={'error': 'No pipeline ID found in db'})
        user_data_dir, profile_dir = self._get_selenium_profile_paths(pipeline_id)
        step_data = self.pipulate.get_step_data(pipeline_id, 'step_03', {})
        is_completed = step_data.get('session_test_complete', False)
        is_confirmed = step_data.get('session_test_confirmed', False)
        step_index = self.steps_indices['step_03']
        next_step_id = self.steps[step_index + 1].id if step_index < len(self.steps) - 1 else 'finalize'
        state = self.pipulate.read_state(pipeline_id)
        is_being_reverted = state.get('_revert_target') == 'step_03'
        if is_confirmed:
            return Div(self.pipulate.display_revert_header(step_id='step_03', app_name=self.app_name, message='Ephemeral Login Test', steps=self.steps), Div(id=next_step_id, hx_get=f'/{self.app_name}/{next_step_id}', hx_trigger='load'), id='step_03')
        elif is_completed and (not is_being_reverted):
            return Div(Card(H3('Ephemeral Login Test'), P('✅ Test completed!'), P('Please confirm that you have successfully logged in and verified the session persistence.'), P(f'Profile directory: {user_data_dir}/{profile_dir}'), P('Note: This profile will be cleared when the server restarts.', style='color: #666; font-style: italic;'), Form(Button('Check Login Status', type='submit', cls='secondary'), hx_post=f'/{self.app_name}/step_03_submit', hx_target='#step_03'), Form(Button('Confirm Test Completion', type='submit', cls='primary'), hx_post=f'/{self.app_name}/step_03_confirm', hx_target='#step_03')), Div(id=next_step_id, hx_get=f'/{self.app_name}/{next_step_id}', hx_trigger='load'), id='step_03')
        else:
            return Div(Card(H3('Ephemeral Login Test'), P('Instructions:'), P('1. Click the button below to open Google in a new browser window'), P('2. Log in to your Google account'), P('3. Close the browser window when done'), P('4. Return here to check your session status'), P('Note: This profile will be cleared when the server restarts.', style='color: #666; font-style: italic;'), Form(Button('Open Google & Log In', type='submit', cls='primary'), hx_post=f'/{self.app_name}/step_03_submit', hx_target='#step_03')), id='step_03')

    async def step_03_submit(self, request):
        """Handles POST request for Ephemeral Login Test."""
        try:
            pipeline_id = self.pipulate.db.get('pipeline_id', 'unknown')
            if not pipeline_id or pipeline_id == 'unknown':
                return JSONResponse(status_code=400, content={'error': 'No pipeline ID found in db'})
            user_data_dir, profile_dir = self._get_selenium_profile_paths(pipeline_id)
            step_data = self.pipulate.get_step_data(pipeline_id, 'step_03', {})
            is_completed = step_data.get('session_test_complete', False)
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(f'--user-data-dir={user_data_dir}')
            chrome_options.add_argument(f'--profile-directory={profile_dir}')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': "\n                    Object.defineProperty(navigator, 'webdriver', {\n                        get: () => undefined\n                    });\n                    Object.defineProperty(navigator, 'apps', {\n                        get: () => [1, 2, 3, 4, 5]\n                    });\n                    Object.defineProperty(navigator, 'languages', {\n                        get: () => ['en-US', 'en']\n                    });\n                "})
            try:
                driver.get('https://www.google.com')
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, 'q')))
                try:
                    profile_pic = WebDriverWait(driver, 0.5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "img[alt*='Google Account']")))
                    is_logged_in = True
                    login_status = '✅ Logged In'
                except TimeoutException:
                    is_logged_in = False
                    login_status = '❌ Not Logged In'
                step_data['session_test_complete'] = True
                step_data['is_logged_in'] = is_logged_in
                step_data['user_data_dir'] = user_data_dir
                step_data['profile_dir'] = profile_dir
                state = self.pipulate.read_state(pipeline_id)
                state['step_03'] = step_data
                self.pipulate.write_state(pipeline_id, state)
                return Div(Card(H3('Ephemeral Login Test'), P('Instructions:'), P('1. A new browser window has opened with Google'), P('2. Log in to your Google account in that window'), P('3. After logging in, close the browser window'), P('4. Return here and click the button below to confirm test completion'), P(f'Current Status: {login_status}'), Form(Button('Check Login Status', type='submit', cls='secondary'), hx_post=f'/{self.app_name}/step_03_submit', hx_target='#step_03'), Form(Button('Confirm Test Completion', type='submit', cls='primary'), hx_post=f'/{self.app_name}/step_03_confirm', hx_target='#step_03')), id='step_03')
            except Exception as e:
                driver.quit()
                raise e
        except Exception as e:
            return JSONResponse(status_code=500, content={'error': str(e)})

    async def step_03_confirm(self, request):
        """Handle confirmation of Ephemeral Login Test."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_03'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = state.get(step_id, {})
        step_data[step.done] = True
        step_data['session_test_confirmed'] = True
        state[step_id] = step_data
        wand.write_state(pipeline_id, state)
        await self.message_queue.add(wand, 'Ephemeral login test confirmed!', verbatim=True)
        return Div(wand.display_revert_header(step_id=step_id, app_name=app_name, message='Ephemeral Login Test', steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)

    async def step_04(self, request):
        """Handles GET request for Persistent Login Test."""
        pipeline_id = self.pipulate.db.get('pipeline_id', 'unknown')
        if not pipeline_id or pipeline_id == 'unknown':
            return JSONResponse(status_code=400, content={'error': 'No pipeline ID found in db'})
        user_data_dir, profile_dir = self._get_persistent_profile_paths(pipeline_id)
        step_data = self.pipulate.get_step_data(pipeline_id, 'step_04', {})
        is_completed = step_data.get('persistent_session_test_complete', False)
        is_confirmed = step_data.get('persistent_session_test_confirmed', False)
        step_index = self.steps_indices['step_04']
        next_step_id = self.steps[step_index + 1].id if step_index < len(self.steps) - 1 else 'finalize'
        state = self.pipulate.read_state(pipeline_id)
        is_being_reverted = state.get('_revert_target') == 'step_04'
        if is_confirmed:
            return Div(self.pipulate.display_revert_header(step_id='step_04', app_name=self.app_name, message='Persistent Login Test', steps=self.steps), Div(id=next_step_id, hx_get=f'/{self.app_name}/{next_step_id}', hx_trigger='load'), id='step_04')
        elif is_completed and (not is_being_reverted):
            return Div(Card(H3('Persistent Login Test'), P('✅ Test completed!'), P('Please confirm that you have successfully logged in and verified the session persistence.'), P(f'Profile directory: {user_data_dir}/{profile_dir}'), P('Note: This profile will persist across server restarts.', style='color: #666; font-style: italic;'), Form(Button('Check Login Status', type='submit', cls='secondary'), hx_post=f'/{self.app_name}/step_04_submit', hx_target='#step_04'), Form(Button('Confirm Test Completion', type='submit', cls='primary'), hx_post=f'/{self.app_name}/step_04_confirm', hx_target='#step_04')), Div(id=next_step_id, hx_get=f'/{self.app_name}/{next_step_id}', hx_trigger='load'), id='step_04')
        else:
            return Div(Card(H3('Persistent Login Test'), P('Instructions:'), P('1. Click the button below to open Google in a new browser window'), P('2. Log in to your Google account'), P('3. Close the browser window when done'), P('4. Return here to check your session status'), P('Note: This profile will persist across server restarts.', style='color: #666; font-style: italic;'), Form(Button('Open Google & Log In', type='submit', cls='primary'), hx_post=f'/{self.app_name}/step_04_submit', hx_target='#step_04')), id='step_04')

    async def step_04_submit(self, request):
        """Handles POST request for Persistent Login Test."""
        try:
            pipeline_id = self.pipulate.db.get('pipeline_id', 'unknown')
            if not pipeline_id or pipeline_id == 'unknown':
                return JSONResponse(status_code=400, content={'error': 'No pipeline ID found in db'})
            user_data_dir, profile_dir = self._get_persistent_profile_paths(pipeline_id)
            step_data = self.pipulate.get_step_data(pipeline_id, 'step_04', {})
            is_completed = step_data.get('persistent_session_test_complete', False)
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(f'--user-data-dir={user_data_dir}')
            chrome_options.add_argument(f'--profile-directory={profile_dir}')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': "\n                    Object.defineProperty(navigator, 'webdriver', {\n                        get: () => undefined\n                    });\n                    Object.defineProperty(navigator, 'apps', {\n                        get: () => [1, 2, 3, 4, 5]\n                    });\n                    Object.defineProperty(navigator, 'languages', {\n                        get: () => ['en-US', 'en']\n                    });\n                "})
            try:
                driver.get('https://www.google.com')
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, 'q')))
                try:
                    profile_pic = WebDriverWait(driver, 0.5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "img[alt*='Google Account']")))
                    is_logged_in = True
                    login_status = '✅ Logged In'
                except TimeoutException:
                    is_logged_in = False
                    login_status = '❌ Not Logged In'
                step_data['persistent_session_test_complete'] = True
                step_data['is_logged_in'] = is_logged_in
                step_data['user_data_dir'] = user_data_dir
                step_data['profile_dir'] = profile_dir
                state = self.pipulate.read_state(pipeline_id)
                state['step_04'] = step_data
                self.pipulate.write_state(pipeline_id, state)
                return Div(Card(H3('Persistent Login Test'), P('Instructions:'), P('1. A new browser window has opened with Google'), P('2. Log in to your Google account in that window'), P('3. After logging in, close the browser window'), P('4. Return here and click the button below to confirm test completion'), P(f'Current Status: {login_status}'), Form(Button('Check Login Status', type='submit', cls='secondary'), hx_post=f'/{self.app_name}/step_04_submit', hx_target='#step_04'), Form(Button('Confirm Test Completion', type='submit', cls='primary'), hx_post=f'/{self.app_name}/step_04_confirm', hx_target='#step_04')), id='step_04')
            except Exception as e:
                driver.quit()
                raise e
        except Exception as e:
            return JSONResponse(status_code=500, content={'error': str(e)})

    async def step_04_confirm(self, request):
        """Handle confirmation of Persistent Login Test."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_04'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = state.get(step_id, {})
        step_data[step.done] = True
        step_data['persistent_session_test_confirmed'] = True
        state[step_id] = step_data
        wand.write_state(pipeline_id, state)
        await self.message_queue.add(wand, 'Persistent login test confirmed!', verbatim=True)
        return Div(wand.display_revert_header(step_id=step_id, app_name=app_name, message='Persistent Login Test', steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)

    async def step_05(self, request):
        """Handles GET request for Step 5 placeholder."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_05'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        placeholder_value = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and placeholder_value:
            wand.append_to_history(f'[WIDGET CONTENT] {step.show} (Finalized):\n{placeholder_value}')
            return Div(Card(H3(f'🔒 {step.show}: Completed')), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        if placeholder_value and state.get('_revert_target') != step_id:
            wand.append_to_history(f'[WIDGET CONTENT] {step.show} (Completed):\n{placeholder_value}')
            return Div(wand.display_revert_header(step_id=step_id, app_name=app_name, message=f'{step.show}: Complete', steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        else:
            wand.append_to_history(f'[WIDGET STATE] {step.show}: Showing input form')
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
            return Div(Card(H3(f'{step.show}'), P('This is a placeholder step. Click Proceed to continue to the next step.'), Form(Button('Next ▸', type='submit', cls='primary'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_05_submit(self, request):
        """Process the submission for Step 5 placeholder."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_05'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        placeholder_value = 'completed'
        await wand.set_step_data(pipeline_id, step_id, placeholder_value, steps)
        wand.append_to_history(f'[WIDGET CONTENT] {step.show}:\n{placeholder_value}')
        wand.append_to_history(f'[WIDGET STATE] {step.show}: Step completed')
        await self.message_queue.add(wand, f'{step.show} complete.', verbatim=True)
        return Div(wand.display_revert_header(step_id=step_id, app_name=app_name, message=f'{step.show}: Complete', steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
