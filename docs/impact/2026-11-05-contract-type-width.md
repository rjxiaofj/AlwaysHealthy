# 影响分析：契约守卫补上字段类型

日期：2026-11-05

## 为什么还要加一层

字段名对上了不代表能用。`types.ts` 写 `value: number`、后端实际给字符串，`tsc` 只看声明、`pytest` 只看自己，两边都绿；运行到模板里 `.toFixed()` 才炸，而且只在有数据的那天才炸。

原来 `tests/contract` 只比字段名与可空性，类型宽度是空的。

## 怎么比

不引 TypeScript 编译器（要 AST，代价远大于收益），而是把两边都归一化成「JS 运行时是哪类值」再比：

- 后端：`_annotation_kinds` 看 pydantic 注解 → `string` / `number` / `boolean` / `array` / `object` / `null`。`datetime`、`UUID`、`date` 序列化后都是字符串；`Literal[...]` 取成员类型；`dict` 与 `BaseModel` 都是 object；看不懂的（`Any`、没注解）给通配符，不误报。
- 前端：`_ts_kinds` 把声明按 `|` 拆开。`Foo[]`、`Array<Foo>` 是 array；`Record<...>`、`{...}` 是 object；命名的接口名（`MedicalHistory`）序列化出来也是 object；字面量联合是 string。

然后按方向比：

- **响应体**：后端给的类型必须 ⊆ 前端声明。前端写成更宽（`string | null` 装在永远有值的字段上）只是保守，不拦。
- **请求体**（`REQUEST_INTERFACES`，目前只有 `ProfilePatchBody`）：方向相反，验「前端可能发的类型，后端接得住」。后端 `dict | None` 而前端只发对象，那是正常的宽松。

## 当场抓到的问题

没有。放开之后 24 个接口全过——唯一失败的 `ProfilePatchBody.lifestyle`（后端 `dict | None`、前端 `Record<...>`）经确认是请求体方向造成的假阳性，加方向区分后通过。

这不是白写：同期的可空性检查在同一个模型上抓到过 `EvidenceSource` 三个字段。类型宽度这层现在从「没有」变成「有」，以后改字段名顺手改错类型会被拦下。

## 验证

变异两处：

1. `MetricPoint.value` 改成 `string` → `["value: 后端 ['number']，前端写的是 'string'"]`，红。
2. `ProfilePatchBody.height_cm` 改成 `string | null` → `["height_cm: 前端可能发 ['null', 'string']，后端只接 ['null', 'number']"]`，红。

另加两条钉住映射表本身的用例（`_annotation_kinds` 的 datetime/UUID/Literal/Annotated，`_ts_kinds` 的四种写法），改动映射即改动判断标准，不该悄悄发生。

后端 233 → 259 项（24 个接口各一条 + 2 条映射）。

## 仍然比不了

嵌套结构（`ReportDetail.content`、`Recommendation`）与 `NO_MODEL` 里那些 service 拼的 dict 依旧没有模型可对，只靠运行时取键 + 注释提醒。泛型接口（`ApiEnvelope<T>`、`PageData<T>`）在解析时被跳过。
