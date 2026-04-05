# Prompits 示例配置

## 翻译版本

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## 文件

- `plaza.agent`: 带有本地 `FileSystemPool` 的 Plaza
- `worker.agent`: 一个会自动向 Plaza 注册的基础 `StandbyAgent`
- `user.agent`: 一个用于展示 Plaza 浏览器 UI 的 `UserAgent`

## 执行顺序

从仓库根目录：
```bash
python3 prompits/create_agent.py --config prompits/examples/plaza.agent
python3 prompits/create_agent.py --config prompits/examples/worker.agent
python3 prompits/create_agent.py --config prompits/examples/user.agent
```

然后访问 `http://127.0.0.1:8214/`。

## 存储

示例配置将本地状态写入：
```text
prompits/examples/storage/
```

该目录由 `FileSystemPool` 自动创建。
