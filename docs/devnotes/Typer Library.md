https://github.com/fastapi/typer

Not for interactive use at first glance, but if I can make Click work, I can make this work, on paper.

This library is based on Click and actually just derives arguments from python typed arguments to functions, which is essentially ideal.

It's made by the FastAPI people, and is worth exploring a bit.

It also does this wild shit: 
https://typer.tiangolo.com/tutorial/one-file-per-command/

Which is incredible to structure a project.

## Stop the presses

It turns out:

* The whole of Click is accessible and usable from within Typer
* You can use Click extensions with Typer
* There's a handful of [[Click REPL Libraries]]