---
name: homeops-rendering
description: Use whenever CI/agent output needs to become glanceable artifacts — compacting flate/rendered diffs (long plain diffs → per-resource digests), rendering PR review summaries to PNG cards, or producing MP4 explainers. Triggers on "render the diff", "review image/card", "flatten this output", "evidence provider", PR-visual or video work. Covers the storage boundary (git sources vs artifacts) and the bjw-s evidence-provider pattern.
---

# Home-ops output rendering

Pipeline output is for machines; rendering is for humans (often on a phone in
Feishu). Every renderer here follows the same contract.

## Iron rules

1. **Source in git, artifacts are build outputs.** Mermaid/drawio/HTML sources
   are committed; PNG/MP4/JSON are CI-rendered deterministically. Never
   hand-edit an artifact.
2. **Renders are evidence, never the gate.** The structured verdict (review
   JSON, CI status) is the gate; a pretty picture must never carry a merge.
3. **Glanceability test before adoption.** Render 5 historical PRs; a human
   judges "image vs raw diff — which surfaces the point faster". Only then
   does a renderer join the template.

## R1 — Compact rendered diffs (flate/kustomize output is plain and long)

Raw `flate build` diffs hide what matters behind YAML noise. Compaction rules:

- Group by `namespace/kind/name`; per object show only changed field paths
  with old → new (truncate values at ~120 chars; hash long blobs).
- Unchanged objects collapse to a one-line count, never printed.
- Image tag bumps get their own section (highest-signal change class).
- Full diff is always available as a job artifact / linked file — the compact
  digest is the default view.
- Reference implementation shape (bjw-s `konflate_evidence.py`): a read-only
  script emitting the reviewer evidence contract
  `{"severity": "info", "findings": [...]}`, exiting 0 with empty findings on
  any failure — evidence providers must never block a review.

## R2 — Review summary → PNG card

The reviewer's sticky comment is markdown — unreadable on a phone. Render:

- verdict badge (approve / comment / request-changes color), finding counts by
  severity, lanes touched, one-line risk summary
- Tooling: HTML template in git → headless Chrome screenshot (deterministic).
- Publish: versitygw S3 bucket (internal; phone reaches it via tailnet) or
  GitHub Release assets (public) — pick per content sensitivity; link goes into
  the sticky comment and the Feishu card.

## R3 — Merge explainer → MP4 (optional, P4)

HyperFrames (Apache-2.0): agent writes HTML + timeline attributes, headless
Chrome + FFmpeg renders a ~30s deterministic MP4 on merge events. Narration via
the existing VoxCPM2 TTS lane. Never commit MP4s to git.

## Storage boundary

| Artifact | Home |
|---|---|
| sources (mermaid/drawio/html/templates) | git, in the PR |
| PNG (<500KB) | S3 bucket or Release assets; linked, never inlined in git |
| MP4 | Release assets or S3 only |
| evidence JSON | CI artifact + reviewer context, ephemeral |

## Reviewer reuse

The same compaction applies to the AI reviewer: evidence providers emit the
compact digest, not the raw diff (token budget + signal-to-noise). See
`.github/scripts/` for the concrete providers (P2).
