import asyncio
import hashlib
import json
import os
import zipfile
from pathlib import Path
from urllib.parse import urlparse, quote

from fasthtml.common import *
from loguru import logger
from starlette.responses import FileResponse, Response

from imports.crud import Step
from tools.scraper_tools import selenium_automation, generate_optics_subprocess

ROLES = ['Core', 'SEO']


class OpticsWorkflow:
    """
    911 LLM Optics Workflow: Zero-credential optical diffraction engine.
    Exposes RFC 9110 wire truth vs. hydrated DOM, structural diffs, and Link Lens
    in a verifiable 3-step FastHTML pipeline with sealed deed export.
    """
    APP_NAME = 'optics'
    DISPLAY_NAME = '911 LLM Optics 👁️'
    ENDPOINT_MESSAGE = 'Inspect DOM diffs, Link Lens, and RFC 9110 wire truth. Press Enter...'

    def __init__(self, app, pipulate, pipeline, db, app_name=APP_NAME):
        self.pipulate = pipulate
        self.app = app
        self.app_name = app_name
        self.wand = pipulate
        wand = self.wand

        self.pipeline = pipeline
        self.steps_indices = {}
        self.message_queue = self.wand.get_message_queue()
        self.ui = self.wand.get_ui_constants()

        self.steps = [
            Step(
                id='step_01',
                done='url',
                show='Target URL',
                refill=True
            ),
            Step(
                id='step_02',
                done='captured',
                show='Capture & SIFT',
                refill=False
            ),
            Step(
                id='step_03',
                done='inspected',
                show='Optical Analysis',
                refill=False
            ),
            Step(id='finalize', done='finalized', show='Finalize & Deed', refill=False)
        ]

        self.steps_indices = {step.id: i for i, step in enumerate(self.steps)}
        pipulate.register_workflow_routes(self)

        self.step_messages = {
            'finalize': {
                'ready': f'{self.ui["EMOJIS"]["SUCCESS"]} All steps complete. Ready to finalize and seal the optics deed.',
                'complete': f'{self.ui["EMOJIS"]["COMPLETION"]} Workflow finalized. Verified deed ready for export.'
            }
        }
        for step in self.steps:
            if step.id != 'finalize':
                self.step_messages[step.id] = {
                    'input': f'{self.ui["EMOJIS"]["INPUT_FORM"]} {self.wand.fmt(step.id)}: Please enter {step.show}.',
                    'complete': f'{self.ui["EMOJIS"]["SUCCESS"]} {step.show} complete. Proceed to next step.'
                }

        @self.app.get('/optics')
        async def redirect_optics_alias(request):
            from starlette.responses import RedirectResponse
            qs = f"?{request.url.query}" if request.url.query else ""
            return RedirectResponse(url=f'/optics_workflow{qs}', status_code=302)

        # Dedicated route for downloading verified ZIP deed
        @self.app.get(f'/{self.app_name}/download/{{pipeline_id}}')
        async def download_deed(pipeline_id: str):
            state = self.wand.read_state(pipeline_id)
            out_dir_str = state.get('step_02', {}).get('captured', '')
            if not out_dir_str:
                return Response("Artifact directory not found", status_code=404)
            zip_path = Path(out_dir_str) / "optics_deed.zip"
            if zip_path.exists():
                return FileResponse(
                    str(zip_path),
                    filename=f"optics_deed_{pipeline_id}.zip",
                    media_type="application/zip"
                )
            return Response("Deed file not found", status_code=404)

    def _is_scripted_demo_run(self, pipeline_id: str) -> bool:
        """True when Ghost Driver (optics_test.json -> live-{{timestamp}}) owns narration for this run."""
        pid = str(pipeline_id or "")
        return pid.startswith("live-") or "-optics-live-" in pid

    def _speak_step_cue(self, pipeline_id: str, text: str) -> None:
        """Speak interactive workflow cue unless Ghost Driver's scripted narration is driving."""
        if not self._is_scripted_demo_run(pipeline_id):
            self.wand.speak(text, wait=False)

    async def landing(self, request):
        return self.wand.create_standard_landing_page(self)

    async def init(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        form = await request.form()
        user_input = form.get('pipeline_id', '').strip()
        if not user_input:
            response = Response('')
            response.headers['HX-Refresh'] = 'true'
            return response

        context = wand.get_plugin_context(self)
        profile_name = context.get('profile_name') or 'default'
        profile_part = profile_name.replace(' ', '_')
        plugin_part = app_name.replace(' ', '_')
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

        all_steps_complete = all((step.id in state and step.done in state[step.id] for step in steps[:-1]))
        is_finalized = 'finalize' in state and 'finalized' in state['finalize']

        await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["WORKFLOW"]} Optics Run ID: {pipeline_id}', verbatim=True, spaces_before=0)
        await self.message_queue.add(wand, f"{self.ui['EMOJIS']['KEY']} Access this audit anytime using '{pipeline_id}'.", verbatim=True, spaces_before=0)

        if all_steps_complete:
            if is_finalized:
                status_msg = f'{self.ui["EMOJIS"]["LOCKED"]} Optics audit is complete and finalized. Download deed below.'
            else:
                status_msg = f'{self.ui["EMOJIS"]["SUCCESS"]} Optics analysis ready. Finalize to seal the deed.'
            await self.message_queue.add(wand, status_msg, verbatim=True)
            self.wand.speak("Optics audit recovered.", wait=False)
        elif not any((step.id in state for step in self.steps)):
            await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["INPUT_FORM"]} Step 1: Provide target URL to begin optical diffraction.', verbatim=True)
            self._speak_step_cue(pipeline_id, "Optics workflow initialized. Enter target URL to begin.")

        parsed = wand.parse_pipeline_key(pipeline_id)
        prefix = f"{parsed['profile_part']}-{parsed['plugin_part']}-"
        self.pipeline.xtra(app_name=app_name)
        matching_records = [record.pkey for record in self.pipeline() if record.pkey.startswith(prefix)]
        if pipeline_id not in matching_records:
            matching_records.append(pipeline_id)
        wand.update_datalist('pipeline-ids', options=matching_records)
        return wand.run_all_cells(app_name, steps)

    async def finalize(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        finalize_step = steps[-1]
        finalize_data = wand.get_step_data(pipeline_id, finalize_step.id, {})

        if request.method == 'GET':
            if finalize_step.done in finalize_data:
                state = wand.read_state(pipeline_id)
                out_dir_str = state.get('step_02', {}).get('captured', '')
                zip_path = Path(out_dir_str) / "optics_deed.zip" if out_dir_str else None
                hash_str = "Unknown"
                if zip_path and zip_path.exists():
                    hash_str = hashlib.sha256(zip_path.read_bytes()).hexdigest()[:16]

                target_url_Done = state.get('step_01', {}).get('url', 'https://example.com/')
                mail_subj = quote(f"911 LLM Optics AI-Readiness Audit: {target_url_Done}")
                mail_body = quote(
                    f"Attached is the 911 LLM Optics single-page AI-readiness deed (optics_deed_{pipeline_id}.zip) for {target_url_Done}.\n\n"
                    f"- Sealed SHA-256 Digest (first 16): {hash_str}\n"
                    f"- Inspect audit_report.md, rfc9110_probe.json, and the Monokai DOM diff lenses inside the ZIP.\n"
                    f"- Run your own audit locally: curl -fsSL https://sunpug.io | less\n"
                )
                return Article(
                    H3(f'{self.ui["EMOJIS"]["LOCKED"]} Optical Deed Sealed'),
                    P(f"SHA-256 Digest: {hash_str}", cls='text-muted'),
                    Div(
                        A("📥 Download Verified Optics Deed (ZIP)", href=f'/{app_name}/download/{pipeline_id}', cls=self.ui['BUTTON_STYLES']['PRIMARY'], role='button', id='optics-download-deed-btn', style='margin-right: 0.75rem;'),
                        A("📧 Email / Share Audit Deed", href=f"mailto:?subject={mail_subj}&body={mail_body}", cls=self.ui['BUTTON_STYLES']['OUTLINE'], role='button', id='optics-email-deed-btn'),
                        style='margin-bottom: 1rem;'
                    ),
                    Form(
                        Button(self.ui['BUTTON_LABELS']['UNLOCK'], type='submit', cls=self.ui['BUTTON_STYLES']['OUTLINE'], id='optics-unlock-btn'),
                        hx_post=f'/{app_name}/unfinalize',
                        hx_target=f'#{app_name}-container',
                        hx_swap='outerHTML',
                        id='optics-unlock-form'
                    ),
                    id=finalize_step.id,
                    role='region'
                )
            else:
                all_steps_complete = all((wand.get_step_data(pipeline_id, step.id, {}).get(step.done) for step in steps[:-1]))
                if all_steps_complete:
                    return Article(
                        H3(f'{self.ui["EMOJIS"]["SUCCESS"]} Optical Analysis Complete. Seal Deed?'),
                        P("Finalizing will compile the ZIP deed, stamp the cryptographic hash, and lock the run.", cls='text-muted'),
                        Form(
                            Button(self.ui['BUTTON_LABELS']['FINALIZE'], type='submit', cls=self.ui['BUTTON_STYLES']['PRIMARY'], id='optics-finalize-btn'),
                            hx_post=f'/{app_name}/finalize',
                            hx_target=f'#{app_name}-container',
                            hx_swap='outerHTML',
                            id='optics-finalize-form'
                        ),
                        id=finalize_step.id,
                        role='region'
                    )
                else:
                    return Div(id=finalize_step.id)
        else:
            # POST: Finalize workflow, build sealed ZIP
            state = wand.read_state(pipeline_id)
            out_dir_str = state.get('step_02', {}).get('captured', '')
            if out_dir_str and os.path.isdir(out_dir_str):
                out_dir = Path(out_dir_str)
                zip_path = out_dir / "optics_deed.zip"
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for fname in [
                        "audit_report.md", "rfc9110_probe.json", "origin_markdown.md",
                        "headers.json", "source.html", "hydrated_dom.html",
                        "diff_simple_dom.txt", "diff_simple_dom.html",
                        "diff_hierarchy.txt", "diff_hierarchy.html",
                        "diff_boxes.txt", "diff_boxes.html",
                        "source_dom_hierarchy.txt", "source_dom_hierarchy.html",
                        "hydrated_dom_hierarchy.txt", "hydrated_dom_hierarchy.html",
                        "source_dom_layout_boxes.txt", "source_dom_layout_boxes.html",
                        "hydrated_dom_layout_boxes.txt", "hydrated_dom_layout_boxes.html",
                        "links.md", "seo.md"
                    ]:
                        fpath = out_dir / fname
                        if fpath.exists():
                            zf.write(fpath, arcname=fname)

            await wand.finalize_workflow(pipeline_id)
            await self.message_queue.add(wand, self.step_messages['finalize']['complete'], verbatim=True)
            self._speak_step_cue(pipeline_id, "The optics deed is now locked and sealed.")
            return wand.run_all_cells(app_name, steps)

    async def unfinalize(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        await wand.unfinalize_workflow(pipeline_id)
        await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["UNLOCKED"]} Workflow unfinalized.', verbatim=True)
        self.wand.speak("Workflow unlocked.", wait=False)
        return wand.run_all_cells(app_name, steps)

    async def handle_revert(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
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
        await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["WARNING"]} Reverted to {step_id}. {message}', verbatim=True)
        return wand.run_all_cells(app_name, steps)

    async def get_suggestion(self, step_id, state):
        return ''

    def _render_rich_html_lens(self, html_doc: str, fallback_text: str, scope_id: str):
        import re
        if not html_doc:
            return Pre(
                fallback_text,
                style='max-height: 340px; overflow-y: auto; overflow-x: auto; background: #111; color: #f8f8f2; padding: 0.75rem; border-radius: 4px; font-size: 0.75rem; line-height: 1.3;'
            )
        style_match = re.search(r'<style[^>]*>(.*?)</style>', html_doc, flags=re.DOTALL | re.IGNORECASE)
        pre_match = re.search(r'<pre[^>]*>.*?</pre>', html_doc, flags=re.DOTALL | re.IGNORECASE)
        if not pre_match:
            return Pre(
                fallback_text,
                style='max-height: 340px; overflow-y: auto; overflow-x: auto; background: #111; color: #f8f8f2; padding: 0.75rem; border-radius: 4px; font-size: 0.75rem; line-height: 1.3;'
            )
        pre_html = pre_match.group(0)
        style_css = ""
        if style_match:
            raw_css = style_match.group(1)
            rule_lines = [
                re.sub(r'\.r(\d+)\b', f'.{scope_id}_r\\1', ln.strip())
                for ln in raw_css.splitlines()
                if ln.strip().startswith('.r')
            ]
            if rule_lines:
                style_css = f"<style>{' '.join(rule_lines)}</style>"
            pre_html = re.sub(r'class="r(\d+)"', f'class="{scope_id}_r\\1"', pre_html)
        return Div(
            NotStr(style_css + pre_html),
            style='max-height: 360px; overflow-y: auto; overflow-x: auto; background: #111; color: #f8f8f2; padding: 0.75rem; border-radius: 4px; font-size: 0.75rem; line-height: 1.3; border: 1px solid #2a3140;'
        )

    def _render_colored_diff(self, diff_text: str):
        lines = []
        for raw_line in diff_text.splitlines():
            if raw_line.startswith('+++') or raw_line.startswith('---'):
                lines.append(Div(raw_line, style='color: #bd93f9; font-weight: bold; white-space: pre;'))
            elif raw_line.startswith('@@'):
                lines.append(Div(raw_line, style='color: #8be9fd; background: rgba(139, 233, 253, 0.08); white-space: pre;'))
            elif raw_line.startswith('+'):
                lines.append(Div(raw_line, style='color: #50fa7b; background: rgba(80, 250, 123, 0.12); white-space: pre;'))
            elif raw_line.startswith('-'):
                lines.append(Div(raw_line, style='color: #ff5555; background: rgba(255, 85, 85, 0.12); white-space: pre;'))
            else:
                lines.append(Div(raw_line or ' ', style='color: #f8f8f2; white-space: pre;'))
        return Pre(
            *lines,
            style='max-height: 280px; overflow-y: auto; overflow-x: auto; background: #111; padding: 0.75rem; border-radius: 4px; font-size: 0.78rem; line-height: 1.35;'
        )

    def _render_markdown_lens(self, md_text: str, widget_id: str):
        return Div(
            Pre(
                md_text,
                id=f'{widget_id}_source',
                style='display: none; white-space: pre-wrap;'
            ),
            Div(
                id=f'{widget_id}_rendered',
                cls='markdown-body',
                style='max-height: 320px; overflow-y: auto; background: #111; color: #f8f8f2; padding: 1rem; border-radius: 4px; font-size: 0.84rem; border: 1px solid #2a3140;'
            ),
            Details(
                Summary('View Raw Link Lens Markdown', style='font-size: 0.78rem; margin-top: 0.4rem; cursor: pointer; color: #8be9fd;'),
                Pre(
                    Code(md_text, cls='language-markdown'),
                    style='max-height: 200px; overflow-y: auto; font-size: 0.75rem; margin-top: 0.4rem;'
                )
            ),
            Script(f"""
                (function() {{
                    const src = document.getElementById('{widget_id}_source');
                    const out = document.getElementById('{widget_id}_rendered');
                    if (src && out) {{
                        const raw = src.textContent || '';
                        if (typeof marked !== 'undefined') {{
                            out.innerHTML = marked.parse(raw);
                        }} else {{
                            out.textContent = raw;
                        }}
                    }}
                    const stepEl = document.getElementById('step_03');
                    if (stepEl && typeof Prism !== 'undefined') {{
                        Prism.highlightAllUnder(stepEl);
                    }}
                }})();
            """),
            id=widget_id
        )

    # --- STEP 01: TARGET URL ---
    async def step_01(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        user_val = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})

        if 'finalized' in finalize_data:
            return Div(
                Article(
                    H3(f'{self.ui["EMOJIS"]["LOCKED"]} {step.show}: {user_val}'),
                    role='region'
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        elif user_val and state.get('_revert_target') != step_id:
            return Div(
                wand.display_revert_header(
                    step_id=step_id,
                    app_name=app_name,
                    message=f'{self.ui["EMOJIS"]["USER_INPUT"]} {step.show}: {user_val}',
                    steps=steps
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        else:
            explanation = "Provide an HTTP/HTTPS URL to observe wire truth vs. hydrated DOM."
            return Div(
                Article(
                    H3(f'{self.ui["EMOJIS"]["USER_INPUT"]} {self.wand.fmt(step.id)}: Enter {step.show}'),
                    P(explanation, cls='text-muted'),
                    Label('Target URL:', _for='optics-step01-url-input'),
                    Form(
                        wand.wrap_with_inline_button(
                            Input(
                                type='url',
                                name=step.done,
                                value=user_val or 'https://mikelev.in/',
                                placeholder='https://example.com/',
                                required=True,
                                autofocus=True,
                                id='optics-step01-url-input',
                                aria_label='Target URL to inspect'
                            ),
                            button_label=self.ui['BUTTON_LABELS']['NEXT_STEP']
                        ),
                        hx_post=f'/{app_name}/{step_id}_submit',
                        hx_target=f'#{step_id}',
                        id='optics-step01-form'
                    ),
                    role='region'
                ),
                Div(id=next_step_id),
                id=step_id
            )

    async def step_01_submit(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get("pipeline_id", "unknown")

        form = await request.form()
        user_val = form.get(step.done, "").strip()
        if not user_val:
            error_msg = f'{self.ui["EMOJIS"]["ERROR"]} Please enter a valid URL'
            await self.message_queue.add(wand, error_msg, verbatim=True)
            return P(error_msg, cls='text-invalid')

        if not user_val.startswith(('http://', 'https://')):
            user_val = f'https://{user_val}'

        await wand.set_step_data(pipeline_id, step_id, user_val, steps)
        await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["SUCCESS"]} Target set: {user_val}', verbatim=True)
        self._speak_step_cue(pipeline_id, "Target URL set. Ready for optical capture.")
        self.wand.append_to_history(f"[WIDGET CONTENT] {step.show}:\n{user_val}")
        return wand.chain_reverter(step_id, step_index, steps, app_name, user_val)

    # --- STEP 02: CAPTURE & SIFT ---
    async def step_02(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        step_id = 'step_02'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        user_val = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})

        target_url = wand.get_step_data(pipeline_id, 'step_01', {}).get('url', '')

        if 'finalized' in finalize_data:
            return Div(
                Article(
                    H3(f'{self.ui["EMOJIS"]["LOCKED"]} {step.show}: Captured & SIFTed'),
                    role='region'
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        elif user_val and state.get('_revert_target') != step_id:
            return Div(
                wand.display_revert_header(
                    step_id=step_id,
                    app_name=app_name,
                    message=f'{self.ui["EMOJIS"]["SUCCESS"]} {step.show}: Artifacts Extracted',
                    steps=steps
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        else:
            return Div(
                Article(
                    H3(f'{self.ui["EMOJIS"]["WORKFLOW"]} {self.wand.fmt(step.id)}: {step.show}'),
                    P(f"Target: {target_url}", cls='text-muted'),
                    P("Engage undetected browser to drain CDP performance log, capture wire response vs. hydrated DOM, and run the SIFT comparator.", cls='text-muted'),
                    Form(
                        Label(
                            Input(
                                type='checkbox',
                                name='show_browser',
                                role='switch',
                                checked=bool(state.get('show_browser', False)),
                                id='optics-step02-show-browser'
                            ),
                            ' Pop visible browser window (headful mode; default is headless)',
                            _for='optics-step02-show-browser',
                            style='margin-bottom: 0.75rem; font-size: 0.88rem; display: block;'
                        ),
                        Button("Engage Optics SIFT 👁️", type='submit', cls=self.ui['BUTTON_STYLES']['PRIMARY'], id='optics-step02-btn'),
                        hx_post=f'/{app_name}/{step_id}_submit',
                        hx_target=f'#{step_id}',
                        onsubmit="const b=this.querySelector('button');if(b){b.setAttribute('aria-busy','true');b.textContent='Capturing Wire & DOM (SIFTing)...';}",
                        id='optics-step02-form'
                    ),
                    role='region'
                ),
                Div(id=next_step_id),
                id=step_id
            )

    async def step_02_submit(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        step_id = 'step_02'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get("pipeline_id", "unknown")

        target_url = wand.get_step_data(pipeline_id, 'step_01', {}).get('url', '')
        parsed = urlparse(target_url)
        domain = parsed.netloc or "unknown"
        slug = quote(parsed.path or "/", safe="").replace("/", "_")[:100] or "%2F"
        output_dir = Path("browser_cache") / domain / slug
        output_dir.mkdir(parents=True, exist_ok=True)

        form = await request.form()
        show_browser = bool(form.get('show_browser'))
        state = wand.read_state(pipeline_id)
        state['show_browser'] = show_browser
        wand.write_state(pipeline_id, state)
        params = {
            "url": target_url,
            "domain": domain,
            "url_path_slug": slug,
            "take_screenshot": False,
            "headless": not show_browser,
            "is_notebook_context": True,
            "verbose": False,
            "persistent": False,
            "override_cache": True,
        }

        try:
            res = await selenium_automation(params)
        except Exception as e:
            logger.warning(f"Selenium capture failed: {e}; attempting HTTP fallback")
            res = {"success": False}

        if res.get("success"):
            looking_at = res.get("looking_at_files") or {}
            sample_path = next((Path(v) for v in looking_at.values() if v), None)
            if sample_path and sample_path.parent.exists():
                output_dir = sample_path.parent
            if not (output_dir / "hydrated_dom_layout_boxes.txt").exists():
                await generate_optics_subprocess(str(output_dir))
        else:
            import urllib.request
            try:
                req = urllib.request.Request(
                    target_url,
                    headers={"User-Agent": "Mozilla/5.0 (Pipulate-Optics/1.0)", "Accept": "text/html,text/markdown;q=0.9"}
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw_html = resp.read().decode('utf-8', errors='replace')
                    headers_dict = {k.lower(): v for k, v in resp.headers.items()}
                (output_dir / "source.html").write_text(raw_html, encoding='utf-8')
                (output_dir / "hydrated_dom.html").write_text(raw_html, encoding='utf-8')
                (output_dir / "simple_source_html.html").write_text(raw_html, encoding='utf-8')
                (output_dir / "simple_hydrated_dom.html").write_text(raw_html, encoding='utf-8')
                (output_dir / "headers.json").write_text(json.dumps({
                    "url": target_url,
                    "final_url": target_url,
                    "source_provenance": "http_fallback",
                    "headers": headers_dict
                }, indent=2), encoding='utf-8')
                await generate_optics_subprocess(str(output_dir))
            except Exception as fb_err:
                error_msg = f'{self.ui["EMOJIS"]["ERROR"]} Capture failed: {fb_err}'
                await self.message_queue.add(wand, error_msg, verbatim=True)
                return P(error_msg, cls='text-invalid')

        # Active RFC 9110 Content Negotiation Probe (Accept: text/markdown)
        import urllib.request
        rfc9110_meta = {
            "url": target_url,
            "negotiated": False,
            "status": 0,
            "content_type": "",
            "vary": "",
            "bytes": 0,
        }
        try:
            md_req = urllib.request.Request(
                target_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; Pipulate-911-Optics/1.0; +https://pipulate.com)",
                    "Accept": "text/markdown",
                },
            )
            with urllib.request.urlopen(md_req, timeout=12) as md_resp:
                md_bytes_raw = md_resp.read()
                md_ctype = md_resp.headers.get("Content-Type", "")
                md_vary = md_resp.headers.get("Vary", "")
                is_md = "text/markdown" in md_ctype.lower()
                rfc9110_meta = {
                    "url": target_url,
                    "negotiated": is_md,
                    "status": getattr(md_resp, "status", 200),
                    "content_type": md_ctype,
                    "vary": md_vary,
                    "bytes": len(md_bytes_raw),
                }
                if is_md:
                    (output_dir / "origin_markdown.md").write_bytes(md_bytes_raw)
        except Exception as md_err:
            logger.debug(f"RFC 9110 markdown probe note for {target_url}: {md_err}")
        (output_dir / "rfc9110_probe.json").write_text(
            json.dumps(rfc9110_meta, indent=2), encoding="utf-8"
        )
        stored_val = str(output_dir)
        await wand.set_step_data(pipeline_id, step_id, stored_val, steps)
        await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["SUCCESS"]} Optics capture complete for {domain}', verbatim=True)
        self._speak_step_cue(pipeline_id, "Optics capture complete. Diff ready for inspection.")
        return wand.chain_reverter(step_id, step_index, steps, app_name, stored_val)

    # --- STEP 03: OPTICAL ANALYSIS ---
    async def step_03(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        step_id = 'step_03'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        user_val = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})

        out_dir_str = wand.get_step_data(pipeline_id, 'step_02', {}).get('captured', '')
        out_dir = Path(out_dir_str) if out_dir_str else None

        if 'finalized' in finalize_data:
            return Div(
                Article(
                    H3(f'{self.ui["EMOJIS"]["LOCKED"]} {step.show}: Inspection Verified'),
                    role='region'
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        elif user_val and state.get('_revert_target') != step_id:
            return Div(
                wand.display_revert_header(
                    step_id=step_id,
                    app_name=app_name,
                    message=f'{self.ui["EMOJIS"]["SUCCESS"]} {step.show}: Verified',
                    steps=steps
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        else:
            # Read artifacts
            diff_text = "No diff artifact found."
            hier_diff_text = "No hierarchy diff found."
            hier_tree_text = "No DOM hierarchy tree found."
            hier_tree_html = ""
            boxes_text = "No layout boxes found."
            boxes_html = ""
            boxes_diff_text = "No layout boxes diff found."
            seo_md_text = "No agent markdown extracted."
            origin_md_text = "Origin did not serve text/markdown on RFC 9110 probe."
            links_text = "No link lens found."
            provenance = "unknown"
            rfc_headers_text = "No RFC 9110/9111 headers captured."
            src_bytes = 0
            hyd_bytes = 0
            hydration_only_links = "0 anchor(s)"
            has_vary_accept = False
            md_negotiated = False
            md_bytes = 0
            md_ctype = ""

            if out_dir and out_dir.exists():
                src_file = out_dir / "source.html"
                hyd_file = out_dir / "hydrated_dom.html"
                rfc_probe_file = out_dir / "rfc9110_probe.json"
                if rfc_probe_file.exists():
                    try:
                        p_data = json.loads(rfc_probe_file.read_text(encoding="utf-8"))
                        md_negotiated = bool(p_data.get("negotiated", False))
                        md_bytes = int(p_data.get("bytes", 0))
                        md_ctype = str(p_data.get("content_type", ""))
                        if "accept" in str(p_data.get("vary", "")).lower():
                            has_vary_accept = True
                    except Exception:
                        pass
                if src_file.exists():
                    src_bytes = src_file.stat().st_size
                if hyd_file.exists():
                    hyd_bytes = hyd_file.stat().st_size
                diff_path = out_dir / "diff_simple_dom.txt"
                if not diff_path.exists():
                    diff_path = out_dir / "diff_hierarchy.txt"
                if diff_path.exists():
                    diff_text = diff_path.read_text(encoding='utf-8')[:4000]

                hier_path = out_dir / "diff_hierarchy.txt"
                if hier_path.exists():
                    hier_diff_text = hier_path.read_text(encoding='utf-8')[:4000]
                tree_path = out_dir / "hydrated_dom_hierarchy.txt"
                if tree_path.exists():
                    hier_tree_text = tree_path.read_text(encoding='utf-8')[:6000]
                tree_html_path = out_dir / "hydrated_dom_hierarchy.html"
                if tree_html_path.exists():
                    hier_tree_html = tree_html_path.read_text(encoding='utf-8')

                boxes_path = out_dir / "hydrated_dom_layout_boxes.txt"
                if boxes_path.exists():
                    boxes_text = boxes_path.read_text(encoding='utf-8')[:6000]
                boxes_html_path = out_dir / "hydrated_dom_layout_boxes.html"
                if boxes_html_path.exists():
                    boxes_html = boxes_html_path.read_text(encoding='utf-8')
                boxes_diff_path = out_dir / "diff_boxes.txt"
                if boxes_diff_path.exists():
                    boxes_diff_text = boxes_diff_path.read_text(encoding='utf-8')[:4000]

                seo_path = out_dir / "seo.md"
                if seo_path.exists():
                    seo_md_text = seo_path.read_text(encoding='utf-8')[:3000]
                origin_md_path = out_dir / "origin_markdown.md"
                if origin_md_path.exists():
                    origin_md_text = origin_md_path.read_text(encoding='utf-8', errors='replace')[:4000]

                links_path = out_dir / "links.md"
                if links_path.exists():
                    full_links = links_path.read_text(encoding='utf-8')
                    links_text = full_links[:2500]
                    for ln in full_links.splitlines():
                        if "present only after hydration:" in ln:
                            hydration_only_links = ln.split("present only after hydration:", 1)[1].strip()
                            break

                headers_path = out_dir / "headers.json"
                if headers_path.exists():
                    try:
                        h_data = json.loads(headers_path.read_text(encoding='utf-8'))
                        provenance = h_data.get("source_provenance") or h_data.get("header_selection") or "wire"
                        hdr_source = h_data.get("headers") or h_data.get("response_headers") or {}
                        raw_hdrs = {str(k).lower(): v for k, v in hdr_source.items()}
                        has_vary_accept = "accept" in str(raw_hdrs.get("vary", "")).lower()
                        meta_lines = []
                        if "status" in h_data:
                            meta_lines.append(f"status: {h_data['status']}")
                        if "header_selection" in h_data:
                            meta_lines.append(f"header-selection: {h_data['header_selection']}")
                        rfc_keys = [
                            "content-type", "vary", "cache-control", "etag",
                            "age", "cache-status", "cf-cache-status", "link",
                            "content-signal", "server"
                        ]
                        found_hdrs = [f"{k}: {raw_hdrs[k]}" for k in rfc_keys if k in raw_hdrs]
                        if not found_hdrs and raw_hdrs:
                            found_hdrs = [f"{k}: {v}" for k, v in list(raw_hdrs.items())[:12]]
                        combined_hdrs = meta_lines + found_hdrs
                        if combined_hdrs:
                            rfc_headers_text = "\n".join(combined_hdrs)
                    except Exception:
                        pass

            vary_badge = "✅ RFC 9111 Vary: Accept" if has_vary_accept else "⚠️ No Vary: Accept"
            md_badge = f"✅ RFC 9110 Markdown: {md_bytes:,} B" if md_negotiated else "❌ RFC 9110 Markdown: Not Served"
            if out_dir and out_dir.exists():
                target_url_str = wand.get_step_data(pipeline_id, 'step_01', {}).get('url', 'unknown')
                report_lines = [
                    "# 911 LLM Optics: Single-Page AI-Readiness Audit Deed",
                    "",
                    f"- **Target URL**: `{target_url_str}`",
                    f"- **Wire Provenance**: `{provenance.upper()}`",
                    f"- **RFC 9110 (`Accept: text/markdown`)**: {md_badge} (`{md_ctype or 'n/a'}`)",
                    f"- **RFC 9111 (`Vary: Accept` Edge Partitioning)**: {vary_badge}",
                    f"- **Wire Source HTML**: `{src_bytes:,}` bytes",
                    f"- **Hydrated DOM HTML**: `{hyd_bytes:,}` bytes",
                    f"- **Links Visible Only After JS Hydration**: `{hydration_only_links}`",
                    "",
                    "## Selected Wire Headers",
                    "```yaml",
                    rfc_headers_text,
                    "```",
                ]
                (out_dir / "audit_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
            accordion_css = Style("""
                #step_03 details > summary {
                    list-style: none;
                    padding: 0.35rem 0.6rem;
                    background: #161b22;
                    border: 1px solid #30363d;
                    border-radius: 5px;
                    user-select: none;
                    transition: background 0.15s ease;
                }
                #step_03 details > summary:hover {
                    background: #1f2937;
                }
                #step_03 details > summary::-webkit-details-marker {
                    display: none;
                }
                #step_03 details > summary::before {
                    content: "▸ ";
                    display: inline-block;
                    width: 1.15rem;
                    font-weight: bold;
                }
                #step_03 details[open] > summary::before {
                    content: "▾ ";
                }
            """)
            return Div(
                accordion_css,
                Article(
                    H3(f'{self.ui["EMOJIS"]["GREETING"]} {self.wand.fmt(step.id)}: {step.show}'),
                    P(f"Wire Truth Provenance: {provenance.upper()}", cls='text-muted'),
                    Div(
                        Strong("📊 Executive AI-Readiness Verdict: "),
                        Span(f"Wire HTML: {src_bytes:,} B vs. Hydrated DOM: {hyd_bytes:,} B | "),
                        Span(f"{md_badge} | "),
                        Span(f"JS-Only Links: {hydration_only_links} | "),
                        Span(vary_badge),
                        id='optics-executive-verdict',
                        style='background: #161b22; color: #f0f6fc; border: 1px solid #30363d; border-left: 4px solid #50fa7b; padding: 0.75rem 1rem; border-radius: 6px; margin-bottom: 1rem; font-size: 0.85rem;'
                    ),
                    H4("1. RFC 9110 / 9111 Wire Headers (Semantics & Caching)"),
                    Pre(
                        Code(rfc_headers_text, cls='language-yaml'),
                        cls='language-yaml',
                        style='max-height: 180px; overflow-y: auto; border-radius: 4px; font-size: 0.78rem;'
                    ),
                    H4("2. DOM Structural Diff (Source vs. Hydrated)"),
                    self._render_colored_diff(diff_text),
                    H4("3. Link Lens (Anchor Accounting)"),
                    self._render_markdown_lens(links_text, f"optics-links-{pipeline_id.replace('-', '_')}"),
                    H4("4. Colorized DOM Hierarchy Tree & ASCII Layout Boxes"),
                    Details(
                        Summary("View Hydrated DOM Hierarchy Tree (🌐 Document Root — Monokai Color)", id='optics-tree-summary', style='font-size: 0.84rem; cursor: pointer; color: #f1fa8c; margin-bottom: 0.4rem;'),
                        self._render_rich_html_lens(hier_tree_html, hier_tree_text, "optics_tree"),
                        id='optics-tree-details'
                    ),
                    Details(
                        Summary("View Hydrated ASCII Layout Boxes (Monokai Color)", id='optics-boxes-summary', style='font-size: 0.84rem; cursor: pointer; color: #50fa7b; margin-top: 0.4rem; margin-bottom: 0.4rem;'),
                        self._render_rich_html_lens(boxes_html, boxes_text, "optics_boxes"),
                        id='optics-boxes-details'
                    ),
                    Details(
                        Summary("View Hierarchy Diff (Source vs. Hydrated Tree)", id='optics-hier-summary', style='font-size: 0.84rem; cursor: pointer; color: #8be9fd; margin-top: 0.4rem; margin-bottom: 0.4rem;'),
                        self._render_colored_diff(hier_diff_text),
                        id='optics-hier-details'
                    ),
                    Details(
                        Summary("View ASCII Layout Boxes Diff (Source vs. Hydrated Boxes)", id='optics-boxes-diff-summary', style='font-size: 0.84rem; cursor: pointer; color: #ffb86c; margin-top: 0.4rem; margin-bottom: 0.4rem;'),
                        self._render_colored_diff(boxes_diff_text),
                        id='optics-boxes-diff-details'
                    ),
                    H4("5. RFC 9110 Origin Markdown vs. Distilled DOM Markdown"),
                    Details(
                        Summary("View RFC 9110 Negotiated Origin Markdown (origin_markdown.md)", id='optics-origin-md-summary', style='font-size: 0.84rem; cursor: pointer; color: #50fa7b; margin-bottom: 0.4rem;'),
                        self._render_markdown_lens(origin_md_text, f"optics-origin-md-{pipeline_id.replace('-', '_')}"),
                        id='optics-origin-md-details'
                    ),
                    Details(
                        Summary("View Distilled DOM Markdown Payload (seo.md)", id='optics-seo-summary', style='font-size: 0.84rem; cursor: pointer; color: #bd93f9; margin-top: 0.4rem; margin-bottom: 0.4rem;'),
                        self._render_markdown_lens(seo_md_text, f"optics-seo-{pipeline_id.replace('-', '_')}"),
                        id='optics-seo-details'
                    ),
                    Form(
                        Button("Accept Optical Findings & Seal ▸", type='submit', cls=self.ui['BUTTON_STYLES']['PRIMARY'], id='optics-step03-accept-btn'),
                        hx_post=f'/{app_name}/{step_id}_submit',
                        hx_target=f'#{step_id}',
                        style='margin-top: 1rem;',
                        id='optics-step03-form'
                    ),
                    role='region'
                ),
                Div(id=next_step_id),
                id=step_id
            )

    async def step_03_submit(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        step_id = 'step_03'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get("pipeline_id", "unknown")

        stored_val = "verified"
        await wand.set_step_data(pipeline_id, step_id, stored_val, steps)
        await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["SUCCESS"]} Optical analysis verified.', verbatim=True)
        self._speak_step_cue(pipeline_id, "Optical analysis accepted. Ready to seal deed.")
        return wand.chain_reverter(step_id, step_index, steps, app_name, stored_val)
