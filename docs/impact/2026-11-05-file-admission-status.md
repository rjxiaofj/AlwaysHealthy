# 文件准入状态语义修正影响分析

日期 2026-11-05。性质：让已有校验可见。

`file_assets.scan_status` 从建表起固定写 `skipped`，默认值也是 `skipped`。但 `file_service.save_upload` 实际上做了三道校验：扩展名白名单、超过 10MB 拒绝、文件头签名与扩展名必须一致。校验是真的，只是结果没落库，列名又叫「扫描」，看起来像从来没检查过。

两件事一起处理：把列名改成 `admission_status`，把通过准入的文件写成 `passed`。被拒的文件本来就不入库，所以库里不该出现失败态。

## 改动文件

后端

- `app/db/models.py`：`FileAsset.scan_status` 改名为 `admission_status`，默认 `passed`，注释写明只做类型准入不做病毒扫描。
- `app/services/file_service.py`：落库时显式写 `admission_status="passed"`。

迁移

- `migrations/versions/d9b2c7e4a1f3_文件准入状态改名并回填.py`：Postgres 用 `alter_column` 改名，SQLite 走 `batch_alter_table`；两种方言都把 `server_default` 改成 `passed`，并回填历史的 `skipped` 为 `passed`。downgrade 原路退回。

测试

- `tests/api/test_document_extract.py` 新增两项：上传成功后 `admission_status` 为 `passed`；文件头不符的请求返回 400 `FILE_REJECTED` 且该用户没有任何 `file_assets` 记录。

## 依赖的公共方法

- `file_service.save_upload`：唯一的文件入口，改名后写入点也在这里。别的模块没有读这个列的，改名不影响业务逻辑。

## 受影响旧模块

- 上传与解析：行为不变，仍然先校验再写盘再解析。
- 文件列表与下载：不返回这一列，前端不用改。
- 迁移顺序：跟在指标质量状态回填之后，两条迁移都只动一列，可单独回退。

## 权限与数据范围检查

- 准入状态只由服务端写入，请求体里没有这个字段。
- 拒绝发生在写盘之前，被拒请求既不落库也不留文件。

## 回归用例

- `tests/api/test_document_extract.py` 全部 7 项。
- 容器实测：正常 PDF 落库 `passed`；伪造 PDF 返回 400 且库里无新增行。
