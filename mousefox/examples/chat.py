"""Example Chat room for MouseFox.

Provides `APP_CONFIG` dictionary to pass keyword arguments for `mousefox.run`.
"""

import arrow
import json
import pgnet
from dataclasses import dataclass, field
from pgnet import Packet, Response
import kvex as kx


BLANK_DATA = dict(message_log=list())


@dataclass
class Message:
    """Chat message."""
    username: str
    text: str
    time: float = field(default_factory=lambda: arrow.now().timestamp())

    def serialize(self) -> str:
        """Export to string."""
        data = dict(username=self.username, text=self.text, time=self.time)
        return json.dumps(data)

    @classmethod
    def deserialize(cls, raw_data: str, /) -> "Message":
        """Import from string."""
        return cls(**json.loads(raw_data))


class Game(pgnet.Game):
    """Chat room logic."""

    def __init__(self, name: str, *args, **kwargs):
        """Override base method."""
        self.name = name
        initial_message = Message("admin", f"Welcome to {name!r} chat room")
        self.message_log: list[Message] = [initial_message]
        self.users: set[str] = set()

    @property
    def persistent(self) -> bool:
        """Override base property."""
        if len(self.message_log) <= 1:
            return False
        time_since_last_message = arrow.now().timestamp() - self.message_log[-1].time
        expired = time_since_last_message > 7200  # Over 2 hours
        return not expired

    def user_joined(self, username: str):
        """Override base method."""
        self.users.add(username)

    def user_left(self, username: str):
        """Override base method."""
        if username in self.users:
            self.users.remove(username)

    def handle_game_packet(self, packet: Packet) -> Response:
        """Override base method."""
        text = packet.payload.get("text")
        if not text:
            return Response("Expected text in payload.", status=pgnet.Status.UNEXPECTED)
        message = Message(username=packet.username, text=text)
        self.message_log.append(message)
        return Response("Added message.")

    def handle_heartbeat(self, packet: Packet) -> Response:
        """Override base method."""
        update_hash = self._update_hash
        client_hash = packet.payload.get("update_hash", -1)
        if client_hash == update_hash:
            return Response("Up to date.", dict(update_hash=update_hash))
        payload = dict(
            update_hash=update_hash,
            room_name=self.name,
            users=list(self.users),
            messages=[m.serialize() for m in self.message_log[-50:]],
        )
        return Response("Last 50 messages.", payload)

    @property
    def _update_hash(self) -> int:
        data = (
            self.name,
            str(sorted(self.users)),
            self.message_log[-1].time,
        )
        return hash(data)


class GameWidget(kx.XAnchor):
    """Tic-tac-toe GUI widget."""

    def __init__(self, client: pgnet.Client, **kwargs):
        """Override base method."""
        super().__init__(**kwargs)
        self.client = client
        self._update_hash = None
        self._make_widgets()
        client.on_heartbeat = self.on_heartbeat
        client.heartbeat_payload = self.heartbeat_payload

    def heartbeat_payload(self) -> dict:
        """Override base method."""
        data = dict(update_hash=self._update_hash)
        return data

    def on_heartbeat(self, heartbeat_response: pgnet.Response):
        """Override base method."""
        update_hash = heartbeat_response.payload.get("update_hash")
        if not update_hash or self._update_hash == update_hash:
            return
        self._update_hash = update_hash
        room_name = heartbeat_response.payload["room_name"]
        users = set(heartbeat_response.payload["users"])
        self.info_panel.text = "\n".join([
            "\n",
            f"[u]Chat Room:[/u] [i]{room_name}[/i]",
            "\n",
            "[u]Users:[/u]",
            *(f" -- {user}" for user in users),
        ])
        text_lines = []
        for raw_message in heartbeat_response.payload["messages"]:
            message = Message.deserialize(raw_message)
            time = arrow.get(message.time).format("HH:MM:SS")
            color = "77ff77" if message.username == self.client._username else "ff7777"
            text_lines.append(f"[color=#{color}]{time} | {message.username}[/color]")
            text_lines.append(f"[color=#666666]>>>[/color] {message.text}")
        self.messages_label.text = "\n".join(text_lines)

    def _make_widgets(self):
        self.info_panel = kx.XLabel(
            text="Getting chat room info...",
            halign="left",
            valign="top",
            padding=(10, 5),
        )
        self.info_panel.set_size(x="200dp")
        self.info_panel.make_bg(kx.get_color("cyan", v=0.2))
        self.messages_label = kx.XLabel(
            text="Getting chat messages...",
            halign="left",
            valign="bottom",
            padding=(10, 5),
            fixed_width=True,
        )
        self.messages_label.make_bg(kx.get_color("white", v=0.05))
        self.message_input = kx.XInput(on_text_validate=self._message_validate)
        self.message_input.set_size(y=100)
        self.message_input.focus = True
        chat_frame = kx.XBox(orientation="vertical")
        messages_frame = kx.XScroll(view=self.messages_label)
        chat_frame.add_widgets(messages_frame, self.message_input)
        main_frame = kx.XBox()
        main_frame.add_widgets(self.info_panel, chat_frame)
        self.clear_widgets()
        self.add_widget(main_frame)

    def _message_validate(self, w):
        self.client.send(pgnet.Packet("message", dict(text=w.text)))
        w.text = ""


INFO_TEXT = (
    "[b][u]Welcome to MouseFox[/u][/b]"
    "\n\n"
    "This chat server is a builtin example to demo MouseFox."
)
ONLINE_INFO_TEXT = (
    "[u]Connecting to a server[/u]"
    "\n\n"
    "To register (if the server allows it) simply choose a username and password"
    " and log in."
)
APP_CONFIG = dict(
    game_class=Game,
    game_widget=GameWidget,
    title="MouseFox chat",
    info_text=INFO_TEXT,
    online_info_text=ONLINE_INFO_TEXT,
)


def run():
    """Run chat example."""
    from .. import run

    run(**APP_CONFIG)
