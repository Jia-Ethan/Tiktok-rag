# Beginner quickstart

这是给第一次试用 `video-rag` 的普通用户准备的说明。

如果你只想尽快跑通一次，请按下面做。

## 你需要准备什么

- 一台本地电脑
- Python 3.9+
- `ffmpeg`
- 一个已经下载到本地的视频文件

推荐先用：

- 1 到 10 分钟左右的视频
- 人声比较清楚的内容
- `.mp4`、`.mov` 或 `.mkv` 文件

## 第一次运行

### 1. 安装 ffmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

### 2. 克隆项目并安装依赖

```bash
git clone https://github.com/Jia-Ethan/video-rag.git
cd video-rag
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

### 3. 启动本地界面

```bash
python3 app/gradio_app.py
```

然后在浏览器打开本地地址，通常是：

```text
http://127.0.0.1:7860
```

如果你看到本地地址打不开，也可以改成：

```bash
VIDEO_RAG_HOST=0.0.0.0 VIDEO_RAG_PORT=7860 python3 app/gradio_app.py
```

### 4. 处理一个视频

在界面里：

1. 选择一个本地视频文件
2. 模型先用默认的 `base`
3. 语言先用默认的 `auto`
4. 点击“开始处理”

## 处理完成后先看哪个文件

第一次试用时，先看这两个：

- `preview.md`
  最适合第一次打开。它会告诉你这次处理的基本信息、chunk 预览，以及每个输出文件怎么用。
- `text.txt`
  最适合直接阅读、复制、发给别人或贴进笔记软件。

然后再做这两步：

1. 打开 UI 里的「个人视频库」
2. 进入刚处理完的视频详情页，继续做筛选、搜索、提问或整理

## txt / md / json 各自适合什么场景

- `txt`
  适合阅读、复制、笔记、贴到其他工具里
- `md`
  适合第一次整体查看结果，因为它会把关键信息和 chunk 预览整理出来
- `json`
  更适合开发者、自动化脚本、后续索引或检索处理

## 如果你卡住了，先检查什么

- 有没有先安装 `ffmpeg`
- 视频文件是不是本地文件，而不是 URL
- 视频格式是不是 `.mp4`、`.mov`、`.mkv`、`.m4v` 或 `.webm`
- 模型是不是先用 `base`
- 如果自动识别语言效果不好，是否手动指定了语言

## 你处理完成后会拿到哪些文件

默认在 `data/` 下：

- `audio/*.wav`
- `text/*.txt`
- `preview/*.md`
- `transcripts/*.json`
- `chunks/*.chunks.json`
- `meta/*.meta.json`
- `manifests/*.manifest.json`
- `library/*.video.json`

如果你只是普通用户，优先打开：

1. `preview/*.md`
2. `text/*.txt`

如果你已经想继续用这份结果，而不是只导出文字：

3. 去 UI 的「个人视频库」里找回这个视频
4. 在详情页里继续做当前视频搜索、提问、保存结果
