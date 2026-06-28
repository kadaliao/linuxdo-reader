LATEST_RSS = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:discourse="http://www.discourse.org/" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>LINUX DO - 最新话题</title>
    <link>https://linux.do/latest</link>
    <description>最新话题</description>
    <language>zh-CN</language>
    <item>
      <title>mac mini m4 24G 应该用来做什么呢?</title>
      <dc:creator><![CDATA[Tipper1971]]></dc:creator>
      <category>搞七捻三</category>
      <description><![CDATA[
        <p>自己有mac pro 32G,日常工作用不到。</p>
        <p><small>1 个帖子 - 1 位参与者</small></p>
        <p><a href="https://linux.do/t/topic/2491173">阅读完整话题</a></p>
      ]]></description>
      <link>https://linux.do/t/topic/2491173</link>
      <pubDate>Sun, 28 Jun 2026 15:17:10 +0000</pubDate>
      <guid isPermaLink="false">linux.do-topic-2491173</guid>
      <source url="https://linux.do/t/topic/2491173.rss">mac mini m4 24G 应该用来做什么呢?</source>
    </item>
    <item>
      <title>囤囤鼠的末日</title>
      <dc:creator><![CDATA[qq124415]]></dc:creator>
      <category>搞七捻三</category>
      <description><![CDATA[
        <p>感谢公益站的囤囤鼠，你们的额度会成为公益站下个月的签到额度～</p>
        <p><small>102 个帖子 - 95 位参与者</small></p>
        <p><a href="https://linux.do/t/topic/2489984">阅读完整话题</a></p>
      ]]></description>
      <link>https://linux.do/t/topic/2489984</link>
      <pubDate>Sun, 28 Jun 2026 09:45:15 +0000</pubDate>
      <guid isPermaLink="false">linux.do-topic-2489984</guid>
      <source url="https://linux.do/t/topic/2489984.rss">囤囤鼠的末日</source>
    </item>
  </channel>
</rss>
"""


TOPIC_RSS = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>囤囤鼠的末日</title>
    <link>https://linux.do/t/topic/2489984</link>
    <description>首帖 Markdown</description>
    <item>
      <title>囤囤鼠的末日</title>
      <dc:creator><![CDATA[欣欣|林可欣]]></dc:creator>
      <description><![CDATA[<p>哈哈哈，已经开始清额度了吗</p>]]></description>
      <link>https://linux.do/t/topic/2489984/105</link>
      <pubDate>Sun, 28 Jun 2026 15:29:18 +0000</pubDate>
    </item>
    <item>
      <title>囤囤鼠的末日</title>
      <dc:creator><![CDATA[Valon]]></dc:creator>
      <description><![CDATA[<p>公益站还是要留给真用的人。</p>]]></description>
      <link>https://linux.do/t/topic/2489984/104</link>
      <pubDate>Sun, 28 Jun 2026 15:28:14 +0000</pubDate>
    </item>
  </channel>
</rss>
"""


TOPIC_JSON = {
    "id": 2489984,
    "title": "囤囤鼠的末日",
    "post_stream": {
        "stream": [19684601, 19684652, 19684699],
        "posts": [
            {
                "id": 19684601,
                "post_number": 1,
                "username": "qq124415",
                "created_at": "2026-06-28T09:45:15.000Z",
                "cooked": "<p>感谢公益站的囤囤鼠，你们的额度会成为公益站下个月的签到额度～</p>",
                "post_url": "/t/topic/2489984/1",
            }
        ],
    },
}


POSTS_JSON = {
    "post_stream": {
        "posts": [
            {
                "id": 19684652,
                "post_number": 2,
                "username": "alice",
                "created_at": "2026-06-28T10:00:00.000Z",
                "cooked": "<p>支持，别囤不用。</p>",
                "post_url": "/t/topic/2489984/2",
            },
            {
                "id": 19684699,
                "post_number": 3,
                "username": "bob",
                "created_at": "2026-06-28T10:05:00.000Z",
                "cooked": "<p>也要考虑偶尔才用的人。</p>",
                "post_url": "/t/topic/2489984/3",
            },
        ]
    }
}
