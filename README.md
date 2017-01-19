![LICENSE](https://img.shields.io/badge/LICENSE-BSD-YELLOW.svg)
![PYTHON3.5.2](https://img.shields.io/badge/Python-3.5.2-red.svg) 
![Linux](https://img.shields.io/badge/Linux-%E2%9C%93-brightgreen.svg)


#MYSYNC

inotify-tools and rsync based project file synchronization tool. Optimized for git project 


##PREREQUISITE

###inotify-tools

    sudo apt-get install inotify-tools

###rsync

Should be exists on modem Linux system

###Python 3.5.2+

[http://www.python.org](http://www.python.org "www.python.org")

###Shared ssh connection for remote target(OPTIONAL)

    cat ~/.ssh/config 
    Host *
        ControlMaster auto
    ControlPath ~/.ssh/control:%h:%p:%r


###SYNOPSIS

    mysync.py -h
    usage: mysync [-h] --local_dir LOCAL_DIR --target_dir TARGET_DIR [--remote]
                  [--ssh_tunnel_port SSH_TUNNEL_PORT] [--gitignore] [--init]
                  [--dry_run]
    
    optional arguments:
      -h, --help            show this help message and exit
      --local_dir LOCAL_DIR
                            local_dir(Only on this machine)
      --target_dir TARGET_DIR
                            target_dir(On this machine or remote machine)
      --remote              If the target_dir is on remote machine, use this flag
      --ssh_tunnel_port SSH_TUNNEL_PORT
                            ssh tunnel port option
      --gitignore           Ignore the file in local_dir/.gitignore
      --init                List all the files in local dir and sync to target
      --dry_run             Dry run, not really do the sync
    
####Note:

.git directory is never synced to avoid complex stall issues

Currently we can not sync file delete/rename


###EXAMPLE

####1. Remote GIT working directory 

If your project is in remote and .git file is on remote server. Tar your current branch and download to local

    git archive --format=tar --prefix=project/ master | gzip >master.tar.gz

Extract the package and do an initial sync

    mysync.py --local_dir=/home/me/project/ --target_dir=me@remoteserver:/home/me/theproject/ --remote --ignore --init

If everything looks fine remote the parameter --init and run again

    mysync.py --local_dir=/home/me/project/ --target_dir=me@remoteserver:/home/me/theproject/ --remote --ignore

**Note, use ssh_key or shared ssh connection to avoid password prompt**


####2. Local GIT working directory

If your git working directory is on local server, every thing is simpler.
Make sure target directory exists on remote server

    mysync.py --local_dir=/home/me/project/ --target_dir=me@remoteserver:/home/me/theproject/ --remote --ignore --init

If everything looks fine remote the parameter --init and run again

    mysync.py --local_dir=/home/me/project/ --target_dir=me@remoteserver:/home/me/theproject/ --remote --ignore


## License


My Sync

Written By Boying Xu

THE "BSD" LICENSE
-----------------

>    Copyright (c) 2017, Boying Xu
>    All rights reserved.

>    Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

>    1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

>    2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

>    3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

>    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUB
>    STITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.