"""Reconnect snapshot must precede queued live events without a subscription gap."""
import asyncio
from types import SimpleNamespace
from fastapi import WebSocketDisconnect
from app.routers import chat
from app.services.chat_channel import get_chat_hub, reset_chat_hub_for_tests


def test_subscribe_before_sending_snapshot(monkeypatch):
    async def scenario():
        reset_chat_hub_for_tests()
        hub = get_chat_hub()
        monkeypatch.setattr(chat, "authenticate_backoffice_token", lambda _token: SimpleNamespace(id="fictional-staff"))
        received = []
        done = asyncio.Event()
        token = {"event": "token_chunk", "data": {"session_id": "chat_restore_order", "token": "Policy", "sequence": 1}}

        class Socket:
            async def accept(self):
                pass

            async def send_json(self, event):
                received.append(event)
                if event["event"] == "session_snapshot":
                    # A producer publishes while the snapshot is being sent.
                    hub.publish("chat_restore_order", token)
                    await asyncio.sleep(0)
                else:
                    done.set()

            async def receive_json(self):
                await done.wait()
                raise WebSocketDisconnect()

        try:
            await asyncio.wait_for(chat.chat_socket(Socket(), "chat_restore_order", token="fictional"), timeout=1)
            assert [event["event"] for event in received] == ["session_snapshot", "token_chunk"]
        finally:
            reset_chat_hub_for_tests()

    asyncio.run(scenario())
