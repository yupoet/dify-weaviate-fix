# How to Fix Knowledge Base Vector Search After Upgrading Dify (Weaviate vectorConfig Issue)

[中文版本](./fix-weaviate-after-upgrade-zh.md)

---

## ⚠️ Important: Official Solution Available

**This is a simplified quick-fix approach.** An official migration guide with data preservation is available:

- 📖 [Official Migration Guide (Dify Docs)](https://docs.dify.ai/en/learn-more/faq/install-faq/weaviate-migration-guide)
- 📜 [Official Migration Script](https://github.com/langgenius/dify-docs/blob/main/assets/migrate_weaviate_collections.py)
- 📝 [Community-edited Guide (by @kurokobo)](https://gist.github.com/kurokobo/51fbe7f92f4526957e12dacfa7783cdf)

### Comparison

| | Official Solution | This Solution |
|---|---|---|
| **Approach** | Migrate data (preserve vectors) | Rebuild schema + re-embed |
| **Preserves vectors** | ✅ Yes | ❌ No |
| **Best for** | Large datasets, production | Small datasets, dev/test |
| **Complexity** | Higher | Lower |

**Choose this solution if:**
- You have a small deployment with few knowledge bases
- You're planning to switch embedding models anyway
- Re-embedding cost/time is acceptable

---

## Problem Description

After upgrading Dify (e.g., from 1.8.x/1.10.x to 1.11.0+), you may encounter this error when testing knowledge base retrieval:

```
Query call with protocol GRPC search failed with message extract target vectors: class 
Vector_index_XXXXXXXX_XXXX_XXXX_XXXX_XXXXXXXXXXXX_Node does not have named vector default 
configured. Available named vectors map[].
```

## Root Cause

This is caused by a **Weaviate schema format change**. 

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

## Solution Overview (Quick Fix Approach)

This approach involves three steps:

1. **Identify** affected collections (old format)
2. **Recreate** collections with the new schema format (data is cleared)
3. **Re-embed** documents in Dify to repopulate vector data

> ⚠️ **Important**: This approach will clear vector data. You must re-embed documents afterwards. If you need to preserve vectors, use the [official migration guide](https://docs.dify.ai/en/learn-more/faq/install-faq/weaviate-migration-guide) instead.

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

> 💡 **Tip**: Switching the embedding model forces Dify to re-embed all documents.

---

## Manual Fix (Without Script)

### 1. Check Collection Format

```bash
docker exec docker-api-1 curl -s -H "Authorization: Bearer YOUR_API_KEY" \
  "http://weaviate:8080/v1/schema/Vector_index_XXXX_Node"
```

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

```bash
# List all Weaviate dataset IDs
docker exec docker-api-1 curl -s -H "Authorization: Bearer YOUR_API_KEY" \
  "http://weaviate:8080/v1/schema" | grep -oP 'Vector_index_[a-f0-9_]+_Node' | \
  sed 's/Vector_index_//;s/_Node//' | sed 's/_/-/g' | sort -u

# Compare with Dify database
docker exec docker-db-1 psql -U postgres -d dify -c "SELECT id, name FROM datasets ORDER BY name;"

# Delete orphaned collections
docker exec docker-api-1 curl -s -X DELETE \
  -H "Authorization: Bearer YOUR_API_KEY" \
  "http://weaviate:8080/v1/schema/Vector_index_ORPHANED_ID_Node"
```

---

## Troubleshooting

### Issue: Re-embedding doesn't populate Weaviate

```bash
# Count in PostgreSQL
docker exec docker-db-1 psql -U postgres -d dify -c \
  "SELECT COUNT(*) FROM document_segments WHERE dataset_id = 'YOUR_DATASET_ID';"

# Count in Weaviate
docker exec docker-api-1 curl -s -H "Authorization: Bearer YOUR_API_KEY" \
  "http://weaviate:8080/v1/objects?class=Vector_index_XXXX_Node&limit=1"
```

### Issue: Script can't connect to Weaviate

```bash
docker exec -it docker-api-1 python /tmp/batch_fix_weaviate.py scan
```

### Issue: Authentication failed

```bash
docker exec docker-api-1 env | grep WEAVIATE_API_KEY
```

---

## References

- [Official Weaviate Migration Guide (Dify Docs)](https://docs.dify.ai/en/learn-more/faq/install-faq/weaviate-migration-guide)
- [Official Migration Script](https://github.com/langgenius/dify-docs/blob/main/assets/migrate_weaviate_collections.py)
- [Community Migration Guide by @kurokobo](https://gist.github.com/kurokobo/51fbe7f92f4526957e12dacfa7783cdf)
- [Weaviate Named Vectors Documentation](https://weaviate.io/developers/weaviate/config-refs/schema/multi-vector)
- [Dify GitHub Repository](https://github.com/langgenius/dify)

---

## Credits

- Script and guide by [@yupoet](https://github.com/yupoet)
- [Dify Team](https://github.com/langgenius/dify) - Official migration guide
- [@kurokobo](https://github.com/kurokobo) - Community migration guide
- Chinese Dify community - LSM recovery method

If this helped you, please ⭐ the repository!

---

*Tested with Dify 1.11.0 and Weaviate 1.27.0*
