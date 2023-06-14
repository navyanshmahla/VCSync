import argparse
import collections
import configparser
import hashlib
import os
import re
import sys
import zlib
import pathlib
from typing import Optional

class GitRepository(object):
    """ Git repository abstraction
    """
    worktree = None
    gitdir = None
    conf = None

    def __init__(self, path : str, force : bool =False):
        """ Checks for valid repo before creation
        """
        self.worktree = path
        self.gitdir = os.path.join(path, ".vcsync")
        
        if not (force or os.path.isdir(self.gitdir)):
            raise Exception(f"Not a Git repository {path}")

        # Read config
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, "config")

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuration file missing")

        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception(f"Unsupported repositoryformatversion {vers}")

def repo_path(repo : GitRepository, *path) -> Optional[str]:
    """ Compute path under repo's gitdir
    """
    return os.path.join(repo.gitdir, *path)

def repo_dir(repo : GitRepository, *path, mkdir: bool = False) -> Optional[str]:
    """ Same as repo_path, but makes create gitdir if mkdir present
    """
    path = repo_path(repo, *path)

    if os.path.exists(path):
        if os.path.isdir(path):
            return path
        else:
            raise Exception(f"Not a directory {path}")
    
    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None
    
def repo_file(repo : GitRepository, *path, mkdir : bool = False) -> Optional[str]:
    """ Same as repo_path, but will create dirname(path) if absent
    """
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)

def repo_create(path : str):
    """ Create new repo from path
    """

    repo = GitRepository(path, True) 

    # First check if the path !exist or is empty
    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception(f"{path} is not a directory!")
        if os.listdir(repo.worktree):
            raise Exception(f"{path} is not empty!")
    else:
        os.makedirs(repo.worktree)

    assert(repo_dir(repo, "branches", mkdir=True))
    assert(repo_dir(repo, "objects", mkdir=True))
    assert(repo_dir(repo, "refs", "tags", mkdir=True))
    assert(repo_dir(repo, "refs", "heads", mkdir=True))
    
    #.vcsync/description
    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unnamed repository; edit this file 'description' to name the repository.\n")

    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/master\n")

    with open(repo_file(repo, "config"), "w") as f:
        config = repo_default_config()
        config.write(f)

    return repo

def repo_default_config():
    ret = configparser.ConfigParser()

    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")

    return ret

def repo_find(path : str = ".", required : bool = True):
    """ Create a Git Repository Object with the git files found in the current or any parent dir.
    """
    path = os.path.realpath(path)

    if os.path.isdir(os.path.join(path, ".vcsync")):
        return GitRepository(path)
    
    # If not found, recurse through parents
    parent = os.path.realpath(os.path.join(path, ".."))

    # handle base case, at root:
    if parent == path:
        if required:
            raise Exception("No git directory")
        else:
            return None
    
    # Recurse
    return repo_find(parent, required)


def ref_resolve(repo, ref):
    with open(repo_file(repo, ref), 'r') as fp:
        data = fp.read()[:-1] # drop final \n
    
    if data.startswith("ref: "):
        return ref_resolve(repo, data[5:])
    else:
        return data

def ref_list(repo, path=None):
    if not path:
        path = repo_dir(repo, "refs")
    ret = collections.OrderedDict()

    for f in sorted(os.listdir(path)):
        can = os.path.join(path, f)
        print(can)
        if os.path.isdir(can):
            ref = ref_list(repo, can)
        else:
            ret[f] = ref_resolve(repo, can)
    return ret