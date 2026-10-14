# 摸鱼补给站 · MOYU CLUB

**今天的班，笑着摸。** 一个无前端构建依赖、可以直接维护的搞笑 GIF 图库。

- 在线图库：https://contione.github.io/moyu-gif/
- 仓库：https://github.com/contione/moyu-gif
- 首批 24 张多帧 GIF：打工日常、情绪发疯、快乐吃瓜、社交必备。
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

## 重新制作首批表情

首批使用 **OpenMoji 开源角色和道具**，重新组合中文文案和动效，并非 AI 原创插画或从聊天记录提取的 GIF。原计划的 AI 生图在创建时因本机接口缺少凭据未能运行；没有伪装成已生成的 AI 作品。

```powershell
rtk python scripts/prepare_sheet.py
rtk python scripts/build_gifs.py --sheet "C:/Users/你的用户名/Pictures/AI/moyu-source-时间/openmoji-sheet.png"
rtk python scripts/package_site.py
```

`prepare_sheet.py` 从 OpenMoji 官方仓库下载素材，并生成 6×4 拼贴。`build_gifs.py` 针对首批 24 格素材制作 320×320、多帧循环 GIF，正文字幕保持稳定；默认使用 Windows 微软雅黑粗体。其他系统传 `--font /path/to/ChineseFont.ttf`。如果已经添加额外表情，重新生成首批时应通过 `--manifest` 指定仅含原 24 条的清单，避免将不同素材顺序混用。图库自身支持任意数量的条目。

## 部署与目录

GitHub Settings → Pages → Source 选择 **GitHub Actions**。推送 `main` 后查看 Actions 的 `Publish GIF library`；失败时日志会指出缺失图片或无效条目。

```text
index.html / styles.css / app.js   页面、样式、交互
data/gifs.json                    唯一内容清单
assets/gifs/                      动态 GIF
assets/posters/                   静态预览
assets/source/                    OpenMoji 原始素材
scripts/                         导入、生成与部署打包
.github/workflows/pages.yml       自动发布
ATTRIBUTION.md                    素材来源和授权
```

## 授权和隐私

OpenMoji 原始素材及衍生 GIF/预览图遵循 **CC BY-SA 4.0**，详见 [ATTRIBUTION.md](ATTRIBUTION.md)。公开分享与再创作请保留署名和相同许可证。项目没有分析跟踪脚本、没有服务端、没有 API 密钥；请勿将公司内部表情或含个人信息的图直接上传公开仓库。
