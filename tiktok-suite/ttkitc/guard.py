"""节奏控制：每日限额 + 动作间隔 cooldown。

settings 键：daily_reply_limit / daily_follow_limit / daily_dm_limit / cooldown_seconds。
CLI 可用 --no-cooldown 跳过 cooldown 等待。
"""

import time

LIMIT_KEYS = {"reply": "daily_reply_limit", "follow": "daily_follow_limit", "dm": "daily_dm_limit"}


def check_daily_limit(db, action_type):
    """检查当日该动作计数是否超限。返回 None(通过) 或 {status:'error', platform_msg:'daily_limit'}。"""
    key = LIMIT_KEYS.get(action_type)
    if not key:
        return None
    limit = db.settings.get_int(key, 0)
    if limit <= 0:
        return None
    if db.interactions.count_today(action_type) >= limit:
        return {"status": "error", "platform_msg": "daily_limit"}
    return None


def cooldown(db, enabled=True):
    """动作间隔 sleep。enabled=False（CLI --no-cooldown）时跳过。"""
    if not enabled:
        return 0
    secs = db.settings.get_int("cooldown_seconds", 0)
    if secs > 0:
        time.sleep(secs)
    return secs
