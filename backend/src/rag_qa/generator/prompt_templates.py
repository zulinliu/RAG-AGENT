from __future__ import annotations


class PromptTemplate:
    SYSTEM_PROMPT = """你是一个专业的项目知识问答助手。你的任务是基于提供的项目文档资料，准确回答用户的问题。

【核心规则】
1. 仅基于提供的参考资料回答问题，不要使用你的先验知识
2. 对每个事实声明，必须引用来源文档编号，格式为[来源N]
3. 如果参考资料中不包含足够信息来回答问题，请明确说"根据现有项目资料，我没有找到相关信息"，不要猜测或编造
4. 如果参考资料中的信息存在矛盾，请指出矛盾并分别引用不同来源
5. 回答要简洁准确，避免冗余信息
6. 如果用户的问题模糊，可以先澄清问题再回答"""

    CHAT_PROMPT = """基于以下参考资料回答用户的问题。

{context}

用户问题：{query}"""

    QUERY_REWRITE_PROMPT = (
        "请将以下用户问题改写为更清晰、更适合检索的查询语句。"
        "保留原始问题的核心意图，去除口语化表达，补充必要的上下文信息。\n\n"
        "原始问题：{query}\n"
        "对话历史：{history}\n\n"
        "请直接输出改写后的查询，不要添加任何解释。"
    )

    INTENT_PROMPT = """请判断以下用户问题的意图类型，从以下选项中选择一个：
- fact_query: 事实查询，寻找具体的事实或数据
- solution_query: 方案查询，寻求解决方案或建议
- comparison_query: 对比查询，比较不同方案或选项
- process_query: 流程查询，了解操作流程或步骤
- clarification: 澄清问题，需要进一步解释或补充信息

用户问题：{query}

请直接输出意图类型，不要添加任何解释。"""

    HYDE_PROMPT = (
        "请针对以下问题，生成一个假设性的详细答案。"
        "这个答案不需要完全准确，但应该包含可能出现在真实答案中的关键词和概念，"
        "用于辅助检索相关文档。\n\n"
        "问题：{query}\n\n"
        "请直接输出假设性答案，不要添加任何解释。"
    )

    QUERY_EXPAND_PROMPT = """请将以下查询扩展为3个不同角度的搜索查询，以便从不同维度检索相关信息。

原始查询：{query}

请每行输出一个扩展查询，不要添加编号或其他解释。"""

    def format_chat(self, context: str, query: str) -> str:
        return self.CHAT_PROMPT.format(context=context, query=query)

    def format_query_rewrite(self, query: str, history: str = "") -> str:
        return self.QUERY_REWRITE_PROMPT.format(query=query, history=history)

    def format_intent(self, query: str) -> str:
        return self.INTENT_PROMPT.format(query=query)

    def format_hyde(self, query: str) -> str:
        return self.HYDE_PROMPT.format(query=query)

    def format_query_expand(self, query: str) -> str:
        return self.QUERY_EXPAND_PROMPT.format(query=query)
