# Request lifecycle

This traces a single "send a magnet link" round trip end to end.

```mermaid
sequenceDiagram
    participant Phone as Your phone (Telegram app)
    participant TG as Telegram Bot API
    participant Bot as mobocloud-relay (Termux)
    participant Tr as Transmission RPC (127.0.0.1)

    Phone->>TG: sendMessage("magnet:?xt=...")
    Note over Bot,TG: Bot is already long-polling<br/>getUpdates(offset, timeout=30)
    TG-->>Bot: update{message, chat.id, text}
    Bot->>Bot: auth.is_authorized(chat.id)?
    alt not authorized
        Bot->>Bot: drop silently, mark update processed
    else authorized
        Bot->>Bot: router.classify(text) -> transmission
        Bot->>Tr: torrent-add {filename: magnet}
        Tr-->>Bot: torrent-added {id, name, totalSize}
        Bot->>Bot: state.mark_processed(update_id)
        Bot->>TG: sendMessage("✅ Download added...")
        TG-->>Phone: shows confirmation
    end
```

Every arrow that crosses the home network boundary in the diagram above is
either (a) Telegram-to-bot, which is the response to a connection the bot
itself opened, or (b) bot-to-RPC, which never leaves `127.0.0.1`/the LAN.
Nothing in this flow requires an inbound connection from the public internet.

# Module map

- `telegram_client.py` — `getUpdates`/`sendMessage` over `urllib`, no webhook.
- `auth.py` — the allowlist gate, applied first, always.
- `router.py` — magnet/URL classification; raises on anything unrecognized
  instead of guessing.
- `backends/transmission.py`, `backends/aria2.py` — thin RPC clients, one
  method per action, no shell involvement.
- `commands.py` — one function per `/command`, each composing backend calls +
  `formatting.py` templates.
- `state.py` — crash-safe, atomic (`os.replace`) persistence of the Telegram
  offset and a recent-update-id ring buffer, for idempotent restarts.
- `main.py` — the long-poll loop: backoff on network failure, per-update
  exception isolation, and the command dispatch table.
