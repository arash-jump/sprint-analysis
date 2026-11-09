# Sprint Analysis

[English README](README.md)

スプリント動画をもとに、選手の動きと速度を分析するWebアプリケーションです。動画をアップロードし、動画上の校正点と撮影条件を入力すると、Pythonスクリプトが解析結果を計算して画面に表示します。

## 主な機能

- ユーザー登録・ログイン
- スプリント動画のアップロード
- 動画上での校正点の指定
- FPS、校正距離、走行距離の入力
- 動画から算出した速度などの解析結果とグラフの表示

## 使用技術

- PHP 8.2以上 / Laravel 12
- SQLite（初期設定）
- JavaScript / Bootstrap / Vite
- Python 3 / OpenCV / MediaPipe

## セットアップ

以下はmacOS・Linux向けの手順です。解析処理はプロジェクト直下の`venv/bin/python3`を使うため、Python環境はこのパスに作成してください。

### 必要なもの

- PHP 8.2以上、Composer
- Node.js、npm
- Python 3、pip
- H.264およびAACエンコーダーを含むFFmpeg

### 1. PHP依存関係と環境設定

```bash
git clone <リポジトリURL>
cd sprint_analysis

composer install
cp .env.example .env
php artisan key:generate
```

`.env`では、動画を非公開で保存し、認証済みユーザー向けのルートから配信するため、ファイルシステムを`local`に設定します。

```dotenv
FILESYSTEM_DISK=local
```

初期設定ではSQLiteを使います。DBファイルがまだなければ作成し、テーブルを準備します。

```bash
touch database/database.sqlite
php artisan migrate
```

動画はLaravelの非公開ローカルディスクに保存するため、公開ストレージへのシンボリックリンクは不要です。

### 2. FFmpegのインストール

動画アップロード時にブラウザー互換性の高いH.264 MP4へ変換します。H.264とAACのエンコードに対応したFFmpegをインストールしてください。

```bash
# macOS（Homebrew）
brew install ffmpeg

# Debian/Ubuntu
sudo apt install ffmpeg
```

FFmpegが`PATH`にない場合は、`.env`の`FFMPEG_BINARY`に実行ファイルのパスを設定してください。

### 3. Python解析環境

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
deactivate
```

Pythonの計算テストは次のコマンドで実行できます。

```bash
./venv/bin/python -m unittest discover -s python -p 'test_analysis_metrics.py'
```

### 4. フロントエンドの準備と起動

```bash
npm install
npm run build
php artisan serve
```

ブラウザで <http://127.0.0.1:8000> を開き、ユーザー登録またはログインしてください。

## 基本的な使い方

1. ログイン後、`/manual/input`を開いて動画をアップロードします。
2. 動画上で校正点を指定して保存します。
3. FPS、校正距離、走行距離を入力します。
4. 解析結果画面で、算出値と速度グラフを確認します。

## ディレクトリ概要

| パス | 役割 |
| --- | --- |
| `app/Http/Controllers/` | リクエスト処理、画面表示、解析処理の呼び出し |
| `app/Models/` | ユーザー、動画入力データ、解析結果のDBモデル |
| `database/migrations/` | データベーステーブルの定義・変更履歴 |
| `resources/views/` | Bladeによる画面テンプレート |
| `resources/js/`, `resources/sass/` | Viteでビルドするフロントエンド資材 |
| `public/js/`, `public/css/` | ブラウザから直接読み込む静的ファイル |
| `python/calculate.py` | 動画解析と速度計算 |
| `python/analysis_metrics.py` | フレーム番号に基づく速度・区間計算 |
| `python/test_analysis_metrics.py` | 速度計算のユニットテスト |
| `requirements.txt` | 動画解析用Python直接依存パッケージのバージョン |
| `routes/web.php` | Webページと処理のURL定義 |

## データと注意事項

- このプロジェクト自体のライセンスは設定していません。プロジェクトのソースコードについて、追加の利用・再配布許可を示すものではありません。依存ライブラリにはそれぞれのライセンスが適用され、MediaPipeはApache License 2.0で配布されています。
- `.env`、SQLiteデータベース、アップロードした動画、Python仮想環境はローカル環境用です。GitHubには登録しないでください。
- アップロード動画は非公開の`storage/app/private/movies/`に保存され、所有者本人の認証済みリクエストにのみ配信されます。実在する人物の動画を扱う場合は、本人の許可を得て適切に管理してください。
- アップロードした動画は保存前にFFmpegでH.264/AACのMP4へ変換します。この変換機能の追加前にアップロードした動画をブラウザー互換形式にするには、再アップロードしてください。
- 速度はMediaPipeの右腰ランドマークの画面上の横移動から推定します。カメラ角度、校正、ランドマークの検出精度によって結果が変わります。
- この非公開保存への変更より前にアップロードした動画は、`storage/app/public/movies/`に残っている可能性があります。新しい非公開ルートからは配信されません。引き続き必要な動画は`storage/app/private/movies/`へ移動し、公開領域のコピーを削除してください。
- Python解析はプロジェクト直下の`venv/bin/python3`を実行します。Windowsで利用するには実行パスの変更が必要です。
- Pythonの直接依存パッケージは`requirements.txt`でバージョンを固定しています。Python 3.9以上を使用してください。対応するパッケージバージョンはPythonのバージョンやOSによって異なる場合があります。
