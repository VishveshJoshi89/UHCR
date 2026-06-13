from plugins.llama import (
    LlamaCppPlugin
)

llm = LlamaCppPlugin()

response = llm.generate(
    "Explain UHCR in 3 lines."
)

print(response)