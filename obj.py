import zlib
import hashlib
import re
from repository import *
import collections

class GitObject(object):
    """ Baseclass for all git objects
    """
    repo = None

    def __init__(self, repo: GitRepository, data=None):
        self.repo = repo

        if data != None:
            self.deserialize(data)
    
    def serialize(self):
        """ This function MUST be implemented by subclasses.
            It must read the object's contents from self.data, a byte string, and do
            whatever it takes to convert it into a meaningful representation.
            What exactly that means depend on each subclass."""
        raise Exception("Unimplemented!")

    def deserialize(self):
        raise Exception("Unimplemented!")

def object_read(repo : GitRepository, sha : str):
    """ Read an object_id from Git repo Return a GitObject whose 
    exact type depends on the object
    """

    path = repo_file(repo, "objects", sha[0:2], sha[2:])
    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())

        # Read object type, note the format will always be [type] followed by an ascii 'space'
        x = raw.find(b' ')
        fmt = raw[0:x]

        y = raw.find(b"\x00", x)
        size = int(raw[x:y].decode("ascii"))
        if size != len(raw)-y-1 :
            raise Exception(f"Malformed object {sha}: bad length")
        
        #pick construtor
        if   fmt==b'commit' : cls=GitCommit
        elif fmt==b'tree'   : cls=GitTree
        elif fmt==b'tag'    : cls=GitTag
        elif fmt==b'blob'   : cls=GitBlob
        else:
            raise Exception(f"Unknown type {fmt.decode('ascii')} for object {sha}")
    
        return cls(repo, raw[y+1:])

def object_find(repo, name, fmt=None, follow=True):
    """ name resolution function since we can reference by full hash, short hash, tags...
    """
    sha = object_resolve(repo, name)

    if not sha:
        raise Exception("No such reference {0}.".format(name))

    if len(sha) > 1:
        raise Exception("Ambiguous reference {0}: Candidates are:\n - {1}.".format(name,  "\n - ".join(sha)))

    if not fmt:
        return sha

    while True:
        obj = object_read(repo, sha)

        if obj.fmt == fmt:
            return sha

        if not follow:
            return None

        # Follow tags
        if obj.fmt == b'tag':
            sha = obj.kvlm[b'object'].decode("ascii")
        elif obj.fmt == b'commit' and fmt == b'tree':
            sha = obj.kvlm[b'tree'].decode("ascii")
        else:
            return None

def object_resolve(repo, name):
    candidates = list()
    hashRE = re.compile(r"^[0-9A-Fa-f]{1,16}$")
    smallHashRE = re.compile(r"^[0-9A-Fa-f]{1,16}$")

    if not name.strip():
        return None
    
    if name == "HEAD":
        return [ref_resolve(repo, "HEAD")]
    
    if hashRE.match(name):
        if len(name) == 40:
            return [name.lower()] # complete hash
        elif len(name) >= 4:
            name = name.lower()
            prefix = name[0:2]
            path = repo_dir(repo, "objects", prefix, mkdir=False)
            if path:
                rem = name[2:]
                for f in os.listdir(path):
                    if f.startswith(rem):
                        candidates.append(prefix + f)
    return candidates


def object_write(obj, actually_write=True):
    """ Compute insert header, compute hash,  
    """
    data = obj.serialize()
    result = obj.fmt + b" " + str(len(data)).encode() + b"\x00" + data
    sha = hashlib.sha1(result).hexdigest()

    if actually_write:
        path=repo_file(obj.repo, "objects", sha[0:2], sha[2:], mkdir=actually_write)

        with open(path, 'wb') as f:
            f.write(zlib.compress(result))
    
    return sha

class GitBlob(GitObject):
    fmt=b'blob'

    def serialize(self):
        return self.blob_data
    
    def deserialize(self, data):
        self.blob_data = data

def object_hash(fd, fmt, repo=None):
    data = fd.read()

    # Choose constructor depending on
    # object type found in header.
    if   fmt==b'commit' : obj=GitCommit(repo, data)
    elif fmt==b'tree'   : obj=GitTree(repo, data)
    elif fmt==b'tag'    : obj=GitTag(repo, data)
    elif fmt==b'blob'   : obj=GitBlob(repo, data)
    else:
        raise Exception("Unknown type %s!" % fmt)

    return object_write(obj, repo)



def kvlm_parse(raw, start : int=0, dct=None):
    

    # use an ordered dict becuase in serialization it matters
    if not dct:
        dct = collections.OrderedDict()

    # search for next space and next new line
    spc = raw.find(b' ', start)
    nl = raw.find(b'\n', start)
    
    # base case
    # if newline appears first, we assume blankline
    # blank line means remainder of data is message
    # in example, this would be dct[b''] => Create first draft
    if (spc < 0) or (nl < spc):
        assert(nl == start)
        dct[b''] = raw[start+1:]
        return dct
    
    # recurse
    # read key val pair, and recurse for next
    key = raw[start:spc]

    # Find the end of the value.  Continuation lines begin with a
    # space, so we loop until we find a "\n" not followed by a space.
    end = start
    while True:
        end = raw.find(b'\n', end+1)
        if raw[end+1] != ord(' '): break

    # Grab the value and drop the leading space on continuation lines
    value = raw[spc+1:end].replace(b'\n ', b'\n')

    # Don't overwrite existing data contents
    # if the key exists, then we turn it into a list,
    #    if it isn't already a list, turn it into one
    if key in dct:
        if type(dct[key]) == list:
            dct[key].append(value)
        else:
            dct[key] = [ dct[key], value ]
    else:
        dct[key]=value
    
    return kvlm_parse(raw, start=end+1, dct=dct)

def kvlm_serialize(kvlm: dict):
    # Serialize to string in the same order 
    ret = b''

    # Output fields
    for k in kvlm.keys():
        # skip the message itself
        if k == b'': continue
        val = kvlm[k]
        # Normalize to list
        if type(val) != list:
            val = [val]
        
        for v in val:
            ret += k + b' ' + (v.replace(b'\n', b'\n ')) + b'\n'
    
    ret += b'\n' + kvlm[b'']

    return ret

class GitCommit(GitObject):
    fmt = b'commit'
    def deserialize(self, data):
        self.kvlm = kvlm_parse(data)
    
    def serialize(self):
        return kvlm_serialize(self.kvlm)

class GitTreeLeaf(object):
    def __init__(self, mode, path, sha):
        self.mode = mode
        self.path = path
        self.sha = sha
    

def tree_parse_one(raw, start=0):
    """ Create a parser that extracts a single record and returns the parsed data
        along with where it leaves off
    """
    # Find the space terminator
    x = raw.find(b' ', start)
    assert(x-start == 5 or x-start==6)

    mode = raw[start:x]

    # get path
    y = raw.find(b'\x00', x)
    path = raw[x+1:y]

    # read sha and convert into hex string
    sha = hex(
        int.from_bytes(
            raw[y+1:y+21], "big"
        )
    )[2:] # hex adds 0x in front

    return y+21, GitTreeLeaf(mode, path, sha)

def tree_parse(raw):
    pos = 0
    max = len(raw)
    ret = list()
    while pos < max:
        pos, data = tree_parse_one(raw, pos)
        ret.append(data)
    
    return ret

def tree_serialize(obj):
    ret = b''
    for i in obj.items:
        ret += i.mode
        ret += b' '
        ret += i.path
        ret += b'\x00'
        sha = int(i.sha, 16)
        ret += sha.to_bytes(20, byteorder="big")
    return ret

class GitTree(GitObject):
    fmt = b'tree'

    def deserialize(self, data):
        self.items = tree_parse(data)
    
    def serialize(self):
        return tree_serialize(self)

class GitTag(GitCommit):
    fmt = b'tag'
