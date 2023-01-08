"""Home of `ServerFrame`."""

from typing import Optional
from loguru import logger
import asyncio
import kvex as kx
import pgnet


INFO_TEXT = (
    "[size=24dp][b][u]Running a server[/u][/b][/size]"
    "\n\n"
    "You may require to configuring port forwarding on your network device before"
    " remote clients can discover a server."
    "\n"
    "[color=#ffbbbb][i]Please consider your network security before running a"
    " server[/i][/color]."
    "\n\n\n"
    "The running server is available at address"
    " [font=RobotoMono-Regular]localhost[/font] and can be connected to normally. To"
    " manage a server, connect as admin and use the admin panel."
)


class ServerFrame(kx.XAnchor):
    """Widget for launching server."""

    def __init__(self, app_config):
        """Initialize the class with an `AppConfig`."""
        super().__init__()
        self._running_server: Optional[pgnet.Server] = None
        self._game_class = app_config.game_class
        self._make_widgets(app_config)
        self.app.controller.set_active_callback("server", self.set_focus)

    def _make_widgets(self, app_config):
        info_label = kx.XLabel(
            text=INFO_TEXT,
            halign="left",
            valign="top",
            padding=(10, 10),
            font_size="18dp",
        )
        left_frame = kx.XBox(orientation="vertical")
        left_frame.add_widgets(
            info_label,
        )
        left_frame.make_bg(kx.get_color("purple", v=0.2))
        config_panel_widgets = {
            "admin_password": kx.XInputPanelWidget("Admin password:"),
            "save_file": kx.XInputPanelWidget("Save file:", 'str'),
            "port": kx.XInputPanelWidget("Port:", 'int', pgnet.util.DEFAULT_PORT),
            "require_user_password": kx.XInputPanelWidget(
                "Require user password:",
                widget="bool",
                default=True,
            ),
        }
        self._config_panel = kx.XInputPanel(
            config_panel_widgets,
            invoke_text="Launch server",
        )
        self._config_panel.bind(on_invoke=self._on_config_invoke)
        config_frame = kx.XAnchor.wrap(self._config_panel)
        config_frame.set_size(hy=5)
        self.shutdown_btn = kx.XButton(
            text="Shutdown server",
            on_release=self._shutdown_server,
            disabled=True,
        )
        self.shutdown_btn.set_size(x="250dp", y="75dp")
        return_btn = kx.XButton(
            text="Return to client",
            on_release=self._return_to_client,
        )
        return_btn.set_size(x="250dp", y="75dp")
        right_frame = kx.XBox(orientation="vertical")
        right_frame.add_widgets(
            config_frame,
            kx.XAnchor.wrap(self.shutdown_btn),
            kx.XAnchor.wrap(return_btn),
        )
        main_frame = kx.XBox()
        main_frame.add_widgets(left_frame, right_frame)
        self.add_widget(main_frame)

    def _on_config_invoke(self, w, values):
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
