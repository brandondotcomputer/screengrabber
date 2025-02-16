import logging
import os
import coloredlogs
from flask import Flask, render_template, request
from flask import send_file
from io import BytesIO
from screengrabber import TwitterService
from screengrabber.helpers import Visitor, identify_visitor
from screengrabber.screengrabber import ScreengrabberService
from screengrabber.storage_service import StorageService
from urllib.parse import unquote

_FORMAT = (
    "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)5d - %(message)s"
)
logging.basicConfig(format=_FORMAT)
logger = logging.getLogger(__name__)
coloredlogs.install(level=logging.INFO, logger=logger, fmt=_FORMAT)

app = Flask(__name__)

twitter_service = TwitterService()
screengrabber_service = ScreengrabberService()
storage_service = StorageService(
    bucket_name=os.getenv("S3_BUCKET_NAME"),
    endpoint_url=os.getenv("S3_ENDPOINT_URL"),
    aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
    region_name=os.getenv("S3_REGION_NAME"),
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/<account>/status/<status_id>")
def twitter_tweet(account, status_id):
    visitor = identify_visitor(request.headers.get("User-Agent"))
    screengrab = screengrabber_service.get_screenshot(
        url=f"http://localhost:{os.getenv('FLASK_PORT')}/render/{account}/status/{status_id}",
        options={"width": 600},
    )
    storage_service.upload_file(
        file=BytesIO(screengrab),
        key=f"twitter/renders/{status_id}.jpg",
        content_type="application/jpg",
    )

    if visitor == Visitor.DISCORD:
        render_url = f"{os.getenv('S3_CUSTOM_DOMAIN')}/twitter/renders/{status_id}.jpg"
        return render_template(
            "service_templates/twitter/discord_embed.html",
            host=os.getenv("SCREENGRABBER_TWITTER_HOST"),
            x_url=f"https://x.com/{account}/status/{status_id}",
            render_url=render_url,
            account=account,
            status_id=status_id,
        )

    else:
        # regular person, send image of screengrab
        return send_file(
            BytesIO(screengrab),
            mimetype="image/jpg",
            download_name=f"{account}_{status_id}.jpg",
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
    return oEmbedGen(desc, user, link, ttype)


def oEmbedGen(description, user, link, ttype):
    out = {
        "type": ttype,
        "version": "1.0",
        "provider_name": "screengrabx - pretty x posts",
        "provider_url": "https://screengrabx.com",
        "title": description,
        "author_name": user,
        "author_url": unquote(link),
    }
    logger.info(out)

    return out


if __name__ == "__main__":
    # app.run(threaded=False, processes=3)
    app.run()
