# How to Fix Knowledge Base Vector Search After Upgrading Dify (Weaviate vectorConfig Issue)

[中文版本](./fix-weaviate-after-upgrade-zh.md)

## Problem Description

After upgrading Dify from an older version (e.g., 1.8.x, 1.10.x) to a newer version (e.g., 1.11.0+), you may encounter the following error when testing recall/retrieval in your Knowledge Base:

```
Query call with protocol GRPC search failed with message extract target vectors: class 
Vector_index_XXXXXXXX_XXXX_XXXX_XXXX_XXXXXXXXXXXX_Node does not have named vector default 
configured. Available named vectors map[].
```

![Error Screenshot](https://your-screenshot-url.png)

## Root Cause

This issue is caused by a **schema format change in Weaviate**. 

- **Old format**: Uses `vectorIndexConfig` at the top level
- **New format**: Uses `vectorConfig.default` with nested configuration

When Dify upgrades, it expects the new `vectorConfig` format, but knowledge bases created before the upgrade still use the old format. This mismatch causes the vector search to fail.

### Old Format (Before Upgrade)
```json
{
  "class": "Vector_index_xxx_Node",
  "vectorIndexConfig": {
    "distance": "cosine",
    ...
  },
  "vectorizer": "none"
}
```

### New Format (After Upgrade)
```json
{
  "class": "Vector_index_xxx_Node",
  "vectorConfig": {
    "default": {
      "vectorIndexType": "hnsw",
      "vectorIndexConfig": {
        "distance": "cosine",
        ...
      },
      "vectorizer": {"none": {}}
    }
  }
}
```

## Solution Overview

The fix involves three steps:

1. **Identify** affected collections (old format)
2. **Recreate** collections with the new schema format
3. **Re-embed** documents in Dify to repopulate vector data

> ⚠️ **Important**: This process will clear the vector data in affected collections. You must re-embed documents in Dify after fixing the schema.

---

## Step-by-Step Fix

### Prerequisites

- SSH access to your Dify server
- Docker installed and running
- Basic command line knowledge

### Step 1: Check Your Weaviate API Key

```bash
docker exec docker-api-1 env | grep -i weaviate
```

Look for `WEAVIATE_API_KEY` in the output. You'll need this for the fix script.

### Step 2: Scan for Affected Collections

First, let's see which collections need fixing:

```bash
# Download the fix script
curl -o /tmp/batch_fix_weaviate.py https://raw.githubusercontent.com/yupoet/dify-weaviate-fix/main/batch_fix_weaviate.py

# Copy to container
docker cp /tmp/batch_fix_weaviate.py docker-api-1:/tmp/

# Run scan
docker exec docker-api-1 python /tmp/batch_fix_weaviate.py scan
```

This will show you:
- Total collections found
- Collections with new format (OK)
- Collections with old format (need fix)

### Step 3: Test Fix on One Collection (Recommended)

Before batch fixing, test on a single collection:

```bash
# Dry run (simulation, no changes made)
docker exec docker-api-1 python /tmp/batch_fix_weaviate.py dry-run

# Fix a single collection
docker exec -it docker-api-1 python /tmp/batch_fix_weaviate.py fix-one Vector_index_XXXX_Node
```

### Step 4: Batch Fix All Affected Collections

```bash
docker exec -it docker-api-1 python /tmp/batch_fix_weaviate.py fix
```

The script will:
1. Ask for confirmation
2. Delete old format collections
3. Recreate with new format
4. List dataset IDs that need re-embedding

### Step 5: Get Knowledge Base Names

The script outputs dataset IDs. To find the actual names in Dify:

```bash
docker exec docker-db-1 psql -U postgres -d dify -c "
SELECT id, name FROM datasets WHERE id IN (
  'dataset-id-1',
  'dataset-id-2'
) ORDER BY name;
"
```

### Step 6: Re-embed Documents in Dify

For each affected knowledge base:

1. Go to Dify Knowledge Base
2. Find the knowledge base by name
3. Go to **Settings** → **Embedding Model**
4. **Switch to a different embedding model** (temporarily)
5. Click **Save** - this triggers re-embedding
6. **Switch back** to your preferred embedding model
7. Click **Save** again

> 💡 **Tip**: Switching the embedding model is the easiest way to force Dify to re-embed all documents. You can switch to any other model and then switch back.

Alternatively, you can:
- Delete and re-upload all documents
- Use the "Re-index" feature if available in your Dify version

---

## Manual Fix (Without Script)

If you prefer to fix manually:

### 1. Check Collection Format

```bash
docker exec docker-api-1 curl -s -H "Authorization: Bearer YOUR_API_KEY" \
  "http://weaviate:8080/v1/schema/Vector_index_XXXX_Node"
```

If you see `vectorIndexConfig` but no `vectorConfig`, it needs fixing.

### 2. Delete Old Collection

```bash
docker exec docker-api-1 curl -s -X DELETE \
  -H "Authorization: Bearer YOUR_API_KEY" \
  "http://weaviate:8080/v1/schema/Vector_index_XXXX_Node"
```

### 3. Create New Collection

```bash
docker exec docker-api-1 curl -s -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  "http://weaviate:8080/v1/schema" \
  -d '{
    "class": "Vector_index_XXXX_Node",
    "properties": [...],
    "vectorConfig": {
      "default": {
        "vectorIndexType": "hnsw",
        "vectorIndexConfig": {
          "distance": "cosine",
          "ef": -1,
          "efConstruction": 128,
          "maxConnections": 32
        },
        "vectorizer": {"none": {}}
      }
    }
  }'
```

### 4. Re-embed in Dify

Follow Step 6 above.

---

## Cleanup: Remove Orphaned Collections

After fixing, you may have orphaned collections (exist in Weaviate but deleted in Dify). To find them:

```bash
# List all Weaviate dataset IDs
docker exec docker-api-1 curl -s -H "Authorization: Bearer YOUR_API_KEY" \
  "http://weaviate:8080/v1/schema" | grep -oP 'Vector_index_[a-f0-9_]+_Node' | \
  sed 's/Vector_index_//;s/_Node//' | sed 's/_/-/g' | sort -u

# Compare with Dify database
docker exec docker-db-1 psql -U postgres -d dify -c "SELECT id, name FROM datasets ORDER BY name;"
```

Delete orphaned collections:

```bash
docker exec docker-api-1 curl -s -X DELETE \
  -H "Authorization: Bearer YOUR_API_KEY" \
  "http://weaviate:8080/v1/schema/Vector_index_ORPHANED_ID_Node"
```

---

## Troubleshooting

### Issue: Re-embedding doesn't populate Weaviate

Check if documents exist in PostgreSQL but not in Weaviate:

```bash
# Count in PostgreSQL
docker exec docker-db-1 psql -U postgres -d dify -c \
  "SELECT COUNT(*) FROM document_segments WHERE dataset_id = 'YOUR_DATASET_ID';"

# Count in Weaviate
docker exec docker-api-1 curl -s -H "Authorization: Bearer YOUR_API_KEY" \
  "http://weaviate:8080/v1/objects?class=Vector_index_XXXX_Node&limit=1"
```

If PostgreSQL has data but Weaviate doesn't, try switching embedding models as described in Step 6.

### Issue: Script can't connect to Weaviate

Make sure you're running the script inside the Docker network:

```bash
docker exec -it docker-api-1 python /tmp/batch_fix_weaviate.py scan
```

### Issue: Authentication failed

Check your API key:

```bash
docker exec docker-api-1 env | grep WEAVIATE_API_KEY
```

Update the `API_KEY` variable in the script if needed.

---

## References

- [Weaviate Named Vectors Documentation](https://weaviate.io/developers/weaviate/config-refs/schema/multi-vector)
- [Dify GitHub Repository](https://github.com/langgenius/dify)
- [Fix Script Repository](https://github.com/yupoet/dify-weaviate-fix)

---

## Credits

Script and guide by [@yupoet](https://github.com/yupoet)

If this helped you, please ⭐ the repository!

---

*Tested with Dify 1.11.0 and Weaviate 1.27.0*
