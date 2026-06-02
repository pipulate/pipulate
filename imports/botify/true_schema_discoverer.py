# modules.botify.true_schema_discoverer.py
import os
import json
import httpx
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set
import asyncio

# --- Configuration ---
TOKEN_FILE = 'botify_token.txt'
CONFIG_FILE = Path(__file__).parent / 'config.json'

class BotifySchemaDiscoverer:
    """True Botify API schema discovery using official datamodel endpoints."""
    
    def __init__(self, org: str, project: str, analysis: str, api_key: str):
        self.org = org
        self.project = project
        self.analysis = analysis
        self.api_key = api_key
        self.headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}
        self.base_url = f"https://api.botify.com/v1/analyses/{org}/{project}/{analysis}"
        
    async def discover_complete_schema(self) -> Dict[str, Any]:
        """True schema discovery using Botify's official datamodel endpoints."""
        print("🔍 Starting TRUE Botify API schema discovery...")
        print(f"📊 Project: {self.org}/{self.project}")
        print(f"📅 Analysis: {self.analysis}")
        
        discovery_results = {
            "project_info": {
                "org": self.org,
                "project": self.project,
                "analysis": self.analysis,
                "discovery_timestamp": datetime.now().isoformat()
            },
            "datamodel": {},
            "datasets": {},
            "collections_discovered": [],
            "total_fields_discovered": 0,
            "discovery_method": "official_datamodel_endpoints"
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Step 1: Get the complete datamodel
            print("\n📋 Phase 1: Discovering Datamodel...")
            datamodel = await self._get_datamodel(client)
            if datamodel:
                discovery_results["datamodel"] = datamodel
                print(f"✅ Datamodel retrieved successfully")
            
            # Step 2: Get available datasets
            print("\n📊 Phase 2: Discovering Datasets...")
            datasets = await self._get_datasets(client)
            if datasets:
                discovery_results["datasets"] = datasets
                print(f"✅ Datasets retrieved successfully")
            
            # Step 3: Parse and analyze the discovered schema
            print("\n🔬 Phase 3: Analyzing Discovered Schema...")
            self._analyze_discovered_schema(discovery_results)
            
        return discovery_results
    
    async def _get_datamodel(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Get the complete datamodel using the official endpoint."""
        try:
            url = f"{self.base_url}/urls/datamodel"
            print(f"  🌐 Fetching: {url}")
            
            response = await client.get(url, headers=self.headers)
            
            if response.status_code == 200:
                datamodel = response.json()
                print(f"  ✅ Datamodel contains {len(datamodel)} top-level elements")
                return datamodel
            else:
                print(f"  ❌ Datamodel request failed: {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"     Error: {error_detail}")
                except:
                    print(f"     Error: {response.text}")
                return {}
                
        except Exception as e:
            print(f"  ❓ Datamodel request error: {e}")
            return {}
    
    async def _get_datasets(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Get available datasets using the official endpoint."""
        try:
            url = f"{self.base_url}/urls/datasets"
            print(f"  🌐 Fetching: {url}")
            
            # Try with deprecated_fields=True to get complete schema
            params = {"deprecated_fields": True}
            response = await client.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                datasets = response.json()
                print(f"  ✅ Datasets retrieved successfully")
                return datasets
            else:
                print(f"  ❌ Datasets request failed: {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"     Error: {error_detail}")
                except:
                    print(f"     Error: {response.text}")
                return {}
                
        except Exception as e:
            print(f"  ❓ Datasets request error: {e}")
            return {}
    
    def _analyze_discovered_schema(self, discovery_results: Dict[str, Any]):
        """Analyze the discovered schema to extract useful information."""
        
        collections = set()
        total_fields = 0
        field_categories = {}
        
        # Analyze datamodel
        if discovery_results.get("datamodel"):
            print("  🔍 Analyzing datamodel structure...")
            datamodel = discovery_results["datamodel"]
            
            # The datamodel structure varies, let's explore it
            self._explore_datamodel_structure(datamodel, collections, field_categories)
        
        # Analyze datasets
        if discovery_results.get("datasets"):
            print("  🔍 Analyzing datasets structure...")
            datasets = discovery_results["datasets"]
            
            # The datasets structure varies, let's explore it
            self._explore_datasets_structure(datasets, collections, field_categories)
        
        # Update discovery results
        discovery_results["collections_discovered"] = list(collections)
        discovery_results["field_categories"] = field_categories
        discovery_results["total_fields_discovered"] = sum(len(fields) for fields in field_categories.values())
        
        print(f"  📊 Discovery Summary:")
        print(f"     Collections: {len(collections)}")
        print(f"     Field Categories: {len(field_categories)}")
        print(f"     Total Fields: {discovery_results['total_fields_discovered']}")
    
    def _explore_datamodel_structure(self, datamodel: Dict, collections: Set, field_categories: Dict):
        """Recursively explore datamodel structure to find all fields."""
        
        def explore_recursive(obj, path="", depth=0):
            if depth > 10:  # Prevent infinite recursion
                return
                
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    
                    # Check if this looks like a collection
                    if key.startswith(('crawl.', 'search_console', 'google_analytics', 'engagement_analytics')):
                        collections.add(key)
                    
                    # Check if this is a field definition
                    if isinstance(value, dict) and ('type' in value or 'description' in value):
                        category = self._categorize_field(current_path)
                        if category not in field_categories:
                            field_categories[category] = []
                        field_categories[category].append(current_path)
                    else:
                        explore_recursive(value, current_path, depth + 1)
            
            elif isinstance(obj, list) and obj:
                # Explore first item in list as representative
                explore_recursive(obj[0], path, depth + 1)
        
        explore_recursive(datamodel)
    
    def _explore_datasets_structure(self, datasets: Dict, collections: Set, field_categories: Dict):
        """Explore datasets structure to find collections and fields."""
        
        def explore_recursive(obj, path="", depth=0):
            if depth > 10:  # Prevent infinite recursion
                return
                
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    
                    # Look for collection indicators
                    if key in ['collections', 'datasets', 'groups']:
                        if isinstance(value, dict):
                            for collection_name in value.keys():
                                collections.add(collection_name)
                        elif isinstance(value, list):
                            for item in value:
                                if isinstance(item, str):
                                    collections.add(item)
                                elif isinstance(item, dict) and 'name' in item:
                                    collections.add(item['name'])
                    
                    # Look for field definitions
                    if key in ['fields', 'dimensions', 'metrics']:
                        if isinstance(value, dict):
                            for field_name, field_def in value.items():
                                category = self._categorize_field(field_name)
                                if category not in field_categories:
                                    field_categories[category] = []
                                field_categories[category].append(field_name)
                        elif isinstance(value, list):
                            for field in value:
                                if isinstance(field, str):
                                    category = self._categorize_field(field)
                                    if category not in field_categories:
                                        field_categories[category] = []
                                    field_categories[category].append(field)
                                elif isinstance(field, dict) and 'name' in field:
                                    category = self._categorize_field(field['name'])
                                    if category not in field_categories:
                                        field_categories[category] = []
                                    field_categories[category].append(field['name'])
                    
                    explore_recursive(value, current_path, depth + 1)
            
            elif isinstance(obj, list) and obj:
                for item in obj:
                    explore_recursive(item, path, depth + 1)
        
        explore_recursive(datasets)
    
    def _categorize_field(self, field_name: str) -> str:
        """Categorize a field based on its name."""
        field_lower = field_name.lower()
        
        if any(term in field_lower for term in ['url', 'domain', 'path', 'query']):
            return "URL Structure"
        elif any(term in field_lower for term in ['http', 'status', 'code', 'redirect']):
            return "HTTP Response"
        elif any(term in field_lower for term in ['title', 'description', 'h1', 'h2', 'meta']):
            return "Metadata"
        elif any(term in field_lower for term in ['content', 'text', 'word', 'body']):
            return "Content"
        elif any(term in field_lower for term in ['link', 'inlink', 'outlink']):
            return "Linking"
        elif any(term in field_lower for term in ['performance', 'time', 'speed', 'load']):
            return "Performance"
        elif any(term in field_lower for term in ['compliant', 'crawl', 'depth', 'visit']):
            return "Crawling"
        elif any(term in field_lower for term in ['impression', 'click', 'ctr', 'position']):
            return "Search Console"
        elif any(term in field_lower for term in ['session', 'user', 'pageview', 'bounce']):
            return "Analytics"
        elif any(term in field_lower for term in ['sitemap', 'robots', 'canonical']):
            return "Technical SEO"
        else:
            return "Other"

async def main():
    """Main function to run true schema discovery."""
    try:
        # Load configuration
        from config import get_botify_token
        api_key = get_botify_token()
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        org, project, analysis = config['org'], config['project'], config['analysis']
        
        # Create discoverer instance
        discoverer = BotifySchemaDiscoverer(org, project, analysis, api_key)
        
        # Discover complete schema
        schema_results = await discoverer.discover_complete_schema()
        
        # Save results in script directory
        script_dir = Path(__file__).parent
        
        # Save complete discovery results
        results_file = script_dir / f"{project}_{analysis}_true_schema_discovery.json"
        with open(results_file, 'w') as f:
            json.dump(schema_results, f, indent=2, default=str)
        
        print(f"\n✅ True schema discovery results saved to:")
        print(f"   {results_file.resolve()}")
        
        # Save collections summary
        if schema_results.get("collections_discovered"):
            collections_df = pd.DataFrame([
                {"collection": col} for col in schema_results["collections_discovered"]
            ])
            collections_file = script_dir / f"{project}_{analysis}_discovered_collections.csv"
            collections_df.to_csv(collections_file, index=False)
            print(f"   {collections_file.resolve()}")
        
        # Save fields summary
        if schema_results.get("field_categories"):
            fields_data = []
            for category, fields in schema_results["field_categories"].items():
                for field in fields:
                    fields_data.append({
                        "field": field,
                        "category": category
                    })
            
            if fields_data:
                fields_df = pd.DataFrame(fields_data)
                fields_file = script_dir / f"{project}_{analysis}_discovered_fields.csv"
                fields_df.to_csv(fields_file, index=False)
                print(f"   {fields_file.resolve()}")
        
        print(f"\n📊 Discovery Summary:")
        print(f"   Collections Found: {len(schema_results.get('collections_discovered', []))}")
        print(f"   Total Fields Found: {schema_results.get('total_fields_discovered', 0)}")
        print(f"   Field Categories: {len(schema_results.get('field_categories', {}))}")
        
    except Exception as e:
        print(f"❌ True schema discovery failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 