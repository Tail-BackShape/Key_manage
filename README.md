# スマートロック状態管理・通知システム

手動で開閉した鍵の状態フラグを Web で管理し、操作ログを Discord Webhook に通知する Flask アプリです。

## 特徴
- GPIO を使わず、状態管理と通知のみを実装
- フロー状態をサーバー側で保持し、リロードや複数端末でも同じフェーズを再開
- SSE によるリアルタイム画面同期
- 一時施錠は「ユーザー選択後」に通知送信し、施錠管理画面へ戻る
- .env でユーザー一覧と通知先を管理
- 操作ログを `[時刻] [操作者]が [アクション] しました` 形式で送信

## ディレクトリ構成
- app: バックエンドロジック
- templates: HTML
- static: CSS / JavaScript
- app.py: 起動エントリーポイント

## セットアップ
1. Python 3.10 以上を用意
2. 依存関係をインストール
   - `pip install -r requirements.txt`
3. 環境変数ファイルを作成
   - `.env.example` をコピーして `.env` を作成
4. サーバー起動
   - `python app.py`

## 環境変数
- DISCORD_WEBHOOK_URL: Discord Webhook URL
- USERS: カンマ区切りのユーザー名
- TIME_FORMAT: 通知に使う時刻フォーマット
- HOST: バインドするホスト
- PORT: ポート番号
- DEBUG: true / false

## API 概要
- GET /api/bootstrap: 初期表示に必要な状態とユーザー一覧
- GET /api/state: 現在状態
- GET /api/events: SSE で状態同期イベントを配信
- POST /api/flow/start: エントリアクション開始（unlock / home / temp_lock）
- POST /api/flow/select-user: ユーザー選択確定と必要な通知送信
- POST /api/flow/back: ユーザー選択画面の戻る（前のフェーズへ）
- POST /api/flow/reset: フローを初期画面へ戻す
- POST /api/flow/change-user: ユーザー選択フェーズへ戻す
- POST /api/action: 操作実行と通知
  - body 例: `{ "user": "山田", "action": "temp_lock" }`
  - action: `unlock` / `temp_lock` / `home`

## 画面遷移メモ
- `開錠` 押下 -> ユーザー選択 -> 開錠通知送信 -> 操作選択
- `一時施錠` 押下（操作選択画面）-> ユーザー選択（「一時施錠する人を選択してください」）-> 一時施錠通知送信 -> 施錠管理画面（開錠/帰宅）
- `施錠・帰宅` 実行 -> 施錠通知送信 -> 施錠管理画面（開錠のみ表示）

## 注意
このプロジェクトは物理鍵を操作しません。人間が手動で鍵を開閉した結果を記録するためのシステムです。
