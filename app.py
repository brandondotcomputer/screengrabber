import logging
import os
import time
import coloredlogs
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from flask import Flask, render_template, request, current_app, send_file
from io import BytesIO

import requests

from screengrabber import (
    CacheService,
    TwitterService,
    ScreengrabberService,
    StorageService,
)
from screengrabber.helpers import Visitor, identify_visitor

_FORMAT = (
    "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)5d - %(message)s"
)
logging.basicConfig(format=_FORMAT)
coloredlogs.install(level=logging.INFO, fmt=_FORMAT)

app = Flask(__name__)
load_dotenv(override=True)

cache_service = CacheService(db_path=os.getenv("CACHE_DB_PATH"))
twitter_service = TwitterService()
screengrabber_service = ScreengrabberService()
storage_service = StorageService(
    bucket_name=os.getenv("S3_BUCKET_NAME"),
    endpoint_url=os.getenv("S3_ENDPOINT_URL"),
    aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
    region_name=os.getenv("S3_REGION_NAME"),
)


def strftime(date, format="%Y-%m-%d %H:%M:%S"):
    if isinstance(date, str):
        date = datetime.fromisoformat(date.replace("Z", "+00:00"))
    return date.strftime(format)


app.jinja_env.filters["strftime"] = strftime


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/<account_name>/status/<status_id>")
def twitter_tweet(account_name, status_id):
    visitor = identify_visitor(request.headers.get("User-Agent"))

    cached_screengrab = cache_service.get_twitter_screengrab_if_exists(
        account_name, status_id
    )
    if cached_screengrab is not None:
        cache_ttl_minutes = int(os.getenv("CACHE_TTL_MINUTES"))
        if datetime.now(timezone.utc) - cached_screengrab[2] < timedelta(
            minutes=cache_ttl_minutes
        ):
            current_app.logger.info(
                f"CACHE HIT: account_name={account_name}, status_id={status_id}"
            )
            render_url = f"{os.getenv('S3_CUSTOM_DOMAIN')}/{cached_screengrab[3]}"

            if visitor == Visitor.DISCORD:
                return render_template(
                    "service_templates/twitter/discord_embed.html",
                    host=os.getenv("SCREENGRABBER_TWITTER_HOST"),
                    x_url=f"https://x.com/{account_name}/status/{status_id}",
                    render_url=render_url,
                    account=account_name,
                    status_id=status_id,
                )

            else:
                # regular person
                return render_template(
                    "service_templates/twitter/download.html",
                    host=os.getenv("SCREENGRABBER_TWITTER_HOST"),
                    s3_domain=os.getenv("S3_CUSTOM_DOMAIN"),
                    x_url=f"https://x.com/{account_name}/status/{status_id}",
                    render_url=render_url,
                    account=account_name,
                    status_id=status_id,
                    medias=cache_service.get_twitter_screengrab_medias(status_id),
                )

    current_app.logger.info(
        f"CACHE MISS: account_name={account_name}, status_id={status_id}"
    )

    screengrab = screengrabber_service.get_screenshot(
        url=f"http://localhost:{os.getenv('FLASK_PORT')}/render/{account_name}/status/{status_id}",
        options={"width": 600},
    )
    s3_path = f"twitter/renders/{status_id}_{int(time.time())}.jpg"
    storage_service.upload_file(
        file=BytesIO(screengrab),
        key=s3_path,
        content_type="application/jpg",
    )

    try:
        cache_service.add_twitter_screengrab(
            account_name=account_name, status_id=status_id, s3_path=s3_path
        )
    except Exception as e:
        current_app.logger.warning(f"Error inserting into CacheService: {str(e)}")

    try:
        tweet_info = twitter_service.get_tweet_info(account_name, status_id)
        for media in tweet_info.media_extended:
            current_app.logger.info(media)
            response = requests.get(media["url"], stream=True)
            response.raise_for_status()

            media_obj = BytesIO(response.content)
            s3_key = f"twitter/media/{status_id}_{media['url'].split('/')[-1]}"
            storage_service.upload_file(file=media_obj, key=s3_key)

            cache_service.add_twitter_screengrab_media(
                status_id=status_id,
                s3_path=s3_key,
                source_url=media["url"],
                media_type=media["type"],
            )
    except Exception as e:
        current_app.logger.warning(
            f"Error inserting twitter_screengrab_media into CacheService: {str(e)}"
        )

    render_url = f"{os.getenv('S3_CUSTOM_DOMAIN')}/{s3_path}"

    if visitor == Visitor.DISCORD:
        return render_template(
            "service_templates/twitter/discord_embed.html",
            host=os.getenv("SCREENGRABBER_TWITTER_HOST"),
            x_url=f"https://x.com/{account_name}/status/{status_id}",
            render_url=render_url,
            account=account_name,
            status_id=status_id,
        )

    else:
        if request.args.get("render_only", None):
            return send_file(
                BytesIO(screengrab),
                mimetype="image/jpg",
                download_name=f"{account_name}_{status_id}.jpg",
            )

        return render_template(
            "service_templates/twitter/download.html",
            host=os.getenv("SCREENGRABBER_TWITTER_HOST"),
            s3_domain=os.getenv("S3_CUSTOM_DOMAIN"),
            x_url=f"https://x.com/{account_name}/status/{status_id}",
            render_url=render_url,
            account=account_name,
            status_id=status_id,
            medias=cache_service.get_twitter_screengrab_medias(status_id),
        )


@app.route("/render/<account>/status/<status_id>")
def render_twitter_tweet(account, status_id):
    tweet_info = twitter_service.get_tweet_info(account, status_id)
    return render_template(
        "service_templates/twitter/render/tweet.html", tweet_info=tweet_info.as_dict()
    )


@app.route("/oembed.json")
def oembedend():
    desc = request.args.get("desc", None)
    user = request.args.get("user", None)
    link = request.args.get("link", None)
    ttype = request.args.get("ttype", None)
    account_name = request.args.get("account_name", None)
    status_id = request.args.get("status_id", None)
    return oEmbedGen(desc, user, link, ttype, account_name, status_id)


def oEmbedGen(description, user, link, ttype, account_name, status_id):
    out = {
        "type": ttype,
        "version": "1.0",
        "provider_name": "screengrabx - pretty x posts\nclick to view on X",
        "provider_url": f"https://x.com/{account_name}/status/{status_id}",
        "title": description,
    }

    return out


if __name__ == "__main__":
    app.run()
