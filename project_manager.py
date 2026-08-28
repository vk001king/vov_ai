from pathlib import Path


BASE_DIR = Path(__file__).parent / "generated_projects"


def create_project(project_name):
    project_path = BASE_DIR / project_name

    project_path.mkdir(
        parents=True,
        exist_ok=True
    )

    return project_path


def create_file(project_name, file_path, content):

    project_path = BASE_DIR / project_name

    full_path = project_path / file_path

    full_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    full_path.write_text(
        content,
        encoding="utf-8"
    )

    return full_path


def read_project(project_name):

    project_path = BASE_DIR / project_name

    if not project_path.exists():
        return {}

    files = {}

    for file in project_path.rglob("*"):

        if file.is_file():

            relative_path = file.relative_to(project_path)

            try:
                files[str(relative_path)] = file.read_text(
                    encoding="utf-8"
                )

            except UnicodeDecodeError:
                pass

    return files
def get_project_context(project_name):

    project_path = BASE_DIR / project_name

    if not project_path.exists():
        return ""

    context = []

    for file in project_path.rglob("*"):

        if file.is_file():

            try:
                content = file.read_text(
                    encoding="utf-8"
                )

                relative = file.relative_to(
                    project_path
                )

                context.append(
                    f"FILE: {relative}\n"
                    f"{content}\n"
                    f"---"
                )

            except UnicodeDecodeError:
                pass

    return "\n".join(context)