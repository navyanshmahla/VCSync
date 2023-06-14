# VCSync

VCSync is a lightweight and robust version control system inspired by Git. It offers a seamless experience for managing your project's source code, providing familiar and essential Git features such as init, add, commit, rebase, and stash.

With VCSync, you can effortlessly track changes to your codebase, create branches, merge changes, and collaborate effectively with other developers. The project aims to replicate the core functionalities of Git while maintaining simplicity and ease of use.

*Just a thing:* While testing I found that collision was observed because of the use of SHA-1. I've used SHA-1 for hashing but please note that Git no more uses SHA-1 and has switched to its hardened variant. 


## How to use this:

Well the ```vcsync``` file that you are seeing in this repo is actually an executable and executes the main ```vcsync.py``` file. It's not yet a full fledged library for version control so you'll still have to hardcore certain things by writing custom path to ```vcsync``` file everytime you want to use VCSync. 

In order to initialize a VCSync repo: 

```<relative/path/to/vcsync/executable> init```

