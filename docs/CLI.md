# CLI 使用说明

项目现在提供一个统一的 CLI 入口 `sau`，当前主线已经接入：

- `douyin`
- `kuaishou`
- `xiaohongshu`
- `bilibili`

实现说明：

- `sau_cli.py` 是当前 CLI 的主入口和唯一主要实现文件
- `sau.exe` 是安装后在 Windows 虚拟环境里自动生成的命令入口，本质上还是调用 `sau_cli.py`
- 如果需要给 OpenClaw、Codex 等 agent 使用，可参考仓库内 skill：
  - `skills/douyin-upload/`
  - `skills/kuaishou-upload/`
  - `skills/xiaohongshu-upload/`
  - `skills/bilibili-upload/`

## 安装 CLI 入口

如果你希望直接使用 `sau` 命令，而不是手动执行 `python sau_cli.py`，先在项目根目录安装一次：

```bash
uv pip install -e .
```

安装后就可以直接使用：

```bash
sau douyin --help
sau kuaishou --help
sau xiaohongshu --help
sau bilibili --help
```

## 安装 patchright 浏览器

Windows 下推荐先指定镜像，再安装 Chromium：

```powershell
$env:PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright"; patchright install chromium
```

## 抖音 CLI 子命令

```bash
sau douyin login --account <account_name>
sau douyin login --account <account_name> --headless
sau douyin check --account <account_name>
sau douyin upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tags 运动,训练
sau douyin upload-note --account <account_name> --images videos/1.png videos/2.png --title "图文标题" --note "图文示例" --tags 图文,测试
```

抖音短信验证码补充说明：

- 视频发布过程中如果触发短信二次验证，CLI 会优先读取项目根目录下的 `verify_code.txt`
- 如果未找到 `verify_code.txt`，并且当前命令是在交互式终端中手动运行，CLI 会直接在终端提示输入验证码
- 对 agent、自动任务、远程桥接这类场景，仍然可以继续用写入 `verify_code.txt` 的方式喂验证码
- 验证通过后，程序会自动清理 `verify_code.txt`

## 快手 CLI 子命令

```bash
sau kuaishou login --account <account_name>
sau kuaishou check --account <account_name>
sau kuaishou upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tags 运动,训练
sau kuaishou upload-note --account <account_name> --images videos/1.png videos/2.png videos/3.png --title "图文标题" --note "图文示例" --tags 图文,测试
```

快手图文（`upload-note`）已与抖音图文能力对齐，额外支持以下增强参数（视频 `upload-video` 也支持 `--cdp-url` / `--no-publish`）：

```bash
# 快手图文：配乐 + 预约 + CDP 直连 + 预览模式
sau kuaishou upload-note --account <account_name> \
    --images videos/1.png videos/2.png videos/3.png \
    --title "图文标题" --note "图文示例" --tags 图文,测试 \
    --bgm "琵琶语" --schedule "2026-08-18 21:30" \
    --cdp-url http://127.0.0.1:9222 --no-publish

# 快手视频：CDP 直连 + 预览模式
sau kuaishou upload-video --account <account_name> --file videos/demo.mp4 \
    --title "示例标题" --desc "示例简介" --tags 运动,训练 \
    --cdp-url http://127.0.0.1:9222 --no-publish
```

- `--bgm <曲名>`：按名搜索并选配乐（搜不到/未命中入口自动跳过，不中断发布）。
- `--cdp-url <url>`：连接你已开启调试端口的真实 Chrome，复用已登录会话、避免另起无头浏览器（需先 `--remote-debugging-port=9222` 启动 Chrome）。
- `--cover <图片>`：图文封面；快手封面只能从已上传图片中选取，故按文件名匹配已上传图（外部独立封面为抖音特性）。
- `--no-publish`：预览模式，完成所有设置后**不点发布**，截图 `progress_preview.png` 并回读预约时间，保持浏览器打开等你手动关闭核对。

完整工作流、参数对照表与注意事项见 **[`kuaishou-upload-guide.md`](./kuaishou-upload-guide.md)**。

## 小红书 CLI 子命令

```bash
sau xiaohongshu login --account <account_name>
sau xiaohongshu check --account <account_name>
sau xiaohongshu upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tags 小红书,视频
sau xiaohongshu upload-note --account <account_name> --images videos/1.png videos/2.png videos/3.png --title "图文标题" --note "图文示例" --tags 图文,测试
```

海外环境如果无法登录默认创作者后台，可以通过环境变量切换到 RedNote 域名。该设置同时作用于登录、cookie 校验、视频发布和图文发布：

```bash
SAU_XHS_CREATOR_BASE_URL=https://creator.rednote.com sau xiaohongshu login --account <account_name>
```

## Bilibili CLI 子命令

```bash
sau bilibili login --account <account_name>
sau bilibili check --account <account_name>
sau bilibili upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tid 249 --tags 足球,测试 --thumbnail covers/demo.png
```

补充说明：

- `creator` 之类的名字只是示例值，真正传的是用户自定义的 `account_name`
- 一个 `account_name` 对应一个账号文件，可以准备多个账号并发使用
- 浏览器平台统一元数据约定：
- 视频使用 `title + desc + tags`
- 图文使用 `title + note + tags`
- `sau bilibili ...` 会自动准备 `biliup`
- 如果本地没有 `biliup`，第一次运行会自动下载
- 如果上游 GitHub Release 有更新，运行时会先自动更新
- `sau bilibili login --account <name>` 建议由用户自己在本地真实终端里执行；如果终端里的二维码显示不完整，可直接打开当前目录下的 `qrcode.png` 扫码

## 登录二维码说明

- 抖音、快手、小红书登录过程中，CLI / uploader 可能会生成临时二维码图片
- 对普通用户来说，可以直接打开该图片扫码
- 对可操作本地文件的 agent 来说，不要只把图片路径告诉用户
- 这类二维码图片本身就是给用户扫码的，agent 应优先直接展示/发送本地图片给用户
- Bilibili 当前不走这套本地二维码图片托管链路，登录按上面的 Bilibili CLI 说明处理即可

## 定时发布

抖音、快手、小红书的图文和视频上传，以及 Bilibili 的视频上传都支持 `--schedule`。只要传了 `--schedule`，CLI 就会自动切换到对应平台的定时发布策略；不传则默认立即发布。

```bash
sau douyin upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --schedule "2026-03-24 21:30"
sau douyin upload-note --account <account_name> --images videos/1.png videos/2.png --title "图文标题" --note "图文示例" --schedule "2026-03-24 21:30"
sau kuaishou upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --schedule "2026-03-24 21:30"
sau kuaishou upload-note --account <account_name> --images videos/1.png videos/2.png videos/3.png --title "图文标题" --note "图文示例" --schedule "2026-03-24 21:30"
sau xiaohongshu upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --schedule "2026-03-24 21:30"
sau xiaohongshu upload-note --account <account_name> --images videos/1.png videos/2.png videos/3.png --title "图文标题" --note "图文示例" --schedule "2026-03-24 21:30"
sau bilibili upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tid 249 --schedule "2026-03-24 21:30"
```

## 运行时参数

CLI 将 `debug` 和 `headless` 拆成了两个独立维度：

```bash
--debug
--headless
--headed
```

- `--debug`: 打开调试行为，例如失败时保留更多调试信息
- `--headless`: 无头模式运行
- `--headed`: 有头模式运行

如果都不传，CLI 当前默认按 `headless=True` 运行。

补充：

- 抖音和快手的 CLI 默认都是无头模式
- 如果用户明确要求可见浏览器窗口，或确实需要人工看页面，再显式传 `--headed`

## 视频上传参数

```bash
--file videos/demo.mp4
--title "示例标题"
--desc "示例简介"
--tags 运动,训练
--thumbnail videos/demo.png
--thumbnail-landscape videos/cover-4x3.png
--thumbnail-portrait videos/cover-3x4.png
```

抖音和视频号支持同时设置两种比例的封面图：

- `--thumbnail-landscape`: 4:3 横版封面
- `--thumbnail-portrait`: 3:4 竖版封面
- `--thumbnail`: 兼容旧参数，等同于 3:4 竖版封面

抖音额外支持：

```bash
--product-link https://example.com/item
--product-title 示例商品
```

Bilibili 额外要求：

```bash
--tid 249
```

- `--tid` 第一版是必填
- `--tags` 会映射到 `biliup upload --tag`
- `--schedule` 会映射到 Bilibili 所需的时间戳参数

## 图文上传参数

```bash
--images videos/1.png videos/2.png videos/3.png
--title "图文标题"
--note "图文内容"
--tags 图文,测试
```

图文上传当前限制：

- 抖音：最多 35 张图片，不支持 GIF
- 快手：支持多张图片，建议传真实不同文件，不要把同一路径重复多次
- 小红书：支持多张图片，正文 `--note` 可选，但 `--title` 建议始终显式传入

## 增强参数（抖音 / 快手 图文）

抖音与快手的图文上传（`upload-note`）均支持以下增强参数，用于对齐「复用已登录浏览器 + 预览核对」的工作流：

```bash
--bgm <曲名>          按名搜索并选配乐（搜不到/未命中入口自动跳过，不中断发布）
--cdp-url <url>       连接已开启调试端口的真实 Chrome（如 http://127.0.0.1:9222），
                      复用已登录会话、避免另起无头浏览器触发登录/短信验证；
                      需先以 --remote-debugging-port=9222 启动 Chrome
--cover <图片>        图文独立封面；抖音可直接上传外部文件，快手只能从已上传图片中选取
--no-publish          预览模式：完成图片/标题/标签/配乐/封面/预约设置后不点「发布」，
                      仅截图 progress_preview.png 并回读预约时间，保持浏览器打开等你手动关闭
```

完整工作流、参数对照表与注意事项见 **[`kuaishou-upload-guide.md`](./kuaishou-upload-guide.md)**。

后续维护 CLI 时，优先看 `sau_cli.py`、`uploader/` 和 `skills/`。
