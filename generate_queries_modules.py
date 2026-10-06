import re
import os
import json

def parse_engine(filepath, engine_name):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    sections = re.split(r'INSIGHT #\d+:', text)
    insights = []
    
    for idx, s in enumerate(sections[1:], start=1):
        lines = s.strip().split('\n')
        title = lines[0].strip()
        method_match = re.search(r'Method Name\s*:\s*([^\n]+)', s)
        headers_match = re.search(r'Headers\s*:\s*([^\n]+)', s)
        desc_match = re.search(r'Description\s*:\s*([^\n]+)', s)
        
        headers = []
        if headers_match:
            headers = [h.strip() for h in headers_match.group(1).split(',')]
            
        method = method_match.group(1).strip() if method_match else f'{engine_name}Connector.get_insight_{idx}()'
        desc = desc_match.group(1).strip() if desc_match else ''
        
        query = ''
        q_match = re.search(r'query\s*=\s*(?:f?\"{3}(.*?)\"{3}|f?\'{3}(.*?)\'{3})', s, re.DOTALL)
        if q_match:
            query = (q_match.group(1) or q_match.group(2) or '').strip()
        elif 'SQL Query:' in s:
            parts = s.split('SQL Query:')
            if len(parts) > 1:
                q_part = parts[1].split('--------------------------------------------------------------------------------')[0].strip()
                q_part = re.sub(r'^```(?:sql|python)?\s*', '', q_part)
                q_part = re.sub(r'```\s*$', '', q_part)
                query = q_part.strip()
        elif 'SQL Query / Implementation:' in s:
            parts = s.split('SQL Query / Implementation:')
            if len(parts) > 1:
                q_part = parts[1].split('--------------------------------------------------------------------------------')[0].strip()
                q_match2 = re.search(r'query\s*=\s*(?:f?\"{3}(.*?)\"{3}|f?\'{3}(.*?)\'{3})', q_part, re.DOTALL)
                if q_match2:
                    query = (q_match2.group(1) or q_match2.group(2) or '').strip()
                else:
                    query = q_part.strip()
        
        # Categorize into 13 tabs
        tl = title.lower()
        if any(w in tl for w in ['storage', 'size', 'footprint', 'engine', 'table-level', 'tablespace', 'datafile', 'segment']):
            cat = 'Storage'
        elif any(w in tl for w in ['io', 'i/o', 'wait', 'buffer pool', 'temp file', 'temporary table', 'temp table']):
            cat = 'I/O'
        elif any(w in tl for w in ['slow', 'cpu', 'frequent', 'digest', 'stat_statements', 'execution time', 'resource-intensive']):
            cat = 'Query Performance'
        elif any(w in tl for w in ['connection', 'session', 'thread', 'processlist', 'transaction']):
            cat = 'Connections'
        elif any(w in tl for w in ['lock', 'deadlock', 'blocking', 'blocked']):
            cat = 'Locks'
        elif any(w in tl for w in ['index', 'primary key', 'auto_increment']):
            cat = 'Indexes'
        elif any(w in tl for w in ['foreign key', 'parent', 'child', 'relationship', 'graph']):
            cat = 'Schema'
        elif any(w in tl for w in ['json', 'column', 'generated', 'large object', 'blob', 'varchar', 'collation']):
            cat = 'Structure'
        elif any(w in tl for w in ['procedure', 'routine', 'function', 'view', 'trigger', 'package', 'event', 'scheduled']):
            cat = 'Objects'
        elif any(w in tl for w in ['replication', 'binlog', 'wal', 'redo', 'gtid', 'slave', 'replica', 'archive', 'data guard']):
            cat = 'Replication'
        elif any(w in tl for w in ['user', 'privilege', 'role', 'security']):
            cat = 'Security'
        elif any(w in tl for w in ['version', 'environment', 'variable', 'parameter', 'config', 'data directory']):
            cat = 'Environment'
        else:
            cat = 'Overview'
            
        insights.append({
            'id': idx,
            'title': title,
            'method': method,
            'description': desc,
            'headers': headers,
            'category': cat,
            'query': query
        })
    return insights

def write_module(target_path, engine_name, insights):
    content = f'''"""
{engine_name} Database Insights & Dynamic SQL Queries
Auto-documented query methods and metadata reference for {engine_name}.
"""

import re
from typing import Any, Dict, List, Optional

INSIGHTS: List[Dict[str, Any]] = {json.dumps(insights, indent=4)}

# Pre-indexed dictionary for fast O(1) lookup
_INDEX_BY_TITLE: Dict[str, Dict[str, Any]] = {{}}
_INDEX_BY_ID: Dict[str, Dict[str, Any]] = {{}}

for item in INSIGHTS:
    raw_title = item.get("title", "")
    _INDEX_BY_TITLE[raw_title.lower()] = item
    clean_title = re.sub(r"^\\d+\\.\\s*", "", raw_title).strip().lower()
    _INDEX_BY_TITLE[clean_title] = item
    _INDEX_BY_ID[str(item.get("id"))] = item


def get_query(title_or_key: str) -> Optional[Dict[str, Any]]:
    """Retrieve metadata, method name, and query for an insight by title or keyword."""
    if not title_or_key:
        return None
    k = title_or_key.strip().lower()
    if k in _INDEX_BY_TITLE:
        return _INDEX_BY_TITLE[k]
    
    clean_k = re.sub(r"^\\d+\\.\\s*", "", k).strip()
    if clean_k in _INDEX_BY_TITLE:
        return _INDEX_BY_TITLE[clean_k]
        
    if k in _INDEX_BY_ID:
        return _INDEX_BY_ID[k]
        
    # Substring / Keyword matching
    for title_k, item in _INDEX_BY_TITLE.items():
        if len(clean_k) >= 4 and (clean_k in title_k or title_k in clean_k):
            return item
            
    # Word token matching
    k_tokens = [w for w in clean_k.split() if len(w) > 3 and w not in ["database", "table", "mysql", "oracle", "postgres", "sqlserver"]]
    if k_tokens:
        for title_k, item in _INDEX_BY_TITLE.items():
            if all(t in title_k for t in k_tokens):
                return item

    return None


def get_all_queries() -> List[Dict[str, Any]]:
    """Return all insight definitions for {engine_name}."""
    return INSIGHTS
'''
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Generated {target_path} with {len(insights)} insights.")

if __name__ == '__main__':
    base_dir = os.path.dirname(__file__)
    queries_dir = os.path.join(base_dir, 'database_queries')
    os.makedirs(queries_dir, exist_ok=True)
    
    mapping = [
        ('mysql_insights_and_queries.txt', 'MySQL', os.path.join(queries_dir, 'mysql.py')),
        ('postgres_insights_and_queries.txt', 'PostgreSQL', os.path.join(queries_dir, 'postgres.py')),
        ('oracle_insights_and_queries.txt', 'Oracle', os.path.join(queries_dir, 'oracle.py')),
        ('sqlserver_insights_and_queries.txt', 'SQLServer', os.path.join(queries_dir, 'sqlserver.py')),
    ]
    
    for txt_file, engine, py_file in mapping:
        txt_path = os.path.join(base_dir, txt_file)
        if os.path.exists(txt_path):
            ins = parse_engine(txt_path, engine)
            write_module(py_file, engine, ins)
        else:
            print(f"File not found: {txt_path}")
