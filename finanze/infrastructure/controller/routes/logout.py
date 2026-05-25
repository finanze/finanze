from domain.use_cases.user_logout import UserLogout


async def logout(user_logout_uc: UserLogout):
    await user_logout_uc.execute()
    return "", 204
