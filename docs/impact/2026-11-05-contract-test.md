# 影响分析：前端类型声明与后端响应的字段一致性守卫

日期：2026-11-05

## 一、问题

`ProfileOut` 漏了 `age_years` 那次修复留下一个疑问：靠人工比对字段，下一次还会漏。

具体失效链是这样的：`profile_service.get_profile` 把 `age_years` 传给 `ProfileOut(...)`，模型里没这个字段，pydantic 默认 `extra='ignore'` 静默丢掉，响应里就没有这个键。前端 `Profile` 接口上明确写着 `age_years: number | null`，`vue-tsc` 认为它存在，运行时永远是 `undefined`。

两边的检查都是绿的：`pytest` 查的是后端自己（模型与模型比），`vue-tsc` 查的是类型声明（声明与声明比），错在两者之间，没有人在那个位置上。

这不是单点问题。`/plans`、`/assessments`、`/tracking/feedback` 这些响应由 service 直接拼 dict，字段名靠代码里写死，改一个键名不会有任何测试报警。

## 二、做法

新增 `backend/tests/contract/test_frontend_types.py`，直接读 `frontend/src/api/types.ts`，把每个 `export interface` 的顶层字段名抠出来，和 pydantic 模型比对。

解析用正则加大括号配对，不引 TypeScript 编译器：

- 去掉 `//` 行注释（文件里有中文注释）。
- `export interface Name {` 定位起点，从 `{` 开始配对，拿到 body。
- body 内按行扫，只在最外层（大括号深度为 0）抓 `key:` 或 `key?:`。嵌套对象（`ReportDetail.content`）的键属于后端拼的 dict，跳过。
- 泛型接口（`ApiEnvelope<T>`、`PageData<T>`）单列，它们没有对应的后端模型。

比对只做单向：`前端字段 - 模型字段` 必须为空。后端多给的字段前端用不上，不算问题；少给的才是。

## 三、覆盖不了的接口要显式登记

有一部分接口在 `types.ts` 里存在，但后端是 service 拼的 dict，静态没法比。这些进 `NO_MODEL`，一条一条写原因：`AssessmentSummary`、`PlanSummary`、`ReportSummary`、`Recommendation`、`KnowledgeSource`、`FeedbackRecord`、`ConsentRecord`、`EmergencyEvent`、`ExtractedDocument`、`ExtractedField`、`ConfirmationPayload`、`ReportSection`。

然后有一条 `test_every_interface_is_accounted_for` 兜住：`types.ts` 里出现的接口，只要不在 `MAPPED` 也不在 `NO_MODEL`，就红。含义是「新增一个前端接口，必须做一次决定」。反向也查：表里有、`types.ts` 里已经没有的，说明接口被改名或删了，表要跟着清。

这条规则一开始就抓到了 `ReportSection`——它是 `ReportDetail.content` 里的嵌套结构，被我漏了。

## 四、`dict` 型响应：取真实响应比键

对四个用得到的接口，起一次真实请求，拿响应里第一个元素的键去比前端声明：

- `GET /profiles/me` 对 `Profile`，顺带显式断言 `age_years` 存在（AG-04 的现场）。
- `GET /tracking/feedback` 对 `FeedbackRecord`：先 POST 一条再读，空列表会让断言变成空转，所以加了 `assert items`。
- `GET /consents` 对 `ConsentRecord`，同上。
- `GET /knowledge/sources` 对 `KnowledgeSource`，也加了非空断言——语料没导入时这条会红，比静默通过好。

## 五、顺手修掉的漂移

`types.ts` 的 `EvidenceSource` 上有 `excerpt?: string`，后端 `SourceOut` 只有 `source_id`、`title`、`version`、`page` 四个字段，风险引擎 `risk_assessment.py` 组装 `evidence_sources` 时也只放这四个。`excerpt` 从来没被赋过值，界面上也没有用它。

删掉。留着一个永远拿不到的字段，下一个人会以为后端该给。

## 测试

| 编号 | 场景 | 期望 |
|---|---|---|
| CT-01 | 每个映射过的接口 | 前端字段全部存在于模型 |
| CT-02 | `types.ts` 新增接口不登记 | 红，提示加进 `MAPPED` 或 `NO_MODEL` |
| CT-03 | 表里登记的接口已从 `types.ts` 删掉 | 红，提示清表 |
| CT-04 | 解析出的接口数量 | 大于 20，解析器被写法绊住时能发现 |
| CT-05 | `GET /profiles/me` | `age_years` 在响应里 |
| CT-06 | `GET /tracking/feedback` | 键与 `FeedbackRecord` 一致 |
| CT-07 | `GET /consents` | 键与 `ConsentRecord` 一致 |
| CT-08 | `GET /knowledge/sources` | 键与 `KnowledgeSource` 一致 |

变异验证：把 `ProfileOut.age_years` 删掉，CT-01 与 CT-05 同时红，报错直接写「Profile 声明了 ['age_years']，但 ProfileOut 没有这些字段」。复原后 30 项全绿。

## 影响面

| 范围 | 是否受影响 | 说明 |
|---|---|---|
| 接口 | 否 | 只加测试 |
| 后端运行时代码 | 否 | 无改动 |
| 前端 | 是 | `types.ts` 删掉一个从未被赋值的字段 `excerpt` |
| 测试耗时 | 是 | 新增 30 项，约 1 秒，其中 4 项起真实请求 |
| CI | 否 | 已在 `pytest` 范围内，不用改 workflow |

## 验证

- `pytest backend` 203 项通过（原 173 + 新增 30）。
- 前端 `npm test` 89 项、`vue-tsc --noEmit`、`npm run build` 通过。

## 遗留

- 只比字段名，不比类型与可选性。`string` 写成 `number`、后端可空前端非空，这类错抓不到。要比类型就得引入 TypeScript 的 AST，代价比收益大很多，暂时不做。
- 嵌套结构（`ReportDetail.content`、`Recommendation`）里的字段完全没有守卫，靠 `NO_MODEL` 里那几行字提醒。
- service 拼 dict 的路径仍然只能靠运行时用例，覆盖面取决于写了多少条。若以后 dict 响应变多，可以考虑把它们收进 `Out` 模型，那时静态比对自动生效。
