# intake 与视觉方案接口

## 唯一的需求收集入口

`new.py` 负责问题、顺序、已知值、授权状态和续填；Codex 负责显示选项与记录用户实际提交，不重复自行提问。视觉方向选项和完整方案确认属于后续设计步骤，仍在对话中进行。

顺序：用途 → 风格（七预设+自定义，三个形容词和一个参考）→ 美术完成度 → 等级 → T3 独立二次确认（仅 T3）→ 内容来源 → 素材方式 → AI 用途与明确授权（仅 AI）→ 验收标准确认。每轮最多三问；确认不能从默认值、预选或“已等待”推断。

需求表中未含主题/正文/章节，Codex 保留原始任务上下文；只有缺失的必要信息才补问。等级内交互重点从用户需求推导并放入视觉方向方案供选择，不额外重复收集已知要求。

## 三种运行方式

- `python new.py --state intake.json`：默认本地浏览器按钮向导；服务只监听 127.0.0.1，页面不联网，不发送素材。`--web --no-open --port 8765` 可手动打开；保存后 Ctrl+C 结束。界面一次一个阶段，保留已提交选择。
- `python new.py --cli --state intake.json`：没有浏览器时终端备用，编号/名称输入，不声称可以点击。
- `python new.py --questions --state intake.json --known known.json`：给 Codex 的 JSON 接口，`questions` 有稳定字段 id，`tool_questions` 直接适用于原生选项工具的 title/options。使用 `request_user_input_async` 时只展示这些题，将答复映射至对应 id；没有该工具时使用本机向导。原生工具选项数量若受限，改用向导，不丢弃七套风格。

```json
{
  "purpose": "课堂展示",
  "style": "学术",
  "tier": "T1",
  "content_source": "我搜索整理"
}
```

上述 `known.json` 仅示例；只能填写用户实际已明确的值。`true` 是 JSON 真布尔值，不接受字符串 "true"/"false"。T3 选择与二次确认需分开发生；只有用户已经在之前另次明确确认，才能预填 `t3_confirmed:true`。AI 同理必须已说明用途并明确授权。

```text
python new.py --questions --state intake.json
python new.py --questions --state intake.json --answers answers.json
```

`answers.json` 必须恰好覆盖当前轮字段。不用 `--answers` 越序伪造确认。`--known` 用于预填或用户提出的需求修改；变更需求后验收、T3/AI 相应确认和批准摘要失效。`acceptance_notes` 允许记录用户修改意见，下一轮重新确认。

可用字段：purpose、style、custom_adjectives、custom_reference、art_quality、tier、t3_confirmed、content_source、asset_mode、ai_scope、ai_authorized、acceptance_notes、acceptance_confirmed，以及仅预填的 academic_use（真布尔值，从用途上下文判断，不额外重复问）。purpose 可预填论文答辩/课程汇报/学术展示，自动映射为其他并标记学术用途；任何预设均可搭配学术用途。选择值以 `--questions` 输出为准。

向导结束仅保存 intake；不会自动搜索、生图、生成项目、批准视觉方案或发布。

## 视觉方案记录

先向用户给 2–3 个方向并让用户选定，再细化下列文件。以下仅格式说明，不是可直接冒充已确认的成品方案。

```json
{
  "directions": [
    {
      "id": "a",
      "name": "方向名称",
      "description": "一句话构图描述",
      "key_frame_differences": "与其他方向的关键画面差异",
      "suitable_for": "适用场景",
      "references": [
        {"kind": "真实项目截图", "source": "核验过的原始出处链接或本地路径", "verification": "打开出处/截图后的真实性与效果依据说明"}
      ]
    },
    {
      "id": "b",
      "name": "另一方向",
      "description": "一句话构图描述",
      "key_frame_differences": "差异",
      "suitable_for": "适用场景",
      "references": [],
      "reference_status": "暂无对标"
    }
  ],
  "selection": {"direction_id": "a", "user_selected": true, "evidence": "用户实际选定答复/时间或消息依据"},
  "screens": [
    {"name": "每一屏均列一项", "composition": "前中后景一句话构图，附窄屏安排", "foreground": "前景", "midground": "中景", "background": "背景"}
  ],
  "key_frames": [
    {"name": "关键画面一", "effect": "目标效果和可验收特征"},
    {"name": "关键画面二", "effect": "目标效果"},
    {"name": "关键画面三", "effect": "目标效果"}
  ],
  "assets": [
    {"name": "素材名", "producer": "Codex/用户/其他负责人", "method": "SVG", "size": "1200×800 或 viewBox/显示尺寸约束", "source": "依据/原创程序化/真实来源与许可"}
  ],
  "t3": {
    "camera_path": "仅 T3 必填：各章起止位置/target、路径、飞行秒数、停留/字幕、探索限制",
    "lighting_plan": "仅 T3 必填：半球/主 directional/rim、参数、雾、曝光和材质响应",
    "postprocessing": "仅 T3 必填：清单/参数/性能与窄屏降级，或明确无后处理"
  }
}
```

`directions` 恰好 2–3 个，`key_frames` 3–5 个，`screens` 覆盖所有实际章节/屏幕。暂无素材时 `assets:[]` 加 `no_assets_reason`。`method` 可用 SVG/CSS/Canvas/AI 生图/用户提供/授权真实图片；Canvas 仅 T3；AI 素材增加 `scope`（背景/贴图/装饰之一），必须在 intake 授权范围内，`source` 在规划时写待制作的生成说明，完成后记录实际来源，不在此阶段生成。

脚本检查字段完整性与申报类型，不能自动证明照片、授权和答复真实，也不能从章节草案判断所有屏幕是否覆盖。Codex 仍须打开真实来源、比对项目范围，不写虚假记录。

## 确认与构建

```text
python new.py --state intake.json --plan visual-plan.json --check-plan
```

结构检查成功给出 `intake_digest`、`plan_digest`，不生成项目。把完整方案和检查结果展示给用户，三项与本档追加项齐全才给“确认按此方案制作／提出修改意见”选项。**用户实际确认后**，将以下块加入 visual-plan.json：

```json
"approval": {
  "confirmed": true,
  "evidence": "用户实际确认答复依据",
  "intake_digest": "check-plan 输出的值",
  "plan_digest": "check-plan 输出的值"
}
```

```text
python new.py --state intake.json --plan visual-plan.json --build --output-root 项目存放目录
```

缺需求、缺方向选定、缺三项方案、缺 T3 细节、缺明确确认或摘要不匹配时不创建项目。修改方向或方案后再次展示、确认，不自动刷新 approval 来复用旧授权。通过后生成用途拼音+日期目录中的单个 index.html；按批准方案继续制作正文/素材/交互，再按 tiers.md 验收。模板/风格/等级与固定 three.js 版本仍保持原样。


## 学术用途方案追加字段

学术用途或学术预设须在 visual-plan.json 增加 `academic`，规则见 [styles.md](styles.md)：

```json
"academic": {
  "mainline": "一句话核心论点/逻辑主线，来自核验内容",
  "chapters": [
    {"name": "与 screens 对应的章节名", "contribution": "如何推进主线", "transition": "前章讲什么、本章讲什么、为什么转入；首章承接核心问题"}
  ],
  "relationships": [
    {"from": "概念一", "to": "概念二", "relation": "因果", "diagram": "有条件标注的流程图", "chapter": "放置章节名", "source": "核验过的材料/引用依据"}
  ]
}
```

chapters 必须覆盖每屏，关系清单覆盖已识别的因果/对比/递进/总分/并列关系。制作时这些内容实际显示于页面，不只存于方案；脚本检查清单存在和覆盖记录，图示语义及关系遗漏仍需人工核对。真人复述属于项目验收，脚本不会自动执行或虚构反馈。
