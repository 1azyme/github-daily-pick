# GitHub 每日 3 选

每天早上挑 3 个 GitHub 上好玩的**高星**项目，发到你手机上。

- 只在「星数高 + 还在更新 + 偏应用和好玩」的项目里挑
- 推过的项目**不会再出现**（去重记录存在 `data/history.json`）
- 避开教程、面试题、脚手架、框架源码这类「太像写作业」的项目
- 每天的项目类型尽量不重样（不会一天三个都是游戏或三个都是 AI）

推送长这样：

```
🎈 GitHub 每日 3 选
📅 9月19日 周六

1️⃣ makerspet/oomwoo
   ⭐ 11.0k · Python · 自建家庭 · 2 天前更新
   💡 看点：硬件小玩具、树莓派玩法
   📝 Open-source vacuum robot cleaner
   🔗 https://github.com/makerspet/oomwoo
...
```

---

## 最快上手：先本地看一天的效果

不需要装任何第三方库（只用 Python 标准库），也不需要配置。

```powershell
cd C:\Users\liuwenyu\Documents\ChatGPT\gameceshi\github-daily-pick
python scripts/main.py --dry-run
```

`--dry-run` 只打印今天会推什么，不推送、不记去重。觉得口味对了再往下走。

想看看每个候选为什么被选中，加 `--verbose`。

---

## 一、让手机收到提醒

推送通道可以**同时配好几个**，互相兜底：第一个失败还有第二个。
配置写在项目根目录的 `.env` 里（照着 `.env.example` 复制一份改名即可）。

| 通道 | 填什么 | 适合谁 |
| --- | --- | --- |
| **ntfy** | `NTFY_TOPIC` | 安卓 / iPhone 通用，App 免费、不用注册，最省事 |
| **Bark** | `BARK_KEY` | iPhone 用户，装完就秒到，最稳 |
| **PushPlus** | `PUSHPLUS_TOKEN` | 想直接用微信收提醒 |
| **Server酱** | `SERVERCHAN_KEY` | 微信收提醒的另一个选择 |
| **飞书 / 企业微信 / 钉钉** | `FEISHU_WEBHOOK` 等 | 想在群里留档、方便回看 |
| **Telegram** | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | 常用 Telegram 的人 |
| **邮件** | `SMTP_HOST` / `SMTP_USER` / `SMTP_PASS` / `MAIL_TO` | 想顺便存档 |

### 推荐一：ntfy（免费、不用注册）

1. 手机应用商店装 **ntfy**（安卓在应用商店 / F-Droid，iPhone 在 App Store）
2. 打开 App，点右上角 `+` 订阅一个话题，话题名**写得随机一点**，例如
   `liuwy-gh-picks-7f3a91`
3. 把话题名填进 `.env`：

   ```
   NTFY_TOPIC=liuwy-gh-picks-7f3a91
   ```

4. 跑一次 `python scripts/main.py --test-push`，手机应该在几秒内弹出通知
   （这条只发测试消息，不消耗当天的 3 个名额）

> 话题名等于密码：谁知道了都能给你发推送，所以别用 `test`、`123` 这种。
> 想更私密就自己在服务器上跑一个 ntfy，然后把 `NTFY_SERVER` 指向它。

### 推荐二：Bark（iPhone）

Bark 是 iPhone 上最省心的方案：免费、不用注册、不用登录，几分钟就能收到推送。
（安卓用不了，安卓走 ntfy 或 PushPlus。）

1. **装 App**：App Store 搜索 **Bark**（开发者 Fin，图标是个小狗爪），安装后打开
2. **允许通知**：第一次打开会问你要不要发通知，选「允许」——
   这一步拒绝了就什么都收不到，得去 iOS 设置里重新打开
3. **拿 key**：App 首页会显示一串地址，形如

   ```
   https://api.day.app/AbCdEf123xyz
   ```

   点一下可以复制。
4. **填进 `.env`**（两种填法都行，程序会自动处理）：

   ```
   BARK_KEY=https://api.day.app/AbCdEf123xyz
   ```

   或者只填后面那一段：

   ```
   BARK_KEY=AbCdEf123xyz
   ```

5. **验证**：

   ```powershell
   python scripts/main.py --test-push
   ```

   看到 `bark: ✅ 成功` 且手机弹出通知，就配好了。之后正常跑
   `python scripts/main.py` 就会推当天的 3 个项目。
6. **挂到云端**（可选）：在 GitHub 仓库的 Settings → Secrets 里加一个叫
   `BARK_KEY` 的 secret，内容同上，之后每天自动推送。

Bark 相关的小细节：

| 想要的效果 | 怎么做 |
| --- | --- |
| 提醒能穿透静音 / 专注模式 | 默认就是 `BARK_LEVEL=timeSensitive`；再在 iOS 设置里允许 Bark 发「时效性通知」 |
| 不想这么打扰 | 在 `.env` 里写 `BARK_LEVEL=active`（普通通知） |
| 用自建 Bark 服务器 | 在 `.env` 里写 `BARK_SERVER=https://你的域名` |
| 历史推送去哪看 | Bark App 里的「历史消息」列表，点条目能直接跳到 GitHub 仓库 |

> 如果 `--test-push` 报 `Bark key 不对`，就是 key 复制错了，回 App 首页重新复制一次。
> 如果 key 对但偶尔失败，多半是 `api.day.app` 这个官方服务器在境外、
> 网络抖动导致的——本程序失败时不会记去重，下次跑会重新推，可以手动再跑一次补上。

### 推荐三：PushPlus（微信）

1. 打开 [pushplus.plus](https://www.pushplus.plus/)，微信扫码登录
2. 首页能看到你的 `token`，填进 `.env`：`PUSHPLUS_TOKEN=你的token`
3. 微信里会收到「pushplus 推送加」服务号的消息

> 飞书 / 企业微信 / 钉钉三个群机器人：在群设置里添加「自定义机器人」，
> 把生成的 Webhook 地址整条填进对应变量即可（飞书和钉钉如果有签名校验，
> 再把密钥填到 `FEISHU_SECRET` / `DINGTALK_SECRET`）。

---

## 二、每天自动推（推荐：GitHub Actions）

这样**不用开着电脑**，GitHub 每天帮你在云端跑一轮。私有仓库也够用，公开仓库完全免费。

1. 在 GitHub 上新建一个仓库（比如 `github-daily-pick`），**Private 也可以**
2. 把 `github-daily-pick` 这个文件夹里的内容推上去
   （`.github/workflows/daily.yml` 要一起上传，路径别改）
3. 打开仓库 **Settings → Secrets and variables → Actions → New repository secret**，
   把上一步 `.env` 里的变量在这里逐个添加（名字要一模一样）
4. 打开 **Actions** 标签页 → 左边选「每日 GitHub 3 选」→ 右边 **Run workflow** 手动跑一次验证
   - 跑完点进那次记录，**Summary** 里能看到今天推了什么
   - 手机收到消息就说明成功了，之后每天早上 9 点自动推送

几个细节：

- **推送时间**：改 `daily.yml` 里的 `cron: "0 1 * * *"`（这是 UTC 时间，+8 小时 = 北京时间）。
  想改成早上 8 点写成 `"0 0 * * *"`。
- **不会自动停掉**：GitHub 会在仓库 60 天没有任何提交活动后暂停定时任务，而这个程序
  每天都会把去重记录提交回仓库，所以不会触发。
- **时间会有点飘**：GitHub 的定时任务高峰期可能延迟几分钟到几十分钟，属于正常现象。
- **别把 token 写进代码里**：用 Secrets，仓库设成公开也安全。
- **想补推**：手动 Run workflow 一次即可，它不会推重复的项目。

---

## 三、不想用 GitHub：挂到 Windows 任务计划

```powershell
cd github-daily-pick
powershell -ExecutionPolicy Bypass -File install_schedule.ps1
```

默认每天早上 9 点跑，想换时间：

```powershell
powershell -ExecutionPolicy Bypass -File install_schedule.ps1 -Time 21:30
```

取消：`Unregister-ScheduledTask -TaskName "GitHub每日3选"`

缺点是电脑得在那个时间开着（睡眠错过了会在开机后补跑一次）。

---

## 四、调口味（改 `config.json`）

| 参数 | 作用 |
| --- | --- |
| `count` | 每天推几个，默认 3 |
| `min_stars` / `max_stars` | 星数区间，默认 2000 ~ 150000 |
| `repeat_after_days` | 一个项目多久之后才允许再推，默认 400 天 |
| `topics` | 从哪些话题里随机挑（加话题 = 扩池子） |
| `boost_topics` | 加分话题 + 中文看点文案，**想让它更合口味就改这里** |
| `penalty_topics` | 扣分话题：越像「给工程师用的」扣得越多 |
| `block_patterns` | 直接拉黑的词：教程、面试、脚手架、后台管理…… |
| `exclude_owners` | 不想看到的作者，填 `"owner名"` |

比如你完全不想要 AI 项目：把 `boost_topics` 里的 `"ai"`、`"llm"` 那几行删掉，
再往 `penalty_topics` 里加 `"ai": 4.0`、`"llm": 4.0`。

---

## 五、它怎么挑的

候选来自三处：GitHub Trending 榜（今天 / 本周）、近期新晋高星项目（GitHub 搜索 API）、
以及从你配置的话题里随机抽的精选仓库。然后：

1. **硬性过滤**：归档、fork、没简介、星数不在区间、超过 300 天没更新、命中黑名单词，全部丢掉
2. **打分**：星数给基础分，有趣的话题加分（游戏、自建服务、硬件小玩具、创意编程……），
   工程味重的话题扣分，有官网 / 一年内新项目 / 最近还在更新再加分，最后加一点随机扰动
3. **去重与搭配**：推过的直接排除；再保证同一天的 3 个项目类型不同、作者也不同；
   最近两天推过的类型还会稍微压一压分数，避免连续几天都是同一类

---

## 六、常见问题

**没收到推送？**
先看 `data/outbox/latest.md`（最近一次生成的内容一定在这里），再看运行日志里的
`推送 xxx: 成功/失败`。失败信息一般能直接说明问题（token 错了、webhook 地址不对等）。
刚配好通道时，先用 `python scripts/main.py --test-push` 单独验证推送能不能到手机，
别等到第二天才发现没配上。

**为什么简介是英文的？**
项目简介是作者自己用英文写的，程序原样展示，不瞎翻译；中文的「看点」是根据项目话题
生成的，用来快速判断值不值得点开。

**今天推的项目不喜欢？**
点开链接看一眼就行，它不会再出现。想让某类项目少出现，改 `penalty_topics` 加大扣分。

**想手动换一批？**
`python scripts/main.py --ignore-history` 会无视去重记录重新挑（不会污染历史文件的话
就再配上 `--dry-run`）。

**需要 GitHub API 令牌吗？**
不填也能跑（候选池小一些）。填了更稳，速率限制从 10 次/分钟提到 30 次/分钟。
在 GitHub **Settings → Developer settings → Personal access tokens** 建一个
**不需要任何权限**的 token，填到 `.env` 的 `GITHUB_TOKEN=` 即可。
