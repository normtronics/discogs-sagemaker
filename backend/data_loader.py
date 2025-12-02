import json
from typing import List, Dict


def load_releases_data(jsonl_path: str) -> List[Dict]:
    """Load releases data from JSONL file"""
    releases = []
    
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                release = json.loads(line)
                releases.append(release)
    
    return releases

