# Prompits 範例配置

## 翻譯版本

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## 檔案

- `plaza.agent`: 帶有本地 `FileSystemPool` 的 Plaza
- `worker.agent`: 一個會自動向 Plaza 註冊的基礎 `StandbyAgent`
- `user.agent`: 一個用於展示 Plaza 瀏覽器 UI 的 `UserAgent`

## 執行順序

從儲存庫根目錄：
```bash
python3 prompits/create_agent.py --config prompits/examples/plaza.agent
python3 prompits/create_agent.py --config prompits/examples/worker.agent
python3 prompits/create_agent.py --config prompits/examples/user.agent
```

然後訪問 `http://127.0.0.1:8214/`。

## 儲存

範例配置將本地狀態寫入：
```text
prompits/examples/storage/
```

該目錄由 `FileSystemPool` 自動建立。
