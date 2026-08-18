#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
upload_douyin_cards.py —— 把「封面图 + 逐字识字卡」作为抖音图文发布
=====================================================================
基于本地已安装的 social-auto-upload（sau）工具，将 cover-text-filler 产出的
「短语封面图」+「cards/<短语>/ 下逐字卡」拼成一条抖音图文轮播，调用：

    sau douyin upload-note --account <账号> --images <封面> <卡1..卡N> \
        --title <标题> --note <正文> --tags <a,b> [--bgm <曲名>] [--schedule <时间>]

前置：
    1) 已 `cd D:/other/socials && uv pip install -e .` 安装 sau（注册到 .venv）
    2) 已 `sau douyin login --account <账号>` 扫码登录（交互式，需手动在终端跑）
    3) 已 `patchright install chromium` 装好浏览器驱动

用法：
    # 单条（dry-run，只打印命令）
    python upload_douyin_cards.py --account 我的账号 --phrase "字里千秋童梦初醒"

    # 真正发布
    python upload_douyin_cards.py --account 我的账号 --phrase "字里千秋童梦初醒" --go

    # 指定配乐（按曲名搜索，搜不到自动跳过）
    ... --bgm "琵琶语"

    # 定时发布
    ... --schedule "2026-08-16 09:00"

    # 批量发布 cards/ 下所有短语
    python upload_douyin_cards.py --account 我的账号 --all --go

    # 仅校验登录态
    python upload_douyin_cards.py --account 我的账号 --check
"""
import argparse
import json
import os
import random
import subprocess
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(HERE, ".venv", "Scripts", "python.exe")
# cover-text-filler 产物目录（封面 png 在根，逐字卡在 cards/）
DEFAULT_COVER_DIR = r"C:\Users\Administrator\.workbuddy\skills\cover-text-filler\scripts"
FONT = "mashanzheng"
NOTE_MAX = 1000  # 抖音图文正文上限（保守截断，超出警告）

# patchright 浏览器装在非默认路径（避开安全删除沙箱），运行时必须告知其位置
# 注意：Git Bash 下的 $TEMP 会解析成 /tmp，必须用绝对 Windows 路径兜底，否则找不到 Chromium
BROWSERS_PATH = os.environ.get(
    "PLAYWRIGHT_BROWSERS_PATH",
    r"C:\Users\Administrator\AppData\Local\Temp\pw-browsers",
)
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = BROWSERS_PATH
os.environ["PATCHRIGHT_BROWSERS_PATH"] = BROWSERS_PATH

# 让脚本无论从哪个目录运行都能 import 同目录的 conf.py
sys.path.insert(0, HERE)
# 预约发布配置：优先取 conf.py 中的同名变量；若本地 conf.py 未定义（如全新克隆），使用以下默认值，避免导入即崩溃。
try:  # noqa: E402
    from conf import (  # noqa: E402
        DOUYIN_NOTE_SCHEDULE_ENABLED,
        DOUYIN_NOTE_SCHEDULE_HOUR,
        DOUYIN_NOTE_SCHEDULE_MINUTE,
        DOUYIN_NOTE_SCHEDULE_DELAY_HOURS,
    )
except ImportError:
    DOUYIN_NOTE_SCHEDULE_ENABLED = False
    DOUYIN_NOTE_SCHEDULE_HOUR = 19
    DOUYIN_NOTE_SCHEDULE_MINUTE = 30
    DOUYIN_NOTE_SCHEDULE_DELAY_HOURS = 2


def load_cfg(cover_dir, phrase, json_file):
    """返回 (title, note, tags, bgm)。优先 json_file；否则在 text_done/ 或 json/ 自动找匹配短语的配置。"""
    cfg = None
    if json_file and os.path.isfile(json_file):
        with open(json_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        for sub in ("text_done", "json"):
            d = os.path.join(cover_dir, sub)
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if not fn.lower().endswith((".json", ".txt")):
                    continue
                try:
                    with open(os.path.join(d, fn), "r", encoding="utf-8") as f:
                        c = json.load(f)
                except Exception:
                    continue
                if c.get("warm_phrase") == phrase or c.get("title") == phrase:
                    cfg = c
                    break
            if cfg:
                break
    cfg = cfg or {}
    title = cfg.get("title") or phrase
    note = cfg.get("power_sentence") or cfg.get("warm_phrase") or phrase
    tags = ",".join(cfg.get("douyin_tags", []))
    bgm = cfg.get("bgm", "")
    return title, note, tags, bgm


def pick_random_bgm(pool_file):
    """从关键词池文件随机取一个非空关键词（一行一个）。文件缺失/为空则返回空串。"""
    if not os.path.isfile(pool_file):
        print(f"[警告] 未找到 BGM 关键词池：{pool_file}，本次不加配乐")
        return ""
    with open(pool_file, "r", encoding="utf-8") as f:
        words = [l.strip() for l in f if l.strip()]
    if not words:
        print(f"[警告] BGM 关键词池为空：{pool_file}，本次不加配乐")
        return ""
    return random.choice(words)


def collect_images(cover_dir, phrase, font, with_cover=False):
    """cards/<短语>/*.png（按文件名排序），可选附带封面；排除 manifest.csv 与 .MISSING.png。
    默认只发逐字卡（封面仅作封面、不进轮播）；--with-cover 时把封面作为第一张加入。"""
    imgs = []
    if with_cover:
        cover = os.path.join(cover_dir, f"{phrase}-{font}.png")
        if os.path.isfile(cover):
            imgs.append(cover)
    cards_dir = os.path.join(cover_dir, "cards", phrase)
    if os.path.isdir(cards_dir):
        for fn in sorted(os.listdir(cards_dir)):
            if not fn.lower().endswith(".png"):
                continue
            if fn.lower().endswith(".missing.png"):
                continue
            imgs.append(os.path.join(cards_dir, fn))
    return imgs


def build_cmd(account, images, title, note, tags, bgm, schedule, headless, cdp_url, cover=None, no_publish=False):
    cmd = [VENV_PYTHON, "-m", "sau_cli", "douyin", "upload-note",
           "--account", account, "--images", *images,
           "--title", title, "--note", note, "--tags", tags]
    if bgm:
        cmd += ["--bgm", bgm]
    if schedule:
        cmd += ["--schedule", schedule]
    if headless:
        cmd += ["--headless"]
    if cdp_url:
        cmd += ["--cdp-url", cdp_url]
    if cover:
        cmd += ["--cover", cover]
    if no_publish:
        cmd += ["--no-publish"]
    return cmd


def shell_quote(s):
    return f'"{s}"' if (" " in s or "\t" in s) else s


def compute_schedule(explicit):
    """解析预约发布时间，返回 'YYYY-MM-DD HH:MM' 字符串或 None（立即发布）。
    - explicit 非空：显式 --schedule 直接透传（优先级最高）；
    - 否则若 conf 开启预约：按规则计算
        · 目标 = 当天 HOUR:MINUTE（默认 19:30）
        · 若当前已超过目标，或目标距现在不足 2 小时（抖音定时发布硬性下限），
          则改为 now + DELAY_HOURS 小时（默认 2 小时）；
    - 否则返回 None（立即发布）。
    """
    if explicit:
        return explicit
    if not DOUYIN_NOTE_SCHEDULE_ENABLED:
        return None
    now = datetime.now()
    target = now.replace(
        hour=DOUYIN_NOTE_SCHEDULE_HOUR,
        minute=DOUYIN_NOTE_SCHEDULE_MINUTE,
        second=0,
        microsecond=0,
    )
    # 抖音定时发布硬性要求：发布时间须严格比当前晚 2 小时。
    # 额外留 5 分钟缓冲，避免恰好卡在 2 小时边界被服务端以
    # “定时发布时间必须大于当前时间 2 小时”拒绝。
    buffer = timedelta(minutes=5)
    min_lead = timedelta(hours=DOUYIN_NOTE_SCHEDULE_DELAY_HOURS) + buffer
    if now < target and (target - now) >= min_lead:
        sched = target
    else:
        sched = now + min_lead
    return sched.strftime("%Y-%m-%d %H:%M")


def main():
    ap = argparse.ArgumentParser(description="抖音图文发布：封面 + 逐字识字卡")
    ap.add_argument("--account", required=True, help="抖音账号名（sau 登录时的 account_name）")
    ap.add_argument("--phrase", default=None, help="短语名（对应封面 <短语>-<font>.png 与 cards/<短语>/）")
    ap.add_argument("--all", action="store_true", help="批量处理 cards/ 下所有短语")
    ap.add_argument("--cover-dir", default=DEFAULT_COVER_DIR, help="cover-text-filler 产物目录")
    ap.add_argument("--font", default=FONT, help="封面字体 key（默认 mashanzheng）")
    ap.add_argument("--json-file", default=None, help="显式指定配置 JSON（覆盖自动查找）")
    ap.add_argument("--bgm", default=None, help="配乐曲名（按名搜索，搜不到自动跳过）")
    ap.add_argument("--bgm-random", action="store_true",
                    help="从 bgm_keywords.txt 随机取一个关键词作为配乐（忽略 --bgm 与配置里的 bgm）")
    ap.add_argument("--bgm-pool", default=os.path.join(HERE, "bgm_keywords.txt"),
                    help="BGM 关键词池文件（默认 <脚本目录>/bgm_keywords.txt）")
    ap.add_argument("--schedule", default=None, help='定时发布 "YYYY-MM-DD HH:MM"')
    ap.add_argument("--headless", action="store_true", help="无头模式（后台运行）")
    ap.add_argument("--with-cover", action="store_true",
                    help="将封面图也作为轮播第一张上传（默认仅发逐字卡，封面不进轮播）")
    ap.add_argument("--cdp-url", default=None,
                    help="连接你已启动调试端口的真实 Chrome（如 http://127.0.0.1:9222），"
                         "直接驱动你的 Chrome 而非另起无头浏览器；需先以 --remote-debugging-port=9222 启动 Chrome")
    ap.add_argument("--cover", default=None,
                    help="图文独立封面图片路径(不进轮播，单独上传为封面)；不传则自动用 <短语>-<font>.png")
    ap.add_argument("--no-publish", action="store_true",
                    help="预览模式：在浏览器完成图片/标题/标签/封面/预约时间设置后，不点击「发布」仅截图核对")
    ap.add_argument("--go", action="store_true", help="真正执行；默认只打印命令(dry-run)")
    ap.add_argument("--check", action="store_true", help="仅校验登录态后退出")
    args = ap.parse_args()

    if args.check:
        if not os.path.isfile(VENV_PYTHON):
            ap.error(f"未找到 venv 解释器：{VENV_PYTHON}\n请先 `cd {HERE} && uv pip install -e .`")
        print(f"[校验] sau douyin check --account {args.account}")
        if args.go:
            subprocess.run([VENV_PYTHON, "-m", "sau_cli", "douyin", "check", "--account", args.account])
        return

    if args.go and not os.path.isfile(VENV_PYTHON):
        ap.error(f"未找到 venv 解释器：{VENV_PYTHON}\n请先 `cd {HERE} && uv pip install -e .`")

    if args.all:
        cd = os.path.join(args.cover_dir, "cards")
        if not os.path.isdir(cd):
            ap.error(f"无 cards 目录: {cd}")
        phrases = sorted(d for d in os.listdir(cd) if os.path.isdir(os.path.join(cd, d)))
    elif args.phrase:
        phrases = [args.phrase]
    else:
        ap.error("需指定 --phrase <短语> 或 --all")

    # 预约发布时间：显式 --schedule 优先；否则按 conf 配置自动计算
    schedule = compute_schedule(args.schedule)

    for phrase in phrases:
        title, note, tags, cfg_bgm = load_cfg(args.cover_dir, phrase, args.json_file)
        if args.bgm_random:
            bgm = pick_random_bgm(args.bgm_pool)
            print(f"  随机配乐关键词：{bgm or '(池为空，未加)'}")
        else:
            bgm = args.bgm or cfg_bgm
        if len(note) > NOTE_MAX:
            print(f"[警告] 正文 {len(note)} 字超过 {NOTE_MAX}，已截断")
            note = note[:NOTE_MAX]
        images = collect_images(args.cover_dir, phrase, args.font, args.with_cover)
        if not images:
            print(f"[跳过] {phrase}：未找到任何图片（封面或 cards）")
            continue
        # 独立封面(不进轮播)：优先显式指定，否则自动用海报
        cover = args.cover
        if not cover:
            candidate = os.path.join(args.cover_dir, f"{phrase}-{args.font}.png")
            if os.path.isfile(candidate):
                cover = candidate
        print(f"\n=== 短语：{phrase} ===")
        print(f"  图片({len(images)}张)：{os.path.basename(images[0])}"
              + (f" +{len(images) - 1} 张逐字卡" if len(images) > 1 else ""))
        print(f"  标题：{title}")
        print(f"  标签：{tags or '(无)'}")
        print(f"  配乐：{bgm or '(无)'}")
        if schedule:
            print(f"  预约发布：{schedule}" + (" (conf 自动计算)" if not args.schedule else " (显式 --schedule)"))
        if args.no_publish:
            print(f"  预览模式：设置完成后不点击发布（仅核对）")
        cmd = build_cmd(args.account, images, title, note, tags, bgm, schedule, args.headless, args.cdp_url, cover, args.no_publish)
        if args.go:
            print("[发布] 执行中……")
            rc = subprocess.run(cmd).returncode
            print(f"[发布] 退出码 {rc}")
        else:
            print("[dry-run] 命令如下：")
            print("  " + " ".join(shell_quote(c) for c in cmd))


if __name__ == "__main__":
    main()
