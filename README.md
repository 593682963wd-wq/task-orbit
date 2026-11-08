# 任务事件星环

保留完整 Canvas 星环、任务席位、演示时间线、事件接收、错误与过期状态、快照导出及响应式页面。

## 运行与验证

Python 3.11+，标准库，无运行依赖。

```sh
python3 -B -m unittest discover -s tests -v
python3 server.py
```

默认端口 8766；支持 `PORT`、`HOST`。远程部署同时设 `ALLOWED_HOSTS=服务器名:端口`。这是本地观察工具，服务没有账号认证，不应裸露到公网。

## 拆分边界

没有 Agent 账号连接、真实聊天或模型调用。外部模式仅接收调用者主动提交的事件；演示数据始终标为演示。原桌面打开功能已删除。

初始数据均为合成样例。运行后用户输入/导出属于用户自己的数据，不能随源码发布。源码采用 MIT 许可证，见 LICENSE；本目录没有携带原仓库历史。

浏览器回归（需先按上文启动服务）：`npm install --ignore-scripts`，`npx playwright install chromium`，然后设置 `TEST_URL` 为该服务地址并运行 `npm run test:browser`。浏览器使用独立无窗口上下文，截图写入 `work/`，不读取现有浏览器资料。

## 显式会话日志摘要CLI

附加 `session_status.py` 保留两种JSONL的状态分支、最近时间、计数和计划完成数；不会自动寻找会话、账号或日志，不接入旧收集器/HTTP接口。输出不含正文、摘要、标题、ID、模型、工具名、路径或参数，仅统计和固定枚举。不是实时心跳或项目验收；不自动把日志发给星环网页。

```bash
python3 session_status.py synthetic.jsonl --format codex --now 2030-01-01T00:10:00Z --fresh-seconds 180
```

`--format` 为 codex/chat；`--now` 必须显式含时区，`--fresh-seconds`为1至86400。数值事件时间默认秒，也可显式 `--timestamp-unit milliseconds`。按时间稳定排序；超过now的记录仅计入future，未识别行计入ignored，完全未知格式拒绝。最多2MiB/20000条；严格JSON重复字段与坏时间拒绝。示例可以自行写入一行 `{"timestamp":"2030-01-01T00:09:00Z","type":"event_msg","payload":{"type":"task_started"}}`。

## 2026-11-08 协作修订

- Docker默认绑定127.0.0.1；BIND_ADDRESS才显式扩大绑定，PUBLIC_ORIGIN须与实际入口一致。
- 事件输入类型和请求长度先校验，再进入状态投影。
- 无关工具的完成/取消不能结束当前活动回合。

集合根目录 `verify_release.py --project external-event-ring` 可复跑测试和包内首次使用示例；Web实际交互的浏览器证据另记。原版本测试数是历史记录，本轮以集合验证报告为准。
