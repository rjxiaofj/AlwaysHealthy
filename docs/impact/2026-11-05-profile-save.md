# 影响分析：档案保存一直没落库，以及清不掉的字段

日期：2026-11-05

## 怎么发现的

在 `ProfileView` 里找「空值当没改」这类分支时，写了第一条用例断言 `PATCH` 之后换个请求能不能读到值。读不到。一开始以为是自己改的清空语义坏了，把改动全部回退再试，仍然读不到，说明这是改动之前就存在的。

## 缺陷一：档案保存从未提交事务

`db_session` 依赖是这样写的：

```python
async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
```

请求结束时不提交。`profile_service.patch_profile` 结尾只有 `await session.flush()`，`add_history` 也一样。`flush` 只把 SQL 发出去，事务还开着，会话关闭时被回滚。

后果是个人中心的两处写入全部无效：

| 操作 | 用户看到 | 数据库实际 |
|---|---|---|
| 保存档案 | 「档案已更新」，版本号 +1 | 一个字段都没变 |
| 添加既往史 | 「已记录」 | 没有这条记录 |

版本号也只在响应里加了一，重新加载又回到原值。刷新页面能看到旧数据，但「保存」按钮每次都提示成功，很容易被当成前端没刷新。

其他 service 都是自己 `commit()` 的（`plan_service` 13 处、`graph_service` 7 处、`auth_service` 4 处），只有 `profile_service` 全程 0 处，属于漏写而不是设计。

修法：`patch_profile` 与 `add_history` 改成 `commit()`。`add_history` 提交后实例属性会过期，补一次 `refresh` 才能读 `id`。

## 缺陷二：清空的字段清不掉

同一类问题在前端也有一份。`save()` 里是这样拼请求体的：

```ts
const lifestyle: Record<string, unknown> = {}
if (form.value.sleep_hours) lifestyle.sleep_hours = Number(form.value.sleep_hours)
```

空值直接不进请求体。后端 `patch_profile` 又是这样处理的：

```python
elif value is not None:
    setattr(profile, field, value)
```

两边合起来的效果：用户把生日、职业、睡眠时长清空后保存，请求里没有这些键（lifestyle 子键）或者带的是 null（标量字段），后端一律当作「没传」，什么都不做。

`lifestyle` 还有一层：写入是 `merged.update(value)` 合并语义，即使前端把所有子键都发出来，空值也会把老值覆盖成 `None` 而不是删掉键，风险引擎按 `snapshot.get(key) is None` 判断缺失，看着能凑合，但 JSON 里会一直留着 `"sleep_hours": null` 这种脏值。

修法：

- 后端去掉 `value is not None` 过滤，靠 `exclude_unset` 区分。显式 `null` 走清空分支。
- `lifestyle` 子键传 `null` 表示删键，没提到的子键保持。
- 前端把五个子键每次都给全，清掉的那项发 `null`。
- 空保存不递增 `profile_version`，避免版本号被无意义地推高。

## 顺带修掉的

- `save()` 里数值填了非数字（例如「一百七」）原来会 `Number()` 得到 `NaN`，序列化成 `null` 后静默清空该字段。改成抛错并提示「身高要填数字」，不再默默吃掉用户数据。
- `load()` 回填时用真值判断，`exercise_days: 0`、`sedentary_hours: 0` 会被回填成空串。抽出的 `formFromProfile` 改成只把 `null` 与 `undefined` 当没填。

## 影响面

| 范围 | 是否受影响 | 说明 |
|---|---|---|
| `PATCH /profiles/me` | 是 | null 从「忽略」变成「清空」 |
| `POST /profiles/me/histories` | 是 | 现在真的会落库 |
| 其他接口 | 否 | 无改动 |
| 历史数据 | 否 | 不涉及迁移与回填 |
| 评估与报告 | 是（正向） | 档案真正保存后，评估读到的快照才与用户填的一致 |
| 前端类型 | 是 | 新增 `ProfilePatchBody`，`profileApi.patch` 从 `Record<string, unknown>` 换成具体类型 |

## 验证

- 新增 `backend/tests/regression/test_profile_clear.py` 共 10 项：清空标量、清空生活方式子键、未传字段不动、重复清空不涨版本、真实改动涨版本、空 lifestyle 不涨版本、三个数值字段清空、既往史落库。
- 变异验证：把 `patch_profile` 的 `commit()` 改回 `flush()`，其中 4 项立刻失败（`assert None == '教师'`）。已复原。
- 前端新增 `views/profileLogic.spec.ts` 10 项。变异验证：让 `lifestyle` 只发非空子键，3 项失败。已复原。
- 全量：`pytest` 166 项通过；前端 55 项通过；`vue-tsc` 与 `build` 通过。

## 一处旧用例是靠这个 bug 才通过的

`test_nh_03_assessment_has_five_dimensions_with_sources` 开头先 `patch_profile(client, auth)`（默认身高 175、体重 88，BMI 28.7），再断言评估结果是「信息不足」。这个断言之所以成立，是因为 patch 根本没落库，档案是空的。提交修好后 BMI 28.7 被正确算成「高」，用例就红了。

现在改成不预先写档案，直接断言空档案下是「信息不足」，再写生活方式做后半段验证。原意保住了，靠的不再是一个 bug。

## 遗留

- `ensure_profile` 在只读路径（`GET /profiles/me`）上也会插入一行并 `flush`，不提交，所以新用户每读一次就白插一次。不影响正确性，没动。
- 档案里 `age_years` 与 `birth_date` 两条来路（对话里只拿到年龄时写 `age_years`），表单只编辑 `birth_date`，所以聊天里填的年龄在表单上看不到。这是产品层面的取舍，不是本轮范围。
