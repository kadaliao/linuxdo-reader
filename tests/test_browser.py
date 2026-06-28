from linuxdo_reader.browser import build_topic_url


def test_build_topic_url_accepts_id_or_url() -> None:
    assert build_topic_url("2489984") == "https://linux.do/t/topic/2489984"
    assert build_topic_url("https://linux.do/t/topic/2489984") == "https://linux.do/t/topic/2489984"
