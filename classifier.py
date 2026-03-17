import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
from anthropic import Anthropic
import warnings

warnings.filterwarnings('ignore')

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

def load_data(filepath='endpoints.json'):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def preprocess_features(df):
    df['calls_historical'] = df['calls_historical'].replace(0, 1)
    df['usage_ratio'] = df['call_count_30d'] / df['calls_historical']

    now = datetime.now()
    df['last_access_dt'] = pd.to_datetime(df['last_access'])
    if df['last_access_dt'].dt.tz is not None:
         now = datetime.now().astimezone()
         
    df['staleness_days'] = (now - df['last_access_dt']).dt.days

    auth_map = {'OAuth2': 1.0, 'JWT': 1.0, 'API_Key': 1.0, 'Basic': 0.5, 'None': 0.0}
    df['auth_score'] = df['auth_type'].map(auth_map).fillna(0.0)

    # 4. exposure score (0-10) for Ghost Score. 10 is Confidential/PII.
    exposure_map = {'Confidential (PII/Financial)': 10.0, 'Internal': 5.0, 'Public': 1.0}
    df['exposure_score'] = df['data_classification'].map(exposure_map).fillna(1.0)

    df['orphan_status'] = df['owner_team'].apply(lambda x: 1.0 if x in ['Unknown', None, 'None'] else 0.0)
    
    return df

def analyze_versions(df):
    """Flag version gaps: e.g. if /v3/ exists, /v1/ is orphaned."""
    import re
    
    # Extract base path and version: /api/v1/payments -> base='/api/payments', v=1
    def extract_version(path):
        match = re.search(r'/v(\d+)/', path)
        if match:
            # removing version segment to find base path
            base = re.sub(r'/v\d+/', '/vX/', path)
            return base, int(match.group(1))
        return None, None
        
    df['version_info'] = df['endpoint'].apply(extract_version)
    bases = df['version_info'].apply(lambda x: x[0]).dropna().unique()
    
    max_versions = {}
    for b in bases:
        max_v = df[df['version_info'].apply(lambda x: x[0]) == b]['version_info'].apply(lambda x: x[1]).max()
        max_versions[b] = max_v
        
    df['is_superseded'] = df['version_info'].apply(
        lambda x: True if (x[0] and x[1] is not None and x[1] < max_versions.get(x[0], 0)) else False
    )
    return df

def rule_based_classification(df):
    """
    Deterministic Rule Engine explicitly using: Active, Deprecated, Orphaned, Zombie.
    """
    categories = []
    ghost_scores = []
    
    df = analyze_versions(df)
    
    for _, row in df.iterrows():
        cat = "Active"
        
        # 1. Calculate Ghost Score Components (out of 10)
        # days_stale (0 to 10 maxing at 180 days)
        stale_factor = np.clip(row['staleness_days'] / 180.0 * 10.0, 0, 10)
        
        # auth_gap (0 to 10)
        auth_gap_factor = 10.0 * (1.0 - row['auth_score'])
        if row.get('stack_leak', False) or not row.get('https', True):
            auth_gap_factor = max(auth_gap_factor, 8.0) # Security vulnerabilities bump this
            
        # data_sensitivity (0 to 10)
        data_sens_factor = row['exposure_score']
        
        # traffic_anomaly (0 to 10)
        # Anomaly if traffic is high but unregistered, OR traffic is zero.
        if row['call_count_30d'] == 0:
            traffic_factor = 10.0 
        elif not row.get('documented', True):
            traffic_factor = 9.0 # Shadow traffic
        else:
            traffic_factor = 2.0 * (1.0 - np.clip(row['usage_ratio'], 0, 1))
            
        # Ghost Score = (days_stale × 0.4) + (auth_gap × 0.3) + (data_sensitivity × 0.2) + (traffic_anomaly × 0.1)
        ghost_score = (stale_factor * 0.4) + (auth_gap_factor * 0.3) + (data_sens_factor * 0.2) + (traffic_factor * 0.1)
        
        # Round 0-10
        score = float(np.clip(ghost_score, 0.0, 10.0))
        
        # Determine Category strictly
        is_stale = row['staleness_days'] > 90
        is_unused = row['call_count_30d'] == 0
        no_auth = row['auth_score'] == 0
        is_legacy = "legacy" in str(row['endpoint']).lower() or "deprecated" in str(row['endpoint']).lower() or row['is_superseded']
        undoc = not row.get('documented', True)
        no_owner = row['orphan_status'] == 1.0
        
        if is_stale and is_unused:
            cat = "Zombie"
        elif (no_auth or undoc or no_owner) and row['call_count_30d'] > 0:
            cat = "Orphaned" # Shadow -> Orphaned per rubric
        elif is_legacy and row['call_count_30d'] > 0:
            cat = "Deprecated"
            
        categories.append(cat)
        ghost_scores.append(round(score, 1))
        
    df['category'] = categories
    df['ghost_score'] = ghost_scores
    df = df.drop(columns=['version_info', 'is_superseded'])
    return df

def generate_llm_explanation(row):
    """Call Anthropic Claude to get natural language context"""
    if not client:
        return f"Deterministic Rule matched {row['category']}. (LLM explanation disabled: Missing ANTHROPIC_API_KEY)"
        
    prompt = f"Analyze this API endpoint: {row['endpoint']}. It has a Ghost Score of {row['ghost_score']}/10. It was classified as '{row['category']}'. " \
             f"Stats: {row['staleness_days']} days stale, {row['call_count_30d']} calls last 30 days, " \
             f"Auth type: {row['auth_type']}, Documented: {row.get('documented', True)}. " \
             "Give a 2 sentence compelling explanation of why this poses a security risk to the business and PCI-DSS compliance."
             
    try:
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            system="You are a cybersecurity expert analyzing API risks.",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Rule matched {row['category']}. (LLM analysis failed: {e})"

def process_apis(filepath='endpoints.json'):
    data = load_data(filepath)
    if not data:
        return []
        
    df = pd.DataFrame(data)
    if df.empty:
        return []
        
    df = preprocess_features(df)
    df = rule_based_classification(df)
    
    # Generate explanations for high risk items
    explanations = []
    
    for i, row in df.iterrows():
        # Only call LLM for risky nodes to save time and tokens
        if row['ghost_score'] >= 7.0:
            explanations.append(generate_llm_explanation(row))
        else:
            explanations.append("Active API traffic pattern detected. Compliant with expected bounds.")
            
    df['llm_explanation'] = explanations
    
    df['last_access'] = df['last_access_dt'].astype(str)
    df = df.drop(columns=['last_access_dt'])
    df = df.fillna(0)
    
    return df.to_dict(orient='records')

if __name__ == '__main__':
    res = process_apis()
    print(f"Processed {len(res)} APIs.")
