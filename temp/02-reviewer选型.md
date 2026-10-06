# 02 Reviewer 选型：kritika vs pr-reviewer-action vs 手搓

## 结论

**选 misospace/pr-reviewer-action**（Forgejo 原生、MIT、已发布、本地模型优先、
有 eval harness），bjw-s 的同栈参考实现直接可适配。kritika 降为上游跟踪。
手搓出局（会重发明对方已测试覆盖的东西）。

## 三方对比

| 维度 | kritika（home-operations） | pr-reviewer-action（misospace） | 手搓 pipeline |
|---|---|---|---|
| Forgejo | ❌ GitHub-only（apps 段硬编码 GitHub Apps；无适配议题） | ✅ 原生 REST backend（sticky comment/CI status 轮询全功能；inline 锚点降级；无 GraphQL 最小化） | ✅ |
| 形态 | 长驻服务 + K8s Job + CNPG/VectorChord + dashboard | CI action 无状态（Forgejo Actions runner，job 镜像需 Node22+git，runner ≥9） | step |
| 成熟度 | 官方明示 not production ready，无 release 无升级路径 | v3.3.0，semver 纪律，dist 钉 SHA | 零依赖 |
| 许可证 | AGPL | MIT | — |
| 本地模型 | openai baseUrl 可指 agentgateway | 同左（local-first 定位） | 同左 |
| 仓库上下文 | tree-sitter + 向量索引（最强） | checkout 只读 tool loop + **evidence providers 自定义脚本** + standards 文件 | 自己写 |
| 门禁语义 | 第二模型置信分 0–5 | **findings→verdict**：仅 open blocker/major 才 request-changes；覆盖不全永不 approve；strict 模式 | 自己写 |
| 省 token | 增量复审 + settle 折叠 | diff 未变整体跳过沿用 verdict（v3 已移除增量复审） | 自己写 |
| 金标/eval | bench/ | **evals/ 语料 + harvest-human-findings 工作流**（人工 review 收获成语料） | 自己写 |
| fork 安全 | ✅ | ✅ 特权隔离工作流（默认拒绝 + label 门） | 自己写 |
| 追问 | @mention 线程 + dismiss | `/ai-review` 评论重审（triage+ 权限） | 自己写 |

## kritika 跟踪要点（若未来回迁或贡献 forge 适配器）

- 优势：向量索引上下文、增量复审、dashboard/审计日志、per-account 预算 caps、
  runner Job 不持密钥的 egress gateway 设计。
- 缺口（2026-10-06）：Forgejo 适配、OTel（issue #308）、review loop 挂 MCP（#364）。
- 适配器工程量：webhook 格式 + Gitea PR/status/comment API + auth，Go 数周级，
  且对方代码高速变动。

## bjw-s 参考实现（github.com/bjw-s/home-ops，同栈：Flux+flate+Forgejo Actions）

三个 commit（2026-10-05）恰好踩完我们必踩的坑：

1. **`3733195` 证据提供者模式**（核心资产）：
   - `.forgejo/konflate-evidence-providers.json` 注册 provider；`konflate` provider
     输出渲染后 manifest diff（raw git diff 隐藏真实变更的解药；等价物=我们
     `flux-test.yaml` 的 flate diff）。
   - 新增 380 行 `upgrade_impact_evidence.py`：diff 解析 chart/image bump →
     注入本仓库 HelmRelease values → `gh api` 拉上游 release notes →
     **新旧 chart 默认 values diff 与本仓库所设 key 求交集**（"所设 key 在新版
     默认值消失 = 静默失效"是 HelmRelease 升级最隐蔽的坑）。
   - `.agents/instructions/pr-review.instructions.md`：仓库约定调教样板。
2. **`515c62e` 门禁边界**：draft 跳过、同仓库限定、`workflow_dispatch` 支持、
   `CI_STATUS_CONTEXT` 自排除——**Forgejo 无 check-runs API，reviewer 等 CI
   会等到自己**，必须按 context 名排除自身。
3. **`bd893d6` 自排除动态化**：不硬编码 context，用 `fjo` CLI
   （perfectra1n/fjo）按 run_number 反查本 run 发布的 status context。照抄。

## P2 实施细节（钉死）

- 工作流：`.github/workflows/pr-reviewer.yaml`，**`pull_request` 原生触发**
  （GitHub 权威仓红利：轮询胶水整段删除），
  `uses: misospace/pr-reviewer-action@829f395f7154b4d87c229500fd09b30a8ad2224d`
  （v3.3.0 钉 SHA），`platform: github`【**前置实测 E2**，不支持则 fallback：
  薄 REST 包装（status+comment 两个 API 自实现 verdict 回写）或重选 GitHub 原生 action】；
  LLM 接入 = `tailscale/github-action`（钉 SHA，`tag:gha-ci` ephemeral）→
  `ai-base-url=https://api.noirprime.com/v1`（`--resolve` 到 `10.10.0.128`）
  + CI 专用 key（00-C1），`ai-model: complex`（内容含上游 release notes 等 web 文本，
  promptGuard 误杀则换 `complex-raw`）。
- 三件套适配本仓库：
  1. instructions（禁动清单）：`clusterconfig/` 生成物手改、sops 明文出现、
     CSI driver 改名、namespace/PVC/STS 删除——即 block；`targetNamespace` 由
     ks.yaml postBuild 注入（而非 `metadata.namespace`）为有意约定——不 flag。
     来源单一：从 `.omp/skills/homelab-gitops` 提炼。
  2. evidence provider ①：flate diff（照 flux-test.yaml 逻辑封装）。
  3. evidence provider ②：`upgrade_impact_evidence.py` 适配（本仓库同是
     OCIRepository+HelmRelease+renovate，近乎直接可用；`gh api` 用 GitHub
     只读 PAT，repo 已有该 1Password item）。
- 自排除：`CI_STATUS_CONTEXT` 技巧（bjw-s `bd893d6` 的 fjo 反查）**不需要**——
  GitHub 有 check-runs API，按 `GITHUB_RUN_ID` 直接排除自身 run 发布的 status。
- **前置实测（P0，见 00-E）**：`platform: github` 支持确认（E2）；`complex` 车道的
  tool-calling 能力（tool loop 硬依赖）与 constrained JSON（E3）；oMLX 上不稳则在
  金标期前定降级路径（缩小 tool 预算）。
- secrets：**原 P0-5 的 `review_token`/`executor_token` PAT 取消**——认证用
  `GITHUB_TOKEN` 原生（`contents:read` + `pull-requests:write` + `statuses:write`，
  每 run 自动下发自动吊销）。新增秘密仅 tailscale OAuth client + CI key（见 00-B/C），
  入 environment `ci-llm`（main 限定）。

## 验证协议（不变，适用于任何选型）

1. **金标集 A/B**：P1 的 3 个真实 PR + 历史 PR 回放（用 action 自带 eval harness），
   与人工判定一致率 ≥90%，block 零误杀。
2. **Shadow 两周**：只评论不门禁；盯 block 误杀率（>10% 降阈值/改提示词）与漏杀
   （人工抽查 diff）。
3. **挂门禁**：过线后把 `AI PR Review` 挂进分支保护 required checks——
   全系统唯一 AI 硬闸门。架构级 PR（networking/storage/talos）长期保留人工扫读。
