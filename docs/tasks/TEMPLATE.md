# Task Card: <title>

> One card = one bounded task for an executor agent. File as a GitHub issue
> with this template. Vague wording is a defect — every field is mandatory.

## Goal

One sentence. What is true when this task is done.

## Scope files

Exact paths the executor may touch. Anything else = out of bounds.

- `path/one`
- `path/two`

## Acceptance commands

Executable shell. The task is done when these exit 0. No "looks right".

```sh
prek run -a
just k8s render-ks <ns> <ks>
```

## Forbidden

- No `kubectl apply/edit` on Flux-managed objects (drift; Flux reverts).
- No plaintext secrets; sops ciphertext only in diffs.
- No namespace/PVC/StatefulSet/CRD deletions.
- No CSI driver / StorageClass renames.
- `clusterconfig/` is generated — never hand-edit.
- Beyond AGENTS.md hard rules, nothing task-specific here.

## Rollback

One sentence: how to undo (e.g. `git revert` + reconcile, `rollout undo`).
If no clean rollback exists, say so loudly here.
