import httpx
import respx

from linuxdo_reader.client import LinuxDoClient

from .fixtures import POSTS_JSON, TOPIC_JSON


@respx.mock
def test_fetch_topic_full_uses_print_json_then_post_ids() -> None:
    respx.get("https://linux.do/t/-/2489984.json").mock(
        return_value=httpx.Response(200, json=TOPIC_JSON)
    )
    respx.get("https://linux.do/t/2489984/posts.json").mock(
        return_value=httpx.Response(200, json=POSTS_JSON)
    )

    client = LinuxDoClient()
    posts = client.fetch_topic_json(2489984, chunk_size=2)

    assert [post.post_number for post in posts] == [1, 2, 3]
    assert posts[0].source == "json"
    assert "偶尔才用" in posts[2].text
