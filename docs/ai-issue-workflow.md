# AI Issue 自動対応ワークフロー

このリポジトリでは、外部から届く Issue の一次対応コストを下げるために、`anthropics/claude-code-action` を中核とした GitHub Actions ベースのワークフローを導入しています。本ドキュメントでは、その全体像と運用方法を記載します。

## 概要

人間（メンテナ）の判断ポイントは「実装するか／しないか」のラベル付けのみに絞り、トリアージ・不足情報の問い返し・実装・wontfix 時の返信は自動化しています。

```
Issue 作成
    ↓
[claude-issue-triage] ──→ needs-info / triaged / out-of-scope
                                   ↓
                           （メンテナがラベル付与）
                                   ↓
                       ai-implement ─→ [implement] ─→ PR
                       wontfix      ─→ [wontfix]   ─→ クローズ
```

### 1. トリアージフェーズ (`claude-issue-triage.yml`)

`issues.opened` をトリガーに発火します。Claude が Issue 内容を読み、以下のいずれかに振り分けます。

- **`needs-info`**: 再現手順・期待動作・実環境情報などが不足している場合。報告者の言語に合わせて、不足項目を箇条書きで質問するコメントを投稿します。
- **`triaged`**: 内容が十分にクリアな場合。3-5 行の要約コメントを投稿し、メンテナが素早く把握できる状態にします。
- **`out-of-scope`**: Streamlit 本体・aiortc・PyAV など別プロジェクトに属する問題、もしくは GitHub Discussions が適切なサポート質問の場合。誘導コメントを投稿します。

ボット由来の Issue は `github.event.issue.user.type != 'Bot'` で除外しています。

### 2. ラベル駆動の実装フェーズ (`claude-issue-implement.yml`)

`issues.labeled` をトリガーに発火し、ラベル名で分岐します。

- **`ai-implement`**: メンテナが「実装してよい」と判断した Issue。Claude が実装ブランチ (`claude/issue-<番号>`) を作成し、テスト・リンタ・changelog fragment 追加まで行ってから PR を作成します。
- **`wontfix`**: メンテナが「対応しない」と判断した Issue。Claude が理由を丁寧に説明し、代替策を提案するコメントを投稿してから Issue をクローズします。

外部からの PR レビューは既存の AI レビューボットで運用しているため、本ワークフローのスコープ外です。

## 初期セットアップ

### 1. Anthropic API Key の登録

GitHub リポジトリの設定で API Key を Secrets に登録します。

1. リポジトリの **Settings → Secrets and variables → Actions** を開く
2. **New repository secret** をクリック
3. Name に `ANTHROPIC_API_KEY`、Value に Anthropic コンソールで発行した API Key を入力して保存

### 2. ラベルの作成

ワークフローで使うラベルを冪等に作成するスクリプトを用意しています。

```bash
bash scripts/setup-issue-labels.sh
```

作成されるラベル:

| name           | 用途 |
| -------------- | ---- |
| `needs-info`   | 報告者からの追加情報待ち（Claude が自動付与） |
| `triaged`      | トリアージ済み・対応待ち（Claude が自動付与） |
| `out-of-scope` | このプロジェクトのスコープ外 |
| `ai-implement` | Claude による実装を依頼（メンテナが手動付与） |
| `wontfix`      | 対応しない（メンテナが手動付与） |

### 3. Actions の権限設定

`ai-implement` ジョブが PR を作成できるように、以下を確認してください。

- **Settings → Actions → General → Workflow permissions**
  - 「Read and write permissions」が選択されていること
  - 「Allow GitHub Actions to create and approve pull requests」にチェックが入っていること

## 運用ガイド

### 導入直後の運用

最初の 2 週間は **`ai-implement` で生成された PR も必ず人間レビューを通す** こと。Claude の判断や実装パターンが想定通りか観察し、必要に応じて `direct_prompt` や `CLAUDE.md` のルールを調整します。

観察ポイント:

- トリアージの判定精度（`needs-info` / `triaged` / `out-of-scope` の振り分けが妥当か）
- 不足情報の質問内容が報告者にとって明確か
- 実装 PR が CLAUDE.md / AGENTS.md の規約を守っているか
- changelog fragment が正しく追加されているか

### プロンプトインジェクション対策

- `allowed_tools` を最小化し、トリアージ・wontfix では `gh issue:*` / `gh label:*` / `gh search:*` のみ許可している
- 実装フェーズでも `Bash,Edit,Write,Read,Grep,Glob` に限定
- `permissions:` ブロックで必要最小限の `GITHUB_TOKEN` スコープに絞っている

Issue 本文内に悪意ある指示が混入している可能性に備え、**生成された PR は必ずレビューする** ことを徹底してください。

### API 消費の抑制

- ボット由来の Issue は `github.event.issue.user.type != 'Bot'` で除外
- ノイズの多い時期は月のコストが嵩むので、必要に応じて以下のフィルタ追加を検討:
  - Issue テンプレを使っていない Issue を除外
  - 特定ラベル付きのみ反応させる
  - 特定リポジトリ コラボレーター以外の Issue は人間レビューに回す

### デバッグ方法

ワークフローが期待通りに動かない場合:

1. **Actions タブのログを確認**: `Claude Issue Triage` / `Claude Issue Implement` の各ジョブログを開き、Claude が実行したコマンドと出力を確認
2. **`direct_prompt` の調整**: 判定基準が曖昧な場合は、本ファイルが参照しているワークフロー YAML 内の `direct_prompt` を編集
3. **`.claude/` 配下のルール追加**: 反復するミスがある場合、リポジトリの `.claude/` 配下にルールファイルを追加して恒常的に守らせる
4. **`CLAUDE.md` への追記**: プロジェクト全体に効くガードレールは `CLAUDE.md` の「OSS Issue 自動対応の運用規約」セクションに追記

## コスト見積もりの考え方

トリアージは 1 件あたり Issue 本文 + コメント数件 + 関連 Issue/ラベル一覧を読む程度のトークン量で済みます。実装フェーズは規模に応じてトークン消費が大きく変動するため、月次コストはトリアージ件数よりも `ai-implement` 付与回数に強く依存します。

ノイズの多い時期は月のコストが嵩むので、必要に応じて Issue テンプレ未使用のものに絞るなどのフィルタ追加を検討してください。

<!-- TODO: mkdocs.yml の nav に追加してください -->
