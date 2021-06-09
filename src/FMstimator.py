#! /usr/bin/env python3.8

import argparse
import itertools
import sys

import vara_feature as flib
import pygit2
from pygit2 import Repository
import logging
import clang.cindex
import os
import os.path
import subprocess
from collections import defaultdict

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

STATS = defaultdict(int)
clang_args = []

# String constants
WORKTREE_NAME = "tracking_tmp"
WORKTREE_PATH = "/tmp"
STATS_H1_USES = "H1 a USES"
STATS_H1_SUCC = "H1 b SUCC"
STATS_H1_FAIL = "H1 c FAIL"
STATS_H2_USES = "H2 a USES"
STATS_H2_SUCC = "H2 b SUCC"
STATS_H2_FAIL = "H2 c FAIL"
STATS_H3_USES = "H3 a USES"
STATS_H3_SUCC = "H3 b SUCC"
STATS_H3_FAIL = "H3 c FAIL"

# Adjust to your system!
clang.cindex.Config.set_library_file('/usr/lib/llvm-10/lib/libclang.so')


def main():
    args = parse_args()

    # read args
    path_repo = os.path.abspath(args.repo)
    commit_target = args.commit_target
    path_feature_model_before = os.path.abspath(args.feature_model_before)
    path_feature_model_after = os.path.abspath(args.feature_model_after)
    global clang_args
    clang_args = args.clangarg

    # create worktree
    git_create_worktree(path_repo, WORKTREE_PATH, WORKTREE_NAME)
    wt_repo = os.path.join(WORKTREE_PATH, WORKTREE_NAME)
    saved_working_dir = os.getcwd()

    # Preparation phase
    logger.info("Phase 1: Preparation")
    fm_before = read_fm(path_feature_model_before)
    len_location_features_before = len([f for f in fm_before if f.hasLocations()])
    STATS["Features_forward_start"] = len_location_features_before
    fm_after = read_fm(path_feature_model_after)
    len_location_features_after = len([f for f in fm_after if f.hasLocations()])
    STATS["Features_backwards_start"] = len_location_features_after

    commit_start = fm_before.commit
    commit_end = fm_after.commit
    os.chdir(wt_repo)

    # init repo and commits
    repo = Repository('.git')
    commits_forward = collect_commits(repo, commit_start, commit_target)
    if not commits_forward:
        exit(1)
    commits_backward = collect_commits_reversed(repo, commit_target, commit_end)
    if not commits_backward:
        exit(1)
    if args.direct:
        if len(commits_forward) > 1:
            commits_forward = [commits_forward[0], commits_forward[-1]]
        if len(commits_backward) > 1:
            commits_backward = [commits_backward[0], commits_backward[-1]]
    STATS["Diffs forward"] = len(commits_forward) - 1
    STATS["Diffs backward"] = len(commits_backward) - 1

    # Tracking phase
    logging.info("Phase 2: Tracking")
    print("Start forward:")
    print_features(commits_forward[0], [f for f in fm_before if f.hasLocations()])
    # walk forward
    track_features_over_commits(commits_forward, fm_before, repo)
    print("Got forward:")
    features_before_done = [f for f in fm_before if f.hasLocations()]
    print_features(commits_forward[-1], features_before_done)
    STATS["Features_forward_end"] = len(features_before_done)

    print("Start backward:")
    print_features(commits_backward[0], [f for f in fm_after if f.hasLocations()])
    # walk backwards
    track_features_over_commits(commits_backward, fm_after, repo)
    print("Got backward:")
    features_after_done = [f for f in fm_after if f.hasLocations()]
    print_features(commits_backward[-1], features_after_done)
    STATS["Features_backwards_end"] = len(features_after_done)

    print("Model_before approximated: ")
    print_fm(fm_before)

    print("Model_after approximated: ")
    print_fm(fm_after)

    # switch cwd back for writing
    os.chdir(saved_working_dir)
    # prune created worktree
    git_remove_worktree(path_repo, WORKTREE_PATH, WORKTREE_NAME)

    # Merge phase, done in feature lib
    logger.info("Phase 3: Merging")
    fm_final = fm_before.merge_with(fm_after)

    # create output files
    create_output_files(fm_final, fm_before, fm_after, commit_target, args.output)

    print("Stats:")
    print_stats()


def collect_commits(repo, commit_start, commit_end):
    """
    Collects commits from commit_start to commit_end over the first parent.
    commit_start must be an ancestor of commit_end.
    """
    # commits are collected in reverse, so we need to reverse to get the normal order
    commits = collect_commits_reversed(repo, commit_start, commit_end)
    commits.reverse()
    return commits


def collect_commits_reversed(repo, commit_start, commit_end):
    """
    Collects commits from commit_start to commit_end over the first parent.
    commit_start must be an ancestor of commit_end.
    """
    commits = []
    start = repo.resolve_refish(commit_start)[0]
    if not start:
        logger.error('commit_end not found: %s', commit_start)
        return None
    end = repo.resolve_refish(commit_end)[0]
    if not end:
        logger.error('commit_end not found: %s', commit_end)
        return None
    commits.append(end)

    # we walk over the parents so we collect the commits in reverse order starting at the latest
    while end != start:
        if len(end.parents):
            first_parent = end.parents[0]
        else:
            logger.error("Could not connect commits")
            return None
        commits.append(first_parent)
        end = first_parent

    return commits


def track_features_over_commits(commits, fm, repo):
    """
    Driver function for tracking. Used for each direction in phase 2.
    """
    for a, b in zip(commits[:-1], commits[1:]):
        logger.info("Tracking changes %s -> %s", a.id, b.id)
        diff = repo.diff(a, b)
        diff.find_similar()

        remove_list = []
        for feature in fm:
            if not feature.hasLocations():
                continue
            logger.info("Checking for changes in feature: %s", feature.name.str())
            for location in feature.locations:
                new_location = estimate_new_location(location, diff, a, b)
                if new_location:
                    feature.updateLocation(location, new_location)
                else:
                    logger.warning(
                        f"Lost {feature.name.str()} location {location} from {a.id} by {a.author.name} to {b.id} by {b.author.name}")
                    feature.removeLocation(location)
                    if not feature.hasLocations():
                        remove_list.append(feature)

        # Reverse handle remove list. FM is iterated topological, so a leaf is handled after its parent, however we cannot
        # remove a parent that still has children.
        for f in reversed(remove_list):
            if list(f.children()):
                # inform user
                logger.error(f"Feature {f.name.str()} has lost all locations but still has children!")
                pass
            else:
                fm.remove_feature(f)
        logger.info("------------------------------------------------")


def estimate_new_location(location: flib.feature.Location, diff: pygit2.Diff, start_commit: pygit2.Commit,
                          end_commit: pygit2.Commit):
    """
    Bundles heuristics and calls them in order.

    For evaluation purposes, both recovery heuristics are compared against each other.
    """
    logger.info("Location is %s", location)
    # save some time by skipping diffs that do not touch the file
    if not diff_contains_file(diff, location.path):
        return location

    # get old code for comparisons
    old_statements = get_code_location(start_commit, location)

    hunk_path, hunks = collect_hunks(diff, location.path)
    new_location = copy_location(location)
    new_location.path = hunk_path

    # simple line tracking
    new_loc1 = track_line_movement(hunks, location, new_location)
    if new_loc1:
        assert old_statements == get_code_location(end_commit, new_loc1)
        return new_loc1

    new_loc2 = recover_from_added_lines(hunks, new_location, end_commit, old_statements)
    new_loc3 = recover_from_ast(diff, location, start_commit, end_commit)
    if new_loc2 != new_loc3:
        logger.warning(f"Location missmatch: lines {new_loc2}, ast {new_loc3}")
    if new_loc2:
        return new_loc2
    else:
        return new_loc3

    # Add more rules to the pipeline here
    # return None


def track_line_movement(hunks, old_location, new_location):
    """
    Heuristic that estimates a new location based on added and removed lines
    """
    logger.info("Trying line tracking")
    STATS[STATS_H1_USES] += 1
    old_start, old_end = old_location.start.line_number, old_location.end.line_number
    for hunk in hunks:
        # check if changes are above old location
        if hunk_before_line(hunk, old_start):
            added = hunk.new_lines - hunk.old_lines
            new_location.start.line_number += added
            new_location.end.line_number += added
            continue

        if hunk_after_line(hunk, old_end):
            # hunks are sorted and do not intersect, so we can skip them
            break

        # Location intersects with hunk
        logger.debug("old: %s, %s; new: %s, %s", hunk.old_start, hunk.old_lines, hunk.new_start, hunk.new_lines)
        for line in hunk.lines:
            if line.origin == ' ':
                # context line, no changes
                continue
            elif line.origin == '-':
                if line_in_location(line.old_lineno, old_location):
                    # line is removed, need to recover
                    logger.info("Line tracking failed")
                    STATS[STATS_H1_FAIL] += 1
                    return None
                # move location upwards if needed
                new_location.start.line_number -= line.num_lines if old_start > line.old_lineno else 0
                new_location.end.line_number -= line.num_lines if old_end > line.old_lineno else 0
            elif line.origin == '+':
                # move location downwards if needed
                new_location.start.line_number += line.num_lines if new_location.start.line_number >= line.new_lineno else 0
                new_location.end.line_number += line.num_lines if new_location.end.line_number >= line.new_lineno else 0
            logger.debug("%s %s %s: %s", line.origin, line.old_lineno, line.new_lineno, line.content.rstrip())
    logger.info("Line tracking successful")
    STATS[STATS_H1_SUCC] += 1
    return new_location


def recover_from_added_lines(hunks, new_location, end_commit, old_statement):
    """
    Heuristic to recover code location by comparing original source code with code in added lines
    """
    logger.info("Trying to recover from added lines")
    STATS[STATS_H2_USES] += 1
    path = new_location.path

    added_lines = []
    for hunk in hunks:
        added_lines.extend([l for l in hunk.lines if l.origin == '+'])

    # We assume that leading/trailing whitespaces have no meaning
    old_statement = [l.strip() for l in old_statement]
    for line in added_lines:
        # try to find parts of the old code in the new lines
        for idx, code in enumerate(old_statement):
            column = line.content.find(code.strip())
            if column != -1:
                # if part is found, compute a candidate location
                start_line = line.new_lineno - idx
                end_line = start_line + len(old_statement) - 1
                candidate = get_code_lines(end_commit, path, start_line, end_line)
                start_col = candidate[0].find(old_statement[0]) + 1
                end_col = candidate[-1].find(old_statement[-1]) + len(old_statement[-1]) + 1
                new_location.start.line_number = start_line
                new_location.end.line_number = end_line
                new_location.start.column_offset = start_col
                new_location.end.column_offset = end_col
                candidate = get_code_location(end_commit, new_location)
                for have, got in zip(old_statement, candidate):
                    logger.debug("Comparing (have) '%s' with (got) '%s'", have.strip(), got.strip())
                    if have.strip() != got.strip():
                        break
                else:
                    # all lines were equal
                    logger.info("Successful recovery")
                    STATS[STATS_H2_SUCC] += 1
                    return new_location
    logger.info("Failed added lines recovery")
    STATS[STATS_H2_FAIL] += 1
    return None


def recover_from_ast(diff, location, start_commit, end_commit):
    """
    Heuristic to recover code location by finding a similar AST subtree in the new code version.
    """
    logger.info("Try node rediscovery")
    STATS[STATS_H3_USES] += 1
    # find representative old subtree
    git_checkout('.', start_commit)
    old_index = clang.cindex.Index.create()
    old_tu = old_index.parse(location.path, args=clang_args)
    print_clang_diagnostics(old_tu)
    old_node = find_node_in_location(old_tu.cursor, location)
    if not old_node:
        logger.warning("Could not find node")
        logger.info("Failed node rediscovery")
        STATS[STATS_H3_FAIL] += 1
        return None

    # search for similar subtree in new version
    git_checkout('.', end_commit)
    hunk_path, hunks = collect_hunks(diff, location.path)
    added_lines = []
    for hunk in hunks:
        added_lines.extend([l.new_lineno for l in hunk.lines if l.origin == '+'])
    new_index = clang.cindex.Index.create()
    new_tu = new_index.parse(hunk_path, args=clang_args)
    if found := search_matching_subtree(new_tu.cursor, old_node, hunk_path, added_lines):
        logger.info("Successful node rediscovery")
        STATS[STATS_H3_SUCC] += 1
        return found
    logger.info("Failed node rediscovery")
    STATS[STATS_H3_FAIL] += 1
    return None


def search_matching_subtree(cursor, searched, file_path, added_lines):
    """
    Searches cursor subtree for match to given subtree.
    """
    if str(cursor.extent.start.file) != file_path:
        return None

    if compare_cursor_recursive(cursor, searched):
        new_loc = extent_to_location(cursor.extent)
        new_loc.end.column_offset += 1  # semicolons are not included in extents
        for line in added_lines:
            if line_in_location(line, new_loc):
                return new_loc
    for c in cursor.get_children():
        if found := search_matching_subtree(c, searched, file_path, added_lines):
            return found


def find_node_in_location(node, location):
    """
    Tries to find a node with an extent inside the given location.
    """
    node_loc = extent_to_location(node.extent)

    if node_loc.path == location.path:
        logger.debug("Node: %s | Location: %s", node_loc, location)
        if node_loc.start.line_number == location.start.line_number:
            if node_loc.start.column_offset == location.start.column_offset:
                if node_loc.end.line_number <= location.end.line_number:
                    if node_loc.end.column_offset <= location.end.column_offset:
                        return node
                    else:
                        logger.debug("End column missmatch")
                else:
                    logger.debug("End line missmatch")
            else:
                logger.debug("Start column missmatch")
        else:
            logger.debug("Start line missmatch")
    else:
        # wrong file
        return None
    for c in node.get_children():
        node = find_node_in_location(c, location)
        if node:
            return node
    return None


def compare_cursor_recursive(old, new):
    """
    Recursively compares the given subtrees.
    """
    if not old or not new:
        return False
    equal = old.kind == new.kind and \
            old.spelling == new.spelling and \
            old.displayname == new.displayname and \
            old.type.spelling == new.type.spelling
    if equal:
        old_children = old.get_children()
        new_children = new.get_children()
        for old_child, new_child in itertools.zip_longest(old_children, new_children):
            if not compare_cursor_recursive(old_child, new_child):
                break
        else:
            # compare tokens
            for old_token, new_token in itertools.zip_longest(old.get_tokens(), new.get_tokens()):
                if old_token.spelling != new_token.spelling:
                    return False
            # all comparisons where successful
            return True
    else:
        return False


def create_output_files(fm_final, fm_before, fm_after, commit_target, output_dir):
    if fm_final:
        STATS['Merging_success'] = True
        STATS['Merging_features'] = len([f for f in fm_final if f.hasLocations()])
        fm_final.commit = commit_target
        logger.info("Merging success")
        print("Merged model:")
        print_fm(fm_final)
        if output_dir:
            output_path = os.path.join(output_dir, f"fm_merged_{commit_target}.xml")
            if not write_fm(fm_final, output_path):
                logger.error(f"Writing failed: {output_path}")
            else:
                logger.info(f"Writing success: {output_path}")
        else:
            fm_writer = flib.fm_writer.FeatureModelXmlWriter(fm_final)
            print(fm_writer.get_feature_model_as_string())
            print()
    else:
        logger.error("Merging failed")
        STATS['Merging_success'] = False
        fm_before.commit = commit_target
        if output_dir:
            write_fm(os.path.join(output_dir, f"fm_approx_before_{commit_target}.xml"))
        else:
            print("XML before:")
            fm_writer = flib.fm_writer.FeatureModelXmlWriter(fm_before)
            print(fm_writer.get_feature_model_as_string())
            print()
        fm_after.commit = commit_target
        if output_dir:
            write_fm(os.path.join(output_dir, f"fm_approx_after_{commit_target}.xml"))
        else:
            print("XML after:")
            fm_writer = flib.fm_writer.FeatureModelXmlWriter(fm_after)
            print(fm_writer.get_feature_model_as_string())
            print()


# helper functions
def extent_to_location(extent):
    """Converts a clang extent to flib location."""
    path = str(extent.start.file)
    start = flib.feature.LineColumnOffset(extent.start.line, extent.start.column)
    end = flib.feature.LineColumnOffset(extent.end.line, extent.end.column)
    return flib.feature.Location(path, start, end)


def hunk_before_line(hunk, line):
    """Returns true if a hunk's old lines end before given line."""
    return hunk.old_start + hunk.old_lines - 1 < line


def hunk_after_line(hunk, line):
    """Returns true if a hunk's old lines start after given line."""
    return hunk.old_start > line


def line_in_location(line, location):
    """Returns true if line is in the location."""
    return location.start.line_number <= line <= location.end.line_number


def diff_contains_file(diff, file):
    """Returns true if the file is changed in the diff."""
    for patch in diff:
        if patch.delta.old_file.path == file:
            return True
    return False


def collect_hunks(diff: pygit2.Diff, path: str):
    """Returns hunks of given file."""
    new_paths = []
    for p in diff:
        if p.delta.old_file.path == path:
            new_paths.append(p.delta.new_file.path)
    # file is unchanged
    if len(new_paths) == 0:
        return None, []
    # more than one file was found
    if len(new_paths) > 1:
        logger.warning("Found more than one new file for %s, picking one at random", path)
    new_path = new_paths[0]
    hunks = []
    [hunks.extend(p.hunks) for p in diff if p.delta.old_file.path == path and p.delta.new_file.path == new_path]

    return new_path, hunks


def copy_location(location):
    """Creates a copy of location."""
    path = location.path
    start_line = location.start.line_number
    start_col = location.start.column_offset
    start = flib.feature.LineColumnOffset(start_line, start_col)
    end_line = location.end.line_number
    end_col = location.end.column_offset
    end = flib.feature.LineColumnOffset(end_line, end_col)
    return flib.feature.Location(path, start, end)


def get_code_location(commit: pygit2.Commit, location: flib.feature.Location):
    """Returns code mapped by location in commit."""
    path = location.path
    start = location.start
    end = location.end
    start_line = start.line_number if start else None
    start_column = start.column_offset if start else None
    end_line = end.line_number if end else None
    end_column = end.column_offset if end else None
    return _get_code(commit, path, start_line, start_column, end_line, end_column)


def get_code_lines(commit: pygit2.Commit, path, start, end):
    """Returns code in path between start and end line in given commit."""
    return _get_code(commit, path, start, None, end, None)


def _get_code(commit: pygit2.Commit, path: str, start_line: int = None, start_column: int = None, end_line: int = None,
              end_column: int = None):
    """Accesses commit to cut requested file location."""
    if start_line:
        start_line -= 1
    if start_column:
        start_column -= 1
    entry = commit.tree[path]
    code_lines = entry.data.decode(errors='ignore').split('\n')
    code = code_lines[start_line:end_line]
    code[-1] = code[-1][:end_column]
    code[0] = code[0][start_column:]
    return code


# input and output helper functions
def read_fm(path):
    """Parses given file with feature library and returns a feature model."""
    logger.info(f"Reading fm: {path}")
    with open(path, 'r') as fm_file:
        fm_parser = flib.fm_parsers.FeatureModelXmlParser(fm_file.read())
        fm = fm_parser.build_feature_model()
    return fm


def write_fm(fm, path):
    """Writes feature model to path."""
    fm_writer = flib.fm_writer.FeatureModelXmlWriter(fm)
    return fm_writer.write_feature_model_to_file(path)


def print_features(commit, features):
    """Prints overview of given features as list."""
    for f in features:
        for l in f.locations:
            loc = l
            try:
                code = ' '.join(l.strip() for l in get_code_location(commit, loc))
                print(f"{f.name.str():>20} || {str(loc):>20} || {code}")
            except IndexError as E:
                logger.error(f"{f.name.str()} - {loc} caused error")
                raise E
    print()
    sys.stdout.flush()


def print_fm(fm):
    """Prints simplified tree representation of feature model."""
    _print_fm(fm.get_root())
    print()
    sys.stdout.flush()


def _print_fm(feature, indentation=1):
    print(('|' * (indentation - 1)) + '-', end='')
    try:
        print(f" {feature.name.str()}")
    except AttributeError:
        print("<Group property>")
    for f in feature:
        _print_fm(f, indentation + 1)


def print_stats():
    """Prints collected statistics."""
    for k, v in sorted(STATS.items()):
        print(f"    {k:<20}: {v}")

    print(
        f"Latex: {STATS['Diffs forward']} & {STATS['Diffs backward']} & ??? & {STATS[STATS_H1_SUCC]} & {STATS[STATS_H1_FAIL]} & {STATS[STATS_H2_SUCC]} & {STATS[STATS_H2_FAIL]} & {STATS[STATS_H3_SUCC]} & {STATS[STATS_H3_FAIL]}")
    print()


def print_clang_diagnostics(tu):
    """Prints diagnostics of translation unit. Helpful to spot missing include files."""
    if tu.diagnostics:
        logger.warning("Clang ran into errors while parsing!")
    for diag in tu.diagnostics:
        logger.warning(f"Clang diagnostic: {str(diag)}")


# Git commands
def git_checkout(cwd, commit: pygit2.Commit):
    """Checkout given commit."""
    command = ['git', 'checkout', str(commit.id)]
    return subprocess.run(command, cwd=cwd).returncode == 0


def git_create_worktree(cwd, path, name):
    """Create worktree of repo at path."""
    wdpath = os.path.join(path, name)
    command = ['rm', '-rf', wdpath]
    subprocess.run(command, cwd=cwd)
    command = ['git', 'worktree', 'add', '-f', wdpath]
    return subprocess.run(command, cwd=cwd, stdout=subprocess.DEVNULL).returncode == 0


def git_remove_worktree(cwd, path, name):
    """Remove worktree at given path."""
    command_wt = ['git', 'worktree', 'remove', os.path.join(path, name)]
    command_b = ['git', 'worktree', 'prune']
    sp_wt = subprocess.run(command_wt, cwd=cwd)
    sp_b = subprocess.run(command_b, cwd=cwd)
    return sp_wt.returncode == 0 and sp_b.returncode == 0


def parse_args():
    """Parses command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument('repo', help='path to repository')
    parser.add_argument('feature_model_before', help='path to feature model before')
    parser.add_argument('feature_model_after', help='path to feature model after')
    parser.add_argument('commit_target', help='commit for final feature model')
    parser.add_argument('-v', '--verbosity', help='sets logging level', action='count', default=0)
    parser.add_argument('-o', '--output', help='path of output fm')
    parser.add_argument('-d', '--direct', help='directly create diff between start and target commits',
                        action='store_true')
    parser.add_argument('--clangarg', help='args passed to clang', action='append')
    args = parser.parse_args()
    levels = [logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
    logger.setLevel(levels[args.verbosity])
    return args


if __name__ == '__main__':
    main()

logging.shutdown()
