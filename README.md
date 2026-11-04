# 自创教辅 · Textbook Framework

一个 **Agent 可执行的教辅生产框架**：Agent 拿框架 + 原始文字素材，产出印刷级质量的教辅 PDF（A4、RGB，纸屏两用）。

风格配方：**日骨 · 英皮 · 中魂** —— 日系教辅的信息密度为骨架，英系修订指南的克制美感为皮肤，中系教辅的考点组织为内容结构。

## 交付物（三层）

1. **内容语义 schema** —— 教辅内容类型的结构化定义（考点讲解、例题精讲、词汇框、易错警示、练习、答案详解等）。
2. **版式语义规范** —— 内容类型 → 版式组件映射、网格、密度规则、设计令牌。
3. **Vivliostyle 主题模板** —— 确定性渲染，Agent 不碰像素层。

## 目录

| 目录 | 内容 |
| --- | --- |
| `规范/` | 框架本体：项目共识、设计令牌、内容 schema、版式映射。**规范是唯一权威**。 |
| `调研/` | 七套参考教辅（英系 ClearRevise/Oxford Revise、日系 Gakken/旺文社、中系教材帮/试题研究/试题调研）的风格解剖报告。 |
| `渲染/` | Vivliostyle 主题（`澄页.css`）、生成脚本、样章与成品 HTML、SIL OFL 可商用字体。 |

素材目录（参考样张、OCR 语料、导出 PDF）为本地文件，未入库。

## 渲染管线

```
HTML（结构化，符合内容 schema）
  → 渲染/node_modules/.bin/vivliostyle build <html> -o <pdf> --timeout 120
  → PDF
```

Agent 只产出符合 schema 的 HTML；像素层由 CSS 主题确定性保证 —— 不写内联样式、不发明 class。

## 快速开始

```bash
cd 渲染 && npm install   # 安装 Vivliostyle
./node_modules/.bin/vivliostyle build 样章-冠词.html -o out.pdf --timeout 120
```

## 字体

`渲染/fonts/` 下全部为 SIL OFL 许可的可商用字体：STIX Two Text（英文衬线）、思源宋体/黑体（CJK）。可直接嵌入售卖物。
