from aiogram.utils.markdown import html_decoration


def esc(value: str) -> str:
    return html_decoration.quote(str(value))


def trim(value: str, limit: int = 4096) -> str:
    return value if len(value) <= limit else value[: limit - 1] + '…'
