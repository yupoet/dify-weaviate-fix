# Dify Weaviate Fix Tool

[English](#english) | [中文](#中文)

---

## ⚠️ Important Notice | 重要说明

**There is an official migration guide available!** This repository provides a **simplified quick-fix approach** that may be suitable for smaller deployments.

**已有官方迁移指南！** 本仓库提供的是一个**简化的快速修复方案**，适合小型部署。

### Official Resources | 官方资源

- 📖 [Official Migration Guide (Dify Docs)](https://docs.dify.ai/en/learn-more/faq/install-faq/weaviate-migration-guide)
- 📜 [Official Migration Script](https://github.com/langgenius/dify-docs/blob/main/assets/migrate_weaviate_collections.py)
- 📝 [Community-edited Guide (by @kurokobo)](https://gist.github.com/kurokobo/51fbe7f92f4526957e12dacfa7783cdf)

### When to Use Which? | 何时使用哪个方案？

| | Official Solution | This Solution |
|---|---|---|
| **Approach** | Migrate data (preserve vectors) | Rebuild schema + re-embed |
| **Preserves vectors** | ✅ Yes | ❌ No, requires re-embedding |
| **Best for** | Large datasets, production | Small datasets, dev/test |
| **Complexity** | Higher (LSM fix + data migration) | Lower (just schema recreation) |
| **Re-embedding cost** | None | Embedding API calls required |

| | 官方方案 | 本方案 |
|---|---|---|
| **方法** | 迁移数据（保留向量） | 重建schema + 重新嵌入 |
| **保留向量数据** | ✅ 是 | ❌ 否，需重新嵌入 |
| **适用场景** | 大型数据集、生产环境 | 小型数据集、开发测试环境 |
| **复杂度** | 较高（LSM修复 + 数据迁移） | 较低（仅重建schema） |
| **重新嵌入成本** | 无 | 需要调用 Embedding API |

**Use this solution if | 使用本方案的情况：**
- ✅ Small deployment with few knowledge bases | 知识库数量较少的小型部署
- ✅ Planning to switch embedding models anyway | 本来就想切换 embedding 模型
- ✅ Re-embedding cost is acceptable | 可以接受重新嵌入的成本
- ✅ Want a quick fix without complex migration | 想要快速修复而不做复杂迁移

**Use official solution if | 使用官方方案的情况：**
- ✅ Large datasets with many documents | 文档量大的大型部署
- ✅ Need to preserve existing vectors | 需要保留现有向量数据
- ✅ Production environment | 生产环境
- ✅ Re-embedding would take too long or cost too much | 重新嵌入耗时过长或成本过高

---

## English

### Quick Fix for Knowledge Base Vector Search After Upgrading Dify

This tool provides a **simplified approach** to fix the `vectorConfig` schema incompatibility issue after upgrading Dify. It rebuilds the schema and requires re-embedding documents.

#### The Problem

After upgrading Dify, you may see this error when testing knowledge base retrieval:

```
Vector_index_xxx_Node does not have named vector default configured. Available named vectors map[].
```

#### Quick Start

```bash
# Copy script to Dify container
docker cp batch_fix_weaviate.py docker-api-1:/tmp/

# Scan for affected collections
docker exec docker-api-1 python /tmp/batch_fix_weaviate.py scan

# Fix all affected collections
docker exec -it docker-api-1 python /tmp/batch_fix_weaviate.py fix
```

After fixing, **re-embed documents** in Dify by switching the embedding model in each affected knowledge base.

#### Documentation

- [Full Guide (English)](./fix-weaviate-after-upgrade-en.md)
- [完整指南 (中文)](./fix-weaviate-after-upgrade-zh.md)

#### Commands

| Command | Description |
|---------|-------------|
| `scan` | List collections needing fix |
| `dry-run` | Simulate fix (no changes) |
| `fix` | Fix all affected collections |
| `fix-one <n>` | Fix single collection |
| `cleanup` | Remove orphaned collections |
| `list-names` | Show dataset names |

---

## 中文

### Dify 升级后知识库向量检索问题的快速修复

此工具提供了一个**简化方案**来修复 Dify 升级后的 `vectorConfig` schema 不兼容问题。它会重建 schema 并需要重新嵌入文档。

#### 问题现象

升级 Dify 后，测试知识库检索时可能看到此错误：

```
Vector_index_xxx_Node does not have named vector default configured. Available named vectors map[].
```

#### 快速开始

```bash
# 复制脚本到 Dify 容器
docker cp batch_fix_weaviate.py docker-api-1:/tmp/

# 扫描受影响的 collections
docker exec docker-api-1 python /tmp/batch_fix_weaviate.py scan

# 修复所有受影响的 collections
docker exec -it docker-api-1 python /tmp/batch_fix_weaviate.py fix
```

修复后，需要在 Dify 中**重新嵌入文档**，方法是切换每个受影响知识库的 embedding 模型。

#### 文档

- [Full Guide (English)](./fix-weaviate-after-upgrade-en.md)
- [完整指南 (中文)](./fix-weaviate-after-upgrade-zh.md)

#### 命令说明

| 命令 | 说明 |
|------|------|
| `scan` | 列出需要修复的 collections |
| `dry-run` | 模拟修复（不实际执行） |
| `fix` | 修复所有受影响的 collections |
| `fix-one <n>` | 修复单个 collection |
| `cleanup` | 删除孤立的 collections |
| `list-names` | 显示知识库名称 |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WEAVIATE_ENDPOINT` | `http://weaviate:8080` | Weaviate URL |
| `WEAVIATE_API_KEY` | (empty) | Weaviate API key |
| `DIFY_DB_HOST` | `db` | PostgreSQL host |
| `DIFY_DB_PORT` | `5432` | PostgreSQL port |
| `DIFY_DB_USER` | `postgres` | PostgreSQL user |
| `DIFY_DB_PASSWORD` | `difyai123456` | PostgreSQL password |
| `DIFY_DB_NAME` | `dify` | PostgreSQL database |

---

## Tested With

- Dify 1.11.0
- Weaviate 1.27.0

## License

MIT

## Author

[@yupoet](https://github.com/yupoet)

## Acknowledgments | 致谢

- [Dify Team](https://github.com/langgenius/dify) - Official migration guide and script
- [@kurokobo](https://github.com/kurokobo) - Community-edited migration guide
- Chinese Dify community - LSM recovery method

If this helped you, please ⭐ the repository!
