
from typing import Optional
from dataclasses import dataclass
import kex as kx
import pgnet
import util


LINE_HEIGHT = 40
TITLE_TEXT = "[b][u]Welcome to KPdemo[/u][/b]"
INFO_TEXT = (
    "This online multiplayer game of tic-tac-toe is a demo for the Kex and"
    " PGNet Python libraries."
    "\n\n"
    "[u]Connecting to a server[/u]"
    "\n\n"
    "To register, simply choose a username and password and log in (if the"
    " server allows it)."
    "\n\n"
    "Server verification is optional. If set with the public key given by the"
    " server owner, it will verify the server at the address."
    "\n\n"
    ""
)


CONFIG_FILE = util.get_appdata_dir() / "connection_config.txt"


@dataclass
class _ConnectionConfig:
    online: bool = True
    username: str = "guest"
    address: str = "localhost"
    port: int = 38929
    pubkey: str = ""

    @classmethod
    def load_from_disk(cls) -> "_ConnectionConfig":
        try:
            with open(CONFIG_FILE) as f:
                data = f.read()
            online, user, addr, port, pubkey = data.splitlines()
            return cls(bool(online), user, addr, int(port), pubkey)
        except Exception:
            return cls()

    def save_to_disk(self):
        data = [int(self.online), self.username, self.address, self.port, self.pubkey]
        with open(CONFIG_FILE, "w") as f:
            f.write("\n".join(str(d) for d in data))
            f.write("\n")


class ConnectionFrame(kx.XAnchor):
    def __init__(
        self,
        client_cls: Optional[pgnet.BaseClient] = None,
        localhost_cls: Optional[pgnet.BaseClient] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if not any((client_cls, localhost_cls)):
            raise RuntimeError("Need at least one client class.")
        self._client_cls = client_cls
        self._localhost_cls = localhost_cls
        self.make_widgets()
        self.app.controller.bind("connection.start", self._invoke_play)

    def make_widgets(self):
        self.clear_widgets()
        config = _ConnectionConfig.load_from_disk()
        # Side panel
        title_label = kx.XLabel(text=TITLE_TEXT)
        title_label.set_size(y=LINE_HEIGHT * 2)
        info_label = kx.XLabel(
            text=INFO_TEXT,
            valign="top",
            halign="left",
            padding=(10, 10),
        )
        left_frame = kx.XBox(orientation="vertical")
        left_frame.set_size(x=350)
        left_frame.add_widgets(title_label, info_label)
        left_frame.make_bg(kx.get_color("cyan", v=0.3))
        # Connection details
        if not self._client_cls and config.online:
            config.online = False
        elif not self._localhost_cls and not config.online:
            config.online = True
        pwidgets = dict(
            online=kx.XInputPanelWidget(
                "Online",
                "bool",
                default=config.online,
                bold=True,
                italic=False,
                showing=all((self._client_cls, self._localhost_cls)),
            ),
            username=kx.XInputPanelWidget("Username", default=config.username),
            password=kx.XInputPanelWidget(
                "Password",
                "password",
                showing=config.online,
            ),
            address=kx.XInputPanelWidget(
                "IP Address",
                default=config.address,
                showing=config.online,
            ),
            advanced=kx.XInputPanelWidget(
                "Advanced",
                "bool",
                default=False,
                bold=True,
                italic=False,
                showing=config.online,
            ),
            port=kx.XInputPanelWidget(
                "Port number",
                "int",
                default=config.port,
                showing=False,
            ),
            pubkey=kx.XInputPanelWidget(
                "Server verification",
                default=config.pubkey,
                showing=False,
            ),
        )
        self.connection_panel = kx.XInputPanel(
            pwidgets,
            invoke_text="Connect",
        )
        self.connection_panel.bind(
            on_invoke=self._invoke_play,
            on_values=self._on_connection_values,
        )
        self.connection_panel.set_focus("username")
        # Assemble
        main_frame = kx.XBox()
        main_frame.set_size(x=900, y=700)
        main_frame.add_widgets(
            left_frame,
            kx.XAnchor.wrap(self.connection_panel)
        )
        main_frame.make_bg(kx.get_color("pink", v=0.3))
        self.add_widget(main_frame)

    def _invoke_play(self, *args):
        get_value = self.connection_panel.get_value
        online = get_value("online")
        advanced = online and get_value("advanced")
        online = get_value("online")
        username = get_value("username")
        password = get_value("password")
        address = get_value("address") if online else _ConnectionConfig.address
        port = get_value("port") if advanced else _ConnectionConfig.port
        pubkey = get_value("pubkey") if advanced else _ConnectionConfig.pubkey
        if online:
            client = self._client_cls(
                address=address,
                port=port,
                username=username,
                password=password,
                verify_server_pubkey=pubkey or None,
            )
        else:
            client = self._localhost_cls(username=username)
        self.app.set_client(client)
        config = _ConnectionConfig(online, username, address, port, pubkey)
        config.save_to_disk()

    def _on_connection_values(self, w, values: dict):
        online = values["online"]
        advanced = online and values["advanced"]
        for iname in ("password", "address", "advanced"):
            self.connection_panel.set_showing(iname, online)
        for iname in ("port", "pubkey"):
            self.connection_panel.set_showing(iname, advanced)
