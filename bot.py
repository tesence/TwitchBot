import config
from twitchio.ext import commands


class Bot(commands.TwitchBot):

    def __init__(self):
        super().__init__(irc_token=config.IRC_TOKEN, client_id=config.CLIENT_ID, nick=config.BOT_USERNAME,
                         prefix=config.PREFIX, initial_channels=config.CHANNELS)

    @commands.twitch_command(name='pyramid')
    async def pyramid(self, ctx, char="LUL", size=4):
        pyramid = [" ".join([char] * (i + 1 if i < size else 2 * size - (i + 1))) for i in range(2 * size - 1)]
        for line in pyramid:
            await ctx.send(line)


bot = Bot()
bot.run()
