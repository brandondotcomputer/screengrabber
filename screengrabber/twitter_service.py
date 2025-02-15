from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional

import requests

from screengrabber.helpers import format_number


@dataclass
class FormattedTweetStats:
    reply_count: str
    retweet_count: str
    like_count: str


@dataclass
class Tweet:
    user_name: str
    handle: str
    verified: bool
    avatar_img_url: str

    date_epoch: str
    reply_count: Optional[int] = None
    retweet_count: Optional[int] = None
    like_count: Optional[int] = None
    view_count: Optional[str] = None
    tweet_text: Optional[str] = None

    def formatted_date(self) -> str:
        tweet_date = datetime.fromtimestamp(self.date_epoch)
        return tweet_date.strftime("%-I:%M %p · %b %-d, %Y")

    def formatted_stats(self) -> FormattedTweetStats:
        return FormattedTweetStats(
            **{
                "reply_count": format_number(self.reply_count),
                "retweet_count": format_number(self.retweet_count),
                "like_count": format_number(self.like_count),
            }
        )

    def as_dict(self) -> dict:
        # Get base fields using dataclass asdict
        base_dict = asdict(self)

        # Add formatted fields
        base_dict.update(
            {
                "formatted_date": self.formatted_date(),
                "formatted_stats": asdict(self.formatted_stats()),
            }
        )

        return base_dict


class TwitterService:
    def __init__(self):
        pass

    def get_tweet_info(self, account: str, status_id: str) -> Tweet:
        response = requests.get(
            f"https://api.vxtwitter.com/{account}/status/{status_id}"
        )
        data = response.json()

        return Tweet(
            user_name=data["user_name"],
            handle=f"@{data['user_screen_name']}",
            verified=True,
            avatar_img_url=data["user_profile_image_url"],
            tweet_text=data["text"],
            date_epoch=data["date_epoch"],
            view_count=data.get("view_count", None),
            reply_count=data.get("replies", None),
            retweet_count=data.get("retweets", None),
            like_count=data.get("likes", None),
        )
