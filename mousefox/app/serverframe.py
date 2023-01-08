"""Home of `ServerFrame`."""

from typing import Optional
from loguru import logger
import asyncio
import kvex as kx
import pgnet
from .palette import Palette


INFO_TEXT = (
    "[size=20dp][b][u]Hosting a server[/u][/b][/size]"
    "\n\n"
    "[color=#ffbbbb][i]Please consider your network security before running a"
    " server[/i][/color]."
    "\n\n"
    "For best performance, run the server in a separate instance."
    " You may be required to configure port forwarding on your network device before"
    " remote clients can discover a server."
    "\n\n\n"
    "The running server is available at address"
    " [font=RobotoMono-Regular][color=#ffffbb]localhost[/color][/font] and can be"
    " connected to normally. To manage a server, connect as admin and use the admin"
    " panel."
    "\n\n\n"
)


class ServerFrame(kx.XAnchor):
    """Widget for launching server."""

    _conpath = "server"

    def __init__(self, app_config):
        """Initialize the class with an `AppConfig`."""
        super().__init__()
        self._running_server: Optional[pgnet.Server] = None
        self._game_class = app_config.game_class
        self._make_widgets(app_config)
        self.app.controller.set_active_callback(self._conpath, self.set_focus)
        self.app.controller.bind(f"{self._conpath}.focus", self.set_focus)
        self.app.controller.bind(f"{self._conpath}.shutdown", self._shutdown_server)

    def _make_widgets(self, app_config):
        # Left frame
        info_label = kx.XLabel(
            text=INFO_TEXT,
            halign="left",
            valign="top",
            padding=(10, 10),
        )
        info_label.set_size(hy=5)
        return_btn = kx.XButton(
            text="Return to client",
            on_release=self._return_to_client,
        )
        return_btn.set_size(x="250dp", y="40dp")
        left_frame = kx.XBox(orientation="vertical")
        left_frame.add_widgets(
            info_label,
            kx.XAnchor.wrap(return_btn),
        )
        left_frame.make_bg(Palette.BG_BASE)
        # Right frame
        config_panel_widgets = {
            "admin_password": kx.XInputPanelWidget(
                "Admin password:",
                default=pgnet.util.DEFAULT_ADMIN_PASSWORD,
            ),
            "save_file": kx.XInputPanelWidget("Save file:", 'str'),
            "port": kx.XInputPanelWidget("Port:", 'int', pgnet.util.DEFAULT_PORT),
            "require_user_password": kx.XInputPanelWidget(
                "Require user password:",
                widget="bool",
                default=False,
            ),
        }
        self._config_panel = kx.XInputPanel(
            config_panel_widgets,
            invoke_text="Launch server",
        )
        self._config_panel.bind(on_invoke=self._on_config_invoke)
        config_frame = kx.XAnchor.wrap(self._config_panel)
        config_frame.set_size(hy=5)
        self.pubkey_label = kx.XInput(
            text="No server running.",
            readonly=True,
            disabled=True,
            select_on_focus=True,
            halign="center",
        )
        self.pubkey_label.set_size(y="40dp")
        pubkey_label_hint = kx.XLabel(text="Server pubkey:")
        pubkey_label_hint.set_size(y="40dp")
        self.shutdown_btn = kx.XButton(
            text="Shutdown server",
            on_release=self._shutdown_server,
            disabled=True,
        )
        self.shutdown_btn.set_size(x="250dp", y="40dp")
        right_frame = kx.XBox(orientation="vertical")
        right_frame.add_widgets(
            config_frame,
            pubkey_label_hint,
            self.pubkey_label,
            kx.XAnchor.wrap(self.shutdown_btn),
        )
        right_frame = kx.XAnchor.wrap(right_frame)
        right_frame.make_bg(Palette.BG_MAIN)
        main_frame = kx.XBox()
        main_frame.add_widgets(left_frame, right_frame)
        wrapped_frame = kx.XAnchor.wrap(main_frame)
        self.add_widget(wrapped_frame)

    def _on_config_invoke(self, w, values):
        self.set_focus()
        server_kwargs = dict(
            listen_globally=True,
            admin_password=values["admin_password"],
            save_file=values["save_file"] or None,
            port=values["port"],
            require_user_password=values["require_user_password"],
        )
        asyncio.create_task(self._run_server(server_kwargs))

    async def _run_server(self, server_kwargs: dict):
        if self._running_server is not None:
            self.app.set_feedback("Server already running.", "warning")
            return
        try:
            server = pgnet.Server(self._game_class, **server_kwargs)
        except Exception as e:
            logger.warning(e)
            self.app.set_feedback(str(e), "warning")
            return
        self._running_server = server
        self.shutdown_btn.disabled = False
        self.pubkey_label.text = server.pubkey
        self.pubkey_label.disabled = False
        stype = "warning"
        try:
            logger.debug(f"Running {server=}")
            exit_code: int = await server.async_run(on_start=self._on_server_start)
            logger.debug(f"Shutdown {server=}")
        except Exception as e:
            logger.warning(e)
            exit_code = str(e)
            stype = "error"
        self.shutdown_btn.disabled = True
        self.pubkey_label.text = "No server running."
        self.pubkey_label.disabled = True
        self._running_server = None
        self.app.set_feedback(f"Server shutdown with exit code: {exit_code}.", stype)

    def _on_server_start(self, *args):
        self.app.set_feedback("Server running.")

    def _shutdown_server(self, *args):
        if self._running_server:
            self._running_server.shutdown()

    def _return_to_client(self, *args):
        self.app.controller.invoke("show_client")

    def set_focus(self, *args):
        """Focus input widgets."""
        self._config_panel.set_focus("admin_password")
