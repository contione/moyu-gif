# 摸鱼补给站 · MOYU CLUB

**今天的班，笑着摸。** 一个无前端构建依赖、可以直接维护的搞笑 GIF 图库。

- 在线图库：https://contione.github.io/moyu-gif/
- 仓库：https://github.com/contione/moyu-gif
- 36 张多帧 GIF：24 张原创打工猫＋12 张参考图衍生的黑帽鸭鸭。旧版 OpenMoji 拼贴表情已全部替换。
- 搜索「鸭鸭」或「职场高效」直达新批次：收到、安排、催进度、等拍板、已交付、高效下班等。
- 鸭鸭的「下载 Emoji」会提供主体放大的 128×128 英文命名 GIF（如 `duck-office-received.gif`），适合 Google Chat 自定义 emoji；网页卡片仍播放带中文字幕的完整 GIF。
- 支持中文搜索、分类筛选、本地收藏、随机抽取、预览切换、复制直链、单张与整包下载。
- 移动端双列布局；关闭动效会切换静态预览；默认尊重系统「减少动态效果」。

## 在 Google Chat 中使用

1. **复制链接**：点击卡片的「复制链接」，粘贴到聊天框并发送。复制的是 `.gif` URL，不是图片二进制；Chat 是否展开为动图由客户端与组织设置决定。
2. **下载并上传**：点击「下载」，将 `.gif` 作为图片文件上传到聊天。不要截图，截图是静态的。
3. **整包带走**：首页下载 ZIP，包含全部 GIF 和素材署名说明。

本站不连接 Google 账号，不会自动向 Chat 发送消息，也不会自动注册自定义表情。收藏保存在当前浏览器的 localStorage，清理浏览器数据会丢失收藏。

## 最简单的维护方式：在 GitHub 网页加图

1. 将有权公开发布的 GIF 上传到 `assets/gifs/`，名称使用英文小写、数字、短横线，如 `meeting-again.gif`。
2. 将它的静态预览图上传到 `assets/posters/`，支持 `.webp`、`.png`、`.jpg`。
3. 在 `data/gifs.json` 数组末尾增加一条，注意前一条与新条目之间的逗号：

```json
{
  "id": "meeting-again",
  "title": "怎么又开会",
  "category": "打工日常",
  "tags": ["开会", "无语", "打工"],
  "file": "assets/gifs/meeting-again.gif",
  "poster": "assets/posters/meeting-again.webp",
  "motion": "原始动效"
}
```

4. 将新素材的来源及授权加入 `ATTRIBUTION.md`，提交到 `main`。GitHub Actions 会校验清单、生成 ZIP、自动发布 Pages。

不需要手工修改总数或分类按钮，它们会自动从 JSON 生成。GIF 须有实际变化的多帧、最大边不超过 2048px、文件不超过 8MB；推荐 320–480px、单张小于 2MB，避免群聊加载缓慢。这些是本站限制，不是对 Google Chat 上传限制的声明。

## 本地一条命令导入

安装 Python 3.10+，在项目目录执行：

```powershell
rtk python -m pip install -r requirements.txt
rtk python scripts/add_gif.py --file "C:/path/meeting.gif" --id meeting-again --title "怎么又开会" --category "打工日常" --tags "开会,无语,打工"
```

导入器保留 GIF 动效、生成静态预览、更新清单与 ZIP，并拒绝重复 ID。素材授权仍由维护者负责。最终图片另存于当前用户 `Pictures/AI` 的唯一时间目录，再复制到项目中。之后正常提交并推送即可上线。

## 本地预览和校验

```powershell
rtk python -m http.server 4192 --bind 127.0.0.1
```

打开 `http://127.0.0.1:4192`，不要直接双击 HTML（浏览器可能禁止 file:// 读取 JSON）。

```powershell
rtk python scripts/package_site.py
```

校验每张图确实有动画、路径安全且文件存在，更新 ZIP 并输出 `_site/`。部署仅发布站点文件，不发布生成脚本和原始素材目录。

## 当前表情如何制作

每张原画通过 ImageGen 逐张生成或编辑，指定模型 `gpt-image-2`，一次只处理一张。24 张打工猫使用文字提示生成；12 张黑帽鸭鸭通过 Custom ImageGen 的 `edit` 模式参考用户提供的图片制作，不宣称鸭鸭角色为本项目原创。参考图原件和本机路径不发布到仓库。

原始 PNG 保存在 `assets/source/`；猫猫提示词和清单见 `content/ai-batch-01-prompts.json`、`content/ai-batch-01.json`；鸭鸭对应 `content/duck-office-01-prompts.json`、`content/duck-office-01.json`。两个批次的 `*-generation.json` 记录实际尺寸及 SHA256。

**原画本身是静态 PNG，不是模型直接生成的视频。** 本地脚本为每张原画添加摇头、弹跳、震动、位移、烟雾等循环动效和中文字幕，输出真正包含不同帧的 320×320 GIF；同时导出 WebP 静态封面。网站播放和下载使用 GIF，关闭动效后才使用封面。当前批次没有使用旧 OpenMoji 图片作为输入。

### 鸭鸭漫画字幕

12 张鸭鸭的关键词使用彩色填充、深色描边、白色外描边和轻阴影，按语气分别加入盖章回弹、挤压、探头、加速和等待圆点。每个 1.6 秒循环的后半段，字幕保持约 0.8 秒不动以便阅读；角色仍可继续运动。不使用整句彩虹闪烁，也不隐藏整句文字。关闭动效时显示字幕停稳后的完整封面。

样式由 `scripts/caption_effects.py` 中的 `CAPTION_STYLES` 按标题配置；未配置的标题继续使用普通黑色字幕。更新样式后，用以下命令仅重绘已有鸭鸭，不重新生图、不修改清单或原始 PNG：

```powershell
rtk python scripts/restyle_gifs.py --manifest content/duck-office-01.json --check-only
rtk python scripts/restyle_gifs.py --manifest content/duck-office-01.json
```

脚本保存旧 GIF、封面和 ZIP 的备份，在隔离目录重绘并验证全量站点，通过后才替换选中的鸭鸭素材。24 张猫猫不变，ZIP 仍包含全部 36 张。

## 整批替换下一批原创表情

1. 参考 `content/ai-batch-01.json` 制作 24 条新清单，使用全新的 ID；对应 PNG 命名为 `{id}.png`。
2. 按提示词逐张调用 ImageGen，保留实际输出并目视检查，不要用重复图片凑数。
3. 执行预检，通过后执行替换：

```powershell
rtk python scripts/replace_ai_batch.py --images-dir "C:/path/to/new-images" --manifest "content/my-next-batch.json" --check-only
rtk python scripts/replace_ai_batch.py --images-dir "C:/path/to/new-images" --manifest "content/my-next-batch.json"
```

脚本预检 24 张 PNG 的完整性、文件大小、尺寸、路径与 SHA256 去重，在隔离目录生成和校验 GIF 后才替换；随后移除旧清单引用的 GIF/封面并重建 ZIP。更新原画归档和 `ATTRIBUTION.md` 后提交推送。默认使用 Windows 微软雅黑粗体；其他系统传 `--font /path/to/ChineseFont.ttf`。

生图用的 API 凭据只在本机配置，不得写入代码、提示词、清单、提交或构建产物。GitHub Actions 仅验证与发布现成图片，不调用付费生图接口。

## 新增一批，不替换现有表情

准备同结构的清单以及 `{id}.png`，数量不限于 24 张，每个 ID 必须全新：

```powershell
rtk python scripts/append_ai_batch.py --images-dir "C:/path/to/new-images" --manifest "content/my-new-batch.json" --check-only
rtk python scripts/append_ai_batch.py --images-dir "C:/path/to/new-images" --manifest "content/my-new-batch.json"
```

脚本先在隔离目录生成并验证动画，再追加原画、GIF、封面和清单，保留现有表情，重建全量 ZIP 与站点。不要使用整批替换脚本来执行追加。参考图的来源及允许用途仍需记录在 `ATTRIBUTION.md`。

## 部署与目录

GitHub Settings → Pages → Source 选择 **GitHub Actions**。推送 `main` 后查看 Actions 的 `Publish GIF library`；失败时日志会指出缺失图片或无效条目。

```text
index.html / styles.css / app.js   页面、样式、交互
data/gifs.json                    唯一内容清单
assets/gifs/                      动态 GIF
assets/posters/                   静态预览
assets/source/                    本批 ImageGen 原始 PNG
content/                          生成提示词、批次清单与来源记录
scripts/                         导入、生成与部署打包
.github/workflows/pages.yml       自动发布
ATTRIBUTION.md                    素材来源和授权
```

## 授权和隐私

当前图片的生成来源见 [ATTRIBUTION.md](ATTRIBUTION.md)，不要将旧版 OpenMoji 的许可自动套用到新生成图上。历史版本中的 OpenMoji 素材仍应遵守其原许可证。项目没有分析跟踪脚本、没有服务端、没有 API 密钥；请勿将公司内部表情或含个人信息的图直接上传公开仓库。
