import re
from pathlib import Path

# Paths
SECRETS_FILE = Path.home() / "repos/nixos/secrets.nix"
ARTICLE_FILE = Path(__file__).parent / "article.txt"

def get_secrets_map():
    """Parses secrets.nix for key-value pairs to redact."""
    secrets_map = {}
    if not SECRETS_FILE.exists():
        print(f"⚠️  Secrets file not found at {SECRETS_FILE}. Skipping redaction.")
        return secrets_map

    content = SECRETS_FILE.read_text()
    
    # Extract patterns: key = value; or key = "value";
    matches = re.findall(r'(\w+)\s*=\s*"?([^";\s]+)"?;', content)
    
    for key, value in matches:
        # Only redact keys that imply sensitive data
        if any(x in key.lower() for x in ['id', 'ip', 'password', 'token', 'secret']):
            # Convert camelCase to [SNAKE_CASE_PLACEHOLDER]
            label = f"[{re.sub(r'(?<!^)(?=[A-Z])', '_', key).upper()}]"
            secrets_map[value] = label
            
    return secrets_map

def sanitize_article():
    """Reads article.txt, applies redactions, and saves back."""
    if not ARTICLE_FILE.exists():
        print(f"⚠️  {ARTICLE_FILE.name} not found.")
        return

    secrets = get_secrets_map()
    if not secrets:
        return

    content = ARTICLE_FILE.read_text()
    original_content = content

    for value, label in secrets.items():
        # Guard: Don't redact very short strings (e.g., "0", "1", "80") 
        # that might appear naturally in prose or code.
        if len(value) > 3 and value in content:
            content = content.replace(value, label)

    if content != original_content:
        ARTICLE_FILE.write_text(content)
        print(f"✅ Article sanitized using logic from {SECRETS_FILE.name}")
    else:
        print(f"ℹ️  No secrets found to redact. Article is already clean.")

if __name__ == "__main__":
    sanitize_article()