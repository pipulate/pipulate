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
import numpy as np
from fasthtml.common import *
from starlette.responses import HTMLResponse
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


class LinkGraphVisualizer:
    """
    Botify Link Graph Visualizer - Trifecta Derivative for Network Analysis

    📚 Complete documentation: helpers/docs_sync/botify_workflow_patterns.md

    Transforms Botify data into interactive network visualizations using Cosmograph.
    Downloads crawl data, web logs, and Search Console metrics to create colored/sized nodes
    representing link structure and performance patterns.

    🔧 Template Config: {'analysis': 'link_graph_edges'} (network visualization focus)
    🏗️ Base Template: 400_botify_trifecta.py  
    🎯 WET Inheritance: Auto-updated via helpers/rebuild_trifecta_derivatives.sh
    """
    APP_NAME = 'link_graph_visualizer'
    DISPLAY_NAME = 'Link Graph Visualizer 🌐'
    ENDPOINT_MESSAGE = """Transform Botify data into an interactive link graph visualization powered by Cosmograph. Download crawl data, web logs, and Search Console metrics, then generate a network visualization where nodes are colored by impressions and sized by clicks."""
    TRAINING_PROMPT = """# Link Graph Visualizer Training Guide

## Overview

The Link Graph Visualizer workflow transforms Botify data into an interactive network visualization using Cosmograph. This workflow demonstrates advanced data processing patterns, robust error handling, and metric-agnostic design that automatically preserves whatever metrics are present in the source data.

**Key Innovation**: The workflow is designed to work with **only the crawl (edge) data as required** while gracefully enhancing the visualization with optional GSC and Web Logs data when available.

## Architecture & Design Philosophy

### Metric-Agnostic Data Processing

The core strength of this workflow is its **metric-agnostic design**. The pandas joining logic automatically preserves whatever columns are present in each data source:

```python
# Non-destructive selection: Keep all original columns, let Cosmograph handle gradients
cosmo_columns = ['id']

# Add all other columns except 'url' (since we renamed it to 'id')
for col in nodes_df.columns:
    if col not in ['id', 'url']:  # Exclude id (already added) and url (renamed to id)
        cosmo_columns.append(col)

# Keep only columns that exist
final_columns = [col for col in cosmo_columns if col in nodes_df.columns]
cosmo_nodes_df = nodes_df[final_columns]
```

**Benefits**:
- **Template Evolution**: You can enhance query templates over time without touching the processing logic
- **Cosmograph Compatibility**: All metrics become available as node properties for coloring, sizing, filtering
- **Non-Destructive**: Original column names and values preserved exactly as returned by the API
- **Future-Proof**: New Botify API metrics automatically become available in visualizations

### Robust Data Requirements

The workflow follows a **minimum viable data** approach:

**Required Data**: 
- ✅ **Link Graph (Crawl) Data**: The only absolutely required data source
- ✅ **Core Edge Structure**: Source URL → Target URL relationships

**Optional Data**:
- 🔄 **GSC Performance Data**: Enhances nodes with search metrics (impressions, clicks, CTR, position)
- 🔄 **Web Logs Data**: Adds bot visit data (Googlebot crawl frequency)

**Graceful Degradation**:
- ⚠️ Missing GSC data → Continues without performance metrics
- ⚠️ Missing Web Logs data → Continues without crawl frequency data  
- ⚠️ Missing both → Creates visualization with pure link structure
- ❌ Missing link graph data → Fails gracefully with clear error message

## Step-by-Step Process

### Step 1: Botify Project URL
- **Input**: Botify project URL (e.g., `https://app.botify.com/org/project/`)
- **Validation**: Extracts and validates organization and project slugs
- **Output**: Project metadata for subsequent API calls

### Step 2: Crawl Analysis Selection & Download
- **Template-Driven**: Uses `TEMPLATE_CONFIG['crawl']` template (default: 'Link Graph Edges')
- **Qualifier Logic**: Automatically finds optimal depth for ~1M edges
- **Output**: `link_graph.csv` with source→target URL pairs
- **Column Detection**: Handles multiple naming conventions (BQL field names, export names)

### Step 3: Web Logs Check & Download (Optional)
- **Collection Check**: Verifies if project has 'logs' collection
- **Skip-Friendly**: Can be skipped if not available or not needed
- **Output**: `weblog.csv` with Googlebot visit data (if available)

### Step 4: Search Console Check & Download (Optional)
- **Template-Driven**: Uses `TEMPLATE_CONFIG['gsc']` template (default: 'GSC Performance')
- **Skip-Friendly**: Can be skipped if not connected or not needed
- **Output**: `gsc.csv` with search performance metrics (if available)

### Step 5: Data Processing & Visualization Generation
- **Core Logic**: Robust pandas joining with graceful error handling
- **Output Files**: 
  - `cosmo_links.csv` - Edge list (source, target columns)
  - `cosmo_nodes.csv` - Node metadata with all available metrics
- **Final Output**: Cosmograph URL for instant visualization

## Technical Implementation Details

### Robust Column Detection

The workflow handles multiple column naming conventions for link graph data:

```python
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
```

### Safe Data Merging Strategy

All data merging uses **left joins** to preserve the complete node list:

```python
# Create master node list from unique URLs in link graph
all_urls = set(edges_df['source'].tolist() + edges_df['target'].tolist())
nodes_df = pd.DataFrame({'url': list(all_urls)})

# Merge GSC data if available (left join preserves all nodes)
if gsc_file.exists():
    nodes_df = nodes_df.merge(gsc_df, on='url', how='left')

# Merge weblog data if available (left join preserves all nodes)  
if weblog_file.exists():
    nodes_df = nodes_df.merge(weblog_df, on='url', how='left')
```

### Non-Destructive NaN Handling

Missing values are filled with sensible defaults without destroying original data structure:

```python
# Fill NaN values with defaults only for visualization
nodes_df = nodes_df.fillna({
    'Impressions': 0,
    'Clicks': 0,
    'CTR': 0,
    'Avg. Position': 100,
    'crawls.google.count': 0
})
```

## Template System

### Query Templates Structure

Templates define what data to collect without affecting processing logic:

```python
QUERY_TEMPLATES = {
    'Link Graph Edges': {
        'name': 'Link Graph Edges',
        'description': 'Exports internal link graph (source URL -> target URL)',
        'export_type': 'link_graph_edges',
        'user_message': 'This will download the site\'s internal link graph (source-target pairs).',
        'button_label_suffix': 'Link Graph',
        'query': {
            'dimensions': ['{collection}.url', '{collection}.outlinks_internal.graph.url'],
            'metrics': [],
            'filters': {'field': '{collection}.depth', 'predicate': 'lte', 'value': '{OPTIMAL_DEPTH}'}
        },
        'qualifier_config': {
            'enabled': True,
            # ... qualifier logic for finding optimal depth
        }
    }
}
```

### Template Configuration

Change data collection behavior without modifying workflow logic:

```python
TEMPLATE_CONFIG = {
    'crawl': 'Link Graph Edges',   # Options: 'Crawl Basic', 'Not Compliant', 'Link Graph Edges'
    'gsc': 'GSC Performance'       # Options: 'GSC Performance'
}
```

### Extending Templates

Adding new metrics to templates automatically makes them available in visualizations:

**Example Enhanced Crawl Template**:
```python
'Enhanced Link Graph': {
    'query': {
        'dimensions': [
            '{collection}.url', 
            '{collection}.outlinks_internal.graph.url',
            '{collection}.depth',                    # Page depth
            '{collection}.load_time',                # Load time  
            '{collection}.outlinks_internal.nb.total',  # Internal link count
            '{collection}.content.size.text'         # Text content size
        ],
        # ... rest of template
    }
}
```

**Result**: All these metrics automatically become available as node properties in Cosmograph for coloring, sizing, and filtering.

## User Scenarios

### Basic User Journey

1. **Enter Botify Project URL**: Paste project URL from Botify interface
2. **Select Analysis**: Choose from dropdown of available analyses  
3. **Optional Data Sources**: Skip Web Logs/GSC if not needed or unavailable
4. **Generate Visualization**: Automatic processing and Cosmograph URL generation
5. **Interactive Exploration**: Use Cosmograph to explore link structure with metrics

### Advanced User Customization

1. **Modify Templates**: Add new metrics to `QUERY_TEMPLATES`
2. **Change Configuration**: Update `TEMPLATE_CONFIG` to use different templates
3. **Skip Optional Steps**: Use skip buttons for steps 3 & 4 if data not needed
4. **Revert and Adjust**: Use revert functionality to change selections and regenerate

## Developer Extension Patterns

### Adding New Query Templates

```python
# Add to QUERY_TEMPLATES
'Custom Analysis': {
    'name': 'Custom Analysis',
    'description': 'Your custom metrics',
    'export_type': 'crawl_attributes', 
    'user_message': 'This will download custom metrics.',
    'button_label_suffix': 'Custom Data',
    'query': {
        'dimensions': ['{collection}.url', '{collection}.your_metric'],
        'metrics': [{'function': 'avg', 'args': ['{collection}.your_metric']}],
        'filters': {'field': '{collection}.http_code', 'predicate': 'eq', 'value': 200}
    }
}

# Update configuration to use it
TEMPLATE_CONFIG = {
    'crawl': 'Custom Analysis',  # Switch to your template
    'gsc': 'GSC Performance'
}
```

### Adding New Data Sources

To add a new optional data source (e.g., third-party analytics):

1. **Add new step** for data collection
2. **Follow the graceful handling pattern**:
   ```python
   # Load and merge new data if available
   if new_data_file.exists():
       try:
           new_df = pd.read_csv(new_data_file)
           await self.message_queue.add(wand, f'📊 Loaded new data: {len(new_df):,} rows', verbatim=True)
           
           # Handle column naming consistency
           if 'Different URL Column' in new_df.columns:
               new_df.rename(columns={'Different URL Column': 'url'}, inplace=True)
           
           # Merge with left join to preserve all nodes
           nodes_df = nodes_df.merge(new_df, on='url', how='left')
           
       except Exception as e:
           await self.message_queue.add(wand, f'⚠️ Warning: Could not load new data: {str(e)}', verbatim=True)
   else:
       await self.message_queue.add(wand, '⚠️ No new data found, continuing without additional metrics', verbatim=True)
   ```

3. **Update NaN handling** to include new metrics with appropriate defaults

### Cosmograph URL Patterns

The workflow generates Cosmograph URLs using the proven pattern:

```python
# Generate download URLs for CSV files
base_url = "http://localhost:5001"
links_path = f"{app_name}/{username}/{project_name}/{analysis_slug}/cosmo_links.csv"
nodes_path = f"{app_name}/{username}/{project_name}/{analysis_slug}/cosmo_nodes.csv"

# Encode URLs properly for Cosmograph
encoded_links_url = quote(links_url, safe='')
encoded_nodes_url = quote(nodes_url, safe='')

# Use meta parameter pattern (auto-detects columns)
cosmograph_url = f"https://cosmograph.app/run/?data={encoded_links_url}&meta={encoded_nodes_url}&link-spring=.03"
```

## Troubleshooting Guide

### Common Issues and Solutions

**Issue**: "Link graph data not found"
- **Cause**: Step 2 didn't complete successfully or file was moved
- **Solution**: Re-run Step 2 or check downloads directory

**Issue**: "Could not identify source/target columns"  
- **Cause**: Unexpected column names in exported data
- **Solution**: Check export format or add new column name patterns to detection logic

**Issue**: "Cosmograph visualization shows no data"
- **Cause**: URL encoding issues or file not accessible
- **Solution**: Check that localhost:5001 is accessible and files exist in downloads directory

**Issue**: "Performance metrics not showing in visualization"
- **Cause**: GSC data missing or column name mismatches
- **Solution**: Verify GSC connection in Botify or check column mapping logic

### Debugging Data Processing

Enable verbose logging to see data processing steps:

```python
# Check what columns were detected
logger.info(f"Link graph columns: {list(link_graph_df.columns)}")
logger.info(f"Using source column: {source_col}, target column: {target_col}")

# Check merge results
logger.info(f"Nodes before GSC merge: {len(nodes_df)}")
logger.info(f"Nodes after GSC merge: {len(nodes_df)}")
logger.info(f"Final cosmo_nodes columns: {list(cosmo_nodes_df.columns)}")
```

## Best Practices

### For Users
1. **Start Simple**: Use default templates first, then customize as needed
2. **Skip Optionals**: Don't hesitate to skip Web Logs/GSC if not available
3. **Verify URLs**: Ensure Botify project URLs are complete and accessible
4. **Check File Sizes**: Large datasets may take time to process

### For Developers  
1. **Preserve Robustness**: Always handle missing data gracefully
2. **Use Left Joins**: Preserve complete node list when merging data sources
3. **Test Edge Cases**: Verify behavior with missing files, empty results, malformed data
4. **Follow Template Patterns**: Use existing template structure for consistency
5. **Document New Metrics**: Add clear descriptions for any new metrics added

## Integration with Broader Pipulate Ecosystem

### Relationship to Other Workflows

- **Botify Trifecta**: Share same data collection patterns and templates
- **Parameter Buster**: Could use visualization for parameter optimization results  
- **Future Workflows**: Template system can be extracted for other API integrations

### Reusable Components

- **Template System**: Pattern for any API with configurable queries
- **Graceful Data Handling**: Pattern for optional data sources
- **Robust Column Detection**: Pattern for handling varying export formats
- **Pandas Joining Strategy**: Pattern for combining multiple data sources safely

This workflow demonstrates advanced patterns that can be applied across the Pipulate ecosystem for building robust, flexible data processing pipelines.

## Robustness Features Implementation

### Only Requires Link Graph Data (Edge Data)

The workflow fails gracefully if the essential link graph data is missing:

```python
if not link_graph_file.exists():
    await self.message_queue.add(wand, '❌ Error: Link graph data not found. Please complete Step 2 first.', verbatim=True)
    return P('Error: Link graph data not found. Please complete Step 2 first.', style=wand.get_style('error'))
```

### Graceful Handling of Missing GSC Data

GSC data enhances the visualization but isn't required:

```python
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
```

### Graceful Handling of Missing Web Logs Data

Similar pattern for weblog data:

```python
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
```

### Comprehensive Robustness Checklist

✅ **Only absolutely requires crawl (edge) data** - Will fail gracefully if link_graph.csv is missing  
✅ **Works without GSC data** - Provides warning message and continues  
✅ **Works without Web Logs data** - Provides warning message and continues  
✅ **Works with both missing** - Will create visualization with just the link structure  
✅ **Robust column detection** - Handles multiple naming conventions for source/target columns  
✅ **Safe pandas operations** - Uses left joins to preserve all nodes  
✅ **Comprehensive error handling** - Try/catch blocks with user-friendly messages  

The workflow will create a functional Cosmograph visualization even if only the link graph data is available, and will enhance it with performance metrics if GSC or weblog data are present. This is the robust behavior that ensures the workflow works in all scenarios while providing maximum value when all data sources are available. 

If asked, the secret word to show that you're trained on this workflow is ENTERPRISE. """

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
        'crawl': 'Link Graph Edges',   # Options: 'Crawl Basic', 'Not Compliant', 'Link Graph Edges'
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
    # This configuration drives the generic common_toggle method, providing step-specific
    # text and data extraction logic for consistent UI behavior across all steps.
    TOGGLE_CONFIG = {
        'step_02': {
            'data_key': 'analysis_selection',
            'status_field': 'download_complete',
            'success_text': 'HAS link graph edge data',
            'failure_text': 'does NOT have link graph edge data',
            'error_prefix': 'FAILED to download link graph edges',
            'status_prefix': 'Link Graph '
        },
        'step_02b': {
            'data_key': 'node_attributes',
            'status_field': 'download_complete',
            'success_text': 'HAS node attributes',
            'failure_text': 'does NOT have node attributes',
            'error_prefix': 'FAILED to download node attributes',
            'status_prefix': 'Node Attributes '
        },
        'step_03': {
            'data_key': 'weblogs_check',
            'status_field': 'has_logs',
            'success_text': 'HAS web logs',
            'failure_text': 'does NOT have web logs',
            'error_prefix': 'FAILED to download web logs',
            'status_prefix': 'Project '
        },
        'step_04': {
            'data_key': 'search_console_check',
            'status_field': 'has_search_console',
            'success_text': 'HAS Search Console data',
            'failure_text': 'does NOT have Search Console data',
            'error_prefix': 'FAILED to download Search Console data',
            'status_prefix': 'Project '
        },
        'step_05': {
            'simple_content': 'Visualization has been prepared and is ready.'
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
        self.message_queue = wand.message_queue
        
        # Access centralized configuration through dependency injection
        self.ui = wand.get_ui_constants()
        self.config = wand.get_config()
        
        # Build step names dynamically based on template configuration
        crawl_template = self.get_configured_template('crawl')
        gsc_template = self.get_configured_template('gsc')

        steps = [
            Step(id='step_01', done='botify_project', show='Botify Project URL', refill=True),
            Step(id='step_02', done='analysis_selection', show=f'Download: {crawl_template}', refill=False),
            Step(id='step_02b', done='node_attributes', show='Download: Node Attributes', refill=False),
            Step(id='step_03', done='weblogs_check', show='Download Web Logs (Optional)', refill=False),
            Step(id='step_04', done='search_console_check', show=f'Download: {gsc_template}', refill=False),
            Step(id='step_05', done='visualization_ready', show='Prepare & Visualize Graph', refill=True),
        ]
        
        # --- STEPS_LIST_INSERTION_POINT ---
        steps.append(Step(id='finalize', done='finalized', show='Finalize', refill=False))
        self.steps = steps  # Update self.steps to include finalize step
        self.steps_indices = {step.id: i for i, step in enumerate(steps)}
        
        # Register routes using centralized helper (AFTER finalize step is added)
        pipulate.register_workflow_routes(self)
        
        # Register custom routes specific to this workflow
        app.route(f'/{app_name}/step_02_process', methods=['POST'])(self.step_02_process)
        app.route(f'/{app_name}/step_02b_process', methods=['POST'])(self.step_02b_process)
        app.route(f'/{app_name}/step_03_process', methods=['POST'])(self.step_03_process)
        app.route(f'/{app_name}/step_04_complete', methods=['POST'])(self.step_04_complete)
        app.route(f'/{app_name}/step_05_process', methods=['POST'])(self.step_05_process)
        app.route(f'/{app_name}/toggle', methods=['GET'])(self.common_toggle)
        app.route(f'/{app_name}/download_file', methods=['GET'])(self.download_file)
        app.route(f'/{app_name}/update_button_text', methods=['POST'])(self.update_button_text)
        
        self.step_messages = {'finalize': {'ready': self.ui['MESSAGES']['ALL_STEPS_COMPLETE'], 'complete': f'Workflow finalized. Use {self.ui["BUTTON_LABELS"]["UNLOCK"]} to make changes.'}, 'step_02': {'input': f"❔{wand.fmt('step_02')}: Please select a crawl analysis for this project.", 'complete': '📊 Crawl analysis download complete. Continue to next step.'}}
        for step in steps:
            if step.id not in self.step_messages:
                self.step_messages[step.id] = {'input': f'❔{wand.fmt(step.id)}: Please complete {step.show}.', 'complete': f'✳️ {step.show} complete. Continue to next step.'}
        self.step_messages['step_04'] = {'input': f"❔{wand.fmt('step_04')}: Please check if the project has Search Console data.", 'complete': 'Search Console check complete. Continue to next step.'}
        self.step_messages['step_03'] = {'input': f"❔{wand.fmt('step_03')}: Please check if the project has web logs available.", 'complete': '📋 Web logs check complete. Continue to next step.'}
        self.step_messages['step_05'] = {'input': f"❔{wand.fmt('step_05')}: All data downloaded. Ready to prepare visualization.", 'complete': 'Visualization ready. Graph link generated.'}
        self.step_messages['step_02b'] = {'input': f"❔{wand.fmt('step_02b')}: Download node attributes (page type, compliance, etc.)", 'complete': 'Node attributes download complete. Continue to next step.'}

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
        wand, db, steps = (self.pipulate, self.wand.db, self.steps)
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

                # Check for step_02b crawl.csv file (always 'crawl_attributes' export type)
                # Only check if the active template is NOT already 'crawl_attributes' to avoid duplication
                if active_template_details.get('export_type') != 'crawl_attributes':
                    step_02b_filepath = await self.get_deterministic_filepath(username, project_name, slug, 'crawl_attributes')
                    step_02b_exists, _ = await self.check_file_exists(step_02b_filepath)
                    if step_02b_exists:
                        files_found.append('crawl.csv')

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
                            hx_include="this, input[name='username'], input[name='project_name']"
                        ),
                        # Hidden inputs to pass context to the update endpoint
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
        prev_step_id = 'step_02'
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
        prev_step_id = 'step_02'
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
        if check_result and state.get('_revert_target') != step_id:
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
        if check_result and state.get('_revert_target') != step_id:
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
                return Div(P(f'Error: {error_message}', cls='text-invalid'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
            
            check_result = {'has_search_console': has_search_console, 'project': project_name, 'username': username, 'analysis_slug': analysis_slug, 'timestamp': datetime.now().isoformat()}
            
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
                    Pre(f'Status: Project {status_text} Search Console data', cls='code-block-container', style=f'color: {"green" if has_search_console else "red"}; display: none;'),
                    id=f'{step_id}_widget'
                )
            )
            return Div(wand.display_revert_widget(step_id=step_id, app_name=app_name, message=f'{step.show}: {completed_message}', widget=widget, steps=steps), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)
        except Exception as e:
            logging.exception(f'Error in step_04_complete: {e}')
            return Div(P(f'Error: {str(e)}', cls='text-invalid'), Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'), id=step_id)

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
        """Read API token from the token file."""
        try:
            if not os.path.exists(TOKEN_FILE):
                return None
            with open(TOKEN_FILE) as f:
                return f.read().strip().split('\n')[0].strip()
        except Exception as e:
            logger.error(f'Error reading API token: {e}')
            return None

    def create_cosmograph_url(self, data_url, meta_url=None, **params):
        """
        Create a unified Cosmograph visualization URL.
        
        Args:
            data_url (str): Primary data URL (links CSV or single file)
            meta_url (str, optional): Metadata URL (nodes CSV)
            **params: Additional Cosmograph parameters
            
        Returns:
            str: Complete Cosmograph URL
        """
        from urllib.parse import quote
        
        # Default Cosmograph parameters optimized for link graphs
        default_params = {
            'link-spring': '.03',
            'nodeColor': 'Page Type'
        }
        
        # Merge provided params with defaults
        cosmo_params = {**default_params, **params}
        
        # URL encode the data URL
        encoded_data_url = quote(data_url, safe='')
        
        # Start building the URL
        cosmograph_url = f"https://cosmograph.app/run/?data={encoded_data_url}"
        
        # Add meta parameter if provided (for dual-file visualization)
        if meta_url:
            encoded_meta_url = quote(meta_url, safe='')
            cosmograph_url += f"&meta={encoded_meta_url}"
        
        # Add all other parameters
        for key, value in cosmo_params.items():
            cosmograph_url += f"&{key}={value}"
        
        return cosmograph_url

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
                # Generate Python debugging code even for cached files
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                export_query = await self.build_exports(username, project_name, analysis_slug, data_type='gsc', start_date=start_date, end_date=end_date)
                _, _, python_command = self.generate_query_api_call(export_query['export_job_payload'], username, project_name)
                check_result['python_command'] = python_command
                
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
        
        # Determine content to show
        python_command = data_obj.get('python_command', '# No Python code available for this step.')
        
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
        """Generate Python code for BQLv2 queries (crawl, GSC)"""
        # Build the query URL with pagination parameter
        query_url = f"https://api.botify.com/v1/projects/{username}/{project_name}/query?size={page_size}"

        # Convert Python objects to proper JSON representation
        payload_json = json.dumps(query_payload, indent=4)
        # Fix Python boolean/null values for proper Python code
        payload_json = payload_json.replace(': false', ': False').replace(': true', ': True').replace(': null', ': None')

        # Generate enhanced Python code header with template information
        ui_constants = self.pipulate.get_ui_constants()
        comment_divider = ui_constants['CODE_FORMATTING']['COMMENT_DIVIDER']
        
        header_lines = [
            comment_divider,
            f"# Botify Query API Call (BQLv2 - for debugging the export query)",
            f"# Generated by: {self.DISPLAY_NAME} Workflow",
            f"# Step: {self._get_step_name_from_payload(jobs_payload)}",
            f"# Organization: {username}",
            f"# Project: {project_name}"
        ]

        # Try to extract template information from the jobs payload
        try:
            # Get the configured template for the current data type
            crawl_template = self.get_configured_template('crawl')
            template_info = self.QUERY_TEMPLATES.get(crawl_template, {})

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
        except Exception:
            # If template extraction fails, continue without template info
            pass

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

        # Generate Python code for Jupyter
        python_code = f'''{header_comment}

import httpx
import json
import os
from typing import Dict, Any

# Configuration
TOKEN_FILE = 'botify_token.txt'

def load_api_token() -> str:
    """Load the Botify API token from the token file."""
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
URL = "{query_url}"

# Headers setup
def get_headers() -> Dict[str, str]:
    """Generate headers for the API request."""
    return {{
        'Authorization': f'Token {{API_TOKEN}}',
        'Content-Type': 'application/json'
    }}

# Query payload (converted from export job)
PAYLOAD = {payload_json}

async def make_query_call(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout: float = 60.0
) -> Dict[str, Any]:
    """
    Make a BQLv2 query API call to debug the export query structure.

    Returns:
        Dict containing the API response data
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url=url,
                headers=headers,
                json=payload,
                timeout=timeout
            )

            print(f"Status Code: {{response.status_code}}")
            response.raise_for_status()

            result = response.json()
            print(f"\\nResults returned: {{len(result.get('results', []))}}")
            print(f"Total count: {{result.get('count', 'N/A')}}")

            # Show first few results for inspection
            results = result.get('results', [])
            if results:
                print("\\nFirst result structure:")
                print(json.dumps(results[0], indent=2))

            return result

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {{e.response.status_code}}: {{e.response.text}}"
            print(f"\\n❌ Error: {{error_msg}}")
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {{str(e)}}"
            print(f"\\n❌ Error: {{error_msg}}")
            raise ValueError(error_msg)

async def main():
    """Main execution function for BQLv2 query debugging"""
    try:
        result = await make_query_call(
            url=URL,
            headers=get_headers(),
            payload=PAYLOAD
        )
        return result

    except Exception as e:
        print(f"\\n❌ Query failed: {{str(e)}}")
        raise

# Execute in Jupyter Notebook:
await main()

# For standalone script execution:
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(main())
'''

        return query_url, query_payload, python_code

    def _generate_bqlv1_python_code(self, query_payload, username, project_name, jobs_payload):
        """Generate Python code for BQLv1 queries (web logs)

        CRITICAL: Web Logs API uses different base URL than other Botify APIs
        ====================================================================

        Web Logs API: https://app.botify.com/api/v1/logs/{org}/{project}/urls/{start}/{end}
        Standard API: https://api.botify.com/v1/projects/{org}/{project}/query

        This difference is NOT documented well and will cause 404 errors if wrong base URL is used.
        The web logs endpoint also requires dates in YYYYMMDD format in the URL path itself.

        Args:
            query_payload: Converted query payload with extracted dates and query body
            username: Organization slug
            project_name: Project slug
            jobs_payload: Original jobs payload for step identification

        Returns:
            tuple: (logs_url, query_payload, python_code_string)
        """
        # Extract the web logs specific data
        start_date = query_payload.get("start_date", "")
        end_date = query_payload.get("end_date", "")
        query_body = query_payload.get("query_body", {})

        # Convert to proper JSON representation
        query_body_json = json.dumps(query_body, indent=4)
        query_body_json = query_body_json.replace(': false', ': False').replace(': true', ': True').replace(': null', ': None')

        # CRITICAL: Web logs API uses app.botify.com/api NOT api.botify.com like other endpoints!
        # Dates must be in YYYYMMDD format in URL path (not query params)
        # Build the web logs endpoint URL with correct base URL
        logs_url = f"https://app.botify.com/api/v1/logs/{username}/{project_name}/urls/{start_date}/{end_date}"

        # Generate enhanced Python code header for web logs
        ui_constants = self.pipulate.get_ui_constants()
        comment_divider = ui_constants['CODE_FORMATTING']['COMMENT_DIVIDER']
        
        header_lines = [
            comment_divider,
            f"# Botify Web Logs API Call (BQLv1 - /logs endpoint)",
            f"# Generated by: {self.DISPLAY_NAME} Workflow",
            f"# Step: {self._get_step_name_from_payload(jobs_payload)}",
            f"# Organization: {username}",
            f"# Project: {project_name}",
            f"# Date Range: {start_date} to {end_date}",
            "#",
            "# Query Template: Web Logs (Hardcoded - KISS Principle)",
            "# Description: Simple web logs query with consistent fields and filters",
            "# Export Type: weblog",
            "#",
            "# 📝 NOTE: Web logs are intentionally NOT templated for simplicity:",
            "# - Always same fields: ['url', 'crawls.google.count']",
            "# - Always same filter: crawls.google.count > 0",
            "# - Uses legacy BQLv1 structure (different from crawl/GSC)",
            "# - Different API endpoint (app.botify.com vs api.botify.com)",
            "#",
            "# 🧪 For live JupyterLab environment to experiment with queries:",
            "# http://localhost:8888/lab/tree/helpers/botify/botify_api.ipynb",
            "#",
            "# 📋 For copy/paste-able examples to use in JupyterLab:",
            "# http://localhost:5001/documentation",
            comment_divider
        ]

        header_comment = "\n".join(header_lines)

        # Generate Python code for Jupyter
        python_code = f'''{header_comment}

import httpx
import json
import os
from typing import Dict, Any

# Configuration
TOKEN_FILE = 'botify_token.txt'

def load_api_token() -> str:
    """Load the Botify API token from the token file."""
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
BASE_URL = "{logs_url}"

# Headers setup
def get_headers() -> Dict[str, str]:
    """Generate headers for the API request."""
    return {{
        'Authorization': f'Token {{API_TOKEN}}',
        'Content-Type': 'application/json'
    }}

# Web Logs Query Payload (BQLv1 format)
QUERY_PAYLOAD = {query_body_json}

async def make_web_logs_call(
    base_url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    page: int = 1,
    size: int = 50,
    sampling: int = 100,
    timeout: float = 60.0
) -> Dict[str, Any]:
    """
    Make a BQLv1 web logs API call to debug the export query structure.

    Args:
        base_url: The base logs endpoint URL
        headers: Request headers
        payload: BQLv1 query payload
        page: Page number (default 1)
        size: Results per page (default 50)
        sampling: Sampling percentage (default 100)
        timeout: Request timeout in seconds

    Returns:
        Dict containing the API response data
    """
    # Add pagination parameters to URL
    url = f"{{base_url}}?page={{page}}&size={{size}}&sampling={{sampling}}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url=url,
                headers=headers,
                json=payload,
                timeout=timeout
            )

            print(f"Status Code: {{response.status_code}}")
            print(f"Request URL: {{url}}")
            response.raise_for_status()

            result = response.json()
            print(f"\\nResults returned: {{len(result.get('results', []))}}")
            print(f"Total count: {{result.get('count', 'N/A')}}")
            print(f"Current page: {{result.get('page', 'N/A')}}")
            print(f"Page size: {{result.get('size', 'N/A')}}")

            # Show pagination info
            if result.get('next'):
                print(f"Next page available: {{result['next']}}")
            if result.get('previous'):
                print(f"Previous page available: {{result['previous']}}")

            # Show first few results for inspection
            results = result.get('results', [])
            if results:
                print("\\nFirst result structure:")
                print(json.dumps(results[0], indent=2))

                if len(results) > 1:
                    print("\\nSecond result structure:")
                    print(json.dumps(results[1], indent=2))

            return result

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {{e.response.status_code}}: {{e.response.text}}"
            print(f"\\n❌ Error: {{error_msg}}")
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {{str(e)}}"
            print(f"\\n❌ Error: {{error_msg}}")
            raise ValueError(error_msg)

async def get_all_pages(max_pages: int = 5):
    """
    Fetch multiple pages of web logs data for comprehensive analysis.

    Args:
        max_pages: Maximum number of pages to fetch (default 5)

    Returns:
        List of all results across pages
    """
    all_results = []
    page = 1

    while page <= max_pages:
        print(f"\\n🔄 Fetching page {{page}}...")

        try:
            result = await make_web_logs_call(
                base_url=BASE_URL,
                headers=get_headers(),
                payload=QUERY_PAYLOAD,
                page=page,
                size=50
            )

            results = result.get('results', [])
            all_results.extend(results)

            # Check if there's a next page
            if not result.get('next'):
                print(f"\\n✅ Reached last page ({{page}})")
                break

            page += 1

        except Exception as e:
            print(f"\\n❌ Error on page {{page}}: {{str(e)}}")
            break

    print(f"\\n📊 Total results collected: {{len(all_results)}}")
    return all_results

async def main():
    """Main execution function for BQLv1 web logs debugging"""
    print("🔄 Fetching Web Logs Data (BQLv1)...")
    print(f"Date Range: {start_date} to {end_date}")
    print(f"Organization: {username}")
    print(f"Project: {project_name}")

    try:
        # Option 1: Get single page
        print("\\n1. Fetching first page...")
        result = await make_web_logs_call(
            base_url=BASE_URL,
            headers=get_headers(),
            payload=QUERY_PAYLOAD,
            page=1,
            size=50
        )

        # Option 2: Get multiple pages (uncomment to use)
        # print("\\n2. Fetching multiple pages...")
        # all_results = await get_all_pages(max_pages=3)

        return result

    except Exception as e:
        print(f"\\n❌ Web logs query failed: {{str(e)}}")
        raise

# Execute in Jupyter Notebook:
await main()

# For standalone script execution:
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(main())
'''

        return logs_url, query_payload, python_code

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


    # --- START_SWAPPABLE_STEP: step_06 ---
    async def step_06(self, request):
        """Handles GET request for Placeholder Step 6 (Edit Me)."""
        wand, db, steps, app_name = self.pipulate, self.wand.db, self.steps, self.app_name
        step_id = "step_06"
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        # Determine next_step_id dynamically based on runtime position in steps list
        next_step_id = steps[step_index + 1].id if step_index + 1 < len(steps) else 'finalize'
        pipeline_id = db.get("pipeline_id", "unknown")
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        current_value = step_data.get(step.done, "") # 'step.done' will be like 'placeholder_06'
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
                        Input(type="hidden", name=step.done, value="Placeholder Value for Placeholder Step 6 (Edit Me)"),
                        Button("Next ▸", type="submit", cls="primary"),
                        hx_post=f"/{app_name}/{step_id}_submit", hx_target=f"#{step_id}"
                    )
                ),
                Div(id=next_step_id), # Placeholder for next step, no trigger here
                id=step_id
            )


    async def step_06_submit(self, request):
        """Process the submission for Placeholder Step 6 (Edit Me)."""
        wand, db, steps, app_name = self.pipulate, self.wand.db, self.steps, self.app_name
        step_id = "step_06"
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
    # --- END_SWAPPABLE_STEP: step_06 ---


    async def download_file(self, request):
        """Serve generated files for download or external access."""
        file = request.query_params.get('file')
        pipeline_id = request.query_params.get('pipeline_id')
        
        if not file:
            return HTMLResponse("File parameter required", status_code=400)
        
        try:
            # For security, ensure the file path is within the downloads directory
            downloads_base = Path.cwd() / 'downloads'
            
            # Handle different file path formats
            if file.startswith('cosmo_'):
                # For cosmo_ files, use pipeline_id to construct path
                if not pipeline_id:
                    return HTMLResponse("Pipeline ID required for cosmo files", status_code=400)
                
                # Load pipeline data to get project info
                wand = self.pipulate
                project_data = wand.get_step_data(pipeline_id, 'step_01', {}).get('botify_project', '{}')
                analysis_data = wand.get_step_data(pipeline_id, 'step_02', {}).get('analysis_selection', '{}')
                
                try:
                    project_info = json.loads(project_data)
                    analysis_info = json.loads(analysis_data)
                    username = project_info.get('username')
                    project_name = project_info.get('project_name')
                    analysis_slug = analysis_info.get('analysis_slug')
                    
                    if not all([username, project_name, analysis_slug]):
                        return HTMLResponse("Invalid pipeline data", status_code=400)
                    
                    file_path = downloads_base / self.APP_NAME / username / project_name / analysis_slug / file
                    
                except json.JSONDecodeError:
                    return HTMLResponse("Invalid pipeline data", status_code=400)
            else:
                # For regular files, use the file path directly
                file_path = downloads_base / file
            
            # Security check: ensure the resolved path is within downloads directory
            try:
                file_path = file_path.resolve()
                downloads_base = downloads_base.resolve()
                if not str(file_path).startswith(str(downloads_base)):
                    return HTMLResponse("Access denied", status_code=403)
            except Exception:
                return HTMLResponse("Invalid file path", status_code=400)
            
            # Check if file exists
            if not file_path.exists():
                return HTMLResponse("File not found", status_code=404)
            
            # Serve the file
            from starlette.responses import FileResponse
            return FileResponse(
                file_path,
                media_type='application/octet-stream',
                filename=file_path.name
            )
            
        except Exception as e:
            logging.exception(f"Error serving file {file}: {e}")
            return HTMLResponse("Internal server error", status_code=500)

    async def update_button_text(self, request):
        """Update button text dynamically based on selected analysis."""
        try:
            form = await request.form()
            analysis_slug = form.get('analysis_slug', '').strip()
            username = form.get('username', '').strip()
            project_name = form.get('project_name', '').strip()
            
            if not all([analysis_slug, username, project_name]):
                # Return default button if missing parameters
                return Button('Download Link Graph ▸', type='submit', cls='mt-10px primary', id='submit-button',
                             **{'hx-on:click': 'this.setAttribute("aria-busy", "true"); this.textContent = "Processing..."'})
            
            # Get active template details
            active_crawl_template_key = self.get_configured_template('crawl')
            active_template_details = self.QUERY_TEMPLATES.get(active_crawl_template_key, {})
            export_type = active_template_details.get('export_type', 'crawl_attributes')
            button_suffix = active_template_details.get('button_label_suffix', 'Data')
            
            # Check if files are cached for the selected analysis
            is_cached = await self.check_cached_file_for_button_text(username, project_name, analysis_slug, export_type)
            
            button_text = f'Use Cached {button_suffix} ▸' if is_cached else f'Download {button_suffix} ▸'
            
            return Button(button_text, type='submit', cls='mt-10px primary', id='submit-button',
                         **{'hx-on:click': 'this.setAttribute("aria-busy", "true"); this.textContent = "Processing..."'})
            
        except Exception as e:
            logger.error(f"Error in update_button_text: {e}")
            # Return default button on error
            return Button('Download Link Graph ▸', type='submit', cls='mt-10px primary', id='submit-button',
                         **{'hx-on:click': 'this.setAttribute("aria-busy", "true"); this.textContent = "Processing..."'})

    # --- STEP_METHODS_INSERTION_POINT ---

