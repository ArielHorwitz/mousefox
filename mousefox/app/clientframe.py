"""Home of `ClientFrame`."""

from typing import Optional
import asyncio
import functools
import kvex as kx
import pgnet
from .connectpanel import ConnectPanel
from .userframe import UserFrame


class ClientFrame(kx.XAnchor):
    """Main client frame.

    This frame contains the `ConnectPanel` and spawns a `UserFrame` for each
    successful connection.
    """

    _conpath = "client"

    def __init__(self, app_config):
        """Initialize the class with an `AppConfig`."""
        super().__init__()
        self._game_widget_factory = app_config.game_widget
        self._make_widgets(app_config)
        self._client: Optional[pgnet.Client] = None
        self.app.menu.set_callback("app", "disconnect", self._disconnect)
        self.app.controller.bind("client.user.disconnect", self._disconnect)
        self.app.controller.set_active_callback(self._conpath, self._on_screen)
        self._on_screen()

    def update(self, *args):
        """Background refresh tasks."""
        if self._user_container.content:
            self._user_container.content.update()

    def _make_widgets(self, app_config):
        self._connect_panel = ConnectPanel(app_config, self._set_client)
        placeholder = kx.XPlaceholder(label_text="Error: not connected.")
        self._user_container = kx.XContainer(placeholder)
        self._sm = kx.XScreenManager.from_widgets(
            dict(
                connect=self._connect_panel,
                user=self._user_container,
            ),
            transition=kx.FadeTransition(duration=0.2),
        )
        self._sm.bind(current=self._on_screen)
        self.add_widget(self._sm)

    def _on_screen(self, *args):
        if self._sm.current == "connect":
            assert self._user_container.content is None
            self.app.menu.get_button("app", "disconnect").disabled = True
            self.app.menu.get_button("app", "leave_game").disabled = True
            if self.app.controller.active.startswith(self._conpath):
                self.app.controller.active = f"{self._conpath}.connect"
            self._connect_panel.set_focus()
        elif self._sm.current == "user":
            self.app.menu.get_button("app", "disconnect").disabled = False
            if self.app.controller.active.startswith(self._conpath):
                self.app.controller.active = f"{self._conpath}.user"
            userframe = self._user_container.content
            if userframe:
                userframe.set_focus()
        else:
            raise RuntimeError(f"Unknown screen: {self._sm.current}")

    def _set_client(self, client: pgnet.Client, /):
        """Set a client for the app to use."""
        asyncio.create_task(self._async_set_client(client))

    async def _async_set_client(self, client: pgnet.Client, /):
        assert not self._client
        self._client = client
        self.app.set_feedback(client.status)
        user_frame = UserFrame(client, self._game_widget_factory)
        self._user_container.content = user_frame
        client.on_status = functools.partial(self._on_client_status, client)
        client.on_connection = functools.partial(self._on_client_connected, client)
        await client.async_connect()
        assert not client.connected
        self._user_container.content = None
        self._client = None
        self._sm.current = "connect"

    def _on_client_connected(self, client: pgnet.Client, connected: bool):
        assert client is self._client
        if not connected:
            return
        client.on_connection = None
        self._sm.current = "user"

    def _on_client_status(self, client: pgnet.Client, status: str):
        assert client is self._client
        self.app.set_feedback(status, "normal" if client.connected else "error")

    def _disconnect(self, *args):
        if not self._client:
            return
        self._client.disconnect()
