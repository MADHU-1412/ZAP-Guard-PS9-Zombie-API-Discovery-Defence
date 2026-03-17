import json
import pandas as pd
import numpy as np
from datetime import datetime
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

def load_data(filepath='endpoints.json'):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def preprocess_features(df):
    # 1. usage_ratio = calls_30d / calls_historical
    # Avoid division by zero
    df['calls_historical'] = df['calls_historical'].replace(0, 1)
    df['usage_ratio'] = df['call_count_30d'] / df['calls_historical']

    # 2. staleness_days = NOW - last_access
    now = datetime.now()
    
    # safely parse datetime, handling tz offsets if needed (the generator does not use tz though)
    df['last_access_dt'] = pd.to_datetime(df['last_access'])
    
    # remove tz if exists to subtract cleanly
    if df['last_access_dt'].dt.tz is not None:
         now = datetime.now().astimezone()
         
    df['staleness_days'] = (now - df['last_access_dt']).dt.days

    # 3. auth_score 
    # 1(Okta/OAuth2/JWT/API_Key) -> 0(None)
    auth_map = {'OAuth2': 1.0, 'JWT': 1.0, 'API_Key': 1.0, 'Basic': 0.5, 'None': 0.0}
    df['auth_score'] = df['auth_type'].map(auth_map).fillna(0.0)

    # 4. exposure multiplier
    # PII/PCI -> higher risk
    exposure_map = {'PII': 2.0, 'PCI': 2.0, 'Confidential': 1.5, 'Internal': 1.0, 'Public': 0.5}
    df['exposure_multiplier'] = df['data_classification'].map(exposure_map).fillna(1.0)

    # 5. orphan_status
    df['orphan_status'] = df['owner_team'].apply(lambda x: 1.0 if x in ['Unknown', None, 'None'] else 0.0)

    return df

def train_and_score(df):
    if len(df) < 3:
        # Not enough data for 3 clusters
        df['risk_score'] = 0.0
        df['is_ml_zombie'] = False
        df['cluster'] = 0
        return df
        
    # Features for KMeans
    feature_cols = ['usage_ratio', 'staleness_days', 'auth_score', 'orphan_status']
    
    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df[feature_cols])

    # KMeans(3 clusters) - Healthy, Shadow, Zombie
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    df['cluster'] = kmeans.fit_predict(X_scaled)

    # Identify the zombie cluster (the one with highest average staleness)
    cluster_stats = df.groupby('cluster')[['staleness_days', 'usage_ratio']].mean()
    zombie_cluster = cluster_stats['staleness_days'].idxmax()
    df['is_ml_zombie'] = df['cluster'] == zombie_cluster

    # Rules for Zombie Probability Score 0-10
    # Base risk starts from staleness (cap at 365 for max 5 points)
    staleness_risk = np.clip(df['staleness_days'] / 365.0 * 5.0, 0, 5)
    
    # Add risk for low usage (up to 2 points)
    usage_risk = 2.0 * (1.0 - np.clip(df['usage_ratio'], 0, 1))
    
    # Add risk for no auth (up to 1.5 points)
    auth_risk = 1.5 * (1.0 - df['auth_score'])
    
    # Add risk for orphan status (up to 1.5 points)
    orphan_risk = 1.5 * df['orphan_status']
    
    base_score = staleness_risk + usage_risk + auth_risk + orphan_risk # max 10
    
    # Apply exposure multiplier and cap at 10.0
    final_score = np.clip(base_score * df['exposure_multiplier'], 0.0, 10.0)
    
    # Give it a nice curve so zombies cluster around 8-10.
    df['risk_score'] = final_score.round(1)
    
    return df

def process_apis(filepath='endpoints.json'):
    data = load_data(filepath)
    if not data:
        return []
        
    df = pd.DataFrame(data)
    df = preprocess_features(df)
    df = train_and_score(df)
    
    # Convert back to dict list, dropping datetime to serialize cleanly
    df['last_access'] = df['last_access_dt'].astype(str) # Update with consistent format
    df = df.drop(columns=['last_access_dt'])
    
    # Provide an explicit string for cluster/classification for UI
    def label_cluster(row):
        if row['is_ml_zombie'] and row['risk_score'] >= 7.5:
            return "Zombie"
        elif row['auth_score'] == 0.0:
            return "Shadow"
        else:
            return "Healthy"
            
    df['category'] = df.apply(label_cluster, axis=1)
    
    # Fill any NaNs that might have sneaked in
    df = df.fillna(0)
    
    result = df.to_dict(orient='records')
    return result

if __name__ == '__main__':
    res = process_apis()
    high_risk = [r for r in res if r['risk_score'] >= 8.0]
    print(f"Processed {len(res)} APIs. Found {len(high_risk)} high risk zombies.")
    
    # Show top 5
    top_zombies = sorted(res, key=lambda x: x['risk_score'], reverse=True)[:5]
    print("\nTop 5 Riskiest APIs:")
    for z in top_zombies:
        print(f"{z['id']} - Risk: {z['risk_score']} - Staleness: {z['staleness_days']} - Auth: {z['auth_type']}")
