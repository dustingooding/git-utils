#!/usr/bin/env python

import argparse
import errno
import os
import shutil
import stat


def delete_file_or_directory(target):
    """ Deletes (with prejudice) a file or directory (recursively). Read-only files/directories are first set to writable, then deleted.

    @type target string
    @param target /path/to/dir or /path/to/file.ext

    @rtype bool
    @returns True if file/directory is deleted (or not there to begin with).
    """

    def make_writeable_and_try_again(func, path, exc_info):
        """ Error callback for shutil.rmtree.
            Sets parent directory writable (if necessary) and the file itself writeable, then reexecutes the function that previously failed. """

        if func in (os.rmdir, os.remove) and exc_info[1].errno == errno.EACCES:
            # ensure parent directory is writeable too
            pardir = os.path.abspath(os.path.join(path, os.path.pardir))
            if not os.access(pardir, os.W_OK):
                os.chmod(pardir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

            os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 0777
            func(path)
        else:
            raise

    if os.path.exists(target):
        if os.path.isfile(target):
            os.remove(target)
        else:
            try:
                shutil.rmtree(target, ignore_errors=False, onerror=make_writeable_and_try_again)
            except OSError:
                return False

    return True


def print_and_run(cmd):
    print '>>>', cmd
    os.system(cmd)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Split a subdirectory out of one git repo into the root of a new repo.')
    parser.add_argument('-s', '--source-repo', type=str, required=True, help='The path to the source repository.')
    parser.add_argument('-d', '--dest-repo', type=str, required=True, help='The path to the destination repository.')
    parser.add_argument('--subdir', type=str, nargs='+', required=True, help='The directory name to create a subtree from, including previous names (renames), in reverse history order.')
    args = parser.parse_args()

    # prep subdir arguments for later
    cat_subdirs = '|'.join(args.subdir)
    slashcat_subdirs = '|'.join('{}\\'.format(x) for x in args.subdir)

    if not os.path.exists(args.source_repo):
        print '>>> MISSING source repo directory'
        exit(1)

    if os.path.exists(args.dest_repo):
        print '>>> Cleaning previous destination repo directory...'
        delete_file_or_directory(args.dest_repo)

    # make a copy of the source repo
    print_and_run('cp -a {} {}'.format(args.source_repo, args.dest_repo))

    # grab all branches
    os.chdir(args.dest_repo)
    print_and_run('git fetch')
    print_and_run('for i in $(git branch -r | sed "s/.*origin\///"); do git branch -t $i origin/$i; done')
    print_and_run('git remote rm origin')

    # remove everything but the subdirs you want to keep and move them to the repo root
    print_and_run('git filter-branch -f --tag-name-filter cat --prune-empty --index-filter \' \
                     git ls-files -z | egrep -zv  "^({})" | xargs -0 -r git rm --cached -q \n\
                     git ls-files -s | sed -e "s-\\t\\({})/-\\t-" | sort | uniq | GIT_INDEX_FILE=$GIT_INDEX_FILE.new git update-index --index-info && mv $GIT_INDEX_FILE.new $GIT_INDEX_FILE \
                     \' -- --all'.format(cat_subdirs, slashcat_subdirs))

    # remove all "empty" merge commits (using ruby because that's how I found it...)
    with open('/tmp/subtree.rb', 'w') as f:
        f.write('#!/usr/bin/env ruby\n')
        f.write('old_parents = gets.chomp.gsub("-p ", " ")\n')
        f.write('new_parents = old_parents.empty? ? [] : `git show-branch --independent #{old_parents}`.split\n')
        f.write('puts new_parents.map{|p| "-p " + p}.join(" ")\n')
    os.chmod('/tmp/subtree.rb', stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 0777
    print_and_run('git filter-branch -f --tag-name-filter cat --prune-empty --parent-filter /tmp/subtree.rb -- --all')
    delete_file_or_directory('/tmp/subtree.rb')

    # clean up left overs
    print_and_run('git reset --hard')
    print_and_run('git for-each-ref --format="%(refname)" refs/original/ | xargs -n 1 git update-ref -d')
    print_and_run('git reflog expire --expire=now --all')
    print_and_run('git gc --aggressive --prune=now')
