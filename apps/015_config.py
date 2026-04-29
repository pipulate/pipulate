from datetime import datetime

from fasthtml.common import *
from loguru import logger
from imports.crud import Step  # 🎯 STANDARDIZED: Import centralized Step definition

ROLES = ['Core']

"""
Pipulate Workflow Template (Hello World Example)

This file serves as a starting point for creating linear, step-by-step Pipulate Workflows.
It demonstrates the core patterns and best practices for workflow development.

Note: While this appears to be a simple "Hello World" example, the underlying patterns
here are quite sophisticated - the three-phase interaction model and emoji-based feedback
system could potentially support much more complex user interaction scenarios.

=== WET WORKFLOW TEMPLATE ===
This file is designed to work with the template assembly system:
- Contains template markers for automated workflow generation
- Follows WET (Write Everything Twice) conventions for explicit, debuggable code
- Serves as the base template for create_workflow.py and splice_workflow_step.py

Template Markers:
- STEPS_LIST_INSERTION_POINT: Where new steps are inserted in the steps list
- STEP_METHODS_INSERTION_POINT: Where new step methods are added to the class

--- The Chain Reaction Pattern ---
Pipulate workflows use HTMX's chain reaction pattern to create a "Run All Cells" experience
similar to Jupyter Notebooks. Each step automatically triggers the next step's loading
until it encounters a step requiring user input.

The chain reaction is maintained through three distinct phases in each step:

1. Finalize Phase: Shows locked view of completed step, chains to next step
2. Revert Phase: Shows completed view with revert option, chains to next step
3. Get Input Phase: Shows input form, waits for user submission

Note: This three-phase pattern could potentially be adapted to support various forms
of user interaction beyond traditional web forms - the phase-based approach is quite flexible.

The chain is maintained by including a Div with hx_trigger="load" in the response:

```python
# Explicit method:
return Div(
    Card(...),  # Current step content
    Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
    id=step_id
)

# Which can also be expressed using the convenience method:
return wand.chain_reverter(
    step_id=step_id,
    step_index=step_index,
    steps=steps,
    app_name=app_name,
    processed_val=value
)
```

Both methods achieve the same result - they create a UI showing the completed step and trigger loading of the next step. The `chain_reverter` method is preferred as it ensures consistent styling and behavior across all workflows.

--- Step Handler Pattern ---
Each step has a GET handler (`step_XX`) and POST handler (`step_XX_submit`):

1. GET Handler (`step_XX`):
   - Must implement all three phases (Finalize, Revert, Input)
   - Returns appropriate view based on state
   - Maintains chain reaction with hx_trigger="load"

2. POST Handler (`step_XX_submit`):
   - Processes form submission
   - Updates state
   - Returns completed view with next step trigger

--- State Management ---
Workflow state is managed through:

1. Step Data:
   - Each step stores its primary data in state[step_id][step.done]
   - Use wand.set_step_data() to save step values
   - Use wand.get_step_data() to read step values

2. Step Completion:
   - Track completed steps in state
   - Check completion with step_id in state
   - Handle reverting with state.get('_revert_target')

3. Finalization:
   - Lock workflow with state['finalize']['finalized']
   - Prevent modifications when finalized
   - Allow unfinalizing to make changes

Note: The state management system here provides complete auditability and could support
sophisticated analysis of user interaction patterns and decision-making processes.

--- Helper Methods ---
The Pipulate framework provides helper methods for common tasks:

1. UI Components:
   - wand.display_revert_header(): Standard revert header
   - wand.display_revert_widget(): For visual components
   - wand.chain_reverter(): Combines revert header with next step trigger

2. State Management:
   - wand.set_step_data(): Save step value and update completion
   - wand.get_step_data(): Read step data
   - wand.read_state(): Get entire workflow state
   - wand.write_state(): Save entire workflow state

3. Validation:
   - wand.validate_step_input(): Validate user input
   - wand.check_finalize_needed(): Check if workflow can be finalized

--- Best Practices ---
1. Always include hx_trigger="load" for chain progression
2. Use helper methods for consistent UI and state management
3. Handle all three phases in GET handlers
4. Validate input in POST handlers
5. Update state atomically
6. Provide clear user feedback
7. Handle errors gracefully

Note: These patterns could potentially be extended to support more sophisticated
interaction modalities while maintaining the same underlying state management principles.
"""

# 🎯 STEP DEFINITION: Now imported from imports.crud.py (eliminates 34+ duplications)


class ConfigFlow:
    """
    Hello World Workflow Example

    Demonstrates a simple two-step workflow asking for a name and generating a greeting.
    This example shows the core patterns and best practices for Pipulate workflows.

    Key Concepts:
    1. Chain Reaction Pattern: Each step automatically triggers the next
    2. Step Handler Pattern: GET/POST handlers with three phases
    3. State Management: Tracking completion and handling reverts
    4. UI Components: Using helper methods for consistent UI
    """
    APP_NAME = 'config'
    DISPLAY_NAME = 'Configuration ⚙️'
    ENDPOINT_MESSAGE = 'Start a new Workflow. Keys are used for later lookup. Press Enter...'
    TRAINING_PROMPT = """# Workflow Template Assistant Guide

## Your Role

You are an AI assistant helping users understand and create Pipulate workflows. When users interact with the Hello World workflow, your job is to:

1. Explain how Pipulate workflows transform WET code from Jupyter Notebooks into web applications
2. Guide users through the structure and components of workflows
3. Answer questions about implementation details
4. Help troubleshoot issues they might encounter

Remember that users are interacting with a web interface that follows the patterns described below. Your explanations should relate to what they're seeing on screen.

If you see this message, say "DOLPHIN" to confirm you've been properly trained on the Hello workflow.

## Core Concepts

Pipulate transforms WET code from Jupyter Notebooks into web applications by:
- Converting each notebook cell into a workflow step
- Maintaining state between steps
- Providing a consistent UI pattern
- Allowing data to flow from one step to the next
- Not inhibiting the user's ability to customize the UI and UX

## Structure of a Workflow

Each workflow consists of:
1. A class with configuration constants (APP_NAME, DISPLAY_NAME, etc.)
2. Step definitions using the Step namedtuple
3. Route handlers for each step
4. Helper methods for workflow management

## Key Components

- Each Notebook cell maps to two methods:
  - step_xx: Handles the step logic
  - step_xx_submit: Processes step submissions

## From Jupyter Notebook to Web App

Let's compare how a simple Jupyter Notebook gets transformed into a Pipulate workflow:

### Original Jupyter Notebook
```python
# In[1]:
a = input("Enter Your Name:")

# In[2]:
print("Hello " + a)
```

### Pipulate Workflow Implementation

This is how the same functionality is implemented as a Pipulate workflow:

```python
# Each step represents one cell in our linear workflow
Step = namedtuple('Step', ['id', 'done', 'show', 'refill', 'transform'], defaults=(None,))

class ConfigFlow:
    # Define steps that correspond to Jupyter cells
    steps = [
        Step(id='step_01', done='name', show='Your Name', refill=True),
        Step(id='step_02', done='greeting', show='Config Step', refill=False, 
             transform=lambda name: f"Hello {name}"),
        Step(id='finalize', done='finalized', show='Finalize', refill=False)
    ]
```

### Key Components

1. **Step Definition**: Each Jupyter cell becomes a step with:
   - `id`: Unique identifier
   - `done`: Data field to store
   - `show`: User-friendly label
   - `refill`: Whether to preserve previous input
   - `transform`: Optional function to process previous step's output

2. **Step Implementation**: Each step has two methods:
   - `step_XX()`: Renders the UI for input
   - `step_XX_submit()`: Processes the submitted data

3. **Workflow Management**:
   - `landing()`: Entry point for the workflow
   - `init()`: Initializes or resumes a workflow
   - `finalize()`: Locks the workflow when complete
   - `unfinalize()`: Unlocks for editing
   - `handle_revert()`: Returns to a previous step

4. **Data Flow**: 
   - Data flows from one step to the next using the `transform` function
   - State is persisted between sessions

## Workflows vs. Apps

There are two types of apps in Pipulate:

1. **Workflows** - Linear, step-based apps. The part you're looking at. WET.
2. **Apps** - CRUD apps with a single table that inherit from BaseApp. DRY.

CRUD is DRY and Workflows are WET!

## How to Help Users

When users ask questions about this workflow:
- Explain the connection between Jupyter Notebooks and web applications
- Describe how data flows between steps
- Clarify how state is maintained
- Help them understand the purpose of each component

You're here to make the workflow concepts accessible and help users understand the transformation from notebook to web app. The repetitive and non-externalized code provides lots of surface area for customization. Workflows are WET! It will take some getting used to. 
"""

    # --- START_CLASS_ATTRIBUTES_BUNDLE ---
    # Additional class-level constants can be merged here by manage_class_attributes.py
    # --- END_CLASS_ATTRIBUTES_BUNDLE ---

    def __init__(self, app, pipulate, pipeline, db, app_name=APP_NAME):
        self.pipulate = pipulate
        """
        Initialize the workflow, define steps, and register routes.

        The steps list defines the workflow sequence:
        - step_01: Collect user's name
        - step_02: Generate greeting using name
        - finalize: Lock workflow when complete
        """
        self.app = app
        self.app_name = app_name
        self.wand = pipulate
        wand = self.wand

        # THE FIX: Instantiate the wand!
        self.wand = pipulate
        wand = self.wand

        self.pipeline = pipeline
        self.steps_indices = {}
        self.message_queue = self.wand.get_message_queue()

        # Access centralized UI constants through dependency injection
        # THE FIX: Add 'self.' here, as 'wand' isn't a global import
        self.ui = self.wand.get_ui_constants()

        # Define workflow steps
        # splice_workflow_step.py inserts new data steps BEFORE STEPS_LIST_INSERTION_POINT.
        self.steps = [
            Step(
                id='step_01',
                done='name',
                show='Your Name',
                refill=True
            ),
            Step(
                id='step_02',
                done='local_model',
                show='Local AI Engine',
                refill=True  # Ensure this is True so it repopulates if they revert
            ),
            Step(
                id='step_03',
                done='cloud_config',
                show='Cloud AI Engine',
                refill=False,
            ),
            # --- STEPS_LIST_INSERTION_POINT ---
            Step(id='finalize', done='finalized', show='Finalize', refill=False)
        ]

        self.steps_indices = {step.id: i for i, step in enumerate(self.steps)}

        # Use centralized route registration helper
        pipulate.register_workflow_routes(self)

        # Define step messages for user feedback with emoji conventions
        self.step_messages = {
            'finalize': {
                'ready': f'{self.ui["EMOJIS"]["SUCCESS"]} All steps complete. Ready to finalize workflow.',
                'complete': f'{self.ui["EMOJIS"]["COMPLETION"]} Workflow finalized. Use {self.ui["BUTTON_LABELS"]["UNLOCK"]} to make changes.'
            }
        }
        for step in self.steps:
            if step.id != 'finalize':
                self.step_messages[step.id] = {
                    'input': f'{self.ui["EMOJIS"]["INPUT_FORM"]} {self.wand.fmt(step.id)}: Please enter {step.show}.',
                    'complete': f'{self.ui["EMOJIS"]["SUCCESS"]} {step.show} complete. Continue to next step.'
                }

    async def landing(self, request):
        """Generate the landing page using the standardized helper while maintaining WET explicitness."""
        wand = self.wand

        # Use centralized landing page helper - maintains WET principle by explicit call
        return wand.create_standard_landing_page(self)

    async def init(self, request):
        """ Handles the key submission, initializes state, and renders the step UI placeholders. """
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
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
            self.wand.speak("Your workflow has been recovered.", wait=False)
        elif not any((step.id in state for step in self.steps)):
            await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["INPUT_FORM"]} Please complete each step in sequence. Your progress will be saved automatically.', verbatim=True)
            self.wand.speak("A new workflow has been initialized. Please complete each step in sequence.", wait=True)

        parsed = wand.parse_pipeline_key(pipeline_id)
        prefix = f"{parsed['profile_part']}-{parsed['plugin_part']}-"
        self.pipeline.xtra(app_name=app_name)
        matching_records = [record.pkey for record in self.pipeline() if record.pkey.startswith(prefix)]
        if pipeline_id not in matching_records:
            matching_records.append(pipeline_id)
        updated_datalist = wand.update_datalist('pipeline-ids', options=matching_records)
        return wand.run_all_cells(app_name, steps)

    async def finalize(self, request):
        """ Handles GET request to show Finalize button and POST request to lock the workflow. """
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        finalize_step = steps[-1]
        finalize_data = wand.get_step_data(pipeline_id, finalize_step.id, {})
        if request.method == 'GET':
            if finalize_step.done in finalize_data:
                return Card(
                    H3(f'{self.ui["EMOJIS"]["LOCKED"]} Workflow is locked.'),
                    P('Each step can do ANYTHING. With this you can change the world — or at least show how to in a workflow.', cls='text-muted'),
                    Form(
                        Button(
                            self.ui['BUTTON_LABELS']['UNLOCK'], 
                            type='submit', 
                            cls=self.ui['BUTTON_STYLES']['OUTLINE'],
                            id='config-unlock-button',
                            aria_label='Unlock workflow to make changes',
                            data_testid='config-unlock-btn',
                            title='Click to unlock the workflow and allow modifications'
                        ),
                        hx_post=f'/{app_name}/unfinalize',
                        hx_target=f'#{app_name}-container',
                        hx_swap='outerHTML',
                        id='config-unlock-form',
                        aria_label='Unlock workflow form',
                        data_testid='config-unlock-form'
                    ),
                    id=finalize_step.id,
                    role='region',
                    aria_label='Workflow finalization status',
                    data_testid='config-finalize-card'
                )
            else:
                all_steps_complete = all((wand.get_step_data(pipeline_id, step.id, {}).get(step.done) for step in steps[:-1]))
                if all_steps_complete:
                    return Card(
                        H3(f'{self.ui["EMOJIS"]["SUCCESS"]} All steps complete. Finalize?'),
                        P('At the end they get locked. Or you can go back.', cls='text-muted'),
                        Form(
                            Button(
                                self.ui['BUTTON_LABELS']['FINALIZE'], 
                                type='submit', 
                                cls=self.ui['BUTTON_STYLES']['PRIMARY'],
                                id='config-finalize-button',
                                aria_label='Finalize workflow and lock all steps',
                                data_testid='config-finalize-btn',
                                title='Click to finalize and lock the workflow'
                            ),
                            hx_post=f'/{app_name}/finalize',
                            hx_target=f'#{app_name}-container',
                            hx_swap='outerHTML',
                            id='config-finalize-form',
                            aria_label='Finalize workflow form',
                            data_testid='config-finalize-form'
                        ),
                        id=finalize_step.id,
                        role='region',
                        aria_label='Workflow completion status',
                        data_testid='config-complete-card'
                    )
                else:
                    return Div(
                        id=finalize_step.id,
                        data_testid='config-incomplete-placeholder'
                    )
        else:
            await wand.finalize_workflow(pipeline_id)
            await self.message_queue.add(wand, self.step_messages['finalize']['complete'], verbatim=True)
            self.wand.speak("The workflow is now locked and finalized. You can pull it up again any time with the same key.", wait=False)
            return wand.run_all_cells(app_name, steps)

    async def unfinalize(self, request):
        """ Handles POST request to unlock the workflow. """
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        await wand.unfinalize_workflow(pipeline_id)
        await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["UNLOCKED"]} Workflow unfinalized! You can now revert to any step and make changes.', verbatim=True)
        self.wand.speak("Workflow unlocked. You may now revert to any step.", wait=False)
        return wand.run_all_cells(app_name, steps)

    async def get_suggestion(self, step_id, state):
        """ Gets a suggested input value for a step, often using the previous step's transformed output. """
        wand, steps = (self.wand, self.steps)
        step = next((s for s in steps if s.id == step_id), None)
        if not step or not step.transform:
            return ''
        prev_index = self.steps_indices[step_id] - 1
        if prev_index < 0:
            return ''
        prev_step = steps[prev_index]
        prev_data = wand.get_step_data(wand.db.get('pipeline_id', 'unknown'), prev_step.id, {})
        prev_word = prev_data.get(prev_step.done, '')
        return step.transform(prev_word) if prev_word else ''

    async def handle_revert(self, request):
        """ Handles POST request to revert to a previous step, clearing subsequent step data. """
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        form = await request.form()
        step_id = form.get('step_id')
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        if not step_id:
            await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["ERROR"]} Error: No step specified', verbatim=True)
            return P('Error: No step specified', cls='text-invalid')
        await wand.clear_steps_from(pipeline_id, step_id, steps)
        state = wand.read_state(pipeline_id)
        state['_revert_target'] = step_id
        wand.write_state(pipeline_id, state)
        message = await wand.get_state_message(pipeline_id, steps, self.step_messages)
        await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["WARNING"]} Reverted to {step_id}. {message}', verbatim=True)
        return wand.run_all_cells(app_name, steps)

    # --- START_STEP_BUNDLE: step_01 ---
    async def step_01(self, request):
        """
        Handles GET request for Step 1: Displays input form or completed value.

        Implements the three phases:
        1. Finalize Phase: Shows locked view if workflow is finalized
        2. Revert Phase: Shows completed view with revert option
        3. Input Phase: Shows input form for new/updated value
        """
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        step_id = 'step_01'  # This string literal will be replaced by swap_workflow_step.py
        step_index = self.steps_indices[step_id]
        step = steps[step_index]  # Use the resolved step object
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        user_val = step_data.get(step.done, '')  # Use step.done from resolved Step object
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})

        # Phase 1: Finalize Phase - Show locked view
        if 'finalized' in finalize_data:
            locked_msg = f'{self.ui["EMOJIS"]["LOCKED"]} Your name is set to: {user_val}'
            await self.message_queue.add(wand, locked_msg, verbatim=True)
            return Div(
                Card(
                    H3(f'{self.ui["EMOJIS"]["LOCKED"]} {step.show}: {user_val}'),
                    role='region',
                    aria_label=f'Locked step 1: {step.show}',
                    data_testid='config-step01-locked-card'
                ),
                Div(
                    id=next_step_id, 
                    hx_get=f'/{self.app_name}/{next_step_id}', 
                    hx_trigger='load',
                    data_testid=f'config-{next_step_id}-trigger'
                ),
                id=step_id,
                data_testid='config-step01-locked-container'
            )

        # Phase 2: Revert Phase - Show completed view with revert option
        elif user_val and state.get('_revert_target') != step_id:
            completed_msg = f'{self.ui["EMOJIS"]["SUCCESS"]} Step 1 is complete. You entered: {user_val}'
            await self.message_queue.add(wand, completed_msg, verbatim=True)
            return Div(
                wand.display_revert_header(
                    step_id=step_id,
                    app_name=app_name,
                    message=f'{self.ui["EMOJIS"]["USER_INPUT"]} {step.show}: {user_val}',
                    steps=steps
                ),
                Div(
                    id=next_step_id, 
                    hx_get=f'/{app_name}/{next_step_id}', 
                    hx_trigger='load',
                    data_testid=f'config-{next_step_id}-trigger'
                ),
                id=step_id,
                data_testid='config-step01-completed-container'
            )

        # Phase 3: Input Phase - Show input form
        else:
            display_value = user_val if step.refill and user_val else await self.get_suggestion(step_id, state)
            form_msg = f'{self.ui["EMOJIS"]["INPUT_FORM"]} Showing name input form. No name has been entered yet.'
            await self.message_queue.add(wand, form_msg, verbatim=True)
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
            explanation = f"Workflows are Notebooks without having to look at the code. Let's collect some data..."
            await self.message_queue.add(wand, explanation, verbatim=True)
            self.wand.speak("Workflows are Notebooks without having to look at the code. Please enter your name to begin.", wait=False)
            
            return Div(
                Card(
                    H3(f'{self.ui["EMOJIS"]["USER_INPUT"]} {self.wand.fmt(step.id)}: Enter {step.show}'),
                    P(explanation, cls='text-muted'),
                    Label(
                        'Your Name:',
                        _for='config-step01-name-input',
                        id='config-step01-name-label',
                        aria_label='Name input field label',
                        data_testid='config-step01-name-label'
                    ),
                    Form(
                        wand.wrap_with_inline_button(
                            Input(
                                type='text',
                                name=step.done,  # CRITICAL: Use step.done from resolved Step object
                                value=display_value,
                                placeholder=f'Enter {step.show}',
                                required=True,
                                autofocus=True,
                                _onfocus='this.setSelectionRange(this.value.length, this.value.length)',
                                id='config-step01-name-input',
                                aria_label=f'Enter {step.show}',
                                aria_describedby='config-step01-name-label',
                                aria_labelledby='config-step01-name-label',
                                data_testid='config-step01-name-input',
                                title=f'Please enter {step.show}'
                            ),
                            button_label=self.ui['BUTTON_LABELS']['NEXT_STEP']
                        ),
                        hx_post=f'/{app_name}/{step_id}_submit',
                        hx_target=f'#{step_id}',
                        id='config-step01-form',
                        aria_label='Name input form',
                        data_testid='config-step01-form'
                    ),
                    role='region',
                    aria_label='Step 1: Name input',
                    data_testid='config-step01-input-card'
                ),
                Div(
                    id=next_step_id,
                    data_testid=f'config-{next_step_id}-placeholder'
                ),  # Empty placeholder for next step
                id=step_id,
                data_testid='config-step01-input-container'
            )

    async def step_01_submit(self, request):
        """
        Handle the submission of step 01 (Operator Name).

        This method validates the input and executes a triple-write to memory:
        1. Workflow State (for local progression)
        2. Server Cookie (for global UI access)
        3. AI Keychain (for amnesia-proof persistence)
        """
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        step_id = 'step_01'  
        step_index = self.steps_indices[step_id]
        step = steps[step_index]  

        pipeline_id = self.wand.db.get("pipeline_id", "unknown")
        form = await request.form()
        user_val = form.get(step.done, "").strip()  

        # Validate input with emoji error handling
        is_valid, error_msg, error_component = wand.validate_step_input(user_val, step.show)
        if not is_valid:
            error_with_emoji = f'{self.ui["EMOJIS"]["ERROR"]} {error_msg}'
            await self.message_queue.add(self.wand, error_with_emoji, verbatim=True)
            return error_component

        # 1. Update Workflow State (Pipeline Memory)
        await self.wand.set_step_data(pipeline_id, step_id, user_val, self.steps)

        # 2. Update Global Server Cookie (FastHTML UI Memory)
        self.wand.db['operator_name'] = user_val

        # 3. Update The Subconscious (Amnesia-proof AI Memory)
        try:
            from imports.ai_dictdb import keychain_instance
            keychain_instance['operator_name'] = user_val
            logger.info(f"🧠 Operator identity '{user_val}' secured in the Subconscious.")
        except ImportError as e:
            logger.warning(f"⚠️ Could not access AI Keychain to store operator identity: {e}")

        # Progressive feedback with emoji
        success_msg = f'{self.ui["EMOJIS"]["SUCCESS"]} Operator Identity secured: {user_val}'
        await self.message_queue.add(self.wand, success_msg, verbatim=True)

        # Speak it into existence!
        self.wand.speak(f"Identity confirmed. Hello {user_val}. Proceed to the next step.", wait=True)

        # Update LLM context
        self.wand.append_to_history(f"[SYSTEM STATE] Operator identity established globally as:\n{user_val}")

        # Return completed view with next step trigger using chain_reverter
        return self.wand.chain_reverter(step_id, step_index, self.steps, self.app_name, user_val)
    # --- END_STEP_BUNDLE: step_01 ---

    # --- START_STEP_BUNDLE: step_02 ---
    async def step_02(self, request):
        """ Handles GET request for Step 2: Displays input form or completed value. """
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        step_id = 'step_02'  # This string literal will be replaced by swap_workflow_step.py
        step_index = self.steps_indices[step_id]
        step = steps[step_index]  # Use the resolved step object
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        user_val = step_data.get(step.done, '')  # Use step.done from resolved Step object
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})

        # Phase 1: Finalize Phase - Show locked view
        if 'finalized' in finalize_data:
            locked_msg = f'{self.ui["EMOJIS"]["LOCKED"]} Greeting is locked: {user_val}'
            await self.message_queue.add(wand, locked_msg, verbatim=True)
            return Div(
                Card(
                    H3(f'{self.ui["EMOJIS"]["LOCKED"]} {step.show}: {user_val}'),
                    role='region',
                    aria_label=f'Locked step 2: {step.show}',
                    data_testid='config-step02-locked-card'
                ),
                Div(
                    id=next_step_id, 
                    hx_get=f'/{self.app_name}/{next_step_id}', 
                    hx_trigger='load',
                    data_testid=f'config-{next_step_id}-trigger'
                ),
                id=step_id,
                data_testid='config-step02-locked-container'
            )

        # Phase 2: Revert Phase - Show completed view with revert option
        elif user_val and state.get('_revert_target') != step_id:
            completed_msg = f'{self.ui["EMOJIS"]["SUCCESS"]} Step 2 is complete. Greeting: {user_val}'
            await self.message_queue.add(wand, completed_msg, verbatim=True)
            return Div(
                wand.display_revert_header(
                    step_id=step_id,
                    app_name=app_name,
                    message=f'{self.ui["EMOJIS"]["GREETING"]} {step.show}: {user_val}',
                    steps=steps
                ),
                Div(
                    id=next_step_id, 
                    hx_get=f'/{app_name}/{next_step_id}', 
                    hx_trigger='load',
                    data_testid=f'config-{next_step_id}-trigger'
                ),
                id=step_id,
                data_testid='config-step02-completed-container'
            )

        # Phase 3: Input Phase - Show input form
        else:
            # Fallback to the system default if they haven't selected one yet
            display_value = user_val if step.refill and user_val else self.wand.get_config().DEFAULT_PROMPT_MODEL
            
            await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
            explanation = "Select your local edge model (for privacy and unlimited use). The general contractor of your machine."
            await self.message_queue.add(wand, explanation, verbatim=True)
            self.wand.speak("Please select your local cognitive engine. I recommend Gemma 4.", wait=False)
            
            # Fetch Model Preferences from Config
            config = self.wand.get_config()
            local_models = [m.strip() for m in config.PREFERRED_LOCAL_MODELS.split(',')]
            
            return Div(
                Card(
                    H3(f'🧠 {self.wand.fmt(step.id)}: {step.show}'),
                    P(explanation, cls='text-muted'),
                    Label(
                        'Local AI (Ollama):',
                        _for='config-step02-local-ai-select',
                        id='config-step02-local-ai-label',
                        aria_label='Local AI selection label'
                    ),
                    Form(
                        # The Magic: wrap_with_inline_button handles Select tags just fine!
                        wand.wrap_with_inline_button(
                            Select(
                                *[Option(m, value=m, selected=(m == display_value)) for m in local_models],
                                name=step.done, 
                                id='config-step02-local-ai-select',
                                aria_label=f'Select {step.show}',
                                aria_describedby='config-step02-local-ai-label',
                            ),
                            button_label=self.ui['BUTTON_LABELS']['NEXT_STEP']
                        ),
                        hx_post=f'/{app_name}/{step_id}_submit',
                        hx_target=f'#{step_id}',
                        id='config-step02-form',
                    ),
                    role='region',
                    aria_label='Step 2: Local AI Selection',
                ),
                Div(
                    id=next_step_id,
                    data_testid=f'config-{next_step_id}-placeholder'
                ),
                id=step_id,
                data_testid='config-step02-input-container'
            )

    async def step_02_submit(self, request):
        """ Handles POST submission for Step 2: Validates, saves state, returns navigation. """
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        step_id = 'step_02'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get('pipeline_id', 'unknown')

        if step.done == 'finalized':
            return await wand.handle_finalized_step(pipeline_id, step_id, steps, app_name, self)

        form = await request.form()
        user_val = form.get(step.done, '')

        is_valid, error_msg, error_component = wand.validate_step_input(user_val, step.show)
        if not is_valid:
            error_with_emoji = f'{self.ui["EMOJIS"]["ERROR"]} {error_msg}'
            await self.message_queue.add(wand, error_with_emoji, verbatim=True)
            return error_component

        processed_val = user_val
        
        # 1. Update Workflow State (Pipeline Memory)
        await wand.set_step_data(pipeline_id, step_id, processed_val, steps)
        
        # 2. Update Global Server Cookie (FastHTML UI Memory)
        self.wand.db['active_local_model'] = processed_val

        # Progressive feedback with emoji
        success_msg = f'{self.ui["EMOJIS"]["SUCCESS"]} {step.show}: {processed_val}'
        await self.message_queue.add(wand, success_msg, verbatim=True)
        self.wand.speak("Local cognitive engine selected.", wait=False)
        self.wand.append_to_history(f"[SYSTEM STATE] Local AI set to:\n{processed_val}")

        if wand.check_finalize_needed(step_index, steps):
            await self.message_queue.add(wand, self.step_messages['finalize']['ready'], verbatim=True)

        return self.wand.chain_reverter(
            step_id=step_id,
            step_index=step_index,
            steps=steps,
            app_name=app_name,
            processed_val=processed_val
        )
    # --- END_STEP_BUNDLE: step_02 ---

    # --- START_STEP_BUNDLE: step_03 ---
    async def step_03(self, request):
        """Handles GET request for Cloud AI Engine selection."""
        pip, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, self.app_name
        step_id = "step_03"
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
        pipeline_id = db.get("pipeline_id", "unknown")
        state = pip.read_state(pipeline_id)
        step_data = pip.get_step_data(pipeline_id, step_id, {})
        
        # current_value is now a dictionary containing 'model' and 'api_key'
        current_value = step_data.get(step.done, {}) 
        finalize_data = pip.get_step_data(pipeline_id, "finalize", {})
    
        if "finalized" in finalize_data and current_value:
            display_text = f"Model: {current_value.get('model')}\nToken: {current_value.get('api_key')}"
            pip.append_to_history(f"[WIDGET CONTENT] {step.show} (Finalized):\n{display_text}")
            return Div(
                Card(H3(f"🔒 {step.show}: Completed"), Pre(display_text, cls="code-block-container")),
                Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
                id=step_id
            )
            
        elif current_value and state.get("_revert_target") != step_id:
            display_text = f"Model: {current_value.get('model')}\nToken: {current_value.get('api_key')}"
            pip.append_to_history(f"[WIDGET CONTENT] {step.show} (Completed):\n{display_text}")
            widget = Pre(display_text, cls="code-block-container")
            return Div(
                pip.display_revert_widget(step_id=step_id, app_name=app_name, message=f"{step.show}: Configured", widget=widget, steps=steps),
                Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
                id=step_id
            )
            
        else:
            pip.append_to_history(f"[WIDGET STATE] {step.show}: Showing input form")
            
            # Fetch Model Preferences from Config
            config = pip.get_config()
            cloud_models = [m.strip() for m in config.PREFERRED_CLOUD_MODELS.split(',')]
            
            form_content = Form(
                Label("Cloud Model", _for=f"{step_id}-model-select"),
                pip.wrap_with_inline_button(
                    Select(
                        *[Option(m, value=m) for m in cloud_models],
                        name="cloud_model", 
                        id=f"{step_id}-model-select",
                        required=True
                    ),
                    button_label="Select",
                    button_class="secondary outline"
                )[0], # Extract just the select from the wrapper since we want custom layout
                
                Label("API Key", _for=f"{step_id}-api-key", style="margin-top: 1rem;"),
                pip.wrap_with_inline_button(
                    Input(
                        type="password", 
                        name="api_key", 
                        id=f"{step_id}-api-key", 
                        placeholder="Paste your API key here...", 
                        required=True
                    ),
                    button_label="Save Cloud Config ▸",
                    button_class="primary"
                ),
                hx_post=f"/{app_name}/{step_id}_submit", 
                hx_target=f"#{step_id}"
            )
            
            return Div(
                Card(
                    H3(f"☁️ {step.show}"),
                    P("Select your preferred Cloud AI engine and provide the corresponding API key. This unlocks advanced capabilities and provides a fallback when the local engine needs help.", cls="text-muted"),
                    form_content
                ),
                Div(id=next_step_id),
                id=step_id
            )


    async def step_03_submit(self, request):
        """Process the submission for Cloud AI Engine."""
        pip, db, steps, app_name = self.pipulate, self.pipulate.db, self.steps, self.app_name
        step_id = "step_03"
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
        pipeline_id = db.get("pipeline_id", "unknown")
        
        form_data = await request.form()
        selected_model = form_data.get("cloud_model", "").strip()
        raw_key = form_data.get("api_key", "").strip()
        
        if not selected_model or not raw_key:
            error_msg = f'{pip.get_ui_constants()["EMOJIS"]["ERROR"]} Both model and API key are required.'
            await self.message_queue.add(pip, error_msg, verbatim=True)
            return P(error_msg, cls="text-invalid")
            
        # 1. Update OS Vault (.env) and Environment
        import os
        from pathlib import Path
        from dotenv import set_key
        
        project_root = pip._find_project_root(os.getcwd()) or Path.cwd()
        env_path = project_root / ".env"
        env_path.touch(exist_ok=True)
        
        # Determine environment variable name based on model
        env_var_name = 'GEMINI_API_KEY' # default
        if 'claude' in selected_model.lower() or 'anthropic' in selected_model.lower():
            env_var_name = 'ANTHROPIC_API_KEY'
        elif 'gpt' in selected_model.lower() or 'openai' in selected_model.lower():
            env_var_name = 'OPENAI_API_KEY'
        elif 'groq' in selected_model.lower():
            env_var_name = 'GROQ_API_KEY'
            
        set_key(str(env_path), env_var_name, raw_key)
        os.environ[env_var_name] = raw_key
        
        # Register it with Simon Willison's LLM keychain to ensure system-wide availability
        try:
            import llm
            key_alias = env_var_name.split('_')[0].lower()
            llm.set_key(key_alias, raw_key)
        except Exception:
            pass

        # 2. Update Global Server Cookie
        db['active_cloud_model'] = selected_model
        
        # 3. Update Pipeline Record (Obfuscated)
        masked_key = f"{raw_key[:4]}{'*' * 15}{raw_key[-4:]}" if len(raw_key) > 8 else "****"
        payload = {
            "model": selected_model,
            "api_key": masked_key
        }
        
        # The payload dictionary becomes the value for state[step_id][step.done]
        await pip.set_step_data(pipeline_id, step_id, payload, steps)
        
        display_text = f"Model: {selected_model}\nToken: {masked_key}"
        pip.append_to_history(f"[WIDGET CONTENT] {step.show}:\n{display_text}")
        pip.append_to_history(f"[WIDGET STATE] {step.show}: Step completed")
        
        success_msg = f'{pip.get_ui_constants()["EMOJIS"]["SUCCESS"]} Cloud Engine secured: {selected_model}'
        await self.message_queue.add(pip, success_msg, verbatim=True)
        pip.speak(f"Cloud cognitive engine selected. Connection secured.", wait=False)
        
        if pip.check_finalize_needed(step_index, steps):
            await self.message_queue.add(pip, self.step_messages['finalize']['ready'], verbatim=True)
        
        widget = Pre(display_text, cls="code-block-container")
        return Div(
            pip.display_revert_widget(step_id=step_id, app_name=app_name, message=f"{step.show}: Configured", widget=widget, steps=steps),
            Div(id=next_step_id, hx_get=f"/{app_name}/{next_step_id}", hx_trigger="load"),
            id=step_id
        )
    # --- END_STEP_BUNDLE: step_03 ---

    # --- STEP_METHODS_INSERTION_POINT ---
