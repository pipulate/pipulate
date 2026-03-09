import asyncio
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
import urllib.parse

from fasthtml.common import *
from loguru import logger
from imports.crud import Step, VALID_ROLES
from starlette.responses import HTMLResponse

PLUGIN_PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DOWNLOADS_BASE_DIR = PLUGIN_PROJECT_ROOT / "downloads"

ROLES = ['Components']  # See config.AVAILABLE_ROLES for all valid roles

# 📚 Widget conversion guide: helpers/docs_sync/widget_conversion_guide.md


class FileUploadWidget:
    """
    File Upload Widget Workflow

    A focused environment for creating and testing file upload functionality.
    Users can select and upload multiple files, which are saved to a designated
    server directory with proper organization and tracking.
    """
    APP_NAME = 'file_upload_widget'
    DISPLAY_NAME = 'File Upload Widget'
    ENDPOINT_MESSAGE = 'This workflow demonstrates a file upload widget. Select one or more files to upload and save them to the server.'
    TRAINING_PROMPT = 'This workflow is for demonstrating and testing the file upload widget. The user will select files, which are then uploaded and saved to a designated server directory.'

    # UI Constants for consistent styling and automation
    UI_CONSTANTS = {
        "COLORS": {
            "HEADER_TEXT": "#2c3e50",
            "SUCCESS_BORDER": "#27ae60",
            "ERROR_BORDER": "#e74c3c"
        },
        "SPACING": {
            "STEP_PADDING": "1vh 0px 0px .5vw",
            "CONTENT_MARGIN": "1rem 0"
        },
        "AUTOMATION": {
            "FILE_INPUT_TESTID": "file-upload-widget-file-input",
            "UPLOAD_BUTTON_TESTID": "file-upload-widget-upload-button",
            "FOLDER_BUTTON_TESTID": "file-upload-widget-folder-button",
            "DOWNLOAD_BUTTON_TESTID": "file-upload-widget-download-button"
        }
    }

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
        steps = [
            Step(id='step_01', done='file_summary', show='Upload Files', refill=True, transform=lambda prev_value: prev_value.strip() if prev_value else ''),
            # --- STEPS_LIST_INSERTION_POINT ---
        ]
        routes = [(f'/{app_name}', self.landing), (f'/{app_name}/init', self.init, ['POST']), (f'/{app_name}/revert', self.handle_revert, ['POST']), (f'/{app_name}/finalize', self.finalize, ['GET', 'POST']), (f'/{app_name}/unfinalize', self.unfinalize, ['POST'])]
        self.steps = steps
        for step in steps:
            step_id = step.id
            routes.append((f'/{app_name}/{step_id}', getattr(self, step_id)))
            routes.append((f'/{app_name}/{step_id}_submit', getattr(self, f'{step_id}_submit'), ['POST']))
        for path, handler, *methods in routes:
            method_list = methods[0] if methods else ['GET']
            app.route(path, methods=method_list)(handler)
        self.step_messages = {'finalize': {'ready': 'All steps complete. Ready to finalize workflow.', 'complete': f'Workflow finalized. Use {wand.UNLOCK_BUTTON_LABEL} to make changes.'}, 'new': 'Please complete each step to explore the file upload widget.', 'step_01': {'input': 'Please select files to upload.', 'complete': 'Files uploaded successfully.'}}
        steps.append(Step(id='finalize', done='finalized', show='Finalize', refill=False))
        self.steps_indices = {step.id: i for i, step in enumerate(steps)}

    async def landing(self, request):
        """Generate the landing page using the standardized helper while maintaining WET explicitness."""
        wand = self.pipulate

        # Use centralized landing page helper - maintains WET principle by explicit call
        return wand.create_standard_landing_page(self)

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
        """ Gets a suggested input value for a step. """
        if step_id == 'step_01':
            return 'No pre-fill for file uploads. Please select files.'
        return ''

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
        """ Handles GET request for file upload widget. """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        file_summary = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})
        if 'finalized' in finalize_data and file_summary:
            try:
                save_directory = PLUGIN_DOWNLOADS_BASE_DIR / app_name
                # Parse file_summary to extract file names (if possible)
                file_lines = file_summary.split('\n') if file_summary else []
                file_buttons = []
                for line in file_lines:
                    if line.strip().startswith('📄') and '->' in line:
                        parts = line.split('->')
                        filename = parts[0].split('📄')[1].split('(')[0].strip()
                        file_path = (save_directory / filename).resolve()
                        try:
                            path_for_url = file_path.relative_to(PLUGIN_DOWNLOADS_BASE_DIR)
                            path_for_url = str(path_for_url).replace('\\', '/')
                        except Exception:
                            path_for_url = f"error/path-resolution-failed/{app_name}/{filename}"
                        download_file_link_ui = A(
                            f"⬇️ Download {filename}",
                            href=f"/download_file?file={urllib.parse.quote(path_for_url)}",
                            target="_blank",
                            role="button",
                            cls="outline contrast ml-sm"
                        )
                        file_buttons.append(download_file_link_ui)
                open_folder_link_ui = A(
                    "📂 View Folder",
                    href="#",
                    hx_get="/open-folder?path=" + urllib.parse.quote(str(save_directory.resolve())),
                    hx_swap="none",
                    title=f"Open folder: {save_directory.resolve()}",
                    cls="mr-sm outline contrast",
                    role="button"
                )
                return Div(Card(H3(f'🔒 {step.show}'), P('Uploaded files summary:'), Pre(file_summary, cls='upload-summary-pre'), P(open_folder_link_ui, *file_buttons, cls='upload-file-buttons')), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
            except Exception as e:
                logger.error(f'Error creating file summary in locked view: {str(e)}')
                return Div(Card(f'🔒 {step.show}: <content locked>'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
        elif state.get('_finalized'):
            try:
                file_summary = wand.get_step_data(pipeline_id, step_id)
                save_directory = PLUGIN_DOWNLOADS_BASE_DIR / app_name
                # Parse file_summary to extract file names (if possible)
                file_lines = file_summary.split('\n') if file_summary else []
                file_buttons = []
                for line in file_lines:
                    if line.strip().startswith('📄') and '->' in line:
                        parts = line.split('->')
                        filename = parts[0].split('📄')[1].split('(')[0].strip()
                        file_path = (save_directory / filename).resolve()
                        try:
                            path_for_url = file_path.relative_to(PLUGIN_DOWNLOADS_BASE_DIR)
                            path_for_url = str(path_for_url).replace('\\', '/')
                        except Exception:
                            path_for_url = f"error/path-resolution-failed/{app_name}/{filename}"
                        download_file_link_ui = A(
                            f"⬇️ Download {filename}",
                            href=f"/download_file?file={urllib.parse.quote(path_for_url)}",
                            target="_blank",
                            role="button",
                            cls="outline contrast ml-sm"
                        )
                        file_buttons.append(download_file_link_ui)
                open_folder_link_ui = A(
                    "📂 View Folder",
                    href="#",
                    hx_get="/open-folder?path=" + urllib.parse.quote(str(save_directory.resolve())),
                    hx_swap="none",
                    title=f"Open folder: {save_directory.resolve()}",
                    cls="mr-sm outline contrast",
                    role="button"
                )
                return Div(Card(f'🔒 {step.show}', P("Uploaded files summary:"), Pre(file_summary, cls='upload-summary-pre'), P(open_folder_link_ui, *file_buttons, cls='upload-file-buttons')), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
            except Exception as e:
                logger.error(f'Error creating file summary in locked view: {str(e)}')
                return Div(Card(f'🔒 {step.show}: <content locked>'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'))
        elif file_summary and state.get('_revert_target') != step_id:
            save_directory = PLUGIN_DOWNLOADS_BASE_DIR / app_name
            open_folder_link_ui = A(
                "📂 View Folder",
                href="#",
                hx_get="/open-folder?path=" + urllib.parse.quote(str(save_directory.resolve())),
                hx_swap="none",
                title=f"Open folder: {save_directory.resolve()}",
                cls="mr-sm outline contrast",
                    role="button"
            )
            # Parse file_summary to extract file names (if possible)
            file_lines = file_summary.split('\n') if file_summary else []
            file_buttons = []
            for line in file_lines:
                if line.strip().startswith('📄') and '->' in line:
                    parts = line.split('->')
                    filename = parts[0].split('📄')[1].split('(')[0].strip()
                    file_path = (save_directory / filename).resolve()
                    try:
                        path_for_url = file_path.relative_to(PLUGIN_DOWNLOADS_BASE_DIR)
                        path_for_url = str(path_for_url).replace('\\', '/')
                    except Exception:
                        path_for_url = f"error/path-resolution-failed/{app_name}/{filename}"
                    download_file_link_ui = A(
                        f"⬇️ Download {filename}",
                        href=f"/download_file?file={urllib.parse.quote(path_for_url)}",
                        target="_blank",
                        role="button",
                        cls="outline contrast ml-sm"
                    )
                    file_buttons.append(download_file_link_ui)
            content_container = wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: Files previously uploaded', widget=Div(
                Pre(file_summary, style='white-space: pre-wrap; font-size: 0.9em; margin-top:1em; padding: 1em; background-color: var(--pico-code-background); border-radius: var(--pico-border-radius);'),
                P(open_folder_link_ui, *file_buttons, cls='upload-file-buttons')
            ), steps=steps)
            return Div(content_container, Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        explanation = 'Select one or more files. They will be saved to the `downloads` directory in a subfolder named after this workflow.'
        await self.message_queue.add(wand, self.step_messages[step_id]['input'], verbatim=True)
        await self.message_queue.add(wand, explanation, verbatim=True)
        return Div(Card(H3(f'{wand.fmt(step_id)}: {step.show}'), P(explanation, cls='text-secondary'), Form(Input(type='file', name='uploaded_files', multiple='true', required='true', cls='contrast', data_testid=self.UI_CONSTANTS["AUTOMATION"]["FILE_INPUT_TESTID"], aria_label='Select files to upload to the server'), Button('Upload Files ▸', type='submit', cls='primary', data_testid=self.UI_CONSTANTS["AUTOMATION"]["UPLOAD_BUTTON_TESTID"], aria_label='Upload selected files to server'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}', enctype='multipart/form-data')), Div(id=next_step_id), id=step_id)

    async def step_01_submit(self, request):
        """ Process the submission for file upload widget. """
        wand, steps, app_name = (self.pipulate, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        form_data = await request.form()
        uploaded_files = form_data.getlist('uploaded_files')
        if not uploaded_files or not uploaded_files[0].filename:
            await self.message_queue.add(wand, 'No files selected. Please try again.', verbatim=True)
            explanation = 'Select one or more files. They will be saved to the `downloads` directory.'
            return Div(Card(H3(f'{wand.fmt(step_id)}: {step.show}'), P('No files were selected. Please try again.', cls='text-invalid'), P(explanation, cls='text-secondary'), Form(Input(type='file', name='uploaded_files', multiple='true', required='true', cls='contrast', data_testid=self.UI_CONSTANTS["AUTOMATION"]["FILE_INPUT_TESTID"], aria_label='Select files to upload to the server'), Button('Upload Files ▸', type='submit', cls='primary', data_testid=self.UI_CONSTANTS["AUTOMATION"]["UPLOAD_BUTTON_TESTID"], aria_label='Upload selected files to server'), hx_post=f'/{app_name}/{step_id}_submit', hx_target=f'#{step_id}', enctype='multipart/form-data')), Div(id=next_step_id), id=step_id)

        # Use the same base directory as the download endpoint
        save_directory = PLUGIN_DOWNLOADS_BASE_DIR / app_name
        try:
            save_directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            error_msg = f'Error creating save directory {save_directory}: {str(e)}'
            logger.error(error_msg)
            await self.message_queue.add(wand, error_msg, verbatim=True)
            return P(f'Error creating save directory. Please check permissions or disk space. Details: {error_msg}', cls='text-invalid')

        file_info_list_for_summary = []  # For the existing text summary
        actual_saved_file_details = []    # New list to store structured details
        total_size = 0

        for uploaded_file in uploaded_files:
            if not uploaded_file.filename:
                continue
            try:
                contents = await uploaded_file.read()
                file_size = len(contents)
                total_size += file_size

                # Save with original filename directly in file_upload_widget directory
                file_save_path = save_directory / uploaded_file.filename
                with open(file_save_path, 'wb') as f:
                    f.write(contents)

                # For the existing text summary
                file_info_list_for_summary.append(f'📄 {uploaded_file.filename} ({file_size:,} bytes) -> {file_save_path}')

                # Store structured details for link generation
                actual_saved_file_details.append({
                    'path_obj': file_save_path,
                    'filename': uploaded_file.filename,
                    'size_bytes': file_size,
                    'save_dir_path_obj': save_directory
                })
            except Exception as e:
                error_msg = f'Error saving file {uploaded_file.filename}: {str(e)}'
                logger.error(error_msg)
                await self.message_queue.add(wand, error_msg, verbatim=True)
                return P(f'Error saving file {uploaded_file.filename}. Details: {error_msg}', cls='text-invalid')

        # Construct the text summary
        file_summary = '\n'.join(file_info_list_for_summary)
        file_summary += f'\n\nTotal: {len(actual_saved_file_details)} files, {total_size:,} bytes'
        file_summary += f'\nSaved to directory: {save_directory.resolve()}'

        await wand.set_step_data(pipeline_id, step_id, file_summary, steps)
        wand.append_to_history(f'[WIDGET CONTENT] {step.show}:\n{file_summary}')
        wand.append_to_history(f'[WIDGET STATE] {step.show}: Files saved')
        await self.message_queue.add(wand, f'Successfully saved {len(actual_saved_file_details)} files to {save_directory}', verbatim=True)

        # Start building the widget content
        widget_elements = [
            Pre(file_summary, style='white-space: pre-wrap; font-size: 0.9em; margin-top:1em; padding: 1em; background-color: var(--pico-code-background); border-radius: var(--pico-border-radius);')
        ]

        if actual_saved_file_details:
            widget_elements.append(H4("File Actions:", style="margin-top: 1rem; margin-bottom: 0.5rem;"))

            for detail in actual_saved_file_details:
                file_abs_path = detail['path_obj']
                file_display_name = detail['filename']
                parent_dir_abs_path = detail['save_dir_path_obj'].resolve()

                # Calculate the path for the download URL - it should be relative to the downloads directory
                try:
                    # The path should be relative to the downloads directory
                    path_for_url = file_abs_path.relative_to(PLUGIN_DOWNLOADS_BASE_DIR)
                    # Convert to string and ensure forward slashes for URL
                    path_for_url = str(path_for_url).replace('\\', '/')
                except ValueError as e:
                    logger.error(f"Path resolution error: {str(e)}")
                    logger.error(f"File path: {file_abs_path}")
                    logger.error(f"Base dir: {PLUGIN_DOWNLOADS_BASE_DIR}")
                    # Use a more descriptive error path
                    path_for_url = f"error/path-resolution-failed/{app_name}/{file_display_name}"

                open_folder_link_ui = A(
                    "📂 View Folder",
                    href="#",
                    hx_get="/open-folder?path=" + urllib.parse.quote(str(parent_dir_abs_path)),
                    hx_swap="none",
                    title=f"Open folder: {parent_dir_abs_path}",
                    cls="mr-sm outline contrast",
                    role="button",
                    data_testid=self.UI_CONSTANTS["AUTOMATION"]["FOLDER_BUTTON_TESTID"],
                    aria_label=f"Open folder containing uploaded files: {parent_dir_abs_path}"
                )

                download_file_link_ui = A(
                    f"⬇️ Download {file_display_name}",
                    href=f"/download_file?file={urllib.parse.quote(path_for_url)}",
                    target="_blank",
                    role="button",
                    cls="outline contrast",
                    data_testid=self.UI_CONSTANTS["AUTOMATION"]["DOWNLOAD_BUTTON_TESTID"],
                    aria_label=f"Download uploaded file: {file_display_name}"
                )

                widget_elements.append(
                    P(
                        open_folder_link_ui,
                        download_file_link_ui,
                        style="margin-top: 0.5em; display: flex; align-items: center; flex-wrap: wrap; gap: 0.5rem;"
                    )
                )

        final_widget_content = Div(*widget_elements)

        content_container = wand.display_revert_widget(
            step_id=step_id,
            app_name=app_name,
            message=f'{step.show}: {len(actual_saved_file_details)} File(s) Uploaded Successfully!',
            widget=final_widget_content,
            steps=steps
        )

        return Div(
            content_container,
            Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
            id=step_id
        )

    # --- STEP_METHODS_INSERTION_POINT ---
