from bisect import bisect

import settings


RATING_LEVELS = ['newbie', 'amateur', 'expert', 'candidate-master', 'master', 'grandmaster', 'target']
RATING_VALUES = [1000, 1300, 1600, 1900, 2400, 3000]


def rating_to_role_name(rating):
    if rating is None:
        return 'unrated'
    return RATING_LEVELS[bisect(RATING_VALUES, rating)]


def get_role_id(guild, role_name):
    if guild is not None and guild.id in settings.ROLE_IDS:
        role_id = settings.ROLE_IDS[guild.id].get(role_name)
        if role_id is not None:
            return guild.get_role(role_id)
    return None


def guild_rating_roles(guild):
    roles = [get_role_id(guild, role_name) for role_name in RATING_LEVELS + ['unrated']]
    return [r for r in roles if r is not None]


def user_to_members(bot, user):
    for guild_id in settings.GUILDS:
        guild = bot.get_guild(guild_id)
        if guild is None:
            continue
        member = guild.get_member(user.discord_id)
        if member is None:
            continue
        yield guild, member


async def update_account_rating_roles_for_guilds(bot, user):
    for guild, member in user_to_members(bot, user):
        await member.remove_roles(*guild_rating_roles(guild), reason='Rating change')
        rating_role = get_role_id(guild, rating_to_role_name(user.rating))
        if rating_role is not None:
            await member.add_roles(rating_role, reason='Rating change')


async def link_account_for_guilds(bot, user):
    for guild, member in user_to_members(bot, user):
        roles = [
            get_role_id(guild, 'verified'),
            get_role_id(guild, rating_to_role_name(user.rating)),
        ]
        roles = [r for r in roles if r is not None]
        await member.add_roles(*roles, reason=f'Linked account with {user.username}')
        try:
            await member.edit(nick=user.username, reason=f'Linked account with {user.username}')
        except Exception:
            import traceback
            traceback.print_exc()


async def link_account(bot, user, data):
    user.dmoj_id = data['id']
    user.username = data['username']
    user.rating = data['rating']
    user.save()
    await link_account_for_guilds(bot, user)


async def unlink_account_for_guilds(bot, user):
    for guild, member in user_to_members(bot, user):
        roles = [get_role_id(guild, 'verified')] + guild_rating_roles(guild)
        roles = [r for r in roles if r is not None]
        await member.remove_roles(*roles, reason='Unlinked account')


async def unlink_account(bot, user):
    user.dmoj_id = None
    user.username = None
    user.rating = None
    user.save()
    await unlink_account_for_guilds(bot, user)
