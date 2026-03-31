import subprocess
import sys

# The command to run on the remote server
# It finds all index.md files and checks for the epoch string
REMOTE_CMD = """
find /home/mike/www/mikelev.in/_site -name "index.md" | \
xargs grep -l "pipulate-levinux-epoch-01" | wc -l
"""

def run_audit():
    print("🔍 Initiating Sovereign Audit of 994 articles...")
    
    # Use SSH to execute the count on the server
    try:
        result = subprocess.check_output([
            "ssh", "mike@192.168.10.100", REMOTE_CMD
        ], universal_newlines=True).strip()
        
        count = int(result)
        
        print(f"📊 Audit Result: {count}/994 articles are successfully dyed.")
        
        if count == 994:
            print("🏆 Perfect Alignment: The archive is 100% Machine-Ready.")
        else:
            print(f"⚠️  Missing {994 - count} anchors. Check the build logs.")
            
    except Exception as e:
        print(f"❌ Audit failed: {e}")

if __name__ == "__main__":
    run_audit()