import pytest
from defusedxml.common import EntitiesForbidden

from linuxdo_reader.feeds import parse_topic_feed, parse_topic_list_feed

from .fixtures import LATEST_RSS, TOPIC_RSS


def test_parse_topic_list_feed_extracts_topic_metadata() -> None:
    topics = parse_topic_list_feed(LATEST_RSS, source="latest")

    assert [topic.topic_id for topic in topics] == [2491173, 2489984]
    assert topics[0].title == "mac mini m4 24G 应该用来做什么呢?"
    assert topics[0].author == "Tipper1971"
    assert topics[0].category == "搞七捻三"
    assert topics[0].reply_count == 1
    assert topics[1].participant_count == 95
    assert "公益站" in topics[1].excerpt


def test_feed_parser_rejects_xml_entities() -> None:
    xml = """<?xml version="1.0"?>
    <!DOCTYPE rss [<!ENTITY payload "untrusted">]>
    <rss><channel><item><title>&payload;</title></item></channel></rss>
    """

    with pytest.raises(EntitiesForbidden):
        parse_topic_list_feed(xml, source="latest")


def test_parse_topic_feed_extracts_recent_comments_in_floor_order() -> None:
    posts = parse_topic_feed(TOPIC_RSS, topic_id=2489984)

    assert [post.post_number for post in posts] == [104, 105]
    assert posts[1].author == "欣欣|林可欣"
    assert posts[1].url == "https://linux.do/t/topic/2489984/105"
    assert posts[0].text == "公益站还是要留给真用的人。"
