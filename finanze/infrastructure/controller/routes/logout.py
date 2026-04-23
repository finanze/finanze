from domain.data_init import AlreadyLockedError
from domain.use_cases.user_logout import UserLogout


async def logout(user_logout_uc: UserLogout):
    try:
        await user_logout_uc.execute()
        return "", 204
    except AlreadyLockedError:
        return "", 204
