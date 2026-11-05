# 报告导出 PDF（打印友好版）

## 问题

报告之前只能导出 Markdown（`/reports/{id}/export`），用户想留存或就诊携带时需要一份排版干净、可直接打印的文档。直接上 weasyprint/reportlab 会引入重依赖与字体渲染问题，对一个「导出」场景过重。

## 方案

打印友好版 HTML：后端把报告内容渲染成独立、样式内联、无外部资源的 HTML 页面，用户点「导出 PDF」后浏览器打开该页面并触发系统打印，用「打印 → 另存为 PDF」得到 PDF。零新增依赖，离线可用。

## 改动

- `report_service.to_print_html(report)`：把 `content.sections`（`heading`/`paragraphs`/`items`）渲染成 `<section><h2>…` 结构，标题、生成时间、`overall_level` 徽章、免责声明齐全。样式内联（`@media print` 里 `break-inside: avoid` 避免分页切断一节）。
- `report_service._escape()`：报告内容可能夹带用户输入（身体感受、计划反馈等自由文本），进 HTML 前做 HTML 转义，防止一段文字变成可执行的标签。
- 新增 `GET /reports/{report_id}/print` 端点，返回 `text/html`。
- 前端 `reportApi.printUrl`，`ReportDetailView` 加「导出 PDF」按钮：先 fetch 拿 HTML（带登录态），再 `window.open` 写入并触发 `print()`；被浏览器拦截弹出窗口时给明确提示。

保留原「导出 Markdown」入口不动。

## 验证

| 编号 | 输入 | 期望 |
|---|---|---|
| PH-01 | 内容含 `<script>`/`<b>`/`<img onerror>` | 转义后可见文本，不出现原始标签 |
| PH-02 | 完整报告 | 标题、时间、免责声明、分节、条目齐全 |
| PH-03 | 无 `overall_level` | 不渲染等级徽章 |
| PH-04 | 结构 | 有 `@media print`、`lang="zh-CN"`、`break-inside: avoid` |
| PH-05 | 条目列表 | 渲染成 `<ul><li>` |

后端 275 → 280 项。`test_tracking_report.py` 里补了 print 端点的接口断言（返回 `<!DOCTYPE html>` 且含标题）。
