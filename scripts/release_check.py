""" A script to check whether a variable `_RELEASE` is set as True.
"""

import argparse
import ast
import sys
from pathlib import Path
from typing import cast


def get_release_flag_value(filepath: Path):
    with open(filepath) as f:
        fbody = f.read()

    parsed_ast = ast.parse(fbody)

    toplevel_assignments = [
        node for node in parsed_ast.body if isinstance(node, ast.Assign)
    ]

    release_val = None
    for node in toplevel_assignments:
        if len(node.targets) != 1:
            continue
        if not isinstance(node.targets[0], ast.Name):
            continue
        single_target = cast(ast.Name, node.targets[0])

        assigned_value = node.value

        if single_target.id == "_RELEASE":
            if not isinstance(assigned_value, ast.Constant):
                raise Exception(
                    f"Not a constant value {assigned_value} is "
                    f"assigned to {single_target}"
                )
            release_val = assigned_value.value

    return release_val


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", type=Path)

    args = parser.parse_args()

    is_release = get_release_flag_value(args.filename)

    if not is_release:
        print("_RELEASE flag is not set as True")
        sys.exit(-1)

    sys.exit(0)
