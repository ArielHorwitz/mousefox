"""Example Chat room for MouseFox."""

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

    def get_lobby_info(self) -> str:
        """Override base method."""
        mtime = arrow.get(self.message_log[-1].time).to("utc").format("HH:mm:ss")
        return f"Last message: {mtime} (UTC)"

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


AWAITING_DATA_TEXT = "Awaiting data from server..."


class GameWidget(kx.XFrame):
    """Chat GUI widget."""

    def __init__(self, client: pgnet.Client, **kwargs):
        """Override base method."""
        super().__init__(**kwargs)
        self.client = client
        self._game_data = dict(
            update_hash=None,
            room_name=AWAITING_DATA_TEXT,
            users=[],
            messages=[Message("system", AWAITING_DATA_TEXT).serialize()],
        )
        self._make_widgets()
        client.on_heartbeat = self.on_heartbeat
        client.heartbeat_payload = self.heartbeat_payload

    def on_subtheme(self, *args, **kwargs):
        """Refresh widgets."""
        super().on_subtheme(*args, **kwargs)
        self._refresh_widgets()

    def heartbeat_payload(self) -> dict:
        """Override base method."""
        return dict(update_hash=self._game_data["update_hash"])

    def on_heartbeat(self, heartbeat_response: pgnet.Response):
        """Override base method."""
        server_hash = heartbeat_response.payload.get("update_hash")
        our_hash = self._game_data["update_hash"]
        if not server_hash or our_hash == server_hash:
            return
        self._game_data = heartbeat_response.payload
        self._refresh_widgets()

    def _refresh_widgets(self, *args):
        room_name = self._game_data["room_name"]
        users = set(self._game_data["users"])
        fg_accent = self.app.theme.secondary.fg_accent.markup
        bullet = self.app.theme.secondary.accent.markup("•")
        self.info_panel.text = "\n".join([
            f"[u][b]Chat Room[/b][/u]\n[i]{fg_accent(room_name)}[/i]",
            "\n",
            "[u][b]Users[/b][/u]",
            *(f" {bullet} {fg_accent(user)}" for user in users),
        ])
        text_lines = []
        chevron = self.subtheme.fg_muted.markup(">")
        for raw_message in self._game_data["messages"]:
            message = Message.deserialize(raw_message)
            time = arrow.get(message.time).to("local").format("HH:mm:ss")
            is_author = message.username == self.client._username
            color = kx.XColor.from_hex("77ff77" if is_author else "ff7777")
            text_lines.append(color.markup(f"[u]{time} | {message.username}[/u]"))
            text_lines.append(f"{chevron} {message.text}")
        self.messages_label.text = "\n".join(text_lines)

    def _make_widgets(self):
        with self.app.subtheme_context("secondary"):
            self.info_panel = kx.XLabel(
                text="Getting chat room info...",
                halign="left",
                valign="top",
            )
            info_frame = kx.pwrap(kx.fwrap(kx.pwrap(self.info_panel)))
            info_frame.set_size(hx=0.3)
        self.messages_label = kx.XLabel(
            text="Getting chat messages...",
            halign="left",
            valign="bottom",
            fixed_width=True,
        )
        with self.app.subtheme_context("accent"):
            self.message_input = kx.XInput(on_text_validate=self._message_validate)
            self.message_input.focus = True
            input_frame = kx.pwrap(kx.fwrap(self.message_input))
            input_frame.set_size(y="55dp")
        messages_frame = kx.pwrap(kx.XScroll(self.messages_label))
        chat_frame = kx.XBox(orientation="vertical")
        chat_frame.add_widgets(messages_frame, input_frame)
        main_frame = kx.XBox()
        main_frame.add_widgets(info_frame, kx.pwrap(chat_frame))
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
