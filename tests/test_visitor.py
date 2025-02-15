import pytest
from screengrabber.helpers import Visitor, identify_visitor


@pytest.mark.parametrize(
    "user_agent,expected",
    [
        (
            "Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)",
            Visitor.DISCORD,
        ),
        ("Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)", Visitor.SLACK),
        ("TelegramBot (like TwitterBot)", Visitor.TELEGRAM),
        ("Mozilla/5.0 (compatible; TwitterBot/1.0)", Visitor.TWITTER),
        (
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            Visitor.GOOGLE,
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            Visitor.UNKNOWN,
        ),
        ("", Visitor.UNKNOWN),
    ],
)
def test_identify_visitor(user_agent, expected):
    assert identify_visitor(user_agent) == expected


def test_case_insensitive():
    assert identify_visitor("DISCORDBOT") == Visitor.DISCORD
    assert identify_visitor("discordBOT") == Visitor.DISCORD


def test_null_input():
    with pytest.raises(AttributeError):
        identify_visitor(None)
