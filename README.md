# スマートロック状態管理・通知システム

手動で開閉した鍵の状態フラグを Web で管理し、操作ログを Discord Webhook に通知する Flask アプリです。

## 特徴
- GPIO を使わず、状態管理と通知のみを実装
- Phase 1 -> Phase 2 -> Phase 3 の画面遷移
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
- POST /api/action: 操作実行と通知
  - body 例: `{ "user": "山田", "action": "temp_lock" }`
  - action: `unlock` / `temp_lock` / `home`

## 注意
このプロジェクトは物理鍵を操作しません。人間が手動で鍵を開閉した結果を記録するためのシステムです。
