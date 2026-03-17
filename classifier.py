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

    exposure_map = {'PII': 2.0, 'PCI': 2.0, 'Confidential': 1.5, 'Internal': 1.0, 'Public': 0.5}
    df['exposure_multiplier'] = df['data_classification'].map(exposure_map).fillna(1.0)

    df['orphan_status'] = df['owner_team'].apply(lambda x: 1.0 if x in ['Unknown', None, 'None'] else 0.0)
    
    return df

def rule_based_classification(df):
    """
    Deterministic Rule Engine
    Zombie: staleness > 90 days AND (no calls in 30d OR usage ratio < 0.01)
    Shadow: undocumented OR auth == None
    Deprecated: url contains legacy/deprecated AND has traffic
    """
    categories = []
    risk_scores = []
    
    for _, row in df.iterrows():
        cat = "Healthy"
        
        # Risk Score building
        staleness_risk = np.clip(row['staleness_days'] / 365.0 * 5.0, 0, 5)
        usage_risk = 2.0 * (1.0 - np.clip(row['usage_ratio'], 0, 1))
        auth_risk = 0 if row['auth_score'] > 0 else 2.5
        orphan_risk = 1.5 * row['orphan_status']
        doc_risk = 0 if row.get('documented', True) else 1.0
        vuln_risk = 2.0 if row.get('stack_leak', False) else 0.0
        
        base_score = staleness_risk + usage_risk + auth_risk + orphan_risk + doc_risk + vuln_risk
        score = float(np.clip(base_score * row['exposure_multiplier'], 0.0, 10.0))
        
        # Determine Category
        is_stale = row['staleness_days'] > 90
        is_unused = row['call_count_30d'] == 0
        no_auth = row['auth_score'] == 0
        is_legacy = "legacy" in str(row['endpoint']).lower() or "deprecated" in str(row['endpoint']).lower()
        undoc = not row.get('documented', True)
        
        if is_stale and is_unused:
            cat = "Zombie"
        elif (no_auth or undoc) and row['call_count_30d'] > 0:
            cat = "Shadow"
        elif is_legacy and row['call_count_30d'] > 0:
            cat = "Deprecated"
            
        categories.append(cat)
        # Bumping score slightly if hard Zombie to ensure it displays at top
        if cat == "Zombie": 
            score = max(score, 8.5)
        elif cat == "Shadow":
            score = max(score, 7.5)
            
        risk_scores.append(round(score, 1))
        
    df['category'] = categories
    df['risk_score'] = risk_scores
    return df

def generate_llm_explanation(row):
    """Call Anthropic Claude to get natural language context"""
    if not client:
        return f"Deterministic Rule matched {row['category']}. (LLM explanation disabled: Missing ANTHROPIC_API_KEY)"
        
    prompt = f"Analyze this API endpoint: {row['endpoint']}. It has a risk score of {row['risk_score']}/10. It was classified as '{row['category']}'. " \
             f"Stats: {row['staleness_days']} days stale, {row['call_count_30d']} calls last 30 days, " \
             f"Auth type: {row['auth_type']}, Documented: {row.get('documented', True)}. " \
             "Give a 2 sentence compelling explanation of why this poses a security risk to the business."
             
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
        if row['risk_score'] >= 7.0:
            explanations.append(generate_llm_explanation(row))
        else:
            explanations.append("Healthy API traffic pattern detected. No significant anomalies.")
            
    df['llm_explanation'] = explanations
    
    df['last_access'] = df['last_access_dt'].astype(str)
    df = df.drop(columns=['last_access_dt'])
    df = df.fillna(0)
    
    return df.to_dict(orient='records')

if __name__ == '__main__':
    res = process_apis()
    print(f"Processed {len(res)} APIs.")
