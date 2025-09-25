import re

rx_trailing_line_in_code = re.compile(r"\n</code>", re.MULTILINE)


def on_page_content(markdown: str, page, config, files):
    # Remove a trailing line breaks in each code block
    markdown = rx_trailing_line_in_code.sub("</code>", markdown)
    return markdown
