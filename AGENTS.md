# 自创教辅

蒸馏自有特色的教辅风格与 UI 语义，做成 Agent 可执行的生产框架：Agent 拿框架 + 文字素材，产出印刷级质量的教辅 PDF（A4、RGB）。

项目共识（目标、风格配方、交付物三层、验收标准）：`规范/00-项目共识.md`——做任何设计或实现决策前先读它。

## 目录角色

- `参考教辅/` — 七套参考样张（英系 ClearRevise、Oxford Revise；日系 Gakken、旺文社；中系 教材帮、试题研究、试题调研）。只读素材。
- `调研/` — 参考教辅的风格解剖报告。
- `规范/` — 框架本体：项目共识、设计令牌、内容 schema、版式映射。规范是唯一权威，CSS 与规范冲突时以规范为准、改 CSS。
- `渲染/` — Vivliostyle 安装、CSS 主题、字体（`fonts/`，仅 SIL OFL 可商用字体）。
- `样章/` — 渲染产出的 PDF。

## 渲染管线

HTML（内联 CSS）→ `渲染/node_modules/.bin/vivliostyle build <html> -o <pdf> --timeout 120` → PDF。
Agent 只产出符合内容 schema 的结构化 HTML，像素层由 CSS 主题确定性保证——不写内联样式、不发明 class。

## 分工

UI 风格与视觉裁决由项目负责人（Claude）做；调研、模板代码、排版实现由干活 Agent 执行。视觉产出每一版都要经负责人过目后才算完成。
