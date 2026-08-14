# Roadmap

Everything that did not fit inside the v0.1 caps, in rough priority order. Start at
[`../README.md`](../README.md) for what ships today, and [`../CHANGELOG.md`](../CHANGELOG.md) for
what the current release does and does not do.

1. **"What did this act require on date D?"**, the two-clock query. The system already knows what
   changed between any two points; this turns that into the question people actually ask.
2. **A second corpus adapter**, the proof that the core is generic. The seam is exercised today by
   a deliberately alien `ToyCorpusAdapter` that is not law at all, which keeps the protocol honest
   but proves nothing about a second real corpus.
3. **Notification integrations**: webhook, email, a bot. Cheap, and it is what makes the tool
   something people run rather than something people read about.
4. **An MCP server** over the changelog and the diff, so agents can query regulatory change. Cheap;
   note that several EU-law MCP servers already exist, so this is a convenience, not a
   differentiator.
5. **Impact filtering**: "here is my situation, tell me what changed *for me*". It is a filter over
   a verified delta rather than a standalone claim about the world, which is the only order in
   which it is worth having: it goes on top of a measured foundation, never underneath one.
