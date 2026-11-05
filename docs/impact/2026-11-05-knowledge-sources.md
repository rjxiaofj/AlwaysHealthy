# 知识来源台账影响分析

日期 2026-11-05。性质：补溯源缺口。报告里有「医学依据」章节，列的是「标题（版本）」，但出处、发布机构、发布日期、适用人群都只写在各知识文件的 YAML 头里。`knowledge_sources` 表建库时就有，字段与文件头几乎一一对应，却一行没写过。评审问一句「这条建议依据哪一版指南」，页面上答不出来。

## 改动文件

后端

- `app/tools/knowledge_base/retriever.py` 抽出 `load_document` 与 `read_metadata`，`_parse_document` 改为复用，行为不变。
- `app/repositories/knowledge.py` 新增：`all_sources`、`upsert`、`as_dict`。`upsert` 按 `source_id` 幂等，`checksum` 相同直接返回 False。
- `app/services/knowledge_service.py` 新增：`sync_sources` 把 `knowledge/*.md` 的文件头写进台账，`list_sources` 供接口用。
- `app/api/v1/endpoints/knowledge.py` 新增 `GET /knowledge/sources`，注册到 `api_router`。
- `app/main.py` 在 lifespan 里调一次 `sync_sources`，日志加 `knowledge_synced`。

前端

- `api/types.ts` 新增 `KnowledgeSource`，`api/index.ts` 新增 `knowledgeApi.sources`。
- `views/ReportDetailView.vue` 底部加可折叠的「资料来源台账」，列出标题、机构、版本、发布日期与适用人群。

测试

- `tests/api/test_knowledge_sources.py`：启动后台账条数与文件数一致、字段解析正确、重复同步不新增行、未登录 401。

## 依赖的公共方法

- `retriever.read_metadata`：新增解析入口。`_parse_document` 改为调 `load_document`，检索通道的建索引逻辑没动。
- `knowledge_repo.upsert`：启动路径唯一写入口。改动它会影响台账的幂等语义，不只是展示。

## 受影响旧模块

- 检索通道：文件读取从「一次读两遍」变成 `load_document` 返回元数据与正文，`KeywordRetriever` 与 `VectorRetriever` 的 chunk 结构不变。
- 报告生成：`agents/report.py` 仍从 `evidence_sources` 取标题与版本，不读台账，报告内容不受影响。
- 启动耗时：多一次目录扫描与 8 次按主键查询，毫秒级。
- 迁移：`knowledge_sources` 表建库时已存在，本次不加列不改类型，不需要 Alembic。

## 权限与数据范围检查

- 台账不含用户数据，也不含会话标识，接口仍需登录，与其余业务接口保持一致。
- 接口只读，不开放写入口。写只能通过启动同步，避免运行期被改成与文件不一致。
- 返回体不含 `checksum`，内部校验字段不外泄。

## 回归用例

- `tests/api/test_assessments.py` 与 `tests/unit/test_risk_engine.py`：确认检索与分级没被文件解析改动带偏。
- 报告详情与导出：确认「医学依据」章节内容不变。
- 启动路径：容器重启两次，第一次 `knowledge_synced=8`，第二次 `knowledge_synced=0`，表内仍 8 行。
