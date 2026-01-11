# Dify Weaviate Fix Tool

[English](#english) | [中文](#中文)

---

## English

### Fix Knowledge Base Vector Search After Upgrading Dify

This tool fixes the `vectorConfig` schema incompatibility issue that occurs after upgrading Dify to a newer version.

#### The Problem

After upgrading Dify, you may see this error when testing knowledge base retrieval:

```
Vector_index_xxx_Node does not have named vector default configured. Available named vectors map[].
```

This happens because older Dify versions created Weaviate collections with a different schema format (`vectorIndexConfig`) than what newer versions expect (`vectorConfig.default`).

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
| `fix-one <name>` | Fix single collection |
| `cleanup` | Remove orphaned collections |
| `list-names` | Show dataset names |

---

## 中文

### 修复 Dify 升级后知识库向量检索问题

此工具修复 Dify 升级到新版本后出现的 `vectorConfig` schema 不兼容问题。

#### 问题现象

升级 Dify 后，测试知识库检索时可能看到此错误：

```
Vector_index_xxx_Node does not have named vector default configured. Available named vectors map[].
```

这是因为旧版 Dify 创建的 Weaviate collections 使用的 schema 格式（`vectorIndexConfig`）与新版本期望的格式（`vectorConfig.default`）不同。

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
| `fix-one <name>` | 修复单个 collection |
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

If this helped you, please ⭐ the repository!
