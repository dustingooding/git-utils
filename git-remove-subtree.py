#!/usr/bin/env python

import argparse
import os


def print_and_run(cmd):
    print '>>>', cmd
    os.system(cmd)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Remove subdirectories from a git repo.')
    parser.add_argument('-r', '--repo', type=str, required=True, help='The path to the repository.')
    parser.add_argument('--subdir', type=str, nargs='+', required=True, help='The directory name to create a subtree from, including previous names (renames), in reverse history order.')
    args = parser.parse_args()

    if not os.path.exists(args.repo):
        print '>>> MISSING source repo directory'
        exit(1)

    # grab all branches
    os.chdir(args.repo)

    for subdir in args.subdir:
        print_and_run('git filter-branch -f --tag-name-filter cat --prune-empty --index-filter \' \
                         git rm -rf --cached --ignore-unmatch {}/ \
                         \' -- --all'.format(subdir))

    # clean up left overs
    print_and_run('git reset --hard')
    print_and_run('git for-each-ref --format="%(refname)" refs/original/ | xargs -n 1 git update-ref -d')
    print_and_run('git reflog expire --expire=now --all')
    print_and_run('git gc --aggressive --prune=now')
