# VHS Tape file used for recording the demo gif
# Will probably need hacked at during big changes.

# This is not exactly reproducible, as it runs against a live setup.
# Additionally, timing is absolutely not deterministic.

# This should be ran via the poe task 'demo' through uv to ensure
# the venv is correctly setup during the run, i.e.
#
#   $ uv run poe demo
#

Output demo.gif

Require echo
Require uv

Set Shell "bash"
Set Theme "Catppuccin Mocha"
Set FontSize 13
Set FontFamily "Cascadia Code"
Set Width 700
Set Height 500
Set Padding 5

Hide
Type "export PS1='> '"
Enter
Type "clear"
Enter
Show

Type "exosphere"
Enter

## CLI demo ##

# Hang at banner for a time
Sleep 3s

# Show inventory
Type "inventory "
Sleep 250ms
Type "status"
Sleep 500ms
Enter
Sleep 2s

# Show host okami
Type "host show "
Sleep 500ms
Type "okami"
Sleep 500ms
Enter
Sleep 3s

# Show host with security updates
Type "inventory status --"
Tab
Sleep 1s
Type "sec"
Tab
Sleep 500ms
Enter
Sleep 2s

# Start UI
Type "ui start"
Sleep 500ms
Enter

# Hang on dashboard for a time
Sleep 3s

#Ping Hosts
Type "P"
Sleep 6s

# Switch to inventory
Type "i"
Sleep 500ms
Down
Sleep 500ms
Down
Sleep 500ms
Up 2
Sleep 2s

# Filter hosts with security updates
Ctrl+F
Down
Sleep 500ms
Down
Sleep 2s
Enter

# Wait for toaster to die down
Sleep 6s

# Select first host
Enter

# Look at host Detail
Sleep 2s

# Select second update
Down
Sleep 500ms
Enter

# Look at update panel
Sleep 3s

# Back out to main inventory
Escape
Escape

# Quit
Ctrl+Q

# Quit repl
Ctrl+D

# Quit terminal
Type "exit"
Enter