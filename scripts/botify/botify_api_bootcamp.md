# Botify Documentation

> This Notebook generates [Botify API Bootcamp](http://localhost:5001/docs/botify_api/page/1) documentation in the Pipulate app. If you're viewing it from there, this was generated from the `make_botify_docs.ipynb` Notebook in the `pipulate/helpers/botify` folder.

This is used primarily to make that documentation but if you find yourself here, it is also an excellent Botify API bootcamp that you can just follow along by running each cell below.

## Run Two Scripts

The first 2 scripts in this series (immediately below) set you up.

- Script 1 makes sure you have your `botify_token.txt` for API-access.
- Script 2 makes sure you have an example `config.json` to use in the examples.

> When you run the scripts in cells 2 & 3, they will appear to *"lock up"*. It's not. Input fields are waiting for you. Type/paste into the field and *Hit Enter*.  
> If you get confused, hit `Esc` + `0` + `0` + `Enter` and that will *restart the kernel.*  
> Yes, that's **Esc, Zero, Zero, Enter** -- *it's a Notebook thing.*  

Good luck!

## Script #1: Get Your Token


```python
#!/usr/bin/env python3
"""
Botify Token Setup
==================

A standalone Jupyter notebook program that:
1. Guides users to get their Botify API token
2. Validates the token with the Botify API
3. Saves the token to botify_token.txt for use in other programs

This replicates the functionality of the "Connect With Botify" workflow
but as a simple standalone script for Jupyter notebooks.
"""

import asyncio
import getpass
import json
import os
import sys
from pathlib import Path
from typing import Optional

import httpx


# Configuration
TOKEN_FILE = 'botify_token.txt'
ACCOUNT_URL = "https://app.botify.com/account"


def display_instructions():
    """Display instructions for getting the Botify API token."""
    print("🚀 Botify API Token Setup")
    print("=" * 50)
    print()
    print("To use Botify API tutorials and tools, you need to set up your API token.")
    print()
    print("📋 Steps to get your token:")
    print("1. Visit your Botify account page:")
    print(f"   🔗 {ACCOUNT_URL}")
    print("2. Look for the 'API' or 'Tokens' section")
    print("3. Copy your 'Main Token' (not a project-specific token)")
    print("4. Paste it in the input box below")
    print()


def check_existing_token() -> Optional[str]:
    """Check if a token file already exists and return its content."""
    # Search for token file in multiple locations (same logic as config generator)
    search_paths = [
        TOKEN_FILE,  # Current directory
        os.path.join(os.getcwd(), TOKEN_FILE),  # Explicit current directory
        os.path.join(os.path.expanduser('~'), TOKEN_FILE),  # Home directory
        os.path.join('/home/mike/repos/pipulate', TOKEN_FILE),  # Pipulate root
        os.path.join('/home/mike/repos', TOKEN_FILE),  # Repos root
    ]
    
    # Add script directory if __file__ is available (not in Jupyter)
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        search_paths.insert(3, os.path.join(script_dir, TOKEN_FILE))
    except NameError:
        # __file__ not available (running in Jupyter), skip script directory
        pass
    
    # Also check if we're in a subdirectory and look up the tree
    current_dir = os.getcwd()
    while current_dir != os.path.dirname(current_dir):  # Not at filesystem root
        search_paths.append(os.path.join(current_dir, TOKEN_FILE))
        current_dir = os.path.dirname(current_dir)
    
    for path in search_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    content = f.read().strip()
                    token = content.split('\n')[0].strip()
                    if token:
                        print(f"🔍 Found existing token file: {path}")
                        return token
            except Exception:
                continue
    
    return None


async def validate_botify_token(token: str) -> Optional[str]:
    """
    Validate the Botify API token and return the username if successful.
    
    Args:
        token: The Botify API token to validate
        
    Returns:
        str or None: The username if token is valid, None otherwise
    """
    url = "https://api.botify.com/v1/authentication/profile"
    headers = {"Authorization": f"Token {token}"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            
            # Extract username if the token is valid
            user_data = response.json()
            username = user_data["data"]["username"]
            return username
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            print(f"❌ Authentication failed: Invalid token")
        elif e.response.status_code == 403:
            print(f"❌ Access forbidden: Token may not have required permissions")
        else:
            print(f"❌ HTTP error {e.response.status_code}: {e.response.text}")
        return None
    except httpx.RequestError as e:
        print(f"❌ Network error: {str(e)}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Invalid response format: {str(e)}")
        return None
    except KeyError as e:
        print(f"❌ Unexpected response structure: Missing {str(e)}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return None


def save_token(token: str, username: str) -> bool:
    """
    Save the validated token to the token file in the current working directory.
    Always saves locally to ensure relative paths work for sample scripts.
    
    Args:
        token: The validated Botify API token
        username: The username associated with the token
        
    Returns:
        bool: True if saved successfully, False otherwise
    """
    try:
        # Always save to current working directory for notebook compatibility
        local_token_path = os.path.join(os.getcwd(), TOKEN_FILE)
        
        # Save token with a comment containing the username
        with open(local_token_path, 'w') as f:
            f.write(f"{token}\n# username: {username}")
        
        print(f"✅ Token saved locally to: {local_token_path}")
        print(f"📁 This ensures relative paths work for sample scripts and notebooks.")
        return True
        
    except Exception as e:
        print(f"❌ Error saving token: {str(e)}")
        return False


async def main():
    """Main execution function"""
    display_instructions()
    
    # Check for existing token
    existing_token = check_existing_token()
    if existing_token:
        print("⚠️  You already have a Botify API token configured.")
        print()
        
        # Validate existing token
        print("🔍 Validating existing token...")
        username = await validate_botify_token(existing_token)
        
        if username:
            print(f"✅ Existing token is valid for user: {username}")
            print()
            
            # Check if token is already local to current directory
            local_token_path = os.path.join(os.getcwd(), TOKEN_FILE)
            existing_token_path = None
            
            # Find where the existing token is located
            search_paths = [
                TOKEN_FILE,  # Current directory
                os.path.join(os.getcwd(), TOKEN_FILE),  # Explicit current directory
                os.path.join(os.path.expanduser('~'), TOKEN_FILE),  # Home directory
                os.path.join('/home/mike/repos/pipulate', TOKEN_FILE),  # Pipulate root
                os.path.join('/home/mike/repos', TOKEN_FILE),  # Repos root
            ]
            
            for path in search_paths:
                if os.path.exists(path):
                    existing_token_path = path
                    break
            
            # If token is not in current directory, copy it locally
            if existing_token_path and os.path.abspath(existing_token_path) != os.path.abspath(local_token_path):
                print(f"📋 Copying token from {existing_token_path} to current directory...")
                if save_token(existing_token, username):
                    print("✅ Token copied locally for notebook compatibility.")
                else:
                    print("⚠️  Failed to copy token locally, but existing token is still valid.")
            
            # Ask if they want to update it
            update_choice = getpass.getpass("Do you want to update your token? (y/N): ").strip().lower()
            if update_choice not in ['y', 'yes']:
                print("🎉 Setup complete! Your token is ready to use.")
                return True  # Return success status, not the token
        else:
            print("❌ Existing token is invalid. You'll need to enter a new one.")
        
        print()
    
    # Get token from user
    print("📝 Please paste your Botify API 'Main Token' below:")
    print("(The input will be hidden for security)")
    print()
    
    # Diagnostic information
    print(f"🔧 Running in: {sys.executable}")
    print(f"🔧 sys.stdin.isatty(): {sys.stdin.isatty()}")
    print()
    
    # Use getpass for hidden input - no fallback to visible input
    try:
        token = getpass.getpass("Botify API Token: ").strip()
        if token:
            print(f"✅ Token received (length: {len(token)})")
        else:
            print("❌ No token provided. Setup cancelled.")
            return False
    except Exception as e:
        print(f"❌ getpass.getpass() failed: {e}")
        print("❌ Secure input not available. Setup cancelled.")
        print("💡 Try running this in a proper terminal or Jupyter environment.")
        return False
    
    # Validate the token
    print()
    print("🔍 Validating your token...")
    username = await validate_botify_token(token)
    
    if not username:
        print("❌ Token validation failed. Please check your token and try again.")
        print()
        print("💡 Make sure you're using the 'Main Token' from:")
        print(f"   {ACCOUNT_URL}")
        return False
    
    print(f"✅ Token validated successfully for user: {username}")
    
    # Save the token
    print()
    print("💾 Saving token...")
    if save_token(token, username):
        print()
        print("🎉 Botify API setup complete!")
        print()
        print("📄 You can now use:")
        print("   • Botify API tutorials and examples")
        print("   • The Botify configuration generator")
        print("   • Any Botify-related workflows")
        print()
        print("🔧 Next steps:")
        print("   1. Run the Botify configuration generator to set up project config")
        print("   2. Explore the Botify API tutorials in the notebooks")
        
        return True  # Return success status, not the token
    else:
        print("❌ Failed to save token. Setup incomplete.")
        return False


# For Jupyter Notebook execution
if __name__ == "__main__":
    # Check if we're in Jupyter (has get_ipython function)
    try:
        get_ipython()
        print("🔬 Running in Jupyter environment")
        # In Jupyter, use await directly
        success = await main()
    except NameError:
        # Not in Jupyter, use asyncio.run()
        print("🖥️  Running in standard Python environment")
        success = asyncio.run(main()) 
```

## Script #2: Setup config file


```python
#!/usr/bin/env python3
"""
Botify Configuration Generator
=============================

A standalone Jupyter notebook program that:
1. Asks for a Botify project URL via input()
2. Validates the URL and extracts org/project info
3. Fetches the most recent analysis from Botify API
4. Generates a configuration JSON file

Based on the Botify Trifecta workflow patterns.
"""

import asyncio
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse
from typing import Tuple, Optional, Dict, Any

import httpx


# Configuration
TOKEN_FILE = 'botify_token.txt'


def load_api_token() -> str:
    """Load the Botify API token from the token file."""
    # Search for token file in multiple locations
    search_paths = [
        TOKEN_FILE,  # Current directory
        os.path.join(os.getcwd(), TOKEN_FILE),  # Explicit current directory
        os.path.join(os.path.expanduser('~'), TOKEN_FILE),  # Home directory
        os.path.join('/home/mike/repos/pipulate', TOKEN_FILE),  # Pipulate root
        os.path.join('/home/mike/repos', TOKEN_FILE),  # Repos root
    ]
    
    # Add script directory if __file__ is available (not in Jupyter)
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        search_paths.insert(3, os.path.join(script_dir, TOKEN_FILE))
    except NameError:
        # __file__ not available (running in Jupyter), skip script directory
        pass
    
    # Also check if we're in a subdirectory and look up the tree
    current_dir = os.getcwd()
    while current_dir != os.path.dirname(current_dir):  # Not at filesystem root
        search_paths.append(os.path.join(current_dir, TOKEN_FILE))
        current_dir = os.path.dirname(current_dir)
    
    token_path = None
    for path in search_paths:
        if os.path.exists(path):
            token_path = path
            break
    
    if not token_path:
        searched_locations = '\n  - '.join(search_paths[:6])  # Show first 6 locations
        raise ValueError(f"Token file '{TOKEN_FILE}' not found in any of these locations:\n  - {searched_locations}\n\nPlease ensure the file exists in one of these locations.")
    
    try:
        with open(token_path) as f:
            content = f.read().strip()
            api_key = content.split('\n')[0].strip()
            if not api_key:
                raise ValueError(f"Token file '{token_path}' is empty.")
            print(f"🔑 Using token from: {token_path}")
            return api_key
    except Exception as e:
        raise ValueError(f"Error reading token file '{token_path}': {str(e)}")


def validate_botify_url(url: str) -> Tuple[bool, str, Dict[str, str]]:
    """
    Validate a Botify project URL and extract project information.
    
    Args:
        url: The Botify project URL to validate
        
    Returns:
        Tuple of (is_valid, message, project_data)
    """
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
        
        project_data = {
            'url': canonical_url,
            'username': org_slug,
            'project_name': project_slug,
            'project_id': f'{org_slug}/{project_slug}'
        }
        
        return (True, f'Valid Botify project: {project_slug}', project_data)
        
    except Exception as e:
        return (False, f'Error parsing URL: {str(e)}', {})


async def get_username(api_token: str) -> Optional[str]:
    """
    Fetch the username associated with the API key.
    
    Args:
        api_token: Botify API token
        
    Returns:
        Username string or None if error
    """
    headers = {"Authorization": f"Token {api_token}"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.botify.com/v1/authentication/profile", headers=headers, timeout=60.0)
            response.raise_for_status()
            return response.json()["data"]["username"]
    except Exception as e:
        print(f'❌ Error fetching username: {str(e)}')
        return None


async def fetch_projects(username: str, api_token: str) -> Optional[list]:
    """
    Fetch all projects for a given username from Botify API.
    
    Args:
        username: Username to fetch projects for
        api_token: Botify API token
        
    Returns:
        List of project tuples (name, slug, user_or_org) or None if error
    """
    url = f"https://api.botify.com/v1/projects/{username}"
    headers = {"Authorization": f"Token {api_token}"}
    projects = []
    
    try:
        while url:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=60.0)
                response.raise_for_status()
                data = response.json()
                
                # Extract project info as tuples (name, slug, user_or_org)
                for p in data.get('results', []):
                    projects.append((
                        p['name'], 
                        p['slug'], 
                        p['user']['login']
                    ))
                
                url = data.get('next')
        
        return sorted(projects) if projects else None
        
    except Exception as e:
        print(f'❌ Error fetching projects for {username}: {str(e)}')
        return None


async def fetch_most_recent_analysis(org: str, project: str, api_token: str, quiet: bool = False) -> Optional[str]:
    """
    Fetch the most recent analysis slug for a Botify project.
    
    Args:
        org: Organization slug
        project: Project slug
        api_token: Botify API token
        
    Returns:
        Most recent analysis slug or None if error/no analyses found
    """
    if not org or not project or not api_token:
        print(f'❌ Missing required parameters: org={org}, project={project}')
        return None
    
    # Fetch first page of analyses (they should be sorted by date, most recent first)
    url = f'https://api.botify.com/v1/analyses/{org}/{project}/light'
    headers = {
        'Authorization': f'Token {api_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=60.0)
            
        if response.status_code != 200:
            print(f'❌ API error: Status {response.status_code} for {url}')
            print(f'Response: {response.text}')
            return None
        
        data = response.json()
        if 'results' not in data:
            print(f"❌ No 'results' key in response: {data}")
            return None
        
        analyses = data['results']
        if not analyses:
            if not quiet:
                print('❌ No analyses found for this project')
            return None
        
        # Get the first (most recent) analysis
        most_recent = analyses[0]
        analysis_slug = most_recent.get('slug')
        
        if not analysis_slug:
            if not quiet:
                print('❌ No slug found in most recent analysis')
            return None
        
        if not quiet:
            print(f'✅ Found most recent analysis: {analysis_slug}')
            print(f'📊 Total analyses available: {len(analyses)}')
            
            # Show some details about the most recent analysis
            if 'date_created' in most_recent:
                print(f'📅 Created: {most_recent["date_created"]}')
            if 'date_last_modified' in most_recent:
                print(f'🔄 Last modified: {most_recent["date_last_modified"]}')
        
        return analysis_slug
        
    except httpx.HTTPStatusError as e:
        print(f'❌ HTTP error: {e.response.status_code} - {e.response.text}')
        return None
    except httpx.RequestError as e:
        print(f'❌ Network error: {str(e)}')
        return None
    except json.JSONDecodeError as e:
        print(f'❌ JSON decode error: {str(e)}')
        return None
    except Exception as e:
        print(f'❌ Unexpected error: {str(e)}')
        return None


def generate_config(org: str, project: str, analysis_slug: str) -> Dict[str, str]:
    """
    Generate the configuration dictionary.
    
    Args:
        org: Organization slug
        project: Project slug  
        analysis_slug: Analysis slug
        
    Returns:
        Configuration dictionary
    """
    return {
        "org": org,
        "project": project,
        "analysis": analysis_slug,
        "collection": f"crawl.{analysis_slug}"
    }


async def get_default_configuration(api_token: str) -> Optional[Dict[str, str]]:
    """
    Get default configuration using first available project with analyses.
    
    Args:
        api_token: Botify API token
        
    Returns:
        Default configuration dictionary or None if unable to generate
    """
    print("🔍 Fetching your default configuration...")
    
    # Step 1: Get username
    print("👤 Fetching username...")
    username = await get_username(api_token)
    if not username:
        print("❌ Could not fetch username")
        return None
    
    print(f"👤 Using username: {username}")
    
    # Step 2: Get projects for username
    print(f"📁 Fetching projects for {username}...")
    projects = await fetch_projects(username, api_token)
    if not projects:
        print("❌ No projects found")
        return None
    
    print(f"📊 Found {len(projects)} projects. Searching for one with analyses...")
    
    # Step 3: Try each project until we find one with analyses
    for i, project_tuple in enumerate(projects):
        project_name = project_tuple[0]  # name
        project_slug = project_tuple[1]  # slug
        org_slug = project_tuple[2]      # user_or_org
        
        print(f"🔍 Trying project {i+1}/{len(projects)}: {org_slug}/{project_slug}")
        
        # Try to get latest analysis for this project (quiet mode during search)
        analysis_slug = await fetch_most_recent_analysis(org_slug, project_slug, api_token, quiet=True)
        
        if analysis_slug:
            print(f"✅ Found project with analyses!")
            print(f"🏢 Using organization: {org_slug}")
            print(f"📁 Using project: {project_slug}")
            
            # Now get the analysis details with full output
            print(f"🔍 Fetching analysis details...")
            await fetch_most_recent_analysis(org_slug, project_slug, api_token, quiet=False)
            
            # Step 4: Generate configuration
            config = generate_config(org_slug, project_slug, analysis_slug)
            return config
        else:
            print(f"⏭️  No analyses found for {org_slug}/{project_slug}, trying next project...")
    
    # If we get here, no projects had analyses
    print("❌ No projects found with analyses")
    return None


def save_config(config: Dict[str, str], filename: str = "botify_config.json") -> None:
    """
    Save the configuration to a JSON file.
    
    Args:
        config: Configuration dictionary
        filename: Output filename
    """
    try:
        file_path = Path(filename)
        
        if file_path.exists():
            print(f'📄 Configuration file already exists: {filename}')
            print(f'💡 Skipping save to avoid overwriting existing file.')
            print(f'🔍 Current configuration that would have been saved:')
            print(json.dumps(config, indent=4))
            return
        
        with open(filename, 'w') as f:
            json.dump(config, f, indent=4)
        print(f'✅ Configuration saved to: {filename}')
    except Exception as e:
        print(f'❌ Error saving configuration: {str(e)}')


async def main():
    """Main execution function"""
    print("🚀 Botify Configuration Generator")
    print("=" * 50)
    
    # Step 1: Load API token
    try:
        api_token = load_api_token()
        print(f"✅ API token loaded from {TOKEN_FILE}")
    except Exception as e:
        print(f"❌ {str(e)}")
        return
    
    # Step 2: Get Botify project URL from user (with default option)
    while True:
        print("\n📝 Please enter your Botify project URL:")
        print("Example: https://app.botify.com/your-org/your-project/")
        print("💡 Or just hit Enter to use your default (first org, first project, latest analysis)")
        
        botify_url = input("Botify Project URL (or Enter for default): ").strip()
        
        # Check if user wants default configuration
        if not botify_url:
            print("\n🎯 Using default configuration...")
            config = await get_default_configuration(api_token)
            
            if config:
                print("✅ Default configuration generated successfully!")
                break
            else:
                print("❌ Could not generate default configuration.")
                print("💡 Please enter a specific Botify project URL instead.")
                continue
        
        # Step 3: Validate URL
        is_valid, message, project_data = validate_botify_url(botify_url)
        
        if not is_valid:
            print(f"❌ {message}")
            print("💡 Please try again or hit Enter for default configuration.")
            continue
        
        print(f"✅ {message}")
        
        org = project_data['username']
        project = project_data['project_name']
        
        print(f"🏢 Organization: {org}")
        print(f"📁 Project: {project}")
        
        # Step 4: Fetch most recent analysis
        print(f"\n🔍 Fetching most recent analysis for {org}/{project}...")
        
        analysis_slug = await fetch_most_recent_analysis(org, project, api_token)
        
        if not analysis_slug:
            print("❌ Could not fetch analysis information")
            print("💡 Please try a different URL or hit Enter for default configuration.")
            continue
        
        # Step 5: Generate configuration
        config = generate_config(org, project, analysis_slug)
        break
    
    # Display and save configuration
    if config:
        print(f"\n📋 Generated Configuration:")
        print("=" * 30)
        print(json.dumps(config, indent=4))
        
        # Step 6: Save configuration
        print(f"\n💾 Saving configuration...")
        save_config(config, "config.json")
        
        print(f"\n🎉 Configuration generation complete!")
        print(f"📄 You can now use the generated config.json file in your projects.")
        
        return config
    else:
        print("❌ Configuration generation failed.")
        return None


# For Jupyter Notebook execution
if __name__ == "__main__":
    # Check if we're in Jupyter (has get_ipython function)
    try:
        get_ipython()
        print("🔬 Running in Jupyter environment")
        # In Jupyter, use await directly
        config = await main()
    except NameError:
        # Not in Jupyter, use asyncio.run()
        print("🖥️  Running in standard Python environment")
        config = asyncio.run(main()) 
```

--------------------------------------------------------------------------------

# Introduction to BQL (Botify Query Language)

Botify API interactions come in many shapes and forms. The example shown below is the most popular: BQLv2 (Botify Query Language V2), but there are others -- not just BQLv1 but also a vast array of *specialized endpoints* for custom reports and analysis. Of all the variations you will find, two "endpoints" (URLs that you make requests to) rise above all the others in their utility and frequency you'll encounter them. And they are:

1. The `/query` endpoint
2. The `/jobs` endpoint

## `/query` Endpoint Example

```python
import httpx

# This is set by the botify_token.txt file you just created above.
api_key = "your_api_key_here"

# These part are read from the config.json file you just created above.
org = "your_organization_slug"
project = "your_project_slug"
analysis = "your_analysis_slug"
collection = "your_collection_name"

# This is an "endpoint". Endpoints are URLs that you can "submit" requests to.
url = f"https://api.botify.com/v1/projects/{org}/{project}/query"  # <-- SEE!!! This is the `/query` endpoint!

# This sets values that need to be sent WITH the request that you submit to the endpoint.
headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}

# BQL query payload
payload = {
    "collections": [collection],
    "query": {
        "dimensions": [{"field": "segments.pagetype.value"}],
        "metrics": [{"field": f"{collection}.count_urls_crawl"}],
        "sort": [
            {"type": "metrics", "index": 0, "order": "desc"},
            {"type": "dimensions", "index": 0, "order": "asc"}
        ]
    }
}

# Send POST request
response = httpx.post(url, headers=headers, json=payload)
response.raise_for_status()
print(response.json())
```

--------------------------------------------------------------------------------

# Use API: Simplest Example

Remember when I told you there are lots of specialized endpoints? Well, this is the first and easiest to have an immediate API success. If you did the above API step correctly, you should be able to get your username with this bare minimum Botify API script.


```python
import httpx

# Read only the first line (the token) from botify_token.txt
# This handles the multi-line format: token on line 1, comment on line 2
api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()

headers = {"Authorization": f"Token {api_key}"}
user_data = httpx.get("https://api.botify.com/v1/authentication/profile", headers=headers).json()

username = user_data["data"]["username"]
print(username)
```

**Sample Output**: 

    first.last

**Note**: these "sample output" cells are here in part for the LLMs who need to know enough about the expected Botify API output in order to help you. Each code-cell is accompanies by a markdown cell that embeds sample output so the system doesn't have to rely on the actual output generated by the code.

--------------------------------------------------------------------------------

# List Orgs: How To Get the List of Projects And Their Orgs Given Username


```python
import httpx

# Load API key
api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
headers = {"Authorization": f"Token {api_key}"}

def get_username():
    """Fetch the username associated with the API key."""
    try:
        response = httpx.get("https://api.botify.com/v1/authentication/profile", headers=headers)
        response.raise_for_status()
        return response.json()["data"]["username"]
    except httpx.RequestError as e:
        print(f"Error fetching username: {e}")

def fetch_projects(username):
    """Fetch all projects for a given username from Botify API."""
    url = f"https://api.botify.com/v1/projects/{username}"
    projects = []
    try:
        while url:
            response = httpx.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            projects.extend(
                (p['name'], p['slug'], p['user']['login']) for p in data.get('results', [])
            )
            url = data.get('next')
        return sorted(projects)
    except httpx.RequestError as e:
        print(f"Error fetching projects for {username}: {e}")
        return []

username = get_username()
if username:
    projects = fetch_projects(username)
    print(f"{'Project Name':<30} {'Project Slug':<35} {'User or Org':<15}")
    print("=" * 80)
    for name, slug, user in projects:
        print(f"{name:<30} {slug:<35} {user:<15}")
else:
    print("Failed to retrieve username or projects.")
```

**Sample Output**:

```
Username: first.last
Project Name                   Project Slug                        User or Org    
================================================================================
Foo Test                       foo.com                             first.last       
Bar Test                       bar.com                             bar-org       
Baz Test                       baz.com                             baz-org       
```

**Rationale**: You need an Organization slug (**org**) for these exercises. It goes in your **config.json** to get started. Your personal login username will usually be used for one Project, but then an offical ***org slug*** (aka group) will usually appear on the others. By convention, these values often end with `-org`.

--------------------------------------------------------------------------------

# List Projects: How To Get the List of Projects Given an Organization

Note: 
- If you're running this in VSCode or Cursor IDE, the `config.json` file should be in the root directory of your project.
- If you're running this in Jupyter Notebook, the `config.json` file should be in the same directory as this notebook.

Your config.json should look like:
```json
{
    "org": "org_name",
    "project": "project_name"
}
```


```python
import json
import httpx

# Load configuration and API key
config = json.load(open("config.json"))
api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
org = config['org']

def fetch_projects(org):
    """Fetch all projects for a given organization from Botify API."""
    url = f"https://api.botify.com/v1/projects/{org}"
    headers = {"Authorization": f"Token {api_key}"}
    projects = []
    
    try:
        while url:
            response = httpx.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            projects.extend((p['name'], p['slug'], p['user']['login']) for p in data.get('results', []))
            url = data.get('next')
        return sorted(projects)
    except httpx.RequestError as e:
        print(f"Error fetching projects: {e}")
        return []

projects = fetch_projects(org)

print(f"{'Project Name':<30} {'Project Slug':<35} {'Login':<15}")
print("=" * 80)
for name, slug, user in projects:
    print(f"{name:<30} {slug:<35} {user:<15}")

print("\nDone")
```

**Sample Output**:

```
Organization: foo-bar
Project Name                   Project Slug                        Login     
================================================================================
Legendary Product Vault        legendary-product-vault             foo-org       
Hidden Content Cove            hidden-content-cove                 foo-org       
Fabled Catalog of Curiosities  fabled-catalog-of-curiosities       foo-org       
```

**Rationale**: Next, you need Project slugs for these exercises.

--------------------------------------------------------------------------------

# List Analyses: How To Get the List of Analysis Slugs Given a Project



```python
import json
import httpx

# Load configuration and API key
config = json.load(open("config.json"))
api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
org, project = config['org'], config['project']

def fetch_analyses(org, project):
    """Fetch analysis slugs for a given project from Botify API."""
    url = f"https://api.botify.com/v1/analyses/{org}/{project}/light"
    headers = {"Authorization": f"Token {api_key}"}
    slugs = []
    
    try:
        while url:
            response = httpx.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            slugs.extend(a['slug'] for a in data.get('results', []))
            url = data.get('next')
        return slugs
    except httpx.RequestError as e:
        print(f"Error fetching analyses: {e}")
        return []

# Output analysis slugs
for slug in fetch_analyses(org, project):
    print(slug)
print("\nDone")
```

**Sample Output**:

```
20240301
20240201
20240101-2
20240101
20231201
20231101
```

**Rationale**: Analysis slugs are dates in YYYYMMDD format but sometimes get incremeted with `-n` extensions starting with `-2`. They're the third thing you typically need in **config.json** for these exercises.

--------------------------------------------------------------------------------

# List URLs: How To Get a List of the First 500 URLs

**Important**: For this step to work, you need to have an `analysis` value set in your `config.json` file. 

Your `config.json` should include:
```json
{
    "org": "your-organization",
    "project": "your-project-slug",
    "analysis": "your-analysis-slug"
}
```

The analysis slug is typically a date in YYYYMMDD format (like "20240301") as shown in the sample output below. Without this value in your config file, you'll encounter a KeyError.


```python
import json
import httpx
import pandas as pd

config = json.load(open("config.json"))
api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
org = config['org']
project = config['project']
analysis = config['analysis']


def get_bqlv2_data(org, project, analysis, api_key):
    """Fetch data based on BQLv2 query for a specific Botify analysis."""
    url = f"https://api.botify.com/v1/projects/{org}/{project}/query"
    
    # BQLv2 query payload
    data_payload = {
        "collections": [f"crawl.{analysis}"],
        "query": {
            "dimensions": [
                f"crawl.{analysis}.url"
            ],
            "metrics": []  # Don't come crying to me when you delete this and it stops working.
        }
    }

    headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}

    # Send the request
    response = httpx.post(url, headers=headers, json=data_payload, timeout=60.0)
    response.raise_for_status()  # Check for errors
    
    return response.json()

# Run the query and load results
data = get_bqlv2_data(org, project, analysis, api_key)

list_of_urls = [url['dimensions'][0] for url in data['results']]

for i, url in enumerate(list_of_urls):
    print(i + 1, url)
    if i >= 9:
        break
```

**Sample Output**:

```
1 https://example.com/page1
2 https://example.com/page2
3 https://example.com/page3
4 https://example.com/page4
5 https://example.com/page5
6 https://example.com/page6
7 https://example.com/page7
8 https://example.com/page8
9 https://example.com/page9
10 https://example.com/page10
```

**Rationale**: To explicitly tell you that you have to leave the `metrics": []` field in this example even though it's empty. Don't believe me? Try it. Ugh! Also, I'm not here to teach you Python, but it's worth noting:

- `enumerate()` exposes the internal counter index.
- Python uses zero-based indexes, thus the `+1` for humans and `>= 9` to cut off at 10.
- The `print()` function takes multiple (un-labeled) inputs--counter & url in this case.
- The other way to use the counter & url together is ***f-strings***: `f"{i+1} {url}"`, which would also work.

You're welcome.

--------------------------------------------------------------------------------

# List SEO Fields: How To Get a List of the First 500 URLs, Titles, Meta Descriptions and H1s


```python
import json
import httpx
import pandas as pd

# Load configuration and API key
config = json.load(open("config.json"))
api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
org = config['org']
project = config['project']
analysis = config['analysis']

def get_bqlv2_data(org, project, analysis, api_key):
    """Fetch data for URLs with title, meta description, and H1 fields."""
    url = f"https://api.botify.com/v1/projects/{org}/{project}/query"
    
    # BQLv2 query payload
    data_payload = {
        "collections": [f"crawl.{analysis}"],
        "query": {
            "dimensions": [
                f"crawl.{analysis}.url",
                f"crawl.{analysis}.metadata.title.content",
                f"crawl.{analysis}.metadata.description.content",
                f"crawl.{analysis}.metadata.h1.contents"
            ],
            "metrics": []
        }
    }

    headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}

    # Send the request with a timeout of 60 seconds
    response = httpx.post(url, headers=headers, json=data_payload, timeout=60)
    response.raise_for_status()  # Check for errors
    
    return response.json()

# Run the query and load results
data = get_bqlv2_data(org, project, analysis, api_key)

# Flatten the data into a DataFrame
columns = ["url", "title", "meta_description", "h1"]
df = pd.DataFrame([item['dimensions'] for item in data['results']], columns=columns)

# Display the first 500 URLs
df.head(500).to_csv("first_500_urls.csv", index=False)
print("Data saved to first_500_urls.csv")

# Show a preview
df.head()
```

**Sample Output**:


| url                              | title               | meta_description                           | h1                 |
|----------------------------------|---------------------|--------------------------------------------|---------------------|
| https://example.com/foo          | Foo Title          | This is a description of Foo.              | Foo Heading        |
| https://example.com/bar          | Bar Overview       | Bar is a collection of great resources.    | Bar Insights       |
| https://example.com/baz          | Baz Guide          | Learn all about Baz and its applications.  | Baz Essentials     |

...

*Data saved to `first_500_urls.csv`*

**Rationale**: To show you the main endpoint for listing 500 lines at a time, paging and quick aggregate queries. To show you how `org` and `project` are in the url (so you notice them disappearing later when we export csv downloads). To introduce the infinitely popular and useful `pandas` data library for manipulating ***row & column*** data.


```python
import json
import httpx
import pandas as pd

# Load configuration and API key
config = json.load(open("config.json"))
api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
org = config['org']
project = config['project']
analysis = config['analysis']

def format_analysis_date(analysis_slug):
    """Convert analysis slug (e.g. '20241108' or '20241108-2') to YYYY-MM-DD format."""
    # Strip any suffix after hyphen
    base_date = analysis_slug.split('-')[0]
    
    # Insert hyphens for YYYY-MM-DD format
    return f"{base_date[:4]}-{base_date[4:6]}-{base_date[6:8]}"

def get_previous_analysis(org, project, current_analysis, api_key):
    """Get the analysis slug immediately prior to the given one."""
    url = f"https://api.botify.com/v1/analyses/{org}/{project}/light"
    headers = {"Authorization": f"Token {api_key}"}
    
    try:
        response = httpx.get(url, headers=headers)
        response.raise_for_status()
        analyses = response.json().get('results', [])
        
        # Get base date without suffix
        current_base = current_analysis.split('-')[0]
        
        # Find the first analysis that's before our current one
        for analysis in analyses:
            slug = analysis['slug']
            base_slug = slug.split('-')[0]
            if base_slug < current_base:
                return slug
                
    except httpx.RequestError as e:
        print(f"Error fetching analyses: {e}")
        return None

def get_bqlv2_data(org, project, analysis, api_key):
    """Fetch data for URLs with titles and search console metrics, sorted by impressions."""
    # Get date range for search console data
    end_date = format_analysis_date(analysis)
    prev_analysis = get_previous_analysis(org, project, analysis, api_key)
    if prev_analysis:
        start_date = format_analysis_date(prev_analysis)
    else:
        # Fallback to 7 days before if no previous analysis found
        start_date = end_date  # You may want to subtract 7 days here
    
    url = f"https://api.botify.com/v1/projects/{org}/{project}/query"
    
    data_payload = {
        "collections": [
            f"crawl.{analysis}",
            "search_console"
        ],
        "query": {
            "dimensions": [
                f"crawl.{analysis}.url",
                f"crawl.{analysis}.metadata.title.content"
            ],
            "metrics": [
                "search_console.period_0.count_impressions",
                "search_console.period_0.count_clicks"
            ],
            "sort": [
                {
                    "field": "search_console.period_0.count_impressions",
                    "order": "desc"
                }
            ]
        },
        "periods": [
            [start_date, end_date]
        ]
    }
    
    headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}
    response = httpx.post(url, headers=headers, json=data_payload, timeout=60.0)
    response.raise_for_status()
    
    return response.json()

# Run the query and load results
data = get_bqlv2_data(org, project, analysis, api_key)

# Flatten the data into a DataFrame with URL, title, and search console metrics
columns = ["url", "title", "impressions", "clicks"]
df = pd.DataFrame([
    item['dimensions'] + item['metrics'] 
    for item in data['results']
], columns=columns)

# Display the first 500 URLs and titles
df.head(500).to_csv("first_500_urls_titles.csv", index=False)
print("Data saved to first_500_urls_titles.csv")

# Show a preview
df.head()
```

**Sample Output**:

| | url                               | title              | impressions | clicks |
|-|-----------------------------------|--------------------|-------------|--------|
|0| https://example.com/foo           | Foo Page Title    | 1200        | 35     |
|1| https://example.com/bar           | Bar Page Title    | 1150        | 40     |
|2| https://example.com/baz           | Baz Page Title    | 980         | 25     |


**Rationale**: So that I can jump up and down screaming that BQL is not SQL and tell the LLMs to stop showing me SQL examples for BQL. Surely SQL is down there somewhere, but it's ***API-wrapped***. Though this does not spare us from some SQL methodology. For example, table-joins across Collections are a thing--demonstrated here as `search_console` joined with `crawl.YYMMDD`, left-outer if I'm reading it correctly (I may have to amend that). If you really wanna know, Collections are table aliases that help with the API-wrapping.

--------------------------------------------------------------------------------

# # Query Segments: How to Get Pagetype Segment Data for a Project With URL Counts

This query requires the "collection" field in your config.json file, in addition to "org", "project", and "analysis".
Example config.json:
```json
{
    "org": "org_name",
    "project": "project_name",
    "analysis": "20241230",
    "collection": "crawl.20241230"
}
```




```python
import httpx
import json

# Load configuration values from config.json
with open("config.json") as config_file:
    config = json.load(config_file)

# Extract configuration details
org = config["org"]
project = config["project"]
analysis = config["analysis"]
collection = config["collection"]

# Load the API key from botify_token.txt
api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()

# Define the URL for the API request
url = f"https://api.botify.com/v1/projects/{org}/{project}/query"

# Set headers for authorization and content type
headers = {
    "Authorization": f"Token {api_key}",
    "Content-Type": "application/json"
}

# Define the payload for the API query
payload = {
    "collections": [collection],
    "query": {
        "dimensions": [{"field": "segments.pagetype.value"}],
        "metrics": [{"field": f"{collection}.count_urls_crawl"}],
        "sort": [
            {"type": "metrics", "index": 0, "order": "desc"},
            {"type": "dimensions", "index": 0, "order": "asc"}
        ]
    }
}

# Send the POST request to the API
response = httpx.post(url, headers=headers, json=payload, timeout=60)
response.raise_for_status()  # Raise an error if the request fails

# Get the results from the response JSON
results = response.json()

# Use json.dumps with separators and indent for compact pretty printing
print(json.dumps(results, indent=4, separators=(',', ': ')))
```

**Sample Output**:

```json
{
    "results": [
        {
            "dimensions": ["pdp"],
            "metrics": [82150]
        },
        {
            "dimensions": ["plp"],
            "metrics": [53400]
        },
        {
            "dimensions": ["category"],
            "metrics": [44420]
        },
        [...]
    ],
    "previous": null,
    "next": "https://api.botify.com/v1/org/project/query?page=1",
    "page": 1,
    "size": 10
}
```

**Rationale**: To give you an example that uses dimensions, metrics and sorting all at once. Also to show you the `page` parameter on the querystring making you think it's the **GET method**, `org` & `project` arguments posing as folders, and finally a JSON `payload` showing you it's actually using the **POST method**. Ahhh, *gotta love the Botify API*.

--------------------------------------------------------------------------------

# List Collections: How To Get the List of Collections Given a Project


```python
# Get List of Collections Given a Project

import json
import httpx

config = json.load(open("config.json"))
api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
org = config['org']
project = config['project']

def fetch_collections(org, project, api_key):
    """Fetch collection IDs for a given project from the Botify API."""
    collections_url = f"https://api.botify.com/v1/projects/{org}/{project}/collections"
    headers = {"Authorization": f"Token {api_key}"}
    
    try:
        response = httpx.get(collections_url, headers=headers)
        response.raise_for_status()
        collections_data = response.json()
        return [
            (collection['id'], collection['name']) for collection in collections_data
        ]
    except httpx.RequestError as e:
        print(f"Error fetching collections for project '{project}': {e}")
        return []


# Fetch collections
collections = fetch_collections(org, project, api_key)
for collection_id, collection_name in collections:
    print(f"ID: {collection_id}, Name: {collection_name}")
```

**Sample Output**:

```
ID: crawl.20240917, Name: 2024 Sept. 17th
ID: actionboard_ml.20240917, Name: ActionBoard ML
ID: crawl.20240715, Name: 2024 July 15th
ID: search_engines_orphans.20240715, Name: Search Engines Orphans
```

**Rationale**: To let you know how tough Collections are once you start digging in. The first challenge is simply knowing what collections you have and what you can do with them--though 9 out of 10 times it's `crawl.YYYYMMDD` and `search_console`. If not, come talk to me, I wanna pick your brain.

--------------------------------------------------------------------------------

# List Fields: How To Get The List of Fields Given a Collection


```python
# Get List of Fields Given a Collection

import json
import httpx

config = json.load(open("config.json"))
api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
org = config['org']
project = config['project']
collection = config['collection']

def fetch_fields(org, project, collection, api_key):
    """Fetch available fields for a given collection from the Botify API."""
    fields_url = f"https://api.botify.com/v1/projects/{org}/{project}/collections/{collection}"
    headers = {"Authorization": f"Token {api_key}"}
    
    try:
        response = httpx.get(fields_url, headers=headers)
        response.raise_for_status()
        fields_data = response.json()
        return [
            (field['id'], field['name'])
            for dataset in fields_data.get('datasets', [])
            for field in dataset.get('fields', [])
        ]
    except httpx.RequestError as e:
        print(f"Error fetching fields for collection '{collection}' in project '{project}': {e}")
        return []

# Fetch and print fields
fields = fetch_fields(org, project, collection, api_key)
print(f"Fields for collection '{collection}':")
for field_id, field_name in fields:
    print(f"ID: {field_id}, Name: {field_name}")
```

**Sample Output**:

```
Fields for collection 'crawl.20241101':
ID: field_of_vision, Name: Survey the Landscape
ID: field_of_dreams, Name: The Mind's Eye
ID: straying_far_afield, Name: Go Home Spiderman
ID: afield_a_complaint, Name: Red Swingline
```

**Rationale**: So you've got a collection and have no idea what to do with it? Well, you can always start by listing its fields. Yeah, let's list the fields.

--------------------------------------------------------------------------------

# Get Pagetypes: How To Get the Unfiltered URL Counts by Pagetype for a Specific Analysis


```python
import json
import httpx
import pandas as pd

# Load configuration and API key
config = json.load(open("config.json"))
api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
org = config['org']
website = config['project']  # Assuming 'project' here refers to the website
analysis_date = config['analysis']  # Date of analysis, formatted as 'YYYYMMDD'

def get_first_page_pagetype_url_counts(org, website, analysis_date, api_key, size=5000):
    """Fetch pagetype segmentation counts for the first page only, sorted by URL count in descending order."""
    url = f"https://app.botify.com/api/v1/projects/{org}/{website}/query?size={size}"
    
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
        "x-botify-client": "spa",
    }
    
    # Payload to retrieve pagetype segmentation counts, ordered by URL count
    data_payload = {
        "collections": [f"crawl.{analysis_date}"],
        "query": {
            "dimensions": [{"field": "segments.pagetype.value"}],
            "metrics": [{"field": f"crawl.{analysis_date}.count_urls_crawl"}],
            "sort": [
                {"type": "metrics", "index": 0, "order": "desc"},
                {"type": "dimensions", "index": 0, "order": "asc"}
            ]
        }
    }

    try:
        # Make a single request for the first page of results
        response = httpx.post(url, headers=headers, json=data_payload)
        response.raise_for_status()
        data = response.json()

        # Process the first page of results
        results = []
        for item in data.get("results", []):
            pagetype = item["dimensions"][0] if item["dimensions"] else "Unknown"
            count = item["metrics"][0] if item["metrics"] else 0
            results.append({"Pagetype": pagetype, "URL Count": count})
    
    except httpx.RequestError as e:
        print(f"Error fetching pagetype URL counts: {e}")
        return []
    
    return results

# Fetch pagetype URL counts for the first page only
results = get_first_page_pagetype_url_counts(org, website, analysis_date, api_key)

# Convert results to a DataFrame and save
df = pd.DataFrame(results)
df.to_csv("pagetype_url_counts.csv", index=False)
print("Data saved to pagetype_url_counts.csv")

# Display a preview
print(df)
```

**Sample Output**:

```
Data saved to pagetype_url_counts.csv
                 Pagetype  URL Count
0                    pdp     250000
1                    plp      50000
2                    hub       5000
3                   blog       2500
4                    faq        500
```

**Rationale**: Do you ever get the feeling a website's folder-structure can tell you something about how it's organized? Yeah, me too. Thankfully, we here at Botify do the ***Regular Expressions*** so you don't have to. And it makes really great great color-coding in the link-graph visualizations. Psst! Wanna see the Death Star?

--------------------------------------------------------------------------------

# Get Short Titles: How To Get the First 500 URLs With Short Titles Given Pagetype


```python
# Get the First 500 URLs With Short Titles Given Pagetype

import json
import httpx
import pandas as pd

api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
org = config['org']
project = config['project']
analysis = config['analysis']


def get_bqlv2_data(org, project, analysis, api_key):
    """Fetch data based on BQLv2 query for a specific Botify analysis."""
    url = f"https://api.botify.com/v1/projects/{org}/{project}/query"
    
    # BQLv2 query payload
    data_payload = {
        "collections": [f"crawl.{analysis}"],
        "query": {
            "dimensions": [
                f"crawl.{analysis}.url",
                f"crawl.{analysis}.metadata.title.len",
                f"crawl.{analysis}.metadata.title.content",
                f"crawl.{analysis}.metadata.title.quality",
                f"crawl.{analysis}.metadata.description.content",
                f"crawl.{analysis}.metadata.structured.breadcrumb.tree",
                f"crawl.{analysis}.metadata.h1.contents",
                f"crawl.{analysis}.metadata.h2.contents"
            ],
            "metrics": [],
            "filters": {
                "and": [
                    {
                        "field": f"crawl.{analysis}.scoring.issues.title_len",
                        "predicate": "eq",
                        "value": True
                    },
                    {
                        "field": f"crawl.{analysis}.segments.pagetype.depth_1",
                        "value": "pdp"
                    }
                ]
            },
            "sort": [
                {
                    "field": f"crawl.{analysis}.metadata.title.len",
                    "order": "asc"
                }
            ]
        }
    }

    headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}

    # Send the request
    # Allow up to a minute for the API to respond
    response = httpx.post(url, headers=headers, json=data_payload, timeout=60.0)
    response.raise_for_status()  # Check for errors
    
    return response.json()

# Run the query and load results
data = get_bqlv2_data(org, project, analysis, api_key)

# Flatten the data into a DataFrame
# Define column names for each dimension in the data
columns = [
    "url", "title_len", "title_content", "title_quality",
    "description_content", "breadcrumb_tree", "h1_contents", "h2_contents"
]
df = pd.DataFrame([item['dimensions'] for item in data['results']], columns=columns)

print("Data saved to titles_too_short.csv")

# Display all columns
pd.set_option('display.max_columns', None)

# Display all rows 
pd.set_option('display.max_rows', None)

# Increase column width to avoid truncation
pd.set_option('display.max_colwidth', None)

df.head(10)
```

**Sample Output**:

**Data saved to titles_too_short.csv**

| url                                      | title_len | title_content     | title_quality | description_content                                              | breadcrumb_tree                                       | h1_contents                     | h2_contents                             |
|------------------------------------------|-----------|-------------------|---------------|------------------------------------------------------------------|--------------------------------------------------------|----------------------------------|-----------------------------------------|
| https://www.example.com/site/socks/12345 | 8         | Sock Store        | unique        | Best socks for every season, unbeatable comfort and style.      | Example Store/Footwear/Accessories/Socks               | [Our Socks]                     | [Features, Sizes, Related Items]        |
| https://www.example.com/site/hats/98765  | 9         | Top Hats Here!    | duplicate     | Stylish hats available year-round with exclusive discounts.     | Example Store/Apparel/Accessories/Hats                 | [Hat Selection]                 | [Details, Reviews, Top Picks]           |
| https://www.example.com/site/shirts/54321| 10        | - Shirt Emporium  | duplicate     | Discover comfortable and stylish shirts at great prices.        | Example Store/Apparel/Topwear/Shirts                   | [Shirt Central]                 | [Sizing, Similar Styles, Reviews]       |

...

**Rationale**: Ahh, ***title tags***. They show in browser bookmarks, tabs and SERPs--the only relevancy factor that will remain standing after SEO Armageddon. You could ditch every other factor but ***anchor text***, set your uber-crawler go off-site, use a click-depth of 4--and harvest yourself a pretty good link-graph of the entire Internet... were it not for spammers.

--------------------------------------------------------------------------------

# Count Short Titles: How To Count Number of URLs Having Short Titles


```python
import json
import httpx

config = json.load(open("config.json"))
api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
org = config['org']
project = config['project']
analysis = config['analysis']

def count_short_titles(org, project, analysis, api_key):
    """Count URLs with short titles for a specific Botify analysis."""
    url = f"https://api.botify.com/v1/projects/{org}/{project}/query"
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json"
    }

    # Data payload for the count of URLs with short titles
    data_payload = {
        "collections": [f"crawl.{analysis}"],
        "query": {
            "dimensions": [],  # No dimensions needed, as we only need a count
            "metrics": [
                {
                    "function": "count",
                    "args": [f"crawl.{analysis}.url"]
                }
            ],
            "filters": {
                "field": f"crawl.{analysis}.scoring.issues.title_len",
                "predicate": "eq",
                "value": True
            }
        }
    }

    try:
        # Send the request
        response = httpx.post(url, headers=headers, json=data_payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        # Extract the count of URLs with short titles
        short_title_count = data["results"][0]["metrics"][0]
        return short_title_count
    except httpx.RequestError as e:
        print(f"Error fetching short title count for analysis '{analysis}' in project '{project}': {e}")
        return None

# Run the count query and display the result
short_title_count = count_short_titles(org, project, analysis, api_key)

if short_title_count is not None:
    print(f"Number of URLs with short titles: {short_title_count:,}")
else:
    print("Failed to retrieve the count of URLs with short titles.")

```

**Sample Output**:

    Number of URLs with short titles: 675,080

**Rationale**: Sometimes ya gotta count what you're trying to get before you go try and download it. Plus, learn ***filtering*** in the Botify API! But I think really I just wanted to show you how easy it is to format `f"{big_numbers:,}"` with commas using ***f-strings*** (I'm talking to you humans--because the LLMs *already know*).

--------------------------------------------------------------------------------

# Download CSV: How To Download Up to 10K URLs Having Short Titles As a CSV


```python
import json
import httpx
import time
import gzip
import shutil

config = json.load(open("config.json"))
api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
org = config['org']
project = config['project']
analysis = config['analysis']


def start_export_job_for_short_titles(org, project, analysis, api_key):
    """Start an export job for URLs with short titles, downloading key metadata fields."""
    url = "https://api.botify.com/v1/jobs"
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json"
    }

    # Data payload for the export job with necessary fields
    data_payload = {
        "job_type": "export",
        "payload": {
            "username": org,
            "project": project,
            "connector": "direct_download",
            "formatter": "csv",
            "export_size": 10000,  # Adjust as needed
            "query": {
                "collections": [f"crawl.{analysis}"],
                "query": {
                    "dimensions": [
                        f"crawl.{analysis}.url",
                        f"crawl.{analysis}.metadata.title.len",
                        f"crawl.{analysis}.metadata.title.content",
                        f"crawl.{analysis}.metadata.title.quality",
                        f"crawl.{analysis}.metadata.description.content",
                        f"crawl.{analysis}.metadata.h1.contents"
                    ],
                    "metrics": [],
                    "filters": {
                        "field": f"crawl.{analysis}.scoring.issues.title_len",
                        "predicate": "eq",
                        "value": True
                    },
                    "sort": [
                        {
                            "field": f"crawl.{analysis}.metadata.title.len",
                            "order": "asc"
                        }
                    ]
                }
            }
        }
    }

    try:
        print("Starting export job for short titles...")
        # Use a longer timeout to prevent ReadTimeout errors
        response = httpx.post(url, headers=headers, json=data_payload, timeout=300.0)
        response.raise_for_status()
        export_job_details = response.json()
        
        # Extract job URL for polling
        job_url = f"https://api.botify.com{export_job_details.get('job_url')}"
        
        # Polling for job completion
        print("Polling for job completion:", end=" ")
        while True:
            time.sleep(5)
            # Use a longer timeout for polling requests as well
            poll_response = httpx.get(job_url, headers=headers, timeout=120.0)
            poll_response.raise_for_status()
            job_status_details = poll_response.json()
            
            if job_status_details["job_status"] == "DONE":
                download_url = job_status_details["results"]["download_url"]
                print("\nDownload URL:", download_url)
                return download_url
            elif job_status_details["job_status"] == "FAILED":
                print("\nJob failed. Error details:", job_status_details)
                return None
            print(".", end="", flush=True)
        
    except httpx.ReadTimeout as e:
        print(f"\nTimeout error during export job: {e}")
        print("The API request timed out. Consider increasing the timeout value or try again later.")
        return None
    except httpx.RequestError as e:
        print(f"\nError starting or polling export job: {e}")
        return None


# Start export job and get download URL
download_url = start_export_job_for_short_titles(org, project, analysis, api_key)

# Download and decompress the file if the download URL is available
if download_url:
    gz_filename = "short_titles_export.csv.gz"
    csv_filename = "short_titles_export.csv"
    
    try:
        # Step 1: Download the gzipped CSV file with increased timeout
        response = httpx.get(download_url, timeout=300.0)
        with open(gz_filename, "wb") as gz_file:
            gz_file.write(response.content)
        print(f"File downloaded as '{gz_filename}'")
        
        # Step 2: Decompress the .gz file to .csv
        with gzip.open(gz_filename, "rb") as f_in:
            with open(csv_filename, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        print(f"File decompressed and saved as '{csv_filename}'")
    except httpx.ReadTimeout as e:
        print(f"Timeout error during file download: {e}")
        print("The download request timed out. Try again later or download manually from the URL.")
    except Exception as e:
        print(f"Error during file download or decompression: {e}")
else:
    print("Failed to retrieve the download URL.")
```

**Sample Output**:

    Starting export job for short titles...  
    Polling for job completion: .  
    Download URL: https://cdn.example.com/export_data/abc/def/ghi/xyz1234567890/funfetti-2024-11-08.csv.gz  
    File downloaded as 'short_titles_export.csv.gz'  
    File decompressed and saved as 'short_titles_export.csv'  

**Rationale**: Is it pulling or pooling? I could never remember. In either case, exporting and downloading csv-files is not as straightforward as you think. First, you make the request. Then you look for ***where*** to check progress, then keep re-checking until done. Then you sacrifice a chicken to help you debug useless errors. Lastly, you notice how your endpoint has changed to`https://api.botify.com/v1/jobs` with `org` and `project` moved into the JSON payload. Or is that firstly? Yeah, definitely firstly.

--------------------------------------------------------------------------------

# Get Total Count: How To Get Aggregate Count of All URLs Crawled During Analysis


```python
import json
import httpx

# --- 1. Configuration ---
# Load necessary details from files (adjust paths if needed)
# Basic error handling for loading is good practice even in tutorials
try:
    config = json.load(open("config.json"))
    api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
    # Get specific config values needed
    ORG_SLUG = config['org']
    PROJECT_SLUG = config['project']
    ANALYSIS_SLUG = config['analysis']
except FileNotFoundError:
    print("Error: 'config.json' or 'botify_token.txt' not found.")
    exit()
except KeyError as e:
    print(f"Error: Key '{e}' not found in 'config.json'.")
    exit()
except Exception as e:
    print(f"Error loading configuration: {e}")
    exit()

# TARGET_MAX_DEPTH is no longer needed for this calculation

# --- 2. Function to Get URL Counts Per Depth ---
def get_all_urls_by_depth(org, project, analysis, key):
    """
    Fetches URL counts for ALL depths from the Botify API.
    Returns a dictionary {depth: count} or None on error.
    """
    api_url = f"https://api.botify.com/v1/projects/{org}/{project}/query"
    headers = {"Authorization": f"Token {key}", "Content-Type": "application/json"}

    # This payload asks for counts grouped by depth, for the entire crawl
    payload = {
        "collections": [f"crawl.{analysis}"],
        "query": {
            "dimensions": [f"crawl.{analysis}.depth"],
            "metrics": [{"field": f"crawl.{analysis}.count_urls_crawl"}],
            "sort": [{"field": f"crawl.{analysis}.depth", "order": "asc"}]
        }
    }

    try:
        print("Requesting total URL count of site from Botify API...")
        response = httpx.post(api_url, headers=headers, json=payload, timeout=120.0)
        response.raise_for_status() # Check for HTTP errors (like 4xx, 5xx)
        print("Data received successfully.")

        # Convert the response list into a more usable {depth: count} dictionary
        results = response.json().get("results", [])
        depth_counts = {
            row["dimensions"][0]: row["metrics"][0]
            for row in results
            if "dimensions" in row and len(row["dimensions"]) > 0 and \
               "metrics" in row and len(row["metrics"]) > 0 and \
               isinstance(row["dimensions"][0], int) # Ensure depth is an int
        }
        return depth_counts

    except httpx.HTTPStatusError as e:
        print(f"API Error: {e.response.status_code} - {e.response.text}")
        return None # Indicate failure
    except Exception as e:
        print(f"An error occurred during API call or processing: {e}")
        return None # Indicate failure

# --- 3. Main Calculation (Grand Total) ---
# Get the depth data using the function
all_depth_data = get_all_urls_by_depth(ORG_SLUG, PROJECT_SLUG, ANALYSIS_SLUG, api_key)

# Proceed only if we got data back
if all_depth_data is not None:
    # Calculate the grand total by summing all counts
    grand_total_urls = 0
    print(f"\nCalculating the grand total number of URLs from all depths...")

    # Loop through all counts returned in the dictionary values and add them up
    for count in all_depth_data.values():
        grand_total_urls += count

    # --- Alternatively, you could use the sum() function directly: ---
    # grand_total_urls = sum(all_depth_data.values())
    # ----------------------------------------------------------------

    # Print the final result
    print(f"\nResult: Grand Total URLs in Crawl = {grand_total_urls:,}")
else:
    print("\nCould not calculate total because API data retrieval failed.")
```

**Sample Output**:

Requesting total URL count of site from Botify API...
Data received successfully.

Calculating the grand total number of URLs from all depths...

Result: Grand Total URLs in Crawl = 3,000,000

**Rationale**: Before doing a download of a CSV it is often worth checking if the number of rows returned will be under the 1-million row API limit.

--------------------------------------------------------------------------------

# Get Depth Count: How To Get Aggregate Count of URLs at Particular Click Depth


```python
import json
import httpx

# --- 1. Configuration ---
# Load necessary details from files (adjust paths if needed)
# Basic error handling for loading is good practice even in tutorials
try:
    config = json.load(open("config.json"))
    api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
    # Get specific config values needed
    ORG_SLUG = config['org']
    PROJECT_SLUG = config['project']
    ANALYSIS_SLUG = config['analysis']
except FileNotFoundError:
    print("Error: 'config.json' or 'botify_token.txt' not found.")
    exit()
except KeyError as e:
    print(f"Error: Key '{e}' not found in 'config.json'.")
    exit()
except Exception as e:
    print(f"Error loading configuration: {e}")
    exit()

# Define the maximum depth for our calculation
TARGET_MAX_DEPTH = 5

# --- 2. Function to Get URL Counts Per Depth ---
def get_all_urls_by_depth(org, project, analysis, key):
    """
    Fetches URL counts for ALL depths from the Botify API.
    Returns a dictionary {depth: count} or None on error.
    """
    api_url = f"https://api.botify.com/v1/projects/{org}/{project}/query"
    headers = {"Authorization": f"Token {key}", "Content-Type": "application/json"}

    # This payload asks for counts grouped by depth, for the entire crawl
    payload = {
        "collections": [f"crawl.{analysis}"],
        "query": {
            "dimensions": [f"crawl.{analysis}.depth"],
            "metrics": [{"field": f"crawl.{analysis}.count_urls_crawl"}],
            "sort": [{"field": f"crawl.{analysis}.depth", "order": "asc"}]
        }
    }

    try:
        print("Requesting data from Botify API...")
        response = httpx.post(api_url, headers=headers, json=payload, timeout=120.0)
        response.raise_for_status() # Check for HTTP errors (like 4xx, 5xx)
        print("Data received successfully.")

        # Convert the response list into a more usable {depth: count} dictionary
        results = response.json().get("results", [])
        depth_counts = {
            row["dimensions"][0]: row["metrics"][0]
            for row in results
            if "dimensions" in row and len(row["dimensions"]) > 0 and \
               "metrics" in row and len(row["metrics"]) > 0 and \
               isinstance(row["dimensions"][0], int) # Ensure depth is an int
        }
        return depth_counts

    except httpx.HTTPStatusError as e:
        print(f"API Error: {e.response.status_code} - {e.response.text}")
        return None # Indicate failure
    except Exception as e:
        print(f"An error occurred during API call or processing: {e}")
        return None # Indicate failure

# --- 3. Main Calculation ---
# Get the depth data using the function
all_depth_data = get_all_urls_by_depth(ORG_SLUG, PROJECT_SLUG, ANALYSIS_SLUG, api_key)

# Proceed only if we got data back
if all_depth_data is not None:
    total_count_at_or_below_depth = 0
    print(f"\nCalculating total for depth <= {TARGET_MAX_DEPTH}...")

    # Loop through the dictionary and sum counts for relevant depths
    for depth, count in all_depth_data.items():
        if depth <= TARGET_MAX_DEPTH:
            total_count_at_or_below_depth += count

    # Print the final result
    print(f"\nResult: Total URLs at depth {TARGET_MAX_DEPTH} or less = {total_count_at_or_below_depth:,}")
else:
    print("\nCould not calculate total because API data retrieval failed.")
```

**Sample Output**:

Attempting to get full URL distribution by depth...

Calculating total URLs for depth <= 5 from received data...

Total URLs at depth 5 or less: 1,500,000

**Rationale**: Before doing a download of a CSV it is often worth checking if the number of rows returned will be under the 1-million row API limit. By using a depth filter, we now have the foundation for reducing depth until we get a downloadable number.

--------------------------------------------------------------------------------

# Get Aggregates: How To Get Map of Click-Depths Aggregates Given Analysis Slug


```python
import json
import httpx
import pprint # Keep pprint for the final output as in the original

# --- 1. Configuration ---
# Load necessary details from files (adjust paths if needed)
try:
    config = json.load(open("config.json"))
    api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
    # Get specific config values needed
    ORG_SLUG = config['org']
    PROJECT_SLUG = config['project']
    ANALYSIS_SLUG = config['analysis']
    print("Configuration loaded successfully.")
except FileNotFoundError:
    print("Error: 'config.json' or 'botify_token.txt' not found.")
    exit(1)
except KeyError as e:
    print(f"Error: Key '{e}' not found in 'config.json'.")
    exit(1)
except Exception as e:
    print(f"Error loading configuration: {e}")
    exit(1)

# --- 2. Function to Get URL Counts Per Depth ---
# (Kept original function name)
def get_urls_by_depth(org, project, analysis, key):
    """
    Fetches URL counts aggregated by depth from the Botify API.
    Returns a dictionary {depth: count} or an empty {} on error.
    (Matches original functionality return type on error)
    """
    # Use clearer variable name for URL
    api_url = f"https://api.botify.com/v1/projects/{org}/{project}/query"
    headers = {"Authorization": f"Token {key}", "Content-Type": "application/json"}

    # Use clearer variable name for payload
    payload = {
        "collections": [f"crawl.{analysis}"],
        "query": {
            "dimensions": [f"crawl.{analysis}.depth"],
            "metrics": [{"field": f"crawl.{analysis}.count_urls_crawl"}],
            "sort": [{"field": f"crawl.{analysis}.depth", "order": "asc"}]
        }
    }

    try:
        print("Requesting URL counts per depth from Botify API...")
        # Use a longer timeout (e.g., 120 seconds)
        response = httpx.post(api_url, headers=headers, json=payload, timeout=120.0)
        response.raise_for_status() # Check for HTTP errors (like 4xx, 5xx)
        print("Data received successfully.")

        # Convert the response list into a more usable {depth: count} dictionary
        # Add validation during processing
        response_data = response.json()
        results = response_data.get("results", [])

        depth_distribution = {}
        print("Processing API response...")
        for row in results:
             # Validate structure before accessing keys/indices
             if "dimensions" in row and len(row["dimensions"]) == 1 and \
                "metrics" in row and len(row["metrics"]) == 1:
                 depth = row["dimensions"][0]
                 count = row["metrics"][0]
                 # Ensure depth is an integer
                 if isinstance(depth, int):
                     depth_distribution[depth] = count
                 else:
                     print(f"Warning: Skipping row with non-integer depth: {row}")
             else:
                 print(f"Warning: Skipping row with unexpected structure: {row}")

        print("Processing complete.")
        return depth_distribution # Return the dictionary with results

    # Adopt more specific error handling from the target style
    except httpx.ReadTimeout:
        print("Request timed out after 120 seconds.")
        return {} # Return empty dict per original functionality
    except httpx.HTTPStatusError as e:
        print(f"API Error: {e.response.status_code} - {e.response.reason_phrase}")
        try:
            # Attempt to show detailed API error message
            error_details = e.response.json()
            print(f"Error details: {error_details}")
        except json.JSONDecodeError:
            # Fallback if response is not JSON
            print(f"Response content: {e.response.text}")
        return {} # Return empty dict per original functionality
    except httpx.RequestError as e:
        # Handles other request errors like connection issues
        print(f"An error occurred during the request: {e}")
        return {} # Return empty dict per original functionality
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
         # Catch issues during JSON processing or accessing expected keys/indices
         print(f"Error processing API response: {e}")
         if 'response' in locals(): # Log raw response if available
              print(f"Response Text: {response.text}")
         return {} # Return empty dict per original functionality
    except Exception as e:
        # Catch-all for any other unexpected errors in this function
        print(f"An unexpected error occurred in get_urls_by_depth: {e}")
        return {} # Return empty dict per original functionality


# --- 3. Main Execution ---
print("\nStarting script execution to get URL distribution by depth...")
try:
    # Call the function using loaded config variables
    depth_distribution_result = get_urls_by_depth(
        ORG_SLUG, PROJECT_SLUG, ANALYSIS_SLUG, api_key
    )

    # Check if the result is not an empty dictionary
    # An empty dict signifies an error occurred in the function OR no data found
    if depth_distribution_result: # A non-empty dict evaluates to True
        print("\n--- URL Distribution by Depth ---")
        # Use pprint for formatted output as in the original script
        pprint.pprint(depth_distribution_result, width=1)
        print("---------------------------------")
    else:
        # This message prints if the function returned {}
        print("\nRetrieved empty distribution. This could be due to an error (check logs above) or no URLs found.")

except Exception as e:
    # Catch any unexpected errors during the main execution sequence
    print(f"An unexpected error occurred during the main execution: {e}")
```

**Sample Output**:

```plaintext
Configuration loaded successfully.

Starting script execution to get URL distribution by depth...
Requesting URL counts per depth from Botify API...
Data received successfully.
Processing API response...
Processing complete.
{ 0: 10,        # Start pages (kept small)
  1: 550,
  2: 28000,     # Rounded 5k * 5.5
  3: 275000,    # 50k * 5.5
  4: 825000,    # Peak (150k * 5.5)
  5: 660000,    # Starting decline (120k * 5.5)
  6: 440000,    # 80k * 5.5
  7: 275000,    # 50k * 5.5
  8: 165000,    # 30k * 5.5
  9: 110000,    # 20k * 5.5
 10: 55000,     # 10k * 5.5
 11: 44000,     # 8k * 5.5
 12: 33000,     # 6k * 5.5
 13: 28000,     # Rounded 5k * 5.5
 14: 22000,     # 4k * 5.5
 15: 17000,     # Rounded 3k * 5.5
 16: 11000,     # 2k * 5.5
 17: 6000,      # Rounded 1k * 5.5
 18: 3000,      # Rounded 500 * 5.5
 19: 1100,      # 200 * 5.5
 20: 550 }      # 100 * 5.5
--------------------------------------------------
```

**Rationale**: This depth distribution shows how many URLs exist at each click depth level from the homepage (hompage = depth 0). A healthy site typically has most content within 3 or 4 clicks of the homepage. Much more, and it may as well not exist. Such reports help identify potential deep crawl issues, spider-traps, and why (in addition to the infinite spam-cannon of generative AI content), brute-force crawls that *"make a copy of the Internet"* are all but dead. And did I mention that excessively crawl-able faceted search makes your site's link-graph look like the Death Star? Yeah, I think I did.

--------------------------------------------------------------------------------

# Get Aggregates: How To Get Map of CUMULATIVE Click-Depths Aggregates Given Analysis Slug


```python
import json
import httpx
import pprint # Keep pprint for the final output

# --- 1. Configuration ---
# Load necessary details from files (adjust paths if needed)
try:
    config = json.load(open("config.json"))
    api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
    # Get specific config values needed
    ORG_SLUG = config['org']
    PROJECT_SLUG = config['project']
    ANALYSIS_SLUG = config['analysis']
    print("Configuration loaded successfully.")
except FileNotFoundError:
    print("Error: 'config.json' or 'botify_token.txt' not found.")
    exit(1)
except KeyError as e:
    print(f"Error: Key '{e}' not found in 'config.json'.")
    exit(1)
except Exception as e:
    print(f"Error loading configuration: {e}")
    exit(1)

# --- 2. Function to Get URL Counts Per Depth ---
# (This function remains unchanged as it fetches the base data needed)
def get_urls_by_depth(org, project, analysis, key):
    """
    Fetches URL counts aggregated by depth from the Botify API.
    Returns a dictionary {depth: count} or an empty {} on error.
    """
    api_url = f"https://api.botify.com/v1/projects/{org}/{project}/query"
    headers = {"Authorization": f"Token {key}", "Content-Type": "application/json"}
    payload = {
        "collections": [f"crawl.{analysis}"],
        "query": {
            "dimensions": [f"crawl.{analysis}.depth"],
            "metrics": [{"field": f"crawl.{analysis}.count_urls_crawl"}],
            "sort": [{"field": f"crawl.{analysis}.depth", "order": "asc"}]
        }
    }
    try:
        print("Requesting URL counts per depth from Botify API...")
        response = httpx.post(api_url, headers=headers, json=payload, timeout=120.0)
        response.raise_for_status()
        print("Data received successfully.")
        response_data = response.json()
        results = response_data.get("results", [])
        depth_distribution = {}
        print("Processing API response...")
        for row in results:
             if "dimensions" in row and len(row["dimensions"]) == 1 and \
                "metrics" in row and len(row["metrics"]) == 1:
                 depth = row["dimensions"][0]
                 count = row["metrics"][0]
                 if isinstance(depth, int):
                     depth_distribution[depth] = count
                 else:
                     print(f"Warning: Skipping row with non-integer depth: {row}")
             else:
                 print(f"Warning: Skipping row with unexpected structure: {row}")
        print("Processing complete.")
        return depth_distribution
    except httpx.ReadTimeout:
        print("Request timed out after 120 seconds.")
        return {}
    except httpx.HTTPStatusError as e:
        print(f"API Error: {e.response.status_code} - {e.response.reason_phrase}")
        try:
            error_details = e.response.json()
            print(f"Error details: {error_details}")
        except json.JSONDecodeError:
            print(f"Response content: {e.response.text}")
        return {}
    except httpx.RequestError as e:
        print(f"An error occurred during the request: {e}")
        return {}
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
         print(f"Error processing API response: {e}")
         if 'response' in locals():
              print(f"Response Text: {response.text}")
         return {}
    except Exception as e:
        print(f"An unexpected error occurred in get_urls_by_depth: {e}")
        return {}


# --- 3. Main Execution ---
print("\nStarting script execution...")
try:
    # Call the function to get the dictionary {depth: count_at_depth}
    depth_distribution_result = get_urls_by_depth(
        ORG_SLUG, PROJECT_SLUG, ANALYSIS_SLUG, api_key
    )

    # Check if the result is not an empty dictionary (which indicates an error)
    if depth_distribution_result: # A non-empty dict evaluates to True
        print("\nCalculating cumulative URL counts by depth...")

        # --- Calculate Cumulative Distribution ---
        cumulative_depth_distribution = {}
        current_cumulative_sum = 0
        # Get the depths present and sort them to process in order (0, 1, 2...)
        # Handle case where result might be empty just in case, though checked above
        sorted_depths = sorted(depth_distribution_result.keys())
        max_depth_found = sorted_depths[-1] if sorted_depths else -1

        # Iterate from depth 0 up to the maximum depth found in the results
        for depth_level in range(max_depth_found + 1):
            # Get the count for this specific depth_level from the original results.
            # Use .get(depth, 0) in case a depth level has no URLs (e.g., depth 0 might be missing if start page redirected)
            count_at_this_level = depth_distribution_result.get(depth_level, 0)

            # Add this level's count to the running cumulative sum
            current_cumulative_sum += count_at_this_level

            # Store the *cumulative* sum in the new dictionary for this depth level
            cumulative_depth_distribution[depth_level] = current_cumulative_sum
        # --- End Calculation ---

        print("\n--- Cumulative URL Distribution by Depth (URLs <= Depth) ---")
        # Use pprint for formatted output of the NEW cumulative dictionary
        pprint.pprint(cumulative_depth_distribution, width=1)
        print("----------------------------------------------------------")

    else:
        # This message prints if the function returned {}
        print("\nRetrieved empty distribution. Cannot calculate cumulative counts.")

except Exception as e:
    # Catch any unexpected errors during the main execution sequence
    print(f"An unexpected error occurred during the main execution: {e}")
```

**Sample Output**:

```plaintext
Configuration loaded successfully.

Starting script execution...
Requesting URL counts per depth from Botify API...
Data received successfully.
Processing API response...
Processing complete.

Calculating cumulative URL counts by depth...
{ 0: 10,
  1: 560,          # (10 + 550)
  2: 28560,        # (560 + 28000)
  3: 303560,       # (28560 + 275000)
  4: 1128560,      # (303560 + 825000) <-- Reaches 1M+
  5: 1788560,      # (1128560 + 660000)
  6: 2228560,      # (1788560 + 440000) <-- Reaches 2M+
  7: 2503560,      # (2228560 + 275000)
  8: 2668560,      # (2503560 + 165000)
  9: 2778560,      # (2668560 + 110000)
 10: 2833560,      # (2778560 + 55000) <-- Growth significantly slower now
 11: 2877560,      # (2833560 + 44000)
 12: 2910560,      # (2877560 + 33000)
 13: 2938560,      # (2910560 + 28000)
 14: 2960560,      # (2938560 + 22000)
 15: 2977560,      # (2960560 + 17000)
 16: 2988560,      # (2977560 + 11000)
 17: 2994560,      # (2988560 + 6000)
 18: 2997560,      # (2994560 + 3000)
 19: 2998660,      # (2997560 + 1100)
 20: 2999210 }      # (2998660 + 550) <-- Final cumulative total ~3M
------------------------------------------------------------
```

**Rationale**: This depth distribution shows how many URLs exist at each click depth level from the homepage (hompage = depth 0). A healthy site typically has most content within 3 or 4 clicks of the homepage. Much more, and it may as well not exist. Such reports help identify potential deep crawl issues, spider-traps, and why (in addition to the infinite spam-cannon of generative AI content), brute-force crawls that *"make a copy of the Internet"* are all but dead. And did I mention that excessively crawl-able faceted search makes your site's link-graph look like the Death Star? Yeah, I think I did.

--------------------------------------------------------------------------------

# Download Link Graph: How to Download a Link Graph for a Specified Organization, Project, and Analysis For Website Visualization.


```python
import os
import time
import json
from pathlib import Path
import httpx
import pandas as pd

# Load configuration and API key
config = json.load(open("config.json"))
api_key = open('botify_token.txt').read().strip().split('\n')[0].strip()
org = config['org']
project = config['project']
analysis = config['analysis']

# Define API headers
headers = {
    "Authorization": f"Token {api_key}",
    "Content-Type": "application/json"
}

# Determine optimal click depth for link graph export
def find_optimal_depth(org, project, analysis, max_edges=1000000):
    """
    Determine the highest depth for which the number of edges does not exceed max_edges.
    """
    url = f"https://api.botify.com/v1/projects/{org}/{project}/query"
    # httpx doesn't have Session, use Client instead
    client = httpx.Client()
    previous_edges = 0

    for depth in range(1, 10):
        data_payload = {
            "collections": [f"crawl.{analysis}"],
            "query": {
                "dimensions": [],
                "metrics": [{"function": "sum", "args": [f"crawl.{analysis}.outlinks_internal.nb.total"]}],
                "filters": {"field": f"crawl.{analysis}.depth", "predicate": "lte", "value": depth},
            },
        }

        response = client.post(url, headers=headers, json=data_payload)
        data = response.json()
        edges = data["results"][0]["metrics"][0]

        print(f"Depth {depth}: {edges:,} edges")

        if edges > max_edges or edges == previous_edges:
            return depth - 1 if depth > 1 else depth, previous_edges

        previous_edges = edges

    return depth, previous_edges

# Export link graph to CSV
def export_link_graph(org, project, analysis, chosen_depth, save_path="downloads"):
    """
    Export link graph up to the chosen depth level and save as a CSV.
    """
    url = "https://api.botify.com/v1/jobs"
    data_payload = {
        "job_type": "export",
        "payload": {
            "username": org,
            "project": project,
            "connector": "direct_download",
            "formatter": "csv",
            "export_size": 1000000,
            "query": {
                "collections": [f"crawl.{analysis}"],
                "query": {
                    "dimensions": [
                        "url",
                        f"crawl.{analysis}.outlinks_internal.graph.url",
                    ],
                    "metrics": [],
                    "filters": {"field": f"crawl.{analysis}.depth", "predicate": "lte", "value": chosen_depth},
                },
            },
        }
    }

    response = httpx.post(url, headers=headers, json=data_payload)
    export_job_details = response.json()
    job_url = f"https://api.botify.com{export_job_details.get('job_url')}"

    # Polling for job completion
    attempts = 300
    delay = 3
    while attempts > 0:
        time.sleep(delay)
        response_poll = httpx.get(job_url, headers=headers)
        job_status_details = response_poll.json()
        if job_status_details["job_status"] == "DONE":
            download_url = job_status_details["results"]["download_url"]
            save_as_filename = Path(save_path) / f"{org}_{project}_{analysis}_linkgraph_depth-{chosen_depth}.csv"
            download_file(download_url, save_as_filename)
            return save_as_filename
        elif job_status_details["job_status"] == "FAILED":
            print("Export job failed.")
            return None
        print(".", end="", flush=True)
        attempts -= 1

    print("Unable to complete download attempts successfully.")
    return None

# Download file function
def download_file(url, save_path):
    """
    Download a file from a URL to a specified local path.
    """
    # Fix: httpx.get() doesn't support 'stream' parameter directly
    with httpx.Client() as client:
        with client.stream("GET", url) as response:
            with open(save_path, "wb") as file:
                for chunk in response.iter_bytes(chunk_size=8192):
                    file.write(chunk)
    print(f"\nFile downloaded as '{save_path}'")

# Main execution
print("Determining optimal depth for link graph export...")
chosen_depth, final_edges = find_optimal_depth(org, project, analysis)
print(f"Using depth {chosen_depth} with {final_edges:,} edges for export.")

# Make sure the downloads folder exists
downloads_folder = Path("downloads")
downloads_folder.mkdir(parents=True, exist_ok=True)

print("Starting link graph export...")
link_graph_path = export_link_graph(org, project, analysis, chosen_depth, save_path="downloads")

if link_graph_path:
    print(f"Link graph saved to: {link_graph_path}")
else:
    print("Link graph export failed.")
```

**Sample Output**:
```
Determining optimal depth for link graph export...
Depth 1: 50,000 edges
Depth 2: 120,000 edges
Depth 3: 500,000 edges
Depth 4: 1,200,000 edges
Using depth 3 with 500,000 edges for export.
Starting link graph export...
Polling for job completion: ...
Download URL: https://botify-export-url.com/file.csv
File downloaded as 'downloads/org_project_analysis_linkgraph_depth-3.csv'
Link graph saved to: downloads/org_project_analysis_linkgraph_depth-3.csv
```

**Rationale**: And now, the moment you’ve all been waiting for--the elusive, hard-to-visualize link-graph of your website. Think Admiral Ackbar scrutinizing a hologram of the Death Star, examining every strength and vulnerability, now superimposed with Google Search Console Clicks and Impressions. The Rebels lean in, studying surprise hot spots and patches of dead wood. Every faceted search site ends up looking like the Death Star. But if you’ve done it right, with solid topical clustering, you’ll have something that resembles broccoli or cauliflower... are those called nodules? Florets? Either way, it’s a good look.

--------------------------------------------------------------------------------

# Check Link-Graph Enhancements: How To Check What Data is Available to Enhance Link-Graph Visualization.


```python
import os
import json
import httpx
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import List

# Load configuration and API key
headers = {
    "Authorization": f"Token {open('botify_token.txt').read().strip()}",
    "Content-Type": "application/json"
}

def preview_data(org, project, analysis, depth=1):
    """Preview data availability before committing to full download"""
    # Get analysis date from the slug (assuming YYYYMMDD format)
    analysis_date = datetime.strptime(analysis, '%Y%m%d')
    # Calculate period start (7 days before analysis date)
    period_start = (analysis_date - timedelta(days=7)).strftime('%Y-%m-%d')
    period_end = analysis_date.strftime('%Y-%m-%d')
    
    url = f"https://api.botify.com/v1/projects/{org}/{project}/query"
    
    data_payload = {
        "collections": [
            f"crawl.{analysis}",
            "search_console"
        ],
        "query": {
            "dimensions": [
                f"crawl.{analysis}.url"
            ],
            "metrics": [
                "search_console.period_0.count_impressions",
                "search_console.period_0.count_clicks"
            ],
            "filters": {
                "field": f"crawl.{analysis}.depth",
                "predicate": "lte",
                "value": depth
            },
            "sort": [
                {
                    "field": "search_console.period_0.count_impressions",
                    "order": "desc"
                }
            ]
        },
        "periods": [
            [
                period_start,
                period_end
            ]
        ]
    }

    print(f"\n🔍 Sampling data for {org}/{project}/{analysis}")
    print("=" * 50)

    response = httpx.post(url, headers=headers, json=data_payload)
    if response.status_code != 200:
        print("❌ Preview failed:", response.status_code)
        return False
        
    data = response.json()
    if not data.get('results'):
        print("⚠️  No preview data available")
        return False
        
    print("\n📊 Data Sample Analysis")
    print("-" * 30)
    metrics_found = 0
    for result in data['results'][:3]:  # Show just top 3 for cleaner output
        url = result['dimensions'][0]
        impressions = result['metrics'][0]
        clicks = result['metrics'][1]
        metrics_found += bool(impressions or clicks)
        print(f"• URL: {url[:60]}...")
        print(f"  └─ Performance: {impressions:,} impressions, {clicks:,} clicks")
    
    print("\n🎯 Data Quality Check")
    print("-" * 30)
    print(f"✓ URLs found: {len(data['results'])}")
    print(f"✓ Search metrics: {'Available' if metrics_found else 'Not found'}")
    print(f"✓ Depth limit: {depth}")
    
    return True

def get_bqlv2_data(org, project, analysis):
    """Fetch data based on BQLv2 query for a specific Botify analysis."""
    collection = f"crawl.{analysis}"
    
    # Calculate dates
    analysis_date = datetime.strptime(analysis, '%Y%m%d')
    period_start = (analysis_date - timedelta(days=7)).strftime('%Y-%m-%d')
    period_end = analysis_date.strftime('%Y-%m-%d')
    
    url = f"https://api.botify.com/v1/projects/{org}/{project}/query"
    
    # Base dimensions that should always be available in crawl
    base_dimensions = [
        f"{collection}.url",
        f"{collection}.depth",
    ]
    
    # Optional dimensions that might not be available
    optional_dimensions = [
        f"{collection}.segments.pagetype.value",
        f"{collection}.compliant.is_compliant",
        f"{collection}.compliant.main_reason",
        f"{collection}.canonical.to.equal",
        f"{collection}.sitemaps.present",
        f"{collection}.js.rendering.exec",
        f"{collection}.js.rendering.ok"
    ]
    
    # Optional metrics from other collections
    optional_metrics = [
        "search_console.period_0.count_impressions",
        "search_console.period_0.count_clicks"
    ]
    
    # First, let's check which collections are available
    collections = [collection]  # Using full collection name
    try:
        # We could add an API call here to check available collections
        # For now, let's assume search_console might be available
        collections.append("search_console")
    except Exception as e:
        print(f"Search Console data not available: {e}")
    
    data_payload = {
        "collections": collections,
        "query": {
            "dimensions": base_dimensions + optional_dimensions,
            "metrics": optional_metrics if "search_console" in collections else [],
            "filters": {
                "field": f"{collection}.depth",
                "predicate": "lte",
                "value": 2
            },
            "sort": [
                {
                    "field": "search_console.period_0.count_impressions" if "search_console" in collections else f"{collection}.depth",
                    "order": "desc" if "search_console" in collections else "asc"
                }
            ]
        },
        "periods": [[period_start, period_end]] if "search_console" in collections else None
    }

    print(f"Query payload: {json.dumps(data_payload, indent=2)}")
    response = httpx.post(url, headers=headers, json=data_payload)
    
    if response.status_code != 200:
        print(f"Error response: {response.text}")
        response.raise_for_status()
    
    data = response.json()
    
    # Define all possible columns
    all_columns = ['url', 'depth', 'pagetype', 'compliant', 'reason', 'canonical', 
                  'sitemap', 'js_exec', 'js_ok', 'impressions', 'clicks']
    
    # Create DataFrame with available data
    results = []
    for item in data['results']:
        # Fill missing dimensions/metrics with None
        row = item['dimensions']
        if 'metrics' in item:
            row.extend(item['metrics'])
        while len(row) < len(all_columns):
            row.append(None)
        results.append(row)
    
    df = pd.DataFrame(results, columns=all_columns)
    
    return df

def fetch_fields(org: str, project: str, collection: str) -> List[str]:
    """
    Fetch available fields for a given collection from the Botify API.
    
    Args:
        org: Organization slug
        project: Project slug  
        collection: Collection name (e.g. 'crawl.20241108')
        
    Returns:
        List of field IDs available in the collection
    """
    fields_url = f"https://api.botify.com/v1/projects/{org}/{project}/collections/{collection}"
    
    try:
        response = httpx.get(fields_url, headers=headers)
        response.raise_for_status()
        fields_data = response.json()
        return [
            field['id'] 
            for dataset in fields_data.get('datasets', [])
            for field in dataset.get('fields', [])
        ]
    except httpx.RequestError as e:
        print(f"Error fetching fields for collection '{collection}': {e}")
        return []

def check_compliance_fields(org, project, analysis):
    """Check available compliance fields in a more structured way."""
    collection = f"crawl.{analysis}"
    url = f"https://api.botify.com/v1/projects/{org}/{project}/query"
    
    # Group compliance fields by category
    compliance_categories = {
        'Basic Compliance': [
            'compliant.is_compliant',
            'compliant.main_reason',
            'compliant.reason.http_code',
            'compliant.reason.content_type',
            'compliant.reason.canonical',
            'compliant.reason.noindex',
            'compliant.detailed_reason'
        ],
        'Performance': [
            'scoring.issues.slow_first_to_last_byte_compliant',
            'scoring.issues.slow_render_time_compliant',
            'scoring.issues.slow_server_time_compliant',
            'scoring.issues.slow_load_time_compliant'
        ],
        'SEO': [
            'scoring.issues.duplicate_query_kvs_compliant'
        ],
        'Outlinks': [
            'outlinks_errors.non_compliant.nb.follow.unique',
            'outlinks_errors.non_compliant.nb.follow.total',
            'outlinks_errors.non_compliant.urls'
        ]
    }
    
    print("\n🔍 Field Availability Analysis")
    print("=" * 50)
    available_count = 0
    total_count = sum(len(fields) for fields in compliance_categories.values())
    
    available_fields = []
    for category, fields in compliance_categories.items():
        available_in_category = 0
        print(f"\n📑 {category}")
        print("-" * 30)
        for field in fields:
            full_field = f"{collection}.{field}"
            # Test field availability with a minimal query
            test_query = {
                "collections": [collection],
                "query": {
                    "dimensions": [full_field],
                    "filters": {"field": f"{collection}.depth", "predicate": "eq", "value": 0}
                }
            }
            
            try:
                response = httpx.post(url, headers=headers, json=test_query, timeout=60)
                if response.status_code == 200:
                    available_in_category += 1
                    available_count += 1
                    print(f"✓ {field.split('.')[-1]}")
                    available_fields.append(field)
                else:
                    print(f"× {field.split('.')[-1]}")
            except Exception as e:
                print(f"? {field.split('.')[-1]} (error checking)")
    
    coverage = (available_count / total_count) * 100
    print(f"\n📊 Field Coverage: {coverage:.1f}%")
    return available_fields

def main():
    """Main execution logic"""
    try:
        with open('config.json') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("Error: config.json file not found")
        return
    except json.JSONDecodeError:
        print("Error: config.json is not valid JSON")
        return
    
    org = config.get('org')
    project = config.get('project')
    analysis = config.get('analysis')
    
    if not all([org, project, analysis]):
        print("Error: Missing required fields in config.json (org, project, analysis)")
        return
    
    print("Previewing data availability...")
    if preview_data(org, project, analysis, depth=2):
        print("Data preview successful. Proceeding with full export...")
        print("Fetching BQLv2 data...")
        df = get_bqlv2_data(org, project, analysis)
        print("\nData Preview:")
        print(df.head())

        # Save to CSV
        Path("downloads").mkdir(parents=True, exist_ok=True)
        output_file = f"downloads/{org}_{project}_{analysis}_metadata.csv"
        df.to_csv(output_file, index=False)
        print(f"\nData saved to {output_file}")
        
        # Use check_compliance_fields
        check_compliance_fields(org, project, analysis)
    else:
        print("Data preview failed. Please check configuration and try again.")

if __name__ == "__main__":
    main()
```

**Sample Output**:

    Previewing data availability...
    
    🔍 Sampling data for example/retail-division/20241108
    ==================================================
    
    📊 Data Sample Analysis
------------------------
    • URL: https://www.example.com/...
      └─ Performance: 123,456 impressions, 12,345 clicks
    • URL: https://www.example.com/site/retail/seasonal-sale/pcmcat...
      └─ Performance: 98,765 impressions, 8,765 clicks
    • URL: https://www.example.com/site/misc/daily-deals/pcmcat2480...
      └─ Performance: 54,321 impressions, 4,321 clicks
    
    🎯 Data Quality Check
------------------------
    ✓ URLs found: 404
    ✓ Search metrics: Available
    ✓ Depth limit: 2
    Data preview successful. Proceeding with full export...
    Fetching BQLv2 data...
    Query payload: {
      "collections": [
        "crawl.20241108",
        "search_console"
      ],
      "query": {
        "dimensions": [
          "crawl.20241108.url",
          "crawl.20241108.depth",
          "crawl.20241108.segments.pagetype.value",
          "crawl.20241108.compliant.is_compliant",
          "crawl.20241108.compliant.main_reason",
          "crawl.20241108.canonical.to.equal",
          "crawl.20241108.sitemaps.present",
          "crawl.20241108.js.rendering.exec",
          "crawl.20241108.js.rendering.ok"
        ],
        "metrics": [
          "search_console.period_0.count_impressions",
          "search_console.period_0.count_clicks"
        ],
        "filters": {
          "field": "crawl.20241108.depth",
          "predicate": "lte",
          "value": 2
        },
        "sort": [
          {
            "field": "search_console.period_0.count_impressions",
            "order": "desc"
          }
        ]
      },
      "periods": [
        [
          "2024-11-01",
          "2024-11-08"
        ]
      ]
    }
    
    Data Preview:
                                                                                                                            url  \
    0  https://www.example.com/realm/shops/merchants-quarter/enchanted-items/
    1  https://www.example.com/realm/elven-moonlight-potion-azure/
    2  https://www.example.com/realm/dwarven-decorative-runes-sapphire/   
    3  https://www.example.com/realm/legendary-artifacts/master-crafted-items/   
    4  ttps://www.example.com/realm/orcish-war-drums-obsidian/    
    
       depth       pagetype  compliant     reason canonical  sitemap  js_exec  \
    0      0           home       True  Indexable      True    False     True   
    1      2            pdp       True  Indexable      True    False     True   
    2      1            plp       True  Indexable      True    False     True   
    3      1       category       True  Indexable      True    False     True   
    4      1           main       True  Indexable      True    False     True   
    
       js_ok  impressions  clicks  
    0  False       123456   12345  
    1  False        98765    8765  
    2  False        54321    4321  
    3  False        11111    1111  
    4  False        12345    1234  
    
    Data saved to downloads/example_retail-division_20241108_metadata.csv

**Rationale**: Just because you happen to work at an enterprise SEO company and possess this peculiar intersection of skills--like crafting prompts that give LLMs instant deep-knowledge (think Neo suddenly knowing kung fu)--doesn't mean you actually understand BQL. In fact, needing to write this prompt rather proves the opposite... wait, did I just create a paradox? Anyway, there's a very subtle chicken-and-egg problem that this file in general and this example in particular helps address: ***validation of collection fields*** so you can template automations without them being too fragile.

--------------------------------------------------------------------------------

# Color-Code Link-Graphs: How To Download Data to Enhance Website Link-Graph Visualization.


```python
import os
import json
import httpx
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import List
import gzip
import shutil
import time

# Load configuration and API key
headers = {
    "Authorization": f"Token {open('botify_token.txt').read().strip()}",
    "Content-Type": "application/json"
}

def preview_data(org, project, analysis, depth=1):
    """Preview data availability before committing to full download"""
    # Get analysis date from the slug (assuming YYYYMMDD format)
    analysis_date = datetime.strptime(analysis, '%Y%m%d')
    # Calculate period start (7 days before analysis date)
    period_start = (analysis_date - timedelta(days=7)).strftime('%Y-%m-%d')
    period_end = analysis_date.strftime('%Y-%m-%d')
    
    url = f"https://api.botify.com/v1/projects/{org}/{project}/query"
    
    data_payload = {
        "collections": [
            f"crawl.{analysis}",
            "search_console"
        ],
        "query": {
            "dimensions": [
                f"crawl.{analysis}.url"
            ],
            "metrics": [
                "search_console.period_0.count_impressions",
                "search_console.period_0.count_clicks"
            ],
            "filters": {
                "field": f"crawl.{analysis}.depth",
                "predicate": "lte",
                "value": depth
            },
            "sort": [
                {
                    "field": "search_console.period_0.count_impressions",
                    "order": "desc"
                }
            ]
        },
        "periods": [
            [
                period_start,
                period_end
            ]
        ]
    }

    print(f"\n🔍 Sampling data for {org}/{project}/{analysis}")
    print("=" * 50)

    response = httpx.post(url, headers=headers, json=data_payload)
    if response.status_code != 200:
        print("❌ Preview failed:", response.status_code)
        return False
        
    data = response.json()
    if not data.get('results'):
        print("⚠️  No preview data available")
        return False
        
    print("\n📊 Data Sample Analysis")
    print("-" * 30)
    metrics_found = 0
    for result in data['results'][:3]:  # Show just top 3 for cleaner output
        url = result['dimensions'][0]
        impressions = result['metrics'][0]
        clicks = result['metrics'][1]
        metrics_found += bool(impressions or clicks)
        print(f"• URL: {url[:60]}...")
        print(f"  └─ Performance: {impressions:,} impressions, {clicks:,} clicks")
    
    print("\n🎯 Data Quality Check")
    print("-" * 30)
    print(f"✓ URLs found: {len(data['results'])}")
    print(f"✓ Search metrics: {'Available' if metrics_found else 'Not found'}")
    print(f"✓ Depth limit: {depth}")
    
    return True

def get_bqlv2_data(org, project, analysis):
    """Fetch BQLv2 data using jobs endpoint"""
    # Calculate periods
    analysis_date = datetime.strptime(analysis, '%Y%m%d')
    period_start = (analysis_date - timedelta(days=7)).strftime('%Y-%m-%d')
    period_end = analysis_date.strftime('%Y-%m-%d')
    
    url = "https://api.botify.com/v1/jobs"
    
    data_payload = {
        "job_type": "export",
        "payload": {
            "username": org,
            "project": project,
            "connector": "direct_download",
            "formatter": "csv",
            "export_size": 1000000,
            "query": {
                "collections": [
                    f"crawl.{analysis}",
                    "search_console"
                ],
                "periods": [[period_start, period_end]],
                "query": {
                    "dimensions": [
                        f"crawl.{analysis}.url", 
                        f"crawl.{analysis}.depth",
                        f"crawl.{analysis}.segments.pagetype.value",
                        f"crawl.{analysis}.compliant.is_compliant",
                        f"crawl.{analysis}.compliant.main_reason",
                        f"crawl.{analysis}.canonical.to.equal",
                        f"crawl.{analysis}.sitemaps.present",
                        f"crawl.{analysis}.js.rendering.exec",
                        f"crawl.{analysis}.js.rendering.ok"
                    ],
                    "metrics": [
                        "search_console.period_0.count_impressions",
                        "search_console.period_0.count_clicks"
                    ],
                    "filters": {
                        "field": f"crawl.{analysis}.depth",
                        "predicate": "lte",
                        "value": 2
                    }
                }
            }
        }
    }

    print("\nStarting export job...")
    response = httpx.post(url, json=data_payload, headers=headers)
    job_data = response.json()
    job_url = f"https://api.botify.com{job_data['job_url']}"
    print(f"Job created successfully (ID: {job_data['job_id']})")
    
    print("\nPolling for job completion: ", end="", flush=True)
    while True:
        time.sleep(5)  # Poll every 5 seconds
        status = httpx.get(job_url, headers=headers).json()
        print(f"\nCurrent status: {status['job_status']}")
        
        if status['job_status'] in ['COMPLETE', 'DONE']:
            download_url = status['results']['download_url']
            print(f"\nDownload URL: {download_url}")
            
            # Download and process the file
            gz_filename = "export.csv.gz"
            csv_filename = "export.csv"
            
            # Download gzipped file
            response = httpx.get(download_url)
            with open(gz_filename, "wb") as gz_file:
                gz_file.write(response.content)
            print(f"File downloaded as '{gz_filename}'")
            
            # Decompress and read into DataFrame
            with gzip.open(gz_filename, "rb") as f_in:
                with open(csv_filename, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            print(f"File decompressed as '{csv_filename}'")
            
            # Read CSV into DataFrame
            df = pd.read_csv(csv_filename, names=[
                'url', 'depth', 'pagetype', 'compliant', 'reason', 
                'canonical', 'sitemap', 'js_exec', 'js_ok',
                'impressions', 'clicks'
            ])
            
            # Cleanup temporary files
            os.remove(gz_filename)
            os.remove(csv_filename)
            
            return df
            
        elif status['job_status'] == 'FAILED':
            print(f"\nJob failed. Error details: {status}")
            raise Exception("Export job failed")
            
        elif status['job_status'] in ['CREATED', 'PROCESSING']:
            print(".", end="", flush=True)
            continue
            
        else:
            print(f"\nUnexpected status: {status}")
            raise Exception(f"Unexpected job status: {status['job_status']}")

def fetch_fields(org: str, project: str, collection: str) -> List[str]:
    """
    Fetch available fields for a given collection from the Botify API.
    
    Args:
        org: Organization slug
        project: Project slug  
        collection: Collection name (e.g. 'crawl.20241108')
        
    Returns:
        List of field IDs available in the collection
    """
    fields_url = f"https://api.botify.com/v1/projects/{org}/{project}/collections/{collection}"
    
    try:
        response = httpx.get(fields_url, headers=headers)
        response.raise_for_status()
        fields_data = response.json()
        return [
            field['id'] 
            for dataset in fields_data.get('datasets', [])
            for field in dataset.get('fields', [])
        ]
    except httpx.RequestError as e:
        print(f"Error fetching fields for collection '{collection}': {e}")
        return []

def check_compliance_fields(org, project, analysis):
    """Check available compliance fields in a more structured way."""
    collection = f"crawl.{analysis}"
    url = f"https://api.botify.com/v1/projects/{org}/{project}/query"
    
    # Group compliance fields by category
    compliance_categories = {
        'Basic Compliance': [
            'compliant.is_compliant',
            'compliant.main_reason',
            'compliant.reason.http_code',
            'compliant.reason.content_type',
            'compliant.reason.canonical',
            'compliant.reason.noindex',
            'compliant.detailed_reason'
        ],
        'Performance': [
            'scoring.issues.slow_first_to_last_byte_compliant',
            'scoring.issues.slow_render_time_compliant',
            'scoring.issues.slow_server_time_compliant',
            'scoring.issues.slow_load_time_compliant'
        ],
        'SEO': [
            'scoring.issues.duplicate_query_kvs_compliant'
        ],
        'Outlinks': [
            'outlinks_errors.non_compliant.nb.follow.unique',
            'outlinks_errors.non_compliant.nb.follow.total',
            'outlinks_errors.non_compliant.urls'
        ]
    }
    
    print("\n🔍 Field Availability Analysis")
    print("=" * 50)
    available_count = 0
    total_count = sum(len(fields) for fields in compliance_categories.values())
    
    available_fields = []
    for category, fields in compliance_categories.items():
        available_in_category = 0
        print(f"\n📑 {category}")
        print("-" * 30)
        for field in fields:
            full_field = f"{collection}.{field}"
            # Test field availability with a minimal query
            test_query = {
                "collections": [collection],
                "query": {
                    "dimensions": [full_field],
                    "filters": {"field": f"{collection}.depth", "predicate": "eq", "value": 0}
                }
            }
            
            try:
                response = httpx.post(url, headers=headers, json=test_query)
                if response.status_code == 200:
                    available_in_category += 1
                    available_count += 1
                    print(f"✓ {field.split('.')[-1]}")
                    available_fields.append(field)
                else:
                    print(f"× {field.split('.')[-1]}")
            except Exception as e:
                print(f"? {field.split('.')[-1]} (error checking)")
    
    coverage = (available_count / total_count) * 100
    print(f"\n📊 Field Coverage: {coverage:.1f}%")
    return available_fields

def download_and_process_csv(download_url, output_filename):
    """Download and decompress CSV from Botify API."""
    gz_filename = f"{output_filename}.gz"
    
    # Download gzipped file
    response = httpx.get(download_url)
    with open(gz_filename, "wb") as gz_file:
        gz_file.write(response.content)
    print(f"Downloaded: {gz_filename}")
    
    # Decompress to CSV
    with gzip.open(gz_filename, "rb") as f_in:
        with open(output_filename, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    print(f"Decompressed to: {output_filename}")
    
    # Cleanup
    os.remove(gz_filename)
    return True

def main():
    """Main execution logic"""
    try:
        with open('config.json') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("Error: config.json file not found")
        return
    except json.JSONDecodeError:
        print("Error: config.json is not valid JSON")
        return
    
    org = config.get('org')
    project = config.get('project')
    analysis = config.get('analysis')
    
    if not all([org, project, analysis]):
        print("Error: Missing required fields in config.json (org, project, analysis)")
        return
    
    print("Previewing data availability...")
    if preview_data(org, project, analysis, depth=2):
        print("Data preview successful. Proceeding with full export...")
        print("Fetching BQLv2 data...")
        df = get_bqlv2_data(org, project, analysis)
        print("\nData Preview:")
        print(df.head())

        # Save to CSV
        Path("downloads").mkdir(parents=True, exist_ok=True)
        output_file = f"downloads/{org}_{project}_{analysis}_metadata.csv"
        df.to_csv(output_file, index=False)
        print(f"\nData saved to {output_file}")
        
        # Use check_compliance_fields
        check_compliance_fields(org, project, analysis)
    else:
        print("Data preview failed. Please check configuration and try again.")

if __name__ == "__main__":
    main()
```

**Sample Output**:

    Previewing data availability...
    
    🔍 Sampling data for example/retail-division/20241108
    ==================================================
    
    📊 Data Sample Analysis
------------------------
    • URL: https://www.example.com/...
      └─ Performance: 123,456 impressions, 12,345 clicks
    • URL: https://www.example.com/site/retail/seasonal-sale/pcmcat...
      └─ Performance: 98,765 impressions, 8,765 clicks
    • URL: https://www.example.com/site/misc/daily-deals/pcmcat2480...
      └─ Performance: 54,321 impressions, 4,321 clicks
    
    🎯 Data Quality Check
------------------------
    ✓ URLs found: 404
    ✓ Search metrics: Available
    ✓ Depth limit: 2
    Data preview successful. Proceeding with full export...
    Fetching BQLv2 data...
    
    Starting export job...
    Job created successfully (ID: 12345)
    
    Polling for job completion: 
    Current status: CREATED
    .
    Current status: PROCESSING
    .
    Current status: DONE
    
    Download URL: https://example.cloudfront.net/exports/a/b/c/abc123def456/example-2024-11-10.csv.gz
    File downloaded as 'export.csv.gz'
    File decompressed as 'export.csv'
    
    Data Preview:
                                                                                                                            url  \
    0  https://www.example.com/realm/shops/merchants-quarter/enchanted-items/
    1  https://www.example.com/realm/elven-moonlight-potion-azure/
    2  https://www.example.com/realm/dwarven-decorative-runes-sapphire/   
    3  https://www.example.com/realm/legendary-artifacts/master-crafted-items/   
    4  ttps://www.example.com/realm/orcish-war-drums-obsidian/  
    
       depth             pagetype  compliant     reason canonical  sitemap  \
    0      2             category       True  Indexable      True    False   
    1      2                  pdp       True  Indexable      True     True   
    2      2                  plp       True  Indexable      True     True   
    3      2               review       True  Indexable      True    False   
    4      2                 main       True  Indexable      True     True   
    
       js_exec  js_ok  impressions  clicks  
    0     True  False       12345     123   
    1     True  False        9876      98   
    2     True  False        5432      54   
    3     True  False        1111      11   
    4     True  False         987       9   
    
    Data saved to downloads/example_retail-division_20241108_metadata.csv

**Rationale**: BQL and enterprise SEO diagnostics provide powerful tools for comprehensive website analysis. This code transforms link structures into detailed visualizations of your site's SEO health, presenting search signals and performance metrics in a multi-dimensional view. Similar to how diagnostic imaging reveals underlying conditions, these analyses expose strengths, vulnerabilities, and technical issues within your site architecture. Prepare your site for the increasing number of AI crawlers by optimizing your content and structure. Ensure your schema.org structured data is properly implemented to support real-time crawls that evaluate product availability and other critical information.
 
Next-generation SEO requires adapting to these AI-driven changes. Now, let's examine the process of converting from BQLv1 to the collection-based BQLv2 format...

--------------------------------------------------------------------------------

# Web Logs: How To Check If A Project Has a Web Logs Collection


```python
import httpx
import json
import os
# No typing imports needed

# --- Configuration ---
CONFIG_FILE = "config.json"
TOKEN_FILE = "botify_token.txt"
# The specific collection ID we are looking for
TARGET_LOG_COLLECTION_ID = "logs"

# --- !!! EASY OVERRIDE SECTION !!! ---
# Set these variables to directly specify org/project, bypassing config.json
# Leave as None to use config.json or prompts.
# https://app.botify.com/michaellevin-org/mikelev.in
# ORG_OVERRIDE = None
# PROJECT_OVERRIDE = None
ORG_OVERRIDE = "michaellevin-org"
PROJECT_OVERRIDE = "mikelev.in"
# Example:
# ORG_OVERRIDE = "my-direct-org"
# PROJECT_OVERRIDE = "my-direct-project.com"
# --- END OVERRIDE SECTION ---


# --- Helper Functions ---

def load_api_key():
    """Loads the API key from the token file. Returns None on error."""
    try:
        if not os.path.exists(TOKEN_FILE):
            print(f"Error: Token file '{TOKEN_FILE}' not found.")
            return None
        with open(TOKEN_FILE) as f:
            api_key = f.read().strip().split('\n')[0].strip()
            if not api_key:
                print(f"Error: Token file '{TOKEN_FILE}' is empty.")
                return None
        return api_key
    except Exception as e:
        print(f"Error loading API key: {e}")
        return None

def load_org_project_from_config():
    """Loads org and project from config file. Returns (None, None) on error or if missing."""
    org_config = None
    project_config = None
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                config_data = json.load(f)
                org_config = config_data.get('org')
                project_config = config_data.get('project')
        # No error if file doesn't exist, just return None
    except json.JSONDecodeError:
        print(f"Warning: '{CONFIG_FILE}' contains invalid JSON.")
    except Exception as e:
        print(f"Warning: Could not load org/project from {CONFIG_FILE}: {e}")
    return org_config, project_config

def get_api_headers(api_key):
    """Returns standard API headers."""
    return {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json"
    }

def check_if_log_collection_exists(org_slug, project_slug, api_key):
    """
    Checks if a collection with ID 'logs' exists for the given org and project.
    Returns True if found, False otherwise or on error.
    """
    if not org_slug or not project_slug or not api_key:
        print("Error: Org slug, project slug, and API key are required for check.")
        return False

    collections_url = f"https://api.botify.com/v1/projects/{org_slug}/{project_slug}/collections"
    headers = get_api_headers(api_key)

    print(f"\nChecking for collection '{TARGET_LOG_COLLECTION_ID}' in {org_slug}/{project_slug}...")

    try:
        response = httpx.get(collections_url, headers=headers, timeout=60.0)

        if response.status_code == 401:
            print("Error: Authentication failed (401). Check your API token.")
            return False
        elif response.status_code == 403:
             print("Error: Forbidden (403). You may not have access to this project or endpoint.")
             return False
        elif response.status_code == 404:
             print("Error: Project not found (404). Check org/project slugs.")
             return False

        response.raise_for_status() # Raise errors for other bad statuses (like 5xx)
        collections_data = response.json()

        if not isinstance(collections_data, list):
             print(f"Error: Unexpected API response format. Expected a list.")
             return False

        for collection in collections_data:
            if isinstance(collection, dict) and collection.get('id') == TARGET_LOG_COLLECTION_ID:
                print(f"Success: Found collection with ID '{TARGET_LOG_COLLECTION_ID}'.")
                return True

        print(f"Result: Collection with ID '{TARGET_LOG_COLLECTION_ID}' was not found in the list.")
        return False

    except httpx.HTTPStatusError as e:
         print(f"API Error checking collections: {e.response.status_code}")
         return False
    except httpx.RequestError as e:
        print(f"Network error checking collections: {e}")
        return False
    except json.JSONDecodeError:
        print("Error: Could not decode the API response as JSON.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during check: {e}")
        return False

# --- Main Function ---

def run_check(org_override=None, project_override=None):
    """
    Orchestrates the check for the 'logs' collection.
    Uses override values if provided, otherwise falls back to config file, then prompts.
    """
    print("Starting Botify Log Collection Check...")

    # 1. Load API Key (Essential)
    api_key = load_api_key()
    if not api_key:
        print("Cannot proceed without a valid API key.")
        return # Exit the function

    # 2. Determine Org and Project to use
    org_config, project_config = load_org_project_from_config()

    # Apply overrides if they exist
    org_to_use = org_override if org_override is not None else org_config
    project_to_use = project_override if project_override is not None else project_config

    # If still missing after config and overrides, prompt the user
    if not org_to_use:
        print(f"Organization slug not found in config or override.")
        org_to_use = input("Enter the organization slug: ").strip()

    if not project_to_use:
        print(f"Project slug not found in config or override.")
        project_to_use = input("Enter the project slug: ").strip()

    # Final check before running API call
    if not org_to_use or not project_to_use:
        print("Organization and Project slugs are required to run the check. Exiting.")
        return

    # 3. Run the core check function
    has_logs = check_if_log_collection_exists(org_to_use, project_to_use, api_key)

    # 4. Report Final Result
    print("\n--- Check Complete ---")
    if has_logs:
        print(f"The project '{org_to_use}/{project_to_use}' appears to HAVE a '{TARGET_LOG_COLLECTION_ID}' collection available.")
    else:
        print(f"The project '{org_to_use}/{project_to_use}' does NOT appear to have a '{TARGET_LOG_COLLECTION_ID}' collection available (or an error occurred).")


# --- Script Execution ---
if __name__ == "__main__":
    # Call the main function, passing the override values defined at the top
    run_check(org_override=ORG_OVERRIDE, project_override=PROJECT_OVERRIDE)
```

**Sample Output**:

    Starting Botify Log Collection Check...
    
    Checking for collection 'logs' in example-org/example.com...
    Success: Found collection with ID 'logs'.
The project 'example-org/example.com' appears to HAVE a 'logs' collection available.

Alternatively:

    Starting Botify Log Collection Check...
    
    Checking for collection 'logs' in example-org/example.com...
    Result: Collection with ID 'logs' was not found in the list.
The project 'example-org/example.com' does NOT appear to have a 'logs' collection available (or an error occurred).

--------------------------------------------------------------------------------

# Migrating from BQLv1 to BQLv2

This guide explains how to convert BQLv1 queries to BQLv2 format, with practical examples and validation helpers.

## Core Concepts

### API Endpoint Changes

- **BQLv1**: `/v1/analyses/{username}/{website}/{analysis}/urls`
- **BQLv2**: `/v1/projects/{username}/{website}/query`

### Key Structural Changes

1. Collections replace URL parameters
2. Fields become dimensions
3. All fields require collection prefixes
4. Areas are replaced with explicit filters

## Query Conversion Examples

### 1. Basic URL Query

```json
// BQLv1 (/v1/analyses/user/site/20210801/urls?area=current&previous_crawl=20210715)
{
  "fields": [
    "url",
    "http_code",
    "previous.http_code"
  ],
  "filters": {
    "field": "indexable.is_indexable",
    "predicate": "eq",
    "value": true
  }
}

// BQLv2 (/v1/projects/user/site/query)
{
  "collections": [
    "crawl.20210801",
    "crawl.20210715"
  ],
  "query": {
    "dimensions": [
      "crawl.20210801.url",
      "crawl.20210801.http_code",
      "crawl.20210715.http_code"
    ],
    "metrics": [],
    "filters": {
      "field": "crawl.20210801.indexable.is_indexable",
      "predicate": "eq",
      "value": true
    }
  }
}
```

### 2. Aggregation Query

```json
// BQLv1 (/v1/analyses/user/site/20210801/urls/aggs)
[
  {
    "aggs": [
      {
        "metrics": ["count"],
        "group_by": [
          {
            "distinct": {
              "field": "segments.pagetype.depth_1",
              "order": {"value": "asc"},
              "size": 300
            }
          }
        ]
      }
    ]
  }
]

// BQLv2
{
  "collections": ["crawl.20210801"],
  "query": {
    "dimensions": [
      "crawl.20210801.segments.pagetype.depth_1"
    ],
    "metrics": [
      "crawl.20210801.count_urls_crawl"
    ],
    "sort": [0]
  }
}
```

### 3. Area Filters

BQLv1's area parameter is replaced with explicit filters in BQLv2:

#### New URLs Filter
```json
{
  "and": [
    {
      "field": "crawl.20210801.url_exists_crawl",
      "value": true
    },
    {
      "field": "crawl.20210715.url_exists_crawl",
      "value": false
    }
  ]
}
```

#### Disappeared URLs Filter
```json
{
  "and": [
    {
      "field": "crawl.20210801.url_exists_crawl",
      "value": false
    },
    {
      "field": "crawl.20210715.url_exists_crawl",
      "value": true
    }
  ]
}
```

## Conversion Helper Functions

```python
def validate_bql_v2(query):
    """Validate BQLv2 query structure"""
    required_keys = {'collections', 'query'}
    query_keys = {'dimensions', 'metrics', 'filters'}
    
    if not all(key in query for key in required_keys):
        raise ValueError(f"Missing required keys: {required_keys}")
    if not any(key in query['query'] for key in query_keys):
        raise ValueError(f"Query must contain one of: {query_keys}")
    for collection in query['collections']:
        if not collection.startswith('crawl.'):
            raise ValueError(f"Invalid collection format: {collection}")
    return True

def convert_url_query(query_v1, current_analysis, previous_analysis=None):
    """Convert BQLv1 URL query to BQLv2"""
    collections = [f"crawl.{current_analysis}"]
    if previous_analysis:
        collections.append(f"crawl.{previous_analysis}")
    
    # Convert fields to dimensions
    dimensions = []
    for field in query_v1.get('fields', []):
        if field.startswith('previous.'):
            if not previous_analysis:
                raise ValueError("Previous analysis required for previous fields")
            field = field.replace('previous.', '')
            dimensions.append(f"crawl.{previous_analysis}.{field}")
        else:
            dimensions.append(f"crawl.{current_analysis}.{field}")
    
    # Convert filters
    filters = None
    if 'filters' in query_v1:
        filters = {
            "field": f"crawl.{current_analysis}.{query_v1['filters']['field']}",
            "predicate": query_v1['filters']['predicate'],
            "value": query_v1['filters']['value']
        }
    
    query_v2 = {
        "collections": collections,
        "query": {
            "dimensions": dimensions,
            "metrics": [],
            "filters": filters
        }
    }
    
    validate_bql_v2(query_v2)
    return query_v2
```

## Key Conversion Rules

1. **Collections**
   - Add `collections` array with `crawl.{analysis}` format
   - Include both analyses for comparison queries

2. **Fields to Dimensions**
   - Prefix fields with `crawl.{analysis}.`
   - Replace `previous.` prefix with `crawl.{previous_analysis}.`

3. **Metrics**
   - Convert aggregation metrics to appropriate BQLv2 metric fields
   - Use empty array when no metrics needed

4. **Filters**
   - Prefix filter fields with collection name
   - Replace area parameters with explicit URL existence filters

--------------------------------------------------------------------------------

# Size Up Botify Open API Swagger


```python
# Python Script to Download Botify OpenAPI Spec, Save Locally, and Calculate Token Count
# ------------------------------------------------------------------------------------
# Purpose:
# This script fetches the OpenAPI (Swagger) specification for the Botify API,
# saves it to a local file ('botify_openapi_spec.json'), and then calculates
# and displays the number of tokens it represents using the 'tiktoken' library.
# This helps in estimating if the content fits LLM context windows and provides
# the file for further use.

import httpx  # For making HTTP requests
import json   # For potential JSON validation (optional here)
import tiktoken # For tokenizing text
import os     # For path operations

# --- Configuration ---
SWAGGER_URL = "https://api.botify.com/v1/swagger.json"
LOCAL_SWAGGER_FILENAME = "botify_openapi_spec.json"  # Filename for saving the spec
# Using "cl100k_base" encoding, common for gpt-4, gpt-3.5-turbo, etc.
TIKTOKEN_ENCODING_NAME = "cl100k_base"

def fetch_swagger_save_and_count_tokens():
    """
    Fetches the Botify API Swagger JSON, saves it locally, prints its size,
    and calculates the number of tokens it contains.
    """
    print(f"INFO: Attempting to download Botify OpenAPI specification from: {SWAGGER_URL}")

    try:
        # Step 1: Fetch the Swagger JSON content
        with httpx.Client(timeout=30.0) as client:
            response = client.get(SWAGGER_URL)
            response.raise_for_status()  # Raise an exception for HTTP errors

        swagger_content_str = response.text
        content_bytes = response.content
        
        print(f"SUCCESS: Downloaded OpenAPI specification.")
        print(f"         Size: {len(content_bytes):,} bytes")

        # Step 1.5: Save the downloaded content to a local file
        # Rationale: To provide the user with the actual file for copy-pasting
        #            or other direct uses.
        try:
            # Determine script's directory to save the file next to it
            script_dir = os.path.dirname(os.path.abspath(__file__))
            local_file_path = os.path.join(script_dir, LOCAL_SWAGGER_FILENAME)
        except NameError: 
            # __file__ is not defined (e.g., if running in a Jupyter cell directly pasted, not as a .py file)
            # Save in the current working directory instead.
            local_file_path = LOCAL_SWAGGER_FILENAME

        with open(local_file_path, 'w', encoding='utf-8') as f:
            f.write(swagger_content_str)
        print(f"SUCCESS: OpenAPI specification saved locally as: '{os.path.abspath(local_file_path)}'")

        # Optional: Verify if it's valid JSON
        # try:
        #     json.loads(swagger_content_str)
        #     print("         Content is valid JSON.")
        # except json.JSONDecodeError:
        #     print("WARNING: Content may not be valid JSON, but token counting will proceed on raw text.")

        # Step 2: Initialize the tiktoken encoder
        try:
            encoding = tiktoken.get_encoding(TIKTOKEN_ENCODING_NAME)
            print(f"INFO: Using tiktoken encoding: '{TIKTOKEN_ENCODING_NAME}'")
        except Exception as e:
            print(f"ERROR: Could not load tiktoken encoding '{TIKTOKEN_ENCODING_NAME}': {e}")
            print("       Please ensure 'tiktoken' is installed correctly.")
            return

        # Step 3: Encode the content and count the tokens
        tokens = encoding.encode(swagger_content_str)
        token_count = len(tokens)

        print(f"\n--- Tokenization Complete ---")
        print(f"Number of tokens (using '{TIKTOKEN_ENCODING_NAME}'): {token_count:,}")
        
        if token_count < 100000:
            print("INFO: Token count is comfortably within a typical 128k context window.")
        elif token_count <= 130000:
            print("INFO: Token count is within the ~100K-130K range mentioned. It should fit, but it's substantial.")
        else:
            print("WARNING: Token count exceeds 130K. It might be too large for a single POST submission depending on the exact model limit.")
            
    except httpx.HTTPStatusError as e:
        print(f"ERROR: HTTP error occurred while fetching Swagger spec: {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        print(f"ERROR: Network request error occurred: {e}")
    except IOError as e:
        print(f"ERROR: Could not save the Swagger specification to file: {e}")
    except Exception as e:
        print(f"ERROR: An unexpected error occurred: {e}")

# --- Script Execution ---
if __name__ == "__main__":
    fetch_swagger_save_and_count_tokens()
```

--------------------------------------------------------------------------------

# All Botify API Endpoints: How Do You Generate a Python Code Example for Every Botify Endpoint Given Their OpenAPI Swagger

Botify OpenAPI Swagger File: [https://api.botify.com/v1/swagger.json](https://api.botify.com/v1/swagger.json)


```python
# Python Script to Generate Paginated LLM Training Data for Botify API
# ------------------------------------------------------------------------------------
# Purpose:
# This script fetches the Botify OpenAPI spec and generates a comprehensive, paginated
# markdown document suitable for both LLM training and a custom web front-end.
# The final file is saved to a configurable output path.

import httpx
import json
import tiktoken
import os
import traceback
from pathlib import Path
from typing import Dict, Any, List

# --- Configuration ---
SWAGGER_URL = "https://api.botify.com/v1/swagger.json"
TIKTOKEN_ENCODING_NAME = "cl100k_base"

# --- Output Configuration ---
# Set this to a specific directory path (e.g., "../../training", "/path/to/output").
# If set to None or an empty string, it will save to a default 'training' folder
# in the current working directory.
OPTIONAL_HARWIRED_OUTPUT_PATH = "../../helpers/botify"

# Filename for the output, specifically named for the documentation plugin.
OUTPUT_FILENAME = "botify_api_examples.md"

# The separator used to paginate the document in the web application.
PAGINATION_SEPARATOR = "-" * 80

# --- Global Variable for Notebook Persistence ---
llm_training_markdown = ""

def generate_python_code_example(method: str, path: str, endpoint_details: Dict[str, Any]) -> str:
    """Generates a practical, professional Python code example for a given API endpoint."""
    lines = [
        "```python",
        f"# Example: {method.upper()} {endpoint_details.get('summary', path)}",
        "import httpx",
        "import json",
        "",
        "# Assumes your Botify API token is in a file named 'botify_token.txt'",
        "try:",
        "    with open('botify_token.txt') as f:",
        r"        token = f.read().split('\n')[0].strip()",
        "except FileNotFoundError:",
        "    print(\"Error: 'botify_token.txt' not found. Please create it.\")",
        "    token = 'YOUR_API_TOKEN'  # Fallback",
        ""
    ]
    
    formatted_path = path
    all_params = endpoint_details.get('parameters', [])
    path_params = [p for p in all_params if p.get('in') == 'path']
    
    path_params_from_url = [p_name.strip('{}') for p_name in path.split('/') if p_name.startswith('{')]
    declared_param_names = {p['name'] for p in path_params}

    for p_name in path_params_from_url:
        if p_name not in declared_param_names:
            path_params.append({'name': p_name})

    if path_params:
        lines.append("# --- Define Path Parameters ---")
        for p in path_params:
            param_name = p['name']
            placeholder_value = f"YOUR_{param_name.upper()}"
            lines.append(f"{param_name} = \"{placeholder_value}\"")
            formatted_path = formatted_path.replace(f"{{{param_name}}}", f"{{{param_name}}}")
        lines.append("")

    lines.append("# --- Construct the Request ---")
    lines.append(f"url = f\"[https://api.botify.com/v1](https://api.botify.com/v1){formatted_path}\"")
    lines.append("headers = {")
    lines.append("    'Authorization': f'Token {token}',")
    lines.append("    'Content-Type': 'application/json'")
    lines.append("}")
    lines.append("")

    query_params = [p for p in all_params if p.get('in') == 'query']
    if query_params:
        lines.append("# Define query parameters")
        lines.append("query_params = {")
        for p in query_params:
            sample_value = "'example_value'" if p.get('type', 'string') == 'string' else '123'
            lines.append(f"    '{p.get('name')}': {sample_value},  # Type: {p.get('type', 'N/A')}, Required: {p.get('required', False)}")
        lines.append("}")

    body_param = next((p for p in all_params if p.get('in') == 'body'), None)
    if body_param:
        lines.append("# Define the JSON payload for the request body")
        lines.append("json_payload = {")
        lines.append("    'key': 'value'  # Replace with actual data")
        lines.append("}")

    lines.append("\n# --- Send the Request ---")
    lines.append("try:")
    lines.append("    with httpx.Client(timeout=30.0) as client:")
    request_args = ["url", "headers=headers"]
    if query_params:
        request_args.append("params=query_params")
    if body_param:
        request_args.append("json=json_payload")
    lines.append(f"        response = client.{method.lower()}({', '.join(request_args)})")
    lines.append("        response.raise_for_status()")
    lines.append("        print('Success! Response:')")
    lines.append("        print(json.dumps(response.json(), indent=2))")
    lines.append("except httpx.HTTPStatusError as e:")
    lines.append("    print(f'HTTP Error: {e.response.status_code} - {e.response.text}')")
    lines.append("except httpx.RequestError as e:")
    lines.append(f"    print(f'Request error: {{e}}')")
    lines.append("except Exception as e:")
    lines.append(f"    print(f'An unexpected error occurred: {{e}}')")
    lines.append("```")
    return "\n".join(lines)

def generate_api_documentation_markdown(spec: Dict[str, Any]) -> str:
    """Generates a complete markdown document from the OpenAPI specification."""
    all_endpoint_docs_as_blocks = []
    all_endpoints = []

    for path, methods in spec.get('paths', {}).items():
        for method, details in methods.items():
            if method.lower() not in ['get', 'post', 'put', 'delete', 'patch']:
                continue
            all_endpoints.append({'method': method, 'path': path, 'details': details})

    for endpoint in all_endpoints:
        try:
            method, path, details = endpoint['method'], endpoint['path'], endpoint['details']
            endpoint_block = []
            tag = details.get('tags', ['Uncategorized'])[0]
            summary = details.get('summary', 'No summary provided.')
            description = details.get('description', 'No detailed description available.')
            parameters = details.get('parameters', [])

            endpoint_block.extend([
                f"#### `{method.upper()} {path}`", "",
                f"**Category:** `{tag}`", "",
                f"**Summary:** {summary}", "",
                "**Description:**", f"{description}", ""
            ])

            if parameters:
                endpoint_block.append("**Parameters:**")
                endpoint_block.append("| Name | Location (in) | Required | Type | Description |")
                endpoint_block.append("|---|---|---|---|---|")
                for p in parameters:
                    param_name = p.get('name', 'N/A')
                    param_in = p.get('in', 'N/A')
                    param_req = p.get('required', False)
                    param_type = p.get('type', 'N/A')
                    param_desc = p.get('description', '').replace('|', ' ')
                    endpoint_block.append(f"| `{param_name}` | {param_in} | {param_req} | `{param_type}` | {param_desc} |")
                endpoint_block.append("")

            endpoint_block.append("**Python Example:**")
            endpoint_block.append(generate_python_code_example(method, path, details))
            
            all_endpoint_docs_as_blocks.append("\n".join(endpoint_block))
        
        except Exception:
            print(f"---")
            print(f"WARNING: Could not process endpoint: {endpoint.get('method', 'N/A').upper()} {endpoint.get('path', 'N/A')}")
            print(f"  ERROR DETAILS BELOW:")
            traceback.print_exc()
            print(f"---")
            continue

    paginated_content = f"\n\n{PAGINATION_SEPARATOR}\n\n".join(all_endpoint_docs_as_blocks)
    main_header = [
        "# Botify Open API Swagger Examples", "",
        "This document provides detailed information and Python code examples for every endpoint in the Botify API...", ""
    ]
    return "\n".join(main_header) + paginated_content

def create_llm_training_document():
    """Main orchestrator function."""
    global llm_training_markdown
    print(f"INFO: Attempting to download Botify OpenAPI specification from: {SWAGGER_URL}")
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(SWAGGER_URL)
            response.raise_for_status()
            spec = response.json()
        print("SUCCESS: Downloaded OpenAPI specification.")

        print("INFO: Generating API documentation with pagination separators...")
        generated_markdown = generate_api_documentation_markdown(spec)
        print("SUCCESS: API documentation generated.")

        print(f"INFO: Calculating token count using '{TIKTOKEN_ENCODING_NAME}'...")
        encoding = tiktoken.get_encoding(TIKTOKEN_ENCODING_NAME)
        tokens = encoding.encode(generated_markdown)
        token_count = len(tokens)
        print(f"SUCCESS: Tokenization complete.")

        token_line = f"**Total Estimated Token Count**: `{token_count:,}` (using `{TIKTOKEN_ENCODING_NAME}`)"
        llm_training_markdown = generated_markdown.replace("# Botify Open API Swagger Examples", f"# Botify Open API Swagger Examples\n\n{token_line}")

        print("\n--- Analysis Complete ---")
        print(token_line)
        if token_count < 200000:
            print("✅ INFO: The generated documentation should fit within a large context window.")
        else:
            print("⚠️ WARNING: Token count is very large and may exceed some context windows.")
        
        # --- Determine the final output path using the optional hardwired path ---
        if OPTIONAL_HARWIRED_OUTPUT_PATH and OPTIONAL_HARWIRED_OUTPUT_PATH.strip():
            final_output_dir = Path(OPTIONAL_HARWIRED_OUTPUT_PATH)
            print(f"INFO: Using optional hardwired output path: {final_output_dir.resolve()}")
        else:
            final_output_dir = Path("training") # Default to 'training' in CWD
            print(f"INFO: No hardwired path set. Using default directory: {final_output_dir.resolve()}")
        
        output_path = final_output_dir / OUTPUT_FILENAME

        print(f"INFO: Saving paginated documentation file to: '{output_path.resolve()}'")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(llm_training_markdown)
        print("SUCCESS: Documentation file saved.")

    except httpx.HTTPStatusError as e:
        error_message = f"ERROR: HTTP error during download: {e.response.status_code} - {e.response.text}"
        print(error_message)
        llm_training_markdown = f"# Error\n\n{error_message}"
    except Exception:
        print("ERROR: An unexpected critical error occurred during the process.")
        traceback.print_exc()
        llm_training_markdown = f"# Error\n\nAn unexpected critical error occurred. See console for traceback."

# --- Script Execution ---
if __name__ == "__main__":
    create_llm_training_document()
    if llm_training_markdown and not llm_training_markdown.startswith("# Error"):
        print(f"\nSUCCESS: Global variable 'llm_training_markdown' is now populated and file has been created.")
    else:
        print("\nERROR: Process did not complete successfully. Check warnings above.")

```

--------------------------------------------------------------------------------

# Create Documentation For Pipulate From This Notebook


```python
# Jupyter Notebook Self-Export and Custom Markdown Processing Script
# -------------------------------------------------------------------
# Purpose:
# This script, when run as a cell in a Jupyter Notebook, automates the conversion
# of the notebook itself into a clean, well-structured Markdown (.md) file.
# The process involves two main stages:
#
# 1. Self-Export to Raw Markdown:
#    - The script first identifies the current Jupyter Notebook file.
#    - It then uses 'jupyter nbconvert' to convert the notebook into a standard
#      Markdown file, saved in the same directory as the notebook.
#
# 2. Custom Post-Processing with Heading-Based Delineators:
#    - The script then applies a custom processing function to this Markdown file.
#    - This custom processing includes:
#      a. Removing any YAML frontmatter (text between '---' markers at the
#         very start of the document).
#      b. Inserting a wide visual delineator (80 hyphens with surrounding
#         blank lines) *before* every H1 Markdown heading (`# Heading`)
#         that is not inside a fenced code block. This leverages the semantic
#         structure of headings for separation.
#      c. Prepending a global header (currently configured to be blank).
#    - The processed content is then saved. If an optional hardwired output path
#      is specified, the final file goes there; otherwise, it overwrites the
#      initial Markdown file in the notebook's directory. This results in a
#      single .md file named after the original notebook, with clear section
#      delineations.
#
# Rationale:
# This workflow produces LLM-ready Markdown. The H1-triggered delineators
# enhance readability and provide strong parsing cues for segmenting content
# based on major sections (as typically denoted by H1s). This approach relies
# on the semantic use of H1 headings in the notebook's Markdown cells to create
# logical breaks, offering a more content-aware separation than generic
# between-cell markers.

# --- Configuration ---
# Set the output directory path.
OPTIONAL_HARWIRED_OUTPUT_PATH = "../../helpers/botify" # Example: "/mnt/c/Users/YourUser/Documents/NotebookExports"

# --- MODIFICATION START: Hardcoded Output Filename ---
# Set this to the desired output filename. If None or empty, it will default
# to using the notebook's name.
OUTPUT_FILENAME_MD = "botify_api_bootcamp.md"
# --- MODIFICATION END ---


# --- Part 1: Necessary Imports ---
# Purpose: Import required Python standard libraries for file operations,
#          running external commands, text processing, and date/time.
import os
import subprocess
import re
from pathlib import Path
import datetime

# --- Part 2: Custom Markdown Post-Processing Function ---
# Purpose: This function takes the Markdown content produced by 'nbconvert'
#          and applies cleaning (frontmatter removal) and custom separator insertion.

def process_markdown(input_path, output_path):
    """
    Processes a Markdown file generated from a Jupyter Notebook.
    It removes YAML frontmatter and inserts a wide horizontal rule delineator
    before each H1 heading (that is not within a code block).
    The input and output paths can be the same for in-place modification.

    Args:
        input_path (str or Path): Path to the input Markdown file.
        output_path (str or Path): Path where the processed Markdown will be saved.
    
    Returns:
        bool: True if processing is successful, False otherwise.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    input_p = Path(input_path)
    output_p = Path(output_path)

    print(f"INFO: Applying custom post-processing to: '{input_p.name}' (output will be '{output_p.resolve()}')")
    
    try:
        with open(input_p, 'r', encoding='utf-8') as infile:
            content = infile.read()
    except FileNotFoundError:
        print(f"ERROR: Input file for process_markdown not found: '{input_p}'")
        return False
    except Exception as e:
        print(f"ERROR: Could not read input file '{input_p}': {e}")
        return False
        
    # Step 2.1: Remove YAML frontmatter from the very beginning of the document.
    content_after_frontmatter_removal = re.sub(r'^\s*---.*?---\s*', '', content, flags=re.DOTALL | re.MULTILINE)
    
    # --- Step 2.2: Insert Wide Delineators Before H1 Headings ---
    # Rationale: This "slice-and-dicer" section iterates through the Markdown content
    #            line by line, identifying H1 headings (e.g., "# Heading") that are
    #            not part of a fenced code block. A prominent visual separator
    #            (80 hyphens) is inserted before such headings to clearly mark major
    #            sections, aiding both visual scanning and LLM parsing.

    lines = content_after_frontmatter_removal.splitlines()
    processed_lines = []
    in_code_block = False  # State variable to track if currently inside a fenced code block
    SEPARATOR = "-" * 80   # The wide delineator

    # Determine if the very first significant content line is an H1.
    # We might not want a separator before the absolute first H1 (e.g., the main document title).
    first_actual_content_line_index = -1
    for idx, line_text in enumerate(lines):
        if line_text.strip():
            first_actual_content_line_index = idx
            break
            
    for i, line in enumerate(lines):
        stripped_line = line.strip()

        # Toggle state if a fenced code block starts or ends
        if stripped_line.startswith("```"):
            in_code_block = not in_code_block
        
        is_h1_outside_code = not in_code_block and line.startswith("# ")

        if is_h1_outside_code:
            # Add separator if this H1 is NOT the very first significant line of content.
            # This prevents a separator at the very top if the document starts with an H1.
            if i > first_actual_content_line_index or \
               (i == first_actual_content_line_index and i > 0) or \
               (i == 0 and first_actual_content_line_index > 0 and lines[0].strip() == ""): # handles H1 after initial blank lines
                # Ensure a blank line before the separator if the previous content wasn't blank
                if processed_lines and processed_lines[-1].strip() != "":
                    processed_lines.append("")
                
                processed_lines.append(SEPARATOR)
                processed_lines.append("") # Blank line after separator, before the H1 heading
        
        processed_lines.append(line) # Add the current line (H1 or otherwise)

    content_with_separators = "\n".join(processed_lines)
    
    # Step 2.3: Prepare the global header for the final document.
    header_comment = "" # Currently blank, as per your last preference.
    final_content = header_comment + content_with_separators
    
    try:
        # Step 2.4: Write the processed content back to the Markdown file.
        output_p.parent.mkdir(parents=True, exist_ok=True) # Ensure output directory exists
        with open(output_p, 'w', encoding='utf-8') as outfile:
            outfile.write(final_content)
        print(f"SUCCESS: Custom post-processing complete. Output: '{output_p.resolve()}'")
        return True 
    except Exception as e:
        print(f"ERROR: Could not write final processed file '{output_p}': {e}")
        return False

# --- Part 3: Orchestration Logic for Self-Export and Processing ---
def export_notebook_and_apply_custom_processing():
    """
    Orchestrates the notebook self-export and custom Markdown processing.
    """
    current_notebook_filename_ipynb = None
    current_notebook_dir = os.getcwd() 

    # --- Step A: Determine the current notebook's filename and directory ---
    env_notebook_path_str = os.environ.get('JPY_SESSION_NAME')
    if env_notebook_path_str and env_notebook_path_str.endswith(".ipynb"):
        path_obj = Path(env_notebook_path_str)
        if path_obj.is_absolute():
            current_notebook_filename_ipynb = path_obj.name
            current_notebook_dir = str(path_obj.parent)
        else: 
            potential_path = Path(os.getcwd()) / env_notebook_path_str
            if potential_path.exists() and potential_path.is_file():
                current_notebook_filename_ipynb = potential_path.name
                current_notebook_dir = str(potential_path.parent)
            else: 
                current_notebook_filename_ipynb = path_obj.name # Assume it's relative to cwd if not found absolute
        if current_notebook_filename_ipynb:
            print(f"INFO: Notebook identified as '{current_notebook_filename_ipynb}' in '{current_notebook_dir}' (via JPY_SESSION_NAME).")

    if not current_notebook_filename_ipynb:
        try:
            import ipynbname 
            notebook_path_obj = ipynbname.path()
            current_notebook_filename_ipynb = notebook_path_obj.name
            current_notebook_dir = str(notebook_path_obj.parent)
            print(f"INFO: Notebook identified as '{current_notebook_filename_ipynb}' in '{current_notebook_dir}' (via 'ipynbname').")
        except ImportError:
            print("WARNING: 'ipynbname' package not found. For robust name detection, consider `pip install ipynbname`.")
        except Exception as e: 
            print(f"WARNING: 'ipynbname' could not determine notebook path (is notebook saved and trusted?): {e}")
            
    if not current_notebook_filename_ipynb:
        print("CRITICAL ERROR: Could not determine the current notebook's .ipynb filename.")
        return

    # This is the default filename nbconvert will use, based on the notebook's name.
    markdown_basename_from_notebook = Path(current_notebook_filename_ipynb).stem + ".md"
    
    # This is where nbconvert will initially place its output
    nbconvert_output_path_in_notebook_dir = Path(current_notebook_dir) / markdown_basename_from_notebook

    # Determine the final path for the processed Markdown file
    final_save_directory_path = Path(current_notebook_dir) # Default
    if OPTIONAL_HARWIRED_OUTPUT_PATH and OPTIONAL_HARWIRED_OUTPUT_PATH.strip():
        prospective_hardwired_path = Path(OPTIONAL_HARWIRED_OUTPUT_PATH)
        try:
            prospective_hardwired_path.mkdir(parents=True, exist_ok=True)
            final_save_directory_path = prospective_hardwired_path
            print(f"INFO: Using hardwired output directory: '{final_save_directory_path.resolve()}'")
        except Exception as e:
            print(f"ERROR: Could not create or access hardwired output directory '{prospective_hardwired_path}': {e}.")
            print(f"         Defaulting to notebook's directory for final output: '{Path(current_notebook_dir).resolve()}'")
            # final_save_directory_path remains current_notebook_dir
    else:
        print(f"INFO: Output directory not hardwired. Using notebook's directory for final output: '{final_save_directory_path.resolve()}'")

    # --- MODIFICATION START: Determine the final filename ---
    # Use the hardcoded OUTPUT_FILENAME_MD if it's set, otherwise fall back to the notebook-derived name.
    final_markdown_filename = OUTPUT_FILENAME_MD if (OUTPUT_FILENAME_MD and OUTPUT_FILENAME_MD.strip()) else markdown_basename_from_notebook
    print(f"INFO: Final output filename has been set to: '{final_markdown_filename}'")
    
    # Construct the full path for the final processed Markdown file.
    final_processed_markdown_path = final_save_directory_path / final_markdown_filename
    # --- MODIFICATION END ---


    # --- Step B: Convert the current notebook to standard Markdown ---
    # nbconvert will output <notebook_name>.md into current_notebook_dir (its CWD)
    nbconvert_command = [
        "jupyter", "nbconvert",
        "--to", "markdown",
        "--MarkdownExporter.exclude_output=True",  # Prevent cell outputs from being written
        current_notebook_filename_ipynb, 
        # '--output-dir', current_notebook_dir, # Explicitly stating, though it's default with CWD
        # '--output', markdown_basename, # nbconvert derives this from input name
    ]
    
    print(f"\nINFO: Exporting '{current_notebook_filename_ipynb}' to '{nbconvert_output_path_in_notebook_dir}' using 'jupyter nbconvert'...")
    
    try:
        result = subprocess.run(
            nbconvert_command,
            capture_output=True, text=True, check=True,
            cwd=current_notebook_dir 
        )
        print(f"SUCCESS: Notebook initially exported by 'nbconvert' to '{nbconvert_output_path_in_notebook_dir}'.")
        if result.stdout and result.stdout.strip(): 
            print("--- nbconvert stdout ---")
            print(result.stdout.strip())
        if result.stderr and result.stderr.strip(): 
            print("--- nbconvert stderr (info/warnings) ---")
            print(result.stderr.strip())
            
    except FileNotFoundError:
        print("\nCRITICAL ERROR: 'jupyter' command (for nbconvert) was not found.")
        print("Ensure Jupyter is installed and in your system's PATH.")
        return
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: 'jupyter nbconvert' failed with exit code {e.returncode}.")
        if e.stdout and e.stdout.strip(): print(f"--- nbconvert stdout ---\n{e.stdout.strip()}")
        if e.stderr and e.stderr.strip(): print(f"--- nbconvert stderr ---\n{e.stderr.strip()}")
        return
    except Exception as e:
        print(f"\nERROR: An unexpected error occurred during 'nbconvert' execution: {e}")
        return

    # --- Step C: Apply custom post-processing (frontmatter removal & H1 delineators) ---
    if nbconvert_output_path_in_notebook_dir.exists():
        processing_successful = process_markdown(
            input_path=nbconvert_output_path_in_notebook_dir, 
            output_path=final_processed_markdown_path
        )
        
        if processing_successful:
            # If the final output path is different from the initial nbconvert output path,
            # remove the initial intermediate file. This happens when either the directory
            # or the filename (or both) are different.
            if nbconvert_output_path_in_notebook_dir.resolve() != final_processed_markdown_path.resolve():
                if nbconvert_output_path_in_notebook_dir.exists():
                    try:
                        nbconvert_output_path_in_notebook_dir.unlink()
                        print(f"INFO: Removed intermediate Markdown file: '{nbconvert_output_path_in_notebook_dir}' as output was saved to '{final_processed_markdown_path}'.")
                    except OSError as e:
                        print(f"WARNING: Could not remove intermediate Markdown file '{nbconvert_output_path_in_notebook_dir}': {e}")
        else: # processing_successful is False
            print(f"WARNING: Custom post-processing encountered an issue. The intended output '{final_processed_markdown_path}' may require review or might not be complete.")
            # In case of processing failure, we leave the intermediate nbconvert output in place for debugging.

    else: # nbconvert_output_path_in_notebook_dir does not exist
        print(f"\nERROR: The 'nbconvert' output file '{nbconvert_output_path_in_notebook_dir}' was not found. Skipping custom post-processing.")

# --- Part 4: Execute the Orchestration ---
export_notebook_and_apply_custom_processing()
print("Done")
```


```python

```