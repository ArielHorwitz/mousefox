"""Home of `ConnectionFrame`."""

from dataclasses import dataclass
import kvex as kx
from .. import util


LINE_HEIGHT = 40
CONFIG_FILE = util.get_appdata_dir() / "connection_config.txt"


@dataclass
class _ConnectionConfig:
    online: bool = False
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
    """Widget enabling to create clients for the app."""

    def __init__(self, app_config: "mousefox.AppConfig"):  # noqa: F821
        """Initialize the class."""
        super().__init__()
        if app_config.disable_local and app_config.disable_remote:
            raise ValueError("Cannot disable both local and remote clients.")
        self._client_class = app_config.client_class
        self._game_class = app_config.game_class
        self._server_factory = app_config.server_factory
        self._enable_local = not app_config.disable_local
        self._enable_remote = not app_config.disable_remote
        self._make_widgets(app_config.info_text, app_config.online_info_text)
        self.app.controller.bind("connection.start", self._connect)

    def _make_widgets(self, info_text, online_info_text):
        self.clear_widgets()
        config = _ConnectionConfig.load_from_disk()
        if not self._enable_remote and config.online:
            config.online = False
        elif not self._enable_local and not config.online:
            config.online = True
        # Side panel
        info_label = kx.XLabel(
            text=info_text,
            valign="top",
            halign="left",
            padding=(10, 10),
        )
        online_info_label = kx.XLabel(
            text=online_info_text,
            valign="top",
            halign="left",
            padding=(10, 10),
        )
        self._online_info_label = kx.XCurtain(
            content=online_info_label,
            showing=config.online,
        )
        left_frame = kx.XBox(orientation="vertical")
        left_frame.add_widgets(info_label, self._online_info_label)
        left_frame = kx.XAnchor.wrap(left_frame, x=1, y=0.9)
        left_frame.set_size(x=350)
        left_frame.make_bg(kx.get_color("cyan", v=0.3))
        # Connection details
        pwidgets = dict(
            online=kx.XInputPanelWidget(
                "Online",
                "bool",
                default=config.online,
                bold=True,
                italic=False,
                showing=self._enable_local and self._enable_remote,
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
            on_invoke=self._connect,
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

    def _connect(self, *args):
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
            client = self._client_class.remote(
                address=address,
                port=port,
                username=username,
                password=password,
                verify_server_pubkey=pubkey or None,
            )
        else:
            client = self._client_class.local(
                username=username,
                game=self._game_class,
                server_factory=self._server_factory,
            )
        self.app.set_client(client)
        config = _ConnectionConfig(online, username, address, port, pubkey)
        config.save_to_disk()

    def _on_connection_values(self, w, values: dict):
        online = values["online"]
        advanced = online and values["advanced"]
        self._online_info_label.showing = online
        for iname in ("password", "address", "advanced"):
            self.connection_panel.set_showing(iname, online)
        for iname in ("port", "pubkey"):
            self.connection_panel.set_showing(iname, advanced)

    def set_focus(self, *args):
        """Focus the input widgets."""
        self.connection_panel.set_focus("username")
