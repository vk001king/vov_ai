from pathlib import Path


def test_project(project_name):

    project_path = (
        Path(__file__).parent
        / "generated_projects"
        / project_name
    )

    errors = []

    # Project exists
    if not project_path.exists():
        return ["Project directory does not exist."]

    # -------------------------
    # HTML CHECK
    # -------------------------

    index = project_path / "index.html"

    if not index.exists():
        return ["index.html is missing."]

    html = index.read_text(
        encoding="utf-8"
    )

    html_lower = html.lower()

    # DOCTYPE
    if "<!doctype html>" not in html_lower:
        errors.append(
            "index.html does not contain a valid DOCTYPE."
        )

    # HTML
    if "<html" not in html_lower:
        errors.append(
            "Missing <html> element."
        )

    # HEAD
    if "<head" not in html_lower:
        errors.append(
            "Missing <head> element."
        )

    # BODY
    if "<body" not in html_lower:
        errors.append(
            "Missing <body> element."
        )

    # -------------------------
    # CSS CHECK
    # -------------------------

    if "style.css" in html_lower:

        css = project_path / "style.css"

        if not css.exists():
            errors.append(
                "style.css is referenced but missing."
            )

    # -------------------------
    # JS CHECK
    # -------------------------

    if "script.js" in html_lower:

        js = project_path / "script.js"

        if not js.exists():
            errors.append(
                "script.js is referenced but missing."
            )

    return errors
