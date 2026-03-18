import json
import sys
import os

def scan_swagger(filepath):
    try:
        with open(filepath, 'r') as f:
            swagger = json.load(f)
    except Exception as e:
        print(f"Error loading swagger: {e}")
        sys.exit(1)
        
    paths = swagger.get('paths', {})
    violations = 0
    
    print("Running ZAP-Guard CI/CD Shift-Left Scanner...")
    for path, methods in paths.items():
        for method, details in methods.items():
            # Check for security requirements
            security = details.get('security', [])
            if not security:
                print(f"🚨 [FAIL] No Authentication defined for {method.upper()} {path}")
                violations += 1
                
    if violations > 0:
        print(f"\n❌ CI/CD Pipeline Blocked: {violations} Insecure/Shadow APIs detected.")
        print("Fix the Swagger spec to include authentication before merging into main.")
        sys.exit(1)
    else:
        print("\n✅ ZAP-Guard CI/CD Check Passed. No vulnerable APIs detected.")
        sys.exit(0)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python pr_scanner.py <swagger.json>")
        sys.exit(1)
    scan_swagger(sys.argv[1])
