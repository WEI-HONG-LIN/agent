"""
simple_agent.py - 最小可執行的 AI 代理（Agent）

一個代理 = 大型語言模型（LLM） + 工具 + 一個 while 迴圈。
執行方式：
    python simple_agent.py "現在幾點？然後幫我算 123 * 45"
"""

import ast
import datetime
import operator
import sys
from pathlib import Path

import anthropic

MODEL = "claude-opus-5-5"
MAX_STEPS = 10  # 安全網：最多讓模型呼叫幾輪工具，避免無限迴圈燒錢

client = anthropic.Anthropic()  # 會自動讀取環境變數 ANTHROPIC_API_KEY

# ---------------------------------------------------------------------------
# 1. 工具本體：就是普通的 Python 函式
# ---------------------------------------------------------------------------

def get_current_time() -> str:
    """回傳現在的本地日期時間。"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def calculate(expression: str) -> str:
    """安全地計算四則運算式（不使用 eval，避免執行任意程式碼）。"""

    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
            return _SAFE_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
            return _SAFE_OPS[type(node.op)](_eval(node.operand))
        raise ValueError(f"不支援的運算：{ast.dump(node)}")

    tree = ast.parse(expression, mode="eval")
    return str(_eval(tree.body))


WORKDIR = Path.cwd().resolve()


def read_text_file(path: str) -> str:
    """讀取工作目錄內的文字檔（最多 4000 字），禁止讀取目錄外的檔案。"""
    target = (WORKDIR / path).resolve()
    if WORKDIR not in target.parents and target != WORKDIR:
        raise PermissionError(f"只能讀取 {WORKDIR} 底下的檔案")
    return target.read_text(encoding="utf-8")[:4000]


# 名稱 -> 函式 的對照表，迴圈靠它找到要執行的工具
TOOL_FUNCS = {
    "get_current_time": get_current_time,
    "calculate": calculate,
    "read_text_file": read_text_file,
}

# ---------------------------------------------------------------------------
# 2. 工具說明書：告訴模型「有哪些工具、怎麼用」
#    description 寫得越清楚，模型越不會用錯
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "get_current_time",
        "description": "取得現在的本地日期與時間。當使用者問『現在幾點』『今天幾號』時使用。不需要任何參數。",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "calculate",
        "description": (
            "計算一個數學運算式並回傳結果。支援 + - * / ** % 與括號，"
            "例如 '(12 + 8) * 3'。凡是需要算數的時候都用這個工具，不要自己心算。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "要計算的運算式，只能含數字、運算子與括號",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "read_text_file",
        "description": "讀取目前工作目錄內的文字檔內容。path 請用相對路徑，例如 'notes.txt'。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相對於工作目錄的檔案路徑"}
            },
            "required": ["path"],
        },
    },
]

SYSTEM_PROMPT = (
    "你是一個樂於助人的助理。需要取得時間、算數或讀檔時，請使用提供的工具，"
    "不要猜測。完成後用繁體中文簡短回答使用者。"
)

# ---------------------------------------------------------------------------
# 3. 代理迴圈：呼叫模型 -> 看它要不要用工具 -> 執行 -> 把結果塞回去 -> 再呼叫
# ---------------------------------------------------------------------------

def run_agent(user_message: str, max_steps: int = MAX_STEPS) -> str:
    messages = [{"role": "user", "content": user_message}]

    for step in range(1, max_steps + 1):
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # 模型這一輪說的話（含 tool_use 區塊）一定要原封不動放回對話紀錄
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # 沒有再呼叫工具，代表任務完成，取出文字回答
            return "".join(b.text for b in response.content if b.type == "text")

        if response.stop_reason == "refusal":
            return "（模型基於安全政策拒絕了這個請求）"

        if response.stop_reason == "max_tokens":
            return "（回答太長被截斷，請提高 max_tokens 或縮小問題）"

        if response.stop_reason != "tool_use":
            return f"（未預期的停止原因：{response.stop_reason}）"

        # 走到這裡表示模型想用工具，可能一次要用好幾個
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            print(f"  [step {step}] 🔧 呼叫工具 {block.name}({block.input})")
            try:
                output = TOOL_FUNCS[block.name](**block.input)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": str(output)}
                )
            except Exception as exc:  # 工具出錯不要讓程式崩潰，把錯誤告訴模型讓它自己修正
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"工具執行失敗：{exc}",
                        "is_error": True,
                    }
                )

        # 所有工具結果要放在「同一則」user 訊息裡回傳
        messages.append({"role": "user", "content": tool_results})

    return f"（已達 {max_steps} 步上限，代理停止）"


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "現在幾點？然後幫我算 123 * 45"
    print(f"👤 使用者：{question}")
    answer = run_agent(question)
    print(f"🤖 代理：{answer}")
