What I want this to be, practically:

An interactive CLI as the main entry point, probably using [[CLI prompt Library Choices|a library]].

It should probably look something like this:

```shell-session
$ exosphere

  ___                 _                
 | __|_ _____ _ __ __| |_  ___ _ _ ___ 
 | _|\ \ / _ \ '_ (_-< ' \/ -_) '_/ -_)
 |___/_\_\___/ .__/__/_||_\___|_| \___|
             |_|                       
        Version x.y
        
EXOSPHERE> 
```

## Core Features

The core features that I want at first are basically:

* [[Config System|A simple host inventory and configuration system]]
* [[Dashboard|A "dashboard" comand that reports the state of inventory systems]]
* [[Patch Management|A system for fetching and displaying the state of pending system updates]]

