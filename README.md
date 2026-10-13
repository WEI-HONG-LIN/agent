# AI 代理（Agent）教學包

| 檔案 | 內容 |
|---|---|
| [01-AI代理運作原理.md](./01-AI代理運作原理.md) | 圖解代理的定義、四大元件、ReAct 迴圈、API 訊息流、六種設計模式、工具設計、安全防線 |
| [02-自己動手實作代理.md](./02-自己動手實作代理.md) | 用生活比喻 + 逐步程式碼，從零寫出一個會用工具的代理 |
| [agent/simple_agent.py](./agent/simple_agent.py) | 可直接執行的最小代理（Python + anthropic SDK，無框架） |

## 快速開始

```bash
pip install -r agent/requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."   # Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
cd agent
python simple_agent.py "現在幾點？然後幫我算 123 * 45"
```

## 閱讀建議

1. 先讀原理篇第 1–4 節，理解「模型只會說、程式才會做」與 `stop_reason` 的角色。
2. 再照實作篇一步步敲，看終端機印出 `🔧 呼叫工具` 時迴圈怎麼轉。
3. 回頭讀原理篇第 5–8 節，了解什麼時候該升級成 workflow 模式或多代理。

所有圖表為 Mermaid 格式，GitHub、VS Code、Obsidian 可直接渲染。
