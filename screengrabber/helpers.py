from enum import Enum
from typing import Any


class Visitor(Enum):
    DISCORD = "discordbot"
    SLACK = "slackbot"
    TELEGRAM = "telegrambot"
    TWITTER = "twitterbot"
    FACEBOOK = "facebookexternalhit"
    GOOGLE = "googlebot"
    BING = "bingbot"
    WHATSAPP = "whatsapp"
    LINKEDIN = "linkedinbot"
    UNKNOWN = "unknown"


def identify_visitor(user_agent: str) -> Visitor:
    user_agent = user_agent.lower()

    for visitor in Visitor:
        if visitor == Visitor.UNKNOWN:
            continue
        if visitor.value in user_agent:
            return visitor

    return Visitor.UNKNOWN


# Example usage
# visitor = identify_visitor(request.headers.get("User-Agent"))
# print(visitor.name)


def format_number(num: Any, decimals: int = 1) -> str:
    if not isinstance(num, (int, float)):
        return "?"

    if num >= 1000000000:
        return f"{num / 1000000000:.{decimals}f}B"
    if num >= 1000000:
        return f"{num / 1000000:.{decimals}f}M"
    if num >= 1000:
        return f"{num / 1000:.{decimals}f}K"
    return str(num)
