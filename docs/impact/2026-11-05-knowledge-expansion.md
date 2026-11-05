# 知识库扩充六篇

## 背景

知识库原来 8 篇、每篇 30 行上下，覆盖了血压、膳食、糖尿病筛检、BMI、心理、身体活动、睡眠。缺的是「筛检之后怎么办」——血脂异常怎么管、糖尿病日常怎么监测、减重怎么落地、用药怎么坚持，这些是咨询里最常被问到、又最需要循证依据的部分。

## 新增六篇

| source_id | 维度 | 内容 |
|---|---|---|
| `KB_CN_LIPID_MANAGEMENT` | metabolic | 血脂四项解读、LDL 目标分层、生活方式干预、随访 |
| `KB_CN_DIABETES_CARE` | metabolic | 血糖监测、饮食管理、运动与低血糖防范、并发症筛查 |
| `KB_CN_CARDIO_PREVENTION` | cardiovascular | 危险因素、血压血脂控制、生活方式预防、早期识别 |
| `KB_WEIGHT_LOSS_PRACTICE` | lifestyle | 能量缺口、饮食结构、行为管理、运动与防反弹 |
| `KB_SMOKING_ALCOHOL` | lifestyle | 吸烟危害、戒烟方法、酒精危害、特殊人群禁忌 |
| `KB_MEDICATION_ADHERENCE` | common | 规律服药、漏服补服、副作用复诊、药物相互作用 |

每篇保持与现有语料一致的结构：YAML front matter（`source_id`/`title`/`issuing_org`/`document_type`/`version`/`publish_date`/`dimensions`/`license_note`）+ 按 `## ` 分节。检索器按 `## ` 切 chunk，每节独立命中，所以每篇都拆成 4 个左右、内容自足的小节。

## 验证

- 检索器加载后总 chunk 从约 30 增至 48。
- 抽查五条查询（低密度脂蛋白目标、糖尿病足部护理、戒烟戒断反应、减重能量缺口、药物漏服补服）都能命中对应新语料、且排在前面。
- `test_knowledge_sources.py` 用 `glob("*.md")` 动态断言源数量，新增后自动通过（3 项全过）。
