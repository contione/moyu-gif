# ImageGen 批次记录

## 打工猫：24 张原创替换批次

`ai-batch-01.json` 是 24 条正式表情清单；`ai-batch-01-prompts.json` 保存公共风格提示和逐图场景；`ai-batch-01-generation.json` 记录实际原画文件的尺寸与 SHA256。

本批已通过 ImageGen 官方 CLI 逐张生成真实 PNG。每张使用 `basePrompt` 与对应 `scene` 拼接，模型参数为 `gpt-image-2`、`quality=high`、`size=1024x1024`，实际返回尺寸为 1254×1254，原始文件未经缩放保存在 `assets/source/`。执行方式是先生成一张，再以 `generate-batch --concurrency 1` 顺序生成剩余 23 张。

原画不是 GIF。`scripts/replace_ai_batch.py` 复用动画生成器，加入中文字幕及循环动效，生成 GIF 与 WebP 静态封面。字体、抖动、弹跳等是本地后期处理，不宣称这些动画帧由图像模型直接绘制。

本批未使用 OpenMoji 或私人聊天图片作为参考输入。所有原画也保存在本机 `Pictures/AI` 下的唯一批次目录；密钥不在任何批次文件或仓库内容中。

## 黑帽鸭鸭：12 张参考图衍生追加批次

`duck-office-01.json` 是新表情清单，`duck-office-01-prompts.json` 保存统一外观约束与 12 个职场场景。每次 `edit` 请求均输入用户提供的同一张鸭鸭参考图，串行执行，保留黑帽、大眼睛、白身体与黄鸭嘴；参考图原件和私人路径不发布。

模型请求为 `gpt-image-2`、`high`、`1024x1024`，实际输出尺寸、模式和 SHA256 见 `duck-office-01-generation.json`。原画不冒充动图：GIF 的字幕及动画仍由本地脚本制作。原始 PNG 保持不变；含透明通道的原画在制作 GIF 时先合成白底。

在图库搜索「鸭鸭」或「职场高效」可以找到全部 12 张。本批追加而不替换猫猫，新增流程使用 `scripts/append_ai_batch.py`。有关参考图权利限制见根目录 `ATTRIBUTION.md`。

## 下一批的替换方式

为下一批准备 24 条清单，使用新的 ID 和对应的 `{id}.png`。先预检，再替换：

```powershell
rtk python scripts/replace_ai_batch.py --images-dir "C:/path/to/new-images" --manifest "content/next-batch.json" --check-only
rtk python scripts/replace_ai_batch.py --images-dir "C:/path/to/new-images" --manifest "content/next-batch.json"
```

当前批次已上线后，不要将同一清单作为“新批次”再次执行替换：脚本会拒绝复用已有 ID，防止覆盖或误删。缺少任何原图、重复 PNG、非法路径或不完整构建都会阻止切换。确认新 GIF、封面、下载 ZIP 和来源说明后，再提交推送。

网页能播放 GIF 不等于已经验证所有 Google Chat 客户端的上传行为。Chat 里的实际效果、组织权限和自定义表情入口需要在对应账号上验证。
