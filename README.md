# MouseFox

A framework for multiplayer Python games using [Kvex](
https://github.com/ArielHorwitz/kvex) and [pgnet](
https://github.com/ArielHorwitz/pgnet).


## Getting started
```bash
pip install git+ssh://git@github.com/ArielHorwitz/mousefox.git
```

For now, the best way to get started is to copy the built-in [tictactoe](
https://github.com/ArielHorwitz/mousefox/tree/master/tictactoe) example into
your project and modify from there.

Create a script entry point:
```python
import tictactoe

tictactoe.run()
```

Then simply run the GUI app:
```bash
python main.py
```

## Testing multiplayer
It is recommended to test multiplayer locally by running one instance locally
(uncheck "online" in the connection screen), and then open as many other
instances as you wish that connect to server IP address "localhost".


## Testing online
The server can run on any home computer, as long as you forward the correct
port on your network. Run the server as follows:

```bash
python main.py server --listen-globally --admin-password PASSWORD
```
