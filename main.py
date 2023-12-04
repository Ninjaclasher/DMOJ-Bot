import datetime
import hashlib
from functools import wraps
from typing import Optional

import discord
from discord import app_commands

import api
import settings
import utils
from models import database, User


class DMOJBot(discord.Client):
    def __init__(self, *, intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        for id in settings.GUILDS:
            guild = discord.Object(id=id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)


intents = discord.Intents.default()
intents.members = True
bot = DMOJBot(intents=intents)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')


# UNUSED
# linked can be:
# - None: do not care
# - False: must not be linked
# - True: must be linked
def command_with_user(linked=True):
    def decorator(f):
        @wraps(f)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            db_user = User.get_or_create(discord_id=interaction.user.id)[0]
            if linked is not None and db_user.is_linked != linked:
                if db_user.is_linked:
                    await interaction.response.send_message('You are already linked! /unlink first.')
                else:
                    await interaction.response.send_message('You are not linked.')
            await f(interaction, db_user, *args, **kwargs)
        return wrapper
    return decorator


@bot.tree.command()
@app_commands.describe(
    username='Your DMOJ username',
)
async def link(interaction: discord.Interaction, username: str):
    '''Links your Discord account with a DMOJ account.'''
    db_user = User.get_or_create(discord_id=interaction.user.id)[0]

    if db_user.is_linked:
        await interaction.response.send_message('You are already linked! /unlink first.')
        return

    hash_key = hashlib.sha256(
        (settings.SECRET_KEY + '/' + username.lower() + '/' + str(db_user.discord_id)).encode()
    ).hexdigest()

    await interaction.response.defer()
    user_about = await api.get_user_about(username)
    if user_about is None:
        await interaction.followup.send(f'{username} does not exist!')
        return

    if hash_key not in user_about.text:
        await interaction.followup.send(
            f'Please add `{hash_key}` anywhere in your about: https://dmoj.ca/edit/profile and run the command again'
        )
        return

    response = await api.get_user(username)
    if response is None:
        await interaction.followup.send(f'{username} does not exist!')
        return

    with database.atomic():
        for u in User.select().where(User.dmoj_id == response['id']):
            await utils.unlink_account(bot, u)
        await utils.link_account(bot, db_user, response)

    await interaction.followup.send('Linked!')


@bot.tree.command()
async def unlink(interaction: discord.Interaction):
    '''Unlink your Discord account with your DMOJ account.'''
    db_user = User.get_or_create(discord_id=interaction.user.id)[0]
    if not db_user.is_linked:
        await interaction.response.send_message('You are not linked.')
        return
    await interaction.response.defer()
    await utils.unlink_account(bot, db_user)
    await interaction.followup.send('Unlinked!')


@bot.tree.command()
@app_commands.describe(
    member='The member whose link to manage',
    username='Update the member to be linked to this username, or unset if to unlink',
)
@app_commands.default_permissions(manage_roles=True)
@app_commands.checks.has_permissions(manage_roles=True)
async def manage_link(interaction: discord.Interaction, member: discord.Member, username: Optional[str]):
    """Manages a user's DMOJ link"""
    db_user = User.get_or_create(discord_id=member.id)[0]
    await interaction.response.defer()
    if username is None:
        await utils.unlink_account(bot, db_user)
        await interaction.followup.send(f'Unlinked {member}.')
    else:
        response = await api.get_user(username)
        if response is None:
            await interaction.followup.send(f'{username} does not exist!')
            return
        with database.atomic():
            for u in User.select().where(User.dmoj_id == response['id']):
                await utils.unlink_account(bot, u)
            await utils.link_account(bot, db_user, response)
        await interaction.followup.send(f'Updated {member} to be linked to {username}')


@bot.tree.command()
@app_commands.describe(member='The member to view; defaults to the user who uses the command')
async def whois(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    '''See who a member is.'''
    member = member or interaction.user
    db_user = User.get_or_create(discord_id=member.id)[0]
    if not db_user.is_linked:
        await interaction.response.send_message('This user is not linked.')
        return

    embed = discord.Embed(colour=settings.BOT_COLOUR)
    embed.description = 'Who is {}?'.format(member.mention)
    embed.add_field(name='Username', value=db_user.username or 'Unknown')
    embed.add_field(name='Rating', value=db_user.rating or 'Unrated')
    await interaction.response.send_message(embed=embed)


@bot.tree.command()
@app_commands.describe(force_roles='Force update rating roles')
@app_commands.default_permissions(manage_roles=True)
@app_commands.checks.has_permissions(manage_roles=True)
async def update_users(interaction: discord.Interaction, force_roles: bool):
    '''Update all users, including usernames and ratings'''
    await interaction.response.send_message('Updating...')
    data = {user['id']: user for user in await api.get_users()}
    to_update = []
    with database.atomic():
        for user in User.select():
            if user.dmoj_id not in data:
                #await util.unlink_account(bot, user)
                continue

            user_data = data[user.dmoj_id]
            changed_username = False
            changed_rating = False

            if user_data['username'] != user.username:
                user.username = user_data['username']
                changed_username = True
            if user_data['rating'] != user.rating:
                user.rating = user_data['rating']
                changed_rating = True

            if changed_rating or force_roles:
                await utils.update_account_rating_roles_for_guilds(bot, user)

            if changed_rating or changed_username:
                to_update.append(user)
        User.bulk_update(to_update, fields=[User.username, User.rating], batch_size=50)
    await interaction.channel.send('Updated all users.')


@bot.tree.command()
@app_commands.describe(key='The contest key')
async def postcontest(interaction: discord.Interaction, key: str):
    '''Add yourself to the postcontest channel for the specified contest'''
    if interaction.guild is None:
        return
    db_user = User.get_or_create(discord_id=interaction.user.id)[0]
    if not db_user.is_linked:
        await interaction.response.send_message('You are not linked.', ephemeral=True)
        return
    await interaction.response.defer()
    contest = await api.get_contest(key)
    if contest is None:
        await interaction.followup.send('Contest not found.', ephemeral=True)
        return
    _now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

    success = False
    for user_data in contest['rankings']:
        if user_data['user'].lower() == db_user.username.lower():
            end_time = datetime.datetime.fromisoformat(user_data['end_time'])
            if _now >= end_time:
                try:
                    role = next(r for r in interaction.guild.roles if r.name == f'postcontest {key.lower()}')
                except StopIteration:
                    pass
                else:
                    await interaction.user.add_roles(role)
                    success = True
            break

    if success:
        await interaction.followup.send('Added!', ephemeral=True)
    else:
        await interaction.followup.send(f"Cannot add you to {key}'s postcontest.", ephemeral=True)


if settings.ERROR_CHANNEL_ID is not None:
    @bot.tree.error
    async def on_error(interaction, error):
        import traceback
        channel = bot.get_channel(settings.ERROR_CHANNEL_ID)
        embed = discord.Embed(
            colour=settings.BOT_COLOUR,
            title='ERROR',
            description='```{}```'.format(traceback.format_exc()[:3000]),
        )
        await channel.send(embed=embed)


database.connect()
database.create_tables([User])
bot.run(settings.DISCORD_TOKEN)
