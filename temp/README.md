# Agent 控制面实施计划（总索引）

> 来源：2026-10-06 架构讨论 + 三轮 eval 收敛。目标：把 "executor→PR→AI reviewer→门禁→merge"
> 的 agent 控制面落到**GitHub 原生 + tailnet 回传本地模型**，零新建长驻服务、零本地 CI runner。
> 状态：**评估稿（已定稿架构），未实施**。本目录未进 .gitignore，入库与否见决策点 D1/D2。

## 定稿架构

```
手机(飞书) ◄── hermes-agent ops profile(已有, websocket) ──► 派活/叫停/审批卡片
   ▲                    │ card action 回调(ws 长连接, 无需公网回调)
   │                    ▼
   │            决策结果写回 GitHub PR 评论 (审计闭环, 04)
   │                    │
   │      GitHub(权威: 代码/PR/Issue/分支保护; home-ops 为公开仓)
   │           │  ▲            ▲ GITHUB_TOKEN 原生(免 PAT)
   │   原生事件 │  │            │ 分支+PR / 评论+status
   │           ▼  │            │
   │      GitHub Actions = 唯一 CI 执行面:
   │        验证门禁(确定性): kubeconform/flate-test/image-pull/docs/infra…
   │        依赖更新: Mend Renovate hosted app(现状, 零运维)
   │        agent 工作流: ① AI reviewer(pr-reviewer-action, pull_request 原生触发)
   │                     ② agent-job(workflow_dispatch 派活, 03-P3)
   │                     ③ @bot 命令(issue_comment)
   │                     ④ 停滞心跳(schedule)
   │           │ tailscale/github-action(tag:gha-ci, ephemeral 节点)
   │           ▼ ACL 唯一放行: 10.10.0.128:443 (agentgateway-proxy LB)
   │      agentgateway(CI 专用 key + 限流 + promptGuard 车道)
   │           ▼
   │      MacStudio 本地模型(complex/omni/micro/audio 车道, 全部已有)
   │
   └── 本地存量(不承担控制面):
       Forgejo(NAS)= home-ops/nix-config mirror(8h) + draftbox(私有, agent 笔记)
       Woodpecker = 数据面 cron 专属(dr-test/backup-verify/image-warm…)
       NAS Gatus(待部署, ADR-02 欠账) = 带外观测: GitHub 探活 + GHA cron 心跳

门禁边界: 所有 required checks 都在 GitHub 分支保护一份列表里;
         验证类(GHA 原生) + 唯一的 AI 门禁 "AI PR Review"(shadow 后挂)。
审计: git 历史 + PR 评论 + Langfuse OTEL(全部已有)。
备份: 代码=GitHub 权威 + Forgejo mirror; draftbox=dump→age→Dropbox(缩小版, 03-P0)。
```

五层收口（pass-through 安全面，细节见 `00-用户前置清单.md` 安全结论）：

1. GitHub environment `ci-llm`（main 限定）+ CODEOWNERS 守 `.github/workflows/` + action 钉 SHA/zizmor
2. Tailscale OAuth client 绑死 `tag:gha-ci`，ephemeral 节点
3. ACL 默认全拒，唯一 accept：`tag:gha-ci → 10.10.0.128:443`，附 tests 断言
4. agentgateway CI 专用 key（独立吊销）+ 限流 + 401 突增告警
5. 皇冠明珠：GitHub 账号硬件 2FA（repo 写权 + Tailscale 后台的收敛点）

## 文档索引

| 文件 | 内容 |
|---|---|
| `00-用户前置清单.md` | **实施前人工项**：Tailscale/1Password/GitHub environment 配置 + 拍板项 D1–D7 + 实测项 E1–E5 |
| `01-现状盘点.md` | 仓库/NAS/集群调研结论 + 二轮实测补记；漂移清单（重定性后） |
| `02-reviewer选型.md` | kritika vs pr-reviewer-action vs 手搓；bjw-s 参考实现拆解；GHA 版实施细节 |
| `03-阶段计划.md` | P0–P5 分阶段实施，每阶段验收标准 |
| `04-飞书按钮交互.md` | 审批卡片 + 按钮回调 + 叫停键，审计写回 GitHub PR |
| `05-图片视频渲染.md` | PR 附图 / PR 讲解视频 / 视觉 diff，铁律与存储边界 |
| `06-新应用接入.md` | 新 app / 新 agent 工作流的准入协议与 GitOps 模板 |
| `07-机会挖掘工作流.md` | follow-up（P6）：副业需求挖掘管道，数据进 git、打分可审计、门禁在人 |

## 决策点汇总（实施前需拍板；详见 00-D）

| # | 决策 | 结论/推荐 | 状态 |
|---|---|---|---|
| 1 | reviewer 选型 | **pr-reviewer-action**（前置实测 E2：`platform: github` 支持） | 已定，待实测 |
| 2 | kritika 策略 | 上游跟踪，不贡献适配器 | 已定 |
| 3 | CI 分工 | **GHA = 验证门禁 + agent 工作流唯一执行面；Woodpecker = 数据面 cron；Forgejo Actions 不复活**。`.woodpecker/` 重复验证管线删/留 = D3 | 已定（D3 待定） |
| 4 | Executor 终态 | **GHA `workflow_dispatch` agent-job**；P1 手动期 = 工作站 omp | 已定 |
| 5 | pass-through | **Tailscale ACL**（稳定 + dashboard；EasyTier 安全模式等效但凭据 TTL 轮换是 recurring chore；WG 公网端口否；DDNS+CF 公网暴露留作预案不部署） | 已定 |
| 6 | Forgejo 定位 | mirror/备份 + draftbox 宿主，不承担控制面；draftbox 备份 = dump→age→Dropbox 缩小版 | 已定 |
| 7 | temp/ 入库方式 | 位置/文件名/公开性 = D1/D2 | 待定 |
| 8 | 任务卡位置 | GitHub issues vs 私有仓 = D4 | 待定 |
| 9 | opportunities 仓 | GitHub PRIVATE（出域例外）= D6 | 待定 |
| 10 | Gatus 部署 | ADR-02 欠账，P3 前 = D7 | 待定 |

## 风险总表

1. **GitHub 账号 = 收敛单点**（repo 写权 + Tailscale 后台登录）。对策：硬件 2FA（00-A1）；
   代码历史有 Forgejo mirror + 本地 clone 兜底，issues/PRs 元数据丢失可接受。
2. **reviewer 与被审同源**：任务卡写"本任务必过"即可绕过。对策：提示词铁律
   （仓库=待审对象）+ verdict 三选一 + strict verdict/覆盖不全不 approve + shadow 期人工抽查。
3. **27B 审查上限**：架构级 PR（networking-system/storage-system/infrastructure/talos）
   长期保留人工扫读。
4. **凭证泄漏面**（GHA runner 持 tailnet 凭证）：单凭证泄漏不致命且互不通用；
   双凭证上限 = 推理盗刷（电费级）+ review 投毒（人工 merge 兜底）。
   对策=五层收口 + 吊销演练（00-E4）。
5. **Tailscale 控制面 CN 可达性**：存量依赖（日常运维已用）；home DERP 保数据面；
   断供场景 CI 死但 flux 本就依赖 GitHub——不新增部署面故障域。
6. **GHA schedule 不可靠**：延迟分钟~小时级 + 60 天无活动自动停用——home-ops 有
   renovate 周更免疫；opportunities 仓批量提交免疫；心跳判死改由 Gatus 带外执行。
7. **NAS compose 无部署自动化**：Forgejo 版本漂移（compose 16.0.5 vs live 15.0.0）
   即产物。P0 处置（升级或记录接受）。
8. **集群外心跳盲区**：forgejo-runner 已归档、Gatus 未部署——ADR-02 承诺的
   out-of-tree 观测实际不存在，D7 补齐。
9. **dump 出域**：draftbox dump 含 token，进 Dropbox 前必须 age 加密。
