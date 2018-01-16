# Twitch IRC Bot

A Twitch IRC Bot based on asynchronous programming (asyncio)
- Sends pyramids

### Create a Twitch account for the bot

Create a Twitch account you will control with the bot: https://www.twitch.tv

The account nickname will be the name used by the bot.

Connect to twitch using the bot account and generate a chat token for the bot

https://twitchapps.com/tmi/

### Setup environment (Python 3.5+ required)

#### Windows
```
cd <project folder>
virtualenv .venv
.venv/Script/pip.exe install -r requirements.txt
```

#### Linux
```
cd <project folder>
virtualenv .venv
.venv/bin/pip install -r requirements.txt
```



### Create a `cfg.py` file

Create the file `cfg.py` at the root of the project directory and fill it as follow:

```
# cfg.py
# Configurations variables

HOST = "irc.twitch.tv"
PORT = 6667
NICK = <bot name in lowercase>
PASS = <chat token>
CHAN = <channel the bot will be connected to in lowercase>

VALID_COMMANDS = ["pyramid"]

DEFAULT_PYRAMID_SYMBOL = <default pyramid char>
DEFAULT_PYRAMID_SIZE = <default pyramid size>  # size is thresholded at 5
```
### Run the bot

In the project folder, run:

#### Windows
```
.venv/Script/python.exe main.py
```

#### Linux
```
.venv/bin/python main.py
```
