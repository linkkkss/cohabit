# 01 · Cohabit 概念站（包豪斯方向）

> 一份独立的 UI 概念方案：不修改 `0.cohabit/frontend` 的业务代码，按新的视觉规范重新实现首页、广场、今日匹配、我的画像四页；用于和现有 Hinge NFAQ 风格做对照。

- **在线预览**：<https://subscriptions-silent-seed-movies.trycloudflare.com>（临时隧道）
- **可运行代码**：本仓库 `ui-concept/`（Vue 3 + Vite + TypeScript，`npm install && npm run dev`）
- **完整规范**：[design.md](design.md) · [design.pdf](design.pdf) · [design.html](design.html)
- **效果图**：[assets/](assets/)

## 一句话

米白纸面 + 炭黑墨线 + 爱马仕橙，用包豪斯的硬边几何（2px 描边、硬投影、网格纸底）讲一个关于「边界」的温和产品。

## 四页

| 页面 | 路径 | 关键点 |
| --- | --- | --- |
| 首页 | `/` | 入场标题卡（滚动展开）+ 磁吸 CTA + 画像卡示例 + 三步流程 + 深色收尾 |
| 广场 | `/plaza` | 深色琥珀舞台上的圆形旋转木马：正面奶油、左侧炭黑、右侧橙色；右侧详情面板 |
| 今日匹配 | `/match` | 左侧「你」的画像卡 + 中间匹配环 + 右侧可拖拽的物理吊牌（SwingTag） |
| 我的画像 | `/profile` | 身份卡（低亮度聚光灯）+ 完成度环 + 六维条 + 公开/私密内容与可见性开关 |

## 交互组件

磁吸按钮、药丸导航、扫光文字、滚动浮现、圆形旋转木马、个人信息卡片移植/改编自 [React Bits](https://reactbits.dev)（MIT），在 `ui-concept/src/components/` 下改写为 Vue 3 并按本规范重绘；物理吊牌只借鉴其「悬挂 + 拖拽 + 回摆」概念，用 CSS + 弹簧摆实现，未使用 three.js。详见 [design.md 第 10 节](design.md#10-组件来源--react-bits)。

## 与现有站点的关系

- 不改动 `0.cohabit/frontend/` 的任何文件
- 设计 token 独立（`ui-concept/src/styles/main.css`），不污染现有样式
- 若后续要合并，建议先对齐 token 与组件边界，再逐页迁移，而不是整站替换
