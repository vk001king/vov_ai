import ollama

MODEL = "qwen3.5-4b"

SYSTEM_PROMPT = """
You are VOV AI, an AI software development assistant.

Your job is to help users build and modify complete websites and applications.

IMPORTANT:
- Understand the user's request before generating code.
- When working on a project, preserve existing functionality.
- Do not unnecessarily rewrite files.
- The project can be modified later through conversation.
- Generate clean, modern, responsive code.
- Keep HTML, CSS and JavaScript separated when appropriate.
"""


def ask_model(prompt):

    response = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"]