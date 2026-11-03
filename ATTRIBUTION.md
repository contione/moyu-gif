# 图片来源说明

## 2026-11-03：纯文字程序员梗 12 张

- 本批新增 12 张纯文字 GIF；加入后图库合计 56 张。既有 44 张素材及其历史批次计数保持不变。
- 本批不是 AI 生图，不含人物、参考图或外部原画。全部文字画面由本地 Pillow 字体排版和本项目 `build_text_batch.py` 生成。
- 标题主码为 `PING`、`PONG`、`402`、`404`、`500`、`503`、`200 OK`、`NULL`、`NaN`、`LGTM`、`git push`、`localhost`，每张配中文程序员梗；搜索标签包含「纯文字」「程序员」。这些代码主码只是笑话的视觉元素，中文文案不构成 HTTP、网络教程或正式释义。
- 批次清单：`content/dev-text-01.json`；制作配置：`content/dev-text-01-designs.json`；来源与文件 SHA256：`content/dev-text-01-generation.json`。
- 生成入口：`rtk python scripts/build_text_batch.py --manifest content/dev-text-01-designs.json`。每张输出 640×640 带中文字幕的大图 GIF，以及 128×128 代码主体 Emoji。
- chat 与 Emoji 输出先备份至 `Pictures/AI` 下的唯一时间目录，再复制入仓库；旧 44 张 GIF、原画、清单和来源记录不因本批次改写。

## 2026-11-03：全量大图及打工新梗 8 张

- 全部 44 张素材新增 640×640 带字幕大图和 128×128 紧凑 Emoji。仅本地裁切白边、等比例缩放和动画编码，不改变原画来源与权利状态。
- 新批次 `office-chaos-*` 复用既有打工猫、黑帽鸭鸭原画，添加不同的搞笑文案与循环动作；不是新 AI 原画，也不宣称原角色授权发生变化。
- 新梗清单及每张对应原画：`content/office-chaos-02.json`；原画和输出 SHA256：`content/office-chaos-02-generation.json`。
- 实际加工工具：Pillow 和本项目 `build_remix_batch.py`、`build_chat_assets.py`。生图工具未返回可用新原画，自定义生图脚本因缺少 API 凭据未执行生成。
- 新输出另存于本地 Pictures/AI 唯一时间目录后复制入仓库，原始 PNG 和既有完整 GIF 保留不变。


## 新增批次：参考图衍生黑帽鸭鸭 12 张

- 制作日期：2026-10-14。
- 参考来源：用户提供的一张白色鸭子、黑色贝雷帽、大圆眼睛、黄色鸭嘴的表情图片。原作者及授权状态未核实，不宣称该角色为本项目原创或已获原作者商业授权。
- 用户请求基于此图制作职场表情并加入当前图库。参考原件、微信目录、账号标识等私人路径不进入公开仓库或 Pages。
- 工具：Custom ImageGen 包装器委托官方 ImageGen CLI，以 `edit` 模式逐张参考同一张图片；请求模型 `gpt-image-2`，并发数为 1。
- 提示词与逐图场景：`content/duck-office-01-prompts.json`；批次清单：`content/duck-office-01.json`；实际文件哈希与尺寸：`content/duck-office-01-generation.json`。
- 新图移除饮料品牌文字，保留鸭鸭外观，并换成职场动作和道具。模型输出静态 PNG，本地脚本添加字幕与循环动效，生成 320×320 多帧 GIF。
- 2026-10-15 字幕优化：通过本地 `caption_effects.py` 添加关键词漫画描边、弹跳、盖章、挤压及阅读停顿；没有再次调用生图模型或修改原始 PNG。静态封面选用字幕停稳的画面。
- 2026-10-15 Google Chat Emoji 版：从现有鸭鸭 GIF 的角色区域裁切并放大到 128×128，移除字幕和画布留白，重新编码为小于 256 KB 的循环 GIF，存放于 `assets/emojis/`。这不是再次生图，原始 PNG 和完整 GIF 不变。
- 原画、动图与封面分别为 `assets/source/duck-office-*.png`、`assets/gifs/duck-office-*.gif`、`assets/posters/duck-office-*.webp`。
- 本记录不构成版权许可。再分发或商业使用前，应核实参考角色与衍生图的相关权利；如需移除，可按对应 ID 删除清单与素材后重新打包。

## 保留批次：原创打工猫 24 张

- 生成日期：2026-10-14。
- 工具：ImageGen Skill 的官方 `image_gen.py` CLI。
- 请求模型：`gpt-image-2`；逐张生成，批处理并发数为 1。
- 输入：项目编写的文字提示词，见 `content/ai-batch-01-prompts.json`；没有使用旧 OpenMoji 图片或用户私人聊天图片作为参考输入。
- 原画：`assets/source/ai-cat-*.png`，保留生图接口返回的原始文件。
- 本地加工：Pillow 裁切白边、添加中文字幕、制作循环动效、调色编码为 GIF，以及导出静态 WebP 封面。
- GIF 与封面：`assets/gifs/ai-cat-*.gif`、`assets/posters/ai-cat-*.webp`。
- 原画与动图的关系：ImageGen 生成的是静态插画，动画由本地脚本制作，不宣称模型直接输出了动态视频或 GIF。

本说明记录素材来源，不将 AI 生成图自动声明为公有领域或承诺不存在第三方权利。外部分享和商业使用时，请自行核实适用的平台条款及用途要求。

## 旧版素材

旧版使用 OpenMoji 开源表情进行拼贴。它们已从当前图库、原画目录和下载 ZIP 中移除，不与本批新图混用；Git 历史仍保留旧提交。若使用历史版本图片，原署名和 CC BY-SA 4.0 许可仍应保留：

- OpenMoji 作者：HfG Schwäbisch Gmünd 学生、教师与贡献者。
- 项目：https://openmoji.org/ ，https://github.com/hfg-gmuend/openmoji
- 许可证：https://creativecommons.org/licenses/by-sa/4.0/legalcode

新增外部图片时，请另行记录来源和授权，不要将聊天群下载的图片自动视为允许公开发布。
