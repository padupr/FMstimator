#!/usr/bin/env python3
"""
Auto generate repositories from their ansible configs.
"""

import pathlib as pl
import shutil
import argparse

from plumbum import local


REPO_NAME_VAR = "repo_name"


def is_git_folder(folder: pl.Path) -> bool:
    """
    Checks if a folder is a git,
    by verifying if it has a .git or .gitted subfolder.
    """
    return folder.name.endswith(".git") or folder.name.endswith(".gitted")


def get_ansible_repo_name(ansible_config: pl.Path):
    """
    Get repository name from ansible-playbook
    """
    with open(ansible_config, 'r') as config_file:
        for line in config_file.readlines():
            if line.strip().startswith(REPO_NAME_VAR):
                return line.split(':')[1].strip().strip('\'').strip('"')

    raise KeyError('Could not find {} in ansible_config'.format(REPO_NAME_VAR))


def run_ansible(ansible_config: pl.Path, output_folder: pl.Path) -> None:
    """
    Run ansible-playbook on a specifc ansible_config and move the generated
    repository into output_folder.
    """
    local['ansible-playbook'](ansible_config)

    repo_name = get_ansible_repo_name(ansible_config)

    if (output_folder / repo_name).exists():
        shutil.rmtree(output_folder / repo_name)
    shutil.move(str(ansible_config.parent / repo_name), output_folder)


def handle_ansible_folder(folder: pl.Path, output_base: pl.Path) -> None:
    """
    Handle generator for an specific ansible folder.

    Params
        folder: folder to work on
        output_base: target folder to put generated repos into
    """
    print("Processing folder ", folder)
    output_folder = output_base / folder
    if not output_folder.exists():
        output_folder.mkdir(parents=True)

    for repo_config in [
            x for x in folder.iterdir() if
            x.is_file() and (x.name.endswith(".yaml") or x.name.endswith('.yml')) \
                        and not "EXCLUDE" in x.name
    ]:
        print("Generating... ", repo_config)
        run_ansible(repo_config, output_folder)

    # Handle sub folder
    for sub_folder in [x for x in folder.iterdir() if x.is_dir()]:
        if is_git_folder(sub_folder):
            # Skip possible generated git folders
            return

        handle_ansible_folder(sub_folder, output_base)


def main() -> None:
    """
    Read inputs and start the generation process.
    """
    root = pl.Path('.')

    parser = argparse.ArgumentParser(description="Generate VaRA test repos")
    parser.add_argument('dst_dir',
                        type=pl.Path,
                        help="Output folder to generate the repos into.")

    args = parser.parse_args()

    output_root = pl.Path(args.dst_dir)

    for folder in [x for x in root.iterdir() if x.is_dir()]:
        if is_git_folder(folder):
            continue

        handle_ansible_folder(folder, output_root)


if __name__ == "__main__":
    main()
