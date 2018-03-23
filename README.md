# Twitch IRC Bot

A Twitch IRC Bot based on asynchronous programming (asyncio)
- Sends pyramids
- Sends follow alerts

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

# TWITCH IRC
TWITCH_IRC_HOST = "irc.twitch.tv"
TWITCH_IRC_PORT = 6667
TWITCH_IRC_BOTNAME = <bot name in lowercase>
TWITCH_IRC_PASSWORD = <chat token>
TWITCH_IRC_CHANNEL = <channel the bot will be connected to in lowercase>

# TWITCH API
TWITCH_API_URL = "https://api.twitch.tv/kraken/"
TWITCH_API_ACCEPT = "application/vnd.twitchtv.v5+json"
TWITCH_API_CLIENT_ID = <twitch client id>

# COMMANDS
VALID_COMMANDS = ["pyramid"]
DEFAULT_PYRAMID_SYMBOL = <default pyramid char>
DEFAULT_PYRAMID_SIZE = <default pyramid size>  # size is thresholded at 5

# EVENTS
VALID_EVENTS = ["follows"]
FOLLOW_MESSAGE = "Thank you {} for the follow!"
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
