import logging
import time
import re
from pathlib import Path

from fastcore.xml import *
from fasthtml.common import *

ROLES = ['Tutorial']

logger = logging.getLogger(__name__)


class DocumentationPlugin:
    NAME = "documentation"
    DISPLAY_NAME = "Documentation 📚"
    ENDPOINT_MESSAGE = "📚 Documentation Browser: When you view any document, its content is automatically added to my conversation history so you can ask me specific questions about it. Browse guides, training files, and framework rules - I'll have the full context to help you understand the content."
    
    # Bootstrap instructions for AI assistants - added silently to conversation history
    TRAINING_PROMPT = """🔥 AI Assistant Bootstrap Instructions - Pipulate Radical Transparency System

## 🎯 Magic Bootstrap Phrases (Copy & Use These)

**Most Common Bootstrap**: "I need help with my Pipulate workflow. My pipeline_id is [PIPELINE_ID]. Please use the pipeline_state_inspector MCP tool to grab my complete workflow state, then tell me what you found and how you can help."

**Mid-Session Debugging**: "My trifecta workflow is stuck at [STEP_NAME]. Pipeline: [PIPELINE_ID]. Please inspect my pipeline state and check the logs for errors."

**File/Data Investigation**: "I have data at downloads/trifecta/[USERNAME]/[PROJECT]/[ANALYSIS]/. Please analyze what files exist and help me understand the data structure."

**API/Template Issues**: "My Botify API call failed for [USERNAME]/[PROJECT]/[ANALYSIS]. Please use the discover-fields endpoint to check available fields and validate my template configuration."

## 🔧 Essential MCP Tools Available

### pipeline_state_inspector
```
curl -X POST "http://localhost:5001/mcp-tool-executor" -H "Content-Type: application/json" -d '{"tool": "pipeline_state_inspector", "params": {"pipeline_id": "PIPELINE_ID"}}'
```

### botify_simple_query  
```
curl -X POST "http://localhost:5001/mcp-tool-executor" -H "Content-Type: application/json" -d '{"tool": "botify_simple_query", "params": {"query": {"dimensions": ["url"], "metrics": []}, "username": "USERNAME", "project": "PROJECT", "analysis": "ANALYSIS"}}'
```

## 🌐 Key Direct Endpoints (Session-less Development)

- **Field Discovery**: `http://localhost:5001/trifecta/discover-fields?username=USERNAME&project=PROJECT&analysis=ANALYSIS`
- **Any Workflow Step**: `http://localhost:5001/trifecta/step_[STEP_NAME]?pipeline_id=PIPELINE_ID`
- **File Downloads**: `http://localhost:5001/download_file?path=downloads/trifecta/[USERNAME]/[PROJECT]/[ANALYSIS]/[FILENAME]`

## 🔍 Searchable Log Tokens

When checking logs, search for these unique tokens:
- `🔍 FINDER_TOKEN` - Specific feature tracking
- `🎯 TEMPLATE_VALIDATION` - Template field validation
- `🌐 API_CALL` - External API interactions  
- `📁 FILE_OPERATION` - File system operations
- `🚀 WORKFLOW_STEP` - Workflow progression

## 🔥 What This Unlocks

- 📊 **Full Pipeline State**: Current step, completed data, file status
- 🎯 **Field Discovery**: Available Botify fields for any project/analysis  
- 🔍 **Template Validation**: Check if your query templates match available data
- 🌐 **Direct Endpoint Testing**: Hit any workflow step without UI navigation
- 📁 **File System Transparency**: Complete visibility into downloads and structure
- 🔧 **API Call Recreation**: Python code generation for debugging

## 💯 The Radical Transparency Achievement

This system provides unprecedented debugging power:

- **Zero-Ceremony Session-less Development**: Any endpoint, any time, without UI navigation
- **AI-Powered Mid-Session Debugging**: Any AI can drop into any workflow with full context
- **Complete State Reconstruction**: From `pipeline_id` alone to full workflow understanding
- **3-Second Development Loop**: Make change → test endpoint → check logs
- **Searchable Log Token System**: Find exactly what you need with unique markers

**The Magic**: When you visit `/docs` through the redirect system, this entire bootstrap guide is automatically loaded into my conversation history, giving me instant knowledge of all transparency capabilities."""

    def __init__(self, app, pipulate, pipeline, db):
        logger.debug(f"DocumentationPlugin initialized with NAME: {self.NAME}")
        self.pipulate = pipulate
        wand = self.pipulate
        self._has_streamed = False

        # Dynamically discover all documentation files
        self.DOCS = self.discover_documentation_files()

        # Register routes for serving individual documents
        for doc_key, doc_info in self.DOCS.items():
            if doc_info.get('paginated'):
                # Generic routes for paginated documents - create proper async wrappers
                def make_toc_handler(dk):
                    async def handler(request):
                        return await self.serve_paginated_toc(request, dk)
                    return handler
                
                def make_page_handler(dk):
                    async def handler(request):
                        return await self.serve_paginated_page(request, dk, request.path_params['page_num'])
                    return handler
                
                # Register the routes with proper async handlers
                app.route(f'/docs/{doc_key}', methods=['GET'])(make_toc_handler(doc_key))
                app.route(f'/docs/{doc_key}/toc', methods=['GET'])(make_toc_handler(doc_key))
                app.route(f'/docs/{doc_key}/page/{{page_num}}', methods=['GET'])(make_page_handler(doc_key))
            else:
                # Standard document route
                app.route(f'/docs/{doc_key}', methods=['GET'])(self.serve_document)

        # Register route for documentation browser
        app.route('/docs', methods=['GET'])(self.serve_browser)

        # Register route for serving raw markdown content
        app.route('/docs/raw/{doc_key}', methods=['GET'])(self.serve_raw_markdown)

    def discover_documentation_files(self):
        """Dynamically discover all documentation files from training, rules, and blog drafts directories"""
        docs = {}

        # Get the project root directory dynamically
        # Start from the current file's directory and go up to find the project root
        current_file = Path(__file__).resolve()
        pipulate_root = current_file.parent.parent  # apps/050_documentation.py -> apps/ -> pipulate/
        
        # Verify we found the right directory by checking for key files
        if not (pipulate_root / 'server.py').exists():
            # Fallback: use current working directory if it contains server.py
            cwd = Path.cwd()
            if (cwd / 'server.py').exists():
                pipulate_root = cwd
            else:
                # Last resort: search up the directory tree
                search_path = current_file.parent
                while search_path != search_path.parent:
                    if (search_path / 'server.py').exists():
                        pipulate_root = search_path
                        break
                    search_path = search_path.parent
                else:
                    logger.warning("Could not find pipulate root directory - using current working directory")
                    pipulate_root = Path.cwd()
        
        logger.info(f"Using pipulate root directory: {pipulate_root}")

        # Scan training directory
        training_dir = pipulate_root / 'helpers/botify'
        if training_dir.exists():
            for file_path in training_dir.glob('*.md'):
                key, info = self.process_training_file(file_path)
                if key and info:
                    docs[key] = info

        # Scan cursor rules directory
        rules_dir = pipulate_root / '.cursor/rules'
        if rules_dir.exists():
            for file_path in rules_dir.glob('*.mdc'):
                key, info = self.process_rules_file(file_path)
                if key and info:
                    docs[key] = info

        # Scan considerations directory
        considerations_dir = pipulate_root / 'helpers/docs_sync/considerations'
        if considerations_dir.exists():
            for file_path in considerations_dir.glob('*.md'):
                key, info = self.process_consideration_file(file_path)
                if key and info:
                    docs[key] = info

        # Special case: Add README.md from project root
        readme_path = pipulate_root / 'README.md'
        if readme_path.exists():
            key, info = self.process_readme_file(readme_path)
            if key and info:
                docs[key] = info

        logger.info(f"Discovered {len(docs)} documentation files")
        return docs

    def process_training_file(self, file_path):
        """Process a training file and extract metadata"""
        filename = file_path.stem

        # Determine category and priority based on filename patterns
        category = 'training'
        priority = 100  # Default priority

        # Featured files get special treatment
        if 'ULTIMATE_PIPULATE_GUIDE' in filename:
            category = 'featured'
            if 'PART2' in filename:
                priority = 2
            elif 'PART3' in filename:
                priority = 3
            else:
                priority = 1  # Part 1
        elif 'QUICK_REFERENCE' in filename:
            category = 'featured'
            priority = 4
        elif 'botify' in filename and 'api' in filename:
            category = 'featured'
            priority = 5  # After Quick Reference

        # Generate title from filename or extract from file content
        title = self.generate_title_from_filename(filename)

        # Try to extract title and description from file content
        try:
            content = file_path.read_text(encoding='utf-8')
            extracted_title, description = self.extract_metadata_from_content(content, title)
            # Only use extracted title if we don't have a specific mapping for this filename
            if extracted_title and filename not in ['ULTIMATE_PIPULATE_GUIDE', 'ULTIMATE_PIPULATE_GUIDE_PART2', 'ULTIMATE_PIPULATE_GUIDE_PART3', 'QUICK_REFERENCE', 'botify_api_bootcamp', 'botify_api_examples', 'change_log']:
                title = extracted_title
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            description = f"Documentation file: {filename}"

        key = self.generate_key_from_filename(filename, 'training')

        # Detect paginated documents
        info = {
            'title': title,
            'file': str(file_path),
            'description': description,
            'category': category,
            'priority': priority,
            'filename': filename
        }
        
        # Add pagination metadata for long documents
        if ('botify' in filename and 'api' in filename) or filename == 'change_log':
            info['paginated'] = True
            info['separator'] = '-' * 80
            # Update title to indicate pagination
            if '(Paginated)' not in info['title']:
                info['title'] += ' (Paginated)'

        return key, info

    def process_rules_file(self, file_path):
        """Process a rules file and extract metadata"""
        filename = file_path.stem

        # Generate title from filename
        title = self.generate_title_from_filename(filename)

        # Try to extract title and description from file content
        try:
            content = file_path.read_text(encoding='utf-8')
            extracted_title, description = self.extract_metadata_from_content(content, title)
            if extracted_title:
                # For rules files with numeric prefixes, preserve the number when using extracted title
                if re.match(r'^\d+_', filename):
                    prefix_match = re.match(r'^(\d+)_', filename)
                    if prefix_match:
                        prefix = prefix_match.group(1)
                        title = f"{prefix} - {extracted_title}"
                    else:
                        title = extracted_title
                else:
                    title = extracted_title
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            description = f"Framework rule: {filename}"

        key = self.generate_key_from_filename(filename, 'rules')

        return key, {
            'title': title,
            'file': str(file_path),
            'description': description,
            'category': 'rules',
            'priority': self.get_rules_priority(filename),
            'filename': filename
        }

    def process_readme_file(self, file_path):
        """Process the README.md file and extract metadata"""
        filename = 'README'

        # Try to extract title and description from file content
        try:
            content = file_path.read_text(encoding='utf-8')
            extracted_title, description = self.extract_metadata_from_content(content, 'Project README')
            # Make it clear this is the README with emoji
            title = f"📄 README - {extracted_title}" if extracted_title else '📄 README - Project Documentation'
            
            # Check if README contains pagination separators
            separator = '-' * 80
            has_pagination = separator in content
            
            if has_pagination:
                title += ' (Paginated)'
                
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            title = '📄 README - Project Documentation'
            description = "Main project documentation and overview"
            content = ""
            has_pagination = False

        key = 'readme'

        info = {
            'title': title,
            'file': str(file_path),
            'description': description,
            'category': 'featured',  # Make it featured so it appears prominently
            'priority': 0,  # Give it highest priority (lowest number = highest priority)
            'filename': filename
        }
        
        # Add pagination metadata if README contains separators
        if has_pagination:
            info['paginated'] = True
            info['separator'] = '-' * 80

        return key, info

    def process_consideration_file(self, file_path):
        """Process a consideration file and extract metadata from YAML frontmatter"""
        filename = file_path.stem

        # Extract date from filename (YYYY-MM-DD-title format)
        import re
        date_match = re.match(r'^(\d{4}-\d{2}-\d{2})-(.+)', filename)
        if not date_match:
            logger.warning(f"Blog draft {filename} doesn't follow YYYY-MM-DD-title format")
            return None, None
        
        date_str = date_match.group(1)
        title_slug = date_match.group(2)

        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Parse YAML frontmatter
            frontmatter = {}
            yaml_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
            if yaml_match:
                yaml_content = yaml_match.group(1)
                # Simple YAML parsing for the fields we need
                for line in yaml_content.split('\n'):
                    line = line.strip()
                    if ':' in line and not line.startswith('#'):
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        # Handle list values like tags
                        if value.startswith('[') and value.endswith(']'):
                            value = value.strip('[]').replace(',', ' |')
                        if key in ['title', 'date', 'category', 'tags']:
                            frontmatter[key] = value

            # Use frontmatter title or generate from filename
            title = frontmatter.get('title', self.generate_title_from_filename(title_slug))
            
            # Add consideration indicator and date to title
            title = f"💭 {title} ({date_str})"
            
            # Generate description from content (skip frontmatter)
            content_without_frontmatter = content
            if yaml_match:
                content_without_frontmatter = content[yaml_match.end():]
            
            description = self.extract_consideration_description(content_without_frontmatter)
            
            # Add category and tags info to description
            if 'category' in frontmatter:
                description = f"[{frontmatter['category']}] {description}"
            
            # Calculate priority from date (newer posts get lower numbers = higher priority)
            try:
                from datetime import datetime
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                # Use negative timestamp to reverse sort order (newer first)
                priority = -int(date_obj.timestamp())
            except ValueError:
                priority = 999999  # Fallback for invalid dates

        except Exception as e:
            logger.warning(f"Could not process consideration file {file_path}: {e}")
            title = f"💭 {self.generate_title_from_filename(title_slug)} ({date_str})"
            description = f"Development consideration: {title_slug}"
            priority = 999999

        key = f"consideration_{filename.replace('-', '_')}"

        return key, {
            'title': title,
            'file': str(file_path),
            'description': description,
            'category': 'considerations',
            'priority': priority,
            'filename': filename,
            'date': date_str
        }

    def extract_consideration_description(self, content):
        """Extract a meaningful description from consideration content"""
        lines = content.split('\n')
        
        # Look for the first substantial paragraph after any headers
        for line in lines:
            line = line.strip()
            # Skip empty lines, headers, and code blocks
            if (line and 
                not line.startswith('#') and 
                not line.startswith('```') and 
                not line.startswith('---') and 
                not line.startswith('*') and  # Skip markdown emphasis/bullets
                len(line) > 30):
                # Clean up markdown and truncate
                clean_line = self._clean_description_text(line)
                return clean_line[:200] + ('...' if len(clean_line) > 200 else '')
        
        return "Development consideration exploring Pipulate architecture and design"

    def generate_title_from_filename(self, filename):
        """Generate a human-readable title from filename"""
        # For rules files, preserve numeric prefix in a nice format
        if filename.startswith(('00_', '01_', '02_', '03_', '04_', '05_', '06_', '07_', '08_', '09_')):
            match = re.match(r'^(\d+)_(.+)', filename)
            if match:
                prefix = match.group(1)
                rest = match.group(2)
                # Clean up the rest of the filename
                rest = re.sub(r'^[Xx][Xx]_', '', rest)
                # For rules files, return with formatted prefix
                title = f"{prefix} - {rest}"
            else:
                # Fallback - remove numeric prefixes and clean up
                title = re.sub(r'^\d+_', '', filename)
                title = re.sub(r'^[Xx][Xx]_', '', title)
        else:
            # For non-rules files, remove numeric prefixes and clean up
            title = re.sub(r'^\d+_', '', filename)
            title = re.sub(r'^[Xx][Xx]_', '', title)

        # Handle only special cases that can't be automatically determined
        # Most titles should be automatically extracted from file content or generated from filename
        title_mappings = {
            # Training files with specific formatting needs
            'ULTIMATE_PIPULATE_GUIDE': 'Ultimate Pipulate Guide - Part 1: Core Patterns',
            'ULTIMATE_PIPULATE_GUIDE_PART2': 'Ultimate Pipulate Guide - Part 2: Advanced Patterns',
            'ULTIMATE_PIPULATE_GUIDE_PART3': 'Ultimate Pipulate Guide - Part 3: Expert Mastery',
            'QUICK_REFERENCE': 'Quick Reference Card',
            # Paginated documents that need special suffixes
            'botify_api': 'Botify API Bootcamp (Paginated)',
            'botify_open_api': 'Botify Open API Swagger Examples (Paginated)',
            'change_log': 'Pipulate Development Changelog (Paginated)',
        }

        if filename in title_mappings:
            return title_mappings[filename]

        # Default: convert underscores to spaces and title case
        title = title.replace('_', ' ').title()
        return title

    def generate_key_from_filename(self, filename, category):
        """Generate a unique key for the document"""
        # Remove numeric prefixes and special characters
        clean_name = re.sub(r'^\d+_', '', filename)
        clean_name = re.sub(r'^[Xx][Xx]_', '', clean_name)
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', clean_name).lower()

        # Add category prefix to avoid collisions
        if category == 'training':
            return clean_name
        elif category == 'rules':
            return f"rule_{clean_name}"

        return clean_name

    def extract_metadata_from_content(self, content, default_title):
        """Extract title and description from file content"""
        lines = content.split('\n')
        title = default_title
        description = ""

        # Look for title in first few lines
        for i, line in enumerate(lines[:10]):
            line = line.strip()

            # Check for markdown headers
            if line.startswith('# '):
                title = line[2:].strip()
                # Clean up title
                title = re.sub(r'🚨\s*\*\*', '', title)
                title = re.sub(r'\*\*\s*🚨', '', title)
                title = title.replace('**', '').strip()
                break

            # Check for description patterns
            if line.startswith('## description:'):
                description = line[15:].strip()
                break

        # If no description found, look for first paragraph or summary
        if not description:
            for line in lines[:20]:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('```') and len(line) > 20:
                    description = line[:150] + ('...' if len(line) > 150 else '')
                    break

        # Fallback description
        if not description:
            if 'training' in str(content).lower():
                description = "Training guide and documentation"
            elif 'rule' in str(content).lower() or 'pattern' in str(content).lower():
                description = "Framework rules and patterns"
            else:
                description = "Documentation and guidelines"

        return title, description

    def get_rules_priority(self, filename):
        """Determine priority for rules files based on numeric prefix in filename"""
        import re
        
        # Extract numeric prefix from filename (e.g., "00" from "00_PIPULATE_MASTER_GUIDE")
        match = re.match(r'^(\d+)_', filename)
        if match:
            # Use the numeric prefix as priority (lower numbers = higher priority)
            return int(match.group(1))
        
        # For files without numeric prefixes, assign high priority numbers
        # This preserves the reading order implied by the filename numbering
        special_cases = {
            'meta_rule_routing': 999,
        }
        
        return special_cases.get(filename, 100)

    def get_rules_navigation(self, current_doc_key):
        """Get previous/next navigation for rules documents"""
        # Get all rules documents sorted by priority
        _, _, rules_docs, _, _ = self.get_categorized_docs()
        
        if not rules_docs:
            return None, None
        
        # Find current document index
        current_index = None
        for i, (key, info) in enumerate(rules_docs):
            if key == current_doc_key:
                current_index = i
                break
        
        if current_index is None:
            return None, None
        
        # Get previous and next documents
        prev_doc = rules_docs[current_index - 1] if current_index > 0 else None
        next_doc = rules_docs[current_index + 1] if current_index < len(rules_docs) - 1 else None
        
        return prev_doc, next_doc

    def get_considerations_navigation(self, current_doc_key):
        """Get previous/next navigation for consideration documents"""
        # Get all consideration documents sorted by priority (newest first)
        _, _, _, _, consideration_docs = self.get_categorized_docs()
        
        if not consideration_docs:
            return None, None
        
        # Find current document index
        current_index = None
        for i, (key, info) in enumerate(consideration_docs):
            if key == current_doc_key:
                current_index = i
                break
        
        if current_index is None:
            return None, None
        
        # Get previous and next documents
        prev_doc = consideration_docs[current_index - 1] if current_index > 0 else None
        next_doc = consideration_docs[current_index + 1] if current_index < len(consideration_docs) - 1 else None
        
        return prev_doc, next_doc

    def markdown_to_html(self, markdown_content):
        """Convert markdown to HTML with proper Markdown semantics"""
        import html

        # Step 1: Protect code blocks by storing them and replacing with placeholders
        code_blocks = []
        placeholder_pattern = "CODEBLOCK_PLACEHOLDER_{}"

        def store_code_block(match):
            code_blocks.append(match.group(0))
            return placeholder_pattern.format(len(code_blocks) - 1)

        # Find and store all code blocks (any language)
        content = re.sub(r'```[a-zA-Z]*\s*\n.*?```', store_code_block, markdown_content, flags=re.DOTALL)

        # Step 2: Process block-level elements line by line
        lines = content.split('\n')
        processed_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Horizontal rules (must come before headers to avoid conflicts)
            if re.match(r'^-{3,}$', stripped) or re.match(r'^\*{3,}$', stripped) or re.match(r'^_{3,}$', stripped):
                processed_lines.append('<hr style="border: none; height: 2px; background: linear-gradient(to right, #e9ecef, #0066cc, #e9ecef); margin: 30px 0; border-radius: 1px;">')
                i += 1

            # Headers
            elif stripped.startswith('# '):
                header_text = self._remove_html_comments(stripped[2:].strip())
                header_id = self._slugify(header_text)
                processed_header = self._process_inline_markdown(header_text)
                processed_lines.append(f'<h1 id="{header_id}">{processed_header}</h1>')
                i += 1
            elif stripped.startswith('## '):
                header_text = self._remove_html_comments(stripped[3:].strip())
                header_id = self._slugify(header_text)
                processed_header = self._process_inline_markdown(header_text)
                processed_lines.append(f'<h2 id="{header_id}">{processed_header}</h2>')
                i += 1
            elif stripped.startswith('### '):
                header_text = self._remove_html_comments(stripped[4:].strip())
                header_id = self._slugify(header_text)
                processed_header = self._process_inline_markdown(header_text)
                processed_lines.append(f'<h3 id="{header_id}">{processed_header}</h3>')
                i += 1
            elif stripped.startswith('#### '):
                header_text = self._remove_html_comments(stripped[5:].strip())
                header_id = self._slugify(header_text)
                processed_header = self._process_inline_markdown(header_text)
                processed_lines.append(f'<h4 id="{header_id}">{processed_header}</h4>')
                i += 1

            # Blockquotes
            elif stripped.startswith('> '):
                blockquote_lines = []
                while i < len(lines) and lines[i].strip().startswith('> '):
                    # Remove the '> ' prefix and collect the content
                    quote_content = lines[i].strip()[2:]
                    blockquote_lines.append(quote_content)
                    i += 1

                # Process the blockquote content as markdown (recursively)
                blockquote_content = '\n'.join(blockquote_lines)
                processed_blockquote = self._process_inline_markdown(blockquote_content)
                processed_lines.append(f'<blockquote>{processed_blockquote}</blockquote>')

            # Unordered lists
            elif stripped.startswith('- ') or stripped.startswith('* ') or stripped.startswith('+ '):
                list_items = []
                while i < len(lines):
                    current_line = lines[i].strip()
                    if current_line.startswith('- ') or current_line.startswith('* ') or current_line.startswith('+ '):
                        item_content = current_line[2:].strip()
                        # Handle multi-line list items
                        i += 1
                        while i < len(lines) and lines[i].startswith('  ') and lines[i].strip():
                            item_content += ' ' + lines[i].strip()
                            i += 1
                        list_items.append(self._process_inline_markdown(item_content))
                    else:
                        break

                if list_items:
                    list_html = '<ul>' + ''.join(f'<li>{item}</li>' for item in list_items) + '</ul>'
                    processed_lines.append(list_html)

            # Ordered lists
            elif re.match(r'^\d+\. ', stripped):
                list_items = []
                while i < len(lines):
                    current_line = lines[i].strip()
                    if re.match(r'^\d+\. ', current_line):
                        item_content = re.sub(r'^\d+\. ', '', current_line)
                        # Handle multi-line list items
                        i += 1
                        while i < len(lines) and lines[i].startswith('  ') and lines[i].strip():
                            item_content += ' ' + lines[i].strip()
                            i += 1
                        list_items.append(self._process_inline_markdown(item_content))
                    else:
                        break

                if list_items:
                    list_html = '<ol>' + ''.join(f'<li>{item}</li>' for item in list_items) + '</ol>'
                    processed_lines.append(list_html)

            # Tables (pipe-delimited)
            elif '|' in stripped and len(stripped.split('|')) >= 3:
                # Look ahead to see if this is a table
                table_lines = []
                table_start = i

                # Collect potential table lines
                while i < len(lines):
                    current_line = lines[i].strip()
                    if not current_line:
                        break
                    if '|' in current_line and len(current_line.split('|')) >= 3:
                        table_lines.append(current_line)
                        i += 1
                    else:
                        break

                # Check if we have a valid table (at least header + separator + data)
                if len(table_lines) >= 2:
                    # Check if second line is a separator (contains dashes and pipes)
                    second_line = table_lines[1]
                    if re.match(r'^\s*\|[\s\-\|:]+\|\s*$', second_line):
                        # Process as table
                        table_html = self._process_table(table_lines)
                        processed_lines.append(table_html)
                    else:
                        # Not a table, backtrack and process as regular lines
                        i = table_start
                        processed_lines.append(line)
                        i += 1
                else:
                    # Not enough lines for a table, backtrack
                    i = table_start
                    processed_lines.append(line)
                    i += 1

            # Empty lines (potential paragraph breaks)
            elif not stripped:
                processed_lines.append('')
                i += 1

            # Code block placeholders (preserve as-is)
            elif re.match(r'^CODEBLOCK_PLACEHOLDER_\d+$', stripped):
                processed_lines.append(line)
                i += 1

            # Regular text lines (will be grouped into paragraphs later)
            else:
                processed_lines.append(line)
                i += 1

        # Step 3: Group consecutive non-empty, non-HTML lines into paragraphs
        final_lines = []
        i = 0

        while i < len(processed_lines):
            line = processed_lines[i]
            stripped = line.strip()

            # If it's an HTML element or empty line, keep as-is
            if not stripped or stripped.startswith('<') or re.match(r'^CODEBLOCK_PLACEHOLDER_\d+$', stripped):
                final_lines.append(line)
                i += 1
            else:
                # Start collecting paragraph content
                paragraph_lines = []
                while i < len(processed_lines):
                    current_line = processed_lines[i]
                    current_stripped = current_line.strip()

                    # Stop if we hit an empty line, HTML element, or placeholder
                    if (not current_stripped or
                        current_stripped.startswith('<') or
                        re.match(r'^CODEBLOCK_PLACEHOLDER_\d+$', current_stripped)):
                        break

                    # Handle hard line breaks (two spaces at end of line)
                    if current_line.rstrip().endswith('  '):
                        paragraph_lines.append(current_line.rstrip()[:-2] + '<br>')
                    else:
                        paragraph_lines.append(current_line.strip())
                    i += 1

                if paragraph_lines:
                    # Join lines with spaces and process inline markdown
                    paragraph_content = ' '.join(paragraph_lines)
                    processed_paragraph = self._process_inline_markdown(paragraph_content)
                    final_lines.append(f'<p>{processed_paragraph}</p>')

        # Step 4: Restore code blocks
        result = '\n'.join(final_lines)
        for i, code_block in enumerate(code_blocks):
            placeholder = placeholder_pattern.format(i)
            processed_block = self.process_code_block(code_block)
            # Use a more precise replacement to avoid partial matches
            if placeholder in result:
                result = result.replace(placeholder, processed_block, 1)  # Replace only first occurrence

        return result

    def _remove_html_comments(self, text):
        """Remove HTML comments from text"""
        import re
        # Remove HTML comments like <!-- key: pipeline-workflows -->
        return re.sub(r'<!--.*?-->', '', text).strip()

    def _clean_description_text(self, text):
        """Clean markdown syntax from description text for TOC display"""
        import re
        
        # Remove images ![alt](src) - Replace with just the alt text or remove entirely
        text = re.sub(r'!\[([^\]]*)\]\([^)]*\)', lambda m: m.group(1) if m.group(1).strip() else '', text)
        
        # Remove bold **text** -> text
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        
        # Remove italic *text* -> text  
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        
        # Remove inline code `text` -> text
        text = re.sub(r'`([^`]*)`', r'\1', text)
        
        # Remove links [text](url) -> text
        text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
        
        # Clean up multiple spaces and return
        return ' '.join(text.split()).strip()

    def _slugify(self, text):
        """Convert text to URL-friendly slug for header IDs"""
        import re
        # Remove HTML comments first
        text = self._remove_html_comments(text)
        # Remove HTML tags if any
        text = re.sub(r'<[^>]+>', '', text)
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', text.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')

    def _process_inline_markdown(self, text):
        """Process inline markdown elements (bold, italic, code, alerts, links)"""
        import html

        # Escape HTML first
        text = html.escape(text)

        # Alert boxes (process before bold/italic to avoid conflicts)
        # Handle patterns with trailing sirens: 🚨 **text** 🚨
        text = re.sub(r'🚨 \*\*(.*?)\*\* 🚨', r'<div class="alert alert-critical"><strong>🚨 \1 🚨</strong></div>', text)
        text = re.sub(r'✅ \*\*(.*?)\*\* ✅', r'<div class="alert alert-success"><strong>✅ \1 ✅</strong></div>', text)
        text = re.sub(r'❌ \*\*(.*?)\*\* ❌', r'<div class="alert alert-error"><strong>❌ \1 ❌</strong></div>', text)

        # Handle patterns without trailing emoji: 🚨 **text**
        text = re.sub(r'🚨 \*\*(.*?)\*\*', r'<div class="alert alert-critical"><strong>🚨 \1</strong></div>', text)
        text = re.sub(r'✅ \*\*(.*?)\*\*', r'<div class="alert alert-success"><strong>✅ \1</strong></div>', text)
        text = re.sub(r'❌ \*\*(.*?)\*\*', r'<div class="alert alert-error"><strong>❌ \1</strong></div>', text)

        # Markdown links [text](url) - process before inline code to avoid conflicts
        def process_link(match):
            link_text = match.group(1)
            link_url = match.group(2)
            # Check if it's a relative URL (starts with /) or absolute URL
            if link_url.startswith('/') or link_url.startswith('http'):
                return f'<a href="{link_url}">{link_text}</a>'
            else:
                # For other URLs, assume they need http:// prefix if not present
                if not link_url.startswith(('http://', 'https://', 'mailto:', 'ftp://')):
                    link_url = f'http://{link_url}'
                return f'<a href="{link_url}">{link_text}</a>'

        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', process_link, text)

        # Inline code (process before bold/italic to avoid conflicts)
        text = re.sub(r'`([^`]+)`', r'<code class="language-text">\1</code>', text)

        # Bold and italic
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)

        return text

    def _process_table(self, table_lines):
        """Process markdown table lines into HTML table"""
        if len(table_lines) < 2:
            return ''

        # Parse header row
        header_row = table_lines[0].strip()
        header_cells = [cell.strip() for cell in header_row.split('|') if cell.strip()]

        # Skip separator row (table_lines[1])

        # Parse data rows
        data_rows = []
        for line in table_lines[2:]:
            if line.strip():
                cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                # Pad cells to match header length
                while len(cells) < len(header_cells):
                    cells.append('')
                data_rows.append(cells[:len(header_cells)])  # Trim excess cells

        # Build HTML table
        html_parts = ['<table>']

        # Header
        html_parts.append('<thead>')
        html_parts.append('<tr>')
        for cell in header_cells:
            processed_cell = self._process_inline_markdown(cell)
            html_parts.append(f'<th>{processed_cell}</th>')
        html_parts.append('</tr>')
        html_parts.append('</thead>')

        # Body
        if data_rows:
            html_parts.append('<tbody>')
            for row in data_rows:
                html_parts.append('<tr>')
                for cell in row:
                    processed_cell = self._process_inline_markdown(cell)
                    html_parts.append(f'<td>{processed_cell}</td>')
                html_parts.append('</tr>')
            html_parts.append('</tbody>')

        html_parts.append('</table>')
        return ''.join(html_parts)

    def process_code_block(self, code_block):
        """Process a single code block and convert to HTML with proper escaping"""
        import html

        # Extract language and content - preserve exact whitespace
        match = re.match(r'```([a-zA-Z]*)\s*\n(.*?)```', code_block, flags=re.DOTALL)
        if match:
            language = match.group(1) or 'text'
            content = match.group(2)
            # Remove only the final newline if present to prevent extra spacing
            if content.endswith('\n'):
                content = content[:-1]
            # Properly escape HTML in code content while preserving all whitespace
            escaped_content = html.escape(content)
            return f'<pre><code class="language-{language}">{escaped_content}</code></pre>'
        return html.escape(code_block)

    def get_categorized_docs(self):
        """Get documents organized by category with proper sorting"""
        featured_docs = []
        training_docs = []
        rules_docs = []
        paginated_docs = []
        consideration_docs = []

        for key, info in self.DOCS.items():
            # Check if document is paginated first
            if info.get('paginated', False):
                paginated_docs.append((key, info))
            else:
                category = info.get('category', 'other')
                if category == 'featured':
                    featured_docs.append((key, info))
                elif category == 'training':
                    training_docs.append((key, info))
                elif category == 'rules':
                    rules_docs.append((key, info))
                elif category == 'considerations':
                    consideration_docs.append((key, info))

        # Sort by priority, then by title
        featured_docs.sort(key=lambda x: (x[1].get('priority', 999), x[1]['title']))
        training_docs.sort(key=lambda x: x[1]['title'])
        rules_docs.sort(key=lambda x: (x[1].get('priority', 999), x[1]['title']))
        paginated_docs.sort(key=lambda x: (x[1].get('priority', 999), x[1]['title']))
        # Considerations sorted by priority (which is negative timestamp, so newer first)
        consideration_docs.sort(key=lambda x: (x[1].get('priority', 999), x[1]['title']))

        return featured_docs, training_docs, rules_docs, paginated_docs, consideration_docs

    async def serve_browser(self, request):
        """Serve the documentation browser with tree view"""

        # Default docs split sizes - localStorage will override if available

        # Get categorized documents
        featured_docs, training_docs, rules_docs, paginated_docs, consideration_docs = self.get_categorized_docs()

        # Check for category filter
        category = request.query_params.get('category', 'all')

        # Filter documents based on category
        if category == 'featured':
            title = "🌟 Featured Guides"
            filtered_featured = featured_docs
            filtered_training = []
            filtered_rules = []
            filtered_paginated = []
            filtered_considerations = []
            welcome_text = "Comprehensive guides and tutorials for getting started with Pipulate."
        elif category == 'training':
            title = "📖 Training Files"
            filtered_featured = []
            filtered_training = training_docs
            filtered_rules = []
            filtered_paginated = []
            filtered_considerations = []
            welcome_text = "Training materials and learning resources for mastering Pipulate workflows."
        elif category == 'rules':
            title = "⚙️ Framework Rules"
            filtered_featured = []
            filtered_training = []
            filtered_rules = rules_docs
            filtered_paginated = []
            filtered_considerations = []
            welcome_text = "Framework rules and coding standards for Pipulate development."
        elif category == 'paginated':
            title = "📚 Paginated Documents"
            filtered_featured = []
            filtered_training = []
            filtered_rules = []
            filtered_paginated = paginated_docs
            filtered_considerations = []
            welcome_text = "Paginated documents for quick reference and learning."
        elif category == 'considerations':
            title = "💭 Development Considerations"
            filtered_featured = []
            filtered_training = []
            filtered_rules = []
            filtered_paginated = []
            filtered_considerations = consideration_docs
            welcome_text = "Development considerations exploring Pipulate architecture, design decisions, and work-in-progress thoughts."
        else:
            title = "📚 All Documentation"
            filtered_featured = featured_docs
            filtered_training = training_docs
            filtered_rules = rules_docs
            filtered_paginated = paginated_docs
            filtered_considerations = consideration_docs
            welcome_text = "Complete documentation library for Pipulate. Start with Featured Guides for comprehensive learning."

        # Create tree view HTML with filtered content
        tree_html = self.create_tree_view(filtered_featured, filtered_training, filtered_rules, filtered_paginated, filtered_considerations)

        # Create breadcrumb navigation for filtered views
        breadcrumb = ""
        if category != 'all':
            breadcrumb = f'<p style="margin-bottom: 1rem; font-size: 0.9em;"><a href="/docs" style="color: #0066cc; text-decoration: underline;">📚 All Documentation</a> → <strong>{title}</strong></p>'

        # Create stats content - either filtered or all with links
        if category == 'all':
            stats_content = f"""
                <a href="/docs" cls="nav-link-block">📊 {len(self.DOCS)} documents discovered</a>
                <a href="/docs?category=featured" cls="nav-link-block">🌟 {len(featured_docs)} featured guides</a>
                <a href="/docs?category=considerations" cls="nav-link-block">💭 {len(consideration_docs)} considerations</a>
                <a href="/docs?category=training" cls="nav-link-block">📖 {len(training_docs)} training files</a>
                <a href="/docs?category=rules" cls="nav-link-block">⚙️ {len(rules_docs)} framework rules</a>
                <a href="/docs?category=paginated" cls="nav-link-block">📚 {len(paginated_docs)} paginated documents</a>
                <hr style="margin: 15px 0; border: none; border-top: 1px solid #e9ecef;">
                <div style="font-weight: bold; margin-bottom: 8px; color: #495057; font-size: 0.9em;">🌐 PUBLIC DOCS</div>
                <a href="https://pipulate.com/" target="_blank" cls="nav-link-block">🏠 Pipulate.com</a>
                <a href="https://pipulate.com/documentation/" target="_blank" cls="nav-link-block">📚 Official Documentation</a>
                <a href="https://pipulate.com/development/" target="_blank" cls="nav-link-block">👨‍💻 1-Pager Development Guide</a>
                <a href="https://pipulate.com/guide/" target="_blank" cls="nav-link-block">📖 Paginated Guide</a>
                <a href="https://pypi.org/project/pipulate/" target="_blank" cls="nav-link-block">📦 PyPI Package</a>
                <a href="https://github.com/miklevin/pipulate" target="_blank" cls="nav-link-block">🐙 GitHub Repository</a>
            """
        else:
            # Show count for current category only
            if category == 'featured':
                count_text = f"🌟 {len(featured_docs)} featured guides"
            elif category == 'training':
                count_text = f"📖 {len(training_docs)} training files"
            elif category == 'rules':
                count_text = f"⚙️ {len(rules_docs)} framework rules"
            elif category == 'paginated':
                count_text = f"📚 {len(paginated_docs)} paginated documents"
            elif category == 'considerations':
                count_text = f"💭 {len(consideration_docs)} considerations"

            stats_content = f'<div style="font-weight: bold; font-size: 1.1em;">{count_text}</div>'

        page_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title} - Pipulate Documentation</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <!-- Prism CSS -->
    <link href="/assets/css/prism.css" rel="stylesheet" />

    <!-- Tree view styles -->
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 0;
            background: #f8f9fa;
            height: 100vh;
            overflow: hidden;
        }}

        .container {{
            height: 100vh;
            display: flex;
        }}

        .sidebar {{
            background: #fff;
            border-right: 1px solid #e9ecef;
            overflow-y: auto;
            padding: 20px;
            /* Let Split.js control the width */
        }}

        .content {{
            background: #fff;
            overflow-y: auto;
            padding: 30px;
            /* Let Split.js control the width */
        }}

        /* Split.js styles */
        .gutter {{
            background-color: #eee;
            background-repeat: no-repeat;
            background-position: 50%;
        }}

        .gutter.gutter-horizontal {{
            background-image: url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUAAAAeCAYAAADkftS9AAAAIklEQVQoU2M4c+YMw+46L/5/FQMdQCvkZZqkIBdqQiOr6QoAmKYa/elSXJQAAAAASUVORK5CYII=');
            cursor: col-resize;
            width: 10px;
        }}

        .tree {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}

        .tree-category {{
            margin-bottom: 20px;
        }}

        .tree-category > .tree-label {{
            font-weight: bold;
            color: #495057;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
            display: block;
        }}

        .tree-item {{
            margin: 4px 0;
        }}

        .tree-link {{
            display: block;
            padding: 8px 12px;
            color: #0066cc;
            text-decoration: none;
            border-radius: 4px;
            transition: background-color 0.2s;
        }}

        .tree-link:hover {{
            background-color: #f8f9fa;
            text-decoration: none;
        }}

        .tree-link.featured {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            font-weight: 500;
        }}

        .tree-link.featured:hover {{
            background-color: #ffeaa7;
        }}

        .tree-link.paginated {{
            background-color: #e3f2fd;
            border-left: 4px solid #2196f3;
            font-weight: 500;
        }}

        .tree-link.paginated:hover {{
            background-color: #bbdefb;
        }}

        .tree-link.consideration {{
            background-color: #f3e5f5;
            border-left: 4px solid #9c27b0;
            font-weight: 500;
        }}

        .tree-link.consideration:hover {{
            background-color: #e1bee7;
        }}

        .tree-description {{
            font-size: 0.8em;
            color: #6c757d;
            margin-top: 2px;
        }}

        .welcome {{
            text-align: center;
            color: #6c757d;
            margin-top: 100px;
        }}

        .welcome h2 {{
            color: #495057;
        }}

        .stats {{
            background: #e9ecef;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
            font-size: 0.9em;
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            .container {{
                flex-direction: column;
            }}

            .sidebar {{
                border-right: none;
                border-bottom: 1px solid #e9ecef;
                max-height: 200px;
                flex: 0 0 auto;
            }}
            
            .content {{
                flex: 1;
            }}
            
            /* Hide split gutters on mobile */
            .gutter {{
                display: none !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <h3>{title}</h3>
            <div class="stats">
                {stats_content}
            </div>
            {tree_html}
        </div>
        <div class="content">
            {breadcrumb}
            <div class="welcome">
                <h2>{title}</h2>
                <p>{welcome_text}</p>
                <p><em>Documentation is automatically discovered from training/ and .cursor/rules/ directories.</em></p>
                {self.get_bootstrap_instructions() if category == 'all' else ''}
            </div>
        </div>
    </div>

    <!-- Split.js and Initialization -->
    <script src="/assets/js/split.js"></script>
    <script src="/assets/init.js"></script>
    
    <!-- Prism JS -->
    <script src="/assets/js/prism.js"></script>
    
    <!-- Initialize Documentation Browser Splitter -->
    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            // Use localStorage-based splitter with docs context
            if (typeof window.initializePipulateSplitter === 'function') {{
                window.initializePipulateSplitter(['.sidebar', '.content'], {{
                    sizes: [25, 75],  // Default sizes - localStorage will override if available
                    minSize: [200, 400], 
                    gutterSize: 10,
                    cursor: 'col-resize',
                    context: 'docs'
                }});
            }} else {{
                console.error('initializePipulateSplitter not available');
            }}
        }});
    </script>
</body>
</html>"""

        # 🏗️ ARCHITECTURAL: Custom HTML pattern (see line 1274 for full details)
        return HTMLResponse(page_html)

    def get_bootstrap_instructions(self):
        """Generate AI assistant bootstrap instructions for common scenarios"""
        return """
        <div style="margin-top: 2rem; padding: 1.5rem; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #0066cc;">
            <h3 style="margin: 0 0 1rem 0; color: #495057; font-size: 1.1em;">🤖 AI Assistant Bootstrap Instructions</h3>
            <p style="margin: 0 0 1rem 0; color: #6c757d; font-size: 0.9em;">
                <strong>Lost Context?</strong> Use these magic phrases to instantly restore full workflow transparency:
            </p>
            
            <!-- Common Scenarios -->
            <div cls="mb-lg">
                <h4 cls="section-heading">🎯 <strong>Most Common Bootstrap</strong></h4>
                <div style="background: #fff; padding: 1rem; border-radius: 4px; font-family: monospace; font-size: 0.85em; border: 1px solid #dee2e6;">
                    "I need help with my Pipulate workflow. My pipeline_id is [PIPELINE_ID].<br>
                    Please use the pipeline_state_inspector MCP tool to grab my complete workflow state,<br>
                    then tell me what you found and how you can help."
                </div>
                <div style="margin-top: 0.5rem; padding: 0.75rem; background: #e3f2fd; border-radius: 4px; font-size: 0.85em; color: #1976d2;">
                    💡 <strong>Pro Tip:</strong> Your pipeline_id appears in the URL bar or forms when using workflows.
                </div>
            </div>

            <div cls="mb-lg">
                <h4 cls="section-heading">🔍 <strong>Mid-Session Debugging</strong></h4>
                <div style="background: #fff; padding: 1rem; border-radius: 4px; font-family: monospace; font-size: 0.85em; border: 1px solid #dee2e6;">
                    "My trifecta workflow is stuck at [STEP_NAME]. Pipeline: [PIPELINE_ID].<br>
                    Please inspect my pipeline state and check the logs for errors."
                </div>
            </div>



            <!-- Power User Section -->
            <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid #dee2e6;">
                <h4 cls="section-heading">⚡ <strong>Power User: Direct MCP Call</strong></h4>
                <div style="background: #fff; padding: 1rem; border-radius: 4px; font-family: monospace; font-size: 0.85em; border: 1px solid #dee2e6;">
                    curl -X POST "http://localhost:5001/mcp-tool-executor" \\<br>
                    &nbsp;&nbsp;-H "Content-Type: application/json" \\<br>
                    &nbsp;&nbsp;-d '{"tool": "pipeline_state_inspector", "params": {"pipeline_id": "YOUR_PIPELINE_ID"}}'
                </div>
            </div>

            <!-- Key Capabilities -->
            <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid #dee2e6;">
                <h4 cls="section-heading">🔥 <strong>What This Unlocks</strong></h4>
                <ul style="margin: 0.5rem 0 0 1.2rem; padding: 0; color: #6c757d; font-size: 0.9em;">
                    <li>📊 <strong>Full Pipeline State</strong>: Current step, completed data, file status</li>
                    <li>🎯 <strong>Field Discovery</strong>: Available Botify fields for any project/analysis</li>
                    <li>🔍 <strong>Template Validation</strong>: Check if your query templates match available data</li>
                    <li>🌐 <strong>Direct Endpoint Testing</strong>: Hit any workflow step without UI navigation</li>
                    <li>📁 <strong>File System Transparency</strong>: Complete visibility into downloads and structure</li>
                    <li>🔧 <strong>API Call Recreation</strong>: Python code generation for debugging</li>
                </ul>
            </div>
        </div>
        """

    def get_bootstrap_instructions_markdown(self):
        """Generate markdown version of bootstrap instructions for LLM conversation history"""
        return """
# 🤖 AI Assistant Bootstrap Instructions

**Lost Context?** Use these magic phrases to instantly restore full workflow transparency:

## 🎯 Most Common Bootstrap

```
"I need help with my Pipulate workflow. My pipeline_id is [PIPELINE_ID].
Please use the pipeline_state_inspector MCP tool to grab my complete workflow state,
then tell me what you found and how you can help."
```

💡 **Pro Tip:** Your pipeline_id appears in the URL bar or forms when using workflows.

## 🔍 Mid-Session Debugging

```
"My trifecta workflow is stuck at [STEP_NAME]. Pipeline: [PIPELINE_ID].
Please inspect my pipeline state and check the logs for errors."
```

## 📁 File/Data Investigation

```
"I have data at downloads/trifecta/[USERNAME]/[PROJECT]/[ANALYSIS]/.
Please analyze what files exist and help me understand the data structure."
```

💡 **Example:** "I have data at downloads/trifecta/uhnd-com/uhnd.com-demo-account/20250616/. Please analyze what files exist."

## 🌐 API/Template Issues

```
"My Botify API call failed for [USERNAME]/[PROJECT]/[ANALYSIS].
Please use the discover-fields endpoint to check available fields
and validate my template configuration."
```

💡 **Example:** "My Botify API call failed for uhnd-com/uhnd.com-demo-account/20250616. Please discover available fields."

## ⚡ Power User: Direct MCP Call

```bash
curl -X POST "http://localhost:5001/mcp-tool-executor" \
  -H "Content-Type: application/json" \
  -d '{"tool": "pipeline_state_inspector", "params": {"pipeline_id": "YOUR_PIPELINE_ID"}}'
```

## 🚀 Quick Transparency Tools

- **Demo Field Discovery**: http://localhost:5001/trifecta/discover-fields/uhnd-com/uhnd.com-demo-account/20250616
- **Start Trifecta Workflow**: http://localhost:5001/trifecta

## 🔥 What This Unlocks

- 📊 **Full Pipeline State**: Current step, completed data, file status
- 🎯 **Field Discovery**: Available Botify fields for any project/analysis  
- 🔍 **Template Validation**: Check if your query templates match available data
- 🌐 **Direct Endpoint Testing**: Hit any workflow step without UI navigation
- 📁 **File System Transparency**: Complete visibility into downloads and structure
- 🔧 **API Call Recreation**: Python code generation for debugging

## 💯 The Radical Transparency Achievement

This system provides unprecedented debugging power:

- **Zero-Ceremony Session-less Development**: Any endpoint, any time, without UI navigation
- **AI-Powered Mid-Session Debugging**: Any AI can drop into any workflow with full context
- **Complete State Reconstruction**: From `pipeline_id` alone to full workflow understanding
- **3-Second Development Loop**: Make change → test endpoint → check logs
- **Searchable Log Token System**: Find exactly what you need with unique markers

**The Magic**: When you visit `/docs` through the redirect system, this entire bootstrap guide is automatically loaded into my conversation history, giving me instant knowledge of all transparency capabilities.
        """

    def get_endpoint_message(self):
        """Generate the endpoint message for display to user (without bootstrap instructions)"""
        # Bootstrap instructions are now handled via TRAINING_PROMPT for silent addition to conversation history
        return self.ENDPOINT_MESSAGE

    def clean_description_for_nav(self, description):
        """Clean markdown from descriptions for navigation display"""
        if not description:
            return ""
        
        # Remove markdown images
        description = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', description)
        
        # Remove markdown links but keep text
        description = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', description)
        
        # Remove bold/italic markdown
        description = re.sub(r'\*\*([^*]+)\*\*', r'\1', description)
        description = re.sub(r'\*([^*]+)\*', r'\1', description)
        
        # Remove code backticks
        description = re.sub(r'`([^`]+)`', r'\1', description)
        
        # Remove blockquote markers
        description = re.sub(r'^>\s*', '', description, flags=re.MULTILINE)
        
        # Convert HTML entities
        description = description.replace('&gt;', '>')
        description = description.replace('&lt;', '<')
        description = description.replace('&amp;', '&')
        
        # Truncate if too long
        if len(description) > 150:
            description = description[:147] + "..."
        
        return description.strip()

    def create_tree_view(self, featured_docs, training_docs, rules_docs, paginated_docs, consideration_docs):
        """Create the tree view HTML structure"""
        html_parts = []

        # Featured section
        if featured_docs:
            html_parts.append('<div class="tree-category" id="featured">')
            html_parts.append('<span class="tree-label">🌟 FEATURED GUIDES</span>')
            html_parts.append('<ul class="tree">')
            for key, info in featured_docs:
                html_parts.append(f'''
                    <li class="tree-item">
                        <a href="/docs/{key}" class="tree-link featured">
                            {info["title"]}
                        </a>
                        <div class="tree-description">{self.clean_description_for_nav(info["description"])}</div>
                    </li>
                ''')
            html_parts.append('</ul>')
            html_parts.append('</div>')

        # Paginated section
        if paginated_docs:
            html_parts.append('<div class="tree-category" id="paginated">')
            html_parts.append('<span class="tree-label">📚 PAGINATED DOCUMENTS</span>')
            html_parts.append('<ul class="tree">')
            for key, info in paginated_docs:
                html_parts.append(f'''
                    <li class="tree-item">
                        <a href="/docs/{key}" class="tree-link paginated">
                            {info["title"]}
                        </a>
                        <div class="tree-description">{self.clean_description_for_nav(info["description"])}</div>
                    </li>
                ''')
            html_parts.append('</ul>')
            html_parts.append('</div>')

        # Rules section (moved to third position)
        if rules_docs:
            html_parts.append('<div class="tree-category" id="rules">')
            html_parts.append('<span class="tree-label">⚙️ FRAMEWORK RULES</span>')
            html_parts.append('<ul class="tree">')
            for key, info in rules_docs:
                html_parts.append(f'''
                    <li class="tree-item">
                        <a href="/docs/{key}" class="tree-link">
                            {info["title"]}
                        </a>
                        <div class="tree-description">{self.clean_description_for_nav(info["description"])}</div>
                    </li>
                ''')
            html_parts.append('</ul>')
            html_parts.append('</div>')

        # Training section (moved to fourth position)
        if training_docs:
            html_parts.append('<div class="tree-category" id="training">')
            html_parts.append('<span class="tree-label">📖 TRAINING GUIDES</span>')
            html_parts.append('<ul class="tree">')
            for key, info in training_docs:
                html_parts.append(f'''
                    <li class="tree-item">
                        <a href="/docs/{key}" class="tree-link">
                            {info["title"]}
                        </a>
                        <div class="tree-description">{self.clean_description_for_nav(info["description"])}</div>
                    </li>
                ''')
            html_parts.append('</ul>')
            html_parts.append('</div>')

        # Considerations section (positioned at bottom for sequential reading)
        if consideration_docs:
            html_parts.append('<div class="tree-category" id="considerations">')
            html_parts.append('<span class="tree-label">💭 DEVELOPMENT CONSIDERATIONS</span>')
            html_parts.append('<ul class="tree">')
            for key, info in consideration_docs:
                html_parts.append(f'''
                    <li class="tree-item">
                        <a href="/docs/{key}" class="tree-link consideration">
                            {info["title"]}
                        </a>
                        <div class="tree-description">{self.clean_description_for_nav(info["description"])}</div>
                    </li>
                ''')
            html_parts.append('</ul>')
            html_parts.append('</div>')

        return ''.join(html_parts)

    async def serve_raw_markdown(self, request):
        """Serve raw markdown content for copying"""
        doc_key = request.path_params.get('doc_key') or request.url.path.split('/')[-1]

        if doc_key not in self.DOCS:
            return HTMLResponse("Document not found", status_code=404)

        doc_info = self.DOCS[doc_key]
        file_path = Path(doc_info['file'])

        if not file_path.exists():
            return HTMLResponse("File not found", status_code=404)

        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Strip YAML frontmatter from .mdc files
            if file_path.suffix == '.mdc':
                import re
                match = re.match(r'---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                if match:
                    content = content[match.end():]
            
            return Response(content, media_type='text/plain; charset=utf-8')
        except Exception as e:
            logger.error(f"Error serving raw markdown {doc_key}: {str(e)}")
            return HTMLResponse("Error reading file", status_code=500)

    async def serve_document(self, request):
        """Serve individual documentation files with enhanced styling"""
        doc_key = request.path_params.get('doc_key') or request.url.path.split('/')[-1]

        if doc_key not in self.DOCS:
            return HTMLResponse("<h1>Document not found</h1>", status_code=404)

        doc_info = self.DOCS[doc_key]
        file_path = Path(doc_info['file'])

        if not file_path.exists():
            return HTMLResponse(f"<h1>File not found: {file_path}</h1>", status_code=404)

        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Strip YAML frontmatter from .mdc files
            if file_path.suffix == '.mdc':
                import re
                match = re.match(r'---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                if match:
                    content = content[match.end():]

            # Always add to conversation history - let dequeue handle overflow
            from server import append_to_conversation
            context_message = f"The user is now viewing the documentation page '{doc_info['title']}'. Here is the content:\n\n{content}"
            append_to_conversation(context_message, role='system')
            logger.info(f"Documentation inserted into conversation history: '{doc_info['title']}' ({len(content)} characters)")

            # Notify user that the document is now available for questions
            if self.pipulate and hasattr(self.pipulate, 'message_queue'):
                import asyncio
                asyncio.create_task(self.pipulate.message_queue.add(
                    self.pipulate,
                    f"📖 Document '{doc_info['title']}' has been loaded into my memory. I'm ready to answer questions about its content!",
                    verbatim=True,
                    role='system'
                ))

            html_content = self.markdown_to_html(content)

            # Create navigation breadcrumb
            category = doc_info.get('category', 'other')
            category_name = {
                'featured': '🌟 Featured Guides',
                'training': '📖 Training Guides',
                'rules': '⚙️ Framework Rules',
                'paginated': '📚 Paginated Documents',
                'considerations': '💭 Development Considerations'
            }.get(category, 'Documentation')

            # Get featured docs for quick navigation
            featured_docs, _, _, _, _ = self.get_categorized_docs()
            quick_nav_links = []
            for key, info in featured_docs[:4]:  # Show first 4 featured
                if key == doc_key:
                    quick_nav_links.append(f'<span class="current-doc">{info["title"][:20]}...</span>')
                else:
                    quick_nav_links.append(f'<a href="/docs/{key}">{info["title"][:20]}...</a>')

            # Generate navigation for rules documents
            rules_navigation = ""
            if category == 'rules':
                prev_doc, next_doc = self.get_rules_navigation(doc_key)
                if prev_doc or next_doc:
                    # Create prev button
                    if prev_doc:
                        prev_key, prev_info = prev_doc
                        prev_button = f'<a href="/docs/{prev_key}" class="nav-button">← {prev_info["title"]}</a>'
                    else:
                        prev_button = '<span class="nav-button disabled">← Previous</span>'
                    
                    # Create next button  
                    if next_doc:
                        next_key, next_info = next_doc
                        next_button = f'<a href="/docs/{next_key}" class="nav-button">{next_info["title"]} →</a>'
                    else:
                        next_button = '<span class="nav-button disabled">Next →</span>'
                    
                    # Create navigation with center info (matching paginated docs)
                    rules_navigation = f'''<div class="navigation">
        {prev_button}
        <div class="nav-info">
            <a href="/docs?category=rules" style="color: #0066cc; text-decoration: none;">⚙️ Framework Rules</a>
        </div>
        {next_button}
    </div>'''

            # Generate navigation for consideration documents
            considerations_navigation = ""
            if category == 'considerations':
                prev_doc, next_doc = self.get_considerations_navigation(doc_key)
                if prev_doc or next_doc:
                    # Create prev button
                    if prev_doc:
                        prev_key, prev_info = prev_doc
                        prev_button = f'<a href="/docs/{prev_key}" class="nav-button">← {prev_info["title"]}</a>'
                    else:
                        prev_button = '<span class="nav-button disabled">← Previous</span>'
                    
                    # Create next button  
                    if next_doc:
                        next_key, next_info = next_doc
                        next_button = f'<a href="/docs/{next_key}" class="nav-button">{next_info["title"]} →</a>'
                    else:
                        next_button = '<span class="nav-button disabled">Next →</span>'
                    
                    # Create navigation with center info
                    considerations_navigation = f'''<div class="navigation">
        {prev_button}
        <div class="nav-info">
            <a href="/docs?category=considerations" style="color: #9c27b0; text-decoration: none;">💭 Development Considerations</a>
        </div>
        {next_button}
    </div>'''

            page_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{doc_info['title']} - Pipulate Documentation</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <!-- Prism CSS -->
    <link href="/assets/css/prism.css" rel="stylesheet" />

    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #fafafa;
        }}

        .breadcrumb {{
            background: #fff;
            padding: 10px 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            font-size: 0.9em;
            color: #6c757d;
        }}

        .breadcrumb a {{
            color: #0066cc;
            text-decoration: none;
        }}

        .breadcrumb a:hover {{
            text-decoration: underline;
        }}

        .nav {{
            background: #fff;
            padding: 15px 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .nav h3 {{
            margin: 0 0 15px 0;
            color: #333;
        }}

        .nav-links {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
        }}

        .nav a {{
            color: #0066cc;
            text-decoration: none;
            padding: 5px 10px;
            border-radius: 4px;
            transition: background-color 0.2s;
        }}

        .nav a:hover {{
            background-color: #f8f9fa;
            text-decoration: none;
        }}

        .current-doc {{
            font-weight: bold;
            color: #333;
            background-color: #e9ecef;
            padding: 5px 10px;
            border-radius: 4px;
        }}

        .copy-markdown-btn {{
            background: #28a745;
            color: white;
            border: none;
            padding: 5px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9em;
            transition: background-color 0.2s;
        }}

        .copy-markdown-btn:hover {{
            background: #218838;
        }}

        .copy-markdown-btn:active {{
            background: #1e7e34;
        }}

        .copy-markdown-btn.copying {{
            background: #ffc107;
            color: #212529;
        }}

        .copy-markdown-btn.success {{
            background: #20c997;
        }}

        .content {{
            background: #fff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        pre {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            overflow-x: auto;
            border-left: 4px solid #0066cc;
            margin: 20px 0;
            white-space: pre;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        }}

        /* Custom copy button styling - override Prism defaults */
        pre .copy-button {{
            position: absolute !important;
            top: 5px !important;
            right: 5px !important;
            padding: 4px 8px !important;
            font-size: 12px !important;
            background: #0066cc !important;
            color: white !important;
            border: none !important;
            border-radius: 3px !important;
            cursor: pointer !important;
            transition: background-color 0.2s ease !important;
            z-index: 10 !important;
        }}

        /* Disable Prism's default hover effects */
        pre .copy-button:hover {{
            background: #0052a3 !important;
            transform: none !important;
            box-shadow: none !important;
        }}

        /* Disable any Prism copy button pseudo-elements or overlays */
        pre .copy-button::before,
        pre .copy-button::after {{
            display: none !important;
        }}

        /* Ensure pre container is positioned for absolute button positioning */
        pre {{
            position: relative !important;
        }}

        code:not([class*="language-"]) {{
            background: #f1f3f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 0.9em;
        }}

        h1, h2, h3, h4 {{
            color: #333;
            margin-top: 2em;
            margin-bottom: 1em;
        }}

        h1 {{
            border-bottom: 3px solid #0066cc;
            padding-bottom: 10px;
            margin-top: 0;
        }}

        h2 {{
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 8px;
        }}

        h3 {{
            border-bottom: 1px solid #f1f3f4;
            padding-bottom: 5px;
        }}

        /* Link styling */
        a {{
            color: #0066cc;
            text-decoration: none;
            transition: color 0.2s ease;
        }}

        a:hover {{
            color: #0052a3;
            text-decoration: underline;
        }}

        a:visited {{
            color: #5a6c7d;
        }}

        /* Links in content should be more prominent */
        .content a {{
            font-weight: 500;
            border-bottom: 1px solid transparent;
        }}

        .content a:hover {{
            border-bottom-color: #0066cc;
            text-decoration: none;
        }}

        blockquote {{
            border-left: 4px solid #ddd;
            margin: 20px 0;
            padding-left: 20px;
            color: #666;
            font-style: italic;
        }}

        /* Enhanced blockquote styling */
        blockquote {{
            background: #f8f9fa;
            border-left: 5px solid #0066cc;
            margin: 25px 0;
            padding: 20px 25px;
            position: relative;
            font-style: italic;
            color: #495057;
            border-radius: 0 8px 8px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}

        blockquote::before {{
            content: '"';
            font-size: 4em;
            color: #0066cc;
            position: absolute;
            left: 10px;
            top: -10px;
            font-family: Georgia, serif;
            opacity: 0.3;
        }}

        blockquote p {{
            margin: 0;
            padding-left: 30px;
            line-height: 1.7;
        }}

        blockquote p:first-child {{
            margin-top: 0;
        }}

        blockquote p:last-child {{
            margin-bottom: 0;
        }}

        .alert {{
            padding: 15px 20px;
            border-radius: 6px;
            margin: 20px 0;
            border-left: 4px solid;
        }}

        .alert-critical {{
            background: #fff5f5;
            border-left-color: #e53e3e;
            color: #742a2a;
        }}

        .alert-success {{
            background: #f0fff4;
            border-left-color: #38a169;
            color: #276749;
        }}

        .alert-error {{
            background: #fffaf0;
            border-left-color: #ed8936;
            color: #9c4221;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}

        th, td {{
            border: 1px solid #e9ecef;
            padding: 12px;
            text-align: left;
        }}

        th {{
            background-color: #f8f9fa;
            font-weight: 600;
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            body {{
                padding: 10px;
            }}

            .content {{
                padding: 20px;
            }}

            .nav-links {{
                flex-direction: column;
                gap: 8px;
            }}
        }}

        /* Additional whitespace preservation rules - surgical approach */

        /* Only pre elements and code inside pre should be block-level */
        pre,
        pre[class*="language-"] {{
            white-space: pre !important;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace !important;
            display: block !important;
            overflow-x: auto !important;
        }}

        /* Code inside pre blocks should inherit pre behavior */
        pre code,
        pre code[class*="language-"] {{
            white-space: pre !important;
            font-family: inherit !important;
            display: block !important;
        }}

        /* Inline code should remain inline but preserve whitespace */
        code:not(pre code),
        code[class*="language-"]:not(pre code) {{
            white-space: pre !important;
            display: inline !important;
        }}

        /* Override any Prism.js whitespace handling */
        .token,
        .token.text {{
            white-space: pre !important;
        }}

        /* Specific rule for text content in code blocks */
        .language-text,
        .language-plaintext {{
            white-space: pre !important;
        }}

        /* Ensure no text normalization for pre content only */
        pre *,
        pre code * {{
            white-space: inherit !important;
        }}

        /* Navigation styles (shared with paginated documents) */
        .navigation {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 20px 0;
        }}
        
        .nav-button {{
            display: inline-block;
            padding: 10px 20px;
            background: #0066cc;
            color: white !important;
            text-decoration: none;
            border-radius: 6px;
            transition: background-color 0.2s;
        }}
        
        .nav-button:hover {{
            background: #0052a3;
            color: white !important;
            text-decoration: none;
        }}
        
        .nav-button:visited {{
            color: white !important;
        }}
        
        .nav-button.disabled {{
            background: #ccc;
            color: #666 !important;
            cursor: not-allowed;
        }}
        
        .nav-info {{
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="breadcrumb">
        <a href="/docs">📚 Documentation</a> → {category_name} → {doc_info['title']}
    </div>

    <div class="nav">
        <h3>Quick Navigation</h3>
        <div class="nav-links">
            <a href="/docs">🏠 Browser</a>
            {' '.join(quick_nav_links)}
            <button id="copy-markdown-btn" class="copy-markdown-btn">📋 Copy Markdown</button>
        </div>
    </div>

    <div class="content">
        {rules_navigation}
        {considerations_navigation}
        {html_content}
        {considerations_navigation}
        {rules_navigation}
    </div>

    <!-- Prism JS -->
    <script src="/assets/js/prism.js"></script>

    <!-- Auto-highlight code blocks and Copy Markdown functionality -->
    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            // Ensure Prism highlights all code blocks
            if (typeof Prism !== 'undefined') {{
                Prism.highlightAll();
            }}

            // Add copy buttons to code blocks
            document.querySelectorAll('pre code').forEach(function(block) {{
                const button = document.createElement('button');
                button.textContent = 'Copy';
                button.className = 'copy-button';

                const pre = block.parentElement;
                pre.appendChild(button);

                button.addEventListener('click', function() {{
                    navigator.clipboard.writeText(block.textContent).then(function() {{
                        button.textContent = 'Copied!';
                        setTimeout(function() {{
                            button.textContent = 'Copy';
                        }}, 2000);
                    }});
                }});
            }});

            // Copy Markdown functionality - check if button exists
            const copyMarkdownBtn = document.getElementById('copy-markdown-btn');
            if (copyMarkdownBtn) {{
                copyMarkdownBtn.addEventListener('click', async function() {{
                    const button = this;
                    const originalText = button.textContent;

                    try {{
                        // Show loading state
                        button.textContent = '⏳ Fetching...';
                        button.classList.add('copying');
                        button.disabled = true;

                        // Fetch the raw markdown content
                        const response = await fetch('/docs/raw/{doc_key}');
                        if (!response.ok) {{
                            throw new Error('Failed to fetch markdown content');
                        }}

                        const markdownContent = await response.text();

                        // Copy to clipboard
                        await navigator.clipboard.writeText(markdownContent);

                        // Show success state
                        button.textContent = '✅ Copied!';
                        button.classList.remove('copying');
                        button.classList.add('success');

                        // Reset after 3 seconds
                        setTimeout(function() {{
                            button.textContent = originalText;
                            button.classList.remove('success');
                            button.disabled = false;
                        }}, 3000);

                    }} catch (error) {{
                        console.error('Error copying markdown:', error);

                        // Show error state
                        button.textContent = '❌ Error';
                        button.classList.remove('copying');

                        // Reset after 3 seconds
                        setTimeout(function() {{
                            button.textContent = originalText;
                            button.disabled = false;
                        }}, 3000);
                    }}
                }});
            }}
        }});
    </script>
</body>
</html>"""

            # 🏗️ ARCHITECTURAL: Custom HTML pattern (see line 1274 for full details)
            return HTMLResponse(page_html)

        except Exception as e:
            logger.error(f"Error serving document {doc_key}: {str(e)}")
            return HTMLResponse(f"<h1>Error loading document: {str(e)}</h1>", status_code=500)

    async def landing(self, render_items=None):
        """Always appears in create_grid_left."""
        unique_id = f"docs-{int(time.time() * 1000)}"

        # Send the documentation info to the conversation history, but only once per session
        if self.pipulate is not None and not self._has_streamed:
            try:
                # First, send the verbatim redirect message
                await self.pipulate.stream(
                    self.ENDPOINT_MESSAGE,
                    verbatim=True,
                    role="system",
                    spaces_before=1,
                    spaces_after=1
                )

                # Then append the documentation info to history without displaying
                featured_docs, training_docs, rules_docs, paginated_docs, _ = self.get_categorized_docs()

                docs_message = f"Available Documentation ({len(self.DOCS)} files discovered):\n"

                if featured_docs:
                    docs_message += "\nFeatured Guides:\n"
                    for key, info in featured_docs:
                        docs_message += f"- {info['title']}: {info['description']}\n"

                docs_message += f"\nPlus {len(training_docs)} training guides and {len(rules_docs)} framework rules automatically discovered."

                self.pipulate.append_to_history(
                    f"[WIDGET CONTENT] Pipulate Documentation Browser\n{docs_message}",
                    role="system"
                )

                self._has_streamed = True
                logger.debug("Documentation info appended to conversation history")
            except Exception as e:
                logger.error(f"Error in documentation plugin: {str(e)}")

        # Create featured documentation links
        featured_docs, training_docs, rules_docs, paginated_docs, _ = self.get_categorized_docs()

        featured_links = []
        for key, info in featured_docs:
            featured_links.append(
                Li(
                    A(
                        info['title'],
                        href=f"/docs/{key}",
                        target="_blank",
                        style="text-decoration: none; color: var(--pico-primary); font-weight: 500;"
                    ),
                    P(info['description'], style="margin: 0.25rem 0 0.75rem 0; font-size: 0.9em; color: var(--pico-muted-color);")
                )
            )

        return Div(
            H2("📚 Documentation Browser"),
            P(Strong("🧠 Smart Documentation Training:"), " When you view any document below, its content is automatically added to the LLM's conversation history. This means you can then ask the chatbot specific questions about that document's content, and it will have the full context to provide detailed answers."),

            # Browse all button
            A(
                "🗂️ Browse All Documentation",
                href="/docs",
                target="_blank",
                style="display: inline-block; padding: 10px 20px; background: var(--pico-primary); color: white; text-decoration: none; border-radius: 6px; font-weight: 500;"
            ),

            # Quick stats summary with clickable links to browse sections
            Div(
                P(A(Span("📄", cls="emoji icon-spaced"), "README - Project Overview",
                    href="/docs/readme", target="_blank",
                    style="color: var(--pico-primary); text-decoration: none; font-weight: bold;",
                    onmouseover="this.style.textDecoration='underline'; this.style.color='var(--pico-primary-hover)';",
                    onmouseout="this.style.textDecoration='none'; this.style.color='var(--pico-primary)';"),
                  cls="my-xs"),
                Hr(style="border: none; height: 1px; background: #e9ecef; margin: 8px 0;"),
                P(A(Span("📊", cls="emoji icon-spaced"), f"{len(self.DOCS)} documents discovered",
                    href="/docs", target="_blank",
                    cls="link-primary",
                    onmouseover="this.style.textDecoration='underline'; this.style.color='var(--pico-primary-hover)';",
                    onmouseout="this.style.textDecoration='none'; this.style.color='var(--pico-primary)';"),
                  cls="my-xs"),
                P(A(Span("🌟", cls="emoji icon-spaced"), f"{len(featured_docs)} featured guides",
                    href="/docs?category=featured", target="_blank",
                    cls="link-primary",
                    onmouseover="this.style.textDecoration='underline'; this.style.color='var(--pico-primary-hover)';",
                    onmouseout="this.style.textDecoration='none'; this.style.color='var(--pico-primary)';"),
                  cls="my-xs"),
                P(A(Span("📖", cls="emoji icon-spaced"), f"{len(training_docs)} training files",
                    href="/docs?category=training", target="_blank",
                    cls="link-primary",
                    onmouseover="this.style.textDecoration='underline'; this.style.color='var(--pico-primary-hover)';",
                    onmouseout="this.style.textDecoration='none'; this.style.color='var(--pico-primary)';"),
                  cls="my-xs"),
                P(A(Span("⚙️", cls="emoji icon-spaced"), f"{len(rules_docs)} framework rules",
                    href="/docs?category=rules", target="_blank",
                    cls="link-primary",
                    onmouseover="this.style.textDecoration='underline'; this.style.color='var(--pico-primary-hover)';",
                    onmouseout="this.style.textDecoration='none'; this.style.color='var(--pico-primary)';"),
                  cls="my-xs"),
                P(A(Span("📚", cls="emoji icon-spaced"), f"{len(paginated_docs)} paginated documents",
                    href="/docs?category=paginated", target="_blank",
                    cls="link-primary",
                    onmouseover="this.style.textDecoration='underline'; this.style.color='var(--pico-primary-hover)';",
                    onmouseout="this.style.textDecoration='none'; this.style.color='var(--pico-primary)';"),
                  cls="my-xs"),
                Hr(style="border: none; height: 1px; background: #e9ecef; margin: 8px 0;"),
                P(Strong("🌐 Public Docs"), style="margin: 0.5rem 0 0.25rem 0; font-size: 0.9em; color: var(--pico-muted-color);"),
                P(A(Span("🏠", cls="emoji icon-spaced"), "Pipulate.com",
                    href="https://pipulate.com/", target="_blank",
                    cls="link-primary",
                    onmouseover="this.style.textDecoration='underline'; this.style.color='var(--pico-primary-hover)';",
                    onmouseout="this.style.textDecoration='none'; this.style.color='var(--pico-primary)';"),
                  cls="my-xs"),
                P(A(Span("📚", cls="emoji icon-spaced"), "Official Documentation",
                    href="https://pipulate.com/documentation/", target="_blank",
                    cls="link-primary",
                    onmouseover="this.style.textDecoration='underline'; this.style.color='var(--pico-primary-hover)';",
                    onmouseout="this.style.textDecoration='none'; this.style.color='var(--pico-primary)';"),
                  cls="my-xs"),
                P(A(Span("👨‍💻", cls="emoji icon-spaced"), "1-Pager Development Guide",
                    href="https://pipulate.com/development/", target="_blank",
                    cls="link-primary",
                    onmouseover="this.style.textDecoration='underline'; this.style.color='var(--pico-primary-hover)';",
                    onmouseout="this.style.textDecoration='none'; this.style.color='var(--pico-primary)';"),
                  cls="my-xs"),
                P(A(Span("📖", cls="emoji icon-spaced"), "Paginated Guide",
                    href="https://pipulate.com/guide/", target="_blank",
                    cls="link-primary",
                    onmouseover="this.style.textDecoration='underline'; this.style.color='var(--pico-primary-hover)';",
                    onmouseout="this.style.textDecoration='none'; this.style.color='var(--pico-primary)';"),
                  cls="my-xs"),
                P(A(Span("📦", cls="emoji icon-spaced"), "PyPI Package",
                    href="https://pypi.org/project/pipulate/", target="_blank",
                    cls="link-primary",
                    onmouseover="this.style.textDecoration='underline'; this.style.color='var(--pico-primary-hover)';",
                    onmouseout="this.style.textDecoration='none'; this.style.color='var(--pico-primary)';"),
                  cls="my-xs"),
                P(A(Span("🐙", cls="emoji icon-spaced"), "GitHub Repository",
                    href="https://github.com/miklevin/pipulate", target="_blank",
                    cls="link-primary",
                    onmouseover="this.style.textDecoration='underline'; this.style.color='var(--pico-primary-hover)';",
                    onmouseout="this.style.textDecoration='none'; this.style.color='var(--pico-primary)';"),
                  cls="my-xs"),
                style="background-color: var(--pico-card-sectionning-background-color); padding: 1rem; margin: 1rem 0; border-radius: var(--pico-border-radius); font-weight: 500;"
            ),

            id=unique_id
        )

    # ========================================
    # GENERIC PAGINATION SYSTEM (80/20 Rule)
    # ========================================
    
    def parse_paginated_document(self, content, separator='-' * 80):
        """Generic method to parse any paginated document"""
        pages = []
        current_page = []
        lines = content.split('\n')

        for line in lines:
            if line.strip() == separator:
                # Found a page separator
                if current_page:
                    pages.append('\n'.join(current_page))
                    current_page = []
            else:
                current_page.append(line)

        # Add the last page if there's content
        if current_page:
            pages.append('\n'.join(current_page))

        return pages

    def extract_paginated_toc(self, pages, doc_key):
        """Generic method to extract TOC from any paginated document"""
        toc = []

        for page_num, page_content in enumerate(pages, 1):
            lines = page_content.split('\n')
            page_title = f"Page {page_num}"

            # Look for first heading in the page
            for line in lines:
                line = line.strip()
                if not line or line.startswith('```'):
                    continue
                    
                # For page 1, accept H1 or H2 (since main title might be used for document)
                # For other pages, look for H1 or H2 headers
                if line.startswith('# '):
                    page_title = self._remove_html_comments(line[2:].strip())
                    break
                elif line.startswith('## '):
                    page_title = self._remove_html_comments(line[3:].strip())
                    break

            # Get a brief description from the first paragraph
            description = ""
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('```') and len(line) > 20:
                    # Clean up markdown in description
                    clean_line = self._clean_description_text(line)
                    description = clean_line[:100] + ('...' if len(clean_line) > 100 else '')
                    break

            toc.append({
                'page_num': page_num,
                'title': page_title,
                'description': description or "Documentation content"
            })

        return toc

    async def serve_paginated_toc(self, request, doc_key):
        """Generic method to serve TOC for any paginated document"""
        if doc_key not in self.DOCS:
            return HTMLResponse("Document not found", status_code=404)
            
        doc_info = self.DOCS[doc_key]
        if not doc_info.get('paginated'):
            return HTMLResponse("Document not paginated", status_code=404)
            
        file_path = Path(doc_info['file'])
        if not file_path.exists():
            return HTMLResponse("File not found", status_code=404)

        try:
            content = file_path.read_text(encoding='utf-8')
            separator = doc_info.get('separator', '-' * 80)
            pages = self.parse_paginated_document(content, separator)
            toc = self.extract_paginated_toc(pages, doc_key)

            # Create table of contents HTML
            toc_items = []
            for item in toc:
                toc_items.append(f'''
                    <div class="toc-item">
                        <h3><a href="/docs/{doc_key}/page/{item['page_num']}">{item['title']}</a></h3>
                        <p class="toc-description">{item['description']}</p>
                        <span class="page-number">Page {item['page_num']} of {len(pages)}</span>
                    </div>
                ''')

            # Get document title for header
            doc_title = doc_info.get('title', 'Documentation')
            
            page_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{doc_title} - Table of Contents</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background: #fafafa;
        }}

        .breadcrumb {{
            background: #fff;
            padding: 10px 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            font-size: 0.9em;
            color: #6c757d;
        }}

        .breadcrumb a {{
            color: #0066cc;
            text-decoration: none;
        }}

        .header {{
            background: #fff;
            padding: 30px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }}

        .header h1 {{
            color: #333;
            margin: 0 0 10px 0;
        }}

        .header .subtitle {{
            color: #666;
            font-size: 1.1em;
        }}

        .stats {{
            background: #e3f2fd;
            padding: 15px;
            border-radius: 6px;
            margin: 20px 0;
            text-align: center;
            color: #1565c0;
        }}

        .toc-container {{
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}

        .toc-item {{
            padding: 20px;
            border-bottom: 1px solid #e9ecef;
            transition: background-color 0.2s;
        }}

        .toc-item:last-child {{
            border-bottom: none;
        }}

        .toc-item:hover {{
            background-color: #f8f9fa;
        }}

        .toc-item h3 {{
            margin: 0 0 10px 0;
        }}

        .toc-item h3 a {{
            color: #0066cc;
            text-decoration: none;
        }}

        .toc-item h3 a:hover {{
            text-decoration: underline;
        }}

        .toc-description {{
            color: #666;
            margin: 0 0 10px 0;
        }}

        .page-number {{
            font-size: 0.9em;
            color: #6c757d;
        }}

        .navigation {{
            display: flex;
            justify-content: space-between;
            margin-top: 20px;
        }}

        .nav-button {{
            display: inline-block;
            padding: 10px 20px;
            background: #0066cc;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            transition: background-color 0.2s;
        }}

        .nav-button:hover {{
            background: #0052a3;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="breadcrumb">
        <a href="/docs">📚 Documentation</a> → <strong>{doc_title}</strong>
    </div>

    <div class="header">
        <h1>📖 {doc_title}</h1>
        <div class="subtitle">Table of Contents</div>
    </div>

    <div class="stats">
        📄 {len(pages)} pages available • 🔍 Click any page to view content
    </div>

    <div class="toc-container">
        {''.join(toc_items)}
    </div>

    <div class="navigation">
        <a href="/docs" class="nav-button">← Back to Documentation</a>
        <a href="/docs/{doc_key}/page/1" class="nav-button">Start Reading →</a>
    </div>
</body>
</html>"""

            # 🏗️ ARCHITECTURAL: Custom HTML pattern (see line 1274 for full details)
            return HTMLResponse(page_html)

        except Exception as e:
            logger.error(f"Error serving paginated TOC for {doc_key}: {e}")
            return HTMLResponse(f"Error loading document: {str(e)}", status_code=500)

    async def serve_paginated_page(self, request, doc_key, page_num):
        """Generic method to serve individual pages of paginated documents"""
        if doc_key not in self.DOCS:
            return HTMLResponse("Document not found", status_code=404)
            
        doc_info = self.DOCS[doc_key]
        if not doc_info.get('paginated'):
            return HTMLResponse("Document not paginated", status_code=404)
            
        file_path = Path(doc_info['file'])
        if not file_path.exists():
            return HTMLResponse("File not found", status_code=404)

        try:
            page_num = int(page_num)
            content = file_path.read_text(encoding='utf-8')
            separator = doc_info.get('separator', '-' * 80)
            pages = self.parse_paginated_document(content, separator)

            if page_num < 1 or page_num > len(pages):
                return HTMLResponse("Page not found", status_code=404)

            page_content = pages[page_num - 1]
            
            # Always add to conversation history - let dequeue handle overflow
            from server import append_to_conversation
            context_message = f"The user is now viewing page {page_num} of '{doc_info['title']}'. Here is the content:\n\n{page_content}"
            append_to_conversation(context_message, role='system')
            logger.info(f"Documentation inserted into conversation history: '{doc_info['title']} - Page {page_num}' ({len(page_content)} characters)")

            # Notify user that the document is now available for questions
            if self.pipulate and hasattr(self.pipulate, 'message_queue'):
                import asyncio
                # Get page title for better user notification
                lines = page_content.split('\n')
                page_title = f"Page {page_num}"
                for line in lines:
                    line = line.strip()
                    if line.startswith('# ') and not line.startswith('```'):
                        page_title = line[2:].strip()
                        break
                
                asyncio.create_task(self.pipulate.message_queue.add(
                    self.pipulate,
                    f"📖 Page {page_num} of {doc_info['title']}: '{page_title}' has been loaded into my memory. I'm ready to answer questions about its content!",
                    verbatim=True,
                    role='system'
                ))
            
            html_content = self.markdown_to_html(page_content)
            doc_title = doc_info.get('title', 'Documentation')

            # Navigation
            prev_link = f'<a href="/docs/{doc_key}/page/{page_num - 1}" class="nav-button">← Previous</a>' if page_num > 1 else '<span class="nav-button disabled">← Previous</span>'
            next_link = f'<a href="/docs/{doc_key}/page/{page_num + 1}" class="nav-button">Next →</a>' if page_num < len(pages) else '<span class="nav-button disabled">Next →</span>'

            # Get page title for display
            lines = page_content.split('\n')
            page_title = f"Page {page_num}"
            for line in lines:
                line = line.strip()
                if line.startswith('# ') and not line.startswith('```'):
                    page_title = line[2:].strip()
                    break

            page_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{page_title} - {doc_title}</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    
    <!-- Prism CSS -->
    <link href="/assets/css/prism.css" rel="stylesheet">
    
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background: #fafafa;
        }}
        .breadcrumb {{
            background: #fff;
            padding: 10px 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            font-size: 0.9em;
            color: #6c757d;
        }}
        .breadcrumb a {{
            color: #0066cc;
            text-decoration: none;
        }}
        .page-header {{
            background: #fff;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .page-info {{
            color: #666;
        }}
        .copy-markdown-btn {{
            background: #28a745;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9em;
            transition: background-color 0.2s;
        }}
        .copy-markdown-btn:hover {{
            background: #218838;
        }}
        .copy-markdown-btn.copying {{
            background: #ffc107;
            color: #212529;
        }}
        .copy-markdown-btn.success {{
            background: #20c997;
        }}
        .content {{
            background: #fff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .navigation {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 20px 0;
        }}
        .nav-button {{
            display: inline-block;
            padding: 10px 20px;
            background: #0066cc;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            transition: background-color 0.2s;
        }}
        .nav-button:hover {{
            background: #0052a3;
            text-decoration: none;
        }}
        .nav-button.disabled {{
            background: #ccc;
            cursor: not-allowed;
        }}
        .nav-info {{
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
        /* Responsive */
        @media (max-width: 768px) {{
            .page-header {{
                flex-direction: column;
                gap: 10px;
                text-align: center;
            }}
            .navigation {{
                flex-direction: column;
                gap: 15px;
            }}
            .nav-info {{
                order: -1;
            }}
        }}
    </style>
</head>
<body>
    <div class="breadcrumb">
        <a href="/docs">📚 Documentation</a> → 
        <a href="/docs/{doc_key}/toc">{doc_title}</a> → 
        <strong>Page {page_num}</strong>
    </div>

    <div class="page-header">
        <div class="page-info">
            <strong>{page_title}</strong><br>
            Page {page_num} of {len(pages)}
        </div>
        <button id="copy-markdown-btn" class="copy-markdown-btn">📋 Copy Page Markdown</button>
    </div>

    <div class="navigation">
        {prev_link}
        <div class="nav-info">
            <a href="/docs/{doc_key}/toc" style="color: #0066cc; text-decoration: none;">📖 Table of Contents</a><br>
            Page {page_num} of {len(pages)}
        </div>
        {next_link}
    </div>

    <div class="content">
        {html_content}
    </div>

    <div class="navigation">
        {prev_link}
        <div class="nav-info">
            <a href="/docs/{doc_key}/toc" style="color: #0066cc; text-decoration: none;">📖 Table of Contents</a><br>
            Page {page_num} of {len(pages)}
        </div>
        {next_link}
    </div>

    <!-- Prism JavaScript -->
    <script src="/assets/js/prism.js"></script>
    <script>
        // Initialize Prism highlighting when page loads
        document.addEventListener('DOMContentLoaded', function() {{
            if (typeof Prism !== 'undefined') {{
                Prism.highlightAll();
            }}

            // Add copy buttons to code blocks
            document.querySelectorAll('pre code').forEach(function(block) {{
                const button = document.createElement('button');
                button.textContent = 'Copy';
                button.className = 'copy-button';
                button.style.position = 'absolute';
                button.style.top = '5px';
                button.style.right = '5px';
                button.style.padding = '4px 8px';
                button.style.fontSize = '12px';
                button.style.background = '#0066cc';
                button.style.color = 'white';
                button.style.border = 'none';
                button.style.borderRadius = '3px';
                button.style.cursor = 'pointer';
                button.style.zIndex = '10';

                const pre = block.parentElement;
                pre.style.position = 'relative';
                pre.appendChild(button);

                button.addEventListener('click', function() {{
                    navigator.clipboard.writeText(block.textContent).then(function() {{
                        button.textContent = 'Copied!';
                        setTimeout(function() {{
                            button.textContent = 'Copy';
                        }}, 2000);
                    }});
                }});
            }});

            // Copy Page Markdown functionality
            const copyMarkdownBtn = document.getElementById('copy-markdown-btn');
            if (copyMarkdownBtn) {{
                copyMarkdownBtn.addEventListener('click', async function() {{
                    const button = this;
                    const originalText = button.textContent;

                    try {{
                        // Show loading state
                        button.textContent = '⏳ Copying...';
                        button.classList.add('copying');
                        button.disabled = true;

                        // Get the raw page content
                        const pageContent = {repr(page_content)};

                        // Copy to clipboard
                        await navigator.clipboard.writeText(pageContent);

                        // Show success state
                        button.textContent = '✅ Copied!';
                        button.classList.remove('copying');
                        button.classList.add('success');

                        // Reset after 3 seconds
                        setTimeout(function() {{
                            button.textContent = originalText;
                            button.classList.remove('success');
                            button.disabled = false;
                        }}, 3000);

                    }} catch (error) {{
                        console.error('Error copying markdown:', error);

                        // Show error state
                        button.textContent = '❌ Error';
                        button.classList.remove('copying');

                        // Reset after 3 seconds
                        setTimeout(function() {{
                            button.textContent = originalText;
                            button.disabled = false;
                        }}, 3000);
                    }}
                }});
            }}
        }});
    </script>
</body>
</html>"""

            # 🏗️ ARCHITECTURAL: Custom HTML pattern (see line 1274 for full details)
            return HTMLResponse(page_html)

        except ValueError:
            return HTMLResponse("Invalid page number", status_code=400)
        except Exception as e:
            logger.error(f"Error serving paginated page {page_num} for {doc_key}: {e}")
            return HTMLResponse(f"Error loading page: {str(e)}", status_code=500)

    # ========================================
    # LEGACY SPECIFIC METHODS (TO BE DEPRECATED)
    # ========================================

    def parse_botify_api_pages(self, content):
        """Parse the botify_api.md content into pages separated by 80 hyphens"""
        pages = []
        current_page = []
        lines = content.split('\n')

        for line in lines:
            if line.strip() == '-' * 80:
                # Found a page separator
                if current_page:
                    pages.append('\n'.join(current_page))
                    current_page = []
            else:
                current_page.append(line)

        # Add the last page if there's content
        if current_page:
            pages.append('\n'.join(current_page))

        return pages

    def extract_botify_api_toc(self, pages):
        """Extract table of contents from botify_api pages"""
        toc = []

        for page_num, page_content in enumerate(pages, 1):
            lines = page_content.split('\n')
            page_title = f"Page {page_num}"

            # Look for the first H1 heading in the page
            for line in lines:
                line = line.strip()
                if line.startswith('# ') and not line.startswith('```'):
                    page_title = line[2:].strip()
                    break

            # Get a brief description from the first paragraph
            description = ""
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('```') and len(line) > 20:
                    description = line[:100] + ('...' if len(line) > 100 else '')
                    break

            toc.append({
                'page_num': page_num,
                'title': page_title,
                'description': description or "Documentation content"
            })

        return toc

    async def serve_botify_api_toc(self, request):
        """Serve the table of contents for botify_api.md"""
        doc_info = self.DOCS['botify_api']
        file_path = Path(doc_info['file'])

        if not file_path.exists():
            return HTMLResponse("File not found", status_code=404)

        try:
            content = file_path.read_text(encoding='utf-8')
            pages = self.parse_botify_api_pages(content)
            toc = self.extract_botify_api_toc(pages)

            # Create table of contents HTML
            toc_items = []
            for item in toc:
                toc_items.append(f'''
                    <div class="toc-item">
                        <h3><a href="/docs/botify_api/page/{item['page_num']}">{item['title']}</a></h3>
                        <p class="toc-description">{item['description']}</p>
                        <span class="page-number">Page {item['page_num']} of {len(pages)}</span>
                    </div>
                ''')

            page_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Botify API Documentation - Table of Contents</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background: #fafafa;
        }}

        .breadcrumb {{
            background: #fff;
            padding: 10px 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            font-size: 0.9em;
            color: #6c757d;
        }}

        .breadcrumb a {{
            color: #0066cc;
            text-decoration: none;
        }}

        .header {{
            background: #fff;
            padding: 30px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }}

        .header h1 {{
            color: #333;
            margin: 0 0 10px 0;
        }}

        .header .subtitle {{
            color: #666;
            font-size: 1.1em;
        }}

        .stats {{
            background: #e3f2fd;
            padding: 15px;
            border-radius: 6px;
            margin: 20px 0;
            text-align: center;
            color: #1565c0;
        }}

        .toc-container {{
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}

        .toc-item {{
            padding: 20px;
            border-bottom: 1px solid #e9ecef;
            transition: background-color 0.2s;
        }}

        .toc-item:last-child {{
            border-bottom: none;
        }}

        .toc-item:hover {{
            background-color: #f8f9fa;
        }}

        .toc-item h3 {{
            margin: 0 0 10px 0;
        }}

        .toc-item h3 a {{
            color: #0066cc;
            text-decoration: none;
        }}

        .toc-item h3 a:hover {{
            text-decoration: underline;
        }}

        .toc-description {{
            color: #666;
            margin: 0 0 10px 0;
        }}

        .page-number {{
            font-size: 0.9em;
            color: #6c757d;
        }}

        .navigation {{
            display: flex;
            justify-content: space-between;
            margin-top: 20px;
        }}

        .nav-button {{
            display: inline-block;
            padding: 10px 20px;
            background: #0066cc;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            transition: background-color 0.2s;
        }}

        .nav-button:hover {{
            background: #0052a3;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="breadcrumb">
        <a href="/docs">📚 Documentation</a> → 📖 Training Guides → Botify API Documentation
    </div>

    <div class="header">
        <h1>📊 Botify API Documentation</h1>
        <p class="subtitle">Complete guide to the Botify API with practical examples</p>
        <div class="stats">
            📄 {len(pages)} pages • 📝 {len(content.split())} words • ⏱️ ~{len(content.split()) // 200} min read
        </div>
    </div>

    <div class="toc-container">
        {''.join(toc_items)}
    </div>

    <div class="navigation">
        <a href="/docs" class="nav-button">🏠 Back to Documentation</a>
        <a href="/docs/botify_api/page/1" class="nav-button">📖 Start Reading</a>
    </div>
</body>
</html>"""

            # 🏗️ ARCHITECTURAL: Custom HTML pattern (see line 1274 for full details)
            return HTMLResponse(page_html)

        except Exception as e:
            logger.error(f"Error serving botify_api TOC: {str(e)}")
            return HTMLResponse(f"Error loading document: {str(e)}", status_code=500)

    async def serve_botify_api_page(self, request):
        """Serve a specific page of botify_api.md"""
        page_num = int(request.path_params.get('page_num', 1))
        doc_info = self.DOCS['botify_api']
        file_path = Path(doc_info['file'])

        if not file_path.exists():
            return HTMLResponse("File not found", status_code=404)

        try:
            content = file_path.read_text(encoding='utf-8')
            pages = self.parse_botify_api_pages(content)

            if page_num < 1 or page_num > len(pages):
                return HTMLResponse("Page not found", status_code=404)

            page_content = pages[page_num - 1]

            # Always add to conversation history - let dequeue handle overflow
            from server import append_to_conversation
            context_message = f"The user is now viewing page {page_num} of the Botify API documentation. Here is the content:\n\n{page_content}"
            append_to_conversation(context_message, role='system')
            logger.info(f"Documentation inserted into conversation history: 'Botify API Documentation - Page {page_num}' ({len(page_content)} characters)")

            # Get page title for better user notification
            lines = page_content.split('\n')
            page_title = f"Page {page_num}"
            for line in lines:
                line = line.strip()
                if line.startswith('# ') and not line.startswith('```'):
                    page_title = line[2:].strip()
                    break

            # Notify user that the document is now available for questions
            if self.pipulate and hasattr(self.pipulate, 'message_queue'):
                import asyncio
                asyncio.create_task(self.pipulate.message_queue.add(
                    self.pipulate,
                    f"📖 Botify API Documentation '{page_title}' has been loaded into my memory. I'm ready to answer questions about its content!",
                    verbatim=True,
                    role='system'
                ))

            html_content = self.markdown_to_html(page_content)

            # Get page title
            lines = page_content.split('\n')
            page_title = f"Page {page_num}"
            for line in lines:
                line = line.strip()
                if line.startswith('# ') and not line.startswith('```'):
                    page_title = line[2:].strip()
                    break

            # Navigation buttons
            prev_button = ""
            next_button = ""

            if page_num > 1:
                prev_button = f'<a href="/docs/botify_api/page/{page_num - 1}" class="nav-button prev">← Previous</a>'

            if page_num < len(pages):
                next_button = f'<a href="/docs/botify_api/page/{page_num + 1}" class="nav-button next">Next →</a>'

            page_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{page_title} - Botify API Documentation</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=2">

    <!-- Prism CSS -->
    <link href="/assets/css/prism.css" rel="stylesheet" />

    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #fafafa;
        }}

        .breadcrumb {{
            background: #fff;
            padding: 10px 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            font-size: 0.9em;
            color: #6c757d;
        }}

        .breadcrumb a {{
            color: #0066cc !important;
            text-decoration: none;
            font-weight: 500;
        }}

        .breadcrumb a:hover {{
            color: #0052a3 !important;
            text-decoration: underline;
        }}

        .breadcrumb a:visited {{
            color: #0066cc !important;
        }}

        .page-header {{
            background: #fff;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .page-info {{
            color: #666;
        }}

        .copy-markdown-btn {{
            background: #28a745;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9em;
            transition: background-color 0.2s;
        }}

        .copy-markdown-btn:hover {{
            background: #218838;
        }}

        .copy-markdown-btn.copying {{
            background: #ffc107;
            color: #212529;
        }}

        .copy-markdown-btn.success {{
            background: #20c997;
        }}

        .content {{
            background: #fff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}

        .navigation {{
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .nav-button {{
            display: inline-block;
            padding: 10px 20px;
            background: #0066cc;
            color: white !important;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 500;
            transition: background-color 0.2s;
        }}

        .nav-button:hover {{
            background: #0052a3;
            color: white !important;
            text-decoration: none;
        }}

        .nav-button:visited {{
            color: white !important;
        }}

        .nav-button.toc {{
            background: #6c757d;
            color: white !important;
        }}

        .nav-button.toc:hover {{
            background: #545b62;
            color: white !important;
        }}

        .nav-button.toc:visited {{
            color: white !important;
        }}

        .nav-center {{
            text-align: center;
            color: #666;
        }}

        pre {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            overflow-x: auto;
            border-left: 4px solid #0066cc;
            margin: 20px 0;
            white-space: pre;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        }}

        /* Custom copy button styling - override Prism defaults */
        pre .copy-button {{
            position: absolute !important;
            top: 5px !important;
            right: 5px !important;
            padding: 4px 8px !important;
            font-size: 12px !important;
            background: #0066cc !important;
            color: white !important;
            border: none !important;
            border-radius: 3px !important;
            cursor: pointer !important;
            transition: background-color 0.2s ease !important;
            z-index: 10 !important;
        }}

        /* Disable Prism's default hover effects */
        pre .copy-button:hover {{
            background: #0052a3 !important;
            transform: none !important;
            box-shadow: none !important;
        }}

        /* Disable any Prism copy button pseudo-elements or overlays */
        pre .copy-button::before,
        pre .copy-button::after {{
            display: none !important;
        }}

        /* Ensure pre container is positioned for absolute button positioning */
        pre {{
            position: relative !important;
        }}

        code:not([class*="language-"]) {{
            background: #f1f3f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 0.9em;
        }}

        h1, h2, h3, h4 {{
            color: #333;
            margin-top: 2em;
            margin-bottom: 1em;
        }}

        h1 {{
            border-bottom: 3px solid #0066cc;
            padding-bottom: 10px;
            margin-top: 0;
        }}

        h2 {{
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 8px;
        }}

        h3 {{
            border-bottom: 1px solid #f1f3f4;
            padding-bottom: 5px;
        }}

        /* Link styling */
        a {{
            color: #0066cc;
            text-decoration: none;
            transition: color 0.2s ease;
        }}

        a:hover {{
            color: #0052a3;
            text-decoration: underline;
        }}

        a:visited {{
            color: #5a6c7d;
        }}

        /* Links in content should be more prominent */
        .content a {{
            font-weight: 500;
            border-bottom: 1px solid transparent;
        }}

        .content a:hover {{
            border-bottom-color: #0066cc;
            text-decoration: none;
        }}

        blockquote {{
            border-left: 4px solid #ddd;
            margin: 20px 0;
            padding-left: 20px;
            color: #666;
            font-style: italic;
        }}

        /* Enhanced blockquote styling */
        blockquote {{
            background: #f8f9fa;
            border-left: 5px solid #0066cc;
            margin: 25px 0;
            padding: 20px 25px;
            position: relative;
            font-style: italic;
            color: #495057;
            border-radius: 0 8px 8px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}

        blockquote::before {{
            content: '"';
            font-size: 4em;
            color: #0066cc;
            position: absolute;
            left: 10px;
            top: -10px;
            font-family: Georgia, serif;
            opacity: 0.3;
        }}

        blockquote p {{
            margin: 0;
            padding-left: 30px;
            line-height: 1.7;
        }}

        blockquote p:first-child {{
            margin-top: 0;
        }}

        blockquote p:last-child {{
            margin-bottom: 0;
        }}

        .alert {{
            padding: 15px 20px;
            border-radius: 6px;
            margin: 20px 0;
            border-left: 4px solid;
        }}

        .alert-critical {{
            background: #fff5f5;
            border-left-color: #e53e3e;
            color: #742a2a;
        }}

        .alert-success {{
            background: #f0fff4;
            border-left-color: #38a169;
            color: #276749;
        }}

        .alert-error {{
            background: #fffaf0;
            border-left-color: #ed8936;
            color: #9c4221;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}

        th, td {{
            border: 1px solid #e9ecef;
            padding: 12px;
            text-align: left;
        }}

        th {{
            background-color: #f8f9fa;
            font-weight: 600;
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            .page-header {{
                flex-direction: column;
                gap: 10px;
                text-align: center;
            }}

            .navigation {{
                flex-direction: column;
                gap: 15px;
            }}

            .nav-center {{
                order: -1;
            }}
        }}

        /* Additional whitespace preservation rules - surgical approach */

        /* Only pre elements and code inside pre should be block-level */
        pre,
        pre[class*="language-"] {{
            white-space: pre !important;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace !important;
            display: block !important;
            overflow-x: auto !important;
        }}

        pre code,
        pre code[class*="language-"] {{
            white-space: pre !important;
            font-family: inherit !important;
            display: block !important;
        }}

        code:not(pre code),
        code[class*="language-"]:not(pre code) {{
            white-space: pre !important;
            display: inline !important;
        }}

        .token,
        .token.text {{
            white-space: pre !important;
        }}

        .language-text,
        .language-plaintext {{
            white-space: pre !important;
        }}

        pre *,
        pre code * {{
            white-space: inherit !important;
        }}
    </style>
</head>
<body>
    <div class="breadcrumb">
        <a href="/docs">📚 Documentation</a> →
        <a href="/docs/botify_api">Botify API</a> →
        Page {page_num}
    </div>

    <div class="page-header">
        <div class="page-info">
            <strong>{page_title}</strong><br>
            Page {page_num} of {len(pages)}
        </div>
        <button id="copy-markdown-btn" class="copy-markdown-btn">📋 Copy Page Markdown</button>
    </div>

    <!-- Top Navigation -->
    <div class="navigation">
        <div>
            {prev_button}
        </div>
        <div class="nav-center">
            <a href="/docs/botify_api" class="nav-button toc">📋 Table of Contents</a>
        </div>
        <div>
            {next_button}
        </div>
    </div>

    <div class="content">
        {html_content}
    </div>

    <!-- Bottom Navigation -->
    <div class="navigation">
        <div>
            {prev_button}
        </div>
        <div class="nav-center">
            <a href="/docs/botify_api" class="nav-button toc">📋 Table of Contents</a>
        </div>
        <div>
            {next_button}
        </div>
    </div>

    <!-- Prism JS -->
    <script src="/assets/js/prism.js"></script>

    <!-- Auto-highlight code blocks and Copy Markdown functionality -->
    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            // Ensure Prism highlights all code blocks
            if (typeof Prism !== 'undefined') {{
                Prism.highlightAll();
            }}

            // Add copy buttons to code blocks
            document.querySelectorAll('pre code').forEach(function(block) {{
                const button = document.createElement('button');
                button.textContent = 'Copy';
                button.className = 'copy-button';

                const pre = block.parentElement;
                pre.appendChild(button);

                button.addEventListener('click', function() {{
                    navigator.clipboard.writeText(block.textContent).then(function() {{
                        button.textContent = 'Copied!';
                        setTimeout(function() {{
                            button.textContent = 'Copy';
                        }}, 2000);
                    }});
                }});
            }});

            // Copy Page Markdown functionality
            const copyMarkdownBtn = document.getElementById('copy-markdown-btn');
            if (copyMarkdownBtn) {{
                copyMarkdownBtn.addEventListener('click', async function() {{
                    const button = this;
                    const originalText = button.textContent;

                    try {{
                        // Show loading state
                        button.textContent = '⏳ Fetching...';
                        button.classList.add('copying');
                        button.disabled = true;

                        // Get the raw page content
                        const pageContent = {repr(page_content)};

                        // Copy to clipboard
                        await navigator.clipboard.writeText(pageContent);

                        // Show success state
                        button.textContent = '✅ Copied!';
                        button.classList.remove('copying');
                        button.classList.add('success');

                        // Reset after 3 seconds
                        setTimeout(function() {{
                            button.textContent = originalText;
                            button.classList.remove('success');
                            button.disabled = false;
                        }}, 3000);

                    }} catch (error) {{
                        console.error('Error copying markdown:', error);

                        // Show error state
                        button.textContent = '❌ Error';
                        button.classList.remove('copying');

                        // Reset after 3 seconds
                        setTimeout(function() {{
                            button.textContent = originalText;
                            button.disabled = false;
                        }}, 3000);
                    }}
                }});
            }}
        }});
    </script>
</body>
</html>"""

            # 🏗️ ARCHITECTURAL: Custom HTML pattern (see line 1274 for full details)
            return HTMLResponse(page_html)

        except Exception as e:
            logger.error(f"Error serving botify_api page {page_num}: {str(e)}")
            return HTMLResponse(f"Error loading page: {str(e)}", status_code=500)

