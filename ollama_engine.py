import ollama


# ============================================================
# MODEL CONFIGURATION
# ============================================================

CHAT_MODEL = "qwen2.5:3b" 

FAST_MODEL = "qwen3.5-4b:latest" 

POWERFUL_MODEL = "qwen3.5:latest"


# ============================================================
# MODEL ALIASES
# ============================================================

MODEL_ALIASES = {

    "qwen2.5": CHAT_MODEL,
    "qwen2.5:3b": CHAT_MODEL,

    "qwen3.5-4b": FAST_MODEL,
    "qwen3.5-4b:latest": FAST_MODEL,

    "qwen3.5": POWERFUL_MODEL,
    "qwen3.5:latest": POWERFUL_MODEL,
}


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are VOV AI.

You are a powerful local AI assistant and software development agent.

Your main purpose is to help users:

- Answer questions
- Explain concepts
- Write code
- Debug code
- Fix errors
- Build complete websites
- Build complete applications
- Create Python programs
- Create JavaScript applications
- Create React applications
- Modify existing projects
- Improve existing projects
- Generate project files
- Improve UI and UX
- Design modern interfaces
- Work with project files
- Continue previous work

IMPORTANT RULES:

1. Understand the user's request before responding.

2. Give useful and direct answers.

3. If the user asks to modify an existing project, preserve existing
   functionality unless the user explicitly asks to remove it.

4. Do not unnecessarily rewrite working code.

5. When generating software, create complete functional code.

6. When the user specifies a programming language, ALWAYS use that language.

7. If the user does not specify a language, choose the most suitable
   technology automatically.

8. If the user asks for a website:
   - Use HTML
   - CSS
   - JavaScript
   unless another framework is requested.

9. If the user asks for React, use React.

10. If the user asks for Python, use Python.

11. When modifying code, carefully preserve existing features.

12. Do not create fake functionality.

13. Do not use placeholders such as:
    TODO
    YOUR CODE HERE
    ADD CODE HERE

14. Do not expose private chain-of-thought or hidden reasoning.

15. If thinking is enabled, only provide a short useful progress summary.

16. You are a local AI running through Ollama.

You are VOV AI.
"""


# ============================================================
# KEYWORDS
# ============================================================

CODING_KEYWORDS = [

    "code",
    "coding",
    "program",
    "programming",

    "website",
    "web app",
    "web application",

    "application",
    "app",

    "software",

    "python",
    "javascript",
    "typescript",

    "react",
    "reactjs",
    "nextjs",
    "next.js",

    "html",
    "css",

    "api",
    "backend",
    "frontend",

    "fastapi",
    "flask",
    "django",

    "node",
    "nodejs",

    "database",
    "sql",

    "debug",
    "debugging",
    "bug",
    "error",

    "fix",

    "build",
    "create",
    "develop",

    "project",

    "component",
    "function",
    "class",

    "algorithm",

    "github",

]


# ============================================================
# COMPLEX REQUEST KEYWORDS
# ============================================================

COMPLEX_KEYWORDS = [

    "full stack",
    "full-stack",

    "complete application",
    "complete app",

    "complete website",

    "build an app",
    "build a website",
    "build application",

    "generate project",
    "create project",

    "large project",
    "complex project",

    "architecture",

    "authentication",
    "authorization",

    "database",

    "api integration",

    "backend",
    "frontend",

    "dashboard",

    "admin panel",

    "ecommerce",
    "e-commerce",

    "login system",

    "signup system",

]


# ============================================================
# CHECK CODING REQUEST
# ============================================================

def is_coding_request(prompt):

    text = str(prompt).lower()

    return any(
        keyword in text
        for keyword in CODING_KEYWORDS
    )


# ============================================================
# CHECK COMPLEX REQUEST
# ============================================================

def is_complex_request(prompt):

    text = str(prompt).lower()

    return any(
        keyword in text
        for keyword in COMPLEX_KEYWORDS
    )


# ============================================================
# AUTOMATIC MODEL SELECTION
# ============================================================

def select_model(prompt, requested_model="auto"):

    # --------------------------------------------------------
    # NORMALIZE REQUESTED MODEL
    # --------------------------------------------------------

    requested_model = (
        requested_model or "auto"
    ).lower().strip()


    # --------------------------------------------------------
    # EXPLICIT MODEL
    # --------------------------------------------------------

    if requested_model != "auto":

        if requested_model in MODEL_ALIASES:

            return MODEL_ALIASES[
                requested_model
            ]

        return requested_model


    # --------------------------------------------------------
    # AUTO MODEL SELECTION
    # --------------------------------------------------------

    # Complex software projects
    if is_complex_request(prompt):

        return POWERFUL_MODEL


    # Normal coding requests
    if is_coding_request(prompt):

        return FAST_MODEL


    # Normal conversation
    return CHAT_MODEL


# ============================================================
# GET AVAILABLE MODELS
# ============================================================ 

def get_available_models():

    try:

        result = ollama.list()

        installed = []

        # New Ollama Python API
        if hasattr(result, "models"):

            for model in result.models:

                name = getattr(
                    model,
                    "model",
                    None
                )

                if name:
                    installed.append(name)

        # Remove duplicates
        installed = list(
            dict.fromkeys(installed)
        )


        return {

            "auto": True,

            "installed": installed,

            "chat": CHAT_MODEL,

            "fast": FAST_MODEL,

            "powerful": POWERFUL_MODEL

        }


    except Exception as e:

        print(
            "Ollama model list error:",
            e
        )

        return {

            "auto": True,

            "installed": [],

            "chat": CHAT_MODEL,

            "fast": FAST_MODEL,

            "powerful": POWERFUL_MODEL

        }


# ============================================================
# NORMAL ASK
# ============================================================

def ask_model(
    prompt,
    model="auto",
    return_model=False
):

    # --------------------------------------------------------
    # SELECT MODEL
    # --------------------------------------------------------

    selected_model = select_model(
        prompt,
        model
    )


    # --------------------------------------------------------
    # ASK OLLAMA
    # --------------------------------------------------------

    response = ollama.chat(

        model=selected_model,

        messages=[

            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },

            {
                "role": "user",
                "content": prompt
            }

        ],

        options={

            "temperature": 0.7,

            "top_p": 0.9

        }

    )


    # --------------------------------------------------------
    # GET ANSWER
    # --------------------------------------------------------

    answer = response[
        "message"
    ][
        "content"
    ]


    # --------------------------------------------------------
    # RETURN MODEL INFORMATION
    # --------------------------------------------------------

    if return_model:

        return {

            "response": answer,

            "model": selected_model

        }


    return answer


# ============================================================
# STREAM MODEL
# ============================================================

def stream_model(
    prompt,
    model="auto"
):

    # --------------------------------------------------------
    # SELECT MODEL
    # --------------------------------------------------------

    selected_model = select_model(
        prompt,
        model
    )


    try:

        # ----------------------------------------------------
        # START OLLAMA STREAM
        # ----------------------------------------------------

        stream = ollama.chat(

            model=selected_model,

            messages=[

                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ],

            stream=True,

            think=True,

            options={

                "temperature": 0.7,

                "top_p": 0.9

            }

        )


        # ----------------------------------------------------
        # PROCESS STREAM
        # ----------------------------------------------------

        for chunk in stream:

            # Ollama Python objects can behave
            # differently between versions.

            if hasattr(
                chunk,
                "message"
            ):

                message = chunk.message 

                thinking = getattr(
                    message,
                    "thinking",
                    None
                )

                content = getattr(
                    message,
                    "content",
                    None
                )

            else:

                message = chunk.get(
                    "message",
                    {}
                )

                thinking = message.get(
                    "thinking"
                )

                content = message.get(
                    "content"
                )


            # ------------------------------------------------
            # THINKING
            # ------------------------------------------------

            if thinking:

                yield {

                    "type": "thinking",

                    "content": thinking,

                    "model": selected_model

                }


            # ------------------------------------------------ 
            # ANSWER
            # ------------------------------------------------

            if content:

                yield {

                    "type": "content",

                    "content": content,

                    "model": selected_model

                }


    except Exception as e:

        yield {

            "type": "error",

            "content": str(e),

            "model": selected_model

        }
