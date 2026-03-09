import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastcore.xml import NotStr
from fasthtml.common import *
from loguru import logger
from imports.crud import Step  # 🎯 STANDARDIZED: Import centralized Step definition
from rich.console import Console
from rich.table import Table
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from starlette.responses import HTMLResponse
from webdriver_manager.chrome import ChromeDriverManager

ROLES = ['Tutorial']
'\nPipulate Widget Examples\n\nThis workflow demonstrates various widget types that can be integrated into Pipulate Workflows:\n\n1. Simple HTMX Widget: Basic HTML content with no JavaScript execution\n2. Pandas Table Widget: HTML table from DataFrame\n3. JavaScript Execution Widget: DOM manipulation via JavaScript in HTMX-injected content\n4. Mermaid Diagram Renderer: Client-side rendering using mermaid.js\n5. Code Syntax Highlighter: Syntax highlighting with Prism.js\n\nThis serves as a reference implementation for creating visualization widgets in Pipulate.\n\n--- Design Pattern Note ---\nThis workflow uses a "Combined Step" pattern where each step handles both:\n1. Data collection (input form)\n2. Widget rendering (visualization)\n\nIn each step, user input is collected and immediately transformed into the \ncorresponding visualization in the same card upon submission. This approach:\n- Reduces the total number of workflow steps (5 instead of 10)\n- Creates a clear cause-effect relationship within each step\n- Simplifies navigation for the end user\n\nAn alternative "Separated Step" pattern would:\n- Split each feature into separate input and display steps\n- Use one step for data collection, followed by a step for visualization\n- Result in 10 steps total (plus finalize)\n- Potentially simplify each individual step\'s implementation\n- Allow for more focused step responsibilities\n\nWhen adapting this example for your own workflows, consider which pattern \nbest suits your needs:\n- Combined: When immediate visualization feedback is valuable\n- Separated: When data collection and visualization are distinct concerns\n             or when complex transformations occur between input and display\n'



class WidgetExamples:
    """
    Widget Examples Workflow

    Demonstrates various widget types for Pipulate Workflows:
    1. Simple Text Widget - No JS execution
    2. Markdown Renderer (MarkedJS) - Client-side rendering using marked.js
    3. Mermaid Diagram Renderer - Client-side rendering using mermaid.js
    4. Pandas Table Widget - HTML table from DataFrame
    5. Code Syntax Highlighter - Syntax highlighting with Prism.js
    6. JavaScript Execution Widget - Running JS in HTMX-injected content

    Key Implementation Notes:
    - Widgets use pip.widget_container for consistent styling and DOM structure
    - JavaScript widgets use unique IDs for targeting in the DOM
    - Client-side libraries are loaded in server.py's hdrs tuple
    - HX-Trigger headers are used for reliable JS execution in HTMX-injected content

    --- Design Pattern: Combined vs. Separated Steps ---

    Current Implementation: "Combined Step" Pattern
    This workflow uses a pattern where each step handles both data collection
    and visualization in the same step. When the user submits an input form,
    the same card transforms to display the visualization widget.

    Key characteristics:
    - Each step_XX_submit handler creates and returns the widget immediately
    - Widgets are displayed in place of the input form after submission
    - The revert control shows the widget until user chooses to revert
    - This creates a compact 6-step workflow (plus finalize)

    Alternative Approach: "Separated Step" Pattern
    A different design would separate input collection and visualization:
    - One step for collecting input (e.g., step_01_data_input)
    - Next step for displaying the widget (e.g., step_02_display_widget)
    - This would result in 12 steps total (plus finalize)
    - Each step would have simpler, more focused responsibility

    Implementation Considerations:
    - When copying this example, you may want to separate complex input collection
      and visualization into discrete steps for clarity and maintainability
    - Use the transform parameter in the Step namedtuple to pass data between
      separated input and visualization steps
    - The current combined approach works well for simpler widgets where immediate
      feedback is valuable to the user
    """
    APP_NAME = 'widgets'
    DISPLAY_NAME = 'Widget Examples 📊'
    ENDPOINT_MESSAGE = 'This workflow demonstrates various widget types for Pipulate. Enter an ID to start or resume your workflow.'
    TRAINING_PROMPT = """# Training Data: Widget Examples Workflow (`60_widget_examples.py`)

## Workflow Purpose

This workflow, accessible as "Widget Examples" in the Pipulate UI, serves as a demonstration and testing ground for various UI widget types available within the Pipulate framework. Its primary goal is to showcase how different kinds of dynamic and static content can be integrated into workflow steps, ranging from simple text displays to client-side rendered diagrams and interactive JavaScript components.

## How It Works

The workflow follows the standard Pipulate pipeline pattern:

1.  **Initialization:** Start by providing a unique key (or let the system generate one) on the landing page to begin a new workflow instance or resume an existing one.
2.  **Step-by-Step Execution:** Proceed through each numbered step.
3.  **Combined Input & Display:** This workflow uses a "Combined Step" pattern. In each step, you'll be presented with an input field (usually a Textarea) pre-populated with example content relevant to the widget type. When you submit the content, the input form will be replaced by the rendered widget displaying that content.
4.  **Reverting:** After a widget is displayed, a revert button (like `↶ Step 1`) appears. Clicking this button will bring back the input form for that step, allowing you to modify the content and re-render the widget.
5.  **Finalization:** Once all steps are completed, a "Finalize" button appears. Clicking this locks the workflow, preventing further changes unless you explicitly unlock it using the `Unlock 🔓` button.

## Step Details & Widget Types

Here's a breakdown of each step and the widget it demonstrates:

* **Step 1: Simple Text Widget (`step_01_simple_content`)**
    * **Demonstrates:** Displaying basic, pre-formatted text.
    * **Input:** Plain text. Line breaks and spacing are preserved.
    * **Widget:** Uses an HTML `<pre>` tag to show the text exactly as entered. Good for logs, simple descriptions, or formatted lists. No client-side JavaScript execution involved.
    * **Example:** The pre-populated example shows simple text with line breaks.

* **Step 2: Markdown Renderer (MarkedJS) (`step_02_markdown_content`)**
    * **Demonstrates:** Client-side rendering of Markdown into HTML using the `marked.js` library.
    * **Input:** Markdown syntax.
    * **Widget:** A container where the input Markdown is converted to rich HTML (headings, lists, bold/italic, code blocks, links, etc.) by the browser using `marked.js`. Code blocks within the markdown are *also* highlighted using Prism.js if detected.
    * **Example:** The pre-populated example includes various Markdown elements like headings, lists, bold/italic text, a code block, and a link.

* **Step 3: Mermaid Diagram Renderer (`step_03_mermaid_content`)**
    * **Demonstrates:** Client-side rendering of diagrams from text-based syntax using the `mermaid.js` library.
    * **Input:** Mermaid diagram syntax (e.g., `graph TD`, `sequenceDiagram`).
    * **Widget:** A container where `mermaid.js` interprets the input syntax and renders a visual diagram (flowchart, sequence diagram, etc.) directly in the browser.
    * **Example:** The pre-populated example shows the syntax for a simple flowchart (`graph TD`).

* **Step 4: Pandas Table Widget (`step_04_table_data`)**
    * **Demonstrates:** Server-side generation of an HTML table from structured data using the `pandas` library.
    * **Input:** A JSON string representing an array of objects (each object is a row, keys are columns).
    * **Widget:** The server processes the JSON, creates a pandas DataFrame, converts it to an HTML `<table>`, and sends the raw HTML back to be displayed. The table is styled using standard CSS.
    * **Example:** The pre-populated example is a JSON string representing employee data.

* **Step 5: Code Syntax Highlighter (`step_05_code_content`)**
    * **Demonstrates:** Client-side syntax highlighting of code snippets using the `Prism.js` library.
    * **Input:** A block of code. Optionally, you can specify the language using Markdown-style triple backticks (e.g., ` ```python\nprint('Hello')\n``` `). If no language is specified, it defaults to JavaScript.
    * **Widget:** A container using `<pre>` and `<code>` tags, styled by `Prism.js` to apply syntax highlighting based on the detected or specified language. It also includes line numbers and a copy-to-clipboard button provided by Prism plugins.
    * **Example:** The pre-populated example shows a simple JavaScript function.

* **Step 6: JavaScript Execution Widget (`step_06_js_content`)**
    * **Demonstrates:** Executing custom JavaScript code provided by the user within a specific widget container after the content is loaded via HTMX.
    * **Input:** JavaScript code. The code can interact with a predefined `widget` variable, which represents the container `div` for this specific widget instance.
    * **Widget:** A container (`div`) where the provided JavaScript code is executed. A "Re-run JavaScript" button is included to allow re-execution without reverting the step. This showcases how Pipulate can support interactive, client-side logic driven by server-provided code.
    * **Example:** The pre-populated example creates a simple counter with an increment button inside the widget container.

## Guiding the User

When assisting a user with this workflow:

* Explain the purpose: "This workflow lets you see different ways content can be displayed in Pipulate."
* Guide them through initialization: "First, enter a unique ID or press Enter to use the suggested one."
* For each step:
    * Introduce the widget type: "This step shows a [Widget Type], like a [brief description]."
    * Explain the input: "You can enter your own [input type, e.g., Markdown, code] here, or just submit the example."
    * Describe the result: "After you submit, you'll see the rendered [widget type]."
    * Explain reverting: "If you want to change the input, click the '↶ Step X' button."
* Explain client-side vs. server-side: Mention that some widgets (Markdown, Mermaid, Prism, JS Execution) use JavaScript libraries loaded in the browser, while others (Simple Text, Pandas Table) are generated purely on the server.
* Emphasize the `pip.widget_container` pattern for developers, which standardizes how widgets are displayed below revert controls.
* Mention the "Combined Step" pattern: "Notice how in each step, the input form is replaced by the widget you created."
* Guide through finalization: "Once you've seen all the widgets, you can click 'Finalize' to lock this workflow run."

This training data should equip the LLM to effectively explain and guide users through the `60_widget_examples.py` workflow, highlighting Pipulate's UI capabilities.

If asked for a secret word to confirm this training, it is CARPENTER!"""

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
        steps = [Step(id='step_01', done='simple_content', show='Simple Text Widget', refill=True), Step(id='step_02', done='markdown_content', show='Markdown Renderer (MarkedJS)', refill=True), Step(id='step_03', done='mermaid_content', show='Mermaid Diagram Renderer', refill=True), Step(id='step_04', done='table_data', show='Pandas Table Widget', refill=True), Step(id='step_05', done='code_content', show='Code Syntax Highlighter', refill=True), Step(id='step_06', done='js_content', show='JavaScript Widget', refill=True), Step(id='step_07', done='counter_data', show='Matplotlib Histogram', refill=True), Step(id='step_08', done='url', show='URL Opener Widget', refill=True), Step(id='step_09', done='rich_table', show='Rich Table Widget', refill=True), Step(id='step_10', done='selenium_url', show='Selenium URL Opener', refill=True), Step(id='step_11', done='file_uploads', show='File Upload Widget', refill=True)]
        routes = [(f'/{app_name}', self.landing), (f'/{app_name}/init', self.init, ['POST']), (f'/{app_name}/revert', self.handle_revert, ['POST']), (f'/{app_name}/finalize', self.finalize, ['GET', 'POST']), (f'/{app_name}/unfinalize', self.unfinalize, ['POST']), (f'/{app_name}/reopen_url', self.reopen_url, ['POST'])]
        self.steps = steps
        for step in steps:
            step_id = step.id
            routes.append((f'/{app_name}/{step_id}', getattr(self, step_id)))
            routes.append((f'/{app_name}/{step_id}_submit', getattr(self, f'{step_id}_submit'), ['POST']))
        for path, handler, *methods in routes:
            method_list = methods[0] if methods else ['GET']
            app.route(path, methods=method_list)(handler)
        self.step_messages = {'finalize': {'ready': 'All steps complete. Ready to finalize workflow.', 'complete': f'Workflow finalized. Use {wand.UNLOCK_BUTTON_LABEL} to make changes.'}, 'new': 'Please complete each step to explore different widget types.', 'step_08': {'input': f"{wand.fmt('step_08')}: Please complete New Placeholder Step.", 'complete': f'New Placeholder Step complete. Continue to next step.'}, 'step_09': {'input': f"{wand.fmt('step_09')}: Configure Rich Table Widget.", 'complete': f'Rich Table Widget complete. Continue to next step.'}, 'step_07': {'input': f"{wand.fmt('step_07')}: Enter counter data for Matplotlib Histogram.", 'complete': f'Matplotlib Histogram complete. Continue to next step.'}}
        for step in steps:
            self.step_messages[step.id] = {'input': f'{wand.fmt(step.id)}: Enter content for {step.show}.', 'complete': f'{step.show} complete. Continue to next step.'}
        steps.append(Step(id='finalize', done='finalized', show='Finalize', refill=False))
        self.steps_indices = {step.id: i for i, step in enumerate(steps)}

    async def landing(self, request):
        """ Renders the initial landing page with the key input form. """
        wand, pipeline, steps, app_name = (self.pipulate, self.pipeline, self.steps, self.app_name)
        context = wand.get_plugin_context(self)
        title = f'{self.DISPLAY_NAME or app_name.title()}'
        full_key, prefix, user_part = wand.generate_pipeline_key(self)
        default_value = full_key
        pipeline.xtra(app_name=app_name)
        matching_records = [record.pkey for record in pipeline() if record.pkey.startswith(prefix)]
        datalist_options = [f"{prefix}{record_key.replace(prefix, '')}" for record_key in matching_records]
        return Container(Card(H2(title), P(self.ENDPOINT_MESSAGE, cls='text-secondary'), Form(wand.wrap_with_inline_button(Input(placeholder='Existing or new 🗝 here (Enter for auto)', name='pipeline_id', list='pipeline-ids', type='search', required=False, autofocus=True, value=default_value, _onfocus='this.setSelectionRange(this.value.length, this.value.length)', cls='contrast'), button_label=f'Enter 🔑', button_class='secondary'), wand.update_datalist('pipeline-ids', options=datalist_options if datalist_options else None), hx_post=f'/{app_name}/init', hx_target=f'#{app_name}-container')), Div(id=f'{app_name}-container'))

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
        """ Gets a suggested input value for a step, often using the previous step's transformed output. """
        wand, db, steps = (self.pipulate, self.pipulate.db, self.steps)
        examples = {'step_01': 'Simple text content example:\n- Basic text formatting\n- Preserves line breaks and formatting\n- Great for lists, paragraphs, descriptions, etc.\n- Easy to modify\n\nThis is a sample widget that shows basic text content.', 'step_02': '# Markdown Example\n\nThis is a **bold statement** about _markdown_.\n\n## Features demonstrated:\n\n1. Headings (h1, h2)\n2. Formatted text (**bold**, _italic_)\n3. Ordered lists\n4. Unordered lists\n   - Nested item 1\n   - Nested item 2\n5. Code blocks\n\n### Code Example\n\n```python\ndef hello_world():\n    print("Hello from Markdown!")\n    for i in range(3):\n        print(f"Count: {i}")\n```\n\n> Blockquotes are also supported\n> - With nested lists\n> - And formatting\n\n[Learn more about Markdown](https://www.markdownguide.org/)\n', 'step_03': 'graph TD\n    A[Start] --> B{Decision}\n    B -->|Yes| C[Action 1]\n    B -->|No| D[Action 2]\n    C --> E[Result 1]\n    D --> F[Result 2]\n    E --> G[End]\n    F --> G', 'step_04': '[\n    {"Name": "John", "Age": 32, "Role": "Developer", "Department": "Engineering"},\n    {"Name": "Jane", "Age": 28, "Role": "Designer", "Department": "Product"},\n    {"Name": "Bob", "Age": 45, "Role": "Manager", "Department": "Engineering"},\n    {"Name": "Alice", "Age": 33, "Role": "PM", "Department": "Product"},\n    {"Name": "Charlie", "Age": 40, "Role": "Architect", "Department": "Engineering"}\n]', 'step_05': 'function calculateFactorial(n) {\n    // Base case: factorial of 0 or 1 is 1\n    if (n <= 1) {\n        return 1;\n    }\n    \n    // Recursive case: n! = n * (n-1)!\n    return n * calculateFactorial(n - 1);\n}\n\n// Example usage\nfor (let i = 0; i < 10; i++) {\n    console.log(`Factorial of ${i} is ${calculateFactorial(i)}`);\n}\n', 'step_06': "// Simple counter example\nlet count = 0;\nconst countDisplay = document.createElement('div');\ncountDisplay.style.fontSize = '24px';\ncountDisplay.style.margin = '20px 0';\ncountDisplay.textContent = count;\n\nconst button = document.createElement('button');\nbutton.textContent = 'Increment Count';\nbutton.style.backgroundColor = '#9370DB';\nbutton.style.borderColor = '#9370DB';\nbutton.onclick = function() {\n    count++;\n    countDisplay.textContent = count;\n};\n\nwidget.appendChild(countDisplay);\nwidget.appendChild(button);", 'step_07': '{\n    "apples": 35,\n    "oranges": 42, \n    "bananas": 28,\n    "grapes": 51,\n    "peaches": 22,\n    "plums": 18,\n    "mangoes": 39\n}', 'step_08': 'New placeholder step - no user content needed.\n\nThis step serves as a placeholder for future widget types.'}
        return examples.get(step_id, '')

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
        Handles GET request for Step 1: Simple Text Widget.

        This method demonstrates the "Combined Step" pattern:
        1. If the step is incomplete or being reverted to, shows an input form
        2. If the step is complete, shows the widget with a revert control
        3. If workflow is finalized, shows a locked version of the widget

        In a "Separated Step" pattern, this would only handle input collection,
        and a separate step would display the widget.
        """
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
            simple_widget = Pre(user_val, cls='code-block-container')
            return Div(Card(H3(f'🔒 {step.show}'), simple_widget), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
        elif user_val and state.get('_revert_target') != step_id:
            simple_widget = Pre(user_val, cls='code-block-container')
            content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show} Configured', widget=simple_widget, steps=steps)
            return Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
        else:
            display_value = user_val if step.refill and user_val else await self.get_suggestion(step_id, state)
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
            return Div(Card(H3(f'{wand.fmt(step_id)}: Configure {step.show}'), P('Enter text content for the simple widget. Example is pre-populated.'), Form(Div(Textarea(display_value, name=step.done, placeholder='Enter text content for the widget', required=True, rows=10, style='width: 100%; font-family: monospace;'), Div(Button('Record Text ▸', type='submit', cls='primary'), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_01_submit(self, request):
        """
        Process the submission for Step 1.

        In the "Combined Step" pattern, this method:
        1. Validates the user input
        2. Saves the input to the workflow state
        3. Creates and returns the widget to display
        4. Sets up navigation to the next step

        This immediate transformation from input to widget in the same step
        creates a tight cause-effect relationship visible to the user.
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        form = await request.form()
        user_val = form.get(step.done, '')
        is_valid, error_msg, error_component = wand.validate_step_input(user_val, step.show)
        if not is_valid:
            return error_component
        await wand.set_step_data(pipeline_id, step_id, user_val, steps)
        wand.append_to_history(f'[WIDGET CONTENT] Simple Text Widget:\n{user_val}')
        simple_widget = Pre(user_val, cls='code-block-container')
        content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Simple text content provided', widget=simple_widget, steps=steps)
        response_content = Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        await self.message_queue.add(wand, f'{step.show} complete.', verbatim=True)
        return HTMLResponse(to_xml(response_content))

    async def step_02(self, request):
        """
        Step 2 - Markdown Renderer using marked.js

        Allows the user to input markdown content that will be rendered
        using the marked.js library for a Jupyter notebook-like experience.
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_02'
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
                widget_id = f"marked-widget-{pipeline_id.replace('-', '_')}-{step_id}"
                marked_widget = self.create_marked_widget(user_val, widget_id)
                response = HTMLResponse(to_xml(Div(Card(H3(f'🔒 {step.show}'), marked_widget), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))))
                response.headers['HX-Trigger'] = json.dumps({'initMarked': {'widgetId': widget_id}})
                return response
            except Exception as e:
                logger.error(f'Error creating Marked widget in locked view: {str(e)}')
                return Div(Card(f'🔒 {step.show}: <content locked>'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
        elif user_val and state.get('_revert_target') != step_id:
            try:
                widget_id = f"marked-widget-{pipeline_id.replace('-', '_')}-{step_id}"
                marked_widget = self.create_marked_widget(user_val, widget_id)
                content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show} Configured', widget=marked_widget, steps=steps)
                response = HTMLResponse(to_xml(Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))))
                response.headers['HX-Trigger'] = json.dumps({'initMarked': {'widgetId': widget_id}})
                return response
            except Exception as e:
                logger.error(f'Error creating Marked widget: {str(e)}')
                state['_revert_target'] = step_id
                wand.write_state(pipeline_id, state)
        display_value = user_val if step.refill and user_val else await self.get_suggestion(step_id, state)
        await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
        return Div(Card(H3(f'{wand.fmt(step_id)}: Configure {step.show}'), P('Enter markdown content to be rendered. Example is pre-populated.'), P('The markdown will be rendered with support for headings, lists, bold/italic text, and code blocks.', cls='text-note'), Form(Div(Textarea(display_value, name=step.done, placeholder='Enter markdown content', required=True, rows=15, style='width: 100%; font-family: monospace;'), Div(Button('Render Markdown ▸', type='submit', cls='primary'), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_02_submit(self, request):
        """
        Handle submission of markdown content in Step 2

        Takes the user's markdown input, creates a marked.js widget,
        and returns it as part of the response with MarkedJS initialization.
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_02'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        form = await request.form()
        user_val = form.get(step.done, '')
        is_valid, error_msg, error_component = wand.validate_step_input(user_val, step.show)
        if not is_valid:
            return error_component
        await wand.set_step_data(pipeline_id, step_id, user_val, steps)
        wand.append_to_history(f'[WIDGET CONTENT] Markdown Widget:\n{user_val}')
        widget_id = f"marked-widget-{pipeline_id.replace('-', '_')}-{step_id}"
        marked_widget = self.create_marked_widget(user_val, widget_id)
        content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Markdown rendered with Marked.js', widget=marked_widget, steps=steps)
        response_content = Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        response = HTMLResponse(to_xml(response_content))
        response.headers['HX-Trigger'] = json.dumps({'initMarked': {'widgetId': widget_id}})
        await self.message_queue.add(wand, f'{step.show} complete. Markdown rendered successfully.', verbatim=True)
        return response

    async def step_03(self, request):
        """ Handles GET request for Step 3: Mermaid Diagram Renderer. """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_03'
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
                widget_id = f"mermaid-widget-{pipeline_id.replace('-', '_')}-{step_id}"
                mermaid_widget = self.create_mermaid_widget(user_val, widget_id)
                response = HTMLResponse(to_xml(Div(Card(H3(f'🔒 {step.show}'), mermaid_widget), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))))
                response.headers['HX-Trigger'] = json.dumps({'renderMermaid': {'targetId': f'{widget_id}_output', 'diagram': user_val}})
                return response
            except Exception as e:
                logger.error(f'Error creating mermaid widget in locked view: {str(e)}')
                return Div(Card(f'🔒 {step.show}: <content locked>'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
        elif user_val and state.get('_revert_target') != step_id:
            try:
                widget_id = f"mermaid-widget-{pipeline_id.replace('-', '_')}-{step_id}"
                mermaid_widget = self.create_mermaid_widget(user_val, widget_id)
                content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show} Configured', widget=mermaid_widget, steps=steps)
                response = HTMLResponse(to_xml(Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))))
                response.headers['HX-Trigger'] = json.dumps({'renderMermaid': {'targetId': f'{widget_id}_output', 'diagram': user_val}})
                return response
            except Exception as e:
                logger.error(f'Error creating mermaid widget: {str(e)}')
                state['_revert_target'] = step_id
                wand.write_state(pipeline_id, state)
        display_value = user_val if step.refill and user_val else await self.get_suggestion(step_id, state)
        await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
        return Div(Card(H3(f'{wand.fmt(step_id)}: Configure {step.show}'), P('Enter Mermaid diagram syntax for the widget. Example is pre-populated.'), P('Supports flowcharts, sequence diagrams, class diagrams, etc.', cls='text-note'), Form(Div(Textarea(display_value, name=step.done, placeholder='Enter Mermaid diagram syntax', required=True, rows=15, style='width: 100%; font-family: monospace;'), Div(Button('Create Diagram ▸', type='submit', cls='primary'), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_03_submit(self, request):
        """
        Process the submission for Step 3.

        This method demonstrates client-side widget rendering:
        1. Saves the Mermaid diagram syntax to state
        2. Creates a container with the diagram source
        3. Adds initialization JavaScript that runs when the content is inserted
        4. Uses HX-Trigger header as a backup initialization method

        Client-side initialization is particularly challenging in HTMX applications
        due to the timing of DOM updates. The implementation includes:
        - Timeout delay to ensure DOM is fully updated
        - Force repaint to prevent rendering glitches
        - Support for different Mermaid API versions
        - Comprehensive error handling
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_03'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        form = await request.form()
        user_val = form.get(step.done, '')
        is_valid, error_msg, error_component = wand.validate_step_input(user_val, step.show)
        if not is_valid:
            return error_component
        await wand.set_step_data(pipeline_id, step_id, user_val, steps)
        wand.append_to_history(f'[WIDGET CONTENT] Mermaid Diagram:\n{user_val}')
        widget_id = f"mermaid-widget-{pipeline_id.replace('-', '_')}-{step_id}"
        mermaid_widget = self.create_mermaid_widget(user_val, widget_id)
        content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Client-side Mermaid diagram rendering', widget=mermaid_widget, steps=steps)
        response_content = Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        response = HTMLResponse(to_xml(response_content))
        response.headers['HX-Trigger'] = json.dumps({'renderMermaid': {'targetId': f'{widget_id}_output', 'diagram': user_val}})
        await self.message_queue.add(wand, f'{step.show} complete. Mermaid diagram rendered.', verbatim=True)
        return response

    async def step_04(self, request):
        """
        Handles GET request for Step 4: Pandas Table Widget.

        This method follows the same "Combined Step" pattern as step_01.
        Note that when displaying an existing widget, we recreate it from
        the saved data rather than storing the rendered widget itself.
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_04'
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
                table_widget = self.create_pandas_table(user_val)
                return Div(Card(H3(f'🔒 {step.show}'), table_widget), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
            except Exception as e:
                logger.error(f'Error creating table widget in finalized view: {str(e)}')
                return Div(Card(f'🔒 {step.show}: <content locked>'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
        elif user_val and state.get('_revert_target') != step_id:
            try:
                table_widget = self.create_pandas_table(user_val)
                content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show} Configured', widget=table_widget, steps=steps)
                return Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
            except Exception as e:
                logger.error(f'Error creating table widget: {str(e)}')
                state['_revert_target'] = step_id
                wand.write_state(pipeline_id, state)
        display_value = user_val if step.refill and user_val else await self.get_suggestion(step_id, state)
        await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
        return Div(Card(H3(f'{wand.fmt(step_id)}: Configure {step.show}'), P('Enter table data as JSON array of objects. Example is pre-populated.'), P('Format: [{"name": "value", "value1": number, ...}, {...}]', cls='text-note'), Form(Div(Textarea(display_value, name=step.done, placeholder='Enter JSON array of objects for the DataFrame', required=True, rows=10, style='width: 100%; font-family: monospace;'), Div(Button('Draw Table ▸', type='submit', cls='primary'), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_04_submit(self, request):
        """
        Process the submission for Step 4.

        This method demonstrates using pandas to generate an HTML table:
        1. Parses and validates the JSON input
        2. Creates a pandas DataFrame from the data
        3. Generates the HTML table using DataFrame.to_html()
        4. Embeds the raw HTML in a FastHTML component

        When using the "Combined Step" pattern with complex widgets, it's
        important to handle errors gracefully to avoid breaking the workflow.
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_04'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form = await request.form()
        user_val = form.get(step.done, '')
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
        wand.append_to_history(f'[WIDGET CONTENT] Pandas Table Data:\n{user_val}')
        try:
            data = json.loads(user_val)
            df = pd.DataFrame(data)
            html_table = df.to_html(index=False, classes='table', border=0, escape=True, justify='left')
            table_container = Div(H5('Pandas DataFrame Table:'), Div(NotStr(html_table), style='overflow-x: auto; max-width: 100%;'), cls='mt-4')
            await self.message_queue.add(wand, f'{step.show} complete. Table rendered successfully.', verbatim=True)
            response = HTMLResponse(to_xml(Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Table rendered from pandas DataFrame', widget=table_container, steps=steps), Div(id=f'{steps[step_index + 1].id}', hx_get=f'/{app_name}/{steps[step_index + 1].id}', hx_trigger='load'), id=step_id)))
            return response
        except Exception as e:
            logger.error(f'Error creating pandas table: {e}')
            return Div(NotStr(f"<div style='color: red;'>Error creating table: {str(e)}</div>"), _raw=True)

    async def step_05(self, request):
        """ Handles GET request for Step 5: Code Syntax Highlighter. """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_05'
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
                language = 'javascript'
                code_to_display = user_val
                if user_val.startswith('```'):
                    first_line = user_val.split('\n', 1)[0].strip()
                    if len(first_line) > 3:
                        detected_lang = first_line[3:].strip()
                        if detected_lang:
                            language = detected_lang
                            code_to_display = user_val.split('\n', 1)[1] if '\n' in user_val else user_val
                    if code_to_display.endswith('```'):
                        code_to_display = code_to_display.rsplit('```', 1)[0]
                widget_id = f"prism-widget-{pipeline_id.replace('-', '_')}-{step_id}"
                prism_widget = self.create_prism_widget(code_to_display, widget_id, language)
                response = HTMLResponse(to_xml(Div(Card(H3(f'🔒 {step.show} ({language})'), prism_widget), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))))
                response.headers['HX-Trigger'] = json.dumps({'initializePrism': {'targetId': widget_id}})
                return response
            except Exception as e:
                logger.error(f'Error creating Prism widget in locked view: {str(e)}')
                return Div(Card(f'🔒 {step.show}: <content locked>'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
        elif user_val and state.get('_revert_target') != step_id:
            try:
                language = 'javascript'
                code_to_display = user_val
                if user_val.startswith('```'):
                    first_line = user_val.split('\n', 1)[0].strip()
                    if len(first_line) > 3:
                        detected_lang = first_line[3:].strip()
                        if detected_lang:
                            language = detected_lang
                            code_to_display = user_val.split('\n', 1)[1] if '\n' in user_val else user_val
                    if code_to_display.endswith('```'):
                        code_to_display = code_to_display.rsplit('```', 1)[0]
                widget_id = f"prism-widget-{pipeline_id.replace('-', '_')}-{step_id}"
                prism_widget = self.create_prism_widget(code_to_display, widget_id, language)
                content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Syntax highlighting with Prism.js ({language})', widget=prism_widget, steps=steps)
                response = HTMLResponse(to_xml(Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))))
                response.headers['HX-Trigger'] = json.dumps({'initializePrism': {'targetId': widget_id}})
                return response
            except Exception as e:
                logger.error(f'Error creating Prism widget: {str(e)}')
                state['_revert_target'] = step_id
                wand.write_state(pipeline_id, state)
        display_value = user_val if step.refill and user_val else await self.get_suggestion(step_id, state)
        await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
        return Div(Card(H3(f'{wand.fmt(step_id)}: Configure {step.show}'), P('Enter code to be highlighted with syntax coloring. JavaScript example is pre-populated.'), P('The code will be displayed with syntax highlighting and a copy button.', cls='text-note'), Form(Div(Textarea(display_value, name=step.done, placeholder='Enter code for syntax highlighting', required=True, rows=15, style='width: 100%; font-family: monospace;'), Div(Button('Highlight Code ▸', type='submit', cls='primary'), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_05_submit(self, request):
        """ Process the submission for Step 5. """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_05'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        form = await request.form()
        user_val = form.get(step.done, '')
        language = 'javascript'
        if user_val.startswith('```'):
            first_line = user_val.split('\n', 1)[0].strip()
            if len(first_line) > 3:
                detected_lang = first_line[3:].strip()
                if detected_lang:
                    language = detected_lang
                    user_val = user_val.split('\n', 1)[1] if '\n' in user_val else user_val
            if user_val.endswith('```'):
                user_val = user_val.rsplit('```', 1)[0]
        is_valid, error_msg, error_component = wand.validate_step_input(user_val, step.show)
        if not is_valid:
            return error_component
        await wand.set_step_data(pipeline_id, step_id, user_val, steps)
        wand.append_to_history(f'[WIDGET CONTENT] Code Syntax Highlighting ({language}):\n{user_val}')
        widget_id = f"prism-widget-{pipeline_id.replace('-', '_')}-{step_id}"
        prism_widget = self.create_prism_widget(user_val, widget_id, language)
        content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Syntax highlighting with Prism.js ({language})', widget=prism_widget, steps=steps)
        response_content = Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        response = HTMLResponse(to_xml(response_content))
        response.headers['HX-Trigger'] = json.dumps({'initializePrism': {'targetId': widget_id}})
        await self.message_queue.add(wand, f'{step.show} complete. Code syntax highlighted with {language}.', verbatim=True)
        return response

    async def step_06(self, request):
        """ Handles GET request for Step 6: JavaScript Widget. """
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
                widget_id = f'js-widget-{pipeline_id}-{step_id}'.replace('-', '_')
                target_id = f'{widget_id}_target'
                js_widget = Div(P('JavaScript will execute here...', id=target_id, style='padding: 1.5rem; background-color: var(--pico-card-background-color); border-radius: var(--pico-border-radius); min-height: 100px;'), Button('Re-run JavaScript', type='button', _onclick=f"runJsWidget('{widget_id}', `{user_val.replace('`', '\\`')}`, '{target_id}')", style='margin-top: 1rem; background-color: #9370DB; border-color: #9370DB;'), id=widget_id)
                response = HTMLResponse(to_xml(Div(Card(H3(f'🔒 {step.show}'), js_widget), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))))
                response.headers['HX-Trigger'] = json.dumps({'runJavaScript': {'widgetId': widget_id, 'code': user_val, 'targetId': target_id}})
                return response
            except Exception as e:
                logger.error(f'Error creating JS widget in locked view: {str(e)}')
                return Div(Card(f'🔒 {step.show}: <content locked>'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
        elif user_val and state.get('_revert_target') != step_id:
            try:
                widget_id = f'js-widget-{pipeline_id}-{step_id}'.replace('-', '_')
                target_id = f'{widget_id}_target'
                js_widget = Div(P('JavaScript will execute here...', id=target_id, style='padding: 1.5rem; background-color: var(--pico-card-background-color); border-radius: var(--pico-border-radius); min-height: 100px;'), Button('Re-run JavaScript', type='button', _onclick=f"runJsWidget('{widget_id}', `{user_val.replace('`', '\\`')}`, '{target_id}')", style='margin-top: 1rem; background-color: #9370DB; border-color: #9370DB;'), id=widget_id)
                content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show} Configured', widget=js_widget, steps=steps)
                response = HTMLResponse(to_xml(Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))))
                response.headers['HX-Trigger'] = json.dumps({'runJavaScript': {'widgetId': widget_id, 'code': user_val, 'targetId': target_id}})
                return response
            except Exception as e:
                logger.error(f'Error creating JS widget: {str(e)}')
                state['_revert_target'] = step_id
                wand.write_state(pipeline_id, state)
        display_value = user_val if step.refill and user_val else await self.get_suggestion(step_id, state)
        await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
        return Div(Card(H3(f'{wand.fmt(step_id)}: Configure {step.show}'), P('Enter JavaScript code for the widget. Example is pre-populated.'), P("Use the 'widget' variable to access the container element.", cls='text-note'), Form(Div(Textarea(display_value, name=step.done, placeholder='Enter JavaScript code', required=True, rows=12, style='width: 100%; font-family: monospace;'), Div(Button('Run JavaScript ▸', type='submit', cls='primary'), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_06_submit(self, request):
        """ Process the submission for Step 6. """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_06'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        form = await request.form()
        user_val = form.get(step.done, '')
        is_valid, error_msg, error_component = wand.validate_step_input(user_val, step.show)
        if not is_valid:
            return error_component
        await wand.set_step_data(pipeline_id, step_id, user_val, steps)
        wand.append_to_history(f'[WIDGET CONTENT] JavaScript Widget Code:\n{user_val}')
        widget_id = f'js-widget-{pipeline_id}-{step_id}'.replace('-', '_')
        target_id = f'{widget_id}_target'
        js_widget = Div(P('JavaScript will execute here...', id=target_id, style='padding: 1.5rem; background-color: var(--pico-card-background-color); border-radius: var(--pico-border-radius); min-height: 100px;'), Button('Re-run JavaScript ▸', type='button', _onclick=f"runJsWidget('{widget_id}', `{user_val.replace('`', '\\`')}`, '{target_id}')", style='margin-top: 1rem; background-color: #9370DB; border-color: #9370DB;'), id=widget_id)
        content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Interactive JavaScript example', widget=js_widget, steps=steps)
        response_content = Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        response = HTMLResponse(to_xml(response_content))
        response.headers['HX-Trigger'] = json.dumps({'runJavaScript': {'widgetId': widget_id, 'code': user_val, 'targetId': target_id}})
        await self.message_queue.add(wand, f'{step.show} complete. JavaScript executed.', verbatim=True)
        return response

    def create_marked_widget(self, markdown_content, widget_id):
        """
        Create a widget for rendering markdown content using marked.js

        Args:
            markdown_content: The markdown text to render
            widget_id: Unique ID for the widget

        Returns:
            Div element containing the widget
        """
        widget = Div(Div(markdown_content, id=f'{widget_id}_source', cls='hidden'), Div(id=f'{widget_id}_rendered', cls='bg-light border markdown-body p-3 rounded-default'), Script(f"\n                document.addEventListener('htmx:afterOnLoad', function() {{\n                    // Function to render markdown\n                    function renderMarkdown() {{\n                        const source = document.getElementById('{widget_id}_source');\n                        const target = document.getElementById('{widget_id}_rendered');\n                        if (source && target) {{\n                            // Use marked.js to convert markdown to HTML\n                            const html = marked.parse(source.textContent);\n                            target.innerHTML = html;\n                            // Apply syntax highlighting to code blocks if Prism is available\n                            if (typeof Prism !== 'undefined') {{\n                                Prism.highlightAllUnder(target);\n                            }}\n                        }}\n                    }}\n                    \n                    // Check if marked.js is loaded\n                    if (typeof marked !== 'undefined') {{\n                        renderMarkdown();\n                    }} else {{\n                        console.error('marked.js is not loaded');\n                    }}\n                }});\n                \n                // Also listen for custom event from HX-Trigger\n                document.addEventListener('initMarked', function(event) {{\n                    if (event.detail.widgetId === '{widget_id}') {{\n                        setTimeout(function() {{\n                            const source = document.getElementById('{widget_id}_source');\n                            const target = document.getElementById('{widget_id}_rendered');\n                            if (source && target && typeof marked !== 'undefined') {{\n                                const html = marked.parse(source.textContent);\n                                target.innerHTML = html;\n                                // Apply syntax highlighting to code blocks if Prism is available\n                                if (typeof Prism !== 'undefined') {{\n                                    Prism.highlightAllUnder(target);\n                                }}\n                            }}\n                        }}, 100);\n                    }}\n                }});\n            "), cls='marked-widget')
        return widget

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

    def create_mermaid_widget(self, diagram_syntax, widget_id):
        """Create a mermaid diagram widget container."""
        container = Div(Div(H5('Rendered Diagram:'), Div(Div(diagram_syntax, cls='mermaid', style='width: 100%; background-color: var(--pico-card-background-color); border-radius: var(--pico-border-radius); padding: 1rem;'), id=f'{widget_id}_output')), id=widget_id)
        init_script = Script(f"""\n            (function() {{\n                // Give the DOM time to fully render before initializing Mermaid\n                setTimeout(function() {{\n                    // Initialize mermaid\n                    if (typeof mermaid !== 'undefined') {{\n                        try {{\n                            mermaid.initialize({{ \n                                startOnLoad: false,  // Important - don't auto-init\n                                theme: 'dark',       // Use dark theme for better visibility\n                                securityLevel: 'loose',\n                                flowchart: {{\n                                    htmlLabels: true\n                                }}\n                            }});\n                            \n                            // Find all mermaid divs in this widget and render them\n                            const container = document.getElementById('{widget_id}');\n                            if (!container) return;\n                            \n                            const mermaidDiv = container.querySelector('.mermaid');\n                            if (mermaidDiv) {{\n                                // Force a repaint before initializing\n                                void container.offsetWidth;\n                                \n                                // Render the diagram\n                                if (typeof mermaid.run === 'function') {{\n                                    // Newer Mermaid API\n                                    mermaid.run({{ nodes: [mermaidDiv] }});\n                                }} else {{\n                                    // Older Mermaid API\n                                    mermaid.init(undefined, mermaidDiv);\n                                }}\n                                console.log('Mermaid rendering successful');\n                            }}\n                        }} catch(e) {{\n                            console.error("Mermaid rendering error:", e);\n                        }}\n                    }} else {{\n                        console.error("Mermaid library not found. Make sure it's included in the page headers.");\n                    }}\n                }}, 300); // 300ms delay to ensure DOM is ready\n            }})();\n            """, type='text/javascript')
        return Div(container, init_script)

    def create_prism_widget(self, code, widget_id, language='javascript'):
        """Create a Prism.js syntax highlighting widget with copy functionality.

        Args:
            code (str): The code to highlight
            widget_id (str): Unique ID for the widget
            language (str): The programming language for syntax highlighting (default: javascript)
        """
        textarea_id = f'{widget_id}_raw_code'
        container = Div(Div(H5('Syntax Highlighted Code:'), Textarea(code, id=textarea_id, style='display: none;'), Pre(Code(code, cls=f'language-{language}'), cls='line-numbers'), cls='mt-4'), id=widget_id)
        init_script = Script(f"\n            (function() {{\n                console.log('Prism widget loaded, ID: {widget_id}');\n                // Check if Prism is loaded\n                if (typeof Prism === 'undefined') {{\n                    console.error('Prism library not found');\n                    return;\n                }}\n                \n                // Attempt to manually trigger highlighting\n                setTimeout(function() {{\n                    try {{\n                        console.log('Manually triggering Prism highlighting for {widget_id}');\n                        Prism.highlightAllUnder(document.getElementById('{widget_id}'));\n                    }} catch(e) {{\n                        console.error('Error during manual Prism highlighting:', e);\n                    }}\n                }}, 300);\n            }})();\n            ", type='text/javascript')
        return Div(container, init_script)

    async def step_07(self, request):
        """
        Handles GET request for Step 7: Matplotlib Histogram Widget.

        This step allows users to input counter data and visualizes it as a histogram.
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_07'
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

    async def step_07_submit(self, request):
        """
        Process the submission for Step 7 (Matplotlib Histogram).

        Takes counter data as input and creates a histogram visualization.
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_07'
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
            import json
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

    async def step_08(self, request):
        """
        Handles GET request for Step 8: URL Opener Widget.

        This widget allows users to input a URL and open it in their default browser.
        It demonstrates a practical use case for workflow steps.
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_08'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        url_value = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and url_value:
            return Div(Card(H3(f'🔒 {step.show}'), P(f'URL configured: ', B(url_value)), Button('Open URL Again ▸', type='button', _onclick=f"window.open('{url_value}', '_blank')", cls='secondary')), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
        elif url_value and state.get('_revert_target') != step_id:
            content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: {url_value}', widget=Div(P(f'URL configured: ', B(url_value)), Button('Open URL Again ▸', type='button', _onclick=f"window.open('{url_value}', '_blank')", cls='secondary')), steps=steps)
            return Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
        else:
            display_value = url_value if step.refill and url_value else 'https://example.com'
            await self.message_queue.add(wand, 'Enter the URL you want to open:', verbatim=True)
            return Div(Card(H3(f'{wand.fmt(step_id)}: Configure {step.show}'), P('Enter a URL to open in your default browser.'), Form(Div(Input(type='url', name='url', placeholder='https://example.com', required=True, value=display_value, cls='contrast'), Div(Button('Open URL ▸', type='submit', cls='primary'), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_08_submit(self, request):
        """
        Process the submission for Step 8 (URL Opener).

        Takes a URL input, validates it, opens it in the default browser,
        and provides a button to reopen it later.
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_08'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        form = await request.form()
        url = form.get('url', '').strip()
        if not url:
            return P('Error: URL is required', cls='text-invalid')
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        await wand.set_step_data(pipeline_id, step_id, url, steps)
        await self.message_queue.add(wand, f'URL set to: {url}', verbatim=True)
        import webbrowser
        webbrowser.open(url)
        url_widget = Div(P(f'URL configured: ', B(url)), Button('Open URL Again ▸', type='button', _onclick=f"window.open('{url}', '_blank')", cls='secondary'))
        content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: {url}', widget=url_widget, steps=steps)
        response_content = Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        await self.message_queue.add(wand, f'Opening URL: {url}', verbatim=True)
        return HTMLResponse(to_xml(response_content))

    def create_matplotlib_histogram(self, data_str):
        """
        Create a matplotlib histogram visualization from JSON counter data.

        Args:
            data_str: A JSON string representing counter data

        Returns:
            A Div element containing the histogram image
        """
        try:
            import json
            from collections import Counter
            data = json.loads(data_str)
            if not isinstance(data, dict):
                return Div(NotStr("<div style='color: red;'>Error: Data must be a JSON object with keys and values</div>"), _raw=True)
            counter = Counter(data)
            if not counter:
                return Div(NotStr("<div style='color: red;'>Error: No data to plot</div>"), _raw=True)
            import base64
            from io import BytesIO

            import matplotlib.pyplot as plt
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

    async def step_09(self, request):
        """
        Handles GET request for Step 9: Rich Table Widget.

        This widget demonstrates a beautifully styled table with:
        - Connected border lines
        - Alternating row colors
        - Bold headers with thicker borders
        - Proper cell padding and alignment
        - Color-coded columns
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_09'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        table_data = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and table_data:
            try:
                data = json.loads(table_data)
                table_widget = self.create_rich_table_widget(data)
                return Div(Card(H3(f'🔒 {step.show}'), table_widget), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
            except Exception as e:
                logger.error(f'Error creating table widget in finalized view: {str(e)}')
                return Div(Card(f'🔒 {step.show}: <content locked>'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        elif table_data and state.get('_revert_target') != step_id:
            try:
                data = json.loads(table_data)
                table_widget = self.create_rich_table_widget(data)
                content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show} Configured', widget=table_widget, steps=steps)
                return Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
            except Exception as e:
                logger.error(f'Error creating table widget: {str(e)}')
                state['_revert_target'] = step_id
                wand.write_state(pipeline_id, state)
        sample_data = [{'name': 'Parameter 1', 'value1': 1000, 'value2': 500, 'value3': 50}, {'name': 'Parameter 2', 'value1': 2000, 'value2': 1000, 'value3': 100}, {'name': 'Parameter 3', 'value1': 3000, 'value2': 1500, 'value3': 150}]
        display_value = table_data if step.refill and table_data else json.dumps(sample_data, indent=2)
        await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
        return Div(Card(H3(f'{wand.fmt(step_id)}: Configure {step.show}'), P('Enter table data as JSON array of objects. Example is pre-populated.'), P('Format: [{"name": "value", "value1": number, ...}, {...}]', cls='text-note'), Form(Div(Textarea(display_value, name=step.done, placeholder='Enter JSON array of objects for the table', required=True, rows=10, style='width: 100%; font-family: monospace;'), Div(Button('Create Table ▸', type='submit', cls='primary'), style='margin-top: 1vh; text-align: right;'), cls='w-full'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_09_submit(self, request):
        """Process the submission for Rich Table Widget."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_09'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form = await request.form()
        table_data = form.get(step.done, '').strip()
        is_valid, error_msg, error_component = wand.validate_step_input(table_data, step.show)
        if not is_valid:
            return error_component
        try:
            data = json.loads(table_data)
            if not isinstance(data, list) or not data:
                return P('Invalid JSON: Must be a non-empty array of objects', cls='text-invalid')
            if not all((isinstance(item, dict) for item in data)):
                return P('Invalid JSON: All items must be objects (dictionaries)', cls='text-invalid')
        except json.JSONDecodeError:
            return P('Invalid JSON format. Please check your syntax.', cls='text-invalid')
        await wand.set_step_data(pipeline_id, step_id, table_data, steps)
        try:
            table_widget = self.create_rich_table_widget(data)
            content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Table created with {len(data)} rows', widget=table_widget, steps=steps)
            response_content = Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
            await self.message_queue.add(wand, f'{step.show} complete. Table created with {len(data)} rows.', verbatim=True)
            return HTMLResponse(to_xml(response_content))
        except Exception as e:
            logger.error(f'Error creating table widget: {e}')
            return P(f'Error creating table: {str(e)}', cls='text-invalid')

    def create_rich_table_widget(self, data):
        """Create a rich table widget with beautiful styling."""
        if not data:
            return P('No data provided for table', cls='text-invalid')
        headers = list(data[0].keys())
        table_html = f'\n        <table class="param-table">\n            <caption>Rich Table Example</caption>\n            <tr class="header">\n        '
        for i, header in enumerate(headers):
            header_class = 'param-name' if header == 'name' else f'{header}-val'
            td_class = 'header-cell'
            table_html += f'<td class="{td_class}"><span class="{header_class}">{header}</span></td>'
        table_html += '</tr>'
        for row in data:
            table_html += '<tr>'
            for i, header in enumerate(headers):
                cell_class = 'param-name' if header == 'name' else f'{header}-val'
                value = row.get(header, '')
                if isinstance(value, (int, float)):
                    value = f'{value:,}'
                table_html += f'<td><span class="{cell_class}">{value}</span></td>'
            table_html += '</tr>'
        table_html += '</table>'
        return Div(NotStr(table_html), cls='overflow-auto')

    async def step_10(self, request):
        """Handles GET request for Selenium URL step."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_10'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        url_value = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and url_value:
            return Div(Card(H3(f'🔒 {step.show}'), P(f'URL configured: ', B(url_value)), Form(Input(type='hidden', name='url', value=url_value), Button('Open URL Again 🪄', type='submit', cls='secondary'), hx_post=f'/{app_name}/reopen_url', hx_target=f'#{step_id}-status'), Div(id=f'{step_id}-status')), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        elif url_value and state.get('_revert_target') != step_id:
            content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: {url_value}', widget=Div(P(f'URL configured: ', B(url_value)), Form(Input(type='hidden', name='url', value=url_value), Button('Open URL Again 🪄', type='submit', cls='secondary'), hx_post=f'/{app_name}/reopen_url', hx_target=f'#{step_id}-status'), Div(id=f'{step_id}-status')), steps=steps)
            return Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        else:
            await self.message_queue.add(wand, 'Enter the URL you want to open with Selenium:', verbatim=True)
            display_value = url_value if step.refill and url_value else 'https://example.com/'
            return Div(Card(H3(f'{step.show}'), Form(Input(type='url', name='url', placeholder='https://example.com/', required=True, value=display_value, cls='contrast'), Button('Open URL 🪄', type='submit', cls='primary'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}')), Div(id=next_step_id), id=step_id)

    async def step_10_submit(self, request):
        """Process the submission for Step 10."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_10'
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
            await self.message_queue.add(wand, error_msg, verbatim=True)
            return P(error_msg, cls='text-invalid')
        wand.append_to_history(f'[WIDGET CONTENT] {step.show}:\n{url}')
        wand.append_to_history(f'[WIDGET STATE] {step.show}: Step completed')
        await self.message_queue.add(wand, f'{step.show} complete.', verbatim=True)
        return Div(wand.display_revert_header(step_id=step_id, app_name=app_name, message=f'{step.show}: Complete', steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)

    async def step_11(self, request):
        """Handles GET request for the file upload widget.

        A reusable widget for handling multiple file uploads with:
        - Multiple file selection
        - File size reporting
        - Automatic file saving
        - Upload summary display
        """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_11'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        file_summary = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and file_summary:
            wand.append_to_history(f'[WIDGET CONTENT] {step.show} (Finalized):\n{file_summary}')
            return Div(Card(H3(f'🔒 {step.show}: Completed')), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        elif file_summary and state.get('_revert_target') != step_id:
            wand.append_to_history(f'[WIDGET CONTENT] {step.show} (Completed):\n{file_summary}')
            return Div(Card(H3(f'{step.show}'), P('Uploaded files:'), Pre(file_summary, style='white-space: pre-wrap; font-size: 0.9em;'), wand.display_revert_header(step_id=step_id, app_name=app_name, message=f'{step.show}: Complete', steps=steps)), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        else:
            wand.append_to_history(f'[WIDGET STATE] {step.show}: Showing upload form')
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
            return Div(Card(H3(f'{step.show}'), P('Select one or more files to upload. Files will be saved automatically.'), Form(Input(type='file', name='uploaded_files', multiple='true', required='true', cls='contrast'), Button('Upload Files ▸', type='submit', cls='primary'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}', enctype='multipart/form-data')), Div(id=next_step_id), id=step_id)

    async def step_11_submit(self, request):
        """Process the submission for the file upload widget."""
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_11'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form_data = await request.form()
        uploaded_files = form_data.getlist('uploaded_files')
        if not uploaded_files:
            await self.message_queue.add(wand, 'No files selected. Please try again.', verbatim=True)
            return Div(Card(H3(f'{step.show}'), P('No files were selected. Please try again.'), Form(Input(type='file', name='uploaded_files', multiple='true', required='true', cls='contrast'), Button('Upload Files ▸', type='submit', cls='primary'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}', enctype='multipart/form-data')), id=step_id)
        save_directory = Path('downloads') / self.app_name / pipeline_id
        try:
            save_directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            error_msg = f'Error creating save directory: {str(e)}'
            logger.error(error_msg)
            await self.message_queue.add(wand, error_msg, verbatim=True)
            return P('Error creating save directory. Please try again.', cls='text-invalid')
        file_info = []
        total_size = 0
        saved_files = []
        for file in uploaded_files:
            try:
                contents = await file.read()
                file_size = len(contents)
                total_size += file_size
                file_save_path = save_directory / file.filename
                with open(file_save_path, 'wb') as f:
                    f.write(contents)
                saved_files.append((file.filename, str(file_save_path)))
                file_info.append(f'📄 {file.filename} ({file_size:,} bytes) -> {file_save_path}')
            except Exception as e:
                error_msg = f'Error saving file {file.filename}: {str(e)}'
                logger.error(error_msg)
                await self.message_queue.add(wand, error_msg, verbatim=True)
                return P(f'Error saving file {file.filename}. Please try again.', cls='text-invalid')
        file_summary = '\n'.join(file_info)
        file_summary += f'\n\nTotal: {len(uploaded_files)} files, {total_size:,} bytes'
        file_summary += f'\nSaved to: {save_directory}'
        await wand.set_step_data(pipeline_id, step_id, file_summary, steps)
        wand.append_to_history(f'[WIDGET CONTENT] {step.show}:\n{file_summary}')
        wand.append_to_history(f'[WIDGET STATE] {step.show}: Files saved')
        await self.message_queue.add(wand, f'Successfully saved {len(uploaded_files)} files to {save_directory}', verbatim=True)
        return Div(Card(H3(f'{step.show}'), P('Files saved successfully:'), Pre(file_summary, style='white-space: pre-wrap; font-size: 0.9em;'), wand.display_revert_header(step_id=step_id, app_name=app_name, message=f'{step.show}: Complete', steps=steps)), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)

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
