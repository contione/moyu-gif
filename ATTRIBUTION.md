# 图片来源说明

## 新增批次：参考图衍生黑帽鸭鸭 12 张

- 制作日期：2026-10-14。
- 参考来源：用户提供的一张白色鸭子、黑色贝雷帽、大圆眼睛、黄色鸭嘴的表情图片。原作者及授权状态未核实，不宣称该角色为本项目原创或已获原作者商业授权。
- 用户请求基于此图制作职场表情并加入当前图库。参考原件、微信目录、账号标识等私人路径不进入公开仓库或 Pages。
- 工具：Custom ImageGen 包装器委托官方 ImageGen CLI，以 `edit` 模式逐张参考同一张图片；请求模型 `gpt-image-2`，并发数为 1。
- 提示词与逐图场景：`content/duck-office-01-prompts.json`；批次清单：`content/duck-office-01.json`；实际文件哈希与尺寸：`content/duck-office-01-generation.json`。
- 新图移除饮料品牌文字，保留鸭鸭外观，并换成职场动作和道具。模型输出静态 PNG，本地脚本添加字幕与循环动效，生成 320×320 多帧 GIF。
- 2026-10-15 字幕优化：通过本地 `caption_effects.py` 添加关键词漫画描边、弹跳、盖章、挤压及阅读停顿；没有再次调用生图模型或修改原始 PNG。静态封面选用字幕停稳的画面。
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
