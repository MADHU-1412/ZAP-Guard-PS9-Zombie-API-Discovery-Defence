import csv
import json
import random
from datetime import datetime, timedelta

def get_random_date(start_days_ago, end_days_ago):
    random_days = random.randint(end_days_ago, start_days_ago)
    return (datetime.now() - timedelta(days=random_days)).isoformat()

def generate_endpoints(num_total=500):
    endpoints = []
    
    # Chaos counts
    num_zombie = int(num_total * 0.20)  # 100
    num_shadow = int(num_total * 0.15)  # 75
    num_exposed = int(num_total * 0.10) # 50
    
    # Base lists
    methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
    auth_types = ['OAuth2', 'JWT', 'API_Key', 'Basic']
    data_classes = ['Public', 'Internal', 'Confidential']
    teams = ['Retail', 'Core Banking', 'Payments', 'Identity', 'Fraud', 'Mobile App']
    
    base_paths = ['/api/v1/account', '/api/v2/loan', '/api/v1/user', '/api/v3/transaction', '/shadow/payroll', '/internal/admin', '/api/v1/cards', '/api/v2/rewards']
    actions = ['/balance', '/approve', '/dump', '/status', '/update', '/delete', '/list', '/details']

    for i in range(num_total):
        # Default flags
        is_zombie = i < num_zombie
        is_shadow = num_zombie <= i < (num_zombie + num_shadow)
        is_exposed = (num_zombie + num_shadow) <= i < (num_zombie + num_shadow + num_exposed)
        
        # We can also distribute flags randomly, but this guarantees exact proportions.
        # To make it more realistic, let's just shuffle later.
        
        api_id = f"API_{i+1:03d}"
        path = random.choice(base_paths) + random.choice(actions)
        method = random.choice(methods)
        
        if is_zombie:
            # 0 calls + >90days
            call_count_30d = 0
            last_access = get_random_date(365, 91) # 91 to 365 days ago
            calls_historical = random.randint(100, 5000)
            auth_type = random.choice(auth_types)
            data_classification = random.choice(data_classes)
            owner_team = random.choice(teams + [None])
        elif is_shadow:
            # no auth
            call_count_30d = random.randint(1, 10000)
            last_access = get_random_date(30, 0)
            calls_historical = call_count_30d + random.randint(1000, 50000)
            auth_type = 'None'
            data_classification = random.choice(data_classes)
            owner_team = random.choice(teams + [None])
        elif is_exposed:
            # PII / PCI data
            call_count_30d = random.randint(1, 10000)
            last_access = get_random_date(30, 0)
            calls_historical = call_count_30d + random.randint(1000, 50000)
            auth_type = random.choice(auth_types + ['None'])
            data_classification = random.choice(['PII', 'PCI'])
            owner_team = random.choice(teams + [None])
        else:
            # Normal healthy API
            call_count_30d = random.randint(100, 50000)
            last_access = get_random_date(10, 0)
            calls_historical = call_count_30d + random.randint(10000, 200000)
            auth_type = random.choice(auth_types)
            data_classification = random.choice(data_classes)
            owner_team = random.choice(teams)
            
        deploy_date = get_random_date(1000, 400) # deployed 400 to 1000 days ago
        
        # Orphan roughly 5% overall for extra chaos unless already set
        if not is_zombie and not is_shadow and not is_exposed and random.random() < 0.05:
            owner_team = None
            
        # Optional: Add multiple paths per API to make them unique
        endpoint = f"{path}/{api_id.lower()}" if path.startswith('/shadow/payroll') else path
        # Random uniqueness
        if random.random() < 0.5:
            endpoint += f"/{random.randint(1, 999)}"

        endpoints.append({
            "id": api_id,
            "endpoint": endpoint,
            "method": method,
            "last_access": last_access,
            "call_count_30d": call_count_30d,
            "calls_historical": calls_historical,
            "auth_type": auth_type,
            "data_classification": data_classification,
            "owner_team": owner_team if owner_team else "Unknown",
            "deploy_date": deploy_date
        })

    # Shuffle to mix zombies, shadows, exposed
    random.shuffle(endpoints)
    return endpoints

def main():
    endpoints = generate_endpoints(500)
    
    # Save as JSON
    with open('endpoints.json', 'w') as f:
        json.dump(endpoints, f, indent=4)
        
    # Save as CSV
    if endpoints:
        keys = endpoints[0].keys()
        with open('apis.csv', 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(endpoints)
            
    print(f"Generated {len(endpoints)} synthetic APIs.")
    print("Files saved: endpoints.json, apis.csv")

if __name__ == '__main__':
    main()
