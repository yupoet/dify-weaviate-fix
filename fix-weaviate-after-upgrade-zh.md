# Dify 升级后知识库向量检索报错的修复方法（Weaviate vectorConfig 问题）

[English Version](./fix-weaviate-after-upgrade-en.md)

---

## ⚠️ 重要提示：已有官方方案

**本方案是一个简化的快速修复方法。** 官方提供了保留数据的完整迁移指南：

- 📖 [官方迁移指南 (Dify Docs)](https://docs.dify.ai/en/learn-more/faq/install-faq/weaviate-migration-guide)
- 📜 [官方迁移脚本](https://github.com/langgenius/dify-docs/blob/main/assets/migrate_weaviate_collections.py)
- 📝 [社区简化指南 (by @kurokobo)](https://gist.github.com/kurokobo/51fbe7f92f4526957e12dacfa7783cdf)

### 方案对比

| | 官方方案 | 本方案 |
|---|---|---|
| **方法** | 迁移数据（保留向量） | 重建schema + 重新嵌入 |
| **保留向量数据** | ✅ 是 | ❌ 否 |
| **适用场景** | 大型数据集、生产环境 | 小型数据集、开发测试环境 |
| **复杂度** | 较高 | 较低 |

**选择本方案的情况：**
- 知识库数量较少的小型部署
- 本来就想切换 embedding 模型
- 可以接受重新嵌入的时间/成本

---

## 问题描述

将 Dify 从旧版本（如 1.8.x、1.10.x）升级到新版本（如 1.11.0+）后，在知识库中测试召回/检索时可能遇到以下错误：

```
Query call with protocol GRPC search failed with message extract target vectors: class 
Vector_index_XXXXXXXX_XXXX_XXXX_XXXX_XXXXXXXXXXXX_Node does not have named vector default 
configured. Available named vectors map[].
```

## 根本原因

这个问题是由 **Weaviate 的 schema 格式变更** 引起的。

- **旧格式**：在顶层使用 `vectorIndexConfig`
- **新格式**：使用嵌套的 `vectorConfig.default` 配置

Dify 升级后期望使用新的 `vectorConfig` 格式，但升级前创建的知识库仍然使用旧格式。这种不匹配导致向量搜索失败。

### 旧格式（升级前）
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

### 新格式（升级后）
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

## 解决方案概述（快速修复方法）

本方案分为三个步骤：

1. **识别** 受影响的 collections（旧格式）
2. **重建** 使用新 schema 格式的 collections（数据会被清除）
3. **重新嵌入** Dify 中的文档以重新填充向量数据

> ⚠️ **重要提示**：此方法会清除向量数据，之后必须重新嵌入文档。如果需要保留向量数据，请使用[官方迁移指南](https://docs.dify.ai/en/learn-more/faq/install-faq/weaviate-migration-guide)。

---

## 详细修复步骤

### 前置条件

- 服务器 SSH 访问权限
- Docker 已安装并运行
- 基本的命令行知识

### 步骤 1：获取 Weaviate API Key

```bash
docker exec docker-api-1 env | grep -i weaviate
```

在输出中找到 `WEAVIATE_API_KEY`，修复脚本需要使用它。

### 步骤 2：扫描受影响的 Collections

```bash
# 下载修复脚本
curl -o /tmp/batch_fix_weaviate.py https://raw.githubusercontent.com/yupoet/dify-weaviate-fix/main/batch_fix_weaviate.py

# 复制到容器
docker cp /tmp/batch_fix_weaviate.py docker-api-1:/tmp/

# 运行扫描
docker exec docker-api-1 python /tmp/batch_fix_weaviate.py scan
```

这将显示：
- 找到的总 collections 数
- 新格式的 collections（正常）
- 旧格式的 collections（需要修复）

### 步骤 3：测试修复单个 Collection（推荐）

批量修复前，先测试单个 collection：

```bash
# 模拟运行（不实际修改）
docker exec docker-api-1 python /tmp/batch_fix_weaviate.py dry-run

# 修复单个 collection
docker exec -it docker-api-1 python /tmp/batch_fix_weaviate.py fix-one Vector_index_XXXX_Node
```

### 步骤 4：批量修复所有受影响的 Collections

```bash
docker exec -it docker-api-1 python /tmp/batch_fix_weaviate.py fix
```

脚本会：
1. 请求确认
2. 删除旧格式 collections
3. 使用新格式重建
4. 列出需要重新嵌入的 dataset IDs

### 步骤 5：获取知识库名称

```bash
docker exec docker-db-1 psql -U postgres -d dify -c "
SELECT id, name FROM datasets WHERE id IN (
  'dataset-id-1',
  'dataset-id-2'
) ORDER BY name;
"
```

### 步骤 6：在 Dify 中重新嵌入文档

对每个受影响的知识库：

1. 进入 Dify 知识库
2. 按名称找到知识库
3. 进入 **设置** → **Embedding 模型**
4. **切换到另一个 embedding 模型**（临时）
5. 点击 **保存** - 这会触发重新嵌入
6. **切换回** 你想用的 embedding 模型
7. 再次点击 **保存**

> 💡 **提示**：切换 embedding 模型会强制 Dify 重新嵌入所有文档。

---

## 手动修复（不使用脚本）

### 1. 检查 Collection 格式

```bash
docker exec docker-api-1 curl -s -H "Authorization: Bearer YOUR_API_KEY" \
  "http://weaviate:8080/v1/schema/Vector_index_XXXX_Node"
```

### 2. 删除旧 Collection

```bash
docker exec docker-api-1 curl -s -X DELETE \
  -H "Authorization: Bearer YOUR_API_KEY" \
  "http://weaviate:8080/v1/schema/Vector_index_XXXX_Node"
```

### 3. 创建新 Collection

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

### 4. 在 Dify 中重新嵌入

按照上面的步骤 6 操作。

---

## 清理：删除孤立的 Collections

```bash
# 列出 Weaviate 中所有 dataset IDs
docker exec docker-api-1 curl -s -H "Authorization: Bearer YOUR_API_KEY" \
  "http://weaviate:8080/v1/schema" | grep -oP 'Vector_index_[a-f0-9_]+_Node' | \
  sed 's/Vector_index_//;s/_Node//' | sed 's/_/-/g' | sort -u

# 与 Dify 数据库对比
docker exec docker-db-1 psql -U postgres -d dify -c "SELECT id, name FROM datasets ORDER BY name;"

# 删除孤立的 collections
docker exec docker-api-1 curl -s -X DELETE \
  -H "Authorization: Bearer YOUR_API_KEY" \
  "http://weaviate:8080/v1/schema/Vector_index_ORPHANED_ID_Node"
```

---

## 故障排除

### 问题：重新嵌入后 Weaviate 中没有数据

```bash
# PostgreSQL 中的数量
docker exec docker-db-1 psql -U postgres -d dify -c \
  "SELECT COUNT(*) FROM document_segments WHERE dataset_id = 'YOUR_DATASET_ID';"

# Weaviate 中的数量
docker exec docker-api-1 curl -s -H "Authorization: Bearer YOUR_API_KEY" \
  "http://weaviate:8080/v1/objects?class=Vector_index_XXXX_Node&limit=1"
```

### 问题：脚本无法连接 Weaviate

```bash
docker exec -it docker-api-1 python /tmp/batch_fix_weaviate.py scan
```

### 问题：认证失败

```bash
docker exec docker-api-1 env | grep WEAVIATE_API_KEY
```

---

## 参考资料

- [官方 Weaviate 迁移指南 (Dify Docs)](https://docs.dify.ai/en/learn-more/faq/install-faq/weaviate-migration-guide)
- [官方迁移脚本](https://github.com/langgenius/dify-docs/blob/main/assets/migrate_weaviate_collections.py)
- [社区迁移指南 by @kurokobo](https://gist.github.com/kurokobo/51fbe7f92f4526957e12dacfa7783cdf)
- [Weaviate Named Vectors 文档](https://weaviate.io/developers/weaviate/config-refs/schema/multi-vector)
- [Dify GitHub 仓库](https://github.com/langgenius/dify)

---

## 致谢

- 脚本和指南由 [@yupoet](https://github.com/yupoet) 编写
- [Dify Team](https://github.com/langgenius/dify) - 官方迁移指南
- [@kurokobo](https://github.com/kurokobo) - 社区迁移指南
- 中文 Dify 社区 - LSM 恢复方法

如果对你有帮助，请给仓库点个 ⭐！

---

*已在 Dify 1.11.0 和 Weaviate 1.27.0 上测试通过*
