#!/usr/bin/env python3
"""
Weaviate Collection Batch Fix Tool for Dify
============================================

Fixes the vectorConfig schema incompatibility issue after upgrading Dify.

Problem: After upgrading Dify, knowledge bases created with older versions
may use the old Weaviate schema format (vectorIndexConfig) instead of the
new format (vectorConfig.default), causing vector search to fail.

Error message:
    "Vector_index_xxx_Node does not have named vector default configured.
     Available named vectors map[]."

Solution: This script recreates affected collections with the correct schema.
After running, you must re-embed documents in Dify.

Usage:
    python batch_fix_weaviate.py scan              # List collections needing fix
    python batch_fix_weaviate.py dry-run           # Simulate fix (no changes)
    python batch_fix_weaviate.py fix               # Fix all affected collections
    python batch_fix_weaviate.py fix-one <name>    # Fix single collection
    python batch_fix_weaviate.py cleanup           # Remove orphaned collections
    python batch_fix_weaviate.py list-names        # Show dataset names from DB

Environment Variables:
    WEAVIATE_ENDPOINT  - Weaviate URL (default: http://weaviate:8080)
    WEAVIATE_API_KEY   - Weaviate API key (default: empty for no auth)
    DIFY_DB_HOST       - PostgreSQL host (default: db)
    DIFY_DB_PORT       - PostgreSQL port (default: 5432)
    DIFY_DB_USER       - PostgreSQL user (default: postgres)
    DIFY_DB_PASSWORD   - PostgreSQL password (default: difyai123456)
    DIFY_DB_NAME       - PostgreSQL database (default: dify)

Author: https://github.com/yupoet
License: MIT
"""

import os
import sys
import json
import time
import requests
from typing import List, Dict, Tuple, Optional, Set

# ============ Configuration ============

# Weaviate settings - can be overridden by environment variables
WEAVIATE_URL = os.environ.get("WEAVIATE_ENDPOINT", "http://weaviate:8080")
WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY", "")

# PostgreSQL settings for querying dataset names
DB_CONFIG = {
    "host": os.environ.get("DIFY_DB_HOST", os.environ.get("DB_HOST", "db")),
    "port": os.environ.get("DIFY_DB_PORT", os.environ.get("DB_PORT", "5432")),
    "user": os.environ.get("DIFY_DB_USER", os.environ.get("DB_USERNAME", "postgres")),
    "password": os.environ.get("DIFY_DB_PASSWORD", os.environ.get("DB_PASSWORD", "difyai123456")),
    "database": os.environ.get("DIFY_DB_NAME", os.environ.get("DB_DATABASE", "dify")),
}

# Request headers
def get_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if WEAVIATE_API_KEY:
        headers["Authorization"] = f"Bearer {WEAVIATE_API_KEY}"
    return headers

HEADERS = get_headers()

# ============ Database Functions ============

def get_db_connection():
    """Get PostgreSQL connection if psycopg2 is available"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"]
        )
        return conn
    except ImportError:
        print("⚠️  psycopg2 not installed. Database queries unavailable.")
        print("   Install with: pip install psycopg2-binary")
        return None
    except Exception as e:
        print(f"⚠️  Database connection failed: {e}")
        return None

def get_dataset_names(dataset_ids: List[str]) -> Dict[str, str]:
    """Query dataset names from PostgreSQL"""
    conn = get_db_connection()
    if not conn or not dataset_ids:
        return {}
    
    try:
        cursor = conn.cursor()
        placeholders = ",".join(["%s"] * len(dataset_ids))
        query = f"SELECT id, name FROM datasets WHERE id IN ({placeholders})"
        cursor.execute(query, dataset_ids)
        results = cursor.fetchall()
        conn.close()
        return {str(row[0]): row[1] for row in results}
    except Exception as e:
        print(f"⚠️  Query failed: {e}")
        return {}

def get_all_dataset_ids_from_db() -> Set[str]:
    """Get all dataset IDs from PostgreSQL"""
    conn = get_db_connection()
    if not conn:
        return set()
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM datasets")
        results = cursor.fetchall()
        conn.close()
        return {str(row[0]) for row in results}
    except Exception as e:
        print(f"⚠️  Query failed: {e}")
        return set()

# ============ Weaviate Functions ============

def test_weaviate_connection() -> bool:
    """Test connection to Weaviate"""
    try:
        resp = requests.get(f"{WEAVIATE_URL}/v1/.well-known/ready", headers=HEADERS, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"❌ Cannot connect to Weaviate at {WEAVIATE_URL}: {e}")
        return False

def get_all_collections() -> List[Dict]:
    """Get all collections from Weaviate"""
    try:
        resp = requests.get(f"{WEAVIATE_URL}/v1/schema", headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            print(f"❌ Failed to get schema: {resp.status_code} - {resp.text}")
            return []
        return resp.json().get("classes", [])
    except Exception as e:
        print(f"❌ Error getting collections: {e}")
        return []

def is_old_format(collection: Dict) -> bool:
    """Check if collection uses old schema format"""
    return "vectorConfig" not in collection and "vectorIndexConfig" in collection

def is_dify_collection(collection: Dict) -> bool:
    """Check if collection belongs to Dify (Vector_index_*_Node format)"""
    name = collection.get("class", "")
    return name.startswith("Vector_index_") and name.endswith("_Node")

def extract_dataset_id(class_name: str) -> str:
    """Extract dataset ID from collection name"""
    # Format: Vector_index_{uuid_with_underscores}_Node
    parts = class_name.replace("Vector_index_", "").replace("_Node", "").split("_")
    if len(parts) >= 5:
        return "-".join(parts[:5])
    return "unknown"

def get_collection_info(collection: Dict) -> Dict:
    """Get detailed info about a collection"""
    name = collection.get("class", "")
    dataset_id = extract_dataset_id(name)
    
    # Try to extract creation time from property descriptions
    created_at = "unknown"
    for prop in collection.get("properties", []):
        desc = prop.get("description", "")
        if "auto-schema feature on" in desc:
            created_at = desc.split("on ")[-1] if "on " in desc else "unknown"
            break
    
    return {
        "name": name,
        "dataset_id": dataset_id,
        "created_at": created_at,
        "is_old_format": is_old_format(collection),
        "is_dify_collection": is_dify_collection(collection)
    }

def get_object_count(class_name: str) -> int:
    """Get approximate object count in a collection"""
    try:
        resp = requests.post(
            f"{WEAVIATE_URL}/v1/graphql",
            headers=HEADERS,
            json={"query": f"{{ Aggregate {{ {class_name} {{ meta {{ count }} }} }} }}"},
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", {}).get("Aggregate", {}).get(class_name, [{}])[0].get("meta", {}).get("count", 0)
    except:
        pass
    return 0

def delete_collection(class_name: str) -> bool:
    """Delete a collection"""
    try:
        resp = requests.delete(
            f"{WEAVIATE_URL}/v1/schema/{class_name}",
            headers=HEADERS,
            timeout=30
        )
        return resp.status_code in [200, 204]
    except Exception as e:
        print(f"❌ Delete failed: {e}")
        return False

def create_collection_new_format(class_name: str, old_schema: Dict) -> Tuple[bool, str]:
    """Create collection with new schema format"""
    properties = old_schema.get("properties", [])
    
    # Remove any auto-generated descriptions to avoid conflicts
    clean_properties = []
    for prop in properties:
        clean_prop = {k: v for k, v in prop.items() if k != "description"}
        clean_properties.append(clean_prop)
    
    new_schema = {
        "class": class_name,
        "properties": clean_properties,
        "vectorConfig": {
            "default": {
                "vectorIndexType": "hnsw",
                "vectorIndexConfig": {
                    "distance": "cosine",
                    "ef": -1,
                    "efConstruction": 128,
                    "maxConnections": 32,
                    "cleanupIntervalSeconds": 300,
                    "flatSearchCutoff": 40000
                },
                "vectorizer": {"none": {}}
            }
        }
    }
    
    try:
        resp = requests.post(
            f"{WEAVIATE_URL}/v1/schema",
            headers=HEADERS,
            json=new_schema,
            timeout=30
        )
        return resp.status_code == 200, resp.text
    except Exception as e:
        return False, str(e)

# ============ Main Operations ============

def scan_collections(show_details: bool = True) -> Tuple[List[Dict], List[Dict]]:
    """Scan all collections and identify those needing fix"""
    print("=" * 70)
    print("Scanning Weaviate Collections")
    print("=" * 70)
    print(f"Weaviate URL: {WEAVIATE_URL}")
    print(f"Auth: {'Enabled' if WEAVIATE_API_KEY else 'Disabled'}")
    print()
    
    if not test_weaviate_connection():
        return [], []
    
    collections = get_all_collections()
    dify_collections = [c for c in collections if is_dify_collection(c)]
    
    print(f"Total collections: {len(collections)}")
    print(f"Dify collections: {len(dify_collections)}")
    print()
    
    old_format = []
    new_format = []
    
    for c in dify_collections:
        info = get_collection_info(c)
        if info["is_old_format"]:
            old_format.append(info)
        else:
            new_format.append(info)
    
    print(f"✅ New format (OK): {len(new_format)}")
    print(f"⚠️  Old format (need fix): {len(old_format)}")
    print()
    
    if show_details and old_format:
        # Try to get dataset names
        dataset_ids = [info["dataset_id"] for info in old_format]
        names = get_dataset_names(dataset_ids)
        
        print("Collections needing fix:")
        print("-" * 70)
        for i, info in enumerate(old_format, 1):
            name = names.get(info["dataset_id"], "(name unavailable)")
            print(f"{i:2}. {info['name']}")
            print(f"    Dataset ID: {info['dataset_id']}")
            print(f"    Name: {name}")
            print(f"    Created: {info['created_at']}")
            print()
    
    return old_format, new_format

def fix_single_collection(class_name: str, dry_run: bool = False) -> bool:
    """Fix a single collection"""
    prefix = "[DRY RUN] " if dry_run else ""
    print(f"\n{prefix}Fixing: {class_name}")
    print("-" * 60)
    
    # Get current schema
    print("1. Getting current schema...")
    try:
        resp = requests.get(f"{WEAVIATE_URL}/v1/schema/{class_name}", headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            print(f"   ❌ Failed: {resp.text}")
            return False
        schema = resp.json()
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Check if fix needed
    if "vectorConfig" in schema:
        print("   ✅ Already new format, skipping")
        return True
    
    if dry_run:
        print("   [DRY RUN] Would delete and recreate collection")
        return True
    
    # Delete old collection
    print("2. Deleting old collection...")
    if not delete_collection(class_name):
        print("   ❌ Delete failed")
        return False
    print("   ✅ Deleted")
    
    # Create new collection
    print("3. Creating new format collection...")
    success, msg = create_collection_new_format(class_name, schema)
    if not success:
        print(f"   ❌ Create failed: {msg}")
        return False
    print("   ✅ Created")
    
    print(f"\n✅ {class_name} fixed successfully!")
    print("   ⚠️  Remember to re-embed in Dify!")
    
    return True

def batch_fix(dry_run: bool = False):
    """Fix all affected collections"""
    old_format, _ = scan_collections(show_details=True)
    
    if not old_format:
        print("\n✅ No collections need fixing!")
        return
    
    print("\n" + "=" * 70)
    print("[DRY RUN] Simulating batch fix" if dry_run else "Starting batch fix")
    print("=" * 70)
    
    if not dry_run:
        print(f"\n⚠️  This will recreate {len(old_format)} collections.")
        print("   Vector data will be cleared. You must re-embed in Dify afterwards.")
        confirm = input(f"\nProceed with fixing {len(old_format)} collections? (yes/no): ")
        if confirm.lower() != "yes":
            print("Cancelled.")
            return
    
    success_count = 0
    failed = []
    
    for info in old_format:
        try:
            if fix_single_collection(info["name"], dry_run):
                success_count += 1
            else:
                failed.append(info)
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            failed.append(info)
        
        if not dry_run:
            time.sleep(0.5)
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"✅ Success: {success_count}")
    print(f"❌ Failed: {len(failed)}")
    
    if failed:
        print("\nFailed collections:")
        for info in failed:
            print(f"  - {info['name']}")
    
    if not dry_run and success_count > 0:
        # Get names for successful fixes
        successful = [info for info in old_format if info not in failed]
        dataset_ids = [info["dataset_id"] for info in successful]
        names = get_dataset_names(dataset_ids)
        
        print("\n" + "=" * 70)
        print("⚠️  IMPORTANT: Next Steps")
        print("=" * 70)
        print("Re-embed the following knowledge bases in Dify:")
        print("(Go to Settings → Embedding Model → Switch model → Save → Switch back)")
        print()
        for info in successful:
            name = names.get(info["dataset_id"], "(name unavailable)")
            print(f"  • {name}")
            print(f"    ID: {info['dataset_id']}")

def cleanup_orphaned():
    """Find and optionally remove orphaned collections"""
    print("=" * 70)
    print("Scanning for Orphaned Collections")
    print("=" * 70)
    
    if not test_weaviate_connection():
        return
    
    collections = get_all_collections()
    dify_collections = [c for c in collections if is_dify_collection(c)]
    
    # Get all dataset IDs from Weaviate
    weaviate_ids = set()
    for c in dify_collections:
        info = get_collection_info(c)
        weaviate_ids.add(info["dataset_id"])
    
    # Get all dataset IDs from database
    db_ids = get_all_dataset_ids_from_db()
    
    if not db_ids:
        print("⚠️  Could not query database. Cannot identify orphaned collections.")
        return
    
    # Find orphaned
    orphaned_ids = weaviate_ids - db_ids
    
    print(f"Weaviate collections: {len(weaviate_ids)}")
    print(f"Database datasets: {len(db_ids)}")
    print(f"Orphaned collections: {len(orphaned_ids)}")
    print()
    
    if not orphaned_ids:
        print("✅ No orphaned collections found!")
        return
    
    # Find collection names for orphaned IDs
    orphaned_collections = []
    for c in dify_collections:
        info = get_collection_info(c)
        if info["dataset_id"] in orphaned_ids:
            orphaned_collections.append(info)
    
    print("Orphaned collections (exist in Weaviate but not in Dify DB):")
    print("-" * 70)
    for info in orphaned_collections:
        count = get_object_count(info["name"])
        print(f"  • {info['name']}")
        print(f"    Dataset ID: {info['dataset_id']}")
        print(f"    Objects: {count}")
        print()
    
    confirm = input(f"\nDelete {len(orphaned_collections)} orphaned collections? (yes/no): ")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return
    
    for info in orphaned_collections:
        print(f"Deleting {info['name']}...", end=" ")
        if delete_collection(info["name"]):
            print("✅")
        else:
            print("❌")
    
    print("\n✅ Cleanup complete!")

def list_dataset_names():
    """List all dataset names that need re-embedding"""
    old_format, _ = scan_collections(show_details=False)
    
    if not old_format:
        print("\n✅ No collections need fixing!")
        return
    
    dataset_ids = [info["dataset_id"] for info in old_format]
    names = get_dataset_names(dataset_ids)
    
    print("\n" + "=" * 70)
    print("Knowledge Bases Needing Re-embedding")
    print("=" * 70)
    
    for info in old_format:
        name = names.get(info["dataset_id"], "(name unavailable)")
        print(f"\n• {name}")
        print(f"  ID: {info['dataset_id']}")
        print(f"  Collection: {info['name']}")

def show_help():
    """Show usage help"""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║     Weaviate Collection Batch Fix Tool for Dify                      ║
║     Fixes vectorConfig schema incompatibility after upgrade          ║
╚══════════════════════════════════════════════════════════════════════╝

Usage:
  python batch_fix_weaviate.py <command>

Commands:
  scan        Scan and list collections needing fix
  dry-run     Simulate batch fix (no changes made)
  fix         Fix all affected collections
  fix-one     Fix single collection: fix-one <collection_name>
  cleanup     Find and remove orphaned collections
  list-names  List dataset names needing re-embedding
  help        Show this help message

Environment Variables:
  WEAVIATE_ENDPOINT   Weaviate URL (default: http://weaviate:8080)
  WEAVIATE_API_KEY    Weaviate API key
  DIFY_DB_HOST        PostgreSQL host (default: db)
  DIFY_DB_PORT        PostgreSQL port (default: 5432)
  DIFY_DB_USER        PostgreSQL user (default: postgres)
  DIFY_DB_PASSWORD    PostgreSQL password
  DIFY_DB_NAME        PostgreSQL database (default: dify)

Examples:
  # Inside Dify container
  docker exec docker-api-1 python /tmp/batch_fix_weaviate.py scan

  # With custom Weaviate URL
  WEAVIATE_ENDPOINT=http://localhost:8080 python batch_fix_weaviate.py scan

  # Fix a specific collection
  python batch_fix_weaviate.py fix-one Vector_index_abc123_Node

Author: https://github.com/yupoet
""")

def main():
    if len(sys.argv) < 2:
        show_help()
        return
    
    cmd = sys.argv[1].lower()
    
    if cmd == "scan":
        scan_collections()
    elif cmd == "dry-run":
        batch_fix(dry_run=True)
    elif cmd == "fix":
        batch_fix(dry_run=False)
    elif cmd == "fix-one":
        if len(sys.argv) < 3:
            print("❌ Please specify collection name: fix-one <collection_name>")
            return
        fix_single_collection(sys.argv[2], dry_run=False)
    elif cmd == "cleanup":
        cleanup_orphaned()
    elif cmd == "list-names":
        list_dataset_names()
    elif cmd in ["help", "-h", "--help"]:
        show_help()
    else:
        print(f"❌ Unknown command: {cmd}")
        print("   Run 'python batch_fix_weaviate.py help' for usage")

if __name__ == "__main__":
    main()
