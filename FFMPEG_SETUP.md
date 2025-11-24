# ffmpegのインストール方法

このツールで動画ファイルをトリミングするには、**ffmpeg**が必要です。

ffmpegはPythonパッケージではなく、独立した外部コマンドラインツールです。そのため、`pip install`ではインストールできません。

## 📌 重要な注意事項

- **画像ファイルのみを扱う場合、ffmpegは不要です**
- 起動時に警告が表示されても、画像の切り抜きは問題なく動作します
- **動画ファイルを扱いたい場合のみ**、ffmpegのインストールが必要です

## 🪟 Windows

### 方法1: ビルド済みバイナリをダウンロード（推奨）

1. **[gyan.devのffmpegビルド](https://www.gyan.dev/ffmpeg/builds/)** にアクセス

2. **「ffmpeg-release-essentials.zip」** をダウンロード
   - ⚠️ 注意：`.tar.xz`ファイルではなく、`.zip`ファイルをダウンロードしてください
   - `.tar.xz`はソースコードであり、ビルドが必要です

3. zipファイルを解凍
   - 例：`C:\ffmpeg`に解凍
   - 解凍後、`C:\ffmpeg\ffmpeg-x.x-essentials_build\bin`フォルダが作成されます

4. **環境変数PATHにbinフォルダを追加**

   **手順：**
   - Windowsキーを押して「環境変数」で検索
   - 「システム環境変数の編集」を開く
   - 「環境変数」ボタンをクリック
   - 「システム環境変数」の「Path」を選択して「編集」
   - 「新規」をクリック
   - ffmpegのbinフォルダのパスを入力（例：`C:\ffmpeg\ffmpeg-7.0-essentials_build\bin`）
   - 「OK」で全てのウィンドウを閉じる

5. **コマンドプロンプトを再起動**して確認
   ```bash
   ffmpeg -version
   ```
   バージョン情報が表示されれば成功です！

### 方法2: Chocolateyを使用（推奨・最も簡単）

Chocolateyがインストールされている場合：

```bash
# コマンドプロンプト（管理者権限）で実行
choco install ffmpeg
```

Chocolateyがインストールされていない場合：

1. PowerShellを**管理者権限**で起動
2. 以下のコマンドを実行してChocolateyをインストール：
   ```powershell
   Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
   ```
3. コマンドプロンプト（管理者権限）で：
   ```bash
   choco install ffmpeg
   ```

PATH設定も自動的に行われます！

### 方法3: wingetを使用（Windows 10/11）

```bash
# コマンドプロンプトで実行
winget install ffmpeg
```

PATH設定も自動的に行われます！

## 🍎 macOS

### Homebrewを使用（推奨）

```bash
brew install ffmpeg
```

Homebrewがインストールされていない場合は、まず[Homebrew公式サイト](https://brew.sh/ja/)からインストールしてください。

## 🐧 Linux

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install ffmpeg
```

### CentOS / RHEL / Fedora

```bash
# CentOS/RHEL 8以降
sudo dnf install ffmpeg

# CentOS/RHEL 7
sudo yum install epel-release
sudo yum install ffmpeg
```

### Arch Linux

```bash
sudo pacman -S ffmpeg
```

## ✅ インストールの確認

どの方法でインストールした場合も、以下のコマンドで確認できます：

```bash
ffmpeg -version
```

以下のような出力が表示されれば成功です：

```
ffmpeg version 7.0 Copyright (c) 2000-2024 the FFmpeg developers
built with gcc 13.2.0 (GCC)
...
```

## 🔧 venv環境での使用について

**特別な設定は不要です！**

ffmpegはシステムレベルのコマンドラインツールなので、Python仮想環境（venv）の内外に関係なく使用できます。

1. システムにffmpegをインストール（上記の方法）
2. venv環境をアクティベート
3. アプリを起動

これだけで動作します。

## ❓ トラブルシューティング

### Windows: 「ffmpegが見つかりません」と表示される

1. **コマンドプロンプトを再起動**してください
   - 環境変数の変更は、新しいコマンドプロンプトでのみ有効です

2. **PATH環境変数が正しいか確認**
   ```bash
   echo %PATH%
   ```
   出力の中にffmpegのbinフォルダのパスが含まれているか確認

3. **ffmpeg.exeが実際に存在するか確認**
   - 追加したパスのフォルダを開く
   - `ffmpeg.exe`ファイルが存在するか確認

### macOS/Linux: 「command not found」と表示される

```bash
# インストールされているか確認
which ffmpeg

# 再インストール
# macOS
brew reinstall ffmpeg

# Ubuntu/Debian
sudo apt install --reinstall ffmpeg
```

### 「.tar.xz」ファイルをダウンロードしてしまった

それはソースコードです。ビルド済みバイナリ（.zipファイル）を再度ダウンロードしてください。

## 📚 参考リンク

- [ffmpeg公式サイト](https://ffmpeg.org/)
- [gyan.dev ffmpegビルド（Windows）](https://www.gyan.dev/ffmpeg/builds/)
- [Chocolatey公式サイト](https://chocolatey.org/)
- [Homebrew公式サイト](https://brew.sh/ja/)
